"""The alchemist's minigames (alchemy lane U2): the eight games in `play/static/js/alchemy-games/`,
the three gauges they add to the shared strip frame `play/static/js/table/33-bench-games.js`
(FLAME, the alchemist's fire; REACTION, the 0 to 100 reaction gauge; STAGES, the colour-stage
track), and `play/static/css/alchemy-games.css`.

Mirrors tests/test_enchant_games.py: most checks read the files, and the behaviour group loads
the frame and every game (herb, forge, enchant and alchemy, so the registry is the real one)
into node and plays each alchemy game through `BenchGames.simulate`, the frame's own headless
path (the same per-frame `advance` as the strip's loop), with the server's real tuning from
rules/alchemist.py `tuning_for`. Every frame the driver also calls the game's `draw` on a stub
canvas, so a draw that throws fails here rather than in the owner's strip. Bots read only the
state a game hands the stage, so a bot that wins proves the game can be won from what it shows:
by keyboard, by mouse on a 360px and a 220px meter, in Steady mode (where no release is ever
heard), and, for the two timing games, by the counted beat alone (the reduced-motion form).
Three kinds of player who will not play (holding every key, mashing every key, pressing
nothing) are measured too: the owner's 2026-10-06 note on the herb games was that cheating
must not score well.

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
GAMES = ROOT / "play" / "static" / "js" / "alchemy-games"
CSS = ROOT / "play" / "static" / "css" / "alchemy-games.css"
THEME = ROOT / "play" / "static" / "css" / "theme-v2.css"
UI_PLAN = ROOT / "docs" / "alchemy-ui-plan.md"
CONTRACTS = ROOT / "docs" / "alchemy-contracts.md"
HERB_GAMES = ROOT / "play" / "static" / "js" / "bench-games"
FORGE_GAMES = ROOT / "play" / "static" / "js" / "forge-games"
ENCHANT_GAMES = ROOT / "play" / "static" / "js" / "enchant-games"

METHODS = ["dissolve", "calcine", "filter", "distill", "react", "sublime", "bottle", "transmute"]
FLAME_GAMES = ["calcine", "distill", "sublime"]
REACTION_GAMES = ["dissolve", "filter", "react", "bottle"]
HERB_METHODS = ["grind", "mix", "brew", "dry", "reduce", "extract", "infuse", "steep", "neutralize"]
FORGE_METHODS = ["smelt", "alloy", "forge", "quench", "temper", "fold", "hone", "assemble", "finish",
                 "strengthen"]
ENCHANT_METHODS = ["prepare", "attune", "bind", "refine", "unbind", "cleanse"]
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

def test_the_eight_games_are_the_contracts_methods():
    """Contracts §8 lists the bench's methods; Assay has none (UI plan §9: "Assay has no
    minigame, like tasting and the forge's assay"). A drifted list (a missing `sublime`, a stray
    `assay`) would leave the bench rolling a success with no game, which `BenchGames.play`
    rejects."""
    m = re.search(r"\*\*Methods:\*\* `([^`]*)`", _read(CONTRACTS))
    assert m, "contracts §8 no longer lists the methods where this test reads them"
    contract = [x.strip() for x in m.group(1).split(",")]
    assert sorted(x for x in contract if x != "assay") == sorted(METHODS)
    assert sorted(p.stem for p in GAMES.glob("*.js")) == sorted(METHODS)


def test_the_server_names_a_game_for_every_method():
    """rules/alchemist.py tuning_for sends `game` and `gauge` from content/world-classes/
    alchemist.json. A method whose content named a gauge this lane did not build (a "pour"
    gauge read as a reaction, say) would play with the game's defaults and never the server's
    numbers."""
    data = json.loads((ROOT / "content" / "world-classes" / "alchemist.json").read_text(encoding="utf-8"))
    rows = data["bench"]["methods"]
    for m in METHODS:
        tun = rows[m]["tuning"]
        assert tun["game"] == m
        gauge = tun["gauge"]
        code = _code(_read(_game(m)))
        if gauge == "heat":
            assert "FLAME:" in code and "heat" in tun, m
        elif gauge == "reaction":
            assert "REACTION:" in code and "reaction" in tun, m
        elif gauge == "pour":
            assert 'from: "pour"' in code and "pour" in tun, m
        elif gauge == "stages":
            assert "STAGES: true" in code and "stages" in tun, m
        else:
            pytest.fail(f"{m}: unknown gauge {gauge!r}")


@pytest.mark.parametrize("method", METHODS)
def test_every_alchemy_game_registers_like_the_others(method):
    """Contracts §12: an alchemy game registers on `window.BenchGameDefs[method]` with
    `track: "alchemy"`, as the forge and enchant games do, so the one frame runs all four benches
    and `methodsFor("alchemy")` finds them. The first-time card is up for two seconds; a longer
    one starts the game under the player's eyes."""
    code = _code(_read(_game(method)))
    assert re.search(r"defs\." + method + r"\s*=\s*\{", code), f"{method}.js does not register defs.{method}"
    assert f'id: "{method}"' in code
    assert 'track: "alchemy"' in code
    assert re.search(r"create\s*:\s*function\s*\(ctx\)", code)
    first = re.search(r'first:\s*"([^"]+)"', code)
    assert first and len(first.group(1)) <= 100, f"{method}.js: first-time card {first and first.group(1)!r}"


@pytest.mark.parametrize("method", METHODS)
def test_steady_mode_declares_no_hold(method):
    """Potion Craft added Auto Hold after players reported hand fatigue (herbalism prior art,
    devlog #14), and the frame drops every release in Steady mode, so HOLDS_STEADY is empty and
    every game reads Steady mode (its holds become toggles: the fire, the pour)."""
    js = _read(_game(method))
    assert _list(js, "HOLDS_STEADY") == []
    assert _list(js, "KEYS"), f"{method}.js listens for no key: not playable by keyboard"
    assert re.search(r"ctx\.steady\b", _code(js)), f"{method}.js ignores Steady mode"


