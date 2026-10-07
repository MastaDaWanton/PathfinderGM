// Alchemy minigame: Filter, pour at the rate the cloth can take (alchemy UI plan §9, revamp
// plan §7).
//
// The solution goes onto the cloth in the funnel; the filtrate runs clear below and the solid
// stays on the cloth. Pour too slowly and almost nothing comes through before the time runs
// out; pour too fast and the funnel overflows round the cloth, which is the one way to spoil a
// filtration. The pour rate is the frame's REACTION gauge read from the server's `pour`
// ({band, start}; `from: "pour"`): while the player pours it climbs, and it falls back when
// they stop. Holding the pour on climbs straight through the band and over the brim.
//
// Input: hold Space or the mouse on the strip to pour; let go to stop. Steady mode (UI plan §9):
// the pour is a toggle (press to pour, press to stop), it rises and falls at 60% of the speed,
// and the band x1.6.
//
// Scoring: the filtrate (8 pips) fills only while the rate is in the band, at full credit in its
// inner 60%, 0.6 at its rim. The score is the share filtered times the mean credit, less 0.15
// for every overflow.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var PIPS = 8, SPILL = 0.15, POUR = 90;

  defs.filter = {
    id: "filter",
    track: "alchemy",
    name: "Filter",
    first: "Pour so the rate stays in its band. Too fast and the funnel overflows.",
    hint: function (steady) { return steady ? "Space or click starts and stops the pour" : "Hold Space or the mouse to pour"; },
    KEYS: ["Space"],
    HOLDS: ["Space"],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "alchemy.drip", miss: "alchemy.spill", pour: "alchemy.pour" },
    REACTION: { from: "pour", label: "Pour", band: [30, 65], rise: 0, settle: 45, flare_at: 82, start: 0,
      steadyBand: 1.6, steadySettle: 0.6,
      words: ["trickle", "pouring", "too fast", "overflowing"],
      say: { low: "Trickle: pour faster", high: "Too fast: ease off", flare: "Overflowing: stop pouring" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, R = ctx.react;
      var rate = POUR * (ctx.steady ? 0.6 : 1);
      var need = ctx.seconds * 0.65, duration = ctx.seconds * (ctx.steady ? 2.4 : 1.7);
      var work = 0, qsum = 0, inT = 0, pouring = false, t = 0, pips = 0, flares = 0;
      var geo = { cx: 40, cy: 40 };

      return {
        duration: duration,
        tick: function (dt, now) {
          t = now;
          if (pouring && work < 1) R.v = Math.min(100, R.v + rate * dt);
          if (R.flares > flares) { flares = R.flares; ctx.miss(); }
          if (work >= 1) { pouring = false; return; }
          var q = R.credit();
          if (q > 0) { work = Math.min(1, work + dt / need); qsum += q * dt; inT += dt; }
          var p = Math.floor(work * PIPS + 1e-9);
          if (p > pips) { pips = p; ctx.hit(inT ? qsum / inT : 1, geo.cx, geo.cy + 20, "steam"); }
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          var was = pouring;
          pouring = ctx.steady ? !pouring : true;
          if (pouring && !was) ctx.cue("pour", { level: work });
          return true;
        },
        up: function () { pouring = false; },
        hint: function () {
          if (work >= 1) return null;
          return R.inBand() ? "Pouring well: hold this rate" : null;
        },
        state: function () {
          return { rate: R.v, band: R.band.slice(), flare_at: R.flare, status: R.status(), pouring: pouring,
            work: work, quality: inT ? qsum / inT : 0, flares: R.flares };
        },
        score: function () { return Math.max(0, Math.min(1, work) * (inT ? qsum / inT : 0) - SPILL * R.flares); },
        done: function () { return work >= 1; },
        draw: function (g, W, H) {
          geo.cx = 42; geo.cy = H / 2 - 6;
          // The funnel with its cloth, and the receiving glass below; the stream drawn while
          // pouring, thicker as the rate climbs.
          g.save();
          g.strokeStyle = C.goldDim; g.lineWidth = 1.5;
          g.beginPath();
          g.moveTo(geo.cx - 24, geo.cy - 18); g.lineTo(geo.cx + 24, geo.cy - 18);
          g.lineTo(geo.cx + 4, geo.cy + 8); g.lineTo(geo.cx + 4, geo.cy + 18);
          g.moveTo(geo.cx - 24, geo.cy - 18); g.lineTo(geo.cx - 4, geo.cy + 8); g.lineTo(geo.cx - 4, geo.cy + 18);
          g.stroke();
          g.strokeRect(geo.cx - 14, geo.cy + 22, 28, H - geo.cy - 26);
          if (pouring) {
            g.strokeStyle = C.ink; g.lineWidth = 1 + 3 * R.v / 100;
            g.beginPath(); g.moveTo(geo.cx - 30, 2); g.lineTo(geo.cx - 8, geo.cy - 14); g.stroke();
          }
          g.restore();
          var x = geo.cx + 46;
          k.text(g, pouring ? "Pouring" : "Not pouring", x, 12, C, { size: 13, colour: pouring ? C.gold : C.dim });
          k.text(g, "Filtrate", x, geo.cy + 10, C, { size: 13 });
          var gap = Math.max(14, Math.min(22, (W - x - 74) / PIPS));
          for (var i = 0; i < PIPS; i++) {
            var f = k.clamp(work * PIPS - i, 0, 1);
            k.pip(g, x + 62 + gap * i, geo.cy + 10, 5, f > 0 ? f : null, C, false);
          }
          if (R.flares) k.text(g, "Overflowed " + R.flares + (R.flares === 1 ? " time" : " times"), x, geo.cy + 30, C,
            { size: 12, colour: C.alarm });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
