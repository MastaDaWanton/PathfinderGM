"""Selling something, and being paid for it.

Recovered from a live campaign save. The player asked an elderly stallholder to name a
price for a satchel of tinctures and elixirs, haggled her from ten gold up to twenty-two,
and shook her hand on it. Every turn of that resolved to `narrate_only`. No item moved, no
coin moved, and the purse was `{}` afterwards.

    "it's also obvious the vender in this interaction did not actually see what i was
     trying to give her it was completely narrative."

It was exactly that. There was no `sell` op anywhere in `rules/intents.py` — no buy, no
trade, no barter — so there was nothing for the stallholder to be handed.
"""
from __future__ import annotations

import pytest

from rules import market, pricing
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.crafting import Stock
from rules.sheet import load_pc


def jar(base="Blackthorn Draught", tier="uncommon", potency=1335.61, count=1,
        specs=None, concentration=1):
    """A crafted jar as the bench makes them. `id` and `name` are derived from `base`
    and `concentration`, so those are what a test sets."""
    return Stock(base=base, concentration=concentration, tier=tier, potency=potency,
                 count=count,
                 specs=specs if specs is not None else [{"type": "heal", "dice": "1d4"}])


@pytest.fixture
def engine():
    scene = Scene(location_id="pangrella")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    return Engine(scene, Dice(seed=3))


def run(engine, raw):
    return engine.run(engine.validate([raw])).outcomes


def test_the_goods_actually_leave_your_hands_and_coin_actually_arrives(engine):
    """The whole point. Before this the transaction was prose and nothing else."""
    pc = engine.scene.pc()
    pc.add_stock(jar(potency=5.8, tier="rare"))
    assert pc.purse == {}

    out = run(engine, {"op": "sell", "actor": "pc",
                       "params": {"item": "blackthorn-draught#1"}})

    assert "blackthorn-draught#1" not in pc.stock, "the jar is still in the satchel"
    assert pc.purse, f"nothing was paid: {out[0].tell}"
    assert out[0].effects[0]["kind"] == "sold"


def test_a_stall_that_cannot_afford_it_pays_what_it_can(engine):
    """"i can still sell to them if i am willing to any get what they can give."

    One Blackthorn purified draught at potency 1,335 is worth 1,325 gp, and a market
    apothecary has a few hundred in the till. The cap is an offer, not a refusal."""
    pc = engine.scene.pc()
    pc.add_stock(jar())
    asked = pricing.what_a_shop_pays(pc.stock["blackthorn-draught#1"])
    assert asked > 600

    out = run(engine, {"op": "sell", "actor": "pc",
                       "params": {"item": "blackthorn-draught#1", "stall": "apothecary"}})

    paid_cp = out[0].effects[0]["paid_cp"]
    assert 0 < paid_cp / 100 < asked
    # And the shortfall is said out loud, or it reads as a bad price rather than an
    # empty till — which is the entire difference the cap exists to express.
    assert "all" in out[0].tell and "asked" in out[0].tell


def test_the_till_empties_and_stays_empty_until_tomorrow(engine):
    """Otherwise a stall with 247 gp buys the whole satchel one bottle at a time."""
    pc = engine.scene.pc()
    pc.add_stock(jar())
    pc.add_stock(jar(base="Yarow Elixir", tier="common", potency=1.25))

    run(engine, {"op": "sell", "actor": "pc",
                 "params": {"item": "blackthorn-draught#1", "stall": "apothecary"}})
    out = run(engine, {"op": "sell", "actor": "pc",
                       "params": {"item": "yarow-elixir#1", "stall": "apothecary"}})

    assert "nothing left in it today" in out[0].tell
    # And the elixir is still in the satchel — a refused sale takes nothing.
    assert "yarow-elixir#1" in pc.stock


def test_a_price_the_player_agreed_to_can_only_lower_the_ask(engine):
    """`accept` is the haggle. It must not be a way to talk a stall into paying more than
    the goods are worth by writing a bigger number into the intent."""
    pc = engine.scene.pc()
    pc.add_stock(jar(base="Yarow Elixir", tier="common", potency=1.25))
    honest = pricing.what_a_shop_pays(pc.stock["yarow-elixir#1"])

    out = run(engine, {"op": "sell", "actor": "pc",
                       "params": {"item": "yarow-elixir#1", "accept": 500}})
    assert out[0].effects[0]["paid_cp"] <= round(honest * 100) + 1


