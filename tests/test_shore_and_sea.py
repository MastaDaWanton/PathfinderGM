"""Shore and sea (fix/shore-and-sea, 2026-11-15).

Four defects, each measured in 0.3.4 before it was fixed:

1. A ship could only be boarded at a quay. Vormoor (stilt-housing on the water, no docks)
   has stated sea routes to Ledgerwarren and Moldwarren, and its only way aboard was five
   days' road to Scrapden. Owner ruling 2026-11-14: a ship lying off a dockless coastal
   town is reached by swimming out or by a small boat.
2. A crossing to an inland town tied up AT the inland town: Vormoor to Moldwarren ended
   at Moldwarren's gate after one day at sea, and Moldwarren's 48-mile mountain road up
   from Ledgernook was never walked.
3. A road stopped short a second time said "3 hours out of Vormoor" after days walked:
   the tell counted that turn's hours only. And the page said "The move did not happen"
   over a road that had been walked, because the stretch of road still offers the same
   town's row (the fix is the server's `moved` flag; play/views.py `_the_way_there`).
4. The Swim skill's hourly check ran only in a shipwreck; currents and floods were not
   read; a swimmer in armour went under with no word of why.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from rules import goods, journey, ontheway, ships, states, water
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc
from world.loader import load_cached

AURVANTIS = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = "bde94b038cba"


def _id(name: str) -> str:
    return next(s["id"] for s in AURVANTIS.play["settlements"] if s["name"] == name)


LEDGERWARREN, MOLDWARREN, LEDGERNOOK, SCRAPDEN = (
    _id("Ledgerwarren"), _id("Moldwarren"), _id("Ledgernook"), _id("Scrapden"))


def _at_vormoor(day: int, pc_file: str = "fixtures/pc-kesst.json"):
    scene = Scene(location_id=VORMOOR)
    pc = load_pc(pc_file)
    scene.add(pc)
    scene.clock_minutes = day * 24 * 60 + 8 * 60
    engine = Engine(scene, Dice(seed=5), world=AURVANTIS)
    engine.place_party()
    pc.purse = {"gp": 500}
    return scene, engine, pc


def _journey(engine, **params):
    engine._journeyed = ""
    res = engine.run(engine.validate(
        [{"op": "journey", "actor": "pc", "because": "t", "params": params}],
        origin="author:test"))
    return next(o for o in res.outcomes if o.op == "journey")


@pytest.fixture
def quiet_road(monkeypatch):
    asked: list[int] = []

    def road(dice, hours, *a, **k):
        asked.append(hours)
        return None

    monkeypatch.setattr(ontheway, "road", road)
    return asked


CALL = journey._call_day(VORMOOR, LEDGERWARREN)


# --- 1. a ship lying off a dockless shore --------------------------------------------------

def test_ships_call_off_dockless_towns_on_the_water_on_their_stated_routes():
    """Measured: 6 of Aurvantis's 41 dockless settlements state a sea route and lie on the
    water, 9 calls between them. A port, and a town that is not on the water, get none."""
    calls = {s["id"]: journey.calls_off(AURVANTIS, s["id"])
             for s in AURVANTIS.play["settlements"]}
    assert sum(1 for c in calls.values() if c) == 6
    assert sum(len(c) for c in calls.values()) == 9
    assert calls[SCRAPDEN] == () and set(calls[VORMOOR]) == {LEDGERWARREN, MOLDWARREN}
    # Once a week each, on its own day.
    days = [d for d in range(14) if LEDGERWARREN in journey.lying_off(AURVANTIS, VORMOOR, d)]
    assert days == [CALL, CALL + 7]


def test_by_boat_from_the_shore_on_her_day(quiet_road):
    """UE p.87's rowboat: 2 cp a mile (1 cp a head at a cable), 1.5 mph (5 minutes)."""
    scene, engine, pc = _at_vormoor(CALL)
    sea = journey.find(journey.legs_from(AURVANTIS, VORMOOR), "Ledgerwarren")
    _ship, _days, fare = engine.passage_quote(sea, 1)
    had, before = goods.in_copper(pc.purse), scene.clock_minutes
    out = _journey(engine, to="Ledgerwarren")
    ship = engine.aboard()
    assert ship is not None and ship.at == VORMOOR, out.tell
    assert quiet_road == [], "no road to Scrapden is walked"
    assert had - goods.in_copper(pc.purse) == fare + 1
    assert scene.clock_minutes - before == ships.rowboat_minutes(1) == 5
    assert "rowboat" in out.tell and "off the shore" in out.tell, out.tell
    _journey(engine, to="Ledgerwarren")
    assert scene.location_id == LEDGERWARREN and engine.aboard() is None


