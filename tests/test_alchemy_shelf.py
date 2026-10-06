"""The alchemist's shelf door and the basilisk-eye collision (docs/alchemy-contracts.md §1,
§3, §4; docs/alchemy-revamp-plan.md §5.7, §13; alchemy lane A).

Measured before this lane, on 11ed095:

* `basilisk-eye` was the id of a herb (content/ingredients/herbs-and-parts.json, hybrid,
  rare) AND of an alchemist gland. `knowledge.resolve("basilisk-eye")` returned the
  gland, so the herb's own card was answered by another document, and one
  `herb_known["basilisk-eye"]` entry stood for both. The only id test compared the
  material catalogues with each other (507 ids, 0 clashes) and never with the herb
  corpus (161 ids), which is where the one clash was. The moment hybrid herbs join the
  alchemy shelf the two would have sat on it under one id.
* `knowledge.property_keys` was 0 for every one of the 139 alchemist materials:
  `MATERIAL_LISTS` knew only the forge's fields, so nothing about a reagent could be
  learned, taught, shown or assayed.

What is pinned: one id per thing across every catalogue and the herb corpus; the
basilisk eye is one document (the herb) carrying the gland's trait; the alchemy shelf
is the catalogue plus every hybrid herb, the herb read by the same keys on both
shelves; a reagent's product, mishap and toxic documents are properties; formulae and
identified potions live in the one store.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import crafting, knowledge, materials
from rules import ingredients as ing_mod
from rules.sheet import Actor

MATERIALS = Path("content/materials")
INGREDIENTS = Path("content/ingredients")


def _material_ids() -> dict[str, list[str]]:
    seen: dict[str, list[str]] = {}
    for path in MATERIALS.glob("*-materials.json"):
        for m in json.loads(path.read_text(encoding="utf-8"))["materials"]:
            seen.setdefault(m["id"], []).append(path.stem)
    return seen


def _ingredient_ids() -> dict[str, list[str]]:
    seen: dict[str, list[str]] = {}
    for path in INGREDIENTS.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("ingredients") if isinstance(data, dict) else data
        for e in rows or ():
            if isinstance(e, dict) and e.get("id"):
                seen.setdefault(e["id"], []).append(path.stem)
    return seen


def _pc() -> Actor:
    return Actor(name="Alchemist", ref="pc")


# --- one id per thing -------------------------------------------------------------------------

def test_no_material_id_is_claimed_by_two_crafts():
    """One shelf, four catalogues, and `load_dir` merges by id in filename order — so a
    duplicate id means the alphabetically-later craft silently wins.

    Measured when this was first written (tests/test_alchemist.py, moved here): the
    alchemist's `blessed-water` (uncommon solvent) was shadowed by the blacksmith's
    `blessed-water` (rare quenchant), which moved four potions up a tier and removed the
    reaction medium from three chains, with nothing anywhere reporting a problem.
    """
    clashes = {k: v for k, v in _material_ids().items() if len(v) > 1}
    assert not clashes, f"ids claimed by two crafts: {clashes}"


def test_no_material_id_is_also_a_herb_id():
    """Every material id against every ingredient id, not the catalogues against each
    other only. Measured 2026-10-06: 507 material ids and 161 ingredient ids, ONE clash —
    `basilisk-eye`, a hybrid herb and an alchemist gland — which the catalogue-only test
    above could not see. `knowledge.resolve` asks materials first, so the herb's card
    resolved to the gland, and one `herb_known` entry stood for two documents. With the
    hybrid door open (`materials.alchemy_shelf`) the two would have shared one shelf id.
    The fix merged the gland into the herb; the next clash fails here, by name."""
    mats, ings = _material_ids(), _ingredient_ids()
    assert len(mats) > 400 and len(ings) > 150, "the corpora did not load"
    clashes = sorted(set(mats) & set(ings))
    assert clashes == [], f"ids that are both a material and a herb: {clashes}"
    dupes = {k: v for k, v in ings.items() if len(v) > 1}
    assert not dupes, f"herb ids claimed twice: {dupes}"


def test_the_knowledge_module_says_what_the_test_checks():
    """knowledge.py's docstring claimed `tests/test_alchemist.py` pinned the two id spaces
    disjoint; that test compared material files only with each other. The comment names
    this file now, and the old claim is gone."""
    doc = knowledge.__doc__ or ""
    assert "tests/test_alchemy_shelf.py pins it" in doc
    assert "(`tests/test_alchemist.py` pins it)" not in doc


# --- the basilisk eye is one document ----------------------------------------------------------

def test_the_basilisk_eye_is_the_herb_and_carries_the_glands_trait():
    """The merge (plan §5.7): one intact basilisk eye, the herb's document. The gland's
    Fortitude DC 15 or staggered 1d4 rounds is on the herb as an `external` product trait;
    its narrative half ("the touched flesh greys...") was dropped, staggered being what it
    does. No alchemist row of that id remains, and the id resolves to the herb."""
    assert materials.get("basilisk-eye") is None
    herb = knowledge.resolve("basilisk-eye")
    assert isinstance(herb, ing_mod.Ingredient) and herb.hybrid
    gates = [s for s in herb.specs if s.get("type") == "save_gate"]
    assert len(gates) == 1
    gate = gates[0]
    assert (gate["target"], gate["dc"], gate["route"]) == ("fort", 15, "external")
    assert gate["on_failure"] == [{"type": "apply_condition", "target": "staggered",
                                   "duration": {"amount": "1d4", "unit": "round"}}]
    assert not any(s.get("type") == "narrative" for s in materials.product_traits(herb))
    # The herb bench still drops it: external is alchemy's alone.
    assert ing_mod.route_of(gate) == "external"


def test_old_knowledge_of_the_basilisk_eye_reads_against_the_herb():
    """Saves made before the merge stored what a taste taught under "basilisk-eye" with
    the herb's keys (the gland had none to learn: 0 property keys). Those keys still name
    the same three effects; the merged trait is the one new unknown, on both shelves."""
    pc = _pc()
    pc.herb_known["basilisk-eye"] = {"keys": ["p0", "p1", "p2"], "how": {}}
    herb = knowledge.resolve("basilisk-eye")
    view = materials.alchemy_doc("basilisk-eye")
    assert knowledge.known_keys(pc, herb) == ["p0", "p1", "p2"]
    assert knowledge.known_keys(pc, view) == ["p0", "p1", "p2"]
    assert knowledge.unknown_count(pc, herb) == knowledge.unknown_count(pc, view) == 1


# --- the hybrid door -----------------------------------------------------------------------------

def test_the_alchemy_shelf_is_the_catalogue_plus_every_hybrid_herb():
    """Plan §5.7, the owner's Q2.1: the alchemist's materials plus every ingredient with
    `hybrid: true` (63 shipped), no herb copied into content/materials, and nobody
    else's catalogue on it."""
    shelf = materials.alchemy_shelf()
    catalogue = {m["id"] for m in json.loads(
        (MATERIALS / "alchemist-materials.json").read_text(encoding="utf-8"))["materials"]}
    hybrids = {k for k, i in ing_mod.all_ingredients().items() if i.hybrid}
    assert len(hybrids) == 63
    assert catalogue | hybrids == set(shelf)
    for hid in hybrids:
        assert materials.is_herb_view(shelf[hid]) and shelf[hid]["hybrid"]
    for mid in catalogue:
        assert shelf[mid]["catalogue"] == materials.ALCHEMY_CATALOGUE
    assert "iron" not in shelf and "mithral" not in shelf
    assert materials.alchemy_doc("iron") is None
    assert materials.alchemy_doc("comfrey") is None or materials.alchemy_doc(
        "comfrey")["hybrid"], "a non-hybrid herb is the herbalist's alone"


