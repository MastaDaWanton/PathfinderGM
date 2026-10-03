"""PLACES THE PLAYER HAS HEARD OF: named by somebody, not on the map yet, not been to.

The brief's side of `rules/heard_places.py`. Without it the planner sees only the places
the settlement already has, and a player who says "I go to the smithy" after the clerk
named it is planning against a list the smithy is not on — the refused travel and the
founded-wherever retry the owner's items save recorded (docs/playtest-2026-10-03.md).
With it, the model knows the place is real in the story, where the speaker put it, and
that going there makes it a place (the engine does the making: `go_to_heard_place`).

Words, not ids: the landmark is said by its name, the speaker by theirs.
"""
from __future__ import annotations

ORDER = 35
SLOT = "place"
SCAFFOLD = (
    "PLACES THE PLAYER HAS HEARD OF (not been to yet):",
    "Going to one makes it a place; it is where the speaker said.",
)

# How many the brief lists: the newest first, few enough to read.
SHOWN = 4


def section(ctx) -> tuple[str, dict]:
    from rules import heard_places
    from rules import places as places_mod

    scene = ctx.scene
    if scene is None or not getattr(scene, "heard_places", None):
        return "", {}
    heard = heard_places.of_here(scene, ctx.known)
    if not heard:
        return "", {}
    people = getattr(scene, "people", None) or getattr(scene, "actors", {}) or {}
    rows, facts = [], []
    for h in list(reversed(heard))[:SHOWN]:
        spot = places_mod.find(ctx.known, h.get("landmark") or "") if h.get("landmark") \
            else None
        where = f" — off {spot.name}" if spot is not None else ""
        who = people.get(str(h.get("from") or ""))
        told = f", as {who.name} told it" if who is not None else ""
        rows.append(f"{h['name']}{where}{told}")
        facts.append({"name": h["name"], "landmark": h.get("landmark", ""),
                      "from": h.get("from", "")})
    text = ("\nPLACES THE PLAYER HAS HEARD OF (not been to yet): " + "; ".join(rows)
            + ". Going to one makes it a place; it is where the speaker said.")
    return text, {"heard_places": facts}
