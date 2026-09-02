"""Spendable pools: ki, rage rounds, uses per day, stacks on an enemy.

Blood Bending forced three things a first sketch of the resource model did not have, and
each came from an ability that would otherwise have been unimplementable — `scope: target`
because blood stacks live on the enemy, dice cooldowns because Vampiric Recovery recharges
on 1d3 turns, and upkeep because a bloodlink costs 1d10 non-lethal every round or it drops.

The maximum is a formula over sheet values so it follows a level-up. A pool frozen at the
number the character had at 1st level is a bug that only shows itself several sessions in.
"""
from __future__ import annotations

import pytest

from rules import resources
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import from_dict, load_pc, to_dict


@pytest.fixture
def pc():
    a = load_pc("fixtures/pc-kesst.json")
    a.level = 6
    a.abilities["con"] = 16
    return a


@pytest.fixture
def engine(pc):
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    s.add(instantiate("thug", scene=s, name="the thug"))
    return Engine(s, Dice(seed=42))


# --- formulas ------------------------------------------------------------------------------

def test_the_ki_pool_is_the_classs_own_formula(pc):
    """"a pool of ki points equal to 1/2 his level + his Con modifier"."""
    resources.define(pc, {"id": "ki", "max": "floor(level/2) + con_mod"})
    assert pc.pool("ki").maximum == 6                   # floor(6/2) + 3


def test_rage_rounds_are_the_classs_own_formula(pc):
    """"rage for 4 + her Constitution modifier rounds per day. For each level after 1st
    she can rage for 2 additional rounds."\""""
    resources.define(pc, {"id": "rage", "max": "4 + con_mod + 2*(level-1)"})
    assert pc.pool("rage").maximum == 17                # 4 + 3 + 10


def test_a_formula_follows_a_level_up(pc):
    """Recomputed rather than frozen, which is the whole reason the formula is stored."""
    resources.define(pc, {"id": "ki", "max": "floor(level/2) + con_mod"})
    pc.level = 10
    resources.define(pc, {"id": "ki", "max": "floor(level/2) + con_mod"})
    assert pc.pool("ki").maximum == 8


def test_per_hit_die_is_not_per_level(pc):
    """Blood Bending has two Hit Dice per level, and anything counted per Hit Die is wrong
    by a factor of two if the formula reads `level`."""
    pc.hit_dice_per_level = 2
    resources.define(pc, {"id": "surge", "max": "hit_dice"})
    assert pc.pool("surge").maximum == 12


def test_a_formula_naming_nothing_says_what_it_could_have_named(pc):
    problem = resources.check("con_mod + wibble")
    assert "wibble" in problem and "con_mod" in problem


def test_a_formula_cannot_execute_anything():
    """A formula arrives from a homebrew file, and a file is not a trusted thing to run.
    Parsed to an AST and walked with a whitelist rather than passed to `eval`."""
    assert "not allowed" in resources.check("__import__('os').system('echo hi')")
    assert "not allowed" in resources.check("open('x').read()")
    assert resources.check("(level + 1) * 2") == ""


def test_a_formula_rounds_down_once_at_the_end(pc):
    """1e rounds fractions down unless it says otherwise, and rounding at each step
    compounds differently depending on how the formula was written."""
    resources.define(pc, {"id": "odd", "max": "level/4"})
    assert pc.pool("odd").maximum == 1                  # 6/4 = 1.5


# --- spending ------------------------------------------------------------------------------

def test_spending_and_running_out(pc):
    resources.define(pc, {"id": "ki", "max": "6"})
    assert pc.spend_pool("ki", 2)["ok"]
    assert pc.pool("ki").current == 4
    refused = pc.spend_pool("ki", 99)
    assert not refused["ok"] and "4 left" in refused["why"]


def test_not_yet_and_not_any_more_are_different_refusals(pc):
    """The player is owed the difference: they lead to different next moves."""
    resources.define(pc, {"id": "vortex", "max": "1"})
    pc.spend_pool("vortex", 1)
    pc.gain_pool("vortex", 1)
    pc.start_cooldown("vortex", 2)

    refused = pc.spend_pool("vortex", 1)
    assert "recharges in 2 rounds" in refused["why"]


def test_a_dice_cooldown_counts_down_with_the_round(pc):
    """Vampiric Recovery and Vortex Pull recharge on 1d3 turns — dice, not an integer."""
    resources.define(pc, {"id": "vortex", "max": "1", "cooldown": "1d3"})
    pc.start_cooldown("vortex", 3)
    assert not pc.pool("vortex").ready
    pc.tick_pools(2)
    assert not pc.pool("vortex").ready
    assert pc.tick_pools(1) == ["vortex"]
    assert pc.pool("vortex").ready


