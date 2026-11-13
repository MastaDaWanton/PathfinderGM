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
(Since 2026-11-11 `rules/fixtures.py` NAMES these squares — this clump is the bar, that
raised band a gallery reached by a stair — without changing any of them; every name it
gives carries only properties the engine reads.)

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
    # How the clumps are laid: `scatter` (anywhere, any way round) or `rows` (straight
    # stall rows with aisles between, a market's; `_rows`).
    layout: str = "scatter"
    # The fixture kinds a WORLD wrote for this place (`fixtures` in the export, a closed
    # list: content/rules/fixtures.json). Empty for every derived shape; `rules/fixtures`
    # reads it in place of the spot's own row.
    fixtures: tuple = ()
    # The vessel a `ship` layout is the hull of (a `ships.VESSELS` key), "" otherwise.
    vessel: str = ""


# Two squares of headroom is a house: ten feet, enough for a Medium creature to stand with
# a little air, and no room at all for anything to fly over anybody's head. Four is a hall.
LOW, HALL = 2, 4

# The spots this app generates, by their own slugs. A closed list, and short, because the
# tables it mirrors are closed and short.
BY_SPOT: dict[str, Shape] = {
    "the-market": Shape(16, 16, None, clumps=7, clump_max=2, rise=2,
                        vertical="scatter", about="stalls and awnings, and a cart to climb on",
                        layout="rows"),
    "the-tavern": Shape(12, 10, LOW, clumps=6, clump_max=2,
                        about="tables, benches and a hearth"),
    "the-temple": Shape(14, 12, HALL, clumps=6, clump_max=1, rise=3, rise_to=1,
                        about="a colonnade, and a dais at the end of it"),
    "the-gate": Shape(14, 10, None, clumps=4, clump_max=3, rise=4, rise_to=2,
                      about="the gatehouse either side, and the wall-walk over it"),
    # A village's entrance: the road, and what stands beside it. Long rather than wide,
    # because that is what a road reaching the first house looks like, and nothing to
    # climb — an unwalled settlement's way in is watched from the ground.
    "the-way-in": Shape(16, 8, None, clumps=3, clump_max=2, rough=2, vertical="none",
                        about="the road in, the first houses, and whoever is watching it"),
    "the-back-streets": Shape(10, 16, None, clumps=8, clump_max=3, rough=6,
                              vertical="none", about="walls close on both sides, and what is left in them"),
    "the-workshops": Shape(12, 12, LOW, clumps=7, clump_max=2,
                           about="benches, a forge and the work stacked around them"),
    "the-guildhall": Shape(14, 12, HALL, clumps=4, clump_max=1, rise=2,
                           about="a long room with a table down it"),
    "the-high-ground": Shape(16, 16, None, clumps=3, clump_max=2, rise=14, rise_to=3,
                             vertical="slope", about="ground that climbs, and something to stand behind"),
    # "the way in, and little to hide behind" until 2026-09-28: the gate's own words on
    # the edge of a forest (docs/playtest-2026-09-28.md, 20.3). Bobby stood among the
    # trees and the map's caption put him at the village entrance he had left.
    "the-approach": Shape(18, 14, None, clumps=3, clump_max=2,
                          vertical="slope", about="the near edge of it, and little to hide behind"),
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
                       about="a quay above the water, and what is stacked on it",
                       layout="quay"),
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
    # The alchemist's laboratory (alchemy plan §14): a low room crowded with benches,
    # shelving and the hooded hearth — raised things to get behind or up on, no rail, as
    # the smithy. The Ultimate Campaign's Alchemy Lab room is 8-16 squares of work space
    # for up to three people (aonprd Rules ID 1291); this is that, plus the room round it.
    "the-laboratory": Shape(10, 10, LOW, clumps=6, clump_max=1, rise=2,
                            vertical="scatter",
                            about="benches of glass, a still, and the hood over the fires"),
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
    # Somebody's house (`places.DWELLINGS`, 2026-10-01): founded, never drawn. Without a
    # row it fell to OPEN — a house under the sky, with no ceiling and so no upstairs.
    "the-house": Shape(10, 8, LOW, clumps=4, clump_max=2,
                       about="a hall, a hearth, and the stair to the rooms above"),
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

    # --- the ground just outside (rules/outskirts.py, 2026-09-28) --------------------
    # `@` marks the ring; a road head and a stretch of road carry the destination's id
    # after their slug, and `shape_for` reads them by the slug alone. Every one is under
    # the sky, and each has its own caption: "no caption names another place" is the
    # defect 20.3 measured.
    "@the-outskirts": Shape(20, 14, None, clumps=4, clump_max=2, rough=3,
                            vertical="scatter",
                            about="the last walls and sheds, and the land opening past them"),
    "@the-crossroads": Shape(18, 18, None, clumps=2, clump_max=1, rough=2,
                             vertical="none", about="tracks meeting, and a post where they part"),
    "@the-far-crossroads": Shape(18, 18, None, clumps=2, clump_max=1, rough=2,
                                 vertical="none",
                                 about="a second parting, with fewer wheel-ruts"),
    "@the-fields": Shape(20, 18, None, clumps=3, clump_max=2, rough=6,
                         vertical="none", about="furrows, a field wall, and a hut at the corner"),
    "@the-shore": Shape(20, 14, None, clumps=4, clump_max=2, rough=8, rise=3, rise_to=1,
                        vertical="scatter", about="wet ground, wrack, and the waterline"),
    "@the-road-to": Shape(20, 10, None, clumps=2, clump_max=2, rough=2,
                          vertical="none", about="a road leaving, ruts either side of it"),
    "@along-the-road-to": Shape(20, 10, None, clumps=3, clump_max=2, rough=4,
                                vertical="scatter", about="the road, and the verge beside it"),
}