def test_selling_what_you_are_not_carrying_is_refused_by_name(engine):
    """A legality error names what they do have, the same way `use_item` does — a blind
    rejection costs the GM a whole regeneration to learn one word."""
    from rules.intents import IntentError

    with pytest.raises(IntentError) as caught:
        run(engine, {"op": "sell", "actor": "pc", "params": {"item": "moonshine#9"}})
    assert "not carrying" in str(caught.value)


def test_selling_more_than_you_have_sells_what_you_have(engine):
    pc = engine.scene.pc()
    # `add_stock` takes the count as its own argument and overwrites the jar's — setting
    # it on the Stock alone silently put one on the shelf.
    pc.add_stock(jar(base="Yarow Elixir", tier="common", potency=1.25), 2)
    assert pc.stock["yarow-elixir#1"].count == 2

    out = run(engine, {"op": "sell", "actor": "pc",
                       "params": {"item": "yarow-elixir#1", "count": 99}})
    assert out[0].effects[0]["count"] == 2
    # `left`, not "how many were taken" — reading `take_stock`'s return as the remainder
    # reported a sold-out jar as having one still on the shelf.
    assert out[0].effects[0]["left"] == 0
    assert "yarow-elixir#1" not in pc.stock


def test_the_stall_and_its_shelf_agree_about_which_shop_this_is(engine):
    """The till is keyed on (place, stall, day) exactly as `market.stock` keys the shelf,
    read off the scene the same way `craft_views` reads it. Two stalls in one town are
    two different shops, and that has to be true of the money as well as the goods."""
    pc = engine.scene.pc()
    pc.add_stock(jar(base="Alpha Tea", tier="common", potency=1.25))
    pc.add_stock(jar(base="Beta Tea", tier="common", potency=1.25))

    run(engine, {"op": "sell", "actor": "pc",
                 "params": {"item": "alpha-tea#1", "stall": "apothecary"}})
    spent = market.spent_today(engine.scene.market_taken, "pangrella", "apothecary", 0)
    assert spent > 0
    # The ironmonger's till is untouched by what the apothecary paid.
    assert market.spent_today(
        engine.scene.market_taken, "pangrella", "ironmonger", 0) == 0



# --- and the GM has to actually emit it --------------------------------------------------

def _scene_with_a_satchel():
    scene = Scene(location_id="pangrella")
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    pc.add_stock(jar(base="Yarow Elixir", tier="common", potency=1.25), 3)
    pc.add_stock(jar(base="Blackthorn Draught"))
    return scene


def test_a_declared_sale_reaches_the_engine_whatever_the_gm_proposed():
    """The ninth injector, and the same measurement every time: the op exists, the prompt
    carries it, the model does not emit it. Four turns of haggling over a satchel of
    tinctures produced four `narrate_only` and nothing else."""
    from gm import judgement

    raw = judgement.inject_sale([{"op": "narrate_only", "params": {}}],
                                "I sell the Yarow Elixir to her", _scene_with_a_satchel())
    assert [r["op"] for r in raw] == ["narrate_only", "sell"]
    assert raw[-1]["params"]["item"] == "yarow-elixir#1"


def test_asking_the_price_is_not_selling():
    """A haggle is full of statements that are still questions. "twenty gold coins" has no
    question mark in it at all, and the turn before it was "I ask her to name a price for
    all my tinctures and elixirs" — if either of those moved goods, the player would have
    sold the satchel by opening their mouth."""
    from gm import judgement

    scene = _scene_with_a_satchel()
    for said in ("I ask her to name a price for all my tinctures and elixirs",
                 "how much will you give me for the Yarow Elixir",
                 "what is the Blackthorn Draught worth to you"):
        raw = judgement.inject_sale([{"op": "narrate_only", "params": {}}], said, scene)
        assert [r["op"] for r in raw] == ["narrate_only"], said


