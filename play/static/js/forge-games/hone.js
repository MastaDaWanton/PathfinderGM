// Forge minigame: Hone, hold the angle (blacksmithing UI plan §9, revamp plan §11).
//
// The edge on the whetstone: keep the blade at its angle while it passes along the stone. The
// angle wanders (a slow drift, three sines, never per-frame noise, so it can be read and
// answered); hold it inside the band for the whole pass. Four passes (`tuning.passes`).
//
// Input:
//   - Mouse or touch: press on the stone and drag along it, left to right. The pointer's height
//     sets the angle, around the drift: drawing the line steady against the wander is the game.
//     The pass ends when the drag reaches the far end, not on release, so it plays the same in
//     Steady mode (where the frame never hands a game the release).
//   - Keyboard: hold Left or Right to tip the angle against the drift; Space starts a pass,
//     which runs along the stone by itself in about a second.
//   - Steady mode (UI plan §9): the angle band x1.6 (`ctx.band(1.6)`), and Left and Right
//     are presses that each tip the angle a step, never holds.
//
// Scoring per pass: the share of the pass spent in the band, with 40% credit within 1.5° of
// it. The score is the sum over the passes.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};

  defs.hone = {
    id: "hone",
    track: "forge",
    name: "Hone",
    first: "Hold the edge inside the band while it passes along the stone.",
    hint: function (steady) {
      return steady ? "Left and Right tip the angle, Space passes" : "Hold Left or Right to steady it, Space passes. Or drag";
    },
    KEYS: ["ArrowLeft", "ArrowRight", "Space"],
    HOLDS: ["ArrowLeft", "ArrowRight", "pointer"],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "forge.grind", miss: "forge.strike.miss" },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var aim = 20, half = 3 * ctx.band(1.6);                // degrees
      var band = [aim - half, aim + half];
      var passes = Math.round(k.clamp(+ctx.tuning.passes || 4, 2, 6));
      var drift = k.drift(ctx.rng() * 10);
      var wander = 6 * ctx.baseSpeed;                        // degrees/s at the drift's peak
      var TURN = 14, STEP = 1.5, PASS_S = 1.0;
      var angle = aim, left = false, right = false, t = 0;
      var res = [], passing = false, along = 0, inBand = 0, timed = 0, src = "", pause = 0, offset = 0;
      var geo = { x0: 30, x1: 260, y: 40, H: 88 };

      function account(dt) {
        timed += dt;
        var d = angle < band[0] ? band[0] - angle : angle > band[1] ? angle - band[1] : 0;
        inBand += dt * (d === 0 ? 1 : d <= 1.5 ? 0.4 : 0);
      }
      function endPass() {
        var q = timed > 0 ? inBand / timed : 0;
        res.push(q);
        if (q >= 0.5) ctx.hit(q, geo.x1, geo.y, "spark"); else ctx.miss();
        passing = false; along = 0; inBand = 0; timed = 0; pause = 0.3;
      }
      function startPass(how) {
        if (passing || pause > 0 || res.length >= passes) return;
        passing = true; src = how; along = 0; inBand = 0; timed = 0;
      }
      function fromY(y) { return aim + (geo.y - y) / (geo.H / 2) * 14; }

      return {
        duration: ctx.seconds * 1.4 + 1,
        tick: function (dt, now) {
          t = now;
          if (pause > 0) pause = Math.max(0, pause - dt);
          offset += wander * drift(t) * dt;
          if (src !== "pointer" || !passing) {
            angle += wander * drift(t) * dt + ((right ? TURN : 0) - (left ? TURN : 0)) * dt;
            angle = k.clamp(angle, aim - 14, aim + 14);
          }
          if (passing && src === "key") {
            along += dt / PASS_S;
            account(dt);
            if (along >= 1) endPass();
          }
        },
        down: function (inp) {
          if (inp.src === "pointer") {
            if (!inp.inside) return false;
            offset = 0;
            angle = fromY(inp.y);
            if (inp.x <= geo.x0 + (geo.x1 - geo.x0) * 0.35) startPass("pointer");
            return true;
          }
          if (inp.key === "Space") { startPass("key"); return true; }
          if (ctx.steady) { angle += inp.key === "ArrowRight" ? STEP : -STEP; return true; }
          if (inp.key === "ArrowRight") right = true; else left = true;
          return true;
        },
        up: function (inp) {
          if (inp.src === "key") { if (inp.key === "ArrowRight") right = false; if (inp.key === "ArrowLeft") left = false; }
          return true;
        },
        move: function (inp) {
          if (!inp.down) return;
          angle = k.clamp(fromY(inp.y) + offset, aim - 14, aim + 14);
          if (!passing || src !== "pointer") return;
          var u = k.clamp((inp.x - geo.x0) / (geo.x1 - geo.x0), 0, 1);
          if (u > along) { account(Math.min(0.1, (u - along) * PASS_S)); along = u; }
          if (along >= 0.98) endPass();
        },
        progress: function () { return (res.length + (passing ? along : 0)) / passes; },
        state: function () {
          return { angle: angle, band: band.slice(), passing: passing, along: along,
            pass: Math.min(res.length + 1, passes), passes: passes };
        },
        score: function () { var s = 0; res.forEach(function (q) { s += q; }); return s / passes; },
        done: function () { return res.length >= passes; },
        draw: function (g, W, H) {
          geo.H = H; geo.y = H / 2; geo.x0 = 30; geo.x1 = Math.max(150, W - 100);
          // The stone, and the angle band on a small dial at its right: the blade drawn as a
          // line at its angle, the band a hatched wedge with notches.
          g.save(); g.strokeStyle = C.goldDim; g.lineWidth = 1.2;
          g.strokeRect(geo.x0 + 0.5, geo.y + 6.5, geo.x1 - geo.x0, 8); g.restore();
          if (passing) {
            var ax = geo.x0 + (geo.x1 - geo.x0) * along;
            g.save(); g.strokeStyle = C.gold; g.lineWidth = 2;
            g.beginPath(); g.moveTo(geo.x0, geo.y + 6); g.lineTo(ax, geo.y + 6); g.stroke(); g.restore();
          }
          var dx = geo.x1 + 46, dy = geo.y + 8, R = Math.min(36, H / 2 - 4);
          var A = function (deg) { return Math.PI + (deg - aim + 14) / 28 * (Math.PI / 2); };
          g.save(); g.strokeStyle = C.edge; g.beginPath(); g.arc(dx, dy, R, Math.PI, 1.5 * Math.PI); g.stroke(); g.restore();
          k.dialBand(g, dx, dy, R - 12, R, A(band[0]), A(band[1]), C.goldDim, { notches: true, notchColour: C.gold });
          var a = A(angle);
          g.save(); g.strokeStyle = C.ink; g.lineWidth = 2;
          g.beginPath(); g.moveTo(dx, dy); g.lineTo(dx + Math.cos(a) * (R + 2), dy + Math.sin(a) * (R + 2)); g.stroke(); g.restore();
          k.text(g, Math.round(angle) + "°", dx + 6, dy - 6, C, { size: 13, colour: C.ink });
          for (var i = 0; i < passes; i++) k.pip(g, geo.x0 + 8 + i * 20, geo.y - 18, 5, i < res.length ? res[i] : null, C, i === res.length);
          // The edge line: where the pointer really is, the blade's line at its angle.
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) {
            var la = (angle - aim) * Math.PI / 180;
            g.save(); g.strokeStyle = C.gold; g.lineWidth = 1.5;
            g.beginPath(); g.moveTo(p.x - Math.cos(la) * 14, p.y + Math.sin(la) * 14);
            g.lineTo(p.x + Math.cos(la) * 14, p.y - Math.sin(la) * 14); g.stroke(); g.restore();
            k.reticle(g, p.x, p.y, C, p.down);
          }
        }
      };
    }
  };
})();
