"""What an enchanter learns, and how (enchanting plan §12-13, contracts §7, lane F).

The owner's discovery ruling (docs/enchanting-answers.md round 2): disenchant a magic item
to learn its property; identify graded by the roll (beat it by 10 to see curses); study,
teachers, libraries and manuals, as herbalism's routes. Unbind (round 4 Q6): the layer
goes, the smith's item stays, a quarter of the motes come back. Each test names the
defect it prevents.

Lane D's essence documents (`grants`, `phase`, `polarity`, `affinity`, `house`) are built
in parallel, so the essences here come through a fake door in `sys.modules`, shaped as
lane D's normalised document; the suite passes with or without lane D merged.
"""
from __future__ import annotations

import copy
import json
import sys
import types

import pytest

from rules import curses, goods, herbknowledge, knowledge, magic_layer
from rules.sheet import Actor, from_dict, to_dict


# --- builders --------------------------------------------------------------------------------

def forged(rid="sword", q=3):
    return {"id": rid, "name": "Longsword", "kind": "crafted", "craft": "blacksmith",
            "count": 1, "gear": "weapon", "base": "longsword", "slot": "hands",
            "quality_index": q, "masterwork": True,
            "pieces": {"head": {"material": "steel", "passes": 1},
                       "haft": {"material": "ash-haft", "passes": 0},
                       "fittings": {"material": "brass-guard", "passes": 0}},
            "quench": None, "finish": [], "flaws": [], "smith": {"level": 3, "perks": {}},
            "schema": 3}


FLAMING = {"enhancement": 1, "properties": [{"id": "flaming"}]}


def enchanted(adds=FLAMING, curse=None, rid="sword"):
    return magic_layer.write(forged(rid), adds, binding={"level": 10}, curse=curse, day=2)


def protection_ring(rid="ring"):
    return magic_layer.write({"id": rid, "name": "Ring", "gear": "ring", "slot": "ring"},
                             {"powers": [{"recipe": "mi-ring-protection-1"}]},
                             binding={"level": 6}, day=2)


def found(record):
    """An item the character did not make: nothing about it is known."""
    rec = copy.deepcopy(record)
    rec["magic"]["known"] = {}
    return rec


def pc():
    return Actor(name="Enchanter", ref="pc")


def a_curse(row="delusion", **extra):
    return {"schema": 1, "id": f"curse:{row}", "row": row, "detail": {}, "cl": 10,
            "gear": "weapon", "origin": "item:sword", "state": {}, **extra}


# A lane-D-shaped essence (contracts §5; materials.normalise on lane D's branch).
EMBER = {
    "id": "test-ember", "name": "Test Ember", "kind": "essence", "tier": "rare",
    "catalogue": "enchanter-materials", "form": "phial", "material": "test-ember",
    "grants": {"property": "flaming"}, "motes": 30, "family": "fire", "phase": "noon",
    "polarity": "weapon", "affinity": ["copper"],
    "house": [{"type": "resistance", "damage_type": "fire", "amount": 1, "house": True},
              {"type": "skill_mod", "target": "stealth", "amount": -1,
               "bonus_type": "untyped", "house": True}],
    "working": [{"type": "working", "trait": "eager"},
                {"type": "working", "trait": "volatile"}],
    "weapon": [], "armour": [], "quench_mark": None, "color": "#e0703a", "text": "",
}
CALM = dict(copy.deepcopy(EMBER), id="test-calm", name="Test Calm", material="test-calm",
            tier="common", working=[{"type": "working", "trait": "eager"}])
COPPER = {"id": "copper", "name": "Copper", "kind": "metal", "tier": "common",
          "weapon": [], "armour": [], "working": [], "quench_mark": None}
FIXTURES = {d["id"]: d for d in (EMBER, CALM, COPPER)}


@pytest.fixture
def door(monkeypatch):
    fake = types.ModuleType("rules.materials")
    fake.get = lambda mid: copy.deepcopy(FIXTURES.get(mid))
    fake.all = lambda: copy.deepcopy(FIXTURES)
    fake.material_of = lambda mid: mid
    monkeypatch.setitem(sys.modules, "rules.materials", fake)
    return fake


# --- identify ----------------------------------------------------------------------------------

