// Forge minigame: Alloy, pour to the ratio (blacksmithing UI plan §9, revamp plan §11).
//
// Two crucibles pour into one: hold to pour the second metal into the first and release when
// the mix reaches the alloy's ratio. The ratio bar shows the second metal's share, with the
// alloy's window outlined; bronze is about 88 copper to 12 tin (the recipe's window is 8 to
// 19% tin in content/world-classes/blacksmith.json, and the game asks for the sweet middle of
// it, not the whole). The server may name the alloy's numbers in `tuning.ratio`
// {target, lo, hi, of: [first, second]} in percent of the second metal; without them the
// game pours bronze.
//
// The stream is not perfectly even: its flow wanders a little (a slow drift, never noise), so
// the pour is watched rather than counted. Three charges in turn (`tuning.charges`).
//
// Input: hold Space or the mouse button to pour; release to stop. A release with almost
// nothing poured is ignored, so a twitch does not spend a charge. Steady mode (UI plan §9):
// one press starts the pour and the next stops it (the frame never hands a Steady game a
// release), the pour at half speed (`ctx.speed`) and the window x1.5 (`ctx.band(1.5)`).
//
// Scoring per charge: 1 within the inner 40% of the window, falling to 0.4 at its edge,
// nothing outside it. Pouring on to twice the recipe's top spoils the charge, and so does
// leaving it unpoured for 3.5 seconds (7 in Steady mode). The score is
// the sum over the charges.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};

  defs.alloy = {
    id: "alloy",
    track: "forge",
    name: "Alloy",
    first: "Pour the second metal in. Stop when the mix reaches the outlined window.",
    hint: function (steady) { return steady ? "Space or click to pour, again to stop" : "Hold Space or the mouse to pour"; },
    KEYS: ["Space"],
    HOLDS: ["Space", "pointer"],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "forge.strike.hit", miss: "forge.strike.miss" },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var given = ctx.tuning.ratio || {};
      var lo = +given.lo > 0 ? +given.lo : 8, hi = +given.hi > lo ? +given.hi : 19;
      var target = +given.target > 0 ? k.clamp(+given.target, lo, hi) : Math.min(hi, Math.max(lo, 12));
      var names = Array.isArray(given.of) && given.of.length === 2 ? given.of : ["copper", "tin"];
      var w = Math.min(2.6 * ctx.band(1.5), (hi - lo) / 2 + 1);
      var win = [target - w, target + w];
      var top = hi * 2;                                       // where the charge is spoiled
      var rate = target / 1.5 * ctx.speed;                   // pp per second: ~1.5s to the target
      var drift = k.drift(ctx.rng() * 10);
      var charges = Math.round(k.clamp(+ctx.tuning.charges || 3, 1, 5));
      // A charge left unpoured for WAIT seconds is lost (the crucible skins over), so a
      // player who walks away is not held at the strip for half a minute.
      var WAIT = 3.5 / (ctx.steady ? 0.5 : 1), idle = 0;
      var res = [], share = 0, pouring = false, pause = 0, t = 0;

      function close() {
        pouring = false;
        if (share < 0.5) return;                              // a twitch, not a pour
        var d = Math.abs(share - target), inner = w * 0.4, q = 0;
        if (d <= inner) q = 1; else if (d <= w) q = 1 - 0.6 * ((d - inner) / (w - inner));
        res.push(q);
        if (q > 0) ctx.hit(q, 60, 30, "spark"); else ctx.miss();
        pause = 0.6;
      }

      return {
        duration: charges * (top / rate + 0.9) + 0.5,
        tick: function (dt, now) {
          t = now;
          if (pause > 0) { pause -= dt; if (pause <= 0) { pause = 0; share = 0; } return; }
          if (res.length >= charges) return;
          if (!pouring && share === 0) {
            idle += dt;
            if (idle > WAIT) { res.push(0); ctx.miss(); pause = 0.6; idle = 0; }
            return;
          }
          idle = 0;
          if (pouring) {
            share += rate * (1 + 0.25 * drift(t)) * dt;
            if (share >= top) { pouring = false; res.push(0); ctx.miss(); pause = 0.6; }
          }
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          if (res.length >= charges || pause > 0) return true;
          if (ctx.steady && pouring) close();
          else pouring = true;
          return true;
        },
        up: function () { if (pouring) close(); return true; },
        progress: function () { return res.length / charges; },
        state: function () {
          return { share: share, window: win.slice(), target: target, pouring: pouring, waiting: pause > 0,
            charge: Math.min(res.length + 1, charges), charges: charges, of: names.slice() };
        },
        score: function () { var s = 0; res.forEach(function (q) { s += q; }); return s / charges; },
        done: function () { return res.length >= charges && pause <= 0; },
        draw: function (g, W, H) {
          var x0 = 14, x1 = Math.max(x0 + 140, W - 70), by = H / 2 - 10, bh = 12;
          var span = top;
          var X = function (v) { return x0 + (x1 - x0) * k.clamp(v / span, 0, 1); };
          g.save(); g.strokeStyle = C.edge; g.strokeRect(x0 + 0.5, by + 0.5, x1 - x0, bh); g.restore();
          // The recipe's whole range, faintly hatched; the game's window, outlined and notched.
          k.barBand(g, X(lo), by + 1, X(hi) - X(lo), bh - 1, C.edge, { gap: 6 });
          k.barBand(g, X(win[0]), by - 3, X(win[1]) - X(win[0]), bh + 7, C.goldDim, { gap: 4 });
          k.notch(g, X(win[0]), by - 5, Math.PI / 2, 5, C.gold);
          k.notch(g, X(win[1]), by - 5, Math.PI / 2, 5, C.gold);
          // The pour so far: a filled line from the left, the stream's head a diamond.
          var sx = X(share);
          g.save(); g.strokeStyle = C.ink; g.lineWidth = 3;
          g.beginPath(); g.moveTo(x0 + 1, by + bh / 2); g.lineTo(sx, by + bh / 2); g.stroke(); g.restore();
          k.diamond(g, sx, by + bh / 2, pouring ? 5 : 4, pouring ? C.gold : C.ink, C.sunk, 1);
          var pct = Math.round(share);
          k.text(g, (100 - pct) + " " + names[0] + " / " + pct + " " + names[1], x0, by - 14, C, { size: 13, colour: C.ink });
          for (var i = 0; i < charges; i++) k.pip(g, x1 + 16 + i * 18, by + bh / 2, 5, i < res.length ? res[i] : null, C, i === res.length);
          k.text(g, pouring ? "Pouring" : "Held", x1 + 10, by + bh + 16, C, { size: 13, colour: pouring ? C.gold : C.dim });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
