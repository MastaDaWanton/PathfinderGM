"""What a second reading of the travelling doors found, 2026-09-23.

The route walk, the road check and the road memory landed on 2026-09-22 across three
commits with a green suite behind each. Read again the next day, end to end and with
the engine driven rather than the tests re-run, six things were wrong that no test had
been written for. Each class below records one, with the measurement that found it.
"""
from __future__ import annotations

from pathlib import Path

from rules import attitude as attitude_mod, ontheway, places as places_mod, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from test_the_way_there import (ROAD_FROM, ROAD_TO, _Certain, _Quiet, _far_side,
                                _journey, _party, _travel)

WOLF = {"id": "wolf", "name": "wolf", "creature_type": "animal", "cr_value": 1}


def _meeting(kind, **kw):
    base = {"kind": kind, "roll": 10, "after": 1}
    if kind == "weather":
        base["count"] = 0
    elif kind == "creature":
        base.update(creature=WOLF, template="wolf", aggressive=True, count=1)
    base.update(kw)
    return ontheway.Meeting(**base)


def _outcomes(e, raws):
    return e.run(e.validate(raws, origin="author:test")).outcomes


class _HitOn(_Quiet):
    """Dice that make the n-th d100 hit and send the table to one band."""

    def __init__(self, real, n, band):
        super().__init__(real)
        self.n, self.band, self.spent = n, band, 0

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if notation != "1d100":
            return self.real.roll(notation, modifiers, label, visibility)
        self.spent += 1
        if self.spent == self.n:
            return self.real.given(1, modifiers, label, notation)
        if self.spent == self.n + 1:
            return self.real.given(self.band, modifiers, label, notation)
        return self.real.given(100, modifiers, label, notation)


class TestWeatherOnAHopIsNobody:
    """`_op_travel`'s meeting block called `_bring_in` unguarded. A weather meeting is
    count zero and no template; `_bring_in` reads a count of zero as one and asked the
    bestiary for a creature named "", which raises `UnknownTemplate` — at resolution
    time a 502 with the player's sentence deleted. Journey and venture both guarded on
    the count; travel did not. Reproduced by forcing the road's table to weather on a
    hop to the forest."""

    def test_the_walk_does_not_raise_and_nobody_arrives(self, monkeypatch):
        s, e, pc = _party()
        monkeypatch.setattr(ontheway, "road", lambda *a, **k: _meeting("weather"))
        monkeypatch.setattr(ontheway, "street", lambda *a, **k: None)
        before = len(s.actors)
        tell = " ".join(o.tell for o in _outcomes(e, [
            {"op": "travel", "actor": pc.ref, "because": "t",
             "params": {"biome": "forest"}}]))
        assert len(s.actors) == before
        assert "no walking through this" in tell

    def test_the_storm_costs_hours_here_as_it_does_on_the_road(self, monkeypatch):
        """An authored band with no teeth is worse than none (`rules/ontheway.py`)."""
        s, e, pc = _party()
        monkeypatch.setattr(ontheway, "road", lambda *a, **k: _meeting("weather"))
        monkeypatch.setattr(ontheway, "street", lambda *a, **k: None)
        clock = s.clock_minutes
        tell = " ".join(o.tell for o in _outcomes(e, [
            {"op": "travel", "actor": pc.ref, "because": "t",
             "params": {"biome": "forest"}}]))
        # The hour the wall costs, and then at least the 1d4+1 the weather does.
        assert s.clock_minutes - clock >= 60 + 2 * 60
        assert "go by before it lets you" in tell


class TestTheWayIntoGroundIsWalkedOnce:
    """The venture rolled its own road check at the PARENT, brought the creature in
    there, opened the fight, and then moved the party in through `travel` — which
    ended the fight and shed the creature. Measured on a cave: "You are at the cave
    now. The fight is left behind. Left behind: wolf. The road is not empty: a wolf is
    on it, and it has seen you." And the inner travel rolled its own one-hour check on
    top, so a two-hour way in was checked twice."""

    def _venture(self, e, pc, kind="cave"):
        return _outcomes(e, [{"op": "venture", "actor": pc.ref, "because": "t",
                              "params": {"kind": kind, "parent": e.here().name}}])

    def test_what_is_met_on_the_way_in_is_in_there_with_you(self, monkeypatch):
        s, e, pc = _party()
        monkeypatch.setattr(ontheway, "road", lambda *a, **k: _meeting("creature"))
        monkeypatch.setattr(ontheway, "street", lambda *a, **k: None)
        tell = " ".join(o.tell for o in self._venture(e, pc))
        wolf = next(a for a in s.actors.values() if a.name == "wolf")
        assert wolf.at == s.at == pc.at
        assert s.in_encounter, "it has seen you, and the fight is still on"
        assert "eft behind" not in tell, tell

    def test_the_hours_the_kind_charges_are_what_is_checked_and_only_once(self, monkeypatch):
        s, e, pc = _party()
        calls = []

        def road(dice, hours, biome, level=1):
            calls.append((hours, biome))
            return None

        monkeypatch.setattr(ontheway, "road", road)
        monkeypatch.setattr(ontheway, "street", lambda *a, **k: None)
        self._venture(e, pc, kind="cave")
        assert calls == [(places_mod.VENTURES["cave"]["hours"], "underground")], calls

    def test_ground_that_costs_no_hours_is_still_a_step(self, monkeypatch):
        """Down into the sewers is free on the clock and still a hop on the table."""
        s, e, pc = _party()
        calls = []
        monkeypatch.setattr(ontheway, "road",
                            lambda dice, hours, biome, level=1: calls.append(hours))
        monkeypatch.setattr(ontheway, "street", lambda *a, **k: None)
        self._venture(e, pc, kind="sewers")
        assert calls == [1]

    def test_nothing_is_left_behind_for_the_next_venture(self, monkeypatch):
        """The handshake is cleared even when the walk is refused."""
        s, e, pc = _party()
        monkeypatch.setattr(ontheway, "road", lambda *a, **k: None)
        monkeypatch.setattr(ontheway, "street", lambda *a, **k: None)
        self._venture(e, pc, kind="cave")
        assert e._hours_underway == {}


