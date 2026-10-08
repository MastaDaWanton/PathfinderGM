// Leather minigame: Salt, cure the hide to its edges (leather UI plan §9, revamp plan §11).
//
// A green hide is cured by rubbing salt over every part of the flesh side, edges included,
// because an edge left bare is where it rots and slips its hair. The weight matters too: dry-
// salting runs from about a quarter of the green weight up to one to one (prior art §3.1: FAO
// 25% of green weight; NMSU one pound of salt per pound of hide). So the strip shows the hide in
// nine parts and the gauge shows the salt laid as a percent of the hide's weight, with the
// server's band. Too little and the cure will not hold; past the band the salt is wasted.
//
// Input: a scoop sweeps over the nine parts in turn (forth, then back); Space casts a handful
// on the part under it. A click casts straight onto the part clicked, scoop or not. A handful
// takes a fifth of a second to land, and a press while it is still in the air holds the next one
// back (the throw starts again): measured before that rule, a Space mashed three frames apart
// salted all nine parts with 15 handfuls at 104%, inside the band, and scored 1.
// Steady mode (UI plan §9, "coverage x1.5 per stroke"): each handful also covers the next part
// along the scoop's way, and the scoop moves at three quarters of the pace. Nothing is held.
// The server's `drift` is 0 for salt: nothing sways.
//
// Scoring: the share of the nine parts salted, times the weight: full anywhere in the band,
// scaled down below it, and falling to nothing a tenth of the scale past it (a hide buried in
// salt is not a cure, it is a sack spent). The game ends when every part is salted.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var N = 9, THROW = 0.2, DWELL = 0.42;

  defs["leather.salt"] = {
    id: "leather.salt",
    track: "leather",
    name: "Salt",
    first: "Salt every part of the hide, edges too. Enough to cure it, not a sackful.",
    hint: function (steady) {
      return "Space casts on the scoop's part, or click a part";
    },
    KEYS: ["Space"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "leather.salt", miss: "leather.salt" },
    BAND: { unit: "percent", label: "", after: "salt by weight", scale: [0, 130],
      target: [25, 100], fail: null, value_start: 0, drift: 0,
      words: { low: "too little", in: "cured", high: "wasted" },
      say: { high: "Too much: the salt is wasted" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, G = ctx.gauge, L = window.LeatherGames;
      var per = 62.5 / N;                       // nine handfuls land in the band's middle
      var covered = [], casts = 0, wasted = 0, busy = 0, t = 0;
      for (var i = 0; i < N; i++) covered.push(false);
      var dwell = DWELL / ctx.baseSpeed * (ctx.steady ? 1 / 0.75 : 1);
      var cells = [];                           // laid out by draw: [x, y, w, h]
      var W = 300, H = 88;

      // The scoop's way: 0..8 then back 8..0, a part at a time.
      function scoopAt(time) {
        var n = Math.floor(time / dwell), lap = 2 * N - 2;
        var m = n % lap;
        return m < N ? m : lap - m;
      }
      function scoopDir(time) { var n = Math.floor(time / dwell) % (2 * N - 2); return n < N - 1 ? 1 : -1; }
      function done() { for (var j = 0; j < N; j++) if (!covered[j]) return false; return true; }
      function count() { var c = 0; covered.forEach(function (x) { if (x) c++; }); return c; }

      function cast(i) {
        if (done() || i < 0 || i >= N) return;
        if (busy > 0) { busy = THROW; return; }
        busy = THROW; casts++;
        G.v = k.clamp(G.v + per, G.scale[0], G.scale[1]);
        var cell = cells[i] || [0, 0, 0, 0];
        if (!covered[i]) { covered[i] = true; ctx.hit(1, cell[0] + cell[2] / 2, cell[1] + cell[3] / 2, "grit"); }
        else { wasted++; ctx.miss(); }
        if (ctx.steady) {
          var j = i + scoopDir(t);
          if (j >= 0 && j < N) covered[j] = true;
        }
      }
      function weight() {
        var b = G.band, span = G.scale[1] - G.scale[0];
        if (G.v < b[0]) return G.v / Math.max(1e-6, b[0]);
        if (G.v <= b[1]) return 1;
        return Math.max(0, 1 - (G.v - b[1]) / (0.1 * span));
      }

      return {
        duration: ctx.seconds * (ctx.steady ? 2.6 : 1.8),
        tick: function (dt, now) { t = now; busy = Math.max(0, busy - dt); },
        down: function (inp) {
          if (inp.src === "key") { cast(scoopAt(t)); return true; }
          if (!inp.inside) return false;
          for (var j = 0; j < cells.length; j++) {
            var c = cells[j];
            if (inp.x >= c[0] && inp.x <= c[0] + c[2] && inp.y >= c[1] && inp.y <= c[1] + c[3]) { cast(j); return true; }
          }
          return true;
        },
        hint: function () { return G.status() === "high" ? null : count() >= N - 2 && count() < N ? "Nearly: find the bare parts" : null; },
        state: function () {
          var i = scoopAt(t), c = cells[i] || [0, 0, 0, 0], bare = [];
          covered.forEach(function (x, j) { if (!x) bare.push(j); });
          return { scoop: i, covered: covered.slice(), bare: bare, salt: G.v, band: G.band.slice(),
            casts: casts, wasted: wasted, busy: busy, cell: cells.map(function (q) { return { x: q[0] + q[2] / 2, y: q[1] + q[3] / 2 }; }),
            scoopAt: { x: c[0] + c[2] / 2, y: c[1] + c[3] / 2 }, parts: N };
        },
        score: function () { return k.clamp(count() / N * weight(), 0, 1); },
        done: done,
        draw: function (g, Wd, Hd) {
          W = Wd; H = Hd;
          var hw = Math.min(Wd - 40, 260), hh = Math.max(40, Hd - 26), x0 = (Wd - hw) / 2, y0 = 14;
          L.hide(g, Wd / 2, y0 + hh / 2, hw + 16, hh + 8, C);
          cells.length = 0;
          var cw = hw / 3, ch = hh / 3;
          for (var r = 0; r < 3; r++) for (var c = 0; c < 3; c++) {
            // The way runs along each row in turn, so its cells are numbered row by row.
            var col = r % 2 ? 2 - c : c;
            cells[r * 3 + c] = [x0 + col * cw + 2, y0 + r * ch + 2, cw - 4, ch - 4];
          }
          var cur = scoopAt(t);
          cells.forEach(function (q, j) {
            if (covered[j]) k.barBand(g, q[0], q[1], q[2], q[3], C.gold, { gap: 3 });
            else {
              g.save(); g.setLineDash && g.setLineDash([3, 3]); g.strokeStyle = C.ash; g.lineWidth = 1;
              g.strokeRect(q[0] + 0.5, q[1] + 0.5, q[2] - 1, q[3] - 1); g.setLineDash && g.setLineDash([]); g.restore();
            }
            if (j === cur && !done()) {
              g.save(); g.strokeStyle = C.ink; g.lineWidth = 2; g.strokeRect(q[0] - 1, q[1] - 1, q[2] + 2, q[3] + 2); g.restore();
            }
          });
          k.text(g, count() + " of " + N + " salted", 8, 8, C, { size: 12 });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= Hd) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
