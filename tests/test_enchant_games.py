"""The enchanter's minigames (enchanting lane U2): the six games in
`play/static/js/enchant-games/`, the day-phase band in the shared strip frame
`play/static/js/table/33-bench-games.js`, and `play/static/css/enchant-games.css`.

Mirrors tests/test_forge_games.py: most checks read the files, and the behaviour group loads the
frame and the games into node and plays every game through `BenchGames.simulate`, the frame's
own headless path (the same per-frame `advance` as the strip's loop). Every frame the driver
also calls the game's `draw` on a stub canvas, so a draw that throws fails here rather than in
the owner's strip. Bots read only the state a game hands the stage, so a bot that wins proves
the game can be won from what it shows: by number keys, by the arrows, by mouse, in Steady mode
(where no release is ever heard), and, for the two timing games, by the counted beat alone
(the reduced-motion form, where nothing moves).

Each docstring names the defect the check prevents.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FRAME = ROOT / "play" / "static" / "js" / "table" / "33-bench-games.js"
GAMES = ROOT / "play" / "static" / "js" / "enchant-games"
CSS = ROOT / "play" / "static" / "css" / "enchant-games.css"
THEME = ROOT / "play" / "static" / "css" / "theme-v2.css"
UI_PLAN = ROOT / "docs" / "enchanting-ui-plan.md"
CONTRACTS = ROOT / "docs" / "enchanting-contracts.md"
HERB_GAMES = ROOT / "play" / "static" / "js" / "bench-games"
FORGE_GAMES = ROOT / "play" / "static" / "js" / "forge-games"

METHODS = ["prepare", "attune", "bind", "refine", "unbind", "cleanse"]
ORDER_GAMES = ["prepare", "unbind", "cleanse"]
HERB_METHODS = ["grind", "mix", "brew", "dry", "reduce", "extract", "infuse", "steep", "neutralize"]
FORGE_METHODS = ["smelt", "alloy", "forge", "quench", "temper", "fold", "hone", "assemble", "finish",
                 "strengthen"]
TIER_NAMES = ["Crude", "Sound", "Fine", "Superior", "Flawless"]
PLANETS = ["planet", "Planet", "Mars", "Saturn", "Jupiter", "Venus", "Mercury", "Moon", "Sun"]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _code(js: str) -> str:
    """A script without its comments, so a rule named in a comment is not mistaken for code."""
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return "\n".join(ln if "://" in ln else ln.split("//", 1)[0] for ln in js.splitlines())


def _strings(js: str) -> list[str]:
    return [a or b for a, b in re.findall(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'', _code(js))]


def _game(method: str) -> Path:
    return GAMES / f"{method}.js"


def _list(js: str, name: str) -> list[str] | None:
    m = re.search(name + r"\s*:\s*\[([^\]]*)\]", _code(js))
    return None if not m else re.findall(r'"([^"]*)"', m.group(1))


# --- every method with a game, one file --------------------------------------------------------

def test_the_six_games_are_the_contracts_methods():
    """Contracts §6 names the bench's methods; Read and Identify have no game (UI plan §9:
    "tasting and assay have none"). A drifted list (a missing `cleanse`, a stray `read`) would
    leave the bench rolling a success with no game, which `BenchGames.play` rejects."""
    m = re.search(r"Methods \(revamp plan §10\): `([^`]*)`", _read(CONTRACTS))
    assert m, "contracts §6 no longer lists the methods where this test reads them"
    contract = [x.strip() for x in m.group(1).split(",")]
    assert [x for x in contract if x not in ("read", "identify")] == METHODS
    assert sorted(p.stem for p in GAMES.glob("*.js")) == sorted(METHODS)


@pytest.mark.parametrize("method", METHODS)
def test_every_enchant_game_registers_like_the_others(method):
    """Contracts §13: an enchant game registers on `window.BenchGameDefs[method]` with
    `track: "enchant"`, as the forge games do, so the one frame runs all three benches and
    `methodsFor("enchant")` finds them. The first-time card is up for two seconds; a longer
    one starts the game under the player's eyes."""
    code = _code(_read(_game(method)))
    assert re.search(r"defs\." + method + r"\s*=\s*\{", code), f"{method}.js does not register defs.{method}"
    assert f'id: "{method}"' in code
    assert 'track: "enchant"' in code
    assert re.search(r"create\s*:\s*function\s*\(ctx\)", code)
    first = re.search(r'first:\s*"([^"]+)"', code)
    assert first and len(first.group(1)) <= 100, f"{method}.js: first-time card {first and first.group(1)!r}"


@pytest.mark.parametrize("method", METHODS)
def test_steady_mode_declares_no_hold(method):
    """Potion Craft added Auto Hold after players reported hand fatigue (herbalism prior art,
    devlog #14), and the frame drops every release in Steady mode. No enchant game holds
    anything in either mode; each must still read Steady mode (UI plan §9's column)."""
    js = _read(_game(method))
    assert _list(js, "HOLDS_STEADY") == [] and _list(js, "HOLDS") == []
    assert _list(js, "KEYS"), f"{method}.js listens for no key: not playable by keyboard"
    assert re.search(r"ctx\.steady\b", _code(js)), f"{method}.js ignores Steady mode"


