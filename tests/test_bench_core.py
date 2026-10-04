"""The bench core (play/static/js/table/29-bench-core.js), split out of the herb bench's shell.

Lane U1 of the Blacksmithing revamp (docs/blacksmithing-ui-plan.md §3 and §15). Before the
split, 30-bench-shell.js was 1,240 lines in which the layer, Esc, the focus trap, the clock,
the footer and the flourish layer were tangled with the herbs. The forge is a second bench;
without a core it would copy those lines, and the two benches would drift apart: two Esc
behaviours, two focus traps, two clocks, two footers. These tests hold the split in place:
the core knows no craft, the herb shell re-implements none of it, and two benches mounted on
one page do not fight over the screen. The behaviour checks load the real files into node
with a small fake DOM (as tests/test_bench_games.py does for the games), so they run where
node is installed and skip, saying why, where it is not.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.test import Client

ROOT = Path(__file__).resolve().parent.parent
TABLE_JS = ROOT / "play" / "static" / "js" / "table"
CORE = TABLE_JS / "29-bench-core.js"
SHELL = TABLE_JS / "30-bench-shell.js"
HERB_MODULES = [TABLE_JS / f for f in ("31-bench-satchel.js", "32-bench-stage.js", "33-bench-games.js",
                                       "34-bench-tag.js", "35-bench-herbarium.js", "36-bench-perks.js")]


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code(text: str) -> str:
    """The source with its // comment lines and trailing // comments dropped, so a rule
    about what the code does is not tripped by a comment that explains it."""
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("//"):
            continue
        out.append(re.sub(r"\s//\s.*$", "", line))
    return "\n".join(out)


# --- the split, read statically ---------------------------------------------------------------

def test_the_core_knows_no_craft():
    """A core that names the herbs is not a core: the forge would mount on it and find the
    satchel's ids, the herb API's paths or "Herbalist" in its footer. The herb bench's own
    element ids, its routes and its words appear only in what 30 passes to `mount`, never
    in 29's code."""
    code = _code(_src(CORE))
    for word in ("/api/bench", "satchel", "Herbalist", "herbalism", "mortar", "grind",
                 '"bench"', "bench-stage", "bench-close", "bench-say", "bench-pops", "bench-foot",
                 "open-bench", "#bench", "craftpanel", "data-bench-open", "Recipes", "Herbarium"):
        assert word not in code, f"29-bench-core.js names {word!r}"


def test_the_herb_shell_does_not_reimplement_the_core():
    """The split's whole point: one Esc behaviour, one focus trap, one clock, one footer
    frame. Each marker below is a line of the machinery that lived in 30 before 2026-10-03;
    one of them back in 30 is the start of the second copy the split removed, and the two
    would drift (a fix to the trap in one bench and not the other)."""
    code = _code(_src(SHELL))
    for marker in ("escStack", "function trapRoot", "function focusables", "wasInert", "clockHome",
                   "Stop and keep what you have?", "csrftoken", "anim.finished", "Sound.unlock",
                   "data-bench-steady>Steady mode", "history.replaceState", "matchMedia",
                   "clockWhenClear", "verdictWord(", "VerdictSparks.burst", '"bench-modal bench-confirm"'):
        assert marker not in code, f"30-bench-shell.js still carries {marker!r}"
    core = _code(_src(CORE))
    for marker in ("escStack", "function trapRoot", "Stop and keep what you have?", "csrftoken",
                   "anim.finished", "Sound.unlock", "data-bench-steady>Steady mode", "clockWhenClear"):
        assert marker in core, f"29-bench-core.js lost {marker!r}"


def test_the_shell_got_smaller_by_what_the_core_holds():
    """Measured at the split: 30 was 1,240 lines; it came out at 919, with 533 in 29 (the
    core carries its own explanation of the shape and the mount options). A shell creeping
    back toward 1,240 is the core being copied back in a piece at a time."""
    shell = len(_src(SHELL).splitlines())
    assert shell < 1000, f"30-bench-shell.js is {shell} lines again"


