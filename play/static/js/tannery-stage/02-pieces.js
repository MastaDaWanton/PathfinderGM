/* The tannery's stage, part 2: the work, built from its pieces.
 *
 * UI plan §7.3, the forge's rule carried over: parametric meshes joined at fixed places, no
 * per-item models. The leather families are:
 *
 *   panel     a cut piece: a suit's body panel (a vest's front, shoulders and all), a shield
 *             blank (round), a strap (a long strip), or a small piece; flat or with a bulge
 *   suit      the body piece of a suit on the table (not a whole suit on a stand, the forge's
 *             rule): a cuirass panel with its cut from the base (leather and hide a moulded
 *             front, padded and quilted a banded one, lamellar rows of laced plates, bone-
 *             studded a front set with studs), its fastenings as buckles or lacing on it and a
 *             lining as a fur or felt edge at the collar
 *   shield    the madu's round leather face and its boss
 *   cloak     a drape of leather laid in folds
 *   boots, gloves, bracers, belt, cap, satchel, sheath, quiver, roll   the worn and carried goods
 *   lacing    a coiled thong (the forge's lash family)
 *   grip      a grip wrap winding onto the forge's haft family (forge-stage/02-families.js)
 *
 * Every builder returns {parts: [{mesh, role}], lo, hi}: meshes in the piece's own frame,
 * lying on y = 0 along x, and a role per mesh ("body", "edge" for a lining, "fit" for a
 * fastening's metal, "lace" for thread and thongs) which the adapter colours from the piece
 * in that slot. Two helpers draw what a method leaves on a piece as it goes: `seam` (a row of
 * stitches, one mesh, drawn a stitch at a time by index range) and `outline` (a chalk line
 * round a pattern, one mesh, cut a stretch at a time the same way). Built once per
 * parameters and cached.
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var F = window.ForgeStageKit || {};
  var T = window.TanneryStageKit = window.TanneryStageKit || {};
  var G = K.mesh, M = K.math, GEO = F.geo, FAM = F.families;
  if (!G || !M || !GEO || !FAM) return;
  var weld = GEO.weld;
  var TAU = Math.PI * 2;

  var cache = {};
  function once(k, fn) { if (!cache[k]) cache[k] = fn(); return cache[k]; }

  /* A sheet over (u, v) in [0, 1]^2 with normals from its own partial derivatives, both faces
     lit by the house shader (it lights the face toward the eye). */
  function field(nu, nv, at) {
    var pos = [], nrm = [], uv = [], idx = [], e = 1e-3;
    for (var i = 0; i <= nu; i++) {
      for (var j = 0; j <= nv; j++) {
        var u = i / nu, v = j / nv, P = at(u, v);
        var du = M.sub(at(Math.min(1, u + e), v), at(Math.max(0, u - e), v));
        var dv = M.sub(at(u, Math.min(1, v + e)), at(u, Math.max(0, v - e)));
        var n = M.cross(dv, du);
        n = M.dot(n, n) < 1e-16 ? [0, 1, 0] : M.norm(n);
        if (n[1] < 0) n = M.scale(n, -1);
        pos.push(P[0], P[1], P[2]); nrm.push(n[0], n[1], n[2]); uv.push(u, v);
      }
    }
    for (i = 0; i < nu; i++) {
      for (j = 0; j < nv; j++) {
        var a = i * (nv + 1) + j, b = a + nv + 1;
        idx.push(a, b, a + 1, a + 1, b, b + 1);
      }
    }
    return GEO.finish(pos, nrm, uv, idx);
  }

  /* --- outlines (half-width along the length, u 0 at the hem, 1 at the collar) ----------- */
  var SHAPES = {
    // A vest's front: the waist, the flare to the chest, the arm holes cut in, the shoulders
    // and the neck scooped out of the middle (that part is the `neck` notch below).
    vest: function (u) {
      var w = 0.92 + 0.08 * Math.sin(u * Math.PI);
      if (u > 0.62 && u < 0.86) w -= 0.3 * Math.sin((u - 0.62) / 0.24 * Math.PI);
      return w;
    },
    round: function (u) { return Math.sqrt(Math.max(0, 1 - Math.pow(2 * u - 1, 2))); },
    strip: function (u) { return u < 0.04 || u > 0.96 ? 0.7 : 1; },
    piece: function (u) { return 0.85 + 0.15 * Math.sin(u * Math.PI); },
    cloak: function (u) { return 0.55 + 0.45 * (1 - u); }
  };
  function neck(shape, u, v) { return shape === "vest" && u > 0.86 && Math.abs(v) < 0.4; }

  /* A flat cut piece L long, W wide, with `bulge` up at its middle (a moulded front). */
  function panel(shape, L, W, bulge, folds) {
    shape = SHAPES[shape] ? shape : "piece";
    return once("panel" + [shape, L, W, bulge || 0, folds || 0].join(","), function () {
      var fn = SHAPES[shape];
      return field(24, 14, function (u, v) {
        var vv = v * 2 - 1, hw = fn(u) * W / 2, z = vv * hw;
        // The neck: the collar's middle is scooped back toward the chest.
        var uu = neck(shape, u, vv) ? 0.86 + (u - 0.86) * Math.pow(Math.abs(vv) / 0.4, 2) : u;
        var y = (bulge || 0) * (1 - vv * vv) * Math.sin(Math.PI * Math.min(1, uu * 1.05));
        if (folds) y += 0.03 * Math.pow(Math.abs(Math.sin(vv * Math.PI * folds)), 1.5) * (1 - uu * 0.6);
        return [(uu - 0.5) * L, y, z];
      });
    });
  }

  /* --- what a method leaves on a piece -------------------------------------------------- */

  /* A row of n stitches along a polyline, each a short slanted bar (saddle stitch), welded in
     order so stitch k is indices [k * per, per]. */
  function seam(points, n, key) {
    return once("seam" + key + n, function () {
      var bar = G.box(1, 0.003, 0.0035), parts = [], per = bar.idx.length;
      var lens = [0], total = 0;
      for (var i = 1; i < points.length; i++) { total += Math.sqrt(M.dot(M.sub(points[i], points[i - 1]), M.sub(points[i], points[i - 1]))); lens.push(total); }
      function at(s) {
        for (var k = 1; k < points.length; k++) {
          if (lens[k] >= s) { var f = (s - lens[k - 1]) / Math.max(1e-6, lens[k] - lens[k - 1]); return [M.lerp3(points[k - 1], points[k], f), M.sub(points[k], points[k - 1])]; }
        }
        return [points[points.length - 1], M.sub(points[points.length - 1], points[points.length - 2])];
      }
      for (var s = 0; s < n; s++) {
        var r = at((s + 0.5) / n * total), d = M.norm(r[1]);
        var yaw = Math.atan2(-d[2], d[0]) + 0.5;
        parts.push([bar, r[0], [0, yaw, 0], [total / n * 0.62, 1, 1]]);
      }
      var m = weld(parts);
      m.per = per; m.count = n;
      return m;
    });
  }

  /* The chalk line round a pattern (a closed polyline), n dashes in order, so the cut can be
     drawn as the first k of them. */
  function outline(points, n, key) {
    return once("outline" + key + n, function () {
      var closed = points.concat([points[0]]), m = seam(closed, n, "o" + key);
      return m;
    });
  }

  /* The edge of a pattern's panel as points on y = 0 (for the chalk line and the seam). */
  function edgeOf(shape, L, W, n) {
    var fn = SHAPES[shape] || SHAPES.piece, pts = [], i;
    n = n || 24;
    for (i = 0; i <= n; i++) { var u = i / n; pts.push([(u - 0.5) * L, 0, fn(u) * W / 2]); }
    for (i = n; i >= 0; i--) { var u2 = i / n; pts.push([(u2 - 0.5) * L, 0, -fn(u2) * W / 2]); }
    return pts;
  }

  /* --- the families --------------------------------------------------------------------- */
  function out(parts) {
    var lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    parts.forEach(function (p) {
      var b = p.mesh.bounds;
      for (var k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], b.lo[k]); hi[k] = Math.max(hi[k], b.hi[k]); }
    });
    return { parts: parts, lo: lo, hi: hi };
  }
  function buckles(span, at) {
    return weld([[G.box(0.05, 0.006, 0.02), [at[0] - span / 2, at[1], at[2]]], [G.ring(0.014, 0.003, 12, 4), [at[0] - span / 2 + 0.03, at[1] + 0.004, at[2]]],
                 [G.box(0.05, 0.006, 0.02), [at[0] + span / 2, at[1], at[2]]], [G.ring(0.014, 0.003, 12, 4), [at[0] + span / 2 - 0.03, at[1] + 0.004, at[2]]]]);
  }
  function lacingRun(L, W, y) {
    var parts = [];
    for (var i = 0; i < 7; i++) {
      var x = -L * 0.35 + i * L * 0.1;
      parts.push([G.box(0.004, 0.003, W * 0.9), [x, y, 0], [0, i % 2 ? 0.35 : -0.35, 0]]);
    }
    return weld(parts);
  }

  function suit(base) {
    var b = String(base || "").toLowerCase(), L = 0.56, W = 0.46;
    return once("suit" + b, function () {
      var parts = [];
      if (/lamellar/.test(b)) {
        // Rows of small laced plates (the forge's scale family's splint rows, in leather).
        parts.push({ mesh: panel("vest", L, W, 0.04), role: "under" });
        var r = [], rows = 9, cols = 7;
        for (var i = 0; i < rows; i++) for (var j = 0; j < cols; j++) {
          r.push([G.box(L / rows * 0.92, 0.008, W / cols * 0.86), [-L / 2 + (i + 0.5) * L / rows, 0.045 + 0.004 * (j % 2), -W / 2 + (j + 0.5) * W / cols]]);
        }
        parts.push({ mesh: weld(r), role: "body" });
        parts.push({ mesh: lacingRun(L, W, 0.052), role: "lace" });
      } else if (/padded|quilted/.test(b)) {
        parts.push({ mesh: panel("vest", L, W, 0.06, 6), role: "body" });
      } else {
        parts.push({ mesh: panel("vest", L, W, 0.08), role: "body" });
        if (/stud/.test(b)) {
          var st = [], sp = G.sphere(0.008, 8, 6);
          for (var a = 0; a < 6; a++) for (var c = 0; c < 5; c++) {
            var u = 0.12 + a * 0.12, v = (c - 2) * 0.18;
            st.push([sp, [(u - 0.5) * L, 0.08 * (1 - v * v) * Math.sin(Math.PI * u) + 0.004, v * W / 2]]);
          }
          parts.push({ mesh: weld(st), role: "fit" });
        }
      }
      parts.push({ mesh: buckles(L * 0.55, [-0.02, 0.03, W * 0.48]), role: "fastenings" });
      parts.push({ mesh: weld([[G.capsule(0.014, W * 0.42, 8), [L * 0.5 - 0.02, 0.02, -W * 0.21], [Math.PI / 2, 0, 0]]]), role: "lining" });
      return out(parts);
    });
  }

  function shield() {
    return once("madu", function () {
      var face = FAM.build("plate", { v: "round", r: 0.26, bulge: 0.05 });
      var boss = FAM.build("guard", { v: "boss" });
      return out([{ mesh: face.meshes[0], role: "body" }, { mesh: weld([[boss.meshes[0], [0, 0.05, 0]]]), role: "fit" },
                  { mesh: weld([[G.ring(0.255, 0.008, 40, 5), [0, 0.006, 0]]]), role: "lace" }]);
    });
  }

  function cloak() {
    return once("cloak", function () {
      return out([{ mesh: panel("cloak", 0.95, 0.9, 0.02, 4), role: "body" },
                   { mesh: weld([[G.capsule(0.016, 0.38, 8), [0.47, 0.02, -0.19], [Math.PI / 2, 0, 0]]]), role: "lining" },
                   { mesh: weld([[G.ring(0.02, 0.005, 12, 4), [0.45, 0.03, 0.08]], [G.ring(0.02, 0.005, 12, 4), [0.45, 0.03, -0.08]]]), role: "fastenings" }]);
    });
  }

  function boot(x) {
    var leg = G.lathe([[0.045, 0], [0.05, 0.1], [0.052, 0.22], [0.055, 0.24], [0, 0.24]], 12, 50);
    return weld([[leg, [x, 0, 0]], [G.capsule(0.045, 0.2, 10), [x + 0.1, 0.04, 0], [0, 0, -Math.PI / 2], [1, 1, 0.9]]]);
  }
  function goods(kind) {
    return once("goods" + kind, function () {
      var p = [];
      switch (kind) {
        case "boots":
          p.push({ mesh: weld([[boot(-0.05), [0, 0, -0.07]], [boot(-0.05), [0.02, 0, 0.07]]]), role: "body" });
          p.push({ mesh: weld([[G.ring(0.056, 0.006, 16, 4), [-0.05, 0.235, -0.07]], [G.ring(0.056, 0.006, 16, 4), [-0.03, 0.235, 0.07]]]), role: "lining" });
          break;
        case "gloves":
          [-0.08, 0.08].forEach(function (z) {
            var f = [[G.box(0.11, 0.02, 0.09), [0, 0.01, z]]];
            for (var i = 0; i < 4; i++) f.push([G.capsule(0.009, 0.07, 6), [0.055, 0.01, z - 0.033 + i * 0.022], [0, 0, -Math.PI / 2]]);
            f.push([G.capsule(0.01, 0.05, 6), [0.02, 0.01, z + 0.05], [0, -0.7, -Math.PI / 2]]);
            p.push({ mesh: weld(f), role: "body" });
          });
          p.push({ mesh: weld([[G.box(0.03, 0.022, 0.095), [-0.065, 0.011, -0.08]], [G.box(0.03, 0.022, 0.095), [-0.065, 0.011, 0.08]]]), role: "lining" });
          break;
        case "bracers":
          p.push({ mesh: weld([[G.cylinder(0.04, 0.2, 14, 0.033), [-0.1, 0.04, -0.06], [0, 0, -Math.PI / 2]], [G.cylinder(0.04, 0.2, 14, 0.033), [-0.1, 0.04, 0.06], [0, 0, -Math.PI / 2]]]), role: "body" });
          p.push({ mesh: lacingRun(0.2, 0.04, 0.08), role: "lace" });
          break;
        case "belt":
          p.push({ mesh: panel("strip", 0.9, 0.045, 0), role: "body" });
          p.push({ mesh: weld([[G.ring(0.028, 0.005, 14, 4), [0.46, 0.004, 0], [0, 0, 0], [1, 1, 0.8]]]), role: "fastenings" });
          break;
        case "cap":
          p.push({ mesh: G.lathe([[0.1, 0], [0.098, 0.04], [0.08, 0.08], [0.04, 0.105], [0, 0.11]], 18, 50), role: "body" });
          p.push({ mesh: weld([[G.ring(0.1, 0.008, 20, 4), [0, 0.004, 0]]]), role: "lining" });
          break;
        case "satchel":
          p.push({ mesh: weld([[G.box(0.28, 0.2, 0.08), [0, 0.04, 0], [Math.PI / 2, 0, 0]]]), role: "body" });
          p.push({ mesh: panel("piece", 0.16, 0.28, 0.01), role: "body", at: [0.06, 0.085, 0] });
          p.push({ mesh: weld([[G.box(0.02, 0.006, 0.03), [0.0, 0.09, 0]]]), role: "fastenings" });
          break;
        case "sheath":
          p.push({ mesh: weld([[G.lathe([[0.03, 0], [0.025, 0.25], [0.004, 0.32], [0, 0.32]], 10, 50), [0.16, 0.02, 0], [0, 0, Math.PI / 2], [1, 1, 0.35]]]), role: "body" });
          break;
        case "quiver":
          p.push({ mesh: weld([[G.cylinder(0.05, 0.5, 14, 0.045), [-0.25, 0.05, 0], [0, 0, -Math.PI / 2]]]), role: "body" });
          p.push({ mesh: weld([[G.ring(0.05, 0.006, 14, 4), [0.25, 0.05, 0], [0, 0, Math.PI / 2]]]), role: "lining" });
          break;
        default:   // the kit roll and anything unknown: a rolled bundle tied with a thong
          p.push({ mesh: weld([[G.cylinder(0.05, 0.36, 14), [0, 0.05, -0.18], [Math.PI / 2, 0, 0]]]), role: "body" });
          p.push({ mesh: weld([[G.ring(0.052, 0.004, 14, 4), [0, 0.05, 0.07], [Math.PI / 2, 0, 0]], [G.ring(0.052, 0.004, 14, 4), [0, 0.05, -0.07], [Math.PI / 2, 0, 0]]]), role: "lace" });
      }
      return out(p);
    });
  }

  function lacing() {
    return once("lacing", function () {
      var lash = FAM.build("haft", { v: "lash", r: 0.008 });
      return out(lash.meshes.map(function (m) { return { mesh: m, role: "body" }; }));
    });
  }

  /* The grip: the forge's haft (a plain straight haft, the wood a smith would fit), and the
     wrap as n turns along it, welded in order so the first k turns are drawn as it winds. */
  function grip(n) {
    n = n || 14;
    return once("grip" + n, function () {
      var haft = FAM.build("haft", { len: 0.5, r: 0.016 });
      var ring = G.ring(0.018, 0.0045, 14, 4), turns = [];
      for (var i = 0; i < n; i++) turns.push([ring, [-0.04 - i * 0.012, 0, 0], [0, 0, Math.PI / 2 + 0.3]]);
      var wrap = weld(turns);
      wrap.per = ring.idx.length; wrap.count = n;
      var o = out([{ mesh: haft.meshes[0], role: "haft" }, { mesh: wrap, role: "body", wrap: true }]);
      return o;
    });
  }

  /* Which family a product id is, and its parameters. Unknown ids are a plain piece. */
  var GOODS = { boots: 1, gloves: 1, bracers: 1, belt: 1, cap: 1, satchel: 1, sheath: 1, quiver: 1, "kit roll": 1 };
  function build(product, base) {
    var p = String(product || "").toLowerCase();
    if (p === "madu" || /shield|madu/.test(String(base || ""))) return shield();
    if (p === "cloak") return cloak();
    if (p === "lacing") return lacing();
    if (p === "grip") return grip();
    if (GOODS[p]) return goods(p === "kit roll" ? "roll" : p);
    if (/armou?r|padded|quilted|lamellar|leather|hide|studded/.test(p + " " + String(base || ""))) return suit(p + " " + String(base || ""));
    return out([{ mesh: panel("piece", 0.4, 0.3, 0.01), role: "body" }]);
  }

  /* The cut piece Cut makes for a product (its pattern on the leather): a suit's front, a
     shield's round, a strap for a belt or a lacing set, a small piece for the rest. */
  function patternOf(product) {
    var p = String(product || "").toLowerCase();
    if (p === "madu") return { shape: "round", L: 0.52, W: 0.52 };
    if (p === "belt" || p === "lacing" || p === "grip") return { shape: "strip", L: 0.7, W: 0.05 };
    if (p === "cloak") return { shape: "cloak", L: 0.8, W: 0.7 };
    if (GOODS[p]) return { shape: "piece", L: 0.3, W: 0.22 };
    return { shape: "vest", L: 0.56, W: 0.46 };
  }

  T.pieces = { panel: panel, seam: seam, outline: outline, edgeOf: edgeOf, build: build, patternOf: patternOf,
               grip: grip, field: field, SHAPES: Object.keys(SHAPES), GOODS: Object.keys(GOODS) };
})();
