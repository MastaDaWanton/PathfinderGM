"""The forge's minigames (blacksmithing lane U3): the ten games in
`play/static/js/forge-games/`, the heat parts of the shared strip frame in
`play/static/js/table/33-bench-games.js`, and `play/static/css/forge-games.css`.

Mirrors tests/test_bench_games.py: most checks read the files, and the behaviour group loads the
frame and the games into node and plays every game through `BenchGames.simulate`, the frame's
own headless path (the same per-frame step and R handling as the strip's loop). Bots read only
the state a game hands the stage, so a bot that wins proves the game can be won from what it
shows, by keyboard, by mouse, and in Steady mode with no release ever heard.

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
GAMES = ROOT / "play" / "static" / "js" / "forge-games"
CSS = ROOT / "play" / "static" / "css" / "forge-games.css"
THEME = ROOT / "play" / "static" / "css" / "theme-v2.css"
UI_PLAN = ROOT / "docs" / "blacksmithing-ui-plan.md"
CONTRACTS = ROOT / "docs" / "blacksmithing-contracts.md"
HERB_GAMES = ROOT / "play" / "static" / "js" / "bench-games"

METHODS = ["smelt", "alloy", "forge", "quench", "temper", "fold", "hone", "assemble", "finish",
           "strengthen"]
HEAT_GAMES = ["smelt", "forge", "quench", "fold", "strengthen"]
REHEAT_GAMES = ["forge", "quench", "fold", "strengthen"]
HERB_METHODS = ["grind", "mix", "brew", "dry", "reduce", "extract", "infuse", "steep", "neutralize"]
TIER_NAMES = ["Crude", "Sound", "Fine", "Superior", "Flawless"]


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


# --- every method, one game ----------------------------------------------------------------

def test_the_ten_games_are_the_contracts_methods():
    """Contracts §7 names the bench's methods (assay has no game, UI plan §9). A game list that
    drifted from it (a missing `strengthen`, a stray `assay`) would leave the bench rolling a
    success with no game to show, which `BenchGames.play` answers with a rejection."""
    m = re.search(r"Methods \(plan §7\): `([^`]*)`", _read(CONTRACTS))
    assert m, "contracts §7 no longer lists the methods where this test reads them"
    contract = [x.strip() for x in m.group(1).split(",")]
    assert [x for x in contract if x != "assay"] == METHODS
    assert sorted(p.stem for p in GAMES.glob("*.js")) == sorted(METHODS)


@pytest.mark.parametrize("method", METHODS)
def test_every_forge_game_registers_like_a_herb_game(method):
    """Contracts §11: a forge game registers on `window.BenchGameDefs[method]` exactly as the
    herb games do, so the one frame runs both. A file that assigned `window.ForgeGames.x`
    instead would load without error and never be found."""
    code = _code(_read(_game(method)))
    assert re.search(r"defs\." + method + r"\s*=\s*\{", code), f"{method}.js does not register defs.{method}"
    assert f'id: "{method}"' in code
    assert 'track: "forge"' in code, f"{method}.js does not say it is a forge game"
    assert re.search(r"create\s*:\s*function\s*\(ctx\)", code)
    first = re.search(r'first:\s*"([^"]+)"', code)
    # The first-time card is up for two seconds (the frame's timer); a card that takes longer
    # than that to read starts the game under the player's eyes.
    assert first and len(first.group(1)) <= 100, f"{method}.js: first-time card {first and first.group(1)!r}"


def test_the_herb_list_is_unchanged_and_forge_methods_come_by_registration():
    """The herb bench's METHODS is fixed vocabulary its own test reads literally; making it
    extensible must not edit it. Forge methods arrive by registration, after the herbs, and
    `methodsFor` separates the two benches so neither shows the other's games."""
    m = re.search(r"var METHODS = \[([^\]]*)\]", _code(_read(FRAME)))
    assert re.findall(r'"([a-z]+)"', m.group(1)) == HERB_METHODS
    assert "function allMethods()" in _code(_read(FRAME))


# --- holds, keys, loops -----------------------------------------------------------------------

