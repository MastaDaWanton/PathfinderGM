"""Travel pacing (feat/travel-pacing-2, 2026-11-18): long journeys in stretches of days,
each stretch one hidden check against an authored table (content/rules/journey-events.json),
quiet days told in one line, and an event stopping the journey as a real scene.

The owner, 2026-11-16: "I dont want it to go day by day when travel could be a month long
but instead every few days you can roll an event on the ship ... overland travel is too
short it should be a few days minimum to other cities and over water it should be a few
weeks minimum." Measured on master 0.4.2 the same week: every Pangrella and Aurvantis road
between settlements was one to four walking days (World Bible's tree bands, 24-96 miles),
and every sea passage one or two days — 192-216 miles at Ultimate Combat's tactical 60 ft
read as 144 miles a day, three times the Core Rulebook's sailing ship (48 miles a day).
"""
from __future__ import annotations

import pytest

from rules import journey, ontheway, places, ships, states
from rules.dice import Dice
from tests.test_b_travel import AURVANTIS, _party, _run
from tests.test_ships_at_sea import MIRABALOS, PANGRELLA, ZHILVARNIA, _at_port, _journey

DAY = ships.MINUTES_A_DAY


def _settlement_legs(world):
    for row in world.play.get("settlements") or []:
        for leg in journey.legs_from(world, row["id"]):
            yield row["id"], leg


# --- distances ------------------------------------------------------------------------------

@pytest.mark.parametrize("world", [PANGRELLA, AURVANTIS], ids=["pangrella", "aurvantis"])
def test_no_road_is_under_three_days_and_no_crossing_under_two_weeks(world):
    """0.4.2: Aurvantis's 24-mile roads were one walking day, and a Pangrella crossing of
    192 miles was ONE day at sea. Unmeasured miles now hold to the floors: three days' walk
    for a human between two settlements, a fortnight under sail."""
    seen = {"road": 0, "sea": 0}
    for _here, leg in _settlement_legs(world):
        hours, _words, how = journey.hours_for(leg, 30)
        if how == "sea":
            vessel = "keelboat" if leg.by == "river" else "sailing ship"
            days = ships.leg_days(leg, vessel)
            assert days >= (journey.ROAD_DAYS_AT_LEAST if leg.by == "river"
                            else ships.PASSAGE_DAYS_AT_LEAST), (leg.to_name, days)
            seen["sea"] += 1
        else:
            assert hours >= journey.ROAD_DAYS_AT_LEAST * journey.HOURS_PER_DAY, \
                (leg.to_name, hours)
            seen["road"] += 1
    assert seen["road"] and seen["sea"], seen


def test_a_measured_route_is_taken_at_its_word():
    """for-world-bible ask 32: a route the world marks `measured` is played at its stated
    length — 48 miles is sixteen hours on a road, 192 miles four days by the CRB's sailing
    ship (Table 7-9, 48 miles a day) — and an unmeasured one meets the floor."""
    leg = journey.Leg(to_id="x", to_name="X", miles=48, road="road",
                      crosses=("grassland",), source="exact", measured=True)
    assert journey.hours_for(leg, 30)[:3:2] == (16, "exact")
    unmeasured = journey.Leg(to_id="x", to_name="X", miles=48, road="road",
                             crosses=("grassland",), source="exact")
    hours, words, how = journey.hours_for(unmeasured, 30)
    assert hours == 24 and how == "derived" and "48 miles" not in words
    assert ships.days_for(192, "sailing ship", measured=True) == 4
    assert ships.days_for(192, "sailing ship") == ships.PASSAGE_DAYS_AT_LEAST
    assert ships.days_for(72, "keelboat", river=True) == journey.ROAD_DAYS_AT_LEAST


