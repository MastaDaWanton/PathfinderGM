"""The forge's sounds (play/static/js/sound.js `forge` bus, blacksmithing UI plan §11 and
§6.8, contracts §10-§11, lane U6).

The Blacksmithing bench calls `Sound.play("forge.<event>", {hardness, bath})` and never
guards, because an unknown name is silent by contract. That contract is exactly what lets a
missing sound ship unnoticed, so these tests hold what the plan promised:

- every event in UI plan §11 exists, with `<name>` over the bench's real methods and
  `<form>` over the rack's real forms;
- a strike's ring rises with the work's hardness (bronze under steel under adamantine),
  and a miss does not ring at all;
- a brine quench is brighter than water, and water than oil;
- the Forge slider's pref scales the forge bus, live;
- the smithy bed fades in, and when stopped it stops every node and schedules nothing more;
- nothing on the forge bus is louder than a combat hit.

Behaviour runs the real prefs.js and sound.js in node against a stand-in Web Audio that keeps
every node it makes (with its frequencies, gains and connection), and skips without node,
as tests/test_sound.py does.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from rules.blacksmith import GROUPS, LEATHER_GROUPS, METHODS

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "play" / "static" / "js"
SOUND = JS / "sound.js"
PREFS = JS / "prefs.js"
HOME = ROOT / "play" / "templates" / "play" / "home.html"
UI_PLAN = ROOT / "docs" / "blacksmithing-ui-plan.md"

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _promised() -> set[str]:
    """Every forge sound UI plan §11 names, its placeholders filled from the engine's own
    vocabularies: the bench's METHODS and the rack's forms (GROUPS' keys, and the leather
    bench's forms the rack carries, LEATHER_GROUPS: a base and a lacing set dropped on the
    anvil were silent until the leather final pass, 2026-10-09, because lane H moved them
    out of GROUPS and nothing then asked for their sound)."""
    text = _read(UI_PLAN)
    i = text.index("## 11. Sound")
    sect = text[i:text.index("## 12.", i)]
    names = set()
    for raw in re.findall(r"`((?:forge|ambience)\.[a-z.<>]+)`", sect):
        m = re.search(r"<(\w+)>", raw)
        if not m:
            names.add(raw)
            continue
        fill = {"name": METHODS, "form": sorted(set(GROUPS) | set(LEATHER_GROUPS))}[
            m.group(1)]
        names.update(raw.replace(m.group(0), v) for v in fill)
    return names


# A stand-in Web Audio that keeps every node: kind, its params' calls, where it connects,
# whether it was stopped. Math.random is pinned at 0.5, so the ±5% jitter and the take are
# the same on every play and two plays differ only by what the caller passed.
_FAKE = r"""
Math.random = () => 0.5;
const nodes = [];
function Param(v) { return { value: v, calls: [],
  setValueAtTime(x, t) { this.calls.push(["set", x, t]); this.value = x; },
  exponentialRampToValueAtTime(x, t) {
    if (!(x > 0)) throw new Error("exponential ramp to " + x); this.calls.push(["exp", x, t]); },
  linearRampToValueAtTime(x, t) { this.calls.push(["lin", x, t]); },
  setTargetAtTime(x, t, k) { this.calls.push(["target", x, t]); this.value = x; },
  cancelScheduledValues() {} }; }
