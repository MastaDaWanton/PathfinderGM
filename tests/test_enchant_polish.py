"""The enchanting bench as one thing: what the final pass (2026-10-06) found between the lanes,
driving the whole bench end to end on scratch data with games, stage and sound live.

Each test names what was measured. The live pass: an Enchanter 4 prepared, attuned and bound
+1 flaming on a forged Superior longsword, collected it from In progress and wielded it; bound
a second FLAWED; identified it; unbound it for a quarter of its motes; answered a converted old
bane's foe on its card; at 1280x720, 1920x1080, 3440x1440 and a 390px phone, keyboard only and
under reduced motion. A temporary spy on Sound.play and on the stage's game view logged every
sound and every hit, miss and flourish.
"""
from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from test_enchant_api import _carry, _give, _step, circle, forged, post  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "play" / "static"
TABLE_JS = STATIC / "js" / "table"
SHELL = TABLE_JS / "45-enchant-shell.js"
STAGE = TABLE_JS / "47-enchant-stage.js"
FRAME = TABLE_JS / "33-bench-games.js"
VERDICT = TABLE_JS / "22-roll-verdict.js"
GAMES = STATIC / "js" / "enchant-games"
METHODS = ["prepare", "attune", "bind", "refine", "unbind", "cleanse"]


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)//.*$", "", line) for line in text.splitlines())


# --- words that match their numbers ------------------------------------------------------------

def test_the_step_dc_words_add_up_to_the_dc():
    """Read off the working's DC line in the live pass: "5 + 5 for rare essence" beside a DC
    of 20. Rare is the third step of rarity and the 5 is per step, so the words said 10 and
    the number said 20. Every rank's words now add up to its DC."""
    from rules import enchanter

    for rank in range(1, 6):
        (term,) = enchanter._step_dc_terms(rank, "essence")
        nums = [int(n) for n in re.findall(r"\d+", term["why"].split(" for ")[0])]
        total = nums[0] + (nums[1] * nums[2] if len(nums) == 3 else nums[1])
        assert total == term["dc"] == enchanter._step_dc(rank), term


def test_an_unchosen_bane_foe_is_said_once_and_without_dashes(circle):  # noqa: F811
    """The live pass seated a bane essence without naming its foe: the problems list said
    "choose its foe — one of aberration, ... — before it is bound" twice, once for the
    essence and once again from the layer's own plan. Said once, for the essence, plainly."""
    _carry(arcane_essence_i=1, bane_essence=1, consecrated_chalk=1, silver_ink=1)
    key = _give(forged())
    _step(circle, {"method": "prepare", "vessel": key,
                   "circle": ["inv:consecrated-chalk", "inv:silver-ink"]})
    chk = post(circle, "/api/enchant/check", {
        "method": "attune", "vessel": key,
        "seats": {"point": "inv:bane-essence", "edge": "inv:arcane-essence-i"}}).json()
    foe = [p for p in chk["problems"] if "choose its foe" in p]
    assert len(foe) == 1, chk["problems"]
    assert foe[0].startswith("Bane Essence: choose its foe (one of "), foe
    assert not any("—" in p for p in chk["problems"])
    # The seat names its phase, which the hour line reads (held by the vessel at Bind, the
    # essence is off the shelf and "Noon favours this essence" was all the page could say).
    seat = next(s for s in chk["seats"] if s["seat"] == "edge")
    assert seat["phase"] and seat["phase"] == seat["phase"].lower()


def test_no_server_prose_of_the_bench_carries_an_em_dash():
    """The lanes reported dashes in the bench's sentences ("choose its foe — ...", "you named
    it — ..."); the owner's copy has none. Every string the bench's server modules can send
    (docstrings aside) and every property's card text."""
    found = []
    for f in ("rules/enchanter.py", "rules/magic_layer.py", "rules/curses.py",
              "rules/knowledge.py", "play/enchant_views.py", "rules/inprogress.py"):
        tree = ast.parse((ROOT / f).read_text(encoding="utf-8"))
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef,
                                  ast.AsyncFunctionDef)) and n.body
                and isinstance(n.body[0], ast.Expr)
                and isinstance(n.body[0].value, ast.Constant)}
        found += [f"{f}:{n.lineno}" for n in ast.walk(tree)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str)
                  and "—" in n.value and id(n) not in docs]
    props = json.loads((ROOT / "content/rules/magic-properties.json").read_text(encoding="utf-8"))
    rows = props if isinstance(props, list) else props.get("properties", props)
    rows = rows.values() if isinstance(rows, dict) else rows
    found += [r.get("id") for r in rows if isinstance(r, dict) and "—" in str(r.get("text", ""))]
    assert not found, found


