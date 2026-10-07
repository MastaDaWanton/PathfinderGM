"""The alchemy bench's 3D stage: glassware with live liquid, a flame that follows the heat, on demand.

Lane U3 of the alchemy revamp (docs/alchemy-ui-plan.md §6.3, §7, §10; docs/alchemy-contracts.md
§11-12). The stage is play/static/js/alchemy-stage/*.js plus play/static/js/table/52-alchemy-
stage.js, which leaves one global, window.AlchemyStage. It runs on the herb stage's renderer,
maths, meshes, grounds, particles and props (bench-stage/00-05) and the forge's node helpers,
sweep, heat colours and smithy room (forge-stage/00-03), all as they are, except for the one
change the contracts give this lane: three liquid uniforms added to bench-stage/01-gl.js.

Two kinds of check, as tests/test_enchant_stage.py has. SOURCE checks pin what a reading of the
code can hold (the shader change is additive, one requestAnimationFrame, no library, no planets,
the contract's methods, the copied heat ranges equal the content's). BEHAVIOUR checks run the
real stage in node: every real part, with only the WebGL renderer replaced by a fake that counts
draw calls and remembers what it uploaded and the fill height each liquid was drawn with, and
the clock, requestAnimationFrame and timers simulated, so ten idle seconds take milliseconds.
There is no JavaScript test runner in the repo and adding one would be a dependency in an app
that bundles none; node is used as the other stages' tests use it, and the behaviour checks skip
without it.
"""
import hashlib
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
PARTS = sorted((JS / "alchemy-stage").glob("*.js"))
STAGE = JS / "table" / "52-alchemy-stage.js"
GL = JS / "bench-stage" / "01-gl.js"
CONTRACTS = (ROOT / "docs" / "alchemy-contracts.md").read_text(encoding="utf-8")
SKY = (ROOT / "rules" / "sky.py").read_text(encoding="utf-8")
CLASS = json.loads((ROOT / "content" / "world-classes" / "alchemist.json").read_text(encoding="utf-8"))
MATERIALS = json.loads((ROOT / "content" / "materials" / "alchemist-materials.json").read_text(encoding="utf-8"))

FILES = PARTS + [STAGE]
ALL_CODE = {p.name: _code(_src(p)) for p in FILES}
# What the stage loads, in table.html's order: the herb kit's 00-05, the forge's 00-03 (its fx
# is the forge's own business), then the glassware's parts and the adapter.
LOADS = ([p for p in KIT if p.name[:2] in ("00", "01", "02", "03", "04", "05")]
         + [p for p in FORGE if p.name[:2] in ("00", "01", "02", "03")] + PARTS + [STAGE])
VESSELS = [m["id"] for m in MATERIALS["materials"] if m.get("kind") == "vessel"]


# --- the shader change is additive, and nothing else sets it ------------------------------

# The sha256 of bench-stage/01-gl.js on build/alchemy before this lane (newlines as \n).
GL_BEFORE = "af4c1f198d3657c747a1f12cc562aa1e5a689eb3ab2a17cc9ce634ad8c1397d2"


def _strip_liquid(text: str) -> str:
    s = text.replace("\r\n", "\n")
    s = re.sub(r"    // The alchemy bench's live liquid.*?\"uniform float uTurbid;\",\n", "", s, flags=re.S)
    s = re.sub(r"    // LIVE LIQUID.*?    \"  if \(uFillY < 5000\.0\) \{\",\n.*?    \"  \}\",\n(?=    \"  vec3 col;\",)",
               "", s, flags=re.S)
    s = s.replace(", fillY: 1e4, surf: [0, 0, 0], turbid: 0", "")
    s = re.sub(r"    // Set on every draw, defaults included.*?gl\.uniform1f\(u\.uTurbid, pick\(mat, \"turbid\"\)\);\n",
               "", s, flags=re.S)
    return s


def test_the_shader_change_is_additive_only():
    """Contracts §11: U3 may change bench-stage/01-gl.js ADDITIVELY ONLY (uFillY, uSurf, uTurbid
    with no-op defaults), because the herb bench, the forge and the circle all draw through it.
    Taking out exactly the four added blocks gives back the file as it was, byte for byte (its
    sha256 before this lane), so nothing else in the renderer moved."""
    assert hashlib.sha256(_strip_liquid(_src(GL)).encode("utf-8")).hexdigest() == GL_BEFORE


def test_the_liquid_branch_is_never_taken_at_its_defaults():
    """The defaults are no-ops: uFillY defaults to 1e4 and the branch runs only below 5000, so
    a material that never names `fillY` (every herb, forge and enchanting one) draws exactly as
    before. 1e4, not the plan's 1e9: mediump floats are only guaranteed to 2^14 (16384), and a
    sentinel past that could read as infinity, or worse, on a mediump-only GPU."""
    code = _code(_src(GL))
    assert '"uniform float uFillY;"' in code and '"uniform vec3 uSurf;"' in code and '"uniform float uTurbid;"' in code
    assert re.search(r"fillY: 1e4, surf: \[0, 0, 0\], turbid: 0 \}", code)
    assert '"  if (uFillY < 5000.0) {",' in code
    assert 1e4 > 5000 and 1e4 < 2 ** 14
    # Set on every draw, so one liquid's fill height cannot leak into the next mesh.
    draw = code[code.index("Renderer.prototype.draw"):code.index("Renderer.prototype.points")]
    for u in ('u.uFillY, pick(mat, "fillY")', 'u.uSurf, pick(mat, "surf")', 'u.uTurbid, pick(mat, "turbid")'):
        assert u in draw, u


