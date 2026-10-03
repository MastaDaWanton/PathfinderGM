"""The act→op table: the reading drives the ops (docs/structured-turn.md, lane F).

The owner, 2026-10-03: "we cant really depend i think on just layering mechanical detection
logic on top this will be an endless loop". Every live bug of that day on the forward side
was a regex misreading a sentence the reader had read right. These tests pin what the
READING does: a frame is handed in (`interpret.remember`, or straight to the table) — the
frames are the ones the live reader produced for these sentences on the owner's saves,
replayed 2026-10-03 — and the table, the engine's finders and the engine do the rest.
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops, interpret
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


@pytest.fixture(autouse=True)
def _no_readings(monkeypatch):
    monkeypatch.setattr(interpret, "_READINGS", {})


def _scene(*names):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    for name in names:
        s.add(instantiate("guildhand", scene=s, name=name))
    return s


def _ref(scene, name):
    return next(r for r, a in scene.actors.items() if a.name == name)


def _frame(*actions, question=False):
    return {"question": question, "actions": [dict(a) for a in actions], "claims": []}


def _turn(scene, said, frame, plan=None):
    """What the turn's chain does with the plan, given this reading."""
    rows = acts_to_ops.table(frame, scene, sentence=said)
    raw = acts_to_ops.apply(list(plan or [{"op": "narrate_only"}]), rows, frame, scene)
    return rows, acts_to_ops.order(raw, rows)


def _run(scene, raw):
    engine = Engine(scene, Dice(seed=1))
    return engine.run(engine.validate(raw)).outcomes


def _gives(raw):
    return [r for r in raw if isinstance(r, dict) and r.get("op") in ("give", "sell")]


# --- coin out of a container, and a thing set down ------------------------------------------

def test_coins_tipped_from_the_pouch_go_into_the_purse():
    """The owner's items save, turn 22: "I transfer the coins from the pouch into my coin
    purse." The model's coin give was rewritten as a PAYMENT out of the purse ("Kesst
    Vayr has no gp to give"), and `declare_emptying`'s regex had to learn "transfer".
    The reading — `take, object: the coins, target: the pouch` — says which way the coin
    goes: out of the pouch, into the player's hands, whatever the plan wrote."""
    scene = _scene("the smith")
    pc = scene.pc()
    rec = scene.hold_prop("pouch", pc.ref, owner=pc.ref)
    rec["contents"] = {"purse": {"gp": 5}, "goods": {}}
    pc.goods["pouch"] = 1
    said = "I transfer the coins from the pouch into my coin purse."
    frame = _frame({"act": "take", "object": "the coins", "target": "the pouch"})
    _, raw = _turn(scene, said, frame,
                   plan=[{"op": "give", "params": {"item": "gp", "count": 1, "from_": "pc"}}])
    assert _gives(raw) == [{"op": "give", "actor": "pc", "because": "the player took it",
                            "params": {"item": "coins", "to": "pc", "from_": "pouch"}}]
    _run(scene, raw)
    assert pc.purse.get("gp") == 5


def test_a_thing_set_down_goes_to_the_floor_not_to_the_smith():
    """Same turn: "I also drop the Brunt of the weight on the ground and leave it behind"
    was read `give, target: the Brunt of the weight` and planned `give actor=pc
    target=c13` — the smith gained a copy and the player kept theirs. With `drop` in the
    reader's vocabulary, the table sets it down from the pack, and the plan's give of the
    same thing to the smith is replaced, capital B and all."""
    scene = _scene("the smith")
    pc = scene.pc()
    pc.goods["brunt of the weight"] = 1
    smith = _ref(scene, "the smith")
    frame = _frame({"act": "drop", "object": "the Brunt of the weight",
                    "place": "the ground"})
    _, raw = _turn(scene, "I also drop the Brunt of the weight on the ground.", frame,
                   plan=[{"op": "give", "actor": "pc", "target": smith,
                          "params": {"item": "Brunt of the weight"}}])
    assert _gives(raw) == [{"op": "give", "actor": "pc", "because": "the player set it down",
                            "params": {"item": "brunt of the weight", "from_": "pc"}}]
    _run(scene, raw)
    assert "brunt of the weight" not in pc.goods
    assert not scene.actors[smith].goods


