// Bench minigame: Infuse (oil), low and slow (revamp plan §9.3, UI plan §9).
//
// The crock cools in its ashes. Add embers to keep the heat between the cold line and the
// scorch line while the infusion fills (the brass thread along the top of the meter). The
// band is wider and the drift gentler than Brew's: an oil wants patience, not reflexes.
// Past the scorch line the oil darkens; that zone is cross-hatched with a saw edge.
//
// Input: a click or Up (or Space) adds embers; Down rakes some out. Every input is a single
// press, in both modes, so this game holds nothing. Steady mode: the drift and the cooling
// are halved and the band is x1.6 wider (through ctx).
//
// Scoring: the fill (it rises only while the heat is in the band) less 0.18 for every second
// spent scorching. The game ends when the infusion is full, or at 1.5x its length.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};

  defs.infuse = {
    id: "infuse",
    name: "Infuse",
    first: "Add embers to keep the heat between cold and scorch.",
    hint: function () { return "Click or Up for embers. Down rakes them out"; },
    KEYS: ["Space", "ArrowUp", "ArrowDown"],
    HOLDS: [],
    HOLDS_STEADY: [],
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var centre = 0.5, half = k.clamp(0.14 * ctx.win, 0.1, 0.26);
      var cold = centre - half, scorch = centre + half;
      var fillTime = 0.8 * ctx.seconds / ctx.baseSpeed;
      var cool = 0.07 * ctx.speed, wander = 0.05 * ctx.speed;
      var drift = k.drift(ctx.rng() * 10);
      var heat = centre - half * 0.6, fill = 0, scorchT = 0, t = 0;
      var pulses = [];            // embers settle in over 0.35s rather than jumping the needle
      var wasScorch = false;
      var geo = { x0: 20, x1: 300, y: 70 };

      function hx(h) { return geo.x0 + (geo.x1 - geo.x0) * h; }
      function add(amount) { pulses.push({ left: 0.35, rate: amount / 0.35 }); }

      return {
        duration: ctx.seconds * 1.5 / ctx.baseSpeed,
        progress: function (now) { return Math.max(fill, now / (ctx.seconds * 1.5 / ctx.baseSpeed)); },
        tick: function (dt, now) {
          t = now;
          var v = -cool + wander * drift(t);
          for (var i = pulses.length - 1; i >= 0; i--) {
            var p = pulses[i], d = Math.min(dt, p.left);
            v += p.rate * d / Math.max(dt, 1e-6);
            p.left -= d;
            if (p.left <= 0) pulses.splice(i, 1);
          }
          heat = k.clamp(heat + v * dt, 0, 1);
          if (heat >= cold && heat <= scorch) fill = Math.min(1, fill + dt / fillTime);
          var sc = heat > scorch;
          if (sc) scorchT += dt;
          if (sc && !wasScorch) ctx.miss();
          wasScorch = sc;
        },
        down: function (inp) {
          if (inp.src === "key" && inp.key === "ArrowDown") { add(-0.1); return true; }
          if (inp.src === "pointer" && !inp.inside) return true;
          add(0.12);
          if (heat < scorch) ctx.hit(0.3, hx(heat), geo.y - 14, "spark");
          return true;
        },
        state: function () { return { heat: heat, cold: cold, scorch: scorch, fill: fill }; },
        score: function () { return k.clamp(fill - 0.18 * scorchT, 0, 1); },
        done: function () { return fill >= 1; },
        draw: function (g, W, H) {
          geo.x0 = 24; geo.x1 = Math.max(180, Math.min(W - 24, 24 + 460)); geo.y = H / 2 + 8;
          var y = geo.y, x0 = geo.x0, x1 = geo.x1;
          // The fill thread: a brass line with no track, a diamond at its head, a notch at full.
          var fy = 16, fx = x0 + (x1 - x0) * fill;
          k.text(g, "Infusion", x0, fy + 12, C, { size: 13 });
          if (fill > 0) {
            g.save(); g.strokeStyle = C.gold; g.lineWidth = 2;
            g.beginPath(); g.moveTo(x0, fy); g.lineTo(fx, fy); g.stroke(); g.restore();
            k.diamond(g, fx, fy, 3, C.gold, null);
          }
          k.notch(g, x1, fy + 5, -Math.PI / 2, 4, C.goldDim);
          // The scale: cold sparse-hatched, the band hatched and notched, scorch cross-hatched.
          k.barBand(g, x0, y - 10, hx(cold) - x0, 20, C.ash, { gap: 9 });
          k.barBand(g, hx(cold), y - 10, hx(scorch) - hx(cold), 20, C.goldDim, { gap: 5 });
          k.barBand(g, hx(scorch), y - 10, x1 - hx(scorch), 20, C.alarm, { cross: true, gap: 4 });
          g.save(); g.strokeStyle = C.alarm; g.lineWidth = 1.2;
          g.beginPath();
          for (var sx = hx(scorch), j = 0; sx <= x1; sx += 5, j++) {
            if (j) g.lineTo(sx, y + 10 + (j % 2 ? 4 : 0)); else g.moveTo(sx, y + 10);
          }
          g.stroke(); g.restore();
          k.notch(g, hx(cold), y - 12, Math.PI / 2, 5, C.gold);
          k.notch(g, hx(scorch), y - 12, Math.PI / 2, 5, C.alarm);
          k.text(g, "Cold", hx(cold), y + 24, C, { size: 13, align: "center" });
          k.text(g, "Scorch", hx(scorch), y + 24, C, { size: 13, align: "center" });
          // The heat marker: a line through the scale and a pointer above it.
          var mx = hx(heat);
          g.save(); g.strokeStyle = C.ink; g.lineWidth = 2;
          g.beginPath(); g.moveTo(mx, y - 14); g.lineTo(mx, y + 14); g.stroke(); g.restore();
          k.notch(g, mx, y - 15, Math.PI / 2, 6, C.ink);
          // Embers still settling in, as small sparks under the scale.
          for (var e = 0; e < pulses.length; e++) {
            if (pulses[e].rate <= 0) continue;
            k.diamond(g, x0 + 6 + e * 9, H - 10, 2.5, C.candle, null);
          }
        }
      };
    }
  };
})();
