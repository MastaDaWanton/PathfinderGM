"""The forge's effect vocabulary: `gear_mod`, `strikes_as`, `working`, the material bonus,
`book` and the item triggers (docs/blacksmithing-contracts.md §2).

Measured before any of this existed: 112 materials, 63 effect specs, **40 of them
`narrative`** — prose nothing could execute. Mithral's five armour numbers were one line of
text, cold iron had no way to say it struck as cold iron, and no material carried a single
trait the bench could read. Every test here names the gap it closes.
"""
from __future__ import annotations

import json

import pytest

from rules import effectspec as es
from rules.dice import Modifier, stack


# --- the three new types exist, are authorable and claim to execute ------------------------

@pytest.mark.parametrize("type_id", ["gear_mod", "strikes_as", "working"])
def test_the_forge_types_are_in_the_catalogue_and_executable(type_id):
    """Mithral's armour numbers were one prose line nothing could execute: there was no
    type to write them as. Each new type must be findable, authorable from the homebrew
    bench (it serialises with the catalogue), and claim the engine runs it — the contract
    says True for all three, and lane B's readers are what make that true."""
    found = es.find(type_id)
    assert found is not None, f"{type_id} is not in the catalogue"
    _, etype = found
    assert etype.engine
    assert es.executable({"type": type_id})
    ids = [t["id"] for c in es.catalogue()["categories"] for t in c["types"]]
    assert ids.count(type_id) == 1
    json.dumps(es.catalogue())


def test_every_dropdown_the_forge_types_use_is_built_from_the_constants():
    """Two copies of one list drift: a consequence rule fixed in one prompt kept shipping
    from its copy. The editor's dropdowns and the module's lists must be the same set, so a
    target the validator accepts is a target the form offers, and the reverse."""
    vocab = lambda name: [o["id"] for o in es.VOCAB[name]]   # noqa: E731
    # The leatherworker's enchanting cost (`es.COST_TARGETS`, leather lane A) is offered
    # after the item's own numbers and kept out of `GEAR_TARGETS`, whose keys the build sums.
    assert vocab("gear_target") == list(es.GEAR_TARGETS) + list(es.COST_TARGETS)
    assert vocab("strikes_as") == es.STRIKES_AS
    assert vocab("working_trait") == es.WORKING_TRAITS
    for t in ("gear_mod", "strikes_as", "working"):
        for f in es.find(t)[1].fields:
            if f.kind == "choice":
                assert f.vocab in es.VOCAB, (t, f.id)


def test_the_lists_are_exactly_what_the_contract_names():
    """Lane C writes 112 materials against these ids and lane D's bench reads them. A trait
    renamed here ('hot-short' for 'hot_short') would refuse every material that uses it."""
    # The enchanting revamp appended to all three (docs/enchanting-contracts.md §2.1, §5):
    # distance's and throwing's range numbers, what a magic weapon strikes as, and the
    # circle's working traits. Appended, never renamed: every forge id here is unchanged,
    # which is what this test protects.
    assert set(es.GEAR_TARGETS) == {"acp", "max_dex", "asf", "weight_pct", "hardness",
                                    "hp_per_inch", "category", "speed_penalty",
                                    "range_pct", "throw_range_ft"}
    # `ghost_touch` joined in wave 2 (contracts §12 item 5): ghost salt blanching's book
    # clause, which lane C had to stand in a +2 against undead for.
    assert es.STRIKES_AS == ["cold_iron", "silver", "adamantine", "ghost_touch",
                             "magic", "good", "evil", "lawful", "chaotic"]
    assert es.WORKING_TRAITS == [
        "easily_worked", "flawless", "malleable", "pure", "slaggy", "sulfurous",
        "clean_heat", "quench_sensitive", "narrow_window", "forgiving", "reactive",
        "cleans_slag", "weld_aid", "brittle", "hot_short",
        "night_only", "eager", "skittish", "heavy", "volatile",
        # The alchemist's bench (alchemy lane B, contracts §2.4), appended; `volatile`
        # and `pure` are shared and not repeated.
        "stabilizer", "catalyst", "apparatus", "solid", "liquid", "combustible",
        "slow_to_dissolve", "light_sensitive", "corrosive", "toxic_to_handle", "wild",
        "drinkable", "shatters", "bursts", "struck", "stick", "fireproof", "warded",
        "lead_lined", "solvent:water", "solvent:alcohol", "solvent:vinegar", "solvent:oil",
        "solvent:acid",
        # The leatherworker's (leather lane A, leatherworking contracts §2), appended.
        "thick", "fast_tan", "slow_tan", "ceiling_up", "ceiling_down", "salt_proof",
        "tans_white", "supple", "fills_tooling", "strong_seam", "weatherproof", "fine_pitch",
        "fast_colour", "fugitive", "rancid"]


