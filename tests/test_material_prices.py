"""What a raw material may cost: one rule over every craft catalogue.

The owner, 2026-10-05, after the shops lane priced 22 unpriced staples at their nearest
priced sibling (1 gp, water 1 cp): "probably most are fine until we get to enchanting
essences, catalysts, and neutralizers and those should cost more. Also if something is
legendary or gives better multipliers it should cost more".

Measured before this, over the 434 authored prices in content/materials (magic-items.json
aside, whose prices are the book's formulas):
- the alchemist's common catalysts (brewer's yeast 1 gp, mother of vinegar 1, rennet 2)
  and its three neutralizers (willow charcoal, fuller's earth, slaked lime, all 1 gp) sat
  at the price of the water, the vinegar and the oak bark on the same counter;
- slaked lime, a strength-2 neutralizer, cost exactly what the strength-1 ones did;
- two rare dyes (dragon's blood crimson 75 gp, shadow black 90) cost less than the
  uncommon murex purple (120), and two rare enchanting vessels (ring, wand: 100 gp) less
  than the uncommon cloak vessel (200).

The rule (`pricing.material_floor`): rung ×5 per step (PF1e's gem grades and trade metals
step ×5 and ×10), ×5 for an essence, catalyst, ink, chalk, focus or neutralizer (Ultimate
Campaign prices Magic capital at 5× Goods), × the row's strength above its rung — and no
inversions. Checked on load, never derived over an authored price.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from rules import goods, market, pricing
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

TOWN = "panthcove"


def _rows(craft: str) -> list[dict]:
    path = Path("content/materials") / f"{craft}-materials.json"
    return json.loads(path.read_text(encoding="utf-8"))["materials"]


def _row(craft: str, mid: str) -> dict:
    return copy.deepcopy(next(r for r in _rows(craft) if r["id"] == mid))


def _priced(craft: str, mid: str, price) -> list[dict]:
    rows = copy.deepcopy(_rows(craft))
    for r in rows:
        if r["id"] == mid:
            r["price_gp"] = price
    return rows


# --- the shipped catalogues obey the rule ---------------------------------------------------

def test_every_shipped_catalogue_obeys_the_price_rule():
    """Twenty refusals before this lane's data pass (eleven under a floor, nine inversions);
    none after it. The gate a new row has to pass."""
    assert market.price_problems() == []


def test_catalysts_and_neutralizers_cost_more_than_the_staples_beside_them():
    """The owner's list, measured at 1-2 gp beside water (1 cp), vinegar (1 gp) and oak
    bark (1 gp) on the same counters. Each is now at least the kind factor times the
    common rung — five times the plainest staple."""
    plain = max(pricing.worth(_row("alchemist", m))
                for m in ("white-vinegar", "distilled-water", "rock-salt"))
    for mid in ("brewers-yeast", "mother-of-vinegar", "rennet",
                "willow-charcoal", "fullers-earth", "slaked-lime"):
        row = _row("alchemist", mid)
        assert pricing.is_power_kind(row), mid
        assert pricing.worth(row) >= pricing.POWER_KIND_FACTOR * plain, (mid, row["price_gp"])
    assert pricing.worth(_row("enchanter", "white-chalk")) >= pricing.POWER_KIND_FACTOR


def test_the_cheap_staples_stay_cheap():
    """"Probably most are fine": the shops lane's 22 staples and the owner's own list —
    water, vinegar, alcohol, charcoal, bark — keep their prices. The rule's common rung
    is 1 gp and water is the free token (1 cp, `goods.FREE_AT_A_COUNTER_GP`)."""
    expect = {("blacksmith", "water"): 0.01, ("blacksmith", "charcoal"): 1,
              ("blacksmith", "coal"): 1, ("blacksmith", "peat"): 1,
              ("blacksmith", "quenching-brine"): 1, ("blacksmith", "limestone"): 1,
              ("alchemist", "white-vinegar"): 1, ("alchemist", "strong-spirits"): 2,
              ("alchemist", "natron"): 1, ("alchemist", "rock-salt"): 1,
              ("leatherworker", "oak-bark"): 1, ("leatherworker", "sinew-thread"): 1,
              ("leatherworker", "curing-salt"): 1, ("leatherworker", "tawing-alum"): 2}
    got = {k: _row(*k)["price_gp"] for k in expect}
    assert got == expect


def test_the_ladder_climbs_and_the_kind_factor_is_the_books_magic_ratio():
    """A legendary floor under a rare one would let "legendary" cost less by rule.
    Ultimate Campaign Table 2-1: Magic capital 100 gp, Goods 20 gp — five to one."""
    ladder = [pricing.MATERIAL_FLOOR_GP[t] for t in
              ("common", "uncommon", "rare", "exotic", "legendary")]
    assert ladder == sorted(ladder) and len(set(ladder)) == 5
    assert pricing.POWER_KIND_FACTOR == 100 / 20


# --- refused with the fix named -------------------------------------------------------------

def test_a_catalyst_priced_like_water_is_refused_with_the_fix_named():
    """Brewer's yeast at 1 gp, as it shipped."""
    problems = pricing.material_price_problems(_priced("alchemist", "brewers-yeast", 1))
    assert any(p.startswith("brewers-yeast is a common catalyst at 1 gp")
               and "raise its price_gp to at least 5" in p for p in problems), problems


