"""The app's sound (play/static/js/sound.js) and the player's preferences (prefs.js).

Lane G of the herbalism revamp (docs/herbalism-contracts.md §5.3, revamp plan §11, UI plan
§6.9 and §11). The app made no sound at all before this, except the dice clack, which went
straight to the speakers and could only be silenced through a localStorage key nobody could
reach. These tests hold what that took to change:

- every sound name another lane is promised exists, so `Sound.play("bench.hit.steep")` is
  never a silent typo nobody hears is missing;
- nothing is a sample file or a download (contracts §0: this batch has none);
- every caller still works on a page that loads no sound.js (contracts §5: "every consumer
  must work when a provider is missing");
- a preference read never throws, because localStorage throws rather than returning null
  when it is blocked, full or disabled.

The behaviour tests run the real scripts in node against a stand-in Web Audio, and skip
when node is not installed (as tests/test_template_scripts.py does).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.test import Client

from rules.biomes import BIOMES

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "play" / "static" / "js"
SOUND = JS / "sound.js"
PREFS = JS / "prefs.js"
HOME = ROOT / "play" / "templates" / "play" / "home.html"
CALLERS = [JS / "dice3d.js", JS / "table" / "22-roll-verdict.js",
           JS / "table" / "04-combat-and-turns.js", HOME]

METHODS = ["grind", "mix", "brew", "dry", "reduce", "extract", "infuse", "steep",
           "neutralize"]
# contracts §2, the `part` field's values.
PARTS = ["leaf", "flower", "root", "bark", "berry", "seed", "sap", "resin", "fungus",
         "gland", "organ", "bone", "horn", "feather", "scale", "eye", "shell", "oil", "wax",
         "mineral", "liquid"]
# Lane G's brief, plus every canonical biome the bench's ground can report.
AMBIENCES = ["forest", "swamp", "tundra", "desert", "grassland", "road", "indoors",
             "tavern", "night"] + sorted(BIOMES)

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _section(text: str, start: str, stop: str) -> str:
    i = text.index(start)
    return text[i:text.index(stop, i + len(start))]


def _promised_names() -> set[str]:
    """Every sound name the plans and the contract promise, with the placeholders
    (`<method>`, `<part>`, `<biome>`, `<name>`) expanded over their vocabularies."""
    docs = ROOT / "docs"
    text = (_section(_read(docs / "herbalism-ui-plan.md"), "## 11. Sound hooks", "## 12.")
            + _section(_read(docs / "herbalism-contracts.md"),
                       "### 5.3", "### 5.4"))
    names = set()
    for raw in re.findall(r"`((?:ui|dice|bench|ambience|combat|verdict)\.[a-z.<>]+)`", text):
        if raw.endswith(".") or raw.endswith("*"):
            continue
        m = re.search(r"<(\w+)>", raw)
        if not m:
            names.add(raw)
            continue
        fill = {"method": METHODS, "name": METHODS, "part": PARTS,
                "biome": AMBIENCES}[m.group(1)]
        names.update(raw.replace(m.group(0), v) for v in fill)
    # Lane G's brief names these as well (bench, dice, verdict, ui, combat).
    names.update(["bench.open", "bench.roll", "bench.tick", "bench.tier.up",
                  "bench.flawless", "bench.fail", "bench.land", "bench.taste",
                  "bench.study", "dice.roll", "dice.land", "verdict.success",
                  "verdict.failure", "ui.click", "ui.open", "ui.close", "ui.page",
                  "combat.hit", "combat.miss", "combat.crit"])
    names.update(f"bench.{k}.{m}" for k in ("method", "hit", "miss") for m in METHODS)
    names.update(f"bench.drop.{p}" for p in PARTS)
    names.update(f"ambience.{b}" for b in AMBIENCES)
    return names


# A stand-in Web Audio: every node takes every call, and the context records what it
# made, so a test can tell "built a sound" from "built nothing".
_FAKE_AUDIO = r"""
const made = [];
function Param(v) { return { value: v, calls: [],
  setValueAtTime(x, t) { this.calls.push(["set", x, t]); this.value = x; },
  exponentialRampToValueAtTime(x, t) {
    if (!(x > 0)) throw new Error("exponential ramp to " + x); this.calls.push(["exp", x, t]); },
  linearRampToValueAtTime(x, t) { this.calls.push(["lin", x, t]); },
  setTargetAtTime(x, t, k) { this.calls.push(["target", x, t]); this.value = x; },
  cancelScheduledValues() {} }; }
