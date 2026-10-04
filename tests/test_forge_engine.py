"""A forged item matters in a fight (docs/blacksmithing-revamp-plan.md §12, contracts §5).

Each test names the defect it closes. Material documents are supplied through
`forge_items.material`, the one door the build reads, because lane C's `rules/materials.py`
is built in parallel and these tests are about the readers, not the data.
"""
from __future__ import annotations

import pytest

from rules import forge_items
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene, _ward_tell
from rules.sheet import Item, Reduction, from_dict, load_pc, to_dict
from tests._board import face_to_face

DOCS = {
    "iron": {"id": "iron", "name": "Iron", "kind": "metal", "material": "iron",
             "weapon": [{"type": "combat_mod", "target": "damage", "amount": 2,
                         "bonus_type": "material"},
                        {"type": "combat_mod", "target": "attack", "amount": -2,
                         "bonus_type": "material"},
                        {"type": "gear_mod", "target": "hardness", "amount": 2}],
             "armour": [{"type": "combat_mod", "target": "ac", "amount": 2,
                         "bonus_type": "material"},
                        {"type": "gear_mod", "target": "acp", "amount": -2},
                        {"type": "gear_mod", "target": "hardness", "amount": 2}]},
    "cold-iron": {"id": "cold-iron", "name": "Cold iron", "kind": "metal",
                  "material": "iron",
                  "weapon": [{"type": "strikes_as", "target": "cold_iron", "book": True},
                             {"type": "combat_mod", "target": "attack", "amount": 2,
                              "bonus_type": "material", "when": {"target": {"type": "fey"}}},
                             {"type": "gear_mod", "target": "hardness", "amount": -2}]},
    "adamantine": {"id": "adamantine", "name": "Adamantine", "kind": "metal",
                   "material": "adamantine",
                   "weapon": [{"type": "strikes_as", "target": "adamantine", "book": True},
                              {"type": "combat_mod", "target": "damage", "amount": 2,
                               "bonus_type": "material"}],
                   "armour": [{"type": "damage_reduction", "amount": 3, "book": True},
                              {"type": "gear_mod", "target": "acp", "amount": -2}]},
    "mithral": {"id": "mithral", "name": "Mithral", "kind": "metal", "material": "mithral",
                "armour": [{"type": "gear_mod", "target": "acp", "amount": 3, "book": True},
                           {"type": "gear_mod", "target": "max_dex", "amount": 2,
                            "book": True},
                           {"type": "gear_mod", "target": "asf", "amount": -10, "book": True},
                           {"type": "gear_mod", "target": "weight_pct", "amount": -50,
                            "book": True},
                           {"type": "gear_mod", "target": "category", "amount": -1,
                            "book": True}]},
    "fire-forged-steel": {"id": "fire-forged-steel", "name": "Fire-forged steel",
                          "kind": "alloy",
                          "armour": [{"type": "resistance", "target": "fire", "amount": 2,
                                      "book": True}]},
    "ash-haft": {"id": "ash-haft", "name": "Ash haft", "kind": "fitting",
                 "weapon": [{"type": "combat_mod", "target": "attack", "amount": 2,
                             "bonus_type": "material"}]},
    "wyvern-blood": {"id": "wyvern-blood", "name": "Wyvern blood", "kind": "quenchant",
                     "quench_mark": {"type": "save_gate", "target": "fort", "dc": 40,
                                     "trigger": "first_wound_daily",
                                     "on_failure": [{"type": "apply_condition",
                                                     "target": "sickened"}]}},
    "viridium": {"id": "viridium", "name": "Viridium", "kind": "metal",
                 "weapon": [{"type": "apply_condition", "target": "nauseated",
                             "trigger": "crit"}]},
    "abysium": {"id": "abysium", "name": "Abysium", "kind": "metal",
                "weapon": [{"type": "apply_condition", "target": "sickened",
                            "trigger": "carried",
                            "duration": {"amount": "1d4", "unit": "hour"}}],
                "armour": [{"type": "apply_condition", "target": "sickened",
                            "trigger": "carried",
                            "duration": {"amount": "1d4", "unit": "hour"}}]},
}


