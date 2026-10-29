"""The printed Bestiaries, read by every block's header instead of one anchor per page.

`content/bestiary/core.json` was built by walking the reference index's creature anchors,
one per page heading, and parsing the first stat block on that page. Measured 2026-10-28:

- the index held 224 anchors for Bestiary 1, 37 for Bestiary 2 and 41 for Bestiary 4, so
  the file had 782 creatures and no plain wolf, goblin's kin or most of two books;
- a page printing two blocks gave its anchor the FIRST one: `wolf-dire` carried the plain
  wolf (CR 1, 13 hp, Medium; the dire wolf is CR 3, Large) and `ant-giant` an army ant
  swarm (Fine, "swarm (3d6)");
- Bestiary 5's text layer splits two-digit CRs ("CR 1 1 XP 12,800"), so its aerial servant
  shipped at CR 1 with 149 hit points;
- Bestiary 4 is a scanned book with an OCR text layer, and two of its twelve blocks had hit
  points their own dice cannot make (the giant emperor scorpion at 4 hp).

Re-read by header (tools/extract_bestiary_pdfs.py `run_scan`): 1,417 blocks from
Bestiaries 1, 2, 3, 5 and 6, Bestiary 4 left out until a text copy exists. The old ids a
save may hold either kept their block or are aliased to it — all but one, the great
horned owl, whose block a sidebar cuts before its statistics (unparsed, never invented).
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

from rules import bestiary
from tools import extract_bestiary_pdfs as extract

CORE = Path(__file__).resolve().parents[1] / "content" / "bestiary" / "core.json"


@pytest.fixture(scope="module")
def core() -> dict:
    return json.loads(CORE.read_text(encoding="utf-8"))


def _by_id(core) -> dict:
    return {c["id"]: c for c in core["creatures"]}


# --- what was wrong ------------------------------------------------------------------------

def test_the_dire_wolf_is_the_dire_wolf_and_the_wolf_exists(core):
    by = _by_id(core)
    assert (by["wolf-dire"]["cr"], by["wolf-dire"]["size"]) == ("3", "large")
    assert (by["wolf"]["cr"], by["wolf"]["hp"], by["wolf"]["size"]) == ("1", 13, "medium")


def test_the_giant_ant_is_one_ant_not_an_army_ant_swarm(core):
    ant = _by_id(core)["ant-giant"]
    assert (ant["cr"], ant["size"]) == ("2", "medium") and "swarm" not in ant["melee"]


def test_a_split_two_digit_cr_reads_as_its_xp_says(core):
    """"AERIAL SERVANT CR 1 1 XP 12,800": CR 11, which the XP table confirms."""
    assert _by_id(core)["aerial-servant"]["cr"] == "11"
    assert extract._cr_of("1 1", "12,800") == "11"


def test_every_book_but_the_ocr_scan_is_read_whole(core):
    counts: dict[str, int] = {}
    for c in core["creatures"]:
        counts[c["source"]] = counts.get(c["source"], 0) + 1
    assert counts.get("Bestiary 4", 0) == 0, "an OCR scan's numbers are not shipped"
    assert all(counts.get(b, 0) >= n for b, n in (("Bestiary", 300), ("Bestiary 2", 280),
                                                  ("Bestiary 3", 270), ("Bestiary 5", 270),
                                                  ("Bestiary 6", 230)))


def test_hit_points_agree_with_their_own_dice(core):
    """1,415 of 1,417, measured; the lich's false life and the skeletal champion's mixed
    Hit Dice are the book's own. A block whose hp its dice cannot make is a misread."""
    def can_make(hp: int, hd: str) -> bool:
        s = hd.replace("–", "-").replace(" ", "").split(";")[0]
        dice = re.findall(r"(\d+)d(\d+)", s)
        if not dice:
            return False
        flat = sum(int(k) * (1 if sg == "+" else -1)
                   for sg, k in re.findall(r"([+-])(\d+)(?!d)", re.sub(r"\d+d\d+", "", s)))
        mean = sum(int(n) * (int(d) + 1) / 2 for n, d in dice) + flat
        first_max = mean + int(dice[0][1]) - (int(dice[0][1]) + 1) / 2   # a class level
        return any(abs(hp - math.floor(v)) <= 1 for v in (mean, first_max))

    odd = sorted(c["id"] for c in core["creatures"] if not can_make(c["hp"], c["hit_dice"]))
    assert odd == ["lich", "skeletal-champion"]


def test_the_buyers_watermark_never_reaches_content():
    """Every page prints "paizo.com #<order>, <name> <<email>>, <date>"."""
    text = CORE.read_text(encoding="utf-8")
    assert "paizo.com" not in text and "@" not in text


# --- saves keep their bodies -----------------------------------------------------------------

def test_every_alias_lands_on_a_block(core):
    by = _by_id(core)
    assert core["aliases"] and all(v in by for v in core["aliases"].values())


@pytest.mark.parametrize("old, now", [
    ("skeleton", "Human Skeleton"), ("zombie", "Human Zombie"),
    ("elephant-mastodon", "Mastodon"), ("worg-winter-wolf", "Winter Wolf"),
    ("hell-hound-nessian", "Nessian Warhound")])
def test_an_old_id_a_save_holds_still_finds_its_creature(old, now):
    """By what the id meant: "Elephant, Mastodon" is the mastodon, though the old file
    carried the elephant printed above it on the page."""
    assert bestiary.raw_block(old)["name"] == now
    assert bestiary.lookup(old) is not None


# --- the header reader, on the measured strings -------------------------------------------------

@pytest.mark.parametrize("before, name", [
    ("451196 451196 Wolf Wolf , Dire WOLf", "Wolf"),
    ("weighs between 45 and 150 pounds, with females being slightly smaller. DIRE WOLf",
     "Dire Wolf"),
    ("Ape, Gorilla Ape, Dire DIRE APE (gIgAnTOPIThECUS)", "Dire Ape"),
    ("it sniffs incessantly. Badger", "Badger"),
    ("like a deformed spider. CraWLing hand", "Crawling Hand"),
    ("Dinosaur, Triceratops–DogDinosaur, Triceratops–Dog DOg", "Dog"),
    ("451051 451051 FamiliarFamiliar RAVEn", "Raven"),
    ("451195 Will-o'-Wisp WILL-O'-WISP", "Will-o'-wisp"),
    ("its vast mouth opens like a toothy cavern. Mu SPORe", "Mu Spore"),
    ("the jubjub's neck is bare and scaly. JUBJUB BIRD", "Jubjub Bird"),
    ("Illustration by Adam Vehige Gorilla Ape, Gorilla gORILLA", "Gorilla"),
])
def test_a_title_is_read_back_from_its_cr(before, name):
    assert extract._title(extract._name_before(before.split())) == name


def test_prose_naming_a_cr_is_not_a_header():
    assert not extract.HEADER.search("Djinn nobles are CR 8. Noble efreet are CR 10.")
    assert extract.HEADER.search("DUPPY CR 7 CE Medium undead (incorporeal)")
    assert extract.HEADER.search("ANUNNAKI CR\t1 8/MR\t7 XP\t153,600 N Large")
