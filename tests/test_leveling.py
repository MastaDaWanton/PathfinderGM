"""Paths, levelling, and the class table a player plans against.

Blood Bending declares four paths — battle blood, blood spike, coagulator, blood
commander — and the abilities behind them are not in the class file. That absence is
the file's own note and it is deliberate: they are not written down anywhere in this
repository, and inventing eighty abilities and calling them somebody's homebrew is
worse than an empty branch. What is built here is the structure around the choice, so
the moment the abilities are written they grant like any other class feature.
"""
from __future__ import annotations

import pytest

from rules import creation, leveling
from rules.dice import Dice
from rules.sheet import from_dict, load_pc, to_dict


def bender(**over):
    base = {
        "name": "Path Test", "race": "half-orc", "bonus_ability": "con",
        "class": "blood bending",
        "abilities": {"str": 12, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
        "skills": [], "feats": [], "paths": ["battle blood"],
    }
    base.update(over)
    return base


# --- the four paths ------------------------------------------------------------------

def test_the_class_declares_its_own_paths():
    assert set(leveling.paths_for("blood bending")) == {
        "battle blood", "blood spike", "coagulator", "blood commander"}
    assert leveling.paths_for("fighter") == []
    assert leveling.needs_path("blood bending")
    assert not leveling.needs_path("fighter")


def test_a_bender_must_take_a_path():
    """"if you choose blood bender you have to choose a path or both paths"."""
    _, problems = creation.build(bender(paths=[]))
    assert any("follows at least one path" in p for p in problems)


def test_a_bender_may_take_more_than_one():
    built, problems = creation.build(bender(paths=["coagulator", "blood commander"]))
    assert problems == []
    assert built["sheet"]["paths"] == ["coagulator", "blood commander"]


def test_a_path_the_class_does_not_offer_is_refused():
    _, problems = creation.build(bender(paths=["blood accountant"]))
    assert any("not a path of this class" in p for p in problems)


def test_a_class_with_no_paths_may_not_carry_one():
    """A rogue with a Coagulator branch is a save that confuses everything downstream
    that reads it."""
    _, problems = creation.build(bender(**{"class": "fighter"}, paths=["coagulator"]))
    assert any("it has none" in p for p in problems)


def test_the_choice_survives_a_save():
    built, _ = creation.build(bender(paths=["blood spike"]))
    assert from_dict(to_dict(from_dict(built["sheet"]))).paths == ["blood spike"]


def test_the_forge_is_told_which_paths_a_class_offers():
    classes = {c["id"]: c for c in creation.options()["classes"]}
    assert len(classes["blood bending"]["paths"]) == 4
    assert classes["fighter"]["paths"] == []


# --- levelling -------------------------------------------------------------------------

def test_a_level_rolls_its_hit_points_rather_than_maximising_them():
    """First level takes the whole die; every level after it rolls. That is the rule
    the user's own sentence draws the contrast against — "2d8 is a roll that should be
    made to get my actual health... however lvl 1 should get Max HP"."""
    pc = load_pc("fixtures/pc-kesst.json")
    before, was = pc.hp_max, pc.level
    got = leveling.level_up(pc, dice=Dice(seed=5))
    assert got["ok"] and pc.level == was + 1
    assert 1 <= got["rolled"] <= 8              # a rogue's d8, rolled not assumed
    assert pc.hp_max == before + got["hp"]
    assert got["hp"] == max(1, got["rolled"] + got["con"])


def test_a_level_never_costs_hit_points():
    """A wretched Constitution and a low roll must not take hit points away."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.abilities["con"] = 3
    before = pc.hp_max
    got = leveling.level_up(pc, dice=Dice(seed=1))
    assert got["hp"] >= 1 and pc.hp_max > before


def test_the_twentieth_level_is_the_last():
    pc = load_pc("fixtures/pc-kesst.json")
    pc.level = leveling.MAX_LEVEL
    assert leveling.level_up(pc)["ok"] is False


def test_what_a_level_is_worth_is_read_from_the_class_not_invented():
    """A Blood Bender's second level: the class file says bonus feat, evasion and
    blood sense, and nothing here says otherwise."""
    gains = leveling.gains_at("blood bending", 2)
    assert gains["grants"] == ["bonus feat", "evasion", "blood sense 60ft"]
    assert gains["bab"] >= 0


def test_a_class_the_app_has_never_seen_is_refused_rather_than_guessed():
    pc = load_pc("fixtures/pc-kesst.json")
    pc.char_class = "chronomancer"
    assert leveling.level_up(pc)["ok"] is False


# --- the table a player plans against --------------------------------------------------

def test_the_whole_twenty_level_table_is_offered_reached_or_not():
    """"add the class tab to the full character sheet page so the player can see the
    full class and plan ahead." Planning means seeing the rows you have not reached."""
    rows = leveling.preview("blood bending", 3)
    assert len(rows) == leveling.MAX_LEVEL
    assert [r["reached"] for r in rows[:4]] == [True, True, True, False]
    assert rows[0]["grants"]


def test_columns_the_app_has_never_heard_of_still_show():
    """Blood Bending prints `fist` and `blood` on its table. Reading the row rather
    than naming the columns is what lets a class ship with its own."""
    row = leveling.preview("blood bending", 1)[2]
    assert row["columns"] == {"fist": "1d6", "blood": "1d8"}


def test_the_sheet_carries_the_progression_and_the_paths():
    from rules.sheet import full_sheet

    built, _ = creation.build(bender(paths=["coagulator"]))
    p = full_sheet(from_dict(built["sheet"]))["progression"]
    assert len(p["rows"]) == 20
    assert p["paths_taken"] == ["coagulator"]
    assert len(p["paths_offered"]) == 4
    assert p["next"]["level"] == 2


def test_the_class_tab_exists_and_draws_the_table():
    from pathlib import Path

    page = Path("play/templates/play/table.html").read_text(encoding="utf-8")
    assert '["class",     "Class",     s => tabClass(s)]' in page
    assert "function tabClass(s)" in page
    assert "The whole table" in page
    assert 'id="levelup"' in page


def test_the_page_says_plainly_that_the_paths_grant_nothing_yet():
    """The one thing this must not do is imply the branches work. They are recorded
    and displayed; they grant nothing until somebody writes them into the class file."""
    from pathlib import Path

    page = Path("play/templates/play/table.html").read_text(encoding="utf-8")
    assert "not\n          in the class file yet" in page or \
           "not" in page and "grants nothing until they are written" in page


# --- over the wire ---------------------------------------------------------------------

def test_the_level_up_endpoint_actually_works(tmp_path, settings):
    """Every test above passed while the endpoint 500'd on `c.engine.dice` — `engine`
    is a method on Campaign, not a property. Unit tests on `leveling` could not see
    that, because the mistake was in the wiring rather than in the rules."""
    import json as _json

    from django.test import Client

    from play import campaign as cm

    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    cm._LIVE.clear()
    client = Client()

    built, problems = creation.build(bender(name="Wire Test"))
    assert problems == []
    r = client.post("/api/character/create",
                    data=_json.dumps(bender(name="Wire Test", begin=True)),
                    content_type="application/json")
    assert r.status_code == 200

    was = cm.current().scene.pc().level
    r = client.post("/api/level-up")
    assert r.status_code == 200, r.content[:200]
    got = r.json()["levelled"]
    assert got["level"] == was + 1
    assert got["rolled"] >= 1
    assert cm.current().scene.pc().level == was + 1


def test_levelling_is_refused_at_twenty_over_the_wire(tmp_path, settings):
    import json as _json

    from django.test import Client

    from play import campaign as cm

    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    cm._LIVE.clear()
    client = Client()
    client.post("/api/character/create",
                data=_json.dumps(bender(name="Capped", begin=True)),
                content_type="application/json")
    c = cm.current()
    c.scene.pc().level = leveling.MAX_LEVEL
    c.save()

    r = client.post("/api/level-up")
    assert r.status_code == 409
    assert "20th level" in r.json()["error"]
