"""456 weapons, and the reach rule they finally made possible.

`tables.WEAPONS` held eleven — enough for the pregenerated characters and nothing else. A
player who wanted a glaive got `KeyError: no such weapon 'glaive'`.

The workbook is a formatted document, not a flat table, and that is the whole difficulty:
proficiency headings alternate with section headings, and **each section carries its own
column layout** — nine distinct ones. Firearms add Misfire and Capacity; siege engines add
Crew, Aim, Load and Speed and drop the small-damage column. A first survey that read columns
by position reported damage types of "50 lbs." and "1 lb.", because a siege engine's weight
had landed where the type column was.

The layering runs the *opposite* way to the class overlay, on purpose. The imported file is
the base and the eleven hand-written entries merge on top, because those eleven are what
several hundred existing tests are written against and a bulk import quietly changing the
rapier's crit range would be a regression found in play rather than here.
"""
from __future__ import annotations

import pytest

from rules import reactions, weapons
from rules.bestiary import instantiate
from rules.engine import Scene
from rules.grid import Grid
from rules.sheet import load_pc
from rules.tables import WEAPONS as SHIPPED


# --- the index ------------------------------------------------------------------------------

def test_the_whole_armoury_is_here():
    assert len(weapons.all_weapons()) > 400


def test_a_glaive_no_longer_raises():
    """The symptom that started this: eleven weapons in the table and a KeyError for
    anything else."""
    assert weapons.get("glaive")["damage"] == "1d10"


def test_the_hand_written_eleven_win():
    """They are the curated ones and the existing suite is written against them. A bulk
    import silently changing the rapier's crit range would be found in play, not here."""
    for key, entry in SHIPPED.items():
        got = weapons.get(key)
        for field, value in entry.items():
            assert got[field] == value, f"{key}.{field} was overwritten by the import"


def test_the_import_still_fills_in_what_the_table_never_had():
    """Winning on conflicts is not the same as ignoring the file."""
    assert weapons.get("rapier").get("traits") is not None
    assert weapons.get("rapier")["prof"] == "martial"


def test_every_weapon_has_the_fields_the_engine_reads():
    for key, w in weapons.all_weapons().items():
        for field in ("name", "crit_range", "crit_mult", "type", "category", "hands",
                      "prof", "finessable", "traits"):
            assert field in w, f"{key} is missing {field}"


def test_the_licence_travels_with_the_content():
    assert "Open Game" in weapons.meta().get("licence", "")


def test_the_component_columns_are_marked_as_not_open_game_content():
    """The head/haft/grip/guard columns are the author's own, for crafting."""
    assert "not Open Game Content" in weapons.meta().get("licence", "")


# --- what the columns actually said -------------------------------------------------------------

def test_a_threat_range_is_split_from_its_multiplier():
    assert (weapons.get("rapier")["crit_range"], weapons.get("rapier")["crit_mult"]) == (18, 2)
    assert (weapons.get("greatsword")["crit_range"],
            weapons.get("greatsword")["crit_mult"]) == (19, 2)


def test_a_bare_multiplier_threatens_only_on_a_twenty():
    assert weapons.get("longspear")["crit_range"] == 20
    assert weapons.get("longspear")["crit_mult"] == 3


def test_damage_types_that_offer_a_choice_keep_both():
    assert set(weapons.get("dagger")["types"]) == {"piercing", "slashing"}


def test_the_wording_of_a_dual_type_is_kept_rather_than_guessed_at():
    """"B or P" is the wielder's choice and "B and P" applies both. Damage reduction is
    the only thing reading this today and treats them alike, so the distinction is
    preserved as text instead of being invented as a mechanic."""
    assert weapons.get("morningstar")["type_text"].lower() in ("b and p", "b & p")
    assert set(weapons.get("morningstar")["types"]) == {"bludgeoning", "piercing"}


def test_ranges_and_weights_become_numbers():
    assert weapons.get("dagger")["range_ft"] == 10
    assert weapons.get("longbow")["range_ft"] == 100
    assert weapons.get("greatsword")["weight_lb"] == 8


def test_costs_are_normalised_to_gold():
    assert weapons.get("dagger")["cost_gp"] == 2
    assert weapons.get("handwraps")["cost_gp"] == pytest.approx(0.1)   # 1 sp


def test_a_weapon_with_no_price_is_none_rather_than_zero():
    """A club costs nothing and a siege engine's price may simply be absent. Zero would
    read as free."""
    assert weapons.get("club")["cost_gp"] is None


def test_special_qualities_are_a_list():
    assert set(weapons.get("longspear")["traits"]) == {"brace", "reach"}
    assert "trip" in weapons.get("whip")["traits"]


def test_proficiency_and_section_come_from_the_headings():
    assert weapons.get("dagger")["prof"] == "simple"
    assert weapons.get("greatsword")["prof"] == "martial"
    assert weapons.get("whip")["prof"] == "exotic"


def test_two_handed_weapons_need_two_hands():
    assert weapons.get("greatsword")["hands"] == 2
    assert weapons.get("dagger")["hands"] == 1


def test_ranged_sections_are_marked_ranged():
    assert weapons.get("longbow")["category"] == "ranged"
    assert weapons.get("rapier")["category"] == "melee"


