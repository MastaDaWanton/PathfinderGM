"""The Leatherworking bench's sounds (play/static/js/sound.js `leather` bus; leatherworking
UI plan §11, contracts §11.1, lane U6).

Every leather caller plays `Sound.play("leather.<event>", {...})` and never guards, because
an unknown name is silent by contract. That is exactly how the enchant lane found sixteen
circle sounds already called and every one silent (tests/test_enchant_sound.py); when this
lane started, the leather shell, games and stage were being written in parallel and no
leather name existed at all. These tests hold:

- every event UI plan §11 names (its `<name>` filled from the engine's methods and `<form>`
  from the rack's forms), every event this lane offered the other UI lanes, and every
  leather name their merged code calls, exists and builds sound under every option it reads;
- every form on the rack and every kind on the shelf has a drop sound;
- the physics the bank is grounded in still shows in what it builds: a knife through fur is
  low and soft, over scale bright and ticking; a creak's slips come closer as the pull
  builds; a wet stamp is lower than a dry one; the kettle is loudest just under the boil;
  the fleshing scrape stays out of the squeak band; a miss never rings and a hit does;
- the Leatherworking slider scales its bus live; the tannery bed stops everything it starts;
- no leather sound is louder than a combat hit, under any option.

Behaviour runs the real prefs.js and sound.js in node against a stand-in Web Audio that
keeps every node (tests/test_alchemy_sound.py's), and skips without node.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from rules import leatherworker as lw

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "play" / "static" / "js"
SOUND = JS / "sound.js"
PREFS = JS / "prefs.js"
HOME = ROOT / "play" / "templates" / "play" / "home.html"
UI_PLAN = ROOT / "docs" / "leatherworking-ui-plan.md"
TABLE = JS / "table"
MATERIALS = ROOT / "content" / "materials" / "leatherworker-materials.json"

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

METHODS = sorted(lw.METHODS)
FORMS = sorted(lw.FORMS)

# What this lane offers lanes U1, U3 and U4 (2026-10-08), whose code is being written in
# parallel and calls no sound yet: the games' beat and miss, the creak of a good stroke,
# and the drops the rack's other words may send. Their merged code is read below as well,
# so a name they add later is checked too.
OFFERED = {
    "leather.hit", "leather.miss", "leather.creak", "leather.drop.hide",
    "leather.drop.leather", "leather.drop.hard", "leather.drop.grain",
    "leather.drop.liquid", "leather.drop.soft", "leather.drop.metal", "leather.drop.item",
    "ambience.yard", "works.ready", "works.collect",
}


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _promised() -> set[str]:
    """Every leather and ambience sound UI plan §11 names, `<name>` filled with the engine's
    methods and `<form>` with the rack's forms."""
    text = _read(UI_PLAN)
    i = text.index("## 11. Sound")
    sect = text[i:text.index("## 12.", i)]
    names = set()
    for raw in re.findall(r"`((?:leather|ambience)\.[a-z.<>-]+)`", sect):
        m = re.search(r"<(\w+)>", raw)
        if not m:
            names.add(raw)
            continue
        fill = METHODS if m.group(1) == "name" else FORMS
        names.update(raw.replace(m.group(0), v) for v in fill)
    return names


_PLAYED = re.compile(r'(?:Sound\.play|\bsound|\.sound|\bcue|playSound)\(\s*["\'](leather\.[a-z][a-z.-]*[a-z])["\']')
_SOUNDS_MAP = re.compile(r"SOUNDS:\s*\{([^}]*)\}")


def _called() -> set[str]:
    """OFFERED, plus every leather sound the merged leather games, stage and table files
    play: the values of a game's `SOUNDS` map, and the first argument of `Sound.play(...)`,
    `sound(...)` or `cue(...)`. Not every `leather.…` literal: lane U3 registers its games
    under "leather.flense", "leather.cut" and so on (the smith's game owns the bare
    "assemble" key), and those are game ids, not sounds."""
    names = set(OFFERED)
    files = []
    for d in (JS / "leather-games", JS / "tannery-stage"):
        if d.is_dir():
            files += list(d.glob("*.js"))
    files += [f for f in TABLE.glob("*.js") if "leather" in f.name or "harvest" in f.name]
    files.append(TABLE / "44-forge-ledger.js")
    for f in files:
        src = _read(f)
        names.update(_PLAYED.findall(src))
        for block in _SOUNDS_MAP.findall(src):
            names.update(re.findall(r'["\'](leather\.[a-z][a-z.-]*[a-z])["\']', block))
    return names