function Node(kind) { const n = { kind, connect(d) { return d; }, disconnect() {},
  start() {}, stop() {}, gain: Param(1), frequency: Param(440), Q: Param(1),
  threshold: Param(0), knee: Param(0), ratio: Param(1), attack: Param(0), release: Param(0),
  type: "", buffer: null, loop: false }; made.push(kind); return n; }
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
let storageBroken = false;
const localStorage = {
  getItem(k) { if (storageBroken) throw new Error("SecurityError"); return k in store ? store[k] : null; },
  setItem(k, v) { if (storageBroken) throw new Error("QuotaExceededError"); store[k] = String(v); },
};
const listeners = {};
const window = {
  AudioContext: FakeContext, localStorage,
  matchMedia: () => ({ matches: false, addEventListener() {} }),
  addEventListener(k, fn) { (listeners[k] = listeners[k] || []).push(fn); },
  removeEventListener() {},
};
const navigator = {};
"""


def _node(tmp_path, body: str, scripts=(PREFS, SOUND)) -> dict:
    # In a browser `window` is the global object, so the scripts' `window.Sound` is
    # reachable as `Sound`; in node the stand-in `window` is a plain object, so say so.
    alias = ("\nconst Sound = window.Sound, PGMPrefs = window.PGMPrefs;\n"
             if scripts else "\n")
    src = _FAKE_AUDIO + "\n".join(_read(p) for p in scripts) + alias + body
    f = tmp_path / "probe.js"
    f.write_text(src, encoding="utf-8")
    done = subprocess.run([NODE, str(f)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout.strip().splitlines()[-1])


# --- the bank ------------------------------------------------------------------------------

@needs_node
def test_every_promised_name_has_a_synthesizer_and_none_of_them_throws(tmp_path):
    """Every name in UI plan §11, contracts §5.3 and the lane brief plays, and builds real
    nodes, after a gesture. An unknown name answers false and builds nothing.

    The defect this prevents: `Sound.play` of an unknown name is a silent no-op by
    contract, so a misspelled or missing synth (`bench.hit.neutralise`, or a part added to
    contracts §2 with no drop sound) is exactly the bug nobody hears is there. It also runs
    every synth's code path, so one that throws or ramps a gain to zero (an
    `exponentialRampToValueAtTime(0)` is a RangeError in real Web Audio) fails here."""
    names = sorted(_promised_names())
    got = _node(tmp_path, "const names = " + json.dumps(names) + r""";
      // The timers that end each voice, held so the test decides when a sound is over.
      const pending = [];
      const setTimeout = fn => { pending.push(fn); return 0; };
      const drain = () => { while (pending.length) pending.shift()(); };
      const out = { before: Sound.play("ui.click"), missing: [], silent: [], loops: [] };
      window.Sound.unlock();
      // The voice cap: a runaway caller (a game loop playing every frame) is refused
      // past 28 sounds at once instead of stacking hundreds of node graphs.
      const burst = [];
      for (let i = 0; i < 30; i++) burst.push(Sound.play("bench.tick"));
      out.capped = burst.filter(x => !x).length;
      drain();
      for (const n of names) {
        drain();
        if (!Sound.has(n)) { out.missing.push(n); continue; }
        if (n.startsWith("ambience.")) {
          const l = Sound.loop(n);
          if (!l || typeof l.stop !== "function") out.loops.push(n);
          l.stop(); continue;
        }
        const was = made.length;
        if (Sound.play(n, { volume: 0.7, rate: 1.1 }) !== true || made.length === was) out.silent.push(n);
      }
      const was = made.length;
      out.unknown = [Sound.play("bench.hit.neutralise"), Sound.play("nothing"),
                     Sound.play(undefined), Sound.play("ui.click", null)];
      out.unknownBuilt = made.length - was;
      out.badLoop = typeof Sound.loop("ambience.the-moon").stop;
      console.log(JSON.stringify(out));
      process.exit(0);""")
    assert got["before"] is False, "a sound before any gesture must be dropped, not queued"
    assert got["capped"] == 2, "the 29th and 30th simultaneous sounds should be refused"
    assert got["missing"] == [], f"names promised with no synthesizer: {got['missing']}"
    assert got["silent"] == [], f"names that built nothing: {got['silent']}"
    assert got["loops"] == []
    assert got["unknown"][:3] == [False, False, False]
    assert got["badLoop"] == "function"


def test_every_sound_has_two_to_four_takes():
    """Revamp plan §11: "two to four takes per sound". A single take repeated a hundred
    times in one grind session is the machine-gun effect; more than four is weight in the
    file nobody can tell apart."""
    src = _read(SOUND)
    takes = re.findall(r'\bdef\(\s*"?[^,]+,\s*(\d+)\s*,', src)
    # 24 written out, plus the method, hit, miss and drop families defined in loops.
    assert len(takes) >= 20, f"found only {len(takes)} def() calls; the parse is stale"
    assert re.search(r'def\("bench\.(method|hit|miss)\." \+ m, [234],', src)
    assert re.search(r'def\("bench\.drop\." \+ part, [234],', src)
    assert all(2 <= int(n) <= 4 for n in takes), takes
    # ±5% pitch on every play, on top of the take.
    assert "0.95 + Math.random() * 0.1" in src


def test_no_audio_file_and_no_third_party_code():
    """Contracts §0: no downloads and no third-party JavaScript. Every sound is
    synthesized; a sample file, a data URI or a fetched library would each be an asset
    the installer ships (or fetches) that this batch has none of."""
    for p in (SOUND, PREFS):
        src = _read(p)
        # A file name ends in a quote; `o.wave` is an oscillator's waveform, not a .wav.
        assert not re.search(r"\.(mp3|wav|ogg|flac|m4a|opus)[\"'?]", src), p.name
        for bad in ("base64", "data:audio", "http://", "https://", "import ", "require(",
                    "fetch(", "new Audio(", "decodeAudioData"):
            assert bad not in src, f"{p.name} contains {bad!r}"
    # The one exception is the owner's own soundtrack (2026-10-02, play/static/audio/music,
    # played by music.js and recorded in docs/asset-licences.md). Sound EFFECTS stay
    # synthesized: any other audio file in the static tree is still a stray asset.
    static = ROOT / "play" / "static"
    music = static / "audio" / "music"
    audio = [f for ext in ("mp3", "wav", "ogg", "flac", "m4a", "opus")
             for f in static.rglob(f"*.{ext}") if music not in f.parents]
    assert audio == [], audio
    licences = (ROOT / "docs" / "asset-licences.md").read_text(encoding="utf-8")
    assert all(f.name in licences or f.stem.rsplit("-", 1)[0] in licences
               for f in music.rglob("*.mp3"))
    # Built from the raw material, as the header says.
    src = _read(SOUND)
    assert "createOscillator" in src and "createBufferSource" in src \
        and "createBiquadFilter" in src


# --- the callers -------------------------------------------------------------------------

def _enclosing(src: str, at: int) -> str:
    """The text from the start of the function holding `at` up to `at`."""
    starts = [m.start() for m in re.finditer(r"\bfunction\b|=>", src[:at])]
    return src[starts[-1] if starts else 0:at]


@pytest.mark.parametrize("path", CALLERS, ids=lambda p: p.name)
def test_every_call_site_is_guarded(path):
    """Contracts §5: every consumer must work when the provider is missing. craft.html
    loads dice3d.js and, until Lane D adds the tags, no sound.js; an unguarded
    `Sound.play` there is a ReferenceError that kills the throw it was decorating. Each
    call is `window.Sound && Sound.play(...)` on its line, or sits in a function that has
    already returned when `window.Sound` is missing."""
    src = _read(path)
    calls = [m.start() for m in re.finditer(r"(?<![\w.])Sound\.(play|loop)\(", src)]
    assert calls, f"{path.name} plays no sound at all"
    for at in calls:
        line = src[src.rfind("\n", 0, at) + 1:at]
        guarded = "window.Sound &&" in line or re.search(
            r"if \(!window\.Sound\b[^)]*\)\s*return", _enclosing(src, at))
        assert guarded, f"{path.name}: unguarded call at …{src[at - 60:at + 30]!r}"


def test_the_dice_clack_obeys_the_volume_and_keeps_its_fallback():
    """The clack went straight to `ctx.destination`, ignoring every slider. With sound.js
    present it is `dice.land` on the dice bus, scheduled at the same contact offset (the
    `delay`); without it, the file's own synth still sounds (test_dice3d.py pins that)."""
    src = _read(JS / "dice3d.js")
    clack = src[src.index("function clack("):src.index("function reducedMotion(")]
    assert 'Sound.play("dice.land"' in clack and "delay:" in clack
    assert clack.index("Sound.play") < clack.index("audio()"), \
        "the fallback synth runs before the app-wide sound is asked"
    assert 'Sound.play("dice.roll"' in src[src.index("function tumble("):]


