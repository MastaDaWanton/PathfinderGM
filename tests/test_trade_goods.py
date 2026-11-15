"""Bulk trade goods along the world's trade routes (owner, 2026-11-14: "can i purchase
bulk trade goods per the traded commodities from world bible to sell for profit at the
destinations listed?" — "build both"; rules/trade.py, docs/trade-goods.md).

Before this the routes were loaded and fed only residency; a settlement's `sells` line
only flavoured a keeper's occupation; cargo nobody priced fell to `pricing.UNLISTED_GP`
(1.5 gp whatever it was); and a ship carried passengers and nothing else.
"""
from __future__ import annotations

import pytest

from rules import attitude, goods, journey, ships, trade
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

PANGRELLA = loader.load_cached("fixtures/pangrella-campaign.json")
AURVANTIS = loader.load_cached("fixtures/aurvantis-campaign.json")
SYNTHETIC = loader.load_cached("fixtures/synthetic-world.json")
# Mirabalos ships "Iron ore from nearby mines"; Zhilvarnia, across the water, wants iron.
MIRABALOS, ZHILVARNIA = "7ef5e373c993", "6953424c8a82"


def _at(place=MIRABALOS, gp=2000, seed=4):
    scene = Scene(location_id=place, clock_minutes=10 * 60)   # mid-morning: counters open
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    engine = Engine(scene, Dice(seed=seed), world=PANGRELLA)
    engine.place_party(f"{place}~urban:the-docks")
    pc.purse = {"gp": gp}
    return scene, engine, pc


def _do(engine, op, item, count=1, **params):
    engine._journeyed = ""
    res = engine.run(engine.validate(
        [{"op": op, "actor": "pc", "because": "trade",
          "params": {"item": item, "count": count, **params}}], origin="author:test"))
    return res.outcomes[-1]


def _sail(engine, to="Zhilvarnia"):
    engine._journeyed = ""
    res = engine.run(engine.validate(
        [{"op": "journey", "actor": "pc", "because": "passage", "params": {"to": to}}],
        origin="author:test"))
    return res.outcomes[-1]


# --- the book's price -------------------------------------------------------------------

@pytest.mark.parametrize("commodity,row", [
    ("tempered steel", "iron"), ("salt", "salt"), ("woven silk", "silk"),
    ("Woven Khy'vyr silk", "silk"), ("Turmoil-era tea blends.", "coffee"),
    ("Resonant crystal; high-quality winged livestock", "gold"), ("wool", "wool"),
    ("Kalixiri's prized Terraglaze ceramics.", "glass"), ("charcoal", "charcoal"),
    ("mercenary contracts", None), ("river tolls", None), ("poisons", None),
    ("a well-known black market", None), ("Shipwrights' specialized wood finishes", None),
])
def test_a_world_commodity_is_priced_as_the_nearest_book_row_or_not_at_all(commodity, row):
    """Every commodity in the three fixture worlds is free text, and until this every one
    of them priced as `UNLISTED_GP`. The engine table files each under a Core (or Ultimate
    Equipment) Trade Goods row by its first listed word; a service is never a good."""
    assert trade.row_for(commodity) == row


def test_every_row_is_the_books_price():
    """Spot-check the Core Rulebook's Table 6-3 rows (aonprd, fetched 2026-11-14)."""
    cp = {k: v[1] for k, v in trade.ROWS.items()}
    assert (cp["wheat"], cp["iron"], cp["salt"], cp["silk"], cp["gold"], cp["platinum"]) \
        == (1, 10, 500, 1000, 5000, 50000)
    assert cp["saffron"] == 1500 and cp["cow"] == 1000 and cp["linen"] == 400


def test_the_world_says_what_is_made_and_wanted_where():
    assert trade.supplied_at(PANGRELLA, MIRABALOS) == {"iron": "Iron ore from nearby mines"}
    assert "iron" in trade.demanded_at(PANGRELLA, ZHILVARNIA)
    assert trade.standing(PANGRELLA, MIRABALOS, "iron") == "supply"
    assert trade.standing(PANGRELLA, ZHILVARNIA, "iron") == "demand"
    # The route's own destination is named first.
    assert trade.sells_dear_in(PANGRELLA, "iron", MIRABALOS)[0] == "Elyrielle"


