// Forge minigame: Finish, even strokes (blacksmithing UI plan §9, revamp plan §11).
//
// Brush the bluing or the etch on in even strokes until the colour takes everywhere. The
// strip shows a coverage map of the piece: four strips of cells, each drawn by how much it
// has taken. Too little and the bare metal shows; too much in one place and it blotches.
//
// Input:
//   - Mouse or touch: drag strokes across the map. A cell takes colour for as long as the
//     brush is over it, so the stroke's speed is the evenness: a steady sweep at a walking
//     pace lays one even coat, a pause blotches, a flick leaves it thin. The brush paints while
//     the button is down, read from the move itself, so it plays the same in Steady mode.
//   - Keyboard: the brush's load swells and thins as it is dipped and wiped (a slow, readable
//     swing, never noise); Left or Right lays the next strip at the load of that moment, and
//     the brush then goes back to the pot for 0.7s. Without that pause four presses in four
//     frames at the one good moment laid the whole piece in a second (measured in the node
//     driver, 2026-10-04): the timing was asked once, not four times.
//   - Steady mode (UI plan §9, "strokes cover x1.5"): the brush is half as wide again, and the
//     even band of coverage x1.5 (`ctx.band(1.5)`).
//
// Scoring: each cell earns 1 inside the even band (about 0.8 to 1.2 coats), falling to 0.4 at
// half a coat either side, and nothing bare or soaked. The score is the mean over the cells.
// The game ends when its time is up, or as soon as every cell sits in the band.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};

  defs.finish = {
    id: "finish",
    track: "forge",
    name: "Finish",
    first: "Brush it on in even strokes until every part has taken the colour.",
    hint: function () { return "Drag even strokes, or Left and Right lay a strip"; },
    KEYS: ["ArrowLeft", "ArrowRight"],
    HOLDS: ["pointer"],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "forge.temper", miss: "forge.strike.miss" },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var ROWS = 4, COLS = 12;
      var cells = [];
      for (var i = 0; i < ROWS * COLS; i++) cells.push(0);
      var half = 0.2 * ctx.band(1.5);
      var even = [1 - half, 1 + half];
      var brush = ctx.steady ? 1.5 : 1;                     // the brush's reach, in rows
      var next = 0, t = 0, load = 1, dip = 0, drift = k.drift(ctx.rng() * 10), swing = 1.6 * ctx.baseSpeed;
      var geo = { x0: 16, y0: 12, cw: 20, rh: 14, W: 0, H: 0 };
      // A coat is laid by a stroke at PACE px/s, about the speed of a calm sweep across 240px.
      var PACE = 260;

      function q(c) {
        if (c >= even[0] && c <= even[1]) return 1;
        var d = c < even[0] ? even[0] - c : c - even[1];
        return d >= 0.5 ? 0 : 1 - 0.6 * (d / 0.5);
      }
      function allEven() { for (var j = 0; j < cells.length; j++) if (q(cells[j]) < 1) return false; return true; }
      function layStrip(dir) {
        if (next >= ROWS || dip > 0) return;
        dip = 0.7;
        for (var c = 0; c < COLS; c++) {
          var wob = 1 + 0.04 * Math.sin(c * 1.7 + next);    // a strip is never perfectly flat
          cells[next * COLS + c] += load * wob;
        }
        var got = 0;
        for (var c2 = 0; c2 < COLS; c2++) got += q(cells[next * COLS + c2]);
        got /= COLS;
        if (got >= 0.5) ctx.hit(got, geo.x0 + (dir > 0 ? COLS * geo.cw : 0), geo.y0 + next * geo.rh, "steam");
        else ctx.miss();
        next++;
      }
      var lastMove = null;
      // Every cell under the brush at (x, y): its column, and every row within its reach.
      function under(x, y, fn) {
        var c = Math.floor((x - geo.x0) / geo.cw);
        if (c < 0 || c >= COLS) return;
        for (var rr = 0; rr < ROWS; rr++) {
          if (Math.abs(geo.y0 + (rr + 0.5) * geo.rh - y) <= geo.rh * brush / 2) fn(rr * COLS + c);
        }
      }

      return {
        duration: ctx.seconds * 1.4,
        tick: function (dt, now) {
          t = now;
          if (dip > 0) dip = Math.max(0, dip - dt);
          // The load swings between 0.45 and 1.55 coats, about one swing every 2.4s.
          load = 1 + 0.55 * Math.sin(t * Math.PI * 2 / 2.4 * swing / 1.6 + 0.6) * (0.85 + 0.15 * drift(t));
        },
        down: function (inp) {
          if (inp.src === "key") { layStrip(inp.key === "ArrowRight" ? 1 : -1); return true; }
          if (!inp.inside) return false;
          lastMove = { x: inp.x, y: inp.y, t: t };
          return true;
        },
        up: function () { lastMove = null; return true; },
        move: function (inp) {
          if (!inp.down) { lastMove = null; return; }
          if (!lastMove) { lastMove = { x: inp.x, y: inp.y, t: t }; return; }
          // Coverage laid along the segment since the last move. A full sweep across a cell
          // lays sqrt(PACE / speed) coats: one at PACE, about 1.4 at half of it, 0.7 at double.
          // The square root is the generous part (prior art §0 item 5): a straight dwell-time
          // rule would make the even band a 210 to 330 px/s window (worked out, not played),
          // too narrow to sweep by feel; and
          // a thin coat can still be built up with a second pass. Standing still soaks the
          // cells under the brush at 3 coats a second, which is what blotches.
          var dx = inp.x - lastMove.x, dy = inp.y - lastMove.y, dist = Math.sqrt(dx * dx + dy * dy);
          var dt = Math.max(1 / 240, t - lastMove.t);
          if (dist < 0.5) {
            under(inp.x, inp.y, function (idx) { cells[idx] += 3 * dt; });
          } else {
            var coat = Math.min(2.5, Math.sqrt(PACE / (dist / dt)));
            var steps = Math.max(1, Math.ceil(dist / (geo.cw / 4))), part = (dist / steps) / geo.cw;
            for (var st = 1; st <= steps; st++) {
              under(lastMove.x + dx * st / steps, lastMove.y + dy * st / steps,
                function (idx) { cells[idx] += coat * part; });
            }
          }
          lastMove = { x: inp.x, y: inp.y, t: t };
        },
        hint: function () { return dip > 0 ? "Dipping the brush" : null; },
        progress: function (now) { return now / (ctx.seconds * 1.4); },
        state: function () {
          return { cells: cells.slice(), rows: ROWS, cols: COLS, even: even.slice(), load: load, strip: next,
            dipping: dip > 0 };
        },
        score: function () { var s = 0; cells.forEach(function (c) { s += q(c); }); return s / cells.length; },
        // Over when every cell is even and the brush is off the piece. The frame's pointer
        // says so even in Steady mode, where this game never hears the release itself.
        done: function () { return allEven() && !ctx.pointer.down; },
        draw: function (g, W, H) {
          geo.W = W; geo.H = H;
          geo.cw = Math.max(10, Math.min(22, (W - 120) / COLS));
          geo.rh = Math.min(18, (H - 24) / ROWS);
          geo.y0 = (H - geo.rh * ROWS) / 2;
          for (var r = 0; r < ROWS; r++) {
            for (var c = 0; c < COLS; c++) {
              var v = cells[r * COLS + c], x = geo.x0 + c * geo.cw, y = geo.y0 + r * geo.rh;
              // Shape, not only colour: bare is an empty box, even is hatched gold, soaked is
              // cross-hatched alarm, thin is a sparse hatch.
              if (v > even[1]) k.barBand(g, x + 1, y + 1, geo.cw - 2, geo.rh - 2, C.alarm, { cross: true, gap: 4 });
              else if (v >= even[0]) k.barBand(g, x + 1, y + 1, geo.cw - 2, geo.rh - 2, C.gold, { gap: 4 });
              else if (v > 0.05) k.barBand(g, x + 1, y + 1, geo.cw - 2, geo.rh - 2, C.goldDim, { gap: 8 });
              else { g.save(); g.strokeStyle = C.edge; g.strokeRect(x + 1.5, y + 1.5, geo.cw - 3, geo.rh - 3); g.restore(); }
            }
          }
          // The brush's load, for the keyboard: a short upright scale with the even band
          // outlined and notched; the strip the next press lays is marked at the map's edge.
          var lx = geo.x0 + COLS * geo.cw + 26, lh = geo.rh * ROWS, ly = geo.y0;
          var Y = function (v) { return ly + lh * (1 - k.clamp(v / 2, 0, 1)); };
          g.save(); g.strokeStyle = C.edge; g.strokeRect(lx + 0.5, ly + 0.5, 10, lh); g.restore();
          k.barBand(g, lx - 2, Y(even[1]), 14, Y(even[0]) - Y(even[1]), C.goldDim, { gap: 4 });
          k.notch(g, lx - 4, Y(load), 0, 6, C.ink);
          if (next < ROWS) k.notch(g, geo.x0 - 4, geo.y0 + (next + 0.5) * geo.rh, 0, 5, C.gold);
          k.text(g, "Load", lx + 5, ly + lh + 9, C, { size: 13, align: "center" });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) {
            // The brush: its width drawn as a short bar where the pointer is.
            g.save(); g.strokeStyle = C.gold; g.lineWidth = 1.5;
            g.strokeRect(p.x - 3, p.y - geo.rh * brush / 2, 6, geo.rh * brush); g.restore();
            k.reticle(g, p.x, p.y, C, p.down);
          }
        }
      };
    }
  };
})();