class TestTheWayInHasAHandleOnTheInside:
    """`_with_a_way_in` gave the generated entrance an exit to the first authored place
    and gave nothing an exit back. Measured on Aurvantis: all eight villages given a
    way in had it unreachable from every other place — `route` found no path, `travel`
    there fell back to a single unwalked step, and NEXT DOOR never listed it."""

    def test_every_generated_way_in_is_reachable_from_everywhere(self):
        from world.loader import load_cached

        world = load_cached("fixtures/aurvantis-campaign.json")
        checked = 0
        for row in world.play["settlements"]:
            home = places_mod.home_set(world.get(row["id"]))
            way = [p for p in home if p.origin == "generated" and p.name == "the way in"]
            if not way:
                continue
            checked += 1
            for p in home:
                if p.id != way[0].id:
                    assert places_mod.route(home, p.id, way[0].id), (row["id"], p.name)
        assert checked == 8, "the measurement was eight villages"

    def test_the_first_authored_place_is_the_one_that_gained_the_door(self):
        from test_authored_places import _ent, _place

        got = places_mod.home_set(_ent(places=[_place()]))
        assert [p.name for p in got] == ["the market", "the way in"]
        assert got[1].id in got[0].exits
        assert got[0].id in got[1].exits


class TestTheRoadRemembersProgressAndNotWeather:
    """`scene.road["walked"]` was taken off `hours` after the storm's hours had been
    added to it: a ten-hour road held up by weather on its second watch recorded twelve
    hours walked."""

    def test_the_hours_sat_out_are_not_hours_walked(self):
        s, e, pc = _party()
        e.dice = _Certain(e.dice, band=80)          # watch one: weather
        _journey(e, pc, ROAD_TO)
        assert s.location_id == ROAD_FROM
        assert s.road["walked"] == ontheway.WATCH_HOURS, s.road


class TestAMeetingOnTheLastWatchIsAnArrival:
    """The check falls at the end of a watch, and the last watch of a march ends where
    the road does. Measured on an eight-hour road: a hit on its second watch recorded
    eight hours walked of eight and stood the party in the fields outside the town they
    had LEFT, with the next attempt costing one hour."""

    def test_they_arrive_and_what_they_met_is_with_them(self):
        s, e, pc = _party()
        from rules import journey as journey_mod

        leg = journey_mod.find(journey_mod.legs_from(e.world, ROAD_FROM), ROAD_TO)
        hours = journey_mod.hours_for(leg, pc.speed_feet)[0]
        full, rest = divmod(hours, ontheway.WATCH_HOURS)
        checks = full + (1 if rest else 0)
        before = len(s.actors)
        e.dice = _HitOn(e.dice, n=checks, band=70)   # the last watch: travellers
        tell = " ".join(o.tell for o in _journey(e, pc, ROAD_TO).outcomes)
        assert s.location_id != ROAD_FROM, tell
        assert s.road == {}
        assert len(s.actors) > before
        assert all(a.at == s.at for a in s.actors.values())
        assert "There are others on this road" in tell


class TestBackInsideTheWallsIsOffTheRoad:
    """The road memory was keyed on the settlement the party set out from, and walking
    back into that settlement does not change the key — so a party three hours out,
    back in town for the night, set out next morning with three hours credited."""

    def test_walking_back_into_town_forgets_the_road(self):
        s, e, pc = _party()
        e.dice = _Certain(e.dice, band=70)
        _journey(e, pc, ROAD_TO)
        assert s.road
        e.dice = _Quiet(e.dice.real)
        inside = next(p for p in e.places() if p.terrain == places_mod.URBAN
                      and not p.described_only)
        _travel(e, pc, inside.name)
        assert s.at == inside.id
        assert s.road == {}

    def test_setting_out_on_another_road_forgets_the_old_one(self):
        s, e, pc = _party()
        s.road = {"to": "nowhere", "to_name": "Nowhere", "from": ROAD_FROM, "walked": 3}
        e.dice = _Quiet(e.dice)
        _journey(e, pc, ROAD_TO)
        assert s.road == {}


