"""The herbalism bench's minigames (Lane E): the shared frame in
`play/static/js/table/33-bench-games.js`, the nine games in `play/static/js/bench-games/`, their
stylesheet and the harness at `tools/bench-harness/games.html`.

Most checks here read the files. The last group loads the frame and the games into node (when
node is installed) and drives a game's own `create(ctx)` with no browser, because two of the
promises this lane makes (the stage gets exactly the state shapes of contracts §5.1, and a
Steady-mode hold is really a toggle) are behaviour, and a regex over source would pass a game
that broke them.

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
GAMES = ROOT / "play" / "static" / "js" / "bench-games"
CSS = ROOT / "play" / "static" / "css" / "bench-games.css"
THEME = ROOT / "play" / "static" / "css" / "theme-v2.css"
HARNESS = ROOT / "tools" / "bench-harness" / "games.html"
CONTRACTS = ROOT / "docs" / "herbalism-contracts.md"

METHODS = ["grind", "mix", "brew", "dry", "reduce", "extract", "infuse", "steep", "neutralize"]
TIER_NAMES = ["Crude", "Sound", "Fine", "Superior", "Flawless"]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _code(js: str) -> str:
    """A script without its comments, so a rule named in a comment is not mistaken for code."""
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return "\n".join(ln if "://" in ln else ln.split("//", 1)[0] for ln in js.splitlines())


def _strings(js: str) -> list[str]:
    """Every string literal in a script's code."""
    return [a or b for a, b in re.findall(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'', _code(js))]


def _game(method: str) -> Path:
    return GAMES / f"{method}.js"


def _list(js: str, name: str) -> list[str] | None:
    m = re.search(name + r"\s*:\s*\[([^\]]*)\]", _code(js))
    if not m:
        return None
    return re.findall(r'"([^"]*)"', m.group(1))


def _lane_files() -> list[Path]:
    return [FRAME, CSS, HARNESS] + [_game(m) for m in METHODS]


# --- every method, one game ----------------------------------------------------------------

@pytest.mark.parametrize("method", METHODS)
def test_every_method_has_a_game_file_that_registers_it(method):
    """The frame finds a game by `BenchGameDefs[method]` at play time. A method without a file
    makes `BenchGames.play` reject, and D's bench would roll a success and then have no game to
    show: nine methods in contracts §2, so nine files, each registering under its own id."""
    p = _game(method)
    assert p.exists(), f"no game file for {method}: expected {p.relative_to(ROOT)}"
    code = _code(_read(p))
    assert re.search(r"defs\." + method + r"\s*=\s*\{", code), f"{p.name} does not register defs.{method}"
    assert f'id: "{method}"' in code, f"{p.name} registers under a different id"
    assert re.search(r"create\s*:\s*function\s*\(ctx\)", code), f"{p.name} has no create(ctx)"


def test_the_frame_knows_exactly_the_contracts_methods():
    """The method ids are fixed vocabulary (contracts §2). A frame list that drifted from it
    (a stale `wash`, a missing `neutralize`) would show a picker for a method the engine does not
    have, or hide one it does."""
    m = re.search(r"\*\*Method ids:\*\*(.*?)\n- ", _read(CONTRACTS), re.S)
    assert m, "contracts §2 no longer lists the method ids where this test reads them"
    contract = re.findall(r"`([a-z]+)`", m.group(1))
    frame = re.search(r"var METHODS = \[([^\]]*)\]", _code(_read(FRAME)))
    assert frame, "33-bench-games.js has no METHODS list"
    assert re.findall(r'"([a-z]+)"', frame.group(1)) == contract == METHODS


# --- Steady mode and holds ------------------------------------------------------------------

@pytest.mark.parametrize("method", METHODS)
def test_every_game_handles_steady(method):
    """Steady mode is per game (UI plan §9's Steady column): halved speeds, windows x1.6, holds
    turned to toggles. A game that read none of the Steady inputs would play exactly the same
    with the setting on, which is the Stardew complaint ("physically impossible" for a player
    with a motor disability, docs/herbalism-prior-art.md) left in place behind a switch."""
    code = _code(_read(_game(method)))
    assert re.search(r"ctx\.(steady|win|speed)\b", code), (
        f"{method}.js reads none of ctx.steady, ctx.win, ctx.speed: Steady mode changes nothing")
    assert _list(_read(_game(method)), "HOLDS") is not None, f"{method}.js declares no HOLDS list"


