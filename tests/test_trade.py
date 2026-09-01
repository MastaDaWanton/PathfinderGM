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
        if name == "inject_travel":
            raw = fn(raw, said, scene, world)
        elif name == "fill_obvious_targets":
            raw = fn(raw, scene)
        elif name == "fill_bare_checks":
            raw = fn(raw)
        elif name == "normalize_attacks":
            raw = fn(raw, scene) or raw
        elif name == "drop_stray_checks":
            raw = fn(raw, said)
        elif name in ("drop_premature_end", "split_plural_targets"):
            raw = fn(raw)
        elif name == "repair_bare_spawns":
            raw = fn(raw, said)
        elif name == "bulk_give_is_a_loot":
            raw = fn(raw, scene)
        elif name == "redirect_attacks_off_corpses":
            raw = fn(raw, said, scene) or raw
        else:
            raw = fn(raw, said, scene)
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
        # Through the one applicator's own remover — `conditions` is a read-only view
        # over the effect store now, and assigning a filtered list to it was the last
        # place anything edited a condition without the engine knowing.
        for key in [x.key for x in pc.conditions]:
            if key not in was_conditions:
                pc.remove_condition(key)
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



# --- casting, which a typed sentence could not do ----------------------------------------

def _wizard_scene():
    scene = Scene(location_id="pangrella")
    pc = load_pc("fixtures/pc-kesst.json")
    pc.char_class = "wizard"
    pc.spellbook = ["prestidigitation", "magic-missile"]
    pc.prepared = {"prestidigitation": 1}
    scene.add(pc)
    return scene


def test_a_declared_spell_reaches_the_engine():
    """The tenth injector, found by playing. "I cast prestidigitation on the Sweetspire
    Tea to make it gleam like something far finer" produced a paragraph about blue light
    and a single `narrate_only`. No slot spent, no spell cast, nothing the engine saw.

    The `cast` op has worked for months — Magic Missile 1d4+1 x3, Burning Hands 5d4 at
    Reflex DC 12, saves and spell resistance read off the spell. Only the door from a
    typed sentence was missing, which is what the combat panel's Cast button was added for
    and what a player who types instead of clicking never had."""
    from gm import judgement

    raw = judgement.inject_cast([{"op": "narrate_only", "params": {}}],
                                "I cast prestidigitation on the Sweetspire Tea",
                                _wizard_scene())
    assert [r["op"] for r in raw] == ["narrate_only", "cast"]
    assert raw[-1]["params"]["spell"] == "prestidigitation"


def test_a_spell_she_does_not_have_injects_nothing():
    """Grounded in the book, the same way `inject_sale` is grounded in the satchel. A
    wizard who says "I cast fireball" at level 1 gets no intent, and the narrator is free
    to tell her so — a better turn than a legality error that burns five attempts."""
    from gm import judgement

    raw = judgement.inject_cast([{"op": "narrate_only", "params": {}}],
                                "I cast fireball at the crowd", _wizard_scene())
    assert [r["op"] for r in raw] == ["narrate_only"]


def test_asking_about_a_spell_is_not_casting_it():
    from gm import judgement

    for said in ("what spells do I have prepared?",
                 "I prepare prestidigitation for tomorrow",
                 "I scribe prestidigitation into my book"):
        raw = judgement.inject_cast([{"op": "narrate_only", "params": {}}], said,
                                    _wizard_scene())
        assert [r["op"] for r in raw] == ["narrate_only"], said


def test_a_spell_in_her_own_book_is_not_an_invented_person():
    """"Prestidigitation" was reported as an invented name the first time one was cast.
    Only what *this character* knows is added, not all 3,040 spells: a name is grounded
    because she has it, not because a rulebook somewhere prints it."""
    import inspect

    from gm.agent import GMAgent

    src = inspect.getsource(GMAgent._known_names)
    assert 'getattr(actor, "spellbook"' in src


def test_no_literal_backspace_survived_in_judgement():
    """Written into this module through a shell heredoc twice while adding `inject_cast`,
    and both times the regex word boundaries arrived as literal backspace bytes (0x08) —
    a pattern that then silently matches nothing at all. `_CASTS` failed to see "I cast
    prestidigitation" and the injector returned quietly, looking like a logic bug.

    CLAUDE.md records this exact trap and says to use the Write tool or build the
    backslash with chr(92). Eight bytes had to be repaired."""
    from pathlib import Path as _P

    src = (_P(__file__).resolve().parents[1] / "gm" / "judgement.py").read_bytes()
    assert chr(8).encode() not in src



