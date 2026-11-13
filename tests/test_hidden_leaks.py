"""What the table shows of a creature the player has not found, and threat across levels.

Found 2026-11-11 while building the visual-polish mocks (branch mock/polish,
docs/mock/polish/build_data.py: Kesst at Zhilvarnia's gate, four goblins, one hidden by
Stealth behind the stone at (6,8)):

  * `/api/state`'s `initiative` listed the hidden goblin by name and score while `actors`
    left it out, and the turn order prints that list (play/static/js/table/02-state.js);
  * the lit reachable squares routed around the hidden goblin's square, so the one gap
    in the light at (7,8) was exactly where it stood;
  * the goblin on the wall-walk at (10,5), level 2 (ten feet up), "threatened" (9,5) and
    (9,6) on the ground below, because `reactions.threatened_by` answered flat squares.

The rule for the first two is one question, `awareness.player_locates`: the player sees
what the PC locates (`awareness.locates`, which is `knows.where` for a hidden creature).
Walking into an unseen creature has no rulebook sentence (AoN's Invisibility and Stealth
pages say nothing of it; checked 2026-11-11). The Paizo and EN World threads agree the
mover is blocked and learns "something" is there, so the move stops short of it, is
spent, and leaves a pinpoint on the square it bumped.
"""
from __future__ import annotations

from play import campaign as campaign_mod
from play import views
from rules import awareness, reactions, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.sheet import load_pc
from tests._places import stand_on


def _hide(scene, who):
    """The Hidden effect the engine's won Stealth check lays (`Engine._stealth_lands`)."""
    who.apply_effect(ActiveEffect(
        name="Hidden", kind="condition", key=awareness.SNEAKING_KEY,
        source=awareness.STEALTH_ORIGIN, origin=awareness.STEALTH_ORIGIN,
        duration="until-dismissed", tags=states.tags_for(awareness.SNEAKING_KEY),
        payload={"result": 30, "at": scene.at, "ends_when": dict(awareness.ENDS_ON_ATTACK),
                 "pace": "half"}))


def _board(goblin_at=(7, 5), corridor=False):
    s = Scene(location_id="5bbd0c40345f", grid=Grid(20, 20))
    if corridor:
        # A one-square corridor along row 5: the only way east is through the goblin.
        for x in range(2, 15):
            s.grid.blocked.update({(x, 4), (x, 6)})
    s.add(load_pc("fixtures/pc-kesst.json"), at=(5, 5))
    gob = instantiate("goblin", scene=s)
    s.add(gob, at=goblin_at)
    stand_on(s, "urban")
    s.clock_minutes = 12 * 60
    s.sides = {"us": ["pc"], "them": [gob.ref]}
    s.initiative = [("pc", 20), (gob.ref, 10)]
    s.round, s.turn = 1, 0
    _hide(s, gob)
    return s, Engine(s, Dice(seed=7)), gob


def _state(s):
    return views._state(campaign_mod.Campaign(
        id="hidden-leaks", world_source="fixtures/pangrella-campaign.json", scene=s, seed=7))


def test_the_turn_order_leaves_out_a_creature_the_player_has_not_found():
    """The mock's state listed the hidden goblin in `initiative` (name and score) and left
    it out of `actors`: the turn order printed what the map hid. Found, it is in both."""
    s, e, gob = _board()
    out = _state(s)["scene"]
    assert gob.ref not in [i["ref"] for i in out["initiative"]]
    assert gob.ref not in [a["ref"] for a in out["actors"]]
    awareness.pinpoint(s, s.pc(), gob, "spotted")
    out = _state(s)["scene"]
    assert gob.ref in [i["ref"] for i in out["initiative"]]
    assert gob.ref in [a["ref"] for a in out["actors"]]


def test_the_lit_squares_do_not_route_around_an_unseen_creature():
    """The mock lit every square within 30 ft but (7,8), where the hidden goblin stood: the
    gap in the light was its square. Lit as the player knows the board, it is lit."""
    s, e, gob = _board()
    lit = {(x, y) for x, y, *_ in views._grid_state(s)["reachable"]}
    assert (7, 5) in lit
    awareness.pinpoint(s, s.pc(), gob, "spotted")
    lit = {(x, y) for x, y, *_ in views._grid_state(s)["reachable"]}
    assert (7, 5) not in lit


