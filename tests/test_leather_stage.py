"""The leather bench's 3D stage: the hide on the beam or the frame, the vat, the kettle, the seam.

Lane U4 of the leatherworking revamp (docs/leatherworking-ui-plan.md §6.3, §7, §10, §12;
docs/leatherworking-contracts.md §11, §11.1). The stage is play/static/js/tannery-stage/*.js plus
play/static/js/table/57-leather-stage.js (57: the plan's 47 plus ten, because 45-49 and 50-54
now belong to the enchanting and alchemy benches), which leaves one global, window.TanneryStage.
It runs on the herb stage's renderer, maths, meshes, grounds and particles (bench-stage/00-04)
and the forge's node helpers and haft family (forge-stage/01-02), all as they are.

Two kinds of check, as tests/test_alchemy_stage.py has. SOURCE checks pin what a reading of the
code can hold (one requestAnimationFrame, no library, no planets, the contract's methods in both
branches, the stage reads only a piece's drawing keys). BEHAVIOUR checks run the real stage in
node: every real part, with only the WebGL renderer replaced by a fake that counts draw calls
and remembers the index ranges each mesh was drawn with, and the clock, requestAnimationFrame
and timers simulated, so ten idle seconds take milliseconds. There is no JavaScript test runner
in the repo and adding one would be a dependency in an app that bundles none; node is used as
the other stages' tests use it, and the behaviour checks skip without it.
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
PARTS = sorted((JS / "tannery-stage").glob("*.js"))
STAGE = JS / "table" / "57-leather-stage.js"
UI_PLAN = (ROOT / "docs" / "leatherworking-ui-plan.md").read_text(encoding="utf-8")
SKY = (ROOT / "rules" / "sky.py").read_text(encoding="utf-8")
CLASS = json.loads((ROOT / "content" / "world-classes" / "leatherworker.json").read_text(encoding="utf-8"))
PRODUCTS = list(CLASS["bench"]["products"].keys())

FILES = PARTS + [STAGE]
ALL_CODE = {p.name: _code(_src(p)) for p in FILES}
# What the stage loads, in table.html's order: the herb kit's 00-04, the forge's 01-02 (its
# node helpers and families; the heat, smithy and fx files are the forge's own business),
# then the tannery's parts and the adapter.
LOADS = ([p for p in KIT if p.name[:2] in ("00", "01", "02", "03", "04")]
         + [p for p in FORGE if p.name[:2] in ("01", "02")] + PARTS + [STAGE])


# --- no library, no download, no stray glyphs --------------------------------------------

def test_the_parts_are_the_five_the_plan_names():
    """UI plan §7.1: hide, props, pieces, yard, fx, and nothing else."""
    assert [p.name for p in PARTS] == ["00-hide.js", "01-props.js", "02-pieces.js", "03-yard.js", "04-fx.js"]


def test_no_third_party_library_is_referenced():
    """The app bundles no third-party JavaScript (bench-stage/00-math.js records why: an offline
    executable, no CDN), so "the same Three.js the app already ships" is the herb stage's own
    hand-written WebGL1 renderer: there is no three.js in the repo to vendor. Nothing here
    fetches a model or an image either; every prop is built in code."""
    for name, code in ALL_CODE.items():
        assert not re.search(r"\bTHREE\b", code), name + " references THREE"
        assert not re.search(r"\b(import|require)\s*\(", code), name + " loads a module"
        assert not re.search(r"^\s*import\s", code, re.M), name + " uses an ES import"
        assert "http://" not in code and "https://" not in code, name + " fetches from a URL"
        for ext in (".gltf", ".glb", ".png", ".jpg", ".webp", ".ktx", ".obj"):
            assert ext not in code, name + " loads a " + ext + " file"
        assert "new Image(" not in code and "fetch(" not in code, name + " downloads something"


def test_no_hand_written_svg():
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
    """The owner's standing ruling: no planet is named anywhere; the time of day is
    rules/sky.py's phase."""
    words = re.compile(r"planet|\b(mars|venus|jupiter|saturn|mercury|earth)\b|[☉☽♂☿♃♀♄]", re.I)
    for name, code in ALL_CODE.items():
        # "earth" as the herb kit's ground kind ("packed earth") is a floor, not a planet; it
        # is the only string allowed, and only as the ground's name.
        stripped = code.replace('"earth"', '""')
        assert not words.search(stripped), name + ": " + words.search(stripped).group(0)


def test_the_stage_s_phases_are_sky_s():
    """The day's phases in the stage are rules/sky.py's, in its order, each with a tint."""
    want = re.findall(r'"(\w+)"', re.search(r"^PHASES = \(([^)]*)\)", SKY, re.M).group(1))
    code = ALL_CODE[STAGE.name]
    got = re.search(r"var PHASES = \[([^\]]*)\]", code).group(1)
    assert re.findall(r'"(\w+)"', got) == want
    tint = code[code.index("var TINT"):]
    for p in want:
        assert p + ":" in tint[:600], "no tint for " + p


