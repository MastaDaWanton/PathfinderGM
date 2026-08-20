"""The rules reference extracted from the PDFs.

Two jobs. First, the extraction has to survive the books' typography — the text layer
tears words apart and a reference full of words no search will match is worse than no
reference. Second, the engine's own tables have to agree with the book; where they do
not, the gap is named here rather than discovered mid-scene.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REF = Path("reference")
sys.path.insert(0, str(REF))

pytestmark = pytest.mark.skipif(
    not (REF / "conditions.json").exists(),
    reason="reference not built; run reference/build_reference.py",
)


@pytest.fixture(scope="module")
def conditions():
    return json.loads((REF / "conditions.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def index():
    return json.loads((REF / "index.json").read_text(encoding="utf-8"))


# --- The typography repair -------------------------------------------------------

@pytest.mark.parametrize("raw,expected,why", [
    ("is f lat-footed, unable to react", "is flat-footed, unable to react",
     "the fl ligature comes out as a bare 'f'"),
    ("You can inf lict damage", "You can inflict damage",
     "the same ligature mid-word leaves the f attached to the head"),
    ("normally to the s itu ation.", "normally to the situation.",
     "kerning scatters a word into pieces of uneven length"),
    ("grappled c re atures can", "grappled creatures can",
     "three pieces, the last one longest"),
    ("is l im ited in the actions", "is limited in the actions",
     "a preceding real word must not be swallowed"),
    ("It can a lw ays attempt to free", "It can always attempt to free",
     "'a' is a real word and also the head of a broken one; 'attempt' must survive"),
])
def test_pdf_typography_is_repaired(raw, expected, why):
    """Every one of these came out of the Core Rulebook's own text layer.

    The naive fixes each broke something else: welding short runs turned "who has not
    yet" into "whohasnotyet" and "with a dog" into "with adog"; joining any word ending
    in f turned "of light" into "oflight".
    """
    from build_reference import clean

    assert clean(raw) == expected, why


@pytest.mark.parametrize("raw", [
    "A character who has not yet acted during a combat",
    "He is in the room with a dog.",
    "A dog ran off and he is at the top of it.",
    "takes a -2 penalty to AC and loses its Dex bonus to AC",
    "The DC is 10 + the CR of the trap.",
    "The light of the sun, if lying flat, is of light weight.",
])
def test_ordinary_prose_is_left_alone(raw):
    """The repair has to be safe on text that was never broken. Two-letter capitals
    (AC, CR, DC) are the sharp case: they look exactly like fragments."""
    from build_reference import clean

    assert clean(raw) == raw


# --- The extracted conditions ------------------------------------------------------

def test_every_condition_in_the_appendix_was_extracted(conditions):
    """Appendix 2 lists 34 conditions. A scraper that silently drops one is a rule the
    engine will never apply, so the count is asserted rather than trusted."""
    got = {c["key"] for c in conditions["conditions"]}
    assert len(got) == 34
    for expected in ("flat-footed", "grappled", "prone", "stunned", "unconscious",
                     "shaken", "nauseated", "pinned", "helpless", "dying"):
        assert expected in got


def test_extracted_descriptions_are_readable(conditions):
    """No leftover ligature breaks, no welded words, and enough text to be worth having."""
    import re

    for c in conditions["conditions"]:
        d = c["description"]
        assert len(d) > 40, f"{c['name']} came out too short: {d!r}"
        assert not re.search(r"\bf [lit][a-z]", d), f"{c['name']} has a broken ligature: {d!r}"
        assert not re.search(r"[a-z]{18,}", d), f"{c['name']} has welded words: {d!r}"


def test_the_engines_conditions_all_exist_in_the_book(conditions):
    """rules/tables.py was written from memory before the books were readable. This is
    the check that it did not invent a condition."""
    from rules.tables import CONDITIONS

    book = {c["key"] for c in conditions["conditions"]}
    ours = set(CONDITIONS)
    invented = ours - book
    assert not invented, f"not in Appendix 2: {sorted(invented)}"


def test_the_conditions_the_engine_does_not_implement_yet_are_named(conditions):
    """Not a failure — a ledger. These are the conditions the book defines that the
    engine will silently ignore if a GM applies them, and this test is where that list
    lives so it shrinks deliberately rather than by accident.
    """
    from rules.tables import CONDITIONS

    book = {c["key"] for c in conditions["conditions"]}
    missing = sorted(book - set(CONDITIONS))
    assert missing == [
        # Needs a per-round damage tick the engine does not have yet.
        "bleed",
        # An item condition, not a creature one; arrives with sunder and item hit points.
        "broken",
        # Negative levels, which means recomputing a whole sheet downwards.
        "energy drained",
        # Both need targeting and miss-chance rules that zones do not yet model.
        "incorporeal", "invisible",
    ], "the unimplemented-condition ledger changed; update it deliberately"


# --- The index ------------------------------------------------------------------------

def test_the_index_covers_both_books(index):
    books = index["books"]
    assert set(books) == {"crb", "gmg"}
    assert len(books["crb"]["sections"]) > 1000
    assert len(books["gmg"]["sections"]) > 500


def test_numbered_tables_are_indexed_with_their_pages(index):
    """125 numbered tables in the Core Rulebook, each with a page. This is what makes
    the reference a substitute for opening the PDF: the app can look up "Table 12-1" and
    know where it is."""
    tables = {t["number"]: t for t in index["books"]["crb"]["tables"]}
    assert len(tables) > 100
    assert "12-1" in tables and "Encounter Design" in tables["12-1"]["title"]
    assert all(isinstance(t["page"], int) for t in tables.values())


def test_the_combat_chapter_is_findable(index):
    """The manoeuvre rules live at CRB p.198-201; the index has to lead there."""
    titles = {s["title"].lower(): s["page"] for s in index["books"]["crb"]["sections"]}
    assert "combat maneuvers" in titles
    assert 195 <= titles["combat maneuvers"] <= 205
