// Leather minigame: Harden, heat against time in the kettle (leather UI plan §9, revamp plan §11).
//
// Cuir bouilli: soaked vegetable-tanned leather is hardened in hot water. The sources disagree
// on the method (Waterer at 50 °C, Dobson at 70 °C, Etherington & Roberts a 20 to 120 second dip
// in boiling water) but share one trade: too little heat or time and it stays soft; too much and
// it shrinks and turns brittle. Jean Turner measured it: about 30 s in hot water left it 7/8 of
// its size, hard but flexible; about 40 s boiling left it 2/3, brittle (prior art §3.5, labelled
// there as our synthesis, not a sourced recipe). So the gauge is the water's heat in °C with the
// server's band and its boiling band cross-hatched, and the time thread is the seconds; a size
// meter beside the piece marks 7/8 and 2/3.
//
// The water heats over the fire as the game runs (Newton's law toward the boil, about a second
// to reach the band and four to leave it; the server's `drift` is the fire's flicker, ±°C).
// Space or a click dips the piece; Space or a click again lifts it, and the lift ends the game.
// The piece sets faster the hotter the water, and shrinks once the water is past 60 °C, faster
// still once it has set and is left in, fastest boiling. Steady mode (UI plan §9): the water
// heats at half the pace, the band x1.5; dip and lift are presses, never a hold.
//
// Scoring: how far it set (0 to 1), times its size: full at 0.86 of its size or better, falling
// to nothing at 2/3. Never dipped, nothing; dipped and lifted at once, nothing set.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var TAU = 2.3, GOOD = 0.86, BRITTLE = 0.67;

  defs["leather.harden"] = {
    id: "leather.harden",
    track: "leather",
    name: "Harden",
    first: "Dip the piece while the water is in the band; lift it the moment it has set.",
    hint: function () { return "Space or click dips; again lifts"; },
    KEYS: ["Space"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "leather.steam", miss: "leather.steam", dip: "leather.slosh" },
    BAND: { unit: "celsius", label: "Water", target: [50, 85], fail: [95, 100], value_start: 20,
      drift: 3, steadyBand: 1.5,
      words: { low: "cool", in: "setting", high: "hot", fail: "boiling" },
      say: { fail: "Boiling: it will shrink and crack" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, G = ctx.gauge;
      var tau = TAU / ctx.baseSpeed * (ctx.steady ? 2 : 1);
      var D = k.drift(ctx.rng() * 10), flick = G.drift * (ctx.steady ? 0.5 : 1);
      var water = G.v, dipped = false, lifted = false, set = 0, size = 1, inFor = 0, t = 0, dips = 0;
      var geo = { x: 40, y: 40 };

      function rate(c) { return c < 45 ? 0 : (c - 45) / 30; }
      function press() {
        if (lifted) return;
        if (!dipped) { dipped = true; dips++; ctx.cue("dip"); return; }
        lifted = true;
        var q = score();
        if (q > 0) ctx.hit(q, geo.x, geo.y, "steam"); else ctx.miss();
      }
      function sizeQ() { return size >= GOOD ? 1 : k.clamp((size - BRITTLE) / (GOOD - BRITTLE), 0, 1); }
      function score() { return k.clamp(Math.min(1, set) * sizeQ(), 0, 1); }

      return {
        duration: ctx.seconds * (ctx.steady ? 2.6 : 1.6),
        tick: function (dt, now) {
          t = now;
          water += (100 - water) * (1 - Math.exp(-dt / tau));
          G.v = k.clamp(water + flick * D(now), G.scale[0], G.scale[1]);
          if (!dipped || lifted) return;
          inFor += dt;
          var c = G.v;
          set = Math.min(1.5, set + rate(c) * dt);
          var shrink = c > 60 ? (c - 60) / 40 * 0.06 : 0;
          if (set >= 1) shrink += 0.12;
          if (G.status() === "fail") shrink += 0.3;
          size = Math.max(0.4, size - shrink * dt);
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          press();
          return true;
        },
        hint: function () {
          if (lifted) return null;
          if (!dipped) return G.status() === "low" ? "The water is warming" : "Dip it now";
          if (set >= 1) return "Set: lift it";
          return "In the water: " + inFor.toFixed(1) + " s";
        },
        state: function () {
          return { water: G.v, band: G.band.slice(), fail: G.fail, dipped: dipped, lifted: lifted, set: set,
            size: size, in_for: inFor, status: G.status() };
        },
        score: score,
        done: function () { return lifted; },
        draw: function (g, W, H) {
          geo.x = 46; geo.y = Math.round(H / 2 + 4);
          // The kettle: a pot on its fire, the water's surface, and the piece in or over it.
          var kx = geo.x - 26, ky = geo.y - 14, kw = 52, kh = 30;
          g.save(); g.strokeStyle = C.goldDim; g.lineWidth = 1.5;
          g.beginPath(); g.moveTo(kx, ky); g.lineTo(kx + 4, ky + kh); g.lineTo(kx + kw - 4, ky + kh); g.lineTo(kx + kw, ky); g.stroke();
          g.restore();
          k.barBand(g, kx + 4, ky + 8, kw - 8, kh - 9, C.goldDim, { gap: G.v > 85 ? 3 : 6 });
          var pw = 26 * size, ph = 9 * size, py = dipped && !lifted ? ky + 12 : ky - 16;
          g.save(); g.fillStyle = C.ink; g.globalAlpha = 0.25 + 0.6 * Math.min(1, set);
          g.fillRect(geo.x - pw / 2, py, pw, ph); g.globalAlpha = 1;
          g.strokeStyle = C.gold; g.lineWidth = 1.2; g.strokeRect(geo.x - pw / 2, py, pw, ph); g.restore();
          if (G.v > 60 && !ctx.reduced) k.flame(g, geo.x, ky - 18, 8 * Math.min(1, (G.v - 60) / 30), true, C);
          // Set and size, as two short rulers with their marks.
          var x = geo.x + 48, w = Math.max(70, Math.min(160, W - x - 16));
          var R = window.LeatherGames.ruler;
          k.text(g, set >= 1 ? "Set" : "Setting", x, 12, C, { size: 12, colour: set >= 1 ? C.ink : C.dim });
          R(k, g, x + 52, 12, w, Math.min(1, set), C, set >= 1 ? C.gold : C.dim);
          k.text(g, "Size", x, 32, C, { size: 12 });
          R(k, g, x + 52, 32, w, size, C, size >= GOOD ? C.gold : C.alarm);
          k.notch(g, x + 52 + w * 0.875, 27, Math.PI / 2, 4, C.gold);
          k.notch(g, x + 52 + w * BRITTLE, 27, Math.PI / 2, 4, C.alarm);
          k.text(g, "7/8", x + 52 + w * 0.875 - 8, 44, C, { size: 11 });
          k.text(g, "2/3", x + 52 + w * BRITTLE - 8, 44, C, { size: 11 });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
