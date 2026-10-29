"""The Core Rulebook's NPC classes, and people built from them with every number computed.

Measured 2026-10-28, before this: no NPC class existed. A guard, a teamster or a farmer was
either a hand-written block of typed totals (`bestiary.TEMPLATES`' watchman: `flat_attack`
2, `flat_ac` 15, `hp` 11 — nobody's derivation) or an adventure's printed block, and the
owner's direction is to ship neither but our own, built from the rules (docs/bestiary-
licensing.md option D; docs/compiled-bestiary-plan.md). The adept's spell list was on 0 of
the corpus's 3,040 spells.

The numbers below are the book's, read 2026-10-28 from CRB Chapter 14 (Tables 14-1 to 14-6,
pp. 448-451) and Chapter 12 ("Adding NPCs", p. 398).
"""
from __future__ import annotations

import pytest

from rules import casting, classbuilder, classes, npc_builds, spells
from rules.sheet import from_dict


def _npc(cls: str, level: int, **extra):
    data = {"name": f"{cls} {level}", "kind": "npc", "class": cls, "level": level,
            "abilities": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            "hp": 10, "hp_max": 10}
    data.update(extra)
    return from_dict(data)


def _save(actor, which: str) -> int:
    return sum(m.value for m in actor.save_modifiers(which))


# --- the five documents ---------------------------------------------------------------------

def test_the_five_npc_classes_load_and_validate():
    assert sorted(classes.npc_classes()) == ["adept", "aristocrat", "commoner", "expert",
                                             "warrior"]
    for cid, doc in classes.npc_classes().items():
        assert classbuilder.validate_class(dict(doc)) == [], cid


def test_no_player_can_be_a_commoner():
    """The forge, the Class tab and the "build every class" tests iterate `all_classes()`;
    an NPC class is reached only through `get`, as the animal companion's is."""
    assert not set(classes.npc_classes()) & set(classes.all_classes())
    assert classes.get("warrior")["bab"] == "full"


@pytest.mark.parametrize("cid, level, bab, fort, ref, will", [
    # Tables 14-1 to 14-5, rows read off the page.
    ("adept", 1, 0, 0, 0, 2), ("adept", 12, 6, 4, 4, 8),
    ("aristocrat", 4, 3, 1, 1, 4), ("aristocrat", 20, 15, 6, 6, 12),
    ("commoner", 1, 0, 0, 0, 0), ("commoner", 20, 10, 6, 6, 6),
    ("expert", 8, 6, 2, 2, 6), ("expert", 15, 11, 5, 5, 9),
    ("warrior", 1, 1, 2, 0, 0), ("warrior", 16, 16, 10, 5, 5),
])
def test_base_attack_and_saves_are_the_printed_tables(cid, level, bab, fort, ref, will):
    a = _npc(cid, level)
    assert a.bab == bab
    assert (_save(a, "fort"), _save(a, "ref"), _save(a, "will")) == (fort, ref, will)


def test_a_commoner_is_proficient_with_the_one_weapon_he_picked():
    """"The commoner is proficient with one simple weapon. He is not proficient with any
    other weapons, nor is he proficient with any type of armor or shield" (p. 449)."""
    pick = {"weapon proficiency": {"option": "class option",
                                   "picks": [{"pick": "club", "level": 1}]}}
    farmer = _npc("commoner", 1, class_choices=pick)
    assert farmer.is_proficient("club")
    assert not farmer.is_proficient("dagger") and not farmer.is_proficient("longsword")


def test_an_expert_names_his_ten_class_skills():
    """"The expert can choose any 10 skills to be class skills" (p. 450). The class-option
    validator capped a choice at five picks; ten is the book's."""
    picks = ["appraise", "craft", "diplomacy", "heal", "knowledge-local", "perception",
             "profession", "sense-motive", "bluff", "linguistics"]
    sage = _npc("expert", 2, class_choices={"class skills": {
        "option": "class option", "picks": [{"pick": p, "level": 1} for p in picks]}})
    assert set(sage.class_skills) == {"appraise", "craft", "diplomacy", "heal",
                                      "knowledge (local)", "perception", "profession",
                                      "sense motive", "bluff", "linguistics"}


