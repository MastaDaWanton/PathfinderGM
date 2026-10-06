"""The Enchanting circle's sounds and the In progress panel's (play/static/js/sound.js
`enchant` and `works` buses; enchanting UI plan §11, contracts §12-§13, lane U6).

Every bench calls `Sound.play("enchant.<event>", {phase})` and `Sound.play("works.ready")`
and never guards, because an unknown name is silent by contract. That contract is exactly
what lets a missing sound ship unnoticed: when this lane started, all six circle games, the
stage's five verdicts, the ledger's read and identify, and the In progress panel's two
calls were already in the code and every one of them was silent. These tests hold:

- every event UI plan §11 names, and every event another lane's code already calls, exists
  and builds sound, with and without a phase;
- the seat's pitch is keyed by the essence's DAY PHASE (the owner: no planets, "this is not
  earth"), ordered by the sun's height on a pentatonic, so any seats rung together agree;
- a flawed binding beats faster than a clean one, and a miss is choked, not rung;
- the chalk stays out of the 2-4 kHz squeak band;
- the Enchanting slider scales the enchant bus live; `works` rides on the Interface slider;
- the sanctum bed stops everything it started;
- nothing on the enchant bus is louder than a combat hit.

Behaviour runs the real prefs.js and sound.js in node against a stand-in Web Audio that
keeps every node, and skips without node, as tests/test_forge_sound.py does.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from rules import enchanter
from rules.sky import PHASES

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "play" / "static" / "js"
SOUND = JS / "sound.js"
PREFS = JS / "prefs.js"
HOME = ROOT / "play" / "templates" / "play" / "home.html"
UI_PLAN = ROOT / "docs" / "enchanting-ui-plan.md"
WORKS = JS / "table" / "37-works.js"
GAMES = JS / "enchant-games"

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

# The circle's methods, from the engine's own table of step builders.
METHODS = sorted(enchanter._BUILD)

# What the other wave-2 lanes' code calls, read from their branches on 2026-10-06 (the games
# are on build/enchanting-u2, the stage on -u3, the ledger on -u5, In progress on master of
# the batch). The games' SOUNDS are also read from the files below once they are merged.
CALLED = {
    # lane U2, every game's SOUNDS (hit, miss, and Attune's lift)
    "enchant.chalk", "enchant.seat", "enchant.unseat", "enchant.bind.hit",
    "enchant.bind.miss", "enchant.draw", "enchant.unpick",
    # lane U3, the stage's verdicts
    "enchant.tier.up", "enchant.flawless", "enchant.flawed", "enchant.fail", "enchant.land",
    "enchant.read", "enchant.identify",
    # lane U4, the In progress panel
    "works.ready", "works.collect",
    # this lane's generic miss, offered to U2 in place of `enchant.bind.miss` everywhere
    "enchant.miss",
}


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _promised() -> set[str]:
    """Every enchant, works and ambience sound UI plan §11 names, `<name>` filled with the
    engine's methods."""
    text = _read(UI_PLAN)
    i = text.index("## 11. Sound")
    sect = text[i:text.index("## 12.", i)]
    names = set()
    for raw in re.findall(r"`((?:enchant|works|ambience)\.[a-z.<>]+)`", sect):
        m = re.search(r"<(\w+)>", raw)
        if not m:
            names.add(raw)
            continue
        names.update(raw.replace(m.group(0), v) for v in METHODS)
    return names


def _called() -> set[str]:
    """CALLED, plus whatever the merged code actually calls: the games' SOUNDS values and
    37-works.js's `sound("works.…")`. A name added to a game later is checked here too."""
    names = set(CALLED)
    if GAMES.is_dir():
        for f in GAMES.glob("*.js"):
            for block in re.findall(r"SOUNDS:\s*\{([^}]*)\}", _read(f)):
                names.update(re.findall(r'"((?:enchant|works)\.[a-z.]+)"', block))
    if WORKS.exists():
        names.update(re.findall(r'sound\("((?:works|enchant)\.[a-z.]+)"\)', _read(WORKS)))
    return names


