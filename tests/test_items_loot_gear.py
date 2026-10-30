"""Items, loot and shops after the review of 0.2.23 (2026-10-30), and the owner's rulings.

Each test names the measurement that made it:

1. **Magic counters sell the catalogue's wondrous items.** The ten "our own versions of the
   setting's items" (commit ae2ba9e9) matched AoN in every number and could not be had: no
   recipe taught them, no counter sold them, no build bought them. The owner: sell them in
   magic shops. The curio stall, which already sells the enchanter's magic, now draws
   finished items (`market.MAGIC_ITEM_DRAW`) under the quota and the settlement's base
   value (GameMastery Guide p.204), at the book's price.
2. **Creatures drop their magic items.** `bestiary._assemble_kit` filtered out every
   printed `magic item`: 2,039 entries in 567 blocks, 231 of them a cloak of resistance +1.
   The printed gear is the treasure ("'NPC gear' indicates the monster has treasure as
   normal for an NPC", Bestiary; "Encounters against NPCs typically award three times the
   treasure ... due to NPC gear", CRB Placing Treasure), so the fight's random purse no
   longer pays it a second time.
3. **A "once" use is spent for good.** `reset_item_uses` wiped every count at dawn: six war
   paints bound on a ring held AC 15→18, speed 30→60, DR 1, +5 Perception and blur forever.
   A colour replaces the one before (AoN: "applying a dose of a different color replaces the
   effects of the previous application"); orange's DR adds to a class's ("This effect stacks
   with damage reduction gained via a character class, such as barbarian"); the Wardstar
   Ring's endure elements, listed as working with an empty `not_yet`, had no reader.
5. **Looted plain gear is filed as a purchase is.** `_pocket` `carry`'d it into the herb
   satchel: 1,650 things across 1,041 printed bodies, 62 of them thieves' tools, which the
   lock-picking roll reads off the shelf (`pc.stock`).

(4, the people's gear by Table 14-9, is in tests/test_npc_gear.py.)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import bestiary, goods, magicitem, market, materials, treasure
from rules.dice import Dice
from rules.effectspec import permission_tag
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict

ROOT = Path(__file__).resolve().parents[1]
OURS = ("mi-lodestar-compass", "mi-wardstar-medallion", "mi-wardstar-ring",
        "mi-iron-saints-mask", "mi-war-paint-black", "mi-war-paint-blue",
        "mi-war-paint-orange", "mi-war-paint-red", "mi-war-paint-silver",
        "mi-war-paint-yellow")
CURIOS = "market:stall-curios"
DAY = 24 * 60 + 1


def _table():
    from tests.test_enchant_engine import _table as table

    return table()


def _use(e, item, power):
    from tests.test_enchant_engine import _run

    res = _run(e, [{"op": "use_item", "actor": "pc", "because": "t",
                    "params": {"item": item, "power": power}}])
    return " ".join(o.tell for o in res.outcomes)


# --- 1. magic counters ---------------------------------------------------------------------

def test_a_city_curio_stall_sells_our_items_at_the_books_price():
    """Before: 0 of the ten own items on any counter. Over 60 days a city's curio stall
    shelved nine of them (the Wardstar Ring, 35,000 gp, is over every settlement's base
    value — a metropolis stops at 16,000 — and is never on a shelf; that is the book's cap,
    not an omission)."""
    seen: dict[str, float] = {}
    for day in range(60):
        for g in market.on_sale("loc1", CURIOS, day, {}, counter_kind=CURIOS, scale="city"):
            if str(g.id).startswith("magic:"):
                seen[g.key] = g.price_gp
    ours = {rid for rid in OURS if rid in seen}
    assert ours == set(OURS) - {"mi-wardstar-ring"}
    for rid in ours:
        assert seen[rid] == materials.recipe(rid)["price_gp"]


def test_a_village_shelf_holds_nothing_dearer_than_its_base_value():
    """GameMastery Guide p.204: a village's base value is 500 gp (`market.BASE_VALUE_GP`)."""
    for day in range(20):
        for g in market.on_sale("loc1", CURIOS, day, {}, counter_kind=CURIOS,
                                scale="village"):
            if str(g.id).startswith("magic:"):
                assert g.price_gp <= 500


