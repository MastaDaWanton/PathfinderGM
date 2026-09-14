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
    # How this place is shaped upward. The default is `ledge` on purpose: a room with
    # something to stand on and shoot from is a more interesting fight than a floor, and
    # most real places have one — a gallery, a landing, a wall-walk, a stack of crates.
    # Places where height would be silly say so, and `none` is the exception that has to
    # be written down.
    #
    #   ledge    a raised band along one side, with a rail at its lip to shoot over
    #   slope    ground that climbs across the map
    #   scatter  isolated raised things, no rail — crates, rubble, a cart
    #   none     flat, and meant to be
    vertical: str = "ledge"
    about: str = ""


# Two squares of headroom is a house: ten feet, enough for a Medium creature to stand with
# a little air, and no room at all for anything to fly over anybody's head. Four is a hall.
LOW, HALL = 2, 4

# The spots this app generates, by their own slugs. A closed list, and short, because the
# tables it mirrors are closed and short.
BY_SPOT: dict[str, Shape] = {
    "the-market": Shape(16, 16, None, clumps=7, clump_max=2, rise=2,
                        vertical="scatter", about="stalls and awnings, and a cart to climb on"),
    "the-tavern": Shape(12, 10, LOW, clumps=6, clump_max=2,
                        about="tables, benches and a hearth"),
    "the-temple": Shape(14, 12, HALL, clumps=6, clump_max=1, rise=3, rise_to=1,
                        about="a colonnade, and a dais at the end of it"),
    "the-gate": Shape(14, 10, None, clumps=4, clump_max=3, rise=4, rise_to=2,
                      about="the gatehouse either side, and the wall-walk over it"),
    "the-back-streets": Shape(10, 16, None, clumps=8, clump_max=3, rough=6,
                              vertical="none", about="walls close on both sides, and what is left in them"),
    "the-workshops": Shape(12, 12, LOW, clumps=7, clump_max=2,
                           about="benches, a forge and the work stacked around them"),
    "the-guildhall": Shape(14, 12, HALL, clumps=4, clump_max=1, rise=2,
                           about="a long room with a table down it"),
    "the-high-ground": Shape(16, 16, None, clumps=3, clump_max=2, rise=14, rise_to=3,
                             vertical="slope", about="ground that climbs, and something to stand behind"),
    "the-approach": Shape(18, 14, None, clumps=3, clump_max=2,
                          vertical="slope", about="the way in, and little to hide behind"),
    "the-heart-of-it": Shape(14, 14, None, clumps=9, clump_max=2, rough=8,
                             vertical="scatter", about="close, and hard going"),
    "the-edge": Shape(18, 16, None, clumps=4, clump_max=2, rough=4,
                      vertical="none", about="where it thins out"),
    # Underground, and every one of them lower than a house.
    "the-sump": Shape(10, 10, LOW, clumps=3, clump_max=2, rough=10,
                      vertical="none", about="as low as it goes, and wet"),
    "the-vaults": Shape(12, 10, LOW, clumps=5, clump_max=1,
                        vertical="scatter", about="pillars, and what is kept between them"),
    "the-deep-chamber": Shape(14, 12, HALL, clumps=5, clump_max=2, rough=4,
                              about="it opens out down here"),
    "the-gallery": Shape(16, 8, LOW, clumps=4, clump_max=2, rough=6,
                         about="a long cut, propped where it needed it"),
    # The places a world implies — `places.IMPLIED` mints these when a settlement's own
    # words ask for them, and most of them are vertical by their nature. A library has
    # galleries because that is where the upper shelves are; a keep has a wall-walk
    # because that is what a keep is.
    "the-library": Shape(16, 14, HALL, clumps=10, clump_max=3,
                         about="stacks to the ceiling, and a gallery round them"),
    "the-keep": Shape(16, 14, HALL, clumps=5, clump_max=2,
                      about="a hall, and the walk above it"),
    "the-docks": Shape(18, 14, None, clumps=6, clump_max=3, rough=6,
                       about="a quay above the water, and what is stacked on it"),
    "the-bridge": Shape(20, 8, None, clumps=2, clump_max=2,
                        about="a span, and a long drop either side"),
    "the-mine-head": Shape(14, 12, None, clumps=6, clump_max=2, rough=6,
                           about="the headframe, and the spoil heaped under it"),
    "the-shrine": Shape(12, 10, HALL, clumps=4, clump_max=1,
                        about="a quiet room with a step up to the altar"),
    "the-well": Shape(12, 12, None, clumps=3, clump_max=2, vertical="scatter",
                      about="a wellhead, and the ground worn round it"),
    "the-workshop-loft": Shape(10, 10, LOW, clumps=5, clump_max=2,
                               about="a loft over the work"),
}

