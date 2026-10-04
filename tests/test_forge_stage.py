"""The forge's 3D stage: hot metal as a light, the work built from its pieces, and render on demand.

Lane U4 of the blacksmithing revamp (docs/blacksmithing-ui-plan.md §6.3, §7, §10;
docs/blacksmithing-contracts.md §10-11). The stage is play/static/js/forge-stage/*.js plus
play/static/js/table/42-forge-stage.js, which leaves one global, window.ForgeStage, and runs on
the herb stage's renderer, maths, meshes, ground and particles (bench-stage/00-04, as is).

Two kinds of check, as tests/test_bench_stage.py has. SOURCE checks pin the rules that a
reading of the code can hold (one requestAnimationFrame, no library, the contract's methods).
BEHAVIOUR checks run the real stage in node: the herb kit's real parts and the forge's real
parts, with only the WebGL renderer replaced by a fake that counts draw calls, and the clock,
requestAnimationFrame and timers simulated, so ten idle seconds take a few milliseconds. There
is no JavaScript test runner in the repo and adding one would be a dependency in an app that
bundles none; node is used the way test_bench_stage.py and test_bench_games.py use it, and the
behaviour checks skip without it.

Measured in the browser on 2026-10-04 (a scratch page serving these files, at 1280x720): the
kit settled to `raf: false` with 43 draw calls a frame and the smithy with 58, 0.45 to 0.7 ms
of script a frame; a cherry blank (850 °C) read as cherry red on the anvil, and a yellow one
(1,150 °C) lit the stump under it.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "play" / "static" / "js"
KIT = sorted((JS / "bench-stage").glob("*.js"))
PARTS = sorted((JS / "forge-stage").glob("*.js"))
STAGE = JS / "table" / "42-forge-stage.js"
CONTRACTS = (ROOT / "docs" / "blacksmithing-contracts.md").read_text(encoding="utf-8")
PRIOR = (ROOT / "docs" / "blacksmithing-prior-art.md").read_text(encoding="utf-8")
WEAPONS = ROOT / "content" / "weapons" / "weapons.json"

FILES = PARTS + [STAGE]
# The herb kit's parts the forge reuses as they are (contracts §10: "reuse 00-04 as is").
REUSED = [p for p in KIT if p.name[:2] in ("00", "01", "02", "03", "04")]


def _src(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _code(text: str) -> str:
    """Source with comments stripped, so prose that names a thing is not mistaken for it.

    The stage's header says "the only place requestAnimationFrame is called" in plain words;
    a check that counted that would fail on the sentence explaining the rule. String literals
    are kept.
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
        if c == "/" and _regex_starts(out):
            # A regex literal: copy it whole, so a quote inside it does not open a string.
            j = i + 1
            in_class = False
            while j < n:
                d = text[j]
                if d == chr(92):
                    j += 2
                    continue
                if d == "[":
                    in_class = True
                elif d == "]":
                    in_class = False
                elif d == "/" and not in_class:
                    break
                j += 1
            out.append(text[i:j + 1])
            i = j + 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _regex_starts(out) -> bool:
    k = len(out) - 1
    while k >= 0 and out[k] in " \t":
        k -= 1
    return k < 0 or out[k] in "(,=:[!&|?{};" + chr(10)


ALL_CODE = {p.name: _code(_src(p)) for p in FILES}


def _strings(code: str):
    return re.findall(r'"((?:[^"\\]|\\.)*)"|' + r"'((?:[^'\\]|\\.)*)'", code)


# --- no library, no download, no stray glyphs --------------------------------------------

def test_no_third_party_library_is_referenced():
    """The app bundles no third-party JavaScript (bench-stage/00-math.js's header records why:
    an offline executable, no CDN). A forge stage that reached for THREE, an import, a require
    or any URL would fail offline in the packaged app. The UI plan's CC0 textures are painted
    instead (03-smithy.js), so nothing here may fetch an image either."""
    for name, code in ALL_CODE.items():
        assert not re.search(r"\bTHREE\b", code), name + " references THREE"
        assert not re.search(r"\b(import|require)\s*\(", code), name + " loads a module"
        assert not re.search(r"^\s*import\s", code, re.M), name + " uses an ES import"
        assert "http://" not in code and "https://" not in code, name + " fetches from a URL"
        for ext in (".gltf", ".glb", ".png", ".jpg", ".webp", ".ktx"):
            assert ext not in code, name + " loads a " + ext + " file"
        assert "new Image(" not in code and "fetch(" not in code, name + " downloads something"


def test_no_hand_written_svg():
    """Icons and art are not hand-drawn SVG (UI plan §4, the skill's icon rule); the stage is
    WebGL and painted textures."""
    for p in FILES:
        text = _src(p).lower()
        assert "<svg" not in text and "createelementns" not in text and "2000/svg" not in text, p.name


def test_no_em_dashes_in_strings():
    """No em-dash or en-dash in any string the stage carries (UI plan §8: no em-dashes in new
    strings). Measured on this lane's first draft: zero, and this keeps it there."""
    for name, code in ALL_CODE.items():
        for a, b in _strings(code):
            s = a or b
            assert chr(0x2014) not in s and chr(0x2013) not in s, name + " string: " + s[:60]


