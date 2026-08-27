"""The first swing opens the battle; it never fights the battle.

The defect, measured in live play 2026-08-27 (campaign mastadawanton, turn 5): the
player wrote "i strike him one final time to put him out of his misery" over a
stranger dying at -7. One spoken turn then spawned a thug from nowhere ("the player
started a fight with somebody" — inject_fight's default template), began an
encounter, swung, confirmed a critical for 30, killed the thug, ended the fight and
paid out 135 XP — an entire war inside one narrated paragraph, the map never shown,
the combat panel never reached, and the dying man untouched.

Two rules fell out. An attack that finds no fight running (or rides the batch that
started one) is deferred: the encounter forms — initiative, sides, the grid laid —
the tell announces that battle is joined, and the first blow is the player's to
declare on their own combat turn. And a coup de grâce is not a fight being started:
the finishing words plus a downed body silence the fight-making repairs entirely.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


@pytest.fixture
def scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    return s


def test_a_first_swing_opens_the_battle_and_stops(scene):
    """The attack finds no fight, so it makes one and goes no further: encounter
    live, grid laid, initiator holding the turn, no roll asked for, nothing hurt."""
    engine = Engine(scene, Dice(seed=5))
    thug_hp = scene.actors["c1"].hp
    res = engine.run(engine.validate([
        {"op": "attack", "actor": "pc", "target": "c1", "because": "she swings"}]))

    assert scene.in_encounter and scene.grid is not None
    assert scene.current_ref() == "pc", "the initiator keeps the turn they declared"
    assert not scene.awaiting, "no die was offered — the swing did not happen"
    assert scene.actors["c1"].hp == thug_hp
    out = res.outcomes[0]
    assert out.op == "attack" and not out.rolls
    assert any(e.get("kind") == "battle_joined" for e in out.effects)
    assert "Battle is joined" in out.tell and "the thug" in out.tell


def test_the_swing_riding_begin_encounter_is_deferred_too(scene):
    """The GM's own [begin_encounter, attack] batch — inject_fight's triple — must
    not resolve the attack either, or the deferral has a hole exactly where the
    playtest fell through."""
    engine = Engine(scene, Dice(seed=5))
    thug_hp = scene.actors["c1"].hp
    res = engine.run(engine.validate([
        {"op": "begin_encounter",
         "params": {"sides": {"you": ["pc"], "them": ["c1"]}}},
        {"op": "attack", "actor": "pc", "target": "c1", "because": "she swung first"},
    ]))
    assert scene.in_encounter
    assert scene.actors["c1"].hp == thug_hp
    assert any("Battle is joined" in (o.tell or "") for o in res.outcomes)


def test_a_swing_inside_a_running_fight_resolves(scene):
    """The gate is about the first moment only: a fresh batch inside a running
    encounter fights exactly as before."""
    engine = Engine(scene, Dice(seed=5))
    engine.run(engine.validate([
        {"op": "attack", "actor": "pc", "target": "c1", "because": "she swings"}]))
    res = engine.run(engine.validate([
        {"op": "attack", "actor": "pc", "target": "c1", "because": "round one"}]))
    assert scene.awaiting and scene.awaiting["die"] == "1d20"
    assert "Attack" in scene.awaiting["label"]
    _ = res


def test_a_mercy_stroke_on_the_dying_opens_nothing_and_lands(scene):
    """One living combatant is no encounter. The blow the playtest deferred to a
    phantom thug resolves against the body it was aimed at."""
    body = scene.actors["c1"]
    body.hp = -7
    body.add_condition("dying", source="the earlier fight")
    engine = Engine(scene, Dice(seed=5))
    res = engine.run(engine.validate([
        {"op": "attack", "actor": "pc", "target": "c1",
         "because": "out of his misery"}]))
    assert not scene.in_encounter, "a corpse cannot be an opponent"
    # The swing itself proceeds (suspending on the player's own d20) rather than
    # being announced as a battle.
    assert scene.awaiting or all(
        e.get("kind") != "battle_joined" for o in res.outcomes for e in o.effects)


def test_inject_fight_stands_aside_for_a_finishing_blow(scene):
    """Turn 5, verbatim. Before the guard: this exact sentence appended
    [spawn thug, begin_encounter, attack c2] and the player fought a man who did
    not exist while the one they named lay untouched."""
    body = scene.actors["c1"]
    body.hp = -7
    body.add_condition("dying", source="the earlier fight")
    raw = [{"op": "attack", "actor": "pc", "target": "c1", "because": ""}]
    out = judgement.inject_fight(
        raw, "i strike him one final time to put him out of his misery", scene)
    assert out == raw, "the mercy stroke is the whole turn — nothing may be added"


def test_the_redirect_leaves_the_mercy_stroke_on_the_body(scene):
    """With a living bystander in the scene, retargeting a coup de grâce would swing
    it at somebody who was never named. The finishing words pin it to the body."""
    body = scene.actors["c1"]
    body.hp = -7
    body.add_condition("dying", source="the earlier fight")
    scene.add(instantiate("guildhand", scene=scene, name="a bystander"))
    raw = [{"op": "attack", "actor": "pc", "target": "c1", "because": ""}]
    fixed = judgement.redirect_attacks_off_corpses(
        raw, "i finish him off", scene)
    assert fixed is None, "a finishing blow is aimed at the body on purpose"