def test_the_crate_picked_back_up_then_the_coins_tipped_both_happen_in_order():
    """Live, the 2026-10-03 batch: "I pick the crate back up, then tip the coins from the
    pouch into my coin purse" — the reading had both takes, the plan was `narrate_only`,
    the prose lifted the crate and tipped the coins, and the engine moved neither,
    because every regex anchored on "I <verb>" and the second clause had no I."""
    scene = _scene("the smith")
    pc = scene.pc()
    scene.place_prop("crate", owner=pc.ref)
    rec = scene.hold_prop("pouch", pc.ref, owner=pc.ref)
    rec["contents"] = {"purse": {"sp": 7}, "goods": {}}
    pc.goods["pouch"] = 1
    frame = _frame({"act": "take", "object": "the crate"},
                   {"act": "take", "object": "the coins", "target": "the pouch"})
    _, raw = _turn(scene, "I pick the crate back up, then tip the coins from the pouch into "
                          "my coin purse", frame)
    assert [g["params"]["item"] for g in _gives(raw)] == ["crate", "coins"]
    _run(scene, raw)
    assert pc.goods.get("crate") == 1 and pc.purse.get("sp") == 7


def test_carrying_what_is_already_carried_takes_nothing():
    """2026-10-03, turn 73: "I take the crate to the man in the counting house" made a
    second crate out of the air. A take of a thing in the pack, from nowhere in
    particular, is carrying it — the pack is asked, not the verb."""
    scene = _scene()
    scene.pc().goods["crate"] = 1
    rows, raw = _turn(scene, "I take the crate to the man in the counting house.",
                      _frame({"act": "take", "object": "the crate"}))
    assert not _gives(raw)
    assert rows[0].note == "the crate is already carried"


def test_a_figure_of_speech_is_never_carried_or_handed_over():
    """Turn 52 of the items save: "I take the brunt of the weight and move it toward the
    storage area" put "brunt of the weight" in the pack; the market save's "I give a
    friendly wink" planned a give of "friendly wink". A slot whose head noun is not a
    thing a satchel holds (`judgement._is_a_thing`, the engine's stop-list) makes no op
    — and the plan's own give of the wink, which no act stands behind, is overruled."""
    scene = _scene("Thessaly")
    rows, raw = _turn(scene, "I take the brunt of the weight and move it.",
                      _frame({"act": "take", "object": "the brunt of the weight"}))
    assert not _gives(raw)
    frame = _frame({"act": "other", "object": "a friendly wink"},
                   {"act": "talk", "says": "just trying to start a conversation"})
    _, raw = _turn(scene, "I give a friendly wink and say \"just trying to start a "
                          "conversation\"", frame,
                   plan=[{"op": "give", "params": {"item": "friendly wink", "from_": "pc",
                                                   "to": _ref(scene, "Thessaly")}}])
    assert not _gives(raw)


# --- selling ---------------------------------------------------------------------------------

def test_a_quoted_deal_closes_the_sale_to_the_one_spoken_to():
    """Live on the merged 2026-10-03 batch: '"It's a deal. You can have the crate."' was
    the whole line, in quotation marks; `redact_speech` blanked it, `_CLOSES_SALE` never
    saw it, and the crate stayed in the pack while the smith pried its lid off. Then "I
    tell the smith, \\"It's a deal…\\"" redacted to "I tell the" and the buyer was lost.
    The reading — `sell, object: the crate, target: the smith` — needs neither regex."""
    scene = _scene("the smith")
    pc = scene.pc()
    pc.goods["crate"] = 1
    smith = _ref(scene, "the smith")
    frame = _frame({"act": "talk", "target": "the smith",
                    "says": "It's a deal. You can have the crate."},
                   {"act": "sell", "object": "the crate", "target": "the smith"})
    rows, raw = _turn(scene, "I tell the smith, \"It's a deal. You can have the crate.\"",
                      frame,
                      plan=[{"op": "give", "params": {"item": "gp", "count": 1,
                                                      "from_": "pc"}}])
    assert _gives(raw) == [{"op": "sell", "actor": "pc", "because": "the player sold it",
                            "params": {"item": "crate", "to": smith}}]
    assert acts_to_ops.declared(rows) == ["say"]
    _run(scene, raw)
    assert "crate" not in pc.goods and scene.actors[smith].goods.get("crate") == 1