def test_identify_by_nine_over_shows_the_intent_only_and_by_ten_the_curse():
    """The plan's lane F test (§21.1) and CRB Cursed Items: "unless the check made to
    identify the item exceeds the DC by 10 or more, the curse is not detected. If the
    check ... still succeeds, all that is revealed is the magic item's original intent."
    DC 15 + caster level 10 (flaming) = 25."""
    rec = found(enchanted(curse=a_curse("opposite")))
    who = pc()
    nine = knowledge.identify(who, rec, 34, day=5)
    assert (nine["result"], nine["dc"], nine["learned"]) == ("intent", 25, ["intent"])
    assert nine["cursed"] is None and nine["curse"] is None
    assert rec["magic"]["known"]["intent"] is True and not rec["magic"]["known"].get("curse")
    ten = knowledge.identify(who, rec, 35, day=6)
    assert (ten["result"], ten["learned"], ten["cursed"]) == ("curse", ["curse"], True)
    assert ten["curse"] == curses.describe(rec["magic"]["curse"])
    assert rec["magic"]["known"]["curse"] is True


def test_identify_twice_in_one_day_returns_the_first_answer():
    """CRB Spellcraft: "you can only attempt to ascertain the properties of an individual
    item once per day. Additional attempts reveal the same results." A better roll the
    same day learns nothing; the next day it may."""
    rec = found(enchanted())
    who = pc()
    first = knowledge.identify(who, rec, 10, day=5)
    again = knowledge.identify(who, rec, 40, day=5)
    assert first["result"] == again["result"] == "fail"
    assert again["repeat"] is True and again["learned"] == [] and again["again_on_day"] == 6
    assert not rec["magic"]["known"].get("intent")
    assert knowledge.identify(who, rec, 40, day=6)["result"] == "curse"


def test_an_uncursed_item_checked_by_ten_says_so_and_never_invents_a_curse():
    """Passing the curse check on a clean item is knowledge too: the card stops saying
    "as the maker intended" and says no curse was found."""
    rec = found(enchanted())
    out = knowledge.identify(pc(), rec, 40, day=1)
    assert (out["result"], out["cursed"], out["curse"], out["learned"]) == (
        "curse", False, None, ["intent"])
    assert knowledge.item_card(rec)["curse"] == "none"


def test_identifying_a_catalogue_item_teaches_its_recipe():
    """Plan §12.3: "Identify: the recipe of a catalogue item"."""
    rec = found(protection_ring())
    who = pc()
    out = knowledge.identify(who, rec, 40, day=1)
    assert out["recipe"] == "mi-ring-protection-1"
    assert knowledge.knows_recipe(who, "mi-ring-protection-1")
    assert knowledge.identify(who, found(protection_ring("r2")), 40, day=1)["recipe"] is None


def test_a_plain_item_has_nothing_to_identify():
    assert knowledge.identify(pc(), forged(), 40, day=1)["result"] == "none"


def test_identify_writes_to_the_stored_item_not_a_copy():
    """A forged item lives in `Actor.stock` as a ForgedStock holding its record; what is
    learned must land on THAT record, or the next load forgets it."""
    from rules import forge_items

    who = pc()
    rec = found(enchanted(rid="kept"))
    who.add_stock(forge_items.stock_item(rec))
    out = knowledge.identify(who, "kept", 30, day=1)
    assert out["result"] == "intent"
    stored = knowledge.find_item(who, "kept")
    assert stored.record["magic"]["known"]["intent"] is True


# --- the hard way ------------------------------------------------------------------------------

def test_a_curse_found_the_hard_way_is_known_once():
    """Plan §12.2: the first time a curse's clause bites, it becomes known; the second
    time it is no news (the caller tells the moment only when this says True)."""
    rec = enchanted(curse=a_curse("specific"))
    who = pc()
    assert knowledge.learn_by_use(who, rec, "curse") is True
    assert knowledge.learn_by_use(who, rec, "curse") is False
    assert knowledge.item_card(rec)["clings"] is True
    clean = enchanted()
    assert knowledge.learn_by_use(who, clean, "curse") is False


def test_a_property_that_fires_is_learned_on_an_unidentified_item():
    rec = found(enchanted())
    who = pc()
    assert knowledge.learn_by_use(who, rec, "flaming") is True
    assert knowledge.learn_by_use(who, rec, "flaming") is False
    assert knowledge.item_card(rec)["learned_by_use"] == ["flaming"]


# --- unbind ------------------------------------------------------------------------------------