@pytest.mark.parametrize("method", METHODS)
def test_no_game_runs_its_own_loop_listens_or_plays_sound(method):
    """One loop, only while a game runs (the frame's rule; the herb harness measured 0 frames in
    the 2s after a game ended). A game with its own frames, timers or listeners would outlive the
    strip; one calling Sound itself would skip the frame's guard and break on a page with none."""
    code = _code(_read(_game(method)))
    for banned in ("requestAnimationFrame", "setInterval", "setTimeout", "addEventListener",
                   "Sound", ".animate(", "import ", "require(", "fetch(", "XMLHttpRequest", "Math.random"):
        assert banned not in code, f"{method}.js uses {banned}"


@pytest.mark.parametrize("method", METHODS)
def test_every_game_draws_shapes_and_its_own_aim(method):
    """Never colour alone (Game Accessibility Guidelines), and no game depends on the cursor art
    (the candle cursor's hotspot drifted in 0.2.2): each draws its marks through the kit's shapes
    and its own reticle."""
    code = _code(_read(_game(method)))
    assert re.search(r"k\.(dialBand|barBand|ring|notch|pip)\(", code)
    assert "k.reticle(" in code and "ctx.pointer" in code, f"{method}.js draws no aim of its own"


# Lane U5's events beyond the UI plan's §11 list (merged on build/alchemy, 9cf2ce2; its brief to
# this lane, 2026-10-07): the games' own hit and miss, the spill, Distill's swap, Sublime's
# scrape, and the fire fed and banked.
U5_EVENTS = {"alchemy.hit", "alchemy.miss", "alchemy.spill", "alchemy.swap", "alchemy.scrape",
             "alchemy.feed", "alchemy.bank", "alchemy.seal", "alchemy.uncork", "alchemy.clink",
             "alchemy.shatter", "alchemy.found"}
SOUND_JS = ROOT / "play" / "static" / "js" / "sound.js"


def _sounds(method: str) -> dict[str, str]:
    m = re.search(r"SOUNDS:\s*\{([^}]*)\}", _code(_read(_game(method))))
    assert m, f"{method}.js names no alchemy sounds; the frame would play bench.* for it"
    return dict(re.findall(r'(\w+):\s*"([^"]+)"', m.group(1)))


@pytest.mark.parametrize("method", METHODS)
def test_alchemy_sounds_are_the_buses_names(method):
    """UI plan §11 (and lane U5's additions) list the alchemy bus's events, and unknown names are
    silent (contracts §12), so a game naming `alchemy.react.hit` (no such event) would play
    nothing and nobody would hear why. Every SOUNDS value must be a known event, and every key a
    game cues (`ctx.cue("feed")`) must be in its SOUNDS, or that cue is silent too."""
    plan = _read(UI_PLAN)
    sec = plan[plan.index("## 11. Sound"):plan.index("## 12.")]
    known = set(re.findall(r"`(alchemy\.[a-z.]+)`", sec)) | U5_EVENTS
    sounds = _sounds(method)
    assert sounds and all(n in known for n in sounds.values()), f"{method}.js: {sounds} not all in {sorted(known)}"
    for key in re.findall(r'ctx\.cue\("([a-z]+)"', _code(_read(_game(method)))):
        assert key in sounds, f"{method}.js cues {key!r}, which its SOUNDS does not name"


@pytest.mark.parametrize("method", METHODS)
def test_a_minigame_overshoot_never_sounds_the_mishap(method):
    """Plan §8.2: "A minigame overshoot never triggers the mishap". `alchemy.flare` is the
    volatile mishap's whump on a failed roll; a React boil-over playing it (the first draft did)
    would tell the player a mishap had happened when nothing had."""
    assert "alchemy.flare" not in _sounds(method).values()


def test_every_sound_is_defined_on_the_bus_when_the_bus_is_here():
    """Once lane U5's sound.js is on the branch, every name the games use must be one it
    defines: a typo between the two lanes is silence nobody hears. (Skipped on a branch whose
    sound.js has no alchemy bus yet.)"""
    js = _read(SOUND_JS)
    defined = set(re.findall(r'def\("(alchemy\.[a-z.]+)"', js))
    if not defined:
        pytest.skip("sound.js has no alchemy bus on this branch (lane U5 not merged here)")
    for m in METHODS:
        missing = [n for n in _sounds(m).values() if n not in defined]
        assert not missing, f"{m}.js plays {missing}, which sound.js does not define"


def test_the_fire_is_heard_through_one_burner():
    """Lane U5's contract: one `Sound.burner({kind, liquid})` per heat game, fed the needle's
    place on the scale (0..1) every frame and stopped when the game ends. A burner never stopped
    would roar on over the table after the bench closed."""
    code = _code(_read(FRAME))
    assert "if (def.FLAME && r.heat && window.Sound && typeof window.Sound.burner === \"function\")" in code
    assert "r.burner.heat(clamp((r.heat.c - r.heat.scale[0]) / (r.heat.scale[1] - r.heat.scale[0]), 0, 1))" in code
    fin = code[code.index("function finish("):code.index("function play(")]
    assert "r.burner.stop()" in fin


def test_each_game_carries_the_gauge_its_operation_needs():
    """UI plan §6.4: the heat gauge for Calcine, Distill and Sublime; the reaction gauge for
    React, Dissolve and Bottle (and Filter's pour, the same bar read from `pour`); the colour-
    stage track for Transmute. A gauge on the wrong game would draw a bar that means nothing."""
    for m in METHODS:
        code = _code(_read(_game(m)))
        assert ("FLAME:" in code) == (m in FLAME_GAMES), m
        assert ("REACTION:" in code) == (m in REACTION_GAMES), m
        assert ("STAGES: true" in code) == (m == "transmute"), m


