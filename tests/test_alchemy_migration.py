"""Old saves meet the new alchemy (alchemy plan §18; contracts §1 wave 2, lane I).

The owner's rulings: Q10.1 "Convert" (levels above 3 become endless levels with perks picked
on first load; old products stay usable and sellable), Q10.2 "Keep every potion id and
`holds_spell` exactly, so a stored potion still stands in for its spell".

What was measured before this lane, on the 254 things the pre-revamp code makes
(`tests/alchemy_migration/old-items.json`, generated from master 067e516's own
`alchemist.preview` and saved the way the old /craft/ view saved them) and the 8 CRB
alchemical goods the old counter and outfitter delivered:

- every old product loaded as "Old work" on the bench (lane F), the 44 spell potions among
  them, a flat copy of the spell's effects; the 17 made by the old recipe table were the
  catalogue's look-alikes the questions doc §11 lists as wrong ("Brimstone Sealed Flask",
  two 1d6 fire, no burn, no splash, an antitoxin of two +1s that do not stack);
- every bought antitoxin, alchemist's fire or sunrod was `Stock(base=name, craft="")` with
  no document: a jar that did nothing at all (lane H's finding).

The owner's real saves (read-only copies, 2026-10-07: four campaigns and their three backups
each, three roster sheets) hold an Alchemist 1 with 0 mastery and nothing else alchemical, so
the corpus is what the conversion is measured on, and the owner's saves are what "a save with
no alchemy in it is not touched" is measured on.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from rules import alchemy_items as items
from rules import alchemy_migration as am
from rules import crafting, enchanter, formulae, knowledge
from rules import worldclass as wc
from rules.sheet import _migrated, _progress, from_dict, load_pc, to_dict

CORPUS = Path("tests/alchemy_migration/old-items.json")


def corpus(part: str = "items") -> list[dict]:
    return [dict(d) for d in json.loads(CORPUS.read_text(encoding="utf-8"))[part]]


def old(how: str) -> dict:
    for part in ("items", "bought"):
        for d in corpus(part):
            if d.pop("_how") == how:
                return d
    raise KeyError(how)


def saved_with(stock: dict, **more) -> dict:
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["stock"] = stock
    d.update(more)
    return d


def _wc(level: int, **more) -> dict:
    return {"alchemist": {"level": level, "mp": 12, "crafted": dict(more.pop("crafted", {})),
                          "mishaps": {}, "milestones": ["legendary-work"], **more}}


# --- the whole corpus ---------------------------------------------------------------------------

def test_every_old_product_the_old_code_makes_converts_or_stays_exactly_as_it_was():
    """All 254 old products and 8 bought jars, measured: the 44 spell potions become their
    formula's record; 18 become the book's classic (17 old recipe-table rows, and a lone
    itchweed floss sealed, which IS the table's itching powder: one material, same set);
    the 8 bought jars become what a counter sells today; the other 192 stay old work, byte
    for byte (the old table's bladeguard and vermin repellent have no formula now, and a
    house compound re-derived through the new pool would be a different thing under the
    same name — rules/alchemy_migration.py says why). Converted once: a converted row is
    never old again, and the old row is kept beside the record for undo."""
    got = {"spell": 0, "classic": 0, "bought": 0, "kept": 0}
    for part in ("items", "bought"):
        for d in corpus(part):
            how = d.pop("_how")
            target = am.target_of(d)
            new = am.migrate_old_record(d)
            if target is None:
                assert new is None, how
                got["kept"] += 1
                continue
            got[target.split(":")[0]] += 1
            assert new is not None, how
            st = crafting.from_stock_dict(copy.deepcopy(new))
            assert am.migrate_old_record(st.as_dict()) is None, how
            if part == "items":
                assert isinstance(st, items.AlchemyStock), how
                assert am.undo_migration(st.record) == d, how
                b = items.build(st.record)
                assert b["missing"] == [] and b["specs"], how
            else:
                assert st.specs and st.how, how
    assert got == {"spell": 44, "classic": 18, "bought": 8, "kept": 192}


@pytest.mark.parametrize("how", [d["_how"] for d in corpus() if d["_how"].startswith("potion:")])
def test_an_old_spell_potion_keeps_its_spell_and_caster_level_exactly(how):
    """Q10.2, for each of the 44: the formula is the potion's own id (lane E kept them), and
    `holds_spell` and `caster_level` are the old bottle's, not re-derived."""
    d = old(how)
    st = crafting.from_stock_dict(am.migrate_old_record(d))
    assert st.record["formula"] == how.split(":", 1)[1]
    assert st.holds_spell == d["holds_spell"] and st.caster_level == d["caster_level"]
    assert st.record["holds_spell"] == d["holds_spell"]
    assert st.count == d["count"]


def test_an_old_potion_loaded_from_a_save_still_stands_in_for_its_spell_at_the_enchanter():
    """Plan §18.3: load an old save and spend its potion at the enchanter. The stock key the
    old save wrote is kept (the circle names the potion by it), and the converted record still
    answers `holds_spell`, so the enchanter's stand-in finds it."""
    from rules import magicitem as mi

    d = old("potion:oil-of-keen-edge")
    d["count"] = 2
    pc = from_dict(saved_with({d["id"]: d}), ref="pc")
    st = pc.stock[d["id"]]
    assert isinstance(st, items.AlchemyStock)
    assert enchanter._spells_held(pc) == {"keen-edge": d["id"]}
    sword = {"masterwork": True, "kind": "weapon", "weapon": "longsword"}
    keen = mi.Chain(material_ids=["mi-keen"], enhancement=1, item="longsword")
    bare = mi.preview(10, keen, item=sword)
    held = mi.preview(10, keen, stock={d["id"]: st}, item=sword)
    assert held.consumes == {d["id"]: 1} and held.dc == bare.dc - 5


def test_an_old_brimstone_sealed_flask_is_the_books_alchemists_fire_and_is_thrown():
    """The old table's alchemist's fire ("brimstone + naphtha, clay flask") made two flat
    1d6 fire specs, no burn and no splash (questions doc §11.1). Converted, it is the formula's
    record at Sound: the book's 1d6, the burn next round and the splash, thrown as lane C's
    splash weapon. The notice says what changed, in words."""
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene

    d = old("classic:alchemists-fire:as-made")
    pc = from_dict(saved_with({d["id"]: d}), ref="pc")
    st = pc.stock[d["id"]]
    assert st.record["formula"] == "alchemists-fire" and st.name == "Alchemist's fire"
    types = [s.get("type") for s in st.specs]
    assert "burning" in types and any(s.get("route") == "splash" for s in st.specs)
    changes = st.record["migrated"]["changes"]
    assert any("Brimstone Sealed Flask" in c for c in changes)
    assert any(c.startswith("Made by the old recipe table") for c in changes)
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    s.add(instantiate("thug", scene=s, name="the thug"))
    s.add(instantiate("thug", scene=s, name="the other thug"))
    e = Engine(s, Dice(seed=7))
    e._ensure_encounter("pc")
    s.positions["pc"] = (2, 10)
    s.positions["c1"] = (5, 10)
    s.positions["c2"] = (6, 10)
    s.resync_zones()
    res = e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "she throws it",
                             "params": {"item": d["id"], "how": "throw", "to": "c1"}}]))
    if res.status != "complete":
        res = e.resume(face=20)
    effects = [x for o in res.outcomes for x in o.effects]
    assert any(x.get("kind") == "splash" for x in effects)


