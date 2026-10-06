"""Alchemy prices and shops (alchemy plan §12.4, §12.5, §5.9; contracts §1 row H).

Measured before this lane (build/alchemy c4e86f5, 2026-10-06):
- a brewed potion of haste was priced on the tier ladder, 60 gp against the book's 750
  (inv §0.4), because `pricing.worth` knew no book price for anything the bench made;
- a bought antitoxin was a jar with a name and no document ("the GM narrates"), and a
  bought alchemist's fire sold back for 0.19 gp — 1.5 gp ladder x the inert 0.25, halved;
- the alchemist's counter sold three of the CRB's eight alchemical goods, no alchemy manual
  (content/rules/alchemy-manuals.json did not exist: the 0.2.4 defect's shape, a craft's
  books on no counter), and no spell potion at all;
- under the formula table (lane E: formulae key on essences, never on materials), the
  cheapest legal set of BOUGHT inputs for a potion of haste was 3 gp (olive oil, beeswax, a
  glass vial) against the book's making cost of 375 — every 2nd- and 3rd-level potion came
  in at 2 to 32 gp, so brewing was a money machine the book's coin fraction closes.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import consumables, formulae, goods, knowledge, market, materials, places, pricing
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parents[1]
ALCHEMIST = "market:alchemist"


def _row(fid):
    row = formulae.get(fid)
    assert row is not None, fid
    return row


# --- what a product is worth ----------------------------------------------------------------

def test_a_brewed_spell_potion_sells_at_the_book_price_not_the_ladder():
    """A potion of haste priced 60 gp against the book's 750 (inv §0.4): the ladder knew no
    book price. Now 50 x 3 x 5 = 750, and a shop pays half, 375."""
    haste = Stock(base="Potion of Haste", tier="exotic", craft="alchemist",
                  holds_spell="haste", caster_level=5)
    assert pricing.worth(haste) == 750.0
    assert pricing.what_a_shop_pays(haste) == 375.0


def test_quality_reaches_a_spell_potion_only_through_caster_level():
    """Open point 6: quality raises caster level and the price follows it, with no second
    multiplier. A Fine haste (CL 6) is 900 gp, not 900 x 1.5; Crude stays at the book
    minimum and prices as Sound."""
    fine = Stock(base="Potion of Haste", craft="alchemist", holds_spell="haste",
                 caster_level=formulae.caster_level("haste", 2), quality=2)
    assert fine.caster_level == 6 and pricing.worth(fine) == 900.0
    crude = Stock(base="Potion of Haste", craft="alchemist", holds_spell="haste",
                  caster_level=formulae.caster_level("haste", 0), quality=0)
    assert pricing.worth(crude) == 750.0


def test_a_classic_is_its_book_price_times_the_quality_column():
    """Q4.4: book prices for book items, quality multiplying them (herbal-quality.json's
    price column: Crude x0.5, Sound x1, Fine x1.5)."""
    acid = goods.alchemy_stock("acid-flask")
    assert pricing.worth(acid) == 10.0
    assert pricing.worth(Stock(base="Acid", craft="alchemist", quality=2)) == 15.0
    assert pricing.worth(Stock(base="Acid", craft="alchemist", quality=0)) == 5.0
    # The bench's record (plan §12.2) names its formula and its quality index; it wins.
    assert pricing.worth({"formula": "alchemists-fire", "craft": "alchemist",
                          "name": "Fine Alchemist's Fire", "quality": "fine",
                          "quality_index": 2}) == 30.0


def test_an_old_bought_alchemists_fire_sells_for_half_its_price_not_two_silver():
    """A counter sold alchemist's fire for 20 gp as a jar with no craft written on it, and
    the ladder bought it back for 0.19 gp (1.5 x 0.25 inert, halved). An old save's jar is
    still the classic it was sold as."""
    old = Stock(base="alchemist's fire", tier="common", potency=1.0, craft="")
    assert pricing.what_a_shop_pays(old) == 10.0


def test_only_the_alchemists_products_take_a_book_price():
    """A scroll or a herbal jar holding a spell's name is not a potion, and a house
    compound (no formula) keeps the tier ladder: the book price is for book items."""
    scroll = Stock(base="Scroll of Haste", craft="enchanter", holds_spell="haste",
                   caster_level=5)
    assert pricing.alchemy_worth(scroll) is None
    tonic = Stock(base="Murky Tonic", craft="alchemist", tier="common")
    assert pricing.alchemy_worth(tonic) is None
    assert pricing.worth(tonic) == round(pricing.TIER_BASE["common"] * pricing.INERT_FACTOR, 2)
    herbal = Stock(base="Antitoxin", craft="herbalism")
    assert pricing.alchemy_worth(herbal) is None


# --- what making one costs ------------------------------------------------------------------

def test_the_making_cost_is_the_books_fraction():
    """CRB Craft: raw materials are a third of the price; Brew Potion: half. Haste 375,
    cure light wounds 25, alchemist's fire 6.67, acid 3.33; a Fine haste at CL 6 costs half
    of its 900."""
    assert pricing.making_cost("potion-of-haste") == 375.0
    assert pricing.making_cost("potion-of-cure-light-wounds") == 25.0
    assert pricing.making_cost("alchemists-fire") == 6.67
    assert pricing.making_cost("acid-flask") == 3.33
    assert pricing.making_cost("potion-of-haste", caster_level=6) == 450.0
    assert pricing.making_cost("no-such-formula") == 0.0


def test_the_cheapest_bought_inputs_were_far_under_the_book_and_the_coin_closes_it():
    """Measured: a 750 gp potion of haste from 3 gp of bought inputs, sold back for 375 —
    Skyrim's money machine. 48 of the 60 authored formulae came in under a fifth of their
    making cost. The bench takes the rest in coin (`coin_to_make`), so the whole bill of
    every formula product whose inputs are under lands exactly at the book's fraction."""
    shelf = materials.alchemy_shelf()
    haste = pricing.input_bill("potion-of-haste", shelf)
    assert haste["gp"] is not None and haste["gp"] <= 10, haste
    assert haste["allowance"] == 375.0
    authored = [f for f, r in formulae.all().items() if not r.get("derived")]
    cheap = 0
    for fid in authored:
        bill = pricing.input_bill(fid, shelf)
        if bill["gp"] is None:
            continue
        if bill["gp"] * 5 < bill["allowance"]:
            cheap += 1
        if not bill["over"]:
            whole = bill["gp"] + pricing.coin_to_make(fid, bill["gp"])
            assert whole == pytest.approx(bill["allowance"], abs=0.01), fid
    assert cheap >= 40, cheap


