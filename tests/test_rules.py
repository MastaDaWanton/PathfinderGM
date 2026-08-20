"""Tests for the rules core.

Each docstring names the measurement or the defect, not the behaviour. A test that only
asserts behaviour gets deleted by the next person; one that records what went wrong
survives.
"""
from __future__ import annotations

import pytest

from rules.dc import BadDC, resolve as resolve_dc
from rules.dice import Dice, Modifier
from rules.sheet import IllegalSheet, from_dict, load_pc
from rules.tables import ability_modifier, iterative_attacks, save_for


# --- Ability modifiers ------------------------------------------------------------

def test_ability_modifier_floors_toward_negative_infinity():
    """A C-style truncating (score-10)/2 gives -1 for a score of 7, where 1e says -2.

    Checked across the whole low range because the bug only appears on odd scores below
    10, which is exactly where nobody looks.
    """
    assert ability_modifier(7) == -2
    assert ability_modifier(9) == -1
    assert ability_modifier(10) == 0
    assert ability_modifier(11) == 0
    assert ability_modifier(3) == -4
    assert ability_modifier(18) == 4


def test_save_progression_matches_1e_table():
    """Good saves are 2 + level/2; poor are level/3. Both floor."""
    assert [save_for(True, l) for l in (1, 2, 3, 4, 20)] == [2, 3, 3, 4, 12]
    assert [save_for(False, l) for l in (1, 2, 3, 4, 20)] == [0, 0, 1, 1, 6]


def test_iterative_attacks_stop_at_plus_one():
    """BAB +6 gives two attacks, +11 three, +16 four; the fourth never appears below +16
    and no iterative below +1 is ever granted."""
    assert iterative_attacks(5) == [5]
    assert iterative_attacks(6) == [6, 1]
    assert iterative_attacks(11) == [11, 6, 1]
    assert iterative_attacks(16) == [16, 11, 6, 1]


# --- Dice --------------------------------------------------------------------------

def test_roll_total_is_raw_plus_every_named_modifier():
    d = Dice(seed=1)
    r = d.roll("2d6", [Modifier(3, "Str"), Modifier(-1, "shaken")])
    assert r.total == r.raw + 2
    assert [m.source for m in r.modifiers] == ["Str", "shaken"]


def test_natural_is_only_defined_for_a_single_d20():
    """Crits and natural 1s are defined on the face, not the total. 2d6 has no natural."""
    d = Dice(seed=1)
    assert d.d20().natural is not None
    assert d.roll("2d6").natural is None


def test_player_supplied_face_cannot_change_the_maths():
    """The popup is an input device, not a second source of truth.

    A player who edits the form supplies a different face; the modifiers still come from
    the sheet, so the total moves by exactly the difference in the face.
    """
    d = Dice()
    mods = [Modifier(9, "Stealth")]
    assert d.given(13, mods).total == 22
    assert d.given(1, mods).total == 10


def test_given_rejects_a_face_the_die_does_not_have():
    d = Dice()
    with pytest.raises(Exception):
        d.given(21, [], die="1d20")


# --- The sheet -----------------------------------------------------------------------

@pytest.fixture
def kesst():
    return load_pc("fixtures/pc-kesst.json")


def test_pregenerated_pc_computes_the_1e_numbers(kesst):
    """Hand-checked against the 1e rules for a human Rogue 1, Dex 17, leather, Stealthy:
    Stealth +9, Reflex +5, AC 15, CMD 14, attack +3 by Finesse, damage 1d6+1 by Str."""
    s = kesst.summary()
    assert s["skills"]["stealth"] == 9
    assert s["saves"] == {"fort": 1, "ref": 5, "will": 0}
    assert s["ac"] == 15
    assert kesst.cmd() == 14
    assert sum(m.value for m in kesst.attack_modifiers()) == 3
    assert sum(m.value for m in kesst.damage_modifiers()) == 1
    assert kesst.damage_dice() == "1d6"


def test_every_modifier_is_named(kesst):
    """The itemisation is the product. A total with an unnamed term is untraceable, and
    this is the assertion that stops one creeping in."""
    for m in kesst.skill_modifiers("stealth"):
        assert m.source and m.source != "notation"
    assert {m.source for m in kesst.skill_modifiers("stealth")} == {
        "ranks", "class skill", "Dex", "Stealthy",
    }


def test_weapon_finesse_moves_the_attack_but_never_the_damage(kesst):
    """A standard place to get 1e wrong: Finesse swaps Dex for Str on the attack roll
    only. Kesst has Dex 17 (+3) and Str 12 (+1) — attack +3, damage +1, not +3."""
    assert sum(m.value for m in kesst.attack_modifiers()) == 3
    assert [(m.value, m.source) for m in kesst.damage_modifiers()] == [(1, "Str")]


def test_conditions_penalise_the_pc_and_the_npc_through_the_same_code(kesst):
    from rules.bestiary import instantiate

    thug = instantiate("thug")
    before_pc = sum(m.value for m in kesst.skill_modifiers("stealth"))
    before_npc = sum(m.value for m in thug.skill_modifiers("stealth"))
    kesst.add_condition("shaken")
    thug.add_condition("shaken")
    assert sum(m.value for m in kesst.skill_modifiers("stealth")) == before_pc - 2
    assert sum(m.value for m in thug.skill_modifiers("stealth")) == before_npc - 2


