"""A place the narration establishes is founded and remembered, when it makes sense.

Ruled 2026-09-23, reversing item 45's answer of rewriting such a beat away:

    "i dont mind it creating a dock so long as it remembers that it has a dock and
    remembers the tavern it put there. It will need to be able to create places that
    is not a problem what matters is the places being remembered, interesting, and at
    least make sense to be where they are. This picture shows the way Vormoor was
    introduced a dock makes sense."

The picture was Vormoor's opening — "rises from the water on a skeletal framework of
coral and driftwood, the stilt-housing swaying slightly as the tide moves" — beside a
beat that had walked the player out to the docks and into a tavern called the
Driftwood Reach. Vormoor's export lists neither. Its facts do say "coral and driftwood
stilt-housing" and "water rights", which is why a dock there makes sense and a dock in
a dry hill village does not.

Three things are pinned: REMEMBERED (the place is on the list next turn, next door, with
the page's own description, and the guard no longer flags it); MAKES SENSE (`fits_here`
refuses a cathedral in a village and docks with no water); and INTERESTING in the one
way the engine can measure — a founded tavern is shaped as a tavern and gets somebody
behind its bar.
"""
from __future__ import annotations

from gm import narration
from rules import keepers, places
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = next(s["id"] for s in WORLD.play["settlements"] if s.get("name") == "Vormoor")


def _party(town=VORMOOR):
    s = Scene(location_id=town)
    pc = instantiate("guildhand", scene=s, name="Spree")
    pc.kind = "pc"
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    return s, e, pc


def _names(e):
    return [p.name for p in e.places()]


class TestMakesSense:
    def test_a_dock_makes_sense_in_a_village_on_stilts(self):
        assert places.fits_here("docks", WORLD.get(VORMOOR)) == ""

    def test_a_tavern_makes_sense_anywhere_people_live(self):
        assert places.fits_here("tavern", WORLD.get(VORMOOR)) == ""

    def test_a_cathedral_does_not_make_sense_in_a_village(self):
        why = places.fits_here("cathedral", WORLD.get(VORMOOR))
        assert "village does not have a cathedral" in why, why

    def test_docks_need_water(self):
        dry = next(WORLD.get(s["id"]) for s in WORLD.play["settlements"]
                   if places.fits_here("docks", WORLD.get(s["id"])))
        assert "water" in places.fits_here("docks", dry)

    def test_a_kind_the_table_does_not_know_is_refused_with_the_list(self):
        why = places.fits_here("counting-house of the league", WORLD.get(VORMOOR))
        assert "no such kind" in why and "tavern" in why


class TestRemembered:
    def test_the_tavern_the_page_put_there_is_a_place_now(self):
        s, e, pc = _party()
        assert "the tavern" not in _names(e)
        note, why = e.found_from_prose(
            "the tavern", "The tavern is a squat, sturdy building of timber and stone.")
        assert note and not why
        tav = places.find(e.places(), "the tavern")
        assert tav is not None and tav.kind == "tavern" and tav.origin == "narrated"
        assert tav.about.startswith("The tavern is a squat")
        assert tav.parent == s.at, "off the place the party was standing in"
        # Described, not stood in: the party has not moved.
        assert s.at != tav.id

    def test_it_survives_a_save_with_its_kind_and_its_shape(self):
        s, e, pc = _party()
        e.found_from_prose("the tavern", "The tavern is a squat building.")
        raw = next(d for d in s.founded if d["name"] == "the tavern")
        back = places.from_dict(raw)
        assert back.kind == "tavern"
        assert back.shape is not None and back.shape == places.shape_of_kind("tavern", back.terrain)

    def test_the_guard_no_longer_flags_it(self):
        s, e, pc = _party()
        here = e.here().name
        assert narration.stands_elsewhere("You sit in the tavern.", here=here,
                                          places=tuple(_names(e)))
        e.found_from_prose("the tavern", "The tavern is a squat building.")
        got = narration.stands_elsewhere("The tavern is quiet tonight.", here=here,
                                         places=tuple(_names(e)))
        assert got == [], got

    def test_it_is_made_once(self):
        s, e, pc = _party()
        e.found_from_prose("the tavern", "The tavern is a squat building.")
        assert e.found_from_prose("the tavern", "The tavern again.") == ("", "")
        assert _names(e).count("the tavern") == 1

    def test_standing_in_it_moves_the_party_there(self):
        s, e, pc = _party()
        note, why = e.found_from_prose(
            "the docks", "You step out onto the docks, where the timber groans.",
            standing=narration.claims_standing(
                "You step out onto the docks, where the timber groans.", "the docks"))
        assert "the party is in it" in note
        assert e.here().name == "the docks"
        assert pc.at == s.at

    def test_a_place_that_makes_no_sense_is_not_made_and_the_reason_is_said(self):
        s, e, pc = _party()
        note, why = e.found_from_prose("the cathedral", "The cathedral looms.")
        assert note == "" and "village does not have a cathedral" in why
        assert "the cathedral" not in _names(e)


class TestInteresting:
    def test_a_founded_tavern_is_shaped_as_a_tavern(self):
        s, e, pc = _party()
        e.found_from_prose("the tavern", "The tavern is a squat building.")
        tav = places.find(e.places(), "the tavern")
        assert tav.shape == places.shape_of_kind("tavern", tav.terrain)

    def test_and_has_somebody_behind_the_bar_when_the_party_walks_in(self):
        s, e, pc = _party()
        e.found_from_prose("the tavern", "The tavern is a squat building.")
        title, words = keepers.wanted_at(places.find(e.places(), "the tavern"))
        assert title, "a tavern is staffed"
        before = len(s.people)
        raw = {"op": "travel", "actor": pc.ref, "because": "t",
               "params": {"place": "the tavern"}}
        e.run(e.validate([raw], origin="author:test"))
        assert e.here().name == "the tavern"
        assert len(s.people) > before

    def test_a_named_house_of_a_kind_is_staffed_as_its_kind(self):
        s, e, pc = _party()
        raw = {"op": "found", "actor": pc.ref, "because": "t",
               "params": {"name": "the Driftwood Reach", "kind": "tavern",
                          "about": "a squat, leaning structure of lashed-together beams"}}
        out = e.run(e.validate([raw], origin="author:test")).outcomes[-1]
        assert out.effects and "It is a tavern." in out.tell, out.tell
        reach = places.find(e.places(), "the Driftwood Reach")
        assert reach.kind == "tavern"
        assert keepers.wanted_at(reach)[0]

    def test_the_plan_is_refused_a_kind_that_makes_no_sense(self):
        s, e, pc = _party()
        raw = {"op": "found", "actor": pc.ref, "because": "t",
               "params": {"name": "the Great Cathedral", "kind": "cathedral"}}
        out = e.run(e.validate([raw], origin="author:test")).outcomes[-1]
        assert out.status == "refused" and "cathedral" in out.tell
