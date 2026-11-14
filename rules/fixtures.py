"""Named fixtures on the tactical map: the bar, the tables, the stair, the crates.

`rules/floorplan.py` refused named features on purpose — "a feature the engine cannot act
on is decoration, and decoration belongs in the prose" — and that refusal still stands.
What this module adds is not decoration: every kind in `content/rules/fixtures.json`
declares only properties the engine already reads (`blocked`, `difficult`, raised floor,
a parapet's cover) or reads from here on (a stair you walk up, a low obstacle you see
over), and records the rest (flammable, breakable, movable) as data for phase 2.

**Phase 1 types the geometry that already exists; it never lays new ground.** Campaigns
have people standing on today's derived maps, so a fixture is a NAME given to squares
the plan already made solid, rough or raised: this blocked clump is the bar, that one the
barrels, this raised band is a gallery. The only addition is a stair at a gallery's foot,
and a stair is walkable, so it can never put a saved position inside anything.

Derived, not stored, the way the floorplan is: the fixtures are a pure function of the
place id and the PRISTINE plan (`floorplan.for_place`), intersected with the grid as it
stands — so a wall of stone a spell raised is never mistaken for a shelf, and a saved
grid from an older plan is typed only where it still agrees. The one stored exception is
a fixture the reader names in a room that has none of that kind (`name_one`): it is
placed once, on a free square, and kept for good in `Scene.fixtures_named` (the
2026-09-28 ruling that people keep their square, extended to things).

Prior art, and what it settled:
- Cataclysm: DDA's furniture JSON is the same shape — a closed list of furniture ids,
  each with flags the engine reads (TRANSPARENT, CLIMBABLE, FLAMMABLE, GOES_UP, RAMP)
  and nothing else; data, never code per item (doc/JSON_FLAGS.md).
- Inform 7's supporters: a thing you can stand on is a kind with a property, not a
  special case in the parser.
- Fate Core's situation aspects: scenery is real once established and keeps being true.
- The Core Rulebook for every number (cover p.195, Climb p.90, Table 7-13/7-14 p.173,
  rubble p.411, stairs p.415); `fixtures.json` cites each and marks the house rules.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import floorplan
from .grid import Grid, Point

OCCUPIES = ("blocked", "difficult", "raised", "open", "overhead")
FORMS = ("steps", "long", "box", "round", "none")
COVERS = ("none", "cover", "soft")
_FLAGS = ("low", "stair", "opening", "see_through", "flammable", "breakable", "movable",
          "burns", "swim", "placed", "narratable")
_NUMBERS = ("climb_dc", "hardness", "hp", "break_dc")
_TEXT = ("name", "plural", "source", "reached_by")
_FIELDS = frozenset(_FLAGS + _NUMBERS + _TEXT + ("occupies", "form", "cover"))
# Which geometry each list in a place row may type.
_SLOTS = {"solid": "blocked", "rough": "difficult", "raised": "raised"}

_DATA: dict | None = None


def validate(raw) -> list[str]:
    """Everything wrong with a fixtures document, each problem with the fix named."""
    problems: list[str] = []
    if not isinstance(raw, dict) or not isinstance(raw.get("kinds"), dict):
        return ['fixtures.json is {"kinds": {...}, "places": {...}, "terrain": {...}}.']
    kinds = raw["kinds"]
    for kid, k in kinds.items():
        at = f"kinds.{kid}"
        if not re.fullmatch(r"[a-z][a-z-]*", str(kid)):
            problems.append(f"{at}: a kind id is lower case letters and hyphens.")
        if not isinstance(k, dict):
            problems.append(f"{at}: a kind is an object.")
            continue
        for extra in sorted(set(k) - _FIELDS):
            problems.append(f"{at}.{extra}: not a fixture property. Use one of "
                            f"{', '.join(sorted(_FIELDS))}.")
        for need in ("name", "plural", "source"):
            if not isinstance(k.get(need), str) or not k.get(need).strip():
                problems.append(f"{at}.{need}: write it as words.")
        occ = k.get("occupies")
        if not isinstance(occ, list) or not occ or any(o not in OCCUPIES for o in occ):
            problems.append(f"{at}.occupies: a list from {', '.join(OCCUPIES)}.")
            occ = []
        if k.get("form") not in FORMS:
            problems.append(f"{at}.form: one of {', '.join(FORMS)}.")
        if k.get("cover") not in COVERS:
            problems.append(f"{at}.cover: one of {', '.join(COVERS)}.")
        for flag in _FLAGS:
            if flag in k and not isinstance(k[flag], bool):
                problems.append(f"{at}.{flag}: true or false.")
        for num in _NUMBERS:
            v = k.get(num)
            if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
                problems.append(f"{at}.{num}: a whole number of at least 0, or null.")
        if k.get("low") and ("blocked" not in occ or k.get("cover") != "cover"):
            problems.append(f"{at}.low: a low obstacle occupies blocked squares and gives "
                            f"cover (CRB p.195); set occupies to include blocked and "
                            f"cover to \"cover\".")
        if k.get("stair") and "open" not in occ:
            problems.append(f"{at}.stair: a stair is walked on; add \"open\" to occupies.")
        by = k.get("reached_by")
        if by is not None and not (isinstance(kinds.get(by), dict) and kinds[by].get("stair")):
            problems.append(f"{at}.reached_by: name a kind with \"stair\": true.")
        if k.get("narratable") and ("blocked" not in occ or k.get("placed") is False):
            problems.append(f"{at}.narratable: only a placeable kind that occupies blocked "
                            f"squares can be put down by the reader.")
    for table in ("places", "terrain"):
        for key, row in (raw.get(table) or {}).items():
            at = f"{table}.{key}"
            if not isinstance(row, dict):
                problems.append(f"{at}: a row is {{\"solid\": [...], \"rough\": [...]}}.")
                continue
            for extra in sorted(set(row) - set(_SLOTS) - {"names"}):
                problems.append(f"{at}.{extra}: use solid, rough, raised or names.")
            for slot, geometry in _SLOTS.items():
                for kid in row.get(slot) or ():
                    k = kinds.get(kid)
                    if not isinstance(k, dict):
                        problems.append(f"{at}.{slot}: no kind called {kid!r}; the kinds "
                                        f"are {', '.join(sorted(kinds))}.")
                    elif geometry not in (k.get("occupies") or ()):
                        problems.append(f"{at}.{slot}: {kid} does not occupy {geometry} "
                                        f"squares; add it to its occupies or move it.")
            for kid, name in (row.get("names") or {}).items():
                if kid not in kinds or not isinstance(name, str):
                    problems.append(f"{at}.names.{kid}: a kind id and the words for it.")
    return problems


def data() -> dict:
    global _DATA
    if _DATA is None:
        from django.conf import settings

        path = Path(settings.BASE_DIR) / "content" / "rules" / "fixtures.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        problems = validate(raw)
        if problems:
            raise ValueError("content/rules/fixtures.json: " + " ".join(problems))
        _DATA = raw
    return _DATA


def kinds() -> dict[str, dict]:
    return data()["kinds"]


def names() -> list[str]:
    """The closed list, for the reader's schema."""
    return sorted(kinds())