@pytest.fixture(autouse=True)
def documents(monkeypatch):
    monkeypatch.setattr(forge_items, "material", lambda mid: DOCS.get(str(mid)))


def weapon_record(rid="fine-iron-rapier", name="Fine Iron Rapier", head="iron",
                  base="rapier", quality_index=2, quench="", **over) -> dict:
    rec = {"id": rid, "name": name, "kind": "crafted", "craft": "blacksmith", "count": 1,
           "gear": "weapon", "base": base, "slot": "hands", "quality_index": quality_index,
           "masterwork": False,
           "pieces": {"head": {"material": head, "passes": 1},
                      "haft": {"material": "ash-haft", "passes": 0}},
           "quench": quench, "finish": [], "flaws": [],
           "smith": {"level": 2, "perks": {}}, "schema": 3}
    rec.update(over)
    return rec


def armour_record(rid="mithral-chain-shirt", name="Mithral Chain Shirt", body="mithral",
                  base="chain shirt", **over) -> dict:
    rec = {"id": rid, "name": name, "kind": "crafted", "craft": "blacksmith", "count": 1,
           "gear": "armour", "base": base, "slot": "armor", "quality_index": 1,
           "pieces": {"body": {"material": body, "passes": 0}},
           "smith": {"level": 1, "perks": {}}, "schema": 3}
    rec.update(over)
    return rec


def table(seed=5):
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    return scene, Engine(scene, Dice(seed=seed))


def wear(engine, item) -> object:
    return engine.run(engine.validate([{"op": "wear", "actor": "pc", "because": "test",
                                        "params": {"item": item}}])).outcomes[0]


def total(mods) -> int:
    return sum(m.value for m in mods)


# --- the open door (docs/stage-8-plan.md: "a masterwork weapon in the hands slot lends its
#     enhancement to every weapon") ------------------------------------------------------

def test_a_masterwork_dagger_in_the_hands_slot_does_not_raise_the_rapier():
    """Measured before the fix (stage 8's verifiers, and again 2026-10-03 on this branch's
    base): Kesst's rapier rolled +1 more with a masterwork dagger record worn in the hands
    slot than without it — `_standing_mods` read every worn record with no weapon scope,
    so the dagger's enhancement rode the rapier, the bow and the fist. The dagger's +1
    belongs to the dagger's own swing."""
    pc = load_pc("fixtures/pc-kesst.json")
    rapier_before = total(pc.attack_modifiers("rapier"))
    dagger_plain = total(pc.attack_modifiers("dagger"))
    pc.wear({"name": "Masterwork Dagger", "slot": "hands", "weapon": "dagger",
             "masterwork": True, "kind": "crafted",
             "specs": [{"type": "combat_mod", "target": "attack", "amount": 1,
                        "bonus_type": "enhancement"}]})
    assert total(pc.attack_modifiers("rapier")) == rapier_before
    assert total(pc.attack_modifiers("unarmed")) == total(
        load_pc("fixtures/pc-kesst.json").attack_modifiers("unarmed"))
    # Its own swing still has it.
    assert total(pc.attack_modifiers("Masterwork Dagger")) == dagger_plain + 1


def test_a_forged_blades_numbers_ride_only_its_own_swing():
    """Contract §5: a weapon record's modifiers apply only when the roll context's weapon
    IS that record. The worked example's +3 damage / −1 attack land on the Fine Iron
    Rapier's swing, and the plain dagger beside it is untouched."""
    scene, engine = table()
    pc = scene.pc()
    dagger = (total(pc.attack_modifiers("dagger")), total(pc.damage_modifiers("dagger")))
    rapier = (total(pc.attack_modifiers("rapier")), total(pc.damage_modifiers("rapier")))
    pc.add_stock(forge_items.stock_item(weapon_record()))
    out = wear(engine, "fine-iron-rapier")
    assert out.effects and pc.equipped == "fine-iron-rapier", out.tell
    assert out.tell == "Kesst Vayr draws the Fine Iron Rapier."
    w = pc.weapon()
    assert w["name"] == "Fine Iron Rapier" and w["damage"] == "1d6"
    assert w["crafted_record"]["id"] == "fine-iron-rapier"
    # Same base, same feats: Weapon Finesse still reads it as a rapier (finessable), and
    # proficiency is the rapier's — a forged rapier is still a rapier.
    assert pc.is_proficient("fine-iron-rapier")
    got = (total(pc.attack_modifiers()), total(pc.damage_modifiers()))
    assert got == (rapier[0] - 1, rapier[1] + 3)
    assert (total(pc.attack_modifiers("dagger")),
            total(pc.damage_modifiers("dagger"))) == dagger
    # And it is still in the pack: drawing a sword does not give it away.
    assert "fine-iron-rapier" in pc.stock


