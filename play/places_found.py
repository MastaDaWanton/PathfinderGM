"""The places the player has found: the fog-of-war place chart's data (`scene.places_found`).

The owner, 2026-09-29, on the table mock's Map mode: "the fog of war only being able to
see places conected to where you have been before … instead of displaying the number of
places the rules know you display the number of places found by the user", and earlier,
"new place[s] that the engine creates should be added to this map". Settled in the
register (docs/fix-interfaces.md, "The place map, with fog of war"): (a) one exit beyond
EVERY place you have been; (b) those neighbours shown by name; the header counts places
FOUND. The approved drawing is `docs/mock/table-layout/places.js`; this is its data, read
off the engine instead of a `sessionStorage` set and a frozen `data.js`.

**Where it comes from.** Two things, both already the engine's:

- `Scene.been` — every place the party has stood in, written by `Scene.stand`, the one
  door every arrival goes through (a walk, a journey, calling on a house, a start, a
  load). The only new state. It is the player's knowledge, never world data: World Bible
  still exports every place and `places.for_scene` still derives them all.
- `exits.ways_from` — the "From here" row as it would read standing in any place, one
  body with `exits.exits`. So the chart can never draw a way the row would not offer, or
  grey one the row would let through, and every place the engine makes later — founded,
  ventured, a shop, a crossroads, the outskirts ring, a road head — is on it the first
  time a way to it leaves somewhere the player has been, because the graph is read live
  on every state and nothing here is cached.

**What the traditions did, and what was taken from each.**

- *MUD automappers* (Mudlet, https://wiki.mudlet.org/w/Manual:Mapper): the map is built
  from where the player actually walked, and a room can carry **exit stubs** — "draw exit
  directions even though the exit rooms have not yet been defined". Those are `stubs`
  here: a way out of a place you have only seen, whose far end is not known yet.
- *Inform 7* (Writing with Inform §6.14, https://ganelson.github.io/inform-website/book/
  WI_6_14.html; Recipe Book §3.1): a room is `visited` or `unvisited`, one bit the world
  model keeps for the player, and `the best route from X to Y through visited rooms` is
  the route-finder over it. `walk` here is that phrase: breadth-first, through places you
  have been. Inform's condition "applies to both ends of the journey"; here the far end
  may be a place only seen, because the way to it leaves a place you have been — the
  mock's rule, and the owner's "one exit beyond".
- *Roguelikes*: Brogue keeps DISCOVERED apart from MAGIC_MAPPED and VISIBLE per cell,
  plus what the player *remembers* of it (`rememberedAppearance`, BrogueCE
  src/brogue/Rogue.h) — known-by-having-seen kept apart from known-by-being-told. Here
  `visited` (stood in) is kept apart from seen (one way from somewhere stood in), and the
  chart draws them differently. **Abandoned there, refused here:** NetHack 3.7 took map
  amnesia out (the "Major amnesia revamp", NetHack commit 04c59ff; `forget_map` and the
  FORGOTTEN flag removed) because forgetting a map is defeated by a player writing it
  down. So `been` only grows: no effect, no duration, nothing that forgets.
- *Etrian Odyssey*: the player draws the floor map by hand. IV fills in the floor tiles
  walked on; the Untold remakes added an option to fill the walls too, because stopping
  every few steps to draw them was tedious — and the player still places every marker
  (player reports on GameFAQs' Untold and IV boards, not a primary source). Nothing here
  is drawn by the player; what is kept from it is that the automatic part fills in only
  what was walked.

Could not confirm from a primary source: whether any MUD client *hides* rooms one exit
beyond the walked ones by default (Mudlet draws only rooms a script has created); the
"one exit beyond" rule is the owner's, not borrowed.

**Why on `/api/state` and not its own endpoint.** It changes on exactly the turns the
state changes (a move, a founded place, the watch taking up a warrant), and the exits row
beside it is already rebuilt there every state; a second request would be a second chance
for the chart and the row to disagree. Measured 2026-09-30 on Zhilvarnia (Pangrella, 43
places): 11–23 ms a state for a fresh campaign and a few walks, 27 ms with every place
visited — against a turn that waits on a local model for tens of seconds.

**The shape** (`{}` when the party stands nowhere):

    {
      "where":   "Zhilvarnia",          # the settlement the chart is of
      "here":    "<place id>",           # where the party stands
      "found":   9,                      # nodes: places visited + places seen
      "visited": 1,                      # of them, places stood in
      "nodes": [{"id", "name", "setting",   # setting: in / under / outside
                 "visited": bool, "current": bool,
                 "near": bool,              # one way from where the party stands
                 "i": int,                  # index into `layout` (below)
                 "walk": {"legs": [leg, ...], "minutes": int} | None,
                 "why": str}],              # when walk is None: why not (else "")
      "edges": [{"from", "to", "group",     # group: next_door / outside
                 "dashed": bool,            # outside the walls: drawn dashed
                 "time_words", "minutes",
                 "shut": str}],             # the rules' own sentence, "" when open
      "stubs": [{"from", "group", "dashed", "toward": int | None}],
      "roads": [{"from", "to", "name", "time_words", "shut"}],
      "layout": {"size": int, "links": [[i, j], ...]},
    }

- `edges` are the ways out of places you have been, one per direction: a pair walked
  both ways is two edges, since a way can be shut in one direction only (the watch
  stands at the way OUT). Draw one line per pair; a bar where `shut` is set.
- `stubs` are the ways out of places only seen, to anywhere not stood in: the way is
  there, where it goes is not known (the mock draws a short stroke into the paper,
  dashed when `dashed`). `toward` is the index of the hidden end in `layout`, so the
  stroke can point the right way without the page learning its name; None for a road.
- `roads` are journeys (days, not minutes) leaving from places you have been; the chart
  is of one settlement, and whether places across settlements join one map is the
  register's open question (c).
- `layout` is the whole live graph WITHOUT names or ids: the count of places and which
  indices are joined (`Place.exits`, both ways). The mock lays the chart out once over
  the whole town so a place never moves when more is found, and that needs the shape of
  what is not found yet. The indices are the places' sorted ids, so nothing about an
  unfound place but its links crosses to the page. `size` is for the layout only: the
  owner ruled that the header shows places found, never the number the rules know.
- `walk` legs are `{"from", "to", "name", "time_words", "minutes"}`, through places you
  have been, never through a shut way or a journey. `minutes` is the engine's own hop
  time (`outskirts.hop_minutes`, the same the exits row words), so "About N minutes on
  foot" is not a guess from words as it was in the mock.
"""
from __future__ import annotations

