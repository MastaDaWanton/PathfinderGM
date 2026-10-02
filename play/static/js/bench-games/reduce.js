// Bench minigame: Reduce, don't scorch it (revamp plan §9.3, UI plan §9).
//
// A pan's level falls toward a scored line, faster the hotter the fire. Keep the heat in the
// simmer notch (high, but under the scorch zone), then pull the pan off at the line. Left
// too long, the level drops past the line into the hatched crust zone and the reduction is
// burnt.
//
// Input:
//   - Mouse or touch: press for heat, release to let it fall; the "Pull off" button in the
//     strip takes the pan off.
//   - Keyboard: hold Up for heat, hold Down to cool faster, Space to pull off.
//   - Steady mode: toggles (a click flips the heat; Up turns it on, Down off), drift and
//     the fire's response halved, the line's window x1.6. The level still falls at the
//     same pace, so the game keeps its length.
//
// Scoring: 55% for the simmer (time in the notch against the expected cooking time, capped
// at 1), 45% for the pull (1 inside the line's window, falling with distance), less a
// crust penalty for time spent in the scorch zone. Pulled too early still pays the simmer
// already done.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};

  defs.reduce = {
    id: "reduce",
    name: "Reduce",
    first: "Keep the simmer in the notch, then pull it off at the line.",
    hint: function (steady) {
      return steady ? "Click or Up for heat. Space pulls it off" : "Hold click or Up for heat. Space pulls it off";
    },
    KEYS: ["Space", "ArrowUp", "ArrowDown"],
    HOLDS: ["ArrowUp", "ArrowDown", "pointer"],
    HOLDS_STEADY: [],
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var line = 0.3;
      var centre = 0.66, half = k.clamp(0.11 * ctx.win, 0.08, 0.2);
      var band = [centre - half, Math.min(0.88, centre + half)];
      var tol = 0.05 * ctx.win;
      var cook = 0.85 * ctx.seconds / ctx.baseSpeed;              // expected time to the line
      var rate = (1 - line) / (centre * cook);
      var up = 0.42 * ctx.speed, fall = 0.3 * ctx.speed, wander = 0.08 * ctx.speed;
      var drift = k.drift(ctx.rng() * 10);
      var heat = 0.6, level = 1, simmer = 0, crust = 0, t = 0;
      var holders = {}, feeding = false, banking = false;
      var pulled = false, pullQ = 0, burnt = false, wasIn = true, lastEvt = -1;
      var geo = { gx: 20, gw: 44, top: 12, bot: 108 };

      function sync() { feeding = !!(holders.ArrowUp || holders.pointer); banking = !!holders.ArrowDown; }
      function levelY(v) { return geo.bot - (geo.bot - geo.top) * v; }
      function pull() {
        if (pulled) return;
        pulled = true;
        var d = level - line;
        if (Math.abs(d) <= tol) pullQ = 1 - 0.3 * (Math.abs(d) / tol);
        else if (d > 0) pullQ = k.clamp(0.7 - (d - tol) * 4, 0, 0.7);
        else pullQ = k.clamp(0.7 - (-d - tol) * 6, 0, 0.7);
        if (pullQ >= 0.5) ctx.hit(pullQ, geo.gx + geo.gw / 2, levelY(level), "steam"); else ctx.miss();
      }

      var game = {
        duration: ctx.seconds * 1.8 / ctx.baseSpeed,
        button: { label: "Pull off", press: function () { pull(); } },
        tick: function (dt, now) {
          t = now;
          var v = feeding ? up : -fall * (banking ? 2 : 1);
          heat = k.clamp(heat + (v + wander * drift(t)) * dt, 0, 1);
          level = Math.max(0, level - rate * heat * dt);
          var inBand = heat >= band[0] && heat <= band[1];
          if (inBand) simmer += dt;
          if (heat >= 0.9) crust += dt;
          if (t - lastEvt > 0.4 && inBand !== wasIn) {
            if (inBand) ctx.hit(0.4, 150, 60, "steam"); else ctx.miss();
            lastEvt = t;
          }
          wasIn = inBand;
          if (level < line - tol * 2.5) { burnt = true; pull(); }
          // Out of time: the pan comes off where it is.
          if (t >= game.duration - 0.02) pull();
        },
        down: function (inp) {
          if (inp.src === "key" && inp.key === "Space") { pull(); return true; }
          var key = inp.src === "pointer" ? "pointer" : inp.key;
          if (ctx.steady) {
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
        state: function () { return { level: level, line: line, heat: heat }; },
        score: function () {
          return k.clamp(0.55 * Math.min(1, simmer / cook) + 0.45 * pullQ - 0.25 * crust, 0, 1);
        },
        done: function () { return pulled; },
        draw: function (g, W, H) {
          geo.top = 12; geo.bot = H - 12;
          var x = geo.gx, w = geo.gw, yL = levelY(level), yLine = levelY(line);
          // The burnt zone below the line's reach: cross-hatched, alarm.
          var yBurn = levelY(line - tol * 2.5);
          k.barBand(g, x, yBurn, w, geo.bot - yBurn, C.alarm, { cross: true, gap: 4 });
          // The liquid: horizontal rules below the surface, the surface in ink.
          g.save();
          g.beginPath(); g.rect(x, yL, w, geo.bot - yL); g.clip();
          g.strokeStyle = C.goldDim; g.lineWidth = 1;
          g.beginPath();
          for (var y = yL + 4; y < geo.bot; y += 5) { g.moveTo(x, y); g.lineTo(x + w, y); }
          g.stroke(); g.restore();
          g.save(); g.strokeStyle = C.ink; g.lineWidth = 2;
          g.beginPath(); g.moveTo(x, yL); g.lineTo(x + w, yL); g.stroke(); g.restore();
          // The pan wall.
          g.save(); g.strokeStyle = C.edge; g.lineWidth = 1.5;
          g.beginPath(); g.moveTo(x, geo.top); g.lineTo(x, geo.bot); g.lineTo(x + w, geo.bot); g.lineTo(x + w, geo.top); g.stroke();
          g.restore();
          // The line and its window: hatched, gold, a notch either side.
          k.barBand(g, x - 6, levelY(line + tol), w + 12, levelY(line - tol) - levelY(line + tol), C.goldDim, { gap: 4 });
          g.save(); g.strokeStyle = C.gold; g.lineWidth = 1.5;
          g.beginPath(); g.moveTo(x - 6, yLine); g.lineTo(x + w + 6, yLine); g.stroke(); g.restore();
          k.notch(g, x - 7, yLine, 0, 6, C.gold);
          k.notch(g, x + w + 7, yLine, Math.PI, 6, C.gold);
          k.text(g, "Line", x + w + 14, yLine, C, { size: 13 });
          // The heat dial.
          var R = Math.min(48, H / 2 - 6), cx = x + w + 70 + R, cy = H - 18;
          var A = function (h) { return Math.PI + h * Math.PI; };
          g.save(); g.strokeStyle = C.edge; g.lineWidth = 1.5;
          g.beginPath(); g.arc(cx, cy, R, Math.PI, 2 * Math.PI); g.stroke(); g.restore();
          k.dialBand(g, cx, cy, R - 12, R, A(band[0]), A(band[1]), C.goldDim, { gap: 4, notches: true, notchColour: C.gold });
          k.dialBand(g, cx, cy, R - 12, R, A(0.9), A(1), C.alarm, { cross: true, jagged: true, gap: 4 });
          var a = A(heat), px = cx + Math.cos(a) * (R - 4), py = cy + Math.sin(a) * (R - 4);
          g.save(); g.strokeStyle = C.ink; g.lineWidth = 2;
          g.beginPath(); g.moveTo(cx, cy); g.lineTo(px, py); g.stroke(); g.restore();
          k.diamond(g, px, py, 3.5, C.ink, null);
          var fx = cx + R + 36;
          if (fx + 26 < W) {
            k.flame(g, fx, H - 40, 22, feeding, C);
            k.text(g, burnt ? "Burnt" : pulled ? "Off the fire" : feeding ? "Heat on" : "Heat off", fx, H - 22, C,
              { align: "center", colour: burnt ? C.alarm : feeding ? C.gold : C.dim });
          }
        }
      };
      return game;
    }
  };
})();
