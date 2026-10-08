// Leather minigame: Tan, the liquor stepped up (leather UI plan §9, revamp plan §8 and §11).
//
// Bark tanning runs the hide through liquors "running weak to strong" (prior art §3.3, J & FJ
// Baker, Colyton), each stronger one only once the hide has taken the last: a hide thrown into
// strong liquor too soon tans on its face and seals its own middle off (case-hardening, the
// tanner's "drawn grain"). It is done when it is "struck through": cut it, and the tan runs the
// full cross-section (Etherington & Roberts, via prior art §3.3). So the game is two things:
//   - THE STEPS. Space (or a click) steps the liquor up. After each step the hide takes the
//     liquor over most of a second (the meter beside the vat fills); step again once it has
//     taken it. Stepping before then draws the grain (that step earns 0.1). Dawdling long after
//     it has taken costs a little. The liquor weakens as the hide draws tannin out of it (the
//     server's `drift`, strength per second, while the hide is taking). The gauge is the
//     liquor's strength in its words, weak, medium, strong, and a number; the band is strong.
//   - THE CUT TEST. When the server says the tannage is played in two halves (`tuning.
//     two_halves`: anything that waits in a vat or the pack, revamp plan §8.3) the steps are
//     this game, and the cut test is played at Collect as its own game (leather.cut-test).
//     Otherwise (brain tan, worked in one session) the cut comes here: once the liquor is in
//     the band and taken, the tan runs into the hide's section over a second and a half; C, the
//     Cut button, or Space cuts it. A cut before it has run through shows the raw core and how
//     far it got, and costs 0.15; cut again.
//
// Steady mode (UI plan §9): the hide takes each liquor at two thirds of the pace and is ready
// to step once it has taken 60% (not 85%), and the dawdle allowance doubles. The plan's "steps
// auto-advance on a beat" was not built: an advance the player did not press would be the game
// playing itself, and the wider ready mark gives the same relief. Nothing is held.
//
// Scoring: the mean of the steps' credit, times how far into the band the liquor got (full in
// it, the square of the share below it). In one session that is 60% of the score and the cut
// 40% (1, less 0.15 for each early cut, less up to 0.4 for leaving it uncut long after it ran
// through).
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var STEP = 0.17, TAKE = 0.75, DRAWN = 0.1, EARLY = 0.15, RUN = 1.5;

  defs["leather.tan"] = {
    id: "leather.tan",
    track: "leather",
    name: "Tan",
    first: "Step the liquor up, weak to strong. Wait for the hide to take each one before the next.",
    hint: function () { return "Space or click steps the liquor up"; },
    KEYS: ["Space", "C"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "leather.slosh", miss: "leather.slosh", cut: "leather.cut-test" },
    BAND: { unit: "strength", label: "Liquor", target: [0.7, 1.0], fail: null, value_start: 0,
      drift: 0.04, levels: [[0.4, "weak"], [0.7, "medium"], [Infinity, "strong"]],
      words: { low: "weak to medium", in: "strong", high: "" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, G = ctx.gauge;
      var halves = !!ctx.tuning.two_halves;
      var take = TAKE / ctx.baseSpeed * (ctx.steady ? 1.5 : 1);
      var ready = ctx.steady ? 0.6 : 0.85, grace = ctx.steady ? 1.6 : 0.8;
      var steps = [], taken = 1, sinceFull = -0.7, t = 0;      // the first step has a little more grace
      var phase = "steps", front = 0, throughAt = -1, early = 0, cutAt = -1, cutScore = 0, shown = -1;
      var geo = { vx: 40, vy: 44 };

      function inBand() { return G.v >= G.band[0]; }
      function stepUp() {
        if (phase !== "steps") { cut(); return; }
        var q;
        if (taken < ready) { q = DRAWN; ctx.miss(); }
        else { q = 1 - k.clamp((sinceFull - grace) / 1.5, 0, 0.5); ctx.hit(q, geo.vx, geo.vy, "steam"); }
        steps.push(q);
        G.v = k.clamp(G.v + STEP, G.scale[0], G.scale[1]);
        taken = 0; sinceFull = 0;
      }
      function cut() {
        if (phase !== "cut") return;
        ctx.cue("cut");
        if (front >= 1) {
          phase = "over"; cutAt = t;
          cutScore = Math.max(0, 1 - EARLY * early - k.clamp((t - throughAt - 1) / 3, 0, 0.4));
          ctx.hit(cutScore, geo.vx, geo.vy, "grit");
        } else { early++; shown = front; ctx.miss(); }
      }
      function stepScore() {
        if (!steps.length) return 0;
        var s = 0; steps.forEach(function (q) { s += q; });
        var reach = inBand() ? 1 : Math.pow(G.v / Math.max(1e-6, G.band[0]), 2);
        return s / steps.length * reach;
      }

      var game = {
        duration: ctx.seconds * (ctx.steady ? 2.6 : 1.9),
        tick: function (dt, now) {
          t = now;
          if (taken < 1) {
            taken = Math.min(1, taken + dt / take);
            G.v = Math.max(G.scale[0], G.v - G.drift * dt * (ctx.steady ? 0.5 : 1));
          } else sinceFull += dt;
          if (phase === "steps" && inBand() && taken >= 1) {
            if (halves) phase = "over";
            else { phase = "cut"; throughAt = -1; }
          }
          if (phase === "cut" && front < 1) {
            front = Math.min(1, front + dt / RUN);
            if (front >= 1) throughAt = now;
          }
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          if (inp.src === "key" && inp.key === "C") { cut(); return true; }
          stepUp();
          return true;
        },
        hint: function () {
          if (phase === "cut") return shown >= 0 && front < 1 ? "Raw in the middle: " + Math.round(shown * 100) + "% through. Wait"
            : "In the band. C cuts the test";
          if (phase === "over") return null;
          if (taken < ready) return "Taking the liquor: wait";
          return steps.length ? "Taken. Step up" : null;
        },
        state: function () {
          return { strength: G.v, band: G.band.slice(), taken: taken, ready: ready, steps: steps.length,
            credits: steps.slice(), phase: phase, front: front, early: early, halves: halves,
            since_full: sinceFull, through: front >= 1 };
        },
        score: function () {
          var a = stepScore();
          if (halves) return k.clamp(a, 0, 1);
          return k.clamp(0.6 * a + 0.4 * (phase === "over" ? cutScore : 0), 0, 1);
        },
        done: function () { return phase === "over"; },
        draw: function (g, W, H) {
          geo.vx = 44; geo.vy = Math.round(H / 2 + 4);
          // The vat: a tub, the hide in it, the liquor's level by its strength.
          var vw = 56, vh = Math.min(48, H - 22), vx = geo.vx - vw / 2, vy = geo.vy - vh / 2;
          g.save(); g.strokeStyle = C.goldDim; g.lineWidth = 1.5;
          g.strokeRect(vx + 0.5, vy + 0.5, vw, vh); g.restore();
          var lvl = vh * (0.25 + 0.6 * k.clamp(G.v, 0, 1));
          k.barBand(g, vx + 2, vy + vh - lvl, vw - 3, lvl - 1, C.goldDim, { gap: G.v < 0.4 ? 7 : G.v < 0.7 ? 5 : 3 });
          // How much of this liquor the hide has taken, a short vertical meter with the ready mark.
          var mx = vx + vw + 14, mh = vh;
          window.LeatherGames.ruler(k, g, mx + 4, vy, mh, taken, C, taken >= ready ? C.gold : C.dim, true);
          k.notch(g, mx + 14, vy + mh * (1 - ready), Math.PI, 5, C.gold);
          var x = mx + 34;
          k.text(g, steps.length + (steps.length === 1 ? " step" : " steps"), x, 10, C, { size: 12 });
          L_pips(g, x, 30, steps);
          if (phase === "cut" || (phase === "over" && !halves)) {
            // The cross-section: the tan running in from both faces, the raw core between.
            var sx = x, sw = Math.max(60, W - x - 16), sy = geo.vy + 8;
            g.save(); g.strokeStyle = C.goldDim; g.strokeRect(sx + 0.5, sy + 0.5, sw, 10); g.restore();
            var f = shown >= 0 && phase === "cut" ? shown : front;
            k.barBand(g, sx, sy, sw * f / 2, 11, C.gold, { gap: 3 });
            k.barBand(g, sx + sw - sw * f / 2, sy, sw * f / 2, 11, C.gold, { gap: 3 });
            k.text(g, phase === "over" ? "Struck through" : shown >= 0 ? "Raw core" : "The tan runs in", sx, sy + 22, C,
              { size: 12, colour: phase === "over" ? C.ink : C.dim });
          }
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
      function L_pips(g, x, y, list) { window.LeatherGames.pips(k, g, x, y, list, Math.max(5, list.length + 1), C, 15); }
      if (!halves) game.button = { label: "Cut", press: cut };
      return game;
    }
  };
})();
