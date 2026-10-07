"""The Alchemy bench's sounds (play/static/js/sound.js `alchemy` bus and `Sound.burner`;
alchemy UI plan §11, contracts §11-§12, lane U5).

Every bench calls `Sound.play("alchemy.<event>", {pitch?})` and never guards, because an
unknown name is silent by contract. That is exactly how the enchant lane found sixteen
circle sounds already called and every one of them silent (tests/test_enchant_sound.py);
when this lane started, the alchemy games, stage and shell were being written in parallel
and no alchemy name existed at all. These tests hold:

- every event UI plan §11 names (its `<name>` and `<form>` families filled from the engine
  and the plan), every event this lane offered the other UI lanes, and every alchemy name
  their merged code calls, exists and builds sound under every option it reads;
- every material kind, intermediate form and product family on the shelf has a drop sound;
- the physics the bank is grounded in still shows in what it builds: a glass rings lower
  when full, a pour rises as it fills, a boil is loudest just under the boil, a fizz is
  bursts a few cycles long, a shatter is the thump-then-fragments pair glass-break
  detectors listen for, a scrape stays out of the squeak band, a miss never rings;
- the Transmute chime climbs the colour stages on a pentatonic;
- the Alchemy slider scales its bus live; a thrown flask's shatter rides on Combat;
- the burner follows the heat, and it and the laboratory bed stop everything they start;
- nothing on the alchemy bus is louder than a combat hit.

Behaviour runs the real prefs.js and sound.js in node against a stand-in Web Audio that
keeps every node, and skips without node, as tests/test_enchant_sound.py does.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from rules import alchemist

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "play" / "static" / "js"
SOUND = JS / "sound.js"
PREFS = JS / "prefs.js"
HOME = ROOT / "play" / "templates" / "play" / "home.html"
UI_PLAN = ROOT / "docs" / "alchemy-ui-plan.md"
GAMES = JS / "alchemy-games"
STAGE = JS / "alchemy-stage"
TABLE = JS / "table"
MATERIALS = ROOT / "content" / "materials" / "alchemist-materials.json"
TRACK = ROOT / "content" / "world-classes" / "alchemist.json"

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

METHODS = sorted(alchemist.METHODS)
# UI plan §11: `alchemy.drop.<form>` (powder, liquid, glass).
PLAN_FORMS = ("powder", "liquid", "glass")

# What this lane offered lanes U1-U3 on 2026-10-07, while their code was being written (none
# of it called a sound yet): the games' beats and misses, the stage's flourishes, the shell's
# cues. Their merged code is also read below, so a name they add later is checked too.
OFFERED = {
    "alchemy.hit", "alchemy.miss", "alchemy.glass.tick", "alchemy.clink", "alchemy.spill",
    "alchemy.swap", "alchemy.scrape", "alchemy.feed", "alchemy.bank", "alchemy.found",
    "alchemy.shatter", "alchemy.seal", "alchemy.uncork", "alchemy.drop.crystal",
    "alchemy.drop.wet", "combat.shatter", "works.ready", "works.collect",
    "ambience.laboratory",
}


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _promised() -> set[str]:
    """Every alchemy and ambience sound UI plan §11 names, `<name>` filled with the engine's
    methods and `<form>` with the plan's three forms."""
    text = _read(UI_PLAN)
    i = text.index("## 11. Sound")
    sect = text[i:text.index("## 12.", i)]
    names = set()
    for raw in re.findall(r"`((?:alchemy|ambience)\.[a-z.<>]+)`", sect):
        m = re.search(r"<(\w+)>", raw)
        if not m:
            names.add(raw)
            continue
        fill = METHODS if m.group(1) == "name" else PLAN_FORMS
        names.update(raw.replace(m.group(0), v) for v in fill)
    return names


def _called() -> set[str]:
    """OFFERED, plus every `alchemy.…` string literal in the merged alchemy games, stage
    and table files (SOUNDS maps, `Sound.play(...)`, `sound(...)`)."""
    names = set(OFFERED)
    files = []
    for d in (GAMES, STAGE):
        if d.is_dir():
            files += list(d.glob("*.js"))
    files += [f for f in TABLE.glob("5*.js")] if TABLE.is_dir() else []
    for f in files:
        names.update(re.findall(r'["\'](alchemy\.[a-z][a-z.]*[a-z])["\']', _read(f)))
    return names


