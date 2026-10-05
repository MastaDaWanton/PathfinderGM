"""What the crafts burn is always on the counter.

The owner, 2026-10-05: "the most important thing for places like the smithy to sell are
items to use as fuel for the furnace and other things consumed in crafting like water
vinegar and alcohol".

Measured before this, over 60 days at Panthcove (the first town of the shipped
Aurvantis export): the smithy had charcoal on its shelf 30 days of 60, quenching oil 29
and potash 33, because a consumable reached a counter only through the daily draw,
competing with every other common material for thirty slots. The smithy also sold silver
ink and glass vials (its draw was every bench's), the alchemist sold charcoal, and the
tannery had curing salt and oak bark on 0 days of 60 — both unpriced, so on no counter
anywhere. And charcoal bought across a counter became a pack jar with no craft, which
the forge's rack (`blacksmith.rack`, filtered by craft) never offered: fuel paid for and
impossible to burn.

The fix is the shape the traditions agree on (content/rules/stall-lines.json,
`consumables`): Skyrim's blacksmith always stocks ingots and leather strips and draws
the rest; Stardew's Clint always sells coal; the Core Rulebook rolls only for magic items.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rules import blacksmith as bs
from rules import goods, market, places
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

DAYS = 60
TOWN = "panthcove"


def _doc() -> dict:
    return json.loads(Path("content/rules/stall-lines.json").read_text(encoding="utf-8"))


def _rows(craft: str) -> list[dict]:
    path = Path("content/materials") / f"{craft}-materials.json"
    return json.loads(path.read_text(encoding="utf-8"))["materials"]


def _common_consumables(craft: str) -> set[str]:
    kinds = set(_doc()["consumables"]["kinds"][craft])
    return {r["id"] for r in _rows(craft)
            if r.get("kind") in kinds and (r.get("tier") or "common") == "common"}


def _counters_selling(craft: str) -> list[str]:
    doc = _doc()
    out = [market.COUNTER_PREFIX + s["id"] for s in doc["shops"]
           if craft in (s.get("consumables") or ())]
    out += [market.COUNTER_PREFIX + market.STALL_PREFIX + s["id"] for s in doc["stalls"]
            if craft in (s.get("consumables") or ())]
    out += [p for p, row in doc["consumables"]["places"].items()
            if craft in (row.get("consumables") or ())]
    return out


@pytest.mark.parametrize("craft", ["blacksmith", "alchemist", "leatherworker", "enchanter"])
def test_every_common_consumable_is_on_its_trades_counters_every_day(craft):
    """Every common consumable of every craft, on every counter declared to sell that
    craft's consumables, on each of 60 days. Before: charcoal 30/60 at the smithy,
    curing salt 0/60 at the tannery."""
    want = _common_consumables(craft)
    assert want, f"{craft} has no common consumables at all"
    counters = _counters_selling(craft)
    assert counters, f"no counter sells {craft}'s consumables"
    for kind in counters:
        for day in range(DAYS):
            ids = {str(getattr(m, "id", "")) for m in
                   market.on_sale(TOWN, kind, day, {}, counter_kind=kind)}
            missing = want - ids
            assert not missing, f"{kind} on day {day} lacks {sorted(missing)}"


def test_the_owners_list_is_on_the_counters_by_name():
    """The owner named them: fuel for the furnace, water, vinegar, alcohol. Each is on a
    counter of its trade, priced from its own row."""
    smithy = {m.id: m for m in market.on_sale(TOWN, "smithy", 0, {}, counter_kind="smithy")}
    for fuel in ("charcoal", "coal", "peat"):
        assert fuel in smithy, fuel
    assert "water" in smithy and "quenching-oil" in smithy
    apothecary = {m.id: m for m in market.on_sale(TOWN, "market:alchemist", 0, {},
                                                  counter_kind="market:alchemist")}
    for solvent in ("distilled-water", "white-vinegar", "strong-spirits", "beeswax"):
        assert solvent in apothecary, solvent
    from rules import pricing

    assert pricing.worth(smithy["charcoal"]) == 1.0
    assert pricing.worth(smithy["water"]) == 0.01


def test_consumables_are_outside_the_draw_and_never_twice():
    """A staple spends none of the quota's slots and is not also drawn: the curio stall's
    drawn part still holds at most the quota, and no id appears twice on any shelf."""
    staples = {g.id for g in market.consumable_goods(
        market.consumables_at("market:stall-curios"))}
    for day in range(10):
        shelf = market.on_sale(TOWN, "market:stall-curios", day, {},
                               counter_kind="market:stall-curios")
        ids = [str(getattr(m, "id", "")) for m in shelf]
        assert len(ids) == len(set(ids)), "a thing on the counter twice"
        drawn = [m for m in shelf if not isinstance(m, goods.Good)]
        assert not {m.id for m in drawn} & staples, "a staple drawn as well"
        for tier, n in market.summary(drawn).items():
            assert n <= market.QUOTA[tier], (tier, n)


def test_a_staple_is_never_sold_out():
    """Bought ten times in one day, the charcoal is still there for the eleventh."""
    s, eng = _at_town_market()
    s.actors["pc"].purse = {"gp": 500}
    for _ in range(10):
        eng.run(eng.validate([{"op": "buy", "actor": "pc", "because": "fuel",
                               "params": {"item": "charcoal", "count": 3,
                                          "stall": "market:armorer"}}]))
    shelf = market.on_sale(TOWN, "market:armorer", market.day_of(s.clock_minutes),
                           s.market_taken, counter_kind="market:armorer")
    assert "charcoal" in {m.id for m in shelf}
    assert s.actors["pc"].inventory.get("charcoal") == 30


def test_a_rare_fuel_stays_in_the_draw():
    """Common tier only: dwarven hearthcoal and the dragon fires are what a shelf should
    be surprising about, and a skymetal smith hunts for them."""
    staples = {m.id for m in market.consumables_of(("blacksmith",))}
    assert "charcoal" in staples
    for rare in ("coke", "dwarven-hearthcoal", "dragonfire-coal", "salamander-cinder",
                 "phoenix-ash-ember", "borax"):
        assert rare not in staples, rare


def test_the_smithy_draws_from_the_forge_and_not_from_every_bench():
    """The smithy's draw was every bench's: silver ink and glass vials beside the anvil."""
    for day in range(10):
        ids = {str(getattr(m, "id", "")) for m in
               market.on_sale(TOWN, "smithy", day, {}, counter_kind="smithy")}
        assert not ids & {"silver-ink", "glass-vial", "white-vinegar", "sealing-wax"}


def _at_town_market():
    s = Scene(location_id=TOWN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = 10 * 60
    return s, Engine(s, Dice(seed=3))


def test_charcoal_bought_across_a_counter_reaches_the_forge():
    """Measured before: the purchase became `Stock(base="Charcoal", craft="")`, and the
    forge's rack skips stock whose craft is not a bench's, so the fire stayed cold with
    the fuel paid for. Now it lands in the satchel under its id, where the rack reads it
    and where the forge's own "Buy from the market" always put it."""
    s, eng = _at_town_market()
    pc = s.actors["pc"]
    pc.purse, pc.inventory, pc.stock = {"gp": 50}, {}, {}
    eng.run(eng.validate([{"op": "buy", "actor": "pc", "because": "fuel",
                           "params": {"item": "charcoal", "count": 4,
                                      "stall": "market:armorer"}}]))
    assert pc.inventory.get("charcoal") == 4
    assert not pc.stock, "a pack jar named Charcoal again"
    rack = {p.material: p.count for p in bs.rack(pc)}
    assert rack.get("charcoal") == 4


