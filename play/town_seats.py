"""Where each place stands on the town tabletop (phase 2 of docs/place-map-v2-build-plan.md).

The owner chose the mock's 3D tabletop on 2026-11-18 (`docs/mock/place-map-v2/`, branch
`mock/place-map-v2`, `shared/model.js` `townLayout`). The town is laid out BY RULE, never by
physics: the export has no coordinates, and a rule gives every place a seat that does not
move as more of the town is found.

- the great square in the middle (or, in a town without one, its best-joined place);
- the four crossings at their compass points, 190 units out;
- each place on a crossing's street in a fixed seat, in pairs either side of the street,
  a row every 85 units further out. **Rows never run out**: the mock's first version dealt
  the seats `k % 8` and stacked places 9-16 on 1-8 when its worst case put sixteen on one
  street. Places are founded in play (a house called on, a shop gone into), so a street's
  length is unbounded;
- every other place round the square, four a ring on the diagonals between the streets
  (eight a ring in the 48 of Aurvantis's 64 towns that have no crossings);
- the ways in (`places.ENTRANCES`: the gate, the way in, the bridge, the docks) at the far
  end of their street, past its last row;
- storeys and cellars (`^n`) are not seats: they are a badge on their building;
- the wall round every seat, however long a street has grown.

**Why this is worked out here and not in the page, as the plan first said.** The mock had
every place's id in the page and dealt the seats over all of them, found or not, sorted by
id. The game never sends an unfound place: `places_found.chart()` gives it to the page only
as an index in `layout.links`, so nothing of it can leak into the DOM. Dealing the seats
needs the whole town, so the dealing happens on this side, and only the seats of places
found cross to the page.

**The shape is the engine's own.** A quartered city's places say which crossing they hang
off (`Place.within`, `places._districted`), and a place founded in play says what it hangs
off (`Place.parent`); the links (`Place.exits`) decide only what neither says.
"""
from __future__ import annotations

import math
import re

from rules import places as places_mod

C = 190                      # the square to a crossing
ROW = 85                     # a row of seats every ROW further out
ACROSS = 82                  # a seat's distance from its street
GATE = C + 195               # the shortest street's way in
DIRS = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}
_CROSSING = re.compile(r"^the (north|east|south|west) crossing$")
_FLOOR = re.compile(r"\^(-?\d+)$")


