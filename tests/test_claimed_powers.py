"""A power the sheet never granted cannot be used, whatever the player calls it.

Reported from the table 2026-09-17, with a screenshot:

    "I use my godly powers to will the missing transport of refined salt to appear
     before me, since a god such as myself could easily do this at any point, instantly"

The narrator wrote it happening. A rift tore open in the market, the cart came through
with its wheels still spinning, the shockwave put merchants on their knees, and the salt
was simply *there*. Nothing had to be refused, because nothing mechanical was ever
proposed — the turn produced narration, and narration is not something the engine gets
a vote on.

**This is the 2026-09-09 psychic report one category over**, and it got through for a
reason worth recording rather than just patching. `gm/judgement.py`'s faculty pattern
listed the adjectives it knew — psychic, psionic, telepathic, mental, mind — so a door
built for precisely this sentence let "godly" walk past it. An adjective list is a
denylist, and a denylist for "ways of claiming a power you were never granted" has no
end: godly, divine, cosmic, eldritch, reality-warping, and whatever gets typed next.

So the gate stopped reading the adjective. What fires is the shape — reaching for a
faculty — and the character sheet decides, which is the rule the whole file already runs
on. `refuse_unnamed_power` stands down whenever an intent names an ability the character
really has, so the cases below are about a claim with nothing behind it.

`tests/test_psychic_powers.py` covers the mind-reaching half and is unchanged.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules.engine import Scene
from rules.sheet import load_pc


@pytest.fixture
def scene():
    """Kesst, a level 1 rogue, who is not a god and has no godly powers."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s


REPORTED = ("I use my godly powers to will the missing transport of refined salt to "
            "appear before me, since a god such as myself could easily do this at any "
            "point, instantly")


def test_the_reported_sentence_is_refused_rather_than_narrated(scene):
    """The turn from the screenshot, with the intents that made it: narration, and a
    spawn that put a cart in the market. The spawn is what made the salt real."""
    out = judgement.refuse_unnamed_power(
        [{"op": "narrate_only", "because": "the god wills the salt into being"},
         {"op": "spawn", "template": "cart", "because": "the transport arrives"}],
        REPORTED, scene)
    ops = [r["op"] for r in out]
    assert "spawn" not in ops, "the cart was still created"
    assert "use_ability" in ops


def test_the_refusal_quotes_the_players_own_words(scene):
    """The engine's door prints "no ability called <X>; they can use: …", and the whole
    value of that sentence is that it quotes the claim. Told there is no ability called
    "psychic powers", a player who wrote "godly powers" has been answered about somebody
    else's turn."""
    out = judgement.refuse_unnamed_power([{"op": "narrate_only", "because": "x"}],
                                         REPORTED, scene)
    named = next(r for r in out if r["op"] == "use_ability")
    assert named["params"]["ability"] == "godly powers"


@pytest.mark.parametrize("said", [
    # The reported phrasing, and the ones a denylist would have had to be told about
    # one at a time.
    "I use my godly powers to make the salt appear",
    "I use my divine powers to open the gate",
    "I call upon my cosmic power and remake the square",
    "I unleash my reality-warping abilities on the crowd",
    "I channel my divine might to heal the wounded",
    "I exert my holy will over the crowd",
    "I wield my eldritch magic against the watch",
    "I draw upon my immortal strength and lift the cart",
    # Claiming to BE it, which is the same declaration with the faculty implied.
    "I am a god, so the gate opens",
    "As a god I simply take the salt",
])
def test_a_faculty_the_sheet_cannot_back_is_refused(said, scene):
    out = judgement.refuse_unnamed_power([{"op": "narrate_only", "because": "x"}],
                                         said, scene)
    assert any(r["op"] == "use_ability" for r in out), said


@pytest.mark.parametrize("said", [
    # Ordinary turns. The nouns in the first two are exactly why `might`, `strength` and
    # `energy` are not general faculty words: a pattern that refused these would be
    # worse than the one it was fixing.
    "I use my last strength to push the door",
    "I channel my remaining energy into running",
    "I draw my rapier and step back",
    "I use my rope to climb the wall",
    "I use my lockpicks on the chest",
    "I search the wagon for the manifest",
    # A question asks rather than declares, and the door checks for one.
    "Could I use my godly powers here?",
])
def test_an_ordinary_turn_is_left_alone(said, scene):
    raw = [{"op": "narrate_only", "because": "x"}]
    assert judgement.refuse_unnamed_power(list(raw), said, scene) == raw, said


def test_a_boast_is_the_characters_to_make(scene):
    """Speech is redacted before any of this runs. A character is entitled to lie about
    what they are — measured on the corpus that taught this file the difference between
    saying a thing and doing it, where `I tell the guard "put down your sword, I do not
    want to fight"` started a fight."""
    said = 'I tell the guard "I am a god, and my divine powers will crush you"'
    raw = [{"op": "narrate_only", "because": "x"}]
    assert judgement.refuse_unnamed_power(list(raw), said, scene) == raw