def test_the_reused_parts_are_untouched():
    """Contracts §11: U4 reads bench-stage/ and forge-stage/02-families.js (and the forge's node
    helpers it stands on) and owns only tannery-stage/ and the adapter. Nothing here assigns
    into the herb kit or the forge kit."""
    for name, code in ALL_CODE.items():
        assert not re.search(r"BenchStageKit\s*=", code), name + " assigns the herb kit"
        assert not re.search(r"ForgeStageKit\s*=", code), name + " assigns the forge kit"
        assert not re.search(r"\bK\.(math|mesh|Renderer|ground|Particles|props|tools|supported)\s*=", code), name
        assert not re.search(r"\bF\.(props|geo|families|smithy|heat|fx)\s*=", code), name


def test_mesh_ids_cannot_collide():
    """The renderer keys GPU buffers by mesh id (01-gl.js). Every mesh here comes from K.mesh's
    own counter or the forge's finish/weld (which pass through it); none keeps a counter of its
    own, and no texture is painted here."""
    for name, code in ALL_CODE.items():
        assert "nextId" not in code and "nextTex" not in code, name + " keeps its own id counter"
        assert "getContext(\"2d\")" not in code and "getContext('2d')" not in code, name + " paints a texture"


def test_every_method_the_bench_has_the_stage_has():
    """The twelve methods are leatherworker.json's bench order, and each has an arrangement."""
    code = ALL_CODE[STAGE.name]
    got = re.findall(r'"(\w+)"', re.search(r"var METHODS = \[([^\]]*)\]", code).group(1))
    assert got == CLASS["bench"]["order"], (got, CLASS["bench"]["order"])
    act = code[code.index("var ACT = {"):code.index("var PIECE_KEYS")]
    for m in got:
        assert re.search(r"\b" + m + r": \{", act), m


def test_the_stage_reads_only_a_piece_s_drawing_keys():
    """The hidden-secret rule (leather UI preamble: "an ungraded hide's properties, a
    creature-derived property before Grade, never reaches the page"). The page has the rack
    row; the stage must not become a second way to show what is on it. It keeps a fixed list of
    keys (colour, surface, form, grade, passes, defects, units, plan, tannage) and copies
    nothing else, and no file of the stage names a property, an effect, the "?" count or a
    material's mark (marks are on hold, the owner's 2026-10-08 ruling)."""
    code = ALL_CODE[STAGE.name]
    keys = re.findall(r'"(\w+)"', re.search(r"var PIECE_KEYS = \[([^\]]*)\]", code).group(1))
    assert sorted(keys) == sorted(["material", "color", "surface", "grade", "passes", "defects", "form",
                                   "units", "plan", "tannage_kind", "tannage", "hardened"]), keys
    for name, c in ALL_CODE.items():
        for word in ("effects", "properties", "property", "unknown", "marks", "knowledge", "price"):
            assert not re.search(r"\b" + word + r"\b", c), name + " reads " + word


# --- the contract -----------------------------------------------------------------------

def _contract_methods():
    sec = UI_PLAN[UI_PLAN.index("**The stage interface**"):]
    sig = sec[:sec.index("WebGL every call")]
    return sorted(set(re.findall(r"(\w+)\(", sig)))


def test_tannerystage_exposes_every_contract_method():
    """Every method in UI plan §12 is on window.TanneryStage, in BOTH branches. U1 builds
    against the plan alone; the second branch is taken when the stage's parts failed to load,
    and it must answer the same calls or U1's flat fallback throws instead."""
    methods = _contract_methods()
    assert methods == sorted(["available", "mount", "unmount", "setScene", "setTool", "setWork", "game",
                              "flourish", "productRect", "reducedMotion"]), methods
    code = ALL_CODE[STAGE.name]
    tail = code[code.index("window.TanneryStage = READY"):]
    ready, fallback = tail.split(" : {", 1)
    for m in methods:
        assert re.search(r"\b" + m + r"\s*:", ready), "TanneryStage." + m + " missing"
        assert re.search(r"\b" + m + r"\s*:", fallback), "fallback TanneryStage." + m + " missing"
        line = re.search(r"\b" + m + r"\s*:([^\n]+)", ready).group(1)
        assert "safe(" in line or "try {" in line, m + " is not wrapped against throwing"


def test_gameview_has_the_four_methods_and_heat():
    code = ALL_CODE[STAGE.name]
    game = code[code.index("function game("):code.index("function shake(")]
    for m in ("update", "hit", "miss", "end", "heat"):
        assert re.search(r"\b" + m + r"\s*:", game), "GameView." + m + " missing"
    assert re.search(r"NOGAME\s*=\s*\{\s*update", code)


def test_sounds_are_the_flourishes_only_on_the_leather_bus():
    """Flourish sounds go through one guarded helper, on U6's leather bus (UI plan §11). The
    stage rings ONLY its flourishes; the shell plays leather.open and leather.method.<m>, and
    the games their knives, scrapes, slosh, steam, stitches and stamps. The alchemy stage's
    first draft rang the game's sounds too, so every one sounded twice."""
    code = ALL_CODE[STAGE.name]
    played = sorted(set(re.findall(r'sound\("([^"]+)"', code)))
    assert played == sorted(["leather.tier.up", "leather.flawless", "leather.fail", "leather.land", "leather.grade"]), played
    assert "window.Sound && typeof window.Sound.play" in code
    assert "sound(" not in code[code.index("function game("):code.index("function shake(")]


