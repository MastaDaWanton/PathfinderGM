// Bench minigame: Steep, pour to the line (revamp plan §9.3, UI plan §9).
//
// Two beats. First pour the spirit or vinegar into the jar and stop at the scored mark for
// this herb's ratio (top-ups allowed; an overfull jar cannot be poured back). When the
// pouring has stopped for a moment, the seal comes: a ring closes on the lid's mark, and
// one press on the beat twists it shut.
//
// Input:
//   - Mouse or touch, or Space: press to pour, release to stop; then one press for the seal.
//   - Steady mode: a press starts the pour and the next press stops it; the pour runs at
//     half speed, the seal's window is x1.6, and the jar waits longer before sealing.
//
// Scoring: 65% for the pour (1 inside the mark's window, falling with distance), 35% for
// the seal (as Grind scores a strike). The seal is never skipped: running out of pour time
// moves on to it.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};

  defs.steep = {
    id: "steep",
    name: "Steep",
    first: "Pour to the mark, then seal on the beat.",
    hint: function (steady) {
      return steady ? "Space or click to pour and stop, then to seal" : "Hold Space or click to pour. Press to seal";
    },
    KEYS: ["Space"],
    HOLDS: ["Space", "pointer"],
    HOLDS_STEADY: [],
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var mark = 0.55 + ctx.rng() * 0.2;
      var tolIn = 0.025 * ctx.win, tolOut = 0.12;
      var rate = 0.32 * ctx.speed;
      var settle = ctx.steady ? 1.5 : 0.9;
      var pourCap = ctx.seconds * 0.8 / ctx.speed;
      // The seal's beat: speed from the difficulty only (Steady changes its window, not its tempo).
      var T = 1.25 / ctx.baseSpeed, tm = 0.8 * T;
      var hw = Math.min(0.11 * ctx.win, T * 0.2 * 0.95);
      var fill = 0, pouring = false, idle = 0, poured = false, t = 0;
      var sealing = false, sealT0 = 0, sealQ = null, pourQ = 0;
      var geo = { jx: 24, jw: 46, top: 14, bot: 108, cx: 160, cy: 60, rm: 12, r0: 44 };

      function fillY(v) { return geo.bot - (geo.bot - geo.top) * v; }
      function startSeal() {
        if (sealing) return;
        pouring = false; sealing = true; sealT0 = t;
        var d = Math.abs(fill - mark);
        pourQ = d <= tolIn ? 1 - 0.2 * (d / tolIn) : k.clamp(0.8 - (d - tolIn) / tolOut * 0.8, 0, 0.8);
        if (pourQ >= 0.5) ctx.hit(pourQ, geo.jx + geo.jw / 2, fillY(fill), "steam"); else ctx.miss();
        ctx.tick();
      }
      function strike() {
        if (sealQ !== null) return;
        var err = (t - sealT0) - tm;
        if (Math.abs(err) <= hw) {
          var a = Math.abs(err), inner = hw * 0.4;
          sealQ = a <= inner ? 1 : 1 - 0.6 * ((a - inner) / (hw - inner));
          ctx.hit(sealQ, geo.cx, geo.cy, "spark");
        } else if (err > -3 * hw) {
          sealQ = 0; ctx.miss();
        }
      }

      return {
        duration: pourCap + settle + T + 0.5,
        progress: function (now) {
          if (sealing) return 0.75 + 0.25 * k.clamp((now - sealT0) / T, 0, 1);
          return 0.75 * k.clamp(fill / Math.max(mark, 0.01), 0, 1);
        },
        tick: function (dt, now) {
          t = now;
          if (!sealing) {
            if (pouring) { fill = Math.min(1, fill + rate * dt); idle = 0; poured = true; }
            else if (poured) idle += dt;
            if (fill >= 1 || (poured && idle >= settle) || t >= pourCap) startSeal();
          } else if (sealQ === null && t - sealT0 > tm + hw) {
            sealQ = 0; ctx.miss();
          }
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return true;
          if (sealing) { strike(); return true; }
          pouring = ctx.steady ? !pouring : true;
          return true;
        },
        up: function () {
          if (!sealing) pouring = false;
          return true;
        },
        state: function () {
          return { fill: fill, mark: mark, sealing: sealing, seal: sealing ? k.clamp((t - sealT0) / tm, 0, 1) : 0 };
        },
        score: function () { return k.clamp(0.65 * pourQ + 0.35 * (sealQ || 0), 0, 1); },
        done: function () { return sealQ !== null; },
        draw: function (g, W, H) {
          geo.top = 18; geo.bot = H - 10;
          var x = geo.jx, w = geo.jw;
          // The mark's window, hatched, with a notch either side; then the liquid; then the jar.
          var ya = fillY(mark + tolIn), yb = fillY(mark - tolIn);
          k.barBand(g, x - 6, ya, w + 12, Math.max(3, yb - ya), C.goldDim, { gap: 4 });
          var yF = fillY(fill);
          g.save();
          g.beginPath(); g.rect(x, yF, w, geo.bot - yF); g.clip();
          g.strokeStyle = C.goldDim; g.lineWidth = 1;
          g.beginPath();
          for (var y = yF + 4; y < geo.bot; y += 5) { g.moveTo(x, y); g.lineTo(x + w, y); }
          g.stroke(); g.restore();
          if (fill > 0) {
            g.save(); g.strokeStyle = C.ink; g.lineWidth = 2;
            g.beginPath(); g.moveTo(x, yF); g.lineTo(x + w, yF); g.stroke(); g.restore();
          }
          g.save(); g.strokeStyle = C.edge; g.lineWidth = 1.5;
          g.beginPath();
          g.moveTo(x + 10, geo.top - 8); g.lineTo(x + 10, geo.top); g.lineTo(x, geo.top + 6);
          g.lineTo(x, geo.bot); g.lineTo(x + w, geo.bot); g.lineTo(x + w, geo.top + 6);
          g.lineTo(x + w - 10, geo.top); g.lineTo(x + w - 10, geo.top - 8);
          g.stroke(); g.restore();
          var yM = fillY(mark);
          g.save(); g.strokeStyle = C.gold; g.lineWidth = 1.5;
          g.beginPath(); g.moveTo(x - 6, yM); g.lineTo(x + w + 6, yM); g.stroke(); g.restore();
          k.notch(g, x - 7, yM, 0, 6, C.gold);
          k.notch(g, x + w + 7, yM, Math.PI, 6, C.gold);
          // The stream while pouring.
          if (pouring) {
            g.save(); g.strokeStyle = C.ink; g.lineWidth = 2;
            g.beginPath(); g.moveTo(x + w / 2, 0); g.lineTo(x + w / 2, yF); g.stroke(); g.restore();
          }
          // The seal: a ring closing on the lid's mark once pouring is done.
          geo.cx = x + w + 70; geo.cy = H / 2; geo.r0 = Math.min(44, H / 2 - 8);
          var tb = sealing ? t - sealT0 : 0;
          var rad = function (v) { return geo.r0 - (geo.r0 - geo.rm) * (v / tm); };
          if (sealing) {
            k.ring(g, geo.cx, geo.cy, geo.rm, Math.max(1, rad(tb)), rad(tm - hw), Math.max(1, rad(tm + hw)), C,
              sealQ === null && Math.abs(tb - tm) <= hw);
            if (sealQ !== null) k.pip(g, geo.cx, geo.cy, 7, sealQ > 0 ? sealQ : "miss", C, false);
          } else {
            g.save(); g.setLineDash([3, 4]); g.strokeStyle = C.goldDim; g.lineWidth = 1;
            g.beginPath(); g.arc(geo.cx, geo.cy, geo.rm, 0, Math.PI * 2); g.stroke(); g.restore();
          }
          var lx = geo.cx + geo.r0 + 18;
          if (lx + 60 < W) {
            k.text(g, sealing ? "Seal on the beat" : pouring ? "Pouring" : "Pour to the line", lx, H / 2, C,
              { colour: pouring ? C.gold : C.dim });
          }
        }
      };
    }
  };
})();
