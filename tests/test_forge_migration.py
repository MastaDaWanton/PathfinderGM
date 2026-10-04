"""Old saves meet the new forge (blacksmithing plan §14, contracts §12 item 7; lane H).

The owner chose "convert". A blade made at the old one-shot chain is a shelf entry with
flat `specs` (two of cold iron's three were `narrative` prose), a `weapon` naming its base
and no `pieces` — so none of the forge's readers could see what it was made of: no
material, no strikes, no build, its +1 masterwork a flat spec. It is re-derived on load
into a contracts §4 record: the main material inferred, the haft and fittings plain, the
masterwork kept, and the old record kept beside it for one version so a bad inference can
be undone. Old recipes naming the four removed methods load with them mapped.
"""
from __future__ import annotations

import pytest

from rules import blacksmith as bs
from rules import crafting, forge_items
from rules.sheet import from_dict, load_pc, to_dict


def old_chain_item(materials=("cold-iron", "charcoal"), base="longsword",
                   methods=("smelt", "forge", "quench", "temper", "hone")) -> dict:
    """What the old /craft/ tab put in the pack: the chain's output through
    `crafting.from_stock_dict`, saved with `as_dict` (play/craft_views.py, before wave 2)."""
    r = bs.preview(3, bs.Chain(track="blacksmith", methods=list(methods),
                               material_ids=list(materials), base=base))
    assert r.output, r.problems
    return crafting.from_stock_dict(dict(r.output, craft="blacksmith")).as_dict()


def saved_with(stock: dict, worn: dict | None = None, slots: dict | None = None) -> dict:
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["stock"] = stock
    if worn is not None:
        d["worn"] = worn
    if slots is not None:
        d["slots"] = slots
    return d


def test_an_old_masterwork_cold_iron_blade_loads_as_a_forged_record_and_keeps_masterwork():
    """Plan §16.1, lane 8: "an old 'Iron Work' save loads and keeps its masterwork".
    Measured before: the old Masterwork Cold Iron Longsword loaded as a plain `Stock` with
    three flat specs, two of them prose ("Bypasses the damage reduction of demons and
    fey"), so it struck a DR 5/cold iron fey as iron. Converted, its head is cold iron, it
    strikes as cold iron, and its masterwork +1 is the build's own."""
    old = old_chain_item()
    assert old["masterwork"] and not old.get("pieces")
    pc = from_dict(saved_with({old["id"]: old}), ref="pc")
    item = pc.stock[old["id"]]
    assert isinstance(item, forge_items.ForgedStock), type(item)
    rec = item.record
    assert rec["id"] == "masterwork-cold-iron-longsword"
    assert rec["name"] == "Masterwork Cold Iron Longsword"
    assert rec["gear"] == "weapon" and rec["base"] == "longsword"
    assert rec["pieces"]["head"] == {"material": "cold-iron", "passes": 0}
    assert rec["pieces"]["haft"] == {"material": "ash-haft", "passes": 0, "plain": True}
    assert rec["pieces"]["fittings"] == {"material": "iron", "passes": 0, "plain": True}
    assert rec["masterwork"] is True and rec["quality_index"] == 3
    assert rec["migrated"] == bs.MIGRATION_STAMP
    b = forge_items.build(rec)
    assert b["masterwork"] and "cold_iron" in b["strikes_as"]
    assert any(s["origin"] == "rule:masterwork" and s["amount"] == 1 for s in b["specs"])
    # The plain pieces count for nothing: only the head is in the sum.
    for row in b["sum"]:
        assert row["pieces"]["haft"] == 0 and row["pieces"]["fittings"] == 0, row
    # It is drawn and swung by its old name.
    w = pc.weapon("masterwork cold iron longsword")
    assert w["crafted_record"]["id"] == "masterwork-cold-iron-longsword"


def test_the_old_record_is_kept_beside_the_new_for_one_version_and_round_trips():
    """Plan §14: "the old record is kept beside the new build for one version, so a bad
    inference can be undone". It survives a save and a load unchanged, and the migration
    does not run twice."""
    old = old_chain_item()
    pc = from_dict(saved_with({old["id"]: old}), ref="pc")
    again = from_dict(to_dict(pc), ref="pc")
    rec = again.stock[old["id"]].record
    assert bs.undo_migration(rec) == old
    assert rec["pieces"]["head"]["material"] == "cold-iron"
    assert "migrated_from" not in rec["migrated_from"]


