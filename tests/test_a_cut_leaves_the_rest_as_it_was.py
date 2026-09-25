"""Cutting a sentence out of a beat leaves the rest of the beat exactly as it was.

Measured 2026-09-25: the cutting passes rebuilt the beat as `" ".join(kept)`, so one cut
sentence flattened every paragraph break in the beat, and cutting a scorched oak before
`"Stand fast," she says` left a stray space inside the quotation. And the detectors that
read `unquoted(text)` returned sentences without their dialogue, which the cutters then
looked for among the RAW sentences — a flagged sentence with a line of speech in it was
silently never cut. The sentence splitter also broke at "Dr." and split "..." into empty
sentences.
"""
from __future__ import annotations

from gm import narration


def test_a_cut_keeps_the_paragraphs():
    beat = ("The square is loud with gulls.\n\nThe guards press in from the north. "
            "A fishwife laughs.\n\nYou wait.")
    out, cut = narration.cut_phantom_opposition(beat)
    if cut:
        assert "\n\n" in out, "a cut flattened the paragraphs"
    out2 = narration._without(beat, [(beat.index("The guards"),
                                      beat.index("A fishwife"))])
    assert out2 == "The square is loud with gulls.\n\nA fishwife laughs.\n\nYou wait."


def test_a_flagged_sentence_carrying_speech_is_cut():
    """The blow landed on a turn that only declared the fight — and the sentence also
    carries his shout, which is why the old raw-sentence match never found it."""
    beat = ("He roars. Your fist connects with his jaw as he yells, \"Enough!\" "
            "The crowd gasps.")
    blows = [{"joined": True, "tell": "Battle is joined."}]
    out, early = narration.cut_premature_blows(beat, blows)
    assert early, "the landing sentence was found"
    assert "connects" not in out, "and it was cut, speech and all"
    assert out.startswith("He roars.") and "The crowd gasps." in out


def test_a_title_does_not_end_a_sentence():
    assert narration._sentences("Dr. Varn waits by the door. He nods.") == [
        "Dr. Varn waits by the door.", "He nods."]


def test_an_ellipsis_is_one_end_and_a_close_quote_stays_with_its_sentence():
    assert narration._sentences("'Wait...' She stops. 'Go!' He goes.") == [
        "'Wait...'", "She stops.", "'Go!'", "He goes."]
