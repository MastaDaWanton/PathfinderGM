"""The druid's nature bond: a domain from seven, or an animal companion that grows.

Reported by the owner, 2026-10-04: "The druid class does not work I was given no choice
for my natures bond and I dont think we have domains or animal bonds set up yet to make
the natures bond work." Measured on master that day: `content/classes/druid.json` carried
"nature bond" as a bare string, `rules/domains.py` answered every class but the cleric
with "takes no domains", no domain had a single granted power, and nothing anywhere could
make an animal companion — the sheet printed "No animal companion, familiar, cohort or
mount" as a fixed sentence.

Book numbers below are the Core Rulebook's (d20pfsrd, read 2026-10-04).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.test import override_settings

from rules import animal_companion as ac
from rules import casting, classbuilder, classes, creation, domains
from rules.sheet import from_dict, to_dict
from rules.tables import bab_for, save_for

BASE = {"name": "Fern", "race": "human", "bonus_ability": "wis", "class": "druid",
        "pronouns": "she/her", "skills": [], "feats": [],
        "abilities": {"str": 10, "dex": 12, "con": 12, "int": 10, "wis": 16, "cha": 10}}
WOLF = {"nature bond": {"option": "animal companion", "pick": "wolf"}}


def _druid(**extra):
    built, problems = creation.build({**BASE, **extra})
    assert problems == [], problems
    return from_dict(built["sheet"], ref="pc")


class _Scene:
    """Just enough scene for the companion door: a store and the arrival door."""

    def __init__(self, *actors):
        self.people = {a.ref: a for a in actors}
        self.minted = 0

    def add(self, actor, zone=None):
        self.people[actor.ref] = actor
        return actor


@pytest.fixture
def scene_with_wolf(monkeypatch):
    from rules import bestiary

    monkeypatch.setattr(bestiary, "next_ref", lambda scene, taken=(): "c9")
    druid = _druid(class_choices=WOLF)
    sc = _Scene(druid)
    wolf = ac.arrive_with(sc, druid)
    return sc, druid, wolf


# --- the choice itself ---------------------------------------------------------------------

def test_a_druid_made_with_no_natures_bond_is_refused_with_the_fix_named():
    """The defect: a druid was made with no nature's bond choice at all — the forge asked
    nothing and the build said nothing."""
    _, problems = creation.build(dict(BASE))
    assert problems == ["A druid chooses Nature's Bond at 1st level: a cleric domain or "
                        "an animal companion. Pick one in the class step."]


def test_the_domain_bond_is_one_of_the_seven_and_only_one():
    assert _druid(domains=["Air"]).domains == ["Air"]
    _, problems = creation.build({**BASE, "domains": ["Healing"]})
    assert problems == ["Healing is not one of a druid's domains: Air, Animal, Earth, "
                        "Fire, Plant, Water, Weather."]
    _, problems = creation.build({**BASE, "domains": ["Air", "Fire"]})
    assert problems == ["A druid takes 1 domain; that is 2."]


def test_the_two_bonds_are_one_or_the_other():
    _, problems = creation.build({**BASE, "domains": ["Air"], "class_choices": WOLF})
    assert problems == ["A druid takes a domain only through nature bond; take the "
                        "domain option there, or send no domains."]
    _, problems = creation.build({**BASE, "class_choices": {
        "nature bond": {"option": "animal companion", "pick": "dragon"}}})
    assert problems and "not on a druid's companion list" in problems[0]
    _, problems = creation.build({**BASE, "class_choices": {
        "nature bond": {"option": "animal companion"}}})
    assert problems and "needs an animal" in problems[0]


def test_the_answer_is_saved_on_the_sheet_and_survives_a_round_trip():
    druid = _druid(class_choices={"nature bond": {"option": "animal companion",
                                                  "pick": "Tiger", "name": "Ash"}})
    assert druid.class_choices == {"nature bond": {"option": "animal companion",
                                                   "pick": "big cat", "name": "Ash"}}
    assert from_dict(to_dict(druid), ref="pc").class_choices == druid.class_choices
    # A domain sent with no answer IS the domain bond, and is recorded as such.
    assert _druid(domains=["Air"]).class_choices == {"nature bond": {"option": "domain"}}
    # Written only when set: every older save, and every class that asks nothing, still
    # round-trips byte for byte.
    built, _ = creation.build({**BASE, "class": "fighter", "domains": []})
    assert "class_choices" not in to_dict(from_dict(built["sheet"], ref="pc"))


def test_a_cleric_still_takes_two_and_says_so_from_her_document():
    """`if cid != "cleric"` was the whole rule. Now the cleric's document declares one
    option — two domains from every one there is — and the code names no class."""
    _, problems = creation.build({**BASE, "class": "cleric"})
    assert problems == ["A cleric takes 2 domains; that is 0."]
    assert domains.rule_for("cleric")["how_many"] == 2
    assert domains.rule_for("cleric")["from"] is None
    assert domains.rule_for("druid", {"nature bond": {"option": "domain"}})["from"] == [
        "Air", "Animal", "Earth", "Fire", "Plant", "Water", "Weather"]
    assert domains.rule_for("druid", WOLF) is None
    import re

    code = re.sub(r'"""(?:.|\n)*?"""', "", Path("rules/domains.py").read_text(
        encoding="utf-8"))
    code = "\n".join(line.split("#")[0] for line in code.splitlines())
    assert '"cleric"' not in code and "'cleric'" not in code


def test_every_shipped_class_choice_validates_and_a_bad_one_names_its_fix():
    for cid, cls in classes.all_classes().items():
        assert classes.validate_choices(cls) == [], cid
    bad = {"choices": [{"id": "nature bond", "level": 1, "options": [
        {"kind": "domain", "from": ["Air", "Starlight"]},
        {"kind": "animal companion", "from": ["wolf", "griffon"]},
        {"kind": "bloodline"}]}]}
    found = classes.validate_choices(bad)
    assert any("no domain called 'Starlight'" in p for p in found)
    assert any("no companion animal called 'griffon'" in p for p in found)
    assert any("'bloodline' has no reader" in p for p in found)
    # And the bench refuses the class with the same words.
    assert any("Starlight" in p for p in classbuilder.validate_class(
        {**classes.get("druid"), **bad}))


def test_the_forge_is_offered_the_choice_from_the_document():
    druid = next(c for c in creation.options()["classes"] if c["id"] == "druid")
    (bond,) = druid["choices"]
    kinds = {o["kind"]: o for o in bond["options"]}
    assert [d["name"] for d in kinds["domain"]["domains"]] == [
        "Air", "Animal", "Earth", "Fire", "Plant", "Water", "Weather"]
    assert any("Lightning Arc" in p for p in kinds["domain"]["domains"][0]["powers"])
    assert len(kinds["animal companion"]["animals"]) == 16


# --- the domain bond -------------------------------------------------------------------------

def test_a_druids_domain_gives_its_slot_and_its_powers():
    """"The druid's effective cleric level is equal to her druid level" (Nature Bond)."""
    druid = _druid(domains=["Air"])
    assert casting.domain_slots_for(druid) == {1: 1}
    arc = druid.pools["lightning arc"]
    assert arc.maximum == 3 + druid.ability_mod("wis") and arc.refresh == "rest.night"
    assert druid.resistance("electricity") == 0          # Electricity Resistance is 6th
    druid.level = 6
    assert druid.resistance("electricity") == 10
    druid.level = 12
    assert druid.resistance("electricity") == 20
    druid.level = 20
    assert druid.immune_to("electricity")
    # Read live off the domain list: take the domain away and the power is gone.
    druid.domains = []
    assert not druid.immune_to("electricity")


def test_the_power_documents_validate_and_cover_the_seven():
    assert domains.validate_powers() == []
    assert set(domains.documented()) >= {"Air", "Animal", "Earth", "Fire", "Plant",
                                         "Water", "Weather"}
    junk = {"domains": {"Air": {"powers": [{"key": "zap", "level": 30, "pool": {},
                                            "cost": {"pool": "other"}, "colour": "blue"}]}}}
    found = domains.validate_powers(junk)
    assert any("unknown field(s) colour" in p for p in found)
    assert any(".level: the class level" in p for p in found)
    assert any(".cost: spends its own pool" in p for p in found)
    # Every power that cannot be fired by the engine yet says so in its own words.
    for d in domains.documented():
        for p in domains.powers_of(d):
            if p.get("pool"):
                assert p.get("not_yet"), (d, p["name"])


# --- the animal companion ---------------------------------------------------------------------

def test_the_companion_table_is_three_quarter_bab_and_good_fort_ref_at_its_hit_dice():
    """Why the companion's numbers can be a class progression read at its Hit Dice: the
    book's BAB and save columns ARE that derivation, row for row. If a transcription slip
    ever broke one row, this names it."""
    book = {1: (1, 3, 0), 2: (2, 3, 1), 3: (2, 3, 1), 4: (3, 4, 1), 5: (3, 4, 1),
            6: (4, 5, 2), 7: (4, 5, 2), 8: (5, 5, 2), 9: (6, 6, 2), 10: (6, 6, 3),
            11: (6, 6, 3), 12: (7, 7, 3), 13: (8, 7, 3), 14: (9, 8, 4), 15: (9, 8, 4),
            16: (9, 8, 4), 17: (10, 9, 4), 18: (11, 9, 5), 19: (11, 9, 5),
            20: (12, 10, 5)}
    for edl, (bab, good, poor) in book.items():
        hd = ac.row(edl)["hd"]
        assert (bab_for("three_quarter", hd), save_for(True, hd), save_for(False, hd)) \
            == (bab, good, poor), edl


def test_a_first_level_druids_wolf_has_the_books_numbers(scene_with_wolf):
    sc, druid, wolf = scene_with_wolf
    assert wolf.ref in sc.people and wolf.name == "wolf"
    assert (wolf.level, wolf.size, wolf.bab) == (2, "medium", 1)
    assert [sum(m.value for m in wolf.save_modifiers(s)) for s in ("fort", "ref", "will")] \
        == [5, 5, 1]                     # +3/+3/+0 base, Con 15, Dex 15, Wis 12
    assert wolf.ac() == 14               # 10 + 2 natural + 2 Dex
    assert wolf.hp == wolf.hp_max == 9 + 2 * 2   # 4.5 x 2 HD, +2 Con per HD
    assert wolf.weapon("bite")["damage"] == "1d6"
    assert wolf.is_proficient("bite")


def test_the_wolf_grows_with_its_druid_and_nothing_is_written_by_hand(scene_with_wolf):
    """7th-level advancement: "Size Large; AC +2 natural armor; Attack bite (1d8 plus
    trip); Ability Scores Str +8, Dex -2, Con +4" — on top of the table's +4 natural armour
    and +2 Str/Dex at druid 7."""
    sc, druid, wolf = scene_with_wolf
    druid.level = 7
    assert ac.sync(sc) == ["wolf grows with Fern: 6 Hit Dice now."]
    assert (wolf.level, wolf.size, wolf.bab) == (6, "large", 4)
    assert wolf.ability_score("str") == 13 + 2 + 8 and wolf.ability_score("dex") == 15
    assert wolf.ac() == 10 + (2 + 2 + 4) + 2 - 1        # natural, Dex, Large
    assert wolf.weapon("bite")["damage"] == "1d8"
    assert wolf.has_state("class.evasion") and not wolf.has_state("class.improved-evasion")
    druid.level = 15
    ac.sync(sc)
    assert wolf.has_state("class.improved-evasion")


def test_a_wounded_companion_keeps_its_wounds_when_it_grows(scene_with_wolf):
    sc, druid, wolf = scene_with_wolf
    wolf.hp -= 4
    druid.level = 3
    ac.sync(sc)
    assert wolf.hp == wolf.hp_max - 4


def test_removing_the_bond_removes_every_number_it_gave(scene_with_wolf):
    """Law 2: the Str/Dex bonus rides the bond effect, so it goes with it."""
    sc, druid, wolf = scene_with_wolf
    druid.level = 3
    ac.sync(sc)
    assert wolf.ability_score("str") == 14
    wolf.remove_effects(kind="bond", source=f"companion:{druid.ref}")
    assert wolf.ability_score("str") == 13
    assert not ac.is_animal_companion(wolf)


def test_the_companion_travels_and_hears_orders_as_an_animal(scene_with_wolf):
    """The owner's ruling, 2026-10-01: companions take spoken orders as their character
    dictates. An animal's character is tricks and tone, not an attitude step and a trade."""
    from gm import companions
    from rules import states

    sc, druid, wolf = scene_with_wolf
    assert wolf.has_state(states.TRAVELS_WITH_YOU) and companions.is_companion(wolf)
    words = companions.who_they_are(sc, wolf)
    assert "Fern's animal companion" in words and "attack" in words
    assert "indifferent" not in words