def _profile(place_id: str, terrain: str = "", authored=None) -> dict:
    """Which kinds type this place: the world's own list when it authored one, then the
    spot's row, then the terrain's, then nothing."""
    d = data()
    bare = str(place_id or "").rsplit(floorplan.STOREY, 1)[0]
    spot = bare.rsplit(":", 1)[-1].rsplit("/", 1)[-1].strip().lower()
    own = dict(d.get("places", {}).get(spot) or {})
    if not own and authored is not None:
        # A place founded in play ("the Copper Kettle", a tavern) has its own slug and its
        # kind's shape (`places.shape_of_kind`): find the kind's row by that shape. Live
        # 2026-11-12 a founded tavern was laid with carts and crates, no bar, no tables.
        kin = next((k for k, v in floorplan.BY_SPOT.items() if v == authored), "")
        own = dict(d.get("places", {}).get(kin) or {})
    row = own
    if not any(own.get(slot) for slot in _SLOTS) or floorplan._storey(place_id):
        # A storey is rooms over the work, not the work: the terrain's row, as for any
        # room this table does not know. A row of names alone (the gate's wall-walk) is
        # still a room the table does not type.
        row = dict(d.get("terrain", {}).get(str(terrain or "").strip().lower()) or {})
        if own.get("names") and not floorplan._storey(place_id):
            row["names"] = {**(row.get("names") or {}), **own["names"]}
    world = tuple(getattr(authored, "fixtures", ()) or ())
    if world:
        k = kinds()
        row["solid"] = [w for w in world if "blocked" in k[w]["occupies"]] or row.get("solid", [])
        row["rough"] = [w for w in world if "difficult" in k[w]["occupies"]] or row.get("rough", [])
        row["raised"] = [w for w in world if "raised" in k[w]["occupies"]
                         and not k[w].get("reached_by")] or row.get("raised", [])
    return row