@pytest.mark.parametrize("method", METHODS)
def test_steady_mode_declares_no_hold(method):
    """Potion Craft added Auto Hold after "a significant number of players reported getting
    hand fatigue" holding the mouse to grind and stir (devlog #14). Each game declares the
    inputs it needs HELD in normal mode (`HOLDS`) and in Steady mode (`HOLDS_STEADY`); Steady's
    list must be empty, and every hold named must be a key the game listens for or the pointer,
    so the declaration cannot drift from the input it describes."""
    js = _read(_game(method))
    steady = _list(js, "HOLDS_STEADY")
    assert steady == [], f"{method}.js: HOLDS_STEADY must be declared and empty, found {steady}"
    keys = _list(js, "KEYS") or []
    for h in _list(js, "HOLDS") or []:
        assert h == "pointer" or h in keys, f"{method}.js holds {h!r}, which is not one of its KEYS {keys}"


def test_the_frame_never_hands_a_release_to_a_game_in_steady_mode():
    """The guarantee behind every HOLDS_STEADY = []: in Steady mode no game ever hears a key-up
    or a pointer-up, so a game CAN only answer presses, and a hold is a toggle by construction.
    Every function in the frame that calls `game.up(` must return on `r.steady` before it does;
    one path that forgot (the blur release, say) would let a game keep a Steady player holding."""
    code = _code(_read(FRAME))
    chunks = re.split(r"\n  function ", code)
    callers = [c for c in chunks if "game.up(" in c]
    assert len(callers) >= 3, "expected the key-up, pointer-up and blur paths to reach game.up"
    for c in callers:
        name = c.split("(", 1)[0]
        first_up = c.index("game.up(")
        guard = c.find(".steady")
        assert 0 <= guard < first_up and "return" in c[guard:first_up], (
            f"{name}: calls game.up without first returning in Steady mode")


def test_key_repeat_is_never_a_press():
    """A held key auto-repeats keydown about 30 times a second. Passed through, a hold would
    become mashing, which the Game Accessibility Guidelines name ("avoid repeated inputs") and
    which grind punishes on purpose. The frame drops `e.repeat`."""
    code = _code(_read(FRAME))
    down = code[code.index("function onKeyDown"):code.index("function onKeyUp")]
    assert "if (e.repeat || r.held.keys[key]) return;" in down, down
    assert down.index("e.repeat || r.held") < down.index("r.game.down("), "the repeat check must come first"


# --- one loop, only while playing ------------------------------------------------------------

@pytest.mark.parametrize("method", METHODS)
def test_no_game_runs_its_own_loop_or_listens_for_itself(method):
    """UI plan §10 and §13.6: an idle bench draws zero frames. The frame owns the only
    requestAnimationFrame and stops it on finish, stop and pause (measured in the harness on
    2026-10-02: 196 frames in the first second of play, 0 during a 1s pause, 0 in the 2s after
    the end). A game that scheduled its own frames, timers or listeners would outlive that and
    keep drawing, or keep hearing keys, after the strip was done."""
    code = _code(_read(_game(method)))
    for banned in ("requestAnimationFrame", "setInterval", "setTimeout", "addEventListener"):
        assert banned not in code, f"{method}.js calls {banned}; only the frame may"


def test_the_frame_loop_reschedules_itself_only_while_playing():
    """The one loop must end itself: it checks the phase before anything else and reschedules
    only at its foot, after the done check. A loop that rescheduled unconditionally would run
    forever after the first game, costing GPU while the owner reads."""
    code = _code(_read(FRAME))
    loop = code[code.index("function loop("):code.index("function start(")]
    assert re.search(r'if \(!r \|\| r\.phase !== "play"\)\s*\{[^}]*return;', loop), loop
    assert loop.count("requestAnimationFrame(loop)") == 1
    assert loop.index("finish(r, false); return;") < loop.index("requestAnimationFrame(loop)")