def test_a_bought_item_is_the_benchs_record_and_works_when_worn():
    """Delivered as the enchanter's bench would have made it (`magicitem.finished`): worn
    from the Equipment tab, the cloak puts +1 on Kesst's Fortitude (1 → 2); known for what
    it is, because a counter sold it."""
    pc = load_pc("fixtures/pc-kesst.json")
    good = next(g for g in goods.magic_item_goods() if g.key == "mi-cloak-resistance-1")
    goods.deliver(None, pc, good, 1)
    cloak = pc.stock["cloak-of-resistance-1#1"]
    assert (cloak.slot, cloak.wearable) == ("shoulders", True)
    assert cloak.magic["known"]["intent"] is True
    before = sum(m.value for m in pc.save_modifiers("fort"))
    pc.wear(cloak.as_dict())
    assert sum(m.value for m in pc.save_modifiers("fort")) == before + 1


def test_a_finished_item_is_worth_its_book_price_at_a_counter():
    """Priced by its tier as a jar would be, a cloak of resistance +1 (1,000 gp) was worth a
    fraction of that to the counter that sold it; now its layer's book price, and the shop
    pays half (`pricing.what_a_shop_pays`), as for everything else."""
    from rules import pricing

    cloak = magicitem.finished("mi-cloak-resistance-1")
    assert pricing.worth(cloak) == 1000
    assert pricing.what_a_shop_pays(cloak) == 500
    assert pricing.worth(magicitem.finished("mi-war-paint-black", how="found")) == 1800


def test_the_equipment_tab_offers_a_pots_power_and_a_worn_rings_not_a_pocketed_one():
    """No button reached `use_item {item, power}`: a bought pot of paint could be put on
    only by the GM's words. Slotless, a pot's Use is offered from the pack; a medallion's
    only while it is worn (`Engine._power_of`'s rule)."""
    from play.views import _power_acts

    paint = magicitem.finished("mi-war-paint-orange")
    acts = _power_acts(paint, {"id": paint.id, "name": paint.name}, "", False, False)
    assert acts == [{"label": "Use", "api": "/api/use",
                     "body": {"item": "War Paint (Orange)", "power": "mi-war-paint-orange"}}]
    medal = magicitem.finished("mi-wardstar-medallion")
    row = {"id": medal.id, "name": medal.name}
    assert _power_acts(medal, row, "neck", False, False) == []
    assert [a["body"]["power"] for a in _power_acts(medal, row, "neck", True, False)] \
        == ["mi-wardstar-medallion"]


def test_a_finished_item_is_never_drunk_and_reads_as_magic_on_the_counter():
    """Seen live on the scratch campaign, 2026-10-30: the looted cloak of resistance and a
    bought pot of war paint each offered "Drink" on the Equipment tab, and the counter's
    deal line called the paint "for show, no effect in play"."""
    from play.views import _carried, _row

    pc = load_pc("fixtures/pc-kesst.json")
    pc.stock = {}
    pc.add_stock(magicitem.finished("mi-cloak-resistance-1", how="found"), 1)
    pc.add_stock(magicitem.finished("mi-war-paint-silver"), 1)
    rows = {r["name"]: [a["label"] for a in r.get("acts") or ()] for r in _carried(pc)}
    assert "Drink" not in rows["Cloak of Resistance +1"]
    assert "Wear" in rows["Cloak of Resistance +1"]
    assert rows["War Paint (Silver)"] == ["Use"]
    good = next(g for g in goods.magic_item_goods() if g.key == "mi-war-paint-silver")
    row = _row(good, good.price_gp)
    assert row["does_something"] and row["shelf"] == "magic"


# --- 2. creatures drop their magic ---------------------------------------------------------

def _loot(template: str):
    s = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    pc.stock = {}
    s.add(pc)
    body = bestiary.instantiate(template, scene=s)
    s.add(body)
    alive = {k: sum(m.value for m in body.save_modifiers(k)) for k in ("fort", "will")}
    body.hp = -50
    body.die("test")
    e = Engine(s, Dice(seed=1))
    tell = " ".join(o.tell for o in e.run(e.validate(
        [{"op": "loot", "actor": "pc", "params": {"from_": body.ref}}])).outcomes)
    return pc, alive, tell


def test_a_slain_scholar_drops_the_cloak_ring_and_amulet_its_block_prints():
    """The aloof scholar's Gear line prints a cloak of resistance +1, a ring of protection
    +1 and an amulet of natural armour +1; before 2026-10-30 the loot was a dagger, coin,
    leather and a potion. Found, so unidentified (`known == {}`); worn by the looter, the
    cloak counts."""
    pc, _, tell = _loot("aloof-scholar")
    for name in ("Cloak of Resistance +1", "Ring of Protection +1",
                 "Amulet of Natural Armor +1"):
        assert name in tell
    cloak = pc.stock["cloak-of-resistance-1#1"]
    assert cloak.magic["known"] == {}
    before = sum(m.value for m in pc.save_modifiers("fort"))
    pc.wear(cloak.as_dict())
    assert sum(m.value for m in pc.save_modifiers("fort")) == before + 1