def test_every_name_the_herb_modules_call_on_bench_is_still_defined():
    """31-36 reach the shell only through `window.Bench`, and none of them changed in the
    split. A name the split dropped (B.confirm, B.pushEsc, B.say, B.renderFoot, B.open...)
    would be a TypeError the first time a tile was clicked or a popover opened, and no
    static check of 29 or 30 alone would see it. Each name used in 31-36 must be assigned
    somewhere in 30-36: `B.name =`, a key of 30's `window.Bench = {...}` literal, or 30's
    `defineProperty(B, "name"`."""
    used = set()
    for path in HERB_MODULES:
        used |= set(re.findall(r"\bB\.([A-Za-z_]\w*)", _src(path)))
    defined = set()
    shell = _src(SHELL)
    literal = shell[shell.index("var B = window.Bench = {"):shell.index("};", shell.index("var B = window.Bench = {"))]
    defined |= set(re.findall(r"([A-Za-z_]\w*):\s", literal))
    defined |= set(re.findall(r'defineProperty\(B, "(\w+)"', shell))
    for path in [SHELL] + HERB_MODULES:
        defined |= set(re.findall(r"\bB\.([A-Za-z_]\w*)\s*=(?!=)", _src(path)))
    missing = sorted(used - defined)
    assert not missing, f"31-36 call Bench names nothing defines: {missing}"


def test_the_core_loads_before_the_herb_shell():
    """30 reads `window.BenchCore` the moment it runs, so 29 must be in the page and before
    it; loaded after, the herb bench throws on the table's first paint and the Herbalism
    button does nothing at all."""
    html = Client().get("/play/").content.decode("utf-8")
    core = html.index("/static/js/table/29-bench-core.js?v=")
    shell = html.index("/static/js/table/30-bench-shell.js?v=")
    assert html.index("/static/js/table/22-roll-verdict.js?v=") < core < shell
    assert html.count("/static/js/table/29-bench-core.js?v=") == 1


def test_the_core_runs_no_loop_and_carries_no_dash():
    """The herb bench's two standing rules, now owed by the core too (test_bench_ui names
    the files it checks, and 29 is new): an idle bench draws zero frames, so no setInterval
    and no requestAnimationFrame here; and zero em-dashes and en-dashes in any bench file
    (herb UI plan §8)."""
    text = _src(CORE)
    assert not re.findall(r"\b(setInterval|requestAnimationFrame)\s*\(", text)
    assert "—" not in text and "–" not in text


# --- behaviour, in node -----------------------------------------------------------------------

