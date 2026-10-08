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

  // THE FORGE'S GAMES (docs/blacksmithing-contracts.md §11, UI plan §6.4, added 2026-10-04).
  // The ten smithing games under js/forge-games/ plug in exactly as the herb games do, on the
  // same registry. METHODS above stays the herb bench's fixed list (its vocabulary is
  // herbalism-contracts §2); any other definition on the registry is a method by
  // registration, and `BenchGames.methods` lists both, herbs first. A definition may carry:
  //   track:  "forge" (so `BenchGames.methodsFor("forge")` finds it);
  //   HEAT:   the metal's default heat {label, band, hearth_c, cool_rate, burn_c?, start_c?,
  //           steadyBand?, reheat?, coldHint?}. The frame then owns the heat: it builds it
  //           from this and the server's `opts.heat` {start_c, hearth_c, band, cool_rate,
  //           narrow}, cools it every frame, takes R (and a Reheat button) as the reheat,
  //           draws the gauge under the game's meter, shows the number in °C in the hint
  //           column, and puts "Reheat: R" in the hint, in words, while the metal is too cold.
  //           Heat colour is content: the blackbody colours appear on the gauge's scale only;
  //           its needle and outline are the chrome's gold and ink (UI plan §4).
  //   SOUNDS: names on the `forge` bus the frame plays instead of `bench.*` (UI plan §11),
  //           {hit, miss, reheat, ...}; a game asks for one by key through `ctx.cue(key)`.
  // Every rule above holds for them unchanged: one loop, no release in Steady mode, no repeat.

  // THE ENCHANTER'S GAMES (docs/enchanting-contracts.md §12-13, UI plan §6.4 and §9, added
  // 2026-10-06). The six circle games under js/enchant-games/ register the same way, with
  // `track: "enchant"`. Each reads what the server's roll sent: `opts.seq` (Prepare, Unbind,
  // Cleanse: the glyph sequence) or `opts.seats` (Attune), falling back to the same names on
  // `opts.tuning` (rules/enchanter.py tuning_for puts them there), handed on as `ctx.seq` and
  // `ctx.seats`. A definition may also carry:
  //   HOUR:   true, and the frame then owns the DAY-PHASE BAND (the owner's round 4 point 10:
  //           phases of the day, never planets). It reads `opts.hour` (or `tuning.hour`), the
  //           shape rules/enchanter.py `_hour` sends {phase, now, inside, minutes_left,
  //           minutes_until, words, widen}, draws the day's seven windows across the foot of
  //           the meter with the essence's phase hatched and notched and the phase it is now
  //           outlined, and says the server's words over the hint, with whether the windows
  //           are wider. It is shown, never computed: the widening itself is the game's, from
  //           the server's numbers. `ctx.hour` is the normalised object, or null.
  // Sounds go on the `enchant` bus through SOUNDS, as the forge's do, and carry `{phase}`
  // when there is an hour (contracts §13: Sound.play("enchant.<event>", {phase})). A herb or
  // forge game has no HOUR, so for them nothing here runs: no band, no phase in the voice.

  // THE ALCHEMIST'S GAMES (docs/alchemy-contracts.md §11-12, alchemy UI plan §6.4 and §9, added
  // 2026-10-07). The eight games under js/alchemy-games/ register with `track: "alchemy"` and
  // read what the server's roll sent (rules/alchemist.py tuning_for): `opts.heat`, `opts.reaction`,
  // `opts.pour` and `opts.stages`, each falling back to the same name on `opts.tuning`. Three
  // new gauges live here, each behind its own definition key, so a herb, forge or enchant game
  // (which carries none of them) runs exactly as before:
  //   FLAME:    the alchemist's fire (Calcine, Distill, Sublime). Not the forge's HEAT: a forge
  //             bar cools on its own and is reheated with R; an alchemist's vessel sits over a
  //             fire the player FEEDS (hold, or a toggle in Steady) and banks, and the vessel's
  //             heat follows the fire with a lag. Bands are the server's own words ("heads,
  //             hearts, tails"; "dull, calcining, fusing"), the target outlined, everything
  //             above it the danger, cross-hatched. The number is in °C in the hint column.
  //   REACTION: a 0 to 100 gauge with a band, a flare line and the zone's name in words
  //             (React's drops, Dissolve's fizz, Bottle's vapour; Filter's pour rate with
  //             `from: "pour"`). Inputs ADD to it; it settles on its own; a drop may bloom over
  //             a moment, and the gauge then shows where the pending rise will land.
  //   STAGES:   the colour-stage track (Transmute): nigredo, albedo, citrinitas, rubedo named
  //             in words along a timeline, each stage's peak window hatched and notched. The
  //             game owns the timing (its `track()`); the frame draws it.
  // How generous a band is: the frame's generous start (`baseWin`) times the server's band scale
  // times the game's Steady factor, EXCEPT the reaction band, which rules/alchemist.py already
  // widened by the working traits before sending it: counting band_scale again would widen a
  // catalyst's band twice (the forge's narrow_window lesson, makeCtx below).

  // THE LEATHERWORKER'S GAMES (docs/leatherworking-contracts.md §11.1, leather UI plan §6.4 and
  // §9, added 2026-10-08). The games under js/leather-games/ register with `track: "leather"`
  // under the key "leather.<method>" (the forge already holds "assemble" on this one registry,
  // and a second definition there would silently replace the smith's game; one prefix for all
  // eleven is a rule the shell can follow without an exception list). They read the server's
  // `opts.band` (or `tuning.band`), the shape rules/leatherworker.py `band_for` sends:
  // {unit, value_start, target: [lo, hi], fail: [lo, hi] | null, drift, narrow}. One new gauge,
  // behind its own definition key, so no herb, forge, enchant or alchemy game notices it:
  //   BAND: the band gauge (UI plan §6.4, the owner's Q8.3: "every band shown as a number and a
  //         bar as well as a colour"). A straight bar on the variable's real scale, the target
  //         outlined in gold and notched, the failing band cross-hatched with a saw edge, a
  //         needle, the bands' names in words under it, and the number in its real unit in
  //         the hint column ("0.42 of thickness", "62 °C", "11 SPI", "14 min since wetting").
  //         The GAME moves the needle (`ctx.gauge.v`): a tanner's variables move by the hand
  //         (pressure, a stitch's pitch, the liquor stepped up), not on their own like a forge
  //         bar cooling, so the frame draws and scores the reading and never steps it.
  // The window: the generous start times the server's band scale (lane E's working traits:
  // forgiving, supple, fine_pitch...) times the game's Steady factor, and x0.8 when the server
  // says `narrow` (rare hides: the forge's "better metal, tighter window", Giants' Foundry),
  // never pushed into the failing band.

  // Every method a game is registered for: the herb list first, in its fixed order, then any
  // other definition on the registry in the order it registered. Read at call time, so a game
  // file loaded after this one is still found (the registry is one shared object).
  function allMethods() {
    var out = METHODS.slice();
    Object.keys(DEFS).forEach(function (m) {
      if (out.indexOf(m) < 0 && DEFS[m] && typeof DEFS[m].create === "function") out.push(m);
    });
    return out;
  }

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
    },
    // The circle's glyphs (enchant games): one line figure per kind the server names, so a
    // piece reads by its SHAPE in greyscale, never by a colour. Sigils are runes from a fixed
    // set (Elder Futhark shapes, public domain, UI plan §7.2), never drawn by the player: the
    // owner ruled out freehand drawing. An unknown kind gets a plain ring, still a shape.
    glyph: function (g, kind, x, y, s, colour, lw) {
      g.save();
      g.strokeStyle = colour; g.fillStyle = colour; g.lineWidth = lw || 1.5;
      g.lineCap = "round"; g.lineJoin = "round";
      g.beginPath();
      if (kind === "chalk") {                      // a drawn ring with its quarter marks
        g.arc(x, y, s * 0.7, 0, Math.PI * 2);
        for (var q = 0; q < 4; q++) {
          var a = q * Math.PI / 2;
          g.moveTo(x + Math.cos(a) * s * 0.7, y + Math.sin(a) * s * 0.7);
          g.lineTo(x + Math.cos(a) * s, y + Math.sin(a) * s);
        }
        g.stroke();
      } else if (kind === "salt") {                // a ring of grains
        for (var i = 0; i < 8; i++) {
          var b = i * Math.PI / 4;
          g.beginPath(); g.arc(x + Math.cos(b) * s * 0.7, y + Math.sin(b) * s * 0.7, Math.max(1, s * 0.13), 0, Math.PI * 2); g.fill();
        }
      } else if (kind === "ink") {                 // a drop
        g.moveTo(x, y - s);
        g.quadraticCurveTo(x + s * 0.75, y + s * 0.1, x, y + s * 0.8);
        g.quadraticCurveTo(x - s * 0.75, y + s * 0.1, x, y - s);
        g.stroke();
      } else if (kind === "treatment") {           // a triangle, point down (a wash poured)
        g.moveTo(x - s * 0.8, y - s * 0.6); g.lineTo(x + s * 0.8, y - s * 0.6); g.lineTo(x, y + s * 0.8);
        g.closePath(); g.stroke();
      } else if (kind === "focus") {               // a cut stone
        g.moveTo(x, y - s); g.lineTo(x + s * 0.8, y - s * 0.2); g.lineTo(x, y + s);
        g.lineTo(x - s * 0.8, y - s * 0.2); g.closePath();
        g.moveTo(x - s * 0.8, y - s * 0.2); g.lineTo(x + s * 0.8, y - s * 0.2);
        g.stroke();
      } else if (kind === "catalyst") {            // a six-pointed star of lines
        for (var j = 0; j < 3; j++) {
          var c = j * Math.PI / 3;
          g.moveTo(x + Math.cos(c) * s, y + Math.sin(c) * s); g.lineTo(x - Math.cos(c) * s, y - Math.sin(c) * s);
        }
        g.stroke();
      } else if (kind === "bell") {                // the test step: a bell and its clapper
        g.moveTo(x - s * 0.75, y + s * 0.55);
        g.quadraticCurveTo(x - s * 0.6, y - s, x, y - s);
        g.quadraticCurveTo(x + s * 0.6, y - s, x + s * 0.75, y + s * 0.55);
        g.closePath(); g.stroke();
        g.beginPath(); g.arc(x, y + s * 0.8, Math.max(1.2, s * 0.16), 0, Math.PI * 2); g.fill();
      } else if (kind === "enhancement") {         // Tiwaz, the arrow rune
        g.moveTo(x, y + s); g.lineTo(x, y - s);
        g.moveTo(x - s * 0.6, y - s * 0.35); g.lineTo(x, y - s); g.lineTo(x + s * 0.6, y - s * 0.35);
        g.stroke();
      } else if (kind === "sigil") {               // Algiz
        g.moveTo(x, y + s); g.lineTo(x, y - s);
        g.moveTo(x - s * 0.65, y - s * 0.75); g.lineTo(x, y - s * 0.05); g.lineTo(x + s * 0.65, y - s * 0.75);
        g.stroke();
      } else if (kind === "quarter") {             // the circle's own mark: a short bar
        g.moveTo(x - s * 0.6, y); g.lineTo(x + s * 0.6, y);
        g.stroke();
      } else {
        g.arc(x, y, s * 0.6, 0, Math.PI * 2); g.stroke();
      }
      g.restore();
    },
    // The counted beat, for reduced motion (enchant games): instead of a light travelling to
    // its crest, three marks light in turn on the beat and the fourth says "Now", so a crest
    // is met by rhythm, as Rhythm Heaven's cues are heard rather than watched (its Night Mode
    // plays on sound alone). `beat` is 1, 2, 3 as the count says "3", "2", "1", 4 at the
    // crest ("Now"), and 0 before the count. Nothing moves: each mark is lit or it is not, so
    // the time windows work unchanged.
    counted: function (g, x, y, beat, C) {
      for (var i = 0; i < 3; i++) {
        var lit = beat > i;
        KIT.diamond(g, x + i * 16, y, 5, lit ? C.gold : null, lit ? C.gold : C.ash, 1.2);
      }
      KIT.text(g, beat >= 4 ? "Now" : beat >= 1 ? String(4 - beat) : "", x + 52, y, C,
        { size: 15, display: true, colour: beat >= 4 ? C.gold : C.dim });
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
  // An alchemy game may have words more urgent than its gauge's (Distill's cut, "Hearts now:
  // swap to the flask", matters more than the fire), through `urgent()`; the alchemist's fire
  // and the reaction gauge speak through their own `say()`. No herb, forge or enchant game has
  // either, so for them this reads exactly as it did.
  function hintNow(r) {
    if (r.game && r.game.urgent) { var u = r.game.urgent(); if (u) return u; }
    if (r.heat && r.heat.say) { var fw = r.heat.say(); if (fw) return fw; }
    else if (r.heat) {
      var s = r.heat.status();
      if (s === "cold") return r.heat.coldHint;
      if (HEAT_WORDS[s]) return HEAT_WORDS[s];
    }
    if (r.react) { var rw = r.react.say(); if (rw) return rw; }
    if (r.gauge) { var bw = r.gauge.say(); if (bw) return bw; }   // leather games only
    var live = r.game && r.game.hint ? r.game.hint() : null;
    return live || r.def.hint(r.steady);
  }

  // --- the day-phase band (enchant games with HOUR only) -----------------------------------
  // One day's windows, as rules/sky.py `windows()` gives them (minutes of the day; an `ends`
  // past 1440 wraps). Used only when the server's hour carries no `windows` of its own;
  // tests/test_enchant_games.py holds this copy equal to sky.windows(), so the two cannot
  // drift. Dawn 06:00 and dusk 18:00 are the engine's; each turning point holds the two hours
  // centred on it, and morning, afternoon and night fill between (sky.py's docstring).
  var PHASE_WINDOWS = [
    { phase: "night", starts: 60, ends: 300 }, { phase: "dawn", starts: 300, ends: 420 },
    { phase: "morning", starts: 420, ends: 660 }, { phase: "noon", starts: 660, ends: 780 },
    { phase: "afternoon", starts: 780, ends: 1020 }, { phase: "dusk", starts: 1020, ends: 1140 },
    { phase: "night", starts: 1140, ends: 1380 }, { phase: "midnight", starts: 1380, ends: 1500 }
  ];
  var PHASE_NAMES = { dawn: "Dawn", morning: "Morning", noon: "Noon", afternoon: "Afternoon",
    dusk: "Dusk", night: "Night", midnight: "Midnight" };
  var HOUR_H = 30;             // px the band takes from the foot of the meter

  // The server's hour, normalised. Two shapes arrive: the check's and the roll's tuning
  // (`_hour(phase, now)`: `phase` is the ESSENCE's phase and `now` the clock's) and the
  // state's (`{phase, left, words, windows}`: `phase` is the clock's, no essence named). A
  // shape with neither `now` nor `inside` is the state's. Anything unreadable is no band.
  function readHour(h) {
    if (!h || typeof h !== "object") return null;
    var phase = String(h.phase || "");
    if (!PHASE_NAMES[phase]) return null;
    var stateShape = h.now === undefined && h.inside === undefined;
    var now = stateShape ? phase : (PHASE_NAMES[h.now] ? h.now : (h.inside ? phase : null));
    var widen = finite(+h.widen) && +h.widen > 0 ? +h.widen : 1;
    var wins = Array.isArray(h.windows) && h.windows.length ? h.windows.filter(function (w) {
      return w && PHASE_NAMES[w.phase] && finite(+w.starts) && finite(+w.ends) && +w.ends > +w.starts;
    }) : [];
    var minute = finite(+h.minute) ? ((+h.minute % 1440) + 1440) % 1440 : null;
    return {
      phase: stateShape ? null : phase, now: now,
      inside: stateShape ? false : (h.inside === undefined ? now === phase : !!h.inside),
      widen: widen, words: typeof h.words === "string" ? h.words : "",
      minutes_left: finite(+h.minutes_left) ? +h.minutes_left : (finite(+h.left) ? +h.left : null),
      minutes_until: finite(+h.minutes_until) ? +h.minutes_until : null,
      windows: wins.length ? wins : PHASE_WINDOWS, minute: minute
    };
  }

  // The words over the hint: the server's own ("Noon, 42 minutes left"), then whether the
  // windows are wider, in words, because the band's hatching alone would leave a player to
  // work out why the crest got easier. `widen` is the game's effective factor (Bind's own,
  // which folds the server's eager trait in), passed by the game through `ctx.hourWiden`.
  function hourWords(H, widen) {
    if (!H) return "";
    var w = widen != null ? widen : H.widen;
    if (!H.phase) return H.words;
    var more = H.inside && w > 1.0001
      ? "In its hour: windows ×" + (Math.round(w * 100) / 100)
      : "Not its hour: windows as usual";
    return (H.words ? H.words + ". " : "") + more;
  }

  // The band (UI plan §6.4, "the hour band"): the day as one bar, 00:00 to 24:00, cut at every
  // phase's edges. The essence's phase is hatched gold with a notch at each end (shape, not
  // colour); the phase it is now is outlined in ink, and when the server sent the minute, an
  // ink needle stands at it. Names under the bar, the essence's first, then now's; a name that
  // would collide with one already drawn is left out, as the heat gauge does.
  function drawHourBand(r, g, W, top) {
    var H = r.hour, C = r.C, x0 = 10, x1 = W - 10;
    if (!H || x1 - x0 < 80) return;
    var X = function (m) { return x0 + (x1 - x0) * clamp(m / 1440, 0, 1); };
    var by = top + 5, bh = 8, parts = [];
    H.windows.forEach(function (w) {
      var s = +w.starts, e = +w.ends;
      if (e <= 1440) parts.push({ phase: w.phase, s: s, e: e });
      else { parts.push({ phase: w.phase, s: s, e: 1440 }); parts.push({ phase: w.phase, s: 0, e: e - 1440 }); }
    });
    g.save();
    g.strokeStyle = C.edge; g.lineWidth = 1;
    g.strokeRect(x0 + 0.5, by + 0.5, x1 - x0 - 1, bh - 1);
    g.fillStyle = C.ash;
    parts.forEach(function (p) { g.fillRect(Math.round(X(p.s)), by, 1, bh); });
    g.restore();
    parts.forEach(function (p) {
      if (p.phase !== H.phase) return;
      KIT.barBand(g, X(p.s), by, Math.max(2, X(p.e) - X(p.s)), bh, C.gold, { gap: 4 });
      KIT.notch(g, X(p.s), by - 1, Math.PI / 2, 4, C.gold);
      KIT.notch(g, X(p.e), by - 1, Math.PI / 2, 4, C.gold);
    });
    parts.forEach(function (p) {
      if (p.phase !== H.now) return;
      g.save(); g.strokeStyle = C.ink; g.lineWidth = 1.5;
      g.strokeRect(X(p.s), by - 3, Math.max(2, X(p.e) - X(p.s)), bh + 6);
      g.restore();
    });
    if (H.minute != null) {
      var nx = X(H.minute);
      g.save(); g.lineCap = "round";
      g.strokeStyle = C.sunk; g.lineWidth = 4; g.beginPath(); g.moveTo(nx, by - 4); g.lineTo(nx, by + bh + 3); g.stroke();
      g.strokeStyle = C.ink; g.lineWidth = 2; g.beginPath(); g.moveTo(nx, by - 4); g.lineTo(nx, by + bh + 3); g.stroke();
      g.restore();
    }
    g.save();
    g.font = "12px " + C.body;
    g.textBaseline = "middle";
    var spans = [];
    var order = parts.slice().sort(function (p, q) {
      var rank = function (o) { return o.phase === H.phase ? 0 : o.phase === H.now ? 1 : 2; };
      return rank(p) - rank(q) || p.s - q.s;
    });
    order.forEach(function (p) {
      if (p.phase !== H.phase && p.phase !== H.now) return;
      var name = PHASE_NAMES[p.phase], w = g.measureText(name).width;
      var l = clamp((X(p.s) + X(p.e)) / 2 - w / 2, x0, x1 - w);
      for (var k = 0; k < spans.length; k++) if (l < spans[k][1] + 6 && l + w > spans[k][0] - 6) return;
      spans.push([l, l + w]);
      g.fillStyle = p.phase === H.phase ? C.ink : C.dim;
      g.fillText(name, l, by + bh + 10);
    });
    g.restore();
  }

  // --- the alchemist's gauges (alchemy games with FLAME, REACTION or STAGES only) -------------
  // Three lessons decided their shape before any code (alchemy UI plan §9; the research in the
  // lane report):
  //   - A GAUGE MUST READ AS A GAUGE. On 2026-10-06 the owner traced the herb Mix game's
  //     texture line, a wavy stroke, believing it was the path (bench-games/mix.js header). So
  //     every gauge here is a straight horizontal bar with a scale, a needle with a keel, the
  //     band outlined in gold and notched at both ends, and its name in words under it; the
  //     game's own input lives above it in the meter and never looks like the gauge.
  //   - NO MOMENTUM. Stardew Valley's fishing bar accelerates and coasts, and its creator said
  //     it "starts too hard" (herbalism prior art). The fire here moves the heat toward a goal
  //     with a first-order lag: it never overshoots on its own, so where the needle is heading
  //     is where it will stop.
  //   - SHOW WHAT IS COMING. A titration's indicator "lingers longer" as the endpoint nears and
  //     the chemist slows to single drops (University of Wisconsin general chemistry lab,
  //     "Using an indicator during a titration"); a drop here blooms over a moment, and the gauge
  //     draws a hollow mark where the pending rise will land, so overshooting is a choice the
  //     player could see, not a surprise.
  var FLAME_TAU = 3;           // seconds for the heat to go 63% of the way to the fire's goal
  var STAGE_H = 34;            // px the colour-stage track takes from the foot of the meter

  function cap(s) { s = String(s || ""); return s.charAt(0).toUpperCase() + s.slice(1); }

  // The fire for one game. `spec` is the game's FLAME, `given` the server's opts.heat
  // {unit, lo, hi, start, bands: [{name, lo, hi}], target}; every field the server sends wins.
  // The target band is widened about its middle by `scale`, and its neighbours give way to it
  // so the named bands still tile the scale without a gap or an overlap.
  function makeFlame(spec, given, steady, scale) {
    given = given && typeof given === "object" ? given : {};
    var num = function (k) { return finite(+given[k]) ? +given[k] : spec[k]; };
    var lo = num("lo"), hi = num("hi");
    if (!(hi > lo)) { lo = spec.lo; hi = spec.hi; }
    var tidy = function (list) {
      return (Array.isArray(list) ? list : []).filter(function (b) {
        return b && typeof b.name === "string" && b.name && finite(+b.lo) && finite(+b.hi) && +b.hi > +b.lo;
      }).map(function (b) { return { name: b.name, lo: +b.lo, hi: +b.hi }; })
        .sort(function (a, b) { return a.lo - b.lo; });
    };
    var target = typeof given.target === "string" && given.target ? given.target : spec.target;
    var bands = tidy(given.bands);
    var ti = bands.map(function (b) { return b.name; }).indexOf(target);
    if (ti < 0) { bands = tidy(spec.bands); target = spec.target; ti = bands.map(function (b) { return b.name; }).indexOf(target); }
    var tb = bands[ti];
    var mid = (tb.lo + tb.hi) / 2, half = (tb.hi - tb.lo) / 2 * scale;
    var band = [clamp(mid - half, lo, hi), clamp(mid + half, lo, hi)];
    bands = bands.map(function (b, i) {
      if (i === ti) return { name: b.name, lo: band[0], hi: band[1], target: true };
      if (i < ti) return { name: b.name, lo: Math.min(b.lo, band[0]), hi: Math.min(b.hi, band[0]) };
      return { name: b.name, lo: Math.max(b.lo, band[1]), hi: Math.max(b.hi, band[1]), danger: true };
    }).filter(function (b) { return b.hi > b.lo; });
    var tau = FLAME_TAU * (spec.tau || 1) * (steady ? 2 : 1);   // Steady: the drift at half speed
    var start = clamp(num("start"), lo, hi);
    var f = {
      named: true, label: spec.label || "Heat", c: start, band: band, bands: bands, target: tb.name,
      scale: [lo, hi], mid: mid, burn: null, reheats: 0, reheating: 0, quiet: false, canReheat: false,
      coldHint: "", fed: false, damp: false,
      // The fire's goal: a little past the top of the scale while fed (holding the fire on is
      // never safe), the foot of the scale while banked, below it while damped.
      step: function (dt) {
        var span = hi - lo;
        var goal = f.fed ? hi + span * 0.06 : f.damp ? lo - span * 0.12 : lo;
        f.c += (goal - f.c) * (1 - Math.exp(-dt / tau));
        f.c = clamp(f.c, lo, hi + span * 0.06);
      },
      reheat: function () { return false; },
      add: function (deg) { f.c = clamp(f.c + deg, lo, hi); },
      inBand: function () { return f.c >= band[0] && f.c <= band[1]; },
      // 1 in the band's inner half, falling to `edge` at its rim, 0 outside (the forge's curve).
      quality: function (inner, edge) {
        if (!f.inBand()) return 0;
        var hw = (band[1] - band[0]) / 2, d = Math.abs(f.c - (band[0] + band[1]) / 2);
        var iw = hw * (inner == null ? 0.5 : inner);
        return d <= iw ? 1 : 1 - (1 - (edge == null ? 0.6 : edge)) * ((d - iw) / Math.max(1e-6, hw - iw));
      },
      // What a game scores the heat at: its quality, except that the way IN is free. Until the
      // needle first reaches the band's inner part, any heat in the band counts in full, because
      // every run has to cross the rim to get there: measured 2026-10-07, a bot that held the
      // exact middle once it arrived scored 0.975 on Calcine and 0.951 in Steady for the crossing
      // alone. The herb Mix lesson again: no credit lost before the player could have done better.
      settled: false,
      credit: function (inner, edge) {
        var q = f.quality(inner, edge);
        if (q >= 1) f.settled = true;
        return f.settled ? q : q > 0 ? 1 : 0;
      },
      bandAt: function (c) {
        for (var i = 0; i < bands.length; i++) if (c >= bands[i].lo && c <= bands[i].hi) return bands[i];
        return null;
      },
      // "burn" is any band above the target: fusing, melting, tails. The stylesheet's heat-burn
      // class and the cross-hatched gauge zone say it twice over; the words say it first.
      status: function () { return f.c < band[0] ? "cold" : f.c > band[1] ? "burn" : "in"; },
      say: function () {
        var s = f.status(), b = f.bandAt(f.c);
        if (s === "cold") return (b ? cap(b.name) : "Cold") + ": feed the fire";
        if (s === "burn") return (b ? cap(b.name) : "Too hot") + ": bank the fire";
        return null;
      },
      // A still's head reads to the degree (its bands are 8 °C wide); a calcining crucible to 5.
      text: function () {
        var n = hi - lo < 200 ? Math.round(f.c) : Math.round(f.c / 5) * 5;
        return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",") + " °C";
      }
    };
    return f;
  }

  // The reaction gauge (UI plan §6.4, the owner's Q9.4): `spec` the game's REACTION
  // {label, band, rise, settle, flare_at, start, words: [below, in, above, flare], say,
  // bloom?, steadyBand?, steadySettle?, from?}; `given` the server's {start, band, rise, settle,
  // flare_at} (or Filter's pour {band, start}). The server's fields win. A band that starts at
  // 0 (Bottle's vapour, where less is better) widens upward only.
  function makeReaction(spec, given, steady, scale) {
    given = given && typeof given === "object" ? given : {};
    var num = function (k) { return finite(+given[k]) ? +given[k] : spec[k]; };
    var b = Array.isArray(given.band) && given.band.length === 2 && finite(+given.band[0]) &&
      finite(+given.band[1]) && +given.band[1] > +given.band[0] ? [+given.band[0], +given.band[1]] : spec.band.slice();
    var floor = b[0] <= 0;
    var band = floor ? [0, clamp(b[1] * scale, 1, 95)]
      : [clamp((b[0] + b[1]) / 2 - (b[1] - b[0]) / 2 * scale, 0, 100), clamp((b[0] + b[1]) / 2 + (b[1] - b[0]) / 2 * scale, 0, 100)];
    var flare = num("flare_at");
    if (!(flare > band[1] + 2)) flare = Math.min(100, band[1] + 10);   // never inside the band
    var settle = Math.max(0, num("settle")) * (steady ? (spec.steadySettle || 1) : 1);
    var bloom = spec.bloom || 0, words = spec.words || ["low", "in band", "high", "over"];
    var R = {
      label: spec.label || "Reaction", v: clamp(num("start"), 0, 100), band: band, flare: flare,
      rise: num("rise"), settle: settle, pending: 0, flares: 0, over: false, floor: floor, words: words,
      step: function (dt) {
        if (R.pending > 0) {
          var take = bloom > 0 ? R.pending * (1 - Math.exp(-dt / bloom)) : R.pending;
          if (R.pending - take < 0.05) take = R.pending;
          R.v += take; R.pending -= take;
        }
        R.v = clamp(R.v - R.settle * dt, 0, 100);
        // A flare is counted on the way over the line, once, and not again until the gauge has
        // fallen clear of it: a needle resting on the line is one flare, not sixty.
        if (R.v >= R.flare && !R.over) { R.over = true; R.flares++; }
        else if (R.v < R.flare - 4) R.over = false;
      },
      add: function (x) { if (bloom > 0) R.pending += x; else R.v = clamp(R.v + x, 0, 100); },
      lands: function () { return clamp(R.v + R.pending, 0, 100); },
      inBand: function () { return R.v >= band[0] && R.v <= band[1]; },
      quality: function () {
        if (!R.inBand()) return 0;
        if (floor) {   // lower is better: the inner 60% of the band from the floor is full credit
          var top = band[1], d = R.v / Math.max(1e-6, top);
          return d <= 0.6 ? 1 : 1 - 0.4 * (d - 0.6) / 0.4;
        }
        var hw = (band[1] - band[0]) / 2, a = Math.abs(R.v - (band[0] + band[1]) / 2), iw = hw * 0.6;
        return a <= iw ? 1 : 1 - 0.4 * ((a - iw) / Math.max(1e-6, hw - iw));
      },
      // The way in is free, as the fire's `credit` (above): until the needle first reaches the
      // band's inner part, any reading in the band counts in full.
      settled: false,
      credit: function () {
        var q = R.quality();
        if (q >= 1) R.settled = true;
        return R.settled ? q : q > 0 ? 1 : 0;
      },
      status: function () {
        return R.v < band[0] ? "low" : R.v <= band[1] ? "in" : R.v < R.flare ? "high" : "flare";
      },
      name: function () { return words[["low", "in", "high", "flare"].indexOf(R.status())] || ""; },
      say: function () { var s = spec.say || {}; return s[R.status()] || null; },
      text: function () { return R.label + " " + Math.round(R.v); }
    };
    return R;
  }

  // The colour stages, normalised: the server's list of names (`["nigredo", ...]`) or of
  // {name, length, window} where `length` and `window` are factors on the game's own (the
  // contracts' "per-stage windows"). Anything unreadable falls back to the definition's list.
  function readStages(list, fallback) {
    var out = (Array.isArray(list) ? list : []).map(function (s) {
      if (typeof s === "string") return s ? { name: s, length: 1, window: 1 } : null;
      if (!s || typeof s !== "object" || typeof s.name !== "string" || !s.name) return null;
      var L = +s.length, Wn = +s.window;
      return { name: s.name, length: finite(L) && L > 0 ? clamp(L, 0.5, 2) : 1,
        window: finite(Wn) && Wn > 0 ? clamp(Wn, 0.5, 2) : 1 };
    }).filter(function (s) { return s; });
    if (!out.length) out = fallback.map(function (n) { return { name: n, length: 1, window: 1 }; });
    return out.slice(0, 6).map(function (s) { s.word = cap(s.name); return s; });
  }

  // Shared by the two straight gauges: the needle, in ink on a dark keel so it reads on any
  // part of the bar, with a diamond cap.
  function needle(g, C, nx, by, bh) {
    g.save();
    g.lineCap = "round";
    g.strokeStyle = C.sunk; g.lineWidth = 4;
    g.beginPath(); g.moveTo(nx, by - 6); g.lineTo(nx, by + bh + 4); g.stroke();
    g.strokeStyle = C.ink; g.lineWidth = 2;
    g.beginPath(); g.moveTo(nx, by - 6); g.lineTo(nx, by + bh + 4); g.stroke();
    g.restore();
    KIT.diamond(g, nx, by - 7, 3.5, C.ink, C.sunk, 1);
  }
  // Names under a straight gauge, the first in `items` placed first; one that would collide with
  // a name already placed is left out (the heat gauge's rule), so the band that matters always
  // has its name.
  function gaugeNames(g, C, items, x0, x1, y) {
    g.save();
    g.font = "12px " + C.body;
    g.textBaseline = "middle";
    var spans = [];
    items.forEach(function (it) {
      if (!it.text || it.b - it.a < 2) return;
      var w = g.measureText(it.text).width;
      var l = clamp((it.a + it.b) / 2 - w / 2, x0, x1 - w);
      for (var k = 0; k < spans.length; k++) if (l < spans[k][1] + 6 && l + w > spans[k][0] - 6) return;
      spans.push([l, l + w]);
      g.fillStyle = it.colour;
      g.fillText(it.text, l, y);
    });
    g.restore();
  }
  // The danger zone: cross-hatched in the alarm colour with a saw edge above it, as the forge's
  // burning zone is, so it reads in greyscale.
  function dangerZone(g, C, xa, xb, by, bh) {
    if (xb - xa < 1) return;
    KIT.barBand(g, xa, by - 2, Math.max(2, xb - xa), bh + 4, C.alarm, { cross: true, gap: 4 });
    g.save(); g.strokeStyle = C.alarm; g.lineWidth = 1.2; g.beginPath();
    for (var i = 0, n = Math.max(2, Math.round((xb - xa) / 5)); i <= n; i++) {
      var px = xa + (xb - xa) * i / n, py = by - 3 - (i % 2 ? 4 : 0);
      if (i) g.lineTo(px, py); else g.moveTo(px, py);
    }
    g.stroke(); g.restore();
  }
  function targetBand(g, C, xa, xb, by, bh) {
    KIT.barBand(g, xa, by, Math.max(2, xb - xa), bh, C.goldDim, { gap: 4 });
    g.save(); g.strokeStyle = C.gold; g.lineWidth = 2; g.strokeRect(xa, by - 4, Math.max(2, xb - xa), bh + 8); g.restore();
    KIT.notch(g, xa, by - 5, Math.PI / 2, 5, C.gold);
    KIT.notch(g, xb, by - 5, Math.PI / 2, 5, C.gold);
  }

  // The fire's gauge: the scale as a plain bar (an alembic's heat has no glow to show, so no
  // blackbody colours: those are the forge's content), a tick and the number at each band's
  // edge, the target band hatched and outlined in gold with its notches, the danger above it
  // cross-hatched, the needle, and the bands' own names under the bar, the target's first.
  function drawFlameGauge(r, g, W, top) {
    var H = r.heat, C = r.C, x0 = 10, x1 = W - 10;
    if (x1 - x0 < 80) return;
    var lo = H.scale[0], hi = H.scale[1];
    var X = function (c) { return x0 + (x1 - x0) * clamp((c - lo) / (hi - lo), 0, 1); };
    var by = top + 6, bh = 9;
    g.save();
    g.fillStyle = C.panel; g.fillRect(x0, by, x1 - x0, bh);
    g.strokeStyle = C.edge; g.lineWidth = 1; g.strokeRect(x0 + 0.5, by + 0.5, x1 - x0 - 1, bh - 1);
    g.fillStyle = C.ash;
    H.bands.forEach(function (b) { g.fillRect(Math.round(X(b.lo)), by + bh, 1, 4); });
    g.restore();
    H.bands.forEach(function (b) { if (b.danger) dangerZone(g, C, X(b.lo), X(b.hi), by, bh); });
    targetBand(g, C, X(H.band[0]), X(H.band[1]), by, bh);
    needle(g, C, X(H.c), by, bh);
    var items = H.bands.slice().sort(function (p, q) {
      var rank = function (b) { return b.target ? 0 : b.danger ? 1 : 2; };
      return rank(p) - rank(q) || p.lo - q.lo;
    }).map(function (b) {
      return { text: b.name, a: X(b.lo), b: X(b.hi), colour: b.target ? C.ink : b.danger ? C.ink : C.dim };
    });
    gaugeNames(g, C, items, x0, x1, by + bh + 12);
  }

  // The reaction gauge: 0 to 100 as a plain bar with a tick every 25, the band hatched and
  // outlined in gold with its notches, everything from the flare line up cross-hatched, the
  // hollow "lands here" mark while a drop is still blooming, the needle, and the zones' words
  // under the bar ("calm", "working", "racing", "boiling over"), the band's word first.
  function drawReaction(r, g, W, top) {
    var R = r.react, C = r.C, x0 = 10, x1 = W - 10;
    if (x1 - x0 < 80) return;
    var X = function (v) { return x0 + (x1 - x0) * clamp(v / 100, 0, 1); };
    var by = top + 6, bh = 9;
    g.save();
    g.fillStyle = C.panel; g.fillRect(x0, by, x1 - x0, bh);
    g.strokeStyle = C.edge; g.lineWidth = 1; g.strokeRect(x0 + 0.5, by + 0.5, x1 - x0 - 1, bh - 1);
    g.fillStyle = C.ash;
    for (var t = 0; t <= 100; t += 25) g.fillRect(Math.round(X(t)), by + bh, 1, 4);
    g.restore();
    dangerZone(g, C, X(R.flare), x1, by, bh);
    targetBand(g, C, X(R.band[0]), X(R.band[1]), by, bh);
    if (R.pending > 0.5) {
      var lx = X(R.lands());
      g.save(); g.strokeStyle = C.ink; g.lineWidth = 1.2; g.setLineDash && g.setLineDash([2, 2]);
      g.beginPath(); g.moveTo(lx, by - 2); g.lineTo(lx, by + bh + 2); g.stroke();
      g.setLineDash && g.setLineDash([]);
      g.restore();
      KIT.diamond(g, lx, by - 6, 3.5, null, C.ink, 1.2);
    }
    needle(g, C, X(R.v), by, bh);
    var w = R.words;
    gaugeNames(g, C, [
      { text: w[1], a: X(R.band[0]), b: X(R.band[1]), colour: C.ink },
      { text: w[3], a: X(R.flare), b: x1, colour: C.ink },
      { text: w[0], a: x0, b: X(R.band[0]), colour: C.dim },
      { text: w[2], a: X(R.band[1]), b: X(R.flare), colour: C.dim }
    ], x0, x1, by + bh + 12);
  }

  // The colour-stage track (Transmute): the run as a timeline cut into its stages, each named
  // under the bar, each stage's peak window hatched and notched, the stage now outlined in ink,
  // and a needle at now. Under reduced motion the needle is not drawn: the game counts each
  // peak in ("3", "2", "1", "Now", the enchant games' counted beat) and the track stands still.
  function drawStageTrack(r, g, W, top) {
    var T = r.game.track(), C = r.C, x0 = 10, x1 = W - 10;
    if (!T || x1 - x0 < 80 || !(T.end > T.start)) return;
    var X = function (s) { return x0 + (x1 - x0) * clamp((s - T.start) / (T.end - T.start), 0, 1); };
    var by = top + 6, bh = 9;
    g.save();
    g.fillStyle = C.panel; g.fillRect(x0, by, x1 - x0, bh);
    g.strokeStyle = C.edge; g.lineWidth = 1; g.strokeRect(x0 + 0.5, by + 0.5, x1 - x0 - 1, bh - 1);
    g.fillStyle = C.ash;
    T.items.forEach(function (it) { g.fillRect(Math.round(X(it.s)), by - 2, 1, bh + 4); });
    g.restore();
    T.items.forEach(function (it) {
      var a = X(it.peak - it.hw), b = X(it.peak + it.hw);
      KIT.barBand(g, a, by, Math.max(2, b - a), bh, it.current ? C.gold : C.goldDim, { gap: 4 });
      KIT.notch(g, a, by - 1, Math.PI / 2, 4, it.current ? C.gold : C.goldDim);
      KIT.notch(g, b, by - 1, Math.PI / 2, 4, it.current ? C.gold : C.goldDim);
      if (it.current) {
        g.save(); g.strokeStyle = C.ink; g.lineWidth = 1.5;
        g.strokeRect(X(it.s), by - 3, Math.max(2, X(it.e) - X(it.s)), bh + 6);
        g.restore();
      }
    });
    if (!r.reduced && T.now >= T.start && T.now <= T.end) needle(g, C, X(T.now), by, bh);
    gaugeNames(g, C, T.items.map(function (it) {
      return { text: it.word, a: X(it.s), b: X(it.e), colour: it.current ? C.ink : C.dim };
    }).sort(function (p, q) { return (q.colour === C.ink ? 1 : 0) - (p.colour === C.ink ? 1 : 0); }), x0, x1, by + bh + 12);
  }

  // --- the band gauge (leather games with BAND only) ------------------------------------------
  // Each unit's default scale and how its number reads. The scale is the bar's ends; the server
  // sends only the bands, so a game may widen its scale (BAND.scale) where its variable runs
  // past the default (Salt's weight past 100%, Curry's fat to 30%).
  var BAND_UNITS = {
    fraction: { scale: [0, 1], text: function (v) { return v.toFixed(2); } },
    strength: { scale: [0, 1], text: function (v) { return v.toFixed(2); } },
    percent: { scale: [0, 100], text: function (v) { return Math.round(v) + "%"; } },
    celsius: { scale: [20, 100], text: function (v) { return Math.round(v) + " °C"; } },
    spi: { scale: [4, 18], text: function (v) { return Math.round(v) + " SPI"; } },
    minutes: { scale: [0, 60], text: function (v) { return Math.round(v) + " min"; } }
  };
  var BAND_STATES = ["low", "in", "high", "fail"];

  function pair(p) {
    return Array.isArray(p) && p.length === 2 && finite(+p[0]) && finite(+p[1]) && +p[1] >= +p[0]
      ? [+p[0], +p[1]] : null;
  }

  // The gauge for one game. `spec` is the game's BAND {unit, label, after, scale, target, fail,
  // value_start, drift, words: {low, in, high, fail}, say: {low, high, fail}, levels?}; `given`
  // the server's band. The server's unit, bands, start and drift win where they are readable;
  // a unit the game was not built for keeps the game's own (a gauge in the wrong unit would
  // print a number that means nothing). The target is widened about its middle by `scale`; a
  // target that runs to an end of the scale (Tan's strong liquor to 1.0, Cut's 0 off the line)
  // widens inward from that end only; neither ever reaches into the failing band.
  function makeBand(spec, given, scale) {
    given = given && typeof given === "object" ? given : {};
    var unit = BAND_UNITS[given.unit] && given.unit === spec.unit ? given.unit : spec.unit;
    var U = BAND_UNITS[unit] || BAND_UNITS.fraction;
    var sc = pair(spec.scale) || U.scale.slice();
    var lo = sc[0], hi = sc[1], span = hi - lo;
    var tg = pair(given.target) || pair(spec.target);
    var fail = given.fail === null ? null : (pair(given.fail) || (given.fail === undefined ? pair(spec.fail) : null));
    tg = [clamp(tg[0], lo, hi), clamp(tg[1], lo, hi)];
    var w = (tg[1] - tg[0]) * scale, band;
    if (tg[0] <= lo + 1e-9 && tg[1] < hi) band = [lo, clamp(lo + w, lo, hi)];
    else if (tg[1] >= hi - 1e-9 && tg[0] > lo) band = [clamp(hi - w, lo, hi), hi];
    else { var mid = (tg[0] + tg[1]) / 2; band = [clamp(mid - w / 2, lo, hi), clamp(mid + w / 2, lo, hi)]; }
    if (fail) {
      var gap = span * 0.02;
      if (fail[0] >= tg[1] && band[1] > fail[0] - gap) { band[0] = Math.max(lo, band[0] - (band[1] - (fail[0] - gap))); band[1] = fail[0] - gap; }
      if (fail[1] <= tg[0] && band[0] < fail[1] + gap) { band[1] = Math.min(hi, band[1] + (fail[1] + gap - band[0])); band[0] = fail[1] + gap; }
    }
    var start = finite(+given.value_start) ? +given.value_start : finite(+spec.value_start) ? +spec.value_start : lo;
    var drift = finite(+given.drift) && +given.drift >= 0 ? +given.drift : (+spec.drift || 0);
    var words = spec.words || {}, say = spec.say || {};
    var G = {
      unit: unit, label: spec.label || "", after: spec.after || "", v: clamp(start, lo, hi),
      scale: [lo, hi], target: tg, band: band, fail: fail, drift: drift,
      inBand: function () { return G.v >= band[0] && G.v <= band[1]; },
      // 1 in the band's inner `inner` share, falling to `edge` at its rim, 0 outside (the
      // forge's curve). A band anchored at an end of the scale is measured from that end: for
      // Cut, 0 off the line is the best there is, not the band's rim.
      quality: function (inner, edge, at) {
        var v = at == null ? G.v : at;
        if (v < band[0] || v > band[1]) return 0;
        inner = inner == null ? 0.5 : inner; edge = edge == null ? 0.6 : edge;
        var d, hw;
        if (band[0] <= lo + 1e-9 && tg[0] <= lo + 1e-9) { hw = band[1] - band[0]; d = v - band[0]; }
        else if (band[1] >= hi - 1e-9 && tg[1] >= hi - 1e-9) { hw = band[1] - band[0]; d = band[1] - v; }
        else { hw = (band[1] - band[0]) / 2; d = Math.abs(v - (band[0] + band[1]) / 2); }
        var iw = hw * inner;
        return d <= iw ? 1 : 1 - (1 - edge) * ((d - iw) / Math.max(1e-6, hw - iw));
      },
      statusAt: function (v) {
        if (fail && v >= fail[0] && v <= fail[1]) return "fail";
        return v < band[0] ? "low" : v > band[1] ? "high" : "in";
      },
      status: function () { return G.statusAt(G.v); },
      word: function (s) { return words[s || G.status()] || ""; },
      say: function () { return say[G.status()] || null; },
      // The reading in words: the label, the number in its unit, what it is "of", and for a
      // liquor the strength's own word ("Liquor 0.62, medium").
      text: function () {
        var n = U.text(G.v), lv = "";
        (spec.levels || []).some(function (l) { if (G.v < l[0]) { lv = l[1]; return true; } return false; });
        return [G.label, n + (lv ? ", " + lv : ""), G.after].filter(function (x) { return x; }).join(" ");
      },
      X: function (v, x0, x1) { return x0 + (x1 - x0) * clamp((v - lo) / span, 0, 1); }
    };
    return G;
  }

  // The band gauge, drawn as the alchemist's straight gauges are (the herb Mix lesson: a gauge
  // must read as a gauge): a plain bar with a tick at each band edge, the failing band cross-
  // hatched with a saw edge (dangerZone), the target hatched, outlined and notched in gold
  // (targetBand), the needle with its keel, and the bands' names under the bar, the target's
  // first, then the failing band's, so the names that matter are the ones always drawn.
  function drawBandGauge(r, g, W, top) {
    var G = r.gauge, C = r.C, x0 = 10, x1 = W - 10;
    if (x1 - x0 < 80) return;
    var X = function (v) { return G.X(v, x0, x1); };
    var by = top + 6, bh = 9;
    g.save();
    g.fillStyle = C.panel; g.fillRect(x0, by, x1 - x0, bh);
    g.strokeStyle = C.edge; g.lineWidth = 1; g.strokeRect(x0 + 0.5, by + 0.5, x1 - x0 - 1, bh - 1);
    g.fillStyle = C.ash;
    [G.band[0], G.band[1]].concat(G.fail ? G.fail : []).forEach(function (v) { g.fillRect(Math.round(X(v)), by + bh, 1, 4); });
    g.restore();
    if (G.fail) dangerZone(g, C, X(G.fail[0]), X(G.fail[1]), by, bh);
    targetBand(g, C, X(G.band[0]), X(G.band[1]), by, bh);
    if (finite(G.ghost)) {
      // A hollow mark where something pending will land (Curry's dubbin soaking in, the
      // reaction gauge's bloom), so an overshoot is a choice the player could see.
      var lx = X(G.ghost);
      g.save(); g.strokeStyle = C.ink; g.lineWidth = 1.2;
      g.beginPath(); g.moveTo(lx, by - 2); g.lineTo(lx, by + bh + 2); g.stroke(); g.restore();
      KIT.diamond(g, lx, by - 6, 3.5, null, C.ink, 1.2);
    }
    needle(g, C, X(G.v), by, bh);
    var lo = G.scale[0], hi = G.scale[1], items = [
      { text: G.word("in"), a: X(G.band[0]), b: X(G.band[1]), colour: C.ink }
    ];
    if (G.fail) items.push({ text: G.word("fail"), a: X(G.fail[0]), b: X(G.fail[1]), colour: C.ink });
    var highTo = G.fail && G.fail[0] >= G.band[1] ? G.fail[0] : hi;
    var lowFrom = G.fail && G.fail[1] <= G.band[0] ? G.fail[1] : lo;
    items.push({ text: G.word("low"), a: X(lowFrom), b: X(G.band[0]), colour: C.dim });
    items.push({ text: G.word("high"), a: X(G.band[1]), b: X(highTo), colour: C.dim });
    gaugeNames(g, C, items, x0, x1, by + bh + 12);
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
    if (H.named) { drawFlameGauge(r, g, W, top); return; }   // an alchemist's fire (FLAME)
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
  function build(mount, def, steady, hour) {
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
    // A forge game's heat: the number in °C above the hint (the gauge itself is drawn on the
    // canvas), the hint spoken when it changes (it changes only for heat and the end), and a
    // Reheat button for a player without a keyboard (UI plan §7.2: "R, or click the hearth";
    // the strip has no hearth to click, so the button is the hearth).
    var heatNum = null, reheat = null;
    if (def.HEAT) {
      root.classList.add("has-heat");
      heatNum = el("p", "bench-game__heat-num");
      heatNum.setAttribute("aria-label", (def.HEAT.label || "Heat") + " in degrees");
      hint.appendChild(heatNum);
      hintText.setAttribute("aria-live", "polite");
      if (def.HEAT.reheat !== false) {
        reheat = el("button", "bench-game__act bench-game__reheat", "Reheat");
        reheat.type = "button";
        reheat.setAttribute("aria-keyshortcuts", "R");
        tools.appendChild(reheat);
      }
    }
    // An alchemy game's gauge number: the fire's °C (it shares the forge's number and its
    // heat-* classes, so the stylesheet's rules for "cold" and "burn" hold), or the reaction's
    // label and value ("Fizz 56"). No Reheat: an alchemist feeds the fire instead. The hint is
    // spoken when it changes, because it is where the gauge's words go.
    var reactNum = null;
    if (def.FLAME) {
      root.classList.add("has-heat");
      heatNum = el("p", "bench-game__heat-num");
      heatNum.setAttribute("aria-label", (def.FLAME.label || "Heat") + " in degrees");
      hint.appendChild(heatNum);
      hintText.setAttribute("aria-live", "polite");
    }
    if (def.REACTION) {
      root.classList.add("has-react");
      reactNum = el("p", "bench-game__react-num");
      reactNum.setAttribute("aria-label", (def.REACTION.label || "Reaction") + ", 0 to 100");
      hint.appendChild(reactNum);
      hintText.setAttribute("aria-live", "polite");
    }
    // A leather game's band gauge: the reading in its real unit above the hint ("62 °C",
    // "Pitch 11 SPI"), and the hint spoken when it changes, because the gauge's words ("Too
    // deep: ease off") are what a player who cannot see the needle's colour reads.
    var bandNum = null;
    if (def.BAND) {
      root.classList.add("has-band");
      bandNum = el("p", "bench-game__band-num");
      bandNum.setAttribute("aria-label", (def.BAND.label || def.name) + ", the reading");
      hint.appendChild(bandNum);
      hintText.setAttribute("aria-live", "polite");
    }
    if (def.STAGES) root.classList.add("has-stages");
    if (def.track === "alchemy") hintText.setAttribute("aria-live", "polite");
    if (def.track) root.classList.add("bench-game--" + def.track);
    // An enchant game's day-phase band: the server's words above the hint (the band itself is
    // drawn on the canvas), and the hint spoken when it changes, because an order game's hint
    // is where it says which piece comes next. Only a definition with HOUR and an hour the
    // server sent gets the words; every other game builds exactly as before.
    var hourWordsEl = null;
    if (def.HOUR && hour) {
      root.classList.add("has-hour");
      if (hour.inside) root.classList.add("is-in-hour");
      hourWordsEl = el("p", "bench-game__hour", hourWords(hour));
      hint.appendChild(hourWordsEl);
    }
    if (def.track === "enchant") hintText.setAttribute("aria-live", "polite");
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
      card: card, cardText: cardText, cardSub: cardSub, heatNum: heatNum, reheat: reheat,
      hour: hourWordsEl, reactNum: reactNum, bandNum: bandNum };
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
    // A heat game draws in the meter above the gauge; the gauge takes the foot. An enchant
    // game with an hour does the same with the day-phase band (no game has both).
    var gh = r.heat ? GAUGE_H : r.hour ? HOUR_H : 0;
    if (r.react) gh = GAUGE_H; else if (r.stages) gh = STAGE_H;   // alchemy only
    if (r.gauge) gh = GAUGE_H;                                     // leather only
    r.game.draw(g, r.W, r.H - gh);
    if (r.heat) drawGauge(r, g, r.W, r.H - gh);
    else if (r.hour) drawHourBand(r, g, r.W, r.H - gh);
    if (r.react) drawReaction(r, g, r.W, r.H - gh);
    else if (r.stages && r.game.track) drawStageTrack(r, g, r.W, r.H - gh);
    if (r.gauge) drawBandGauge(r, g, r.W, r.H - gh);
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
    advance(r, dt);
    stepParticles(r, dt);
    paint(r);
    feed(r);
    if (r.game.done() || r.t >= r.game.duration) { finish(r, false); return; }
    r.raf = window.requestAnimationFrame(loop);
  }

  // One step of game time, shared by the loop and the headless `simulate` (so what the node
  // tests drive is what the strip plays): the heat cools or reheats first, then the game reads
  // it on the same frame.
  function advance(r, dt) {
    r.t += dt;
    if (r.heat) r.heat.step(dt);
    if (r.react) r.react.step(dt);
    r.game.tick(dt, r.t);
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
      // The forge's stage (contracts §11, `ForgeStage`) takes `heat(celsius)` and may have no
      // `update`; a missing method is skipped, never a throw that drops the stage.
      try {
        if (typeof r.stage.update === "function") r.stage.update(r.game.state());
        if (r.heat && typeof r.stage.heat === "function") r.stage.heat(r.heat.c);
        // AlchemyStage (contracts §12): `reaction(value)` churns the liquid with the gauge.
        if (r.react && typeof r.stage.reaction === "function") r.stage.reaction(r.react.v);
      }
      catch (e) { r.stage = null; if (window.console) console.warn("bench stage update failed; the strip plays on", e); }
    }
    if (r.burner) {
      try { r.burner.heat(clamp((r.heat.c - r.heat.scale[0]) / (r.heat.scale[1] - r.heat.scale[0]), 0, 1)); }
      catch (e) { r.burner = null; }
    }
    if (r.heat) showHeat(r);
    else if (r.react) showReact(r);
    else if (r.gauge) showGauge(r);
    else if (r.game.hint) setHint(r, hintNow(r));
    var s = clamp(r.game.score(), 0, 1);
    if (Math.abs(s - r.lastScore) >= 0.004) {
      r.lastScore = s;
      if (r.onScore) { try { r.onScore(s); } catch (e) { if (window.console) console.warn(e); } }
    }
    showBand(r, s);
  }

  // The hint's words change only when they really change: the hint is a live region on a
  // heat game, and a region rewritten every frame would be read out every frame.
  function setHint(r, text) {
    if (r.phase === "done" || text === r.hintShown) return;
    r.hintShown = text;
    r.dom.hintText.textContent = text;
  }
  // The number in °C (rounded to 5, so it reads instead of flickering), the hint, and a class
  // on the strip naming the heat's state for the stylesheet.
  function showHeat(r) {
    var n = r.heat.text ? r.heat.text() : degrees(r.heat.c), s = r.heat.status();
    if (r.dom.heatNum && n !== r.heatShown) { r.heatShown = n; r.dom.heatNum.textContent = n; }
    if (s !== r.heatState) {
      if (r.heatState) r.dom.root.classList.remove("heat-" + r.heatState);
      r.heatState = s;
      r.dom.root.classList.add("heat-" + s);
      if (r.dom.reheat) r.dom.reheat.disabled = s === "reheating";
    }
    setHint(r, hintNow(r));
  }
  // The reaction's number and zone (alchemy games with REACTION): "Fizz 56", a `react-<zone>`
  // class on the strip (low, in, high, flare) for the stylesheet, and the hint.
  function showReact(r) {
    var n = r.react.text(), s = r.react.status();
    if (r.dom.reactNum && n !== r.reactShown) { r.reactShown = n; r.dom.reactNum.textContent = n; }
    if (s !== r.reactState) {
      if (r.reactState) r.dom.root.classList.remove("react-" + r.reactState);
      r.reactState = s;
      r.dom.root.classList.add("react-" + s);
    }
    setHint(r, hintNow(r));
  }

  // The band gauge's reading and zone (leather games with BAND): "Water 62 °C", a `band-<zone>`
  // class on the strip (low, in, high, fail) for the stylesheet, and the hint.
  function showGauge(r) {
    var n = r.gauge.text(), s = r.gauge.status();
    if (r.dom.bandNum && n !== r.gaugeShown) { r.gaugeShown = n; r.dom.bandNum.textContent = n; }
    if (s !== r.gaugeState) {
      if (r.gaugeState) r.dom.root.classList.remove("band-" + r.gaugeState);
      r.gaugeState = s;
      r.dom.root.classList.add("band-" + s);
    }
    setHint(r, hintNow(r));
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
    // The forge's window (contracts §11). The server's `tuning.band_scale` already folds in
    // the working traits (forgiving 1.2, narrow_window 0.8, rules/blacksmith.py tuning_for);
    // `opts.heat.narrow` says "better metal narrows the window" (Giants' Foundry, prior art
    // §5.4) and counts only when the band scale has not already counted narrow_window, so a
    // narrow metal is never narrowed twice (0.64 where the rule says 0.8).
    var heatIn = opts.heat && typeof opts.heat === "object" ? opts.heat : null;
    var traits = Array.isArray(tuning.traits) ? tuning.traits : [];
    var narrow = !!(heatIn && heatIn.narrow) || traits.indexOf("narrow_window") >= 0;
    var bs = +tuning.band_scale;
    var bandScale = finite(bs) && bs > 0 ? clamp(bs, 0.5, 1.6) : 1;
    if (heatIn && heatIn.narrow && traits.indexOf("narrow_window") < 0) bandScale *= NARROW;
    r.bandScale = bandScale;
    r.heat = r.def.HEAT ? makeHeat(r.def.HEAT, heatIn, steady, baseWin * bandScale, narrow) : null;
    // The alchemist's gauges (alchemy contracts §12), each read from the opts first and the
    // server's tuning second, as the enchant games' seq and seats are.
    var DF = r.def.FLAME, DR = r.def.REACTION;
    if (DF) {
      r.heat = makeFlame(DF, heatIn || tuning.heat, steady,
        baseWin * bandScale * (steady ? (DF.steadyBand || 1) : 1));
    }
    if (DR) {
      var from = DR.from || "reaction";
      // rules/alchemist.py tuning_for has already widened `reaction.band` by the working traits
      // (a catalyst's 1.2); `pour` it has not. So band_scale counts for the pour, not twice for
      // the reaction.
      r.react = makeReaction(DR, opts[from] || tuning[from], steady,
        baseWin * (from === "reaction" ? 1 : bandScale) * (steady ? (DR.steadyBand || 1) : 1));
    }
    if (r.def.STAGES) r.stages = readStages(opts.stages || tuning.stages, r.def.STAGE_NAMES || []);
    // The leather band gauge (leather contracts §11.1): the opts first, the server's tuning
    // second (rules/leatherworker.py puts `band` on both the roll's body and its tuning). Lane
    // E's band_scale is the working traits only, and its `narrow` is the hide's rarity alone,
    // so each is counted once here.
    var DB = r.def.BAND;
    if (DB) {
      var bandIn = opts.band && typeof opts.band === "object" ? opts.band
        : tuning.band && typeof tuning.band === "object" ? tuning.band : null;
      r.gauge = makeBand(DB, bandIn, baseWin * bandScale * (steady ? (DB.steadyBand || 1) : 1) *
        (bandIn && bandIn.narrow ? NARROW : 1));
    }
    var voice = { hardness: tuning.hardness, bath: tuning.bath };
    // The enchanter's sound contract (contracts §13): enchant events carry the day phase.
    // Only an hour adds it, and only an enchant game with HOUR has one.
    if (r.hour) voice.phase = r.hour.phase || r.hour.now;
    return {
      // The enchant games' inputs (contracts §13), the opts first, the server's tuning second:
      // the glyph sequence for Prepare, Unbind and Cleanse, the seats for Attune, the hour.
      seq: Array.isArray(opts.seq) ? opts.seq : Array.isArray(tuning.seq) ? tuning.seq : null,
      seats: Array.isArray(opts.seats) ? opts.seats : Array.isArray(tuning.seats) ? tuning.seats : null,
      hour: r.hour || null,
      method: r.def.id,
      // The forge's additions: the heat the frame owns (null for a game without one), the
      // band scale, and `band(steadyFactor)`, the window multiplier a forge game uses: the
      // generous start times the band scale, times the game's own Steady factor from the UI
      // plan §9 table (they differ by game: x1.5 for Alloy, x1.6 for Forge's ring).
      heat: r.heat,
      // The alchemist's reaction gauge and colour stages (null for every other game).
      react: r.react || null,
      stages: r.stages || null,
      // The leather band gauge (null for every other game): the game sets `gauge.v`.
      gauge: r.gauge || null,
      narrow: narrow,
      bandScale: bandScale,
      band: function (steadyFactor) { return baseWin * bandScale * (steady ? (steadyFactor || 1) : 1); },
      // A named sound from the game's own SOUNDS (the forge bus); an unknown key is silent.
      cue: function (key, o) {
        var name = r.def.SOUNDS && r.def.SOUNDS[key];
        if (name) sound(name, Object.assign({}, voice, o || {}));
      },
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
      // `cue` (optional) names a SOUNDS key that plays in place of `hit` for this one
      // press: Prepare lays chalk, salt, ink and a bell, and every piece rang as chalk
      // (the final pass, 2026-10-06: `enchant.salt`, `.ink` and `.bell` were defined and
      // never called). An unknown cue falls back to `hit`.
      hit: function (strength, x, y, kind, index, cue) {
        var s = clamp(strength == null ? 1 : strength, 0, 1);
        r.hits++;
        var hs = r.def.SOUNDS && ((cue && r.def.SOUNDS[cue]) || r.def.SOUNDS.hit);
        sound(hs || "bench.hit." + r.def.id, Object.assign({}, voice, { volume: 0.5 + 0.5 * s }));
        if (r.stage && typeof r.stage.hit === "function") {
          try { if (typeof index === "number") r.stage.hit(s, index); else r.stage.hit(s); }
          catch (e) { r.stage = null; }
        }
        burst(r, x, y, kind || "grit", Math.round(4 + 8 * s));
        if (s >= 0.5) jolt(r);
      },
      miss: function (index) {
        r.misses++;
        var ms = r.def.SOUNDS && r.def.SOUNDS.miss;
        sound(ms || "bench.miss." + r.def.id, voice);
        if (r.stage && typeof r.stage.miss === "function") {
          try { if (typeof index === "number") r.stage.miss(index); else r.stage.miss(); }
          catch (e) { r.stage = null; }
        }
      },
      tick: function () {
        if (typeof performance === "undefined") return;
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
    // A letter is its capital, so R reheats with or without Shift or Caps Lock (the forge's
    // R and T; no herb game uses a letter).
    if (e.key && e.key.length === 1 && /[a-z]/i.test(e.key)) return e.key.toUpperCase();
    return e.key;
  }

  // R is the frame's, not the game's, in a game with heat it can reheat: one reheat path for
  // all five heat games, counted once, and the same as the Reheat button. Answers whether it
  // took the key.
  function reheatKey(r, key) {
    if (key !== "R" || !r.heat || !r.heat.canReheat) return false;
    if (r.heat.reheat()) {
      var rs = r.def.SOUNDS && r.def.SOUNDS.reheat;
      if (rs) sound(rs, {});
    }
    return true;
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
    if (reheatKey(r, key)) return;
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
      },
      reheat: function (e) {
        e.preventDefault();
        if (r.phase === "play") reheatKey(r, "R");
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
    if (r.dom.reheat) r.dom.reheat.addEventListener("click", r.on.reheat);
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
      if (r.dom.reheat) r.dom.reheat.removeEventListener("click", r.on.reheat);
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
    if (r.burner) { try { r.burner.stop(); } catch (e) { /* the fire goes out regardless */ } r.burner = null; }
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
    if (r.dom.reheat) r.dom.reheat.disabled = true;
    if (r.stage) {
      try {
        if (typeof r.stage.update === "function") r.stage.update(r.game.state());
        if (typeof r.stage.end === "function") r.stage.end();
      } catch (e) { /* the result still stands */ }
    }
    if (r.onScore) { try { r.onScore(score); } catch (e) { if (window.console) console.warn(e); } }
    if (!stopped && score >= 0.6) seenSet(r.def.id);
    if (run === r) run = null;
    // `reheats` is what /api/forge/finish charges world minutes for (forge_views, plan §11);
    // 0 for a game without heat, so the herb bench's result only gains a zero.
    r.resolve({ score: score, stopped: !!stopped, hits: r.hits, misses: r.misses,
      reheats: r.heat ? r.heat.reheats : 0 });
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
    var tuning = opts.tuning || {};
    var hour = def.HOUR ? readHour(opts.hour || tuning.hour) : null;
    var dom = build(opts.mount, def, steady, hour);
    if (reduced) dom.root.classList.add("is-still");
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
        particles: [], W: 0, H: 0, dpr: 1, resolve: resolve, rng: KIT.rng(7), hour: hour
      };
      r.C = colours(dom.root);
      r.g = dom.canvas.getContext("2d");
      r.game = def.create(makeCtx(r, opts));
      // The words say the game's own widening (Bind folds the server's eager trait in), when
      // the game reports one.
      if (dom.hour && finite(r.game.widen)) dom.hour.textContent = hourWords(hour, r.game.widen);
      if (r.game.button) {
        var b = el("button", "bench-game__act", r.game.button.label);
        b.type = "button";
        dom.tools.insertBefore(b, dom.help);
        dom.button = b;
      }
      // The alchemist's fire is heard (lane U5, `Sound.burner`): one burner per FLAME game, fed
      // the needle's place on the scale every frame (`feed`) and stopped when the game ends
      // (`finish`). `opts.burner` ("lamp" at the field kit, "athanor" in a laboratory) is the
      // shell's to say; a game without FLAME, or a page without the bus, has none.
      if (def.FLAME && r.heat && window.Sound && typeof window.Sound.burner === "function") {
        try {
          r.burner = window.Sound.burner({ kind: opts.burner || tuning.burner || def.FLAME.burner || "lamp",
            liquid: !!def.FLAME.liquid });
        } catch (e) { r.burner = null; }
      }
      run = r;
      bind(r);
      paint(r);
      showBand(r, 0);
      if (r.heat) showHeat(r);
      if (r.gauge) showGauge(r);
      if (r.stage) {
        try { if (typeof r.stage.update === "function") r.stage.update(r.game.state()); }
        catch (e) { r.stage = null; }
      }
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

  // A game with no strip: the same ctx, heat, R and Steady rules as `play`, stepped by the
  // caller instead of the loop, and nothing drawn. For tests and tuning (tests/
  // test_forge_games.py drives every game through it in node), so what is measured is the
  // frame's own path: `advance` is the loop's step, `reheatKey` the keyboard's R, and a
  // release in Steady mode is dropped here exactly as onKeyUp drops it.
  function simulate(opts) {
    opts = opts || {};
    var def = DEFS[opts.method];
    if (!def) throw new Error("No minigame for the method " + opts.method);
    var C = Object.assign({}, FALLBACK, { display: "serif", body: "serif" });
    var r = {
      def: def, dom: null, stage: null, onScore: null, steady: !!opts.steady, reduced: true,
      t: 0, hits: 0, misses: 0, phase: "play", particles: [], rng: KIT.rng(7), C: C,
      held: { keys: {}, pointer: false }, pointer: { x: -1, y: -1, inside: false, down: false },
      hour: def.HOUR ? readHour(opts.hour || (opts.tuning || {}).hour) : null
    };
    var ctx = makeCtx(r, opts);
    r.game = def.create(ctx);
    return {
      game: r.game, heat: r.heat, ctx: ctx, hour: r.hour, react: r.react || null, stages: r.stages || null,
      gauge: r.gauge || null,
      // What the strip would say over the hint (the day-phase words), for the tests.
      hourWords: function () { return r.hour ? hourWords(r.hour, finite(r.game.widen) ? r.game.widen : null) : ""; },
      t: function () { return r.t; },
      step: function (dt) { advance(r, dt); return !!(r.game.done() || r.t >= r.game.duration); },
      press: function (key) { if (!reheatKey(r, key)) r.game.down({ src: "key", key: key }); },
      release: function (key) {
        if (r.steady || !r.game.up) return;   // STEADY-NO-RELEASE, as onKeyUp
        r.game.up({ src: "key", key: key });
      },
      pointer: function (kind, x, y) {
        r.pointer.x = x; r.pointer.y = y; r.pointer.inside = true;
        var inp = { src: "pointer", x: x, y: y, inside: true, down: r.pointer.down };
        if (kind === "down") { r.pointer.down = true; inp.down = true; r.game.down(inp); }
        else if (kind === "move") { if (r.game.move) r.game.move(inp); }
        else if (kind === "up") {
          r.pointer.down = false;
          if (r.steady || !r.game.up) return;   // STEADY-NO-RELEASE, as onPointerUp
          r.game.up(inp);
        }
      },
      button: function () { if (r.game.button) r.game.button.press(); },
      hint: function () { return hintNow(r); },
      result: function () {
        return { score: clamp(+r.game.score() || 0, 0, 1), hits: r.hits, misses: r.misses,
          reheats: r.heat ? r.heat.reheats : 0 };
      }
    };
  }

  window.BenchGames = {
    play: play,
    stop: stop,
    pause: pause,
    resume: resume,
    methodsFor: function (track) {
      return allMethods().filter(function (m) { return (DEFS[m] && DEFS[m].track || "herb") === track; });
    },
    simulate: simulate,
    gauge: { names: HEAT_NAMES.map(function (b) { return b.name; }), degrees: degrees },
    // The day-phase band's fallback windows and names (tests hold them to rules/sky.py).
    dayPhases: { windows: PHASE_WINDOWS, names: PHASE_NAMES },
    // The band gauge's units (leather contracts §11.1), for the tests.
    bandUnits: Object.keys(BAND_UNITS),
    running: function () { return !!run; },
    kit: KIT
  };
  // `methods` is read when asked, so a game registered after this file loaded is listed too
  // (contracts §11: the method list is extensible by registration). Herbs first, unchanged.
  Object.defineProperty(window.BenchGames, "methods", { get: allMethods, enumerable: true });
})();