def test_the_forged_damage_term_names_its_piece():
    """Read off `damage_modifiers` with a Superior iron longsword in hand: "+4 Superior Iron
    Longsword", unexplained beside Str. Measured, it is no double count: the forge's own
    number for the iron head, 2 x 1.5 (one strengthening pass) x 1.5 (Superior) = 4.5, toward
    zero 4, the only damage term the sword adds. It is named for its piece now."""
    from rules import forge_items

    b = forge_items.build(forged())
    dmg = [s for s in forge_items.roll_specs(b) if s.get("target") == "damage"]
    assert [(s["amount"], s["label"]) for s in dmg] == [(4, "forged iron head")]
    cmd = next(s for s in forge_items.roll_specs(b) if s.get("target") == "cmd")
    assert cmd["label"] == "forged ash haft and brass guard"


# --- the Equipment tab ---------------------------------------------------------------------------

def _carried_rows():
    from play import campaign as cm
    from play.views import _carried

    return {r["key"]: r for r in _carried(cm.current().scene.pc())}


def test_a_binding_in_progress_offers_no_wield(circle):  # noqa: F811
    """Seen in the live pass: the longsword on the circle, eight days from bound, read "Wield"
    on the Equipment tab, a button the engine's wear door refuses ("is still binding"). The
    act is gone and the reason is the row's note. A forged weapon also said "for show, no
    effect in play, goes at the hands": it is a weapon for the hand, with its own numbers."""
    from play import campaign as cm
    from rules import inprogress

    key = _give(forged())
    row = _carried_rows()["iron-longsword"]
    assert [a["label"] for a in row["acts"]] == ["Wield"]
    assert row["kind"] == "weapon" and row["fits"] == "hand" and row["shelf"] == "weapons"
    assert row["line"].startswith("1d8 S, 19-20/x2") and "+4 damage (forged iron head)" in row["line"]
    pc = cm.current().scene.pc()
    now = int(cm.current().scene.clock_minutes)
    inprogress.begin(pc, key.split(":", 1)[1], craft="enchanter", minutes=8 * 1440, now=now,
                     label="Binding a +1 flaming longsword", doing="binding")
    row = _carried_rows()["iron-longsword"]
    assert row["acts"] == [] and row["in_progress"]
    assert row["note"].startswith("The Superior Iron Longsword is still binding; it is ready in")


# --- the page: sounds, the stage fed by the games, FLAWED on the mat -------------------------------

def test_the_shell_starts_the_sanctum_bed_and_stops_it():
    """U6 made `ambience.sanctum` and nothing started it (the spy logged no LOOP at all in the
    first open). The circle now plays the sanctum's bed at a sanctum and the ground's own
    elsewhere, swaps it when the place changes and stops it on close; live: "LOOP
    ambience.urban" on open, "STOP ambience.urban" / "LOOP ambience.sanctum" when the state
    said a sanctum, and STOP on close."""
    code = _code(_src(SHELL))
    assert 'w.sanctum ? "sanctum" : String(w.biome || "")' in code
    assert 'Sound.loop("ambience." + name)' in code
    assert re.search(r"closing: function \(\) \{\s*stopAmbience\(\);", code)


def test_read_and_identify_ring_once():
    """Counted with the spy: with the WebGL stage up, Identify rang `enchant.identify` twice,
    once as the die was thrown (the shell) and once in the stage's flourish. The shell rings it
    only for the flat stand-in now, so the live count was one."""
    code = _code(_src(SHELL))
    assert 'E.sound("enchant.read")' not in code and 'E.sound("enchant.identify")' not in code
    assert re.search(r'if \(!staged\) E\.sound\("enchant\." \+ kind\);', code)


