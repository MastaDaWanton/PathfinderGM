"""Harm with no victim: a damage roll that reached nobody, narrated as a hit (item 22.4).

Measured on the Bobby playtest, 2026-09-28, turn 13. Burning Hands from the Spells tab
resolved with `targets: []` and a bare "1d4 — 1" — no damage effect on anybody, the man
in the jerkin still at 4 of 4. The page burned him anyway: "the heat licks across his
face", "the man is thrown backward", "his face blackened by soot, his hands clutching his
scorched arms", "a raspy growl of pain". `contradicts_state` run on that beat found
nothing: `_name_stems` dropped "man", the wound sentences said "he" and "his", and the
wound words held no burn and no impact. FIREBALL (Zhu et al. 2023) records the same
failure in real D&D play — damage read as a kill "regardless of the target's true
remaining health"; this is it with no target at all.

Condition: an outcome that rolled damage and landed it on nobody — a cast whose targets
are empty, or E's `no_victim`, with no `damage` or `condition` effect on anybody but the
caster. Detect, for each person here the turn did not harm: the sentences about them
(`_people.about`, pronoun continuation included) that hold a harm word of the damage's
family — fire, impact, or a wound. Repair: one rewrite per sentence, the fact named
("the spell reached nobody; he is untouched"). Backstop: the sentences are cut and the
engine's plain fact stands in their place.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from ._page import cut, effects, field
from ._people import about

ORDER = 40
KINDS = frozenset({"harm-without-a-victim"})
DOORS = frozenset({"turn", "outcome", "plan"})

# Fire ON somebody, not fire as such: "a searing cone surging toward him" is the spell
# being cast, which happened; "his scorched arms" is a wound, which did not.
_GROUND = (r"(?!,?\s+(?:\w+\s+)?(?:earth|ground|soil|grass|brush|ferns?|air|path|floor|"
           r"scar|stones?|wood|trees?|leaves|mulch|moss|bark|canopy))")
_FIRE = (r"burn(?:s|ed|t)?\b(?!\s+(?:bright|low|steady))|scorch\w*\b" + _GROUND + r"|"
         r"sear(?:s|ed)\b|singe\w*|blacken\w*\b" + _GROUND + r"|soot\b|blister\w*|"
         r"char(?:s|red)\b" + _GROUND + r"|"
         r"(?:heat|flames?|fire)\s+(?:licks?|washes?|rolls?|engulfs?|sweeps?)\s+(?:over|"
         r"across|into)\s+(?:his|her|their|its|the)|engulf\w*|catch(?:es)?\s+fire|"
         r"on\s+fire|in\s+flames")
_IMPACT = (r"thrown\s+(?:back|backward|backwards|clear|off)|knocked\s+(?:back|down|flat)|"
           r"hits?\s+the\s+(?:ground|floor|dirt)|slams?\s+into|sent\s+(?:flying|sprawling)|"
           r"sprawl\w*|staggers?\s+back")
_WOUND = (r"wound\w*|bleed\w*|bloodied|blood\s+(?:runs|pours|wells)|injur\w*|"
          r"(?:cry|cries|gasps?|growls?|groans?|howls?|screams?)\s+(?:of|in|with)\s+pain|"
          r"clutch\w*\s+(?:his|her|their)\s+\w*\s*(?:arm|arms|face|side|chest|hand|hands|"
          r"leg|burns?|wound)|writh\w*|in\s+agony")
HARM = re.compile(rf"\b(?:{_FIRE}|{_IMPACT}|{_WOUND})", re.I)


def _no_victim(o) -> bool:
    """A damage roll that landed on nobody."""
    if field(o, "status") == "refused":
        return False
    effs = effects(o)
    caster = {str(field(o, "actor") or "")}
    for e in effs:
        if e.get("kind") == "cast":
            caster.add(str(e.get("ref") or ""))
    if any(e.get("kind") in ("damage", "condition", "ability_damage")
           and str(e.get("ref") or "") not in caster for e in effs):
        return False
    if any(e.get("no_victim") or e.get("reached_nobody") for e in effs):
        return True
    rolled = any("damage" in str(r.get("label", "") if isinstance(r, dict)
                                 else getattr(r, "label", "")).lower()
                 for r in (field(o, "rolls") or []))
    cast = [e for e in effs if e.get("kind") == "cast"]
    return rolled and bool(cast) and all(not (e.get("targets") or e.get("caught"))
                                         for e in cast)


def _unharmed(ctx) -> list[str]:
    harmed = {str(e.get("ref") or "") for o in ctx.outcomes for e in effects(o)
              if e.get("kind") in ("damage", "condition", "ability_damage")}
    return [r for r, a in ctx.scene.actors.items()
            if not getattr(a, "is_pc", False) and r not in harmed]


def _spell(ctx) -> str:
    for o in ctx.outcomes:
        if _no_victim(o):
            for e in effects(o):
                if e.get("kind") == "cast" and e.get("name"):
                    return str(e["name"])
    return "the spell"


def _flagged(ctx) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for ref in _unharmed(ctx):
        hits = [w for w, n in about(ctx, ref) if HARM.search(n)]
        if hits:
            out[ref] = hits
    return out


def find(ctx) -> list:
    if not any(_no_victim(o) for o in ctx.outcomes):
        return []
    found = []
    spell = _spell(ctx)
    for ref, hits in _flagged(ctx).items():
        name = called(str(ctx.scene.actors[ref].name))
        found.append(Finding(
            "harm-without-a-victim",
            f"{spell} reached nobody, and the prose harms {name}: {hits[0][:90]!r}",
            f"{spell} reached nobody: nothing was caught in it, and {name} is untouched "
            f"— not burned, not thrown, not hurt. Rewrite the sentence so the {spell} "
            f"misses them or lands on nothing, and {name} is exactly as they were.",
            weight=3, sentences=tuple(hits)))
    return found


def backstop(ctx, text: str, findings) -> tuple[str, list[str]]:
    """Cut what still harms somebody the roll never reached, and say who it reached."""
    from dataclasses import replace

    flagged = _flagged(replace(ctx, text=text))
    gone = [s for hits in flagged.values() for s in hits]
    if not gone:
        return text, []
    names = [called(str(ctx.scene.actors[r].name)) for r in flagged]
    kept = cut(text, gone)
    spell = _spell(ctx)
    line = (f"{spell[:1].upper()}{spell[1:]} catches nobody; {' and '.join(names)} "
            f"{'is' if len(names) == 1 else 'are'} untouched.")
    from gm.narration import _append_before_hand_back

    return _append_before_hand_back(kept, line), [
        f"harm without a victim: cut {len(gone)} sentence(s) and said nobody was caught"]


def called(name: str) -> str:
    """A descriptor as a sentence uses it: "man in a stained leather jerkin" → "the man
    in a stained leather jerkin"; a proper name as it is."""
    name = " ".join(str(name or "").split())
    if name[:1].islower() and not name.lower().startswith(("the ", "a ", "an ")):
        return f"the {name}"
    return name
