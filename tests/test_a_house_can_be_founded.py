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


def _graft_before_2026_11_08(base, founded, at=""):
    """`places.with_founded` as it stood, kept to hold the rewrite to the same answer."""
    from dataclasses import replace

    minted = [p if isinstance(p, places.Place) else places.from_dict(p) for p in founded]
    out = {p.id: p for p in base}
    changed = True
    while changed:
        changed = False
        for m in minted:
            if m.id in out:
                continue
            if (m.parent in out) or (at and (m.id == at or str(at).startswith(m.id + "/"))):
                out[m.id] = m
                changed = True
    result = {}
    for pid, p in out.items():
        exits = list(p.exits)
        for q in out.values():
            if q.parent == pid and q.id != pid and q.id not in exits:
                exits.append(q.id)
        if p.parent and p.parent in out and p.parent not in exits:
            exits.append(p.parent)
        result[pid] = replace(p, exits=tuple(exits))
    return tuple(result.values())


def test_grafting_founded_places_is_not_quadratic_and_gives_the_same_answer():
    """Audit 2026-11-07: `with_founded` wired exits by asking, for every grafted place,
    every other grafted place whether it was a child — |places|² comparisons, on a call
    `Engine.places()` makes many times a turn. Measured on this set before the fix: 0.11 s a
    call at 1,200 founded rooms and 0.62 s at 3,000; 0.07 s at 3,000 after. The children
    are indexed once now; the places, their order and their exits are exactly what the
    old loop gave."""
    import time

    base = (places.Place(id="town:square", name="the square", terrain="urban"),
            places.Place(id="town:gate", name="the gate", terrain="urban",
                         exits=("town:square",)))
    founded, parents = [], ["town:square", "town:gate"]
    for n in range(3000):
        pid = f"town:house-{n}"
        founded.append({"id": pid, "name": f"house {n}", "terrain": "urban",
                        "parent": parents[n % len(parents)], "kind": "house"})
        parents.append(pid)
    founded.append({"id": "elsewhere:hut", "name": "a hut", "parent": "elsewhere:x"})
    assert places.with_founded(base, founded) == _graft_before_2026_11_08(base, founded)
    assert places.with_founded(base, founded, at="elsewhere:hut") == \
        _graft_before_2026_11_08(base, founded, at="elsewhere:hut")
    t = time.perf_counter()
    places.with_founded(base, founded)
    assert time.perf_counter() - t < 0.3
