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
from pagesource import table_source


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


# --- the turn that stopped with nothing to answer (found in play, 2026-08-22) --------

DEAD_END = (
    "You quickly dress yourself, pulling on your worn leather tunic and cinching your "
    "belt around your waist. The guildhand's eyes flicker towards you as you move, his "
    "expression still wary but slightly less tense than before. His gaze lingers on the "
    "small pouch at your side, where you keep your few remaining lucite crystals. You "
    "take a deep breath, trying to calm the air of unease that seems to cling to "
    "everything in this room. The woman on the bed stirs, her dark eyes fluttering open "
    "as she takes in the scene before her. She looks pale and drawn, with dark circles "
    "under her eyes. 'What do you need?' you ask the guildhand, trying to keep your "
    "tone neutral."
)


def test_a_question_mark_inside_dialogue_is_not_a_hand_back():
    """Verbatim from a live turn. The rule tested `"?" in text`, the character's own
    speech supplied the question mark, and the beat shipped: the player's character
    asked the guildhand something, nobody answered, and the scene stopped with nothing
    for the player to respond to."""
    review = narration.review(DEAD_END, min_chars=320)
    assert "no-hand-back" in {f.kind for f in review.findings}


def test_a_question_three_sentences_from_the_end_is_still_not_a_hand_back():
    """Why the ending is tested rather than the un-quoted body.

    Stripping the speech would have caught the turn above too — but it accepts any
    question anywhere, including one the narration has since walked away from. The
    hand-back is by definition the last thing in the turn.
    """
    text = ("What kind of person keeps a room like this? " + "The lamp swings out over "
            "the yard and back again. " * 10)
    assert "?" in narration.unquoted(text)          # the weaker rule would pass this
    assert "no-hand-back" in {f.kind for f in narration.review(text, min_chars=320).findings}


def test_the_players_own_speech_is_never_mistaken_for_the_hand_back():
    """`asks_player_to_narrate` reads the *closing* question. Before it required the
    text to end on one, it would have judged "'What do you need?'" — the character
    speaking — and rewritten a line of dialogue into "What do you do?"."""
    assert narration.asks_player_to_narrate(DEAD_END) == ""
    assert narration.fix_hand_back(DEAD_END) == (DEAD_END, "")


def test_a_turn_that_ends_on_a_full_stop_is_flagged_however_long_it_is():
    text = "The lamp swings out over the yard and back again. " * 12
    review = narration.review(text, min_chars=320)
    assert "no-hand-back" in {f.kind for f in review.findings}


# --- Continue: a turn the player takes by not acting ---------------------------------

def test_continue_sends_an_instruction_to_the_gm_not_an_action():
    """"maybe we should add a continue button to ask the narrator to keep going."

    The line is written by the server, not typed into the box: a turn that put "I wait"
    in the input would have the character stand there while the question they had just
    asked went on not being answered."""
    from play.views import CARRY_ON

    assert "take no action" in CARRY_ON
    assert "answer" in CARRY_ON


def test_continue_shows_the_player_nothing_they_did_not_say():
    """The GM is given the whole instruction; the transcript shows the button. Printing
    the instruction back would put words in their mouth on the one turn whose entire
    point is that they said none."""
    from pathlib import Path

    view = Path("play/views.py").read_text(encoding="utf-8")
    assert 'shown = "…" if carry_on else text' in view
    assert '"who": "player", "text": shown' in view
    assert '"who": "player", "text": text' not in view

    page = table_source()
    assert 'id="carryon"' in page
    assert "takeTurn({carry_on: true}, false)" in page


def test_continue_is_not_run_through_the_declaration_check():
    """`player_input.check` refuses a turn that narrates the world — which is exactly
    what this instruction asks the GM to do. Routing it through the check would make
    the button refuse itself."""
    from pathlib import Path

    view = Path("play/views.py").read_text(encoding="utf-8")
    assert "if not carry_on:" in view
    assert "said = player_input.check(text)" in view



def test_dialogue_full_of_contractions_is_still_dialogue():
    """Measured on the 60-turn audit of 2026-08-26: a boatman's speech in single
    quotes — "'But that's just between you and me, right?'" — was carved at its
    contractions by a single-quote pattern that could not cross an apostrophe, and
    "between you and me" leaked into narration, where the first-person detector read
    the narrator as having a body. An apostrophe inside a word is never a closing
    quote; the pair boundaries are whitespace ones."""
    speech = ("'We carry all sorts of goods,' he says. 'But I'll let you in "
              "on a little secret: that's just between you and me, right?' "
              "He glances around the dock.")
    assert narration.narrator_in_first_person(speech) == []

    # And a possessive is not an opening quote: nothing here is dialogue, and the
    # narrator's own unquoted "I" must stay visible to the detector.
    told = "The guards' spears crossed the miners' path, and I watched them go."
    assert "I" in narration.unquoted(told)