def test_the_frame_exposes_play_stop_pause_and_resume():
    """Contracts §5.2 is D's whole view of this lane: `play`, `stop` (Esc confirmed),
    `pause` and `resume` (window blur and focus). A missing one is a TypeError in D's bench the
    first time the player presses Esc."""
    code = _code(_read(FRAME))
    api = re.search(r"window\.BenchGames = \{(.*?)\};", code, re.S)
    assert api, "33-bench-games.js does not assign window.BenchGames"
    for name in ("play", "stop", "pause", "resume"):
        assert re.search(rf"\b{name}: {name}\b", api.group(1)), f"BenchGames.{name} is missing"


# --- the three laws, copy, assets ------------------------------------------------------------

def test_the_page_never_names_a_tier():
    """The server turns the score into a tier against the character's ceiling (contracts
    §3.4); the page never names one, as no model authors a number. The live band word comes
    only from `tuning.names`, which the server sends, so no tier name may appear as a literal
    in the frame or any game."""
    for p in [FRAME] + [_game(m) for m in METHODS]:
        for s in _strings(_read(p)):
            for name in TIER_NAMES:
                assert not re.search(rf"\b{name}\b", s), f"{p.name} names the tier {name!r} in {s!r}"


def test_no_em_or_en_dashes_anywhere_in_the_lanes_files():
    """UI plan §8 and the design skill's §9.G: zero em-dashes in bench strings. Checked over
    whole files, comments included, because a comment's dash is copied into a string the next
    time someone reuses the sentence."""
    for p in _lane_files():
        text = _read(p)
        for ch, name in (("—", "em-dash"), ("–", "en-dash")):
            assert ch not in text, f"{p.relative_to(ROOT)} has an {name} on line {text[:text.index(ch)].count(chr(10)) + 1}"


def test_no_third_party_script_or_stylesheet():
    """The app bundles no third-party JavaScript on purpose (contracts §0; scene3d.js's header)
    and fetches nothing at runtime. The harness loads only the repo's own files by relative
    path, and no lane script imports, requires or fetches anything."""
    html = _read(HARNESS)
    srcs = re.findall(r'<script[^>]*\bsrc="([^"]+)"', html)
    hrefs = re.findall(r'<link[^>]*\bhref="([^"]+)"', html)
    assert srcs, "the harness loads no scripts?"
    for s in srcs:
        assert s.startswith("../../play/static/js/"), f"the harness loads {s}"
    for h in hrefs:
        assert h.startswith("../../play/static/css/"), f"the harness links {h}"
    assert "//" not in "".join(srcs + hrefs).replace("../", "")
    for p in [FRAME] + [_game(m) for m in METHODS]:
        code = _code(_read(p))
        for banned in ("import ", "require(", "fetch(", "XMLHttpRequest", "http://", "https://", "importScripts"):
            assert banned not in code, f"{p.name} uses {banned!r}"


def test_the_harness_loads_every_game_before_the_frame():
    """Contracts §1: the game files load before 33 (D follows the same order in table.html). The
    frame reads the registry lazily, but a harness that skipped a game would hide it from
    anyone tuning by hand."""
    srcs = re.findall(r'<script[^>]*\bsrc="([^"]+)"', _read(HARNESS))
    games = [s.rsplit("/", 1)[1][:-3] for s in srcs if "/bench-games/" in s]
    assert sorted(games) == sorted(METHODS)
    assert srcs[-1].endswith("table/33-bench-games.js")


def test_the_first_time_card_reads_storage_only_inside_a_try():
    """Storage can be absent or throw (a private window, blocked site data); a throw there would
    kill `play` before the game started. Every localStorage touch in the frame sits in a try,
    under the key the brief names, `pgm.games.seen.<method>`."""
    code = _code(_read(FRAME))
    assert '"pgm.games.seen." + method' in code
    for m in re.finditer(r"localStorage", code):
        before = code[max(0, m.start() - 80):m.start()]
        assert "try {" in before, f"localStorage used outside a try: ...{code[m.start() - 60:m.end() + 30]}"


def test_sounds_go_through_the_bench_bus_and_are_optional():
    """Contracts §5.3: names start with their bus (`bench.`), and every consumer works with no
    `window.Sound` at all. The frame plays hits and misses by method, ticks sparingly, and
    checks for Sound before each call."""
    code = _code(_read(FRAME))
    assert '"bench.hit." + r.def.id' in code and '"bench.miss." + r.def.id' in code
    assert 'sound("bench.tick")' in code
    names = re.findall(r'sound\("([^"]+)"', code)
    assert names and all(n.startswith("bench.") for n in names), names
    assert "window.Sound &&" in code
    for m in METHODS:
        assert "Sound" not in _code(_read(_game(m))), f"{m}.js plays sound itself; the frame does"


