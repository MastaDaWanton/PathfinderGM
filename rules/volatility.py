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
# export says better (World Bible ask 16).
SETTLED_DEFAULT, WILD_DEFAULT = 1, 2
# The multiplier on a table's base chance, researched 2026-11-13 (docs/encounter-budget.md,
# "Danger and how often"): B/X's wilderness check runs 1-in-6 settled, 2-in-6 wild, 3-in-6
# in the worst ground, so settled is half and dangerous one and a half times the wild rate;
# Kingmaker's claimed hex is 5% a day against the wild's 15%, a third, for calm. Lawless
# (2.0) is B/X's own 1-in-6 step continued once more (4-in-6): no published table goes
# past 3-in-6, so it is the one number here that is extrapolated, not read.
FACTORS = (1 / 3, 0.5, 1.0, 1.5, 2.0)


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
    own = stated(world, place_id)
    return default_for(str(place_id or "")) if own is None else own


def stated(world, place_id: str) -> int | None:
    """The rating the world itself gives the place (its row, its entity, an ancestor's),
    or None when nothing says one and only the ground's default would answer."""
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
                    return _clamp(e.volatility)
    return None


def factor(level: int) -> float:
    """How much a rating multiplies a table's base chance (uneasy = 1.0)."""
    level = _clamp(level)
    return FACTORS[WILD_DEFAULT if level is None else level]


def scale(world, *place_ids: str, base: int = WILD_DEFAULT) -> float:
    """What a table whose base chance was set for ground rated `base` multiplies it by
    here: the worst rating the world STATES for any of `place_ids` (a road is as bad as
    its worse end), against `base`. Nothing stated is 1.0 exactly, so a world without the
    field rolls today's published rates, the street's included (its 8% was measured in
    towns, `base=SETTLED_DEFAULT`)."""
    rated = [r for r in (stated(world, p) for p in place_ids if p) if r is not None]
    if not rated:
        return 1.0
    return factor(max(rated)) / factor(base)


def word(level: int) -> str:
    level = _clamp(level)
    return LEVELS[WILD_DEFAULT if level is None else level]
