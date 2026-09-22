"""The engine's two travelling doors, walked rather than assigned.

The request, 2026-09-22: *"it should be that i can say i go to the market and the narrator
doesn't just put me in the market but describes all the places i needed to move through to
get there ... not that i have to spend four turns to get to the market. however if it is 4
places i move through there should be some kind of NPC encounter table that rolls for
chance encounters ... the chance should roll for every movement and it should roll on the
table for the respective area im moving through and stop rolling if an encounter hits. the
same should apply to over land travel."*

Both halves are here: `_op_travel` walking the exits graph inside a settlement, and
`_op_journey` checking the road watch by watch between them. The tables themselves and
their numbers are `tests/test_on_the_way.py`; this file is about what the engine does with
what they answer.
"""
from __future__ import annotations

from rules import journey as journey_mod, ontheway, places as places_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from world.loader import load_cached

WORLD = load_cached("fixtures/pangrella-campaign.json")


def _a_road() -> tuple[str, str]:
    for settlement in WORLD.play["settlements"]:
        for leg in journey_mod.legs_from(WORLD, settlement["id"]):
            if not leg.by_sea:
                return settlement["id"], leg.to_name
    raise AssertionError("the shipped world has no land route left to test with")


ROAD_FROM, ROAD_TO = _a_road()


def _party(town=ROAD_FROM, seed=3, hp=40):
    s = Scene(location_id=town)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = hp
    s.add(pc)
    e = Engine(s, Dice(seed=seed), world=WORLD)
    e.place_party()
    return s, e, pc


def _travel(e, pc, where):
    raw = {"op": "travel", "actor": pc.ref, "because": "t", "params": {"place": where}}
    return e.run(e.validate([raw], origin="author:test"))


def _journey(e, pc, where):
    raw = {"op": "journey", "actor": pc.ref, "because": "t", "params": {"to": where}}
    return e.run(e.validate([raw], origin="author:test"))


class _Quiet:
    """Dice that never let anything happen: every d100 comes up 100."""

    def __init__(self, real):
        self.real = real

    def __getattr__(self, name):
        return getattr(self.real, name)

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if notation == "1d100":
            return self.real.given(100, modifiers, label, notation)
        return self.real.roll(notation, modifiers, label, visibility)


class _Certain(_Quiet):
    """Dice that make the first check hit, and send the table to one band."""

    def __init__(self, real, band):
        super().__init__(real)
        self.band = band
        self.spent = 0

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if notation == "1d100":
            self.spent += 1
            return self.real.given(1 if self.spent == 1 else self.band,
                                   modifiers, label, notation)
        return self.real.roll(notation, modifiers, label, visibility)


def _far_side(e):
    """Somewhere in this town that is more than one hop from where the party stands."""
    here = e.here()
    for p in e.places():
        if p.described_only or p.id == here.id:
            continue
        if len(places_mod.route(e.places(), here.id, p.id)) > 1:
            return p
    raise AssertionError("this town is one hop wide")


