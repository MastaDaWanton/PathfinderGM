"""In progress on the page (play/static/js/table/37-works.js, play/static/css/works.css).

Enchanting lane U4 (docs/enchanting-ui-plan.md §6.10; contracts §12 row U4, §13). Lane G
moved herbalism's steeping jar onto one In progress store for every craft and made a
finished jar wait to be collected; it shipped with NO Collect button anywhere, so a jar a
fortnight past its day said "ready now" in the satchel and could be neither drunk nor taken
out (lane G's report, 2026-10-05). These tests hold the page half: a door and a panel that
show every craft's work with the server's countdown, a Collect on every ready row (refused,
with its reason in words, when the work waits somewhere else), Stop only where a craft
allows it, the count on the door from the table's own state, and the herb bench's old
Steeping group, which worked its countdown out in the page, replaced by the shared group.
The behaviour checks run the real file in node with a small fake DOM, as
tests/test_bench_core.py does, and skip, saying why, where node is not installed.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from django.test import Client

from rules import blacksmith, crafting, inprogress

# The herb bench's own fixture and helpers, so the steep below is the one the player makes.
from test_bench_api import _c, _carry, _craft, _get, _key, _level, bench  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
TABLE_JS = ROOT / "play" / "static" / "js" / "table"
WORKS = TABLE_JS / "37-works.js"
CSS = ROOT / "play" / "static" / "css" / "works.css"
SATCHEL = TABLE_JS / "31-bench-satchel.js"
RACK = TABLE_JS / "41-forge-rack.js"
CORE = TABLE_JS / "29-bench-core.js"
DAY = 1440


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code(text: str) -> str:
    """JS with its comments taken out, so a rule is tested against what runs, not against
    the comment that explains why it was removed."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)//.*$", "", line) for line in text.splitlines())


# --- the table's state carries the door's count ---------------------------------------------

def test_the_table_state_carries_the_count_so_the_door_needs_no_fetch(bench):
    """Contracts §8.2: "the table's own state carries `works: inprogress.summary(...)` so the
    door's count renders without a fetch". Without it the door either asked api/works on
    every turn (a second request per turn, for a count) or said nothing until opened, and a
    jar that turned ready overnight went unnoticed. Through the routes the page calls: the
    bench's steep, then the table's state before and after the clock passes the jar's day."""
    assert _get(bench, "/api/state")["works"] == {"ready": 0, "working": 0, "next": None}
    _level(2)
    _carry(mint=1, spirits=1)
    _craft(bench, "steep", [{"key": _key(bench, "Mint"), "count": 1},
                            {"key": _key(bench, "Strong Spirits"), "count": 1}])
    works = _get(bench, "/api/state")["works"]
    assert works["working"] == 1 and works["ready"] == 0
    assert works["next"]["ready_words"] == "ready in 14 days"
    _c().scene.advance(14 * DAY, charge_body=False)
    assert _get(bench, "/api/state")["works"]["ready"] == 1


# --- the page's files, read statically -------------------------------------------------------

def test_the_panel_loads_after_the_herb_bench_and_before_the_forge():
    """37 is looked up by the benches when they draw (`window.Works`), and it reads the
    table's render hooks (07) as it runs; loaded before 07 its door would never get a count,
    and missing from the page the herb bench's In progress group and every footer's button
    are simply absent. Its stylesheet comes after bench.css, whose icon disc and skeleton
    bars its rows reuse."""
    html = Client().get("/play/").content.decode("utf-8")
    at = html.index("/static/js/table/37-works.js?v=")
    assert html.index("/static/js/table/07-panels.js?v=") < at
    assert html.index("/static/js/table/36-bench-perks.js?v=") < at < \
        html.index("/static/js/table/40-forge-shell.js?v=")
    assert html.count("/static/js/table/37-works.js?v=") == 1
    assert html.index("/static/css/bench.css?v=") < html.index("/static/css/works.css?v=")


def test_countdowns_move_with_game_time_never_a_timer():
    """The owner: "countdown timers that move with game time" (leatherworking Q9.3). A
    real-time tick would count a steep down while the player sat at the menu. So no
    setInterval and no requestAnimationFrame in 37, and the rows are asked again only from
    the clock: the table's render hook (`onRender`) and the benches' `Works.sync` with the
    bench clock's minute."""
    code = _code(_src(WORKS))
    assert not re.findall(r"\b(setInterval|requestAnimationFrame)\s*\(", code)
    assert "onRender(onState)" in code and "clock_minutes" in code
    for shelf in (SATCHEL, RACK):
        assert re.search(r"W\.sync\([^)]*clock\.minute", _code(_src(shelf))), shelf.name