def test_a_drawn_material_bought_at_a_counter_reaches_the_bench_too():
    """The same hole, for anything a counter drew rather than stocks: a bench material
    goes in the satchel. Gear and goods do not."""
    s, eng = _at_town_market()
    pc = s.actors["pc"]
    pc.inventory, pc.stock = {}, {}
    goods.deliver(s, pc, bs.get("iron"), 2)
    assert pc.inventory.get("iron") == 2
    goods.deliver(s, pc, goods.good("rope"), 1)
    assert "rope" not in pc.inventory


def test_the_forge_errand_reaches_the_same_staples():
    """"Buy from the market" and the trade panel are one store: the errand's shelf
    starts with the same consumables the counters carry (`market.consumables_of`). The
    errand itself is driven through its endpoint with the draw sold out in
    tests/test_market.py, and comes back with staples only."""
    names = {m.id for m in market.consumables_of(("blacksmith",))}
    counter = {g.id for g in market.consumable_goods(market.consumables_at("smithy"))}
    assert names == counter


def test_every_town_offers_a_counter_with_forge_fuel(worlds):
    """A smith in any settlement of any shipped world can buy fuel: the curio stall is
    in every market (every line is dealt to some stallholder), and in a town the armorer
    carries it too."""
    for e in worlds.entities.values():
        scale = places.scale_of(e)
        if scale not in places.PLACES_BY_SCALE or not any(
                market.is_market(p.id) for p in places.home_set(e)):
            continue
        kinds = [c.kind for c in market.counters(e)]
        fuelled = [k for k in kinds if "blacksmith" in market.consumables_at(k)]
        assert fuelled, f"{e.name} ({scale}): no counter sells forge fuel"