_FAKE = r"""
Math.random = () => 0.5;
const nodes = [];
// `value` assigned directly is logged as ["value", x], so a test can tell what a gain held
// before its first automation event (a real AudioParam plays its `value` until then).
function Param(v) { return { _v: v, calls: [],
  get value() { return this._v; },
  set value(x) { this.calls.push(["value", x]); this._v = x; },
  setValueAtTime(x, t) { this.calls.push(["set", x, t]); this._v = x; },
  exponentialRampToValueAtTime(x, t) {
    if (!(x > 0)) throw new Error("exponential ramp to " + x); this.calls.push(["exp", x, t]); },
  linearRampToValueAtTime(x, t) { this.calls.push(["lin", x, t]); },
  setTargetAtTime(x, t, k) { this.calls.push(["target", x, t]); this._v = x; },
  cancelScheduledValues() {} }; }
function Node(kind) { const n = { kind, to: null, stopped: false, stopAt: null, id: nodes.length,
  connect(d) { this.to = d; return d; }, disconnect() {},
  start() {}, stop(t) { this.stopped = true; this.stopAt = t; }, gain: Param(1),
  frequency: Param(440), Q: Param(1), playbackRate: Param(1), threshold: Param(0),
  knee: Param(0), ratio: Param(1), attack: Param(0), release: Param(0), type: "",
  buffer: null, loop: false };
  nodes.push(n); return n; }
class FakeContext {
  constructor() { this.state = "suspended"; this.currentTime = 0; this.sampleRate = 48000;
                  this.destination = Node("destination"); FakeContext.last = this; }
  resume() { this.state = "running"; return Promise.resolve(); }
  createGain() { return Node("gain"); }
  createBiquadFilter() { return Node("filter"); }
  createOscillator() { return Node("osc"); }
  createBufferSource() { return Node("source"); }
  createDynamicsCompressor() { return Node("compressor"); }
  createBuffer(ch, len, sr) { return { duration: len / sr,
    getChannelData: () => new Float32Array(len) }; }
}
const store = {};
const localStorage = {
  getItem(k) { return k in store ? store[k] : null; },
  setItem(k, v) { store[k] = String(v); },
};
const window = {
  AudioContext: FakeContext, localStorage,
  matchMedia: () => ({ matches: false, addEventListener() {} }),
  addEventListener() {}, removeEventListener() {},
};
const navigator = {};
const pending = [];
const setTimeout = (fn, ms) => { pending.push(fn); return pending.length; };
const clearTimeout = () => {};
const drain = () => { while (pending.length) pending.shift()(); };
// Every frequency an oscillator or a filter was set to by one play.
function freqs(from, kind) {
  const out = [];
  for (const n of nodes.slice(from)) {
    if (kind && n.kind !== kind) continue;
    if (n.kind !== "osc" && n.kind !== "filter") continue;
    for (const c of n.frequency.calls) if (c[0] === "set" || c[0] === "exp") out.push(c[1]);
  }
  return out;
}
// The oscillators one play built, each as [its start frequency, when it stops].
function oscs(from) {
  return nodes.slice(from).filter(n => n.kind === "osc")
    .map(n => [n.frequency.calls[0][1], n.stopAt]);
}
"""