# A road head's slug ends in the destination's id; its shape is its kind's.
_SPOT_PREFIXES = ("@along-the-road-to", "@the-road-to")

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

# What a room may come out as, in squares.
#
# The floor was six — thirty feet — and it was wrong, which the supplier caught and
# argued better than the floor was argued for: **"a lane ten feet across is an alley; the
# same lane at thirty feet is a street."** Two things followed from that and both were
# real. "Walls close on both sides" is this app's OWN stated reason for keeping the lane
# and the back streets flat, and a thirty-foot floor removes the geometry the reason
# depends on. And their generator had a rule that flattened anything three squares or
# less, which a floor of six made permanently unreachable.
#
# So two squares: ten feet, which is the width two Medium creatures can pass in and the
# narrowest thing that is still a fight rather than a queue. Nothing below that, because
# a one-square room has no room to miss in.
#
# The ceiling of twenty-four holds for a building's interior in a town only (the owner,
# 2026-11-12: "probably okay for building interiors inside of towns but anywhere else it
# should be uncapped"). It was set when the board had no zoom, as "a grid much past
# twenty-four is a map a player reads badly"; a street, a square or a yard is as big as
# the world says.
MIN_SQUARES, MAX_SQUARES = 2, 24

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
    # The world's own fixture kinds, held to the closed list: a word outside it is
    # dropped, never guessed at (models read, code validates — 2026-10-03). Imported only
    # when the world wrote some: tools/check_places.py runs this module without Django.
    named: tuple = ()
    if isinstance(raw.get("fixtures"), list) and raw["fixtures"]:
        from . import fixtures as fixtures_mod

        named = tuple(dict.fromkeys(
            w for w in (str(x or "").strip().lower() for x in raw["fixtures"])
            if w in fixtures_mod.kinds()))
    if not (size or clutter or footing or vertical or named):
        return None
    base = ground if ground is not None else OPEN
    if not (size or clutter or footing or vertical):
        # Fixtures and nothing else: the room keeps the table's shape exactly.
        from dataclasses import replace

        return replace(base, fixtures=named)
    # A roof in a town is a building's interior: capped. Anything else is not.
    cap = MAX_SQUARES if size and size.get("height") is not None \
        and "~urban:" in str(raw.get("id") or "") else None
    width = _squares(size.get("width"), base.width, cap)
    height = _squares(size.get("depth"), base.height, cap)
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
                 vertical=kind, about=base.about, fixtures=named, layout=base.layout)


