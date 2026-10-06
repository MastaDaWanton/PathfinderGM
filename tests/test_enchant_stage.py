"""The enchanting bench's 3D stage: a chalk circle, candles and the essence's glow, on demand.

Lane U3 of the enchanting revamp (docs/enchanting-ui-plan.md §6.3, §7, §10; docs/enchanting-
contracts.md §12-13). The stage is play/static/js/enchant-stage/*.js plus play/static/js/table/
47-enchant-stage.js, which leaves one global, window.EnchantStage. It runs on the herb stage's
renderer, maths, meshes, grounds and particles (bench-stage/00-04) and the forge's node helpers,
weapon families and smithy room (forge-stage/01-03), all as they are.

Two kinds of check, as tests/test_forge_stage.py has. SOURCE checks pin what a reading of the
code can hold (one requestAnimationFrame, no library, no planets, the contract's methods).
BEHAVIOUR checks run the real stage in node: every real part, with only the WebGL renderer
replaced by a fake that counts draw calls and remembers which meshes it was asked to upload, and
the clock, requestAnimationFrame and timers simulated, so ten idle seconds take milliseconds.
There is no JavaScript test runner in the repo and adding one would be a dependency in an app
that bundles none; node is used as the forge's and the herb bench's tests use it, and the
behaviour checks skip without it.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_forge_stage import _code, _src, _strings

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "play" / "static" / "js"
KIT = sorted((JS / "bench-stage").glob("*.js"))
FORGE = sorted((JS / "forge-stage").glob("*.js"))
PARTS = sorted((JS / "enchant-stage").glob("*.js"))
STAGE = JS / "table" / "47-enchant-stage.js"
PLAN = (ROOT / "docs" / "enchanting-ui-plan.md").read_text(encoding="utf-8")
SKY = (ROOT / "rules" / "sky.py").read_text(encoding="utf-8")
WEAPONS = ROOT / "content" / "weapons" / "weapons.json"

FILES = PARTS + [STAGE]
ALL_CODE = {p.name: _code(_src(p)) for p in FILES}
# What the stage loads, in table.html's order: the herb kit's 00-04, the forge's 01-03 (its heat
# table and fx are the forge's own business), then the circle's parts and the adapter.
LOADS = ([p for p in KIT if p.name[:2] in ("00", "01", "02", "03", "04")]
         + [p for p in FORGE if p.name[:2] in ("01", "02", "03")] + PARTS + [STAGE])


# --- no library, no download, no stray glyphs --------------------------------------------

def test_no_third_party_library_is_referenced():
    """The app bundles no third-party JavaScript (bench-stage/00-math.js records why: an offline
    executable, no CDN); the packaged app could not load one. The circle's dust and the floors
    are painted in code, so nothing here may fetch an image either."""
    for name, code in ALL_CODE.items():
        assert not re.search(r"\bTHREE\b", code), name + " references THREE"
        assert not re.search(r"\b(import|require)\s*\(", code), name + " loads a module"
        assert not re.search(r"^\s*import\s", code, re.M), name + " uses an ES import"
        assert "http://" not in code and "https://" not in code, name + " fetches from a URL"
        for ext in (".gltf", ".glb", ".png", ".jpg", ".webp", ".ktx"):
            assert ext not in code, name + " loads a " + ext + " file"
        assert "new Image(" not in code and "fetch(" not in code, name + " downloads something"


def test_no_hand_written_svg():
    """Icons and art are not hand-drawn SVG; the stage is WebGL and painted textures."""
    for p in FILES:
        text = _src(p).lower()
        assert "<svg" not in text and "createelementns" not in text and "2000/svg" not in text, p.name


def test_no_em_dashes_in_strings():
    """No em-dash or en-dash in any string the stage carries (UI plan §8)."""
    for name, code in ALL_CODE.items():
        for a, b in _strings(code):
            s = a or b
            assert chr(0x2014) not in s and chr(0x2013) not in s, name + " string: " + s[:60]


def test_there_are_no_planets():
    """The owner's ruling (answers round 4, point 10): "this is not earth", and named planets
    would not be world-agnostic, so the favourable time is the day's phase. The UI plan §7.1 was
    written before the ruling and names `planet` in setSeats and hour(); the first draft of this
    stage carried that word through from the plan. No planet, by name or by sign, anywhere in
    the stage's code or strings."""
    words = re.compile(r"planet|\b(mars|venus|jupiter|saturn|mercury)\b|[☉☽♂☿♃♀♄]", re.I)
    for name, code in ALL_CODE.items():
        assert not words.search(code), name + ": " + words.search(code).group(0)


def test_the_stage_s_phases_are_sky_s():
    """The day's phases in the stage are rules/sky.py's, in its order (round 5 added
    afternoon so no hour past one is called noon). A stage with six phases would tint 15:00 as
    noon while the strip said afternoon."""
    sky = re.search(r"^PHASES = \(([^)]*)\)", SKY, re.M).group(1)
    want = re.findall(r'"(\w+)"', sky)
    got = re.search(r"var PHASES = \[([^\]]*)\]", ALL_CODE[STAGE.name]).group(1)
    assert re.findall(r'"(\w+)"', got) == want
    tint = ALL_CODE[STAGE.name][ALL_CODE[STAGE.name].index("var TINT"):]
    for p in want:
        assert p + ":" in tint[:600], "no tint for " + p