def test_every_reaction_gauge_names_its_zones_in_words():
    """UI plan §6.4: the gauge carries "the band's name in words: calm, working, boiling over",
    and over the flare line the hint changes to "Let it settle" in words. A gauge with no words
    would leave the colour of a needle to say the reaction is boiling."""
    for m in REACTION_GAMES:
        code = _code(_read(_game(m)))
        words = re.search(r"words:\s*\[([^\]]*)\]", code)
        assert words and len(re.findall(r'"([^"]*)"', words.group(1))) == 4, m
        say = re.search(r"say:\s*\{([^}]*)\}", code).group(1)
        assert "flare:" in say and "high:" in say, m
    react = _code(_read(_game("react")))
    assert '"calm", "working"' in react and '"boiling over"' in react and "let it settle" in react


# --- copy, tokens, the world ---------------------------------------------------------------------

def _lane_files() -> list[Path]:
    return [CSS, FRAME] + [_game(m) for m in METHODS]


def test_the_page_never_names_a_tier():
    """The server turns the score into a tier (alchemy_views finish); the page never names one,
    as no model and no page authors a number. "Fine" and "Sound" are tier names, which is why no
    hint says a seal was "fine"."""
    for p in [FRAME] + [_game(m) for m in METHODS]:
        for s in _strings(_read(p)):
            for name in TIER_NAMES:
                assert not re.search(rf"\b{name}\b", s), f"{p.name} names the tier {name!r} in {s!r}"


def test_no_planet_reaches_the_page():
    """The owner: "this is not earth", and the old alchemy's metals-for-planets would not be
    world-agnostic. The colour stages are colours; nothing here names a planet."""
    for p in [CSS] + [_game(m) for m in METHODS]:
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
    everyday traps), silently breaking a regex while tests passed; the fire's °C formatter is a
    regex with `\\B` and `\\d`."""
    for p in _lane_files():
        bad = [c for c in _read(p) if ord(c) < 32 and c not in "\n\r\t"]
        assert not bad, f"{p.name} has control bytes {bad!r}"


def test_the_stylesheet_uses_theme_tokens_only():
    """Keep the colours (owner, 2026-09-28; UI plan §4: "No new colours"). A liquid's colour, a
    stage's colour and the gauges' scales are content, drawn on the canvas; a raw colour here
    would be a second palette on the chrome."""
    css = re.sub(r"/\*.*?\*/", "", _read(CSS), flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
    assert not re.search(r"\b(rgb|rgba|hsl|hsla)\(", css)
    theme = _read(THEME)
    for tok in set(re.findall(r"var\((--[a-z0-9-]+)\)", css)):
        assert f"{tok}:" in theme, f"alchemy-games.css uses {tok}, which theme-v2.css does not define"


def test_the_stylesheet_styles_what_the_frame_builds():
    """The frame builds `bench-game__react-num` and puts `react-<zone>` and `bench-game--alchemy`
    on the strip; a stylesheet styling other names would leave the number unstyled and the hint
    dim while the reaction boils over."""
    css, code = _read(CSS), _code(_read(FRAME))
    assert 'el("p", "bench-game__react-num")' in code and ".bench-game__react-num" in css
    assert '"react-" + s' in code and ".react-flare" in css
    assert ".bench-game--alchemy" in css


# --- the frame: the herb, forge and enchant games must not notice --------------------------------

def test_every_alchemy_path_in_the_frame_is_gated():
    """The three gauges are optional, as the forge's heat and the enchanter's hour were, and the
    25 other games must play exactly as before (the lane's proof: 450 scripted runs under the old
    and the new frame, Math.random pinned, every state, hint, score and canvas call hashed,
    identical; report 2026-10-07). Every alchemy path is behind a definition's FLAME, REACTION or
    STAGES or an object it produced, the old forge lines are unchanged, and the herb list is
    still the literal nine."""
    code = _code(_read(FRAME))
    assert "var DF = r.def.FLAME, DR = r.def.REACTION;" in code
    assert "if (DF) {" in code and "if (DR) {" in code
    assert "if (r.def.STAGES) r.stages = readStages(" in code
    assert "if (H.named) { drawFlameGauge(r, g, W, top); return; }" in code
    assert "if (r.react) gh = GAUGE_H; else if (r.stages) gh = STAGE_H;" in code
    assert "if (r.react) r.react.step(dt);" in code
    assert "if (r.game && r.game.urgent) {" in code
    assert "if (r.heat && r.heat.say) {" in code
    # The forge's own lines, as they were.
    assert "r.heat = r.def.HEAT ? makeHeat(r.def.HEAT, heatIn, steady, baseWin * bandScale, narrow) : null;" in code
    assert "var gh = r.heat ? GAUGE_H : r.hour ? HOUR_H : 0;" in code
    m = re.search(r"var METHODS = \[([^\]]*)\]", code)
    assert re.findall(r'"([a-z]+)"', m.group(1)) == HERB_METHODS
    assert all(n.startswith("bench.") for n in re.findall(r'sound\("([^"]+)"', code))


def test_the_reaction_band_is_not_widened_twice():
    """rules/alchemist.py tuning_for widens `reaction.band` by the working traits (a catalyst's
    1.2) before sending it, and ALSO sends `band_scale`. The forge counted narrow_window twice once
    (0.64 where the rule said 0.8); here the frame must use band_scale for the pour and the heat,
    which the server sends unscaled, and never for the reaction."""
    code = _code(_read(FRAME))
    assert 'baseWin * (from === "reaction" ? 1 : bandScale)' in code


def test_the_gauges_are_drawn_as_gauges():
    """The herb Mix lesson (2026-10-06): the owner traced a wavy texture line, believing it was
    the path, because a decoration looked like the input. Every alchemy gauge is a straight bar
    with the band outlined and notched (targetBand), the danger cross-hatched with a saw edge
    (dangerZone), a needle with a keel (needle) and its zones named in words (gaugeNames)."""
    code = _code(_read(FRAME))
    for fn in ("drawFlameGauge", "drawReaction", "drawStageTrack"):
        body = code[code.index("function " + fn):]
        body = body[:body.index("\n  }\n")]
        assert "gaugeNames(" in body, fn
        if fn != "drawStageTrack":
            assert "targetBand(" in body and "dangerZone(" in body and "needle(" in body, fn
        else:
            assert "KIT.notch(" in body and "barBand(" in body, fn
    # The reduced-motion track stands still: its needle is drawn only without reduced motion.
    assert "if (!r.reduced && T.now >= T.start && T.now <= T.end) needle(" in code


# --- behaviour, in node ------------------------------------------------------------------------

_DRIVER = r"""// Node driver for tests/test_alchemy_games.py: loads the frame and every game (herb, forge,
// enchant, alchemy) into a bare sandbox and plays each alchemy game through `BenchGames.simulate`,
// the frame's own headless path (the same per-frame `advance` as the strip's loop). Every frame
// the game's draw runs on a stub canvas, so a draw that throws fails the run. Bots read only
// the state a game hands the stage (and the reaction gauge the frame draws), so a bot that wins
// proves the game can be won from what it shows. One JSON object comes out.
"use strict";
const fs = require("fs"), vm = require("vm");
const files = JSON.parse(process.argv[2]);
const sandbox = { window: {}, Math, JSON, Object, Array, Promise, console, performance: { now: () => 0 } };
sandbox.window.window = sandbox.window;
vm.createContext(sandbox);
for (const f of files) vm.runInContext(fs.readFileSync(f, "utf8"), sandbox);
const W = sandbox.window, BG = W.BenchGames;
const DT = 1 / 60;
const ALCHEMY = ["dissolve", "calcine", "filter", "distill", "react", "sublime", "bottle", "transmute"];
const stub = new Proxy({}, {
  get(t, k) {
    if (k === "measureText") return (s) => ({ width: String(s).length * 6.5 });
    if (k === "createLinearGradient") return () => ({ addColorStop() {} });
    if (k in t) return t[k];
    return () => {};
  },
  set(t, k, v) { t[k] = v; return true; }
});
// The server's tuning, exactly as rules/alchemist.py tuning_for builds it from alchemist.json
// (the Python side passes the real ones in as argv[3]; these are the fallback for a hand run).
const TUNING = process.argv[3] ? JSON.parse(process.argv[3]) : {};

