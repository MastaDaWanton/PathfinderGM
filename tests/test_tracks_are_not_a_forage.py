"""A search for tracks is not a forage (the register's deferred row, 2026-09-29).

Measured live twice on 2026-09-29, at the crossroads, and once more in the agent's own run:
"I search the crossroads for tracks, then head out" beside the outskirts chip was planned
as `forage` → `check` Survival → `travel`, and herbs went into the pack on a tracking check.
Replayed on 2026-09-30 in all three fixture worlds, no detector declared the forage — the
plan wrote it — so a forage the words do not declare, beside words about trail-signs, is
taken out of the plan by `judgement.inject_forage`; the Survival check stands (CRB p.107,
Survival, "Follow Tracks"). The declarer itself is narrowed to plant, herb, food and forage
words, and "gather" alone ("I gather my things") no longer orders an intent as a forage.
"""
from __future__ import annotations

import pytest

from gm import judgement

from test_suggestions_held_to_the_sheet import _market

TRACKS = [
    "I search the crossroads for tracks, then head out",
    "I search for tracks",
    "I look for tracks leading away from the road",
    "I search the ground for footprints",
    "I hunt for signs of the wolves",
    "I follow the trail into the trees",
]
FORAGES = [
    "I forage for mushrooms",
    "I gather some berries",
    "I search for herbs along the road",
    "I search the hedgerow for herbs",
    "I search the area for food",
    "I look for something to eat in the undergrowth",
]


@pytest.mark.parametrize("line", TRACKS)
def test_tracks_never_declare_a_forage(worlds, line):
    s, _ = _market(worlds)
    assert "forage" not in judgement.declared_ops(line, s, worlds), line
    assert judgement.inject_forage([], line, s) == []


@pytest.mark.parametrize("line", TRACKS)
def test_the_plans_own_forage_on_tracks_is_taken_out(worlds, line):
    """The live plan, op for op: the forage goes, the Survival check and the walk stay."""
    s, _ = _market(worlds)
    plan = [{"op": "forage", "actor": "pc", "params": {}},
            {"op": "check", "actor": "pc", "params": {"skill": "survival"}},
            {"op": "travel", "params": {"place": "the outskirts"}}]
    out = judgement.inject_forage([dict(r) for r in plan], line, s)
    assert [r["op"] for r in out] == ["check", "travel"], out


@pytest.mark.parametrize("line", FORAGES)
def test_plants_herbs_and_food_still_forage(worlds, line):
    s, _ = _market(worlds)
    assert judgement.declares_forage(line), line
    assert [r["op"] for r in judgement.inject_forage([], line, s)] == ["forage"]
    # And the plan's own forage on those words is left alone.
    plan = [{"op": "forage", "actor": "pc", "params": {}}]
    assert judgement.inject_forage(list(plan), line, s) == plan


def test_herbs_by_the_tracks_still_forage(worlds):
    """A forage the words DO declare stands even beside a trail."""
    s, _ = _market(worlds)
    line = "I follow the trail and gather herbs as I go"
    plan = [{"op": "forage", "actor": "pc", "params": {}}]
    assert judgement.inject_forage(list(plan), line, s) == plan


def test_gathering_my_things_is_not_ordered_as_a_forage(worlds):
    s, _ = _market(worlds)
    assert "forage" not in judgement._clause_ops("I gather my things", s, worlds)
    assert "forage" in judgement._clause_ops("I forage by the river", s, worlds)