def test_unbind_teaches_types_and_returns_a_quarter_of_the_motes():
    """The plan's lane F test: Unbind teaches the property TYPES, never their size
    ("the magnitude is irrelevant", Skyrim), keeps the smith's item, and returns a
    quarter of the motes (owner round 4 Q6). A +1 flaming longsword is (1 + 1)² × 2,000
    = 8,000 gp; half to make, 4,000 gp = 40 motes; a quarter is 10."""
    who = pc()
    rec = enchanted(curse=a_curse("delusion"))
    out = knowledge.unbind(who, rec, clock=3 * 24 * 60)
    assert out["types"] == ["enhancement", "flaming"] == out["learned"]
    assert out["motes"] == 40 and out["residue"] == {"arcane-residue": 10}
    assert "magic" not in out["record"]
    assert out["record"]["pieces"] == rec["pieces"]
    assert knowledge.knows_property(who, "flaming") and knowledge.knows_property(
        who, "enhancement")
    assert knowledge.known_properties(who) == ["enhancement", "flaming"]
    assert who.herb_known["property:flaming"]["how"]["type"] == "unbound, day 4"
    again = knowledge.unbind(who, enchanted(), clock=0)
    assert again["learned"] == [] and again["types"] == ["enhancement", "flaming"]
    assert rec["magic"]["curse"]["row"] == "delusion"   # pure on the record


def test_unbinding_a_ring_teaches_its_recipe():
    who = pc()
    out = knowledge.unbind(who, protection_ring())
    assert out["recipe"] == "mi-ring-protection-1" and out["types"] == []
    # Ring of protection +1: 2,000 gp; 1,000 to make = 10 motes; a quarter, rounded down.
    assert out["motes"] == 10 and out["residue"] == {"arcane-residue": 2}


def test_property_knowledge_survives_a_save():
    """One store (contract §7): property types and recipes live in `Actor.herb_known`
    beside herbs and metals, and must round-trip a save."""
    who = pc()
    knowledge.unbind(who, enchanted(), clock=0)
    knowledge.unbind(who, protection_ring(), clock=0)
    back = from_dict(json.loads(json.dumps(to_dict(who))))
    assert knowledge.known_properties(back) == ["enhancement", "flaming"]
    assert knowledge.knows_recipe(back, "mi-ring-protection-1")


# --- essences ------------------------------------------------------------------------------------

def test_an_essence_has_one_key_per_trait_in_lane_ds_order(door):
    """Plan §7.2: the grant, each house top-up, the phase, the polarity, the affinity and
    each working trait are each a discoverable key. Before this, an essence document had
    0 keys: the material keys read `weapon`, `armour` and `working`, which an essence
    fills differently."""
    assert knowledge.property_keys(EMBER) == [
        "grants", "house:0", "house:1", "phase", "polarity", "affinity",
        "working:eager", "working:volatile"]
    assert knowledge.craft_of(EMBER) == knowledge.ENCHANTER
    assert sorted(knowledge.property_keys(EMBER), key=knowledge.key_order) == \
        knowledge.property_keys(EMBER)


def test_essence_keys_agree_with_lane_ds_door():
    """Two copies of one key rule drift (CLAUDE.md: grep for every copy). When lane D's
    `materials.essence_traits` exists, knowledge asks it and the two give one answer."""
    from rules import materials

    if not hasattr(materials, "essence_traits"):
        pytest.skip("lane D's essence_traits is not merged on this branch")
    assert knowledge.property_keys(EMBER) == list(materials.essence_traits(EMBER))


def test_an_alchemists_essence_keeps_its_material_keys():
    """The alchemist's catalogue files camphor under kind `essence` too; it is a
    reagent, not the circle's, and keeps the keys it always had."""
    from rules import materials

    camphor = materials.get("camphor")
    assert camphor is not None and not knowledge.is_essence(camphor)
    assert knowledge.craft_of(camphor) == knowledge.BLACKSMITH