def test_an_offer_is_a_haggle_unless_the_buyer_keeps_a_counter():
    """"I try to sell the crate to Korvu for coin" — Korvu, a labourer, said no in the
    fiction — and "I agree to sell the crate to the clerk" were both `sell` until the
    reader learned `offer`. An offer to somebody with no counter is a haggle (no op);
    the close is the sale (CircleMUD's shopkeeper buys what its trade takes; anybody
    else has to agree)."""
    scene = _scene("Korvu")
    scene.pc().goods["crate"] = 1
    rows, raw = _turn(scene, "I try to sell the crate to Korvu for coin",
                      _frame({"act": "offer", "object": "the crate", "target": "Korvu"}))
    assert not _gives(raw) and rows[0].note.startswith("an offer")
    _, raw = _turn(scene, "I agree to sell the crate to Korvu at 75% of its value",
                   _frame({"act": "sell", "object": "the crate", "target": "Korvu"}))
    sale = _gives(raw)[0]
    assert sale["op"] == "sell" and sale["params"]["to"] == _ref(scene, "Korvu")
    assert sale["params"]["accept"] > 0          # the player's own 75%, a number


def test_a_plan_sale_no_act_stands_behind_is_overruled():
    """The plan sold for an offer: an `offer` to a labourer builds no sale, and the
    model's own `sell` of the crate, which only a `sell` act could stand behind, goes."""
    scene = _scene("Korvu")
    scene.pc().goods["crate"] = 1
    _, raw = _turn(scene, "I try to sell the crate to Korvu for coin",
                   _frame({"act": "offer", "object": "the crate", "target": "Korvu"}),
                   plan=[{"op": "sell", "actor": "pc", "params": {"item": "crate"}}])
    assert not _gives(raw)


# --- handing over, paying, and what is not here ----------------------------------------------

def test_paying_an_amount_is_a_give_of_the_denomination():
    """The brothel, 2026-09-18: "I pay her ten gold" reached the engine as `sell
    gold_coins_10`. The reading's `give, object: ten gold, target: her` is a number and a
    denomination (`acts_to_ops.coin_amount`) — closed vocabulary, which code may read —
    and "her" is the one person the player is dealing with."""
    scene = _scene("Marra")
    frame = _frame({"act": "give", "object": "ten gold", "target": "her"})
    _, raw = _turn(scene, "I pay her ten gold", frame)
    assert _gives(raw)[0]["params"] == {"item": "gp", "count": 10, "from_": "pc",
                                        "to": _ref(scene, "Marra")}


def test_it_is_the_thing_the_sentence_already_named():
    """"I lift the lantern off the hook, then hand it to the boy": "it" is the object of
    the deed before it in the same frame — the frame's structure, not a guess."""
    scene = _scene("the boy")
    frame = _frame({"act": "take", "object": "the lantern", "target": "the hook"},
                   {"act": "give", "object": "it", "target": "the boy"})
    rows, raw = _turn(scene, "I lift the lantern off the hook, then hand it to the boy.", frame)
    assert [(g["params"]["item"], g["params"].get("to")) for g in _gives(raw)] == [
        ("lantern", "pc"), ("lantern", _ref(scene, "the boy"))]


