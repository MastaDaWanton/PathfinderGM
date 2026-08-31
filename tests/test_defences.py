"""The four defences become effects — and a potion can finally grant one.

Damage reduction, immunity, energy resistance and vulnerability were four more parallel
stores, the fifth through eighth mechanisms law 2 forbids, and they survived stage 2
because they arrive from a stat block and never expire. Never expiring is what made them
wrong: `effectspec` offers all four types, 123 shipped spells and 13 magic items author
one, and the catalogue's own `blocked` text admitted the consequence — "nothing wears off
yet, so nothing is granted temporarily". `consumables._spec_to_intents` had no branch for
any of them and fell through to `return []`, so a potion of fire resistance was drunk,
the dose was spent, and nothing happened with no error anywhere.
"""
from __future__ import annotations

import pytest

from rules import consumables
from rules.dice import Dice
from rules.engine import Engine, IntentError, Scene
from rules.sheet import Reduction, from_dict, to_dict


def _pc():
    return from_dict({"name": "Subject", "kind": "pc", "hp": 30, "hp_max": 30,
                      "class": "rogue", "level": 1,
                      "abilities": {k: 12 for k in
                                    ("str", "dex", "con", "int", "wis", "cha")}},
                     ref="pc")


def _table():
    pc = _pc()
    s = Scene()
    s.add(pc)
    return pc, Engine(s, Dice(seed=3))


def _drink(engine, spec):
    return engine.run(engine.validate(
        consumables._spec_to_intents(spec, "pc", "drinks it", 1.0)))


# --- the four are one store now --------------------------------------------------------


def test_the_four_defences_live_in_the_one_store():
    a = _pc()
    a.immunities = ["cold"]
    a.resistances = {"fire": 10}
    a.vulnerabilities = ["sonic"]
    a.reductions = [Reduction(5, "silver", "thick hide")]
    kinds = sorted(e.kind for e in a.effects)
    assert kinds == ["damage_reduction", "immunity", "resistance", "vulnerability"]
    # and the views still answer exactly as they did
    assert a.immune_to("cold") and a.resistance("fire") == 10
    assert a.vulnerable_to("sonic")
    assert a.damage_reduction("slashing").amount == 5


def test_two_kinds_of_damage_reduction_stay_two():
    """`apply_effect` treats (kind, key, source) as one record, so keying a defence on
    what it is against alone made DR 10/silver and DR 3/— the same record: the second
    refreshed the first and a creature with two kinds of DR silently had one. The key
    carries what defeats it as well."""
    a = _pc()
    a.reductions = [Reduction(10, bypass="silver"), Reduction(3)]
    assert len(a.reductions) == 2
    assert a.damage_reduction("slashing").amount == 10
    assert a.damage_reduction("slashing", traits=("silver",)).amount == 3


def test_a_defence_is_not_counted_twice_by_the_reader():
    """`damage_reduction` seeded its pool from `reductions` and then walked the effects
    as well. Once `reductions` became a view over those same effects that counted every
    innate DR twice — and best-only would have hidden it until two sources differed."""
    a = _pc()
    a.reductions = [Reduction(4, source="hide")]
    assert len([r for r in a.reductions if r.amount == 4]) == 1
    assert a.damage_reduction("bludgeoning").amount == 4


# --- and a potion can grant one --------------------------------------------------------


def test_a_potion_of_fire_resistance_finally_does_something():
    """The measurement this stage exists for: the dose used to be spent for nothing."""
    pc, engine = _table()
    assert pc.resistance("fire") == 0
    spec = {"type": "resistance", "target": "fire", "amount": 10,
            "duration": {"amount": 10, "unit": "minute"},
            "from": "potion of fire resistance"}
    assert consumables._spec_to_intents(spec, "pc", "drinks", 1.0), \
        "no intents at all — the dose vanishes"
    _drink(engine, spec)
    assert pc.resistance("fire") == 10
    got = pc.take_damage(18, "fire")
    assert got["resisted"] == 10 and got["taken"] == 8


