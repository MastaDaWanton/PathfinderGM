"""The shape of the ground a fight happens on.

Every fight in this game has been fought on the same empty field. `_lay_battlefield` laid a
bare `Grid()` — twenty squares by twenty of open floor — and `end_encounter` threw it away
again, so a brawl in a cellar had the same geometry as one in a meadow, and the only walls
that ever existed were conjured by `wall of stone`. The place graph knew the party was in
the cellar; the grid the fight ran on had never heard of it.

So a place gets a shape, and it is **derived, not stored**. `places._seed` is a SHA-256 of
the place id, chosen so that "the same town would not lay itself out differently after a
restart"; the same trick one level down gives the same room the same pillars in every
session, on every machine, for ever, without a byte in the save. That is the arrangement
the spot list has always used, and it is why this can be a pure function.

**A place is one room, not a building.** The house is the place graph — `places.mint` has
always made a cellar a child place of the house above it, and `places.storeys` puts floors
over it the same way — so nothing here generates corridors or a building's plan. It answers
one question: what is underfoot, and what is in the way, where the party is standing. A
storey is read as a floor OF the building it belongs to, which is how an upstairs room keeps
the roof it obviously has.

What a plan may contain is deliberately small, and every part of it is something the engine
already knows how to read:

    blocked     walls, pillars, stalls      refuses movement, blocks sight, gives cover
    difficult   rubble, undergrowth, mud    doubles the cost of entering
    floor       a dais, a wall-walk, a cart raised ground, and so higher ground
    ceiling     how much air is above       a flier's limit indoors

Nothing else. No doors, no furniture that is only scenery, no authored encounters — a
feature the engine cannot act on is decoration, and decoration belongs in the prose the
narrator writes, not in a data structure that has to be saved, drawn and reasoned about.

Keyed off the **spot** where the spot is one this app generates, and off the terrain
otherwise. Both vocabularies are closed and small (`places._SETTLEMENT`, `places._WILD`,
`places.VENTURES`, `biomes.BIOMES`), and anything unrecognised — a place World Bible
authors, a place the fiction founded — falls through to its terrain and then to open
ground. Falling through is the right failure: an unknown room is a clearing until somebody
says otherwise, and a clearing is what every fight already got.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .grid import Grid, Point

# The separator `rules/places.py` puts a storey behind. Imported as a constant
# rather than importing the module, because `places` asks `floorplan` whether a
# place is indoors and the two would import each other.
STOREY = "^"


@dataclass(frozen=True)
class Shape:
    """What one kind of place looks like underfoot.

    `clumps` are how many knots of solid stuff to scatter — a market's stalls, a temple's
    pillars, a wood's trees — and `clump_max` how many squares each may run to. `rough` is
    a count of difficult squares, `rise` a count of raised ones and how high they go.
    """
    width: int = 20
    height: int = 20
    ceiling: int | None = None
    clumps: int = 0
    clump_max: int = 1
    rough: int = 0
    rise: int = 0
    rise_to: int = 1
    about: str = ""


# Two squares of headroom is a house: ten feet, enough for a Medium creature to stand with
# a little air, and no room at all for anything to fly over anybody's head. Four is a hall.
LOW, HALL = 2, 4

# The spots this app generates, by their own slugs. A closed list, and short, because the
# tables it mirrors are closed and short.
BY_SPOT: dict[str, Shape] = {
    "the-market": Shape(16, 16, None, clumps=7, clump_max=2, rise=2,
                        about="stalls and awnings, and a cart to climb on"),
    "the-tavern": Shape(12, 10, LOW, clumps=6, clump_max=2,
                        about="tables, benches and a hearth"),
    "the-temple": Shape(14, 12, HALL, clumps=6, clump_max=1, rise=3, rise_to=1,
                        about="a colonnade, and a dais at the end of it"),
    "the-gate": Shape(14, 10, None, clumps=4, clump_max=3, rise=4, rise_to=2,
                      about="the gatehouse either side, and the wall-walk over it"),
    "the-back-streets": Shape(10, 16, None, clumps=8, clump_max=3, rough=6,
                              about="walls close on both sides, and what is left in them"),
    "the-workshops": Shape(12, 12, LOW, clumps=7, clump_max=2,
                           about="benches, a forge and the work stacked around them"),
    "the-guildhall": Shape(14, 12, HALL, clumps=4, clump_max=1, rise=2,
                           about="a long room with a table down it"),
    "the-high-ground": Shape(16, 16, None, clumps=3, clump_max=2, rise=14, rise_to=3,
                             about="ground that climbs, and something to stand behind"),
    "the-approach": Shape(18, 14, None, clumps=3, clump_max=2,
                          about="the way in, and little to hide behind"),
    "the-heart-of-it": Shape(14, 14, None, clumps=9, clump_max=2, rough=8,
                             about="close, and hard going"),
    "the-edge": Shape(18, 16, None, clumps=4, clump_max=2, rough=4,
                      about="where it thins out"),
    # Underground, and every one of them lower than a house.
    "the-sump": Shape(10, 10, LOW, clumps=3, clump_max=2, rough=10,
                      about="as low as it goes, and wet"),
    "the-vaults": Shape(12, 10, LOW, clumps=5, clump_max=1,
                        about="pillars, and what is kept between them"),
    "the-deep-chamber": Shape(14, 12, HALL, clumps=5, clump_max=2, rough=4,
                              about="it opens out down here"),
    "the-gallery": Shape(16, 8, LOW, clumps=4, clump_max=2, rough=6,
                         about="a long cut, propped where it needed it"),
}

# Everything else, by the ground it stands on.
BY_TERRAIN: dict[str, Shape] = {
    "urban": Shape(16, 14, None, clumps=6, clump_max=2,
                   about="walls, and the things people leave against them"),
    "forest": Shape(18, 18, None, clumps=12, clump_max=2, rough=10,
                    about="trunks, and undergrowth between them"),
    "jungle": Shape(16, 16, None, clumps=14, clump_max=2, rough=18,
                    about="it is hard to move and harder to see"),
    "swamp": Shape(18, 18, None, clumps=4, clump_max=2, rough=22,
                   about="standing water and the roots under it"),
    "hills": Shape(18, 18, None, clumps=4, clump_max=2, rise=16, rise_to=2,
                   about="ground that rises and falls"),
    "mountain": Shape(16, 16, None, clumps=9, clump_max=3, rough=8, rise=14, rise_to=3,
                      about="rock, and a way up it"),
    "ruins": Shape(16, 16, None, clumps=10, clump_max=3, rough=12, rise=4, rise_to=1,
                   about="broken walls, and rubble where they fell"),
    "underground": Shape(14, 12, LOW, clumps=6, clump_max=2, rough=6,
                         about="close stone, and not much air"),
    "farmland": Shape(20, 18, None, clumps=3, clump_max=2, rough=4,
                      about="open, with a wall or a hedge to it"),
    "grassland": Shape(20, 20, None, clumps=1, clump_max=2,
                       about="open ground"),
    "desert": Shape(20, 20, None, clumps=2, clump_max=2, rough=8, rise=6, rise_to=1,
                    about="sand that moves under you"),
    "tundra": Shape(20, 20, None, clumps=2, clump_max=2, rough=8,
                    about="open, and hard going"),
    "coast": Shape(18, 16, None, clumps=5, clump_max=2, rough=8, rise=4, rise_to=1,
                   about="rocks, and the tide line"),
}

OPEN = Shape(about="open ground")


def _seed(place_id: str) -> int:
    """The same durable number `places._seed` takes, and for the same reason: `hash()` is
    salted per process, so a town would lay itself out differently after every restart."""
    return int(hashlib.sha256(
        str(place_id or "nowhere").encode()).hexdigest()[:8], 16)


class _Rolls:
    """A tiny deterministic sequence off the seed.

    Not `random.Random`: the campaign's dice are the engine's, this is not a roll anybody
    makes, and importing a PRNG here would put a second source of randomness in a codebase
    whose whole design is that the engine owns the dice. A multiply-and-take is enough to
    scatter stalls and cannot be mistaken for a die.
    """

    def __init__(self, seed: int):
        self.n = seed or 1

    def next(self, upper: int) -> int:
        self.n = (self.n * 1103515245 + 12345) & 0x7FFFFFFF
        # The HIGH bits, and this is not a style choice. An LCG's low bits cycle with a
        # tiny period — measured here: `n % 8` off this multiplier runs
        # 6,7,4,5,2,3,0,1 and then repeats those eight for ever. The first version took
        # the low bits, and the result was that a sump asking for ten squares of standing
        # water got two, because every draw landed on the same handful of columns. A
        # plan that looks scattered and is really a stripe is the kind of wrong that
        # never announces itself.
        return (self.n >> 16) % max(1, upper)


def shape_for(place_id: str, terrain: str = "") -> Shape:
    """Which shape this place takes: its own spot first, then its ground, then open.

    A storey is read as the building it is a floor of. Without that, `the-tavern^1` matches
    no spot, falls through to `urban`, and an upstairs room comes out **with no roof on it**
    — which would let a flier leave through a bedroom ceiling and is the sort of wrong that
    only shows up when somebody tries it.
    """
    bare = str(place_id or "").rsplit(STOREY, 1)[0]
    spot = bare.rsplit(":", 1)[-1].rsplit("/", 1)[-1].strip().lower()
    found = BY_SPOT.get(spot) or BY_TERRAIN.get(
        str(terrain or "").strip().lower(), OPEN)
    level = _storey(place_id)
    if not level or found.ceiling is None:
        return found
    return _upstairs(found, level)


def _storey(place_id: str) -> int:
    tail = str(place_id or "").rsplit(STOREY, 1)
    if len(tail) < 2:
        return 0
    try:
        return int(tail[1])
    except ValueError:
        return 0


def _upstairs(ground: Shape, level: int) -> Shape:
    """A floor of the same building: the same footprint, divided up more.

    Upper rooms are smaller and more partitioned than the hall you walk into, and an
    undercroft is smaller still and worse going. Derived from the ground floor's own shape
    rather than authored per building, so a change to the tavern reaches its bedrooms.
    """
    if level < 0:
        return Shape(max(6, ground.width - 4), max(6, ground.height - 4), LOW,
                     clumps=ground.clumps, clump_max=2,
                     rough=max(4, ground.rough + 4),
                     about="low, and stacked with what nobody wants upstairs")
    if level >= 2:
        return Shape(max(6, ground.width - 4), max(6, ground.height - 4), LOW,
                     clumps=ground.clumps + 1, clump_max=2, rough=ground.rough,
                     about="under the beams, and low enough to mind your head")
    return Shape(max(6, ground.width - 2), max(6, ground.height - 2), LOW,
                 clumps=ground.clumps + 3, clump_max=2, rough=ground.rough,
                 about="partitioned, and lower than the room below")


def for_place(place_id: str, terrain: str = "") -> Grid:
    """The ground at this place, the same every time it is asked for.

    Nothing is placed in the outermost ring, so a plan can never wall a scene in or strand
    a combatant in a corner they cannot leave. Everything in the middle is fair game.
    """
    shape = shape_for(place_id, terrain)
    r = _Rolls(_seed(place_id))
    grid = Grid(width=shape.width, height=shape.height, ceiling=shape.ceiling)

    def somewhere() -> Point:
        return (1 + r.next(max(1, shape.width - 2)),
                1 + r.next(max(1, shape.height - 2)))

    for _ in range(shape.clumps):
        x, y = somewhere()
        run = 1 + r.next(shape.clump_max)
        down = r.next(2)
        for step in range(run):
            p = (x + step, y) if not down else (x, y + step)
            if 0 < p[0] < shape.width - 1 and 0 < p[1] < shape.height - 1:
                grid.blocked.add(p)

    for _ in range(shape.rough):
        p = somewhere()
        if p not in grid.blocked:
            grid.difficult.add(p)

    for _ in range(shape.rise):
        p = somewhere()
        if p not in grid.blocked:
            grid.floor[p] = 1 + r.next(shape.rise_to)

    return grid


def describe(place_id: str, terrain: str = "") -> str:
    """One phrase about the ground, for a tell. Never a number — the third law."""
    return shape_for(place_id, terrain).about