def test_the_copied_harden_and_tool_edges_are_the_content_s():
    """The stage poses two looks from band edges it copies from leatherworker.json: Tool's
    leather has its colour back by 40 minutes since wetting (the casing band's fail edge), and
    Harden steams from about 50 °C (the target band's floor). The standing rule: a copied number
    is pinned to its source."""
    tool = CLASS["bench"]["methods"]["tool"]["tuning"]["band"]
    harden = CLASS["bench"]["methods"]["harden"]["tuning"]["band"]
    assert tool["fail"][0] == 40
    assert harden["target"][0] == 50
    code = ALL_CODE[STAGE.name]
    assert "1 - v / 40" in code
    assert "(num(c, 20) - 30) / 70" in code   # 30 °C nothing, 50 °C about a third, 100 °C full


# --- render on demand, and stopping when no one can see it -------------------------------

def test_requestanimationframe_only_from_the_dirty_path():
    """One rAF call in the whole stage, inside wake() (marked TANNERY-STAGE-RAF), and frame()
    asks for the next only `if (busy)` (DIRTY-ONLY). wake()'s guard also refuses a hidden bench
    and a background tab."""
    total = sum(len(re.findall(r"requestAnimationFrame\s*\(", c)) for c in ALL_CODE.values())
    assert total == 1, "requestAnimationFrame is called %d times; only wake() may" % total
    raw = _src(STAGE)
    assert 0 < raw.index("function wake()") - raw.index("TANNERY-STAGE-RAF") < 400
    code = ALL_CODE[STAGE.name]
    w = code[code.index("function wake()"):code.index("function frame(")]
    assert "if (S.raf || !S.mounted || S.lost || S.hiddenBox || S.hiddenTab) return;" in w
    f = code[code.index("function frame("):code.index("function tween(")]
    assert re.search(r"if \(busy\) wake\(\);", f)
    for name, c in ALL_CODE.items():
        assert "setInterval(" not in c, name + " polls with setInterval"


def test_there_is_no_flicker_at_all():
    """UI plan §6.3 and §7.4: "No flicker loop, so the idle-zero-frames rule holds without the
    forge's hearth exception." The fire is lit and steady: nothing in the stage varies a light
    with a sine of the clock."""
    for name, c in ALL_CODE.items():
        assert "flick" not in c, name + " has a flicker"


def test_device_pixel_ratio_is_capped_and_context_loss_claimed():
    code = ALL_CODE[STAGE.name]
    r = code[code.index("function resize()"):]
    assert "Math.min(2, window.devicePixelRatio || 1)" in r and "MAX_PIXELS" in r
    lost = code[code.index("function onLost("):code.index("function onRestored(")]
    assert "e.preventDefault()" in lost
    u = code[code.index("function unmount("):code.index("function setScene(")]
    assert "loseContext()" in u and "S.r.dispose()" in u
    assert 'removeEventListener("visibilitychange", onVisibility' in u


def test_the_canvas_takes_no_input_and_only_it_shakes():
    code = ALL_CODE[STAGE.name]
    assert "pointer-events:none;" in code
    sh = code[code.index("function shake("):code.index("function flourish(")]
    assert "cv.style.transform" in sh and "if (!cv || still()) return;" in sh
    for target in ("document.body", "document.documentElement", "S.host.style.transform"):
        assert target not in sh


# --- the running stage, in node ---------------------------------------------------------------

@pytest.fixture(scope="module")
def node():
    exe = shutil.which("node")
    if not exe:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    return exe