def test_a_thing_set_down_and_left_behind_is_set_down_once():
    """The items save's last line, read live on 2026-10-03: "I also drop the Brunt of the
    weight on the ground and leave it behind" came back `drop: the Brunt of the weight`,
    then `drop: it` — the same brunt twice, and the engine would refuse the second into
    the prose ("not carrying"). One thing is parted with once; two payments stay two."""
    scene = _scene("the smith")
    pc = scene.pc()
    pc.goods["brunt of the weight"] = 1
    pc.purse = {"gp": 20, "sp": 10}
    rows, raw = _turn(scene, "I also drop the Brunt of the weight on the ground and leave "
                             "it behind.",
                      _frame({"act": "drop", "object": "the Brunt of the weight",
                              "place": "on the ground"}, {"act": "drop", "object": "it"}))
    assert [g["params"]["item"] for g in _gives(raw)] == ["brunt of the weight"]
    assert rows[1].note == "brunt of the weight is already parted with"
    _, raw = _turn(scene, "I pay him ten gold and give him five silver",
                   _frame({"act": "give", "object": "ten gold", "target": "him"},
                          {"act": "give", "object": "five silver", "target": "him"}))
    assert [(g["params"]["item"], g["params"]["count"]) for g in _gives(raw)] == [
        ("gp", 10), ("sp", 5)]


def test_nothing_found_is_the_turns_answer_and_nothing_is_invented():
    """"Where a slot cannot be resolved, the op is not invented" (docs/structured-turn.md).
    A sale of a thing the pack does not hold, and nothing else declared: the turn is the
    refusal, said, and no op is made for the engine to refuse into the narrator."""
    scene = _scene("the smith")
    rows, raw = _turn(scene, "I sell the lantern to the smith",
                      _frame({"act": "sell", "object": "the lantern", "target": "the smith"}))
    assert not _gives(raw)
    assert acts_to_ops.refusal(rows) == "Kesst Vayr is not carrying the lantern."
    # With anything else owed, the missing thing is a fact for the planner instead.
    rows, _ = _turn(scene, "I sell the lantern and ask the smith his name",
                    _frame({"act": "sell", "object": "the lantern"},
                           {"act": "talk", "target": "the smith", "says": "his name"}))
    assert acts_to_ops.refusal(rows) == ""
    assert acts_to_ops.unresolved(rows) == ["Kesst Vayr is not carrying the lantern"]


def test_the_plans_op_on_a_thing_the_reading_found_missing_goes_too():
    """The replay of the items save's last line on the new path (2026-10-03): the
    reading's `drop: the Brunt of the weight` found none in the pack — the new path had
    never minted one — and the plan's own `give actor=pc target=c13` of it stood, to be
    refused into the prose ("Kesst Vayr has no Brunt of the weight to give"). The
    reading named the thing; the table's answer for it is the turn's."""
    scene = _scene("the smith")
    smith = _ref(scene, "the smith")
    rows, raw = _turn(scene, "I also drop the Brunt of the weight on the ground.",
                      _frame({"act": "drop", "object": "the Brunt of the weight"}),
                      plan=[{"op": "give", "actor": "pc", "target": smith,
                             "params": {"item": "Brunt of the weight"}}])
    assert not _gives(raw)
    assert acts_to_ops.unresolved(rows) == ["Kesst Vayr is not carrying the Brunt of the weight"]


def test_nobody_by_that_name_is_said_not_guessed():
    scene = _scene("the smith")
    scene.pc().goods["crate"] = 1
    rows, raw = _turn(scene, "I give the crate to the abbess",
                      _frame({"act": "give", "object": "the crate", "target": "the abbess"}))
    assert not _gives(raw)
    assert rows[0].missing == "there is nobody here who is the abbess"


def test_no_reading_is_the_plan_alone():
    """A failed reading is a missing one: the plan stands as written, and nothing reads
    the words behind it (measured 2026-10-03: 0 failed readings in 220 bench lines and
    in all 22 turn rows of the owner's items save)."""
    scene = _scene("the smith")
    plan = [{"op": "give", "params": {"item": "crate", "to": "pc"}}]
    rows = acts_to_ops.table(None, scene, sentence="I pick up the crate")
    assert rows == []
    assert acts_to_ops.apply(plan, rows, None, scene) == plan
    assert acts_to_ops.apply(plan, rows, {"error": "timed out"}, scene) == plan


