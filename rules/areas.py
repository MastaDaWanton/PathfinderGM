"""Where a spell's area falls, and what it catches: the one place membership is decided.

Measured 2026-09-28 (docs/playtest-2026-09-28.md item 22): Bobby cast Burning Hands at a
man fifteen feet away. The outcome said `targets: []`, the dice said `1d4 = 1`, and the man
stood at 4 of 4 hit points while the prose burned his face. The cone that contained him was
never laid. `grid.cone`, `grid.line` and `grid.burst` existed and only the manifestation
path (`Engine._squares_for`) ever asked them, and `_op_cast` took its victims from
`intent.target` alone — which the Spells tab never sent for a cone. Every one of the 96
area-damage spells resolved the same way.

**The rule, from the book, and one rule for every shape** (owner, Q41). CRB, Aiming a
Spell (aonprd.com/Rules.aspx?ID=228): "The point of origin of a spell is always a grid
intersection. When determining whether a given creature is within the area of a spell,
count out the distance from the point of origin in squares ... you count from intersection
to intersection ... If the far edge of a square is within the spell's area, anything within
that square is within the spell's area." A cone "starts from any corner of your square".
So every area here is laid from an intersection and a square is in when its FAR corner is
within the length, counted 5-10-5. `grid.burst` measured from a square's centre and gave
61 squares for a 20-ft burst where the rule gives 44 (12 for 10 ft, 4 for 5 ft); `grid.cone`
did the same for cones, 12 squares for a diagonal 15-ft cone where the corner rule gives 6.
`rules/grid.py` is left untouched (read-only for this pass): the old shapes stay for the
callers that still use them, and no area of effect is decided anywhere but here.

**What was tried elsewhere and refused.** Every Foundry module that auto-targets ships it as
a toggle a human GM can overrule (Advanced Templates PF1, Walled Templates, Midi-QOL), and
Walled Templates offers two definitions of "caught" (centre point or area percentage).
There is no human GM here, so the toggle would be between the engine deciding and the model
deciding — which is how the man was burned in prose. One definition, always on, and the
cells go to the map so the player can see the ruling and dispute it the way a table would.

**House rules, marked as such.** The CRB states no vertical for cones or lines, so a cone
is extruded upward no wider than its depth (the same shape the quarter-circle has on the
flat), an upward cone is the same wedge about the vertical, and lines climb as they
travel. The canopy starts at 10 ft (`CANOPY_FROM`, owner's ruling Q32 — the CRB forest
gives no height) and is taken to reach 30 ft. Line of effect is stopped by `blocked`
squares only: smoke and fog obscure sight, not fire.

Pure functions: they read a `Scene` and never write one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import grid as gridmod

# The aim grammar (fix-interfaces §2.7). Directions are the map's axes and never reach
# prose: the world has no bearings (item 19.5), so a tell names what was aimed at.
AIM_PATTERN = (r"^(ref:[A-Za-z0-9_-]+|self|dir:(n|ne|e|se|s|sw|w|nw|up|down)"
               r"|point:\d+,\d+(,\d+)?|object:[^\n]{1,60})$")
_AIM = re.compile(AIM_PATTERN)

FLAT_DIRECTIONS = ("n", "ne", "e", "se", "s", "sw", "w", "nw")
DIRECTIONS = FLAT_DIRECTIONS + ("up", "down")

# The canopy's underside, in levels of five feet: 10 ft, the owner's ruling (Q32). The CRB
# describes forest canopy only as platforms "far above the surface floor" and gives no
# height, so this is a house rule. The top (30 ft) is unsourced as well.
CANOPY_FROM = 2
CANOPY_TO = 6

# What a place's ground has in it that a spell can be aimed at or can catch, keyed on the
# terrain words `floorplan.BY_TERRAIN` uses — never on a world's names (world-agnostic: a
# world with no forests still gets undergrowth wherever its ground is forest). Each
# feature is (where its cells come from, whether fire lights it).
#
#   difficult — the grid's difficult squares at ground level (undergrowth, reeds, hedge)
#   blocked   — the grid's blocked squares below the canopy (trunks, walls)
#   canopy    — every column from CANOPY_FROM to CANOPY_TO
#   ground    — every open square at ground level (a field of grass)
#
# Trunks do not burn from a brief flame: a typical trunk "has AC 4, hardness 5, and 150 hp"
# (CRB environment), and energy does half to objects before hardness (Smashing an Object,
# ID=126). Dry undergrowth, grass, hedge and a canopy do: Burning Hands' own text,
# "Flammable materials burn if the flames touch them".
FEATURES: dict[str, dict[str, tuple[str, bool]]] = {
    "forest": {"undergrowth": ("difficult", True), "trees": ("blocked", False),
               "canopy": ("canopy", True)},
    "jungle": {"undergrowth": ("difficult", True), "trees": ("blocked", False),
               "canopy": ("canopy", True)},
    "swamp": {"reeds": ("difficult", False), "trees": ("blocked", False)},
    "grassland": {"grass": ("ground", True)},
    "farmland": {"hedge": ("difficult", True), "walls": ("blocked", False)},
}

# The words a player uses for each feature. Checked against the player's own sentence by
# `aim_from_words`, so "burning hands into the tree tops" finds the canopy without a model.
FEATURE_WORDS: dict[str, tuple[str, ...]] = {
    "canopy": ("canopy", "tree tops", "treetops", "tree-tops", "branches", "boughs",
               "leaves", "the tops of the trees"),
    "trees": ("tree", "trees", "trunk", "trunks"),
    "undergrowth": ("undergrowth", "underbrush", "brush", "bushes", "scrub", "bracken",
                    "thicket"),
    "reeds": ("reeds", "rushes"),
    "grass": ("grass", "the field"),
    "hedge": ("hedge", "hedgerow", "hedges"),
    "walls": ("wall", "walls"),
}

# The materials fire lights outright: Smashing an Object's "Fire might do full damage
# against parchment, cloth" and the spell's own "flammable materials". Matched as whole
# words in a prop's name, what it was, and what it is made of.
FLAMMABLE = ("cloth", "parchment", "paper", "rope", "straw", "thatch", "oil", "hay",
             "canvas", "tinder", "kindling", "linen", "sackcloth", "scroll", "dry wood")

_UP_WORDS = re.compile(r"\b(?:up(?:ward|wards)?|overhead|into the sky|skyward|aloft)\b",
                       re.I)
_SELF_WORDS = re.compile(r"\b(?:myself|on me|at me|centred on me|centered on me)\b", re.I)

# The spells whose area lays a flat footprint rather than a volume.
_RADIUS_SHAPES = ("burst", "spread", "emanation", "radius", "cylinder")
_UNPARSED_RADIUS = re.compile(
    r"(\d+)\s*-?\s*(?:foot|ft\.?)\s*-?\s*(burst|spread|emanation)\b", re.I)


# --- the aim -------------------------------------------------------------------------------

@dataclass(frozen=True)
class Aim:
    """What a cast was aimed at: `kind` is ref | self | direction | point | object | none,
    `value` the ref, direction, "x,y[,z]" or the thing's words, `said` the words the tell
    uses for it."""
    kind: str = "none"
    value: str = ""
    said: str = ""

    def as_param(self) -> str:
        return {"ref": f"ref:{self.value}", "self": "self",
                "direction": f"dir:{self.value}", "point": f"point:{self.value}",
                "object": f"object:{self.value}"}.get(self.kind, "")

    def as_dict(self) -> dict:
        return {"kind": self.kind, "value": self.value, "said": self.said}

    def cell(self) -> tuple[int, ...] | None:
        if self.kind != "point":
            return None
        return tuple(int(v) for v in self.value.split(","))


def valid(text) -> bool:
    return isinstance(text, str) and bool(_AIM.match(text))


def parse_aim(text) -> Aim:
    """An aim param as an `Aim`. "" is no aim; anything else outside the grammar raises
    ValueError, so a caller refuses it rather than guessing what was meant."""
    s = str(text or "").strip()
    if not s:
        return Aim()
    if not _AIM.match(s):
        raise ValueError(f"{s!r} is not an aim")
    if s == "self":
        return Aim("self")
    head, _, rest = s.partition(":")
    kind = {"ref": "ref", "dir": "direction", "point": "point", "object": "object"}[head]
    if kind == "object":
        rest = " ".join(rest.lower().split())
        for word in ("the ", "a ", "an ", "into ", "at "):
            if rest.startswith(word):
                rest = rest[len(word):]
    return Aim(kind, rest)


def aim_of(params: dict, caster_ref: str = "") -> Aim:
    """The cast's aim, legacy params included: `aim` wins; `at` reads as `ref:<at>` (or
    `self` when it names the caster); `square` reads as `point:` when there is no aim."""
    params = params or {}
    if params.get("aim"):
        try:
            return parse_aim(params["aim"])
        except ValueError:
            return Aim()
    at = str(params.get("at") or "").strip()
    if at:
        # `at: "self"` is the aim grammar's own word for the caster written in the legacy
        # slot. Read as a ref it named nobody — and since G2 (2026-09-28) a ref nobody
        # holds is refused, where it used to resolve at nobody.
        return Aim("self") if at in (caster_ref, "self") else Aim("ref", at)
    square = params.get("square")
    if square not in (None, "", [], ()):
        return Aim("point", ",".join(str(int(v)) for v in tuple(square)))
    return Aim()


# --- the spell's shape -----------------------------------------------------------------------

def shape_of(spell, caster_level: int) -> dict:
    """The spell's area as a shape and a length in feet, or {} when it has none the grid
    can draw ("see text", a wall, an effect that is a created thing).

    From the printed `area` line only. A cone's length is its range: "Range 15 ft., Area
    cone-shaped burst" is the whole of Burning Hands, and `parse_area` rightly refuses to
    invent a length from the area line — so it is read here from `range_feet`. "30-foot
    burst" (no "radius") is read too; `parse_area` missed eleven spells like it.
    """
    from . import spells as spells_mod

    text = str(getattr(spell, "area", "") or "").strip()
    if not text:
        return {}
    parsed = spells_mod.parse_area(text)
    shape = str(parsed.get("shape") or "")
    out: dict = {}
    if shape in _RADIUS_SHAPES and parsed.get("radius"):
        out = {"shape": shape, "length_ft": int(parsed["radius"])}
    elif shape == "cone":
        reach = spells_mod.range_feet(spell, caster_level)
        if reach:
            out = {"shape": "cone", "length_ft": int(reach)}
    elif shape in ("line", "cube", "square") and parsed.get("length"):
        out = {"shape": shape, "length_ft": int(parsed["length"])}
    else:
        m = _UNPARSED_RADIUS.search(text)
        if m:
            out = {"shape": m.group(2).lower(), "length_ft": int(m.group(1))}
    if out and parsed.get("origin") == "you":
        out["on_you"] = True
    return out


# --- the area --------------------------------------------------------------------------------

@dataclass(frozen=True)
class Area:
    """A laid area. `origin` is the intersection it was measured from (x, y, level), or the
    caster's cell for a line; `cells` the (x, y, z) cells it covers after line of effect.
    `measured` is False where there is no map (theatre of the mind: membership by the aim
    alone). `fell_short` is True when the thing aimed at is not in it."""
    shape: str = "none"
    length_ft: int = 0
    origin: tuple = ()
    direction: str = ""
    cells: frozenset = field(default_factory=frozenset)
    measured: bool = False
    aim: Aim = field(default_factory=Aim)
    fell_short: bool = False

    def as_dict(self) -> dict:
        """The register's shape (§2.7): the cell COUNT on the outcome; `squares` carries the
        cells for the map overlay (`/api/state` `scene.grid.areas`), never for a tell."""
        out = {"shape": self.shape, "length_ft": self.length_ft,
               "origin": list(self.origin), "cells": len(self.cells),
               "measured": self.measured}
        if self.cells:
            out["squares"] = [list(c) for c in sorted(self.cells)]
        return out


def _level_of(scene, pos) -> int:
    if len(tuple(pos)) > 2:
        return int(pos[2])
    return scene.grid.ground(tuple(pos[:2])) if scene.grid is not None else 0


def _feet(dx: int, dy: int, dz: int = 0) -> int:
    """Feet for a far-corner separation of so many squares on each axis (5-10-5)."""
    return gridmod._count(abs(dx), abs(dy), abs(dz))


def burst_cells(origin, radius_ft: int, scene=None) -> set[tuple[int, int, int]]:
    """A burst, emanation or spread's cells from an intersection: every cell whose far
    corner is within the radius, counted intersection to intersection.

    `origin` is (x, y) or (x, y, level): the intersection at the top-left corner of cell
    (x, y), at the bottom of `level`. Measured on an empty floor: 44 cells on the ground
    for 20 ft, 12 for 10 ft, 4 for 5 ft — where `grid.burst` gave 61, 21 and 9.
    Nothing is kept below the floor under it (`scene.grid.ground`) or below level 0.
    """
    ox, oy = int(origin[0]), int(origin[1])
    oz = int(origin[2]) if len(tuple(origin)) > 2 else 0
    r = max(0, int(radius_ft)) // gridmod.SQUARE_FT
    out: set[tuple[int, int, int]] = set()
    for dx in range(-r, r):
        fx = dx + 1 if dx >= 0 else -dx
        for dy in range(-r, r):
            fy = dy + 1 if dy >= 0 else -dy
            floor = scene.grid.ground((ox + dx, oy + dy)) if (
                scene is not None and scene.grid is not None) else 0
            for dz in range(-r, r):
                fz = dz + 1 if dz >= 0 else -dz
                z = oz + dz
                if z < max(0, floor):
                    continue
                if _feet(fx, fy, fz) <= radius_ft:
                    out.add((ox + dx, oy + dy, z))
    return out


def _corner_of(square, step) -> tuple[int, int]:
    """The corner of a square that faces a diagonal step."""
    return (square[0] + (1 if step[0] > 0 else 0), square[1] + (1 if step[1] > 0 else 0))


def cone_corners(square, direction: str) -> list[tuple[int, int]]:
    """The intersections a cone in this direction may start from: the one corner facing a
    diagonal, the two corners on the facing side for a straight direction."""
    sx, sy = gridmod.DIRECTIONS[direction]
    x, y = int(square[0]), int(square[1])
    if sx and sy:
        return [_corner_of((x, y), (sx, sy))]
    if sx:
        edge = x + (1 if sx > 0 else 0)
        return [(edge, y), (edge, y + 1)]
    edge = y + (1 if sy > 0 else 0)
    return [(x, edge), (x + 1, edge)]


def _cone_flat(corner, direction: str, length_ft: int) -> dict[tuple[int, int], tuple]:
    """A horizontal cone's squares from one corner, each with its far-corner offsets
    (along, across) so the vertical can be laid by the same count. The quarter-circle,
    by the far-corner rule: a diagonal 15-ft cone is 6 squares (`grid.cone` gave 12), a
    straight one 8 (`grid.cone` gave 11)."""
    sx, sy = gridmod.DIRECTIONS[direction]
    X, Y = corner
    n = max(0, int(length_ft)) // gridmod.SQUARE_FT
    out: dict[tuple[int, int], tuple] = {}
    if sx and sy:
        for a in range(1, n + 1):
            for b in range(1, n + 1):
                if _feet(a, b) > length_ft:
                    continue
                cx = X + (a - 1) if sx > 0 else X - a
                cy = Y + (b - 1) if sy > 0 else Y - b
                out[(cx, cy)] = (max(a, b), a, b)
        return out
    for a in range(1, n + 1):
        for r in range(-a, a):
            across = r + 1 if r >= 0 else -r
            if _feet(a, across) > length_ft:
                continue
            if sx:
                cx = X + (a - 1) if sx > 0 else X - a
                cy = Y + r
            else:
                cy = Y + (a - 1) if sy > 0 else Y - a
                cx = X + r
            out[(cx, cy)] = (a, a, across)
    return out


def cone_cells(scene, square, level: int, direction: str, length_ft: int,
               corner=None, height: int = 1) -> tuple[set, tuple]:
    """A cone's cells and the corner it was laid from.

    Horizontal cones are the quarter-circle on the flat, extruded up (and down, never below
    the floor) no wider than their depth — a house rule, since the CRB gives cones no
    vertical. `up` and `down` build the same wedge about the vertical axis, starting at the
    caster's head or feet."""
    x, y = int(square[0]), int(square[1])
    n = max(0, int(length_ft)) // gridmod.SQUARE_FT
    cells: set = set()
    if direction in ("up", "down"):
        top = level + max(1, int(height))
        for dz in range(1, n + 1):
            z = top + dz - 1 if direction == "up" else level - dz
            if z < 0:
                break
            for hx in range(-(dz - 1), dz):
                for hy in range(-(dz - 1), dz):
                    if _feet(hx, hy, dz) <= length_ft:
                        cells.add((x + hx, y + hy, z))
        return cells, (x, y, top if direction == "up" else level)
    corners = [tuple(corner)] if corner else cone_corners((x, y), direction)
    corner = corners[0]
    flat = _cone_flat(corner, direction, length_ft)
    for (cx, cy), (depth, a, b) in flat.items():
        floor = scene.grid.ground((cx, cy)) if scene.grid is not None else 0
        for k in range(0, depth):
            far = k + 1
            if _feet(a, b, far) > length_ft:
                break
            cells.add((cx, cy, level + k))
            if k and level - k >= max(0, floor):
                cells.add((cx, cy, level - k))
    return cells, (corner[0], corner[1], level)


