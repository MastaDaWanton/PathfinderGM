"""A player declaring what their character IS, answered at the door.

Reported with a screenshot, 2026-09-18, on 0.1.9. Two turns earlier the same session
had been handled well: "I attempt to implode the boxes" got "the world remains
stubbornly intact", "I swing the longsword cutting reality apart" got "the world does not
tear". Then:

    I reveal my true from as a divine being

and the prose made it so — "The mud at your feet flash-freezes into glass … the silhouette
isn't that of a man, but something towering and ancient. The stranger on the step falls to
his knees … What do you say to them now that the truth is laid bare?"

Why the 0.1.9 gates missed it: `refuse_unnamed_power` turns a claimed faculty into
`use_ability` so the engine's door can refuse it, but this line produced no intent at all,
and a gate on intents has nothing to hold. The fiat door in `play.player_input` catches a
wagon willed into being and has no sheet to read. This door has the sheet, runs before
any model is asked, and gives the same answer the fiat door gives: nothing on the sheet
makes you that, and there is no roll that makes it so — say it out loud if you like, and
the people here decide what they believe.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules.engine import Scene


class _PC:
    is_pc = True
    name = "Dorito"
    ref = "pc"

    def __init__(self, abilities=()):
        self._abilities = list(abilities)


def _scene(abilities=()):
    s = Scene()
    pc = _PC(abilities)
    s.people = {"pc": pc}
    s.actors  # exists on Scene; the pc() lookup below is what the door uses
    return s, pc


@pytest.fixture
def plain(monkeypatch):
    """A character whose sheet grants no form, shape or divinity."""
    s, pc = _scene()
    monkeypatch.setattr(Scene, "pc", lambda self: pc)
    from rules import leveling

    monkeypatch.setattr(leveling, "usable_names", lambda actor: ["Blood Armament", "Iron Skin"])
    return s


@pytest.fixture
def shapeshifter(monkeypatch):
    s, pc = _scene()
    monkeypatch.setattr(Scene, "pc", lambda self: pc)
    from rules import leveling

    monkeypatch.setattr(leveling, "usable_names", lambda actor: ["Wild Shape", "Woodland Stride"])
    return s


@pytest.mark.parametrize("line", [
    "I reveal my true from as a divine being",          # the reported line, typo and all
    "I reveal my true form as a divine being.",
    "I shed my mortal guise and rise.",
    "I transform into a dragon and roar at them.",
    "Knowing what I am, I let go of the mask of being human and show my true nature to the crowd.",
    "I am no mere mortal, and I let them see it.",
    "As a god such as myself, I make the crates kneel.",
])
def test_declaring_what_you_are_is_handed_back_before_any_model(plain, line):
    hint = judgement.claims_a_nature(line, plain)
    assert hint, line
    assert "nothing on your sheet" in hint and "no roll" in hint
    assert "“" in hint, "their own words are quoted back"


@pytest.mark.parametrize("line", [
    'I tell the guard, "I am a divine being and you will kneel."',   # a boast is theirs to tell
    "I ask him whether he believes I am a god?",                     # a question is asking
    "I reveal the letter to the crier.",                             # revealing a thing
    "I take the true road north.",                                   # "true" is not a form
    "I punch him in the face.",
    "I turn into the alley.",
])
def test_speech_questions_and_ordinary_lines_pass(plain, line):
    assert judgement.claims_a_nature(line, plain) == ""


def test_a_sheet_that_grants_a_form_lets_the_line_through(shapeshifter):
    """A druid's Wild Shape is an ability being used, and `inject_ability` routes it;
    the door is the complement of that door, never a second opinion on it."""
    assert judgement.claims_a_nature("I transform into a bear.", shapeshifter) == ""
    assert judgement.claims_a_nature("I reveal my true form.", shapeshifter) == ""


def test_the_door_sits_in_the_say_handler_before_the_model():
    """Where it lives matters: after the fiat check, before any model call."""
    import inspect

    from play import views

    src = inspect.getsource(views.say)
    assert "claims_a_nature" in src
    assert src.index("player_input.check(text)") < src.index("claims_a_nature") \
        < src.index("agent.plan_turn(")