def test_no_other_bench_sets_the_liquid_uniforms():
    """Contracts §11: herb and forge materials never set them (and the circle's do not either),
    so their output is unchanged. No file of theirs gives a material a fillY, surf or turbid
    (as a key or an assignment; the herb jar's own `function fillY` is a different thing), nor
    names the uniforms."""
    others = (sorted((JS / "bench-stage").glob("*.js")) + sorted((JS / "forge-stage").glob("*.js"))
              + sorted((JS / "enchant-stage").glob("*.js"))
              + [JS / "table" / n for n in ("32-bench-stage.js", "42-forge-stage.js", "47-enchant-stage.js")])
    for p in others:
        code = _code(_src(p))
        if p.name == "01-gl.js":
            continue
        for pat in (r"\bfillY\s*:", r"\.fillY\s*=", r"\bturbid\s*:", r"\.turbid\s*=", r"\bsurf\s*:", r"\.surf\s*=",
                    r"uFillY", r"uSurf", r"uTurbid"):
            assert not re.search(pat, code), p.name + " sets " + pat


# --- no library, no download, no stray glyphs --------------------------------------------

def test_no_third_party_library_is_referenced():
    """The app bundles no third-party JavaScript (bench-stage/00-math.js records why: an offline
    executable, no CDN); the packaged app could not load one. Every vessel is a lathe built in
    code, so nothing here fetches a model or an image either."""
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
    """The owner's standing ruling: "this is not earth", and no planet is named anywhere; the
    time of day is rules/sky.py's phase."""
    words = re.compile(r"planet|\b(mars|venus|jupiter|saturn|mercury|earth)\b|[☉☽♂☿♃♀♄]", re.I)
    for name, code in ALL_CODE.items():
        assert not words.search(code), name + ": " + words.search(code).group(0)


def test_the_stage_s_phases_are_sky_s():
    """The day's phases in the stage are rules/sky.py's, in its order, each with a tint."""
    sky = re.search(r"^PHASES = \(([^)]*)\)", SKY, re.M).group(1)
    want = re.findall(r'"(\w+)"', sky)
    got = re.search(r"var PHASES = \[([^\]]*)\]", ALL_CODE[STAGE.name]).group(1)
    assert re.findall(r'"(\w+)"', got) == want
    tint = ALL_CODE[STAGE.name][ALL_CODE[STAGE.name].index("var TINT"):]
    for p in want:
        assert p + ":" in tint[:600], "no tint for " + p


def test_the_reused_parts_are_untouched():
    """Contracts §11: U3 reads bench-stage/ and forge-stage/ and owns only alchemy-stage/ and 52.
    Nothing here assigns into the herb kit or the forge kit."""
    for name, code in ALL_CODE.items():
        assert not re.search(r"BenchStageKit\s*=", code), name + " assigns the herb kit"
        assert not re.search(r"ForgeStageKit\s*=", code), name + " assigns the forge kit"
        assert not re.search(r"\bK\.(math|mesh|Renderer|ground|Particles|props|tools|supported)\s*=", code), name
        assert not re.search(r"\bF\.(props|geo|families|smithy|heat|fx)\s*=", code), name


def test_mesh_ids_cannot_collide():
    """The renderer keys GPU buffers by mesh id (01-gl.js). Every mesh here comes from K.mesh's
    own counter or the forge's sweep (which passes through it); none keeps a counter of its own,
    and no texture is painted here at all."""
    for name, code in ALL_CODE.items():
        assert "nextId" not in code and "nextTex" not in code, name + " keeps its own id counter"


def test_the_copied_heat_ranges_are_the_content_s():
    """The stage keeps a copy of the heat gauges' ranges so a bare heat(c) still poses the
    flame (52-alchemy-stage.js HEAT_RANGE). The standing rule: when a number is copied, pin the
    copy. Every heat block in alchemist.json's bench methods has the same lo and hi here, and
    there is no range here the content does not have."""
    code = ALL_CODE[STAGE.name]
    got = {m: [int(a), int(b)] for m, a, b in re.findall(r"(\w+): \[(\d+), (\d+)\]",
                                                          re.search(r"var HEAT_RANGE = \{([^}]*)\}", code).group(1))}
    want = {m: [row["tuning"]["heat"]["lo"], row["tuning"]["heat"]["hi"]]
            for m, row in CLASS["bench"]["methods"].items() if "heat" in (row.get("tuning") or {})}
    assert got == want, (got, want)


def test_every_method_the_bench_has_the_stage_has():
    """The nine methods are alchemist.json's bench order, and each has an arrangement."""
    code = ALL_CODE[STAGE.name]
    got = re.findall(r'"(\w+)"', re.search(r"var METHODS = \[([^\]]*)\]", code).group(1))
    assert sorted(got) == sorted(CLASS["bench"]["order"]), (got, CLASS["bench"]["order"])
    act = code[code.index("var ACT = {"):code.index("var APPARATUS")]
    for m in got:
        assert re.search(r"\b" + m + r": \{", act), m


def test_every_shelf_vessel_has_a_shape():
    """Bottle draws the glass the work goes into (UI plan §7.2). Every vessel the materials file
    sells (kind "vessel") is named in VESSEL_OF, so none falls back to a vial by accident."""
    code = ALL_CODE["00-glass.js"]
    block = code[code.index("var VESSEL_OF = {"):code.index("function kindOf(")]
    for vid in VESSELS:
        assert '"' + vid + '"' in block, vid + " has no shape"


# --- the contract -----------------------------------------------------------------------

