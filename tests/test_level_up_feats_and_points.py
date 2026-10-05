"""A level owes feats and ability points by the book, and the table's house rule adds more.

Measured on master before this (2026-10-04): `rules/leveling.py level_up` rolled hit
points, grew the class's own `ability_growth` and resized the pools — and nothing in the
app appended to `actor.feats` or raised a score after the forge. The Core Rulebook's feat
at every odd level, its +1 to one score at 4th, 8th, 12th, 16th and 20th, and a fighter's
bonus feats (2, 4, 6…) were granted nowhere: a level-5 fighter had taken 1 feat since
creation's — none — against four owed.

And the Class tab printed "nothing new" under 47 levels of the core classes (wizard 15,
cleric 10, sorcerer 9, druid 8, bard 3, paladin 1, ranger 1), because a row showed only
the class's `grants`. The owner: "there are a bunch of levels that say you gain nothing
but there are no level where you gain nothing."

The house rule, in the owner's words: "1 extra feat and 2 ability points every level,
every odd level, or every even level separate the pickers for feats and the ability
points so i can assign feats to odd levels and ability points to even if I want."
"""
from __future__ import annotations

import json

import pytest

from rules import classes as classes_mod, creation, houserules, leveling
from rules import xp as xp_mod
from rules.sheet import from_dict, to_dict

CORE = ("barbarian", "bard", "cleric", "druid", "fighter", "monk", "paladin", "ranger",
        "rogue", "sorcerer", "wizard")


def forge(cls="fighter", feats=None, **over):
    body = {
        "name": "Owed Test", "race": "dwarf", "class": cls, "gender": "woman",
        "abilities": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 8},
        "skills": ["climb", "intimidate"],
        "feats": feats if feats is not None else
        ["power attack", {"id": "weapon-focus", "target": "longsword"}],
    }
    body.update(over)
    built, problems = creation.build(body)
    assert problems == [], problems
    return from_dict(built["sheet"], ref="pc")


def levelled(actor, to: int):
    while actor.level < to:
        actor.xp = xp_mod.total_for(actor.level + 1)
        got = leveling.level_up(actor)
        assert got["ok"], got
    return actor


# --- by the book ------------------------------------------------------------------------

def test_a_fifth_level_fighter_is_owed_two_feats_two_bonus_feats_and_a_point():
    """A level-5 fighter had taken 1 feat since creation's — none — and level-up granted
    none. By the book: general feats at 3 and 5, bonus feats at 2 and 4, +1 at 4."""
    pc = levelled(forge(), 5)
    due = leveling.owed(pc)
    assert [p["for_level"] for p in due["feats"]["picks"]] == [3, 5]
    assert [p["for_level"] for p in due["bonus"]["picks"]] == [2, 4]
    assert due["bonus"]["rule"] == "a combat feat"
    assert due["points"]["owed"] == 1 and due["points"]["picks"][0]["for_level"] == 4
    assert due["total"] == 5


def test_a_new_character_owes_nothing_the_forge_already_gave():
    """Level 1's feat and a fighter's 1st-level bonus feat are the forge's budget."""
    assert leveling.owed(forge())["total"] == 0


def test_the_level_up_line_says_what_is_left_to_choose():
    pc = levelled(forge(), 3)
    pc.xp = xp_mod.total_for(4)
    got = leveling.level_up(pc)
    said = " ".join(got["grants"])
    assert "feat" in said and "ability point" in said, got["grants"]
    assert got["picks_owed"]["total"] == 4      # feat (3), bonus (2, 4), point (4)


def test_taking_feats_counts_them_and_refuses_what_the_rule_forbids():
    """Checked in order against the character with the earlier picks taken, so a feat
    and the feat it opens may be chosen together; refused whole, with the fix named."""
    pc = levelled(forge(), 5)
    assert any("already has Power Attack" in p
               for p in leveling.feat_problems(pc, ["power-attack"], "feats"))
    bad = leveling.feat_problems(pc, ["toughness"], "bonus")
    assert bad and "not a combat feat" in bad[0], bad
    alone = leveling.feat_problems(pc, ["great-cleave"], "feats")
    assert alone and "Cleave" in alone[0], alone
    assert pc.feats == ["power attack", "weapon focus (longsword)"], (
        "a refused check left a feat behind")
    added, problems = leveling.take_feats(pc, ["cleave", "great-cleave"], "feats")
    assert problems == [] and added == ["cleave", "great cleave"]
    assert pc.level_feats_taken == 2 and leveling.owed(pc)["feats"]["owed"] == 0
    added, problems = leveling.take_feats(pc, ["dodge"], "feats")
    assert added == [] and "no feats owed" in problems[0]