def test_the_games_sounds_are_read_from_their_sounds_maps():
    """A guard on `_called`: the lead's list of what lane U3's games play (2026-10-08), as a
    SOUNDS map would name them, is read back, and a game's registration id is not."""
    sample = ('defs["leather.flense"] = { id: "leather.flense", SOUNDS: { hit: "leather.scrape",'
              ' tear: "leather.tear" } }; Sound.play("leather.knife", {surface: s});')
    got = set(_PLAYED.findall(sample))
    for block in _SOUNDS_MAP.findall(sample):
        got.update(re.findall(r'["\'](leather\.[a-z][a-z.-]*[a-z])["\']', block))
    assert got == {"leather.scrape", "leather.tear", "leather.knife"}, got


# What the lead said lane U3's merged games play (2026-10-08): each must be defined.
GAMES_PLAY = ("leather.scrape", "leather.tear", "leather.salt", "leather.slosh",
              "leather.cut-test", "leather.knife", "leather.stitch.pull", "leather.steam",
              "leather.stamp", "leather.brush", "leather.clamp", "leather.buckle")


_FAKE = (ROOT / "tests" / "test_alchemy_sound.py").read_text(encoding="utf-8")
_FAKE = _FAKE[_FAKE.index('_FAKE = r"""') + len('_FAKE = r"""'):]
_FAKE = _FAKE[:_FAKE.index('"""')]