def test_a_hybrids_external_effects_reach_the_alchemy_shelf():
    """The herb bench drops an `external` effect as "alchemy only"; this shelf is where
    they go. Every effect of every hybrid is a product trait, all routes included, and in
    the herb's own order."""
    shelf = materials.alchemy_shelf()
    external = 0
    for hid, ing in ing_mod.all_ingredients().items():
        if not ing.hybrid:
            continue
        product = materials.product_traits(shelf[hid])
        assert product == [spec for _, spec in ing.pairs], hid
        assert materials.product_traits(ing) == product, hid
        external += sum(1 for s in product if ing_mod.route_of(s) == "external")
    assert external >= 49, external


def test_a_hybrid_is_read_by_the_same_keys_on_both_shelves():
    """One document, one store (plan §13.2: "tasting a hybrid herb at the herb bench
    still works, and teaches the herb's traits on both shelves"). For every one of the 63
    hybrids, the shelf's view and the herb give the same keys, the same benefit and
    drawback classes and the same poison gates — so a taste and an assay pick from one
    set, and the herbarium and the codex count one number."""
    shelf = materials.alchemy_shelf()
    for hid, ing in ing_mod.all_ingredients().items():
        if not ing.hybrid:
            continue
        a, b = knowledge.anatomy(shelf[hid]), knowledge.anatomy(ing)
        assert a["keys"] == b["keys"], hid
        assert a["kinds"] == b["kinds"], hid
        assert a["gate_of"] == b["gate_of"], hid
        assert knowledge.doc_id(shelf[hid]) == hid
        assert knowledge.craft_of(shelf[hid]) == knowledge.HERBALIST


