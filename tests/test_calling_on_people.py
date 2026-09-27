"""Calling on somebody at home (docs/the-population.md, "Built: shop hours and calling on
people").

Residency (2026-09-27) sent people home at night, and "at home" was a place nobody could
walk into: the finder said "would be indoors, at home", and there was no door to knock
on. Researched before building: where somebody lives is knowledge the character holds
(PF1e gather information — Diplomacy, at least 1d4 hours, DC 10 for what is commonly
known; The Alexandrian's targeted investigation), and a visit is a knock with two gates,
the hour and the relationship, as Stardew Valley's homes keep (door times; two hearts
for a bedroom). U7's innkeeper "must be awoken". Skyrim warns, then fines, a trespasser:
this door only knocks.
"""
from __future__ import annotations

from gm import judgement
from rules import attitude, population, residency
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id
HOUR = 60


def _met(clock, regard=None, work="baker"):
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = clock
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    rec = population.note(s, "a woman selling bread")
    rec["life"].update(work=work, work_name=work, mobility="resident")
    ref = judgement.embody_sought(s, "I talk to the woman selling bread.", WORLD)
    body = s.people[ref]
    e.run(e.validate([{"op": "say", "params": {"words": "Good day.", "to": ref}}],
                     origin="author:test"))
    body.remove_effects(source="talk")
    if regard is not None:
        attitude.set_regard(body, regard, "test")
    # And the party goes about its business: while it stands with her she stays (the
    # ruling), so nobody's day moves her until it leaves.
    elsewhere = next(p for p in e.places() if p.id != s.at)
    e.run(e.validate([{"op": "travel", "params": {"place": elsewhere.name}}],
                     origin="author:test"))
    return s, e, rec, body


def _call(e, who="her", visit=True):
    return e.run(e.validate([{"op": "call_on", "params": {"who": who, "visit": visit}}],
                            origin="author:test"))


def test_at_night_she_is_at_home_and_a_friend_is_let_in():
    s, e, rec, body = _met(10 * HOUR, regard=80)
    s.advance(12 * HOUR)                       # ten at night: home
    out = _call(e)
    call = out.outcomes[0]
    assert call.status == "resolved", call.tell
    house = call.effects[0]["house"]
    assert s.at == house and body.ref in s.actors
    assert "lets you in" in call.tell
    assert s.pc().has_state(f"knows.home.{rec['id']}")


def test_a_stranger_asks_around_first_and_it_costs_hours():
    s, e, rec, body = _met(10 * HOUR)
    before = s.clock_minutes
    call = _call(e, visit=False).outcomes[0]
    assert "asking around" in call.tell and s.clock_minutes > before
    assert "They live at" in call.tell


def test_in_the_small_hours_only_a_friend_opens_and_waking_costs_regard():
    s, e, rec, body = _met(10 * HOUR, regard=45)   # indifferent
    s.advance(16 * HOUR)                           # two in the morning
    was = attitude.regard_of(body)
    call = _call(e).outcomes[0]
    assert "does not open" in call.tell and attitude.regard_of(body) < was
    assert s.at != call.effects[0]["house"]


def test_by_day_she_is_out_and_a_neighbour_says_where():
    s, e, rec, body = _met(10 * HOUR, regard=80)
    call = _call(e).outcomes[0]
    assert "Nobody answers" in call.tell and "at this hour" in call.tell
    assert body.ref not in s.actors


def test_calling_on_somebody_standing_beside_you_says_so():
    s, e, rec, body = _met(10 * HOUR, regard=80)
    e.run(e.validate([{"op": "travel", "params": {"place": rec["spot"]}}],
                     origin="author:test"))
    assert body.ref in s.actors
    call = _call(e).outcomes[0]
    assert call.status == "refused" and "here, with you" in call.tell


def test_her_house_is_where_her_day_sends_her_from_then_on():
    s, e, rec, body = _met(10 * HOUR, regard=80)
    call = _call(e, visit=False).outcomes[0]
    house = call.effects[0]["house"]
    night = residency.whereabouts(rec, s.clock_minutes + 12 * HOUR, WORLD, s.founded)
    assert night.place == house and not residency.is_offstage(house)


