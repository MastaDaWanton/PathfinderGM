"""A move the engine refused is not narrated as a move (item 17.5).

Measured on the Bobby playtest, 2026-09-28: "I walk to the nearest crossroads" (turn 6)
and "I take the path away from town" (turn 7). `found` and `travel` were refused both
times and the party stood at the way in both times; the page said "You are standing where
the paths diverge" and "You are now on the outskirts". The only check that fired caught
the word "gate".
"""
from __future__ import annotations

import pytest

import replays
from gm import checks
from gm.checks import refused_move

from _a_truth import APPROACH, MARKET, WAY_IN, context, people_named, scene_at

corpus = pytest.mark.skipif(not replays.available(),
                            reason="the Bobby corpus is not on this disk")


def _ctx(n, place=WAY_IN, **kw):
    r = replays.turn(n)
    agent, _ = scene_at(place, people_named("the watchman waving traffic through"))
    return context(agent, replays.beat_text(r), outcomes=kw.pop("outcomes",
                                                                 replays.outcomes(r)),
                   player=r["player"], reading=(r.get("plan") or {}).get("reading"), **kw)


@corpus
@pytest.mark.parametrize("case, quote", [
    ("crossroads-refused-but-moved", "You are standing where the paths diverge."),
    ("path-away-refused-but-moved", "You are now on the outskirts"),
])
def test_the_crossroads_and_path_away_beats_are_flagged(case, quote):
    """G2: refused-move-shown-as-moved flagged on both beats."""
    c = replays.case(case)
    outs = replays.outcomes(c["record"])
    assert {o["op"] for o in outs if o["status"] == "refused"} >= {"found", "travel"}
    got = refused_move.find(_ctx(c["turn"]))
    assert [f.kind for f in got] == ["refused-move-shown-as-moved"]
    assert any(quote in s for s in got[0].sentences)


@corpus
def test_the_same_prose_after_a_move_that_happened_is_not_flagged():
    """Turn 7's prose, had the walk out resolved: the engine moved them, so the prose may."""
    r = replays.turn(7)
    moved = [{"intent_id": "i1", "op": "travel", "status": "resolved", "effects": [
        {"kind": "biome", "place": APPROACH, "was_place": WAY_IN}], "tell": ""}]
    assert refused_move.find(_ctx(7, place=APPROACH, outcomes=moved, was_at=WAY_IN)) == []


@corpus
def test_no_other_beat_of_the_corpus_is_flagged():
    """The sweep: every beat with its own outcomes. Only the two measured beats flag."""
    flagged = []
    for t in replays.turns():
        if refused_move.find(_ctx(t["n"])):
            flagged.append(t["n"])
    assert flagged == [6, 7]


@pytest.mark.parametrize("sentence", [
    "You could walk to the crossroads from here.",
    "You will reach the road by noon if you go now.",
    "You do not reach the crossroads.",
    "Do you head for the road?",
    "You are in no hurry, and the watchman knows it.",
    "You are at the way in, and the road waits.",
])
def test_a_hedge_a_denial_a_question_and_here_are_not_moves(sentence):
    agent, _ = scene_at(WAY_IN)
    refused = [{"intent_id": "i1", "op": "travel", "status": "refused", "effects": [],
                "tell": "There is no the crossroads here to go to."}]
    assert refused_move.find(context(agent, sentence, outcomes=refused)) == []


def test_the_backstop_cuts_from_the_first_move_and_says_where_they_are():
    agent, _ = scene_at(MARKET)
    refused = [{"intent_id": "i1", "op": "travel", "status": "refused", "effects": [],
                "tell": "There is no the crossroads here to go to. From here you can reach "
                        "the well."}]
    text = ("The stalls are loud. You set off toward the crossroads. You reach it by "
            "noon. What do you do?")
    ctx = context(agent, text, outcomes=refused)
    found = refused_move.find(ctx)
    assert found and found[0].sentences[0] == "You set off toward the crossroads."
    kept, notes = refused_move.backstop(ctx, text, found)
    assert kept == "The stalls are loud. You are still at the market."
    assert "planner" not in kept and "From here you can reach" not in kept


def test_the_check_is_registered_for_the_plan_and_turn_doors():
    assert refused_move in checks.registered()
    assert refused_move.DOORS == frozenset({"plan", "turn"})


# --- leaving is a move; moving inside the place is not (the owner's save, 2026-10-01) ---

_HOUSE_REFUSED = [{"intent_id": "i2", "op": "travel", "status": "refused", "effects": [],
                   "tell": "There is no the house here to go to."}]


def _in_a_tavern():
    """Bobby in a tavern the plan founded under a name of its own, off the way in: the
    shape of the owner's save, on the fixture world."""
    agent, _ = scene_at(WAY_IN)
    e = agent.engine
    pc = e.scene.pc()
    out = e.run(e.validate([
        {"op": "found", "actor": pc.ref, "params": {"name": "the Copper Kettle",
                                                    "kind": "tavern"}},
        {"op": "travel", "actor": pc.ref, "params": {"place": "the Copper Kettle"}}],
        origin="author:test")).outcomes
    assert all(o.status == "resolved" for o in out), [o.tell for o in out]
    return agent


def _flags(agent, text):
    return refused_move.find(context(agent, text, outcomes=_HOUSE_REFUSED,
                                     was_at=agent.engine.scene.at))