function Node(kind) { const n = { kind, to: null, stopped: false, id: nodes.length,
  connect(d) { this.to = d; return d; }, disconnect() {},
  start() {}, stop() { this.stopped = true; }, gain: Param(1), frequency: Param(440),
  Q: Param(1), playbackRate: Param(1), threshold: Param(0), knee: Param(0), ratio: Param(1),
  attack: Param(0), release: Param(0), type: "", buffer: null, loop: false };
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
// Timers held, so the test decides when a voice ends or a bed's next event fires.
const pending = [];
const setTimeout = (fn, ms) => { pending.push(fn); return pending.length; };
const clearTimeout = () => {};
const drain = () => { while (pending.length) pending.shift()(); };
// Every frequency an oscillator or a filter was set to by one play.
function freqs(from, kind) {
  const out = [];
  for (const n of nodes.slice(from)) {
    if (n.kind !== kind) continue;
    for (const c of n.frequency.calls) if (c[0] === "set" || c[0] === "exp") out.push(c[1]);
  }
  return out;
}
"""


def _node(tmp_path, body: str) -> dict:
    src = (_FAKE + _read(PREFS) + "\n" + _read(SOUND)
           + "\nconst Sound = window.Sound, PGMPrefs = window.PGMPrefs;\n" + body)
    f = tmp_path / "forge_probe.js"
    f.write_text(src, encoding="utf-8")
    done = subprocess.run([NODE, str(f)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout.strip().splitlines()[-1])


# --- the bank ------------------------------------------------------------------------------

def test_the_plan_names_the_events_this_file_checks():
    """A guard on the parse below: if UI plan §11 were reworded so the regex found nothing,
    the existence test would pass on an empty set. It named 22 sounds when written, plus a
    method and a form family."""
    names = _promised()
    for n in ("forge.open", "forge.roll", "forge.strike.hit", "forge.strike.miss",
              "forge.bellows", "forge.quench", "forge.temper", "forge.grind",
              "forge.rivet", "forge.weld", "forge.tier.up", "forge.flawless", "forge.fail",
              "forge.land", "forge.assay", "ambience.smithy"):
        assert n in names, n
    assert {f"forge.method.{m}" for m in METHODS} <= names
    assert "forge.drop.bar" in names and "forge.drop.ore" in names


@needs_node
def test_every_ui_plan_forge_event_exists_and_builds_sound(tmp_path):
    """Every forge sound UI plan §11 promises plays and builds nodes, with and without its
    options; an unknown forge name answers false and builds nothing.

    The defect: `Sound.play` of a missing name is silent by contract (contracts §11,
    "unknown events are silent, so callers never guard"), so `forge.method.strengthen` or
    `forge.drop.plate` missing from the bank would be a bench that is quiet at one step
    and nobody would hear why. Running every synth also catches one that throws or ramps
    a gain to zero, a RangeError in real Web Audio."""
    names = sorted(_promised())
    got = _node(tmp_path, "const names = " + json.dumps(names) + r""";
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
        for (const o of [undefined, { hardness: 20, bath: "quenching-brine" },
                         { hardness: "bronze", bath: "whale-oil" }, { hardness: "nonsense" }]) {
          drain();
          const was = nodes.length;
          if (Sound.play(n, o) !== true || nodes.length === was) out.silent.push(n);
        }
      }
      drain();
      const was = nodes.length;
      out.unknown = [Sound.play("forge.strike.crit"), Sound.play("forge.method.knit"),
                     Sound.play("forge.drop.cheese", { hardness: 12 })];
      out.unknownBuilt = nodes.length - was;
      console.log(JSON.stringify(out));""")
    assert got["missing"] == [], f"promised with no synthesizer: {got['missing']}"
    assert got["silent"] == [], f"built nothing: {sorted(set(got['silent']))}"
    assert got["loops"] == []
    assert got["unknown"] == [False, False, False] and got["unknownBuilt"] == 0


@needs_node
def test_a_strike_rings_higher_on_harder_metal_and_a_miss_does_not_ring(tmp_path):
    """UI plan §11: "bronze rings lower than steel, adamantine highest". A struck body's
    modes scale with its speed of sound (steel 5180 m/s, brass 3480, bell bronze 3400); the
    bank maps 100 Hz per point of hardness. Measured here as the ring's fundamental (the
    lowest oscillator above the hot-iron thump) for bronze 8, steel 12, adamantine 20,
    both as numbers and as material names.

    And a miss is the smiths' "dull thud": no oscillator above 400 Hz. A miss that pinged
    like the hit would tell the ear the opposite of the words."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      const ring = o => { drain(); const was = nodes.length;
        Sound.play("forge.strike.hit", o);
        return Math.min(...freqs(was, "osc").filter(f => f > 400)); };
      const out = {
        nums: [ring({ hardness: 8 }), ring({ hardness: 12 }), ring({ hardness: 20 })],
        names: [ring({ hardness: "bronze" }), ring({ hardness: "steel" }),
                ring({ hardness: "adamantine" })],
        fallback: ring({}),
      };
      drain(); const was = nodes.length;
      Sound.play("forge.strike.miss", { hardness: 20 });
      out.missTop = Math.max(...freqs(was, "osc"));
      console.log(JSON.stringify(out));""")
    bronze, steel, adamantine = got["nums"]
    assert bronze < steel < adamantine, got["nums"]
    # Each play takes a different take (the same take never plays twice in a row), and
    # the strike's takes detune the ring by up to 2%; so equal within 3%.
    assert all(abs(a / b - 1) < 0.03 for a, b in zip(got["names"], got["nums"])), \
        f"a material name should ring as its hardness: {got['names']} vs {got['nums']}"
    # A difference the ear hears through the ±5% jitter: at least a fifth apart.
    assert steel / bronze > 1.2 and adamantine / steel > 1.2, got["nums"]
    assert bronze < got["fallback"] < steel, "no hardness given should ring as iron (10)"
    assert got["missTop"] <= 400, f"a miss rang at {got['missTop']} Hz"


@needs_node
def test_brine_hisses_brighter_than_water_and_water_than_oil(tmp_path):
    """UI plan §11: "hiss by bath: brine sharpest, oil softest". Brine's salt breaks the
    vapour blanket at once and the discharge crackles; oil's vapour stage is longer and its
    boiling gentler. Measured as the highest filter frequency one quench sets (the hiss
    band), for each bath id the materials file ships with that behaviour, and a homebrew
    name read by its word."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      const top = bath => { drain(); const was = nodes.length;
        Sound.play("forge.quench", { bath }); return Math.max(...freqs(was, "filter")); };
      console.log(JSON.stringify({
        brine: top("quenching-brine"), water: top("water"), oil: top("quenching-oil"),
        whale: top("whale-oil"), sea: top("sea-brine"), none: top(undefined),
      }));""")
    assert got["brine"] > got["water"] > got["oil"], got
    assert got["whale"] == got["oil"] and got["sea"] == got["brine"], got
    assert got["none"] == got["water"], "no bath named should sound as water"


@needs_node
def test_the_forge_volume_pref_scales_the_forge_bus_live(tmp_path):
    """UI plan §6.8: a Forge volume beside Bench. The forge bus gain starts at
    `sound.forge`, follows it when the slider moves (in this window or another), and a
    forge sound plays into that bus, not the herb bench's. A pref nobody wired would be a
    slider that moves and changes nothing."""
    got = _node(tmp_path, r"""
      PGMPrefs.set("sound.forge", 0.3);
      Sound.unlock();
      const ctx = FakeContext.last;
      const out = { default: PGMPrefs.defaults()["sound.forge"] };
      // bus -> master -> makeup (x6, 2026-10-05: "i can barely hear them") -> limiter.
      const buses = nodes.filter(n => n.kind === "gain" && n.to && n.to.kind === "gain"
                                      && n.to.to && n.to.to.kind === "gain"
                                      && n.to.to.to && n.to.to.to.kind === "compressor");
      const forge = buses.filter(n => n.gain.value === 0.3);
      out.forgeBuses = forge.length;
      Sound.play("forge.strike.hit", { hardness: 12 });
      const voice = nodes.filter(n => n.kind === "gain" && n.to === forge[0]);
      out.voiceOnForge = voice.length;
      PGMPrefs.set("sound.forge", 0.1);
      out.after = forge[0].gain.calls.filter(c => c[0] === "target").map(c => c[1]);
      // The herb bench's bus is untouched by the forge slider.
      out.benchLevels = buses.filter(n => n !== forge[0] && n.gain.value === 0.8).length;
      console.log(JSON.stringify(out));""")
    assert got["default"] == 0.8
    assert got["forgeBuses"] == 1, "exactly one bus should start at the forge pref"
    assert got["voiceOnForge"] >= 1, "a forge sound did not play into the forge bus"
    assert got["after"][-1] == 0.1
    assert got["benchLevels"] >= 2   # bench and dice keep their 0.8


@needs_node
def test_the_smithy_bed_fades_in_and_stops_everything_it_started(tmp_path):
    """UI plan §11: `ambience.smithy`, a low furnace roar. A bed that faded in from a
    click, or that kept a single source running, or kept rescheduling its crackles after
    stop(), would play on under the next screen. Measured: every source and oscillator the
    bed built is stopped, its gain ramps down rather than cutting, and running every
    pending timer after stop builds no new node."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      drain();
      const was = nodes.length;
      const bed = Sound.loop("ambience.smithy");
      const mine = nodes.slice(was);
      const out = {};
      const outGain = mine.find(n => n.kind === "gain" && n.to && n.to.kind === "gain"
                                     && n.gain.calls.some(c => c[0] === "exp"));
      out.fadeIn = outGain.gain.calls.slice(0, 2).map(c => c[0] + ":" + c[1]);
      out.lowpassRoar = mine.some(n => n.kind === "filter" && n.type === "lowpass"
                                       && n.frequency.value >= 250 && n.frequency.value <= 500);
      // Let a few of its crackles fire while it runs.
      FakeContext.last.state = "running";
      for (let i = 0; i < 3; i++) { const fns = pending.splice(0); fns.forEach(f => f()); }
      out.eventsWhileLive = nodes.length - was - mine.length;
      bed.stop();
      bed.stop();   // twice is harmless
      const running = mine.filter(n => (n.kind === "source" || n.kind === "osc") && !n.stopped);
      out.unstopped = running.length;
      out.fadeOut = outGain.gain.calls.slice(-1)[0];
      const before = nodes.length;
      drain();
      out.builtAfterStop = nodes.length - before;
      console.log(JSON.stringify(out));""")
    assert got["fadeIn"][0] == "set:0.0001" and got["fadeIn"][1] == "exp:1"
    assert got["lowpassRoar"], "the roar should sit at combustion's 250-500 Hz peak"
    assert got["eventsWhileLive"] > 0, "the bed's crackles never fired"
    assert got["unstopped"] == 0
    assert got["fadeOut"][0] == "exp" and got["fadeOut"][1] <= 0.001
    assert got["builtAfterStop"] == 0, "a stopped bed kept scheduling events"


# --- levels and settings ---------------------------------------------------------------------

def _forge_bodies() -> str:
    src = _read(SOUND)
    i = src.index("/* --- forge: the Blacksmithing bench")
    return src[i:src.index("/* --- ambience: beds that loop", i)]


def test_nothing_on_the_forge_bus_is_louder_than_a_combat_hit():
    """The owner asked the device sounds to be "not too loud", then "a bit louder"
    (2026-10-02). A strike is heard dozens of times in one craft, so no forge peak may
    reach combat.hit's body (0.24), the loudest everyday sound in the app."""
    src = _read(SOUND)
    hit = src[src.index('def("combat.hit"'):src.index('def("combat.miss"')]
    ceiling = max(float(x) for x in re.findall(r"peak: ([0-9.]+)", hit))
    peaks = [float(x) for x in re.findall(r"peak: ([0-9.]+)", _forge_bodies())]
    assert len(peaks) > 40, "the parse found too few forge peaks; it is stale"
    assert max(peaks) < ceiling, max(peaks)