def _contract_methods():
    sec = CONTRACTS[CONTRACTS.index("**Stage (U3 provides, U1 calls).**"):]
    sig = sec[sec.index("```"):sec.index("Without WebGL")]
    return sorted(set(re.findall(r"(\w+)\(", sig)))


def test_alchemystage_exposes_every_contract_method():
    """Every method in contracts §12 is on window.AlchemyStage, in BOTH branches. U1 builds
    against the contract alone; the second branch is taken when the stage's parts failed to load,
    and it must answer the same calls or U1's flat fallback throws instead."""
    methods = _contract_methods()
    assert methods == sorted(["available", "mount", "unmount", "setScene", "setTool", "setVessel", "liquid",
                              "heat", "reaction", "game", "flourish", "productRect", "reducedMotion"]), methods
    code = ALL_CODE[STAGE.name]
    tail = code[code.index("window.AlchemyStage = READY"):]
    ready, fallback = tail.split(" : {", 1)
    for m in methods:
        assert re.search(r"\b" + m + r"\s*:", ready), "AlchemyStage." + m + " missing"
        assert re.search(r"\b" + m + r"\s*:", fallback), "fallback AlchemyStage." + m + " missing"
        line = re.search(r"\b" + m + r"\s*:([^\n]+)", ready).group(1)
        assert "safe(" in line or "try {" in line, m + " is not wrapped against throwing"


def test_gameview_has_the_four_methods_and_the_gauges():
    """game(method) returns {update, hit, miss, end}, the GameView every stage hands
    33-bench-games.js, plus heat and reaction, which the strip calls on a stage that has them
    (33-bench-games.js: `r.stage.heat(r.heat.c)`). An inert one when anything goes wrong."""
    code = ALL_CODE[STAGE.name]
    game = code[code.index("function game("):code.index("function shake(")]
    for m in ("update", "hit", "miss", "end", "heat", "reaction"):
        assert re.search(r"\b" + m + r"\s*:", game), "GameView." + m + " missing"
    assert re.search(r"NOGAME\s*=\s*\{\s*update", code)


def test_sounds_are_the_flourishes_only_on_the_alchemy_bus():
    """Flourish sounds go through one guarded helper, on U5's alchemy bus (UI plan §11; U5's
    list: "Stage flourish(kind) maps to alchemy.<kind>"). The stage rings ONLY its flourishes:
    the shell plays alchemy.open and alchemy.method.<m>, and the games their hits, chimes,
    stoppers and hisses, as the enchanting bench splits them. The first draft also played the
    chime, the stopper, the hiss and a glass tick on set-down, each of which the shell or a game
    rings too, so every one would have sounded twice."""
    code = ALL_CODE[STAGE.name]
    played = sorted(set(re.findall(r'sound\("([^"]+)"', code)))
    assert played == sorted(["alchemy.tier.up", "alchemy.flawless", "alchemy.fail", "alchemy.land",
                             "alchemy.found", "alchemy.flare", "alchemy.crack"]), played
    assert "window.Sound && typeof window.Sound.play" in code
    assert "Sound.play(" not in code.replace("window.Sound.play(name, opts)", "")
    fl = code[code.index("function flourish("):code.index("function land(")]
    assert "sound(" not in code[code.index("function game("):code.index("function shake(")]
    assert 'sound("alchemy.found")' in fl


# --- render on demand, and stopping when no one can see it -------------------------------

def test_requestanimationframe_only_from_the_dirty_path():
    """One rAF call in the whole stage, inside wake() (marked ALCHEMY-STAGE-RAF), and frame()
    asks for the next only `if (busy)` (DIRTY-ONLY). wake()'s guard also refuses a hidden bench
    and a background tab."""
    total = sum(len(re.findall(r"requestAnimationFrame\s*\(", c)) for c in ALL_CODE.values())
    assert total == 1, "requestAnimationFrame is called %d times; only wake() may" % total
    raw = _src(STAGE)
    assert 0 < raw.index("function wake()") - raw.index("ALCHEMY-STAGE-RAF") < 400
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
    code = ALL_CODE[STAGE.name]
    m = code[code.index("function mount("):code.index("function unmount(")]
    u = code[code.index("function unmount("):code.index("function setScene(")]
    assert 'addEventListener("visibilitychange", onVisibility' in m
    assert 'removeEventListener("visibilitychange", onVisibility' in u
    assert "loseContext()" in u and "S.r.dispose()" in u


def test_the_flicker_is_gated_on_a_live_game():
    """UI plan §7.6: the lamp's flicker and the bubbles run only while a game is live."""
    code = ALL_CODE[STAGE.name]
    step = code[code.index("function step("):code.index("function liveStep(")]
    assert "if (isLive(t))" in step and "liveStep(dt, t / 1000)" in step and "S.flick = 1;" in step
    assert re.search(r"return S\.gameOn && \(t - S\.gameLast\) < 300", code)
    assert code.count("S.flick = 1 + ") == 1


def test_device_pixel_ratio_is_capped_and_context_loss_claimed():
    code = ALL_CODE[STAGE.name]
    r = code[code.index("function resize()"):]
    assert "Math.min(2, window.devicePixelRatio || 1)" in r and "MAX_PIXELS" in r
    lost = code[code.index("function onLost("):code.index("function onRestored(")]
    assert "e.preventDefault()" in lost


def test_the_canvas_takes_no_input_and_only_it_shakes():
    """The one-second rule (UI plan §10): the canvas has pointer-events: none, and the shakes
    (Flawless, the flare) are a transform on the stage canvas alone."""
    code = ALL_CODE[STAGE.name]
    assert "pointer-events:none;" in code
    sh = code[code.index("function shake("):code.index("function land(")]
    assert "cv.style.transform" in sh
    for target in ("document.body", "document.documentElement", "S.host.style.transform"):
        assert target not in sh
    assert "if (!cv || still()) return;" in sh


