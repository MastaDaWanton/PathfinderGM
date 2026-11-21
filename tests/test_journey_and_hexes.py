"""Road journeys and hex moves on one board (feat/travel-pacing, 2026-11-21).

Two layers move a party between towns: the road journey (`_op_journey`, paced in stretches
of days, content/rules/journey-events.json) and the region map's hex moves
(`_op_hex_move`, one hex and one road check at a time). The Alexandrian's layered hexcrawl
keeps a road pointmap and a hexmap "in sync" over one region; here that means one position
and one clock, so a party is never charged the same ground twice and never stands in two
places. Measured on master 0.4.6 before this file, on every fixture world:

- one hex out of town toward the next, then the journey: the journey still charged the whole
  road (Pangrella 32 hours of road for 9 hexes, all of it again after the 8-hour hex);
- and it "arrived" with the party still standing on the open-desert hex beside the town it
  had left, the far town its location.

Every test runs once per export (fixes are world-agnostic, 2026-09-28). The road's checks
are held quiet: a meeting legitimately stops a journey short.
"""
from __future__ import annotations

import pytest

from rules import hexes, journey, ontheway, outskirts, places
from tests.test_hex_travel import _move, _party


@pytest.fixture
def quiet(monkeypatch):
    monkeypatch.setattr(ontheway, "road", lambda *a, **k: None)
    monkeypatch.setattr(ontheway, "road_stretches", lambda *a, **k: None)


def _a_road(world):
    """A town with a land road out, the road, and the party standing in that town."""
    for row in world.play["settlements"]:
        for leg in journey.legs_from(world, row["id"]):
            if not leg.by_sea and leg.by not in ("sea", "river"):
                return row["id"], leg
    pytest.skip("no land road in this export")


def _journey(e, leg):
    r = e.run(e.validate([{"op": "journey", "actor": "pc", "params": {"to": leg.to_name}}]))
    return [o for o in r.outcomes if o.op == "journey"][0]


def _road_hours(s, e, leg):
    t = s.clock_minutes
    out = _journey(e, leg)
    return s.clock_minutes - t, out


def _one_hex(e, g, dest, toward=True):
    here = e.party_hex(g)
    land = [h for h in hexes.neighbours(*here) if g.cell(*h)["land"]]
    pick = min if toward else max
    return _move(e, pick(land, key=lambda h: hexes.distance(h, dest)))


def test_a_journey_from_open_ground_arrives_at_the_far_towns_way_in(worlds, quiet):
    """0.4.6: the party stood on `{town}~desert:@hex-52-m37` after "arriving" at
    Vylthysia, nine hexes away; the board and the page disagreed about where it was."""
    town, leg = _a_road(worlds)
    s, e, pc = _party(worlds, town)
    g = e.hex_world()
    _one_hex(e, g, g.town_hex[leg.to_id])
    assert hexes.parse_place(s.at) is not None
    out = _journey(e, leg)
    assert out.status == "resolved", out.tell
    assert s.location_id == leg.to_id
    assert hexes.parse_place(s.at) is None and places.location_of(s.at) == leg.to_id, s.at
    assert e.party_hex(g) == g.town_hex[leg.to_id]


def test_hexes_walked_toward_a_town_are_road_behind_you_and_away_road_to_make_up(worlds,
                                                                                  quiet):
    """0.4.6 charged the whole road whichever way the party had walked across the board:
    a hex toward the far town was paid twice, a hex away from it never. The road now
    joins where the party stands, by the share of hexes still between it and the town."""
    town, leg = _a_road(worlds)
    s, e, _pc = _party(worlds, town)
    full, _ = _road_hours(s, e, leg)

    s, e, _pc = _party(worlds, town)
    g = e.hex_world()
    a, b = g.town_hex[town], g.town_hex[leg.to_id]
    _one_hex(e, g, b, toward=True)
    near = hexes.distance(e.party_hex(g), b)
    toward, out = _road_hours(s, e, leg)
    assert near < hexes.distance(a, b)
    assert toward < full, (toward, full, out.tell)
    assert "already behind them" in out.tell, out.tell

    s, e, _pc = _party(worlds, town)
    g = e.hex_world()
    _one_hex(e, g, b, toward=False)
    if hexes.distance(e.party_hex(g), b) > hexes.distance(a, b) \
            and places.location_of(s.at) == town:
        away, out = _road_hours(s, e, leg)
        assert away > full, (away, full, out.tell)
        assert "to make up" in out.tell, out.tell


def test_a_journey_turned_back_from_open_ground_leaves_the_party_on_its_hex(worlds, quiet,
                                                                          monkeypatch):
    """The turn-back branch stood the party at the place set's first place; from a hex that
    is the hex, and it must stay so after the change that sends arrivals to the gate."""
    from rules.engine import Engine

    town, leg = _a_road(worlds)
    s, e, _pc = _party(worlds, town)
    g = e.hex_world()
    _one_hex(e, g, g.town_hex[leg.to_id])
    at = s.at
    monkeypatch.setattr(Engine, "_march", lambda self, pc, hours, biome: (False, ""))
    out = _journey(e, leg)
    assert out.status == "prevented" and s.at == at and s.location_id == town, out.tell


def test_a_journey_stopped_on_the_road_stands_on_the_board_between_the_towns(worlds, quiet,
                                                                            monkeypatch):
    """0.4.6 put a party stopped days down the road on its origin town's hex, so the hexes
    stepped onto from there were beside the gate it had left two days before."""
    from tests.test_second_look_at_the_way_there import _force

    town, leg = _a_road(worlds)
    s, e, _pc = _party(worlds, town)
    g = e.hex_world()
    a, b = g.town_hex[town], g.town_hex[leg.to_id]
    monkeypatch.undo()                      # the real stretch check, forced to hit
    monkeypatch.setattr(ontheway, "road", lambda *a, **k: None)
    _force(monkeypatch, "travellers", 2)
    out = _journey(e, leg)
    assert outskirts.is_along(s.at), (s.at, out.tell)
    assert s.road.get("of") and 0 < s.road["walked"] < s.road["of"], s.road
    h = e.party_hex(g)
    if g.cell(*hexes.along(a, b, s.road["walked"] / s.road["of"]))["land"]:
        assert h != a and hexes.distance(h, a) + hexes.distance(h, b) == hexes.distance(a, b), h


def test_a_journey_from_open_ground_is_not_told_as_a_road_taken_up_again(worlds, quiet,
                                                                         monkeypatch):
    """Live 2026-11-21 (the owner's save, a hex east of Branford to Brackgate): stopped on
    the second day, the tell read "A quiet day more on the road" on the first day out."""
    from tests.test_second_look_at_the_way_there import _force

    town, leg = _a_road(worlds)
    s, e, _pc = _party(worlds, town)
    g = e.hex_world()
    _one_hex(e, g, g.town_hex[leg.to_id])
    monkeypatch.undo()
    monkeypatch.setattr(ontheway, "road", lambda *a, **k: None)
    _force(monkeypatch, "travellers", 2)
    out = _journey(e, leg)
    assert "quiet day on the road out of" in out.tell and " more " not in out.tell, out.tell


def test_along_walks_the_straight_line_between_two_hexes():
    a, b = (0, 0), (6, -3)
    assert hexes.along(a, b, 0) == a and hexes.along(a, b, 1) == b
    line = [hexes.along(a, b, k / 6) for k in range(7)]
    assert all(hexes.distance(x, y) == 1 for x, y in zip(line, line[1:])), line
