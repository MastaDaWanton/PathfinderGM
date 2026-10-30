"""A monster's saves are the ones its stat block prints.

The PDF scan read "Fort +3, Ref +2, Will –1" with an ASCII minus only, and the books print
an en dash. Measured 2026-10-30 over the 1,417 core blocks: 39 had no saves at all — the
goblin, the orc, the kobold, the drow, the duergar, the merfolk, every ooze — each for one
negative save, or for a qualifier between two ("Fort +10 (+12 vs. nonmagical disease)",
the hippopotamus), or for the kerned "w ill" (the cassisian). 29 of them had saves in
0.2.22, from the spreadsheet rows option D removed. Without them the sheet derived saves
from ability scores, and they came out low: the goblin 1/2/−1 where the book prints
+3/+2/−1, the gray ooze 8/−5/−5 for +9/−4/−4. The same dash cost 69 blocks their
initiative and 48 their CMB.

The table below is Archives of Nethys (aonprd.com, MonsterDisplay, read 2026-10-30), 20
of the 39. A 21st, the hippopotamus, is printed differently there (+8/+5/+3, citing
Bestiary 2 and Heart of the Jungle) than in the Bestiary 2 PDF the app reads (+10/+5/+2,
p. 157): the book's stands, and it is pinned separately.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import bestiary
from tools import extract_bestiary_pdfs as extract

CORE = Path(__file__).resolve().parents[1] / "content" / "bestiary" / "core.json"

AON = {
    "goblin": (3, 2, -1), "orc": (3, 0, -1), "kobold": (2, 1, -1), "drow": (2, 2, -1),
    "duergar": (4, -1, 1), "merfolk": (4, 1, -1), "gray-ooze": (9, -4, -4),
    "gelatinous-cube": (9, -4, -4), "black-pudding": (9, -2, -2), "ochre-jelly": (8, -3, -3),
    "troglodyte": (7, -1, 0), "dhampir": (2, 3, -1), "suli": (2, 3, -1),
    "slithering-pit": (5, 4, -2), "caligni": (3, 5, -1), "skeletal-champion": (3, 1, 3),
    "porcupine": (3, 5, -1), "slime-mold": (6, 0, -4), "frog-poison": (2, 3, -1),
    "spear-urchin": (8, -3, 1),
}


@pytest.mark.parametrize("bid, want", sorted(AON.items()))
def test_a_creature_saves_as_the_book_prints(bid, want):
    actor = bestiary.instantiate(bid)
    got = tuple(sum(m.value for m in actor.save_modifiers(s)) for s in ("fort", "ref", "will"))
    assert got == want


def test_the_hippopotamus_saves_as_its_bestiary_prints():
    actor = bestiary.instantiate("hippopotamus")
    assert actor.flat_saves == {"fort": 10, "ref": 5, "will": 2}


def test_every_core_block_has_its_saves_and_initiative():
    core = json.loads(CORE.read_text(encoding="utf-8"))["creatures"]
    assert [c["id"] for c in core if not c.get("flat_saves")] == []
    # The ogrekin's page prints "int +5" where the heading should say Init (Bestiary 2
    # p. 204): a misprint, read as nothing rather than guessed.
    assert [c["id"] for c in core if c.get("flat_initiative") is None] == ["ogrekin"]


@pytest.mark.parametrize("text, want", [
    ("Fort +3, Ref +2, Will –1", {"fort": 3, "ref": 2, "will": -1}),
    ("fort +10 (+12 vs. nonmagical disease), ref +5, Will +2", {"fort": 10, "ref": 5, "will": 2}),
    ("fort +4, ref +3, w ill +2; +4 vs. poison", {"fort": 4, "ref": 3, "will": 2}),
])
def test_the_scan_reads_every_save_layout(text, want):
    block = (f"GOBLIN CR 1/3 XP 135 Goblin warrior 1 NE Small humanoid (goblinoid) "
             f"Init –1; Senses darkvision 60 ft.; Perception –1 DEFENSE AC 16, touch 13, "
             f"flat-footed 14 (+2 armor, +2 Dex, +1 shield, +1 size) hp 6 (1d10+1) {text} "
             f"OFFENSE Speed 30 ft. Melee short sword +2 (1d4/19–20) STATISTICS Str 11, "
             f"Dex 15, Con 12, Int 10, Wis 9, Cha 6 Base Atk +1; CMB –1; CMD 12")
    got = extract.parse_block(block, "Goblin", "1/3")
    assert got["flat_saves"] == want
    assert (got["flat_initiative"], got["cmb"]) == (-1, -1)


def test_a_templates_rules_are_not_a_blocks_special_attacks():
    """The lizardfolk prints no Special Attacks; its page runs on into the lycanthrope
    template's "Special Attacks: A lycanthrope retains all the special attacks ...", which
    it carried as its own, with four more blocks the same way."""
    by = {c["id"]: c for c in json.loads(CORE.read_text(encoding="utf-8"))["creatures"]}
    for bid in ("lizardfolk", "human-skeleton", "human-zombie", "petitioner",
                "taxidermic-grizzly-bear"):
        assert not by[bid]["special_attacks"].lstrip().startswith(":"), bid
