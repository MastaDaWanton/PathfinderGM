// Forge minigame: Fold, weld at yellow heat (blacksmithing UI plan §9, revamp plan §11).
//
// Fold the bar, bring it to welding heat, strike to weld the fold shut; the layer count
// doubles with each good weld. Steel forge-welds "at a bright yellow heat" (prior art §3.1,
// Wikipedia's Forge welding), so the band is the gauge's yellow, 1,093 to 1,258 °C. A strike
// below it is a cold shut: the fold does not take. A strike above it, near white, burns the
// surface and the weld takes only half. Each weld costs the bar heat (the hammer and the
// fold take it), so most folds need a trip back to the fire: R, or the Reheat button. The
// frame owns the heat, its gauge and the "Reheat: R" hint.
//
// Input: Space or a click to strike; R to reheat. Nothing is held. Steady mode: cooling x0.5
// (the frame), as the UI plan's column asks; nothing else changes, since the band is already
// wide and the game is not timed by a beat.
//
// Scoring per fold: the heat's quality at the blow (1 in the band's inner 60%, falling to 0.5
// at its rim; `heat.quality`), halved above the band, 0 for a cold shut. The first blow on a
// fold decides it; folding the bar over takes half a second in which a blow does nothing. The
// score is the sum over the folds, so it climbs as the player welds.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};

  defs.fold = {
    id: "fold",
    track: "forge",
    name: "Fold",
    first: "Strike at welding heat to weld each fold. R puts it back in the fire.",
    hint: function () { return "Space or click to weld"; },
    KEYS: ["Space", "R"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "forge.weld", miss: "forge.strike.miss", reheat: "forge.bellows" },
    HEAT: { label: "Welding heat", band: [1093, 1258], hearth_c: 1290, cool_rate: 55 },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, heat = ctx.heat;
      var folds = Math.round(k.clamp(+ctx.tuning.folds || 4, 3, 6));
      var res = [];
      for (var i = 0; i < folds; i++) res.push(null);
      var folding = 0, t = 0, last = { i: -1, ok: false };
      var geo = { x: 20, y: 40, w: 140, h: 14 };

      function current() { for (var j = 0; j < folds; j++) if (res[j] === null) return j; return folds; }
      function welds() { var n = 0; res.forEach(function (q) { if (typeof q === "number" && q > 0) n++; }); return n; }

      function strike() {
        var i = current();
        if (i >= folds || folding > 0 || heat.reheating > 0) return;
        var s = heat.status();
        if (s === "cold") {
          res[i] = 0; last = { i: i, ok: false }; ctx.miss();
        } else {
          var q = s === "in" ? heat.quality(0.6, 0.5) : 0.5;
          res[i] = q; last = { i: i, ok: true };
          ctx.hit(q, geo.x + geo.w / 2, geo.y, "spark");
        }
        heat.add(-90);
        folding = 0.5;
      }

      return {
        duration: ctx.seconds * 1.6 + 2,
        tick: function (dt, now) { t = now; if (folding > 0) folding = Math.max(0, folding - dt); },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          strike();
          return true;
        },
        hint: function () { return folding > 0 ? "Folding" : null; },
        progress: function () { return current() / folds; },
        state: function () {
          return { fold: Math.min(current(), folds), folds: folds, layers: Math.pow(2, welds() + 1),
            folding: folding > 0, hot_c: heat.c, in_band: heat.inBand(), reheating: heat.reheating > 0 };
        },
        score: function () {
          var s = 0;
          res.forEach(function (q) { if (typeof q === "number") s += q; });
          return s / folds;
        },
        done: function () { return current() >= folds && folding <= 0; },
        draw: function (g, W, H) {
          geo.y = H / 2 - 4;
          geo.w = Math.min(160, W * 0.42);
          // The bar, its layers drawn as lines: more welds, more lines (a pattern, not a hue).
          var n = Math.min(16, Math.pow(2, welds() + 1)), bx = geo.x, by = geo.y - geo.h / 2;
          g.save();
          g.strokeStyle = C.goldDim; g.lineWidth = 1.2;
          g.strokeRect(bx + 0.5, by + 0.5, geo.w, geo.h);
          g.strokeStyle = C.dim; g.lineWidth = 1;
          for (var L = 1; L < n; L++) {
            var ly = by + geo.h * L / n;
            g.beginPath(); g.moveTo(bx + 2, ly); g.lineTo(bx + geo.w - 2, ly); g.stroke();
          }
          if (folding > 0) {
            // The fold: the bar's far half turning over, shown as an arc at its end.
            g.strokeStyle = C.gold;
            g.beginPath(); g.arc(bx + geo.w, geo.y, geo.h * 0.8, -Math.PI / 2, Math.PI / 2); g.stroke();
          }
          g.restore();
          var x0 = bx + geo.w + 26, gap = Math.min(26, (W - x0 - 10) / folds);
          for (var f = 0; f < folds; f++) k.pip(g, x0 + gap * f + gap / 2, geo.y - 6, 6, res[f], C, f === current());
          k.text(g, "Layers " + Math.pow(2, welds() + 1), x0 + gap / 2 - 6, geo.y + 16, C, { size: 13 });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