_FAKE = r"""
Math.random = () => 0.5;
const nodes = [];
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
function freqs(from, kind) {
  const out = [];
  for (const n of nodes.slice(from)) {
    if (kind && n.kind !== kind) continue;
    if (n.kind !== "osc" && n.kind !== "filter") continue;
    for (const c of n.frequency.calls) if (c[0] === "set" || c[0] === "exp") out.push(c[1]);
  }
  return out;
}
// The oscillators one play built: [start frequency, stop time, envelope seconds].
function oscs(from) {
  return nodes.slice(from).filter(n => n.kind === "osc" && n.frequency.calls.length)
    .map(n => { const g = n.to && n.to.kind === "gain" ? n.to
                  : (n.to && n.to.to && n.to.to.kind === "gain" ? n.to.to : null);
                let span = null;
                if (g) { const cs = g.gain.calls.filter(c => c[0] === "set" || c[0] === "exp");
                         if (cs.length > 1) span = cs[cs.length - 1][2] - cs[0][2]; }
                return [n.frequency.calls[0][1], n.stopAt, span]; });
}
// The highest level each new gain was ramped to, summed: how much one play puts out.
function energy(from) {
  let sum = 0;
  for (const n of nodes.slice(from)) {
    if (n.kind !== "gain") continue;
    const tops = n.gain.calls.filter(c => c[0] === "exp").map(c => c[1]);
    if (tops.length) sum += Math.max(...tops);
  }
  return sum;
}
// One play's sound, with the take held: sound.js never plays one take twice in a row, so
// a throwaway play before each measured one keeps every measured play on the same take.
function held(name, o) { drain(); Sound.play(name, o); drain(); const was = nodes.length;
                         Sound.play(name, o); return was; }
"""