def test_an_old_bought_antitoxin_gives_its_plus_five_and_keeps_its_count():
    """Before lane H a counter delivered "antitoxin" as a jar with no document. Loaded now,
    it is what a counter sells today (`goods.alchemy_stock`): the book's +5 Fortitude."""
    d = old("bought:antitoxin")
    d["count"] = 3
    assert crafting.from_stock_dict(dict(d)).specs == []          # what it was: nothing
    pc = from_dict(saved_with({d["id"]: d}), ref="pc")
    st = pc.stock[d["id"]]
    assert st.count == 3 and st.craft == "alchemist"
    assert st.specs == formulae.get("antitoxin")["core"]
    assert any(s.get("target") == "fort" and s.get("amount") == 5 for s in st.specs)


def test_a_bought_product_is_finished_work_on_the_bench_never_old_work():
    """Measured live on a converted save (2026-10-07): the 8 converted bought jars — and
    every product bought since lane H — were listed as "Old work ... made at the old bench",
    because the shelf called every plain alchemist row old. Old work is what carries the
    materials its chain used; a bought one is finished work and never an input."""
    from rules import alchemist as al

    d = old("bought:alchemist's fire")
    kept = old("flask:naphtha")
    pc = from_dict(saved_with({d["id"]: d, kept["id"]: kept}), ref="pc")
    rows = {i.key: i for i in al.shelf(pc)}
    bought, house = rows[f"stock:{d['id']}"], rows[f"stock:{kept['id']}"]
    assert bought.group == "Finished work" and not bought.old
    assert al.fit_reason("dissolve", "inputs", bought) == \
        "a finished product cannot go back into the glass"
    assert house.group == "Old work" and house.old == al.OLD_WORK