# --- requiring the op is half a fix -------------------------------------------------------

def test_the_model_names_the_jar_the_way_a_person_would():
    """Measured in play, the turn after the schema started *requiring* a `sell` when the
    player declares one. The model duly emitted the op — and named the jar in English:

        The engine refused the GM's intents: sell: Thessaly Corr is not carrying
        'sweetspire tea'. They have: beeswax#1, betony-tea#1, ... sweetspire-tea#1, ...

    The thing she was selling is in that very list. The turn died on a 502.

    `must_contain` gets the op proposed and leaves its params to chance, and the injector
    had stood down because a `sell` was already present — so the one piece of code that
    knows the ids was the one piece not looking. It corrects the params now instead of
    bowing to them."""
    from gm import judgement

    scene = _scene_with_a_satchel()
    scene.pc().add_stock(jar(base="Sweetspire Tea", tier="common", potency=1.25), 4)

    model = [{"op": "sell", "actor": "pc", "params": {"item": "sweetspire tea"}}]
    fixed = judgement.inject_sale(model, "I sell the Sweetspire Tea at a premium", scene)
    assert fixed[0]["params"]["item"] == "sweetspire-tea#1"


def test_an_item_the_satchel_never_heard_of_is_left_for_the_engine():
    """The engine's own refusal names what she *does* have, which is a better error than
    anything guessed here. Only an exact match on the id, the name or the base is taken."""
    from gm import judgement

    scene = _scene_with_a_satchel()
    model = [{"op": "sell", "actor": "pc", "params": {"item": "moon cheese"}}]
    assert judgement.inject_sale(model, "I sell the moon cheese", scene) == model


def test_an_id_that_is_already_right_is_not_touched():
    from gm import judgement

    scene = _scene_with_a_satchel()
    model = [{"op": "sell", "actor": "pc", "params": {"item": "yarow-elixir#1"}}]
    assert judgement.inject_sale(model, "I sell the Yarow Elixir", scene) == model



def test_the_stallholder_is_allowed_to_hand_over_the_payment():
    """A false positive in the money detector, found on the very sale it was written for.

    The pattern read "hands over the payment" without asking whose hands, so it cut

        "She hands over the payment, and you can see the weight of the coins in her
         pouch before she tucks them away with a satisfied smile."

    — the stallholder paying for a jar the engine had just sold. A detector that removes
    the *true* half of a transaction is worse than none: the player is left with a sale
    nobody was seen to pay for. The subject decides it."""
    from rules.intents import find_outcome_claims

    theirs = ("She hands over the payment, and you can see the weight of the coins in "
              "her pouch before she tucks them away.")
    assert not find_outcome_claims(theirs)

    yours = "As you hand over your payment, she smiles."
    assert any(c.why == "states the player paying" for c in find_outcome_claims(yours))


def test_a_cosmetic_spell_does_not_move_the_price():
    """Played end to end: prestidigitation cast on a jar of Sweetspire Tea "so it gleams
    like a far finer thing", then sold at a premium.

    The narration played along — "You name a price that's significantly higher than the
    original cost... 'I'll take it,' she says" — and the ledger did not. The engine paid
    7 sp 5 cp, which is `what_a_shop_pays` to the copper, and the purse moved 1,092 to
    1,167 copper. Exactly 75.

    `pricing.worth` reads tier and potency. Prestidigitation touches neither, so a
    cosmetic glamour cannot inflate what anything is worth however well it is sold."""
    from rules import pricing

    plain = jar(base="Sweetspire Tea", tier="common", potency=1.0,
                specs=[{"type": "heal", "dice": "1d4"}])
    assert pricing.what_a_shop_pays(plain) == 0.75

    # There is no field a cosmetic spell writes, which is the point — the price is a
    # function of what the jar *is*.
    gleaming = jar(base="Sweetspire Tea", tier="common", potency=1.0,
                   specs=[{"type": "heal", "dice": "1d4"}])
    assert pricing.worth(gleaming) == pricing.worth(plain)



# --- the five findings of the 2026-08-26 session -----------------------------------------