def _node(tmp_path, body: str) -> dict:
    src = (_FAKE + _read(PREFS) + "\n" + _read(SOUND)
           + "\nconst Sound = window.Sound, PGMPrefs = window.PGMPrefs;\n" + body)
    f = tmp_path / "alchemy_probe.js"
    f.write_text(src, encoding="utf-8")
    done = subprocess.run([NODE, str(f)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout.strip().splitlines()[-1])


# --- the bank ------------------------------------------------------------------------------

def test_the_plan_names_the_events_this_file_checks():
    """A guard on the parse below: if UI plan §11 were reworded so the regex found nothing,
    the existence test would pass on an empty set. It named 21 sounds when written, plus a
    method family over the engine's nine operations and a drop family over three forms."""
    names = _promised()
    for n in ("alchemy.open", "alchemy.roll", "alchemy.pour", "alchemy.stir",
              "alchemy.bubble", "alchemy.boil", "alchemy.drip", "alchemy.fizz", "alchemy.hiss",
              "alchemy.chime", "alchemy.stopper", "alchemy.glass.tick", "alchemy.crack",
              "alchemy.flare", "alchemy.tier.up", "alchemy.flawless", "alchemy.fail",
              "alchemy.land", "alchemy.assay", "ambience.laboratory"):
        assert n in names, n
    assert {f"alchemy.method.{m}" for m in METHODS} <= names
    assert {f"alchemy.drop.{f}" for f in PLAN_FORMS} <= names
    assert len(METHODS) == 9, METHODS


@needs_node
def test_every_promised_and_called_event_exists_and_builds_sound(tmp_path):
    """Every alchemy sound the plan promises, this lane offered, or another lane's merged
    code calls plays and builds nodes, with no options and under every option the bank
    reads, sane or not; an unknown alchemy name answers false and builds nothing.

    The defect this holds off: on 2026-10-06 the enchant lane found sixteen circle and works
    names already called and every one silent, by contract. Running every synth under odd
    options also catches one that throws or ramps a gain to zero (a RangeError in real Web
    Audio), e.g. a `heat` of 7 or a `pitch` of "x"."""
    names = sorted(_promised() | _called())
    got = _node(tmp_path, "const names = " + json.dumps(names) + r""";
      Sound.unlock();
      const out = { missing: [], silent: [], loops: [] };
      const opts = [undefined, { pitch: 3 }, { pitch: "x" }, { pitch: -40 }, { pitch: 99 },
                    { stage: "rubedo" }, { stage: "Saturn" }, { heat: 0 }, { heat: 1 },
                    { heat: 7 }, { heat: null }, { level: 0 }, { level: 1 }, { level: -2 },
                    { seal: "wax" }, { volume: 0.5 }];
      for (const n of names) {
        drain();
        if (!Sound.has(n)) { out.missing.push(n); continue; }
        if (n.startsWith("ambience.")) {
          const l = Sound.loop(n);
          if (!l || typeof l.stop !== "function") out.loops.push(n);
          l.stop(); continue;
        }
        for (const o of opts) {
          drain();
          const was = nodes.length;
          if (Sound.play(n, o) !== true || nodes.length === was) out.silent.push(n);
        }
      }
      drain();
      const was = nodes.length;
      out.unknown = [Sound.play("alchemy.boom"), Sound.play("alchemy.method.brew"),
                     Sound.play("alchemy.drop.plasma", { pitch: 2 })];
      out.unknownBuilt = nodes.length - was;
      console.log(JSON.stringify(out));""")
    assert got["missing"] == [], f"promised or called with no synthesizer: {got['missing']}"
    assert got["silent"] == [], f"built nothing: {sorted(set(got['silent']))}"
    assert got["loops"] == []
    assert got["unknown"] == [False, False, False] and got["unknownBuilt"] == 0


@needs_node
def test_every_kind_form_and_family_on_the_shelf_has_a_drop_sound(tmp_path):
    """The shell drops a material into a slot by whatever word it has: the material's kind
    (eight on the shelf), an intermediate's form (seven in alchemist.json's bench), or a
    product's family (five). A word with no `alchemy.drop.<word>` is silent by contract, so
    an item the shelf grows would land without a sound and nobody would hear it missing."""
    kinds = {m["kind"] for m in json.loads(_read(MATERIALS))["materials"]}
    bench = json.loads(_read(TRACK))["bench"]
    words = sorted(kinds | set(bench["forms"]) | set(bench["families"]))
    assert len(kinds) == 8 and len(words) >= 18, words
    got = _node(tmp_path, "const words = " + json.dumps(words) + r""";
      Sound.unlock();
      console.log(JSON.stringify({ missing: words.filter(w => !Sound.has("alchemy.drop." + w)) }));""")
    assert got["missing"] == [], got["missing"]


# --- the physics the bank rests on -------------------------------------------------------

@needs_node
def test_a_glass_rings_lower_as_it_fills(tmp_path):
    """Jundt et al. (JASA 2006) fitted w² = w0²/(1 + a·h^5.5) to a wine glass filling with
    water: almost no change to half full, a large fall at the brim. Measured here as the
    clink's fundamental (its lowest oscillator) at three levels: half full within 2% of
    empty, full at 1/sqrt(2) of it (a = 1). A clink that ignored `level` would tell the ear
    an empty flask and a brimming one are the same glass."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      const f = lv => { const was = held("alchemy.clink", { level: lv });
                        return Math.min(...freqs(was, "osc")); };
      console.log(JSON.stringify({ empty: f(0), half: f(0.5), full: f(1) }));""")
    assert abs(got["half"] / got["empty"] - 1) < 0.02, got
    assert abs(got["full"] / got["empty"] - 1 / math.sqrt(2)) < 0.01, got


@needs_node
def test_a_pour_rises_as_the_vessel_fills(tmp_path):
    """Cabe and Pittenger (JEP:HPP 2000): people fill a vessel to the brim by ear, from the
    pitch of the air column above the liquid, which shortens as it fills. Measured: the
    pour's resonant band (the bandpass at Q 4) starts more than three times higher at 0.9
    full than at 0.1, and within one pour it always climbs."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      const band = lv => { const was = held("alchemy.pour", { level: lv });
        const f = nodes.slice(was).find(n => n.kind === "filter" && n.Q.value === 4);
        return [f.frequency.calls.find(c => c[0] === "set")[1],
                f.frequency.calls.find(c => c[0] === "exp")[1]]; };
      console.log(JSON.stringify({ low: band(0.1), high: band(0.9) }));""")
    assert got["high"][0] / got["low"][0] > 3, got
    assert got["low"][1] > got["low"][0] and got["high"][1] > got["high"][0], got