def test_toughness_taken_later_carries_current_hit_points_with_the_maximum():
    pc = levelled(forge(), 3)
    pc.hp = pc.hp_max
    before = pc.hp_max
    leveling.take_feats(pc, ["toughness"], "feats")
    assert pc.hp_max > before and pc.hp == pc.hp_max


def test_a_level_carries_current_hit_points_with_a_feat_that_scales_with_hit_dice():
    """Measured live 2026-10-04: a fighter with Toughness reached 4th level at 43 of 44 —
    Toughness's +1 for the fourth Hit Die went onto the maximum and never onto the hit
    points she had, because the level added only the roll."""
    pc = forge(feats=["power attack", "toughness"])
    pc = levelled(pc, 3)
    pc.hp = pc.hp_max
    pc.xp = xp_mod.total_for(4)
    leveling.level_up(pc)
    assert pc.hp == pc.hp_max


def test_the_level_up_click_keeps_the_page_on_the_games_revision():
    """Measured live: after Take level 4, the first feat chosen was refused with
    "Another device moved the game on" — the level-up fetch bumped the revision and the
    page never noted it, so its next write went in stale."""
    from pagesource import table_source

    page = table_source()
    at = page.index('fetch("/api/level-up"')
    assert "noteRevision(r)" in page[at:at + 600]


def test_a_constitution_point_pays_every_hit_die_already_earned():
    """Through `Actor.grow_ability`, the one door a base score goes up by — a bare
    `+=` cannot reach 1e's retroactive Constitution rule."""
    pc = forge(abilities={"str": 16, "dex": 14, "con": 13, "int": 10, "wis": 12,
                          "cha": 8})
    pc = levelled(pc, 4)
    assert pc.abilities["con"] == 15             # dwarf +2
    changes, problems = leveling.take_points(pc, {"con": 1})
    assert problems == [] and changes[0]["hp_change"] == 4
    assert pc.ability_points_taken == 1
    assert leveling.take_points(pc, {"con": 1})[1], "a second point was not owed"


def test_points_refuse_what_is_not_owed_or_not_a_score():
    pc = levelled(forge(), 4)
    assert "against 1 owed" in " ".join(leveling.point_problems(pc, {"str": 2}))
    assert "not an ability" in " ".join(leveling.point_problems(pc, {"luck": 1}))
    assert leveling.point_problems(pc, "str")


def test_the_counters_round_trip_and_an_older_save_reads_them_as_none_taken():
    """Written only when set, the spell counter's rule: a save from before reads back
    byte for byte, and absent is zero — nothing granted a feat after creation before."""
    fresh = forge()
    assert not {"level_feats_taken", "bonus_feats_taken",
                "ability_points_taken"} & set(to_dict(fresh))
    pc = levelled(forge(), 4)
    leveling.take_feats(pc, ["dodge"], "bonus")
    leveling.take_points(pc, {"str": 1})
    again = from_dict(json.loads(json.dumps(to_dict(pc))), ref="pc")
    assert (again.bonus_feats_taken, again.ability_points_taken) == (1, 1)
    assert leveling.owed(again)["bonus"]["owed"] == 1


