"""Things have an owner, a source and a destination (Lane A, docs/playtest-2026-10-03.md).

The owner's `items` save ended

    goods: {"brunt of the weight": 1, "crate": 1, "pouch": 1, "coins": 1}   purse: {}

after a session in which Kesst carried a crate to the counting house, sold it to the clerk
and pocketed the payment. Every line here is built from a sentence in that save (or the
market-talk save for the wink) and names what it measured. The design and its sources are
docs/items-have-owners.md.
"""
from __future__ import annotations

import json

import pytest

from gm import interpret, judgement, ledger
from rules import goods, holding, pricing
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


def _run(scene, raw):
    engine = Engine(scene, Dice(seed=1))
    return engine.run(engine.validate(raw)).outcomes


def _names(scene):
    return {r: a.name for r, a in scene.people.items()}


def _read(said, scene, *actions, plan=None, recent=()):
    """The turn's goods door with this reading (gm/acts_to_ops.py): since 2026-10-03 the
    reading drives these ops, and the regex readers these tests first pinned
    (`inject_goods`, `inject_sale`, `declare_drop`, `declare_emptying`) are retired."""
    from gm import acts_to_ops

    frame = {"question": False, "claims": [], "actions": [dict(a) for a in actions]}
    rows = acts_to_ops.table(frame, scene, sentence=said, recent=recent)
    return acts_to_ops.apply(list(plan or [{"op": "narrate_only", "params": {}}]),
                             rows, frame, scene)


# --- 1. a take is FROM somewhere, and a figure of speech is nothing ------------------------

def test_the_brunt_of_the_weight_is_not_a_thing():
    """Turn 52 of the items save: "I take the brunt of the weight and move it toward the
    storage area" minted an item called "brunt of the weight", which the player later
    dropped on a smithy floor. Read from the end, the head was "weight"; before "of" the
    head comes first, and a brunt is not something a satchel holds."""
    said = "I take the brunt of the weight and move it toward the storage area."
    # The reading of that line on the save: `take, object: the brunt of the weight`.
    out = _read(said, _scene(), {"act": "take", "object": "the brunt of the weight"},
                {"act": "go", "place": "the storage area"})
    assert not [i for i in out if i.get("op") == "give"]
    assert not judgement._is_a_thing("brunt of the weight")
    # The rule's own docstring example, which the old head-at-the-end reading got wrong.
    assert not judgement._is_a_thing("offer of a room")
    # And the measure words still hand the head on: a chunk of wood is wood.
    assert judgement._is_a_thing("chunk of wood")
    assert holding.head_of("a pouch of coins") == "pouch"


def test_a_take_moves_the_thing_out_of_the_hands_holding_it():
    """The crate the docks man was carrying was copied rather than moved: a `give crate
    to pc` with no `from_` came "from the world, which never runs out", and the man kept
    his. Now the holder is asked first, and a thing taken that was not handed over keeps
    its owner on the props ledger (Creation Kit's owner and stolen flag)."""
    scene = _scene("the man")
    man = scene.actors[_ref(scene, "the man")]
    man.goods["crate"] = 1
    out = _run(scene, [{"op": "give", "params": {"item": "crate", "to": "pc"}}])
    assert scene.pc().goods == {"crate": 1} and "crate" not in man.goods
    rec = scene.prop_named("crate")
    assert rec["held_by"] == "pc" and rec["owner"] == man.ref and rec["stolen"]
    assert "from the man, who did not hand it over" in out[0].tell


def test_a_persons_label_says_what_is_in_their_hands():
    """Playtest item 7: the narration hauled "the heavy pack onto your own shoulders… the
    merchant's eyes widen", and nothing recorded the pack as his. "The merchant with a
    heavy pack" is the narration's own statement about his hands, and a take of the pack
    is a take from him."""
    scene = _scene("merchant with a heavy pack")
    merchant = _ref(scene, "merchant with a heavy pack")
    out = _run(scene, [{"op": "give", "params": {"item": "pack", "to": "pc"}}])
    assert scene.pc().goods == {"heavy pack": 1}
    rec = scene.prop_named("heavy pack")
    assert rec["owner"] == merchant and rec["stolen"]
    assert "from the merchant with a heavy pack" in out[0].tell
    # Taken once: a second take does not find a second pack on his back.
    again = _run(scene, [{"op": "give", "params": {"item": "pack", "to": "pc"}}])
    assert "from merchant" not in again[0].tell