@needs_node
def test_a_boil_is_loudest_just_under_the_boil(tmp_path):
    """Aljishi and Tatarkiewicz (Am. J. Phys. 1991): a kettle is quiet cold, loudest near
    80-90 °C while bubbles collapse before reaching the surface, and quieter at a full boil.
    Measured as the summed envelope peaks of one `alchemy.boil` (the seethe and its bubbles)
    and the burner's liquid layer target: 0.85 > 1.0 > 0.3 for both. A boil that only grew
    with heat would be the cartoon, not the kettle."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      const boil = h => { const was = held("alchemy.boil", { heat: h }); return energy(was); };
      const seethe = h => { drain(); const was = nodes.length;
        const b = Sound.burner({ liquid: true }); b.heat(h);
        const sf = nodes.slice(was).find(n => n.kind === "filter" && n.frequency.calls.length
                                          && n.Q.value === 1.6);
        const v = sf.to.gain.calls.filter(c => c[0] === "target").pop()[1];
        b.stop(); return v; };
      console.log(JSON.stringify({ boil: [boil(0.3), boil(0.85), boil(1)],
                                   seethe: [seethe(0.3), seethe(0.85), seethe(1)] }));""")
    for k in ("boil", "seethe"):
        cold, peak, full = got[k]
        assert peak > full > cold, (k, got[k])


@needs_node
def test_a_fizz_is_bursts_a_few_cycles_long(tmp_path):
    """Champagne's "sizzling or crackling" is short tone bursts lasting only a few cycles,
    6.7 kHz for a 0.94 mm bubble (Physics Today, "Champagne acoustics"). The first draft
    here rang each burst for 3.5 cycles plus 2 ms, about 22 cycles at 6.5 kHz: pings, not a
    fizz. Measured: every oscillator of a fizz sits in 2-8 kHz and its envelope lasts at
    most six cycles."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      const was = held("alchemy.fizz");
      console.log(JSON.stringify({ o: oscs(was) }));""")
    assert len(got["o"]) >= 20
    for f, _stop, span in got["o"]:
        assert 2000 < f < 8000, f
        assert span * f <= 6.01, (f, span, span * f)


@needs_node
def test_a_shatter_is_the_thump_then_the_fragments(tmp_path):
    """Glass-break detectors fire on two things in order: the pane's flex thump, centred
    near 350 Hz, then the fragments' scatter, centred near 6.5 kHz (Cypress AN2186). A
    splash flask's shatter that lacked either reads as a clink or a hiss. Measured: one
    oscillator starting in 300-400 Hz, and at least eight fragment pings in 4.5-8.5 kHz
    falling after it. A thermal crack is the tink alone: no thump under 500 Hz."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      let was = held("alchemy.shatter"); const s = oscs(was);
      was = held("alchemy.crack"); const c = oscs(was);
      console.log(JSON.stringify({ s, c }));""")
    starts = [o[0] for o in got["s"]]
    assert any(300 <= f <= 400 for f in starts), starts
    assert sum(1 for f in starts if 4500 <= f <= 8500) >= 8, starts
    assert all(o[0] > 500 for o in got["c"]), got["c"]


@needs_node
def test_the_scrape_stays_out_of_the_squeak_band(tmp_path):
    """Sublime's scrape is heard on every crust. Reuter and Oehler found the 2000-4000 Hz
    band carries most of a chalkboard's unpleasantness (the enchant bank's chalk rule).
    Measured: every filter and oscillator frequency in each take stays under 2 kHz."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      const tops = [];
      for (let i = 0; i < 6; i++) { drain(); const was = nodes.length;
        Sound.play("alchemy.scrape"); tops.push(Math.max(...freqs(was))); }
      console.log(JSON.stringify({ tops }));""")
    assert max(got["tops"]) < 2000, got["tops"]