def _node(tmp_path, body: str) -> dict:
    src = (_FAKE + _read(PREFS) + "\n" + _read(SOUND)
           + "\nconst Sound = window.Sound, PGMPrefs = window.PGMPrefs;\n" + body)
    f = tmp_path / "leather_probe.js"
    f.write_text(src, encoding="utf-8")
    done = subprocess.run([NODE, str(f)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout.strip().splitlines()[-1])


OPTS = ("[undefined, { surface: 'fur' }, { surface: 'scale' }, { surface: 'smooth' },"
        " { surface: 'Feather ' }, { surface: 7 }, { casing: 0 }, { casing: 1 }, { casing: -3 },"
        " { casing: 'x' }, { heat: 0 }, { heat: 1 }, { heat: 9 }, { level: 0 }, { level: 1 },"
        " { level: -2 }, { pitch: 3 }, { pitch: 'x' }, { pitch: 99 }, { volume: 0.5 }]")


# --- the bank ------------------------------------------------------------------------------

def test_the_plan_names_the_events_this_file_checks():
    """A guard on the parse below: if UI plan §11 were reworded so the regex found nothing,
    the existence test would pass on an empty set. It named 23 sounds when written, plus a
    method family over the engine's twelve methods and a drop family over the rack's forms.
    `leather.cut-test` carries a hyphen, which the alchemy file's pattern did not allow."""
    names = _promised()
    for n in ("leather.open", "leather.roll", "leather.knife", "leather.tear",
              "leather.scrape", "leather.salt", "leather.slosh", "leather.cut-test",
              "leather.steam", "leather.stitch.pull", "leather.stamp", "leather.brush",
              "leather.clamp", "leather.buckle", "leather.tier.up", "leather.flawless",
              "leather.fail", "leather.land", "leather.grade", "ambience.tannery"):
        assert n in names, n
    assert {f"leather.method.{m}" for m in METHODS} <= names
    assert {f"leather.drop.{f}" for f in FORMS} <= names
    assert len(METHODS) == 12, METHODS


@needs_node
def test_every_promised_and_called_event_exists_and_builds_sound(tmp_path):
    """Every leather sound the plan promises, this lane offered, or another lane's merged
    code calls plays and builds nodes, with no options and under every option the bank
    reads, sane or not; an unknown leather name answers false and builds nothing. Running
    every synth under odd options also catches one that throws or ramps a gain to zero (a
    RangeError in real Web Audio), e.g. a `casing` of "x" or a `heat` of 9."""
    names = sorted(_promised() | _called() | set(GAMES_PLAY) | {"leather.found"})
    got = _node(tmp_path, "const names = " + json.dumps(names) + ";\n const opts = " + OPTS + r""";
      Sound.unlock();
      const out = { missing: [], silent: [], loops: [] };
      for (const n of names) {
        drain();
        if (!Sound.has(n)) { out.missing.push(n); continue; }
        if (n.startsWith("ambience.") || n.startsWith("works.")) {
          if (n.startsWith("ambience.")) { const l = Sound.loop(n);
            if (!l || typeof l.stop !== "function") out.loops.push(n); l.stop(); }
          continue;
        }
        for (const o of opts) {
          drain();
          const was = nodes.length;
          if (Sound.play(n, o) !== true || nodes.length === was) out.silent.push(n);
        }
      }
      drain();
      const was = nodes.length;
      out.unknown = [Sound.play("leather.boom"), Sound.play("leather.method.skin"),
                     Sound.play("leather.drop.plasma", { surface: "fur" })];
      out.unknownBuilt = nodes.length - was;
      console.log(JSON.stringify(out));""")
    assert got["missing"] == [], f"promised or called with no synthesizer: {got['missing']}"
    assert got["silent"] == [], f"built nothing: {sorted(set(got['silent']))}"
    assert got["loops"] == []
    assert got["unknown"] == [False, False, False] and got["unknownBuilt"] == 0


@needs_node
def test_every_form_and_kind_on_the_rack_has_a_drop_sound(tmp_path):
    """The shell drops a piece into a slot by whatever word it has: the rack's form (green,
    salted, pelt, leather, ... rules/leatherworker.py FORMS) or a supply's kind (eight on the
    shelf). A word with no `leather.drop.<word>` is silent by contract, so a piece the rack
    grows would land without a sound and nobody would hear it missing."""
    kinds = {m["kind"] for m in json.loads(_read(MATERIALS))["materials"]}
    words = sorted(kinds | set(FORMS) | {"item"})
    assert len(kinds) >= 8 and len(words) >= 18, words
    got = _node(tmp_path, "const words = " + json.dumps(words) + r""";
      Sound.unlock();
      console.log(JSON.stringify({ missing: words.filter(w => !Sound.has("leather.drop." + w)) }));""")
    assert got["missing"] == [], got["missing"]


# --- the physics the bank rests on -------------------------------------------------------

@needs_node
def test_the_knife_reads_the_surface_it_cuts(tmp_path):
    """UI plan §11: `leather.knife` is "pitch by hide surface: fur soft, scale sharp". A
    scrape is a noise source shaped by the surface under the edge (the source-filter model,
    arXiv 2112.08984): hair damps it, plates tick. Measured on the filters each play builds:
    through fur every band stays under 1.2 kHz and nothing ticks; over scale at least eight
    tick grains sit above 2.5 kHz; smooth grain sits between, and a surface the bench has
    never named (feather counts as soft, chitin and shell as hard) falls on a known source."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      const run = s => { const was = held("leather.knife", { surface: s });
        return freqs(was, "filter"); };
      console.log(JSON.stringify({ fur: run("fur"), scale: run("scale"), smooth: run("smooth"),
                                   feather: run("feather"), chitin: run("chitin"), none: run(undefined) }));""")
    assert max(got["fur"]) < 1200, got["fur"]
    assert max(got["feather"]) < 1200
    assert sum(1 for f in got["scale"] if f > 2500) >= 8, got["scale"]
    assert sum(1 for f in got["chitin"] if f > 2500) >= 8
    assert 1200 <= max(got["smooth"]) <= 2500, got["smooth"]
    assert got["none"] == got["smooth"] or 1200 <= max(got["none"]) <= 2500


@needs_node
def test_a_creaks_slips_come_closer_as_the_pull_builds(tmp_path):
    """Stick-slip (Farnell, "Designing Sound", Practical 9): the slip rate follows the force,
    so as the pull builds the slips come faster. A creak spaced evenly is a buzz, not leather
    giving. Measured on `leather.creak`'s main formant impulses (Q 6): the last gap is under
    half the first."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      const was = held("leather.creak");
      const times = nodes.slice(was).filter(n => n.kind === "filter" && n.Q.value === 6)
        .map(n => n.to.gain.calls.find(c => c[0] === "set")[2]);
      console.log(JSON.stringify({ times }));""")
    t = got["times"]
    assert len(t) >= 8, t
    gaps = [b - a for a, b in zip(t, t[1:])]
    assert gaps[-1] < gaps[0] / 2, gaps