def test_the_reused_herb_parts_are_untouched_by_name():
    """Contracts §10: U4 reuses bench-stage/00-04 AS IS and owns only forge-stage/ and 42. The
    forge parts reach the herb kit only through window.BenchStageKit and never write to it, so
    the herb bench cannot be changed by loading the forge."""
    for name, code in ALL_CODE.items():
        assert not re.search(r"BenchStageKit\s*=", code), name + " assigns the herb kit"
        assert not re.search(r"\bK\.(math|mesh|Renderer|ground|Particles|props|tools)\s*=", code), name + " overwrites a herb part"


# --- the contract -----------------------------------------------------------------------

def _contract_methods():
    sec = CONTRACTS[CONTRACTS.index("**Stage (U4 provides, U2 calls).**"):CONTRACTS.index("**Ledger (U5 provides")]
    sig = sec[sec.index("`available()"):sec.index("Without WebGL")]
    return sorted(set(re.findall(r"(\w+)\(", sig)))


def test_forgestage_exposes_every_contract_method():
    """Every method in contracts §11 is on window.ForgeStage, in BOTH branches.

    U2 builds against the contract alone; a missing method would only show at merge. The
    second branch is the one taken when the stage's parts failed to load, and it must answer
    the same calls or U2's flat fallback throws instead.
    """
    methods = _contract_methods()
    assert methods == sorted(["available", "mount", "unmount", "setScene", "setTool", "setWork", "heat",
                              "game", "flourish", "productRect", "reducedMotion"]), methods
    code = ALL_CODE[STAGE.name]
    tail = code[code.index("window.ForgeStage = READY"):]
    ready, fallback = tail.split(" : {", 1)
    for m in methods:
        assert re.search(r"\b" + m + r"\s*:", ready), "ForgeStage." + m + " missing"
        assert re.search(r"\b" + m + r"\s*:", fallback), "fallback ForgeStage." + m + " missing"


def test_gameview_has_the_four_methods():
    """game(method) returns {update, hit, miss, end}, the herb stage's GameView (§11: "mirrors
    BenchStage"), and an inert one when anything goes wrong."""
    code = ALL_CODE[STAGE.name]
    game = code[code.index("function game("):code.index("function flourish(")]
    for m in ("update", "hit", "miss", "end"):
        assert re.search(r"\b" + m + r"\s*:", game), "GameView." + m + " missing"
    assert re.search(r"NOGAME\s*=\s*\{\s*update", code), "no inert GameView for the fallback"


def test_every_contract_sound_is_played_guarded():
    """The stage plays its flourish sounds through window.Sound on the forge bus (UI plan §11),
    through one guarded helper: Sound may be absent, and U6's bus is silent for unknown names."""
    code = ALL_CODE[STAGE.name]
    for name in ('"forge.drop." +', '"forge.tier.up"', '"forge.flawless"', '"forge.fail"', '"forge.land"'):
        assert "sound(" + name in code, "never plays " + name
    assert "window.Sound && typeof window.Sound.play" in code
    assert "Sound.play(" not in code.replace("window.Sound.play(name)", "")


# --- render on demand -------------------------------------------------------------------

def test_requestanimationframe_only_from_the_dirty_path():
    """No unconditional animation loop: one rAF call in the whole stage, inside wake().

    UI plan §7.4: idle, the bench draws no frames. That holds because the only rAF lives in
    wake() (marked FORGE-STAGE-RAF) and frame() asks for the next only under `if (busy)`
    (marked DIRTY-ONLY). The hearth's flicker would be a loop for ever if it scheduled its own
    frames; it is a term inside step() that only runs while a game is live.
    """
    total = sum(len(re.findall(r"requestAnimationFrame\s*\(", c)) for c in ALL_CODE.values())
    assert total == 1, "requestAnimationFrame is called %d times; only wake() may" % total
    raw = _src(STAGE)
    marker = raw.index("FORGE-STAGE-RAF")
    wake = raw.index("function wake()")
    assert 0 < wake - marker < 300, "the FORGE-STAGE-RAF marker no longer sits on wake()"
    code = ALL_CODE[STAGE.name]
    w = code[code.index("function wake()"):code.index("function frame(")]
    assert "requestAnimationFrame(frame)" in w
    assert re.search(r"if \(S\.raf \|\| !S\.mounted \|\| S\.lost\) return;", w), "wake() lost its guard"
    f = code[code.index("function frame("):code.index("function tween(")]
    assert "DIRTY-ONLY" in raw[raw.index("function frame("):raw.index("function tween(")]
    assert re.search(r"if \(busy\) wake\(\);", f), "frame() re-schedules unconditionally"
    for name, c in ALL_CODE.items():
        assert "setInterval(" not in c, name + " polls with setInterval"


def test_the_flicker_is_gated_on_a_live_game():
    """The flicker term is computed only inside liveStep, which step() calls only while a game
    is sending states (`isLive`), and it falls back to 1 otherwise (UI plan §7.4)."""
    code = ALL_CODE[STAGE.name]
    step = code[code.index("function step("):code.index("function liveStep(")]
    assert "var live = isLive(t);" in step and "liveStep(dt, t / 1000)" in step
    assert "S.flick = 1;" in step
    assert re.search(r"return S\.gameOn && \(t - S\.gameLast\) < 300", code)
    assert code.count("S.flick = 1 + ") == 1


def test_device_pixel_ratio_is_capped_at_two():
    """DPR-aware, capped at 2 and again at 4K worth of pixels (the herb stage's measurement:
    3440x1440 at a ratio of 2 would be five times 1080p's fill)."""
    code = ALL_CODE[STAGE.name]
    r = code[code.index("function resize()"):]
    assert "Math.min(2, window.devicePixelRatio || 1)" in r
    assert "MAX_PIXELS" in r