def _slot(k: int) -> tuple[float, int]:
    """The k-th seat on a street: how far out, and which side."""
    return C - 5 + ROW * (k // 2), (1 if k % 2 else -1)


def _floor(pid: str) -> int:
    m = _FLOOR.search(pid)
    return int(m.group(1)) if m else 0


def _base(pid: str) -> str:
    return _FLOOR.sub("", pid)


def layout(known) -> dict:
    """Seats over the whole live graph (`Engine.places()`).

    Returns {"pos": {id: (x, y)}, "kind": {id: square|crossing|gate|place},
             "street": {id: the id its street starts from}, "ward": {id: north|...|square},
             "storeys": {id: int}, "wall": float, "half": float, "gate": id | ""}.
    Every seat is a place inside the walls that is not a storey.
    """
    by_id = {p.id: p for p in known}
    ids = sorted(by_id)
    urban = [i for i in ids if places_mod.setting_of(i) == "in" and not _floor(i)]
    out = {"pos": {}, "kind": {}, "street": {}, "ward": {}, "storeys": {}, "wall": float(GATE),
           "half": 560.0, "gate": ""}
    if not urban:
        return out
    inside = set(urban)
    near: dict[str, set] = {i: set() for i in urban}
    for i in urban:
        for x in by_id[i].exits:
            if x in inside and x != i:
                near[i].add(x)
                near[x].add(i)
    name = {i: str(by_id[i].name or "").strip().lower() for i in urban}
    square = next((i for i in urban if name[i] == "the great square"), None) \
        or max(urban, key=lambda i: (len(near[i]), -urban.index(i)))
    crossings = {}
    for i in urban:
        m = _CROSSING.match(name[i])
        if m and i != square and m.group(1) not in crossings:
            crossings[m.group(1)] = i
    dir_of = {i: d for d, i in crossings.items()}
    entrances = {i for i in urban if name[i] in places_mod.ENTRANCES}

    pos, kind, street, ward = out["pos"], out["kind"], out["street"], out["ward"]
    pos[square], kind[square], ward[square] = (0.0, 0.0), "square", "square"
    for d, i in crossings.items():
        dx, dy = DIRS[d]
        pos[i], kind[i], street[i], ward[i] = (dx * C, dy * C), "crossing", square, d

    # Which street each remaining place is on: what the place says it hangs off first
    # (`within`, then `parent`, followed up to a crossing), its links to a crossing next.
    def quarter(i: str) -> str | None:
        seen, cur = set(), i
        while cur and cur not in seen:
            seen.add(cur)
            p = by_id.get(cur)
            for up in (getattr(p, "within", ""), getattr(p, "parent", "")):
                if up in dir_of:
                    return up
            cur = getattr(p, "parent", "") or getattr(p, "within", "")
        return next((crossings[d] for d in DIRS if d in crossings and crossings[d] in near[i]), None)

    by_crossing: dict[str, list] = {}
    by_square: list = []
    for i in urban:
        if i in pos:
            continue
        c = quarter(i)
        (by_crossing.setdefault(c, []) if c else by_square).append(i)

    for c, members in by_crossing.items():
        dx, dy = DIRS[dir_of[c]]
        nx, ny = -dy, dx
        gates = [i for i in members if i in entrances]
        rest = sorted(i for i in members if i not in entrances)
        end = max(GATE, _slot(max(len(rest) - 1, 0))[0] + 90)   # past the last row
        for k, g in enumerate(gates):
            side = (k + 1) // 2 * (1 if k % 2 else -1) * ACROSS
            pos[g] = (dx * end + nx * side, dy * end + ny * side)
            kind[g], street[g], ward[g] = "gate", c, dir_of[c]
        for k, i in enumerate(rest):
            a, side = _slot(k)
            pos[i] = (dx * a + nx * side * ACROSS, dy * a + ny * side * ACROSS)
            kind[i], street[i], ward[i] = "place", c, dir_of[c]

    # Round the square: on the diagonals between the four streets, a ring further out for
    # every four; with no streets, eight a ring. Measured 2026-11-18 on the mock: the old
    # ring (28 degrees round, 26 further out) put a town's tenth place 56 units from a seat.
    per = 4 if crossings else 8
    for k, i in enumerate(sorted(by_square)):
        ring = k // per
        deg = (45 + 90 * (k % 4)) if per == 4 else (22.5 + 45 * (k % 8) + (ring % 2) * 22.5)
        r = 112 + (62 if per == 4 else 72) * ring
        a = math.radians(deg)
        pos[i] = (math.cos(a) * r, math.sin(a) * r)
        kind[i] = "gate" if i in entrances else "place"
        street[i], ward[i] = square, "square"

    for i in ids:
        if _floor(i) > 0 and _base(i) in pos:
            out["storeys"][_base(i)] = out["storeys"].get(_base(i), 1) + 1
    out["wall"] = max(GATE, *(math.hypot(*p) + 50 for p in pos.values()))
    out["half"] = max(560.0, *(max(abs(p[0]), abs(p[1])) + 130 for p in pos.values()))
    gates = sorted(i for i in pos if kind[i] == "gate")
    out["gate"] = next((g for g in gates if name[g] == "the gate"), gates[0] if gates else "")
    return out


def _r(p):
    return [round(p[0], 1), round(p[1], 1)] if p else None


def seats(known, found_ids, here_id: str) -> dict:
    """What the tabletop needs, for the places found only.

    Returns {"wall", "half", "gate": id of the town's way out if FOUND else "",
             "seats": {id: {"at", "drawn", "kind", "foot", "ward", "storeys"}}}.

    `at` is where a place's miniature stands, or for one that is not a seat where the party
    is drawn when standing in it: a storey at its building, a cellar or a dungeon's room at
    the place above it, anywhere outside the walls at the gate. `foot` is where the ink of
    its street starts (the square for a crossing, the crossing for a gate, the street's own
    line for a place), so the page draws the streets without knowing an unfound place.
    """
    L = layout(known)
    by_id = {p.id: p for p in known}
    pos, kind, street = L["pos"], L["kind"], L["street"]
    found = set(found_ids) | {here_id}
    gate = L["gate"] if L["gate"] in found else ""

    def anchor(i: str):
        seen, cur = set(), i
        while cur and cur not in seen:
            seen.add(cur)
            if cur in pos:
                return pos[cur]
            if _base(cur) in pos:
                return pos[_base(cur)]
            cur = getattr(by_id.get(cur), "parent", "")
        if places_mod.setting_of(i) == "outside" and gate:
            return pos[gate]
        return None

    def foot(i: str):
        s = street.get(i)
        if not s:
            return None
        if kind[i] in ("crossing", "gate"):
            return pos[s]
        (x, y), (sx, sy) = pos[i], pos[s]
        if kind.get(s) == "crossing":
            return (0.0, y) if sx == 0 else (x, 0.0)
        return (sx, sy)

    out = {}
    for i in sorted(found):
        drawn = i in pos
        out[i] = {"at": _r(anchor(i)), "drawn": drawn, "kind": kind.get(i, ""),
                  "foot": _r(foot(i)) if drawn else None, "ward": L["ward"].get(i, ""),
                  "storeys": L["storeys"].get(i, 1) if drawn else 0}
    return {"wall": round(L["wall"], 1), "half": round(L["half"], 1), "gate": gate, "seats": out}
