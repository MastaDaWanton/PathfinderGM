// Leather minigame: Assemble, lacing the pieces (leather UI plan §9: "the forge's Assemble beat
// game, with lacing in place of rivets"; revamp plan §11).
//
// The forge's Assemble (js/forge-games/assemble.js) carried over: the body, its fastenings and
// its lining come together one lace (or buckle) at a time, each pulled snug on its beat as a
// ring closes on the hole. Its fit meter is this game's gauge: how well seated the piece is so
// far, the running quality of the pulls made, with the server's "seated" band (lane E's band
// for Assemble is a fraction, 0.7 to 1). A lace not pulled before its window passes is loose.
//
// It registers as "leather.assemble", never "assemble": that key is the smith's game on the one
// registry, and replacing it would have the forge play lacing (js/leather-games/00-kit.js).
//
// Input: Space or a click, one press per lace. Nothing is held. Steady mode (UI plan §9, "as
// the forge's"): the ring's window x1.6 (`ctx.band(1.6)`); the tempo stays. The server's `drift`
// is unused (the ring is the beat).
//
// Scoring per lace: 1 in the inner 40% of the window, falling to 0.4 at its edge; a press just
// before the window or none at all is loose. The score is the sum over the six laces, over six.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var LACES = 6;

  defs["leather.assemble"] = {
    id: "leather.assemble",
    track: "leather",
    name: "Assemble",
    first: "Pull each lace snug as the ring closes on its hole.",
    hint: function () { return "Space or click on the beat"; },
    KEYS: ["Space"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "leather.buckle", miss: "leather.stitch.pull" },
    BAND: { unit: "fraction", label: "Seated", target: [0.7, 1.0], fail: null, value_start: 0, drift: 0,
      words: { low: "loose", in: "seated" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, G = ctx.gauge;
      var period = ((ctx.seconds - 0.4) / LACES) / ctx.baseSpeed;
      var markAt = 0.76, tm = markAt * period;
      var hw = Math.min(0.11 * ctx.band(1.6), period * (1 - markAt) * 0.95);
      var res = [];
      for (var i = 0; i < LACES; i++) res.push(null);
      var t = 0, geo = { cx: 52, cy: 44, rm: 10, r0: 40 };

      function beatAt(time) { return Math.floor(time / period); }
      function radius(tb) { return geo.r0 - (geo.r0 - geo.rm) * (tb / tm); }
      function fit() {
        var s = 0, n = 0;
        res.forEach(function (q) { if (q !== null) { n++; if (typeof q === "number") s += q; } });
        return n ? s / n : 0;
      }
      function pull() {
        var j = beatAt(t);
        if (j >= LACES || res[j] !== null) return;
        var err = (t - j * period) - tm;
        if (Math.abs(err) <= hw) {
          var a = Math.abs(err), inner = hw * 0.4;
          res[j] = a <= inner ? 1 : 1 - 0.6 * ((a - inner) / (hw - inner));
          ctx.hit(res[j], geo.cx, geo.cy, "grit");
        } else if (err < -hw && err > -3 * hw) { res[j] = "miss"; ctx.miss(); }
        G.v = fit();
      }

      return {
        duration: LACES * period + 0.15,
        tick: function (dt, now) {
          t = now;
          var cur = beatAt(t);
          for (var j = 0; j < LACES; j++) {
            if (res[j] !== null) continue;
            if (j < cur || (j === cur && (t - j * period) > tm + hw)) { res[j] = "miss"; ctx.miss(); G.v = fit(); }
          }
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          pull();
          return true;
        },
        state: function () {
          var j = Math.min(beatAt(t), LACES - 1);
          return { ring: k.clamp((t - j * period) / tm, 0, 1), pulled: res[j] !== null, lace: j, laces: LACES,
            fit: fit(), offset_s: (t - j * period) - tm, hw: hw };
        },
        score: function () {
          var s = 0; res.forEach(function (q) { if (typeof q === "number") s += q; });
          return k.clamp(s / LACES, 0, 1);
        },
        done: function () { for (var j = 0; j < LACES; j++) if (res[j] === null) return false; return true; },
        draw: function (g, W, H) {
          geo.cy = Math.round(H / 2 + 2); geo.r0 = Math.min(40, H / 2 - 4);
          var j = Math.min(beatAt(t), LACES - 1), tb = t - j * period;
          var r = Math.max(1, radius(Math.min(tb, tm + hw)));
          var rOut = radius(tm - hw), rIn = Math.max(1, radius(tm + hw));
          if (!ctx.reduced) k.ring(g, geo.cx, geo.cy, geo.rm, r, rOut, rIn, C, Math.abs(tb - tm) <= hw);
          else {
            var f = tb / tm;
            k.counted(g, geo.cx - 24, geo.cy, f >= 1 ? 4 : f >= 0.75 ? 3 : f >= 0.5 ? 2 : f >= 0.25 ? 1 : 0, C);
          }
          var x = geo.cx + 56;
          k.text(g, "Laces", x, 12, C, { size: 12 });
          window.LeatherGames.pips(k, g, x + 48, 12, res.filter(function (q) { return q !== null; }).map(function (q) { return q === "miss" ? "miss" : q; }), LACES, C,
            Math.max(12, Math.min(20, (W - x - 60) / LACES)));
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
