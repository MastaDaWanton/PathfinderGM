// Forge minigame: Smelt, pump and tap (blacksmithing UI plan §9, revamp plan §11).
//
// Pump the bellows to hold the furnace in the smelting band, and tap the slag when it is
// ready. A bloomery never melts the iron: it makes a spongy bloom from which the slag runs
// (prior art §3.6), at around 1,150 to 1,300 °C. Too cold and no bloom forms; too hot and the
// iron starts taking up carbon and running to brittle cast iron, which is why the band has a
// top. The gauge here is the FURNACE's heat, not the work's, so there is no R: pumping is
// how the heat comes back, and the hint says so in words ("Too cold. Pump: Space").
//
// Slag gathers only while the furnace is in band. When it is ready a tap mark lights and
// stays open for a generous window; tap inside it. A window missed lets the slag freeze back
// into the bloom (a miss) and it starts gathering again.
//
// Input: Space or a click on the strip pumps once (a press, never a hold); T or the Tap
// button taps. Steady mode (UI plan §9): the heat drifts at half speed (the frame halves the
// cooling) and pumping is a toggle: one press sets the bellows working steadily, the next
// stops them, so no player has to mash.
//
// Scoring: 60% is the time the furnace spent in band (full credit in it, 40% within 30 °C of
// it, as Brew credits a near miss), 40% the taps (1 in the first 60% of the tap window,
// falling to 0.5 at its close). Both climb as the player plays.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};

  defs.smelt = {
    id: "smelt",
    track: "forge",
    name: "Smelt",
    first: "Pump to keep the furnace in the band. Tap the slag when it is ready.",
    hint: function (steady) { return steady ? "Space to work the bellows, T to tap" : "Space or click to pump, T to tap"; },
    KEYS: ["Space", "T"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "forge.strike.hit", miss: "forge.strike.miss", pump: "forge.bellows" },
    HEAT: { label: "Furnace heat", band: [1150, 1300], hearth_c: 1300, cool_rate: 24, reheat: false,
      coldHint: "Too cold. Pump: Space", start_c: 1165 },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, heat = ctx.heat;
      var taps = Math.round(k.clamp(+ctx.tuning.taps || 2, 1, 4));
      var duration = ctx.seconds * 1.1;
      var fillTime = duration / (taps + 1.2);          // in-band seconds for one tap's slag
      var tw = 1.4 * ctx.band(1.6);                    // the tap window, seconds
      var PUMP = 38, FLOW = 70;                        // °C a pump adds; °C/s the steady bellows add
      var slag = 0, ready = -1, res = [], acc = 0, t = 0, pumping = false, pumped = 0, lastPump = -1;
      var geo = { x: 16, y: 30 };

      function tap() {
        if (res.length >= taps || ready < 0) return;   // nothing to tap: an early T is ignored
        var w = t - ready, inner = tw * 0.6;
        var q = w <= inner ? 1 : 1 - 0.5 * ((w - inner) / (tw - inner));
        res.push(q); ready = -1; slag = 0;
        ctx.hit(q, geo.x + 150, geo.y, "spark");
      }
      function pump() {
        if (ctx.steady) { pumping = !pumping; return; }
        heat.add(PUMP); pumped++; lastPump = t;
        ctx.cue("pump");
      }

      return {
        duration: duration,
        tick: function (dt, now) {
          t = now;
          if (pumping) heat.add(FLOW * dt);
          var s = heat.status();
          var near = Math.min(Math.abs(heat.c - heat.band[0]), Math.abs(heat.c - heat.band[1])) <= 30;
          acc += dt * (s === "in" ? 1 : near ? 0.4 : 0);
          if (res.length < taps) {
            if (ready < 0) {
              if (s === "in") slag += dt / fillTime;
              if (slag >= 1) { slag = 1; ready = t; ctx.tick(); }
            } else if (t - ready > tw) {
              res.push(0); ready = -1; slag = 0; ctx.miss();
            }
          }
        },
        down: function (inp) {
          if (inp.src === "key" && inp.key === "T") { tap(); return true; }
          if (inp.src === "pointer" && !inp.inside) return false;
          pump();
          return true;
        },
        button: { label: "Tap", press: function () { tap(); } },
        state: function () {
          return { furnace_c: heat.c, in_band: heat.inBand(), slag: slag, ready: ready >= 0,
            taps: res.length, of: taps, pumping: pumping, pumps: pumped };
        },
        score: function () {
          var s = 0;
          res.forEach(function (q) { s += q; });
          return 0.6 * (acc / duration) + 0.4 * (s / taps);
        },
        done: function () { return false; },
        draw: function (g, W, H) {
          geo.y = H / 2 - 4;
          // The bellows: a flame that stands tall for a moment after each pump (or while the
          // Steady bellows work), with its state in words beneath.
          var lit = pumping || (lastPump >= 0 && t - lastPump < 0.35);
          k.flame(g, geo.x + 22, geo.y + 14, 24, lit, C);
          k.text(g, ctx.steady ? (pumping ? "Bellows on" : "Bellows off") : "Bellows", geo.x + 22, geo.y + 28,
            C, { align: "center", colour: lit ? C.gold : C.dim });
          // The slag: a bar that fills while in band, its tap mark a notched band at the end.
          var bx = geo.x + 64, bw = Math.max(80, Math.min(180, W - bx - 90)), by = geo.y - 4;
          g.save(); g.strokeStyle = C.edge; g.lineWidth = 1; g.strokeRect(bx + 0.5, by + 0.5, bw, 8); g.restore();
          k.barBand(g, bx + 1, by + 1, Math.max(1, (bw - 2) * slag), 7, ready >= 0 ? C.gold : C.goldDim, { gap: 4 });
          var tx = bx + bw + 14;
          k.notch(g, tx, by + 4, Math.PI, 6, ready >= 0 ? C.gold : C.ash);
          k.text(g, ready >= 0 ? "Tap now" : "Slag", tx + 8, by + 4, C, { size: 13, colour: ready >= 0 ? C.gold : C.dim });
          geo.x2 = tx;
          var x0 = bx, gap = 22;
          for (var i = 0; i < taps; i++) k.pip(g, x0 + gap * i + 6, by + 24, 5, i < res.length ? res[i] : null, C, i === res.length);
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
