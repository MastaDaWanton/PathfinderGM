"""Leaving is never narrated as arriving (item 16.4).

Measured on the Bobby playtest, 2026-09-28, turn 5: the move went from the market out to
the way in — out of the village — and the page said "The dusty road stretches out behind
you" and "the gates of Vormoor open to receive you". Nothing compared the prose's
direction with the move's.
"""
from __future__ import annotations

import pytest

import replays
from gm.checks import direction

from _a_truth import MARKET, WAY_IN, context, scene_at

corpus = pytest.mark.skipif(not replays.available(),
                            reason="the Bobby corpus is not on this disk")


def _move(frm, to, **extra):
    return [{"intent_id": "i1", "op": "travel", "status": "resolved", "tell": "",
             "effects": [dict({"kind": "biome", "place": to, "was_place": frm}, **extra)]}]


@corpus
def test_both_arriving_sentences_are_flagged_on_the_way_out():
    r = replays.case("leave-village-stopped")["record"]
    agent, _ = scene_at(WAY_IN)
    got = direction.find(context(agent, replays.beat_text(r),
                                 outcomes=replays.outcomes(r), was_at=MARKET))
    assert [f.kind for f in got] == ["direction-reversed"]
    assert len(got[0].sentences) == 2
    assert any("open to receive you" in s for s in got[0].sentences)
    assert any("stretches out behind you" in s for s in got[0].sentences)


@corpus
def test_the_same_text_on_an_inward_move_is_not_flagged():
    r = replays.case("leave-village-stopped")["record"]
    agent, _ = scene_at(MARKET)
    assert direction.find(context(agent, replays.beat_text(r),
                                  outcomes=_move(WAY_IN, MARKET), was_at=WAY_IN)) == []


def test_the_effects_own_direction_is_read_first():
    agent, _ = scene_at(MARKET)
    text = "You leave Vormoor behind you and walk on."
    inward = _move("x~urban:the-well", MARKET, direction="in")
    assert direction.find(context(agent, text, outcomes=inward)) != []
    assert direction.find(context(agent, text, outcomes=_move(
        "x~urban:the-well", MARKET, direction="along"))) == []


def test_across_the_worlds_the_settlements_own_name_and_scale_are_read(worlds):
    """No world's words in the rule: the settlement's own name and its scale word."""
    from rules.bestiary import instantiate  # noqa: F401 — the world's scene is enough
    from _a_truth import scene_at as at

    row = (worlds.play.get("settlements") or [])[0]
    location = worlds.get(row["id"])
    agent, _ = at("", world=worlds, location=location)
    text = f"The gates of {location.name} open to receive you."
    out = _move(f"{location.id}~urban:the-market", f"{location.id}~urban:the-way-in")
    got = direction.find(context(agent, text, outcomes=out))
    assert got and got[0].sentences == (text,)


def test_the_backstop_cuts_the_reversed_sentences():
    agent, _ = scene_at(WAY_IN)
    text = "You reach the way in. The gates of Vormoor open to receive you. What now?"
    ctx = context(agent, text, outcomes=_move(MARKET, WAY_IN), was_at=MARKET)
    kept, notes = direction.backstop(ctx, text, direction.find(ctx))
    assert kept == "You reach the way in. What now?"
