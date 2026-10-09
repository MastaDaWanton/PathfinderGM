"""The harvest sheet and the harvest game (leather lane U2; docs/leatherworking-ui-plan.md §6.9,
§9, §11; contracts §11 row U2 and §11.1; the owner's answers of 2026-10-08).

`play/static/js/table/59-harvest.js` is "Harvest the carcass": one sheet over the table for every
craft the character has, opened from the scene panel's Harvest button (07-panels.js) and the
craft-action hub, on lane C's API (play/harvest_views.py). `play/static/js/leather-games/
harvest.js` is the knife game a hide is worked off with; it reports a DEFECT AREA and the server
turns that into the grade (rules/harvest.py `grade_of`).

Verified live on scratch data before these were written (2026-10-08, 1600x900, 1280x720 and
375x812): a wolf killed through the engine's damage op, its pelt taken from the scene panel's
button with the table's d20 and worked off to grade 1, a second Take refused "already been
taken"; a young red dragon (karkadon) listing red dragonhide as its only hide with its fire
danger said before the roll and rolled as its own die; a lantern archon asking "Take it" /
"Leave it" before any die; a dying wolf saying "finish it first"; a goblin never offered.

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
STATIC = ROOT / "play" / "static"
SHEET = STATIC / "js" / "table" / "59-harvest.js"
PANELS = STATIC / "js" / "table" / "07-panels.js"
FRAME = STATIC / "js" / "table" / "33-bench-games.js"
GAMES = STATIC / "js" / "leather-games"
KIT = GAMES / "00-kit.js"
GAME = GAMES / "harvest.js"
FLENSE = GAMES / "flense.js"
HERB_GRIND = STATIC / "js" / "bench-games" / "grind.js"
THEME = STATIC / "css" / "theme-v2.css"
BENCH_CSS = STATIC / "css" / "bench.css"
SOUND = STATIC / "js" / "sound.js"
UI_PLAN = ROOT / "docs" / "leatherworking-ui-plan.md"
TABLE = ROOT / "play" / "templates" / "play" / "table.html"
PLANETS = ["planet", "Planet", "Mars", "Saturn", "Jupiter", "Venus", "Mercury"]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _code(js: str) -> str:
    """A script without its comments, so a rule named in a comment is not mistaken for code."""
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return "\n".join(ln if "://" in ln else ln.split("//", 1)[0] for ln in js.splitlines())


def _strings(js: str) -> list[str]:
    return [a or b for a, b in re.findall(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'', _code(js))]


def _panel_block() -> str:
    """07-panels.js's Harvest part, from its heading to the controls."""
    js = _read(PANELS)
    return js[js.index('// --- "In the scene": Harvest'):js.index("// --- controls")]


def _fn(js: str, name: str) -> str:
    start = js.index(f"function {name}(")
    nxt = re.search(r"\n  function |\n  // --- ", js[start + 10:])
    return js[start:start + 10 + (nxt.start() if nxt else len(js))]


# --- the files and their wiring ------------------------------------------------------------------

def test_the_sheet_is_one_iife_on_the_bench_core():
    """The table's numbered scripts share one global scope (test_s6_panel_shell: no top-level
    function declared twice). The sheet leaves one name, `HarvestSheet`, and mounts its layer on
    BenchCore so Esc one layer at a time, the focus trap, the inert table behind and "Stop and
    keep what you have?" during the game are the core's, not a second copy that drifts (the
    reason 29-bench-core.js exists: two benches had grown two Esc handlers)."""
    js = _code(_read(SHEET))
    assert js.lstrip().startswith("(function () {") and js.rstrip().endswith("})();")
    assert "window.HarvestSheet = {" in js
    assert "C.mount({" in js and 'layer: "harvest"' in js
    assert "live: function () { return !!H.live; }" in js


def test_nothing_in_the_lanes_files_loops():
    """An idle table draws zero frames (UI plan §10, §13.6): the frame owns the one loop, only
    while a game runs. A timer or a frame request in the sheet or the panel's hook would run for
    as long as the table is open."""
    for src in (_code(_read(SHEET)), _code(_panel_block()), _code(_read(GAME))):
        for banned in ("setInterval", "requestAnimationFrame"):
            assert banned not in src


