// Bench minigame: Mix, fold the pattern (revamp plan §9.3, UI plan §9).
//
// The stroke guide (a circle, a figure-eight or a fold, `tuning.pattern` or chosen from the
// seed) is drawn as a brass line cut into segments. Trace the lit segment before the base
// sets; the texture line on the right goes from lumpy to glossy as the segments are made.
//
// Input:
//   - Mouse or touch: drag along the line, OR click once to take up the paddle, trace by
//     moving, and click again to put it down. The click form exists so the mouse never has
//     to be held for six seconds (Potion Craft's stirring was the hand-fatigue complaint,
//     devlog #14).
//   - Keyboard: the arrow shown on the lit segment, one press per segment.
//   - Steady mode: the guide waits for you instead of moving on (UI plan §9). The frame
//     drops releases, so the paddle is click-to-take, click-to-put-down.
//
// Scoring: a segment traced earns 0.3..1 by how close the trace stayed to it (mean distance
// against the tolerance); a segment the guide moved on from earns 0. A trace that reached the
// end but wandered too far on the way (cutting across, scribbling) is not a trace: it is
// refused with a miss and the segment stays lit to be made again. A wrong arrow is a miss
// and takes 0.3 off that segment, down to 0.4. The score is the sum over all segments.
//
// What changed on 2026-10-06, and why (owner: "the trace for mix in herbalism is impossible",
// then "i thought the squiggly line that ran across the bar was what i was supposed to
// trace"). The defect was legibility first: the texture gauge was a 120px wavy stroke, the
// largest line on the strip, beside a guide of thin dashes, so it read as the path. A
// human-model bot tracing the RIGHT line completed 100% of segments at 150-600 px/s in node
// and in the live bench (0.996), so the trace itself was never impossible; but measured on
// the same bot it was unfair at the edges and leaked at the other:
//   - a player who took 1.2s to find the start lost the first segment every time (score
//     capped at 0.83-0.88), because the first segment's clock ran from the first frame;
//   - joining the lit segment 25px along never counted on the eight or the fold (0.75-0.88);
//   - following the bead with a 0.2s lag scored 0.38-0.54: the bead reached the segment's
//     end exactly when the base set, so it led a follower into the timeout;
//   - cutting across the circle through its centre made EVERY segment (0.66, Steady 0.72-
//     0.84), and scribbling in Steady made 91-94% of them (0.58-0.63): any completed trace
//     earned at least 0.5, however far it strayed.
// The fixes follow what rhythm games settled on: osu! scores a slider by a follow circle
// larger than the ball (osu! wiki, Hit object/Slider), and in December 2023 lazer began
// crediting a slider joined late as long as the cursor is within that range (ppy/osu
// discussion #25129, PRs #25748 and #25776). Here: the first segment waits for the paddle
// (LEAD), a trace may join anywhere in the lit segment's first part (JOIN), the bead runs
// ahead of the deadline (BEAD), and closeness has a floor below which a "trace" is refused
// (PASS). The texture gauge is a framed, labelled fill bar (the revamp plan's own word is
// "meter"), never a line: a decoration that looks like the input is a false affordance
// (Gaver, "Technology Affordances", CHI 1991).
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};

  // Each pattern is a polyline in a 0..1 box and the box's aspect (width / height).
  var PATTERNS = {
    circle: { aspect: 1, segs: 8, pts: function () {
      var p = [];
      for (var i = 0; i <= 48; i++) {
        var a = -Math.PI / 2 + i / 48 * Math.PI * 2;
        p.push([0.5 + 0.42 * Math.cos(a), 0.5 + 0.42 * Math.sin(a)]);
      }
      return p;
    } },
    eight: { aspect: 2.1, segs: 8, pts: function () {
      var p = [];
      for (var i = 0; i <= 64; i++) {
        var a = i / 64 * Math.PI * 2;
        p.push([0.5 + 0.44 * Math.sin(a), 0.5 + 0.8 * Math.sin(a) * Math.cos(a)]);
      }
      return p;
    } },
    fold: { aspect: 2.1, segs: 6, pts: function () {
      // Three passes across with a turn at each end: folding a base over on itself.
      var p = [], rows = [0.18, 0.5, 0.82], i, a;
      for (var r = 0; r < 3; r++) {
        var ltr = r % 2 === 0, y = rows[r];
        for (i = 0; i <= 10; i++) p.push([ltr ? 0.1 + 0.8 * i / 10 : 0.9 - 0.8 * i / 10, y]);
        if (r < 2) {
          var cx = ltr ? 0.9 : 0.1, cy = (rows[r] + rows[r + 1]) / 2, rad = (rows[r + 1] - rows[r]) / 2;
          for (i = 1; i < 8; i++) {
            a = -Math.PI / 2 + i / 8 * Math.PI;
            // x is squeezed by the box's aspect so the turn reads round.
            p.push([cx + (ltr ? 1 : -1) * rad * 0.35 * Math.cos(a), cy + rad * Math.sin(a)]);
          }
        }
      }
      return p;
    } }
  };
  var ORDER = ["circle", "eight", "fold"];
  var ARROWS = ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"];

  // Cut a polyline into `n` runs of equal length, each resampled every `step` units.
  function segment(pts, n, step) {
    var lens = [0], i;
    for (i = 1; i < pts.length; i++) {
      lens.push(lens[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    }
    var total = lens[lens.length - 1];
    function at(d) {
      var j = 1;
      while (j < lens.length - 1 && lens[j] < d) j++;
      var f = (d - lens[j - 1]) / Math.max(1e-9, lens[j] - lens[j - 1]);
      return [pts[j - 1][0] + (pts[j][0] - pts[j - 1][0]) * f, pts[j - 1][1] + (pts[j][1] - pts[j - 1][1]) * f];
    }
    var out = [];
    for (var s = 0; s < n; s++) {
      var a = total * s / n, b = total * (s + 1) / n, run = [];
      var m = Math.max(2, Math.ceil((b - a) / step));
      for (i = 0; i <= m; i++) run.push(at(a + (b - a) * i / m));
      out.push(run);
    }
    return out;
  }

  // The first segment's clock waits for the paddle (or the first arrow), up to this long: a
  // player has to find the diamond before they can trace from it (measured: 1.2s to start
  // lost the first segment every time). The game's length grows by the same.
  var LEAD = 1.2;
  // The bead reaches the lit segment's end at this share of its slot, so a player following
  // it a reaction behind still makes the segment (0.2s behind scored 0.38 on the fold).
  var BEAD = 0.7;
  // A trace may join the lit segment anywhere in this first share of it, as osu! lazer
  // credits a slider joined late within its follow range.
  var JOIN = 0.4;
  // Closeness below this is not a trace: the segment is refused and stays lit.
  var PASS = 0.3;
  // The cover radius as a share of the tolerance, and the share of a segment's points that
  // must be covered (see `follow`).
  var COVER = 0.65, COVER_SHARE = 0.8;
  // A trace that walked more than this many times the segment's length (plus twice the
  // tolerance) to make it was scribbling, not following: honest traces in the bot measured
  // 1.46 at most (a 10px wobble), scribbles from 2 to several hundred.
  var WANDER = 3;
  // Room the texture gauge takes at the meter's right: the bar and its words.
  var GAUGE_ROOM = 100;

  defs.mix = {
    id: "mix",
    name: "Mix",
    first: "Trace the gold line from its diamond, before the base sets.",
    hint: function (steady) {
      return steady ? "Click, then follow the gold line. Or the arrows" : "Drag along the gold line, or the arrows";
    },
    KEYS: ARROWS.slice(),
    // Nothing needs holding: a drag works, and so does click, move, click.
    HOLDS: [],
    HOLDS_STEADY: [],
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var name = PATTERNS[ctx.tuning.pattern] ? ctx.tuning.pattern : ORDER[Math.floor(ctx.rng() * ORDER.length)];
      var pat = PATTERNS[name];
      var guideN = pat.pts();                     // normalised, for the stage
      var segsN = segment(guideN, pat.segs, 0.012);
      var n = segsN.length;
      var keyOf = segsN.map(function (run) {
        var dx = run[run.length - 1][0] - run[0][0], dy = run[run.length - 1][1] - run[0][1];
        if (Math.abs(dx) >= Math.abs(dy)) return dx >= 0 ? "ArrowRight" : "ArrowLeft";
        return dy >= 0 ? "ArrowDown" : "ArrowUp";
      });
      var slot = ctx.seconds * 1.1 / n / ctx.baseSpeed;   // how long the guide waits per segment
      var duration = LEAD + (ctx.steady ? ctx.seconds * 2.2 / ctx.baseSpeed : ctx.seconds * 1.1 / ctx.baseSpeed + 0.3);
      var tolPx = 15 * ctx.win;
      // A point of the lit segment counts as traced when the pointer passes this close to it.
      // Narrower than the tolerance: with the tolerance itself (17px, Steady 27px, on circle
      // segments 31px long) touching a segment anywhere near its middle "traced" all of it,
      // and cutting across the circle through its centre made every segment.
      var coverPx = COVER * tolPx;
      // Closeness: the first sixth of the tolerance is free (a hand on the line wobbles a few
      // pixels), and it falls to nothing over the next half of it. Before 2026-10-06 the free
      // third and a 0.5 floor scored a 10px wobble 0.95-1.00, the same as a careful trace.
      var slack = tolPx / 6, span = tolPx / 2;
      var q = [], wrong = [], devSum = 0, devN = 0;
      for (var i = 0; i < n; i++) { q.push(null); wrong.push(0); }
      var seg = 0, segStart = 0, joined = false, t = 0, started = false, taken = false;
      var pen = false, downAt = null, moved = 0, last = null;
      var trace = [], traceN = [];
      var box = { x: 14, y: 12, w: 96, h: 96, W: 0 };
      var segsPx = [], allPx = [], segLen = [], walked = 0, covered = [], coverN = 0;

      function layout(W, H) {
        if (box.W === W && box.H === H) return;
        box.W = W; box.H = H;
        box.h = H - 24; box.y = 12;
        box.w = Math.max(60, Math.min(box.h * pat.aspect, W - box.x - GAUGE_ROOM));
        segsPx = segsN.map(function (run) { return run.map(function (p) { return [box.x + p[0] * box.w, box.y + p[1] * box.h]; }); });
        allPx = [].concat.apply([], segsPx);
        segLen = segsPx.map(function (run) {
          var L = 0;
          for (var j = 1; j < run.length; j++) L += Math.hypot(run[j][0] - run[j - 1][0], run[j][1] - run[j - 1][1]);
          return L;
        });
      }
      function norm(x, y) { return [(x - box.x) / box.w, (y - box.y) / box.h]; }

      // The first segment's clock starts on the first take (or arrow), or after LEAD.
      function begin() { if (!started) { started = true; segStart = t; } }

      function restart() { joined = false; devSum = 0; devN = 0; walked = 0; covered = []; coverN = 0; }
      function close(x) {
        if (seg >= n || q[seg] !== null) return;
        q[seg] = x;
        if (x > 0) ctx.hit(x, segsPx[seg] ? segsPx[seg][segsPx[seg].length - 1][0] : null,
          segsPx[seg] ? segsPx[seg][segsPx[seg].length - 1][1] : null, "steam");
        else ctx.miss();
        seg++; segStart = t; restart();
      }

      // Follow the pointer along the lit segment. The trace joins it with a first touch
      // within the tolerance of its first JOIN share; from then on every resampled point the
      // pointer passes within the COVER radius of is covered, and the segment is made once
      // COVER_SHARE of its points are and the pointer is at its end. Covering points, not
      // creeping a window forward, is what lets a hand that wobbled off the line for a moment
      // pick up again where it is: the window form stalled for good once the hand got more
      // than four points ahead. A fast flick is interpolated in 4px steps. Only the trace
      // from the first touch on is measured: the way the paddle came to the line is not part
      // of the stroke.
      function follow(x, y, step) {
        if (seg >= n || !segsPx.length) return;
        var run = segsPx[seg], j, dj;
        if (!joined) {
          var top = Math.max(4, Math.floor(JOIN * (run.length - 1)));
          for (j = 0; j <= top && !joined; j++) {
            if (Math.hypot(run[j][0] - x, run[j][1] - y) <= tolPx) joined = true;
          }
          if (!joined) return;
        }
        // Closeness is to the LINE, the whole guide, not to the lit segment alone: the lit
        // segment changes the moment the last one is made, while the hand is still a few
        // pixels short of its start, and measured against the lit run alone those pixels
        // scored a careful 600px/s trace of the circle 0.78 (Steady 0.58).
        var dl = Infinity;
        for (j = 0; j < allPx.length; j++) dl = Math.min(dl, Math.hypot(allPx[j][0] - x, allPx[j][1] - y));
        devSum += Math.min(dl, tolPx * 2); devN++;
        walked += step || 0;
        for (j = 0; j < run.length; j++) {
          dj = Math.hypot(run[j][0] - x, run[j][1] - y);
          if (!covered[j] && dj <= coverPx) { covered[j] = 1; coverN++; }
        }
        var end = run[run.length - 1];
        if (coverN >= COVER_SHARE * run.length && Math.hypot(end[0] - x, end[1] - y) <= tolPx) {
          var mean = devN ? devSum / devN : 0;
          var near = 1 - Math.max(0, mean - slack) / span;
          if (near < PASS || walked > WANDER * segLen[seg] + 2 * tolPx) {
            // Reached the end by wandering, not by following it (too far from the line on
            // the way, or a path several times the segment's length): refused, and said so.
            ctx.miss();
            restart();
            return;
          }
          close(k.clamp(near, PASS, 1) * Math.max(0.4, 1 - 0.3 * wrong[seg]));
        }
      }

      function moveTo(x, y) {
        if (last) {
          var dist = Math.hypot(x - last[0], y - last[1]), steps = Math.max(1, Math.ceil(dist / 4));
          moved += dist;
          for (var s = 1; s <= steps; s++) {
            var px = last[0] + (x - last[0]) * s / steps, py = last[1] + (y - last[1]) * s / steps;
            follow(px, py, dist / steps);
          }
        } else {
          follow(x, y, 0);
        }
        last = [x, y];
        trace.push([x, y]); traceN.push(norm(x, y));
        if (trace.length > 80) { trace.shift(); traceN.shift(); }
      }

      // The nearest point of the lit segment to (x, y), and how far it is.
      function nearest(x, y) {
        var run = segsPx[seg], best = null, bd = Infinity;
        for (var j = 0; j < run.length; j++) {
          var dd = Math.hypot(run[j][0] - x, run[j][1] - y);
          if (dd < bd) { bd = dd; best = run[j]; }
        }
        return { p: best, d: bd };
      }

      function stroke(g, run, upto) {
        g.beginPath();
        for (var j = 0; j < Math.min(run.length, upto); j++) { if (j) g.lineTo(run[j][0], run[j][1]); else g.moveTo(run[j][0], run[j][1]); }
        g.stroke();
      }

      // The texture gauge: a framed bar that fills from "lumpy" at its foot to "glossy" at
      // its head, with its name beside it. A fill in a frame, never a stroke across the strip:
      // the wavy line it replaced was what the owner tried to trace. Left out when the meter
      // is too narrow for it; the band word and the bowl on the stage say the same.
      function gauge(g, W, gloss) {
        var bw = 10, x1 = W - 16, x0 = x1 - bw, top = box.y + 10, bot = box.y + box.h - 10;
        if (x0 - (box.x + box.w) < 64 || bot - top < 40) return;
        var fill = (bot - top) * k.clamp(gloss, 0, 1);
        if (fill >= 2) k.barBand(g, x0, bot - fill, bw, fill, C.gold, { gap: 4 });
        g.save();
        g.strokeStyle = C.goldDim; g.lineWidth = 1;
        g.strokeRect(x0 - 0.5, top - 0.5, bw + 1, bot - top + 1);
        g.restore();
        k.text(g, "glossy", x0 - 7, top + 5, C, { size: 12, align: "right" });
        k.text(g, "Texture", x0 - 7, (top + bot) / 2, C, { size: 13, align: "right", colour: C.ink });
        k.text(g, "lumpy", x0 - 7, bot - 5, C, { size: 12, align: "right" });
      }

      // "Start" beside the lit segment's diamond until the paddle is first taken: placed on
      // whichever side of the diamond is furthest from the guide, so it never sits on a line.
      function startLabel(g, sx, sy) {
        var cands = [[0, -15, "center"], [0, 15, "center"], [-10, 0, "right"], [10, 0, "left"]];
        var best = null, bd = -1;
        cands.forEach(function (c) {
          var cx = sx + c[0] + (c[2] === "right" ? -16 : c[2] === "left" ? 16 : 0), cy = sy + c[1];
          if (cy < 6 || cx < 18) return;
          var dmin = Infinity;
          segsPx.forEach(function (run) {
            for (var j = 0; j < run.length; j += 2) dmin = Math.min(dmin, Math.hypot(run[j][0] - cx, run[j][1] - cy));
          });
          if (dmin > bd) { bd = dmin; best = c; }
        });
        if (best) k.text(g, "Start", sx + best[0], sy + best[1], C, { size: 12, align: best[2], colour: C.gold });
      }

      return {
        duration: duration,
        tick: function (dt, now) {
          t = now;
          if (!started && t >= LEAD) begin();
          // The base sets: outside Steady mode a segment not made in its slot is lost and
          // the guide moves on.
          if (started && !ctx.steady && seg < n && t - segStart > slot) close(0);
        },
        down: function (inp) {
          if (inp.src === "key") {
            if (seg >= n) return true;
            begin(); taken = true;
            if (inp.key === keyOf[seg]) {
              // The keyboard lays the trace along the guide, so the stage sees a stroke too.
              segsN[seg].forEach(function (p) { traceN.push(p); if (traceN.length > 80) traceN.shift(); });
              trace = []; last = null;
              close(Math.max(0.4, 1 - 0.3 * wrong[seg]));
            } else {
              wrong[seg]++;
              ctx.miss();
            }
            return true;
          }
          if (!inp.inside) return true;
          if (pen) { pen = false; last = null; return true; }
          begin(); taken = true;
          pen = true; downAt = [inp.x, inp.y]; moved = 0; last = null;
          moveTo(inp.x, inp.y);
          return true;
        },
        // Only outside Steady mode: a drag that has travelled puts the paddle down on release;
        // a click (no travel) leaves it up, for the click, move, click form.
        up: function (inp) {
          if (inp.src === "pointer" && pen && moved > 12) { pen = false; last = null; }
          return true;
        },
        move: function (inp) {
          if (pen) moveTo(inp.x, inp.y);
        },
        state: function () {
          var made = 0;
          q.forEach(function (x) { if (x) made += x; });
          return { guide: guideN, trace: traceN.slice(), gloss: made / n };
        },
        score: function () {
          var s = 0;
          q.forEach(function (x) { if (x) s += x; });
          return s / n;
        },
        done: function () { return seg >= n; },
        draw: function (g, W, H) {
          layout(W, H);
          var s, run;
          // Segments: made ones in ink, those to come dashed and dim, and the lit one in gold
          // with a soft halo, drawn last so nothing crosses over it.
          for (s = 0; s < n; s++) {
            if (s === seg) continue;
            run = segsPx[s];
            g.save();
            if (s < seg) {
              g.strokeStyle = q[s] > 0 ? C.ink : C.ash; g.lineWidth = q[s] > 0 ? 2 : 1;
              if (!(q[s] > 0)) g.setLineDash([2, 4]);
            } else {
              g.strokeStyle = C.goldDim; g.lineWidth = 1.2; g.setLineDash([4, 4]);
            }
            stroke(g, run, run.length);
            g.restore();
          }
          if (seg < n) {
            run = segsPx[seg];
            g.save();
            g.lineCap = "round"; g.lineJoin = "round";
            g.globalAlpha = 0.22; g.strokeStyle = C.gold; g.lineWidth = 10;
            stroke(g, run, run.length);
            g.globalAlpha = 1; g.lineWidth = 3.5;
            stroke(g, run, run.length);
            // What the trace has made of it so far, in ink: the line fills as you follow it.
            if (coverN) {
              g.strokeStyle = C.ink; g.lineWidth = 2; g.beginPath();
              for (var j = 1; j < run.length; j++) {
                if (covered[j] && covered[j - 1]) { g.moveTo(run[j - 1][0], run[j - 1][1]); g.lineTo(run[j][0], run[j][1]); }
              }
              g.stroke();
            }
            g.restore();
            // The start of the lit segment (a diamond in a ring), the way it runs (an arrow
            // past its end), and the arrow key that makes it (the notch beside it).
            var a0 = run[0], e0 = run[run.length - 2], e1 = run[run.length - 1];
            var ring = 7 + (ctx.reduced || taken ? 0 : 1.5 * Math.sin(t * 5));
            k.diamond(g, a0[0], a0[1], 4.5, C.gold, null);
            g.save(); g.strokeStyle = C.gold; g.lineWidth = 1.2;
            g.beginPath(); g.arc(a0[0], a0[1], ring, 0, Math.PI * 2); g.stroke(); g.restore();
            var ea = Math.atan2(e1[1] - e0[1], e1[0] - e0[0]);
            k.notch(g, e1[0] + Math.cos(ea) * 9, e1[1] + Math.sin(ea) * 9, ea, 6, C.gold);
            var mid = run[Math.floor(run.length / 2)], key = keyOf[seg];
            var ang = { ArrowRight: 0, ArrowDown: Math.PI / 2, ArrowLeft: Math.PI, ArrowUp: -Math.PI / 2 }[key];
            var ox = Math.cos(ang + Math.PI / 2) * 12, oy = Math.sin(ang + Math.PI / 2) * 12;
            k.notch(g, mid[0] + ox + Math.cos(ang) * 4, mid[1] + oy + Math.sin(ang) * 4, ang, 6, C.goldDim);
            if (!taken) startLabel(g, a0[0], a0[1]);
            // Outside Steady mode a bead runs down the lit segment ahead of the deadline: the
            // base setting. It waits at the start until the clock does.
            if (!ctx.steady) {
              var f = started ? k.clamp((t - segStart) / (slot * BEAD), 0, 1) : 0;
              var p = run[Math.min(run.length - 1, Math.floor(f * (run.length - 1)))];
              g.beginPath(); g.arc(p[0], p[1], 3, 0, Math.PI * 2); g.strokeStyle = C.candle; g.lineWidth = 1.4; g.stroke();
            }
          }
          // The player's trace, in ink.
          if (trace.length > 1) {
            g.save(); g.strokeStyle = C.ink; g.globalAlpha = 0.6; g.lineWidth = 1.2;
            g.beginPath();
            trace.forEach(function (p, i) { if (i) g.lineTo(p[0], p[1]); else g.moveTo(p[0], p[1]); });
            g.stroke(); g.restore();
          }
          gauge(g, W, this.score());
          // The paddle: on the line (within the tolerance) it sits on the line, so "I am on
          // it" shows; off the line it is where the pointer is.
          if (ctx.pointer.inside) {
            var at = pen && seg < n ? nearest(ctx.pointer.x, ctx.pointer.y) : null;
            if (at && at.d <= tolPx) k.reticle(g, at.p[0], at.p[1], C, true);
            else k.reticle(g, ctx.pointer.x, ctx.pointer.y, C, pen);
          }
        }
      };
    }
  };
})();
