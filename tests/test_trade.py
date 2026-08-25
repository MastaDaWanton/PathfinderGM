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
