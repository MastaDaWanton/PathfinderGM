"""Worn leather reaches the sheet (leather lane B: plan §18.1-18.4, §23.1 B; contracts §4.3).

Each test names the defect it closes. The leatherworker's records are the forge's crafted
record (`forge_items.build`), worn on the pc-kesst fixture (rogue, Dex 17, table `leather`,
AC 15). Material documents come through `forge_items.material`, the build's one door,
because the data pass (lane D) and the bench (lane E) are built in parallel: these are
about the readers, so each record is the shape the contracts fix (§4.2) and the bench
will write.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from play import campaign as cm
from rules import armour as armour_mod
from rules import crafting, forge_items, magic_layer
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

DOCS = {
    "plain-hide": {"id": "plain-hide", "name": "Plain hide", "kind": "hide",
                   "armour": [{"type": "skill_mod", "target": "survival", "amount": 2,
                               "bonus_type": "material"},
                              {"type": "gear_mod", "target": "hardness", "amount": 2},
                              {"type": "gear_mod", "target": "weight_pct", "amount": 10}]},
    "winter-wolf-pelt": {"id": "winter-wolf-pelt", "name": "Winter Wolf Pelt", "kind": "hide",
                         "armour": [{"type": "resistance", "target": "cold", "amount": 2},
                                    {"type": "skill_mod", "target": "stealth", "amount": 2,
                                     "bonus_type": "material"},
                                    {"type": "gear_mod", "target": "acp", "amount": -2}]},
    # The book's dragonhide alone (plan §15): no house top-up, so what the wearer gets is
    # what the book gives the wearer — nothing.
    "red-dragonhide": {"id": "red-dragonhide", "name": "Red Dragonhide", "kind": "hide",
                       "always_masterwork": True,
                       "armour": [{"type": "object_immunity", "target": "fire", "book": True},
                                  {"type": "gear_mod", "target": "enchant_cost_pct",
                                   "amount": -25, "applies_to": "energy_resistance",
                                   "book": True},
                                  {"type": "gear_mod", "target": "hardness", "amount": 8,
                                   "book": True}]},
    "bulette-leather": {"id": "bulette-leather", "name": "Bulette Leather", "kind": "hide",
                        "armour": [{"type": "as_base", "target": "studded leather",
                                    "book": True},
                                   {"type": "skill_mod", "target": "survival", "amount": 2,
                                    "bonus_type": "material"}]},
    "werewolf-pelt": {"id": "werewolf-pelt", "name": "Werewolf pelt", "kind": "hide",
                      "armour": [{"type": "damage_reduction", "amount": 1, "bypass": "silver",
                                  "from_creature": True}]},
}


@pytest.fixture(autouse=True)
def documents(monkeypatch):
    real = forge_items.material
    monkeypatch.setattr(forge_items, "material",
                        lambda mid: DOCS.get(str(mid)) or real(mid))


def record(body="plain-hide", *, rid="hide-studded-leather", name="Hide Studded Leather",
           base="studded leather", gear="armour", slot="armor", q=1,
           fastenings="steel-studs", **over) -> dict:
    pieces = {"body": {"material": body, "passes": 0}}
    if fastenings:
        pieces["fastenings"] = {"material": fastenings, "passes": 0}
    rec = {"id": rid, "name": name, "kind": "crafted", "craft": "leatherworker", "count": 1,
           "gear": gear, "base": base, "slot": slot, "quality_index": q, "masterwork": False,
           "pieces": pieces, "smith": {"level": 1, "perks": {}}, "schema": 3}
    rec.update(over)
    return rec


def table(seed=5):
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    return scene, Engine(scene, Dice(seed=seed))


def run(engine, op, item):
    return engine.run(engine.validate([{"op": op, "actor": "pc", "because": "test",
                                        "params": {"item": item}}])).outcomes[0]


@pytest.fixture
def client(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
        yield Client()
        cm._LIVE.clear()


def post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


# --- worn leather through the forge's armour record (plan §18.1) --------------------------

def test_a_bench_studded_leather_raises_kesst_from_15_to_16():
    """The plan's proof of done (§13.3, Q7.1). Measured before (inventory §0.1): AC 15 ->
    15, the name went into the slot. A leather base from a hide with no AC modifier,
    finished with plain steel studs (studded leather), worn: AC 16 — studded leather's +3
    against leather's +2, max Dex 5 still above Kesst's Dex +3 — and the hide's numbers
    reach the sheet (Survival +2, weight +10%)."""
    scene, engine = table()
    pc = scene.pc()
    assert (pc.armour, pc.ac()) == ("leather", 15)
    survival = sum(m.value for m in pc.skill_modifiers("survival"))
    pc.add_stock(forge_items.stock_item(record()))
    out = run(engine, "wear", "hide-studded-leather")
    assert out.effects, out.tell
    assert "Armour class 15 to 16" in out.tell
    assert pc.armour == "studded leather" and pc.armour_record()["id"] == "hide-studded-leather"
    assert pc.ac() == 16
    row = pc.armour_stats()
    assert (row["acp"], row["max_dex"], row["lb"]) == (-1, 5, 22.0)
    assert sum(m.value for m in pc.skill_modifiers("survival")) == survival + 2
    # The leather base itself is wearable as what it already is (plan §4.3): leather, 15.
    pc.add_stock(forge_items.stock_item(record(rid="hide-leather", name="Hide Leather",
                                               base="leather", fastenings=None)))
    run(engine, "wear", "hide-leather")
    assert pc.armour == "leather" and pc.ac() == 15


def test_a_bench_suit_never_meets_not_built_on_any_suit():
    """Inventory §0.1, measured: "The Deer Armour is not built on any suit the rules know
    ('Deer Armour')" — the old record's `base` is its Stock's NAME, and the engine read
    `base` first. Both shapes now don: the forge-shape record (base a table key), and an
    older flat record (key under `armour`), which also comes off into the pack it never
    left rather than becoming a second, plain studded leather in `goods`."""
    scene, engine = table()
    pc = scene.pc()
    old = crafting.from_stock_dict({
        "base": "Deer Armour", "craft": "leatherworker", "kind": "crafted",
        "slot": "armor", "wearable": True, "armour": "studded leather", "masterwork": True,
        "from_materials": ["deer-hide", "steel-studs"]})
    pc.add_stock(old, 1)
    assert old.as_dict()["base"] == "Deer Armour"        # the Stock's name, by design
    out = run(engine, "wear", "Deer Armour")
    assert "not built on any suit" not in out.tell and out.effects, out.tell
    assert pc.armour == "studded leather" and pc.ac() == 16
    goods = dict(pc.goods)
    out = run(engine, "take_off", "Deer Armour")
    assert out.effects, out.tell
    assert pc.armour == "none" and pc.goods == goods
    assert any(getattr(s, "base", "") == "Deer Armour" for s in pc.stock.values())


def test_a_forge_shape_record_through_from_stock_dict_keeps_its_table_key():
    """The writer half (contracts §1: `crafting.from_stock_dict`'s base). The bench's
    output door (`play/craft_views.py`) builds its Stock through `from_stock_dict`, which
    turned a forge-shape record into a plain Stock whose `base` was whatever the dict said
    and whose pieces were gone. It is now the record whole (`ForgedStock`), base the table
    key, name the item's."""
    got = crafting.from_stock_dict(record())
    assert isinstance(got, forge_items.ForgedStock)
    assert got.record["base"] == "studded leather" and got.name == "Hide Studded Leather"
    assert forge_items.is_forged(got.as_dict())


def test_the_wear_button_without_an_op_puts_the_suit_on_through_the_engine(client):
    """Inventory §0.1, measured: the older `/api/wear` path with no `op` (the `[data-wear]`
    buttons) put the NAME in the armour slot and left `armour` alone — AC 15 -> 15, and
    the masterwork -1 ACP never reached the sheet. Routed through the engine's `wear` op
    for a crafted suit: 15 -> 16, and off again through `take_off`, back to nothing worn
    and the record still in the pack."""
    c = cm.current()
    pc = c.scene.pc()
    item = forge_items.stock_item(record(q=3))           # Superior: masterwork
    pc.add_stock(item)
    c.save()
    r = post(client, "/api/wear", {"item": item.id})
    assert r.status_code == 200, r.content[:300]
    pc = cm.current().scene.pc()
    assert pc.armour == "studded leather" and pc.ac() == 16
    assert pc.armour_check_penalty == 0                  # studded -1, masterwork +1
    assert "Armour class 15 to 16" in r.json().get("wear_tell", "")
    r = post(client, "/api/wear", {"item": item.id, "off": True})
    assert r.status_code == 200, r.content[:300]
    pc = cm.current().scene.pc()
    assert pc.armour == "none" and pc.armour_record() is None
    assert item.id in pc.stock


# --- worn goods (plan §18.2) -----------------------------------------------------------------

def cloak(rid="winter-wolf-cloak", name="Winter Wolf Cloak", slot="shoulders"):
    return record("winter-wolf-pelt", rid=rid, name=name, base="cloak", gear="worn",
                  slot=slot, fastenings=None)


def test_a_winter_wolf_cloaks_cold_resistance_reaches_resistance():
    """Plan §18.2. `resistance()` read only the worn forged suit's build: a cloak made of a
    winter-wolf pelt was worn and did nothing. Worn through the sheet's door or the
    engine's `wear` op, its cold resistance 2 and Stealth +2 reach the sheet; off, gone."""
    scene, engine = table()
    pc = scene.pc()
    stealth = sum(m.value for m in pc.skill_modifiers("stealth"))
    pc.add_stock(forge_items.stock_item(cloak()))
    assert pc.resistance("cold") == 0
    out = run(engine, "wear", "winter wolf cloak")
    assert out.effects and out.tell == "Kesst Vayr puts on the Winter Wolf Cloak.", out.tell
    assert pc.resistance("cold") == 2
    assert sum(m.value for m in pc.skill_modifiers("stealth")) == stealth + 2
    assert pc.ac() == 15, "a cloak has no armour bonus to fold an AC into"
    pc.take_off("Winter Wolf Cloak")
    assert pc.resistance("cold") == 0


def test_two_goods_of_one_hide_do_not_add_their_stealth_twice():
    """Plan §18.2: `bonus_type: material` never stacks with itself, so a wolf-pelt cloak
    and wolf-pelt boots give the better Stealth +2, not +4 (`dice.stack`)."""
    pc = load_pc("fixtures/pc-kesst.json")
    stealth = sum(m.value for m in pc.skill_modifiers("stealth"))
    pc.add_stock(forge_items.stock_item(cloak()))
    pc.add_stock(forge_items.stock_item(cloak(rid="wolf-boots", name="Wolf Boots",
                                              slot="feet")))
    pc.wear(cloak())
    pc.wear(cloak(rid="wolf-boots", name="Wolf Boots", slot="feet"))
    assert sum(m.value for m in pc.skill_modifiers("stealth")) == stealth + 2


def test_the_wear_button_puts_a_leather_cloak_in_its_slot(client):
    """The Equipment tab's slot door for a worn good: the record names its slot, and its
    build is read from there (the forged-record branch of `_standing_mods`)."""
    c = cm.current()
    pc = c.scene.pc()
    item = forge_items.stock_item(cloak())
    pc.add_stock(item)
    c.save()
    r = post(client, "/api/wear", {"item": item.id})
    assert r.status_code == 200, r.content[:300]
    pc = cm.current().scene.pc()
    assert pc.slot_list("shoulders")[0] == "Winter Wolf Cloak"
    assert pc.resistance("cold") == 2


# --- a creature's DR on the body of a suit ---------------------------------------------------

def test_a_creatures_dr_on_the_suit_reaches_damage_reduction():
    """The owner's reduced DR (2026-10-08) on a worn suit: a werewolf-pelt body's DR
    1/silver reaches `damage_reduction` at Crude, where the forge's maths would have made
    it 0.75 -> 0 (tests/test_leather_items.py measures the build), and silver gets past
    it."""
    scene, engine = table()
    pc = scene.pc()
    pc.add_stock(forge_items.stock_item(record("werewolf-pelt", rid="wolf-suit",
                                               name="Wolf Suit", base="leather",
                                               fastenings=None, q=0)))
    run(engine, "wear", "wolf-suit")
    assert pc.damage_reduction("slashing").label == "DR 1/silver"
    assert pc.damage_reduction("slashing", ("silver",)) is None


def test_the_sheet_lists_what_the_leather_worn_gives():
    """Measured live 2026-10-08 (this lane's check on scratch data): a werewolf-pelt
    suit's DR 1/silver and a wolf cloak's cold resistance 2 reached the damage path and
    were on no page — the sheet's `dr` listed only innate and class DR, and the sheet
    listed no resistances at all. Both now come from the same readers the fight uses."""
    from rules.sheet import full_sheet

    scene, engine = table()
    pc = scene.pc()
    before = full_sheet(pc)["defense"]
    assert before["dr"] == [] and before["resistances"] == []
    pc.add_stock(forge_items.stock_item(record("werewolf-pelt", rid="wolf-suit",
                                               name="Wolf Suit", base="leather",
                                               fastenings=None, q=0)))
    pc.add_stock(forge_items.stock_item(cloak()))
    run(engine, "wear", "wolf-suit")
    run(engine, "wear", "winter-wolf-cloak")
    d = full_sheet(pc)["defense"]
    assert [(r["label"], r["source"]) for r in d["dr"]] == [("DR 1/silver", "Wolf Suit")]
    assert d["resistances"] == [{"type": "cold", "amount": 2}]
    assert pc.summary()["dr"] == ["DR 1/silver"]


# --- dragonhide (plan §15, §18.4) ------------------------------------------------------------

def test_a_red_dragonhide_suit_does_not_burn_and_its_wearer_does():
    """Questions doc, 'Book versus catalogue' 1: eleven dragonhide entries gave the WEARER
    resistance 5 "as if it were the book's rule"; the book makes the ARMOUR immune to the
    dragon's energy, "although this does not confer any protection to the wearer". A fire
    that reaches the suit (`Engine._object_damage`) takes nothing off it and says so; the
    same fire through the wearer's own resistance meets 0; acid still bites the suit."""
    scene, engine = table()
    pc = scene.pc()
    pc.add_stock(forge_items.stock_item(record("red-dragonhide", rid="red-dragonhide-armour",
                                               name="Red Dragonhide Armour",
                                               base="hide armour", fastenings=None)))
    assert run(engine, "wear", "red-dragonhide-armour").effects
    whole = pc.item("Red Dragonhide Armour")
    assert (whole.hardness, whole.hp_max) == (10, 20)
    effects, tells = engine._object_damage(
        {"type": "object_damage", "dice": "40", "damage_type": "fire",
         "recipient": "target", "item": "Red Dragonhide Armour"},
        {"caster": "pc", "targets": ["pc"], "caster_level": 5})
    assert effects[0]["taken"] == 0 and effects[0]["immune"] == "fire"
    assert pc.item("Red Dragonhide Armour").hp == 20
    assert tells == ["Kesst Vayr's Red Dragonhide Armour does not char: the fire cannot "
                     "touch what it is made of."]
    assert pc.resistance("fire") == 0, "the book protects the armour, never the wearer"
    effects, _ = engine._object_damage(
        {"type": "object_damage", "dice": "30", "damage_type": "acid",
         "recipient": "target", "item": "Red Dragonhide Armour"},
        {"caster": "pc", "targets": ["pc"], "caster_level": 5})
    assert effects[0]["taken"] == 20 and not effects[0].get("immune")


def test_energy_resistance_costs_a_quarter_less_to_bind_into_dragonhide():
    """Dragonhide's book "adding energy resistance costs 25% less" (plan §15; lane A's
    `enchant_cost_pct`, read by the Enchanting price, contracts §6.3). Measured before:
    nothing in the app named an enchanting cost. A Sound red dragonhide suit (masterwork
    by its nature — before, the enchanter refused it "Only a masterwork armour can carry
    magic") takes energy resistance (18,000 gp, making 9,000) for 6,750; a plain Superior
    hide suit pays the 9,000; the +1 enhancement beside it is not discounted."""
    dragon = record("red-dragonhide", rid="rd", name="Red Dragonhide Armour",
                    base="hide armour", fastenings=None, q=1)
    plain = record("plain-hide", rid="ph", name="Hide Armour", base="hide armour",
                   fastenings=None, q=3)
    binder = {"level": 20, "knows": ["resist-energy"], "classes": ["wizard"]}
    adds = {"flat": [{"id": "energy-resistance", "choice": "fire"}]}
    got = magic_layer.plan(dragon, {"enhancement": 1, **adds}, binder=binder)
    base = magic_layer.plan(plain, {"enhancement": 1, **adds}, binder=binder)
    assert not any("masterwork" in p for p in got["problems"]), got["problems"]
    assert base["price"]["making_gp"] == 500 + 9000
    assert got["price"]["making_gp"] == 500 + 6750
    assert any("energy resistance costs 25% less" in s["why"]
               for s in got["price"]["surcharges"])


# --- as_base on the body ------------------------------------------------------------------------

def test_a_bulette_suit_is_worn_as_studded_leather_with_no_metal():
    """Bulette leather "has the same statistics as studded leather" (plan §14.5): worn on
    Kesst, AC 16 as studded leather gives, on a record whose base is leather — and no
    metal on her (lane A's note: studded leather's studs are the ROW's; the druid reads
    `armour.wears_metal`)."""
    scene, engine = table()
    pc = scene.pc()
    pc.add_stock(forge_items.stock_item(record("bulette-leather", rid="bulette-suit",
                                               name="Bulette Suit", base="leather",
                                               fastenings=None)))
    assert run(engine, "wear", "bulette-suit").effects
    assert pc.armour == "leather" and pc.ac() == 16
    assert pc.armour_stats()["as_base"] == "studded leather"
    assert not armour_mod.wears_metal(pc)
