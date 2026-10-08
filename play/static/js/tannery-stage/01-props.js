/* The tannery's stage, part 1: the tanner's kit and the yard's furniture.
 *
 * UI plan §7.1: the fleshing beam, the stretching frame, the kit roll, the round knife, the
 * awl and needles, the stitching pony, the mallet and stamps, the slicker, the brain-tan pot
 * (the field kit's small kettle, the owner's 2026-10-08 answer: Harden common and uncommon in
 * the field), the hardening kettle, the sunk vat, the drying rack and the currier's table.
 * Low-poly, built in code from the herb kit's primitives (bench-stage/02-meshes.js) and the
 * forge's node helpers and welding (forge-stage/01-props.js), as the herb tools, the forge's
 * props and the alchemist's glassware are. Every static cluster is welded into one mesh, so a
 * prop is a draw call or two, not one per stave.
 *
 * Each builder returns {root, ...handles}: a node tree standing on y = 0 round its own
 * origin, and the points the adapter needs (where the hide lies, where the water is, where a
 * tool's working edge is). Nothing here keeps time; the adapter poses and draws.
 *
 * THERE IS NO FLAME LOOP. The fire under the pot and the kettle is lit and steady; the plan
 * (§6.3: "the kettle and the vats give steam, not light. No flicker loop") lets this bench
 * idle at zero frames with no exception, unlike the forge's hearth.
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var F = window.ForgeStageKit || {};
  var T = window.TanneryStageKit = window.TanneryStageKit || {};
  var G = K.mesh, M = K.math, GEO = F.geo, FP = F.props;
  if (!G || !M || !GEO || !FP) return;
  var node = FP.node, add = FP.add, group = FP.group, mat = FP.mat, weld = GEO.weld;
  var TAU = Math.PI * 2;

  var cache = {};
  function once(k, fn) { if (!cache[k]) cache[k] = fn(); return cache[k]; }

  /* A rod from a to b: a cylinder (which stands on +y) turned onto the line. */
  function rodRot(a, b) {
    var d = M.sub(b, a), l = Math.sqrt(M.dot(d, d)) || 1e-6, n = M.scale(d, 1 / l);
    return { len: l, rot: [Math.acos(Math.max(-1, Math.min(1, n[1]))), Math.atan2(n[0], n[2]), 0] };
  }
  function rod(a, b, r, seg) {
    var q = rodRot(a, b);
    return [G.cylinder(r, 1, seg || 8), a, q.rot, [1, q.len, 1]];
  }

  /* Materials beyond the forge's palette: the tanner's own. */
  function m(name, over) {
    var own = {
      log: { color: [0.36, 0.26, 0.17], spec: 0.2, shin: 10, pattern: 1, patScale: 1.2 },
      bark: { color: [0.2, 0.15, 0.11], spec: 0.08, shin: 8, pattern: 5, patScale: 2 },
      rope: { color: [0.62, 0.52, 0.36], spec: 0.1, shin: 8, pattern: 1, patScale: 6 },
      sinew: { color: [0.78, 0.68, 0.5], spec: 0.25, shin: 14 },
      salt: { color: [0.9, 0.9, 0.88], spec: 0.3, shin: 20, pattern: 3, patScale: 12 },
      sack: { color: [0.55, 0.47, 0.34], spec: 0.05, shin: 6, pattern: 6, patScale: 3 },
      liquor: { color: [0.22, 0.14, 0.08], alpha: 0.86, spec: 1.2, shin: 70, pass: "alpha", order: 1, fresnel: 0.2 },
      chalk: { color: [0.92, 0.9, 0.84], unlit: 1, pass: "alpha", alpha: 0.85, order: 2 },
      ink: { color: [0.05, 0.035, 0.025], unlit: 1, pass: "alpha", alpha: 0.88, order: 2 },
      thatch: { color: [0.46, 0.38, 0.24], spec: 0.05, shin: 6, pattern: 1, patScale: 4 },
      flag: { color: [0.44, 0.42, 0.39], spec: 0.25, shin: 16, pattern: 2, patScale: 1.2 },
      glass: { color: [0.8, 0.86, 0.84], alpha: 0.25, fresnel: 0.6, spec: 1.4, shin: 90, pass: "alpha", order: 3 }
    };
    if (!own[name]) return mat(name, over);
    var o = {}, b = own[name], k;
    for (k in b) o[k] = Array.isArray(b[k]) ? b[k].slice() : b[k];
    if (over) for (k in over) o[k] = Array.isArray(over[k]) ? over[k].slice() : over[k];
    return o;
  }

  /* --- the fleshing beam: a log on two splayed legs, one end on the ground -------------- */
  // Returns the log's axis so the hide drape lies on exactly this log.
  var BEAM = { R: 0.085, len: 1.7, tilt: 0.36 };
  function fleshingBeam() {
    var g = group(), R = BEAM.R, L = BEAM.len, t = BEAM.tilt;
    // The low end rests on the ground at x = -L/2 cos t; the high end on the legs.
    var lowY = R * 0.9, mid = [0, lowY + Math.sin(t) * L / 2, 0];
    var mesh = once("beam", function () {
      var ax = [Math.cos(t), Math.sin(t), 0];
      var a = M.sub(mid, M.scale(ax, L / 2)), b = M.add(mid, M.scale(ax, L / 2));
      var hi = M.sub(b, M.scale(ax, 0.18));
      return weld([
        rod(a, b, R, 14),
        rod(hi, [hi[0] + 0.12, 0, 0.28], 0.03, 6), rod(hi, [hi[0] + 0.12, 0, -0.28], 0.03, 6),
        [G.cylinder(R * 0.98, 0.012, 14), b, rodRot(a, b).rot]
      ]);
    });
    add(g, node(mesh, m("log")));
    add(g, FP.shadow(0.5, 0.35, { scl: [1.9, 1, 0.55] }));
    return { root: g, axis: { at: mid, R: R, tilt: t, len: L } };
  }

  /* --- the stretching frame: four poles lashed, leaning back ------------------------------ */
  function stretchFrame(w, h) {
    var g = group(), lean = 0.2, hw = w / 2, base = 0.06;
    var up = [0, Math.cos(lean), -Math.sin(lean)];
    var c = [0, base + h / 2 * Math.cos(lean), -h / 2 * Math.sin(lean)];
    function P(x, y) { return M.add(c, M.add([x, 0, 0], M.scale(up, y))); }
    var k = "frame" + w.toFixed(2) + h.toFixed(2);
    var mesh = once(k, function () {
      var pad = 0.08, r = 0.026;
      return weld([
        rod(P(-hw - pad, -h / 2 - 0.12), P(-hw - pad, h / 2 + 0.12), r, 8),
        rod(P(hw + pad, -h / 2 - 0.12), P(hw + pad, h / 2 + 0.12), r, 8),
        rod(P(-hw - pad - 0.1, h / 2 + 0.06), P(hw + pad + 0.1, h / 2 + 0.06), r, 8),
        rod(P(-hw - pad - 0.1, -h / 2 - 0.06), P(hw + pad + 0.1, -h / 2 - 0.06), r, 8),
        // The prop behind that keeps it standing.
        rod(P(0, h / 2 + 0.06), [0, 0, -0.95], 0.022, 6)
      ]);
    });
    add(g, node(mesh, m("darkwood")));
    return { root: g, centre: c, lean: lean, hl: h / 2, hw: hw, post: hw + 0.08, P: P };
  }

  /* The lacing from the hide's edge to the frame's poles: one welded mesh per hide shape.
     `edge` is in the set's frame and `origin` is where the frame stands in it. */
  function lacing(edge, fr, origin, key) {
    return once("lace" + key, function () {
      var parts = [], c = M.add(origin, fr.centre), up = [0, Math.cos(fr.lean), -Math.sin(fr.lean)];
      edge.forEach(function (p) {
        var side = p[0] >= c[0] ? 1 : -1;
        var along = Math.max(-fr.hl, Math.min(fr.hl, M.dot(M.sub(p, c), up)));
        parts.push(rod(p, M.add(origin, fr.P(side * fr.post, along)), 0.003, 4));
      });
      return parts.length ? weld(parts) : null;
    });
  }

  /* --- the kit roll, open on the ground, with the tools on it ---------------------------- */
  function kitRoll() {
    var g = group();
    var sheetM = once("roll-sheet", function () {
      return weld([[G.box(0.62, 0.006, 0.34), [0, 0.003, 0]], [G.cylinder(0.035, 0.34, 12), [-0.33, 0.035, -0.17], [Math.PI / 2, 0, 0]]]);
    });
    var sheet = add(g, node(sheetM, mat("leather", { color: [0.3, 0.19, 0.11] })));
    var tools = once("roll-tools", function () {
      return weld([
        // A skinning knife, a round knife's handle, an awl, two needles and a mallet laid in.
        [G.box(0.16, 0.004, 0.022), [-0.18, 0.012, -0.1]],
        [G.capsule(0.011, 0.1, 8), [-0.04, 0.012, -0.1], [0, 0, Math.PI / 2]],
        [G.capsule(0.009, 0.08, 8), [-0.12, 0.012, 0.0], [0, 0, Math.PI / 2]],
        [G.lathe([[0, 0], [0.004, 0], [0, 0.05]], 6, 60), [-0.12, 0.012, 0.0], [0, 0, -Math.PI / 2]],
        [G.cylinder(0.0016, 0.07, 4), [0.02, 0.008, 0.06], [0, 0, Math.PI / 2]],
        [G.cylinder(0.0016, 0.06, 4), [0.02, 0.008, 0.08], [0, 0, Math.PI / 2]],
        [G.cylinder(0.03, 0.08, 12), [0.14, 0.033, -0.08], [Math.PI / 2, 0, 0]],
        [G.cylinder(0.009, 0.2, 6), [0.14, 0.033, -0.04], [0, 0, Math.PI / 2], [1, 1, 1]]
      ]);
    });
    add(g, node(tools, mat("steel", { color: [0.5, 0.48, 0.45], spec: 0.8 })));
    add(g, FP.shadow(0.4, 0.3, { scl: [1, 1, 0.6] }));
    return { root: g, sheet: sheet };
  }

  /* --- hand tools: the one in use comes forward when the method changes ------------------ */
  function handle(len, r) { return G.capsule(r || 0.013, len, 8); }

  // The two-handled fleshing knife: a curved blade between two handles, along x.
  function fleshingKnife() {
    var g = group();
    add(g, node(once("fk-blade", function () { return weld([[G.box(0.32, 0.03, 0.004), [0, 0.0, 0]]]); }), mat("steel")));
    add(g, node(once("fk-handles", function () {
      return weld([[handle(0.11), [-0.16, 0, 0], [0, 0, Math.PI / 2]], [handle(0.11), [0.27, 0, 0], [0, 0, Math.PI / 2]]]);
    }), mat("wood")));
    return { root: g, edge: [0, -0.015, 0] };
  }
  // The round knife: a half-moon blade on a short handle.
  function roundKnife() {
    var g = group();
    add(g, node(once("rk-blade", function () {
      var pos = [0, 0, 0], nrm = [0, 0, 1], uv = [0, 0], idx = [], n = 16;
      for (var i = 0; i <= n; i++) { var a = Math.PI * i / n; pos.push(Math.cos(a) * 0.06, -Math.sin(a) * 0.05, 0); nrm.push(0, 0, 1); uv.push(0, 0); }
      for (var j = 1; j <= n; j++) idx.push(0, j, j + 1);
      return GEO.finish(pos, nrm, uv, idx);
    }), mat("steel", { spec: 1.3 })));
    add(g, node(once("rk-handle", function () { return weld([[handle(0.08, 0.012), [0, 0, 0]], [G.cylinder(0.005, 0.03, 6), [0, -0.03, 0]]]); }), mat("wood")));
    return { root: g, edge: [0, -0.05, 0] };
  }
  function slicker() {
    var g = group();
    add(g, node(once("sl-blade", function () { return G.box(0.13, 0.05, 0.004); }), mat("steel", { color: [0.45, 0.45, 0.46] }), { pos: [0, 0.025, 0] }));
    add(g, node(once("sl-handle", function () { return G.box(0.15, 0.035, 0.03); }), mat("wood"), { pos: [0, 0.06, 0] }));
    return { root: g, edge: [0, 0, 0] };
  }
  function malletStamp() {
    var g = group();
    add(g, node(once("mallet", function () {
      return weld([[G.cylinder(0.04, 0.12, 14), [-0.06, 0.12, 0], [0, 0, Math.PI / 2]], [G.cylinder(0.011, 0.2, 8), [0.0, 0.12, 0], [0, 0, 0]]]);
    }), mat("rope", { color: [0.7, 0.6, 0.45] })));
    var stamp = add(g, node(once("stamp", function () { return G.cylinder(0.008, 0.1, 8); }), mat("steel"), { pos: [0.1, 0, 0.02] }));
    return { root: g, stamp: stamp, edge: [0.1, 0, 0.02] };
  }
  function brush(col) {
    var g = group();
    add(g, node(once("brush-h", function () { return G.cylinder(0.007, 0.16, 6); }), mat("wood"), { pos: [0, 0.03, 0], rot: [0, 0, 0.5] }));
    var tip = add(g, node(once("brush-t", function () { return G.lathe([[0, 0], [0.012, 0.01], [0.01, 0.04], [0, 0.045]], 8, 60); }), mat("cloth", { color: col || [0.4, 0.3, 0.2] }), { pos: [0.015, 0, 0], rot: [0, 0, 0.5] }));
    return { root: g, tip: tip, edge: [0, 0, 0] };
  }
  function needlePair(col) {
    var g = group();
    add(g, node(once("needles", function () { return weld([[G.cylinder(0.0018, 0.07, 4), [-0.03, 0, 0]], [G.cylinder(0.0018, 0.07, 4), [0.03, 0, 0]]]); }), mat("steel")));
    var thread = add(g, node(once("needle-thread", function () { return weld([rod([-0.03, 0.07, 0], [0, 0.12, 0.02], 0.0012, 4), rod([0.03, 0.07, 0], [0, 0.12, 0.02], 0.0012, 4)]); }), mat("cloth", { color: col || [0.85, 0.8, 0.66] })));
    return { root: g, thread: thread, edge: [0, 0, 0] };
  }
  function magnifier() {
    var g = group();
    add(g, node(once("mag-ring", function () { return G.ring(0.035, 0.004, 24, 6); }), mat("brass"), { rot: [Math.PI / 2, 0, 0] }));
    add(g, node(once("mag-glass", function () { return G.cylinder(0.034, 0.002, 20); }), m("glass"), { rot: [Math.PI / 2, 0, 0], pos: [0, 0, -0.001] }));
    add(g, node(once("mag-h", function () { return G.capsule(0.008, 0.09, 8); }), mat("darkwood"), { pos: [0, -0.035, 0], rot: [Math.PI, 0, 0] }));
    return { root: g, edge: [0, 0, 0] };
  }
  function clamp2() {
    var g = group();
    add(g, node(once("clamp", function () {
      return weld([[G.box(0.02, 0.09, 0.02), [0, 0.045, 0]], [G.box(0.07, 0.016, 0.02), [0.025, 0.09, 0]], [G.box(0.07, 0.016, 0.02), [0.025, 0.0, 0]]]);
    }), mat("iron")));
    return { root: g, edge: [0.05, 0.05, 0] };
  }
  var HAND = { flense: fleshingKnife, cut: roundKnife, curry: slicker, tool: malletStamp, dye: brush,
               stitch: needlePair, grade: magnifier, laminate: clamp2 };

  /* --- the stitching pony: two jaws clamped by a peg, on a low stool --------------------- */
  function stitchingPony() {
    var g = group();
    add(g, node(once("pony", function () {
      return weld([
        [G.box(0.3, 0.04, 0.22), [0, 0.2, 0]],
        rod([-0.12, 0, -0.08], [-0.12, 0.2, -0.08], 0.016, 6), rod([0.12, 0, -0.08], [0.12, 0.2, -0.08], 0.016, 6),
        rod([-0.12, 0, 0.08], [-0.12, 0.2, 0.08], 0.016, 6), rod([0.12, 0, 0.08], [0.12, 0.2, 0.08], 0.016, 6),
        // The jaws face the camera: a piece stands between them in the x-y plane.
        [G.box(0.26, 0.3, 0.03), [0, 0.37, -0.025], [0.06, 0, 0]],
        [G.box(0.26, 0.3, 0.03), [0, 0.37, 0.025], [-0.06, 0, 0]],
        rod([0, 0.32, -0.08], [0, 0.32, 0.08], 0.01, 8)
      ]);
    }), m("darkwood")));
    return { root: g, jaw: [0, 0.52, 0] };
  }

  /* --- fire, pot and kettle ----------------------------------------------------------------- */
  function fire(scale) {
    var g = group(), s = scale || 1;
    add(g, node(once("fire-stones", function () {
      var parts = [], n = 9;
      for (var i = 0; i < n; i++) { var a = i / n * TAU; parts.push([G.sphere(0.04, 8, 6), [Math.cos(a) * 0.15, 0.02, Math.sin(a) * 0.15], [0, a, 0], [1.2, 0.7, 1]]); }
      return weld(parts);
    }), mat("stone"), { scl: [s, s, s] }));
    add(g, node(once("fire-logs", function () {
      return weld([rod([-0.11, 0.02, -0.04], [0.1, 0.05, 0.05], 0.022, 7), rod([0.1, 0.02, -0.06], [-0.09, 0.05, 0.06], 0.022, 7)]);
    }), mat("soot"), { scl: [s, s, s] }));
    var flame = add(g, node(once("flame", function () {
      return weld([[G.lathe([[0.05, 0], [0.035, 0.05], [0, 0.13]], 10, 60), [0, 0.03, 0]],
                   [G.lathe([[0.03, 0], [0.02, 0.04], [0, 0.09]], 8, 60), [0.04, 0.03, 0.02]]]);
    }), mat("flame", { alpha: 0.75 }), { scl: [s, s, s] }));
    var glow = add(g, node(G.disc(0.28, 20), mat("glow", { alpha: 0.35 }), { pos: [0, 0.01, 0], scl: [s, 1, s], glint: false }));
    return { root: g, flame: flame, glow: glow, light: [0, 0.14 * s, 0] };
  }

  /* A pot hung over a fire on three sticks: the brain-tan pot and the field kit's small
     kettle in one (UI plan §6.3). `water` is the surface node and `mouth` its height. */
  function potOverFire() {
    var g = group(), f = fire(0.8);
    add(g, f.root);
    add(g, node(once("tripod", function () {
      var top = [0, 0.62, 0];
      return weld([rod([0.3, 0, 0.15], top, 0.014, 6), rod([-0.3, 0, 0.15], top, 0.014, 6), rod([0, 0, -0.32], top, 0.014, 6),
                   rod(top, [0, 0.4, 0], 0.003, 4)]);
    }), m("darkwood")));
    var prof = [[0.12, 0], [0.16, 0.06], [0.17, 0.14], [0.155, 0.2], [0.145, 0.2], [0.155, 0.14], [0.145, 0.06], [0.1, 0.008]];
    var pot = add(g, node(once("pot", function () { return weld([[G.lathe(prof, 20, 35), [0, 0, 0]], [G.ring(0.15, 0.004, 20, 4), [0, 0.2, 0]]]); }), mat("iron", { spec: 0.6 }), { pos: [0, 0.2, 0] }));
    var water = add(g, node(G.disc(0.148, 24), m("liquor", { color: [0.3, 0.33, 0.32] }), { pos: [0, 0.37, 0] }));
    return { root: g, pot: pot, water: water, mouth: [0, 0.4, 0], fire: f, r: 0.148, light: [0, 0.18, 0.1] };
  }

  /* The yard's hardening kettle: a wide cauldron on an iron ring stand over a stone hearth. */
  function kettleStand() {
    var g = group(), f = fire(1.1);
    add(g, f.root);
    add(g, node(once("kettle-stand", function () {
      var parts = [[G.ring(0.27, 0.012, 24, 6), [0, 0.38, 0]]];
      for (var i = 0; i < 3; i++) { var a = i / 3 * TAU + 0.5; parts.push(rod([Math.cos(a) * 0.32, 0, Math.sin(a) * 0.32], [Math.cos(a) * 0.27, 0.38, Math.sin(a) * 0.27], 0.014, 6)); }
      return weld(parts);
    }), mat("iron")));
    var prof = [[0.16, 0], [0.26, 0.08], [0.3, 0.2], [0.29, 0.3], [0.28, 0.3], [0.285, 0.2], [0.25, 0.08], [0.15, 0.01]];
    add(g, node(once("kettle", function () { return weld([[G.lathe(prof, 26, 35), [0, 0, 0]], [G.ring(0.285, 0.008, 26, 4), [0, 0.3, 0]]]); }), mat("iron", { color: [0.2, 0.18, 0.17], spec: 0.55, metal: 0.4 }), { pos: [0, 0.3, 0] }));
    var water = add(g, node(G.disc(0.28, 28), m("liquor", { color: [0.28, 0.3, 0.29], alpha: 0.82 }), { pos: [0, 0.56, 0] }));
    return { root: g, water: water, mouth: [0, 0.6, 0], fire: f, r: 0.28, light: [0, 0.24, 0.12] };
  }

  /* --- vats, the table, the rack, the salt and the dye ------------------------------------- */

  /* A tan pit: sunk in the yard, its timber curb standing a hand proud of the ground and the
     liquor just under the curb. Sunk flush, the yard's one ground plane hid the liquor (the
     first live capture showed three empty rings): the stage has no hole to cut in its floor,
     so the curb is raised instead, as a lined pit's is. */
  function sunkVat(r) {
    var g = group();
    r = r || 0.45;
    add(g, node(once("vat" + r, function () {
      var curb = [[r + 0.07, 0], [r + 0.07, 0.15], [r + 0.02, 0.17], [r - 0.01, 0.15], [r - 0.01, 0.02], [0, 0.02]];
      return weld([[G.lathe(curb, 28, 35), [0, 0, 0]]]);
    }), m("darkwood")));
    var liquor = add(g, node(G.disc(r - 0.008, 30), m("liquor"), { pos: [0, 0.12, 0] }));
    return { root: g, liquor: liquor, r: r - 0.02, surface: [0, 0.12, 0] };
  }

  /* The currier's table (and, at the kit, a low board on the ground): a plain top on legs. */
  function table(w, d, h) {
    var g = group(), k = "table" + [w, d, h].join(",");
    add(g, node(once(k, function () {
      var parts = [[G.box(w, 0.05, d), [0, h - 0.025, 0]]];
      if (h > 0.2) {
        [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(function (s) { parts.push([G.box(0.06, h - 0.05, 0.06), [s[0] * (w / 2 - 0.08), (h - 0.05) / 2, s[1] * (d / 2 - 0.08)]]); });
        parts.push([G.box(w - 0.2, 0.04, 0.04), [0, 0.18, 0]]);
      }
      return weld(parts);
    }), mat("wood", { color: [0.5, 0.36, 0.22], pattern: 1, patScale: 1.1 })));
    add(g, FP.shadow(Math.max(w, d) * 0.62, 0.35, { scl: [1, 1, d / w] }));
    return { root: g, top: h, hx: w / 2, hz: d / 2 };
  }

  /* A drying rack: two A-frames and a pole, with hides hung over it (other work of the yard's,
     in the yard's own tannage colours). `hang(pole)` gives the drape for one hung hide. */
  function dryingRack(len) {
    var g = group(), h = 1.35;
    add(g, node(once("rack" + len, function () {
      var parts = [];
      [-len / 2, len / 2].forEach(function (x) {
        parts.push(rod([x, 0, 0.32], [x, h, 0], 0.025, 6), rod([x, 0, -0.32], [x, h, 0], 0.025, 6));
      });
      parts.push(rod([-len / 2 - 0.08, h, 0], [len / 2 + 0.08, h, 0], 0.03, 8));
      return weld(parts);
    }), m("darkwood")));
    return { root: g, pole: [0, h, 0], len: len };
  }

  function saltSack() {
    var g = group();
    add(g, node(once("sack", function () {
      return G.lathe([[0, 0], [0.13, 0.01], [0.15, 0.08], [0.14, 0.2], [0.1, 0.27], [0.11, 0.3], [0.0, 0.31]], 14, 50);
    }), m("sack")));
    add(g, node(once("salt-pile", function () { return G.lathe([[0.16, 0], [0.08, 0.05], [0, 0.07]], 16, 60); }), m("salt"), { pos: [0.24, 0, 0.05] }));
    return { root: g, mouth: [0.24, 0.07, 0.05] };
  }

  function dyePot(col) {
    var g = group();
    add(g, node(once("dyepot", function () { return G.lathe([[0.07, 0], [0.09, 0.05], [0.085, 0.1], [0.078, 0.1], [0.08, 0.05], [0.06, 0.006]], 16, 35); }), mat("clay")));
    var dye = add(g, node(G.disc(0.078, 18), m("liquor", { color: col || [0.3, 0.2, 0.12], alpha: 0.95 }), { pos: [0, 0.088, 0] }));
    return { root: g, dye: dye, mouth: [0, 0.1, 0] };
  }

  function spool(col) {
    var g = group();
    add(g, node(once("spool-w", function () { return weld([[G.cylinder(0.025, 0.006, 12), [0, 0, 0]], [G.cylinder(0.025, 0.006, 12), [0, 0.054, 0]]]); }), mat("wood")));
    var th = add(g, node(once("spool-t", function () { return G.cylinder(0.02, 0.048, 12); }), mat("cloth", { color: col || [0.85, 0.8, 0.66] }), { pos: [0, 0.006, 0] }));
    return { root: g, thread: th };
  }
  function oilFlask(col) {
    var g = group();
    add(g, node(once("oilflask", function () { return G.lathe([[0.04, 0], [0.05, 0.04], [0.03, 0.11], [0.014, 0.13], [0.016, 0.15], [0, 0.15]], 14, 40); }), mat("clay", { color: col || [0.5, 0.36, 0.2], spec: 0.5 })));
    return { root: g };
  }
  function lantern() {
    var g = group();
    add(g, node(once("lantern", function () { return weld([[G.box(0.1, 0.012, 0.1), [0, 0, 0]], [G.box(0.1, 0.012, 0.1), [0, 0.16, 0]], [G.ring(0.02, 0.004, 10, 4), [0, 0.18, 0], [Math.PI / 2, 0, 0]]]); }), mat("iron")));
    var light = add(g, node(once("lantern-glow", function () { return G.box(0.07, 0.14, 0.07); }), mat("gold", { alpha: 0.7 }), { pos: [0, 0.08, 0] }));
    return { root: g, light: light, at: [0, 0.09, 0] };
  }

  /* --- the yard's ground and its shelters ---------------------------------------------------- */

  /* Flagstones for a town yard: irregular slabs welded into one mesh (no texture painted). */
  function flagstones(w, d) {
    return node(once("flags" + w + d, function () {
      var r = M.rng(4242), parts = [], s = 0.34;
      for (var x = -w / 2; x < w / 2; x += s) {
        for (var z = -d / 2; z < d / 2; z += s * 0.9) {
          var jx = (r() - 0.5) * 0.012, jz = (r() - 0.5) * 0.012, h = 0.012 + r() * 0.01;
          parts.push([G.box(s - 0.01 - r() * 0.012, h, s * 0.9 - 0.01 - r() * 0.012), [x + s / 2 + jx, h / 2, z + s * 0.45 + jz], [0, (r() - 0.5) * 0.06, 0]]);
        }
      }
      return weld(parts);
    }), m("flag"));
  }

  /* A lean-to (town) or a plank shed (founded), behind the work: posts and a sloped roof. */
  function shelter(owned) {
    var g = group(), w = 3.4;
    add(g, node(once("shelter" + (owned ? 1 : 0), function () {
      var parts = [rod([-w / 2, 0, 0.4], [-w / 2, 1.9, 0.4], 0.04, 6), rod([w / 2, 0, 0.4], [w / 2, 1.9, 0.4], 0.04, 6),
                   rod([-w / 2, 0, -0.6], [-w / 2, 2.4, -0.6], 0.04, 6), rod([w / 2, 0, -0.6], [w / 2, 2.4, -0.6], 0.04, 6)];
      var n = owned ? 13 : 1;
      for (var i = 0; i < n; i++) {
        var x = -w / 2 + (i + 0.5) * w / n;
        parts.push([G.box(owned ? w / n - 0.02 : w + 0.3, 0.03, 1.25), [x, 2.2, -0.1], [-0.42, 0, 0]]);
      }
      if (owned) for (var j = 0; j < 12; j++) parts.push([G.box(w / 12 - 0.015, 2.3, 0.03), [-w / 2 + (j + 0.5) * w / 12, 1.15, -0.62]]);
      return weld(parts);
    }), owned ? mat("wood", { color: [0.36, 0.25, 0.16] }) : m("thatch")));
    return { root: g };
  }

  T.props = {
    m: m, rod: rod, rodRot: rodRot, once: once, BEAM: BEAM, HAND: HAND,
    fleshingBeam: fleshingBeam, stretchFrame: stretchFrame, lacing: lacing, kitRoll: kitRoll,
    fleshingKnife: fleshingKnife, roundKnife: roundKnife, slicker: slicker, malletStamp: malletStamp,
    brush: brush, needlePair: needlePair, magnifier: magnifier, clamp2: clamp2,
    stitchingPony: stitchingPony, fire: fire, potOverFire: potOverFire, kettleStand: kettleStand,
    sunkVat: sunkVat, table: table, dryingRack: dryingRack, saltSack: saltSack, dyePot: dyePot,
    spool: spool, oilFlask: oilFlask, lantern: lantern, flagstones: flagstones, shelter: shelter
  };
})();
