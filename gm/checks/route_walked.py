"""A walk the engine made through places the page never mentions.

Measured 2026-09-28 (docs/playtest-2026-09-28.md, 16.2): "I leave the village" walked the
party through the well, and the page gave it half a line — "the path through the well now
a memory in the haze" — while describing arrival at a gate. The engine's tell carries the
route (`went_by`, and since Lane B each place's own line, `went_by_about`); a beat that
names none of the places passed has not walked it.

Detect in code: a `travel` this beat with a non-empty `went_by`, and prose that names none
of those places by name or by head word. Repair with a targeted call — one clause for each
place passed, in order. There is no backstop: a missing walk cannot be cut into being, and
the tell stands on the record.
"""
from __future__ import annotations

import re

from gm.narration import Finding

from . import _space

ORDER = 60
KINDS = frozenset({"route-not-walked"})
DOORS = frozenset({"turn", "outcome"})

_ARTICLES = ("the ", "a ", "an ")


def _handles(name: str) -> list[str]:
    """The words a place is found by on the page: its name, and its last word."""
    low = " ".join(str(name or "").lower().split())
    for art in _ARTICLES:
        if low.startswith(art):
            low = low[len(art):]
            break
    out = [low] if low else []
    tail = low.split()[-1] if low.split() else ""
    if tail and len(tail) >= 3 and tail not in out:
        out.append(tail)
    return out


def _named(text: str, name: str) -> bool:
    low = str(text or "").lower()
    return any(re.search(rf"\b{re.escape(h)}s?\b", low) for h in _handles(name))


def find(ctx) -> list[Finding]:
    found: list[Finding] = []
    for e in _space.effects(ctx, "travel", "biome"):
        passed = [str(n) for n in (e.get("went_by") or []) if str(n)]
        if not passed:
            continue
        if any(_named(ctx.text, n) for n in passed):
            continue
        about = {r.get("name"): r.get("about") for r in (e.get("went_by_about") or [])
                 if isinstance(r, dict)}
        route = "; ".join(f"{n} ({about[n]})" if about.get(n) else n for n in passed)
        found.append(Finding(
            kind="route-not-walked",
            detail=f"the walk passed {', '.join(passed)} and the page names none of them",
            fix_hint=(f"Walk the route the engine walked: one clause for each place "
                      f"passed, in order — {route} — before arriving at "
                      f"{e.get('place_name') or 'the destination'}."),
            weight=1))
    return found
