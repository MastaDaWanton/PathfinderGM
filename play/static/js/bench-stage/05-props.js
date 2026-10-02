/* The herbalism bench's stage, part 5: materials, scene nodes, and the small props.
 *
 * MATERIALS are the house palette carried into 3D: brass (the one accent, lit with the
 * house's tight highlight), wood, clay, stone, blackened iron, glass and leather. Liquid
 * and herb colours live INSIDE the scene as content, never on the chrome (UI plan §2: the
 * green --brew banner was retired because it was a second accent on the interface).
 *
 * A NODE is {mesh, mat, pos, rot, scl, kids, alpha, visible}; the stage walks the tree each
 * frame it draws. Nothing here keeps time: poses are set by the tools, and the stage only
 * draws when something asked it to.
 *
 * PROPS are the things that are not a tool: the ingredient chips on the rim, the gold drop
 * ring, and the product that rises on `land`.
 */
(function () {
  "use strict";
  var K = window.BenchStageKit = window.BenchStageKit || {};
  var G = K.mesh;

  var BASE = {
    stone: { color: [0.43, 0.41, 0.38], spec: 0.22, shin: 14, pattern: 2 },
    wood: { color: [0.44, 0.28, 0.15], spec: 0.25, shin: 12, pattern: 1, patScale: 1.6 },
    darkwood: { color: [0.3, 0.19, 0.11], spec: 0.3, shin: 14, pattern: 1 },
    charred: { color: [0.13, 0.09, 0.07], spec: 0.08, shin: 8, pattern: 7 },
    iron: { color: [0.15, 0.14, 0.13], spec: 0.55, shin: 22, pattern: 5, metal: 0.3 },
    steel: { color: [0.62, 0.62, 0.64], spec: 1.2, shin: 60, metal: 0.6 },
    brass: { color: [0.78, 0.6, 0.32], spec: 1.0, shin: 26, metal: 1 },
    clay: { color: [0.62, 0.37, 0.22], spec: 0.2, shin: 10, pattern: 3 },
    glaze: { color: [0.5, 0.42, 0.32], spec: 0.8, shin: 40, pattern: 3 },
    glass: { color: [0.8, 0.88, 0.84], alpha: 0.1, fresnel: 0.55, spec: 1.4, shin: 90,
             pass: "alpha", order: 3 },
    leather: { color: [0.26, 0.16, 0.09], spec: 0.35, shin: 18, pattern: 6 },
    ash: { color: [0.26, 0.25, 0.24], spec: 0.05, shin: 6, pattern: 7 },
    cork: { color: [0.62, 0.47, 0.3], spec: 0.1, shin: 8, pattern: 3, patScale: 3 },
    cloth: { color: [0.6, 0.52, 0.38], spec: 0.1, shin: 8, pattern: 6 },
    enamel: { color: [0.1, 0.085, 0.07], spec: 0.3, shin: 60 },
    rubber: { color: [0.32, 0.12, 0.08], spec: 0.5, shin: 20 },
    ember: { color: [0.12, 0.06, 0.04], spec: 0.1, shin: 8, pattern: 7, emit: [0, 0, 0] },
    flame: { color: [1.0, 0.5, 0.16], unlit: 1, pass: "add", alpha: 0.85 },
    gold: { color: [1.0, 0.8, 0.42], unlit: 1, pass: "add", alpha: 0.95 },
    shadow: { color: [0.0, 0.0, 0.0], unlit: 1, pass: "alpha", alpha: 0.62, radial: 1.4, order: -1 }
  };

  function mat(name, over) {
    var m = {}, b = BASE[name] || {}, k;
    for (k in b) m[k] = Array.isArray(b[k]) ? b[k].slice() : b[k];
    if (over) for (k in over) m[k] = Array.isArray(over[k]) ? over[k].slice() : over[k];
    return m;
  }

  function node(mesh, m, o) {
    var n = { mesh: mesh || null, mat: m || null, pos: [0, 0, 0], rot: [0, 0, 0], scl: [1, 1, 1],
              kids: [], alpha: 1, visible: true, ranges: null, glint: true };
    if (o) for (var k in o) n[k] = o[k];
    return n;
  }
  function add(parent, child) { parent.kids.push(child); return child; }
  function group(o) { return node(null, null, o); }

  /* --- ingredient chips ------------------------------------------------------------------
     One small object per satchel item, shaped by its PART (the contracts' vocabulary), so
     a root reads as a root and a berry as berries even without the icon. Colour alone is
     never the only signal; the shape is. */
  var PART = {
    leaf: ["leaf", [0.34, 0.48, 0.2]], flower: ["flower", [0.62, 0.46, 0.66]],
    root: ["log", [0.5, 0.36, 0.22]], bark: ["slab", [0.36, 0.24, 0.16]],
    berry: ["berries", [0.55, 0.12, 0.15]], seed: ["seeds", [0.6, 0.5, 0.3]],
    sap: ["drop", [0.75, 0.5, 0.15]], resin: ["drop", [0.7, 0.42, 0.12]],
    fungus: ["mushroom", [0.66, 0.56, 0.42]], gland: ["blob", [0.6, 0.34, 0.32]],
    organ: ["blob", [0.5, 0.2, 0.2]], bone: ["log", [0.85, 0.8, 0.68]],
    horn: ["log", [0.7, 0.62, 0.5]], feather: ["leaf", [0.72, 0.7, 0.64]],
    scale: ["puck", [0.3, 0.45, 0.42]], eye: ["berries", [0.85, 0.82, 0.7]],
    shell: ["puck", [0.82, 0.75, 0.65]], oil: ["drop", [0.8, 0.65, 0.25]],
    wax: ["puck", [0.85, 0.75, 0.45]], mineral: ["crystal", [0.55, 0.58, 0.62]],
    liquid: ["drop", [0.4, 0.5, 0.55]]
  };
  var shapeCache = {};
  function shapeMesh(shape) {
    if (shapeCache[shape]) return shapeCache[shape];
    var M = K.math, m;
    if (shape === "leaf") m = G.leaf(0.2, 0.08, 0.15);
    else if (shape === "log") m = G.capsule(0.03, 0.17, 10);
    else if (shape === "slab") m = G.box(0.15, 0.03, 0.08);
    else if (shape === "berries" || shape === "seeds") {
      var r = shape === "seeds" ? 0.018 : 0.03, s = G.sphere(r, 10, 6);
      m = G.merge([{ mesh: s, m: M.compose([0, r, 0], [0, 0, 0], [1, 1, 1]) },
                   { mesh: s, m: M.compose([r * 1.8, r, r * 0.6], [0, 0, 0], [1, 1, 1]) },
                   { mesh: s, m: M.compose([r * 0.6, r, -r * 1.7], [0, 0, 0], [1, 1, 1]) },
                   { mesh: s, m: M.compose([r * 0.9, r * 2.4, -r * 0.3], [0, 0, 0], [1, 1, 1]) }]);
    } else if (shape === "drop") m = G.lathe([[0, 0], [0.04, 0.008], [0.048, 0.03], [0.03, 0.07], [0, 0.1]], 16, 60);
    else if (shape === "mushroom") {
      m = G.merge([{ mesh: G.cylinder(0.018, 0.06, 10), m: M.ident() },
                   { mesh: G.lathe([[0, 0.05], [0.06, 0.05], [0.055, 0.075], [0.03, 0.095], [0, 0.1]], 16, 50), m: M.ident() }]);
    } else if (shape === "blob") m = G.sphere(0.06, 16, 10);
    else if (shape === "puck") m = G.cylinder(0.06, 0.022, 16);
    else if (shape === "crystal") m = G.box(0.07, 0.11, 0.07);
    else if (shape === "flower") {
      var p = G.sphere(0.03, 10, 6), parts = [];
      for (var i = 0; i < 5; i++) {
        var a = i / 5 * Math.PI * 2;
        parts.push({ mesh: p, m: M.compose([Math.cos(a) * 0.035, 0.012, Math.sin(a) * 0.035], [0, -a, 0], [1.2, 0.35, 0.8]) });
      }
      m = G.merge(parts);
    }
    shapeCache[shape] = m;
    return m;
  }

  function chip(part) {
    var def = PART[part] || PART.leaf, shape = def[0], col = def[1];
    var glossy = shape === "drop" || shape === "blob" || shape === "puck" || shape === "crystal";
    var mt = mat("wood", { color: col, pattern: shape === "log" || shape === "slab" ? 1 : 3,
                           spec: glossy ? 0.9 : 0.2, shin: glossy ? 40 : 12, patScale: 4 });
    var g = group();
    var n = add(g, node(shapeMesh(shape), mt));
    if (shape === "leaf") { n.rot = [-Math.PI / 2, 0, 0]; n.pos = [0, 0.012, -0.09]; }
    if (shape === "log") { n.rot = [0, 0, Math.PI / 2]; n.pos = [0.085, 0.03, 0]; }
    if (shape === "slab") n.pos = [0, 0.015, 0];
    if (shape === "blob") n.scl = [1.1, 0.6, 0.9];
    if (shape === "crystal") { n.rot = [0.3, 0.6, 0.25]; n.pos = [0, 0.05, 0]; }
    if (shape === "flower") {
      add(g, node(G.sphere(0.016, 10, 6), mat("wood", { color: [0.85, 0.7, 0.3], pattern: 0 }), { pos: [0, 0.018, 0] }));
    }
    add(g, node(G.disc(0.09, 20), mat("shadow", { alpha: 0.45 }), { pos: [0, 0.004, 0], glint: false }));
    return g;
  }

  /* --- the gold drop ring ----------------------------------------------------------------
     While a tile is dragged over the stage, the tool's rim gets a ring of light AND four
     ticks, so the target has a shape as well as a colour (UI plan §6.3). */
  var ringCache = {};
  function dropRing(r) {
    var key = r.toFixed(3);
    if (!ringCache[key]) ringCache[key] = G.ring(r, 0.014, 72, 8);
    var g = group({ visible: false, alpha: 0 });
    // Additive gold at full strength burned to white over pale stone; this keeps it gold.
    var gm = mat("gold", { color: [0.92, 0.66, 0.3], alpha: 0.75 });
    add(g, node(ringCache[key], gm, { glint: false }));
    var tick = G.box(0.08, 0.016, 0.022);
    for (var i = 0; i < 4; i++) {
      var a = i / 4 * Math.PI * 2 + Math.PI / 4;
      add(g, node(tick, gm, { pos: [Math.cos(a) * (r + 0.07), 0, Math.sin(a) * (r + 0.07)],
                              rot: [0, -a, 0], glint: false }));
    }
    add(g, node(G.disc(r + 0.12, 48), mat("gold", { alpha: 0.18, radial: 0.8 }),
                { pos: [0, -0.004, 0], scl: [1, 1, 1], glint: false }));
    return g;
  }

  /* --- the product ------------------------------------------------------------------------
     What the step made, rising off the tool on `land`. Its form follows the method: a
     powder is a paper twist, a salve a tin, a dried herb a tied bundle, anything liquid a
     corked vial. The UI then flies its own copy from productRect() to the satchel. */
  var PRODUCT = { grind: "pouch", mix: "tin", dry: "bundle" };
  function product(method, liquid) {
    var kind = PRODUCT[method] || "vial", g = group({ visible: false });
    if (kind === "vial") {
      var prof = [[0, 0], [0.07, 0], [0.08, 0.02], [0.08, 0.16], [0.04, 0.2], [0.035, 0.25], [0, 0.25]];
      add(g, node(G.cylinder(0.068, 0.15, 16), mat("wood", { color: liquid || [0.55, 0.4, 0.18],
        pattern: 0, spec: 1, shin: 50, alpha: 0.9, pass: "alpha", order: 1 }), { pos: [0, 0.012, 0] }));
      add(g, node(G.lathe(prof, 20, 50), mat("glass", { alpha: 0.16 })));
      add(g, node(G.cylinder(0.036, 0.06, 12), mat("cork"), { pos: [0, 0.22, 0] }));
    } else if (kind === "pouch") {
      add(g, node(G.sphere(0.12, 16, 10), mat("cloth"), { scl: [1, 0.85, 1], pos: [0, 0.1, 0] }));
      add(g, node(G.lathe([[0.05, 0.17], [0.03, 0.21], [0.06, 0.27], [0, 0.26]], 12, 70), mat("cloth"), {}));
      add(g, node(G.ring(0.036, 0.008, 24, 6), mat("brass"), { pos: [0, 0.205, 0] }));
    } else if (kind === "tin") {
      add(g, node(G.cylinder(0.12, 0.07, 24), mat("brass")));
      add(g, node(G.cylinder(0.125, 0.025, 24), mat("brass", { color: [0.7, 0.52, 0.27] }), { pos: [0, 0.07, 0] }));
    } else {
      var lf = G.leaf(0.24, 0.07, 0.3);
      for (var i = 0; i < 6; i++) {
        add(g, node(lf, mat("wood", { color: [0.55, 0.5, 0.26], pattern: 3 }),
                    { pos: [0, 0.3, 0], rot: [0.25, i / 6 * Math.PI * 2, 0] }));
      }
      add(g, node(G.ring(0.03, 0.01, 20, 6), mat("cloth", { color: [0.7, 0.2, 0.15] }), { pos: [0, 0.27, 0] }));
    }
    // A brass-gold underglow, so the rising product reads as the thing to watch.
    add(g, node(G.disc(0.28, 32), mat("gold", { alpha: 0.35, radial: 1.2 }), { pos: [0, -0.02, 0], glint: false }));
    g.kind = kind;
    // Scaled up from bench size: it is the thing the eye follows to the satchel, and at true
    // scale a vial over the pot was a dozen pixels tall at 16:9.
    g.base = 1.7;
    return g;
  }

  K.props = { mat: mat, node: node, add: add, group: group, chip: chip, dropRing: dropRing,
              product: product, PART: PART };
})();
