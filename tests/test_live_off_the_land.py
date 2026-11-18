"""Living off the land and hunting (the owner's report of 2026-11-17, item 6: "no water or
wildlife in the forest").

Measured in the owner's save (jack, transcript 177, 183, 186): parched, out of water and in
the woods, "I search for a pond, spring or river", "I search for a source of water" and "I
search for a river" were read `search` three times. They built a Perception check, a herb
forage and a hunt for tracks, and none of them gave water: free water existed only in a
settlement's well (`Engine.water_at_hand`).

The book's rule is Survival's "get along in the wild" (CRB p.107): DC 10, hunting and
foraging feed and water you for a day, plus one more person for every 2 points over. The
reader now has a `fend` deed for it, the engine a `live_off_land` op, and a `hunt` that
draws an animal of the ground through the forage's creature pick (`gathering.draw_for`).
"""
from __future__ import annotations

from gm import acts_to_ops, interpret
from rules import harvest, survival
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

from _places import stand_on

ROW_177 = {"question": False, "claims": [], "actions": [
    {"act": "fend", "object": "a pond, spring or river",
     "span": "search for a pond, spring or river"}]}
HUNT = {"question": False, "claims": [], "actions": [
    {"act": "hunt", "object": "a deer", "span": "go hunting for a deer"}]}


def _wild(biome: str = "forest", seed: int = 1):
    s = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    stand_on(s, biome)
    return s, Engine(s, Dice(seed=seed))


def _parched(pc):
    """Jack's state at row 177: a day and a half without water, three thirst checks made."""
    pc.watered_minutes = 36 * 60
    pc.thirst_checks = 3
    pc.fed_minutes = 30 * 60
    pc.hunger_checks = 0


def _do(e, op, face):
    res = e.run(e.validate([{"op": op, "actor": "pc", "because": "t", "params": {}}],
                           origin="author:test"))
    assert res.awaiting is not None and "Survival" in res.awaiting["label"], res
    assert res.awaiting["dc"] == survival.GET_ALONG_DC
    return e.resume(face).outcomes[0]


def test_the_book_feeds_one_more_for_every_two_points_over_ten():
    """CRB p.107: "one other person for every 2 points by which your check result exceeds
    10"."""
    assert [survival.fed_by_the_land(t) for t in (9, 10, 11, 12, 13, 14, 20)] == \
        [0, 1, 1, 2, 2, 3, 6]


def test_living_off_the_woods_gives_a_parched_body_its_days_water_and_food():
    """Row 177's words, read `fend`: the table builds `live_off_land`, and a success
    waters and feeds the player for a day — the thirst count back to nothing."""
    s, e = _wild()
    pc = s.pc()
    _parched(pc)
    rows = acts_to_ops.table(ROW_177, s, sentence="I search for a pond, spring or river")
    assert [b["op"] for r in rows for b in r.intents] == ["live_off_land"]
    clock = s.clock_minutes
    out = _do(e, "live_off_land", 15)
    assert out.verdict == "success" and out.effects[0]["fed"] == ["pc"], out.tell
    assert pc.watered_minutes == 0 and pc.thirst_checks == 0 and pc.fed_minutes == 0
    # The hours the body managed: a parched one may stop short (`survival.pass_hours`).
    hours = out.effects[0]["hours"]
    assert 1 <= hours <= Engine.LIVE_OFF_LAND_HOURS and s.clock_minutes - clock == hours * 60
    assert "DC 10" in out.tell and "a day" in out.tell


def test_a_failed_check_finds_nothing_to_live_on():
    s, e = _wild()
    pc = s.pc()
    _parched(pc)
    pc.abilities["wis"] = 1          # Survival well under 10 on a natural 1
    out = _do(e, "live_off_land", 1)
    assert out.verdict == "failure" and out.effects[0]["fed"] == []
    assert pc.thirst_checks >= 3 and "Not enough water" in out.tell


def test_a_town_has_no_wild_to_live_off():
    """A settlement's water is its well (`water_at_hand`) and its food is bought: the act
    is refused with the reason, before any hour is spent."""
    s, e = _wild("urban")
    clock = s.clock_minutes
    res = e.run(e.validate([{"op": "live_off_land", "actor": "pc", "because": "t",
                             "params": {}}], origin="author:test"))
    out = res.outcomes[0]
    assert out.status == "refused" and "town" in out.tell and s.clock_minutes == clock


def test_a_hunt_finds_an_animal_of_the_ground_far_off_and_unaware():
    """The reader's `hunt` builds the `hunt` op; a success brings in animals of the forest through the
    encounter budget, far off, with no fight opened: the hunter found them first."""
    s, e = _wild()
    rows = acts_to_ops.table(HUNT, s, sentence="I go hunting for a deer")
    assert [b["op"] for r in rows for b in r.intents] == ["hunt"]
    out = _do(e, "hunt", 20)
    assert out.verdict == "success", out.tell
    refs = [r for fx in out.effects for r in (fx.get("refs") or ())]
    assert refs, out.tell
    for r in refs:
        block = harvest.block_of(s.actors[r]) or {}
        assert block.get("creature_type") == "animal" and s.zones[r] == "far", (r, block)
    assert not s.in_encounter and "finds game" in out.tell


def test_fend_and_hunt_are_the_readers_own_deeds_and_take_time():
    """Live 2026-11-18: as a closed `seeks` choice on `fend`, "I go hunting for game in the
    woods" was read water-and-food three times of three; the hunt is an act of its own."""
    assert {"fend", "hunt"} <= set(interpret.ACTS)
    assert interpret.ACT_COSTS["fend"] == interpret.ACT_COSTS["hunt"] == "takes_time"

def test_the_plans_own_looking_goes_when_the_reading_built_the_fend():
    """Row 183's plan wrote a herb forage and a Perception check for "a source of water";
    beside the reading's `live_off_land` they would be the same looking twice."""
    s, _e = _wild()
    rows = acts_to_ops.table(ROW_177, s, sentence="I search for a pond, spring or river")
    plan = [{"op": "forage", "actor": "pc", "params": {}},
            {"op": "drink", "actor": "pc", "params": {}},
            {"op": "check", "actor": "pc", "params": {"skill": "perception"}}]
    raw = acts_to_ops.apply(plan, rows, ROW_177, s)
    assert [r["op"] for r in raw] == ["live_off_land"], raw

