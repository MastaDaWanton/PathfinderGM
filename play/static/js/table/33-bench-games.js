// The herbalism bench, part 33: the minigame strip's shared frame, and `window.BenchGames`.
// Classic script, but everything here lives in one IIFE: the only names it leaves on
// `window` are `BenchGames` and the `BenchGameDefs` registry the nine game files fill.
//
// THE CONTRACT (docs/herbalism-contracts.md §5.2). D's bench calls
//   BenchGames.play({method, part, tuning, mount, stage, steady, reducedMotion, onScore})
// after a successful Craft roll and posts the score it resolves with to /api/bench/finish.
// The score is 0..1 and nothing more: the SERVER turns it into a tier against the
// character's ceiling (revamp plan §9.2, the same shape as "no model authors a number"), so
// this file never names a final tier. While the game runs, the strip shows a live band word
// only when the server passed its names in `tuning.names`; without them the band is five
// pips and the time thread, and no word at all. When the game ends the word is cleared.
//
// THE FRAME (UI plan §6.4). 120px tall: the meter on the left (a canvas each game draws
// on), the input hint in the centre, the live band on the right in 34px Cinzel, and a 2px
// time thread along the top. The thread has no background track: a filled-track bar is
// one of the design skill's banned shapes, and a line that grows says "time" on its own.
//
// HOW A GAME PLUGS IN. Each file under js/bench-games/ registers a definition on
// `window.BenchGameDefs[method]` and is loaded BEFORE this file (contracts §1, script
// order). A definition is {name, first, hint(steady), KEYS, HOLDS, HOLDS_STEADY,
// create(ctx)}; create returns {duration, tick, draw, down, up?, move?, state, score,
// done, progress?, button?}. The frame owns everything a game should not each re-solve:
// the loop, input, pause, the first-time card, sound, the stage hand-off, particles.
//
// RULES THE FRAME ENFORCES FOR EVERY GAME, so no game file can quietly break them:
//   - ONE LOOP, AND ONLY WHILE A GAME RUNS. `requestAnimationFrame` is called here and
//     nowhere else; `loop` reschedules itself only in the "play" phase, so finishing,
//     stopping or pausing ends it. An idle bench draws zero frames (UI plan §10, §13.6).
//   - STEADY MODE HAS NO HOLDS. Potion Craft added Auto Hold after "a significant number
//     of players reported getting hand fatigue" holding the mouse to grind and stir
//     (docs/herbalism-prior-art.md, devlog #14), and Xbox guideline 107 asks for every
//     hold to have a single-press form (The Long Dark turns every hold into a press). In
//     Steady mode no game ever hears a key or button RELEASE: the frame drops them (look
//     for STEADY-NO-RELEASE below), so the only thing a game can do with an input is
//     respond to the press, which makes every hold a toggle by construction.
//   - KEY REPEAT IS NOT A PRESS. A held key's auto-repeat would turn a hold into mashing;
//     `e.repeat` is ignored everywhere.
//   - LOSING FOCUS PAUSES. A game running while the player is in another window would
//     score them for time they were not there for (UI plan §7). Window blur and a hidden
//     tab pause; Space or a click carries on.
//   - THE CURSOR IS NOT THE AIM. The app draws a candle cursor whose hotspot the owner saw
//     drift in 0.2.2; every game that aims draws its own reticle where the pointer
//     really is (UI plan §9).
//   - REDUCED MOTION: no shake and no particles. The meters still move, because they are
//     the game (WCAG 2.3.3 exempts motion that is essential).
(function () {
  "use strict";

  var DEFS = window.BenchGameDefs = window.BenchGameDefs || {};
  var METHODS = ["grind", "mix", "brew", "dry", "reduce", "extract", "infuse", "steep",
    "neutralize"];

  // theme-v2.css values, used only when a token cannot be read (a page without the theme,
  // a detached mount). tests/test_bench_games.py checks every one is the theme's own.
  var FALLBACK = {
    ink: "#e8ddc4", dim: "#93866e", ash: "#6d675e", gold: "#ddc48e", goldDim: "#7d6845",
    accent: "#cfa964", candle: "#f0c070", alarm: "#b0483c", edge: "#3a2f22",
    sunk: "#0b0908", panel: "#161210", ember: "255, 176, 84"
  };
  var TOKENS = {
    ink: "--ink", dim: "--dim", ash: "--ash", gold: "--gold", goldDim: "--gold-dim",
    accent: "--accent", candle: "--candle", alarm: "--alarm", edge: "--edge",
    sunk: "--sunk", panel: "--panel", ember: "--ember"
  };

  var run = null;          // the one live game; null when the strip is idle
  var tickSoundAt = 0;     // bench.tick is rationed: at most one every 400ms

  // --- small helpers ---------------------------------------------------------------------
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function sound(name, o) {
    try { if (window.Sound && typeof window.Sound.play === "function") window.Sound.play(name, o || {}); }
    catch (e) { /* sound is optional; a broken bus must never stop a game */ }
  }

  // The first-time card stays until the player has scored 0.6 or better in that game. The
  // storage can be absent or throw (a private window, blocked site data), and then the card
  // simply shows again: never an error.
  function seenGet(method) {
    try { return window.localStorage.getItem("pgm.games.seen." + method) === "1"; }
    catch (e) { return false; }
  }
  function seenSet(method) {
    try { window.localStorage.setItem("pgm.games.seen." + method, "1"); }
    catch (e) { /* the card will show again next time; that is all */ }
  }

  function colours(node) {
    var cs = window.getComputedStyle(node), c = {};
    Object.keys(TOKENS).forEach(function (k) {
      var v = cs.getPropertyValue(TOKENS[k]).trim();
      c[k] = v || FALLBACK[k];
    });
    c.display = cs.getPropertyValue("--display").trim() || "\"Cinzel\", serif";
    c.body = cs.getPropertyValue("--body").trim() || "\"Palatino Linotype\", Palatino, serif";
    return c;
  }

  // --- the drawing kit every game shares ------------------------------------------------
  // "Never colour alone" (Game Accessibility Guidelines, vision basic): every zone a game
  // draws is hatched or notched as well as tinted, and every danger zone is cross-hatched
  // with a jagged edge, so a zone reads in greyscale.
  var KIT = {
    clamp: clamp,
    lerp: lerp,
    // A seeded generator (mulberry32), so a harness seed replays the same layout.
    rng: function (seed) {
      var a = (seed >>> 0) || 1;
      return function () {
        a = (a + 0x6D2B79F5) >>> 0;
        var t = a;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
      };
    },
    // A smooth wander in roughly -1..1: three slow sines, no randomness per frame, so the
    // drift can be read and answered rather than being noise.
    drift: function (seed) {
      return function (t) {
        return Math.sin(t * 1.3 + seed) * 0.6 + Math.sin(t * 2.9 + seed * 2.1) * 0.3 +
          Math.sin(t * 0.7 + seed * 0.5) * 0.1;
      };
    },
    // Diagonal hatching inside whatever path `shape(g)` builds.
    hatch: function (g, shape, box, colour, gap, cross, width) {
      g.save();
      g.beginPath(); shape(g); g.clip();
      g.strokeStyle = colour; g.lineWidth = width || 1;
      g.beginPath();
      var x0 = box[0] - box[3], x1 = box[0] + box[2] + box[3];
      for (var x = x0; x <= x1; x += gap) {
        g.moveTo(x, box[1] + box[3]); g.lineTo(x + box[3], box[1]);
        if (cross) { g.moveTo(x, box[1]); g.lineTo(x + box[3], box[1] + box[3]); }
      }
      g.stroke();
      g.restore();
    },
    // An annular wedge (for dials), angles in radians.
    wedge: function (g, cx, cy, r0, r1, a0, a1) {
      g.arc(cx, cy, r1, a0, a1, false);
      g.arc(cx, cy, r0, a1, a0, true);
      g.closePath();
    },
    // A small triangle pointing at (x, y) from direction `ang`: the notch that marks a
    // band's edge as a shape.
    notch: function (g, x, y, ang, size, colour) {
      var s = size || 5;
      g.save();
      g.translate(x, y); g.rotate(ang);
      g.beginPath(); g.moveTo(0, 0); g.lineTo(-s, -s * 0.7); g.lineTo(-s, s * 0.7); g.closePath();
      g.fillStyle = colour; g.fill();
      g.restore();
    },
    // A band on a dial: hatched wedge, edged, with a notch at each end.
    dialBand: function (g, cx, cy, r0, r1, a0, a1, colour, opts) {
      opts = opts || {};
      var box = [cx - r1, cy - r1, r1 * 2, r1 * 2];
      KIT.hatch(g, function (c) { KIT.wedge(c, cx, cy, r0, r1, a0, a1); }, box, colour,
        opts.gap || 5, !!opts.cross, 1);
      g.save();
      g.beginPath(); KIT.wedge(g, cx, cy, r0, r1, a0, a1);
      g.strokeStyle = colour; g.lineWidth = 1.2; g.stroke();
      if (opts.jagged) {
        // A saw edge outside the rim: danger reads by its outline, not only its hue.
        g.beginPath();
        var steps = Math.max(3, Math.round((a1 - a0) * r1 / 6));
        for (var i = 0; i <= steps; i++) {
          var a = a0 + (a1 - a0) * i / steps, rr = r1 + (i % 2 ? 5 : 1);
          var px = cx + Math.cos(a) * rr, py = cy + Math.sin(a) * rr;
          if (i) g.lineTo(px, py); else g.moveTo(px, py);
        }
        g.stroke();
      }
      g.restore();
      if (opts.notches) {
        [a0, a1].forEach(function (a) {
          KIT.notch(g, cx + Math.cos(a) * (r1 + 7), cy + Math.sin(a) * (r1 + 7), a + Math.PI,
            5, opts.notchColour || colour);
        });
      }
    },
    // A band on a straight scale, horizontal (x0..x1 at y, thickness h) or, with
    // `vertical`, y0..y1 at x.
    barBand: function (g, x, y, w, h, colour, opts) {
      opts = opts || {};
      KIT.hatch(g, function (c) { c.rect(x, y, w, h); }, [x, y, w, Math.max(w, h)],
        colour, opts.gap || 5, !!opts.cross, 1);
      g.save();
      g.strokeStyle = colour; g.lineWidth = 1.2; g.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
      g.restore();
    },
    diamond: function (g, x, y, s, fill, stroke, lw) {
      g.beginPath();
      g.moveTo(x, y - s); g.lineTo(x + s, y); g.lineTo(x, y + s); g.lineTo(x - s, y);
      g.closePath();
      if (fill) { g.fillStyle = fill; g.fill(); }
      if (stroke) { g.strokeStyle = stroke; g.lineWidth = lw || 1.2; g.stroke(); }
    },
    // A result pip: a filled diamond for a hit (smaller for a weak one), a hollow diamond
    // struck through for a miss, a dot for one still to come. Shape first, colour second.
    pip: function (g, x, y, s, res, C, current) {
      if (res === null || res === undefined) {
        if (current) KIT.diamond(g, x, y, s + 1, null, C.gold, 1.4);
        else { g.beginPath(); g.arc(x, y, 1.8, 0, Math.PI * 2); g.fillStyle = C.ash; g.fill(); }
        return;
      }
      if (res === "miss" || res <= 0) {
        KIT.diamond(g, x, y, s, null, C.ash, 1.2);
        g.beginPath(); g.moveTo(x - s * 0.9, y - s * 0.9); g.lineTo(x + s * 0.9, y + s * 0.9);
        g.strokeStyle = C.alarm; g.lineWidth = 1.6; g.stroke();
        return;
      }
      KIT.diamond(g, x, y, s, null, C.goldDim, 1);
      KIT.diamond(g, x, y, s * (0.45 + 0.55 * res), C.gold, null);
    },
    // The aim mark: drawn where the pointer really is, so the candle cursor's art never
    // decides a score.
    reticle: function (g, x, y, C, solid) {
      g.save();
      g.strokeStyle = C.gold; g.lineWidth = 1.2;
      g.beginPath(); g.arc(x, y, 7, 0, Math.PI * 2); g.stroke();
      g.beginPath();
      g.moveTo(x - 11, y); g.lineTo(x - 4, y); g.moveTo(x + 4, y); g.lineTo(x + 11, y);
      g.moveTo(x, y - 11); g.lineTo(x, y - 4); g.moveTo(x, y + 4); g.lineTo(x, y + 11);
      g.stroke();
      if (solid) { g.beginPath(); g.arc(x, y, 2.5, 0, Math.PI * 2); g.fillStyle = C.gold; g.fill(); }
      g.restore();
    },
    // A ring closing on a mark (grind's strike, steep's seal). `r` is the ring's radius
    // now; [rOut, rIn] the window, drawn as a hatched annulus.
    ring: function (g, cx, cy, rm, r, rOut, rIn, C, inWindow) {
      KIT.hatch(g, function (c) {
        c.arc(cx, cy, rOut, 0, Math.PI * 2, false); c.arc(cx, cy, Math.max(0.5, rIn), Math.PI * 2, 0, true);
      }, [cx - rOut, cy - rOut, rOut * 2, rOut * 2], C.goldDim, 4, false, 1);
      g.save();
      g.strokeStyle = C.goldDim; g.lineWidth = 1;
      g.beginPath(); g.arc(cx, cy, rOut, 0, Math.PI * 2); g.stroke();
      g.beginPath(); g.arc(cx, cy, Math.max(0.5, rIn), 0, Math.PI * 2); g.stroke();
      // The mark: a circle with four notches, the strike point.
      g.strokeStyle = C.gold; g.lineWidth = 1.5;
      g.beginPath(); g.arc(cx, cy, rm, 0, Math.PI * 2); g.stroke();
      for (var i = 0; i < 4; i++) {
        var a = i * Math.PI / 2;
        g.beginPath();
        g.moveTo(cx + Math.cos(a) * (rm - 4), cy + Math.sin(a) * (rm - 4));
        g.lineTo(cx + Math.cos(a) * (rm + 4), cy + Math.sin(a) * (rm + 4));
        g.stroke();
      }
      g.strokeStyle = inWindow ? C.gold : C.ink; g.lineWidth = inWindow ? 2.6 : 1.8;
      g.beginPath(); g.arc(cx, cy, Math.max(1, r), 0, Math.PI * 2); g.stroke();
      g.restore();
    },
    text: function (g, str, x, y, C, opts) {
      opts = opts || {};
      g.save();
      g.font = (opts.size || 13) + "px " + (opts.display ? C.display : C.body);
      g.fillStyle = opts.colour || C.dim;
      g.textAlign = opts.align || "left";
      g.textBaseline = opts.baseline || "middle";
      g.fillText(str, x, y);
      g.restore();
    },
    // A flame drawn as three tongues: tall while the fire is fed, low when banked, so the
    // input's state shows as a shape as well as in the word under it.
    flame: function (g, x, y, size, lit, C) {
      var h = size * (lit ? 1 : 0.45);
      g.save();
      g.strokeStyle = lit ? C.candle : C.ash; g.lineWidth = 1.5;
      [-0.5, 0, 0.5].forEach(function (o, i) {
        var hh = h * (i === 1 ? 1 : 0.7), bx = x + o * size * 0.6;
        g.beginPath();
        g.moveTo(bx - size * 0.16, y);
        g.quadraticCurveTo(bx - size * 0.2, y - hh * 0.6, bx, y - hh);
        g.quadraticCurveTo(bx + size * 0.2, y - hh * 0.6, bx + size * 0.16, y);
        g.stroke();
      });
      g.beginPath(); g.moveTo(x - size * 0.6, y + 2); g.lineTo(x + size * 0.6, y + 2);
      g.strokeStyle = C.goldDim; g.stroke();
      g.restore();
    }
  };

  // --- heat (forge games only) ---------------------------------------------------------------
  // The named bands on the gauge: Chapman's table (Workshop Technology, 1972, via
  // docs/blacksmithing-prior-art.md §3.1), its nine names merged to the five the UI plan §6.4
  // prints, because nine labels do not fit under a 300px bar and a smith says "cherry" for
  // both cherry and light cherry. Below 594 °C steel shows no useful colour ("black heat").
  // These colours are CONTENT, like a material's swatch: they are the metal's own light and
  // appear only on the gauge's scale, never on chrome (UI plan §4).
  var HEAT_NAMES = [
    { name: "Dark red", lo: 594, hi: 815 },
    { name: "Cherry", lo: 815, hi: 982 },
    { name: "Orange", lo: 982, hi: 1093 },
    { name: "Yellow", lo: 1093, hi: 1315 },
    { name: "White", lo: 1315, hi: 1700 }
  ];
  var HEAT_STOPS = [
    [450, "#1c0805"], [600, "#4a0d06"], [760, "#8a1a0a"], [850, "#b3260e"], [940, "#d8441a"],
    [1040, "#ef7a22"], [1150, "#f6b443"], [1280, "#f9de8a"], [1350, "#fff3d6"], [1700, "#fffaf0"]
  ];
  var GAUGE_H = 32;            // px the gauge takes from the foot of the meter
  var REHEAT_S = 1.5;          // a reheat: about a second and a half in the fire (UI plan §7.2)
  var NARROW = 0.8;            // `narrow_window` metal: the band at 0.8 (blacksmith.json traits)

  function finite(v) { return typeof v === "number" && isFinite(v); }

  // The metal's heat for one game. `spec` is the game's own default (its HEAT), `given` the
  // server's opts.heat; every field the server sends wins. The band is widened about its
  // middle by `scale` (the generous start, the server's band scale, Steady's factor), but
  // never into the burning zone: a band pushed up against the burn grows downward instead.
  //
  // Cooling is Newton's law toward the room, so a white-hot bar loses heat faster than a
  // dull red one, as the metal does; `cool_rate` is the °C per second at the band's middle.
  // Steady mode halves it (UI plan §7.2), and narrow-window metal cools a quarter faster
  // (§7.2: "faster for narrow_window metals"). A reheat pulls the heat toward the hearth's
  // over REHEAT_S seconds and is counted: the server charges world minutes for each
  // (revamp plan §11), which is why play() resolves with `reheats`.
  function makeHeat(spec, given, steady, scale, narrow) {
    given = given || {};
    var b = Array.isArray(given.band) && given.band.length === 2 && finite(+given.band[0]) &&
      finite(+given.band[1]) && +given.band[1] > +given.band[0]
      ? [+given.band[0], +given.band[1]] : spec.band.slice();
    var burn = finite(given.burn_c) ? +given.burn_c : (finite(spec.burn_c) ? spec.burn_c : null);
    var mid = (b[0] + b[1]) / 2, half = (b[1] - b[0]) / 2 * scale * (steady ? (spec.steadyBand || 1) : 1);
    var band = [mid - half, mid + half];
    if (burn != null && band[1] > burn - 5) { band[0] -= band[1] - (burn - 5); band[1] = burn - 5; }
    var hearth = finite(given.hearth_c) ? +given.hearth_c : spec.hearth_c;
    var start = finite(given.start_c) ? +given.start_c
      : finite(spec.start_c) ? spec.start_c : band[1] - (band[1] - band[0]) * 0.15;
    var cool = (finite(given.cool_rate) && given.cool_rate >= 0 ? +given.cool_rate : spec.cool_rate) *
      (steady ? 0.5 : 1) * (narrow ? 1.25 : 1);
    var lo = Math.min(550, band[0] - 80), hi = Math.max(1400, (burn != null ? burn : band[1]) + 90, hearth + 30);
    var h = {
      label: spec.label || "Heat",
      c: start, band: band, burn: burn, hearth: hearth, cool: cool, mid: (band[0] + band[1]) / 2,
      scale: [lo, hi], reheats: 0, reheating: 0, quiet: false,
      canReheat: spec.reheat !== false,
      coldHint: spec.coldHint || "Reheat: R",
      step: function (dt) {
        if (h.reheating > 0) {
          h.c += (h.hearth - h.c) * (1 - Math.exp(-dt / (REHEAT_S / 3)));
          h.reheating = Math.max(0, h.reheating - dt);
          return;
        }
        if (h.quiet) return;   // the game holds the heat itself (the quench bath)
        h.c -= h.cool * (h.c - 20) / Math.max(1, h.mid - 20) * dt;
        if (h.c < 20) h.c = 20;
      },
      reheat: function () {
        if (!h.canReheat || h.reheating > 0 || h.quiet) return false;
        h.reheating = REHEAT_S;
        h.reheats++;
        return true;
      },
      add: function (deg) { h.c = clamp(h.c + deg, 20, h.scale[1]); },
      inBand: function () { return h.c >= h.band[0] && h.c <= h.band[1]; },
      // 1 in the band's inner `inner` share, falling to `edge` at its rim, 0 outside.
      quality: function (inner, edge) {
        if (!h.inBand()) return 0;
        var hw = (h.band[1] - h.band[0]) / 2, d = Math.abs(h.c - (h.band[0] + h.band[1]) / 2);
        var iw = hw * (inner == null ? 0.5 : inner);
        return d <= iw ? 1 : 1 - (1 - (edge == null ? 0.5 : edge)) * ((d - iw) / Math.max(1e-6, hw - iw));
      },
      status: function () {
        if (h.reheating > 0) return "reheating";
        if (h.quiet) return "in";
        if (h.burn != null && h.c >= h.burn) return "burn";
        if (h.c > h.band[1]) return "hot";
        if (h.c < h.band[0]) return "cold";
        return "in";
      }
    };
    return h;
  }

  // What the hint says. The heat speaks first, in words (UI plan §6.4: "Reheat: R" when the
  // metal leaves the band), because a strike out of band is wasted whatever the game's own
  // hint says; then the game's live hint, if it has one; then its fixed one.
  var HEAT_WORDS = { reheating: "Reheating", hot: "Too hot: let it cool", burn: "Burning: let it cool" };
  function hintNow(r) {
    if (r.heat) {
      var s = r.heat.status();
      if (s === "cold") return r.heat.coldHint;
      if (HEAT_WORDS[s]) return HEAT_WORDS[s];
    }
    var live = r.game && r.game.hint ? r.game.hint() : null;
    return live || r.def.hint(r.steady);
  }

  function degrees(c) {
    var n = String(Math.round(c / 5) * 5);
    return n.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + " °C";
  }

  // The gauge (UI plan §6.4), drawn across the foot of the meter: the blackbody scale as a
  // bar, the burning zone cross-hatched with a saw edge, the target band outlined in gold with
  // a notch at each end (shape, not only colour), the needle in ink on a dark keel so it reads
  // on the white end too, and the five band names under the bar. A name that would collide
  // with one already drawn is left out, target bands first, so the band that matters is the
  // one that is always named.
  function drawGauge(r, g, W, top) {
    var H = r.heat, C = r.C, x0 = 10, x1 = W - 10;
    if (x1 - x0 < 80) return;
    var lo = H.scale[0], hi = H.scale[1];
    var X = function (c) { return x0 + (x1 - x0) * clamp((c - lo) / (hi - lo), 0, 1); };
    var by = top + 6, bh = 9;
    var grad = g.createLinearGradient(x0, 0, x1, 0);
    HEAT_STOPS.forEach(function (s) { grad.addColorStop(clamp((s[0] - lo) / (hi - lo), 0, 1), s[1]); });
    g.fillStyle = grad;
    g.fillRect(x0, by, x1 - x0, bh);
    g.save(); g.strokeStyle = C.edge; g.lineWidth = 1; g.strokeRect(x0 + 0.5, by + 0.5, x1 - x0 - 1, bh - 1); g.restore();
    if (H.burn != null) {
      var bx = X(H.burn);
      KIT.barBand(g, bx, by - 2, Math.max(2, x1 - bx), bh + 4, C.alarm, { cross: true, gap: 4 });
      g.save(); g.strokeStyle = C.alarm; g.lineWidth = 1.2; g.beginPath();
      for (var i = 0, n = Math.max(2, Math.round((x1 - bx) / 5)); i <= n; i++) {
        var px = bx + (x1 - bx) * i / n, py = by - 3 - (i % 2 ? 4 : 0);
        if (i) g.lineTo(px, py); else g.moveTo(px, py);
      }
      g.stroke(); g.restore();
    }
    var ax = X(H.band[0]), zx = X(H.band[1]);
    g.save();
    g.strokeStyle = C.gold; g.lineWidth = 2;
    g.strokeRect(ax, by - 4, Math.max(2, zx - ax), bh + 8);
    g.restore();
    KIT.notch(g, ax, by - 5, Math.PI / 2, 5, C.gold);
    KIT.notch(g, zx, by - 5, Math.PI / 2, 5, C.gold);
    // The needle.
    var nx = X(H.c);
    g.save();
    g.lineCap = "round";
    g.strokeStyle = C.sunk; g.lineWidth = 4;
    g.beginPath(); g.moveTo(nx, by - 6); g.lineTo(nx, by + bh + 4); g.stroke();
    g.strokeStyle = C.ink; g.lineWidth = 2;
    g.beginPath(); g.moveTo(nx, by - 6); g.lineTo(nx, by + bh + 4); g.stroke();
    g.restore();
    KIT.diamond(g, nx, by - 7, 3.5, C.ink, C.sunk, 1);
    // The names, the target's first.
    g.save();
    g.font = "13px " + C.body;
    var spans = [], order = HEAT_NAMES.map(function (b, i) {
      var hit = b.hi > H.band[0] && b.lo < H.band[1];
      return { b: b, i: i, hit: hit };
    }).sort(function (p, q) { return (q.hit ? 1 : 0) - (p.hit ? 1 : 0) || p.i - q.i; });
    order.forEach(function (o) {
      var a = Math.max(o.b.lo, lo), z = Math.min(o.b.hi, hi);
      if (z <= a) return;
      var cx = (X(a) + X(z)) / 2, w = g.measureText(o.b.name).width;
      var l = clamp(cx - w / 2, x0, x1 - w), rr = l + w;
      for (var k = 0; k < spans.length; k++) if (l < spans[k][1] + 6 && rr > spans[k][0] - 6) return;
      spans.push([l, rr]);
      g.fillStyle = o.hit ? C.ink : C.dim;
      g.textBaseline = "middle";
      g.fillText(o.b.name, l, by + bh + 12);
      // A tick at the band's lower edge, so the name sits between marks on the scale.
      g.fillRect(X(a), by + bh, 1, 3);
    });
    g.restore();
  }

  // --- DOM ---------------------------------------------------------------------------------
  function build(mount, def, steady) {
    var old = mount.querySelector(".bench-game");
    if (old && old.parentNode) old.parentNode.removeChild(old);

    var root = el("div", "bench-game");
    root.setAttribute("role", "group");
    root.setAttribute("aria-label", def.name + ", the minigame");
    root.dataset.method = def.id;

    var thread = el("div", "bench-game__thread");
    thread.setAttribute("aria-hidden", "true");

    var meter = el("div", "bench-game__meter");
    var canvas = el("canvas", "bench-game__canvas");
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", def.first);
    meter.appendChild(canvas);

    var hint = el("div", "bench-game__hint");
    var hintText = el("p", "bench-game__hint-text", def.hint(steady));
    var tools = el("div", "bench-game__tools");
    if (steady) tools.appendChild(el("span", "bench-game__steady", "Steady"));
    var help = el("button", "bench-game__help", "?");
    help.type = "button";
    help.setAttribute("aria-label", "How to play");
    tools.appendChild(help);
    hint.appendChild(hintText);
    hint.appendChild(tools);

    var tier = el("div", "bench-game__tier");
    tier.setAttribute("aria-hidden", "true");
    var word = el("span", "bench-game__word");
    var band = el("span", "bench-game__band");
    for (var i = 0; i < 5; i++) band.appendChild(el("i"));
    tier.appendChild(word);
    tier.appendChild(band);

    var live = el("span", "bench-game__live");
    live.setAttribute("aria-live", "polite");

    var card = el("div", "bench-game__card");
    card.hidden = true;
    var cardText = el("p", "bench-game__card-text");
    var cardSub = el("p", "bench-game__card-sub");
    card.appendChild(cardText);
    card.appendChild(cardSub);

    root.appendChild(thread);
    root.appendChild(meter);
    root.appendChild(hint);
    root.appendChild(tier);
    root.appendChild(live);
    root.appendChild(card);
    mount.appendChild(root);

    return { root: root, thread: thread, meter: meter, canvas: canvas, hint: hint, tier: tier,
      hintText: hintText, tools: tools, help: help, word: word, band: band, live: live,
      card: card, cardText: cardText, cardSub: cardSub };
  }

  // --- the loop ---------------------------------------------------------------------------
  function size(r) {
    var w = r.dom.canvas.clientWidth, h = r.dom.canvas.clientHeight;
    var dpr = window.devicePixelRatio || 1;
    if (w !== r.W || h !== r.H || dpr !== r.dpr) {
      r.W = w; r.H = h; r.dpr = dpr;
      r.dom.canvas.width = Math.max(1, Math.round(w * dpr));
      r.dom.canvas.height = Math.max(1, Math.round(h * dpr));
    }
  }

  function paint(r) {
    size(r);
    var g = r.g;
    g.setTransform(r.dpr, 0, 0, r.dpr, 0, 0);
    g.clearRect(0, 0, r.W, r.H);
    if (r.W < 2 || r.H < 2) return;
    r.game.draw(g, r.W, r.H);
    if (r.particles.length) drawParticles(r, g);
    var p = r.game.progress ? r.game.progress(r.t) : r.t / r.game.duration;
    r.dom.thread.style.transform = "scaleX(" + clamp(p, 0, 1).toFixed(4) + ")";
  }

  function loop(now) {
    var r = run;
    // The loop ends itself: outside the "play" phase nothing reschedules it.
    if (!r || r.phase !== "play") { if (r) r.raf = 0; return; }
    var dt = clamp((now - r.last) / 1000, 0, 0.05);
    r.last = now;
    r.t += dt;
    r.game.tick(dt, r.t);
    stepParticles(r, dt);
    paint(r);
    feed(r);
    if (r.game.done() || r.t >= r.game.duration) { finish(r, false); return; }
    r.raf = window.requestAnimationFrame(loop);
  }

  function start(r) {
    r.phase = "play";
    r.dom.card.hidden = true;
    r.dom.root.classList.remove("is-paused");
    r.last = performance.now();
    if (!r.raf) r.raf = window.requestAnimationFrame(loop);
  }

  // Hand the stage its state, the page its score, the listener its band.
  function feed(r) {
    if (r.stage) {
      try { r.stage.update(r.game.state()); }
      catch (e) { r.stage = null; if (window.console) console.warn("bench stage update failed; the strip plays on", e); }
    }
    var s = clamp(r.game.score(), 0, 1);
    if (Math.abs(s - r.lastScore) >= 0.004) {
      r.lastScore = s;
      if (r.onScore) { try { r.onScore(s); } catch (e) { if (window.console) console.warn(e); } }
    }
    showBand(r, s);
  }

  // The live band. Bounds come from `tuning.bands` (ascending lower bounds) when the
  // server sends them, else even fifths or even shares of `tuning.names`. A 0.015 margin
  // either side of each bound keeps the word from flickering when a needle sits on an
  // edge, and the live region speaks only when the band really changes.
  function bandOf(r, s) {
    var b = r.bounds, i = r.band < 0 ? 0 : r.band;
    while (i + 1 < b.length && s >= b[i + 1] + 0.015) i++;
    while (i > 0 && s < b[i] - 0.015) i--;
    return i;
  }
  function showBand(r, s) {
    var i = bandOf(r, s);
    if (i === r.band) return;
    var up = i > r.band;
    r.band = i;
    if (r.names) {
      r.dom.word.textContent = r.names[i];
      r.dom.live.textContent = r.names[i];
      // 34px Cinzel is the design's size; a long name the server sends ("Flawless +2")
      // steps down rather than spilling out of its column.
      r.dom.word.style.fontSize = "";
      var room = r.dom.tier.clientWidth - 28, wide = r.dom.word.scrollWidth;
      if (room > 0 && wide > room) r.dom.word.style.fontSize = Math.max(18, Math.floor(34 * room / wide)) + "px";
    } else {
      var pips = r.dom.band.children;
      for (var k = 0; k < pips.length; k++) pips[k].className = k <= i ? "is-on" : "";
      r.dom.live.textContent = "Rough quality " + (i + 1) + " of " + r.bounds.length;
    }
    // A tier up brightens the word once for 180ms (UI plan §10, "Tier up"); reduced
    // motion moves it instantly.
    if (up && i > 0 && !r.reduced && r.dom.tier.animate) {
      r.dom.tier.animate([{ opacity: 0.55 }, { opacity: 1 }], { duration: 180, easing: "ease-out" });
    }
  }

  // --- particles (never under reduced motion) -------------------------------------------
  function burst(r, x, y, kind, n) {
    if (r.reduced || x == null) return;
    var C = r.C, col = kind === "spark" ? C.candle : kind === "steam" ? C.dim : C.gold;
    for (var i = 0; i < (n || 8); i++) {
      var a = r.rng() * Math.PI * 2, sp = 30 + r.rng() * 70;
      r.particles.push({ x: x, y: y, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp - (kind === "steam" ? 40 : 10),
        life: 0.35 + r.rng() * 0.3, age: 0, col: col, sq: kind === "grit" });
    }
    if (r.particles.length > 120) r.particles.splice(0, r.particles.length - 120);
  }
  function stepParticles(r, dt) {
    for (var i = r.particles.length - 1; i >= 0; i--) {
      var p = r.particles[i];
      p.age += dt;
      if (p.age >= p.life) { r.particles.splice(i, 1); continue; }
      p.x += p.vx * dt; p.y += p.vy * dt; p.vy += 120 * dt;
    }
  }
  function drawParticles(r, g) {
    g.save();
    r.particles.forEach(function (p) {
      g.globalAlpha = 1 - p.age / p.life;
      g.fillStyle = p.col;
      if (p.sq) g.fillRect(p.x - 1.5, p.y - 1.5, 3, 3);
      else { g.beginPath(); g.arc(p.x, p.y, 1.6, 0, Math.PI * 2); g.fill(); }
    });
    g.restore();
  }
  function jolt(r) {
    if (r.reduced || !r.dom.root.animate) return;
    // Transform only, 90ms: feedback that a strike landed, never a shake that moves text
    // the player is reading for long.
    r.dom.root.animate([{ transform: "translateY(0)" }, { transform: "translateY(2px)" },
      { transform: "translateY(0)" }], { duration: 90, easing: "ease-out" });
  }

  // --- the context a game is built with -------------------------------------------------
  function makeCtx(r, opts) {
    var tuning = opts.tuning || {};
    var d = clamp(tuning.difficulty == null ? 0.5 : +tuning.difficulty || 0, 0, 1);
    var steady = !!opts.steady;
    // Generous to begin with: at the middle difficulty a window is 1.1x the base and at
    // the easiest 1.35x. Stardew's creator said fishing "starts too hard" and the early
    // bar should have been bigger (docs/herbalism-prior-art.md); the server's difficulty
    // can only take the window down to 0.85x.
    var baseWin = lerp(1.35, 0.85, d);
    var baseSpeed = lerp(0.85, 1.15, d);
    var seed = tuning.seed != null ? (tuning.seed | 0) : ((Math.random() * 1e9) | 0);
    return {
      method: r.def.id,
      tuning: tuning,
      part: opts.part || tuning.part || "leaf",
      steady: steady,
      reduced: r.reduced,
      difficulty: d,
      // Steady mode (UI plan §9): windows x1.6 and speeds halved. A game whose Steady
      // column says otherwise uses baseWin or baseSpeed instead.
      win: baseWin * (steady ? 1.6 : 1),
      baseWin: baseWin,
      speed: baseSpeed * (steady ? 0.5 : 1),
      baseSpeed: baseSpeed,
      seconds: clamp(+tuning.seconds || 6, 3, 12),
      kit: KIT,
      C: r.C,
      rng: KIT.rng(seed),
      seed: seed,
      pointer: r.pointer,
      // `index` (optional) names WHICH piece on the tool the hit or miss belongs to, for a
      // game with several (Dry's bundles). Without it the stage guessed from the last state
      // it was sent, and that state is a frame behind the press: the hit showed on the
      // bundle turned before. Added 2026-10-02; a stage that ignores it still works.
      hit: function (strength, x, y, kind, index) {
        var s = clamp(strength == null ? 1 : strength, 0, 1);
        r.hits++;
        sound("bench.hit." + r.def.id, { volume: 0.5 + 0.5 * s });
        if (r.stage) {
          try { if (typeof index === "number") r.stage.hit(s, index); else r.stage.hit(s); }
          catch (e) { r.stage = null; }
        }
        burst(r, x, y, kind || "grit", Math.round(4 + 8 * s));
        if (s >= 0.5) jolt(r);
      },
      miss: function (index) {
        r.misses++;
        sound("bench.miss." + r.def.id);
        if (r.stage) {
          try { if (typeof index === "number") r.stage.miss(index); else r.stage.miss(); }
          catch (e) { r.stage = null; }
        }
      },
      tick: function () {
        var now = performance.now();
        if (now - tickSoundAt < 400) return;
        tickSoundAt = now;
        sound("bench.tick");
      }
    };
  }

  // --- input ------------------------------------------------------------------------------
  function keyName(e) {
    if (e.key === " " || e.key === "Spacebar") return "Space";
    if (/^Numpad[0-9]$/.test(e.code || "")) return e.code.slice(6);
    return e.key;
  }
  function typing(t) {
    if (!t || !t.tagName) return false;
    var n = t.tagName;
    return n === "INPUT" || n === "TEXTAREA" || n === "SELECT" || t.isContentEditable;
  }
  // Handled keys go no further: Space would press a focused button, the arrows scroll,
  // and 1-9 and the arrows are the bench's own method keys (UI plan §6.1). Listening in the
  // capture phase is what lets the game have them first while it runs.
  function swallow(e) { e.preventDefault(); e.stopPropagation(); }

  function onKeyDown(e) {
    var r = run;
    if (!r || typing(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
    var key = keyName(e);
    if (key === "Escape") return;   // D owns Esc: "Stop and keep what you have?"
    if (r.phase === "card" || r.phase === "paused") {
      if (key === "Space" || key === "Enter") { swallow(e); if (!e.repeat) carryOn(r); }
      else if (r.def.KEYS.indexOf(key) >= 0) swallow(e);
      return;
    }
    if (r.phase !== "play" || r.def.KEYS.indexOf(key) < 0) return;
    swallow(e);
    if (e.repeat || r.held.keys[key]) return;   // auto-repeat is a hold, not a run of presses
    r.held.keys[key] = true;
    r.game.down({ src: "key", key: key });
  }

  function onKeyUp(e) {
    var r = run;
    if (!r || typing(e.target)) return;
    var key = keyName(e);
    if (r.def.KEYS.indexOf(key) < 0 && key !== "Space" && key !== "Enter") return;
    if (r.phase !== "done") swallow(e);
    var was = !!r.held.keys[key];
    delete r.held.keys[key];
    if (r.steady) return;   // STEADY-NO-RELEASE: in Steady mode no game hears a release
    if (was && r.phase === "play" && r.game.up) r.game.up({ src: "key", key: key });
  }

  function locate(r, e) {
    var b = r.dom.canvas.getBoundingClientRect();
    var x = e.clientX - b.left, y = e.clientY - b.top;
    r.pointer.x = x; r.pointer.y = y;
    r.pointer.inside = x >= 0 && y >= 0 && x <= b.width && y <= b.height;
    return r.pointer;
  }

  function onPointerDown(e) {
    var r = run;
    if (!r) return;
    if (e.pointerType === "mouse" && e.button !== 0) return;
    if (e.target.closest && e.target.closest("button")) return;   // ? and Pull off are buttons
    e.preventDefault();
    if (r.phase === "card" || r.phase === "paused") { carryOn(r); return; }
    if (r.phase !== "play") return;
    var p = locate(r, e);
    p.down = true;
    r.held.pointer = true;
    r.game.down({ src: "pointer", x: p.x, y: p.y, inside: p.inside });
  }

  function onPointerMove(e) {
    var r = run;
    if (!r) return;
    var p = locate(r, e);
    if (r.phase === "play" && r.game.move) r.game.move({ src: "pointer", x: p.x, y: p.y, inside: p.inside, down: p.down });
  }

  function onPointerUp(e) {
    var r = run;
    if (!r || !r.held.pointer) return;
    var p = locate(r, e);
    r.held.pointer = false;
    p.down = false;
    if (r.steady) return;   // STEADY-NO-RELEASE: in Steady mode no game hears a release
    if (r.phase === "play" && r.game.up) r.game.up({ src: "pointer", x: p.x, y: p.y, inside: p.inside });
  }

  // A blur or a pause takes every held input with it: the key-up for a key held while the
  // window lost focus never arrives, and a game would go on feeding a fire nobody holds.
  function releaseHeld(r) {
    var keys = Object.keys(r.held.keys);
    r.held.keys = {};
    var wasPointer = r.held.pointer;
    r.held.pointer = false;
    r.pointer.down = false;
    if (r.steady || !r.game.up) return;   // STEADY-NO-RELEASE
    keys.forEach(function (k) { r.game.up({ src: "key", key: k }); });
    if (wasPointer) r.game.up({ src: "pointer", x: r.pointer.x, y: r.pointer.y, inside: false });
  }

  function onBlur() { if (run) pauseRun(run, "Paused. Press Space to carry on."); }
  function onVisibility() { if (run && document.hidden) pauseRun(run, "Paused. Press Space to carry on."); }

  function bind(r) {
    r.on = {
      down: onPointerDown, help: function (e) {
        e.preventDefault();
        if (r.phase === "play") {
          pauseRun(r, null);
          showCard(r, r.def.first, "Space or click to carry on");
        }
      },
      button: function (e) {
        e.preventDefault();
        if (r.phase === "play" && r.game.button) r.game.button.press();
      }
    };
    window.addEventListener("keydown", onKeyDown, true);
    window.addEventListener("keyup", onKeyUp, true);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerUp);
    window.addEventListener("blur", onBlur);
    document.addEventListener("visibilitychange", onVisibility);
    r.dom.root.addEventListener("pointerdown", r.on.down);
    r.dom.help.addEventListener("click", r.on.help);
    if (r.dom.button) r.dom.button.addEventListener("click", r.on.button);
    if (window.ResizeObserver) {
      // A resize repaints once; it never starts a loop.
      r.ro = new ResizeObserver(function () { if (r.phase !== "play") { paint(r); } });
      r.ro.observe(r.dom.meter);
    }
  }

  function unbind(r) {
    window.removeEventListener("keydown", onKeyDown, true);
    window.removeEventListener("keyup", onKeyUp, true);
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
    window.removeEventListener("pointercancel", onPointerUp);
    window.removeEventListener("blur", onBlur);
    document.removeEventListener("visibilitychange", onVisibility);
    if (r.on) {
      r.dom.root.removeEventListener("pointerdown", r.on.down);
      r.dom.help.removeEventListener("click", r.on.help);
      if (r.dom.button) r.dom.button.removeEventListener("click", r.on.button);
    }
    if (r.ro) { r.ro.disconnect(); r.ro = null; }
  }

  // --- phases -----------------------------------------------------------------------------
  function showCard(r, text, sub) {
    r.dom.cardText.textContent = text;
    r.dom.cardSub.textContent = sub;
    r.dom.card.hidden = false;
  }

  function carryOn(r) {
    clearTimeout(r.cardTimer);
    if (r.phase === "card" || r.phase === "paused") start(r);
  }

  function pauseRun(r, text) {
    if (r.phase === "card") { clearTimeout(r.cardTimer); return; }   // the card now waits for a press
    if (r.phase !== "play") return;
    r.phase = "paused";
    if (r.raf) { window.cancelAnimationFrame(r.raf); r.raf = 0; }
    releaseHeld(r);
    r.dom.root.classList.add("is-paused");
    if (text) showCard(r, text, "Or click the strip");
  }

  function finish(r, stopped) {
    if (r.phase === "done") return;
    if (r.raf) { window.cancelAnimationFrame(r.raf); r.raf = 0; }
    clearTimeout(r.cardTimer);
    r.phase = "done";
    unbind(r);
    var score = clamp(+r.game.score() || 0, 0, 1);
    // One last still picture: the particles go, the meter stays as it ended.
    r.particles.length = 0;
    paint(r);
    if (!stopped) r.dom.thread.style.transform = "scaleX(1)";
    r.dom.card.hidden = true;
    r.dom.root.classList.remove("is-paused");
    r.dom.root.classList.add("is-done");
    // The live word goes: the tier this run earns is the server's to name (contracts §3.4).
    r.dom.word.textContent = "";
    Array.prototype.forEach.call(r.dom.band.children, function (p) { p.className = ""; });
    r.dom.hintText.textContent = stopped ? "Stopped" : "Done";
    if (r.dom.button) r.dom.button.disabled = true;
    if (r.stage) {
      try { r.stage.update(r.game.state()); r.stage.end(); } catch (e) { /* the result still stands */ }
    }
    if (r.onScore) { try { r.onScore(score); } catch (e) { if (window.console) console.warn(e); } }
    if (!stopped && score >= 0.6) seenSet(r.def.id);
    if (run === r) run = null;
    r.resolve({ score: score, stopped: !!stopped, hits: r.hits, misses: r.misses });
  }

  // --- the API ----------------------------------------------------------------------------
  function play(opts) {
    opts = opts || {};
    if (run) finish(run, true);   // one game at a time: a new play stops the old one
    var def = DEFS[opts.method];
    if (!def) return Promise.reject(new Error("No minigame for the method " + opts.method));
    if (!opts.mount) return Promise.reject(new Error("BenchGames.play needs a mount element"));

    var reduced = opts.reducedMotion;
    if (reduced == null) {
      reduced = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    }
    var steady = !!opts.steady;
    var dom = build(opts.mount, def, steady);
    if (reduced) dom.root.classList.add("is-still");
    var tuning = opts.tuning || {};
    var names = Array.isArray(tuning.names) && tuning.names.length ? tuning.names.slice() : null;
    var n = names ? names.length : 5;
    var bounds = Array.isArray(tuning.bands) && tuning.bands.length === n ? tuning.bands.slice()
      : Array.apply(null, Array(n)).map(function (_, i) { return i / n; });
    if (names) dom.band.hidden = true; else dom.word.hidden = true;

    return new Promise(function (resolve) {
      var r = {
        def: def, dom: dom, stage: opts.stage || null, onScore: opts.onScore || null,
        steady: steady, reduced: !!reduced, names: names, bounds: bounds, band: -1,
        lastScore: -1, t: 0, last: 0, raf: 0, phase: "card", cardTimer: 0, hits: 0, misses: 0,
        held: { keys: {}, pointer: false }, pointer: { x: -1, y: -1, inside: false, down: false },
        particles: [], W: 0, H: 0, dpr: 1, resolve: resolve, rng: KIT.rng(7)
      };
      r.C = colours(dom.root);
      r.g = dom.canvas.getContext("2d");
      r.game = def.create(makeCtx(r, opts));
      if (r.game.button) {
        var b = el("button", "bench-game__act", r.game.button.label);
        b.type = "button";
        dom.tools.insertBefore(b, dom.help);
        dom.button = b;
      }
      run = r;
      bind(r);
      paint(r);
      showBand(r, 0);
      if (r.stage) { try { r.stage.update(r.game.state()); } catch (e) { r.stage = null; } }
      // The first-time card: two seconds, then the game starts by itself; Space or a click
      // starts it sooner. Shown until the player scores 0.6 or better in this game.
      if (!seenGet(def.id)) {
        showCard(r, def.first, "Space or click to begin");
        r.cardTimer = setTimeout(function () { if (run === r && r.phase === "card") start(r); }, 2000);
      } else {
        start(r);
      }
    });
  }

  function stop() { if (run) finish(run, true); }
  function pause() { if (run) pauseRun(run, "Paused. Press Space to carry on."); }
  function resume() { if (run && (run.phase === "paused" || run.phase === "card")) carryOn(run); }

  window.BenchGames = {
    play: play,
    stop: stop,
    pause: pause,
    resume: resume,
    methods: METHODS.slice(),
    running: function () { return !!run; },
    kit: KIT
  };
})();
