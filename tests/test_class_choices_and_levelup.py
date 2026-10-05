"""Class choices at any level, skill ranks at every level, and the bonus-feat plumbing.

Measured by the class audit (docs/class-audit.md, 2026-10-05) against master 1f88ada:

- D1: no skill rank was owed, offered or placeable after 1st level. "A 20th-level human
  barbarian in these runs has the 5 ranks she was made with. The book gives her 100."
- A: 19 choices could not be made. The forge refused "'bloodline' is not a choice a
  sorcerer makes; it makes none." and nothing wrote `class_choices` after creation, so
  rage powers, rogue talents, mercies, favored enemies, the wizard's school and bond and
  the ranger's whole kit had no picker anywhere.
- D2: "Ranger combat style feats: 0 owed at 2/6/10/14/18. Sorcerer bloodline feats: 0 owed
  at 7/13/19."
- D3: "Fighter with Toughness, Iron Will and Great Fortitude: 200. Monk with Toughness:
  200."
- D4: "Monk L1 feats: the three chosen, with no Improved Unarmed Strike and no Stunning
  Fist. Wizard: no Scribe Scroll. Ranger: no Endurance at 3."
- D5: "A 3rd-level wizard took Extra Rage Power: 200."
- D6: "Druid 7 with a wolf: EDL 1, 2 HD, 13 hp live. After dropping the cached campaign:
  EDL 7, 6 HD, 51 hp."
- D8: "One path at creation; at 11 nothing is offered."
"""
from __future__ import annotations

import json

import pytest

from rules import classes, creation, feats, leveling
from rules import xp as xp_mod
from rules.sheet import from_dict, to_dict

ABILITIES = {"str": 14, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 12}


def forge(cls, race="human", **over):
    body = {"name": "Choice Test", "race": race, "class": cls, "gender": "woman",
            "abilities": dict(ABILITIES), "choices": ["str"] if race == "human" else [],
            "skills": ["perception"], "feats": [],
            "domains": creation.starter_domains(cls),
            "spellbook": creation.starter_spells(cls, 1)}
    body.update(over)
    built, problems = creation.build(body)
    assert problems == [], problems
    return from_dict(built["sheet"], ref="pc")


def refused(cls, race="human", **over):
    body = {"name": "Choice Test", "race": race, "class": cls, "gender": "woman",
            "abilities": dict(ABILITIES), "choices": ["str"] if race == "human" else [],
            "skills": ["perception"], "feats": [],
            "domains": creation.starter_domains(cls),
            "spellbook": creation.starter_spells(cls, 1)}
    body.update(over)
    built, problems = creation.build(body)
    return " ".join(problems)


def levelled(actor, to: int):
    while actor.level < to:
        actor.xp = xp_mod.total_for(actor.level + 1)
        got = leveling.level_up(actor)
        assert got["ok"], got
    return actor


# --- D1: skill ranks ------------------------------------------------------------------

def test_a_twentieth_level_barbarian_is_owed_the_books_hundred_ranks():
    """A 20th-level barbarian had 5 skill ranks; the book gives 100 — (4 class + 0 Int)
    + 1 human, at every one of 20 levels."""
    pc = forge("barbarian", abilities={**ABILITIES, "int": 10}, skills=[])
    assert leveling.skill_ranks(pc)["owed"] == 5
    levelled(pc, 20)
    due = leveling.skill_ranks(pc)
    assert (due["per_level"], due["total"], due["owed"]) == (5, 100, 100)
    said = " ".join(leveling.owed_lines(leveling.owed(pc)))
    assert "100 skill ranks to place" in said


def test_ranks_are_placed_and_no_skill_holds_more_than_the_level():
    pc = levelled(forge("rogue"), 4)
    placed, problems = leveling.take_ranks(pc, {"perception": 4})
    assert placed == {} and "no skill holds more than your level (4)" in problems[0]
    placed, problems = leveling.take_ranks(pc, {"perception": 3, "stealth": 4})
    assert problems == [] and pc.ranks["perception"] == 4 and pc.ranks["stealth"] == 4
    placed, problems = leveling.take_ranks(pc, {"dancing": 1})
    assert "'dancing' is not a skill" in problems[0]


