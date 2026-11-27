"""The 5-foot step's three rules (CRB, Combat; feat loop b5-core, rules/stepping.py).

Measured before: a one-square move was a step by its length alone
(`reactions.provoked_by_move`), so a fighter who walked 30 feet past a thug and then one
square more out of its reach drew no swing; a step after a step was free; and a step into
rubble provoked nothing. The book: "you can't take a 5-foot step in the same round that you
move any distance ... You can't take a 5-foot step into difficult terrain", and a step
"never provokes".
"""
from __future__ import annotations

from rules import stepping
from tests.test_feats_b4_moves import _board, _pc, _run, _tells


def _move(e, square, actor="pc"):
    return _run(e, {"op": "move", "actor": actor, "params": {"square": list(square)}})


def _swung_at(res) -> bool:
    return any(o.op == "attack" and o.actor != "pc" for o in res.outcomes)


def test_a_first_step_out_of_reach_provokes_nothing():
    pc = _pc("fighter", weapons=("longsword",))
    s, e = _board(pc, ("thug", (6, 5)))
    res = _move(e, (4, 5))
    assert not _swung_at(res), _tells(res)
    assert stepping.walked(s, "pc") == "step"


def test_one_square_more_after_a_walk_is_movement_and_provokes():
    """Walk up beside the thug, then one square away: the square is not a step, and leaving
    the thug's reach draws its swing."""
    pc = _pc("fighter", weapons=("longsword",))
    s, e = _board(pc, ("thug", (9, 5)))
    _move(e, (8, 6))                          # 15 ft up to the thug: the move action
    assert stepping.walked(s, "pc") == "move"
    res = _move(e, (7, 7))                    # one square out of reach
    assert _swung_at(res), _tells(res)


def test_nothing_moves_after_the_rounds_step():
    pc = _pc("fighter", weapons=("longsword",))
    s, e = _board(pc, ("thug", (15, 15)))
    _move(e, (6, 5))
    res = _move(e, (9, 5))
    assert res.outcomes[-1].status == "refused" and res.outcomes[-1].code == "stepped", \
        _tells(res)
    assert s.positions["pc"][:2] == (6, 5)


def test_a_square_of_difficult_terrain_is_no_step_until_nimble_moves():
    """Into rubble beside the thug's reach: without the feat it is movement and leaving the
    reach provokes; Nimble Moves (CRB) "allows you to take a 5-foot step into difficult
    terrain"."""
    for feats, provokes in (((), True), (("Nimble Moves",), False)):
        pc = _pc("fighter", feats=feats, weapons=("longsword",))
        s, e = _board(pc, ("thug", (6, 5)))
        s.grid.difficult = {(4, 5)}
        res = _move(e, (4, 5))
        assert _swung_at(res) is provokes, (feats, _tells(res))


def test_pack_attack_steps_after_a_walk_beside_an_ally_with_the_feat():
    """Pack Attack (UC): beside an ally with the feat, after the first melee attack, "an
    immediate action to take a 5-foot step, even if you have otherwise moved this round"."""
    ally = _pc("fighter", feats=("Pack Attack",), weapons=("longsword",))
    ally.ref = "ally"
    pc = _pc("fighter", feats=("Pack Attack",), weapons=("longsword",))
    s, e = _board(pc, ("thug", (8, 5)), at=(5, 5), allies=[(ally, (6, 6))])
    _move(e, (7, 5))                                   # 10 ft: the move action
    s.swung["pc"] = s.round                            # the turn's melee blow, struck
    assert stepping.is_step(s, pc, (7, 5), (7, 6))
    res = _move(e, (7, 6))
    assert res.outcomes[-1].status == "resolved", _tells(res)
    assert s.swift_spent.get("pc") == s.round, "the step spends the immediate action"


def test_a_second_move_spends_the_standard_and_the_blow_after_it_is_refused():
    """CRB, Action Types: "You can take a move action in place of a standard action." Batch
    4 measured two moves and a blow in one turn, and backed the rule out because the reach
    refusal advised exactly that; b5-core changed the advice and landed the rule."""
    pc = _pc("fighter", weapons=("longsword",))
    pc.equipped = "longsword"
    s, e = _board(pc, ("thug", (15, 5)))
    _move(e, (9, 5))
    assert s.standard_spent.get("pc") != s.round
    _move(e, (14, 5))
    assert s.standard_spent.get("pc") == s.round
    res = _run(e, {"op": "attack", "actor": "pc", "target": "c1", "params": {}})
    assert res.outcomes[-1].status == "refused", _tells(res)


def test_a_step_after_a_draw_is_still_a_step_and_spends_no_standard():
    """A draw spends the move action and moves nobody, so the one square after it is the
    round's 5-foot step: no standard spent, no swing drawn."""
    pc = _pc("fighter", weapons=("longsword",))
    s, e = _board(pc, ("thug", (6, 5)))
    s.move_spent["pc"] = s.round                   # the draw's move action
    res = _move(e, (4, 5))
    assert not _swung_at(res), _tells(res)
    assert s.standard_spent.get("pc") != s.round