def test_a_worn_old_blade_stays_in_hand_through_the_migration():
    """The worn copy migrates with the shelf's and keeps its slot key: an old blade put in
    the hands slot through the sheet editor is still the blade in that slot."""
    old = old_chain_item()
    worn = {"masterwork cold iron longsword": dict(old)}
    slots = {"hands": ["Masterwork Cold Iron Longsword"]}
    pc = from_dict(saved_with({old["id"]: old}, worn, slots), ref="pc")
    rec = pc.worn["masterwork cold iron longsword"]
    assert forge_items.is_forged(rec) and rec["pieces"]["head"]["material"] == "cold-iron"
    assert rec in pc.worn_items()


@pytest.mark.parametrize("materials, base, want", [
    (("iron", "charcoal"), "longsword", "iron"),
    (("steel", "coke"), "battleaxe", "steel"),
    (("mithral", "charcoal"), "chain shirt", "mithral"),
])
def test_the_main_material_is_read_off_what_the_old_chain_was_made_of(materials, base, want):
    """The inference reads the old record's own `from_materials` first (a metal before a
    fuel), so a steel axe is steel and a mithral shirt is mithral; a suit's body is the
    metal and its fastenings plain iron."""
    old = old_chain_item(materials=materials, base=base, methods=("smelt", "forge"))
    rec = bs.migrate_old_record(old)
    main = "head" if rec["gear"] == "weapon" else "body"
    assert rec["pieces"][main]["material"] == want
    if rec["gear"] == "armour":
        assert rec["pieces"]["fastenings"]["plain"] is True and "lining" not in rec["pieces"]


def test_the_name_decides_when_the_charge_does_not():
    """A record whose charge names nothing that fills a head ("Cold Iron Dagger" with no
    `from_materials` left) is read by the longest metal name inside its own name — cold
    iron, not iron — and falls back to iron when nothing says."""
    rec = bs.migrate_old_record({"id": "cold-iron-dagger", "name": "Cold Iron Dagger",
                                 "craft": "blacksmith", "weapon": "dagger", "specs": []})
    assert rec["pieces"]["head"]["material"] == "cold-iron"
    rec = bs.migrate_old_record({"id": "odd-dagger", "name": "Odd Dagger",
                                 "craft": "blacksmith", "weapon": "dagger", "specs": []})
    assert rec["pieces"]["head"]["material"] == "iron"


def test_what_is_not_an_old_forge_item_is_left_alone():
    """Only an old weapon or suit converts. "Iron Work" with no base was never something
    to wield; a tea is a tea; the step bench's own items (forge.* tags) and a contracts §4
    record are already new."""
    plain = old_chain_item(base="", methods=("smelt",), materials=("iron", "charcoal"))
    assert plain["name"] == "Iron Work" and bs.migrate_old_record(plain) is None
    assert bs.migrate_old_record({"base": "Mint Tea", "craft": "herbalism"}) is None
    assert bs.migrate_old_record({"name": "x", "craft": "blacksmith", "weapon": "dagger",
                                  "properties": ["forge.form.item"]}) is None
    assert bs.migrate_old_record({"name": "x", "craft": "blacksmith", "gear": "weapon",
                                  "pieces": {}}) is None


def test_an_old_recipe_naming_removed_methods_loads_with_them_mapped():
    """Plan §14: draw -> forge, polish -> hone, flux -> a Smelt ingredient, rivet ->
    assemble. Measured before: a saved recipe naming draw was refused by the chain
    preview — "Blacksmith has no method called 'draw': Draw became Forge." — a sentence
    telling the player what the code already knew."""
    assert bs.migrate_methods(["smelt", "flux", "forge", "draw", "polish", "rivet"]) == \
        ["smelt", "forge", "hone", "assemble"]
    assert bs.migrate_methods(["flux", "forge"]) == ["smelt", "forge"]
    chain = bs.chain_from_body({"methods": ["smelt", "draw", "temper", "polish"],
                                "materials": ["iron", "charcoal"], "base": "longsword"})
    assert chain.methods == ["smelt", "forge", "temper", "hone"]
    problems = bs.preview(3, chain).problems
    assert not any("no method called" in p for p in problems), problems