def test_a_power_the_character_really_has_still_stands(scene):
    """The complement of `inject_ability`, never a second opinion on it. If an intent
    names something on the sheet, this door does not open — otherwise broadening the
    detector would start refusing clerics for channelling."""
    from rules import leveling

    pc = scene.pc()
    real = None
    for cand in ("Sneak Attack", "sneak attack"):
        _path, found, _fx = leveling.find_ability(pc, cand)
        if found:
            real = cand
            break
    if real is None:
        pytest.skip("the fixture PC has no named ability to test the stand-down with")
    raw = [{"op": "use_ability", "actor": pc.ref, "because": "y",
            "params": {"ability": real}}]
    assert judgement.refuse_unnamed_power(list(raw), "I use my divine powers", scene) == raw


# --- the bypass the reporter found ---------------------------------------------------
#
# Asked the same day, about the fix above: "will it work if I say I channel my last
# energy to disintegrate the enemy, or I use my rope to explode the enemy to bits?"
#
# It did not. Both name something mundane, so no faculty door opens. Two different
# answers came out of testing them, and only one was a defect:
#
#   * The *numbers* were already safe. `rules/intents.py` refuses damage with no
#     document behind it — "name what does it: use_item, cast, use_ability" — so the
#     rope explodes nobody. `condition: dead` was accepted and did nothing.
#   * The *creation* was not. "I use my rope to make a wagon of salt appear" left the
#     model's `spawn` untouched and the cart arrived, which is the reported bug with one
#     word changed.

def test_the_rope_bypass_is_handed_back_before_any_model_call(said=None):
    """The reported sentence with the supernatural claim taken out of it.

    Handed back by `play/player_input.py` rather than repaired downstream: there is no
    roll that decides whether a wagon exists, so there is nothing for the engine to
    adjudicate and no reason to spend a model call finding that out."""
    from play import player_input

    v = player_input.check("I use my rope to make a wagon of salt appear before me")
    assert not v.ok
    assert "GM's to decide" in v.hint


@pytest.mark.parametrize("said", [
    "I use my rope to make a wagon of salt appear before me",
    "I make a chest of gold appear",
    "I bring the dragon into existence",
    "I will the gate to appear out of thin air",
    "I have the guard appear at the gate",
])
def test_fiat_creation_is_the_gms_whatever_instrument_is_named(said):
    from play import player_input

    assert not player_input.check(said).ok, said


@pytest.mark.parametrize("said", [
    # The determiner requirement is what keeps this one out: the verb has to be followed
    # by the thing, not by the appearing.
    "I will appear calm before the crier",
    "I make my way to the market",
    "I wait for the merchant to appear",
    "I watch the sun appear over the roofs",
    # Spell vocabulary is deliberately not the text layer's business — the sheet decides.
    "I summon a celestial dog",
    # A boast is the character's to make.
    'I tell the crier "I will make a dragon appear"',
])
def test_the_fiat_check_leaves_ordinary_turns_alone(said):
    from play import player_input

    assert player_input.check(said).ok, said


def test_a_summoning_nothing_grants_puts_nothing_on_the_board(scene):
    """`summon` reaches the sheet rather than the handback, so this is where a rogue's
    celestial dog is refused — and where a summoner's is not."""
    out = judgement.refuse_declared_creation(
        [{"op": "narrate_only", "because": "it arrives"},
         {"op": "spawn", "template": "dog", "because": "a celestial dog appears"},
         {"op": "give", "item": "salt", "count": 50, "because": "the salt"}],
        "I summon a celestial dog", scene)
    ops = [r["op"] for r in out]
    assert "spawn" not in ops and "give" not in ops
    assert "use_ability" in ops


def test_a_real_casters_summoning_is_untouched(scene):
    """The whole reason `summon` is not handed back at the text layer. A `cast` stands
    the door down completely, and the spell's own spawn survives with it."""
    cast = [{"op": "cast", "actor": "pc", "because": "x",
             "params": {"spell": "summon-monster-i"}},
            {"op": "spawn", "template": "dog", "because": "the spell's creature"}]
    assert judgement.refuse_declared_creation(
        [dict(c) for c in cast], "I summon a celestial dog", scene) == cast


def test_an_ordinary_turn_keeps_the_gms_own_spawn(scene):
    """`spawn` is how the GM reads opposition into a scene and must survive a turn that
    never declared anything. Refusing it wholesale would be a worse bug than the one
    this closes."""
    raw = [{"op": "narrate_only", "because": "x"},
           {"op": "spawn", "template": "thug", "because": "two bravos step out"}]
    assert judgement.refuse_declared_creation(
        [dict(r) for r in raw], "I draw my rapier and step back", scene) == raw
