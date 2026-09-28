"""A person the prose describes is booked under the whole description, never a stump.

Measured in `tests/replay/2026-09-25-fight-bodies-plain-gemma4-12b.jsonl.gz`: the setup
beat wrote "a man with a thick neck and a weary face leans against the bar", and the
scene gained an actor called **man with a thick** — the tells then read "man with a
thick's attack misses Kesst Vayr" and "grappling man with a thick". The cut is in
`judgement.note_cast`: the description tail's slot is one word after the article, and an
adjective it does not recognise ("thick") takes the noun's place, leaving "neck" behind.

The prose no longer makes bodies (2026-09-27), but the stump still reaches one: `note_cast`
books it, `record_people` gives it a life, and `embody_sought` walks it on the moment the
player turns to "the man with the thick neck".

Measured over all 239 beats in tests/replay/ on 2026-09-27: 13 tails ended a word short,
and 8 beats then wrote the stump back as prose ("The man with a thick grunts"). After the
fix 12 of the 13 book whole; the one left is "a sharp, intelligent face", where the comma
is also how a clause begins. None of the 20 whole descriptions that the next word was a
verb or a function word gained a word.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from gm import judgement
from rules.engine import Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id
RECORDING = Path(__file__).parent / "replay" / "2026-09-25-fight-bodies-plain-gemma4-12b.jsonl.gz"


def fresh():
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s


def _recorded_setup_beat() -> str:
    with gzip.open(RECORDING, "rt", encoding="utf-8") as f:
        first = json.loads(f.readline())
    return next(t["text"] for t in first["added_transcript"] if t["who"] == "gm")


def test_the_recorded_beat_books_the_man_with_a_thick_neck():
    beat = _recorded_setup_beat()
    assert "a man with a thick neck and a weary face" in beat, "the recording changed"
    added = judgement.note_cast(fresh(), beat, turn=0)
    assert "man with a thick neck" in added, added
    assert "man with a thick" not in added


@pytest.mark.parametrize("beat,booked", [
    # Each one cut short in the recorded prose, and the noun it lost.
    ("A man with a thick neck and a weary face leans on the bar.", "man with a thick neck"),
    ("The man with the thick accent laughs at you.", "man with the thick accent"),
    ("A man in a stained leather apron wipes the counter.", "man in a stained leather apron"),
    ("A sturdy woman with a missing front tooth grins.", "sturdy woman with a missing front tooth"),
    ("The woman with the wild mane turns.", "woman with the wild mane"),
    ("A man with a wide wingspan lands on the roof.", "man with a wide wingspan"),
    # A plural noun, told from a verb by the auxiliary after it.
    ("The tall figure in the silk robes is now visible.", "tall figure in the silk robes"),
])
def test_a_description_is_not_cut_one_word_short(beat, booked):
    assert judgement.note_cast(fresh(), beat, turn=1) == [booked]


@pytest.mark.parametrize("beat,booked", [
    # Whole already, followed in the recordings by a verb or a function word: unchanged.
    ("The girl with the bread watches you closely.", "girl with the bread"),
    ("The man in the stained leather steps forward.", "man in the stained leather"),
    ("A man with a jagged scar across his cheek nods.", "man with a jagged scar"),
    ("A man with a scarred hand and a limp waits.", "man with a scarred hand"),
    ("The man with a massive wingspan is watching.", "man with a massive wingspan"),
    ("A man in a tattered tunic is sweeping.", "man in a tattered tunic"),
    # The older measurements this tail has carried (tests/test_one_person_one_card.py).
    ("A man with a distinctive satchel watches you.", "man with a distinctive satchel"),
    ("A man in the scarred leather steps up.", "man in the scarred leather"),
    # The adjective-and-comma rule still drops a known adjective stump.
    ("A man in a heavy, grease-stained leather apron stands behind the counter.", "man"),
])
def test_a_whole_description_gains_no_verb(beat, booked):
    assert judgement.note_cast(fresh(), beat, turn=1) == [booked]


def test_the_player_turning_to_him_embodies_the_whole_description():
    """The live door to a body since 2026-09-27: the prose records, the player's words
    embody. Before the fix the actor that walked on was named "man with a thick"."""
    s = fresh()
    beat = _recorded_setup_beat()
    introduced = judgement.note_cast(s, beat, turn=0)
    judgement.record_people(s, introduced, turn=0, world=WORLD)
    ref = judgement.embody_sought(s, "I talk to the man with the thick neck.", WORLD)
    assert ref, "nobody was found to talk to"
    assert s.actors[ref].name == "man with a thick neck", s.actors[ref].name


def test_a_stump_an_older_save_booked_is_the_same_person():
    """The replay corpus's saves were written before the fix, and their ledgers hold
    "sturdy woman with a missing front". Read whole, "a sturdy woman with a missing front
    tooth" no longer equals it, and booked her a second card on 2 of 142 replayed turns
    (note_cast booked 76 -> 78, population noted 62 -> 64). One word short of a phrase
    with a description in it is the same person; a bare role word is not a stump."""
    s = fresh()
    s.cast.append({"who": "sturdy woman with a missing front", "turn": 3})
    assert judgement.note_cast(
        s, "A sturdy woman with a missing front tooth waves you over.", turn=4) == []
    s = fresh()
    s.cast.append({"who": "man", "turn": 3})
    assert judgement.note_cast(
        s, "A man with a thick neck leans on the bar.", turn=4) == ["man with a thick neck"]
