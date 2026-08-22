"""The two or three things the GM offers the player.

Offered, never enforced. The engine does not read them, the player may type anything at
all, and nothing about the turn depends on them — which is exactly why the parser is
tolerant rather than strict. A model that returns a string instead of a list, or eight
instead of three, or nothing at all, must cost the turn nothing.
"""
from __future__ import annotations

import pytest

from gm.agent import _suggestions
from gm import prompts


def test_the_ordinary_case():
    assert _suggestions({"suggestions": ["Go now", "Wait for him to turn"]}) == \
        ["Go now", "Wait for him to turn"]


def test_at_most_three():
    """A menu of eight is a menu. Two or three is a nudge."""
    got = _suggestions({"suggestions": [f"do thing {n}" for n in range(8)]})
    assert len(got) == 3


def test_a_bare_string_is_taken_as_one_suggestion():
    assert _suggestions({"suggestions": "Go over the wall"}) == ["Go over the wall"]


@pytest.mark.parametrize("raw", [None, {}, 7, {"suggestions": None},
                                 {"suggestions": {}}, {"suggestions": []}])
def test_anything_unusable_is_simply_no_suggestions(raw):
    """The page does not draw the row, and the turn is unaffected."""
    data = raw if isinstance(raw, dict) else {"suggestions": raw}
    assert _suggestions(data) == []


def test_bullets_and_whitespace_are_cleaned_off():
    assert _suggestions({"suggestions": ["  - Go now  ", "* Wait\n  and see"]}) == \
        ["Go now", "Wait and see"]


def test_duplicates_are_dropped():
    assert _suggestions({"suggestions": ["Go now", "Go now", "Wait"]}) == \
        ["Go now", "Wait"]


def test_something_too_long_for_a_button_is_dropped():
    assert _suggestions({"suggestions": ["x" * 200, "Go now"]}) == ["Go now"]


def test_every_example_offers_some():
    """Demonstration, not instruction: if the examples do not do it, the model will not."""
    for example in prompts.EXAMPLES:
        offered = example["reply"].get("suggestions")
        assert offered, f"{example['player']!r} offers none"
        assert 2 <= len(offered) <= 3
        assert all(len(s) <= 120 for s in offered)


def test_the_reply_shape_in_the_briefing_names_the_field():
    """The model is shown the field in the examples and told it in the shape line. If the
    shape line ever stops mentioning it, the examples are doing all the work alone."""
    assert '"suggestions"' in prompts.BRIEFING
