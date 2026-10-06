// Enchant minigame: Prepare, lay the circle in its order (enchanting UI plan §9, revamp plan
// §10; the owner's ruling: "Lay components in order ... No freehand drawing").
//
// The server's roll sends the circle's sequence (`opts.seq`, rules/enchanter.py tuning_for):
// the kinds of the circle materials in the order they were set out, then the focus, then the
// bell, the test step before sealing (Havamal's "freista": carve, read, stain, test; prior
// art §5.5). The game plays it back once, one glyph at a time, then veils it, and the player
// lays it from memory, one piece per slot. That is Simon's shape, and its numbers: 0.42s a
// glyph and 0.05s between for a sequence of five or fewer, and three seconds to answer before
// the slot is lost (reverse-engineered from the 1978 MB Electronic Simon,
// waitingforfriday.com/?p=586). A wrong piece costs that slot a third of its credit and shows
// the right glyph in it, so nobody is ever stuck guessing.
//
// Input: 1 to 6 lays that piece; or the arrows choose and Space or Enter lays it; or a click on
// the piece. Nothing is held. Steady mode (UI plan §9): the sequence is never veiled, there is
// no clock, and a wrong pick costs half as much.
//
// Scoring per slot: 1, less 0.34 for each wrong pick (0.17 in Steady), times its pace: full
// within the slot's share of time (0.9s at the middle difficulty), falling to 0.6 at Simon's
// three seconds, when the slot is lost at 0. The score is the mean over the slots.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var NAMES = { chalk: "Chalk", salt: "Salt", ink: "Ink", treatment: "Treatment", focus: "Focus",
    catalyst: "Catalyst", bell: "Bell" };
  var POOL = ["chalk", "salt", "ink", "treatment", "focus", "catalyst", "bell"];
  var GLANCE = 0.47, LIMIT = 3, COST = 0.34;
  function nameOf(kind) { return NAMES[kind] || (kind.charAt(0).toUpperCase() + kind.slice(1)); }

  defs.prepare = {
    id: "prepare",
    track: "enchant",
    name: "Prepare",
    first: "Watch the circle's order, then lay each piece in it. The bell tests it last.",
    hint: function (steady) { return steady ? "1 to 6, or click the piece" : "Watch, then 1 to 6 or click"; },
    KEYS: ["1", "2", "3", "4", "5", "6", "ArrowLeft", "ArrowRight", "Space", "Enter"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "enchant.chalk", miss: "enchant.bind.miss" },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, steady = ctx.steady;
      var seq = (ctx.seq || []).map(function (s) { return String(s || "").toLowerCase(); })
        .filter(function (s) { return s; }).slice(0, 8);
      if (!seq.length) seq = ["chalk", "ink", "bell"];
      var n = seq.length;
      // The pieces: every kind the sequence uses, and one decoy (two above the middle
      // difficulty) from the circle's other materials, shuffled once with the run's seed so a
      // number key means the same piece for the whole game.
      var kinds = [];
      seq.forEach(function (s) { if (kinds.indexOf(s) < 0) kinds.push(s); });
      var decoys = POOL.filter(function (p) { return kinds.indexOf(p) < 0; });
      var want = Math.min(6 - Math.min(6, kinds.length), ctx.difficulty > 0.5 ? 2 : 1);
      for (var d = 0; d < want && decoys.length; d++) kinds.push(decoys.splice(Math.floor(ctx.rng() * decoys.length), 1)[0]);
      kinds = kinds.slice(0, 6);
      for (var i = kinds.length - 1; i > 0; i--) {
        var j = Math.floor(ctx.rng() * (i + 1)), tmp = kinds[i]; kinds[i] = kinds[j]; kinds[j] = tmp;
      }
      var glanceEnd = steady ? 0 : n * GLANCE + 0.3;
      var share = 0.9 / ctx.baseSpeed;
      var cost = steady ? COST / 2 : COST;
      var res = [], wrong = [], shown = [];
      for (var s = 0; s < n; s++) { res.push(null); wrong.push(0); shown.push(steady); }
      var step = 0, stepStart = glanceEnd, t = 0, focus = 0;
      var tiles = [], slots = [];

      function pace(dt) {
        if (steady || dt <= share) return 1;
        return dt >= LIMIT ? 0.6 : 1 - 0.4 * (dt - share) / (LIMIT - share);
      }
      function advance() { step++; stepStart = t; }
      function pick(idx) {
        if (step >= n || t < glanceEnd || idx < 0 || idx >= kinds.length) return;
        var slot = slots[step] || { x: 0, y: 0 };
        if (kinds[idx] === seq[step]) {
          res[step] = Math.max(0, 1 - wrong[step] * cost) * pace(t - stepStart);
          shown[step] = true;
          ctx.hit(res[step], slot.x, slot.y, "grit", step);
          advance();
        } else {
          wrong[step]++;
          shown[step] = true;     // the right glyph shows, so the slot can be finished
          ctx.miss(step);
        }
      }
      function lit() {          // the glyph playing back now, or -1
        if (t >= glanceEnd || steady) return -1;
        var i = Math.floor(t / GLANCE);
        return i < n && (t - i * GLANCE) < GLANCE - 0.05 ? i : -1;
      }

      return {
        duration: steady ? 600 : glanceEnd + n * LIMIT + 0.3,
        tick: function (dt, now) {
          t = now;
          if (!steady && step < n && t >= glanceEnd && t - stepStart >= LIMIT) {
            res[step] = 0; shown[step] = true; ctx.miss(step); advance();
          }
        },
        down: function (inp) {
          if (inp.src === "key") {
            if (/^[1-6]$/.test(inp.key)) { focus = Math.min(kinds.length - 1, +inp.key - 1); pick(+inp.key - 1); }
            else if (inp.key === "ArrowLeft") focus = (focus + kinds.length - 1) % kinds.length;
            else if (inp.key === "ArrowRight") focus = (focus + 1) % kinds.length;
            else pick(focus);
            return true;
          }
          if (!inp.inside) return false;
          for (var q = 0; q < tiles.length; q++) {
            var b = tiles[q];
            if (inp.x >= b.x - b.w / 2 && inp.x <= b.x + b.w / 2 && inp.y >= b.y - b.h / 2 && inp.y <= b.y + b.h / 2) {
              focus = q; pick(q); return true;
            }
          }
          return false;
        },
        hint: function () {
          if (step >= n) return null;
          if (t < glanceEnd) return "Watch the order";
          return "Piece " + (step + 1) + " of " + n + (shown[step] && !steady ? ": " + nameOf(seq[step]) : "");
        },
        progress: function () { return step / n; },
        state: function () {
          return { phase: t < glanceEnd ? "watch" : step >= n ? "sealed" : "lay", step: Math.min(step, n - 1),
            steps: n, seq: seq.slice(), lit: lit(), pieces: kinds.slice(), focus: focus,
            placed: res.map(function (q) { return q === null ? null : q; }), wrong: wrong[Math.min(step, n - 1)],
            // Where each piece was last drawn, for a stage or a harness aiming the pointer.
            tiles: tiles.map(function (b) { return { x: b.x, y: b.y }; }) };
        },
        score: function () { var sum = 0; res.forEach(function (q) { if (typeof q === "number") sum += q; }); return sum / n; },
        done: function () { return step >= n; },
        draw: function (g, W, H) {
          var L = lit(), cur = step < n ? step : -1;
          // The slots: one per step, the next outlined in gold with a notch over it.
          var sw = Math.max(18, Math.min(30, (W - 24) / n - 6)), sy = 8 + sw / 2;
          var x0 = (W - n * (sw + 6) + 6) / 2;
          slots = [];
          for (var i = 0; i < n; i++) {
            var x = x0 + i * (sw + 6) + sw / 2;
            slots.push({ x: x, y: sy });
            g.save();
            g.strokeStyle = i === cur && t >= glanceEnd ? C.gold : C.edge;
            g.lineWidth = i === cur && t >= glanceEnd ? 2 : 1;
            g.strokeRect(x - sw / 2 + 0.5, sy - sw / 2 + 0.5, sw - 1, sw - 1);
            g.restore();
            if (i === cur && t >= glanceEnd) k.notch(g, x, sy - sw / 2 - 3, Math.PI / 2, 4, C.gold);
            var gs = sw * 0.32;
            if (res[i] !== null) {
              if (res[i] > 0) k.glyph(g, seq[i], x, sy, gs, C.gold, 1.8);
              else { k.glyph(g, seq[i], x, sy, gs, C.ash, 1.2); k.pip(g, x + sw / 2 - 4, sy + sw / 2 - 4, 3, "miss", C); }
            } else if (i === L || shown[i] || steady) {
              k.glyph(g, seq[i], x, sy, gs, i === L ? C.ink : C.dim, 1.5);
            } else {
              k.text(g, "?", x, sy, C, { size: 13, align: "center", colour: C.ash });
            }
          }
          // The pieces: a tile each, its glyph, its number key and its name.
          var tw = Math.max(34, Math.min(64, (W - 20) / kinds.length - 6)), th = Math.min(46, H - sw - 24);
          var ty = Math.max(sy + sw / 2 + 8 + th / 2, H - th / 2 - 4);
          var tx0 = (W - kinds.length * (tw + 6) + 6) / 2;
          tiles = [];
          for (var q = 0; q < kinds.length; q++) {
            var cx = tx0 + q * (tw + 6) + tw / 2;
            tiles.push({ x: cx, y: ty, w: tw, h: th });
            g.save();
            g.strokeStyle = q === focus ? C.gold : C.goldDim; g.lineWidth = q === focus ? 2 : 1;
            g.strokeRect(cx - tw / 2 + 0.5, ty - th / 2 + 0.5, tw - 1, th - 1);
            g.restore();
            k.glyph(g, kinds[q], cx, ty - th * 0.12, Math.min(9, th * 0.22), C.ink, 1.4);
            k.text(g, String(q + 1), cx - tw / 2 + 5, ty - th / 2 + 8, C, { size: 12, colour: C.dim });
            if (th >= 38) k.text(g, nameOf(kinds[q]), cx, ty + th / 2 - 8, C, { size: 12, align: "center", colour: C.dim });
          }
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