_NODE = r"""
const fs = require('fs'), vm = require('vm');
const [corePath, shellPath] = JSON.parse(process.argv[2]);

class El {
  constructor(id, opts) {
    opts = opts || {};
    this.id = id || ''; this.listeners = {}; this.cls = new Set(); this.hidden = !!opts.hidden;
    this.inert = false; this.parentNode = null; this.q = {}; this.auto = !!opts.auto;
    this.marks = new Set(opts.marks || []); this.attrs = {}; this.dataset = {}; this.style = {};
    this.innerHTML = ''; this.textContent = ''; this.removed = false; this.disabled = false;
    const self = this;
    this.classList = {
      add: (c) => self.cls.add(c), remove: (c) => self.cls.delete(c), contains: (c) => self.cls.has(c),
      toggle: (c, on) => { if (on === undefined) on = !self.cls.has(c); on ? self.cls.add(c) : self.cls.delete(c); return on; },
    };
  }
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  removeEventListener(t, f) { this.listeners[t] = (this.listeners[t] || []).filter((g) => g !== f); }
  fire(t, e) { e = e || {}; e.target = e.target || this; e.preventDefault = e.preventDefault || (() => {});
    e.stopPropagation = e.stopPropagation || (() => { e.stopped = true; });
    (this.listeners[t] || []).slice().forEach((f) => f(e)); return e; }
  focus() { doc.activeElement = this; }
  contains(x) { while (x) { if (x === this) return true; x = x.parentNode; } return false; }
  closest(sel) { return this.marks.has(sel) ? this : null; }
  querySelector(sel) {
    if (sel in this.q) return this.q[sel];
    if (this.auto) { const c = new El('', { auto: true }); c.parentNode = this; this.q[sel] = c; return c; }
    return null;
  }
  querySelectorAll() { return []; }
  appendChild(c) { c.parentNode = this; return c; }
  insertBefore(c) { c.parentNode = this; return c; }
  remove() { this.removed = true; this.parentNode = null; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  getClientRects() { return [1]; }
  get offsetWidth() { return 1; }
}

const ids = {};
const make = (id, opts) => (ids[id] = new El(id, opts));
const body = new El('body');
const behind = new El('stage');
const home = new El('home-of-clock');
const clock = make('clockpop'); clock.parentNode = home;
const replaced = [];
const store = {};
const location = { hash: '', pathname: '/play/', search: '' };
const doc = {
  body, activeElement: body, cookie: '', readyState: 'complete', listeners: {},
  getElementById: (id) => ids[id] || null,
  querySelector: () => null,
  querySelectorAll: (sel) => (sel === '#stage' ? [behind] : []),
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
  removeEventListener(t, f) { this.listeners[t] = (this.listeners[t] || []).filter((g) => g !== f); },
  createElement: () => new El('', { auto: true }),
  createTextNode: () => new El(''),
  contains: (x) => !!x && !x.removed,
};
const games = { paused: 0, resumed: 0, stopped: 0,
  pause() { this.paused++; }, resume() { this.resumed++; }, stop() { this.stopped++; } };
const sandbox = {
  document: doc, location, console, Math, JSON, Object, Array, Promise, String, Number, Date, Error,
  setTimeout, clearTimeout, CustomEvent: function () {},
  history: { replaceState(_s, _t, url) { replaced.push(url); location.hash = url.startsWith('#') ? url : ''; } },
  localStorage: { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } },
  matchMedia: () => ({ matches: false, addEventListener() {} }),
  addEventListener() {}, BenchGames: games,
  // Opening the herb bench asks the server for its state; here the answer never comes,
  // which is the bench's loading state, and nothing below needs more.
  fetch: () => new Promise(() => {}),
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(corePath, 'utf8'), sandbox);
const C = sandbox.BenchCore;
const tick = (ms) => new Promise((r) => setTimeout(r, ms || 0));
const out = {};

(async () => {
  // Two benches on one page, as the herb bench and the forge will be.
  const benches = {};
  const calls = { opened: [], closing: [], keys: [] };
  const live = { a: false, b: false };
  for (const n of ['a', 'b']) {
    make(n, { hidden: true }); make(n + '-close'); make(n + '-home'); make(n + '-stage');
    make(n + '-pops'); make(n + '-say'); make(n + '-foot'); make(n + '-foot-in');
    benches[n] = C.mount({
      layer: n, close: n + '-close', home: n + '-home', stage: n + '-stage', pops: n + '-pops',
      say: n + '-say', foot: n + '-foot', footIn: n + '-foot-in', hash: '#' + n, bodyClass: n + '-on',
      live: () => live[n], keys: (e) => calls.keys.push(n + ':' + e.key),
      opened: () => calls.opened.push(n), closing: () => calls.closing.push(n),
    });
  }
  const A = benches.a, B = benches.b, layerA = ids.a;
  const opener = new El('opener');

  A.openLayer(opener);
  out.open = { open: A.open, hidden: layerA.hidden, hash: location.hash, focus: doc.activeElement.id,
               inert: behind.inert, clockOn: clock.parentNode === ids['a-stage'], body: body.cls.has('a-on'),
               opened: calls.opened.slice(), isIn: layerA.cls.has('is-in') };

  B.openLayer(new El('x'));
  out.refused = { bOpen: B.open, bHidden: ids.b.hidden, current: C.current === A };

  // Esc runs the newest popover's closer, and only that.
  const shut = [];
  const pop1 = () => shut.push(1), pop2 = () => shut.push(2);
  A.pushEsc(pop1); A.pushEsc(pop2);
  const esc1 = layerA.fire('keydown', { key: 'Escape' });
  out.escStack = { shut: shut.slice(), stillOpen: A.open, stopped: !!esc1.stopped };
  A.dropEsc(pop2); A.dropEsc(pop1);

  // A digit reaches the bench's keys only when nobody is typing and nothing is open.
  layerA.fire('keydown', { key: '3' });
  layerA.fire('keydown', { key: '4', target: Object.assign(new El('q'), { tagName: 'INPUT' }) });
  A.pushEsc(pop1); layerA.fire('keydown', { key: '5' }); A.dropEsc(pop1);
  out.keys = calls.keys.slice();

  // A live game: Esc and Close both ask, and the layer stays.
  live.a = true;
  layerA.fire('keydown', { key: 'Escape' });
  await tick();
  const wrap = ids['a-pops'];   // the confirm was appended to the layer's pops
  out.liveEsc = { stillOpen: A.open, paused: games.paused, escOpen: A.escOpen() };
  A.closeLayer();
  out.liveClose = { stillOpen: A.open, escOpen: A.escOpen() };
  // "Keep playing": the confirm's safe button, which the core focused, resumes the game.
  const keep = doc.activeElement;
  keep.fire('click', {});
  await tick();
  out.keep = { resumed: games.resumed, stillOpen: A.open, escOpen: A.escOpen() };

  // Game over: Esc closes, focus goes back to the opener, everything is put back.
  live.a = false;
  layerA.fire('keydown', { key: 'Escape' });
  out.close = { open: A.open, hidden: layerA.hidden, hash: location.hash, focus: doc.activeElement.id,
                inert: behind.inert, clockHome: clock.parentNode === home, body: body.cls.has('a-on'),
                closing: calls.closing.slice(), current: C.current };

  // An opener that left the page sends focus home.
  const gone = new El('gone');
  A.openLayer(gone); gone.removed = true; A.closeLayer();
  out.home = doc.activeElement.id;

  // Now the other bench may open.
  B.openLayer(new El('y'));
  out.bOpens = B.open; B.closeLayer();

  // The footer frame, and the Steady switch it owns.
  make('f', { hidden: true }); make('f-in'); make('f-foot'); make('f-say');
  const foot2 = C.mount({ layer: 'f', footIn: 'f-in', foot: 'f-foot', say: 'f-say', clockId: 'f-clock',
    footer: () => ({ clock: 'Day 2, 9am', trackLabel: 'Your smithing',
                     track: { title: 'Blacksmith', level: 1, need: 0, have: 0, mp: 7 }, picks: 1,
                     buttons: '<button type="button" class="bf-btn">Ledger</button>' }) });
  foot2.renderFoot();
  out.forgeFoot = ids['f-in'].innerHTML;
  const sw = new El('sw', { marks: ['[data-bench-steady]'] });
  ids['f-foot'].fire('click', { target: sw });
  await tick(50);
  out.steady = { stored: store['pgm.steady'], said: ids['f-say'].textContent };
  store['pgm.steady'] = '0';

  // The herb shell, loaded for real on the core, with only its layer's ids in the page.
  for (const id of ['bench', 'bench-close', 'bench-stage', 'bench-say', 'bench-pops', 'bench-foot',
                    'bench-foot-in', 'open-bench', 'bench-tool', 'bench-chips', 'bench-info',
                    'bench-why', 'bench-roll', 'bench-game']) make(id, { hidden: id === 'bench' });
  vm.runInContext(fs.readFileSync(shellPath, 'utf8'), sandbox);
  const H = sandbox.Bench;
  H.state = { clock: { label: 'Day 3, 4pm' },
              track: { level: 3, mp: 50, to_next: { need: 40, have: 10 }, picks_banked: 2 } };
  H.renderFoot();
  out.herbFoot = ids['bench-foot-in'].innerHTML;
  H.state = { clock: { label: 'Day 3, 4pm' }, track: { level: 5, mp: 120, to_next: null, picks_banked: 1 } };
  H.renderFoot();
  out.herbFootTop = ids['bench-foot-in'].innerHTML;
  out.herbApi = ['openBench', 'closeBench', 'pushEsc', 'dropEsc', 'confirm', 'say', 'renderFoot',
                 'tickClock', 'focusMat', 'flourish', 'api', 'minutes', 'span', 'sign', 'sound',
                 'reduced', 'steady', 'setSteady', 'esc'].filter((n) => typeof H[n] !== 'function');
  out.herbOpenBefore = H.open;
  // The herb bench opens on the core, and `Bench.open` is the core's own state.
  H.openBench(ids['open-bench']);
  out.herbOpen = { open: H.open, core: C.current && C.current.layer === ids.bench, hash: location.hash };
  // While its game is live, Close asks rather than closes (the herb's B.live, read by the core).
  H.live = { token: 't' };
  H.closeBench();
  out.herbLiveClose = H.open;
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


@pytest.fixture(scope="module")
def run():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "core.js"
        script.write_text(_NODE, encoding="utf-8")
        done = subprocess.run([node, str(script), json.dumps([str(CORE), str(SHELL)])],
                              capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout)


def test_opening_puts_the_layer_up_and_the_table_behind_it(run):
    """What the herb bench did on open, now the core's for any bench (herb UI plan §4.1):
    the layer shows and fades in, the table behind goes inert, the scene clock stands on the
    bench's stage (09's time-skip clock sits in #stage at z 8; left there, an hour-long
    step would turn it under the z 35 layer where nobody sees it), the hash is written, and
    focus lands in the layer (on Close when the bench names nothing first)."""
    o = run["open"]
    assert o == {"open": True, "hidden": False, "hash": "#a", "focus": "a-close", "inert": True,
                 "clockOn": True, "body": True, "opened": ["a"], "isIn": True}, o


def test_a_second_bench_cannot_open_over_the_first(run):
    """Two layers at z 35 would each trap Tab and each answer Esc: the double-handler bug
    the stacked-modal pattern exists to prevent, and new with the second bench. Opening one
    while the other is open is refused, and is allowed again once it closes."""
    assert run["refused"] == {"bOpen": False, "bHidden": True, "current": True}
    assert run["bOpens"] is True


def test_esc_closes_one_popover_at_a_time(run):
    """One Esc, one layer: with two popovers open, Esc runs the newest closer only, the
    bench stays, and the key goes no further (the table's own document shortcuts, "m" for
    the map, must not act behind the bench)."""
    assert run["escStack"] == {"shut": [2], "stillOpen": True, "stopped": True}


def test_the_benchs_keys_wait_while_typing_or_a_popover_is_open(run):
    """The herb bench's 1-9 keys switch the method, which empties the pot. Typed into the
    satchel's search box, or pressed while a confirm is open, a digit would do that behind
    the player's back; the core asks a bench's `keys` only when nobody is typing and no
    popover holds Esc. Of three digits pressed (plain, in an input, under a popover) exactly
    the plain one reaches the bench."""
    assert run["keys"] == ["a:3"]


def test_a_live_game_is_never_dropped_on_the_floor(run):
    """Herb UI plan §4.1: while a minigame is live, Esc asks "Stop and keep what you
    have?" and so does Close; the game pauses while it asks, the bench stays open, and
    "Keep playing" resumes it. Closing straight away would strand the reserved materials,
    and two benches each with their own copy of this rule is how one of them forgets it."""
    assert run["liveEsc"] == {"stillOpen": True, "paused": 1, "escOpen": True}
    assert run["liveClose"] == {"stillOpen": True, "escOpen": True}, "Close asked a second time"
    assert run["keep"] == {"resumed": 1, "stillOpen": True, "escOpen": False}


def test_closing_puts_everything_back_and_returns_focus(run):
    """On close: the layer hides, the table is live again, the clock goes home, the hash
    is cleared, the bench's own `closing` runs, and focus returns to what opened it, or to
    the bench's home button when that has left the page (the WAI-ARIA dialog pattern;
    focusing a removed element drops focus to <body>, and the next Tab starts from the top
    of a table the player cannot see the place of)."""
    c = run["close"]
    assert c == {"open": False, "hidden": True, "hash": "", "focus": "opener", "inert": False,
                 "clockHome": True, "body": False, "closing": ["a"], "current": None}, c
    assert run["home"] == "a-home"


_STEADY = ('<button type="button" class="bf-btn bf-steady" role="switch" aria-checked="false" '
           'data-bench-steady>Steady mode<span class="bf-switch" aria-hidden="true"></span></button>')
_HERB_BUTTONS = ('<button type="button" class="bf-btn" data-bench-recipes aria-haspopup="dialog">Recipes</button>'
                 '<button type="button" class="bf-btn" data-bench-herbarium>Herbarium</button>')


def test_the_herb_footer_is_byte_for_byte_what_it_was(run):
    """The split promised no visible change. The footer is the one piece whose markup moved
    from the herb shell into the core's frame, so it is compared whole against the string
    the pre-split renderFoot built for the same state (copied from 30-bench-shell.js at
    4b25335): mid-level with a mastery line at a quarter and two picks banked, and at the
    top of the track with no next level, where the line is full and the mastery stands
    alone."""
    expect = ('<span class="bf-clock" id="bench-clock">Day 3, 4pm</span>'
              '<span class="bf-track" role="group" aria-label="Your herbalism">'
              '<span class="bf-level">Herbalist 3</span>'
              '<span class="bf-line" aria-hidden="true"><i style="transform:scaleX(0.250)"></i></span>'
              '<span class="bf-mp">10 / 40</span></span>'
              '<button type="button" class="bf-btn bf-perks" data-bench-perks>2 perks to pick</button>'
              '<span class="bf-gap"></span>' + _HERB_BUTTONS + _STEADY)
    assert run["herbFoot"] == expect
    top = ('<span class="bf-clock" id="bench-clock">Day 3, 4pm</span>'
           '<span class="bf-track" role="group" aria-label="Your herbalism">'
           '<span class="bf-level">Herbalist 5</span>'
           '<span class="bf-line" aria-hidden="true"><i style="transform:scaleX(1.000)"></i></span>'
           '<span class="bf-mp">120 mastery</span></span>'
           '<button type="button" class="bf-btn bf-perks" data-bench-perks>1 perk to pick</button>'
           '<span class="bf-gap"></span>' + _HERB_BUTTONS + _STEADY)
    assert run["herbFootTop"] == top


def test_a_second_bench_gets_the_same_footer_frame_with_its_own_words(run):
    """The forge's footer (blacksmithing UI plan §6.8) is "as the herb bench": the clock,
    the level and mastery line, the picks, its own buttons, Steady mode. Drawn by the same
    frame with its own clock id (two `bench-clock` ids in one page would make 09 and a
    screen reader find the wrong clock), and the Steady switch works there too."""
    f = run["forgeFoot"]
    assert f.startswith('<span class="bf-clock" id="f-clock">Day 2, 9am</span>')
    assert 'aria-label="Your smithing"' in f and "Blacksmith 1" in f and "7 mastery" in f
    assert "1 perk to pick" in f and "Ledger</button>" in f and f.endswith(_STEADY)
    assert "Herbalist" not in f and "Recipes" not in f
    assert run["steady"] == {"stored": "1", "said": "Steady mode on."}


def test_the_herb_shell_loads_on_the_core_with_its_api_whole(run):
    """30 runs on 29 alone (no stage, no games, no sound) and still answers every name the
    other herb modules call as a function; `Bench.open` is the core's state, read through a
    getter, so 31-36 and the core can never disagree about whether the bench is open."""
    assert run["herbApi"] == []
    assert run["herbOpenBefore"] is False
    assert run["herbOpen"] == {"open": True, "core": True, "hash": "#bench"}
    assert run["herbLiveClose"] is True, "Close dropped the herb bench's live game"


def test_the_clock_face_waits_for_the_steps_game():
    """Seen live on the forge at the merge (2026-10-04): the four-second clock face turned
    over the anvil for the game's opening seconds, covering the blank while the first blows
    had to be struck; 09 waits only for the dice mat, and the game starts as the mat closes.
    The herb bench had the same overlap. A roll a game follows holds the turn, and the bench
    releases it when the game settles, with no timer polling (the core runs no loop)."""
    core = _code(_src(CORE))
    assert "C.releaseClock = function" in core and "heldClock = [before, after]" in core
    for path in (SHELL, TABLE_JS / "40-forge-shell.js"):
        shell = _src(path)
        assert "tickClock(r.minutes, r.clock, !!(r.roll && r.roll.success && r.token))" in shell, path
        assert shell.count("C.releaseClock()") >= 3, path
