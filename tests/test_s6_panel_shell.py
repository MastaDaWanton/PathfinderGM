"""The play table's panel shell (S6, 2026-09-28): the seams Lane F builds on in Phase 2.

`docs/fix-interfaces.md` §2.11 is the contract. Six lanes write against these ids and
hooks in parallel, so a mount point that goes missing, or appears twice, fails here
rather than as a blank panel that nobody can explain three merges later. The existing
renderers were moved, not rewritten: every id the page had before the shell is still on
it exactly once, which is the whole claim that "the table works as it did".

Verified by driving the served page in headless Edge at 1440x900 and 375x812 (no dev
server): five panels collapse, close and restore and survive a reload; "Hide the column"
gives the edge tabs; a conversation starting on a phone badges the Talk tab ("Talk, 3
new") and leaves the drawer shut; Esc returns focus to the tab that opened it; page
width stayed 375 at 375 (no sideways scroll). These tests hold what Python can hold.

The table rebuild (2026-09-30, docs/table-rebuild-inventory.md) replaced the column with
the owner's approved design: the stage's two sides and the tabs on top. What these tests
proved carries over, moved to where the rebuild put each thing: every mount point is on
the page once; every id the page had before is still there once, or is gone by a ruling
the inventory cites (and is really gone); the renderers live where the design gives them;
the one choice that must not flash (the sheet hidden) is made before the first paint.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

import pytest
from django.test import Client

from pagesource import TABLE, TABLE_SCRIPTS

# The conversation was a fifth panel until the owner's ruling of 2026-09-28 (Q42): "It
# should be removed from the panel." It is a tray of its own now, `#talktray` (Lane F).
# Since the table rebuild the sheet in brief is the stage's two sides and the map is a
# tab; "In the scene" and "Rolls" are the two panels left, at the foot of the right side.
PANELS = ("scene", "rolls")

MOUNTS = (
    ["panels"]
    + [f"panel-{p}" for p in PANELS] + [f"panel-{p}-body" for p in PANELS]
    + ["talktab", "talktray", "talkclose"]
    + ["convo", "convo-people", "convo-log", "convo-latest", "clockpop",
       "clocksay", "spellbtn", "spellpop", "attachments", "saystatus"]
    # The rebuild's own (12-21): the stage, its device, the two sides, the tabs' pages.
    + ["stage", "device", "dv-slot", "book", "boardframe", "desk", "sheetmore", "sheet",
       "side-who", "sheettoggle", "world-name", "glance", "place-name", "where-line",
       "here-list", "face", "trade-none"]
    + [f"tab-{m}" for m in ("table", "map", "sheet", "equipment", "spells", "trade", "journal")]
    + [f"mode-{m}" for m in ("equipment", "spells", "trade", "journal")]
)

# Gone with the rebuild, each by the ruling docs/table-rebuild-inventory.md cites on its
# row: the footer's duplicate Trade button (the Trade tab is the one door), the map tray
# and its edge tab (Map is a tab), the phone drawer's Sheet edge tab (the Sheet is a tab).
DROPPED = {"tradeaction": "P16", "maptab": "M5", "maptray": "M5", "mapclose": "M5",
           "maptrayinner": "M5", "sheettab": "N15"}

# Every id the template carried at `phase-1-base` (a5955ef), before the shell. Each one
# has a renderer or a listener somewhere in static/js/table/ that finds it by id.
BEFORE = """embers cursorshade cursorlight story busy err suggestions combatbar cb-round
cb-turn cb-targets cb-plan cb-strike cb-fullatk cb-coup cb-ability cb-cast cb-swift cb-free
cb-clear cb-commit cb-end cb-menu cb-hint abilities sayform input send carryon craftaction
tradeaction craftpanel cp-biome cp-desc cp-biomepick cp-debug cp-busy cp-h cp-hn cp-actions
sheet order mapwrap board talk gmview rolls maptab sheettab maptray mapclose maptrayinner
veil popup deathveil deathtitle deathtext deathchoices deathroster tradepanel tradename
trademeta trademsg closetrade tradepurse tradmine tradewhat tradesum tradeshort tradego
tradetill tradtheirs sheetpanel sheetname sheetmeta sheeterr closesheet sheettabs
sheetbody""".split()


class _Tree(HTMLParser):
    """Each element with its attributes and the chain of ids/classes above it."""

    VOID = {"input", "br", "img", "meta", "link", "hr", "source", "path", "circle"}

    def __init__(self):
        super().__init__()
        self.stack: list[dict] = []
        self.elements: list[dict] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        el = {"tag": tag, "attrs": a, "ancestors": list(self.stack), "index": len(self.elements)}
        self.elements.append(el)
        if tag not in self.VOID and not tag.endswith("/"):
            self.stack.append(el)

    def handle_startendtag(self, tag, attrs):
        self.elements.append({"tag": tag, "attrs": dict(attrs),
                              "ancestors": list(self.stack), "index": len(self.elements)})

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


def _by_id(elements, id_):
    return [e for e in elements if e["attrs"].get("id") == id_]


def _classes(e):
    return (e["attrs"].get("class") or "").split()


def test_every_mount_point_is_on_the_served_page_exactly_once(page):
    """Six lanes code against these ids; a duplicate id makes `$()` return whichever
    comes first, which is a bug that renders perfectly."""
    _, els = page
    counts = {m: len(_by_id(els, m)) for m in MOUNTS}
    assert all(n == 1 for n in counts.values()), {m: n for m, n in counts.items() if n != 1}


def test_every_id_the_page_had_before_the_shell_is_still_there_once(page):
    """The renderers were moved into panel bodies, not re-invented: `#mapwrap`, `#board`,
    `#talk`, `#rolls` and the rest keep their ids, so `renderMap`, `renderTalk` and
    `renderRolls` needed no edits. Since the table rebuild an id is either still on the
    page once, or gone by a ruling the inventory cites on its row, and then really gone:
    a dropped control left in the markup is a button that does nothing."""
    _, els = page
    kept = [i for i in BEFORE if i not in DROPPED]
    bad = {i: len(_by_id(els, i)) for i in kept if len(_by_id(els, i)) != 1}
    assert not bad, bad
    lingering = [i for i in DROPPED if _by_id(els, i)]
    assert not lingering, f"dropped by a ruling but still on the page: {lingering}"
    inventory = (TABLE.parents[3] / "docs" / "table-rebuild-inventory.md").read_text(encoding="utf-8")
    for i, row in DROPPED.items():
        line = next((ln for ln in inventory.splitlines() if ln.startswith(f"| {row} |")), "")
        assert "| dropped |" in line and "README" in line, f"#{i}: row {row} cites no ruling"


def test_each_panel_has_the_shape_the_register_names(page):
    """`section.panel#panel-<id>` with `.panelhead > button.paneltoggle[aria-expanded]`
    and `.panelbody#panel-<id>-body`, inside the right side (#panels). The bar of toggles
    and each panel's close went with the rebuild: the side shows its two disclosures
    always, so there is nothing to take off it and nothing to bring back (inventory N12)."""
    _, els = page
    for p in PANELS:
        (section,) = _by_id(els, f"panel-{p}")
        assert section["tag"] == "section" and "panel" in _classes(section), p
        inside = [e for e in els if section in e["ancestors"]]
        heads = [e for e in inside if "panelhead" in _classes(e)]
        assert len(heads) == 1, p
        in_head = [e for e in inside if heads[0] in e["ancestors"] and e["tag"] == "button"]
        assert [("paneltoggle" in _classes(b)) for b in in_head] == [True], p
        assert in_head[0]["attrs"].get("aria-expanded") in ("true", "false"), p
        assert in_head[0]["attrs"].get("aria-controls") == f"panel-{p}-body", p
        (body,) = _by_id(els, f"panel-{p}-body")
        assert section in body["ancestors"] and "panelbody" in _classes(body), p
        assert _by_id(els, "panels")[0] in section["ancestors"], p
    assert not [e for e in els if "panelbtn" in _classes(e) or "panelclose" in _classes(e)]


def test_the_renderers_live_in_the_panels_the_design_gives_them(page):
    """docs/design-f-ui.md §4.1's table, as the rebuild moved it: Scene holds #order,
    #board and #gmview; Rolls #rolls; the map (#mapwrap) is the Map tab's board, where the
    book was; the sheet in brief is the two sides, who (#side-who) and the numbers
    (#panels). The conversation, #convo above #talk, is in its own tray and in no panel
    (owner, Q42)."""
    _, els = page
    where = {"scene": ["order", "board", "gmview"], "rolls": ["rolls"]}
    for p, ids in where.items():
        (body,) = _by_id(els, f"panel-{p}-body")
        for i in ids:
            assert body in _by_id(els, i)[0]["ancestors"], f"#{i} is not in the {p} panel"
    (frame,) = _by_id(els, "boardframe")
    assert frame in _by_id(els, "mapwrap")[0]["ancestors"], "#mapwrap is not on the Map tab's board"
    (sheet,) = _by_id(els, "sheet")
    for i in ("side-who", "panels", "loadout", "medals", "life", "xp", "open-equipment"):
        assert sheet in _by_id(els, i)[0]["ancestors"], f"#{i} is not in the sheet's two sides"
    (tray,) = _by_id(els, "talktray")
    (aside,) = _by_id(els, "panels")
    for i in ("convo", "talk"):
        assert tray in _by_id(els, i)[0]["ancestors"], f"#{i} is not in the tray"
        assert aside not in _by_id(els, i)[0]["ancestors"], f"#{i} is still in the column"
    assert _by_id(els, "convo")[0]["index"] < _by_id(els, "talk")[0]["index"]
    convo = _by_id(els, "convo")[0]
    for i in ("convo-people", "convo-log", "convo-latest"):
        assert convo in _by_id(els, i)[0]["ancestors"], i


def test_the_mounts_outside_the_column_sit_where_lane_f_expects_them(page):
    """#clockpop inside main (so the clock never covers the column); #attachments inside
    #sayform before #input (a chip beside the words, not in them); #spellpop a popover;
    the two status regions present from load, because a live region injected at the
    moment it speaks is not announced."""
    _, els = page
    (main,) = [e for e in els if e["tag"] == "main"]
    assert main in _by_id(els, "clockpop")[0]["ancestors"]
    (form,) = _by_id(els, "sayform")
    att, inp = _by_id(els, "attachments")[0], _by_id(els, "input")[0]
    assert form in att["ancestors"] and att["index"] < inp["index"]
    assert form in _by_id(els, "spellbtn")[0]["ancestors"]
    assert _by_id(els, "spellpop")[0]["attrs"].get("popover") is not None
    for i in ("clocksay", "saystatus"):
        assert _by_id(els, i)[0]["attrs"].get("role") == "status", i


def test_the_drawer_is_decided_before_first_paint_without_template_variables():
    """The first thing in <body> is the script that decides the layout before the first
    paint, so a desktop that hid the sheet never flashes it back. Since the rebuild the
    choice is `body.sheet-hidden` (Hide sheet; a phone has the Sheet tab instead, so the
    script leaves a narrow window alone). It may carry no `{{ }}` or `{% %}`: Django
    renders a missing variable as "", and `x = ;` kills every script after it silently
    (the PATHFINDER_BOOT lesson, table.html)."""
    src = TABLE.read_text(encoding="utf-8")
    after = src[src.index(">", src.index("<body")) + 1:].lstrip()
    assert after.startswith("<script>"), "the pre-paint script is not first in <body>"
    block = after[:after.index("</script>")]
    assert "{{" not in block and "{%" not in block
    assert 'classList.add("sheet-hidden")' in block and "max-width: 760px" in block
    assert '"pgm.table.panels.v1"' in block
    panels = (TABLE_SCRIPTS / "07-panels.js").read_text(encoding="utf-8")
    assert 'const PANELS_KEY = "pgm.table.panels.v1";' in panels, \
        "the pre-paint script and 07 read the layout under different keys"


def test_scripts_07_to_10_load_in_order_after_06_through_the_asset_tag():
    """`{% asset %}` stamps each URL with its content hash, which is what defeats the
    Electron disk cache that outlives reinstalls (templatetags/assets.py)."""
    src = TABLE.read_text(encoding="utf-8")
    names = ["06-trade-and-page", "07-panels", "08-conversation", "09-clock", "10-spells"]
    at = [src.index(f"{{% asset 'js/table/{n}.js' %}}") for n in names]
    assert at == sorted(at), "the table scripts are not loaded in order"
    for n in names[1:]:
        assert (TABLE_SCRIPTS / f"{n}.js").is_file(), n


def test_the_four_state_hooks_are_in_02():
    """§2.11's four edits, each read where it must be: `prev` kept and the hooks run
    before `if (hold) return` (a held dice mat must not hide a turn from the clock);
    `post()` announcing its own success with the clock it held; the beat renderer
    drawing `b.attachments`; the sheet line preferring geography's words."""
    js = (TABLE_SCRIPTS / "02-state.js").read_text(encoding="utf-8")
    render = js[js.index("function render(s, hold)"):js.index("function renderTalk(")]
    assert render.index("const prev = STATE;") < render.index("STATE = s;")
    assert "runRenderHooks(s, prev)" in render
    assert render.index("runRenderHooks(s, prev)") < render.index("if (hold) return;")
    post = js[js.index("async function post("):js.index("function render(s, hold)")]
    assert '"table:posted"' in post and "clockBefore" in post and "url" in post
    # After every status check, so only a turn that was actually taken arms anything.
    assert post.index('"table:posted"') > post.index("if (!r.ok) throw")
    assert "b.attachments" in render
    # The place line prefers geography's words; since the rebuild it is the book's head
    # (15-book.js), the old side column's biome line moved there.
    book = (TABLE_SCRIPTS / "15-book.js").read_text(encoding="utf-8")
    where = book[book.index("function bookWhere("):book.index("function bookStanding(")]
    assert "sc.where_label" in where and "sc.where_detail" in where
    assert where.index("sc.where_label") < where.index("sc.location")


def test_the_first_draw_cannot_throw_on_a_hook_that_is_not_defined_yet():
    """06 ends with `render(STATE)`, which runs before 07 has defined `runRenderHooks`.
    An unguarded call there is a ReferenceError that stops the first draw; 07 primes the
    hooks with `prev === null` once the document has loaded instead."""
    js = (TABLE_SCRIPTS / "02-state.js").read_text(encoding="utf-8")
    assert 'if (typeof runRenderHooks === "function") runRenderHooks(s, prev);' in js
    six = (TABLE_SCRIPTS / "06-trade-and-page.js").read_text(encoding="utf-8")
    assert six.rstrip().endswith("render(STATE);")
    panels = (TABLE_SCRIPTS / "07-panels.js").read_text(encoding="utf-8")
    assert "runRenderHooks(STATE, null)" in panels and "DOMContentLoaded" in panels


def test_07_exports_the_register_api_and_the_stubs_use_it():
    panels = (TABLE_SCRIPTS / "07-panels.js").read_text(encoding="utf-8")
    assert "function onRender(fn)" in panels
    api = panels[panels.index("const Panels = {"):]
    for member in ("open(", "close(", "collapse(", "expand(", "forward(", "mode("):
        assert f"\n  {member}" in api, member
    for stub in ("08-conversation", "09-clock", "10-spells"):
        assert "onRender(" in (TABLE_SCRIPTS / f"{stub}.js").read_text(encoding="utf-8")


def test_showsheet_was_replaced_not_shadowed():
    """A later classic script's `function showSheet` silently wins over 01's, the JS
    form of what test_no_silent_shadowing guards in Python. So 01 calls `Panels` and no
    table script declares `showSheet`; and no top-level function name is declared twice
    across the ten files."""
    seen: dict[str, str] = {}
    dupes = []
    for f in sorted(TABLE_SCRIPTS.glob("*.js")):
        text = f.read_text(encoding="utf-8")
        assert "function showSheet" not in text, f.name
        for name in re.findall(r"^(?:async\s+)?function\s+(\w+)", text, re.M):
            if name in seen:
                dupes.append((name, seen[name], f.name))
            seen[name] = f.name
    assert not dupes, dupes
    # Since the rebuild 01 reaches the map through the tabs (12-shell.js), not a drawer.
    core = (TABLE_SCRIPTS / "01-core.js").read_text(encoding="utf-8")
    assert "Shell.show(" in core


def test_nothing_opens_a_window():
    """The packaged shell's `setWindowOpenHandler` sends every `window.open` to the
    external browser, and Roll20's pop-out chat left players with chat lost until a
    reload. Nothing on the table pops out (docs/design-f-ui.md §3, lesson 3)."""
    for f in [TABLE, *sorted(TABLE_SCRIPTS.glob("*.js"))]:
        assert "window.open" not in f.read_text(encoding="utf-8"), f.name


def test_the_layout_is_read_and_written_only_inside_try():
    """Storage throws in a private window and when site data is blocked; the layout then
    falls back to everything open and docked rather than taking the page down."""
    lines = (TABLE_SCRIPTS / "07-panels.js").read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if "localStorage." in line and not line.lstrip().startswith("//"):
            window = "\n".join(lines[max(0, i - 2):i + 1])
            assert "try" in window, f"07-panels.js:{i + 1} touches storage outside a try"


def test_the_sheet_hides_on_a_desktop_and_is_a_tab_on_a_phone():
    """The drawer went with the rebuild (inventory N14): on a desktop Hide sheet gives the
    story the width (`body.sheet-hidden`, the same stored choice the column's "Hide the
    column" was), and on a phone the sheet is a tab of its own, so the toggle is not
    offered there and the Table and Map tabs show no sides at all. The drawer's rules are
    gone, not left to style nothing."""
    src = TABLE.read_text(encoding="utf-8")
    assert "body.drawer aside {" not in src and "#edgetabs" not in src
    assert "body.sheet-hidden:is(.mode-table, .mode-map) .sheet { display: none; }" in src
    shell = src[src.index("/* --- Phone: the story is the page; the sheet is a tab"):]
    assert "#sheettoggle { display: none; }" in shell
    assert "body:is(.mode-table, .mode-map) .sheet { display: none; }" in shell