def test_selling_something_you_do_not_have_injects_nothing():
    """Grounded in the satchel rather than in the sentence, which is the whole difference
    between this and `inject_goods`. "I sell my soul" finds no jar and stays out of it."""
    from gm import judgement

    scene = _scene_with_a_satchel()
    for said in ("I sell my soul to the winged man", "I sell the warhorse"):
        raw = judgement.inject_sale([{"op": "narrate_only", "params": {}}], said, scene)
        assert [r["op"] for r in raw] == ["narrate_only"], said


def test_a_sale_the_gm_already_proposed_is_left_alone():
    """The same guard every injector has: never a second copy of what is already there."""
    from gm import judgement

    already = [{"op": "sell", "actor": "pc", "params": {"item": "yarow-elixir#1"}}]
    raw = judgement.inject_sale(already, "I sell the Yarow Elixir", _scene_with_a_satchel())
    assert raw == already


def test_the_longest_matching_name_wins():
    """A jar merely called "Elixir" must not beat "Yarow Elixir" to the sale."""
    from gm import judgement

    scene = _scene_with_a_satchel()
    scene.pc().add_stock(jar(base="Elixir", tier="common", potency=1.0))
    raw = judgement.inject_sale([{"op": "narrate_only", "params": {}}],
                                "I sell the Yarow Elixir", scene)
    assert raw[-1]["params"]["item"] == "yarow-elixir#1"



# --- buying, which did not exist in play at all ------------------------------------------

def _counter(place="pangrella", stall="market", day=0, taken=None):
    from rules import market as m

    return m.on_sale(place, stall, day, taken or {})


def test_you_can_buy_a_thing_while_standing_in_front_of_it(engine):
    """Buying existed only on the crafting bench, as an excursion that spends hours and
    rolls a check to go and find a supplier. That is the right shape for stocking a
    workshop and the wrong one for standing at a counter, so there was no way at all to
    buy a thing while looking at it."""
    pc = engine.scene.pc()
    pc.purse = {"gp": 50}
    cheapest = min(_counter(), key=pricing.worth)

    out = run(engine, {"op": "buy", "actor": "pc",
                       "params": {"item": cheapest.id, "count": 2}})

    assert out[0].effects[0]["kind"] == "bought"
    # Named exactly, not "something in the satchel has a count of 2" — the loose version
    # of this passes even when the wrong thing was bought.
    assert len(pc.stock) == 1
    bought = next(iter(pc.stock.values()))
    assert bought.base == cheapest.name and bought.count == 2
    assert pc.purse != {"gp": 50}, "nothing was paid"


def test_what_has_been_carried_out_of_the_shop_is_gone(engine):
    """`mark_sold` is what makes the one legendary one legendary."""
    from rules import market as m

    pc = engine.scene.pc()
    pc.purse = {"gp": 500}
    cheapest = min(_counter(), key=pricing.worth)
    run(engine, {"op": "buy", "actor": "pc", "params": {"item": cheapest.id}})

    left = m.on_sale("pangrella", "market", 0, engine.scene.market_taken)
    assert cheapest.id not in {x.id for x in left}


def test_an_empty_purse_buys_nothing_and_says_the_price(engine):
    pc = engine.scene.pc()
    pc.purse = {"sp": 2}
    dearest = max(_counter(), key=pricing.worth)

    out = run(engine, {"op": "buy", "actor": "pc", "params": {"item": dearest.id}})
    assert "Nothing changes hands" in out[0].tell
    assert pc.purse == {"sp": 2} and not pc.stock


def test_buying_what_is_not_on_the_counter_names_what_is(engine):
    """A blind rejection costs the GM a whole regeneration to learn one word."""
    from rules.intents import IntentError

    with pytest.raises(IntentError) as caught:
        run(engine, {"op": "buy", "actor": "pc", "params": {"item": "moon-cheese"}})
    assert "on the counter" in str(caught.value)


def test_a_stall_does_not_stock_what_it_could_not_have_bought():
    """The rarity quota alone put a 2,500 gp Ring of Climbing on a market stall's *common*
    shelf. 18 of the 79 common-tier materials are magic gear over 100 gp — the tiers track
    price well on average (common median 2 gp against legendary 16,000) and it is the tail
    that gets you. A corner stall holding a ring it could never have bought is the "shop is
    a catalogue" bug wearing a different hat.

    The till is the bound, which makes the two halves of a shop agree: what a stallholder
    can pay out and what they have on the shelf are one fact seen from both sides."""
    from rules import market as m

    till = m.purse("pangrella", "market", 0, "common")
    shelf = m.on_sale("pangrella", "market", 0, {}, "common")
    assert shelf, "the filter emptied the shelf entirely"
    dearest = max(pricing.worth(x) for x in shelf)
    assert dearest <= till, f"a {dearest} gp thing on a stall holding {till} gp"