@needs_node
def test_a_miss_never_rings_and_a_hit_does(tmp_path):
    """UI plan §10: a good beat is "a bloom of colour, a soft chime"; out of band is "a dull
    fizz, vapour puffs". A miss with a glass ring in it would tell the ear the opposite of
    the words. Measured: every oscillator of `alchemy.miss` is under 400 Hz and stops within
    0.3 s; `alchemy.hit` has a glass partial over 1 kHz ringing past 0.4 s."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      let was = held("alchemy.miss"); const miss = oscs(was);
      was = held("alchemy.hit"); const hit = oscs(was);
      console.log(JSON.stringify({ miss, hit, now: FakeContext.last.currentTime }));""")
    assert got["miss"] and all(f < 400 and stop < 0.3 for f, stop, _ in got["miss"]), got["miss"]
    assert any(f > 1000 and stop > 0.4 for f, stop, _ in got["hit"]), got["hit"]


@needs_node
def test_the_transmute_chime_climbs_the_colour_stages(tmp_path):
    """UI plan §11: `alchemy.chime` is "a Transmute stage, pitched up the colour stages".
    Measured as its fundamental per stage: nigredo, albedo, citrinitas and rubedo stand 0,
    2, 4 and 7 semitones up a major pentatonic (the enchant bowls' no-clash ladder), and
    `{pitch: n}` walks the same ladder (0 2 4 7 9 12) for a game that counts drops. A stage
    the bench has never heard of, or none, rings as nigredo."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      const f = o => { const was = held("alchemy.chime", o);
                       return Math.min(...freqs(was, "osc")); };
      const out = { stages: ["nigredo", "albedo", "citrinitas", "rubedo"].map(s => f({ stage: s })),
                    pitch: [0, 1, 2, 3, 4, 5].map(p => f({ pitch: p })),
                    none: f({}), odd: f({ stage: "Saturn" }), caps: f({ stage: " ALBEDO " }) };
      console.log(JSON.stringify(out));""")
    base = got["stages"][0]
    steps = [round(12 * math.log2(x / base), 3) for x in got["stages"]]
    assert steps == [0, 2, 4, 7], steps
    pbase = got["pitch"][0]
    assert [round(12 * math.log2(x / pbase), 3) for x in got["pitch"]] == [0, 2, 4, 7, 9, 12]
    assert got["none"] == base and got["odd"] == base
    assert abs(got["caps"] / got["stages"][1] - 1) < 1e-9


# --- the slider, the burner and the bed ----------------------------------------------------

@needs_node
def test_the_alchemy_slider_scales_its_bus_and_the_thrown_flask_rides_on_combat(tmp_path):
    """Settings → Sound and motion gains an Alchemy volume beside the Enchanting one. The
    alchemy bus starts at `sound.alchemy`, follows it live, and an alchemy sound and the
    burner play into it, not into a neighbour's. A splash flask thrown in a fight is a
    fight's sound: `combat.shatter` rides on Combat, so turning the bench down never
    quietens the battle. A pref nobody wired would be a slider that moves and changes
    nothing."""
    got = _node(tmp_path, r"""
      PGMPrefs.set("sound.alchemy", 0.35);
      PGMPrefs.set("sound.combat", 0.55);
      Sound.unlock();
      const out = { default: PGMPrefs.defaults()["sound.alchemy"] };
      const buses = nodes.filter(n => n.kind === "gain" && n.to && n.to.kind === "gain"
                                      && n.to.to && n.to.to.kind === "gain"
                                      && n.to.to.to && n.to.to.to.kind === "compressor");
      const alch = buses.filter(n => n.gain.value === 0.35);
      out.alchBuses = alch.length;
      Sound.play("alchemy.hit");
      out.voiceOnAlchemy = nodes.filter(n => n.kind === "gain" && n.to === alch[0]).length;
      drain(); let was = nodes.length;
      const b = Sound.burner(); out.burnerOnAlchemy = nodes.slice(was)
        .some(n => n.kind === "gain" && n.to === alch[0]); b.stop();
      PGMPrefs.set("sound.alchemy", 0.1);
      out.after = alch[0].gain.calls.filter(c => c[0] === "target").map(c => c[1]);
      was = nodes.length;
      Sound.play("combat.shatter");
      const voice = nodes.slice(was).find(n => n.kind === "gain" && buses.includes(n.to));
      out.shatterOnCombat = voice.to.gain.value === 0.55;
      console.log(JSON.stringify(out));""")
    assert got["default"] == 0.8
    assert got["alchBuses"] == 1, "exactly one bus should start at the alchemy pref"
    assert got["voiceOnAlchemy"] >= 1 and got["burnerOnAlchemy"] is True
    assert got["after"][-1] == 0.1
    assert got["shatterOnCombat"] is True


