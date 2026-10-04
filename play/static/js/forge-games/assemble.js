// Forge minigame: Assemble, peen the rivets (blacksmithing UI plan §9, revamp plan §11).
//
// The head slides onto the haft and the guard seats; each rivet is peened on its beat. A ring
// closes on the rivet's head, as Grind's ring does; strike as it closes. The fit meter beside
// it shows how true the piece is sitting, rivet by rivet: the running quality of the blows
// struck so far, with a notch where the piece counts as seated.
//
// Input: Space or a click on the strip, one press per rivet. Nothing is held in either mode.
// Steady mode (UI plan §9): the ring's window x1.6 (`ctx.band(1.6)`); the tempo stays, as the
// column asks only for the window.
//
// Scoring per rivet: 1 in the inner 40% of the window, falling to 0.4 at its edge; a press
// just before the window or none at all is a miss for that rivet. The score is the sum over
// the rivets (five by default, `tuning.rivets`).
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};

  defs.assemble = {
    id: "assemble",
    track: "forge",
    name: "Assemble",
    first: "Peen each rivet as the ring closes on it.",
    hint: function () { return "Space or click on the beat"; },
    KEYS: ["Space"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "forge.rivet", miss: "forge.strike.miss" },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var rivets = Math.round(k.clamp(+ctx.tuning.rivets || 5, 3, 8));
      var period = ((ctx.seconds - 0.4) / rivets) / ctx.baseSpeed;
      var markAt = 0.76, tm = markAt * period;
      var hw = Math.min(0.11 * ctx.band(1.6), period * (1 - markAt) * 0.95);
      var res = [];
      for (var i = 0; i < rivets; i++) res.push(null);
      var t = 0;
      var geo = { cx: 52, cy: 44, rm: 10, r0: 40 };

      function beatAt(time) { return Math.floor(time / period); }
      function radius(tb) { return geo.r0 - (geo.r0 - geo.rm) * (tb / tm); }
      function resolved() { var n = 0; for (var j = 0; j < rivets; j++) if (res[j] !== null) n++; return n; }
      function fit() {
        var s = 0, n = 0;
        res.forEach(function (q) { if (q !== null) { n++; if (typeof q === "number") s += q; } });
        return n ? s / n : 0;
      }

      function peen() {
        var i = beatAt(t);
        if (i >= rivets || res[i] !== null) return;
        var err = (t - i * period) - tm;
        if (Math.abs(err) <= hw) {
          var a = Math.abs(err), inner = hw * 0.4;
          res[i] = a <= inner ? 1 : 1 - 0.6 * ((a - inner) / (hw - inner));
          ctx.hit(res[i], geo.cx, geo.cy, "spark");
        } else if (err < -hw && err > -3 * hw) {
          res[i] = "miss"; ctx.miss();
        }
      }

      return {
        duration: rivets * period + 0.15,
        tick: function (dt, now) {
          t = now;
          var cur = beatAt(t);
          for (var i = 0; i < rivets; i++) {
            if (res[i] !== null) continue;
            if (i < cur || (i === cur && (t - i * period) > tm + hw)) { res[i] = "miss"; ctx.miss(); }
          }
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          peen();
          return true;
        },
        state: function () {
          var i = Math.min(beatAt(t), rivets - 1);
          return { ring: k.clamp((t - i * period) / tm, 0, 1), struck: res[i] !== null,
            rivet: i, rivets: rivets, fit: fit() };
        },
        score: function () { var s = 0; res.forEach(function (q) { if (typeof q === "number") s += q; }); return s / rivets; },
        done: function () { return resolved() >= rivets; },
        draw: function (g, W, H) {
          geo.cy = H / 2;
          geo.r0 = Math.min(40, H / 2 - 4);
          var i = Math.min(beatAt(t), rivets - 1), tb = t - i * period;
          var inWin = Math.abs(tb - tm) <= hw && res[i] === null;
          k.ring(g, geo.cx, geo.cy, geo.rm, Math.max(1, radius(tb)), radius(tm - hw), Math.max(1, radius(tm + hw)), C, inWin);
          // The rivets, as pips in a row along the haft.
          var x0 = 112, gap = Math.min(28, (W - x0 - 90) / rivets);
          g.save(); g.strokeStyle = C.goldDim; g.lineWidth = 1;
          g.beginPath(); g.moveTo(x0, geo.cy); g.lineTo(x0 + gap * rivets, geo.cy); g.stroke(); g.restore();
          for (var b = 0; b < rivets; b++) k.pip(g, x0 + gap * b + gap / 2, geo.cy, 6, res[b], C, b === i && res[b] === null);
          k.text(g, "Rivet " + Math.min(i + 1, rivets) + " of " + rivets, x0, geo.cy + 22, C, { size: 13 });
          // The fit meter: a short upright scale, filled to the running fit, notched at 0.6
          // (seated).
          var fx = Math.min(W - 30, x0 + gap * rivets + 40), fh = Math.min(64, H - 16), fy = geo.cy - fh / 2;
          g.save(); g.strokeStyle = C.edge; g.strokeRect(fx + 0.5, fy + 0.5, 10, fh); g.restore();
          var f = fit();
          if (f > 0) k.barBand(g, fx + 1, fy + fh * (1 - f), 9, fh * f, C.gold, { gap: 4 });
          k.notch(g, fx - 3, fy + fh * 0.4, 0, 5, C.gold);
          k.text(g, "Fit", fx + 5, fy + fh + 9, C, { size: 13, align: "center" });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
