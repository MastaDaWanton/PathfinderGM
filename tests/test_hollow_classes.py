"""Group 13 of the 2026-09-19 fix pass: the three classes that granted nothing.

Reported as a screenshot of the Class tab (docs/playtest-2026-09-18.md item 27): *The whole
table*, levels 1 to 20, "What it grants" reading **—** on every row.

The table was honest and the document was empty. Eight classes live in
`content/classes/*.json` with 20-row `levels` tables; **cleric, fighter, wizard and rogue**
lived in `rules/tables.CLASSES` with no table at all. So no bonus feats, no armour or weapon
training, no arcane bond or school — and no sneak attack, a phrase that appeared exactly
once in the app, in `rules/glossary.py`, as a definition nothing read.

The cleric shipped with group 12, because its domain slot is part of that arithmetic. These
are the other three, each taken from its own rulebook page (d20pfsrd, read 2026-09-20)
rather than written from memory.
"""
from __future__ import annotations

import pytest

from rules import classes, creation


def _rows(cid: str) -> list[dict]:
    return list(classes.all_classes()[cid].get("levels") or [])


@pytest.mark.parametrize("cid", ["fighter", "rogue", "wizard", "cleric"])
def test_every_core_class_has_a_twenty_row_table(cid):
    """The Class tab printed twenty dashes because there was nothing to print."""
    rows = _rows(cid)
    assert len(rows) == 20, cid
    assert [r["level"] for r in rows] == list(range(1, 21))
    assert any(r.get("grants") for r in rows), f"{cid} grants nothing at any level"


def test_the_fighters_bonus_feats_land_where_the_book_puts_them():
    """Bonus feats at 1st and every even level; bravery at 2, 6, 10, 14, 18; armour
    training at 3, 7, 11, 15; weapon training at 5, 9, 13, 17; the two masteries at 19
    and 20."""
    at = {r["level"]: r.get("grants", []) for r in _rows("fighter")}
    feats = [lvl for lvl, g in at.items() if "bonus feat" in g]
    assert feats == [1, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
    assert [lvl for lvl, g in at.items() if any(x.startswith("bravery") for x in g)] == \
        [2, 6, 10, 14, 18]
    assert [lvl for lvl, g in at.items() if any(x.startswith("armor training") for x in g)] == \
        [3, 7, 11, 15]
    assert [lvl for lvl, g in at.items() if any(x.startswith("weapon training") for x in g)] == \
        [5, 9, 13, 17]
    assert "armor mastery" in at[19] and "weapon mastery" in at[20]


def test_the_rogue_finally_has_a_sneak_attack():
    """The phrase appeared once in the whole app — in the glossary, as a definition nothing
    read. It is 1d6 at 1st and another d6 every odd level, to 10d6 at 19th."""
    at = {r["level"]: r.get("grants", []) for r in _rows("rogue")}
    dice = {lvl: g for lvl, g in at.items()
            if any(x.startswith("sneak attack") for x in g)}
    assert sorted(dice) == [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]
    assert "sneak attack 1d6" in at[1] and "sneak attack 10d6" in at[19]
    assert "trapfinding" in at[1] and "evasion" in at[2]
    assert [lvl for lvl, g in at.items() if "rogue talent" in g] == \
        [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
    assert "uncanny dodge" in at[4] and "improved uncanny dodge" in at[8]
    assert "master strike" in at[20]


def test_the_wizards_school_and_bond_are_at_first_level():
    at = {r["level"]: r.get("grants", []) for r in _rows("wizard")}
    assert {"arcane bond", "arcane school", "cantrips", "scribe scroll"} <= set(at[1])
    assert [lvl for lvl, g in at.items() if "bonus feat" in g] == [5, 10, 15, 20]


def test_the_proficiencies_are_the_ones_the_book_gives():
    """The stubs were thin in a way that mattered: a fighter had no armour proficiency at
    all, so every fighter in the game took the untrained penalty in his own plate."""
    fighter = classes.all_classes()["fighter"]["proficiencies"]
    assert {"heavy armor", "shields", "tower shields"} <= set(fighter)
    rogue = classes.all_classes()["rogue"]["proficiencies"]
    assert "light armor" in rogue and "rapier" in rogue
    wizard = classes.all_classes()["wizard"]["proficiencies"]
    assert "quarterstaff" in wizard and "heavy armor" not in wizard


def test_the_classes_still_build_and_the_forge_still_offers_them():
    """A document that replaces a stub must not lose what the stub was for."""
    offered = {c["id"] for c in creation.options()["classes"]}
    assert {"fighter", "rogue", "wizard", "cleric"} <= offered
    for cid in ("fighter", "rogue", "wizard"):
        built, problems = creation.build({
            "name": f"Table {cid}", "race": "human", "bonus_ability": "con",
            "class": cid, "pronouns": "they/them",
            "abilities": {"str": 12, "dex": 12, "con": 12, "int": 12, "wis": 12, "cha": 12},
            "skills": [], "feats": [],
            "spellbook": creation.starter_spells(cid, int_mod=1),
            "domains": creation.starter_domains(cid)})
        assert problems == [], (cid, problems)
        assert built["sheet"]["class"] == cid
