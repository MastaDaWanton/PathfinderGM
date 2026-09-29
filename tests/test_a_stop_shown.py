"""A stop the engine rolled is shown as a stop (item 16.3).

Measured on the Bobby playtest, 2026-09-28, turn 5: the walk out was stopped by the
street check (`met: "patrol"`, "The watch comes down the road at the way in, two of them,
looking at faces. You get no further."), and the page turned it into scenery: "the
watchmen are making their rounds". No check read `met`.
"""
from __future__ import annotations

import pytest

import replays
from gm.checks import stop_shown

from _a_truth import MARKET, WAY_IN, context, scene_at

corpus = pytest.mark.skipif(not replays.available(),
                            reason="the Bobby corpus is not on this disk")

_MET = [{"intent_id": "i1", "op": "travel", "status": "resolved", "effects": [
    {"kind": "biome", "place": WAY_IN, "was_place": MARKET, "met": "patrol"}],
    "tell": "The way there ran through the well. You are at the way in now. The watch "
            "comes down the road at the way in, two of them, looking at faces. You get no "
            "further. Left behind: Drenn Ironvale."}]


@corpus
def test_the_patrol_written_as_background_is_flagged():
    r = replays.case("leave-village-stopped")["record"]
    assert replays.outcomes(r)[0]["effects"][0]["met"] == "patrol"
    agent, _ = scene_at(WAY_IN)
    got = stop_shown.find(context(agent, replays.beat_text(r),
                                  outcomes=replays.outcomes(r), was_at=MARKET))
    assert [f.kind for f in got] == ["stop-not-shown"]
    assert any("making their rounds" in s for s in got[0].sentences)


@pytest.mark.parametrize("shown", [
    "Two of the watch step into your path at the way in. 'Where to?' one asks.",
    "The watch stops you at the way in and looks you over.",
    "You get no further than the way in: the watch is there.",
])
def test_a_stop_on_the_page_is_not_flagged(shown):
    agent, _ = scene_at(WAY_IN)
    assert stop_shown.find(context(agent, shown, outcomes=_MET, was_at=MARKET)) == []


def test_the_backstop_puts_the_engines_meeting_after_the_first_sentence():
    agent, _ = scene_at(WAY_IN)
    text = ("You come to the way in. The watchmen are making their rounds. "
            "What do you do?")
    ctx = context(agent, text, outcomes=_MET, was_at=MARKET)
    kept, notes = stop_shown.backstop(ctx, text, stop_shown.find(ctx))
    assert kept.startswith("You come to the way in. The watch comes down the road at "
                           "the way in, two of them, looking at faces. You get no further.")
    assert stop_shown.find(context(agent, kept, outcomes=_MET, was_at=MARKET)) == []


def test_a_walk_that_met_nobody_is_not_judged():
    agent, _ = scene_at(WAY_IN)
    quiet = [dict(_MET[0], effects=[dict(_MET[0]["effects"][0], met="")])]
    assert stop_shown.find(context(agent, "The watchmen make their rounds.",
                                   outcomes=quiet, was_at=MARKET)) == []
