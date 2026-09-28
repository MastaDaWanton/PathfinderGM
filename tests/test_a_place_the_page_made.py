"""A place is made by the plan or the player, remembered, and made to make sense — and
the page makes none.

Two rulings, the second replacing the first:

  * 2026-09-23, reversing item 45's rewrite: "i dont mind it creating a dock so long as
    it remembers that it has a dock and remembers the tavern it put there … what matters
    is the places being remembered, interesting, and at least make sense to be where
    they are." The page was given leave to found the places it established.
  * 2026-09-27, option (a) of the declared-not-guessed review: places come from the plan
    (`found`, which can now found and walk in within one turn), from the player, and from
    venturing out — no longer from the page. Measured before choosing: in three live runs
    of the discover script the page founded none and the plan all ten; the page's one
    measured misfire was a smithy founded from a brawl's prose. A beat that puts the
    party somewhere they are not is corrected (`stands-elsewhere`), never kept.

What the first ruling cared about still holds, through the plan's door: REMEMBERED (on
the list next turn, surviving a save), MAKES SENSE (`fits_here`), and INTERESTING in the
one way the engine can measure — a founded tavern is shaped as a tavern and staffed.
"""
from __future__ import annotations

import json

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


def _found(e, pc, name, kind="", about=""):
    raw = {"op": "found", "actor": pc.ref, "because": "t",
           "params": {"name": name, **({"kind": kind} if kind else {}),
                      **({"about": about} if about else {})}}
    return e.run(e.validate([raw], origin="author:test")).outcomes[-1]


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

    def test_the_plan_is_refused_a_kind_that_makes_no_sense(self):
        s, e, pc = _party()
        out = _found(e, pc, "the Great Cathedral", "cathedral")
        assert out.status == "refused" and "cathedral" in out.tell


class TestRemembered:
    def test_the_tavern_the_plan_founds_is_a_place_now(self):
        s, e, pc = _party()
        assert "the tavern" not in _names(e)
        out = _found(e, pc, "the tavern", "tavern", "a squat, sturdy building")
        tav = places.find(e.places(), "the tavern")
        assert tav is not None and tav.kind == "tavern", out.tell
        # Founded, not stood in: the party has not moved.
        assert s.at != tav.id

    def test_it_survives_a_save_with_its_kind_and_its_shape(self):
        s, e, pc = _party()
        _found(e, pc, "the tavern", "tavern")
        raw = next(d for d in s.founded if d["name"] == "the tavern")
        back = places.from_dict(json.loads(json.dumps(raw)))
        assert back.kind == "tavern"
        assert back.shape is not None and back.shape == places.shape_of_kind("tavern", back.terrain)

    def test_the_guard_no_longer_flags_it(self):
        s, e, pc = _party()
        here = e.here().name
        assert narration.stands_elsewhere("You sit in the tavern.", here=here,
                                          places=tuple(_names(e)))
        _found(e, pc, "the tavern", "tavern")
        got = narration.stands_elsewhere("The tavern is quiet tonight.", here=here,
                                         places=tuple(_names(e)))
        assert got == [], got

    def test_it_is_made_once(self):
        s, e, pc = _party()
        _found(e, pc, "the tavern", "tavern")
        again = _found(e, pc, "the tavern", "tavern")
        assert again.status == "refused" and "already a place" in again.tell
        assert _names(e).count("the tavern") == 1

    def test_founded_and_walked_into_in_one_plan(self):
        s, e, pc = _party()
        e.run(e.validate([
            {"op": "found", "actor": pc.ref, "params": {"name": "the docks", "kind": "docks"}},
            {"op": "travel", "actor": pc.ref, "params": {"place": "the docks"}}],
            origin="author:test"))
        assert e.here().name == "the docks"
        assert pc.at == s.at


class TestInteresting:
    def test_a_founded_tavern_is_shaped_as_a_tavern(self):
        s, e, pc = _party()
        _found(e, pc, "the tavern", "tavern")
        tav = places.find(e.places(), "the tavern")
        assert tav.shape == places.shape_of_kind("tavern", tav.terrain)

    def test_and_has_somebody_behind_the_bar_when_the_party_walks_in(self):
        s, e, pc = _party()
        _found(e, pc, "the tavern", "tavern")
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
        out = _found(e, pc, "the Driftwood Reach", "tavern",
                     "a squat, leaning structure of lashed-together beams")
        assert out.effects and "It is a tavern." in out.tell, out.tell
        reach = places.find(e.places(), "the Driftwood Reach")
        assert reach.kind == "tavern"
        assert keepers.wanted_at(reach)[0]


class TestThePageFoundsNothing:
    """The ruling of 2026-09-27: a beat that walks the party into a place the town does
    not list is corrected, not kept."""

    def test_a_beat_set_in_an_unlisted_tavern_founds_nothing(self, monkeypatch):
        from gm import client as gm_client
        from gm.agent import GMAgent
        from gm.client import Reply

        s, e, pc = _party()
        here = e.here().name
        fixed = f"You stand at {here}, the evening coming down around you. What do you do?"
        monkeypatch.setattr(gm_client, "chat", lambda *a, **k: Reply(
            json.dumps({"narration": fixed}), 0.1, "stub"))
        before = _names(e)
        GMAgent(WORLD, e).polish("You sit in the tavern with a cup of something warm, "
                                 "listening to the room. What do you do?")
        assert _names(e) == before
        assert not hasattr(GMAgent, "_found_from_the_page")
