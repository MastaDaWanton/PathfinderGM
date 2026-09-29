"""Lane B's four narrator checks: route_walked, land_described, bearing_invented,
road_claimed (gm/checks/, docs/fix-interfaces.md §2.1).

Each is detection in code with a targeted repair named in `fix_hint` — the shape that held
in World Bible — and, where a cut can mend it, a backstop. The replay cases are Bobby's
beats of 2026-09-28 (docs/playtest-2026-09-28.md, items 16, 17, 19, 20), run through the
checks exactly as the page showed them.
"""
from __future__ import annotations

import pytest

import replays
from gm.checks import BeatContext
from gm.checks import bearing_invented, land_described, road_claimed, route_walked
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene
from rules import places
from world.loader import load_cached

AURVANTIS = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = "bde94b038cba"


def _engine(at_name="the way in", at=""):
    s = Scene(location_id=VORMOOR)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=AURVANTIS)
    if not at:
        at = next(p.id for p in places.home_set(AURVANTIS.get(VORMOOR))
                  if p.name == at_name)
    e.place_party(at)
    return s, e


def _ctx(text, s, e, outcomes=(), reading=None, brief_facts=None, door="turn"):
    return BeatContext(
        door=door, text=text, player_text="", engine=e, scene=s, world=AURVANTIS,
        location=AURVANTIS.get(VORMOOR), reading=reading, outcomes=tuple(outcomes),
        tells=(), said=(), attribution=None, brief="", brief_facts=brief_facts or {},
        pull=None, was_at="", acting="", turn=1)


def _travel(effect, status="resolved"):
    return Outcome(intent_id="i1", op="travel", status=status, effects=[effect], tell="")


# --- route_walked ---------------------------------------------------------------------------

def test_a_walk_the_page_never_walks_is_found():
    """16.2: the engine walked the party through two places and the page arrived without
    passing either. The repair names each place and its own line, in order."""
    s, e = _engine()
    out = _travel({"kind": "biome", "went_by": ["the well", "the market"],
                   "went_by_about": [{"name": "the well", "about": "where the water is"}]})
    found = route_walked.find(_ctx("You arrive at the gate. It is quiet.", s, e, [out]))
    assert [f.kind for f in found] == ["route-not-walked"]
    assert "the well (where the water is); the market" in found[0].fix_hint
    walked = "You pass the well, where a queue has formed, and come out at the gate."
    assert route_walked.find(_ctx(walked, s, e, [out])) == []


def test_a_refused_travel_walks_nothing():
    s, e = _engine()
    out = _travel({"kind": "biome", "went_by": ["the well"]}, status="refused")
    assert route_walked.find(_ctx("Nothing moves.", s, e, [out])) == []


# --- land_described ------------------------------------------------------------------------

def test_walking_out_with_no_word_of_the_land_is_found():
    """19 (a): "With the current narration I would assume there was endless flat desert
    around me". A beat that leaves the settlement carries at least one word of the land
    the world describes, or it is repaired with the world's list."""
    s, e = _engine()
    out = _travel({"kind": "biome", "direction": "out"})
    bare = "You step past the last house. The morning is bright and the air is still."
    found = land_described.find(_ctx(bare, s, e, [out]))
    assert [f.kind for f in found] == ["land-not-described"]
    assert "farmland" in found[0].fix_hint or "badland" in found[0].fix_hint
    told = "Past the last house the farmland runs out toward black-rock canyons."
    assert land_described.find(_ctx(told, s, e, [out])) == []


def test_ground_that_is_not_there_is_found_and_cut():
    """19 (b), 20.2: pine and trees around a village whose land is farmland, mountain and
    ash-fields. The sentence is flagged with the ground that IS there, and the backstop
    cuts it."""
    s, e = _engine()
    out = _travel({"kind": "biome", "direction": "out"})
    text = ("The farmland opens past the last house. To the west the trees grow denser, "
            "dark with pine. The road runs on.")
    found = land_described.find(_ctx(text, s, e, [out]))
    absent = [f for f in found if f.kind == "absent-ground"]
    assert absent and absent[0].sentences == (
        "To the west the trees grow denser, dark with pine.",)
    assert "There is no forest here" in absent[0].fix_hint
    cut, notes = land_described.backstop(None, text, absent)
    assert "pine" not in cut and "farmland" in cut and notes


def test_in_town_trees_are_not_judged():
    """A green has trees. (b) judges only a beat outside or walking out, so the market's
    prose is never cut for a tree."""
    s, e = _engine("the green")
    text = "Under the trees of the green the elders sit."
    assert land_described.find(_ctx(text, s, e)) == []


# --- bearing_invented ----------------------------------------------------------------------

def test_a_compass_point_by_a_settlement_or_a_road_is_found_and_cut():
    """16.6 and 19: the world records no bearings; "a settlement to the north, reachable
    by journey: Dustgate" was invented, and so was "toward the west, where the coastal
    road begins". The backstop cuts the compass phrase and keeps the rest."""
    s, e = _engine()
    text = ("There is a settlement to the north, reachable by journey: Dustgate. "
            "The market is loud today.")
    found = bearing_invented.find(_ctx(text, s, e))
    assert [f.kind for f in found] == ["bearing-invented"]
    assert found[0].sentences == (
        "There is a settlement to the north, reachable by journey: Dustgate.",)
    assert "where each road leaves from" in found[0].fix_hint
    cut, _notes = bearing_invented.backstop(None, text, found)
    assert "north" not in cut and "Dustgate" in cut and "The market is loud" in cut


