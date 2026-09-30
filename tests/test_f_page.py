"""The table's furniture on the page (Lane F): the conversation tray, the clock, the chip.

What Python can hold of it, plus the pure parts of the scripts run in node. The rest was
driven in headless Edge against the served template, with `/api/*` answered from a real
campaign's JSON (docs in the Lane F report): at 1440x900, docked and with the column
hidden, and at 375x812, with zero console errors; the tray opening and closing with Esc
returning focus to its tab; a conversation starting counting "Conversation, 2 new" on the
tab and opening nothing; the chip surviving a 422 with the words in the box; an eight-hour
turn spinning the clock and a thirty-minute one not; a resync of two days not; reduced
motion showing the still face for 1.6s.

The rulings these hold (docs/fix-interfaces.md §4):

  * Q42 — the conversation is its own tray with Ignore and Take your leave in it, and out
    of the column: no `#panel-conversation`, no bar button, no drawer tab for it.
  * Q45 — twelve identical black strips, no numerals, hour hand capped at two turns, a
    words-only caption at a day or more, fired only by this page's own post of 60+ min.
  * Q46/Q47/Q49 — no target picker; the combat bar's Cast… opens the same picker; the
    Spells button shows by `spellcasting.kind`.
  * The owner's motion rule, 2026-09-28: trays open and close in 150ms or less, nothing
    jumps under the pointer on hover.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser

import pytest
from django.test import Client

from pagesource import TABLE, TABLE_SCRIPTS


class _Tree(HTMLParser):
    VOID = {"input", "br", "img", "meta", "link", "hr", "source", "path", "circle", "rect"}

    def __init__(self):
        super().__init__()
        self.stack, self.elements = [], []

    def handle_starttag(self, tag, attrs):
        el = {"tag": tag, "attrs": dict(attrs), "ancestors": list(self.stack),
              "index": len(self.elements)}
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


def _one(els, id_):
    found = [e for e in els if e["attrs"].get("id") == id_]
    assert len(found) == 1, (id_, len(found))
    return found[0]


def _js(name: str) -> str:
    return (TABLE_SCRIPTS / name).read_text(encoding="utf-8")


def _css() -> str:
    src = TABLE.read_text(encoding="utf-8")
    return src[src.index("<style>"):src.index("</style>")]


def _rule(css: str, selector: str) -> str:
    at = css.index(selector + " {")
    return css[at:css.index("}", at)]


# --- the conversation tray (Q42) ------------------------------------------------------------

def test_the_conversation_is_a_tray_out_of_the_column(page):
    """Owner, Q42: "It should be removed from the panel." Nothing in the column, its bar
    or its drawer tabs names the conversation any more; the log and the controls are in
    `#talktray`, opened from `#talktab` (Talk in the top bar since the table rebuild; the
    left-edge tab it was kept its id)."""
    html, els = page
    assert 'id="panel-conversation' not in html
    assert not [e for e in els if e["attrs"].get("data-panel") == "conversation"]
    tray, aside = _one(els, "talktray"), _one(els, "panels")
    for i in ("convo", "convo-people", "convo-log", "convo-latest", "talk", "talkclose"):
        el = _one(els, i)
        assert tray in el["ancestors"] and aside not in el["ancestors"], i
    tab = _one(els, "talktab")
    assert tab["attrs"].get("aria-controls") == "talktray"
    assert tab["attrs"].get("aria-expanded") == "false"
    # Closed, it is out of the Tab order as well as off the screen.
    assert "inert" in tray["attrs"]
    assert '"conversation"' not in _js("07-panels.js").split("const PANEL_IDS")[1].split(";")[0]


def test_ignore_and_leave_sit_below_the_log_never_inside_it(page):
    """Disco Elysium's log held its live choices; scrolling back left players unable to
    reach them or leave the conversation. #talk comes after the log, outside it."""
    _, els = page
    log, talk = _one(els, "convo-log"), _one(els, "talk")
    assert log not in talk["ancestors"] and talk["index"] > log["index"]
    assert log["attrs"].get("role") == "log" and log["attrs"].get("aria-live") == "off"


def test_the_latest_button_floats_so_it_never_moves_the_controls():
    """Its coming and going would push Ignore and Take your leave under the pointer."""
    assert "position: absolute" in _rule(_css(), "#convo-latest")


# --- motion --------------------------------------------------------------------------------

def _seconds(rule: str) -> float:
    m = re.search(r"transition:\s*transform\s+([\d.]+)(m?s)", rule)
    assert m, rule
    return float(m.group(1)) / (1000 if m.group(2) == "ms" else 1)