class TestStoppedShortSaysWhereTheyAre:
    def test_the_second_move_is_refused_with_the_true_place(self):
        """`_journeyed` was set to the far town's name on a journey that did not reach
        it, so the refusal read "is at Vylthysia" a sentence after "got no further"."""
        s, e, pc = _party()
        e.dice = _Certain(e.dice, band=70)
        tells = [o.tell for o in _outcomes(e, [
            {"op": "journey", "actor": pc.ref, "because": "t", "params": {"to": ROAD_TO}},
            {"op": "journey", "actor": pc.ref, "because": "t", "params": {"to": ROAD_TO}}])]
        assert "One journey a turn" in tells[1]
        assert e.here().name in tells[1], tells[1]
        assert ROAD_TO not in tells[1], tells[1]


class TestTheWatchReadsWhereYouGot:
    """The warrant block ran before the walk, against the place the plan named: a
    suspected character stopped one hop short of the gate by a hawker was told the
    guards at the gate looked twice and let them through."""

    def _suspect(self, pc, town, how="suspected"):
        tag = (states.wanted_tag(town) if how == "wanted"
               else states.suspected_tag(town))
        pc.apply_effect(ActiveEffect(name=how, kind="situation", key=f"t:{tag}",
                                     source="t", origin="t",
                                     duration="until-dismissed", tags=(tag,)))

    def _away_from_the_gate(self):
        s, e, pc = _party()
        e.dice = _Quiet(e.dice)
        gate = e.here()
        assert " ".join(gate.name.split()).lower() in places_mod.ENTRANCES
        _travel(e, pc, _far_side(e).name)
        assert len(places_mod.route(e.places(), s.at, gate.id)) > 1
        return s, e, pc, gate

    def test_stopped_short_of_the_gate_nobody_looked_twice(self):
        s, e, pc, gate = self._away_from_the_gate()
        self._suspect(pc, ROAD_FROM)
        e.dice = _Certain(e.dice.real, band=10)       # the first hop: a cart across it
        tell = " ".join(o.tell for o in _travel(e, pc, gate.name).outcomes)
        assert "got no further" in tell
        assert "look twice" not in tell, tell

    def test_reaching_the_gate_they_still_do(self):
        s, e, pc, gate = self._away_from_the_gate()
        self._suspect(pc, ROAD_FROM)
        e.dice = _Quiet(e.dice.real)
        tell = " ".join(o.tell for o in _travel(e, pc, gate.name).outcomes)
        assert "look twice" in tell, tell

    def test_a_wanted_character_stopped_short_was_not_taken_at_an_arch_they_never_reached(self):
        s, e, pc, gate = self._away_from_the_gate()
        self._suspect(pc, ROAD_FROM, how="wanted")
        e.dice = _Certain(e.dice.real, band=10)
        out = _travel(e, pc, gate.name).outcomes[-1]
        assert out.effects, "moved, not refused"
        assert "got no further" in out.tell
        e.dice = _Quiet(e.dice.real)
        out = _travel(e, pc, gate.name).outcomes[-1]
        assert out.effects == [] and "wanted" in out.tell


class TestCompanyIsSomebodyInTheRoom:
    """Listed in the review as a gap — "`_op_company` never asks where the person is" —
    and found on writing the test to be no gap: `Scene.actors` is "who is in the
    party's place" (`_Here`), so somebody at another place is not an actor the op can
    see, and the existing refusal already fires. Kept as the record of that, so the
    next reading does not add the same dead check this one nearly did."""

    def test_somebody_in_another_place_cannot_be_asked_along(self):
        s, e, pc = _party()
        marra = instantiate("guildhand", scene=s, name="Marra")
        s.add(marra)
        e.settle_attitude(marra, attitude_mod.COMES_ALONG, None, "t")
        elsewhere = next(p for p in e.places() if p.id != s.at and not p.described_only)
        s.move(marra.ref, elsewhere.id)
        assert marra.ref not in s.actors
        out = _outcomes(e, [{"op": "company", "actor": pc.ref, "because": "t",
                             "params": {"who": marra.ref}}])[-1]
        assert out.effects == []
        assert "here to come along" in out.tell, out.tell
        assert not marra.has_state(states.TRAVELS_WITH_YOU)
        # In the room, the same word works.
        s.move(marra.ref, s.at)
        out = _outcomes(e, [{"op": "company", "actor": pc.ref, "because": "t",
                             "params": {"who": marra.ref}}])[-1]
        assert marra.has_state(states.TRAVELS_WITH_YOU), out.tell


class TestNoReaderSpellsAnAttitude:
    def test_acquaint_asks_the_track_for_its_step(self):
        """The commit that introduced `attitude.COMES_ALONG` so that no reader spells an
        attitude spelled one in `backgrounds.acquaint`."""
        src = Path("rules/backgrounds.py").read_text(encoding="utf-8")
        assert '"friendly"' not in src
        assert "attitude_mod.COMES_ALONG" in src
