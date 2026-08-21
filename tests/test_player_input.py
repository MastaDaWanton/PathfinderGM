"""What the player is entitled to say.

The player controls one character; the GM controls the world. Getting this wrong is not
a detail — it ran through the app for several commits. A worked example in the GM's
prompt used the invalid shape, and `gm/judgement.py` read the enemy count out of the
player's sentence, so the app taught the mistake and then honoured it.
"""
from __future__ import annotations

import pytest

from play import player_input


@pytest.mark.parametrize("text", [
    "Two guild bravos come round the corner. I turn and fight.",
    "A watchman appears at the end of the alley.",
    "The guildhand falls asleep at his post.",
    "The gate swings open and three guards rush out.",
    "His sword drops from his hand.",
])
def test_declaring_what_the_world_does_is_handed_back(text):
    """This is the GM's half of the table. The player does not get to say who is there
    or what they do."""
    v = player_input.check(text)
    assert not v.ok
    assert v.offending
    assert "GM" in v.hint


@pytest.mark.parametrize("text", [
    "I turn and fight.",
    "I put my back to the wall and draw.",
    "I wait for the lamp to swing away, then go over the wall.",
    "I ask the guildhand who really pays for the windcatchers.",
    "I have had enough of his lies. I draw my rapier and attack him.",
    "I sweep his legs out from under him.",
    "I spin round and go for whoever is behind me.",
    "I keep my back to the wall and watch the gate.",
])
def test_saying_what_the_character_does_is_a_turn(text):
    assert player_input.check(text).ok


@pytest.mark.parametrize("text", [
    "What does the yard look like?",
    "Is anyone else in here?",
    "Who pays for the windcatchers?",
])
def test_asking_is_not_declaring(text):
    """A question hands authority to the GM rather than taking it."""
    assert player_input.check(text).ok


def test_the_players_own_dialogue_is_theirs():
    """Words the character speaks are the player's to write, whoever they are about."""
    assert player_input.check('I tell him, "The guild pays for nothing."').ok


def test_the_hint_shows_which_part_was_wrong():
    """The turn is not consumed and the text is not lost — the player is told which half
    was theirs to declare so they can rewrite it."""
    v = player_input.check("Two guild bravos come round the corner. I turn and fight.")
    assert "Two guild bravos come round the corner" in v.offending
    assert "I turn and fight" not in v.offending


def test_the_gms_own_example_obeys_the_rule():
    """The example that taught the wrong shape lived in the prompt for several commits.
    Every player line the GM is shown must be one a player could legitimately type."""
    from gm import prompts

    for example in prompts.EXAMPLES:
        assert player_input.check(example["player"]).ok, example["player"]