def test_a_night_refills_what_a_night_refills(pc):
    resources.define(pc, {"id": "ki", "max": "6", "refresh": "rest.night"})
    resources.define(pc, {"id": "once", "max": "1", "refresh": "never"})
    pc.spend_pool("ki", 6)
    pc.spend_pool("once", 1)

    assert pc.refresh_pools("rest.night") == ["ki"]
    assert pc.pool("ki").current == 6
    assert pc.pool("once").current == 0


def test_a_night_also_satisfies_any_rest(pc):
    """A pool that only refilled on the exact word would quietly never come back."""
    resources.define(pc, {"id": "breath", "max": "2", "refresh": "rest.any"})
    pc.spend_pool("breath", 2)
    assert "breath" in pc.refresh_pools("rest.night")


# --- stacks, which live on somebody else -----------------------------------------------------

def test_a_stack_lives_on_the_creature_it_was_applied_to(engine):
    """The field that forced the model to change. Blood stacks are applied by one ability
    and spent by four others, and the owner never holds them."""
    thug = engine.scene.actors["c1"]
    thug.gain_pool("blood_stack", 3, source="blood javelin")
    assert thug.pool("blood_stack").current == 3
    assert engine.scene.pc().pool("blood_stack") is None


def test_a_stack_pool_is_created_on_the_enemy_who_never_had_one(engine):
    """An enemy has no notion of blood stacks until somebody puts one there."""
    thug = engine.scene.actors["c1"]
    assert thug.pool("blood_stack") is None
    thug.gain_pool("blood_stack", 1)
    assert thug.pool("blood_stack").current == 1


def test_an_uncapped_pool_has_no_ceiling(engine):
    """Two Blood Bending paths declare "there is no upper limit" in as many words."""
    thug = engine.scene.actors["c1"]
    for _ in range(30):
        thug.gain_pool("blood_stack", 1)
    assert thug.pool("blood_stack").current == 30


# --- through the engine -----------------------------------------------------------------------

def test_the_engine_grants_a_stack_to_a_target(engine):
    engine.run(engine.validate([
        {"op": "resource", "because": "the javelin leaves two stacks",
         "params": {"pool": "blood_stack", "to": "c1", "amount": 2}},
    ]))
    assert engine.scene.actors["c1"].pool("blood_stack").current == 2


def test_the_engine_spends_and_says_what_is_left(engine):
    pc = engine.scene.pc()
    resources.define(pc, {"id": "ki", "max": "6"})
    res = engine.run(engine.validate([
        {"op": "resource", "actor": "pc", "because": "one more attack",
         "params": {"pool": "ki", "amount": 1, "spend": True}},
    ]))
    assert "spends 1 ki" in res.outcomes[0].tell
    assert pc.pool("ki").current == 5


def test_spending_an_empty_pool_is_refused_not_ignored(engine):
    """An ability that fires with an empty pool is one the player thinks they still
    have. Refused out loud — and printed, since stage 7: how much is left in a pool is
    a fact the player could not have known, and the sentence is theirs to read."""
    pc = engine.scene.pc()
    resources.define(pc, {"id": "ki", "max": "1"})
    pc.spend_pool("ki", 1)
    out = engine.run(engine.validate([
        {"op": "resource", "actor": "pc",
         "params": {"pool": "ki", "amount": 1, "spend": True}}])).outcomes[0]
    assert out.effects == [] and "0 left" in out.tell
    assert pc.pool("ki").current == 0


def test_spending_can_start_a_rolled_cooldown(engine):
    pc = engine.scene.pc()
    resources.define(pc, {"id": "vortex", "max": "1"})
    engine.run(engine.validate([
        {"op": "resource", "actor": "pc", "because": "the stacks tear loose",
         "params": {"pool": "vortex", "amount": 1, "spend": True, "cooldown": "1d3"}},
    ]))
    assert 1 <= pc.pool("vortex").cooldown_left <= 3


def test_a_night_in_the_engine_refills_the_pools(engine):
    pc = engine.scene.pc()
    resources.define(pc, {"id": "ki", "max": "6", "refresh": "rest.night"})
    pc.spend_pool("ki", 6)

    res = engine.run(engine.validate([{"op": "rest", "actor": "pc",
                                       "params": {"kind": "night"}}]))
    assert pc.pool("ki").current == 6
    assert "Recovered: ki" in res.outcomes[0].tell


# --- persistence -------------------------------------------------------------------------------

def test_pools_survive_a_save(pc):
    resources.define(pc, {"id": "ki", "max": "floor(level/2) + con_mod",
                          "refresh": "rest.night"})
    pc.spend_pool("ki", 2)
    pc.start_cooldown("ki", 2)

    back = from_dict(to_dict(pc))
    got = back.pool("ki")
    assert got.current == 4 and got.maximum == 6
    assert got.max_formula == "floor(level/2) + con_mod"
    assert got.cooldown_left == 2 and not got.ready


def test_the_sheet_shows_what_can_be_spent(pc):
    resources.define(pc, {"id": "ki", "max": "6"})
    shown = pc.summary()["pools"]
    assert shown and shown[0]["id"] == "ki" and shown[0]["max"] == 6
