"""The road to the harbour is walked (`Engine.road_to_the_coast`, `_op_journey`).

Measured in 0.3.2 (2026-11-14): booking Vormoor to Ledgerwarren by sea, from inland
Vormoor, stood the party on a deck with **0 minutes** on the clock — no march, no road
check, no camp — while Vormoor's road to its nearest port (Scrapden, 96 miles) is five
days on foot. Of Aurvantis's 52 stated sea legs that start inland, 36 also END inland, so
"walk to the port and book there" would strand them (no port sells a berth to an inland
town): the player books where they stand and the journey op walks them to the harbour.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from rules import goods, journey, ontheway
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

AURVANTIS = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = "bde94b038cba"


def _id(name: str) -> str:
    return next(s["id"] for s in AURVANTIS.play["settlements"] if s["name"] == name)


SCRAPDEN, LEDGERWARREN, MOLDWARREN = (_id("Scrapden"), _id("Ledgerwarren"),
                                      _id("Moldwarren"))


def _at_vormoor(gp: int = 500):
    scene = Scene(location_id=VORMOOR)
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    engine = Engine(scene, Dice(seed=4), world=AURVANTIS)
    engine.place_party()
    pc.purse = {"gp": gp}
    return scene, engine, pc


def _journey(engine, to: str):
    engine._journeyed = ""
    res = engine.run(engine.validate(
        [{"op": "journey", "actor": "pc", "because": "passage", "params": {"to": to}}],
        origin="author:test"))
    return res.outcomes[-1]


@pytest.fixture
def quiet_road(monkeypatch):
    """The road's own check, recorded and answered "nothing happens"."""
    asked: list[int] = []

    def road(dice, hours, *a, **k):
        asked.append(hours)
        return None

    monkeypatch.setattr(ontheway, "road", road)
    return asked


def test_the_coast_road_is_the_quickest_road_to_a_port():
    sea = journey.find(journey.legs_from(AURVANTIS, VORMOOR), "Ledgerwarren")
    assert sea.by_sea and not sea.from_port
    coast = journey.coast_road(AURVANTIS, VORMOOR, sea)
    assert coast.to_id == SCRAPDEN and not coast.by_sea
    # From a port there is no road first.
    assert journey.coast_road(AURVANTIS, SCRAPDEN, replace(sea, from_port=True)) is None


def test_booking_inland_walks_the_road_then_boards_at_the_harbour(quiet_road):
    """0.3.2: 0 minutes on the clock and a deck in Vormoor. Now the five days' road to
    Scrapden is marched (the road's check asked for exactly its hours), and the berth is
    bought at Scrapden's quay at Scrapden's price."""
    scene, engine, pc = _at_vormoor()
    coast = journey.coast_road(AURVANTIS, VORMOOR,
                               journey.find(journey.legs_from(AURVANTIS, VORMOOR),
                                            "Ledgerwarren"), pc.speed_feet)
    road_hours = journey.hours_for(coast, pc.speed_feet)[0]
    sea = journey.find(journey.legs_from(AURVANTIS, VORMOOR), "Ledgerwarren")
    _ship, _days, fare = engine.passage_quote(sea, 1, port=SCRAPDEN)
    had, before = goods.in_copper(pc.purse), scene.clock_minutes

    out = _journey(engine, "Ledgerwarren")

    assert quiet_road == [road_hours], out.tell
    assert scene.location_id == SCRAPDEN, out.tell
    ship = engine.aboard()
    assert ship is not None and ship.bound_for == LEDGERWARREN and ship.at == SCRAPDEN
    assert scene.clock_minutes - before >= road_hours * 60
    assert had - goods.in_copper(pc.purse) == fare
    assert "Scrapden is ahead of you" in out.tell and "pays" in out.tell, out.tell
    # And the voyage from there is the ordinary one.
    _journey(engine, "Ledgerwarren")
    assert scene.location_id == LEDGERWARREN


def test_an_inland_to_inland_crossing_sails_from_the_harbour(quiet_road):
    """Vormoor to Moldwarren: both ends inland. No port's legs reach Moldwarren, which is
    why the booking is made at the start and carried down the road."""
    scene, engine, pc = _at_vormoor()
    _journey(engine, "Moldwarren")
    ship = engine.aboard()
    assert scene.location_id == SCRAPDEN and ship.bound_for == MOLDWARREN


def test_a_short_purse_is_refused_before_the_road_is_walked(quiet_road):
    scene, engine, pc = _at_vormoor(gp=1)
    before = scene.clock_minutes
    out = _journey(engine, "Ledgerwarren")
    assert out.status == "refused" and "Passage to Ledgerwarren" in out.tell, out.tell
    assert scene.clock_minutes == before and quiet_road == []
    assert scene.location_id == VORMOOR and pc.purse == {"gp": 1}


def test_a_harbour_road_stopped_short_resumes_and_the_row_offers_it(monkeypatch):
    """Weather on the first watch stops the march on the road to Scrapden: the crossing is
    remembered with the road, the From Here row offers it from the stretch of road, and
    the next journey walks only what is left before boarding."""
    from play import exits

    scene, engine, pc = _at_vormoor()
    met = iter([ontheway.Meeting(kind="weather", roll=1, after=1), None])
    asked: list[int] = []

    def road(dice, hours, *a, **k):
        asked.append(hours)
        return next(met)

    monkeypatch.setattr(ontheway, "road", road)
    _journey(engine, "Ledgerwarren")
    assert engine.aboard() is None and scene.road.get("then") == LEDGERWARREN
    assert scene.road.get("to") == SCRAPDEN and scene.road.get("walked")
    row = next(r for r in exits.exits(engine, AURVANTIS) if r["id"] == LEDGERWARREN)
    assert "to Scrapden, then" in row["time_words"] and "at sea" in row["time_words"]
    _journey(engine, "Ledgerwarren")
    assert asked[1] < asked[0], asked
    assert scene.location_id == SCRAPDEN and engine.aboard() is not None


def test_the_from_here_row_says_the_road_and_the_sea():
    """0.3.2's row read only the days at sea for an inland crossing: honest days, and a
    total five days short."""
    from rules import geography

    words = next(r for r in geography.roads_out(AURVANTIS, VORMOOR)
                 if r.to_id == LEDGERWARREN).time_words
    coast = journey.coast_road(AURVANTIS, VORMOOR, journey.find(
        journey.legs_from(AURVANTIS, VORMOOR), "Ledgerwarren"))
    walk = geography._walk_time_words(journey.hours_for(coast)[0])
    assert walk.endswith("days on foot")
    assert words.startswith(f"{walk} to Scrapden, then"), words
    assert words.endswith("aboard"), words


def test_the_row_is_offered_at_the_harbour_road_not_the_shore():
    """Vormoor has a shore a quarter of an hour out, and in 0.3.2 the Ledgerwarren row was
    offered there with a day at sea as its whole time. The ship is five days off at
    Scrapden: the row is offered where the Scrapden road leaves, like that road."""
    from play import exits

    scene, engine, pc = _at_vormoor()
    engine.place_party(f"{VORMOOR}~coast:@the-shore")
    assert all(r["id"] != LEDGERWARREN for r in exits.exits(engine, AURVANTIS))
    head = next(p.id for p in engine.places() if p.name == "the road to Scrapden")
    engine.place_party(head)
    row = next(r for r in exits.exits(engine, AURVANTIS) if r["id"] == LEDGERWARREN)
    assert row["journey"] and "to Scrapden, then" in row["time_words"], row
