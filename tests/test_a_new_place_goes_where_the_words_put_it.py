"""A new place goes under the place the words put it in (item 9, the parent part).

Measured on the owner's 2026-09-30 save, turn_log row 102, Ledgerwarren in Aurvantis. At
the gate, the guard had just said there was "a place tucked down in the back streets",
and the player typed **"I head toward the back streets to find the Velvet Veil."** The
travel to the Veil was refused with a hint to found it first — a hint whose example had no
`parent` — and the plan founded it with none. `Engine._parent_place("")` defaults to where
the party stands, so the tell read **"the Velvet Veil is a place now, off the gate"**, one
hop from the gate and nowhere near the back streets.

The evidence now read, strongest first: the player's words ("the X in Y", or the place
they head for to find it); a person here who just said where; the kind's natural street;
and only then where the party stands.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules import places
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import from_dict

from test_a_take_is_not_a_boast import SAM
from test_suggestions_held_to_the_sheet import _market

ROW_102 = "I head toward the back streets to find the Velvet Veil."
PLAN_102 = [{"op": "found", "actor": "pc",
             "params": {"name": "the Velvet Veil", "kind": "tavern"}},
            {"op": "travel", "params": {"place": "the Velvet Veil"}}]
LEDGERWARREN = "c82025c86b89"


@pytest.fixture
def at_the_gate():
    from world.loader import load_cached

    world = load_cached("fixtures/aurvantis-campaign.json")
    s = Scene(location_id=LEDGERWARREN)
    s.add(from_dict(dict(SAM), ref="pc"))
    e = Engine(s, Dice(seed=2), world=world)
    gate = places.find(e.places(), "the gate")
    e.place_party(gate.id)
    return s, e, world


def test_row_102_founds_the_veil_in_the_back_streets(at_the_gate):
    s, e, world = at_the_gate
    plan = judgement.inject_found([dict(r) for r in PLAN_102], ROW_102, s, world)
    assert plan[0]["params"]["parent"] == "the back streets"
    res = e.run(e.validate(plan))
    founded = next(o for o in res.outcomes if o.op == "found")
    assert "off the back streets" in founded.tell, founded.tell
    veil = places.find(e.places(), "the Velvet Veil")
    assert places.find(e.places(), veil.parent).name == "the back streets"


def test_what_the_guard_said_puts_it_there_when_the_words_do_not(at_the_gate):
    s, e, world = at_the_gate
    s.conversation_log = [{"who": "c6", "name": "guard", "to": "you", "kind": "line",
                           "text": "There's a place tucked down in the back streets, "
                                   "just past the tannery."}]
    plan = judgement.inject_found([dict(r) for r in PLAN_102],
                                  "I go and find the Velvet Veil.", s, world)
    assert plan[0]["params"]["parent"] == "the back streets"


def test_the_words_x_in_y_name_the_parent(worlds):
    s, e = _market(worlds)
    hidden = next(p for p in e.places() if p.id != s.at and not places.is_indoors(p.id))
    line = f"I look for the Rusty Anchor, a tavern in {hidden.name}."
    plan = judgement.inject_found(
        [{"op": "found", "actor": "pc", "params": {"name": "the Rusty Anchor",
                                                   "kind": "tavern"}}], line, s, worlds)
    assert plan[0]["params"]["parent"] == hidden.name


def test_a_place_being_left_is_not_the_parent(worlds):
    s, e = _market(worlds)
    other = next(p for p in e.places() if p.id != s.at and not places.is_indoors(p.id)
                 and p.name not in ("the market",))
    line = f"I leave {other.name} and look for the Rusty Anchor."
    found = places.find(e.places(), s.at)
    plan = judgement.inject_found(
        [{"op": "found", "actor": "pc", "params": {"name": "the Rusty Anchor"}}],
        line, s, worlds)
    assert plan[0]["params"].get("parent") != other.name
    assert found is not None


def test_a_tavern_with_no_word_of_where_goes_on_its_natural_street(worlds):
    s, e = _market(worlds)
    # Standing somewhere other than the market, so the natural street is not "here".
    away = next((p for p in e.places() if not places.is_indoors(p.id)
                 and p.name not in ("the market", "the green")), None)
    if away is None:
        pytest.skip("nowhere outdoors but the market")
    e.place_party(away.id)
    plan = judgement.inject_found(
        [{"op": "found", "actor": "pc", "params": {"name": "the Rusty Anchor",
                                                   "kind": "tavern"}}],
        "I look for a tavern called the Rusty Anchor.", s, worlds)
    street = plan[0]["params"].get("parent")
    names = {p.name for p in e.places()}
    expected = next((n for n in ("the market", "the green") if n in names), None)
    assert street == expected


def test_where_the_party_stands_is_left_to_the_engines_default(worlds):
    s, e = _market(worlds)
    here = places.find(e.places(), s.at)
    plan = judgement.inject_found(
        [{"op": "found", "actor": "pc", "params": {"name": "Marra's stall"}}],
        f"I make Marra's stall in {here.name} my base.", s, worlds)
    assert "parent" not in plan[0]["params"]


def test_a_parent_the_plan_named_is_the_engines_to_resolve(worlds):
    s, e = _market(worlds)
    plan = [{"op": "found", "actor": "pc",
             "params": {"name": "the Rusty Anchor", "parent": "the outskirts"}}]
    assert judgement.fill_found_parent([dict(r) for r in plan], ROW_102, s, worlds) == plan
    copied = [{"op": "found", "actor": "pc", "params": {
        "name": "the Velvet Veil", "kind": "tavern",
        "parent": "<the place above it stands in or off>"}}]
    out = judgement.fill_found_parent(copied, ROW_102, s, worlds)
    assert "<" not in str(out[0]["params"].get("parent", ""))


def test_the_hint_asks_for_the_parent(at_the_gate):
    """The hint taught leaving `parent` out since 68fd6f0; it names it now."""
    s, e, world = at_the_gate
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "travel", "params": {"place": "the Velvet Veil"}}])
    assert '"parent":' in str(err.value)
    assert "where the player's words or the people here put it" in str(err.value)
