"""Somebody's house is a place a plan can found (owner's turn, 2026-10-01).

"I take the key and head to the house 3 streets over." The plan was right — `found` the
house off the back streets, then `travel` to it — and the engine answered "There is no
such kind of place as 'house'". The settlement table knew the tannery, the counting house
and the cistern, and not a house. The walk was refused, the prose walked the player there
anyway, and the beat ended "You are still at the Velvet Veil." Reproduced on the scratch
copy of the owner's campaign with the same line: `found` refused, `travel` refused, and
the refusal came at resolution, so the plan never got its retry.
"""
from __future__ import annotations

import pytest

from rules import floorplan, places
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc
from world import loader

VYRAKON = "5bbd0c40345f"
WORLD = loader.load_cached("fixtures/pangrella-campaign.json")


def _room():
    s = Scene(location_id=VYRAKON)
    s.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(s, Dice(seed=3), world=WORLD)
    return s, engine


def _run(engine, ops):
    return engine.run(engine.validate(ops, origin="author:test")).outcomes


def test_the_owners_walk_founds_the_house_and_goes_there():
    s, engine = _room()
    out = _run(engine, [
        {"op": "found", "actor": "pc", "params": {"name": "the house", "kind": "house"}},
        {"op": "travel", "actor": "pc", "params": {"place": "the house"}},
    ])
    assert out[0].effects and out[0].effects[0]["is"] == "house", out[0].tell
    assert out[1].effects, out[1].tell
    assert s.at.endswith("the-house"), s.at


def test_a_house_founded_from_a_back_room_stands_on_the_street():
    """The scratch replay of the owner's turn, from "the chamber" (a room founded off
    the Velvet Veil, no kind of its own): the house was founded off the chamber — a house
    inside a back room — because a kindless founded room has no floor plan and read as
    open sky, which stopped the climb out to the street."""
    s, engine = _room()
    out = _run(engine, [
        {"op": "found", "actor": "pc", "params": {"name": "the Velvet Veil", "kind": "tavern"}},
        {"op": "travel", "actor": "pc", "params": {"place": "the Velvet Veil"}}])
    out += _run(engine, [
        {"op": "found", "actor": "pc", "params": {"name": "the chamber"}},
        {"op": "travel", "actor": "pc", "params": {"place": "the chamber"}}])
    assert all(o.effects for o in out), [o.tell for o in out]
    assert s.at.endswith("the-chamber"), s.at
    tavern = out[0].effects[0]["id"]
    out = _run(engine, [{"op": "found", "actor": "pc",
                         "params": {"name": "the house", "kind": "house"}}])
    parent = out[0].effects[0]["parent"]
    assert "the-chamber" not in parent and parent != tavern, parent


def test_a_house_has_a_roof_and_a_stair():
    """Without a floor-plan row it fell to OPEN: a house under the sky, no upstairs."""
    shape = places.shape_of_kind("house", "urban")
    assert shape.ceiling == floorplan.LOW


@pytest.mark.parametrize("word", ["cottage", "home", "the townhouse", "residence"])
def test_the_words_people_use_for_a_house_are_a_house(word):
    assert places.kind_named(word) == "house"
    assert places.known_kind(word)


def test_any_settlement_has_houses():
    """No scale to check: a village has houses as surely as a city."""
    assert places.fits_here("house", WORLD.get(VYRAKON)) == ""


def test_a_kind_nobody_has_heard_of_is_refused_before_the_plan_is_spent():
    """Refused at validation, with the vocabulary, so the planner's next attempt can use
    it; at resolution it reached nobody who could act on it."""
    _s, engine = _room()
    with pytest.raises(IntentError) as err:
        engine.validate([{"op": "found", "actor": "pc",
                          "params": {"name": "the airship", "kind": "airship"}}],
                        origin="author:test")
    assert err.value.code == "no_such_kind"
    assert "house" in str(err.value) and "tavern" in str(err.value)


def test_the_generated_towns_are_not_redrawn():
    """A house is founded, never drawn: SETTLEMENT_PLACES — what every world's towns are
    drawn from — has no house row, so no existing town changes."""
    assert "house" not in places.KINDS
    assert not any(row[0] == "the house" for row in places.SETTLEMENT_PLACES)