@needs_node
def test_the_burner_follows_the_heat_and_stops_everything(tmp_path):
    """Calcine, Distill and Sublime hold a flame for the whole game, so it is a live handle,
    not a string of one-shots: `Sound.burner({kind, liquid}).heat(0..1)`. Measured on the
    nodes it builds: the roar's level at full heat is over twice its level banked; the hiss
    is all but absent low on the gauge and present at the top; the liquid layer bubbles
    while live. stop() stops every source and oscillator, and running every pending timer
    afterwards builds nothing (a flame that kept bubbling under the next screen). Muted, it
    builds nothing at all."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      drain();
      const was = nodes.length;
      const b = Sound.burner({ kind: "athanor", liquid: true });
      const mine = nodes.slice(was);
      const rf = mine.find(n => n.kind === "filter" && n.type === "lowpass");
      const hf = mine.find(n => n.kind === "filter" && n.Q.value === 0.8);
      const last = g => g.gain.calls.filter(c => c[0] === "target").pop()[1];
      const out = {};
      b.heat(0); out.roar0 = last(rf.to); out.hiss0 = last(hf.to);
      b.heat(1); out.roar1 = last(rf.to); out.hiss1 = last(hf.to);
      b.heat(0.85);
      FakeContext.last.state = "running";
      const before = nodes.length;
      for (let i = 0; i < 3; i++) { const fns = pending.splice(0); fns.forEach(f => f()); }
      out.bubbled = nodes.length - before;
      b.stop(); b.heat(1);
      out.unstopped = mine.filter(n => (n.kind === "source" || n.kind === "osc") && !n.stopped).length;
      const after = nodes.length; drain(); out.builtAfterStop = nodes.length - after;
      PGMPrefs.set("sound.mute", true);
      const was2 = nodes.length; const m = Sound.burner(); m.heat(1); m.stop();
      out.mutedBuilt = nodes.length - was2;
      console.log(JSON.stringify(out));""")
    assert got["roar1"] > 2 * got["roar0"], got
    assert got["hiss0"] < 0.001 < got["hiss1"], got
    assert got["bubbled"] > 0, "the liquid over the flame never bubbled"
    assert got["unstopped"] == 0 and got["builtAfterStop"] == 0, got
    assert got["mutedBuilt"] == 0


@needs_node
def test_the_laboratory_bed_stops_everything_it_started(tmp_path):
    """UI plan §11: `ambience.laboratory`, "a low athanor roar and the odd glass tick". A bed
    that kept a source running or kept scheduling its ticks and bubbles after stop() would
    play on under the next screen. Measured: its events fire while live, every source and
    oscillator is stopped, and running every pending timer after stop builds no node."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      drain();
      const was = nodes.length;
      const bed = Sound.loop("ambience.laboratory");
      const mine = nodes.slice(was);
      FakeContext.last.state = "running";
      for (let i = 0; i < 3; i++) { const fns = pending.splice(0); fns.forEach(f => f()); }
      const out = { eventsWhileLive: nodes.length - was - mine.length };
      bed.stop();
      out.unstopped = mine.filter(n => (n.kind === "source" || n.kind === "osc") && !n.stopped).length;
      const before = nodes.length;
      drain();
      out.builtAfterStop = nodes.length - before;
      out.alias = Sound.has("ambience.lab");
      console.log(JSON.stringify(out));""")
    assert got["eventsWhileLive"] > 0, "the laboratory's events never fired"
    assert got["unstopped"] == 0
    assert got["builtAfterStop"] == 0, "a stopped bed kept scheduling events"
    assert got["alias"] is True


# --- levels, sources and settings --------------------------------------------------------------

def _alchemy_bodies() -> str:
    src = _read(SOUND)
    i = src.index("/* --- alchemy: the Alchemy bench")
    return src[i:src.index("/* --- ambience: beds that loop", i)]


