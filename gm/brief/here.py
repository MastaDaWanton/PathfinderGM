"""HERE, THE PLACES HERE, NEXT DOOR and UNDERFOOT: which settlement, which part of it.

Moved out of `prompts.scene_brief` unchanged (fix pass S2, docs/fix-interfaces.md §2.2),
so Lane B could change it without editing a file it does not own. Lane B's changes
(2026-09-28): the HERE line says outside, under or on the road when the party is (20.1),
and THE PLACES HERE is split IN / OUTSIDE when the settlement has ground outside (17.1).
A scene with no ring — no world to build one from — reads exactly as it did.
"""
from __future__ import annotations

ORDER = 10
SLOT = "place"
SCAFFOLD = (
    "HERE:",
    "The party is at",
    "Not anywhere else in",
    "and not anywhere else;",
    "they are there now.",
    "THE PLACES HERE (the only ones that exist):",
    "To move between them use",
    "Anything else is refused, and so is a SECOND travel in the same plan — one "
    "journey a turn.",
    "NEXT DOOR to",
    "and reached in one step:",
    "Everywhere else here is further off and is reached by walking through these — "
    "name the DESTINATION in the travel and the engine walks the way, through every "
    "place between, in one turn. Never plan the route yourself.",
    "UNDERFOOT at",
    "(what is physically here, and what the map is drawn from):",
)
# Printed only when the party stands outside the settlement (Lane B, 20.1).
SOMETIMES = ("and not anywhere else;",)


def section(ctx) -> tuple[str, dict]:
    location = ctx.location
    if not location:
        return "", {}
    # The scale AND what it means. "a village" was all this said, and a model shown
    # a bare word writes whatever size of place it happens to imagine — which is how
    # a settlement of a few hundred acquires crowds to be lost in. `places.what_it_is`
    # is the one composer; the opening and the panel print the same sentence.
    from rules import places as _places_for_scale

    scale = _places_for_scale.what_it_is(_places_for_scale.scale_of(location)) or 'a place'
    # Outside reads as outside (Lane B, item 20.1): Bobby stood in a forest past the way
    # in and the brief said "HERE: Vormoor, a village…" — the same line it gave the
    # market — because the ground outside is filed under the settlement's own id. The
    # setting is parsed off the place id (`places.setting_of`), never stored.
    from rules import geography as _geography

    where = _geography.where(ctx.world, ctx.scene, ctx.here) if ctx.scene is not None \
        else None
    setting = where.setting if where is not None else "in"
    if setting == "road":
        lines = [f"\nHERE: {where.label}, {where.detail}; {location.name} is {scale}."]
    elif setting in ("outside", "under"):
        lines = [f"\nHERE: {setting} {location.name}, {scale}."]
    else:
        lines = [f"\nHERE: {location.name}, {scale}."]
    facts: dict = {"settlement": location.name, "scale": scale, "setting": setting}
    # Which part of it, and what leads out — stated the same way the cast is, because
    # it is the same rule. "WHO IS HERE (these refs are the only ones that exist)"
    # has grounded people since it was written; this file's own docstring has asked
    # for the same courtesy for PLACES since it was written too ("a model invents
    # places and people, then treats them as settled fact") and never got it. Without
    # it the model reconstructs the room from earlier beats, and put a player back
    # inside a building they had walked out of two turns before.
    # `here` and `known` are handed down by the caller that has an engine, never derived
    # in the brief (`scene_brief` resolves the engine-less fallback once, before any slot
    # runs, with the same one function the engine calls).
    here, known = ctx.here, ctx.known
    if here is not None and len(known) > 1:
        from rules import places as _places

        others = [p.name for p in known if p.id != here.id]
        if setting == "in":
            lines.append(f"  The party is at {here.name}. Not anywhere else in "
                         f"{location.name}; they are there now.")
        else:
            lines.append(f"  The party is at {here.name}, {setting if setting != 'road' else 'outside'} "
                         f"{location.name}, and not anywhere else; they are there now.")
        # IN and OUTSIDE the settlement as two lists when it has ground outside (the
        # ring, `rules/outskirts.py`), so each stays short and the model can see which
        # side of the edge a name is on. Without a ring the line is today's.
        outside = [p.name for p in known if _places.setting_of(p.id) == "outside"]
        inside = [p.name for p in known if _places.setting_of(p.id) != "outside"]
        if outside and inside:
            listed = (f"IN {location.name.upper()}: {', '.join(inside)}; "
                      f"OUTSIDE {location.name.upper()}: {', '.join(outside)}")
            facts["outside"] = outside
        else:
            listed = ", ".join(p.name for p in known)
        lines.append(f"  THE PLACES HERE (the only ones that exist): "
                     f"{listed}. To move between them use "
                     f'{{"op": "travel", "params": {{"place": "{others[0]}"}}}}. '
                     f"Anything else is refused, and so is a SECOND travel in the "
                     f"same plan — one journey a turn.")
        facts["here"] = here.id
        facts["here_name"] = here.name
        facts["places"] = [p.name for p in known]
        # What is NEXT DOOR, which is a different question from what exists, and
        # became answerable on 2026-09-22 when `places.route` started walking the
        # exits graph. The engine finds the way itself now, so the plan must name
        # the destination and never the route — said here because the block above
        # reads as a flat list of equally-near rooms, which is what produced plans
        # of five travels in the first place (item 35).
        near = [p.name for p in known if p.id in (here.exits or ())]
        if near:
            lines.append(
                f"  NEXT DOOR to {here.name}, and reached in one step: "
                f"{', '.join(near)}. Everywhere else here is further off and is "
                f"reached by walking through these — name the DESTINATION in the "
                f"travel and the engine walks the way, through every place between, "
                f"in one turn. Never plan the route yourself.")
            facts["next_door"] = near
        # And what this ground looks like underfoot. The shape is what the tactical
        # map is drawn from, so a narrator describing the market's stalls and the
        # cart is describing the same market the player can climb on — which is the
        # positional half of the 2026-09-22 request ("describes positionally where i
        # am in the market what's around me").
        from rules import floorplan as _floorplan

        underfoot = _floorplan.describe(here.id, here.terrain, here.shape)
        if underfoot:
            lines.append(f"  UNDERFOOT at {here.name} (what is physically here, and "
                         f"what the map is drawn from): {underfoot}.")
            facts["underfoot"] = underfoot
    return "\n".join(lines), facts
