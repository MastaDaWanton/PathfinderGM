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
#
# Feat loop b1 (2026-11-22) added the rest of the book's metamagic, read on aonprd.com
# (CRB, APG, UM FeatDisplay pages) the same day:
# - Heighten (+N): "a higher spell level than normal (up to a maximum of 9th level) ...
#   All effects dependent on spell level (such as saving throw DCs ...)". Stepped: the
#   cast names how many levels, "heighten-spell-2".
# - Widen (+3): "Any numeric measurements of the spell's area increase by 100%" for a
#   burst, emanation or spread (a cone-shaped burst is a burst).
# - Reach (+1 a step): touch -> close -> medium -> long; "Spells modified by this feat
#   that require melee touch attacks instead require ranged touch attacks." Stepped.
# - Merciful (+0): "inflict nonlethal damage instead ... of that same type".
# - Intensified (+1): "increases the maximum number of damage dice by 5 levels".
# - Elemental (+1): "replace a spell's normal damage with that energy type" (the feat's
#   own pick: Elemental Spell (cold)). The split-in-half option is NOT built.
# - Piercing (+1): "treats the spell resistance of the target as 5 lower".
# - Persistent (+2): a creature that saves "must make another saving throw".
# - Focused (+1): one creature's "saving throw DC ... is increased by +2".
# - Selective (+1): an instantaneous area spell excludes "a number of targets ... equal to
#   the ability score modifier used to determine bonus spells".
# - Disruptive (+1): those affected "must make concentration checks when using spells ...
#   (DC equals the save DC of the disruptive spell plus the level of the spell being
#   cast) for 1 round".
# - Ectoplasmic (+1): "full effect against incorporeal ... creatures".
# - The damage riders (`rider`): Dazing (+3, dazed, Will), Sickening (+2, sickened, Fort),
#   Thundering (+2, deafened, Fort) -- "If the spell allows a saving throw, a successful
#   save negates"; else the named save -- for rounds equal to the spell's original level;
#   Rime (+1, cold: entangled), Flaring (+1, fire/light/electricity: dazzled), Concussive
#   (+2, sonic: -2 on attacks, saves, skills and ability checks), Burning (+2, acid or
#   fire: 2 x the spell's level at the start of the creature's next turn), Toppling (+1,
#   force: a trip check at caster level + the casting ability bonus).
DOES = ("extend", "empower", "maximize", "enlarge", "silent", "still", "quicken",
        "heighten", "widen", "reach", "merciful", "intensify", "elemental", "pierce",
        "persist", "focus", "select", "disrupt", "ectoplasm", "rider")

# What a `rider` may lay, and the fields it carries (see `_rider_problems`).
RIDER_KEYS = ("condition", "burn", "trip", "save", "needs", "damage_types")

# Reach Spell's ladder (CRB range categories).
REACH_LADDER = ("touch", "close", "medium", "long")
_REACH_RANGES = {"close": {"kind": "close", "feet": 25, "add": 5, "every": 2},
                 "medium": {"kind": "medium", "feet": 100, "add": 10, "every": 1},
                 "long": {"kind": "long", "feet": 400, "add": 40, "every": 1}}


def base_id(fid: str) -> str:
    """"heighten-spell" for "heighten-spell-2": the feat, without the cast's step count."""
    return re.sub(r"-\d+$", "", str(fid))


def steps(fid: str) -> int:
    """How many steps a stepped feat is taken ("heighten-spell-2" is 2); 1 otherwise."""
    m = re.search(r"-(\d+)$", str(fid))
    return max(1, int(m.group(1))) if m else 1


def document_problems(at: str, doc) -> list[str]:
    """A feat document's `metamagic` block, checked with the fix named."""
    if not isinstance(doc, dict) or str(doc.get("does") or "") not in DOES:
        return [f"{at}.metamagic: {{\"does\": one of {', '.join(DOES)}, \"levels\": the "
                f"slot levels it adds}}."]
    if not isinstance(doc.get("levels"), int) or not 0 <= doc["levels"] <= 9:
        return [f"{at}.metamagic.levels: the slot levels the feat adds, a whole number "
                f"(Extend Spell: 1)."]
    out = []
    if sorted(set(doc) - {"does", "levels", "steps", "rider"}):
        out.append(f"{at}.metamagic: only does, levels, steps and rider.")
    if "steps" in doc and (isinstance(doc["steps"], bool) or not isinstance(
            doc["steps"], int) or not 1 < doc["steps"] <= 9):
        out.append(f"{at}.metamagic.steps: the most steps the cast may name (Heighten "
                   f"Spell: 8, to 9th level from 1st), each costing `levels`.")
    if (doc["does"] == "rider") != ("rider" in doc):
        out.append(f"{at}.metamagic.rider: what the spell lays on a creature it damages, "
                   f"for does \"rider\" and no other.")
    elif doc["does"] == "rider":
        out.extend(_rider_problems(f"{at}.metamagic.rider", doc["rider"]))
    return out