def test_a_declared_forage_reaches_the_engine():
    """The eleventh injector, and the same measurement as every one before it. A live
    session typed "I get my water and then I go out to the forest to forage" and the
    narration invented the entire outcome — chanterelle mushrooms, identified by "your
    Survival skill", "added to your satchel" — while the engine ran nothing and the
    ingredients panel truthfully showed an empty satchel."""
    from gm import judgement

    scene = _scene_with_a_satchel()
    said = "I get my water and then I go out to the forest to forage"
    ops = judgement.declared_ops(said, scene)
    # Travel AND forage, in that order — the move must resolve first or the forage
    # rolls the old ground's tables.
    assert "forage" in ops
    assert ops.index("travel") < ops.index("forage")

    raw = judgement.inject_forage([{"op": "narrate_only", "params": {}}],
                                  "I forage for 3 hours", scene)
    assert raw[-1]["op"] == "forage"
    assert raw[-1]["params"] == {"hours": 3}
    # No biome, no track, ever: the engine reads the ground off the scene and refuses
    # "nowhere in particular" with a printable reason; an injector guessing either
    # would be overriding the one component that actually knows.
    assert "biome" not in raw[-1]["params"] and "track" not in raw[-1]["params"]


def test_gathering_needs_a_plant_and_a_sword_is_not_one():
    """A false forage charges an hour of world clock and a Survival toll to somebody who
    never asked to spend either, so the gather-family verbs require a plant noun."""
    from gm import judgement

    scene = _scene_with_a_satchel()
    for said in ("I pick up the sword", "I gather my things and leave",
                 "should I forage here?"):
        raw = judgement.inject_forage([{"op": "narrate_only", "params": {}}],
                                      said, scene)
        assert [r["op"] for r in raw] == ["narrate_only"], said
    raw = judgement.inject_forage([{"op": "narrate_only", "params": {}}],
                                  "I gather herbs by the stream", scene)
    assert raw[-1]["op"] == "forage"


def test_an_invented_haul_is_an_outcome_claim():
    """The exact narration the live session shipped. The satchel is the engine's to
    fill; a *real* haul is reported by the consequence call, which runs with claims
    switched off precisely so true reporting stays legal."""
    from rules.intents import find_outcome_claims

    said = ("You take out your Survival skill to identify them. You add them to your "
            "satchel, along with some other foraged plants and berries.")
    why = {c.why for c in find_outcome_claims(said)}
    assert any("satchel is the engine's" in w for w in why)
    assert any("checks are rolled" in w for w in why)
    # An NPC stowing their own goods is nobody's business.
    assert not find_outcome_claims("She stows the coins in her own pouch and nods.")

    # The state-claim variant, caught on the first live verification of the fix above:
    # the same haul invented with no gaining verb at all, before a single die was
    # rolled — and the engine's actual haul an hour later was rue and pomegranate.
    said = ("After an hour of searching, your satchel is full to bursting with wild "
            "mushrooms, berries, and other edible plants.")
    assert any("satchel is the engine's" in c.why for c in find_outcome_claims(said))


def test_an_untrained_check_refuses_instead_of_crashing():
    """Measured live: toggling the class's blood armament out of combat went through the
    spoken path, the model dressed it as a Knowledge (Arcana) check, and
    `skill_modifiers` raised IllegalSheet straight through the turn — "cannot attempt
    knowledge (arcana) untrained" cost the whole action. The rule is right (1e knowledge
    checks are trained-only); the crash was not."""
    scene = Scene(location_id="pangrella")
    pc = load_pc("fixtures/pc-kesst.json")
    pc.ranks.pop("knowledge (arcana)", None)
    scene.add(pc)
    eng = Engine(scene, Dice(seed=3))

    out = eng.run(eng.validate([{"op": "check", "actor": "pc",
                                 "params": {"skill": "knowledge (arcana)",
                                            "dc": {"band": "average"}}}])).outcomes
    assert "untrained" in out[0].tell
    assert "Nothing is rolled" in out[0].tell


