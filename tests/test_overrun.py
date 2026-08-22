"""The commonest sentence in the game, and the manoeuvre nobody asked for.

Measured in live play and captured in a screenshot: "I attack the beast" came back as
`{"op": "attack", "params": {"manoeuvre": "overrun"}}` with no target, on five consecutive
attempts, and the turn died with "attack: a overrun needs a target".

Two separate defects met in the same turn:

  * The GM chose a manoeuvre the player never described. The old rule only dropped one
    when the player had used an explicitly wounding verb — "stab", "cut", "kill" — and
    "attack" is not one of them, so the plainest thing a player can say fell through
    every branch of the check.
  * The attack named nobody, and the engine refused it rather than looking at the one
    creature standing in front of the character.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import parse_all
from rules.sheet import load_pc


@pytest.fixture
def scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the beast"))
    return s


def reviewed(text, raw, scene):
    intents = parse_all(raw)
    return intents, judgement.review(text, intents, scene)


# --- the manoeuvre nobody asked for ---------------------------------------------------

def test_plain_attack_does_not_become_an_overrun(scene):
    """The exact turn from the screenshot."""
    intents, verdict = reviewed(
        "I attack the beast",
        [{"op": "attack", "actor": "pc", "target": "c1", "because": "she goes for it",
          "params": {"manoeuvre": "overrun"}}], scene)
    assert "manoeuvre" not in intents[0].params
    assert any(f.kind == "manoeuvre-nobody-asked-for" for f in verdict.corrections)


@pytest.mark.parametrize("text", [
    "I attack the beast",
    "I hit it",
    "I go for him",
    "I swing at the thing",
    "I fight back",
])
def test_no_manoeuvre_cue_means_no_manoeuvre(text, scene):
    intents, _ = reviewed(
        text, [{"op": "attack", "actor": "pc", "target": "c1",
                "params": {"manoeuvre": "grapple"}}], scene)
    assert "manoeuvre" not in intents[0].params


def test_a_manoeuvre_the_player_did_describe_survives(scene):
    """The check must not flatten every manoeuvre out of the game."""
    intents, verdict = reviewed(
        "I sweep his legs out from under him",
        [{"op": "attack", "actor": "pc", "target": "c1",
          "params": {"manoeuvre": "trip"}}], scene)
    assert intents[0].params["manoeuvre"] == "trip"
    assert not verdict.corrections


def test_the_wrong_manoeuvre_is_still_swapped_rather_than_dropped(scene):
    intents, verdict = reviewed(
        "I grab him and hold him down",
        [{"op": "attack", "actor": "pc", "target": "c1",
          "params": {"manoeuvre": "overrun"}}], scene)
    assert intents[0].params["manoeuvre"] == "grapple"
    assert any(f.kind == "wrong-manoeuvre" for f in verdict.corrections)


def test_an_npc_may_still_choose_a_manoeuvre():
    """`npc_turn` does not go through `judgement.review`, so a thug can still decide to
    grapple. If it ever does, this rule would neuter every monster in the game."""
    import inspect

    from gm import agent

    source = inspect.getsource(agent.GMAgent.npc_turn)
    assert "judgement.review" not in source


# --- the attack with nobody on the end of it --------------------------------------------

def test_an_attack_with_no_target_takes_the_only_one_there(scene):
    """Filled in *before* validation. Putting this in `review` did nothing at all, because
    `review` runs after the validation that had already killed the turn."""
    fixed = judgement.fill_obvious_targets(
        [{"op": "attack", "actor": "pc", "because": "she goes for it"}], scene)
    assert fixed[0]["target"] == "c1"


def test_it_does_not_guess_when_there_is_more_than_one(scene):
    """Two creatures is a choice, and choosing for the player is worse than asking."""
    scene.add(instantiate("thug", scene=scene, name="the other one"))
    fixed = judgement.fill_obvious_targets([{"op": "attack", "actor": "pc"}], scene)
    assert not fixed[0].get("target")


def test_a_corpse_is_not_a_candidate(scene):
    scene.add(instantiate("thug", scene=scene, name="the dead one"))
    scene.actors["c2"].add_condition("dead")
    fixed = judgement.fill_obvious_targets([{"op": "attack", "actor": "pc"}], scene)
    assert fixed[0]["target"] == "c1"


def test_a_stated_target_is_never_overridden(scene):
    fixed = judgement.fill_obvious_targets(
        [{"op": "attack", "actor": "pc", "target": "c9"}], scene)
    assert fixed[0]["target"] == "c9"


def test_only_attacks_are_touched(scene):
    fixed = judgement.fill_obvious_targets([{"op": "narrate_only"}], scene)
    assert "target" not in fixed[0]


def test_the_whole_turn_that_died_five_times_now_runs(scene):
    """The point of all of it, in the order the agent actually does it: fill the target,
    validate, review, resolve."""
    e = Engine(scene, Dice(seed=4))
    raw = [{"op": "attack", "actor": "pc", "because": "she goes for it",
            "params": {"manoeuvre": "overrun"}}]

    intents = e.validate(judgement.fill_obvious_targets(raw, scene))
    verdict = judgement.review("I attack the beast", intents, scene)
    assert any(f.kind == "manoeuvre-nobody-asked-for" for f in verdict.corrections)
    assert "manoeuvre" not in intents[0].params

    res = e.run(e.validate([i.as_dict() for i in intents]))
    assert res.status in ("complete", "awaiting_player_roll")
