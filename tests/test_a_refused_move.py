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
