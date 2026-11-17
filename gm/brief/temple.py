"""THE TEMPLE'S CASTINGS: what its keeper casts for pay, when the party stands in it.

Playtest 2026-11-16 #70 (T289): asked "Can you heal me? I can pay.", the cathedral's priest
answered "I am not a doctor, nor do I possess the arts of healing", and the table talk
backed it with a world fact nobody wrote ("Mirabalos doesn't have any healers in this
order"). The engine now sells a temple's castings (rules/services.py, bought at the counter
through `Engine._buy_spell`); a narrator who is not told so invents the refusal again, so
the fact is in the brief, with where the coin moves.
"""
from __future__ import annotations

ORDER = 46
SLOT = "people"
SCAFFOLD = (
    "THE TEMPLE'S CASTINGS (fact):",
    "casts these for pay:",
    "The player pays at the counter (the Trade panel); nothing is cast and no coin "
    "changes hands in the prose.",
)


def section(ctx) -> tuple[str, dict]:
    from rules import keepers, places, pricing, services

    scene = ctx.scene
    at = str(getattr(scene, "at", "") or "")
    keeper = keepers.keeper_in(scene, at) if at else None
    if keeper is None or getattr(keeper, "is_down", False) \
            or not services.keeps_a_temple(keeper):
        return "", {}
    scale = places.scale_of(ctx.location) if ctx.location is not None else "town"
    rows = services.menu(scale)
    if not rows:
        return "", {}
    said = "; ".join(f"{r['spell_name']} ({pricing.as_text(r['gp'])})" for r in rows)
    text = (f"\n  {SCAFFOLD[0]} {keeper.name} {SCAFFOLD[1]} {said}. {SCAFFOLD[2]}")
    return text, {"temple_keeper": keeper.ref, "castings": [r["spell"] for r in rows]}
