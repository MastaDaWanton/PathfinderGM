"""Our own versions of the adventures' items: the book's numbers, our names and words.

The owner, 2026-10-28, after option D took the adventure rows out: write our own versions
of the adventures' items, with nothing that needs a licence. Paizo's legal page marks as
Product Identity "proper names (characters, deities, etc.)" and leaves "the game
mechanics" open (docs/own-items.md, with the source). Measured on 2026-10-29: 4,310
distinct pieces of gear were carried only by the removed rows; the setting's own items
among them were read on Archives of Nethys and ten rows written (tools/own_items.py).

What these tests hold: no setting name in an item's name or words (its `source` is the
citation of where the numbers were read, and the one place an original is named); the
numbers are the book's, stated here by hand from the AoN pages independently of the
generator; and a rule that worked only for one god's faithful works for anybody.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parents[1]
ROWS = {r["id"]: r for r in json.loads(
    (ROOT / "content" / "materials" / "magic-items.json").read_text(encoding="utf-8"))
    ["materials"]}
OURS = ("mi-lodestar-compass", "mi-wardstar-medallion", "mi-wardstar-ring",
        "mi-iron-saints-mask", "mi-war-paint-black", "mi-war-paint-blue",
        "mi-war-paint-orange", "mi-war-paint-red", "mi-war-paint-silver",
        "mi-war-paint-yellow")
SETTING = ("sihedron", "wayfinder", "pathfinder", "shoanti", "razmir", "hellknight",
           "mantis", "harrow", "thassilon", "runelord", "varisia", "golarion", "iomedae",
           "glorious", "azlant", "absalom", "living god")

# (price gp, caster level), read on AoN 2026-10-29 (docs/own-items.md has each URL).
BOOK = {"mi-lodestar-compass": (500, 5), "mi-wardstar-medallion": (3500, 5),
        "mi-wardstar-ring": (35000, 9), "mi-iron-saints-mask": (2100, 1),
        "mi-war-paint-black": (1800, 7), "mi-war-paint-blue": (900, 7),
        "mi-war-paint-orange": (900, 7), "mi-war-paint-red": (900, 7),
        "mi-war-paint-silver": (900, 7), "mi-war-paint-yellow": (900, 7)}


def test_every_own_item_ships():
    assert all(rid in ROWS for rid in OURS)


@pytest.mark.parametrize("rid", OURS)
def test_no_setting_name_in_an_items_name_or_words(rid):
    row = ROWS[rid]
    words = " ".join([row["name"], row["text"], *row.get("not_yet", []),
                      json.dumps(row.get("book"))]).lower()
    assert not [w for w in SETTING if w in words], rid


def test_the_numbers_are_the_books():
    assert {rid: (ROWS[rid]["price_gp"], ROWS[rid]["caster_level"]) for rid in OURS} == BOOK
    ring = ROWS["mi-wardstar-ring"]["book"]
    assert [(d["type"], d.get("target"), d.get("amount"), d.get("bonus_type"))
            for d in ring[:4]] == [("combat_mod", "ac", 3, "deflection"),
                                   ("save_mod", "fort", 3, "resistance"),
                                   ("save_mod", "ref", 3, "resistance"),
                                   ("save_mod", "will", 3, "resistance")]
    medallion = ROWS["mi-wardstar-medallion"]["book"]
    assert medallion[-1]["spell"] == "false-life" and medallion[-1]["uses_count"] == 1


def test_a_war_paint_lasts_a_day_and_is_used_once():
    """"Effects last 24 hours", one dose: the book's paint."""
    for rid in OURS:
        if rid.startswith("mi-war-paint-"):
            power = ROWS[rid]["book"][0]
            assert power["uses"] == "once"
            assert power["effect"][0]["duration"] == {"amount": 24, "unit": "hour"}


def test_the_masks_powers_are_anybodys():
    """The book's mask works only "if Razmir is your patron"; ours names no patron, and no
    row of ours asks a creator to be anybody in particular."""
    assert not any(ROWS[rid].get("creator") for rid in OURS)


def test_worn_they_change_the_sheet():
    """Read through the catalogue like any Core wondrous item (`magicitem.worn_specs`):
    Kesst at AC 15 and Fortitude +1 wears the ring and stands at 18 and +4."""
    a = load_pc("fixtures/pc-kesst.json")
    ac, fort = a.ac(), sum(m.value for m in a.save_modifiers("fort"))
    a.slots["ring"] = ["Wardstar Ring"]
    assert a.ac() == ac + 3
    assert sum(m.value for m in a.save_modifiers("fort")) == fort + 3
    a.slots["head"] = ["Iron Saint's Mask"]
    assert any(m.value == 2 and "Iron Saint" in m.source for m in a.skill_modifiers("heal"))


def test_the_generator_is_the_record():
    """The rows are written by tools/own_items.py and nothing else: the shipped row equals
    the generator's, so a hand edit to the content file is caught."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("own_items", ROOT / "tools" / "own_items.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for row in mod.ROWS:
        shipped = {k: v for k, v in ROWS[row["id"]].items() if k not in ("tier", "effects")}
        assert shipped == row, row["id"]
    assert re.fullmatch(r"https://aonprd\.com/.+", ROWS["mi-wardstar-ring"]["source"])
