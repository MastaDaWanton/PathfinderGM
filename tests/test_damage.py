"""Temporary hit points and damage reduction.

Both are core 1e and both were missing. Until now `take_damage` was one line —
`self.hp -= amount` — so there was no stage in the pipeline where anything could reduce
a hit or absorb it. Every buff that grants temporary hit points and every creature with
DR was unplayable, and the homebrew work needs both before it can start: an entire Blood
Bending path is built on Temp HP and Iron Clot is DR 2/5/8/12/—.

The rules being enforced, from the Core Rulebook:

- Temporary hit points are lost first, and are not restored by healing.
- Temporary hit points from different sources do not stack; only the best applies.
- Damage reduction subtracts from each hit, never reduces damage below 0, and applies
  only to physical damage — DR 10/- does not soften a fireball.
- When a creature has several kinds of DR, only the best applicable one applies.
"""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import Reduction, from_dict, load_pc
from rules.tables import is_physical, normalise_damage_type


@pytest.fixture
def pc():
    return load_pc("fixtures/pc-kesst.json")


@pytest.fixture
def scene(pc):
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    s.add(instantiate("thug", scene=s, name="the thug"))
    return s


@pytest.fixture
def engine(scene):
    return Engine(scene, Dice(seed=42))


# --- temporary hit points ----------------------------------------------------------------

def test_temporary_hit_points_are_spent_before_real_ones(pc):
    pc.hp = 9
    pc.gain_temp_hp(5, "rage")
    d = pc.take_damage(4, "slashing")
    assert d["absorbed"] == 4 and d["taken"] == 0
    assert pc.hp == 9 and pc.temp_hp == 1


def test_damage_carries_through_once_the_temporary_ones_are_gone(pc):
    pc.hp = 9
    pc.gain_temp_hp(5, "rage")
    d = pc.take_damage(8, "slashing")
    assert d["absorbed"] == 5 and d["taken"] == 3
    assert pc.hp == 6 and pc.temp_hp == 0


def test_temporary_hit_points_do_not_stack(pc):
    """1e: "temporary hit points from different sources do not stack; only the best
    applies." Adding them is the obvious implementation and compounds — two 10-point
    sources would read as 20, survive a hit that should have dropped the character, and
    nothing on the sheet would show why."""
    pc.gain_temp_hp(10, "rage")
    pc.gain_temp_hp(6, "aid another")
    assert pc.temp_hp == 10

    pc.gain_temp_hp(14, "a better source")
    assert pc.temp_hp == 14
    assert pc.temp_hp_source == "a better source"


def test_the_same_source_refreshes_rather_than_being_ignored(pc):
    """Re-entering a rage is not stacking. Without this, a second rage of equal value
    would be refused for being merely equal and the character would fight on with
    whatever was left of the first."""
    pc.gain_temp_hp(10, "rage")
    pc.take_damage(7, "slashing")
    assert pc.temp_hp == 3

    pc.gain_temp_hp(10, "rage")
    assert pc.temp_hp == 10


def test_healing_does_not_restore_temporary_hit_points(pc):
    pc.hp = 4
    pc.gain_temp_hp(6, "rage")
    pc.take_damage(6, "slashing")
    assert pc.temp_hp == 0

    pc.heal(20)
    assert pc.hp == pc.hp_max
    assert pc.temp_hp == 0


def test_healing_stops_at_your_maximum(pc):
    pc.hp = 8
    assert pc.heal(50) == 1
    assert pc.hp == pc.hp_max == 9


def test_losing_the_last_temporary_point_forgets_its_source(pc):
    """Otherwise the source lingers and the next grant from it is treated as a refresh of
    something that is no longer there."""
    pc.gain_temp_hp(3, "rage")
    pc.take_damage(3, "slashing")
    assert pc.temp_hp == 0 and pc.temp_hp_source == ""


def test_temporary_hit_points_can_exceed_your_maximum(pc):
    """They sit on top of hp_max rather than inside it — that is the whole point of them."""
    pc.hp = pc.hp_max
    pc.gain_temp_hp(20, "rage")
    assert pc.temp_hp == 20
    pc.take_damage(15, "slashing")
    assert pc.hp == pc.hp_max


# --- damage reduction --------------------------------------------------------------------

def test_damage_reduction_comes_off_every_hit(pc):
    pc.hp = 20
    pc.hp_max = 20
    pc.reductions = [Reduction(5, source="iron clot")]
    d = pc.take_damage(12, "slashing")
    assert d["reduced"] == 5 and d["taken"] == 7
    assert pc.hp == 13


def test_damage_reduction_cannot_heal_you(pc):
    """"Reduce damage by 5" against a hit for 3 is a hit for 0, not a gain of 2."""
    pc.hp = 9
    pc.reductions = [Reduction(5)]
    d = pc.take_damage(3, "bludgeoning")
    assert d["reduced"] == 3 and d["taken"] == 0
    assert pc.hp == 9


def test_damage_reduction_does_not_apply_to_energy(pc):
    """A creature with DR 10/- still takes a fireball in full. Without a damage-type
    vocabulary DR would silently soak acid and fire, and Blood Bending's Caustic Blood —
    acid, against a path whose defining feature is DR — would do nothing at all."""
    pc.hp = 20
    pc.hp_max = 20
    pc.reductions = [Reduction(10)]
    d = pc.take_damage(8, "fire")
    assert d["reduced"] == 0 and d["taken"] == 8


def test_only_the_best_damage_reduction_applies(pc):
    """1e does not add them together."""
    pc.hp = 30
    pc.hp_max = 30
    pc.reductions = [Reduction(2, source="a"), Reduction(7, source="b"),
                     Reduction(5, source="c")]
    d = pc.take_damage(20, "piercing")
    assert d["reduced"] == 7