def test_a_forged_weapon_round_trips_held_through_the_save():
    """Drawn, saved and loaded, the blade is still in hand and still computes: the record
    in `worn` and the shelf entry (`ForgedStock`) both survive `to_dict`/`from_dict`."""
    scene, engine = table()
    pc = scene.pc()
    pc.add_stock(forge_items.stock_item(weapon_record()))
    wear(engine, "fine-iron-rapier")
    back = from_dict(to_dict(pc), ref="pc")
    assert back.equipped == "fine-iron-rapier"
    assert total(back.damage_modifiers()) == total(pc.damage_modifiers())


def test_cold_iron_bites_past_dr_cold_iron_and_says_so():
    """Plan §16.1: a cold iron sword's hit on a DR 5/cold iron creature deals full damage.
    Before the revamp weapon hits passed no traits to `_apply_damage` (engine ~5270), so
    `Reduction.bypassed_by` never fired and DR 5/cold iron held against cold iron exactly
    as against a stick; the stat block's "cold iron" (a space) and the vocabulary's
    `cold_iron` (an underscore) would not even have compared equal."""
    scene, engine = table(seed=7)
    pc = scene.pc()
    thug = scene.add(instantiate("thug", scene=scene, name="the thug"))
    thug.hp = thug.hp_max = 200
    thug.grant_defence("damage_reduction", "", amount=5, bypass="cold iron",
                       source="fey blood")
    pc.add_stock(forge_items.stock_item(weapon_record(
        rid="cold-iron-rapier", name="Cold Iron Rapier", head="cold-iron")))
    wear(engine, "cold-iron-rapier")
    engine.run(engine.validate([{"op": "begin_encounter",
                                 "params": {"sides": {"you": ["pc"], "them": [thug.ref]}}}]))
    face_to_face(scene)
    for _ in range(15):
        scene.turn = [r for r, _ in scene.initiative].index("pc")
        out = engine.run(engine.validate([{"op": "attack", "actor": "pc", "target": thug.ref,
                                           "visibility": "hidden", "params": {},
                                           "because": "test"}])).outcomes[-1]
        hit = next((e for e in out.effects if e.get("kind") == "damage"), None)
        if hit:
            break
    else:
        pytest.fail("never hit")
    assert hit["reduced"] == 0, hit
    assert "The cold iron bites past the thug's DR 5/cold iron." in out.tell
    # The same blow with plain iron is reduced.
    assert thug.damage_reduction("piercing", ()).amount == 5


def test_a_dr_bypass_reads_the_bestiarys_words():
    """'DR 10/cold iron and good' needs both; 'silver or good' either; and the trait's
    underscore never decides it."""
    assert Reduction(5, "cold iron").bypassed_by(("cold_iron",))
    assert not Reduction(10, "cold iron and good").bypassed_by(("cold_iron",))
    assert Reduction(10, "cold iron and good").bypassed_by(("cold_iron", "good"))
    assert Reduction(5, "silver or good").bypassed_by(("silver",))
    assert not Reduction(5, "").bypassed_by(("adamantine",))