def test_no_dash_no_control_byte_no_planet():
    """UI plan §8: no em-dashes or en-dashes in new copy (whole files, comments included, since
    a comment's dash is copied into a string the next time it is reused); bash heredocs have
    written `\\b` into source as a literal backspace byte (CLAUDE.md); the owner: no planets."""
    for p, text in ((SHEET, _read(SHEET)), (GAME, _read(GAME)), (PANELS, _panel_block())):
        for ch in ("—", "–"):
            assert ch not in text, f"{p.name} has a dash"
        assert not [c for c in text if ord(c) < 32 and c not in "\n\r\t"], f"{p.name} has control bytes"
        code = _code(text)
        for word in PLANETS:
            assert not re.search(rf"\b{word}\b", code), f"{p.name} says {word!r}"


def test_help_never_opens_from_hover_or_focus():
    """The owner's emergency fix of 2026-10-08: a card opened by hovering or focusing a whole
    row covered the next rows and made the list unusable. Nothing in the sheet listens for the
    pointer passing over or focus arriving."""
    js = _code(_read(SHEET)) + _code(_panel_block())
    for ev in ("mouseenter", "mouseover", "pointerenter", "pointerover", "focusin", '"focus"'):
        assert ev not in js, ev


# --- the page never computes a number -------------------------------------------------------------

def test_the_page_never_turns_the_defects_into_a_grade():
    """Contracts §11.1: "the server, not the page, turns that into a grade". The game reports
    `defects` and the sheet posts it to api/harvest/finish and prints the server's
    `grade_words`; neither file holds the UNIDO bands (content/rules/harvest.json `grade_bands`)
    or compares a defect area against a threshold."""
    sheet, game = _code(_read(SHEET)), _code(_read(GAME))
    assert 'C.api("/api/harvest/finish", { token: live.token, defects: defects })' in sheet
    assert "f.grade_words" in sheet
    for src in (sheet, game):
        assert "grade_bands" not in src
        assert not re.search(r"defects\s*[<>]=?\s*0?\.\d", src)
    for s in _strings(_read(GAME)):
        assert not re.search(r"\bgrade\b", s, re.I), f"the game names a grade: {s!r}"


def test_take_sends_the_players_own_faces():
    """Every bench rolls the table's own d20 (Dice3D) and sends the face; the dangerous body's
    second rounds roll their own faces too (`danger_faces`, harvest_views `harvest_take`). The
    die then lands on the face the SERVER names, and a skill check passes no natural (CRB
    p.180: no natural 20 or 1 on a skill check)."""
    js = _code(_read(SHEET))
    roll = _fn(js, "roll")
    assert "dice.ask(" in roll and "dice.land(" in roll
    assert 'C.api("/api/harvest/take", body)' in roll
    assert "body.face = face" in roll and "body.danger_faces = faces" in roll
    assert "result: d.face" in roll and "result: r.roll.face" in roll
    assert "showVerdict({ verdict: v.verdict, natural: null }, rest)" in roll
    # The dangers are asked before the part's own die, so the order on the mat is the server's.
    assert roll.index("dangers.forEach") < roll.index('skill + " (harvest)"')


def test_the_keyboard_stays_on_the_mat_through_every_die():
    """Seen live, keyboard only (2026-10-08): on a dangerous body the danger's die landed and
    the throw disabled the mat's button, so the keyboard fell to <body>; Enter then did nothing
    and the player was stranded on a mat that said Close. Every land, the danger's and the
    part's, hands focus back to the mat once the die is at rest (29's `focusMat`), as rollD20
    does for every bench."""
    roll = _fn(_code(_read(SHEET)), "roll")
    assert roll.count("dice.land(") == 2
    assert roll.count("if (rest) rest.then(C.focusMat);") == 2


