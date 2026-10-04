/* The forge's stage, part 1: materials, nodes, the sweep builder, and the smith's kit.
 *
 * Built in code like the herb tools (bench-stage/06-tools.js), from the herb kit's
 * primitives (bench-stage/02-meshes.js), which this file uses as is. Two things are added
 * here because a forge needs them and a herbalist does not:
 *
 *   SWEEP. A blade, an axe's cheek and a spear's leaf are a cross-section carried along a
 *   path, with the width and thickness changing as it goes. The lathe cannot make a flat
 *   diamond; a box cannot taper to an edge. `sweep` builds each FACE of the section as its
 *   own strip, smooth along the path and creased across it, so a blade's ridge and edge stay
 *   sharp while its length reads as one surface. It can cut its stations into runs, one mesh
 *   each, so the temper colour can run along a blade a segment at a time (04-fx.js).
 *
 *   IDS. Every mesh is passed once through K.mesh.merge, which hands it an id from the herb
 *   kit's own counter. The renderer keys its GPU buffers by mesh id (01-gl.js), so a second
 *   counter here would hand out ids the herb kit already used and two meshes would share one
 *   buffer.
 *
 * PROPS are what stands round the anvil: the camp anvil and the smithy anvil, the field
 * hearth and the furnace mouth, bellows, the quench bucket and trough, the whetstone wheel
 * (a hand stone at the field kit), the crucible and tongs, the tool rack, and the hand tools
 * that swap on the rack when the method changes (UI plan §10). Each returns a node tree
 * standing on y = 0 round its own origin, plus whatever handles the stage moves.
 *
 * Nothing here keeps time. The adapter (table/42-forge-stage.js) poses and draws.
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var F = window.ForgeStageKit = window.ForgeStageKit || {};
  var G = K.mesh, M = K.math;
  if (!G || !M) return;   // the herb kit's parts did not load; the adapter goes flat
  var TAU = Math.PI * 2;

  /* --- materials --------------------------------------------------------------------------
     The house palette carried into 3D, as the herb kit's are (bench-stage/05-props.js), with
     the forge's own: anvil iron, brick, coal, water. Heat colour is CONTENT and lives only in
     the scene (UI plan §4); the chrome never sees it. Patterns are the herb shader's own:
     1 grain, 2 stone, 3 clay, 4 lumps (a bent normal), 5 iron blotch, 6 leather, 7 char. */
  var BASE = {
    // Measured in the scratch harness: at 0.11 the anvil read as a black hole under a cherry
    // blank even with the blank's light on it; 0.2 lets the heat show on its body.
    anvil: { color: [0.2, 0.19, 0.18], spec: 0.8, shin: 30, pattern: 5, metal: 0.45 },
    face: { color: [0.45, 0.44, 0.43], spec: 1.4, shin: 64, metal: 0.7 },
    iron: { color: [0.16, 0.15, 0.14], spec: 0.55, shin: 22, pattern: 5, metal: 0.3 },
    steel: { color: [0.6, 0.6, 0.62], spec: 1.2, shin: 60, metal: 0.6 },
    brass: { color: [0.78, 0.6, 0.32], spec: 1.0, shin: 26, metal: 1 },
    wood: { color: [0.42, 0.27, 0.15], spec: 0.25, shin: 12, pattern: 1, patScale: 1.6 },
    darkwood: { color: [0.26, 0.17, 0.1], spec: 0.3, shin: 14, pattern: 1 },
    stump: { color: [0.36, 0.25, 0.15], spec: 0.15, shin: 10, pattern: 1, patScale: 0.9 },
    stone: { color: [0.42, 0.4, 0.37], spec: 0.22, shin: 14, pattern: 2 },
    brick: { color: [0.42, 0.2, 0.13], spec: 0.15, shin: 10, pattern: 2, patScale: 1.4 },
    soot: { color: [0.07, 0.06, 0.055], spec: 0.08, shin: 8, pattern: 7 },
    clay: { color: [0.55, 0.33, 0.2], spec: 0.2, shin: 10, pattern: 3 },
    leather: { color: [0.25, 0.15, 0.08], spec: 0.35, shin: 18, pattern: 6 },
    cloth: { color: [0.5, 0.43, 0.32], spec: 0.1, shin: 8, pattern: 6 },
    coal: { color: [0.06, 0.055, 0.05], spec: 0.5, shin: 30, pattern: 7, emit: [0, 0, 0] },
    water: { color: [0.12, 0.15, 0.15], alpha: 0.78, spec: 1.6, shin: 90, pass: "alpha", order: 1, fresnel: 0.3 },
    flame: { color: [1.0, 0.5, 0.16], unlit: 1, pass: "add", alpha: 0.85 },
    glow: { color: [1.0, 0.45, 0.12], unlit: 1, pass: "add", alpha: 0.5, radial: 1.4 },
    gold: { color: [1.0, 0.8, 0.42], unlit: 1, pass: "add", alpha: 0.95 },
    shadow: { color: [0, 0, 0], unlit: 1, pass: "alpha", alpha: 0.6, radial: 1.4, order: -1 }
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
  function shadow(r, a, o) {
    var n = node(G.disc(r, 32), mat("shadow", { alpha: a === undefined ? 0.55 : a }), { glint: false });
    n.pos = [0, 0.004, 0];
    if (o) for (var k in o) n[k] = o[k];
    return n;
  }

  /* --- geometry ------------------------------------------------------------------------- */

  /* Raw arrays to a renderable mesh, with an id from the herb kit's counter (see header). */
  function finish(pos, nrm, uv, idx) {
    var raw = { pos: pos, nrm: nrm, uv: uv, idx: idx };
    return G.merge([{ mesh: raw, m: M.ident() }]);
  }
  /* Static parts welded into one mesh: [mesh, pos, rot, scl] each. */
  function weld(parts) {
    return G.merge(parts.map(function (p) {
      return { mesh: p[0], m: M.compose(p[1] || [0, 0, 0], p[2] || [0, 0, 0], p[3] || [1, 1, 1]) };
    }));
  }

  /* sweep(n, k, at, opts): n stations along a path, k points round a closed section;
     at(i, j) gives station i's point j. Each face j..j+1 is its own strip (creased across,
     smooth along). opts.runs: station indices to cut at, giving one mesh per run; opts.caps
     closes the two ends. Returns an array of meshes (one unless runs are given). */
  function sweep(n, k, at, opts) {
    opts = opts || {};
    var P = [], i, j;
    for (i = 0; i < n; i++) { P.push([]); for (j = 0; j < k; j++) P[i].push(at(i, j)); }
    var cuts = (opts.runs || []).filter(function (c) { return c > 0 && c < n - 1; });
    var bounds = [0].concat(cuts, [n - 1]), out = [];
    function centre(row) {
      var c = [0, 0, 0];
      row.forEach(function (p) { c[0] += p[0]; c[1] += p[1]; c[2] += p[2]; });
      return M.scale(c, 1 / row.length);
    }
    for (var r = 0; r < bounds.length - 1; r++) {
      var i0 = bounds[r], i1 = bounds[r + 1];
      var pos = [], nrm = [], uv = [], idx = [];
      for (j = 0; j < k; j++) {
        var j2 = (j + 1) % k, base = pos.length / 3;
        for (i = i0; i <= i1; i++) {
          var a = P[i][j], b = P[i][j2];
          var prev = P[Math.max(0, i - 1)], next = P[Math.min(n - 1, i + 1)];
          var along = M.sub(M.lerp3(next[j], next[j2], 0.5), M.lerp3(prev[j], prev[j2], 0.5));
          var across = M.sub(b, a);
          var nn = M.cross(across, along);
          if (M.dot(nn, nn) < 1e-14) nn = [0, 1, 0];
          nn = M.norm(nn);
          // Point it out of the section: away from the station's centre.
          var mid = M.lerp3(a, b, 0.5);
          if (M.dot(nn, M.sub(mid, centre(P[i]))) < 0) nn = M.scale(nn, -1);
          pos.push(a[0], a[1], a[2], b[0], b[1], b[2]);
          nrm.push(nn[0], nn[1], nn[2], nn[0], nn[1], nn[2]);
          uv.push(i / (n - 1), j / k, i / (n - 1), (j + 1) / k);
        }
        for (i = 0; i < i1 - i0; i++) {
          var q = base + i * 2;
          idx.push(q, q + 1, q + 2, q + 2, q + 1, q + 3);
        }
      }
      var capAt = [];
      if (opts.caps && r === 0) capAt.push([i0, -1]);
      if (opts.caps && r === bounds.length - 2) capAt.push([i1, 1]);
      capAt.forEach(function (ce) {
        var row = P[ce[0]], c = centre(row), cb = pos.length / 3;
        var dir = M.sub(centre(P[Math.min(n - 1, Math.max(0, ce[0] + ce[1]))]), centre(P[Math.min(n - 1, Math.max(0, ce[0] - ce[1]))]));
        var cn = M.dot(dir, dir) > 1e-12 ? M.norm(dir) : [ce[1], 0, 0];
        pos.push(c[0], c[1], c[2]); nrm.push(cn[0], cn[1], cn[2]); uv.push(0.5, 0.5);
        row.forEach(function (p) { pos.push(p[0], p[1], p[2]); nrm.push(cn[0], cn[1], cn[2]); uv.push(0, 0); });
        for (var t = 0; t < k; t++) idx.push(cb, cb + 1 + t, cb + 1 + (t + 1) % k);
      });
      out.push(finish(pos, nrm, uv, idx));
    }
    return out;
  }

  /* A lathe laid along +x (the herb lathe stands on +y): rings for hafts, grips, sockets. */
  function latheX(profile, seg, crease) {
    return weld([[G.lathe(profile, seg || 14, crease === undefined ? 50 : crease), [0, 0, 0], [0, 0, -Math.PI / 2]]]);
  }

  /* --- props ------------------------------------------------------------------------------
     Positions in the scene are the adapter's; here every prop stands on its own origin. */

  /* The camp anvil: a stake anvil set into a stump, face at y 0.5. Small, because it is
     carried. */
  function campAnvil() {
    var g = group();
    add(g, node(G.cylinder(0.25, 0.36, 18, 0.23), mat("stump")));
    add(g, node(G.disc(0.23, 18), mat("wood", { color: [0.55, 0.4, 0.25], pattern: 3, patScale: 4 }), { pos: [0, 0.361, 0] }));
    var body = weld([
      [G.box(0.12, 0.08, 0.12), [0, 0.4, 0]],
      [G.box(0.34, 0.07, 0.15), [0, 0.465, 0]],
      [G.lathe([[0, 0], [0.055, 0], [0.0, 0.17]], 12, 60), [0.17, 0.465, 0], [0, 0, -Math.PI / 2], [1, 1, 0.75]]
    ]);
    add(g, node(body, mat("anvil")));
    add(g, node(G.box(0.3, 0.006, 0.14), mat("face"), { pos: [-0.01, 0.502, 0] }));
    add(g, shadow(0.42, 0.5));
    return { root: g, face: 0.505, faceLen: 0.34, kind: "camp" };
  }

  /* The smithy anvil: a London-pattern anvil on a squared block, face at y 0.68. */
  function smithyAnvil() {
    var g = group();
    add(g, node(G.box(0.42, 0.34, 0.38), mat("darkwood", { patScale: 0.8 }), { pos: [0, 0.17, 0] }));
    var body = weld([
      [G.box(0.5, 0.06, 0.26), [0, 0.37, 0]],
      [G.box(0.24, 0.12, 0.15), [0, 0.46, 0]],
      [G.box(0.56, 0.12, 0.17), [-0.02, 0.58, 0]],
      [G.box(0.12, 0.08, 0.14), [-0.34, 0.6, 0]],
      [G.lathe([[0, 0], [0.085, 0], [0.06, 0.12], [0.0, 0.32]], 16, 50), [0.26, 0.6, 0], [0, 0, -Math.PI / 2], [1, 1, 0.7]]
    ]);
    add(g, node(body, mat("anvil")));
    add(g, node(G.box(0.62, 0.008, 0.165), mat("face"), { pos: [-0.06, 0.644, 0] }));
    add(g, node(G.box(0.03, 0.009, 0.03), mat("soot"), { pos: [-0.33, 0.645, 0.03] }));   // the hardy hole
    add(g, shadow(0.55, 0.55));
    return { root: g, face: 0.648, faceLen: 0.56, kind: "smithy" };
  }

  /* Coals: a bed of lumps whose emission the stage sets from the hearth's heat. Returns the
     node and the material to warm. */
  function coalBed(r, n, seed) {
    var rnd = M.rng(seed || 3), lump = G.sphere(0.04, 7, 5), parts = [];
    for (var i = 0; i < n; i++) {
      var a = rnd() * TAU, d = Math.sqrt(rnd()) * r;
      var s = 0.6 + rnd() * 0.8;
      parts.push([lump, [Math.cos(a) * d, 0.015 + rnd() * 0.03 * (1 - d / r), Math.sin(a) * d],
                  [rnd() * 3, rnd() * 3, rnd() * 3], [s, s * 0.7, s]]);
    }
    var m = mat("coal");
    return { node: node(weld(parts), m, { glint: false }), mat: m };
  }

  /* Flame: a few small additive tongues of different heights rather than one cone. The first
     pass was a single cone 0.26 tall, and in the harness it read as a yellow paper triangle
     stood on the coals. set(k) follows the hearth's heat. */
  function tongues(parent, at, size) {
    var shape = G.lathe([[0, 0], [0.035, 0.02], [0.026, 0.07], [0.01, 0.12], [0, 0.14]], 9, 70);
    var outer = mat("flame", { alpha: 0.3 }), inner = mat("flame", { color: [1.0, 0.78, 0.4], alpha: 0.3 });
    var spots = [[0, 0, 0, 1.2], [0.07, 0, 0.03, 0.8], [-0.06, 0, -0.04, 0.95], [0.02, 0, -0.08, 0.7], [-0.04, 0, 0.07, 0.75]];
    var nodes = spots.map(function (s, i) {
      return add(parent, node(shape, i ? outer : inner, { pos: [at[0] + s[0] * size, at[1], at[2] + s[2] * size],
                                                         rot: [0, i * 1.3, 0], glint: false, base: s[3] * size }));
    });
    return {
      nodes: nodes,
      set: function (k) {
        outer.alpha = 0.06 + 0.3 * k; inner.alpha = 0.08 + 0.35 * k;
        nodes.forEach(function (n) { var h = n.base * (0.5 + 0.9 * k); n.scl = [n.base, h, n.base]; });
      }
    };
  }

  /* The field hearth: a ring of stones round a coal bed in a scorch, with the glow above it.
     setHeat(k) is 0 (banked) .. 1 (white under the bellows). */
  function fieldHearth() {
    var g = group(), rnd = M.rng(21), stone = G.sphere(0.07, 9, 6), parts = [];
    for (var i = 0; i < 11; i++) {
      var a = i / 11 * TAU + rnd() * 0.2, s = 0.8 + rnd() * 0.5;
      parts.push([stone, [Math.cos(a) * 0.3, 0.04 * s, Math.sin(a) * 0.3], [rnd() * 3, rnd() * 3, 0], [s, s * 0.75, s * 0.9]]);
    }
    add(g, node(G.disc(0.5, 32), mat("shadow", { alpha: 0.72, radial: 0.9 }), { pos: [0, 0.003, 0], glint: false }));
    add(g, node(weld(parts), mat("stone")));
    var coals = coalBed(0.24, 34, 7);
    add(g, coals.node);
    var glowM = mat("glow", { alpha: 0.4 });
    var glow = add(g, node(G.disc(0.45, 32), glowM, { pos: [0, 0.07, 0], glint: false }));
    var flame = tongues(g, [0, 0.03, 0], 1);
    function setHeat(k) {
      k = Math.max(0, Math.min(1.3, k));
      coals.mat.emit = [0.5 * k + 0.08, 0.13 * k + 0.012, 0.02 * k];
      glowM.alpha = 0.12 + 0.38 * k;
      flame.set(k);
    }
    setHeat(0.5);
    return { root: g, setHeat: setHeat, fire: [0, 0.12, 0], flame: flame, glow: glow, coals: coals.node };
  }

  /* The furnace mouth: a brick forge against the back wall, the fire seen through an arched
     mouth, a coal hearth on its ledge, and the hood rising into the dark. */
  function furnaceMouth() {
    var g = group();
    var brick = weld([
      [G.box(1.0, 0.7, 0.8), [0, 0.35, 0]],
      [G.box(0.32, 0.5, 0.8), [-0.34, 0.95, -0.06]],
      [G.box(0.32, 0.5, 0.8), [0.34, 0.95, -0.06]],
      [G.box(1.0, 0.16, 0.8), [0, 1.28, -0.06]]
    ]);
    add(g, node(brick, mat("brick")));
    // The hood: a straight square frustum (a four-step lathe turned square to the wall) and a
    // chimney. A curved three-point profile was tried first and read as a wine bottle. The
    // hood is left out of the camera's fit (`noFit`): it is tall, and fitting it framed the
    // whole room with the anvil a speck in the middle.
    add(g, node(weld([[G.lathe([[0.7, 0], [0.3, 0.55]], 4, 10), [0, 0, 0], [0, Math.PI / 4, 0], [1, 1, 0.8]],
                      [G.box(0.36, 1.2, 0.3), [0, 1.15, -0.04]]]),
                mat("brick", { color: [0.3, 0.16, 0.11] }), { pos: [0, 1.36, -0.12], noFit: true }));
    add(g, node(G.box(1.04, 0.05, 0.84), mat("stone", { color: [0.33, 0.31, 0.29] }), { pos: [0, 0.72, 0] }));
    // The mouth: a sooted recess lit from within by the fire, and the fire's heart in front of
    // it. The first harness capture had the heart disc INSIDE the recess box (hidden) and the
    // mouth read as a black hole; the recess now glows with the hearth's heat itself.
    var recessM = mat("soot", { emit: [0.2, 0.05, 0.01] });
    add(g, node(G.box(0.36, 0.5, 0.5), recessM, { pos: [0, 0.95, 0.1] }));
    var heartM = mat("glow", { radial: 0.9, alpha: 0.9 });
    var heart = add(g, node(G.disc(0.22, 28), heartM, { pos: [0, 0.9, 0.37], rot: [Math.PI / 2, 0, 0], glint: false }));
    var coals = coalBed(0.2, 30, 11);
    coals.node.pos = [0, 0.745, 0.12];
    coals.node.scl = [1.1, 1, 0.8];
    add(g, coals.node);
    var glowM = mat("glow", { alpha: 0.35 });
    add(g, node(G.disc(0.42, 28), glowM, { pos: [0, 0.8, 0.14], glint: false }));
    var flame = tongues(g, [0, 0.76, 0.1], 1.1);
    add(g, shadow(0.8, 0.5, { scl: [1.2, 1, 0.8] }));
    function setHeat(k) {
      k = Math.max(0, Math.min(1.3, k));
      coals.mat.emit = [0.55 * k + 0.1, 0.15 * k + 0.015, 0.025 * k];
      recessM.emit = [0.12 + 0.45 * k, 0.03 + 0.16 * k * k, 0.005 + 0.04 * k * k];
      heartM.color = [1.0, 0.36 + 0.4 * k, 0.1 + 0.25 * k * k];
      heartM.alpha = 0.35 + 0.6 * k;
      glowM.alpha = 0.12 + 0.36 * k;
      flame.set(k);
    }
    setHeat(0.5);
    return { root: g, setHeat: setHeat, fire: [0, 0.85, 0.15], flame: flame, heart: heart };
  }

  /* Bellows: two boards, a leather body between them and a nozzle toward the fire. setPump(p)
     is 0 (open) .. 1 (pressed). The nozzle points along -x from the bellows' origin. */
  function bellows(small) {
    var k = small ? 0.62 : 1, g = group();
    var board = G.lathe([[0, 0], [0.2, 0], [0.22, 0.012], [0.2, 0.024], [0, 0.024]], 18, 50);
    var top = add(g, node(board, mat("wood"), { scl: [1.3 * k, 1, k] }));
    var bot = add(g, node(board, mat("wood"), { scl: [1.3 * k, 1, k], pos: [0, 0.06 * k, 0] }));
    var body = add(g, node(G.sphere(0.2, 18, 10), mat("leather"), { scl: [1.25 * k, 0.4 * k, 0.95 * k] }));
    add(g, node(latheX([[0.04, 0], [0.03, 0.16], [0.016, 0.3]], 10), mat("iron"), { pos: [-0.25 * k, 0.1 * k, 0], scl: [k, k, k], rot: [0, Math.PI, 0] }));
    add(g, node(latheX([[0.02, 0], [0.02, 0.22]], 8), mat("wood"), { pos: [0.24 * k, 0.15 * k, 0], scl: [k, k, k] }));
    add(g, shadow(0.36 * k, 0.45, { scl: [1.3, 1, 1] }));
    function setPump(p) {
      p = Math.max(0, Math.min(1, +p || 0));
      var h = (0.24 - 0.14 * p) * k;
      bot.pos = [0, 0.015 * k, 0];
      top.pos = [0, h, 0];
      top.rot = [0, 0, 0.12 * (1 - p)];
      body.pos = [0.02 * k, h * 0.55, 0];
      body.scl = [1.25 * k, (0.46 - 0.3 * p) * k, 0.95 * k];
    }
    setPump(0);
    return { root: g, setPump: setPump, nozzle: [-0.55 * k, 0.1 * k, 0] };
  }

  /* The quench bucket (field kit): staves, two iron hoops and the water. */
  function quenchBucket() {
    var g = group();
    var prof = [[0.17, 0], [0.2, 0.32], [0.185, 0.32], [0.155, 0.02], [0, 0.02]];
    add(g, node(G.lathe(prof, 16, 30), mat("wood", { patScale: 3 })));
    add(g, node(G.ring(0.178, 0.008, 32, 5), mat("iron"), { pos: [0, 0.06, 0] }));
    add(g, node(G.ring(0.196, 0.008, 32, 5), mat("iron"), { pos: [0, 0.27, 0] }));
    var waterM = mat("water");
    add(g, node(G.disc(0.188, 28), waterM, { pos: [0, 0.27, 0] }));
    add(g, shadow(0.3, 0.5));
    return { root: g, surface: [0, 0.27, 0], water: waterM, r: 0.18 };
  }

  /* The quench trough (smithy): a long stone trough of water. */
  function quenchTrough() {
    var g = group();
    var stone = weld([
      [G.box(0.9, 0.08, 0.42), [0, 0.04, 0]],
      [G.box(0.9, 0.42, 0.06), [0, 0.21, 0.18]],
      [G.box(0.9, 0.42, 0.06), [0, 0.21, -0.18]],
      [G.box(0.06, 0.42, 0.42), [-0.42, 0.21, 0]],
      [G.box(0.06, 0.42, 0.42), [0.42, 0.21, 0]]
    ]);
    add(g, node(stone, mat("stone", { color: [0.38, 0.37, 0.35] })));
    var waterM = mat("water");
    add(g, node(G.box(0.78, 0.004, 0.3), waterM, { pos: [0, 0.37, 0] }));
    add(g, shadow(0.62, 0.5, { scl: [1.2, 1, 0.6] }));
    return { root: g, surface: [0, 0.37, 0], water: waterM, r: 0.36 };
  }

  /* The whetstone wheel on its frame (smithy), or a hand stone on a stump (field kit).
     spin(a) turns the wheel; `edge` is where the steel meets the stone, for sparks. */
  function whetWheel(kit) {
    var g = group();
    if (kit) {
      add(g, node(G.cylinder(0.14, 0.26, 14, 0.13), mat("stump")));
      add(g, node(G.box(0.2, 0.04, 0.06), mat("stone", { color: [0.5, 0.47, 0.42], patScale: 3 }), { pos: [0, 0.28, 0] }));
      add(g, shadow(0.24, 0.45));
      return { root: g, spin: function () {}, edge: [0, 0.3, 0] };
    }
    var frame = weld([
      [G.box(0.05, 0.62, 0.05), [0, 0.31, 0.12]], [G.box(0.05, 0.62, 0.05), [0, 0.31, -0.12]],
      [G.box(0.5, 0.05, 0.05), [0, 0.04, 0.12]], [G.box(0.5, 0.05, 0.05), [0, 0.04, -0.12]],
      [G.box(0.42, 0.2, 0.2), [0, 0.18, 0]]
    ]);
    add(g, node(frame, mat("wood")));
    add(g, node(G.box(0.38, 0.03, 0.18), mat("water"), { pos: [0, 0.28, 0] }));
    var wheel = add(g, node(null, null, { pos: [0, 0.6, 0] }));
    add(wheel, node(G.cylinder(0.24, 0.07, 28), mat("stone", { color: [0.6, 0.56, 0.48], patScale: 2.5 }),
                    { rot: [Math.PI / 2, 0, 0], pos: [0, 0, 0.035] }));
    add(wheel, node(G.cylinder(0.02, 0.32, 8), mat("iron"), { rot: [Math.PI / 2, 0, 0], pos: [0, 0, 0.16] }));
    add(g, node(latheX([[0.015, 0], [0.015, 0.14]], 6), mat("wood"), { pos: [0, 0.6, -0.17], rot: [0, Math.PI / 2, 0] }));
    add(g, shadow(0.36, 0.45));
    return { root: g, spin: function (a) { wheel.rot = [0, 0, a]; }, edge: [-0.2, 0.75, 0] };
  }

  /* The crucible (molten metal shows heat by the same table as the work) and its tongs. */
  function crucible() {
    var g = group();
    add(g, node(G.lathe([[0, 0], [0.08, 0], [0.11, 0.12], [0.1, 0.2], [0.085, 0.2], [0.09, 0.12], [0.065, 0.02], [0, 0.02]], 18, 40),
                mat("clay", { color: [0.44, 0.38, 0.33] })));
    var meltM = mat("coal", { color: [0.2, 0.2, 0.2], spec: 1.4, shin: 80, pattern: 0 });
    var melt = add(g, node(G.disc(0.088, 20), meltM, { pos: [0, 0.16, 0] }));
    add(g, shadow(0.18, 0.5));
    return { root: g, melt: meltM, meltNode: melt, lip: [0.1, 0.2, 0] };
  }
  function tongs() {
    var arm = G.box(0.42, 0.012, 0.016);
    var g = group();
    add(g, node(arm, mat("iron"), { pos: [0, 0.008, 0.012], rot: [0, 0.05, 0] }));
    add(g, node(arm, mat("iron"), { pos: [0, 0.008, -0.012], rot: [0, -0.05, 0] }));
    add(g, node(G.cylinder(0.012, 0.03, 8), mat("iron"), { pos: [0.09, 0, 0] }));
    return g;
  }

  /* --- the hand tools ------------------------------------------------------------------- */
  function hammer(heavy) {
    var g = group(), k = heavy ? 1.2 : 1;
    add(g, node(latheX([[0.016, 0], [0.019, 0.22], [0.017, 0.34]], 8), mat("wood"), { pos: [-0.34 * k, 0, 0], scl: [k, k, k] }));
    add(g, node(weld([[G.box(0.045, 0.045, 0.13), [0, 0, 0]], [G.cylinder(0.026, 0.02, 12), [0, 0, 0.065], [Math.PI / 2, 0, 0]]]),
                mat("iron"), { scl: [k, k, k] }));
    return g;
  }
  function file() {
    var g = group();
    add(g, node(G.box(0.26, 0.008, 0.026), mat("steel", { spec: 0.6, pattern: 5 })));
    add(g, node(latheX([[0.014, 0], [0.016, 0.06], [0.012, 0.1]], 8), mat("wood"), { pos: [-0.23, 0, 0] }));
    return g;
  }
  function brush() {
    var g = group();
    add(g, node(G.box(0.16, 0.024, 0.05), mat("wood")));
    add(g, node(G.box(0.14, 0.03, 0.044), mat("cloth", { color: [0.24, 0.2, 0.16] }), { pos: [0, -0.025, 0] }));
    return g;
  }
  function rivetSet() {
    var g = group();
    add(g, node(latheX([[0.012, 0], [0.012, 0.12], [0.02, 0.14], [0, 0.15]], 8), mat("iron"), { rot: [0, 0, Math.PI / 2] }));
    return g;
  }
  function touchstone() {
    var g = group();
    add(g, node(G.box(0.14, 0.02, 0.07), mat("soot", { spec: 0.6, shin: 40, pattern: 0 })));
    return g;
  }

  /* Which tool the smith reaches for, by method (UI plan §10: "tools swap on the rack"). */
  var HAND = {
    smelt: "tongs", alloy: "tongs", forge: "hammer", quench: "tongs", temper: "tongs",
    fold: "hammer", hone: "file", assemble: "rivet", finish: "brush", strengthen: "sledge",
    assay: "touchstone"
  };
  var HAND_BUILD = {
    hammer: function () { return hammer(false); }, sledge: function () { return hammer(true); },
    tongs: tongs, file: file, brush: brush, rivet: rivetSet, touchstone: touchstone
  };

  /* The tool rack: a board on two posts with what is not in hand hanging from it. */
  function toolRack(kit) {
    var g = group();
    if (kit) {
      // At the field kit the "rack" is a leather roll laid open on the ground.
      add(g, node(G.box(0.5, 0.01, 0.22), mat("leather", { color: [0.3, 0.19, 0.1] }), { pos: [0, 0.005, 0] }));
      add(g, node(G.cylinder(0.04, 0.24, 10), mat("leather"), { rot: [Math.PI / 2, 0, 0], pos: [0.27, 0.04, 0.12] }));
      return { root: g, hooks: [[-0.16, 0.03, 0], [-0.05, 0.03, 0], [0.06, 0.03, 0], [0.16, 0.03, 0]], lying: true };
    }
    add(g, node(weld([[G.box(0.05, 1.1, 0.05), [-0.42, 0.55, 0]], [G.box(0.05, 1.1, 0.05), [0.42, 0.55, 0]],
                      [G.box(0.92, 0.14, 0.04), [0, 0.98, 0.02]], [G.box(0.92, 0.04, 0.12), [0, 0.12, 0.04]]]),
                mat("darkwood")));
    var hooks = [[-0.3, 0.9, 0.06], [-0.1, 0.9, 0.06], [0.1, 0.9, 0.06], [0.3, 0.9, 0.06]];
    hooks.forEach(function (h) { add(g, node(G.cylinder(0.008, 0.05, 6), mat("iron"), { pos: h, rot: [Math.PI / 2, 0, 0] })); });
    add(g, shadow(0.5, 0.4, { scl: [1, 1, 0.4] }));
    return { root: g, hooks: hooks, lying: false };
  }

  /* A stack of bar stock by the anvil, so the floor reads as a working smithy. */
  function barStock() {
    var bar = G.box(0.44, 0.03, 0.03), parts = [];
    for (var i = 0; i < 5; i++) parts.push([bar, [(i % 2) * 0.02, 0.015 + Math.floor(i / 3) * 0.03, (i % 3) * 0.04], [0, 0.04 * (i - 2), 0]]);
    var g = group();
    add(g, node(weld(parts), mat("iron")));
    return g;
  }

  /* A hanging lamp (the smithy's fill): an iron cage round a flame, on a chain. */
  function lamp() {
    var g = group();
    add(g, node(G.cylinder(0.006, 0.6, 6), mat("iron"), { pos: [0, 0.18, 0] }));
    add(g, node(G.lathe([[0.07, 0], [0.09, 0.04], [0.09, 0.14], [0.05, 0.18], [0, 0.2]], 8, 50), mat("iron", { alpha: 0.55, pass: "alpha" })));
    var flameM = mat("flame", { color: [1.0, 0.72, 0.36], alpha: 0.9 });
    add(g, node(G.sphere(0.03, 10, 6), flameM, { pos: [0, 0.08, 0], scl: [1, 1.6, 1], glint: false }));
    add(g, node(G.disc(0.22, 20), mat("glow", { color: [1.0, 0.7, 0.36], alpha: 0.28 }), { pos: [0, 0.08, 0], rot: [Math.PI / 2, 0, 0], glint: false }));
    return g;
  }

  F.geo = { finish: finish, weld: weld, sweep: sweep, latheX: latheX };
  F.props = {
    mat: mat, node: node, add: add, group: group, shadow: shadow, BASE: BASE,
    campAnvil: campAnvil, smithyAnvil: smithyAnvil, fieldHearth: fieldHearth, furnaceMouth: furnaceMouth,
    bellows: bellows, quenchBucket: quenchBucket, quenchTrough: quenchTrough, whetWheel: whetWheel,
    crucible: crucible, tongs: tongs, toolRack: toolRack, barStock: barStock, lamp: lamp,
    HAND: HAND, HAND_BUILD: HAND_BUILD
  };
})();