@pytest.mark.parametrize("method", METHODS)
def test_no_game_runs_its_own_loop_listens_or_plays_sound(method):
    """One loop, only while a game runs (the frame's rule; the herb harness measured 0 frames in
    the 2s after a game ended). A game with its own frames, timers or listeners would outlive the
    strip; one calling Sound itself would skip the frame's guard and break on a page with none."""
    code = _code(_read(_game(method)))
    for banned in ("requestAnimationFrame", "setInterval", "setTimeout", "addEventListener",
                   "Sound", ".animate(", "import ", "require(", "fetch(", "XMLHttpRequest"):
        assert banned not in code, f"{method}.js uses {banned}"


@pytest.mark.parametrize("method", METHODS)
def test_every_game_draws_shapes_and_its_own_aim(method):
    """Never colour alone (Game Accessibility Guidelines; the curse's ring is cross-hatched with
    a saw edge, not only red), and no game depends on the cursor art (the candle cursor's hotspot
    drifted in 0.2.2): each draws its zones through the kit's shapes and its own reticle."""
    code = _code(_read(_game(method)))
    assert re.search(r"k\.(dialBand|barBand|ring|notch|pip)\(", code)
    assert "k.reticle(" in code and "ctx.pointer" in code, f"{method}.js draws no aim of its own"


@pytest.mark.parametrize("method", METHODS)
def test_enchant_sounds_are_the_ui_plans_names(method):
    """UI plan §11 lists the enchant bus's events and unknown names are silent (contracts §13),
    so a game naming `enchant.prepare.hit` (no such event) would play nothing and nobody would
    hear why. Every SOUNDS value must be one of §11's names."""
    plan = _read(UI_PLAN)
    sec = plan[plan.index("## 11. Sound"):plan.index("## 12.")]
    known = set(re.findall(r"`(enchant\.[a-z.]+)`", sec))
    m = re.search(r"SOUNDS:\s*\{([^}]*)\}", _code(_read(_game(method))))
    assert m, f"{method}.js names no enchant sounds; the frame would play bench.* for it"
    names = re.findall(r'"([^"]+)"', m.group(1))
    assert names and all(n in known for n in names), f"{method}.js: {names} not all in {sorted(known)}"


def test_only_bind_carries_the_day_phase_band():
    """The owner's round 4: the favourable day phase widens BIND's windows (x1.5), and only
    Bind's (rules/enchanter.py tuning_for folds `phase_widen` in for bind alone). A band on
    another game would tell the player the hour matters where it does not."""
    for m in METHODS:
        has = "HOUR: true" in _code(_read(_game(m)))
        assert has == (m == "bind"), m


# --- copy, tokens, the world ---------------------------------------------------------------------

def _lane_files() -> list[Path]:
    return [CSS, FRAME] + [_game(m) for m in METHODS]


def test_the_page_never_names_a_tier():
    """The server turns the score into a tier (enchant_views finish, `crafting.tier_from_score`);
    the page never names one. "Sound" is a tier name, which is why Cleanse calls the curse's
    neighbours whole sigils."""
    for p in [FRAME] + [_game(m) for m in METHODS]:
        for s in _strings(_read(p)):
            for name in TIER_NAMES:
                assert not re.search(rf"\b{name}\b", s), f"{p.name} names the tier {name!r} in {s!r}"


def test_no_planet_reaches_the_page():
    """The owner, round 4 point 10: "this is not earth", and named planets would not be
    world-agnostic. The favourable time is the essence family's phase of the day. The UI plan
    and the contracts still say planet in places (the lead's correction to §13); a game or the
    band that copied them would put Mars on a world that has none."""
    for p in [FRAME, CSS] + [_game(m) for m in METHODS]:
        code = _code(_read(p)) if p.suffix == ".js" else re.sub(r"/\*.*?\*/", "", _read(p), flags=re.S)
        for word in PLANETS:
            assert not re.search(rf"\b{word}\b", code), f"{p.name} says {word!r} outside a comment"


def test_no_em_or_en_dashes_in_the_lanes_files():
    """UI plan §8: no em-dashes in new strings; checked over whole files, comments included."""
    for p in _lane_files():
        text = _read(p)
        for ch in ("—", "–"):
            assert ch not in text, f"{p.relative_to(ROOT)} has a dash on line {text[:text.index(ch)].count(chr(10)) + 1}"


def test_no_control_bytes_in_the_lanes_files():
    """Bash heredocs have written `\\b` into source as a literal backspace byte (CLAUDE.md,
    everyday traps), silently breaking a regex while tests passed; Prepare's number keys are a
    regex with `^[1-6]$`."""
    for p in _lane_files():
        bad = [c for c in _read(p) if ord(c) < 32 and c not in "\n\r\t"]
        assert not bad, f"{p.name} has control bytes {bad!r}"