def _node(tmp_path, body: str) -> dict:
    src = (_FAKE + _read(PREFS) + "\n" + _read(SOUND)
           + "\nconst Sound = window.Sound, PGMPrefs = window.PGMPrefs;\n" + body)
    f = tmp_path / "enchant_probe.js"
    f.write_text(src, encoding="utf-8")
    done = subprocess.run([NODE, str(f)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout.strip().splitlines()[-1])


# --- the bank ------------------------------------------------------------------------------

def test_the_plan_and_the_callers_name_the_events_this_file_checks():
    """A guard on the parses below: if UI plan §11 were reworded so the regex found nothing,
    the existence test would pass on an empty set. It named 26 sounds when written, plus a
    method family over the engine's six methods."""
    names = _promised()
    for n in ("enchant.open", "enchant.roll", "enchant.chalk", "enchant.salt", "enchant.ink",
              "enchant.bell", "enchant.seat", "enchant.unseat", "enchant.bind.hit",
              "enchant.bind.miss", "enchant.draw", "enchant.unpick", "enchant.tier.up",
              "enchant.flawless", "enchant.flawed", "enchant.fail", "enchant.land",
              "enchant.read", "enchant.identify", "works.ready", "works.collect",
              "ambience.sanctum"):
        assert n in names, n
    assert {f"enchant.method.{m}" for m in METHODS} <= names
    assert len(METHODS) == 6, METHODS
    assert {"works.ready", "works.collect"} <= _called()


@needs_node
def test_every_promised_and_every_called_event_exists_and_builds_sound(tmp_path):
    """Every enchant and works sound the plan promises or another lane's code calls plays and
    builds nodes, with no options, with each day phase, and with nonsense; an unknown
    enchant name answers false and builds nothing.

    The defect: on 2026-10-06 the six circle games, the stage's verdicts, the ledger and the
    In progress panel already called 16 enchant and works names, and `Sound.play` answered
    false to every one of them, silently, by contract. Running every synth also catches one
    that throws or ramps a gain to zero (a RangeError in real Web Audio)."""
    names = sorted(_promised() | _called())
    got = _node(tmp_path, "const names = " + json.dumps(names) + ";\n"
                + "const phases = " + json.dumps(list(PHASES)) + r""";
      Sound.unlock();
      const out = { missing: [], silent: [], loops: [] };
      for (const n of names) {
        drain();
        if (!Sound.has(n)) { out.missing.push(n); continue; }
        if (n.startsWith("ambience.")) {
          const l = Sound.loop(n);
          if (!l || typeof l.stop !== "function") out.loops.push(n);
          l.stop(); continue;
        }
        const opts = [undefined, { phase: "Saturn" }, { phase: null }, { volume: 0.5 }]
          .concat(phases.map(p => ({ phase: p })));
        for (const o of opts) {
          drain();
          const was = nodes.length;
          if (Sound.play(n, o) !== true || nodes.length === was) out.silent.push(n);
        }
      }
      drain();
      const was = nodes.length;
      out.unknown = [Sound.play("enchant.bind.crit"), Sound.play("enchant.method.knit"),
                     Sound.play("works.lost", { phase: "noon" })];
      out.unknownBuilt = nodes.length - was;
      console.log(JSON.stringify(out));""")
    assert got["missing"] == [], f"promised or called with no synthesizer: {got['missing']}"
    assert got["silent"] == [], f"built nothing: {sorted(set(got['silent']))}"
    assert got["loops"] == []
    assert got["unknown"] == [False, False, False] and got["unknownBuilt"] == 0


@needs_node
def test_a_seat_rings_at_its_phase_on_a_pentatonic_ordered_by_the_sun(tmp_path):
    """UI plan §11 promised `enchant.seat` "with pitch by planet (Saturn lowest, the Moon
    highest)"; the owner ruled no planets, so it is the essence family's day phase. Measured
    as the bowl's fundamental (the lowest oscillator above 300 Hz) per phase: midnight
    lowest, then night, dusk, dawn, afternoon, morning, noon, each a pentatonic degree
    (0 2 4 7 9 12 14 semitones), so two seats rung together never clash. Adjacent phases
    stand at least a whole tone apart, past the ±5% jitter. No phase, or one the game has
    never heard of, rings as dawn."""
    got = _node(tmp_path, "const phases = " + json.dumps(list(PHASES)) + r""";
      Sound.unlock();
      const ring = o => { drain(); const was = nodes.length;
        Sound.play("enchant.seat", o);
        return Math.min(...freqs(was, "osc").filter(f => f > 300)); };
      const out = { by: {} };
      for (const p of phases) out.by[p] = ring({ phase: p });
      out.none = ring({}); out.odd = ring({ phase: "Saturn" }); out.caps = ring({ phase: " NOON " });
      console.log(JSON.stringify(out));""")
    by = got["by"]
    order = ["midnight", "night", "dusk", "dawn", "afternoon", "morning", "noon"]
    assert sorted(PHASES) == sorted(order), "rules/sky.py's phases changed; re-key the bank"
    pitches = [by[p] for p in order]
    assert pitches == sorted(pitches), by
    import math
    steps = [round(12 * math.log2(f / by["midnight"]), 3) for f in pitches]
    assert steps == [0, 2, 4, 7, 9, 12, 14], steps
    assert all(b / a > 1.1 for a, b in zip(pitches, pitches[1:])), pitches
    assert abs(got["none"] / by["dawn"] - 1) < 0.01 and abs(got["odd"] / by["dawn"] - 1) < 0.01
    assert abs(got["caps"] / by["noon"] - 1) < 0.01


@needs_node
def test_a_flawed_bowl_beats_faster_and_a_miss_is_choked(tmp_path):
    """UI plan §11: `enchant.flawed` is "a bell slightly off its note", `enchant.bind.miss`
    "a muffled one". A singing bowl's modes are doublets split by 1-2% (Wang, Tsai and Wu,
    MATEC 2018: 700.0/712.5 Hz, 1123.4/1135.2 Hz), the slow beat of a good bowl. Measured
    here: the gap between the two oscillators of the fundamental's doublet, as a fraction,
    for a clean strike and a flawed one; the flawed one must beat at least twice as fast.
    And a miss's longest ring is under a quarter second where the hit's runs over a second:
    a miss that rang on would tell the ear the opposite of the words."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      const split = name => { drain(); const was = nodes.length;
        Sound.play(name, { phase: "dawn" });
        const fs = oscs(was).map(o => o[0]).filter(f => f > 300 && f < 900).sort((a, b) => a - b);
        return fs[fs.length - 1] / fs[0] - 1; };
      const longest = name => { drain(); const was = nodes.length;
        Sound.play(name, { phase: "dawn" });
        return Math.max(...oscs(was).map(o => o[1])); };
      console.log(JSON.stringify({
        hit: split("enchant.bind.hit"), flawed: split("enchant.flawed"),
        hitRing: longest("enchant.bind.hit"), missRing: longest("enchant.bind.miss"),
        genericRing: longest("enchant.miss"),
      }));""")
    assert 0.01 <= got["hit"] <= 0.02, got
    assert got["flawed"] >= 2 * got["hit"], got
    assert got["hitRing"] > 1.0, got
    assert got["missRing"] < 0.25 and got["genericRing"] < 0.25, got


