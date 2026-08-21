"""What actually crosses the wire to the browser.

The engine keeps a complete, auditable record of every roll. What the *player* is sent is
a much smaller thing, and the difference is enforced here — a hidden roll that reaches the
page is readable in the page source whether or not anything renders it.
"""
from __future__ import annotations

import json

import pytest

from play.views import _player_visible_entry
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


@pytest.fixture
def played():
    """One turn containing a player roll and a hidden roll, as the log records it."""
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.add(instantiate("guildhand", scene=scene, name="the guildhand"))
    engine = Engine(scene, Dice(seed=1))

    intents = engine.validate([
        {"op": "check", "actor": "pc", "because": "slipping past him",
         "params": {"skill": "stealth",
                    "opposed_by": {"ref": "c1", "skill": "perception"}}},
        {"op": "check", "actor": "c1", "visibility": "hidden",
         "because": "he thinks he heard something",
         "params": {"skill": "acrobatics", "dc": {"band": "tough"}}},
    ])
    engine.run(intents)
    engine.resume(face=14)
    # Shaped exactly as views._log_turn writes it: outcomes, plus the model-facing
    # debris that must not travel.
    return {
        "kind": "turn",
        "intents": [i.as_dict() for i in intents],
        "rejections": ["attempt 1: something the player has no business seeing"],
        "outcomes": list(scene.log),
    }


@pytest.mark.parametrize("tell,expected", [
    # Produced in a live fight, shown raw to the player when the narrator was skipped.
    ("the guildhand on the gate's attack misses Kesst Vayr (5 against AC 12 (flat-footed)).",
     "the guildhand on the gate's attack misses Kesst Vayr."),
    ("Kesst Vayr beats the guildhand on the gate's perception by 6.",
     "Kesst Vayr beats the guildhand on the gate's perception."),
    ("Kesst Vayr trips the thug by 7: the target is knocked prone.",
     "Kesst Vayr trips the thug: the target is knocked prone."),
    ("Kesst Vayr fails the Reflex save by 6.", "Kesst Vayr fails the Reflex save."),
])
def test_a_raw_tell_shown_to_the_player_loses_its_arithmetic(tell, expected):
    """Tells are written for the GM to narrate and carry the maths. When the narrator is
    unavailable the tell is shown raw, and that put an NPC's hidden roll in front of the
    player — the one thing the hidden/player split exists to prevent.
    """
    from play.views import plain_tell

    assert plain_tell(tell) == expected


def test_the_players_own_damage_survives():
    """They rolled it themselves; hiding it would be absurd."""
    from play.views import plain_tell

    assert plain_tell("Kesst Vayr hits the thug for 6 piercing.") == (
        "Kesst Vayr hits the thug for 6 piercing.")


def test_hidden_rolls_do_not_reach_the_browser(played):
    visible = _player_visible_entry(played)
    blob = json.dumps(visible)
    for roll in (r for o in visible["outcomes"] for r in o["rolls"]):
        assert roll["visibility"] == "player"
    assert "hidden" not in blob


def test_the_hidden_checks_very_existence_does_not_reach_the_browser(played):
    """Found in the running app: hidden *rolls* were filtered, but the entry still
    carried the GM's raw intents — so "the guildhand makes an Acrobatics check" was
    sitting in the page source with only its numbers removed.

    An allow-list rebuild leaks nothing you forgot to name; a deny-list leaks exactly
    that.
    """
    blob = json.dumps(_player_visible_entry(played)).lower()
    assert "acrobatics" not in blob
    assert "perception" not in blob


def test_the_model_facing_debris_does_not_reach_the_browser(played):
    """Rejections and attempt transcripts are for the server-side audit log. They are
    full of the model's discarded guesses, which are not part of the fiction."""
    blob = json.dumps(_player_visible_entry(played)).lower()
    assert "no business seeing" not in blob
    assert "rejections" not in blob
    assert "intents" not in blob


def test_the_players_own_roll_survives_with_its_itemised_terms(played):
    """Stripping must not take the thing the app exists to show."""
    visible = _player_visible_entry(played)
    rolls = [r for o in visible["outcomes"] for r in o["rolls"]]
    assert len(rolls) == 1
    assert rolls[0]["label"] == "Stealth check"
    assert {m["source"] for m in rolls[0]["modifiers"]} == {
        "ranks", "class skill", "Dex", "Stealthy",
    }
    assert visible["outcomes"][0]["because"] == "slipping past him"


def test_an_outcome_with_nothing_of_the_players_in_it_is_dropped_entirely(played):
    """The hidden check's tell reaches the player through the narration. It does not
    need a blank line in the roll log announcing that something was rolled."""
    assert len(_player_visible_entry(played)["outcomes"]) == 1