@needs_node
def test_a_resolved_attack_is_heard_once_with_its_crit(tmp_path):
    """04-combat-and-turns.js sounds the attacks a reply ADDED to the log. The log is a
    sliding window of thirty entries with no ids, so a naive "sound every attack in the
    log" replays the whole fight on every turn; this aligns the old window against the new
    one. A critical is the hit whose "Confirm critical" roll met the AC (the engine's own
    test); a threat that failed to confirm is a plain hit."""
    src = _read(JS / "table" / "04-combat-and-turns.js")
    fns = src[src.index("function newLogEntries("):src.index("async function commitTurn(")]
    got = _node(tmp_path, fns + r"""
      const heard = [];
      window.Sound = { play: (n, o) => { heard.push(n); return true; } };
      const Sound = window.Sound;
      const atk = (verdict, rolls) => ({ kind: "turn", outcomes: [{ op: "attack", verdict,
        dc: { value: 15 }, rolls }] });
      const swing = { label: "Attack (rapier)", total: 18 };
      const A = atk("hit", [swing]), B = atk("miss", [{ label: "Attack", total: 9 }]);
      const C = atk("hit", [swing, { label: "Confirm critical (rapier)", total: 16 }]);
      const D = atk("hit", [swing, { label: "Confirm critical (rapier)", total: 11 }]);
      const npc = { kind: "npc", outcomes: [] };
      const out = {};
      out.appended = newLogEntries([A, npc], [A, npc, B, npc]).length;
      out.same = newLogEntries([A, B], [A, B]).length;
      const full = Array.from({ length: 30 }, (_, i) => ({ kind: "turn", n: i, outcomes: [] }));
      out.shifted = newLogEntries(full, full.slice(1).concat([C])).length;
      (async () => {
        attackSounds([A], [A, B, C, D, npc], null);
        await new Promise(r => setTimeout(r, 10));
        out.heard = heard.slice();
        heard.length = 0;
        attackSounds([A, B], [A, B], null);
        await new Promise(r => setTimeout(r, 10));
        out.replayed = heard.length;
        window.Sound = undefined;
        attackSounds([], [C], null);   // no sound.js: nothing, and nothing thrown
        console.log(JSON.stringify(out));
      })();""", scripts=())
    assert got["appended"] == 2 and got["same"] == 0 and got["shifted"] == 1
    assert got["heard"] == ["combat.miss", "combat.crit", "combat.hit"]
    assert got["replayed"] == 0, "an old attack was heard again"


