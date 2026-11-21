"""Hex travel on the region map: the 12-mile hex as engine state (docs/hexcrawl-plan.md).

The Region map (play/static/js/places-board.js) drew its hexes in the browser, from a layout
the browser worked out (16-places-world.js `worldLayout`). Nothing in the engine knew a hex
existed, so nothing could move a party across one, charge the hours, or remember what was
found there. This module is the grid the engine owns; the board now draws it.

**The layout** is `worldLayout` ported line for line: no coordinates come in the export
(World Bible ask 1; ask 33 asks for them), so each continent is a quadrant and a seeded
spring pass over the land roads places its towns. It is computed once and **stored in the
save** (`Scene.hexes["layout"]`, stamped with `LAYOUT_VERSION`): a campaign names its world by
path, the world can be re-exported under it, and a town added to the export would move every
town and every hex under the player's feet (CLAUDE.md: version-stamp what outlives a build).
A town the stored layout lacks takes its place from a fresh pass; nothing already placed
moves. The browser draws from the same stored positions (`/api/atlas` carries them), so the
board cannot disagree with the engine by a floating-point hair.

**The grid** is world-wide axial `(q, r)`, pointy-top, its circumradius six miles (Ultimate
Campaign's 12-mile hex, corner to corner), anchored at the layout's origin, so every region
map is a window onto one grid and a hex is the same hex whichever nation's map shows it.

**Ground by rule** is the Region map's own reading, moved here so the engine and the board
read one answer (`ground`): a hex along a road takes what the road crosses there
(`geography`'s `crosses`), the ring round a town its near ground, further out now and then
its ground beyond, and each named reach (`geography.Reach`) a patch at its miles, in the
direction furthest from every road out. A reach with no hex of its own ground near its town
takes the nearest free hex of its nation, so the woods a player can walk to stand on a forest
hex. Everything else is grassland, as the board always drew it.

**Sites** (plan §5, "never nothing; about one in three holds a site"): a hex's site is rolled
once from the world's name and `(q, r)` (Daggerfall's re-roll farming is the defect a seed
prevents), as a KIND only, and opened through the venture door that already builds caves,
mines, ruins and towers with their dungeon story (`places.VENTURES`, `rules/dungeons.py`).

What this module refuses, with reasons (plan, prior art): no fixed "explore for two days"
block (the owner's ruling 2: moving is the only time that passes on its own); no second
encounter roller (the travel door's `ontheway.road` checks the hours of every hex); no
authored numbers from a model (the XP is `rule:hex-explored`).
"""
from __future__ import annotations

import hashlib
import math
import re

from . import biomes

LAYOUT_VERSION = 1
# The grid's scale. 1: a hex is twelve of the world's raw road miles (0.4.4-0.4.6). 2: the
# board is drawn no smaller than the roads' own journey times (`Grid._fit`), so walking
# the hexes between two towns is never quicker than the road (docs/research/2026-11-21-
# hex-scale.md). A save of an older scale is re-keyed on load (`mend_save`).
GRID_VERSION = 2
# The coast. 1: every coastal town has its channel down to the sea (`Grid._chart_channels`,
# feat/sea-hexes 2026-11-21). A save from before it whose party stands on a hex the channel
# now covers is stood on the nearest land on load (`mend_save`).
COAST_VERSION = 1
HEX_MILES = 12
# How far out from a nation's coast its Region map draws the sea, in hexes.
WATER_RING = 6
SQRT3 = math.sqrt(3)
# The six neighbours, in the board's order (places-board.js `HEX_DIRS`).
DIRS = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))

# Ultimate Campaign, Exploration: travel through one hex at speed 30 takes 5 hours on plain,
# 8 on anything else. Grassland and farmland are the plain.
PLAIN = frozenset({"grassland", "farmland"})
HOURS_PLAIN, HOURS_ROUGH = 5, 8
# The same table's other speeds (Ultimate Campaign Table 3-2, aonprd Rules ID 1376, read
# 2026-11-21): (speed, plain, all other). The party's speed is its slowest member's; a
# speed between rows takes the slower row. Until 2026-11-21 every speed walked a hex in
# the 30-foot hours, so a 20-foot party crossed the board faster than its road.
HOURS_BY_SPEED = ((15, 11, 16), (20, 8, 12), (30, 5, 8), (40, 4, 6), (50, 3, 5))
# +25 XP for difficult terrain (UC). Our reading of "difficult": the ground the CRB's
# overland table slows (Table 7-8: forest, jungle, swamp, mountain).
DIFFICULT = frozenset({"forest", "jungle", "swamp", "mountain"})
EXPLORED_XP, DIFFICULT_XP = 100, 25
# A hex with no site counts as explored once the party has spent an hour there doing
# something (owner call 1, answered by default 2026-11-19).
EXPLORE_MINUTES = 60


# --- the layout ---------------------------------------------------------------------------