def _squares(feet, fallback: int, cap: int | None = MAX_SQUARES) -> int:
    try:
        n = round(float(feet) / FEET_PER_SQUARE)
    except (TypeError, ValueError):
        return fallback
    if not n:
        return fallback
    return max(MIN_SQUARES, min(cap, n) if cap else n)


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
    spot = next((p for p in _SPOT_PREFIXES if spot.startswith(p + "-")), spot)
    if authored is None and str(terrain or "").strip().lower() == "deck":
        return ship_shape("", place_id)   # the vessel unknown here: its room's usual hull
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


def for_place(place_id: str, terrain: str = "", authored: "Shape | None" = None,
              *, scatter: bool = False) -> Grid:
    """The ground at this place, the same every time it is asked for.

    Nothing is placed in the outermost ring, so a plan can never wall a scene in or strand
    a combatant in a corner they cannot leave. Everything in the middle is fair game.
    `scatter` lays a `rows` place the way it was laid before rows (`fixtures.derive`
    names a market saved then by its own old stalls).
    """
    shape = shape_for(place_id, terrain, authored)
    r = _Rolls(_seed(place_id))
    grid = Grid(width=shape.width, height=shape.height, ceiling=shape.ceiling)

    def somewhere() -> Point:
        return (1 + r.next(max(1, shape.width - 2)),
                1 + r.next(max(1, shape.height - 2)))

    if shape.layout == "ship":
        _lay_parts(grid, shape, place_id)
        return grid
    if shape.layout == "rows" and not scatter:
        _rows(grid, shape, r)
    for _ in range(0 if shape.layout == "rows" and not scatter else shape.clumps):
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
    if shape.layout == "quay":
        _lay_parts(grid, shape, place_id)
    return grid


def _rows(grid: Grid, shape: Shape, r: "_Rolls") -> None:
    """A market's stalls in straight rows (plan item 6, 2026-11-13).

    Scattered, two runs that happened to touch were typed as one stall bent round a corner
    (the owner's market picture showed three L-shaped stalls). In rows they cannot touch:
    a row, then a two-square aisle (10 ft, the FAO's and street-market guides' main aisle),
    and a gap of one or two squares between stalls in a row to walk through. Rows run the
    long way; a square market rolls for it. Whole rows are filled, in rolled order, until
    `clumps` stalls stand: seven picked from every slot read as scattered again."""
    w, h = shape.width, shape.height
    across = w > h or (w == h and r.next(2) == 0)
    long_, short = (w, h) if across else (h, w)
    lanes = []
    for lane in range(2, short - 2, 3):
        at, row = 1 + r.next(2), []            # rows start staggered, not in a column
        while True:
            run = 1 + r.next(shape.clump_max)
            if at + run > long_ - 1:
                break
            row.append([(at + k, lane) for k in range(run)])
            at += run + 1 + r.next(2)
        lanes.append(row)
    left = shape.clumps
    while lanes and left > 0:
        for stall in lanes.pop(r.next(len(lanes)))[:left]:
            left -= 1
            for a, b in stall:
                grid.blocked.add((a, b) if across else (b, a))