def test_the_deed_asks_before_any_die():
    """The deeds plan's UI note: skinning a good outsider or a good dragon is a bad deed, so the
    confirm shows BEFORE the roll ("Take it" / "Leave it", the safe one focused, Esc the safe
    one: the core's confirm). Asked once, before the body's first cut, which is when the deed
    is recorded (rules/harvest.py `take`: "once per carcass")."""
    js = _code(_read(SHEET))
    take = _fn(js, "take")
    assert "row.deed && first ? core.confirm({" in take
    assert 'ok: "Take it", cancel: "Leave it"' in take
    assert take.index("core.confirm(") < take.index("return roll(row, first)")
    assert "good-outsider" in _fn(js, "deedWho") and "good-dragon" in _fn(js, "deedWho")


def test_the_dangers_and_the_salt_are_said_before_the_roll():
    """The brief: before the roll, say in words the DC and terms, the dangers the body holds
    (the owner: exposed only on a miss by 5 or more), the salt needed and whether the pack covers
    it. A player who first learns of venom in the body from the wound has been told too late."""
    js = _code(_read(SHEET))
    d = _fn(js, "dangersHtml")
    assert "A miss by 5 or more and you are exposed; a smaller miss does no harm." in d
    assert "d.dc" in d and "d.faced" in d
    row = _fn(js, "rowHtml")
    assert "r.need_words" in row and "termsWords(r.terms)" in row and "saltWords(r, s)" in row
    assert "r.deed_words" in row
    salt = _fn(js, "saltWords")
    assert "r.salt_needed" in salt and "r.salt_covers" in salt


def test_no_hidden_property_reaches_the_page():
    """UI plan §6.7: a creature-derived property is a secret until Grade. The take's answer
    carries the landed stock's name, form, units and grade only; the sheet must not reach for
    anything inherited (rules/harvest.py `inherited`) or a hide's properties."""
    js = _code(_read(SHEET))
    for word in ("inherited", "properties", "resist", ".dr", "immun"):
        assert word not in js, word


# --- where it opens -------------------------------------------------------------------------------

def test_the_scene_panel_offers_harvest_only_on_a_carcass_out_of_a_fight():
    """UI plan §6.9: "Harvest" beside the downed creature's row, "only while the carcass is
    harvestable and the character has a craft that wants a part": the rows come from
    api/harvest (humanoids never listed, so nothing to refuse) with `parts > 0`. Never while a
    fight is on (the take refuses in a fight), and never without the sheet in the build. A body
    still breathing says "finish it first" (lane C measured a wolf at -12 after the last blow).
    The board is redrawn whole on every render, so the buttons are put back from the last
    answer and the server is asked again only when hit points, actors or the hour change."""
    js = _code(_panel_block())
    assert "!window.HarvestSheet || scene.in_encounter || !fallen" in js
    assert 'fetch("/api/harvest"' in js
    assert ".filter(b => b.parts > 0)" in js
    assert 'b.setAttribute("data-harvest-open", a.ref)' in js
    assert "still breathing: finish it first" in js
    assert "if (sig === HARVEST_BOARD.sig) return;" in js
    # A fresh answer replaces the old buttons: painted over, a wolf with nothing left on it
    # still offered Harvest after its last part was taken (seen live, 2026-10-08).
    assert 'row.querySelectorAll(".who-harvest, .who-breathing").forEach(el => el.remove());' in js
    # The sheet marks the board stale on close: the last part going changes no hit point.
    assert 'typeof harvestBoardStale === "function"' in _code(_read(SHEET))


def test_the_hub_gets_harvest_the_carcass_back():
    """Lane C took the four carcass excursions out of the craft-action hub; UI plan §13: "the
    hub shows Harvest the carcass in their place". The hub redraws its whole list on every open
    (03-offers-and-map.js), so the entry is put back by watching that list, disabled with the
    server's reason when there is nothing to take."""
    js = _code(_read(SHEET))
    hub = _fn(js, "hubEntry")
    assert 'host.querySelector("[data-hv-hub]")' in hub and "Harvest the carcass" in hub
    assert "btn.disabled = true" in hub and "finish it first" in hub
    assert "new MutationObserver(function () { hubEntry(); }).observe(hub, { childList: true })" in js


# --- the look ---------------------------------------------------------------------------------------