def test_todays_exports_offer_goods_somewhere_in_every_fixture_world():
    """World-agnostic: none of the asks in docs/for-world-bible.md (19-21) is needed."""
    for world in (PANGRELLA, AURVANTIS, SYNTHETIC):
        made = [s for s in world.play["settlements"] if trade.supplied_at(world, s["id"])]
        assert made, world


# --- the market moves, and comes back ---------------------------------------------------

def test_buying_then_selling_back_at_one_market_makes_nothing():
    """One curve for both directions: a round trip at one counter nets at most the
    rounding, so the only profit is in carrying the goods to where they are wanted."""
    scene, engine, pc = _at()
    before = goods.in_copper(pc.purse)
    _do(engine, "buy", "cargo:iron", 300)
    _do(engine, "sell", "cargo:iron", 300)
    assert 0 <= before - goods.in_copper(pc.purse) <= 2
    assert not trade.lots(scene)


def test_every_unit_bought_raises_the_next_and_the_market_runs_out():
    """Elite Dangerous shipped unlimited demand for its mining minerals and patched in a
    finite one in 2020: here a market has a base value's worth of stock (a city 8,000 gp:
    80,000 lb of iron) and the price climbs 0.8 -> 1.2 of the book across it."""
    scene, engine, pc = _at(gp=20000)
    first = trade.unit_now(scene, PANGRELLA, MIRABALOS, "iron")
    assert first == pytest.approx(8.0)
    vol = trade.volume(PANGRELLA, MIRABALOS, "iron")
    assert vol == 80000
    trade.record(scene, PANGRELLA, MIRABALOS, "iron", vol, buying=True)
    assert trade.unit_now(scene, PANGRELLA, MIRABALOS, "iron") == pytest.approx(12.0)
    assert trade.can_buy(scene, PANGRELLA, MIRABALOS, "iron") == 0
    out = _do(engine, "buy", "cargo:iron", 10)
    assert out.status != "ok" or "bought this market out" in out.tell, out.tell