def test_a_raised_intelligence_pays_its_ranks_for_every_level_already_taken():
    """Pathfinder dropped 3.5's "not retroactive": a permanent Int increase is worth a
    rank at every level already taken (d20pfsrd, Ability Scores, fetched 2026-10-05).
    A wizard with Int 13 (+1) raised to 14 (+2) at 4th is owed 4 more ranks at once."""
    pc = forge("wizard", race="dwarf", abilities={**ABILITIES, "int": 13, "cha": 10})
    levelled(pc, 4)
    before = leveling.skill_ranks(pc)["owed"]
    changes, problems = leveling.take_points(pc, {"int": 1})
    assert problems == []
    assert leveling.skill_ranks(pc)["owed"] == before + 4


# --- A: class choices -----------------------------------------------------------------

def test_bloodline_is_a_choice_a_sorcerer_makes():
    """The forge used to refuse it by name: "'bloodline' is not a choice a sorcerer
    makes; it makes none." Now it is stored, with its dragon, and readable by lane 2."""
    pc = forge("sorcerer", class_choices={"bloodline": {"pick": "draconic",
                                                          "variant": "red"}})
    got = classes.chosen(pc, "bloodline")
    assert [(p["id"], p["variant"]) for p in got] == [("draconic", "red")]
    assert got[0]["entry"]["class_skill"] == "perception"
    assert "skill-focus" in got[0]["entry"]["bonus_feats"]
    assert from_dict(to_dict(pc)).class_choices == pc.class_choices
    assert "needs a dragon type" in refused("sorcerer", class_choices={
        "bloodline": {"pick": "draconic"}})
    assert "is not one of the choices" in refused("sorcerer", class_choices={
        "bloodline": {"pick": "vampiric"}})


def test_a_choice_left_at_the_forge_waits_on_the_sheet():
    """No PF1 builder blocks a character for an unmade choice (docs/class-audit.md §5);
    it is owed until made. The druid's bond is the exception kept: it decides spells."""
    pc = forge("sorcerer")
    rows = leveling.owed(pc)["choices"]["picks"]
    assert [(r["choice"], r["for_level"]) for r in rows] == [("bloodline", 1)]
    taken, problems = classes.take_choice(pc, "bloodline", {"picks": [
        {"pick": "elemental", "variant": "fire"}]})
    assert problems == [] and taken == ["Elemental (fire)"]
    assert leveling.owed(pc)["choices"]["owed"] == 0


def test_rage_powers_are_owed_at_even_levels_and_judged_by_level_and_prerequisite():
    pc = levelled(forge("barbarian"), 6)
    rows = leveling.owed(pc)["choices"]["picks"]
    assert [r["for_level"] for r in rows] == [2, 4, 6]
    _, problems = classes.take_choice(pc, "rage power", {"picks": ["terrifying-howl"]})
    assert "open from 8th level" in problems[0]
    _, problems = classes.take_choice(pc, "rage power", {"picks": ["renewed-vigor"] * 2})
    assert "already chosen Renewed Vigor" in problems[0]
    taken, problems = classes.take_choice(pc, "rage power",
                                          {"picks": ["intimidating-glare", "scent"]})
    assert problems == [] and len(taken) == 2
    levelled(pc, 8)
    # Two 8th-level powers for the 6th- and 8th-level picks: only one fits.
    _, problems = classes.take_choice(pc, "rage power",
                                      {"picks": ["terrifying-howl", "clear-mind"]})
    assert "open from 8th level; this pick is the one for level 6" in problems[0]
    taken, problems = classes.take_choice(pc, "rage power",
                                          {"picks": ["terrifying-howl", "animal-fury"]})
    assert problems == [], problems
    _, problems = classes.take_choice(pc, "rage power", {"picks": ["knockback"]})
    assert "nothing is owed" in problems[0]
    assert classes.chosen_ids(pc, "rage power") == [
        "intimidating-glare", "scent", "terrifying-howl", "animal-fury"]


