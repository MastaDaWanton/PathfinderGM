"""Old saves meet the new leatherworking (plan §20, §23.1 I; contracts §11, wave 2, lane I).

The owner's ruling, Q9.1 "Convert": old leather records are re-derived as armour records (body
= the hide named in `from_materials`), old masterwork stays masterwork, and raw hides in the
satchel start their clock on load with a full 48 hours.

What was measured before this lane, on the 252 things the pre-revamp bench makes
(`tests/leather_migration/old-items.json`, generated from master 0abad17's own
`leatherworker.preview` at level 5 and saved the way its /craft/ view saved them) and one old
sheet that build's `to_dict` wrote (`old-save.json`: pc-kesst after the old bench made a
masterwork studded "Deer Armour", the old /api/wear path put it in her armour slot, and the
old skin excursion carried a winter wolf pelt and two deer hides):

- all 230 old suits loaded as plain shelf rows; lane B's engine donned one by its `armour`
  key as the TABLE row (a masterwork studded wolf suit at check penalty -1, the masterwork's
  +1 gone) and the hide's numbers were prose;
- the worn "Deer Armour" sat in the armour slot by name while `armour` still said "leather":
  AC 15, the suit uncounted (inventory §5);
- the satchel's raw hides had no clock (`picked_at` empty) and the revamped rack read every
  bare hide as a counter's purchase: TANNED leather, a free tannage and no clock at all.

No owner save is read: the corpus is generated, as the alchemy and enchanting lanes did.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from django.test import override_settings

from play import campaign as cm
from rules import crafting, forge_items
from rules import leather_migration as lm
from rules import leatherworker as lw
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict
from rules.tables import ARMOUR

CORPUS = Path("tests/leather_migration/old-items.json")
OLD_SAVE = Path("tests/leather_migration/old-save.json")


def corpus() -> list[dict]:
    return [dict(d) for d in json.loads(CORPUS.read_text(encoding="utf-8"))["items"]]


def old(how: str) -> dict:
    for d in corpus():
        if d.pop("_how") == how:
            return d
    raise KeyError(how)


def old_pc() -> dict:
    return copy.deepcopy(json.loads(OLD_SAVE.read_text(encoding="utf-8"))["pc"])


def row_of(rec: dict) -> dict:
    return forge_items.armour_row(ARMOUR[rec["base"]], forge_items.build(rec))


# --- the whole corpus ------------------------------------------------------------------------

def test_every_old_thing_converts_or_stays_exactly_as_it_was():
    """All 252, measured: the 230 suits (leather and studded leather, with and without Tool,
    57 hides each way, the named Deer Armour and a cold-iron-studded boar suit) become
    forge-shape records that build with no problem; the 22 other
    things (cloaks, small goods, straps, barding, an untanned "armour piece" with no armour
    row) answer None and stay old work byte for byte. A converted record is never old again,
    and the old one is kept beside it for undo: nothing is dropped."""
    got = {"suit": 0, "kept": 0}
    for d in corpus():
        how = d.pop("_how")
        new = lm.migrate_old_record(d)
        if not how.split(":")[0] in ("studded", "studded-mw", "leather", "leather-mw",
                                     "named", "studded-cold-iron"):
            assert new is None, how
            got["kept"] += 1
            continue
        assert new is not None, how
        got["suit"] += 1
        st = crafting.from_stock_dict(copy.deepcopy(new))
        assert isinstance(st, forge_items.ForgedStock), how
        assert forge_items.is_forged(st.as_dict()), how
        assert lm.migrate_old_record(st.as_dict()) is None, how
        assert lm.undo_migration(st) == d, how
        assert forge_items.build(st.record)["problems"] == [], how
        assert st.record["base"] == d["armour"] and st.count == d["count"], how
    assert got == {"suit": 230, "kept": 22}


def test_an_old_studded_deer_armour_loads_as_a_wearable_forge_suit_and_keeps_its_masterwork():
    """Plan §23.1 I, the first proof. The old "Deer Armour" (deer hide, oak bark, linen thread,
    steel studs, tooled: `masterwork: True`, `armour: "studded leather"`, `base` the NAME)
    loads as the forge's crafted record: base the table key, body the deer hide, fastenings
    the steel studs that made it studded, masterwork kept at Superior. Worn through the
    engine's `wear` op on a fresh pc-kesst it is studded leather counted from its build
    (AC 15 -> 17: the row's +3 and steel studs' house +1, lane D's ruling of 2026-10-08)."""
    d = old("named:deer-armour")
    data = to_dict(load_pc("fixtures/pc-kesst.json"))
    data["stock"] = {d["id"]: d}
    pc = from_dict(data, ref="pc")
    st = pc.stock[d["id"]]
    assert isinstance(st, forge_items.ForgedStock)
    rec = st.record
    assert (rec["name"], rec["id"], rec["base"], rec["gear"]) == (
        "Deer Armour", "deer-armour", "studded leather", "armour")
    assert rec["pieces"]["body"]["material"] == "deer-hide"
    assert rec["pieces"]["body"]["tannage"] == "oak-bark"
    assert rec["pieces"]["fastenings"] == {"material": "steel-studs", "passes": 0}
    assert rec["masterwork"] is True and rec["quality"] == "superior"
    assert forge_items.build(rec)["masterwork"] is True
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(pc)
    engine = Engine(scene, Dice(seed=5))
    assert (pc.armour, pc.ac()) == ("leather", 15)
    out = engine.run(engine.validate([{"op": "wear", "actor": "pc", "because": "test",
                                       "params": {"item": "Deer Armour"}}])).outcomes[0]
    assert out.effects, out.tell
    assert pc.armour == "studded leather" and pc.armour_record()["id"] == "deer-armour"
    assert pc.ac() == 17


def test_old_masterwork_is_one_lighter_than_the_table_row_after_conversion():
    """Lane B's note, measured: an old flat record donned through the engine read the TABLE
    row, so a masterwork studded wolf-pelt suit had studded leather's check penalty, -1, and
    its masterwork bought nothing. Converted, the masterwork suit is 0 and the same suit
    without Tool is -1: the book's one lighter (plan §13.4)."""
    plain = lm.migrate_old_record(old("studded:wolf-pelt"))
    tooled = lm.migrate_old_record(old("studded-mw:wolf-pelt"))
    assert ARMOUR["studded leather"]["acp"] == -1
    assert row_of(plain)["acp"] == -1
    assert row_of(tooled)["acp"] == 0


def test_studs_are_the_ones_the_old_suit_was_studded_with():
    """The old rule made a suit studded for any fitting whose id or name said "stud"; the
    conversion reads the same fitting back, so cold-iron studs stay cold iron (they answer
    the material tag), never become steel."""
    rec = lm.migrate_old_record(old("studded-cold-iron:boar-hide"))
    assert rec["pieces"]["fastenings"]["material"] == "cold-iron-studs"
    assert rec["pieces"]["body"]["material"] == "boar-hide"


def test_a_plain_leather_suit_is_laced_with_its_own_hide_and_is_still_a_base():
    """No studs: the fastenings are a lacing set of its own hide, `plain` (nobody chose it, so
    `forge_items.build` names it and never sums it, the forge migration's rule), and the
    suit is still a leather base the forge can stud (owner Q1.3)."""
    rec = lm.migrate_old_record(old("leather:elk-hide"))
    fast = rec["pieces"]["fastenings"]
    assert fast["material"] == "elk-hide" and fast["plain"] is True
    assert rec["base"] == "leather" and "studded leather" in rec["base_for"]
    assert "lining" not in rec["pieces"]


def test_a_suit_of_a_hide_now_made_only_into_other_suits_stays_old_work():
    """Griffon mane is made only into padded or quilted cloth now (`allowed_bases`). An old
    leather suit of it is kept as it was, rather than becoming a padded suit under the
    player: the conversion never changes what kind of suit a thing is."""
    d = old("leather:elk-hide")
    d["from_materials"] = ["griffon-mane" if m == "elk-hide" else m
                           for m in d["from_materials"]]
    assert lm.target_of(d) is None and lm.migrate_old_record(d) is None


def test_barding_and_an_untanned_armour_piece_are_not_suits():
    """Barding carried an armour row and no slot (a mount's); an untanned piece no armour row
    at all. Neither is converted: both stay old work."""
    assert lm.migrate_old_record(old("barding:elk-hide")) is None
    assert lm.migrate_old_record(old("untanned:elk-hide")) is None
    assert lm.migrate_old_record(old("cloak:winter-wolf-pelt")) is None


# --- the old save --------------------------------------------------------------------------------

def test_raw_hides_in_an_old_satchel_read_48_hours_on_load(tmp_path):
    """Plan §23.1 I, the second proof, through the real load (`Campaign.load`). The old save's
    winter wolf pelt and two deer hides had no clock and the revamped rack read them as bought
    TANNED leather. Loaded, they are green hides on the rack, grade 2, 48 hours left at the
    scene's minute; the tannin and thread keep their counts; the worn Deer Armour counts
    (AC 15 -> 17) and the leather she had on goes into her pack; the notice says so. Saved
    and loaded again, nothing moves: the second load is the first one's save, byte for byte."""
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
        path = c.save()
        raw = json.loads(path.read_text(encoding="utf-8"))
        people = raw["scene"]["people"]
        ref = next(r for r, a in people.items() if a.get("ref") == "pc" or r == "pc")
        was = old_pc()
        was["at"] = people[ref].get("at")
        people[ref] = was
        path.write_text(json.dumps(raw), encoding="utf-8")
        cm._LIVE.clear()
        back = cm.Campaign.load(path)
        now = back.scene.clock_minutes
        pc = back.scene.pc()
        assert pc.inventory == {"linen-thread": 2, "oak-bark": 3}
        green = {p.material: p for p in lw.rack(pc, now) if p.form == "green"}
        assert set(green) == {"deer-hide", "winter-wolf-pelt"}
        assert green["deer-hide"].count == 2 and green["winter-wolf-pelt"].count == 1
        for p in green.values():
            assert p.hide.grade == 2 and p.hide.harvested_at == now
            assert lw.freshness(p.hide, now)["hours_left"] == 48
        assert lw.freshness(green["deer-hide"].hide, now + 48 * 60)["spoiled"]
        assert (pc.armour, pc.ac(), pc.armour_check_penalty) == ("studded leather", 17, 0)
        assert pc.armour_record()["name"] == "Deer Armour" and pc.goods == {"leather": 1}
        notice = lm.conversions(pc)
        assert [n["key"] for n in notice] == ["leatherworker", "stock:deer-armour#1"]
        assert any("48 hours" in line for line in notice[0]["changes"])
        saved = back.save()
        first = saved.read_text(encoding="utf-8")
        cm._LIVE.clear()
        twice = cm.Campaign.load(saved)
        assert twice.save().read_text(encoding="utf-8") == first
        cm._LIVE.clear()


def test_a_salted_old_satchel_hide_comes_back_salted():
    """Herbalism's satchel salt (`preserved`) kept an old hide: it lands salted, its six weeks
    started on load, never green."""
    data = old_pc()
    data["preserved"] = {"deer-hide": True}
    pc = from_dict(data, ref="pc")
    lm.settle(pc, now=500)
    (p,) = [p for p in lw.rack(pc, 500) if p.material == "deer-hide" and p.kind == "hide"]
    assert p.form == "salted" and p.hide.salted_at == 500
    assert "deer-hide" not in pc.preserved


def test_a_hide_bought_in_this_build_is_never_taken_for_an_old_raw_one():
    """The ambiguity, measured: a counter's hide lands as a bare satchel count
    (`goods.deliver` -> `carry`), exactly the shape of an old raw hide. A sheet this build
    saves while it carries one is stamped, so the next load leaves it bought leather; the
    same dict without the stamp (an old save) is converted. A sheet with no hide is not
    stamped: it round-trips byte for byte (G1)."""
    pc = load_pc("fixtures/pc-kesst.json")
    plain = to_dict(pc)
    assert lm.NOTE_SLOT not in (plain.get("herb_known") or {})
    pc.carry("deer-hide", 1)
    d = to_dict(pc)
    assert d["herb_known"][lm.NOTE_SLOT]["stamp"] == lm.MIGRATION_STAMP
    back = from_dict(copy.deepcopy(d), ref="pc")
    assert lm.settle(back, now=100) == []
    (p,) = [p for p in lw.rack(back, 100) if p.material == "deer-hide"]
    assert p.form == "leather" and back.inventory == {"deer-hide": 1}
    d["herb_known"].pop(lm.NOTE_SLOT)
    old_one = from_dict(d, ref="pc")
    assert lm.settle(old_one, now=100)
    assert [p.form for p in lw.rack(old_one, 100) if p.material == "deer-hide"] == ["green"]


@pytest.mark.parametrize("path", sorted(str(p) for p in Path("fixtures").glob("pc-*.json")))
def test_a_save_with_no_old_leatherwork_is_not_touched(path):
    """Every fixture character: no record converts, `settle` writes nothing, and a save and a
    load leave the sheet byte for byte as it was."""
    data = to_dict(load_pc(path))
    for rec in (data.get("stock") or {}).values():
        assert lm.migrate_old_record(rec) is None
    pc = from_dict(copy.deepcopy(data), ref=data.get("ref"))
    assert lm.settle(pc, now=0) == [] and lm.NOTE_SLOT not in pc.herb_known
    assert json.dumps(to_dict(pc), sort_keys=True) == json.dumps(data, sort_keys=True)


def test_the_notice_is_shown_once():
    """`conversion_seen` marks one entry or all; the worn copy of a suit is marked with its
    pack entry, so the notice never comes back from the slot."""
    pc = from_dict(old_pc(), ref="pc")
    lm.settle(pc, now=0)
    assert len(lm.conversions(pc)) == 2
    lm.conversion_seen(pc, "stock:deer-armour#1")
    assert [n["key"] for n in lm.conversions(pc)] == ["leatherworker"]
    assert pc.worn["deer armour"]["migration"]["seen"] is True
    lm.conversion_seen(pc)
    assert lm.conversions(pc) == []