@pytest.mark.parametrize("method", METHODS)
def test_every_game_draws_its_zones_with_shape(method):
    """Never colour alone (Game Accessibility Guidelines, vision basic; revamp plan §3): every
    band a game draws is hatched or notched through the shared kit, and every result is a pip
    whose shape (filled, hollow, struck through) carries it. A game drawing only filled
    coloured rectangles would fail in greyscale."""
    code = _code(_read(_game(method)))
    assert re.search(r"k\.(dialBand|barBand|ring|notch|pip)\(", code), (
        f"{method}.js draws no hatched band, notch, ring or pip")


def test_the_stylesheet_uses_theme_tokens_only():
    """The preserve-the-look rule (owner, 2026-09-28): colours come from theme-v2.css's tokens.
    A raw colour in bench-games.css would be a second palette the theme cannot change."""
    css = re.sub(r"/\*.*?\*/", "", _read(CSS), flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css), "bench-games.css has a raw hex colour"
    assert not re.search(r"\b(rgb|rgba|hsl|hsla)\(", css), "bench-games.css has a raw colour function"


def test_the_frames_fallback_colours_are_the_themes_own():
    """The canvas cannot read a CSS variable it was not handed, so the frame reads the tokens
    and keeps fallbacks for a page without the theme. Each fallback must be the theme's own
    value, or a detached strip would draw in colours the theme never had."""
    fb = re.search(r"var FALLBACK = \{(.*?)\};", _read(FRAME), re.S)
    assert fb
    theme = _read(THEME).lower()
    for hexv in re.findall(r"#[0-9a-fA-F]{6}", fb.group(1)):
        assert hexv.lower() in theme, f"fallback {hexv} is not a theme-v2.css value"


# --- behaviour, in node ----------------------------------------------------------------------

_NODE = r"""
const fs = require('fs'), vm = require('vm');
const files = JSON.parse(process.argv[2]);
const sandbox = { window: {}, Math, JSON, Object, Array, Promise, console };
sandbox.window.window = sandbox.window;
vm.createContext(sandbox);
for (const f of files) vm.runInContext(fs.readFileSync(f, 'utf8'), sandbox);
const W = sandbox.window, kit = W.BenchGames.kit;
function ctx(steady) {
  return { method: '', tuning: { names: null }, part: 'leaf', steady, reduced: true, difficulty: 0.5,
    win: 1.1 * (steady ? 1.6 : 1), baseWin: 1.1, speed: steady ? 0.5 : 1, baseSpeed: 1, seconds: 6,
    kit, C: {}, rng: kit.rng(3), seed: 3, pointer: { x: -1, y: -1, inside: false, down: false },
    hit() {}, miss() {}, tick() {} };
}
const out = {};
for (const m of Object.keys(W.BenchGameDefs)) {
  const def = W.BenchGameDefs[m], g = def.create(ctx(true));
  for (let i = 0; i < 30; i++) g.tick(1 / 60, i / 60);
  const s = g.state();
  out[m] = { keys: Object.keys(s), state: s, score: g.score(), duration: g.duration,
             holds: def.HOLDS, keys_: def.KEYS };
}
// Toggles: in Steady mode one press must keep the action going with no release, and the
// next press must stop it. Measured on the value the hold drives.
function run(m, key, read, secs) {
  const g = W.BenchGameDefs[m].create(ctx(true)); let t = 0;
  const step = (s) => { for (let i = 0; i < s * 60; i++) { t += 1 / 60; g.tick(1 / 60, t); } };
  step(0.1); const a = read(g.state());
  g.down({ src: 'key', key }); step(secs); const b = read(g.state());
  g.down({ src: 'key', key }); step(0.05); const c = read(g.state()); step(secs); const d = read(g.state());
  return { before: a, held: b, released: c, after: d };
}
out.toggles = {
  brew: run('brew', 'Space', s => s.heat, 0.6),
  steep: run('steep', 'Space', s => s.fill, 0.6),
  extract: run('extract', 'ArrowRight', s => s.at, 0.6),
};
// Dry: the bundle the player turns is named to the stage with the hit (2026-10-02). Play
// until a bundle is inside its band, turn it by its number key, and keep what ctx heard.
{
  const calls = [], c = ctx(false);
  c.hit = (...a) => calls.push(['hit'].concat(a));
  c.miss = (...a) => calls.push(['miss'].concat(a));
  const g = W.BenchGameDefs.dry.create(c);
  let t = 0, target = -1;
  for (let i = 0; i < 60 * 14 && target < 0; i++) {
    t += 1 / 60; g.tick(1 / 60, t);
    g.state().bundles.forEach((b, j) => {
      if (target < 0 && !b.turned && b.cure >= b.band[0] + 0.02 && b.cure <= b.band[1]) target = j;
    });
  }
  const before = calls.length;
  g.down({ src: 'key', key: String(target + 1) });
  out.dryIndex = { target, calls: calls.slice(before) };
}
process.stdout.write(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def node_run(tmp_path_factory):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    script = tmp_path_factory.mktemp("bench") / "run.js"
    script.write_text(_NODE, encoding="utf-8")
    files = [str(_game(m)) for m in METHODS] + [str(FRAME)]
    done = subprocess.run([node, str(script), json.dumps(files)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout)


def _contract_shapes() -> dict[str, list[str]]:
    """Top-level keys of each GameView state in contracts §5.1's table."""
    text = _read(CONTRACTS)
    shapes = {}
    for m, body in re.findall(r"^\| (\w+) \| `(\{.*\})` \|$", text, re.M):
        # Keys at depth 0: a word followed by a colon, not inside brackets.
        depth, keys = 0, []
        for tok in re.finditer(r"[\[\]{}()]|(\w+)\s*:", body[1:-1]):
            if tok.group(0) in "[{(":
                depth += 1
            elif tok.group(0) in "]})":
                depth -= 1
            elif depth == 0:
                keys.append(tok.group(1))
        shapes[m] = keys
    return shapes