def layout(atlas: dict) -> dict:
    """`worldLayout` (16-places-world.js), ported line for line: {"pos": {city: [x, y]},
    "centre": {continent: [x, y]}, "half": float}. Deterministic for a world."""
    conts = sorted((atlas.get("continents") or {}).keys())
    centre, R = {}, 300
    for k, c in enumerate(conts):
        ring, q = k // 4, k % 4
        centre[c] = [(1 if q % 2 else -1) * 380 * (1 + ring), (-1 if q < 2 else 1) * 330 * (1 + ring)]
    by_cont: dict[str, list] = {}
    for c in atlas.get("cities") or []:
        by_cont.setdefault(c["continent"], []).append(c)
    pos: dict[str, list] = {}
    land = [r for r in atlas.get("routes") or [] if r.get("by") != "sea"]
    for cont, lst in by_cont.items():
        lst = sorted(lst, key=lambda c: c["id"])
        nations = sorted({c["nation"] for c in lst})
        cx, cy = centre.get(cont, [0, 0])
        P = {}
        for k, c in enumerate(lst):
            n = nations.index(c["nation"])
            a = (n + .5) / len(nations) * math.pi * 2 + (k % 5) * .18
            r = R * (.35 + .12 * (k % 4))
            P[c["id"]] = [math.cos(a) * r, math.sin(a) * r]
        ids = [c["id"] for c in lst]
        here = set(ids)
        by_id = {c["id"]: c for c in lst}
        springs = [r for r in land if r["a"] in here and r["b"] in here]
        for _ in range(300):
            F = {i: [0.0, 0.0] for i in ids}
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    a, b = P[ids[i]], P[ids[j]]
                    dx, dy = a[0] - b[0], a[1] - b[1]
                    d2 = dx * dx + dy * dy + .01
                    d = math.sqrt(d2)
                    f = 2600 / d2
                    F[ids[i]][0] += dx / d * f
                    F[ids[i]][1] += dy / d * f
                    F[ids[j]][0] -= dx / d * f
                    F[ids[j]][1] -= dy / d * f
            for rt in springs:
                a, b = P[rt["a"]], P[rt["b"]]
                dx, dy = b[0] - a[0], b[1] - a[1]
                d = math.hypot(dx, dy) + .01
                f = (d - 70) * .03
                F[rt["a"]][0] += dx / d * f
                F[rt["a"]][1] += dy / d * f
                F[rt["b"]][0] -= dx / d * f
                F[rt["b"]][1] -= dy / d * f
            mid: dict[str, list] = {}
            for i in ids:
                m = mid.setdefault(by_id[i]["nation"], [0.0, 0.0, 0])
                m[0] += P[i][0]
                m[1] += P[i][1]
                m[2] += 1
            for i in ids:
                m = mid[by_id[i]["nation"]]
                F[i][0] += (m[0] / m[2] - P[i][0]) * .06
                F[i][1] += (m[1] / m[2] - P[i][1]) * .06
            for i in ids:
                p = P[i]
                d = math.hypot(p[0], p[1])
                if d > R:
                    F[i][0] -= p[0] / d * (d - R) * .2
                    F[i][1] -= p[1] / d * (d - R) * .2
                p[0] += max(-6, min(6, F[i][0]))
                p[1] += max(-6, min(6, F[i][1]))
        for i in ids:
            pos[i] = [cx + P[i][0], cy + P[i][1] * .8]
    half = max((max(abs(p[0]), abs(p[1])) for p in pos.values()), default=0) + 160
    return {"pos": pos, "centre": centre, "half": half}


def held_layout(scene, atlas: dict) -> dict:
    """The layout this campaign plays on: the stored one, topped up with any town the
    stored one lacks (placed by a fresh pass), else a fresh pass, stored. Returns
    {"v", "pos", "centre", "half"}."""
    store = scene.hexes if isinstance(getattr(scene, "hexes", None), dict) else {}
    held = store.get("layout") if isinstance(store.get("layout"), dict) else None
    ids = [c["id"] for c in atlas.get("cities") or []]
    if held and held.get("v") == LAYOUT_VERSION and all(i in (held.get("pos") or {}) for i in ids):
        return held
    fresh = layout(atlas)
    if held and held.get("v") == LAYOUT_VERSION:
        pos = dict(held.get("pos") or {})
        for i in ids:
            pos.setdefault(i, fresh["pos"][i])
        got = {"v": LAYOUT_VERSION, "pos": pos,
               "centre": {**fresh["centre"], **(held.get("centre") or {})},
               "half": max(float(held.get("half") or 0), fresh["half"])}
    else:
        got = {"v": LAYOUT_VERSION, **fresh}
    if isinstance(getattr(scene, "hexes", None), dict):
        if not held:
            # Laid out for the first time: nothing is keyed to an older grid.
            scene.hexes.setdefault("grid", GRID_VERSION)
            scene.hexes.setdefault("coast", COAST_VERSION)
        scene.hexes["layout"] = got
    return got


# --- the grid -----------------------------------------------------------------------------

def centre(q: int, r: int, size: float) -> tuple[float, float]:
    """The middle of hex (q, r), in layout units: pointy-top, circumradius `size`."""
    return size * SQRT3 * (q + r / 2), size * 1.5 * r


def hex_at(x: float, y: float, size: float) -> tuple[int, int]:
    """The hex a layout point falls in (cube rounding)."""
    rf = y / (1.5 * size)
    qf = x / (SQRT3 * size) - rf / 2
    sf = -qf - rf
    q, r, s = round(qf), round(rf), round(sf)
    dq, dr, ds = abs(q - qf), abs(r - rf), abs(s - sf)
    if dq > dr and dq > ds:
        q = -r - s
    elif dr > ds:
        r = -q - s
    return int(q), int(r)


