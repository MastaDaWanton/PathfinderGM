"""The magic-item catalogue: Pathfinder's priced properties and wondrous items.

It was also the old "By the book" enchanting mode (the +1 ladder, the masterwork vessel, the
potion standing in for a prerequisite spell). That chain was deleted on 2026-11-08 (audit
finding #20) with the tests that pinned it; what is left is the catalogue every live reader
asks.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import effectspec
from rules import magicitem as mi

SHIPPED = Path("content/materials/magic-items.json")


@pytest.fixture
def corpus():
    return json.loads(SHIPPED.read_text(encoding="utf-8"))["materials"]


# --- the catalogue ------------------------------------------------------------------------

def test_the_catalogue_loads_and_ids_are_unique(corpus):
    """Duplicate ids merge silently on read — one entry shadowing another with no error
    anywhere, which is how a priced property quietly becomes a different one."""
    ids = [m["id"] for m in corpus]
    assert not {i for i in ids if ids.count(i) > 1}
    assert len(mi.catalogue()) == len(corpus)


def test_the_catalogue_is_only_its_own_file():
    """This mode reads `magic-items.json` alone, where the essence mode reads the whole
    shared materials folder. A blacksmith's quenching brine appearing as a weapon
    property would be nonsense rather than generosity."""
    assert "quartz-focus" not in mi.catalogue()
    assert "mi-flaming" in mi.catalogue()


def test_every_authored_effect_validates(corpus):
    """Zero invalid specs, offenders printed. A spec that fails validation renders on a
    card and does nothing when the engine is asked — the silent failure the effect
    vocabulary exists to prevent."""
    bad = []
    for m in corpus:
        for where in ("effects", "drawbacks"):
            for i, spec in enumerate(m.get(where) or []):
                bad.extend(effectspec.validate(spec, f"{m['id']}.{where}[{i}]"))
    for line in bad:
        print(line)
    assert not bad, f"{len(bad)} invalid specs (printed above)"


def test_every_prerequisite_spell_is_a_real_spell(corpus):
    """The prerequisite is the whole point of the potion rule, so a misspelled spell id
    would refuse a working for a spell no potion could ever hold. Grounded against the
    corpus rather than trusted — "ground every name", measured."""
    from rules import spells

    known = spells.all_spells()
    missing = sorted({m["spell"] for m in corpus
                      if m.get("spell") and m["spell"] not in known})
    assert not missing, f"prerequisite spells not in the corpus: {missing}"


def test_all_three_kinds_are_stocked(corpus):
    """Weapons, armour and jewelry each need enough to choose between, or a mode tab
    opens on a list of four things."""
    by_kind = {}
    for m in corpus:
        by_kind.setdefault(m["kind"], []).append(m)
    assert len(by_kind["weapon_property"]) >= 15
    assert len(by_kind["armour_property"]) >= 15
    assert len(by_kind["wondrous"]) >= 40


# --- what a worn item reads ------------------------------------------------------------------

def test_worn_items_read_the_checked_book_numbers_not_the_old_row():
    """Lane D's data pass corrected the catalogue against AoN and served it as `book`; this
    module kept reading the old `effects`, so the Goggles of Minute Seeing went on giving
    +5 Perception (the old row) where the book gives +5 Disable Device."""
    got = mi.worn_specs("Goggles of Minute Seeing")
    assert [(s["type"], s["target"], s["amount"]) for s in got] == \
        [("skill_mod", "disable device", 5)]
    flaming = mi.get("mi-flaming").effects
    assert flaming and flaming[0].get("trigger") == "hit"