def test_a_pushed_market_recovers_over_a_week():
    """Patrician's anchor: about a week of a town's consumption. Half the stock bought
    is a quarter after three and a half days and nothing after seven."""
    scene, engine, pc = _at()
    vol = trade.volume(PANGRELLA, MIRABALOS, "iron")
    trade.record(scene, PANGRELLA, MIRABALOS, "iron", vol // 2, buying=True)
    scene.clock_minutes += 24 * 60 * 7 // 2
    assert trade.pressure(scene, MIRABALOS, "iron", vol) == pytest.approx(vol / 2 - vol / 2,
                                                                        abs=vol / 7)
    scene.clock_minutes += 24 * 60 * 4
    assert trade.pressure(scene, MIRABALOS, "iron", vol) == 0


def test_two_small_buys_cost_what_one_big_one_does():
    scene, engine, pc = _at()
    big = trade.book_cp(scene, PANGRELLA, MIRABALOS, "iron", 200, buying=True)
    a = trade.book_cp(scene, PANGRELLA, MIRABALOS, "iron", 100, buying=True)
    trade.record(scene, PANGRELLA, MIRABALOS, "iron", 100, buying=True)
    b = trade.book_cp(scene, PANGRELLA, MIRABALOS, "iron", 100, buying=True)
    assert abs((a + b) - big) <= 1


# --- buying, where, and how much can be carried ----------------------------------------

def test_a_town_that_does_not_make_it_will_not_sell_it_and_names_who_does():
    scene, engine, pc = _at(place=ZHILVARNIA)
    out = _do(engine, "buy", "cargo:iron", 10)
    assert "Nobody here sells iron in bulk" in out.tell and "Mirabalos" in out.tell
    assert not trade.lots(scene)


def test_a_lot_is_the_partys_and_what_it_cannot_haul_waits_where_it_was_bought():
    """Weight is real: Kesst on foot carries her spare light load, and the rest is a lot
    `left` at Mirabalos — a state a hired guard can be set over."""
    scene, engine, pc = _at()
    out = _do(engine, "buy", "cargo:iron", 400)
    assert "That is all" not in out.tell
    assert "Iron ore" not in out.tell        # the book's row, not the world's prose
    assert "sells dear in" in out.tell and "Elyrielle" in out.tell
    lots = trade.lots(scene)
    assert sum(x["units"] for x in lots) == 400
    assert {x["owner"] for x in lots} == {pc.ref}
    haul = trade.haul_lb(scene)["lb"]
    assert trade.with_party_lb(scene) <= haul
    left = [x for x in lots if x["stowed"] == "left"]
    assert left and left[0]["at"] == MIRABALOS, lots
    assert "waits here" in out.tell


def test_a_mule_and_a_cart_haul_five_times_the_beasts_heavy_load():
    """CRB: a creature can drag five times its maximum load; a cart is 200 lb and needs
    one beast. A mule is a Large quadruped (x3 on the biped table)."""
    scene, engine, pc = _at()
    on_foot = trade.haul_lb(scene)["lb"]
    pc.purse = {"gp": 100}
    engine.place_party(f"{MIRABALOS}~urban:the-docks")
    from rules import goods as goods_mod

    mule = next(g for g in goods_mod.stables_goods() if g.key == "mule")
    goods_mod.deliver(scene, pc, mule)
    # A pack beast carries on a pack saddle (CRB; tests/test_merchant_road.py).
    goods_mod.deliver(scene, pc, next(g for g in goods_mod.stables_goods()
                                      if g.key == trade.PACK_SADDLE))
    beast = trade.haul_lb(scene)["lb"] + trade.PACK_SADDLE_LB
    assert beast > on_foot
    cart = next(g for g in goods_mod.stables_goods() if g.key == "cart")
    goods_mod.deliver(scene, pc, cart)
    hauled = trade.haul_lb(scene)
    assert "a cart" in hauled["how"]
    assert hauled["lb"] == pytest.approx(on_foot + 5 * (beast - on_foot) - 200)


def test_seller_attitude_moves_the_bulk_price_but_the_haggle_does_not():
    """Every price moves with the seller (0.3.2/0.3.3); trade goods are "exempt from
    bargaining" (Ultimate Campaign p.139), so a won haggle is not read here."""
    scene, engine, pc = _at()
    book = trade.book_cp(scene, PANGRELLA, MIRABALOS, "iron", 100, buying=True)
    keeper = load_pc("fixtures/pc-borin.json")
    keeper.ref = "k1"
    attitude.set_regard(keeper, 80, "test")
    percent, moved, markup = engine._cargo_terms(pc, keeper)
    assert percent >= 10 and "would do you a good turn" in moved and "% off" in moved
    assert markup == 1.0
    assert book > 0


# --- by sea: freight, the quay, the sale, the wreck ------------------------------------

def test_freight_rides_on_the_fare_and_sells_dear_across_the_water():
    """The whole trade: buy iron where it is mined, ship it as freight (a berth's rate
    for each 200 lb), land it on the quay and sell it where the world says it is wanted,
    for more than it cost."""
    scene, engine, pc = _at(gp=3000)
    leg = {l.to_id: l for l in journey.legs_from(PANGRELLA, MIRABALOS)}[ZHILVARNIA]
    bare = engine.passage_quote(leg)[2]
    _do(engine, "buy", "cargo:iron", 500)     # the op's bound is 500 a trade
    _do(engine, "buy", "cargo:iron", 500)
    paid = sum(x["paid_cp"] for x in trade.lots(scene))
    quoted = engine.passage_quote(leg)[2]
    assert quoted - bare == trade.freight_cp(1000, bare // ships.PASSAGE_CP_PER_MILE)         == bare // 2                            # half a ton pays half a berth
    booked = _sail(engine)
    assert "as freight" in booked.tell, booked.tell
    assert {x["stowed"] for x in trade.lots(scene)} == {"hold"}
    arrived = _sail(engine)
    while scene.location_id != ZHILVARNIA and engine.aboard() is not None:
        arrived = _sail(engine)
    assert scene.location_id == ZHILVARNIA, arrived.tell
    assert "swung onto the quay" in arrived.tell
    before = goods.in_copper(pc.purse)
    sold = _do(engine, "sell", "cargo:iron", 500)
    sold = _do(engine, "sell", "cargo:iron", 500)
    got = goods.in_copper(pc.purse) - before
    assert "wanted here" in sold.tell and "a profit of" in sold.tell, sold.tell
    freight = quoted - bare
    assert got > paid + freight, (got, paid, freight)
    assert not trade.lots(scene)


def test_a_wreck_takes_the_hold(monkeypatch):
    scene, engine, pc = _at(seed=9)
    _do(engine, "buy", "cargo:iron", 100)
    _sail(engine)
    monkeypatch.setattr(ships, "day_at_sea", lambda dice, level: "wreck")
    out = _sail(engine)
    assert not trade.lots(scene)
    assert "100 lb of iron" in out.tell, out.tell


def test_robbers_take_the_cargo_where_the_party_fell_and_it_stays_the_partys():
    """The robbery's own scene (tests/test_robbed_retrieval_quest.py): two street thugs
    beat Kesst down. Her 20 lb of iron goes with them, still hers by right and stolen,
    and is no longer hers to sell — the state a guard is hired to prevent."""
    import test_robbed_retrieval_quest as robbery

    def with_cargo(s, e, pc, gang):
        trade.add_lot(s, "iron", 20, pc.ref, 160, s.location_id)

    s, e, pc, gang, out, _quest = robbery._robbed(before=with_cargo)
    lot = trade.lots(s)[0]
    assert lot["stowed"] == "taken" and lot["held_by"] == gang[0].ref and lot["stolen"]
    assert lot["owner"] == pc.ref
    assert not trade.reachable(s)
    assert "20 lb of iron" in str(out), out


def test_a_toll_keeper_names_a_levy_on_the_cargo():
    scene, engine, pc = _at()
    assert trade.toll_cp(scene) == 0
    _do(engine, "buy", "cargo:iron", 20)
    assert trade.toll_cp(scene) == 5          # 20 lb at 1 sp is 200 cp; a fortieth


def test_cargo_and_the_markets_push_survive_a_save(tmp_path, settings):
    """Where the salt is, and how far the market was pushed, are things that happened:
    a reload that dropped them would hand the party its lots back at the quay for free
    or reset a bought-out market."""
    from play import campaign as cm

    settings.CAMPAIGN_DIR = tmp_path
    scene, engine, pc = _at()
    _do(engine, "buy", "cargo:iron", 400)
    c = cm.Campaign(id="cargo", world_source="fixtures/pangrella-campaign.json",
                    scene=scene)
    c.save()
    back = cm.Campaign.load(c.path())
    assert back.scene.cargo == scene.cargo and back.scene.cargo
    assert back.scene.trade_pressure == scene.trade_pressure


# --- what World Bible may export (docs/for-world-bible.md asks 19-21) -------------------

def test_a_route_that_describes_its_good_in_words_is_read_before_the_prose():
    """Ask 19: `good: {kind, worth}` settles the row, so prose like "river-borne trade
    goods" (no row today) becomes a good, and `service: true` takes one off the table."""
    assert trade.route_row({"commodity": "river-borne trade goods",
                            "good": {"kind": "food", "worth": "dear"}}) == "salt"
    assert trade.route_row({"commodity": "salt", "good": {"service": True}}) is None
    assert trade.route_row({"commodity": "salt"}) == "salt"


def test_a_route_that_says_how_much_moves_scales_its_markets():
    """Ask 20: `volume` "heavy" doubles the stock and appetite at both ends."""
    from types import SimpleNamespace

    base = trade.volume(PANGRELLA, MIRABALOS, "iron")
    heavy = SimpleNamespace(**{**PANGRELLA.__dict__, "trade_routes": [
        {**r, "volume": "heavy"} for r in PANGRELLA.trade_routes]})
    heavy.get = PANGRELLA.get
    assert trade.volume(heavy, MIRABALOS, "iron") == 2 * base


def test_a_settlement_that_lists_its_goods_is_read_before_its_one_line():
    """Ask 21: `goods.sells` / `goods.buys` rows, each a good in words."""
    from types import SimpleNamespace

    town = {"id": "x1", "name": "Saltby", "sells": "nothing much",
            "goods": {"sells": [{"name": "rock salt", "kind": "food", "worth": "dear"}],
                      "buys": [{"name": "timber", "kind": "timber", "worth": "cheap"}]}}
    world = SimpleNamespace(play={"settlements": [town]}, trade_routes=[],
                            get=lambda i: None)
    assert trade.supplied_at(world, "x1") == {"salt": "rock salt"}
    assert trade.demanded_at(world, "x1") == {"stone"}


def test_a_plan_that_names_the_good_buys_and_sells_it_in_bulk():
    """The reader's plan names the thing ("iron"), not the panel's `cargo:iron`: a town
    that makes it sells it by the unit when no shelf row is called that, and a lot the
    party has here is what a sale of it sells."""
    scene, engine, pc = _at()
    out = _do(engine, "buy", "iron", 10)
    assert sum(x["units"] for x in trade.lots(scene)) == 10, out.tell
    out = _do(engine, "sell", "iron", 10)
    assert not trade.lots(scene), out.tell


def test_a_stolen_lot_comes_back_when_its_holder_is_beaten_here():
    """Coordinator, 2026-11-14: the robbed lot must come back when the robbers holding it
    are beaten, killed or caught. Before it, `trade.robbed` marked the lot taken and
    nothing ever read it again: 20 lb of iron gone for good the moment Kesst went down.
    Measured on the holdings, as `defeat.settle` measures the coin: the robber is found
    (here, on his feet: it stays his), then put down (it is the party's again, owned by
    Kesst, no longer stolen)."""
    import test_robbed_retrieval_quest as robbery
    from rules import defeat

    def with_cargo(s, e, pc, gang):
        trade.add_lot(s, "iron", 20, pc.ref, 160, s.location_id)

    s, e, pc, gang, _out, _quest = robbery._robbed(before=with_cargo)
    holder = gang[0]
    defeat.settle(e)                                            # gone off stage: kept
    assert trade.lots(s)[0]["stowed"] == "taken"
    s.move(holder.ref, s.at)                                    # the party finds him
    assert holder.ref in s.actors
    defeat.settle(e)
    assert trade.lots(s)[0]["stowed"] == "taken", "a robber on his feet kept it"
    holder.take_damage(holder.hp + 20)
    outs = defeat.settle(e)
    lot = trade.lots(s)[0]
    assert lot["stowed"] == "party" and lot["owner"] == pc.ref
    assert "held_by" not in lot and "stolen" not in lot and lot["stolen_by"] == holder.ref
    assert trade.reachable(s, "iron")
    assert any("20 lb of iron" in o.tell and "theirs again" in o.tell for o in outs), outs


def test_a_robber_in_custody_gives_the_lot_up_too():
    import test_robbed_retrieval_quest as robbery
    from rules import defeat, states
    from rules.activeeffect import ActiveEffect

    def with_cargo(s, e, pc, gang):
        trade.add_lot(s, "iron", 20, pc.ref, 160, s.location_id)

    s, e, pc, gang, _out, _quest = robbery._robbed(before=with_cargo)
    holder = gang[0]
    s.move(holder.ref, s.at)
    holder.apply_effect(ActiveEffect(name="held by the watch", kind="situation",
                                     key="custody", source="test", origin="test",
                                     tags=(states.CUSTODY,)))
    defeat.settle(e)
    assert trade.lots(s)[0]["stowed"] == "party"