def test_the_flat_and_staged_binding_both_sound():
    """The stage's `bind` flourish, the moment the plan spends its boldness on, played no sound
    at all, while the flat stand-in played `enchant.land` for the same result. Live after the
    fix: `enchant.land` with the flourish."""
    code = _code(_src(STAGE))
    body = code[code.index('kind === "bind"'):code.index('kind === "flawed"')]
    assert 'sound("enchant.land", ph)' in body


def test_a_forged_vessel_is_drawn_from_its_pieces():
    """Live: the Superior longsword lay in the circle as a pair of gloves. The shell passed
    the gear as the stage's `family`, which makes the stage skip the forge's pieces and read
    a wearable family off the "hands" slot."""
    code = _code(_src(SHELL))
    assert 'family: forged ? "" : v.gear' in code


def test_the_stage_reads_the_games_states():
    """Each game's state against what the stage reads (the spy logged them live): Prepare sent
    `placed` as a list, which the stage's count read as NaN, so a step lost to the clock never
    drew its part; Attune says `lit`, the stage waited for `matched`; Bind sent neither
    `window` nor `pour`, so the crest's arc sat at its default whatever the day phase widened
    it to; Unbind and Cleanse sent no `seq` or `picked`, so the circle always showed three
    sigils and a timed-out one never came out. Live after: three timed-out Prepare steps drew
    the whole circle (rings 1, sigils 9)."""
    code = _code(_src(STAGE))
    assert "Array.isArray(st.placed)" in code
    assert "s.matched !== undefined ? s.matched : s.lit" in code
    assert "sn.col = parseColor(s.color, sn.col)" in code
    assert "if (!same && S.flawed && is)" in code
    bind = _code(_src(GAMES / "bind.js"))
    assert "window: k.clamp(2 * hw / period, 0, 1)" in bind and "pour: k.clamp(poured / crests" in bind
    for m in ("unbind", "cleanse"):
        assert "seq: seq.slice(), picked: step" in _code(_src(GAMES / f"{m}.js")), m


_DRIVER = r"""
"use strict";
const fs = require("fs"), vm = require("vm");
const files = JSON.parse(process.argv[2]);
const played = [];
const sandbox = { window: {}, Math, JSON, Object, Array, Promise, console, performance: { now: () => 0 } };
sandbox.window.window = sandbox.window;
sandbox.window.Sound = { play: (n, o) => { played.push(n); } };
vm.createContext(sandbox);
for (const f of files) vm.runInContext(fs.readFileSync(f, "utf8"), sandbox);
const BG = sandbox.window.BenchGames;
const stub = new Proxy({}, { get(t, k) {
  if (k === "measureText") return (s) => ({ width: String(s).length * 6.5 });
  if (k === "createLinearGradient") return () => ({ addColorStop() {} });
  if (k in t) return t[k]; return () => {}; }, set(t, k, v) { t[k] = v; return true; } });
const out = {};
// Prepare, played right: every piece by its own key.
let s = BG.simulate({ method: "prepare", seq: ["chalk", "salt", "ink", "bell"], tuning: { seed: 3, difficulty: 0.4 } });
for (let f = 0; f < 60 * 60; f++) {
  s.game.draw(stub, 360, 88);
  const st = s.game.state();
  if (st.phase === "lay") s.press(String(st.pieces.indexOf(st.seq[st.step]) + 1));
  if (s.step(1 / 60)) break;
}
out.prepare = played.splice(0);
// One wrong piece, then nothing: the miss is the generic muffled bowl.
s = BG.simulate({ method: "prepare", seq: ["chalk", "ink", "bell"], tuning: { seed: 3, difficulty: 0.4 } });
for (let f = 0; f < 60 * 30; f++) {
  s.game.draw(stub, 360, 88);
  const st = s.game.state();
  if (st.phase === "lay" && st.step === 0 && !out.wrongDone) { s.press(String(st.pieces.findIndex(p => p !== st.seq[0]) + 1)); out.wrongDone = true; }
  if (s.step(1 / 60)) break;
}
out.missed = played.splice(0);
// Bind: the state carries the crest's arc and the pour.
s = BG.simulate({ method: "bind", tuning: { seed: 2, difficulty: 0.45, widen: 1.5 } });
let st0 = null;
for (let f = 0; f < 60 * 30; f++) {
  s.game.draw(stub, 360, 88);
  const st = s.game.state();
  if (!st0) st0 = st;
  if (!st.struck && st.offset_s >= 0) s.press("Space");
  if (s.step(1 / 60)) break;
}
out.bind = { first: st0, last: s.game.state() };
for (const m of ["unbind", "cleanse"]) {
  s = BG.simulate({ method: m, seq: ["sigil", "enhancement"], tuning: { seed: 2, difficulty: 0.4 } });
  for (let f = 0; f < 60 * 30; f++) { s.game.draw(stub, 360, 88); if (s.step(1 / 60)) break; }
  out[m] = s.game.state();
}
out.defs = {};
for (const m of %METHODS%) out.defs[m] = sandbox.window.BenchGameDefs[m].SOUNDS;
process.stdout.write(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def games_run(tmp_path_factory):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("polish") / "driver.js"
    script.write_text(_DRIVER.replace("%METHODS%", json.dumps(METHODS)), encoding="utf-8")
    files = [str(GAMES / f"{m}.js") for m in METHODS] + [str(FRAME)]
    done = subprocess.run([node, str(script), json.dumps(files)], capture_output=True, text=True,
                          encoding="utf-8", timeout=120)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout)


def test_prepare_rings_each_piece_as_what_it_is(games_run):
    """U6 defined `enchant.salt`, `enchant.ink` and `enchant.bell` and no game called them:
    every Prepare piece rang as chalk. Live after the fix, the spy logged chalk, ink, bell for
    a chalk-ink-bell circle."""
    assert games_run["prepare"] == ["enchant.chalk", "enchant.salt", "enchant.ink", "enchant.bell"]


def test_every_circle_game_misses_with_the_generic_bowl(games_run):
    """U6's generic `enchant.miss` (the same muffled bowl under a name that says what it is
    for) in place of `enchant.bind.miss` in all six games' SOUNDS."""
    assert all(games_run["defs"][m]["miss"] == "enchant.miss" for m in METHODS)
    assert games_run["missed"][0] == "enchant.miss"


