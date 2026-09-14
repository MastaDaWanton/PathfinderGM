"""The battlefield in five-foot squares.

`docs/architecture.md` said "initiative and positions, no grid", and zones — engaged, near,
far — were enough for a fight the GM narrated. They stopped being enough as soon as
anything needed to know *where*: attacks of opportunity are defined by which squares a
creature threatens, a fireball is defined by which squares it covers, and a charge is
defined by whether there is a straight line to run down. Each of those had to be either
refused or hand-waved by the GM, and hand-waving is how a rules engine turns back into a
chat log.

Zones do not go away. A scene without a grid still works exactly as it did, and a scene
*with* one derives its zones from real distance instead of taking the GM's word — see
`zone_between`. That way nothing in the intent protocol had to change to gain a map.

Coordinates are integer `(col, row)` square indices with the origin top-left, matching how
the map is drawn. Distances are returned in **feet**, because every rule in the book is
written in feet and converting at the edges is where sign errors live.

What this module deliberately does not do: it has no opinion about who may move where.
Legality is the engine's, and geometry is this module's. Mixing the two is what made the
first sketch of `movement_cost` need a `Scene`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappop, heappush

from .tables import SPACE_AND_REACH

Point = tuple[int, int]
# A square plus the level it is on, five feet apiece. `Point` stays two-dimensional
# because the map is drawn flat and most of the app has no vertical in it; anything
# that reads a third coordinate accepts either and treats a missing one as ground.
Cell = tuple[int, int, int]

# One square, in feet. Named rather than spelled 5 everywhere, because "5" appears in this
# file as a distance, as a reach and as a speed, and only one of those is this.
SQUARE_FT = 5

# The eight directions, ordered so index//2 gives an axis — used by `cone`.
DIRECTIONS: dict[str, Point] = {
    "n": (0, -1), "ne": (1, -1), "e": (1, 0), "se": (1, 1),
    "s": (0, 1), "sw": (-1, 1), "w": (-1, 0), "nw": (-1, -1),
}


def _xyz(p) -> tuple[int, int, int]:
    """A point as three coordinates, with a missing third reading as ground level.

    Every position in the app was `(col, row)` before height existed, and most still are:
    a scene with no vertical in it should not have to say `z=0` on every call, and a save
    written last week must load without a migration. So two-tuples keep working and mean
    exactly what they meant.
    """
    return (p[0], p[1], p[2] if len(p) > 2 else 0)


def distance(a, b) -> int:
    """Distance in feet, counting diagonals the way 1e counts them.

    "The first diagonal counts as 5 feet, the second counts as 10 feet, the third as 5,
    and so on." Not Euclidean and not Chebyshev — the naive `max(dx, dy) * 5` makes a
    diagonal retreat free, and the naive Pythagoras makes every distance a fraction.

    Areas count the same way, which is why there is one function here and not two.

    **The third axis is a house rule, and this is the one place it is decided.**
    Pathfinder does not have one: Movement, Position and Distance and Measuring Distance
    both define the five-foot square and the 5-10-5 diagonal and contain no vertical
    clause at all (checked against aonprd.com/Rules.aspx?ID=173 and ID=175 on 2026-09-14).
    Nothing official says whether climbing a square while stepping sideways costs one
    diagonal or two.

    What is chosen here is the reading that adds no second rule to learn: a step is
    diagonal if it moves on more than one axis, and **the number of diagonal steps is the
    second-largest of the three deltas**. Sort them and the shape falls out — the smallest
    is how many steps move on all three axes, the middle is how many move on at least two,
    and the largest is the total number of steps.

    It reduces to the existing two-dimensional answer exactly when the heights match
    (`dz == 0` sorts to the front and the middle delta becomes `min(dx, dy)`), which is
    why this could replace the old body rather than sit beside it. Straight up three
    squares is fifteen feet; one step up and one step over is five, like any other first
    diagonal.
    """
    ax, ay, az = _xyz(a)
    bx, by, bz = _xyz(b)
    return _count(abs(bx - ax), abs(by - ay), abs(bz - az))


def _count(dx: int, dy: int, dz: int = 0) -> int:
    """Feet for a separation of so many squares on each axis. See `distance`."""
    d = sorted((dx, dy, dz))
    diagonals, straights = d[1], d[2] - d[1]
    return SQUARE_FT * (straights + diagonals + diagonals // 2)


def footprint(anchor: Point, size: str = "medium") -> list[Point]:
    """Every square a creature of this size stands on, anchored at its top-left square.

    Top-left rather than centre because a Large creature occupies an even 2x2 and has no
    centre square to anchor to. Half the bugs in a first pass at this were an ogre whose
    position was half a square off its own footprint.
    """
    n = SPACE_AND_REACH.get(size.lower(), SPACE_AND_REACH["medium"])["squares"]
    return [(anchor[0] + dx, anchor[1] + dy) for dy in range(n) for dx in range(n)]


def natural_reach(size: str = "medium", shape: str = "tall") -> int:
    """Natural reach in feet. An ogre threatens 10 feet and a horse threatens 5."""
    row = SPACE_AND_REACH.get(size.lower(), SPACE_AND_REACH["medium"])
    return row["reach_long" if shape == "long" else "reach_tall"]


def height_ft(size: str = "medium", shape: str = "tall",
              override: float | None = None) -> float:
    """How far up a creature of this size reaches when it stands, in feet.

    `override` wins, because the source of these bands says they are typical and that
    exceptions exist — so a document that knows its creature is nine feet of Medium says
    so, and this table stops guessing for it.

    A `long` creature wears its size band horizontally rather than vertically (a horse is
    Large and is not sixteen feet tall), so it gets its space instead: about as tall as it
    is wide, which is the only other measurement the rules hand us.
    """
    if override is not None:
        return max(0.0, float(override))
    row = SPACE_AND_REACH.get(size.lower(), SPACE_AND_REACH["medium"])
    return float(row["space"] if shape == "long" else row["tall_ft"])


def height_squares(size: str = "medium", shape: str = "tall",
                   override: float | None = None) -> int:
    """How many squares of vertical a creature of this size fills, at least one.

    Rounded up, because the question this answers is "what has to clear it" — eight feet
    of Medium needs two squares of headroom, and a two-foot Tiny still needs one.
    """
    ft = height_ft(size, shape, override)
    return max(1, -(-int(ft * 100) // (SQUARE_FT * 100)))


def volume(anchor: Point, size: str = "medium", level: int = 0,
           shape: str = "tall", height: float | None = None) -> list[Cell]:
    """Every cell a creature fills — its footprint, stacked as high as it stands.

    The three-dimensional `footprint`, and anchored the same way: top-left of the
    footprint, and `level` is the square its feet are in. A spider clinging to a ceiling
    twenty feet up is `level=4`; a flier is wherever it climbed to.
    """
    tall = height_squares(size, shape, height)
    return [(x, y, level + dz)
            for (x, y) in footprint(anchor, size) for dz in range(tall)]


def _span(lo: int, n: int) -> tuple[int, int]:
    return lo, lo + n - 1


def distance_between(a: Point, a_size: str, b: Point, b_size: str,
                     a_shape: str = "tall", b_shape: str = "tall",
                     a_height: float | None = None,
                     b_height: float | None = None) -> int:
    """Distance between two creatures — the shortest gap between the space they fill.

    Measuring anchor to anchor makes a Colossal dragon impossible to reach: its anchor is
    up to six squares from the edge a character is standing against, and every reach check
    would fail while the two were nose to nose.

    Either position may carry a third coordinate. With both on the ground this is the
    same number it always was, because two creatures standing on the same floor overlap
    on the vertical axis and the gap there is zero.

    Computed from the gap on each axis rather than by comparing every cell to every cell.
    Both answers are identical — `test_the_box_gap_agrees_with_comparing_every_cell`
    proves it across sizes and offsets — and the enumeration is not affordable once
    creatures have height: a Colossal creature is 6x6 squares and thirteen of them tall,
    so a pair of them is 468 cells against 468, and the old loop would ask 219,024
    questions to answer one reach check.
    """
    ax, ay, az = _xyz(a)
    bx, by, bz = _xyz(b)
    an, bn = size_squares(a_size), size_squares(b_size)
    ah = height_squares(a_size, a_shape, a_height)
    bh = height_squares(b_size, b_shape, b_height)

    gaps = []
    for (lo1, n1), (lo2, n2) in (((ax, an), (bx, bn)), ((ay, an), (by, bn)),
                                 ((az, ah), (bz, bh))):
        a_lo, a_hi = _span(lo1, n1)
        b_lo, b_hi = _span(lo2, n2)
        gaps.append(max(0, a_lo - b_hi, b_lo - a_hi))
    return _count(*gaps)


def threatened_squares(anchor: Point, size: str = "medium", reach: int = 0,
                       shape: str = "tall") -> set[Point]:
    """Every square this creature threatens — the definition an attack of opportunity is
    built on, which is why this module exists before reactions do.

    `reach` of 0 means "use the creature's natural reach". A weapon with the reach
    property, or Blood Bending's own extensions, pass their own number.

    A creature does not threaten the squares it is standing in. A reach weapon also does
    not threaten adjacent squares in 1e, but that belongs to the weapon rather than to
    geometry, so it is the caller's to subtract.
    """
    ft = reach or natural_reach(size, shape)
    if ft <= 0:
        return set()
    mine = set(footprint(anchor, size))
    # Far enough out to catch the whole reach from the *far* edge of the footprint, which
    # for a Colossal creature is five squares past its anchor before reach starts counting.
    span = ft // SQUARE_FT + size_squares(size)
    out = set()
    for dy in range(-span, span + 1):
        for dx in range(-span, span + 1):
            square = (anchor[0] + dx, anchor[1] + dy)
            if square in mine:
                continue
            if min(distance(square, p) for p in mine) <= ft:
                out.add(square)
    return out


def is_adjacent(a: Point, a_size: str, b: Point, b_size: str) -> bool:
    return distance_between(a, a_size, b, b_size) <= SQUARE_FT


@dataclass
class Grid:
    """The map: how big it is, and which squares are awkward or solid.

    Terrain is held as sets of squares rather than a dense array because a battlefield is
    mostly ordinary floor, and a 40x40 map of the word "normal" is 1,600 entries that a
    save file has to carry and a human has to read.
    """
    width: int = 20
    height: int = 20
    # Costs double to enter. Rubble, undergrowth, a flooded floor.
    difficult: set[Point] = field(default_factory=set)
    # Cannot be entered and blocks sight. A wall, a pillar.
    blocked: set[Point] = field(default_factory=set)
    # Blocks sight without blocking movement — smoke, fog, a blood mist.
    obscuring: set[Point] = field(default_factory=set)
    # How high the floor stands in a square, in levels, where it is not zero. A dais, a
    # cart bed, a wall-walk, the slope of a hill. Sparse for the same reason the terrain
    # sets are: a battlefield is mostly flat as well as mostly ordinary, and the squares
    # worth naming are few.
    #
    # This is the heightmap and not a voxel field, which is the shape Final Fantasy Tactics
    # settled on for the same job: one number per square buys rooftops, daises and "you
    # cannot get up there", and it cannot express an overhang — nothing is ever *under* a
    # walkable square in the same column. Storeys are places joined by stairs instead,
    # which is where the place graph already was.
    floor: dict[Point, int] = field(default_factory=dict)
    # Levels of headroom above the floor, or None for open sky. A cellar at 2 is ten feet
    # of air: something can stand, and a flier can get one square up and no further.
    ceiling: int | None = None
    # Low obstacles, by the absolute level of their top: a balustrade, a parapet, a
    # counter, a cart's side. 1e has this exactly — "a low obstacle (such as a wall no
    # higher than half your height) provides cover" — and the reason it is not just a
    # `blocked` square is what a balustrade does to a fight on two levels. Blocked is
    # solid at every height, so a gallery rail between an archer above and a man below
    # reads as a wall and the engine calls it TOTAL cover in both directions, which is
    # the opposite of what a rail is for. A parapet stops a line that passes at or under
    # its top and lets everything over it through.
    parapet: dict[Point, int] = field(default_factory=dict)

    def inside(self, p: Point) -> bool:
        return 0 <= p[0] < self.width and 0 <= p[1] < self.height

    def passable(self, p: Point) -> bool:
        return self.inside(p) and p not in self.blocked

    def ground(self, p: Point) -> int:
        """The level the floor stands at in this square. Zero unless it says otherwise."""
        return int(self.floor.get(tuple(p[:2]), 0))

    def headroom(self, p: Point) -> int | None:
        """The highest level a body may occupy over this square, or None under open sky.

        Measured from the square's own floor, so a dais in a cellar has less air above it
        than the flagstones beside it — which is the whole reason the two are separate
        numbers rather than one.
        """
        if self.ceiling is None:
            return None
        return self.ground(p) + self.ceiling - 1

    def enter_cost(self, p: Point) -> int:
        """Feet to enter this square, before diagonals are accounted for."""
        return SQUARE_FT * (2 if p in self.difficult else 1)

    # --- sight ---------------------------------------------------------------------------

    def opaque(self, p: Point) -> bool:
        return p in self.blocked or p in self.obscuring

    def line_of_sight(self, a: Point, b: Point) -> bool:
        """1e draws a line from any corner of one square to any corner of the other and
        asks whether it is unobstructed. Any one clear line is enough.

        Corner to corner rather than centre to centre, and the difference is not academic:
        centres make a creature standing directly behind a single pillar invisible when
        the rules say they can be seen around it.
        """
        if a == b:
            return True
        for ca in _corners(a):
            for cb in _corners(b):
                if not self._crosses_opaque(ca, cb, ignore=(a, b)):
                    return True
        return False

    def cover_between(self, a: Point, a_size: str, b: Point, b_size: str) -> str:
        """`"none"`, `"cover"` or `"total"` — what the terrain gives the target.

        1e's test, and it is the mirror image of `line_of_sight`: *"choose a corner of
        your square. If any line from this corner to any corner of the target's square
        passes through a square or border that blocks line of effect, the target has
        cover."* The attacker picks the corner that suits them, so a target has cover
        only when **every** corner the attacker could shoot from leaves at least one
        blocked line.

        Sight asks whether ANY line gets through; cover asks whether ALL of them do. Two
        questions of the same geometry with opposite quantifiers, which is why they are
        neighbours here and why neither is written in terms of the other.

        `total` when no line gets through at all — the target cannot be attacked, which
        the engine turns into a refusal rather than a penalty.

        **Height is part of it.** The levels of the two positions decide how high the line
        runs where it crosses each square, so a parapet stops what passes under its top
        and lets what clears it through. Written after a foyer was measured: an archer on
        a landing and a man on the floor below, with a balustrade between them, came back
        as TOTAL cover in both directions — the rail read as a wall because `blocked` is
        solid at every height, and neither could attack the other at all.

        A parapet can never give total cover. A rail is something to shoot over.

        Soft cover, the +4 a creature in the way grants, is not here: this module has no
        opinion about who is standing where, and `rules/position.py` reads the scene.
        """
        here, there = footprint(a, a_size), footprint(b, b_size)
        ignore = tuple(here) + tuple(there)
        a_level = a[2] if len(a) > 2 else 0
        b_level = b[2] if len(b) > 2 else 0
        # 1e's quantifier, and it is easy to lose: the attacker CHOOSES a corner, and
        # from that corner the target has cover if ANY line to it is obstructed. So cover
        # applies only when every corner the attacker could pick has something in the way
        # — one clean corner and there is no cover at all.
        anything_through = False
        for corner in {c for p in here for c in _corners(p)}:
            hard = rail = through = False
            for target in {c for p in there for c in _corners(p)}:
                if self._crosses_opaque(corner, target, ignore=ignore):
                    hard = True
                    continue
                through = True
                if self._crosses_parapet(corner, a_level, target, b_level,
                                         ignore=ignore):
                    rail = True
            if not through:
                continue                      # this corner sees nothing; try another
            anything_through = True
            if not hard and not rail:
                return "none"                 # a corner with a clean shot from it
        # Nothing got through from anywhere: solid. A parapet can never reach here,
        # because it never sets `hard` — a balustrade is a thing to shoot over, and
        # calling it total cover is how a gallery fight becomes two people who cannot
        # touch each other.
        return "cover" if anything_through else "total"

    def _crosses_parapet(self, a: tuple[float, float], a_level: int,
                         b: tuple[float, float], b_level: int,
                         ignore: tuple[Point, ...] = ()) -> bool:
        """Whether a low obstacle stands in this line, at the height the line is at.

        The one place the third dimension enters the cover geometry. Sampled like
        `_crosses_opaque`, but carrying the level along the segment: a rail whose top is
        level 2 stops a line running at 1 and does nothing to one running at 3.
        """
        if not self.parapet:
            return False
        steps = max(1, int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 8) + 1)
        for i in range(steps + 1):
            t = i / steps
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            at = a_level + (b_level - a_level) * t
            for square in _squares_at(x, y):
                if square in ignore:
                    continue
                top = self.parapet.get(square)
                if top is not None and at <= top:
                    return True
        return False

    def _crosses_opaque(self, a: tuple[float, float], b: tuple[float, float],
                        ignore: tuple[Point, ...] = ()) -> bool:
        """Walk the segment and ask, at each point, whether it is inside anything solid.

        Per point rather than per square, because of the seam. A point sitting exactly on
        a grid line belongs to *both* neighbouring squares, and the rule that a line grazing
        a pillar's edge gets through is really the rule that one of those two squares is
        open. When both are solid — a line run along the face of a wall — there is nothing
        to graze past and the line is blocked. Treating a seam as "belongs to neither" was
        the first attempt and it let sight travel the length of a stone wall.
        """
        steps = max(1, int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 8) + 1)
        for i in range(steps + 1):
            t = i / steps
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            here = [s for s in _squares_at(x, y) if s not in ignore]
            if here and all(self.opaque(s) for s in here):
                return True
        return False

    # --- movement ------------------------------------------------------------------------

    def reachable(self, start: Point, feet: int, size: str = "medium",
                  occupied: set[Point] | None = None) -> dict[Point, int]:
        """Every square this creature can end its move in, and what it costs to get there.

        Dijkstra rather than a flood fill, because difficult terrain means the cheapest
        route to a square is not always the shortest one, and because the diagonal rule
        makes cost depend on how many diagonals the *path* has already used — which is
        state a plain breadth-first search does not carry.

        The alternating diagonal is tracked per path in the priority queue. Rounding it at
        the end instead, which is the obvious shortcut, lets a character zig-zag across a
        map for the price of a straight line.
        """
        occupied = occupied or set()
        start = tuple(start)
        best: dict[tuple[Point, int], int] = {}
        out: dict[Point, int] = {}
        # (cost so far, square, whether the next diagonal is the expensive one)
        queue: list[tuple[int, Point, int]] = [(0, start, 0)]

        while queue:
            cost, here, odd = heappop(queue)
            if best.get((here, odd), 1 << 30) < cost:
                continue
            if here not in out or cost < out[here]:
                out[here] = cost

            for (dx, dy) in DIRECTIONS.values():
                there = (here[0] + dx, here[1] + dy)
                if not self._fits(there, size, occupied):
                    continue
                diagonal = dx and dy
                if diagonal and not self._corner_open(here, there):
                    continue
                step = self.enter_cost(there)
                # Every second diagonal costs an extra square. Difficult terrain doubles
                # the whole step, expensive diagonal included.
                if diagonal and odd:
                    step += SQUARE_FT * (2 if there in self.difficult else 1)
                nxt = cost + step
                if nxt > feet:
                    continue
                flag = (odd ^ 1) if diagonal else odd
                if nxt < best.get((there, flag), 1 << 30):
                    best[(there, flag)] = nxt
                    heappush(queue, (nxt, there, flag))

        out.pop(start, None)
        return out

    def _fits(self, anchor: Point, size: str, occupied: set[Point]) -> bool:
        squares = footprint(anchor, size)
        return all(self.passable(p) and p not in occupied for p in squares)

    def _corner_open(self, a: Point, b: Point) -> bool:
        """1e: "you can't move diagonally past a corner (even by taking a different
        diagonal to avoid the corner)". Either orthogonal neighbour being solid makes this
        a corner, so both must be open.

        Only blocking terrain counts, not other creatures: squeezing diagonally between two
        allies is legal and slipping between two wall corners is not.
        """
        return (a[0], b[1]) not in self.blocked and (b[0], a[1]) not in self.blocked

    def path_cost(self, path: list[Point]) -> int:
        """What a specific route costs, diagonals alternating along it."""
        total, odd = 0, 0
        for here, there in zip(path, path[1:]):
            diagonal = (here[0] != there[0]) and (here[1] != there[1])
            step = self.enter_cost(there)
            if diagonal and odd:
                step += SQUARE_FT * (2 if there in self.difficult else 1)
            if diagonal:
                odd ^= 1
            total += step
        return total


# --- areas of effect ---------------------------------------------------------------------

def burst(centre: Point, radius_ft: int) -> set[Point]:
    """A spread or burst: every square within the radius, sight permitting.

    Sight does not permit here — `Grid.line_of_sight` is applied by the caller when the
    effect is a spread rather than a burst, because the two differ on exactly that and
    nothing else.
    """
    r = radius_ft // SQUARE_FT + 1
    return {(centre[0] + dx, centre[1] + dy)
            for dy in range(-r, r + 1) for dx in range(-r, r + 1)
            if distance(centre, (centre[0] + dx, centre[1] + dy)) <= radius_ft}


def line(origin: Point, towards: Point, length_ft: int) -> set[Point]:
    """A line effect — lightning bolt, and a charge lane.

    Walks the supercover of the ray so a diagonal line catches both squares it clips
    rather than slipping between them, which is how a lightning bolt ends up missing
    somebody it visibly passes through.
    """
    if origin == towards:
        return {origin}
    dx, dy = towards[0] - origin[0], towards[1] - origin[1]
    span = max(abs(dx), abs(dy))
    reach = length_ft // SQUARE_FT + 1
    far = (origin[0] + round(dx / span * reach), origin[1] + round(dy / span * reach))
    out = {p for p in _squares_on_segment(_centre(origin), _centre(far))
           if distance(origin, p) <= length_ft}
    out.add(origin)
    return out


def cone(origin: Point, direction: str, length_ft: int) -> set[Point]:
    """A cone — burning hands, a dragon's breath.

    1e draws cones from a corner of the caster's square as a quarter-circle. This walks
    outward from the origin and keeps squares whose spread from the axis is no wider than
    their distance along it, which is the same quarter-circle to within a square and does
    not need the map to know which corner the caster is standing on. Where a table would
    argue about one square at the edge, this is the square it would argue about.
    """
    step = DIRECTIONS.get(direction.lower())
    if step is None:
        raise KeyError(f"no such direction {direction!r}")
    reach = length_ft // SQUARE_FT
    out: set[Point] = set()

    if step[0] and step[1]:
        # A diagonal cone is the quadrant on that side of the caster — which is exactly
        # what the corner-anchored quarter-circle covers when it points at a corner.
        for dy in range(reach + 1):
            for dx in range(reach + 1):
                p = (origin[0] + step[0] * dx, origin[1] + step[1] * dy)
                if p != origin and distance(origin, p) <= length_ft:
                    out.add(p)
        return out

    for depth in range(1, reach + 1):
        for spread in range(-depth, depth + 1):
            p = ((origin[0] + step[0] * depth, origin[1] + spread) if step[0]
                 else (origin[0] + spread, origin[1] + step[1] * depth))
            if distance(origin, p) <= length_ft:
                out.add(p)
    return out


# --- flanking ------------------------------------------------------------------------------

def flanking(a: Point, b: Point, target: Point, target_size: str = "medium") -> bool:
    """Are these two on opposite sides of the target?

    1e: draw a line from the centre of one attacker's square to the centre of the other's;
    if it passes through opposite sides — or opposite corners — of the target's space, they
    flank. For a creature bigger than one square the test is against the whole footprint,
    which is why an ogre is so much harder to flank than a goblin.
    """
    squares = footprint(target, target_size)
    if a in squares or b in squares:
        return False
    xs = [p[0] for p in squares]
    ys = [p[1] for p in squares]
    left, right, top, bottom = min(xs), max(xs), min(ys), max(ys)

    def side(p: Point) -> tuple[int, int]:
        return ((-1 if p[0] < left else 1 if p[0] > right else 0),
                (-1 if p[1] < top else 1 if p[1] > bottom else 0))

    sa, sb = side(a), side(b)
    if sa == (0, 0) or sb == (0, 0):
        return False
    return sa[0] == -sb[0] and sa[1] == -sb[1]


# --- zones, so nothing that already worked has to change ---------------------------------------

def zone_between(a: Point, a_size: str, b: Point, b_size: str) -> str:
    """The zone word for a real distance.

    The intent protocol speaks in `engaged` / `near` / `far` and every GM prompt is written
    in them. Rather than teach the model coordinates, a scene that has a grid answers those
    same three words from measured distance, and one that does not keeps taking the GM's
    word for it. The protocol did not have to change to gain a map.
    """
    ft = distance_between(a, a_size, b, b_size)
    if ft <= max(natural_reach(a_size), SQUARE_FT):
        return "engaged"
    return "near" if ft <= 30 else "far"


# --- geometry helpers ---------------------------------------------------------------------------

def _centre(p: Point) -> tuple[float, float]:
    return (p[0] + 0.5, p[1] + 0.5)


def _corners(p: Point) -> list[tuple[float, float]]:
    """The four true grid intersections of a square.

    Not nudged inward. The nudge was the obvious defensive move and it silently broke the
    rule this is here to implement: a line drawn along the *edge* of a blocking square
    grazes it and is not blocked, which is exactly how a creature is seen around a single
    pillar. Pushing the corners inside the square forces every such line into the pillar's
    interior, and the pillar becomes a wall.
    """
    return [(p[0], p[1]), (p[0] + 1, p[1]), (p[0], p[1] + 1), (p[0] + 1, p[1] + 1)]


_SEAM = 1e-9


def _squares_at(x: float, y: float) -> list[Point]:
    """Every square whose closure contains this point — one of it, two on an edge, four on
    a corner. What "the line is here" means when here is a boundary."""
    xs = [int(x) - 1, int(x)] if _on_seam(x) else [int(x // 1)]
    ys = [int(y) - 1, int(y)] if _on_seam(y) else [int(y // 1)]
    return [(cx, cy) for cx in xs for cy in ys]


def _squares_on_segment(a: tuple[float, float], b: tuple[float, float]) -> set[Point]:
    """Every square a segment passes through — the supercover, not Bresenham.

    Bresenham picks one square per step and skips the other one a diagonal clips, which is
    correct for drawing a thin line and wrong for asking what a line hits: a lightning bolt
    that slips between two squares it visibly crosses is a bolt somebody dodged by standing
    still.
    """
    steps = max(1, int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 8) + 1)
    out: set[Point] = set()
    for i in range(steps + 1):
        t = i / steps
        x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        out.update(_squares_at(x, y))
    return out


def _on_seam(v: float) -> bool:
    return abs(v - round(v)) < _SEAM


def size_squares(size: str) -> int:
    return SPACE_AND_REACH.get(size.lower(), SPACE_AND_REACH["medium"])["squares"]


__all__ = [
    "Cell", "Grid", "Point", "SQUARE_FT", "DIRECTIONS", "burst", "cone", "distance",
    "distance_between", "flanking", "footprint", "is_adjacent", "line", "natural_reach",
    "height_ft", "height_squares", "size_squares", "threatened_squares",
    "volume", "zone_between",
]
