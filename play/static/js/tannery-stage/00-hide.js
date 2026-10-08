/* The tannery's stage, part 0: the hide.
 *
 * UI plan §7.2. A hide is the centre of this bench the way the blank is the forge's, so it is
 * built here with more care than any prop:
 *
 *   OUTLINE BY BODY PLAN, NOT PER CREATURE. Five plans, the ones the harvest tag names
 *   (contracts §5.1, `harvest.plan.<plan>`): quadruped (legs out at the four corners, the
 *   neck and a strip of tail), long (crocodile, worm: long, narrow, small legs, a long tail),
 *   serpent (a long tapering ribbon), winged (a narrow body between two broad, scalloped
 *   wings) and carapace (an oval shell that keeps its dome). An untagged hide is a quadruped.
 *   Each plan is a half-width profile along the hide's length, so a row of the grid is always
 *   a row across the hide; the edge is roughened by a seeded noise per side (the material id
 *   is the seed), so the same wolf pelt has the same ragged edge on every open.
 *
 *   SIZE from the server's hide units (a Medium hide is 1 unit): the area goes with the
 *   units, so each side with their square root, capped at what the stage can frame. A Large
 *   pelt fills the stretching frame; a Small one sits in its middle.
 *
 *   ROW-MAJOR. The grid is built a row along the length at a time, so any run of rows is one
 *   contiguous run of indices, and the renderer can draw just that stretch of hide
 *   (01-gl.js's `range`). That is how flensing clears the flesh side "side by side as strokes
 *   land": the fat layer is drawn only over the rows not yet cleared, with no mesh rebuilt.
 *
 *   DRAPES. The same outline is laid onto what holds it: a slab (the ground, the kit's board,
 *   the currier's table, hanging over its edges and pooling on the ground past them), the
 *   fleshing beam (wrapped over the log and hanging down both sides), the stretching frame
 *   (upright, leaning back, bellying a little between its lacing), or a vat or pot (folded
 *   and crumpled into the liquor). Each drape works in the set's own frame, with y up, so a
 *   hide that would hang through the ground lies on it instead.
 *
 *   TWO SIDES. A hide is two sheets a few millimetres apart: the side being worked (the flesh
 *   side of a raw hide, the grain of a tanned one) on the outside of the drape, and the other
 *   side (the hair, or the suede) under it. The house shader lights both faces of a sheet, so
 *   depth alone decides which side the eye meets.
 *
 *   DEFECTS STAY. The holes and scores the harvest left are dark scars welded into one mesh
 *   on both sheets, placed on the draped surface, and drawn through every later step, so a
 *   Grade 3 hide looks like one (UI plan §7.2). A number (the harvest game's defect area,
 *   contracts §11.1) gives that many scars at seeded places; a list gives them where it says.
 *
 * Every mesh comes from the herb kit's counter (bench-stage/02-meshes.js) through the forge's
 * `finish`, and is cached by everything it was built from, so reopening, re-draping and
 * switching methods build nothing twice.
 *
 * WHAT THIS FILE DOES NOT KNOW. Any property of a material. The stage is sent a colour and a
 * surface word per piece, and that is all it ever reads (the hidden-secret rule: an ungraded
 * hide's properties never reach the page, so the stage could not draw one if it tried).
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var F = window.ForgeStageKit || {};
  var T = window.TanneryStageKit = window.TanneryStageKit || {};
  var G = K.mesh, M = K.math, GEO = F.geo, FP = F.props;
  if (!G || !M || !GEO || !FP) return;   // the herb kit or the forge's helpers did not load: go flat

  var NU = 40, NV = 16;                   // rows along the length, columns across
  var EPS = 0.0016;                       // half the hide's thickness, metres

  /* --- the body plans ------------------------------------------------------------------- */

  function g(u, c, w) { var d = (u - c) / w; return Math.exp(-d * d); }
  // Anything not a number is 0: a look the game never sent (undefined) must not become NaN in
  // a colour, which the shader draws black (seen in the first live capture of Flense).
  function sat(x) { x = +x; return !isFinite(x) || x < 0 ? 0 : (x > 1 ? 1 : x); }

  // len and wid are metres at one hide unit (a Medium hide). shape(u) is the half-width as a
  // fraction of wid/2, u from the tail (0) to the head (1); legs(u) is how much of that is a
  // leg flap, for the sweep of the legs forward and back.
  var PLANS = {
    quadruped: {
      len: 1.15, wid: 0.86,
      shape: function (u) {
        var b = Math.pow(Math.sin(Math.PI * sat((u - 0.05) / 0.86)), 0.45) * 0.6;
        var w = b + this.legs(u) + 0.24 * g(u, 0.95, 0.035);
        return u < 0.06 ? Math.max(w, 0.08) : w;
      },
      legs: function (u) { return 0.42 * g(u, 0.2, 0.045) + 0.38 * g(u, 0.73, 0.04); },
      sweep: function (u) { return u < 0.45 ? -1 : 1; }
    },
    long: {
      len: 1.6, wid: 0.56,
      shape: function (u) {
        var b = 0.62 * Math.pow(Math.sin(Math.PI * sat(u)), 0.55);
        if (u < 0.45) b *= Math.pow(u / 0.45, 0.85) * 0.8 + 0.2;
        return b + this.legs(u);
      },
      legs: function (u) { return 0.22 * g(u, 0.42, 0.035) + 0.2 * g(u, 0.7, 0.035); },
      sweep: function (u) { return u < 0.55 ? -1 : 1; }
    },
    serpent: {
      len: 2.3, wid: 0.3,
      shape: function (u) { return 0.52 * Math.pow(Math.min(1, u / 0.3), 0.7) * Math.pow(Math.min(1, (1 - u) / 0.1), 0.5); },
      legs: function () { return 0; },
      sweep: function () { return 0; }
    },
    winged: {
      len: 0.95, wid: 1.45,
      shape: function (u) {
        var body = 0.24 * Math.pow(Math.sin(Math.PI * sat(u)), 0.5);
        var wing = this.legs(u);
        return body + wing * (1 - 0.14 * Math.abs(Math.sin(u * 34)));
      },
      legs: function (u) { return 0.74 * g(u, 0.6, 0.15); },
      sweep: function () { return -0.4; }
    },
    carapace: {
      len: 0.9, wid: 0.72, dome: 0.09,
      shape: function (u) { return 0.5 * Math.pow(Math.max(0, Math.sin(Math.PI * u)), 0.5); },
      legs: function () { return 0; },
      sweep: function () { return 0; }
    }
  };
  function planOf(p) {
    p = String(p || "").toLowerCase().replace(/^harvest\.plan\./, "");
    return PLANS[p] ? p : "quadruped";
  }

  /* A smooth noise along the length, per side, from a seed: the ragged edge. */
  function seedOf(s) {
    s = String(s || "hide");
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }
  function edgeNoise(seed) {
    var r = M.rng(seed), knots = [];
    for (var i = 0; i <= 12; i++) knots.push([r() - 0.5, r() - 0.5]);
    return function (u, side) {
      var x = sat(u) * 12, i0 = Math.min(11, Math.floor(x)), f = x - i0, e = f * f * (3 - 2 * f);
      var k = side > 0 ? 0 : 1;
      return knots[i0][k] + (knots[i0 + 1][k] - knots[i0][k]) * e;
    };
  }

  /* The flat outline at a size: {plan, L, W, at(u, v) -> [x, z]}. */
  function outline(planName, units, seed) {
    var P = PLANS[planOf(planName)];
    var k = Math.sqrt(Math.max(0.2, +units || 1));
    var L = P.len * k, W = P.wid * k;
    var cap = Math.min(1, 1.9 / L, 1.5 / W);   // what the stage can frame
    L *= cap; W *= cap;
    var noise = edgeNoise(seed);
    return {
      plan: planOf(planName), L: L, W: W, dome: (P.dome || 0) * k * cap,
      at: function (u, v) {
        var side = v >= 0 ? 1 : -1;
        var w = Math.max(0, P.shape(u)) * (1 + 0.09 * noise(u, side)) * (W / 2);
        var x = (u - 0.5) * L;
        // Leg flaps sweep toward their own end of the hide, as a skinned leg lies.
        var lw = P.legs(u);
        if (lw > 0.02) x += P.sweep(u) * 0.09 * L * lw * v * v;
        return [x, v * w];
      }
    };
  }

  /* --- drapes --------------------------------------------------------------------------- */
  // Each takes the flat (x, z) and gives a point in the set's frame, y up.

  /* A slab: everything inside [hx, hz] lies on top at height h; past an edge the hide turns
     down over it, and anything that would go under the ground lies on the ground instead,
     spreading outward. A slab of height 0 and a huge size is simply the ground. */
  function slab(o) {
    var h = o.h || 0.005, hx = o.hx || 50, hz = o.hz || 50, c = o.at || [0, 0, 0], yaw = o.yaw || 0;
    var cy = Math.cos(yaw), sy = Math.sin(yaw), floor = o.floor === undefined ? 0.006 : o.floor;
    return function (x, z, dome) {
      var px = x, pz = z, y = h + (dome || 0);
      var dx = Math.abs(x) - hx, dz = Math.abs(z) - hz, drop = 0;
      if (dx > 0) { px = (x > 0 ? 1 : -1) * (hx + 0.012); drop += dx; }
      if (dz > 0) { pz = (z > 0 ? 1 : -1) * (hz + 0.012); drop += dz; }
      if (drop > 0) {
        y = h - drop;
        // The floor is the ground, in the set's frame: the slab's own top is c[1] above it. (The
        // first live capture had a serpent's hide hanging in the air past the kit's board,
        // because the floor was taken as relative to the board.)
        if (y < floor - c[1]) {
          var spill = floor - c[1] - y;
          y = floor - c[1];
          if (dx > 0) px += (x > 0 ? 1 : -1) * spill * (dx / drop);
          if (dz > 0) pz += (z > 0 ? 1 : -1) * spill * (dz / drop);
        }
      }
      // A little lie of the hide on whatever it rests on: never perfectly flat.
      y += 0.0035 * Math.sin(x * 9.1 + 1.3) * Math.sin(z * 7.3 + 0.4);
      // The same turn as a node's yaw (00-math.js compose: x' = cos x + sin z).
      return [c[0] + px * cy + pz * sy, c[1] + y, c[2] - px * sy + pz * cy];
    };
  }

  /* The fleshing beam: a log of radius R whose axis rises at `tilt` along +x from `base`.
     The hide's length runs along the log; across, it wraps over the top and hangs down both
     sides, flaring a little, and pools on the ground where the beam runs low. */
  function beam(o) {
    var R = (o.R || 0.09) + EPS * 2, t = o.tilt || 0.38, base = o.at || [0, 0.45, 0], yaw = o.yaw || 0;
    var ax = [Math.cos(t), Math.sin(t), 0], up = [-Math.sin(t), Math.cos(t), 0];
    var cy = Math.cos(yaw), sy = Math.sin(yaw), wrap = Math.PI / 2, off = o.offset || [0, 0, 0];
    return function (x, z) {
      var c = M.add(base, M.scale(ax, x)), az = Math.abs(z), sg = z >= 0 ? 1 : -1, p;
      var phi = az / R;
      if (phi <= wrap) {
        p = M.add(c, M.add(M.scale(up, R * Math.cos(phi)), [0, 0, sg * R * Math.sin(phi)]));
      } else {
        var e = M.add(c, [0, 0, sg * R]), s = az - R * wrap;
        p = [e[0], e[1] - s, e[2] + sg * 0.22 * s];
        if (p[1] < 0.006) { var spill = 0.006 - p[1]; p[1] = 0.006; p[2] += sg * spill; }
      }
      return [off[0] + p[0] * cy + p[2] * sy, off[1] + p[1], off[2] - p[0] * sy + p[2] * cy];
    };
  }

  /* The stretching frame: upright, leaning back by `lean`, the hide's length up the frame,
     bellying away from the eye between the lacing. */
  function frame(o) {
    var c = o.at || [0, 0.9, -0.6], lean = o.lean === undefined ? 0.2 : o.lean, hl = o.hl || 0.8, hw = o.hw || 0.6;
    var up = [0, Math.cos(lean), -Math.sin(lean)], nrm = [0, Math.sin(lean), Math.cos(lean)];
    return function (x, z) {
      var b = -0.03 * (1 - Math.min(1, (x / hl) * (x / hl))) * (1 - Math.min(1, (z / hw) * (z / hw)));
      return M.add(M.add(c, M.add(M.scale(up, x), [z, 0, 0])), M.scale(nrm, b));
    };
  }

  /* Pushed into a vat or a pot of radius `r`, floating at the liquor's top (`at`): crumpled,
     and where it meets the wall it rides up it rather than passing through. The adapter sinks
     the whole of it as the tannage starts; the first draft folded and shrank the hide to a
     few centimetres in the middle of the vat, which read as a leaf, not a hide. */
  function vat(o) {
    var c = o.at || [0, 0, 0], r = o.r || 0.4, lim = r * 0.9;
    return function (x, z) {
      var px = x, pz = z * 0.8, y = 0.006 + 0.014 * Math.sin(x * 9 + z * 4) * Math.cos(z * 11 - x * 3);
      var rad = Math.sqrt(px * px + pz * pz);
      if (rad > lim) {
        var s = lim / rad, ex = rad - lim;
        px *= s; pz *= s;
        y += Math.min(0.1, ex * 0.9);
      }
      return [c[0] + px, c[1] + y, c[2] + pz];
    };
  }

  var DRAPES = { slab: slab, beam: beam, frame: frame, vat: vat };

  /* --- the meshes ------------------------------------------------------------------------- */

  var cache = {};
  function keyOf(o) { return JSON.stringify(o); }

  /* Builds the draped grid once: positions on the surface and their normals, row-major. */
  function surface(spec) {
    var k = "s" + keyOf(spec);
    if (cache[k]) return cache[k];
    var ol = outline(spec.plan, spec.units, spec.seed);
    var d = DRAPES[spec.drape.kind](spec.drape);
    // A drape that holds a bounded hide (the frame between its poles, a vat inside its curb)
    // says how much room there is; a hide larger than that is drawn to fit it.
    var room = spec.drape.fit, fit = room ? Math.min(1, room[0] / ol.L, room[1] / ol.W) : 1;
    var P = [], uv = [], i, j;
    for (i = 0; i <= NU; i++) {
      var u = i / NU;
      for (j = 0; j <= NV; j++) {
        var v = j / NV * 2 - 1, f = ol.at(u, v);
        if (fit < 1) f = [f[0] * fit, f[1] * fit];
        var dome = ol.dome ? ol.dome * Math.max(0, 1 - v * v) * Math.sin(Math.PI * u) : 0;
        P.push(d(f[0], f[1], dome));
        uv.push(u, (v + 1) / 2);
      }
    }
    // Normals from the draped grid's own neighbours, pointed to the drape's outside (up, or
    // toward the camera for the frame).
    var N = [], out = spec.drape.kind === "frame" ? [0, 0.2, 1] : [0, 1, 0];
    function at(a, b) { return P[Math.max(0, Math.min(NU, a)) * (NV + 1) + Math.max(0, Math.min(NV, b))]; }
    for (i = 0; i <= NU; i++) {
      for (j = 0; j <= NV; j++) {
        var du = M.sub(at(i + 1, j), at(i - 1, j)), dv = M.sub(at(i, j + 1), at(i, j - 1));
        var n = M.cross(dv, du);
        if (M.dot(n, n) < 1e-14) n = out.slice();
        n = M.norm(n);
        // Hanging flaps face outward, not up: away from the hide's own middle row.
        var mid = at(i, NV / 2), here = at(i, j), away = M.sub(here, mid);
        var ref = spec.drape.kind === "beam" || spec.drape.kind === "slab" ? M.add(out, M.scale(away, 2)) : out;
        if (M.dot(n, ref) < 0) n = M.scale(n, -1);
        N.push(n);
      }
    }
    var s = { P: P, N: N, uv: uv, L: ol.L * fit, W: ol.W * fit, plan: ol.plan };
    cache[k] = s;
    return s;
  }

  /* One sheet of the hide, offset along its normal by `off`. */
  function sheet(spec, off) {
    var k = "m" + off + keyOf(spec);
    if (cache[k]) return cache[k];
    var s = surface(spec), pos = [], nrm = [], idx = [];
    for (var q = 0; q < s.P.length; q++) {
      var p = M.add(s.P[q], M.scale(s.N[q], off));
      pos.push(p[0], p[1], p[2]);
      nrm.push(s.N[q][0], s.N[q][1], s.N[q][2]);
    }
    for (var i = 0; i < NU; i++) {
      for (var j = 0; j < NV; j++) {
        var a = i * (NV + 1) + j, b = a + NV + 1;
        idx.push(a, b, a + 1, a + 1, b, b + 1);
      }
    }
    var m = GEO.finish(pos, nrm, s.uv.slice(), idx);
    m.rowIdx = NV * 6;          // indices per row: a run of rows is one contiguous range
    m.rows = NU;
    cache[k] = m;
    return m;
  }

  /* The point and normal at (u, v) on the draped surface, bilinear between grid points. */
  function pointAt(spec, u, v) {
    var s = surface(spec);
    var x = sat(u) * NU, y = (Math.max(-1, Math.min(1, v)) + 1) / 2 * NV;
    var i0 = Math.min(NU - 1, Math.floor(x)), j0 = Math.min(NV - 1, Math.floor(y)), fx = x - i0, fy = y - j0;
    function P(a, b) { return s.P[a * (NV + 1) + b]; }
    function N(a, b) { return s.N[a * (NV + 1) + b]; }
    var p = M.lerp3(M.lerp3(P(i0, j0), P(i0, j0 + 1), fy), M.lerp3(P(i0 + 1, j0), P(i0 + 1, j0 + 1), fy), fx);
    var n = M.norm(M.lerp3(M.lerp3(N(i0, j0), N(i0, j0 + 1), fy), M.lerp3(N(i0 + 1, j0), N(i0 + 1, j0 + 1), fy), fx));
    return { p: p, n: n };
  }

  /* A rotation that stands a mesh's +y on n, then turns it by `spin` about that axis. */
  function onNormal(p, n, spin, scl) {
    var pitch = Math.acos(Math.max(-1, Math.min(1, n[1]))), yaw = Math.atan2(n[0], n[2]);
    return M.mul(M.compose(p, [pitch, yaw, 0], [1, 1, 1]), M.compose([0, 0, 0], [0, spin || 0, 0], scl || [1, 1, 1]));
  }

  /* The defects as a list of {u, v, kind, len}: as sent, or seeded from a 0..1 area. */
  function defectList(defects, seed) {
    if (Array.isArray(defects)) {
      return defects.filter(function (d) { return d && isFinite(+d.u) && isFinite(+d.v); }).slice(0, 40).map(function (d) {
        return { u: sat(+d.u), v: Math.max(-1, Math.min(1, +d.v)), kind: d.kind === "score" ? "score" : "hole",
                 len: isFinite(+d.len) ? Math.max(0.02, Math.min(0.3, +d.len)) : 0.08 };
      });
    }
    var area = sat(+defects || 0), n = Math.round(area * 14);
    if (!n) return [];
    var r = M.rng(seed ^ 0x9e3779b9), out = [];
    for (var i = 0; i < n; i++) {
      out.push({ u: 0.15 + r() * 0.7, v: (r() * 2 - 1) * 0.65, kind: r() < 0.45 ? "hole" : "score", len: 0.04 + r() * 0.06, spin: r() * Math.PI });
    }
    return out;
  }

  /* The scars, welded into one mesh on both faces of the hide. Null when there are none. */
  function scars(spec, defects) {
    var list = defectList(defects, spec.seed);
    if (!list.length) return null;
    var k = "d" + keyOf(spec) + keyOf(list);
    if (cache[k]) return cache[k];
    var disc = G.disc(1, 14), parts = [];
    list.forEach(function (d, i) {
      var at = pointAt(spec, d.u, d.v);
      var scl = d.kind === "hole" ? [0.014 + 0.01 * (i % 3), 1, 0.01 + 0.006 * (i % 2)] : [d.len / 2, 1, 0.0035];
      [1, -1].forEach(function (side) {
        var p = M.add(at.p, M.scale(at.n, side * (EPS * 2 + 0.0012)));
        parts.push({ mesh: disc, m: onNormal(p, side > 0 ? at.n : M.scale(at.n, -1), d.spin === undefined ? i * 1.7 : d.spin, scl) });
      });
    });
    var m = G.merge(parts);
    cache[k] = m;
    return m;
  }

  /* --- colour and surface --------------------------------------------------------------- */

  function parseColor(c, d) {
    if (Array.isArray(c) && c.length >= 3) {
      var big = c[0] > 1 || c[1] > 1 || c[2] > 1, k = big ? 1 / 255 : 1;
      var o = [+c[0] * k, +c[1] * k, +c[2] * k];
      return o.every(isFinite) ? o.map(sat) : d;
    }
    if (typeof c === "string") {
      var m = /^#?([0-9a-f]{6})$/i.exec(c.trim());
      if (m) {
        var v = parseInt(m[1], 16);
        return [(v >> 16 & 255) / 255, (v >> 8 & 255) / 255, (v & 255) / 255];
      }
    }
    return d;
  }
  // An sRGB swatch to the base the house shader lights (it does no gamma), as every stage does.
  function toBase(c) { return [Math.pow(c[0], 1.6), Math.pow(c[1], 1.6), Math.pow(c[2], 1.6)]; }

  // The colours of the work's states, swatch values. Scene content (UI plan §4: the
  // tannage's own colour, alum white, bark tan, brain and smoke brown), never chrome.
  var FLESH = [0.8, 0.6, 0.5], FAT = [0.93, 0.86, 0.72], SALTED = [0.9, 0.88, 0.84], PELT = [0.86, 0.76, 0.64];
  var TANNAGE = {
    brain: [0.74, 0.62, 0.46], rawhide: [0.86, 0.74, 0.52], alum: [0.94, 0.92, 0.87],
    bark: [0.6, 0.38, 0.2], mineral: [0.5, 0.56, 0.6], planar: [0.56, 0.5, 0.64]
  };
  // How the hair side of each surface word is shaded: the herb shader's own patterns
  // (1 grain, 3 clay, 4 lumps with a bent normal, 6 leather). Fur is fine soft lumps with no
  // sheen; scale is coarse lumps with a sheen; feather runs in streaks; chitin and shell are
  // a hard, glossy mottle.
  var SURFACE = {
    fur: { pattern: 4, patScale: 9, bump: 0.7, spec: 0.05, shin: 8 },
    scale: { pattern: 4, patScale: 3.4, bump: 1.0, spec: 0.65, shin: 30 },
    feather: { pattern: 1, patScale: 2.2, spec: 0.12, shin: 10 },
    chitin: { pattern: 3, patScale: 3, spec: 0.9, shin: 50 },
    shell: { pattern: 3, patScale: 2, spec: 0.8, shin: 44 },
    smooth: { pattern: 6, patScale: 1.6, spec: 0.3, shin: 16 }
  };
  function surfaceOf(word) { word = String(word || "").toLowerCase(); return SURFACE[word] ? word : "smooth"; }

  var RAW = { green: 1, salted: 1, pelt: 1 };
  /* The two faces of a piece, as materials, from what the server sent and the game's state:
     {out, under, fat}. `st` carries the live look: salt 0..1, wet 0..1, dye [colour, 0..1],
     sheen 0..1, harden 0..1, dull 0..1, quality 0..1. */
  function faces(piece, st) {
    piece = piece || {}; st = st || {};
    var form = String(piece.form || "leather").toLowerCase();
    var hair = parseColor(piece.color, [0.55, 0.42, 0.3]);
    var word = surfaceOf(piece.surface);
    var tk = String(piece.tannage_kind || piece.tannage || "").toLowerCase();
    var tint = TANNAGE[tk] || null;
    var out, under, outLook, underLook;
    var hairLook = SURFACE[word];
    if (RAW[form]) {
      // Raw: the flesh side is worked, the hair below. Salt whitens and speckles it; a fleshed
      // pelt is clean and paler.
      var fl = form === "pelt" ? PELT : FLESH;
      var salt = Math.max(form === "salted" ? 1 : 0, sat(st.salt));
      out = M.lerp3(fl, SALTED, salt * 0.8);
      outLook = salt > 0.05 ? { pattern: 3, patScale: 9, spec: 0.12, shin: 10 } : { pattern: 6, patScale: 2.4, spec: 0.35, shin: 18 };
      under = hair; underLook = hairLook;
    } else if (form === "fur") {
      // Hair-on tanned: the fur is the show side.
      out = hair; outLook = hairLook;
      under = tint || PELT; underLook = SURFACE.smooth;
    } else {
      // Tanned leather and everything cut from it: the grain is the show side, the tannage's
      // colour over the creature's, and the flesh side a paler suede.
      var grain = tint ? M.lerp3(tint, hair, 0.3) : hair;
      if (form === "rawhide") grain = M.lerp3(TANNAGE.rawhide, hair, 0.25);
      out = grain;
      outLook = word === "scale" || word === "chitin" || word === "shell" ? hairLook : SURFACE.smooth;
      under = M.lerp3(grain, [0.88, 0.82, 0.72], 0.35); underLook = { pattern: 6, patScale: 3, spec: 0.05, shin: 6 };
    }
    var dye = st.dye && st.dye[0] ? parseColor(st.dye[0], null) : null;
    if (!dye && piece.dye) dye = parseColor(piece.dye, null);
    var dk = st.dye && st.dye[0] ? sat(st.dye[1]) : (dye ? 1 : 0);
    if (dye && !RAW[form]) out = M.lerp3(out, M.scale(dye, 0.9), 0.75 * dk);
    var hard = Math.max(form === "plate" || piece.hardened ? 1 : 0, sat(st.harden));
    if (hard) out = M.scale(out, 1 - 0.3 * hard);
    var wet = sat(st.wet);
    if (wet) out = M.scale(out, 1 - 0.32 * wet);
    var dull = sat(st.dull);
    if (dull) { out = M.scale(out, 1 - 0.25 * dull); }
    var q = st.quality === undefined ? 0.5 : sat(st.quality);
    function mk(col, look, extra) {
      var o = { color: toBase(col) };
      for (var a in look) o[a] = look[a];
      if (extra) for (var b in extra) o[b] = extra[b];
      return FP.mat("leather", o);
    }
    var outM = mk(out, outLook);
    if (!RAW[form] && form !== "fur") {
      // Finish by quality (UI plan §7.3): rough at Crude, burnished at Flawless; hardened
      // leather takes the gloss cuir bouilli is known for; oil (Curry) and wet casing add sheen.
      outM.spec = (outLook.spec || 0.3) * (0.6 + 0.9 * q) + 0.45 * hard + 0.5 * sat(st.sheen) + 0.35 * wet;
      outM.shin = 14 + 26 * q + 16 * hard + 20 * sat(st.sheen);
    }
    if (dull) outM.spec *= 1 - 0.6 * dull;
    return { out: outM, under: mk(under, underLook), fat: mk(FAT, { pattern: 4, patScale: 7, bump: 1, spec: 0.5, shin: 24 }),
             rgb: out, hair: hair, word: word, form: form, raw: !!RAW[form], hard: hard };
  }

  /* The hide's three layers as meshes for a spec {plan, units, seed, drape}. */
  function hide(spec, layers) {
    return {
      out: sheet(spec, EPS),
      under: sheet(spec, -EPS),
      fat: layers && layers.fat ? sheet(spec, EPS * 3.2) : null,
      laminae: (layers && layers.passes ? Array.apply(null, Array(Math.min(4, layers.passes))).map(function (_, i) { return sheet(spec, -EPS * (3 + 2.4 * i)); }) : []),
      size: outlineSize(spec)
    };
  }
  function outlineSize(spec) { var s = surface(spec); return { L: s.L, W: s.W }; }

  T.hide = {
    PLANS: Object.keys(PLANS), NU: NU, NV: NV, EPS: EPS,
    planOf: planOf, seedOf: seedOf, outline: outline, surface: surface, sheet: sheet, hide: hide,
    pointAt: pointAt, scars: scars, defectList: defectList, onNormal: onNormal,
    faces: faces, parseColor: parseColor, toBase: toBase, surfaceOf: surfaceOf,
    TANNAGE: TANNAGE, SURFACES: Object.keys(SURFACE), size: outlineSize
  };
})();