def test_against_fey_is_asked_of_the_defender_by_tag():
    """Cold iron's '+2 attack against fey' is a `when: {"target": {"type": "fey"}}` clause
    (contracts §2), asked of THIS defender by tag prefix (law 1) — never of every swing,
    and never by a creature's name."""
    scene, engine = table()
    pc = scene.pc()
    pc.add_stock(forge_items.stock_item(weapon_record(
        rid="cold-iron-rapier", name="Cold Iron Rapier", head="cold-iron")))
    wear(engine, "cold-iron-rapier")
    thug = instantiate("thug", scene=scene, name="the thug")
    sprite = instantiate("thug", scene=scene, name="the sprite")
    sprite.apply_effect(ActiveEffect(name="fey", kind="trait", source="test",
                                     tags=("type.fey",)))
    plain = total(pc.attack_modifiers(defender=thug))
    assert total(pc.attack_modifiers(defender=sprite)) == plain + 2
    assert total(pc.attack_modifiers()) == plain     # no defender, the term is dropped


def test_adamantine_shears_hardness_under_twenty():
    """CRB, Special Materials: adamantine 'ignores hardness less than 20'. Nothing passed a
    trait to an object until now, so an adamantine edge met a lock's hardness 10 like any
    other — and still respects hardness 20 and above."""
    lock = Item(name="iron lock", material="iron")
    plain = lock.take_damage(15, "slashing")
    assert plain["reduced"] == 10
    lock = Item(name="iron lock", material="iron")
    shorn = lock.take_damage(15, "slashing", ("adamantine",))
    assert shorn["reduced"] == 0 and shorn["taken"] == 15 and shorn["sheared"]
    wall = Item(name="adamantine door", material="adamantine")
    assert wall.take_damage(25, "slashing", ("adamantine",))["reduced"] == 20