def test_a_move_into_an_unseen_creatures_square_stops_short_and_finds_it():
    """Before: `_check_move` refused "(7, 5) is taken" — a free probe that named the
    hidden square and spent nothing. Now the walk stops beside it, the move is spent, and
    the PC has pinpointed what it walked into."""
    s, e, gob = _board()
    res = e.run(e.validate([{"op": "move", "actor": "pc", "because": "walks",
                             "params": {"square": [7, 5]}}]))
    at = tuple(s.positions["pc"][:2])
    assert at != (7, 5) and max(abs(at[0] - 7), abs(at[1] - 5)) == 1, at
    assert s.move_spent.get("pc") == s.round
    assert awareness.knows_where(s, s.pc(), gob)
    tell = " ".join(o.tell for o in res.outcomes if o.tell)
    assert gob.name not in tell and "something" in tell.lower(), tell


def test_a_move_through_an_unseen_creature_stops_where_it_bumps():
    """A corridor one square wide with the hidden goblin at (7,5): a walk to (9,5) was
    refused as having no route, telling the player something stood in the way and where.
    Now it walks to (6,5), bumps, stops and finds it."""
    s, e, gob = _board(corridor=True)
    e.run(e.validate([{"op": "move", "actor": "pc", "because": "walks",
                       "params": {"square": [9, 5]}}]))
    assert tuple(s.positions["pc"][:2]) == (6, 5)
    assert awareness.knows_where(s, s.pc(), gob)


def test_a_move_the_unseen_creature_is_not_in_the_way_of_goes_ahead():
    """The hidden goblin off to the side changes nothing about a walk that never meets it."""
    s, e, gob = _board(goblin_at=(7, 9))
    e.run(e.validate([{"op": "move", "actor": "pc", "because": "walks",
                       "params": {"square": [7, 5]}}]))
    assert tuple(s.positions["pc"][:2]) == (7, 5)
    assert not awareness.knows_where(s, s.pc(), gob)


def test_threat_across_levels_is_measured_on_the_body_standing_there():
    """The mock's goblin on the wall-walk at (10,5), level 2, "threatened" (9,5) on the
    ground, and `threatened_by` was flat: raised to level 3 (15 ft up) it still did. By
    `grid.distance_between`'s third axis a Medium body (two squares tall) at (9,5,0) is
    5 ft from the goblin at level 2, so Kesst there IS threatened; a Small one is 10 ft
    off, and at level 3 a Medium one is too. The wall-walk beside it stays in."""
    s, e, gob = _board()
    for y in range(20):
        s.grid.floor[(10, y)] = 2
        s.grid.floor[(11, y)] = 2
    s.positions[gob.ref] = (10, 5, 2)
    assert (9, 5) in reactions.threatened_by(s, gob.ref, "medium")
    small = reactions.threatened_by(s, gob.ref, "small")
    assert (9, 5) not in small and (9, 6) not in small, sorted(small)
    assert (11, 5) in small and (10, 6) in small
    for y in range(20):
        s.grid.floor[(10, y)] = s.grid.floor[(11, y)] = 3
    s.positions[gob.ref] = (10, 5, 3)
    high = reactions.threatened_by(s, gob.ref, "medium")
    assert (9, 5) not in high and (11, 5) in high, sorted(high)


def test_a_watcher_written_without_its_level_threatens_from_its_own_floor():
    """The first cut read a two-tuple anchor as level 0, so the goblin at (10,5) on the
    level-3 wall-walk, its position written (10, 5), was measured as standing on the
    ground: (9,5) below came back threatened and the wall-walk (11,5) beside it did not.
    A two-tuple is the floor there (`Engine._cannot_leave_the_ground`)."""
    s, e, gob = _board()
    for y in range(20):
        s.grid.floor[(10, y)] = s.grid.floor[(11, y)] = 3
    s.positions[gob.ref] = (10, 5)
    zone = reactions.threatened_by(s, gob.ref, "medium")
    assert (9, 5) not in zone and (11, 5) in zone, sorted(zone)


def test_the_reach_panel_does_not_key_a_creature_the_player_has_not_found(monkeypatch):
    """`_attack_slots`' `reach` is keyed by foe ref with the squares that strike it: the
    hidden goblin's ref and a ring of squares round (7,5) went to the page while the map
    hid it. Found, it is there."""
    s, e, gob = _board()
    c = campaign_mod.Campaign(id="hidden-leaks", world_source="fixtures/pangrella-campaign.json",
                              scene=s, seed=7)
    monkeypatch.setitem(campaign_mod._LIVE, c.id, c)
    assert gob.ref not in views._reach_from(s.pc())
    awareness.pinpoint(s, s.pc(), gob, "spotted")
    assert views._reach_from(s.pc()).get(gob.ref)
