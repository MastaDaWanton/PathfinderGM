"""Herbalism's Mix game (play/static/js/bench-games/mix.js): the trace a player makes, and
what the strip shows them to trace.

The owner's report, 2026-10-06: "the trace for mix in herbalism is impossible", then "i
thought the squiggly line that ran across the bar was what i was supposed to trace". The
texture gauge was a 120px wavy stroke, the biggest line on the strip; the real guide beside
it was thin dashes. Measured the same day with a human-model bot (a hand moving along the
lit segment at 150-600 px/s with a few pixels of wobble), in node and with real mouse events
in the running herb bench:

- tracing the RIGHT line already made 100% of segments; the defect was what the strip showed;
- but a player who took 1.2s to find the start lost the first segment every time (0.83-0.88),
  and in the live bench after the first-time card is gone, the first segment was lost in
  every run (the clock started while the strip was still sliding up);
- joining the lit segment 25px along never counted on the eight or the fold (0.75-0.88);
- following the bead 0.2s behind scored 0.38-0.54 (the bead reached the end at the deadline);
- cutting across the circle through its centre made every segment (0.66; Steady 0.72-0.84),
  and a ten-pixel wobble scored the same as a careful hand (0.95-1.00).

These tests drive the game through `BenchGames.simulate`, the frame's own headless path, with
the same bot. The bot reads only what the strip draws: the lit segment is the path stroked in
gold, as the player sees it. Each docstring names the measurement it holds.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "play" / "static" / "js"
METHODS = ["grind", "mix", "brew", "dry", "reduce", "extract", "infuse", "steep", "neutralize"]
PATTERNS = ["circle", "eight", "fold"]

_DRIVER = r"""// Node driver for tests/test_mix_trace.py. A human-model hand plays Mix through
// BenchGames.simulate; everything it knows of the game it reads from the strip's own drawing.
"use strict";
const fs = require("fs"), vm = require("vm");
const files = JSON.parse(process.argv[2]), plays = JSON.parse(process.argv[3]);
const sandbox = { window: {}, Math, JSON, Object, Array, Promise, console, performance: { now: () => 0 } };
sandbox.window.window = sandbox.window;
vm.createContext(sandbox);
for (const f of files) vm.runInContext(fs.readFileSync(f, "utf8"), sandbox);
const BG = sandbox.window.BenchGames;
const W = 370, H = 118, DT = 1 / 60;   // the meter measured in the live herb bench at 1440px

