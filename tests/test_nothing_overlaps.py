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

There is no layout engine in the suite, so these hold the rules the measurements came
from: the frame's reach is computed from the same numbers the browser uses, and the bar
is held to the shape that cannot overlap (a wrapping flex row whose parts keep their own
widths).
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

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
