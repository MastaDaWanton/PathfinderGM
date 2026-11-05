"""Battle Blood Ki Pool does what the class says, and an undocumented ability says so.

Measured on the owner's report of 2026-11-01 (Corvin T., Control Blood 2 on battle blood):
"use Battle Blood Ki Pool" resolved with no effects and the tell "Battle Blood Ki Pool is a
Control Blood 2 ability of the battle blood path; Corvin T. has reached 2" — the tier
message, printed for a tier he HAD reached, status resolved, ki unspent, nothing applied.
The ability had no document; the class's words (content/classes/blood-bending.json) are
"Spend 1 ki point as a swift action to: make 1 extra attack at highest bonus, gain +20 ft
speed, or gain +4 dodge bonus to AC for 1 round" — the monk's ki pool (CRB p.58).
"""
from __future__ import annotations

import pytest

from rules import classbuilder, classes as classes_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict
from tests._board import face_to_face


def _bender(level=3):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["class"] = "blood bending"
    d["level"] = level
    d["ranks"] = {}
    d["paths"] = ["battle blood"]
    return from_dict(d, ref="pc")


def _engine(level=3):
    scene = Scene()
    scene.add(_bender(level))
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    e = Engine(scene, dice=Dice(seed=7))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    face_to_face(scene)
    return scene, e


def _use(e, ability):
    return e.run(e.validate([{"op": "use_ability", "actor": "pc",
                              "params": {"ability": ability}, "because": "test"}])
                 ).outcomes[-1]


def test_the_panel_offers_each_mode_as_a_swift_use_with_the_ki_left():
    """The combat panel's Swift menu builds "<name> (<mode>)" buttons from `choices`
    (04-combat-and-turns.js); the bar shows uses as (left/most)."""
    from play.views import _usable_abilities

    entry = next(a for a in _usable_abilities(_bender()) if a["name"] == "Battle Blood Ki Pool")
    assert entry["action"] == "swift" and entry["aim"] == "self"
    assert entry["choices"] == ["attack", "speed", "dodge"]
    assert entry["pool"] == "ki" and entry["uses"] == entry["max"] and entry["cost"] == 1


def test_the_class_file_validates_with_the_document():
    assert classbuilder.validate_class(classes_mod.get("blood bending")) == []


def test_dodge_spends_one_ki_and_lays_four_dodge_ac_for_a_round():
    scene, e = _engine()
    pc = scene.pc()
    ki, ac = pc.pool("ki").current, pc.ac()
    out = _use(e, "Battle Blood Ki Pool (dodge)")
    assert out.status == "resolved", out.tell
    assert pc.pool("ki").current == ki - 1
    assert pc.ac() == ac + 4
    assert "+4 dodge to AC" in out.tell
    assert any(r.get("kind") == "resource" and r.get("pool") == "ki" for r in out.effects)
    assert any(str(r.get("origin", "")).startswith("ability:battle blood/")
               for r in out.effects)
    # A round later it is gone.
    scene.advance_turn()
    scene.advance_turn()
    assert pc.ac() == ac


def test_speed_adds_twenty_feet_for_a_round():
    scene, e = _engine()
    pc = scene.pc()
    before = pc.speed_feet
    out = _use(e, "Battle Blood Ki Pool (speed)")
    assert out.status == "resolved", out.tell
    assert pc.speed_feet == before + 20


def test_the_attack_mode_adds_one_swing_at_full_bonus_and_is_spent_by_it():
    """One extra swing at iteration 0 on the attack it is spent on, then gone: a second
    attack the same round swings once."""
    scene, e = _engine()
    pc = scene.pc()
    scene.actors["c1"].hp = scene.actors["c1"].hp_max = 300
    assert pc.attack_sequence("unarmed") == [0]
    out = _use(e, "Battle Blood Ki Pool (attack)")
    assert out.status == "resolved", out.tell
    assert pc.attack_sequence("unarmed") == [0, 0]
    hit = e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                             "visibility": "hidden", "params": {}, "because": "test"}])
                ).outcomes[-1]
    swings = [r for r in hit.rolls if r.label.startswith("Attack")]
    assert len(swings) >= 2
    assert pc.attack_sequence("unarmed") == [0]


def test_no_mode_named_is_refused_with_the_modes_listed_and_no_ki_spent():
    scene, e = _engine()
    pc = scene.pc()
    ki = pc.pool("ki").current
    out = _use(e, "Battle Blood Ki Pool")
    assert out.status == "refused"
    assert "attack" in out.tell and "speed" in out.tell and "dodge" in out.tell
    assert pc.pool("ki").current == ki


def test_an_empty_pool_refuses():
    scene, e = _engine()
    pc = scene.pc()
    pc.pool("ki").current = 0
    out = _use(e, "Battle Blood Ki Pool (dodge)")
    assert out.status == "refused" and "ki" in out.tell


def test_below_the_tier_it_is_refused_with_the_tier_named():
    scene, e = _engine(level=1)
    out = _use(e, "Battle Blood Ki Pool (dodge)")
    assert out.status == "refused" and "Control Blood 2" in out.tell


def test_an_ability_with_no_rules_is_refused_as_unsupported_never_resolved():
    """The general fallback: a reached ability the class file gives no effects and no
    document is said as unsupported, status refused — never a resolved no-op. Measured
    with a synthetic path ability, as the shipped file's own undocumented names may gain
    documents later."""
    from rules import leveling

    scene, e = _engine()
    pc = scene.pc()
    det = leveling.path_detail("blood bending", "battle blood")
    tier_two = (det.get("tiers") or {}).get("2") or []
    bare = next((n for n in tier_two
                 if not (det.get("effects") or {}).get((det.get("resolves") or {}).get(n, ""))
                 and not (det.get("grants") or {}).get((det.get("resolves") or {}).get(n, ""))
                 and n.lower() not in {p.lower() for p in det.get("passive") or ()}
                 and not leveling.toggle_key(pc, n.lower())), None)
    if bare is None:
        pytest.skip("every tier-2 battle blood ability has rules now")
    out = _use(e, bare)
    assert out.status == "refused", out.tell
    assert "no rules the engine can run" in out.tell