# Everything else, by the ground it stands on.
BY_TERRAIN: dict[str, Shape] = {
    "urban": Shape(16, 14, None, clumps=6, clump_max=2,
                   about="walls, and the things people leave against them"),
    "forest": Shape(18, 18, None, clumps=12, clump_max=2, rough=10,
                    vertical="scatter", about="trunks, and undergrowth between them"),
    "jungle": Shape(16, 16, None, clumps=14, clump_max=2, rough=18,
                    vertical="scatter", about="it is hard to move and harder to see"),
    "swamp": Shape(18, 18, None, clumps=4, clump_max=2, rough=22,
                   vertical="scatter", about="standing water and the roots under it"),
    "hills": Shape(18, 18, None, clumps=4, clump_max=2, rise=16, rise_to=2,
                   vertical="slope", about="ground that rises and falls"),
    "mountain": Shape(16, 16, None, clumps=9, clump_max=3, rough=8, rise=14, rise_to=3,
                      vertical="slope", about="rock, and a way up it"),
    "ruins": Shape(16, 16, None, clumps=10, clump_max=3, rough=12, rise=4, rise_to=1,
                   about="broken walls, and rubble where they fell"),
    "underground": Shape(14, 12, LOW, clumps=6, clump_max=2, rough=6,
                         vertical="scatter", about="close stone, and not much air"),
    "farmland": Shape(20, 18, None, clumps=3, clump_max=2, rough=4,
                      vertical="none", about="open, with a wall or a hedge to it"),
    "grassland": Shape(20, 20, None, clumps=1, clump_max=2,
                       vertical="none", about="open ground"),
    "desert": Shape(20, 20, None, clumps=2, clump_max=2, rough=8, rise=6, rise_to=1,
                    vertical="slope", about="sand that moves under you"),
    "tundra": Shape(20, 20, None, clumps=2, clump_max=2, rough=8,
                    vertical="none", about="open, and hard going"),
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

    _raise(grid, shape, r)
    return grid


# How high a ledge stands and how high its rail comes. Two squares is ten feet — a storey
# — so a gallery is a floor above a floor, and the rail tops out level with the walkway,
# which is what lets somebody on it shoot over and somebody under it shoot back.
LEDGE_AT = 2


def _raise(grid: Grid, shape: Shape, r: "_Rolls") -> None:
    """Put the height into a plan, in the shape that place is meant to have."""
    kind = shape.vertical
    inner_w, inner_h = max(1, shape.width - 2), max(1, shape.height - 2)

    if kind == "none":
        return

    if kind == "ledge":
        # A band along one side, with its rail on the inside edge. The side is chosen
        # from the seed, so a given room has its gallery in the same place for ever.
        side = r.next(4)
        depth = 2 if min(shape.width, shape.height) >= 10 else 1
        for step in range(depth):
            for along in range(1, (shape.width if side < 2 else shape.height) - 1):
                if side == 0:
                    walk, lip = (along, 1 + step), (along, 1 + depth)
                elif side == 1:
                    walk, lip = (along, shape.height - 2 - step), (along, shape.height - 2 - depth)
                elif side == 2:
                    walk, lip = (1 + step, along), (1 + depth, along)
                else:
                    walk, lip = (shape.width - 2 - step, along), (shape.width - 2 - depth, along)
                if not grid.inside(walk) or not grid.inside(lip):
                    continue
                grid.blocked.discard(walk)
                grid.floor[walk] = LEDGE_AT
                if step == depth - 1 and grid.inside(lip) and lip not in grid.floor:
                    grid.parapet[lip] = LEDGE_AT
        return

    if kind == "slope":
        # Ground that climbs one way across the map, in bands, so a fight on it has an
        # uphill side and a downhill one rather than a scatter of steps.
        steps = max(1, shape.rise_to)
        across = shape.width if r.next(2) else shape.height
        band = max(1, across // (steps + 1))
        for x in range(1, shape.width - 1):
            for y in range(1, shape.height - 1):
                along = x if across == shape.width else y
                height = min(steps, along // band)
                if height:
                    grid.floor[(x, y)] = height
        return

    for _ in range(max(shape.rise, 3)):
        p = (1 + r.next(inner_w), 1 + r.next(inner_h))
        if p not in grid.blocked:
            grid.floor[p] = 1 + r.next(shape.rise_to)


def describe(place_id: str, terrain: str = "") -> str:
    """One phrase about the ground, for a tell. Never a number — the third law."""
    return shape_for(place_id, terrain).about