def test_the_contract_table_is_where_this_test_reads_it():
    """If §5.1's table moved or changed format, the shape check below would compare nothing."""
    assert sorted(_contract_shapes()) == sorted(METHODS)


@pytest.mark.parametrize("method", METHODS)
def test_every_game_hands_the_stage_exactly_the_contracts_state(node_run, method):
    """F's stage is built against contracts §5.1 alone. A game that sent `{closing: 0.4}` for
    grind instead of `{ring, struck}`, or left out `turned` on a dry bundle, would leave the
    pestle still and the bundles uncurled with no error anywhere: the stage reads undefined
    and draws nothing. Checked on the real object the game returns, after half a second of play."""
    want = _contract_shapes()[method]
    got = node_run[method]["keys"]
    assert got == want, f"{method}: state keys {got}, contracts §5.1 says {want}"
    s = node_run[method]["state"]
    if method == "dry":
        assert s["bundles"] and sorted(s["bundles"][0]) == ["band", "cure", "turned"]
    for k, v in s.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool) and k not in ("drops", "needle"):
            assert 0 <= v <= 1, f"{method}.{k} = {v}, outside 0..1"
    if method == "neutralize":
        assert -1 <= s["needle"] <= 1


@pytest.mark.parametrize("method", METHODS)
def test_every_game_scores_inside_zero_to_one_and_has_a_length(node_run, method):
    """The server clamps, but a game that returned NaN or 3.2 would light the live band past the
    ceiling while the player watched. About six seconds each (revamp plan §9.3), stretched at
    most to the low teens by Steady's halved speeds."""
    r = node_run[method]
    assert 0 <= r["score"] <= 1
    assert 3 <= r["duration"] <= 16, f"{method} lasts {r['duration']:.1f}s in Steady mode"


@pytest.mark.parametrize("method", ["brew", "steep", "extract"])
def test_a_steady_hold_is_a_toggle(node_run, method):
    """What Steady mode is for, measured on the value each hold drives: one press keeps the fire
    fed (brew), the spirit pouring (steep) or the blade cutting (extract) with no release at all,
    and the next press stops it. Before the toggle form, a Steady player had to hold a key for
    as long as the pour took."""
    t = node_run["toggles"][method]
    assert t["held"] > t["before"] + 0.05, f"{method}: one press did not start it {t}"
    if method == "brew":
        assert t["after"] < t["released"], f"brew: the second press did not bank the fire {t}"
    else:
        assert abs(t["after"] - t["released"]) < 1e-6, f"{method}: the second press did not stop it {t}"


