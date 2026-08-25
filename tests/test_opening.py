"""The first thing the player reads, and the rule about first-level hit points.

The old opening was one hard-coded sentence — a shut guild yard, after dark, in a town
named by a literal entity id out of the shipped fixture. It told a wizard, a paladin
and a Blood Bender the same thing, gave them nothing to do and nobody to do it with,
and any world that was not Pangrella began nowhere at all.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from play import opening
from rules import creation


# --- first level takes the maximum ---------------------------------------------------

def test_first_level_takes_the_whole_die_and_never_rolls_it():
    """"2d8 is a roll that should be made to get my actual health (2d8 +Con) however
    lvl 1 should get Max HP (16 + Con)". First level is the kind rule in 1e: you do
    not roll, you take the top of the die. For 2d8 the top is 16."""
    assert creation.max_hit_die("2d8") == 16
    built, problems = creation.build({
        "name": "Full Health", "race": "half-orc", "bonus_ability": "con",
        "class": "blood bending",
        "pronouns": "she/her",
        "abilities": {"str": 10, "dex": 10, "con": 14, "int": 10, "wis": 10, "cha": 10},
        "skills": [], "feats": [], "paths": ["coagulator"],
    })
    assert problems == [], problems
    # Con 14 +2 half-orc = 16, a +3 modifier. 16 from the dice, and no dice were rolled.
    assert built["sheet"]["abilities"]["con"] == 16
    assert built["sheet"]["hp"] == 16 + 3 == built["sheet"]["hp_max"]


@pytest.mark.parametrize("cid,die", [
    ("barbarian", 12), ("fighter", 10), ("rogue", 8), ("wizard", 6),
])
def test_the_core_classes_take_their_own_die_whole(cid, die):
    built, problems = creation.build({
        "name": f"Max {cid}", "race": "human", "bonus_ability": "str", "class": cid, "pronouns": "she/her",
        "abilities": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        "skills": [], "feats": [],
        "spellbook": creation.starter_spells(cid),
    })
    assert problems == []
    assert built["sheet"]["hp"] == die       # Con 10 is no modifier either way


# --- the opening reads off any world -------------------------------------------------

@dataclass
class FakeEntity:
    id: str
    kind: str
    name: str
    summary: str = ""
    scale: str | None = None
    facts: dict = field(default_factory=dict)
    sections: list = field(default_factory=list)

    def fact(self, key, default=""):
        return self.facts.get(key, default)


@dataclass
class FakeWorld:
    name: str
    premise: dict
    entities: dict

    def get(self, eid):
        return self.entities.get(eid)


def a_world(**over):
    town = FakeEntity("t1", "CITY", "Averthorn", scale="town", facts={
        "Architecture": "Turf roofs and low stone walls",
        "Social Classes": "Reeve, freeholders, and bonded labour",
        "Daily Norms": "Market on the eighth day",
        "Tension": "The reeve's tithe is two years unpaid",
    })
    world = FakeWorld(name="Elsewhere",
                      premise={"setting": "A drowned coast", "tone": "Bleak"},
                      entities={"t1": town})
    for k, v in over.items():
        setattr(world, k, v)
    return world, town


def test_nothing_in_the_opening_names_the_shipped_fixture():
    """The whole table is common nouns. A proper noun here would be this app writing
    a place into somebody's world that World Bible never wrote."""
    import re

    for s in opening.SITUATIONS:
        for text in (s.when, s.where, s.doing, s.who):
            stray = re.findall(r"(?<![.!?] )(?<!^)\b[A-Z][a-z]{2,}", text)
            assert not stray, (text, stray)


def test_every_situation_starts_somewhere_alive():
    """"Puts the player somewhere alive" — every opening is among people, in daylight
    or lamplight, doing something ordinary. None of them is a locked door at midnight,
    which is what the old one was for everybody."""
    for s in opening.SITUATIONS:
        assert s.who, s
        assert "night" not in s.when.lower(), s
        assert s.doing.startswith("You "), s


def test_the_starting_place_is_found_not_named():
    world, town = a_world()
    assert opening.starting_place(world) is town


def test_the_best_described_settlement_wins():
    """Ranking by scale started the game in whichever hamlet sorted first, which was
    reliably the place the export had nothing to say about."""
    world, rich = a_world()
    bare = FakeEntity("t2", "CITY", "Aaronsholt", scale="hamlet")
    world.entities["t2"] = bare
    assert opening.starting_place(world) is rich


def test_a_world_with_no_settlements_still_starts_somewhere():
    world, _ = a_world()
    world.entities = {"c1": FakeEntity("c1", "CONTINENT", "The Long Shelf")}
    assert opening.starting_place(world).name == "The Long Shelf"


def test_a_world_describing_almost_nothing_still_opens():
    """Shorter, never broken. A world written by a different run of World Bible will
    not carry the same fact names, and every lookup here may legitimately miss."""
    world = FakeWorld(name="Sparse", premise={}, entities={})
    assert opening.what_you_know(world, None) == ""
    assert opening.starting_place(world) is None


def test_writing_instructions_are_not_things_the_character_knows():
    """The shipped export carries `tone: Evocative`, and it turned up in the opening
    as something everybody here takes for granted."""
    world, town = a_world()
    known = opening.what_you_know(world, town)
    assert "Bleak" not in known
    assert "A drowned coast" in known


def test_the_worlds_own_names_are_never_restyled():
    """`_clause` lower-cased its first letter to make the litany read better, and
    turned "Khy'vyr-centric clans" into "khy'vyr-centric clans" — the app quietly
    respelling a people that every other page spells correctly."""
    assert opening._clause("Khy'vyr-centric clans.") == "Khy'vyr-centric clans"


def test_the_roll_is_stable_for_a_game_and_varies_between_games():
    """Written into the transcript once, so it must not change under the player on a
    restart — `hash()` is salted per process and would have done exactly that."""
    assert opening.roll("alpha") == opening.roll("alpha")
    assert len({opening.roll(f"game-{n}") for n in range(40)}) > 1


def test_the_opening_says_all_four_things():
    """The ask: where I am in the world as my character knows it, where I am
    physically, who I am, and what I am currently doing."""
    world, town = a_world()

    @dataclass
    class FakePC:
        name: str = "Averil Stane"
        char_class: str = "ranger"

    @dataclass
    class FakeScene:
        def pc(self):
            return FakePC()

    class FakeCampaign:
        id, seed = "four-beats", None
        scene = FakeScene()

    game = FakeCampaign()
    game.world, game.location = world, town
    text = opening.compose(game, "a stranger here")
    assert "A drowned coast" in text                       # the world, as known
    assert "Averthorn" in text and "Turf roofs" in text     # where, physically
    assert "Averil Stane" in text and "a ranger" in text    # who
    assert "close enough to speak to" in text              # what, and someone to do it with
    assert text.rstrip().endswith("What do you do?")
    assert len(text) > 400, "the ask was for a larger opening than one sentence"