def test_a_living_creature_does_not_wear_its_printed_items_twice():
    """Into the pack, not onto the body: the printed saves already count the cloak, so the
    scholar's Fortitude and Will alive are its block's, unchanged by the drop."""
    body = bestiary.instantiate("aloof-scholar")
    assert not any(v for v in (body.slots.get("shoulders") or []))
    assert "mi-cloak-resistance-1" in body.kit_pending["pockets"]


def test_most_printed_magic_items_are_read_by_the_catalogues_own_name():
    """1,267 of the 2,039 printed magic items name a catalogue item exactly; the rest —
    wands, scrolls, ioun stones — have no row and are not invented. 2,040 since the second
    names sweep (fix/bestiary-names): the Grand Dam's "Book of the Black Sphynx" became
    "black sphinx tome", which the compile now files as a magic item."""
    comp = json.loads((ROOT / "content" / "bestiary" / "compiled.json").read_text(
        encoding="utf-8"))["creatures"]
    printed = [it["printed"] for r in comp.values() for it in r.get("carries") or ()
               if it.get("table") == "magic item"]
    read = [p for p in printed if magicitem.recipe_named(p)]
    assert len(printed) == 2040
    assert len(read) >= 1267
    assert magicitem.recipe_named("wand of cure light wounds (20 charges)") is None


def test_the_fights_purse_does_not_pay_the_printed_gear_twice():
    """The treasure value is the whole of what a creature has, and its printed gear is part
    of it. Measured over the 192 bodies with printed gear and a treasure class: the purse's
    centre was 972,595 gp on top of 867,244 gp of looted gear; now only what the gear
    leaves. The axiomite (CR 8, standard: a purse centred on 837 gp, at most 1,256)
    carries 2,315 gp of printed gear, so the purse is nothing; the abrikandilu (CR 3,
    standard, centre 200) carries 30 gp of thieves' tools and an improvised weapon, and its
    purse is what is left after them."""
    a = bestiary.instantiate("axiomite")
    assert (treasure.class_of(a), treasure.carried_gp(a)) == ("standard", 2315)
    assert all(treasure.worth(a, Dice(seed=i)) == 0 for i in range(5))
    b = bestiary.instantiate("abrikandilu")
    assert treasure.carried_gp(b) == 30
    for i in range(5):
        whole = treasure.worth(b, Dice(seed=i)) + 30
        assert 100 <= whole <= 300                 # the purse's own 50%-150% band


# --- 3. uses, war paint, endure elements ----------------------------------------------------

def test_a_pot_of_war_paint_is_used_up_and_the_rest_of_the_stack_stays_fresh():
    """Two pots of orange: the first is put on (DR 1/—) and leaves the shelf; the second is
    still whole the next day, and after it there is none."""
    s, e = _table()
    pc = s.pc()
    pc.add_stock(magicitem.finished("mi-war-paint-orange"), 2)
    tell = _use(e, "War Paint (Orange)", "mi-war-paint-orange")
    assert "used up" in tell
    assert pc.stock["war-paint-orange#1"].count == 1
    assert pc.damage_reduction("slashing").amount == 1
    s.advance(minutes=DAY)
    _use(e, "War Paint (Orange)", "mi-war-paint-orange")
    assert "war-paint-orange#1" not in pc.stock


def test_a_once_power_on_a_ring_does_not_come_back_with_the_day():
    """The defect: silver paint bound on a ring re-armed at every dawn (AC 15 → 18 for good).
    Now spent once, refused after, and the AC is back to 15 when the day's paint wears off."""
    s, e = _table()
    pc = s.pc()
    pc.wear({"id": "paint-ring", "name": "Paint Ring", "kind": "crafted",
             "craft": "enchanter", "slot": "ring",
             "magic": {"schema": 1, "enhancement": 0, "properties": [], "flat": [],
                       "powers": [{"recipe": "mi-war-paint-silver"}]}}, 0)
    ac = pc.ac()
    assert "spent for good" in _use(e, "Paint Ring", "mi-war-paint-silver")
    assert pc.ac() == ac + 3
    s.advance(minutes=DAY)
    assert pc.ac() == ac
    from rules.intents import IntentError

    with pytest.raises(IntentError, match="good for one use"):
        _use(e, "Paint Ring", "mi-war-paint-silver")


