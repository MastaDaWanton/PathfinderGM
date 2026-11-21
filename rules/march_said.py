"""A forced march's hourly checks said as one sentence, for the tell (owner, 2026-11-21).

feat/hex-travel-to's walk put one sentence a walker an hour into the hex move's tell, and
the story printed five "Shadow Constitution 15 vs DC 10, holds up" lines for one night's
push. The owner: "all the checks should go in the GM lane and be replace by descriptions
... of what those checks represent". The figures stay in the effects (and the GM's
record); the tell the narrator is fed says what the night meant, once: how far past the
day's walk, who held up, and who faltered, in which hour, and how it left them. That is
the Alexandrian's one passage for a vector of travel rather than a line a watch
("Hexcrawl Addendum: Describing Travel"; docs/research/2026-11-21-travel-prose.md).

Engine-side on purpose (law three): the narrator never reads these effects; it reads the
tell this writes. `said` takes the `forced_march` effects exactly as `_forced_march`
writes them (`ref`, `who`, `hour`, `passed`, `conditions`, `mount`).
"""
from __future__ import annotations

from . import words as english


def said(effects) -> str:
    """One sentence for the march, no figure in it, or "" when nobody marched."""
    rows = [e for e in effects or [] if isinstance(e, dict) and e.get("kind") == "forced_march"]
    if not rows:
        return ""
    held, faltered = [], []
    for who in dict.fromkeys(str(e.get("who") or "someone") for e in rows):
        bad = next((e for e in rows if str(e.get("who") or "someone") == who
                    and not e.get("passed")), None)
        if bad is None:
            held.append(who)
            continue
        hurt = [str(c) for c in (bad.get("conditions") or []) if c]
        faltered.append(f"{who} falters in hour {english.number(int(bad.get('hour') or 0))}"
                        + (f" and is left {' and '.join(hurt)}" if hurt else ", hurt by it"))
    n = len({int(e.get("hour") or 0) for e in rows})
    out = (f"A forced march, {english.number(n)} hour{'s' if n != 1 else ''} past the "
           f"day's walking")
    parts = []
    if held:
        parts.append(f"{_and(held)} {'holds' if len(held) == 1 else 'hold'} up through "
                     f"all of it")
    parts += faltered
    return out + (": " + "; ".join(parts) if parts else "") + "."


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