def _components(squares: set) -> list[list[Point]]:
    """4-connected clumps, biggest first, then by their first square: a stable order."""
    left, out = set(squares), []
    while left:
        seed = min(left)
        clump, todo = set(), [seed]
        while todo:
            p = todo.pop()
            if p in clump or p not in left:
                continue
            clump.add(p)
            todo.extend(((p[0] + 1, p[1]), (p[0] - 1, p[1]), (p[0], p[1] + 1), (p[0], p[1] - 1)))
        left -= clump
        out.append(sorted(clump))
    return sorted(out, key=lambda c: (-len(c), c[0]))


def _fixture(kind: str, squares, level: int, row: dict) -> dict:
    k = kinds()[kind]
    many = len(squares) > 1 and k["form"] in ("box", "round")
    name = (row.get("names") or {}).get(kind) or (k["plural"] if many else k["name"])
    return {"kind": kind, "name": name, "squares": [list(p) for p in sorted(squares)],
            "level": int(level), "form": k["form"],
            "height": 0 if k["form"] == "none" else (1 if k.get("low") else 2)}


def derive(grid: Grid | None, place_id: str, terrain: str = "", authored=None) -> list[dict]:
    """The fixtures this place's existing geometry is, the same every time it is asked."""
    if grid is None:
        return []
    plan = floorplan.for_place(place_id, terrain, authored)
    if (plan.width, plan.height) != (grid.width, grid.height):
        return []                    # a saved room of another shape: type nothing
    shape = floorplan.shape_for(place_id, terrain, authored)
    if shape.layout == "rows" and not plan.blocked <= grid.blocked:
        # Saved rooms are left alone (plan item 6): a market laid before its stalls stood
        # in rows keeps the stalls it was saved with, named by the old scatter. Never
        # moved, so nobody saved standing beside one is now inside it.
        old = floorplan.for_place(place_id, terrain, authored, scatter=True)
        if len(old.blocked & grid.blocked) > len(plan.blocked & grid.blocked):
            plan = old
    row = _profile(place_id, terrain, authored)
    out: list[dict] = []
    # A ship's room or a quay names its own pieces (`floorplan.parts`): the mast, the
    # hatch, the rail. Each is named only where the grid still agrees with it.
    named: set = set()
    for part in floorplan.parts(place_id, terrain, authored):
        sq = {tuple(p) for p in part["squares"]}
        lay = part["lay"]
        if not (sq <= grid.blocked if lay == "blocked" else sq <= grid.difficult
                if lay == "difficult" else all(grid.floor.get(p) == part["level"] for p in sq)
                if lay == "raised" else sq.isdisjoint(grid.blocked)):
            continue
        f = _fixture(part["kind"], sorted(sq),
                     part["level"] if lay == "raised" else grid.ground(min(sq)), row)
        f["name"] = part["name"] or f["name"]
        out.append(f)
        named |= sq
    if shape.layout == "ship":
        return out                   # all of a hull is its parts; its sides are nobody's
    for slot, squares in (("solid", (plan.blocked & grid.blocked) - named),
                          ("rough", (plan.difficult & grid.difficult) - named)):
        kinds_here = row.get(slot) or ()
        for i, clump in enumerate(_components(squares) if kinds_here else ()):
            out.append(_fixture(kinds_here[i % len(kinds_here)], clump,
                                grid.ground(clump[0]), row))
    raised = {p: v for p, v in plan.floor.items() if grid.floor.get(p) == v and p not in named}
    kinds_up, n = row.get("raised") or (), 0
    for level in sorted(set(raised.values())):
        for clump in _components({p for p, v in raised.items() if v == level}):
            if shape.vertical == "ledge":
                out.extend(_gallery(grid, clump, level, place_id, row))
            elif shape.vertical == "scatter" and kinds_up:
                out.append(_fixture(kinds_up[n % len(kinds_up)], clump, level, row))
                n += 1
    return out