def test_coin_to_make_never_pays_the_alchemist_back():
    """An expensive input chosen on purpose (old recipes put azoth, 1,500 gp, in every
    3rd-level potion) costs what it costs; the coin is never negative, and a house compound
    takes none."""
    assert pricing.coin_to_make("potion-of-haste", 1500) == 0.0
    assert pricing.coin_to_make("potion-of-haste", 0) == 375.0
    assert pricing.coin_to_make(None, 0) == 0.0


# The formulae whose cheapest bought inputs still run over the book's fraction, and those
# whose essence no priced material carries. A RATCHET: it may only shrink. Each is one of
# the owner's open price choices, which live in content/materials (lane D's file): light is carried for money only by powdered silver (30 gp) and
# phosphorus (40 gp); binding by sal volatile (20 gp); thunder and storm by nothing priced
# (saltpetre, storm quartz, shocker lizard node are found, never sold); a 1 gp tindertwig or
# a 2 gp sunrod cannot come under a third of its price while the cheapest input is 1 gp,
# and no "stick" vessel exists for a tool at all.
OVER_AT_SHIP = {"tanglefoot-bag", "flash-powder", "alchemical-grease", "holy-weapon-balm",
                "sunrod", "tindertwig", "potion-of-protection-from-evil",
                "potion-of-snapdragon-fireworks", "potion-of-veil-of-heaven"}
UNBUYABLE_ESSENCES_AT_SHIP = {"thunder", "storm"}


def test_formulae_over_the_fraction_are_only_the_known_ones():
    """The 2026-10-06 measurement, as a ratchet: 9 of 485 formulae over the fraction, 42
    with an essence no counter sells (23 thunder, 20 storm). Before the formula table, the
    old recipe sets put 11 of the 18 classics and 25 of the 44 potions over (lane D's
    review: rectified spirits at 25 gp, azoth at 1,500)."""
    shelf = materials.alchemy_shelf()
    over, unbuyable = set(), set()
    for fid in formulae.all():
        bill = pricing.input_bill(fid, shelf)
        if bill["unbuyable"]:
            unbuyable |= set(bill["unbuyable"])
        elif bill["over"]:
            over.add(fid)
    assert over <= OVER_AT_SHIP, sorted(over - OVER_AT_SHIP)
    assert unbuyable <= UNBUYABLE_ESSENCES_AT_SHIP, sorted(unbuyable)


