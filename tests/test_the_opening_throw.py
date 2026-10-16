"""A thing hurled at somebody is an attack, and the throw that opens a fight is rolled.

The 2026-10-16 report (0.2.19, free narrator, the owner's wife's game). In a market the
player wrote "I pick up the hairball and hurl it at the woman with the braid because she
gave me a weird look". Three things went wrong in one turn:

  1. `judgement.review` objected "the player did not attack anyone" on three attempts
     running — VIOLENCE has no "hurl", and PEACEFUL matched the "look" in *her* look —
     while the reading had it right: `attack target=the woman with the braid`;
  2. when the plan's throw did get through, the engine opened the fight ("Battle is
     joined … nothing has landed yet") and never rolled it: `_their_first_blow` asked
     `closing_move` whether the improvised weapon reached, read it as a melee swing from
     fifteen feet, and left the player's blow for a combat panel they never used for it;
  3. the prose landed it anyway, and a repair turned it into a miss that still "stung
     her skin".

What 1e says (CRB, Combat, "How Combat Works"; Improvised Weapons): combat opens on the
act that starts it, and the act is the initiator's — the engine keeps the turn with the
initiator, as it always has (`_ensure_encounter`); an improvised weapon takes -4, and "an
improvised thrown weapon has a range increment of 10 feet". So the declared throw is a
real attack roll: Dex to hit (a throw is a ranged attack), -4, -2 per full increment past
the first, against a target flat-footed until it acts.
"""
from __future__ import annotations

import pytest

from gm import interpret, judgement
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import parse_all
from rules.sheet import load_pc

THROW = {"op": "attack", "actor": "pc", "target": "c1", "because": "the player hurls it",
         "params": {"weapon": "improvised", "item": "hairball", "thrown": True}}


@pytest.fixture
def scene():
    s = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    s.add(instantiate("thug", scene=s, name="the woman with the braid"))
    pc.goods["hairball"] = 1
    return s


def test_the_opening_throw_is_rolled_on_the_players_own_die(scene):
    """Fifteen feet off, no fight running: the throw opens the fight AND asks for the
    player's d20 — before 2026-10-16 it asked for nothing ("Battle is joined" and stop)."""
    engine = Engine(scene, Dice(seed=5))
    res = engine.run(engine.validate([THROW]))
    assert scene.distance_between("pc", "c1") == 15, "the premise: out of arm's reach"
    assert scene.in_encounter
    assert "Battle is joined" in res.outcomes[0].tell
    assert scene.awaiting, "the declared throw waits on the player's die"
    sources = [m["source"] for m in scene.awaiting["breakdown"]]
    assert scene.awaiting["label"] == "Attack with hairball"
    assert "Dex" in sources and "Str" not in sources, "a throw is a ranged attack"
    assert any("not proficient with improvised" in s for s in sources), "the -4"
    assert any(s.startswith("range (15 ft") for s in sources), \
        "the improvised thrown weapon's 10 ft range increment, -2 at fifteen feet"


def test_the_throw_resolves_against_the_flat_footed_target_and_lands_the_thing(scene):
    engine = Engine(scene, Dice(seed=5))
    engine.run(engine.validate([THROW]))
    res = engine.resume(12)
    blow = next(o for o in res.outcomes if o.op == "attack" and o.rolls)
    assert blow.dc["flat_footed"], "she has not acted yet this fight"
    assert "The hairball lies where it fell." in blow.tell
    assert "hairball" not in scene.pc().goods
    assert any(p["name"] == "hairball" for p in scene.props_here())


def test_a_thrown_thing_at_a_person_is_not_unprovoked_when_the_reading_says_attack(scene):
    """The reading's `attack` act counts as the player swinging; the cue words alone
    refused it (VIOLENCE has no "hurl", PEACEFUL matched "look")."""
    line = ("I pick up the hairball and hurl it at the woman with the braid because she "
            "gave me a weird look.")
    assert not judgement.review(line, parse_all([THROW]), scene).ok, \
        "the premise: with no reading the cue words refuse it"
    interpret.remember(line, {"actions": [
        {"act": "take", "object": "the hairball", "span": "pick up the hairball"},
        {"act": "attack", "target": "the woman with the braid",
         "span": "hurl it at the woman with the braid"}]})
    try:
        assert judgement.review(line, parse_all([THROW]), scene).ok
    finally:
        interpret._READINGS.clear()


def test_an_intended_attack_in_the_reading_is_still_no_swing(scene):
    """Only an act done or tried now counts (`interpret.acting`): "I think about throwing
    it at her" commits to nothing."""
    line = "I wonder whether to throw it at her and ask her what she is looking at."
    interpret.remember(line, {"actions": [
        {"act": "attack", "target": "her", "commit": "intended",
         "span": "throw it at her"}]})
    try:
        assert not judgement.review(line, parse_all([THROW]), scene).ok
    finally:
        interpret._READINGS.clear()