def test_a_companion_survives_a_save_and_load(scene_with_wolf):
    sc, druid, wolf = scene_with_wolf
    back = from_dict(json.loads(json.dumps(to_dict(wolf))), ref=wolf.ref)
    assert back.weapon("bite")["damage"] == "1d6" and back.ac() == wolf.ac()
    assert ac.master_ref(back) == druid.ref and back.race == ""


def test_the_companion_document_names_only_animals_it_can_build():
    druid = classes.get("druid")
    (option,) = [o for o in druid["choices"][0]["options"]
                 if o["kind"] == "animal companion"]
    for key in option["from"]:
        b = ac.body(key, 1)
        assert b["attacks"], key
        for attack in b["attacks"]:
            assert attack["damage"].get(b["size"]), (key, attack["key"], b["size"])
        adv = ac.animals()[key].get("advances") or {}
        if adv:
            later = ac.body(key, int(adv["at"]))
            for attack in later["attacks"]:
                assert attack["damage"].get(later["size"]), (key, attack["key"])


def test_a_druid_with_a_wolf_begins_with_the_wolf_beside_her(tmp_path):
    """End to end through the door the player clicks: build, begin, save, load."""
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        c = cm.begin_with(_druid(class_choices=WOLF))
        pc = c.scene.pc()
        (wolf,) = ac.companions_of(c.scene, pc)
        assert wolf.at == pc.at
        path = c.save()
        back = cm.Campaign.load(path)
        (again,) = ac.companions_of(back.scene, back.scene.pc())
        assert again.weapon("bite")["damage"] == "1d6"
        assert ac.sheet_lines(back.scene, back.scene.pc())[0]["hd"] == 2
        cm._LIVE.clear()