def test_nothing_on_the_alchemy_bus_is_louder_than_a_combat_hit():
    """The owner asked for every sound louder (2026-10-05, the x6 makeup gain), and a game
    plays a beat every half second: no alchemy peak literal may reach combat.hit's body
    (0.24), the loudest everyday sound in the app.

    Measured 2026-10-07 through the real chain (bus, master, x6 makeup, limiter) in Chrome's
    OfflineAudioContext, every slider at its top, median / max of eight renders, against the
    neighbours this lane levelled to (the enchant lane's figures re-measured the same way):
      a game's beat: hit 0.32, drip 0.31, stir 0.30, pour 0.30, bubble 0.34, swap 0.32,
        stopper 0.31, uncork 0.33  -- forge.strike.hit 0.31, enchant.bind.hit 0.33
      a miss: miss 0.22, fizz 0.24, spill 0.25, hiss 0.26  -- forge.strike.miss 0.24,
        enchant.miss 0.23
      open 0.39 (0.37 / 0.41), roll 0.17 (0.17 / 0.17), methods 0.14-0.20 (0.14-0.18),
        drops 0.15-0.18 (0.17), land 0.18 (0.16 / 0.18), assay 0.26 (0.24 / 0.29)
      tier up 0.43 (0.42 / 0.42), flawless 0.67 / 0.70 (0.69 / 0.71), fail 0.76 / 0.80
        (0.78 / 0.78), found 0.55, chime 0.39 a stage and 0.69 rubedo's chord
      flare 0.71 / 0.81 (between combat.crit 0.60 and a fail), shatter 0.41 (combat.hit
        0.42), crack 0.31, boil 0.36 at its peak heat
      the burner, a bed under the beats: peak 0.07 banked, 0.17 at half, 0.30 at full
        (RMS 0.015 / 0.034 / 0.058; the smithy bed's RMS is 0.135)
    The loudest single render of any alchemy name under any option was under 0.95."""
    src = _read(SOUND)
    hit = src[src.index('def("combat.hit"'):src.index('def("combat.miss"')]
    ceiling = max(float(x) for x in re.findall(r"peak: ([0-9.]+)", hit))
    peaks = [float(x) for x in re.findall(r"peak: ([0-9.]+)", _alchemy_bodies())]
    assert len(peaks) > 100, "the parse found too few alchemy peaks; it is stale"
    assert max(peaks) < ceiling, max(peaks)


def test_the_alchemy_bank_cites_its_sources_and_names_no_planet():
    """CLAUDE.md: search first, cite what is used. Every shape in the bank rests on a
    measurement named in its header, by title since sound.js may hold no URL. And the
    owner, round 4: no planets anywhere ("this is not earth"), so none may key a sound."""
    body = _alchemy_bodies()
    head = re.sub(r"\s*\n\s*\*?\s*", " ", body)
    for cite in ("Vibrational modes of partly filled wine glasses",
                 "The Sound Produced by a Dripping Tap is Driven by Resonant Oscillations of "
                 "an Entrapped Air Bubble", "Champagne acoustics",
                 "Why does heating water in a kettle produce sound?",
                 "Human sensitivity to acoustic information from vessel filling",
                 "On the popping sound and liquid sloshing when opening a beer bottle",
                 "Consumer or Industrial Acoustic Glass Break Detector"):
        assert cite in head, cite
    code = re.sub(r"//[^\n]*|/\*.*?\*/", "", body, flags=re.S).lower()
    for planet in ("saturn", "jupiter", "mars", "venus", "mercury", "moon"):
        assert planet not in code, planet


def test_the_settings_pane_has_an_alchemy_slider_beside_enchanting():
    """Settings → Sound and motion: an Alchemy volume right after the Enchanting one,
    writing `sound.alchemy` and sampling a game's good beat when let go; the pref has its
    default, and the bus reads it."""
    home = _read(HOME)
    block = home[home.index("const SOUND_SLIDERS = ["):home.index("function prefGet(")]
    keys = re.findall(r'key: "([a-z.]+)"', block)
    assert keys.index("sound.alchemy") == keys.index("sound.enchant") + 1, keys
    assert 'label: "Alchemy", sample: "alchemy.hit"' in block
    assert '"sound.alchemy": 0.8' in _read(PREFS)
    assert 'alchemy: "sound.alchemy"' in _read(SOUND)
