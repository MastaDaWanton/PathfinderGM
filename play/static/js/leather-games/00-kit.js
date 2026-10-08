// Leather minigames, the shared part (leather UI plan §6.4 and §9, contracts §11.1).
//
// Loaded before every leather game file, and all of them before table/33-bench-games.js (the
// frame), exactly as the herb, forge, enchant and alchemy games are. It leaves one name on
// `window`: `LeatherGames`, which the games and the leather shell share.
//
// THE KEYS. Each game registers on `window.BenchGameDefs["leather.<method>"]`, not on the bare
// method name: the registry is one object for every bench, and the forge registered "assemble"
// first (js/forge-games/assemble.js). A second `defs.assemble` would replace the smith's game
// without a word, and the forge would then play lacing. One prefix for all of them is a rule
// the shell can follow with no exception list: `BenchGames.play({method:
// LeatherGames.key(method), band: roll.band, tuning: roll.tuning, ...})`. The cut test that a
// bark tannage plays at Collect (revamp plan §8.3) is `LeatherGames.cutTest`.
//
// THE GAUGE. Every leather game carries a BAND (the frame's band gauge): the server's band from
// rules/leatherworker.py `band_for` is drawn as a bar in its real unit, and the game moves the
// needle (`ctx.gauge.v`). What each game makes of the server's `drift` is written in its own
// header, because the one number means a different thing for a knife (a hand's sway) than for
// a liquor (the tannin the hide draws out of it).
//
// NO GAME HOLDS. Every input in every leather game is a press, in both modes, so Steady mode
// (where the frame drops every release) loses nothing and no game needs a long press (UI plan
// §9: "No game needs a long press").
(function () {
  "use strict";

  var METHODS = ["flense", "salt", "tan", "curry", "cut", "stitch", "harden", "tool", "dye",
    "laminate", "assemble"];

  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }

  window.LeatherGames = {
    // The methods that have a game. Grade has none (UI plan §9: "Grade has no minigame (the
    // forge's Assay and herb tasting have none)"), and the harvest game belongs to the harvest
    // lane.
    methods: METHODS.slice(),
    key: function (method) { return "leather." + String(method || ""); },
    cutTest: "leather.cut-test",

    // A hand on a variable: the needle goes where the hand aims, eased (no momentum: the
    // alchemist's lesson that where the needle is heading is where it stops), plus the hand's
    // own sway, a smooth wander the player can read and answer (KIT.drift: three slow sines,
    // never per-frame noise). Up and Down nudge the aim a step; the pointer's place across the
    // meter sets it, mapped onto the gauge's own scale so the pointer stands over the reading
    // it asks for. Steady mode halves the sway.
    steer: function (ctx, G, o) {
      o = o || {};
      var lo = G.scale[0], hi = G.scale[1], span = hi - lo;
      var amp = (o.wander != null ? o.wander : G.drift * 2) * (ctx.steady ? 0.5 : 1);
      var D = ctx.kit.drift(o.seed != null ? o.seed : ctx.rng() * 10);
      var S = {
        aim: G.v, base: G.v, sway: 0, step: o.step || span * 0.06, tau: o.tau || 0.12,
        nudge: function (dir) { S.aim = clamp(S.aim + dir * S.step, lo, hi); },
        point: function (x, W) { S.aim = clamp(lo + (x - 10) / Math.max(1, W - 20) * span, lo, hi); },
        tick: function (dt, t) {
          S.base += (S.aim - S.base) * (1 - Math.exp(-dt / S.tau));
          S.sway = amp * D(t * (o.rate || 1));
          G.v = clamp(S.base + S.sway, lo, hi);
        }
      };
      return S;
    },

    // A stretched hide, flesh side up: a body with four leg tabs and a neck, the shape every
    // leather game draws its work on (the stage shows the real one; this is the strip's sign of
    // it). Line only, in the chrome's gold-dim: a hide's own colour is the stage's content.
    hide: function (g, cx, cy, w, h, C, o) {
      o = o || {};
      var rx = w / 2, ry = h / 2;
      g.save();
      g.beginPath();
      g.moveTo(cx - rx * 0.62, cy - ry * 0.7);
      g.lineTo(cx - rx * 0.95, cy - ry);            // foreleg
      g.lineTo(cx - rx * 0.8, cy - ry * 0.45);
      g.quadraticCurveTo(cx - rx * 1.02, cy, cx - rx * 0.8, cy + ry * 0.45);
      g.lineTo(cx - rx * 0.95, cy + ry);            // hind leg
      g.lineTo(cx - rx * 0.62, cy + ry * 0.7);
      g.quadraticCurveTo(cx, cy + ry * 0.98, cx + rx * 0.62, cy + ry * 0.7);
      g.lineTo(cx + rx * 0.95, cy + ry);
      g.lineTo(cx + rx * 0.8, cy + ry * 0.45);
      g.quadraticCurveTo(cx + rx * 1.02, cy, cx + rx * 0.8, cy - ry * 0.45);
      g.lineTo(cx + rx * 0.95, cy - ry);
      g.lineTo(cx + rx * 0.62, cy - ry * 0.7);
      g.quadraticCurveTo(cx, cy - ry * 0.98, cx - rx * 0.62, cy - ry * 0.7);
      g.closePath();
      if (o.fill) { g.fillStyle = o.fill; g.globalAlpha = o.alpha == null ? 1 : o.alpha; g.fill(); g.globalAlpha = 1; }
      g.strokeStyle = o.stroke || C.goldDim; g.lineWidth = 1.4; g.stroke();
      g.restore();
    },

    // A row of result pips (the kit's diamonds: a hit filled by its quality, a miss struck
    // through, one to come a dot), `list` the results so far and `n` how many there will be.
    pips: function (k, g, x, y, list, n, C, gap) {
      gap = gap || 16;
      for (var i = 0; i < n; i++) {
        var r = i < list.length ? list[i] : null;
        k.pip(g, x + i * gap, y, 5, r, C, i === list.length);
      }
    },

    // A short ruler with a marker: a hairline scale with end ticks and a diamond at `v` (0..1).
    // Not a filled bar: the design skill bans a filled track, and a marker on a scale reads as
    // a reading, which is what Set, Size and Taken are. `vertical` stands it up.
    ruler: function (k, g, x, y, len, v, C, colour, vertical) {
      g.save(); g.strokeStyle = C.edge; g.lineWidth = 1;
      g.beginPath();
      if (vertical) { g.moveTo(x, y); g.lineTo(x, y + len); g.moveTo(x - 3, y); g.lineTo(x + 3, y); g.moveTo(x - 3, y + len); g.lineTo(x + 3, y + len); }
      else { g.moveTo(x, y); g.lineTo(x + len, y); g.moveTo(x, y - 3); g.lineTo(x, y + 3); g.moveTo(x + len, y - 3); g.lineTo(x + len, y + 3); }
      g.stroke(); g.restore();
      var f = clamp(v, 0, 1);
      if (vertical) k.diamond(g, x, y + len * (1 - f), 4, colour, C.sunk, 1);
      else k.diamond(g, x + len * f, y, 4, colour, C.sunk, 1);
    },

    clamp: clamp
  };
})();
