"""A name the page gives a person is the name the panel shows.

Reported 2026-09-24 with the panel on screen: the beat began "The man—Korgath Varn—takes
a slow pull of his ale", the panel's IN THE SCENE read "man c8 · Bystander", and the
player: *"I am supposedly speaking with korgath Varn but he is not scene or Man did not
update to Korgath."*

Two gaps, both on the save. `introductions` reads names GIVEN inside speech and skips
the narrator's own sentence about somebody on purpose, so an apposition was read by
nothing. And c8 carried a world pool name, "Kael Sorek", behind the descriptor — so had
the man SAID "Korgath Varn", `settle_introductions` would have swapped it for the pool's
name, contradicting the beat two turns earlier in which Drenn Ironvale named Korgath
Varn as the man to find. A name the story has established wins, and becomes the one the
world holds.
"""
from __future__ import annotations

from gm import judgement, narration
from rules.bestiary import instantiate
from rules.engine import Scene

BEAT = ("The man—Korgath Varn—takes a slow pull of his ale, the mug letting out a wet "
        "sound as he sets it back down. He watches you over the rim.")


def _scene():
    s = Scene(location_id="t")
    pc = instantiate("guildhand", scene=s, name="Spree")
    pc.kind = "pc"
    s.add(pc)
    man = instantiate("guildhand", scene=s, name="man")
    man.true_name = "Kael Sorek"
    s.add(man)
    s.cast.append({"who": "man", "ref": man.ref, "turn": 16})
    return s, pc, man


class TestTheShape:
    def test_the_reported_sentence(self):
        assert narration.named_in_apposition(BEAT) == [("man", "Korgath Varn")]

    def test_commas_and_named(self):
        assert narration.named_in_apposition(
            "The woman, Marra Tull, looks up from the ledger.") == [("woman", "Marra Tull")]
        assert narration.named_in_apposition(
            "A guard named Osric waves you through.") == [("guard", "Osric")]

    def test_a_place_in_apposition_is_not_a_person(self):
        assert narration.named_in_apposition(
            "You cross the market, Vormoor's heart, at a walk.") == []

    def test_speech_is_not_read_here(self):
        assert narration.named_in_apposition(
            'Drenn says, "the man, Korgath Varn, sits in the back corner."') == []


class TestThePanel:
    def test_the_man_becomes_korgath_varn(self):
        s, pc, man = _scene()
        got = judgement.apply_introductions(s, BEAT, "I ask him to point me the right way")
        assert got == [(man.ref, "Korgath Varn")]
        assert man.name == "Korgath Varn"
        assert man.true_name == "Korgath Varn", "the world holds the story's name now"
        assert s.cast[-1]["who"] == "Korgath Varn"

    def test_somebody_already_carrying_the_name_is_not_taken_twice(self):
        s, pc, man = _scene()
        drenn = instantiate("guildhand", scene=s, name="Korgath Varn")
        s.add(drenn)
        assert judgement.apply_introductions(s, BEAT) == []
        assert man.name == "man"


class TestTheStorysNameWins:
    def test_a_name_the_player_was_told_is_not_swapped_for_the_pools(self):
        beat = "The man shrugs. 'The name's Korgath Varn,' he says. 'You found me.'"
        expected = {"man": "Kael Sorek"}
        swapped, swaps = narration.settle_introductions(beat, expected)
        assert "Kael Sorek" in swapped and swaps, "without the story, the pool's name"
        kept, swaps = narration.settle_introductions(
            beat, expected,
            established="Drenn leans in. 'Korgath Varn,' they say. 'Find him.'")
        assert kept == beat and swaps == []

    def test_and_then_he_is_korgath_varn_to_the_world_as_well(self):
        s, pc, man = _scene()
        beat = "The man shrugs. 'The name's Korgath Varn,' he says. 'You found me.'"
        judgement.apply_introductions(s, beat, "I ask the man his name")
        assert man.name == "Korgath Varn" and man.true_name == "Korgath Varn"