def test_a_stronger_neutralizer_at_the_same_price_is_refused():
    """Slaked lime neutralizes at strength 2 and cost the 1 gp the strength-1 ones did:
    a better multiplier costs more, strictly."""
    rows = _priced("alchemist", "slaked-lime", 5)
    problems = pricing.material_price_problems(rows)
    assert any("slaked-lime is a common salt at 5 gp, under its floor of 10 gp" in p
               and "x2 for its strength" in p for p in problems), problems
    assert any(p.startswith("slaked-lime has neutralizer 2 against")
               and "raise slaked-lime above 5 gp" in p for p in problems), problems
    assert pricing.worth(_row("alchemist", "slaked-lime")) \
        > pricing.worth(_row("alchemist", "fullers-earth"))


def test_a_rarer_dye_cheaper_than_a_commoner_one_is_refused():
    """Dragon's blood crimson (rare) shipped at 75 gp against murex purple (uncommon) at
    120: a rarer thing that cost less."""
    problems = pricing.material_price_problems(
        _priced("leatherworker", "dragons-blood-crimson", 75))
    assert any(p.startswith("dragons-blood-crimson is a rare dye at 75 gp, cheaper than "
                            "the uncommon murex-purple at 120 gp")
               and "Raise dragons-blood-crimson to at least 120 gp" in p
               for p in problems), problems


def test_a_legendary_priced_under_its_rung_is_refused():
    """"If something is legendary ... it should cost more": a legendary essence at a rare
    price is under the legendary floor (625 gp × 5 for an essence)."""
    problems = pricing.material_price_problems(_priced("enchanter", "vorpal-essence", 1800))
    assert any(p.startswith("vorpal-essence is a legendary essence at 1800 gp, under its "
                            "floor of 3125 gp") for p in problems), problems


def test_the_free_token_frees_only_a_plain_common_thing():
    """Water at 1 cp is the free token a counter needs (0 reads as "no price"). A
    catalyst at 1 cp is not free; it is mispriced."""
    assert not pricing.material_price_problems([_row("blacksmith", "water")])
    yeast = dict(_row("alchemist", "brewers-yeast"), price_gp=goods.FREE_AT_A_COUNTER_GP)
    assert pricing.material_price_problems([yeast])


def test_book_prices_are_not_held_to_the_house_ladder():
    """Cold iron (uncommon) is 4 gp a bar against copper's 5 (common) because the book says
    so — ×2 iron, and iron is a fifth of copper's trade price. A printed price is not a
    house rung; unmark it and the rule would refuse it."""
    rows = _rows("blacksmith")
    assert not pricing.material_price_problems(rows)
    unmarked = copy.deepcopy(rows)
    for r in unmarked:
        if r["id"] == "cold-iron":
            r["book"] = False
    assert any(p.startswith("cold-iron is an uncommon metal at 4 gp, cheaper than")
               for p in pricing.material_price_problems(unmarked))