def test_the_forge_bank_cites_what_it_is_grounded_in():
    """CLAUDE.md: search for how it is already done before designing, and cite it. The
    anvil's ring, the hardness-to-pitch rule and the quench's hiss each rest on a source,
    and a later edit that drops the sources loses the reason the numbers are what they are.
    sound.js may not hold a URL scheme (test_sound.py bans http:// and https://), so the
    sources are named by host and title."""
    # The comment's line breaks and leading asterisks folded away, so a title wrapped
    # across two comment lines still reads as one phrase.
    head = re.sub(r"\s*\n\s*\*?\s*", " ", _forge_bodies())
    for cite in ("blacksmithtalk.com", "laopera.org", "engineeringtoolbox.com",
                 "Investigation of sound phenomena during quenching process",
                 "Combustion roar of premix burners"):
        assert cite in head, cite


def test_the_settings_pane_has_a_forge_slider_beside_bench():
    """UI plan §6.8: "Settings gains a Forge volume on the sound buses beside Bench". The
    slider writes `sound.forge`, samples a forge strike when let go, and sits right after
    Bench in the list."""
    home = _read(HOME)
    block = home[home.index("const SOUND_SLIDERS = ["):home.index("function prefGet(")]
    keys = re.findall(r'key: "([a-z.]+)"', block)
    assert keys.index("sound.forge") == keys.index("sound.bench") + 1, keys
    assert 'label: "Forge", sample: "forge.strike.hit"' in block
    prefs = _read(PREFS)
    assert '"sound.forge": 0.8' in prefs
    assert 'forge: "sound.forge"' in _read(SOUND)
