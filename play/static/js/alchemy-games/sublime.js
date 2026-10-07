// Alchemy minigame: Sublime, grow the crust and scrape it (alchemy UI plan §9, revamp plan §7).
//
// Sal ammoniac does not melt: heated, it vaporises and re-forms as a crust on the cool upper
// wall of the aludel (alchemy prior art §5, the Jabirian "spirit"). Too cool and nothing rises;
// too hot and the charge melts instead, and a crust already grown slumps back into it. The
// sublimation band is NARROW (the server's 280 to 330 °C on a 150 to 450 scale), which is why
// this game's fire is the frame's FLAME with a Steady band of x1.5.
//
// While the heat is in the band the crust thickens (a meter of pips on the upper wall). When it
// is thick the scrape mark lights: scrape it (S, the Scrape button, or a click on the crust)
// before it falls back. A crust left past its window falls back into the charge (a miss) and
// starts again; a scrape at a crust still thin knocks it down too, so pressing S over and over
// gathers nothing: the crust never gets the chance to set.
//
// Input: hold Space, Up or the mouse on the aludel to feed the fire, Down to damp it, S to
// scrape. Steady mode (UI plan §9): the band x1.5, the crust grows at half speed and stays
// ready twice as long, and the fire is a toggle.
//
// Scoring: each of the three crusts is worth a third: the mean heat credit while it grew (full
// in the band's inner half, 0.6 at its rim) times the scrape's timing (full in the first 60% of
// the ready window, falling to 0.5 at its close). Melting or a fallen crust scores nothing.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var READY_S = 1.4, SLUMP = 0.8;

  defs.sublime = {
    id: "sublime",
    track: "alchemy",
    name: "Sublime",
    first: "Hold the narrow subliming band so a crust grows. Scrape it with S when it is thick.",
    hint: function (steady) {
      return steady ? "Space or Up lights or banks the fire; S scrapes" : "Hold Space or Up to feed the fire; S scrapes";
    },
    KEYS: ["Space", "ArrowUp", "ArrowDown", "S"],
    HOLDS: ["Space", "ArrowUp", "ArrowDown"],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "alchemy.scrape", miss: "alchemy.miss", ready: "alchemy.glass.tick", feed: "alchemy.feed",
      bank: "alchemy.bank" },
    FLAME: { label: "Aludel heat", lo: 150, hi: 450, start: 180, target: "subliming", steadyBand: 1.5,
      bands: [{ name: "cold", lo: 150, hi: 280 }, { name: "subliming", lo: 280, hi: 330 },
        { name: "melting", lo: 330, hi: 450 }] },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, heat = ctx.heat;
      var crusts = Math.round(k.clamp(+ctx.tuning.scrapes || 3, 2, 4));
      var grow = ctx.seconds * 0.65 / crusts * (ctx.steady ? 2 : 1);   // in-band seconds a crust
      var window_s = READY_S * ctx.band(2);                            // Steady: twice as long
      var duration = ctx.seconds * (ctx.steady ? 3 : 1.9);
      var crust = 0, qsum = 0, gt = 0, ready = -1, res = [], knocked = 0, t = 0, wasBurn = false;
      var geo = { crust: null };

      function scrape() {
        if (res.length >= crusts) return;
        if (ready < 0) {
          // Too thin to come away: it breaks and falls back. Nothing is scored, nothing kept.
          if (crust > 0.05) { crust = 0; qsum = 0; gt = 0; knocked++; ctx.miss(); }
          return;
        }
        var w = t - ready, inner = window_s * 0.6;
        var q = w <= inner ? 1 : 1 - 0.5 * ((w - inner) / (window_s - inner));
        res.push(q * (gt ? qsum / gt : 1));
        crust = 0; qsum = 0; gt = 0; ready = -1;
        ctx.hit(q, geo.crust ? geo.crust.x : null, geo.crust ? geo.crust.y : null, "grit", res.length - 1);
      }
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
          if (res.length >= crusts) return;
          var burn = heat.status() === "burn";
          if (ready < 0) {
            var q = heat.credit(0.5, 0.6);
            if (q > 0) { crust = Math.min(1, crust + dt / grow); qsum += q * dt; gt += dt; }
            if (burn) crust = Math.max(0, crust - SLUMP * dt);
            if (crust >= 1) { ready = t; ctx.cue("ready"); }
          } else {
            // Melting under a ready crust slumps it; past a quarter gone, or left past its
            // window, it falls back into the charge. A brush with the melting band survives:
            // measured 2026-10-07, a hand 0.2s late that killed the crust at the first degree
            // over scored 0.26 for heat that was in band nine tenths of the time.
            if (burn) crust = Math.max(0, crust - SLUMP * dt);
            if (crust < 0.75 || t - ready > window_s) {
              res.push(0); crust = 0; qsum = 0; gt = 0; ready = -1; ctx.miss(res.length - 1);
            }
          }
          if (burn && !wasBurn && ready < 0 && crust > 0) ctx.miss();
          wasBurn = burn;
        },
        down: function (inp) {
          if (inp.src === "key") {
            if (inp.key === "S") { scrape(); return true; }
            if (inp.key === "ArrowDown") { feed(false); heat.damp = ctx.steady ? !heat.damp : true; return true; }
            if (ctx.steady) feed(!heat.fed); else feed(true);
            return true;
          }
          if (!inp.inside) return false;
          var b = geo.crust;
          if (b && inp.x >= b.x - b.w / 2 - 8 && inp.x <= b.x + b.w / 2 + 8 && inp.y >= b.y - 12 && inp.y <= b.y + 12) {
            scrape(); return true;
          }
          if (ctx.steady) feed(!heat.fed); else feed(true);
          return true;
        },
        up: function (inp) {
          if (inp.src === "key" && inp.key === "ArrowDown") { heat.damp = false; return; }
          if (inp.src === "key" && inp.key === "S") return;
          feed(false);
        },
        button: { label: "Scrape", press: scrape },
        urgent: function () {
          if (ready >= 0) return "The crust is thick: scrape it (S)";
          return null;
        },
        hint: function () {
          if (res.length >= crusts) return null;
          return heat.inBand() ? "Subliming: the crust is growing" : null;
        },
        progress: function () { return t / duration; },
        state: function () {
          return { heat_c: heat.c, in_band: heat.inBand(), status: heat.status(), fed: heat.fed, crust: crust,
            ready: ready >= 0, ready_for: ready >= 0 ? t - ready : 0, window_s: window_s, scraped: res.length,
            of: crusts, knocked: knocked, band: heat.band.slice(), crustAt: geo.crust };
        },
        score: function () {
          var s = 0;
          res.forEach(function (q) { s += q; });
          return s / crusts;
        },
        done: function () { return res.length >= crusts; },
        draw: function (g, W, H) {
          var cx = 44, top = 8, bot = H - 10;
          // The aludel: a tall pot; the charge at its foot, the crust on its cool upper wall.
          k.flame(g, cx, H - 2, 22, heat.fed, C);
          g.save();
          g.strokeStyle = C.goldDim; g.lineWidth = 1.5;
          g.strokeRect(cx - 18, top + 0.5, 36, bot - top - 10);
          g.fillStyle = C.ash; g.fillRect(cx - 16, bot - 22, 32, 10);
          g.restore();
          geo.crust = { x: cx, y: top + 14, w: 32 };
          // The crust: hatched in gold as it thickens, outlined and notched when it is ready.
          var ch = Math.max(1, 12 * crust);
          k.barBand(g, cx - 16, top + 8, 32, ch, ready >= 0 ? C.gold : C.goldDim, { gap: 3 });
          if (ready >= 0) {
            k.notch(g, cx + 22, top + 14, Math.PI, 6, C.gold);
            k.text(g, "Scrape now", cx + 30, top + 14, C, { size: 13, colour: C.gold });
          }
          var x = cx + 40 + (ready >= 0 ? 80 : 0);
          k.text(g, heat.fed ? (ctx.steady ? "Fire lit" : "Feeding the fire") : heat.damp ? "Damping" : "Fire banked",
            cx + 40, H - 28, C, { size: 13, colour: heat.fed ? C.gold : C.dim });
          // The crust's thickness and the scrapes: pips.
          var gx = Math.max(x, cx + 40), gap = 22;
          k.text(g, "Crust", gx, top + 36, C, { size: 12 });
          for (var i = 0; i < 4; i++) {
            var f = k.clamp(crust * 4 - i, 0, 1);
            k.pip(g, gx + 48 + 16 * i, top + 36, 4.5, f > 0 ? f : null, C, false);
          }
          for (var j = 0; j < crusts; j++) k.pip(g, gx + 140 + gap * j, top + 36, 5, j < res.length ? res[j] : null, C, j === res.length);
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