def test_a_thing_paid_for_is_handed_over_not_stolen():
    scene = _scene("the pedlar")
    pedlar = scene.actors[_ref(scene, "the pedlar")]
    pedlar.goods["lantern"] = 1
    scene.pc().purse = {"gp": 9}
    _run(scene, [{"op": "give", "params": {"item": "lantern", "to": "pc", "price": "7 gp"}}])
    assert scene.pc().goods == {"lantern": 1} and not pedlar.goods
    assert not (scene.prop_named("lantern") or {}).get("stolen")


def test_carrying_what_is_already_carried_mints_nothing():
    """Turn 73: "I take the crate to the man in the counting house" — taking a thing
    somewhere is carrying it, and with the crate already in the pack it made a second."""
    scene = _scene()
    scene.pc().goods["crate"] = 1
    said = "I take the crate to the man in the counting house who will buy it from me."
    out = _read(said, scene, {"act": "take", "object": "the crate",
                              "target": "the man in the counting house"})
    assert not [i for i in out if i.get("op") == "give"]


# --- 2 and 6. selling goods, at the book's half ---------------------------------------------

def test_a_carried_crate_sells_at_half_its_value_and_leaves_the_pack():
    """Turns 66–97: four turns of haggling over the crate resolved to `narrate_only`, and
    the save ended `goods: {"crate": 1, …}` after the sale. `_op_sell` only knew the
    crafting shelf. Core Rulebook p.140: an item sells for half its listed price; a crate
    lists none, so it is the app's bottom rung (`pricing.UNLISTED_GP`), halved."""
    scene = _scene("the clerk of the counting house")
    clerk = _ref(scene, "the clerk of the counting house")
    scene.pc().goods["crate"] = 1
    out = _run(scene, [{"op": "sell", "actor": "pc",
                        "params": {"item": "crate", "to": clerk}}])
    pc = scene.pc()
    assert "crate" not in pc.goods
    assert scene.actors[clerk].goods == {"crate": 1}, "sold into his hands, not vanished"
    assert goods.in_copper(pc.purse) == round(pricing.UNLISTED_GP * 50)
    assert out[0].tell.startswith(
        "Kesst Vayr sells the crate to the clerk of the counting house for ")


def test_the_players_seventy_five_percent_cannot_raise_the_price():
    """Turn 94: "I agree to sell the crate to the clerk at 75% of the crate's value"
    passed with no appraisal and no price. The share becomes `accept`, which — like the
    jar's — can only lower what the rule pays."""
    scene = _scene("the clerk of the counting house")
    clerk = _ref(scene, "the clerk of the counting house")
    scene.pc().goods["crate"] = 1
    raw = _read("I agree to sell the crate to the clerk at 75% of the crate's value.", scene,
                {"act": "sell", "object": "the crate", "target": "the clerk"})
    sell = next(r for r in raw if r["op"] == "sell")
    assert sell["params"]["to"] == clerk and sell["params"]["item"] == "crate"
    assert sell["params"]["accept"] == round(0.75 * pricing.UNLISTED_GP, 2)
    _run(scene, raw)
    assert goods.in_copper(scene.pc().purse) == round(pricing.UNLISTED_GP / 2 * 100)


def test_a_listed_thing_sells_at_half_its_core_price():
    scene = _scene("the smith")
    scene.pc().goods["lantern"] = 1
    _run(scene, [{"op": "sell", "actor": "pc",
                  "params": {"item": "lantern", "to": _ref(scene, "the smith")}}])
    assert scene.pc().purse == {"gp": 3, "sp": 5}, "a hooded lantern is 7 gp, half is 3½"


def test_an_offer_is_a_haggle_and_the_close_is_the_sale():
    """The three sale lines of the save, in order. An offer to somebody who keeps no
    counter is haggling and moves nothing — Korvu said no in the fiction — and the
    player's own close is the sale."""
    scene = _scene("Korvu", "the clerk of the counting house")
    scene.pc().goods["crate"] = 1
    quiet = [{"op": "narrate_only", "params": {}}]
    # The reader's `offer` (2026-10-03) is the haggle; `sell` is the close.
    for said, target in (("I try to sell the crate to Korvu for coin", "Korvu"),
                         ("I smile and flirt with the clerk and offer the crate for coin.",
                          "the clerk")):
        assert _read(said, scene, {"act": "offer", "object": "the crate",
                                   "target": target}) == quiet, said
    raw = _read("I agree to sell the crate to the clerk at 75% of the crate's value.", scene,
                {"act": "sell", "object": "the crate", "target": "the clerk"})
    assert [r["op"] for r in raw] == ["narrate_only", "sell"]
    # A close that names nothing takes the thing the last beats were about, and is
    # made to the person the player is talking to.
    scene.thread = {"ref": _ref(scene, "the clerk of the counting house")}
    raw = _read("It's a deal, he can have it.", scene,
                {"act": "sell", "object": "it", "target": "he"},
                recent=["You set the crate on the counter.", "The clerk eyes the crate."])
    assert raw[-1]["op"] == "sell" and raw[-1]["params"]["item"] == "crate"