# --- mithral, written as documents --------------------------------------------------------

MITHRAL_ARMOUR = [
    {"type": "gear_mod", "target": "acp", "amount": 3, "book": True},
    {"type": "gear_mod", "target": "max_dex", "amount": 2, "book": True},
    {"type": "gear_mod", "target": "asf", "amount": -10, "book": True},
    {"type": "gear_mod", "target": "weight_pct", "amount": -50, "book": True},
    {"type": "gear_mod", "target": "category", "amount": -1, "book": True},
]


def test_mithral_armour_is_five_documents_that_validate_and_execute():
    """Mithral's "-3 ACP, +2 max Dex, -10% spell failure, half weight, one category
    lighter for movement" was one prose sentence. Written as five gear_mods each must
    validate clean, execute, and render a line a player can read."""
    lines = []
    for spec in MITHRAL_ARMOUR:
        assert es.validate(spec) == [], spec
        assert es.executable(spec)
        lines.append(es.render(spec))
    assert lines == [
        "Armour check penalty 3 lighter", "+2 maximum Dexterity bonus",
        "-10% arcane spell failure", "Weighs 50% less",
        "Moves as one weight class lighter"]


def test_a_gear_number_adds_to_the_table_and_the_drawback_follows_the_target():
    """Plan §5.4 wrote mithral's acp as -3 (lighter) and adamantine's as -2 (heavier):
    the same sign meaning opposite things. The amount is added to the number as
    `tables.ARMOUR` keeps it — acp negative, spell failure positive — so a lighter penalty
    is +3, and whether an effect is the list's drawback is a lookup by target, not the
    sign alone. Every mithral number is a benefit; adamantine's acp -2 and noqual's asf
    +20 are drawbacks."""
    from rules.tables import ARMOUR

    assert ARMOUR["chain shirt"]["acp"] < 0 and ARMOUR["chain shirt"]["asf"] > 0
    assert not any(es.is_drawback(s) for s in MITHRAL_ARMOUR)
    assert es.is_drawback({"type": "gear_mod", "target": "acp", "amount": -2})
    assert es.is_drawback({"type": "gear_mod", "target": "asf", "amount": 20})
    assert es.is_drawback({"type": "gear_mod", "target": "hardness", "amount": -5})
    assert es.is_drawback({"type": "gear_mod", "target": "weight_pct", "amount": 10})
    assert es.is_drawback({"type": "combat_mod", "target": "attack", "amount": -2,
                           "bonus_type": "material"})
    assert not es.is_drawback({"type": "combat_mod", "target": "damage", "amount": 2,
                               "bonus_type": "material"})
    assert not es.is_drawback({"type": "strikes_as", "target": "silver"})


def test_the_heavier_side_of_every_gear_target_renders_in_plain_words():
    """'+3 armour check penalty' would read as a heavier suit to anyone who has seen a
    printed one. Each target is worded for its own sign, and none falls through to the
    type's name — which tells a player nothing."""
    samples = {
        ("acp", -2): "-2 armour check penalty",
        ("max_dex", -1): "-1 maximum Dexterity bonus",
        ("asf", 20): "+20% arcane spell failure",
        ("weight_pct", 10): "Weighs 10% more",
        ("hardness", -5): "-5 hardness",
        ("hp_per_inch", 10): "+10 hit points per inch",
        ("category", 1): "Moves as one weight class heavier",
        ("speed_penalty", 5): "5 ft more speed penalty",
        # The enchanting revamp's two (distance, throwing).
        ("range_pct", 100): "Doubles the range increment",
        ("throw_range_ft", 10): "Can be thrown, range increment 10 ft",
    }
    for (target, amount), line in samples.items():
        assert es.render({"type": "gear_mod", "target": target, "amount": amount}) == line
    assert set(t for t, _ in samples) == set(es.GEAR_TARGETS)