def _gallery(grid: Grid, band: list, level: int, place_id: str, row: dict) -> list[dict]:
    """A raised band and the stair up to it, on an open square at its foot.

    The stair is the one thing phase 1 adds, and it changes no geometry: the square stays
    open floor, so nothing standing there is ever inside it. Taken from the band's ends
    (the first or last candidate in order, by the place's seed), which is where a stair
    to a gallery runs.
    """
    gallery = _fixture("gallery", band, level, row)
    inner = [q for p in band
             for q in ((p[0] + 1, p[1]), (p[0] - 1, p[1]), (p[0], p[1] + 1), (p[0], p[1] - 1))
             if grid.inside(q) and grid.ground(q) < level and q not in grid.blocked
             and q not in grid.difficult]
    ring = [q for q in inner if 0 < q[0] < grid.width - 1 and 0 < q[1] < grid.height - 1]
    feet = sorted(set(ring or inner))
    if not feet:
        return [gallery]
    foot = feet[-1] if floorplan._seed(place_id) % 2 else feet[0]
    stair = _fixture("stair", [foot], grid.ground(foot), row)
    stair["up_to"] = level
    gallery["stair"] = list(foot)
    return [gallery, stair]


def type_the_ground(scene, place_id: str, terrain: str = "", authored=None) -> None:
    """Name the ground the scene stands on: derive, add the reader's own, apply the reads.

    The one door fixtures reach a grid by, called by `Engine.lay_the_ground` both when a
    room is laid and when a saved one is loaded (a save carries no fixtures — they are
    derived — so a campaign from before this module gains them on its next load).
    """
    grid = getattr(scene, "grid", None)
    if grid is None:
        return
    named = [f for f in (getattr(scene, "fixtures_named", {}) or {}).get(place_id, ())
             if f.get("kind") in kinds()
             and all(grid.inside(tuple(p)) for p in f.get("squares") or ())]
    for f in named:
        if "blocked" in kinds()[f["kind"]]["occupies"]:
            grid.blocked.update(tuple(p) for p in f["squares"])
    grid.fixtures = derive(grid, place_id, terrain, authored) + [dict(f) for f in named]
    # Open water (a `swim` kind: the sea past the side, the rail's squares of it), which a
    # swimmer may enter and anybody may go over the side into (`Grid.passable(swims=)`).
    grid.water = {tuple(p) for f in grid.fixtures if kinds()[f["kind"]].get("swim")
                  and "blocked" in kinds()[f["kind"]]["occupies"] for p in f["squares"]}
    grid.low = {tuple(p): grid.ground(tuple(p)) + 1 for f in grid.fixtures
                if kinds()[f["kind"]].get("low") for p in f["squares"]}
    # Water you cannot walk on but can see and shoot across (the sea past a rail): its
    # top is the surface, a level under the floor, so it blocks no line and covers nobody.
    grid.low.update({tuple(p): grid.ground(tuple(p)) - 1 for f in grid.fixtures
                     if kinds()[f["kind"]].get("see_through") and not kinds()[f["kind"]].get("low")
                     and "blocked" in kinds()[f["kind"]]["occupies"] for p in f["squares"]})
    # The rail opens where the stair arrives. The floorplan's rail stands on the squares in
    # front of a gallery (`floorplan._raise`'s lip), and the stair's foot is one of those
    # squares: left there, the board drew a rail through the stair and anyone on it, and a
    # line from the stair's top met a rail in its own square (the gate, 2026-11-11).
    for f in grid.fixtures:
        if kinds()[f["kind"]].get("stair"):
            for p in f["squares"]:
                grid.parapet.pop(tuple(p), None)


def at(grid: Grid | None, square) -> dict | None:
    """The fixture standing on this square, or None."""
    if grid is None or not getattr(grid, "fixtures", None):
        return None
    sq = [int(square[0]), int(square[1])]
    return next((f for f in grid.fixtures if sq in f["squares"]), None)


def stair_to(grid: Grid | None, square) -> tuple | None:
    """The stair square by which a body walks up onto this raised square, or None."""
    f = at(grid, square)
    if f is None or not kinds()[f["kind"]].get("reached_by") or not f.get("stair"):
        return None
    return tuple(f["stair"])


def climb_onto(grid: Grid | None, square) -> tuple[str, int] | None:
    """(what it is, its Climb DC) when this raised square is a thing to climb onto."""
    f = at(grid, square)
    if f is None or f["level"] <= 0:
        return None
    dc = kinds()[f["kind"]].get("climb_dc")
    return (f["name"], int(dc)) if dc is not None else None


