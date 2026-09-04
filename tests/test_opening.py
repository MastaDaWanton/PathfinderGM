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
        for text in (s.when, s.where, s.doing, s.who, s.edge):
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


def _game(world, town, cls: str = "ranger", seed=None):
    @dataclass
    class FakePC:
        name: str = "Averil Stane"
        char_class: str = cls

    @dataclass
    class FakeScene:
        def pc(self):
            return FakePC()

    class FakeCampaign:
        id = "four-beats"
        scene = FakeScene()

    game = FakeCampaign()
    game.world, game.location, game.seed = world, town, seed
    return game


def test_the_opening_says_who_where_and_what_is_going_on():
    """Nelson's overture, on the opening of *Trinity* (*The Craft of Adventure*, 2nd
    ed., §"The Overture"): "Already you know: who you are …; exactly where you are …;
    and what is going on". All three, and the place's own props carrying the setting
    rather than a paragraph of stated facts."""
    world, town = a_world()
    text = opening.compose(_game(world, town), "a stranger here")
    assert "Averthorn" in text                                   # exactly where
    # The fact's own words and its own capitals, joined into English: the export
    # writes "Turf roofs, low stone walls" as a field, and only the last comma
    # becomes a conjunction.
    assert "Turf roofs and low stone walls" in text
    assert "Averil Stane" in text and "a Ranger" in text         # who
    assert "The reeve" not in text, "the strain is the GM's note, not the first screen"
    body = text.split("\n\n")
    assert len(body) == 4, body


def test_something_is_already_happening_when_the_game_picks_up():
    """The player used to arrive beside a man in a doorway with nothing in motion:
    "You are watching a thing being made that you half know how to make. The
    apprentice minding the door is close enough to speak to. What do you do?"

    Dungeon World's rule for a first session (SRD, "First Session") is to "start the
    session with a group of player characters … in a tense situation", and Nelson's
    overture has to carry "what is going on" as well as who and where. Every situation
    now opens on something already moving, and it is never explained: the explanation
    is the GM's private note, and asking is the player's first turn.
    """
    world, town = a_world()
    for s in opening.SITUATIONS:
        assert s.edge, s
        assert s.edge.rstrip().endswith("."), s
    text = opening.compose(_game(world, town), "a stranger here")
    assert "close enough to speak to" not in text
    assert "has stopped to watch." in text


def test_the_question_carries_the_role_the_player_is_playing():
    """Nelson, same essay, on Infocom's *Witness*: it "asks pointedly on the first
    turn" — "What should you, the detective, do now?" — and he raises it under telling
    the player who to be. "What do you do?" is that question with the role removed."""
    world, town = a_world()
    text = opening.compose(_game(world, town), "a stranger here")
    assert text.rstrip().endswith("What should you, the Ranger, do now?")
    # And the word is the one the class document uses for a person of that class.
    blooded = opening.compose(_game(world, town, cls="blood bending"), "a stranger here")
    assert "a Blood Bender" in blooded and "the Blood Bender, do now?" in blooded
    assert "a Blood Bending" not in blooded, "the class name is not a noun for a person"


def test_the_opening_is_striking_and_concise():
    """Nelson: the opening "ought to be striking and concise (not an effort to sit
    through, like the title page of `Beyond Zork')". His model does it in two
    paragraphs and 83 words. Measured across all twelve situations on 2026-09-03 this
    runs 79 to 91 words; the old one ran past 200, most of it the export's premise.

    A ceiling rather than an exact count, because a world with a longer place name or
    a longer architecture fact legitimately costs a few words.
    """
    world, town = a_world()
    counts = []
    for s in opening.SITUATIONS:
        game = _game(world, town)
        text = _with_situation(s, lambda: opening.compose(game, "a stranger here"))
        counts.append(len(text.split()))
    assert max(counts) <= 110, counts
    assert min(counts) >= 60, counts


def _with_situation(situation, fn):
    """Compose against one named situation rather than whichever the seed rolls."""
    original = opening.situation_for
    opening.situation_for = lambda _campaign: situation
    try:
        return fn()
    finally:
        opening.situation_for = original


