"""The GM asking the player to do the GM's job.

Measured in live play on 2026-08-22, from a saved transcript: three consecutive beats
ended "What do you see?", "What do you notice next?" and "What do you feel next?". The
player had said "I follow her" and "I enter and look around" — describing the room is
the only thing the narrator is there for, and it handed that back every time.

llama3.1:8b wrote all three. The campaign's turn log records zero rejections on all ten
turns, and the fallback model needs five before it is reached, so it never ran once.

The rule that produced it is the one immediately above the new check in `review`: a
turn must end in a question, and "What do you see?" is the cheapest question there is.
That is the shape-of-the-prompt-becomes-the-shape-of-the-output trap, and the answer is
the one that has always held here — detect it in code.
"""
from __future__ import annotations

import pytest

from gm import narration


# --- what counts as outsourcing -------------------------------------------------------

@pytest.mark.parametrize("ending", [
    "What do you see?",
    "What do you notice next?",
    "What do you feel next?",
    "What do you find?",
    "What do you hear?",
    "What does the room look like to you now?",
    "How do you feel about that?",
])
def test_a_question_about_their_senses_is_the_gms_job(ending):
    assert narration.asks_player_to_narrate(f"The door swings open. {ending}") == ending


@pytest.mark.parametrize("ending", [
    "What do you do?",
    "What do you do now?",
    "What do you want to do?",
    "How do you answer her?",
    "Do you follow, or let her go?",
    "What do you say to that?",
])
def test_a_question_about_what_they_do_is_the_hand_back(ending):
    """"What do you want to do?" reaches for `want` and is a perfectly good hand-back:
    the thing being asked for is still an action."""
    assert narration.asks_player_to_narrate(f"She waits. {ending}") == ""


def test_an_npc_may_ask_the_player_anything_they_like():
    """Spoken dialogue is not the narrator handing the turn back. An NPC asking "what
    do you see out there?" is a person in the room talking."""
    text = ('The watchman leans out over the parapet. "What do you see out there?" '
            'he asks, not looking round. What do you do?')
    assert narration.asks_player_to_narrate(text) == ""


def test_only_the_closing_question_is_judged():
    """A question in the middle of a beat is rhetoric or dialogue; the last one is the
    hand-back, and that is the one that has to be an action."""
    text = ("What kind of person keeps a room like this? You will not find out standing "
            "in the doorway. What do you do?")
    assert narration.asks_player_to_narrate(text) == ""


# --- the backstop -------------------------------------------------------------------

def test_the_question_is_replaced_with_the_one_every_example_uses():
    text = ("The room is small, the air thick with the scent of roses. She closes the "
            "door behind her and leans against it. What do you notice next?")
    fixed, gone = narration.fix_hand_back(text)
    assert gone == "What do you notice next?"
    assert fixed.endswith("What do you do?")
    assert "notice next" not in fixed
    # The description the model did write is kept; only the outsourcing is cut.
    assert "scent of roses" in fixed


def test_a_good_hand_back_is_left_exactly_alone():
    text = "She leans against the door, watching you. What do you do?"
    assert narration.fix_hand_back(text) == (text, "")


def test_the_replacement_is_by_span_not_by_replace():
    """`str.replace` is a silent no-op the moment whitespace shifts between the
    extracted sentence and the text it came from — the trap `cut_outcome_claims`
    already documents. Here the question is split across a newline."""
    text = "The candelabra gutters.\n  What   do you\n  see?"
    fixed, gone = narration.fix_hand_back(text)
    assert gone
    assert fixed == "The candelabra gutters. What do you do?"


# --- and the reviewer complains about it, so the model gets a chance to fix it --------

def test_the_review_names_it_and_says_whose_job_it_is():
    text = ("The corridor is long and hung with tapestries, and the incense is thick "
            "enough to taste. She stops at a door that does not match its neighbours "
            "and works a small key into it. The lock gives. Inside, past her shoulder, "
            "the light is low and there is something under the smell of roses that you "
            "cannot place. What do you see?")
    review = narration.review(text, min_chars=320)
    kinds = {f.kind for f in review.findings}
    assert "asks-the-player-to-narrate" in kinds
    assert "no-hand-back" not in kinds        # it did ask something, just the wrong thing
    finding = next(f for f in review.findings if f.kind == "asks-the-player-to-narrate")
    assert "your job, not theirs" in finding.fix_hint


def test_the_turn_log_records_which_model_spoke():
    """This defect could only be pinned on a model by counting rejections and reasoning
    about which one the schedule would have reached. `Attempt` has always carried the
    field; the save dropped it."""
    from pathlib import Path

    saved = Path("play/views.py").read_text(encoding="utf-8")
    assert '"model": a.model' in saved
