// Bench minigame: Dry, turn the bundles (revamp plan §9.3, UI plan §9).
//
// Three to five bundles hang over smoke and cure at different speeds. Turn each one as it
// reaches its band. Each bundle shows its number, its leaves (which CURL as they cure, so
// the state reads by shape and not only by colour, as the plan requires), and a small dial
// with the band hatched and notched. A bundle left past the band goes brittle; one left to
// the end of its dial is scorched and lost.
//
// Input: click the bundle, or press its number (1-5). Single presses only. Steady mode:
// bands x1.6 wider (the §9 Steady column names only that, so the curing speed stays).
//
// Scoring per bundle: in the band 0.7..1 by closeness to its centre; just short of it
// ("too soon, still damp") 0.35; past it, 0.5 falling to 0.1; scorched 0. The score is the
// sum over all bundles. The moments each bundle reaches its band are spread through the
// game in a shuffled order, so the next one to watch is not simply the next on the left.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};

  defs.dry = {
    id: "dry",
    name: "Dry",
    first: "Turn each bundle when its needle reaches the notch.",
    hint: function () { return "Click a bundle, or press its number"; },
    KEYS: ["1", "2", "3", "4", "5"],
    HOLDS: [],
    HOLDS_STEADY: [],
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var n = Math.round(k.clamp(+ctx.tuning.bundles || (3 + Math.round(ctx.difficulty * 2)), 3, 5));
      var centre = 0.7;
      // ctx.win already carries Steady's x1.6.
      var half = k.clamp(0.09 * ctx.win, 0.06, 0.2);
      var band = [centre - half, Math.min(0.97, centre + half)];
      var first = 2.0, last = Math.max(first + 1, ctx.seconds - 0.8);
      var order = [];
      for (var i = 0; i < n; i++) order.push(i);
      for (i = n - 1; i > 0; i--) { var j = Math.floor(ctx.rng() * (i + 1)), tmp = order[i]; order[i] = order[j]; order[j] = tmp; }
      var bundles = [];
      for (i = 0; i < n; i++) {
        var when = (first + (last - first) * order[i] / Math.max(1, n - 1)) / ctx.baseSpeed;
        bundles.push({ cure: 0, rate: centre / when, turned: false, q: null, entered: false });
      }
      var duration = 0;
      bundles.forEach(function (b) { duration = Math.max(duration, 1 / b.rate + 0.25); });
      var cols = { x0: 12, w: 80 };

      function centreX(i) { return cols.x0 + cols.w * i + cols.w / 2; }
      function turn(i) {
        var b = bundles[i];
        if (!b || b.turned) return;
        b.turned = true;
        var c = b.cure, x = centreX(i);
        // The bundle's index goes with every hit and miss, so the stage puts the glint on
        // THIS bundle; the state it last saw does not yet say this one was turned.
        if (c >= band[0] && c <= band[1]) {
          b.q = 1 - 0.3 * Math.min(1, Math.abs(c - centre) / half);
          ctx.hit(b.q, x, 50, "steam", i);
        } else if (c < band[0]) {
          b.q = c >= band[0] - 0.08 ? 0.35 : 0;
          if (b.q) ctx.hit(0.2, x, 50, "steam", i); else ctx.miss(i);
        } else {
          b.q = Math.max(0.1, 0.5 - (c - band[1]) * 3);
          ctx.miss(i);
        }
      }

      // One leaf: a pointed blade whose tip curls upward and inward as it cures.
      function leaf(g, x, y, ang, len, curl, colour) {
        var tx = x + Math.cos(ang) * len, ty = y + Math.sin(ang) * len;
        var bend = curl * len * 0.9, side = Math.cos(ang) >= 0 ? -1 : 1;
        var cx1 = x + Math.cos(ang) * len * 0.5, cy1 = y + Math.sin(ang) * len * 0.5;
        tx += side * bend * 0.4; ty -= bend * 0.8;
        g.beginPath();
        g.moveTo(x, y);
        g.quadraticCurveTo(cx1 + 5, cy1 - 2 * curl, tx, ty);
        g.quadraticCurveTo(cx1 - 5, cy1 + 4, x, y);
        g.strokeStyle = colour; g.lineWidth = 1.3; g.stroke();
      }

      return {
        duration: duration,
        tick: function (dt) {
          bundles.forEach(function (b, i) {
            if (b.turned) return;
            b.cure = Math.min(1, b.cure + b.rate * dt);
            if (!b.entered && b.cure >= band[0]) { b.entered = true; ctx.tick(); }
            if (b.cure >= 1) { b.turned = true; b.q = 0; b.scorched = true; ctx.miss(i); }
          });
        },
        down: function (inp) {
          if (inp.src === "key") { turn(+inp.key - 1); return true; }
          if (!inp.inside) return true;
          var i = Math.floor((inp.x - cols.x0) / cols.w);
          if (i >= 0 && i < n) turn(i);
          return true;
        },
        state: function () {
          return { bundles: bundles.map(function (b) { return { cure: b.cure, band: band.slice(), turned: b.turned }; }) };
        },
        score: function () {
          var s = 0;
          bundles.forEach(function (b) { if (b.q) s += b.q; });
          return s / n;
        },
        done: function () { return bundles.every(function (b) { return b.turned; }); },
        draw: function (g, W, H) {
          cols.w = Math.min(96, (W - 24) / n);
          cols.x0 = 12;
          bundles.forEach(function (b, i) {
            var x = centreX(i), c = b.cure;
            var inBand = c >= band[0] && c <= band[1];
            var colour = b.scorched ? C.ash : inBand ? C.gold : c > band[1] ? C.ash : C.dim;
            k.text(g, String(i + 1), x, 10, C, { display: true, size: 13, align: "center", colour: inBand && !b.turned ? C.gold : C.dim });
            g.save(); g.strokeStyle = C.goldDim; g.lineWidth = 1;
            g.beginPath(); g.moveTo(x, 18); g.lineTo(x, 26); g.stroke(); g.restore();
            // A turned bundle hangs the other way up (its leaves point up), a shape change
            // that says "done" without colour.
            var flip = b.turned && !b.scorched ? -1 : 1, y0 = flip > 0 ? 26 : 58;
            for (var l = 0; l < 5; l++) {
              var ang = Math.PI / 2 + (l - 2) * 0.32;
              leaf(g, x, y0, flip > 0 ? ang : -ang, 26, Math.min(1, c * 1.15), colour);
            }
            if (b.scorched) {
              g.save(); g.strokeStyle = C.alarm; g.lineWidth = 1.8;
              g.beginPath(); g.moveTo(x - 10, 30); g.lineTo(x + 10, 52); g.moveTo(x + 10, 30); g.lineTo(x - 10, 52); g.stroke();
              g.restore();
            }
            // The dial: band hatched and notched, needle at the cure.
            var gy = H - 12, gr = Math.min(17, cols.w / 2 - 6);
            var A = function (v) { return Math.PI + v * Math.PI; };
            g.save(); g.strokeStyle = C.edge; g.lineWidth = 1.2;
            g.beginPath(); g.arc(x, gy, gr, Math.PI, 2 * Math.PI); g.stroke(); g.restore();
            k.dialBand(g, x, gy, gr - 7, gr, A(band[0]), A(band[1]), C.goldDim, { gap: 3, notches: true, notchColour: C.gold });
            var na = A(c);
            g.save(); g.strokeStyle = b.turned ? C.dim : C.ink; g.lineWidth = 1.6;
            g.beginPath(); g.moveTo(x, gy); g.lineTo(x + Math.cos(na) * (gr - 2), gy + Math.sin(na) * (gr - 2)); g.stroke();
            g.restore();
            if (b.turned) k.pip(g, x + gr + 8, gy - 6, 4, b.q > 0 ? b.q : "miss", C, false);
          });
          // The aim: a bracket under the bundle the pointer is over.
          var p = ctx.pointer;
          if (p.inside) {
            var i = Math.floor((p.x - cols.x0) / cols.w);
            if (i >= 0 && i < n) {
              var bx = cols.x0 + cols.w * i + 3, bw = cols.w - 6;
              g.save(); g.strokeStyle = C.gold; g.lineWidth = 1.2;
              g.beginPath();
              g.moveTo(bx, 22); g.lineTo(bx, 16); g.lineTo(bx + 6, 16);
              g.moveTo(bx + bw - 6, 16); g.lineTo(bx + bw, 16); g.lineTo(bx + bw, 22);
              g.stroke(); g.restore();
            }
          }
        }
      };
    }
  };
})();
