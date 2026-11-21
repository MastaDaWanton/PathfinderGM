"""The exits row offers only the rooms the party could know (playtest 2026-11-20 #21;
research note docs/research/2026-11-21-dungeon-exits.md).

A hex site's places sit under its `@hex` root, which `places.is_ring` reads as a
settlement's ring, so the row's "the rest of the ring" pass listed every room of the
dungeon, unblocked, from the moment the way down was found. The same pass runs for a
venture off a town's outskirts (the town dungeons of 0.3.7), whose ids are under `@`.

Every test runs once per export (`worlds`): fixes are world-agnostic (2026-09-28).
"""
from __future__ import annotations

import pytest

from play import exits as exits_mod
from play import places_found
from rules import dungeons, hexes, ontheway
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene


@pytest.fixture
def quiet_road(monkeypatch):
    monkeypatch.setattr(ontheway, "road", lambda *a, **k: None)


def _at_a_site(world, seed=3):
    s = Scene(location_id=world.play["settlements"][0]["id"])
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = 60
    s.add(pc)
    e = Engine(s, Dice(seed=seed), world=world)
    e.place_party("")
    g = e.hex_world()
    to = next((h for h in e.hex_reach(g) if hexes.site_of(g, *h)), None)
    if to is None:
        pytest.skip("no site beside this town")
    r = e.run(e.validate([{"op": "hex_move", "actor": "pc", "params": {"hex": list(to)}}]))
    if r.awaiting:
        e.resume(20)
    r = e.run(e.validate([{"op": "hex_enter", "actor": "pc", "params": {}}]))
    assert [o for o in r.outcomes if o.op == "venture"][0].status == "resolved"
    head = next(p for p in s.founded if p["id"] == s.at)
    if not head["deeper"]["found"]:
        dungeons._found(e, head, head["deeper"])
    rooms = [p for p in s.founded if (p.get("dungeon") or {}).get("of") == head["id"]]
    entrance = next(p for p in rooms if p["dungeon"]["role"] == "entrance")
    return s, e, head, rooms, entrance


def _room_rows(e, world, rooms):
    ids = {p["id"] for p in rooms}
    return [r for r in exits_mod.exits(e, world) if r["id"] in ids]


def test_found_way_down_offers_only_its_first_room(worlds, quiet_road):
    """Playtest 2026-11-20 #21: at the ruins with the trapdoor found and still stuck, the row
    named every room below, down to the climax ("the plague pit"), as minutes' walks.
    Measured on Aurvantis before the fix: four rooms past the stuck trapdoor were listed,
    none of them shut. Only the room beyond the way down is a way on, and while its door is
    shut the row says so in the door's own sentence."""
    s, e, head, rooms, entrance = _at_a_site(worlds)
    rows = _room_rows(e, worlds, rooms)
    assert [r["id"] for r in rows] == [entrance["id"]], [r["name"] for r in rows]
    if (entrance["dungeon"].get("door") or {}).get("state", "open") != "open":
        assert rows[0]["blocked"]


def test_a_room_joins_the_row_when_its_way_opens_and_it_is_stood_beside(worlds, quiet_road):
    """The rooms come into being in play: the first room's row opens the moment its door
    gives, and the rooms past it join only once the party stands in the room they open
    from. Back at the head, a room already stood in is a way on again, by the walk."""
    s, e, head, rooms, entrance = _at_a_site(worlds)
    door = entrance["dungeon"].get("door")
    if door and door["state"] != "open":
        r = e.run(e.validate([{"op": "break_in", "actor": "pc", "params": {"how": "force"}}]))
        if r.awaiting:
            e.resume(20)
        assert door["state"] == "open"
    assert not _room_rows(e, worlds, rooms)[0]["blocked"]
    r = e.run(e.validate([{"op": "travel", "actor": "pc",
                           "params": {"place": entrance["name"]}}]))
    assert s.at == entrance["id"], [o.tell for o in r.outcomes]
    beside = {p["id"] for p in rooms if p.get("parent") == entrance["id"]}
    assert {r["id"] for r in _room_rows(e, worlds, rooms)} == beside
    e.place_party(head["id"])
    assert entrance["id"] in {r["id"] for r in _room_rows(e, worlds, rooms)}
    assert not beside & {r["id"] for r in _room_rows(e, worlds, rooms)
                         if r["id"] not in s.been}


def test_the_fog_chart_does_not_name_rooms_below_either(worlds, quiet_road):
    """The place chart reads the same rows (`ways_from`), so it named every room too."""
    s, e, head, rooms, entrance = _at_a_site(worlds)
    named = {n["id"] for n in places_found.chart(e, worlds).get("nodes", ())}
    assert named & {p["id"] for p in rooms} <= {entrance["id"]}


def test_a_shut_door_on_the_way_stops_the_walk_offered_across_the_ring(worlds, quiet_road):
    """Even a room stood in before is not offered by a walk that goes through a shut door:
    the row must never offer a click the per-hop door check would refuse."""
    s, e, head, rooms, entrance = _at_a_site(worlds)
    deep = next(p for p in rooms if p.get("parent") == entrance["id"])
    s.been.append(deep["id"])
    entrance["dungeon"]["door"] = {"name": "the trapdoor", "state": "stuck", "force": 16}
    assert deep["id"] not in {r["id"] for r in exits_mod.exits(e, worlds)}