def test_the_fare_is_for_the_days_she_sails():
    """1 sp a mile (Ultimate Equipment's passage), the miles her day's run over the
    floored days: a fortnight on a sailing ship is 672 miles, 67 gp 2 sp a head."""
    scene, engine, pc = _at_port(gp=500)
    _journey(engine)
    assert engine.aboard().days_total == ships.PASSAGE_DAYS_AT_LEAST
    assert 500 * 100 - sum(v * {"gp": 100, "sp": 10, "cp": 1, "pp": 1000}[k]
                           for k, v in pc.purse.items()) == 6720


# --- the table ------------------------------------------------------------------------------

def test_a_journey_is_cut_into_stretches():
    assert ontheway.stretches(14, 3) == [3, 3, 3, 3, 2]
    assert ontheway.stretches(3, 3) == [3]
    assert ontheway.stretches(0, 3) == []


def test_a_fortnight_meets_something_most_passages_and_never_every_day():
    """One check a stretch of three days at 40%: a fortnight is five checks, so about one
    passage in ten is quiet (0.6^4 x 0.73 = 9.5%), and an event falls on any day of it.
    The old daily storm plus daily sea check stopped a fortnight on nearly every passage
    within its first days (1 - 0.76^3 = 56% by day three)."""
    dice = Dice(seed=5)
    days = [getattr(ontheway.sea_stretches(dice, 14, 3, apl=3), "day", 0)
            for _ in range(2000)]
    quiet = days.count(0) / len(days)
    assert 0.06 <= quiet <= 0.14, quiet
    assert set(range(1, 15)) <= set(days), sorted(set(days))
    assert sum(1 for d in days if 1 <= d <= 3) / len(days) < 0.45


@pytest.mark.parametrize("table", ["road", "sea"])
def test_every_band_the_table_names_is_one_the_code_makes(table):
    """The table is authored data: a band the code cannot make would be a hit that says
    nothing. Each band, forced, comes back as a meeting of its own kind (a creature the
    ground does not stock falls back to people, as the hops' table does)."""
    for band in ontheway.events()[table]["bands"]:
        kind = band["kind"]
        if table == "sea":
            met = ontheway._sea_meeting(Dice(seed=1), kind, 50, 3, 3, ())
        else:
            real = ontheway._pick_band
            try:
                ontheway._pick_band = lambda dice, bands, label: (kind, 50)
                met = None
                for seed in range(40):
                    met = ontheway.road_stretches(Dice(seed=seed), 72, "forest", 3, apl=3)
                    if met is not None:
                        break
            finally:
                ontheway._pick_band = real
        assert met is not None and met.kind in (kind, "travellers", "merchant"), (kind, met)
        if kind in ontheway.events().get("people", {}):
            assert met.template and met.count >= 1 and met.name, met


# --- at sea -----------------------------------------------------------------------------------

def _force_sea(monkeypatch, kind: str, day: int):
    """The voyage's stretch check made to meet `kind` on `day`, once (then nothing): the
    meeting itself made by the real `_sea_meeting`."""
    left = [kind]

    def stretches(dice, days, level=1, **kw):
        if not left or day > days:
            return None
        met = ontheway._sea_meeting(dice, left.pop(), 50, level, kw.get("apl"), ())
        return ontheway.Meeting(**{**met.__dict__, "day": day})

    monkeypatch.setattr(ontheway, "sea_stretches", stretches)


def test_quiet_days_pass_in_one_line_and_the_clock_moves_by_them(monkeypatch):
    """The owner's "eleven quiet days out of Mirabalos": an island met on the fifth day
    stops the passage there, four days told in one line and five days on the clock."""
    scene, engine, pc = _at_port()
    _journey(engine)
    ship = engine.aboard()
    _force_sea(monkeypatch, "island", 5)
    start = scene.clock_minutes
    out = _journey(engine)
    assert scene.clock_minutes - start == 5 * DAY, out.tell
    assert "four quiet days at sea" in out.tell and "fifth day out of" in out.tell, out.tell
    assert engine.aboard().days_left == ship.days_total - 5