# --- a ship's rooms, and the quay she lies at (2026-11-13) ------------------------------
#
# The owner: "make sure we have some boat/ship specific 3D objects like coils of rope and
# masts to populate the maps". A deck was the `deck` terrain's twelve-by-twenty scatter
# with a gallery down one side: a room, not a ship. So a ship's rooms get a HULL, laid
# like a ship and not like a room: long and narrow, the bow at the top of the board, a
# mast or more on the centre line, the rail down both sides with the sea past it, a hatch,
# the helm aft, coils of rope and cargo about the place.
#
# These are the one layout in this module that places NAMED things (`parts`): a scatter
# of clumps cannot be a mast, a hatch and a capstan, and `rules/fixtures.py` typing clumps
# in turn would make the mast a barrel as often as not. Every part is still only geometry
# the engine reads — blocked, difficult, raised, or left open — and `fixtures.derive`
# names exactly these squares, so the two can never disagree.
#
# Beam and length in feet, how many masts, and what she is steered by: Ultimate Combat
# pp.184-185, the water vehicles (aonprd.com Vehicles: keelboat "Squares 40 (20 ft. by
# 50 ft.)", rudder; longship 15 by 75, one mast, rudder, forty rowers; sailing ship
# 20 by 75, two masts, steering wheel; warship 20 by 100, one mast, wheel, eighty
# rowers; galley 20 by 130, three masts, wheel, 140 rowers). `ships.VESSELS` has the
# GameMastery Guide's fast-play numbers, which give no dimensions at all; its rooms are
# read from there, its hull from here. "The nine squares around the steering wheel,
# typically located at the aft of the ship" (UC) is where the helm goes.
HULLS = {
    "keelboat": (20, 50, 1, "the tiller"),
    "longship": (15, 75, 1, "the steerboard"),
    "sailing ship": (20, 75, 2, "the wheel"),
    "warship": (20, 100, 1, "the wheel"),
    "galley": (20, 130, 3, "the wheel"),
}
_MASTS = {1: ("the mast",), 2: ("the foremast", "the mainmast"),
          3: ("the foremast", "the mainmast", "the mizzen")}
# A ship's rooms by their slug (`ships.places_of`). The castles are short decks aft; the
# rigging is the masts and their shrouds over the same hull; the rest are under a deck.
_AFT = ("the-steering-deck", "the-sterncastle")
_BELOW = ("the-hold", "below-decks", "the-oar-deck")
# The vessel a room implies when nothing says which (a caller holding only a place id):
# only a galley has an oar deck, and so on; anything else is the trader.
_HULL_OF_ROOM = {"the-oar-deck": "galley", "the-sterncastle": "warship",
                 "the-steering-deck": "longship"}


def _slug_of(place_id: str) -> str:
    bare = str(place_id or "").rsplit(STOREY, 1)[0]
    return bare.rsplit(":", 1)[-1].rsplit("/", 1)[-1].strip().lower()