function sim(method, o) {
  o = o || {};
  const tuning = Object.assign({}, TUNING[method] || {}, { seed: 5 }, o.tuning || {});
  return BG.simulate(Object.assign({ method, tuning }, o.steady ? { steady: true } : {}, o.opts || {}));
}

// A hand: presses and holds keys and the pointer, remembering what it holds, so a bot can ask
// for a state ("feeding") and the hand does whatever it takes in this mode.
function hand(s) {
  const held = {};
  return {
    tap(key) { s.press(key); if (!s.ctx.steady) s.release(key); },
    hold(key, on) {
      if (on && !held[key]) { s.press(key); held[key] = true; }
      else if (!on && held[key]) { s.release(key); held[key] = false; }
    },
    // A wanted on/off input that is a hold normally and a toggle in Steady: `is` is the game's
    // own state (fed, pouring), so a Steady toggle is pressed only when it must change.
    want(key, on, is) {
      if (s.ctx.steady) { if (on !== is) s.press(key); return; }
      this.hold(key, on);
    },
    click(x, y) { s.pointer("down", x, y); s.pointer("up", x, y); },
    pdown(x, y) { s.pointer("down", x, y); },
    pup(x, y) { s.pointer("up", x, y); },
  };
}

// --- perfect bots (keyboard) ------------------------------------------------------------------
const mid = (b) => (b[0] + b[1]) / 2;
function fire(s, io, st, aim, key, mouse) {
  const on = st.heat_c < aim;
  if (mouse) {
    if (s.ctx.steady) { if (on !== st.fed) io.click(260, 30); }
    else if (on && !st.fed) io.pdown(260, 30);
    else if (!on && st.fed) io.pup(260, 30);
    return;
  }
  io.want(key || "ArrowUp", on, st.fed);
}
const PERFECT = {
  calcine: (s, io, m) => { const st = s.game.state(); fire(s, io, st, mid(st.band), "ArrowUp", m); },
  sublime: (s, io, m) => {
    const st = s.game.state(); fire(s, io, st, mid(st.band), "ArrowUp", m);
    if (st.ready) { if (m && st.crustAt) io.click(st.crustAt.x, st.crustAt.y); else io.tap("S"); }
  },
  distill: (s, io, m) => {
    const st = s.game.state();
    fire(s, io, st, mid(st.band) - 1.5, "ArrowUp", m);
    if (st.swapping) return;
    const want = st.heads_left > 0.22 ? "jar" : !st.spent ? "flask" : "jar";
    if (want !== st.under) {
      if (m && st.jarAt) { const b = want === "jar" ? st.jarAt : st.flaskAt; io.click(b.x, b.y - 4); }
      else io.tap("Space");
    }
  },
  dissolve: (s, io, m) => {
    const st = s.game.state();
    if (st.lands < mid(st.band)) {
      if (m) { const c = st.centre; io.click(c.x + (st.next === "ArrowLeft" ? -10 : 10), c.y); }
      else io.tap(st.next);
    }
  },
  react: (s, io, m) => {
    const st = s.game.state();
    if (st.lands + st.rise <= st.band[1] - 2 && st.lands < mid(st.band)) { if (m) io.click(100, 40); else io.tap("Space"); }
  },
  filter: (s, io, m) => {
    const st = s.game.state(), on = st.rate < mid(st.band);
    if (m) {
      if (s.ctx.steady) { if (on !== st.pouring) io.click(100, 40); }
      else if (on && !st.pouring) io.pdown(100, 40); else if (!on && st.pouring) io.pup(100, 40);
    } else io.want("Space", on, st.pouring);
  },
  bottle: (s, io, m) => {
    const st = s.game.state();
    if (st.phase === "pour") {
      const on = st.level < st.mark;
      if (m) {
        if (s.ctx.steady) { if (on !== st.pouring) io.click(100, 40); }
        else if (on && !st.pouring) io.pdown(100, 40); else if (!on && st.pouring) io.pup(100, 40);
      } else io.want("Space", on, st.pouring);
      return;
    }
    if (st.ring_open && st.lull_ok && Math.abs(st.offset_s) <= DT / 2 + 1e-9) { if (m) io.click(100, 40); else io.tap("Space"); }
  },
  transmute: (s, io, m) => {
    const st = s.game.state();
    if (st.started && Math.abs(st.offset_s) <= DT / 2 + 1e-9) { if (m) io.click(100, 40); else io.tap("Space"); }
  },
};