def _rider_problems(at: str, rider) -> list[str]:
    from .tables import CONDITIONS

    if not isinstance(rider, dict) or sorted(set(rider) - set(RIDER_KEYS)):
        return [f"{at}: an object of {', '.join(RIDER_KEYS)}."]
    lays = [k for k in ("condition", "burn", "trip") if k in rider]
    out = []
    if len(lays) != 1:
        out.append(f"{at}: exactly one of condition (a condition key), burn (times the "
                   f"spell's level, next turn) or trip (true).")
    if "condition" in rider and str(rider["condition"]) not in CONDITIONS:
        out.append(f"{at}.condition: {rider['condition']!r} is not a condition.")
    if "burn" in rider and (not isinstance(rider["burn"], int) or rider["burn"] < 1):
        out.append(f"{at}.burn: a whole number, the multiple of the spell's level.")
    if rider.get("save", "") not in ("", "fort", "ref", "will"):
        out.append(f"{at}.save: fort, ref or will -- the save that negates it when the "
                   f"spell has none of its own.")
    for key in ("needs", "damage_types"):
        if key in rider and (not isinstance(rider[key], list) or not rider[key]):
            out.append(f"{at}.{key}: a list of words.")
    return out


def chosen(params) -> list[str]:
    """The feat ids a cast names, as a list: `["extend-spell"]` from a list or "a, b"."""
    raw = (params or {}).get("metamagic")
    if raw in (None, ""):
        return []
    items = raw if isinstance(raw, (list, tuple)) else re.split(r"[,+]", str(raw))
    out = []
    for item in items:
        key = re.sub(r"[^a-z0-9]+", "-", str(item).strip().lower()).strip("-")
        # A stepped feat names its count: "heighten 2", "heighten-spell-2", "reach:3".
        m = re.fullmatch(r"(.+?)(?:-spell)?-(\d+)(?:-spell)?", key)
        if m:
            key = f"{m.group(1)}-spell-{m.group(2)}"
        elif key and not key.endswith("-spell"):
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
    return sum(_cost((docs.get(base_id(i)) or {}).get("metamagic") or {}, i) for i in ids)


def levels(actor, ids) -> int:
    """The slot levels these feats add for this actor."""
    mine = held(actor)
    return sum(_cost(mine[base_id(i)]["metamagic"], i) for i in ids if base_id(i) in mine)


def _cost(doc: dict, fid: str) -> int:
    return int(doc.get("levels", 0)) * (steps(fid) if doc.get("steps") else 1)


def refusal(actor, spell, ids, *, spontaneous: bool) -> str:
    """Why these feats cannot be applied to this spell by this caster, or ""."""
    mine = held(actor)
    for fid in ids:
        doc = mine.get(base_id(fid))
        if doc is None:
            return f"{actor.name} does not have the {base_id(fid).replace('-', ' ')} feat."
        does = doc["metamagic"]["does"]
        if base_id(fid) != fid and not doc["metamagic"].get("steps"):
            return f"{doc['name']} is applied once, without a number."
        if steps(fid) > int(doc["metamagic"].get("steps") or 1):
            return f"{doc['name']} is applied at most {doc['metamagic']['steps']} times."
        # A rider asks the spell as an Elemental Spell named with it makes it: a cold
        # fireball is a cold spell to Rime Spell.
        shaped = spell if does != "rider" else apply(spell, actor, [
            i for i in ids if (mine.get(base_id(i)) or {}).get("metamagic", {}).get(
                "does") == "elemental"])
        why = _not_for(does, shaped, actor, spontaneous, doc, steps(fid))
        if why:
            return f"{doc['name']} cannot be applied to {spell.name}: {why}"
    return ""