def test_a_section_with_its_own_column_layout_is_read_correctly():
    """Firearms put Misfire and Capacity where melee weapons put Type and Special.
    Reading by position gave weights as damage types."""
    musket = weapons.get("musket")
    assert musket["misfire"]
    assert musket["type"] in ("bludgeoning", "piercing", "slashing", "untyped")
    assert "lb" not in musket["type"]


def test_no_weapon_has_a_weight_where_its_damage_type_should_be():
    """The measurement that proved the position-based reader wrong, kept as a test."""
    for key, w in weapons.all_weapons().items():
        assert "lb" not in str(w["type"]).lower(), f"{key} has {w['type']!r} as its type"


def test_the_component_columns_survive_into_later_sections():
    """Only the very first header names them, but the data is in every melee section. A
    reader that dropped them after the first section lost them for 400 weapons."""
    assert weapons.get("glaive")["components"]["head"]
    assert weapons.get("longspear")["components"]["haft"] == "Wooden shaft"


def test_light_melee_weapons_are_finessable():
    assert weapons.get("dagger")["finessable"]
    assert not weapons.get("greatsword")["finessable"]


def test_the_three_named_exceptions_are_finessable_too():
    """1e names the rapier, whip and spiked chain specifically, and nothing in the sheet
    marks them."""
    for key in ("rapier", "whip"):
        assert weapons.get(key)["finessable"], key


# --- reach, which is what this import was really for ------------------------------------------------

def board(equipped="rapier"):
    s = Scene(location_id="5bbd0c40345f", grid=Grid(20, 20))
    s.add(load_pc("fixtures/pc-kesst.json"), at=(5, 5))
    s.actors["pc"].equipped = equipped
    return s


def test_a_reach_weapon_doubles_the_threatened_area():
    """`_reach_of` was natural reach only for as long as no weapon in the table had a
    trait field. Forty of them do now."""
    s = board("longspear")
    assert reactions._reach_of(s.actors["pc"]) == 10
    assert reactions.threatens(s, "pc", (7, 5))


def test_a_reach_weapon_cannot_strike_what_is_next_to_it():
    """The half of the rule that is easy to forget is the half that costs the player.
    Implementing only the doubling would make a glaive strictly better in the app than at
    a table."""
    s = board("glaive")
    assert reactions.reach_gap(s.actors["pc"])
    assert not reactions.threatens(s, "pc", (6, 5))
    assert not reactions.threatens(s, "pc", (6, 6))


def test_an_ordinary_weapon_threatens_what_is_next_to_it():
    s = board("rapier")
    assert reactions.threatens(s, "pc", (6, 5))
    assert not reactions.threatens(s, "pc", (7, 5))


def test_natural_reach_has_no_gap():
    """An ogre threatens everything out to ten feet, including what is under its nose.
    Only a reach *weapon* leaves a hole."""
    s = board("rapier")
    s.actors["pc"].size = "large"
    assert not reactions.reach_gap(s.actors["pc"])
    assert reactions.threatens(s, "pc", (7, 5))


def test_forty_weapons_carry_reach():
    assert sum(1 for w in weapons.all_weapons().values()
               if "reach" in w.get("traits", [])) >= 40


# --- lookups and search -------------------------------------------------------------------------------

def test_has_trait_is_tolerant_of_a_weapon_that_does_not_exist():
    """The callers are asking about geometry, and "no weapon, so no reach" is the right
    answer for an unarmed creature."""
    assert not weapons.has_trait("", "reach")
    assert not weapons.has_trait("a stern look", "reach")


def test_an_unknown_weapon_still_raises_from_get():
    with pytest.raises(KeyError):
        weapons.get("plasma rifle")


def test_search_prefers_an_exact_name():
    assert weapons.search("club")[0]["name"].lower() == "club"


def test_search_can_filter_to_a_trait():
    found = weapons.search("", trait="reach", limit=0)
    assert found and all("reach" in w["traits"] for w in found)


def test_search_can_filter_to_a_proficiency():
    found = weapons.search("", prof="simple", limit=0)
    assert found and all(w["prof"] == "simple" for w in found)


# --- through the sheet and the engine ---------------------------------------------------------------------

def test_a_character_can_wield_something_the_old_table_never_had():
    a = load_pc("fixtures/pc-kesst.json")
    a.weapons = ["glaive"]
    a.equipped = "glaive"
    assert a.weapon()["damage"] == "1d10"
    assert a.attack_modifiers("glaive")


def test_validation_accepts_a_weapon_from_the_import():
    from rules.dice import Dice
    from rules.engine import Engine

    s = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    pc.weapons = ["glaive"]
    s.add(pc)
    s.add(instantiate("thug", scene=s, name="the thug"))
    e = Engine(s, Dice(seed=1))
    intents = e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                           "because": "a wide sweep",
                           "params": {"weapon": "glaive", "full_attack": False}}])
    assert intents[0].params["weapon"] == "glaive"


def test_a_weapon_that_does_not_exist_is_still_rejected_with_a_suggestion():
    """The rejection used to print all eleven weapon names. At 456 that is noise, so it
    is a near-miss suggestion instead."""
    from rules.dice import Dice
    from rules.engine import Engine
    from rules.intents import IntentError

    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=1))
    with pytest.raises(IntentError) as caught:
        e.validate([{"op": "attack", "actor": "pc",
                     "params": {"weapon": "glave", "full_attack": False}}])
    assert "glaive" in str(caught.value)
    assert len(str(caught.value)) < 400
