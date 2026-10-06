// Enchant minigame: Cleanse, unpick the curse's sigils and leave the rest (enchanting UI plan
// §9, revamp plan §10 and §11; the book's remove curse DC is the roll's, already made).
//
// The curse is known before Cleanse can be chosen, so its sigils are shown for what they are:
// among the item's whole sigils round the circle, the curse's stand in a darker line, each with
// a cross-hatched, saw-edged ring (a shape, so it reads without colour, as every danger zone in
// these games does) and its number in the curse's sequence. Unpick them in that order, 1 first,
// and leave the whole ones alone (UI plan §9: "Only the curse's sigils glow ... unpick those,
// leave the others"). The server sends the curse's sequence (`opts.seq`, rules/enchanter.py
// tuning_for: three sigils today); how many whole sigils stand among them is the game's own
// (three, four at the middle difficulty, five at the hardest; `tuning.whole` overrides), since
// the curse's id and shape never reach the page (contracts §7).
//
// Input: a click on the sigil; or the arrows walk round the circle and Space or Enter unpicks;
// or the curse sigil's number key unpicks it at once. Nothing is held. Steady mode (UI plan
// §9): no clock, and a whole sigil or one out of turn is refused, not scored.
//
// Scoring per curse sigil: 1, less 0.34 for each wrong pick (none in Steady), times its pace:
// full within 1.2s, falling to 0.6 at three seconds, when it tears out on its own at 0. The
// score is the mean over the curse's sigils.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var LIMIT = 3, COST = 0.34;

  defs.cleanse = {
    id: "cleanse",
    track: "enchant",
    name: "Cleanse",
    first: "Unpick the curse's ringed sigils in their order. Leave the whole ones.",
    hint: function () { return "Click it, or its number key"; },
    KEYS: ["1", "2", "3", "4", "5", "6", "7", "8", "9", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Space", "Enter"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "enchant.unpick", miss: "enchant.bind.miss" },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, steady = ctx.steady;
      var seq = (ctx.seq || []).map(function (s) { return String(s || "").toLowerCase(); })
        .filter(function (s) { return s; }).slice(0, 9);
      if (!seq.length) seq = ["sigil", "sigil", "sigil"];
      var n = seq.length;
      var whole = Math.round(k.clamp(+ctx.tuning.whole || (3 + Math.round(2 * ctx.difficulty)), 1, 8));
      var slots = Math.max(10, n + whole + 2);
      var free = [];
      for (var s = 0; s < slots; s++) free.push(s);
      for (var i = free.length - 1; i > 0; i--) {
        var j = Math.floor(ctx.rng() * (i + 1)), tmp = free[i]; free[i] = free[j]; free[j] = tmp;
      }
      var marks = [];
      seq.forEach(function (kind, idx) { marks.push({ kind: kind, slot: free[idx], turn: idx, curse: true, gone: false }); });
      for (var w = 0; w < whole; w++) marks.push({ kind: w % 3 === 2 ? "enhancement" : "sigil", slot: free[n + w], turn: -1, curse: false, gone: false });
      marks.sort(function (a, b) { return a.slot - b.slot; });
      var res = [], wrong = [];
      for (var r = 0; r < n; r++) { res.push(null); wrong.push(0); }
      var share = 1.2 / ctx.baseSpeed;
      var step = 0, stepStart = 0, t = 0, focus = 0, refused = "";
      var geo = { cx: 50, cy: 44, R: 34 };

      function pace(dt) {
        if (steady || dt <= share) return 1;
        return dt >= LIMIT ? 0.6 : 1 - 0.4 * (dt - share) / (LIMIT - share);
      }
      function posOf(m) {
        var a = -Math.PI / 2 + (m.slot / slots) * Math.PI * 2;
        return { x: geo.cx + Math.cos(a) * geo.R, y: geo.cy + Math.sin(a) * geo.R, a: a };
      }
      function markFor(turn) { for (var x = 0; x < marks.length; x++) if (marks[x].turn === turn) return x; return -1; }
      function take(mi) {
        if (step >= n || mi < 0 || mi >= marks.length || marks[mi].gone) return;
        var m = marks[mi], p = posOf(m);
        if (m.turn === step) {
          res[step] = Math.max(0, 1 - wrong[step] * COST) * pace(t - stepStart);
          m.gone = true; refused = "";
          ctx.hit(res[step], p.x, p.y, "steam", step);
          step++; stepStart = t;
          return;
        }
        refused = m.curse ? "Not yet: unpick " + (step + 1) + " first" : "That one is whole: leave it";
        // Steady mode refuses the pick and does not score it (UI plan §9's Steady column); the
        // muffled bell still says it was refused.
        if (!steady) wrong[step]++;
        ctx.miss(step);
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
            ctx.miss(step); step++; stepStart = t; refused = "";
          }
        },
        down: function (inp) {
          if (inp.src === "key") {
            if (/^[1-9]$/.test(inp.key)) {
              // The number key names a curse sigil by its place in the curse's sequence; a
              // number no sigil carries picks nothing.
              var mi = markFor(+inp.key - 1);
              if (mi >= 0 && !marks[mi].gone) { focus = mi; take(mi); }
              return true;
            }
            if (inp.key === "ArrowLeft" || inp.key === "ArrowUp") walk(-1);
            else if (inp.key === "ArrowRight" || inp.key === "ArrowDown") walk(1);
            else take(focus);
            return true;
          }
          if (!inp.inside) return false;
          var best = -1, bd = 15 * 15;
          marks.forEach(function (m, x) {
            if (m.gone) return;
            var p = posOf(m), d = (p.x - inp.x) * (p.x - inp.x) + (p.y - inp.y) * (p.y - inp.y);
            if (d <= bd) { bd = d; best = x; }
          });
          if (best >= 0) { focus = best; take(best); return true; }
          return false;
        },
        hint: function () {
          if (step >= n) return null;
          return refused || "Unpick the curse's sigil " + (step + 1) + " of " + n;
        },
        progress: function () { return step / n; },
        state: function () {
          return { step: Math.min(step, n - 1), steps: n, focus: focus, refused: refused,
            marks: marks.map(function (m) { var p = posOf(m); return { kind: m.kind, curse: m.curse, turn: m.turn, slot: m.slot, gone: m.gone, x: p.x, y: p.y }; }),
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
            var p = posOf(m);
            if (mi === focus && !m.gone) {
              g.save(); g.strokeStyle = C.gold; g.lineWidth = 1.5; g.strokeRect(p.x - 11, p.y - 11, 22, 22); g.restore();
            }
            if (m.gone) { k.glyph(g, m.kind, p.x, p.y, 6, C.ash, 1); return; }
            if (m.curse) {
              // The curse's ring: cross-hatched, with a saw edge, in the alarm colour as a third cue.
              k.dialBand(g, p.x, p.y, 6, 9, 0, Math.PI * 2, C.alarm, { cross: true, jagged: true, gap: 3 });
              k.glyph(g, m.kind, p.x, p.y, 5, C.ink, 1.6);
              k.text(g, String(m.turn + 1), geo.cx + Math.cos(p.a) * (geo.R + 17), geo.cy + Math.sin(p.a) * (geo.R + 15), C,
                { size: 12, align: "center", colour: m.turn === step ? C.gold : C.dim });
            } else {
              k.glyph(g, m.kind, p.x, p.y, 6, C.dim, 1.3);
            }
          });
          var px = geo.cx + geo.R + 34, gap = Math.min(24, Math.max(14, (W - px - 20) / n));
          for (var b = 0; b < n; b++) k.pip(g, px + gap * b + gap / 2, geo.cy, 6, res[b], C, b === step);
          k.text(g, step < n ? "Curse sigil " + (step + 1) + " of " + n : "Cleansed", px, geo.cy + 22, C, { size: 13 });
          var pt = ctx.pointer;
          if (pt.inside && pt.y >= 0 && pt.y <= H) k.reticle(g, pt.x, pt.y, C, pt.down);
        }
      };
    }
  };
})();