def test_tasting_a_hybrid_teaches_the_alchemist_too():
    pc = _pc()
    herb = knowledge.resolve("basilisk-eye")
    knowledge.reveal(pc, "basilisk-eye", knowledge.reveal_picks(pc, herb), "tasted, day 1")
    view = materials.alchemy_doc("basilisk-eye")
    known = knowledge.known_keys(pc, view)
    assert known and known == knowledge.known_keys(pc, herb)
    rows = {r["key"]: r for r in knowledge.properties(pc, view)}
    assert all(rows[k]["known"] for k in known)
    assert rows["p3"]["group"] == "product"


def test_a_homebrew_herb_cannot_take_a_materials_place(settings, tmp_path):
    """Should a homebrew herb ever take a material's id, the material keeps it on the
    shelf, as `knowledge.resolve` answers (materials first): the shelf and the store must
    give one answer."""
    home = tmp_path / "campaign"
    home.mkdir()
    hb = tmp_path / "homebrew" / "ingredients"
    hb.mkdir(parents=True)
    (hb / "brimstone.json").write_text(json.dumps({
        "id": "brimstone", "name": "Brimstone Weed", "kind": "herb", "hybrid": True,
        "effects": [{"type": "heal", "dice": "1d4"}]}), encoding="utf-8")
    settings.CAMPAIGN_DIR = str(home)
    shelf = materials.alchemy_shelf()
    assert shelf["brimstone"]["catalogue"] == materials.ALCHEMY_CATALOGUE
    assert knowledge.resolve("brimstone")["catalogue"] == materials.ALCHEMY_CATALOGUE


# --- the alchemy material document (contract §3) -----------------------------------------------

def test_an_old_alchemist_entry_reads_its_effects_as_product():
    """Every pre-revamp alchemist row has `effects`; the normaliser reads that as
    `product`, the forge's legacy trick, so nothing needs rewriting before lane D's pass.
    A forge or enchanter row's `effects` is NOT a product (the blacksmith still reads it
    as item effects)."""
    # The shipped rows were rewritten by lane D (they write `product`, and keep `effects`
    # for the old chain bench), so the legacy read is held on an unwritten row below; a
    # shipped row's `product` is what it wrote, never its legacy `effects`.
    brim = materials.get("brimstone")
    assert brim["product"] and brim["product"] != brim["effects"]
    assert all(t.get("essence") for t in brim["product"])
    assert materials.is_alchemy(brim)
    for mid in ("iron", "mithral"):
        doc = materials.get(mid)
        assert doc["product"] == [] and not materials.is_alchemy(doc)
    raw = {"id": "x", "kind": "reagent", "effects": [{"type": "heal", "dice": "1d4"}]}
    assert materials.normalise(raw, materials.ALCHEMY_CATALOGUE)["product"] == raw["effects"]
    assert materials.normalise(raw, materials.FORGE_CATALOGUE)["product"] == []
    written = dict(raw, product=[{"type": "heal", "dice": "1d6"}])
    assert materials.normalise(written, materials.ALCHEMY_CATALOGUE)["product"] == \
        written["product"]


