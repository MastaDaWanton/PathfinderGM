// Leather minigame: Curry, fat worked in with the slicker (leather UI plan §9, revamp plan §11).
//
// Currying works dubbin (cod oil and tallow) into tanned leather with a slicker, for strength,
// suppleness and water repellency (prior art §3.4). Healthy finished leather holds 2 to 10% fat
// (WA Museum conservation manual, prior art §3.4); dry leather cracks, and a hide given more
// grease than it can hold spews it back out of the grain (a curried leather's "spue"). So the
// gauge is the fat in the leather as a percent, the server's healthy band hatched and its
// greasy failing band cross-hatched, and each slicker stroke works some dubbin in. The fat
// sinks into the leather as it is worked (the server's `drift`, percent per second; half in
// Steady), so the reading falls between strokes and the player keeps it up.
//
// Input: Space or a click is one stroke of the slicker with dubbin. A stroke takes a third of
// a second to work in; a press while it is still working is a hurried smear: it adds the
// grease without the work and counts nothing. So mashing greases the hide over the band and
// earns nothing. Steady mode (UI plan §9, "drift x0.5"): the fat sinks at half the rate and the
// band is x1.6. Nothing is held.
//
// Scoring: eight strokes made while the fat reads in the band are the work. Each earns the
// gauge's quality at that moment (1 in the band's inner half, 0.6 at its rim; the way in is
// free, as the alchemist's gauges: the first strokes cross the rim on the way to the middle).
// A stroke out of the band does no work. Each crossing into the spewing band costs 0.15. The
// score is the strokes' credit over eight, less the spews.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var NEED = 8, RISE = 1.0, WORK = 0.34, SPEW = 0.15;

  defs["leather.curry"] = {
    id: "leather.curry",
    track: "leather",
    name: "Curry",
    first: "Work the dubbin in, stroke by stroke. Keep the leather supple, never greasy.",
    hint: function () { return "Space or click: one stroke"; },
    KEYS: ["Space"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "leather.scrape", miss: "leather.scrape" },
    BAND: { unit: "percent", label: "Fat", scale: [0, 30], target: [2, 10], fail: [16, 30],
      value_start: 0, drift: 0.5, steadyBand: 1.6,
      words: { low: "dry", in: "supple", high: "greasy", fail: "spewing" },
      say: { high: "Greasy: let it sink in", fail: "Spewing fat: let it sink in" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, G = ctx.gauge;
      var res = [], busy = 0, smears = 0, spews = 0, over = false, settled = false, t = 0;
      var geo = { x: 40, y: 40 };

      function stroke() {
        if (res.length >= NEED) return;
        G.v = k.clamp(G.v + RISE, G.scale[0], G.scale[1]);
        if (busy > 0) { smears++; ctx.miss(); return; }
        busy = WORK;
        if (!G.inBand()) { ctx.miss(); return; }
        var q = G.quality(0.5, 0.6);
        if (q >= 1) settled = true;
        if (!settled) q = 1;
        res.push(q);
        ctx.hit(q, geo.x, geo.y, "grit");
      }

      return {
        duration: ctx.seconds * (ctx.steady ? 2.6 : 1.9),
        tick: function (dt, now) {
          t = now; busy = Math.max(0, busy - dt);
          G.v = Math.max(G.scale[0], G.v - G.drift * dt * (ctx.steady ? 0.5 : 1));
          var s = G.status();
          if (s === "fail" && !over) { over = true; spews++; ctx.miss(); }
          else if (s !== "fail" && G.fail && G.v < G.fail[0] - 1) over = false;
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          stroke();
          return true;
        },
        hint: function () {
          if (res.length >= NEED) return null;
          if (busy > 0) return "Working it in";
          return G.status() === "low" ? "Dry: a stroke of dubbin" : null;
        },
        state: function () {
          return { fat: G.v, band: G.band.slice(), fail: G.fail, rise: RISE, busy: busy, strokes: res.length,
            need: NEED, smears: smears, spews: spews, status: G.status() };
        },
        score: function () {
          var s = 0; res.forEach(function (q) { s += q; });
          return Math.max(0, Math.min(1, s / NEED) - SPEW * spews);
        },
        done: function () { return res.length >= NEED; },
        draw: function (g, W, H) {
          geo.x = 44; geo.y = Math.round(H / 2);
          // The slicker over the leather: a blade on a handle, rocked forward on each stroke.
          var lean = busy > 0 && !ctx.reduced ? (busy / WORK) * 6 : 0;
          g.save(); g.strokeStyle = C.goldDim; g.lineWidth = 1.2;
          g.strokeRect(10.5, geo.y + 10.5, 68, 10); g.restore();
          g.save(); g.strokeStyle = busy > 0 ? C.gold : C.ink; g.lineWidth = 2;
          g.beginPath(); g.moveTo(24 + lean, geo.y + 8); g.lineTo(64 + lean, geo.y + 8);
          g.moveTo(44 + lean, geo.y + 8); g.lineTo(44 + lean, geo.y - 12); g.stroke(); g.restore();
          var x = 96;
          k.text(g, "Worked", x, 12, C, { size: 12 });
          window.LeatherGames.pips(k, g, x + 56, 12, res, NEED, C, Math.max(12, Math.min(18, (W - x - 70) / NEED)));
          if (spews) k.text(g, "Spewed " + spews + (spews === 1 ? " time" : " times"), x, geo.y + 14, C, { size: 12, colour: C.alarm });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