def line_cells(scene, square, level: int, towards, length_ft: int) -> tuple[set, tuple]:
    """A line from the corner of the caster's square nearest the aim, through every square
    whose interior it crosses, to its length or the first barrier — "until it strikes a
    barrier that blocks line of effect" (Aiming a Spell). Length is counted in the
    continuous form of 5-10-5 (the long axis plus half the short), so a diagonal bolt is
    not longer than a straight one. A line that climbs interpolates its level, as
    `grid.line` does."""
    x, y = int(square[0]), int(square[1])
    tx, ty = float(towards[0]) + 0.5, float(towards[1]) + 0.5
    tz = float(towards[2]) if len(tuple(towards)) > 2 else float(level)
    corners = [(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)]
    ox, oy = min(corners, key=lambda c: (c[0] - tx) ** 2 + (c[1] - ty) ** 2)
    dx, dy = tx - ox, ty - oy
    if not dx and not dy:
        return set(), (ox, oy, level)
    per = max(abs(dx), abs(dy)) + min(abs(dx), abs(dy)) / 2
    reach = length_ft / gridmod.SQUARE_FT
    scale = reach / per
    ex, ey = ox + dx * scale, oy + dy * scale
    rise = (tz - level) * scale
    steps = int(max(abs(ex - ox), abs(ey - oy)) * 16) + 1
    cells: set = set()
    for i in range(1, steps + 1):
        t = i / steps
        px, py = ox + (ex - ox) * t, oy + (ey - oy) * t
        if _on_seam(px) or _on_seam(py):
            continue
        cell2 = (int(px // 1), int(py // 1))
        if scene.grid is not None and not scene.grid.inside(cell2):
            break
        if scene.grid is not None and cell2 in scene.grid.blocked:
            break
        if cell2 == (x, y):
            continue
        cells.add((cell2[0], cell2[1], int(round(level + rise * t))))
    return cells, (ox, oy, level)


def _on_seam(v: float) -> bool:
    return abs(v - round(v)) < 1e-9


def _squares_at(x: float, y: float) -> list[tuple[int, int]]:
    xs = [int(round(x)) - 1, int(round(x))] if _on_seam(x) else [int(x // 1)]
    ys = [int(round(y)) - 1, int(round(y))] if _on_seam(y) else [int(y // 1)]
    return [(cx, cy) for cx in xs for cy in ys]


def _clear(scene, a, b, ignore) -> bool:
    """A straight, unblocked path (line of effect), `blocked` squares only.

    Not `Grid.line_of_sight`, which treats `obscuring` as opaque: smoke and fog stop sight
    and never stop a fireball. The seam rule is the grid's own: a line grazing a solid
    square's edge gets through unless both squares on the seam are solid."""
    blocked = scene.grid.blocked
    steps = max(1, int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 8) + 1)
    for i in range(steps + 1):
        t = i / steps
        x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        here = [s for s in _squares_at(x, y) if s not in ignore]
        if here and all(s in blocked for s in here):
            return False
    return True


def _with_effect(scene, origin, cells) -> set:
    """Keep the cells the origin has line of effect to: any clear line from the origin
    intersection to a corner of the square."""
    if scene.grid is None or not scene.grid.blocked:
        return set(cells)
    o = (float(origin[0]), float(origin[1]))
    keep: set = set()
    verdict: dict = {}
    for c in cells:
        col = (c[0], c[1])
        if col not in verdict:
            corners = [(col[0], col[1]), (col[0] + 1, col[1]), (col[0], col[1] + 1),
                       (col[0] + 1, col[1] + 1)]
            verdict[col] = any(_clear(scene, o, k, ignore={col}) for k in corners)
        if verdict[col]:
            keep.add(c)
    return keep


def _flooded(scene, origin, cells) -> set:
    """A spread "can turn corners": the burst's cells joined to the origin through open
    ground, rather than those in a straight line from it. The length is not re-measured
    around the corner — a simplification, said here."""
    if scene.grid is None or not scene.grid.blocked:
        return set(cells)
    cols = {(c[0], c[1]) for c in cells}
    ox, oy = int(origin[0]), int(origin[1])
    start = [s for s in ((ox - 1, oy - 1), (ox, oy - 1), (ox - 1, oy), (ox, oy))
             if s in cols and s not in scene.grid.blocked]
    seen, todo = set(start), list(start)
    while todo:
        here = todo.pop()
        for dx, dy in gridmod.DIRECTIONS.values():
            there = (here[0] + dx, here[1] + dy)
            if there in cols and there not in seen and there not in scene.grid.blocked:
                seen.add(there)
                todo.append(there)
    return {c for c in cells if (c[0], c[1]) in seen}


# --- what is where ---------------------------------------------------------------------------

def terrain_here(scene) -> str:
    from . import places as places_mod

    return places_mod.terrain_of(getattr(scene, "at", "") or "")


def features_here(scene) -> dict[str, frozenset]:
    """Feature word -> the cells it fills here, from the place's own terrain and its map.
    Without a map the features are still known (empty cells), so "into the canopy" still
    finds the canopy and lands in the fiction only."""
    table = FEATURES.get(terrain_here(scene), {})
    g = getattr(scene, "grid", None)
    out: dict[str, frozenset] = {}
    for name, (source, _burns) in table.items():
        if g is None:
            out[name] = frozenset()
            continue
        if source == "difficult":
            cells = {(x, y, g.ground((x, y))) for (x, y) in g.difficult if g.inside((x, y))}
        elif source == "blocked":
            cells = {(x, y, z) for (x, y) in g.blocked if g.inside((x, y))
                     for z in range(g.ground((x, y)), g.ground((x, y)) + CANOPY_FROM)}
        elif source == "canopy":
            cells = {(x, y, g.ground((x, y)) + z) for x in range(g.width)
                     for y in range(g.height) for z in range(CANOPY_FROM, CANOPY_TO)}
        else:
            cells = {(x, y, g.ground((x, y))) for x in range(g.width)
                     for y in range(g.height) if (x, y) not in g.blocked}
        if cells:
            out[name] = frozenset(cells)
    return out


def _flammable(rec: dict) -> bool:
    about = " ".join(str(rec.get(k, "") or "") for k in ("name", "from_", "material")).lower()
    return any(re.search(r"\b" + re.escape(w) + r"\b", about) for w in FLAMMABLE)


def is_fire(spell) -> bool:
    return str(getattr(spell, "element", "") or "").lower() == "fire"


def find_object(scene, words: str) -> dict | None:
    """The feature or unheld prop here that the words name, or None: {"kind", "name",
    "cells"} for a feature, {"kind", "name", "square", "rec"} for a prop."""
    said = " ".join(str(words or "").lower().replace("-", " ").split())
    if not said:
        return None
    name = _feature_in(scene, said)
    if name:
        return {"kind": "feature", "name": name,
                "cells": features_here(scene).get(name, frozenset())}
    for rec in scene.props_here() if hasattr(scene, "props_here") else []:
        name = str(rec.get("name", "")).lower()
        if name and (name == said or name in said or said in name):
            return {"kind": "prop", "name": rec.get("name", ""), "square":
                    rec.get("square"), "rec": rec}
    return None


def _feature_in(scene, words: str) -> str:
    """The feature here the words name, by the LONGEST word that matches — "tree tops" is
    the canopy, not the trees its first word also names. "" for none."""
    said = " ".join(str(words or "").lower().replace("-", " ").split())
    best, best_len = "", 0
    for name in FEATURES.get(terrain_here(scene), {}):
        for w in (name,) + FEATURE_WORDS.get(name, ()):
            w = w.replace("-", " ")
            if len(w) > best_len and re.search(r"\b" + re.escape(w) + r"\b", said):
                best, best_len = name, len(w)
    return best


def objects_here(scene) -> list[str]:
    """What a spell can be aimed at here besides people, in words — for a refusal that
    names what is here (the classbuilder's style)."""
    names = list(FEATURES.get(terrain_here(scene), {}))
    names += [str(r.get("name", "")) for r in (scene.props_here()
                                               if hasattr(scene, "props_here") else [])]
    return [n for n in names if n]


# --- laying it -------------------------------------------------------------------------------

def _target_cells(scene, ref) -> set:
    a = scene.actors.get(ref)
    pos = scene.positions.get(ref)
    if a is None or pos is None or scene.grid is None:
        return set()
    return set(gridmod.volume(tuple(pos[:2]), a.size or "medium", _level_of(scene, pos)))


def _order_towards(src, dst) -> list[str]:
    """The eight map directions, nearest the bearing to `dst` first."""
    import math

    vx, vy = dst[0] - src[0], dst[1] - src[1]
    if not vx and not vy:
        return list(FLAT_DIRECTIONS)
    want = math.atan2(vy, vx)

    def off(d):
        sx, sy = gridmod.DIRECTIONS[d]
        diff = abs(math.atan2(sy, sx) - want) % (2 * math.pi)
        return min(diff, 2 * math.pi - diff)
    return sorted(FLAT_DIRECTIONS, key=off)


def lay(scene, caster_ref: str, spell, caster_level: int, aim: Aim) -> Area:
    """Lay the spell's area from the caster and the aim. Pure.

    A cone or line aimed at a creature, a thing or a point takes the direction (and the
    corner) whose area contains it, nearest the bearing first; a burst aimed at a creature
    centres on the corner of its space nearest the caster. With no map the area is not
    measured and holds no cells."""
    shape = shape_of(spell, caster_level)
    if not shape:
        return Area(aim=aim)
    kind, length = shape["shape"], int(shape["length_ft"])
    caster = scene.actors.get(caster_ref)
    pos = scene.positions.get(caster_ref) if caster is not None else None
    if scene.grid is None or pos is None:
        return Area(shape=kind, length_ft=length, aim=aim, measured=False)
    square = (int(pos[0]), int(pos[1]))
    level = _level_of(scene, pos)
    height = gridmod.height_squares(caster.size or "medium")
    wanted: set = set()
    point = None
    if aim.kind == "ref":
        wanted = _target_cells(scene, aim.value)
        tpos = scene.positions.get(aim.value)
        if tpos is not None:
            point = (int(tpos[0]), int(tpos[1]), _level_of(scene, tpos))
    elif aim.kind == "object":
        found = find_object(scene, aim.value)
        if found and found["kind"] == "feature":
            wanted = set(found["cells"])
        elif found and found.get("square"):
            sq = found["square"]
            wanted = {(int(sq[0]), int(sq[1]), scene.grid.ground(tuple(sq)))}
        if wanted:
            point = min(wanted, key=lambda c: gridmod.distance(
                (square[0], square[1], level), c))
    elif aim.kind == "point":
        c = aim.cell()
        point = (c[0], c[1], c[2] if len(c) > 2 else scene.grid.ground(c[:2]))
    elif aim.kind == "self":
        point = (square[0], square[1], level)

    if kind == "cone":
        options: list[tuple[str, object]] = []
        if aim.kind == "direction":
            options = [(aim.value, None)]
        elif point is not None:
            if aim.kind == "object" and point[2] >= level + height:
                options.append(("up", None))
            for d in _order_towards(square, point):
                options += [(d, c) for c in cone_corners(square, d)]
            options.append(("up", None))
        if not options:
            return Area(shape=kind, length_ft=length, aim=aim, measured=True)
        best = None
        for d, corner in options:
            cells, origin = cone_cells(scene, square, level, d, length, corner, height)
            if d not in ("up", "down"):
                cells = _with_effect(scene, origin, cells)
            if best is None:
                best = (d, cells, origin)
            if not wanted or cells & wanted:
                best = (d, cells, origin)
                break
        d, cells, origin = best
        cells = {c for c in cells if scene.grid.inside(c[:2])}
        return Area(shape=kind, length_ft=length, origin=tuple(origin), direction=d,
                    cells=frozenset(cells), measured=True, aim=aim,
                    fell_short=bool(wanted) and not (cells & wanted))
    if kind == "line":
        if aim.kind == "direction" and aim.value in gridmod.DIRECTIONS:
            sx, sy = gridmod.DIRECTIONS[aim.value]
            n = length // gridmod.SQUARE_FT + 1
            point = (square[0] + sx * n, square[1] + sy * n, level)
        if point is None:
            return Area(shape=kind, length_ft=length, aim=aim, measured=True)
        cells, origin = line_cells(scene, square, level, point, length)
        return Area(shape=kind, length_ft=length, origin=tuple(origin), cells=frozenset(cells),
                    measured=True, aim=aim,
                    fell_short=bool(wanted) and not (cells & wanted))
    # A radius, a cube or a square: from an intersection.
    if shape.get("on_you"):
        point = (square[0], square[1], level)
    if point is None:
        return Area(shape=kind, length_ft=length, aim=aim, measured=True)
    ox, oy = point[0], point[1]
    if aim.kind in ("ref", "object") and not shape.get("on_you"):
        # The corner of the space nearest the caster: the burst still contains the
        # creature (a square touching the origin is 5 ft in), and the choice is
        # deterministic rather than left to whoever reads the map.
        corners = [(point[0] + dx, point[1] + dy) for dx in (0, 1) for dy in (0, 1)]
        ox, oy = min(corners, key=lambda c: ((c[0] - square[0] - 0.5) ** 2
                                             + (c[1] - square[1] - 0.5) ** 2, c))
    origin = (ox, oy, point[2])
    if kind in ("cube", "square"):
        n = max(1, length // gridmod.SQUARE_FT)
        cells = {(ox + dx, oy + dy, point[2] + dz) for dx in range(n) for dy in range(n)
                 for dz in range(n if kind == "cube" else 1)}
    elif kind == "cylinder":
        flat = {(c[0], c[1]) for c in burst_cells((ox, oy, point[2]), length, scene)}
        cells = {(x, y, z) for (x, y) in flat
                 for z in range(scene.grid.ground((x, y)), point[2] + 1)}
    else:
        cells = burst_cells(origin, length, scene)
        cells = _flooded(scene, origin, cells) if kind == "spread" \
            else _with_effect(scene, origin, cells)
    cells = {c for c in cells if scene.grid.inside(c[:2])}
    return Area(shape=kind, length_ft=length, origin=origin, cells=frozenset(cells),
                measured=True, aim=aim, fell_short=bool(wanted) and not (cells & wanted))


def caught(scene, area: Area, *, exclude=()) -> list[str]:
    """The creatures in the area: any cell of a creature's volume in the area's cells —
    the far-edge rule applied to footprints, since a cell is wholly in or wholly out. A
    burst "affects whatever it catches in its area, including creatures that you can't
    see", so the hidden are caught too. The dead are not creatures any more.

    Unmeasured (no map): the creature the aim named, and nobody else."""
    if not area.measured:
        if area.aim.kind == "ref" and area.aim.value in scene.actors \
                and area.aim.value not in exclude:
            return [area.aim.value]
        return []
    out = []
    for ref, actor in scene.actors.items():
        if ref in exclude or actor.has_state("state.down.dead"):
            continue
        if _target_cells(scene, ref) & area.cells:
            out.append(ref)
    return out


def objects_caught(scene, area: Area, spell) -> list[dict]:
    """The things in the area: unheld props lying here and the ground's features.
    Attended objects are not listed — carried and worn items "are assumed to survive a
    magical attack" unless the spell says otherwise (CRB magic chapter).

    Without a map, the thing the aim named, when it is here (in the fiction only)."""
    fire = is_fire(spell)
    table = FEATURES.get(terrain_here(scene), {})
    out: list[dict] = []
    if not area.measured:
        if area.aim.kind == "object":
            found = find_object(scene, area.aim.value)
            if found and found["kind"] == "feature":
                out.append({"kind": "feature", "name": found["name"], "cells": 0,
                            "burns": fire and table.get(found["name"], ("", False))[1]})
            elif found:
                out.append({"kind": "prop", "name": found["name"],
                            "burns": fire and _flammable(found["rec"])})
        return out
    cols = {(c[0], c[1]) for c in area.cells}
    for rec in scene.props_here() if hasattr(scene, "props_here") else []:
        sq = rec.get("square")
        if sq is not None and (int(sq[0]), int(sq[1])) in cols:
            out.append({"kind": "prop", "name": rec.get("name", ""),
                        "square": [int(sq[0]), int(sq[1])],
                        "burns": fire and _flammable(rec)})
    for name, cells in features_here(scene).items():
        hit = cells & area.cells
        if hit:
            out.append({"kind": "feature", "name": name, "cells": len(hit),
                        "burns": fire and table.get(name, ("", False))[1],
                        "at": [list(c) for c in sorted(hit)]})
    return out


# --- grounding an aim without a model --------------------------------------------------------

_STOP = frozenset({"the", "a", "an", "in", "of", "with", "and", "at", "to", "on", "by",
                   "his", "her", "their", "its", "from"})


def _name_words(name: str) -> list[str]:
    return [w for w in re.findall(r"[a-z']+", str(name or "").lower())
            if len(w) >= 3 and w not in _STOP]


def aim_from_words(scene, caster_ref: str, words: str, spell=None) -> str | None:
    """An aim from the player's own sentence, deterministically, or None.

    A person present named in full, or by a word of their name no one else here shares →
    `ref:`; the caster → `self`; a feature or prop here ("tree tops" → the canopy) →
    `object:`; "up", "overhead" → `dir:up`. Checked in that order, so "at the man by the
    trees" is the man."""
    said = " ".join(str(words or "").lower().split())
    if not said:
        return None
    others = [(r, a) for r, a in scene.actors.items()
              if r != caster_ref and a.name and not a.has_state("state.down.dead")]
    for ref, actor in others:
        if actor.name.lower() in said:
            return f"ref:{ref}"
    counts: dict[str, list[str]] = {}
    for ref, actor in others:
        for w in set(_name_words(actor.name)):
            counts.setdefault(w, []).append(ref)
    for w, refs in counts.items():
        if len(refs) == 1 and re.search(r"\b" + re.escape(w) + r"\b", said):
            return f"ref:{refs[0]}"
    if _SELF_WORDS.search(said):
        return "self"
    feature = _feature_in(scene, said)
    if feature:
        return f"object:{feature}"
    for rec in scene.props_here() if hasattr(scene, "props_here") else []:
        name = str(rec.get("name", "")).lower()
        if name and re.search(r"\b" + re.escape(name) + r"\b", said):
            return f"object:{name}"[:67]
    if _UP_WORDS.search(said):
        return "dir:up"
    return None


def legal_aims(scene, caster_ref: str, spell=None) -> list[str]:
    """Every aim the spell could take here — the enum a model chooses from, so it cannot
    invent one (I3 wires it into the plan's schema): the people present, the caster, the
    features and props here, and straight up."""
    out = [f"ref:{r}" for r, a in scene.actors.items()
           if r != caster_ref and not a.has_state("state.down.dead")]
    out.append("self")
    out += [f"object:{n}"[:67] for n in objects_here(scene)]
    out.append("dir:up")
    return [a for a in out if valid(a)]


__all__ = [
    "AIM_PATTERN", "Aim", "Area", "CANOPY_FROM", "FEATURES", "aim_from_words", "aim_of",
    "burst_cells", "caught", "cone_cells", "features_here", "find_object", "lay",
    "legal_aims", "line_cells", "objects_caught", "objects_here", "parse_aim", "shape_of",
    "valid",
]