def test_the_first_screen_is_not_a_list_of_promises():
    """D.G. Jerz, *Exposition in Interactive Fiction*: "Casual details like these are
    often found enriching ordinary prose narratives, but when they appear in the
    opening screen of an IF game, they take on a great deal of prominence" — every
    noun on the first screen reads as a thing the player may touch.

    Measured on the user's own world, 2026-09-03: the opening's first paragraph was
    sixteen comma-separated facts joined by semicolons, read straight out of the
    export's `premise`, which is the set of dials World Bible generated the world
    with — "varying by region" appeared three times and one value carried its own
    typo. Nobody was born knowing that, and none of it could be touched.
    """
    world, town = a_world()
    text = opening.compose(_game(world, town), "a stranger here")
    assert text.count(";") == 0, text
    assert "A drowned coast" not in text, "the premise is the generator's dials"
    assert "What you know" not in text


def test_the_narrator_never_decides_for_the_player():
    """Jerz, same essay, on an opening that says "you realize", "you can't bear" and
    "you decide": "The player doesn't get the chance to respond emotionally to the
    scene, and to decide upon a course of action accordingly." He calls "something
    tells you" a "narrative cop-out". Detected rather than remembered, which is this
    repo's own rule about prompt rules versus mechanical checks."""
    import re

    banned = re.compile(r"you reali[sz]e|you decide|you can't bear|"
                        r"something tells you|you feel that", re.I)
    world, town = a_world()
    for s in opening.SITUATIONS:
        game = _game(world, town)
        text = _with_situation(s, lambda: opening.compose(game, "a stranger here"))
        found = banned.findall(text)
        assert not found, (s.where, found)


def test_the_person_beside_you_is_not_watching_themselves():
    """The edge is about the world and the watcher is about the person, and the first
    cut mixed them: the crier's situation read "The crier has stopped in the middle of
    a notice … The crier working through the notices has stopped to watch." Three of
    the twelve did this. The edge may not name the person it is being watched by."""
    for s in opening.SITUATIONS:
        # The person-word itself: the first real word after "the" — "crier",
        # "foreman", "watchman". Not every long word in the phrase, or "the woman at
        # the bread stall" would forbid an edge about a stall.
        words = [w for w in s.who.lower().split() if w != "the" and len(w) > 3]
        assert words, s.who
        assert words[0] not in s.edge.lower(), (s.who, s.edge)


def test_the_world_is_introduced_from_the_place_not_the_dials():
    """The preface the first cut of this rewrite threw out with the bathwater.

    Reported at the table: "the intro to the world is missing". Deleting the premise
    was right — it is the set of knobs World Bible generated with — but the settlement
    carries what its author actually wrote, and that only ever needed to be a sentence
    instead of a field.

    Each sentence reads its own keys, because the fact has to fit the sentence. The
    first cut shared one list and produced "Vyrakon keeps to merchants, artisans,
    farmers and herders" (a rule that is a list of trades) and "The day here is mixed
    economy with market-driven trade" (a day that is an economy).
    """
    world, town = a_world()
    town.facts["Formal Power"] = "matriarchal clan law"
    town.facts["Daily Norms"] = "morning markets, evening prayers"
    said = opening.the_world_here(town)
    assert said == ("Averthorn keeps to matriarchal clan law. "
                    "The day here is morning markets and evening prayers.")

    # A place that describes its people and not its government still gets a preface,
    # and the clock still names the place, because that preface does not.
    del town.facts["Formal Power"]
    text = opening.compose(_game(world, town), "a stranger here")
    assert "Its people are Reeve, freeholders and bonded labour." in text
    assert "Averthorn" in text, "the one thing the overture may not drop"


def test_an_oxford_comma_does_not_become_two_conjunctions():
    """"merchants, artisans, farmers, and herders" is a field with the conjunction
    already on the last item, and joining it again read "farmers and and herders"."""
    assert opening._listed("merchants, artisans, farmers, and herders") == \
        "merchants, artisans, farmers and herders"
    assert opening._listed("wooden buildings, thatched roofs") == \
        "wooden buildings and thatched roofs"
    assert opening._listed("matriarchal clan law") == "matriarchal clan law"


def test_a_world_that_describes_nothing_still_opens_and_still_names_the_place():
    """The preface is what the place says about itself, so a place that says nothing
    simply has none — and then the clock carries the name, as it always did."""
    world, town = a_world()
    town.facts.clear()
    assert opening.the_world_here(town) == ""
    text = opening.compose(_game(world, town), "a stranger here")
    assert text.startswith("Evening in Averthorn.") or "in Averthorn." in text