def distance(a, b) -> int:
    dq, dr = a[0] - b[0], a[1] - b[1]
    return int((abs(dq) + abs(dr) + abs(dq + dr)) // 2)


def along(a, b, frac: float) -> tuple[int, int]:
    """The hex `frac` of the way from hex a to hex b, on the straight line between them:
    Red Blob Games' hex line drawing (redblobgames.com/grids/hexagons, cube lerp and
    round). For a journey stopped on the road (`Engine.party_hex`)."""
    n = distance(a, b)
    if not n:
        return (int(a[0]), int(a[1]))
    t = round(n * max(0.0, min(1.0, float(frac)))) / n
    q, r = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    if abs(rq - q) > abs(rr - r) and abs(rq - q) > abs(rs - s):
        rq = -rr - rs
    elif abs(rr - r) > abs(rs - s):
        rr = -rq - rs
    return (int(rq), int(rr))


def neighbours(q: int, r: int) -> list[tuple[int, int]]:
    return [(q + dq, r + dr) for dq, dr in DIRS]


def key(q: int, r: int) -> str:
    return f"{int(q)},{int(r)}"


def unkey(k: str) -> tuple[int, int]:
    a, b = str(k).split(",")
    return int(a), int(b)


def _js_round(x: float) -> int:
    """Math.round: halves go up (Python's round goes to even)."""
    return math.floor(x + .5)


def _seg_d(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy or 1
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _miles_per_unit(routes, pos) -> float:
    """Miles to a layout unit from the roads the world measured (the median): the scale
    of GRID_VERSION 1, and where `Grid._fit` starts from."""
    ratios = sorted(r["miles"] / (math.hypot(pos[r["a"]][0] - pos[r["b"]][0],
                                             pos[r["a"]][1] - pos[r["b"]][1]) or 1)
                    for r in routes if r.get("miles"))
    return ratios[len(ratios) >> 1] if ratios else 1.0


class Grid:
    """One world's hexes on one layout. Built once and remembered (`grid`)."""

    def __init__(self, atlas: dict, lay: dict, size: float | None = None,
                 channels: bool = True):
        self.atlas = atlas
        self.pos = lay["pos"]
        self.cities = [c for c in atlas.get("cities") or [] if c["id"] in self.pos]
        self.city = {c["id"]: c for c in self.cities}
        self.nations = atlas.get("nations") or {}
        self.routes = [r for r in atlas.get("routes") or []
                       if r.get("by") != "sea" and r["a"] in self.pos and r["b"] in self.pos]
        # Miles to a layout unit, from the roads the world measured (the median), so a hex
        # is twelve miles (places-board.js `nationMap`, which this replaces).
        self.miles_per_unit = _miles_per_unit(self.routes, self.pos)
        self.size = (HEX_MILES / 2) / self.miles_per_unit if size is None else float(size)
        # The land: `landAt`'s five discs round every city, in the atlas's city order.
        self.discs = []
        for n, c in enumerate(atlas.get("cities") or []):
            p = self.pos.get(c["id"])
            if not p:
                continue
            for k in range(5):
                a, rad = n * 1.7 + k * 1.26, 70 + (n * 37 + k * 13) % 40
                self.discs.append((p[0] + math.cos(a) * 30, p[1] + math.sin(a) * 30, rad))
        # The way down to the sea from every town on the coast (`_chart_channels`): none on
        # the grid a save of an older coast was played on (`mend_save` rebuilds that one).
        self._centres = lay.get("centre") or {}
        self.channels = self._chart_channels() if channels else []
        self._cells: dict = {}
        self._routes_of = {c["id"]: [r for r in self.routes
                                     if (r["a"] == c["id"] or r["b"] == c["id"]) and r.get("crosses")]
                           for c in self.cities}
        self._place_towns()
        if size is None:
            self._fit()
        self.patches = self._patches()

    def _place_towns(self) -> None:
        # A coastal town's own hex is never cut away by its channel: the hex its point falls
        # in, at this size (the size moves while `_fit` runs, so this is made with it).
        self._kept = {hex_at(*self.pos[c["id"]], self.size) for c in self.cities}
        self._land: dict = {}
        self.town_hex: dict[str, tuple] = {}
        self.towns_at: dict[tuple, list] = {}
        for c in sorted(self.cities, key=lambda c: c["id"]):
            h = self._town_hex(c)
            self.town_hex[c["id"]] = h
            self.towns_at.setdefault(h, []).append(c["id"])

    def _short(self) -> float:
        """How many times too few hexes the worst road has: its journey hours on foot at
        30 ft (`walk`, from `journey.hours_for` via the atlas) over the hours of the hexes
        between its towns at the quickest a hex goes (plain, 30 ft). 1 or less is fit."""
        worst = 0.0
        for r in self.routes:
            walk = float(r.get("walk") or 0)
            if walk <= 0:
                continue
            n = distance(self.town_hex[r["a"]], self.town_hex[r["b"]])
            worst = max(worst, walk / (HOURS_PLAIN * n) if n else walk / HOURS_PLAIN + 1)
        return worst

    def _fit(self) -> None:
        """Shrink the hex until walking the hexes between any two towns takes at least as
        long as their road (the owner, 2026-11-21: never quicker than the journey floor).

        The board's scale came from the world's raw road miles alone, so a 48-mile road
        the journey floors at three days was four hexes (20 hours) on plain: 56 of 190 land
        legs on the three exports were quicker by the hexes. Measured against the road's
        own hours, not its miles, so a floored road, a measured one and slow ground are all
        covered; only ever smaller, so no town is nearer than it was, and a save's hexes
        map one to one onto the new grid (`mend_save`). Plain at 30 ft is the quickest a
        hex goes (Table 3-2's ratios between speeds match the road's), so one check holds
        for every party."""
        for _ in range(60):
            short = self._short()
            if short <= 1:
                return
            self.size /= max(1.02, short * 1.01)
            self._cells.clear()
            self._place_towns()

    # The bare facts of a hex, before ground: land, the nearest town, its nation.
    def _land_at(self, x: float, y: float) -> bool:
        return any((x - cx) ** 2 + (y - cy) ** 2 < rad * rad for cx, cy, rad in self.discs)

    def _chart_channels(self) -> list[tuple]:
        """The water from every coastal town out to the open sea: [((x0, y0), (x1, y1))].

        The land is `landAt`'s discs round every town, seventy to a hundred and ten layout
        units across, and the hexes are a few units wide after `_fit`, so on the shipped
        exports not one port of 34 had a water hex within twelve hexes of it (measured
        2026-11-21: Aurvantis 23 ports, Pangrella 4, the owner's fantasia 7; the synthetic
        world's one port eleven hexes off). Nothing could put out from a quay. Until World
        Bible exports a coastline (ask 33), a town the world puts on the coast (`coast`
        in its near ground: a port, or the export's own coast fact) is given a firth: a
        channel of water two hexes wide from its gate, straight away from its continent's
        middle, to where the land stops. A line that would pass within thirty layout units
        (three to six hexes) of another town's point turns, twenty degrees at a time, up to eighty
        either way."""
        out = []
        towns = [self.pos[c["id"]] for c in self.cities]
        for c in sorted(self.cities, key=lambda c: c["id"]):
            if "coast" not in (c.get("near") or ()):
                continue
            p = self.pos[c["id"]]
            mid = self._centres.get(c.get("continent")) or [0.0, 0.0]
            base = math.atan2(p[1] - mid[1], p[0] - mid[0]) if p != mid else 0.0
            best = None
            for turn in (0, 20, -20, 40, -40, 60, -60, 80, -80):
                a = base + math.radians(turn)
                dx, dy = math.cos(a), math.sin(a)
                n = 1
                while n < 400 and self._land_at(p[0] + dx * n * 5, p[1] + dy * n * 5):
                    n += 1
                end = (p[0] + dx * (n * 5 + 10), p[1] + dy * (n * 5 + 10))
                seg = ((p[0], p[1]), end)
                clear = all(q is p or _seg_d(q, *seg) > 30 for q in towns)
                if best is None:
                    best = seg
                if clear:
                    best = seg
                    break
            out.append(best)
        return out

    def _in_channel(self, x: float, y: float, h) -> bool:
        if h in self._kept:
            return False
        # A hex's middle within its circumradius of the line: every hex the line crosses.
        w = self.size * 1.05
        return any(_seg_d((x, y), a, b) < w for a, b in self.channels)

    def _is_land(self, q: int, r: int) -> bool:
        """Land or water, alone: what the sea's inshore/open asks of six neighbours, without
        the nearest-town search `_base` makes (that made the region's water five times
        slower to read, measured 2026-11-21: 5.5 s for one Aurvantis nation against 1.0)."""
        k = (q, r)
        got = self._land.get(k)
        if got is None:
            x, y = centre(q, r, self.size)
            got = self._land_at(x, y) and not (self.channels and self._in_channel(x, y, k))
            if len(self._land) < 400_000:
                self._land[k] = got
        return got

    def _base(self, q: int, r: int) -> tuple:
        x, y = centre(q, r, self.size)
        land = self._is_land(q, r)
        best, near = 1e18, None
        for c in self.cities:
            p = self.pos[c["id"]]
            d = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d < best:
                best, near = d, c
        return x, y, land, near

    def _town_hex(self, c) -> tuple:
        """The hex a town stands on: the one its point falls in, or, when that is sea or
        another nation's, the nearest of its own nation's land within two hexes."""
        p = self.pos[c["id"]]
        h0 = hex_at(p[0], p[1], self.size)
        x, y, land, near = self._base(*h0)
        if land and near is not None and near["nation"] == c["nation"]:
            return h0
        best, got = 1e18, h0
        for dq in range(-2, 3):
            for dr in range(-2, 3):
                h = (h0[0] + dq, h0[1] + dr)
                if distance(h, h0) > 2:
                    continue
                x, y, land, near = self._base(*h)
                if land and near is not None and near["nation"] == c["nation"]:
                    d = (x - p[0]) ** 2 + (y - p[1]) ** 2
                    if d < best:
                        best, got = d, h
        return got

    def _road_ground(self, q, r, x, y, c) -> str:
        cx, cy = self.pos[c["id"]]
        dhex = math.hypot(x - cx, y - cy) / (self.size * SQRT3)
        for rt in self._routes_of.get(c["id"], ()):
            o = rt["b"] if rt["a"] == c["id"] else rt["a"]
            ox, oy = self.pos[o]
            if _seg_d((x, y), (cx, cy), (ox, oy)) > self.size * .9:
                continue
            L = math.hypot(ox - cx, oy - cy) or 1
            t = ((x - cx) * (ox - cx) + (y - cy) * (oy - cy)) / (L * L)
            if t < 0 or t > 1:
                continue
            cr = list(rt["crosses"]) if rt["a"] == c["id"] else list(reversed(rt["crosses"]))
            return cr[min(len(cr) - 1, math.floor(t * len(cr)))]
        if .5 < dhex < 1.6:
            near = [n for n in (c.get("near") or []) if n not in ("desert", "coast")]
            if near:
                return near[((q * 7 + r * 3) & 1023) % len(near)]
        if dhex >= 1.6:
            far = c.get("beyond") or []
            if far and ((q * 7 + r * 3) & 1023) % 4 == 0:
                return far[((q + r) & 1023) % len(far)]
            # The rest by the town's own ground (plan §2), in patches three hexes across so
            # a forest is a forest and not a speckle: measured 2026-11-19, the board's rule
            # alone left 350 of Aurvantis's first nation's 417 hexes grassland, and a
            # hexcrawl across one ground is the sameness the plan's risks name.
            mix = [n for n in (list(c.get("near") or []) + list(far))
                   if n not in ("coast", "urban") and biomes.canonical(n) not in (None, "water")]
            if mix:
                world = str(self.atlas.get("world") or "")
                pq, pr = q // 3, r // 3
                if _roll(world, pq, pr, "patch") % 2 == 0:
                    return mix[_roll(world, pq, pr, "ground") % len(mix)]
        return ""

    def _patches(self) -> dict:
        """The named reaches, each on a patch of its own ground (`nationMap`'s rule), and
        a reach that found no hex of its ground near its town given the nearest free one."""
        out: dict[tuple, str] = {}
        for c in self.cities:
            routes = self._routes_of.get(c["id"], ())
            h0 = self.town_hex[c["id"]]
            p = self.pos[c["id"]]
            taken = [math.atan2(self.pos[o][1] - p[1], self.pos[o][0] - p[0])
                     for rt in routes for o in [rt["b"] if rt["a"] == c["id"] else rt["a"]]]
            for rc in c.get("reaches") or []:
                if any((rt.get("crosses") or [None])[0] == rc["ground"] for rt in routes):
                    continue
                n = max(1, _js_round((float(rc.get("miles") or 0) + 6) / 12))
                scored = []
                for dq, dr in DIRS:
                    dx, dz = centre(dq, dr, 1)
                    ang = math.atan2(dz, dx)
                    score = min((abs(math.atan2(math.sin(ang - b), math.cos(ang - b))) for b in taken),
                                default=math.pi)
                    scored.append((score, (dq, dr)))
                best = max(s for s, _ in scored)
                dq, dr = next(d for s, d in scored if s == best)
                for eq, er in ((0, 0), (dq, dr)):
                    h = (h0[0] + dq * n + eq, h0[1] + dr * n + er)
                    _x, _y, land, near = self._base(*h)
                    if land and near is not None and near["nation"] == c["nation"] \
                            and h not in self.towns_at:
                        out[h] = rc["ground"]
        # Every reach on a hex of its own ground within three of its town.
        for c in sorted(self.cities, key=lambda c: c["id"]):
            h0 = self.town_hex[c["id"]]
            ring = [h for h in _spiral(h0, 3) if h != h0]
            for rc in c.get("reaches") or []:
                g = rc["ground"]
                if any(self._ground_no_fallback(h, out) == g for h in ring):
                    continue
                for h in ring:
                    if h in out or h in self.towns_at:
                        continue
                    _x, _y, land, near = self._base(*h)
                    if land and near is not None and near["nation"] == c["nation"]:
                        out[h] = g
                        break
        return out

    def _ground_no_fallback(self, h, patches) -> str:
        if h in patches:
            return patches[h]
        x, y, land, near = self._base(*h)
        if not land or near is None:
            return ""
        return self._road_ground(h[0], h[1], x, y, near)

    @property
    def sea_miles(self) -> float:
        """The miles a water hex stands for: twelve, or more where the board's sea is
        narrower than the passages across it (`sea_hex_miles`)."""
        got = getattr(self, "_sea_miles", None)
        if got is None:
            got = self._sea_miles = sea_hex_miles(self.atlas, self.town_hex)
        return got

    def cell(self, q: int, r: int) -> dict:
        """{"q", "r", "land", "sea": "" | "inshore" | "open", "nation", "ground",
        "near": town id, "town": town id | ""}."""
        k = (int(q), int(r))
        got = self._cells.get(k)
        if got is not None:
            return got
        x, y, land, near = self._base(*k)
        ground = ""
        if land and near is not None:
            ground = self.patches.get(k) or self._road_ground(k[0], k[1], x, y, near)
            ground = biomes.canonical(ground) or "grassland" if ground else "grassland"
            if ground in ("urban", "underground", "ruins"):
                ground = "grassland"
            if ground == "water":
                # A river or a lake on land: the bank is ground to stand on.
                ground = "coast"
        towns = self.towns_at.get(k) or []
        # Water is inshore beside land (a coast's own water, where a boat or a swimmer comes
        # ashore) and open further out (UC p.158 has one water hex; the two are this app's).
        sea = "" if land else ("inshore" if any(self._is_land(*h) for h in neighbours(*k))
                               else "open")
        got = {"q": k[0], "r": k[1], "x": x, "y": y, "land": bool(land), "sea": sea,
               "nation": near["nation"] if (land and near is not None) else "",
               "ground": ground if land else "water",
               "near": near["id"] if near is not None else "",
               "town": towns[0] if towns else ""}
        if len(self._cells) < 200_000:
            self._cells[k] = got
        return got

    def region(self, nation: str, also=()) -> list[dict]:
        """The hexes of a nation's map: its land, a ring of whatever touches it, its waters
        `WATER_RING` hexes out from its coast (water whose nearest town is the nation's),
        and every hex in `also` with the six round it (the water the party has sailed)."""
        mine_c = [c for c in self.cities if c["nation"] == nation]
        if not mine_c:
            return []
        xs = [self.pos[c["id"]][0] for c in mine_c]
        ys = [self.pos[c["id"]][1] for c in mine_c]
        pad = 200
        q_lo, r_lo = hex_at(min(xs) - pad, min(ys) - pad, self.size)
        q_hi, r_hi = hex_at(max(xs) + pad, max(ys) + pad, self.size)
        mine = []
        for r in range(r_lo - 1, r_hi + 2):
            # The box in axial: q's range slides by half a step a row.
            q0 = hex_at(min(xs) - pad, centre(0, r, self.size)[1], self.size)[0]
            q1 = hex_at(max(xs) + pad, centre(0, r, self.size)[1], self.size)[0]
            for q in range(q0 - 1, q1 + 2):
                c = self.cell(q, r)
                if c["nation"] == nation:
                    mine.append(c)
        seen = {(c["q"], c["r"]) for c in mine}
        ring = []
        for c in mine:
            for h in neighbours(c["q"], c["r"]):
                if h not in seen:
                    seen.add(h)
                    ring.append(self.cell(*h))
        # Its waters, out from the coast a hex at a time (feat/sea-hexes): the sea a ship
        # puts out onto is on the map it puts out from.
        edge = [c for c in ring if not c["land"]]
        own = {c["id"] for c in mine_c}
        for _ in range(WATER_RING):
            nxt = []
            for c in edge:
                for h in neighbours(c["q"], c["r"]):
                    if h in seen:
                        continue
                    o = self.cell(*h)
                    if not o["land"] and o["near"] in own:
                        seen.add(h)
                        nxt.append(o)
            ring += nxt
            edge = nxt
        for h0 in also:
            for h in [tuple(h0)] + neighbours(*h0):
                if h not in seen:
                    seen.add(h)
                    ring.append(self.cell(*h))
        return mine + ring

    def hex_of_place(self, place_id: str, location_id: str = "") -> tuple | None:
        """The hex a place id stands in: a hex place's own `(q, r)`, else its town's."""
        got = parse_place(place_id)
        if got is not None:
            return got
        from . import places as places_mod

        town = places_mod.location_of(place_id) if place_id else location_id
        if town not in self.town_hex:
            town = location_id
        return self.town_hex.get(town)


def _spiral(h0, radius: int) -> list[tuple]:
    """Every hex within `radius` of h0, nearest first, in a fixed order."""
    out = [h0]
    for k in range(1, radius + 1):
        q, r = h0[0] + DIRS[4][0] * k, h0[1] + DIRS[4][1] * k
        for side in range(6):
            for _ in range(k):
                out.append((q, r))
                q, r = q + DIRS[side][0], r + DIRS[side][1]
    return out


_GRIDS: dict = {}


def grid(atlas: dict, lay: dict) -> Grid:
    """The Grid for this atlas and layout, remembered by identity and the layout's towns."""
    k = (id(atlas), LAYOUT_VERSION, len(lay.get("pos") or {}),
         round(sum(p[0] + 2 * p[1] for p in (lay.get("pos") or {}).values()), 6))
    held = _GRIDS.get(k)
    if held is not None and held[0] is atlas:
        return held[1]
    if len(_GRIDS) > 8:
        _GRIDS.clear()
    g = Grid(atlas, lay)
    _GRIDS[k] = (atlas, g)
    return g


# --- the hex as a place -------------------------------------------------------------------

def slug(q: int, r: int) -> str:
    """`hex-{q}-{r}`, a minus as `m` (a slug keeps `[a-z0-9-]`)."""
    def n(v):
        return f"m{-v}" if v < 0 else str(v)
    return f"hex-{n(int(q))}-{n(int(r))}"


def parse_place(place_id: str) -> tuple | None:
    """(q, r) from a hex place's id, `{town}~{ground}:@hex-{q}-{r}`, or None."""
    spot = str(place_id or "").split(":", 1)[-1] if ":" in str(place_id or "") else ""
    if not spot.startswith("@hex-"):
        return None
    head = spot[1:].split("/", 1)[0]
    bits = head.split("-")[1:]
    if len(bits) != 2:
        return None
    try:
        return tuple(-int(b[1:]) if b.startswith("m") else int(b) for b in bits)
    except ValueError:
        return None


def in_site(place_id: str, h=None) -> bool:
    """Whether a place id is inside a hex's site (`{loc}~{ground}:@hex-q-r/...`), and, with
    `h`, inside that hex's."""
    spot = str(place_id or "").split(":", 1)[-1] if ":" in str(place_id or "") else ""
    got = parse_place(place_id)
    return got is not None and "/" in spot and (h is None or tuple(h) == got)


_COMPASS = ("east", "south-east", "south", "south-west", "west", "north-west", "north",
            "north-east")


def bearing(frm, to) -> str:
    """Eight-point compass from one layout point to another. North is up the board
    (layout y grows southward, as the board's z does)."""
    ang = math.atan2(to[1] - frm[1], to[0] - frm[0])
    return _COMPASS[int(round(ang / (math.pi / 4))) % 8]


def place_doc(g: Grid, q: int, r: int, parent: str, world=None, boat: bool = False) -> dict:
    """The founded place for standing in hex (q, r): filed under its nearest town, so its
    nation, coin and law still answer (owner call 3, answered by default 2026-11-19).

    A water hex is two places: the water itself (`water` ground, where a swimmer is and the
    Swim rules apply, `rules/water.py`), and, with `boat`, a rowboat on it (`deck`
    ground, `ships.DECK`: planking, nobody swimming until they go over the side)."""
    from . import outskirts as outskirts_mod

    c = g.cell(q, r)
    town = g.city.get(c["near"]) or {}
    tname = town.get("name") or "the nearest town"
    tp = g.pos.get(c["near"], (c["x"], c["y"]))
    # Whole hexes from the town's own, at twelve miles each: the board's measure. From the
    # town's point instead, the hex beside Ashwatch read "6 miles east" (2026-11-19).
    th = g.town_hex.get(c["near"]) or (q, r)
    miles = max(1, distance(th, (q, r))) * HEX_MILES
    if not c["land"]:
        d = bearing(tp, (c["x"], c["y"]))
        # "the coastal water" read to the narrator as the coast itself: live 2026-11-21 it
        # had the party "reach the distant shore" a hex out from Branford, still afloat.
        what = "the inshore sea" if c.get("sea") == "inshore" else "the open sea"
        name = f"{what} {miles} miles {d} of {tname}"
        where = name
    elif c["town"]:
        name, where = f"the land round {tname}", f"the {c['ground']} round {tname}"
    else:
        d = bearing(tp, (c["x"], c["y"]))
        name = f"the {c['ground']} {miles} miles {d} of {tname}"
        where = f"open {c['ground']}, {miles} miles {d} of {tname}"
    nation = (g.nations.get(c["nation"]) or {}).get("name") or ""
    about = f"{where[:1].upper()}{where[1:]}" + (f", in {nation}" if nation else "") + "."
    ground = c["ground"]
    if boat and not c["land"]:
        from . import ships

        ground, name = ships.DECK, f"a rowboat on {name}"
        about = f"A hired rowboat and its boatman, on {where}."
    return {"id": outskirts_mod.ring_id(c["near"], ground, slug(q, r)),
            "name": name, "about": about, "terrain": ground, "exits": [],
            "parent": parent, "owner": "", "origin": "hex", "kind": "",
            # How far out of its town the hex lies (0 for the town's own): what a walk
            # between it and the town's places costs (`outskirts.hop_minutes`).
            "miles": distance(th, (q, r)) * HEX_MILES}


def hours_through(ground: str, speed_ft: int = 30) -> int:
    row = next((r for r in reversed(HOURS_BY_SPEED) if int(speed_ft or 30) >= r[0]),
               HOURS_BY_SPEED[0])
    return row[1] if ground in PLAIN else row[2]


# --- water hexes (feat/sea-hexes, docs/research/2026-11-21-sea-hexes.md) -------------------

def sea_hex_miles(atlas: dict, town_hex: dict) -> float:
    """The miles one water hex is reckoned at, so no crossing by hexes beats the passage.

    A passage is reckoned in days (`ships.leg_days`: the world's miles, else the floor of
    `ships.PASSAGE_MILES_AT_LEAST`, three weeks under a sailing ship, owner 2026-11-21),
    and the atlas carries each crossing's miles under that reckoning (`sail`). A ship
    sailing the hexes between the two ports crosses at least as many as lie on the
    straight line between them, so a water hex is the larger of twelve miles and the
    worst crossing's miles over its hexes. Measured 2026-11-21: 12.44 on Pangrella (81
    hexes for 1,008 miles), 12 on Aurvantis and the owner's fantasia, whose narrowest
    crossings are 107 and 90 hexes. The land's hexes are made fit by shrinking the hex
    (`Grid._fit`); the sea cannot shrink a grid the land shares, so its hours stretch."""
    worst = float(HEX_MILES)
    for rt in atlas.get("routes") or []:
        miles = float(rt.get("sail") or 0)
        a, b = town_hex.get(rt.get("a")), town_hex.get(rt.get("b"))
        if miles <= 0 or a is None or b is None:
            continue
        worst = max(worst, miles / max(1, distance(a, b)))
    return worst


# How a party crosses a water hex. A ship's run is the Core Rulebook's Table 7-9 day
# (`ships.MILES_A_DAY`, the whole day, a ship keeps watches); a rowboat is Ultimate
# Equipment's "about 1-1/2 miles per hour" (`ships.ROWBOAT_FT_PER_MINUTE`; CRB Table 7-9
# rows it 15 miles in a ten-hour day, so a hex is inside one rowing day); a swimmer is the
# Swim skill's half speed a round (`Engine._swim_out`), or a swim speed at the land's own
# Table 3-2 hours on plain.
WAYS = ("ship", "boat", "swim")


def ship_minutes(kind: str, miles: float) -> int:
    from . import ships

    return max(1, round(float(miles) * 24 * 60 / ships.miles_a_day(kind)))


def row_minutes(miles: float) -> int:
    from . import ships

    return max(1, round(float(miles) * 5280 / ships.ROWBOAT_FT_PER_MINUTE))


def swim_hours(speed_ft: int, miles: float, swim_speed: int = 0) -> float:
    """Hours to swim `miles`: a swim speed at Table 3-2's plain hours a twelve-mile hex;
    else the Swim skill's half speed as a full-round action, ten rounds a minute."""
    if swim_speed > 0:
        return hours_through("grassland", swim_speed) * float(miles) / HEX_MILES
    per_round = max(5, int(speed_ft or 30) // 2)
    return float(miles) * 5280 / per_round / 600


# --- what a hex holds ---------------------------------------------------------------------

# Site kinds by ground: the venture door's away-from-town kinds (`places.VENTURES`, hours > 0).
SITES_BY_GROUND = {
    "mountain": ("cave", "mine", "tower"), "hills": ("mine", "cave", "ruins", "tower"),
    "forest": ("ruins", "cave", "tower"), "jungle": ("ruins", "cave"),
    "swamp": ("ruins", "tower"), "desert": ("ruins", "cave", "tower"),
    "tundra": ("cave", "ruins"), "grassland": ("ruins", "tower", "cave"),
    "farmland": ("ruins", "tower"), "coast": ("cave", "ruins", "tower"),
}
# Find DCs (UC: a hidden site carries its own). What shows from far off is easy; what hides
# is hard. Cover adds to it.
FIND_DC = {"tower": 10, "ruins": 12, "mine": 15, "cave": 18}
COVER = frozenset({"forest", "jungle", "swamp"})
# Seen from inside its own hex: you are standing in it.
OWN_HEX_DC = -5
SITE_ONE_IN = 3

SEEN_FROM_AFAR = {
    "tower": "a tower stands against the sky",
    "ruins": "broken walls show",
    "mine": "the spoil heaps of an old mine scar the ground",
    "cave": "a cave mouth opens in the ground",
}
# A site already found, said once more when the party stops in its hex: it is where they
# can go in (playtest 2026-11-20 #4 asked for the look's finds once, not every walk).
FOUND_BEFORE = {
    "tower": "The tower you saw before stands in this hex.",
    "ruins": "The ruins you found before are in this hex.",
    "mine": "The old mine you found before is in this hex.",
    "cave": "The cave you found before opens in this hex.",
}


def found_before(kind: str) -> str:
    return FOUND_BEFORE.get(kind, "")


# The part of the day as a phrase that takes "in": `residency.day_part`'s eight words.
_DAY_PHRASE = {"deep in the night": "the dead of night", "the small hours": "the small hours",
               "early morning": "the early morning", "morning": "the morning",
               "midday": "the middle of the day", "afternoon": "the afternoon",
               "evening": "the evening", "late evening": "the late evening"}


def day_said(set_out: int, stopped: int) -> str:
    """When a hex's walk began and ended, from the clock, in words (no clock face): the
    foundation of a travel description is terrain, distance and time (the Alexandrian,
    "Hexcrawl Addendum: Describing Travel"). 0.4.4 said eight hours and nothing of the day."""
    from .residency import day_part

    a, b = day_part(set_out), day_part(stopped)
    pa, pb = _DAY_PHRASE.get(a, a), _DAY_PHRASE.get(b, b)
    if stopped - set_out >= 24 * 60:
        return f"You set out in {pa} and stop a day later, in {pb}."
    if a == b:
        return f"You set out and stop in {pb}."
    return f"You set out in {pa} and stop in {pb}."


def _roll(world_name: str, q: int, r: int, what: str) -> int:
    h = hashlib.sha256(f"{world_name}|{q}|{r}|{what}".encode()).digest()
    return int.from_bytes(h[:4], "big")


def site_of(g: Grid, q: int, r: int, kept: dict | None = None) -> dict | None:
    """The site in hex (q, r), or None: {"kind", "dc"}. Fixed by the world and the hex,
    except a site a save already found on an older grid (`kept`, `Scene.hexes["sites"]`,
    written by `mend_save`): the ruins a party stands in stay ruins after a rescale."""
    c = g.cell(q, r)
    if not c["land"] or c["town"]:
        return None
    kind = (kept or {}).get(key(q, r))
    if not kind:
        name = str(g.atlas.get("world") or "")
        if _roll(name, q, r, "site") % SITE_ONE_IN:
            return None
        kinds = SITES_BY_GROUND.get(c["ground"]) or ("ruins", "tower")
        kind = kinds[_roll(name, q, r, "kind") % len(kinds)]
    return {"kind": kind, "dc": FIND_DC[kind] + (2 if c["ground"] in COVER else 0)}


# --- a save from an older scale -----------------------------------------------------------

_HEX_ID = re.compile(r"([A-Za-z0-9_.-]+)~([a-z_-]+):@hex-(m?[0-9]+)-(m?[0-9]+)")


def _num(v: str) -> int:
    return -int(v[1:]) if v.startswith("m") else int(v)


def mend_save(data: dict, atlas: dict) -> bool:
    """Re-key a save's hexes from the grid it was played on to this build's
    (`GRID_VERSION`), in place, before the scene is read. True when anything changed.

    Every hex of the old grid is mapped to the new hex its middle falls in. The new hexes
    are only ever smaller (`Grid._fit`), so no two old hexes land on one new one. What
    moves with it: hex place ids wherever they are written in the scene, the ledger and
    the model's history (the party's place, everyone's place, founded hex places and the
    sites and rooms under them, props, cards, quests, roads, the places been); the
    `touched` and `spotted` records; and the founded hex places' own names and miles,
    re-made for the new hex. A hex place's head is re-made from its new hex (the nearest
    town and the ground); a site's head keeps its own ground. A site already spotted is
    kept as found (`Scene.hexes["sites"]`, read by `site_of`), whatever the new hex rolls.
    Sources: docs/research/2026-11-21-hex-scale.md."""
    import json
    from types import SimpleNamespace

    s = data.get("scene")
    hx = s.get("hexes") if isinstance(s, dict) else None
    if not isinstance(hx, dict):
        return False
    if hx.get("grid") == GRID_VERSION:
        return _mend_coast(data, atlas)
    lay = hx.get("layout")
    if not isinstance(lay, dict) or not atlas.get("cities"):
        # Never laid out: no hex was ever stood in, so nothing is keyed to a grid.
        hx["grid"], hx["coast"] = GRID_VERSION, COAST_VERSION
        return False
    lay = held_layout(SimpleNamespace(hexes=hx), atlas)
    routes = [r for r in atlas.get("routes") or []
              if r.get("by") != "sea" and r["a"] in lay["pos"] and r["b"] in lay["pos"]]
    # The grid as it was played: the old scale, and no channels (they came after it).
    old = Grid(atlas, lay, size=(HEX_MILES / 2) / _miles_per_unit(routes, lay["pos"]),
               channels=False)
    new = grid(atlas, lay)

    def moved(q: int, r: int) -> tuple[int, int]:
        return hex_at(*centre(q, r, old.size), new.size)

    def rekey(m) -> str:
        near, ground, q, r = m.group(1), m.group(2), _num(m.group(3)), _num(m.group(4))
        h = moved(q, r)
        cell = new.cell(*h)
        if ground == old.cell(q, r)["ground"]:
            ground = cell["ground"]                 # the hex itself: its new ground
        return f"{cell['near'] or near}~{ground}:@{slug(*h)}"

    for part in ("scene", "ledger", "history"):
        if data.get(part) is not None:
            data[part] = json.loads(_HEX_ID.sub(rekey, json.dumps(data[part])))
    s = data["scene"]
    hx = s["hexes"]
    for k in ("touched", "spotted"):
        if isinstance(hx.get(k), dict):
            hx[k] = {key(*moved(*unkey(x))): v for x, v in hx[k].items()}
    hx["sites"] = {**dict(hx.get("spotted") or {}), **dict(hx.get("sites") or {})}
    for doc in s.get("founded") or []:
        h = parse_place(str(doc.get("id") or ""))
        if h is not None and doc.get("origin") == "hex":
            fresh = place_doc(new, h[0], h[1], str(doc.get("parent") or ""))
            doc.update({k: fresh[k] for k in ("name", "about", "terrain", "miles")})
    at = str(s.get("at") or "")
    if parse_place(at) is not None:
        # Out on a hex, the party's town is the one that hex now lies nearest.
        s["location_id"] = at.split(":", 1)[0].rsplit("~", 1)[0]
    hx["grid"] = GRID_VERSION
    _mend_coast(data, atlas)
    return True


def _mend_coast(data: dict, atlas: dict) -> bool:
    """A save from before the coast's channels (`COAST_VERSION`): a party standing on the
    open ground of a hex a channel now covers is stood on the nearest land hex, and its
    place id moved wherever the scene writes it. Inside a hex's site, on a deck or in the
    water it is left: those places stand whatever the hex beneath them is now."""
    import json
    from types import SimpleNamespace

    from . import places as places_mod

    s = data["scene"]
    hx = s["hexes"]
    if hx.get("coast") == COAST_VERSION:
        return False
    hx["coast"] = COAST_VERSION
    at = str(s.get("at") or "")
    h = parse_place(at)
    if h is None or in_site(at) or places_mod.terrain_of(at) in ("water", "deck")             or not isinstance(hx.get("layout"), dict) or not atlas.get("cities"):
        return False
    g = grid(atlas, held_layout(SimpleNamespace(hexes=hx), atlas))
    if g.cell(*h)["land"]:
        return False
    land = next((x for x in _spiral(h, 8) if g.cell(*x)["land"]), None)
    if land is None:
        return False
    doc = place_doc(g, land[0], land[1], parent="")
    data["scene"] = s = json.loads(json.dumps(s).replace(json.dumps(at), json.dumps(doc["id"])))
    if not any(d.get("id") == doc["id"] for d in s.get("founded") or []):
        s.setdefault("founded", []).append(doc)
    s["location_id"] = doc["id"].split(":", 1)[0].rsplit("~", 1)[0]
    return True