def test_the_satchel_no_longer_works_out_a_countdown():
    """Until 2026-10-05 the satchel had its own "Steeping" group whose line was computed in
    the page, `it.ready_at - g.minute` through `B.span`, with no Collect: the page computed
    a number the server owns (UI plan §12, "the page never computes a number, including
    the countdowns"), and a ready jar had no way out. The group is now `Works.group` with
    the herb track's id, and in-progress jars are kept out of every satchel group."""
    code = _code(_src(SATCHEL))
    assert '"Steeping"' not in code
    assert "ready_at -" not in code and "ready_at-" not in code
    assert 'W.group(host, "herbalist")' in code
    assert "!held(it)" in code


def test_each_shelf_asks_for_its_own_craft_by_the_id_the_rules_register():
    """A group filters rows by `craft`; one asked for under a name the rules do not use
    (the herb track's older "herbalism", or "smith") is empty for ever, silently. The ids
    the shelves pass are the ones the rules register and stamp on each row."""
    assert "herbalist" in inprogress._registry()
    assert crafting.TRACK_ID == "herbalist"
    assert 'W.group(host, "' + crafting.TRACK_ID + '")' in _src(SATCHEL)
    assert 'W.group(host, "' + blacksmith.TRACK_ID + '")' in _src(RACK)


def test_every_bench_footer_carries_the_button_from_the_core():
    """UI plan §6.10: "the In progress button in every bench's footer". Drawn by the core's
    `renderFoot` from 37's own markup, so the herb bench, the forge and every bench after
    them have it without naming it, and its count is the door's."""
    core = _code(_src(CORE))
    foot = core[core.index("h.renderFoot = function"):core.index("var footEl = o.foot")]
    assert "Works.footButton()" in foot
    assert foot.index("Works.footButton()") < foot.index("bf-steady")


def test_the_look_is_the_tables_own():
    """The owner's standing instruction for UI work: keep the colours, images and textures.
    No colour literal in works.css (every colour is a theme token or the bench's own
    translucent lamp-light), the panel is the benches' framed card, its buttons are v2-btn,
    and no dash a reader would see (the benches' rule, test_bench_core)."""
    css = _src(CSS)
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", css)
    js = _src(WORKS)
    assert '"works v2-framed v2-card-leather"' in js
    assert "v2-count" in js
    for text in (css, js):
        assert "—" not in text and "–" not in text


def test_the_z_order_sits_under_the_benches_and_over_the_table():
    """Over the table at 34: above the table's popovers (30), under the bench layers (35),
    so a bench opened over it covers it; inside a bench it orders among the bench's own
    popovers (1 to 9); 1 is its contents over the card's leather, under its gilt ring. Any
    other value would put it over the deathveil or under the log."""
    values = sorted(set(int(v) for v in re.findall(r"z-index:\s*(-?\d+)", _src(CSS))))
    assert values == [1, 8, 34], values


def test_motion_is_gated_by_reduced_motion():
    """The door's glint and a refused Collect's nudge are the only motion; both stop under
    prefers-reduced-motion and under the benches' Short flourishes (`bench-still`), and the
    script asks `reduced()` before starting the glint."""
    css = _src(CSS)
    tail = css[css.index("@media (prefers-reduced-motion: reduce)"):]
    assert "wk-new" in tail and "is-nudged" in tail and "animation: none" in tail
    assert ".bench.bench-still" in css
    assert "if (reduced()) return;" in _src(WORKS)


# --- behaviour, in node ---------------------------------------------------------------------

