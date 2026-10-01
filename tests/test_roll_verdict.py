"""The roll's verdict: the success / failure flourish after the player's d20.

The owner, 2026-10-01: "I would like to have a success or Failure animation play after
rolling the D20 success with confetti maybe and something for failure."

What can go wrong with that, and what each test here holds:

  * **The browser working the verdict out for itself.** The popup is deliberately never
    told the number to beat on an opposed check: it is the other side's secret die
    (`dc_shown`, measured once as "beat: 8", the guard's Perception, shown before the
    player rolled Stealth). A flourish computed in the page would need that number. So the
    engine judges the face (`Engine._judge`) and `/api/roll` hands the page its
    judgement; the page's code never reads a `dc` at all.
  * **The wrong die's verdict.** A resumed list rolls other people's dice after the
    player's — an NPC's check, the guard's save against the PC's spell. Only the Roll
    built from the face the player sent is judged, held by identity.
  * **A full attack's coarse verdict.** An attack outcome says "hit" if ANY swing hit,
    so on a three-swing attack whose last swing missed it would have cheered a miss. The
    to-hit stage judges each d20 where it decides it.
  * **A natural 20 read as a success.** 1e excludes skill checks from the natural-20
    rule; a 20 that still misses is a failure and gets the failure flourish.
  * **A die with no verdict celebrated.** Damage, initiative: nothing.
  * **The flourish getting in the way** (the owner's standing rule: no motion that makes
    a menu harder to use). It is not awaited, takes no pointer, and under reduced motion
    plays no particles at all.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.test import Client, override_settings

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from tests._board import face_to_face

ROOT = Path(__file__).resolve().parents[1]
VERDICT_JS = ROOT / "play" / "static" / "js" / "table" / "22-roll-verdict.js"
TURNS_JS = ROOT / "play" / "static" / "js" / "table" / "04-combat-and-turns.js"


@pytest.fixture
def engine():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="the guildhand"))
    return Engine(s, Dice(seed=20261001))


def _run(engine, raw):
    return engine.run(engine.validate(raw, origin="author:test"))


def _check(band, **extra):
    return {"op": "check", "actor": "pc", "visibility": "player", "because": "testing",
            "params": {"skill": "stealth", "dc": {"band": band}, **extra}}


# --- the engine's judgement ---------------------------------------------------------------

def test_a_stated_check_is_judged_as_its_outcome_says(engine):
    """Stealth +9 against DC 15: a 13 makes it, a 2 does not, and the record agrees with
    the outcome's own verdict rather than being worked out a second time."""
    _run(engine, [_check("tough")])
    done = engine.resume(13)
    assert done.outcomes[0].verdict == "success"
    assert engine.judged == {"verdict": "success", "natural": 13}

    _run(engine, [_check("tough")])
    done = engine.resume(2)
    assert done.outcomes[0].verdict == "failure"
    assert engine.judged == {"verdict": "failure", "natural": 2}


def test_a_natural_20_on_a_skill_check_that_misses_is_a_failure(engine):
    """29 against DC 40. 1e: a 20 on a skill check is not an automatic success. The face
    may scale the flourish, never overturn the verdict."""
    _run(engine, [_check("nearly_impossible")])
    engine.resume(20)
    assert engine.judged == {"verdict": "failure", "natural": 20}


def test_an_opposed_check_is_judged_without_the_number_to_beat(engine):
    """The guard's Perception is a secret die; the popup is told `dc_shown: False`. The
    judgement carries the verdict and the face and nothing else, so nothing that reaches
    the page can be the opponent's number."""
    got = _run(engine, [{"op": "check", "actor": "pc", "visibility": "player",
                         "because": "sneaking", "params": {
                             "skill": "stealth",
                             "opposed_by": {"ref": "c1", "skill": "perception"}}}])
    assert got.awaiting["dc_shown"] is False
    done = engine.resume(11)
    assert set(engine.judged) == {"verdict", "natural"}
    assert engine.judged["verdict"] == done.outcomes[0].verdict


def test_only_the_players_own_die_is_judged(engine):
    """The player's check, then the guildhand's own check in the same list. Measured
    shape of the risk: the second roll is a d20 too, and a 'last d20 judged' rule would
    have reported the guildhand's result as the player's."""
    _run(engine, [_check("tough"),
                  {"op": "check", "actor": "c1", "because": "looking round",
                   "params": {"skill": "perception", "dc": {"band": "very_easy"}}}])
    done = engine.resume(1)
    assert [o.op for o in done.outcomes] == ["check", "check"]
    assert done.outcomes[1].verdict == "success"
    assert engine.judged == {"verdict": "failure", "natural": 1}


@pytest.fixture
def fight(engine):
    engine._ensure_encounter("pc")
    face_to_face(engine.scene)
    return engine


def _strike(fight):
    got = _run(fight, [{"op": "attack", "actor": "pc", "target": "c1", "params": {}}])
    assert got.awaiting and got.awaiting["die"] == "1d20", got.awaiting
    return got