def test_a_gear_number_that_changes_nothing_or_too_much_is_refused_with_the_fix():
    """An effect that is authored and does nothing is the failure docs/homebrew-rules.md
    §1 exists to prevent; a zero gear_mod is that, and a weight of -100% is a suit that
    weighs nothing. Each refusal names the fix."""
    zero = es.validate({"type": "gear_mod", "target": "hardness", "amount": 0})
    assert zero and "changes nothing" in zero[0]
    assert es.validate({"type": "gear_mod", "target": "category", "amount": -3})
    assert es.validate({"type": "gear_mod", "target": "weight_pct", "amount": -100})
    assert es.validate({"type": "gear_mod", "target": "asf", "amount": 150})
    bad = es.validate({"type": "gear_mod", "target": "weight", "amount": -50})
    assert bad and "hardness" in bad[0]                # the list of real targets
    assert es.validate({"type": "gear_mod", "target": "acp", "amount": "light"})
    assert es.validate({"type": "gear_mod", "target": "acp"})        # no amount


# --- strikes_as -----------------------------------------------------------------------------

def test_strikes_as_names_a_material_from_the_list_and_nothing_else():
    """`Reduction.bypassed_by` has been on the sheet since stage 2 and nothing ever passed
    it a trait, because no effect could say a blade *was* cold iron. The type takes the
    list and refuses a material it does not know, rather than inventing one."""
    for m in es.STRIKES_AS:
        spec = {"type": "strikes_as", "target": m}
        assert es.validate(spec) == []
    assert es.render({"type": "strikes_as", "target": "cold_iron"}) == "Strikes as cold iron"
    assert es.render({"type": "strikes_as", "target": "adamantine"}) == "Strikes as adamantine"
    refused = es.validate({"type": "strikes_as", "target": "mithral"})
    assert refused and "cold_iron" in refused[0]
    assert es.validate({"type": "strikes_as"})


# --- working traits -------------------------------------------------------------------------

def test_every_working_trait_validates_and_renders_its_own_words():
    """Under the herb trait rule, 58 of the 112 materials had no trait at all and none had
    three; there was no trait to give them. Each of the fifteen must validate and render
    a sentence of its own — not its id, and not the same words as another trait."""
    seen = set()
    for trait in es.WORKING_TRAITS:
        spec = {"type": "working", "trait": trait}
        assert es.validate(spec) == [], trait
        line = es.render(spec)
        assert line and line != trait and "_" not in line, (trait, line)
        assert line[0].isupper()
        seen.add(line)
    assert len(seen) == len(es.WORKING_TRAITS)
    assert es.render({"type": "working", "trait": "easily_worked"}) \
        == "Works easily at the forge"
    assert es.validate({"type": "working", "trait": "forgiving", "amount": 20}) == []
    assert "(+20)" in es.render({"type": "working", "trait": "forgiving", "amount": 20})


def test_a_working_trait_outside_the_list_is_refused():
    """A trait the bench does not read is a trait that does nothing at the forge."""
    refused = es.validate({"type": "working", "trait": "shiny"})
    assert refused and "easily_worked" in refused[0]
    assert es.validate({"type": "working"})


# --- the material bonus ---------------------------------------------------------------------

def test_material_is_a_bonus_type_that_stacks_with_others_and_never_with_itself():
    """Plan §5.2's iron writes `"bonus_type": "material"`, which failed validation outright
    before — the same way Coagulated Plate's "armor" did. In the funnel it must add to an
    enhancement bonus and collide with a second material bonus, best one kept; and two
    material penalties still both apply, as every 1e penalty does."""
    spec = {"type": "combat_mod", "target": "damage", "amount": 2,
            "bonus_type": "material"}
    assert es.validate(spec) == []
    assert "material" in {o["id"] for o in es.VOCAB["bonus_type"]}

    kept = stack([Modifier(2, "iron", "material"), Modifier(1, "+1", "enhancement"),
                  Modifier(3, "adamantine", "material")])
    assert sorted(m.value for m in kept) == [1, 3]
    penalties = stack([Modifier(-2, "a", "material"), Modifier(-1, "b", "material")])
    assert sum(m.value for m in penalties) == -3


# --- book and the item triggers -------------------------------------------------------------

def test_book_is_a_boolean_and_nothing_else():
    """`book` decides that a number is applied from the main piece only and never scaled.
    A "yes" string would be a second spelling of the same fact for every reader to
    handle, so it is refused with the fix named; true and false both pass."""
    base = {"type": "strikes_as", "target": "silver"}
    assert es.validate({**base, "book": True}) == []
    assert es.validate({**base, "book": False}) == []
    for wrong in ("yes", 1, "true"):
        problems = es.validate({**base, "book": wrong})
        assert problems and "true or false" in problems[0], wrong