_NODE = r"""
const fs = require("fs");
const [file] = JSON.parse(process.argv[2]);
const noop = () => {};
const el = () => ({ addEventListener: noop, appendChild: noop, setAttribute: noop,
  classList: { add: noop, remove: noop, toggle: noop }, querySelector: () => null,
  querySelectorAll: () => [], style: {}, dataset: {} });
global.window = global;
global.addEventListener = noop;
global.innerWidth = 1440; global.innerHeight = 900;
global.document = {
  readyState: "complete", cookie: "", body: el(),
  getElementById: () => null, querySelector: () => null, querySelectorAll: () => [],
  addEventListener: noop, createElement: el, contains: () => false,
};
let fetched = 0;
global.fetch = () => { fetched++; return new Promise(noop); };
eval(fs.readFileSync(file, "utf8"));
const W = window.Works;
const row = (o) => Object.assign({
  key: "k1", craft: "herbalist", icon: "steeping", name: "Borage Acetum", label: "Steeping",
  where: "carried", where_words: "carried", state: "working", ready_words: "ready in 6 days",
  ready_when: "day 15, morning", fraction: 0.25, can_collect: false, why_not: "Not ready yet",
  can_stop: false, stop_words: "" }, o);
const out = {
  working: W.rowHtml(row({}), "p"),
  readyHere: W.rowHtml(row({ state: "ready", ready_words: "ready now", fraction: 1, can_collect: true,
                             why_not: null }), "p"),
  readyAway: W.rowHtml(row({ key: "hide#1", state: "ready", ready_words: "ready since day 3",
                             fraction: 1, where: "place:t", where_words: "at Brannoc's tannery",
                             why_not: "Collect at Brannoc's tannery" }), "p"),
  stoppable: W.rowHtml(row({ craft: "enchanter", can_stop: true }), "p"),
  hostile: W.rowHtml(row({ name: '<img src=x onerror="1">' }), "p"),
  countReady: W.countHtml({ ready: 1, working: 2 }),
  countWorking: W.countHtml({ ready: 0, working: 2 }),
  countNone: W.countHtml({ ready: 0, working: 0 }),
  foot: W.footButton(),
  fetchedAtLoad: fetched,
};
W.sync("12|0/1");
out.fetchedBySyncWithNothingShown = fetched;
process.stdout.write(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def run():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "works.js"
        script.write_text(_NODE, encoding="utf-8")
        done = subprocess.run([node, str(script), json.dumps([str(WORKS)])],
                              capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout)


def test_a_ready_row_at_hand_has_the_one_gold_collect(run):
    """The defect this lane exists for: a finished jar had no Collect anywhere. A ready row
    the player can collect here carries Collect, gold (`is-go`) and live."""
    html = run["readyHere"]
    assert 'data-works-collect="k1"' in html and "is-go" in html
    assert "aria-disabled" not in html
    assert "ready now" in html and "is-ready" in html


def test_a_ready_row_elsewhere_refuses_collect_with_the_reason_in_words(run):
    """Work left at a place is collected there (rules/inprogress.py). The row keeps its
    Collect, refused (aria-disabled so it stays focusable and is read with its reason), not
    gold, with the server's own words beside it; never colour alone."""
    html = run["readyAway"]
    assert 'aria-disabled="true"' in html and "is-go" not in html
    m = re.search(r'aria-describedby="([^"]+)"', html)
    assert m and f'id="{m.group(1)}"' in html
    assert "Collect at Brannoc&#39;s tannery" in html
    assert "Steeping, at Brannoc&#39;s tannery" in html


def test_a_working_row_shows_the_servers_countdown_and_no_collect(run):
    """The countdown is the server's words ("ready in 6 days", "day 15, morning") and the
    dial is the server's fraction, drawn as is: the page computes no number."""
    html = run["working"]
    assert "data-works-collect" not in html
    assert "ready in 6 days" in html and "day 15, morning" in html
    assert 'stroke-dasharray="25.0 100"' in html
    assert "Steeping, carried" in html


def test_stop_only_where_the_craft_allows_it(run):
    """The owner (Round 5): "a steep must finish", so jars have no Stop; a craft that
    registers a cancel gets one, which confirms before anything is stopped."""
    assert "data-works-stop" not in run["working"]
    assert 'data-works-stop="k1"' in run["stoppable"]
    assert "data-works-stop-yes" not in run["stoppable"]


def test_names_are_escaped(run):
    """Names come from the world and the player; a row is markup."""
    assert "<img" not in run["hostile"] and "&lt;img" in run["hostile"]


def test_the_count_is_in_words_and_struck_in_gilt_when_ready(run):
    """The arrival of ready work is noticed by the door, not a pop-up (plan §6.10: "nothing
    pops over play"): "1 ready" in the theme's gilt count, "2 working" in quiet words, and
    nothing at all when nothing is in progress. The words are the button's own text, so its
    accessible name carries the count."""
    assert "v2-count" in run["countReady"] and "1 ready" in run["countReady"]
    assert "2 working" in run["countWorking"] and "v2-count" not in run["countWorking"]
    assert run["countNone"] == ""
    assert "data-works-open" in run["foot"] and "In progress" in run["foot"]


def test_a_turn_costs_no_second_request_when_nothing_shows_the_rows(run):
    """The door's count comes with the table's state; the rows are asked only while the
    panel or a shelf's group is on screen. Loading the file and a turn landing with neither
    open fetch nothing."""
    assert run["fetchedAtLoad"] == 0
    assert run["fetchedBySyncWithNothingShown"] == 0