def test_a_city_s_quarter_is_not_a_bearing():
    s, e = _engine()
    assert bearing_invented.find(_ctx("You take the road through the east crossing.",
                                      s, e)) == []


def test_a_bearing_the_world_states_is_allowed():
    names = {"dustgate": "north"}
    assert bearing_invented.invented("Dustgate lies to the north.", names) == []
    assert bearing_invented.invented("Dustgate lies to the south.", names) == ["south"]


# --- road_claimed --------------------------------------------------------------------------

def test_a_road_the_party_never_took_is_found():
    """20.5 and 17: the page put the party on "the road toward Dustgate" while the engine
    held it at the way in. No journey, no road head: flagged with where the party is and
    where that road starts."""
    s, e = _engine()
    text = "You set out along the road to Dustgate, the village at your back."
    found = road_claimed.find(_ctx(text, s, e))
    assert [f.kind for f in found] == ["road-claimed"]
    assert "the way in" in found[0].fix_hint and "starts from the outskirts" in found[0].fix_hint
    cut, _ = road_claimed.backstop(None, text, found)
    assert cut == ""


def test_the_road_s_own_head_and_a_journey_are_not_claims():
    s, e = _engine()
    e._journeyed = ""
    e.run(e.validate([{"op": "travel", "actor": s.pc().ref, "because": "t",
                       "params": {"place": "the road to Dustgate"}}], origin="author:test"))
    if e.here().name != "the road to Dustgate":
        pytest.skip("stopped on the way; the walk is covered elsewhere")
    assert road_claimed.find(_ctx("You stand on the road to Dustgate.", s, e)) == []
    s2, e2 = _engine()
    journey = Outcome(intent_id="i1", op="journey", status="resolved",
                      effects=[{"kind": "journey", "to": "x"}], tell="")
    assert road_claimed.find(_ctx("You set out along the road to Dustgate.", s2, e2,
                                  [journey])) == []
    fact = "The road to Dustgate leaves from the outskirts."
    assert road_claimed.find(_ctx(fact, s2, e2)) == []


# --- the replay corpus ---------------------------------------------------------------------

needs_bobby = pytest.mark.skipif(not replays.available(),
                                 reason="the Bobby corpus is not on this disk")


@needs_bobby
def test_bobby_turn_7_invented_bearings_are_found():
    """Turn 7's signposts: north to Dustgate, west to Grotburrow, "toward the west, where
    the coastal road begins". Three sentences, every one an invention."""
    s, e = _engine()
    rec = replays.turn(7)
    found = bearing_invented.find(_ctx(replays.beat_text(rec), s, e,
                                       rec["plan"]["outcomes"]))
    assert found and len(found[0].sentences) >= 3, found


@needs_bobby
def test_bobby_turn_8_road_and_bearing_found():
    """Turn 8: "To the north … the road toward Dustgate is a straight, punishing line of
    white stone", with the engine holding the party at the way in."""
    s, e = _engine()
    rec = replays.turn(8)
    ctx = _ctx(replays.beat_text(rec), s, e, rec["plan"]["outcomes"])
    assert road_claimed.find(ctx), "the road toward Dustgate"
    assert bearing_invented.find(ctx)


@needs_bobby
def test_bobby_turn_9_pine_and_the_road_to_grotburrow_are_found():
    """Turn 9: "crushed pine and damp earth" in a forest Vormoor does not have, and a
    stranger's "The road to Grotburrow isn't for the faint of heart" with no journey
    begun — the owner's own example of a road claimed (20.5).

    Stood where the fixed engine would hold the party: the forest move is refused now
    (`absent_ground`), so Bobby is still out at the crossroads he walked to on turn 7."""
    s, e = _engine(at=f"{VORMOOR}~farmland:@the-crossroads")
    rec = replays.turn(9)
    ctx = _ctx(replays.beat_text(rec), s, e, rec["plan"]["outcomes"])
    kinds = {f.kind for f in land_described.find(ctx)}
    assert "absent-ground" in kinds
    pine = next(f for f in land_described.find(ctx) if f.kind == "absent-ground")
    assert any("pine" in sentence for sentence in pine.sentences)
    assert road_claimed.find(ctx)


@needs_bobby
def test_bobby_turn_5_prose_over_the_fixed_move_says_no_land():
    """Turn 5 now walks OUT of the village (test_b_travel). Its recorded prose — salt,
    timber, dust, the coast — carries not one word of the land the world describes, which
    is exactly what the land check exists to catch on the walk out."""
    s, e = _engine()
    out = _travel({"kind": "biome", "direction": "out"})
    found = land_described.find(_ctx(replays.beat_text(replays.turn(5)), s, e, [out]))
    assert [f.kind for f in found] == ["land-not-described"]
