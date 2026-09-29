"""Pre-release polish, the page's side (G3 leftovers, docs/fix-interfaces.md §3.4, items 1,
6 and 8). What each test holds, and what was measured before it:

  (1) The exits row mid-fight. The row offered "the arena · a few minutes" during an
      encounter exactly as it did in a quiet street, one click from walking out. In a
      fight every open way is now marked "provokes" and the first click asks "Leave the
      fight?" before the second goes, the journeys' own confirm idiom. The page reads
      `scene.in_encounter`; it works out nothing about who threatens whom.

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

# Just enough of a page for 11-exits.js to run: one #exits box, a click listener caught,
# and `takeTurn` recorded instead of sent.
_EXITS_PRELUDE = r"""
const BOX = { hidden: true, innerHTML: "", classList: { on: new Set(),
  toggle(c, v) { v ? this.on.add(c) : this.on.delete(c); } } };
const LISTENERS = {};
const document = {
  getElementById: id => id === "exits" ? BOX : null,
  querySelector: () => null,
  addEventListener: (t, f) => { LISTENERS[t] = f; },
};
const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
  .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const SENT = [];
function takeTurn(body) { SENT.push(body); }
function onRender() {}
let STATE = null;
function click(id) {
  const btn = { dataset: { exit: id }, getAttribute: () => null };
  LISTENERS.click({ target: { closest: sel => sel.includes(".exitbtn") ? btn : null } });
}
"""


def _exits_state(fighting: bool) -> dict:
    return {"scene": {"in_encounter": fighting, "exits": [
        {"id": "p:arena", "name": "the arena", "group": "next_door",
         "time_words": "a few minutes' walk", "blocked": "", "journey": False},
        {"id": "p:gate", "name": "the gate", "group": "outside",
         "time_words": "a few minutes' walk", "blocked": "The watch has your name.",
         "journey": False},
        {"id": "r:north", "name": "the north road", "group": "road",
         "time_words": "about three days on foot", "blocked": "", "journey": True},
    ]}}


def _run_exits(tmp_path, steps: str) -> dict:
    code = _read(TABLE / "11-exits.js")
    return _node(tmp_path, _EXITS_PRELUDE + code + "\n" + steps)


@needs_node
def test_in_a_fight_every_open_way_says_it_provokes_and_the_shut_one_does_not(tmp_path):
    """Measured before: mid-fight the row was the quiet street's row, "the arena · a few
    minutes" and nothing else. Now each open way carries the mark and the full sentence
    for a screen reader; a shut way stays shut and unmarked, because it cannot be taken."""
    got = _run_exits(tmp_path, f"""
      STATE = {json.dumps(_exits_state(True))};
      renderExits(STATE);
      const fight = BOX.innerHTML, fightClass = [...BOX.classList.on];
      STATE = {json.dumps(_exits_state(False))};
      renderExits(STATE);
      console.log(JSON.stringify({{ fight, fightClass, calm: BOX.innerHTML }}));
    """)
    buttons = re.findall(r"<button[^>]*class=\"exitbtn[^\"]*\"[^>]*>.*?</button>",
                         got["fight"], re.S)
    assert len(buttons) == 3
    arena, gate, road = buttons
    for open_way in (arena, road):
        assert "risky" in open_way and ">provokes<" in open_way
        assert "leaving the fight provokes attacks of opportunity" in open_way
        assert 'aria-expanded="false"' in open_way, "it asks before it goes"
    assert "shut" in gate and "provokes" not in gate
    assert "fighting" in got["fightClass"]
    assert "provokes" not in got["calm"], "out of a fight the row is the quiet row"


@needs_node
def test_mid_fight_the_first_click_asks_and_only_the_second_leaves(tmp_path):
    """The journeys already asked before spending days; a walk out of a fight asked
    nothing. First click: the "Leave the fight?" line and no turn sent. Second click on
    the same way: one turn, "I go to the arena.", with the place attached. Out of a fight
    the same way goes on the first click, as it always did."""
    got = _run_exits(tmp_path, f"""
      STATE = {json.dumps(_exits_state(True))};
      renderExits(STATE);
      click("p:arena");
      const asked = BOX.innerHTML, sentAfterOne = SENT.length;
      click("p:arena");
      const fightSent = SENT.slice();
      SENT.length = 0;
      STATE = {json.dumps(_exits_state(False))};
      renderExits(STATE);
      click("p:arena");
      console.log(JSON.stringify({{ asked, sentAfterOne, fightSent, calmSent: SENT }}));
    """)
    assert got["sentAfterOne"] == 0
    assert "Leave the fight?" in got["asked"]
    assert "Walking away to the arena provokes an" in got["asked"]
    assert ">Leave</button>" in got["asked"] and ">Stay</button>" in got["asked"]
    assert [s["text"] for s in got["fightSent"]] == ["I go to the arena."]
    assert got["fightSent"][0]["attachments"] == [{"kind": "place", "id": "p:arena"}]
    assert [s["text"] for s in got["calmSent"]] == ["I go to the arena."]


@needs_node
def test_a_question_left_open_when_the_fight_ends_is_closed(tmp_path):
    """A "Leave the fight?" line with no fight under it would be a question about
    nothing; the next state that is not a fight closes it (a journey's would stay)."""
    got = _run_exits(tmp_path, f"""
      STATE = {json.dumps(_exits_state(True))};
      renderExits(STATE);
      click("p:arena");
      STATE = {json.dumps(_exits_state(False))};
      renderExits(STATE);
      console.log(JSON.stringify({{ html: BOX.innerHTML, open: EXIT_CONFIRM }}));
    """)
    assert got["open"] is None
    assert 'id="exits-confirm"' not in got["html"]


@needs_node
def test_a_fight_on_a_journey_says_both_and_still_confirms_the_journey(tmp_path):
    """Leaving a fight by the road is both things: the line names the provocation and
    the days, and the second click carries `confirmed`, which the server demands of a
    journey (play/views.py `_read_place`)."""
    got = _run_exits(tmp_path, f"""
      STATE = {json.dumps(_exits_state(True))};
      renderExits(STATE);
      click("r:north");
      const asked = BOX.innerHTML;
      click("r:north");
      console.log(JSON.stringify({{ asked, sent: SENT }}));
    """)
    assert "Leave the fight?" in got["asked"]
    assert "About three days on foot. The days pass on the road." in got["asked"]
    assert got["sent"][0]["attachments"] == [
        {"kind": "place", "id": "r:north", "confirmed": True}]


def test_the_fight_mark_is_styled_readably_and_without_dashes_or_motion():
    """The mark wears the combat bar's colours: #e8b0a8 text (about 9:1 on the button's
    leather) and the --alarm border. The page's --alarm as TEXT measures 3.3:1 there,
    under WCAG AA, which is why it is only the border."""
    page = _read(PAGE)
    block = page[page.index("#exits .exitbtn.risky"):page.index("#exits .exitgo {")]
    assert "border-color: var(--alarm)" in block
    assert re.search(r"\.ex-risk \{[^}]*color: #e8b0a8", block)
    assert "animation" not in block and "transition" not in block
    code = _read(TABLE / "11-exits.js")
    lines = [ln for ln in code.splitlines() if not ln.lstrip().startswith("//")]
    for bad in ("—", "–", "→", "←"):
        assert not any(bad in ln for ln in lines), bad


# --- (6) the sheet header and tab strip at phone width ------------------------------------

def test_the_sheet_column_is_held_to_the_screen_and_its_tabs_do_not_shrink():
    """458px of `auto` column on a 375px screen, and tabs shrunk to two letters, were one
    defect seen twice: the column sized to its widest child, and the only thing that
    could give was the tab labels. Both halves are held here."""
    page = _read(PAGE)
    assert "#sheetpanel { grid-template-columns: minmax(0, 1fr); }" in page
    assert "#sheettabs button { flex: 0 0 auto; }" in page


def _phone_block() -> str:
    page = _read(PAGE)
    start = page.index("--- The sheet on a phone")
    return page[start:page.index(".sheetbody { overflow-y: auto;", start)]


def test_the_sheet_header_wraps_on_a_phone_with_close_beside_the_name():
    """Close was off the right edge at 375px. On a phone the header wraps: the name
    takes what is left beside Close, and the identity line and anything the sheet has
    to say (the gender prompt, an error) take their own full lines under them."""
    block = _phone_block()
    assert "@media (max-width: 760px)" in block
    assert re.search(r"#sheetpanel \.sheethead \{[^}]*flex-wrap: wrap", block)
    assert re.search(r"#sheetpanel \.sheethead h1 \{[^}]*min-width: 0", block)
    for full in (".meta", "#genderask", "#sheeterr"):
        assert re.search(re.escape(full) + r" \{[^}]*flex-basis: 100%", block), full


def test_the_gender_prompt_is_styled_in_the_stylesheet_not_inline():
    """Its inline `flex: 1` beat every stylesheet rule, so the phone block could not
    give it a line of its own. The declaration moved to table.html unchanged."""
    code = _read(TABLE / "05-sheet.js")
    ask = code[code.index("function askGender("):]
    ask = ask[:ask.index("\n}\n")]
    assert "style.cssText" not in ask
    assert re.search(r"#genderask \{ flex: 1; display: flex;", _read(PAGE))


def test_the_sigil_goes_in_the_sheets_own_header():
    """Found measuring the phone header: the sheet's sigil was 0x0 because the bare
    `$(".sheethead")` matched the trade panel's header, which is earlier in the page, so
    the counter wore the sheet's sigil. The same trap askGender already names."""
    code = _read(TABLE / "05-sheet.js")
    assert '$("#sheetpanel .sheethead").insertAdjacentHTML("afterbegin"' in code
    assert '$(".sheethead").insertAdjacentHTML' not in code


def test_the_tab_strip_scrolls_as_one_row_and_shows_it_has_more():
    """One sideways row with a visible scrollbar and a fade on whichever edge has more
    past it, rather than three or four wrapped rows (about 1285px of labels at 375px)."""
    block = _phone_block()
    assert "scrollbar-width: thin" in block
    for edge in ("#sheettabs.more-right", "#sheettabs.more-left"):
        assert edge in block and "mask-image" in block[block.index(edge):]
    assert "#sheettabs button:focus-visible" in _read(PAGE), \
        "the page's focus ring is a box-shadow the scroller clips; the tab draws its own"


@needs_node
def test_the_strip_fades_only_the_edges_that_have_more(tmp_path):
    """Measured, not assumed: a strip that fits fades nothing; at the start only the
    right edge; in the middle both; at the end only the left."""
    code = _read(TABLE / "05-sheet.js")
    fn = code[code.index("function sheetTabEdges()"):]
    fn = fn[:fn.index("\n}\n") + 3]
    cases = [(375, 375, 0), (1285, 375, 0), (1285, 375, 400), (1285, 375, 910)]
    got = _node(tmp_path, r"""
      const out = [];
      let STRIP;
      const document = { getElementById: () => STRIP };
      """ + fn + f"""
      for (const [sw, cw, left] of {json.dumps(cases)}) {{
        const on = new Set();
        STRIP = {{ scrollWidth: sw, clientWidth: cw, scrollLeft: left,
                  classList: {{ toggle(c, v) {{ v ? on.add(c) : on.delete(c); }} }} }};
        sheetTabEdges();
        out.push([...on].sort());
      }}
      console.log(JSON.stringify(out));
    """)
    assert got == [[], ["more-right"], ["more-left", "more-right"], ["more-left"]]


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
