// Enchant minigame: Unbind, unpick the sigils last-cut first (enchanting UI plan §9, revamp plan
// §10 and §13; Egil's Saga: shave the runes, burn the shavings, re-carve).
//
// The server's roll sends the layer's sigils already reversed (`opts.seq`, rules/enchanter.py
// tuning_for: one `enhancement` for the +N, one `sigil` for each property, flat property and
// power, last-cut first). They stand round the circle where they were cut, scattered among
// the circle's own four quarter marks, each with its cut number in numerals beside it. Unpick
// the highest number first, then down: order is the whole craft (prior art §5.5). A quarter
// mark, or a sigil out of its turn, is a wrong pick: that sigil's credit drops and its number
// is outlined, so the next one is never in doubt.
//
// Input: a click on the sigil; or the arrows walk round the circle and Space or Enter unpicks;
// or the sigil's number key unpicks it at once. Nothing is held. Steady mode (UI plan §9): no
// clock, and a wrong pick costs half as much.
//
// Scoring per sigil: 1, less 0.34 for each wrong pick (0.17 in Steady), times its pace: full
// within 1.2s, falling to 0.6 at three seconds (Simon's answer time, as Prepare), when the
// sigil tears out on its own at 0. The score is the mean over the sigils.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var LIMIT = 3, COST = 0.34;
  var ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"];

  defs.unbind = {
    id: "unbind",
    track: "enchant",
    name: "Unbind",
    first: "Unpick the sigils from the last cut to the first: the highest number first.",
    hint: function () { return "Click it, or its number key"; },
    KEYS: ["1", "2", "3", "4", "5", "6", "7", "8", "9", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Space", "Enter"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "enchant.unpick", miss: "enchant.bind.miss" },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, steady = ctx.steady;
      var seq = (ctx.seq || []).map(function (s) { return String(s || "").toLowerCase(); })
        .filter(function (s) { return s; }).slice(0, 12);
      if (!seq.length) seq = ["sigil", "sigil", "enhancement"];
      var n = seq.length;
      // Round the circle: the four quarter marks at the quarters, the sigils in the other
      // places, scattered once with the run's seed.
      var slots = Math.max(12, Math.ceil((n + 4) / 4) * 4), per = slots / 4;
      var open = [];
      for (var s = 0; s < slots; s++) if (s % per) open.push(s);
      for (var i = open.length - 1; i > 0; i--) {
        var j = Math.floor(ctx.rng() * (i + 1)), tmp = open[i]; open[i] = open[j]; open[j] = tmp;
      }
      var marks = [];
      for (var q = 0; q < 4; q++) marks.push({ kind: "quarter", slot: q * per, turn: -1, cut: 0, gone: false });
      seq.forEach(function (kind, idx) {
        marks.push({ kind: kind, slot: open[idx], turn: idx, cut: n - idx, gone: false });
      });
      marks.sort(function (a, b) { return a.slot - b.slot; });   // the arrows walk clockwise
      var res = [], wrong = [];
      for (var r = 0; r < n; r++) { res.push(null); wrong.push(0); }
      var cost = steady ? COST / 2 : COST;
      var share = 1.2 / ctx.baseSpeed;
      var step = 0, stepStart = 0, t = 0, focus = 0, flagged = -1;
      var geo = { cx: 50, cy: 44, R: 34 };

      function pace(dt) {
        if (steady || dt <= share) return 1;
        return dt >= LIMIT ? 0.6 : 1 - 0.4 * (dt - share) / (LIMIT - share);
      }
      function posOf(m) {
        var a = -Math.PI / 2 + (m.slot / slots) * Math.PI * 2;
        return { x: geo.cx + Math.cos(a) * geo.R, y: geo.cy + Math.sin(a) * geo.R };
      }
      function markFor(turn) { for (var x = 0; x < marks.length; x++) if (marks[x].turn === turn) return x; return -1; }
      function take(mi) {
        if (step >= n || mi < 0 || mi >= marks.length || marks[mi].gone) return;
        var m = marks[mi], p = posOf(m);
        if (m.turn === step) {
          res[step] = Math.max(0, 1 - wrong[step] * cost) * pace(t - stepStart);
          m.gone = true;
          ctx.hit(res[step], p.x, p.y, "steam", step);
          step++; stepStart = t; flagged = -1;
        } else {
          wrong[step]++;
          flagged = markFor(step);    // the right one is outlined, so nobody is stuck
          ctx.miss(step);
        }
      }
      function walk(dir) {
        for (var c = 1; c <= marks.length; c++) {
          var x = (focus + dir * c + marks.length * 4) % marks.length;
          if (!marks[x].gone) { focus = x; return; }
        }
      }

      return {
        duration: steady ? 600 : n * LIMIT + 0.3,
        tick: function (dt, now) {
          t = now;
          if (!steady && step < n && t - stepStart >= LIMIT) {
            var mi = markFor(step);
            res[step] = 0; if (mi >= 0) marks[mi].gone = true;
            ctx.miss(step); step++; stepStart = t; flagged = -1;
          }
        },
        down: function (inp) {
          if (inp.src === "key") {
            if (/^[1-9]$/.test(inp.key)) {
              // The number key names the sigil by its cut number.
              // A number no sigil carries (or one already unpicked) picks nothing, so costs nothing.
              for (var x = 0; x < marks.length; x++) if (marks[x].cut === +inp.key && !marks[x].gone) { focus = x; take(x); break; }
              return true;
            }
            if (inp.key === "ArrowLeft" || inp.key === "ArrowUp") walk(-1);
            else if (inp.key === "ArrowRight" || inp.key === "ArrowDown") walk(1);
            else take(focus);
            return true;
          }
          if (!inp.inside) return false;
          var best = -1, bd = 15 * 15;
          marks.forEach(function (m, mi) {
            if (m.gone) return;
            var p = posOf(m), d = (p.x - inp.x) * (p.x - inp.x) + (p.y - inp.y) * (p.y - inp.y);
            if (d <= bd) { bd = d; best = mi; }
          });
          if (best >= 0) { focus = best; take(best); return true; }
          return false;
        },
        hint: function () {
          if (step >= n) return null;
          return "Unpick " + ROMAN[n - step - 1] + " next: the last cut comes out first";
        },
        progress: function () { return step / n; },
        state: function () {
          return { step: Math.min(step, n - 1), steps: n, next: step < n ? n - step : 0, focus: focus,
            marks: marks.map(function (m) { var p = posOf(m); return { kind: m.kind, cut: m.cut, slot: m.slot, gone: m.gone, quarter: m.turn < 0, x: p.x, y: p.y }; }),
            slots: slots, unpicked: res.map(function (q) { return q; }) };
        },
        score: function () { var sum = 0; res.forEach(function (q) { if (typeof q === "number") sum += q; }); return sum / n; },
        done: function () { return step >= n; },
        draw: function (g, W, H) {
          geo.cy = H / 2;
          geo.R = Math.max(16, Math.min(40, H / 2 - 12));
          geo.cx = geo.R + 22;
          g.save(); g.strokeStyle = C.edge; g.lineWidth = 1;
          g.beginPath(); g.arc(geo.cx, geo.cy, geo.R, 0, Math.PI * 2); g.stroke(); g.restore();
          marks.forEach(function (m, mi) {
            var p = posOf(m), sz = m.turn < 0 ? 5 : 7;
            if (mi === focus && !m.gone) {
              g.save(); g.strokeStyle = C.gold; g.lineWidth = 1.5; g.strokeRect(p.x - 10, p.y - 10, 20, 20); g.restore();
            }
            if (mi === flagged) k.notch(g, p.x, p.y - 13, Math.PI / 2, 4, C.gold);
            if (m.gone) { k.glyph(g, m.kind, p.x, p.y, sz, C.ash, 1); return; }
            k.glyph(g, m.kind, p.x, p.y, sz, m.turn < 0 ? C.dim : C.ink, m.turn < 0 ? 1.2 : 1.6);
            if (m.cut) {
              var a = -Math.PI / 2 + (m.slot / slots) * Math.PI * 2;
              k.text(g, ROMAN[m.cut - 1] || String(m.cut), geo.cx + Math.cos(a) * (geo.R + 15), geo.cy + Math.sin(a) * (geo.R + 13), C,
                { size: 12, align: "center", colour: m.turn === step ? C.gold : C.dim });
            }
          });
          var px = geo.cx + geo.R + 34, gap = Math.min(24, Math.max(14, (W - px - 20) / n));
          for (var b = 0; b < n; b++) k.pip(g, px + gap * b + gap / 2, geo.cy, 6, res[b], C, b === step);
          k.text(g, step < n ? "Unpick " + ROMAN[n - step - 1] : "Unbound", px, geo.cy + 22, C, { size: 13 });
          var pt = ctx.pointer;
          if (pt.inside && pt.y >= 0 && pt.y <= H) k.reticle(g, pt.x, pt.y, C, pt.down);
        }
      };
    }
  };
})();
