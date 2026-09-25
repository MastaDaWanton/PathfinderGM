"""Friendly prose does not open a fight.

Measured 2026-09-25, by probe against `judgement.attacked_by`: every one of these read
as a blow struck at the player — "The barmaid rushes over to you with a tankard", "Old
Harl grabs your hand and shakes it warmly", "The merchant throws a wink at you", "cuts
you a slice of cheese", "charges you two silver for it", "slams a mug down in front of
you" (six of six). `_STRIKES_AT_YOU` took any of 30 verbs followed anywhere in the
sentence by "you" or "your", and `Engine.struck_first` asked nobody's attitude before it
opened the encounter and rolled the barmaid's attack on the player.

Two layers now, each enough on its own for the cases it owns:
- the detector: a verb that is a blow in itself (lunges, stabs, punches) still needs
  only the player in its sentence; a verb that is usually not (rushes, grabs, cuts,
  charges, throws, slams) needs a weapon in the sentence or a blow aimed at the player —
  "at you", "your throat" — and a thrown wink is not a thrown knife;
- the engine: somebody friendly or better, or travelling with the player, does not
  strike first on the prose's word.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


@pytest.fixture
def tavern():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    for name in ("barmaid", "Old Harl", "merchant", "man in the leather apron"):
        s.add(instantiate("guildhand", scene=s, name=name), zone="near")
    return s


def _ref(scene, name):
    return next(r for r, a in scene.actors.items() if a.name == name)


KINDNESSES = [
    "The barmaid rushes over to you with a tankard.",
    "Old Harl grabs your hand and shakes it warmly.",
    "The merchant throws a wink at you.",
    "The merchant cuts you a slice of cheese.",
    "The merchant charges you two silver for it.",
    "The barmaid slams a mug down in front of you.",
    "The barmaid strikes up a conversation with you about the harvest.",
    "Old Harl swings the door open for you.",
    "The merchant drives a hard bargain with you.",
    "The barmaid rushes to your side with a cloth for the spill.",
    "Old Harl grabs your arm to steady you on the step.",
    "The merchant throws you a grateful look.",
]


@pytest.mark.parametrize("beat", KINDNESSES)
def test_a_kindness_is_not_a_blow(tavern, beat):
    assert judgement.attacked_by(tavern, beat) == [], beat


BLOWS = [
    ("The man in the leather apron lunges at you with the blade.", "man in the leather apron"),
    ("The barmaid rushes at you, a knife low in her fist.", "barmaid"),
    ("Old Harl grabs your throat and squeezes.", "Old Harl"),
    ("The merchant throws a bottle at your head.", "merchant"),
    ("The merchant charges you, cudgel raised.", "merchant"),
    ("The barmaid cuts at you with a paring knife.", "barmaid"),
    ("The man in the leather apron punches you in the jaw.", "man in the leather apron"),
    ("The man in the leather apron slams his fist into your ribs.", "man in the leather apron"),
]


@pytest.mark.parametrize("beat,who", BLOWS)
def test_a_blow_still_opens_the_fight(tavern, beat, who):
    assert [r for r, _ in judgement.attacked_by(tavern, beat)] == [_ref(tavern, who)], beat


def test_a_friend_does_not_strike_first_on_the_prose_word(tavern):
    """Even when the sentence is a blow in every word, a friendly barmaid's attack is
    the prose's invention: her attitude would have to change first, and that is a fact
    the engine holds, not one a regex reads off a beat."""
    from rules import states

    ref = _ref(tavern, "barmaid")
    tavern.actors[ref].add_condition("friendly", source="test")
    assert states.attitude_of(tavern.actors[ref]) == "friendly"
    engine = Engine(tavern, Dice(seed=3))
    assert engine.struck_first(ref) == []
    assert not tavern.in_encounter


def test_an_indifferent_stranger_still_can(tavern):
    ref = _ref(tavern, "man in the leather apron")
    engine = Engine(tavern, Dice(seed=3))
    outs = engine.struck_first(ref)
    assert tavern.in_encounter and outs
