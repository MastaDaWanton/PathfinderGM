// Leather minigame: Laminate, glue spread then clamped (leather UI plan §9, revamp plan §12).
//
// Two leathers of one material are glued and stitched into one heavy leather (doubled leather
// was a real armour build, revamp plan §12). The two things that decide the bond are how evenly
// the glue covers the faces and when they are pressed: a contact glue is laid on, left until
// it is tacky, then the faces are brought together; clamped wet, the layers slide; clamped
// late, the glue has skinned over and will not take. So the game has two parts:
//   - SPREAD. Space or a click on the strip lays one stroke of glue. The gauge is the faces'
//     coverage in percent, with the server's even band; short of it leaves dry patches, past
//     it the glue squeezes out of the edges. A stroke takes a quarter of a second.
//   - CLAMP. From the last stroke the glue goes tacky: a ring closes on the clamp's mark over
//     about a second (a fresh stroke starts it again). C or the Clamp button presses the faces
//     together, and the clamp ends the game. Under reduced motion the ring stands still and the
//     counted beat ("3", "2", "1", "Now") gives the same moment.
// The server's `drift` is 0 for laminate. Steady mode (UI plan §9, "window x1.6"): the clamp's
// window x1.6. Nothing is held.
//
// Scoring: the coverage's quality at the clamp (1 in the band's inner half, 0.7 at its rim,
// nothing outside it) times the clamp's timing (1 in the inner 40% of the window, 0.6 at its
// edge; a clamp before the window is wet, 0.2; after it, dry, 0.2). Never clamped, nothing.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var STROKE = 0.25, ADD = 18, TACK = 1.0, HW = 0.16;

  defs["leather.laminate"] = {
    id: "leather.laminate",
    track: "leather",
    name: "Laminate",
    first: "Spread the glue evenly, then clamp the layers as it turns tacky.",
    hint: function () { return "Space or click spreads; C clamps"; },
    KEYS: ["Space", "C"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "leather.clamp", miss: "leather.clamp", spread: "leather.brush" },
    BAND: { unit: "percent", label: "Glue", after: "", scale: [0, 130], target: [80, 100],
      fail: null, value_start: 0, drift: 0,
      words: { low: "dry patches", in: "even", high: "squeezing out" },
      say: { high: "Squeezing out: clamp it as it is" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, G = ctx.gauge;
      var hw = HW * ctx.band(1.6);
      var strokes = 0, busy = 0, since = -1, clamped = false, timing = 0, cov = 0, t = 0, word = "";
      var geo = { cx: 60, cy: 40 };

      function spread() {
        if (clamped || busy > 0) return;
        busy = STROKE; strokes++; since = 0;
        G.v = k.clamp(G.v + ADD, G.scale[0], G.scale[1]);
        ctx.cue("spread");
      }
      function clamp() {
        if (clamped) return;
        clamped = true;
        cov = G.inBand() ? G.quality(0.5, 0.7) : 0;
        if (since < 0) timing = 0;
        else {
          var err = since - TACK;
          if (Math.abs(err) <= hw) { var a = Math.abs(err), inner = hw * 0.4; timing = a <= inner ? 1 : 1 - 0.4 * ((a - inner) / (hw - inner)); }
          else timing = 0.2;
          word = err < -hw ? "Clamped wet: the layers slid" : err > hw ? "Clamped late: the glue had skinned" : "";
        }
        var q = cov * timing;
        if (q > 0.5) ctx.hit(q, geo.cx, geo.cy, "grit"); else ctx.miss();
      }

      return {
        duration: ctx.seconds * (ctx.steady ? 2.4 : 1.8),
        tick: function (dt, now) {
          t = now; busy = Math.max(0, busy - dt);
          if (since >= 0 && !clamped) since += dt;
        },
        down: function (inp) {
          if (inp.src === "key" && inp.key === "C") { clamp(); return true; }
          if (inp.src === "pointer" && !inp.inside) return false;
          spread();
          return true;
        },
        button: { label: "Clamp", press: function () { clamp(); } },
        hint: function () {
          if (clamped) return word || null;
          if (since < 0) return null;
          if (since < TACK - hw) return "Wet: wait for it to go tacky";
          if (since <= TACK + hw) return "Tacky: clamp now";
          return "Skinning over: spread a fresh stroke";
        },
        state: function () {
          return { glue: G.v, band: G.band.slice(), strokes: strokes, busy: busy, since: since, tack: TACK, hw: hw,
            clamped: clamped, timing: timing, in_window: since >= 0 && Math.abs(since - TACK) <= hw };
        },
        score: function () { return clamped ? k.clamp(cov * timing, 0, 1) : 0; },
        done: function () { return clamped; },
        draw: function (g, W, H) {
          geo.cx = 60; geo.cy = Math.round(H / 2 + 2);
          // The two layers, the lower glued as it is spread (hatched by coverage), and the clamp.
          var lw = 76, lx = geo.cx - lw / 2;
          g.save(); g.strokeStyle = C.goldDim; g.lineWidth = 1.2;
          g.strokeRect(lx + 0.5, geo.cy + 6.5, lw, 8);
          g.strokeRect(lx + 0.5, (clamped ? geo.cy - 2 : geo.cy - 14) + 0.5, lw, 8);
          g.restore();
          var c = k.clamp(G.v / 100, 0, 1);
          if (c > 0) k.barBand(g, lx + 1, geo.cy + 2, lw * c, 4, C.gold, { gap: 3 });
          // The tack ring, closing on the clamp's mark (still under reduced motion: the count).
          var rx = geo.cx + 76, f = since < 0 ? 0 : k.clamp(since / TACK, 0, 1.6);
          if (!ctx.reduced) {
            var rm = 8, r0 = 30, r = Math.max(2, r0 - (r0 - rm) * f);
            var rOut = rm + (r0 - rm) * (hw / TACK), rIn = Math.max(1, rm - (r0 - rm) * (hw / TACK));
            k.ring(g, rx, geo.cy, rm, r, rOut, rIn, C, since >= 0 && Math.abs(since - TACK) <= hw);
          } else {
            var cf = since < 0 ? 0 : since / TACK;
            k.counted(g, rx - 20, geo.cy, cf >= 1 ? 4 : cf >= 0.75 ? 3 : cf >= 0.5 ? 2 : cf >= 0.25 ? 1 : 0, C);
          }
          k.text(g, strokes + (strokes === 1 ? " stroke" : " strokes"), 8, 9, C, { size: 12 });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