def test_the_masterwork_vessels_carry_the_books_surcharge():
    """The Core Rulebook's masterwork surcharges: +300 gp a weapon, +150 armour and a
    shield. Marked book so the ladder does not hold them, which is what let the ring and
    wand vessels (rare) be lifted to the uncommon cloak vessel's 200 rather than to 300."""
    vessels = {r["id"]: r for r in _rows("enchanter") if r["kind"] == "vessel"}
    assert {k: (v["price_gp"], v.get("book")) for k, v in vessels.items()
            if k.startswith("masterwork-") and k != "masterwork-cloak-vessel"} == {
        "masterwork-weapon-vessel": (300, True), "masterwork-armour-vessel": (150, True),
        "masterwork-shield-vessel": (150, True)}
    assert vessels["ring-vessel"]["price_gp"] >= vessels["masterwork-cloak-vessel"]["price_gp"]


def test_a_bad_price_refuses_the_market_on_load(monkeypatch):
    """Checked where the counters are opened, not only in this file: `lines_doc`, which
    every counter reads first, refuses a catalogue that breaks the rule."""
    bad = _priced("alchemist", "brewers-yeast", 1)
    real = market._catalogue_rows
    monkeypatch.setattr(market, "_catalogue_rows",
                        lambda craft: bad if craft == "alchemist" else real(craft))
    monkeypatch.setattr(market, "_LINES", None)
    with pytest.raises(ValueError, match="brewers-yeast is a common catalyst at 1 gp"):
        market.lines_doc()


# --- the counter charges it, and buys back by it --------------------------------------------

def test_the_alchemists_counter_charges_the_checked_price_and_pays_half_back():
    """Bought across the counter at the rule-checked price, and what a shop would pay for
    the same row is half of that same number (`SHOP_BUYS_AT`) — one price, both ways.
    Before: 1 gp in, 50 cp back, for a catalyst."""
    shelf = {getattr(m, "id", ""): m for m in market.on_sale(
        TOWN, "market:alchemist", 0, {}, counter_kind="market:alchemist")}
    for mid in ("brewers-yeast", "slaked-lime", "fullers-earth"):
        good = shelf[mid]
        price = float(_row("alchemist", mid)["price_gp"])
        assert pricing.worth(good) == price
        assert pricing.what_a_shop_pays(good) == round(price * pricing.SHOP_BUYS_AT, 2)

    s = Scene(location_id=TOWN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = 10 * 60
    eng = Engine(s, Dice(seed=3))
    pc = s.actors["pc"]
    pc.purse, pc.inventory = {"gp": 50}, {}
    out = eng.run(eng.validate([{"op": "buy", "actor": "pc", "because": "a catalyst",
                                 "params": {"item": "brewers-yeast", "count": 2,
                                            "stall": "market:alchemist"}}]))
    bought = [e for o in out.outcomes for e in o.effects if e.get("kind") == "bought"]
    assert bought and bought[0]["paid_cp"] == 2 * 500, bought
    assert pc.inventory.get("brewers-yeast") == 2


def test_a_copper_price_survives_every_loader():
    """Water is 0.01 gp (1 cp). The alchemist and enchanter loaders read `price_gp` with
    `int()`, so through them water cost 0, free, while the counter (the blacksmith
    loader) said 1 cp: found by the pricing lane, 2026-10-05. The alchemist's shelf reads
    through the one door since alchemy lane F, and its own copper row (the wooden rod)
    survives it too."""
    from rules import alchemist, enchanter

    assert alchemist.materials()["water"].price_gp == 0.01
    assert alchemist.materials()["wooden-rod"].price_gp == 0.01
    assert alchemist.materials()["distilled-water"].price_gp == 1
    assert isinstance(alchemist.materials()["distilled-water"].price_gp, int)
    assert enchanter.from_dict({"id": "probe", "name": "Probe", "price_gp": 0.05}).price_gp == 0.05