def test_same_condition_twice_does_not_stack(kesst):
    """1e: the same condition does not stack, the longer duration wins."""
    kesst.add_condition("shaken", 3)
    kesst.add_condition("shaken", 7)
    assert len(kesst.conditions) == 1
    assert kesst.conditions[0].rounds_left == 7


def test_flat_footed_removes_dex_from_ac(kesst):
    assert kesst.ac() == 15
    assert kesst.ac(flat_footed=True) == 12


def test_max_dex_bonus_caps_ac():
    """Leather allows +6 Dex, so Kesst's +3 is uncapped; full plate allows +1 and must
    cap it. A missing cap silently over-armours every high-Dex character in heavy gear."""
    build = {
        "name": "test", "kind": "pc", "class": "fighter", "level": 1,
        "abilities": {"str": 12, "dex": 18, "con": 12, "int": 10, "wis": 10, "cha": 10},
        "armour": "full plate", "hp": 10, "ranks": {},
    }
    a = from_dict(build)
    assert a.ac() == 10 + 9 + 1


def test_hp_thresholds_apply_1e_death_rules(kesst):
    """Unconscious at 0 or below, dead at -Con. Kesst has Con 12, so -12 is dead and
    -11 is merely unconscious."""
    kesst.hp = -11
    kesst.apply_hp_state()
    assert kesst.has_condition("unconscious") and not kesst.has_condition("dead")
    kesst.hp = -12
    kesst.apply_hp_state()
    assert kesst.has_condition("dead")


def test_illegal_sheet_is_rejected_at_load_not_mid_scene():
    """A wrong sheet poisons every roll that follows, so overspent ranks must fail at
    load. Human Rogue 1 with Int 13 has 8 + 1 + 1 = 10 ranks; 11 is illegal."""
    build = {
        "name": "cheat", "kind": "pc", "class": "rogue", "level": 1,
        "abilities": {"str": 10, "dex": 14, "con": 10, "int": 13, "wis": 10, "cha": 10},
        "hp": 8, "ranks": {s: 1 for s in (
            "stealth", "perception", "acrobatics", "bluff", "climb", "diplomacy",
            "appraise", "swim", "intimidate", "disguise", "survival",
        )},
    }
    with pytest.raises(IllegalSheet, match="skill ranks"):
        from_dict(build)


def test_ranks_cannot_exceed_character_level():
    build = {
        "name": "cheat", "kind": "pc", "class": "rogue", "level": 1,
        "abilities": {"str": 10, "dex": 14, "con": 10, "int": 13, "wis": 10, "cha": 10},
        "hp": 8, "ranks": {"stealth": 4},
    }
    with pytest.raises(IllegalSheet, match="exceeds character level"):
        from_dict(build)


def test_untrained_use_of_a_trained_only_skill_is_refused(kesst):
    with pytest.raises(IllegalSheet, match="untrained"):
        kesst.skill_modifiers("spellcraft")


def test_unknown_feat_is_carried_as_flavour_and_says_so():
    """Silently pretending an unimplemented feat applied is worse than doing nothing and
    recording it, because the sheet then shows a bonus the engine never gives."""
    build = {
        "name": "test", "kind": "pc", "class": "rogue", "level": 1,
        "abilities": {"str": 10, "dex": 14, "con": 10, "int": 10, "wis": 10, "cha": 10},
        "hp": 8, "ranks": {"stealth": 1}, "feats": ["Combat Reflexes"],
    }
    a = from_dict(build)
    assert "carried as flavour" in a.notes
    assert sum(m.value for m in a.skill_modifiers("stealth")) == 1 + 3 + 2


# --- DC bands -------------------------------------------------------------------------

def test_bands_map_to_the_1e_difficulty_table():
    assert resolve_dc({"band": "tough"}).final == 15
    assert resolve_dc({"band": "challenging"}).final == 20
    assert resolve_dc("formidable").final == 25


def test_stated_dc_is_clamped_to_a_plausible_range_and_says_so():
    """A model that says DC 45 for a locked door is telling you about the scene's mood,
    not the door. At level 1 the range is 5..22, so 45 clamps to 22 and records it."""
    r = resolve_dc({"value": 45}, level=1)
    assert r.final == 22 and r.clamped and r.stated == 45
    assert "clamped from 45" in r.explain()


def test_a_dc_inside_the_range_is_untouched():
    """The user's own example — 'Reflex save DC 18' — must survive verbatim."""
    r = resolve_dc({"value": 18}, level=1)
    assert r.final == 18 and not r.clamped


def test_unknown_band_is_refused_rather_than_guessed():
    with pytest.raises(BadDC, match="unknown difficulty band"):
        resolve_dc({"band": "quite hard indeed"})


def test_circumstance_is_a_closed_enum_worth_exactly_two():
    """There is nowhere to put an invented +7. The vocabulary is the guard rail."""
    r = resolve_dc({"band": "tough"}, circumstance={"value": "favorable", "why": "dark"})
    assert r.final == 13
    r = resolve_dc({"band": "tough"}, circumstance="unfavorable")
    assert r.final == 17
    with pytest.raises(BadDC, match="circumstance must be"):
        resolve_dc({"band": "tough"}, circumstance={"value": "+7"})
