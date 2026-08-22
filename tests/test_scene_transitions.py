"""Travel is the scene transition, and a transition sheds its cast.

The ghost this prevents, from the 2026-08-22 playtest: a gatekeeper wounded in the guild
yard travelled inside the scene to the forest — still in an initiative order that never
ended — and took a "holds back" NPC turn after every player turn for the rest of the
session. When the fiction then aimed attacks at forest strangers, every one landed on
him, because he was the only body the engine had.
"""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


@pytest.fixture
def yard():
    s = Scene(location_id="5bbd0c40345f")
    s.biome = "urban"
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="the gatekeeper"))
    s.add(instantiate("thug", scene=s, name="the bravo"))
    return s, Engine(s, Dice(seed=11))


def travel(engine, biome="forest", **params):
    return engine.run(engine.validate([
        {"op": "travel", "because": "she makes for the treeline",
         "params": {"biome": biome, **params}}]))


# --- departing --------------------------------------------------------------------------

def test_depart_removes_every_trace(yard):
    """Five structures name an actor — actors, zones, initiative, sides, the reaction
    ledger — and a removal that missed one would leave a ghost acting from it."""
    s, engine = yard
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"pc": ["pc"],
                                                      "them": ["c1", "c2"]}}}]))
    s.reacted["c1:aoo"] = 1
    gone = s.depart("c1")
    assert gone.name == "the gatekeeper"
    assert "c1" not in s.actors and "c1" not in s.zones
    assert all(r != "c1" for r, _ in s.initiative)
    assert "c1" not in s.sides["them"]
    assert not any(k.startswith("c1:") for k in s.reacted)


def test_depart_keeps_the_turn_on_the_same_creature(yard):
    """The turn pointer is an index into a list that just got shorter; without the fix a
    removal handed somebody else's turn to the wrong side of the fight."""
    s, engine = yard
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"pc": ["pc"],
                                                      "them": ["c1", "c2"]}}}]))
    order = [r for r, _ in s.initiative]
    current = s.current_ref()
    other = next(r for r in order if r not in ("pc", current))
    s.depart(other)
    assert s.current_ref() == current


def test_the_pc_cannot_be_departed(yard):
    s, _ = yard
    assert s.depart("pc") is None
    assert "pc" in s.actors


# --- travelling -------------------------------------------------------------------------

def test_travel_leaves_the_cast_behind(yard):
    """The gatekeeper does not follow you to the forest."""
    s, engine = yard
    r = travel(engine)
    assert list(s.actors) == ["pc"]
    assert s.biome == "forest"
    assert "Left behind: the gatekeeper, the bravo." in r.outcomes[0].tell


def test_travel_ends_the_fight_it_walks_away_from(yard):
    """The playtest's encounter never ended: the initiative order crossed a biome and the
    ghost in it acted every turn thereafter."""
    s, engine = yard
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"pc": ["pc"],
                                                      "them": ["c1", "c2"]}}}]))
    assert s.in_encounter
    r = travel(engine)
    assert not s.in_encounter
    assert s.initiative == [] and s.sides == {}
    assert "The fight is left behind." in r.outcomes[0].tell


def test_an_escort_named_in_with_comes_along(yard):
    """How the GM says somebody travels with the party — by ref or by name."""
    s, engine = yard
    travel(engine, **{"with": ["c2"]})
    assert set(s.actors) == {"pc", "c2"}


def test_the_dying_stay_where_they_fell_even_when_named(yard):
    """A dying escort is not an escort. They stay, whatever the intent says."""
    s, engine = yard
    s.actors["c2"].hp = 0
    travel(engine, **{"with": ["c2"]})
    assert set(s.actors) == {"pc"}


def test_travel_within_the_same_biome_sheds_nobody(yard):
    """Crossing town is not leaving it: the cast of an urban scene survives urban
    travel, and only a change of ground is a transition."""
    s, engine = yard
    travel(engine, biome="urban")
    assert set(s.actors) == {"pc", "c1", "c2"}
