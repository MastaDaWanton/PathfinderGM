"""A weapon edited at the homebrew bench reaches play.

Two gaps, found reading the code for the architecture overview (2026-09-29) and
reproduced here before the fix:

1. `rules/weapons.py` says "Homebrew layers last, as it does everywhere else", and then
   merged the eleven hand-written weapons on top AFTER the homebrew folder. A homebrew
   rapier with a 15-20 threat range came back 18-20: an edit to any of the eleven was
   silently overwritten.
2. The "Items, weapons & armour" bench saved to `homebrew/items/`, and no code read that
   folder — the weapon table reads `homebrew/weapons/`, and armour and shields are a
   hand-written table with no homebrew layer at all. Every save from that bench reached
   the bench and nothing else, with no error anywhere. Its armour and shield rows did not
   even open: `registry.find("items", "chainmail")` asked the weapon table and 404'd.

The bench is the weapon bench now, saving where the weapon table reads, and a file left
in the old folder by an earlier build still counts.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client

from rules import registry
from rules import weapons


@pytest.fixture
def mine(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    weapons._ALL = None
    yield tmp_path / "homebrew"
    weapons._ALL = None


def test_a_homebrew_edit_to_a_curated_weapon_wins(mine):
    """The rapier is one of the hand-written eleven. Measured before the fix: homebrew
    said crit_range 15, the table said 18."""
    (mine / "weapons").mkdir(parents=True)
    (mine / "weapons" / "rapier.json").write_text(
        json.dumps({"id": "rapier", "name": "Rapier", "crit_range": 15}), encoding="utf-8")
    row = weapons.all_weapons()["rapier"]
    assert row["crit_range"] == 15
    # Merged, not replaced: the fields the edit never mentioned are still the rapier's.
    assert row["finessable"] is True and row["damage"] == "1d6"


def test_the_curated_eleven_still_win_over_the_bulk_import():
    """The other half of the layering, which must not move: the imported file is the
    base and the hand-written entries correct it."""
    from rules.tables import WEAPONS as SHIPPED

    table = weapons.all_weapons()
    for key, entry in SHIPPED.items():
        row = table[weapons.ALIASES.get(key, key)]
        for field, value in entry.items():
            assert row[field] == value, (key, field)


def test_a_homebrew_weapon_under_a_curated_alias_lands_on_the_one_row(mine):
    """"shortsword" is the curated spelling of the file's "short-sword". A homebrew file
    keyed the curated way must correct that sword, not stand beside it as a second one —
    the two-rows-for-one-sword defect E1 fixed for the shipped tables."""
    (mine / "weapons").mkdir(parents=True)
    (mine / "weapons" / "shortsword.json").write_text(
        json.dumps({"id": "shortsword", "name": "Shortsword", "crit_mult": 3}),
        encoding="utf-8")
    table = weapons.all_weapons()
    assert table["short-sword"]["crit_mult"] == 3
    assert "shortsword" not in table


def test_saving_a_weapon_at_the_bench_changes_the_weapon_in_play(mine):
    """The whole path: the bench's save, then the table the attack op and the shops read.
    Before the fix the save wrote homebrew/items/rapier.json and the rapier never
    changed."""
    r = Client().post("/api/bench/items/save", data=json.dumps({
        "id": "rapier", "name": "Rapier", "crit_range": 15, "damage": "1d6",
        "crit_mult": 2, "type": "piercing", "description": "", "effects": [],
    }), content_type="application/json")
    assert r.status_code == 200, r.json()
    assert weapons.all_weapons()["rapier"]["crit_range"] == 15


def test_a_weapon_saved_by_an_earlier_build_still_counts(mine):
    """Files the old bench wrote to homebrew/items/ are read, so nobody's edit is lost
    to the move. Only weapons: an armour or shield written there has no table to reach,
    and turning it into a weapon would be worse than leaving it."""
    (mine / "items").mkdir(parents=True)
    (mine / "items" / "glaive.json").write_text(
        json.dumps({"id": "glaive", "name": "Glaive", "kind": "weapon", "crit_mult": 4}),
        encoding="utf-8")
    (mine / "items" / "mithral-shirt.json").write_text(
        json.dumps({"id": "mithral-shirt", "name": "Mithral shirt", "kind": "armour"}),
        encoding="utf-8")
    table = weapons.all_weapons()
    assert table["glaive"]["crit_mult"] == 4
    assert "mithral-shirt" not in table


def test_every_row_on_the_weapon_bench_opens(mine):
    """The old bench drew armour and shield rows that 404'd when clicked: the registry
    resolves the items bench through the weapon table."""
    rows = Client().get("/api/bench/items").json()["rows"]
    assert rows
    for row in rows:
        r = Client().get(f"/api/bench/items/open/{row['id']}")
        assert r.status_code == 200, row


def test_the_bench_saves_where_the_weapon_table_reads():
    """One folder, named once: the registry's declaration and the weapon loader agree."""
    assert registry.get("items").folder == "weapons"