# --- the stage's missing inputs (added 2026-10-02) -------------------------------------------

_MERGE_GAP = ("the stage could not draw Extract's stop points or Reduce's simmer band; both lanes "
              "reported it at merge, 2026-10-02")


def test_extract_hands_the_stage_its_stop_points(node_run):
    """The stage could not draw Extract's stop points or Reduce's simmer band; both lanes
    reported it at merge, 2026-10-02. Extract's state was `{path, at, pace, nicked}`: the four
    nodes the player must stop at lived only in the game, so the 3D cut had nowhere marked to
    stop. The state now carries `nodes`, in the same 0..1 units as `at`, ascending, and they are
    the game's own scoring nodes (0.25, 0.5, 0.75, 0.97), not a copy that could drift."""
    s = node_run["extract"]["state"]
    assert "nodes" in s, _MERGE_GAP
    nodes = s["nodes"]
    assert nodes == sorted(nodes) and len(nodes) == 4, nodes
    assert all(0 < u <= 1 for u in nodes), nodes
    code = _code(_read(_game("extract")))
    assert "var nodes = [0.25, 0.5, 0.75, 0.97];" in code
    assert "nodes: nodes.slice()" in code, "the state must carry the scoring nodes, copied"


def test_reduce_hands_the_stage_its_band_and_scorch(node_run):
    """The stage could not draw Extract's stop points or Reduce's simmer band; both lanes
    reported it at merge, 2026-10-02. Reduce's state was `{level, line, heat}`, so the pan showed
    the level falling and nothing of where the heat should sit. It now carries `band` (the
    simmer notch the score pays for) and `scorch` (where the crust penalty starts), in heat
    units. The scorch sent is the one scored: one constant feeds the crust check, the strip's
    hatched zone and the state."""
    s = node_run["reduce"]["state"]
    assert "band" in s and "scorch" in s, _MERGE_GAP
    lo, hi = s["band"]
    assert 0 <= lo < hi < s["scorch"] <= 1, s
    code = _code(_read(_game("reduce")))
    assert "heat >= SCORCH" in code, "the crust check no longer uses the scorch the stage is sent"
    assert "A(SCORCH)" in code, "the strip's hatched scorch zone no longer uses the same constant"
    assert "band: band.slice(), scorch: SCORCH" in code
    assert "0.9" not in code.replace("var SCORCH = 0.9", ""), "a second copy of the scorch heat"


def test_dry_names_the_bundle_it_hits(node_run):
    """`hit()` had no bundle index, so the stage put each hit's glint on the bundle the LAST
    state showed turning, which is a frame behind the press: the game calls hit() inside the
    key press and only sends the state that says this bundle turned on the next tick, so the
    stage marked the bundle turned before. Measured here: the turned bundle's index travels
    with the hit as its fifth argument."""
    r = node_run["dryIndex"]
    assert r["target"] >= 0, "no bundle reached its band in fourteen seconds"
    assert r["calls"], "turning a bundle in its band reported nothing"
    kind, *args = r["calls"][0]
    assert kind == "hit", r
    assert args[-1] == r["target"], f"the hit named bundle {args[-1]}, the player turned {r['target']}"


def test_the_frame_forwards_the_index_and_keeps_the_old_call():
    """The frame passes a game's index to `stage.hit(s, index)` / `stage.miss(index)`, and when
    a game sends none it makes the old one-argument call, so a stage or fake built against the
    first contract sees exactly what it always did."""
    code = _code(_read(FRAME))
    assert "hit: function (strength, x, y, kind, index)" in code
    assert 'if (typeof index === "number") r.stage.hit(s, index); else r.stage.hit(s);' in code
    assert "miss: function (index)" in code
    assert 'if (typeof index === "number") r.stage.miss(index); else r.stage.miss();' in code
    dry = _code(_read(_game("dry")))
    assert dry.count(", i);") >= 2 and "ctx.miss(i)" in dry