# --- the shop items are the same documents (Q8.3) -------------------------------------------

def test_every_gear_classic_is_its_formula_at_the_books_price():
    """The CRB's eight keep GEAR rows (the outfit page sells from GEAR); each is one formula
    and costs exactly its printed price — two copies of a price, held to one answer."""
    assert len(goods.CLASSIC_GEAR) == 8
    for key, fid in goods.CLASSIC_GEAR.items():
        assert key in goods.GEAR, key
        assert goods.GEAR[key]["cost_gp"] == _row(fid)["price_gp"], key
        assert _row(fid)["kind"] == "classic"


def test_a_bought_antitoxin_is_the_formulas_plus_five_not_a_narrated_jar():
    """A bought antitoxin had no document ("which the GM narrates"); a bought one is now the
    formula's +5 alchemical on Fortitude against poison for an hour, and drinking it
    produces the intent that grants it."""
    s = Scene(location_id="nowhere")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    goods.deliver(s, pc, goods.good("antitoxin"), 2)
    jar = next(st for st in pc.stock.values() if st.base == "Antitoxin")
    assert jar.count == 2 and jar.craft == "alchemist" and jar.quality == formulae.SOUND
    assert jar.specs == _row("antitoxin")["core"]
    use = consumables.plan(jar, "drink", "pc")
    assert not use.problems and use.intents, use.problems


def test_a_bought_flask_of_acid_can_be_thrown():
    """Q8.3: one item whether bought or made. A bought flask carries the book's 1d6 acid,
    and the throw door takes it."""
    s = Scene(location_id="nowhere")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    goods.deliver(s, pc, goods.good("acid"), 1)
    flask = next(st for st in pc.stock.values() if st.base == "Acid")
    assert flask.how == ["throw"]
    use = consumables.plan(flask, "throw", "c1")
    assert not use.problems and use.thrown and use.thrown["struck"], use.problems


def test_a_bought_potion_keeps_holds_spell_and_caster_level():
    """The enchanter's contract (contracts §6, tests/test_magicitem.py): every spell potion
    writes `holds_spell` and `caster_level`, bought ones too."""
    s = Scene(location_id="nowhere")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    good = next(g for g in goods.potion_goods() if g.key == "potion-of-invisibility")
    assert good.price_gp == 300.0
    goods.deliver(s, pc, good, 1)
    pot = next(st for st in pc.stock.values() if st.base == good.name)
    assert pot.holds_spell == "invisibility" and pot.caster_level == 3
    assert pricing.what_a_shop_pays(pot) == 150.0


def test_tindertwig_left_flint_and_steel():
    """Plan §12.5: gear.json's tindertwig line ("the engine has no fire or light to make")
    is replaced by the tool, which the light model now lights."""
    doc = json.loads((ROOT / "content/rules/gear.json").read_text(encoding="utf-8"))
    for row in doc["items"].values():
        assert "tindertwig" not in row.get("names", []), row["names"]
    twig = goods.alchemy_stock("tindertwig")
    assert twig.how == ["light"] and twig.specs[0]["type"] == "light"


# --- the alchemist's counter ----------------------------------------------------------------

def test_the_alchemists_counter_sells_the_classics_and_every_alchemy_manual():
    """The 0.2.4 defect was manuals on no counter. Every alchemy manual is a staple of the
    alchemist's shop, as is every classic formula (the CRB's 8 through GEAR, the rest as
    the alchemy-classics table), at its book price."""
    staples = {g.id: g for g in market.staples_of(ALCHEMIST)}
    books = knowledge.manuals(knowledge.ALCHEMIST)
    assert len(books) >= 6
    for mid, m in books.items():
        assert goods.PREFIXES["manual"] + mid in staples, mid
        assert staples[goods.PREFIXES["manual"] + mid].price_gp == float(m["price_gp"])
    classics = [f for f, r in formulae.all().items() if r.get("kind") == "classic"]
    geared = set(goods.CLASSIC_GEAR.values())
    for fid in classics:
        sid = (goods.GOOD_PREFIX + next(k for k, v in goods.CLASSIC_GEAR.items() if v == fid)
               if fid in geared else goods.PREFIXES["alchemy"] + fid)
        assert sid in staples, fid
        assert pricing.worth(staples[sid]) == _row(fid)["price_gp"], fid