def test_what_is_not_old_alchemy_is_never_claimed():
    """A herbal antitoxin, a new bench record, a bought product with its document, a forge
    bar, and a jar the player named "antitoxin" but which does something: none is ours."""
    herbal = {"base": "Antitoxin", "craft": "herbalism", "specs": [{"type": "heal"}]}
    record = items.to_stock(items.record_for_formula("acid-flask")).as_dict()
    from rules import goods

    bought_now = goods.alchemy_stock("antitoxin").as_dict()
    bar = {"base": "Iron Bar", "craft": "blacksmith", "specs": []}
    doing = {"base": "antitoxin", "craft": "", "specs": [{"type": "save_mod"}]}
    for d in (herbal, record, bought_now, bar, doing):
        assert am.target_of(d) is None and am.migrate_old_record(d) is None, d
        assert _migrated(d) is d or d.get("craft") in ("blacksmith",), d


def test_old_work_nothing_maps_is_kept_byte_for_byte_and_still_works():
    """A house compound ("Naphtha Sealed Flask") stays the shelf row it was: the same specs,
    read as before, and the bench lists it as old work (lane F's "Old work" group)."""
    from rules import alchemist as al

    d = old("flask:naphtha")
    pc = from_dict(saved_with({d["id"]: d}), ref="pc")
    st = pc.stock[d["id"]]
    assert not isinstance(st, items.AlchemyStock)
    assert st.as_dict() == crafting.from_stock_dict(dict(d)).as_dict()
    assert st.specs == d["specs"] and st.how == ["throw"]
    row = next(i for i in al.shelf(pc) if i.key == f"stock:{d['id']}")
    assert row.old and row.group == "Old work"


# --- progress ----------------------------------------------------------------------------------

@pytest.mark.parametrize("level, picks", [(1, 0), (3, 0), (4, 2), (5, 4), (6, 6)])
def test_old_alchemist_levels_above_three_are_a_bank_of_perk_picks(level, picks):
    """Plan §18.1: an old Alchemist 4 or 5 (and the 6+ that granted nothing) keeps its level,
    the levels past 3 two perk picks each, chosen at the bench's picker; mastery untouched;
    the old `legendary-work` milestone inert. Stamped only past 3, where it means anything."""
    p = _progress("alchemist", _wc(level)["alchemist"])
    assert p.level == level and p.mp == 12
    assert p.schema == (wc.ALCHEMIST_SCHEMA if level > 3 else 0)
    summary = wc.track_summary(wc.get("alchemist"), p)
    assert summary["picks_banked"] == picks
    if picks:
        got = wc.pick_perks(wc.get("alchemist"), p, ["containment"] * picks)
        assert got["picks_banked"] == 0 and got["perks"] == {"containment": picks}
    assert wc.migrate(p) is False                                  # idempotent


# --- the alchemist: knowledge and the notice ---------------------------------------------------

def test_a_converted_alchemist_knows_what_they_made_and_is_told_once():
    """Plan §18.5: the formulae of what they hold (a converted potion and a converted fire),
    of what they made (an old `crafted` key that is a potion's name), and every property of
    every material in what they hold; then one notice, the alchemist's entry first, each
    converted record after it, gone once seen and still gone after a save and a load."""
    pot = old("potion:potion-of-haste")
    fire = old("classic:alchemists-fire:as-made")
    house = old("flask:naphtha")
    data = saved_with({pot["id"]: pot, fire["id"]: fire, house["id"]: house},
                      world_classes=_wc(5, crafted={"potion of fly": 1,
                                                     "naphtha sealed flask": 2}))
    pc = from_dict(data, ref="pc")
    pc.herb_known.pop(am.NOTE_SLOT, None)
    lines = am.settle(pc)
    assert lines and lines[0].startswith("Alchemist 5:") and "4 perk picks" in lines[0]
    assert set(formulae.known(pc)) >= {"potion-of-haste", "alchemists-fire", "potion-of-fly"}
    assert knowledge.formula_how(pc, "potion-of-fly") == "made before the new bench"
    brim = knowledge.resolve("brimstone")
    assert knowledge.known_keys(pc, brim) == knowledge.property_keys(brim)
    assert any("Naphtha Sealed Flask" in line and line.startswith("Kept as it was")
               for line in lines)
    notes = am.conversions(pc)
    assert [n["key"] for n in notes][0] == am.NOTE_KEY
    assert {n["key"] for n in notes[1:]} == {f"stock:{pot['id']}", f"stock:{fire['id']}"}
    assert am.settle(pc) == []                                     # once
    am.conversion_seen(pc)
    assert am.conversions(pc) == []
    again = from_dict(to_dict(pc), ref="pc")
    assert am.conversions(again) == [] and am.settle(again) == []


