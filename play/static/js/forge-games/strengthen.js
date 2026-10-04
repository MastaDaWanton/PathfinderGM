// Forge minigame: Strengthen, two bars become one (blacksmithing UI plan §9, revamp plan §11).
//
// Two bars stacked, welded at white-yellow heat without burning. The band is narrow and sits
// just under the burning zone: 1,200 to 1,300 °C, with burning from 1,315 °C, Chapman's
// white (prior art §3.1: sparks from the steel mean it is burning; overheating grows the grain
// and decarburisation cannot be undone). The hearth runs hotter than the band, so a bar out
// of the fire is burning for its first moments: wait for the needle to come down out of the
// hatched zone, then strike. That patience is the game. The frame owns the heat: the gauge
// cross-hatches the burning zone with a saw edge, and the hint says "Burning: let it cool".
//
// Input: Space or a click to strike; R to reheat. Nothing is held. Steady mode: the band
// x1.5 (the HEAT's steadyBand, applied by the frame, never into the burning zone) and the
// frame's halved cooling.
//
// Scoring: `welds` blows in band are needed (4 by default). Each earns the heat's quality
// (1 in the band's inner half, 0.6 at its rim). A blow while burning is a burn: it earns
// nothing for that weld and takes a quarter of a weld off the total, so striking in the white
// is worse than waiting. A blow below the band does not weld and costs only the blow. The
// score is the sum over the welds needed.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};

  defs.strengthen = {
    id: "strengthen",
    track: "forge",
    name: "Strengthen",
    first: "Strike in the narrow band. Wait out the burning white first.",
    hint: function () { return "Space or click to strike"; },
    KEYS: ["Space", "R"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "forge.weld", miss: "forge.strike.miss", reheat: "forge.bellows" },
    HEAT: { label: "Welding heat", band: [1200, 1300], burn_c: 1315, hearth_c: 1345, cool_rate: 45,
      steadyBand: 1.5 },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, heat = ctx.heat;
      var need = Math.round(k.clamp(+ctx.tuning.welds || 4, 2, 6));
      var res = [], burns = 0, cold = 0, t = 0, mark = { ok: null, at: -1 };
      var geo = { cx: 70, cy: 40 };

      function strike() {
        if (res.length >= need || heat.reheating > 0) return;
        var s = heat.status();
        if (s === "burn") { burns++; mark = { ok: false, at: t }; ctx.miss(); heat.add(-15); return; }
        if (s === "cold") { cold++; mark = { ok: false, at: t }; ctx.miss(); return; }
        var q = s === "in" ? heat.quality(0.5, 0.6) : 0.5;
        res.push(q); mark = { ok: true, at: t };
        ctx.hit(q, geo.cx, geo.cy, "spark");
        heat.add(-35);
      }

      return {
        duration: ctx.seconds * 1.5 + 2,
        tick: function (dt, now) { t = now; },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          strike();
          return true;
        },
        progress: function () { return res.length / need; },
        state: function () {
          return { welds: res.length, need: need, burns: burns, hot_c: heat.c, in_band: heat.inBand(),
            burning: heat.status() === "burn", reheating: heat.reheating > 0 };
        },
        score: function () {
          var s = 0;
          res.forEach(function (q) { s += q; });
          return Math.max(0, s - 0.25 * burns) / need;
        },
        done: function () { return res.length >= need; },
        draw: function (g, W, H) {
          geo.cy = H / 2 - 2;
          // Two bars stacked; the seam between them closes as the welds add up.
          var w = Math.min(120, W * 0.32), x = 16, gap = 6 * (1 - res.length / need);
          g.save();
          g.strokeStyle = C.goldDim; g.lineWidth = 1.2;
          g.strokeRect(x + 0.5, geo.cy - 10 - gap / 2, w, 9);
          g.strokeRect(x + 0.5, geo.cy + 1 + gap / 2, w, 9);
          g.restore();
          geo.cx = x + w / 2;
          if (mark.at >= 0 && t - mark.at < 0.5) {
            if (mark.ok) k.diamond(g, geo.cx, geo.cy, 6, C.gold, null);
            else {
              g.save(); g.strokeStyle = C.alarm; g.lineWidth = 2; g.beginPath();
              g.moveTo(geo.cx - 6, geo.cy - 6); g.lineTo(geo.cx + 6, geo.cy + 6);
              g.moveTo(geo.cx + 6, geo.cy - 6); g.lineTo(geo.cx - 6, geo.cy + 6); g.stroke(); g.restore();
            }
          }
          var x0 = x + w + 26, step = Math.min(26, (W - x0 - 10) / need);
          for (var i = 0; i < need; i++) k.pip(g, x0 + step * i + step / 2, geo.cy - 6, 6, i < res.length ? res[i] : null, C, i === res.length);
          k.text(g, burns ? "Burnt " + burns : "Weld " + Math.min(res.length + 1, need) + " of " + need,
            x0 + step / 2 - 6, geo.cy + 16, C, { size: 13, colour: burns ? C.alarm : C.dim });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
