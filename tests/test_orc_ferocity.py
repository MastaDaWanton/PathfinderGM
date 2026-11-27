"""Orc Ferocity, the racial trait, apart from the Bestiary's ferocity.

Measured before (fix/orc-ferocity): b5-core made every half-orc PC fight on below 0
indefinitely. Feat loop b5-core built the universal monster rule ("remains conscious and
can continue fighting even if its hit point total is below 0 ... loses 1 hit point each
round") on the tag `ferocity`, and the tag was carried by RACES: the core half-orc and the
race builder's `ferocity` evolution. The racial trait is the CRB's Orc Ferocity: "Once per
day, when a half-orc is brought below 0 hit points but not killed, he can fight on for 1
more round as if disabled. At the end of his next turn, unless brought to above 0 hit
points, he immediately falls unconscious and begins dying."
"""
from __future__ import annotations

import json

from pathfindergm import files
from rules import races
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import ORC_FEROCITY, load_pc


def _fight(race="half-orc"):
    s = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    pc.race = race
    s.add(pc)
    thug = instantiate("thug", scene=s, name="the thug")
    s.add(thug)
    Engine(s, Dice(seed=5))
    s.initiative = [(pc.ref, 20), (thug.ref, 10)]
    s.sides = {"pc": [pc.ref], "them": [thug.ref]}
    s.round, s.turn = 1, 1                   # the thug's turn: he is about to drop her
    return s, pc, thug


def _drop(pc, to=-2):
    pc.hp = to
    return pc.apply_hp_state()


def test_a_half_orc_fights_on_one_round_then_falls_dying():
    """b5-core made every half-orc PC fight on below 0 indefinitely: two whole rounds
    later she was still up. By the book, one more round as if disabled, then out."""
    s, pc, _ = _fight()
    assert pc.has_state(ORC_FEROCITY) and not pc.has_state("ferocity")
    said = _drop(pc)
    assert "orc ferocity" in said and "disabled" in said
    assert not pc.is_down and pc.has_state("state.impaired.disabled")
    assert not pc.has_state("state.impaired.staggered"), "disabled, not the monster's stagger"
    assert not pc.has_condition("dying")
    assert s.advance_turn() == pc.ref        # round 2: her next turn, still standing
    assert not pc.is_down
    s.advance_turn()                         # the end of that turn
    assert pc.is_down and pc.has_condition("unconscious") and pc.has_condition("dying")
    assert not pc.has_condition("disabled")
    told = {(h.get("kind"), h.get("condition")) for h in s.hazards}
    assert ("condition", "unconscious") in told and ("condition", "dying") in told


def test_dropped_on_her_own_turn_she_gets_the_next_one():
    """"At the end of his NEXT turn": a turn already running when she fell is not it."""
    s, pc, _ = _fight()
    s.turn = 0
    _drop(pc)
    s.advance_turn()                         # her own turn ends: still fighting on
    assert not pc.is_down
    assert s.advance_turn() == pc.ref        # round 2, her next turn
    assert not pc.is_down
    s.advance_turn()
    assert pc.has_condition("dying")


def test_the_second_fall_that_day_is_at_once_and_a_night_restores_it():
    s, pc, _ = _fight()
    _drop(pc)
    pc.hp = 5
    pc.after_healing(7)                      # healed above 0: the round is swept
    assert not pc.has_state("state.fighting-on")
    _drop(pc)
    assert pc.has_condition("unconscious") and pc.has_condition("dying"), \
        "once per day: the second fall is a fall"
    pc.hp = 5
    pc.clear_states("state.down")
    pc.apply_hp_state()
    pc.clear_states("recovery.rest")         # what a night's rest sweeps
    _drop(pc)
    assert not pc.is_down, "the night gave it back"


def test_healed_above_zero_during_the_round_she_stays_up():
    s, pc, _ = _fight()
    _drop(pc)
    s.advance_turn()
    pc.hp = 3
    pc.after_healing(5)
    s.advance_turn()
    assert not pc.is_down and not pc.has_condition("dying")


def test_the_monster_rule_still_fights_on_past_its_turns():
    """A summons with Ferocious Summons' `ferocity` keeps b5-core's universal rule."""
    s, _, thug = _fight()
    thug.apply_effect(ActiveEffect(name="summoned gifts", kind="buff", key="summons-granted",
                                   source="Ferocious Summons", origin="test",
                                   tags=("ferocity",)))
    thug.hp = -2
    thug.apply_hp_state()
    for _ in range(4):
        s.advance_turn()
    assert not thug.is_down and thug.has_state("state.impaired.staggered")
    assert not thug.has_state(ORC_FEROCITY)


def test_a_homebrew_race_with_the_ferocity_evolution_gets_the_racial_rule():
    """The race builder's `ferocity` evolution, and an old card that wrote the bare tag."""
    for doc in ({"id": "built-fero", "name": "Built Fero", "evolutions": [{"id": "ferocity"}]},
                {"id": "built-fero", "name": "Built Fero", "tags": ["ferocity"]}):
        path = races.homebrew_dir(make=True) / "built-fero.json"
        files.write_text(path, json.dumps(doc))
        try:
            d = races.document("built-fero")
            assert ORC_FEROCITY in d["tags"] and "ferocity" not in d["tags"], doc
            s, pc, _ = _fight(race="built-fero")
            _drop(pc)
            s.advance_turn()
            s.advance_turn()
            assert pc.has_condition("dying"), doc
        finally:
            files.remove(path)
