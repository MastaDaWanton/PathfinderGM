// Enchant minigame: Refine, diminishing draws (enchanting UI plan §9, revamp plan §10).
//
// Cennini's ultramarine (prior art §5.5): the first extraction is the deepest, each one after
// is paler. Here a bubble rises in the source and crests; press at the crest and the dropper
// draws clean. Each draw is worth less than the one before (32, 24, 19, 14, 11 hundredths; five
// clean draws make 1) and its window is 12% narrower, while a draw taken off the crest comes up
// cloudy: it takes back half that draw's worth and the source is spoiled for the rest. So the
// choice the craft is about is the player's: stop with what you have, or draw again for less,
// on a narrower crest. "Stop drawing" (S, or the button) ends the game; it is part of the game,
// so the frame resolves it as a finish, never as the Esc stop. A crest left alone costs nothing.
//
// Input: Space or a click at the crest; S or the button to stop. Nothing is held. Steady mode
// (UI plan §9): crests x1.6 and no clock ("no pressure to stop").
//
// REDUCED MOTION: the bubble does not rise. Its crest is counted in as Bind's is: three marks a
// quarter-rise apart, then "Now" exactly at the crest, so the same windows are met by rhythm.
//
// Scoring per draw: its worth times 1 in the inner 40% of its window, falling to 0.4 at the
// edge; a cloudy draw takes back half its worth. The score is the sum, held to 0..1.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var WORTH = [0.32, 0.24, 0.19, 0.14, 0.11];
  var HALF = 0.14, PALER = 0.12;

  defs.refine = {
    id: "refine",
    track: "enchant",
    name: "Refine",
    first: "Draw at each bubble's crest. Each draw is paler. Stop when you choose.",
    hint: function (steady) { return steady ? "Space at the crest, S to stop" : "Space or click at the crest; S stops"; },
    KEYS: ["Space", "S"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "enchant.draw", miss: "enchant.miss" },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var draws = Math.round(k.clamp(+ctx.tuning.draws || WORTH.length, 1, WORTH.length));
      var worth = WORTH.slice(0, draws), total = worth.reduce(function (a, b) { return a + b; }, 0);
      worth = worth.map(function (w) { return w / total; });
      var period = 1.1 / ctx.baseSpeed, markAt = 0.7, tm = markAt * period, beat = tm / 3;
      // One draw a crest: a second press on the crest just drawn is nothing, not a second
      // draw (a harness bot pressing on every open frame took all five on the first crest).
      var res = [], score = 0, t = 0, ended = false, cloudy = false, drawnAt = -1;
      var geo = { cx: 40, cy: 44 };

      function hwFor(i) {
        return Math.min(HALF * ctx.baseWin * (ctx.steady ? 1.6 : 1) * (1 - PALER * i), period * (1 - markAt) * 0.9, beat * 0.9);
      }
      function tb() { return t % period; }
      function counted(x, hw) {
        var rem = tm - x;
        if (Math.abs(rem) <= hw) return 4;
        if (rem < 0) return 0;
        return rem <= beat ? 3 : rem <= 2 * beat ? 2 : 1;
      }
      function draw() {
        if (ended || res.length >= draws || Math.floor(t / period) === drawnAt) return;
        var i = res.length, hw = hwFor(i), err = tb() - tm;
        drawnAt = Math.floor(t / period);
        if (Math.abs(err) <= hw) {
          var a = Math.abs(err), inner = hw * 0.4;
          var q = a <= inner ? 1 : 1 - 0.6 * ((a - inner) / (hw - inner));
          res.push(q);
          score += worth[i] * q;
          ctx.hit(q, geo.cx, geo.cy - 20, "steam", i);
          if (res.length >= draws) ended = true;
        } else {
          res.push("miss");
          score = Math.max(0, score - worth[i] * 0.5);
          cloudy = true; ended = true;
          ctx.miss(i);
        }
      }
      function stop() { ended = true; }

      var game = {
        duration: ctx.steady ? 600 : draws * period * 1.6 + 0.3,
        tick: function (dt, now) { t = now; },
        down: function (inp) {
          if (inp.src === "key" && inp.key === "S") { stop(); return true; }
          if (inp.src === "pointer" && !inp.inside) return false;
          draw();
          return true;
        },
        button: { label: "Stop drawing", press: stop },
        hint: function () {
          if (ended) return cloudy ? "Cloudy: the source is spoiled" : null;
          return res.length ? "Draw " + (res.length + 1) + " of " + draws + ", paler. Or S to stop" : null;
        },
        progress: function () { return ended ? 1 : res.length / draws; },
        state: function () {
          var i = Math.min(res.length, draws - 1), hw = hwFor(i);
          return { draw: res.length, draws: draws, rise: k.clamp(tb() / tm, 0, 1), beat: counted(tb(), hw),
            open: !ended && Math.abs(tb() - tm) <= hw && Math.floor(t / period) !== drawnAt, offset_s: tb() - tm, worth: worth[i], purity: res.length ? 1 - res.length / draws : 1,
            cloudy: cloudy, stopped: ended && !cloudy && res.length < draws, window_s: hw * 2 };
        },
        score: function () { return k.clamp(score, 0, 1); },
        done: function () { return ended; },
        draw: function (g, W, H) {
          geo.cy = H / 2;
          var i = Math.min(res.length, draws - 1), hw = hwFor(i), x = tb();
          var open = !ended && Math.abs(x - tm) <= hw;
          // The source: an upright glass, the crest band near its top hatched and notched,
          // narrower with each draw.
          var gx = 24, gw = 30, gt = 8, gb = H - 8, gh = gb - gt;
          var crestY = gt + gh * 0.18, bandH = Math.max(4, gh * 0.5 * (hw / period));
          g.save(); g.strokeStyle = C.goldDim; g.lineWidth = 1.2; g.strokeRect(gx + 0.5, gt + 0.5, gw, gh); g.restore();
          k.barBand(g, gx + 1, crestY - bandH, gw - 1, bandH * 2, C.gold, { gap: 4 });
          k.notch(g, gx - 2, crestY, 0, 5, C.gold);
          if (ctx.reduced) {
            k.counted(g, gx + gw + 16, geo.cy, ended ? 0 : counted(x, hw), C);
          } else if (!ended) {
            // The bubble: from the foot of the glass to the crest band by the crest's moment.
            var by = gb - 6 - (gb - 6 - crestY) * (x / tm);
            if (x > tm) by = crestY - (x - tm) / (period - tm) * (crestY - gt);
            g.save(); g.beginPath(); g.arc(gx + gw / 2 + 0.5, by, open ? 6 : 4.5, 0, Math.PI * 2);
            g.strokeStyle = open ? C.gold : C.ink; g.lineWidth = open ? 2 : 1.2; g.stroke(); g.restore();
          }
          // The draws: pips, each smaller than the last (paler), filled as drawn.
          var px = gx + gw + (ctx.reduced ? 130 : 26), gap = Math.min(24, Math.max(14, (W - px - 20) / draws));
          for (var d = 0; d < draws; d++) {
            var r0 = res[d] === undefined ? null : res[d];
            k.pip(g, px + gap * d + gap / 2, geo.cy, 7 - d * 0.8, r0, C, d === res.length && !ended);
          }
          k.text(g, ended ? (cloudy ? "Cloudy" : "Stopped") : "Draw " + Math.min(res.length + 1, draws) + " of " + draws,
            px, geo.cy + 22, C, { size: 13 });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
      return game;
    }
  };
})();
