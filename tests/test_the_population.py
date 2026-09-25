"""Everybody the prose describes is somebody the campaign keeps.

The user's rulings of 2026-09-25: the woman watching from a doorway "should stay there
until i leave or something moves them in prose. and once I leave that woman remains a
resident"; "there is nothing left of her?" had to be answered no; notes carry work, wants,
goals, hobbies, a rolled personality and a quirk. Before this, `note_cast`'s ledger was
cleared on every move, so a person the prose painted and the player did not engage at once
was gone the moment the party left the room.
"""
from __future__ import annotations

import json

from django.test import override_settings

from rules import population
from rules.engine import Scene


def _scene(at="plaza"):
    s = Scene(location_id="5bbd0c40345f")
    s.at = at
    s.clock_minutes = 600
    return s


def test_a_described_woman_is_recorded_where_she_was_seen():
    s = _scene()
    rec = population.note(s, "woman watching from a doorway", turn=3)
    assert rec["spot"] == "plaza" and rec["home"] == "5bbd0c40345f"
    assert rec["tier"] == "glimpse" and rec["first_seen"] == 600
    life = rec["life"]
    assert life["work"] and life["wants"] and life["goal"] and life["hobby"]
    assert life["quirk"] and life["traits"] and life["face"]


def test_seen_again_is_the_same_woman_not_a_second_one():
    s = _scene()
    first = population.note(s, "woman watching from a doorway")
    s.clock_minutes = 700
    again = population.note(s, "Woman watching from a doorway")
    assert again is first and len(s.population) == 1
    assert again["last_seen"] == 700 and again["first_seen"] == 600


def test_the_same_words_somewhere_else_are_somebody_else():
    s = _scene()
    a = population.note(s, "a guard")
    s.at = "gate"
    b = population.note(s, "a guard")
    assert a["id"] != b["id"] and len(s.population) == 2


def test_nobody_in_a_town_shares_a_quirk_until_the_bag_is_empty():
    s = _scene()
    who = ["baker", "fishwife", "carter", "guard", "scribe", "weaver", "beggar", "priest",
           "smith", "boy", "girl", "old man", "old woman", "sailor", "tanner", "potter",
           "minstrel", "servant", "farmer", "clerk"]
    frames = [population.note(s, f"a {w}")["life"]["quirk_frame"] for w in who]
    assert len(set(frames)) == 20


def test_a_life_is_rolled_once_and_kept(tmp_path):
    """The roll is stored, not the seed: a reload never re-rolls anybody."""
    from play import campaign as cm
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=str(tmp_path)):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        rec = population.note(c.scene, "an old fisherman mending nets")
        c.save()
        back = cm.Campaign.load(c.path())
        cm._LIVE.clear()
    assert back.scene.population[rec["id"]] == json.loads(json.dumps(rec))


def test_a_promoted_person_wears_the_face_their_record_rolled():
    from gm import judgement
    from world.loader import load_cached

    world = load_cached("fixtures/pangrella-campaign.json")
    s = _scene()
    rec = population.note(s, "man in a stained leather apron")
    s.cast.append({"who": "man in a stained leather apron", "turn": 1})
    judgement.promote_cast(s, ["man in a stained leather apron"], world=world)
    actor = s.people[rec["ref"]]
    assert rec["ref"] and rec["life"]["face"] in actor.appearance
    assert population.of_ref(s, actor.ref) is rec
