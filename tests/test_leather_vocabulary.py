"""The leatherworker's effect vocabulary (docs/leatherworking-contracts.md §2, plan §23 row A).

Measured before any of it (plan §14.1, inventory §2): 127 leather materials, **96 of their 171
effect specs `narrative`**, not one working trait in the catalogue, and no word for the three
book rules the craft needs most — dragonhide's armour that does not burn ("does not confer any
protection to the wearer", while all 11 catalogue dragonhides gave the wearer resistance 5),
its 25% cheaper energy-resistance enchantments, and bulette leather's "same statistics as
studded leather". Every test here names the gap it closes.

The owner's answer 6 (2026-10-08, "add the reduced DR") is the last section: the vocabulary
already had `damage_reduction` with a bypass, and these tests pin that a leather document can
carry one and that it reaches the wearer's DR through the existing funnel.
"""
from __future__ import annotations

import json

import pytest

from rules import effectspec as es
from rules import forge_items
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from rules.tables import ARMOUR, ENERGY_DAMAGE


# --- object_immunity -------------------------------------------------------------------------

def test_object_immunity_validates_only_with_an_energy_target():
    """Dragonhide's book power is about the armour, and there was no way to say it: 11 of the
    old catalogue's dragonhides gave the WEARER resistance 5 instead (plan §15). The new type
    takes exactly the five energies, and refuses anything else with the five named — a suit
    immune to slashing or to poison is no book rule."""
    for energy in ENERGY_DAMAGE:
        assert es.validate({"type": "object_immunity", "target": energy}) == [], energy
    assert set(ENERGY_DAMAGE) == {"acid", "cold", "electricity", "fire", "sonic"}
    for wrong in ("slashing", "poison", "force", "negative"):
        refused = es.validate({"type": "object_immunity", "target": wrong})
        assert refused and all(e in refused[0] for e in ENERGY_DAMAGE), (wrong, refused)
    missing = es.validate({"type": "object_immunity"})
    assert missing and "energy type" in missing[0]


def test_object_immunity_reads_as_the_items_own_and_never_the_wearers():
    """"Immune to fire" on a suit's card reads as the wearer's — the exact misreading the 11
    dragonhides shipped. The line says the ITEM takes no damage, and is not the creature
    `immunity` type's line."""
    line = es.render({"type": "object_immunity", "target": "fire", "book": True})
    assert line == "The item itself takes no fire damage"
    assert line != es.render({"type": "immunity", "target": "fire"})
    _, etype = es.find("object_immunity")
    assert "wearer is not protected" in etype.blocked
    cat, _ = es.find("object_immunity")
    assert cat.id == "object"


# --- as_base ---------------------------------------------------------------------------------

def test_as_base_names_an_armour_table_row_and_nothing_else():
    """Bulette leather "has the same statistics as studded leather" (prior art §1.3), and the
    old catalogue wrote it as a +3 armour-typed AC on the hide. A name the table does not know
    is the defect that left bench suits "not built on any suit the rules know" (inventory
    §0.1), so the target is a `tables.ARMOUR` key from the dropdown, and 'none' is refused."""
    ok = {"type": "as_base", "target": "studded leather", "book": True}
    assert es.validate(ok) == []
    assert es.render(ok) == "Has the statistics of studded leather, with no metal"
    assert {o["id"] for o in es.VOCAB["armour"]} == set(ARMOUR)
    refused = es.validate({"type": "as_base", "target": "bulette plate"})
    assert refused and "studded leather" in refused[0]
    none = es.validate({"type": "as_base", "target": "none"})
    assert none and "studded leather" in none[0]


def test_both_new_types_are_standing_properties_and_refuse_a_trigger():
    """"Immune to fire on a hit" and "studded leather every round" are not rules. A trigger
    on either would be accepted and ignored by every reader; it is refused with the fix."""
    for spec in ({"type": "object_immunity", "target": "fire", "trigger": "hit"},
                 {"type": "as_base", "target": "studded leather", "trigger": "worn"},
                 {"type": "as_base", "target": "studded leather", "trigger": "each_round",
                  "duration": {"amount": 3, "unit": "round"}}):
        problems = es.validate(spec)
        assert problems, spec
    assert any("Remove the trigger" in p for p in es.validate(
        {"type": "object_immunity", "target": "fire", "trigger": "hit"}))


# --- the enchanting cost -----------------------------------------------------------------------

DRAGONHIDE_DISCOUNT = {"type": "gear_mod", "target": "enchant_cost_pct", "amount": -25,
                       "applies_to": "energy_resistance", "book": True}