@pytest.mark.parametrize("method", METHODS)
def test_steady_mode_declares_no_hold(method):
    """Potion Craft added Auto Hold after players reported hand fatigue (herbalism prior art,
    devlog #14), and the frame drops every release in Steady mode. Each game declares its holds;
    Steady's list must be empty, and every hold must be a key it listens for or the pointer."""
    js = _read(_game(method))
    assert _list(js, "HOLDS_STEADY") == []
    keys = _list(js, "KEYS") or []
    assert keys, f"{method}.js listens for no key: not playable by keyboard"
    for h in _list(js, "HOLDS") or []:
        assert h == "pointer" or h in keys, f"{method}.js holds {h!r}, not one of its KEYS {keys}"
    # Steady mode reaches a game through ctx (its windows and speeds) or through its HEAT, whose
    # cooling the frame halves and whose band it widens by `steadyBand` (Fold's and
    # Strengthen's Steady columns name only those).
    assert re.search(r"ctx\.(steady|band|speed|win)\b", _code(js)) or "HEAT:" in _code(js), (
        f"{method}.js ignores Steady mode")


@pytest.mark.parametrize("method", METHODS)
def test_reheat_is_r_exactly_where_there_is_heat_to_reheat(method):
    """UI plan §7.2: "Reheat (R, or click the hearth)". The frame takes R for a game whose heat
    can be reheated; a heat game that left R out of its KEYS would have R pass straight to the
    table (where it is not swallowed) and the metal would not come back. Smelt's heat is the
    furnace's: it comes back by pumping, so it has no R and says "Pump" instead."""
    js = _read(_game(method))
    keys = _list(js, "KEYS")
    if method in REHEAT_GAMES:
        assert "R" in keys
    else:
        assert "R" not in keys
    assert ("HEAT:" in _code(js)) == (method in HEAT_GAMES)


@pytest.mark.parametrize("method", METHODS)
def test_no_game_runs_its_own_loop_listens_or_plays_sound(method):
    """One loop, only while a game runs (UI plan §7.4, the frame's rule): the herb harness
    measured 0 frames in the 2s after a game ended. A game scheduling its own frames, timers or
    listeners would outlive the strip; one calling Sound itself would skip the frame's optional
    guard and play on a page with no Sound module."""
    code = _code(_read(_game(method)))
    for banned in ("requestAnimationFrame", "setInterval", "setTimeout", "addEventListener",
                   "Sound", ".animate(", "import ", "require(", "fetch(", "XMLHttpRequest"):
        assert banned not in code, f"{method}.js uses {banned}"


@pytest.mark.parametrize("method", METHODS)
def test_every_game_draws_shapes_and_its_own_aim(method):
    """Never colour alone (heat colour especially: "colour alone also fails accessibility",
    prior art §5.4), and no game depends on the cursor art (UI plan §9; the candle cursor's
    hotspot drifted in 0.2.2). Every game draws its zones through the kit's hatched bands,
    notches, rings or pips, and draws its own reticle where the pointer really is."""
    code = _code(_read(_game(method)))
    assert re.search(r"k\.(dialBand|barBand|ring|notch|pip)\(", code)
    assert "k.reticle(" in code and "ctx.pointer" in code, f"{method}.js draws no aim of its own"


@pytest.mark.parametrize("method", METHODS)
def test_forge_sounds_are_the_ui_plans_names(method):
    """UI plan §11 lists the forge bus's events and contracts §11 makes unknown names silent, so
    a game naming `forge.finish` (no such event) would play nothing and nobody would hear why.
    Every SOUNDS value must be one of §11's names."""
    plan = _read(UI_PLAN)
    sec = plan[plan.index("## 11. Sound"):plan.index("## 12.")]
    known = set(re.findall(r"`(forge\.[a-z.]+)`", sec))
    m = re.search(r"SOUNDS:\s*\{([^}]*)\}", _code(_read(_game(method))))
    assert m, f"{method}.js names no forge sounds; the frame would play bench.* for it"
    names = re.findall(r'"([^"]+)"', m.group(1))
    assert names and all(n in known for n in names), f"{method}.js: {names} not all in {sorted(known)}"


