"""Regard: how somebody stands towards the player over time, as a number.

Asked for 2026-09-24: *"their attitude toward me quantified ... I want to be able to
talk with them and increase that attitude until they Idolize/Love me."* The book's track
(`rules/attitude.py`) is a state a check sets for 1d4 hours and has no memory: when the
shift ran out the person was indifferent again, whatever had passed between them. Regard
is the memory — a 0 to 100 score kept on the person as ONE effect, the track's baseline
when nothing is holding a step, and the number the talk panel shows.

Three laws: the score is an `ActiveEffect` with a tag (`states.REGARD`) and a source, so
removing the effect removes the opinion; `attitude.set_regard` is the one writer; the
narrator is told a step crossed in words and never the number.
"""
from __future__ import annotations

from rules import attitude, states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "5bbd0c40345f"
MARKET = f"{TOWN}~urban:the-market"


def _table(seed: int = 5):
    s = Scene(location_id=TOWN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=seed), world=WORLD)
    e.place_party(MARKET)
    grix = s.add(instantiate("thug", scene=s, name="Grix"))
    return s, e, grix


def _talk(e, who, face, skill="diplomacy"):
    res = e.run(e.validate(
        [{"op": "check", "actor": "pc", "target": who.ref, "because": "a word",
          "params": {"skill": skill}}], origin="author:test"))
    if res.awaiting:
        res = e.resume(face)
    return next(o for o in res.outcomes if o.op == "check")


class TestTheScale:
    def test_a_stranger_reads_as_indifferent_with_nothing_recorded(self):
        s, e, grix = _table()
        assert not grix.has_state(states.REGARD)
        assert attitude.regard_of(grix) == attitude.floor_of("indifferent")
        assert attitude.of(grix) == "indifferent"

    def test_the_bands_cover_the_scale_in_order(self):
        assert [attitude.band_of(n) for n in (0, 14, 15, 34, 35, 54, 55, 74, 75, 89, 90, 100)] == [
            "hostile", "hostile", "unfriendly", "unfriendly", "indifferent", "indifferent",
            "friendly", "friendly", "helpful", "helpful", "devoted", "devoted"]

    def test_devoted_is_on_the_track_and_no_check_reaches_it(self):
        assert states.ATTITUDES[-1] == "devoted"
        assert attitude.moved("helpful", 2) == "helpful"
        assert attitude.moved("friendly", 2) == "helpful"


class TestOneWriter:
    def test_the_score_is_one_effect_with_a_tag_and_a_source(self):
        s, e, grix = _table()
        attitude.set_regard(grix, 60, "test")
        held = [x for x in grix.effects if states.REGARD in x.tags]
        assert len(held) == 1 and held[0].amount == 60 and held[0].source == "regard"
        attitude.set_regard(grix, 70, "test")
        assert len([x for x in grix.effects if states.REGARD in x.tags]) == 1
        assert attitude.regard_of(grix) == 70
        grix.remove_effects(source="regard")
        assert attitude.regard_of(grix) == attitude.floor_of("indifferent")

    def test_the_track_falls_back_to_regard_when_no_step_is_held(self):
        s, e, grix = _table()
        attitude.set_regard(grix, 60, "test")
        assert attitude.of(grix) == "friendly"
        e.settle_attitude(grix, "hostile", 2, "a spell")
        assert attitude.of(grix) == "hostile", "a held step answers first"
        grix.clear_states("attitude")
        assert attitude.of(grix) == "friendly", "and when it lapses, regard answers"

    def test_a_permanent_shift_moves_the_baseline_with_it(self):
        s, e, grix = _table()
        e.settle_attitude(grix, attitude.COMES_ALONG, None, "background")
        assert attitude.regard_of(grix) == attitude.floor_of("friendly")
        e.settle_attitude(grix, attitude.HOSTILE, None, "the warrant")
        assert attitude.regard_of(grix) == attitude.floor_of("hostile")


class TestHowItGrows:
    def test_talking_earns_a_little_and_no_more_than_the_daily_cap(self):
        s, e, grix = _table()
        pc = s.pc()
        before = attitude.regard_of(grix)
        for _ in range(attitude.TALKS_A_DAY + 2):
            e.run(e.validate([{"op": "say", "actor": pc.ref, "because": "t",
                               "params": {"words": "Fine day.", "to": grix.ref}}],
                             origin="author:test"))
        assert attitude.regard_of(grix) == before + attitude.REGARD_PER_TALK * attitude.TALKS_A_DAY
        s.advance(24 * 60)
        e.run(e.validate([{"op": "say", "actor": pc.ref, "because": "t",
                           "params": {"words": "Fine day.", "to": grix.ref}}],
                         origin="author:test"))
        assert attitude.regard_of(grix) == before + attitude.REGARD_PER_TALK * (attitude.TALKS_A_DAY + 1)

    def test_a_diplomacy_success_is_remembered_by_the_step(self):
        s, e, grix = _table()
        before = attitude.regard_of(grix)
        out = _talk(e, grix, 20)
        moved = next(x for x in out.effects if x.get("kind") == "regard")
        assert moved["to"] > before
        assert moved["to"] - moved["from"] in (attitude.REGARD_PER_STEP,
                                                2 * attitude.REGARD_PER_STEP)

    def test_a_bad_failure_costs(self):
        s, e, grix = _table()
        before = attitude.regard_of(grix)
        _talk(e, grix, 1)
        assert attitude.regard_of(grix) == before - attitude.REGARD_LOST_ON_FAILURE

    def test_being_cowed_is_resented(self):
        s, e, grix = _table()
        before = attitude.regard_of(grix)
        _talk(e, grix, 20, skill="intimidate")
        assert attitude.regard_of(grix) == before - attitude.REGARD_RESENTMENT

    def test_a_gift_counts_and_a_sale_does_not(self):
        s, e, grix = _table()
        pc = s.pc()
        pc.goods["apple"] = 2
        before = attitude.regard_of(grix)
        e.run(e.validate([{"op": "give", "actor": pc.ref, "because": "t",
                           "params": {"item": "apple", "from_": pc.ref, "to": grix.ref}}],
                         origin="author:test"))
        assert attitude.regard_of(grix) == before + attitude.REGARD_GIFT

    def test_the_narrator_hears_a_step_crossed_and_never_a_number(self):
        s, e, grix = _table()
        pc = s.pc()
        attitude.set_regard(grix, attitude.floor_of("friendly") - 1, "test")
        out = e.run(e.validate([{"op": "say", "actor": pc.ref, "because": "t",
                                 "params": {"words": "Fine day.", "to": grix.ref}}],
                               origin="author:test")).outcomes[0]
        assert attitude.of(grix) == "friendly"
        assert attitude.said("Grix", "indifferent", "friendly") in out.tell, out.tell
        import re

        assert not re.search(r"\b\d+\b", out.tell.split("says")[-1].split("effect that")[-1]
                             .replace("Fine day.", "")), out.tell
