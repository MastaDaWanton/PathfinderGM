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
// Scoring: a segment traced earns 0.5..1 by how close the trace stayed to it (mean distance
// against the tolerance); a segment the guide moved on from earns 0. A wrong arrow is a miss
// and takes 0.3 off that segment, down to 0.4. The score is the sum over all segments.
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

  defs.mix = {
    id: "mix",
    name: "Mix",
    first: "Trace the brass line before the base sets.",
    hint: function (steady) {
      return steady ? "Click, then follow the line. Or the arrows" : "Drag along the line, or the arrows";
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
      var duration = ctx.steady ? ctx.seconds * 2.2 / ctx.baseSpeed : ctx.seconds * 1.1 / ctx.baseSpeed + 0.3;
      var tolPx = 15 * ctx.win;
      var q = [], wrong = [], devSum = 0, devN = 0;
      for (var i = 0; i < n; i++) { q.push(null); wrong.push(0); }
      var seg = 0, segStart = 0, reach = 0, t = 0;
      var pen = false, downAt = null, moved = 0, last = null;
      var trace = [], traceN = [];
      var box = { x: 14, y: 12, w: 96, h: 96, W: 0 };
      var segsPx = [];

      function layout(W, H) {
        if (box.W === W && box.H === H) return;
        box.W = W; box.H = H;
        box.h = H - 24; box.y = 12;
        box.w = Math.max(60, Math.min(box.h * pat.aspect, W - 150));
        segsPx = segsN.map(function (run) { return run.map(function (p) { return [box.x + p[0] * box.w, box.y + p[1] * box.h]; }); });
      }
      function norm(x, y) { return [(x - box.x) / box.w, (y - box.y) / box.h]; }

      function close(x) {
        if (seg >= n || q[seg] !== null) return;
        q[seg] = x;
        if (x > 0) ctx.hit(x, segsPx[seg] ? segsPx[seg][segsPx[seg].length - 1][0] : null,
          segsPx[seg] ? segsPx[seg][segsPx[seg].length - 1][1] : null, "steam");
        else ctx.miss();
        seg++; segStart = t; reach = 0; devSum = 0; devN = 0;
      }

      // Follow the pointer along the lit segment: `reach` creeps forward over consecutive
      // resampled points the pointer comes within tolerance of, so cutting across the
      // pattern does not count, and a fast flick is interpolated in 4px steps.
      function follow(x, y) {
        if (seg >= n || !segsPx.length) return;
        var run = segsPx[seg], d = Infinity, j;
        for (j = 0; j < run.length; j++) d = Math.min(d, Math.hypot(run[j][0] - x, run[j][1] - y));
        devSum += Math.min(d, tolPx * 2); devN++;
        for (j = reach; j < Math.min(run.length, reach + 4); j++) {
          if (Math.hypot(run[j][0] - x, run[j][1] - y) <= tolPx) reach = j + 1;
        }
        if (reach >= run.length - 1) {
          // The first third of the tolerance is free: a hand on the line wobbles a few
          // pixels, and a bot tracing the guide exactly still measured 0.92 without it.
          var mean = devN ? devSum / devN : 0, slack = tolPx / 3;
          close(k.clamp(1 - 0.5 * (Math.max(0, mean - slack) / (tolPx - slack)), 0.5, 1) *
            Math.max(0.4, 1 - 0.3 * wrong[seg]));
        }
      }

      function moveTo(x, y) {
        if (last) {
          var dist = Math.hypot(x - last[0], y - last[1]), steps = Math.max(1, Math.ceil(dist / 4));
          moved += dist;
          for (var s = 1; s <= steps; s++) {
            var px = last[0] + (x - last[0]) * s / steps, py = last[1] + (y - last[1]) * s / steps;
            follow(px, py);
          }
        } else {
          follow(x, y);
        }
        last = [x, y];
        trace.push([x, y]); traceN.push(norm(x, y));
        if (trace.length > 80) { trace.shift(); traceN.shift(); }
      }

      return {
        duration: duration,
        tick: function (dt, now) {
          t = now;
          // The base sets: outside Steady mode a segment not made in its slot is lost and
          // the guide moves on.
          if (!ctx.steady && seg < n && t - segStart > slot) close(0);
        },
        down: function (inp) {
          if (inp.src === "key") {
            if (seg >= n) return true;
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
          var s, j, run;
          // Segments: made ones in ink, the lit one in gold, those to come dashed.
          for (s = 0; s < n; s++) {
            run = segsPx[s];
            g.save();
            g.beginPath();
            for (j = 0; j < run.length; j++) { if (j) g.lineTo(run[j][0], run[j][1]); else g.moveTo(run[j][0], run[j][1]); }
            if (s < seg) {
              g.strokeStyle = q[s] > 0 ? C.ink : C.ash; g.lineWidth = q[s] > 0 ? 2 : 1;
              if (!(q[s] > 0)) g.setLineDash([2, 4]);
            } else if (s === seg) {
              g.strokeStyle = C.gold; g.lineWidth = 3;
            } else {
              g.strokeStyle = C.goldDim; g.lineWidth = 1.2; g.setLineDash([4, 4]);
            }
            g.stroke();
            g.restore();
          }
          if (seg < n) {
            run = segsPx[seg];
            // The start of the lit segment, and the arrow that makes it from the keyboard.
            k.diamond(g, run[0][0], run[0][1], 4, C.gold, null);
            var mid = run[Math.floor(run.length / 2)], key = keyOf[seg];
            var ang = { ArrowRight: 0, ArrowDown: Math.PI / 2, ArrowLeft: Math.PI, ArrowUp: -Math.PI / 2 }[key];
            var ox = Math.cos(ang + Math.PI / 2) * 12, oy = Math.sin(ang + Math.PI / 2) * 12;
            k.notch(g, mid[0] + ox + Math.cos(ang) * 4, mid[1] + oy + Math.sin(ang) * 4, ang, 6, C.gold);
            // Outside Steady mode a bead runs down the lit segment: the base setting.
            if (!ctx.steady) {
              var f = k.clamp((t - segStart) / slot, 0, 1), p = run[Math.min(run.length - 1, Math.floor(f * (run.length - 1)))];
              g.beginPath(); g.arc(p[0], p[1], 3, 0, Math.PI * 2); g.strokeStyle = C.candle; g.lineWidth = 1.4; g.stroke();
            }
          }
          // The player's trace, in ink.
          if (trace.length > 1) {
            g.save(); g.strokeStyle = C.ink; g.globalAlpha = 0.75; g.lineWidth = 1.4;
            g.beginPath();
            trace.forEach(function (p, i) { if (i) g.lineTo(p[0], p[1]); else g.moveTo(p[0], p[1]); });
            g.stroke(); g.restore();
          }
          // The texture line: lumpy (tall, jagged) to glossy (flat) as segments are made.
          var gloss = this.score(), x0 = box.x + box.w + 24, x1 = W - 14, y = H / 2;
          if (x1 - x0 > 30) {
            g.save(); g.strokeStyle = gloss > 0.6 ? C.gold : C.goldDim; g.lineWidth = 1.6;
            g.beginPath();
            for (var x = x0; x <= x1; x += 4) {
              var amp = (1 - gloss) * 12, yy = y + amp * Math.sin((x - x0) * 0.21) * Math.cos((x - x0) * 0.057 + 1.3);
              if (x === x0) g.moveTo(x, yy); else g.lineTo(x, yy);
            }
            g.stroke(); g.restore();
            k.text(g, "Texture", x0, y + 30, C, { size: 13 });
          }
          if (ctx.pointer.inside) k.reticle(g, ctx.pointer.x, ctx.pointer.y, C, pen);
        }
      };
    }
  };
})();
