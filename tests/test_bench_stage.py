"""The herbalism bench's 3D stage: hand-built, render-on-demand, and true to its contract.

Lane F of the herbalism revamp (docs/herbalism-contracts.md §5.1, docs/herbalism-ui-plan.md
§6.3 and §10). The stage is play/static/js/bench-stage/*.js plus
play/static/js/table/32-bench-stage.js, which leaves one global, window.BenchStage.

These are source checks rather than behaviour, for the reason tests/test_dice3d.py gives:
there is no JavaScript test runner here, and adding one would be a dependency in an app
that bundles none. The behaviour was measured in the harness (tools/bench-harness/stage.html)
on 2026-10-02, and each test below names what it pins and what that measurement was:

  * idle: 0 draw calls and 0 requestAnimationFrame calls in 3 seconds after everything
    settled, counted by patching the live WebGL context from outside the stage; one ground
    change then cost exactly 1 frame of 27 draw calls;
  * Flawless flourish: 138 to 141 frames in its 0.7s, 0.3 to 0.43ms of script per frame,
    and a 5.0ms median frame gap on a 200Hz display, at 1276x718 and at 2820x1340;
  * the tool stood at 50% of the stage height at 16:9, 21:9 and 3440x1440, and at no less
    than 38% on a 418x760 narrow stage, measured from every vertex.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "play" / "static" / "js"
PARTS = sorted((JS / "bench-stage").glob("*.js"))
STAGE = JS / "table" / "32-bench-stage.js"
HARNESS = ROOT / "tools" / "bench-harness" / "stage.html"
CONTRACTS = (ROOT / "docs" / "herbalism-contracts.md").read_text(encoding="utf-8")

FILES = PARTS + [STAGE]


def _src(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _code(text: str) -> str:
    """Source with comments stripped, so prose that names a thing is not mistaken for it.

    The stage's own header says "no requestAnimationFrame loop" and "three.js" in plain
    words; a check that counted those would fail on the sentence explaining the rule.
    String literals are kept (the shaders live in them).
    """
    out, i, n = [], 0, len(text)
    quote = None
    while i < n:
        c = text[i]
        if quote:
            out.append(c)
            if c == chr(92) and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "\"'":
            quote = c
            out.append(c)
            i += 1
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if text.startswith("//", i):
            j = text.find(chr(10), i)
            i = n if j < 0 else j
            continue
        out.append(c)
        i += 1
    return "".join(out)


ALL_CODE = {p.name: _code(_src(p)) for p in FILES}


def _strings(code: str):
    return re.findall(r'"((?:[^"\\]|\\.)*)"|' + r"'((?:[^'\\]|\\.)*)'", code)


# --- no library, no download ------------------------------------------------------------

def test_no_third_party_library_is_referenced():
    """The plan said "reuse three.js"; the app has none and bundles no third-party JS.

    scene3d.js's header records why (an offline executable, no CDN). A stage that reached
    for THREE, an import, a require or any URL would either fail offline in the packaged
    app or smuggle in a bundling decision nobody made.
    """
    for name, code in ALL_CODE.items():
        assert not re.search(r"\bTHREE\b", code), name + " references THREE"
        assert not re.search(r"\b(import|require)\s*\(", code), name + " loads a module"
        assert not re.search(r"^\s*import\s", code, re.M), name + " uses an ES import"
        assert "http://" not in code and "https://" not in code, name + " fetches from a URL"
        assert ".gltf" not in code and ".glb" not in code, name + " loads a model file"
    html = _src(HARNESS)
    for src in re.findall(r'<script[^>]*src="([^"]+)"', html):
        assert not src.startswith(("http:", "https:", "//")), "the harness loads " + src


def test_no_hand_written_svg():
    """Icons and art are not hand-drawn SVG paths (UI plan §3, the skill's icon rule).

    The stage is WebGL and procedural textures; any SVG here would be a hand-drawn icon.
    """
    for p in FILES + [HARNESS]:
        text = _src(p).lower()
        assert "<svg" not in text, p.name + " contains an svg element"
        assert "createelementns" not in text, p.name + " builds svg nodes"
        assert "2000/svg" not in text, p.name + " names the svg namespace"


def test_no_em_dashes_in_strings():
    """No em-dash or en-dash in any string the stage carries (contracts §0, UI plan §8).

    Measured on this lane's first draft: zero, and this keeps it there.
    """
    for name, code in ALL_CODE.items():
        for a, b in _strings(code):
            s = a or b
            assert chr(0x2014) not in s and chr(0x2013) not in s, name + " string: " + s[:60]


# --- the contract ----------------------------------------------------------------------

def _contract_methods():
    sec = CONTRACTS[CONTRACTS.index("### 5.1"):CONTRACTS.index("### 5.2")]
    return sorted(set(re.findall(r"BenchStage\.(\w+)\(", sec)))


def test_benchstage_exposes_every_contract_method():
    """Every method in contracts §5.1 is on window.BenchStage, in BOTH branches.

    D and E build against the contract alone, with fakes; a missing method would only
    show up at merge. The second branch is the one taken when the stage's parts failed to
    load, and it must answer the same calls or D's flat fallback throws instead.
    """
    methods = _contract_methods()
    assert len(methods) == 13, methods
    code = ALL_CODE[STAGE.name]
    tail = code[code.index("window.BenchStage = READY"):]
    ready, fallback = tail.split(" : {", 1)
    for m in methods:
        assert re.search(r"\b" + m + r"\s*:", ready), "BenchStage." + m + " missing"
        assert re.search(r"\b" + m + r"\s*:", fallback), "fallback BenchStage." + m + " missing"


def test_gameview_has_the_four_contract_methods():
    """GameView is {update(state), hit(strength0to1), miss(), end()} (contracts §5.1)."""
    code = ALL_CODE[STAGE.name]
    game = code[code.index("function game("):code.index("function flourish(")]
    for m in ("update", "hit", "miss", "end"):
        assert re.search(r"\b" + m + r"\s*:", game), "GameView." + m + " missing"
    assert re.search(r"NOGAME\s*=\s*\{\s*update", code), "no inert GameView for the fallback"


def _method_ids():
    # The list wraps onto a second line in the contract, so read up to the level bullets.
    m = re.search(r"\*\*Method ids:\*\*(.*?)\n- ", CONTRACTS, re.S)
    return re.findall(r"`(\w+)`", m.group(1))


def test_every_method_id_has_a_tool_builder():
    """All nine method ids in contracts §2 have a tool (revamp plan §9.3).

    setTool(method) on an id with no builder resolves false and leaves the stage empty,
    which in the bench would be a method with no tool on its ground.
    """
    ids = _method_ids()
    assert ids == ["grind", "mix", "brew", "dry", "reduce", "extract", "infuse", "steep",
                   "neutralize"], ids
    code = ALL_CODE["06-tools.js"]
    build = code[code.index("var BUILD = {"):]
    build = build[:build.index("}")]
    for i in ids:
        assert re.search(r"\b" + i + r"\s*:\s*" + i + r"\b", build), "no builder for " + i
        assert re.search(r"function " + i + r"\(\)", code), "no builder function " + i


def _contract_state_keys():
    sec = CONTRACTS[CONTRACTS.index("**GameView**"):CONTRACTS.index("### 5.2")]
    rows = re.findall(r"^\|\s*(\w+)\s*\|\s*`\{(.*)\}`\s*\|$", sec, re.M)
    out = {}
    for method, body in rows:
        out[method] = re.findall(r"(\w+)\s*:", body)
    return out


def test_every_tool_reads_its_contract_state():
    """Each tool's pose reads every key the contract gives its GameView state.

    A key the tool never reads is a value in E's game that moves nothing on the stage.
    Measured: the first run of this test found Infuse ignoring `cold` (the heat could sit
    under the cold line and the crock looked exactly as it did inside the band). The table
    in §5.1 is parsed here, so a contract change that adds a key fails until a tool shows it.
    """
    keys = _contract_state_keys()
    assert sorted(keys) == sorted(_method_ids()), keys
    code = ALL_CODE["06-tools.js"]
    for method, ks in keys.items():
        start = code.index("function " + method + "()")
        nxt = code.find("\n  function ", start + 10)
        body = code[start:nxt if nxt > 0 else len(code)]
        for k in ks:
            if method == "dry" and k in ("cure", "band", "turned"):
                assert "bk." + k in body, "dry ignores bundles[]." + k
            elif method == "dry" and k == "bundles":
                assert "s.bundles" in body
            else:
                # Read straight off the state in pose(), or off the kept copy `st` in dots().
                assert re.search(r"\bst?\." + k + r"\b", body), method + " ignores state." + k


def test_every_contract_sound_is_played():
    """The stage plays its five sounds through window.Sound (UI plan §11), guarded.

    `Sound` may be absent (lane G is separate), so every call goes through one guarded
    helper rather than a bare Sound.play that would throw without it.
    """
    code = ALL_CODE[STAGE.name]
    for name in ('"bench.drop." + part', '"bench.tier.up"', '"bench.flawless"', '"bench.fail"',
                 '"bench.land"'):
        assert "sound(" + name in code, "never plays " + name
    assert "window.Sound && typeof window.Sound.play" in code
    assert "Sound.play(" not in code.replace("window.Sound.play(name)", "")


# --- render on demand -------------------------------------------------------------------

def test_requestanimationframe_only_from_the_dirty_path():
    """No unconditional animation loop: one rAF call in the whole stage, inside wake().

    UI plan §10: "No requestAnimationFrame loop runs while the bench is idle." Measured in
    the harness: 0 frames and 0 draw calls in 3 idle seconds. That holds because the only
    rAF lives in wake() (marked BENCH-STAGE-RAF), and frame() asks for the next one only
    under `if (busy)` (marked DIRTY-ONLY). A second rAF anywhere, or an unconditional
    re-schedule, would be a loop that burns the GPU while the owner reads.
    """
    total = sum(len(re.findall(r"requestAnimationFrame\s*\(", c)) for c in ALL_CODE.values())
    assert total == 1, "requestAnimationFrame is called %d times; only wake() may" % total
    raw = _src(STAGE)
    marker = raw.index("BENCH-STAGE-RAF")
    wake = raw.index("function wake()")
    assert 0 < wake - marker < 300, "the BENCH-STAGE-RAF marker no longer sits on wake()"
    code = ALL_CODE[STAGE.name]
    w = code[code.index("function wake()"):code.index("function frame(")]
    assert "requestAnimationFrame(frame)" in w
    assert re.search(r"if \(S\.raf \|\| !S\.mounted \|\| S\.lost\) return;", w), "wake() lost its guard"
    f = code[code.index("function frame("):code.index("function tween(")]
    assert "DIRTY-ONLY" in raw[raw.index("function frame("):raw.index("function tween(")]
    assert re.search(r"if \(busy\) wake\(\);", f), "frame() re-schedules unconditionally"
    for name, c in ALL_CODE.items():
        assert "setInterval(" not in c, name + " polls with setInterval"


def test_device_pixel_ratio_is_capped_at_two():
    """The canvas is DPR-aware but capped at 2, and again at 4K worth of pixels.

    At 3440x1440 and a ratio of 2 the buffer would be 6880x2880, five times 1080p's fill.
    """
    code = ALL_CODE[STAGE.name]
    r = code[code.index("function resize()"):]
    assert "Math.min(2, window.devicePixelRatio || 1)" in r
    assert "MAX_PIXELS" in r


def test_context_loss_is_claimed_and_recovered():
    """webglcontextlost is preventDefault-ed and restore rebuilds (Khronos HandlingContextLost).

    Without preventDefault the browser never offers the context back. Measured in the
    harness: lost, every API call made while lost returned quietly, and after restore one
    ground change drew a full frame again.
    """
    code = ALL_CODE[STAGE.name]
    lost = code[code.index("function onLost("):code.index("function onRestored(")]
    assert "e.preventDefault()" in lost
    assert '"webglcontextlost"' in code and '"webglcontextrestored"' in code
    gl = ALL_CODE["01-gl.js"]
    init = gl[gl.index("Renderer.prototype.init"):gl.index("Renderer.prototype.program")]
    assert "this.bufs = {}" in init and "this.texs = {}" in init, "restore keeps dead GL handles"


def test_nothing_throws_without_webgl():
    """available() is false without WebGL, and every public call is wrapped.

    Measured in the harness with getContext stubbed to return null: available() false,
    mount() resolved false, every other call returned without an error.
    """
    gl = ALL_CODE["01-gl.js"]
    sup = gl[gl.index("function supported()"):gl.index("function Renderer(")]
    assert "try {" in sup and "catch (e)" in sup
    code = ALL_CODE[STAGE.name]
    ready = code[code.index("window.BenchStage = READY"):].split(" : {", 1)[0]
    for m in _contract_methods():
        line = re.search(r"\b" + m + r"\s*:([^\n]+)", ready).group(1)
        assert "safe(" in line or "try {" in line, m + " is not wrapped against throwing"


# --- never in the way -------------------------------------------------------------------

def test_the_canvas_takes_no_input_and_only_it_shakes():
    """The stage never blocks a menu (UI plan §10, the one-second rule).

    The canvas has pointer-events: none, and the Flawless shake is a transform on the
    stage canvas alone. Measured: during the shake the canvas carried
    translate(3.37px, -3.4px) while body and the host stayed at `none`.
    """
    code = ALL_CODE[STAGE.name]
    assert "pointer-events:none;" in code
    fl = code[code.index("function flourish("):code.index("function showProduct(")]
    assert "cv.style.transform" in fl
    for target in ("document.body", "document.documentElement", "S.host.style.transform"):
        assert target not in fl, "a flourish moves " + target


def test_reduced_motion_drops_particles_and_shake():
    """Reduced motion: no particles, no shake, a crossfade instead of a drop (UI plan §10).

    Measured: with the flag on, two hits left 0 particles alive, the Flawless shake left
    the canvas transform empty, and a tool swap resolved in 125ms (the 120ms crossfade)
    against 636ms for the full lift and drop.
    """
    code = ALL_CODE[STAGE.name]
    emit = code[code.index("emit: function"):code.index("dot: function")]
    assert "if (S.reduced" in emit, "particles are emitted under reduced motion"
    fl = code[code.index("function flourish("):code.index("function showProduct(")]
    assert "shook = !S.reduced" in fl
    sw = code[code.index("function setTool("):code.index("function chipSpot(")]
    assert "if (S.reduced)" in sw and "tween(120" in sw


def test_the_swap_timing_is_the_plan_s():
    """Old tool lifts out in 180ms; the new one drops in 450ms with a 4% overshoot."""
    code = ALL_CODE[STAGE.name]
    sw = code[code.index("function setTool("):code.index("function chipSpot(")]
    assert "tween(180" in sw
    assert "lead + 450" in sw
    assert "0.04 * Math.cos" in sw, "the 4% overshoot is gone"
    assert "setTimeout(" in sw, "a swap promise could hang in a background tab"


def test_harness_loads_every_part_before_the_api():
    """The harness loads bench-stage/*.js in number order, then 32 (contracts §1 tag order).

    D copies this order into table.html; a part loaded after 32 would leave READY false
    and the stage silently flat.
    """
    html = _src(HARNESS)
    srcs = re.findall(r'<script src="([^"]+)"', html)
    parts = [s for s in srcs if "/bench-stage/" in s]
    assert [Path(s).name for s in parts] == [p.name for p in PARTS]
    assert srcs.index(parts[-1]) < srcs.index(next(s for s in srcs if s.endswith("32-bench-stage.js")))
