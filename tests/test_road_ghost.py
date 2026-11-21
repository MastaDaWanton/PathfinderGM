"""Somebody met on the way and then walked away from, in the same list (fix/road-ghost).

Bench 2026-11-21, road-jason#1 (the travel-prose lane, Aurvantis): a poltergeist met on the
road to Caelholt stopped the journey. "I keep walking toward Caelholt" was read as the walk
on, and the plan added a move and an attack on the poltergeist, c17. The journey resolved
first and walked on past it; the poltergeist stayed where it was met (it is site bound,
120 ft), and the attack raised "attack: 'c17' is not on the board at resolution time". That
raise refused the WHOLE turn, the player's own walk with it, on both tries.

The creature had its square all along (people keep their square, 2026-09-28; asserted
below). What was missing was a refusal for an act on somebody the list itself had walked
away from. Every test runs once per export (fixes are world-agnostic).
"""
from __future__ import annotations

import pytest

from rules import bestiary, journey, ontheway


class _Got:
    def __init__(self, row):
        self.row, self.count = row, 1


@pytest.fixture
def ghost_on_the_road(monkeypatch):
    """The road's stretch check made to meet one poltergeist on day 2."""
    from tests.test_second_look_at_the_way_there import _force

    monkeypatch.setattr(ontheway, "road", lambda *a, **k: None)
    _force(monkeypatch, "creature", 2)
    row = bestiary.lookup("poltergeist")
    monkeypatch.setattr(ontheway, "_the_land", lambda *a, **k: _Got(row))


def _a_road(world):
    for row in world.play["settlements"]:
        for leg in journey.legs_from(world, row["id"]):
            if not leg.by_sea and leg.by not in ("sea", "river"):
                return row["id"], leg
    pytest.skip("no land road in this export")


def test_a_ghost_met_on_the_road_and_walked_past_refuses_the_blow_not_the_turn(
        worlds, ghost_on_the_road):
    """Bench road-jason#1: "a poltergeist met on the road to Caelholt could not be
    attacked: 'c17' is not on the board" — an IntentError at resolution that lost the
    player's walk on as well. The walk now happens and the blow is a printed refusal."""
    from rules.intents import IntentError
    from tests.test_hex_travel import _party

    town, leg = _a_road(worlds)
    s, e, pc = _party(worlds, town)
    first = e.run(e.validate([{"op": "journey", "actor": pc.ref,
                               "params": {"to": leg.to_name}}]))
    assert any(o.op == "journey" for o in first.outcomes)
    ghost = next(a for a in s.actors.values()
                 if "oltergeist" in a.name)
    # Met on the road, it stands on the board (people keep their square).
    assert ghost.ref in s.positions, (ghost.ref, s.positions)

    try:
        r = e.run(e.validate([
            {"op": "journey", "actor": pc.ref, "params": {"to": leg.to_name}},
            {"op": "attack", "actor": pc.ref, "target": ghost.ref}]))
    except IntentError as exc:
        pytest.fail(f"the turn was refused whole: {exc}")
    walk = next(o for o in r.outcomes if o.op == "journey")
    blow = next(o for o in r.outcomes if o.op == "attack")
    assert walk.status == "resolved", walk.tell
    assert ghost.ref not in s.actors
    assert blow.status == "refused" and "left them behind" in blow.tell, blow.tell


def test_the_ghost_can_still_be_struck_before_walking_on(worlds, ghost_on_the_road):
    """The other order is a real blow: met on the road, it can be attacked where it stands."""
    from tests.test_hex_travel import _party

    town, leg = _a_road(worlds)
    s, e, pc = _party(worlds, town)
    e.run(e.validate([{"op": "journey", "actor": pc.ref, "params": {"to": leg.to_name}}]))
    ghost = next(a for a in s.actors.values() if "oltergeist" in a.name)
    r = e.run(e.validate([{"op": "attack", "actor": pc.ref, "target": ghost.ref}]))
    blow = next(o for o in r.outcomes if o.op == "attack")
    assert blow.status != "refused", blow.tell
