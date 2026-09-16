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

    # --- the settlement vocabulary (2026-09-15) -------------------------------------
    # "cities and towns have businesses and entertainment and leisure/recreation and
    # religious establishments/cultural buildings...the list goes on and on". Thirty-eight
    # kinds of place now, and a place with no row here falls through to plain `urban` —
    # a sixteen-by-fourteen room with walls and clutter, which works and is the same room
    # every time. A tuned row is what makes a bathhouse read differently from a gaol when
    # a fight starts in one.
    #
    # Most are vertical, per the standing instruction, and the flat ones are flat because
    # a reader would agree they are: a lane between two walls, a midden, a green.

    # buying, selling, making
    "the-smithy": Shape(10, 10, LOW, clumps=5, clump_max=1, rise=2,
                        vertical="scatter", about="a hearth, an anvil, and what is stacked round them"),
    "the-mill": Shape(12, 12, HALL, clumps=5, clump_max=2, rise=3, rise_to=2,
                      about="the wheel, the sacks, and a floor above them"),
    "the-tannery": Shape(14, 12, LOW, clumps=7, clump_max=2, rough=10,
                         vertical="scatter", about="pits and frames, and nowhere clean to stand"),
    "the-brewery": Shape(14, 12, HALL, clumps=6, clump_max=2, rise=3, rise_to=2,
                         about="vats to climb between, and a gantry over them"),
    "the-warehouses": Shape(16, 14, HALL, clumps=10, clump_max=3,
                            about="stacked to the roof, with a walk round the top"),
    "the-counting-house": Shape(10, 10, LOW, clumps=4, clump_max=1,
                                about="a desk, a grille, and a stair to the strongroom"),
    "the-merchants-row": Shape(18, 8, None, clumps=6, clump_max=2, rise=2,
                               about="a long street with steps up to every door"),
    # who is in charge
    "the-guardhouse": Shape(12, 10, LOW, clumps=4, clump_max=2, rise=2,
                            about="a rack of arms, a stair to the wall, and always more of them inside"),
    "the-barracks": Shape(16, 14, HALL, clumps=6, clump_max=2, rise=3, rise_to=2,
                          about="a yard, a gallery of bunks over it, and a drill square"),
    "the-moot-hall": Shape(14, 12, HALL, clumps=4, clump_max=1, rise=2,
                           about="benches round a floor, and a gallery for everyone else"),
    "the-gaol": Shape(10, 10, LOW, clumps=6, clump_max=1,
                      vertical="none", about="cells, a passage between them, and one door"),
    "the-courthouse": Shape(14, 14, HALL, clumps=5, clump_max=1, rise=4, rise_to=2,
                            about="a bench above the floor, and a gallery above that"),
    "the-customs-house": Shape(12, 12, LOW, clumps=6, clump_max=2,
                               about="a counter, a scale, and everything waiting to be opened"),
    # faith, and the dead
    "the-graveyard": Shape(16, 14, None, clumps=9, clump_max=1, rough=6, rise=3,
                           vertical="scatter", about="stones, and the ground uneven between them"),
    "the-cathedral": Shape(20, 16, HALL, clumps=8, clump_max=2, rise=4, rise_to=2,
                           about="a nave, a triforium over it, and pillars the width of a cart"),
    # drinking, watching, resting
    "the-inn": Shape(12, 10, LOW, clumps=6, clump_max=2,
                     about="tables, a hearth, and the stair to the rooms"),
    "the-green": Shape(18, 16, None, clumps=2, clump_max=2,
                       vertical="none", about="open ground the whole place uses"),
    "the-bathhouse": Shape(14, 12, HALL, clumps=5, clump_max=2, rough=8,
                           about="wet stone, a colonnade, and a gallery to look down from"),
    "the-theatre": Shape(16, 16, HALL, clumps=4, clump_max=2, rise=8, rise_to=3,
                         vertical="slope", about="a stage, and the seats banked above it"),
    "the-arena": Shape(20, 18, None, clumps=2, clump_max=2, rough=6, rise=10, rise_to=3,
                       vertical="slope", about="sand, and the crowd banked all the way round"),
    "the-gardens": Shape(18, 16, None, clumps=7, clump_max=2, rough=4, rise=3,
                         vertical="scatter", about="walls, walks, and something to get behind"),
    # what a place needs to exist
    "the-granary": Shape(12, 12, HALL, clumps=6, clump_max=2, rise=3, rise_to=2,
                         about="bins to the roof, and a loading gallery"),
    "the-midden": Shape(12, 12, None, clumps=4, clump_max=2, rough=14,
                        vertical="none", about="where it all ends up, and the footing shows it"),
    "the-cistern": Shape(14, 12, LOW, clumps=5, clump_max=2, rough=10,
                         vertical="scatter", about="standing water, and the pillars holding the street up"),
    # getting somewhere else
    "the-stables": Shape(14, 10, LOW, clumps=6, clump_max=2, rough=4,
                         about="stalls, a tack room, and a hayloft over both"),
    "the-carters-yard": Shape(16, 14, None, clumps=7, clump_max=3, rough=4, rise=3,
                              vertical="scatter", about="carts, crates, and the gaps between them"),
    # where nobody is watching
    "the-lane": Shape(8, 16, None, clumps=6, clump_max=3, rough=4,
                      vertical="none", about="two walls, and whatever is left between them"),
    "the-warrens": Shape(14, 14, None, clumps=12, clump_max=3, rough=8, rise=3,
                         vertical="scatter", about="a street plan nobody drew, on three levels"),

    # the shape of a city: a square, and the crossings off it
    "the-great-square": Shape(20, 18, None, clumps=4, clump_max=2, rise=3,
                              about="the middle of it, with steps and a plinth to fight from"),
    "the-north-crossing": Shape(14, 14, None, clumps=5, clump_max=2, rise=2,
                                about="where four streets meet, and the balconies over them"),
    "the-east-crossing": Shape(14, 14, None, clumps=5, clump_max=2, rise=2,
                               about="where four streets meet, and the balconies over them"),
    "the-south-crossing": Shape(14, 14, None, clumps=5, clump_max=2, rise=2,
                                about="where four streets meet, and the balconies over them"),
    "the-west-crossing": Shape(14, 14, None, clumps=5, clump_max=2, rise=2,
                               about="where four streets meet, and the balconies over them"),
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
    # Water, and under it. Both are `none` — flat, and meant to be, which is the one
    # honest answer here: the whole surface of a lake is one height, and a ledge in open
    # water is a thing nobody can point at. The verticality of water is DEPTH, and depth
    # is the other place (`underwater`), reached by diving rather than by climbing.
    #
    # Nothing is blocked and nothing is difficult, for the same reason: water is not
    # rough going the way scree is — it is a different way of moving altogether, and it
    # is `rules/water.py` that says what that costs, creature by creature. A wave is not
    # a wall.
    # A ship. Small, crowded, and with a rail: the one piece of ground in the game where
    # the edge of the map is a real edge and going over it is a different set of rules.
    "deck": Shape(12, 20, None, clumps=4, clump_max=2, rough=0, rise=2,
                  vertical="ledge", about="planking, a mast to put between you and them, "
                                          "and a rail with the sea past it"),
    "water": Shape(20, 20, None, clumps=0, clump_max=1, rough=0,
                   vertical="none", about="open water, and nothing to stand on"),
    "underwater": Shape(20, 20, None, clumps=2, clump_max=2, rough=0,
                        vertical="none",
                        about="green light from above, and weed moving with you"),
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


