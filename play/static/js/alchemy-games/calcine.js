// Alchemy minigame: Calcine, hold the crucible in the calcining band (alchemy UI plan §9,
// revamp plan §7).
//
// Calcination is strong heat short of melting: the charge darkens, then whitens into a powdery
// calx (alchemy prior art §5, "drive to a white calx without melting"). Too cool and nothing
// happens; too hot and it fuses into slag, which no amount of care afterwards takes back.
//
// The FIRE is the frame's (33-bench-games.js FLAME): the player feeds it and the crucible's heat
// follows with a lag, never coasting past where the fire is taking it (no momentum: Stardew's
// fishing bar was the warning). The server's bands are the gauge's words ("dull, calcining,
// fusing", rules/alchemist.py tuning_for), the target outlined, fusing cross-hatched.
//
// Input: hold Space, Up or the mouse on the strip to feed the fire; let go to bank it; Down
// damps it to cool faster. Steady mode (UI plan §9): the heat drifts at half speed (the frame
// doubles the lag) and every hold is a toggle: a press lights the fire, the next banks it.
//
// Scoring: the calx fills only while the heat is in the band (8 pips, the "whiteness meter"),
// at full credit in the band's inner half, falling to 0.6 at its rim. The score is the share
// filled times the mean credit, times what the slag left: every second in the fusing band
// turns 40% of the charge to slag. Holding the fire on from the start runs through the band
// in under three seconds and then fuses everything (0); leaving it banked never calcines (0).
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var PIPS = 8, SLAG_RATE = 0.4;
  // Content colours: the charge's own, dark ore to white calx; slag a dull glassy brown.
  var DARK = [74, 64, 58], WHITE = [236, 232, 222], SLAG = [92, 52, 36];

  function blend(a, b, t) { return a.map(function (v, i) { return v + (b[i] - v) * t; }); }
  function mix(a, b, t) { return "rgb(" + blend(a, b, t).map(Math.round).join(",") + ")"; }

  defs.calcine = {
    id: "calcine",
    track: "alchemy",
    name: "Calcine",
    first: "Feed the fire to hold the heat in the calcining band until the calx is white.",
    hint: function (steady) {
      return steady ? "Space or Up lights the fire; again banks it" : "Hold Space or Up to feed the fire; Down damps it";
    },
    KEYS: ["Space", "ArrowUp", "ArrowDown"],
    HOLDS: ["Space", "ArrowUp", "ArrowDown"],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "alchemy.hit", miss: "alchemy.miss", feed: "alchemy.feed", bank: "alchemy.bank" },
    FLAME: { label: "Crucible heat", lo: 200, hi: 1100, start: 300, target: "calcining",
      bands: [{ name: "dull", lo: 200, hi: 600 }, { name: "calcining", lo: 600, hi: 900 },
        { name: "fusing", lo: 900, hi: 1100 }] },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, heat = ctx.heat;
      var need = ctx.seconds * 0.65;                       // in-band seconds to a white calx
      var duration = ctx.seconds * (ctx.steady ? 2.2 : 1.6);
      var work = 0, qsum = 0, inT = 0, slag = 0, pips = 0, wasBurn = false, t = 0;
      var geo = { cx: 40, cy: 40 };

      var cuedAt = -1;
      // The fire fed or banked is heard once as it changes (lane U5's alchemy.feed and .bank);
      // the burner the frame holds carries the roar in between.
      function feed(on) {
        // At most one every quarter second: a hand pulsing the fire answers each pulse, a bot
        // flicking it every frame (84 cues in 5.7s, measured live) does not stutter the bus.
        if (on !== heat.fed && t - cuedAt >= 0.25) { cuedAt = t; ctx.cue(on ? "feed" : "bank"); }
        heat.fed = on; if (on) heat.damp = false;
      }
      return {
        duration: duration,
        tick: function (dt, now) {
          t = now;
          if (work >= 1) return;
          var q = heat.credit(0.5, 0.6);
          if (q > 0) { work = Math.min(1, work + dt / need); qsum += q * dt; inT += dt; }
          var burn = heat.status() === "burn";
          if (burn) slag = Math.min(1, slag + SLAG_RATE * dt);
          if (burn && !wasBurn) ctx.miss();
          wasBurn = burn;
          var p = Math.floor(work * PIPS + 1e-9);
          if (p > pips) { pips = p; ctx.hit(inT ? qsum / inT : 1, geo.cx, geo.cy - 10, "steam"); }
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          if (inp.src === "key" && inp.key === "ArrowDown") {
            if (ctx.steady) { feed(false); heat.damp = !heat.damp; } else { feed(false); heat.damp = true; }
            return true;
          }
          if (ctx.steady) feed(!heat.fed); else feed(true);
          return true;
        },
        up: function (inp) {
          if (inp.src === "key" && inp.key === "ArrowDown") heat.damp = false;
          else feed(false);
        },
        hint: function () {
          if (slag > 0 && heat.status() !== "burn") return "Slag: " + Math.round(slag * 100) + "% of the charge is lost";
          return heat.inBand() ? "Calcining: hold it here" : null;
        },
        state: function () {
          return { heat_c: heat.c, in_band: heat.inBand(), status: heat.status(), fed: heat.fed, damp: heat.damp,
            work: work, slag: slag, quality: inT ? qsum / inT : 0, band: heat.band.slice(), done: work >= 1 };
        },
        score: function () { return Math.min(1, work) * (inT ? qsum / inT : 0) * (1 - slag); },
        done: function () { return work >= 1 || slag >= 1; },
        draw: function (g, W, H) {
          geo.cx = 46; geo.cy = H / 2 + 4;
          var lit = heat.fed;
          // The crucible: a tapered pot on its fire, the charge inside in its own colour.
          k.flame(g, geo.cx, H - 6, 26, lit, C);
          g.save();
          g.beginPath();
          g.moveTo(geo.cx - 22, geo.cy - 22); g.lineTo(geo.cx + 22, geo.cy - 22);
          g.lineTo(geo.cx + 15, geo.cy + 14); g.lineTo(geo.cx - 15, geo.cy + 14); g.closePath();
          g.strokeStyle = C.goldDim; g.lineWidth = 1.5; g.stroke();
          g.beginPath();
          g.moveTo(geo.cx - 19, geo.cy - 6); g.lineTo(geo.cx + 19, geo.cy - 6);
          g.lineTo(geo.cx + 15, geo.cy + 12); g.lineTo(geo.cx - 15, geo.cy + 12); g.closePath();
          g.fillStyle = mix(blend(DARK, WHITE, work), SLAG, slag);
          g.fill();
          g.restore();
          // The fire's state in words beneath the meters, so feeding reads without the flame.
          var x = geo.cx + 46;
          k.text(g, ctx.steady ? (lit ? "Fire lit" : heat.damp ? "Fire damped" : "Fire banked")
            : (lit ? "Feeding the fire" : heat.damp ? "Damping" : "Fire banked"), x, 14, C,
            { size: 13, colour: lit ? C.gold : C.dim });
          // The calx: eight pips, each filling as the charge whitens.
          k.text(g, "Calx", x, geo.cy - 4, C, { size: 13 });
          var gap = Math.max(14, Math.min(22, (W - x - 60) / PIPS));
          for (var i = 0; i < PIPS; i++) {
            var f = k.clamp(work * PIPS - i, 0, 1);
            k.pip(g, x + 44 + gap * i, geo.cy - 4, 5, f > 0 ? f : null, C, false);
          }
          if (slag > 0.005) {
            k.text(g, "Slag " + Math.round(slag * 100) + "%", x, geo.cy + 16, C, { size: 13, colour: C.alarm });
          }
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
