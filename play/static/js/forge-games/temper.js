// Forge minigame: Temper, stop the colour run (blacksmithing UI plan §9, revamp plan §11).
//
// Quenched steel is too brittle; tempering reheats it gently, and the oxide colour on the
// cleaned steel shows how far it has gone (prior art §3.3, Wikipedia's Tempering): faint
// yellow at 176 °C, straw at 205 to 226, brown at 260, purple at 282, blue at 310 to 337,
// grey-blue from 371. The colour runs along the steel; pull it from the heat when the colour
// reaches the band the item needs: straw for an edge, brown to purple for a tool, blue for a
// spring (`tuning.temper`: "edge", "tool" or "spring"; edge by default). Too early and it is
// still brittle; too late and it is soft.
//
// This game has no heat gauge: the forge gauge's bands (dark red to white) are hundreds of
// degrees above tempering, and a needle pinned at its cold end would say nothing. Its own
// track is the gauge here, with the oxide names printed under it, the target band outlined
// and named, and the number in °C. The oxide colours are content, like the heat's: the steel's
// own colour, drawn on the track only.
//
// Input: Space or a click pulls the piece from the heat. Three pieces in turn (`tuning.runs`).
// Steady mode (UI plan §9): the colour run at half speed (`ctx.speed`).
//
// Scoring per piece: 1 in the band's inner half, falling to 0.5 at its rim; outside the band
// nothing. Running 70 °C past the band pulls it for you at no credit. The score is the sum.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  // The track's colours: Wikipedia's tempering table (prior art §3.3), as oxide on bright steel.
  var OXIDE = [
    [150, "#c9c4b8"], [176, "#e7d8a0"], [205, "#dcbf6a"], [226, "#c79a3f"], [260, "#8f5a2c"],
    [282, "#6d3b6e"], [310, "#2f3f8f"], [337, "#4f7fc0"], [371, "#7d8fa0"], [400, "#8d98a2"]
  ];
  var NAMES = [["Straw", 176, 240], ["Brown", 240, 272], ["Purple", 272, 300], ["Blue", 300, 360], ["Grey", 360, 400]];
  var TARGETS = {
    edge: { band: [205, 235], word: "Straw, for an edge" },
    tool: { band: [258, 290], word: "Brown to purple, for a tool" },
    spring: { band: [305, 340], word: "Blue, for a spring" }
  };
  var LO = 150, HI = 400;

  defs.temper = {
    id: "temper",
    track: "forge",
    name: "Temper",
    first: "Watch the colour run. Pull it from the heat when it reaches the named band.",
    hint: function () { return "Space or click to pull it"; },
    KEYS: ["Space"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "forge.temper", miss: "forge.strike.miss" },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var tg = TARGETS[ctx.tuning.temper] || TARGETS.edge;
      var mid = (tg.band[0] + tg.band[1]) / 2, half = (tg.band[1] - tg.band[0]) / 2 * ctx.band(1);
      var band = [mid - half, mid + half];
      var runs = Math.round(k.clamp(+ctx.tuning.runs || 3, 1, 5));
      // The run reaches the band's middle about 1.6s after the piece goes in, whatever the
      // target, so a spring is not three times the wait of an edge.
      var rate = (mid - LO) / 1.6 * ctx.speed;
      // A piece run well past the band is soft whatever happens next: it is pulled for the
      // player 70 °C past the band, so an idle run does not sit through the whole track.
      var over = Math.min(HI, band[1] + 70);
      var res = [], c = LO, pause = 0, t = 0;

      function pull(auto) {
        if (res.length >= runs || pause > 0) return;
        var q = 0;
        if (!auto && c >= band[0] && c <= band[1]) {
          var d = Math.abs(c - mid), iw = half * 0.5;
          q = d <= iw ? 1 : 1 - 0.5 * ((d - iw) / (half - iw));
        }
        res.push(q);
        if (q > 0) ctx.hit(q, 60, 30, "spark"); else ctx.miss();
        pause = 0.45; c = LO;
      }

      return {
        duration: runs * ((over - LO) / rate + 0.5) + 0.3,
        tick: function (dt, now) {
          t = now;
          if (pause > 0) { pause = Math.max(0, pause - dt); return; }
          if (res.length >= runs) return;
          c += rate * dt;
          if (c >= over) pull(true);
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          pull(false);
          return true;
        },
        progress: function () { return res.length / runs; },
        state: function () {
          return { temp_c: c, band: band.slice(), target: ctx.tuning.temper && TARGETS[ctx.tuning.temper] ? ctx.tuning.temper : "edge",
            piece: Math.min(res.length + 1, runs), pieces: runs, waiting: pause > 0 };
        },
        score: function () { var s = 0; res.forEach(function (q) { s += q; }); return s / runs; },
        done: function () { return res.length >= runs && pause <= 0; },
        draw: function (g, W, H) {
          var x0 = 14, x1 = Math.max(x0 + 120, W - 84), ty = Math.max(28, Math.round(H / 2 - 12)), th = 10;
          var X = function (v) { return x0 + (x1 - x0) * k.clamp((v - LO) / (HI - LO), 0, 1); };
          var grad = g.createLinearGradient(x0, 0, x1, 0);
          OXIDE.forEach(function (s) { grad.addColorStop((s[0] - LO) / (HI - LO), s[1]); });
          g.fillStyle = grad; g.fillRect(x0, ty, x1 - x0, th);
          g.save(); g.strokeStyle = C.edge; g.strokeRect(x0 + 0.5, ty + 0.5, x1 - x0 - 1, th - 1); g.restore();
          var ax = X(band[0]), zx = X(band[1]);
          g.save(); g.strokeStyle = C.gold; g.lineWidth = 2; g.strokeRect(ax, ty - 4, zx - ax, th + 8); g.restore();
          k.notch(g, ax, ty - 5, Math.PI / 2, 5, C.gold);
          k.notch(g, zx, ty - 5, Math.PI / 2, 5, C.gold);
          k.text(g, tg.word, x0, ty - 16, C, { size: 13, colour: C.ink });
          g.save(); g.font = "13px " + C.body;
          // The colour names, those the target band touches first, so a name that collides
          // with a neighbour is never the one the player is aiming for.
          var spans = [];
          NAMES.map(function (n, i) { return { n: n, i: i, hit: n[2] > band[0] && n[1] < band[1] }; })
            .sort(function (a, b) { return (b.hit ? 1 : 0) - (a.hit ? 1 : 0) || a.i - b.i; })
            .forEach(function (o) {
              var n = o.n, cx = (X(n[1]) + X(n[2])) / 2, w = g.measureText(n[0]).width, l = cx - w / 2;
              for (var i = 0; i < spans.length; i++) if (l < spans[i][1] + 6 && l + w > spans[i][0] - 6) return;
              spans.push([l, l + w]);
              g.fillStyle = o.hit ? C.ink : C.dim; g.textBaseline = "middle"; g.fillText(n[0], l, ty + th + 12);
            });
          g.restore();
          var nx = X(c);
          g.save(); g.lineCap = "round";
          g.strokeStyle = C.sunk; g.lineWidth = 4; g.beginPath(); g.moveTo(nx, ty - 6); g.lineTo(nx, ty + th + 4); g.stroke();
          g.strokeStyle = C.ink; g.lineWidth = 2; g.beginPath(); g.moveTo(nx, ty - 6); g.lineTo(nx, ty + th + 4); g.stroke();
          g.restore();
          k.text(g, Math.round(c / 5) * 5 + " °C", x1 + 10, ty + th / 2, C, { size: 13, colour: C.ink });
          for (var r = 0; r < runs; r++) k.pip(g, x1 + 16 + r * 18, ty + th + 26, 5, r < res.length ? res[r] : null, C, r === res.length);
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
