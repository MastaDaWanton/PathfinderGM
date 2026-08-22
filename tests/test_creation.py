"""Guided creation: the rules decide, and a refusal names the number.

The output contract is the whole design: a made character is exactly the dict a pregen
file holds, loaded through the same `from_dict`, enrolled through the same roster. If
anything downstream could tell them apart, creation would be a second character system
to keep level with the first.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from rules import creation
from rules.sheet import from_dict


def spec(**over):
    base = {
        "name": "Durga Stonebrow", "race": "dwarf", "class": "fighter",
        "abilities": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 8},
        "skills": ["climb", "intimidate"],
        "feats": ["power attack", "weapon focus"],
    }
    base.update(over)
    return base


# --- the numbers -------------------------------------------------------------------------

def test_a_legal_character_builds_and_loads():
    built, problems = creation.build(spec())
    assert problems == []
    actor = from_dict(built["sheet"])
    assert actor.name == "Durga Stonebrow"
    assert actor.hp == 10 + 1 + 2      # max d10, +Con 16 after the dwarf's +2... 13


def test_racial_modifiers_are_baked_into_the_scores():
    built, _ = creation.build(spec())
    ab = built["sheet"]["abilities"]
    assert ab["con"] == 16 and ab["wis"] == 14 and ab["cha"] == 6


def test_the_point_budget_is_a_wall():
    _, problems = creation.build(spec(abilities={
        "str": 18, "dex": 18, "con": 18, "int": 10, "wis": 10, "cha": 10}))
    assert any("points" in p for p in problems)


def test_scores_run_seven_to_eighteen_before_race():
    _, problems = creation.build(spec(abilities={
        "str": 19, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}))
    assert any("7 to 18" in p for p in problems)


def test_a_human_must_say_where_their_bonus_goes():
    """+2 anywhere is a choice, and silently picking for the player is choosing their
    character."""
    _, problems = creation.build(spec(race="human"))
    assert any("say which ability" in p for p in problems)
    built, problems = creation.build(spec(race="human", bonus_ability="str"))
    assert problems == []
    assert built["sheet"]["abilities"]["str"] == 18


def test_skill_ranks_are_counted_and_named():
    _, problems = creation.build(spec(skills=["climb", "intimidate", "swim"]))
    assert any("ranks" in p for p in problems)
    _, problems = creation.build(spec(skills=["basketweaving"]))
    assert any("not a skill" in p for p in problems)


def test_a_human_fighter_gets_three_feats_and_a_dwarf_one_fewer():
    """One for everyone, one for a human, one for a fighter — the budget is stated in
    the refusal so the player learns the rule from being refused."""
    _, problems = creation.build(spec(
        feats=["power attack", "weapon focus", "toughness"]))
    assert any("feats against 2" in p for p in problems)
    built, problems = creation.build(spec(
        race="human", bonus_ability="str",
        feats=["power attack", "weapon focus", "toughness"]))
    assert problems == []


def test_spells_known_are_capped_by_the_class():
    _, problems = creation.build(spec(
        race="human", bonus_ability="cha", **{"class": "sorcerer"},
        skills=["bluff", "spellcraft"], feats=["toughness", "dodge"],
        spellbook=["magic-missile", "shield", "grease"]))
    assert any("against 2 known" in p for p in problems)


def test_a_non_caster_picks_no_spells():
    _, problems = creation.build(spec(spellbook=["magic-missile"]))
    assert any("picks no spells" in p for p in problems)


def test_a_spell_off_the_class_list_is_refused():
    _, problems = creation.build(spec(
        race="human", bonus_ability="cha", **{"class": "sorcerer"},
        skills=["bluff", "spellcraft"], feats=["toughness", "dodge"],
        spellbook=["cure-light-wounds"]))
    assert any("not a level 0-1 sorcerer spell" in p for p in problems)


def test_all_the_problems_arrive_at_once():
    """A wizard nobody finishes is a wizard built one error per submit."""
    _, problems = creation.build({"name": "", "race": "orc", "class": "ninja"})
    assert len(problems) >= 3


def test_every_kit_survives_the_sheet_validator():
    """The kits name gear from the small core tables because `equipped` is refused
    outside them. This walks all eleven through `from_dict`, so a kit naming unknown
    gear is a failing test rather than a corrupt character on disk."""
    for cid in creation.KITS:
        built, problems = creation.build({
            "name": f"Kit test {cid}", "race": "elf", "class": cid,
            "abilities": {"str": 14, "dex": 14, "con": 12, "int": 10,
                          "wis": 10, "cha": 10},
            "skills": [], "feats": [],
        })
        assert problems == [], (cid, problems)
        from_dict(built["sheet"])


# --- through the wire -----------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    return Client()


def test_the_wizard_draws_from_one_payload(client):
    d = client.get("/api/create/options").json()
    assert len(d["races"]) == 7
    assert {c["id"] for c in d["classes"]} >= {"barbarian", "monk", "sorcerer"}
    assert d["point_budget"] == 20
    assert "stealth" in d["skills"]


def test_creating_over_the_wire_lands_on_the_roster(client):
    r = client.post("/api/character/create", data=json.dumps(spec()),
                    content_type="application/json")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] and d["id"] == "durga-stonebrow"

    from play import roster
    entry = roster.load(d["id"])
    assert entry is not None
    assert entry.sheet["class"] == "fighter"
    assert entry.sheet["abilities"]["con"] == 16


def test_a_broken_character_reports_every_problem(client):
    r = client.post("/api/character/create",
                    data=json.dumps({"name": "", "race": "x", "class": "y"}),
                    content_type="application/json")
    assert r.status_code == 400
    assert len(r.json()["problems"]) >= 3


# --- the roster stops multiplying (found in use, 2026-08-22) ---------------------------

def test_an_abandoned_start_is_retired_when_the_next_game_begins(tmp_path):
    """Seven identical "Kesst Vayr · Rogue 1 · 9/9 hp" rows accumulated in one afternoon
    of playtesting, and a roster nobody can read is a roster nobody uses.

    The first fix tried was recycling the entry inside `enrol` — and
    `test_two_characters_of_the_same_name_do_not_collide` caught it immediately, which
    is the test doing its job: two characters who merely share a name must never
    overwrite each other, however empty one of them looks. So the narrower rule stands
    instead, and it is the one this module already applies to the character a reset
    replaces: a start with no turns in it is retired, not deleted and not reused.
    """
    from django.test import override_settings

    from play import campaign as cm, roster
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        first = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        assert roster.load(first.character_id).status == roster.ALIVE

        second = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        assert roster.load(first.character_id).status == roster.RETIRED
        living = [e for e in roster.everyone() if e.status == roster.ALIVE]
        assert [e.id for e in living] == [second.character_id]


def test_a_character_who_played_is_never_retired_behind_your_back(tmp_path):
    """The dead and the played stay on the roster: they are the reason the next game
    went the way it did. Only an empty start is swept up."""
    from django.test import override_settings

    from play import campaign as cm, roster
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        first = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        played = roster.load(first.character_id)
        played.turns_played = 12
        roster.save(played)

        cm.begin_with(load_pc("fixtures/pc-borin.json"))
        assert roster.load(first.character_id).status == roster.ALIVE


def test_the_forge_is_reachable_from_the_shelf_and_from_a_world():
    """Creation shipped and stayed behind one button on the roster tab, while a world's
    own "Start something new" still said full creation was "the next piece" — the exact
    drift this page's module docstring warns about."""
    from pathlib import Path

    page = Path("play/templates/play/home.html").read_text(encoding="utf-8")
    assert page.count("data-forge") >= 3, "shelf, world and roster each need a door"
    assert "next piece; until it lands" not in page
    # And the forge outranks the tab, so it can open from any of them.
    assert "FORGE ? paneForge()\n    : TAB === \"worlds\"" in page