def test_context_loss_is_claimed_and_recovered():
    """webglcontextlost is preventDefault-ed (Khronos HandlingContextLost) or the browser never
    offers the context back; the herb renderer rebuilds every handle on restore."""
    code = ALL_CODE[STAGE.name]
    lost = code[code.index("function onLost("):code.index("function onRestored(")]
    assert "e.preventDefault()" in lost
    assert '"webglcontextlost"' in code and '"webglcontextrestored"' in code


def test_the_canvas_takes_no_input_and_only_it_shakes():
    """The stage never blocks a menu (UI plan §10, the one-second rule): the canvas has
    pointer-events: none, and the Flawless shake is a transform on the stage canvas alone."""
    code = ALL_CODE[STAGE.name]
    assert "pointer-events:none;" in code
    fl = code[code.index("function flourish("):code.index("function land(")]
    assert "cv.style.transform" in fl
    for target in ("document.body", "document.documentElement", "S.host.style.transform"):
        assert target not in fl, "a flourish moves " + target


def test_reduced_motion_drops_particles_shake_and_flicker():
    """Reduced motion: no particles (the emitter refuses), no shake, a crossfade instead of a
    drop, and the hearth does not flicker (UI plan §13.2)."""
    code = ALL_CODE[STAGE.name]
    emit = code[code.index("emit: function"):code.index("function draw(")]
    assert "if (S.reduced" in emit, "particles are emitted under reduced motion"
    fl = code[code.index("function flourish("):code.index("function land(")]
    assert "shook = !S.reduced" in fl
    sw = code[code.index("function setTool("):code.index("function finishSwap(")]
    assert "if (S.reduced)" in sw and "tween(120" in sw
    live = code[code.index("function liveStep("):code.index("function buildSet(")]
    assert "if (!S.reduced)" in live


def test_the_swap_timing_is_the_plan_s():
    """Old tool lifts out in 180ms; the new one drops in 450ms with a 4% overshoot (UI plan
    §10, "tools swap on the rack"), and a swap can never hang in a background tab."""
    code = ALL_CODE[STAGE.name]
    sw = code[code.index("function setTool("):code.index("function finishSwap(")]
    assert "tween(180" in sw and "lead + 450" in sw and "0.04 * Math.cos" in sw
    assert "setTimeout(" in sw


def test_mesh_and_texture_ids_cannot_collide_with_the_herb_kit():
    """The renderer keys GPU buffers by mesh id and textures by record id (01-gl.js). A second
    mesh counter in the forge parts would hand out ids 02-meshes.js had already used, and two
    meshes would share one buffer; so every forge mesh is finished through K.mesh.merge, and the
    painted smithy textures count from 9001, far above 03-ground.js's handful."""
    for name, code in ALL_CODE.items():
        assert "nextId" not in code, name + " keeps its own mesh id counter"
    assert "G.merge([{ mesh: raw" in ALL_CODE["01-props.js"]
    assert "nextTex = 9001" in ALL_CODE["03-smithy.js"]


# --- heat, by the prior art --------------------------------------------------------------

def _prior_table(heading: str, cols: int):
    sec = PRIOR[PRIOR.index(heading):]
    sec = sec[:sec.index("\n### ", 5)]
    rows = re.findall(r"^\|([^|\n]+)\|([^|\n]+)\|" + ("([^|\n]+)\\|" if cols == 3 else "") + r"\s*$", sec, re.M)
    out = []
    for r in rows:
        name, temp = r[0].strip(), r[1].strip()
        if name in ("Colour",) or set(name) <= set("-"):
            continue
        out.append((name, temp))
    return out


@pytest.fixture(scope="module")
def node():
    exe = shutil.which("node")
    if not exe:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    return exe


