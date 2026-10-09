// Leather minigame: Harvest, the knife that takes the hide off a carcass (leather UI plan §9,
// revamp plan §5.7, contracts §11.1). Lane U2's, loaded with the other leather games and before
// the frame (33-bench-games.js), and played from the harvest sheet (table/59-harvest.js), never
// from the bench: the harvest is a scene action, not a bench method.
//
// THE REAL VARIABLE (prior art §3.1, the UNIDO hide grading the server's bands come from). A
// hide is taken by cutting it away from the body along the opening line, throat to tail, the
// knife held flat against the inside of the skin. Too shallow and the knife will not part it
// (it drags, and the line is slow to open); a little too deep and the blade scores the flesh
// side of the hide (a flay cut, the first defect group graders count); deeper still and it goes
// through, a hole. And a hide is not one thickness: it is thick over the neck and the butt and
// thin over the belly and flanks (prior art §3.1), so a knife held at one depth reads deeper
// where the hide thins. The gauge is the knife's depth as a FRACTION OF THE HIDE'S THICKNESS
// under it, with the server's clean band and its "through" band (play/harvest_views.py
// `_tuning`: content/rules/harvest.json `game.band`); the player sets the knife's depth in the
// body, and the thickness ahead of it is drawn, so the hand is moved before the thin belly
// comes, not after.
//
// WHAT IT REPORTS. The DEFECT AREA, 0..1 (`defects()`), which the frame hands back with the
// score; the SERVER turns it into the grade (rules/harvest.py `grade_of`, the UNIDO bands in
// harvest.json `grade_bands`), so this file never names a grade. Scoring the hide adds area by
// the length scored; a hole adds a fixed piece and more by the length cut through; whatever of
// the line is still unopened when the time runs out is torn off by hand, which is the worst of
// all (an idle knife is a reject). The 0..1 score the frame wants is the share of the line
// opened less twice the area spoiled: 1 for a clean hide opened end to end.
//
// INPUT. Nothing is held (00-kit.js: every leather input is a press). Space or a click starts
// the knife, and it then runs along the line by itself (the plan's Steady column, "the line
// advances by itself", made the rule for both modes so that no hold is ever asked). Up and Down
// raise and lower the blade a step; the pointer's height over the section puts the blade at
// that depth in the hide drawn there. Left and Right slow the knife and quicken it, three
// paces: slower is steadier (the hand sways less) and quicker sways more; the line has to be
// open before the time runs out. Steady mode (UI plan §9): the knife runs at half speed and the
// clean band is x1.5.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  // Paces (slow, steady, quick): how fast the knife opens the line, and how much the hand sways.
  var PACE = [0.6, 1, 1.45], SWAY = [0.55, 1, 1.5];
  // Area per whole line: a score along all of it, a hole through all of it; each new hole's own
  // piece; the unopened rest torn off by hand.
  var SCORE_AREA = 0.25, HOLE_AREA = 1, HOLE_EACH = 0.03, TORN = 0.8;
  // A shallow knife drags: it opens the line at this share of its pace.
  var DRAG = 0.2;
  // The hand's sway, as Flense's: the server's drift x3.
  var SWAY_X = 3;
  // How thick the hide runs along the line, as a share of its middle thickness.
  var THIN = 0.4, THICK = 1.7;
  // The deepest the blade goes, in middle thicknesses (past the thickest hide: through it).
  var DEEPEST = 1.8;
  // One press of Up or Down moves the blade this far (middle thicknesses). Sized so four
  // presses a second (a person, not a bot) keep up with the hide thinning toward the belly: at
  // 0.06 a hand a sixth of a second late fell behind on the steep stretches and left a grade 3.
  var STEP = 0.08;

  defs["leather.harvest"] = {
    id: "leather.harvest",
    track: "leather",
    name: "Harvest",
    first: "Open the hide along the line. Keep the knife in the clean band: thin hide reads deeper.",
    hint: function (steady) {
      return steady ? "Space starts. Up, Down: depth. Left, Right: pace"
        : "Space or click starts. Up, Down or the pointer: depth. Left, Right: pace";
    },
    KEYS: ["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "leather.knife", miss: "leather.scrape", tear: "leather.tear" },
    BAND: { unit: "fraction", label: "", after: "of thickness", target: [0.3, 0.55],
      fail: [0.8, 1], value_start: 0.15, drift: 0.04, steadyBand: 1.5,
      words: { low: "shallow", in: "clean", high: "scoring", fail: "through" },
      say: { low: "Shallow: the hide will not part", high: "Scoring the hide: ease off",
        fail: "Through the hide: ease off" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, G = ctx.gauge, clamp = k.clamp;
      var lo = G.scale[0], hi = G.scale[1];
      // Seconds to open the line at the middle pace (Steady: half speed).
      var run = ctx.seconds * 0.6 / ctx.baseSpeed / (ctx.steady ? 0.5 : 1);
      var amp = G.drift * SWAY_X * (ctx.steady ? 0.5 : 1);
      var D = k.drift(ctx.rng() * 10);
      var ph = ctx.rng() * 6.28, ph2 = ctx.rng() * 6.28;
      // The blade's depth in the body (middle thicknesses), where the hand aims it and where it is.
      var start = clamp(G.v, lo, hi);
      var aim = start, base = start, sway = 0, pace = 1;
      var s = 0, started = false, t = 0, lastHit = 0;
      var area = 0, holes = 0, scores = 0, inHole = false, inScore = false;
      var marks = [];               // {s, kind: "score" | "hole"} along the line, for the drawing
      var geo = { x0: 12, x1: 300, top: 22, unit: 26 };

      // The hide's thickness along the line (s 0..1), a smooth run between thin and thick:
      // the neck, the thin flanks and belly, the butt.
      function thick(u) {
        var w = 0.5 + 0.5 * (0.8 * Math.sin(2 * Math.PI * u * 1.15 + ph) + 0.2 * Math.sin(2 * Math.PI * u * 2.3 + ph2));
        return THIN + (THICK - THIN) * clamp(w, 0, 1);
      }
      function fraction(depth, u) { return clamp(depth / thick(u), lo, hi); }
      function along() { return clamp(s, 0, 1); }

      function nudge(dir) { aim = clamp(aim + dir * STEP, 0, DEEPEST); }
      function pointAt(y) { aim = clamp((y - geo.top) / geo.unit, 0, DEEPEST); }

      return {
        duration: run * 1.5 + 1.2,
        tick: function (dt, now) {
          t = now;
          base += (aim - base) * (1 - Math.exp(-dt / 0.12));
          sway = amp * SWAY[pace] * D(now);
          G.v = fraction(base + sway, along());
          if (!started || s >= 1) return;
          var st = G.status();
          var ds = Math.min(1 - s, dt * PACE[pace] * (st === "low" ? DRAG : 1) / run);
          var mid = s + ds / 2;
          s += ds;
          if (st === "high") {
            area += SCORE_AREA * ds;
            if (!inScore) { scores++; marks.push({ s: mid, kind: "score" }); ctx.miss(); }
          }
          inScore = st === "high";
          if (st === "fail") {
            area += HOLE_AREA * ds;
            if (!inHole) { holes++; area += HOLE_EACH; marks.push({ s: mid, kind: "hole" }); ctx.miss(); ctx.cue("tear"); }
          }
          inHole = st === "fail";
          if (st === "in" && now - lastHit > 0.3) {
            lastHit = now;
            ctx.hit(0.4 + 0.6 * G.quality(0.5, 0.6), geo.x0 + (geo.x1 - geo.x0) * s, geo.top, "grit");
          }
        },
        down: function (inp) {
          if (inp.src === "key") {
            if (inp.key === "Space") started = true;
            else if (inp.key === "ArrowUp") nudge(-1);
            else if (inp.key === "ArrowDown") nudge(1);
            else if (inp.key === "ArrowLeft") pace = Math.max(0, pace - 1);
            else if (inp.key === "ArrowRight") pace = Math.min(PACE.length - 1, pace + 1);
            return true;
          }
          if (!inp.inside) return false;
          started = true;
          pointAt(inp.y);
          return true;
        },
        move: function (inp) { if (inp.inside) pointAt(inp.y); },
        hint: function () {
          if (!started) return "Space or click to start the knife";
          if (s >= 1) return null;
          var ahead = thick(Math.min(1, s + 0.12)), now = thick(along());
          if (ahead < now - 0.12) return "Thinner ahead: lift the knife";
          if (ahead > now + 0.12) return "Thicker ahead: the knife can go deeper";
          return null;
        },
        // The defect area the server grades (contracts §11.1): what was scored and holed, and
        // whatever of the line is still unopened, torn off by hand.
        defects: function () { return clamp(area + TORN * (1 - along()), 0, 1); },
        state: function () {
          // `thick_soon` is the hide a tenth of a second ahead of the knife; `thick_ahead` a
          // quarter of a second, as far as a person reads the drawn hide ahead before moving.
          var u = along(), soon = Math.min(1, u + 0.12 / Math.max(0.5, run) * PACE[pace]);
          var ahead = Math.min(1, u + 0.25 / Math.max(0.5, run) * PACE[pace]);
          return { started: started, along: u, depth: base + sway, aim: aim, base: base, sway: sway,
            pace: pace, paces: PACE.length, fraction: G.v, band: G.band.slice(), fail: G.fail,
            status: G.status(), thick: thick(u), thick_soon: thick(soon), thick_ahead: thick(ahead), holes: holes, scores: scores,
            area: area, defects: clamp(area + TORN * (1 - u), 0, 1), run: run, unit: geo.unit, top: geo.top,
            // The hide drawn into the stage (57's `defects`: a 0..1 area), and how far the knife is.
            progress: u, plan: ctx.tuning && ctx.tuning.plan || "" };
        },
        // The frame reads the score every frame for its live pips, so it is what the knife has
        // earned SO FAR: the share of the line opened, less twice the area spoiled. A first draft
        // turned the defect area over (1 - area/0.5, the rest of the line counted as torn), and
        // the pips sat at nothing until the knife was nearly at the tail (seen live, 2026-10-08).
        // The server never reads it: it grades the defect area.
        score: function () { return clamp(along() - 2 * area, 0, 1); },
        done: function () { return s >= 1; },
        draw: function (g, W, H) {
          geo.x0 = 12; geo.x1 = Math.max(60, W - 12);
          geo.top = 20; geo.unit = Math.max(14, (H - geo.top - 4) / DEEPEST);
          var X = function (u) { return geo.x0 + (geo.x1 - geo.x0) * u; };
          var Y = function (d) { return geo.top + d * geo.unit; };
          // The hide in section along the line: its outer face along the top, its flesh side
          // following its thickness, so a thin stretch reads as a thin stretch. The opened part
          // is drawn in gold, the part still to come in the quiet edge colour.
          g.save();
          g.beginPath();
          g.moveTo(X(0), Y(0));
          g.lineTo(X(1), Y(0));
          for (var i = 40; i >= 0; i--) g.lineTo(X(i / 40), Y(thick(i / 40)));
          g.closePath();
          g.fillStyle = C.panel; g.fill();
          g.strokeStyle = C.goldDim; g.lineWidth = 1.2; g.stroke();
          g.restore();
          // The clean band inside the hide: hatched where the blade should run.
          var b0 = G.band[0], b1 = G.band[1];
          k.hatch(g, function (c) {
            c.moveTo(X(0), Y(thick(0) * b0));
            for (var j = 1; j <= 40; j++) c.lineTo(X(j / 40), Y(thick(j / 40) * b0));
            for (var j2 = 40; j2 >= 0; j2--) c.lineTo(X(j2 / 40), Y(thick(j2 / 40) * b1));
            c.closePath();
          }, [geo.x0, geo.top, geo.x1 - geo.x0, Math.max(geo.x1 - geo.x0, geo.unit * DEEPEST)], C.goldDim, 6, false, 1);
          // The cut so far: a gold line at the depth the blade ran.
          g.save();
          g.strokeStyle = C.gold; g.lineWidth = 1.6;
          g.beginPath(); g.moveTo(X(0), Y(0)); g.lineTo(X(along()), Y(0)); g.stroke();
          g.restore();
          // Where the hide was scored (a notch) and holed (a cross), at the place it happened.
          marks.forEach(function (m) {
            if (m.kind === "score") k.notch(g, X(m.s), Y(thick(m.s)) - 2, -Math.PI / 2, 4, C.alarm);
            else {
              var hx = X(m.s), hy = Y(thick(m.s) / 2);
              g.save(); g.strokeStyle = C.alarm; g.lineWidth = 1.8;
              g.beginPath(); g.moveTo(hx - 4, hy - 4); g.lineTo(hx + 4, hy + 4);
              g.moveTo(hx + 4, hy - 4); g.lineTo(hx - 4, hy + 4); g.stroke(); g.restore();
            }
          });
          // The knife: a blade edge at its depth, a diamond on the edge where it cuts.
          var kx = X(along()), ky = Y(clamp(base + sway, 0, DEEPEST));
          g.save(); g.strokeStyle = started ? C.gold : C.ink; g.lineWidth = 2;
          g.beginPath(); g.moveTo(kx - 14, ky); g.lineTo(kx + 6, ky); g.stroke(); g.restore();
          k.diamond(g, kx + 6, ky, 3.5, C.gold, C.sunk, 1);
          k.text(g, Math.round(along() * 100) + "% open", geo.x0, 9, C, { size: 12 });
          var said = [];
          if (scores) said.push(scores + (scores === 1 ? " score" : " scores"));
          if (holes) said.push(holes + (holes === 1 ? " hole" : " holes"));
          if (said.length) k.text(g, said.join(", "), geo.x0 + 84, 9, C, { size: 12, colour: C.alarm });
          var paceWord = ["slow", "steady", "quick"][pace];
          k.text(g, "Pace: " + paceWord, geo.x1, 9, C, { size: 12, align: "right" });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
