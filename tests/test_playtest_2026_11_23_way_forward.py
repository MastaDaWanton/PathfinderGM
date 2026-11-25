"""The way forward, seen and chosen: playtest 2026-11-23 items 5, O2, O3 and O5.

The owner: "I cannot find/see the way forward through narration even when the way forward
exists, I should be able to inspect the doors or hallways that lead to different places in
order to make a decision on where I want to go." In the record, "I search the area for the
way down" answered "does not find it here" beside the locked trapdoor named on arrival,
and "I look around for the different ways to go" answered the same in a room with three
ways out. The tower's rooms never reached the Site map (O3: `known_places.sites` was []
standing in the death room), and the pit trap found at t=231 was on no map (O5).
Research: docs/research/2026-11-25-way-forward.md.
"""
from __future__ import annotations

import re

from gm import acts_to_ops, interpret
from play import atlas, places_found
from rules import dungeons, places
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

VYRAKON = "5bbd0c40345f"
WORLD = loader.load_cached("fixtures/pangrella-campaign.json")


def _below():
    """A party at a spot with a dungeon's rooms behind a stuck trapdoor (the ruins row)."""
    s = Scene(location_id=VYRAKON)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=4), world=WORLD)
    e.place_party("")
    spot = e.here()
    rooms = dungeons.generate("~ruins:x/the-ruins", "ruins", spot.id, "ruins",
                              dungeons.FEATURES["ruins"][0], 1)
    s.founded.extend(rooms)
    return s, e, spot, rooms


def _search(e, sought, seeking):
    params = {"skill": "perception", "search": True, "take": 10, "sought": sought,
              "seeking": seeking}
    r = e.run(e.validate([{"op": "check", "actor": "pc", "params": params}]))
    return [o for o in r.outcomes if o.op == "check"][0]


def test_a_search_for_the_way_down_names_the_shut_trapdoor_that_is_it():
    """#177: "I search the area for the way down", read `seeking: a place`, said "does not
    find it here" beside the locked trapdoor. Now the ways on are told, the trapdoor shut
    with the book's way to open it, and nothing says the way down is missing."""
    s, e, spot, rooms = _below()
    out = _search(e, "the way down", "a place")
    first = rooms[0]
    assert f"The way to {first['name']} is shut." in out.tell, out.tell
    assert "The trapdoor is stuck" in out.tell and "Strength" in out.tell
    assert "does not find" not in out.tell


def test_looking_for_the_ways_to_go_tells_every_way_out_and_what_is_seen_beyond():
    """#214: "I look around for the different ways to go inspecting them" was "not found"
    in a room with three ways out. Every exit is told; through an open way the room beyond
    is in sight, through a shut door it is not ("A closed door blocks line of sight")."""
    s, e, spot, rooms = _below()
    first = rooms[0]
    first["dungeon"]["door"]["state"] = "open"
    s.move("pc", first["id"])
    s.at = first["id"]
    here = places.find(e.places(), first["id"])
    nxt = [r for r in rooms if r["parent"] == first["id"]]
    nxt[0]["dungeon"]["door"] = {"name": "a good wooden door", "state": "stuck", "force": 16}
    if len(nxt) > 1:
        nxt[1]["dungeon"]["door"] = {"name": "a good wooden door", "state": "open"}
    out = _search(e, "the different ways to go", "a door or way on")
    assert len(re.findall(r"The way (?:back )?to ", out.tell)) == len(here.exits), out.tell
    assert f"The way back to {spot.name}" in out.tell
    assert nxt[0]["about"] not in out.tell                     # behind a shut door
    if len(nxt) > 1:
        assert f"In sight beyond: {nxt[1]['about']}" in out.tell
    assert "does not find" not in out.tell


def test_inspecting_one_door_is_a_search_of_that_way_only():
    """"I inspect the trapdoor": a look at a way out of here, by the door's own noun,
    builds the engine's search for that way, and the answer is that way alone."""
    s, e, spot, rooms = _below()
    frame = {"actions": [{"act": "look", "object": "the trapdoor",
                          "span": "inspect the trapdoor"}]}
    rows = acts_to_ops.table(frame, s, places=e.places(), sentence="I inspect the trapdoor")
    built = [b for r in rows for b in r.intents if b["op"] == "check"]
    assert built and built[0]["params"]["seeking"] == "a door or way on", rows
    out = _search(e, built[0]["params"]["sought"], "a door or way on")
    assert len(re.findall(r"The way (?:back )?to ", out.tell)) == 1, out.tell
    assert "trapdoor" in out.tell
    assert "a door or way on" in interpret.SEEKING


