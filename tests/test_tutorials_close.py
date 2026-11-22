"""Tutorials phase 6 (docs/tutorials-plan.md §4): the manual's tips section, and four layout
defects the section lanes' hit tests found with a card open (all older than the cards).

Each was measured live with tools/table_hit_test.js before and after; these tests hold the
rule each fix put in place, with the measurement in the docstring.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = (ROOT / "play" / "templates" / "play" / "table.html").read_text(encoding="utf-8")
HOME = (ROOT / "play" / "templates" / "play" / "home.html").read_text(encoding="utf-8")
MANUAL = (ROOT / "play" / "templates" / "play" / "manual.html").read_text(encoding="utf-8")
TUT_JS = (ROOT / "play" / "static" / "js" / "tutorials.js").read_text(encoding="utf-8")
WORKS_JS = (ROOT / "play" / "static" / "js" / "table" / "37-works.js").read_text(encoding="utf-8")


def test_the_manual_says_how_the_tips_work_in_the_buttons_own_words():
    """The welcome line sends the player to the Manual, which had no word about tips.
    The section names each control by the label the page draws, so it cannot describe a
    button that is not there."""
    m = re.search(r'<h2 id="tips">(.*?)<h2 ', MANUAL, re.S)
    assert m and 'href="#tips"' in MANUAL, "the section and its contents link"
    words = m.group(1)
    for label in ("Next", "Got it", "Not now", "Turn tips off", "Show me", "Show all tips again"):
        assert f"<b>{label}</b>" in words and f">{label}<" in TUT_JS, label
    for said in ("F6", "Esc", "Settings → Tutorials", "data folder", "phone"):
        assert said in words, said
    assert 'href="/manual#tips"' in TUT_JS, "the welcome line opens the section itself"


def test_the_shelf_never_scrolls_sideways():
    """A world card's clasp layer (.card::after, inset -35px) reaches past main's 30px
    gutter: with a scrollbar main measured scrollWidth 1013 in a 1009px box at 1024x700
    (789/785 at 800x600, 378/360 at 375 wide) and scrolled 4px sideways."""
    rule = re.search(r"\n  main \{[^}]*\}", HOME).group(0)
    assert "overflow-x: hidden" in rule


def test_a_short_fight_keeps_the_ground_inside_its_frame():
    """At 800x600 in a fight the board's row is 179px; its head wrapped to 115px and left
    the ground 8px, so the foot (90px) spilled 66px out of the frame (bottom 302, foot to
    368) over Full attack, Ability and Cast. The ground now scrolls in its own well."""
    block = TABLE[TABLE.index("@media (min-width: 761px) and (max-height: 639.98px)"):]
    block = block[:block.index("\n  }\n")]
    assert "#mapwrap {" in block and "overflow-y: auto" in block
    assert "flex-wrap: nowrap" in block
    # theme-v2.css: the framed card itself must never get an overflow, or its clasps go.
    assert "#boardframe" not in block and ".board {" not in block


def test_a_short_window_never_pins_the_deal_over_the_wares():
    """At 800x600 the pinned deal was 190px in a 127px scroller, so it lay over every
    ware at every scroll: four cards measured under div.tr-total."""
    m = re.search(r"@media \(max-width: 1000px\) and \(max-height: 759\.98px\) \{(.*?)\n  \}",
                  TABLE, re.S)
    assert m and ".tradedeal { position: static; }" in m.group(1)


def test_in_progress_over_the_table_stands_clear_of_the_pen():
    """Level with a low door at 800x600 the panel lay at 310-690 x 406-584, over the pen
    (top 401), Continue and Craft action. It now ends above the pen when it fits there,
    its list shortened to no less than 160px."""
    place = WORKS_JS[WORKS_JS.index("function place()"):]
    place = place[:place.index("\n  }\n")]
    assert 'getElementById("sayform")' in place and "room" in place
    assert "maxHeight" in place, "a long list scrolls inside rather than over the pen"


def test_the_creation_and_homebrew_pages_fit_a_phone():
    """Phase 6's phone pass (375x812): Outfitting, the race and the spell builders had no
    viewport tag and laid out 980px wide, shrunk to a third. Given one, Outfitting's Begin
    the sandbox and Keep on the shelf sat at 310-462px, and the class builder (which had
    one) scrolled sideways to 652px behind a nowrap heading."""
    pages = ROOT / "play" / "templates" / "play"
    for name in ("outfit", "racebuilder", "spellbuilder", "classbuilder"):
        assert 'name="viewport" content="width=device-width' in (pages / f"{name}.html").read_text(
            encoding="utf-8"), name
    outfit = (pages / "outfit.html").read_text(encoding="utf-8")
    phone = outfit[outfit.index("@media (max-width: 600px)"):]
    assert ".purse, .sortbar { flex-wrap: wrap; }" in phone[:phone.index("\n  }")]
    builder = (pages / "classbuilder.html").read_text(encoding="utf-8")
    phone = builder[builder.index("@media (max-width: 600px)"):]
    assert "h1 small { white-space: normal; }" in phone[:phone.index("\n  }")]