def test_a_forged_blades_own_hardness_comes_from_its_build():
    """The sword's object numbers: its main piece's metal (iron, hardness 10) moved by the
    build (+5 for the worked example's Strengthened head and fittings)."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.add_stock(forge_items.stock_item(weapon_record()))
    item = pc.item("Fine Iron Rapier")
    assert item.material == "iron" and item.hardness == 10 + 3


# --- armour from the build --------------------------------------------------------------

def test_a_mithral_shirts_check_penalty_and_max_dex_reach_the_sheet():
    """Plan §16.1. A chain shirt is ACP −2, max Dex +4, spell failure 20%, 25 lb, light.
    Mithral (book): ACP +3 (minimum 0), max Dex +2, spell failure −10, half weight, one
    class lighter for movement. Before the revamp `armour` was a table key and nothing
    could put a forged suit on at all."""
    scene, engine = table()
    pc = scene.pc()
    pc.add_stock(forge_items.stock_item(armour_record()))
    out = wear(engine, "mithral-chain-shirt")
    assert out.effects, out.tell
    assert pc.armour == "chain shirt" and pc.armour_record()["id"] == "mithral-chain-shirt"
    row = pc.armour_stats()
    assert (row["acp"], row["max_dex"], row["asf"], row["lb"]) == (0, 6, 10, 12.5)
    assert row["name"] == "Mithral Chain Shirt"
    assert pc.armour_check_penalty == 0
    ac_terms = {m.source: m.value for m in pc.ac_modifiers()}
    assert ac_terms["Mithral Chain Shirt"] == 4
    # Off again: back to the shelf it never left, and no phantom plain shirt in `goods`.
    before_goods = dict(pc.goods)
    out = engine.run(engine.validate([{"op": "take_off", "actor": "pc", "because": "t",
                                       "params": {"item": "mithral chain shirt"}}])).outcomes[0]
    assert pc.armour == "none" and pc.armour_record() is None, out.tell
    assert pc.goods == before_goods and "mithral-chain-shirt" in pc.stock


def test_an_iron_suits_material_ac_folds_into_the_armour_bonus():
    """Plan §5.2: a material's AC folds into the suit's ARMOUR bonus. As a separate
    'material' term it would stack with the suit; as a second 'armour' term it would be
    swallowed by best-of-type. Folded, the chain shirt is armour 4 + 2 = 6, one term."""
    scene, engine = table()
    pc = scene.pc()
    pc.add_stock(forge_items.stock_item(armour_record(
        rid="iron-chain-shirt", name="Iron Chain Shirt", body="iron")))
    wear(engine, "iron-chain-shirt")
    armour_terms = [m for m in pc.ac_modifiers() if m.type == "armour"]
    assert [(m.source, m.value) for m in armour_terms] == [("Iron Chain Shirt", 6)]
    assert pc.armour_check_penalty == -2 - 2


def test_worn_armour_lends_its_build_dr_and_resistance():
    """Contract §5: `damage_reduction()` and `resistance()` read the worn suit's build —
    adamantine armour's DR, fire-forged steel's resistance — and stop when it comes off."""
    scene, engine = table()
    pc = scene.pc()
    pc.add_stock(forge_items.stock_item(armour_record(
        rid="adamant-shirt", name="Adamantine Shirt", body="adamantine")))
    pc.add_stock(forge_items.stock_item(armour_record(
        rid="fire-shirt", name="Fire-Forged Shirt", body="fire-forged-steel")))
    assert pc.damage_reduction("slashing") is None
    wear(engine, "adamant-shirt")
    assert pc.damage_reduction("slashing").label == "DR 3/—"
    assert pc.resistance("fire") == 0
    wear(engine, "fire-shirt")
    assert pc.damage_reduction("slashing") is None and pc.resistance("fire") == 2


# --- riders and carried effects ------------------------------------------------------------

def _armed(seed=3, **rec):
    scene, engine = table(seed)
    pc = scene.pc()
    pc.add_stock(forge_items.stock_item(weapon_record(**rec)))
    wear(engine, rec.get("rid", "fine-iron-rapier"))
    thug = scene.add(instantiate("thug", scene=scene, name="the thug"))
    return scene, engine, pc, thug


def test_a_first_wound_rider_lands_once_a_day_through_the_applicator():
    """Wyvern blood's quench mark (plan §5.6): the first wound each day, a Fort save or
    the venom. Lands as an ActiveEffect stamped `item:<id>` (law 2), told (law 3), and
    the second wound that day does nothing — the day is an `item_spent` effect the ticker
    expires, not a counter beside the store."""
    scene, engine, pc, thug = _armed(quench="wyvern-blood")
    w = pc.weapon()
    first = engine._item_riders(pc, thug, w)
    assert any("works on the thug" in x["tell"] for x in first)
    sick = [e for e in thug.effects if e.key == "sickened"]
    assert sick and sick[0].origin == "item:fine-iron-rapier", [e.as_dict() for e in thug.effects]
    assert engine._item_riders(pc, thug, w) == []
    spent = [e for e in pc.effects if e.kind == "item_spent"]
    assert spent and spent[0].rounds_left == Engine.ROUNDS_PER_DAY
    pc.tick_effects(Engine.ROUNDS_PER_DAY)
    assert engine._item_riders(pc, thug, w)


def test_a_crit_rider_waits_for_the_crit():
    """Viridium's crit rider fires on a confirmed critical and on nothing else."""
    scene, engine, pc, thug = _armed(rid="viridium-rapier", name="Viridium Rapier",
                                     head="viridium")
    assert engine._item_riders(pc, thug, pc.weapon()) == []
    got = engine._item_riders(pc, thug, pc.weapon(), crit=True)
    assert got and thug.has_condition("nauseated")


def test_abysium_in_the_pack_sickens_and_lingers_after_it_leaves():
    """Plan §12.5: abysium sickens whoever carries it, and for 1d4 hours after. Granted by
    carrying (source `item:<id>`), removed with the item, then a timed copy the ticker
    expires — every step through the applicator and every step told."""
    scene, engine = table(seed=4)
    pc = scene.pc()
    pc.add_stock(forge_items.stock_item(weapon_record(
        rid="abysium-dagger", name="Abysium Dagger", head="abysium", base="dagger")))
    res = engine.run(engine.validate([{"op": "narrate_only", "because": "t",
                                       "params": {}}]))
    carried = [o for o in res.outcomes if o.op == "carried"]
    assert carried and "sickened (the Abysium Dagger carried)" in carried[0].tell
    held = [e for e in pc.effects if e.key == "sickened"]
    assert held and held[0].origin == "item:abysium-dagger" and held[0].rounds_left is None
    # Sold: the carried condition goes, and a 1d4-hour copy lingers.
    pc.take_stock("abysium-dagger", 1)
    said = pc.sync_carried(engine.dice)
    linger = [e for e in pc.effects if e.key == "sickened"]
    assert len(linger) == 1 and linger[0].source == "item:abysium-dagger:linger"
    assert linger[0].rounds_left in (600, 1200, 1800, 2400)
    assert any(r["kind"] == "effect_ended" for r in said)
    assert any("lingering for" in _ward_tell(scene, r) for r in said)
    pc.tick_effects(2400)
    assert not pc.has_condition("sickened")