def _sheet_css() -> str:
    js = _read(SHEET)
    block = js[js.index("var CSS = ["):js.index('].join("\\n");')]
    return "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', block))


def test_the_sheet_keeps_the_colours():
    """The owner (2026-09-28): keep the app's colours, images and textures. The sheet's style is
    tokens only: no raw colour, and every token one theme-v2.css or the bench's layer defines."""
    css = _sheet_css()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
    assert not re.search(r"\b(rgb|rgba|hsl|hsla)\(", css)
    known = _read(THEME) + _read(BENCH_CSS)
    for tok in set(re.findall(r"var\((--[a-z0-9-]+)\)", css)):
        assert f"{tok}:" in known, tok
    assert "v2-card-leather" in _read(SHEET) and "v2-framed" in _read(SHEET)


def test_the_sheet_fits_the_window_at_every_size():
    """Measured live at 1280x720 (2026-10-08): with `max-height: 100%` on a sheet in an auto grid
    row, the game strip pushed the sheet past the window and its title and Close went off the top.
    The sheet is held to the viewport less its 16px gutters, its list scrolls inside it, and the
    game rises outside that list so it is always on screen. Under 560px the rows stack and the
    Take button drops under its words (phone width, no sideways scroll)."""
    css = _sheet_css()
    assert "max-height:calc(100dvh - 32px)" in css and "width:min(760px,100%)" in css
    assert "#harvest.bench{display:grid;" in css and "padding:16px" in css
    assert "overflow-y:auto;overflow-x:hidden" in css
    assert "@media (max-width:560px)" in css and "grid-template-columns:minmax(0,1fr)" in css
    html = _read(SHEET)
    assert html.index('id="harvest-body"') < html.index('id="harvest-game"')
    assert "scrollIntoView" not in _code(html)


def test_every_sound_is_on_the_leather_bus():
    """Contracts §11.1: unknown events are silent, so a typo is silence nobody hears. Every
    `leather.*` the sheet and the game play is one lane U6 defines in sound.js."""
    defined = set(re.findall(r'def\("(leather\.[a-z.-]+)"', _read(SOUND)))
    used = set(re.findall(r'"(leather\.[a-z.-]+)"', _code(_read(SHEET)) + _code(_read(GAME))))
    used.discard("leather.harvest")       # the game's registry key, not a sound
    assert used and used <= defined, sorted(used - defined)
    plan = _read(UI_PLAN)
    sec = plan[plan.index("## 11. Sound"):plan.index("## 12.")]
    assert "leather.knife" in sec and "pitch by hide surface" in sec


# --- the game ---------------------------------------------------------------------------------------

def test_the_game_registers_as_a_leather_game():
    """Contracts §11.1: the harvest game registers on the shared registry under
    `LeatherGames.key("harvest")` = "leather.harvest" with `track: "leather"`, a BAND in the
    server's unit (fraction of thickness, content/rules/harvest.json `game.band`), no holds
    (00-kit.js: every leather input is a press), and its sounds on the leather bus."""
    code = _code(_read(GAME))
    assert 'defs["leather.harvest"] = {' in code and 'id: "leather.harvest"' in code
    assert 'track: "leather"' in code
    assert re.search(r'BAND:\s*\{\s*unit:\s*"fraction"', code)
    assert "HOLDS: []" in code and "HOLDS_STEADY: []" in code
    assert "up: function" not in code
    assert "defects: function ()" in code
    for banned in ("requestAnimationFrame", "setInterval", "setTimeout", "addEventListener",
                   "Sound", "fetch(", "Math.random"):
        assert banned not in code, banned
    assert "k.reticle(" in code and "ctx.pointer" in code
    first = re.search(r'first:\s*"([^"]+)"', code).group(1)
    assert len(first) <= 110


def test_the_frame_hands_back_the_defects_only_for_a_game_that_has_them():
    """Contracts §11.1: "The harvest game also reports `defects` (0..1 area) so the server can
    grade it". The frame's result carries `defects` when, and only when, the game defines it,
    so the other forty-three games' results are exactly what they were; and the knife's sound
    is pitched by the hide's surface only when the tuning carries one."""
    code = _code(_read(FRAME))
    assert 'if (typeof r.game.defects === "function") out.defects = clamp(+r.game.defects() || 0, 0, 1);' in code
    assert 'if (typeof r.game.defects === "function") res.defects = clamp(+r.game.defects() || 0, 0, 1);' in code
    assert "if (tuning.surface) voice.surface = tuning.surface;" in code