def test_rogue_advanced_talents_open_at_tenth_in_place_of_a_talent():
    pc = levelled(forge("rogue"), 10)
    picks = ["fast-stealth", "ledge-walker", "minor-magic", "trap-spotter", "opportunist"]
    _, problems = classes.take_choice(pc, "rogue talent", {"picks": picks})
    assert problems == [], problems
    pc2 = levelled(forge("rogue"), 8)
    _, problems = classes.take_choice(pc2, "rogue talent", {"picks": ["opportunist"]})
    assert "open from 10th level" in problems[0]
    _, problems = classes.take_choice(pc2, "rogue talent", {"picks": ["major-magic"]})
    assert "requires Minor Magic" in problems[0]


def test_a_wizard_specialist_names_two_other_schools_and_a_universalist_none():
    pc = forge("wizard", class_choices={"arcane school": {"pick": "evocation"},
                                        "opposition schools": {"picks": ["necromancy",
                                                                         "enchantment"]},
                                        "arcane bond": {"pick": "bonded-object",
                                                        "variant": "staff"}})
    assert classes.chosen_ids(pc, "opposition schools") == ["necromancy", "enchantment"]
    assert leveling.owed(pc)["choices"]["owed"] == 0
    assert "already your arcane school" in refused("wizard", class_choices={
        "arcane school": {"pick": "evocation"},
        "opposition schools": {"picks": ["evocation", "necromancy"]}})
    uni = forge("wizard", class_choices={"arcane school": {"pick": "universalist"}})
    assert [r["choice"] for r in leveling.owed(uni)["choices"]["picks"]] == ["arcane bond"]


def test_a_ranger_raises_a_favored_enemy_he_has_including_the_new_one():
    pc = forge("ranger", class_choices={"favored enemy": {"pick": "humanoid-orc"}})
    levelled(pc, 5)
    rows = [r["choice"] for r in leveling.owed(pc)["choices"]["picks"]]
    assert rows.count("favored enemy") == 1 and "favored enemy bonus" in rows
    assert classes.take_choice(pc, "favored enemy", {"picks": ["undead"]})[1] == []
    _, problems = classes.take_choice(pc, "favored enemy bonus", {"picks": ["dragon"]})
    assert "is not one of the choices" in problems[0]
    assert classes.take_choice(pc, "favored enemy bonus", {"picks": ["undead"]})[1] == []
    assert classes.chosen_ids(pc, "favored enemy") == ["humanoid-orc", "undead"]
    assert classes.chosen(pc, "favored enemy bonus")[0]["name"] == "Undead"
    # The raise is written onto the pick it raises (`sync_raises`), the shape lane 3's
    # reader takes: without it every enemy read +2, though the book lets the player
    # choose which one rises.
    stored = {p["pick"]: p["bonus"] for p in pc.class_choices["favored enemy"]["picks"]}
    assert stored == {"humanoid-orc": 2, "undead": 4}
    assert [p["bonus"] for p in classes.chosen(pc, "favored enemy")] == [2, 4]


# --- D2: the bonus-feat pools the table names otherwise ----------------------------------

def test_a_ranger_is_owed_combat_style_feats_from_his_style_with_prerequisites_waived():
    """0 owed at 2/6/10/14/18 before. Rapid Shot needs Point Blank Shot and Dex 13; the
    ranger's style waives both, and only his style's list is open."""
    pc = levelled(forge("ranger", abilities={**ABILITIES, "dex": 12}), 6)
    due = leveling.owed(pc)["bonus"]
    assert [p["for_level"] for p in due["picks"]] == [2, 6]
    assert "Choose your combat style first" in leveling.feat_problems(
        pc, ["rapid-shot"], "bonus")[0]
    assert classes.take_choice(pc, "combat style", {"picks": ["archery"]})[1] == []
    assert "not a feat of your combat style" in " ".join(
        leveling.feat_problems(pc, ["power-attack"], "bonus"))
    added, problems = leveling.take_feats(pc, ["rapid-shot", "manyshot"], "bonus")
    assert problems == [], problems
    menu = leveling.feat_menu(pc, "bonus")
    assert menu["owed"] == 0