# --- what the world said about the ground -------------------------------------------------
#
# World Bible has written four things about every place it ships since schema 1.3 —
# `size_ft`, `clutter`, `footing`, `vertical` — and for two releases nothing read one of
# them. Measured 2026-09-16 across both fixtures: 456 authored places, every one carrying
# all four, and every one of them fought on a shape this app made up out of the room's
# NAME. Ashwatch's market is written 75 by 70 feet and was laid out 16 by 16 squares; a
# place whose name the table does not know got the twenty-by-twenty blank field, which is
# what the whole of stages 1 to 7 existed to remove.
#
# The mapping below is the whole of the reader: arithmetic and a lookup. It lives HERE
# rather than in `rules/places.py` because feet, squares and levels are this module's
# units — `places` holds the id grammar and knows nothing about how wide a square is.

# Five feet to a square, as everywhere else in the game.
FEET_PER_SQUARE = 5

# What a room may come out as, in squares. The floor is six because a scene smaller than
# that has nowhere to stand off; the ceiling is twenty-four because the authored range
# runs to 125 feet (25 squares) and a grid much past twenty-four is a map the player reads
# badly. Measured range: 25-125 ft wide, 15-110 ft deep.
MIN_SQUARES, MAX_SQUARES = 6, 24

# How much of the floor each clutter word puts something solid on, as a fraction of the
# inner squares. Calibrated against the hand-written shapes rather than invented: "some"
# lands a 14x12 room on six clumps, which is what the tavern and the market were already
# given by hand, and "dense" lands it on twelve, which is what the warrens have.
CLUTTER = {"bare": 0.02, "some": 0.05, "cluttered": 0.08, "dense": 0.11}