_DRIVER = r"""// Node driver for tests/test_harvest_ui.py: the frame, the leather kit, the harvest game,
// Flense and a herb game, played through `BenchGames.simulate` (the frame's own headless step).
// Bots read only the state the game hands the stage, so a bot that wins proves the game can be
// won from what it shows.
"use strict";
const fs = require("fs"), vm = require("vm");
const files = JSON.parse(process.argv[2]);
const TUNING = JSON.parse(process.argv[3]);
const sandbox = { window: {}, Math, JSON, Object, Array, Promise, console, Infinity, performance: { now: () => 0 } };
sandbox.window.window = sandbox.window;
vm.createContext(sandbox);
for (const f of files) vm.runInContext(fs.readFileSync(f, "utf8"), sandbox);
const W = sandbox.window, BG = W.BenchGames;
const DT = 1 / 60;
const stub = new Proxy({}, { get(t, k) { if (k === "measureText") return (s) => ({ width: String(s).length * 6.5 });
  if (k in t) return t[k]; return () => {}; }, set(t, k, v) { t[k] = v; return true; } });

function sim(o) {
  o = o || {};
  const tuning = Object.assign({}, o.rare ? TUNING.rare : TUNING.common, { seed: o.seed || 5 });
  return BG.simulate(Object.assign({ method: "leather.harvest", tuning, band: tuning.band },
    o.steady ? { steady: true } : {}, o.opts || {}));
}
const mid = (b) => (b[0] + b[1]) / 2;
function hand(s) { return { tap(k) { s.press(k); s.release(k); },
  click(x, y) { s.pointer("move", x, y); s.pointer("down", x, y); s.pointer("up", x, y); },
  move(x, y) { s.pointer("move", x, y); } }; }
function perfect(s, io, m) {
  const st = s.game.state();
  const want = mid(st.band) * st.thick_soon - st.sway;
  if (m) { const y = st.top + want * st.unit; if (!st.started) io.click(100, y); else io.move(100, y); return; }
  if (!st.started) { io.tap("Space"); return; }
  if (st.aim < want - 0.03) io.tap("ArrowDown"); else if (st.aim > want + 0.03) io.tap("ArrowUp");
}
// A person: sees the state late, reads the drawn hide a quarter of a second ahead of the knife
// (not the bot's tenth), does not read the hand's sway, and presses a key at most four times a
// second.
function late(lag) { const q = [], last = {}; return (s, io) => {
  q.push({ t: s.t(), st: s.game.state() }); while (q.length > 1 && q[1].t <= s.t() - lag) q.shift();
  const st = q[0].st;
  const ok = (k) => { if (last[k] != null && s.t() - last[k] < 0.25) return false; last[k] = s.t(); return true; };
  const want = mid(st.band) * st.thick_ahead;
  if (!st.started) { if (ok("Space")) io.tap("Space"); return; }
  if (st.aim < want - 0.04) { if (ok("ArrowDown")) io.tap("ArrowDown"); }
  else if (st.aim > want + 0.04) { if (ok("ArrowUp")) io.tap("ArrowUp"); } }; }
function play(o) {
  o = o || {}; const s = sim(o); const io = hand(s); const bot = o.idle ? null : o.bot || perfect;
  let ended = false, f = 0;
  while (!ended && f < 3600) { s.game.draw(stub, o.width || 360, 88); if (bot) bot(s, io, o.mode === "mouse"); ended = s.step(DT); f++; }
  return Object.assign(s.result(), { seconds: +(f / 60).toFixed(3) });
}
const KEYS = W.BenchGameDefs["leather.harvest"].KEYS;
function mash(every) { let n = 0; return (s) => { n++; if (n % every === 0) KEYS.forEach((k) => { s.press(k); s.release(k); }); }; }
function holdAll() { let d = false; return (s) => { if (!d) { KEYS.forEach((k) => s.press(k)); d = true; } }; }
// The pointer parked at one height and clicked: the knife at one depth the whole way.
function parked(y) { let started = false; return (s) => { if (!started) { s.pointer("move", 100, y); s.pointer("down", 100, y); s.pointer("up", 100, y); started = true; } }; }

const out = { registered: BG.methodsFor("leather").indexOf("leather.harvest") >= 0,
  key: W.LeatherGames.key("harvest"), seeds: {} };
for (const seed of [1, 5, 9, 13]) {
  const r = out.seeds[seed] = {
    keys: play({ seed }), steady: play({ seed, steady: true }), mouse: play({ seed, mode: "mouse" }),
    mouse_steady: play({ seed, mode: "mouse", steady: true }), narrow: play({ seed, mode: "mouse", width: 220 }),
    rare: play({ seed, rare: true }), reduced: play({ seed, opts: { reducedMotion: true } }),
    sloppy: play({ seed, bot: late(0.15) }), idle: play({ seed, idle: true }), idle_steady: play({ seed, idle: true, steady: true }),
    mash: play({ seed, bot: mash(3) }), mash_fast: play({ seed, bot: mash(1) }), hold: play({ seed, bot: holdAll() }),
  };
  // The best a parked knife can do, over every height of the 88px meter.
  let best = 1;
  for (let y = 0; y <= 88; y += 2) best = Math.min(best, play({ seed, bot: parked(y) }).defects);
  r.parked_best = best;
}
const s0 = sim();
out.gauge = { unit: s0.gauge.unit, band: s0.gauge.band, fail: s0.gauge.fail, target: s0.gauge.target, text: s0.gauge.text() };
const sr = sim({ rare: true });
out.rare_band = sr.gauge.band;
// Steady mode never hears a release.
const ss = sim({ steady: true }); let ups = 0; const up = ss.game.up;
ss.game.up = function () { ups++; return up && up.apply(this, arguments); };
KEYS.forEach((k) => { ss.press(k); ss.release(k); }); ss.pointer("down", 100, 40); ss.pointer("up", 100, 40);
out.steady_ups = ups;
// Other games' results carry no `defects`.
const fl = BG.simulate({ method: "leather.flense", tuning: { seed: 5 } });
for (let i = 0; i < 60; i++) fl.step(DT);
const gr = BG.simulate({ method: "grind", tuning: { seed: 5 } });
for (let i = 0; i < 60; i++) gr.step(DT);
out.others = { flense: Object.keys(fl.result()), grind: Object.keys(gr.result()) };
process.stdout.write(JSON.stringify(out));
"""


