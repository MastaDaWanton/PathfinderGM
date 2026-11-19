"""The atlas: what the place map's World, Continent and Region draw from.

Phase 1 of docs/place-map-v2-build-plan.md (the mock is `docs/mock/place-map-v2/` on branch
`mock/place-map-v2`; the owner chose its 3D tabletop on 2026-11-18). Two halves, because
they change at different rates:

- `atlas(world)` is the WORLD, which never changes in play: every settlement with its
  nation and continent, the ground round it as the engine reads it, and every journey the
  engine offers between settlements. Served once per campaign at `/api/atlas`, never on
  `/api/state`.
- `known_places(engine, world)` is the PLAYER'S knowledge, which grows with play: the
  settlements stood in, those an NPC named (`Scene.heard_towns`) and the nations whose map
  was read (`Scene.maps_read`), and the sites (caves, dungeons, sewers) found so far with the
  rooms known in each. Small, the last key of `/api/state`'s scene.

**Nothing here is a second reading of the world.** Every fact is an existing engine answer,
so the map cannot disagree with the game:

- the journeys are `journey.legs_from`, the list the travel door itself offers. Not
  `play.travel` alone: the engine derives sea passages for ports that the export never
  lists (measured on Aurvantis: Ledgernook has 17 sea legs, only 2 of them in
  `play.travel`). A leg's `by` is the route's stated way; `by_sea` is not read, because it
  is also true of river legs (3 of Ledgernook's).
- the ground is `geography.land_around` (`near`, `beyond`, and the named `reaches` with
  their miles and source), the same answer the outskirts ring is built from, so the
  region map's woods are the woods the player can walk to.
- the sites and rooms are `Engine.places()`, read through the same fog rule as
  `places_found.chart()`: rooms stood in, and rooms one passage from them. A room not yet
  seen does not cross to the page at all, so nothing of it can leak into the DOM.

**Knowledge only grows.** `been` is `Scene.places_been()`, which only grows; heard and
maps will be stores that only grow (NetHack 3.7 took map amnesia out because a player just
writes the map down; places_found.py cites the same refusal). There is no forgetting here.
"""
from __future__ import annotations

from rules import geography, journey

_MEMO: dict = {}


def _ancestry(world, entity_id: str) -> tuple[str, str]:
    """(nation id, continent id) for a settlement: its nearest ancestor and its farthest
    below the world. Read off the containment chain, never off kind names, which vary by
    export (Aurvantis calls all 64 settlements CITY; the synthetic world uses VILLAGE, TOWN
    and CITY)."""
    chain = [a for a in world.ancestors(entity_id) if str(getattr(a, "kind", "")).upper() != "WORLD"]
    if not chain:
        return "", ""
    return chain[0].id, chain[-1].id


def atlas(world) -> dict:
    """The world as the maps need it. Remembered per world object, held and compared by
    identity, as `geography.land_around` is: the world never changes during play, and
    reading every settlement's land and legs is the expensive part.

    Shape:
        {"world": name,
         "cities":  [{"id", "name", "scale", "nation", "continent",
                      "near": [...], "beyond": [...],
                      "reaches": [{"ground", "name", "miles", "source"}]}],
         "nations": {id: {"name", "continent"}},
         "continents": {id: name},
         "routes": [{"a", "b", "by", "miles", "days", "crosses": [...]}]}   # one per pair
    """
    if world is None:
        return {}
    key = id(world)
    held = _MEMO.get(key)
    if held is not None and held[0] is world:
        return held[1]
    rows = (getattr(world, "play", None) or {}).get("settlements") or []
    cities, nations, continents, routes, seen_pairs = [], {}, {}, [], set()
    for row in rows:
        entity = world.get(row.get("id"))
        if entity is None:
            continue
        nation, continent = _ancestry(world, entity.id)
        land = geography.land_around(world, entity.id)
        cities.append({
            "id": entity.id, "name": entity.name,
            "scale": str(getattr(entity, "scale", "") or row.get("scale") or ""),
            "nation": nation, "continent": continent,
            "near": list(land.near), "beyond": list(land.beyond),
            "reaches": [{"ground": r.ground, "name": r.name, "miles": r.miles, "source": r.source}
                        for r in land.reaches],
        })
        if nation and nation not in nations:
            n = world.get(nation)
            nations[nation] = {"name": getattr(n, "name", ""), "continent": continent}
        if continent and continent not in continents:
            continents[continent] = getattr(world.get(continent), "name", "")
        for leg in journey.legs_from(world, entity.id):
            pair = tuple(sorted((entity.id, leg.to_id)))
            if pair in seen_pairs or world.get(leg.to_id) is None:
                continue
            seen_pairs.add(pair)
            routes.append({"a": entity.id, "b": leg.to_id, "by": leg.by or "",
                           "miles": leg.miles, "days": leg.days_apart,
                           "crosses": list(leg.crosses)})
    got = {"world": getattr(world, "name", ""), "cities": cities, "nations": nations,
           "continents": continents, "routes": routes}
    if len(_MEMO) > 8:
        _MEMO.clear()
    _MEMO[key] = (world, got)
    return got