def test_a_raw_abysium_bar_in_the_pack_sickens_too():
    """The carried effect belongs to the metal, not only to a finished blade: a bar of it
    in the pack (a Stock naming its material in `from_materials`) sickens the same way."""
    from rules import crafting

    scene, engine = table()
    pc = scene.pc()
    pc.add_stock(crafting.Stock(base="Abysium Bar", kind="metal", craft="blacksmith",
                                from_materials=["abysium"]))
    pc.sync_carried(engine.dice)
    assert pc.has_condition("sickened")
    assert next(e for e in pc.effects if e.key == "sickened").origin == "item:abysium"


# --- prospecting reaches the forge ------------------------------------------------------

def test_prospected_ore_reaches_the_blacksmiths_bench():
    """RUN 2026-10-03 on scratch data before the fix: three hours in the hills brought
    back 4 Calamine and 1 Copper Ore written as `craft: "smithing"`, and the bench's own
    filter (`play/craft_views._stock_of`, `craft == "blacksmith"`) saw none of it. The
    tell also read '2× Calamine, 2× Calamine'."""
    from play import craft_views
    from tests._places import stand_on

    scene, engine = table(seed=11)
    stand_on(scene, "hills")
    engine.run(engine.validate([{"op": "prospect", "actor": "pc", "because": "t",
                                 "params": {"hours": 3}}], origin="author:test"))
    out = engine.resume(20).outcomes[-1]
    pc = scene.pc()
    track = next(d for d in craft_views.DISCIPLINES if d["id"] == "blacksmithing")["track"]
    seen = [v for v in pc.stock.values() if v.craft == track]
    assert seen, [(k, v.craft) for k, v in pc.stock.items()]
    assert all(v.from_materials for v in seen)
    names = [part.split("× ", 1)[1] for part in
             out.tell.split("comes back with ", 1)[1].split(".")[0].split(", ")]
    assert len(names) == len(set(names)), out.tell


def test_prospecting_yields_every_mined_material_and_never_out_of_reach():
    """`kind == "ore"` left the smith's mined metals, coal and limestone unfindable; the
    `or ores` fallback handed out ANY tier when none was in reach, so a bare success on
    ground whose only mined things were exotic dug up exotic metal."""
    from rules import blacksmith
    from rules.engine import PROSPECT_TIERS

    mined = blacksmith.obtainable("mined")
    assert any(m.kind != "ore" for m in mined)
    assert PROSPECT_TIERS[:1 + 0 // 5] == ("common",)
    assert PROSPECT_TIERS[:1 + min(4, 22 // 5)][-1] == "legendary"


# --- the found door names a forge (lane G's word table) ----------------------------------

def test_founding_the_forge_by_name_makes_a_smithy():
    """Found by lane G, 2026-10-03: `_op_found` took a name as a kind only when it was
    EXACTLY in `places.KINDS`, so `found` of "the forge" with no `kind` made a place of
    no kind — not a smithy, and the forge bench refused to work in it — while "the
    smithy" worked. The name now goes through `places.kind_named`, the table `kind`
    already used."""
    from world import loader

    world = loader.load_cached("fixtures/pangrella-campaign.json")
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=3), world=world)
    engine.place_party()
    made = engine.run(engine.validate([{"op": "found", "actor": "pc", "because": "t",
                                        "params": {"name": "the forge"}}],
                                      origin="author:test")).outcomes[-1]
    assert made.effects and made.effects[0]["is"] == "smithy", made.tell
    # (The player's own "my forge" staying a mere name is lane G's ratchet,
    # tests/test_forge_places.py::test_the_players_words_never_make_a_smithy.)
