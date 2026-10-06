"""Old saves meet the new enchanting (enchanting plan §19, contracts §12; lane H).

The owner's ruling (round 3): "Convert. Levels above 3 become endless levels with perks
picked on first load; old enchanted items keep their +N and specs, re-derived onto the new
layer where possible, the old record kept beside them for one version."

What an old enchanted item was, measured on the 268 items the pre-revamp code makes
(`tests/enchant_migration/old-items.json`, generated from master e028885's own previews):
a shelf entry with `craft: "enchanter"`, a flat `specs` list, an `enhancement` number and
`properties` as display names. Loaded on the revamped tree without this lane, every one of
them was offered at the circle as a PLAIN vessel (no layer), so a +1 flaming sword could be
enchanted again from scratch, and its fire was a note ("on a hit") with no trigger that no
reader ever fired. The owner's real saves (read-only copies, 2026-10-06) hold no enchanted
item and no Enchanter above level 1, so the corpus is what the migration is measured on.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from rules import crafting, effectspec, enchanter, forge_items, magic_layer, magicitem
from rules import worldclass as wc
from rules.sheet import _migrated, _progress, from_dict, load_pc, to_dict

CORPUS = Path("tests/enchant_migration/old-items.json")


def corpus() -> list[dict]:
    return [dict(d) for d in json.loads(CORPUS.read_text(encoding="utf-8"))["items"]]


def old(how: str) -> dict:
    """One old item, as the old /craft/ view saved it, by the working that made it."""
    for d in corpus():
        if d.pop("_how") == how:
            return d
    raise KeyError(how)


def saved_with(stock: dict, worn: dict | None = None, slots: dict | None = None,
               **more) -> dict:
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["stock"] = stock
    if worn is not None:
        d["worn"] = worn
    if slots is not None:
        d["slots"] = slots
    d.update(more)
    return d


# --- the whole corpus ---------------------------------------------------------------------------

def test_every_old_item_the_old_code_makes_converts_with_nothing_lost():
    """All 268 convert. Measured: 137 become forged records (every weapon and armour
    property on the book tab, the +N ladder, and every essence that grants something now),
    131 keep their shelf shape with the layer on `magic` (the 112 wondrous items and rings,
    and 19 essence bindings). None has a layer problem and none is over its capacity (the
    binding is stamped at the level that holds what the item carries).

    Only 19 keep anything flat, and all 19 are essences that grant nothing in the new
    enchanting: nine of the old motes (fire, frost, gale, glow, spark, stone, tide, hearth
    ember, lich dust) and the ten alchemist essences the old shelf also read. Their specs
    stay where `magic_layer.record_specs` reads them, as before; dropped, those items would
    have silently lost what they did. Three items wait on a question, all three bane."""
    forged = shelf = 0
    flat_left, waiting = [], []
    for d in corpus():
        how = d.pop("_how")
        new = enchanter.migrate_old_record(d)
        assert new is not None, how
        if forge_items.is_forged(new):
            forged += 1
            assert not new.get("specs"), how
        else:
            shelf += 1
        lay = magic_layer.layer(new)
        assert lay["problems"] == [], (how, lay["problems"])
        assert magic_layer.capacity(new)["left"] >= 0, how
        m = new["magic"]
        if new.get("specs"):
            flat_left.append(how)
        waiting.extend(p["id"] for p in m.get("pending") or ())
        # Converted once: a record with a layer is never old again.
        assert enchanter.migrate_old_record(new) is None, how
        assert enchanter.undo_migration(new) == d, how
    assert (forged, shelf) == (137, 131)
    assert len(flat_left) == 19 and all(h.startswith("essence:") for h in flat_left)
    assert sorted(waiting) == ["bane", "bane", "bane"]


# --- arms and armour ----------------------------------------------------------------------------

def test_an_old_flaming_longsword_loads_as_a_forged_sword_whose_fire_lands():
    """Before: loaded as a plain shelf entry the circle offered as an unenchanted vessel
    (`state: "plain"`), its +1 and its fire two flat specs, the fire a note with no trigger.
    After: a forged longsword (default pieces, plain; Superior), +1 on its layer, flaming
    a rider that fires on a hit, the old record kept beside it. Drawn by its old name."""
    item = old("book:mi-flaming")
    unconverted = crafting.from_stock_dict(item)
    assert not magic_layer.has_layer(unconverted.as_dict())
    assert not any(s.get("trigger") for s in unconverted.specs)

    pc = from_dict(saved_with({item["id"]: item}), ref="pc")
    st = pc.stock[item["id"]]
    assert isinstance(st, forge_items.ForgedStock)
    rec = st.record
    assert rec["gear"] == "weapon" and rec["base"] == "longsword"
    assert rec["quality_index"] == 3 and rec["masterwork"] is True
    assert rec["magic"]["enhancement"] == 1
    assert [p["id"] for p in rec["magic"]["properties"]] == ["flaming"]
    b = forge_items.build(rec)
    assert any(s.get("source") == "enhancement" and s["target"] == "attack"
               and s["amount"] == 1 for s in b["specs"])
    riders = b["magic"]["riders"]
    assert any(r["type"] == "damage" and r.get("damage_type") == "fire"
               and r.get("trigger") == "hit" for r in riders)
    assert "magic" in b["strikes_as"]
    assert enchanter.undo_migration(rec) == item
    w = pc.weapon(item["name"])
    assert w["crafted_record"]["id"] == rec["id"]
    v = [x for x in enchanter.vessels(pc) if x.key == f"stock:{item['id']}"]
    assert v and v[0].state == "magic"


def test_the_conversion_survives_a_save_and_a_load_unchanged():
    """Idempotent by its own shape: a converted item has a layer, and a record with a layer
    is not old. The second load is the first load's save, byte for byte."""
    item = old("book:+2 flaming keen")
    pc = from_dict(saved_with({item["id"]: item}), ref="pc")
    once = to_dict(pc)
    twice = to_dict(from_dict(copy.deepcopy(once), ref="pc"))
    assert json.dumps(once, sort_keys=True) == json.dumps(twice, sort_keys=True)
    rec = from_dict(once, ref="pc").stock[item["id"]].record
    assert rec["magic"]["enhancement"] == 2
    assert sorted(p["id"] for p in rec["magic"]["properties"]) == ["flaming", "keen"]
    assert rec["magic"]["migrated"]["stamp"] == enchanter.MIGRATION_STAMP