def test_a_per_day_power_still_comes_back():
    """The other half of the rule: the Wardstar Medallion's false life, 1/day, is refused
    the same day and returns with the next."""
    from rules.intents import IntentError

    s, e = _table()
    pc = s.pc()
    item = magicitem.finished("mi-wardstar-medallion")
    pc.add_stock(item, 1)
    pc.wear(item.as_dict())
    _use(e, "Wardstar Medallion", "false-life")
    with pytest.raises(IntentError, match="spent for today"):
        _use(e, "Wardstar Medallion", "false-life")
    s.advance(minutes=DAY)
    assert "Wardstar Medallion" in _use(e, "Wardstar Medallion", "false-life")


def test_a_second_colour_replaces_the_first():
    """0.2.23 held all six colours at once. Silver (+3 deflection) then blue (+30 ft): the
    silver is gone, the AC back to 15 and the speed 60."""
    s, e = _table()
    pc = s.pc()
    for c in ("silver", "blue"):
        pc.add_stock(magicitem.finished(f"mi-war-paint-{c}"), 1)
    ac = pc.ac()
    _use(e, "War Paint (Silver)", "mi-war-paint-silver")
    assert pc.ac() == ac + 3
    tell = _use(e, "War Paint (Blue)", "mi-war-paint-blue")
    assert "before is gone" in tell
    assert (pc.ac(), pc.speed_feet) == (ac, 60)


def _barbarian(level: int):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "barbarian", "level": level, "armour": "none", "shield": "none",
              "feats": [], "ranks": {}, "weapons": ["longsword"], "equipped": "longsword"})
    return from_dict(d, ref="pc")


def test_orange_paint_adds_to_a_barbarians_damage_reduction():
    """AoN: "This effect stacks with damage reduction gained via a character class, such as
    barbarian." A 10th-level barbarian (DR 2/—) under orange paint was best-of-two, 2/—;
    now 3/—. Anybody else's DR still never adds up."""
    b = _barbarian(10)
    assert b.damage_reduction("slashing").amount == 2
    b.grant_defence("damage_reduction", "", amount=1, source="war paint", rounds=14400,
                    stacks_with="class")
    assert b.damage_reduction("slashing").amount == 3
    b.grant_defence("damage_reduction", "", amount=2, source="a potion", rounds=600)
    assert b.damage_reduction("slashing").amount == 3


def test_the_wardstar_ring_keeps_out_the_cold():
    """The ring's constant endure elements (a `spell_effect`, trigger worn) had no reader:
    its wearer rolled four Fortitude saves for four hours of cold. Endure elements: "no harm
    from being in a hot or cold environment ... without having to make Fortitude saves"
    (CRB). Now no save is rolled; taken off, the cold gets in again."""
    s, e = _table()
    pc = s.pc()
    pc.slots["ring"] = ["Wardstar Ring"]
    assert pc.has_state(permission_tag("endure_elements"))
    res = e.run(e.validate([{"op": "hazard", "actor": "pc", "because": "t",
                             "params": {"rule": "cold", "to": "pc", "hours": 4}}],
                           origin="author:test"))
    assert not any(o.rolls for o in res.outcomes)
    assert "endure elements" in res.outcomes[0].tell
    pc.slots["ring"] = []
    assert not pc.has_state(permission_tag("endure_elements"))


# --- 5. looted plain gear --------------------------------------------------------------------

def test_looted_thieves_tools_are_on_the_shelf_the_lock_roll_reads():
    """The abrikandilu prints thieves' tools. Looted, they were `carry`'d into the herb
    satchel, and `Engine._op_break_in` asks the shelf: "(no thieves' tools)", +10 to the
    DC, with the tools in the pack. Now they are where a bought set is."""
    pc, _, _ = _loot("abrikandilu")
    assert pc.inventory == {}
    assert any("thieves' tools" in str(getattr(s, "base", "")).lower()
               for s in pc.stock.values())


def test_a_kit_thing_no_table_names_is_still_a_shelf_entry_not_a_herb():
    """A militia kit's "watch whistle" is no general-store row; it is listed on the shelf by
    its name, as `goods.deliver` files an unknown purchase, never in the herb satchel."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.inventory, pc.stock = {}, {}
    bestiary._pocket(pc, "watch-whistle")
    bestiary._pocket(pc, "torch")
    assert pc.inventory == {}
    assert {s.base for s in pc.stock.values()} == {"watch whistle", "torch"}