// The reduced-motion player for the two timing games: hears only the counted beat and presses one
// beat after "1", by the rhythm the marks set. It never reads where anything is, but for Bottle
// it reads the ring's words (gold "Lull coming" or "Still fuming"), which are shown in words.
function rhythm() {
  let last = 0, at = {}, pressedFor = -1;
  return (s, io) => {
    const st = s.game.state(), t = s.t();
    if (st.phase === "pour") { PERFECT.bottle(s, io, false); return; }
    if (st.lull_ok === false) { at = {}; last = 0; return; }
    const key = st.stage != null ? st.stage : Math.round(t / 1.3);
    if (st.beat !== last) { at[st.beat] = t; last = st.beat; }
    if (at[1] != null && at[2] != null && at[3] != null && pressedFor !== key) {
      const beat = at[2] - at[1];
      if (t >= at[3] + beat - DT / 2) { io.tap("Space"); pressedFor = key; at = {}; }
    }
  };
}

function play(method, o) {
  o = o || {};
  const s = sim(method, o);
  const io = hand(s);
  const bot = o.idle ? null : o.bot || PERFECT[method];
  let ended = false, frames = 0;
  while (!ended && frames < 60 * 120) {
    s.game.draw(stub, o.width || 360, 88);
    if (bot) bot(s, io, o.mode === "mouse");
    ended = s.step(DT);
    frames++;
  }
  return Object.assign(s.result(), { seconds: +(frames / 60).toFixed(3), duration: s.game.duration, hint: s.hint() });
}

// --- sloppy hands: a real player, late and loose ------------------------------------------------
// A hand that sees the state `lag` seconds late (a queue of past states), so it overshoots as a
// person does.
function laggy(lag, inner) {
  const q = [];
  return (s, io, m) => {
    q.push({ t: s.t(), st: s.game.state() });
    while (q.length > 1 && q[1].t <= s.t() - lag) q.shift();
    const st = q[0].st;
    inner(s, io, st);
  };
}
// A careless hand on a gauge: content with "somewhere in the band". It starts feeding only when
// the needle nears the band's foot and stops only when it nears the top (10% in from each edge),
// and it sees the needle 0.2s late.
function edges(lag, read, act) {
  let on = false;
  return laggy(lag, (s, io, st) => {
    const v = read(st), b = st.band, w = b[1] - b[0];
    if (v < b[0] + 0.1 * w) on = true; else if (v > b[1] - 0.1 * w) on = false;
    act(s, io, on, st);
  });
}
const SLOPPY = {
  calcine: edges(0.2, (st) => st.heat_c, (s, io, on) => io.want("ArrowUp", on, s.game.state().fed)),
  // The same fire, and each crust scraped late in its window (1.1s after it is ready).
  sublime: edges(0.2, (st) => st.heat_c, (s, io, on, st) => {
    io.want("ArrowUp", on, s.game.state().fed);
    const now = s.game.state();
    if (now.ready && now.ready_for > 1.1) io.tap("S");
  }),
  // Cuts made 0.4s late on each side, the fire held a little loose.
  distill: laggy(0.4, (s, io, st) => {
    const now = s.game.state();
    io.want("ArrowUp", st.heat_c < mid(st.band) - 1, now.fed);
    if (now.swapping) return;
    const want = st.heads_left > 0 ? "jar" : !st.spent ? "flask" : "jar";
    if (want !== now.under) io.tap("Space");
  }),
  // A drop every 0.2s while the needle reads below the band's middle, never looking at where the
  // last drop will land (the hollow mark).
  react: (s, io) => { const st = s.game.state(); if (st.reaction < mid(st.band) && Math.round(s.t() * 60) % 12 === 0) io.tap("Space"); },
  // Stirring by feel: a stroke every 0.3s while below the band's top, 0.25s late.
  dissolve: laggy(0.25, (s, io, st) => { if (st.fizz < st.band[1] - 4 && s.t() % 0.3 < DT) io.tap(s.game.state().next); }),
  filter: edges(0.2, (st) => st.rate, (s, io, on) => io.want("Space", on, s.game.state().pouring)),
  // Over the mark by a fifth of the tolerance, and the seal 180ms late.
  bottle: (s, io) => {
    const st = s.game.state();
    if (st.phase === "pour") { io.want("Space", st.level < st.mark + st.tol * 0.6, st.pouring); return; }
    if (st.ring_open && st.lull_ok && Math.abs(st.offset_s - 0.18) <= DT / 2 + 1e-9) io.tap("Space");
  },
  // Every stage sealed 180ms late.
  transmute: (s, io) => { const st = s.game.state(); if (st.started && Math.abs(st.offset_s - 0.18) <= DT / 2 + 1e-9) io.tap("Space"); },
};

// --- cheats: what a player who will not play scores ---------------------------------------------
const KEYSET = { calcine: ["Space", "ArrowUp"], sublime: ["Space", "ArrowUp", "S"], distill: ["ArrowUp", "Space"],
  dissolve: ["ArrowLeft", "ArrowRight"], react: ["Space"], filter: ["Space"], bottle: ["Space"], transmute: ["Space"] };
