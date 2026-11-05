"""A wait runs to the time of day the words name (owner report 2026-11-01, Corvin, turn 19).

"wait till tomarrow" at 22:00 was read `wait, time: till tomarrow`. The wait door's table
(`timewords.minutes_until`) has no "tomorrow" — and the misspelling would beat it if it
had — so the plan's `advance_time 1 day` stood: "1 day pass", 22:00 to 22:00, and the
prose wrote "When the new day breaks" over a late evening, caught by its own truth check.

The reader names the time of day now, as a closed choice (`interpret.UNTILS`); code turns
the name into minutes against the clock. No new regex reads the player's words.
"""
from __future__ import annotations

from gm import acts_to_ops, interpret
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/pangrella-campaign.json")
KHALMORIN = WORLD.by_name("Khalmorin", kind="CITY").id
HOUR = 60

GAGE_TURN_19 = "wait till tomarrow"
FRAME = {"question": False, "actions": [
    {"span": "wait till tomarrow", "time": "till tomarrow", "until": "morning",
     "act": "wait", "commit": "done", "means": "ordinary", "power": None}],
    "claims": []}


def _scene(clock):
    s = Scene(location_id=KHALMORIN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    s.clock_minutes = clock
    return s, e


def test_the_reader_offers_a_closed_time_of_day_on_wait_and_rest_only():
    alts = interpret.per_act_schema()["properties"]["actions"]["items"]["anyOf"]
    by_act = {a["properties"]["act"]["const"]: a for a in alts}
    for act in ("wait", "rest"):
        assert by_act[act]["properties"]["until"]["enum"] == list(interpret.UNTILS)
        assert "until" in by_act[act]["required"]
    assert "until" not in by_act["go"]["properties"]
    assert "morning" in interpret.UNTILS


def test_ground_keeps_the_readers_time_of_day_and_drops_one_outside_the_enum():
    kept, _ = interpret.ground(FRAME, GAGE_TURN_19)
    assert kept["actions"][0]["until"] == "morning"
    odd = {"question": False, "claims": [], "actions": [dict(FRAME["actions"][0],
                                                             until="tomorrowish")]}
    kept, _ = interpret.ground(odd, GAGE_TURN_19)
    assert "until" not in kept["actions"][0]


def test_till_tomorrow_at_ten_at_night_waits_to_the_morning_not_a_day():
    """Corvin's turn: the plan's 1 day becomes ten hours, 22:00 to 08:00, and the engine's
    clock lands on the morning."""
    s, e = _scene(24 * HOUR + 22 * HOUR)
    plan = [{"op": "advance_time", "params": {"amount": 1, "unit": "day"},
             "because": "the player's words commit the turn to it"}]
    notes: list = []
    fixed = acts_to_ops.timed_waits(plan, FRAME, s, notes=notes)
    assert fixed[0]["params"] == {"amount": 10 * HOUR, "unit": "minutes"}
    assert notes and "until morning" in notes[0]
    e.run(e.validate(fixed, origin="author:test"))
    assert s.clock_minutes % (24 * HOUR) == 8 * HOUR


def test_a_length_of_time_stays_the_plans():
    s, _e = _scene(10 * HOUR)
    frame = {"question": False, "claims": [], "actions": [
        {"act": "wait", "time": "for an hour", "until": "a while", "span": "wait an hour"}]}
    plan = [{"op": "advance_time", "params": {"amount": 1, "unit": "hour"}}]
    assert acts_to_ops.timed_waits(plan, frame, s) == plan


def test_a_sleep_till_tomorrow_wakes_in_the_morning():
    """The same choice reaches a sleep: the rest's `until` is "until morning", which
    `Engine._camp_for` reads against the clock."""
    frame = {"question": False, "claims": [], "actions": [
        {"act": "rest", "time": "till tomarrow", "until": "morning", "span": "sleep"}]}
    plan = [{"op": "rest", "actor": "pc", "params": {"kind": "night"}}]
    fixed = acts_to_ops.timed_rests(plan, frame)
    assert fixed[0]["params"]["until"] == "until morning"


def test_a_wait_with_a_time_of_day_and_no_time_slot_still_owes_a_wait():
    assert "advance_time" in interpret.ops_for(
        {"actions": [{"act": "wait", "until": "dusk", "span": "wait till dark"}]})


def test_the_demonstrations_show_tomorrow_as_the_morning():
    """Demonstration volume beats instruction volume (CLAUDE.md): a line with "tomorrow"
    is shown with the choice it gets."""
    shown = [f for said, f in interpret._DEMOS if "tomorrow" in said]
    assert shown and shown[0]["actions"][0]["until"] == "morning"