_STAGE_NODE = r"""
const fs = require('fs'), vm = require('vm');
const files = JSON.parse(process.argv[2]), mode = process.argv[3], products = JSON.parse(process.argv[4]);
let T = 0;
const timers = [], rafs = [];
let rafCount = 0; const warns = [];
const listeners = { win: {}, doc: {} };
function on(map, k, fn) { (map[k] = map[k] || []).push(fn); }
function off(map, k, fn) { map[k] = (map[k] || []).filter((f) => f !== fn); }
function ctx2d() {
  const base = {
    createImageData: (a, b) => ({ data: new Uint8ClampedArray(a * b * 4) }),
    getImageData: (x, y, a, b) => ({ data: new Uint8ClampedArray(a * b * 4) }),
    createRadialGradient: () => ({ addColorStop() {} }), createLinearGradient: () => ({ addColorStop() {} }),
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
  Sound: { play: (n) => sounds.push(n) },
};
win.window = win;
const sb = { window: win, document: doc, performance: win.performance, Math, JSON, Object, Array, String, Number,
             Float32Array, Uint8Array, Uint8ClampedArray, Uint16Array, Promise, Proxy, isFinite, getComputedStyle: win.getComputedStyle,
             setTimeout: (cb, ms) => { timers.push({ at: T + (ms || 0), cb }); return timers.length; },
             clearTimeout: (id) => { if (timers[id - 1]) timers[id - 1] = null; }, console: win.console };
sb.requestAnimationFrame = win.requestAnimationFrame;
vm.createContext(sb);
for (const f of files) vm.runInContext(fs.readFileSync(f, 'utf8'), sb, { filename: f });
const K = win.BenchStageKit;
let draws = 0, frames = 0, disposed = 0, contexts = 0;
const uploaded = new Set();
let drawn = new Map();
if (mode !== 'nogl') {
  K.supported = () => true;
  K.Renderer = function (cv) {
    this.canvas = cv; this.bufs = {}; this.texs = {}; contexts++; this.draws = 0;
    this.gl = { getExtension: () => ({ loseContext() {} }), isContextLost: () => false };
  };
  K.Renderer.prototype = {
    init() { return true; }, resize(w, h) { this.canvas.width = w; this.canvas.height = h; },
    begin(f) { this.draws = 0; frames++; drawn = new Map(); },
    setBlend() {},
    draw(mesh, m, mat, a, g, range) {
      this.bufs[mesh.id] = 1; if (mat.tex) this.texs[mat.tex.id] = 1; uploaded.add(mesh.id); this.draws++; draws++;
      drawn.set(mesh.id, (drawn.get(mesh.id) || 0) + (range ? range[1] : mesh.idx.length));
    },
    points(d, c) { if (c) { this.draws++; draws++; } },
    dispose() { disposed++; this.bufs = {}; this.texs = {}; }, forgetTexture(rec) { delete this.texs[rec.id]; },
  };
}
const TS = win.TanneryStage;
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
function hostOf(w, h) { const host = el('div'); host.clientWidth = w; host.clientHeight = h; host.appendChild = (c) => { c.parentNode = host; }; host.removeChild = () => {}; return host; }
function fire(map, k) { (map[k] || []).slice().forEach((f) => f()); }
const D = () => TS._debug();
const WOLF = { key: 'r1', material: 'wolf-pelt', name: 'Wolf pelt', color: '#7a6a58', surface: 'fur', form: 'green', units: 1, grade: 2, plan: 'quadruped' };
const PANEL = { material: 'deer-leather', color: '#9a6a40', surface: 'smooth', form: 'panel', tannage_kind: 'bark', units: 0.5 };
const WORK = {
  flense: { hide: WOLF }, salt: { hide: WOLF, salt: { color: '#f0f0ec' } }, tan: { hide: Object.assign({}, WOLF, { form: 'pelt' }), tannin: { material: 'oak-bark', color: '#7a4a24' } },
  curry: { piece: Object.assign({}, PANEL, { form: 'leather' }), oil: { color: '#b08840' } }, cut: { hide: Object.assign({}, WOLF, { form: 'leather', tannage_kind: 'bark' }) },
  stitch: { piece: PANEL, thread: { color: '#e8dcc0' } }, harden: { piece: PANEL }, tool: { piece: PANEL }, dye: { piece: PANEL, dye: { color: '#3a2a60' } },
  laminate: { piece: PANEL }, assemble: { body: Object.assign({}, PANEL, { form: 'plate' }), fastenings: { color: '#b08840', form: 'fitting' } }, grade: { hide: WOLF },
};
const METHODS = ['flense', 'salt', 'tan', 'curry', 'cut', 'stitch', 'harden', 'tool', 'dye', 'laminate', 'assemble', 'grade'];
(async () => {
  const out = { mode };
  if (mode === 'nogl') {
    out.available = TS.available();
    out.mount = await TS.mount(el('div'));
    const calls = [];
    try {
      TS.setScene({ kind: 'town' }); calls.push('setScene');
      calls.push('setTool:' + await TS.setTool('flense'));
      TS.setWork({ product: 'leather armour', pieces: WORK.flense }); calls.push('setWork');
      const g = TS.game('flense'); g.update({ progress: 0.5 }); g.heat(80); g.hit(1); g.miss(); g.end(); calls.push('game');
      calls.push('flourish:' + await TS.flourish('tier'));
      calls.push('rect:' + JSON.stringify(TS.productRect()));
      TS.reducedMotion(true); calls.push('reducedMotion'); TS.unmount(); calls.push('unmount');
    } catch (e) { calls.push('THREW ' + e.message); }
    out.calls = calls; out.rafs = rafCount;
    process.stdout.write(JSON.stringify(out));
    return;
  }
  out.available = TS.available();
  const host = hostOf(1000, 560);
  out.mount = await TS.mount(host);
  // Idle: every scene with every method and its work, after it settles.
  out.idle = {};
  for (const kind of ['kit', 'town', 'owned']) {
    TS.setScene({ kind, biome: 'forest', minute: 21 * 60 });
    for (const m of METHODS) {
      await timed(TS.setTool(m));
      TS.setWork({ product: 'leather armour', base: 'leather armor', pieces: WORK[m], quality_index: 2 });
      await advance(1500);
      const c = counters();
      await advance(10000);
      const s = since(c), d = D();
      out.idle[kind + ':' + m] = [s.rafs, s.frames, s.draws, d.raf, d.spot, d.shape];
    }
  }
  // The colour and the surface are the server's.
  TS.setScene({ kind: 'kit', biome: 'forest', minute: 720 });
  await timed(TS.setTool('grade'));
  out.surface = {};
  for (const [surface, form] of [['fur', 'fur'], ['scale', 'leather'], ['smooth', 'leather'], ['feather', 'fur'], ['chitin', 'leather']]) {
    TS.setWork({ pieces: { hide: { material: 'x-' + surface, color: '#806040', surface, form, units: 1 } } }); await advance(50);
    out.surface[surface] = { color: D().color, pattern: D().pattern };
  }
  // The hidden secret: a row's other keys never reach the stage.
  TS.setWork({ pieces: { hide: Object.assign({ effects: [{ type: 'secret-effect' }], properties: ['secret-prop'], unknown: 3, name: 'Secret Wolf', price_gp: 99, record: { pieces: {} } }, WOLF) } });
  await advance(50);
  out.secret = JSON.stringify(D().work);
  // Body plans and size.
  out.plans = {};
  for (const plan of ['quadruped', 'long', 'serpent', 'winged', 'carapace', 'nonsense']) {
    TS.setWork({ pieces: { hide: Object.assign({}, WOLF, { plan, material: 'p-' + plan }) } }); await advance(50);
    out.plans[plan] = { plan: D().plan, size: D().size };
  }
  TS.setWork({ pieces: { hide: Object.assign({}, WOLF, { units: 2, material: 'big' }) } }); await advance(50); out.large = D().size;
  TS.setWork({ pieces: { hide: Object.assign({}, WOLF, { units: 0.5, material: 'small' }) } }); await advance(50); out.small = D().size;
  TS.setWork({ pieces: { hide: Object.assign({}, WOLF, { defects: 0.4 }) } }); await advance(50); out.scars = D().scars;
  TS.setWork({ pieces: { hide: Object.assign({}, WOLF, { defects: 0 }) } }); await advance(50); out.noScars = D().scars;
  // Flense: the fat clears as the knife goes; curls fly on a stroke.
  await timed(TS.setTool('flense'));
  TS.setWork({ pieces: WORK.flense }); await advance(100);
  let g = TS.game('flense');
  out.flense = { start: D().fat };
  g.update({ progress: 0.5 }); await advance(32); out.flense.half = D().fat;
  g.hit(1); await advance(32); out.flense.particles = D().particles;
  g.update({ progress: 1 }); await advance(32); out.flense.done = D().fat;
  g.end(); await advance(3000);
  // Cut: the knife follows the chalk.
  await timed(TS.setTool('cut'));
  TS.setWork({ product: 'leather armour', pieces: WORK.cut }); await advance(100);
  g = TS.game('cut'); g.update({ progress: 0 }); await advance(32);
  out.cut = { start: D().cut };
  g.update({ progress: 0.5 }); await advance(32); out.cut.half = D().cut;
  g.update({ progress: 1 }); await advance(32); out.cut.done = D().cut;
  g.end(); await advance(2000);
  // Stitch: in the pony, the seam fills stitch by stitch.
  await timed(TS.setTool('stitch'));
  TS.setWork({ product: 'leather armour', pieces: WORK.stitch }); await advance(100);
  g = TS.game('stitch');
  out.stitch = { spot: D().spot, shape: D().shape };
  g.update({ progress: 0 }); await advance(32); out.stitch.start = D().seam;
  g.update({ stitches: 10 }); await advance(32); out.stitch.ten = D().seam;
  g.end(); await advance(2000);
  // Harden: dipped, it steams; it darkens and shrinks to 7/8.
  await timed(TS.setTool('harden'));
  TS.setWork({ product: 'leather armour', pieces: WORK.harden }); await advance(200);
  out.harden = { spot: D().spot, scale0: D().scale, color0: D().color, dip0: D().dip };
  g = TS.game('harden', { band: { unit: 'celsius', value_start: 20, target: [50, 85] } });
  const st0 = D().steam;
  for (let i = 0; i < 60; i++) { g.update({ value: 80, dipped: true, harden: i / 59 }); await advance(16); }
  out.harden.dip1 = D().dip; out.harden.scale1 = D().scale; out.harden.color1 = D().color; out.harden.steam = D().steam - st0; out.harden.particles = D().particles;
  g.update({ dipped: false }); await advance(400); out.harden.dip2 = D().dip;
  g.end(); await advance(3000);
  // Tan: the pot at the kit, a vat in a yard, the frame for rawhide and alum; the liquor darkens.
  out.tan = {};
  for (const [kind, tannin] of [['kit', 'oak-bark'], ['town', 'oak-bark'], ['town', 'alum-salts'], ['kit', 'rawhide']]) {
    TS.setScene({ kind, biome: 'forest', minute: 720 });
    await timed(TS.setTool('tan'));
    TS.setWork({ pieces: { hide: WORK.tan.hide, tannin: { material: tannin, color: '#7a4a24' } } }); await advance(100);
    out.tan[kind + ':' + tannin] = D().spot;
  }
  TS.setScene({ kind: 'town', biome: 'forest', minute: 720 });
  await timed(TS.setTool('tan'));
  TS.setWork({ pieces: WORK.tan }); await advance(100);
  g = TS.game('tan');
  g.update({ strength: 0 }); await advance(32); const weak = D().liquor;
  g.update({ strength: 1 }); await advance(32); const strong = D().liquor;
  const ct0 = D().cutTest;
  g.update({ cut: 0.6 }); await advance(32);
  out.tanLiquor = { weak, strong, cutBefore: ct0, cutAfter: D().cutTest };
  g.end(); await advance(2000);
  out.sink = await timed(TS.flourish('sink'));
  // Tool: one stamp per strike.
  TS.setScene({ kind: 'kit', biome: 'forest', minute: 720 });
  await timed(TS.setTool('tool'));
  TS.setWork({ product: 'leather armour', pieces: WORK.tool }); await advance(100);
  g = TS.game('tool');
  g.update({ value: 0 }); await advance(32); const wet = D().color;
  for (let i = 0; i < 5; i++) { g.hit(1); await advance(48); }
  g.update({ value: 40 }); await advance(32);
  out.tool = { stamps: D().stamps, wet, dry: D().color };
  g.end(); await advance(2000);
  // Assemble: every product the bench makes builds, without a warning.
  await timed(TS.setTool('assemble'));
  out.products = {};
  for (const p of products) { TS.setWork({ product: p, pieces: WORK.assemble }); await advance(32); out.products[p] = D().shape; }
  // Hidden mid-game: no frame asked for, a flourish still resolves on time, and back it comes.
  await timed(TS.setTool('flense'));
  TS.setWork({ pieces: WORK.flense });
  g = TS.game('flense');
  host.clientWidth = 0; host.clientHeight = 0; fire(listeners.win, 'resize');
  let c = counters();
  for (let i = 0; i < 60; i++) { g.update({ progress: i / 60 }); if (i % 20 === 0) g.hit(1); await advance(16); }
  const hid = await timed(TS.flourish('tier'));
  out.hidden = Object.assign(since(c), { flourish: hid });
  host.clientWidth = 1000; host.clientHeight = 560; fire(listeners.win, 'resize');
  c = counters(); await advance(200); out.shownAgain = since(c);
  g.end(); await advance(3000);
  doc.hidden = true; fire(listeners.doc, 'visibilitychange');
  g = TS.game('flense'); c = counters();
  for (let i = 0; i < 60; i++) { g.update({ progress: 0.3 }); await advance(16); }
  out.background = since(c);
  doc.hidden = false; fire(listeners.doc, 'visibilitychange');
  g.end(); await advance(3000);
  // Reduced motion: nothing flies, states still show.
  TS.reducedMotion(true);
  await timed(TS.setTool('harden'));
  TS.setWork({ product: 'leather armour', pieces: WORK.harden });
  g = TS.game('harden');
  for (let i = 0; i < 40; i++) { g.update({ value: 90, dipped: true, harden: 1 }); if (i % 10 === 0) g.hit(1); await advance(16); }
  out.reduced = { particles: D().particles, dip: D().dip, scale: D().scale };
  g.end(); await advance(500);
  TS.reducedMotion(false); await advance(1000);
  // Flourishes, each from rest.
  out.flourish = {};
  await timed(TS.setTool('grade'));
  for (const k of ['tier', 'flawless', 'land', 'fail', 'sink', 'grade']) {
    TS.setWork({ pieces: { hide: Object.assign({}, WOLF, { material: 'f-' + k }) } });
    await advance(1500);
    out.flourish[k] = await timed(TS.flourish(k));
    await advance(100);
    out.flourish[k].dull = D().dull;
    await advance(2500);
  }
  out.flourish.unknown = await timed(TS.flourish('nonsense'));
  TS.setWork({ pieces: { hide: Object.assign({}, WOLF, { material: 'another' }) } }); out.newWorkDull = D().dull;
  out.tools = {};
  for (const m of METHODS.concat(['forge'])) out.tools[m] = (await timed(TS.setTool(m))).val;
  // The day's phase tints the fill, a little.
  out.tint = {};
  for (const [ph, minute] of [['noon', 720], ['midnight', 0], ['dusk', 1080]]) {
    TS.setScene({ kind: 'kit', biome: 'forest', minute }); await advance(200);
    out.tint[ph] = { fill: D().fill, phase: D().phase };
  }
  // Memory: churn grows nothing, and ten opens and closes leave nothing behind.
  for (const kind of ['kit', 'town']) {
    TS.setScene({ kind, minute: 600 });
    for (const m of METHODS) { await timed(TS.setTool(m)); TS.setWork({ product: 'leather armour', pieces: WORK[m] }); await advance(100); }
  }
  const before = uploaded.size;
  for (let i = 0; i < 48; i++) {
    TS.setScene({ kind: i % 2 ? 'town' : 'kit', minute: 600 });
    const m = METHODS[i % METHODS.length];
    await timed(TS.setTool(m));
    TS.setWork({ product: 'leather armour', pieces: WORK[m] }); await advance(48);
  }
  await advance(500);
  const afterChurn = uploaded.size;
  const cycles = [];
  TS.unmount();
  for (let i = 0; i < 10; i++) {
    await TS.mount(host); TS.setScene({ kind: i % 2 ? 'town' : 'kit', biome: 'forest', minute: 600 });
    await timed(TS.setTool('flense')); TS.setWork({ pieces: WORK.flense });
    await advance(1200);
    cycles.push(uploaded.size);
    TS.unmount();
  }
  out.memory = { before, afterChurn, cycles, disposed, contexts, listeners: { resize: (listeners.win.resize || []).length, vis: (listeners.doc.visibilitychange || []).length }, timersLeft: timers.filter(Boolean).length };
  out.sounds = sounds;
  out.warns = warns;
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
"""