# --- the document is refused when it does not account for the catalogues ------------------

def _problems_with(edit) -> list[str]:
    doc = copy.deepcopy(_doc())
    edit(doc)
    return market.consumable_problems(doc)


def test_the_shipped_document_is_sound():
    assert market.consumable_problems(_doc()) == []


def test_a_kind_nobody_filed_is_refused_with_the_fix_named():
    """A new kind added to a catalogue tomorrow cannot land on no counter silently."""
    def drop(doc):
        doc["consumables"]["kinds"]["blacksmith"].remove("fuel")
    problems = _problems_with(drop)
    assert any("'fuel'" in p and "add it to one" in p for p in problems), problems


def test_a_craft_on_no_counter_is_refused():
    def unsell(doc):
        for row in doc["shops"] + doc["stalls"]:
            if "leatherworker" in (row.get("consumables") or ()):
                row["consumables"].remove("leatherworker")
    problems = _problems_with(unsell)
    assert any("leatherworker" in p and "add 'leatherworker'" in p for p in problems)


def test_an_unpriced_common_consumable_is_refused(monkeypatch):
    """Curing salt had no price and so was on no counter anywhere: 0 days of 60."""
    rows = [dict(r) for r in _rows("leatherworker")]
    for r in rows:
        if r["id"] == "curing-salt":
            r.pop("price_gp", None)
    real = market._catalogue_rows
    monkeypatch.setattr(market, "_catalogue_rows",
                        lambda craft: rows if craft == "leatherworker" else real(craft))
    problems = market.consumable_problems(_doc())
    assert any(p.startswith("curing-salt") and "give it one" in p for p in problems)


def test_the_enchanters_own_consumed_flag_agrees():
    """The enchanter's catalogue already marks its circle materials `consumed: true`;
    filing one of those kinds as made_from contradicts the document itself."""
    def contradict(doc):
        doc["consumables"]["kinds"]["enchanter"].remove("ink")
        doc["consumables"]["made_from"]["enchanter"].append("ink")
    problems = _problems_with(contradict)
    assert any("consumed: true" in p for p in problems)


def test_the_world_bible_note_says_what_a_settlement_may_declare():
    """Fixes are world-agnostic: the format a world would use to say what its trades sell
    is written down for World Bible."""
    text = Path("docs/from-world-bible.md").read_text(encoding="utf-8")
    assert "consumables" in text and "stall-lines.json" in text
