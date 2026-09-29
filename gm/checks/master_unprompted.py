"""master-approaches: the master of the market speaks to a player who did not seek them.

Measured on the 2026-09-28 playtest (item 10): the market's one person was its authority
and its seller at once, and — minted on arrival because the trade panel needed a body —
the first person the player met there, walking up to them. The market's master is now an
authority who sells nothing and is busy (`rules/audience.py`); the brief says so
(`gm/brief/market_master.py`) and this holds the page to it.

It fires when the master has a line to the player on a beat the player did not turn to
them (`audience.addressed`) and the player has no ground for the master's attention
(`audience.grounds`: regard, a background tie to the market, the master's own business,
the evening count). `keeper-forward` covers a keeper the player has never dealt with;
this covers the master after that too — a master the player spoke to yesterday is still
busy today. When both flag the same sentences, the lighter-ordered one is dropped by
`checks.run`, so one sentence is repaired once.
"""
from __future__ import annotations

from gm.narration import Finding

ORDER = 67
KINDS = frozenset({"master-approaches"})
DOORS = frozenset({"turn"})


def find(ctx) -> list:
    from rules import audience, keepers, places

    scene = ctx.scene
    master = keepers.master_here(scene)
    if master is None:
        return []
    location = ctx.location if ctx.location is not None else getattr(scene, "location_id", "")
    if not places.has_a_master(places.scale_of(location)):
        return []
    lines = [str(r.get("line") or "") for r in ctx.said or ()
             if str(r.get("who") or "") == master.ref and str(r.get("to") or "") == "you"
             and str(r.get("line") or "").strip()]
    if not lines:
        return []
    if audience.addressed(scene, master, ctx.player_text, ctx.reading):
        return []
    pc = scene.pc()
    if pc is not None and audience.grounds(scene, master, pc, ctx.player_text, ctx.reading):
        return []
    return [Finding(
        "master-approaches",
        f"{master.name} ({master.ref}), the master of the market, speaks to the player "
        f"unprompted: {lines[0][:120]!r}",
        f"{master.name} runs the market and is busy with it; they do not seek the player "
        f"out or speak to them first. Trade happens at the counters.",
        weight=2, sentences=tuple(lines))]
