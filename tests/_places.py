"""Stand a test scene on named ground, the way a test used to write `scene.biome`.

`scene.biome` is a parse of the party's place now and has no setter: twenty-six test
sites assigned it, and every one of them meant "put the party on this ground". This is
that, said once. `urban` is the location's own settlement; anything else is that
region's first place. Everyone in the store moves, for the reason the review gave about
`new_campaign`: a helper that moved only the PC left the opening companion standing
nowhere, out of view on turn one.
"""
from __future__ import annotations

from rules import places


def stand_on(scene, biome: str) -> str:
    """Move the whole party onto `biome` and return the place id they stand at."""
    ground = str(biome or "").strip().lower()
    loc = getattr(scene, "location_id", None) or ""
    if not ground:
        target = ""
    elif ground == places.URBAN:
        target = places.home_set(loc, places.URBAN)[0].id
    else:
        target = places.region_set(loc, ground)[0].id
    scene.at = target
    for actor in scene.people.values():
        actor.at = target
    return target