def test_dragonhides_discount_is_one_document_that_validates_and_reads_as_the_book():
    """Dragonhide: "adding energy protection later costs 25% less" (CRB/UE; plan §15). No
    material, property or reader named an enchanting cost anywhere in the app. As a
    document it validates, reads as the book does, and is a benefit — a cheaper enchantment
    is never the hide's drawback."""
    assert es.validate(DRAGONHIDE_DISCOUNT) == []
    assert es.render(DRAGONHIDE_DISCOUNT) == \
        "Energy resistance enchantments on it cost 25% less"
    assert not es.is_drawback(DRAGONHIDE_DISCOUNT)
    assert es.is_drawback(dict(DRAGONHIDE_DISCOUNT, amount=10))
    assert "enchant_cost_pct" in {o["id"] for o in es.VOCAB["gear_target"]}


def test_a_discount_must_say_what_it_reaches_and_be_the_books():
    """A discount with no family is a discount on everything, which no book material gives;
    a house one would be summed by the build by target and lose its `applies_to` (see
    `es.COST_TARGETS`), so it would be accepted and read by nobody. Each refusal names the
    fix, in the classbuilder's style."""
    no_family = es.validate({k: v for k, v in DRAGONHIDE_DISCOUNT.items()
                             if k != "applies_to"})
    assert no_family and "energy_resistance" in no_family[0]
    unknown = es.validate(dict(DRAGONHIDE_DISCOUNT, applies_to="flight"))
    assert unknown and "energy_resistance" in unknown[0]
    house = es.validate({k: v for k, v in DRAGONHIDE_DISCOUNT.items() if k != "book"})
    assert house and '"book": true' in house[0]
    assert es.validate(dict(DRAGONHIDE_DISCOUNT, amount=-100))
    assert es.validate(dict(DRAGONHIDE_DISCOUNT, amount=0))


def test_applies_to_is_refused_wherever_nothing_reads_it():
    """A key no reader asks is a fact that silently does nothing. `applies_to` means
    something on the enchanting cost and nowhere else."""
    on_acp = es.validate({"type": "gear_mod", "target": "acp", "amount": -2,
                          "applies_to": "energy_resistance"})
    assert on_acp and "enchant_cost_pct" in on_acp[0]
    on_resist = es.validate({"type": "resistance", "target": "fire", "amount": 2,
                             "applies_to": "energy_resistance"})
    assert on_resist and "Remove it" in on_resist[0]


def test_every_cost_family_names_properties_the_table_has():
    """The family is how the Enchanting cost reader matches a property to a discount
    (contracts §6.3). A family naming a property id the table does not carry would discount
    nothing, silently."""
    table = es.properties()
    for family, row in es.ENCHANT_COST_FAMILIES.items():
        assert row["properties"], family
        for pid in row["properties"]:
            assert pid in table, (family, pid)
            assert es.cost_family_of(pid) == family
            # Every one of them is an energy resistance, by its own documents.
            assert any(d.get("type") == "resistance" for d in table[pid]["documents"])
    assert es.cost_family_of("flaming") == ""
    assert es.cost_family_of("") == ""


def test_the_discount_stays_whole_in_the_build_and_out_of_its_gear_numbers(monkeypatch):
    """`forge_items.build` gives every `GEAR_TARGETS` key a slot in the build's `gear` and
    sums same-target rows into it: the discount there would be one bare −25 with its
    `applies_to` gone. Kept out of that dict, a book discount on the main piece reaches the
    build's `book` list whole, where the cost reader finds it, and the suit's own numbers
    (the ones `armour_row` folds) are exactly what they were without it."""
    hide = {"id": "test-red-dragonhide", "name": "Red dragonhide", "kind": "hide",
            "armour": [{"type": "object_immunity", "target": "fire", "book": True},
                       DRAGONHIDE_DISCOUNT,
                       {"type": "gear_mod", "target": "hardness", "amount": 10,
                        "book": True}]}
    plain = dict(hide, armour=hide["armour"][2:])
    docs = {"with": hide, "without": plain}
    monkeypatch.setattr(forge_items, "material", lambda mid: docs.get(str(mid)))

    def suit(body):
        return {"id": "suit", "name": "Suit", "gear": "armour", "base": "hide armour",
                "craft": "leatherworker", "quality_index": 1,
                "pieces": {"body": {"material": body, "passes": 0}},
                "smith": {"level": 1, "perks": {}}}

    built = forge_items.build(suit("with"))
    assert "enchant_cost_pct" not in forge_items.GEAR_TARGETS
    assert "enchant_cost_pct" not in built["gear"]
    assert built["gear"] == forge_items.build(suit("without"))["gear"]
    found = [b for b in built["book"] if b.get("target") == "enchant_cost_pct"]
    assert len(found) == 1 and found[0]["applies_to"] == "energy_resistance"
    assert found[0]["amount"] == -25
    assert any(b.get("type") == "object_immunity" for b in built["book"])


