// Bench minigame: Brew, keep the simmer (revamp plan §9.3, UI plan §9).
//
// A heat needle drifts on a brass dial; keep it in the notch by feeding or banking the
// fire. For an infusion (`tuning.infusion`) the notch sits low, so the oils are not boiled
// away; for a decoction it sits high and the game runs 20% longer. Past 0.9 is a rolling
// boil, cross-hatched with a saw edge.
//
// Input:
//   - Mouse or touch: press to feed, release to bank.
//   - Keyboard: hold Up (or Space) to feed; hold Down to bank harder.
//   - Steady mode: toggles instead of holds (a click or Space flips feeding on and off; Up
//     feeds, Down banks), and the drift and the fire's response are halved (UI plan §9).
// The fire answers fast enough that no single hold lasts long: fed flat out the needle
// crosses the whole notch in about half a second, so the rhythm is short presses.
//
// Scoring: time with the needle in the notch earns full credit, within 0.05 of it 40%, and
// nothing while boiling. The score is that credit over the game's length, so it climbs as
// the player holds the simmer. The needle starts in the notch: generous from the first frame.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};

  defs.brew = {
    id: "brew",
    name: "Brew",
    first: "Feed the fire to keep the needle in the notch.",
    hint: function (steady) {
      return steady ? "Space or click to feed or bank" : "Hold Space or click to feed";
    },
    KEYS: ["Space", "ArrowUp", "ArrowDown"],
    // Held outside Steady mode: feeding is pressing. In Steady mode every one is a toggle.
    HOLDS: ["Space", "ArrowUp", "ArrowDown", "pointer"],
    HOLDS_STEADY: [],
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var infusion = !!ctx.tuning.infusion;
      var centre = infusion ? 0.36 : 0.64;
      var half = k.clamp(0.1 * ctx.win, 0.07, 0.2);
      var band = [centre - half, centre + half];
      var duration = ctx.seconds * (infusion ? 1 : 1.2);
      var up = 0.42 * ctx.speed, fall = 0.3 * ctx.speed, wander = 0.1 * ctx.speed;
      var drift = k.drift(ctx.rng() * 10);
      var heat = centre, acc = 0, t = 0;
      var holders = {}, feeding = false, banking = false, wasIn = true, wasBoil = false, lastEvt = -1;
      var geo = { cx: 0, cy: 0, R: 0 };

      function sync() { feeding = !!(holders.Space || holders.ArrowUp || holders.pointer); banking = !!holders.ArrowDown; }
      function tip() { var a = Math.PI + heat * Math.PI; return [geo.cx + Math.cos(a) * (geo.R - 6), geo.cy + Math.sin(a) * (geo.R - 6)]; }

      return {
        duration: duration,
        tick: function (dt, now) {
          t = now;
          var v = feeding ? up : -fall * (banking ? 2 : 1);
          v += wander * drift(t);
          heat = k.clamp(heat + v * dt, 0, 1);
          var inBand = heat >= band[0] && heat <= band[1];
          var near = !inBand && (heat >= band[0] - 0.05 && heat <= band[1] + 0.05);
          var boil = heat >= 0.9;
          acc += dt * (boil ? 0 : inBand ? 1 : near ? 0.4 : 0);
          // Sound and stage cues on the change only, at most one every 0.4s.
          if (t - lastEvt > 0.4) {
            var p = tip();
            if (inBand && !wasIn) { ctx.hit(0.5, p[0], p[1], "steam"); lastEvt = t; }
            else if (!inBand && wasIn) { ctx.miss(); lastEvt = t; }
            else if (boil && !wasBoil) { ctx.miss(); lastEvt = t; }
          }
          wasIn = inBand; wasBoil = boil;
        },
        down: function (inp) {
          var key = inp.src === "pointer" ? "pointer" : inp.key;
          if (ctx.steady) {
            // Steady mode: one press per change. Up feeds, Down banks, Space and a click flip.
            if (key === "ArrowUp") feeding = true;
            else if (key === "ArrowDown") feeding = false;
            else feeding = !feeding;
            return true;
          }
          holders[key] = true; sync();
          return true;
        },
        up: function (inp) {
          var key = inp.src === "pointer" ? "pointer" : inp.key;
          delete holders[key]; sync();
          return true;
        },
        state: function () { return { heat: heat, band: band.slice(), boil: heat >= 0.9 }; },
        score: function () { return acc / duration; },
        done: function () { return false; },
        draw: function (g, W, H) {
          geo.R = Math.min(86, H - 30); geo.cx = 18 + geo.R; geo.cy = H - 14;
          var cx = geo.cx, cy = geo.cy, R = geo.R;
          var A = function (h) { return Math.PI + h * Math.PI; };
          g.save();
          g.strokeStyle = C.edge; g.lineWidth = 1.5;
          g.beginPath(); g.arc(cx, cy, R, Math.PI, 2 * Math.PI); g.stroke();
          g.strokeStyle = C.dim; g.lineWidth = 1;
          for (var i = 0; i <= 10; i++) {
            var a = A(i / 10), r0 = R - (i % 5 ? 5 : 9);
            g.beginPath(); g.moveTo(cx + Math.cos(a) * r0, cy + Math.sin(a) * r0);
            g.lineTo(cx + Math.cos(a) * R, cy + Math.sin(a) * R); g.stroke();
          }
          g.restore();
          k.dialBand(g, cx, cy, R - 18, R, A(band[0]), A(band[1]), C.goldDim, { notches: true, notchColour: C.gold });
          k.dialBand(g, cx, cy, R - 18, R, A(0.9), A(1), C.alarm, { cross: true, jagged: true, gap: 4 });
          var p = tip();
          g.save();
          g.strokeStyle = C.ink; g.lineWidth = 2;
          g.beginPath(); g.moveTo(cx, cy); g.lineTo(p[0], p[1]); g.stroke();
          g.restore();
          k.diamond(g, p[0], p[1], 4, C.ink, null);
          g.beginPath(); g.arc(cx, cy, 5, 0, Math.PI * 2); g.fillStyle = C.goldDim; g.fill();
          // The fire, and its state in words.
          var fx = cx + R + 42;
          if (fx + 30 < W) {
            k.flame(g, fx, H - 40, 26, feeding, C);
            k.text(g, feeding ? "Feeding" : "Banked", fx, H - 22, C, { align: "center", colour: feeding ? C.gold : C.dim });
            k.text(g, infusion ? "Keep it low" : "Keep it high", fx, 18, C, { align: "center" });
          }
        }
      };
    }
  };
})();
