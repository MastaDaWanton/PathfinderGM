"""Bleeding out.

Found in a live fight: Kesst was knocked to -4, "The fight is over" printed, and she
simply lay there. Nothing counted her down, nothing gave her a chance to stabilise, and
nothing would ever have killed her. That is not what 1e says and not what a player
expects to happen to them.

Core Rulebook: below 0 hit points and above -Con you are unconscious and dying, losing a
hit point each round until you stabilise or die. Stabilising is a Constitution check
against DC 10 + your negative hit point total.
"""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


@pytest.fixture
def kesst():
    return load_pc("fixtures/pc-kesst.json")


# --- The thresholds ---------------------------------------------------------------

def test_zero_is_disabled_not_dying(kesst):
    """Exactly 0 is conscious but disabled — a distinct state from dying, and the one
    people most often get wrong."""
    kesst.hp = 0
    kesst.apply_hp_state()
    assert kesst.has_condition("disabled")
    assert not kesst.has_condition("dying")


def test_below_zero_is_unconscious_and_dying(kesst):
    kesst.hp = -4
    kesst.apply_hp_state()
    assert kesst.has_condition("unconscious")
    assert kesst.has_condition("dying")
    assert not kesst.has_condition("dead")


def test_negative_con_is_dead(kesst):
    """Kesst has Con 12, so -12 is dead and -11 is not."""
    kesst.hp = -11
    kesst.apply_hp_state()
    assert not kesst.has_condition("dead")
    kesst.hp = -12
    kesst.apply_hp_state()
    assert kesst.has_condition("dead")
    assert not kesst.has_condition("dying"), "the dead have stopped dying"


# --- Bleeding out ------------------------------------------------------------------

def test_a_dying_character_loses_a_hit_point_a_round(kesst):
    kesst.hp = -2
    kesst.apply_hp_state()
    kesst.bleed_out(Dice(seed=1))
    assert kesst.hp == -3


def test_stabilising_stops_the_bleeding(kesst):
    """A Constitution check against DC 10 + the negative total. Seeded so the roll that
    succeeds is the same every run."""
    kesst.hp = -1
    kesst.apply_hp_state()
    for seed in range(60):
        probe = load_pc("fixtures/pc-kesst.json")
        probe.hp = -1
        probe.apply_hp_state()
        result = probe.bleed_out(Dice(seed=seed))
        if result["outcome"] == "stable":
            assert probe.has_condition("stable")
            assert not probe.has_condition("dying")
            assert result["dc"] == 10 + abs(probe.hp)
            return
    pytest.fail("no seed in 60 produced a stabilisation")


def test_bleeding_out_far_enough_kills(kesst):
    """Con 12, so the eleventh point below zero is the last one."""
    kesst.hp = -11
    kesst.apply_hp_state()
    result = kesst.bleed_out(Dice(seed=3))
    assert result["outcome"] == "dead"
    assert kesst.has_condition("dead")


def test_the_stable_do_not_keep_bleeding(kesst):
    kesst.hp = -3
    kesst.apply_hp_state()
    kesst.remove_condition("dying")
    kesst.add_condition("stable")
    assert kesst.bleed_out(Dice(seed=1)) is None
    assert kesst.hp == -3


def test_fresh_damage_starts_the_dying_again(kesst):
    """Stabilised is not safe: being hit again puts you back to bleeding."""
    kesst.hp = -3
    kesst.apply_hp_state()
    kesst.remove_condition("dying")
    kesst.add_condition("stable")

    kesst.remove_condition("stable")      # the blow that reopens it
    kesst.take_damage(1)
    kesst.apply_hp_state()
    assert kesst.has_condition("dying")


# --- In a fight ---------------------------------------------------------------------

def test_the_round_tick_bleeds_the_dying(kesst):
    """The dying lose their point when the round turns over, not when they are hit."""
    scene = Scene()
    scene.add(kesst)
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    engine = Engine(scene, Dice(seed=11))
    engine.run(engine.validate([{
        "op": "begin_encounter", "params": {"sides": {"pc": ["pc"], "them": ["c1"]}},
    }]))

    kesst.hp = -2
    kesst.apply_hp_state()
    before = kesst.hp

    # `bleeding` is overwritten on every round wrap, so collect it as it happens rather
    # than reading it at the end — she may have stabilised by then, and an empty report
    # from a later round says nothing about the first.
    reported = []
    for _ in range(len(scene.initiative) * 2):
        scene.advance_turn()
        reported.extend(scene.bleeding)

    assert kesst.hp < before
    assert reported, "the round tick should report who bled"
    assert reported[0]["ref"] == "pc"


def test_a_dying_character_does_not_get_a_turn(kesst):
    scene = Scene()
    scene.add(kesst)
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    engine = Engine(scene, Dice(seed=5))
    engine.run(engine.validate([{
        "op": "begin_encounter", "params": {"sides": {"pc": ["pc"], "them": ["c1"]}},
    }]))
    kesst.hp = -1
    kesst.apply_hp_state()
    assert not scene.conscious("pc")
    assert {scene.advance_turn() for _ in range(4)} == {"c1"}
