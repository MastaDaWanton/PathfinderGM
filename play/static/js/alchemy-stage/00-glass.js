/* The alchemy bench's stage, part 0: the glassware, and the liquid inside it.
 *
 * UI plan §7.1-7.3: every vessel is a LATHE PROFILE, built in code from the herb kit's
 * primitives (bench-stage/02-meshes.js, as it is), the same bargain the herb tools and the
 * forge's families made: no models, no downloads. A profile is written outside-up, over the
 * lip and inside-down, which is the order that makes every normal point out of the
 * material (02-meshes.js); the inside is the outside OFFSET INWARD by the wall, so a vial's
 * glass has a thickness the fresnel rim can show (01-gl.js already brightens a grazing
 * edge, so a vial's edge reads brighter than its face; there is no refraction, by plan).
 *
 * THE LIQUID is the vessel's own inner profile, closed at the axis top and bottom, a hair
 * inside the glass. It carries `liquid: {lo, hi}`, the inner bottom and the shoulder in the
 * vessel's own height: the stage turns a level 0..1 into a world fill height between the
 * two each frame, and the shader (01-gl.js `uFillY`) discards everything above it and
 * paints the back faces seen through the cut as the liquid's top. One number a frame moves
 * the level; no cap mesh has to follow it.
 *
 * Vessel kinds are the alchemist's real glassware (UI plan §6.3, art §5): the vial, the
 * round-bottom flask, the cucurbit and its alembic head, the receiver, the retort, the
 * aludel, the crucible, the mortar, the bain-marie pot; and the shelf's own vessels for
 * Bottle (content/materials/alchemist-materials.json, kind "vessel"): clay and iron flasks,
 * the waxed bladder, the stoneware pot, the brass casing, the phial, the egg shell and the
 * wooden rod. Which material id is which shape is VESSEL_OF below; an unknown id takes the
 * shape its words suggest, and anything else is a vial, which is never a lie about a bottle.
 *
 * Every mesh is built once a session and cached (`once`): the renderer keeps a GPU buffer
 * per mesh id until the stage closes, so a vessel rebuilt per call would grow that map for
 * as long as the bench stays open (the enchanting stage's phial measurement).
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var F = window.ForgeStageKit || {};
  var A = window.AlchemyStageKit = window.AlchemyStageKit || {};
  var G = K.mesh, M = K.math, FP = F.props;
  if (!G || !M || !FP) return;   // the herb kit or the forge's helpers did not load: go flat
  var TAU = Math.PI * 2;
  var node = FP.node, add = FP.add, group = FP.group;

  /* --- materials -------------------------------------------------------------------------
     The forge's palette (forge-stage/01-props.js) plus the glass and the liquid. Glass starts
     from the herb kit's (bench-stage/05-props.js: alpha .1, fresnel .55, spec 1.4, shin 90,
     the alpha pass at order 3). The liquid draws at order 1, before the glass round it. */
  var OWN = {
    glass: { color: [0.8, 0.88, 0.86], alpha: 0.1, fresnel: 0.55, spec: 1.4, shin: 90, pass: "alpha", order: 3 },
    leadglass: { color: [0.62, 0.66, 0.62], alpha: 0.2, fresnel: 0.5, spec: 1.3, shin: 80, pass: "alpha", order: 3 },
    // A softer, broader highlight than glass: at spec 1.1 / shin 60 the athanor's key, a few
    // centimetres off, burned a hard-edged hot spot into the flat top of the liquid.
    liquid: { color: [0.5, 0.4, 0.2], alpha: 0.6, spec: 0.6, shin: 30, pass: "alpha", order: 1,
              fillY: 1e4, surf: [0.6, 0.5, 0.3], turbid: 0 },
    glaze: { color: [0.36, 0.3, 0.24], spec: 0.8, shin: 40, pattern: 3 },
    stoneware: { color: [0.5, 0.46, 0.41], spec: 0.5, shin: 30, pattern: 3, patScale: 2 },
    clay: { color: [0.55, 0.36, 0.24], spec: 0.2, shin: 10, pattern: 3 },
    crucible: { color: [0.44, 0.38, 0.33], spec: 0.2, shin: 10, pattern: 3 },
    bladder: { color: [0.62, 0.5, 0.32], spec: 0.7, shin: 30, pattern: 6, patScale: 2 },
    shell: { color: [0.92, 0.9, 0.82], spec: 0.6, shin: 40, pattern: 3, patScale: 6 },
    cork: { color: [0.62, 0.47, 0.3], spec: 0.1, shin: 8, pattern: 3, patScale: 3 },
    wax: { color: [0.62, 0.16, 0.12], spec: 0.6, shin: 30 },
    crust: { color: [0.92, 0.92, 0.88], alpha: 0, spec: 1.2, shin: 70, pass: "alpha", order: 2, pattern: 3, patScale: 30 },
    crack: { color: [0.05, 0.04, 0.04], alpha: 0.85, unlit: 1, pass: "alpha", order: 4 }
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

  /* --- profiles ------------------------------------------------------------------------- */

  /* The outward normal at each point of an outside-up profile, averaged from its two
     segments, as the lathe turns it (02-meshes.js: the profile's tangent turned a quarter). */
  function normals(p) {
    var segs = [];
    for (var i = 0; i < p.length - 1; i++) {
      var dr = p[i + 1][0] - p[i][0], dy = p[i + 1][1] - p[i][1], l = Math.sqrt(dr * dr + dy * dy) || 1;
      segs.push([dy / l, -dr / l]);
    }
    return p.map(function (_, i) {
      var a = segs[i - 1], b = segs[i];
      if (!a) return b; if (!b) return a;
      var x = a[0] + b[0], y = a[1] + b[1], l = Math.sqrt(x * x + y * y) || 1;
      return [x / l, y / l];
    });
  }
  /* The profile moved inward by d: what the inside of a wall d thick looks like. A point on
     the axis stays on it (it only rises), so the inside closes where the outside does. */
  function inset(p, d) {
    var n = normals(p);
    return p.map(function (q, i) {
      if (q[0] <= 1e-6) return [0, q[1] + d];
      return [Math.max(0, q[0] - n[i][0] * d), q[1] - n[i][1] * d];
    });
  }
  /* A wall: the outside up, over the lip, the inside down. */
  function wall(outer, d) {
    var inner = inset(outer, d).slice().reverse();
    return outer.concat(inner);
  }
  /* The liquid: the inside, a hair further in, closed at the axis at the top. */
  function liquidProfile(outer, d) {
    var p = inset(outer, d + 0.0016);
    var top = p[p.length - 1][1];
    return p.concat([[0, top]]);
  }

  /* A round-bottom flask's outside: a sphere of radius R sitting on y = 0 up to where it
     meets the neck, the neck to its top, and a flared lip. */
  function bulb(R, neckR, neckTop, lip) {
    var pts = [], aTop = Math.acos(Math.min(0.99, neckR / R)), N = 12;
    for (var i = 0; i <= N; i++) {
      var a = -Math.PI / 2 + (Math.PI / 2 + aTop) * i / N;
      pts.push([Math.max(0, R * Math.cos(a)), R + R * Math.sin(a)]);
    }
    pts[0] = [0, 0];
    pts.push([neckR, neckTop]);
    pts.push([neckR * 1.3, neckTop + (lip || 0.008)]);
    return pts;
  }

  /* --- the registry ----------------------------------------------------------------------
     outer: the outside profile; d: the wall; mat: what it is made of; fill: [lo, hi] of the
     liquid in the vessel's height (lo the inner bottom, hi the shoulder: a level of 1 fills to
     the shoulder, never up the neck); mouth: the top of the opening, where a pour lands and a
     stopper sits; open: a single sheet (an alembic head) rather than a wall. */
  var KINDS = {
    vial: { outer: [[0, 0.003], [0.012, 0], [0.019, 0.005], [0.021, 0.018], [0.021, 0.1], [0.017, 0.11],
                    [0.0155, 0.118], [0.0185, 0.124]], d: 0.0022, mat: "glass", fill: [0.006, 0.1], mouth: 0.124, stopper: 0.0155 },
    flask: { outer: bulb(0.085, 0.019, 0.25, 0.01), d: 0.003, mat: "glass", fill: [0.006, 0.13], mouth: 0.26, stopper: 0.019 },
    receiver: { outer: bulb(0.06, 0.016, 0.17, 0.008), d: 0.0026, mat: "glass", fill: [0.005, 0.095], mouth: 0.178, stopper: 0.016 },
    cucurbit: { outer: [[0, 0], [0.08, 0], [0.1, 0.03], [0.106, 0.09], [0.092, 0.16], [0.062, 0.21], [0.05, 0.24],
                        [0.056, 0.25]], d: 0.003, mat: "glass", fill: [0.006, 0.17], mouth: 0.25 },
    head: { outer: [[0.054, 0], [0.074, 0.03], [0.07, 0.08], [0.042, 0.112], [0, 0.124]], d: 0, mat: "glass", open: true },
    aludel: { outer: [[0, 0], [0.03, 0.004], [0.07, 0.04], [0.085, 0.1], [0.078, 0.16], [0.05, 0.22], [0.022, 0.26],
                      [0.02, 0.3], [0.026, 0.306]], d: 0.003, mat: "glass", fill: [0.006, 0.15], mouth: 0.306, stopper: 0.02,
              crust: [0.17, 0.235] },
    retort: { outer: bulb(0.07, 0.02, 0.14, 0.004), d: 0.003, mat: "glass", fill: [0.006, 0.09], mouth: 0.144 },
    crucible: { outer: [[0, 0], [0.07, 0], [0.095, 0.11], [0.088, 0.17], [0.096, 0.176]], d: 0.012, mat: "crucible",
                fill: [0.014, 0.13], mouth: 0.176 },
    mortar: { outer: [[0, 0], [0.08, 0], [0.1, 0.04], [0.106, 0.08], [0.098, 0.086]], d: 0.018, mat: "stone",
              fill: [0.02, 0.06], mouth: 0.086 },
    bainmarie: { outer: [[0, 0], [0.13, 0], [0.135, 0.12], [0.145, 0.13]], d: 0.006, mat: "iron", fill: [0.008, 0.1], mouth: 0.13 },
    pot: { outer: [[0, 0], [0.07, 0], [0.086, 0.05], [0.08, 0.11], [0.06, 0.14], [0.05, 0.16], [0.056, 0.17]], d: 0.008,
           mat: "stoneware", fill: [0.01, 0.12], mouth: 0.17, stopper: 0.05 },
    clayflask: { outer: [[0, 0], [0.05, 0], [0.066, 0.04], [0.061, 0.1], [0.026, 0.13], [0.018, 0.17], [0.022, 0.176]],
                 d: 0.006, mat: "clay", fill: [0.008, 0.11], mouth: 0.176, stopper: 0.018 },
    ironflask: { outer: [[0, 0], [0.05, 0], [0.064, 0.03], [0.064, 0.11], [0.026, 0.135], [0.016, 0.17], [0.02, 0.175]],
                 d: 0.004, mat: "iron", fill: [0.006, 0.11], mouth: 0.175, stopper: 0.016 },
    bladder: { outer: [[0, 0], [0.04, 0.005], [0.07, 0.05], [0.062, 0.1], [0.022, 0.13], [0.014, 0.16], [0.02, 0.166]],
               d: 0.004, mat: "bladder", fill: [0.008, 0.1], mouth: 0.166, stopper: 0.014 },
    casing: { outer: [[0, 0], [0.025, 0], [0.028, 0.004], [0.028, 0.13], [0.023, 0.136]], d: 0.003, mat: "brass",
              fill: [0.006, 0.12], mouth: 0.136, stopper: 0.026 },
    phial: { outer: [[0, 0], [0.02, 0], [0.026, 0.01], [0.026, 0.06], [0.012, 0.08], [0.009, 0.1], [0.012, 0.104]],
             d: 0.002, mat: "glass", fill: [0.004, 0.065], mouth: 0.104, stopper: 0.009 },
    egg: { outer: [[0, 0], [0.03, 0.006], [0.05, 0.035], [0.056, 0.075], [0.048, 0.115], [0.03, 0.14], [0.018, 0.148]],
           d: 0.003, mat: "shell", fill: [0.006, 0.1], mouth: 0.148, stopper: 0.018 },
    rod: { rod: true, mouth: 0.3 }
  };

  /* The shelf's vessels (alchemist-materials.json, kind "vessel") to a shape and a glass. */
  var VESSEL_OF = {
    "glass-vial": ["vial"], "lead-glass-vial": ["vial", "leadglass"], "clay-flask": ["clayflask"],
    "iron-flask": ["ironflask"], "waxed-bladder": ["bladder"], "stoneware-pot": ["pot"],
    "brass-casing": ["casing"], "crystal-retort": ["retort"], "salamander-glass-flask": ["flask", "glass", [0.85, 0.5, 0.3]],
    "warded-phial": ["phial"], "genie-breath-phial": ["phial", "glass", [0.85, 0.7, 0.35]],
    "adamantine-crucible": ["crucible", "iron"], "world-egg-shell": ["egg"], "wooden-rod": ["rod"]
  };
  /* A kind for anything: a shape's own name, a known vessel id, or the shape its words say. */
  function kindOf(id) {
    var s = String(id || "").toLowerCase();
    if (KINDS[s]) return [s];
    if (VESSEL_OF[s]) return VESSEL_OF[s];
    var words = [["crucible", "crucible"], ["mortar", "mortar"], ["retort", "retort"], ["aludel", "aludel"],
                 ["cucurbit", "cucurbit"], ["receiver", "receiver"], ["bladder", "bladder"], ["casing", "casing"],
                 ["phial", "phial"], ["pot", "pot"], ["egg", "egg"], ["rod", "rod"], ["flask", "flask"], ["vial", "vial"]];
    for (var i = 0; i < words.length; i++) if (s.indexOf(words[i][0]) >= 0) return [words[i][1]];
    return null;
  }

  /* --- building a vessel ------------------------------------------------------------------
     Returns {root, kind, def, liquid (node or null), body (the wall's node), stopper (node,
     hidden), crust (node or null), mouth, radiusAt(y)}. `glass` overrides the wall's
     material (lead glass, an adamantine crucible); `tint` colours a glass. */
  function vessel(kind, glassName, tint) {
    var def = KINDS[kind] || KINDS.vial;
    kind = KINDS[kind] ? kind : "vial";
    var g = group(), out = { root: g, kind: kind, def: def, liquid: null, crust: null, stopper: null, mouth: def.mouth };
    if (def.rod) {
      // A sunrod's kind: a wooden rod, banded at its head. It holds no liquid.
      out.body = add(g, node(once("rod", function () { return G.cylinder(0.011, 0.28, 10); }), FP.mat("wood"), {}));
      add(g, node(once("rod-band", function () { return G.cylinder(0.013, 0.03, 10); }), FP.mat("brass"), { pos: [0, 0.24, 0] }));
      add(g, shadowNode(0.04));
      out.radiusAt = function () { return 0.011; };
      return out;
    }
    var seg = def.outer[def.outer.length - 1][0] > 0.04 || kind === "flask" ? 30 : 20;
    var wm = mat(glassName || def.mat);
    if (tint) wm.color = tint.slice();
    var mesh = once("v:" + kind, function () { return G.lathe(def.open ? def.outer : wall(def.outer, def.d), seg, 35); });
    out.body = add(g, node(mesh, wm));
    out.radiusAt = function (y) { return G.radiusAt(def.outer, y, false); };
    if (def.fill) {
      var lp = once("l:" + kind, function () { return G.lathe(liquidProfile(def.outer, def.d), seg, 35); });
      out.liquid = add(g, node(lp, mat("liquid"), { glint: true }));
      out.liquid.liquid = { lo: def.fill[0], hi: def.fill[1], level: 0 };
    }
    if (def.crust) {
      // The sublimate grows on the cool upper wall (UI plan §9, Sublime): a band of the inside,
      // a hair in from the glass, that thickens as the crust grows.
      var cr = def.crust, inner = inset(def.outer, def.d + 0.001).filter(function (q) { return q[1] >= cr[0] && q[1] <= cr[1]; });
      if (inner.length >= 2) {
        out.crust = add(g, node(once("c:" + kind, function () { return G.lathe(inner, seg, 60); }), mat("crust"), { visible: false, glint: false }));
      }
    }
    if (def.stopper) {
      var sr = def.stopper;
      out.stopper = add(g, node(once("s:" + kind, function () { return G.cylinder(sr * 0.92, 0.024, 10, sr * 1.1); }),
                                mat(kind === "pot" || kind === "egg" ? "wax" : "cork"), { pos: [0, def.mouth - 0.012, 0], visible: false }));
    }
    var rr = Math.max.apply(null, def.outer.map(function (q) { return q[0]; }));
    if (!def.open) add(g, shadowNode(rr * 1.5));
    return out;
  }

  function shadowNode(r) {
    return node(once("sh" + r.toFixed(3), function () { return G.disc(r, 24); }), FP.mat("shadow", { alpha: 0.5 }),
                { pos: [0, 0.004, 0], glint: false });
  }

  /* A crack on the glass (UI plan §7.5): a short zigzag of thin dark strokes laid on the
     vessel's front, toward the camera. It is a state, so it stays under reduced motion and
     until another vessel is set. */
  function crack() {
    return once("crack", function () {
      var r = M.rng(77), parts = [], x = 0, y = 0;
      for (var i = 0; i < 7; i++) {
        var a = -Math.PI / 2 + (r() - 0.5) * 1.6, l = 0.012 + r() * 0.012;
        var nx = x + Math.cos(a) * l * 0.6, ny = y + Math.sin(a) * l;
        var mx = (x + nx) / 2, my = (y + ny) / 2, ang = Math.atan2(ny - y, nx - x);
        parts.push({ mesh: G.box(Math.sqrt((nx - x) * (nx - x) + (ny - y) * (ny - y)), 0.0016, 0.0016),
                     m: M.compose([mx, my, 0], [0, 0, ang], [1, 1, 1]) });
        if (i === 3) {
          parts.push({ mesh: G.box(0.014, 0.0012, 0.0012), m: M.compose([nx + 0.006, ny + 0.002, 0], [0, 0, 0.5], [1, 1, 1]) });
        }
        x = nx; y = ny;
      }
      return G.merge(parts);
    });
  }

  A.glass = { mat: mat, once: once, KINDS: KINDS, VESSEL_OF: VESSEL_OF, kindOf: kindOf, vessel: vessel, crack: crack,
              inset: inset, wall: wall, liquidProfile: liquidProfile, bulb: bulb, shadow: shadowNode, TAU: TAU };
})();