def test_the_new_fields_default_and_the_colour_keeps_its_shelfs_shape():
    """Every field defaults (contract §3): an old file loads. The alchemist's colour is the
    [r, g, b] the stage draws; the enchanter's is a CSS string. Folding one into the
    other's shape would hand the stage "[0.86, 0.78, 0.22]" as a string."""
    doc = materials.normalise({"id": "y", "kind": "reagent"}, materials.ALCHEMY_CATALOGUE)
    assert (doc["product"], doc["mishap"], doc["toxic"], doc["color"]) == ([], None, None, "")
    rgb = materials.normalise({"id": "y", "color": [0.86, 0.78, 0.22]}, "")
    assert rgb["color"] == [0.86, 0.78, 0.22]
    css = materials.normalise({"id": "y", "color": "#c8a2ff"}, materials.ENCHANT_CATALOGUE)
    assert css["color"] == "#c8a2ff"


def test_product_essences_reads_the_essence_of_each_trait():
    doc = {"id": "z", "catalogue": materials.ALCHEMY_CATALOGUE, "product": [
        {"type": "damage", "dice": "1d6", "damage_type": "fire", "essence": "fire"},
        {"type": "skill_mod", "target": "stealth", "amount": -2, "essence": "shadow",
         "drawback": True},
        {"type": "heal", "dice": "1d4"}]}
    assert materials.product_essences(doc) == {"fire", "shadow"}
    # The enchanter's `essences()` is untouched: every essence document on its shelf.
    assert isinstance(materials.essences(), dict)


# --- knowledge (contract §4) ---------------------------------------------------------------------

REAGENT = {
    "id": "testbrim", "name": "Testbrim", "kind": "reagent", "tier": "common",
    "catalogue": materials.ALCHEMY_CATALOGUE, "material": "testbrim",
    "product": [
        {"type": "damage", "dice": "1d6", "damage_type": "fire", "route": "struck",
         "essence": "fire", "grade": 1},
        {"type": "skill_mod", "target": "stealth", "amount": -2, "bonus_type": "untyped",
         "route": "carried", "essence": "shadow", "drawback": True}],
    "working": [{"type": "working", "trait": "volatile"}],
    "mishap": {"type": "damage", "dice": "1d6", "damage_type": "fire", "recipient": "self"},
    "toxic": {"type": "ability_damage", "target": "con", "dice": "1d2"},
}


def test_a_reagents_product_working_mishap_and_toxic_are_properties():
    """Contract §4: `MATERIAL_LISTS` counts product, working, mishap and toxic, so a
    reagent written to plan §5.6 has at least 3 properties (it was 0 for all 139)."""
    assert knowledge.property_keys(REAGENT) == ["p0", "p1", "t0", "m0", "x0"]
    kinds = knowledge.anatomy(REAGENT)["kinds"]
    # Fire on the struck foe is the flask's point; the stealth cost says it is one;
    # volatility is a working drawback; the mishap and the toxic document are costs to
    # whoever works it, whatever their type.
    assert kinds == {"p0": knowledge.BENEFIT, "p1": knowledge.DRAWBACK,
                     "t0": knowledge.DRAWBACK, "m0": knowledge.DRAWBACK,
                     "x0": knowledge.DRAWBACK}
    stable = dict(REAGENT, working=[{"type": "working", "trait": "stabilizer"},
                                    {"type": "working", "trait": "corrosive"}])
    assert [knowledge.anatomy(stable)["kinds"][k] for k in ("t0", "t1")] == [
        knowledge.BENEFIT, knowledge.DRAWBACK]
    rows = knowledge.properties(_pc(), REAGENT)
    assert [r["group"] for r in rows] == ["product", "product", "working", "mishap",
                                         "toxic"]
    assert not any(r["known"] for r in rows)