function mulberry(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function recorder() {
  const paths = [], texts = [], fills = [], st = { strokeStyle: null, lineWidth: 1, fillStyle: null }, stack = [];
  let rot = null;
  let cur = [];
  const g = new Proxy({}, {
    get(t, k) {
      if (k === "beginPath") return () => { cur = []; };
      if (k === "moveTo" || k === "lineTo" || k === "arc") return (x, y) => { cur.push([x, y]); };
      if (k === "stroke") return () => { paths.push({ pts: cur.slice(), style: st.strokeStyle, w: st.lineWidth }); };
      if (k === "rotate") return (a) => { rot = a; };
      if (k === "fill") return () => { fills.push({ style: st.fillStyle, rot }); };
      if (k === "fillText") return (s, x, y) => { texts.push([String(s), x, y]); };
      if (k === "save") return () => stack.push(Object.assign({}, st));
      if (k === "restore") return () => Object.assign(st, stack.pop() || {});
      if (k === "measureText") return (s) => ({ width: String(s).length * 6.5 });
      if (k in st) return st[k];
      if (k in t) return t[k];
      return () => {};
    },
    set(t, k, v) { if (k in st) st[k] = v; else t[k] = v; return true; }
  });
  return { g, paths, texts, fills, reset() { paths.length = 0; texts.length = 0; fills.length = 0; rot = null; } };
}
function polyLen(p) { let L = 0; for (let i = 1; i < p.length; i++) L += Math.hypot(p[i][0] - p[i - 1][0], p[i][1] - p[i - 1][1]); return L; }
function along(p, u) {
  let acc = 0;
  for (let i = 1; i < p.length; i++) {
    const l = Math.hypot(p[i][0] - p[i - 1][0], p[i][1] - p[i - 1][1]);
    if (acc + l >= u || i === p.length - 1) {
      const f = l ? Math.max(0, Math.min(1, (u - acc) / l)) : 0;
      return { x: p[i - 1][0] + (p[i][0] - p[i - 1][0]) * f, y: p[i - 1][1] + (p[i][1] - p[i - 1][1]) * f,
        tx: l ? (p[i][0] - p[i - 1][0]) / l : 1, ty: l ? (p[i][1] - p[i - 1][1]) / l : 0 };
    }
    acc += l;
  }
  return { x: p[0][0], y: p[0][1], tx: 1, ty: 0 };
}

// kind: "trace" (follow the lit segment), "bead" (follow the bead `lag` behind), "cut"
// (straight from the lit segment's start through the figure's centre to its end), "keys".
function play(cfg) {
  const R = mulberry(cfg.seed * 7919 + 13);
  const s = BG.simulate({ method: "mix", steady: !!cfg.steady,
    tuning: { seed: cfg.seed, difficulty: cfg.difficulty == null ? 0.45 : cfg.difficulty, pattern: cfg.pattern, seconds: 6 } });
  const C = s.ctx.C, segs = [];
  const h0 = s.ctx.hit, m0 = s.ctx.miss;
  s.ctx.hit = function (x) { segs.push(+x.toFixed(3)); return h0.apply(this, arguments); };
  s.ctx.miss = function () { segs.push(0); return m0.apply(this, arguments); };
  const rec = recorder();
  const ph = [R() * 6.28, R() * 6.28, R() * 6.28], f1 = 0.9 + R() * 0.8, f2 = 2.8 + R() * 1.6;
  const wob = (t) => cfg.A * (0.6 * Math.sin(6.283 * f1 * t + ph[0]) + 0.4 * Math.sin(6.283 * f2 * t + ph[1]));
  let t = 0, u = 0, litKey = "", lit = null, hold = 0, phase = "wait", hand = null, travel = null, cut = null;
  const beads = [];
  let done = false, frames = 0, first = null;
  while (!done && frames < 60 * 30) {
    frames++;
    rec.reset(); s.game.draw(rec.g, W, H);
    if (frames === 1) first = { paths: rec.paths.slice(), texts: rec.texts.slice() };
    const lp = rec.paths.find((q) => q.style === C.gold && q.pts.length > 2);
    const P = lp ? lp.pts : null;
    if (P) {
      const key = P[0][0].toFixed(1) + "," + P[0][1].toFixed(1);
      if (key !== litKey) {
        litKey = key; lit = P; hold = 0; u = 0;
        if (hand && Math.hypot(hand[0] - P[0][0], hand[1] - P[0][1]) > 20) travel = [P[0][0], P[0][1]];
      }
      if (cfg.kind === "keys") {
        // The arrow the strip shows: the dim notch beside the lit segment, read by its angle.
        const notch = rec.fills.find((f) => f.style === C.goldDim && f.rot != null);
        if (t >= cfg.react && frames % 12 === 0 && notch) {
          const a = Math.round(notch.rot / (Math.PI / 2));
          s.press(a === 0 ? "ArrowRight" : a === 1 ? "ArrowDown" : a === -1 ? "ArrowUp" : "ArrowLeft");
        }
      } else if (phase === "wait") {
        if (t >= cfg.react) {
          u = cfg.startOff || 0;
          const a = along(P, u); hand = [a.x, a.y];
          s.pointer("down", hand[0], hand[1]);
          if (cfg.mode === "click") s.pointer("up", hand[0], hand[1]);
          phase = "trace";
        }
      } else if (cfg.kind === "bead") {
        const b = rec.paths.find((q) => q.style === C.candle && q.pts.length === 1);
        if (b) beads.push([t, b.pts[0][0], b.pts[0][1]]);
        const want = beads.filter((h) => h[0] <= t - cfg.lag).pop();
        if (want) { hand = [want[1], want[2]]; s.pointer("move", hand[0], hand[1]); }
      } else if (cfg.kind === "cut") {
        const gp = [].concat(...rec.paths.filter((q) => q.pts.length > 2 && (q.style === C.gold || q.style === C.goldDim || q.style === C.ink) && q.w < 4).map((q) => q.pts));
        const xs = gp.map((p) => p[0]), ys = gp.map((p) => p[1]);
        const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2, e = P[P.length - 1];
        if (!cut || cut.key !== key) cut = { key, pts: [[hand[0], hand[1]], [P[0][0], P[0][1]], [cx, cy], [e[0], e[1]]], u: 0 };
        cut.u += cfg.v * DT;
        const a = along(cut.pts, Math.min(cut.u, polyLen(cut.pts))); hand = [a.x, a.y];
        s.pointer("move", hand[0], hand[1]);
      } else if (travel) {
        const d = Math.hypot(travel[0] - hand[0], travel[1] - hand[1]), stp = cfg.v * DT;
        if (d <= stp) { hand = travel; travel = null; }
        else hand = [hand[0] + (travel[0] - hand[0]) * stp / d, hand[1] + (travel[1] - hand[1]) * stp / d];
        s.pointer("move", hand[0], hand[1]);
      } else {
        const L = polyLen(lit), v = cfg.v * (1 + 0.2 * Math.sin(6.283 * 0.7 * t + ph[2]));
        if (u < L) u = Math.min(L, u + v * DT);
        else { hold += DT; if (hold > 0.35) { hold = 0; u = 0; travel = [lit[0][0], lit[0][1]]; } }
        const a = along(lit, u), w = wob(t);
        hand = [a.x - a.ty * w + (R() - 0.5) * 2, a.y + a.tx * w + (R() - 0.5) * 2];
        s.pointer("move", hand[0], hand[1]);
      }
    }
    done = s.step(DT); t += DT;
  }
  const r = s.result();
  return { score: r.score, hits: r.hits, misses: r.misses, segs, n: cfg.pattern === "fold" ? 6 : 8,
    duration: s.game.duration, t, first: cfg.wantFirst ? first : undefined };
}
process.stdout.write(JSON.stringify(plays.map(play)));
"""


@pytest.fixture(scope="module")
def drive(tmp_path_factory):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    script = tmp_path_factory.mktemp("mix") / "drive.js"
    script.write_text(_DRIVER, encoding="utf-8")
    files = [str(JS / "bench-games" / f"{m}.js") for m in METHODS] + [str(JS / "table" / "33-bench-games.js")]

    def run(plays: list[dict]) -> list[dict]:
        done = subprocess.run([node, str(script), json.dumps(files), json.dumps(plays)],
                              capture_output=True, text=True, timeout=240)
        assert done.returncode == 0, done.stderr[:2000]
        return json.loads(done.stdout)
    return run


SEEDS = (1, 2, 3)
CAREFUL = {"kind": "trace", "v": 300, "A": 4, "react": 0.5, "startOff": 3}


def _each(pattern: str, steady: bool, **kw) -> list[dict]:
    return [dict(CAREFUL, pattern=pattern, steady=steady, seed=s, **kw) for s in SEEDS]


@pytest.mark.parametrize("steady", [False, True], ids=["normal", "steady"])
@pytest.mark.parametrize("pattern", PATTERNS)
def test_a_careful_human_trace_makes_every_segment(drive, pattern, steady):
    """A hand on the gold line at 150-600 px/s with 4px of wobble, by drag and by click, makes
    every segment of every pattern and scores 0.8 or better. Before 2026-10-06 the same hand
    already made them all: the owner's "impossible" was the strip, not this. Held so that a
    legibility change cannot quietly break the trace."""
    plays = (_each(pattern, steady) + _each(pattern, steady, v=150, A=3)
             + _each(pattern, steady, v=600, A=5) + _each(pattern, steady, mode="click"))
    for cfg, r in zip(plays, drive(plays)):
        assert r["hits"] == r["n"] and 0 not in r["segs"], (cfg, r["segs"])
        assert r["score"] >= 0.8, (cfg, r["score"], r["segs"])


@pytest.mark.parametrize("pattern", PATTERNS)
def test_the_first_segment_waits_for_the_paddle(drive, pattern):
    """Measured: a player who took 1.2s to find the start lost the first segment every time
    (scores capped at 0.83-0.88), because its 0.84s clock ran from the strip's first frame,
    while it was still sliding up. In the live bench, once the first-time card no longer shows,
    the first segment was lost in every run. The clock now starts at the first take, or after
    1.2s, and the game is 1.2s longer."""
    plays = _each(pattern, False, react=1.2, startOff=12)
    for cfg, r in zip(plays, drive(plays)):
        assert r["segs"][:1] and r["segs"][0] > 0, (cfg, r["segs"])
        assert r["hits"] == r["n"], (cfg, r["segs"])


@pytest.mark.parametrize("pattern", ["eight", "fold"])
def test_joining_the_segment_a_little_way_along_counts(drive, pattern):
    """Measured: a first touch 25px along the lit segment never counted on the eight or the
    fold (0.75-0.88): `reach` crept forward only from the segment's first four points. osu!
    lazer credits a slider joined late while the cursor is inside its follow range (ppy/osu
    discussion #25129); here the first touch may land anywhere in the segment's first 40%."""
    plays = _each(pattern, False, startOff=25)
    for cfg, r in zip(plays, drive(plays)):
        assert r["hits"] == r["n"] and r["score"] >= 0.8, (cfg, r["segs"])


@pytest.mark.parametrize("pattern", PATTERNS)
def test_following_the_bead_a_reaction_behind_still_makes_the_segment(drive, pattern):
    """Measured: following the bead 0.2s behind scored 0.38 on the fold and 0.54 on the eight,
    because the bead reached the segment's end exactly when the base set. A bead reads as
    "follow me" (it is how osu! draws a slider), so it now arrives at 70% of the slot."""
    plays = [dict(pattern=pattern, steady=False, seed=s, kind="bead", lag=0.2, A=0, react=0.5)
             for s in SEEDS]
    for cfg, r in zip(plays, drive(plays)):
        assert r["hits"] == r["n"], (cfg, r["segs"])


@pytest.mark.parametrize("pattern", PATTERNS)
def test_a_wobbly_trace_scores_lower_than_a_careful_one_but_passes(drive, pattern):
    """Before, a 10px wobble scored 0.95-1.00, the same as a careful hand: the first third of
    the tolerance was free and a made segment never earned under 0.5. Now the free part is a
    sixth and closeness falls off over half the tolerance: a 9px wobble makes every segment,
    scores 0.6 or better, and scores below the careful hand."""
    careful = drive(_each(pattern, False))
    wobbly = drive(_each(pattern, False, A=9))
    for c, w in zip(careful, wobbly):
        assert w["hits"] >= w["n"] - 1 and w["score"] >= 0.6, w["segs"]
    assert sum(w["score"] for w in wobbly) < sum(c["score"] for c in careful) - 0.15, (careful, wobbly)


@pytest.mark.parametrize("steady", [False, True], ids=["normal", "steady"])
@pytest.mark.parametrize("pattern", PATTERNS)
def test_cutting_across_the_pattern_does_not_count(drive, pattern, steady):
    """Measured: a pointer going straight from each segment's start through the circle's
    centre to its end made EVERY segment (score 0.66; in Steady 0.72 on the circle, 0.70 on
    the eight, 0.84 on the fold), because the follow tolerance (17px, Steady 27px) is most of
    a circle segment's 31px. A point now counts only when passed within 0.65 of the
    tolerance, and a trace that strays from the line on the way is refused. Measured after:
    0.04 / 0.19 / 0.29, Steady 0.00 / 0.36 / 0.11 (the V through the eight's centre runs
    along its crossing strokes, and the fold's middle row is on the centre)."""
    plays = [dict(pattern=pattern, steady=steady, seed=s, kind="cut", v=300, A=0, react=0.5)
             for s in SEEDS]
    careful = drive(_each(pattern, steady))
    for cfg, r, c in zip(plays, drive(plays), careful):
        assert r["score"] <= 0.45 and r["score"] < c["score"] / 2, (cfg, r["segs"])
        assert r["hits"] <= r["n"] // 2, (cfg, r["segs"])


@pytest.mark.parametrize("pattern", PATTERNS)
def test_steady_mode_never_times_out_a_slow_hand(drive, pattern):
    """Steady mode waits for the player (UI plan §9): a hand that sets off after 2s and moves
    at 80px/s, a third of a careful hand's pace, still makes every segment and no segment is
    scored as set."""
    plays = _each(pattern, True, react=2.0, v=80, A=3)
    for cfg, r in zip(plays, drive(plays)):
        assert r["hits"] == r["n"] and 0 not in r["segs"], (cfg, r["segs"])
        assert r["t"] < r["duration"], (cfg, r["t"], r["duration"])


@pytest.mark.parametrize("pattern", PATTERNS)
def test_the_keyboard_route_still_makes_every_segment(drive, pattern):
    """The arrow shown on the lit segment makes it, one press per segment (UI plan §9): the
    accessible route the trace changes must not touch."""
    plays = [dict(pattern=pattern, steady=st, seed=1, kind="keys", react=0.3) for st in (False, True)]
    for cfg, r in zip(plays, drive(plays)):
        assert r["hits"] == r["n"] and r["score"] >= 0.99, (cfg, r["segs"])


def test_the_texture_gauge_is_a_framed_meter_not_a_line(drive):
    """The owner tried to trace the texture gauge: a wavy stroke of some thirty points across
    120px of the strip, the biggest line on it, drawn beside a guide of thin dashes. It is now
    a framed fill bar named "Texture" with "lumpy" and "glossy" at its ends. Checked on what is
    drawn: right of the figure there is no stroked path of more than five points, and the three
    words are there."""
    plays = [dict(CAREFUL, pattern=p, steady=False, seed=1, wantFirst=True) for p in PATTERNS]
    for cfg, r in zip(plays, drive(plays)):
        first = r["first"]
        words = [t[0] for t in first["texts"]]
        for w in ("Texture", "lumpy", "glossy"):
            assert w in words, (cfg["pattern"], words)
        guide_right = max(p[0] for path in first["paths"] if len(path["pts"]) > 2 and path["w"] < 4
                          for p in path["pts"] if p[0] < 300)
        for path in first["paths"]:
            if all(p[0] > guide_right + 20 for p in path["pts"]) and path["pts"]:
                assert len(path["pts"]) <= 5, (cfg["pattern"], path)


def test_the_strip_names_the_gold_line_and_marks_the_start(drive):
    """"Drag along the line" named no line, and the strip had two. The words now name the
    gold line, the first-time card says to trace it from its diamond, and until the paddle is
    first taken a "Start" label sits beside the lit segment's diamond."""
    code = (JS / "bench-games" / "mix.js").read_text(encoding="utf-8")
    assert 'first: "Trace the gold line from its diamond, before the base sets."' in code
    assert '"Drag along the gold line, or the arrows"' in code
    assert '"Click, then follow the gold line. Or the arrows"' in code
    plays = [dict(CAREFUL, pattern=p, steady=False, seed=1, wantFirst=True) for p in PATTERNS]
    for r in drive(plays):
        assert "Start" in [t[0] for t in r["first"]["texts"]]