@pytest.mark.parametrize("sentence", [
    # The first refused walk to the house, as it opened: the first cut of `claims` read
    # "you leave <here>" as naming where the party is, and had no `move`.
    "You leave the Copper Kettle, the air outside thick with woodsmoke.",
    "You move through the town with a deliberate pace.",
    # The second: a door shutting behind the player, and the rewrite's own dodge of
    # "You step out into the cooling evening".
    "The heavy door of the Copper Kettle thuds shut behind you.",
    "You stand out in the cooling evening, the key in your pocket.",
    "You move into the shadows of the nearby streets.",
    "You turn your back to the village and set off.",
    "You step out of the tavern into the night.",
])
def test_leaving_the_place_is_a_move(sentence):
    """Measured on the owner's save of 2026-10-01: two refused walks to "the house 3
    streets over". The first beat's draft left the tavern in its second sentence and the
    check's first claim was the arrival, five sentences on — so the backstop cut there
    and appended "You are still at <the tavern>." after the walk out of it, which shipped.
    In the two beats as they shipped, seven sentences walk the player out: the old
    `claims` caught none of them, and now catches five — "Each street takes you further
    from the tavern" and "You find the spot…" are left, but each comes after a caught one,
    so the cut removes them.
    On the committed corpus the new departures flag five more sentences, every one a
    real move, one of them on a refused turn the old check let through ("The heavy gates
    of … groan shut behind you")."""
    agent = _in_a_tavern()
    got = _flags(agent, sentence)
    assert got and got[0].sentences == (sentence,), sentence


@pytest.mark.parametrize("sentence", [
    "You leave her words hanging in the smoke of the tavern as you turn your back on her.",
    "You move toward the back of the room where the shadows are deeper.",
    "You walk to the bar and set a coin down.",
    "You reach the top of the stairs.",
    "You are at the counter, waiting.",
    "You walk into the Copper Kettle, out of the rain.",
    "You are in the tavern, by the fire.",
    "You reach for the knocker.",
    "You are standing before the man at the crates.",
])
def test_moving_inside_the_place_or_into_it_is_not_a_move(sentence):
    """The bar, the stairs, the back of the room, a person, and the place itself by its
    name or its kind: none is leaving it (Inform: only `going` changes the room; the
    things in it are reached without it). On the committed corpus this removes two
    flagged sentences, both standing still ("You are standing before the man…", "…in
    the shadow of the cart's canopy"); in the owner's save "you reach for the knocker"
    was a claim."""
    agent = _in_a_tavern()
    assert _flags(agent, sentence) == [], sentence


def test_the_backstop_cuts_at_the_door_not_after_the_walk():
    """The first beat's shape: the cut lands on the departure, and the fact follows the
    sentence before it — not a walk across town with "You are still at" after it."""
    agent = _in_a_tavern()
    text = ("The key is cold in your palm as you pocket it. You leave the Copper Kettle, "
            "the air outside thick with woodsmoke. You move through the town with a "
            "deliberate pace. Each street takes you further from the tavern. You reach "
            "the house, its windows dark. What do you do?")
    ctx = context(agent, text, outcomes=_HOUSE_REFUSED, was_at=agent.engine.scene.at)
    found = refused_move.find(ctx)
    assert found[0].sentences[0].startswith("You leave the Copper Kettle")
    kept, _ = refused_move.backstop(ctx, text, found)
    assert kept == ("The key is cold in your palm as you pocket it. "
                    "You are still at the Copper Kettle.")


def test_the_street_a_tavern_opens_off_is_outside_it():
    """A tavern founded off the market: standing in the market is having left it, though
    the tavern's parent is the market (`words_for_here(outside=False)`)."""
    agent, _ = scene_at(MARKET)
    e = agent.engine
    pc = e.scene.pc()
    e.run(e.validate([
        {"op": "found", "actor": pc.ref, "params": {"name": "the Copper Kettle",
                                                    "kind": "tavern"}},
        {"op": "travel", "actor": pc.ref, "params": {"place": "the Copper Kettle"}}],
        origin="author:test"))
    assert e.here().name == "the Copper Kettle" and "market" in e.here().parent
    assert _flags(agent, "You are standing in the market, the tavern behind you.")


_ANVIL = "I set the crate down on the ground and walk over toward the anvil."
_ANVIL_READ = {"actions": [{"act": "use", "object": "the ground", "target": "the crate"},
                           {"act": "go", "place": "the anvil"}]}


def test_a_walk_across_the_room_is_not_a_refused_journey():
    """Measured live on the 2026-10-03 batch, the first turn played on the merged branch:
    the reading said `go: the anvil`, the planner rightly made no travel of it, and with no
    move resolved this check took the reading's `go` for a refused one — "You move toward
    the anvil, the massive block of iron…" was cut and the beat ended "You are still at the
    smithy." An anvil is not on `_INSIDE`'s list and no fixed list holds every fitting, so
    the judge is the planner's own `movement_within`."""
    agent = _in_a_tavern()
    ctx = context(agent, "You move toward the anvil, the massive block of iron standing "
                         "like a monument in the heat.", player=_ANVIL, reading=_ANVIL_READ,
                  was_at=agent.engine.scene.at)
    assert refused_move.find(ctx) == []


def test_a_walk_out_of_the_place_is_still_caught_without_a_refusal():
    """The other side of the same door: the reading's `go` to the street, with no move
    resolved, is still a walk nobody made."""
    agent = _in_a_tavern()
    ctx = context(agent, "You leave the Copper Kettle and walk out into the street.",
                  player="I walk out into the street.",
                  reading={"actions": [{"act": "go", "place": "the street"}]},
                  was_at=agent.engine.scene.at)
    assert [f.kind for f in refused_move.find(ctx)] == ["refused-move-shown-as-moved"]