def test_a_campaign_converts_its_old_chain_recipes_into_formulae_and_drops_them(tmp_path):
    """Plan §18.4: `campaign.recipes` rows with `craft: "alchemy"` cannot run on a bench that
    works one step at a time. A saved chain that made a formula (the old table's antitoxin,
    a spell potion's own recipe) teaches it; the rest are named; all are dropped, once. A
    herbalism recipe beside them is not touched."""
    from django.test import override_settings

    from play import campaign as cm

    pot = old("potion:potion-of-haste")
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.stock[pot["id"]] = crafting.from_stock_dict(dict(pot))
        herbal = {"name": "Mint tea", "craft": "herbalism", "methods": ["brew"],
                  "ingredients": ["mint"]}
        c.recipes = [
            {"name": "My antitoxin", "craft": "alchemy", "methods": ["dissolve", "filter", "seal"],
             "ingredients": ["adder-venom-gland", "willow-charcoal", "bitter-aloes",
                             "white-vinegar"]},
            {"name": "Enlarging draught", "craft": "alchemy",
             "methods": ["dissolve", "react", "seal"],
             "ingredients": ["rectified-spirits", "iron-filings", "glass-vial"]},
            {"name": "Mystery", "craft": "alchemy", "methods": ["seal"], "ingredients": ["talc"]},
            herbal]
        path = c.save()
        raw = json.loads(path.read_text(encoding="utf-8"))
        # The save as the old code wrote it: no notice, the potion old work.
        for a in raw["scene"]["people"].values():
            (a.get("herb_known") or {}).pop(am.NOTE_SLOT, None)
        path.write_text(json.dumps(raw), encoding="utf-8")
        back = cm.Campaign.load(path)
        pc = back.scene.pc()
        assert back.recipes == [herbal]
        assert {"antitoxin", "potion-of-enlarge-person", "potion-of-haste"} <= set(
            formulae.known(pc))
        note = pc.herb_known[am.NOTE_SLOT]["lines"]
        assert any("Mystery" in line and "My antitoxin" in line for line in note)
        saved = back.save()
        twice = cm.Campaign.load(saved)
        assert twice.recipes == [herbal]
        assert json.dumps(to_dict(twice.scene.pc()), sort_keys=True) == \
            json.dumps(to_dict(pc), sort_keys=True)
        cm._LIVE.clear()


# --- saves with no alchemy ----------------------------------------------------------------------

@pytest.mark.parametrize("path", sorted(str(p) for p in Path("fixtures").glob("pc-*.json")))
def test_a_save_with_no_alchemy_content_is_not_touched(path):
    """Every fixture character's pack comes back as the very object that went in, no notice
    is written, and a save and a load leave it byte for byte as it was."""
    data = to_dict(load_pc(path))
    for rec in (data.get("stock") or {}).values():
        assert am.migrate_old_record(rec) is None
    pc = from_dict(copy.deepcopy(data), ref=data.get("ref"))
    assert am.settle(pc) == [] and am.NOTE_SLOT not in pc.herb_known
    again = to_dict(pc)
    assert json.dumps(again, sort_keys=True) == json.dumps(data, sort_keys=True)


def test_an_untouched_alchemist_one_is_not_stamped():
    """Every owner save measured on 2026-10-07 holds `world_classes.alchemist` at level 1,
    0 mastery, no stamp. Levels 1-3 are the same before and after, so nothing is written:
    the progress reads back exactly as it was saved."""
    raw = {"level": 1, "mp": 0, "crafted": {}, "mishaps": {}, "milestones": []}
    from rules.sheet import _progress_dict

    assert _progress_dict(_progress("alchemist", dict(raw))) == raw
