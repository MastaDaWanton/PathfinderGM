"""The leatherworker's materials: one door, typed effects, the book's numbers, nothing inert.

Measured before the leather data pass (docs/leatherworking-revamp-plan.md §14.1, inventory
§2): 127 materials, 96 of their 171 effect specs `narrative`, 52 materials carrying only
prose and 14 nothing, no material with three traits of any kind, and no hide with a drawback
in executable form. `materials.validate` returned early for every leather document, so
nothing judged them; the hides' effects sat in a flat legacy list the forge's build never
reads, so a hide in a body slot did nothing; and the tannins', waxes' and threads' prose was
laid on every finished item (a boar-hide suit listed "The standard tanning agent for common
and uncommon hides" as one of its effects). Eleven dragonhides gave the WEARER resistance 5
as if it were the book's rule, which says the opposite.

These pin plan §23.1 lane D and contracts §3: every hide has >= 3 armour modifiers with a
drawback and no narrative; only grip-capable hides carry weapon lists; every book material's
book effects equal the prior-art table (a set comparison); dragonhide gives the wearer no
book resistance; no consumable's prose reaches an item; and `validate` refuses each
violation with the fix named.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import re
from pathlib import Path

import pytest
from django.conf import settings

from rules import effectspec, forge_items, materials, pricing, tables

FILE = Path(settings.BASE_DIR) / "content" / "materials" / "leatherworker-materials.json"


@pytest.fixture(scope="module")
def leather() -> dict[str, dict]:
    materials.refresh()
    return {k: d for k, d in materials.all().items()
            if d["catalogue"] == materials.LEATHER_CATALOGUE}


def _raw() -> dict:
    return json.loads(FILE.read_text(encoding="utf-8"))


# --- the door ---------------------------------------------------------------------------------

def test_the_door_judges_every_leather_document(leather):
    """`validate` returned early for all 127 leather documents (rules/materials.py:405 on
    master): the shelf could hold anything. Now every one is judged by the leather rules and
    the shipped catalogue passes them."""
    assert len(leather) >= 127
    assert all(materials.is_judged(d) and materials.is_leather(d) for d in leather.values())
    problems = [p for d in leather.values() for p in materials.validate(d)]
    assert not problems, "\n".join(problems)


def test_ids_and_names_did_not_change(leather):
    """The old chain bench, saved stock and the counter key on ids (contracts §3: "ids and
    names do not change"). Every id the catalogue shipped before the pass is still here
    under its old name, including the 23 lane G's counter sells by id."""
    before = {
        "deer-hide": "Deer Hide", "winter-wolf-pelt": "Winter Wolf Pelt",
        "red-dragonhide": "Red Dragonhide", "electric-eel-skin": "Electric Eel Skin",
        "bulette-plate": "Bulette Plate", "curing-salt": "Curing Salt",
        "tawing-alum": "Tawing Alum", "brain-paste": "Brain Tan Paste", "oak-bark": "Oak Bark",
        "sumac-leaf": "Sumac Leaf", "hemlock-bark": "Hemlock Bark",
        "willow-bark": "Willow Bark", "neatsfoot-oil": "Neatsfoot Oil",
        "currier-tallow": "Currier's Tallow", "fish-oil": "Fish Oil",
        "thread-wax": "Thread Wax", "seam-pitch": "Seam Pitch",
        "linen-thread": "Linen Thread", "sinew-thread": "Sinew Thread",
        "gut-cord": "Gut Cord", "horsehair-cord": "Horsehair Cord",
        "waxed-flax": "Waxed Heavy Flax", "steel-studs": "Steel Studs",
    }
    for mid, name in before.items():
        assert mid in leather, mid
        assert leather[mid]["name"].lower() == name.lower(), (mid, leather[mid]["name"])


def test_an_old_leather_entry_loads_with_every_field_defaulted():
    """Every field defaults (the herbprep rule): a homebrew hide written before the pass
    loads, gets its kind's colour, its shelves and the form a counter sells it in, and the
    validator says what it lacks rather than the bench crashing."""
    doc = materials.normalise({"id": "Glass-Cat-Hide", "name": "Glass Cat Hide",
                               "kind": "hide"}, "")
    assert materials.is_leather(doc) and not materials.is_forge(doc)
    assert doc["pieces"] == {"weapon": [], "armour": [], "shield": [], "worn": []}
    assert doc["shield"] == [] and doc["mark"] is None and doc["allowed_bases"] == []
    assert doc["surface"] == "smooth" and doc["color"] == materials.KIND_COLOUR["hide"]
    assert not doc["always_masterwork"] and not doc["druid_permitted"]
    assert doc["tannage"] is None and doc["sold_as"] == "leather"
    assert doc["forms"][0] == "green" and "leather" in doc["forms"]
    problems = materials.validate(doc)
    assert any("fills no armour piece" in p for p in problems)
    assert any("no working trait" in p for p in problems)


def test_grip_capable_and_salt_are_read_from_the_document(leather):
    """Contracts §3's two questions. Salt is asked by id and field, never by a word in a
    name: `herbprep.has_salt` matched name fragments (plan §6), the shape law 1 refuses."""
    assert materials.grip_capable(leather["sharkskin"])
    assert not materials.grip_capable(leather["winter-wolf-pelt"])
    assert materials.is_salt("curing-salt") and materials.is_salt(leather["curing-salt"])
    assert not materials.is_salt("mordant-salts")        # a salt by name, not curing salt
    assert materials.is_salt({"id": "sea-salt-sack", "salt": True})


# --- the hides ----------------------------------------------------------------------------------

def test_no_leather_effect_is_narrative(leather):
    """96 of 171 specs were narrative: prose that looked authored and did nothing. None is
    left in any list a bench reads, nor in the legacy `effects` the old chain bench reads,
    nor in the held marks."""
    found = []
    for d in leather.values():
        for g in materials.EFFECT_GEARS:
            for spec in d[g]:
                for nested in materials._walk(spec):
                    if nested.get("type") == "narrative":
                        found.append(f"{d['id']} {g}")
    raw = _raw()
    for m in raw["materials"]:
        found += [f"{m['id']} effects" for e in m.get("effects") or []
                  if e.get("type") == "narrative"]
    found += [f"marks_on_hold {k}" for k, v in raw["marks_on_hold"].items()
              if isinstance(v, dict) and v.get("type") == "narrative"]
    assert not found, found


def test_every_hide_has_three_armour_modifiers_with_a_drawback(leather):
    """The owner's rule (Q3.1), the forge's fences: 3 armour modifiers on every hide, at
    least one negative. Before the pass no material had three traits of any kind and no hide
    carried a drawback in executable form ("check penalty one worse" was prose on seven)."""
    short, soft = [], []
    for d in leather.values():
        if d["kind"] != "hide":
            continue
        if len(d["armour"]) < 3:
            short.append(d["id"])
        if not any(materials.is_negative(e) for e in d["armour"]):
            soft.append(d["id"])
    assert not short and not soft, (short, soft)


GRIP_CAPABLE = {
    # Plan §14.3: the skins that were real grip materials or are thin and tough, every
    # dragonhide, and plain leather (cowhide).
    "sharkskin", "ray-skin", "viper-skin", "crocodile-hide", "monitor-lizard-hide",
    "frilled-lizard-hide", "basilisk-hide", "wyvern-hide", "behir-hide", "cowhide",
    "red-dragonhide", "gold-dragonhide", "brass-dragonhide", "white-dragonhide",
    "silver-dragonhide", "blue-dragonhide", "bronze-dragonhide", "black-dragonhide",
    "copper-dragonhide", "green-dragonhide", "umbral-dragonhide",
}


def test_only_grip_capable_hides_carry_weapon_lists(leather):
    """Q3.1: "3 weapon modifiers only on grip-capable hides". A weapon list on a bear pelt
    is about 65 lists nobody wraps a hilt in; the set is plan §14.3's, compared whole."""
    with_weapon = {k for k, d in leather.items() if d["weapon"]}
    capable = {k for k, d in leather.items() if materials.grip_capable(d)}
    assert with_weapon == capable == GRIP_CAPABLE
    for mid in capable:
        d = leather[mid]
        assert len(d["weapon"]) >= 3 and any(materials.is_negative(e) for e in d["weapon"])
        assert d["pieces"]["weapon"] == ["haft"]
        assert "grip" in d["forms"]


def test_same_tier_hides_are_not_reskins(leather):
    """Materials must feel different: within one tier no two hides carry the same armour
    and grip lists. Before the pass ten dragonhides differed only in a line of prose."""
    seen: dict[tuple, str] = {}
    for d in leather.values():
        if d["kind"] != "hide":
            continue
        key = (d["tier"], json.dumps([d["armour"], d["weapon"]], sort_keys=True))
        assert key not in seen, f"{d['id']} and {seen[key]} are the same {d['tier']} hide"
        seen[key] = d["id"]


def test_a_hides_ac_is_material_and_folds_into_the_suit(leather):
    """Every hide AC was typed `armour` (tests/test_aggregator.py:321 pinned it) and so
    never stacked with the suit's own armour bonus: measured, a bulette suit at +5 came out
    as leather AC 2, and 13 hide specs did nothing on any suit (inventory §0.2). Typed
    `material`, it folds into the armour bonus through the forge's build."""
    for d in leather.values():
        for e in d["armour"]:
            if e.get("type") == "combat_mod" and e.get("target") == "ac" \
                    and not e.get("book"):
                assert e.get("bonus_type") == "material", d["id"]
    rec = {"id": "probe-boar-leather", "gear": "armour", "base": "leather",
           "quality_index": 1, "pieces": {"body": {"material": "boar-hide"}},
           "smith": {"level": 1, "perks": {}}}
    row = forge_items.armour_row(tables.ARMOUR["leather"], forge_items.build(rec))
    assert row["ac"] == tables.ARMOUR["leather"]["ac"] + 2


# --- the book --------------------------------------------------------------------------------
#
# Stated here independently of tools/leather_data_pass.py, by hand from
# docs/leatherworking-prior-art.md §1.3 (Core and Ultimate Equipment, confirmed in its critic
# pass §7.1). Hardness and hp per inch are deltas on leather's 2 and 5 (CRB, Table 7-12). A
# canonical row is (type, target, number, bonus type, applies_to); compared as sets, so a
# book effect added, dropped or changed in either place fails here.

def _canon(e: dict) -> tuple:
    return (e["type"], e.get("target"), e.get("amount"), e.get("bonus_type"),
            e.get("applies_to"))


def _dragon(energy: str) -> set:
    return {("object_immunity", energy, None, None, None),
            ("gear_mod", "enchant_cost_pct", -25, None, "energy_resistance"),
            ("gear_mod", "hardness", 8, None, None),
            ("gear_mod", "hp_per_inch", 5, None, None)}


BOOK = {
    **{f"{c}-dragonhide": _dragon(e) for c, e in (
        ("red", "fire"), ("gold", "fire"), ("brass", "fire"), ("white", "cold"),
        ("silver", "cold"), ("blue", "electricity"), ("bronze", "electricity"),
        ("black", "acid"), ("copper", "acid"), ("green", "acid"), ("umbral", "cold"))},
    "electric-eel-skin": {("gear_mod", "acp", 1, None, None),
                          ("gear_mod", "max_dex", 1, None, None),
                          ("resistance", "electricity", 2, None, None)},
    "angelskin": {("gear_mod", "hardness", 3, None, None)},
    "darkleaf-cloth": {("gear_mod", "asf", -10, None, None),
                       ("gear_mod", "max_dex", 2, None, None),
                       ("gear_mod", "acp", 3, None, None),
                       ("gear_mod", "weight_pct", -50, None, None),
                       ("gear_mod", "hardness", 8, None, None),
                       ("gear_mod", "hp_per_inch", 15, None, None)},
    "griffon-mane": {("skill_mod", "fly", 2, "competence", None)},
    "bone-studs": {("combat_mod", "ac", -1, "material", None),
                   ("gear_mod", "acp", 1, None, None),
                   ("gear_mod", "hardness", 3, None, None)},
    "bulette-plate": {("as_base", "studded leather", None, None, None)},
}
ALWAYS_MASTERWORK = {f"{c}-dragonhide" for c in (
    "red", "gold", "brass", "white", "silver", "blue", "bronze", "black", "copper", "green",
    "umbral")} | {"electric-eel-skin", "angelskin", "darkleaf-cloth"}
ALLOWED = {
    "electric-eel-skin": {"leather", "hide armour", "studded leather"},
    "angelskin": {"leather", "hide armour", "studded leather"},
    "darkleaf-cloth": {"padded", "leather", "studded leather", "hide armour"},
    "griffon-mane": {"padded", "quilted cloth"},
}


def test_every_book_materials_effects_match_the_prior_art_table(leather):
    """Plan §14.5, "the book fixes (do these first)": every contradiction in the questions
    doc's book-versus-catalogue list corrected to the printed rule, compared as a set, and no
    book effect anywhere else. Before: eel hide lacked its ACP, max Dex, masterwork and suit
    restriction; angelskin carried an invented Will +3 / AC +2 / Diplomacy -3; bulette an
    invented +3 armour-typed AC; darkleaf cloth, griffon mane and bone did not exist."""
    wrong = {}
    for mid, want in BOOK.items():
        d = leather[mid]
        have = {_canon(e) for g in materials.EFFECT_GEARS for e in d[g] if e.get("book")}
        if have != want:
            wrong[mid] = (sorted(have - want, key=str), sorted(want - have, key=str))
        assert d["book"], mid
    assert not wrong, wrong
    # A fitting that is a form of a forge metal carries the metal's own book lines
    # (mithral's, adamantine's), which the forge's test holds to the forge's table.
    elsewhere = [k for k, d in leather.items() if k not in BOOK and d["material"] == k
                 and any(e.get("book") for g in materials.EFFECT_GEARS for e in d[g])]
    assert not elsewhere, elsewhere
    assert {k for k, d in leather.items() if d["always_masterwork"]} == ALWAYS_MASTERWORK
    assert {k: set(d["allowed_bases"]) for k, d in leather.items()
            if d["allowed_bases"]} == ALLOWED
    # The book clauses no effect can say yet are kept as words, not dropped.
    assert any("evil aura" in n for n in leather["angelskin"]["not_yet"])
    assert any("Flight" in n for n in leather["griffon-mane"]["not_yet"])


def test_dragonhide_gives_the_wearer_no_book_resistance(leather):
    """The book: "if the dragon was immune to an energy type, the armor is also immune,
    although this does not confer any protection to the wearer" (prior art §1.3, verbatim
    in the critic pass). Before the pass all 11 dragonhides gave the WEARER resistance 5 as
    their book effect. Now the immunity is the armour's (`object_immunity`), the wearer's
    resistance is a house 2 inside the legendary ceiling, and the book's other three lines
    hold: always masterwork, a druid may wear it, its scales are a form."""
    dragons = [d for k, d in leather.items() if k.endswith("-dragonhide")]
    assert len(dragons) == 11
    for d in dragons:
        book = [e for e in d["armour"] if e.get("book")]
        assert not any(e["type"] in ("resistance", "immunity") for e in book), d["id"]
        immune = {e["target"] for e in book if e["type"] == "object_immunity"}
        wearer = [e for e in d["armour"] if e["type"] == "resistance"]
        assert len(immune) == 1 and [e["target"] for e in wearer] == list(immune), d["id"]
        assert all(e["amount"] <= materials.TIER_CEILING["legendary"] for e in wearer)
        assert d["always_masterwork"] and d["druid_permitted"], d["id"]
        assert "scales" in d["forms"] and "thick" in {w["trait"] for w in d["working"]}
    # The old legacy list (what the chain bench reads) no longer says 5 either.
    raw = {m["id"]: m for m in _raw()["materials"]}
    assert all(e.get("amount") != 5 for d in dragons for e in raw[d["id"]]["effects"])


def test_reduced_dr_follows_the_owners_rule(leather):
    """The owner, 2026-10-08: "add the reduced DR" — a creature's DR N/x gives DR max(1,
    N/5)/x on a rare-and-up hide. Before the pass dire boar, cave bear and purple worm
    carried DR their creatures do not have in the book, and tarrasque's was DR 3/— with no
    bypass. Each DR now is the printed creature DR, reduced, with its bypass."""
    printed = {"salamander-hide": (10, "magic"), "noble-salamander-hide": (15, "magic"),
               "phoenix-feather-hide": (15, "evil"), "tarrasque-plate": (15, "epic")}
    have = {}
    for k, d in leather.items():
        if d["kind"] != "hide":
            continue          # adamantine buckles carry adamantine's own printed DR
        for e in d["armour"]:
            if e["type"] == "damage_reduction":
                have[k] = (e["amount"], e["bypass"])
    assert have == {k: (max(1, n // 5), by) for k, (n, by) in printed.items()}
    for k in have:
        assert leather[k]["tier"] in ("rare", "exotic", "legendary"), k


# --- the consumables ----------------------------------------------------------------------------

def test_no_consumables_prose_reaches_an_item(leather):
    """Measured before the pass: a boar-hide suit listed "The standard tanning agent for
    common and uncommon hides" as an effect, because the old chain bench gathered every
    material's flat `effects` on the bench, tannins and threads included (inventory §0.6).
    No consumable now carries an item effect, a piece or a mark, and its legacy list is
    empty; and a boar hide suit built through the forge's build names no consumable."""
    raw = {m["id"]: m for m in _raw()["materials"]}
    for k, d in leather.items():
        if d["kind"] not in materials.LEATHER_CONSUMABLES:
            continue
        assert not any(d[g] for g in materials.EFFECT_GEARS), k
        assert not any(d["pieces"][g] for g in materials.GEARS), k
        assert d["mark"] is None and raw[k]["effects"] == [], k
        assert d["working"], k
    rec = {"id": "probe-boar-suit", "gear": "armour", "base": "hide armour",
           "quality_index": 2,
           "pieces": {"body": {"material": "boar-hide", "tannage": "oak-bark"},
                      "fastenings": {"material": "deer-hide", "form": "lacing"},
                      "lining": {"material": "wolf-pelt"}},
           "marks": ["neatsfoot-oil", "oak-bark"],
           "smith": {"level": 1, "perks": {}}}
    b = forge_items.build(rec)
    text = json.dumps(b)
    consumables = [k for k, d in leather.items() if d["kind"] in materials.LEATHER_CONSUMABLES]
    assert "tanning agent" not in text
    assert not any(f'"{k}"' in text for k in consumables)
    assert not b["problems"]


def test_every_tannin_says_how_it_tans(leather):
    """Plan §8.1: the tannage decides the wait and whether the leather can be hardened, so
    it is a field and not prose. Before the pass every tannin's job was one narrative line;
    brain paste and tawing alum, the brain and alum tannins, were filed as treatments."""
    tannins = {k: d for k, d in leather.items() if d["kind"] == "tannin"}
    assert {d["tannage"] for d in tannins.values()} == set(materials.TANNAGES)
    assert tannins["brain-paste"]["tannage"] == "brain"
    assert tannins["tawing-alum"]["tannage"] == "alum"
    assert all(d["tannage"] is None for d in leather.values() if d["kind"] != "tannin")
    # Hemlock's "halves tanning time" and mangrove's "salt-proof" were prose; now traits.
    assert "fast_tan" in {w["trait"] for w in tannins["hemlock-bark"]["working"]}
    assert "salt_proof" in {w["trait"] for w in tannins["mangrove-bark"]["working"]}


def test_marks_are_held_in_one_block_nothing_reads(leather):
    """The owner held marks on 2026-10-08 ("explain before deciding"). The proposed marks
    live in the catalogue's `marks_on_hold` block, every row a valid leather effect so
    enabling them is safe, no shipped document carries one, the validator refuses one while
    held, and no reader in the app names the block (a grep, so a later reader that starts
    applying them fails here first)."""
    raw = _raw()
    held = {k: v for k, v in raw["marks_on_hold"].items() if not k.startswith("_")}
    assert held and all(k in leather for k in held)
    for k, mark in held.items():
        assert effectspec.leather_effect_problems(mark, k) == [], k
        assert leather[k]["kind"] in materials.LEATHER_CONSUMABLES
    assert materials.MARKS_HELD
    assert not any(d["mark"] for d in leather.values())
    doc = copy.deepcopy(leather["salamander-oil"])
    doc["mark"] = held["salamander-oil"]
    assert any("marks are on hold" in p for p in materials.validate(doc))
    # A reader indexes the block by its key; a comment or a message naming it is not one.
    reads = re.compile(r"""(\[\s*|get\(\s*)["']marks_on_hold["']""")
    root = Path(settings.BASE_DIR)
    readers = [p for folder in ("rules", "play", "gm", "pathfindergm")
               for p in (root / folder).rglob("*.py")
               if reads.search(p.read_text(encoding="utf-8", errors="ignore"))]
    assert readers == [], readers


# --- the forge's side -----------------------------------------------------------------------------

def test_the_forges_leather_pieces_are_forms_of_their_hides():
    """Plan §4.4 (the owner, Q7.4): the forge's four leather pieces become forms of the
    leatherworker's materials, carrying their parent's numbers. Before, sharkskin, plain
    leather and angelskin had no document at all and the binding's numbers were invented."""
    pairs = {"leather-grip": ("cowhide", ("weapon", "armour")),
             "sharkskin-grip": ("sharkskin", ("weapon",)),
             "dragonhide-grip": ("red-dragonhide", ("weapon",)),
             "angelskin-binding": ("angelskin", ("armour",))}
    for form, (parent, gears) in pairs.items():
        doc, par = materials.get(form), materials.get(parent)
        assert materials.material_of(form) == parent
        for g in gears:
            assert doc[g] == par[g], (form, g)
        assert materials.validate(doc) == [], form
    # The dragonhide grip no longer gives its wielder the dragon's fire resistance.
    assert not any(e["type"] == "resistance" for e in materials.get("dragonhide-grip")["weapon"])


def test_leather_fittings_carry_their_metals_numbers(leather):
    """The eight leather fittings were forms of forge metals with no numbers of their own
    (inventory §2: flat, and only steel studs carried anything), so a stud in a fastening
    contributed nothing to a build. Each now carries its metal's armour list exactly."""
    linked = {k: d for k, d in leather.items()
              if d["kind"] == "fitting" and d["material"] != k}
    assert len(linked) == 8
    for k, d in linked.items():
        assert d["armour"] == materials.get(d["material"])["armour"], k
        assert d["pieces"]["armour"] == ["fastenings"]


FERROUS = {"iron", "wrought-iron", "cold-iron", "star-iron", "steel", "high-carbon-steel",
           "pattern-steel", "nexavaran-steel", "living-steel", "fire-forged-steel",
           "frost-forged-steel"}


def test_ferrous_marks_iron_and_its_alloys_only():
    """Rusting grasp eats "one nonmagical ferrous object" (plan §18.5) and the metal tag
    needs to know which metals are iron (contracts §6.2). Measured before: no material said.
    Not mithral, adamantine, inubrix ("ghost iron" is a skymetal) or wyrmsteel."""
    shelf = materials.all()
    assert {k for k, d in shelf.items() if d["ferrous"]} == FERROUS
    bad = copy.deepcopy(shelf["deer-hide"])
    bad["ferrous"] = True
    assert any("ferrous" in p for p in materials.validate(bad))


# --- prices and the counter ----------------------------------------------------------------------

COUNTER = ("curing-salt", "tawing-alum", "brain-paste", "oak-bark", "sumac-leaf",
           "hemlock-bark", "willow-bark", "neatsfoot-oil", "currier-tallow", "fish-oil",
           "thread-wax", "seam-pitch", "linen-thread", "sinew-thread", "gut-cord",
           "horsehair-cord", "waxed-flax")


def test_every_settlements_leatherworker_has_priced_supplies(leather):
    """The owner (open point 9): every settlement's leatherworker sells curing salt,
    tannins, oils, waxes, threads, dyes and common hides, and "unpriced means not sold".
    Measured before the pass: none of the 14 common hides and none of the 5 common dyes had
    a price, nor bog liquor or mangrove bark. Every one has a price the one rule accepts,
    and the ids lane G's counter sells by are the same ids."""
    for mid in COUNTER:
        assert leather[mid].get("price_gp"), mid
    for d in leather.values():
        common_hide = (d["kind"] == "hide" and d["tier"] == "common"
                       and not d["id"].startswith("generic-"))
        common_dye = d["kind"] == "dye" and d["tier"] == "common"
        if common_hide or common_dye:
            assert d.get("price_gp"), d["id"]
    for mid in ("bog-liquor", "mangrove-bark", "tara-pod"):
        assert leather[mid].get("price_gp"), mid
    raw = _raw()["materials"]
    assert pricing.material_price_problems(raw, "leatherworker-materials.json") == []


def test_a_bought_hide_is_sold_tanned(leather):
    """Plan §9: a counter sells leather, never a green hide ("cannot be bought or sold in
    most settlements", Harvest Parts). Every hide says which tanned form it is sold in, and
    that form is one of its shelves, so the bench can write the stock record."""
    for d in leather.values():
        if d["kind"] == "hide":
            assert d["sold_as"] in ("leather", "fur", "rawhide"), d["id"]
            assert d["sold_as"] in d["forms"], d["id"]
        else:
            assert d["sold_as"] == "", d["id"]
    assert leather["winter-wolf-pelt"]["sold_as"] == "fur"
    assert leather["deer-hide"]["sold_as"] == "leather"


def test_the_worked_example_reads_true_from_the_real_data(leather):
    """Plan §13.3's worked example (a Fine hide armour of laminated elk with deer lacing:
    AC 7, ACP -4, Survival +3, max Dex 5) is lane E's test, and it only stays true while
    elk and deer carry exactly the numbers it assumes; a rebalance that breaks the example
    has to break this test first."""
    def rows(mid):
        return {(e["type"], e["target"]): e["amount"] for e in leather[mid]["armour"]}
    assert rows("elk-hide") == {("combat_mod", "ac"): 2, ("gear_mod", "acp"): -2,
                                ("skill_mod", "survival"): 2}
    assert rows("deer-hide") == {("gear_mod", "acp"): 2, ("gear_mod", "max_dex"): 2,
                                 ("gear_mod", "hardness"): -2}


# --- the validator refuses each violation with the fix named ---------------------------------------

def _hide() -> dict:
    return copy.deepcopy(materials.get("winter-wolf-pelt"))


def _set(key, value):
    def go(d):
        d[key] = value
    return go


def _armour(i, spec):
    def go(d):
        d["armour"][i] = spec
    return go


CASES = [
    ("a narrative effect",
     _armour(1, {"type": "narrative", "target": "The fur stays frost-rimed"}),
     "never narrative"),
    ("two armour effects", lambda d: d["armour"].pop(), "needs at least 3"),
    ("no drawback", _armour(2, {"type": "gear_mod", "target": "acp", "amount": 2}),
     "no drawback"),
    ("a weapon list on a pelt", _set("weapon", [
        {"type": "combat_mod", "target": "attack", "amount": 2, "bonus_type": "material"}] * 3),
     "not grip-capable"),
    ("over the ceiling", _armour(1, {"type": "skill_mod", "target": "survival", "amount": 3,
                                     "bonus_type": "material"}), "at most ±2"),
    ("under the floor", _armour(1, {"type": "skill_mod", "target": "survival", "amount": 1,
                                    "bonus_type": "material"}), "start at ±2"),
    ("a circumstance bonus", _armour(1, {"type": "skill_mod", "target": "survival",
                                         "amount": 2, "bonus_type": "circumstance"}),
     "\"material\""),
    ("a forge trait", _set("working", [{"type": "working", "trait": "slaggy"}]),
     "not read at the leather bench"),
    ("masterwork without the book", _set("always_masterwork", True), "only the book"),
    ("a base no table has", _set("allowed_bases", ["chain leather"]), "no armour or shield"),
    ("a misspelt DR bypass", _armour(1, {"type": "damage_reduction", "amount": 2,
                                         "bypass": "sliver"}), "not something a blow"),
    ("a tannage on a hide", _set("tannage", "bark"), "not a tannin"),
    ("sold green", _set("sold_as", "green"), "sold as"),
    ("a bad surface", _set("surface", "velvet"), "surface"),
]


@pytest.mark.parametrize("what,mutate,fix", CASES, ids=[c[0] for c in CASES])
def test_validate_refuses_each_violation_with_the_fix_named(what, mutate, fix):
    doc = _hide()
    mutate(doc)
    problems = materials.validate(doc)
    assert any(fix in p for p in problems), (what, problems)


def test_the_unmutated_document_is_clean():
    assert materials.validate(_hide()) == []


def test_a_consumable_with_an_item_effect_or_no_tannage_is_refused():
    tannin = copy.deepcopy(materials.get("oak-bark"))
    tannin["armour"] = [{"type": "resistance", "target": "fire", "amount": 1}]
    assert any("working traits only" in p for p in materials.validate(tannin))
    tannin = copy.deepcopy(materials.get("oak-bark"))
    tannin["tannage"] = None
    assert any("Say how it tans" in p for p in materials.validate(tannin))


def test_a_form_whose_numbers_drift_from_its_metal_is_refused():
    studs = copy.deepcopy(materials.get("steel-studs"))
    studs["armour"][0] = dict(studs["armour"][0], amount=3)
    assert any("form of steel" in p for p in materials.validate(studs))


def test_the_owner_review_is_current():
    """docs/leatherworking-review.md is generated from the shipped file; a number changed
    without re-running the review would leave the owner reviewing a table the game does not
    read."""
    path = Path(settings.BASE_DIR) / "tools" / "leather_review.py"
    spec = importlib.util.spec_from_file_location("_leather_review", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    current = (Path(settings.BASE_DIR) / "docs" / "leatherworking-review.md").read_text(
        encoding="utf-8")
    assert current == mod.render(), "run python tools/leather_review.py"


def test_pending_bases_are_still_pending():
    """`materials.PENDING_BASES` lets a book restriction name the armour rows leather lane
    B adds (contracts §4.2). A row that has landed in the tables must leave that list, or
    it hides the day the table loses it again."""
    landed = [b for b in materials.PENDING_BASES
              if b in tables.ARMOUR or b in tables.SHIELDS]
    assert not landed, f"{landed} are in the tables now: drop them from PENDING_BASES"


def test_a_hides_size_and_green_clock_survive_the_reader():
    """Measured 2026-10-08 by lane E: `materials.get` dropped `size` and `fresh_hours`, so
    every reader but the bench saw a Large hide as one Medium unit with no clock."""
    from rules import materials

    doc = materials.get("deer-hide")
    assert doc["size"] == "medium" and doc["fresh_hours"] == 48