def test_a_found_trap_is_told_on_its_way_and_sent_to_both_maps():
    """O5: the pit trap found from the cold hall was on no map. A found, armed trap rides
    on the chart's node and the Site room, entered or not; an unfound one is never sent."""
    s, e, spot, rooms = _below()
    first = rooms[0]
    first["dungeon"]["door"]["state"] = "open"
    first["dungeon"]["trap"] = {"id": "pit-trap", "on": "room", "found": False, "armed": True}
    assert dungeons.found_trap(s, first["id"]) == ""
    first["dungeon"]["trap"]["found"] = True
    assert dungeons.found_trap(s, first["id"]) == "a pit trap"
    assert "A pit trap was found there." in dungeons.way_line(e, spot.id, first["id"])
    pf = places_found.chart(e, WORLD)
    node = next(n for n in pf["nodes"] if n["id"] == first["id"])
    assert node["trap"] == "a pit trap"
    first["dungeon"]["trap"]["armed"] = False                  # sprung or disarmed
    assert dungeons.found_trap(s, first["id"]) == ""


def test_a_ruins_venture_is_a_site_on_the_map_and_the_rooftops_are_not():
    """O3: `_sites` took only `underground:` roots, so the tower (a `ruins:` venture on its
    hex) and its rooms below the trapdoor never reached the Site map. A venture's head off
    non-town ground is a site; the rooftops are town ground and stay on the town chart."""
    s = Scene(location_id=VYRAKON)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=4), world=WORLD)
    e.place_party("")
    e.run(e.validate([{"op": "venture", "actor": "pc", "because": "t",
                       "params": {"kind": "ruins"}, "visibility": "hidden"}],
                     origin="author:test"))
    head = next(p for p in s.founded if p["id"] == s.at)
    rooms = dungeons.generate(head["id"], "ruins", head["id"] + "/the-gate", "ruins",
                              dungeons.FEATURES["ruins"][0], 1)
    rooms[0]["dungeon"]["trap"] = {"id": "pit-trap", "on": "room", "found": True,
                                   "armed": True}
    s.founded.extend(rooms)
    sites = atlas.known_places(e, WORLD)["sites"]
    site = next((st for st in sites if st["id"] == head["id"]), None)
    assert site is not None, [st["id"] for st in sites]
    assert any(r["id"] == head["id"] for r in site["rooms"])
    known = {p.id: p for p in e.places()}
    roof = next((p for p in known.values() if p.name == "the rooftops"), None)
    if roof is not None:
        assert not atlas._site_root(roof, known)


def test_a_search_the_reader_gave_no_kind_still_tells_the_ways_on():
    """Live 2026-11-25 on the owner's save: the same #214 line was read with no `seeking`
    at all, and the answer was "does not find it here" in the cold hall, three ways out.
    Words that name nothing on the record, and nothing hidden found: the ways on follow."""
    s, e, spot, rooms = _below()
    out = _search(e, "the different ways to go", "")
    assert "finds nothing here by that name" in out.tell, out.tell
    assert f"The way to {rooms[0]['name']} is shut." in out.tell


def test_a_room_named_the_room_that_moves_is_not_a_roof_under_the_open_sky():
    """Live 2026-11-25 on the owner's save: the beat naming the ways out of the cold hall
    lost "the open wooden door leading to the room that moves", cut by the setting check
    as "the room" furnished under the open sky (the owner's record at t=231 was "repaired"
    to "the hall that moves" the same way). A cue inside a longer place name the engine
    holds is the place's name; the bare furniture is still caught."""
    from gm.checks import setting_kind

    names = {"the room that moves", "the cold hall"}
    line = "You note the open wooden door leading to the room that moves."
    assert setting_kind.cues_in(line, set(), False, names) == []
    assert setting_kind.cues_in("Dust drifts from the ceiling.", set(), False, names) \
        == ["the ceiling"]