def test_an_old_enchanted_suit_folds_its_plus_into_the_armour_bonus_and_resists_fire():
    """A +1 chain shirt of fire resistance, worn. Converted to a forged suit, its +1 is the
    layer's armour bonus that the armour row folds into the suit's (4 + 1), and resist fire
    10 is read off the worn suit's layer. Measured: a suit left on the shelf with the +N on
    its layer would have read +1 as a SECOND armour bonus that the suit's own +4 beats."""
    item = old("book:mi-energy-resistance-fire")
    name = item["name"]
    pc = from_dict(saved_with({item["id"]: item}, {name.lower(): dict(item)},
                              {"armor": [name]}, armour="chain shirt"), ref="pc")
    rec = pc.armour_record()
    assert rec is not None and rec["magic"]["enhancement"] == 1
    assert pc.armour_stats()["ac"] == 5
    assert pc.resistance("fire") == 10


def test_an_old_plus_three_shield_converts_and_keeps_its_plus_three():
    item = old("book:+3 shield")
    rec = enchanter.migrate_old_record(item)
    assert forge_items.is_forged(rec) and rec["gear"] == "shield"
    assert rec["magic"]["enhancement"] == 3
    assert rec["magic"]["binding"]["level"] == 6     # capacity floor(6 / 2) holds +3
    assert magic_layer.capacity(rec)["left"] == 0


# --- rings and wondrous items --------------------------------------------------------------------

def test_a_worn_old_ring_of_protection_keeps_its_deflection_once():
    """The ring becomes its recipe's power on the layer, its flat +1 lifted off: worn, AC
    rises by exactly 1 (not 2, which the flat spec beside the power would have given)."""
    item = old("book:mi-ring-protection-1")
    name = item["name"]
    bare = from_dict(saved_with({item["id"]: item}), ref="pc")
    worn = from_dict(saved_with({item["id"]: item}, {name.lower(): dict(item)},
                                {"ring": [name]}), ref="pc")
    rec = worn.worn[name.lower()]
    assert rec["magic"]["powers"] == [{"recipe": "mi-ring-protection-1", "essence": None}]
    assert rec["specs"] == []
    assert worn.ac() == bare.ac() + 1


def test_a_renamed_catalogue_row_does_not_do_its_thing_twice():
    """Lane D's book check renamed three rows (Gauntlets of Rust, Belt of Mighty Hurling,
    Ring of Mindshielding). Matched by today's names only, their old specs stayed flat
    beside the power they became; the old record's own `properties` names pair them up."""
    for how in ("book:mi-belt-mighty-hurling", "book:mi-gauntlets-rust",
                "book:mi-ring-mindshield"):
        rec = enchanter.migrate_old_record(old(how))
        assert rec["specs"] == [], how
        assert len(rec["magic"]["powers"]) == 1, how


