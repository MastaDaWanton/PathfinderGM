"""Swift Strikes is a passive, and passives are never "used".

Watched live: Swift Strikes sat on the abilities bar as a button, the player clicked it
in place of attacking — "use swift strikes" queued as their turn — and the fight went
rounds without a single to-hit rolled. A passive is not an action; it modifies the
attacks the player actually declares.
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
    e = Engine(scene, dice=Dice(seed=7))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    return scene, e


def _attack(e, full=False):
    """A PC attack rolled by the engine: visibility hidden so the test does not have to
    play the dice popup's suspension ping-pong for every swing."""
    return e.run(e.validate([{
        "op": "attack", "actor": "pc", "target": "c1", "visibility": "hidden",
        "params": ({"full_attack": True} if full else {}),
        "because": "test"}])).outcomes[-1]


def _swings(outcome):
    return sum(1 for r in outcome.rolls if r.label.startswith("Attack"))


def test_a_passive_is_not_on_the_usable_list():
    from play.views import _usable_abilities

    names = [a["name"].lower() for a in _usable_abilities(_bender())]
    assert "extracorporeal blood armament" in names     # a real active, still there
    assert "swift strikes" not in names


def test_using_a_passive_is_refused_with_the_reason():
    scene, e = _fight()
    with pytest.raises(IntentError, match="always active"):
        e.run(e.validate([{"op": "use_ability", "actor": "pc",
                           "params": {"ability": "swift strikes"},
                           "because": "test"}]))


def test_the_first_attack_on_a_target_is_single():
    scene, e = _fight()
    assert _swings(_attack(e)) == 1


def test_subsequent_attacks_on_the_same_target_strike_twice():
    """The user's ruling: "an always active passive that makes me hit twice on
    subsequent attacks against the same target." +1 swing on a standard action."""
    scene, e = _fight()
    _attack(e)
    assert _swings(_attack(e)) == 2


def test_a_subsequent_full_attack_gains_two():
    scene, e = _fight()
    _attack(e)
    out = _attack(e, full=True)
    base = len(_bender().attack_sequence("unarmed", True))
    assert _swings(out) == base + 2


def test_first_blood_does_not_survive_the_encounter():
    """`attacked` is the fight's memory, not the character's: a new encounter against
    the same creature starts from a single swing again."""
    scene, e = _fight()
    _attack(e)
    scene.end_encounter()
    assert scene.attacked == set()


def test_a_character_without_the_passive_never_doubles():
    scene = Scene()
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("thug", scene=scene, name="the thug"))
    e = Engine(scene, dice=Dice(seed=7))
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
    _attack(e)
    assert _swings(_attack(e)) == 1
