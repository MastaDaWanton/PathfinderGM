"""A level's Hit Dice as the dice they are, Constitution on each, and the favoured class bonus.

Measured on the owner's report of 2026-11-01 (their homebrew class, not in the report; the
class here is synthetic, built the same way): a class declaring `"hit_die": "4d8"` — four
Hit Dice a level — rolled ONE d32 at level-up (`max_hit_die` read the notation as its top),
and each level added Constitution once, while the sheet itemised "Con × 8 HD": the level
code cancelled the other three Hit Dice's share (`hp_base += hp - con * hit_dice_per_level`).
The forge did the same at 1st: Constitution once, whatever the dice.

And the favoured class bonus (CRB p.31, "Favored Class": "Whenever a character gains a
level in his favored class, he receives either +1 hit point or +1 skill rank") was given to
built NPCs (rules/npc_builds.py, the owner's ruling of 2026-10-30) and to no player at all.
"""
from __future__ import annotations

import pytest

from rules import classes as classes_mod, creation, leveling
from rules.dice import Dice
from rules.sheet import from_dict, to_dict


@pytest.fixture
def quad(monkeypatch):
    """A synthetic four-Hit-Dice-a-level class: the fighter's table, `"4d8"` dice."""
    every = dict(classes_mod.all_classes())
    cls = dict(every["fighter"], id="quadmancer", name="Quadmancer", hit_die="4d8",
               hit_dice_per_level=4)
    every["quadmancer"] = cls
    monkeypatch.setattr(classes_mod, "_ALL", every)
    return cls


def _forge(favoured="hp", con=14):
    built, problems = creation.build({
        "name": "Quad", "race": "human", "bonus_ability": "str", "class": "quadmancer",
        "pronouns": "he/him",
        "abilities": {"str": 14, "dex": 12, "con": con, "int": 10, "wis": 10, "cha": 10},
        "skills": [], "feats": [], "paths": [], "favoured_bonus": favoured})
    assert problems == [], problems
    return from_dict(built["sheet"], ref="pc")


def _earned(pc):
    from rules import xp

    pc.xp = xp.total_for(int(pc.level) + 1)


def test_first_level_maximises_every_die_and_adds_con_to_each(quad):
    """4d8 maxed is 32, and Con 14 (+2) on each of the four Hit Dice is 8 — 40, plus the
    favoured class's hit point. Before: 32 + 2 = 34 + nothing."""
    pc = _forge()
    assert pc.hit_dice == 4
    assert pc.hp_max == 32 + 2 * 4 + 1 == pc.hp
    terms = {m.source: m.value for m in pc.hp_max_modifiers()}
    assert terms == {"rolled hit points": 32, "Con × 4 HD": 8, "favoured class": 1}


def test_a_level_rolls_four_d8s_and_con_on_each(quad):
    """Measured: one d32 and Constitution once. Now four d8s, each with Constitution."""
    pc = _forge()
    _earned(pc)
    before, base_before = pc.hp_max, pc.hp_base
    got = leveling.level_up(pc, dice=Dice(seed=11), favoured="hp")
    assert got["ok"]
    assert got["hit_dice"] == "4d8" and len(got["faces"]) == 4
    assert all(1 <= f <= 8 for f in got["faces"])
    assert got["rolled"] == sum(got["faces"])
    assert got["hp"] == sum(max(1, f + 2) for f in got["faces"]) + 1
    assert pc.hp_max == before + got["hp"]
    # The store holds the dice alone; Constitution is derived on all eight Hit Dice.
    assert pc.hp_base == base_before + sum(got["faces"])
    terms = {m.source: m.value for m in pc.hp_max_modifiers()}
    assert terms["Con × 8 HD"] == 16 and terms["favoured class"] == 2
    # And the record survives a save.
    assert from_dict(to_dict(pc), ref="pc").hp_max == pc.hp_max


def test_a_shipped_two_hd_class_takes_con_twice_a_level():
    """Blood Bending, 2d8 a level: Con on both dice, from the forge on."""
    built, problems = creation.build({
        "name": "Bender", "race": "half-orc", "bonus_ability": "con",
        "class": "blood bending", "pronouns": "she/her",
        "abilities": {"str": 12, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
        "skills": [], "feats": [], "paths": ["battle blood"]})
    assert problems == [], problems
    pc = from_dict(built["sheet"], ref="pc")
    con = pc.ability_mod("con")
    assert pc.hp_max == 16 + con * 2 + 1
    _earned(pc)
    got = leveling.level_up(pc, dice=Dice(seed=4), favoured="skill")
    assert len(got["faces"]) == 2
    assert got["hp"] == sum(max(1, f + con) for f in got["faces"])


def test_the_favoured_bonus_as_a_skill_rank_is_a_rank_owed_not_a_hit_point(quad):
    """CRB p.31: either, never both. A level taken as "skill" owes one more rank and adds
    no hit point; the forge's own "skill" choice allows one more rank at 1st."""
    pc = _forge(favoured="skill")
    assert pc.hp_max == 32 + 8
    assert leveling.skill_ranks(pc)["total"] == leveling.skill_ranks(pc)["per_level"] + 1
    _earned(pc)
    owed_before = leveling.skill_ranks(pc)["owed"]
    got = leveling.level_up(pc, dice=Dice(seed=2), favoured="skill")
    assert got["hp"] == sum(max(1, f + 2) for f in got["faces"])
    due = leveling.skill_ranks(pc)
    assert due["owed"] == owed_before + due["per_level"] + 1
    assert due["favoured_ranks"] == 2
    assert pc.favoured == ["skill", "skill"]


def test_an_unknown_favoured_bonus_is_refused_with_the_choices_named(quad):
    pc = _forge()
    _earned(pc)
    got = leveling.level_up(pc, dice=Dice(seed=2), favoured="gold")
    assert got["ok"] is False and "hp or skill" in got["why"]
    assert pc.level == 1


def test_the_class_tab_offers_the_choice_and_the_button_sends_it():
    """The level-up flow on the Class tab: the two radios beside the button, and the
    click posts the one checked. And the die lands from the reply's `levelled` record —
    it read the reply's top level, where `rolled` never is, so it never landed."""
    from pathlib import Path

    js = Path("play/static/js/table")
    sheet = (js / "05-sheet.js").read_text(encoding="utf-8")
    core = (js / "01-core.js").read_text(encoding="utf-8")
    assert 'name="lvfavoured" value="hp" checked' in sheet
    assert 'name="lvfavoured" value="skill"' in sheet
    assert 'input[name="lvfavoured"]:checked' in core and "favoured:" in core
    assert "d.levelled || d" in core
