// Alchemy minigame: Dissolve, stir at the pace that keeps the fizz working (alchemy UI plan §9,
// revamp plan §7).
//
// The solid sinks into the solvent and the liquid clears as it is stirred. Stir too slowly and
// nothing goes into solution; stir too hard and it froths and splashes. The fizz is the frame's
// REACTION gauge (the server's {start, band, rise, settle, flare_at}): every stroke adds to it,
// it settles on its own, and the work (the clarity) is done only while it is in the band.
//
// A STROKE IS AN ALTERNATION. Left then Right is one stir (each arrow is half of it, `rise / 2`);
// the same arrow twice is not a stir, and the frame never passes a held key's repeat, so holding
// one key or tapping one key does nothing at all. With the mouse: drag round the flask (each half
// turn in the same direction is half a stir; scribbling back and forth cancels itself out), or
// click its left and right halves in turn, which is the tap form.
//
// Steady mode (UI plan §9): the stir counts half (rise x0.5) and the fizz settles at half the
// rate, so the same pace holds the band with half the drift; the band x1.6; the drag is click
// to take up the rod, move, click to put it down (the frame drops every release in Steady).
//
// Scoring: the clarity fills while the fizz is in the band, at full credit in its inner 60%,
// 0.6 at its rim. The score is the share cleared times the mean credit, less 0.12 for every time
// it splashed over the flare line. Mashing the arrows as fast as possible splashes again and
// again; leaving it settles to nothing.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var PIPS = 8, SPLASH = 0.12;
  var CLOUDY = [150, 140, 120], CLEAR = [214, 222, 214];

  defs.dissolve = {
    id: "dissolve",
    track: "alchemy",
    name: "Dissolve",
    first: "Stir with Left and Right in turn to keep the fizz in its band until the liquid clears.",
    hint: function (steady) {
      return steady ? "Left and Right in turn stir; click to take up the rod" : "Left and Right in turn to stir, or drag round the flask";
    },
    KEYS: ["ArrowLeft", "ArrowRight"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "alchemy.hit", miss: "alchemy.spill", stroke: "alchemy.stir" },
    REACTION: { label: "Fizz", band: [35, 70], rise: 12, settle: 6, flare_at: 88, start: 10,
      steadyBand: 1.6, steadySettle: 0.5,
      words: ["still", "fizzing", "frothing", "splashing"],
      say: { low: "Still: stir faster", high: "Frothing: ease off", flare: "Splashing: let it settle" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, R = ctx.react;
      var half = R.rise / 2 * (ctx.steady ? 0.5 : 1);
      var need = ctx.seconds * 0.65, duration = ctx.seconds * (ctx.steady ? 2.4 : 1.7);
      var work = 0, qsum = 0, inT = 0, last = null, strokes = 0, same = 0, t = 0, pips = 0, flares = 0;
      var holding = false, angle = null, swept = 0;
      var geo = { cx: 40, cy: 40, r: 22 };

      function stir(side) {
        if (work >= 1) return;
        if (side === last) { same++; return; }   // the same side twice is not a stir
        last = side; strokes++;
        R.add(half);
        ctx.cue("stroke");
      }
      function sweep(x, y) {
        var a = Math.atan2(y - geo.cy, x - geo.cx);
        if (angle != null) {
          var d = a - angle;
          if (d > Math.PI) d -= Math.PI * 2;
          if (d < -Math.PI) d += Math.PI * 2;
          swept += d;
          // Half a turn in one direction is half a stir. Back and forth cancels: `swept` is signed.
          while (swept >= Math.PI) { swept -= Math.PI; last = null; stir("cw"); }
          while (swept <= -Math.PI) { swept += Math.PI; last = null; stir("ccw"); }
        }
        angle = a;
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
          if (inp.src === "key") {
            if (inp.key === "ArrowLeft") stir("left");
            else if (inp.key === "ArrowRight") stir("right");
            return true;
          }
          if (!inp.inside) return false;
          // A click on the flask's left or right half is that arrow (the tap form).
          var dx = inp.x - geo.cx, dy = inp.y - geo.cy;
          if (Math.abs(dx) <= geo.r + 10 && Math.abs(dy) <= geo.r + 12) stir(dx < 0 ? "left" : "right");
          if (ctx.steady) holding = !holding; else holding = true;
          angle = null; swept = 0;
          return true;
        },
        move: function (inp) {
          if (!(ctx.steady ? holding : inp.down && holding)) return;
          sweep(inp.x, inp.y);
        },
        up: function () { holding = false; angle = null; swept = 0; },
        hint: function () {
          if (work >= 1) return null;
          if (same >= 2 && R.status() === "low") return "Alternate: Left, then Right";
          return R.inBand() ? "Keep this pace" : null;
        },
        state: function () {
          return { fizz: R.v, lands: R.lands(), band: R.band.slice(), flare_at: R.flare, status: R.status(),
            work: work, quality: inT ? qsum / inT : 0, strokes: strokes, same: same, flares: R.flares,
            next: last === "left" ? "ArrowRight" : "ArrowLeft", holding: holding, centre: { x: geo.cx, y: geo.cy, r: geo.r } };
        },
        score: function () { return Math.max(0, Math.min(1, work) * (inT ? qsum / inT : 0) - SPLASH * R.flares); },
        done: function () { return work >= 1; },
        draw: function (g, W, H) {
          geo.cx = 42; geo.cy = H / 2 + 2; geo.r = Math.min(24, H / 2 - 8);
          // The flask seen from above: the liquid cloudy to clear as the work is done (content
          // colour), the stir guide's two arrows either side, the next one lit.
          g.save();
          g.beginPath(); g.arc(geo.cx, geo.cy, geo.r, 0, Math.PI * 2);
          var c = CLOUDY.map(function (v, i) { return Math.round(v + (CLEAR[i] - v) * work); });
          g.fillStyle = "rgba(" + c.join(",") + ",0.35)"; g.fill();
          g.strokeStyle = C.goldDim; g.lineWidth = 1.5; g.stroke();
          g.restore();
          var nextLeft = last !== "left";
          k.notch(g, geo.cx - geo.r - 4, geo.cy, Math.PI, 7, nextLeft ? C.gold : C.ash);
          k.notch(g, geo.cx + geo.r + 4, geo.cy, 0, 7, nextLeft ? C.ash : C.gold);
          k.text(g, nextLeft ? "Left" : "Right", geo.cx, geo.cy + geo.r + 10, C,
            { size: 12, align: "center", colour: C.gold });
          // The clarity: eight pips.
          var x = geo.cx + geo.r + 30;
          k.text(g, "Clarity", x, geo.cy - 6, C, { size: 13 });
          var gap = Math.max(14, Math.min(22, (W - x - 70) / PIPS));
          for (var i = 0; i < PIPS; i++) {
            var f = k.clamp(work * PIPS - i, 0, 1);
            k.pip(g, x + 56 + gap * i, geo.cy - 6, 5, f > 0 ? f : null, C, false);
          }
          if (R.flares) k.text(g, "Splashed " + R.flares + (R.flares === 1 ? " time" : " times"), x, geo.cy + 14, C,
            { size: 12, colour: C.alarm });
          if (ctx.steady) k.text(g, holding ? "Rod in hand" : "Rod down", x, 12, C, { size: 12, colour: holding ? C.gold : C.dim });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down || holding);
        }
      };
    }
  };
})();