def test_the_stylesheet_uses_theme_tokens_only():
    """Keep the colours (owner, 2026-09-28; UI plan §4: "No new colours"). An essence's colour is
    content, drawn as a swatch on the canvas; a raw colour here would be a second palette."""
    css = re.sub(r"/\*.*?\*/", "", _read(CSS), flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
    assert not re.search(r"\b(rgb|rgba|hsl|hsla)\(", css)
    theme = _read(THEME)
    for tok in set(re.findall(r"var\((--[a-z0-9-]+)\)", css)):
        assert f"{tok}:" in theme, f"enchant-games.css uses {tok}, which theme-v2.css does not define"


# --- the frame: the herb and forge games must not notice --------------------------------------

def test_the_band_and_the_phase_are_gated_on_hour():
    """The band is "optional, as the forge added the heat gauge" (UI plan §6.4) and the herb and
    forge games must stay as they were. Every enchant path in the frame is behind a definition's
    HOUR or an hour it produced: the hour is read only for a HOUR game, the band's height is
    taken only with an hour, the phase joins the sound's voice only with an hour, and the herb
    list is still the literal nine."""
    code = _code(_read(FRAME))
    assert code.count("readHour(") == 3, "readHour is called outside play, simulate and its definition"
    assert "var hour = def.HOUR ? readHour(" in code
    assert "hour: def.HOUR ? readHour(" in code
    assert "var gh = r.heat ? GAUGE_H : r.hour ? HOUR_H : 0;" in code
    assert "else if (r.hour) drawHourBand(r, g, r.W, r.H - gh);" in code
    assert "if (r.hour) voice.phase = " in code
    assert "if (def.HOUR && hour) {" in code
    m = re.search(r"var METHODS = \[([^\]]*)\]", code)
    assert re.findall(r'"([a-z]+)"', m.group(1)) == HERB_METHODS
    # Every literal sound name in the frame is still the bench bus's (test_bench_games reads it).
    assert all(n.startswith("bench.") for n in re.findall(r'sound\("([^"]+)"', code))


def test_the_bands_fallback_is_skys_own_day():
    """rules/sky.py owns the day's phases (lane G); the band falls back to a copy when the
    server's hour carries no windows. A copy that drifted (noon at 12:00-13:00 when sky says
    11:00-13:00) would outline the wrong stretch of the day under the right words."""
    from rules import sky

    code = _code(_read(FRAME))
    body = re.search(r"var PHASE_WINDOWS = \[(.*?)\];", code, re.S).group(1)
    js = [{"phase": p, "starts": int(s), "ends": int(e)}
          for p, s, e in re.findall(r'phase: "([a-z]+)", starts: (\d+), ends: (\d+)', body)]
    assert js == sky.windows()
    names = re.search(r"var PHASE_NAMES = \{(.*?)\};", code, re.S).group(1)
    assert sorted(re.findall(r"([a-z]+): \"", names)) == sorted(sky.PHASES)


# --- behaviour, in node ------------------------------------------------------------------------

_DRIVER = r"""// Node driver for tests/test_enchant_games.py: loads the frame and the six enchant games
// (and, for the gating checks, the herb and forge games) into a bare sandbox and plays each one
// through `BenchGames.simulate`, the frame's own headless path. Every frame the game's draw runs
// on a stub canvas, so a draw that throws fails the run. One JSON object comes out.
"use strict";
const fs = require("fs"), vm = require("vm");
const files = JSON.parse(process.argv[2]);
const sandbox = { window: {}, Math, JSON, Object, Array, Promise, console, performance: { now: () => 0 } };
sandbox.window.window = sandbox.window;
vm.createContext(sandbox);
for (const f of files) vm.runInContext(fs.readFileSync(f, "utf8"), sandbox);
const W = sandbox.window, BG = W.BenchGames;
const DT = 1 / 60;
const ENCHANT = ["prepare", "attune", "bind", "refine", "unbind", "cleanse"];
const stub = new Proxy({}, {
  get(t, k) {
    if (k === "measureText") return (s) => ({ width: String(s).length * 6.5 });
    if (k === "createLinearGradient") return () => ({ addColorStop() {} });
    if (k in t) return t[k];
    return () => {};
  },
  set(t, k, v) { t[k] = v; return true; }
});
const NOON_IN = { phase: "noon", now: "noon", inside: true, minutes_left: 42, minutes_until: 0, widen: 1.5, words: "Noon, 42 minutes left" };
const NOON_OUT = { phase: "noon", now: "dusk", inside: false, minutes_left: 0, minutes_until: 600, widen: 1.0, words: "Noon in 10 hours" };
// The server's seat rows as rules/enchanter.py seat_signs writes them: a longsword's point and
// edge both sit on its cold iron head, its guard on brass fittings; two seated essences.
const SEATS = [
  { seat: "point", name: "Point", polarity: ["weapon", "any"], material: "cold iron",
    sign: "takes weapon or any essences; suits what loves cold iron", seated: "stock:fl", essence: "Flaming essence", color: "#d0602a" },
  { seat: "edge", name: "Edge", polarity: ["weapon", "any"], material: "cold iron",
    sign: "takes weapon or any essences; suits what loves cold iron", seated: null, essence: null, color: null },
  { seat: "guard", name: "Guard", polarity: ["weapon", "any"], material: "brass",
    sign: "takes weapon or any essences; suits what loves brass", seated: "stock:ke", essence: "Keen essence", color: "#9ab0c8" },
];
const DEFAULTS = {
  prepare: { seq: ["chalk", "salt", "ink", "ink", "bell"] },
  attune: { seats: SEATS },
  bind: { hour: NOON_OUT },
  refine: {},
  unbind: { seq: ["sigil", "sigil", "enhancement"] },
  cleanse: { seq: ["sigil", "sigil", "sigil"] },
};

function sim(method, o) {
  o = o || {};
  const base = Object.assign({}, DEFAULTS[method] || {});
  return BG.simulate(Object.assign(base, { method, tuning: Object.assign({ seed: 5, difficulty: 0.45 }, o.tuning || {}) },
    o.steady ? { steady: true } : {}, o.opts || {}));
}

function input(s) {
  return {
    tap(key) { s.press(key); if (!s.ctx.steady) s.release(key); },
    click(x, y) { s.pointer("down", x, y); s.pointer("up", x, y); },
  };
}

// --- bots, reading only state() ------------------------------------------------------------
function nextFocus(st, target, n) { return st === target ? null : "ArrowRight"; }
const KEYS = {
  prepare: (s, io) => {
    const st = s.game.state(); if (st.phase !== "lay") return;
    io.tap(String(st.pieces.indexOf(st.seq[st.step]) + 1));
  },
  unbind: (s, io) => { const st = s.game.state(); if (st.next) io.tap(String(st.next)); },
  cleanse: (s, io) => { const st = s.game.state(); if (st.step < st.steps) io.tap(String(st.step + 1)); },
};
function attuneTarget(st) {
  return st.seats.findIndex((x) => x.room && x.answers.indexOf(st.held) >= 0);
}
const ARROWS = {
  prepare: (s, io) => {
    const st = s.game.state(); if (st.phase !== "lay") return;
    const want = st.pieces.indexOf(st.seq[st.step]);
    io.tap(st.focus === want ? "Space" : "ArrowRight");
  },
  attune: (s, io) => {
    const st = s.game.state(); if (st.placed >= st.count) return;
    if (st.row === "phials") { io.tap("Enter"); return; }
    const want = attuneTarget(st);
    io.tap(st.seatFocus === want ? "Enter" : "ArrowRight");
  },
  bind: (s, io) => { const st = s.game.state(); if (!st.struck && st.offset_s >= 0) io.tap("Space"); },
  refine: (s, io) => { const st = s.game.state(); if (st.open && st.offset_s >= 0) io.tap("Space"); },
  unbind: (s, io) => {
    const st = s.game.state(); if (!st.next) return;
    const want = st.marks.findIndex((m) => m.cut === st.next && !m.gone);
    io.tap(st.focus === want ? "Space" : "ArrowRight");
  },
  cleanse: (s, io) => {
    const st = s.game.state(); if (st.step >= st.steps || st.unpicked[st.step] !== null) return;
    const want = st.marks.findIndex((m) => m.turn === st.step && !m.gone);
    io.tap(st.focus === want ? "Space" : "ArrowRight");
  },
};
const MOUSE = {
  prepare: (s, io) => {
    const st = s.game.state(); if (st.phase !== "lay" || !st.tiles.length) return;
    const b = st.tiles[st.pieces.indexOf(st.seq[st.step])]; io.click(b.x, b.y);
  },
  attune: (s, io) => {
    const st = s.game.state(); if (st.placed >= st.count || !st.seatAt.length) return;
    if (st.held < 0) { const b = st.phialAt.find((x) => x); io.click(b.x, b.y); return; }
    const b = st.seatAt[attuneTarget(st)]; io.click(b.x, b.y);
  },
  bind: (s, io) => { const st = s.game.state(); if (!st.struck && st.offset_s >= 0) io.click(100, 40); },
  refine: (s, io) => { const st = s.game.state(); if (st.open && st.offset_s >= 0) io.click(100, 40); },
  unbind: (s, io) => {
    const st = s.game.state(); if (!st.next) return;
    const m = st.marks.find((x) => x.cut === st.next && !x.gone); io.click(m.x, m.y);
  },
  cleanse: (s, io) => {
    const st = s.game.state(); if (st.step >= st.steps || st.unpicked[st.step] !== null) return;
    const m = st.marks.find((x) => x.turn === st.step && !x.gone); io.click(m.x, m.y);
  },
};
// The reduced-motion player: hears only the counted beat ("3", "2", "1", "Now") and presses
// one beat after "1", by the rhythm the first three set. It never reads where anything is.
function rhythm() {
  let last = 0, at = {}, pressed = -1;
  return (s, io) => {
    const st = s.game.state(), t = s.t(), key = st.crest != null ? st.crest : st.draw;
    if (st.beat !== last) { at[st.beat] = t; last = st.beat; }
    // "Now" itself lights a little before the crest (the window's edge), so the press is timed
    // by the rhythm, not by waiting to see "Now".
    if (at[3] != null && at[2] != null && pressed !== key) {
      const beat = at[3] - at[2];
      if (t >= at[3] + beat - DT / 2) { io.tap("Space"); pressed = key; at = {}; }
    }
  };
}

function play(method, o) {
  o = o || {};
  const s = sim(method, o);
  const io = input(s);
  const bot = o.idle ? null : o.bot || (o.mode === "mouse" ? MOUSE : o.mode === "keys" ? KEYS : ARROWS)[method];
  let ended = false, frames = 0;
  while (!ended && frames < 60 * 700) {
    s.game.draw(stub, o.width || 360, 88);
    if (bot) bot(s, io);
    ended = s.step(DT);
    frames++;
  }
  return Object.assign(s.result(), { seconds: frames / 60, duration: s.game.duration, state: s.game.state() });
}

const out = { methods: BG.methods, enchant: BG.methodsFor("enchant"), herb: BG.methodsFor("herb"),
  forge: BG.methodsFor("forge"), games: {}, phases: BG.dayPhases };
for (const m of ENCHANT) {
  const def = W.BenchGameDefs[m];
  const g = out.games[m] = { keys: def.KEYS, sounds: def.SOUNDS || {}, hour: !!def.HOUR,
    arrows: play(m), arrows_steady: play(m, { steady: true }),
    mouse: play(m, { mode: "mouse" }), mouse_steady: play(m, { mode: "mouse", steady: true }),
    narrow: play(m, { mode: "mouse", width: 220 }),
    idle: play(m, { idle: true }), idle_steady: play(m, { idle: true, steady: true }) };
  if (KEYS[m]) { g.keys_run = play(m, { mode: "keys" }); g.keys_steady = play(m, { mode: "keys", steady: true }); }
  const s = sim(m, { steady: true }); let ups = 0;
  const up = s.game.up; s.game.up = function () { ups++; return up && up.apply(this, arguments); };
  for (const k of def.KEYS) { s.press(k); s.release(k); }
  s.pointer("down", 100, 40); s.pointer("up", 100, 40);
  g.steady_ups = ups;
}
// --- the timing games by the counted beat alone --------------------------------------------
out.rhythm = { bind: play("bind", { bot: rhythm() }), refine: play("refine", { bot: rhythm() }) };
// --- poor play: what a careless hand scores --------------------------------------------------
const late = (by) => (s, io) => { const st = s.game.state(); if (!st.struck && st.offset_s >= by) io.tap("Space"); };
const slowWrong = (delay) => {
  let seen = -1, since = 0, erred = false;
  return (s, io) => {
    const st = s.game.state(); if (st.phase !== "lay") return;
    if (st.step !== seen) { seen = st.step; since = s.t(); erred = false; }
    if (!erred) { const bad = st.pieces.findIndex((p) => p !== st.seq[st.step]); io.tap(String(bad + 1)); erred = true; return; }
    if (s.t() - since >= delay) io.tap(String(st.pieces.indexOf(st.seq[st.step]) + 1));
  };
};
out.poor = {
  bind_late_90ms: play("bind", { bot: late(0.09) }),
  bind_late_130ms: play("bind", { bot: late(0.13) }),
  bind_late_90ms_in_hour: play("bind", { bot: late(0.09), opts: { hour: NOON_IN } }),
  prepare_one_wrong_each: play("prepare", { bot: slowWrong(0) }),
  prepare_one_wrong_slow: play("prepare", { bot: slowWrong(2) }),
  refine_two_then_stop: play("refine", { bot: (s, io) => { const st = s.game.state();
    if (st.draw >= 2) { io.tap("S"); return; } if (st.open && st.offset_s >= 0) io.tap("Space"); } }),
  refine_greedy_cloudy: play("refine", { bot: (s, io) => { const st = s.game.state();
    if (st.draw >= 2) { if (st.offset_s < -0.3 && st.offset_s > -0.32) io.tap("Space"); return; }
    if (st.open && st.offset_s >= 0) io.tap("Space"); } }),
  cleanse_whole_first: play("cleanse", { bot: (() => { let done = false; return (s, io) => {
    const st = s.game.state(); if (!done) { const w = st.marks.find((x) => !x.curse); io.click(w.x, w.y); done = true; return; }
    KEYS.cleanse(s, io); }; })() }),
  cleanse_whole_first_steady: play("cleanse", { steady: true, bot: (() => { let done = false; return (s, io) => {
    const st = s.game.state(); if (!done) { const w = st.marks.find((x) => !x.curse); io.click(w.x, w.y); done = true; return; }
    KEYS.cleanse(s, io); }; })() }),
};
// --- the day phase -------------------------------------------------------------------------------
const win = (o) => sim("bind", o).game.state().window_s;
out.hour = {
  outside: win({ opts: { hour: NOON_OUT } }), inside: win({ opts: { hour: NOON_IN } }),
  none: win({ opts: { hour: null } }),
  eager_inside: win({ opts: { hour: NOON_IN }, tuning: { widen: 1.65 } }),
  server_says_one: win({ opts: { hour: NOON_IN }, tuning: { widen: 1 } }),
  steady_inside: win({ steady: true, opts: { hour: NOON_IN } }),
  steady_outside: win({ steady: true, opts: { hour: NOON_OUT } }),
  words_in: sim("bind", { opts: { hour: NOON_IN } }).hourWords(),
  words_out: sim("bind", { opts: { hour: NOON_OUT } }).hourWords(),
  words_eager: sim("bind", { opts: { hour: NOON_IN }, tuning: { widen: 1.65 } }).hourWords(),
  from_tuning: (() => { const s = BG.simulate({ method: "bind", tuning: { seed: 5, hour: NOON_IN } }); return s.hour && s.hour.phase; })(),
  state_shape: sim("bind", { opts: { hour: { phase: "dusk", left: 30, words: "Dusk, 30 minutes left" } } }).hour,
  bogus: sim("bind", { opts: { hour: { phase: "mars", inside: true, widen: 1.5 } } }).hour,
  prepare_ignores: sim("prepare", { opts: { hour: NOON_IN } }).hour,
  herb_and_forge_ignore: ["grind", "steep", "forge", "temper"].map((m) =>
    BG.simulate({ method: m, tuning: { seed: 5 }, hour: NOON_IN }).hour),
  ctx_hour_herb: BG.simulate({ method: "brew", tuning: { seed: 5 }, hour: NOON_IN }).ctx.hour,
};
// --- what the server sends wins --------------------------------------------------------------------
out.inputs = {
  seq_from_opts: sim("prepare", { opts: { seq: ["salt", "bell"] } }).game.state().seq,
  seq_from_tuning: BG.simulate({ method: "prepare", tuning: { seed: 5, seq: ["chalk", "focus", "bell"] } }).game.state().seq,
  unbind_from_tuning: BG.simulate({ method: "unbind", tuning: { seed: 5, seq: ["sigil", "enhancement"] } }).game.state().steps,
  seats_from_tuning: BG.simulate({ method: "attune", tuning: { seed: 5, seats: SEATS } }).game.state().phials.map((p) => p.name),
  seats_listed: BG.simulate({ method: "attune", tuning: { seed: 5 }, seats: [
    { seat: "stone", sign: "takes ward essences; suits what loves ruby", material: "ruby", essences: ["Ward essence", { name: "Lesser ward" }] },
    { seat: "band", sign: "takes ward essences" }] }).game.state(),
};
// Attune: a phial set on a seat whose sign it does not answer is refused, and the right one
// takes it; the point's phial is right on the edge too (one material, one sign).
{
  const s = sim("attune"); const io = input(s);
  s.game.draw(stub, 360, 88);
  let st = s.game.state();
  const fl = st.phials.findIndex((p) => p.name === "Flaming essence");
  const guard = st.seats.findIndex((x) => x.seat === "guard"), edge = st.seats.findIndex((x) => x.seat === "edge");
  io.click(st.phialAt[fl].x, st.phialAt[fl].y); io.click(st.seatAt[guard].x, st.seatAt[guard].y);
  const refused = s.game.state().phials[fl];
  io.click(st.phialAt[fl].x, st.phialAt[fl].y); io.click(st.seatAt[edge].x, st.seatAt[edge].y);
  out.attune_rule = { refused_at: refused.at, wrong: refused.wrong, then_at: s.game.state().phials[fl].at };
  // A drag: press on the other phial, let go over its seat.
  st = s.game.state(); s.game.draw(stub, 360, 88); st = s.game.state();
  const ke = st.phials.findIndex((p) => p.name === "Keen essence");
  s.pointer("down", st.phialAt[ke].x, st.phialAt[ke].y); s.pointer("up", st.seatAt[guard].x, st.seatAt[guard].y);
  out.attune_rule.dragged_to = s.game.state().phials[ke].at;
  s.press("Backspace");
  out.attune_rule.lifted = s.game.state().phials[ke].at;
}
out.phases = BG.dayPhases;
process.stdout.write(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def node_run(tmp_path_factory):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    script = tmp_path_factory.mktemp("enchant") / "driver.js"
    script.write_text(_DRIVER, encoding="utf-8")
    files = ([str(HERB_GAMES / f"{m}.js") for m in HERB_METHODS]
             + [str(FORGE_GAMES / f"{m}.js") for m in FORGE_METHODS]
             + [str(_game(m)) for m in METHODS] + [str(FRAME)])
    done = subprocess.run([node, str(script), json.dumps(files)], capture_output=True, text=True,
                          encoding="utf-8", timeout=300)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout)


def test_the_enchant_games_come_by_registration(node_run):
    """Contracts §13: the six register on the shared registry with `track: "enchant"`. Measured
    on the live API: herbs first in their fixed order, then the forge's, then the enchanter's,
    and `methodsFor` keeps each bench to its own games."""
    assert node_run["methods"] == HERB_METHODS + FORGE_METHODS + METHODS
    assert node_run["enchant"] == METHODS
    assert node_run["herb"] == HERB_METHODS and node_run["forge"] == FORGE_METHODS


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("mode", ["arrows", "arrows_steady", "mouse", "mouse_steady", "narrow"])
def test_a_perfect_run_scores_one(node_run, method, mode):
    """The server maps the score to the tier under the ceiling, so a perfect run that tops out
    at 0.9 caps every player a tier low. A bot reading only the game's state plays each game by
    the arrows (and Space or Enter), by mouse on a 360px and a 220px meter, and in Steady mode
    where no release is heard; each must score 1."""
    r = node_run["games"][method][mode]
    assert r["score"] >= 0.99, f"{method} {mode}: {r}"


@pytest.mark.parametrize("method", ORDER_GAMES)
@pytest.mark.parametrize("mode", ["keys_run", "keys_steady"])
def test_the_number_keys_win_the_order_games(node_run, method, mode):
    """UI plan §9: Prepare's "1-6 pick a piece"; Unbind and Cleanse take a sigil's number. The
    fastest keyboard path must score 1 as the arrows do."""
    assert node_run["games"][method][mode]["score"] >= 0.99, node_run["games"][method][mode]


@pytest.mark.parametrize("method", METHODS)
def test_a_perfect_run_is_short(node_run, method):
    """UI plan §9: "5-8 seconds (proposed)". A mandatory minigame that drags is the KCD2
    complaint (forge prior art §0 item 5). A clean run by the fastest bot ends inside 8s;
    Prepare's includes Simon's playback of the sequence before anything can be laid."""
    g = node_run["games"][method]
    assert g["arrows"]["seconds"] <= 8, g["arrows"]
    assert g["mouse"]["seconds"] <= 8, g["mouse"]


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("mode", ["idle", "idle_steady"])
def test_an_idle_run_scores_nothing(node_run, method, mode):
    """Pressing nothing must not earn a tier: an unattended order game loses each slot at
    Simon's three seconds, Attune's phials settle at 0, and a crest or a draw left alone is
    nothing. In Steady mode there is no clock, and the run ends only at the frame's limit."""
    r = node_run["games"][method][mode]
    assert r["score"] == 0, f"{method} {mode}: {r}"


@pytest.mark.parametrize("method", METHODS)
def test_steady_mode_never_hears_a_release(node_run, method):
    """The frame drops every key-up and pointer-up in Steady mode (STEADY-NO-RELEASE), and the
    headless path does the same: Attune's drag must have heard nothing."""
    assert node_run["games"][method]["steady_ups"] == 0


@pytest.mark.parametrize("method", ["bind", "refine"])
def test_reduced_motion_is_played_by_the_counted_beat(node_run, method):
    """Reduced motion stops the light and the bubble, which are the game. The windows must still
    be reachable: a player who sees only the count ("3", "2", "1", "Now", a mark lit on each
    beat, nothing travelling) and presses one beat after "1" lands inside the inner window every
    time (Rhythm Heaven is played by cue; its Night Mode on sound alone)."""
    r = node_run["rhythm"][method]
    assert r["score"] >= 0.99, r


def test_poor_play_scores_low_and_in_order(node_run):
    """What a careless hand earns, measured 2026-10-06: Bind pressed 90ms late every crest scores
    0.72; 130ms late (just inside the window's 146ms edge) 0.47; and the same 90ms inside the
    essence's phase 0.95, which is the whole point of waiting for the hour. Prepare with one
    wrong piece a slot keeps 0.66; dawdling two seconds a slot as well 0.52. These are the numbers the server's
    tier bands meet, so a change to the curves must move them on purpose."""
    p = node_run["poor"]
    assert 0.6 <= p["bind_late_90ms"]["score"] <= 0.75, p["bind_late_90ms"]
    assert 0.35 <= p["bind_late_130ms"]["score"] <= 0.5, p["bind_late_130ms"]
    assert p["bind_late_90ms_in_hour"]["score"] >= p["bind_late_90ms"]["score"] + 0.15
    assert 0.6 <= p["prepare_one_wrong_each"]["score"] <= 0.7, p["prepare_one_wrong_each"]
    assert 0.45 <= p["prepare_one_wrong_slow"]["score"] <= 0.58, p["prepare_one_wrong_slow"]


def test_refine_is_a_choice_to_stop(node_run):
    """Cennini's draws: two clean draws and a stop keep 0.56 (the first two draws' worth); a third
    draw taken off its crest comes up cloudy, gives back half its worth and spoils the source, so
    greed scores below the stop. Stopping is part of the game, not the frame's Esc."""
    p = node_run["poor"]
    stop, greedy = p["refine_two_then_stop"], p["refine_greedy_cloudy"]
    assert stop["score"] == pytest.approx(0.56, abs=0.005), stop
    assert stop["state"]["stopped"] and not stop["state"]["cloudy"]
    assert greedy["state"]["cloudy"] and greedy["score"] < stop["score"], greedy


def test_cleanse_steady_refuses_rather_than_scores(node_run):
    """UI plan §9, Cleanse's Steady column: "wrong sigils are refused, not scored". Picking a
    whole sigil first costs a normal run a third of the first curse sigil's credit and costs a
    Steady run nothing."""
    p = node_run["poor"]
    assert p["cleanse_whole_first"]["score"] == pytest.approx(1 - 0.34 / 3, abs=0.01)
    assert p["cleanse_whole_first_steady"]["score"] >= 0.99


def test_attune_refuses_a_seat_whose_sign_the_phial_does_not_answer(node_run):
    """The owner's "match essence to vessel": the flaming phial came off the point (cold iron
    head) and answers cold iron; the guard (brass fittings) refuses it, it goes back to the row
    with its credit lowered, and the edge (the same cold iron head) takes it. A drag sets a
    phial; Backspace lifts the last one set."""
    a = node_run["attune_rule"]
    assert a["refused_at"] is None and a["wrong"] == 1 and a["then_at"] == "edge"
    assert a["dragged_to"] == "guard" and a["lifted"] is None


def test_the_day_phase_widens_binds_windows_once(node_run):
    """Owner, round 4 points 9 and 10: Bind's windows x1.5 inside the essence family's phase.
    The server already folds the phase (and an eager essence's x1.1) into `tuning.widen`, so that
    wins and the hour is not counted again: 1.65 stays 1.65, not 2.475, and a server that says 1
    is believed. Without `tuning.widen` the game reads the hour itself. Steady's x1.6 stacks."""
    h = node_run["hour"]
    assert h["inside"] == pytest.approx(h["outside"] * 1.5, rel=1e-6)
    assert h["none"] == pytest.approx(h["outside"], rel=1e-6)
    assert h["eager_inside"] == pytest.approx(h["outside"] * 1.65, rel=1e-6)
    assert h["server_says_one"] == pytest.approx(h["outside"], rel=1e-6)
    assert h["steady_inside"] == pytest.approx(h["steady_outside"] * 1.5, rel=1e-6)
    assert h["steady_outside"] == pytest.approx(h["outside"] * 1.6, rel=1e-6)


def test_the_band_says_why_in_words(node_run):
    """UI plan §6.4: the band "tells the player why the windows are wide or narrow. Shape and
    words, not colour alone." The words are the server's own, then the effective widening."""
    h = node_run["hour"]
    assert h["words_in"] == "Noon, 42 minutes left. In its hour: windows ×1.5"
    assert h["words_out"] == "Noon in 10 hours. Not its hour: windows as usual"
    assert h["words_eager"].endswith("windows ×1.65")


def test_the_hour_is_read_only_where_it_belongs(node_run):
    """The band is Bind's alone and optional. The tuning's hour is read when the opts carry
    none; the state's shape (`{phase, left, words}`, the clock's phase, no essence) draws the
    band with no essence marked and widens nothing; a phase that is not one of sky's (a planet's
    name) is no band; and a herb, forge or other enchant game handed an hour ignores it."""
    h = node_run["hour"]
    assert h["from_tuning"] == "noon"
    assert h["state_shape"]["phase"] is None and h["state_shape"]["now"] == "dusk"
    assert h["state_shape"]["inside"] is False and h["state_shape"]["minutes_left"] == 30
    assert h["bogus"] is None
    assert h["prepare_ignores"] is None
    assert h["herb_and_forge_ignore"] == [None, None, None, None] and h["ctx_hour_herb"] is None


def test_what_the_server_sent_is_what_is_played(node_run):
    """Contracts §13: `opts.seq` and `opts.seats` are the server's, and rules/enchanter.py
    tuning_for puts the same lists on the tuning, so either door works and the opts win. A game
    that played its demonstration sequence instead would score the player on a circle they never
    laid. Attune also takes the contracts' first shape, a seat's `essences` list, and a seat that
    sent two takes two back."""
    i = node_run["inputs"]
    assert i["seq_from_opts"] == ["salt", "bell"]
    assert i["seq_from_tuning"] == ["chalk", "focus", "bell"]
    assert i["unbind_from_tuning"] == 2
    assert sorted(i["seats_from_tuning"]) == ["Flaming essence", "Keen essence"]
    listed = i["seats_listed"]
    assert sorted(p["name"] for p in listed["phials"]) == ["Lesser ward", "Ward essence"]
    assert listed["seats"][0]["answers"] == [0, 1] or sorted(listed["seats"][0]["answers"]) == [0, 1]


def test_the_frames_fallback_day_matches_the_driver(node_run):
    """The band's copy of the day, as the page has it at run time (the static check reads the
    source; this one the object the frame exports)."""
    from rules import sky

    assert node_run["phases"]["windows"] == sky.windows()
