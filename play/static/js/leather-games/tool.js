// Leather minigame: Tool, stamping cased leather (leather UI plan §9, revamp plan §11).
//
// Leather is "cased" before it is tooled: wetted, then left until the surface has gone back to
// its natural colour but still feels cool. Too wet and a stamp's impression looks deep, then
// springs back as the leather dries; too dry and the impression is faint and uneven (prior art
// §3.6, Weaver Leather Supply; Tandy Leather, "How to case leather for tooling"; International
// Leather Club, "Preparing leather for stamping or carving"). No published moisture percentage
// exists, so the variable is time since wetting, as the prior art advised: the gauge reads
// minutes since wetting with the server's cased band and its "too dry" band cross-hatched, and
// the leather on the strip lightens as it dries, the real cue.
//
// The drying clock runs at the game's pace (five minutes of drying a second; the strip is a
// compression of a quarter of an hour, as the forge's quench is of a real one); the server's
// `drift` is how unevenly it dries, ±minutes. Steady mode (UI plan §9): the drying at half the
// pace. Nothing is held.
//
// Input: Space or a click strikes the stamp; W wets it again (back to just wetted). A strike
// takes a fifth of a second; a press during it does nothing.
//
// Scoring: six stamps along the border, each earning the gauge's quality at the strike (1 in
// the band's inner half, 0.6 at its rim; nothing too wet or too dry). The score is the mean of
// the six. The game ends at the sixth.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var N = 6, RATE = 5, STRIKE = 0.2;

  defs["leather.tool"] = {
    id: "leather.tool",
    track: "leather",
    name: "Tool",
    first: "Wait for the colour to come back, then stamp while the leather is still cool. W wets it again.",
    hint: function () { return "Space or click stamps; W wets it again"; },
    KEYS: ["Space", "W"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "leather.stamp", miss: "leather.stamp", wet: "leather.slosh" },
    BAND: { unit: "minutes", label: "", after: "since wetting", target: [10, 25], fail: [40, 60],
      value_start: 0, drift: 1,
      words: { low: "too wet", in: "cased", high: "drying", fail: "too dry" },
      say: { low: "Too wet: wait for the colour to come back", fail: "Too dry: W wets it again" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, G = ctx.gauge;
      var rate = RATE * ctx.baseSpeed * (ctx.steady ? 0.5 : 1);
      var D = k.drift(ctx.rng() * 10);
      var dry = G.v, res = [], busy = 0, wets = 0, t = 0, lastWord = "";
      var geo = { x: 40, y: 40, gap: 20 };

      function strike() {
        if (busy > 0 || res.length >= N) return;
        busy = STRIKE;
        var q = G.quality(0.5, 0.6), s = G.status();
        res.push(q);
        lastWord = q > 0 ? "" : s === "low" ? "Too wet: it sprang back" : "Too dry: faint";
        if (q > 0) ctx.hit(q, geo.x + geo.gap * (res.length - 1), geo.y, "grit"); else ctx.miss();
      }

      return {
        duration: ctx.seconds * (ctx.steady ? 2.6 : 1.7),
        tick: function (dt, now) {
          t = now; busy = Math.max(0, busy - dt);
          dry = Math.min(G.scale[1], dry + rate * dt);
          G.v = k.clamp(dry + G.drift * D(now), G.scale[0], G.scale[1]);
        },
        down: function (inp) {
          if (inp.src === "key" && inp.key === "W") { dry = 0; wets++; ctx.cue("wet"); return true; }
          if (inp.src === "pointer" && !inp.inside) return false;
          strike();
          return true;
        },
        hint: function () { return busy > 0 && lastWord ? lastWord : null; },
        state: function () {
          return { minutes: G.v, band: G.band.slice(), fail: G.fail, stamps: res.length, of: N, results: res.slice(),
            busy: busy, wets: wets, status: G.status() };
        },
        score: function () { var s = 0; res.forEach(function (q) { s += q; }); return k.clamp(s / N, 0, 1); },
        done: function () { return res.length >= N; },
        draw: function (g, W, H) {
          // The leather: darker the wetter it is (its tone is content, drawn in the dim ink at
          // a strength that falls as it dries), with the border of stamps along its foot.
          var lw = Math.max(80, W - 32), lx = 16, ly = 10, lh = Math.max(30, H - 22);
          var wet = k.clamp(1 - (G.v - G.scale[0]) / Math.max(1, G.band[1] - G.scale[0]), 0, 1);
          g.save(); g.fillStyle = C.dim; g.globalAlpha = 0.08 + 0.32 * wet; g.fillRect(lx, ly, lw, lh); g.restore();
          g.save(); g.strokeStyle = C.goldDim; g.lineWidth = 1.2; g.strokeRect(lx + 0.5, ly + 0.5, lw - 1, lh - 1); g.restore();
          geo.gap = Math.max(14, Math.min(34, (lw - 30) / N)); geo.x = lx + 20; geo.y = ly + lh - 14;
          for (var i = 0; i < N; i++) {
            var px = geo.x + i * geo.gap;
            if (i < res.length) {
              // A stamp's mark: a four-leafed basket stamp, crisp when it took, struck through when not.
              k.diamond(g, px, geo.y, 6, res[i] > 0 ? C.gold : null, res[i] > 0 ? C.gold : C.ash, 1.2);
              if (res[i] <= 0) { g.save(); g.strokeStyle = C.alarm; g.lineWidth = 1.5; g.beginPath(); g.moveTo(px - 6, geo.y - 6); g.lineTo(px + 6, geo.y + 6); g.stroke(); g.restore(); }
            } else { g.beginPath(); g.arc(px, geo.y, 1.8, 0, Math.PI * 2); g.fillStyle = C.ash; g.fill(); }
          }
          k.text(g, wet > 0.66 ? "Dark: still wet" : wet > 0.15 ? "Its colour is coming back" : "Pale: drying out", lx + 8, ly + 10, C, { size: 12 });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