def test_a_richer_house_stocks_what_a_stall_cannot():
    from rules import market as m

    poor = max(pricing.worth(x) for x in m.on_sale("pangrella", "market", 0, {}, "common"))
    rich = max(pricing.worth(x)
               for x in m.on_sale("pangrella", "vault", 0, {}, "legendary"))
    assert rich > poor * 10



# --- required up front rather than injected afterwards -----------------------------------

def test_a_declared_sale_is_required_by_the_schema_not_bolted_on():
    """Nine injectors now, one per feature, growing forever — and each one is a repair
    applied after the model failed to propose something the player plainly said.

    The fight schema already shows the better shape: in combat `narrate_only` is not in
    the op enum, so proposing nothing is not a reply the sampler can produce. The same
    trick generalises. When a declaration is detected the schema requires that op, and the
    model then picks the item and the target with the scene in front of it — which an
    injector guessing afterwards cannot."""
    from gm import judgement, prompts

    scene = _scene_with_a_satchel()
    assert judgement.declared_ops("I sell the Yarow Elixir to her", scene) == ["sell"]

    schema = prompts.turn_schema(refs=("pc",), must_contain=("sell",))
    required = schema["properties"]["intents"]["allOf"]
    assert required[0]["contains"]["properties"]["op"]["const"] == "sell"
    assert schema["properties"]["intents"]["minItems"] >= 1


def test_selling_is_not_also_giving_it_away():
    """Found by building `declared_ops`, in code committed hours earlier the same day.

    "I sell the Yarow Elixir" matches `_HANDS_OVER`, so `inject_goods` ran first and wrote
    a `give` — the elixir left the satchel for nothing — and `inject_sale` then bowed out
    because a `give` was already present. A declared sale paid the player zero gold, and
    the entire trade feature was invisible behind it.

    Sale first, and `inject_goods` bows out to it. One sentence, one item, one op."""
    from gm import judgement

    scene = _scene_with_a_satchel()
    said = "I sell the Yarow Elixir to her"

    raw = judgement.inject_sale([{"op": "narrate_only", "params": {}}], said, scene)
    raw = judgement.inject_goods(raw, said, scene)
    assert [r["op"] for r in raw] == ["narrate_only", "sell"]
    assert judgement.declared_ops(said, scene) == ["sell"]


def test_handing_something_over_is_still_a_give():
    """The narrower reading must not swallow the wider one — "I hand over the brass key"
    is not a sale and there is no key in the satchel to sell."""
    from gm import judgement

    scene = _scene_with_a_satchel()
    assert judgement.declared_ops("I hand over the brass key", scene) == ["give"]


def test_a_turn_that_declares_nothing_constrains_nothing():
    """The schema only narrows when the player's own words commit the turn to something.
    "I look around the square" is a quiet beat and must stay one."""
    from gm import judgement, prompts

    scene = _scene_with_a_satchel()
    assert judgement.declared_ops("I look around the square", scene) == []
    schema = prompts.turn_schema(refs=("pc",), must_contain=())
    assert "allOf" not in schema["properties"]["intents"]


def test_two_declarations_both_have_to_be_there():
    """`allOf` of `contains`, one per op — a single `contains` with an enum is satisfied by
    any one of them, so a turn that both travels and buys would be accepted with either
    alone."""
    from gm import prompts

    schema = prompts.turn_schema(refs=("pc",), must_contain=("travel", "give"))
    ops = [c["contains"]["properties"]["op"]["const"]
           for c in schema["properties"]["intents"]["allOf"]]
    assert ops == ["travel", "give"]
    assert schema["properties"]["intents"]["minItems"] >= 2



# --- the chain, not the links ------------------------------------------------------------

