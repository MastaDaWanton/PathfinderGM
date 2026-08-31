"""One door for the world clock.

Six places moved `scene.clock_minutes` and two of them expired anything. A forty-eight
hour forage, a twelve-hour crafting session, an hour spent waking up from a beating and a
resurrection costing up to twenty-seven days all left every timed effect in the scene
exactly where it was. This is the lesson `rules/survival.py` already records — "the clock
moved and the body did not know" — with effects in the place of hunger.
"""
from __future__ import annotations

import pytest

from rules.engine import Engine, IntentError, Scene
from rules.sheet import from_dict


def _actor(ref, name, kind="npc"):
    return from_dict({"name": name, "kind": kind, "hp": 20, "hp_max": 20,
                      "class": "rogue" if kind == "pc" else None, "level": 1,
                      "abilities": {k: 12 for k in
                                    ("str", "dex", "con", "int", "wis", "cha")}},
                     ref=ref)


def _scene():
    s = Scene()
    s.add(_actor("pc", "Player", "pc"))
    s.add(_actor("c1", "Bystander"))
    return s


def test_advance_expires_everything_on_everyone():
    """Not just the actor who asked. `_op_rest` ticked only the resting character, so an
    NPC standing in the same room kept every timed buff through an eight-hour night."""
    s = _scene()
    for a in s.actors.values():
        a.add_buff("save_mod", "will", 2, source="a tea", rounds=100)
    s.advance(60)
    assert not any(a.buffs for a in s.actors.values())


def test_advance_ticks_the_clocks_the_old_sites_forgot():
    """Four of the six sites ticked nothing; the two that did ticked conditions and
    buffs only, so pool cooldowns and compulsions stood still while hours passed."""
    s = _scene()
    pc = s.actors["pc"]
    pc.gain_pool("ki", 1)
    pc.start_cooldown("ki", 50)
    s.advance(60)
    assert pc.pool("ki").cooldown_left == 0


def test_advance_says_what_it_ended():
    """Four of the six threw the ended list away. `_op_advance_time` was the one that
    kept it, and its tell ("Ended: …") is the shape the rest inherit."""
    s = _scene()
    s.actors["pc"].add_buff("save_mod", "will", 2, source="a tea", rounds=10)
    got = s.advance(60)
    assert got["minutes"] == 60 and got["rounds"] == 600
    assert any("a tea" in line for line in got["ended"])


def test_time_never_runs_backwards():
    """`advance_time.amount` was `int()`-coerced with no floor, and the engine hands it
    to `tick_effects`, whose body is `e.rounds_left -= rounds`. A negative advance
    rewound the world clock past market days already sold AND extended every timed
    effect on every actor in the scene."""
    s = _scene()
    s.clock_minutes = 500
    s.actors["pc"].add_buff("save_mod", "will", 2, source="a tea", rounds=10)
    before = s.actors["pc"].effects[0].rounds_left
    got = s.advance(-9999)
    assert got == {"minutes": 0, "rounds": 0, "ended": []}
    assert s.clock_minutes == 500
    assert s.actors["pc"].effects[0].rounds_left == before, "an effect was extended"


def test_the_op_refuses_a_negative_or_absurd_amount():
    s = _scene()
    engine = Engine(s)
    with pytest.raises(IntentError, match="how much time passes"):
        engine.validate([{"op": "advance_time", "because": "t",
                          "params": {"amount": "backwards", "unit": "hour"}}])
    parsed = engine.validate([{"op": "advance_time", "because": "t",
                               "params": {"amount": -50, "unit": "hour"}}])
    assert parsed[0].params["amount"] == 0
    capped = engine.validate([{"op": "advance_time", "because": "t",
                               "params": {"amount": 10 ** 9, "unit": "day"}}])
    assert capped[0].params["amount"] == 365


def test_skipped_time_expires_a_hazard_without_firing_it_thousands_of_times():
    """The trap in the obvious implementation. An eight-hour rest is 4,800 rounds:
    firing every `each_round` ward that many times would roll thousands of saves and
    empty every pool, and firing once would understate a cloud stood in for a minute.
    `advance` ends things; `advance_turn` keeps the firing."""
    from rules.engine import Ward

    s = _scene()
    fired = []
    s.wards.append(Ward(owner="pc", trigger="each_round", rounds_left=10,
                        source="a burning cloud", spec={}))
    original = s._fire
    s._fire = lambda *a, **k: fired.append(1) or []
    try:
        s.advance(60)
    finally:
        s._fire = original
    assert not fired, "skipping time fired a hazard"
    assert not s.wards, "and the cloud should still have expired"


def test_a_scene_with_no_dice_can_still_advance():
    """`play/views.py`'s resurrection never builds an Engine, so `scene._dice` is None
    on that path — and it is the site that skips the most time in the app, up to
    twenty-seven days."""
    s = _scene()
    assert s._dice is None
    s.advance(9 * 24 * 60)
    assert s.clock_minutes == 9 * 24 * 60


def test_a_round_is_finer_than_a_minute_and_the_conversion_floors():
    """Found by an adversarial review of stage 4a, in a throwaway probe it wrote to
    dump the numbers — the suite was green through the whole regression.

    `advance_time` may be asked for five rounds. Deriving the tick from minutes alone
    floors 5 // 10 to zero, so "five rounds pass" expired NOTHING, and fifteen rounds
    ticked ten and quietly lost five. The clock still moves in whole minutes; the tick
    is stated in rounds."""
    from rules.engine import Engine

    for amount, unit, duration, survives in ((5, "round", 5, False),
                                             (15, "round", 15, False),
                                             (9, "round", 9, False),
                                             (9, "round", 20, True)):
        s = _scene()
        pc = s.actors["pc"]
        pc.add_buff("save_mod", "will", 2, source="bless", rounds=duration)
        Engine(s).run(Engine(s).validate(
            [{"op": "advance_time", "because": "t",
              "params": {"amount": amount, "unit": unit}}]))
        assert bool(pc.effects) is survives, (
            f"{amount} {unit} against a {duration}-round buff")


def test_rounds_that_do_not_fill_a_minute_still_leave_the_clock_alone():
    """The other half: five rounds is half a minute, and the world clock counts whole
    minutes. The tick must happen without the clock moving."""
    s = _scene()
    got = s.advance(0, rounds=5)
    assert got["rounds"] == 5 and got["minutes"] == 0
    assert s.clock_minutes == 0