def test_the_verdict_sting_plays_with_the_word():
    """22-roll-verdict.js: the sting starts where the word is made, before the reduced-
    motion branch, because Short (UI plan §6.9) keeps the sounds."""
    src = _read(JS / "table" / "22-roll-verdict.js")
    fn = src[src.index("async function showVerdict("):src.index("function verdictWord(")]
    assert '"verdict.success"' in fn and '"verdict.failure"' in fn
    assert fn.index("verdictWord(f") < fn.index("Sound.play") < fn.index("if (!f.still)")


# --- preferences ---------------------------------------------------------------------------

def _strip_try_blocks(src: str) -> str:
    """The source with every `try { ... }` body removed (braces matched)."""
    out, i = [], 0
    while True:
        j = src.find("try {", i)
        if j < 0:
            out.append(src[i:])
            return "".join(out)
        out.append(src[i:j])
        depth, k = 0, j + 4
        while True:
            if src[k] == "{":
                depth += 1
            elif src[k] == "}":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        i = k + 1


@pytest.mark.parametrize("path", [PREFS, SOUND], ids=lambda p: p.name)
def test_storage_and_media_queries_are_only_touched_inside_try(path):
    """localStorage THROWS (SecurityError, QuotaExceededError) when storage is disabled,
    blocked by a privacy setting, or full; it does not return null. A preference read
    outside a try would take the Settings pane, the sound and the bench's games down with
    it over a volume level."""
    rest = _strip_try_blocks(_read(path))
    code = re.sub(r"/\*.*?\*/|//[^\n]*", "", rest, flags=re.S)
    for touchy in ("localStorage.", ".matchMedia(", "PGMPrefs.get(", "PGMPrefs.on("):
        assert touchy not in code, f"{path.name}: {touchy} outside a try block"