def test_an_alchemists_form_keeps_its_own_store():
    """A forge form shares its parent's store because a form of mithral is read by
    mithral's lists. An alchemist's form is not: iron filings carry their own product
    traits. Measured when the alchemist's lists joined: of the 9 alchemist forms, iron
    filings and the iron flask would have shared one "p0" under "iron", and cinnabar
    would have shared "p0" with quicksilver (an alchemist reagent with an effect of its
    own) — the basilisk-eye collision one level down. Each is stored and resolved under
    its own id; the forge's forms still go to their parent."""
    pc = _pc()
    for mid in ("iron-filings", "iron-flask", "cinnabar", "mithral-dust"):
        doc = knowledge.resolve(mid)
        assert doc["id"] == mid and knowledge.doc_id(doc) == mid
    knowledge.reveal(pc, "cinnabar", ["p0"], "assayed, day 1")
    assert "cinnabar" in pc.herb_known and "quicksilver" not in pc.herb_known
    assert knowledge.known_keys(pc, knowledge.resolve("quicksilver")) == []
    # The forge's form rule is untouched: an ore is still learned on its metal.
    ore = next(d for d in materials.all().values()
               if d["kind"] == "ore" and d["material"] != d["id"])
    assert knowledge.doc_id(ore) == materials.material_of(ore["id"])


def test_the_shipped_alchemist_materials_now_have_properties():
    """Measured before: 0 keys on all 139. After this lane, every alchemist material that
    carries an effect has a key per effect; the 70 that carry none get theirs from lane
    D's data pass (plan §5.8), and this test is where that count is held."""
    shelf = materials.alchemy_shelf()
    mats = [d for d in shelf.values() if not d.get("hybrid")]
    with_keys = [d for d in mats if knowledge.property_keys(d)]
    assert len(mats) == 138                               # 139 less the basilisk eye
    # Lane D's data pass (2026-10-06) gave every one of the 138 its properties: product
    # traits on the 112 reagents, working traits (and a mishap or toxic document) on the
    # 26 vessels, catalysts, neutral media and prima materia, at least 3 on each.
    assert len(with_keys) == 138
    for d in with_keys:
        assert len(knowledge.property_keys(d)) >= max(3, len(d["product"]))


def test_the_forge_and_the_circle_keep_their_keys():
    """Adding the alchemist's lists moved no other craft's keys: a metal is still
    w/a/t/q, an essence still named keys, a herb still p."""
    iron = materials.get("iron")
    assert all(k[0] in "watq" for k in knowledge.property_keys(iron))
    ess = next(d for d in materials.all().values() if knowledge.is_essence(d))
    assert all(":" in k or k in ("grants", "phase", "polarity", "affinity")
               for k in knowledge.property_keys(ess))
    assert all(k.startswith("p") for k in knowledge.property_keys(ing_mod.get("comfrey")))


def test_the_alchemists_rows_can_be_asked_before_their_files_exist():
    """`ALCHEMIST` is a craft the knowledge rows answer for, so lane H's
    alchemy-manuals.json is read the moment it ships. Until an alchemy lore file ships,
    the alchemist reads the herbalist's rows, the plan's own route for teachers and
    libraries (§13.3); until the manuals ship there are none, rather than a crash.
    A hybrid herb on either shelf answers to the herbalist's rows."""
    if not (Path("content/rules") / "alchemy-lore.json").is_file():
        assert knowledge.lore(knowledge.ALCHEMIST) is knowledge.lore(knowledge.HERBALIST)
    if not (Path("content/rules") / "alchemy-manuals.json").is_file():
        assert knowledge.manuals(knowledge.ALCHEMIST) == {}
    assert knowledge.craft_of(materials.alchemy_doc("basilisk-eye")) == knowledge.HERBALIST
    assert knowledge.study_dc(materials.get("brimstone")) == 10