function holdAll(keys) { let done = false; return (s, io) => { if (!done) { keys.forEach((k) => s.press(k)); done = true; } }; }
function mash(keys, every) {
  let n = 0;
  return (s, io) => { n++; if (n % every === 0) keys.forEach((k) => { s.press(k); s.release(k); }); };
}
function mashOne(key, every) { let n = 0; return (s, io) => { n++; if (n % every === 0) { s.press(key); s.release(key); } }; }

const out = { methods: BG.methods, alchemy: BG.methodsFor("alchemy"), herb: BG.methodsFor("herb"),
  forge: BG.methodsFor("forge"), enchant: BG.methodsFor("enchant"), games: {} };
for (const m of ALCHEMY) {
  const def = W.BenchGameDefs[m];
  const g = out.games[m] = {
    keys: def.KEYS, holds: def.HOLDS, holds_steady: def.HOLDS_STEADY, sounds: def.SOUNDS || {},
    flame: !!def.FLAME, reaction: !!def.REACTION, stages: !!def.STAGES,
    keys_run: play(m), keys_steady: play(m, { steady: true }),
    mouse: play(m, { mode: "mouse" }), mouse_steady: play(m, { mode: "mouse", steady: true }),
    narrow: play(m, { mode: "mouse", width: 220 }),
    sloppy: play(m, { bot: SLOPPY[m] }),
    idle: play(m, { idle: true }), idle_steady: play(m, { idle: true, steady: true }),
    hold_all: play(m, { bot: holdAll(KEYSET[m]) }),
    mash_all: play(m, { bot: mash(KEYSET[m], 3) }),
    mash_fast: play(m, { bot: mash(KEYSET[m], 1) }),
  };
  g.mash_each = {};
  def.KEYS.forEach((k) => { g.mash_each[k] = play(m, { bot: mashOne(k, 4) }).score; });
  const s = sim(m, { steady: true }); let ups = 0;
  const up = s.game.up; s.game.up = function () { ups++; return up && up.apply(this, arguments); };
  for (const k of def.KEYS) { s.press(k); s.release(k); }
  s.pointer("down", 100, 40); s.pointer("up", 100, 40);
  g.steady_ups = ups;
  // The first moment a player could lose credit by not having acted: for the timing games, the
  // first window's opening; for the gauge games, the time before anything they do can count.
  const s0 = sim(m); g.first = s0.game.state();
}
out.rhythm = { transmute: play("transmute", { bot: rhythm(), opts: { reducedMotion: true } }),
  bottle: play("bottle", { bot: rhythm() }),
  transmute_steady: play("transmute", { bot: rhythm(), steady: true }) };