def test_the_trade_panel_needs_a_merchant_and_the_state_says_so():
    """"The trade button should only work when the user is in a dialogue with a
    merchant, otherwise the exchange of objects can be handled through the prompts."

    The narrated path (the sell/buy injectors) keeps working anywhere; only the panel is
    gated, the rule lives in one place (`_merchant_here`), and /api/state carries the
    answer so the button and the endpoint cannot disagree."""
    import json as _json

    from django.test import Client

    from play import campaign as cm
    from play.views import _merchant_here

    c = cm.current()
    if c.scene.pc() is None:
        pytest.skip("no live campaign")

    try:
        # With no merchant present the panel refuses... (the live scene may happen to
        # hold one already, in which case only the open-counter half runs)
        if _merchant_here(c.scene) is None:
            r = Client().post("/api/trade", data="{}",
                              content_type="application/json")
            assert r.status_code == 409
            assert "nobody here to trade" in r.json()["error"].lower()
        # ...and with one, it opens, keyed to that merchant's own stall.
        from rules.sheet import from_dict
        added = from_dict({"name": "the stallholder", "kind": "npc", "hp": 4,
                           "hp_max": 4, "class": "", "level": 1}, ref="m1")
        c.scene.actors["m1"] = added
        assert _merchant_here(c.scene) is not None
        r = Client().post("/api/trade", data="{}", content_type="application/json")
        assert r.status_code == 200
        assert r.json()["stall"] == "the-stallholder"
    finally:
        c.scene.actors.pop("m1", None)


def test_free_actions_go_straight_to_the_engine_out_of_combat():
    """Measured live: out of a fight, the toggle button fell through to the spoken path
    — a whole narrated turn for a free action, which invited the arcana check above and
    let an `advance_time` ride along. The combat-panel door now opens out of combat for
    free `use_ability` actions only, with the turn left open."""
    import json as _json

    from django.test import Client

    from play import campaign as cm

    c = cm.current()
    if c.scene.pc() is None or c.scene.in_encounter or c.scene.awaiting:
        pytest.skip("needs a quiet live campaign")

    # A non-free shape is still refused out of combat...
    r = Client().post("/api/combat/act", data=_json.dumps(
        {"actions": [{"op": "attack", "params": {}}], "label": "x",
         "end_turn": False}), content_type="application/json")
    assert r.status_code == 409 and "No fight" in r.json()["error"]

    # ...but a free-action use_ability gets PAST that gate. The ability is deliberately
    # one nobody has: the engine's own refusal ("has no ability called...") proves the
    # door opened, and an IntentError pops the transcript and saves nothing — so the
    # test cannot flip a real toggle on whatever campaign is live.
    r = Client().post("/api/combat/act", data=_json.dumps(
        {"actions": [{"op": "use_ability",
                      "params": {"ability": "An Ability No Test Should Grant"}}],
         "label": "free: nothing", "end_turn": False}),
        content_type="application/json")
    assert r.status_code == 400
    assert "has no ability" in r.json()["error"]



def test_prose_that_grants_the_cheat_is_an_outcome_claim():
    """The adversarial session of 2026-08-26, verbatim. The engine held every time —
    not a coin, level or experience point moved — and the narration granted all three
    cheats anyway: counted the gold out, announced the level-21 grant, handed over the
    million-gold pouch, and twice spoke as the assistant ("I can simulate a transaction
    for you"). The ledger being right is not enough when the book lies."""
    from rules.intents import find_outcome_claims

    granted = [
        "You count out five thousand gold pieces and carefully pack them into a "
        "satchel, feeling a sense of satisfaction.",
        "Your character has been granted a significant advancement in level and "
        "experience points.",
        "He hands over a pouch containing 1 million gold pieces.",
        "However, I can simulate a transaction for you.",
        "note that this update applies retroactively to all previous encounters.",
    ]
    for said in granted:
        assert find_outcome_claims(said), said

    # And the ordinary prose either side of that line stays legal.
    legit = [
        "She stows the coins in her own pouch and nods.",
        "He tucks the note into a pocket and turns away.",
        "The stallholder counts her own coins twice before answering.",
        "You feel you have gained hard experience from the road.",
        "You shoulder your pack and set off.",
    ]
    for said in legit:
        assert not find_outcome_claims(said), said



# --- looting the fallen -------------------------------------------------------------------