def test_an_island_is_a_place_ashore_and_is_left_astern(monkeypatch):
    """Places must be creatable (2026-10-03): the island is a real place off her deck, a
    real hand of hers asks to put in, and sailing on leaves it astern."""
    scene, engine, pc = _at_port()
    _journey(engine)
    _force_sea(monkeypatch, "island", 2)
    out = _journey(engine)
    fx = next(e for e in out.effects if e.get("kind") == "sea_encounter")
    island = places.find(engine.places(), fx["place"])
    assert island is not None and island.name == "the island", out.tell
    assert fx.get("asks") in scene.people, "the hand who asks is a person in the scene"
    went = engine.run(engine.validate([{"op": "travel", "actor": "pc", "because": "t",
                                        "params": {"place": island.id}}],
                                      origin="author:test")).outcomes[-1]
    assert scene.at == island.id, went.tell
    _force_sea(monkeypatch, "island", 99)            # nothing more this passage
    on = _journey(engine)
    assert "left astern" in on.tell, on.tell
    assert places.find(engine.places(), island.id) is None
    assert ships.vessel_of(scene.at) or scene.location_id == ZHILVARNIA


def test_a_wreck_holds_a_chest_of_coin_the_engine_rolled(monkeypatch):
    scene, engine, pc = _at_port()
    _journey(engine)
    _force_sea(monkeypatch, "wreck", 3)
    out = _journey(engine)
    fx = next(e for e in out.effects if e.get("kind") == "sea_encounter")
    chest = [p for p in scene.props if p.get("at") == fx["place"]]
    assert chest and chest[0]["name"] == "a sea chest", scene.props
    from rules import holding

    assert sum(holding.contents(chest[0])["purse"].values()) > 0


def test_a_survivor_is_a_real_person_hauled_aboard_fatigued(monkeypatch):
    """Seen people are real (2026-10-01): the survivor is an actor on her deck, aboard as
    a passenger, fatigued through the one applicator."""
    scene, engine, pc = _at_port()
    _journey(engine)
    _force_sea(monkeypatch, "survivor", 2)
    out = _journey(engine)
    fx = next(e for e in out.effects if e.get("kind") == "sea_encounter")
    who = scene.people[fx["refs"][0]]
    assert who.name.lower().startswith("survivor") or "survivor" in who.name.lower()
    assert who.has_state("state.impaired.fatigued")
    assert who.ref in engine.aboard().passengers and who.at == scene.at


def test_ship_fever_sickens_one_of_her_real_hands(monkeypatch):
    scene, engine, pc = _at_port()
    _journey(engine)
    _force_sea(monkeypatch, "sickness", 2)
    out = _journey(engine)
    fx = next(e for e in out.effects if e.get("kind") == "sea_encounter")
    assert scene.people[fx["ref"]].has_state("state.impaired.sickened"), out.tell


def test_a_quiet_passage_arrives_after_the_whole_fortnight(monkeypatch):
    monkeypatch.setattr(ontheway, "sea_stretches", lambda *a, **k: None)
    scene, engine, pc = _at_port()
    _journey(engine)
    start = scene.clock_minutes
    out = _journey(engine)
    assert scene.location_id == ZHILVARNIA, out.tell
    assert scene.clock_minutes - start == ships.PASSAGE_DAYS_AT_LEAST * DAY
    assert "14 days at sea" in out.tell


# --- the road ---------------------------------------------------------------------------------

def _force_road(monkeypatch, kind: str, day: int):
    """The road's stretch check made to hit on `day` with band `kind`, once; the meeting
    itself made by the real `road_stretches`."""
    left = [kind]
    real_pick = ontheway._pick_band

    def event_day(*a, **k):
        return day if left else 0

    def pick(dice, bands, label):
        return (left.pop(), 50) if left else real_pick(dice, bands, label)

    monkeypatch.setattr(ontheway, "_event_day", event_day)
    monkeypatch.setattr(ontheway, "_pick_band", pick)