def test_bonus_feats_are_read_off_the_class_table_not_its_name():
    """A wizard's 5th-level bonus feat is metamagic, item creation or Spell Mastery; a
    monk's ignores prerequisites. Both were inert strings on the table before."""
    w = forge("wizard", feats=["toughness"], skills=["appraise"],
              abilities={"str": 10, "dex": 14, "con": 14, "int": 16, "wis": 12, "cha": 8},
              spellbook=["mage-armor", "magic-missile", "shield"])
    w = levelled(w, 5)
    assert leveling.owed(w)["bonus"]["owed"] == 1
    assert leveling.feat_problems(w, ["dodge"], "bonus")
    assert leveling.feat_problems(w, ["empower-spell"], "bonus") == []
    m = forge("monk", feats=["dodge"], skills=["climb"])
    m = levelled(m, 2)
    assert leveling.feat_problems(m, ["power-attack"], "bonus")
    assert leveling.feat_problems(m, ["deflect-arrows"], "bonus") == []


# --- "nothing new" retired -------------------------------------------------------------

def test_no_level_of_a_core_class_reads_nothing_new():
    """47 rows read "nothing new" across wizard 15, cleric 10, sorcerer 9, druid 8,
    bard 3, paladin 1 and ranger 1 — every one of them raises a save, a base attack, a
    slot or owes a feat. Each row now says what it gives; none may be empty."""
    empty = [(cid, row["level"]) for cid in CORE
             for row in leveling.preview(cid, 1, rules={"bonus_feats": "off",
                                                        "bonus_ability_points": "off"})
             if not row["gains"]]
    assert empty == []


def test_a_row_names_base_attack_saves_slots_feats_and_points():
    """Wizard 4 printed "nothing new"; it is base attack +1, Will +1, +1 to a score, a
    1st- and a 2nd-level slot and two spells for the book."""
    row = leveling.gains_at("wizard", 4, {"bonus_feats": "off",
                                          "bonus_ability_points": "off"})["said"]
    assert "base attack +1" in row and "Will +1" in row
    assert "+1 to an ability score" in row
    assert any("2nd-level" in g for g in row) and "2 spells for the spellbook" in row
    assert "a feat" in leveling.gains_at("cleric", 3)["said"]
    assert any(g.startswith("rage +") for g in leveling.gains_at("barbarian", 2)["said"])


def test_the_page_prints_gains_and_never_nothing_new():
    from pagesource import table_source

    page = table_source()
    assert '|| "nothing new"' not in page
    assert "r.gains" in page and "owedPicksBlock(s)" in page
    assert "/api/level/feats/take" in page and "/api/level/points" in page


# --- the house rule ---------------------------------------------------------------------

@pytest.fixture
def isolated(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    return tmp_path


def test_the_two_settings_are_separate_and_only_named_rhythms_are_accepted(isolated):
    rules, problems = houserules.set_active({"bonus_feats": "odd",
                                             "bonus_ability_points": "even"})
    assert problems == []
    assert (houserules.bonus_feats(), houserules.bonus_ability_points()) == ("odd", "even")
    rules, problems = houserules.set_active({"bonus_feats": "thrice"})
    assert problems and "'thrice'" in problems[0]
    assert rules["bonus_feats"] == "odd"


def test_feats_on_odd_and_points_on_even_land_where_the_owner_put_them(isolated):
    """The owner's own example: feats to odd levels, ability points to even. A fighter
    taken from 1 to 4 under it owes, on top of the book's: house feats at 3 (1 was the
    forge's), house points at 2 and 4."""
    houserules.set_active({"bonus_feats": "odd", "bonus_ability_points": "even"})
    pc = forge(feats=["power attack", {"id": "weapon-focus", "target": "longsword"},
                      "toughness"])
    assert pc.level_feats_taken == 1, "the forge's house feat was counted as taken"
    pc = levelled(pc, 4)
    due = leveling.owed(pc)
    assert [(p["for_level"], p["source"]) for p in due["feats"]["picks"]] == \
        [(3, "book"), (3, "house")]
    assert [(p["for_level"], p["source"], p["points"]) for p in due["points"]["picks"]] \
        == [(2, "house", 2), (4, "book", 1), (4, "house", 2)]
    assert due["points"]["owed"] == 5
    # Both house points on one score is allowed; the counter takes them oldest first.
    changes, problems = leveling.take_points(pc, {"str": 2})
    assert problems == [] and changes[0]["amount"] == 2
    assert [p["for_level"] for p in leveling.owed(pc)["points"]["picks"]] == [4, 4]


def test_level_one_counts_and_the_forge_offers_it(isolated):
    """Decided with the rule: level 1 is odd, so "every" and "odd" grant in the forge —
    one more feat in the budget and two ability points after the race."""
    houserules.set_active({"bonus_feats": "every", "bonus_ability_points": "odd"})
    assert creation.options()["level_one"] == {"feats": 1, "points": 2}
    three = ["power attack", {"id": "weapon-focus", "target": "longsword"}, "toughness",
             "dodge"]
    built, problems = creation.build({
        "name": "House Test", "race": "dwarf", "class": "fighter", "gender": "woman",
        "abilities": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 8},
        "skills": ["climb", "intimidate"], "feats": three,
        "house_points": {"str": 2}})
    assert "4 feats against 3" in " ".join(problems), problems
    built, problems = creation.build({
        "name": "House Test", "race": "dwarf", "class": "fighter", "gender": "woman",
        "abilities": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 8},
        "skills": ["climb", "intimidate"], "feats": three[:3],
        "house_points": {"str": 2}})
    assert problems == [], problems
    sheet = built["sheet"]
    assert sheet["abilities"]["str"] == 18 and sheet["ability_points_taken"] == 2
    built, problems = creation.build({
        "name": "House Test", "race": "dwarf", "class": "fighter", "gender": "woman",
        "abilities": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 8},
        "skills": ["climb", "intimidate"], "feats": three[:3],
        "house_points": {"str": 3}})
    assert "3 house-rule ability points against 2" in " ".join(problems)


