"""Every keeper's price moves with how they feel about you (owner ruling 2026-11-13: "yes
make shop prices move with attitude too", after the berth's fare did).

Before: a counter's prices moved only with the law's markup and a haggle won; a keeper who
liked the player charged a stranger's price, and an unfriendly one refused outright. Now
one number (`tradecraft.counter_terms`: the keeper's attitude and thrift, `pricing.
seller_terms`, plus the day's haggle, capped at 25% either way) is read by what they
charge (`buy_price`), what they pay (`sell_price`, the same steps the other way), the
trade panel, a commission's bill and a berth. Unfriendly trades dearer; hostile refuses.
"""
from __future__ import annotations

import pytest

from rules import attitude, market, pricing, tradecraft
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/pangrella-campaign.json")
TOWN = "5bbd0c40345f"


def _table():
    s = Scene(location_id=TOWN)
    pc = s.add(load_pc("fixtures/pc-thessaly.json"))
    pc.purse = {"gp": 500}
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    ama = s.add(instantiate("guildhand", scene=s, name="Ama"))
    # Middling thrift, so attitude alone moves the price (a seeded score would not be).
    s.population = {"p1": {"id": "p1", "ref": ama.ref, "life": {"axes": {"thrift": 50}}}}
    return s, e, pc, ama


def _run(e, raw):
    res = e.run(e.validate([{"actor": "pc", "because": "test", **raw}]))
    return res.outcomes[-1]


def _thing(s, pc):
    shelf = market.on_sale(s.location_id, "ama", market.day_of(s.clock_minutes),
                           s.market_taken)
    return next(m for m in shelf if pricing.worth(m, buyer=pc, town=s.location_id) >= 10)


@pytest.mark.parametrize("regard,factor,said", [
    (40, 1.00, ""),
    (60, 0.95, "Ama likes you: 5% off"),
    (80, 0.90, "Ama would do you a good turn: 10% off"),
    (20, 1.10, "Ama does not like you: 10% over"),
])
def test_what_a_keeper_charges_moves_with_their_regard(regard, factor, said):
    """Measured before: a friendly and an indifferent keeper charged the same coin."""
    s, e, pc, ama = _table()
    attitude.set_regard(ama, regard, "test")
    thing = _thing(s, pc)
    worth = round(pricing.worth(thing, buyer=pc, town=s.location_id), 2)
    out = _run(e, {"op": "buy", "params": {"item": thing.id, "from_": ama.ref,
                                           "stall": "ama"}})
    assert out.effects[0]["paid_cp"] == int(round(round(worth * factor, 2) * 100)), out.tell
    assert (said in out.tell) if said else "(Ama" not in out.tell, out.tell


@pytest.mark.parametrize("regard,cp,said", [
    (40, 50, ""), (60, 53, "Ama likes you: 5% more"), (20, 45, "Ama does not like you: 10% less"),
])
def test_what_a_keeper_pays_moves_the_other_way_by_the_same_steps(regard, cp, said):
    """A coil of rope is 1 gp; a shop pays half (CRB p.140), 50 cp to a stranger. A friend
    pays 5% more (52.5 cp, 53 as the till rounds), somebody disliked 10% less."""
    s, e, pc, ama = _table()
    attitude.set_regard(ama, regard, "test")
    pc.goods["rope"] = 1
    out = _run(e, {"op": "sell", "params": {"item": "rope", "to": ama.ref, "stall": "ama"}})
    assert out.effects[0]["paid_cp"] == cp, out.tell
    assert (said in out.tell) if said else "(Ama" not in out.tell, out.tell


def test_a_hostile_keeper_will_not_deal_and_an_unfriendly_one_does():
    s, e, pc, ama = _table()
    thing = _thing(s, pc)
    attitude.set_regard(ama, 5, "test")
    out = _run(e, {"op": "buy", "params": {"item": thing.id, "from_": ama.ref,
                                           "stall": "ama"}})
    assert out.status == "refused" and "will not deal" in out.tell, out.tell
    pc.goods["rope"] = 1
    out = _run(e, {"op": "sell", "params": {"item": "rope", "to": ama.ref, "stall": "ama"}})
    assert out.status == "refused" and pc.goods["rope"] == 1
    attitude.set_regard(ama, 20, "test")
    out = _run(e, {"op": "buy", "params": {"item": thing.id, "from_": ama.ref,
                                           "stall": "ama"}})
    assert out.status != "refused" and out.effects[0]["kind"] == "bought", out.tell


def test_regard_and_a_haggle_add_and_stop_at_a_quarter_either_way():
    s, e, pc, ama = _table()
    day = market.day_of(s.clock_minutes)
    s.dealings[tradecraft.dealing_key("haggle", pc.ref, s.location_id, "ama", day)] = \
        {"percent": 20}
    attitude.set_regard(ama, 80, "test")
    assert tradecraft.counter_terms(s, pc, ama, s.location_id, "ama", day)[0] == 25
    attitude.set_regard(ama, 5, "test")
    s.dealings.clear()
    s.population["p1"]["life"]["axes"]["thrift"] = 100
    assert tradecraft.counter_terms(s, pc, ama, s.location_id, "ama", day) \
        == (-25, ["cannot stand you", "is tight-fisted"])


def test_the_panel_shows_the_price_the_buy_charges(tmp_path):
    """One number: the trade panel's shelf price for a friendly keeper is what the buy op
    then takes, and the panel names why."""
    from django.test import Client, override_settings

    from play import campaign as cm
    from play.views import _merchant_here

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.end_encounter()
        c.scene.location_id = TOWN
        c.engine().place_party(f"{TOWN}~urban:the-market")
        c.save()
        keeper = _merchant_here(c.scene)
        assert keeper is not None
        plain = Client().post("/api/trade", data="{}", content_type="application/json").json()
        attitude.set_regard(keeper, 60, "test")
        c.save()
        warm = Client().post("/api/trade", data="{}", content_type="application/json").json()
        assert "likes you" in warm["terms"]
        before = {r["id"]: r["gp"] for r in plain["theirs"]}
        pct, _why = tradecraft.counter_terms(c.scene, c.scene.pc(), keeper, warm["place"],
                                            warm["stall"], warm["day"])
        for r in warm["theirs"]:
            assert r["gp"] < before[r["id"]] or before[r["id"]] < 0.2, (r, before[r["id"]])
        row = max(warm["theirs"], key=lambda r: r["gp"])
        c.scene.pc().purse = {"gp": 10_000}
        res = c.engine().run(c.engine().validate([{
            "op": "buy", "actor": "pc", "because": "t",
            "params": {"item": row["id"], "from_": keeper.ref, "stall": warm["stall"]}}]))
        out = res.outcomes[-1]
        assert out.effects[0]["paid_cp"] == int(round(row["gp"] * 100)), (out.tell, row)
        cm._LIVE.clear()
