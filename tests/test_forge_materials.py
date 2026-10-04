"""The forge's materials: one door, typed effects, the book's numbers, and nothing inert.

Measured before the data pass (docs/blacksmithing-revamp-plan.md §5.1): of 112 smithing
materials, 57 had no effect at all; of the 63 effects that did exist, 40 were `narrative`
prose nothing could execute; none carried a piece, and no material had three properties to
discover (0 traits: 58, 1: 47, 2: 7). Eleven entries contradicted the printed PF1e rule
(docs/blacksmithing-prior-art.md §5.2): mithral claimed a lighter category "for
proficiency", abysium carried an invented DC 18 save where the book has none, horacalcum
gave +1 initiative regardless of armour weight, singing steel an invented Perform bonus,
and inubrix and noqual had lost their drawbacks.

These tests pin plan §16.1 lane 4: every structural material has 3 + 3 effects with a
drawback in each, no narrative, the book effects equal the sweep's table, house numbers
inside the tier ceilings, every material relevant and discoverable, and `validate`
refusing each violation with the fix named.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest
from django.conf import settings

from rules import effectspec, materials

FILE = Path(settings.BASE_DIR) / "content" / "materials" / "blacksmith-materials.json"


@pytest.fixture(scope="module")
def forge() -> list[dict]:
    materials.refresh()
    return [d for d in materials.all().values()
            if d["catalogue"] == materials.FORGE_CATALOGUE]


def _by_id(forge):
    return {d["id"]: d for d in forge}


# --- the door ---------------------------------------------------------------------------------

def test_the_door_reads_all_four_catalogues():
    """One door to the shared shelf (contract §3). Each craft read `content/materials`
    through its own loader in its own dialect; a door that read only the forge's file
    could not answer "what is mithral dust?" and "one material, many shelves" would
    have nowhere to stand."""
    shelf = materials.all()
    cats = {d["catalogue"] for d in shelf.values()}
    assert set(materials.CATALOGUES) <= cats
    assert len(shelf) > 450, len(shelf)
    # Products are not materials: the spell potions and magic items stay out.
    assert not any(c in ("alchemist-spell-potions", "magic-items") for c in cats)


def test_an_old_entry_loads_with_every_field_defaulted():
    """The herbprep rule: every field defaults, so a homebrew metal written before the
    revamp loads instead of crashing the bench. Empty is a list, never None, so a reader
    can iterate without a guard."""
    doc = materials.normalise({"id": "Orichalch", "name": "Orichalch", "kind": "metal"})
    assert doc["id"] == "orichalch" and doc["material"] == "orichalch"
    assert doc["pieces"] == {"weapon": [], "armour": []}
    assert doc["weapon"] == [] and doc["armour"] == [] and doc["working"] == []
    assert doc["quench_mark"] is None and doc["book"] is False
    assert doc["form"] == "bar" and doc["tier"] == "common"


def test_get_returns_a_copy_the_caller_cannot_poison():
    """`get` serves a read-only document. A bench that appended a scaled effect to the
    cached list would change iron for every later reader in the process."""
    iron = materials.get("iron")
    iron["weapon"].append({"type": "narrative", "target": "poison"})
    assert len(materials.get("iron")["weapon"]) == 3
    assert materials.get("no-such-metal") is None


def test_a_homebrew_metal_appears_and_disappears_without_a_refresh():
    """The door's cache is keyed on the homebrew it read. tests/test_three_laws.py records
    the defect this avoids: thirteen content caches held one test's homebrew for every
    test after it, because sixteen tests move `settings.CAMPAIGN_DIR` and never restore
    it. A changed file or a moved directory is a new key, so nothing has to remember to
    drop this cache."""
    home = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "materials"
    home.mkdir(parents=True, exist_ok=True)
    path = home / "test-forge-orichalch.json"
    materials.get("iron")                      # fill the cache first
    path.write_text(json.dumps({"id": "test-forge-orichalch", "name": "Orichalch",
                                "kind": "metal", "tier": "rare"}), encoding="utf-8")
    try:
        doc = materials.get("test-forge-orichalch")
        assert doc is not None and doc["catalogue"] == "" and materials.is_forge(doc)
        # An old-shaped homebrew metal loads, and the validator says what it lacks.
        assert any("no working trait" in p for p in materials.validate(doc))
    finally:
        path.unlink(missing_ok=True)
    assert materials.get("test-forge-orichalch") is None


def test_of_kind_lists_in_the_order_a_smith_climbs():
    from rules.worldclass import TIERS

    ranks = [TIERS.index(d["tier"]) for d in materials.of_kind("metal")]
    assert ranks == sorted(ranks)
    assert len(materials.of_kind("metal")) == 21


def test_one_material_many_shelves():
    """The owner's ruling: mithral is one document, and the leatherworker's fittings, the
    enchanter's filings and the alchemist's dust are forms of it. Ids are kept (test_
    alchemist.py pins cross-file uniqueness), so the link is a field and the parent's
    list of forms is computed, never stored, so it cannot go stale."""
    assert materials.material_of("mithral-fittings") == "mithral"
    assert materials.material_of("mithral-dust") == "mithral"
    assert materials.material_of("true-silver-shavings") == "mithral"
    assert materials.material_of("adamantine-dust") == "adamantine"
    assert materials.material_of("cold-iron-studs") == "cold-iron"
    assert materials.material_of("silver-ink") == "silver"
    assert materials.material_of("mithral-ore") == "mithral"
    assert materials.material_of("mithral") == "mithral"
    assert materials.material_of("nothing-at-all") == "nothing-at-all"
    forms = materials.get("mithral")["forms"]
    for shelf in ("ore:mithral-ore", "catalyst:mithral-dust", "catalyst:mithral-filings",
                  "fitting:mithral-fittings"):
        assert shelf in forms, forms


def test_every_link_names_a_real_parent():
    """A link to a parent that does not exist is a form of nothing: learning it would
    teach no material at all."""
    shelf = materials.all()
    bad = {k: d["material"] for k, d in shelf.items() if d["material"] not in shelf}
    assert not bad, bad


def test_every_ore_smelts_to_its_metal(forge):
    """Plan §5.2: a prospected ore and a bought bar are the same material, so an ore
    points at its metal and is assayed for it. Nickel ore alone smelts to no forgeable
    metal and says what it feeds instead."""
    for d in forge:
        if d["kind"] != "ore":
            continue
        assert d["form"] == "ore"
        assert d["material"] != d["id"] or d["feeds"], d["id"]
    assert materials.material_of("iron-ore") == "iron"
    assert materials.material_of("cinnabar-ore") == "quicksilver"


def test_the_catalogue_kept_its_ids_names_and_kinds(forge):
    """Ids, names and the 8 kinds do not change (contract §3): the bench, saved stock and
    tests/test_blacksmith.py all key on them. Counted per kind as the inventory had them."""
    kinds: dict[str, int] = {}
    for d in forge:
        kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
    assert kinds == {"ore": 20, "metal": 21, "alloy": 15, "fuel": 10, "flux": 9,
                     "quenchant": 11, "fitting": 16, "treatment": 10}


# --- the shipped data passes its own validator ------------------------------------------------

def test_every_shipped_forge_material_is_valid(forge):
    """The whole of plan §5.7 in one gate: run the validator over all 112."""
    problems = [p for d in forge for p in materials.validate(d)]
    assert not problems, "\n".join(problems)


def test_every_linked_form_on_the_other_shelves_is_valid():
    shelf = materials.all()
    problems = [p for d in shelf.values() if d["material"] != d["id"]
                for p in materials.validate(d)]
    assert not problems, "\n".join(problems)


def test_every_structural_material_has_three_and_three_with_a_drawback(forge):
    """The owner's rule: at least 3 weapon and 3 armour modifiers per structural material
    where it fills that gear's piece, and at least one negative in each. Before the pass
    the most any material had was 2, and most metals had none."""
    short, no_drawback = [], []
    for d in forge:
        if d["kind"] not in materials.STRUCTURAL:
            continue
        for gear in materials.GEARS:
            if not d["pieces"][gear]:
                continue
            if len(d[gear]) < 3:
                short.append(f"{d['id']} {gear}: {len(d[gear])}")
            if not any(materials.is_negative(e) for e in d[gear]):
                no_drawback.append(f"{d['id']} {gear}")
    assert not short, short
    assert not no_drawback, no_drawback


def test_no_material_effect_is_narrative(forge):
    """40 of the 63 material effects were `narrative`: prose that looked authored and did
    nothing. Every forge effect is now a document the engine can run."""
    found = []
    for d in forge:
        specs = d["weapon"] + d["armour"] + ([d["quench_mark"]] if d["quench_mark"] else [])
        for spec in specs:
            for nested in materials._walk(spec):
                if nested.get("type") == "narrative" or not effectspec.executable(nested):
                    found.append(f"{d['id']}: {nested.get('type')}")
    assert not found, found


def test_every_effect_passes_the_shared_vocabulary(forge):
    problems = []
    for d in forge:
        for gear in materials.GEARS:
            for i, spec in enumerate(d[gear]):
                problems.extend(effectspec.validate(spec, f"{d['id']} {gear} {i + 1}"))
        for i, spec in enumerate(d["working"]):
            problems.extend(effectspec.validate(spec, f"{d['id']} working {i + 1}"))
        if d["quench_mark"]:
            problems.extend(effectspec.validate(d["quench_mark"], f"{d['id']} mark"))
    assert not problems, "\n".join(problems)


def test_house_numbers_stay_inside_the_tier_ceilings(forge):
    """Small numbers so materials can be worked up without becoming overpowered: a house
    modifier is at most ±2 common/uncommon, ±3 rare/exotic, ±4 legendary, and a summed one
    at least ±2 (the owner's base, so a half-weight piece still moves a number)."""
    over, under = [], []
    for d in forge:
        ceiling = materials.TIER_CEILING[d["tier"]]
        for gear in materials.GEARS:
            for e in d[gear]:
                if e.get("book"):
                    continue
                pts = materials.points(e)
                if pts is None:
                    continue
                if pts > ceiling:
                    over.append(f"{d['id']} {gear} {e['type']} {e.get('target')}: {pts}")
                if d["kind"] in materials.STRUCTURAL and pts < materials.HOUSE_FLOOR:
                    under.append(f"{d['id']} {gear} {e['type']} {e.get('target')}: {pts}")
        if d["quench_mark"]:
            for e in materials._walk(d["quench_mark"]):
                pts = materials.points(e)
                if pts is not None and pts > ceiling:
                    over.append(f"{d['id']} mark: {pts}")
    assert not over, over
    assert not under, under
    assert materials.TIER_CEILING == {"common": 2, "uncommon": 2, "rare": 3, "exotic": 3,
                                      "legendary": 4}


def test_every_material_has_a_working_trait_and_consumables_have_only_those(forge):
    """Two layers (plan §5.1): every material behaves some way at the forge. Fuels and
    fluxes carry working traits only, and quenchants add exactly one mark (the owner's
    rulings)."""
    for d in forge:
        assert d["working"], d["id"]
        assert all(w["type"] == "working" and w["trait"] in effectspec.WORKING_TRAITS
                   for w in d["working"]), d["id"]
        if d["kind"] in ("fuel", "flux"):
            assert not d["weapon"] and not d["armour"] and not d["quench_mark"], d["id"]
        if d["kind"] == "quenchant":
            assert isinstance(d["quench_mark"], dict), d["id"]
        else:
            assert d["quench_mark"] is None, d["id"]


def test_every_material_has_three_discoverable_properties(forge):
    """Herbalism's "three traits to discover" rule. Measured before: 0 of 112 materials had
    three. An ore counts its metal's, because assaying ore is how a metal is learned."""
    shelf = materials.all()
    thin = []
    for d in forge:
        n = materials.properties(d)
        if d["material"] != d["id"]:
            parent = shelf[materials.material_of(d["id"])]
            n += materials.properties(parent) + (
                0 if materials.is_forge(parent) else len(parent["effects"]))
        if n < 3:
            thin.append(f"{d['id']}: {n}")
    assert not thin, thin


def test_every_material_is_relevant(forge):
    """Herbalism's relevance rule (test_herb_relevance.py's pattern): a material fills a
    piece, feeds a method or finishes an item. A shelf entry that does none of those is a
    thing to buy and never use."""
    idle = []
    for d in forge:
        ok = (any(d["pieces"][g] for g in materials.GEARS)
              or d["kind"] in ("fuel", "flux", "quenchant")
              or (d["kind"] == "treatment" and d["finishes"]
                  and any(d[g] for g in d["finishes"]))
              or d["feeds"]
              or (d["kind"] == "ore" and d["material"] != d["id"]))
        if not ok:
            idle.append(d["id"])
    assert not idle, idle


def test_book_flag_agrees_with_book_effects(forge):
    for d in forge:
        has = any(e.get("book") for g in materials.GEARS for e in d[g])
        assert d["book"] == has, d["id"]


# --- the book's numbers -----------------------------------------------------------------------
#
# Stated here independently of tools/forge_data_pass.py, by hand from
# docs/blacksmithing-prior-art.md §1.3 (hardness and hp per inch against steel's 10/30),
# §1.4 and §5.2, and the weapon blanch (Ultimate Equipment 103). A canonical row is
# (gear, type, target, number, trigger, armour weight); the comparison is a set, so a book
# effect added, dropped or changed in either place fails here.

def _canon(gear: str, e: dict) -> tuple:
    number = e.get("amount", e.get("dc", e.get("dice")))
    target = e.get("target") or e.get("damage_type")
    if e.get("type") == "damage":
        target = e.get("damage_type")
    weight = ((e.get("when") or {}).get("armour") or {}).get("weight")
    tail = e.get("recipient") if e.get("recipient") in ("self", "attacker") else None
    return (gear, e["type"], target, None if number is None else str(number),
            e.get("trigger"), weight, tail)


def _r(gear, etype, target, number=None, trigger=None, weight=None, who=None):
    return (gear, etype, target, None if number is None else str(number), trigger, weight,
            who)


BOOK = {
    "mithral": {
        _r("weapon", "strikes_as", "silver"), _r("weapon", "gear_mod", "weight_pct", -50),
        _r("weapon", "gear_mod", "hardness", 5),
        _r("armour", "gear_mod", "acp", 3), _r("armour", "gear_mod", "max_dex", 2),
        _r("armour", "gear_mod", "asf", -10), _r("armour", "gear_mod", "weight_pct", -50),
        _r("armour", "gear_mod", "category", -1), _r("armour", "gear_mod", "hardness", 5)},
    "adamantine": {
        _r("weapon", "strikes_as", "adamantine"), _r("weapon", "gear_mod", "hardness", 10),
        _r("weapon", "gear_mod", "hp_per_inch", 10),
        _r("armour", "damage_reduction", None, 1, weight="light"),
        _r("armour", "damage_reduction", None, 2, weight="medium"),
        _r("armour", "damage_reduction", None, 3, weight="heavy"),
        _r("armour", "gear_mod", "hardness", 10), _r("armour", "gear_mod", "hp_per_inch", 10)},
    "cold-iron": {_r("weapon", "strikes_as", "cold_iron")},
    "nexavaran-steel": {_r("weapon", "strikes_as", "cold_iron")},
    "cold-iron-blanching": {_r("weapon", "strikes_as", "cold_iron")},
    # The other weapon blanch (Ultimate Equipment): full damage to incorporeal creatures.
    # A house +2 against undead stood in for it until `strikes_as: ghost_touch` existed
    # (contracts §12 item 5, lane H).
    "ghost-salt-blanching": {_r("weapon", "strikes_as", "ghost_touch")},
    "alchemical-silver-plating": {
        _r("weapon", "strikes_as", "silver"), _r("weapon", "combat_mod", "damage", -1)},
    "singing-steel": {
        _r("weapon", "strikes_as", "silver"), _r("weapon", "combat_mod", "damage", -1),
        _r("weapon", "gear_mod", "hp_per_inch", -10),
        _r("armour", "gear_mod", "category", -1), _r("armour", "gear_mod", "asf", -5),
        _r("armour", "gear_mod", "max_dex", 1), _r("armour", "gear_mod", "acp", 1),
        _r("armour", "gear_mod", "hp_per_inch", -10)},
    "gold": {
        _r("weapon", "combat_mod", "damage", -2), _r("weapon", "gear_mod", "hardness", -5),
        _r("weapon", "gear_mod", "weight_pct", 50),
        _r("armour", "combat_mod", "ac", -2), _r("armour", "gear_mod", "acp", -2),
        _r("armour", "gear_mod", "hardness", -5), _r("armour", "gear_mod", "weight_pct", 50)},
    "copper": {_r("armour", "gear_mod", "hardness", -1)},
    "bronze": {_r("armour", "gear_mod", "hardness", -1)},
    "viridium": {
        _r("weapon", "save_gate", "fort", 12, "hit"),
        _r("weapon", "save_gate", "fort", 13, "crit"),
        _r("weapon", "save_gate", "fort", 12, "carried", who="self"),
        _r("weapon", "gear_mod", "hardness", -5)},
    "abysium": {
        _r("weapon", "apply_condition", "sickened", trigger="carried"),
        _r("armour", "apply_condition", "sickened", trigger="carried")},
    "horacalcum": {
        _r("weapon", "combat_mod", "attack", 1), _r("weapon", "gear_mod", "hardness", 5),
        _r("armour", "combat_mod", "initiative", 1, weight="light"),
        _r("armour", "combat_mod", "initiative", 2, weight="medium"),
        _r("armour", "combat_mod", "initiative", 3, weight="heavy"),
        _r("armour", "gear_mod", "hardness", 5)},
    "inubrix": {
        _r("weapon", "combat_mod", "attack", -2), _r("weapon", "combat_mod", "damage", -2),
        _r("weapon", "gear_mod", "hardness", -5), _r("weapon", "gear_mod", "hp_per_inch", -20)},
    "noqual": {
        _r("weapon", "gear_mod", "weight_pct", -50),
        _r("weapon", "combat_mod", "damage", 1), _r("weapon", "combat_mod", "damage", 1),
        _r("armour", "gear_mod", "asf", 20), _r("armour", "save_mod", "fort", 2),
        _r("armour", "save_mod", "ref", 2), _r("armour", "save_mod", "will", 2),
        _r("armour", "gear_mod", "weight_pct", -50), _r("armour", "gear_mod", "category", -1),
        _r("armour", "gear_mod", "max_dex", 2), _r("armour", "gear_mod", "acp", 3)},
    "siccatite": {
        _r("weapon", "damage", "fire", 1, "hit"),
        _r("weapon", "damage", "fire", 1, "each_round", who="self"),
        _r("armour", "damage", "fire", 1, "each_round", who="self"),
        _r("armour", "damage", "fire", 1, "when_grappled", who="attacker"),
        _r("armour", "resistance", "cold", 5)},
    "elysian-bronze": {
        _r("weapon", "combat_mod", "damage", 1), _r("weapon", "combat_mod", "attack", 1, "hit", who="self"),
        _r("armour", "damage_reduction", None, 1, weight="light"),
        _r("armour", "damage_reduction", None, 2, weight="medium"),
        _r("armour", "damage_reduction", None, 3, weight="heavy")},
    "living-steel": {
        _r("weapon", "gear_mod", "hardness", 5), _r("weapon", "gear_mod", "hp_per_inch", 5),
        _r("armour", "gear_mod", "hardness", 5), _r("armour", "gear_mod", "hp_per_inch", 5)},
    "fire-forged-steel": {_r("armour", "resistance", "fire", 2)},
    "frost-forged-steel": {_r("armour", "resistance", "cold", 2)},
    "darkwood-haft": {_r("weapon", "gear_mod", "weight_pct", -50)},
}


def test_book_effects_equal_the_prior_art_table(forge):
    """Every book material's book effects, as a set, against the sweep's table; and no
    book effect anywhere else. The eleven catalogue errors were each a book number
    written from memory; this is the check that a printed rule is the printed rule."""
    by_id = _by_id(forge)
    wrong = {}
    for mid, want in BOOK.items():
        d = by_id[mid]
        have = {_canon(g, e) for g in materials.GEARS for e in d[g] if e.get("book")}
        if have != want:
            wrong[mid] = {"missing": sorted(map(str, want - have)),
                          "unexpected": sorted(map(str, have - want))}
    assert not wrong, json.dumps(wrong, indent=1)
    stray = [d["id"] for d in forge if d["id"] not in BOOK
             and any(e.get("book") for g in materials.GEARS for e in d[g])]
    assert not stray, stray
    # The same set in a list: a duplicated book row would hide inside a set comparison.
    for mid in BOOK:
        rows = [_canon(g, e) for g in materials.GEARS for e in by_id[mid][g] if e.get("book")]
        dupes = {r for r in rows if rows.count(r) > 1}
        assert not dupes - {_r("weapon", "combat_mod", "damage", 1)}, (mid, dupes)


def test_the_eleven_catalogue_errors_are_gone(forge):
    """Prior-art §5.2's table, one assertion per error, so a regression names itself."""
    d = _by_id(forge)
    # Mithral: lighter for movement, never proficiency; spell failure; strikes as silver.
    assert "proficiency" not in json.dumps(d["mithral"]["armour"]).replace(
        "never for proficiency", "")
    # Abysium: no save at all; the sickness is carried.
    assert not any(e["type"] == "save_gate" for e in d["abysium"]["weapon"])
    # Viridium: leprosy at DC 12, not DC 14 sickened.
    assert not any(e.get("dc") == 14 for e in d["viridium"]["weapon"])
    # Horacalcum: initiative by armour weight, attack on the weapon.
    assert not any(e.get("target") == "initiative" and e.get("book")
                   for e in d["horacalcum"]["weapon"])
    # Singing steel: the invented +2 Perform is gone as a book number.
    assert not any(e.get("target") == "perform" and e.get("book")
                   for g in materials.GEARS for e in d["singing-steel"][g])
    # Inubrix and noqual keep their drawbacks.
    assert any(materials.is_negative(e) and e.get("book") for e in d["inubrix"]["weapon"])
    assert any(e.get("target") == "asf" and e.get("amount") == 20
               for e in d["noqual"]["armour"])
    assert d["noqual"]["enchant_surcharge_gp"] == 5000
    # Fire-forged armour resists always, not "once it has drunk a round of flame".
    assert {"type": "resistance", "target": "fire", "amount": 2, "book": True} in \
        d["fire-forged-steel"]["armour"]
    # Alchemical silver: not on adamantine, cold iron or mithral.
    assert set(d["alchemical-silver-plating"]["not_on"]) == {"adamantine", "cold-iron",
                                                             "mithral"}


def test_the_worked_example_reads_true_from_the_real_data():
    """Plan §6.4's worked example (+3 damage, -1 attack, +5 hardness on a Fine longsword
    with a strengthened iron head, ash haft and brass guard) is lane B's test. It only
    stays true if these three materials carry exactly the numbers the example assumes, so
    a rebalance that breaks the example has to break this test first."""
    def rows(mid):
        out = {}
        for e in materials.get(mid)["weapon"]:
            if e["type"] in ("combat_mod", "gear_mod") and e["target"] in (
                    "damage", "attack", "hardness"):
                out[e["target"]] = out.get(e["target"], 0) + e["amount"]
        return out

    assert rows("iron") == {"damage": 2, "attack": -2, "hardness": 2}
    assert rows("ash-haft") == {"attack": 2}
    assert rows("brass-guard") == {"hardness": 2}


# --- the validator refuses each violation, with the fix named ---------------------------------

def _iron():
    return copy.deepcopy(materials.get("iron"))


def _mutated(mutate):
    doc = _iron()
    mutate(doc)
    return materials.validate(doc)


CASES = [
    ("two weapon effects", lambda d: d["weapon"].pop(), "needs at least 3"),
    ("no drawback", lambda d: d["weapon"].__setitem__(1, {
        "type": "combat_mod", "target": "cmd", "amount": 2, "bonus_type": "material"}),
     "no drawback"),
    ("narrative", lambda d: d["weapon"].append({"type": "narrative", "target": "Gleams"}),
     "narrative prose"),
    ("over the ceiling", lambda d: d["weapon"][0].__setitem__("amount", 3), "at most ±2"),
    ("under the base", lambda d: d["weapon"][0].__setitem__("amount", 1),
     "start at ±2"),
    ("wrong bonus type", lambda d: d["weapon"][0].__setitem__("bonus_type", "untyped"),
     "\"material\" bonus"),
    ("no working trait", lambda d: d.__setitem__("working", []), "no working trait"),
    ("bad working trait", lambda d: d["working"].append(
        {"type": "working", "trait": "shiny"}), "shiny"),
    ("effects on an unnamed piece", lambda d: d["pieces"].__setitem__("armour", []),
     "fills no armour piece"),
    ("book unmarked", lambda d: d["weapon"][0].__setitem__("book", True),
     "not marked \"book\": true"),
    ("not a slot", lambda d: d["pieces"]["weapon"].append("blade"), "is not a slot"),
    ("bad gear target", lambda d: d["weapon"][2].__setitem__("target", "sharpness"),
     "sharpness"),
    ("unknown parent", lambda d: d.__setitem__("material", "unobtainium"),
     "no material has that id"),
    ("not executable", lambda d: d["weapon"].append({"type": "sense", "target": "darkvision"}),
     "not executable"),
]


@pytest.mark.parametrize("what,mutate,fix", CASES, ids=[c[0] for c in CASES])
def test_validate_refuses_each_violation_with_the_fix_named(what, mutate, fix):
    """Herbalism's lesson and the third law: validators refuse documents with the fix
    named. A bare "invalid" teaches nobody what to change."""
    problems = _mutated(mutate)
    assert any(fix in p for p in problems), problems


def test_the_unmutated_document_is_clean():
    """The control for the cases above: iron itself passes, so each refusal is the
    mutation's and not a standing failure."""
    assert materials.validate(_iron()) == []


def _forge_doc(**fields):
    base = {"id": "test-thing", "name": "Test Thing", "tier": "common",
            "catalogue": materials.FORGE_CATALOGUE}
    base.update(fields)
    return materials.normalise(base, materials.FORGE_CATALOGUE)


def test_a_quenchant_without_a_mark_is_refused():
    doc = _forge_doc(kind="quenchant", working=[{"type": "working", "trait": "forgiving"}] * 3)
    assert any("no quench mark" in p for p in materials.validate(doc))


def test_a_fuel_with_item_effects_is_refused():
    doc = _forge_doc(kind="fuel", working=[{"type": "working", "trait": "clean_heat"}] * 3,
                     weapon=[{"type": "combat_mod", "target": "damage", "amount": 2,
                              "bonus_type": "material"}])
    assert any("working traits only" in p for p in materials.validate(doc))


def test_an_ore_that_smelts_to_nothing_is_refused():
    doc = _forge_doc(kind="ore", working=[{"type": "working", "trait": "slaggy"}] * 3)
    assert any("smelts to nothing" in p for p in materials.validate(doc))


def test_a_treatment_that_finishes_nothing_is_refused():
    doc = _forge_doc(kind="treatment", working=[{"type": "working", "trait": "pure"}] * 2,
                     weapon=[{"type": "strikes_as", "target": "silver"}])
    problems = materials.validate(doc)
    assert any("finishes nothing" in p for p in problems), problems


def test_too_few_properties_is_refused():
    doc = _forge_doc(kind="flux", working=[{"type": "working", "trait": "cleans_slag"}])
    assert any("discoverable propert" in p for p in materials.validate(doc))


def test_a_carried_sickness_counts_as_the_drawback():
    """Abysium's only drawback is its carrier effect (plan §5.4). A sign-only check would
    call its weapon list drawback-free and demand an invented penalty on top."""
    carried = {"type": "apply_condition", "target": "sickened", "trigger": "carried"}
    on_hit = {"type": "apply_condition", "target": "sickened", "trigger": "hit"}
    assert materials.is_negative(carried)
    assert not materials.is_negative(on_hit)
    assert materials.is_negative({"type": "gear_mod", "target": "acp", "amount": -2})
    assert not materials.is_negative({"type": "gear_mod", "target": "asf", "amount": -10})


# --- the review the owner reads ---------------------------------------------------------------

def test_the_owner_review_is_current():
    """docs/blacksmithing-review.md is generated from the data. A hand-kept table would
    drift from the numbers the game reads, and the owner would be ruling on numbers that
    no longer exist."""
    path = Path(settings.BASE_DIR) / "tools" / "forge_review.py"
    spec = importlib.util.spec_from_file_location("_forge_review", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    current = mod.OUT.read_text(encoding="utf-8")
    assert current == mod.render(), "run python tools/forge_review.py"