def test_a_bypassed_reduction_steps_aside_for_the_next_best(pc):
    pc.hp = 30
    pc.hp_max = 30
    pc.reductions = [Reduction(10, bypass="silver"), Reduction(3)]
    assert pc.take_damage(20, "slashing", traits=("silver",))["reduced"] == 3
    assert pc.damage_reduction("slashing").amount == 10


def test_reduction_that_nothing_bypasses_is_never_bypassed(pc):
    pc.reductions = [Reduction(4)]
    assert pc.take_damage(10, "slashing", traits=("silver", "magic"))["reduced"] == 4


def test_reduction_is_applied_before_temporary_hit_points(pc):
    """The other order is quietly wrong: a DR 5 character would lose 5 temporary hit
    points to an attack for 5 that never hurt them at all."""
    pc.hp = 9
    pc.reductions = [Reduction(5)]
    pc.gain_temp_hp(6, "rage")
    d = pc.take_damage(5, "slashing")
    assert d["reduced"] == 5 and d["absorbed"] == 0
    assert pc.temp_hp == 6 and pc.hp == 9


# --- damage types ------------------------------------------------------------------------

@pytest.mark.parametrize("said,means", [
    ("lightning", "electricity"), ("flame", "fire"), ("frost", "cold"),
    ("blunt", "bludgeoning"), ("Slash", "slashing"), ("stabbing", "piercing"),
])
def test_the_words_a_narrator_reaches_for_are_understood(said, means):
    """Left alone, "lightning" reads as an unknown type, and an unknown type counts as
    physical — which would hand DR a reduction it should never get."""
    assert normalise_damage_type(said) == means


def test_an_unknown_damage_type_counts_as_physical():
    """The cautious direction. An unrecognised type that DR ignores is damage a player
    can see and query; one that DR soaks is damage that vanishes silently."""
    assert is_physical("gravitic")
    assert not is_physical("acid")


# --- through the engine ------------------------------------------------------------------

def test_the_engine_grants_temporary_hit_points(engine, scene):
    pc = scene.pc()
    engine.run(engine.validate([
        {"op": "temp_hp", "actor": "pc", "because": "the blood closes over her arms",
         "params": {"amount": 8, "source": "blood rage"}},
    ]))
    assert pc.temp_hp == 8


def test_a_second_source_is_refused_and_says_so(engine, scene):
    engine.run(engine.validate([
        {"op": "temp_hp", "actor": "pc", "params": {"amount": 8, "source": "rage"}}]))
    res = engine.run(engine.validate([
        {"op": "temp_hp", "actor": "pc", "params": {"amount": 3, "source": "a potion"}}]))
    assert "do not stack" in res.outcomes[0].tell
    assert scene.pc().temp_hp == 8


def test_the_engine_heals(engine, scene):
    pc = scene.pc()
    pc.hp = 3
    res = engine.run(engine.validate([
        {"op": "heal", "actor": "pc", "because": "a draught of something foul",
         "params": {"amount": 4}},
    ]))
    assert pc.hp == 7
    assert "recovers 4 hit points" in res.outcomes[0].tell


def test_healing_above_zero_stops_the_dying(engine, scene):
    pc = scene.pc()
    pc.hp = -3
    pc.apply_hp_state()
    assert pc.has_condition("dying")

    engine.run(engine.validate([{"op": "heal", "actor": "pc", "params": {"amount": 6}}]))
    assert pc.hp == 3
    assert not pc.has_condition("dying") and not pc.has_condition("unconscious")


def test_a_soaked_hit_says_where_the_damage_went(engine, scene):
    """Damage that disappears without explanation is the failure this exists to prevent:
    the GM narrates a wound nobody took, and the player has no way to see why the number
    on screen disagrees with the number rolled."""
    thug = scene.actors["c1"]
    thug.reductions = [Reduction(5, source="iron clot")]
    res = engine.run(engine.validate([
        {"op": "damage", "target": "c1", "because": "the beam catches it",
         "params": {"amount": 12, "type": "slashing"}},
    ]))
    tell = res.outcomes[0].tell
    assert "7" in tell and "DR 5/—" in tell


def test_an_energy_hit_is_not_soaked_and_reads_plainly(engine, scene):
    thug = scene.actors["c1"]
    thug.reductions = [Reduction(5)]
    res = engine.run(engine.validate([
        {"op": "damage", "target": "c1", "params": {"amount": 9, "type": "fire"}}]))
    assert "9 fire damage." in res.outcomes[0].tell


# --- round trip --------------------------------------------------------------------------

def test_temporary_hit_points_and_reductions_survive_a_save(pc):
    from rules.sheet import to_dict

    pc.gain_temp_hp(7, "rage")
    pc.reductions = [Reduction(5, bypass="silver", source="iron clot")]
    back = from_dict(to_dict(pc))
    assert back.temp_hp == 7 and back.temp_hp_source == "rage"
    assert back.reductions[0].amount == 5 and back.reductions[0].bypass == "silver"


@pytest.mark.parametrize("written,amount,bypass", [
    ("DR 5/silver", 5, "silver"), ("DR 2/-", 2, ""), ("10/magic", 10, "magic"),
])
def test_a_stat_block_may_write_reduction_the_way_the_book_does(written, amount, bypass):
    """The bestiary is authored by hand and saves are written by code; both have to load."""
    a = from_dict({"name": "thing", "kind": "npc", "hp": 10, "hp_max": 10,
                   "abilities": {"str": 10, "dex": 10, "con": 10,
                                 "int": 10, "wis": 10, "cha": 10},
                   "reductions": [written]})
    assert a.reductions[0].amount == amount
    assert a.reductions[0].bypass == bypass