def test_a_sorcerer_is_owed_bloodline_feats_at_seven_thirteen_and_nineteen():
    pc = forge("sorcerer", class_choices={"bloodline": {"pick": "draconic",
                                                          "variant": "red"}})
    levelled(pc, 13)
    assert [p["for_level"] for p in leveling.owed(pc)["bonus"]["picks"]] == [7, 13]
    assert "not one of your bloodline's" in " ".join(
        leveling.feat_problems(pc, ["dodge"], "bonus"))
    assert leveling.take_feats(pc, ["toughness", "blind-fight"], "bonus")[1] == []


# --- D3, D4: the 1st-level bonus feat and the feats a class grants ------------------------

def test_the_forge_holds_a_fighters_first_bonus_feat_to_combat_feats():
    """Toughness, Iron Will and Great Fortitude were accepted as a human fighter's three
    1st-level feats (200); one of them is the bonus feat, and none is a combat feat."""
    said = refused("fighter", feats=["toughness", "iron-will", "great-fortitude"])
    assert "1st-level bonus feat must be a combat feat" in said
    forge("fighter", feats=["toughness", "iron-will", "power-attack"])


def test_a_monks_bonus_feat_waives_its_prerequisites_at_the_forge_too():
    """Improved Grapple needs Dex 13; the book waives it for a monk's bonus feat, as the
    level-up already did. Toughness as the bonus feat is refused."""
    pc = forge("monk", race="dwarf", abilities={**ABILITIES, "dex": 12, "wis": 14,
                                                 "cha": 8},
               feats=["toughness", "improved-grapple"])
    assert "improved grapple" in pc.feats
    assert "monk's bonus feats" in refused("monk", race="dwarf", feats=["toughness",
                                                                        "iron-will"])


def test_the_feats_a_class_grants_are_on_the_sheet():
    monk = forge("monk")
    assert {"improved unarmed strike", "stunning fist"} <= set(monk.feats)
    assert "scribe scroll" in forge("wizard").feats
    assert "eschew materials" in forge("sorcerer").feats
    ranger = forge("ranger")
    assert "endurance" not in ranger.feats
    assert "endurance" in levelled(ranger, 3).feats
    assert "comes with the monk class" in refused("monk", feats=["stunning-fist"])
    # Idempotent: a load or a second call adds nothing twice.
    assert leveling.grant_class_feats(monk) == []


# --- D5: class features as prerequisites ------------------------------------------------

def test_a_wizard_cannot_take_extra_rage_power():
    """A 3rd-level wizard took Extra Rage Power with 200; 201 feats answered "unknown"."""
    wizard = levelled(forge("wizard"), 3)
    verdict = feats.meets(wizard, feats.get("extra-rage-power"))
    assert verdict["unmet"] == ["Rage power class feature"]
    assert feats.meets(levelled(forge("barbarian"), 2), "extra-rage-power")["ok"]
    assert feats.meets(forge("barbarian"), "extra-rage-power")["unmet"]
    assert classes.has_feature(forge("cleric"), "Channel positive energy class feature")
    assert classes.has_feature(wizard, "You have no levels in a class that has the grit "
                                       "class feature") is None


# --- D8: the second path ----------------------------------------------------------------

def test_a_blood_bender_may_take_path_b_once_the_track_opens():
    cid = "blood bending"
    path = leveling.paths_for(cid)[0]
    pc = forge(cid, paths=[path])
    levelled(pc, 10)
    assert not leveling.owed(pc)["paths"]["open"]
    assert "opens at 11th" in leveling.take_path(pc, leveling.paths_for(cid)[1])[1][0]
    levelled(pc, 11)
    offer = leveling.owed(pc)["paths"]
    assert offer["open"] and path not in offer["offered"]
    got, problems = leveling.take_path(pc, offer["offered"][0])
    assert problems == [] and pc.paths == [path, got]
    assert not leveling.owed(pc)["paths"]["open"]