def _not_for(does: str, spell, actor, spontaneous: bool, doc: dict | None = None,
             n: int = 1) -> str:
    from . import spells as spells_mod

    why = _not_for_b1(does, spell, actor, doc or {}, n)
    if why:
        return why

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


def _area_shape(spell) -> str:
    """burst, spread or emanation -- "cone-shaped burst" and "cylinder-shaped spread"
    are a burst and a spread -- else the parsed shape, else ""."""
    from . import spells as spells_mod

    text = str(getattr(spell, "area", "") or "")
    m = re.search(r"\b(burst|spread|emanation)\b", text, re.I)
    if m:
        return m.group(1).lower()
    return str(spells_mod.parse_area(text).get("shape") or "") if text.strip() else ""


def _not_for_b1(does: str, spell, actor, doc: dict, n: int) -> str:
    """The b1 transforms' own exclusions, each the feat's printed one."""
    from . import spells as spells_mod

    plan = spells_mod.casting_plan(spell, 1) if does in (
        "merciful", "elemental", "intensify", "rider") else {}
    save = str(getattr(spell, "save", "") or "")
    harmless = bool(getattr(spell, "save_harmless", False))
    lvl = min((getattr(spell, "lists", None) or {}).values(), default=0)
    if does == "heighten" and lvl + n > 9:
        return "a spell cannot be heightened past 9th level."
    if does == "widen" and _area_shape(spell) not in ("burst", "spread", "emanation"):
        return "only a burst, emanation or spread can be widened."
    if does == "reach":
        kind = str((spell.range_value or {}).get("kind") or "")
        if kind not in REACH_LADDER[:-1]:
            return "only a range of touch, close or medium can be reached."
        if REACH_LADDER.index(kind) + n >= len(REACH_LADDER):
            return (f"{kind} range reaches long range in "
                    f"{len(REACH_LADDER) - 1 - REACH_LADDER.index(kind)} step(s) at most.")
    if does in ("merciful", "elemental") and plan.get("kind") != "damage":
        return "it deals no damage the engine rolls."
    if does == "elemental" and str(doc.get("target") or "") not in ("acid", "cold",
                                                                     "electricity", "fire"):
        return "Elemental Spell names its energy: acid, cold, electricity or fire."
    if does == "intensify" and not int((spell.scaling or {}).get("cap_dice", 0) or 0):
        return "its damage has no maximum number of dice to raise."
    if does == "pierce" and getattr(spell, "sr", None) is not True:
        return "spell resistance does not apply to it."
    if does in ("persist", "focus") and (not save or harmless):
        return "it calls for no saving throw to resist."
    if does == "focus" and not (str(getattr(spell, "area", "") or "").strip()
                                or spells_mod._counts_its_targets(spell)):
        return "it affects or targets only one creature."
    if does == "select" and (not str(getattr(spell, "area", "") or "").strip()
                             or str((spell.duration_value or {}).get("kind") or "")
                             != "instantaneous"):
        return "only an instantaneous spell with an area can be selective."
    if does == "rider":
        rider = doc.get("metamagic", {}).get("rider") or {}
        words = {str(d).lower() for d in getattr(spell, "descriptors", None) or ()}
        if rider.get("needs") and not words & set(rider["needs"]):
            return f"it has none of the descriptors {', '.join(rider['needs'])}."
        if not rider.get("trip") and plan.get("kind") != "damage":
            return "it deals no damage the engine rolls."
    return ""


def apply(spell, actor, ids):
    """A copy of `spell` with each named feat's transform made on it.

    The copy carries `metamagic`, the transforms applied, for the readers that act at
    roll time (`dice_total`) and for the tell."""
    mine = held(actor)
    does = [mine[base_id(i)]["metamagic"]["does"] for i in ids if base_id(i) in mine]
    if not does:
        return spell
    out = copy.deepcopy(spell)
    _apply_b1(out, spell, mine, ids)
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