def _chain(said, scene, world=None):
    """Every injector `agent.plan_turn` runs, in the order it runs them.

    Read out of the agent's own source rather than rewritten here, because a copy of an
    ordering is an ordering that can drift — and this whole test file exists because one
    did. If `plan_turn` reorders them, this reorders with it.
    """
    import inspect
    import re

    from gm import agent as agent_mod, judgement

    src = inspect.getsource(agent_mod.GMAgent.plan_turn)
    names = re.findall(r"judgement\.(\w+)\(raw", src)
    raw = [{"op": "narrate_only", "params": {}}]
    for name in names:
        fn = getattr(judgement, name)
        raw = fn(raw, said, scene, world) if name == "inject_travel" else (
            fn(raw, scene) if name == "fill_obvious_targets" else fn(raw, said, scene))
    return raw, names


def test_the_injectors_run_in_an_order_that_does_not_give_the_goods_away():
    """The bug this file exists for, and the reason it survived a green suite.

    "I sell the Yarow Elixir" matches `_HANDS_OVER`. `inject_goods` ran first and wrote a
    `give` — the elixir left the satchel for nothing — and `inject_sale` then bowed out,
    because a `give` was already present. A declared sale paid zero gold.

    Every test of the sale passed, because every one of them called `inject_sale`
    directly. The order only exists in `plan_turn`, and nothing ran the chain."""
    scene = _scene_with_a_satchel()
    raw, names = _chain("I sell the Yarow Elixir to her", scene)

    assert "inject_sale" in names and "inject_goods" in names
    assert names.index("inject_sale") < names.index("inject_goods"), \
        f"goods runs before sale: {names}"

    ops = [r["op"] for r in raw]
    assert "sell" in ops, f"the declared sale never reached the engine: {ops}"
    assert "give" not in ops, f"the elixir was also given away: {ops}"


def test_one_sentence_produces_one_op_for_the_thing_it_names():
    """The general form. Whatever the chain does, an item may leave the satchel once."""
    scene = _scene_with_a_satchel()
    for said in ("I sell the Yarow Elixir to her",
                 "I hand over the Yarow Elixir",
                 "I buy a lantern"):
        raw, _ = _chain(said, scene)
        moving = [r["op"] for r in raw if r["op"] in {"sell", "buy", "give"}]
        assert len(moving) <= 1, f"{said!r} moved goods {len(moving)} times: {moving}"


def test_the_chain_leaves_a_quiet_turn_quiet():
    scene = _scene_with_a_satchel()
    raw, _ = _chain("I look around the square", scene)
    assert [r["op"] for r in raw] == ["narrate_only"]


def test_what_the_chain_produces_is_what_the_schema_asked_for():
    """`declared_ops` and the chain have to agree, or the schema requires an op the
    injectors would never have supplied as a backstop — and a turn the model cannot
    satisfy is a turn that burns seven attempts and dies."""
    from gm import judgement

    scene = _scene_with_a_satchel()
    for said in ("I sell the Yarow Elixir to her", "I hand over the brass key",
                 "I sneak past the guard", "I look around the square"):
        wanted = judgement.declared_ops(said, scene)
        raw, _ = _chain(said, scene)
        got = {r["op"] for r in raw}
        for op in wanted:
            assert op in got, f"{said!r}: schema wants {op}, chain gives {sorted(got)}"



# --- one rule, four doors ----------------------------------------------------------------

def test_an_unconscious_character_cannot_trade_use_items_or_swing():
    """Found in the first minute of a play session, in code committed the same day.

    Thessaly Corr was at 0 hit points, Unconscious and Disabled after a fight — and she
    sold a Woad Tincture and bought a jar of beeswax across the counter. Nothing anywhere
    asked whether she was awake.

    `say` has refused the downed since somebody typed "now what" at -3 hit points and got
    cheerful narration about dodging a thug. `use_item`, `combat_act` and the counter all
    shipped without that guard: one rule, four doors, one of them locked.

    `say` still answers 200 here and that is correct — a turn taken while down runs the
    stabilisation clock rather than refusing, which is what `downed.resolve` is for."""
    import json as _json

    from django.test import Client

    from play import campaign as cm

    c = cm.current()
    pc = c.scene.pc()
    if pc is None:
        import pytest as _pytest
        _pytest.skip("no live campaign to check the doors against")

    was_hp, was_conditions = pc.hp, [x.key for x in pc.conditions]
    pc.hp = 0
    pc.add_condition("unconscious")
    c.save()
    try:
        client = Client()
        for path, body in (
                ("/api/trade/do", {"op": "sell", "item": "nothing#1"}),
                ("/api/use", {"item": "nothing#1", "how": "drink"}),
                ("/api/combat/act", {"actions": [], "label": "x"})):
            r = client.post(path, data=_json.dumps(body),
                            content_type="application/json")
            assert r.status_code == 409, f"{path} let a downed character act"
            assert "no condition to" in r.json().get("error", ""), path
    finally:
        pc.hp = was_hp
        pc.conditions = [x for x in pc.conditions if x.key in was_conditions]
        c.save()


