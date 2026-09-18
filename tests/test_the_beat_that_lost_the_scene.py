"""The deflection check that threw away good prose, and what ships in its place.

Measured 2026-09-18. On the second sixty-turn audit after the narrator guards, four prose
turns lost BOTH models to `reintroduces_the_present` and shipped the engine's lines
instead — "You eats. You take stall.", the holding line, "You are already at the edge." In
the player's own save (`dorito.json`), four turns of fourteen. Every one was a false
positive against a role-noun actor name:

  * "the distinct, heavy crest of a merchant guild house" on a wax seal — an actor named
    `merchant` present;
  * "a man" in a market — an actor the cast ledger had promoted as `man`;
  * "a stranger" in the woods — an actor named `stranger`.

The check exists for a real case (an intimate beat the model would not continue, rewritten
as a door broken down and "a woman is there", the one woman in the scene) and it still
catches that one. What changed: only an INTRODUCTION counts, "another" is excluded, a
common-noun name is a candidate only when the scene holds them as unique, and a beat the
check rejects on every model ships with the article made definite rather than not at all.
"""
from __future__ import annotations

import inspect

import pytest

from gm import judgement, narration
from rules.engine import Scene

WOMAN = ("The heavy door gives way with a groan. Behind it, a woman is there, slumped in a "
         "high-backed chair.")


# --- the four false positives, and the true positive -------------------------------------


@pytest.mark.parametrize("beat, present", [
    ("He pulls out a small, wax-sealed scroll. The seal is the distinct, heavy crest of a "
     "merchant guild house. He holds it out to you.", ["merchant", "guard"]),
    ("The boatwright leans on his bench. Across the way a man is haggling over rope, and "
     "the water slaps the pilings.", ["man", "boatwright", "merchant"]),
    ("The transition from the gate to the tree line is immediate. A stranger's footprints "
     "cross the mud ahead of you.", ["stranger", "guard"]),
    ("Another merchant leans over the counter and names a price.", ["merchant"]),
    ("You hear a man's voice behind the shutters, low and angry.", ["man"]),
])
def test_a_role_noun_in_a_crowded_scene_is_not_a_reintroduction(beat, present):
    assert narration.reintroduces_the_present(beat, present) == []


def test_the_measured_deflection_is_still_caught():
    """She was the one other person in the scene, and the beat met her as a stranger."""
    assert narration.reintroduces_the_present(WOMAN, ["the woman"]) == ["the woman"]
    # Or the subject of the standing thread, in a fuller scene.
    assert narration.reintroduces_the_present(
        WOMAN, ["the woman", "the innkeeper"], thread="the woman") == ["the woman"]
    # In a fuller scene with no thread, "a woman" is one woman of several possible.
    assert narration.reintroduces_the_present(WOMAN, ["the woman", "the innkeeper"]) == []


def test_a_proper_name_is_always_a_candidate():
    beat = "You turn. There is a Threnn at the door, hat in hand, as if you had never met."
    assert narration.reintroduces_the_present(beat, ["Threnn", "merchant", "man"]) == ["Threnn"]


def test_only_an_introduction_counts():
    """Subject after a boundary, "there is a", "you see a" — followed by presence or
    action. A possessive or a compound noun is not somebody walking in."""
    assert narration.reintroduces_the_present("A woman steps out of the dark.", ["the woman"]) == ["the woman"]
    assert narration.reintroduces_the_present("You see a woman by the fire.", ["the woman"]) == ["the woman"]
    assert narration.reintroduces_the_present("There's a woman at the rail.", ["the woman"]) == ["the woman"]
    assert narration.reintroduces_the_present("You hear a woman's laugh upstairs.", ["the woman"]) == []
    assert narration.reintroduces_the_present("It is a woman thing, he says.", ["the woman"]) == []


def test_a_group_is_still_a_group():
    beat = "A man leans on the gatepost and spits."
    assert narration.reintroduces_the_present(beat, ["man", "man", "man", "man"]) == []


# --- the backstop ------------------------------------------------------------------------


def test_the_article_is_made_definite_when_every_model_lost_the_scene():
    out, made = narration.definite_present(WOMAN, ["the woman"])
    assert made == ["the woman"]
    assert "Behind it, the woman is there" in out
    same, none = narration.definite_present("She looks up as you enter.", ["the woman"])
    assert same == "She looks up as you enter." and none == []


def test_narrate_turn_retries_with_the_present_named_and_then_keeps_the_beat():
    """The shape every fix here has held: detect, one targeted retry naming the defect,
    then the next model, then a deterministic backstop — never the holding line under a
    thousand characters of good prose."""
    from gm import agent

    src = inspect.getsource(agent.GMAgent.narrate_turn)
    assert "retry, present named" in src
    assert "definite_present" in src
    assert src.index("reintroduces_the_present") < src.index("retry, present named") \
        < src.index("definite_present")
    assert "already here" in src


# --- what shipped instead, and never should again ------------------------------------------


def test_the_engines_own_tell_verbs_agree_with_you():
    """"You eats. You take stall." was a whole beat."""
    out, n = narration.pc_to_second_person("Kesst Vayr eats. Kesst Vayr takes stall.", "Kesst Vayr")
    assert out == "You eat. You take stall." and n == 2
    out, _ = narration.pc_to_second_person("Kesst Vayr spends an hour and comes back.", "Kesst Vayr")
    assert out.startswith("You spend an hour and come")


def test_a_question_asked_of_somebody_engages_them_not_the_question():
    """The anchor read "You have not let him what he carries downstream out of your
    sight". The subject stops where the question begins; a bare pronoun continues the
    engagement already on the books rather than replacing it with nobody."""
    s = Scene()
    judgement.update_thread(s, "I ask the boatman what he carries downstream")
    assert s.thread.get("subject") == "the boatman"
    judgement.update_thread(s, "I ask him what he carries downstream")
    assert s.thread.get("subject") == "the boatman", "a pronoun keeps the current engagement"
    judgement.update_thread(s, "I ask the smith about the ore he uses")
    assert s.thread.get("subject") == "the smith"