@needs_node
def test_a_wet_stamp_is_lower_and_duller_than_a_dry_one(tmp_path):
    """UI plan §11: `leather.stamp` is "pitch by casing". Damp (cased) leather takes the
    stamp without the dry crack: measured as the knock's body (its lowest oscillator) and the
    crack's band, both lower at casing 1 than at casing 0."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      const run = w => { const was = held("leather.stamp", { casing: w });
        return [Math.min(...freqs(was, "osc")), Math.max(...freqs(was, "filter"))]; };
      console.log(JSON.stringify({ dry: run(0), wet: run(1) }));""")
    assert got["wet"][0] < got["dry"][0] * 0.75, got
    assert got["wet"][1] < got["dry"][1], got


@needs_node
def test_the_hardening_kettle_is_loudest_just_under_the_boil(tmp_path):
    """Hardening is leather plunged in hot water, and a kettle is quiet cold, loudest near
    80-90 °C, and quieter at a full boil (Aljishi and Tatarkiewicz, Am. J. Phys. 1991, the
    alchemy bank's curve). Measured as the summed envelope peaks of one `leather.steam`:
    0.85 > 1.0 > 0.3."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      const e = h => { const was = held("leather.steam", { heat: h }); return energy(was); };
      console.log(JSON.stringify({ e: [e(0.3), e(0.85), e(1)] }));""")
    cold, peak, full = got["e"]
    assert peak > full > cold, got["e"]


@needs_node
def test_the_fleshing_scrape_stays_out_of_the_squeak_band(tmp_path):
    """The fleshing scrape is heard on every hide. Reuter and Oehler found the 2000-4000 Hz
    band carries most of a chalkboard's unpleasantness (the enchant bank's chalk rule).
    Measured: every filter and oscillator frequency of each take stays under 2 kHz."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      const tops = [];
      for (let i = 0; i < 8; i++) { drain(); const was = nodes.length;
        Sound.play("leather.scrape"); tops.push(Math.max(...freqs(was))); }
      console.log(JSON.stringify({ tops }));""")
    assert max(got["tops"]) < 2000, got["tops"]


@needs_node
def test_a_miss_never_rings_and_a_hit_does(tmp_path):
    """UI plan §10: a good stroke is "a clean curl, a pull of thread, a soft creak"; a miss
    "a nick, a dull scrape". A miss with a ring in it would tell the ear the opposite of the
    words. Measured: every oscillator of `leather.miss` is under 400 Hz and stops within
    0.3 s; `leather.hit` has a partial over 1 kHz ringing past 0.4 s."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      let was = held("leather.miss"); const miss = oscs(was);
      was = held("leather.hit"); const hit = oscs(was);
      console.log(JSON.stringify({ miss, hit }));""")
    assert got["miss"] and all(f < 400 and stop < 0.3 for f, stop, _ in got["miss"]), got["miss"]
    assert any(f > 1000 and stop > 0.4 for f, stop, _ in got["hit"]), got["hit"]


# --- the slider and the bed ----------------------------------------------------------------

@needs_node
def test_the_leatherworking_slider_scales_its_bus(tmp_path):
    """Settings → Sound and motion gains a Leatherworking volume beside Alchemy. The leather
    bus starts at `sound.leather`, follows it live, and a leather sound plays into it, not
    into a neighbour's. A pref nobody wired would be a slider that moves and changes
    nothing."""
    got = _node(tmp_path, r"""
      PGMPrefs.set("sound.leather", 0.35);
      Sound.unlock();
      const out = { default: PGMPrefs.defaults()["sound.leather"] };
      const buses = nodes.filter(n => n.kind === "gain" && n.to && n.to.kind === "gain"
                                      && n.to.to && n.to.to.kind === "gain"
                                      && n.to.to.to && n.to.to.to.kind === "compressor");
      const mine = buses.filter(n => n.gain.value === 0.35);
      out.buses = mine.length;
      Sound.play("leather.hit");
      out.voiceOnLeather = nodes.filter(n => n.kind === "gain" && n.to === mine[0]).length;
      PGMPrefs.set("sound.leather", 0.1);
      out.after = mine[0].gain.calls.filter(c => c[0] === "target").map(c => c[1]);
      console.log(JSON.stringify(out));""")
    assert got["default"] == 0.8
    assert got["buses"] == 1, "exactly one bus should start at the leather pref"
    assert got["voiceOnLeather"] >= 1
    assert got["after"][-1] == 0.1