class TestTheWalkAcrossTown:
    def test_one_turn_still_gets_you_all_the_way_there(self):
        """"not that i have to spend four turns to get to the market". The route is
        walked inside one op; one journey a turn is unchanged and uncontested."""
        s, e, pc = _party()
        e.dice = _Quiet(e.dice)
        far = _far_side(e)
        _travel(e, pc, far.name)
        assert s.at == far.id

    def test_the_tell_names_the_places_walked_through(self):
        """Before this, a travel was a single assignment however far it went, and the
        narrator had nothing to describe the way with — so it invented streets."""
        s, e, pc = _party()
        e.dice = _Quiet(e.dice)
        far = _far_side(e)
        through = places_mod.route(e.places(), s.at, far.id)[:-1]
        tell = " ".join(o.tell for o in _travel(e, pc, far.name).outcomes)
        assert "The way there ran through" in tell, tell
        for hop in through:
            assert (places_mod.find(e.places(), hop)).name in tell

    def test_a_single_step_names_no_way_there(self):
        """One hop is not a route, and "the way there ran through" with nothing in it
        would be the template speaking where the fiction has nothing to say."""
        s, e, pc = _party()
        e.dice = _Quiet(e.dice)
        here = e.here()
        nxt = places_mod.find(e.places(), here.exits[0])
        tell = " ".join(o.tell for o in _travel(e, pc, nxt.name).outcomes)
        assert "ran through" not in tell

    def test_something_on_the_way_stops_the_walk_where_it_happened(self):
        """"perhaps my journey is stopped short because as im moving through the streets
        a child pickpockets me or I get blocked by a pedestrian squabble"."""
        s, e, pc = _party()
        far = _far_side(e)
        first_hop = places_mod.route(e.places(), s.at, far.id)[0]
        e.dice = _Certain(e.dice, band=30)          # squabble
        tell = " ".join(o.tell for o in _travel(e, pc, far.name).outcomes)
        assert s.at == first_hop, "the party stops where it was stopped"
        assert "going at each other" in tell
        assert far.name in tell, "and is told where it was making for"

    def test_the_people_in_the_way_are_real_actors_on_the_new_ground(self):
        """A meeting the engine does not create is prose, and prose forgets. They
        arrive by `_bring_in`, the one door creatures come in by."""
        s, e, pc = _party()
        far = _far_side(e)
        e.dice = _Certain(e.dice, band=30)          # squabble: two of them
        before = set(s.actors)
        _travel(e, pc, far.name)
        # Two of them, plus whoever keeps the room they were stopped in — the keeper is
        # `staff_the_place`'s and has always been there.
        assert len(set(s.actors) - before) >= 2
        for a in s.actors.values():
            if not a.is_pc:
                assert a.at == s.at, "standing where the party stopped, not where it set out"

    def test_a_street_fight_starts_a_fight(self):
        """Four bands in a hundred are somebody who means it, and those four do not
        wait to be spoken to."""
        s, e, pc = _party()
        far = _far_side(e)
        e.dice = _Certain(e.dice, band=99)          # trouble
        _travel(e, pc, far.name)
        assert s.in_encounter

    def test_the_cutpurse_is_rolled_and_not_decided(self):
        """Sleight of Hand against the mark's Perception, both hidden. The purse only
        ever moves through `goods.spend`."""
        s, e, pc = _party()
        pc.purse = {"cp": 500}
        far = _far_side(e)
        e.dice = _Certain(e.dice, band=90)          # cutpurse
        tell = " ".join(o.tell for o in _travel(e, pc, far.name).outcomes)
        took = 500 - int(pc.purse.get("cp", 0))
        assert ("lighter" in tell) == (took > 0)
        assert took == 0 or 12 <= took <= 30

    def test_an_empty_purse_cannot_be_robbed(self):
        s, e, pc = _party()
        pc.purse = {}
        far = _far_side(e)
        e.dice = _Certain(e.dice, band=90)
        _travel(e, pc, far.name)
        assert not pc.purse

    def test_the_ground_underfoot_is_still_redrawn_where_the_walk_ended(self):
        """The 2026-09-21 defect, which the router must not reintroduce: the map has to
        be the map of the place the party actually stopped at."""
        s, e, pc = _party()
        far = _far_side(e)
        e.dice = _Certain(e.dice, band=30)
        _travel(e, pc, far.name)
        assert s.grid is not None
        assert s.positions.get(pc.ref) is not None
        assert s.grid.width == places_mod.find(e.places(), s.at).shape.width


