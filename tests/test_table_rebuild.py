"""The play table rebuild, stage 1 (the shell): what Python and node can hold of it.

The owner's approved design (docs/mock/table-layout/, README in full) was built into
play/templates/play/table.html on the shared theme (play/static/css/theme-v2.css), with
the existing scripts moved and restyled rather than rewritten, and one new script per
tab. docs/table-rebuild-inventory.md lists every feature, control, panel, popover, key and
state the old table had, where each went, and whether stage 1 built it, carried it as it
was for stage 2 or 3, or dropped it by a cited ruling. These tests read that document and
hold the page to it, so the next rebuild cannot lose a thing silently:

  * every row's anchor is on the page if it was built or carried, gone if it was dropped,
    and the sentence that says why is there if it is a gap;
  * every id the old table had is on the new page or named by a dropped row;
  * the brass device answers the three signals the page really has, and holds nothing;
  * the owner's rulings for the shell are in the code, each where it was ruled;
  * everything the page loads is served by the app itself (the packaged exe is offline).

Verified in the running app too (the stage 1 report): real turns against the local
model, the device's timings measured, every tab screenshotted at 1792, 1440, 1024 and 375.
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

from pagesource import ROOT, TABLE, TABLE_SCRIPTS, table_source

INVENTORY = ROOT / "docs" / "table-rebuild-inventory.md"
MOCK = ROOT / "docs" / "mock" / "table-layout"
THEME = ROOT / "play" / "static" / "css" / "theme-v2.css"
STATUSES = {"built", "carried-2", "carried-3", "dropped", "gap"}

# Every id the table carried at `table-rebuild-base` (f3f74b0): the template's own, and
# the ones its scripts write into the page. Measured from that commit when the inventory
# was written; the test below needs each of them on the new page or on a dropped row.
OLD_TEMPLATE_IDS = """abilities attachments board busy carryon cb-ability cb-cast cb-clear cb-commit
cb-coup cb-end cb-free cb-fullatk cb-hint cb-menu cb-plan cb-round cb-strike cb-swift
cb-targets cb-turn clockpop clocksay closesheet closetrade combatbar convo convo-empty
convo-latest convo-log convo-people cp-actions cp-biome cp-biomepick cp-busy cp-debug
cp-desc cp-h cp-hn craftaction craftpanel cursorlight cursorshade deathchoices
deathroster deathtext deathtitle deathveil edgetabs embers err exits gmview input
mapclose maptab maptray maptrayinner mapwrap order panel-map panel-map-body
panel-map-title panel-rolls panel-rolls-body panel-rolls-title panel-scene
panel-scene-body panel-scene-title panel-sheet panel-sheet-body panel-sheet-title
panelbar panelmode panels panelsnone popup rolls sayform saystatus send sheet sheetbody
sheeterr sheetmeta sheetname sheetpanel sheettab sheettabs spellbtn spellpop story
suggestions talk talkclose talktab talktray talktray-title tr-carry-h tr-deal-h
tr-wares-h tradeaction tradego tradelines trademeta trademsg tradename tradepanel
tradepurse tradeshelves tradeshort tradesum tradetill tradetotlab tradewhat tradmine
tradtheirs veil""".split()
OLD_SCRIPT_IDS = """att-note cb-fullok clk-bezel clk-face closeroster convo-earlier cp-forage
exits-why featq featresults gx-count gx-list levelerr levelup map mapopen openroster
opensheet resurrectbtn sheethead-sigil spelldetail-h spellpick-find spellsay sx-today
sx-today-h sx-today-hint takeleave unithatch-foe unithatch-quiet genderask glosscard
spelldetail""".split()


def _rows() -> list[dict]:
    """The inventory's table rows: #, item, where, stage 1, anchors (every backticked
    literal in the last column)."""
    rows = []
    for line in INVENTORY.read_text(encoding="utf-8").splitlines():
        if not re.match(r"\| [A-Z]\d+ \|", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        assert len(cells) == 5, line
        anchors = re.findall(r"`([^`]+)`", cells[4])
        rows.append({"id": cells[0], "item": cells[1], "where": cells[2],
                     "status": cells[3], "anchors": anchors, "line": line})
    return rows


def _code(js: str) -> str:
    """A script without its comments: a dropped id named in a comment is history."""
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return "\n".join(ln.split("//", 1)[0] if "://" not in ln else ln for ln in js.splitlines())


def _scripts_code() -> str:
    return "\n".join(_code(p.read_text(encoding="utf-8")) for p in sorted(TABLE_SCRIPTS.glob("*.js")))


def _template_code() -> str:
    return re.sub(r"<!--.*?-->", "", TABLE.read_text(encoding="utf-8"), flags=re.S)


class _Tree(HTMLParser):
    VOID = {"input", "br", "img", "meta", "link", "hr", "source", "path", "circle", "rect"}

    def __init__(self):
        super().__init__()
        self.stack, self.elements = [], []

    def handle_starttag(self, tag, attrs):
        el = {"tag": tag, "attrs": dict(attrs), "ancestors": list(self.stack)}
        self.elements.append(el)
        if tag not in self.VOID:
            self.stack.append(el)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                break


@pytest.fixture(scope="module")
def page():
    html = Client().get("/play/").content.decode("utf-8")
    tree = _Tree()
    tree.feed(html)
    return html, tree.elements


def _by_id(els, i):
    return [e for e in els if e["attrs"].get("id") == i]


def _one(els, i):
    found = _by_id(els, i)
    assert len(found) == 1, (i, len(found))
    return found[0]


# --- the inventory ------------------------------------------------------------------------

def test_the_inventory_covers_what_the_brief_asked_it_to():
    """The brief named the ground the inventory must cover; a section that quietly went
    missing is how a whole family of controls disappears unnoticed. Each area has at
    least one row, and every row has a status from the five the document defines."""
    rows = _rows()
    assert len(rows) >= 120, f"only {len(rows)} rows: the parse has gone stale"
    bad = [r["line"] for r in rows if r["status"] not in STATUSES or not r["anchors"]]
    assert not bad, bad
    text = " ".join(r["item"] + " " + r["where"] for r in rows).lower()
    for area in ("transcript", "say box", "continue", "craft action", "spells", "chip",
                 "backspace", "esc", "unfinished", "422", "suggestions", "exits row",
                 "withdraw", "42px", "combat bar", "strike", "full attack", "coup de grace",
                 "commit turn", "end turn", "targets", "die", "own die", "clock", "ignore",
                 "take your leave", "new-lines", "rolls", "flat board", "3d board", "floors",
                 "full sheet", "spells page", "trade window", "quest log", "downed",
                 "ended state", "/gm", "/cheat", "free actions", "phone drawer", "edge tabs",
                 "device", "worlds & characters", "crafting bench", "hide sheet"):
        assert area in text, f"nothing in the inventory is about {area!r}"


def test_every_built_or_carried_item_is_on_the_page():
    """Built means working in the new design, carried means working as it was: either
    way its anchor (the id, the function, the sentence) is in the template or the scripts
    the page loads. An anchor that is not is a row that promises what the page lacks."""
    source = table_source()
    missing = [(r["id"], a) for r in _rows() if r["status"] in {"built", "carried-2", "carried-3"}
               for a in r["anchors"] if a not in source]
    assert not missing, missing


def test_every_dropped_item_is_gone_and_cites_its_ruling():
    """Dropped means gone, by a ruling of the owner's the row cites (the mock README or
    fix-interfaces §3.4). Left in the markup it is a control that does nothing, which is
    worse than either keeping it or removing it."""
    code = _template_code() + "\n" + _scripts_code()
    for r in _rows():
        if r["status"] != "dropped":
            continue
        assert re.search(r"README|FI 3\.4|became|moved|the design has no|replaced", r["where"]), \
            f"{r['id']} is dropped without a reason: {r['where']}"
        for a in r["anchors"]:
            assert a not in code, f"{r['id']}: {a!r} is still in the page's code"


def test_every_gap_says_why_on_the_page():
    """A gap is a thing the design shows and the engine or the app cannot: the owner's
    rule is a visible reason, not a hidden control. The sentence is the anchor."""
    source = table_source()
    for r in _rows():
        if r["status"] == "gap":
            for a in r["anchors"]:
                assert a in source, f"{r['id']}: the page does not say {a!r}"


def test_no_old_id_disappeared_without_a_row():
    """Every id the old table had (template and scripts, measured at table-rebuild-base)
    is on the new page, or is named by a dropped row. This is the test that fails when a
    rebuild loses something nobody listed."""
    source = table_source()
    dropped = {a for r in _rows() if r["status"] == "dropped" for a in r["anchors"]}
    lost = []
    for i in OLD_TEMPLATE_IDS + OLD_SCRIPT_IDS:
        present = (f'id="{i}"' in source or f'id = "{i}"' in source
                   or f"id=\"{i}\"" in source)
        if not present and f'id="{i}"' not in dropped:
            lost.append(i)
    assert not lost, f"gone from the page with no dropped row: {lost}"


# --- the shell ----------------------------------------------------------------------------

def test_every_tab_opens_a_page_that_is_there(page):
    """Seven word tabs, each controlling a container that exists; the pages that share the
    stage point at it. Spells starts hidden (a caster's only) and is still a real tab."""
    _, els = page
    tabs = [e for e in els if e["attrs"].get("role") == "tab" and e["attrs"].get("data-mode")]
    modes = [t["attrs"]["data-mode"] for t in tabs]
    assert modes == ["table", "map", "sheet", "equipment", "spells", "trade", "journal"]
    for t in tabs:
        ctl = t["attrs"].get("aria-controls")
        assert ctl and len(_by_id(els, ctl)) == 1, (t["attrs"]["id"], ctl)
    assert "hidden" in _one(els, "tab-spells")["attrs"]
    selected = [t for t in tabs if t["attrs"].get("aria-selected") == "true"]
    assert [t["attrs"]["data-mode"] for t in selected] == ["table"]
    shell = (TABLE_SCRIPTS / "12-shell.js").read_text(encoding="utf-8")
    for key in ("ArrowRight", "ArrowLeft", "Home", "End"):
        assert f'"{key}"' in shell, key
    for n, m in enumerate(("map", "sheet", "equipment", "spells", "trade", "journal"), 16):
        tab = next(TABLE_SCRIPTS.glob(f"{n}-tab-{m}.js"))
        assert f'Shell.tab("{m}"' in tab.read_text(encoding="utf-8"), tab.name


def test_the_stage_holds_what_the_design_puts_on_it(page):
    """The three columns and what sits in each, as the approved design has them: who on
    the left (portrait frame, name, In hand and worn, the Equipment and Crafting bench
    doors), the book with its head row, the desk with the pen, the numbers on the right;
    the device on the stage itself, not in the book, so it is on Map and Sheet too."""
    _, els = page
    stage = _one(els, "stage")
    assert stage["tag"] == "main" and "stage" in stage["attrs"]["class"].split()
    for i in ("device", "book", "boardframe", "desk", "sheetmore", "sheet", "talktray", "clockpop"):
        assert stage in _one(els, i)["ancestors"], i
    assert _one(els, "book") not in _one(els, "device")["ancestors"]
    assert _one(els, "device")["ancestors"][-1] is stage, "the device belongs to the stage"
    who = _one(els, "side-who")
    for i in ("pc-name", "pc-line", "pc-state", "loadout", "purse", "open-equipment", "openroster"):
        assert who in _one(els, i)["ancestors"], i
    bench = [e for e in els if e["tag"] == "a" and e["attrs"].get("href") == "/craft/"]
    assert any(who in e["ancestors"] for e in bench), "no Crafting bench door in the sheet"
    assert any(_one(els, "craftpanel") in e["ancestors"] for e in bench), \
        "no bench door in the Craft action popover"
    nums = _one(els, "panels")
    for i in ("life", "medals", "defence", "saves", "xp", "panel-scene", "panel-rolls"):
        assert nums in _one(els, i)["ancestors"], i
    desk = _one(els, "desk")
    for i in ("combatbar", "exits", "suggestions", "abilities", "err", "sayform", "input",
              "send", "carryon", "craftaction", "spellbtn", "attachments", "craftpanel"):
        assert desk in _one(els, i)["ancestors"], i
    head = [e for e in els if "bookhead" in (e["attrs"].get("class") or "").split()][0]
    for i in ("place-name", "where-line", "here-list", "face", "glance"):
        assert head in _one(els, i)["ancestors"], i


def test_the_top_bar_has_the_way_out_the_tabs_talk_and_hide_sheet(page):
    """The owner asked where the landing page and the bench had gone (the mock README,
    "The doors out of the table"): Worlds & characters sits at the bar's far left, above
    the world's name, as far from the tabs and the pen as the bar allows. Talk carries
    its count; Hide sheet says which way it goes."""
    _, els = page
    bar = [e for e in els if e["tag"] == "header" and "topbar" in e["attrs"].get("class", "")][0]
    inside = [e for e in els if bar in e["ancestors"]]
    first_link = next(e for e in inside if e["tag"] in ("a", "button"))
    assert first_link["tag"] == "a" and first_link["attrs"].get("href") == "/"
    assert "leave" in first_link["attrs"].get("class", "")
    for i in ("world-name", "talktab", "sheettoggle", "dv-slot"):
        assert bar in _one(els, i)["ancestors"], i
    talk = _one(els, "talktab")
    assert talk["attrs"].get("aria-controls") == "talktray"
    count = [e for e in els if talk in e["ancestors"] and "edgecount" in e["attrs"].get("class", "")]
    assert count and "v2-count" in count[0]["attrs"]["class"]


def test_the_footer_trade_button_is_gone_and_the_trade_tab_says_why_it_is_empty(page):
    """The footer's duplicate Trade button is gone (the mock README: the tab is the one
    door). Where nobody keeps a counter the tab still opens and says so, in the words the
    old button's greyed title used, rather than opening onto nothing."""
    html, els = page
    assert 'id="tradeaction"' not in html
    none = _one(els, "trade-none")
    assert _one(els, "mode-trade") in none["ancestors"]
    trade = (TABLE_SCRIPTS / "20-tab-trade.js").read_text(encoding="utf-8")
    assert "NO_COUNTER" in trade and "openTrade()" in trade
    page06 = (TABLE_SCRIPTS / "06-trade-and-page.js").read_text(encoding="utf-8")
    assert 'const NO_COUNTER = "Nobody here keeps a counter.' in page06


def test_spells_is_a_casters_tab_by_the_same_rule_as_the_button():
    """A caster gets the Spells tab and the button beside Say; a non-caster neither (the
    mock README, point 3). Both follow `spellcasting.kind` (owner Q49), never
    `pc.castable`, which offers a prepared caster's whole book when nothing is prepared."""
    tab = _code((TABLE_SCRIPTS / "19-tab-spells.js").read_text(encoding="utf-8"))
    button = (TABLE_SCRIPTS / "10-spells.js").read_text(encoding="utf-8")
    assert "s.spellcasting.kind" in tab and "tab.hidden = !kind" in tab
    assert "btn.hidden = !kind" in button
    assert "castable" not in tab


def test_equipment_offers_only_what_the_engine_can_do_and_says_so(page):
    """Equipment offers the engine's own acts and nothing more: the engine has no op to
    drop a thing (the mock README, "What the engine does not know"), so it is not offered,
    and the page says so rather than leaving the player to look for it. Taking armour off
    is an op since 2026-09-30 (`take_off`, tests/test_gear_usable.py), offered by the
    server's own row acts and never by a button the page invents.

    Stage 1 pinned the carried Inventory and Equipment pages here; stage 2 draws the
    design's page instead, and its every button is an act the server named
    (`_carried`'s `acts`), so the page cannot invent one."""
    html, els = page
    note = _one(els, "equipment-note")
    assert _one(els, "mode-equipment") in note["ancestors"]
    assert "There is no drop yet." in html
    sheet_tab = (TABLE_SCRIPTS / "17-tab-sheet.js").read_text(encoding="utf-8")
    assert 'equipment: "mode-equipment"' in sheet_tab
    sheet = (TABLE_SCRIPTS / "05-sheet.js").read_text(encoding="utf-8")
    page_fn = sheet[sheet.index("function pageEquipment("):sheet.index("function slotEditor(")]
    assert "(r.acts || []).map(" in page_fn, "an Equipment button must be one the server named"
    code = _scripts_code()
    # No endpoint for either and no button offering either (a drag's drop zone on the
    # Spells page is another thing, "data-drop" there is where a spell lands).
    for op in ('"/api/drop"', '"/api/take-off"', ">Drop<", ">Take off<", ">drop<", ">take off<"):
        assert op not in code, op


# --- the owner's rulings, where they were ruled -------------------------------------------

def _css() -> str:
    src = TABLE.read_text(encoding="utf-8")
    return src[src.index("<style>"):src.index("</style>")]


def _rule(css: str, selector: str) -> str:
    at = css.index(selector + " {")
    return css[at:css.index("}", at)]


def test_the_leaf_is_half_the_page_over_a_four_pixel_blur_and_the_head_is_opaque():
    """The owner, 2026-09-30: "make the text box background slightly transparent", then
    "50% is good" after 70% was set. Only the fill: at 50% the dim text measured 4.58:1 at
    its worst (README table); the head keeps its opaque paper."""
    leaf = _rule(_css(), ".bookin")
    assert "--leaf-a: .5;" in leaf and "rgba(17, 14, 10, var(--leaf-a))" in leaf
    assert "backdrop-filter: blur(4px)" in leaf
    assert "opacity:" not in leaf, "the leaf's text must not fade with its fill"
    assert "var(--tex-page-paper)" in _rule(_css(), ".bookhead")


def test_the_book_has_one_border_and_its_clasps_on_the_ring():
    """"there is some extra border or something on the right and bottom of the narration
    box": seven hard 1px offsets in the book's box-shadow (the old page stack) read as a
    second 7px band. The depth is the cast shadow alone; the ring and its clasps are the
    theme's (.v2-framed, registered on the ring's centre line)."""
    css = _css()
    book = _rule(css, "  .book")
    assert "box-shadow: var(--sh-3)" in book
    assert not re.search(r"\d+px \d+px 0 #", book), "a hard offset band is back on the book"
    html = Client().get("/play/").content.decode("utf-8")
    assert 'class="book v2-framed"' in html
    theme = THEME.read_text(encoding="utf-8")
    assert "--clasp-in-x: 29px; --clasp-in-y: 28px; --boss-in: 24px;" in theme


def test_the_backdrop_is_the_boiler_room_with_its_own_lift():
    """The table sits in the owner's boiler room (theme-v2's .page-backdrop-room), dimmed
    by the room's own four variables (the owner's last lift, 2026-09-30), not re-dimmed
    by the page: "only the background and not the UI"."""
    html = Client().get("/play/").content.decode("utf-8")
    assert re.search(r'<body class="[^"]*\bpage-backdrop-room\b', html)
    theme = THEME.read_text(encoding="utf-8")
    assert "--room-dim-top: .60; --room-dim-foot: .655; --room-vig-mid: .44; --room-vig-edge: .83;" in theme
    assert "--room-dim" not in _css(), "the table re-dims the room itself"


def test_the_table_reads_the_theme_and_redefines_none_of_its_tokens():
    """The theme is linked with `{% asset %}` before the page's own style, so a changed
    theme is a new URL the packaged app's cache cannot serve stale; and the page defines
    none of the theme's tokens again, which is how two copies drift apart."""
    src = TABLE.read_text(encoding="utf-8")
    assert src.index("{% asset 'css/theme-v2.css' %}") < src.index("<style>")
    theme_tokens = set(re.findall(r"(--[\w-]+)\s*:", re.sub(r"/\*.*?\*/", "", THEME.read_text(encoding="utf-8"), flags=re.S)))
    roots = re.findall(r":root\s*\{([^}]*)\}", _css())
    mine = {t for block in roots for t in re.findall(r"(--[\w-]+)\s*:", block)}
    assert not (mine & theme_tokens), f"the table redefines the theme's {sorted(mine & theme_tokens)}"


def test_the_device_is_placed_by_css_alone_and_hangs_on_the_centre_column():
    """"the way it is now is good" (placement accepted 2026-09-30): on the centre column's
    left gilt edge, 24px down, its box the column's grid area. A version that measured
    the column in script kept a stale offset (-35,137 at 1792, off the window's edge), so
    the script may not measure where it goes."""
    device = _rule(_css(), "  .device")
    assert "grid-area: book" in device and "top: 24px" in device
    assert "(100% - var(--col-max)) / 2" in device
    js = _code((TABLE_SCRIPTS / "13-device.js").read_text(encoding="utf-8"))
    placing = js[js.index("function place()"):js.index("function draw()")]
    for measure in ("getBoundingClientRect", "offsetLeft", "offsetTop", "style.left", "style.top"):
        assert measure not in placing, measure
    phone = _css()[_css().index("/* --- Phone: the story is the page"):]
    assert ".dv-slot { display: block;" in phone and "rotate(90deg)" in phone


def test_the_devices_model_is_the_approved_mocks():
    """The timings the owner watched and approved: a 520ms ease to a stop, then a
    heartbeat of 700ms before the lever ("the gears should stop a heartbeat before the
    lever lifts up"). Measured in the mock at 700-709ms gear-stop to lever; the app's
    copy must be the same arithmetic, or the approval was of something else."""
    mine = (TABLE_SCRIPTS / "13-device.js").read_text(encoding="utf-8")
    theirs = (MOCK / "device.js").read_text(encoding="utf-8")
    block = lambda s: s[s.index("const T = {"):s.index("};", s.index("const T = {"))]
    assert block(mine) == block(theirs)
    for const in ("const LARGE_RPS = 1.4;", "const LEVER_UP = -46, LEVER_DOWN = 34;",
                  "const k = 520, c = 26;", "900 * (M.tabTarget - M.tab) - 34 * M.tabV"):
        assert const in mine and const in theirs, const


def test_the_device_images_are_found_beside_the_script_and_ship():
    """The frozen app serves play/static at /static/ out of the bundle; a path built from
    where the app was installed would point inside the PyInstaller bundle (CLAUDE.md). The
    device finds its images from its own script's URL, as 06 finds the item icons."""
    js = (TABLE_SCRIPTS / "13-device.js").read_text(encoding="utf-8")
    assert 'new URL("../../img/v2/", s.src)' in js
    v2 = ROOT / "play" / "static" / "img" / "v2"
    for f in ("device-frame.png", "device-chamber.png", "device-lip.png", "device-tab.png",
              "device-geometry.js"):
        assert (v2 / f).is_file(), f
    src = TABLE.read_text(encoding="utf-8")
    assert "{% asset 'img/v2/device-geometry.js' %}" in src
    assert src.index("{% asset 'img/v2/device-geometry.js' %}")         < src.index("{% asset 'js/table/13-device.js' %}"), "the geometry must load first"


# --- the device's signals, run in node ----------------------------------------------------

_DEVICE_STUB = r"""
const L = {};
const CALLS = [];
const document = {
  querySelector: () => null, getElementById: () => null,
  addEventListener: (k, fn) => { (L[k] = L[k] || []).push(fn); },
};
const window = { DEVICE_GEOMETRY: null, matchMedia: () => ({ matches: false }) };
let MODE = "idle";
window.Device = { run: () => { CALLS.push("run"); MODE = "running"; },
                  wait: () => { CALLS.push("wait"); MODE = "waiting"; },
                  ready: () => { CALLS.push("ready"); MODE = "idle"; },
                  stop: () => { CALLS.push("stop"); MODE = "idle"; },
                  state: () => MODE };
const HOOKS = [];
function onRender(fn) { HOOKS.push(fn); }
const draw = s => HOOKS.forEach(fn => fn(s, null));
const fire = (k, detail) => (L[k] || []).forEach(fn => fn({ detail }));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on this machine")
def test_the_device_answers_the_three_signals_the_page_really_has(tmp_path):
    """The owner, 2026-09-29: "dont hold back narration for it and dont worry about
    displaying what its doing." So the device knows only what the page knows: `busy(true)`
    is running; the POST's reply is the answer, `ready` or, with a roll owed, `wait`; a
    turn that ends with no reply (a refusal, a busy table) comes to rest with `stop`. A
    post outside a turn (a counter's deal, the die's face) moves nothing, and a reply is
    answered once, however many posts a turn makes. And a roll owed that no turn of
    this page's asked for (a page reloaded over a pending die, measured live showing the
    device idle; or the other device's turn drawn by the resync) is shown as waiting, and
    comes to rest when a drawn state owes nothing; a turn in flight draws nothing here."""
    src = _DEVICE_STUB + (TABLE_SCRIPTS / "13-device.js").read_text(encoding="utf-8") + """
    const seq = [];
    const mark = label => { seq.push([label, CALLS.splice(0)]); };
    fire("table:posted", { awaiting: false });                     mark("post outside a turn");
    fire("table:busy", { on: true });                              mark("say");
    fire("table:posted", { awaiting: true });                      mark("reply owes a roll");
    fire("table:busy", { on: false });                             mark("busy off after it");
    fire("table:posted", { awaiting: false });                     mark("the die's face");
    fire("table:busy", { on: true });                              mark("roll");
    fire("table:posted", { awaiting: false });                     mark("reply");
    fire("table:posted", { awaiting: false });                     mark("a second post");
    fire("table:busy", { on: false });                             mark("busy off");
    fire("table:busy", { on: true });                              mark("say again");
    fire("table:busy", { on: false });                             mark("refused, no reply");
    draw({ awaiting: { label: "Attack" } });                       mark("opened over a roll owed");
    draw({ awaiting: { label: "Attack" } });                       mark("drawn again");
    draw({ awaiting: null });                                      mark("the other device rolled it");
    fire("table:busy", { on: true });                              mark("a turn");
    draw({ awaiting: { label: "Damage" } });                       mark("its own draw, mid-turn");
    console.log(JSON.stringify(seq));"""
    f = tmp_path / "device.js"
    f.write_text(src, encoding="utf-8")
    done = subprocess.run(["node", str(f)], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    got = dict(json.loads(done.stdout.strip().splitlines()[-1]))
    assert got == {"post outside a turn": [], "say": ["run"], "reply owes a roll": ["wait"],
                   "busy off after it": [], "the die's face": [], "roll": ["run"],
                   "reply": ["ready"], "a second post": [], "busy off": [],
                   "say again": ["run"], "refused, no reply": ["stop"],
                   "opened over a roll owed": ["wait"], "drawn again": [],
                   "the other device rolled it": ["stop"], "a turn": ["run"],
                   "its own draw, mid-turn": []}


def test_the_signals_are_sent_where_the_page_already_knows_them():
    """`table:busy` from 06's `busy`, the one switch every action already throws; the
    answer from 02's `post`, dispatched after every status check and before the caller
    draws the reply, carrying whether a roll is owed. Nothing waits on the device: no
    script awaits it, and the turn's render never asks it anything."""
    page06 = (TABLE_SCRIPTS / "06-trade-and-page.js").read_text(encoding="utf-8")
    busy = page06[page06.index("function busy(on)"):]
    busy = busy[:busy.index("\n}\n")]
    assert 'new CustomEvent("table:busy", { detail: { on: !!on } })' in busy
    state = (TABLE_SCRIPTS / "02-state.js").read_text(encoding="utf-8")
    post = state[state.index("async function post("):state.index("function render(s, hold)")]
    assert post.index('"table:posted"') > post.index("if (!r.ok) throw")
    assert post.index('"table:posted"') < post.index("return data;")
    assert "awaiting: !!(data && data.awaiting)" in post
    code = _scripts_code()
    assert not re.search(r"await[^;\n]*Device", code), "something waits on the device"
    turns = (TABLE_SCRIPTS / "04-combat-and-turns.js").read_text(encoding="utf-8")
    take = turns[turns.index("async function takeTurn("):turns.index('$("#sayform").onsubmit')]
    assert "Device" not in take and take.index("render(s);") < take.index("finally { busy(false); }")


# --- the frozen app ------------------------------------------------------------------------

def test_everything_the_page_loads_is_the_apps_own():
    """The packaged exe is offline and installed anywhere: every script, stylesheet and
    image the page names goes through `{% static %}` or `{% asset %}` (or is a data URL),
    no URL points off the machine, and every font the page can ask for is in
    play/static/fonts."""
    src = TABLE.read_text(encoding="utf-8")
    refs = re.findall(r"""(?:src|href)="([^"]+)\"""", src)
    for ref in refs:
        if ref.startswith(("{%", "data:", "#", "/", "https://game-icons.net",
                           "https://creativecommons.org")):
            continue
        pytest.fail(f"the page loads {ref!r} by a bare path")
    for ref in refs:
        if ref.startswith("http") and "game-icons" not in ref and "creativecommons" not in ref:
            pytest.fail(f"the page loads {ref!r} from off the machine")
    css = _css()
    assert not re.search(r"url\(\s*[\"']?(?!data:)(?!\{%)[\w./-]+\.(png|jpg|woff2?)", css), \
        "a url() in the table's style does not go through {% static %} or a theme token"
    assert "fonts.googleapis" not in src and "cdn" not in src.lower()
    theme = THEME.read_text(encoding="utf-8")
    for font in re.findall(r'url\("(\.\./fonts/[^"]+)"\)', theme):
        assert (THEME.parent / font).resolve().is_file(), font
    spec = (ROOT / "pathfindergm.spec").read_text(encoding="utf-8")
    assert "play/static" in spec, "the new scripts ship only because play/static ships whole"


def test_the_phone_is_the_designs_phone():
    """At 375px (the mock README, "Phone (375px)"): the tabs keep their words in one row
    that scrolls sideways (one row measured 479px and widened the page to 427px before
    `min-width: 0`); the device lies in the head bar; each group of ways and the GM's
    offers are one sideways row; the sheet is a tab of its own. Measured on the running
    app: scrollWidth 375 on every tab."""
    phone = _css()[_css().index("/* --- Phone: the story is the page"):]
    assert re.search(r"\.modes \{ grid-area: modes; min-width: 0;[^}]*overflow-x: auto", phone)
    assert "#exits .ex-list { flex-wrap: nowrap; overflow-x: auto;" in phone
    assert "#suggestions { flex-wrap: nowrap; overflow-x: auto;" in phone
    assert "body.mode-sheet .stage { display: flex; flex-direction: column;" in phone
    assert "body:is(.mode-table, .mode-map) .sheet { display: none; }" in phone
    stage = _rule(_css(), "  .stage")
    assert "overflow-x: clip" in stage, "the clasps' box widens a phone page without it"
    # The tabs that take the whole page hold framed cards too: the Trade tab's notice
    # widened a 375px page to 397px until its page was clipped the same way (measured).
    assert "overflow-x: clip" in _rule(_css(), "  .modepage")
    # The combat bar's one sideways row of buttons made the bar wider than the desk, and
    # its hint was cut off at "just type below fo" (measured at 375).
    assert ".choices > * { min-width: 0; }" in _css()


def test_the_craft_hub_opens_over_the_story_and_stays_in_the_window():
    """The hub is a popover anchored to the desk, so nothing in the desk moves when it
    opens (the exits row measured 563px before and after); held to the book's height and
    scrolled inside, because with every craft's ways listed it measured 584px and ran 45px
    off the top of a 1440x900 window. Its door to the full bench is inside it."""
    css = _css()
    assert "bottom: calc(100% + 10px)" in _rule(css, "  .pop")
    hub = _rule(css, "  #craftpanel")
    assert "max-height: calc(45dvh - 50px)" in hub and "overflow-y: auto" in hub
    html = Client().get("/play/").content.decode("utf-8")
    assert 'id="craftpanel" class="pop"' in html and 'id="craftclose"' in html


# --- the Table tab's story and its share of the height (stage 1, second pass) --------------

_STORY_STUB = r"""
const HOOKS = [];
function onRender(fn) { HOOKS.push(fn); }
const $ = s => document.getElementById(s.replace(/^#/, ""));
const esc = s => String(s);
function beats(tops) { return tops.map(t => ({ offsetTop: t })); }
const story = { id: "story", scrollTop: 0, scrollHeight: 6000, clientHeight: 255, offsetTop: 64,
                _beats: [], querySelectorAll: () => story._beats, addEventListener() {},
                style: { overflowY: "auto", paddingTop: "22px" } };
const leaf = { id: "bookin", scrollTop: 0, scrollHeight: 6100, clientHeight: 700,
               addEventListener() {}, style: { overflowY: "auto", paddingTop: "0px" } };
const document = {
  getElementById: id => ({ story, bookin: leaf })[id] || null,
  querySelector: () => null, querySelectorAll: () => story._beats,
  addEventListener() {}, fonts: null,
};
const getComputedStyle = el => el.style;
class ResizeObserver { constructor(fn) { this.fn = fn; } observe() {} disconnect() {} }
const window = {};
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on this machine")
def test_a_new_beat_lands_with_its_first_line_at_the_top_and_a_rereader_stays(tmp_path):
    """The story was sent to its foot on every state (`scrollTop = scrollHeight`). A beat
    longer than the page then opened above the head: measured at 1792x805 on a reload, the
    fresh beat's top at 119 against the story's top at 145, 26px under the book's head,
    its drop cap showing only its stem (scrollTop 1942 of 2487, clientHeight 255). And
    the foot itself moved, because the first draw runs before the head is filled in.
    Now the newest beat (on a fresh page) or the first new one (after a turn) is put at
    the top, by its own offset less the story's padding; a reader who scrolled back above
    where the last beat landed is left where they are; on a phone the leaf scrolls, and
    the story's own offset in it is counted."""
    book = (TABLE_SCRIPTS / "15-book.js").read_text(encoding="utf-8")
    src = _STORY_STUB + book + r"""
    const out = {};
    const T = n => ({ transcript: Array.from({ length: n }, (_, i) => ({ text: "b" + i })) });
    story._beats = beats([22, 400, 1916]);
    storyLand(T(3), null);                             // a fresh page: the newest beat
    out.load = story.scrollTop;
    story._beats = beats([22, 400, 1916, 2500, 2540]);
    story.scrollTop = 2000;                            // read on, past where it landed
    storyLand(T(5), T(3));                             // a turn: the first new beat
    out.turn = story.scrollTop;
    story._beats = beats([22, 400, 1916, 2500, 2540, 3100]);
    story.scrollTop = 900;                             // scrolled back to reread
    storyLand(T(6), T(5));
    out.reread = story.scrollTop;
    storyLand(T(6), T(6));                             // a resync, nothing new
    out.resync = story.scrollTop;
    story.style.overflowY = "visible";                 // a phone: the leaf scrolls
    story._beats = beats([12, 380]);
    storyLand(T(2), null);
    out.phone = leaf.scrollTop;
    console.log(JSON.stringify(out));"""
    f = tmp_path / "story.js"
    f.write_text(src, encoding="utf-8")
    done = subprocess.run(["node", str(f)], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    got = json.loads(done.stdout.strip().splitlines()[-1])
    assert got["load"] == 1916 - 22, "the newest beat's first line is not at the top"
    assert got["turn"] == 2500 - 22, "the first new beat did not land at the top"
    assert got["reread"] == 900 and got["resync"] == 900, "a rereader was moved"
    assert got["phone"] == 64 + 380 - 22


def test_the_story_is_landed_by_the_book_not_sent_to_its_foot():
    """02 sends the page to its foot only before 15-book.js has loaded (the very first
    draw); the landing is 15's, redone as the layout under it settles, and the browser's
    own scroll anchoring is off where the page is rebuilt whole each state."""
    state = (TABLE_SCRIPTS / "02-state.js").read_text(encoding="utf-8")
    assert 'if (typeof storyLand !== "function") $("#story").scrollTop = $("#story").scrollHeight;' in state
    book = (TABLE_SCRIPTS / "15-book.js").read_text(encoding="utf-8")
    assert "new ResizeObserver" in book and "storySettle" in book
    assert "#story, .bookin { overflow-anchor: none; }" in _css()


def test_the_book_keeps_45_percent_of_the_stage_at_every_width():
    """The mock README: the book keeps at least 45% of the height; past that the desk's
    choices scroll and the pen stays. `minmax(45%, 1fr)` is 45% of the stage's content
    box, not of the stage: measured 319px of a 744px stage at 1792x805 (0.43) under a
    373px desk of eight exits and two offers. The floor counts the padding back in (45% of
    36px on a desktop, of 24px on a phone), so it measured 0.45 at 1792x805, 1440x900,
    1024x768 (six lines of story, where it had once been three) and 375x812, with eight
    exits, the choices scrolling and the pen inside the desk every time."""
    css = _css()
    assert "grid-template-rows: minmax(calc(45% + 16.2px), 1fr) minmax(0, auto);" in _rule(css, "  .stage")
    phone = css[css.index("/* --- Phone: the story is the page"):]
    assert ".stage { grid-template-rows: minmax(calc(45% + 10.8px), 1fr) minmax(0, auto); }" in phone
    desk = css[css.index("  .desk { position: relative"):]
    desk = desk[:desk.index("}")]
    assert "grid-template-rows: minmax(0, 1fr) auto auto" in desk and "min-height: 0" in desk
    assert "overflow-y: auto" in _rule(css, "  .choices")
