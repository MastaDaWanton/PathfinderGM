"""Two overlaps the owner screenshotted on 0.2.12 (2026-10-09), held by the layout rules.

1. The forge's choice cards. The ornate frame (`.card::after`) reaches past every card,
   and a druid's Nature's Bond is two grids, the choice and then its domains or animals,
   with nothing between them: "A cleric domain" and "An animal companion" laid their
   bottom bosses across the tops of "Air", "Animal" and "Earth". Measured in Chrome on a
   scratch server at 375, 770 (the owner's window), 1024, 1440 and 1920, every class:
   the druid's two grids touched at 0px, so the bosses lay 10px over the next row and the
   two frames crossed by 20px, at every width; the note under a chosen bloodline's or
   bond's cards ("Draconic, dragon type:", "Familiar, familiar:", the companion's name)
   sat under the bosses the same way; the house rules' lone Core races switch stood 8px
   under the race tiers. After: none, at every width, for the druid (domain and animal),
   sorcerer (and draconic's dragon types), wizard (and the familiar), ranger and cleric.
   The cards' heights were never the cause: the grid rows size to their content.

2. The table's top bar. Its three tracks (`minmax(0, 1fr) auto minmax(0, 1fr)`, and
   `auto minmax(0, 1fr) auto` under 1181px) could each shrink below what they held, so a
   narrow window put one control on another. Swept every 5px from 375 to 1920 with a
   caster's Spells tab and Talk's "2 new": 152 of 310 widths overlapped (Talk over Trade
   and Journal from 1185 to 1550px, Worlds & characters under Table and Map from 765 to
   1070px, the device over the world's name and a 28px sideways page scroll at 375px).
   After: 0 of 310, no sideways scroll at any width, focus order unchanged.

3. The bar's second line. Wrapping cured the overlap, but with Spells and "2 new" the end
   group fell to a line of its own from 761 to 1102px and from 1181 to 1220px, the bar
   60px tall becoming 108 (the book 315px tall at 1024x768 instead of 364). The owner
   (2026-10-09): give Talk, Music, Settings and the toggle their phone size at mid widths.
   Measured with headless Chrome on a scratch server, every 5px from 375 to 1920 and every
   1px from 761 to 1300: the bar needed 1103px under 1181 and 1221px above; with the end
   group at phone sides and tracking under 1241px (473px to 380) and the tabs at the
   phone's type under 1181 (481px to 451) it needs 980 and 1127. It is one row from 980px
   up: 59.5px tall at 1024 (was 108.4), 61 at 1200 (was 109.4); 0 of 310 widths overlap,
   none scroll sideways, the tab key's order is the same, and every word is the same.

4. The story over End turn (integrate/0.2.25 and master 0.2.24 alike, 2026-10-30). In a fight
   at 794x608 with four rows of people in the book's head, the story's box (never shorter
   than its 44px of padding) ran 65px below the leaf, and the leaf is laid over the desk:
   a real click on End turn's visible part landed on `p.beat` and the turn did not end.
   tools/table_hit_test.js caught it only when End turn happened to be scrolled into the
   desk's 17px strip of choices; scrolled out, it was never checked at all.

There is no layout engine in the suite, so these hold the rules the measurements came
from: the frame's reach is computed from the same numbers the browser uses, and the bar
is held to the shape that cannot overlap (a wrapping flex row whose parts keep their own
widths).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest
from django.test import Client

from pagesource import ROOT, TABLE

HOME = ROOT / "play" / "templates" / "play" / "home.html"
THEME = ROOT / "play" / "static" / "css" / "theme-v2.css"


def _style(path: Path) -> str:
    src = path.read_text(encoding="utf-8")
    return src[src.index("<style>"):src.index("</style>")]


def _rules(css: str, selector: str) -> list[str]:
    """Every block for exactly this selector, in source order."""
    pat = re.compile(r"(?:^|\n)\s*" + re.escape(selector) + r"\s*\{([^}]*)\}")
    return [m.group(1) for m in pat.finditer(css)]


def _px(block: str, prop: str) -> list[float]:
    m = re.search(r"(?:^|[;{\s])" + re.escape(prop) + r":\s*([^;]+);", block)
    assert m, f"no {prop} in {block!r}"
    return [float(v) for v in re.findall(r"(-?[\d.]+)px", m.group(1))]


def _reach_and_lift() -> tuple[float, float]:
    """How far the frame's metal stands past a card's border edge, and how far a card
    rises on hover, from the numbers the page itself uses."""
    css = _style(HOME)
    after = [b for b in _rules(css, ".card::after") if "inset:" in b][-1]
    inset = -_px(after, "inset")[0]                       # 35: from the padding edge
    card = [b for b in _rules(css, ".card") if "border:" in b][0]
    border = float(re.search(r"border:\s*([\d.]+)px", card).group(1))
    theme = THEME.read_text(encoding="utf-8")
    boss_in = float(re.search(r"--boss-in:\s*([\d.]+)px", theme).group(1))
    clasp_in = float(re.search(r"--clasp-in-y:\s*([\d.]+)px", theme).group(1))
    reach = inset - border - min(boss_in, clasp_in)       # 35 - 1 - 24 = 10
    hover = [b for b in _rules(css, ".card.pick:hover") if "translateY" in b][0]
    lift = -float(re.search(r"translateY\((-?[\d.]+)px\)", hover).group(1))
    return reach, lift


def test_the_frames_reach_is_what_was_measured():
    """The bosses sit 10px past the card (the frame's box 34px out, the boss 24px in),
    and a picked card lifts 4px on hover: the two numbers every clearance below is
    measured against. If the frame is re-registered, these move and the rest follow."""
    reach, lift = _reach_and_lift()
    assert reach == 10 and lift == 4


def test_a_card_grid_keeps_clear_of_whatever_stands_beside_it():
    """The note under a chosen bloodline's cards ("Draconic, dragon type:") and the bond's
    name line printed under the bottom bosses (10px of metal over the text, at 375 to
    1920px). A grid's own margin is the frame's reach plus the hover lift, and more: as a
    margin it collapses into a neighbour's larger one, so nothing further off moved."""
    reach, lift = _reach_and_lift()
    css = _style(HOME)
    block = [b for b in _rules(css, ".cards") if "margin-block" in b]
    assert block, ".cards has no margin of its own: text beside a grid runs under its frame"
    assert min(_px(block[-1], "margin-block")) >= reach + lift
    alone = _rules(css, ".card + p")
    assert alone and _px(alone[-1], "margin-top")[0] >= reach + lift, \
        "the note after a lone card (Fade to black) sits under its bosses"


def test_a_grid_after_a_grid_stands_off_by_two_frames():
    """The owner's screenshot: the druid's choice grid and its domain grid touched at 0px,
    so "A cleric domain"'s bottom bosses lay across "Air", "Animal" and "Earth" and the
    frames crossed by 20px. Two grids now stand apart by at least both reaches and a
    lift, and so do the rows and columns inside every grid."""
    reach, lift = _reach_and_lift()
    css = _style(HOME)
    after = _rules(css, ".cards + .cards")
    assert after, "nothing parts one card grid from the next"
    assert _px(after[-1], "margin-top")[0] >= 2 * reach + lift
    for sel in (".cards", ".forge .cards.tight", ".forge .cards.races"):
        gaps = [b for b in _rules(css, sel) if re.search(r"(?:^|[;\s])gap:", b)]
        assert gaps, sel
        assert min(_px(gaps[-1], "gap")) >= 2 * reach + lift, sel


def test_the_druids_bond_is_still_two_grids_one_after_the_other():
    """What the clearance is for: the choice's cards, then the domain's or animal's cards,
    each its own `.cards` grid with nothing between. If this ever changes shape the test
    above still holds, but this is the case the owner saw."""
    src = HOME.read_text(encoding="utf-8")
    fn = src[src.index("function classChoiceSection("):src.index("function domainMatches(")]
    assert re.search(r'const pickDomain = [^`]*`\s*<div class="cards tight">', fn)
    assert re.search(r'const pickAnimal = [^`]*`\s*<div class="cards tight">', fn)
    # Once an option is chosen the "Not chosen yet" note is gone, and the two grids meet.
    assert "${!opt ? `<p" in fn and "${pickDomain}${pickAnimal}" in fn


# --- the table's top bar --------------------------------------------------------------

def _phone(css: str) -> str:
    at = css.index("/* --- Phone: the story is the page")
    return css[at:css.index("\n  }\n", at)]


def test_the_top_bar_wraps_rather_than_overlapping():
    """152 of 310 widths from 375 to 1920 put one of the bar's controls on another (Talk
    over Trade and Journal at 1185 to 1550px, as in the owner's screenshot; Worlds &
    characters under Table and Map at 765 to 1070px). Each grid track could shrink below
    what it held. The bar is a wrapping flex row now, and no rule gives it tracks back."""
    css = _style(TABLE)
    bar = _rules(css, ".topbar")
    assert "display: flex; flex-wrap: wrap;" in bar[0]
    assert "min-width: 0" in bar[0], \
        "the page grid sizes the bar to its widest part: 440px on a 375px phone"
    for block in bar:
        assert "grid-template" not in block, "the top bar has grid tracks again"


def test_each_part_of_the_bar_keeps_its_own_width():
    """A part that may shrink below its content is a part something else is drawn over.
    The way out keeps its one line (`min-width: 0` on .worldnav let it fall to nothing
    under the tabs), the world's name is contained so a long one never forces a wrap,
    the end group keeps its words on one line so its width is honest when the row
    decides to wrap, and the tabs never shrink at all above the phone."""
    css = _style(TABLE)
    nav = _rules(css, ".worldnav")[0]
    assert "min-width: 0" not in nav and "flex: 1 1 0" in nav
    assert "white-space: nowrap" in _rules(css, ".leave")[0]
    world = _rules(css, ".world")[0]
    assert "contain: inline-size" in world and "text-overflow: ellipsis" in world
    end = _rules(css, ".topend")[0]
    assert "flex: 1 1 0" in end and "white-space: nowrap" in end
    assert "flex: none" in _rules(css, ".modes")[0]


def test_on_a_phone_the_tabs_take_their_own_line_and_scroll():
    """At 375px with Talk's "2 new" the bar was 403px wide (a 28px sideways page scroll,
    Settings cut off) and the device lay over Worlds & characters from 375 to 445px. The
    first line now wraps Talk's group under the world's name when it does not fit, and
    the tabs keep a line of their own that scrolls."""
    phone = _phone(_style(TABLE))
    modes = phone[phone.index(".modes {"):]
    modes = modes[:modes.index("}")]
    assert "flex: 1 1 100%" in modes and "min-width: 0" in modes and "overflow-x: auto" in modes
    assert "grid-area" not in phone[:phone.index(".stage")], "a grid area left on the bar"


def _block(css: str, title: str, query: str) -> str:
    """The body of the @media block that follows the section comment `title`, which
    must open with exactly this query."""
    at = css.index("/* --- " + title)
    head = "@media " + query + " {"
    at = css.index("@media ", at)
    assert css.startswith(head, at), f"{title!r} is no longer under {head}"
    return css[at:css.index("\n  }\n", at)]


def test_the_end_group_takes_its_phone_size_where_the_full_one_does_not_fit():
    """With Spells and "2 new" the end group (Talk 127, Music 87, Settings 106, Hide sheet
    129, 473px with its gaps) dropped to a second line from 761 to 1102px and from 1181 to
    1220px: the bar 108px tall at 1024 and 109 at 1200 instead of 60. At phone sides and
    tracking it is 380px (115, 65, 81, 101) and the bar is one row from 980px up. The
    bound has to stand above 1220, the widest width the full-size group wrapped at, and
    the block has no lower bound, so the phone's size is this same rule, not a copy."""
    css = _style(TABLE)
    mid = _block(css, "Mid widths: the bar's end group", "(max-width: 1240px)")
    bound = int(re.search(r"max-width: (\d+)px", mid).group(1))
    assert bound > 1220, "the full-size group wrapped at up to 1220px with the tabs above 1180"
    assert ".topend { gap: 6px; }" in mid
    assert ".talkbtn { min-height: 36px; padding: 6px 12px; }" in mid
    assert ".topend > .v2-btn.is-quiet { min-height: 36px; padding: 6px 10px; " \
           "letter-spacing: .04em; }" in mid
    # The toggle holds its longer label's width, "Show sheet": 101px at the tight
    # tracking. Its desktop 8.6em (129px) here would give back 28 of the 93px saved.
    em = float(re.search(r"#sheettoggle \{ min-width: ([\d.]+)em; \}", mid).group(1))
    assert 6.7 <= em < 8.6, em
    phone = _phone(css)
    for rule in (".talkbtn {", ".topend > .v2-btn.is-quiet {", ".topend { gap"):
        assert rule not in phone, f"a second copy of {rule} on the phone"


def test_under_1181_the_tabs_take_the_phones_type():
    """The last 30px: at 14px and .05em the seven tabs measured 481px and the bar needed
    1010px with the compact end group; at the phone's 13.5px and .04em (keeping 10px
    sides, tighter than the phone's 12) they measure 451 and it needs 980."""
    css = _style(TABLE)
    narrow = _block(css, "Narrower desktops: one sheet column", "(max-width: 1180px)")
    tabs = narrow[narrow.index(".modes > button {"):]
    tabs = tabs[:tabs.index("}")]
    assert "padding: 8px 10px" in tabs and "font-size: 13.5px" in tabs \
        and "letter-spacing: .04em" in tabs
    phone = _phone(css)
    ptabs = phone[phone.index(".modes > button {"):]
    assert "font-size: 13.5px" in ptabs[:ptabs.index("}")]


def test_no_word_on_the_bar_was_shortened():
    """Only sizes changed to keep the bar on one row: every control still says its whole
    name, so nothing needs an aria-label or a hover tooltip to explain a cut-down word."""
    html = Client().get("/play/").content.decode("utf-8")
    bar = html[html.index('<header class="topbar">'):html.index("</header>")]
    words = [re.sub(r"<[^>]+>", "", m).strip()
             for m in re.findall(r"<(?:button|a)\b[^>]*>(.*?)</(?:button|a)>", bar, re.S)]
    assert words == ["Worlds &amp; characters", "Table", "Map", "Sheet", "Equipment",
                     "Spells", "Trade", "Journal", "Talk", "Music", "Settings",
                     "Hide sheet"], words


class _Bar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.order: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "header" and "topbar" in (a.get("class") or ""):
            self.depth = 1
            return
        if self.depth:
            if tag in ("a", "button"):
                self.order.append(a.get("id") or a.get("class") or tag)
            if tag not in ("br", "img", "input"):
                self.depth += 1

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1


def test_the_tab_key_meets_the_bar_in_the_order_it_is_drawn():
    """The fix moves nothing in the page: the way out, the seven tabs, Talk, Music,
    Settings, Hide sheet, in that order, and no `order` above the phone, so the tab key
    still walks the bar left to right, top to bottom, at every width a desktop window
    can take."""
    html = Client().get("/play/").content.decode("utf-8")
    p = _Bar()
    p.feed(html)
    assert p.order == ["leave", "tab-table", "tab-map", "tab-sheet", "tab-equipment",
                       "tab-spells", "tab-trade", "tab-journal", "talktab", "musictoggle",
                       "settingsbtn", "sheettoggle"], p.order
    css = _style(TABLE)
    desktop = css[:css.index("/* --- Phone: the story is the page")]
    for sel in (".topbar", ".worldnav", ".modes", ".topend"):
        for block in _rules(desktop, sel):
            assert "order:" not in block, sel


# --- 4. the story over End turn ------------------------------------------------------------

HIT_TEST = ROOT / "tools" / "table_hit_test.js"
BOOK_JS = ROOT / "play" / "static" / "js" / "table" / "15-book.js"
PACKAGING = ROOT / "docs" / "packaging.md"


def test_the_leaf_draws_nothing_below_itself():
    """At 794x608 with four rows of people in the head, `#story` measured 372-416 against a
    leaf ending at 351, and `.bookin` (z-index 1) laid that 65px over the desk: End turn's
    visible middle answered `p.beat`, and a real click there did not end the turn. The leaf
    clips down, with `clip`, not `hidden`: `hidden` would make the leaf a scroller and clip
    its sides too. The phone keeps a leaf that scrolls, head and all (its own later rule),
    and the book still asks the story's own overflow which box scrolls, so the clip cannot
    change where a beat lands."""
    css = _style(TABLE)
    desktop = css[:css.index("/* --- Phone: the story is the page")]
    assert ".bookin { overflow-y: clip; }" in desktop
    assert not any("overflow-y: hidden" in b or "overflow: hidden" in b
                   for b in _rules(desktop, ".bookin")), "a hidden leaf is a scroller"
    assert ".bookin { display: block; height: 100%; overflow-y: auto; }" in _phone(css), \
        "the phone's leaf must still scroll, and come after the desktop's clip"
    book = BOOK_JS.read_text(encoding="utf-8")
    assert 'getComputedStyle(story).overflowY === "visible"' in book


# The page as measured on integrate/0.2.25 (ae28efe2) at 794x608 in a fight, End turn
# scrolled into the desk's choices: the choices 382-399 (a 17px strip, overflow auto),
# End turn 383-417 in it, and the story's paragraph over its visible middle. And the same
# page at 1366x850, where it all fits. Rects are [left, top, right, bottom].
_HIT_STUB = r"""
const geometry = JSON.parse(process.argv[2]);
const root = {tagName: "HTML", parentElement: null};
const box = (id, cls, tag, parent, rect, overflow) => ({
  id, className: cls, tagName: tag, parentElement: parent, innerText: id, value: "",
  _rect: rect, _overflow: overflow || "visible",
  getBoundingClientRect() { const [l, t, r, b] = this._rect;
    return {left: l, top: t, right: r, bottom: b, width: r - l, height: b - t}; },
  getClientRects() { return [this.getBoundingClientRect()]; },
  getAttribute() { return null; }, closest() { return null; },
  contains(o) { for (let p = o; p; p = p.parentElement) if (p === this) return true; return false; },
});
const g = geometry;
const body = box("", "", "BODY", root, [0, 0, g.vw, g.vh]);
const desk = box("desk", "desk", "SECTION", body, g.desk);
const choices = box("", "choices", "DIV", desk, g.choices, "auto");
const bar = box("combatbar", "", "DIV", choices, g.bar);
const end = box("cb-end", "v2-btn", "BUTTON", bar, g.end);
const commit = box("cb-commit", "v2-btn", "BUTTON", bar, g.commit);
const form = box("sayform", "pen", "FORM", desk, g.say);
const input = box("input", "v2-well", "INPUT", form, g.input);
const say = box("", "v2-btn", "BUTTON", form, g.sayButton);
const story = box("story", "story", "DIV", body, g.story, "auto");
const beat = box("", "beat setup fresh", "P", story, g.story);
document.documentElement = root;
const all = [end, commit, input, say];
document.querySelectorAll = (sel) => ({
  "#cb-end": [end], "#cb-commit": [commit], "#input": [input],
  "#sayform button[type=submit]": [say]})[sel] || all;
global.getComputedStyle = (el) => ({display: "block", visibility: "visible",
  pointerEvents: "auto", overflowX: el._overflow, overflowY: el._overflow});
const inside = (el, x, y) => { const r = el.getBoundingClientRect();
  return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom; };
document.elementFromPoint = (x, y) => {
  if (g.storyOnTop && inside(story, x, y)) return beat;
  for (const el of all) if (inside(el, x, y)) return el;
  return body;
};
global.innerWidth = g.vw; global.innerHeight = g.vh;
console.log(JSON.stringify(eval(require("fs").readFileSync(process.argv[3], "utf8"))));
"""

_AT_794 = {"vw": 794, "vh": 608, "desk": [318, 367, 774, 592],
           "choices": [335, 382, 757, 399], "bar": [335, 147, 747, 502],
           "end": [350, 383, 438, 417], "commit": [620, 343, 732, 377],
           "say": [335, 409, 757, 565], "input": [335, 459, 661, 511],
           "sayButton": [669, 459, 757, 511], "story": [318, 372, 774, 416],
           "storyOnTop": True}
_AT_1366 = {"vw": 1366, "vh": 850, "desk": [300, 462, 1060, 834],
            "choices": [316, 477, 1044, 714], "bar": [316, 477, 1044, 832],
            "end": [350, 636, 438, 670], "commit": [900, 590, 1010, 624],
            "say": [316, 724, 1044, 818], "input": [316, 760, 800, 812],
            "sayButton": [810, 760, 900, 812], "story": [300, 200, 1060, 446],
            "storyOnTop": True}


def _hit_test(tmp_path, geometry: dict) -> dict:
    stub = tmp_path / "stub.js"
    stub.write_text("const document = {}; global.document = document;\n" + _HIT_STUB,
                    encoding="utf-8")
    done = subprocess.run(["node", str(stub), json.dumps(geometry), str(HIT_TEST)],
                          capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on this machine")
def test_the_hit_test_names_the_story_over_end_turn_and_the_strip_it_sits_in(tmp_path):
    """The release hit test, run over the measured 794x608 page: it must name End turn as
    covered by the story's paragraph, and name End turn and Commit turn as unreachable, a
    34px button in a 17px box that no scroll shows whole (a mouse wheel's 100px step
    skipped past it live). Before, a control scrolled out of its box was never checked, so
    the same page with End turn scrolled away passed clean. Over the page at 1366x850,
    where everything fits, it must pass."""
    out = _hit_test(tmp_path, _AT_794)
    assert {"control": "#cb-end", "label": "cb-end", "under": "p.beat.setup.fresh"} \
        in out["covered"]
    gone = {u["control"]: u for u in out["unreachable"]}
    assert gone["#cb-end"] == {"control": "#cb-end", "box": 17, "of": 34}
    assert gone["#cb-commit"]["box"] == 17
    assert "#input" not in gone
    wide = _hit_test(tmp_path, _AT_1366)
    assert wide["covered"] == [] and wide["unreachable"] == [] and wide["checked"] == 4


def test_a_release_needs_both_lists_empty():
    """The release step reads the hit test's answer; a step that still said only `covered`
    would let a turn's buttons squeezed out of reach ship."""
    src = HIT_TEST.read_text(encoding="utf-8")
    assert ('const MUST_SHOW = ["#cb-commit", "#cb-end", "#input", '
            '"#sayform button[type=submit]"];') in src
    assert "return {checked: seen.length, covered, unreachable};" in src
    step = " ".join(PACKAGING.read_text(encoding="utf-8").split())
    assert "`covered` and `unreachable` must both be empty" in step
