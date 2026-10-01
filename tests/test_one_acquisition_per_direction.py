"""What comes in and what goes out are two questions, not one (item 13, 2026-09-30).

Measured on Sam's save: turn 7, "I pocket the coin and give them a piece of paper with my
name on it. "Remember me when you have a bone that needs setting."" The plan carried a
`give` of the paper to the cage owner, and `judgement.inject_goods` bowed out whenever ANY
`give` was present — so the lead coin Sam pocketed was never recorded, and his goods at
the end of the session held a scholar's outfit, herbs and a key, and no coin.
"""
from __future__ import annotations

from gm import judgement
from rules.dice import Dice
from rules.engine import Engine

from test_a_take_is_not_a_boast import _sam

TURN_7 = ("I pocket the coin and give them a piece of paper with my name on it. "
          "\"Remember me when you have a bone that needs setting.\"")
PLAN_7 = [{"op": "say", "params": {"words": "Remember me when you have a bone that needs "
                                            "setting.", "to": "c1"}},
          {"op": "give", "params": {"item": "paper_with_name", "to": "c1"},
           "because": "the player's words commit the turn to it"}]


def test_the_coin_is_recorded_beside_the_paper_given_away():
    scene = _sam("the cage owner")
    out = judgement.inject_goods([dict(r) for r in PLAN_7], TURN_7, scene)
    assert out[:2] == PLAN_7
    assert out[2]["op"] == "give" and out[2]["params"] == {"item": "coin", "to": "pc"}
    engine = Engine(scene, Dice(seed=1))
    engine.run(engine.validate(out))
    assert scene.pc().goods.get("coin") == 1


def test_a_direction_the_plan_already_filled_is_not_filled_twice():
    scene = _sam("the cage owner")
    plan = [{"op": "give", "params": {"item": "coin", "to": "pc"}}]
    assert judgement.inject_goods(list(plan), "I pocket the coin", scene) == plan
    # A give with neither `to` nor `from_` is the player's, as drop_unread_gifts reads it.
    bare = [{"op": "give", "params": {"item": "coin"}}]
    assert judgement.inject_goods(list(bare), "I pocket the coin", scene) == bare


def test_a_purchase_still_covers_both_directions():
    """"I pay the merchant for the rope" is the purchase's coin, never a merchant handed
    over — the reason the old rule bowed out on `buy`."""
    scene = _sam("the merchant")
    plan = [{"op": "buy", "params": {"item": "rope"}}]
    assert judgement.inject_goods(list(plan), "I pay the merchant for the rope", scene) == plan


def test_a_sale_still_bows_out():
    """"I sell the Yarow Elixir" matches the handing-over verbs; a give written here first
    left the satchel for nothing (the reason `sell` bows out)."""
    scene = _sam("the merchant")
    plan = [{"op": "sell", "params": {"item": "yarow elixir"}}]
    assert judgement.inject_goods(list(plan), "I sell the Yarow Elixir", scene) == plan
