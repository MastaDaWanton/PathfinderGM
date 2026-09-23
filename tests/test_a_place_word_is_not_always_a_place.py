"""The absent-place rule reads a PLACE, not every "the <word>" in the vocabulary.

Measured 2026-09-23, the day after the rule shipped in `stands_elsewhere`, with the party
at the market of a village whose places are the well, the market, the guildhall, the
lane, the green and the way in. Each of these was a weight-3 "stands-elsewhere" finding,
and each sent the beat to a repair call telling the rewrite there is no such place here:

    "You stand at the edge of the market, watching the traders."   -> the edge
    "Drenn watches the approach of the carter with a frown."       -> the approach
    "She scratches the bridge of her nose and shrugs."             -> the bridge
    "The keep of the coin is yours, he says."                      -> the keep
    "The talk gets to the heart of it quickly."                    -> the heart of it
    "You look for the way in."  (in a town with a gate)            -> the way in

Two causes. The wild reaches — "the edge", "the approach", "the heart of it", "the high
ground" — were in the absent list although they are names only at a wild site, and plain
English everywhere else. And the rule read any "the <word>" at all, so an adjective ("the
green cloak") and a genitive ("the edge of") both counted as a place being named.
"""
from __future__ import annotations

import pytest

from gm import narration

VILLAGE = ("the well", "the market", "the guildhall", "the lane", "the green",
           "the way in", "the upper floor of the guildhall")


def _found(text, here="the market", places=VILLAGE):
    return narration.stands_elsewhere(text, here=here, places=places)


class TestOrdinaryEnglishIsNotAPlace:
    @pytest.mark.parametrize("sentence", [
        "You stand at the edge of the market, watching the traders.",
        "Drenn watches the approach of the carter with a frown.",
        "She scratches the bridge of her nose and shrugs.",
        "The keep of the coin is yours, he says.",
        "The talk gets to the heart of it quickly.",
        "You look for the way in and find it.",
        "He pulls the green cloak tighter and says nothing.",
        "You take the high ground in the argument.",
    ])
    def test_the_measured_false_positives(self, sentence):
        assert _found(sentence) == [], sentence

    def test_the_way_in_is_how_anybody_asks_where_the_door_is(self):
        """In a town that has a gate and no place called "the way in"."""
        assert _found("You look for the way in.", places=("the gate", "the market")) == []

    def test_the_wild_reaches_are_names_only_at_a_wild_site(self):
        assert "edge" not in narration._place_words(wild=False)
        assert "edge" in narration._place_words()
        # At a wild site the caller's own list supplies them, and a claim to be at a
        # reach the party is not at is still judged.
        got = _found("You are at the edge now.", here="the heart of it",
                     places=("the approach", "the heart of it", "the edge"))
        assert got and got[0][0] == "the edge"


class TestAPlaceIsStillAPlace:
    """The reported inventions are still caught: the fix narrowed, it did not blunt."""

    @pytest.mark.parametrize("sentence", [
        "The tavern is a squat, sturdy building of timber and stone.",
        "We should find a place to sit inside the tavern, my legs are weary.",
        "The tavern's door swings open.",
        "Drenn leads you toward the inn.",
        "You are at the gate, where wagons pass through.",
    ])
    def test_a_place_this_village_does_not_have(self, sentence):
        got = _found(sentence)
        assert got, sentence
        assert got[0][0] in ("the tavern", "the inn", "the gate"), got


class TestACompoundIsStillTheThingItIsMadeOf:
    """"The tavern door" is a tavern. Only a word that is also an ordinary modifier in
    English — green, tower, cave — is read by what follows it, and each of those is named
    with the compound it was measured in."""

    def test_the_tavern_door_is_a_tavern(self):
        assert _found("Drenn leads you toward the tavern door.")

    def test_the_market_square_is_a_market(self):
        assert _found("You push through the market square.", here="the well",
                      places=("the well",))

    def test_a_tower_shield_is_not_a_tower(self):
        assert _found("She raises the tower shield.", places=("the well",)) == []

    def test_a_cave_bear_is_not_a_cave(self):
        assert _found("The cave bear turns.", places=("the well",)) == []

    def test_but_the_tower_itself_still_is(self):
        assert _found("The tower is dark tonight.", places=("the well",))
