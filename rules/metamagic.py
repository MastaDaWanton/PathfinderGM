"""Metamagic: a transform of a COPY of the spell, made for one cast.

A metamagic feat's document (content/feats/mechanics/metamagic.json) says which transform
it is and how many slot levels it costs: `{"metamagic": {"does": "extend", "levels": 1}}`.
The cast names the feats (`cast` param `metamagic`); `apply` returns a deep copy of the
spell with the transform made on it, and every reader downstream — the duration clock,
the range, the components gate, the dice — reads that copy as the spell. The book's spell
is never touched, and nothing about the feat is stored on the caster: remove the param
and the cast is the plain spell again (law 2's shape, one cast long).

Prior art (docs/implementation-audit-2026-11-22.md §4, lesson 6): Foundry PF1 never built
metamagic (issues #17, #1069: users duplicate the spell entry by hand); Owlcat declares
`isExtendable` on each duration value rather than inferring it. Here the parsed
`duration_value` is that declaration: only a clocked duration (per level, fixed, rolled)
can be extended, which is the feat's own exclusion of "concentration, instantaneous, or
permanent". Could not source how Owlcat hooks Empower and Maximize into damage.

The rules (CRB, Metamagic Feats, read on aonprd.com 2026-11-22):
- Extend (+1): "lasts twice as long"; not concentration, instantaneous or permanent.
- Empower (+2): "all variable, numeric effects ... increased by half, including bonuses
  to those dice rolls"; saves and opposed rolls are not affected.
- Maximize (+3): "all variable, numeric effects ... maximized"; with Empower, "the
  maximum result plus half the normally rolled result".
- Enlarge (+1): close, medium or long range doubled; no other range benefits.
- Silent (+1): no verbal component; "Bard spells cannot be enhanced by this feat."
- Still (+1): no somatic component.
- Quicken (+4): a swift action; not a spell whose casting time is more than 1 round or
  a full-round action (the Special: a spontaneous caster quickens without the longer
  casting time). A quickened spell does not provoke.
- A spontaneous caster's metamagic spell "takes longer to cast": a full-round action
  for a standard-action spell; a prepared caster fixes the feat at preparation and casts
  in the normal time.
"""
from __future__ import annotations

import copy
import re

# The closed set of transforms a document may name. A new one is code here, never data.
DOES = ("extend", "empower", "maximize", "enlarge", "silent", "still", "quicken")


def document_problems(at: str, doc) -> list[str]:
    """A feat document's `metamagic` block, checked with the fix named."""
    if not isinstance(doc, dict) or str(doc.get("does") or "") not in DOES:
        return [f"{at}.metamagic: {{\"does\": one of {', '.join(DOES)}, \"levels\": the "
                f"slot levels it adds}}."]
    if not isinstance(doc.get("levels"), int) or not 0 <= doc["levels"] <= 9:
        return [f"{at}.metamagic.levels: the slot levels the feat adds, a whole number "
                f"(Extend Spell: 1)."]
    return []


def chosen(params) -> list[str]:
    """The feat ids a cast names, as a list: `["extend-spell"]` from a list or "a, b"."""
    raw = (params or {}).get("metamagic")
    if raw in (None, ""):
        return []
    items = raw if isinstance(raw, (list, tuple)) else re.split(r"[,+]", str(raw))
    out = []
    for item in items:
        key = re.sub(r"[^a-z0-9]+", "-", str(item).strip().lower()).strip("-")
        if key and not key.endswith("-spell"):
            key += "-spell"                     # "extend" is Extend Spell
        if key and key not in out:
            out.append(key)
    return out


def held(actor) -> dict[str, dict]:
    """The metamagic feats this actor holds: `{feat id: document}`."""
    from . import feats as feats_mod

    out = {}
    for raw in getattr(actor, "feats", None) or ():
        doc = feats_mod.document(raw)
        if doc and doc.get("metamagic"):
            out[doc["id"]] = doc
    return out


def document_levels(ids) -> int:
    """The slot levels these feats add, by their documents alone (a prepared copy's slot
    is the copy's, whoever holds it now)."""
    from . import feats as feats_mod

    docs = feats_mod.documents()
    return sum(int((docs.get(i) or {}).get("metamagic", {}).get("levels", 0)) for i in ids)


def levels(actor, ids) -> int:
    """The slot levels these feats add for this actor."""
    mine = held(actor)
    return sum(int(mine[i]["metamagic"]["levels"]) for i in ids if i in mine)


def refusal(actor, spell, ids, *, spontaneous: bool) -> str:
    """Why these feats cannot be applied to this spell by this caster, or ""."""
    mine = held(actor)
    for fid in ids:
        doc = mine.get(fid)
        if doc is None:
            return f"{actor.name} does not have the {fid.replace('-', ' ')} feat."
        does = doc["metamagic"]["does"]
        why = _not_for(does, spell, actor, spontaneous)
        if why:
            return f"{doc['name']} cannot be applied to {spell.name}: {why}"
    return ""