def test_culling_is_put_back_after_the_liquids():
    """The liquids draw backs then fronts with face culling (drawLiquids); the herb kit's
    renderer never enables CULL_FACE (01-gl.js init disables it) and every other mesh is drawn
    two-sided, so culling left on would hollow out the rest of the frame."""
    code = ALL_CODE[STAGE.name]
    d = code[code.index("function drawLiquids("):code.index("function resize()")]
    assert d.count("gl.enable(gl.CULL_FACE)") == 1 and d.count("gl.disable(gl.CULL_FACE)") == 1
    assert d.index("gl.enable(gl.CULL_FACE)") < d.index("gl.disable(gl.CULL_FACE)")


# --- the running stage, in node ---------------------------------------------------------------

@pytest.fixture(scope="module")
def node():
    exe = shutil.which("node")
    if not exe:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    return exe


_STAGE_NODE = r"""
const fs = require('fs'), vm = require('vm');
const files = JSON.parse(process.argv[2]), mode = process.argv[3], vessels = JSON.parse(process.argv[4]);
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
const sb = { window: win, document: doc, performance: win.performance, Math, JSON, Object, Array,
             Float32Array, Uint8Array, Uint8ClampedArray, Uint16Array, Promise, Proxy, isFinite, getComputedStyle: win.getComputedStyle,
             setTimeout: (cb, ms) => { timers.push({ at: T + (ms || 0), cb }); return timers.length; },
             clearTimeout: (id) => { if (timers[id - 1]) timers[id - 1] = null; }, console: win.console };
sb.requestAnimationFrame = win.requestAnimationFrame;
vm.createContext(sb);
for (const f of files) vm.runInContext(fs.readFileSync(f, 'utf8'), sb, { filename: f });
const K = win.BenchStageKit;
let draws = 0, frames = 0, disposed = 0, contexts = 0, culls = 0;
const uploaded = new Set();
let fills = [];
if (mode !== 'nogl') {
  K.supported = () => true;
  K.Renderer = function (cv) {
    this.canvas = cv; this.bufs = {}; this.texs = {}; contexts++; this.draws = 0;
    this.gl = { CULL_FACE: 2884, FRONT: 1028, BACK: 1029, getExtension: () => ({ loseContext() {} }), isContextLost: () => false,
                enable: (x) => { if (x === 2884) culls++; }, disable() {}, cullFace() {} };
  };
  K.Renderer.prototype = {
    init() { return true; }, resize(w, h) { this.canvas.width = w; this.canvas.height = h; },
    begin(f) { this.draws = 0; frames++; fills = []; },
    setBlend() {},
    draw(mesh, m, mat) {
      this.bufs[mesh.id] = 1; if (mat.tex) this.texs[mat.tex.id] = 1; uploaded.add(mesh.id); this.draws++; draws++;
      if (mat.fillY !== undefined && mat.fillY < 5000) fills.push(mat.fillY);
    },
    points(d, c) { if (c) { this.draws++; draws++; } },
    dispose() { disposed++; this.bufs = {}; this.texs = {}; }, forgetTexture(rec) { delete this.texs[rec.id]; },
  };
}
const AS = win.AlchemyStage;
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
const AMBER = { color: [0.86, 0.6, 0.2], level: 0.6, turbidity: 0.85 };
function hostOf(w, h) { const host = el('div'); host.clientWidth = w; host.clientHeight = h; host.appendChild = (c) => { c.parentNode = host; }; host.removeChild = () => {}; return host; }
function fire(map, k) { (map[k] || []).slice().forEach((f) => f()); }
const D = () => AS._debug();
(async () => {
  const out = { mode };
  if (mode === 'nogl') {
    out.available = AS.available();
    out.mount = await AS.mount(el('div'));
    const calls = [];
    try {
      AS.setScene({ kind: 'town' }); calls.push('setScene');
      calls.push('setTool:' + await AS.setTool('distill'));
      AS.setVessel({ id: 'glass-vial', kind: 'vial', liquid: AMBER, receiver: { color: [1, 1, 1], level: 0 } }); calls.push('setVessel');
      calls.push('liquid:' + await AS.liquid({ level: 0.2 }, 300));
      AS.heat(80); AS.reaction(50); calls.push('heat+reaction');
      const g = AS.game('distill'); g.update({ heat: 80, progress: 0.5 }); g.heat(85); g.reaction(10); g.hit(1); g.miss(); g.end(); calls.push('game');
      calls.push('flourish:' + await AS.flourish('flare'));
      calls.push('rect:' + JSON.stringify(AS.productRect()));
      AS.reducedMotion(true); calls.push('reducedMotion'); AS.unmount(); calls.push('unmount');
    } catch (e) { calls.push('THREW ' + e.message); }
    out.calls = calls; out.rafs = rafCount;
    process.stdout.write(JSON.stringify(out));
    return;
  }
  out.available = AS.available();
  const host = hostOf(1000, 560);
  out.mount = await AS.mount(host);
  // Idle: every scene with every method, a vessel and a liquid set, after it settles.
  out.idle = {};
  for (const kind of ['kit', 'town', 'owned']) {
    AS.setScene({ kind, biome: 'forest', minute: 21 * 60 });
    for (const m of ['calcine', 'dissolve', 'distill', 'filter', 'react', 'sublime', 'bottle', 'transmute', 'assay']) {
      await timed(AS.setTool(m));
      AS.setVessel({ id: 'glass-vial', liquid: AMBER, receiver: { color: [0.9, 0.8, 0.5], level: 0.2 } });
      await advance(1500);
      const c = counters();
      await advance(10000);
      const s = since(c), d = D();
      out.idle[kind + ':' + m] = [s.rafs, s.frames, s.draws, d.raf, d.vessel, d.liquids];
    }
  }
  // The liquid: the server's colour is the colour drawn; the level eases over the time given and
  // the fill height climbs with it; reduced motion jumps.
  AS.setScene({ kind: 'kit', biome: 'forest', minute: 720 });
  await timed(AS.setTool('dissolve'));
  AS.setVessel({ id: 'x', liquid: { color: [0.86, 0.6, 0.2], level: 0.2, turbidity: 0.85 } });
  await advance(300);
  const f0 = D().shown.fillY;
  const lp = AS.liquid({ level: 0.9, turbidity: 0.1 }, 600);
  await advance(300);
  const mid = D().liquid;
  const done = await timed(lp);
  await advance(100);
  out.liquid = { f0, f1: D().shown.fillY, mid, end: D().liquid, shown: D().shown, ms: done.ms, val: done.val, drawnFills: fills.slice() };
  AS.reducedMotion(true);
  const t0 = T; await AS.liquid({ level: 0.3 }, 600); out.liquid.reducedMs = T - t0; out.liquid.reducedLevel = D().liquid.level;
  AS.reducedMotion(false);
  // No liquid sent is an empty vessel, not a guessed one.
  AS.setVessel({ id: 'x' }); await advance(200); out.empty = D().shown;
  // A live game: the flame breathes, bubbles rise, and it all stops when the states stop.
  AS.setVessel({ id: 'x', liquid: AMBER });
  await timed(AS.setTool('react'));
  let g = AS.game('react', { end: { color: [0.3, 0.5, 0.8], level: 0.7, turbidity: 0.2 } });
  let flicks = new Set(), c = counters();
  for (let i = 0; i < 125; i++) { g.update({ reaction: 55 + 10 * Math.sin(i / 7), progress: i / 124 }); if (i % 30 === 29) g.hit(0.9); await advance(16); flicks.add(D().flick.toFixed(4)); }
  out.live = Object.assign(since(c), { flicks: flicks.size, particles: D().particles, end: D().liquid });
  const stopAt = T; let lastFrame = 0, fr0 = frames;
  while (T - stopAt < 6000) { const before = frames; await advance(16); if (frames > before) lastFrame = T - stopAt; }
  out.afterStop = { lastFrameMs: lastFrame, frames: frames - fr0 };
  c = counters(); await advance(10000); out.idleAfterGame = since(c);
  g.end(); await advance(1500);
  // The reaction gauge overshoots: one puff and one hiss per crossing, no crack.
  g = AS.game('react');
  const hiss0 = sounds.filter((s) => s === 'alchemy.hiss').length, puffs0 = D().puffs;
  for (const v of [60, 80, 95, 97, 70, 92]) { g.update({ reaction: v, flare_at: 90 }); await advance(16); }
  out.overshoot = { puffs: D().puffs - puffs0, hiss: sounds.filter((s) => s === 'alchemy.hiss').length - hiss0, cracked: D().cracked, particles: D().particles };
  g.end(); await advance(3000);
  // Heat: the flame follows; Calcine's charge glows by its temperature (the forge's table).
  await timed(AS.setTool('calcine'));
  AS.setVessel({ id: 'x', liquid: { color: [0.86, 0.78, 0.22], level: 0.4, turbidity: 1 } });
  g = AS.game('calcine');
  g.heat(300); await advance(32); const cool = { k: D().heatK, glow: D().glow };
  g.heat(850); await advance(32); const hot = { k: D().heatK, glow: D().glow };
  g.update({ whiteness: 1, heat: 850 }); await advance(32); const white = D().shown.color;
  out.heat = { cool, hot, white };
  g.end(); await advance(2000);
  // Distill: the cucurbit's level falls and the receiver's rises as the hearts run.
  await timed(AS.setTool('distill'));
  AS.setVessel({ id: 'x', liquid: { color: [0.5, 0.7, 0.4], level: 0.8, turbidity: 0.4 }, receiver: { color: [0.8, 0.9, 0.8], level: 0 } });
  g = AS.game('distill', { end: { color: [0.5, 0.7, 0.4], level: 0.4, turbidity: 0 } });
  const r0 = D().receiver;
  for (let i = 0; i <= 50; i++) { g.update({ heat: 84, progress: i / 50 }); await advance(16); }
  out.distill = { r0, r1: D().receiver, level: D().liquid.level, particles: D().particles, k: D().heatK };
  g.end(); await advance(3000);
  // Transmute: the four stages, black to red.
  await timed(AS.setTool('transmute'));
  AS.setVessel({ id: 'x', liquid: { color: [0.2, 0.2, 0.2], level: 0.6, turbidity: 1 } });
  g = AS.game('transmute');
  out.transmute = {};
  for (const [i, name] of [[0, 'nigredo'], [1, 'albedo'], [2, 'citrinitas'], [3, 'rubedo']]) {
    g.update({ stage: name }); g.hit(1, i); await advance(64); out.transmute[name] = D().shown.color;
  }
  out.transmute.glow = D().glow;
  g.end(); await advance(3000);
  // Sublime's crust grows, and a scrape lets it fall.
  await timed(AS.setTool('sublime'));
  AS.setVessel({ id: 'x', liquid: { color: [0.9, 0.9, 0.85], level: 0.3, turbidity: 1 } });
  g = AS.game('sublime');
  g.update({ crust: 0.8 }); await advance(32); const crust = D().crust;
  g.update({ crust: 0 }); await advance(32);
  out.sublime = { crust, after: D().crust, particles: D().particles };
  g.end(); await advance(3000);
  // Bottle: the vessel the shelf names; the stopper goes in on the hit.
  await timed(AS.setTool('bottle'));
  out.bottle = {};
  for (const v of vessels) { AS.setVessel({ id: v, liquid: { color: [0.8, 0.2, 0.2], level: 0.5, turbidity: 0.1 } }); out.bottle[v] = D().vessel; }
  AS.setVessel({ id: 'glass-vial', liquid: { color: [0.8, 0.2, 0.2], level: 0.5, turbidity: 0.1 } });
  g = AS.game('bottle'); g.update({ pour: 1 }); await advance(100); g.hit(1, 1); await advance(32);
  out.bottle._stopper = D().stopper;
  g.end(); await advance(3000);
  // Hidden mid-game: no frame asked for, a flourish still resolves on time, and back it comes.
  await timed(AS.setTool('react'));
  g = AS.game('react');
  host.clientWidth = 0; host.clientHeight = 0; fire(listeners.win, 'resize');
  c = counters();
  for (let i = 0; i < 60; i++) { g.update({ reaction: 50 }); if (i % 20 === 0) g.hit(1); await advance(16); }
  const hid = await timed(AS.flourish('tier'));
  out.hidden = Object.assign(since(c), { flourish: hid });
  host.clientWidth = 1000; host.clientHeight = 560; fire(listeners.win, 'resize');
  c = counters(); await advance(200); out.shownAgain = since(c);
  g.end(); await advance(3000);
  doc.hidden = true; fire(listeners.doc, 'visibilitychange');
  g = AS.game('react'); c = counters();
  for (let i = 0; i < 60; i++) { g.update({ reaction: 50, heat: 40 }); await advance(16); }
  out.background = since(c);
  doc.hidden = false; fire(listeners.doc, 'visibilitychange');
  g.end(); await advance(3000);
  // Reduced motion: no flicker, nothing flies.
  AS.reducedMotion(true);
  g = AS.game('react'); flicks = new Set();
  for (let i = 0; i < 60; i++) { g.update({ reaction: 70 }); if (i % 20 === 0) g.hit(1); await advance(16); flicks.add(D().flick.toFixed(4)); }
  out.reduced = { flicks: flicks.size, particles: D().particles };
  g.end(); await advance(500);
  // The flare under reduced motion keeps its states: the crack and the lost liquid.
  AS.setVessel({ id: 'x', liquid: { color: [0.9, 0.5, 0.1], level: 0.8, turbidity: 0.3 } });
  const rfp = AS.flourish('flare');
  await advance(16);
  const spike = D().flare;
  const rf = await timed(rfp);
  out.reducedFlare = { ms: rf.ms + 16, cracked: D().cracked, level: D().liquid.level, particles: D().particles, flare: spike };
  AS.reducedMotion(false); await advance(2000);
  // Flourishes, each from rest; the flare cracks the glass and loses most of the liquid.
  out.flourish = {};
  for (const k of ['tier', 'flawless', 'land', 'fail', 'flare', 'found']) {
    AS.setVessel({ id: 'x' + k, liquid: { color: [0.9, 0.5, 0.1], level: 0.8, turbidity: 0.3 } });
    await advance(1500);
    out.flourish[k] = await timed(AS.flourish(k));
    await advance(100);
    out.flourish[k].after = { cracked: D().cracked, level: D().liquid.level, dull: D().dull };
    await advance(2500);
  }
  out.flourish.unknown = await timed(AS.flourish('nonsense'));
  AS.setVessel({ id: 'another', liquid: AMBER }); out.newVesselCracked = D().cracked;
  // Every method has an arrangement; an unknown one says no.
  out.tools = {};
  for (const m of ['calcine', 'dissolve', 'distill', 'filter', 'react', 'sublime', 'bottle', 'transmute', 'assay', 'forge']) out.tools[m] = (await timed(AS.setTool(m))).val;
  // The day's phase tints the fill, a little.
  out.tint = {};
  for (const [ph, minute] of [['noon', 720], ['midnight', 0], ['dusk', 1080]]) {
    AS.setScene({ kind: 'kit', biome: 'forest', minute }); await advance(200);
    out.tint[ph] = { fill: D().fill, phase: D().phase };
  }
  // Memory: churn grows nothing, and ten opens and closes leave nothing behind.
  AS.setScene({ kind: 'town', minute: 600 });
  for (const m of ['calcine', 'dissolve', 'distill', 'filter', 'react', 'sublime', 'bottle', 'transmute', 'assay']) { await timed(AS.setTool(m)); await advance(100); }
  // Every shelf vessel once in this laboratory, so what follows measures churn, not first builds.
  await timed(AS.setTool('bottle'));
  for (const v of vessels) { AS.setVessel({ id: v, liquid: AMBER }); await advance(32); }
  const before = uploaded.size;
  for (let i = 0; i < 40; i++) {
    await timed(AS.setTool(['distill', 'bottle', 'react', 'filter'][i % 4]));
    AS.setVessel({ id: vessels[i % vessels.length], liquid: AMBER }); await advance(48);
  }
  await advance(500);
  const afterChurn = uploaded.size;
  const cycles = [];
  AS.unmount();
  for (let i = 0; i < 10; i++) {
    await AS.mount(host); AS.setScene({ kind: i % 2 ? 'town' : 'kit', biome: 'forest', minute: 600 });
    await timed(AS.setTool('distill')); AS.setVessel({ id: 'x', liquid: AMBER });
    await advance(1200);
    cycles.push(uploaded.size);
    AS.unmount();
  }
  out.memory = { before, afterChurn, cycles, disposed, contexts, culls, listeners: { resize: (listeners.win.resize || []).length, vis: (listeners.doc.visibilitychange || []).length }, timersLeft: timers.filter(Boolean).length };
  out.sounds = sounds;
  out.warns = warns;
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
"""