def test_swimming_out_rolls_real_checks_and_names_the_armour():
    """Borin's chain shirt: his take-10 fails calm water, so he rolls every round, goes
    under, and is told why; he still makes it. Kesst takes 10 and throws no die."""
    scene, engine, pc = _at_vormoor(CALL, "fixtures/pc-borin.json")
    mods = list(pc.skill_modifiers("swim"))
    assert 10 + sum(m.value for m in mods) < 10, "the fixture's Borin cannot take 10"
    out = _journey(engine, to="Ledgerwarren", out="swim")
    assert engine.aboard() is not None, out.tell
    assert "armour drags" in out.tell and "going under" in out.tell, out.tell
    rec = next(e for e in out.effects if e.get("kind") == "swim")
    assert rec["made"] and rec["rounds"] > ships.ANCHORED_OFF_FT // (pc.speed_feet // 2)
    assert not pc.has_state(states.UNDER_WATER) and pc.held_breath_rounds == 0

    scene, engine, pc = _at_vormoor(CALL)
    rolled = []
    real = engine.dice.d20
    engine.dice.d20 = lambda mods, **k: rolled.append(k.get("label")) or real(mods, **k)
    _journey(engine, to="Ledgerwarren", out="swim")
    assert engine.aboard() is not None and not [r for r in rolled if "Swim" in str(r)]


def test_a_swimmer_who_cannot_keep_up_drowns_by_the_ladder():
    """A body that cannot swim at all (every die a 1, in stormy water where 10 cannot be taken) goes under and drowns on
    the breath clock: twice Con in rounds, then the Constitution checks, then the ladder."""
    scene, engine, pc = _at_vormoor(CALL)
    engine.dice.d20 = lambda mods, **k: SimpleNamespace(total=1)
    made, rounds, said = engine._swim_out(pc, ships.ANCHORED_OFF_FT, "stormy")
    assert not made and pc.has_state("state.down.dead"), said
    assert rounds > water.breath_rounds(pc), rounds
    assert "drowned" in " ".join(said), said


def test_not_her_day_walks_the_road_to_the_port_as_before(quiet_road):
    scene, engine, pc = _at_vormoor(CALL + 1)
    assert not engine.lies_off(journey.find(journey.legs_from(AURVANTIS, VORMOOR),
                                            "Ledgerwarren"))
    _journey(engine, to="Ledgerwarren")
    assert quiet_road and scene.location_id == SCRAPDEN


def test_the_exits_row_offers_both_ways_from_the_shore():
    from play import exits
    from rules import outskirts

    scene, engine, pc = _at_vormoor(CALL)
    shore = next(p for p in engine.places() if p.name == outskirts.SHORE)
    engine.place_party(shore.id)
    rows = {r["id"]: r for r in exits.exits(engine, AURVANTIS)}
    assert "rowboat" in rows[LEDGERWARREN]["time_words"], rows[LEDGERWARREN]
    swim = rows[f"{LEDGERWARREN}~swim"]
    assert swim["to"] == LEDGERWARREN and swim["out"] == "swim"


def test_out_is_a_closed_word():
    scene, engine, pc = _at_vormoor(CALL)
    with pytest.raises(IntentError, match="not a way out"):
        engine.validate([{"op": "journey", "actor": "pc", "because": "t",
                          "params": {"to": "Ledgerwarren", "out": "paddle"}}])


# --- 2. the far end inland ------------------------------------------------------------------

