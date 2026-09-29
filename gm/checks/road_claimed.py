"""The party on a road it never set out on.

Measured 2026-09-28 (docs/playtest-2026-09-28.md, items 17 and 20.5): with the engine
holding the party at the way in, the page said "You are now on the outskirts, where the
immediate reach of Vormoor's presence fades" and set it on "the road toward Dustgate";
every later turn resolved from the way in. A road is the engine's to put the party on — a
journey, or a road head of the settlement's outside (`rules/outskirts.py`) — and the page
may not claim one otherwise.

Detect in code: a claim of being on, taking or setting out along the road to a
settlement the world's roads reach ("on the road to X", "take the road toward X", "set
out for X"), outside quoted speech — or that road put in front of the party ("the road
to X is…", "stretches…"), quoted or not — when (1) no journey happened this beat, (2) the party
does not stand at X's road head or on its stretch of road, and (3) the reading has no
journey act. Repair: where the party is, and where that road starts. Backstop: cut the
sentence.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from . import _space

ORDER = 63
KINDS = frozenset({"road-claimed"})
DOORS = frozenset({"turn", "outcome"})

_CLAIM = (r"\b(?:on|along|down|up|onto|take|takes|took|taking|follow|follows|followed|"
          r"following|walk|walks|walked|walking|set(?:s|ting)?\s+(?:out|off)\s+(?:on|along|"
          r"down))\s+the\s+(?:\w+\s+){{0,2}}(?:road|path|track|highway|trail)\s+"
          r"(?:to|toward|towards|for)\s+{name}\b"
          r"|\bset(?:s|ting)?\s+(?:out|off)\s+(?:for|toward|towards)\s+{name}\b"
          r"|\b(?:road|path|track|highway|trail)\s+(?:to|toward|towards)\s+{name}\s+"
          r"(?:stretches|runs|lies|unwinds|winds|climbs)\s+(?:out\s+)?(?:before|ahead|in front)")


# The road put in front of the party: "the road toward Dustgate is a straight, punishing
# line of white stone" (turn 8, with the engine holding the party at the way in); "The
# road to Grotburrow isn't for the faint of heart", said by a stranger in a wood nowhere
# near it (turn 9, item 20.5 — the owner's own example, so quoted speech counts here).
# A road said to START somewhere ("the road to Dustgate leaves from the outskirts") is
# the brief's fact, not a claim, and none of these verbs match it.
_PRESENT = (r"\bthe\s+(?:\w+\s+){{0,2}}(?:road|path|track|highway|trail)\s+(?:to|toward|"
            r"towards)\s+{name}\s+(?:is|isn't|is\s+not|stretches|runs|lies|winds|unwinds|"
            r"climbs|cuts|twists|ahead|before|in\s+front)\b")


def _patterns(ctx) -> list[tuple[str, re.Pattern, re.Pattern]]:
    out = []
    for r in _space.roads(ctx):
        name = re.escape(str(r.to_name))
        out.append((str(r.to_name), re.compile(_CLAIM.format(name=name), re.I),
                    re.compile(_PRESENT.format(name=name), re.I)))
    return out


def _on_it(ctx, to_name: str) -> bool:
    """Whether the party stands at this road's head or on its stretch of road."""
    from rules import outskirts

    at = str(getattr(ctx.scene, "at", "") or "")
    slug = outskirts.road_head_of(at)
    if not slug:
        return False
    road = next((r for r in _space.roads(ctx) if r.to_name == to_name), None)
    return road is not None and \
        outskirts._road_slug(road.to_id) == "the-road-to-" + slug


def find(ctx) -> list[Finding]:
    if _space.journeyed(ctx) or "journey" in _space.reading_acts(ctx):
        return []
    flagged: list[tuple[str, str]] = []
    for s in _space.sentences(ctx.text):
        plain = _space.unquoted(s)
        for to_name, claim, present in _patterns(ctx):
            if (claim.search(plain) or present.search(s)) and not _on_it(ctx, to_name):
                flagged.append((s, to_name))
                break
    if not flagged:
        return []
    starts = {r.to_name: r.leaves_from for r in _space.roads(ctx)}
    try:
        here = ctx.engine.here().name if ctx.engine is not None else ""
    except Exception:  # noqa: BLE001
        here = ""
    said = "; ".join(f"the road to {n} starts from {starts.get(n) or 'the outskirts'}"
                     for n in dict.fromkeys(n for _s, n in flagged))
    return [Finding(
        kind="road-claimed",
        detail=f"the page puts the party on a road it has not taken: "
               f"{', '.join(dict.fromkeys(n for _s, n in flagged))}",
        fix_hint=(f"The party is at {here or 'where the engine holds it'}, not on any road; "
                  f"{said}. Say where they stand."),
        weight=2, sentences=tuple(s for s, _n in flagged))]


def backstop(ctx, text: str, findings: list) -> tuple[str, list[str]]:
    notes: list[str] = []
    for f in findings:
        if f.kind != "road-claimed":
            continue
        for s in f.sentences:
            if s in text:
                text = re.sub(r"\s*" + re.escape(s), "", text, count=1).strip()
                notes.append(f"cut: {s[:80]}")
    return text, notes