def test_a_granted_defence_wears_off_on_the_one_ticker():
    """Which is the whole reason these could not be granted before: there was no shape
    for a defence that ends."""
    pc, engine = _table()
    _drink(engine, {"type": "resistance", "target": "fire", "amount": 10,
                    "duration": {"amount": 1, "unit": "minute"}, "from": "a potion"})
    assert pc.resistance("fire") == 10
    pc.tick_effects(9)
    assert pc.resistance("fire") == 10, "a minute is ten rounds"
    pc.tick_effects(1)
    assert pc.resistance("fire") == 0


def test_every_one_of_the_four_can_be_granted_and_saved():
    pc, engine = _table()
    _drink(engine, {"type": "damage_reduction", "amount": 5, "bypass": "silver",
                    "duration": {"amount": 1, "unit": "hour"}, "from": "a draught"})
    _drink(engine, {"type": "immunity", "target": "fire",
                    "duration": {"amount": 2, "unit": "hour"}, "from": "a tonic"})
    _drink(engine, {"type": "vulnerability", "target": "cold",
                    "duration": {"amount": 1, "unit": "minute"}, "from": "a curse"})
    assert pc.damage_reduction("slashing").label == "DR 5/silver"
    assert pc.immune_to("fire") and pc.vulnerable_to("cold")

    back = from_dict(to_dict(pc), ref="pc")
    assert back.immune_to("fire") and back.vulnerable_to("cold")
    assert back.damage_reduction("slashing").label == "DR 5/silver"


def test_a_reload_does_not_duplicate_an_innate_defence():
    """The migration reads the flat keys only when the store holds none, because
    `from_dict` rebinds `a.effects` wholesale when a save carries `active_effects` —
    the two plausible implementations fail in opposite directions, one losing every
    legacy save's defences and the other doubling them on every round trip."""
    a = _pc()
    a.immunities = ["cold"]
    a.resistances = {"fire": 10}
    for _ in range(3):
        a = from_dict(to_dict(a), ref="pc")
    assert a.immunities == ["cold"]
    assert a.resistances == {"fire": 10}


def test_a_save_written_before_this_still_loads_its_defences():
    """Nine of the user's twelve campaigns take this branch."""
    a = from_dict({"name": "old", "kind": "npc", "hp": 20, "hp_max": 20,
                   "abilities": {k: 10 for k in
                                 ("str", "dex", "con", "int", "wis", "cha")},
                   "immunities": ["cold"], "resistances": {"fire": 5},
                   "vulnerabilities": ["sonic"],
                   "reductions": [{"amount": 3, "bypass": "", "source": "hide"}]})
    assert a.immune_to("cold") and a.resistance("fire") == 5
    assert a.vulnerable_to("sonic") and a.damage_reduction("slashing").amount == 3


def test_the_defence_op_refuses_with_the_fix_named():
    pc, engine = _table()
    with pytest.raises(IntentError, match="is not a kind of defence"):
        engine.validate([{"op": "defence", "actor": "pc", "because": "t",
                          "params": {"kind": "warding", "against": "fire"}}])
    with pytest.raises(IntentError, match="needs `against`"):
        engine.validate([{"op": "defence", "actor": "pc", "because": "t",
                          "params": {"kind": "immunity"}}])
    with pytest.raises(IntentError, match="needs an amount"):
        engine.validate([{"op": "defence", "actor": "pc", "because": "t",
                          "params": {"kind": "damage_reduction"}}])


def test_an_op_that_declares_a_param_keeps_it():
    """`PARAM_ALIASES` renamed `against` to `opposed_by` for EVERY op, so the defence
    op's own declared param was renamed away and the intent then refused for missing
    it. An alias fires only when the op wants the target and does not declare the word
    itself — otherwise the table is a landmine for every op added after it."""
    from rules.intents import parse_all

    got = parse_all([{"op": "defence", "actor": "pc", "because": "t",
                      "params": {"kind": "immunity", "against": "fire"}}])[0]
    assert got.params["against"] == "fire"
    opposed = parse_all([{"op": "check", "actor": "pc", "because": "t",
                          "params": {"skill": "stealth",
                                     "against": {"ref": "c1",
                                                 "skill": "perception"}}}])[0]
    assert opposed.params["opposed_by"]["skill"] == "perception"