def test_the_reused_parts_are_untouched():
    """Contracts §12: U3 reads bench-stage/ and forge-stage/ and owns only enchant-stage/ and 47.
    Nothing here assigns into the herb kit or the forge kit, so loading the enchanter cannot
    change either other bench."""
    for name, code in ALL_CODE.items():
        assert not re.search(r"BenchStageKit\s*=", code), name + " assigns the herb kit"
        assert not re.search(r"ForgeStageKit\s*=", code), name + " assigns the forge kit"
        assert not re.search(r"\bK\.(math|mesh|Renderer|ground|Particles|props|tools|supported)\s*=", code), name
        assert not re.search(r"\bF\.(props|geo|families|smithy|heat|fx)\s*=", code), name


def test_mesh_and_texture_ids_cannot_collide():
    """The renderer keys GPU buffers by mesh id and textures by record id (01-gl.js). Every mesh
    here comes from K.mesh (its own counter); the painted chalk dust counts from 9501, above the
    forge's smithy textures (9001 up) and the herb grounds (1 up)."""
    for name, code in ALL_CODE.items():
        assert "nextId" not in code, name + " keeps its own mesh id counter"
    assert "nextTex = 9501" in ALL_CODE["00-circle.js"]


def test_the_runes_are_the_elder_futhark_s_twenty_four():
    """UI plan §7.1: sigils from a fixed rune set (the Elder Futhark, public domain), never drawn
    by the player. Twenty-four shapes, every stroke inside its unit box."""
    code = ALL_CODE["00-circle.js"]
    block = code[code.index("var RUNES = ["):code.index("function strokePart")]
    rows = [ln for ln in block.splitlines() if ln.strip().startswith("[[[")]
    assert len(rows) == 24
    for ln in rows:
        for u, v in re.findall(r"\[(-?[\d.]+), (-?[\d.]+)\]", ln):
            assert -0.5 <= float(u) <= 0.5 and 0 <= float(v) <= 1, ln


# --- the contract -----------------------------------------------------------------------

def _plan_methods():
    sec = PLAN[PLAN.index("Adapter `47-enchant-stage.js`"):]
    sig = sec[sec.index("`available()"):sec.index("Without WebGL")]
    return sorted(set(re.findall(r"(\w+)\(", sig)))


def test_enchantstage_exposes_every_plan_method():
    """Every method in the UI plan §7.1 is on window.EnchantStage, in BOTH branches. U1 builds
    against the plan alone; the second branch is the one taken when the stage's parts failed to
    load, and it must answer the same calls or U1's flat fallback throws instead."""
    methods = _plan_methods()
    assert methods == sorted(["available", "mount", "unmount", "setScene", "setTool", "setVessel", "setSeats",
                              "hour", "game", "flourish", "productRect", "reducedMotion"]), methods
    code = ALL_CODE[STAGE.name]
    tail = code[code.index("window.EnchantStage = READY"):]
    ready, fallback = tail.split(" : {", 1)
    for m in methods:
        assert re.search(r"\b" + m + r"\s*:", ready), "EnchantStage." + m + " missing"
        assert re.search(r"\b" + m + r"\s*:", fallback), "fallback EnchantStage." + m + " missing"


def test_gameview_has_the_four_methods():
    """game(method) returns {update, hit, miss, end}, the GameView both other stages hand
    33-bench-games.js, and an inert one when anything goes wrong."""
    code = ALL_CODE[STAGE.name]
    game = code[code.index("function game("):code.index("function flourish(")]
    for m in ("update", "hit", "miss", "end"):
        assert re.search(r"\b" + m + r"\s*:", game), "GameView." + m + " missing"
    assert re.search(r"NOGAME\s*=\s*\{\s*update", code)


def test_sounds_are_played_guarded_on_the_enchant_bus():
    """Flourish sounds go through one guarded helper on U6's enchant bus (UI plan §11) with the
    phase, never a planet (contracts §13 as corrected); Sound may be absent."""
    code = ALL_CODE[STAGE.name]
    for name in ('"enchant.tier.up"', '"enchant.flawless"', '"enchant.flawed"', '"enchant.fail"', '"enchant.land"'):
        assert "sound(" + name in code, "never plays " + name
    assert "window.Sound && typeof window.Sound.play" in code
    assert "Sound.play(" not in code.replace("window.Sound.play(name, opts)", "")
    assert re.search(r"var ph = \{ phase:", code)


# --- render on demand, and stopping when no one can see it -------------------------------

def test_requestanimationframe_only_from_the_dirty_path():
    """One rAF call in the whole stage, inside wake() (marked ENCHANT-STAGE-RAF), and frame()
    asks for the next only `if (busy)` (DIRTY-ONLY). wake()'s guard also refuses a hidden bench
    and a background tab: the forge's guard did not, and a canvas inside a display:none layer
    keeps drawing at full rate if anything wakes it."""
    total = sum(len(re.findall(r"requestAnimationFrame\s*\(", c)) for c in ALL_CODE.values())
    assert total == 1, "requestAnimationFrame is called %d times; only wake() may" % total
    raw = _src(STAGE)
    assert 0 < raw.index("function wake()") - raw.index("ENCHANT-STAGE-RAF") < 400
    code = ALL_CODE[STAGE.name]
    w = code[code.index("function wake()"):code.index("function frame(")]
    assert "requestAnimationFrame(frame)" in w
    assert "if (S.raf || !S.mounted || S.lost || S.hiddenBox || S.hiddenTab) return;" in w
    f = code[code.index("function frame("):code.index("function tween(")]
    assert "DIRTY-ONLY" in raw[raw.index("function frame("):raw.index("function tween(")]
    assert re.search(r"if \(busy\) wake\(\);", f)
    for name, c in ALL_CODE.items():
        assert "setInterval(" not in c, name + " polls with setInterval"


