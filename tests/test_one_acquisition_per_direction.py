"""What comes in and what goes out are two questions, not one (item 13, 2026-09-30).

Measured on Sam's save: turn 7, "I pocket the coin and give them a piece of paper with my
name on it. "Remember me when you have a bone that needs setting."" The plan carried a
`give` of the paper to the cage owner, and `judgement.inject_goods` bowed out whenever ANY
`give` was present — so the lead coin Sam pocketed was never recorded, and his goods at
the end of the session held a scholar's outfit, herbs and a key, and no coin.

Since 2026-10-03 the reading drives these ops (gm/acts_to_ops.py; `inject_goods` is
retired, docs/structured-turn.md): each deed of the reading is its own op, so a give away
can never stand in for a thing taken, and a plan op for the same thing is replaced by the
reading's, never doubled.
"""
from __future__ import annotations

from gm import acts_to_ops
from rules.dice import Dice
from rules.engine import Engine

from test_a_take_is_not_a_boast import _sam

TURN_7 = ("I pocket the coin and give them a piece of paper with my name on it. "
          "\"Remember me when you have a bone that needs setting.\"")
PLAN_7 = [{"op": "say", "params": {"words": "Remember me when you have a bone that needs "
                                            "setting.", "to": "c1"}},
          {"op": "give", "params": {"item": "paper_with_name", "to": "c1"},
           "because": "the player's words commit the turn to it"}]
READING_7 = {"question": False, "claims": [], "actions": [
    {"act": "take", "object": "the coin"},
    {"act": "give", "object": "a piece of paper with my name on it", "target": "them"},
    {"act": "talk", "says": "Remember me when you have a bone that needs setting."}]}


def _read(said, scene, frame, plan):
    rows = acts_to_ops.table(frame, scene, sentence=said)
    return acts_to_ops.apply([dict(r) for r in plan], rows, frame, scene)


def test_the_coin_is_recorded_beside_the_paper_given_away():
    scene = _sam("the cage owner")
    out = _read(TURN_7, scene, READING_7, PLAN_7)
    # The paper is not in Sam's pack, so the reading's give of it is not built and the
    # plan's own give of it stands (an act of the reading, `give`, stands behind it).
    assert out[:2] == PLAN_7
    assert out[2]["op"] == "give" and out[2]["params"] == {"item": "coin", "to": "pc"}
    engine = Engine(scene, Dice(seed=1))
    engine.run(engine.validate(out))
    # Recorded in the PURSE since 2026-10-03 (item 3: "the coins" were a goods line
    # beside an empty purse). Nothing counted it out, so it is the one coin the engine
    # can vouch for — a single copper piece — and never the goods line "coin".
    assert scene.pc().purse.get("cp") == 1
    assert "coin" not in scene.pc().goods


def test_a_take_the_plan_already_made_is_not_made_twice():
    """The plan's own give of the coin is the same thing as the reading's: replaced, once."""
    scene = _sam("the cage owner")
    frame = {"actions": [{"act": "take", "object": "the coin"}]}
    for plan in ([{"op": "give", "params": {"item": "coin", "to": "pc"}}],
                 [{"op": "give", "params": {"item": "coin"}}]):
        out = _read("I pocket the coin", scene, frame, plan)
        assert [r["params"]["item"] for r in out if r["op"] == "give"] == ["coin"]


def test_a_purchase_still_covers_both_directions():
    """"I pay the merchant for the rope" is the purchase's coin, never a merchant handed
    over: the plan's buy stands under the reading's `buy`."""
    scene = _sam("the merchant")
    plan = [{"op": "buy", "params": {"item": "rope"}}]
    frame = {"actions": [{"act": "buy", "object": "the rope", "target": "the merchant"}]}
    assert _read("I pay the merchant for the rope", scene, frame, plan) == plan


def test_a_sale_is_one_op():
    """"I sell the Yarow Elixir" matched the handing-over verbs; a give written first left
    the satchel for nothing. The reading's sell is one op, and nothing gives it away."""
    scene = _sam("the merchant")
    plan = [{"op": "sell", "params": {"item": "yarow elixir"}}]
    frame = {"actions": [{"act": "sell", "object": "the Yarow Elixir"}]}
    out = _read("I sell the Yarow Elixir", scene, frame, plan)
    assert [r["op"] for r in out] == ["sell"]
