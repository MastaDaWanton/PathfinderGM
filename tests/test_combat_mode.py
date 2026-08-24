"""A fight is a different job, and gets a different prompt.

Nine hundred characters of cellar-and-weather is right when somebody opens a door and
badly wrong when there is a sap coming at their head: the pace of the prose is the pace of
the fight, and a turn that takes four sentences to reach the threat has already lost it.

Also here: reasoning models. Qwen3 and its tunes emit their working before their answer,
and measured on R4C3R/qwen3-8b-heretic every consequence call came back as a thousand
characters of "Okay, let me break down what's happening here" and never reached the prose.
Call 1 looked fine only because `format=json` forces the model out of that mode.
"""
from __future__ import annotations

import pytest

from gm import narration, prompts
from gm.client import strip_thinking


# --- two modes -----------------------------------------------------------------------

def test_a_fight_is_shown_the_combat_examples():
    msgs = prompts.call_one_messages("BRIEF", [], "I swing at him", in_combat=True)
    shown = " ".join(m["content"] for m in msgs)
    assert prompts.COMBAT_EXAMPLES[0]["reply"]["narration"] in shown


def test_a_fight_is_not_shown_the_long_ones():
    """They replace rather than extend. Nine hundred characters of scene-setting in front
    of a model being asked for three sentences is demonstration volume pulling the wrong
    way."""
    msgs = prompts.call_one_messages("BRIEF", [], "I swing at him", in_combat=True)
    shown = " ".join(m["content"] for m in msgs)
    assert prompts.EXAMPLES[0]["reply"]["narration"] not in shown


def test_out_of_a_fight_is_shown_the_long_ones():
    msgs = prompts.call_one_messages("BRIEF", [], "I open the box")
    shown = " ".join(m["content"] for m in msgs)
    assert prompts.fill_enemy(prompts.EXAMPLES[0]["reply"]["narration"], None) in shown
    assert prompts.COMBAT_EXAMPLES[0]["reply"]["narration"] not in shown


def test_the_combat_formula_reaches_the_model():
    msgs = prompts.call_one_messages("BRIEF", [], "I swing", in_combat=True)
    assert "LANDED" in msgs[0]["content"]
    assert "OPENING" in msgs[0]["content"]


def test_the_scene_formulas_reach_the_model():
    assert "ARRIVING SOMEWHERE" in prompts.BRIEFING
    assert "A HAZARD GOING WRONG" in prompts.BRIEFING


def test_combat_examples_are_short_and_scene_examples_are_not():
    """The length *is* the demonstration."""
    combat = [len(e["reply"]["narration"]) for e in prompts.COMBAT_EXAMPLES]
    scene = [len(e["reply"]["narration"]) for e in prompts.EXAMPLES]
    assert max(combat) < min(scene)
    assert sum(combat) / len(combat) < 400
    assert sum(scene) / len(scene) > 450


def test_there_are_enough_scene_examples_to_generalise_from():
    """Eight examples covering eight situations gives every situation exactly one
    template, and a model inclined to copy has nothing else to do with it. Measured on
    qwen3-8b-heretic: three turns in five came back as whole example paragraphs. More of
    them, further apart, took that to one in three."""
    assert len(prompts.EXAMPLES) >= 12
    assert len(prompts.COMBAT_EXAMPLES) >= 5


def test_every_combat_example_offers_suggestions_too():
    for ex in prompts.COMBAT_EXAMPLES:
        assert 2 <= len(ex["reply"]["suggestions"]) <= 3


def test_every_combat_example_hands_the_turn_back():
    for ex in prompts.COMBAT_EXAMPLES:
        assert "?" in ex["reply"]["narration"]


# --- the floors differ ------------------------------------------------------------------

def test_a_combat_turn_may_be_much_shorter_than_a_scene():
    short = prompts.COMBAT_EXAMPLES[1]["reply"]["narration"]
    assert narration.review(short, min_chars=narration.MIN_SCENE_CHARS).findings
    assert not narration.review(short, min_chars=narration.MIN_COMBAT_CHARS,
                                max_chars=narration.MAX_COMBAT_CHARS).findings


def test_a_fight_that_stops_to_describe_the_weather_is_caught():
    long_one = prompts.EXAMPLES[0]["reply"]["narration"]
    r = narration.review(long_one, min_chars=narration.MIN_COMBAT_CHARS,
                         max_chars=narration.MAX_COMBAT_CHARS)
    assert [f.kind for f in r.findings] == ["too-long-for-a-fight"]


def test_there_is_no_ceiling_outside_a_fight():
    long_one = prompts.EXAMPLES[0]["reply"]["narration"]
    assert not narration.review(long_one, min_chars=narration.MIN_SCENE_CHARS).findings


# --- reasoning models -------------------------------------------------------------------

def test_a_closed_think_block_is_removed():
    assert strip_thinking("<think>working</think>The answer.") == "The answer."


def test_an_unterminated_block_is_thinking_all_the_way_to_the_end():
    """Thinking that ran out of budget mid-thought, which is exactly what it was."""
    assert strip_thinking("<think>ran out of budget partway") == ""


def test_ordinary_prose_is_untouched():
    assert strip_thinking("Just prose.") == "Just prose."


@pytest.mark.parametrize("tag", ["think", "thinking", "reasoning", "THINK"])
def test_the_shapes_models_actually_use(tag):
    assert strip_thinking(f"<{tag}>x</{tag}>Kept.") == "Kept."


def test_the_regex_survived_being_written():
    """The first version of these patterns went in through a shell heredoc and the
    backreference arrived as a literal 0x01 byte: the closed-block pattern never matched,
    the open-block pattern ate the whole reply, and every answer came back empty.
    CLAUDE.md warns about exactly this."""
    import pathlib

    src = pathlib.Path("gm/client.py").read_text(encoding="utf-8")
    assert not [c for c in src if ord(c) < 32 and c not in "\n\r\t"]