def test_trays_and_the_drawer_open_in_150ms_or_less():
    """Owner, 2026-09-28: "i dont need reduced motion i just dont want the kind of motion
    that makes the pages or menus harder to use". The map tray and the drawer slid for
    320ms, long enough to be clicked through while still moving.

    Since the table rebuild the map tray and the drawer are gone (the Map and Sheet tabs,
    docs/table-rebuild-inventory.md M5 and N14), and the conversation tray opens in its
    column at once: no rule for it may slide, and none may take longer than 150ms."""
    css = _css()
    assert "#maptray {" not in css and "body.drawer aside {" not in css
    tray = [m.group(0) for m in re.finditer(r"#talktray[^{}]*\{[^}]*\}", css)]
    assert tray, "no rule draws the tray"
    for rule in tray:
        head = rule[:rule.index("{")]
        if "prefers-reduced-motion" in head:
            continue
        assert "translateX" not in rule, rule
        for dur, unit in re.findall(r"transition:[^;]*?([\d.]+)(m?s)", rule):
            assert float(dur) / (1000 if unit == "ms" else 1) <= 0.15, rule


def test_no_button_hops_under_the_pointer():
    """The page's old button base is fenced off the rebuild's controls (`:where(...)`),
    which wear the theme's cast iron; the suggestions are the desk's wax seals. None of
    them lifts on hover."""
    css = _css()
    fence = ":where(:not(.v2-btn, .v2-tabs > *, .v2-recess > *))"
    for selector in (f"button{fence}:hover:not(:disabled)", "#suggestions .sugg:hover"):
        assert "translateY" not in _rule(css, selector), selector
    theme = (TABLE.parents[2] / "static" / "css" / "theme-v2.css").read_text(encoding="utf-8")
    assert "translate" not in _rule(theme, ".v2-btn:hover")


def test_the_existing_reduced_motion_fallbacks_are_kept_and_the_tray_has_one():
    css = _css()
    assert re.search(r"prefers-reduced-motion: reduce\)\s*\{\s*#talktray \{ transition: none; \}", css)
    assert re.search(r"prefers-reduced-motion: reduce\)\s*\{\s*\*, \*::before, \*::after \{\s*"
                     r"animation: none !important; transition: none !important;", css)
    assert "CLOCK_STILL" in _js("09-clock.js") and "prefers-reduced-motion" in _js("09-clock.js")


# --- words on the page ----------------------------------------------------------------------

_BANNED = re.compile("[—–→←↑↓●○•✦]")


def _code_lines(text: str):
    for n, line in enumerate(text.splitlines(), 1):
        code = line.split("//", 1)[0] if not line.lstrip().startswith("*") else ""
        yield n, code


@pytest.mark.parametrize("name", ["08-conversation.js", "09-clock.js", "10-spells.js"])
def test_no_dash_arrow_or_dot_reaches_the_page_from_lane_fs_scripts(name):
    """Plain sentence-case words (owner's standing design instruction): no em or en dash,
    no arrow ("↓ latest" became "Go to the latest line"), no decorative dot or star (the
    design's "✦ Burning Hands" chip became a small-caps "Spell"). Comments may use them."""
    bad = [(n, c.strip()) for n, c in _code_lines(_js(name)) if _BANNED.search(c)]
    assert not bad, bad


# --- the spells, the chip and the refusal -----------------------------------------------------

def test_the_spell_picker_is_opened_by_script_from_both_doors(page):
    """The combat bar's Cast… opens the same picker (Q47), so neither button can be the
    popover's own invoker."""
    _, els = page
    for i in ("spellbtn", "cb-cast"):
        b = _one(els, i)
        assert "popovertarget" not in b["attrs"] and b["attrs"].get("aria-controls") == "spellpop"
    combat = _js("04-combat-and-turns.js")
    cast = combat[combat.index('if (t.closest("#cb-cast"))'):]
    assert cast.split("\n", 1)[0].count("castFromCombatBar(") == 1
    code = "\n".join(c for _n, c in _code_lines(combat))
    assert "pc.castable" not in code, "Cast… still reads the list that offers the whole book"


def test_the_spells_tab_cast_attaches_rather_than_casts():
    """Item 21.1: "I cast burning hands into the tree tops" did nothing, and the tab's
    Cast button could only aim at a person and fired at once."""
    state = _js("02-state.js")
    handler = state[state.index('const cast = e.target.closest(".castbtn");'):]
    handler = handler[:handler.index("return;")]
    assert "attachSpell(" in handler and "/api/cast" not in handler


def test_the_turn_sends_the_chip_and_clears_it_only_once_taken():
    turns = _js("04-combat-and-turns.js")
    submit = turns[turns.index('$("#sayform").onsubmit'):]
    submit = submit[:submit.index("\n};")]
    assert "attachments" in submit and "if (!text && !attached.length) return;" in submit
    take = turns[turns.index("async function takeTurn("):turns.index('$("#sayform").onsubmit')]
    assert take.index("render(s);") < take.index("clearAttachments()")
    assert "showRefusal(err.refusal)" in take
    post = _js("02-state.js")
    post = post[post.index("async function post("):post.index("function render(s, hold)")]
    assert "e.refusal = data.refusal" in post