def test_a_hit_is_judged_at_the_to_hit_and_the_damage_die_is_not(fight):
    """The to-hit d20 decides; the attack outcome does not exist yet (it suspends again
    for damage), so the stage judges it. The damage die that follows is nobody's
    success."""
    _strike(fight)
    after = fight.resume(16)          # under the rapier's 18-20, so no confirm
    assert fight.judged == {"verdict": "success", "natural": 16}
    assert after.awaiting and after.awaiting["die"] != "1d20", after.awaiting
    fight.resume(int(after.awaiting["min"]))
    assert fight.judged is None


def test_a_miss_and_a_natural_1_are_failures(fight):
    _strike(fight)
    fight.resume(1)
    assert fight.judged == {"verdict": "failure", "natural": 1}


# --- /api/roll hands it over ------------------------------------------------------------

@pytest.fixture
def table(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.seed = 20261001
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        thug = instantiate("thug", scene=c.scene, name="the thug")
        thug.ref = "c1"
        c.scene.add(thug)
        e = c.engine()
        e.run(e.validate([{"op": "begin_encounter",
                           "params": {"sides": {"pc": ["pc"], "them": ["c1"]}}}]))
        while c.scene.current_ref() != "pc":
            c.scene.advance_turn()
        face_to_face(c.scene)
        c.save()
        yield Client(), cm
        cm._LIVE.clear()


def _post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def test_the_roll_reply_carries_the_engines_verdict(table):
    """From the combat bar: strike, roll a natural 20, and the reply says success on a
    20; the damage die after it says nothing. The page plays from this field alone."""
    client, cm = table
    r = _post(client, "/api/combat/act",
              {"actions": [{"op": "attack", "target": "c1", "params": {}}],
               "label": "Strike", "end_turn": True})
    assert r.status_code == 200 and r.json()["awaiting"]
    hit = _post(client, "/api/roll", {"face": 20}).json()
    assert hit["rolled"] == 20
    assert hit["verdict"] == {"verdict": "success", "natural": 20}
    # Confirm and damage, whatever they are: none of the damage dice is judged.
    guard = 0
    while cm.current().scene.awaiting and guard < 6:
        prompt = cm.current().scene.awaiting
        reply = _post(client, "/api/roll", {"face": int(prompt["min"])}).json()
        if prompt["die"] != "1d20":
            assert reply["verdict"] is None, (prompt["label"], reply["verdict"])
        guard += 1


def test_a_miss_comes_back_as_a_failure(table):
    client, _ = table
    _post(client, "/api/combat/act",
          {"actions": [{"op": "attack", "target": "c1", "params": {}}],
           "label": "Strike", "end_turn": True})
    miss = _post(client, "/api/roll", {"face": 1}).json()
    assert miss["verdict"] == {"verdict": "failure", "natural": 1}


# --- the page -------------------------------------------------------------------------

def _code(text: str) -> str:
    """Source without its comments: the comments here name `dc` and `dc_shown` in order
    to say they are never read, and a test must not fail on the explanation."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return chr(10).join(l.split("//")[0] if l.strip().startswith("//") else l
                        for l in text.splitlines())


def test_the_page_never_reads_a_number_to_beat():
    """No `dc`, no `dc_shown`, no total compared with anything: the flourish is chosen
    from the server's verdict and the natural face, and from nothing else."""
    code = _code(VERDICT_JS.read_text(encoding="utf-8"))
    assert not re.search(r"\bdc\b", code), "the verdict script reads a DC"
    assert "dc_shown" not in code
    assert not re.search(r"\.total\b", code), "the verdict script reads a total"


def _send_roll() -> str:
    src = TURNS_JS.read_text(encoding="utf-8")
    start = src.index("async function sendRoll(")
    return src[start:src.index("\nasync function ", start + 10)]


def test_send_roll_plays_the_servers_verdict_and_waits_for_nothing():
    """The flourish is fed `state.verdict` (the reply's own field) and is never awaited:
    the next popup, the page's redraw and the player's next click wait on nothing it
    does."""
    fn = _code(_send_roll())
    assert "showVerdict(state.verdict" in fn
    assert "await showVerdict" not in fn


_STUB = r"""
const made = [];
const fakeEl = tag => ({
  tag, className: "", textContent: "", attrs: {}, kids: [],
  style: { setProperty(k, v) { this[k] = v; } },
  setAttribute(k, v) { this.attrs[k] = v; }, remove() { this.gone = true; },
  appendChild(el) { this.kids.push(el); },
  getContext: () => ({ setTransform() {}, clearRect() {}, fillRect() {}, beginPath() {},
    arc() {}, fill() {}, stroke() {}, moveTo() {}, lineTo() {}, save() {}, restore() {},
    translate() {}, rotate() {}, scale() {}, createRadialGradient: () => ({ addColorStop() {} }) }),
  getClientRects: () => [1],
  getBoundingClientRect: () => ({ left: 100, top: 200, width: 300, height: 40, bottom: 240 }),
});
let STILL = false;
const window = { matchMedia: () => ({ get matches() { return STILL; } }), devicePixelRatio: 1 };
const innerWidth = 1280, innerHeight = 800;
const performance = { now: () => 0 };
const frames = [];
const requestAnimationFrame = fn => { frames.push(fn); return frames.length; };
const document = {
  body: { appendChild: el => made.push(el) },
  createElement: tag => fakeEl(tag),
  querySelector: () => fakeEl("div"),
  querySelectorAll: () => [],
  getElementById: () => fakeEl("div"),
};
const setTimeout = () => 0;
let MARKED = null;
window.Dice3D = { mark: (id, f) => { MARKED = [id, f.text]; return MAT; } };
const Dice3D = window.Dice3D;
let MAT = null;
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on this machine")
def test_the_verdict_alone_chooses_the_flourish(tmp_path):
    """Run in node against the real script: which flourish each server answer earns, that
    no answer earns none and draws nothing, that reduced motion draws no particles, and
    that every flourish is over well inside 1.5s."""
    src = _STUB + VERDICT_JS.read_text(encoding="utf-8") + r"""
    (async () => {
      const out = {};
      const kinds = v => { const f = verdictFlourish(v, false); return f && f.kind; };
      out.kinds = [
        kinds({ verdict: "success", natural: 12 }), kinds({ verdict: "success", natural: 20 }),
        kinds({ verdict: "failure", natural: 20 }), kinds({ verdict: "failure", natural: 7 }),
        kinds({ verdict: "failure", natural: 1 }), kinds(null), kinds(undefined),
        kinds({ verdict: null }), kinds({ verdict: "hit", natural: 15 }),
      ];
      out.longest = Math.max(...Object.values(VERDICT_MS));

      // No verdict: nothing chosen, nothing made, no frame asked for.
      out.none = await showVerdict(null, Promise.resolve(1));
      out.noneMade = made.length; out.noneFrames = frames.length;

      // A success off the mat: the word and the canvas, and a frame loop started.
      const f1 = await showVerdict({ verdict: "success", natural: 14 }, Promise.resolve(3));
      out.offMat = [f1.kind, made.map(e => e.tag + "." + e.className + "#" + (e.id || "")),
                    frames.length > 0];

      // On the mat: the sentence goes into the mat's line (mark), and the big word stands
      // over the middle of the die the mat reports.
      made.length = 0; MAT = { left: 400, top: 300, width: 200, height: 200 };
      await showVerdict({ verdict: "failure", natural: 1 }, Promise.resolve(4));
      const w = made.find(e => /rv-word/.test(e.className));
      out.onMat = [MARKED, w.className, w.style.left, w.style.top,
                   w.kids.map(k => k.className + ":" + k.textContent)];
      MAT = null;

      // Reduced motion: the still word, and no canvas made or drawn.
      made.length = 0; frames.length = 0; STILL = true;
      const f3 = await showVerdict({ verdict: "success", natural: 20 }, null);
      out.still = [f3.still, f3.ms, made.map(e => e.className), frames.length];
      console.log(JSON.stringify(out));
    })();"""
    f = tmp_path / "verdict.js"
    f.write_text(src, encoding="utf-8")
    done = subprocess.run(["node", str(f)], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    got = json.loads(done.stdout.strip().splitlines()[-1])
    assert got["kinds"] == ["success", "triumph", "failure", "failure", "calamity",
                            None, None, None, None]
    assert got["longest"] < 1500
    assert got["none"] is None and got["noneMade"] == 0 and got["noneFrames"] == 0
    kind, els, looping = got["offMat"]
    assert kind == "success" and looping
    assert "div.rv-word is-good#" in els and "canvas.#rv-layer" in els, els
    assert got["onMat"] == [[4, "Failure on a natural 1"], "rv-word is-bad is-strong",
                            "500px", "400px", ["rv-w:Failure", "rv-sub:natural 1"]]
    still, ms, classes, frames = got["still"]
    assert still is True and ms < 1500 and frames == 0
    assert classes == ["rv-word is-good is-strong"], \
        "reduced motion made something besides the word"


def test_the_roll_log_does_not_print_the_other_sides_secret_roll():
    """Measured live 2026-10-01: an opposed Stealth check's line in the Rolls panel read
    "25 vs 3", and 3 was the guard's hidden Perception roll, the number `dc_shown` keeps
    off the popup. The log entry drops the target, and the margin that gives it back by
    subtraction; a stated DC beside the same kind of entry still shows."""
    from play.views import _player_visible_entry

    mine = {"total": 25, "visibility": "player", "die": "1d20"}
    theirs = {"total": 3, "visibility": "hidden", "die": "1d20"}
    opposed = _player_visible_entry({"kind": "turn", "outcomes": [{
        "op": "check", "verdict": "success", "margin": 22,
        "dc": {"value": 3}, "rolls": [mine, theirs]}]})
    got = opposed["outcomes"][0]
    assert got["dc"] is None and got["margin"] is None
    assert got["verdict"] == "success" and got["rolls"] == [mine]

    stated = _player_visible_entry({"kind": "turn", "outcomes": [{
        "op": "check", "verdict": "success", "margin": 10,
        "dc": {"value": 15}, "rolls": [mine]}]})
    assert stated["outcomes"][0]["dc"] == {"value": 15}
    assert stated["outcomes"][0]["margin"] == 10