def test_visibility_is_listened_for_and_let_go():
    """The tab's visibility (Page Visibility API) is listened for on mount and the listener is
    removed on unmount, so ten opens do not leave ten listeners behind."""
    code = ALL_CODE[STAGE.name]
    m = code[code.index("function mount("):code.index("function unmount(")]
    u = code[code.index("function unmount("):code.index("function setScene(")]
    assert 'addEventListener("visibilitychange", onVisibility' in m
    assert 'removeEventListener("visibilitychange", onVisibility' in u
    assert "loseContext()" in u and "S.r.dispose()" in u


def test_the_flicker_is_gated_on_a_live_game():
    """The flicker is computed only inside liveStep, called only while a game sends states."""
    code = ALL_CODE[STAGE.name]
    step = code[code.index("function step("):code.index("function liveStep(")]
    assert "if (isLive(t))" in step and "liveStep(dt, t / 1000)" in step and "S.flick = 1;" in step
    assert re.search(r"return S\.gameOn && \(t - S\.gameLast\) < 300", code)
    assert code.count("S.flick = 1 + ") == 1


def test_device_pixel_ratio_is_capped_at_two():
    """DPR-aware, capped at 2 and again at 4K worth of pixels, as both other stages."""
    r = ALL_CODE[STAGE.name][ALL_CODE[STAGE.name].index("function resize()"):]
    assert "Math.min(2, window.devicePixelRatio || 1)" in r and "MAX_PIXELS" in r


def test_context_loss_is_claimed():
    """webglcontextlost is preventDefault-ed (Khronos HandlingContextLost)."""
    code = ALL_CODE[STAGE.name]
    lost = code[code.index("function onLost("):code.index("function onRestored(")]
    assert "e.preventDefault()" in lost


def test_the_canvas_takes_no_input_and_only_it_shakes():
    """The one-second rule (UI plan §10): the canvas has pointer-events: none, and the Flawless
    shake is a transform on the stage canvas alone."""
    code = ALL_CODE[STAGE.name]
    assert "pointer-events:none;" in code
    fl = code[code.index("function flourish("):code.index("function land(")]
    assert "cv.style.transform" in fl
    for target in ("document.body", "document.documentElement", "S.host.style.transform"):
        assert target not in fl


def test_reduced_motion_is_asked_the_device_s_way():
    """Reduced motion is the OS setting OR the player's Short flourishes OR reducedMotion(true),
    asked as 13-device.js's still() asks it; the emitter, the flicker and the shake all ask."""
    code = ALL_CODE[STAGE.name]
    st = code[code.index("function still()"):code.index("function Springs(")]
    assert "prefers-reduced-motion: reduce" in code and 'get("flourishes") === "short"' in st and "S.reduced" in st
    emit = code[code.index("emit: function"):code.index("function glowLight(")]
    assert "if (still()" in emit
    assert "if (!quiet)" in code[code.index('kind === "flawless"'):code.index('kind === "bind"')]


# --- the running stage, in node ---------------------------------------------------------------

@pytest.fixture(scope="module")
def node():
    exe = shutil.which("node")
    if not exe:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    return exe