def test_a_druid_begun_from_the_outfitting_page_brings_her_wolf_too(tmp_path):
    """The door the player actually clicks. The first live run put the companion's
    arrival in `begin_with` alone; the forge's "Create & outfit" parks the character on
    the roster and the outfitting page's Begin starts the game through `switch_to`, and
    the sheet came back saying "it is not here"."""
    from play import campaign as cm
    from play import roster

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        entry = roster.enrol(_druid(class_choices=WOLF))
        c = cm.switch_to(entry.id)
        pc = c.scene.pc()
        (wolf,) = ac.companions_of(c.scene, pc)
        assert wolf.at == pc.at and ac.wanted_but_absent(c.scene, pc) == ""
        cm._LIVE.clear()


# --- the class tables, against the book ------------------------------------------------------

def _grants(cid, level):
    return classes.table_at(cid, level).get("grants") or []


def test_the_class_tables_match_the_core_rulebook_where_they_did_not():
    """Measured 2026-10-04 against the d20pfsrd class tables: the druid's elementals came
    at 8th and plants at 10th (the book: 6th and 8th) and no row after 4th said how many
    wild shapes a day; the paladin had no divine bond; the ranger's 13th was a combat
    style feat (the book: 3rd favoured terrain) and 10th/14th/18th had none; the bard's
    inspire courage ran a step late from 5th and versatile performance stopped at 2nd;
    the monk had no 1st-level bonus feat and no slow fall at 12th."""
    assert any("elemental" in g for g in _grants("druid", 6))
    assert any("plant" in g for g in _grants("druid", 8))
    for lvl, n in ((6, 2), (8, 3), (10, 4), (12, 5), (14, 6), (16, 7), (18, 8)):
        assert f"wild shape {n}/day" in _grants("druid", lvl), lvl
    assert "divine bond" in _grants("paladin", 5)
    assert _grants("ranger", 13) == ["favored terrain (3rd)"]
    for lvl in (2, 6, 10, 14, 18):
        assert "combat style feat" in _grants("ranger", lvl), lvl
    for lvl, bonus in ((1, 1), (5, 2), (11, 3), (17, 4)):
        assert f"inspire courage +{bonus}" in _grants("bard", lvl), lvl
    for lvl in (2, 6, 10, 14, 18):
        assert "versatile performance" in _grants("bard", lvl), lvl
    assert "bonus feat" in _grants("monk", 1)
    assert "slow fall 60 ft" in _grants("monk", 12)