_HEAT_NODE = r"""
const fs = require('fs'), vm = require('vm');
const files = JSON.parse(process.argv[2]);
const sb = { window: {}, Math, JSON, Object, Array, Float32Array, Uint8Array, Uint16Array, console, isFinite };
sb.window.window = sb.window;
vm.createContext(sb);
for (const f of files) vm.runInContext(fs.readFileSync(f, 'utf8'), sb, { filename: f });
const H = sb.window.ForgeStageKit.heat;
const out = { bands: H.BANDS.map(b => [b.name, b.lo, b.hi]), temper: H.TEMPER.map(t => [t.name, t.c]), bath: H.BATH };
out.emit = [300, 450, 600, 850, 1000, 1150, 1300, 1400].map(c => [c, H.emit(c), H.light(c), (H.band(c) || {}).name || null]);
function secs(c0, c1, o) { let c = c0, t = 0; while (c > c1 && t < 600) { c = H.cool(c, 0.05, o); t += 0.05; } return t; }
out.cool = { thick: secs(1100, 800, {}), thin: secs(1100, 800, { thin: 1 }), narrow: secs(1100, 800, { narrow: true }),
             steady: secs(1100, 800, { steady: true }), low: secs(600, 500, {}), high: secs(1200, 1100, {}),
             floor: H.cool(100, 1e6, {}) };
out.reheat = { one: H.reheat(700, 1150, 1), two: H.reheat(700, 1150, 2) };
out.quench = ['brine', 'water', 'oil', 'air'].map(b => [b, H.quench(850, 1, b)]);
out.phase = [[850, 'water'], [850, 'brine'], [300, 'water'], [60, 'water'], [850, 'air']].map(a => H.quenchPhase(a[0], a[1]));
out.temperRun = H.temper(100), out.temperAt = [176, 260, 310, 400].map(c => H.temper(c));
process.stdout.write(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def heat_run(node, tmp_path_factory):
    script = tmp_path_factory.mktemp("forge") / "heat.js"
    script.write_text(_HEAT_NODE, encoding="utf-8")
    done = subprocess.run([node, str(script), json.dumps([str(PARTS[0])])], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout)


def test_heat_bands_match_the_prior_art(heat_run):
    """The heat colour table is the prior-art sweep's §3.1 (Chapman, Workshop Technology, 1972),
    name for name and degree for degree. Parsed from the doc, so an edit to either side that
    the other does not share fails here: a stage that called 900 °C "cherry" while the gauge's
    doc said "light cherry" would teach the player the wrong colour."""
    doc = _prior_table("### 3.1 Heat colour", 2)
    assert len(doc) == 9, doc
    bands = heat_run["bands"]
    assert len(bands) == len(doc)
    for (name, temp), (bname, lo, hi) in zip(doc, bands):
        assert name == bname, (name, bname)
        nums = [int(x.replace(",", "")) for x in re.findall(r"[\d,]+", temp)]
        if temp.endswith("+"):
            assert (lo, hi) == (nums[0], None), (name, lo, hi)
        else:
            assert (lo, hi) == (nums[0], nums[1]), (name, lo, hi)


def test_temper_colours_match_the_prior_art(heat_run):
    """The oxide colours are the sweep's §3.3 table, name and temperature."""
    doc = _prior_table("### 3.3 Tempering colours", 3)
    assert [(n, int(t.rstrip("+"))) for n, t in doc] == [tuple(x) for x in heat_run["temper"]]


def test_hot_metal_glows_by_its_band_and_goes_out_below_red(heat_run):
    """UI plan §7.2: below about 450 °C the emissive is off and the metal shows its own colour;
    above, the colour is the band's, red climbing through orange to near white, and the light
    the work throws grows with the fourth power of its temperature. Measured: 300 °C emits
    nothing, 850 °C is cherry red with red well over green, 1,300 °C is near white, and the
    light at 1,400 °C is more than ten times the light at 600 °C."""
    em = {c: (e, l, b) for c, e, l, b in heat_run["emit"]}
    assert em[300][0] == [0, 0, 0] and em[300][1] == [0, 0, 0] and em[300][2] is None
    assert em[850][2] == "Cherry red" and em[850][0][0] > 4 * em[850][0][1]
    assert em[1000][2] == "Orange" and em[1150][2] == "Yellow" and em[1400][2] == "White"
    assert min(em[1300][0]) > 0.5, em[1300][0]
    reds = [em[c][0][0] for c in (450, 600, 850, 1000)]
    assert reds == sorted(reds), "the glow does not brighten with heat"
    assert max(em[1400][1]) > 10 * max(em[600][1])


def test_cooling_follows_thickness_metal_and_steady_mode(heat_run):
    """Plan §7.2: thin pieces and narrow_window metals cool faster; Steady mode halves the rate.
    Radiation makes yellow heat fall faster than dull red (1,200 to 1,100 °C quicker than 600
    to 500 °C), and cooling never goes below the room. Measured at the default rate: a blank
    takes about 12.6 s to fall from 1,100 to 800 °C."""
    c = heat_run["cool"]
    assert 9 < c["thick"] < 16, c
    assert c["thin"] < c["thick"] * 0.6 and c["narrow"] < c["thick"] * 0.7
    assert c["steady"] > c["thick"] * 1.8
    assert c["high"] < c["low"]
    assert abs(c["floor"] - 20) < 1e-6


def test_reheat_takes_a_second_or_two(heat_run):
    """Reheat (R, or a click on the hearth) pushes the work back toward the hearth over "a
    second or two" (plan §7.2): most of the gap gone in one second, all but a few degrees in two."""
    r = heat_run["reheat"]
    assert 1150 - r["one"] < 0.3 * 450 and 1150 - r["two"] < 0.1 * 450, r


def test_quench_severity_is_grossmann_s_order(heat_run):
    """Prior art §3.2: brine > water > oil > air (Grossmann H), and the vapour jacket holds in
    water above about 400 °C while brine's salt breaks it."""
    q = dict(heat_run["quench"])
    assert q["brine"] < q["water"] < q["oil"] < q["air"], q
    assert heat_run["phase"] == ["jacket", "boil", "boil", "still", "dry"]


# --- the work, built from its pieces ---------------------------------------------------------