def test_walking_straight_into_her_house_knocks_first():
    s, e, rec, body = _met(10 * HOUR, regard=10)   # hostile
    house = _call(e, visit=False).outcomes[0].effects[0]["house"]
    s.advance(10 * HOUR)
    out = e.run(e.validate([{"op": "travel", "params": {"place": house}}],
                           origin="author:test"))
    assert out.outcomes[0].status == "refused" and s.at != house


def test_the_players_words_are_read_as_a_call():
    assert judgement.called_on("I go to the bread seller's house.") == ("bread seller", True)
    assert judgement.called_on("I knock at her door.") == ("her", True)
    assert judgement.called_on("I ask around where the baker lives.") == ("baker", False)
    assert judgement.called_on("I go home.") == ("", False)
    raw = judgement.inject_call_on([{"op": "travel", "params": {"place": "her house"}}],
                                   "I go to her house.", Scene(location_id=VORMOOR))
    assert [r["op"] for r in raw] == ["call_on"]


def test_the_bread_seller_is_the_one_selling_bread():
    """Live: "I ask around where the bread seller lives" found nobody — "seller" was read
    as a stallholder, and she had been written "somebody selling bread"."""
    s, e, rec, body = _met(10 * HOUR, regard=80)
    call = _call(e, who="bread seller", visit=False).outcomes[0]
    assert call.status == "resolved", call.tell


def test_a_call_decides_the_walk():
    """Live: `call_on` came back beside a `travel` to "the baker's row", which walked the
    party off before the knock."""
    raw = judgement.inject_call_on(
        [{"op": "travel", "params": {"place": "the baker's row"}},
         {"op": "call_on", "params": {"who": "her", "visit": True}}],
        "I go to her house.", Scene(location_id=VORMOOR))
    assert [r["op"] for r in raw] == ["call_on"]


def test_a_night_begun_in_the_evening_ends_in_the_morning():
    """Live: "I find somewhere to sleep until morning" at five in the afternoon woke the
    party at one in the morning, and the prose wrote the morning sun."""
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = 17 * HOUR
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    e.run(e.validate([{"op": "rest", "actor": "pc", "params": {"kind": "night"}}],
                     origin="author:test"))
    assert s.clock_minutes == 30 * HOUR          # six the next morning
    s.clock_minutes = 2 * HOUR                   # a night begun at two is eight hours
    e.run(e.validate([{"op": "rest", "actor": "pc", "params": {"kind": "night"}}],
                     origin="author:test"))
    assert s.clock_minutes == 10 * HOUR


def test_her_is_the_one_whose_home_was_just_asked_after():
    """Live: two people met in the same minute, and "I go to her house" knocked for the
    opening's companion rather than the bread seller asked after the turn before."""
    s, e, rec, body = _met(10 * HOUR, regard=80)
    other = population.note(s, "a neighbour who knows the words", fresh=True)
    other["last_met"] = rec["last_met"]
    other["last_seen"] = s.clock_minutes + 5
    _call(e, who="woman selling bread", visit=False)
    got, _ = e._person_called_on("her")
    assert got["id"] == rec["id"]


def test_waiting_until_a_named_hour_waits_until_it():
    """Live: "I wait at the well until ten at night" at mid-morning was planned as 140
    minutes."""
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = 10 * HOUR
    raw = judgement.inject_wait(
        [{"op": "advance_time", "params": {"amount": 140, "unit": "minute"}}],
        "I wait at the well until ten at night.", s)
    assert raw[0]["params"] == {"amount": 12 * HOUR, "unit": "minutes"}
    assert judgement.minutes_until("I wait until dawn.", 22 * HOUR) == 8 * HOUR


def test_sleeping_until_morning_is_a_night_not_a_day_in_bed():
    """Live: "I find somewhere to sleep until morning" came back as bed rest, a full day
    and night, and the party woke at noon."""
    got = judgement.repair_rest_kind([{"op": "rest", "params": {"kind": "bed rest"}}],
                                     "I find somewhere to sleep until morning.")
    assert got[0]["params"]["kind"] == "night"
    kept = judgement.repair_rest_kind([{"op": "rest", "params": {"kind": "bed rest"}}],
                                      "I take a full day of bed rest.")
    assert kept[0]["params"]["kind"] == "bed rest"
