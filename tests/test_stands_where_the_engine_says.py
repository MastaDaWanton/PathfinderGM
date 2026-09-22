"""The prose stands where the engine says, or it is repaired.

Two items of the 2026-09-19/21 play-test, and they turn out to be one rule.

**Item 45**, reported with the map open: *"i am at a gate with wagons passing through and
a wagon off to the side this map is completely wrong."* The map was right. The engine held
the party at **the well** and drew it faithfully — a 5x5 place World Bible authored, "a
wellhead, and the ground worn round it". The prose was describing a gate, and Vormoor's
places are the well, the market, the guildhall, the lane, the green and the upper floor of
the guildhall. **There is no gate.**

And the narrator was told. `scene_brief` states it twice over — "The party is at the well.
Not anywhere else in Vormoor; they are there now", then "THE PLACES HERE (the only ones
that exist)". Nothing checked whether the prose obeyed.

**Item 38**, found live during group 14's own check: a `travel` was refused with a reason
— *"the upper floor of the guildhall is not reached from here: the stairs to it are inside
the guildhall"* — and the beat then described climbing those stairs and reaching the
landing. The party stayed where it was.

Same defect from two ends: a beat set where the party is not. The check is against engine
state (`Scene.at` and the places that exist), never against a list of forbidden words —
the vocabulary is used only to recognise that a phrase IS a place claim.
"""
from __future__ import annotations

import pytest

from gm import narration

PLACES = ("the well", "the market", "the guildhall", "the lane", "the green",
          "the upper floor of the guildhall")


def _found(text, here="the well", places=PLACES):
    return narration.stands_elsewhere(text, here=here, places=places)


class TestAPlaceThatDoesNotExist:
    def test_the_measured_sentence(self):
        """Item 45, in the shape it arrived."""
        got = _found("You are at the gate, where wagons pass through and a wagon "
                     "stands off to the side.")
        assert got and got[0][0] == "the gate"

    def test_ground_nobody_ventured_into(self):
        """The other half of the vocabulary the brief teaches: a narrator who writes the
        player into sewers nobody went down has invented a place just as surely."""
        assert _found("You find yourself in the sewers, a place of enclosed stone.")

    def test_a_place_that_does_exist_and_is_where_they_are(self):
        assert not _found("The market is loud around you.", here="the market")
        assert not _found("You step into the market and the noise closes over you.",
                          here="the market")


class TestAPlaceTheyDidNotGoTo:
    def test_the_refused_walk(self):
        """Item 38: the travel was refused, and the beat climbed the stairs anyway."""
        got = _found("You climb the stairs and reach the upper floor of the guildhall.",
                     here="the market")
        assert got and got[0][0] == "the upper floor of the guildhall"

    def test_the_longest_name_wins(self):
        """"the upper floor of the guildhall" must not be read as "the guildhall", and
        "the great square" must not be read as "the square"."""
        got = _found("You reach the upper floor of the guildhall.", here="the market")
        assert got[0][0] == "the upper floor of the guildhall"

    def test_a_real_place_they_walked_to_this_turn_is_fine(self):
        assert not _found("You step into the guildhall.", here="the guildhall")


class TestWhatItDoesNotFireOn:
    """A noisy guard is worth less than none — this file's own standard, and the reason
    several of these are deliberate misses."""

    def test_seeing_somewhere_is_not_standing_in_it(self):
        assert not _found("You can see the gate from here.")
        assert not _found("The lane runs off toward the green.")

    def test_somebody_else_going_somewhere_is_not_the_player(self):
        assert not _found("The drover reaches the gate and is waved through.")

    def test_crossing_on_the_way_is_passage_and_not_arrival(self):
        """The route-finder models passage now and the tell names it, so "you cross the
        green toward the well" is true. Flagging it would make this guard noisy."""
        assert not _found("You cross the green toward the well.")

    def test_a_place_being_talked_about_in_speech_is_not_a_claim(self):
        assert not _found('The old man says, "You are at the gate before dawn or you '
                          'are not going at all."')

    def test_scenery_it_cannot_judge_is_left_alone(self):
        """The stated limit: a place the app's own generator could never name is not
        caught, because deciding an unknown noun phrase is a room rather than scenery is
        the word-list trap the player has objected to twice."""
        assert not _found("You are in a work yard, loud with somebody else's trade.")


class TestTheReview:
    def _review(self, text, here="the well"):
        return narration.review(text, here=here, places=PLACES)

    def test_it_is_a_finding_and_a_heavy_one(self):
        r = self._review("You are at the gate, where wagons pass through.")
        found = [f for f in r.findings if f.kind == "stands-elsewhere"]
        assert found and found[0].weight == 3

    def test_the_repair_names_the_real_place_and_the_real_list(self):
        """Detect mechanically, repair with a targeted call — and the call has to carry
        the facts, or the rewrite invents a second wrong place."""
        r = self._review("You are at the gate, where wagons pass through.")
        note = [f for f in r.findings if f.kind == "stands-elsewhere"][0].fix_hint
        assert "the well" in note and "the market" in note

    def test_a_caller_that_cannot_say_where_they_are_judges_nothing(self):
        """Same rule as `fire_context`: a guard that guesses is worse than one that
        abstains, and most callers of `review` are tests with no scene."""
        r = narration.review("You are at the gate, where wagons pass through.")
        assert not [f for f in r.findings if f.kind == "stands-elsewhere"]

    def test_an_ordinary_beat_passes(self):
        r = self._review("The queue shuffles forward. You lower the bucket and the "
                         "rope goes taut in your hands.")
        assert not [f for f in r.findings if f.kind == "stands-elsewhere"]


class TestTheVocabularyIsTheAppsOwn:
    def test_it_is_read_from_the_generator_and_not_typed_here(self):
        """One list, so a place kind added to the generator is covered the day it is
        added — the drift CLAUDE.md names, refused in advance."""
        from rules import places as places_mod

        words = narration._place_words()
        for row in places_mod.SETTLEMENT_PLACES:
            label = str(row[0]).lower().removeprefix("the ")
            if len(label) > 2:
                assert label in words, label
        for kind in places_mod.VENTURES:
            assert kind in words, kind

    @pytest.mark.parametrize("entrance", ["the gate", "the way in", "the docks"])
    def test_every_entrance_is_in_it(self, entrance):
        assert entrance.removeprefix("the ") in narration._place_words()