# --- copy, tokens, tiers -----------------------------------------------------------------------

def _lane_files() -> list[Path]:
    return [CSS] + [_game(m) for m in METHODS]


def test_the_page_never_names_a_tier():
    """The server turns the score into a tier (forge_views finish); the page never names one."""
    for p in [FRAME] + [_game(m) for m in METHODS]:
        for s in _strings(_read(p)):
            for name in TIER_NAMES:
                assert not re.search(rf"\b{name}\b", s), f"{p.name} names the tier {name!r} in {s!r}"


def test_no_em_or_en_dashes_in_the_lanes_files():
    """UI plan §8: no em-dashes in new strings; checked over whole files, comments included."""
    for p in _lane_files() + [FRAME]:
        text = _read(p)
        for ch in ("—", "–"):
            assert ch not in text, f"{p.relative_to(ROOT)} has a dash on line {text[:text.index(ch)].count(chr(10)) + 1}"


def test_no_control_bytes_in_the_lanes_files():
    """Bash heredocs have written `\\b` into source as a literal backspace byte (CLAUDE.md,
    everyday traps), silently breaking a regex while tests passed; the frame's °C formatter is
    a regex with `\\B` and `\\d`."""
    for p in _lane_files() + [FRAME]:
        bad = [c for c in _read(p) if ord(c) < 32 and c not in "\n\r\t"]
        assert not bad, f"{p.name} has control bytes {bad!r}"