def test_the_guard_is_one_helper_and_not_four_copies():
    """CLAUDE.md's rule about a rule with more than one home: a consequence rule was
    corrected in one prompt and left stale in the other, and the bug went on shipping from
    the copy nobody looked at. This is that shape exactly — the check existed, in one
    place, and three other doors never got it."""
    import inspect

    from play import views

    src = inspect.getsource(views)
    assert src.count("def _cannot_act(") == 1
    # Every door calls the helper rather than re-deriving the rule.
    for door in ("def trade_do", "def use_item", "def combat_act"):
        body = src.split(door, 1)[1][:1600]
        assert "_cannot_act(" in body, f"{door} does not ask whether the player can act"



# --- what a played sale actually did ------------------------------------------------------

def test_a_purse_carries_rather_than_growing_sideways():
    """Measured in play, after two sales through the counter and one through the narrator:

        {'gp': 9, 'sp': 18, 'cp': 12}

    Eighteen silver pieces and twelve coppers. 1,092 copper written in a way no purse in
    the world has ever been counted — nobody carries twelve coppers when ten of them are
    a silver.

    `credit` called `_add_change` on the existing purse, which only ever carried the coin
    *arriving*. Whatever was already there kept its shape, so the piles grew sideways
    every time somebody was paid."""
    from rules import goods

    broken = {"gp": 9, "sp": 18, "cp": 12}
    assert goods.in_copper(broken) == 1092
    recounted = goods.credit(broken, 0)
    assert goods.in_copper(recounted) == 1092, "recounting changed the money"
    assert all(n < 10 for cid, n in recounted.items() if cid != "pp"), recounted

    # And it stays counted as it grows.
    purse = {}
    for _ in range(30):
        purse = goods.credit(purse, 37)
    assert goods.in_copper(purse) == 30 * 37
    assert all(n < 10 for cid, n in purse.items() if cid != "pp"), purse


def test_the_narration_may_not_name_a_price():
    """The first sale played through the narrator rather than the counter. The engine
    priced the jar and credited the purse; the prose, in the same turn, had the
    stallholder *charging* her —

        "'That'll be 5 silver crescents, please.' As you hand over your payment..."

    — and the consequence beat carried on with "you hand over more coins than she asked
    for". The direction of the transaction was inverted and the sum invented, while the
    engine's own tell in the same transcript said she had been paid.

    Same family as a damage number. What a price *is* here is `rules.pricing`'s answer,
    from tier and potency, and the narrator has no way to know it."""
    from rules.intents import find_outcome_claims

    said = ("She takes the vial. 'That'll be 5 silver crescents, please.' As you hand "
            "over your payment, she smiles.")
    why = {c.why for c in find_outcome_claims(said)}
    assert "states a sum of money" in why
    assert "states a price" in why
    assert "states the player paying" in why


def test_prose_that_names_no_sum_is_left_alone():
    """A sale still has to be describable. Only the numbers are the engine's."""
    from rules.intents import find_outcome_claims

    said = ("She turns the vial over twice, holds it up to the light, and counts coins "
            "into your palm without saying anything at all.")
    assert not find_outcome_claims(said)


def test_a_jar_in_the_satchel_is_not_a_person():
    """"Musk Muddle Tincture" is a jar she crafted, and `Tincture` was reported as an
    invented person the moment she sold one. The catalogue vocabulary covers materials the
    world *sells*; it had never heard of anything a character made."""
    import inspect

    from gm.agent import GMAgent

    src = inspect.getsource(GMAgent._known_names)
    assert 'getattr(actor, "stock"' in src, \
        "the satchel is not part of the vocabulary"