def ship_shape(kind: str, place_id: str) -> Shape:
    """The hull of this room of a ship of this kind (a `ships.VESSELS` key; "" when the
    caller does not know, and the room's own name picks the likeliest)."""
    from . import ships

    slug = _slug_of(place_id)
    kind = kind if kind in HULLS else _HULL_OF_ROOM.get(slug, "sailing ship")
    beam, length, _masts, _helm = HULLS[kind]
    wide, long_ = beam // FEET_PER_SQUARE, length // FEET_PER_SQUARE
    if slug in _AFT:
        long_ = max(4, long_ // 4)
    about = next((a for label, a, _i in ships.VESSELS[kind]["places"]
                  if label.replace(" ", "-") == slug),
                 BY_TERRAIN["deck"].about)
    return Shape(wide + 2, long_ + 2, LOW if slug in _BELOW else None,
                 vertical="scatter", layout="ship", vessel=kind, about=about)


def parts(place_id: str, terrain: str = "", authored: "Shape | None" = None) -> list[dict]:
    """The named pieces of a ship's room or a quay, the same every time: each
    {"kind", "squares", "lay" (blocked / difficult / raised / open), "level", "name"}.
    Empty for every other place (`rules/fixtures.py` types those by their clumps)."""
    shape = shape_for(place_id, terrain, authored)
    if shape.layout == "ship":
        return _ship_parts(shape, place_id)
    if shape.layout == "quay":
        return _quay_parts(shape, place_id)
    return []


def _lay_parts(grid: Grid, shape: Shape, place_id: str) -> None:
    """Put the parts' geometry down. Below decks, everything outside the hull is the
    ship's side: solid, and nothing's name."""
    got = _ship_parts(shape, place_id) if shape.layout == "ship" else _quay_parts(shape, place_id)
    for part in got:
        for p in part["squares"]:
            grid.blocked.discard(p)
            grid.difficult.discard(p)
            grid.floor.pop(p, None)
            grid.parapet.pop(p, None)
            if part["lay"] == "blocked":
                grid.blocked.add(p)
            elif part["lay"] == "difficult":
                grid.difficult.add(p)
            elif part["lay"] == "raised":
                grid.floor[p] = part["level"]
    if shape.layout == "ship" and shape.ceiling is not None:
        hull = _hull(shape, _slug_of(place_id))
        grid.blocked |= {(x, y) for x in range(shape.width) for y in range(shape.height)
                         if (x, y) not in hull}


def _hull(shape: Shape, slug: str) -> set:
    """The squares of planking: columns 1..beam, rows 1..length, the bow's corners cut
    off (row 1) so she comes to a point. A castle aft is square at both ends."""
    wide, long_ = shape.width - 2, shape.height - 2
    return {(x, y) for y in range(1, long_ + 1) for x in range(1, wide + 1)
            if not (y == 1 and slug not in _AFT and wide >= 3 and x in (1, wide))}


def _ship_parts(shape: Shape, place_id: str) -> list[dict]:
    from . import ships

    slug = _slug_of(place_id)
    # The vessel's own seed, not the room's, so the hatch below is under the hatch above.
    r = _Rolls(_seed(str(place_id).split("~", 1)[0]))
    wide, long_ = shape.width - 2, shape.height - 2
    _b, _l, masts, helm = HULLS[shape.vessel]
    hull = _hull(shape, slug)
    aft, below, aloft = slug in _AFT, shape.ceiling is not None, slug == "the-rigging"
    out: list[dict] = []
    taken: set = set()

    def put(kind, squares, lay, level=0, name=""):
        squares = [tuple(p) for p in squares]
        if not squares or any(p not in hull or p in taken for p in squares):
            return False
        taken.update(squares)
        out.append({"kind": kind, "squares": squares, "lay": lay, "level": level,
                    "name": name})
        return True

    mid = (wide + 1) // 2 if wide % 2 else wide // 2 + r.next(2)
    mast_rows = [] if aft else [max(3, round(1 + (i + 1) * long_ / (masts + 1)))
                                for i in range(masts)]
    for row, name in zip(mast_rows, _MASTS[masts]):
        put("mast", [(mid, row)], "blocked", name=name)
        if not below:
            # The shrouds, a step abaft the mast at either rail: a rope ladder up to the top.
            for x in (1, wide):
                put("rigging", [(x, row + 1)], "raised", 2, "the rigging")
    if not below:
        # The rail: every square of sea beside the hull. The sea beyond it is the sea.
        side = {(x, y) for x in range(shape.width) for y in range(shape.height)
                if (x, y) not in hull}
        rail = sorted(p for p in side if any(
            (p[0] + dx, p[1] + dy) in hull for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))))
        out.append({"kind": "rail", "squares": rail, "lay": "blocked", "level": 0,
                    "name": "the rail"})
        sea = sorted(side - set(rail))
        if sea:
            out.append({"kind": "sea", "squares": sea, "lay": "blocked", "level": 0,
                        "name": "the sea"})
    if aloft:
        return out
    hatch = (round((mast_rows[0] + mast_rows[1]) / 2) if len(mast_rows) > 1
             else min(long_ - 2, mast_rows[0] + 3) if mast_rows else 2)
    put("hatch", [(mid, hatch)], "open", name="the hatch")
    has_castle = any(label.replace(" ", "-") in _AFT
                     for label, _a, _i in ships.VESSELS[shape.vessel]["places"])
    if aft or (not below and not has_castle):
        put("helm", [(mid, long_ - 1)], "blocked", name=helm)
        put("rope", [(1 if mid > 1 else wide, long_ - 1)], "difficult", name="a coil of rope")
    for row in mast_rows:
        # Lines coiled down at the foot of every mast.
        put("rope", [(mid - 1, row)], "difficult", name="a coil of rope") or \
            put("rope", [(mid + 1, row)], "difficult", name="a coil of rope")
    if not below and not aft:
        if shape.vessel in ("sailing ship", "warship", "galley"):
            put("capstan", [(mid, 3)], "blocked", name="the capstan") or \
                put("capstan", [(mid, 4)], "blocked", name="the capstan")
        put("anchor", [(wide, 2)], "blocked", name="the anchor")
        put("rope", [(1, 2)], "difficult", name="a coil of rope")
        if shape.vessel in ("sailing ship", "warship"):
            col = wide + 1 - mid
            for y in range(hatch + 2, long_ - 2):
                if put("boat", [(col, y), (col, y + 1)], "blocked", name="the ship's boat"):
                    break
    # Nothing beside a mast's rows but what is laid above: a bench or a crate there would
    # close the deck across and leave the shrouds with no square to step up from.
    keep_clear = {y for m in mast_rows for y in (m - 1, m, m + 1, m + 2)} | {hatch}
    rowers = (slug == "the-deck" and shape.vessel == "longship") or slug == "the-oar-deck"
    if rowers:
        for y in range(3, long_ - 1, 2):
            if y not in keep_clear:
                for x in (1, wide):
                    put("bench", [(x, y)], "blocked", name="a rowing bench")
        return out
    if aft:
        return out
    # Cargo along the ship's sides, the middle kept for walking: the hold stowed full,
    # below decks every other row (sea chests and stores), on deck a few lashed down.
    rows = [y for y in range(2, long_) if y not in keep_clear]
    if slug == "the-hold":
        stow = [(x, y) for y in rows for x in (1, wide)]
    elif below:
        stow = [(x, y) for y in rows[::2] for x in (1, wide)]
    else:
        spots = [(x, y) for y in rows if 2 < y < long_ - 1 for x in (1, wide)]
        stow = [spots.pop(r.next(len(spots))) for _ in range(min(len(spots), 2 + r.next(3)))]
    for i, p in enumerate(sorted(stow)):
        kind = ("crate", "barrel")[(i + r.next(2)) % 2]
        put(kind, [p], "blocked", name="")
    return out


