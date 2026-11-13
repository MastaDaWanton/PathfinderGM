"""A coup de grâce with a non-lethal blow knocks out longer; it never kills.

Measured on master before this (2026-11-13): a coup de grâce with a sap — non-lethal by
its own trait — dealt non-lethal damage and then rolled the lethal coup's Fortitude save,
and a failure went through `Actor.die`: a bound ogre given a sap's coup de grâce died of
it on 29 of 39 seeds.

The owner's ruling (2026-11-13): a coup de grâce with a non-lethal weapon (a sap, an
unarmed strike, or a lethal weapon pulled at -4) is allowed. It is an automatic critical
dealing non-lethal damage; the victim saves on Fortitude at DC 10 + the damage dealt; on a
failure they stay unconscious for 1d4 hours, engine-rolled, on their own clock that the
hourly non-lethal healing cannot lift; on a success, ordinary non-lethal rules. Never a
death save. A lethal coup de grâce is unchanged (tests/test_coup_de_grace.py).
"""
from __future__ import annotations

import re

import pytest

from rules import coup_de_grace as coup_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


def _bound_ogre():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    ogre = s.add(instantiate("ogre", scene=s, name="the ogre"))
    ogre.add_condition("helpless", source="bound hand and foot")
    return s, ogre


def _coup(s, seed, weapon="sap", **params):
    pc = s.actors["pc"]
    if weapon not in pc.weapons:
        pc.weapons.append(weapon)
    pc.equipped = weapon                     # in hand: no draw in front of the blow
    e = Engine(s, Dice(seed=seed))
    res = e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                             "because": "put him to sleep", "visibility": "hidden",
                             "params": {"weapon": weapon, "coup_de_grace": True,
                                        **params}}]))
    return next(o for o in res.outcomes if o.op == "attack")


def _knocked_out(actor):
    return next((e for e in actor.effects
                 if e.kind == "condition" and e.key == coup_mod.KNOCKED_OUT), None)


@pytest.mark.parametrize("weapon,params", [("sap", {}), ("unarmed", {}),
                                           ("rapier", {"lethality": "nonlethal"})],
                         ids=["sap", "unarmed", "pulled-rapier"])
def test_a_failed_save_is_a_longer_knockout_and_never_death(weapon, params):
    """The finding: the sap's coup killed on a failed save. Across seeds both branches
    are seen, nobody dies, the DC is 10 + the non-lethal dealt, and the tell names it."""
    seen = set()
    for seed in range(1, 60):
        s, ogre = _bound_ogre()
        out = _coup(s, seed, weapon, **params)
        assert out.status == "resolved", out.tell
        dmg = next(e for e in out.effects if e.get("kind") == "damage")
        assert dmg.get("lethality") == "nonlethal", dmg
        assert not ogre.has_state("state.down.dead"), out.tell
        save = next(r for r in out.rolls if "Fortitude" in r.label)
        dc = 10 + dmg["amount"]
        assert out.dc["value"] == dc and f"against DC {dc}" in out.tell, out.tell
        held = _knocked_out(ogre)
        failed = "fails the Fortitude save" in out.tell
        assert failed == (held is not None), out.tell
        if failed:
            hours = int(re.search(r"knocked out cold for (\d) hour", out.tell).group(1))
            assert 1 <= hours <= 4
            assert held.rounds_left == hours * 600
            assert ogre.has_state("state.down.unconscious")
        seen.add(failed)
        if seen == {True, False}:
            break
    assert seen == {True, False}, f"only saw {seen}"


def _failed_knockout():
    for seed in range(1, 80):
        s, ogre = _bound_ogre()
        out = _coup(s, seed)
        if _knocked_out(ogre) is not None:
            return s, ogre, out
    raise AssertionError("no failed save in 80 seeds")


def test_non_lethal_healing_does_not_wake_them_but_the_clock_does():
    """The knockout outlasts the non-lethal: healed to nothing, still out; when its 1d4
    hours run out they come round by the normal rules (and removing it is all it
    takes — law 2)."""
    s, ogre, _ = _failed_knockout()
    ogre.nonlethal = 0
    ogre.apply_nonlethal_state()
    assert ogre.has_state("state.down.unconscious"), "non-lethal healing woke them"
    ended = ogre.tick_effects(_knocked_out(ogre).rounds_left)
    assert ended, "the knockout's end is not told"
    assert _knocked_out(ogre) is None
    assert not ogre.has_state("state.down.unconscious")


def test_when_it_ends_with_the_non_lethal_still_past_them_they_stay_down():
    """Normal rules after it: non-lethal still past the hit points keeps them out."""
    s, ogre, _ = _failed_knockout()
    ogre.nonlethal = ogre.hp + 5
    ogre.apply_nonlethal_state()
    ogre.tick_effects(_knocked_out(ogre).rounds_left)
    assert _knocked_out(ogre) is None
    assert ogre.has_state("state.down.unconscious")


def test_a_lethal_coup_still_kills_on_a_failed_save():
    """Unchanged: the rapier, lethal, still writes death on a failure."""
    deaths = 0
    for seed in range(1, 40):
        s, ogre = _bound_ogre()
        _coup(s, seed, "rapier")
        assert _knocked_out(ogre) is None
        deaths += ogre.has_state("state.down.dead")
    assert deaths, "no lethal coup killed across 39 seeds"