def _tunings() -> dict:
    """The server's own tuning (harvest_views `_tuning`, from content/rules/harvest.json), for a
    common pelt and a rare one, so a change to the rule rows is what the bots play."""
    from play import harvest_views

    return {"common": harvest_views._tuning({"tier": "common", "material": "wolf-pelt"}, "quadruped"),
            "rare": harvest_views._tuning({"tier": "rare", "material": "wolf-pelt"}, "quadruped")}


@pytest.fixture(scope="module")
def node_run(tmp_path_factory):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    script = tmp_path_factory.mktemp("harvest") / "driver.js"
    script.write_text(_DRIVER, encoding="utf-8")
    files = [str(HERB_GRIND), str(KIT), str(FLENSE), str(GAME), str(FRAME)]
    done = subprocess.run([node, str(script), json.dumps(files), json.dumps(_tunings())],
                          capture_output=True, text=True, encoding="utf-8", timeout=600)
    assert done.returncode == 0, done.stderr[:3000]
    return json.loads(done.stdout)


def _grade(defects: float) -> int:
    from rules import harvest

    return harvest.grade_of(defects)


def test_the_game_comes_by_registration(node_run):
    """The sheet asks `LeatherGames.key("harvest")` and finds the game under that key, on the
    leather track: a key the sheet does not find is a hide that keeps its unplayed grade."""
    assert node_run["registered"] and node_run["key"] == "leather.harvest"


