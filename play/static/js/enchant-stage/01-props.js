/* The enchanting bench's stage, part 1: materials and the enchanter's kit.
 *
 * Candles (a lathe of wax with a drip lip, a wick, an emissive flame and a soft halo), the
 * essence phials, the ink pot, a stick of chalk, the salt bowl, the silvered bell, a small cloth
 * for jewellery, and the hand tools that swap at the near edge when the method changes (UI plan
 * §7.1, §10). Low-poly and built in code from the herb kit's primitives (bench-stage/02), with
 * the forge's node helpers (forge-stage/01-props.js), both reused as they are.
 *
 * THE CANDLES ARE NOT LIGHTS. The house shader has three point lights (bench-stage/01-gl.js),
 * and the stage spends them on the candle ring as a whole (the key), the essence's glow and the
 * bind flash (UI plan §6.3). Each flame is an unlit additive mesh with a halo card turned to the
 * camera: the game-art convention for small flames (a camera-facing card and a flame shape,
 * with the flicker done by moving or scaling them; Godot Shaders' "candle flame" and Clockwork
 * Chilli's GLSL fire both build the flame this way rather than as a light per flame). No shader
 * change was needed.
 *
 * Essence colour is CONTENT (UI plan §4): it lives here, in the phial's liquid and the seat's
 * light, never on the chrome.
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var F = window.ForgeStageKit || {};
  var E = window.EnchantStageKit = window.EnchantStageKit || {};
  var G = K.mesh, M = K.math, FP = F.props;
  if (!G || !M || !FP) return;
  var TAU = Math.PI * 2;
  var node = FP.node, add = FP.add, group = FP.group;

  /* The forge's palette plus the circle's own. Patterns are the herb shader's: 1 grain,
     2 stone, 3 clay, 5 iron blotch, 6 leather and cloth, 7 char. */
  var OWN = {
    chalk: { color: [0.86, 0.84, 0.78], spec: 0.05, shin: 6, pattern: 3, patScale: 9 },
    // A little light of its own: wax is translucent and glows under its flame. Lit only from the
    // circle's centre, the candles nearest the camera read as black stubs in the first capture.
    wax: { color: [0.82, 0.74, 0.58], spec: 0.35, shin: 22, pattern: 3, patScale: 3, emit: [0.1, 0.07, 0.035] },
    wick: { color: [0.06, 0.05, 0.045], spec: 0.05, shin: 6 },
    ink: { color: [0.05, 0.045, 0.07], spec: 1.2, shin: 70 },
    salt: { color: [0.9, 0.89, 0.86], spec: 0.5, shin: 30, pattern: 3, patScale: 12 },
    silver: { color: [0.72, 0.73, 0.76], spec: 1.3, shin: 70, metal: 0.8 },
    rug: { color: [0.2, 0.085, 0.07], spec: 0.08, shin: 8, pattern: 6, patScale: 3 },
    vellum: { color: [0.78, 0.7, 0.54], spec: 0.1, shin: 8, pattern: 3, patScale: 5 },
    glass: { color: [0.8, 0.86, 0.84], alpha: 0.14, fresnel: 0.6, spec: 1.4, shin: 90, pass: "alpha", order: 3 },
    liquid: { color: [0.5, 0.5, 0.5], spec: 1.0, shin: 50, alpha: 0.88, pass: "alpha", order: 1 },
    seatglow: { color: [1, 1, 1], unlit: 1, pass: "add", alpha: 0.5, radial: 1.6 },
    halo: { color: [1.0, 0.72, 0.38], unlit: 1, pass: "add", alpha: 0.3, radial: 1.8 },
    line: { color: [1, 1, 1], unlit: 1, pass: "add", alpha: 0.9 }
  };
  function mat(name, over) {
    if (!OWN[name]) return FP.mat(name, over);
    var m = {}, b = OWN[name], k;
    for (k in b) m[k] = Array.isArray(b[k]) ? b[k].slice() : b[k];
    if (over) for (k in over) m[k] = Array.isArray(over[k]) ? over[k].slice() : over[k];
    return m;
  }

  var cache = {};
  function once(k, fn) { if (!cache[k]) cache[k] = fn(); return cache[k]; }
  /* The forge's shadow() builds a fresh disc per call, and the renderer keeps a GPU buffer per
     mesh id until the stage closes; phials are rebuilt whenever the seats change, so a fresh
     disc per phial would grow the buffer map for as long as the bench stays open. Cached. */
  function shadow(r, a) {
    return node(once("shadow" + r.toFixed(3), function () { return G.disc(r, 24); }),
                FP.mat("shadow", { alpha: a === undefined ? 0.55 : a }), { pos: [0, 0.004, 0], glint: false });
  }

  /* --- candles ---------------------------------------------------------------------------- */
  /* h: the candle's height as it stands (burnt down from its full height). Returns {root,
     flame, halo, tip}: the flame and halo are the adapter's to scale, dim and gutter. */
  function candle(h, r) {
    r = r || 0.026;
    var g = group();
    var key = "wax" + h.toFixed(3) + ":" + r.toFixed(3);
    var body = once(key, function () {
      // Drips run down the side as a lumpy lip at the top: a lathe that bulges past the wall.
      return G.merge([
        { mesh: G.lathe([[0, 0], [r * 1.05, 0], [r, h * 0.7], [r * 1.09, h * 0.9], [r * 1.02, h], [r * 0.6, h - 0.006], [0, h - 0.004]], 14, 45),
          m: M.ident() },
        { mesh: G.cylinder(0.0024, 0.014, 5), m: M.compose([0, h - 0.004, 0], [0.12, 0, 0.05], [1, 1, 1]) }
      ]);
    });
    // The body is returned, not added: the adapter welds all eight bodies into one mesh (one draw
    // call, not eight). A blue core inside each flame was cut for the same reason: measured live,
    // draw calls, not pixels, were what the stage's frame time was made of.
    var bodyNode = node(body, mat("wax"));
    var flameMesh = once("flame", function () {
      return G.lathe([[0, 0], [0.0095, 0.006], [0.0125, 0.018], [0.009, 0.034], [0.003, 0.05], [0, 0.056]], 10, 60);
    });
    var tip = h + 0.008;
    var flame = add(g, node(flameMesh, FP.mat("flame", { color: [1.0, 0.7, 0.32], alpha: 0.95 }), { pos: [0, tip, 0], glint: false }));
    var halo = add(g, node(once("halo", function () { return G.disc(0.1, 24); }), mat("halo"), { pos: [0, tip + 0.02, 0], glint: false }));
    return { root: g, body: bodyNode, flame: flame, halo: halo, tip: tip };
  }

  /* --- an essence phial ------------------------------------------------------------------- */
  function phial(color) {
    var g = group();
    var prof = [[0, 0], [0.024, 0], [0.028, 0.008], [0.028, 0.06], [0.012, 0.08], [0.01, 0.1], [0.013, 0.104], [0, 0.104]];
    var liq = mat("liquid", { color: color || [0.6, 0.55, 0.4] });
    var liquid = add(g, node(once("phial-liquid", function () { return G.cylinder(0.024, 0.052, 14); }), liq, { pos: [0, 0.004, 0] }));
    add(g, node(once("phial-glass", function () { return G.lathe(prof, 16, 50); }), mat("glass")));
    add(g, node(once("phial-cork", function () { return G.cylinder(0.0105, 0.022, 8); }), FP.mat("wood", { color: [0.62, 0.47, 0.3], pattern: 3, patScale: 3 }), { pos: [0, 0.098, 0] }));
    add(g, shadow(0.05, 0.45));
    return { root: g, liquid: liquid, top: [0, 0.11, 0] };
  }

  /* --- the near edge: ink, chalk, salt, bell ------------------------------------------------ */
  function inkPot() {
    var g = group();
    add(g, node(once("inkpot", function () {
      return G.lathe([[0, 0], [0.045, 0], [0.05, 0.02], [0.045, 0.05], [0.02, 0.06], [0.022, 0.07], [0.016, 0.07], [0.016, 0.055], [0, 0.055]], 18, 50);
    }), FP.mat("clay", { color: [0.16, 0.13, 0.12], pattern: 3, spec: 0.8, shin: 40 })));
    add(g, node(once("inkdisc", function () { return G.disc(0.015, 12); }), mat("ink"), { pos: [0, 0.066, 0] }));
    add(g, shadow(0.08, 0.5));
    return g;
  }
  function chalkStick() {
    var g = group();
    add(g, node(once("chalk", function () { return G.capsule(0.011, 0.075, 8); }), mat("chalk"), { pos: [0.03, 0.011, 0], rot: [0, 0.4, Math.PI / 2] }));
    return g;
  }
  function saltBowl() {
    var g = group();
    add(g, node(once("bowl", function () {
      return G.lathe([[0, 0], [0.04, 0], [0.065, 0.03], [0.07, 0.036], [0.064, 0.036], [0.058, 0.029], [0.034, 0.008], [0, 0.008]], 20, 40);
    }), FP.mat("wood", { color: [0.36, 0.23, 0.13] })));
    add(g, node(once("saltfill", function () { return G.sphere(0.055, 14, 6); }), mat("salt"), { pos: [0, 0.022, 0], scl: [1, 0.22, 1] }));
    add(g, shadow(0.1, 0.45));
    return g;
  }
  function bell() {
    var g = group();
    add(g, node(once("bell", function () {
      return G.lathe([[0, 0.005], [0.045, 0.005], [0.04, 0.02], [0.03, 0.06], [0.02, 0.075], [0.012, 0.08], [0.008, 0.11], [0.014, 0.12], [0, 0.125]], 18, 40);
    }), mat("silver")));
    add(g, shadow(0.07, 0.5));
    return g;
  }
  function dropper() {
    var g = group();
    add(g, node(once("dropper-glass", function () { return G.lathe([[0, 0], [0.004, 0.004], [0.007, 0.03], [0.008, 0.12], [0, 0.12]], 10, 60); }), mat("glass", { alpha: 0.3 }), { rot: [0, 0, Math.PI / 2 - 0.1], pos: [0.06, 0.01, 0] }));
    add(g, node(once("dropper-bulb", function () { return G.sphere(0.017, 12, 8); }), FP.mat("leather", { color: [0.32, 0.12, 0.08] }), { pos: [-0.065, 0.02, 0], scl: [1.4, 1, 1] }));
    return g;
  }
  function stylus() {
    var g = group();
    add(g, node(once("stylus", function () { return G.lathe([[0, 0], [0.004, 0.02], [0.005, 0.15], [0.007, 0.16], [0, 0.17]], 8, 50); }), mat("silver"), { rot: [0, 0.3, Math.PI / 2], pos: [0.08, 0.007, 0] }));
    return g;
  }
  function lens() {
    var g = group();
    add(g, node(once("lens-rim", function () { return G.ring(0.04, 0.005, 32, 6); }), FP.mat("brass"), { pos: [0, 0.006, 0] }));
    add(g, node(once("lens-glass", function () { return G.disc(0.04, 24); }), mat("glass", { alpha: 0.2 }), { pos: [0, 0.007, 0] }));
    add(g, node(once("lens-handle", function () { return G.capsule(0.007, 0.09, 8); }), FP.mat("darkwood"), { pos: [0.04, 0.007, 0.0], rot: [0, 0, -Math.PI / 2] }));
    return g;
  }
  /* The tool each method lays at the near edge (UI plan §10, "the tools on the near edge swap"). */
  var TOOL = { prepare: "chalk", attune: "salt", bind: "bell", refine: "dropper", unbind: "stylus",
               cleanse: "salt", read: "lens", identify: "lens" };
  var TOOL_BUILD = { chalk: chalkStick, salt: saltBowl, bell: bell, dropper: dropper, stylus: stylus, lens: lens };

  /* A small cloth for a ring or an amulet to lie on (UI plan §6.3). */
  function cloth() {
    return node(once("cloth", function () { return G.box(0.42, 0.006, 0.34); }), FP.mat("cloth", { color: [0.3, 0.1, 0.12], patScale: 2.4 }), { pos: [0, 0.003, 0], rot: [0, 0.08, 0] });
  }

  /* --- the sanctum's furniture ---------------------------------------------------------------- */
  function lectern() {
    var g = group();
    add(g, node(once("lectern", function () {
      return G.merge([
        { mesh: G.box(0.32, 0.03, 0.26), m: M.compose([0, 0.015, 0], [0, 0, 0], [1, 1, 1]) },
        { mesh: G.box(0.08, 0.86, 0.08), m: M.compose([0, 0.45, 0], [0, 0, 0], [1, 1, 1]) },
        { mesh: G.box(0.42, 0.025, 0.32), m: M.compose([0, 0.9, 0.02], [0.45, 0, 0], [1, 1, 1]) }
      ]);
    }), FP.mat("darkwood")));
    add(g, node(once("book", function () { return G.box(0.34, 0.03, 0.24); }), mat("vellum"), { pos: [0, 0.925, 0.03], rot: [0.45, 0, 0] }));
    add(g, shadow(0.3, 0.5));
    return g;
  }
  function shelf() {
    var g = group();
    add(g, node(once("shelf", function () {
      var parts = [];
      [0.3, 0.75, 1.2].forEach(function (y) { parts.push({ mesh: G.box(1.1, 0.03, 0.26), m: M.compose([0, y, 0], [0, 0, 0], [1, 1, 1]) }); });
      [-0.55, 0.55].forEach(function (x) { parts.push({ mesh: G.box(0.04, 1.4, 0.26), m: M.compose([x, 0.7, 0], [0, 0, 0], [1, 1, 1]) }); });
      return G.merge(parts);
    }), FP.mat("darkwood")));
    // Jars and bottles: colour and shape vary a little, so the shelf is a shelf of things.
    var r = M.rng(733), jar = once("jar", function () { return G.lathe([[0, 0], [0.04, 0], [0.045, 0.1], [0.025, 0.13], [0, 0.13]], 12, 50); });
    [0.315, 0.765].forEach(function (y) {
      for (var i = 0; i < 6; i++) {
        var c = [0.25 + r() * 0.4, 0.2 + r() * 0.3, 0.15 + r() * 0.3];
        add(g, node(jar, FP.mat("clay", { color: c, spec: 0.7, shin: 40 }), { pos: [-0.45 + i * 0.18 + r() * 0.04, y, 0], scl: [1, 0.7 + r() * 0.6, 1] }));
      }
    });
    return g;
  }
  /* A round rug under the circle, its top two millimetres above the flags. The first capture
     had a square rug 8 mm thick in a saturated red: it buried the chalk (drawn at 2 mm) and
     filled the stage with one colour. The circle's lines now sit above it (the adapter lifts
     the whole set). */
  function rug() {
    return node(once("rug", function () { return G.cylinder(1.32, 0.002, 64); }), mat("rug"), { glint: false });
  }

  E.props = { mat: mat, candle: candle, phial: phial, inkPot: inkPot, chalkStick: chalkStick, saltBowl: saltBowl,
              bell: bell, dropper: dropper, stylus: stylus, lens: lens, cloth: cloth, lectern: lectern,
              shelf: shelf, rug: rug, TOOL: TOOL, TOOL_BUILD: TOOL_BUILD, TAU: TAU };
})();