# --- the op names, and the order ---------------------------------------------------------------

def test_the_words_order_is_the_turns_order():
    """Inform's DM4 §34: parse and run one action at a time, because the second means
    something different once the first has happened. The plan's travel came first and
    the table's pick-up was appended after it: the crate would be looked for at the
    market. Put back in the words' order."""
    scene = _scene()
    scene.place_prop("crate", owner="pc")
    frame = _frame({"act": "take", "object": "the crate"},
                   {"act": "go", "place": "the market"})
    rows = acts_to_ops.table(frame, scene, sentence="I pick up the crate and go to the market")
    rows[1].ops = ["travel"]               # as `ops_for` makes it where the market exists
    raw = acts_to_ops.apply([{"op": "travel", "params": {"place": "the market"}}],
                            rows, frame, scene)
    assert [r["op"] for r in acts_to_ops.order(raw, rows)] == ["give", "travel"]


def test_built_ops_are_never_asked_of_the_model():
    """The `declared` block is the model's to fill (`prompts.turn_schema`); a give or a
    sale built whole here is not, or its required body would be merged in beside the
    table's (`GMAgent._merge_declared`) — the same thing moved twice."""
    scene = _scene("the smith")
    scene.pc().goods["crate"] = 1
    frame = _frame({"act": "sell", "object": "the crate", "target": "the smith"},
                   {"act": "insult", "target": "the smith"})
    rows = acts_to_ops.table(frame, scene, sentence="I sell the crate and insult the smith")
    assert acts_to_ops.declared(rows) == ["provoke"]
    assert acts_to_ops.built_ops(rows) == ["sell"]


# --- the reader's own structure ---------------------------------------------------------------

def test_one_deed_read_twice_is_merged_and_two_deeds_are_not():
    """3 of the 19 dev-bench misses of 2026-10-03: "I make camp and sleep until dawn"
    read `rest` then `rest, time: until dawn` — two rests in the turn. Merged when the
    slots agree; "I turn my back on him and tell the barkeep he smells" insults two
    people and stays two."""
    merged = interpret.merge_repeats([{"act": "rest"}, {"act": "rest", "time": "until dawn"}])
    assert merged == [{"act": "rest", "time": "until dawn"}]
    two = [{"act": "insult", "target": "him"},
           {"act": "insult", "target": "the barkeep", "says": "he smells"}]
    assert interpret.merge_repeats([dict(a) for a in two]) == two


def test_the_per_act_schema_offers_each_act_only_its_own_slots():
    """Probed 2026-10-03, six real lines: Ollama enforced the per-act `anyOf` on 6 of 6
    (memory: `contains` and `prefixItems` were 0 of 6, so a construct is probed before
    it is relied on). Each alternative: the span, the act as a const right after it — with
    the act last, the slot keys chose the act and "I look around" came back `claim` — and
    exactly that act's slots, required."""
    items = interpret.per_act_schema()["properties"]["actions"]["items"]["anyOf"]
    assert {a["properties"]["act"]["const"] for a in items} == set(interpret.ACTS)
    for alt in items:
        act = alt["properties"]["act"]["const"]
        assert list(alt["properties"])[:2] == ["span", "act"]
        assert set(alt["properties"]) == {"span", "act", *interpret.ACT_SLOTS[act]}
        assert alt["required"] == list(alt["properties"])
        assert alt["additionalProperties"] is False


def test_a_null_written_as_a_word_is_no_slot():
    """The per-act probe came back `target: "none"` on a gesture."""
    frame, _ = interpret.ground({"question": False, "claims": [], "actions": [
        {"span": "give a friendly wink", "act": "other", "target": "none",
         "object": "none", "place": "none"}]}, "I give a friendly wink, none the wiser")
    assert frame["actions"] == [{"act": "other"}]