@needs_node
def test_the_chalk_stays_out_of_the_squeak_band(tmp_path):
    """A sigil stroke is heard on every Prepare press, hundreds of times a session. Reuter
    and Oehler found the 2000-4000 Hz band carries most of a chalkboard's unpleasantness
    and that cutting it made the sounds far more pleasant. Measured: every filter and
    oscillator frequency a chalk stroke sets, in each of its four takes, stays under 2 kHz."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      const tops = [];
      for (let i = 0; i < 8; i++) { drain(); const was = nodes.length;
        Sound.play("enchant.chalk", { phase: "noon" }); tops.push(Math.max(...freqs(was))); }
      console.log(JSON.stringify({ tops }));""")
    assert max(got["tops"]) < 2000, got["tops"]


@needs_node
def test_the_enchant_slider_scales_its_bus_and_works_rides_on_interface(tmp_path):
    """Settings → Sound and motion gains an Enchanting volume beside the forge's. The enchant
    bus starts at `sound.enchant`, follows it live, and an enchant sound plays into it, not
    into the forge's or the herb bench's. The In progress panel's chime is every bench's, so
    it rides on `sound.ui` (as the verdict rides on the dice): turning the circle down must
    not quieten "your work is ready". A pref nobody wired would be a slider that moves and
    changes nothing."""
    got = _node(tmp_path, r"""
      PGMPrefs.set("sound.enchant", 0.3);
      PGMPrefs.set("sound.ui", 0.45);
      Sound.unlock();
      const out = { default: PGMPrefs.defaults()["sound.enchant"] };
      // bus -> master -> makeup -> limiter.
      const buses = nodes.filter(n => n.kind === "gain" && n.to && n.to.kind === "gain"
                                      && n.to.to && n.to.to.kind === "gain"
                                      && n.to.to.to && n.to.to.to.kind === "compressor");
      const enchant = buses.filter(n => n.gain.value === 0.3);
      out.enchantBuses = enchant.length;
      Sound.play("enchant.bind.hit", { phase: "dusk" });
      out.voiceOnEnchant = nodes.filter(n => n.kind === "gain" && n.to === enchant[0]).length;
      PGMPrefs.set("sound.enchant", 0.1);
      out.after = enchant[0].gain.calls.filter(c => c[0] === "target").map(c => c[1]);
      const ui = buses.filter(n => n.gain.value === 0.45);
      out.uiBuses = ui.length;          // ui and works
      const was = nodes.length;
      Sound.play("works.ready");
      const voice = nodes.slice(was).find(n => n.kind === "gain" && buses.includes(n.to));
      out.worksOnUi = ui.includes(voice.to);
      PGMPrefs.set("sound.ui", 0.2);
      out.worksFollows = voice.to.gain.value;
      console.log(JSON.stringify(out));""")
    assert got["default"] == 0.8
    assert got["enchantBuses"] == 1, "exactly one bus should start at the enchant pref"
    assert got["voiceOnEnchant"] >= 1, "an enchant sound did not play into the enchant bus"
    assert got["after"][-1] == 0.1
    assert got["uiBuses"] == 2 and got["worksOnUi"] is True
    assert got["worksFollows"] == 0.2


