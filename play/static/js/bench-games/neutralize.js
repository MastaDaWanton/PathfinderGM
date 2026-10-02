// Bench minigame: Neutralize, titrate (revamp plan §9.3, UI plan §9).
//
// A volatility needle swings on a glass dial, sitting well over on the volatile side. Each
// drop of neutralizer moves where it settles toward the centre and calms its swing; past
// the centre the material weakens. Leave the needle settled in the safe notch. A drop given
// while the needle swings out toward "volatile" calms it more than one given on the swing
// back, so reading the swing is the skill, and counting drops is the risk. Every drop
// leaves a tick on the dial where it set the needle to settle.
//
// Input: a click or Space, one press per drop. Nothing is ever held. Steady mode: the needle
// settles twice as fast (UI plan §9), so each drop's effect is plain sooner.
//
// Scoring: where the needle is settling now. Inside the safe notch 0.75..1 by closeness to
// the centre; outside it falls away over half the dial. So the score is a live reading, not a
// running sum: it climbs as the drops bring the needle in and falls if one too many sends it
// past.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};

  defs.neutralize = {
    id: "neutralize",
    name: "Neutralize",
    first: "Add drops until the needle settles in the safe notch.",
    hint: function () { return "Space or click for each drop"; },
    KEYS: ["Space"],
    HOLDS: [],
    HOLDS_STEADY: [],
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var half = k.clamp(0.1 * ctx.win, 0.07, 0.24);
      var safe = [-half, half];
      var target = 0.6 + ctx.rng() * 0.25, off = target;
      var amp = 0.28, omega = Math.PI * 2 * 0.9 * ctx.baseSpeed, ph = ctx.rng() * Math.PI * 2;
      var tau = ctx.steady ? 0.275 : 0.55;
      var drops = 0, ticks = [], t = 0, needle = target;
      var geo = { cx: 0, cy: 0, R: 0 };

      function quality(v) {
        var d = Math.abs(v);
        return d <= half ? 1 - 0.25 * (d / half) : k.clamp(0.75 - (d - half) / 0.5, 0, 1);
      }
      function ang(v) { return Math.PI + (v + 1) / 2 * Math.PI; }

      return {
        duration: ctx.seconds / ctx.baseSpeed,
        tick: function (dt, now) {
          t = now;
          off += (target - off) * (1 - Math.exp(-dt / tau));
          amp *= Math.exp(-0.05 * dt);
          needle = k.clamp(off + amp * Math.sin(omega * t + ph), -1, 1);
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return true;
          var swing = amp > 0.001 ? k.clamp((needle - off) / amp, -1, 1) * 0.5 + 0.5 : 0.5;
          target -= 0.17 + 0.12 * swing;
          amp *= 0.72;
          drops++;
          ticks.push(target);
          var a = ang(k.clamp(target, -1, 1));
          var x = geo.cx + Math.cos(a) * geo.R, y = geo.cy + Math.sin(a) * geo.R;
          if (Math.abs(target) <= half) ctx.hit(quality(target), x, y, "steam");
          else if (target < -half) ctx.miss();   // past the centre: the material weakens
          else ctx.hit(0.25, x, y, "steam");
          return true;
        },
        state: function () { return { needle: needle, safe: safe.slice(), drops: drops }; },
        score: function () { return quality(target); },
        done: function () { return false; },
        draw: function (g, W, H) {
          // The hub sits higher than Brew's so "Weak" and "Volatile" fit under the dial's ends
          // instead of over its hatching.
          geo.R = Math.min(80, H - 40); geo.cx = 24 + geo.R; geo.cy = H - 24;
          var cx = geo.cx, cy = geo.cy, R = geo.R;
          g.save(); g.strokeStyle = C.edge; g.lineWidth = 1.5;
          g.beginPath(); g.arc(cx, cy, R, Math.PI, 2 * Math.PI); g.stroke(); g.restore();
          k.dialBand(g, cx, cy, R - 18, R, ang(-1), ang(-0.55), C.ash, { gap: 8 });
          k.dialBand(g, cx, cy, R - 18, R, ang(0.55), ang(1), C.alarm, { cross: true, jagged: true, gap: 4 });
          k.dialBand(g, cx, cy, R - 18, R, ang(safe[0]), ang(safe[1]), C.goldDim, { notches: true, notchColour: C.gold });
          k.text(g, "Weak", cx - R + 9, cy + 14, C, { size: 13, align: "center" });
          k.text(g, "Volatile", cx + R - 9, cy + 14, C, { size: 13, align: "center" });
          // Each drop's tick: where that drop set the needle to settle.
          g.save(); g.strokeStyle = C.gold; g.lineWidth = 1.2;
          ticks.forEach(function (v) {
            var a = ang(k.clamp(v, -1, 1));
            g.beginPath();
            g.moveTo(cx + Math.cos(a) * (R - 26), cy + Math.sin(a) * (R - 26));
            g.lineTo(cx + Math.cos(a) * (R - 20), cy + Math.sin(a) * (R - 20));
            g.stroke();
          });
          g.restore();
          var a = ang(needle), px = cx + Math.cos(a) * (R - 4), py = cy + Math.sin(a) * (R - 4);
          g.save(); g.strokeStyle = C.ink; g.lineWidth = 2;
          g.beginPath(); g.moveTo(cx, cy); g.lineTo(px, py); g.stroke(); g.restore();
          k.diamond(g, px, py, 4, C.ink, null);
          g.beginPath(); g.arc(cx, cy, 5, 0, Math.PI * 2); g.fillStyle = C.goldDim; g.fill();
          // The drops, as droplets: shape, then a count.
          var dx = cx + R + 28;
          if (dx + 40 < W) {
            for (var i = 0; i < Math.min(drops, 8); i++) {
              var x = dx + (i % 4) * 14, y = 40 + Math.floor(i / 4) * 22;
              g.save(); g.strokeStyle = C.gold; g.lineWidth = 1.3;
              g.beginPath(); g.moveTo(x, y - 8);
              g.quadraticCurveTo(x + 6, y, x, y + 4); g.quadraticCurveTo(x - 6, y, x, y - 8);
              g.stroke(); g.restore();
            }
            k.text(g, drops === 1 ? "1 drop" : drops + " drops", dx - 4, 96, C, { size: 13 });
          }
        }
      };
    }
  };
})();