def test_the_stylesheet_uses_theme_tokens_only():
    """Keep the colours (owner, 2026-09-28; UI plan §4: "No new colours"). Heat colour is
    content and is drawn on the gauge's canvas; a raw colour in this stylesheet would be a
    second palette on the chrome."""
    css = re.sub(r"/\*.*?\*/", "", _read(CSS), flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
    assert not re.search(r"\b(rgb|rgba|hsl|hsla)\(", css)
    theme = _read(THEME)
    for tok in set(re.findall(r"var\((--[a-z0-9-]+)\)", css)):
        assert f"{tok}:" in theme, f"forge-games.css uses {tok}, which theme-v2.css does not define"


def test_heat_colour_lives_on_the_gauge_only():
    """UI plan §4: "Heat colour is content, not chrome": the blackbody colours appear only on the
    gauge's scale (and Temper's oxide track, the steel's own colour). In the frame they sit in
    HEAT_STOPS, used by drawGauge's gradient and nowhere else."""
    code = _code(_read(FRAME))
    assert code.count("HEAT_STOPS") == 2, "HEAT_STOPS is used outside the gauge"
    gauge = code[code.index("function drawGauge"):code.index("function build(")]
    assert "HEAT_STOPS.forEach" in gauge and "createLinearGradient" in gauge


# --- the frame's heat --------------------------------------------------------------------------

def test_the_gauge_has_its_named_bands_needle_outline_and_number():
    """UI plan §6.4: named bands (dark red, cherry, orange, yellow, white) under a horizontal
    bar, a needle, the target band outlined (shape, not only colour), the number in °C. A gauge
    without its names or its number would leave colour alone to carry the heat, which KCD2's
    patch 1.2 had to fix ("Improved visual indication of workpiece cooling", prior art §0)."""
    code = _code(_read(FRAME))
    names = re.search(r"var HEAT_NAMES = \[(.*?)\];", code, re.S).group(1)
    assert re.findall(r'name: "([^"]+)"', names) == ["Dark red", "Cherry", "Orange", "Yellow", "White"]
    gauge = code[code.index("function drawGauge"):code.index("function build(")]
    assert "strokeRect(ax" in gauge and "KIT.notch(g, ax" in gauge and "KIT.notch(g, zx" in gauge
    assert "cross: true" in gauge, "the burning zone is not cross-hatched"
    assert "fillText(o.b.name" in gauge
    assert 'el("p", "bench-game__heat-num")' in code
    assert "showHeat(r)" in code


def test_r_is_the_frames_and_comes_before_the_game():
    """One reheat path for every heat game, counted once: the keyboard's R and the Reheat
    button both go through `reheatKey`, and the keydown handler offers R to it before the game
    hears the key. Letters are capitals so Shift or Caps Lock does not lose the reheat."""
    code = _code(_read(FRAME))
    down = code[code.index("function onKeyDown"):code.index("function onKeyUp")]
    assert down.index("reheatKey(r, key)") < down.index("r.game.down(")
    assert 'reheatKey(r, "R")' in code
    assert "e.key.toUpperCase()" in code


def test_the_result_carries_the_reheats_the_server_charges_for():
    """forge_views.forge_finish reads `reheats` and charges reheat_minutes for each (revamp plan
    §11, "a reheat costs ... 5 minutes of world time"). A frame that kept the count to itself
    would make every reheat free."""
    code = _code(_read(FRAME))
    assert "reheats: r.heat ? r.heat.reheats : 0" in code
    views = _read(ROOT / "play" / "forge_views.py")
    assert 'read_int(body, "reheats"' in views


def test_the_forge_stage_is_never_dropped_for_a_missing_method():
    """ForgeStage (contracts §11) has `heat(celsius)` and not necessarily the herb stage's
    `update`, `hit` or `miss`. The frame called them unguarded inside a try whose catch sets
    the stage to null, so the first frame of a forge game would have silently dropped the 3D
    stage for the rest of the run."""
    code = _code(_read(FRAME))
    assert 'typeof r.stage.update === "function"' in code
    assert 'r.stage && typeof r.stage.hit === "function"' in code
    assert 'r.stage && typeof r.stage.miss === "function"' in code
    assert 'typeof r.stage.heat === "function") r.stage.heat(r.heat.c)' in code


def test_the_simulate_path_is_the_loops_path():
    """The behaviour tests below drive `simulate`; they mean something only if it steps the game
    the way the loop does. Both call `advance`, which cools the metal before the game ticks."""
    code = _code(_read(FRAME))
    loop = code[code.index("function loop("):code.index("function advance(")]
    assert "advance(r, dt);" in loop and "r.game.tick(" not in loop
    sim = code[code.index("function simulate("):code.index("window.BenchGames = {")]
    assert "advance(r, dt)" in sim and "reheatKey(r, key)" in sim


# --- behaviour, in node --------------------------------------------------------------------------

_DRIVER = r"""// Node driver for tests/test_forge_games.py: loads the frame and the ten forge games into a
// bare sandbox and plays each one through `BenchGames.simulate`, the frame's own headless
// path (the same `advance` step and R handling as the strip's loop). It prints one JSON
// object; the Python tests read it. Bots read only the state a game hands the stage, so a
// bot that scores 1 proves the game can be won from what it shows.
"use strict";
const fs = require("fs"), vm = require("vm");
const files = JSON.parse(process.argv[2]);
const sandbox = { window: {}, Math, JSON, Object, Array, Promise, console, performance: { now: () => 0 } };
sandbox.window.window = sandbox.window;
vm.createContext(sandbox);
for (const f of files) vm.runInContext(fs.readFileSync(f, "utf8"), sandbox);
const W = sandbox.window, BG = W.BenchGames;
const DT = 1 / 60;
const FORGE = ["smelt", "alloy", "forge", "quench", "temper", "fold", "hone", "assemble", "finish", "strengthen"];

function sim(method, o) {
  o = o || {};
  return BG.simulate(Object.assign({ method, tuning: Object.assign({ seed: 5, difficulty: 0.5 }, o.tuning || {}) }, o));
}
function mid(b) { return (b[0] + b[1]) / 2; }

// --- input: the bot names keys; in mouse mode Space becomes the mouse button --------------
function input(s, mouse) {
  const held = {};
  return {
    press(key) {
      if (mouse && key === "Space") { s.pointer("down", 100, 40); held[key] = true; return; }
      if (mouse && key === "T") { s.button(); return; }
      s.press(key); held[key] = true;
    },
    release(key) {
      if (!held[key]) return;
      delete held[key];
      if (mouse && key === "Space") { s.pointer("up", 100, 40); return; }
      s.release(key);
    },
    tap(key) { this.press(key); if (!s.ctx.steady) this.release(key); }
  };
}

// --- bots: one per game, reading only state() (and the heat the frame owns) ---------------
function heatBot(inner) {
  // Strike when the heat is in the band's inner share, reheat when it falls below it.
  return (s, io) => {
    const h = s.heat, st = s.game.state();
    if (h.reheating > 0 || st.folding) return;
    const hw = (h.band[1] - h.band[0]) / 2, m = mid(h.band), lo = m - hw * inner + 2, hi = m + hw * inner - 2;
    if (h.c >= lo && h.c <= hi && (h.burn == null || h.c < h.burn)) io.tap("Space");
    else if (h.c < lo) io.tap("R");
  };
}
function ringBot(useHeat) {
  return (s, io) => {
    const st = s.game.state();
    if (useHeat) {
      const h = s.heat;
      if (h.reheating > 0) return;
      if (h.c < h.band[0] + 25) { io.tap("R"); return; }
    }
    if (st.ring >= 1 && !st.struck) io.tap("Space");
  };
}
const BOTS = {
  forge: ringBot(true),
  assemble: ringBot(false),
  fold: heatBot(0.6),
  strengthen: heatBot(0.5),
  smelt: (s, io) => {
    const st = s.game.state(), h = s.heat, m = mid(h.band);
    if (st.ready) io.tap("T");
    if (s.ctx.steady) {
      if (!st.pumping && h.c < m - 15) io.press("Space");
      else if (st.pumping && h.c > m + 15) io.press("Space");
    } else if (h.c < m - 10) io.tap("Space");
  },
  quench: (s, io) => {
    const st = s.game.state();
    if (st.phase === "air" && s.heat.reheating <= 0) {
      if (s.heat.c <= mid(s.heat.band)) io.press("Space");
    } else if (st.phase === "under" && st.under >= mid(st.hold)) {
      if (s.ctx.steady) io.press("Space"); else io.release("Space");
    }
  },
  temper: (s, io) => {
    const st = s.game.state();
    if (!st.waiting && st.temp_c >= mid(st.band)) io.tap("Space");
  },
  alloy: (s, io) => {
    const st = s.game.state();
    if (st.waiting) return;
    if (!st.pouring && st.share === 0) io.press("Space");
    else if (st.pouring && st.share >= st.target) { if (s.ctx.steady) io.press("Space"); else io.release("Space"); }
  },
  hone: (s, io) => {
    const st = s.game.state(), aim = mid(st.band), d = st.angle - aim;
    if (s.ctx.steady) {
      if (d < -0.75) io.press("ArrowRight"); else if (d > 0.75) io.press("ArrowLeft");
    } else {
      if (d < -0.3) { io.release("ArrowLeft"); io.press("ArrowRight"); }
      else if (d > 0.3) { io.release("ArrowRight"); io.press("ArrowLeft"); }
      else { io.release("ArrowLeft"); io.release("ArrowRight"); }
    }
    if (!st.passing) io.tap("Space");
  },
  finish: (s, io) => {
    const st = s.game.state();
    if (st.strip < st.rows && Math.abs(st.load - 1) < 0.03) io.tap("ArrowRight");
  },
};

// Mouse bots for the two drag games: hone draws the line along the stone, finish sweeps
// each strip once at the brush's even pace.
const MOUSE = {
  hone: () => {
    let x = 0, going = false;
    return (s) => {
      const st = s.game.state(), aim = mid(st.band);
      // The pointer's height for an angle, inverting hone's fromY on its undrawn geometry
      // (geo.y 40, geo.H 88): angle = aim + (40 - y) / 44 * 14.
      const yFor = (deg) => 40 - (deg - aim) / 14 * 44;
      if (!going && !st.passing && st.pass <= st.passes) {
        x = 32; s.pointer("down", x, yFor(aim)); going = true; return;
      }
      if (going) {
        x += 4;
        // Steer against the drift the game reports: aim the pointer so angle returns to aim.
        const err = st.angle - aim;
        s._y = (s._y == null ? yFor(aim) : s._y) + err * 44 / 14 * 0.5;
        s.pointer("move", x, s._y);
        if (!s.game.state().passing) { s.pointer("up", x, s._y); going = false; s._y = null; }
      }
    };
  },
  finish: () => {
    let row = 0, x = null, phase = 0;
    return (s) => {
      if (row >= 4) return;
      const y = 12 + (row + 0.5) * 14;
      if (x === null) { x = 10; s.pointer("down", x, y); s.pointer("move", x, y); return; }
      x += 260 / 60;                       // PACE px/s, one frame's travel
      s.pointer("move", x, y);
      if (x > 16 + 12 * 20 + 6) { s.pointer("up", x, y); x = null; row++; }
    };
  },
};

function play(method, opts) {
  opts = opts || {};
  const s = sim(method, { steady: !!opts.steady, heat: opts.heat, tuning: opts.tuning });
  const io = input(s, !!opts.mouse);
  const bot = opts.idle ? null : opts.mouse && MOUSE[method] ? MOUSE[method]() : BOTS[method];
  let ended = false, frames = 0;
  while (!ended && frames < 60 * 60) {
    if (bot) bot(s, io);
    ended = s.step(DT);
    frames++;
  }
  return Object.assign(s.result(), { seconds: frames / 60, duration: s.game.duration });
}

const out = { methods: BG.methods, forge: BG.methodsFor("forge"), herb: BG.methodsFor("herb"), games: {} };
for (const m of FORGE) {
  const def = W.BenchGameDefs[m];
  const g = out.games[m] = {
    keys: def.KEYS, holds: def.HOLDS, holds_steady: def.HOLDS_STEADY, heat: !!def.HEAT,
    reheat: !!def.HEAT && def.HEAT.reheat !== false, sounds: def.SOUNDS || {},
    perfect: play(m), perfect_steady: play(m, { steady: true }),
    mouse: play(m, { mouse: true }), mouse_steady: play(m, { mouse: true, steady: true }),
    idle: play(m, { idle: true }), idle_steady: play(m, { idle: true, steady: true }),
  };
  // Steady mode never hears a release: count the game's own up() while a Steady bot plays
  // and its releases are handed to the sim, which must drop them as the frame does.
  {
    const s = sim(m, { steady: true }); let ups = 0;
    const up = s.game.up; s.game.up = function () { ups++; return up && up.apply(this, arguments); };
    for (const k of def.KEYS) { s.press(k); s.release(k); }
    s.pointer("down", 100, 40); s.pointer("up", 100, 40);
    g.steady_ups = ups;
  }
  // The heat's words: idle until the metal is too cold, and read the hint.
  if (def.HEAT) {
    const s = sim(m), seen = {};
    for (let i = 0; i < 60 * 40; i++) {
      s.step(DT);
      const st = s.heat.status();
      if (!(st in seen)) seen[st] = s.hint();
    }
    g.hints = seen;
    g.heat_band = s.heat.band; g.heat_scale = s.heat.scale; g.burn = s.heat.burn;
    // The frame's R: a reheat counted once, a second R while it reheats ignored.
    const r = sim(m);
    r.press("R"); r.step(DT); r.press("R");
    for (let i = 0; i < 120; i++) r.step(DT);
    r.press("R");
    g.reheats = r.result().reheats;
    g.after_reheat_c = r.heat.c;
    g.hearth = r.heat.hearth;
    // Band widths: generous default, narrow metal, narrow counted once, server band wins.
    const width = (o) => { const x = sim(m, o).heat.band; return x[1] - x[0]; };
    g.width = {
      plain: width({}), narrow: width({ heat: { narrow: true } }),
      both: width({ heat: { narrow: true }, tuning: { traits: ["narrow_window"], band_scale: 0.8 } }),
      scaled: width({ tuning: { traits: ["narrow_window"], band_scale: 0.8 } }),
      steady: width({ steady: true }), easy: width({ tuning: { difficulty: 0 } }),
      hard: width({ tuning: { difficulty: 1 } }),
    };
    const sv = sim(m, { heat: { band: [900, 1000], start_c: 990, hearth_c: 1010, cool_rate: 10 } });
    g.server = { band: sv.heat.band, c: sv.heat.c, hearth: sv.heat.hearth, cool: sv.heat.cool };
    const nc = sim(m, { heat: { narrow: true } }).heat.cool, pc = sim(m).heat.cool, sc = sim(m, { steady: true }).heat.cool;
    g.cool = { plain: pc, narrow: nc, steady: sc };
  }
}
out.gauge = BG.gauge.names;
out.degrees = [BG.gauge.degrees(1043), BG.gauge.degrees(815)];
process.stdout.write(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def node_run(tmp_path_factory):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    script = tmp_path_factory.mktemp("forge") / "driver.js"
    script.write_text(_DRIVER, encoding="utf-8")
    files = [str(_game(m)) for m in METHODS] + [str(FRAME)]
    done = subprocess.run([node, str(script), json.dumps(files)], capture_output=True, text=True,
                          encoding="utf-8", timeout=120)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout)


def test_the_method_list_is_extended_by_registration(node_run):
    """Contracts §10: "make METHODS extensible by registration (herb games unchanged)". Measured
    on the live API: herbs first in their fixed order, then the ten forge games."""
    assert node_run["methods"] == HERB_METHODS + METHODS
    assert node_run["herb"] == HERB_METHODS
    assert node_run["forge"] == METHODS


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("mode", ["perfect", "perfect_steady", "mouse", "mouse_steady"])
def test_a_perfect_run_scores_one(node_run, method, mode):
    """A game that cannot be won is a broken game, and the server maps the score to the tier
    under the ceiling, so a perfect run that tops out at 0.9 would cap every player a tier low.
    A bot reading only the game's state plays each game by keyboard, by mouse, and in Steady
    mode (where it never releases anything), and must score 1."""
    r = node_run["games"][method][mode]
    assert r["score"] >= 0.99, f"{method} {mode}: {r}"


@pytest.mark.parametrize("method", METHODS)
def test_a_perfect_run_is_short(node_run, method):
    """About six seconds a game (revamp plan §11, as herbalism's §9.3): a game whose clean run
    took twenty seconds would be the KCD2 complaint (a mandatory minigame for routine output,
    prior art §0 item 5). Steady mode may take longer, as its speeds are halved."""
    g = node_run["games"][method]
    assert g["perfect"]["seconds"] <= 10.5, g["perfect"]
    assert g["perfect_steady"]["seconds"] <= 13, g["perfect_steady"]


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("mode", ["idle", "idle_steady"])
def test_an_idle_run_scores_low(node_run, method, mode):
    """Pressing nothing must not earn a tier. Measured 2026-10-04: nine games score 0 idle;
    Smelt credits the furnace for the seconds it stays in band on its own, 0.14 idle and 0.28
    in Steady mode (its drift is halved there), which was 0.47 before the furnace was started
    low in its band."""
    r = node_run["games"][method][mode]
    assert r["score"] <= 0.3, f"{method} {mode}: {r}"
    if method != "smelt":
        assert r["score"] == 0, f"{method} {mode}: {r}"


@pytest.mark.parametrize("method", METHODS)
def test_steady_mode_never_hears_a_release(node_run, method):
    """The frame drops every key-up and pointer-up in Steady mode (STEADY-NO-RELEASE), and the
    headless path does the same. Every key the game takes was pressed and released, and the
    pointer pressed and lifted, in Steady mode: the game's own up() must have heard nothing."""
    assert node_run["games"][method]["steady_ups"] == 0


@pytest.mark.parametrize("method", REHEAT_GAMES)
def test_heat_out_of_band_says_reheat(node_run, method):
    """UI plan §6.4: "When the metal leaves the band the hint changes to 'Reheat: R' in words."
    Left alone, every reheatable game's metal cools below its band, and the hint must say it,
    the same words in every game, since the frame owns them."""
    hints = node_run["games"][method]["hints"]
    assert hints.get("cold") == "Reheat: R", hints
    assert hints.get("in") and "Reheat" not in hints["in"]
    if "hot" in hints:
        assert hints["hot"] == "Too hot: let it cool"


def test_the_furnace_says_pump_not_reheat(node_run):
    """Smelt's gauge is the furnace's heat; R would do nothing there. Its cold words name the
    action that brings the heat back."""
    assert node_run["games"]["smelt"]["hints"].get("cold") == "Too cold. Pump: Space"
    assert node_run["games"]["smelt"]["reheat"] is False


@pytest.mark.parametrize("method", REHEAT_GAMES)
def test_a_reheat_is_counted_once_and_reaches_the_hearth(node_run, method):
    """R twice in a row is one reheat (the second lands while the first is in the fire), and a
    later R is another: two in all, the number the server charges world minutes for. After two
    seconds the metal is within 5% of the hearth's heat."""
    g = node_run["games"][method]
    assert g["reheats"] == 2, g["reheats"]
    assert abs(g["after_reheat_c"] - g["hearth"]) <= 0.05 * g["hearth"], g


@pytest.mark.parametrize("method", HEAT_GAMES)
def test_better_metal_narrows_the_window_once(node_run, method):
    """Contracts §11: `opts.heat.narrow` narrows the window (Giants' Foundry, prior art §5.4) to
    the narrow_window trait's 0.8. The server's band_scale already counts that trait, so a
    narrow metal sent with both must be narrowed once (0.8), not twice (0.64)."""
    w = node_run["games"][method]["width"]
    assert w["narrow"] == pytest.approx(w["plain"] * 0.8, rel=1e-6)
    assert w["both"] == pytest.approx(w["narrow"], rel=1e-6)
    assert w["scaled"] == pytest.approx(w["narrow"], rel=1e-6)


@pytest.mark.parametrize("method", HEAT_GAMES)
def test_the_window_starts_generous(node_run, method):
    """Every shipped smithing minigame was softened afterwards (prior art §0 item 5), so the
    band starts wider than the metallurgy: x1.1 at the server's middle difficulty, x1.35 at the
    easiest, and the hardest only takes it to x0.85."""
    w = node_run["games"][method]["width"]
    assert w["easy"] > w["plain"] > w["hard"]
    assert w["easy"] / w["hard"] == pytest.approx(1.35 / 0.85, rel=1e-3)


@pytest.mark.parametrize("method", ["quench", "strengthen"])
def test_steady_widens_the_bands_its_column_names(node_run, method):
    """UI plan §9's Steady column: Quench "bands x1.5", Strengthen "band x1.5"."""
    w = node_run["games"][method]["width"]
    assert w["steady"] == pytest.approx(w["plain"] * 1.5, rel=1e-6)


@pytest.mark.parametrize("method", HEAT_GAMES)
def test_cooling_halves_in_steady_and_quickens_for_narrow_metal(node_run, method):
    """UI plan §7.2: "Under Steady mode cooling runs at half speed", and cooling is "faster ...
    for narrow_window metals"."""
    c = node_run["games"][method]["cool"]
    assert c["steady"] == pytest.approx(c["plain"] / 2)
    assert c["narrow"] == pytest.approx(c["plain"] * 1.25)


@pytest.mark.parametrize("method", HEAT_GAMES)
def test_the_servers_heat_wins(node_run, method):
    """Contracts §11: games receive `opts.heat` from the server's check response. A game that
    kept its own default band when the server sent one would score against the wrong metal."""
    s = node_run["games"][method]["server"]
    assert sum(s["band"]) / 2 == pytest.approx(950)
    assert s["c"] == 990 and s["hearth"] == 1010


def test_strengthen_never_widens_into_burning(node_run):
    """The burning zone starts at 1,315 °C (Chapman's white, prior art §3.1). Widening the band
    for a generous start or Steady mode must grow it downward, never into the white, or a
    "strike in band" could burn the bar."""
    g = node_run["games"]["strengthen"]
    assert g["burn"] == 1315 and g["heat_band"][1] <= 1310


def test_the_degrees_read_as_a_number(node_run):
    """The number beside the gauge is rounded to 5 °C with a thousands comma, so it reads rather
    than flickering a new digit every frame: 1043 shows as "1,045 °C"."""
    assert node_run["degrees"] == ["1,045 °C", "815 °C"]
    assert node_run["gauge"] == ["Dark red", "Cherry", "Orange", "Yellow", "White"]