# --- the documents ----------------------------------------------------------------------

def test_every_class_choices_block_and_catalogue_validates():
    for cid in classes.all_classes():
        assert classes.validate_choices(classes.get(cid)) == [], cid
    assert len(classes.catalogues()) >= 11
    for name, cat in classes.catalogues().items():
        assert classes.validate_catalogue(cat) == [], name
    # Every feat a style or a bloodline names is a feat the corpus has, or the pool it
    # feeds would offer nothing for it.
    for cat in classes.catalogues().values():
        for e in cat["options"]:
            got = e.get("bonus_feats") or []
            for names in (got.values() if isinstance(got, dict) else [got]):
                for fid in names:
                    feats.get(fid)


# --- over the wire: the forge, the Class tab, and every class 1 to 20 ---------------------

def _post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


@pytest.fixture
def isolated(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    return tmp_path


def _create(client, cls, **over):
    body = {"name": f"Climb {cls}", "race": "human", "class": cls, "gender": "woman",
            "abilities": dict(ABILITIES), "choices": ["int"], "skills": ["perception"],
            "feats": [], "domains": creation.starter_domains(cls),
            "spellbook": creation.starter_spells(cls, 1), "begin": True}
    if leveling.paths_for(cls):
        body["paths"] = leveling.paths_for(cls)[:1]
    if cls == "druid":
        body["domains"] = []
        body["class_choices"] = {"nature bond": {"option": "animal companion",
                                                 "pick": "wolf"}}
    if cls == "monk":
        body["feats"] = ["dodge"]
    body.update(over)
    res = _post(client, "/api/character/create", body)
    assert res.status_code == 200, res.json()


def _settle(client):
    """Take every pick the levels owe through the real endpoints, the way the Class tab
    does, until nothing is outstanding. Returns the sheet."""
    from play import campaign as campaign_mod

    for _ in range(60):
        sheet = client.get("/api/sheet").json()
        o = sheet["progression"]["owed"]
        if o["choices"]["owed"]:
            row = o["choices"]["picks"][0]
            menu = client.get(f"/api/level/choices?choice={row['choice']}").json()
            n = sum(1 for r in o["choices"]["picks"] if r["choice"] == row["choice"])
            opt = menu["options"][-1]
            body = {"choice": row["choice"], "option": opt["key"]}
            if opt["kind"] == "class option":
                open_ = [e for e in opt["entries"] if e["open"]][:1]
                body["picks"] = [{"pick": e["id"], "variant": (e["variants"] or [""])[0]}
                                 for e in open_]
            elif opt["kind"] == "animal companion":
                body["pick"] = opt["animals"][0]["key"]
            elif opt["kind"] == "domain":
                body["domains"] = opt["domains"][:1]
            res = _post(client, "/api/level/choose", body)
            assert res.status_code == 200, (row, res.json())
            assert n >= 1
            continue
        if o["bonus"]["owed"] or o["feats"]["owed"]:
            pool = "bonus" if o["bonus"]["owed"] else "feats"
            menu = client.get(f"/api/level/feats?pool={pool}").json()
            pick = next(f for f in menu["open"] if not f["target"])
            res = _post(client, "/api/level/feats/take", {"pool": pool, "feats": [pick["id"]]})
            assert res.status_code == 200, res.json()
            continue
        if o["points"]["owed"]:
            res = _post(client, "/api/level/points", {"points": {"int": o["points"]["owed"]}})
            assert res.status_code == 200, res.json()
            continue
        if o["skills"]["owed"]:
            left, spread = o["skills"]["owed"], {}
            for k in sorted(o["skills"]["skills"], key=lambda k: not k["class_skill"]):
                take = min(left, k["room"])
                if take:
                    spread[k["name"]] = take
                    left -= take
                if not left:
                    break
            res = _post(client, "/api/level/skills", {"ranks": spread})
            assert res.status_code == 200, res.json()
            continue
        due = (sheet.get("spells") or {}).get("to_learn") or {}
        if due.get("owed"):
            got = client.get("/api/spells/learnable").json()
            want, ids = due["owed"], []
            for row in got["spells"]:
                if len(ids) >= want:
                    break
                ids.append(row["id"])
            res = _post(client, "/api/spells/learn", {"spells": ids[:1]})
            assert res.status_code == 200, res.json()
            continue
        return sheet
    raise AssertionError("the picks never settled")


CHOOSERS = {
    # class: {choice id: picks made by 20th level}
    "barbarian": {"rage power": 10}, "bard": {"versatile performance": 5},
    "fighter": {"weapon training": 4}, "rogue": {"rogue talent": 10},
    "paladin": {"mercy": 6, "divine bond": 1}, "sorcerer": {"bloodline": 1},
    "wizard": {"arcane school": 1, "arcane bond": 1},
    "ranger": {"favored enemy": 5, "favored enemy bonus": 4, "combat style": 1,
               "favored terrain": 4, "favored terrain bonus": 3, "hunter's bond": 1},
}


@pytest.mark.parametrize("cls", sorted(CHOOSERS) + ["cleric", "druid", "monk",
                                                     "blood bending"])
def test_every_class_climbs_one_to_twenty_through_the_endpoints(client, isolated, cls):
    """The audit's 1→20 harness, re-run with choices and skill ranks taken through the
    real endpoints. Before: 0 ranks placed after 1st in all 36 runs; 19 choices with no
    picker anywhere."""
    from play import campaign as campaign_mod

    _create(client, cls)
    for level in range(2, 21):
        c = campaign_mod.current()
        pc = c.scene.pc()
        pc.xp = xp_mod.total_for(level)
        c.save()
        res = client.post("/api/level-up")
        assert res.status_code == 200, res.json()
        _settle(client)
    pc = campaign_mod.current().scene.pc()
    due = leveling.skill_ranks(pc)
    assert pc.level == 20 and due["owed"] == 0 and due["spent"] == due["total"]
    assert leveling.owed(pc)["outstanding"] == 0
    for cid, n in CHOOSERS.get(cls, {}).items():
        assert len(classes.chosen(pc, cid)) == n, (cid, classes.chosen(pc, cid))


def test_the_level_up_grows_the_companion_without_a_reload(client, isolated):
    """D6: the wolf stayed at 2 HD from druid 1 to 7 until a reload."""
    from play import campaign as campaign_mod
    from rules import animal_companion

    _create(client, "druid")
    c = campaign_mod.current()
    druid = c.scene.pc()
    wolf = animal_companion.companions_of(c.scene, druid)[0]
    hd = wolf.level
    for level in range(2, 8):
        c = campaign_mod.current()
        c.scene.pc().xp = xp_mod.total_for(level)
        c.save()
        assert client.post("/api/level-up").status_code == 200
    c = campaign_mod.current()
    wolf = animal_companion.companions_of(c.scene, c.scene.pc())[0]
    assert wolf.level > hd
    assert any("grows with" in t.get("text", "") for t in c.transcript)


def test_a_paladins_mount_arrives_when_the_bond_is_chosen(client, isolated):
    from play import campaign as campaign_mod
    from rules import animal_companion

    _create(client, "paladin")
    c = campaign_mod.current()
    c.scene.pc().xp = xp_mod.total_for(5)
    c.scene.pc().level = 4
    c.save()
    assert client.post("/api/level-up").status_code == 200
    res = _post(client, "/api/level/choose", {"choice": "divine bond", "option": "mount",
                                              "pick": "horse", "name": "Bramble"})
    assert res.status_code == 200, res.json()
    c = campaign_mod.current()
    assert [a.name for a in animal_companion.companions_of(c.scene, c.scene.pc())] \
        == ["Bramble"]


def test_the_page_draws_the_new_pickers_and_the_guest_may_use_them():
    from pagesource import table_source
    from pathfindergm import lan

    page = table_source()
    for url in ("/api/level/skills", "/api/level/choose", "/api/level/path",
                "/api/level/choices"):
        assert url in page, url
        assert lan.guest_may("POST", url) or url == "/api/level/choices"