@needs_node
def test_the_tannery_bed_stops_everything_it_started(tmp_path):
    """UI plan §11: `ambience.tannery`, "water, a distant yard". A bed that kept a source
    running or kept scheduling its vat laps and drips after stop() would play on under the
    next screen. Measured: its events fire while live, every source and oscillator is
    stopped, and running every pending timer after stop builds no node."""
    got = _node(tmp_path, r"""
      Sound.unlock();
      drain();
      const was = nodes.length;
      const bed = Sound.loop("ambience.tannery");
      const mine = nodes.slice(was);
      FakeContext.last.state = "running";
      for (let i = 0; i < 3; i++) { const fns = pending.splice(0); fns.forEach(f => f()); }
      const out = { eventsWhileLive: nodes.length - was - mine.length };
      bed.stop();
      out.unstopped = mine.filter(n => (n.kind === "source" || n.kind === "osc") && !n.stopped).length;
      const before = nodes.length;
      drain();
      out.builtAfterStop = nodes.length - before;
      out.alias = Sound.has("ambience.yard");
      console.log(JSON.stringify(out));""")
    assert got["eventsWhileLive"] > 0, "the tannery's events never fired"
    assert got["unstopped"] == 0
    assert got["builtAfterStop"] == 0, "a stopped bed kept scheduling events"
    assert got["alias"] is True


# --- levels, sources and settings --------------------------------------------------------------

def _leather_bodies() -> str:
    src = _read(SOUND)
    i = src.index("/* --- leather: the Leatherworking bench")
    return src[i:src.index("/* --- ambience: beds that loop", i)]


@needs_node
def test_nothing_on_the_leather_bus_is_louder_than_a_combat_hit(tmp_path):
    """The owner asked for every sound louder (2026-10-05, the x6 makeup gain), and a game
    plays a stroke every half second: no leather envelope may reach combat.hit's body
    (0.24), the loudest everyday sound in the app. Measured in the stand-in, not parsed: the
    highest envelope peak any leather name builds under every option the bank reads (some
    peaks are computed from `heat` or `casing`, which a literal parse would miss)."""
    src = _read(SOUND)
    hit = src[src.index('def("combat.hit"'):src.index('def("combat.miss"')]
    ceiling = max(float(x) for x in re.findall(r"peak: ([0-9.]+)", hit))
    names = sorted(n for n in _promised() | _called() if n.startswith("leather."))
    got = _node(tmp_path, "const names = " + json.dumps(names) + ";\n const opts = " + OPTS + r""";
      Sound.unlock();
      let top = 0, who = "";
      for (const n of names) for (const o of opts) {
        drain(); const was = nodes.length; Sound.play(n, o);
        for (const g of nodes.slice(was)) { if (g.kind !== "gain") continue;
          for (const c of g.gain.calls) if (c[0] === "exp" && c[1] > top) { top = c[1]; who = n; } }
      }
      console.log(JSON.stringify({ top, who }));""")
    assert 0 < got["top"] < ceiling, got


def test_the_leather_bank_cites_its_sources_and_names_no_planet():
    """CLAUDE.md: search first, cite what is used. Every shape in the bank rests on a source
    named in its header, by title since sound.js may hold no URL. And the owner, round 4: no
    planets anywhere, so none may key a sound. No em-dash or en-dash in the new strings."""
    body = _leather_bodies()
    head = re.sub(r"\s*\n\s*\*?\s*", " ", body)
    for cite in ("Designing Sound", "Practical 9", "Object-based synthesis of scraping and "
                 "rolling sounds based on non-linear physical constraints",
                 "The Sounding Object", "Aljishi and Tatarkiewicz", "Reuter and Oehler"):
        assert cite in head, cite
    code = re.sub(r"//[^\n]*|/\*.*?\*/", "", body, flags=re.S).lower()
    for planet in ("saturn", "jupiter", "mars", "venus", "mercury", "moon"):
        assert planet not in code, planet
    assert "—" not in body and "–" not in body


def test_the_settings_pane_has_a_leatherworking_slider_after_alchemy():
    """Settings → Sound and motion: a Leatherworking volume right after the Alchemy one,
    writing `sound.leather` and sampling a game's good stroke when let go; the pref has its
    default, and the bus reads it."""
    home = _read(HOME)
    block = home[home.index("const SOUND_SLIDERS = ["):home.index("function prefGet(")]
    keys = re.findall(r'key: "([a-z.]+)"', block)
    assert keys.index("sound.leather") == keys.index("sound.alchemy") + 1, keys
    assert 'label: "Leatherworking", sample: "leather.hit"' in block
    assert '"sound.leather": 0.8' in _read(PREFS)
    assert 'leather: "sound.leather"' in _read(SOUND)
