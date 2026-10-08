// Leather minigame: the cut test, the second half of Tan, played at Collect (leather UI plan
// §9, revamp plan §8.3: "Collecting a bark or planar tannage plays the cut test").
//
// A tanner knows a bark hide is done when it is "struck through": cut it, and the tan colour
// runs the full cross-section (prior art §3.3). The cut has to be square to the face, or the
// section reads wider than the leather is and a raw streak hides in the slant; and it is made
// in more than one place, because a hide tans unevenly (the butt is thickest). So: three cuts,
// at the butt, the belly and the shoulder, each made when the knife stands square. The knife's
// lean swings out and back (a hand settling, slowest as it comes square); the gauge is the lean
// as a fraction off square, the square band hatched, the slant that reads false cross-hatched.
//
// The server sends no band at Collect, so this game's own BAND is what it plays unless the
// shell passes one. The lean's swing is the game's (sin squared, so it dwells near square);
// `drift` is unused here.
//
// Input: Space, C or a click cuts. A cut takes half a second; a press while the knife is still
// in the cut keeps it there (it starts the half second again), so mashing cuts nothing more.
// Steady mode: the swing at 0.6 of the pace and the band x1.6. Nothing is held.
//
// Scoring: each cut earns the gauge's quality (1 in the inner half of the square band, 0.6 at
// its rim, nothing outside it); the score is the mean of the three.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var CUTS = 3, BUSY = 0.5, PERIOD = 1.8, PLACES = ["butt", "belly", "shoulder"];

  defs["leather.cut-test"] = {
    id: "leather.cut-test",
    track: "leather",
    name: "Cut test",
    first: "Cut the leather square, three times, to see whether the tan has run through.",
    hint: function () { return "Space or click cuts when it stands square"; },
    KEYS: ["Space", "C"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "leather.cut-test", miss: "leather.knife" },
    BAND: { unit: "fraction", label: "", after: "off square", target: [0, 0.15], fail: [0.6, 1],
      value_start: 0.8, drift: 0, steadyBand: 1.6,
      words: { in: "square", high: "leaning", fail: "slanted" },
      say: { fail: "Slanted: wait for it to come square" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, G = ctx.gauge;
      var period = PERIOD / ctx.baseSpeed / (ctx.steady ? 0.6 : 1);
      var res = [], busy = 0, t = 0, geo = { x: 60, y: 40 };

      function cutNow() {
        if (res.length >= CUTS) return;
        if (busy > 0) { busy = BUSY; return; }
        busy = BUSY;
        var q = G.quality(0.5, 0.6);
        res.push(q);
        if (q > 0) ctx.hit(q, geo.x, geo.y, "grit"); else ctx.miss();
      }

      return {
        duration: ctx.seconds * (ctx.steady ? 2.4 : 1.6),
        tick: function (dt, now) {
          t = now; busy = Math.max(0, busy - dt);
          var c = Math.cos(Math.PI * now / period);
          G.v = 0.8 * c * c;
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          cutNow();
          return true;
        },
        hint: function () {
          if (res.length >= CUTS) return null;
          return busy > 0 ? "In the cut" : "Cut " + (res.length + 1) + ": the " + PLACES[res.length];
        },
        state: function () {
          return { lean: G.v, band: G.band.slice(), cuts: res.length, of: CUTS, busy: busy, results: res.slice() };
        },
        score: function () { var s = 0; res.forEach(function (q) { s += q; }); return k.clamp(s / CUTS, 0, 1); },
        done: function () { return res.length >= CUTS && busy <= 0; },
        draw: function (g, W, H) {
          geo.x = 50; geo.y = Math.round(H / 2 + 2);
          // The knife, leaning by the gauge's value, over the leather's edge.
          var ang = G.v * 0.9 * (Math.sin(Math.PI * t / period) >= 0 ? 1 : -1);
          g.save(); g.translate(geo.x, geo.y + 14);
          g.strokeStyle = C.goldDim; g.lineWidth = 1.2; g.strokeRect(-34, 0.5, 68, 8);
          g.rotate(ang);
          g.strokeStyle = busy > 0 ? C.gold : C.ink; g.lineWidth = 2.4;
          g.beginPath(); g.moveTo(0, 0); g.lineTo(0, -30); g.stroke();
          g.restore();
          var x = geo.x + 54;
          k.text(g, "Cuts", x, 12, C, { size: 12 });
          window.LeatherGames.pips(k, g, x + 40, 12, res, CUTS, C, 18);
          if (res.length) {
            // Each section as it was read: the tan bar across the leather's thickness.
            for (var i = 0; i < res.length; i++) {
              var sx = x + i * 46, sy = geo.y + 6;
              k.barBand(g, sx, sy, 38, 9, res[i] > 0 ? C.gold : C.ash, { gap: res[i] > 0 ? 3 : 6 });
              k.text(g, PLACES[i], sx, sy + 20, C, { size: 11 });
            }
          }
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