def test_item_triggers_need_no_duration_where_a_spell_trigger_does():
    """Before, any trigger other than 'immediately' needed a duration — right for
    incendiary cloud, wrong for a blade: wyvern blood's venom fires on the first wound
    every day for as long as the blade exists, and asking for a duration would make the
    author invent one. A spell's each_round still needs one."""
    wyvern = {"type": "save_gate", "target": "fort", "dc": 17,
              "trigger": "first_wound_daily",
              "on_failure": [{"type": "ability_damage", "target": "con", "dice": "1d4"}]}
    assert es.validate(wyvern) == []
    for trig in ("hit", "crit"):
        assert es.validate({"type": "damage", "dice": "1d4", "damage_type": "fire",
                            "lethality": "lethal", "trigger": trig}) == []
    assert es.validate({"type": "damage", "dice": "1d4", "damage_type": "fire",
                        "lethality": "lethal", "trigger": "each_round"})


def test_carried_works_only_on_the_three_types_a_burden_can_have():
    """Abysium sickens whoever carries it; viridium makes a daily save. Carrying a thing
    cannot swing a sword or grant a sense, so 'while carried' is accepted on
    apply_condition, save_gate and ability_damage and refused, named, on everything
    else."""
    ok = [
        {"type": "apply_condition", "target": "sickened", "trigger": "carried"},
        {"type": "save_gate", "target": "fort", "dc": 12, "trigger": "carried"},
        {"type": "ability_damage", "target": "con", "dice": "1", "trigger": "carried"},
    ]
    for spec in ok:
        assert es.validate(spec) == [], spec
    assert es.render(ok[0]) == "Causes sickened, while carried"
    refused = es.validate({"type": "damage", "dice": "1d4", "damage_type": "fire",
                           "lethality": "lethal", "trigger": "carried"})
    assert refused and "apply_condition" in refused[0]


def test_a_standing_property_refuses_a_trigger():
    """"Strikes as silver on a crit" and "-2 armour check penalty every round" are not
    rules. A trigger on gear_mod, strikes_as or working would be accepted and silently
    ignored by every reader; it is refused instead."""
    for spec in ({"type": "strikes_as", "target": "silver", "trigger": "crit"},
                 {"type": "gear_mod", "target": "acp", "amount": -2, "trigger": "hit"},
                 {"type": "working", "trait": "pure", "trigger": "carried"},
                 {"type": "gear_mod", "target": "acp", "amount": -2,
                  "trigger": "each_round", "duration": {"amount": 3, "unit": "round"}}):
        assert es.validate(spec), spec


def test_item_triggers_render_on_the_card():
    """The card is read by a player; a rider that fires on a crit and reads the same as
    one that fires on cast misdescribes the weapon."""
    leprosy = {"type": "save_gate", "target": "fort", "dc": 12, "trigger": "crit",
               "on_failure": [{"type": "apply_condition", "target": "sickened"}]}
    assert es.render(leprosy).endswith("on a critical hit")
    assert es.render({"type": "damage", "dice": "1d4", "damage_type": "fire",
                      "lethality": "lethal", "trigger": "hit"}) == "1d4 fire damage, on a hit"
    assert "first wound" in es.render({"type": "damage", "dice": "1", "damage_type": "fire",
                                       "lethality": "lethal",
                                       "trigger": "first_wound_daily"})
    for trig in es.ITEM_TRIGGERS:
        assert trig in {o["id"] for o in es.VOCAB["trigger"]}


def test_plan_iron_document_validates_as_written():
    """Plan §5.2's own iron, end to end: three weapon effects, three armour effects, a
    working trait, every one of them executable and none narrative. If the worked example
    in the plan cannot be written, no material can."""
    weapon = [
        {"type": "combat_mod", "target": "damage", "amount": 2, "bonus_type": "material"},
        {"type": "combat_mod", "target": "attack", "amount": -2, "bonus_type": "material"},
        {"type": "gear_mod", "target": "hardness", "amount": 2},
    ]
    armour = [
        {"type": "combat_mod", "target": "ac", "amount": 2, "bonus_type": "material"},
        {"type": "gear_mod", "target": "acp", "amount": -2},
        {"type": "gear_mod", "target": "hardness", "amount": 2},
    ]
    working = [{"type": "working", "trait": "forgiving", "note": "wide heat band"}]
    for spec in weapon + armour + working:
        assert es.validate(spec) == [], spec
        assert es.executable(spec), spec
    assert sum(es.is_drawback(s) for s in weapon) == 1
    assert sum(es.is_drawback(s) for s in armour) == 1
