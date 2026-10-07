// Alchemy minigame: Transmute, seal each colour stage at its peak (alchemy UI plan §9, revamp
// plan §9).
//
// The Great Work turns black, then white, then yellow, then red: nigredo, albedo, citrinitas,
// rubedo (alchemy prior art §5; Rampling, Ambix 2024, on citrination). Each stage ripens to a
// "Goldilocks moment" past which the fire spoils it (Schmechel on Petrus Bonus, Ambix 2025), and
// Potion Craft already makes the four stages its legendary chain. Here the work in the aludel
// passes through the server's stages in order, each colour deepening to its peak and turning to
// the next; seal each one as it peaks.
//
// The frame draws the COLOUR-STAGE TRACK (33-bench-games.js STAGES): the run as a timeline cut
// into its stages, each named in words, each peak's window hatched and notched, the stage now
// outlined, a needle at now. The stages come in order and only in order: a press always seals
// the stage now, never a later one, and a press before a stage's window opens seals it unripe
// (nothing) and moves on, so pressing out of time scores nothing and mashing scores nothing at
// all. The first peak is never sooner than two seconds after the game starts, so a player who
// has just closed the first-time card is not already late.
//
// REDUCED MOTION: the needle does not travel and the colour does not swell. Each peak is counted
// in ("3", "2", "1", "Now", the enchant games' counted marks), on the same windows.
//
// Input: Space or a click, once per stage. Steady mode (UI plan §9): the stages last x1.5 and the
// peak windows x1.6.
//
// Scoring: the mean over the stages of each seal's timing: full in the inner 40% of the window,
// falling to 0.4 at its edge; an unripe seal or a stage let pass is 0. Per-stage windows from the
// server (`{name, length, window}` factors) are honoured; plain names get the defaults.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  // LEAD + 0.7 x the shortest stage (1.2s) puts the first peak at 2.04s at the earliest.
  var LEAD = 1.2, PEAK_AT = 0.7, HALF = 0.24, TAIL = 0.4;
  // Content colours: the stage's own (prior art §5), never chrome. Unknown names are grey.
  var COLOURS = { nigredo: [30, 26, 24], albedo: [232, 228, 218], citrinitas: [214, 170, 56],
    rubedo: [160, 46, 40] };
  var GREY = [120, 116, 110];

  defs.transmute = {
    id: "transmute",
    track: "alchemy",
    name: "Transmute",
    first: "Black, white, yellow, red. Seal each colour as it peaks, in order. Space or click.",
    hint: function (steady) { return steady ? "Space or click as each stage peaks" : "Space or click as each colour peaks"; },
    KEYS: ["Space"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { chime: "alchemy.chime", miss: "alchemy.miss" },
    STAGES: true,
    STAGE_NAMES: ["nigredo", "albedo", "citrinitas", "rubedo"],
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var list = ctx.stages || [];
      var L = Math.max(1.2, (ctx.seconds - LEAD) / Math.max(1, list.length)) * (ctx.steady ? 1.5 : 1);
      var s = LEAD, items = list.map(function (st) {
        var len = L * st.length, it = { name: st.name, word: st.word, s: s, e: s + len };
        it.peak = s + len * PEAK_AT;
        it.hw = Math.min(len * 0.28, HALF * ctx.band(1.6) * st.window);
        it.res = null;
        s += len;
        return it;
      });
      var end = s + TAIL, cur = 0, t = 0;
      var geo = { cx: 40, cy: 40 };

      function seal() {
        if (cur >= items.length) return;
        var it = items[cur];
        if (t < it.s) return;                     // the stage has not begun: nothing to seal yet
        var err = Math.abs(t - it.peak);
        if (err <= it.hw) {
          var inner = it.hw * 0.4, q = err <= inner ? 1 : 1 - 0.6 * (err - inner) / (it.hw - inner);
          it.res = q;
          ctx.hit(q, geo.cx, geo.cy, "steam", cur);
          ctx.cue("chime", { stage: it.name });
        } else {
          it.res = 0;                             // unripe, or late: sealed at nothing
          ctx.miss(cur);
        }
        cur++;
      }
      function colourAt() {
        if (!items.length) return GREY;
        var i = Math.min(cur < items.length ? cur : items.length - 1, items.length - 1), it = items[i];
        var from = i > 0 ? (COLOURS[items[i - 1].name] || GREY) : [70, 66, 60], to = COLOURS[it.name] || GREY;
        var f = ctx.reduced ? (t >= it.s ? 1 : 0) : k.clamp((t - it.s) / Math.max(0.01, it.peak - it.s), 0, 1);
        return from.map(function (v, j) { return Math.round(v + (to[j] - v) * f); });
      }
      function beat() {
        if (cur >= items.length) return 0;
        var it = items[cur], b = Math.min(0.4, (it.peak - it.s) / 3.2), o = t - it.peak;
        if (Math.abs(o) <= it.hw && o >= -Math.min(it.hw, b / 2)) return 4;
        if (o > 0) return 0;
        return o >= -b ? 3 : o >= -2 * b ? 2 : o >= -3 * b ? 1 : 0;
      }

      return {
        duration: end,
        tick: function (dt, now) {
          t = now;
          // A stage let pass its window is lost.
          while (cur < items.length && t > items[cur].peak + items[cur].hw) {
            items[cur].res = 0; ctx.miss(cur); cur++;
          }
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          seal();
          return true;
        },
        hint: function () {
          if (cur >= items.length) return null;
          var it = items[cur];
          if (t < it.s) return "The work is warming";
          return cap(it.name) + ": seal it as it peaks";
        },
        track: function () {
          return { start: 0, end: end, now: t, items: items.map(function (it, i) {
            return { name: it.name, word: it.word, s: it.s, e: it.e, peak: it.peak, hw: it.hw, res: it.res, current: i === cur };
          }) };
        },
        progress: function () { return t / end; },
        state: function () {
          var it = items[Math.min(cur, items.length - 1)] || {};
          return { stage: cur, of: items.length, name: it.name, offset_s: t - (it.peak || 0), window_s: (it.hw || 0) * 2,
            started: t >= (it.s || 0), beat: beat(), results: items.map(function (x) { return x.res; }),
            colour: colourAt(), names: items.map(function (x) { return x.name; }) };
        },
        score: function () {
          if (!items.length) return 0;
          var sum = 0;
          items.forEach(function (it) { sum += it.res || 0; });
          return sum / items.length;
        },
        done: function () { return cur >= items.length && t >= (items.length ? items[items.length - 1].peak + 0.2 : 0); },
        draw: function (g, W, H) {
          geo.cx = 40; geo.cy = H / 2;
          var c = colourAt();
          // The aludel, its work in the stage's colour (content): a round body and a short neck.
          g.save();
          g.beginPath(); g.arc(geo.cx, geo.cy + 4, 22, 0, Math.PI * 2);
          g.fillStyle = "rgb(" + c.join(",") + ")"; g.fill();
          g.strokeStyle = C.goldDim; g.lineWidth = 1.5; g.stroke();
          g.strokeRect(geo.cx - 5, geo.cy - 30, 10, 14);
          g.restore();
          // The stage's name in words, large, and one pip per stage below it.
          var x = geo.cx + 40, it = items[Math.min(cur, items.length - 1)];
          k.text(g, cur < items.length ? cap(it.name) : "Sealed", x, 16, C, { size: 17, display: true, colour: C.ink });
          for (var i = 0; i < items.length; i++) k.pip(g, x + 8 + 22 * i, geo.cy + 10, 5, items[i].res, C, i === cur);
          if (ctx.reduced) k.counted(g, x + 8 + 22 * items.length + 16, geo.cy + 10, beat(), C);
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
  function cap(s) { s = String(s || ""); return s.charAt(0).toUpperCase() + s.slice(1); }
})();
