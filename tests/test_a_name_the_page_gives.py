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

Who the name in the page is FOR was read by `narration.named_in_apposition` and
`judgement.apply_introductions` until 2026-10-03; it is the beat reader's answer now (its
"names"), taken through `seen_people.name_them`. The shapes the patterns were tested on
are on the bench (tests/beat_reader/gold.py, the "names-" cases).
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


def _named(s, text, ref, name):
    """The beat reader's answer — this name is this person's — through the one door."""
    from play.aftermath import seen_people
    from tests.beat_reader import stub

    reading = stub.read(text, s, names={ref: name})
    return seen_people.name_them(stub.ctx(s, reading, text=text), reading)


def test_the_shapes_are_on_the_bench():
    from tests.beat_reader.gold import CASES

    ids = {c["id"] for c in CASES}
    assert {"names-the-man-korgath-varn", "names-a-place-in-apposition"} <= ids


class TestThePanel:
    def test_the_man_becomes_korgath_varn(self):
        s, pc, man = _scene()
        (row,) = _named(s, BEAT, man.ref, "Korgath Varn")
        assert row["taken"] and man.name == "Korgath Varn"
        assert man.true_name == "Korgath Varn", "the world holds the story's name now"
        assert s.cast[-1]["who"] == "Korgath Varn"

    def test_somebody_already_carrying_the_name_is_not_taken_twice(self):
        s, pc, man = _scene()
        drenn = instantiate("guildhand", scene=s, name="Korgath Varn")
        s.add(drenn)
        (row,) = _named(s, BEAT, man.ref, "Korgath Varn")
        assert not row["taken"] and man.name == "man"


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
        _named(s, beat, man.ref, "Korgath Varn")
        assert man.name == "Korgath Varn" and man.true_name == "Korgath Varn"