_FAMILY_NODE = r"""
const fs = require('fs'), vm = require('vm');
const files = JSON.parse(process.argv[2]), rows = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')).weapons;
const armour = JSON.parse(process.argv[4]);
const sb = { window: {}, Math, JSON, Object, Array, Float32Array, Uint8Array, Uint16Array, console, isFinite };
sb.window.window = sb.window;
vm.createContext(sb);
for (const f of files) vm.runInContext(fs.readFileSync(f, 'utf8'), sb, { filename: f });
const Fam = sb.window.ForgeStageKit.families;
const out = { families: Fam.FAMILIES, rows: {}, ids: {}, bad: [], maxVerts: 0 };
function check(id, plan) {
  ['head', 'haft', 'fittings', 'body', 'fastenings', 'lining'].forEach(s => {
    const pc = plan[s];
    if (!pc) return;
    if (Fam.FAMILIES.indexOf(pc.fam) < 0) out.bad.push(id + ':' + s + ':' + pc.fam);
    const b = Fam.build(pc.fam, pc.p);
    if (!b.meshes.length) out.bad.push(id + ':' + s + ': no mesh');
    b.meshes.forEach(m => {
      out.maxVerts = Math.max(out.maxVerts, m.pos.length / 3);
      for (const v of m.pos) if (!isFinite(v)) { out.bad.push(id + ':' + s + ': NaN position'); break; }
      for (const v of m.nrm) if (!isFinite(v)) { out.bad.push(id + ':' + s + ': NaN normal'); break; }
    });
  });
}
for (const r of rows) {
  const p = Fam.planFor('weapon', r);
  check(r.id, p);
  out.rows[r.id] = [p.head.fam, p.head.p.v || null, p.haft ? p.haft.fam : null, p.fittings ? p.fittings.p.v : null, p.by];
  const q = Fam.planFor('weapon', r.id);
  check(r.id + '(id)', q);
  out.ids[r.id] = q.head.fam;
}
out.armour = {};
for (const [gear, name] of armour) { const p = Fam.planFor(gear, name); check(name, p); out.armour[name] = [p.body.fam, p.body.p.v || null]; }
const bar = Fam.planFor('', ''); check('bar', bar); out.bar = [bar.head.fam, bar.head.p.v];
process.stdout.write(JSON.stringify(out));
"""


def _forged():
    from rules import blacksmith as bs
    return [["armour", a] for a in bs.FORGED_ARMOUR] + [["shield", s] for s in bs.FORGED_SHIELDS]


@pytest.fixture(scope="module")
def family_run(node, tmp_path_factory):
    script = tmp_path_factory.mktemp("forge") / "families.js"
    script.write_text(_FAMILY_NODE, encoding="utf-8")
    parts = [str(p) for p in KIT if p.name[:2] in ("00", "02")] + [str(p) for p in PARTS if p.name[:2] in ("00", "01", "02")]
    done = subprocess.run([node, str(script), json.dumps(parts), str(WEAPONS), json.dumps(_forged())],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout)


def test_the_families_are_the_plan_s_eleven(family_run):
    """UI plan §7.3 and the owner's §1 answer: the work is built from a fixed set of procedural
    families, no per-weapon models. Eleven, and every plan names only these."""
    assert family_run["families"] == ["blade.straight", "blade.curved", "axe", "hammer", "spear", "haft", "grip",
                                      "guard", "plate", "mail", "scale"]


def test_every_weapon_row_gets_a_shape(family_run):
    """UI plan §7.3: "weapons map to families through their table entry ... so all 456 rows get
    a shape without a model each". Every row of content/weapons/weapons.json, as a row and as a
    bare id (the record's `base`), gets a head from the eleven families, and every mesh it
    builds is finite and fits a 16-bit index buffer. The first run of this check found none
    failing; the measurement was 429 rows settled by name, 23 by components, 4 by damage type."""
    rows = json.loads(WEAPONS.read_text(encoding="utf-8"))["weapons"]
    assert len(family_run["rows"]) == len(rows) == 456
    assert family_run["bad"] == [], family_run["bad"][:10]
    assert family_run["maxVerts"] < 65536
    by = {}
    for fam, v, haft, fit, how in family_run["rows"].values():
        by[how] = by.get(how, 0) + 1
    assert by.get("type", 0) <= 10, by


@pytest.mark.parametrize("wid,head,haft,fitting", [
    ("longsword", "blade.straight", "grip", "cross"),
    ("greatsword", "blade.straight", "grip", "cross"),
    ("dagger", "blade.straight", "grip", "small"),
    ("rapier", "blade.straight", "grip", "basket"),
    ("scimitar", "blade.curved", "grip", "cross"),
    ("katana", "blade.curved", "grip", "disc"),
    ("glaive", "blade.curved", "haft", "collar"),
    ("battleaxe", "axe", "haft", "collar"),
    ("halberd", "axe", "haft", "collar"),
    ("warhammer", "hammer", "haft", "collar"),
    ("heavy-mace", "hammer", "haft", "collar"),
    ("longspear", "spear", "haft", "cap"),
    ("trident", "spear", "haft", "cap"),
])
def test_common_weapons_take_the_shape_a_smith_would_name(family_run, wid, head, haft, fitting):
    """Spot checks over the rows a player forges most: a longsword is a straight blade with a
    grip and a cross guard, a scimitar is curved, a halberd is an axe on a pole, a spear has a
    butt cap. The name rules come first because the components column calls a glaive's head
    "Blade/spike head", which the words alone would read as a straight blade."""
    fam, v, h, f, how = family_run["rows"][wid]
    assert (fam, h, f) == (head, haft, fitting), (wid, fam, h, f, how)
    assert family_run["ids"][wid] == head, "the bare id reads differently from the row"


