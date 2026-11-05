"""The night's own numbers, said truly (owner report 2026-11-01, Ansel, 0.2.25).

Two defects in one save:

* "Ansel sleeps 5 hours 34 minutes, till morning: short of a full night's rest" — and the
  engine handed `survival.sleep` `max(1, round(334 / 60)) = 6` hours, the exact count that
  resets the awake clock. A sleep of five and a half hours reset what only six may.
* "Ansel rests for 8 hours. Ansel wakes still fatigued: hunger holds it until Ansel eats
  ... Ansel was already unhurt." — at full hit points and carrying hunger's non-lethal
  damage, held until a meal. The only line about the body on the page was false.
"""
from __future__ import annotations

from rules import survival
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/pangrella-campaign.json")
KHALMORIN = WORLD.by_name("Khalmorin", kind="CITY").id
HOUR = 60


def _town(clock):
    s = Scene(location_id=KHALMORIN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = clock
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    s.clock_minutes = clock
    return s, e


def _rest(e, **params):
    return e.run(e.validate([{"op": "rest", "actor": "pc", "because": "t",
                              "params": {"kind": "night", **params}}],
                            origin="author:test")).outcomes[0]


def test_five_and_a_half_hours_asleep_is_not_the_six_that_reset_the_awake_clock():
    """Ansel's measurement: 02:26 to morning (eight o'clock) is 5 h 34 min. The awake clock (twenty hours up)
    stays where it was, because survival's rule is six hours slept, and the record keeps
    the real minutes beside the rounded hours."""
    s, e = _town(26 * HOUR + 26)
    pc = s.pc()
    pc.awake_minutes = 20 * HOUR
    rest = _rest(e, until="till morning")
    assert rest.effects[0].get("short"), rest.tell
    assert "5 hours 34 minutes" in rest.tell
    assert rest.effects[0]["minutes"] == 5 * HOUR + 34
    assert pc.awake_minutes > 0, "five and a half hours reset the six-hour clock"


def test_six_whole_hours_still_reset_the_clock():
    """The rule itself is unchanged: six hours slept is a reset."""
    _s, _e = _town(0)
    pc = _s.pc()
    pc.awake_minutes = 20 * HOUR
    survival.sleep(pc, minutes=6 * HOUR)
    assert pc.awake_minutes == 0
    pc.awake_minutes = 20 * HOUR
    survival.sleep(pc, minutes=6 * HOUR - 1)
    assert pc.awake_minutes == 20 * HOUR
    survival.sleep(pc, 8)
    assert pc.awake_minutes == 0


def test_a_body_carrying_held_hunger_damage_is_not_already_unhurt():
    """Full hit points and three points of hunger's non-lethal, held until a meal: the
    night's tell says what holds it, never "was already unhurt"."""
    s, e = _town(22 * HOUR)
    pc = s.pc()
    pc.hp = pc.hp_max
    pc.take_nonlethal(3)
    pc.withhold_nonlethal("hunger", 3)
    rest = _rest(e)
    assert "already unhurt" not in rest.tell, rest.tell
    assert "hunger" in rest.tell and "will not mend" in rest.tell, rest.tell


def test_an_unhurt_body_is_still_said_to_be_unhurt():
    s, e = _town(22 * HOUR)
    pc = s.pc()
    pc.hp = pc.hp_max
    rest = _rest(e)
    assert "already unhurt" in rest.tell, rest.tell