def test_bind_tells_the_stage_its_window_and_pour(games_run):
    """The crest's arc as a fraction of a turn and the binding poured so far (see
    test_the_stage_reads_the_games_states). The arc is the band's own +-hw/period."""
    first, last = games_run["bind"]["first"], games_run["bind"]["last"]
    assert 0 < first["window"] < 1 and first["pour"] == 0
    assert 0 < last["pour"] <= 1


def test_unbind_and_cleanse_send_their_sequence_and_progress(games_run):
    for m in ("unbind", "cleanse"):
        st = games_run[m]
        assert st["seq"] == ["sigil", "enhancement"] and st["picked"] == 2, m


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_flawed_is_said_on_the_mat(tmp_path):
    """The roll mat said nothing on a FLAWED Bind: the table's verdict knew only success and
    failure, so the shell passed none and cast the word over the circle after the mat closed,
    while the player was reading the margin on the mat. Live after the fix: the mat's verdict
    line read "Flawed: it took, but something went wrong in the binding", the word stood over
    the die in the failing cast, and the bowl rang off its note (`enchant.flawed`)."""
    script = tmp_path / "v.js"
    script.write_text(
        "const window = {matchMedia: null};\nconst document = {};\n"
        + _src(VERDICT)
        + "\nprocess.stdout.write(JSON.stringify(["
          "verdictFlourish({verdict: 'flawed', natural: null}, false),"
          "verdictFlourish({verdict: 'flawed', natural: 20}, true)]));\n",
        encoding="utf-8")
    done = subprocess.run([shutil.which("node"), str(script)], capture_output=True, text=True,
                          timeout=30)
    assert done.returncode == 0, done.stderr[:2000]
    a, b = json.loads(done.stdout)
    assert a["kind"] == "flawed" and a["word"] == "Flawed" and a["good"] is False
    assert a["text"].startswith("Flawed: it took") and not a["sub"]
    assert b["still"] is True and not b["sub"]
    code = _code(_src(VERDICT))
    assert 'f.kind === "flawed" ? "enchant.flawed"' in code
    shell = _code(_src(SHELL))
    assert "flawedWord" not in shell
    assert "return { verdict: v.verdict, natural: null };" in shell