def test_every_forged_armour_and_shield_shows_its_body(family_run):
    """Armour shows as its body piece on the anvil (plan §7.3): mail as a fold of rings, scale
    and splint as rows, plates as a shaped plate; shields as a disc or a kite. Every suit and
    shield rules/blacksmith.py lets a smith make has one."""
    a = family_run["armour"]
    assert a["chain shirt"][0] == a["chainmail"][0] == "mail"
    assert a["scale mail"] == ["scale", None] and a["splint mail"] == ["scale", "splint"]
    assert a["breastplate"] == ["plate", "breast"] and a["full plate"][0] == "plate"
    assert a["banded mail"] == ["plate", "banded"]
    assert a["buckler"] == ["plate", "round"] and a["heavy shield"] == ["plate", "kite"]
    assert len(a) == len(_forged())
    assert family_run["bar"] == ["plate", "bar"]


# --- the running stage, in node ---------------------------------------------------------------

_STAGE_NODE = r"""
const fs = require('fs'), vm = require('vm');
const files = JSON.parse(process.argv[2]), mode = process.argv[3], rows = JSON.parse(fs.readFileSync(process.argv[4], 'utf8')).weapons;
let T = 0;
const timers = [], rafs = [];
let rafCount = 0, warns = [];
function ctx2d(w, h) {
  const base = {
    createImageData: (a, b) => ({ data: new Uint8ClampedArray(a * b * 4) }),
    getImageData: (x, y, a, b) => ({ data: new Uint8ClampedArray(a * b * 4) }),
  };
  return new Proxy(base, { get: (t, k) => (k in t ? t[k] : () => {}), set: () => true });
}
function el(tag) {
  return {
    tag, style: {}, width: 0, height: 0, parentNode: null, className: '',
    setAttribute() {}, addEventListener() {}, removeEventListener() {},
    getContext: (type) => (type === '2d' ? ctx2d() : null),
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 1280, height: 720 }),
  };
}
const win = {
  performance: { now: () => T },
  requestAnimationFrame: (cb) => { rafCount++; rafs.push(cb); return rafs.length; },
  cancelAnimationFrame: () => {},
  devicePixelRatio: 1,
  addEventListener() {}, removeEventListener() {},
  getComputedStyle: () => ({ position: 'relative' }),
  console: { warn: (...a) => warns.push(a.join(' ')), log() {} },
  Sound: { play: (n) => sounds.push(n) },
};
const sounds = [];
win.window = win;
const sb = { window: win, document: { createElement: el }, performance: win.performance, Math, JSON, Object, Array,
             Float32Array, Uint8Array, Uint8ClampedArray, Uint16Array, Promise, Proxy, isFinite, getComputedStyle: win.getComputedStyle,
             setTimeout: (cb, ms) => { timers.push({ at: T + (ms || 0), cb }); return timers.length; },
             clearTimeout: () => {}, console: win.console };
sb.requestAnimationFrame = win.requestAnimationFrame;
vm.createContext(sb);
for (const f of files) vm.runInContext(fs.readFileSync(f, 'utf8'), sb, { filename: f });
const K = win.BenchStageKit;
let draws = 0, frames = 0, keys = [];
if (mode !== 'nogl') {
  K.supported = () => true;
  K.Renderer = function (cv) { this.canvas = cv; this.gl = { getExtension: () => null, isContextLost: () => false }; this.draws = 0; };
  K.Renderer.prototype = {
    init() { return true; }, resize(w, h) { this.canvas.width = w; this.canvas.height = h; },
    begin(f) { this.draws = 0; frames++; keys.push(f.keyCol[0]); },
    setBlend() {}, draw() { this.draws++; draws++; }, points(d, c) { if (c) { this.draws++; draws++; } },
    dispose() {}, forgetTexture() {},
  };
}
const FS = win.ForgeStage;
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
const PIECES = { head: { material: 'iron', color: '#8c8a86', passes: 0 }, haft: { material: 'ash-haft', color: '#6b4a2b' },
                 fittings: { material: 'bronze', color: [176, 141, 87] } };
async function timed(p) { const t0 = T; let done = false, val; p.then((v) => { done = true; val = v; }); while (!done && T - t0 < 5000) await advance(16); return { ms: T - t0, val }; }
(async () => {
  const out = { mode };
  if (mode === 'nogl') {
    out.available = FS.available();
    out.mount = await FS.mount(el('div'));
    const calls = [];
    try {
      FS.setScene({ kind: 'town' }); calls.push('setScene');
      calls.push('setTool:' + await FS.setTool('forge'));
      FS.setWork({ gear: 'weapon', base: 'longsword', pieces: PIECES, hot_c: 850 }); calls.push('setWork');
      FS.heat(900); calls.push('heat');
      const g = FS.game('forge'); g.update({ heat_c: 900, ring: 0.5 }); g.hit(1); g.miss(); g.end(); calls.push('game');
      calls.push('flourish:' + await FS.flourish('flawless'));
      calls.push('rect:' + JSON.stringify(FS.productRect()));
      FS.reducedMotion(true); calls.push('reducedMotion'); FS.unmount(); calls.push('unmount');
    } catch (e) { calls.push('THREW ' + e.message); }
    out.calls = calls;
    out.rafs = rafCount;
    process.stdout.write(JSON.stringify(out));
    return;
  }
  out.available = FS.available();
  const host = el('div'); host.clientWidth = 1280; host.clientHeight = 720; host.appendChild = (c) => { c.parentNode = host; }; host.removeChild = () => {};
  out.mount = await FS.mount(host);
  out.idle = {};
  for (const kind of ['kit', 'town', 'owned']) {
    FS.setScene({ kind, biome: 'forest', minute: 600 });
    await timed(FS.setTool('forge'));
    FS.setWork({ gear: 'weapon', base: 'longsword', quality_index: 2, hot_c: 850, pieces: PIECES });
    await advance(3000);
    const c = counters();
    await advance(10000);
    out.idle[kind] = Object.assign(since(c), { debug: FS._debug() });
  }
  // A live game: states every frame for two seconds, then nothing.
  FS.setScene({ kind: 'kit', biome: 'forest', minute: 1200 });
  await advance(2000);
  let g = FS.game('forge');
  keys = [];
  let flicks = new Set();
  let c = counters();
  for (let i = 0; i < 125; i++) { g.update({ heat_c: 1100, ring: (i % 30) / 30, struck: i % 30 === 0 }); if (i % 30 === 0) g.hit(0.8); await advance(16); flicks.add(FS._debug().flick.toFixed(4)); }
  out.live = Object.assign(since(c), { keys: Array.from(new Set(keys.map((k) => k.toFixed(4)))).length, flicks: flicks.size, particles: FS._debug().particles });
  c = counters();
  const stopAt = T;
  let lastFrame = 0, f0 = frames;
  while (T - stopAt < 6000) { const before = frames; await advance(16); if (frames > before) lastFrame = T - stopAt; }
  out.afterStop = { lastFrameMs: lastFrame, frames: frames - f0 };
  c = counters();
  await advance(10000);
  out.idleAfterGame = since(c);
  g.end();
  await advance(2000);
  // Reduced motion: the hearth does not flicker and nothing flies.
  FS.reducedMotion(true);
  g = FS.game('forge');
  flicks = new Set();
  for (let i = 0; i < 60; i++) { g.update({ heat_c: 1100, ring: 0.5 }); if (i % 20 === 0) g.hit(1); await advance(16); flicks.add(FS._debug().flick.toFixed(4)); }
  out.reduced = { flicks: flicks.size, particles: FS._debug().particles };
  g.end();
  FS.reducedMotion(false);
  await advance(3000);
  // Flourishes, each from rest.
  out.flourish = {};
  for (const k of ['tierUp', 'flawless', 'fail', 'quench', 'land']) {
    FS.setWork({ gear: 'weapon', base: 'longsword', quality_index: 2, hot_c: 850, pieces: PIECES });
    await advance(1500);
    const r = await timed(FS.flourish(k));
    out.flourish[k] = r;
    await advance(2500);
  }
  out.flourish.unknown = await timed(FS.flourish('nonsense'));
  // Every method has a tool; an unknown one says no.
  out.tools = {};
  for (const m of ['smelt', 'alloy', 'forge', 'quench', 'temper', 'fold', 'hone', 'assemble', 'finish', 'strengthen', 'assay', 'grind']) {
    out.tools[m] = (await timed(FS.setTool(m))).val;
  }
  // Heat: cherry shows as cherry, cold glows not at all.
  FS.setScene({ kind: 'town' });
  await timed(FS.setTool('forge'));
  FS.setWork({ gear: 'weapon', base: 'longsword', quality_index: 2, hot_c: 850, pieces: PIECES });
  await advance(1500);
  out.cherry = FS._debug();
  FS.heat(20);
  await advance(1500);
  out.cold = FS._debug();
  // Assemble shows every piece; Forge only the blank.
  await timed(FS.setTool('assemble'));
  FS.setWork({ gear: 'weapon', base: 'longsword', quality_index: 2, hot_c: 20, pieces: PIECES });
  await advance(1000);
  out.assembled = FS._debug().pieces;
  await timed(FS.setTool('forge'));
  out.forging = FS._debug().pieces;
  // A piece dropped into a slot arcs to the anvil and seats, with its sound.
  await timed(FS.setTool('assemble'));
  FS.setWork({ gear: 'weapon', base: 'battleaxe', quality_index: 2, hot_c: 20, pieces: { head: PIECES.head } });
  await advance(800);
  const before = sounds.length;
  FS.setWork({ gear: 'weapon', base: 'battleaxe', quality_index: 2, hot_c: 20, pieces: { head: PIECES.head, haft: Object.assign({ form: 'haft' }, PIECES.haft) } });
  const arc = await timed(new Promise((res) => { const t0 = T; (function poll() { if (FS._debug().tweens === 0) res(T - t0); else sb.setTimeout(poll, 16); })(); }));
  out.drop = { sounds: sounds.slice(before), ms: arc.val, pieces: FS._debug().pieces };
  // Every weapon row, every slot, on the anvil, without a warning.
  warns = [];
  let empty = [];
  for (const r of rows) {
    FS.setWork({ gear: 'weapon', base: r, quality_index: 3, hot_c: 20, pieces: PIECES });
    if (!FS._debug().pieces.length) empty.push(r.id);
  }
  await advance(500);
  out.rows = { n: rows.length, empty, warns: warns.slice(0, 5) };
  out.rect = FS.productRect();
  out.sounds = sounds;
  out.debug = FS._debug();
  FS.unmount();
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
"""