_STAGE_NODE = r"""
const fs = require('fs'), vm = require('vm');
const files = JSON.parse(process.argv[2]), mode = process.argv[3], rows = JSON.parse(fs.readFileSync(process.argv[4], 'utf8')).weapons;
let T = 0;
const timers = [], rafs = [];
let rafCount = 0, warns = [];
const listeners = { win: {}, doc: {} };
function on(map, k, fn) { (map[k] = map[k] || []).push(fn); }
function off(map, k, fn) { map[k] = (map[k] || []).filter((f) => f !== fn); }
function ctx2d() {
  const base = {
    createImageData: (a, b) => ({ data: new Uint8ClampedArray(a * b * 4) }),
    getImageData: (x, y, a, b) => ({ data: new Uint8ClampedArray(a * b * 4) }),
    createRadialGradient: () => ({ addColorStop() {} }),
  };
  return new Proxy(base, { get: (t, k) => (k in t ? t[k] : () => {}), set: () => true });
}
function el(tag) {
  return {
    tag, style: {}, width: 0, height: 0, parentNode: null, className: '',
    setAttribute() {}, addEventListener() {}, removeEventListener() {},
    getContext: (type) => (type === '2d' ? ctx2d() : null),
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 1000, height: 560 }),
  };
}
const sounds = [];
const doc = { hidden: false, createElement: el, addEventListener: (k, f) => on(listeners.doc, k, f), removeEventListener: (k, f) => off(listeners.doc, k, f) };
const win = {
  performance: { now: () => T },
  requestAnimationFrame: (cb) => { rafCount++; rafs.push(cb); return rafs.length; },
  cancelAnimationFrame: () => { rafs.length = 0; },
  devicePixelRatio: 1,
  addEventListener: (k, f) => on(listeners.win, k, f), removeEventListener: (k, f) => off(listeners.win, k, f),
  getComputedStyle: () => ({ position: 'relative' }),
  console: { warn: (...a) => warns.push(a.join(' ')), log() {} },
  Sound: { play: (n, o) => sounds.push([n, o && o.phase]) },
};
win.window = win;
const sb = { window: win, document: doc, performance: win.performance, Math, JSON, Object, Array,
             Float32Array, Uint8Array, Uint8ClampedArray, Uint16Array, Promise, Proxy, isFinite, getComputedStyle: win.getComputedStyle,
             setTimeout: (cb, ms) => { timers.push({ at: T + (ms || 0), cb }); return timers.length; },
             clearTimeout: (id) => { if (timers[id - 1]) timers[id - 1] = null; }, console: win.console };
sb.requestAnimationFrame = win.requestAnimationFrame;
vm.createContext(sb);
for (const f of files) vm.runInContext(fs.readFileSync(f, 'utf8'), sb, { filename: f });
const K = win.BenchStageKit;
let draws = 0, frames = 0, last = null, disposed = 0, contexts = 0;
const uploaded = new Set();
if (mode !== 'nogl') {
  K.supported = () => true;
  K.Renderer = function (cv) { this.canvas = cv; this.bufs = {}; this.texs = {}; contexts++; this.gl = { getExtension: () => ({ loseContext() {} }), isContextLost: () => false }; this.draws = 0; };
  K.Renderer.prototype = {
    init() { return true; }, resize(w, h) { this.canvas.width = w; this.canvas.height = h; },
    begin(f) { this.draws = 0; frames++; last = f; },
    setBlend() {}, draw(mesh, m, mat) { this.bufs[mesh.id] = 1; if (mat.tex) this.texs[mat.tex.id] = 1; uploaded.add(mesh.id); this.draws++; draws++; },
    points(d, c) { if (c) { this.draws++; draws++; } },
    dispose() { disposed++; this.bufs = {}; this.texs = {}; }, forgetTexture(rec) { delete this.texs[rec.id]; },
  };
}
const ES = win.EnchantStage;
async function flush() { for (let i = 0; i < 4; i++) await Promise.resolve(); }
async function advance(ms) {
  const end = T + ms;
  while (T < end) {
    T += 16;
    for (let i = 0; i < timers.length; i++) { const t = timers[i]; if (t && t.at <= T) { timers[i] = null; t.cb(); } }
    const cbs = rafs.splice(0); cbs.forEach((cb) => cb(T));
    await flush();
  }
}
function counters() { return { rafs: rafCount, draws, frames }; }
function since(c) { const n = counters(); return { rafs: n.rafs - c.rafs, draws: n.draws - c.draws, frames: n.frames - c.frames }; }
async function timed(p) { const t0 = T; let done = false, val; p.then((v) => { done = true; val = v; }); while (!done && T - t0 < 5000) await advance(16); return { ms: T - t0, val }; }
const SWORD = { key: 'stock:sword-1', gear: 'weapon', base: 'longsword', quality_index: 3,
                pieces: { head: { material: 'cold-iron', color: '#5b6066' }, haft: { material: 'ash-haft', color: '#6b4a2b' }, fittings: { material: 'bronze' } } };
const SEATS = [{ seat: 'point', essence: 'Flaming', color: '#d0461c', phase: 'noon', seated: true },
               { seat: 'edge', essence: 'Arcane', color: '#6a5acd', phase: 'midnight', seated: true },
               { seat: 'guard', essence: null, color: null, seated: false }];
function hostOf(w, h) { const host = el('div'); host.clientWidth = w; host.clientHeight = h; host.appendChild = (c) => { c.parentNode = host; }; host.removeChild = () => {}; return host; }
function fire(map, k) { (map[k] || []).slice().forEach((f) => f()); }
(async () => {
  const out = { mode };
  if (mode === 'nogl') {
    out.available = ES.available();
    out.mount = await ES.mount(el('div'));
    const calls = [];
    try {
      ES.setScene({ kind: 'sanctum' }); calls.push('setScene');
      calls.push('setTool:' + await ES.setTool('bind'));
      ES.setVessel(SWORD); calls.push('setVessel');
      ES.setSeats(SEATS); calls.push('setSeats');
      ES.hour({ phase: 'noon', inside: true, minutes_left: 42, widen: 1.5 }); calls.push('hour');
      const g = ES.game('bind'); g.update({ light: 0.5 }); g.hit(1); g.miss(); g.end(); calls.push('game');
      calls.push('flourish:' + await ES.flourish('flawless'));
      calls.push('rect:' + JSON.stringify(ES.productRect()));
      ES.reducedMotion(true); calls.push('reducedMotion'); ES.unmount(); calls.push('unmount');
    } catch (e) { calls.push('THREW ' + e.message); }
    out.calls = calls; out.rafs = rafCount;
    process.stdout.write(JSON.stringify(out));
    return;
  }
  out.available = ES.available();
  const host = hostOf(1000, 560);
  out.mount = await ES.mount(host);
  out.paintMs = ES._debug().paintMs;
  // Idle: every room, a longsword and two essences seated, the candles lit.
  out.idle = {};
  for (const kind of ['camp', 'roofed', 'sanctum', 'hired']) {
    ES.setScene({ kind, biome: 'forest', minute: 21 * 60 });
    await timed(ES.setTool('bind'));
    ES.setVessel(SWORD); ES.setSeats(SEATS);
    await advance(3000);
    const c = counters();
    await advance(10000);
    out.idle[kind] = Object.assign(since(c), { debug: ES._debug() });
  }
  // The open: candles light one by one, then rest.
  ES.unmount(); await ES.mount(host);
  const litSeen = [];
  for (let i = 0; i < 50; i++) { await advance(16); litSeen.push(ES._debug().candles.filter((x) => x >= 1).length); }
  out.open = { litSeen: Array.from(new Set(litSeen)) };
  ES.setScene({ kind: 'camp', biome: 'forest', minute: 21 * 60 });
  ES.setVessel(SWORD); ES.setSeats(SEATS);
  await advance(2000);
  // A live Bind: states every frame for two seconds; the light runs; three good presses.
  await timed(ES.setTool('bind'));
  let g = ES.game('bind');
  let flicks = new Set(), c = counters();
  const pour0 = ES._debug().pour;
  for (let i = 0; i < 125; i++) { g.update({ light: (i % 40) / 40, window: 0.18 }); if (i % 40 === 39) g.hit(0.9); await advance(16); flicks.add(ES._debug().flick.toFixed(4)); }
  out.live = Object.assign(since(c), { flicks: flicks.size, particles: ES._debug().particles, pour: [pour0, ES._debug().pour], glow: ES._debug().glow });
  const stopAt = T; let lastFrame = 0, f0 = frames;
  while (T - stopAt < 6000) { const before = frames; await advance(16); if (frames > before) lastFrame = T - stopAt; }
  out.afterStop = { lastFrameMs: lastFrame, frames: frames - f0 };
  c = counters(); await advance(10000); out.idleAfterGame = since(c);
  g.end(); await advance(1500);
  // Hidden: the bench's box goes to nothing mid-game; no frame is asked for, whatever wakes it.
  g = ES.game('bind');
  host.clientWidth = 0; host.clientHeight = 0; fire(listeners.win, 'resize');
  c = counters();
  for (let i = 0; i < 60; i++) { g.update({ light: i / 60 }); if (i % 20 === 0) g.hit(1); await advance(16); }
  const hid = await timed(ES.flourish('tierUp'));
  out.hidden = Object.assign(since(c), { flourish: hid });
  host.clientWidth = 1000; host.clientHeight = 560; fire(listeners.win, 'resize');
  c = counters(); await advance(200); out.shownAgain = since(c);
  g.end(); await advance(3000);
  // A background tab: the same.
  doc.hidden = true; fire(listeners.doc, 'visibilitychange');
  g = ES.game('bind'); c = counters();
  for (let i = 0; i < 60; i++) { g.update({ light: i / 60 }); await advance(16); }
  out.background = since(c);
  doc.hidden = false; fire(listeners.doc, 'visibilitychange');
  g.end(); await advance(3000);
  // Reduced motion: no flicker, nothing flies.
  ES.reducedMotion(true);
  g = ES.game('bind'); flicks = new Set();
  for (let i = 0; i < 60; i++) { g.update({ light: (i % 30) / 30 }); if (i % 20 === 0) g.hit(1); await advance(16); flicks.add(ES._debug().flick.toFixed(4)); }
  out.reduced = { flicks: flicks.size, particles: ES._debug().particles };
  g.end(); ES.reducedMotion(false); await advance(3000);
  // Prepare: the circle starts empty and draws on, part by part, as the steps are placed.
  await timed(ES.setTool('prepare'));
  const seq = ['chalk', 'salt', 'ink', 'ink', 'focus', 'bell'];
  g = ES.game('prepare'); g.update({ seq, placed: 0 });
  await advance(100);
  out.prepare = { empty: ES._debug().circle };
  g.hit(1, 0); await advance(900); out.prepare.chalk = ES._debug().circle;
  g.hit(1, 1); await advance(600); out.prepare.salt = ES._debug().circle;
  g.hit(1, 2); await advance(900); out.prepare.ink1 = ES._debug().circle;
  g.miss(3); g.hit(1, 3); await advance(900); out.prepare.ink2 = ES._debug().circle;
  g.end(); await advance(2000);
  await timed(ES.setTool('attune'));
  await advance(1500);
  out.prepare.after = ES._debug().circle;
  // Attune: the seats start dull and each lights as it is matched.
  g = ES.game('attune'); g.update({ seats: [{}, {}] }); await advance(300);
  out.attune = { dull: ES._debug().seats };
  g.hit(1, 1); await advance(800); out.attune.one = ES._debug().seats;
  g.end(); await advance(2000);
  // Unbind: the vessel's sigils are picked, the last cut first.
  await timed(ES.setTool('unbind'));
  g = ES.game('unbind'); g.update({ seq: ['sigil', 'sigil', 'enhancement'], picked: 0 });
  g.hit(1, 0); await advance(800); out.unbind = { one: ES._debug().picks };
  g.update({ seq: ['sigil', 'sigil', 'enhancement'], picked: 3 }); await advance(800); out.unbind.all = ES._debug().picks;
  g.end(); await advance(2000);
  // Flourishes, each from rest.
  await timed(ES.setTool('bind'));
  out.flourish = {};
  for (const k of ['tierUp', 'flawless', 'bind', 'fail', 'read', 'identify', 'land', 'flawed']) {
    ES.setVessel(SWORD); ES.setSeats(SEATS);
    await advance(1500);
    const glow0 = ES._debug().glow;
    out.flourish[k] = await timed(ES.flourish(k));
    await advance(2500);
    out.flourish[k].after = { candles: ES._debug().candles, glow0, glow: ES._debug().glow, flawed: ES._debug().flawed };
  }
  out.flourish.unknown = await timed(ES.flourish('nonsense'));
  ES.unmount(); await ES.mount(host); ES.setVessel(SWORD); ES.setSeats(SEATS); await advance(1500);
  out.reopened = ES._debug().candles;
  await timed(ES.setTool('bind')); await timed(ES.flourish('flawed')); await advance(1000);
  ES.setVessel(Object.assign({}, SWORD, { key: 'stock:other' })); await advance(500);
  out.relit = ES._debug().candles;
  // Every method has a tool; an unknown one says no.
  out.tools = {};
  for (const m of ['prepare', 'attune', 'bind', 'refine', 'unbind', 'cleanse', 'read', 'identify', 'forge']) out.tools[m] = (await timed(ES.setTool(m))).val;
  // The day's phase tints the fill, a little.
  out.tint = {};
  for (const [ph, minute] of [['noon', 720], ['midnight', 0], ['dawn', 360], ['dusk', 1080]]) {
    ES.setScene({ kind: 'camp', biome: 'forest', minute }); ES.hour({ phase: ph }); await advance(200);
    out.tint[ph] = { fill: ES._debug().fill, phase: ES._debug().phase };
  }
  ES.hour({ phase: 'noon', now: 'dusk', inside: false }); await advance(100); out.tint.checkHour = ES._debug().phase;
  // The essence's colour is the glow's colour.
  ES.setSeats([{ seat: 'point', color: '#20c040', seated: true }]); await advance(500); out.green = ES._debug().glow;
  ES.setSeats([]); await advance(500); out.noEssence = ES._debug().glow;
  // Every vessel family, and every weapon row, at the heart of the circle without a warning.
  warns = [];
  out.families = {};
  for (const fam of ['ring', 'amulet', 'circlet', 'cloak', 'boots', 'belt', 'gloves', 'bracers']) { ES.setVessel({ gear: 'wondrous', family: fam }); out.families[fam] = ES._debug().family; }
  ES.setVessel({ gear: 'ring', name: 'Ring' }); out.ringGear = ES._debug().vessel;
  ES.setVessel({ gear: 'wondrous', slot: 'shoulders', name: 'Cloak' }); out.cloakSlot = ES._debug().vessel;
  ES.setVessel({ gear: 'armour', base: 'breastplate', pieces: { body: { material: 'mithral' } } }); out.armour = ES._debug().family;
  ES.setVessel({ gear: 'shield', base: 'heavy steel shield' }); out.shield = ES._debug().family;
  const empty = [];
  for (const r of rows) { ES.setVessel({ gear: 'weapon', base: r, quality_index: 3 }); if (!ES._debug().family) empty.push(r.id); }
  await advance(500);
  out.rows = { n: rows.length, empty, warns: warns.slice(0, 5) };
  // Memory: what a mounted stage holds does not grow with churn, and ten opens and closes leave
  // nothing behind (no listener, no context, the same meshes).
  ES.setVessel(SWORD); ES.setSeats(SEATS); await advance(500);
  const before = uploaded.size;
  for (let i = 0; i < 40; i++) { ES.setSeats(i % 2 ? SEATS : SEATS.slice(0, 1)); ES.setVessel(i % 3 ? SWORD : { gear: 'ring', key: 'r' + (i % 3) }); await advance(48); }
  ES.setVessel(SWORD); ES.setSeats(SEATS); await advance(500);
  const afterChurn = uploaded.size;
  const cycles = [];
  ES.unmount();
  for (let i = 0; i < 10; i++) {
    await ES.mount(host); ES.setScene({ kind: i % 2 ? 'sanctum' : 'camp', biome: 'forest', minute: 600 }); ES.setVessel(SWORD); ES.setSeats(SEATS);
    await timed(ES.setTool('bind')); await advance(1200);
    cycles.push(uploaded.size);
    ES.unmount();
  }
  out.memory = { before, afterChurn, cycles, disposed, contexts, listeners: { resize: (listeners.win.resize || []).length, vis: (listeners.doc.visibilitychange || []).length }, timersLeft: timers.filter(Boolean).length };
  out.rect = ES.productRect();
  out.sounds = sounds;
  out.warns = warns;
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
"""


