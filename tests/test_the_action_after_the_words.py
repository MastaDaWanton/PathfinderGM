"""What the character does after what they say is still read as done.

Measured 2026-09-25 by probe: `redact_speech` blanked a speech verb's complement to the
end of its sentence, and the sentence ended at . ! ? ; or "then" — not at "and". So "I
ask the smith about the axe and buy it" lost "buy it", and "I say nothing and attack the
guard" read as no violence at all. Every injector and the plan schema's `must_contain`
read the redacted line.
"""
from __future__ import annotations

import pytest

from gm import judgement


@pytest.mark.parametrize("line,kept", [
    ("I ask the smith about the axe and buy it", "buy it"),
    ("I say nothing and attack the guard", "attack the guard"),
    ("I shout a warning, and then I draw my sword", "draw my sword"),
    ("I answer him and walk out", "walk out"),
])
def test_the_second_action_survives(line, kept):
    assert kept in judgement.redact_speech(line)


@pytest.mark.parametrize("line,hidden", [
    ("I tell him to leave and go home", "go home"),
    ("I say that I'll pay and go", "go"),
    ("I ask the woman if she will sell and leave town", "leave town"),
    ('I say "run and hide" to the children', "hide"),
])
def test_what_was_said_stays_said(line, hidden):
    red = judgement.redact_speech(line)
    assert hidden not in red.split(), (line, red)


def test_violence_after_words_is_violence():
    from gm.judgement import VIOLENCE

    assert VIOLENCE.search(judgement.redact_speech("I say nothing and attack the guard"))