@needs_node
def test_prefs_have_their_defaults_survive_broken_storage_and_tell_listeners(tmp_path):
    """The contract's keys and defaults; coercion of whatever a slider or a hand-edited
    store holds; a change heard by `on` listeners, in this window and (through the
    `storage` event) from another; and with storage throwing on every call, defaults and
    in-memory values instead of an exception."""
    got = _node(tmp_path, r"""
      const out = {};
      out.defaults = PGMPrefs.defaults();
      const heard = [];
      PGMPrefs.on("sound.ui", (v, k) => heard.push([k, v]));
      out.clamped = [PGMPrefs.set("sound.ui", "7"), PGMPrefs.set("sound.ui", -1),
                     PGMPrefs.set("sound.ui", "loud"), PGMPrefs.set("sound.ui", 0.25)];
      out.stored = store["pgm.pref.sound.ui"];
      out.flags = [PGMPrefs.set("steady", "true"), PGMPrefs.set("flourishes", "wild"),
                   PGMPrefs.set("flourishes", "short")];
      // Another window wrote it.
      store["pgm.pref.sound.ui"] = "0.5";
      listeners.storage.forEach(fn => fn({ key: "pgm.pref.sound.ui" }));
      out.heard = heard;
      // The old dice-only switch still silences the dice until the slider is moved.
      store["pfgm.dice.mute"] = "1";
      out.legacy = PGMPrefs.get("sound.dice");
      storageBroken = true;
      out.broken = [PGMPrefs.get("sound.master"), PGMPrefs.set("sound.master", 0.3),
                    PGMPrefs.get("sound.master"), PGMPrefs.get("steady")];
      console.log(JSON.stringify(out));
      process.exit(0);""", scripts=(PREFS,))
    assert got["defaults"] == {"steady": False, "flourishes": "full", "sound.master": 0.8,
                               "sound.ui": 0.6, "sound.dice": 0.8, "sound.bench": 0.8,
                               # The Blacksmithing bench's bus (forge UI plan §6.8).
                               "sound.forge": 0.8,
                               "sound.ambience": 0.4, "sound.combat": 0.7,
                               "sound.mute": False,
                               # The owner's soundtrack (music.js, 2026-10-02).
                               "sound.music": 0.45, "music.on": True}
    assert got["clamped"] == [1, 0, 0.6, 0.25] and got["stored"] == "0.25"
    assert got["flags"] == [True, "full", "short"]
    assert got["heard"][-1] == ["sound.ui", 0.5], got["heard"]
    assert got["legacy"] == 0
    assert got["broken"] == [0.8, 0.3, 0.3, False]