# And how much of it is bad going. "firm" is not nothing — a floor with no rubble on it
# anywhere reads as a stage — and the hand-written places sit at two to three per cent.
FOOTING = {"firm": 0.02, "broken": 0.08, "bad": 0.18}

# A clump runs one to this many squares; the count below is divided by the average.
CLUMP_MAX = 2

VERTICAL_KINDS = ("ledge", "slope", "scatter", "none")


def from_world(raw: dict, ground: "Shape | None" = None) -> "Shape | None":
    """The shape an authored place actually has, or None when the world said nothing.

    The dimensions, the clutter, the footing and the vertical kind are the world's. The
    `about` phrase is NOT: it is the sentence a tell is built from, written for that
    purpose and never a number, while the export's own `about` is a line about the
    settlement's politics ("A merchant oligarchy that outspends the nobility") which would
    read as nonsense said of a floor. So the ground the table would have given keeps its
    phrase and loses everything else.
    """
    if not isinstance(raw, dict):
        return None
    size = raw.get("size_ft") if isinstance(raw.get("size_ft"), dict) else {}
    clutter = str(raw.get("clutter") or "").strip().lower()
    footing = str(raw.get("footing") or "").strip().lower()
    vertical = str(raw.get("vertical") or "").strip().lower()
    if not (size or clutter or footing or vertical):
        return None
    base = ground if ground is not None else OPEN
    width = _squares(size.get("width"), base.width)
    height = _squares(size.get("depth"), base.height)
    # An authored height of null is a place with no roof, which is a fact and not a gap:
    # 241 of the 456 are written that way and they are the yards, the greens and the
    # streets. Only a place that wrote nothing at all about its size keeps the table's
    # ceiling — the empty-is-not-absent trap, and the one field here where it bites.
    ceiling = base.ceiling if not size else _levels(size.get("height"))
    inner = max(1, width - 2) * max(1, height - 2)
    clumps = round(inner * CLUTTER.get(clutter, CLUTTER["some"]) / ((1 + CLUMP_MAX) / 2))
    rough = round(inner * FOOTING.get(footing, FOOTING["firm"]))
    kind = vertical if vertical in VERTICAL_KINDS else base.vertical
    # `rise` and `rise_to` are not authored and are not asked for: they are how many
    # raised things a SCATTER scatters and how far a SLOPE climbs, which the kind already
    # implies. A ledge and a flat floor use neither.
    return Shape(width=width, height=height, ceiling=ceiling,
                 clumps=max(0, clumps), clump_max=CLUMP_MAX if clumps else 1,
                 rough=max(0, rough),
                 rise=max(3, inner // 60) if kind == "scatter" else 0,
                 rise_to=2 if kind == "slope" else 1,
                 vertical=kind, about=base.about)


def _squares(feet, fallback: int) -> int:
    try:
        n = round(float(feet) / FEET_PER_SQUARE)
    except (TypeError, ValueError):
        return fallback
    return max(MIN_SQUARES, min(MAX_SQUARES, n)) if n else fallback


def _levels(feet) -> int | None:
    try:
        n = round(float(feet) / FEET_PER_SQUARE)
    except (TypeError, ValueError):
        return None
    return max(1, n) if n else None


def shape_for(place_id: str, terrain: str = "", authored: "Shape | None" = None) -> Shape:
    """Which shape this place takes: what the world wrote, then its own spot, then its
    ground, then open.

    `authored` is carried on the `Place` by `places._authored` and handed down, never
    looked up: this module has no world and must not acquire one. A caller holding only an
    id gets the derived answer, which is what every place got before World Bible shipped
    room dimensions.

    A storey is read as the building it is a floor of. Without that, `the-tavern^1` matches
    no spot, falls through to `urban`, and an upstairs room comes out **with no roof on it**
    — which would let a flier leave through a bedroom ceiling and is the sort of wrong that
    only shows up when somebody tries it.
    """
    bare = str(place_id or "").rsplit(STOREY, 1)[0]
    spot = bare.rsplit(":", 1)[-1].rsplit("/", 1)[-1].strip().lower()
    found = authored or BY_SPOT.get(spot) or BY_TERRAIN.get(
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


def for_place(place_id: str, terrain: str = "", authored: "Shape | None" = None) -> Grid:
    """The ground at this place, the same every time it is asked for.

    Nothing is placed in the outermost ring, so a plan can never wall a scene in or strand
    a combatant in a corner they cannot leave. Everything in the middle is fair game.
    """
    shape = shape_for(place_id, terrain, authored)
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


def describe(place_id: str, terrain: str = "", authored: "Shape | None" = None) -> str:
    """One phrase about the ground, for a tell. Never a number — the third law."""
    return shape_for(place_id, terrain, authored).about