def test_flash_is_defined_once():
    """02 has called `flash` for the talk buttons' failures since 2026-09-24 and nothing
    defined it: a refused Ignore threw a ReferenceError and showed the player nothing."""
    defs = [f.name for f in sorted(TABLE_SCRIPTS.glob("*.js"))
            if re.search(r"^function flash\(", f.read_text(encoding="utf-8"), re.M)]
    assert defs == ["08-conversation.js"]


# --- the pure parts, run -------------------------------------------------------------------

_STUBS = """
const document = { addEventListener() {}, getElementById() { return null; },
                   querySelector() { return null; }, body: { classList: { add() {}, remove() {} } } };
const window = { matchMedia: () => ({ matches: false }) };
const HOOKS = [];
function onRender(fn) { HOOKS.push(fn); }
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g,
  c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
"""


def _node(source: str, tmp_path) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    f = tmp_path / "probe.js"
    f.write_text(source, encoding="utf-8")
    done = subprocess.run([node, str(f)], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_the_hands_always_go_forward_and_the_hour_hand_stops_at_two_turns(tmp_path):
    """design F §8's clock cases: 08:00 to 09:00 is +30 and +360; 08:00 to 20:00 is a
    whole turn of the hour hand, not none; 23:00 to 01:00 is +60, never -300; 72 hours is
    two hour turns and the minute hand stopped at fourteen, "Three days later"."""
    src = _STUBS + _js("09-clock.js") + """
    const at = h => h * 60;
    console.log(JSON.stringify({
      hour: clockTravel(at(8), 60),
      half: clockTravel(at(8), 720),
      night: clockTravel(at(23), 120),
      days: clockTravel(at(8), 72 * 60),
      caps: [clockCaption(at(20), at(20) + 1440), clockCaption(at(8), at(8) + 3 * 1440),
             clockCaption(0, 15 * 1440), clockCaption(0, 22 * 1440), clockCaption(0, 40 * 1440)],
      said: clockSentence(at(8), at(11), "evening"),
      one: clockSentence(at(8), at(9), ""),
    }));"""
    got = _node(src, tmp_path)
    assert got["hour"] == {"hour0": 240, "minute0": 0, "hour": 30, "minute": 360}
    assert got["half"]["hour"] == 360
    assert got["night"]["hour"] == 60 and got["night"]["hour0"] == 330
    assert got["days"]["hour"] == 720 and got["days"]["minute"] == 14 * 360
    assert got["caps"] == ["The next day", "Three days later", "Two weeks later",
                           "Three weeks later", "Some weeks later"]
    assert got["said"] == "Three hours pass. It is now evening."
    assert got["one"] == "An hour passes."


def test_the_clock_fires_only_on_this_pages_own_post_of_an_hour_or_more(tmp_path):
    """Δ=59 does not fire and Δ=60 does; the first draw never fires; a render with no post
    before it (a resync, the other device's turn) never fires."""
    src = _STUBS.replace("addEventListener() {}", "addEventListener(k, fn) { (L[k] = L[k] || []).push(fn); }") \
        .replace("const document", "const L = {};\nconst document") + _js("09-clock.js") + """
    const fired = [];
    clockWhenClear = (b, a) => fired.push([b, a]);
    const hook = HOOKS[0];
    const post = before => L["table:posted"].forEach(fn => fn({ detail: { clockBefore: before } }));
    const state = m => ({ scene: { clock_minutes: m, day_part: "" } });
    post(480); hook(state(539), state(480));
    post(480); hook(state(540), state(480));
    post(480); hook(state(600), null);
    hook(state(9999), state(480));
    console.log(JSON.stringify(fired));"""
    assert _node(src, tmp_path) == [[480, 540]]


def test_the_log_groups_a_speakers_lines_and_names_who_grunted(tmp_path):
    src = _STUBS + _js("08-conversation.js") + """
    const e = (n, who, kind, text, extra = {}) => ({ n, t: 540, beat: 3, who, name:
      who === "you" ? "Bobby" : "the watchman waving traffic through", to: "you", kind, text,
      among: ["c1"], src: "tag", ...extra });
    const html = convoRows([e(1, "c1", "line", "Seen it? No,"), e(2, "c1", "line", "But I know."),
                            e(3, "c1", "vocal", "lets out a low, dry grunt"),
                            e(4, "you", "line", "Who?", { beat: 4 })], "c1");
    console.log(JSON.stringify({ html,
      involves: [convoInvolves(e(5, "you", "line", "x", { to: "" }), "c1"),
                 convoInvolves(e(6, "c2", "line", "x", { to: "you", among: [] }), "c1")] }));"""
    got = _node(src, tmp_path)
    html = got["html"]
    assert html.count('class="cl-name"') == 2, html          # one heading per speaker turn
    assert "The watchman waving traffic through lets out a low, dry grunt." in html
    assert '<div class="cl-turn cl-you"><span class="cl-name">You' in html
    assert html.count('<div class="cl-day">Day 1</div>') == 1
    assert got["involves"] == [True, False]
