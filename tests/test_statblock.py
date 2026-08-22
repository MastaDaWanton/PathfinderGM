"""Where a stat-block list ends when the page did not say.

The defect, measured on the shipped `content/bestiary/core.json` before the repair:

- `immune` held 2,461 terms across 672 creatures. 392 of them were over 90 characters.
- `resist` held 2,915 terms, of which 835 were over 90 characters — more than the 701 that
  were under 10. A real resistance is "cold 10".
- 1,144 distinct immunity terms, in a game whose whole immunity vocabulary is under 100.
  Among them: `d m <dm_123_456@yahoo.com>` on 38 creatures, and `oct 20` on 38.
- Basilisk's immunities contained the Dire Bat's entire stat block. Derro's contained the
  four-page essay on the hierarchy of Hell.

The cause is one line in `_between`: with no terminating keyword it falls through to `$`
and takes the rest of the page. Every other field survived because every other field is
capped by a slice at the point of extraction. The three that split on commas were not, so a
runaway became a list of short plausible-looking terms instead of one visibly wrong string.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import statblock as sb

CORE = json.loads(Path("content/bestiary/core.json").read_text(encoding="utf-8"))
ROWS = CORE.get("creatures") or CORE


def by_name(name):
    return next(r for r in ROWS if r["name"] == name)


# --- the rule ------------------------------------------------------------------------------

@pytest.mark.parametrize("term", [
    "paizo.com #1276082",
    "D M <dm_123_456@yahoo.com>",
    "Oct 20",
    "2009 757001 757001 757001 450988",
    "Will +0 DR 10/-; Immune cold",                     # the next creature's DEFENSE line
    "low-light vision; Perception +10 DEfEnSE AC 15",   # the next creature's header
    "and his eight archdevil tyrants",                  # prose
    "raid caravans and humanoid settlements",
    "to the basilisk's stare",                          # `Immune` matched inside prose
    "this effect with a DC 22",
])
def test_page_text_is_recognised_as_spill(term):
    assert sb.is_spill(term)


@pytest.mark.parametrize("term", [
    "cold", "poison", "undead traits", "mind-affecting effects", "acid 10",
    "electricity (partial)", "energy drain", "petrification", "nonlethal damage",
])
def test_a_real_term_is_not(term):
    assert not sb.is_spill(term)


def test_the_cut_is_a_truncation_and_not_a_filter():
    """Spill is sequential, so everything after the first bad term is bad too. Filtering
    would keep the short innocuous fragments that follow — "wild hair", "burn", "and die"
    each pass a length test alone — and those are the ones that read as real immunities."""
    assert sb.trim(["cold", "fire", "and his eight archdevil tyrants", "burn",
                    "wild hair"]) == ["cold", "fire"]


def test_a_real_term_with_the_next_label_welded_on_survives():
    """Berbalang's first immunity is "undead traits Defensive Abilities projection" — the
    line ended without a comma, so the next field is stuck to a fact the book printed.
    Cutting the whole term loses the immunity; cutting at the label keeps it."""
    assert sb.trim(["undead traits Defensive Abilities projection"]) == ["undead traits"]
    assert by_name("Berbalang")["immune"] == ["undead traits"]


def test_a_resistance_must_carry_an_amount():
    """"Resist cold 10" is the only shape a DEFENSE line writes. The word also appears in
    the spell-like abilities block and inside spell names, and `_between` takes the first
    match either way — which is how "cure light wounds", "sound burst (DC 22)" and "all
    spells cast on it" survived every other test here."""
    assert sb.trim(["cure light wounds"], shape=sb.RESISTANCE) == []
    assert sb.trim(["cold 10", "fire 10"], shape=sb.RESISTANCE) == ["cold 10", "fire 10"]


def test_a_word_the_pdf_broke_is_rejoined():
    """"mind- aff ecting" and "mind-affecting" are the same immunity, and left apart they
    split the commonest immunity in the game across three spellings."""
    assert sb.mend("mind- aff ecting effects") == "mind-affecting effects"
    assert sb.mend("co ld 10") == "cold 10"


def test_the_watermark_comes_out_of_prose_too():
    """A capped field cannot run away, but the stamp still lands inside the cap: the
    Devourer's treasure read "standard paizo.com #1276082, D M <...@...>, Oct 20, 2009".
    55 prose fields carried it."""
    assert sb.scrub("standard paizo.com #1276082, D M <dm_123_456@yahoo.com>, "
                    "Oct 20, 2009") == "standard"


# --- what the shipped file holds now ---------------------------------------------------------

def test_no_purchasers_email_address_ships_with_the_app():
    """The PDFs are watermarked on every page with the buyer's address, and 192 copies of
    one reached content/bestiary/core.json. It is not a rule, it is somebody's personal
    data, and it was being distributed."""
    text = Path("content/bestiary/core.json").read_text(encoding="utf-8")
    assert "@yahoo.com" not in text
    assert "paizo.com #" not in text


def test_the_immunity_vocabulary_is_the_size_of_the_games():
    """1,144 distinct terms before, 79 after. Pathfinder's whole immunity vocabulary is
    energy types, conditions, a handful of "X traits" lines and a few named effects."""
    terms = {t.lower() for r in ROWS for t in (r.get("immune") or [])}
    assert len(terms) < 100
    assert {"cold", "poison", "undead traits", "mind-affecting effects"} <= terms


def test_every_resistance_is_an_energy_and_a_number():
    kinds = set()
    for r in ROWS:
        for t in r.get("resist") or []:
            assert sb.RESISTANCE.match(t), t
            kinds.add(t.rsplit(" ", 1)[0].lower())
    assert kinds <= {"acid", "cold", "electricity", "fire", "sonic", "negative energy"}


@pytest.mark.parametrize("name,immune", [
    ("Giant, Frost", ["cold"]),
    ("Ghost", ["undead traits"]),
    ("Skeleton", ["cold", "undead traits"]),
    ("Zombie", ["undead traits"]),
])
def test_creatures_whose_defence_line_can_be_checked_by_hand(name, immune):
    assert by_name(name)["immune"] == immune


def test_no_list_is_longer_than_a_printed_one():
    for r in ROWS:
        for f in ("immune", "resist", "languages"):
            assert len(r.get(f) or []) <= sb.MAX_TERMS, (r["name"], f)


def test_an_emptied_list_means_the_line_was_never_captured():
    """53 creatures came out of the cut with no immunities, and that is the honest state
    rather than a loss: their `immune` never held their immunities. The Ghoul's first term
    was "to this effect) STATISTICS Str 13" — the parser had matched the word "immune" in
    a sentence, because the DEFENSE line's own `Immune` was not extracted at all.

    So a Ghoul that reads as having none is a gap in the extraction, not in the repair,
    and filling it needs the book.
    """
    assert by_name("Ghoul")["immune"] == []


@pytest.mark.xfail(reason="known and not mechanically detectable — see the docstring",
                   strict=True)
def test_a_single_plausible_term_from_prose_still_gets_through():
    """The cut removes what can be proven wrong. A goblin has no immunities in the book,
    and its entry reads `["disease"]` — one short, well-formed, entirely plausible term the
    parser lifted out of a sentence. Nothing in the shape of it says so.

    Recorded as a failing test rather than fixed, because fixing it needs the source PDFs
    to compare against and they are not in the repository. It marks the boundary: the
    immunity lists are now clean of page spill, which is not the same as verified.
    """
    assert by_name("Goblin")["immune"] == []