def test_assaying_a_hybrid_herb_costs_a_pinch_and_teaches_the_herbs_keys():
    """Plan §13.2: a pinch, a tenth of a unit. An alchemist may assay a basilisk eye as
    readily as brimstone, and what it teaches is the herb's own keys."""
    pc = _pc()
    res = knowledge.assay(pc, "basilisk-eye", 40, clock=0)
    assert res["success"] and res["cost"] == {"pinch": 0.1}
    assert res["revealed"]
    assert set(res["revealed"]) <= set(knowledge.property_keys(knowledge.resolve(
        "basilisk-eye")))
    assert knowledge.assay(pc, "brimstone", 0, clock=0)["cost"] == {"pinch": 0.1}
    assert "bars" in knowledge.assay(pc, "iron", 0, clock=0)["cost"]


def test_the_codex_lists_what_was_met_on_the_alchemy_shelf():
    pc = _pc()
    knowledge.reveal(pc, "basilisk-eye", ["p0"], "tasted, day 1")
    pc.inventory["brimstone"] = 2
    pc.herb_known["iron"] = {"keys": ["w0"], "how": {}}
    rows = {r["id"]: r for r in knowledge.alchemy_codex(pc)}
    assert set(rows) == {"basilisk-eye", "brimstone"}
    assert rows["basilisk-eye"]["known"] == 1 and rows["basilisk-eye"]["total"] == 4
    assert rows["basilisk-eye"]["hybrid"] and not rows["brimstone"]["hybrid"]


# --- formulae and potions in the one store -------------------------------------------------------

def test_formulae_are_kept_in_the_one_store_under_their_prefix():
    """Contract §4: formula ids are stored as "formula:<id>"; lane E reads and writes
    through these, never a second list. The colon keeps them out of every other id space
    (materials and herbs are lowercase letters, digits and hyphens)."""
    pc = _pc()
    assert not knowledge.knows_formula(pc, "alchemists-fire")
    assert knowledge.learn_formula(pc, "alchemists-fire", "starting knowledge")
    assert not knowledge.learn_formula(pc, "alchemists-fire", "again")
    assert knowledge.knows_formula(pc, "alchemists-fire")
    assert knowledge.known_formulae(pc) == ["alchemists-fire"]
    assert knowledge.formula_how(pc, "alchemists-fire") == "starting knowledge"
    assert "formula:alchemists-fire" in pc.herb_known
    assert knowledge.alchemy_codex(pc) == []


def test_identifying_a_potion_is_dc_15_plus_its_spell_level():
    """Plan §11.3: DC 15 + spell level, holding it a round (the CRB's Potions page; its
    Perception table says caster level instead, noted in knowledge.py). The level is the
    authored potion's row (cure moderate wounds: 2), else the spell's lowest list level.
    It reveals what the potion is and never the formula; a miss reveals nothing."""
    pc = _pc()
    vial = crafting.Stock(base="Potion of Cure Moderate Wounds", craft="alchemy",
                          holds_spell="cure-moderate-wounds", caster_level=3)
    assert knowledge.potion_identify_dc(vial) == 17
    miss = knowledge.identify_potion(pc, vial, 16)
    assert not miss["success"] and miss["spell"] is None and miss["name"] is None
    assert not knowledge.potion_known(pc, vial)
    hit = knowledge.identify_potion(pc, vial, 17, clock=0)
    assert hit["success"] and hit["spell"] == "cure-moderate-wounds"
    assert (hit["spell_level"], hit["caster_level"], hit["rounds"]) == (2, 3, 1)
    assert knowledge.potion_known(pc, vial)
    assert knowledge.known_formulae(pc) == []
    plain = crafting.Stock(base="Tanglefoot Bag", craft="alchemy")
    assert knowledge.potion_identify_dc(plain) == 15