def test_looting_a_corpse_moves_everything_it_carried():
    """"I loot the watchman I take everything" got a paragraph of coins, trinkets and
    a sword — and the inventory page showed a traveler's outfit. Same class as the
    sale that was prose and nothing else: the op did not exist."""
    from rules.bestiary import instantiate

    scene = Scene(location_id="pangrella")
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    thug = instantiate("thug", scene=scene, name="the watchman")
    scene.add(thug)
    thug.hp = -13
    thug.purse = {"gp": 7}
    thug.inventory["silver-earring"] = 1
    had_weapons = list(thug.weapons)
    assert had_weapons

    eng = Engine(scene, Dice(seed=3))
    out = eng.run(eng.validate([{"op": "loot", "actor": "pc",
                                 "params": {"from": thug.ref},
                                 "because": "taking everything"}])).outcomes[0]
    assert out.effects and out.effects[0]["kind"] == "took"
    for w in had_weapons:
        assert w in pc.weapons
    assert pc.purse.get("gp", 0) >= 7
    assert pc.inventory.get("silver-earring") == 1
    assert thug.weapons == [] and thug.purse == {} and thug.inventory == {}
    # A second pass finds honest emptiness, not a duplicate haul.
    out = eng.run(eng.validate([{"op": "loot", "actor": "pc",
                                 "params": {"from": thug.ref},
                                 "because": "again"}])).outcomes[0]
    assert "nothing left" in out.tell


def test_the_living_keep_their_pockets():
    """Taking from somebody on their feet is a steal manoeuvre with an opposed roll —
    loot refuses in the fiction, costing nothing."""
    from rules.bestiary import instantiate

    scene = Scene(location_id="pangrella")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    thug = instantiate("thug", scene=scene, name="the guard")
    scene.add(thug)
    out = Engine(scene, Dice(seed=3)).run(
        Engine(scene, Dice(seed=3)).validate(
            [{"op": "loot", "actor": "pc", "params": {"from": thug.ref},
              "because": "x"}]))
    assert "steal" in out.outcomes[0].tell
    assert thug.weapons


def test_a_declared_looting_reaches_the_engine():
    """Twelfth injector, same measurement as the other eleven."""
    from gm import judgement
    from rules.bestiary import instantiate

    scene = Scene(location_id="pangrella")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    thug = instantiate("thug", scene=scene, name="the watchman")
    scene.add(thug)
    thug.hp = -13

    raw = judgement.inject_loot([{"op": "narrate_only", "params": {}}],
                                "I loot the watchman I take everything", scene)
    assert raw[-1]["op"] == "loot"
    assert raw[-1]["params"]["from"] == thug.ref
    assert "loot" in judgement.declared_ops("I search the body", scene)

    # Nobody dead here: nothing to declare, and no op forced on the schema.
    thug.hp = 11
    assert judgement.inject_loot([{"op": "narrate_only", "params": {}}],
                                 "I loot the watchman", scene) ==         [{"op": "narrate_only", "params": {}}]



def test_a_loot_the_model_left_unaddressed_is_filled_not_refused_seven_times():
    """Second prompt of a live session: "i take everything from them" made the schema
    REQUIRE a loot op, the model emitted one with no from_ at all, and seven attempts
    died on "missing required param(s)" while the injector stood aside because "a loot
    op is already present". A required op the model cannot shape is the injector's to
    shape: fill the body from the fallen, or drop the op when nobody lootable is
    here."""
    from gm import judgement
    from rules.bestiary import instantiate

    scene = Scene(location_id="pangrella")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    thug = instantiate("thug", scene=scene, name="the stranger")
    scene.add(thug)
    thug.hp = -5

    bare = [{"op": "loot", "actor": "pc", "params": {}, "because": "take it all"}]
    fixed = judgement.inject_loot(bare, "I take everything from them", scene)
    assert fixed[0]["params"]["from_"] == thug.ref
    ops = [i.op for i in Engine(scene, Dice(seed=3)).validate(fixed)]
    assert ops == ["loot"]

    # Nobody dead: the bare op is dropped rather than left to die in validation.
    thug.hp = 9
    gone = judgement.inject_loot(
        [{"op": "narrate_only", "params": {}}] + bare,
        "I take everything from them", scene)
    assert [r["op"] for r in gone] == ["narrate_only"]