# --- working traits ----------------------------------------------------------------------------

def test_every_leather_working_trait_validates_and_says_its_own_words():
    """No leather material carried a working trait (plan §14.1): a tannin that "halves tanning
    time" said so in prose the bench never read. Each of the fifteen validates, executes (the
    bench reads `working`), renders a sentence of its own — not its id, not another trait's —
    and is spelled as a tag the bench can ask by prefix (`working.thick`)."""
    assert es.LEATHER_WORKING_TRAITS == (
        "thick", "fast_tan", "slow_tan", "ceiling_up", "ceiling_down", "salt_proof",
        "tans_white", "supple", "fills_tooling", "strong_seam", "weatherproof", "fine_pitch",
        "fast_colour", "fugitive", "rancid")
    lines = set()
    for trait in es.LEATHER_WORKING_TRAITS:
        assert trait in es.WORKING_TRAITS
        spec = {"type": "working", "trait": trait}
        assert es.validate(spec) == [] and es.leather_effect_problems(spec) == [], trait
        assert es.executable(spec)
        line = es.render(spec)
        assert line and line != trait and "_" not in line and line[0].isupper(), line
        lines.add(line)
    every = {es.render({"type": "working", "trait": t}) for t in es.WORKING_TRAITS}
    assert len(lines) == len(es.LEATHER_WORKING_TRAITS)
    assert len(every) == len(es.WORKING_TRAITS), "two traits read the same on a card"
    assert es.working_tag("thick") == "working.thick"
    assert es.WORKING_TRAITS.count("thick") == 1


def test_a_leather_working_trait_outside_the_list_is_refused_with_the_list_named():
    """A trait the leather bench does not read does nothing at it. "shiny" is no trait at
    all; "slaggy" is the forge's and means slag in a smelt — on a hide it would be accepted
    by the general vocabulary and read by no leather step. Both are refused by the leather
    validator with the leather list named; the two shared traits the plan itself uses on a
    hide (`flawless`, §7; `forgiving`, §14.2) pass."""
    for trait in ("shiny", "slaggy", "solvent:water", "volatile"):
        problems = es.leather_effect_problems({"type": "working", "trait": trait})
        named = [p for p in problems if "leather bench" in p]
        assert named, (trait, problems)
        assert all(t in named[0] for t in es.LEATHER_TRAITS), named[0]
    assert es.validate({"type": "working", "trait": "shiny"})
    for trait in es.LEATHER_SHARED_TRAITS:
        assert es.leather_effect_problems({"type": "working", "trait": trait}) == []


def test_the_leather_validator_refuses_narrative_the_vocabulary_keeps():
    """96 of 171 leather specs were narrative (plan §14.1). The vocabulary keeps narrative
    legal (the herb and spell corpora use it); the leather validator refuses it, named."""
    spec = {"type": "narrative", "target": "Heavy and stubborn: check penalty one worse"}
    assert es.validate(spec) == []
    refused = es.leather_effect_problems(spec)
    assert refused and "never narrative" in refused[0]


# --- honesty -----------------------------------------------------------------------------------

def test_each_addition_either_runs_or_waits_on_a_named_reader():
    """The contract fixed `executable()` True for every addition; the honesty ratchet
    (tests/test_effectspec_extensions.py, "no type may be narrative wearing a costume")
    refuses a type that claims the engine runs it when nothing does — measured on the
    enchanting revamp's first full run, ten types claimed and none ran. So each new type or
    target waits in the ledger with its reader's site until leather lane B (or the
    Enchanting price) lands it, and is executable the moment its line comes out. This test
    holds in both states, so the reader's lane removes the line and nothing else."""
    for type_id, sample in (("object_immunity", {"target": "fire"}),
                            ("as_base", {"target": "studded leather"})):
        spec = {"type": type_id, **sample}
        _, etype = es.find(type_id)
        if type_id in es.AWAITING_READER:
            assert not es.executable(spec) and not etype.engine
            assert etype.blocked.startswith("Not run yet: its reader")
            assert es.AWAITING_READER[type_id] in etype.blocked
            assert "lane B" in es.AWAITING_READER[type_id]
        else:
            assert es.executable(spec) and etype.engine
    waiting = es.TARGETS_AWAITING_READER.get("gear_mod", {})
    assert es.executable(DRAGONHIDE_DISCOUNT) == ("enchant_cost_pct" not in waiting)
    if "enchant_cost_pct" in waiting:
        assert "magic_layer" in waiting["enchant_cost_pct"]
    # The forge's own gear numbers are untouched by the waiting target.
    assert es.executable({"type": "gear_mod", "target": "acp", "amount": -2})
    json.dumps(es.catalogue())