def test_reading_an_essence_reveals_one_benefit_and_one_drawback(door):
    """Plan §12.3: "Read a pinch: one trait (the herb rule: one benefit and one drawback
    where there is one)". Rare is DC 20 (10 + 5 a band, as study). The drawback learned
    is the one that bit: a volatile phial's own house drawback."""
    who = pc()
    out = knowledge.read(who, "test-ember", 20, clock=0)
    assert (out["dc"], out["success"]) == (20, True)
    assert out["revealed"] == ["grants", "house:1"]
    assert out["cost"] == {"phial": 0.1} and out["minutes"] == 10
    rows = {r["key"]: r for r in knowledge.properties(who, EMBER)}
    assert rows["grants"]["text"] == "Binds Flaming" and rows["grants"]["group"] == "grants"
    assert rows["house:1"]["drawback"] is True
    assert rows["phase"]["text"] is None


def test_a_volatile_essence_bites_whatever_the_roll_with_its_own_drawback(door):
    """Plan §7.3: "volatile (Read is dangerous: reading it applies its house drawback for
    an hour, the forge's reactive-assay shape)". The essence's own drawback — never a
    hazard invented for the bench — on a miss too, for an hour; a calm phial is safe."""
    who = pc()
    miss = knowledge.read(who, "test-ember", 3, clock=0)
    assert miss["success"] is False and miss["revealed"] == []
    assert miss["danger"] == {"type": "skill_mod", "target": "stealth", "amount": -1,
                              "bonus_type": "untyped",
                              "duration": {"amount": 1, "unit": "hour"}}
    assert knowledge.read(who, "test-calm", 3, clock=0)["danger"] is None


def test_a_volatile_read_lands_through_the_one_applicator_with_a_tell(door):
    """Law 2 and law 3: the danger runs through the engine (`apply_danger`), lands as an
    effect with the essence as its origin, and is told."""
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=1))
    who = s.pc()
    out = knowledge.read(who, "test-ember", 3, clock=0)
    said = knowledge.apply_danger(e, who, "test-ember", out["danger"])
    assert said and all(o.tell for o in said)
    assert any(getattr(fx, "origin", "") == "item:test-ember" for fx in who.effects)


def test_attune_shows_where_it_sits_and_bind_what_it_binds(door):
    """Plan §12.3: Attune shows polarity and phase; Bind the granted property (ESO's
    translate-by-use)."""
    who = pc()
    assert knowledge.attuned(who, "test-ember", clock=0) == ["phase", "polarity"]
    assert knowledge.attuned(who, "test-ember", clock=0) == []
    assert knowledge.bound(who, "test-ember", clock=0) == ["grants"]
    assert knowledge.attuned(who, "copper", clock=0) == []


def test_the_essence_card_says_every_fact_in_words(door):
    """A fact with no effect document still needs a line: measured, the effect
    renderer answers an unknown type with its bare type id ("essence_fact")."""
    who = pc()
    knowledge.reveal(who, "test-ember", knowledge.property_keys(EMBER), "test")
    texts = {r["key"]: r["text"] for r in knowledge.properties(who, EMBER)}
    assert texts["phase"] == "Favours noon"
    assert texts["polarity"] == "Seats in a weapon"
    assert texts["affinity"] == "Takes to Copper"
    assert texts["working:volatile"].startswith("Volatile")    # lane A's renderer
    assert all(t and "essence_fact" not in t for t in texts.values())


def test_a_library_tells_a_common_essences_plain_facts_and_never_its_drawbacks(door):
    """The herbal and smithing rule (plan §12.3: libraries): common knowledge of a common
    or uncommon essence, never a drawback, never a rare one's."""
    common = set(knowledge.common_knowledge(CALM))
    assert {"grants", "phase", "polarity", "affinity", "house:0"} <= common
    assert "house:1" not in common
    assert knowledge.common_knowledge(EMBER) == []


def test_a_wizard_teaches_enchanting_and_a_smith_does_not():
    wizard = types.SimpleNamespace(name="Merrow the Wizard", template="", notes="")
    smith = types.SimpleNamespace(name="Hale the Smith", template="", notes="")
    assert knowledge.teaches(wizard, None, knowledge.ENCHANTER)
    assert not knowledge.teaches(smith, None, knowledge.ENCHANTER)
    assert knowledge.teaches(smith, None, knowledge.BLACKSMITH)


# --- manuals -----------------------------------------------------------------------------------