def _not_for(does: str, spell, actor, spontaneous: bool) -> str:
    from . import spells as spells_mod

    if does == "extend":
        kind = str((spell.duration_value or {}).get("kind") or "")
        if kind not in ("per_level", "fixed", "rolled"):
            return "its duration is not one that can last twice as long (concentration, " \
                   "instantaneous and permanent spells are not affected)."
    if does in ("empower", "maximize"):
        plan = spells_mod.casting_plan(spell, 1)
        if not plan.get("dice"):
            return "it has no variable numeric effect the engine rolls."
    if does == "enlarge" and str((spell.range_value or {}).get("kind") or "") \
            not in ("close", "medium", "long"):
        return "only a close, medium or long range can be enlarged."
    comps = [str(c).strip().upper() for c in spell.components or ()]
    if does == "silent":
        from . import casting

        if "V" not in comps:
            return "it has no verbal component."
        if str(casting.caster_data(actor).get("list") or "").lower() == "bard":
            return "bard spells cannot be enhanced by Silent Spell."
    if does == "still" and "S" not in comps:
        return "it has no somatic component."
    if does == "quicken":
        timing = str(spell.casting_time or "").lower()
        if not spontaneous and not re.match(r"\s*(1\s+)?(standard|move|swift)", timing):
            return f"it takes {spell.casting_time or 'longer'} to cast, and a spell of " \
                   f"more than 1 round or a full round cannot be quickened."
        if spontaneous and not re.match(r"\s*(1\s+)?(standard|move|swift|full|round)",
                                        timing):
            return f"it takes {spell.casting_time or 'longer'} to cast."
    return ""


def apply(spell, actor, ids):
    """A copy of `spell` with each named feat's transform made on it.

    The copy carries `metamagic`, the transforms applied, for the readers that act at
    roll time (`dice_total`) and for the tell."""
    mine = held(actor)
    does = [mine[i]["metamagic"]["does"] for i in ids if i in mine]
    if not does:
        return spell
    out = copy.deepcopy(spell)
    if "extend" in does:
        d = dict(out.duration_value or {})
        if d.get("kind") in ("per_level", "fixed"):
            d["amount"] = int(d.get("amount", 1) or 1) * 2
            if d.get("base"):
                d["base"] = int(d["base"]) * 2
        elif d.get("kind") == "rolled":
            d["times"] = 2                       # read by `spells.roll_duration`
        out.duration_value = d
    if "enlarge" in does:
        r = dict(out.range_value or {})
        r["feet"] = int(r.get("feet", 0) or 0) * 2
        r["add"] = int(r.get("add", 0) or 0) * 2
        out.range_value = r
    if "silent" in does:
        out.components = [c for c in out.components if str(c).strip().upper() != "V"]
    if "still" in does:
        out.components = [c for c in out.components if str(c).strip().upper() != "S"]
    if "quicken" in does:
        out.casting_time = "swift action"
    # The name is left alone: buffs and manifestations take their source from it, and an
    # "Extended Bless" beside a Bless would be two sources where the book has one spell.
    out.metamagic = does
    return out


ADJECTIVE = {"extend": "extended", "empower": "empowered", "maximize": "maximized",
             "enlarge": "enlarged", "silent": "silent", "still": "stilled",
             "quicken": "quickened"}


def named(name: str, ids) -> str:
    """"Fireball (empowered)" for a copy prepared with Empower Spell; the name alone for
    none. By the feat ids, so it reads without knowing who holds them."""
    from . import feats as feats_mod

    docs = feats_mod.documents()
    words = [ADJECTIVE[docs[i]["metamagic"]["does"]] for i in ids or ()
             if (docs.get(i) or {}).get("metamagic")]
    return f"{name} ({', '.join(words)})" if words else name


def said(spell) -> str:
    """"empowered, maximized" — for the cast's tell; "" for a plain cast."""
    return ", ".join(ADJECTIVE[d] for d in getattr(spell, "metamagic", None) or ())


def dice_said(spell, state: dict, missiles=None) -> str:
    """The dice line's companion when Empower or Maximize remade the roll: "Empowered:
    the 14 rolled counts as 21." "" when nothing was remade, so a plain cast stays quiet
    and the narrator is never left with two totals to choose between."""
    does = [d for d in getattr(spell, "metamagic", None) or () if d in ("empower",
                                                                        "maximize")]
    if not does or "raw_rolled" not in state:
        return ""
    raw = int(state["raw_rolled"])
    now = (sum(int(m["amount"]) for m in missiles) if missiles is not None
           else int(state.get("rolled", 0)))
    head = " and ".join(ADJECTIVE[d] for d in does).capitalize()
    return f"{head}: the {raw} rolled counts as {now}."


def dice_total(spell, dice: str, rolled: int, faces=None) -> int:
    """A rolled total as the copy's Empower and Maximize make it.

    Maximize: the dice at their maximum, the flat part included. Empower: half again,
    "including bonuses to those dice rolls". Both: "the maximum result plus half the
    normally rolled result"."""
    does = getattr(spell, "metamagic", None) or ()
    if not dice or not ({"empower", "maximize"} & set(does)):
        return rolled
    m = re.fullmatch(r"\s*(\d+)d(\d+)\s*([+-]\s*\d+)?\s*", str(dice))
    best = (int(m.group(1)) * int(m.group(2)) + int((m.group(3) or "0").replace(" ", ""))
            if m else rolled)
    if "maximize" in does:
        return best + (rolled // 2 if "empower" in does else 0)
    return rolled + rolled // 2