def _run(node, tmp, mode):
    script = tmp / ("stage-" + mode + ".js")
    script.write_text(_STAGE_NODE, encoding="utf-8")
    done = subprocess.run([node, str(script), json.dumps([str(p) for p in LOADS]), mode, json.dumps(VESSELS)],
                          capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr[:3000]
    return json.loads(done.stdout)


@pytest.fixture(scope="module")
def run(node, tmp_path_factory):
    return _run(node, tmp_path_factory.mktemp("alchemy"), "gl")


@pytest.fixture(scope="module")
def nogl(node, tmp_path_factory):
    return _run(node, tmp_path_factory.mktemp("alchemy"), "nogl")


def test_idle_draws_zero_frames(run):
    """UI plan §7.6: "a test pins zero frames over 10 idle seconds", the lamp and the liquid
    included. Measured with the real stage on a counting renderer: after each arrangement
    settles, ten simulated seconds at the field kit, in a town laboratory and in your own, for
    all nine methods with a vessel and a liquid set, ask for 0 frames and issue 0 draw calls."""
    assert run["available"] is True and run["mount"] is True
    assert len(run["idle"]) == 27
    for key, (rafs, frames, draws, raf, vessel, liquids) in run["idle"].items():
        assert (rafs, frames, draws, raf) == (0, 0, 0, False), (key, rafs, frames, draws)
        assert vessel, key + " has no vessel"


def test_the_liquid_is_the_server_s_and_eases_to_its_level(run):
    """UI plan §7.4: the page never invents a colour, it only eases between two the server sent.
    The amber the server sent is the colour drawn (through the house shader's 1.6 gamma), the
    level eased from 0.2 through the middle to 0.9 in the 600 ms given and the fill height
    climbed with it; under reduced motion the same call landed at once. A vessel sent with no
    liquid is drawn empty: the first draft defaulted to half full of water."""
    lq = run["liquid"]
    assert lq["val"] is True and lq["ms"] <= 700, lq
    assert 0.2 < lq["mid"]["level"] < 0.9 and abs(lq["end"]["level"] - 0.9) < 1e-6, lq
    assert lq["f1"] > lq["f0"] + 0.05, (lq["f0"], lq["f1"])
    want = [round(x ** 1.6, 4) for x in (0.86, 0.6, 0.2)]
    assert [round(x, 4) for x in lq["shown"]["color"]] == want, lq["shown"]
    assert lq["drawnFills"], "no liquid was drawn with a fill height"
    assert lq["reducedMs"] <= 32 and abs(lq["reducedLevel"] - 0.3) < 1e-6
    assert run["empty"]["visible"] is False


def test_the_flame_and_churn_run_only_while_a_game_is_live(run):
    """The flicker and the bubbles are the motions that would keep the loop alive for ever, so
    they run only while a game sends states. Measured: 125 states drew a frame each with the
    flicker taking over twenty values and bubbles in the air, and the liquid reached the game's
    end state; when the states stopped the loop ended inside three seconds (the last particles
    dying), and the ten seconds after drew nothing. Under reduced motion the flicker held one
    value and nothing flew."""
    live = run["live"]
    assert live["frames"] >= 100 and live["flicks"] > 20 and live["particles"] > 0, live
    assert abs(live["end"]["level"] - 0.7) < 0.02, live["end"]
    assert run["afterStop"]["lastFrameMs"] < 3000, run["afterStop"]
    assert run["idleAfterGame"] == {"rafs": 0, "draws": 0, "frames": 0}
    assert run["reduced"] == {"flicks": 1, "particles": 0}, run["reduced"]


def test_a_hidden_bench_and_a_background_tab_draw_nothing(run):
    """A hidden canvas drawing at 60 frames a second costs the GPU what a visible one does.
    Measured: a live React sending 60 states and three hits to a bench whose box has no size
    asked for 0 frames, a flourish started while hidden still resolved on time, and the first
    frame came back once the box had a size again. The same for a background tab."""
    h = run["hidden"]
    assert (h["rafs"], h["frames"], h["draws"]) == (0, 0, 0), h
    assert h["flourish"]["val"] is True and h["flourish"]["ms"] <= 600, h
    assert run["shownAgain"]["frames"] >= 1
    b = run["background"]
    assert (b["rafs"], b["frames"]) == (0, 0), b


def test_the_reaction_s_overshoot_is_a_puff_not_a_mishap(run):
    """UI plan §6.4: over `flare_at` the stage shows a small flare, "a quality signal only": a
    puff of vapour, no crack (the hiss is the game's to ring). Six states crossing 90 twice
    puffed exactly twice, and the stage rang no sound for it."""
    o = run["overshoot"]
    assert o["puffs"] == 2 and o["hiss"] == 0 and o["cracked"] is False and o["particles"] > 0, o


def test_the_flame_follows_the_heat_and_the_calx_glows(run):
    """The burner's flame follows heat(celsius) on the method's gauge (Calcine 200..1100 °C),
    and the charge glows by its own temperature through the forge's table: none at 300 °C
    (below black red), a red glow at 850 °C (cherry). Whiteness 1 whitens the charge to a calx
    from the server's brimstone yellow."""
    h = run["heat"]
    assert h["hot"]["k"] > h["cool"]["k"] + 0.5, h
    assert h["cool"]["glow"] == [0, 0, 0] and h["hot"]["glow"][0] > h["hot"]["glow"][2] > -1, h
    assert h["hot"]["glow"][0] > 0.05
    w = h["white"]
    assert min(w) > 0.7 and abs(w[0] - w[2]) < 0.15, w


def test_distill_moves_the_liquid_into_the_receiver(run):
    """UI plan §7.4: "Distill moves the cucurbit's level down and the receiver's level up as the
    hearts run". Over a game from progress 0 to 1 toward an end level of 0.4, the cucurbit fell
    from 0.8 to 0.4, the receiver rose from empty, and the alembic dripped."""
    d = run["distill"]
    assert d["r0"] == 0 and d["r1"] > 0.3 and abs(d["level"] - 0.4) < 1e-6 and d["particles"] > 0, d


def test_transmute_runs_black_white_yellow_red(run):
    """UI plan §9: "The Great Work in the aludel turns black, then white, then yellow, then
    red." Measured by the colour drawn at each stage, and the Great Work's own light at
    rubedo."""
    t = run["transmute"]
    assert max(t["nigredo"]) < 0.02, t["nigredo"]
    assert min(t["albedo"]) > 0.75, t["albedo"]
    assert t["citrinitas"][0] > 0.6 and t["citrinitas"][2] < 0.1, t["citrinitas"]
    assert t["rubedo"][0] > 0.5 and t["rubedo"][1] < 0.05, t["rubedo"]
    assert t["glow"][0] > t["glow"][1], t["glow"]


def test_sublime_s_crust_grows_and_falls(run):
    s = run["sublime"]
    assert s["crust"] == 0.8 and s["after"] == 0 and s["particles"] > 0, s


def test_every_shelf_vessel_reaches_the_bench(run):
    """Bottle draws the vessel the shelf names: all fourteen of alchemist-materials.json's
    vessels build without a warning, each as its own shape (a clay flask is not a vial, a waxed
    bladder is not a flask), and the stopper goes in on the stopper's hit."""
    b = run["bottle"]
    shapes = {k: v for k, v in b.items() if not k.startswith("_")}
    assert len(shapes) == 14, shapes
    assert shapes["glass-vial"] == "vial" and shapes["clay-flask"] == "clayflask" and shapes["waxed-bladder"] == "bladder"
    assert shapes["wooden-rod"] == "rod" and shapes["adamantine-crucible"] == "crucible"
    assert b["_stopper"] is True
    assert run["warns"] == [], run["warns"][:5]


def test_every_flourish_ends_inside_1_1_seconds(run):
    """The one-second rule (UI plan §10): every flourish ends on its own inside 1.1 s, and an
    unknown one answers false at once. The flare (UI plan §7.5) leaves the glass cracked and
    keeps 45% of the liquid; a new vessel clears the crack. Failure leaves the liquid dulled."""
    f = run["flourish"]
    for k in ("tier", "flawless", "land", "fail", "flare", "found"):
        assert f[k]["val"] is True, (k, f[k])
        assert f[k]["ms"] <= 1100, (k, f[k]["ms"])
    assert f["unknown"]["val"] is False and f["unknown"]["ms"] <= 32
    assert f["flare"]["after"]["cracked"] is True and abs(f["flare"]["after"]["level"] - 0.36) < 0.01, f["flare"]
    assert f["tier"]["after"]["cracked"] is False
    assert f["fail"]["after"]["dull"] == 1
    assert run["newVesselCracked"] is False
    for name in ("alchemy.tier.up", "alchemy.flawless", "alchemy.fail", "alchemy.land", "alchemy.flare", "alchemy.crack",
                 "alchemy.found"):
        assert name in run["sounds"], name


def test_the_reduced_flare_keeps_its_states(run):
    """UI plan §7.5: "Reduced motion: the glow spike and the word only, with no shake, smoke or
    particles. The crack still shows, because it is a state." Measured: the light spiked, the
    glass cracked, the level fell to 45% at once, and no particle flew."""
    r = run["reducedFlare"]
    assert r["cracked"] is True and abs(r["level"] - 0.36) < 1e-6 and r["particles"] == 0 and r["flare"] > 0.5, r
    assert r["ms"] <= 400


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
    """The brief: "dispose GPU resources on close (measure 10 open/close cycles)". Measured on
    the counting renderer: once every arrangement and all fourteen vessels had been built, 40 more
    rounds of changing methods and vessels grew the set of distinct meshes by nothing (the first
    pass of this test counted first builds as growth: 84 to 107, then flat); ten mounts and unmounts disposed ten renderers, drew the same mesh
    set every time, culled only round the liquids, and left no resize or visibility listener and
    no pending timer."""
    m = run["memory"]
    assert m["afterChurn"] == m["before"], m
    assert len(set(m["cycles"])) == 1, m["cycles"]
    assert m["disposed"] >= 10 and m["listeners"] == {"resize": 0, "vis": 0}, m
    assert m["timersLeft"] == 0, m
    assert m["culls"] > 0


def test_nothing_throws_without_webgl(nogl):
    """available() is false without WebGL, mount() resolves false, and every other call is a
    quiet no-op (contracts §12: "Without WebGL every call is a no-op")."""
    assert nogl["available"] is False and nogl["mount"] is False
    assert not any(c.startswith("THREW") for c in nogl["calls"]), nogl["calls"]
    assert nogl["rafs"] == 0
