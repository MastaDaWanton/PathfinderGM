// Leather minigame: Dye, an even take (leather UI plan §9: "the forge's Finish game (coverage
// strokes), with a dye colour"; revamp plan §11).
//
// The forge's Finish, keyboard form, carried over: the brush's load swells and thins as it is
// dipped and wiped (a slow, readable swing, never noise), and each press lays the next strip at
// the load of that moment; the brush then goes back to the pot. Too thin and the leather shows
// through in streaks; too heavy and the dye pools and blotches. The gauge is the brush's load
// as a percent of an even coat, with the server's even band. Lane E sends no failing band for
// dye (a heavy strip is uneven, not ruined), so above the band reads "heavy", not a danger.
//
// The swing is sin squared, so the load lingers at its full and its empty and passes through
// the band on the way: the player waits for it to come into the band and lays the strip. The
// server's `drift` is 0 for dye.
//
// Input: Space or a click lays the next strip. The brush is in the pot for half a second after
// each; a press while it is there keeps it there (the forge measured four presses in four frames
// laying the whole piece at one good moment, so the timing has to be asked each time). Steady
// mode (UI plan §9, "as the forge's": strokes x1.5): the band x1.5 and the swing at two thirds
// of the pace. Nothing is held. The dye's own colour is the stage's content; the strip draws
// the strips in the chrome's gold.
//
// Scoring: four strips, each earning the gauge's quality at its laying (1 in the band's inner
// half, 0.6 at its rim, nothing thin or heavy). The score is the mean of the four.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var N = 4, POT = 0.5, PERIOD = 2.6, LOW = 30, SWING = 75;

  defs["leather.dye"] = {
    id: "leather.dye",
    track: "leather",
    name: "Dye",
    first: "Lay each strip when the brush holds an even coat: not thin, not heavy.",
    hint: function () { return "Space or click lays the next strip"; },
    KEYS: ["Space"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "leather.brush", miss: "leather.brush" },
    BAND: { unit: "percent", label: "", after: "of a coat", scale: [0, 140], target: [85, 100],
      fail: null, value_start: LOW, drift: 0, steadyBand: 1.5,
      words: { low: "thin", in: "even", high: "heavy" },
      say: { high: "Heavy: it will blotch" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, G = ctx.gauge;
      var period = PERIOD / ctx.baseSpeed / (ctx.steady ? 2 / 3 : 1);
      var res = [], pot = 0, t = 0, ph = 0, geo = { x0: 16, y0: 10, w: 200, h: 50 };

      function lay() {
        if (res.length >= N) return;
        if (pot > 0) { pot = POT; return; }
        pot = POT;
        var q = G.quality(0.5, 0.6);
        res.push(q);
        var sy = geo.y0 + geo.h * (res.length - 0.5) / N;
        if (q > 0) ctx.hit(q, geo.x0 + geo.w / 2, sy, "grit"); else ctx.miss();
      }

      return {
        duration: ctx.seconds * (ctx.steady ? 2.6 : 1.7),
        tick: function (dt, now) {
          t = now; pot = Math.max(0, pot - dt);
          ph = Math.sin(Math.PI * now / period);
          G.v = LOW + SWING * ph * ph;
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          lay();
          return true;
        },
        hint: function () { return pot > 0 && res.length < N ? "In the pot" : null; },
        state: function () {
          return { load: G.v, band: G.band.slice(), pot: pot, strips: res.length, of: N, results: res.slice(),
            rising: Math.cos(Math.PI * t / period) * ph > 0 };
        },
        score: function () { var s = 0; res.forEach(function (q) { s += q; }); return k.clamp(s / N, 0, 1); },
        done: function () { return res.length >= N && pot <= 0.3; },
        draw: function (g, W, H) {
          geo.x0 = 16; geo.y0 = 10; geo.w = Math.max(80, Math.min(W - 120, 260)); geo.h = Math.max(30, H - 20);
          var sh = geo.h / N;
          for (var i = 0; i < N; i++) {
            var y = geo.y0 + i * sh;
            if (i < res.length) {
              var q = res[i], v = q > 0 ? 3 : 7;
              k.barBand(g, geo.x0, y + 1, geo.w, sh - 2, q > 0 ? C.gold : C.ash, { gap: v, cross: q <= 0 });
            } else {
              g.save(); g.strokeStyle = i === res.length ? C.ink : C.edge; g.lineWidth = 1;
              g.strokeRect(geo.x0 + 0.5, y + 1.5, geo.w - 1, sh - 3); g.restore();
            }
          }
          // The brush beside the piece: its bristles fuller the heavier its load.
          var bx = geo.x0 + geo.w + 26, by = geo.y0 + geo.h / 2;
          g.save(); g.strokeStyle = pot > 0 ? C.dim : C.gold; g.lineWidth = 1.5;
          g.beginPath(); g.moveTo(bx, by - 18); g.lineTo(bx, by); g.stroke();
          var bw = 4 + 8 * k.clamp(G.v / 115, 0, 1);
          g.beginPath(); g.moveTo(bx - bw / 2, by); g.lineTo(bx + bw / 2, by); g.lineTo(bx, by + 10); g.closePath(); g.stroke();
          g.restore();
          k.text(g, res.length + " of " + N, bx + 16, by, C, { size: 12 });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
