"""Reloading a crossbow (CRB; feat loop b5-core, rules/reloading.py).

Measured before (feat loop b4-moves, Crossbow Mastery's not_yet): "a crossbow already fires
every iterative of a full attack for anyone and never provokes for its reload" — a level-8
fighter's light crossbow fired twice a round with no reload at all, and Rapid Reload and
Crossbow Mastery waived nothing. The book: loading a light crossbow is a move action, a
heavy one a full-round action; Rapid Reload makes them free and a move.
"""
from __future__ import annotations

from rules import reloading
from tests._board import new_turn
from tests.test_feats_b4_moves import _board, _pc, _run, _tells


def _xbow(kind="light-crossbow", feats=()):
    pc = _pc("fighter", level=8, feats=feats, weapons=(kind,))
    pc.equipped = kind
    pc.goods["crossbow bolts"] = 20
    return pc


def _shoot(e, **params):
    return _run(e, {"op": "attack", "actor": "pc", "target": "c1", "visibility": "hidden",
                    "params": params})


def _shots(res) -> int:
    return sum(len(o.blows or ()) for o in res.outcomes if o.op == "attack" and o.actor == "pc")


def test_a_light_crossbow_full_attack_is_one_bolt_until_rapid_reload():
    """BAB 8 gives two iteratives; without Rapid Reload the second needs a move action a
    full attack has no room for (Rapid Reload's Normal), with it the reload is free."""
    assert reloading.one_shot(_xbow(), "light-crossbow")
    assert len(_xbow().attack_plan("light-crossbow", True)) == 1
    rapid = _xbow(feats=("Rapid Reload (light crossbow)",))
    assert not reloading.one_shot(rapid, "light-crossbow")
    assert len(rapid.attack_plan("light-crossbow", True)) == 2


def test_a_shot_unloads_and_the_next_turns_shot_spends_the_move_to_load():
    pc = _xbow()
    s, e = _board(pc, ("thug", (12, 5)))
    _shoot(e)
    assert reloading.unloaded(pc, "light-crossbow")
    s.round += 1
    new_turn(s)
    res = _shoot(e)
    assert any(o.op == "reload" for o in res.outcomes), _tells(res)
    assert s.move_spent.get("pc") == s.round, "the reload was the move action"
    assert _shots(res) == 1


def test_a_heavy_crossbow_reload_is_the_whole_round():
    """"Loading a heavy crossbow is a full-round action": the turn after a shot is the
    reload, and the shot behind it is refused."""
    pc = _xbow("heavy-crossbow")
    s, e = _board(pc, ("thug", (12, 5)))
    _shoot(e)
    s.round += 1
    new_turn(s)
    res = _shoot(e)
    assert any(o.op == "reload" and o.status == "resolved" for o in res.outcomes)
    assert res.outcomes[-1].status == "refused", _tells(res)


def test_crossbow_mastery_reloads_any_crossbow_free():
    pc = _xbow("heavy-crossbow", feats=("Crossbow Mastery",))
    assert reloading.action(pc, "heavy-crossbow") == "free"
    assert len(pc.attack_plan("heavy-crossbow", True)) == 2