@needs_node
def test_the_buses_follow_the_sliders_and_mute_builds_nothing(tmp_path):
    """Each bus gain is bound to its PGMPrefs volume live (a slider in another window
    moves this window's mix), and a muted app builds no nodes at all rather than playing
    into a zero gain thousands of times."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      Sound.play("ui.click");
      const ctx = FakeContext.last;
      const out = {};
      const before = made.length;
      PGMPrefs.set("sound.mute", true);
      out.mutedPlay = Sound.play("bench.flawless");
      out.mutedBuilt = made.length - before;
      PGMPrefs.set("sound.mute", false);
      out.unmuted = Sound.play("bench.flawless");
      console.log(JSON.stringify(out));
      process.exit(0);""")
    assert got["mutedPlay"] is False and got["mutedBuilt"] == 0
    assert got["unmuted"] is True
    src = _read(SOUND)
    for key in ("sound.ui", "sound.dice", "sound.bench", "sound.ambience", "sound.combat"):
        assert f'"{key}"' in src
    assert 'p.on("sound.master"' in src and 'p.on("sound.mute"' in src


# --- the Settings pane ---------------------------------------------------------------------

def _settings_block() -> str:
    src = _read(HOME)
    return _section(src, "/* --- Sound and motion", "function paneSettings()")


def test_the_settings_group_has_every_control_and_no_dashes():
    """UI plan §6.9: master, a slider per bus, mute, Steady mode with its one plain line,
    and Flourishes Full or Short. The brief and UI plan §8 ban em-dashes and en-dashes in
    new player-facing strings; this pane's neighbours have plenty, so the check is on the
    new block alone."""
    block = _settings_block()
    for key in ("sound.master", "sound.ui", "sound.dice", "sound.bench", "sound.ambience",
                "sound.combat", "sound.mute", "steady", "flourishes"):
        assert f'"{key}"' in block, key
    assert "Slower minigames, and every hold becomes a press." in " ".join(block.split())
    assert 'value="full"' in block and 'value="short"' in block
    assert "—" not in block and "–" not in block
    # A sample of the bus when a slider is let go, not on every step of a drag.
    assert 'document.addEventListener("change"' in block and "soundSample(el.dataset.sample)" in block


def test_the_home_page_renders_and_loads_prefs_then_sound_before_its_own_script():
    """The page draws the Settings pane from `PGMPrefs` on load, so the two files must be
    loaded ahead of its inline script; behind it, the pane drew with every default and
    ignored what the player had set."""
    r = Client().get("/")
    assert r.status_code == 200
    html = r.content.decode("utf-8")
    p = html.index("/static/js/prefs.js")
    s = html.index("/static/js/sound.js")
    inline = html.index("const STATE = ")
    assert p < s < inline
    assert "Sound and motion" in html
    for src in ("/static/js/prefs.js", "/static/js/sound.js"):
        assert Client().get(src).status_code == 200


def test_the_mix_has_makeup_gain_so_maxed_sliders_are_audible():
    """The owner, 2026-10-05: "make all the sounds except for music louder, right now they
    are maxxed out and i can barely hear them." Measured with every slider at its top:
    combat.hit peaked at 0.043 of full scale, a forge strike 0.031-0.037, a herb grind hit
    0.021 (about -28 dBFS), against music's mastered tracks. A makeup gain of at least x4
    sits between the master volume and the limiter, so the limiter still guards clipping."""
    import re
    from pathlib import Path

    src = Path("play/static/js/sound.js").read_text(encoding="utf-8")
    m = re.search(r"var MAKEUP = (\d+(?:\.\d+)?);", src)
    assert m and float(m.group(1)) >= 4, "the makeup gain is missing or too small"
    assert "master.connect(makeup);" in src and "makeup.connect(limiter);" in src
    assert "master.connect(limiter);" not in src, "the makeup stage was bypassed"
