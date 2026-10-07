// Alchemy minigame: React, drop by drop (alchemy UI plan §9, revamp plan §7).
//
// A titration's discipline: add the reagent in single drops as the reaction nears its working
// point, and wait to see each one take before the next, because the colour "lingers longer" as
// the end nears and a hurried hand overshoots (University of Wisconsin general chemistry lab,
// "Using an indicator during a titration"; ACS inChemistry, "Know your lab techniques:
// titration"). The gauge is the frame's REACTION: each drop adds `rise`, but it BLOOMS over about
// a third of a second, and while it does the gauge draws a hollow mark where it will land. So a
// player who drops again before looking is warned by the gauge itself; the overshoot is theirs.
//
// Keep the reaction in its band until it completes (the work pips fill only in the band). Over
// the flare line it boils over: the hint says "let it settle" in words, the stage shows a small
// flare, and the run loses a little. A minigame's overshoot never triggers the mishap; that is
// the roll's alone (plan §8.2).
//
// Input: Space or a click, one drop each. Nothing is held. Steady mode (UI plan §9): the gauge
// settles x1.5 and the band x1.6.
//
// Scoring: the share of the reaction completed times the mean credit while in the band (full in
// its inner 60%, 0.6 at its rim), less 0.15 for every boil-over. Pressing as fast as possible
// boils it over at once; pressing nothing never starts it.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var PIPS = 8, BOIL = 0.15;

  defs.react = {
    id: "react",
    track: "alchemy",
    name: "React",
    first: "One drop at a time. Keep the reaction in its band until it completes. Do not hurry.",
    hint: function (steady) { return steady ? "Space or click: one drop" : "Space or click for one drop; watch where it lands"; },
    KEYS: ["Space"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "alchemy.bubble", miss: "alchemy.fizz", drop: "alchemy.drip" },
    REACTION: { label: "Reaction", band: [40, 72], rise: 14, settle: 5, flare_at: 90, start: 5, bloom: 0.35,
      steadyBand: 1.6, steadySettle: 1.5,
      words: ["calm", "working", "racing", "boiling over"],
      say: { low: "Calm: add a drop", high: "Racing: wait", flare: "Boiling over: let it settle" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, R = ctx.react;
      var need = ctx.seconds * 0.65, duration = ctx.seconds * (ctx.steady ? 2.4 : 1.8);
      var work = 0, qsum = 0, inT = 0, drops = 0, t = 0, pips = 0, flares = 0, lastDrop = -1;
      var geo = { cx: 40, cy: 40 };

      function drop() {
        if (work >= 1) return;
        drops++; lastDrop = t;
        R.add(R.rise);
        ctx.cue("drop");
      }

      return {
        duration: duration,
        tick: function (dt, now) {
          t = now;
          if (R.flares > flares) { flares = R.flares; ctx.miss(); }
          if (work >= 1) return;
          var q = R.credit();
          if (q > 0) { work = Math.min(1, work + dt / need); qsum += q * dt; inT += dt; }
          var p = Math.floor(work * PIPS + 1e-9);
          if (p > pips) { pips = p; ctx.hit(inT ? qsum / inT : 1, geo.cx, geo.cy, "steam"); }
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          drop();
          return true;
        },
        // While a drop is still blooming the gauge's own "Calm: add a drop" is exactly the advice
        // that overshoots (seen live: four quick drops, the needle at 35 and still rising, the
        // hint asking for a fifth), so the bloom speaks first.
        urgent: function () {
          if (work >= 1) return null;
          return R.pending > 0.5 ? "Wait for it to take" : null;
        },
        hint: function () {
          if (work >= 1) return null;
          return R.inBand() ? "Working: hold it here" : null;
        },
        state: function () {
          return { reaction: R.v, lands: R.lands(), pending: R.pending, band: R.band.slice(), flare_at: R.flare,
            rise: R.rise, settle: R.settle, status: R.status(), work: work, quality: inT ? qsum / inT : 0,
            drops: drops, flares: R.flares };
        },
        score: function () { return Math.max(0, Math.min(1, work) * (inT ? qsum / inT : 0) - BOIL * R.flares); },
        done: function () { return work >= 1; },
        draw: function (g, W, H) {
          geo.cx = 40; geo.cy = H / 2 + 8;
          // The dropper over a round flask; a drop shown falling for a moment after each press.
          g.save();
          g.strokeStyle = C.goldDim; g.lineWidth = 1.5;
          g.beginPath(); g.arc(geo.cx, geo.cy + 6, 18, 0, Math.PI * 2); g.stroke();
          g.beginPath(); g.moveTo(geo.cx - 3, 4); g.lineTo(geo.cx - 3, 18); g.lineTo(geo.cx, 24); g.lineTo(geo.cx + 3, 18); g.lineTo(geo.cx + 3, 4); g.stroke();
          g.restore();
          if (lastDrop >= 0 && t - lastDrop < 0.3 && !ctx.reduced) {
            var dy = 26 + (geo.cy - 14 - 26) * ((t - lastDrop) / 0.3);
            g.save(); g.fillStyle = C.ink; g.beginPath(); g.arc(geo.cx, dy, 2.2, 0, Math.PI * 2); g.fill(); g.restore();
          }
          var x = geo.cx + 44;
          k.text(g, "Done", x, geo.cy - 6, C, { size: 13 });
          var gap = Math.max(14, Math.min(22, (W - x - 64) / PIPS));
          for (var i = 0; i < PIPS; i++) {
            var f = k.clamp(work * PIPS - i, 0, 1);
            k.pip(g, x + 50 + gap * i, geo.cy - 6, 5, f > 0 ? f : null, C, false);
          }
          k.text(g, drops + (drops === 1 ? " drop" : " drops"), x, 12, C, { size: 12 });
          if (R.flares) k.text(g, "Boiled over " + R.flares + (R.flares === 1 ? " time" : " times"), x, geo.cy + 14, C,
            { size: 12, colour: C.alarm });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
