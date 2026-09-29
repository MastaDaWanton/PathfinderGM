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
    # Through the turn's own door, with the ledger holding each: booked by `population.note`
    # alone, "a clerk" is found as the one scribe standing here — the finder reads clerk
    # as the scribe's trade — which is right for somebody met before and wrong for a
    # beat that books them both.
    from gm import judgement

    frames = []
    for w in who:
        s.cast.append({"who": w, "turn": 1})
        frames += [r["life"]["quirk_frame"] for r in judgement.record_people(s, [w])]
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


def test_the_openings_own_company_is_in_the_population(tmp_path):
    """Measured live 2026-09-25: "the woman at the bread stall" stood on the board with no
    record and no face — only `views._finish` noted people, and the opening never passes
    through it."""
    from play import campaign as cm
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=str(tmp_path)):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        cm._LIVE.clear()
    # The people the start brought in (rules/openings.py, 2026-09-28). The keeper of a
    # counter the start stands at is the keepers' own business and is not the opening's.
    brought = set((c.scene.start.get("slots") or {}).values())
    company = [a for a in c.scene.actors.values() if a.ref in brought]
    assert company
    for actor in company:
        rec = population.of_ref(c.scene, actor.ref)
        assert rec is not None, actor.name
        # A world resident wears their own Appearance fact; everybody else the face
        # their record rolled.
        if not actor.world_entity_id:
            assert rec["life"]["face"] in actor.appearance


def test_a_crowd_is_not_one_person_with_a_life():
    """Measured live 2026-09-25: "neighboring merchants" was rolled a work, a face and a
    quirk, as if one merchant. A bare plural and a counted group are scenery until the
    prose singles one of them out."""
    from gm import judgement

    s = _scene()
    s.cast = [{"who": "neighboring merchants", "turn": 1},
              {"who": "guard", "turn": 1, "count": 3},
              {"who": "woman at the bread stall", "turn": 1}]
    made = judgement.record_people(s, [e["who"] for e in s.cast], turn=1)
    assert [r["phrase"] for r in made] == ["woman at the bread stall"]
    assert len(s.population) == 1


def test_the_prose_calling_her_by_other_words_is_still_her():
    """Measured live 2026-09-25: an old woman "mending fishing nets by the doorway" was a
    glimpse at the party's spot; the player spoke to her, the prose wrote "the old woman",
    and the booking door made a second person with a second face while her record stayed
    without a body. The booking now asks the finder first."""
    from gm import judgement
    from world.loader import load_cached

    world = load_cached("fixtures/pangrella-campaign.json")
    s = _scene()
    her = population.note(s, "old woman mending fishing nets by the doorway")
    s.cast.append({"who": "old woman", "turn": 2})
    made = judgement.record_people(s, ["old woman"], turn=2)
    assert made == [her] and len(s.population) == 1
    judgement.promote_cast(s, ["old woman"], beat="The old woman looks up from her nets.",
                           world=world)
    assert her["ref"] and her["life"]["face"] in s.people[her["ref"]].appearance


def test_two_the_ledger_ruled_different_stay_two():
    """The ledger's definiteness test already said "a young guard" and "a guard" arriving
    are two people; the finder does not overrule it."""
    from gm import judgement

    s = _scene()
    s.cast = [{"who": "young guard", "turn": 1}]
    judgement.record_people(s, ["young guard"], turn=1)
    s.cast.append({"who": "guard", "turn": 2})
    judgement.record_people(s, ["guard"], turn=2)
    assert len(s.population) == 2


def test_the_openings_company_is_not_booked_a_second_time(tmp_path):
    """Measured live 2026-09-25: the opening put "the old man ahead of you" at the
    well-head; the next beat called him "the old man" and a second old man was booked and
    stood beside him. The ledger, whose definiteness test decides that, had never been
    told the opening's company was there."""
    from gm import judgement
    from play import campaign as cm
    from rules.sheet import load_pc

    # The well queue is a start document now (the kept quiet floor, 2026-09-28), and
    # its lead is "the old neighbour".
    with override_settings(CAMPAIGN_DIR=str(tmp_path)):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-well-queue")
        cm._LIVE.clear()
    assert c.scene.start.get("id") == "quiet-the-well-queue"
    before = len(c.scene.actors)
    booked = judgement.note_cast(
        c.scene, "The old neighbour turns, squints at your bucket, and says nothing.",
        turn=1)
    assert booked == []
    judgement.promote_cast(c.scene, booked, beat="", world=c.world)
    assert len(c.scene.actors) == before
