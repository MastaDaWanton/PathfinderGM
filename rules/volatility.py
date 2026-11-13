"""How dangerous a place's ground is: 0 calm, 1 settled, 2 uneasy, 3 dangerous, 4 lawless.

Owner, 2026-11-13: World Bible should set a volatility/danger rating on places, and it
should move the chance of meeting monsters, bandits and catastrophe (a storm that wrecks a
ship among them). Asked of World Bible in docs/for-world-bible.md; until an export carries
it, every place falls back to a default by its ground, so worlds without the field play as
before (the owner's standing rule: fixes are world-agnostic).

Read in this order, the first that says: the place's own `play.places[]` row, the entity
the place id is filed under, then that entity's ancestors (a city inherits its nation's,
a nation its continent's). This module only answers the rating; what a rating DOES to a
chance is each table's own business, through `factor`.
"""
from __future__ import annotations

from . import places as places_mod

LEVELS = ("calm", "settled", "uneasy", "dangerous", "lawless")
# shortcut: a flat default by ground (a town settled, everything else uneasy), until an
# export says better; tune with the encounter lane's research.
SETTLED_DEFAULT, WILD_DEFAULT = 1, 2
# shortcut: the multiplier on a table's base chance, uneasy = the published rate. Tune
# with the encounter lane's research.
FACTORS = (0.5, 0.75, 1.0, 1.5, 2.0)


def _clamp(value) -> int | None:
    try:
        return max(0, min(len(LEVELS) - 1, int(value)))
    except (TypeError, ValueError):
        return None


def default_for(place_id: str) -> int:
    """The rating a place's ground gives when nothing in the world says one."""
    return SETTLED_DEFAULT if places_mod.terrain_of(place_id) == places_mod.URBAN \
        else WILD_DEFAULT


def of(world, place_id: str) -> int:
    """The place's rating, 0..4. `world` may be None (a Scene holds no world): then only
    the ground's default answers."""
    place_id = str(place_id or "")
    if world is not None:
        entity_id = places_mod.location_of(place_id)
        entity = world.get(entity_id) if entity_id else None
        if entity is not None:
            for row in getattr(entity, "places", None) or ():
                if isinstance(row, dict) and row.get("id") == place_id:
                    own = _clamp(row.get("volatility"))
                    if own is not None:
                        return own
            for e in [entity, *world.ancestors(entity.id)]:
                if getattr(e, "volatility", None) is not None:
                    return int(e.volatility)
    return default_for(place_id)


def factor(level: int) -> float:
    """How much a rating multiplies a table's base chance (uneasy = 1.0)."""
    level = _clamp(level)
    return FACTORS[WILD_DEFAULT if level is None else level]


def word(level: int) -> str:
    level = _clamp(level)
    return LEVELS[WILD_DEFAULT if level is None else level]