def _apply_b1(out, spell, mine: dict, ids) -> None:
    """The b1 transforms on the copy. The readers downstream take the copy as the spell:
    `areas.shape_of` reads `area_scale`, `spells.range_feet` the range, the dice the
    scaling and the documents; the engine reads the flags (`heightened`, `riders`,
    `metamagic_flags` through `flag`)."""
    from .tables import ENERGY_DAMAGE

    by = {mine[base_id(i)]["metamagic"]["does"]: (mine[base_id(i)], steps(i))
          for i in ids if base_id(i) in mine}
    if "heighten" in by:
        out.heightened = by["heighten"][1]
    if "widen" in by:
        out.area_scale = 2
    if "reach" in by:
        kind = str((out.range_value or {}).get("kind") or "")
        to = REACH_LADDER[min(len(REACH_LADDER) - 1,
                              REACH_LADDER.index(kind) + by["reach"][1])]
        if kind == "touch":
            from . import casting

            touch = casting.touch_attack(spell, 1)
            if touch is not None and str(touch.get("touch") or "melee") == "melee":
                # "require ranged touch attacks instead": the copy's own document says so.
                # The copy's SPELL documents, not an actor's effect store.
                out.effects[:] = [{**touch, "touch": "ranged"}] + [
                    e for e in out.effects
                    if not (isinstance(e, dict) and e.get("type") == "touch_attack")]
        out.range_value = {**_REACH_RANGES[to], "unit": "feet"}
        out.range = f"{to} ({out.range})"

    def walk(specs, fn):
        for e in specs or ():
            if isinstance(e, dict):
                fn(e)
                for branch in ("on_failure", "on_success", "effects", "options"):
                    walk(e.get(branch), fn)

    if "merciful" in by:
        walk(out.effects, lambda e: e.update(lethality="nonlethal")
             if e.get("type") == "damage" else None)
        if out.scaling:
            out.scaling = {**out.scaling, "lethality": "nonlethal"}
    if "intensify" in by and (out.scaling or {}).get("cap_dice"):
        out.scaling = {**out.scaling, "cap_dice": int(out.scaling["cap_dice"]) + 5}
    if "elemental" in by:
        energy = str(by["elemental"][0].get("target") or "")
        was = set()

        def swap(e):
            if e.get("type") == "damage":
                was.add(str(e.get("damage_type") or ""))
                e["damage_type"] = energy
        walk(out.effects, swap)
        if out.scaling:
            out.scaling = {**out.scaling, "damage_type": energy}
        out.element = energy
        # The copy's descriptor follows its energy: a cold fireball is a [cold] spell to
        # Rime Spell and to cold resistance alike (owner call, b1).
        out.descriptors = [d for d in out.descriptors
                           if str(d).lower() not in set(ENERGY_DAMAGE) | was] + [energy]
    out.riders = [dict(doc["metamagic"]["rider"], feat=doc["name"])
                  for doc, _ in by.values() if doc["metamagic"]["does"] == "rider"]
    out.metamagic_flags = sorted(by)


def flag(spell, does: str) -> bool:
    """Whether this cast's copy was made with that transform (Piercing, Persistent ...)."""
    return does in (getattr(spell, "metamagic_flags", None) or ())


ADJECTIVE = {"extend": "extended", "empower": "empowered", "maximize": "maximized",
             "enlarge": "enlarged", "silent": "silent", "still": "stilled",
             "quicken": "quickened", "heighten": "heightened", "widen": "widened",
             "reach": "reaching", "merciful": "merciful", "intensify": "intensified",
             "elemental": "elemental", "pierce": "piercing", "persist": "persistent",
             "focus": "focused", "select": "selective", "disrupt": "disruptive",
             "ectoplasm": "ectoplasmic", "rider": "riding"}


def named(name: str, ids) -> str:
    """"Fireball (empowered)" for a copy prepared with Empower Spell; the name alone for
    none. By the feat ids, so it reads without knowing who holds them."""
    from . import feats as feats_mod

    docs = feats_mod.documents()
    words = [_word(docs[base_id(i)]) for i in ids or ()
             if (docs.get(base_id(i)) or {}).get("metamagic")]
    return f"{name} ({', '.join(words)})" if words else name


def _word(doc: dict) -> str:
    """A feat's adjective: the book's own for a rider ("dazing" from Dazing Spell)."""
    does = doc["metamagic"]["does"]
    return doc["name"].split()[0].lower() if does == "rider" else ADJECTIVE[does]


def said(spell) -> str:
    """"empowered, maximized" — for the cast's tell; "" for a plain cast."""
    words = [ADJECTIVE[d] for d in getattr(spell, "metamagic", None) or () if d != "rider"]
    words += [r["feat"].split()[0].lower() for r in getattr(spell, "riders", None) or ()]
    return ", ".join(words)


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
