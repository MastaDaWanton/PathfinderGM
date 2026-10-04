// Forge minigame: Forge, strike while it glows (blacksmithing UI plan §9, revamp plan §11).
//
// A ring closes on the strike mark, as Grind's does; strike as it closes. The difference is
// the heat: the blank cools on the anvil, and a blow only shapes it while it glows in the
// forging band, cherry to orange (815 to 1,092 °C; Chapman's table, prior art §3.1; the UI
// plan §9 row names exactly that band). The frame owns the heat: it cools the metal, draws the
// gauge under this meter, takes R as the reheat and says "Reheat: R" when the metal is too
// cold. While the blank is back in the fire no beat comes (nothing is struck in the fire), so
// a reheat costs its second and a half of game time and nothing else; the server charges the
// world minutes for it.
//
// Input: Space or a click on the strip, one press per beat; R or the Reheat button reheats.
// Nothing is held in either mode. Steady mode (UI plan §9): cooling x0.5 (the frame) and the
// ring's window x1.6 (`ctx.band(1.6)`); the tempo is not halved, because the column does not
// ask for it and a halved tempo would double the time the metal spends cooling per blow.
//
// Scoring per beat: inside the ring's window, 1 in the inner 40% falling to 0.4 at its edge
// (Grind's curve), times the heat: a blow in band keeps it, a blow above the band (too hot,
// yellow) keeps half, and a blow below the band is a miss: cold iron cracks rather than
// moves (prior art §3.1: hot forging is above recrystallisation). The score is the sum over
// the beats, so it climbs as the player plays.
//
// Generous to start (prior art §0 item 5: every shipped smithing minigame was softened
// afterwards; KCD2 patch 1.2 rebalanced its smithing and made cooling readable): the metal
// starts near the top of the band and cools slowly enough that a clean run of eight blows
// needs one reheat at most.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};

  defs.forge = {
    id: "forge",
    track: "forge",
    name: "Forge",
    first: "Strike as the ring closes, while the metal glows in the band.",
    hint: function () { return "Space or click on the ring"; },
    KEYS: ["Space", "R"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "forge.strike.hit", miss: "forge.strike.miss", reheat: "forge.bellows" },
    HEAT: { label: "Forging heat", band: [815, 1092], hearth_c: 1120, cool_rate: 26 },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, heat = ctx.heat;
      var beats = Math.round(k.clamp(+ctx.tuning.beats || 8, 4, 12));
      var period = ((ctx.seconds - 0.4) / beats) / ctx.baseSpeed;
      var markAt = 0.75, tm = markAt * period;
      var hw = Math.min(0.11 * ctx.band(1.6), period * (1 - markAt) * 0.95);
      var res = [];
      for (var i = 0; i < beats; i++) res.push(null);
      var bt = 0, t = 0, flash = { beat: -1, ok: false };
      var geo = { cx: 52, cy: 44, rm: 12, r0: 40 };

      function beatAt(time) { return Math.floor(time / period); }
      function radius(tb) { return geo.r0 - (geo.r0 - geo.rm) * (tb / tm); }
      function resolved() { var n = 0; for (var j = 0; j < beats; j++) if (res[j] !== null) n++; return n; }

      function strike() {
        if (heat.reheating > 0) return;               // the blank is in the fire
        var i = beatAt(bt);
        if (i >= beats || res[i] !== null) return;
        var err = (bt - i * period) - tm;
        if (Math.abs(err) <= hw) {
          var a = Math.abs(err), inner = hw * 0.4;
          var q = a <= inner ? 1 : 1 - 0.6 * ((a - inner) / (hw - inner));
          var s = heat.status();
          if (s === "cold") { res[i] = "miss"; flash = { beat: i, ok: false }; ctx.miss(); return; }
          if (s === "hot" || s === "burn") q *= 0.5;
          res[i] = q;
          flash = { beat: i, ok: true };
          ctx.hit(q, geo.cx, geo.cy, "spark");
          heat.add(-6);                                // each blow takes a little heat
        } else if (err < -hw && err > -3 * hw) {
          res[i] = "miss"; flash = { beat: i, ok: false }; ctx.miss();
        }
      }

      return {
        // Room for two reheats on top of the beats; done() ends it when the last beat is in.
        duration: beats * period + 0.2 + 3.2,
        tick: function (dt, now) {
          t = now;
          if (heat.reheating > 0) return;              // the beat clock waits for the fire
          bt += dt;
          var cur = beatAt(bt);
          for (var i = 0; i < beats; i++) {
            if (res[i] !== null) continue;
            if (i < cur || (i === cur && (bt - i * period) > tm + hw)) {
              res[i] = "miss"; flash = { beat: i, ok: false }; ctx.miss();
            }
          }
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          strike();
          return true;
        },
        progress: function () { return resolved() / beats; },
        state: function () {
          var i = Math.min(beatAt(bt), beats - 1);
          return { ring: k.clamp((bt - i * period) / tm, 0, 1), struck: res[i] !== null,
            beat: i, beats: beats, hot_c: heat.c, in_band: heat.inBand(), reheating: heat.reheating > 0 };
        },
        score: function () {
          var s = 0;
          res.forEach(function (q) { if (typeof q === "number") s += q; });
          return s / beats;
        },
        done: function () { return resolved() >= beats; },
        draw: function (g, W, H) {
          geo.cy = H / 2;
          geo.r0 = Math.min(40, H / 2 - 4);
          geo.rm = Math.min(12, geo.r0 / 3);
          var i = Math.min(beatAt(bt), beats - 1), tb = bt - i * period;
          var rOut = radius(tm - hw), rIn = Math.max(1, radius(tm + hw));
          var inWin = Math.abs(tb - tm) <= hw && res[i] === null && heat.reheating <= 0;
          k.ring(g, geo.cx, geo.cy, geo.rm, Math.max(1, radius(tb)), rOut, rIn, C, inWin);
          if (flash.beat === i) {
            if (flash.ok) {
              g.beginPath(); g.arc(geo.cx, geo.cy, geo.rm - 3, 0, Math.PI * 2); g.fillStyle = C.gold; g.fill();
            } else {
              g.save(); g.strokeStyle = C.alarm; g.lineWidth = 2; g.beginPath();
              g.moveTo(geo.cx - 7, geo.cy - 7); g.lineTo(geo.cx + 7, geo.cy + 7);
              g.moveTo(geo.cx + 7, geo.cy - 7); g.lineTo(geo.cx - 7, geo.cy + 7);
              g.stroke(); g.restore();
            }
          }
          var x0 = 112, gap = Math.min(28, (W - x0 - 12) / beats);
          for (var b = 0; b < beats; b++) {
            k.pip(g, x0 + gap * b + gap / 2, geo.cy - 6, 6, res[b], C, b === i && res[b] === null);
          }
          k.text(g, heat.reheating > 0 ? "In the fire" : "Blow " + Math.min(i + 1, beats) + " of " + beats,
            x0 + gap / 2 - 6, geo.cy + 16, C, { size: 13 });
          // The hammer face: drawn where the pointer really is (the cursor art is not the aim).
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