def _run(node, tmp, mode):
    script = tmp / ("stage-" + mode + ".js")
    script.write_text(_STAGE_NODE, encoding="utf-8")
    done = subprocess.run([node, str(script), json.dumps([str(p) for p in LOADS]), mode, str(WEAPONS)],
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr[:3000]
    return json.loads(done.stdout)


@pytest.fixture(scope="module")
def run(node, tmp_path_factory):
    return _run(node, tmp_path_factory.mktemp("enchant"), "gl")


@pytest.fixture(scope="module")
def nogl(node, tmp_path_factory):
    return _run(node, tmp_path_factory.mktemp("enchant"), "nogl")


def test_idle_draws_zero_frames(run):
    """UI plan §7.3: "a test pins zero frames over 10 idle seconds, as both earlier plans",
    candles included. Measured with the real stage on a counting renderer: after the scene
    settles, ten simulated seconds at camp, under a roof, in a sanctum and at a hired circle,
    a longsword and two essences seated, each ask for 0 frames and issue 0 draw calls."""
    assert run["available"] is True and run["mount"] is True
    for kind, r in run["idle"].items():
        assert (r["rafs"], r["frames"], r["draws"]) == (0, 0, 0), (kind, r)
        assert r["debug"]["raf"] is False
    assert run["idle"]["sanctum"]["debug"]["room"] == "sanctum"


def test_the_candles_light_one_by_one_on_open(run):
    """UI plan §10, "Open the bench: the candles light one by one round the circle (600ms)".
    Over the first 800 ms the count of fully lit candles climbs through the values between
    none and all eight, rather than jumping from none to eight."""
    seen = run["open"]["litSeen"]
    assert 8 in seen and len(seen) >= 6, seen


def test_the_candles_flicker_only_while_a_game_is_live(run):
    """The flicker is the one motion that would keep the loop alive for ever, so it runs only
    while a game sends states. Measured: 125 states drew a frame each with the flicker taking
    over twenty values and motes in the air; when they stopped the loop ended inside three
    seconds (the last motes dying), and the ten seconds after drew nothing. Under reduced
    motion the flicker held one value and no particle flew."""
    live = run["live"]
    assert live["frames"] >= 100 and live["flicks"] > 20 and live["particles"] > 0, live
    assert run["afterStop"]["lastFrameMs"] < 3000, run["afterStop"]
    assert run["idleAfterGame"] == {"rafs": 0, "draws": 0, "frames": 0}
    assert run["reduced"] == {"flicks": 1, "particles": 0}, run["reduced"]


def test_a_hidden_bench_and_a_background_tab_draw_nothing(run):
    """The lane's brief: "pause when the bench is hidden or the tab is in the background". The
    forge's wake() asks for a frame whenever anything changes, hidden or not, and a canvas in a
    display:none layer then draws at full rate for nothing. Measured here: a live Bind sending
    60 states and three hits to a bench whose box has no size asked for 0 frames, a flourish
    started while hidden still resolved on time (its timer, not the frame clock), and the first
    frame came back as soon as the box had a size again. The same for a background tab."""
    h = run["hidden"]
    assert (h["rafs"], h["frames"], h["draws"]) == (0, 0, 0), h
    assert h["flourish"]["val"] is True and h["flourish"]["ms"] <= 600, h
    assert run["shownAgain"]["frames"] >= 1
    b = run["background"]
    assert (b["rafs"], b["frames"]) == (0, 0), b


def test_bind_pours_the_essence_into_the_vessel(run):
    """UI plan §9: "press as it crests at the vessel"; a good press pours the essence's light
    into the work, so the glow climbs with each hit (measured from 0 to over 0.4 on three)."""
    pour0, pour1 = run["live"]["pour"]
    assert pour0 == 0 and pour1 > 0.4, run["live"]["pour"]
    g = run["live"]["glow"]
    assert g[0] > g[1] and g[0] > g[2], "the flaming essence's glow is not red"


def test_prepare_draws_the_circle_on_as_it_is_placed(run):
    """UI plan §7.2: "Prepare draws the rings and cuts the sigils one by one, as the order game
    places them". Measured on a six-step sequence: empty at the start; the chalk drew the rings
    and the figure; the salt the heaps; the first of two inks cut 5 of the 9 sigils (rounded
    half) and the second the rest; and moving on to Attune leaves the circle whole."""
    p = run["prepare"]
    assert p["empty"] == {"rings": 0, "fig": 0, "salt": 0, "sig": 0}, p["empty"]
    assert p["chalk"]["rings"] == 1 and p["chalk"]["fig"] == 1 and p["chalk"]["salt"] == 0 and p["chalk"]["sig"] == 0
    assert p["salt"]["salt"] == 1 and p["salt"]["sig"] == 0
    assert 4 <= p["ink1"]["sig"] <= 5 and p["ink2"]["sig"] == 9
    assert p["after"] == {"rings": 1, "fig": 1, "salt": 1, "sig": 9}


def test_attune_lights_each_seat_as_it_is_matched(run):
    """UI plan §7.2: "Attune lights each seat's mark in the essence's colour as it is matched;
    an unmatched seat's mark stays dull chalk"."""
    a = run["attune"]
    assert a["dull"][:2] == [0, 0], a
    assert a["one"][1] > 0.95 and a["one"][0] == 0, a


def test_unbind_picks_the_last_cut_sigil_first(run):
    """UI plan §9, Unbind: "unpick them last-cut first; each unpicked one fades". The three
    sigils of a +1 item with two properties are slots 0-2 of the nine; the first pick fades
    the last cut (slot 2), and three picks fade all three and nothing else."""
    one, all_ = run["unbind"]["one"], run["unbind"]["all"]
    assert one[2] == 0 and one[0] == 1 and one[1] == 1, one
    assert all_[:3] == [0, 0, 0] and all_[3:] == [1] * 6, all_


def test_every_flourish_ends_inside_1_1_seconds(run):
    """The one-second rule (UI plan §10): every flourish ends on its own inside 1.1 s, and an
    unknown one answers false at once."""
    f = run["flourish"]
    for k in ("tierUp", "flawless", "bind", "fail", "read", "identify", "land", "flawed"):
        assert f[k]["val"] is True, (k, f[k])
        assert f[k]["ms"] <= 1100, (k, f[k]["ms"])
    assert f["unknown"]["val"] is False and f["unknown"]["ms"] <= 32
    names = [s[0] for s in run["sounds"]]
    for name in ("enchant.tier.up", "enchant.flawless", "enchant.flawed", "enchant.fail", "enchant.land"):
        assert name in names, name
    assert all(s[1] in ("dawn", "morning", "noon", "afternoon", "dusk", "night", "midnight") for s in run["sounds"]), run["sounds"]


def test_flawed_puts_one_candle_out_and_darkens_the_glow(run):
    """UI plan §7.2: "one candle gutters out and the glow settles a shade darker. It says
    something went wrong without saying what". Seven of eight candles stay lit, the glow drops
    (to 0.62 of what it was), and a new vessel on the circle lights the candle again. Seen live
    in the first draft: closing and reopening the bench on the same vessel kept the candle out;
    a reopened bench now has all eight lit."""
    a = run["flourish"]["flawed"]["after"]
    assert a["flawed"] is True and sorted(a["candles"]).count(0) == 1 and a["candles"].count(1) == 7, a
    assert max(a["glow"]) < 0.75 * max(a["glow0"]), a
    assert run["reopened"].count(1) == 8, run["reopened"]
    assert run["relit"].count(1) == 8


def test_every_method_has_a_tool(run):
    """All eight methods set a tool at the near edge; a method the enchanter has not resolves
    false rather than leaving the stage half-swapped."""
    t = run["tools"]
    assert all(t[m] is True for m in t if m != "forge"), t
    assert t["forge"] is False


def test_the_day_s_phase_tints_the_light_a_little(run):
    """The brief: day phase may tint the light, subtly. Midnight's fill is bluer than noon's
    (blue over red), dusk's warmer, and the phase named NOW wins over the essence's phase in a
    check's hour (lane E sends {phase: the essence's, now, inside})."""
    t = run["tint"]
    assert t["noon"]["phase"] == "noon" and t["midnight"]["phase"] == "midnight"
    def ratio(f):
        return f[2] / max(1e-6, f[0])
    assert ratio(t["midnight"]["fill"]) > ratio(t["noon"]["fill"])
    assert ratio(t["dusk"]["fill"]) < ratio(t["noon"]["fill"])
    assert t["checkHour"] == "dusk"


def test_the_essence_s_colour_is_the_glow_s(run):
    """Lane D's `color` is the essence's light (UI plan §4: essence colour is content, it lives in
    the scene): a green essence casts a green glow, and with no essence seated there is none."""
    g = run["green"]
    assert g[1] > g[0] and g[1] > g[2], g
    assert run["noEssence"] == [0, 0, 0]


def test_every_vessel_reaches_the_circle(run):
    """The forge's weapon, armour and shield families come as they are; the eight jewellery and
    wearable families are the circle's own (UI plan §7.1, 02-vessels.js). Every family builds,
    a ring's gear and a cloak's slot pick their family, and all 456 weapon rows lie at the
    heart of the circle without a warning."""
    assert all(n > 0 for n in run["families"].values()), run["families"]
    assert run["ringGear"].endswith(":ring") and run["cloakSlot"].endswith(":wondrous")
    assert run["armour"] > 0 and run["shield"] > 0
    r = run["rows"]
    assert r["n"] == 456 and r["empty"] == [] and r["warns"] == [], r


def test_open_and_close_ten_times_leaves_nothing_behind(run):
    """The brief: "dispose GPU resources on close (measure memory across open/close cycles)".
    Measured on the counting renderer: 40 rounds of changing vessels and seats grew the set of
    distinct meshes by the ring family's parts once and no more (the first draft built a
    fresh shadow disc per phial, which would have grown the GPU buffer map for as long as the
    bench stayed open); ten mounts and unmounts disposed ten renderers, drew the same mesh set
    every time, and left no resize or visibility listener and no pending timer."""
    m = run["memory"]
    assert m["afterChurn"] - m["before"] <= 12, m
    assert len(set(m["cycles"])) == 1, m["cycles"]
    assert m["disposed"] >= 10 and m["listeners"] == {"resize": 0, "vis": 0}, m
    assert m["timersLeft"] == 0, m


def test_nothing_throws_without_webgl(nogl):
    """available() is false without WebGL, mount() resolves false, and every other call is a
    quiet no-op (contracts §13: "Without WebGL every call is a no-op")."""
    assert nogl["available"] is False and nogl["mount"] is False
    assert not any(c.startswith("THREW") for c in nogl["calls"]), nogl["calls"]
    assert nogl["rafs"] == 0
