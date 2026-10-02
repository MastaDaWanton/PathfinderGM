// Bench minigame: Grind, the crush rhythm (revamp plan §9.3, UI plan §9).
//
// A ring closes on the strike mark; strike as it closes. Eight beats by default
// (`tuning.beats`, kept to 4..10). Hard parts (root, bark, seed and the like) beat slower
// and heavier, as the plan asks. The strip shows the ring, its window as a hatched band,
// and one pip per beat: filled brass on a hit (smaller for a weak one), struck through on a
// miss.
//
// Input: Space or a click, one press per beat. Nothing is ever held, in either mode; this is
// exactly the input Potion Craft's players got hand fatigue from when it was a held drag
// (devlog #14), so grind is a press game from the start. Steady mode: tempo x0.5 and window
// x1.6 (both through ctx).
//
// Scoring: each beat earns 1 inside the inner 40% of its window, falling to 0.4 at the
// window's edge; a miss earns 0. The score is the sum over all beats, so it climbs as the
// player plays and ends where the server reads it. A press well before the ring (more than
// three windows early) is ignored as a stray; a press just before the window is a miss for
// that beat, which is what stops mashing from scoring.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var HARD = ["root", "bark", "seed", "horn", "bone", "shell", "mineral", "scale"];

  defs.grind = {
    id: "grind",
    name: "Grind",
    first: "Strike as the ring closes on the mark.",
    hint: function () { return "Space or click"; },
    KEYS: ["Space"],
    // Inputs this game needs HELD. Empty in both modes: one press per beat.
    HOLDS: [],
    HOLDS_STEADY: [],
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var beats = Math.round(k.clamp(+ctx.tuning.beats || 8, 4, 10));
      var hard = HARD.indexOf(ctx.part) >= 0;
      var period = ((ctx.seconds - 0.4) / beats) * (hard ? 1.15 : 1) / ctx.speed;
      var markAt = 0.78;                       // where in the beat the ring meets the mark
      var tm = markAt * period;
      var hw = Math.min(0.105 * ctx.win, period * (1 - markAt) * 0.95);
      var res = [];                            // per beat: null, a quality 0..1, or "miss"
      for (var i = 0; i < beats; i++) res.push(null);
      var t = 0, flash = { beat: -1, ok: false };
      var geo = { cx: 58, cy: 60, rm: 13, r0: 50 };

      function beatAt(time) { return Math.floor(time / period); }
      function radius(tb) { return geo.r0 - (geo.r0 - geo.rm) * (tb / tm); }
      function resolved() { var n = 0; for (var i = 0; i < beats; i++) if (res[i] !== null) n++; return n; }

      function strike() {
        var i = beatAt(t);
        if (i >= beats || res[i] !== null) return;
        var err = (t - i * period) - tm;
        if (Math.abs(err) <= hw) {
          var a = Math.abs(err), inner = hw * 0.4;
          var q = a <= inner ? 1 : 1 - 0.6 * ((a - inner) / (hw - inner));
          res[i] = q;
          flash = { beat: i, ok: true };
          ctx.hit(q, geo.cx, geo.cy, "grit");
        } else if (err < -hw && err > -3 * hw) {
          res[i] = "miss";
          flash = { beat: i, ok: false };
          ctx.miss();
        }
        // Earlier than that: a stray press, ignored.
      }

      return {
        duration: beats * period + 0.15,
        tick: function (dt, now) {
          t = now;
          var cur = beatAt(t);
          for (var i = 0; i < beats; i++) {
            if (res[i] !== null) continue;
            var late = i < cur || (i === cur && (t - i * period) > tm + hw);
            if (late) { res[i] = "miss"; flash = { beat: i, ok: false }; ctx.miss(); }
          }
        },
        down: function () { strike(); return true; },
        state: function () {
          var i = Math.min(beatAt(t), beats - 1);
          return { ring: k.clamp((t - i * period) / tm, 0, 1), struck: res[i] !== null };
        },
        score: function () {
          var s = 0;
          res.forEach(function (q) { if (typeof q === "number") s += q; });
          return s / beats;
        },
        done: function () { return resolved() >= beats; },
        draw: function (g, W, H) {
          geo.cy = H / 2;
          geo.r0 = Math.min(50, H / 2 - 8);
          var i = Math.min(beatAt(t), beats - 1), tb = t - i * period;
          var r = radius(tb);
          var rOut = radius(tm - hw), rIn = Math.max(1, radius(tm + hw));
          var inWin = Math.abs(tb - tm) <= hw && res[i] === null;
          k.ring(g, geo.cx, geo.cy, geo.rm, Math.max(1, r), rOut, rIn, C, inWin);
          // The struck beat answers on the mark: a filled mark for a hit, a cross for a miss.
          if (flash.beat === i) {
            if (flash.ok) {
              g.beginPath(); g.arc(geo.cx, geo.cy, geo.rm - 3, 0, Math.PI * 2);
              g.fillStyle = C.gold; g.fill();
            } else {
              g.save(); g.strokeStyle = C.alarm; g.lineWidth = 2;
              g.beginPath();
              g.moveTo(geo.cx - 8, geo.cy - 8); g.lineTo(geo.cx + 8, geo.cy + 8);
              g.moveTo(geo.cx + 8, geo.cy - 8); g.lineTo(geo.cx - 8, geo.cy + 8);
              g.stroke(); g.restore();
            }
          }
          // The beat pips.
          var x0 = 128, gap = Math.min(30, (W - x0 - 16) / beats);
          for (var b = 0; b < beats; b++) {
            k.pip(g, x0 + gap * b + gap / 2, geo.cy, 7, res[b], C, b === i && res[b] === null);
          }
          k.text(g, "Beat " + Math.min(i + 1, beats) + " of " + beats, x0 + gap / 2 - 7, geo.cy + 26, C,
            { size: 13 });
        }
      };
    }
  };
})();