def test_an_overland_journey_takes_days_and_stops_on_its_event(monkeypatch):
    """A road of three days and more, an event on its second day: the party stands on
    that road a day and a half out, the clock moved by it, with the quiet day said."""
    s, e, pc = _party()
    _force_road(monkeypatch, "travellers", 2)
    start = s.clock_minutes
    out = _run(e, pc, "journey", to="Scrapden")[0]
    eff = out.effects[0]
    assert eff.get("stopped_short") and eff.get("met") == "travellers", out.tell
    assert "A quiet day on the road" in out.tell and "second day" in out.tell, out.tell
    assert s.clock_minutes - start >= DAY, s.clock_minutes - start
    assert eff["met_refs"], "the travellers are people in the scene"


def test_a_ruin_off_the_road_is_a_place_to_go_into(monkeypatch):
    s, e, pc = _party()
    _force_road(monkeypatch, "ruin", 2)
    out = _run(e, pc, "journey", to="Scrapden")[0]
    assert out.effects[0].get("met") == "ruin", out.tell
    assert any(p.name == "the ruins" for p in e.places()), [p.name for p in e.places()]


def test_a_bridge_down_is_the_long_way_round(monkeypatch):
    """The detour is road still to walk: the resumed journey costs its hours more."""
    s, e, pc = _party()
    _force_road(monkeypatch, "bridge", 2)
    _run(e, pc, "journey", to="Scrapden")
    assert s.road.get("detour") == ontheway.events()["bridge_detour_hours"]


def test_a_caravan_brings_its_guards(monkeypatch):
    s, e, pc = _party()
    _force_road(monkeypatch, "caravan", 2)
    out = _run(e, pc, "journey", to="Scrapden")[0]
    refs = out.effects[0]["met_refs"]
    assert len(refs) >= 3, out.tell                      # the master and two guards
    names = [s.people[r].name for r in refs if r in s.people]
    assert any("guard" in n for n in names), names


def test_weather_on_a_long_road_costs_hours_and_walks_on(monkeypatch):
    """A storm is nobody to play: it delays the march and the party still arrives."""
    s, e, pc = _party()
    _force_road(monkeypatch, "weather", 2)
    out = _run(e, pc, "journey", to="Scrapden")[0]
    assert s.location_id == out.effects[0]["to"] and not s.road, out.tell
    assert "weather turned" in out.tell, out.tell


# --- a held ship's cruise -----------------------------------------------------------------------

def test_a_cruise_runs_days_until_it_meets_a_sail(held_at_quay, monkeypatch):
    """0.3.9 cruised one day a turn; a cruise now runs day after day until it meets
    something (the merchantman a held ship can close with), quiet days in one line."""
    scene, engine, pc, ship = held_at_quay
    _force_sea(monkeypatch, "merchant", 3)
    start = scene.clock_minutes
    out = engine.run(engine.validate([{"op": "sea", "actor": "pc", "because": "t",
                                       "params": {"do": "cruise"}}],
                                     origin="author:test")).outcomes[-1]
    assert scene.clock_minutes - start == 3 * DAY, out.tell
    assert "two quiet days" in out.tell and scene.sea.get("theirs"), out.tell


from tests.test_ships_and_piracy import held_at_quay  # noqa: E402,F401  (the fixture)


def test_days_cruised_are_not_given_back_to_the_next_voyage(held_at_quay):
    """Live 2026-11-18: two days cruised off Mirabalos, then the Red Gull's "14 days at
    sea" to Zhilvarnia moved the clock twelve — `_sail` counts from `sailed_at`, which the
    cruise left at its own start. A quiet week's cruise then a fortnight is three weeks."""
    scene, engine, pc, ship = held_at_quay
    start = scene.clock_minutes
    engine.run(engine.validate([{"op": "sea", "actor": "pc", "because": "t",
                                 "params": {"do": "cruise"}}], origin="author:test"))
    assert scene.clock_minutes - start == ships.CRUISE_DAYS * DAY
    out = _journey(engine, to="Mirabalos")
    days = next(e["days"] for e in out.effects if e.get("kind") == "voyage")
    assert scene.clock_minutes - start == (ships.CRUISE_DAYS + days) * DAY, out.tell
