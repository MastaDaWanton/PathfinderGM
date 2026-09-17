"""A question answered with something nobody asked for.

Reported from the table 2026-09-17, with a screenshot. The player typed:

    /gm what are the people around me doing in reaction to this?

and got back a `WHO:` roster of everyone present with their hit points, followed by the
full rules text of the spell **Negative Reaction** — school, casting time, range,
duration, saving throw, components. The GM was never asked anything.

Two independent faults produced that, and they compound:

  **"reaction" matched a spell.** `_match`'s last clause found the term as a whole word
  anywhere inside a name, so one ordinary English word pulled a rules entry out of the
  middle of "negative reaction". The docstring directly above it already promised
  "never a loose contains", and at word granularity that is exactly what it was.

  **The engine answering at all stopped the GM being asked.** `answer()` returns as soon
  as any section produces a line, and "people" matches the `who` topic. So a question
  only a narrator could answer was answered by a keyword index.

The roster was not wrong. It was beside the point — the engine holds who is present and
what their hit points are; it does not hold what they are doing about the bodies on the
cobbles, and no amount of state ever will.
"""
from __future__ import annotations

import pytest

from play import gm_answers

REPORTED = "what are the people around me doing in reaction to this?"


# A stand-in index rather than the real catalogue: the point is the matcher's rule, and
# a test that depended on a spell keeping its name would fail for the wrong reason.
NAMES = {"negative reaction": "the spell", "magic missile": "mm", "power attack": "pa"}


def test_one_ordinary_word_no_longer_pulls_a_rules_entry():
    """The half of the bug that put a spell block under the question."""
    assert gm_answers._match(NAMES, "reaction") is None


def test_naming_the_thing_properly_still_finds_it():
    """The lookup is narrowed, not removed. Two words in sequence is somebody naming a
    rules entry; one ordinary word is somebody speaking English."""
    assert gm_answers._match(NAMES, "negative reaction") == "the spell"
    assert gm_answers._match(NAMES, "power attack") == "pa"
    assert gm_answers._match(NAMES, "magic missile") == "mm"


def test_an_exact_name_and_a_prefix_are_untouched():
    """The two clauses above the narrowed one. A player who types the whole name, or the
    start of it, is unambiguously naming it."""
    assert gm_answers._match({"fireball": "fb"}, "fireball") == "fb"
    assert gm_answers._match({"magic missile": "mm"}, "magic") == "mm"


def test_the_cost_of_the_narrowing_is_stated():
    """A single mid-name word no longer finds its entry, and that is the right way
    round: failing to find a lookup sends the question to the GM, while finding the
    wrong one answers a question nobody asked *and* stops the GM being asked at all."""
    assert gm_answers._match(NAMES, "missile") is None


@pytest.mark.parametrize("question", [
    REPORTED,
    "how are they reacting?",
    "what do the merchants think of me?",
    "what is the crowd doing",
    "how does the guard seem",
    "what are they saying about the rift",
])
def test_a_question_about_behaviour_goes_to_the_gm(question):
    """These ask for a reading of the scene, which is the one thing the GM is for. The
    engine's own lines are still gathered and handed over as grounding — the question
    does not stop being about the people who are actually there."""
    assert gm_answers.wants_a_reading(question), question


@pytest.mark.parametrize("question", [
    "who is here",
    "how many hit points do I have",
    "what is in my pack",
    "where am I",
    "what time is it",
    "what quests do I have",
])
def test_a_question_about_state_is_still_answered_by_the_engine(question):
    """The engine pass is cheaper, certain, and labelled as fact. Routing these to the
    model would trade an answer that is true for one that reads well."""
    assert not gm_answers.wants_a_reading(question), question


def test_the_reported_question_would_no_longer_be_answered_by_the_index():
    """Both faults at once, which is how it reached the player: the topic matched on
    'people', the lookup matched on 'reaction', and between them the GM was never
    asked."""
    assert "who" in gm_answers.topics_for(REPORTED)     # the roster still matches
    assert gm_answers.wants_a_reading(REPORTED)         # and it no longer decides
    assert gm_answers._match(NAMES, "reaction") is None