def _settlement_of(place_id: str) -> str:
    """The settlement a place id belongs to: the part before `~`."""
    return str(place_id or "").split("~", 1)[0]


def _underground(place_id: str) -> bool:
    return str(place_id or "").split("~", 1)[-1].startswith("underground:")


def known_places(engine, world) -> dict:
    """What the player knows of the world, for the maps. `{}` when the party stands nowhere.

    Shape:
        {"town":  the settlement the party is in ("" when none),
         "been":  [settlement ids stood in, first first],
         "heard": {settlement id: {"who", "line", "turn"}},   # named by an NPC
         "maps":  [nation ids whose map was read],
         "sites": [{"id", "name", "host", "here": room id | "",
                    "rooms": [{"id", "name", "parent", "exits": [...], "visited": bool,
                               "about": str, "role": str, "door": str,
                               "at": [column, row]}]}]}

    A room's `about`, `role` and `door` are sent only once it has been stood in: a room
    only seen is its name and its passages, as a place only seen is on the town chart.
    `at` is the room's seat on the Site map (`_site_seats`).
    """
    scene = engine.scene
    if not str(scene.at or ""):
        return {}
    settlement_ids = {row.get("id") for row in ((getattr(world, "play", None) or {}).get("settlements") or [])}
    been_places = scene.places_been()
    been = []
    for pid in been_places + [str(scene.location_id or "")]:
        sid = _settlement_of(pid)
        if sid in settlement_ids and sid not in been:
            been.append(sid)
    town = str(scene.location_id or "")
    # Told of by an NPC (rules/heard_towns.py) and read off a map (rules/maps.py). The speaker
    # goes by name only: a ref is never put on the page.
    heard = {cid: {"who": str(h.get("who") or ""), "line": str(h.get("line") or ""),
                   "turn": int(h.get("turn") or 0)}
             for cid, h in (getattr(scene, "heard_towns", None) or {}).items()
             if cid in settlement_ids and isinstance(h, dict)}
    return {"town": town if town in settlement_ids else "", "been": been, "heard": heard,
            "maps": list(getattr(scene, "maps_read", None) or []),
            "sites": _sites(engine, set(been_places)),
            "hexes": _hexes(engine)}


def _hexes(engine) -> dict:
    """The party on the region grid (rules/hexes.py): its hex, the hexes a click can move
    it to, what it did on the hexes it touched, and the sites it spotted. Small: only
    touched hexes are kept. `{}` with no world or off the map (aboard a ship)."""
    try:
        g = engine.hex_world()
        here = engine.party_hex(g) if g is not None else None
    except Exception:  # noqa: BLE001 - the map is a view; a failure must not lose the state
        import logging

        logging.getLogger("pathfindergm").exception("the hex grid failed")
        return {}
    if g is None or here is None:
        return {}
    from rules import hexes

    held = engine.scene.hexes or {}
    return {"party": list(here), "nation": g.cell(*here)["nation"],
            "reach": [list(h) for h in engine.hex_reach(g)],
            "rides": engine.party_rides(),
            "touched": {k: {"entered": "entered" in v, "searched": "searched" in v,
                            "explored": bool(v.get("explored"))}
                        for k, v in (held.get("touched") or {}).items()},
            "spotted": dict(held.get("spotted") or {}),
            "in_site": hexes.in_site(engine.scene.at or "", here),
            "site_here": (held.get("spotted") or {}).get(hexes.key(*here), "")}