@pytest.mark.parametrize("seed", ["1", "5", "9", "13"])
@pytest.mark.parametrize("mode", ["keys", "steady", "mouse", "mouse_steady", "narrow", "rare", "reduced"])
def test_a_clean_knife_is_a_grade_one_hide(node_run, seed, mode):
    """A bot reading only the game's state, by keyboard, by mouse on a 360px and a 220px meter,
    in Steady mode, on a rare hide's narrowed band and with reduced motion, must leave a defect
    area the server grades 1 (content/rules/harvest.json: 0.02 or less). A perfect run that the
    bands cap at grade 2 would cap every hide a grade low (the alchemy lane measured Calcine at
    0.975 for nothing but crossing the band's rim on the way in)."""
    r = node_run["seeds"][seed][mode]
    assert r["defects"] <= 0.02 and _grade(r["defects"]) == 1, r
    assert r["score"] >= 0.99, r


@pytest.mark.parametrize("seed", ["1", "5", "9", "13"])
def test_a_clean_run_is_short(node_run, seed):
    """The owner: crafts' minigames are always played, so they are short (the KCD2 complaint,
    forge prior art §0). A clean run by keyboard and by mouse ends inside 7 seconds."""
    g = node_run["seeds"][seed]
    assert g["keys"]["seconds"] <= 7 and g["mouse"]["seconds"] <= 7, g["keys"]


@pytest.mark.parametrize("seed", ["1", "5", "9", "13"])
def test_an_idle_knife_is_a_reject(node_run, seed):
    """Pressing nothing tears the whole hide off by hand: a reject (grade 0, scraps). If doing
    nothing earned a grade, the game would be a wait, not a skill."""
    g = node_run["seeds"][seed]
    for mode in ("idle", "idle_steady"):
        assert _grade(g[mode]["defects"]) == 0, g[mode]
        assert g[mode]["score"] == 0


@pytest.mark.parametrize("seed", ["1", "5", "9", "13"])
def test_holding_or_mashing_every_key_earns_the_worst_grade_or_none(node_run, seed):
    """The owner's 2026-10-06 note on the herb games: cheating must not score well. Holding every
    key (repeat is not a press) or mashing them all (Up and Down cancel, Left and Right cancel)
    leaves the knife at its shallow start, dragging: measured 0.37 to 0.52 of the area over four
    seeds, grade 4 or a reject, never better."""
    g = node_run["seeds"][seed]
    for mode in ("hold", "mash", "mash_fast"):
        assert g[mode]["defects"] >= 0.3 and _grade(g[mode]["defects"]) in (0, 4), (mode, g[mode])


@pytest.mark.parametrize("seed", ["1", "5", "9", "13"])
def test_a_parked_knife_cannot_earn_grade_one(node_run, seed):
    """Measured on the first draft (2026-10-08): with the hide's thickness running only 0.74 to
    1.26, a pointer parked at one height left the knife in the clean band almost the whole way
    (0.000 defects, grade 1, on two of four seeds). The hide now runs thin to thick as a real one
    does (belly against butt), so the knife has to follow it: at the best of every height on the
    meter a parked knife leaves 0.037 to 0.132 of the area (grade 2 or 3), never 0.02 or less."""
    assert node_run["seeds"][seed]["parked_best"] > 0.02


def test_a_person_lands_between(node_run):
    """A hand a sixth of a second late and pressing four times a second (a person, not a bot)
    gets a usable hide, grade 1 or 2 (measured 0.000 to 0.041 of the area), well clear of the idle
    reject: the game can be played by someone watching it, not only by the bot. At one press
    moving the blade 0.06 a person fell behind the thinning hide and left a grade 3 (0.246)."""
    for seed, g in node_run["seeds"].items():
        assert _grade(g["sloppy"]["defects"]) in (1, 2), (seed, g["sloppy"])