def test_every_enchanting_manual_names_real_things():
    """`manual_keys` skips an id nothing holds, silently: a mistyped id is a book that
    teaches nothing and says nothing. Every row is checked against the shipped files."""
    from rules import effectspec, materials

    books = knowledge.manuals(knowledge.ENCHANTER)
    assert len(books) >= 5
    words = {"all", "benefits", "drawbacks", "working"}
    for mid, m in books.items():
        assert m["teaches"] and m["price_gp"] > 0 and m["hours"] > 0, mid
        for row in m["teaches"]:
            if "essence" in row:
                doc = materials.get(row["essence"])
                assert doc and doc["kind"] == "essence", (mid, row)
                assert row["keys"] in words or isinstance(row["keys"], list), (mid, row)
            elif "recipe" in row:
                assert magic_layer.recipe(row["recipe"]) is not None, (mid, row)
            else:
                assert row["property"] == "enhancement" or effectspec.property(
                    row["property"]) is not None, (mid, row)


def test_a_manual_teaches_essences_recipes_and_property_types(door):
    book = {"teaches": [{"essence": "test-ember", "keys": "drawbacks"},
                        {"essence": "test-calm", "keys": "working"},
                        {"recipe": "mi-ring-protection-1"}, {"recipe": "no-such-ring"},
                        {"property": "keen"}, {"property": "enhancement"},
                        {"property": "no-such-property"}]}
    assert knowledge.manual_keys(book) == {
        "test-ember": ["house:1", "working:volatile"], "test-calm": ["working:eager"],
        "mi-ring-protection-1": ["recipe"], "property:keen": ["type"],
        "property:enhancement": ["type"]}


def test_enchanting_manuals_are_goods_and_a_bought_one_is_held():
    """The 0.2.4 lesson (tests/test_herb_manuals_market.py): a book with no goods row can
    never be bought. Every enchanting manual is a good; a bought one is shelved under its
    name and `holds_manual` finds it. (WHICH counter sells them is content/rules/
    stall-lines.json, owned by no lane this wave: see the lane F report.)"""
    books = knowledge.manuals(knowledge.ENCHANTER)
    table = {g.key: g for g in goods.table_goods("enchanting-manuals")}
    assert set(table) == set(books)
    manual = next(iter(books.values()))
    reader = Actor(name="Reader", ref="pc")
    assert not knowledge.holds_manual(reader, manual)
    goods.deliver(None, reader, table[manual["id"]], 1)
    assert knowledge.holds_manual(reader, manual)
    assert knowledge.manual_named(manual["name"], knowledge.ENCHANTER)["id"] == manual["id"]
    assert herbknowledge.manual_named(manual["name"]) is None


def test_the_other_crafts_manual_tables_are_unchanged():
    """The three goods tables are one builder now; the herbal and smithing ones must sell
    exactly the books they sold before."""
    assert {g.key for g in goods.table_goods("herbal-manuals")} == set(herbknowledge.manuals())
    assert {g.key for g in goods.table_goods("smithing-manuals")} == set(
        knowledge.manuals(knowledge.BLACKSMITH))


# --- the card ----------------------------------------------------------------------------------

def test_the_item_card_shows_only_what_is_known():
    """Plan §12.4: an unidentified found item reads "magic, moderate aura" and nothing
    else; identified, the maker's intent, marked as such until the curse check passes;
    the curse's words only once it is known. Measured against the curse's id and words."""
    curse = a_curse("opposite")
    rec = found(enchanted(curse=curse))
    blank = knowledge.item_card(rec)
    assert blank["aura"] == "moderate" and blank["identified"] is False
    assert "lines" not in blank and blank["curse"] is None
    knowledge.identify(pc(), rec, 30, day=1)
    seen = knowledge.item_card(rec)
    assert seen["lines"][0] == "+1 enhancement" and seen["as_intended"] is True
    assert curse["id"] not in json.dumps([blank, seen])
    assert curses.describe(curse) not in json.dumps([blank, seen])
    knowledge.identify(pc(), rec, 40, day=2)
    assert knowledge.item_card(rec)["curse"] == curses.describe(curse)
    assert knowledge.item_card(forged()) == {"magic": False}


def test_the_enchanting_manuals_are_on_a_counter():
    """Lane F built six enchanting manuals and no counter sold them — the 0.2.4 defect
    again (manuals in the data, none on any shelf), because a stall could list GEAR but not
    a whole table. The curio stall now carries the table, so every market sells them."""
    from rules import goods, market

    manuals = {g.name for g in goods.table_goods("enchanting-manuals")}
    on_shelf = {g.name for g in market.staples_of("market:stall-curios")}
    assert manuals and manuals <= on_shelf
