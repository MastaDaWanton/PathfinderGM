// Forge minigame: Quench, plunge and hold (blacksmithing UI plan §9, revamp plan §11).
//
// Lift the blank from the fire, watch it cool in the air, and plunge it while it is at
// hardening heat; then hold it under through the boil until the bath goes quiet, and lift.
// The plunge band is 780 to 870 °C: just past the point where steel goes non-magnetic (iron's
// Curie point is about 770 °C, the old smith's "hot enough to harden", prior art §3.1) and
// within cherry red. Above the band the blank warps and may crack; below it, it will not
// harden. The hold is the vapour jacket: at first the steel "is fully surrounded by vapor
// which insulates it" (§3.2), then the boil breaks and the bath quiets. How long that takes
// depends on the bath: brine breaks the jacket fastest, oil slowest (Grossmann H: brine
// 2.0 to 5.0, water 0.9 to 2.0, oils 0.25 to 0.8), so the hold's target is short in brine
// and long in oil (`tuning.bath`, water by default).
//
// The frame owns the heat until the plunge (gauge, R to reheat, "Reheat: R" when the blank
// cools below the band unplunged); from the plunge the game holds the heat (`heat.quiet`)
// and drops it toward the bath's.
//
// Input: press (Space, or the mouse button) to plunge, release to lift. Steady mode (UI plan
// §9): toggles instead of holds, one press plunges and the next lifts (the frame never hands
// a Steady game a release), and the bands are x1.5: the plunge band through the HEAT's
// steadyBand, the hold's window through `ctx.band(1.5)`.
//
// Scoring: half the plunge (the heat's quality, 1 in the band's inner 60%, 0.5 at its rim;
// a plunge above the band earns 0.3, below it nothing), half the lift (1 inside the hold's
// inner 50%, falling to 0.5 at its edge; lifted too early, the steel is soft: half of that
// falling to 0; held far too long it is lifted for you at no credit).
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var HOLD = { brine: 1.3, water: 1.7, oil: 2.4 };   // seconds under, by bath

  defs.quench = {
    id: "quench",
    track: "forge",
    name: "Quench",
    first: "Plunge while it glows in the band. Hold it under until the boil quiets, then lift.",
    hint: function (steady) { return steady ? "Space or click to plunge, again to lift" : "Hold Space or the mouse to plunge"; },
    KEYS: ["Space", "R"],
    HOLDS: ["Space", "pointer"],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "forge.quench", miss: "forge.strike.miss", reheat: "forge.bellows" },
    HEAT: { label: "Plunge heat", band: [780, 870], hearth_c: 950, start_c: 930, cool_rate: 40,
      steadyBand: 1.5 },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, heat = ctx.heat;
      var bath = HOLD[ctx.tuning.bath] ? ctx.tuning.bath : "water";   // the frame voices hits by tuning.bath too
      var target = HOLD[bath], hw = 0.45 * ctx.band(1.5);
      var phase = "air", under = 0, qp = null, ql = null, t = 0;
      var geo = { x: 20, y: 40 };

      function plunge() {
        if (phase !== "air" || heat.reheating > 0) return;
        var s = heat.status();
        qp = s === "in" ? heat.quality(0.6, 0.5) : s === "hot" ? 0.3 : 0;
        phase = "under"; under = 0;
        heat.quiet = true;
        // The hiss comes with the hit (SOUNDS.hit, by bath); a plunge that earns nothing still
        // hisses, since the steel still met the water.
        if (qp > 0) ctx.hit(qp, geo.x + 40, geo.y, "steam"); else { ctx.cue("hit", { bath: bath }); ctx.miss(); }
      }
      function lift(auto) {
        if (phase !== "under") return;
        var d = under - target, a = Math.abs(d), inner = hw * 0.5;
        if (auto) ql = 0;
        else if (a <= inner) ql = 1;
        else if (a <= hw) ql = 1 - 0.5 * ((a - inner) / (hw - inner));
        else if (d < 0) ql = Math.max(0, 0.5 * (1 - (a - hw) / target));
        else ql = 0;
        phase = "out";
        if (ql >= 0.5) ctx.hit(ql, geo.x + 40, geo.y, "steam"); else ctx.miss();
      }

      return {
        duration: Math.max(ctx.seconds, 5) + target + 1.5,
        tick: function (dt, now) {
          t = now;
          if (phase === "under") {
            under += dt;
            heat.c += (40 - heat.c) * (1 - Math.exp(-dt / 0.7));   // the bath takes it
            if (under > target + hw * 3) lift(true);
          }
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          if (phase === "air") plunge();
          else if (phase === "under" && ctx.steady) lift(false);
          return true;
        },
        up: function () { if (phase === "under") lift(false); return true; },
        hint: function () {
          if (phase === "under") return under < target - hw ? "Boiling: hold it under" : "Quieting: lift now";
          return phase === "out" ? "Lifted" : null;
        },
        progress: function (now) {
          return phase === "out" ? 1 : phase === "under" ? 0.5 + 0.5 * Math.min(1, under / (target + hw)) : Math.min(0.5, now / 4);
        },
        state: function () {
          return { phase: phase, hot_c: heat.c, in_band: phase === "air" && heat.inBand(), under: under,
            hold: [target - hw, target + hw], bath: bath, jacket: phase === "under" && under < target * 0.6 };
        },
        score: function () { return 0.5 * (qp || 0) + 0.5 * (ql || 0); },
        done: function () { return phase === "out"; },
        draw: function (g, W, H) {
          geo.y = H / 2 - 2;
          // The trough, and the blank above it or in it.
          var tx = geo.x, tw = Math.min(90, W * 0.24), ty = geo.y + 2;
          g.save();
          g.strokeStyle = C.goldDim; g.lineWidth = 1.2;
          g.beginPath(); g.moveTo(tx, ty - 6); g.lineTo(tx + 6, ty + 14); g.lineTo(tx + tw - 6, ty + 14); g.lineTo(tx + tw, ty - 6); g.stroke();
          g.strokeStyle = C.dim; g.beginPath(); g.moveTo(tx + 3, ty); g.lineTo(tx + tw - 3, ty); g.stroke();
          var by = phase === "under" ? ty + 4 : ty - 20;
          g.strokeStyle = C.ink; g.lineWidth = 2;
          g.beginPath(); g.moveTo(tx + 14, by); g.lineTo(tx + tw - 14, by); g.stroke();
          g.restore();
          // The hold meter: time under against the hold's window, notched at both ends.
          var mx = tx + tw + 22, mw = Math.max(80, W - mx - 14), my = geo.y - 6, span = target + hw * 3;
          var X = function (s) { return mx + mw * k.clamp(s / span, 0, 1); };
          g.save(); g.strokeStyle = C.edge; g.strokeRect(mx + 0.5, my + 0.5, mw, 10); g.restore();
          k.barBand(g, X(target - hw), my, X(target + hw) - X(target - hw), 11, C.goldDim, { gap: 4 });
          k.notch(g, X(target - hw), my - 3, Math.PI / 2, 5, C.gold);
          k.notch(g, X(target + hw), my - 3, Math.PI / 2, 5, C.gold);
          var ux = X(under);
          g.save(); g.strokeStyle = phase === "under" ? C.ink : C.ash; g.lineWidth = 2;
          g.beginPath(); g.moveTo(ux, my - 4); g.lineTo(ux, my + 14); g.stroke(); g.restore();
          k.pip(g, mx + 6, my + 26, 5, qp, C, phase === "air");
          k.pip(g, mx + 24, my + 26, 5, ql, C, phase === "under");
          k.text(g, "Under " + bath, mx + 38, my + 26, C, { size: 13 });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