def test_a_retired_catalogue_row_still_loads_and_works_and_is_never_offered():
    """Lane D retired ten rows found in no Paizo book. An item built on one keeps working:
    its recipe power resolves through the old catalogue (`magic_layer.recipe` falls back to
    `magicitem.get`, which keeps retired rows), so the layer lays exactly the old row's
    effects. It is never offered: `materials.recipe` leaves retired rows out."""
    from rules import materials

    item = old("book:mi-periapt-wisdom")
    rec = enchanter.migrate_old_record(item)
    assert rec["magic"]["powers"][0]["recipe"] == "mi-periapt-wisdom"
    assert materials.recipe("mi-periapt-wisdom") is None
    lay = magic_layer.layer(rec)
    assert lay["problems"] == []
    sig = sorted((s["type"], s.get("target"), s.get("amount")) for s in lay["specs"])
    was = sorted((s["type"], s.get("target"), s.get("amount"))
                 for s in magicitem.get("mi-periapt-wisdom").effects)
    assert sig == was and sig


# --- what nothing maps, and what the old numbers prove ------------------------------------------

def test_an_essence_that_grants_nothing_now_keeps_its_specs_as_they_were():
    """A Fire Mote longsword: the mote grants nothing in the new enchanting. Its spec stays
    flat and is read as before; the item is marked converted (so it is not re-read every
    load) and its notes say what was kept."""
    item = old("essence:fire-mote")
    rec = enchanter.migrate_old_record(item)
    assert not forge_items.is_forged(rec)
    assert rec["specs"] == item["specs"]
    assert not magic_layer.has_layer(rec)
    assert any(c.startswith("Kept as it was") for c in rec["magic"]["migrated"]["changes"])
    assert enchanter.migrate_old_record(rec) is None


def test_a_choice_the_old_numbers_prove_is_read_not_guessed():
    """Angel Feather now grants deflection, a scaled property with no bonus in its grant.
    The old item gave +1 deflection to AC, and of the five ways deflection binds only +1
    reproduces that: it is read. Bane's numbers tie across every creature type: asked."""
    rec = enchanter.migrate_old_record(old("essence:angel-feather"))
    props = rec["magic"]["properties"]
    assert props == [{"id": "deflection", "essence": "angel-feather", "choice": {"bonus": 1}}]
    rec = enchanter.migrate_old_record(old("essence:bane-essence"))
    assert [p["id"] for p in rec["magic"]["pending"]] == ["bane"]


# --- bane: asked, never guessed -----------------------------------------------------------------

def test_an_old_bane_waits_for_its_foe_and_is_asked_on_the_card_and_on_first_load():
    """`mi-bane` maps to bane with no foe (lane A). The old bane's +2 and +2d6 were notes
    every reader applied to EVERY foe; carried on, the conversion would keep that bug. So
    bane waits in `pending`: the layer lays nothing of it (the +1 and the flaming still
    work), the item card carries the question, and the one-time notice lists it."""
    item = old("book:+1 bane flaming")
    name = item["name"]
    pc = from_dict(saved_with({item["id"]: item}, {name.lower(): dict(item)},
                              {"hands": [name]}), ref="pc")
    rec = pc.stock[item["id"]].record
    lay = magic_layer.layer(rec)
    assert not lay["raises"] and "property.bane" not in lay["tags"]
    assert "property.flaming" in lay["tags"] and lay["enhancement"] == 1
    card = enchanter.item_card(rec)
    q = card["questions"][0]
    assert q["property"] == "bane" and q["asks"] == ["foe"] and "undead" in q["options"]
    notes = enchanter.conversions(pc)
    assert [n["name"] for n in notes] == [name]           # pack entry and worn copy: once
    assert notes[0]["questions"] and not notes[0]["seen"]


def test_answering_bane_binds_it_on_the_pack_entry_and_the_worn_copy():
    item = old("book:+1 bane flaming")
    name = item["name"]
    pc = from_dict(saved_with({item["id"]: item}, {name.lower(): dict(item)},
                              {"hands": [name]}), ref="pc")
    key = f"stock:{item['id']}"
    with pytest.raises(ValueError):
        enchanter.answer_question(pc, key, "bane", {"foe": "teapots"})
    assert enchanter.pending_of(pc.stock[item["id"]].record)     # still asked
    got = enchanter.answer_question(pc, key, "bane", {"foe": "undead"})
    assert got["ok"] and any("undead" in line for line in got["lines"])
    for rec in (pc.stock[item["id"]].record, pc.worn[name.lower()]):
        m = rec["magic"]
        assert "pending" not in m
        bane = [p for p in m["properties"] if p["id"] == "bane"]
        assert bane == [{"id": "bane", "essence": None, "choice": {"foe": "undead"}}]
        lay = magic_layer.layer(rec)
        assert lay["raises"] and lay["raises"][0]["when"] == {"target": {"type": "undead"}}
        assert magic_layer.capacity(rec)["left"] >= 0
    assert not enchanter.item_card(pc.stock[item["id"]].record).get("questions")
    again = from_dict(to_dict(pc), ref="pc")
    assert any(p["id"] == "bane" for p in again.stock[item["id"]].record["magic"]["properties"])