class TestTheRoadBetweenTowns:
    def test_a_quiet_road_arrives_exactly_as_it_always_did(self):
        s, e, pc = _party()
        e.dice = _Quiet(e.dice)
        _journey(e, pc, ROAD_TO)
        assert s.location_id != ROAD_FROM

    def test_a_road_stopped_short_leaves_the_party_out_in_the_open(self):
        """Not back in town and not at the far end: on the ground the route crosses.
        A party halted in open country can be fought, camped with, and walked on from."""
        s, e, pc = _party()
        e.dice = _Certain(e.dice, band=70)          # travellers
        _journey(e, pc, ROAD_TO)
        assert s.location_id == ROAD_FROM, "they did not arrive"
        assert places_mod.terrain_of(s.at) != places_mod.URBAN, s.at

    def test_the_road_remembers_what_is_left_of_it(self):
        """Charging the whole road again would make being interrupted a punishment for
        the dice rather than an event."""
        s, e, pc = _party()
        e.dice = _Certain(e.dice, band=70)
        _journey(e, pc, ROAD_TO)
        assert s.road["to_name"] == ROAD_TO
        assert s.road["walked"] > 0
        assert s.road["from"] == ROAD_FROM

    def test_the_rest_of_the_road_is_the_only_part_walked_twice(self):
        s, e, pc = _party()
        e.dice = _Certain(e.dice, band=70)
        _journey(e, pc, ROAD_TO)
        walked = s.road["walked"]
        e.dice = _Quiet(e.dice.real)
        tell = " ".join(o.tell for o in _journey(e, pc, ROAD_TO).outcomes)
        assert s.location_id != ROAD_FROM
        assert f"{walked} hour" in tell, tell
        assert not s.road, "and the road is behind them once it is walked"

    def test_arriving_anywhere_clears_the_road(self):
        s, e, pc = _party()
        e.dice = _Quiet(e.dice)
        _journey(e, pc, ROAD_TO)
        assert s.road == {}

    def test_what_is_on_the_road_is_on_the_road_with_you(self):
        s, e, pc = _party()
        e.dice = _Certain(e.dice, band=70)
        before = len(s.actors)
        _journey(e, pc, ROAD_TO)
        assert len(s.actors) > before
        assert all(a.at == s.at for a in s.actors.values())

    def test_a_journey_that_stopped_short_still_spends_the_turn_s_journey(self):
        """Item 35 is not weakened by this: the party walked a road today."""
        s, e, pc = _party()
        e.dice = _Certain(e.dice, band=70)
        raw = [{"op": "journey", "actor": pc.ref, "because": "t",
                "params": {"to": ROAD_TO}},
               {"op": "journey", "actor": pc.ref, "because": "t",
                "params": {"to": ROAD_TO}}]
        res = e.run(e.validate(raw, origin="author:test"))
        assert "One journey a turn" in " ".join(o.tell for o in res.outcomes[1:])


class TestWhatTheNarratorIsTold:
    """The engine can walk a route and roll a table and it changes nothing the player
    reads unless the narrator is told. Every defect in `docs/playtest-2026-09-18.md`
    that survived a correct engine survived it this way."""

    def _brief(self, e):
        from gm import prompts

        return prompts.scene_brief(WORLD, e.scene, WORLD.get(e.scene.location_id),
                                   recent=[], turn=1, here=e.here(), known=e.places())

    def test_the_brief_says_what_is_next_door_and_not_only_what_exists(self):
        """A flat list of every room reads as a flat list of equally near rooms, which
        is what produced plans of five travels (item 35)."""
        s, e, pc = _party()
        brief = self._brief(e)
        assert "NEXT DOOR" in brief
        for near in (places_mod.find(e.places(), x) for x in e.here().exits):
            if near is not None:
                assert near.name in brief

    def test_the_brief_tells_the_plan_to_name_the_destination_and_not_the_route(self):
        s, e, pc = _party()
        assert "Never plan the route yourself." in self._brief(e)

    def test_the_brief_says_what_is_underfoot(self):
        """The positional half of the request. The same shape the tactical map is drawn
        from, so the stalls the prose describes are the stalls on the map."""
        s, e, pc = _party()
        here = e.here()
        from rules import floorplan

        about = floorplan.describe(here.id, here.terrain, here.shape)
        assert about and about in self._brief(e)

    def test_an_arrival_turn_asks_for_an_arrival(self):
        from gm import prompts

        msgs = prompts.call_prose_messages(
            "BRIEF", [], "i go to the market",
            ["The way there ran through the gate and the square. You are at the market now."])
        last = msgs[-1]["content"]
        assert "THIS TURN THE PARTY ARRIVED SOMEWHERE" in last
        assert "End on ONE particular thing" in last

    def test_an_ordinary_turn_does_not(self):
        """A five-part instruction on every beat is a five-part beat on every turn —
        this file's own rule about prompt shape becoming output shape."""
        from gm import prompts

        msgs = prompts.call_prose_messages("BRIEF", [], "i look around",
                                           ["The merchant says nothing."])
        assert "ARRIVED SOMEWHERE" not in msgs[-1]["content"]