# --- 3. coin is currency ---------------------------------------------------------------------

def test_the_coins_are_money_and_the_payment_is_not_counted_twice():
    """Turns 102–110: after the clerk "produces a small, leather pouch… The payment is
    yours", "I take the pouch and count the coins", "I pocket the coins" and "I transfer
    the coins from the pouch into my coin purse" — and the save ended with an item called
    "coins" beside an empty purse. Now the sale pays the purse, and the coins the
    narration then shows are that payment: said, and never paid again."""
    scene = _scene("the clerk of the counting house")
    clerk = _ref(scene, "the clerk of the counting house")
    pc = scene.pc()
    pc.goods["crate"] = 1
    _run(scene, [{"op": "sell", "actor": "pc", "params": {"item": "crate", "to": clerk}}])
    paid = dict(pc.purse)
    out = _run(scene, [{"op": "give", "params": {"item": "coins", "to": "pc"}}])
    assert pc.purse == paid and "coins" not in pc.goods
    assert "already in Kesst Vayr's purse" in out[0].tell
    note = ledger.note(out, turn=1, names=_names(scene))
    assert note is None, "acknowledging the payment again is not a memory"


def test_coins_nobody_counted_out_are_one_copper_once():
    scene = _scene()
    pc = scene.pc()
    _run(scene, [{"op": "give", "params": {"item": "coins", "to": "pc"}}])
    _run(scene, [{"op": "give", "params": {"item": "the coins", "to": "pc"}}])
    assert pc.purse == {"cp": 1} and not pc.goods, "the number is the engine's, once"


def test_paying_in_gp_works_once_the_purse_has_it():
    """Turn 106 planned `give gp 1 from pc` and got "Kesst Vayr has no gp to give",
    because the coins were in the goods."""
    scene = _scene("the smith")
    pc = scene.pc()
    pc.purse = {"gp": 2}
    smith = _ref(scene, "the smith")
    _run(scene, [{"op": "give", "params": {"item": "gp", "count": 1, "from_": "pc",
                                           "to": smith}}])
    assert pc.purse == {"gp": 1} and scene.actors[smith].purse.get("gp") == 1


def test_a_gold_ring_is_not_a_gold_piece():
    """`coin_named` read the metal alone, so "gold ring" was a denomination and a ring
    picked up went into the purse — item 3's mistake the other way round."""
    assert goods.coin_named("gold ring") == ""
    assert goods.coin_named("gold coins") == "gp"
    assert goods.coin_named("Khy'vyr gold piece") == "gp"


def test_coins_coming_in_are_not_a_payment_going_out():
    """Turn 110: the model's coin give for "I transfer the coins from the pouch into my
    coin purse" was rewritten by `inject_payment` into `give gp 1 from pc` — the coins
    would have LEFT the purse they were going into."""
    scene = _scene()
    raw = judgement.inject_payment(
        [{"op": "give", "params": {"item": "coins", "to": "pc"}}],
        "I pocket the coins and head for the side door.", scene)
    assert raw == [{"op": "give", "params": {"item": "coins", "to": "pc"}}]


# --- 4. a pouch holds things -------------------------------------------------------------------