def _stage_files():
    return [str(p) for p in REUSED] + [str(p) for p in PARTS] + [str(STAGE)]


def _run_stage(node, tmp, mode):
    script = tmp / ("stage-" + mode + ".js")
    script.write_text(_STAGE_NODE, encoding="utf-8")
    done = subprocess.run([node, str(script), json.dumps(_stage_files()), mode, str(WEAPONS)],
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr[:3000]
    return json.loads(done.stdout)


@pytest.fixture(scope="module")
def stage_run(node, tmp_path_factory):
    return _run_stage(node, tmp_path_factory.mktemp("forge"), "gl")


@pytest.fixture(scope="module")
def nogl_run(node, tmp_path_factory):
    return _run_stage(node, tmp_path_factory.mktemp("forge"), "nogl")


def test_idle_draws_zero_frames(stage_run):
    """UI plan §7.4 and §13.5: idle, the hearth is lit steadily and the bench draws no frames;
    "a test pins zero frames over 10 idle seconds". Measured here, with the real stage on a
    counting renderer: after the scene settles, ten simulated seconds at the field kit, a town
    smithy and a founded one each ask for 0 animation frames and issue 0 draw calls, with a
    cherry-hot blank on the anvil (the heat is a colour, not a motion)."""
    assert stage_run["available"] is True and stage_run["mount"] is True
    for kind, r in stage_run["idle"].items():
        assert (r["rafs"], r["frames"], r["draws"]) == (0, 0, 0), (kind, r)
        assert r["debug"]["band"] == "Cherry red", (kind, r["debug"]["band"])
        assert r["debug"]["raf"] is False


def test_the_hearth_flickers_only_while_a_game_is_live(stage_run):
    """The flicker is the one motion that would keep the loop alive for ever (UI plan §7.4), so
    it runs only while a game sends states. Measured: 125 states over two seconds drew 125
    frames with the flicker taking 120 distinct values and 71 sparks and embers in the air; when
    the states stopped, the last frame came 1,584 ms later (the last embers dying), and the ten
    seconds after that drew nothing. Under reduced motion the flicker held one value and no
    particle flew."""
    live = stage_run["live"]
    assert live["frames"] >= 100 and live["keys"] > 20 and live["flicks"] > 20, live
    assert live["particles"] > 0, "a strike threw no sparks"
    assert stage_run["afterStop"]["lastFrameMs"] < 3000, stage_run["afterStop"]
    assert stage_run["idleAfterGame"] == {"rafs": 0, "draws": 0, "frames": 0}
    assert stage_run["reduced"] == {"flicks": 1, "particles": 0}, stage_run["reduced"]


def test_every_flourish_ends_inside_1_1_seconds(stage_run):
    """The one-second rule (UI plan §10): every flourish ends on its own inside 1.1 s, and an
    unknown one answers false at once. Measured on the simulated clock from the call to the
    promise resolving: tierUp 384 ms, flawless 704, fail 608, quench 912, land 1,056."""
    f = stage_run["flourish"]
    for k in ("tierUp", "flawless", "fail", "quench", "land"):
        assert f[k]["val"] is True, (k, f[k])
        assert f[k]["ms"] <= 1100, (k, f[k])
    assert f["unknown"]["val"] is False and f["unknown"]["ms"] <= 32
    for name in ("forge.tier.up", "forge.flawless", "forge.fail", "forge.quench", "forge.land"):
        assert name in stage_run["sounds"], name


def test_every_method_has_a_hand_tool(stage_run):
    """All eleven methods (contracts §7) set a tool on the stage; a method the forge does not
    have resolves false rather than leaving the stage half-swapped."""
    t = stage_run["tools"]
    assert all(t[m] is True for m in t if m != "grind"), t
    assert t["grind"] is False


def test_hot_metal_is_a_light_and_cold_metal_is_not(stage_run):
    """UI plan §7.2: the work's heat drives a point light; a cherry blank lights the anvil red
    and a cold one throws no light at all."""
    hot, cold = stage_run["cherry"], stage_run["cold"]
    assert hot["band"] == "Cherry red" and hot["glow"][0] > 0.5 and hot["glow"][0] > 4 * hot["glow"][1]
    assert cold["band"] is None and cold["glow"] == [0, 0, 0]


def test_assemble_shows_every_piece_and_forge_only_the_blank(stage_run):
    """The work is built from its pieces (UI plan §7.3): at Assemble the head, haft and
    fittings are all on the anvil; while the blank is being forged only the head is."""
    assert stage_run["assembled"] == ["head", "haft", "fittings"]
    assert stage_run["forging"] == ["head"]


def test_a_dropped_piece_arcs_in_with_its_sound(stage_run):
    """UI plan §10, "Drop into a slot: the piece arcs to the anvil and seats; a metal clink".
    Adding a haft to an axe head already on the anvil plays forge.drop.<form> once, and
    everything the drop starts is over inside half a second: the 320 ms arc, and the camera's
    450 ms ease out to frame the longer work (measured 480 ms to the last tween, at 16 ms frames)."""
    d = stage_run["drop"]
    assert d["sounds"] == ["forge.drop.haft"], d
    assert d["ms"] <= 500, d
    assert d["pieces"] == ["head", "haft"]


def test_every_weapon_row_reaches_the_anvil(stage_run):
    """All 456 weapon rows, handed to setWork as their table rows, put at least one piece on
    the anvil without a single warning from the stage."""
    r = stage_run["rows"]
    assert r["n"] == 456 and r["empty"] == [] and r["warns"] == [], r


def test_nothing_throws_without_webgl(nogl_run):
    """available() is false without WebGL, mount() resolves false, and every other call is a
    quiet no-op (contracts §11: "Without WebGL every call is a no-op"). Measured with the real
    herb renderer and canvas.getContext returning null."""
    r = nogl_run
    assert r["available"] is False and r["mount"] is False
    assert not any(c.startswith("THREW") for c in r["calls"]), r["calls"]
    assert r["rafs"] == 0