@needs_node
def test_no_envelope_opens_at_full_gain_before_its_first_event(tmp_path):
    """Measured 2026-10-06 while levelling this bank, rendered offline in Chrome with every
    slider at its top: forge.flawless peaked at 2.4-5.7 of full scale, a hard clip at the
    speakers, at exactly 0.105 s, the start of its delayed highpassed shimmer; without that
    layer it peaked at 0.53. A new GainNode plays at 1 until its first automation event, and
    a source started at the same sub-sample time can render a sample before the event lands:
    raw noise at full gain, times the makeup x6. Every envelope gain must hold 0.0001 BEFORE
    its first event, in every bank (the fix is in the shared env(), so the forge's and the
    herb bench's sounds are held too). After the fix the loudest of all 148 one-shots,
    rendered four times each, peaked at 0.85."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      const bad = [];
      for (const n of Sound.names().filter(n => !n.startsWith("ambience."))) {
        drain(); const was = nodes.length;
        Sound.play(n, { phase: "noon", hardness: 12, bath: "brine" });
        for (const g of nodes.slice(was)) {
          if (g.kind !== "gain") continue;
          const i = g.gain.calls.findIndex(c => c[0] === "set" && c[1] === 0.0001);
          if (i < 0) continue;                        // not an env() gain
          const before = g.gain.calls.slice(0, i).filter(c => c[0] === "value");
          if (!before.length || before[before.length - 1][1] > 0.0001) { bad.push(n); break; }
        }
      }
      console.log(JSON.stringify({ bad }));""")
    assert got["bad"] == [], f"envelopes that open at full gain: {got['bad'][:10]}"