def test_the_adept_casts_off_its_own_list_by_table_14_1():
    """0 of 3,040 spells named the adept's list; the class prints it (p. 449), declares it,
    and the spell loader writes it into each spell's `lists`: 67 spells, levels 0-5. A 4th
    level adept with Wis 15 has 3/3/1 — the printed 0 at 2nd is bonus spells only."""
    assert spells.class_list_misses() == []
    on = [s for s in spells.all_spells().values() if "adept" in (s.lists or {})]
    assert len(on) == 67
    assert spells.all_spells()["cure-light-wounds"].lists["adept"] == 1
    hedge = _npc("adept", 4, abilities={"str": 10, "dex": 8, "con": 12, "int": 9,
                                        "wis": 15, "cha": 11})
    assert casting.slots_for(hedge) == {0: 3, 1: 3, 2: 1}
    # "a Wisdom score equal to at least 10 + the spell level" (p. 448): Wis 11 casts the
    # printed 2 at 1st and no bonus; Wis 10 casts nothing above 0.
    plain = dict(hedge.abilities, wis=11)
    assert casting.slots_for(_npc("adept", 4, abilities=plain)) == {0: 3, 1: 2}
    assert casting.slots_for(_npc("adept", 4)) == {0: 3}


# --- a person built, every number derived ------------------------------------------------------

TEAMSTER = {"id": "caravan-teamster", "name": "caravan teamster", "race": "human",
            "class": "commoner", "level": 1, "abilities": {"preset": "skill"},
            "racial_choices": ["str"], "skills": ["handle animal", "profession", "perception"],
            "feats": ["Toughness", "Skill Focus (Handle Animal)"],
            "class_choices": {"weapon proficiency": {
                "option": "class option", "picks": [{"pick": "club", "level": 1}]}},
            "weapons": ["club"], "equipped": "club", "armour": "padded"}
GUARD = {"id": "town-guard", "name": "town guard", "race": "human", "class": "warrior",
         "level": 2, "abilities": {"preset": "melee"}, "racial_choices": ["str"],
         "skills": ["intimidate", "perception"], "feats": ["Power Attack", "Toughness"],
         "weapons": ["longsword", "light-crossbow"], "equipped": "longsword",
         "armour": "scale mail", "shield": "heavy shield"}


def test_a_teamster_built_from_the_rules():
    """Hand-checked: skill preset 10/12/11/13/8/9, +2 Str for a human; hp 3 (a d6's average,
    Step 7) + 0 Con + 3 Toughness = 6; AC 10 + 1 Dex + 1 padded = 12; +1 with the club;
    CR 1/3 (commoner 1, "class levels –2", p. 398)."""
    assert npc_builds.check(TEAMSTER) == []
    a = npc_builds.actor(TEAMSTER)
    assert a.abilities == {"str": 12, "dex": 12, "con": 11, "int": 13, "wis": 8, "cha": 9}
    assert (a.hp_max, a.ac(), sum(m.value for m in a.attack_modifiers("club"))) == (6, 12, 1)
    assert npc_builds.build(TEAMSTER)[0]["cr"] == "1/3"


def test_a_town_guard_built_from_the_rules():
    """Melee preset 13/11/12/9/10/8, +2 Str; hp 11 (2 x 5.5) + 2 Con + 3 Toughness = 16;
    AC 10 + 5 scale + 2 heavy shield = 17; BAB 2 + Str 2 = +4; Fort 3 + 1 = +4; CR 1/2."""
    assert npc_builds.check(GUARD) == []
    a = npc_builds.actor(GUARD)
    assert (a.hp_max, a.ac(), a.bab) == (16, 17, 2)
    assert sum(m.value for m in a.attack_modifiers("longsword")) == 4
    assert _save(a, "fort") == 4
    assert npc_builds.build(GUARD)[0]["cr"] == "1/2"


@pytest.mark.parametrize("level, npc_class, cr", [
    (1, True, "1/3"), (2, True, "1/2"), (3, True, "1"), (8, True, "6"),
    (1, False, "1/2"), (2, False, "1"), (5, False, "4")])
def test_the_cr_of_class_levels_is_the_books(level, npc_class, cr):
    assert npc_builds.challenge(level, npc_class) == cr


@pytest.mark.parametrize("change, says", [
    ({"skills": ["intimidate", "perception", "climb"]}, "Table 14-8"),
    ({"feats": ["Toughness"]}, "1 taken, 2 owed"),
    ({"class": "baker"}, "no class"),
    ({"level": 4, "increases": []}, "every four levels"),
])
def test_a_build_that_breaks_a_rule_is_refused_with_the_fix(change, says):
    problems = npc_builds.check(dict(GUARD, **change))
    assert problems and any(says in p for p in problems), problems


def test_a_feat_whose_prerequisite_is_missing_is_refused():
    assert npc_builds.check(dict(GUARD, feats=["Cleave", "Toughness"])) == [
        "feats: Cleave — Power Attack."]


def test_a_weapon_the_class_does_not_grant_is_refused():
    farmer = dict(TEAMSTER, weapons=["longsword"], equipped="longsword")
    assert any("not proficient with the longsword" in p for p in npc_builds.check(farmer))