def _quay_parts(shape: Shape, place_id: str) -> list[dict]:
    """The docks' water side: the harbour along one long edge, bollards along the quay's
    lip with rope coiled by them, and a ship's boat tied up in the water."""
    r = _Rolls(_seed(place_id) ^ 0x5EA)
    across = shape.width >= shape.height
    long_, short = (shape.width, shape.height) if across else (shape.height, shape.width)

    def at(a, b):            # (along the quay, out from the land) as a board square
        return (a, b) if across else (b, a)

    deep = 2 if short >= 8 else 1
    water = [at(a, b) for a in range(long_) for b in range(short - deep, short)]
    lip = short - deep - 1
    boat_at = 2 + r.next(max(1, long_ - 7))
    boat = [at(a, short - deep) for a in range(boat_at, boat_at + 3)]
    out = [{"kind": "sea", "squares": sorted(set(water) - set(boat)), "lay": "blocked",
            "level": 0, "name": ""},
           {"kind": "boat", "squares": boat, "lay": "blocked", "level": 0,
            "name": "a ship's boat"}]
    for a in range(2 + r.next(2), long_ - 1, 4):
        out.append({"kind": "bollard", "squares": [at(a, lip)], "lay": "blocked",
                    "level": 0, "name": "a bollard"})
        if a + 1 < long_ - 1 and r.next(2):
            out.append({"kind": "rope", "squares": [at(a + 1, lip)], "lay": "difficult",
                        "level": 0, "name": "a coil of rope"})
    return out


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