from collections import deque

from . import exits as exits_mod


def chart(engine, world) -> dict:
    """The fog-of-war chart for where the party stands. `{}` when it stands nowhere."""
    from rules import places as places_mod

    scene = engine.scene
    if not str(scene.at or ""):
        return {}
    known = engine.places()
    by_id = {p.id: p for p in known}
    here = engine.here()
    # The chart is of the live graph from where the party stands: a place stood in that is
    # not in it (another settlement, a reach of wild ground left behind) is not drawn.
    visited = [pid for pid in scene.places_been() if pid in by_id]
    if here.id not in visited:
        visited.append(here.id)
    been = set(visited)

    ways = exits_mod.ways_from(engine, world, visited)
    seen: list[str] = []
    for pid in visited:
        for row in ways.get(pid, ()):
            if row["journey"] or row["id"] not in by_id:
                continue
            if row["id"] not in been and row["id"] not in seen:
                seen.append(row["id"])
    ways.update(exits_mod.ways_from(engine, world, seen))

    index = {pid: i for i, pid in enumerate(sorted(by_id))}
    near = {row["id"] for row in ways.get(here.id, ()) if not row["journey"]}

    edges, roads, stubs = [], [], []
    for pid in visited:
        for row in ways.get(pid, ()):
            if row["journey"]:
                roads.append({"from": pid, "to": row["id"], "name": row["name"],
                              "time_words": row["time_words"], "shut": row["blocked"]})
            elif row["id"] in by_id:
                edges.append({"from": pid, "to": row["id"], "group": row["group"],
                              "dashed": row["group"] != "next_door",
                              "time_words": row["time_words"],
                              "minutes": int(row["minutes"]), "shut": row["blocked"]})
    for pid in seen:
        for row in ways.get(pid, ()):
            if row["id"] in been:
                continue
            stubs.append({"from": pid, "group": row["group"],
                          "dashed": row["group"] != "next_door",
                          "toward": None if row["journey"] else index.get(row["id"])})

    nodes = []
    for pid in visited + seen:
        p = by_id[pid]
        legs, why = ([], "") if pid == here.id else route(ways, been, here.id, pid)
        nodes.append({
            "id": pid, "name": p.name, "setting": places_mod.setting_of(pid),
            "visited": pid in been, "current": pid == here.id, "near": pid in near,
            "i": index[pid],
            "walk": ({"legs": legs, "minutes": sum(x["minutes"] for x in legs)}
                     if legs else None),
            "why": why,
        })

    links = sorted({tuple(sorted((index[p.id], index[x])))
                    for p in known for x in p.exits if x in index and x != p.id})
    loc = world.get(scene.location_id) if world is not None and scene.location_id else None
    return {
        "where": str(getattr(loc, "name", "") or ""),
        "here": here.id,
        "found": len(nodes),
        "visited": len(visited),
        "nodes": nodes,
        "edges": edges,
        "stubs": stubs,
        "roads": roads,
        "layout": {"size": len(index), "links": [list(pair) for pair in links]},
    }


def route(ways: dict, been, start: str, to: str) -> tuple[list[dict], str]:
    """The walk from `start` to `to` by known ways: `(legs, "")`, or `([], why)`.

    Inform's "best route ... through visited rooms": breadth-first (fewest legs, ties on
    the order the exits row lists them, which is the engine's), leaving only places in
    `been`, never by a journey and never by a way the rules shut. When there is no open
    way but there is a shut one, `why` is the rule's own sentence for the first shut way
    on it, so the player reads the watch's reason rather than "no way".
    """
    def search(through_shut: bool):
        came = {start: None}
        queue = deque([start])
        while queue:
            cur = queue.popleft()
            if cur == to:
                break
            if cur not in been:
                continue
            for row in ways.get(cur, ()):
                if row["journey"] or row["id"] in came:
                    continue
                if row["blocked"] and not through_shut:
                    continue
                came[row["id"]] = (cur, row)
                queue.append(row["id"])
        if to not in came:
            return None
        legs, k = [], to
        while came[k] is not None:
            cur, row = came[k]
            legs.append((cur, row))
            k = cur
        return legs[::-1]

    found = search(False)
    if found:
        return ([{"from": cur, "to": row["id"], "name": row["name"],
                  "time_words": row["time_words"], "minutes": int(row["minutes"])}
                 for cur, row in found], "")
    shut = search(True)
    if shut:
        return [], next(row["blocked"] for _cur, row in shut if row["blocked"])
    return [], "No way there by the ways you know."