def test_the_first_load_notice_is_shown_once():
    item = old("book:mi-flaming")
    pc = from_dict(saved_with({item["id"]: item}), ref="pc")
    notes = enchanter.conversions(pc)
    assert len(notes) == 1 and any("Flaming" in c for c in notes[0]["changes"])
    enchanter.conversion_seen(pc, notes[0]["key"])
    assert enchanter.conversions(pc) == []
    assert enchanter.conversions(from_dict(to_dict(pc), ref="pc")) == []


# --- what is not old, and saves with no enchanting -----------------------------------------------

def test_what_is_not_an_old_enchanted_item_is_left_alone():
    """The new bench's own records: a phial (enchant.* tags), a blank, an unbound vessel,
    anything with a layer, a forge record, a herb jar."""
    assert not enchanter.is_old_enchanted({"base": "Mint Tea", "craft": "herbalism",
                                           "specs": [{"type": "heal"}]})
    assert not enchanter.is_old_enchanted({"base": "Ring", "craft": "enchanter",
                                           "slot": "ring", "specs": []})
    assert not enchanter.is_old_enchanted({"base": "Flaming Essence", "craft": "enchanter",
                                           "properties": ["enchant.form.phial"]})
    assert not enchanter.is_old_enchanted({"name": "x", "craft": "enchanter",
                                           "enhancement": 1, "magic": {"enhancement": 1}})
    assert not enchanter.is_old_enchanted({"name": "x", "craft": "enchanter",
                                           "enhancement": 1, "pieces": {}})


@pytest.mark.parametrize("path", sorted(str(p) for p in Path("fixtures").glob("pc-*.json")))
def test_a_save_with_no_enchanting_content_is_not_touched(path):
    """Every pack and worn record of the fixture characters comes back as the very object
    that went in, and a save and a load leave the save byte for byte as it was."""
    data = to_dict(load_pc(path))
    for rec in list((data.get("stock") or {}).values()) + list((data.get("worn") or {}).values()):
        assert _migrated(rec) is rec
    again = to_dict(from_dict(copy.deepcopy(data), ref=data.get("ref")))
    assert json.dumps(again, sort_keys=True) == json.dumps(data, sort_keys=True)


def test_the_old_by_the_book_tab_still_writes_old_records_and_they_convert_on_load():
    """The old tab (rules/magicitem.py) is kept until the UI wave retires it, and it still
    writes the flat record. What it makes today converts on the next load like the rest."""
    r = magicitem.preview(5, magicitem.Chain(material_ids=["mi-frost"], enhancement=1),
                          item={"masterwork": True, "kind": "weapon", "weapon": "longsword"})
    saved = crafting.from_stock_dict(dict(r.output, craft="enchanter")).as_dict()
    rec = enchanter.migrate_old_record(saved)
    assert forge_items.is_forged(rec)
    assert [p["id"] for p in rec["magic"]["properties"]] == ["frost"]


# --- progress ----------------------------------------------------------------------------------

@pytest.mark.parametrize("level, picks", [(1, 0), (3, 0), (4, 2), (5, 4)])
def test_old_enchanter_levels_above_three_are_a_bank_of_perk_picks(level, picks):
    """Plan §19: an old Enchanter 4 or 5 keeps its level, and the levels past 3 are perk
    picks waiting at the circle (two per level, the track's `endless` block), chosen on the
    first visit through the perk picker. Mastery banked is untouched; the stamp is written
    once."""
    p = _progress("enchanter", {"level": level, "mp": 37, "crafted": {"x": 1},
                                "milestones": ["legendary-binding"]})
    assert p.level == level and p.mp == 37 and p.schema == wc.ENCHANTER_SCHEMA
    summary = wc.track_summary(wc.get("enchanter"), p)
    assert summary["picks_banked"] == picks
    if picks:
        got = wc.pick_perks(wc.get("enchanter"), p, ["capacity"] * picks)
        assert got["picks_banked"] == 0 and got["perks"] == {"capacity": picks}
        assert wc.perk_multipliers(p)["capacity"] == picks


def test_property_aliases_cover_every_old_weapon_and_armour_row():
    """Every old weapon and armour property row has a property by lane A's alias, so none
    of them falls back to a flat spec. 58 rows, measured."""
    rows = [i for i in magicitem.catalogue().values()
            if i.kind in ("weapon_property", "armour_property")]
    assert len(rows) == 58
    assert all(effectspec.from_alias(i.id) for i in rows)
