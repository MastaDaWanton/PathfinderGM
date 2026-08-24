"""Extracorporeal Blood Armament is a toggle, and the armed punch is its weapon.

The ability used to be fire-and-forget: nothing on screen said whether it still held,
and the user asked for exactly that — "make extracorporeal blood armament a toggle so
the user isn't confused about whether or not its active." The state lives as a
clockless condition, so every place that shows conditions shows it.
"""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, IntentError, Scene
from rules.sheet import from_dict, load_pc, to_dict


def _bender(level=1):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["class"] = "blood bending"
    d["level"] = level
    d["ranks"] = {}
    d["paths"] = ["battle blood"]
    return from_dict(d, ref="pc")


def _fight():
    scene = Scene()
    scene.add(_bender())
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    e = Engine(scene, dice=Dice(seed=11))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    return scene, e


def _use(e, ability="extracorporeal blood armament"):
    return e.run(e.validate([{"op": "use_ability", "actor": "pc",
                              "params": {"ability": ability},
                              "because": "test"}])).outcomes[-1]


def test_using_the_ability_forms_and_dismisses():
    scene, e = _fight()
    pc = scene.actors["pc"]
    out = _use(e)
    assert pc.has_condition("blood armament")
    assert "forms" in out.tell
    out = _use(e)
    assert not pc.has_condition("blood armament")
    assert "fall away" in out.tell


def test_the_toggle_never_expires_on_its_own():
    """A stance is not a spell: rounds tick and the armament holds until dismissed."""
    scene, e = _fight()
    pc = scene.actors["pc"]
    _use(e)
    pc.tick_conditions(600)
    assert pc.has_condition("blood armament")


def test_the_armed_punch_needs_the_armament():
    scene, e = _fight()
    with pytest.raises(IntentError, match="not formed"):
        e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                           "visibility": "hidden",
                           "params": {"weapon": "armed punch"},
                           "because": "test"}]))


def test_the_armed_punch_rolls_blood_plus_fist():
    """Blood DMG + Fist DMG + STR: the blood die is the weapon's own die and the fist
    die rides as an itemised modifier — one visible die, every number named."""
    scene, e = _fight()
    pc = scene.actors["pc"]
    _use(e)
    out = e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                             "visibility": "hidden",
                             "params": {"weapon": "armed punch"},
                             "because": "test"}])).outcomes[-1]
    dmg = [r for r in out.rolls if r.label.startswith("Damage")]
    if dmg:                       # the seeded swing may miss; the weapon shape may not
        assert any("fist die" in m.source for m in dmg[0].modifiers)
    assert pc.weapon("armed punch")["damage"] == "1d8"      # the level-1 blood die


def test_a_held_weapon_never_carries_the_armament():
    """"the armament should not apply through held weapons" — an ordinary rapier
    attack while the armament is formed gains no fist-die rider and no blood die."""
    scene, e = _fight()
    _use(e)
    out = e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                             "visibility": "hidden", "params": {},
                             "because": "test"}])).outcomes[-1]
    for roll in out.rolls:
        assert not any("fist die" in m.source for m in roll.modifiers)


def test_the_panel_offers_the_punch_only_while_formed():
    from play.views import _attack_slots

    pc = _bender()
    assert _attack_slots(pc)["weapons"] == [pc.equipped or "unarmed"]
    pc.add_condition("blood armament", rounds=None, source="test")
    assert "armed punch" in _attack_slots(pc)["weapons"]


def test_the_ability_button_reports_its_state():
    from play.views import _usable_abilities

    pc = _bender()
    entry = next(a for a in _usable_abilities(pc)
                 if a["name"].lower() == "extracorporeal blood armament")
    assert entry["toggle"] is True and entry["active"] is False
    pc.add_condition("blood armament", rounds=None, source="test")
    entry = next(a for a in _usable_abilities(pc)
                 if a["name"].lower() == "extracorporeal blood armament")
    assert entry["active"] is True