// What the server sent is what is played.
const fl = (m, o) => sim(m, o).heat;
out.inputs = {
  distill_bands: fl("distill").bands.map((b) => [b.name, +b.lo.toFixed(2), +b.hi.toFixed(2)]),
  distill_target: fl("distill").target,
  calcine_from_opts: fl("calcine", { opts: { heat: { lo: 100, hi: 1000, start: 150, target: "white", bands: [
    { name: "dark", lo: 100, hi: 500 }, { name: "white", lo: 500, hi: 800 }, { name: "slagging", lo: 800, hi: 1000 }] } } }).bands.map((b) => b.name),
  calcine_bad_target: fl("calcine", { opts: { heat: { target: "nowhere", bands: [{ name: "x", lo: 1, hi: 2 }] } } }).target,
  react_band: sim("react").react.band,
  // The server's own catalyst tunings (rules/alchemist.py tuning_for with working ["catalyst"]).
  react_band_catalyst: sim("react", { tuning: TUNING.react_catalyst || {} }).react.band,
  react_server_band_catalyst: (TUNING.react_catalyst || {}).reaction ? TUNING.react_catalyst.reaction.band : null,
  react_from_opts: sim("react", { opts: { reaction: { start: 50, band: [20, 30], rise: 3, settle: 1, flare_at: 60 } } }).react,
  filter_band: sim("filter").react.band,
  filter_band_catalyst: sim("filter", { tuning: TUNING.filter_catalyst || {} }).react.band,
  calcine_band: sim("calcine").heat.band,
  calcine_band_catalyst: sim("calcine", { tuning: TUNING.calcine_catalyst || {} }).heat.band,
  base_win: sim("react").ctx.baseWin,
  bottle_band: sim("bottle").react.band,
  stages_default: sim("transmute", { tuning: { stages: null } }).stages.map((x) => x.name),
  stages_objects: sim("transmute", { opts: { stages: [{ name: "nigredo", window: 2 }, { name: "rubedo", length: 0.5 }] } }).game.track().items.map((i) => [i.name, +(i.e - i.s).toFixed(3), +(i.hw * 2).toFixed(3)]),
  stages_plain: sim("transmute").game.track().items.map((i) => [i.name, +(i.e - i.s).toFixed(3), +(i.hw * 2).toFixed(3)]),
  first_peak: sim("transmute").game.track().items[0].peak,
  first_peak_short: sim("transmute", { tuning: { seconds: 3 } }).game.track().items[0].peak,
  hint_heat: (() => { const s = sim("calcine"); return s.hint(); })(),
  hint_react_low: sim("react").hint(),
  react_text: sim("react").react.text(),
  calcine_text: sim("calcine").heat.text(),
  distill_text: sim("distill").heat.text(),
  herb_and_forge_ignore: ["grind", "steep", "forge", "temper", "bind"].map((m) => {
    const s = BG.simulate({ method: m, tuning: { seed: 5, reaction: { band: [1, 2] }, stages: ["x"] }, reaction: { band: [1, 2] }, stages: ["x"] });
    return [s.react, s.stages, s.ctx.react, s.ctx.stages, s.heat ? !!s.heat.named : null];
  }),
};
// The reaction's flare is counted once per crossing, not once per frame over the line.
{
  const s = sim("react"); s.game.draw(stub, 360, 88);
  for (let i = 0; i < 8; i++) s.press("Space");
  for (let f = 0; f < 120; f++) s.step(DT);
  out.flare_once = { flares: s.react.flares, v: s.react.v };
}
process.stdout.write(JSON.stringify(out));
"""


def _tunings() -> dict:
    """The server's tuning for every method, built by the real `tuning_for` (so a change to
    alchemist.json's numbers is what the bots play), plus the catalyst forms the band checks
    need."""
    from rules import alchemist as al

    out = {m: al.tuning_for(al.AlchemyPlan(method=m)) for m in METHODS}
    for m in ("react", "filter", "calcine"):
        out[f"{m}_catalyst"] = al.tuning_for(al.AlchemyPlan(method=m, working=["catalyst"]))
    return out


@pytest.fixture(scope="module")
def node_run(tmp_path_factory):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    script = tmp_path_factory.mktemp("alchemy") / "driver.js"
    script.write_text(_DRIVER, encoding="utf-8")
    files = ([str(HERB_GAMES / f"{m}.js") for m in HERB_METHODS]
             + [str(FORGE_GAMES / f"{m}.js") for m in FORGE_METHODS]
             + [str(ENCHANT_GAMES / f"{m}.js") for m in ENCHANT_METHODS]
             + [str(_game(m)) for m in METHODS] + [str(FRAME)])
    done = subprocess.run([node, str(script), json.dumps(files), json.dumps(_tunings())],
                          capture_output=True, text=True, encoding="utf-8", timeout=600)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout)


def test_the_alchemy_games_come_by_registration(node_run):
    """Contracts §12: the eight register on the shared registry with `track: "alchemy"`. Measured
    on the live API: herbs first in their fixed order, then the forge's, the enchanter's and the
    alchemist's, and `methodsFor` keeps each bench to its own games."""
    assert node_run["methods"] == HERB_METHODS + FORGE_METHODS + ENCHANT_METHODS + METHODS
    assert node_run["alchemy"] == METHODS
    assert node_run["herb"] == HERB_METHODS and node_run["forge"] == FORGE_METHODS
    assert node_run["enchant"] == ENCHANT_METHODS


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("mode", ["keys_run", "keys_steady", "mouse", "mouse_steady", "narrow"])
def test_a_perfect_run_scores_one(node_run, method, mode):
    """The server maps the score to the tier under the ceiling, so a perfect run that tops out at
    0.95 caps every player a tier low. Measured 2026-10-07 before the fix: Calcine 0.975 and 0.951
    in Steady, React 0.990, Filter 0.988 and 0.971, for nothing but crossing the band's rim on the
    way in (the frame's `credit` now makes the way in free). A bot reading only the game's state
    plays each game by keyboard, by mouse on a 360px and a 220px meter, and in Steady mode where
    no release is heard; each must score 0.99 or better."""
    r = node_run["games"][method][mode]
    assert r["score"] >= 0.99, f"{method} {mode}: {r}"


@pytest.mark.parametrize("method", METHODS)
def test_a_perfect_run_is_short(node_run, method):
    """UI plan §9: "a run of about 6 seconds (proposed)". A mandatory minigame that drags is the
    KCD2 complaint (forge prior art §0 item 5). A clean run ends inside 8s; Transmute's four
    stages take 7.7s, by design the longest (it is the Great Work)."""
    g = node_run["games"][method]
    assert g["keys_run"]["seconds"] <= 8, g["keys_run"]
    assert g["mouse"]["seconds"] <= 8, g["mouse"]


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("mode", ["idle", "idle_steady"])
def test_an_idle_run_scores_nothing(node_run, method, mode):
    """Pressing nothing must not earn a tier: a banked fire never reaches the band, a reaction
    left alone never starts, an unpoured vessel is never sealed, and an unsealed stage is lost."""
    r = node_run["games"][method][mode]
    assert r["score"] == 0, f"{method} {mode}: {r}"


@pytest.mark.parametrize("method", METHODS)
def test_holding_or_mashing_every_key_scores_almost_nothing(node_run, method):
    """The owner's lesson from the herb games: cheating must not score well. Holding every key the
    game listens to for the whole run, mashing them all every third frame (20 a second), every
    frame (60 a second), or mashing any one key four frames apart, must each stay under 0.25, a
    crude result at best. Measured 2026-10-07: every one scores 0 except Filter held (0.08: the
    pour climbs through the band once on its way over the brim), Bottle held (0.04: poured over
    the brim, never sealed) and Distill held (0.20: one swap at the start, then the fire held on;
    the hearts come over smeared with tails at half their rate)."""
    g = node_run["games"][method]
    for mode in ("hold_all", "mash_all", "mash_fast"):
        assert g[mode]["score"] < 0.25, f"{method} {mode}: {g[mode]}"
    for key, score in g["mash_each"].items():
        assert score < 0.25, f"{method}: mashing {key} scored {score}"


def test_sloppy_play_scores_between(node_run):
    """What a careless hand earns, measured 2026-10-07, so the server's tier bands meet a curve
    that separates care from carelessness: a fire tended "somewhere in the band" (fed near the
    foot, banked near the top, seen 0.2s late) scores 0.92 on Calcine and 0.78 on Sublime with each
    crust scraped late; Distill's cuts made 0.4s late 0.88; React dropping every 0.2s without
    watching where the drop lands 0.91; Dissolve stirring by feel 0.91; Filter poured edge to edge
    0.92; Bottle 0.6 of the tolerance over the mark and sealed 180ms off the lull 0.62; Transmute
    sealed 180ms late at every stage 0.73. A change to a curve must move these on purpose."""
    want = {"calcine": (0.85, 0.97), "sublime": (0.65, 0.88), "distill": (0.78, 0.95), "react": (0.8, 0.97),
            "dissolve": (0.8, 0.97), "filter": (0.85, 0.97), "bottle": (0.5, 0.75), "transmute": (0.6, 0.85)}
    for m, (lo, hi) in want.items():
        s = node_run["games"][m]["sloppy"]["score"]
        assert lo <= s <= hi, f"{m} sloppy {s}"