def test_a_crossing_to_an_inland_town_lands_at_its_harbour_and_walks_up(quiet_road):
    """0.3.4: one day at sea and the party stood at Moldwarren's gate. Now she ties up at
    Ledgernook and the 48-mile road is walked, its own road check asked."""
    scene, engine, pc = _at_vormoor(CALL + 1)
    _journey(engine, to="Moldwarren")
    ship = engine.aboard()
    assert ship.bound_for == MOLDWARREN and ship.lands_at == LEDGERNOOK
    up = journey.harbour_road(AURVANTIS, MOLDWARREN, pc.speed_feet)
    road_hours = journey.hours_for(up, pc.speed_feet)[0]
    quiet_road.clear()
    before = scene.clock_minutes
    out = _journey(engine, to="Moldwarren")
    assert scene.location_id == MOLDWARREN, out.tell
    assert quiet_road == [road_hours], quiet_road
    assert scene.clock_minutes - before >= 24 * 60 + road_hours * 60
    assert "makes Ledgernook" in out.tell and "Moldwarren is ahead" in out.tell, out.tell


# --- 3. the road-stop tell ------------------------------------------------------------------

def test_a_road_stopped_twice_says_the_whole_road_so_far(monkeypatch):
    """Weather stops the road on both turns; the second tell counts both."""
    scene, engine, pc = _at_vormoor(CALL + 1)
    met = iter([ontheway.Meeting(kind="weather", roll=1, after=1),
                ontheway.Meeting(kind="weather", roll=1, after=1)])
    monkeypatch.setattr(ontheway, "road", lambda *a, **k: next(met))
    _journey(engine, to="Scrapden")
    first = int(scene.road["walked"])
    out = _journey(engine, to="Scrapden")
    total = int(scene.road["walked"])
    assert total > first
    said = f"{total} hours" if total < journey.HOURS_PER_DAY else "a day"
    assert said in out.tell and "on foot out of Vormoor" in out.tell, out.tell
    assert "of it this time" in out.tell, out.tell


# --- 4. long swims, currents, floods --------------------------------------------------------

def _lake(row: dict):
    from tests.test_swim_checks import _in_a

    s, e, pc = _in_a("water", fight=False)
    e.world = SimpleNamespace(get=lambda _id: SimpleNamespace(places=[{"id": s.at, **row}]))
    return s, e, pc


def test_an_hour_in_the_water_asks_the_fatigue_check():
    """CRB Swim: each hour, DC 20 Swim or 1d6 nonlethal. Only a wreck asked it before."""
    s, e, pc = _lake({})
    s.advance(60)
    assert pc.swum_rounds >= water.ROUNDS_AN_HOUR
    e.dice.d20 = lambda mods, **k: SimpleNamespace(total=2)
    had = pc.nonlethal
    told = e.swim()
    assert pc.nonlethal > had and any("hour in the water" in t for t in told), told
    assert pc.swum_rounds < water.ROUNDS_AN_HOUR


def test_a_current_batters_a_swimmer_who_fails_and_a_flood_is_a_step_harder():
    s, e, pc = _lake({"current": "fast"})
    assert water.roughness(e.world, s.at) == "rough"
    s, e, pc = _lake({"current": "rapids"})
    assert water.roughness(e.world, s.at) == "stormy"
    s, e, pc = _lake({"water": "rough", "flooded": True})
    assert water.roughness(e.world, s.at) == "stormy"
    s, e, pc = _lake({"current": "fast"})
    e.dice.d20 = lambda mods, **k: SimpleNamespace(total=1)
    had = pc.nonlethal
    told = e.swim()
    assert pc.nonlethal > had and any("current" in t for t in told), told


def test_armour_is_named_only_when_it_is_why():
    mod = SimpleNamespace
    acp = [mod(value=3, source="Strength"), mod(value=-6, source="armour check")]
    assert water.armour_is_why(acp, -3)          # 10 + 3 - 6 vs 10: fails by 3
    assert not water.armour_is_why(acp, -7)      # would fail without it too
    assert not water.armour_is_why(acp, 2)
