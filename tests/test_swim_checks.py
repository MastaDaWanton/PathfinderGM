"""The Swim check in the open water beside a ship (`Engine.swim`), 2026-11-13.

Measured the day the sea's squares opened to anybody going over the side: a PC in the
water swam where they liked and never sank — no Swim check was rolled anywhere in the
engine (rules/water.py listed swimming as movement as open). CRB, Swim: "Make a Swim
check once per round while you are in the water"; calm DC 10, rough 15, stormy 20; fail
by 4 or less, no progress; by 5 or more, underwater.

2026-11-14, every water: until then only the sea beside a ship rolled it. A PC standing in
a lake (`~water:` ground) rolled nothing at all, beat after beat, and every Swim check in
the game was DC 10 or 20 — the rough row (DC 15) had nothing that could say it. And the
check was a d20 every beat even out of a fight, where the book lets you take 10.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from rules import states, water
from rules.activeeffect import ActiveEffect
from rules.intents import IntentError
from tests.test_map_fixtures import _move
from tests.test_sea_encounters import _beside, _deck_with


def _fight(s, *refs):
    """In a fight, where the book does not let a threatened swimmer take 10."""
    s.initiative = [(r, 10) for r in refs]
    s.turn = 0


def _in_the_water():
    s, e, pc, shark = _deck_with()
    g = s.grid
    start = next(p for p in sorted(g.water) if _beside(s, p))
    s.positions[pc.ref] = start
    s.positions.pop(shark.ref, None)
    _fight(s, pc.ref)
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


# --- every water, 2026-11-14 ---------------------------------------------------------------

def _in_a(ground="water", fight=True):
    """The PC standing in a whole wet place — a lake, or below its surface."""
    from tests.test_water import TOWN, _table

    s, e, pc = _table()
    e.place_party(f"{TOWN}~{ground}:the-approach")
    if fight:
        _fight(s, pc.ref)
    return s, e, pc


def test_a_whole_lake_asks_the_swim_check_the_sea_beside_a_ship_does():
    """Measured: a PC in a `~water:` place rolled no Swim check, ever — `Engine.swim` asked
    only the board's sea squares, and a lake's board had none (`Grid.water` was empty)."""
    from rules.engine import _drowning_ground

    s, e, pc = _in_a("water")
    g = s.grid
    assert g.water == {(x, y) for x in range(g.width) for y in range(g.height)} - g.blocked
    assert s.afloat(pc.ref)
    seen = []
    _face(e, 4, seen)
    told = e.swim()
    assert seen and "DC 10" in seen[0][0], seen
    assert pc.has_state(states.UNDER_WATER) and "goes under" in " ".join(told), told
    assert _drowning_ground(pc)


def test_a_failed_check_in_a_lake_refuses_the_move_and_swimming_costs_a_quarter():
    s, e, pc = _in_a("water")
    at = s.positions[pc.ref]
    nxt = next(p for p in sorted(s.grid.water) if abs(p[0] - at[0]) + abs(p[1] - at[1]) == 1)
    assert s.grid.reachable(at, 30, swims="over")[nxt] == 20
    _face(e, 7, [])
    e.swim()
    with pytest.raises(IntentError, match="Swim check"):
        _move(e, pc.ref, nxt)


def test_a_wet_place_with_no_board_laid_still_swims():
    s, e, pc = _in_a("water")
    s.grid = None
    s.positions.clear()
    seen = []
    _face(e, 12, seen)
    e.swim()
    assert seen and pc.swim_check_made is True


def test_below_the_surface_a_made_check_swims_on_under_and_a_bad_one_sinks():
    """In an `underwater` place there is no surface to come up to (that is a move to the
    place above): the old tell "fights back up to the surface and breathes" would have been
    a lie, and the going-under effect a second writer beside the ground's own clock."""
    s, e, pc = _in_a("underwater")
    _face(e, 10, [])
    told = " ".join(e.swim())
    assert "under the calm water" in told and "surface" not in told, told
    assert not pc.has_state(states.UNDER_WATER) and pc.swim_check_made is True
    _face(e, 3, [])
    told = " ".join(e.swim())
    assert "sinks" in told and pc.swim_check_made is False, told


def test_a_lake_the_party_is_not_at_rolls_nothing():
    """Somebody standing in a wet place the party is not at is not afloat HERE: their
    checks would be hidden rolls and tells about water nobody at the table can see."""
    s, e, pc = _in_a("water")
    other_lake = s.at.replace("the-approach", "the-edge")
    pc.at = other_lake
    s.positions.pop(pc.ref, None)
    assert not s.afloat(pc.ref)
    seen = []
    _face(e, 1, seen)
    assert e.swim() == [] and not seen
    assert pc.swim_check_made is None


class _World:
    """A world whose one place row says how rough its water is (World Bible ask 17)."""

    def __init__(self, place_id, water_said):
        from tests.test_water import WORLD

        self._real, self._id, self._said = WORLD, place_id, water_said

    def get(self, entity_id):
        entity = self._real.get(entity_id)
        return SimpleNamespace(places=[{"id": self._id, "water": self._said}]) \
            if entity is not None else None


def test_a_place_that_says_rough_water_is_dc_15_and_stormy_dc_20():
    """Measured: the DC was 10 or 20 and nothing else — `SWIM_DC["rough"]` was unread.
    CRB Aquatic Terrain: fast rivers are rough (15), whitewater rapids stormy (20)."""
    for said, dc in (("rough", 15), ("stormy", 20), ("calm", 10), ("nonsense", 10)):
        s, e, pc = _in_a("water")
        e.world = _World(s.at, said)
        seen = []
        _face(e, 30, seen)
        e.swim()
        assert f"DC {dc}" in seen[0][0], (said, seen)
    assert water.roughness(None, s.at, storm=True) == "stormy"


def test_out_of_a_fight_the_swimmer_takes_10_and_says_so_once():
    """CRB Swim: taking 10 is allowed when not threatened, "You can't take 10 on a Swim
    check in stormy water". Before, a calm lake out of any fight rolled a d20 every beat,
    and a +1 swimmer drowned on a 4 with nobody near them."""
    s, e, pc = _in_a("water", fight=False)
    mod = sum(m.value for m in pc.skill_modifiers("swim"))
    seen = []
    _face(e, 1, seen)
    told = e.swim()
    assert not seen, "taking 10 throws no die"
    assert pc.swim_check_made is (10 + mod >= 10) and told, told
    assert e.swim() == [], "the same result the next beat is not news"


def test_stormy_water_out_of_a_fight_still_rolls():
    s, e, pc = _in_a("water", fight=False)
    e.world = _World(s.at, "stormy")
    seen = []
    _face(e, 25, seen)
    e.swim()
    assert seen and "stormy" in seen[0][0] and "DC 20" in seen[0][0]