@pytest.mark.parametrize("method", METHODS)
def test_steady_mode_never_hears_a_release(node_run, method):
    """The frame drops every key-up and pointer-up in Steady mode (STEADY-NO-RELEASE), and the
    headless path does the same: the fire, the pour and the rod must have heard nothing."""
    assert node_run["games"][method]["steady_ups"] == 0


def test_reduced_motion_is_played_by_the_counted_beat(node_run):
    """Reduced motion stops the ring and the track's needle, which are the timing. The windows
    must still be reachable: a player who sees only the count ("3", "2", "1", "Now", a mark lit on
    each beat, nothing travelling) and presses one beat after "1" seals every Transmute stage and
    the Bottle's stopper on the lull (Rhythm Heaven is played by cue; its Night Mode on sound
    alone)."""
    r = node_run["rhythm"]
    assert r["transmute"]["score"] >= 0.99, r["transmute"]
    assert r["transmute_steady"]["score"] >= 0.99, r["transmute_steady"]
    assert r["bottle"]["score"] >= 0.99, r["bottle"]


def test_the_first_peak_waits_for_the_player(node_run):
    """The herb Mix lesson: the first segment's clock ran from the first frame, and a player who
    took 1.2s to find the start lost it every time. Transmute's first peak comes at 2.39s with the
    server's 8 seconds and never before 2s however short the run."""
    i = node_run["inputs"]
    assert i["first_peak"] >= 2.0 and i["first_peak_short"] >= 2.0, i


def test_what_the_server_sent_is_what_is_played(node_run):
    """Contracts §12: opts.heat, opts.reaction and opts.stages are the server's; tuning_for puts
    the same on the tuning, so either door works and the opts win. Distill's gauge says heads,
    hearts, tails from the server; a calcining heat sent with other words is drawn with them; a
    target the bands do not name falls back to the game's own (never a band-less gauge)."""
    i = node_run["inputs"]
    assert [b[0] for b in i["distill_bands"]] == ["heads", "hearts", "tails"]
    assert i["distill_target"] == "hearts"
    assert i["calcine_from_opts"] == ["dark", "white", "slagging"]
    assert i["calcine_bad_target"] == "calcining"
    r = i["react_from_opts"]
    assert r["v"] == 50 and r["rise"] == 3 and r["settle"] == 1 and r["flare"] == 60
    assert i["stages_default"] == ["nigredo", "albedo", "citrinitas", "rubedo"]


def test_per_stage_windows_are_honoured(node_run):
    """The contracts promise Transmute "per-stage windows"; alchemist.json today sends plain
    names. Both shapes must play: `{name, length, window}` factors double nigredo's window and
    halve rubedo's length, and plain names all take the defaults."""
    plain = node_run["inputs"]["stages_plain"]
    assert len({(x[1], x[2]) for x in plain}) == 1
    objs = dict((x[0], x[1:]) for x in node_run["inputs"]["stages_objects"])
    assert objs["nigredo"][1] == pytest.approx(plain[0][2] * 2, rel=1e-3)
    assert objs["rubedo"][0] == pytest.approx(objs["nigredo"][0] * 0.5, rel=1e-3)
    assert objs["rubedo"][1] == pytest.approx(plain[0][2], rel=1e-3)


def test_a_catalyst_widens_each_band_once(node_run):
    """A catalyst widens the window by 1.2 (alchemist.json traits). The server folds it into the
    reaction band it sends and sends `band_scale` too; the frame then widens the reaction band
    only by its generous start, while the pour and the heat (sent unscaled) take band_scale."""
    i = node_run["inputs"]
    win = i["base_win"]
    lo, hi = i["react_server_band_catalyst"]
    got = i["react_band_catalyst"]
    assert (got[1] - got[0]) == pytest.approx((hi - lo) * win, rel=1e-6)
    plain, cat = i["filter_band"], i["filter_band_catalyst"]
    assert (cat[1] - cat[0]) == pytest.approx((plain[1] - plain[0]) * 1.2, rel=1e-6)
    plain, cat = i["calcine_band"], i["calcine_band_catalyst"]
    assert (cat[1] - cat[0]) == pytest.approx((plain[1] - plain[0]) * 1.2, rel=1e-6)


def test_a_flare_is_counted_once_per_crossing(node_run):
    """Eight drops at once boil the reaction over and it stays over for two seconds; that is one
    boil-over (0.15 off the score), not 120 (one a frame), which would floor any score at once."""
    assert node_run["flare_once"]["flares"] == 1


def test_the_gauges_speak_in_words_and_numbers(node_run):
    """UI plan §4: every gauge is "a number and a bar as well as a colour", with the band's name in
    words. The fire's number reads to the degree on a still (bands 8 °C wide) and to 5 on a
    crucible; the reaction's number carries its label; the hint names the band and what to do."""
    i = node_run["inputs"]
    assert i["calcine_text"] == "300 °C" and i["distill_text"] == "65 °C"
    assert i["react_text"] == "Reaction 5"
    assert i["hint_heat"] == "Dull: feed the fire"
    assert i["hint_react_low"] == "Calm: add a drop"


def test_other_benches_ignore_the_alchemy_inputs(node_run):
    """A herb, forge or enchant game handed a reaction or stages (a shell passing the whole tuning
    through) gets no reaction gauge, no stage track and no alchemist's fire."""
    for row in node_run["inputs"]["herb_and_forge_ignore"]:
        assert row[:4] == [None, None, None, None] and row[4] in (None, False), row
