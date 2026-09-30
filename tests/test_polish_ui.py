"""Pre-release polish, the page's side (G3 leftovers, docs/fix-interfaces.md §3.4, items 1,
6 and 8). What each test holds, and what was measured before it:

  (1) The exits row mid-fight. The row offered "the arena · a few minutes" during an
      encounter exactly as it did in a quiet street, one click from walking out. In a
      fight every open way is now marked "withdraw", and (since 2026-09-29) a click
      attaches a Withdraw chip whose line says what leaving costs, and Say sends it. The
      page reads `scene.in_encounter`; it works out nothing about who threatens whom.

  (6) The sheet at 375x812, measured in the browser pane before the fix: the panel's one
      grid column was `auto` and came out 458px wide, the Close button was off the right
      edge, and twelve tabs shrank inside 636px of content until they read "De Of Sk Cl
      Fe Spi Eq". After: the column is 375px, the header wraps (name and Close on one
      line, the identity line under them), and the strip is one row of full labels that
      scrolls sideways (1285px of tabs in 375px), fading the edge that has more past it.

  (8) The 3D map. `scene.grid.areas` was drawn by the flat board only
      (`if (spellAreas.length && !MAP_3D)`), so switching to 3D hid where a cone went.
      Verified in the browser: seven filled squares and one dashed outline 15 ft up, in
      the flat map's #e0701e, under the figure standing in them, at turns 0 and 2.

The JavaScript is run in node against the shipped files, as test_i3_table runs the
spell filter, so the tests read the real functions and not copies of them.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import _exits_dom as exits_dom

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "play" / "static" / "js" / "table"
PAGE = ROOT / "play" / "templates" / "play" / "table.html"
SCENE3D = ROOT / "play" / "static" / "js" / "scene3d.js"

needs_node = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not on this machine")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _node(tmp_path: Path, script: str) -> dict:
    f = tmp_path / "probe.js"
    f.write_text(script, encoding="utf-8")
    done = subprocess.run(["node", str(f)], capture_output=True, text=True,
                          encoding="utf-8")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


# --- (1) the exits row in a fight -------------------------------------------------------
#
# The row's script runs with the spells script beside it, as on the page: since
# 2026-09-29 a click attaches the way into the spell chip's slot (tests/_exits_dom.py).

def _exits_state(fighting: bool) -> dict:
    return exits_dom.exits_state(fighting)


def _run_exits(tmp_path, steps: str) -> dict:
    return exits_dom.run(tmp_path, steps)


@needs_node
def test_in_a_fight_every_open_way_says_it_is_a_withdraw_and_the_shut_one_does_not(tmp_path):
    """Measured before: mid-fight the row was the quiet street's row, "the arena · a few
    minutes" and nothing else. Now each open way carries the mark and the full sentence
    for a screen reader; a shut way stays shut and unmarked, because it cannot be taken.

    The mark read "provokes" until the engine rolled it (tests/test_leaving_provokes.py):
    leaving is a withdraw, so one visible foe beside you gets no swing and the mark
    promising one on every way would have been wrong the other way round."""
    got = _run_exits(tmp_path, f"""
      renderAll({json.dumps(_exits_state(True))});
      const fight = BOX.innerHTML, fightClass = [...BOX.classList.on];
      renderAll({json.dumps(_exits_state(False))});
      done({{ fight, fightClass, calm: BOX.innerHTML }});
    """)
    buttons = re.findall(r"<button[^>]*class=\"exitbtn[^\"]*\"[^>]*>.*?</button>",
                         got["fight"], re.S)
    assert len(buttons) == 3
    arena, gate, road = buttons
    for open_way in (arena, road):
        assert "risky" in open_way and ">withdraw<" in open_way
        assert "leaving the fight is a withdraw" in open_way
        assert 'aria-pressed="false"' in open_way, "a toggle: it attaches, it does not go"
    assert "shut" in gate and "withdraw" not in gate and "aria-pressed" not in gate
    assert "fighting" in got["fightClass"]
    assert "withdraw" not in got["calm"], "out of a fight the row is the quiet row"


@needs_node
def test_mid_fight_a_click_attaches_a_withdraw_chip_whose_line_says_what_it_costs(tmp_path):
    """The journeys asked before spending days, and a walk out of a fight asked "Leave the
    fight?" on a line under the row that a second click answered. Since the owner's
    "attach like a spell does and then apply when you send" (2026-09-29) the click sends
    nothing: it attaches a Withdraw chip, and the confirm line's sentence is held visibly
    under the chip. Say is the second step. Out of a fight the same way is a Go chip with
    no line under it."""
    got = _run_exits(tmp_path, f"""
      renderAll({json.dumps(_exits_state(True))});
      click("p:arena");
      const fight = ELS.attachments.innerHTML, sentAfterClick = SENT.length;
      const fightSay = sayBody();
      removeAttachment({{ announce: false }});
      renderAll({json.dumps(_exits_state(False))});
      click("p:arena");
      done({{ fight, sentAfterClick, fightSay, calm: ELS.attachments.innerHTML,
              calmSay: sayBody() }});
    """)
    assert got["sentAfterClick"] == 0, "a click attaches; it does not send a turn"
    assert ">Withdraw<" in got["fight"] and ">the arena<" in got["fight"]
    assert 'class="att-note"' in got["fight"], "the line is visible, not screen-reader only"
    assert "Leaving the fight is a withdraw" in got["fight"]
    assert "whose reach covers your way out still strikes" in got["fight"]
    assert got["fightSay"]["attachments"] == [{"kind": "place", "id": "p:arena"}]
    assert ">Go<" in got["calm"] and "att-note" not in got["calm"]
    assert got["calmSay"] == {"text": "", "attachments": [{"kind": "place", "id": "p:arena"}]}


@needs_node
def test_a_withdraw_chip_left_attached_when_the_fight_ends_becomes_a_walk(tmp_path):
    """A withdraw line with no fight under it would be a warning about nothing; the next
    state that is not a fight makes the chip a Go chip and takes the line away (a
    journey's line of days would stay)."""
    got = _run_exits(tmp_path, f"""
      renderAll({json.dumps(_exits_state(True))});
      click("p:arena");
      renderAll({json.dumps(_exits_state(False))});
      done({{ html: ELS.attachments.innerHTML, chip: attachedChip() }});
    """)
    assert got["chip"]["label"] == "Go" and got["chip"]["note"] == ""
    assert "withdraw" not in got["html"].lower()


@needs_node
def test_a_fight_on_a_journey_says_both_and_still_confirms_the_journey(tmp_path):
    """Leaving a fight by the road is both things: the chip's line names the withdraw and
    the days, and Say carries `confirmed`, which the server demands of a journey
    (play/views.py `_read_place`)."""
    got = _run_exits(tmp_path, f"""
      renderAll({json.dumps(_exits_state(True))});
      click("r:north");
      done({{ html: ELS.attachments.innerHTML, say: sayBody() }});
    """)
    assert "Leaving the fight is a withdraw" in got["html"]
    assert "About three days on foot; the days pass on the road." in got["html"]
    assert got["say"]["attachments"] == [
        {"kind": "place", "id": "r:north", "confirmed": True}]


def test_the_fight_mark_is_styled_readably_and_without_dashes_or_motion():
    """The mark wears the combat bar's colours: #e8b0a8 text (about 9:1 on the button's
    leather) and the --alarm border. The page's --alarm as TEXT measures 3.3:1 there,
    under WCAG AA, which is why it is only the border."""
    page = _read(PAGE)
    block = page[page.index("#exits .exitbtn.risky"):page.index("body.resolving #exits button")]
    assert "border-color: var(--alarm)" in block
    assert re.search(r"\.ex-risk \{[^}]*color: #e8b0a8", block)
    assert "animation" not in block and "transition" not in block
    code = _read(TABLE / "11-exits.js")
    lines = [ln for ln in code.splitlines() if not ln.lstrip().startswith("//")]
    for bad in ("—", "–", "→", "←"):
        assert not any(bad in ln for ln in lines), bad


# --- (6) the sheet at phone width ----------------------------------------------------------
# The sheet's own header (sigil, name, Close) and its strip of twelve pages went with the
# table rebuild's stage 2: the design has no strip, each tab is its own page, and the name
# is the left panel's (docs/table-rebuild-inventory.md, H4 and H18). What those tests held
# that still applies is held here.

def test_the_sheet_column_is_held_to_the_screen_and_its_strip_is_gone():
    """458px of `auto` column on a 375px screen, and tabs shrunk to two letters, were one
    defect seen twice: the column sized to its widest child, and the only thing that
    could give was the tab labels. The column is still held; the strip is gone, by the
    ruling its inventory row cites, so it cannot shrink again."""
    page = _read(PAGE)
    assert "#sheetpanel { grid-template-columns: minmax(0, 1fr); }" in page
    assert 'id="sheettabs"' not in page
    assert "function sheetTabEdges(" not in _read(TABLE / "05-sheet.js")


def _phone_block() -> str:
    page = _read(PAGE)
    start = page.index("--- The sheet on a phone")
    return page[start:page.index("  .cols {", start)]


def test_the_sheet_note_gives_the_prompt_and_an_error_their_own_lines_on_a_phone():
    """Close was off the right edge at 375px while the sheet had a header. What sat in it
    and still has something to say (the gender prompt, a refusal) is the note line above
    every sheet page now, and on a phone each takes a full line of its own."""
    block = _phone_block()
    assert "@media (max-width: 760px)" in block
    for full in ("#genderask", "#sheeterr"):
        assert re.search(re.escape(full) + r" \{[^}]*flex-basis: 100%", block), full


def test_the_gender_prompt_is_styled_in_the_stylesheet_not_inline():
    """Its inline `flex: 1` beat every stylesheet rule, so the phone block could not
    give it a line of its own. The declaration moved to table.html unchanged."""
    code = _read(TABLE / "05-sheet.js")
    ask = code[code.index("function askGender("):]
    ask = ask[:ask.index("\n}\n")]
    assert "style.cssText" not in ask
    assert re.search(r"#genderask \{ flex: 1; display: flex;", _read(PAGE))


def test_the_prompt_goes_in_the_sheets_own_note_not_the_counters_header():
    """Found measuring the phone header: the sheet's sigil was 0x0 because the bare
    `$(".sheethead")` matched the trade panel's header, which is earlier in the page, so
    the counter wore the sheet's sigil. The sigil is gone; the prompt it sat beside is
    scoped to the sheet panel the same way."""
    code = _read(TABLE / "05-sheet.js")
    ask = code[code.index("function askGender("):]
    ask = ask[:ask.index("\n}\n")]
    assert '$("#sheetpanel #sheetnote")' in ask
    assert '$(".sheethead")' not in code


# --- (8) the 3D map draws the spell areas --------------------------------------------------

def _render3d(tmp_path, grid: dict, actors: list, opts: dict) -> str:
    code = _read(SCENE3D)
    out = _node(tmp_path, "const window = {};\n" + code + f"""
      console.log(JSON.stringify({{ svg: window.Scene3D.render(
        {json.dumps(grid)}, {json.dumps(actors)}, {json.dumps(opts)}) }}));
    """)
    return out["svg"]


def _grid(**extra) -> dict:
    g = {"width": 6, "height": 6, "blocked": [], "difficult": [], "obscuring": [],
         "floor": [], "parapet": [], "reachable": [[2, 2, 5, 0]]}
    g.update(extra)
    return g


_CONE = {"spell": "burning-hands",
         "cells": [[2, 2, 0], [2, 2, 1], [3, 2, 0], [3, 3, 0], [1, 1, 3]]}


@needs_node
def test_the_3d_view_draws_the_latest_areas_in_the_flat_maps_tint(tmp_path):
    """One square per column, by the flat board's rule: a column with a cell on the
    level being looked at is filled (#e0701e at .32); a column whose only cell is 15 ft
    up is a dashed outline. The stroke goes in a style, because `#view3d polygon` sets
    every face's stroke in the stylesheet and a presentation attribute would lose."""
    svg = _render3d(tmp_path, _grid(areas=[_CONE]), [], {"turn": 0, "level": 0})
    areas = re.findall(r'<polygon class="spellarea3[^"]*"[^>]*>.*?</polygon>', svg)
    assert len(areas) == 4, "(2,2) is one square though the cone fills it twice"
    filled = [a for a in areas if "offlevel" not in a]
    dashed = [a for a in areas if "offlevel" in a]
    assert len(filled) == 3 and len(dashed) == 1
    for a in areas:
        assert 'fill="#e0701e"' in a and 'pointer-events="none"' in a
        assert "stroke:#f0a050" in a and "<title>burning hands" in a
    assert all('fill-opacity="0.32"' in a for a in filled)
    assert 'fill-opacity="0"' in dashed[0] and "stroke-dasharray:3 2" in dashed[0]
    assert "above or below this floor" in dashed[0]


@needs_node
def test_an_area_lies_over_its_tile_and_under_whoever_stands_in_it(tmp_path):
    """Lifted a hair off the floor, so the depth sort draws it after its own tile (or the
    tile would paint over it) and before the walls of a figure standing there (or it
    would paint over them). Held at all four quarter-turns, as the depth sort is."""
    grid = _grid(areas=[{"spell": "burning-hands", "cells": [[2, 2, 0]]}])
    actors = [{"name": "Bandit", "at": [2, 2], "hp": 5, "hp_max": 5, "side": "foe"}]
    for turn in range(4):
        svg = _render3d(tmp_path, grid, actors, {"turn": turn, "level": 0})
        polys = re.findall(r'<polygon class="([^"]*)"[^>]*points="([^"]+)"', svg)
        area = next(i for i, (cls, _) in enumerate(polys) if cls.startswith("spellarea3"))
        tile = _nearest_tile_top(polys, polys[area][1])
        figure_top = max(i for i, (cls, _) in enumerate(polys) if cls.startswith("fig"))
        assert tile < area < figure_top, turn


def _centre(points: str) -> tuple[float, float]:
    xs, ys = zip(*(map(float, p.split(",")) for p in points.split()))
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _nearest_tile_top(polys, area_points: str) -> int:
    """The top face of the area's own square: the tile top whose projected centre is
    nearest the area's (the same square, 0.02 of a level lower)."""
    ax, ay = _centre(area_points)
    tops = [(i, _centre(p)) for i, (cls, p) in enumerate(polys)
            if cls.startswith("tile") and "face-top" in cls]
    return min(tops, key=lambda t: (t[1][0] - ax) ** 2 + (t[1][1] - ay) ** 2)[0]


@needs_node
def test_no_areas_draws_nothing_extra(tmp_path):
    """The view adds no facts: with `areas` absent or empty the board is byte-identical,
    and no spell polygon appears."""
    plain = _render3d(tmp_path, _grid(), [], {"turn": 1})
    empty = _render3d(tmp_path, _grid(areas=[]), [], {"turn": 1})
    assert plain == empty and "spellarea3" not in plain
