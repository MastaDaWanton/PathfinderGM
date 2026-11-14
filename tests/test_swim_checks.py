"""The Swim check in the open water beside a ship (`Engine.swim`), 2026-11-13.

Measured the day the sea's squares opened to anybody going over the side: a PC in the
water swam where they liked and never sank — no Swim check was rolled anywhere in the
engine (rules/water.py listed swimming as movement as open). CRB, Swim: "Make a Swim
check once per round while you are in the water"; calm DC 10, rough 15, stormy 20; fail
by 4 or less, no progress; by 5 or more, underwater.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from rules import states, water
from rules.activeeffect import ActiveEffect
from rules.intents import IntentError
from tests.test_map_fixtures import _move
from tests.test_sea_encounters import _beside, _deck_with


def _in_the_water():
    s, e, pc, shark = _deck_with()
    g = s.grid
    start = next(p for p in sorted(g.water) if _beside(s, p))
    s.positions[pc.ref] = start
    s.positions.pop(shark.ref, None)
    return s, e, pc, shark, start


def _face(e, total, seen):
    def d20(mods, label="", visibility=""):
        seen.append((label, sum(m.value for m in mods), visibility))
        return SimpleNamespace(total=total)
    e.dice.d20 = d20


def test_a_made_check_swims_on():
    s, e, pc, _shark, _at = _in_the_water()
    seen = []
    _face(e, 10, seen)
    told = e.swim()
    assert pc.swim_check_made is True and "swims" in " ".join(told), told
    assert seen and "DC 10" in seen[0][0] and seen[0][2] == "hidden"


def test_failing_by_four_or_less_gets_nowhere_and_the_move_is_refused():
    s, e, pc, _shark, at = _in_the_water()
    _face(e, 6, [])
    told = e.swim()
    assert pc.swim_check_made is False and "no headway" in " ".join(told), told
    assert not pc.has_state(states.UNDER_WATER)
    back = _beside(s, at)
    with pytest.raises(IntentError, match="Swim check"):
        _move(e, pc.ref, back)


def test_failing_by_five_goes_under_onto_the_breath_clock_and_a_made_check_surfaces():
    from rules.engine import _drowning_ground

    s, e, pc, _shark, _at = _in_the_water()
    _face(e, 5, [])
    told = e.swim()
    assert pc.has_state(states.UNDER_WATER) and "goes under" in " ".join(told), told
    assert _drowning_ground(pc), "under the water is the drowning clock's ground"
    before = pc.held_breath_rounds
    s.advance(1)
    assert pc.held_breath_rounds > before
    _face(e, 12, [])
    told = e.swim()
    assert not pc.has_state(states.UNDER_WATER) and "surface" in " ".join(told), told


def test_a_storm_makes_it_stormy_water():
    s, e, pc, _shark, _at = _in_the_water()
    pc.apply_effect(ActiveEffect(name="a storm at sea", kind="situation", key="storm-at-sea",
                                 tags=states.tags_for("storm-at-sea"),
                                 duration="rounds", rounds_left=100))
    seen = []
    _face(e, 19, seen)
    e.swim()
    assert "stormy" in seen[0][0] and "DC 20" in seen[0][0]
    assert pc.swim_check_made is False                       # 19 against 20


def test_a_swimmer_makes_no_check_and_a_body_that_cannot_act_goes_under():
    s, e, pc, shark, at = _in_the_water()
    s.positions[shark.ref] = next(p for p in sorted(s.grid.water) if p != at)
    seen = []
    _face(e, 1, seen)
    pc.hp = -1
    pc.apply_hp_state()
    e.swim()
    assert not any(shark.name in label for label, *_ in seen), "a swim speed needs no check"
    assert pc.has_state(states.UNDER_WATER) and not seen, "a downed body is not rolled for"


def test_armour_check_penalty_applies_once():
    """The Pathfinder Swim skill lists Armor Check Penalty and does not double it."""
    s, e, pc, _shark, _at = _in_the_water()
    pc.add_buff("combat_mod", "armour_check", -4, source="test armour")
    assert pc.armour_check_penalty == -4
    seen = []
    _face(e, 10, seen)
    e.swim()
    plain = sum(m.value for m in pc.skill_modifiers("swim"))
    assert seen[0][1] == plain and any(m.value == -4 for m in pc.skill_modifiers("swim"))


def test_out_of_the_water_the_going_under_ends():
    s, e, pc, _shark, at = _in_the_water()
    _face(e, 1, [])
    e.swim()
    assert pc.has_state(states.UNDER_WATER)
    s.positions[pc.ref] = _beside(s, at)
    e.swim()
    assert not pc.has_state(states.UNDER_WATER) and pc.swim_check_made is None


def test_swimming_costs_a_quarter_of_speed_a_move():
    """CRB Swim: "a quarter of your speed as a move action"."""
    s, _e, _pc, _shark, at = _in_the_water()
    g = s.grid
    nxt = next(p for p in sorted(g.water) if abs(p[0] - at[0]) + abs(p[1] - at[1]) == 1)
    assert g.reachable(at, 30, swims="over")[nxt] == 20
    assert g.reachable(at, 30, swims="speed")[nxt] == 5
