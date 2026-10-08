// Leather minigame: Cut, the round knife along the pattern (leather UI plan §9, revamp plan §11).
//
// A pattern piece is chalked onto the leather and cut out with a round knife pushed along the
// line. The variable is how far the edge wanders off the chalk: a little is trimmed, a lot
// spoils the piece's edge. The gauge is the knife's distance off the line (a fraction of the
// widest the line ever runs from the start), with the server's "on the line" band from 0 and
// its "off the pattern" band cross-hatched; the hand trembles by the server's `drift` either
// way (half in Steady).
//
// Input: Space (or a click) sets the knife going; it then runs along the line by itself. Up and
// Down turn its heading a step each way (three steps either side), so a curve is followed with a
// few presses rather than one per stroke; the pointer's height over the strip steers it
// straight to that place. The plan names Left and Right for steering because the line runs away
// from the player on the stage; in the strip it runs across, so Up and Down move the knife the
// way they read, and Left and Right are kept as the same two turns for a player who looks at
// the stage. Steady mode (UI plan §9, "auto-advance, steer only; band x1.5"): the knife runs at
// three quarters of the pace and the band is x1.5. Nothing is held.
//
// Scoring: the knife's distance off the line is read every moment of the cut, each moment
// earning the gauge's quality (1 within the band's inner half from the line, 0.6 at its rim,
// nothing beyond). The score is the mean over the whole line. A knife never started cuts
// nothing.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var TURN = 0.12, MAXT = 3;

  defs["leather.cut"] = {
    id: "leather.cut",
    track: "leather",
    name: "Cut",
    first: "Follow the chalk line with the knife. Space starts it; Up and Down steer.",
    hint: function () { return "Space starts; Up, Down or the pointer steer"; },
    KEYS: ["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "leather.knife", miss: "leather.knife" },
    BAND: { unit: "fraction", label: "Off the line", target: [0, 0.1], fail: [0.4, 1],
      value_start: 0, drift: 0.03, steadyBand: 1.5,
      words: { in: "on the line", high: "wandering", fail: "off the pattern" },
      say: { high: "Wandering: steer back to the line", fail: "Off the pattern: steer back" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, G = ctx.gauge;
      var run = ctx.seconds * 0.75 / ctx.baseSpeed / (ctx.steady ? 0.75 : 1);
      var side = ctx.rng() < 0.5 ? -1 : 1, ph = ctx.rng() * 6.28, amp = 0.38 + 0.06 * ctx.rng();
      var D = k.drift(ctx.rng() * 10), trem = G.drift * (ctx.steady ? 0.5 : 1);
      var s = 0, l = 0, heading = 0, started = false, t = 0, sum = 0, n = 0, aimY = null, last = 0;
      var geo = { x0: 16, x1: 300, cy: 40, half: 30 };

      // The chalk line: a pattern edge, one sweep to one side and back, with a small waver.
      function line(u) { return side * (amp * Math.sin(Math.PI * u) + 0.05 * Math.sin(2 * Math.PI * u * 2 + ph) * Math.sin(Math.PI * u)); }
      function off() { return Math.abs(l + trem * D(t) - line(s)); }

      return {
        duration: run * 1.9 + 1,
        tick: function (dt, now) {
          t = now;
          if (!started || s >= 1) { G.v = k.clamp(off(), 0, 1); return; }
          if (aimY != null) l += (aimY - l) * (1 - Math.exp(-dt / 0.1));
          else l = k.clamp(l + heading * TURN * dt * 1.6, -1, 1);
          s = Math.min(1, s + dt / run);
          G.v = k.clamp(off(), 0, 1);
          var q = G.quality(0.5, 0.6);
          sum += q * dt; n += dt;
          if (now - last > 0.25) { last = now; if (q > 0) ctx.hit(q * 0.6, geo.x0 + (geo.x1 - geo.x0) * s, geo.cy, "grit"); else ctx.miss(); }
        },
        down: function (inp) {
          if (inp.src === "key") {
            if (inp.key === "Space") started = true;
            else if (inp.key === "ArrowUp" || inp.key === "ArrowLeft") { aimY = null; heading = Math.max(-MAXT, heading - 1); }
            else { aimY = null; heading = Math.min(MAXT, heading + 1); }
            return true;
          }
          if (!inp.inside) return false;
          started = true;
          aimY = k.clamp((inp.y - geo.cy) / geo.half, -1, 1);
          return true;
        },
        move: function (inp) { if (inp.inside && aimY != null) aimY = k.clamp((inp.y - geo.cy) / geo.half, -1, 1); },
        hint: function () { return started ? null : "Space or click to start the knife"; },
        state: function () {
          var ahead = Math.min(1, s + 0.08), soon = Math.min(1, s + 0.1 / run), dU = 0.01;
          return { started: started, along: s, knife: l, heading: heading, line: line(s), line_ahead: line(ahead),
            line_soon: line(soon), line_rate: (line(Math.min(1, s + dU)) - line(s)) / (dU * run), turn: TURN * 1.6,
            off: G.v, band: G.band.slice(), run: run, tremor: trem * D(t), y: geo.cy + l * geo.half,
            line_y: geo.cy + line(ahead) * geo.half, half: geo.half, cy: geo.cy };
        },
        score: function () { return n > 0 ? k.clamp(sum / Math.max(n, run), 0, 1) : 0; },
        done: function () { return s >= 1; },
        draw: function (g, W, H) {
          geo.x0 = 16; geo.x1 = Math.max(60, W - 16); geo.cy = Math.round(H / 2 + 2); geo.half = Math.max(16, H / 2 - 12);
          var X = function (u) { return geo.x0 + (geo.x1 - geo.x0) * u; };
          // The chalk line, dashed (the pattern), and the cut so far, solid.
          g.save(); g.strokeStyle = C.dim; g.lineWidth = 1.2; g.setLineDash && g.setLineDash([4, 3]);
          g.beginPath();
          for (var i = 0; i <= 40; i++) { var u = i / 40, y = geo.cy + line(u) * geo.half; if (i) g.lineTo(X(u), y); else g.moveTo(X(u), y); }
          g.stroke(); g.setLineDash && g.setLineDash([]); g.restore();
          // The knife: a half-moon blade at its place.
          var kx = X(s), ky = geo.cy + l * geo.half;
          g.save(); g.strokeStyle = started ? C.gold : C.ink; g.lineWidth = 2;
          g.beginPath(); g.arc(kx, ky, 7, Math.PI * 0.5, Math.PI * 1.5, heading > 0); g.stroke(); g.restore();
          k.notch(g, kx + 10, ky, 0, 4, C.gold);
          k.text(g, Math.round(s * 100) + "% cut", 8, 9, C, { size: 12 });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