def test_the_server_band_is_what_is_played(node_run):
    """The gauge is the server's band (harvest.json `game.band`, fraction of thickness), widened
    by the frame's generous start and never into the "through" band; a rare hide's `narrow`
    tightens it once (the forge's "better metal, tighter window")."""
    from rules import harvest

    band = harvest.rules()["game"]["band"]
    g = node_run["gauge"]
    assert g["unit"] == "fraction" and g["target"] == band["target"] and g["fail"] == band["fail"]
    assert g["band"][1] < g["fail"][0]
    assert "of thickness" in g["text"]
    rare = node_run["rare_band"]
    assert rare[1] - rare[0] < g["band"][1] - g["band"][0]


def test_steady_mode_never_hears_a_release(node_run):
    """Steady mode has no holds (the frame drops every release; Xbox guideline 107)."""
    assert node_run["steady_ups"] == 0


def test_only_the_harvest_game_reports_defects(node_run):
    """The frame adds `defects` to a result only for a game that defines it: Flense and the herb
    Grind come back exactly as before."""
    assert "defects" not in node_run["others"]["flense"]
    assert "defects" not in node_run["others"]["grind"]
    assert "defects" in node_run["seeds"]["5"]["keys"]


# --- the server path the sheet drives -------------------------------------------------------------

def test_the_rows_the_sheet_reads_are_what_the_server_sends(tmp_path):
    """The sheet reads these row fields by name (rowHtml, yieldWords, saltWords) and the take's
    answer by these keys (resultHtml, roll); a rename in harvest_views would leave a blank sheet
    with no error. Driven through the real routes on a real campaign: a wolf killed by the
    engine's damage op, its sheet, a take with the player's face, the game's defect area."""
    from django.test import Client, override_settings

    from play import campaign as cm
    from play import harvest_views
    from rules import bestiary
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        harvest_views._PENDING.clear()
        try:
            c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
            pc = c.scene.pc()
            pc.inventory.clear()
            pc.stock.clear()
            pc.inventory["curing-salt"] = 1
            wolf = c.scene.add(bestiary.instantiate("wolf", scene=c.scene))
            e = c.engine()
            e.run(e.validate([{"op": "damage", "actor": pc.ref, "visibility": "hidden",
                               "params": {"to": wolf.ref, "amount": 99, "type": "slashing"}}],
                             origin="author:test"))
            c.save()
            client = Client()
            here = json.loads(client.get("/api/harvest").content)
            assert {"ref", "name", "parts", "others"} <= set(here["carcasses"][0])
            assert "breathing" in here and "label" in here["clock"]
            sheet = json.loads(client.get(f"/api/harvest/{wolf.ref}").content)
            assert {"creature", "harvestable", "why", "parts", "taken", "others", "dangers",
                    "clock_words", "salt", "clock"} <= set(sheet)
            assert {"size", "cr", "dead_words", "keeps_words", "ref", "name"} <= set(sheet["creature"])
            pelt = next(r for r in sheet["parts"] if r["branch"] == "hide")
            assert {"key", "craft", "craft_word", "name", "tier", "skill", "dc", "bonus", "terms",
                    "need_words", "units_words", "minutes", "deed", "deed_words", "game",
                    "salt_needed", "salt_covers"} <= set(pelt)
            r = client.post("/api/harvest/take", data=json.dumps(
                {"creature": wolf.ref, "key": pelt["key"], "face": 18}), content_type="application/json")
            got = json.loads(r.content)
            assert r.status_code == 200, got
            assert {"roll", "verdict", "dangers", "part", "stock", "carried", "grade", "lost",
                    "salt_spent", "yielded", "deed", "token", "tuning", "mastery", "tells", "sheet",
                    "clock"} <= set(got)
            assert {"face", "bonus", "total", "dc", "success"} <= set(got["roll"])
            assert {"lines", "levelled"} <= set(got["mastery"])
            assert all({"why", "mp"} <= set(line) for line in got["mastery"]["lines"])
            assert got["tuning"]["band"]["unit"] == "fraction" and got["tuning"]["surface"]
            r = client.post("/api/harvest/finish", data=json.dumps(
                {"token": got["token"], "defects": 0.0}), content_type="application/json")
            done = json.loads(r.content)
            assert r.status_code == 200 and done["grade"] == 1 and done["grade_words"] == "grade 1"
        finally:
            cm._LIVE.clear()
            harvest_views._PENDING.clear()