def test_the_house_rule_off_refuses_house_points_in_the_forge(isolated):
    _, problems = creation.build({
        "name": "Book Test", "race": "dwarf", "class": "fighter", "gender": "woman",
        "abilities": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 8},
        "skills": ["climb"], "feats": ["power attack"], "house_points": {"str": 1}})
    assert "grants none at 1st level" in " ".join(problems)


def test_a_character_made_before_the_rule_is_offered_its_first_level_share(isolated):
    pc = forge()
    houserules.set_active({"bonus_feats": "odd"})
    assert leveling.owed(pc)["feats"]["picks"] == [{"for_level": 1, "source": "house"}]


def test_the_rows_label_the_house_rule(isolated):
    houserules.set_active({"bonus_feats": "odd", "bonus_ability_points": "even"})
    rows = leveling.preview("fighter", 4)
    assert "1 extra feat (house rule)" in rows[2]["gains"]
    assert "2 ability points (house rule)" in rows[3]["gains"]
    assert not any("house rule" in g for g in rows[1]["gains"] if "feat" in g)


# --- over the wire, the way the Class tab asks -----------------------------------------

@pytest.fixture
def fighter_table(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path)
    from play import campaign as campaign_mod

    pc = levelled(forge(), 3)
    return campaign_mod.begin_with(pc)


def _post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def test_the_class_tab_offers_and_takes_owed_feats_and_points(client, fighter_table):
    sheet = client.get("/api/sheet").json()
    owed = sheet["progression"]["owed"]
    assert owed["feats"]["owed"] == 1 and owed["bonus"]["owed"] == 1
    menu = client.get("/api/level/feats?pool=bonus").json()
    assert menu["open"] and all("combat" in [t.lower() for t in f["types"]]
                                for f in menu["open"])
    assert "power-attack" not in {f["id"] for f in menu["open"]}, "a held feat was offered"
    res = _post(client, "/api/level/feats/take", {"pool": "bonus", "feats": ["dodge"]})
    assert res.status_code == 200, res.json()
    assert res.json()["progression"]["owed"]["bonus"]["owed"] == 0
    res = _post(client, "/api/level/feats/take", {"pool": "feats", "feats": "dodge"})
    assert res.status_code == 400 and "list" in res.json()["error"]
    res = _post(client, "/api/level/points", {"points": {"str": 1}})
    assert res.status_code == 400 and "no ability points owed" in res.json()["error"]


def test_the_guest_may_take_owed_picks():
    from pathfindergm import lan

    assert lan.guest_may("POST", "/api/level/feats/take")
    assert lan.guest_may("POST", "/api/level/points")