@needs_node
def test_the_sanctum_bed_stops_everything_it_started(tmp_path):
    """UI plan §11: `ambience.sanctum`, "a still room, a candle's hiss". A bed that kept a
    source running or kept scheduling its wick's sputters after stop() would play on under
    the next screen. Measured: every source and oscillator stopped, and running every
    pending timer after stop builds no new node."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      drain();
      const was = nodes.length;
      const bed = Sound.loop("ambience.sanctum");
      const mine = nodes.slice(was);
      FakeContext.last.state = "running";
      for (let i = 0; i < 3; i++) { const fns = pending.splice(0); fns.forEach(f => f()); }
      const out = { eventsWhileLive: nodes.length - was - mine.length };
      bed.stop();
      out.unstopped = mine.filter(n => (n.kind === "source" || n.kind === "osc") && !n.stopped).length;
      const before = nodes.length;
      drain();
      out.builtAfterStop = nodes.length - before;
      console.log(JSON.stringify(out));""")
    assert got["eventsWhileLive"] > 0, "the bed's sputters never fired"
    assert got["unstopped"] == 0
    assert got["builtAfterStop"] == 0, "a stopped bed kept scheduling events"


# --- levels, sources and settings --------------------------------------------------------------

def _enchant_bodies() -> str:
    src = _read(SOUND)
    i = src.index("/* --- enchant: the Enchanting circle")
    return src[i:src.index("/* --- ambience: beds that loop", i)]


def test_nothing_on_the_enchant_bus_is_louder_than_a_combat_hit():
    """The owner asked for the sounds louder (2026-10-05, the x6 makeup gain), and a bowl
    is struck dozens of times in one binding: no enchant or works peak may reach
    combat.hit's body (0.24), the loudest everyday sound in the app."""
    src = _read(SOUND)
    hit = src[src.index('def("combat.hit"'):src.index('def("combat.miss"')]
    ceiling = max(float(x) for x in re.findall(r"peak: ([0-9.]+)", hit))
    peaks = [float(x) for x in re.findall(r"peak: ([0-9.]+)", _enchant_bodies())]
    assert len(peaks) > 40, "the parse found too few enchant peaks; it is stale"
    assert max(peaks) < ceiling, max(peaks)


def test_the_enchant_bank_is_keyed_by_phase_and_names_no_planet():
    """The owner, round 4: there are no planets anywhere ("this is not earth"); the plan's
    planet-keyed pitch became the day phase. A planet's name in the bank would be the old
    design leaking back in. And the bank cites what its shapes rest on (CLAUDE.md: search
    first, cite what is used), by host and title since sound.js may hold no URL."""
    body = _enchant_bodies()
    code = re.sub(r"//[^\n]*|/\*.*?\*/", "", body, flags=re.S).lower()
    for planet in ("saturn", "jupiter", "mars", "venus", "mercury", "moon"):
        assert planet not in code, planet
    for p in PHASES:
        assert f"{p}:" in code, p
    head = re.sub(r"\s*\n\s*\*?\s*", " ", body)
    for cite in ("Vibration Modes and Sound Characteristic Analysis for Different Sizes of "
                 "Singing Bowls", "Psychoacoustics of chalkboard squeaking",
                 "Chime Design and Build"):
        assert cite in head, cite


def test_the_settings_pane_has_an_enchanting_slider_beside_the_forge():
    """Settings → Sound and motion: an Enchanting volume right after the Forge's, writing
    `sound.enchant` and sampling the struck bowl when let go."""
    home = _read(HOME)
    block = home[home.index("const SOUND_SLIDERS = ["):home.index("function prefGet(")]
    keys = re.findall(r'key: "([a-z.]+)"', block)
    assert keys.index("sound.enchant") == keys.index("sound.forge") + 1, keys
    assert 'label: "Enchanting", sample: "enchant.bind.hit"' in block
    assert '"sound.enchant": 0.8' in _read(PREFS)
    src = _read(SOUND)
    assert 'enchant: "sound.enchant"' in src and 'works: "sound.ui"' in src