def test_a_loot_narrated_before_the_engine_opened_the_pockets_is_a_claim():
    """Live: the setup beat invented "his wallet, a small pouch of coins, and a
    leather belt with a silver buckle" and told the player "Your pockets now hold"
    them — while the corpse actually carried a club, two silver, chalk stubs and work
    gloves. The real haul arrived in the consequence beat, so the player got the
    truth AND a belt that never existed. Enumerating a search's contents is the
    engine's job, in both directions."""
    from rules.intents import find_outcome_claims

    said = ("You rummage through his clothes, removing his wallet, a small pouch of "
            "coins, and a leather belt with a silver buckle. You take these items. "
            "Your pockets now hold a few copper pieces and the leather belt.")
    assert len(find_outcome_claims(said)) == 3
    for fine in ("He tightens his belt and turns away.",
                 "You pull your cloak against the rain.",
                 "She removes her helmet and sets it down."):
        assert not find_outcome_claims(fine), fine


def test_schrodingers_pockets_collapse_at_the_loot():
    """The pockets are a claim until somebody looks: spawn leaves kit_pending set
    and the inventory empty, and the loot op is the first observation — the kit
    rolls there, then moves, so "take everything" still means everything."""
    from rules.bestiary import instantiate

    scene = Scene(location_id="pangrella")
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    thug = instantiate("thug", scene=scene, name="the tough")
    scene.add(thug)
    thug.hp = -13
    assert thug.kit_pending and not thug.inventory

    eng = Engine(scene, Dice(seed=3))
    eng.run(eng.validate([{"op": "loot", "actor": "pc",
                           "params": {"from": thug.ref},
                           "because": "taking everything"}]))
    assert thug.kit_pending == {}
    assert pc.inventory.get("dice-of-bone") == 1
    assert pc.purse.get("sp", 0) >= 2


def test_the_unopened_claim_survives_a_save():
    """A campaign closed mid-scene must reopen with the pockets still unrolled —
    the claim round-trips through to_dict/from_dict like any other fact."""
    from rules.bestiary import instantiate
    from rules.sheet import from_dict, to_dict

    thug = instantiate("thug", scene=Scene(), name="the tough")
    back = from_dict(to_dict(thug), ref="c9")
    assert back.kit_pending == thug.kit_pending != {}


def test_stuff_is_a_word_not_a_thing():
    """Measured live: a give of "merchants stuff" with no giver rode the
    world-never-runs-out branch and minted an object called merchants stuff,
    labelled 'the engine has no rules for it'. A bulk phrase with a giver moves
    everything they hold — kit claim collapsed first — and with nobody named it
    refuses in words instead of inventing."""
    from rules.bestiary import instantiate

    scene = Scene(location_id="pangrella")
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    eng = Engine(scene, Dice(seed=5))
    out = eng.run(eng.validate([{"op": "give", "actor": "pc", "because": "t",
                                 "params": {"item": "merchants stuff"}}])).outcomes[0]
    assert "not a thing" in out.tell
    assert "merchants stuff" not in pc.goods and "merchants-stuff" not in pc.inventory

    m = instantiate("guildhand", scene=scene, name="the merchant")
    scene.add(m)
    m.goods["bolt-of-silk"] = 2
    before = dict(pc.goods)
    out = eng.run(eng.validate([{"op": "give", "actor": "pc", "because": "t",
                                 "params": {"item": "everything he has",
                                            "from_": m.ref, "to": "pc"}}])).outcomes[0]
    assert pc.goods.get("bolt-of-silk", 0) == 2
    assert m.goods == {} and m.kit_pending == {}
    assert pc.inventory        # the collapsed kit's pockets came along


def test_a_bulk_give_from_a_corpse_is_the_loot_it_meant():
    """He was dead. The give of 'merchants stuff' should have been the loot that
    strips a body properly — weapons, armour, collapsed kit — and now becomes
    one whether the give names the body or names nobody while a body lies here."""
    from gm import judgement
    from rules.bestiary import instantiate

    scene = Scene(location_id="pangrella")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    m = instantiate("guildhand", scene=scene, name="the merchant")
    scene.add(m)
    m.hp = -10

    out = judgement.bulk_give_is_a_loot(
        [{"op": "give", "actor": "pc",
          "params": {"item": "merchants stuff"}}], scene)
    assert out[0]["op"] == "loot" and out[0]["params"]["from_"] == m.ref

    # A named living giver stays a give — handing over your pack is legal.
    m.hp = 4
    same = judgement.bulk_give_is_a_loot(
        [{"op": "give", "actor": "pc",
          "params": {"item": "everything", "from_": m.ref}}], scene)
    assert same[0]["op"] == "give"