def _run(node, tmp, mode):
    script = tmp / ("stage-" + mode + ".js")
    script.write_text(_STAGE_NODE, encoding="utf-8")
    done = subprocess.run([node, str(script), json.dumps([str(p) for p in LOADS]), mode, json.dumps(PRODUCTS)],
                          capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr[:3000]
    return json.loads(done.stdout)


@pytest.fixture(scope="module")
def run(node, tmp_path_factory):
    return _run(node, tmp_path_factory.mktemp("leather"), "gl")


@pytest.fixture(scope="module")
def nogl(node, tmp_path_factory):
    return _run(node, tmp_path_factory.mktemp("leather"), "nogl")


def test_idle_draws_zero_frames(run):
    """UI plan §7.4: "A test pins zero frames over 10 idle seconds", and there is no flame to
    excuse. Measured with the real stage on a counting renderer: after each arrangement settles,
    ten simulated seconds at the field kit, in a town tannery and in your own, for all twelve
    methods with their work set, ask for 0 frames and issue 0 draw calls; and every method put
    its work somewhere."""
    assert run["available"] is True and run["mount"] is True
    assert len(run["idle"]) == 36
    for key, (rafs, frames, draws, raf, spot, shape) in run["idle"].items():
        assert (rafs, frames, draws, raf) == (0, 0, 0, False), (key, rafs, frames, draws)
        assert spot and shape, key + " shows no work"
    assert run["warns"] == [], run["warns"][:5]


def test_the_hide_s_colour_and_surface_are_the_server_s(run):
    """UI plan §7.2: "Surface from the material's server-sent `surface` and colour." A fur hide
    shows its server colour (through the house shader's 1.6 gamma) with the fine lumps of fur;
    a scale hide coarse lumps; smooth leather the leather grain; feathers the streak; chitin the
    hard mottle. Five surfaces, five looks, one colour."""
    s = run["surface"]
    want = [round((x / 255) ** 1.6, 4) for x in (0x80, 0x60, 0x40)]
    assert s["fur"]["color"] == want, s["fur"]
    assert s["fur"]["pattern"] == 4 and s["scale"]["pattern"] == 4 and s["smooth"]["pattern"] == 6
    assert s["feather"]["pattern"] == 1 and s["chitin"]["pattern"] == 3


def test_a_rack_row_s_secrets_never_reach_the_stage(run):
    """The hidden-secret rule, measured: a rack row sent with effects, properties, a "?" count,
    a name and a price in it was kept by the stage as its drawing keys only; none of those words
    or values is anywhere in what the stage holds."""
    s = run["secret"]
    for word in ("secret-effect", "secret-prop", "Secret Wolf", "effects", "properties", "unknown", "price", "record", "name"):
        assert word not in s, word


def test_each_body_plan_has_its_own_outline_and_size_follows_units(run):
    """UI plan §7.2: an outline per body plan, untagged hides a quadruped, and "a Large pelt
    fills the frame and a Small one sits in its middle". Five plans, five shapes (a serpent's
    hide is long and narrow, a winged hide wider than long); a 2-unit hide is wider than a
    1-unit one, a half-unit one narrower."""
    p = run["plans"]
    assert p["nonsense"]["plan"] == "quadruped"
    assert len({json.dumps(p[k]["size"]) for k in ("quadruped", "long", "serpent", "winged", "carapace")}) == 5
    assert p["serpent"]["size"]["L"] > 3 * p["serpent"]["size"]["W"]
    assert p["winged"]["size"]["W"] > p["winged"]["size"]["L"]
    assert run["large"]["W"] > p["quadruped"]["size"]["W"] > run["small"]["W"]
    assert run["scars"] is True and run["noScars"] is False


def test_flensing_clears_the_flesh_row_by_row(run):
    """UI plan §7.2: "Flensing removes the fur side by side as strokes land" (the fat on the
    flesh side, here). The fat layer is drawn over 40 rows at the start, half of them at
    progress 0.5, none at the end; a stroke throws curls."""
    f = run["flense"]
    assert f["start"] == 2 * f["half"] > 0 and f["done"] == 0, f
    assert f["particles"] > 0


def test_the_knife_follows_the_chalk_and_the_seam_fills(run):
    c, s = run["cut"], run["stitch"]
    assert c["start"] == 0 and 0 < c["half"] < c["done"], c
    assert s["spot"] == "pony" and s["shape"] == "piece" and s["start"] == 0 and s["ten"] > 0, s


def test_harden_dips_steams_darkens_and_shrinks(run):
    """PA §3.5: about 30 s in hot water leaves cuir bouilli at about 7/8 its size, darker and
    hard. The piece went into the kettle (dip 0 to 1) and out again, steamed while in, darkened
    and shrank to 7/8 of its scale."""
    h = run["harden"]
    assert h["spot"] == "kettle" and h["dip0"] in (0, None) and h["dip1"] == 1 and h["dip2"] == 0, h
    assert abs(h["scale1"] / h["scale0"] - 0.875) < 1e-3, h
    assert sum(h["color1"]) < sum(h["color0"]) * 0.8, h
    assert h["steam"] > 0 and h["particles"] > 0


def test_tan_goes_to_the_pot_the_vat_or_the_frame(run):
    """UI plan §6.3: at the kit the brain-tan pot, at a tannery the sunk vat; rawhide and alum
    dry stretched on the frame. The liquor darkens toward the tannin's colour as the strength
    steps up, and Collect's cut test shows only when its state is sent."""
    t = run["tan"]
    assert t["kit:oak-bark"] == "pot" and t["town:oak-bark"] == "vat"
    assert t["town:alum-salts"] == "frame" and t["kit:rawhide"] == "frame"
    lq = run["tanLiquor"]
    assert sum(lq["strong"]) < sum(lq["weak"]), lq
    assert lq["cutBefore"] is False and lq["cutAfter"] is True
    assert run["sink"]["val"] is True and run["sink"]["ms"] <= 800


def test_tool_lays_a_stamp_per_strike_and_the_leather_dries(run):
    t = run["tool"]
    assert t["stamps"] > 0 and sum(t["dry"]) > sum(t["wet"]), t


def test_every_product_has_a_finished_shape(run):
    """Every pattern in leatherworker.json's products builds at Assemble as a piece, without a
    warning (the forge's rule: no item falls back to nothing)."""
    assert set(run["products"]) == set(PRODUCTS)
    assert all(v == "piece" for v in run["products"].values()), run["products"]


def test_a_hidden_bench_and_a_background_tab_draw_nothing(run):
    h = run["hidden"]
    assert (h["rafs"], h["frames"], h["draws"]) == (0, 0, 0), h
    assert h["flourish"]["val"] is True and h["flourish"]["ms"] <= 600, h
    assert run["shownAgain"]["frames"] >= 1
    b = run["background"]
    assert (b["rafs"], b["frames"]) == (0, 0), b


def test_reduced_motion_keeps_the_states_and_drops_the_motion(run):
    """Nothing flies under reduced motion (no steam, no curls), and the states still show at
    once: the piece is in the kettle and shrunk."""
    r = run["reduced"]
    assert r["particles"] == 0 and r["dip"] == 1 and r["scale"] is not None, r


def test_every_flourish_ends_inside_1_1_seconds(run):
    f = run["flourish"]
    for k in ("tier", "flawless", "land", "fail", "sink", "grade"):
        assert f[k]["val"] is True and f[k]["ms"] <= 1100, (k, f[k])
    assert f["unknown"]["val"] is False and f["unknown"]["ms"] <= 32
    assert f["fail"]["dull"] == 1 and run["newWorkDull"] == 0
    for name in ("leather.tier.up", "leather.flawless", "leather.fail", "leather.land", "leather.grade"):
        assert name in run["sounds"], name


def test_every_method_has_an_arrangement(run):
    t = run["tools"]
    assert all(t[m] is True for m in t if m != "forge"), t
    assert t["forge"] is False


def test_the_day_s_phase_tints_the_light_a_little(run):
    t = run["tint"]
    assert t["noon"]["phase"] == "noon" and t["midnight"]["phase"] == "midnight"

    def ratio(f):
        return f[2] / max(1e-6, f[0])
    assert ratio(t["midnight"]["fill"]) > ratio(t["noon"]["fill"])
    assert ratio(t["dusk"]["fill"]) < ratio(t["noon"]["fill"])


def test_open_and_close_ten_times_leaves_nothing_behind(run):
    """Once every method had been arranged at the kit and in a yard, 48 more rounds of
    changing scene, method and work grew the set of distinct meshes by nothing; ten mounts and
    unmounts disposed ten renderers, drew the same mesh set every time, and left no resize or
    visibility listener and no pending timer."""
    m = run["memory"]
    assert m["afterChurn"] == m["before"], m
    assert len(set(m["cycles"])) == 1, m["cycles"]
    assert m["disposed"] >= 10 and m["listeners"] == {"resize": 0, "vis": 0}, m
    assert m["timersLeft"] == 0, m


def test_nothing_throws_without_webgl(nogl):
    """available() is false without WebGL, mount() resolves false, and every other call is a
    quiet no-op (contracts §11.1: "Without WebGL every call is a no-op")."""
    assert nogl["available"] is False and nogl["mount"] is False
    assert not any(c.startswith("THREW") for c in nogl["calls"]), nogl["calls"]
    assert nogl["rafs"] == 0