def test_every_crafts_manuals_are_on_some_counter():
    """No craft's books on no counter, for any craft: every `*-manuals.json` is a table some
    shop or stall line sells."""
    sold = set()
    doc = market.lines_doc()
    for row in list(doc.get("shops") or ()) + list(doc.get("stalls") or ()):
        sold |= set(row.get("tables") or ())
    for path in (ROOT / "content/rules").glob("*-manuals.json"):
        table = path.stem
        assert table in goods.MANUAL_TABLES, table
        assert table in sold, table


def test_a_formularys_price_is_the_blank_book_and_the_writing():
    """A formulary's price is the book's, never authored: Ultimate Equipment's formula book
    (15 gp) plus the CRB's writing cost of each formula (5 gp a classic, 10 x level squared
    a spell). Every formula and every material a manual names exists."""
    shelf = materials.alchemy_shelf()
    for mid, m in knowledge.manuals(knowledge.ALCHEMIST).items():
        fs = m.get("formulae") or []
        for fid in fs:
            assert formulae.get(fid) is not None, (mid, fid)
        if fs:
            want = 15 + sum(formulae.copy_cost_gp(int(_row(f).get("spell_level") or 0))
                            for f in fs)
            assert m["price_gp"] == want, (mid, m["price_gp"], want)
        for t in m.get("teaches") or ():
            assert t["material"] in shelf, (mid, t)
        if m.get("teaches"):
            assert knowledge.manual_keys(m), mid
        assert fs or m.get("teaches"), mid


def test_the_alchemist_draws_spell_potions_inside_its_till():
    """Plan §12.5: potions on sale are spell potions at Sound quality and the book price,
    drawn under the market's existing rule (rarity quota, the till). None is harmful (a
    drunk potion's target is its drinker), and none costs more than the till holds."""
    day, place = 3, "laneh-town"
    shelf = market.on_sale(place, ALCHEMIST, day, {}, counter_kind=ALCHEMIST)
    till = market.purse(place, ALCHEMIST, day)
    pots = [g for g in shelf if getattr(g, "kind", "") == "alchemy" and not g.staple]
    assert pots, "no potion on the alchemist's counter"
    for g in pots:
        row = _row(g.key)
        assert row["kind"] == "spell" and not row.get("harmful"), g.key
        assert g.price_gp == pricing.book_price(row) <= till, g.key


def test_buying_a_classic_and_a_manual_at_a_town_alchemist(worlds):
    """End to end through the engine's `buy`: at a town's alchemist, an alchemist's fire
    comes off the counter as the formula's document and a manual as a book the reader
    finds (`knowledge.holds_manual`); 20 gp and the manual's price leave the purse."""
    def market_of(e):
        if e.kind not in ("CITY", "TOWN", "SETTLEMENT", "VILLAGE") \
                and (e.scale or "").lower() not in places.PLACES_BY_SCALE:
            return None
        if places.scale_of(e) != "town":
            return None
        return next((p.id for p in places.home_set(e) if market.is_market(p.id)), None)

    town = next(e for e in sorted(worlds.entities.values(), key=lambda e: str(e.id))
                if market_of(e))
    s = Scene(location_id=town.id)
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = 10 * 60
    eng = Engine(s, Dice(seed=5), world=worlds)
    eng.place_party(market_of(town))
    pc.purse = {"gp": 100}
    book = knowledge.manuals(knowledge.ALCHEMIST)["the-bench-primer"]
    for item in ("gear:alchemist's fire", "manual:the-bench-primer"):
        out = eng.run(eng.validate([{"op": "buy", "actor": "pc", "because": "t",
                                     "params": {"item": item, "stall": ALCHEMIST}}],
                                   origin="author:test")).outcomes[0]
        assert out.status == "resolved", out.tell
    from rules import goods as g
    assert g.in_copper(pc.purse) == (100 - 20 - book["price_gp"]) * 100
    fire = next(st for st in pc.stock.values() if st.base == "Alchemist's fire")
    assert fire.specs == _row("alchemists-fire")["core"] and fire.how == ["throw"]
    assert knowledge.holds_manual(pc, book)