def seen(grid: Grid | None) -> list[dict]:
    """The fixtures the player can see: every one not wholly inside fog or smoke."""
    if grid is None or not getattr(grid, "fixtures", None):
        return []
    return [{k: f[k] for k in ("kind", "name", "squares", "level", "form", "height")}
            for f in grid.fixtures
            if not all(tuple(p) in grid.obscuring for p in f["squares"])]


def said(grid: Grid | None) -> list[str]:
    """The fixtures in plain words, no numbers: one phrase per kind, in map order."""
    out: list[str] = []
    by: dict[str, list[dict]] = {}
    for f in getattr(grid, "fixtures", None) or ():
        by.setdefault(f["kind"], []).append(f)
    for kind, fs in by.items():
        if kind == "stair" and "gallery" in by:
            continue                     # said with the gallery it climbs to
        first = fs[0]["name"]
        # Three masts named fore, main and mizzen are "masts", not "the foremast" alone.
        same = all(f["name"] == first for f in fs)
        phrase = first if len(fs) == 1 or same and first.startswith("the ") \
            else kinds()[kind]["plural"]
        if kind == "gallery" and any(f.get("stair") for f in fs):
            phrase += " reached by a stair"
        out.append(phrase)
    return out


def name_one(scene, kind: str, near: str | None = None) -> dict | None:
    """Put down a fixture the reader named in a room that has none of that kind.

    On a free square nearest the person the sentence put it by (else the player): open,
    level floor, nobody standing on it, nothing solid in any of its eight neighbours —
    so a new barrel can never wall a doorway shut or box anybody in. Kept for good:
    stored in `Scene.fixtures_named` under the place, and the square stays solid.
    """
    grid = getattr(scene, "grid", None)
    k = kinds().get(str(kind or ""))
    if grid is None or grid.fixtures is None or k is None or not k.get("narratable"):
        return None
    if any(f["kind"] == kind for f in grid.fixtures):
        return None
    from .grid import distance

    pc = scene.pc() if hasattr(scene, "pc") else None
    who = near or (pc.ref if pc is not None else "")
    origin = tuple((scene.positions.get(who) or (grid.width // 2, grid.height // 2))[:2])
    taken = scene.occupied() | {tuple(p) for f in grid.fixtures for p in f["squares"]}

    def free(p) -> bool:
        if not (0 < p[0] < grid.width - 1 and 0 < p[1] < grid.height - 1):
            return False
        if p in taken or p in grid.difficult or grid.ground(p) or not grid.passable(p):
            return False
        return not any((p[0] + dx, p[1] + dy) in grid.blocked
                       for dx in (-1, 0, 1) for dy in (-1, 0, 1))

    spots = sorted((p for p in ((x, y) for x in range(grid.width) for y in range(grid.height))
                    if free(p)), key=lambda p: (distance(origin, p), p))
    if not spots:
        return None
    square = spots[0]
    fixture = _fixture(kind, [square], 0, {})
    fixture["named"] = True
    grid.blocked.add(square)
    if k.get("low"):
        grid.low[square] = grid.ground(square) + 1
    grid.fixtures.append(fixture)
    scene.fixtures_named.setdefault(str(scene.at or ""), []).append(dict(fixture))
    return fixture


def held_to_words(grid: Grid | None, kind: str, words: str) -> str:
    """The reader's fixture, held to the walker's own words against this room's fixtures.

    The Copper Kettle, 2026-11-12: "I step behind the bar" was read `fixture: barrel`,
    and the walk stood the player beside the barrel in the open, an ogre a square away;
    the room's counter is called "the bar". So when the words name a fixture of the room
    — by its own name's noun ("bar", "landing") or its kind's ("counter", "counters") —
    and not the kind the reader chose, the named one is the walk's. Words naming nothing
    here leave the reader's answer as it was (a room that lacks the kind gets one,
    `name_one`)."""
    if grid is None or not grid.fixtures or not words or kind == FLOOR:
        return kind
    word = r"[a-z]+(?:-[a-z]+)*"             # "wall-walk" is one word, never "walk"
    said = set(re.findall(word, words.lower()))

    def nouns(k: str) -> set[str]:
        row = kinds().get(k) or {}
        names = [f["name"] for f in grid.fixtures if f["kind"] == k]
        names += [str(row.get("name") or ""), str(row.get("plural") or "")]
        return {re.findall(word, n.lower())[-1] for n in names if re.findall(word, n.lower())}

    if nouns(kind) & said:
        return kind
    named = [f["kind"] for f in grid.fixtures if nouns(f["kind"]) & said]
    return named[0] if named else kind


def square_name(p) -> str:
    """A square's name as the board prints it: column letters across (A..Z, then AA..),
    rows from 1 at the top — `sqName` in play/static/js/table/03-offers-and-map.js."""
    c, r = int(p[0]), int(p[1])
    col = chr(65 + c) if c < 26 else chr(64 + c // 26) + chr(65 + c % 26)
    return f"{col}{r + 1}"


def square_said(grid: Grid | None, words: str):
    """The board square a line names by its printed coordinate ("I go to C5"), or None.
    The owner, 2026-11-12: coordinates on the map "so that the user can be precise about
    where he wants to stand". A name the board printed, matched only against squares this
    board has — never a guess at English. One square: two named is no single place to go."""
    if grid is None or not words:
        return None
    names = {square_name((c, r)): (c, r) for c in range(grid.width) for r in range(grid.height)}
    found = {names[m] for m in re.findall(r"\b([A-Z]{1,2}\d{1,3})\b", words) if m in names}
    return found.pop() if len(found) == 1 else None


# The reader's answer for a walk back down off a raised fixture to the room's own floor
# ("I go back down"): not a kind, so never on the map, but in the reader's closed list.
FLOOR = "floor"


def walk_to(scene, kind: str, who) -> tuple[tuple | None, str]:
    """Where a walk to this fixture of the room ends: (square, "") with the level written
    in, (None, why) when there is no room for them there, or (None, "") when nothing here
    answers or they are there already.

    Measured at the gate, 2026-11-11: "I walk up the stair onto the wall-walk above the
    gate" was read as two walks within the place, to the stair and the wall-walk, and built
    no move at all — the narration put the player on the wall-walk while the token stayed
    on the ground. A walk inside the place is free (the turn-budget ruling, 2026-11-06),
    which means it costs no time, not that it does not happen.

    * a raised fixture reached by a stair (a gallery): its free square nearest the stair,
      on its floor — the engine's stair rule walks them up;
    * the stair itself, or anything else open: its own free square;
    * something solid (the bar, a shelf, a barrel): the free floor beside it nearest them;
    * FLOOR, from up on a gallery: the stair's foot, else free floor beside it.
    """
    grid = getattr(scene, "grid", None)
    if grid is None or not grid.fixtures or who is None or who.ref not in scene.positions:
        return None, ""
    from .grid import distance

    here = tuple(scene.positions[who.ref])
    level = here[2] if len(here) > 2 else grid.ground(here)
    taken = scene.occupied(ignore=who.ref)

    def free(p) -> bool:
        return grid.inside(p) and p not in taken and p not in grid.blocked \
            and grid.passable(p)

    def nearest(squares, origin):
        return sorted(squares, key=lambda p: (distance(origin, p), p))

    def beside(squares):
        ring = {(p[0] + dx, p[1] + dy) for p in squares
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}
        return [p for p in ring - set(squares) if free(p) and grid.ground(p) == 0]

    if kind == FLOOR:
        if level <= 0:
            return None, ""
        stair = stair_to(grid, here) or next(
            (tuple(f["squares"][0]) for f in grid.fixtures
             if kinds()[f["kind"]].get("stair")), None)
        if stair is None:
            return None, ""
        spots = [stair] if free(stair) else nearest(beside([stair]), stair)
        if not spots:
            return None, "There is no clear floor at the foot of the stair to step down to."
        return (*spots[0], 0), ""

    found = [f for f in grid.fixtures if f["kind"] == kind]
    if not found:
        return None, ""
    k = kinds()[kind]
    f = min(found, key=lambda f: min(distance(here[:2], tuple(p)) for p in f["squares"]))
    squares = [tuple(p) for p in f["squares"]]
    name = f["name"]
    if here[:2] in squares and level == f["level"]:
        return None, ""
    if "blocked" in k["occupies"] and set(squares) <= grid.blocked:
        # In a fight, the side of it away from the foes: the Copper Kettle, 2026-11-12,
        # "I step behind the bar, keeping it between me and the ogre" stood the player on
        # the ogre's side. Any side does out of a fight (the nearest).
        foes = [(tuple(scene.positions[r]), scene.actors[r].size)
                for side, refs in (getattr(scene, "sides", None) or {}).items()
                if who.ref not in refs for r in refs
                if r in scene.positions and r in scene.actors
                and scene.actors[r].hp > 0]
        foes = foes if any(who.ref in refs for refs in (scene.sides or {}).values()) else []

        def covers(p) -> int:
            """How many foes it covers this square from."""
            return sum(grid.cover_between(at, size, (*p, 0), who.size, solid_only=True)
                       != "none" for at, size in foes)

        # In a fight, within this round's movement, as the engine's move check counts it:
        # live the same day the far side was 35 ft off with 30 ft to spend, every plan was
        # refused and the turn fell to narration after seven attempts.
        reach = None
        if getattr(scene, "in_encounter", False):
            reach = set(grid.reachable(here[:2], who.speed_feet, size=who.size,
                                       occupied=taken)) | {here[:2]}
        # The nearest of the kind they can reach a side of, and on it the side covered from
        # the most foes, then the nearest side. The owner, 2026-11-12: "if i say go to the
        # nearest stall that is were i should go unless its not possible for some reason"
        # — the walk had crossed the market to a stall hiding them from both thugs. Tried
        # first and dropped for that: the most-covered square of any stall in the room.
        for g_ in sorted(found, key=lambda g_: min(distance(here[:2], tuple(p))
                                                    for p in g_["squares"])):
            sq = [tuple(p) for p in g_["squares"]]
            ring = beside(sq)
            if any(distance(here[:2], p) <= 5 for p in sq) and level == 0:
                ring.append(here[:2])         # already standing at it
            spots = sorted((p for p in ring if reach is None or p in reach),
                           key=lambda p: (-covers(p), distance(here[:2], p), p))
            if not spots:
                continue                      # no side of this one in reach: the next
            # Its covered side out of reach is "not possible", not a walk into the open:
            # the next live try stood the player on the one side of the bar in reach,
            # beside the bruiser (AC 15, sapped).
            if foes and not covers(spots[0]) and any(covers(p) for p in ring):
                return None, f"{who.name} cannot reach the far side of {g_['name']} this round."
            if spots[0] == here[:2]:
                return None, ""               # no square of it is better than where they are
            return (*spots[0], 0), ""
        return None, f"There is no clear floor beside {name} that {who.name} can reach."
    origin = tuple(f["stair"]) if f.get("stair") else here[:2]
    spots = nearest([p for p in squares if free(p)], origin)
    if not spots:
        return None, f"There is no room on {name}: somebody stands on every square of it."
    return (*spots[0], grid.ground(spots[0])), ""


def where_said(grid: Grid | None, start, end) -> str:
    """Where a move left its walker in words, for the move's tell: "up onto the wall-walk",
    "onto the stair", "back down to the floor", or "". The tell is all the narrator and the
    tells check know of a move (the third law); "moves to near (25 ft)" said nothing a
    page putting the player on the wall-walk could contradict (the gate, 2026-11-11)."""
    if grid is None or end is None:
        return ""
    end = tuple(end)
    now = end[2] if len(end) > 2 else grid.ground(end)
    was = (start[2] if start is not None and len(start) > 2
           else grid.ground(tuple(start)[:2]) if start is not None else 0)
    f = at(grid, end)
    if now < was and now == 0:
        return "back down to the floor"
    if f is not None and f["level"] > 0 and now > was:
        return f"up onto {f['name']}"
    if f is not None and kinds()[f["kind"]].get("stair"):
        return f"onto {f['name']}"
    if now or start is None or tuple(start)[:2] == end[:2] or not grid.fixtures:
        return ""
    from .grid import distance

    # A walk across the floor ends beside something or in the open, said: "Pip moves to
    # near (15 ft)." alone was dressed live (2026-11-12, "I walk over to L9") as "moving
    # toward the figure in the distance ... within fifteen feet of the one you seek" — a
    # destination and a purpose nobody had. The nearest fixture a step away names the spot.
    near = sorted((min(distance(end[:2], tuple(p)) for p in g["squares"]), g["name"])
                  for g in grid.fixtures if not g.get("level"))
    near = [n for n in near if n[0] <= 5]
    return f"beside {near[0][1]}" if near else "out in open ground"


# --- posts: where a person stands when they come into a room -------------------------
#
# Reported 2026-11-11 with a picture of the market: every stallholder stood in a ring
# round the player, because an arrival was put at its zone's distance from the PC and
# nothing else (`Scene.place_by_zone`). A trader belongs behind their own stall.
#
# Prior art: the Creation Kit links an NPC to furniture or an idle marker it OWNS, and a
# sandboxing NPC only uses markers nobody owns (ck.uesp.net, Sandbox Package, IdleMarker);
# The Sims' smart objects advertise what they offer and people go to them. Here a fixture
# is the marker: a stall or a counter is owned by its keeper, a table or a hearth is
# anybody's. Nothing is stored: the post is derived on arrival, and the square it gives
# is then the person's own until they move (the 2026-09-28 ruling).
_SELLS = ("stall", "counter")
_GATHER = ("table", "hearth", "counter", "stall", "barrel", "cart", "crate", "bookshelf", "rack")


def post_for(scene, actor, taken) -> tuple | None:
    """The square this person would be standing on when the party walks in, or None.

    A market counter's keeper stands behind a stall of their own (one keeper a stall);
    any other keeper behind the place's counter, else its stall; everyone else beside a
    table, the hearth or a stall front — never in a ring round the player."""
    from . import keepers

    grid = getattr(scene, "grid", None)
    if grid is None or not grid.fixtures:
        return None
    pc = scene.pc()
    pcsq = scene.positions.get(pc.ref) if pc is not None else None
    centre = (grid.width / 2, grid.height / 2)

    def free(p) -> bool:
        return (grid.inside(p) and p not in grid.blocked and p not in grid.difficult
                and grid.ground(p) == 0 and p not in taken
                and not (pcsq and max(abs(p[0] - pcsq[0]), abs(p[1] - pcsq[1])) < 2))

    def around(f):
        return sorted({q for s in f["squares"] for q in (
            (s[0] + 1, s[1]), (s[0] - 1, s[1]), (s[0], s[1] + 1), (s[0], s[1] - 1)) if free(q)})

    def far(q):          # behind a counter is the side away from the middle of the room
        return (q[0] - centre[0]) ** 2 + (q[1] - centre[1]) ** 2, q

    ground = [f for f in grid.fixtures if f["level"] == 0]
    wid = str(getattr(actor, "world_entity_id", "") or "")
    seed = floorplan._seed(str(actor.ref) + wid)
    if keepers.is_keeper(wid):
        counter = keepers.counter_of(wid)
        # A place's one keeper keeps no stall: the bar if there is one; in a market (stalls,
        # no bar) the open ground near the middle. Live 2026-11-11 the market's master
        # stood at a stall and read as a trader. A smith or librarian falls through to the
        # hearth or the shelves below.
        order = ("stall", "counter") if counter else ("counter",)
        for kind in order:
            posts = [f for f in ground if f["kind"] == kind]
            if counter:
                # One keeper a stall: a stall with a keeper beside it is theirs.
                kept = {tuple(p) for r, p in scene.positions.items()
                        if keepers.counter_of(getattr(scene.people.get(r), "world_entity_id",
                                                      "") or "")}
                posts = [f for f in posts if not any(
                    max(abs(k[0] - s[0]), abs(k[1] - s[1])) <= 1
                    for k in kept for s in f["squares"])] or posts
            start = seed % len(posts) if posts else 0
            for f in posts[start:] + posts[:start]:
                spots = around(f)
                if spots:
                    return max(spots, key=far)[:2]
        if not counter and any(f["kind"] == "stall" for f in ground):
            open_ = [(x, y) for x in range(grid.width) for y in range(grid.height)
                     if free((x, y))]
            stood = {q for f in ground for s in f["squares"] for q in (
                (s[0] + dx, s[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))}
            if open_:
                return min(open_, key=lambda q: (q in stood, far(q)))
    # Everyone else goes to the least crowded table, hearth or stall front, ties broken by
    # their own seed. Measured live 2026-11-11: picking from "the fronts nearest the middle"
    # put five of the market's six shoppers round one stall.
    here = [p for r, p in scene.positions.items() if r != getattr(pc, "ref", None)]
    best = None
    for i, f in enumerate(f for f in ground if f["kind"] in _GATHER):
        spots = around(f)
        if not spots:
            continue
        crowd = sum(1 for p in here if any(max(abs(p[0] - s[0]), abs(p[1] - s[1])) <= 1
                                           for s in f["squares"]))
        rank = (crowd, (i * 7919 + seed) % 101)
        if best is None or rank < best[0]:
            best = (rank, min(spots, key=far))     # its front nearest the middle
    return best[1][:2] if best else None