def test_a_pouch_handed_over_carries_its_coin_and_empties_into_the_purse():
    """"Transfer the coins from the pouch into my coin purse" did nothing, and the pouch
    stayed in the goods beside the coins it had held. A container's contents ride on its
    props record; emptying it turns the coin back into the number (Circle's money
    object) and the empty pouch stays in the pack."""
    scene = _scene("the clerk of the counting house")
    clerk = scene.actors[_ref(scene, "the clerk of the counting house")]
    clerk.goods["pouch"] = 1
    rec = scene.hold_prop("pouch", clerk.ref, owner=clerk.ref)
    holding.contents(rec)["purse"]["gp"] = 12
    pc = scene.pc()
    _run(scene, [{"op": "give", "params": {"item": "pouch", "from_": clerk.ref,
                                           "to": "pc"}}])
    assert pc.goods == {"pouch": 1} and pc.purse == {}
    assert scene.prop_named("pouch")["held_by"] == "pc"
    said = "I transfer the coins from the pouch into my coin purse."
    raw = _read(said, scene, {"act": "take", "object": "the coins", "target": "the pouch"})
    out = _run(scene, raw)
    assert goods.in_copper(pc.purse) == 1200 and pc.goods == {"pouch": 1}
    assert holding.coin_in(scene.prop_named("pouch")) == 0
    assert "empties the pouch into their purse" in out[-1].tell
    assert ledger.note(out, turn=1, names=_names(scene))["text"] == \
        "you emptied the pouch into the purse"


def test_coin_set_down_lies_there_and_can_be_picked_up():
    """Dropping coin used to make it vanish: the purse went down and nothing lay
    anywhere. Set down, it is a pile holding its amount; picked up, the number again."""
    scene = _scene()
    pc = scene.pc()
    pc.purse = {"sp": 5}
    _run(scene, [{"op": "give", "params": {"item": "sp", "count": 3, "from_": "pc"}}])
    assert pc.purse == {"sp": 2} and holding.coin_in(scene.props_here()[0]) == 30
    _run(scene, [{"op": "give", "params": {"item": "the coins", "to": "pc"}}])
    assert pc.purse == {"sp": 5} and not scene.props_here()


# --- 5. a drop goes to the floor ------------------------------------------------------------------

def test_a_drop_goes_to_the_floor_not_to_the_smith():
    """Turn 110: "I also drop the Brunt of the weight on the ground and leave it behind"
    was planned as `give actor=pc target=c13` with no `from_`. The smith gained a new
    "Brunt of the weight", and the player kept "brunt of the weight", because the names
    differ only in case. Now: the words say drop, the name is matched the way people say
    it, and the thing lies here — and can be picked up again."""
    scene = _scene("the smith")
    smith = scene.actors[_ref(scene, "the smith")]
    pc = scene.pc()
    pc.goods["brunt of the weight"] = 1
    model = [{"op": "give", "actor": "pc", "target": smith.ref,
              "params": {"item": "Brunt of the weight"}}]
    said = ("I transfer the coins from the pouch into my coin purse.  I also drop the "
            "Brunt of the weight on the ground and leave it behind.")
    raw = _read(said, scene, {"act": "drop", "object": "the Brunt of the weight",
                              "place": "the ground"}, plan=model)
    assert raw == [{"op": "give", "actor": "pc", "because": "the player set it down",
                    "params": {"item": "brunt of the weight", "from_": "pc"}}]
    _run(scene, raw)
    assert "brunt of the weight" not in pc.goods and not smith.goods
    assert scene.props_here()[0]["name"] == "brunt of the weight"
    _run(scene, [{"op": "give", "params": {"item": "brunt of the weight", "to": "pc"}}])
    assert pc.goods == {"brunt of the weight": 1} and not scene.props_here()


def test_the_actor_of_a_give_to_somebody_else_is_the_giver():
    """The engine read `give actor=pc target=c13` as the smith taking one out of the air.
    Whoever acts, gives (Inform's giving action): the player's lantern goes to the smith,
    and the player no longer has it."""
    scene = _scene("the smith")
    smith = scene.actors[_ref(scene, "the smith")]
    scene.pc().goods["lantern"] = 1
    _run(scene, [{"op": "give", "actor": "pc", "target": smith.ref,
                  "params": {"item": "Lantern"}}])
    assert "lantern" not in scene.pc().goods and smith.goods == {"lantern": 1}


# --- 6/8. an overruled or empty give leaves no tell and no ledger line ---------------------------

def test_a_wink_is_not_handed_over_and_nothing_remembers_it():
    """The market-talk save, turn 4: "I give a friendly wink and say …" was read as
    `other` + `talk`; the reading overruled the `give`, the detector planned one anyway,
    "Kesst Vayr has no friendly wink to give" reached the narrator, and the ledger kept
    "handed something to Kesst Vayr"."""
    said = ('I give a friendly wink and say "just trying to start a conversation and see '
            'what is happening here."')
    scene = _scene()
    # The plan's give of the wink, which the detector used to add: no act stands behind it.
    out = _read(said, scene, {"act": "other", "target": "a friendly wink"}, {"act": "talk"},
                plan=[{"op": "give", "params": {"item": "friendly wink", "from_": "pc"}}])
    assert not [i for i in out if i.get("op") == "give"]
    # And the engine's own floor: a give of what the player does not carry is a refusal,
    # which the ledger does not remember as something that happened.
    res = _run(scene, [{"op": "give", "params": {"item": "friendly wink", "from_": "pc"}}])
    assert res[0].status == "refused"
    assert ledger.note(res, turn=4, names=_names(scene)) is None