# --- the owner's reduced DR (answer 6, 2026-10-08) ---------------------------------------------

def test_a_leather_document_can_carry_reduced_dr_with_its_bypass():
    """"add the reduced DR": a generic hide from a creature with DR N/x gives DR max(1, N/5)/x.
    The vocabulary already had it — `damage_reduction` with `amount` and `bypass`, the same
    document adamantine armour's book DR is — so lane D writes
    `{"type": "damage_reduction", "amount": 1, "bypass": "silver"}` in a hide's `armour` list
    (empty bypass for DR/—). The leather validator holds what the general one cannot over a
    corpus full of stat-block debris: a misspelt bypass is a word no blow carries, which
    silently turns DR 1/sliver into DR 1/—, the strongest kind; "—" written in is a second
    spelling of the empty bypass; and a hide's DR is a whole number of 1 or more."""
    for bypass, line in (("silver", "DR 1/silver"), ("magic", "DR 1/magic"),
                         ("", "DR 1/—"), ("cold iron and good", "DR 1/cold iron and good"),
                         ("good or silver", "DR 1/good or silver")):
        spec = {"type": "damage_reduction", "amount": 1, "bypass": bypass}
        assert es.validate(spec) == [] and es.leather_effect_problems(spec) == [], bypass
        assert es.render(spec) == line
        assert es.executable(spec)
    for bad in ("sliver", "cold iorn", "silver or wood"):
        problems = es.leather_effect_problems(
            {"type": "damage_reduction", "amount": 1, "bypass": bad})
        assert problems and "silver" in problems[0] and "magic" in problems[0], bad
    for dash in ("—", "-", "–"):
        problems = es.leather_effect_problems(
            {"type": "damage_reduction", "amount": 1, "bypass": dash})
        assert problems and "leave bypass empty" in problems[0], dash
    for amount in (0, -1, "1d4", True):
        assert es.leather_effect_problems(
            {"type": "damage_reduction", "amount": amount, "bypass": "silver"}), amount


HIDE = {"id": "test-werewolf-hide", "name": "Werewolf hide", "kind": "hide",
        "armour": [{"type": "damage_reduction", "amount": 1, "bypass": "silver"},
                   {"type": "skill_mod", "target": "stealth", "amount": 2,
                    "bonus_type": "material"},
                   {"type": "gear_mod", "target": "acp", "amount": -2}]}


@pytest.fixture
def hide_doc(monkeypatch):
    monkeypatch.setattr(forge_items, "material",
                        lambda mid: HIDE if str(mid) == HIDE["id"] else None)


def test_reduced_dr_on_a_worn_hide_suit_reaches_the_wearers_dr(hide_doc):
    """The shape above, worn: a Sound leather suit whose body is a hide with DR 1/silver gives
    Kesst DR 1/silver through the one DR funnel (`Actor.damage_reduction`, which reads worn
    builds through `worn_specs_of`), a silver blow passes it, energy never meets it, and
    taking the suit off takes it away. Before the owner's answer the plan inherited no DR
    at all (plan §5.4: "DR: nothing in this pass")."""
    for spec in HIDE["armour"]:
        assert es.leather_effect_problems(spec) == [], spec
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=5))
    pc = scene.pc()
    rec = {"id": "werewolf-leather", "name": "Werewolf Leather", "kind": "crafted",
           "craft": "leatherworker", "count": 1, "gear": "armour", "base": "leather",
           "slot": "armor", "quality_index": 1,
           "pieces": {"body": {"material": HIDE["id"], "passes": 0}},
           "smith": {"level": 1, "perks": {}}, "schema": 3}
    pc.add_stock(forge_items.stock_item(rec))
    assert pc.damage_reduction("slashing") is None
    out = engine.run(engine.validate([{"op": "wear", "actor": "pc", "because": "test",
                                       "params": {"item": "werewolf-leather"}}])).outcomes[0]
    assert pc.armour_record() and pc.armour_record()["id"] == "werewolf-leather", out.tell
    dr = pc.damage_reduction("slashing")
    assert dr is not None and dr.label == "DR 1/silver"
    assert pc.damage_reduction("slashing", traits=("silver",)) is None
    assert pc.damage_reduction("fire") is None
    engine.run(engine.validate([{"op": "take_off", "actor": "pc", "because": "t",
                                 "params": {"item": "werewolf leather"}}]))
    assert pc.damage_reduction("slashing") is None
