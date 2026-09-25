"""One answer to "is this inside a quotation?", and every pass asks it.

Measured 2026-09-25: nine rules answered that question and disagreed — no rule knew
curly single quotes, two `re.split` copies flipped speech and narration on "guards'" and
"it's", `_ANY_SPEECH` could not cross "it's", and `narration._QUOTED` opened on ‘ but
only closed on a double quote, so it blanked the narrated sentence that introduced Vorn
in "‘Go home,’ the guard says. A stranger named Vorn steps up. “Wait,”". `gm/speech.py`
is the one scanner; the last test here fails if a second one appears.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from gm import speech

KORGATH = ("Korgath leans back. ‘If it’s the leaf you want, you’ll not find it in the "
           "elder-quarter, and don’t let the priests tell you otherwise.’ He drinks.")


def test_curly_single_speech_is_speech_and_its_apostrophes_are_inside_it():
    assert speech.lines(KORGATH) == [
        "If it’s the leaf you want, you’ll not find it in the elder-quarter, and don’t "
        "let the priests tell you otherwise."]
    assert "elder" not in speech.unquoted(KORGATH)
    assert speech.unquoted(KORGATH).strip().endswith("He drinks.")


def test_straight_single_speech_crosses_contractions():
    beat = "'It's late, and I don't like the look of it,' the boatman says."
    assert speech.lines(beat) == ["It's late, and I don't like the look of it,"]
    assert speech.unquoted(beat).strip() == "the boatman says."


def test_a_mixed_beat_keeps_its_narration():
    """The case `narration._QUOTED` got wrong: ‘ opened and only a double quote closed."""
    beat = ("‘Go home,’ the guard says. A stranger named Vorn steps up. “Wait,” he "
            "calls.")
    plain = speech.unquoted(beat)
    assert "A stranger named Vorn steps up." in plain
    assert "Go home" not in plain and "Wait" not in plain


@pytest.mark.parametrize("beat", [
    "The guards' blades catch the light as they pass.",
    "It's quiet; the dog's bowl is empty and the cats' door swings.",
    "They gave 'em a hiding at the docks, and 'tis said they deserved it.",
])
def test_an_apostrophe_is_not_a_quotation(beat):
    assert speech.spans(beat) == []
    assert speech.unquoted(beat) == beat


def test_a_speech_that_runs_into_the_next_paragraph_is_still_speech():
    beat = "“Listen, all of you. The ford is out\n\nand the bridge is watched.” Silence."
    assert speech.unquoted(beat).startswith(" \n\nand the bridge")


def test_blanked_keeps_every_offset():
    blank = speech.blanked(KORGATH)
    assert len(blank) == len(KORGATH)
    at = KORGATH.index("He drinks")
    assert blank[at:at + 9] == "He drinks"
    assert speech.inside(KORGATH, KORGATH.index("elder"))
    assert not speech.inside(KORGATH, at)


def test_split_joins_back_to_the_beat():
    runs = speech.split(KORGATH)
    assert "".join(r for _, r in runs) == KORGATH
    assert [s for s, _ in runs] == [False, True, False]


# --- the three passes the review reproduced wrong on 2026-09-25 --------------------------

def test_a_face_is_never_written_into_a_curly_quoted_line():
    """The phantom elder, in ‘…’ speech: `place_the_face` wrote "The elder is a stooped
    man…" into the middle of Korgath's sentence, because no rule knew curly singles."""
    from gm import narration

    out = narration.place_the_face(KORGATH, "elder", "The elder is a stooped man.")
    assert "The elder is a stooped man." in out
    inside = speech.lines(out)
    assert inside and not any("stooped" in line for line in inside)


def test_second_person_leaves_a_line_of_dialogue_alone():
    from gm import narration

    out, _ = narration.pc_to_second_person(
        "Borin looks up. ‘I can mend this, Kesst,’ he says. Kesst waits.", "Kesst")
    assert "‘I can mend this, Kesst,’" in out
    assert "You wait." in out


def test_a_name_a_man_gives_for_himself_is_not_struck():
    """`"Name's Vorn," he says, and Vorn grins` came back as `"the stranger," he says,
    and the onlooker grins` — his own introduction rewritten, one man given two
    descriptors, and struck before `apply_introductions` could record it."""
    from gm import narration

    out, gone = narration.unname_strangers('"Name\'s Vorn," he says, and Vorn grins.',
                                           set())
    assert out == '"Name\'s Vorn," he says, and Vorn grins.' and gone == []


def test_a_name_said_about_somebody_else_is_still_the_narrators_invention():
    from gm import narration

    out, _ = narration.unname_strangers(
        "'Stay back, Kaida!' the guard shouts as Kaida draws her blade.", set())
    assert "Kaida" not in out


def test_the_close_of_the_last_sentence_is_not_an_opening():
    """The sentence split leaves "' The merchant nods" at the front of a sentence; read
    as an opening, it shielded a dead man's nod from `cut_dead_men_walking`."""
    assert speech.first_opening("' The merchant nods, saying 'Silk.'") > 2


def test_no_second_quotation_rule_is_written_in_the_prose_passes():
    """The ratchet. A quotation regex in gm/ or play/ outside this module is the tenth
    rule, and it will disagree with the nine this replaced. The player's own input keeps
    its double-quote-only rule on purpose (gm/judgement.py `_QUOTED`, play/player_input):
    a player's "I don't" must not open a quotation, and that is a different question."""
    # A span rule is a character class of nothing but quote marks, run up to the NEXT
    # one — `[^"]*`, `[^\"“”]`, `[^']` — which is exactly how each of the nine copies
    # found its close. A class that merely stops AT a quote among other punctuation
    # (`[^.,;!?"“”]`, a phrase ending) is not one.
    span_rule = re.compile(r"\[\^(?=[^\]]*[\"'“”‘’‟])(?:\\?[\"'“”‘’‟]|\\n)+\]")
    player_side = {("gm/judgement.py", "_QUOTED = re.compile("),
                   ("play/player_input.py", "_QUOTED = re.compile(")}
    offenders = []
    for path in list(pathlib.Path("gm").glob("*.py")) + list(pathlib.Path("play").glob("*.py")):
        rel = path.as_posix()
        if rel == "gm/speech.py":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#") or not span_rule.search(line):
                continue
            if any(rel == f and marker in line for f, marker in player_side):
                continue
            offenders.append(f"{rel}:{n}")
    assert offenders == [], ("a quotation rule outside gm/speech.py — use speech.spans / "
                             "speech.unquoted / speech.blanked: " + ", ".join(offenders))
