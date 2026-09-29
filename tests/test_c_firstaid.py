"""Lane C — first aid (rules/firstaid.py, the `_op_check` branch).

Design C §4.2, confirmed by the critic (fix-interfaces §1.4 C3): no path in the engine let
a Heal check stabilise anybody. `_op_check` resolved Heal like any skill, and a dying
patient went on losing a hit point a round whatever the roll — while the bonesetter's and
the ferryman's own starts hand the player exactly that check. The rule (CRB Heal, first
aid): DC 15, and "a stable character regains no hit points but stops losing them".
"""
from __future__ import annotations

from rules import firstaid
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


def _table(seed: int):
    scene = Scene(location_id=None)
    scene.add(load_pc("fixtures/pc-thessaly.json"))
    patient = scene.add(instantiate("guildhand", scene=scene, name="the beaten fighter"),
                        zone="engaged")
    patient.hp = -1
    patient.apply_hp_state()
    assert firstaid.dying(patient)
    return scene, Engine(scene, Dice(seed)), patient


def _first_aid(engine, ref: str, dc: int):
    return engine.run(engine.validate([{
        "op": "check", "actor": "pc", "target": ref, "visibility": "hidden",
        "because": "first aid", "params": {"skill": "heal", "dc": dc}}])).outcomes[0]


def test_first_aid_is_dc_fifteen_whatever_the_plan_wrote():
    """The DC is the rule's, never the plan's: a plan that writes an easy DC 5 is still
    held to fifteen."""
    _scene, engine, patient = _table(1)
    out = _first_aid(engine, patient.ref, 5)
    assert out.dc["value"] == firstaid.DC == 15


def test_a_made_check_leaves_the_patient_stable_and_a_missed_one_does_not():
    """Stable: no longer dying, no hit points back. Over a range of seeds both answers
    occur, and each is what the roll against fifteen says."""
    seen = set()
    for seed in range(40):
        _scene, engine, patient = _table(seed)
        out = _first_aid(engine, patient.ref, 15)
        made = out.verdict == "success"
        seen.add(made)
        assert patient.has_state("state.down.stable") is made, (seed, out.tell)
        assert patient.has_state("state.down.dying") is (not made)
        assert patient.hp == -1, "first aid heals nothing"
        assert ("is stable" in out.tell) is made
    assert seen == {True, False}


def test_a_heal_check_on_somebody_not_dying_is_an_ordinary_check():
    """Only a DYING target makes it first aid; everything else resolves as it did."""
    scene = Scene(location_id=None)
    scene.add(load_pc("fixtures/pc-thessaly.json"))
    well = scene.add(instantiate("guildhand", scene=scene, name="a well man"))
    engine = Engine(scene, Dice(3))
    out = _first_aid(engine, well.ref, 10)
    assert out.dc["value"] == 10
    assert not well.has_state("state.down.stable")


def test_the_door_of_its_own_rolls_at_fifteen():
    """`firstaid.stabilise` — for anybody the engine rolls for — is the same rule."""
    _scene, engine, patient = _table(9)
    out = firstaid.stabilise(engine, engine.scene.pc(), patient)
    assert out.dc["value"] == 15
    assert patient.has_state("state.down.stable") is (out.verdict == "success")
