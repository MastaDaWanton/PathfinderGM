// Leather minigame: Flense, scrape the flesh away (leather UI plan §9, revamp plan §11).
//
// The hide lies over the fleshing beam, flesh side up, and the knife is drawn across it in
// strokes. The real variable is how hard the blade bears: too light and the flesh and fat stay
// on, too hard and it scores the hide or goes clean through (prior art §3.2: hides were scraped
// over a beam; §3.1: flaying cuts and scores are one of the grading standard's defect groups).
// The gauge is that pressure as a fraction of the hide's thickness, with the server's clean band
// and its "through" band; the hand sways (the server's `drift` is the sway: ±3x drift, half in
// Steady), so a stroke is timed as well as aimed: aimed at the band's middle, the needle still
// swings out past its rim, and the stroke waits for it to come back.
//
// Input: Up and Down nudge the pressure a step, or the pointer's place across the strip sets it;
// Space or a click strokes. Nothing is held. A stroke takes a third of a second, and a press
// while the knife is still moving keeps it moving (the stroke starts again), so mashing strokes
// nothing: the forge's lesson that the timing has to be asked each time (forge-games/finish.js).
// Steady mode (UI plan §9): the sway at half, the band x1.5.
//
// Scoring: six patches to clear. A clean stroke clears one and earns the gauge's quality (1 in
// the band's inner half, 0.6 at its rim); a deep stroke clears one for 0.3 (it scored the
// hide); a shallow stroke clears nothing; a stroke through the hide clears nothing and costs a
// quarter of a patch (the hole stays). The score is the sum over the six, less the holes.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var PATCHES = 6, HOLE = 0.25, STROKE = 0.32, DEEP = 0.3, SWAY = 3;

  defs["leather.flense"] = {
    id: "leather.flense",
    track: "leather",
    name: "Flense",
    first: "Scrape the flesh away. Keep the pressure in the clean band: too deep cuts through.",
    hint: function (steady) {
      return steady ? "Up, Down: pressure. Space: stroke" : "Up, Down or move: pressure. Space or click: stroke";
    },
    KEYS: ["Space", "ArrowUp", "ArrowDown"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "leather.scrape", miss: "leather.scrape", tear: "leather.tear" },
    BAND: { unit: "fraction", label: "", after: "of thickness", target: [0.25, 0.55],
      fail: [0.85, 1], value_start: 0.1, drift: 0.05, steadyBand: 1.5,
      words: { low: "shallow", in: "clean", high: "deep", fail: "through" },
      say: { low: "Shallow: press deeper", high: "Deep: ease off", fail: "Through the hide: ease off" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, G = ctx.gauge, L = window.LeatherGames;
      var S = L.steer(ctx, G, { step: 0.06, wander: G.drift * SWAY });
      var res = [], holes = 0, strokes = 0, busy = 0, t = 0, W = 300, last = null;
      var geo = { x0: 20, y: 30, w: 200 };

      function stroke() {
        if (res.length >= PATCHES) return;
        if (busy > 0) { busy = STROKE; return; }
        busy = STROKE; strokes++;
        var s = G.status(), x = geo.x0 + geo.w * (res.length + 0.5) / PATCHES;
        last = s;
        if (s === "in") { var q = G.quality(0.5, 0.6); res.push(q); ctx.hit(q, x, geo.y, "grit"); }
        else if (s === "high") { res.push(DEEP); ctx.hit(DEEP, x, geo.y, "grit"); }
        else if (s === "fail") { holes++; ctx.miss(); ctx.cue("tear"); }
        else ctx.miss();
      }

      return {
        duration: ctx.seconds * (ctx.steady ? 2.4 : 1.7),
        tick: function (dt, now) { t = now; busy = Math.max(0, busy - dt); S.tick(dt, now); },
        down: function (inp) {
          if (inp.src === "key") {
            if (inp.key === "ArrowUp") S.nudge(1);
            else if (inp.key === "ArrowDown") S.nudge(-1);
            else stroke();
            return true;
          }
          if (!inp.inside) return false;
          S.point(inp.x, W);
          stroke();
          return true;
        },
        move: function (inp) { if (inp.inside) S.point(inp.x, W); },
        hint: function () {
          if (last === "low" && busy > 0) return "Too light: nothing came away";
          if (last === "fail" && busy > 0) return "Through: that hole stays";
          return null;
        },
        state: function () {
          return { pressure: G.v, aim: S.aim, sway: S.sway, band: G.band.slice(), fail: G.fail,
            status: G.status(), cleared: res.length, patches: PATCHES, holes: holes, strokes: strokes,
            busy: busy, scale: G.scale.slice() };
        },
        score: function () {
          var s = 0; res.forEach(function (q) { s += q; });
          return Math.max(0, Math.min(1, s / PATCHES) - HOLE * holes);
        },
        done: function () { return res.length >= PATCHES; },
        draw: function (g, Wd, H) {
          W = Wd;
          geo.x0 = 18; geo.w = Math.max(80, Wd - 36); geo.y = Math.round(H * 0.45);
          // The hide in section over the beam: its thickness as a band, the flesh still on it
          // hatched (a patch at a time), the knife's edge at the pressure, holes cut through.
          var top = geo.y - 12, th = 22;
          g.save();
          g.strokeStyle = C.goldDim; g.lineWidth = 1.2;
          g.strokeRect(geo.x0 + 0.5, top + 0.5, geo.w - 1, th);
          g.restore();
          for (var i = 0; i < PATCHES; i++) {
            var px = geo.x0 + geo.w * i / PATCHES, pw = geo.w / PATCHES;
            if (i >= res.length) k.barBand(g, px + 1, top - 6, pw - 2, 6, C.goldDim, { gap: 4 });
            else if (res[i] === DEEP) k.notch(g, px + pw / 2, top + 4, Math.PI / 2, 4, C.alarm);
          }
          for (var h = 0; h < holes; h++) {
            var hx = geo.x0 + 10 + h * 14;
            g.save(); g.strokeStyle = C.alarm; g.lineWidth = 1.6;
            g.beginPath(); g.moveTo(hx - 4, top + th + 4); g.lineTo(hx + 4, top - 2); g.stroke(); g.restore();
          }
          // The edge: a line across the next patch at the depth the knife now bears.
          var nx = geo.x0 + geo.w * (Math.min(res.length, PATCHES - 1) + 0.5) / PATCHES;
          var dy = top + th * k.clamp((G.v - G.scale[0]) / (G.scale[1] - G.scale[0]), 0, 1);
          g.save(); g.strokeStyle = busy > 0 ? C.gold : C.ink; g.lineWidth = 2;
          g.beginPath(); g.moveTo(nx - 16, dy); g.lineTo(nx + 16, dy); g.stroke(); g.restore();
          k.text(g, res.length + " of " + PATCHES + " clear", geo.x0, 10, C, { size: 12 });
          if (holes) k.text(g, holes + (holes === 1 ? " hole" : " holes"), geo.x0 + 110, 10, C, { size: 12, colour: C.alarm });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