def _sites(engine, been: set) -> list[dict]:
    """Every site under or round the settlement the party is in, with the rooms the fog
    lets through: a site's root is an underground place whose parent is not underground
    (the cave off the woods, the sewers under the well); its rooms are the root and every
    place beneath it by id. A room is sent when it has been stood in, or when it is one
    passage (parent, child or exit) from one that has; a site is sent when any room is."""
    known = {p.id: p for p in engine.places()}
    founded = {d.get("id"): d for d in (engine.scene.founded or []) if isinstance(d, dict)}
    roots = [p for p in known.values() if _underground(p.id) and not _underground(p.parent)]
    out = []
    for root in sorted(roots, key=lambda p: p.id):
        rooms = {pid: p for pid, p in known.items() if pid == root.id or pid.startswith(root.id + "/")}
        links: dict[str, set] = {pid: set() for pid in rooms}
        for pid, p in rooms.items():
            if p.parent in rooms:
                links[pid].add(p.parent)
                links[p.parent].add(pid)
            for x in p.exits:
                if x in rooms:
                    links[pid].add(x)
                    links.setdefault(x, set()).add(pid)
        visited = {pid for pid in rooms if pid in been}
        # The way in: a site whose root's host place has been stood in shows its root,
        # as the chart shows a place one way from somewhere stood in.
        host = root.parent
        if not visited and host not in been:
            continue
        seen = {x for pid in visited for x in links[pid]} - visited
        if not visited:
            seen = {root.id}
        here = engine.scene.at if engine.scene.at in rooms else ""
        seat = _site_seats(rooms, root.id)
        sent = []
        for pid in sorted(visited | seen):
            p, f = rooms[pid], founded.get(pid) or {}
            dungeon = f.get("dungeon") or {}
            entered = pid in visited
            sent.append({
                "id": pid, "name": p.name,
                "parent": p.parent if p.parent in (visited | seen) else "",
                "exits": sorted(x for x in links[pid] if x in (visited | seen) and x != p.parent
                                and rooms[x].parent != pid),
                "visited": entered,
                "about": p.about if entered else "",
                "role": str(dungeon.get("role") or "") if entered else "",
                "door": str(((dungeon.get("door") or {}).get("state")) or "") if entered else "",
                "at": seat[pid],
            })
        out.append({"id": root.id, "name": root.name, "host": host, "here": here, "rooms": sent})
    return out


def _site_seats(rooms: dict, root: str) -> dict[str, list]:
    """Each room's seat on the Site map, `[column, row]`: Darkest Dungeon's corridor map as
    the mock laid it, depth in the room tree the column and the order of the leaves the row,
    a room with rooms beneath it centred on them. Dealt over EVERY room of the site, found
    or not, as the town's seats are (play/town_seats.py), so finding a room never moves one
    already drawn; the page is sent the seats of the rooms the fog lets through only."""
    kids: dict[str, list] = {}
    for pid, p in rooms.items():
        if pid != root and p.parent in rooms:
            kids.setdefault(p.parent, []).append(pid)
    seat: dict[str, list] = {}
    leaves = [0]

    def deal(pid: str, depth: int, path: frozenset) -> float:
        below = [k for k in sorted(kids.get(pid, ())) if k not in path]
        if not below:
            row = float(leaves[0])
            leaves[0] += 1
        else:
            rows = [deal(k, depth + 1, path | {pid}) for k in below]
            row = (min(rows) + max(rows)) / 2
        seat[pid] = [depth, row]
        return row

    deal(root, 0, frozenset())
    # A room whose parent is outside the site (none in play today) still gets a seat, below.
    for pid in sorted(rooms):
        if pid not in seat:
            seat[pid] = [0, float(leaves[0])]
            leaves[0] += 1
    return seat
