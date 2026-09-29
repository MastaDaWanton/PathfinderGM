"""The brief's wording is not printed as prose (item 17.6).

Measured on the Bobby playtest, 2026-09-28, turn 7: "There is a settlement to the north,
reachable by journey: Dustgate." — the ROADS OUT line's shape, sharing no 3-gram with the
brief, so an echo index would miss it. The label-colon shape occurred twice in the 32 prose
beats of the five saves on the machine, both times this defect.
"""
from __future__ import annotations

import pytest

import replays
from gm.checks import brief_verbatim

from _a_truth import WAY_IN, context, scene_at

corpus = pytest.mark.skipif(not replays.available(),
                            reason="the Bobby corpus is not on this disk")


@corpus
def test_the_signpost_beat_is_flagged_and_every_other_beat_is_clean():
    beats = [("opening", replays.opening()["text"])] + [
        (t["n"], b["text"]) for t in replays.turns() for b in t["beats"]]
    flagged = {n: brief_verbatim.flagged(text) for n, text in beats}
    flagged = {n: got for n, got in flagged.items() if got}
    assert list(flagged) == [7]
    assert [w for w, _ in flagged[7]] == [
        "There is a settlement to the north, reachable by journey: Dustgate.",
        "There is a settlement to the west, reachable by journey: Grotburrow."]


def test_a_registered_scaffold_phrase_is_caught_verbatim():
    agent, _ = scene_at(WAY_IN)
    text = ("The road bends away. These are the only settlements that can be reached, "
            "and only by journey. What now?")
    got = brief_verbatim.find(context(agent, text))
    assert got and got[0].sentences == ("These are the only settlements that can be "
                                        "reached, and only by journey.",)


@pytest.mark.parametrize("fine", [
    "The watchman waving traffic through is an Orc: old enough to have stopped counting.",
    "He says it plainly: the road is closed.",
    "The market is loud. You buy bread.",
])
def test_a_colon_in_ordinary_prose_is_not_the_brief(fine):
    assert brief_verbatim.flagged(fine) == []


def test_the_backstop_cuts_the_sentence():
    agent, _ = scene_at(WAY_IN)
    text = "The road forks. Reachable by journey: Dustgate. What do you do?"
    ctx = context(agent, text)
    kept, _ = brief_verbatim.backstop(ctx, text, brief_verbatim.find(ctx))
    assert kept == "The road forks. What do you do?"
