"""The leatherworker's minigames (leather lane U3): the eleven games and the cut test in
`play/static/js/leather-games/`, the band gauge they add to the shared strip frame
`play/static/js/table/33-bench-games.js` (BAND), and `play/static/css/leather-games.css`.

Mirrors tests/test_alchemy_games.py: most checks read the files, and the behaviour group loads
the frame and every game (herb, forge, enchant, alchemy and leather, so the registry is the real
one) into node and plays each leather game through `BenchGames.simulate`, the frame's own
headless path (the same per-frame `advance` as the strip's loop), with the server's real band and
tuning from rules/leatherworker.py `tuning_for`. Every frame the driver also calls the game's
`draw` on a stub canvas, so a draw that throws fails here rather than in the owner's strip. Bots
read only the state a game hands the stage, so a bot that wins proves the game can be won from
what it shows: by keyboard, by mouse on a 360px and a 220px meter, and in Steady mode (where no
release is ever heard). Three kinds of player who will not play (holding every key, mashing every
key, pressing nothing) are measured too: the owner's 2026-10-06 note on the herb games was that
cheating must not score well.

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
GAMES = ROOT / "play" / "static" / "js" / "leather-games"
KIT = GAMES / "00-kit.js"
CSS = ROOT / "play" / "static" / "css" / "leather-games.css"
THEME = ROOT / "play" / "static" / "css" / "theme-v2.css"
UI_PLAN = ROOT / "docs" / "leatherworking-ui-plan.md"
CONTENT = ROOT / "content" / "world-classes" / "leatherworker.json"
HERB_GAMES = ROOT / "play" / "static" / "js" / "bench-games"
FORGE_GAMES = ROOT / "play" / "static" / "js" / "forge-games"
ENCHANT_GAMES = ROOT / "play" / "static" / "js" / "enchant-games"
ALCHEMY_GAMES = ROOT / "play" / "static" / "js" / "alchemy-games"

METHODS = ["flense", "salt", "tan", "curry", "cut", "stitch", "harden", "tool", "dye", "laminate",
           "assemble"]
GAMES_ALL = METHODS + ["cut-test"]
HERB_METHODS = ["grind", "mix", "brew", "dry", "reduce", "extract", "infuse", "steep", "neutralize"]
FORGE_METHODS = ["smelt", "alloy", "forge", "quench", "temper", "fold", "hone", "assemble", "finish",
                 "strengthen"]
ENCHANT_METHODS = ["prepare", "attune", "bind", "refine", "unbind", "cleanse"]
ALCHEMY_METHODS = ["dissolve", "calcine", "filter", "distill", "react", "sublime", "bottle", "transmute"]
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


def _game(name: str) -> Path:
    return GAMES / f"{name}.js"


def _list(js: str, name: str) -> list[str] | None:
    m = re.search(name + r"\s*:\s*\[([^\]]*)\]", _code(js))
    return None if not m else re.findall(r'"([^"]*)"', m.group(1))


def _rows() -> dict:
    return json.loads(_read(CONTENT))["bench"]["methods"]


# --- every method with a game, one file --------------------------------------------------------

def test_every_method_lane_e_tunes_has_a_game_and_grade_has_none():
    """Lane E's twelve methods (content/world-classes/leatherworker.json) each carry a band for
    their game, except Grade (UI plan §9: "Grade has no minigame (the forge's Assay and herb
    tasting have none)"). A method with a band and no game would roll a success the shell then
    cannot play (`BenchGames.play` rejects an unknown method); a game for Grade would be a game
    the server never scores."""
    rows = _rows()
    banded = sorted(m for m, r in rows.items() if (r.get("tuning") or {}).get("band"))
    assert banded == sorted(METHODS)
    assert "grade" in rows and not (rows["grade"].get("tuning") or {}).get("band")
    files = sorted(p.stem for p in GAMES.glob("*.js") if p.stem != "00-kit")
    assert files == sorted(GAMES_ALL)


@pytest.mark.parametrize("name", GAMES_ALL)
def test_every_leather_game_registers_under_its_prefixed_key(name):
    """Contracts §11.1: each leather game registers on `window.BenchGameDefs` as the herb, forge
    and alchemy games do, with `track: "leather"`. Under the bare method name `assemble` would
    have replaced the smith's Assemble on the one shared registry (js/forge-games/assemble.js
    registers `defs.assemble`), and the forge would have played lacing; so every leather game
    is keyed "leather.<method>", one rule for all, which `LeatherGames.key` gives the shell."""
    code = _code(_read(_game(name)))
    key = f"leather.{name}"
    assert f'defs["{key}"] = {{' in code, f"{name}.js does not register {key}"
    assert f'id: "{key}"' in code
    assert 'track: "leather"' in code
    assert "defs.assemble" not in code
    first = re.search(r'first:\s*"([^"]+)"', code)
    assert first and len(first.group(1)) <= 110, f"{name}.js: first-time card {first and first.group(1)!r}"
    kit = _code(_read(KIT))
    assert 'key: function (method) { return "leather." + String(method || ""); }' in kit
    assert 'cutTest: "leather.cut-test"' in kit


@pytest.mark.parametrize("name", GAMES_ALL)
def test_no_leather_game_holds_anything(name):
    """Potion Craft added Auto Hold after players reported hand fatigue (herbalism prior art,
    devlog #14), and the UI plan §9 says "No game needs a long press". Every leather input is a
    press in both modes, so HOLDS and HOLDS_STEADY are empty, and the game reads Steady mode."""
    js = _read(_game(name))
    assert _list(js, "HOLDS") == [] and _list(js, "HOLDS_STEADY") == []
    assert _list(js, "KEYS"), f"{name}.js listens for no key: not playable by keyboard"
    assert re.search(r"ctx\.steady\b|ctx\.band\(", _code(js)) or "steadyBand" in js, f"{name}.js ignores Steady mode"
    assert "up: function" not in _code(js), f"{name}.js listens for a release"


@pytest.mark.parametrize("name", GAMES_ALL + ["00-kit"])
def test_no_game_runs_its_own_loop_listens_or_plays_sound(name):
    """One loop, only while a game runs (the frame's rule; the herb harness measured 0 frames in
    the 2s after a game ended). A game with its own frames, timers or listeners would outlive the
    strip; one calling Sound itself would skip the frame's guard and break on a page with none;
    Math.random would make the node bots' runs unrepeatable."""
    code = _code(_read(_game(name)))
    for banned in ("requestAnimationFrame", "setInterval", "setTimeout", "addEventListener",
                   "Sound", ".animate(", "import ", "require(", "fetch(", "XMLHttpRequest", "Math.random"):
        assert banned not in code, f"{name}.js uses {banned}"


@pytest.mark.parametrize("name", GAMES_ALL)
def test_every_game_draws_shapes_and_its_own_aim(name):
    """Never colour alone (Game Accessibility Guidelines), and no game depends on the cursor art
    (the candle cursor's hotspot drifted in 0.2.2; UI plan §9: "No game depends on the cursor
    art"): each draws its marks through the kit's shapes and its own reticle."""
    code = _code(_read(_game(name)))
    assert re.search(r"k\.(barBand|ring|notch|pip|diamond|counted)\(|LeatherGames\.(pips|ruler|hide)\(", code)
    assert "k.reticle(" in code and "ctx.pointer" in code, f"{name}.js draws no aim of its own"


@pytest.mark.parametrize("name", GAMES_ALL)
def test_each_game_reads_the_band_gauge_and_its_unit(name):
    """UI plan §6.4: "Each game declares its unit; the frame prints it" (fraction for Flense and
    Cut, strength for Tan, °C for Harden, SPI for Stitch, minutes for Tool, percent for Curry).
    A game declaring a unit other than the server's would be drawn in its own unit, never the
    server's band (makeBand keeps the game's unit when the two differ)."""
    code = _code(_read(_game(name)))
    m = re.search(r'BAND:\s*\{\s*unit:\s*"([a-z]+)"', code)
    assert m, f"{name}.js has no BAND"
    if name in METHODS:
        assert m.group(1) == _rows()[name]["tuning"]["band"]["unit"], name
    assert "ctx.gauge" in code


# Lane U6's events (UI plan §11 lists the leather bus); unknown events are silent (contracts §11.1),
# so a typo here is silence nobody hears.
SOUND_JS = ROOT / "play" / "static" / "js" / "sound.js"


def _sounds(name: str) -> dict[str, str]:
    m = re.search(r"SOUNDS:\s*\{([^}]*)\}", _code(_read(_game(name))))
    assert m, f"{name}.js names no leather sounds; the frame would play bench.* for it"
    return dict(re.findall(r'(\w+):\s*"([^"]+)"', m.group(1)))


@pytest.mark.parametrize("name", GAMES_ALL)
def test_leather_sounds_are_the_plans_names(name):
    """UI plan §11 lists the leather bus's events. Every SOUNDS value must be one of them, and
    every key a game cues (`ctx.cue("tear")`) must be in its SOUNDS, or that cue is silent."""
    plan = _read(UI_PLAN)
    sec = plan[plan.index("## 11. Sound"):plan.index("## 12.")]
    known = set(re.findall(r"`(leather\.[a-z.-]+)`", sec))
    sounds = _sounds(name)
    assert sounds and all(n in known for n in sounds.values()), f"{name}.js: {sounds} not all in {sorted(known)}"
    for key in re.findall(r'ctx\.cue\("([a-z]+)"', _code(_read(_game(name)))):
        assert key in sounds, f"{name}.js cues {key!r}, which its SOUNDS does not name"


def test_every_sound_is_defined_on_the_bus_when_the_bus_is_here():
    """Once lane U6's sound.js carries the leather bus, every name the games use must be one it
    defines. (Skipped on a branch whose sound.js has no leather bus yet.)"""
    js = _read(SOUND_JS)
    defined = set(re.findall(r'def\("(leather\.[a-z.-]+)"', js))
    if not defined:
        pytest.skip("sound.js has no leather bus on this branch (lane U6 not merged here)")
    for n in GAMES_ALL:
        missing = [s for s in _sounds(n).values() if s not in defined]
        assert not missing, f"{n}.js plays {missing}, which sound.js does not define"


# --- copy, tokens, the world ---------------------------------------------------------------------

def _lane_files() -> list[Path]:
    return [CSS, FRAME, KIT] + [_game(m) for m in GAMES_ALL]


def test_the_page_never_names_a_tier():
    """The server turns the score into a tier (leather_views finish; collect for the cut test);
    the page never names one, as no model and no page authors a number. "Fine" and "Sound" are
    tier names, which is why no reading says a stitch was "fine"."""
    for p in [FRAME, KIT] + [_game(m) for m in GAMES_ALL]:
        for s in _strings(_read(p)):
            for name in TIER_NAMES:
                assert not re.search(rf"\b{name}\b", s), f"{p.name} names the tier {name!r} in {s!r}"


def test_no_planet_reaches_the_page():
    """The owner: no planets anywhere (world-agnostic)."""
    for p in [CSS, KIT] + [_game(m) for m in GAMES_ALL]:
        code = _code(_read(p)) if p.suffix == ".js" else re.sub(r"/\*.*?\*/", "", _read(p), flags=re.S)
        for word in PLANETS:
            assert not re.search(rf"\b{word}\b", code), f"{p.name} says {word!r} outside a comment"


def test_no_em_or_en_dashes_in_the_lanes_files():
    """UI plan §8: no em-dashes or en-dashes in new strings; checked over whole files, comments
    included, because a comment's dash is copied into a string the next time it is reused."""
    for p in _lane_files():
        text = _read(p)
        for ch in ("—", "–"):
            assert ch not in text, f"{p.relative_to(ROOT)} has a dash on line {text[:text.index(ch)].count(chr(10)) + 1}"


def test_no_control_bytes_in_the_lanes_files():
    """Bash heredocs have written `\\b` into source as a literal backspace byte (CLAUDE.md,
    everyday traps), silently breaking a regex while tests passed."""
    for p in _lane_files():
        bad = [c for c in _read(p) if ord(c) < 32 and c not in "\n\r\t"]
        assert not bad, f"{p.name} has control bytes {bad!r}"


def test_the_stylesheet_uses_theme_tokens_only():
    """Keep the colours (owner, 2026-09-28; UI plan §4: "No new colours"). A hide's, a tannage's
    and a dye's colours are content, drawn on the stage; a raw colour here would be a second
    palette on the chrome."""
    css = re.sub(r"/\*.*?\*/", "", _read(CSS), flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
    assert not re.search(r"\b(rgb|rgba|hsl|hsla)\(", css)
    theme = _read(THEME)
    for tok in set(re.findall(r"var\((--[a-z0-9-]+)\)", css)):
        assert f"{tok}:" in theme, f"leather-games.css uses {tok}, which theme-v2.css does not define"


def test_the_stylesheet_styles_what_the_frame_builds():
    """The frame builds `bench-game__band-num` and puts `band-<zone>` and `bench-game--leather` on
    the strip; a stylesheet styling other names would leave the reading unstyled and the hint dim
    while the knife goes through the hide."""
    css, code = _read(CSS), _code(_read(FRAME))
    assert 'el("p", "bench-game__band-num")' in code and ".bench-game__band-num" in css
    assert '"band-" + s' in code and ".band-fail" in css
    assert ".bench-game--leather" in css


def test_no_filled_track_meters():
    """UI plan §15: "No filled-track progress bars". The first draft of Harden's Set and Size and
    Tan's Taken were fillRect bars in an outlined track; they are a marker on a ruler now
    (LeatherGames.ruler). A fillRect the width of a value is the shape this refuses."""
    for n in GAMES_ALL:
        code = _code(_read(_game(n)))
        assert not re.search(r"fillRect\([^)]*\*\s*(Math\.min\(1, )?(set|size|taken|c|f)\b", code), n


# --- the frame: the other benches must not notice ------------------------------------------------

def test_every_leather_path_in_the_frame_is_gated():
    """The band gauge is optional, as the forge's heat, the enchanter's hour and the alchemist's
    gauges were, and the 33 other games must play exactly as before. Every leather path is behind
    a definition's BAND or the gauge it produced; the old lines are unchanged; the herb list is
    still the literal nine, and the frame's own sounds are still all `bench.*`."""
    code = _code(_read(FRAME))
    assert "var DB = r.def.BAND;" in code and "if (DB) {" in code
    assert "if (r.gauge) gh = GAUGE_H;" in code
    assert "if (r.gauge) drawBandGauge(r, g, r.W, r.H - gh);" in code
    assert "else if (r.gauge) showGauge(r);" in code
    assert "if (r.gauge) { var bw = r.gauge.say(); if (bw) return bw; }" in code
    assert "if (def.BAND) {" in code
    # The lines the other benches rely on, as they were.
    assert "r.heat = r.def.HEAT ? makeHeat(r.def.HEAT, heatIn, steady, baseWin * bandScale, narrow) : null;" in code
    assert "var gh = r.heat ? GAUGE_H : r.hour ? HOUR_H : 0;" in code
    assert "if (r.react) gh = GAUGE_H; else if (r.stages) gh = STAGE_H;" in code
    assert 'baseWin * (from === "reaction" ? 1 : bandScale)' in code
    m = re.search(r"var METHODS = \[([^\]]*)\]", code)
    assert re.findall(r'"([a-z]+)"', m.group(1)) == HERB_METHODS
    assert all(n.startswith("bench.") for n in re.findall(r'sound\("([^"]+)"', code))


def test_the_band_gauge_is_drawn_as_a_gauge():
    """The herb Mix lesson (2026-10-06): the owner traced a wavy texture line, believing it was
    the path. The band gauge is a straight bar with the target outlined and notched
    (targetBand), the failing band cross-hatched with a saw edge (dangerZone), a needle with a
    keel (needle) and the bands named in words (gaugeNames), as the alchemist's gauges are."""
    code = _code(_read(FRAME))
    body = code[code.index("function drawBandGauge"):]
    body = body[:body.index("\n  }\n")]
    for fn in ("targetBand(", "dangerZone(", "needle(", "gaugeNames("):
        assert fn in body, fn


def test_the_rare_hide_narrowing_counts_once():
    """Lane E's `band_scale` is the working traits only and its `narrow` the hide's rarity alone
    (rules/leatherworker.py band_for / tuning_for), so the frame multiplies each once. The forge
    once counted narrow_window twice (0.64 where the rule said 0.8)."""
    code = _code(_read(FRAME))
    assert "(bandIn && bandIn.narrow ? NARROW : 1)" in code
    assert code.count("bandIn.narrow") == 1


# --- behaviour, in node ------------------------------------------------------------------------

_DRIVER = r"""// Node driver for tests/test_leather_games.py: loads the frame and every game (herb, forge,
// enchant, alchemy, leather) into a bare sandbox and plays each leather game through
// `BenchGames.simulate`, the frame's own headless path. Every frame the game's draw runs on a stub
// canvas. Bots read only the state a game hands the stage (and the gauge the frame draws), so a
// bot that wins proves the game can be won from what it shows. One JSON object comes out.
"use strict";
const fs = require("fs"), vm = require("vm");
const files = JSON.parse(process.argv[2]);
const sandbox = { window: {}, Math, JSON, Object, Array, Promise, console, Infinity, performance: { now: () => 0 } };
sandbox.window.window = sandbox.window;
vm.createContext(sandbox);
for (const f of files) vm.runInContext(fs.readFileSync(f, "utf8"), sandbox);
const W = sandbox.window, BG = W.BenchGames, LG = W.LeatherGames;
const DT = 1 / 60;
const NAMES = ["flense", "salt", "tan", "curry", "cut", "stitch", "harden", "tool", "dye", "laminate", "assemble", "cut-test"];
const stub = new Proxy({}, {
  get(t, k) {
    if (k === "measureText") return (s) => ({ width: String(s).length * 6.5 });
    if (k === "createLinearGradient") return () => ({ addColorStop() {} });
    if (k in t) return t[k];
    return () => {};
  },
  set(t, k, v) { t[k] = v; return true; }
});
const TUNING = process.argv[3] ? JSON.parse(process.argv[3]) : {};

function sim(name, o) {
  o = o || {};
  const tuning = Object.assign({}, TUNING[name] || {}, { seed: 5 }, o.tuning || {});
  const opts = Object.assign({ method: "leather." + name, tuning }, tuning.band ? { band: tuning.band } : {},
    o.steady ? { steady: true } : {}, o.opts || {});
  return BG.simulate(opts);
}

function hand(s) {
  return {
    tap(key) { s.press(key); s.release(key); },
    click(x, y) { s.pointer("move", x, y); s.pointer("down", x, y); s.pointer("up", x, y); },
    move(x, y) { s.pointer("move", x, y); },
  };
}

const mid = (b) => (b[0] + b[1]) / 2;
const xOf = (v, st, width) => 10 + (v - st.scale[0]) / (st.scale[1] - st.scale[0]) * (width - 20);
let width = 360;

const PERFECT = {
  flense: (s, io, m) => {
    const st = s.game.state(), aimFor = mid(st.band) - st.sway, d = st.pressure - mid(st.band);
    const inner = (st.band[1] - st.band[0]) / 2 * 0.5;
    if (m) {
      io.move(xOf(aimFor, st, width), 30);
      if (!st.busy && Math.abs(d) < inner * 0.6) io.click(xOf(aimFor, st, width), 30);
      return;
    }
    if (st.aim < aimFor - 0.035) io.tap("ArrowUp");
    else if (st.aim > aimFor + 0.035) io.tap("ArrowDown");
    else if (!st.busy && Math.abs(d) < inner * 0.6) io.tap("Space");
  },
  salt: (s, io, m) => {
    const st = s.game.state();
    if (st.busy > 0 || !st.bare.length) return;
    if (m) { const c = st.cell[st.bare[0]]; io.click(c.x, c.y); }
    else if (st.bare.indexOf(st.scoop) >= 0) io.tap("Space");
  },
  tan: (s, io, m) => {
    const st = s.game.state();
    if (st.phase === "steps") { if (st.taken >= st.ready && st.strength < st.band[0] + 0.03) { if (m) io.click(100, 40); else io.tap("Space"); } }
    else if (st.phase === "cut" && st.through) { if (m) s.button(); else io.tap("C"); }
  },
  "cut-test": (s, io, m) => {
    const st = s.game.state();
    if (!st.busy && st.lean < 0.02) { if (m) io.click(100, 40); else io.tap("Space"); }
  },
  curry: (s, io, m) => {
    const st = s.game.state();
    if (!st.busy && st.fat + st.rise <= mid(st.band) + 1.5) { if (m) io.click(100, 40); else io.tap("Space"); }
  },
  cut: (s, io, m) => {
    const st = s.game.state();
    const want = st.line_soon - st.tremor;
    if (m) {
      const y = st.cy + want * st.half;
      if (!st.started) io.click(100, st.cy + st.line * st.half); else io.move(100, y);
      return;
    }
    if (!st.started) { io.tap("Space"); return; }
    const v = (want - st.knife) / 0.25 + st.line_rate;
    const h = Math.max(-3, Math.min(3, Math.round(v / st.turn)));
    if (h > st.heading) io.tap("ArrowDown"); else if (h < st.heading) io.tap("ArrowUp");
  },
  stitch: (s, io, m) => {
    const st = s.game.state();
    if (!st.pulling && st.pitch <= mid(st.band) + 0.15) { if (m) io.click(100, 40); else io.tap("Space"); }
  },
  harden: (s, io, m) => {
    const st = s.game.state();
    const go = (!st.dipped && st.water >= st.band[0]) || (st.dipped && st.set >= 1);
    if (go) { if (m) io.click(100, 40); else io.tap("Space"); }
  },
  tool: (s, io, m) => {
    const st = s.game.state(), inner = (st.band[1] - st.band[0]) / 2 * 0.5;
    if (st.minutes > mid(st.band) + inner * 0.8) { io.tap("W"); return; }
    if (!st.busy && Math.abs(st.minutes - mid(st.band)) < inner * 0.8) { if (m) io.click(100, 40); else io.tap("Space"); }
  },
  dye: (s, io, m) => {
    const st = s.game.state();
    if (st.pot <= 0 && Math.abs(st.load - mid(st.band)) < 2) { if (m) io.click(100, 40); else io.tap("Space"); }
  },
  laminate: (s, io, m) => {
    const st = s.game.state();
    if (!st.busy && st.glue < mid(st.band) - 5 && st.since < 0.5) { if (m) io.click(100, 40); else io.tap("Space"); return; }
    if (st.glue >= st.band[0] && Math.abs(st.since - st.tack) <= DT / 2 + 1e-9) { if (m) s.button(); else io.tap("C"); }
  },
  assemble: (s, io, m) => {
    const st = s.game.state();
    if (!st.pulled && Math.abs(st.offset_s) <= DT / 2 + 1e-9) { if (m) io.click(100, 40); else io.tap("Space"); }
  },
};

function play(name, o) {
  o = o || {};
  width = o.width || 360;
  const s = sim(name, o);
  const io = hand(s);
  const bot = o.idle ? null : o.bot || PERFECT[name];
  let ended = false, frames = 0;
  while (!ended && frames < 60 * 60) {
    s.game.draw(stub, width, 88);
    if (bot) bot(s, io, o.mode === "mouse");
    ended = s.step(DT);
    frames++;
  }
  return Object.assign(s.result(), { seconds: +(frames / 60).toFixed(3), duration: s.game.duration, hint: s.hint() });
}

// A hand that sees the state `lag` seconds late, as a person does, and cannot press the same key
// again within a quarter of a second (a person presses about four times a second, not sixty).
function late(lag, name) {
  const q = [], last = {};
  return (s, io, m) => {
    q.push({ t: s.t(), st: s.game.state() });
    while (q.length > 1 && q[1].t <= s.t() - lag) q.shift();
    const real = s.game.state, tap = io.tap, click = io.click, btn = s.button;
    const ok = (k) => { if (last[k] != null && s.t() - last[k] < 0.25) return false; last[k] = s.t(); return true; };
    s.game.state = () => q[0].st;
    io.tap = (k) => { if (ok(k)) tap(k); };
    io.click = (x, y) => { if (ok("click")) click(x, y); };
    s.button = () => { if (ok("button")) btn(); };
    try { PERFECT[name](s, io, m); } finally { s.game.state = real; io.tap = tap; io.click = click; s.button = btn; }
  };
}

function holdAll(keys) { let done = false; return (s) => { if (!done) { keys.forEach((k) => s.press(k)); done = true; } }; }
function mash(keys, every) { let n = 0; return (s) => { n++; if (n % every === 0) keys.forEach((k) => { s.press(k); s.release(k); }); }; }
function mashOne(key, every) { let n = 0; return (s) => { n++; if (n % every === 0) { s.press(key); s.release(key); } }; }
function clickMash(every) { let n = 0; return (s) => { n++; if (n % every === 0) { s.pointer("down", 100, 40); s.pointer("up", 100, 40); } }; }

const out = { methods: BG.methods, leather: BG.methodsFor("leather"), forge: BG.methodsFor("forge"),
  herb: BG.methodsFor("herb"), units: BG.bandUnits, kit_methods: LG.methods, games: {} };
for (const n of NAMES) {
  const def = W.BenchGameDefs["leather." + n];
  const g = out.games[n] = {
    keys: def.KEYS,
    keys_run: play(n), keys_steady: play(n, { steady: true }),
    mouse: play(n, { mode: "mouse" }), mouse_steady: play(n, { mode: "mouse", steady: true }),
    narrow: play(n, { mode: "mouse", width: 220 }),
    sloppy: play(n, { bot: late(0.1, n) }),
    idle: play(n, { idle: true }), idle_steady: play(n, { idle: true, steady: true }),
    hold_all: play(n, { bot: holdAll(def.KEYS) }),
    mash_all: play(n, { bot: mash(def.KEYS, 3) }),
    mash_fast: play(n, { bot: mash(def.KEYS, 1) }),
    click_mash: play(n, { bot: clickMash(3) }),
  };
  g.mash_each = {};
  def.KEYS.forEach((k) => { g.mash_each[k] = play(n, { bot: mashOne(k, 4) }).score; });
  const s = sim(n, { steady: true }); let ups = 0;
  const up = s.game.up; s.game.up = function () { ups++; return up && up.apply(this, arguments); };
  for (const k of def.KEYS) { s.press(k); s.release(k); }
  s.pointer("down", 100, 40); s.pointer("up", 100, 40);
  g.steady_ups = ups;
  const s0 = sim(n);
  g.gauge = { unit: s0.gauge.unit, band: s0.gauge.band, target: s0.gauge.target, fail: s0.gauge.fail,
    scale: s0.gauge.scale, v: s0.gauge.v, text: s0.gauge.text(), words: ["low", "in", "high", "fail"].map((z) => s0.gauge.word(z)) };
  g.reduced = play(n, { opts: { reducedMotion: true } }).score;
}
// What the server sent is what is played; the opts win over the tuning; narrow tightens once.
const gw = (n, o) => { const s = sim(n, o); return s.gauge.band[1] - s.gauge.band[0]; };
out.inputs = {
  flense_from_opts: sim("flense", { opts: { band: { unit: "fraction", value_start: 0.3, target: [0.4, 0.5], fail: [0.6, 1], drift: 0 } } }).gauge,
  flense_wrong_unit: sim("flense", { opts: { band: { unit: "celsius", target: [50, 60] } } }).gauge.unit,
  flense_width: gw("flense"),
  flense_narrow: gw("flense", { opts: { band: Object.assign({}, (TUNING.flense || {}).band, { narrow: true }) } }),
  flense_steady: gw("flense", { steady: true }),
  curry_supple: gw("curry", { tuning: TUNING.curry_supple || {} }),
  curry_width: gw("curry"),
  cut_band: sim("cut").gauge.band,
  tan_band: sim("tan").gauge.band,
  stitch_band: sim("stitch").gauge.band,
  harden_band: sim("harden").gauge.band,
  tan_one_session: play("tan", { tuning: { two_halves: false } }),
  tan_one_session_early: play("tan", { tuning: { two_halves: false }, bot: (s, io) => { const st = s.game.state();
    if (st.phase === "steps") PERFECT.tan(s, io, false); else if (st.phase === "cut" && st.front > 0.3 && st.early === 0) io.tap("C"); else if (st.through) io.tap("C"); } }),
  tan_halves: (TUNING.tan || {}).two_halves,
  texts: {
    flense: sim("flense").gauge.text(), harden: sim("harden").gauge.text(), stitch: sim("stitch").gauge.text(),
    tool: sim("tool").gauge.text(), curry: sim("curry").gauge.text(), tan: sim("tan").gauge.text(),
  },
  others_ignore: ["grind", "forge", "assemble", "bind", "react"].map((m) => {
    const s = BG.simulate({ method: m, tuning: { seed: 5, band: { unit: "fraction", target: [0, 1] } }, band: { unit: "fraction", target: [0, 1] } });
    return [s.gauge, s.ctx.gauge];
  }),
  forge_assemble_track: W.BenchGameDefs.assemble.track,
};
process.stdout.write(JSON.stringify(out));
"""


def _tunings() -> dict:
    """The server's tuning for every method, built by the real `tuning_for` (so a change to
    leatherworker.json's bands is what the bots play). Tan is a bark tannage that waits in a vat
    (two halves, as most tannages are); `curry_supple` carries the supple trait's band scale."""
    from rules import leatherworker as lw

    out = {m: lw.tuning_for(lw.LeatherPlan(method=m)) for m in METHODS if m != "tan"}
    out["tan"] = lw.tuning_for(lw.LeatherPlan(method="tan", wait_minutes=4 * 7 * 1440, tannage="oak-bark"))
    out["curry_supple"] = lw.tuning_for(lw.LeatherPlan(method="curry", working=["supple"]))
    return out


@pytest.fixture(scope="module")
def node_run(tmp_path_factory):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    script = tmp_path_factory.mktemp("leather") / "driver.js"
    script.write_text(_DRIVER, encoding="utf-8")
    files = ([str(HERB_GAMES / f"{m}.js") for m in HERB_METHODS]
             + [str(FORGE_GAMES / f"{m}.js") for m in FORGE_METHODS]
             + [str(ENCHANT_GAMES / f"{m}.js") for m in ENCHANT_METHODS]
             + [str(ALCHEMY_GAMES / f"{m}.js") for m in ALCHEMY_METHODS]
             + [str(KIT)] + [str(_game(m)) for m in GAMES_ALL] + [str(FRAME)])
    done = subprocess.run([node, str(script), json.dumps(files), json.dumps(_tunings())],
                          capture_output=True, text=True, encoding="utf-8", timeout=900)
    assert done.returncode == 0, done.stderr[:3000]
    return json.loads(done.stdout)


def test_the_leather_games_come_by_registration(node_run):
    """Contracts §11.1: the leather games register on the shared registry with `track: "leather"`.
    Measured on the live API: the herb, forge, enchant and alchemy lists are exactly what they
    were, the forge's Assemble is still the forge's, and `methodsFor("leather")` lists the eleven
    and the cut test under their keys."""
    assert node_run["methods"] == (HERB_METHODS + FORGE_METHODS + ENCHANT_METHODS + ALCHEMY_METHODS
                                   + [f"leather.{n}" for n in GAMES_ALL])
    assert node_run["leather"] == [f"leather.{n}" for n in GAMES_ALL]
    assert node_run["forge"] == FORGE_METHODS and node_run["herb"] == HERB_METHODS
    assert node_run["inputs"]["forge_assemble_track"] == "forge"
    assert node_run["kit_methods"] == METHODS
    assert sorted(node_run["units"]) == sorted(["fraction", "strength", "percent", "celsius", "spi", "minutes"])


@pytest.mark.parametrize("name", GAMES_ALL)
@pytest.mark.parametrize("mode", ["keys_run", "keys_steady", "mouse", "mouse_steady", "narrow"])
def test_a_perfect_run_scores_one(node_run, name, mode):
    """The server maps the score to the tier under the ceiling, so a perfect run that tops out
    under 1 caps every player a tier low (the alchemy lane measured Calcine at 0.975 for nothing
    but crossing the band's rim on the way in). A bot reading only the game's state plays each
    game by keyboard, by mouse on a 360px and a 220px meter, and in Steady mode; each must score
    0.99 or better."""
    r = node_run["games"][name][mode]
    assert r["score"] >= 0.99, f"{name} {mode}: {r}"


@pytest.mark.parametrize("name", GAMES_ALL)
def test_a_perfect_run_is_short(node_run, name):
    """The owner's standing rule for crafts: minigames are always played, so they are short. A
    mandatory minigame that drags is the KCD2 complaint (forge prior art §0 item 5). A clean run
    ends inside 7s by keyboard and by mouse."""
    g = node_run["games"][name]
    assert g["keys_run"]["seconds"] <= 7, g["keys_run"]
    assert g["mouse"]["seconds"] <= 7, g["mouse"]


@pytest.mark.parametrize("name", GAMES_ALL)
@pytest.mark.parametrize("mode", ["idle", "idle_steady"])
def test_an_idle_run_scores_nothing(node_run, name, mode):
    """Pressing nothing must not earn a tier: no stroke, no salt, no step, no cut, no dip."""
    r = node_run["games"][name][mode]
    assert r["score"] == 0, f"{name} {mode}: {r}"


@pytest.mark.parametrize("name", GAMES_ALL)
def test_holding_or_mashing_every_key_scores_almost_nothing(node_run, name):
    """The owner's lesson from the herb games: cheating must not score well. Holding every key the
    game listens to, mashing them all every third frame (20 a second), every frame, clicking the
    strip every third frame, or mashing any one key four frames apart, must each stay under 0.25,
    a crude result at best."""
    g = node_run["games"][name]
    for mode in ("hold_all", "mash_all", "mash_fast", "click_mash"):
        assert g[mode]["score"] < 0.25, f"{name} {mode}: {g[mode]}"
    for key, score in g["mash_each"].items():
        assert score < 0.25, f"{name}: mashing {key} scored {score}"


def test_sloppy_play_scores_between(node_run):
    """What a hand that sees the strip 0.1s late and presses at most four times a second earns.
    Measured 2026-10-08: on the beat and timing games less than a perfect run (Stitch 0.87, Dye
    0.86, Laminate 0.84, Assemble 0.53, the forge's own window, the tightest); on the gauge games,
    where the needle moves at a hand's pace, the late hand still scores 1. Before the stitch's
    awl slowed toward its mark the band lasted 0.13s and this hand scored 0 there. A change to a
    curve must move these on purpose."""
    timing = {"stitch": (0.75, 0.95), "dye": (0.75, 0.95), "laminate": (0.7, 0.95), "assemble": (0.45, 0.7)}
    for n in GAMES_ALL:
        s = node_run["games"][n]["sloppy"]["score"]
        lo, hi = timing.get(n, (0.95, 1.0))
        assert lo <= s <= hi, f"{n} sloppy {s}"


@pytest.mark.parametrize("name", GAMES_ALL)
def test_steady_mode_never_hears_a_release(node_run, name):
    """The frame drops every key-up and pointer-up in Steady mode (STEADY-NO-RELEASE), and no
    leather game listens for one anyway."""
    assert node_run["games"][name]["steady_ups"] == 0


@pytest.mark.parametrize("name", GAMES_ALL)
def test_reduced_motion_plays_the_same(node_run, name):
    """Reduced motion takes away particles, shake and the travelling rings (the counted beat
    stands in), never the game: the same perfect bot scores the same 0.99."""
    assert node_run["games"][name]["reduced"] >= 0.99


def test_what_the_server_sent_is_what_is_played(node_run):
    """Contracts §11.1: `opts.band` is the server's (rules/leatherworker.py band_for), and its
    target, failing band and start are what the gauge draws; a band in a unit the game was not
    built for keeps the game's own unit (a Flense gauge in °C would mean nothing)."""
    i = node_run["inputs"]
    f = i["flense_from_opts"]
    assert f["target"] == [0.4, 0.5] and f["fail"] == [0.6, 1] and f["v"] == 0.3
    assert f["band"][1] < 0.6
    assert i["flense_wrong_unit"] == "fraction"
    for n in METHODS:
        g = node_run["games"][n]["gauge"]
        band = _rows()[n]["tuning"]["band"]
        assert g["unit"] == band["unit"], n
        assert g["target"] == [float(x) for x in band["target"]], n
        assert (g["fail"] is None) == (band["fail"] is None), n
        assert g["words"][1], f"{n}: the band has no name in words"
    # The tannage that waits is played in two halves (the server says so).
    assert i["tan_halves"] is True


def test_the_bands_never_reach_into_the_failing_band(node_run):
    """A widened band pushed into the failing band would score a stroke through the hide as
    clean (the forge's rule: the band never grows into the burning zone)."""
    for n in GAMES_ALL:
        g = node_run["games"][n]["gauge"]
        if g["fail"]:
            lo, hi = g["band"]
            flo, fhi = g["fail"]
            assert hi < flo or lo > fhi, f"{n}: band {g['band']} meets fail {g['fail']}"


def test_ends_anchored_bands_widen_inward(node_run):
    """Cut's band runs from 0 off the line, Tan's to the strongest liquor: widening them about
    their middle would put half the widening off the scale and leave the band narrower than the
    generous start promises. They widen inward from their end."""
    i = node_run["inputs"]
    assert i["cut_band"][0] == 0 and i["cut_band"][1] > 0.1
    assert i["tan_band"][1] == 1 and i["tan_band"][0] < 0.7


def test_rarer_hides_and_traits_scale_the_window_once(node_run):
    """UI plan §9: "rarer hides narrow the window" (`narrow`, x0.8, once); Steady widens it by the
    game's own factor (Flense x1.5); a working trait (supple, 1.25 at Curry) arrives in the
    server's band_scale and widens it once."""
    i = node_run["inputs"]
    assert i["flense_narrow"] == pytest.approx(i["flense_width"] * 0.8, rel=1e-6)
    assert i["flense_steady"] == pytest.approx(i["flense_width"] * 1.5, rel=1e-3)
    assert i["curry_supple"] == pytest.approx(i["curry_width"] * 1.25, rel=1e-3)


def test_the_tan_game_in_one_session_ends_with_its_cut(node_run):
    """A tannage that does not wait (brain tan: `two_halves` false) plays the cut test inside the
    game (UI plan §9, "Space steps; C cuts"); a cut before the tan has run through shows the raw
    core and costs 0.15, and the game goes on until it is cut through."""
    i = node_run["inputs"]
    assert i["tan_one_session"]["score"] >= 0.99
    early = i["tan_one_session_early"]["score"]
    assert 0.9 <= early <= 0.95, early


def test_the_gauges_speak_in_words_and_numbers(node_run):
    """UI plan §6.4: every band "a number and a bar as well as a colour", the number in its real
    unit: fraction of thickness for Flense, °C for Harden, stitches per inch for Stitch, minutes
    since wetting for Tool, percent fat for Curry, and the liquor's strength in words for Tan."""
    t = node_run["inputs"]["texts"]
    assert t["flense"] == "0.10 of thickness"
    assert t["harden"] == "Water 20 °C"
    assert t["stitch"] == "Pitch 18 SPI"   # a punch at once would crowd the hole
    assert t["tool"] == "0 min since wetting"
    assert t["curry"] == "Fat 0%"
    assert t["tan"] == "Liquor 0.00, weak"


def test_other_benches_ignore_the_band(node_run):
    """A herb, forge, enchant or alchemy game handed a band (a shell passing the whole roll body
    through) gets no band gauge."""
    for row in node_run["inputs"]["others_ignore"]:
        assert row == [None, None], row
