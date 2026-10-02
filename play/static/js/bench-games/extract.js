// Bench minigame: Extract, the clean cut (revamp plan §9.3, UI plan §9).
//
// A dotted incision path crosses the part, with four nodes on it (diamonds). Cut along it
// at an even pace and stop at each node. Going too fast nicks the gland: the pace needle
// runs into the hatched "too fast" zone and that stretch of the cut is marked nicked. Running
// straight past a node loses it.
//
// Input:
//   - Mouse or touch: drag the knife along the path (it follows your aim, never faster than
//     a blade can), or click once to take the knife, move, and click again to lift it. To
//     stop at a node, stop moving (a fifth of a second of stillness) or lift the knife.
//   - Keyboard: hold Right (or Space) to advance; release at the node.
//   - Steady mode: Right, Space or a click toggles the cut on and off, the cut runs at half
//     speed, and the path pauses at each node for you (UI plan §9): the knife stops on the
//     node by itself and waits for the next press.
//
// Scoring per node: a stop inside the node's window earns 1 falling to 0.5 at its edge,
// halved if that stretch was nicked; a node run past earns 0. The score is the sum over all
// nodes.
//
// State for the stage: {path, at, pace, nicked} as contracts §5.1 has it. The nodes are not
// in that shape, so the stage cannot draw them; noted in the lane's hand-back.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};

  defs.extract = {
    id: "extract",
    name: "Extract",
    first: "Cut along the path and stop at each node.",
    hint: function (steady) {
      return steady ? "Space, Right or click to cut. It stops at each node" : "Hold Right or drag. Stop at each node";
    },
    KEYS: ["ArrowRight", "Space"],
    HOLDS: ["ArrowRight", "Space"],
    HOLDS_STEADY: [],
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var nodes = [0.25, 0.5, 0.75, 0.97];
      var res = nodes.map(function () { return null; });
      var nicked = nodes.map(function () { return false; });
      var vk = 1 / (0.62 * ctx.seconds) * ctx.speed;    // the blade's even pace, path units/s
      var w = 0.042 * ctx.win;                           // a node's stop window
      var phase = ctx.rng() * Math.PI * 2;
      var at = 0, pace = 0, t = 0;
      var advancing = false, grip = false, moved = 0, still = 0, fast = 0, lastX = null;
      var geo = { x0: 24, x1: 300, cy: 70, amp: 14, W: 0, H: 0 };
      var pathN = [];

      function seg() { for (var i = 0; i < nodes.length; i++) if (res[i] === null) return i; return nodes.length; }
      function px(u) { return geo.x0 + (geo.x1 - geo.x0) * u; }
      function py(u) { return geo.cy + geo.amp * Math.sin(u * Math.PI * 3 + phase); }
      function layout(W, H) {
        if (geo.W === W && geo.H === H) return;
        geo.W = W; geo.H = H;
        geo.x0 = 24; geo.x1 = Math.max(160, W - 24); geo.cy = H / 2 + 12; geo.amp = Math.min(16, H / 2 - 30);
        pathN = [];
        for (var i = 0; i <= 40; i++) { var u = i / 40; pathN.push([px(u) / W, py(u) / H]); }
      }
      // The u on the path under a screen x.
      function project(x) { return k.clamp((x - geo.x0) / (geo.x1 - geo.x0), 0, 1); }

      // A stop: score the nearest unresolved node if the knife is inside its window.
      function stopHere() {
        var i = seg();
        if (i >= nodes.length) return;
        var d = Math.abs(at - nodes[i]);
        if (d <= w) {
          res[i] = (1 - 0.5 * (d / w)) * (nicked[i] ? 0.5 : 1);
          ctx.hit(res[i], px(at), py(at), "spark");
        }
      }

      if (!pathN.length) layout(320, 120);

      return {
        duration: ctx.seconds * (ctx.steady ? 2.2 : 1.15) / ctx.baseSpeed,
        tick: function (dt, now) {
          t = now;
          var i = seg(), prev = at, rate = 0;
          if (advancing) {
            at = Math.min(1, at + vk * dt);
          } else if (grip && ctx.pointer.x >= 0) {
            var target = project(ctx.pointer.x), want = Math.max(0, target - at);
            var step = Math.min(want, vk * 2.5 * dt);
            at = Math.min(1, at + step);
            // Faster than 1.6x the even pace for a tenth of a second nicks this stretch.
            if (dt > 0 && want / dt > vk * 1.6 && step > 0) fast += dt; else fast = 0;
            if (fast > 0.1 && i < nodes.length && !nicked[i]) { nicked[i] = true; ctx.miss(); }
            // A fifth of a second of stillness inside a node's window is a stop.
            if (dt > 0 && step / dt < vk * 0.15) still += dt; else still = 0;
            if (still >= 0.2 && i < nodes.length && Math.abs(at - nodes[i]) <= w) { stopHere(); still = 0; }
          }
          rate = dt > 0 ? (at - prev) / dt : 0;
          pace = k.clamp(rate / (vk * 1.6), 0, 1);
          i = seg();
          if (i < nodes.length) {
            if (ctx.steady && prev < nodes[i] && at >= nodes[i]) {
              // Steady mode: the path pauses at the node for you.
              at = nodes[i]; advancing = false; grip = false;
              res[i] = nicked[i] ? 0.5 : 1;
              ctx.hit(res[i], px(at), py(at), "spark");
            } else if (at > nodes[i] + w) {
              res[i] = 0; ctx.miss();   // ran straight through it
            }
          }
        },
        down: function (inp) {
          if (inp.src === "key") {
            if (ctx.steady) { advancing = !advancing; if (!advancing) stopHere(); }
            else advancing = true;
            return true;
          }
          if (!inp.inside) return true;
          if (grip) { grip = false; stopHere(); return true; }
          grip = true; moved = 0; lastX = inp.x; still = 0; fast = 0;
          return true;
        },
        up: function (inp) {
          if (inp.src === "key") { if (advancing) { advancing = false; stopHere(); } return true; }
          if (grip && moved > 10) { grip = false; stopHere(); }
          return true;
        },
        move: function (inp) {
          if (lastX !== null) moved += Math.abs(inp.x - lastX);
          lastX = inp.x;
        },
        state: function () {
          var i = seg();
          return { path: pathN, at: at, pace: pace, nicked: i < nodes.length ? nicked[i] : nicked[nodes.length - 1] };
        },
        score: function () {
          var s = 0;
          res.forEach(function (q) { if (q) s += q; });
          return s / nodes.length;
        },
        done: function () { return seg() >= nodes.length; },
        draw: function (g, W, H) {
          layout(W, H);
          var u;
          // The path: cut in ink behind the knife, dotted gold ahead of it.
          g.save();
          g.lineWidth = 1.6; g.strokeStyle = C.goldDim; g.setLineDash([3, 4]);
          g.beginPath();
          for (u = at; u <= 1.0001; u += 0.01) { if (u === at) g.moveTo(px(u), py(u)); else g.lineTo(px(u), py(u)); }
          g.stroke();
          g.setLineDash([]); g.strokeStyle = C.ink; g.lineWidth = 2;
          g.beginPath();
          for (u = 0; u <= at; u += 0.01) { if (u === 0) g.moveTo(px(u), py(u)); else g.lineTo(px(u), py(u)); }
          g.lineTo(px(at), py(at));
          g.stroke();
          g.restore();
          // Nicked stretches: short red slashes across the cut.
          nodes.forEach(function (n, j) {
            if (!nicked[j]) return;
            var a = j ? nodes[j - 1] : 0;
            g.save(); g.strokeStyle = C.alarm; g.lineWidth = 1.4;
            for (var v = a + 0.03; v < Math.min(n, at); v += 0.05) {
              g.beginPath(); g.moveTo(px(v) - 3, py(v) - 6); g.lineTo(px(v) + 3, py(v) + 6); g.stroke();
            }
            g.restore();
          });
          // The nodes: hatched windows on the path, diamonds for the node, pips once done.
          var cur = seg();
          nodes.forEach(function (n, j) {
            var xa = px(n - w), xb = px(Math.min(1, n + w));
            if (res[j] === null) {
              k.barBand(g, xa, py(n) - 12, Math.max(3, xb - xa), 24, j === cur ? C.gold : C.goldDim, { gap: 4 });
              k.diamond(g, px(n), py(n), 5, null, j === cur ? C.gold : C.goldDim, 1.4);
            } else {
              k.pip(g, px(n), py(n), 6, res[j] > 0 ? res[j] : "miss", C, false);
            }
          });
          // The knife: a blade pointing along the path, with its own aim ring.
          var kx = px(at), ky = py(at), ang = Math.atan2(py(at + 0.01) - ky, px(at + 0.01) - kx);
          g.save(); g.translate(kx, ky); g.rotate(ang);
          g.beginPath(); g.moveTo(6, 0); g.lineTo(-10, -5); g.lineTo(-10, 2); g.closePath();
          g.fillStyle = C.ink; g.fill(); g.strokeStyle = C.gold; g.lineWidth = 1; g.stroke();
          g.restore();
          if (grip || advancing) { g.beginPath(); g.arc(kx, ky, 9, 0, Math.PI * 2); g.strokeStyle = C.gold; g.lineWidth = 1.2; g.stroke(); }
          if (ctx.pointer.inside && !advancing) k.reticle(g, ctx.pointer.x, ctx.pointer.y, C, grip);
          // The pace gauge: a short scale, "too fast" hatched with a saw edge, a needle.
          var gx = 24, gw = 90, gy = 18;
          k.text(g, "Pace", gx, gy, C, { size: 13 });
          var sx = gx + 40;
          k.barBand(g, sx + gw * 0.8, gy - 5, gw * 0.2, 10, C.alarm, { cross: true, gap: 3 });
          g.save(); g.strokeStyle = C.edge; g.lineWidth = 1.2;
          g.beginPath(); g.moveTo(sx, gy + 5); g.lineTo(sx + gw, gy + 5); g.stroke(); g.restore();
          k.notch(g, sx + gw * pace, gy + 5, -Math.PI / 2, 5, pace > 0.8 ? C.alarm : C.ink);
        }
      };
    }
  };
})();
