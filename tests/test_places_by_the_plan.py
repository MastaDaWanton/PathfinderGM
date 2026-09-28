"""A plan may found a place and walk into it in the same turn.

docs/declared-not-guessed.md, the places door (2026-09-26). The user's ruling: the
mechanism is free, the outcome is not — places must keep being created for travel,
questing and discovery; the prose door stays, and the planner's `found` is added to it.
Measured before this: a plan that founded "The Tarred Rope" and travelled to it was
refused — validation checks the whole list before any of it runs, and the travel named a
place that did not exist yet — and a live plan wrote the `travel` BEFORE its own `found`.
`spawn` solved the same gap for people by projecting the refs an earlier intent mints.
"""
from __future__ import annotations

import pytest

from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id


@pytest.fixture
def engine():
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=1), world=WORLD)
    e.place_party()
    return e


FOUND = {"op": "found", "params": {"name": "The Tarred Rope", "kind": "tavern"}}
WALK = {"op": "travel", "params": {"place": "the tarred rope"}}


@pytest.mark.parametrize("plan", [[FOUND, WALK], [WALK, FOUND]],
                         ids=["found-then-walk", "walk-written-first"])
def test_the_plan_founds_a_place_and_walks_into_it(engine, plan):
    res = engine.run(engine.validate([dict(i) for i in plan]))
    assert [o.op for o in res.outcomes] == ["found", "travel"]
    assert engine.here().name == "The Tarred Rope"


def test_a_place_nothing_founds_is_still_refused_with_the_fix_named(engine):
    with pytest.raises(IntentError, match="found it first"):
        engine.validate([{"op": "travel", "params": {"place": "The Nowhere Inn"}}])


def test_the_projection_does_not_outlive_the_plan(engine):
    engine.validate([dict(FOUND), dict(WALK)])
    with pytest.raises(IntentError):
        engine.validate([{"op": "travel", "params": {"place": "The Tarred Rope"}}])


def test_a_building_hangs_off_the_street_not_off_the_room_you_stand_in(engine):
    """Measured live 2026-09-26: "I head for the stables" from inside a shrine made "the
    stables … off the shrine". A settlement kind goes off the nearest place under the
    sky; the guildhall here is indoors and hangs off the town."""
    engine.run(engine.validate([{"op": "travel", "params": {"place": "the guildhall"}}]))
    assert engine.here().name == "the guildhall"
    res = engine.run(engine.validate([
        {"op": "found", "params": {"name": "the stables", "kind": "stables"}}]))
    assert "off the guildhall" not in res.outcomes[0].tell, res.outcomes[0].tell
    stables = next(p for p in engine.places() if p.name == "the stables")
    from rules import places

    parent = places.find(engine.places(), stables.parent)
    assert parent is None or not places.is_indoors(parent.id)


def test_a_travel_with_nowhere_in_it_takes_the_place_the_player_named(engine):
    """Measured live 2026-09-26, twice in two runs: "I go looking for the bathhouse" came
    back as a travel with no place, and the engine answered "Nobody moves: where to?".
    Filled from the player's words, validation then names the fix: found it first."""
    from gm import judgement

    raw = judgement.fill_empty_travel([{"op": "travel", "params": {}}],
                                      "I go looking for the bathhouse.", engine.scene)
    assert raw[0]["params"]["place"] == "the bathhouse"
    with pytest.raises(IntentError, match="found it first"):
        engine.validate(raw)
    # Two kinds named, or none: left alone.
    for said in ("I look for a bookseller.", "I go from the market to the tavern."):
        assert judgement.fill_empty_travel([{"op": "travel", "params": {}}], said,
                                           engine.scene) == [{"op": "travel", "params": {}}]