# --- 7. tells and ledger lines name what moved -----------------------------------------------

def test_the_ledger_says_what_was_sold_and_to_whom():
    """The ledger's template read the first ref in the effect: a sale was remembered as
    "sold to Kesst Vayr" and every give as "handed something to …". No digits — the
    price is the tell's."""
    scene = _scene("the clerk of the counting house")
    clerk = _ref(scene, "the clerk of the counting house")
    scene.pc().goods["crate"] = 1
    out = _run(scene, [{"op": "sell", "actor": "pc", "params": {"item": "crate",
                                                                 "to": clerk}}])
    assert ledger.note(out, turn=9, names=_names(scene))["text"] == \
        "you sold the crate to the clerk of the counting house"
    scene.pc().goods["lantern"] = 1
    out = _run(scene, [{"op": "give", "params": {"item": "lantern", "from_": "pc",
                                                 "to": clerk}}])
    assert ledger.note(out, turn=10, names=_names(scene))["text"] == \
        "you handed the lantern to the clerk of the counting house"


# --- the real path: the player's line through `plan_turn`, then the engine ------------------

class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "fake"

    def json(self):
        return json.loads(self.text)


def _agent_with(monkeypatch, reply, *names):
    """The agent the turn uses, with the model's reply scripted as the save recorded it."""
    from gm import agent as agent_mod
    from _a_truth import VORMOOR, WORLD

    s = Scene(location_id=VORMOOR.id)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=5), world=WORLD)
    e.place_party()
    for name in names:
        s.add(instantiate("guildhand", scene=s, name=name))
    monkeypatch.setattr(agent_mod.client, "chat",
                        lambda messages, model, host, **kw: _Reply(json.dumps(
                            reply(s) if callable(reply) else reply)))
    return agent_mod.GMAgent(WORLD, e), s, e


def test_the_recorded_drop_through_the_turn_lands_on_the_floor(monkeypatch):
    """Turn 110 end to end: the player's own line and the model's own plan as recorded
    (`give actor=pc target=<the smith>`), through every injector `plan_turn` runs."""
    def plan(s):
        return {"narration": "", "intents": [
            {"op": "give", "actor": "pc", "target": _ref(s, "the smith"),
             "params": {"item": "Brunt of the weight"}}]}

    gm, s, e = _agent_with(monkeypatch, plan, "the smith")
    smith = _ref(s, "the smith")
    s.pc().goods["brunt of the weight"] = 1
    said = ("I transfer the coins from the pouch into my coin purse.  I also drop the "
            "Brunt of the weight on the ground and leave it behind.")
    # The reading the 2026-10-03 reader gave this line (the replay of the items save).
    interpret.remember(said, {"question": False, "claims": [], "actions": [
        {"act": "take", "object": "the coins", "target": "the pouch"},
        {"act": "drop", "object": "the Brunt of the weight", "place": "the ground"}]})
    turn = gm.plan_turn(said, history=[])
    e.run(turn.intents)
    assert "brunt of the weight" not in s.pc().goods and not s.actors[smith].goods
    assert any(p["name"] == "brunt of the weight" for p in s.props_here())


def test_the_recorded_close_through_the_turn_sells_the_crate(monkeypatch):
    """Turn 94 end to end: the model planned `narrate_only` ("the negotiation of a price
    is a social interaction") and the crate stayed in the pack."""
    gm, s, e = _agent_with(monkeypatch, {"narration": "", "intents": [
        {"op": "narrate_only",
         "because": "the negotiation of a price is a social interaction"}]},
        "the clerk of the counting house")
    s.pc().goods["crate"] = 1
    said = "I agree to sell the crate to the clerk at 75% of the crate's value."
    interpret.remember(said, {"question": False, "claims": [], "actions": [
        {"act": "sell", "object": "the crate", "target": "the clerk"}]})
    turn = gm.plan_turn(said, history=[])
    e.run(turn.intents)
    assert "crate" not in s.pc().goods
    assert goods.in_copper(s.pc().purse) == round(pricing.UNLISTED_GP / 2 * 100)
