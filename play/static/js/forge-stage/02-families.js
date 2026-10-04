/* The forge's stage, part 2: the work, built from its pieces.
 *
 * UI plan §7.3 and the owner's answer (§1): "Procedural families ... joined on the anvil and
 * coloured by material. No per-weapon models." A FAMILY is a parametric mesh builder; a PLAN
 * says which family fills each of the item's piece slots, with what parameters, and where its
 * socket sits; the adapter (table/42-forge-stage.js) gives each piece its material.
 *
 * The eleven families, and nothing else (tests/test_forge_stage.py holds the list):
 *   blade.straight  blade.curved  axe  hammer  spear  haft  grip  guard  plate  mail  scale
 *
 * THE FRAME. Every piece lies on the anvil along x, flat faces up (+y), its socket at the
 * origin. A head reaches toward +x (an axe's or hammer's head stands across the haft, toward
 * +z, the camera); a haft or grip reaches back toward -x; a guard sits at the socket. So a
 * sword is grip [-0.2, 0], guard at 0, blade [0, 0.8], and an axe is haft [-0.6, 0.04] with
 * its head at 0 reaching toward the viewer. The plan may move a piece (`at`) when the item is
 * not built that way round: a bow's grip sits in the middle of its limbs, a spear's butt cap
 * at the far end of its haft.
 *
 * WHICH FAMILY. Weapons map through their table row (UI plan §7.3: "category, damage type,
 * hands"), in three passes, most specific first, so every one of the 456 rows gets a shape:
 *   1. the NAME, against what each weapon is (a glaive is a curved blade on a pole whatever
 *      its components column says);
 *   2. the row's `components.head` words ("Axehead", "Barrel", "Spiked pick head");
 *   3. damage type and hands (slashing a blade, piercing a spear, bludgeoning a hammer).
 * The test runs every row of content/weapons/weapons.json through this and asserts each
 * lands on one of the eleven families, and pins the common ones (a longsword is a straight
 * blade with a grip and a cross guard; a scimitar is curved; a halberd is an axe on a pole).
 * With only an id (the record's `base`), the id's words stand in for the name, and the
 * same passes run.
 *
 * Armour shows as its body piece on the anvil (plan §7.3, proposed): a plate, a fold of mail,
 * a row of scales; fastenings show as buckles, and the lining is not drawn (it is inside).
 * A plan with no gear at all is a bar of the head's metal (what Forge starts from).
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var F = window.ForgeStageKit = window.ForgeStageKit || {};
  var G = K.mesh, M = K.math, GEO = F.geo;
  var FAMILIES = ["blade.straight", "blade.curved", "axe", "hammer", "spear", "haft", "grip", "guard",
                  "plate", "mail", "scale"];
  var TAU = Math.PI * 2;

  /* --- builders -----------------------------------------------------------------------------
     Each returns {meshes: [mesh, ...], lo: [x,y,z], hi: [x,y,z]}: the meshes in the piece's
     own frame (a head may be cut into runs along its length, for the temper colour run). */
  var cache = {};
  function key(fam, p) { return fam + JSON.stringify(p); }
  function boundsOf(meshes) {
    var lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    meshes.forEach(function (m) {
      for (var k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], m.bounds.lo[k]); hi[k] = Math.max(hi[k], m.bounds.hi[k]); }
    });
    return { lo: lo, hi: hi };
  }
  function out(meshes) { var b = boundsOf(meshes); return { meshes: meshes, lo: b.lo, hi: b.hi }; }
  var RUNS = 8;
  function runs(n) { var r = []; for (var i = 1; i < RUNS; i++) r.push(Math.round(i * (n - 1) / RUNS)); return r; }

  /* A blade along +x. p: len, width, thick, curve (0 straight; the edge is on the convex,
     +z, side), single (single-edged), tip ("point" | "round" | "leaf" | "chisel" | "wave"),
     taper (width kept at the start of the point). Double-edged blades have a flat with
     bevels (six points round), so the flat catches the light and the edges stay sharp. */
  function blade(p) {
    var n = 33, len = p.len || 0.8, W = p.width || 0.05, T = p.thick || W * 0.18;
    var curve = p.curve || 0, tip = p.tip || "point", taper = p.taper === undefined ? 0.72 : p.taper;
    function width(s) {
      if (tip === "leaf") return W * (0.45 + 0.75 * Math.sin(Math.PI * Math.pow(s, 0.75))) * (1 - Math.pow(s, 6)) + 0.002;
      var w = W * (1 - (1 - taper) * s);
      var t0 = tip === "round" ? 0.9 : (tip === "chisel" ? 0.97 : 0.82);
      if (s > t0) {
        var q = (s - t0) / (1 - t0);
        w *= tip === "round" ? Math.sqrt(Math.max(0, 1 - q * q)) : (tip === "chisel" ? 1 - 0.4 * q : 1 - q);
      }
      if (tip === "wave") w *= 1 + 0.12 * Math.sin(s * 22);
      return Math.max(0.0015, w);
    }
    function centre(s) { return [s * len, 0, -curve * len * s * s]; }
    var sec = p.single
      ? function (w, t) { return [[w * 0.5, 0], [w * 0.1, t * 0.5], [-w * 0.5, t * 0.42], [-w * 0.5, -t * 0.42], [w * 0.1, -t * 0.5]]; }
      : function (w, t) { return [[w * 0.5, 0], [w * 0.2, t * 0.5], [-w * 0.2, t * 0.5], [-w * 0.5, 0], [-w * 0.2, -t * 0.5], [w * 0.2, -t * 0.5]]; };
    var K0 = p.single ? 5 : 6;
    var meshes = GEO.sweep(n, K0, function (i, j) {
      var s = i / (n - 1), c = centre(s), c2 = centre(Math.min(1, s + 0.01)), c1 = centre(Math.max(0, s - 0.01));
      var tx = c2[0] - c1[0], tz = c2[2] - c1[2], tl = Math.sqrt(tx * tx + tz * tz) || 1;
      var wz = [-tz / tl, tx / tl];   // across the blade, in xz
      var t = T * (1 - 0.55 * s) + 0.0008, pt = sec(width(s), t)[j];
      return [c[0] + wz[0] * pt[0], pt[1], c[2] + wz[1] * pt[0]];
    }, { runs: runs(n), caps: true });
    return out(meshes);
  }

  /* An axe head standing across the haft toward +z. p: edge (length of the cutting edge,
     along x), depth (how far it reaches), beard (0..1, the lower horn), double (a second bit
     toward -z). The eye wraps the haft at the origin. */
  function axe(p) {
    var E = p.edge || 0.16, D = p.depth || 0.16, beard = p.beard || 0;
    function bit(sign) {
      var n = 14;
      return GEO.sweep(n, 6, function (i, j) {
        var s = i / (n - 1), z = sign * (0.02 + s * D);
        var wx = 0.06 + (E - 0.06) * Math.pow(s, 1.7), ty = 0.04 * (1 - s) + 0.003;
        var cx = -beard * E * 0.35 * s * s;
        var sec = [[wx / 2, ty * 0.2], [0, ty / 2], [-wx / 2, ty * 0.2], [-wx / 2, -ty * 0.2], [0, -ty / 2], [wx / 2, -ty * 0.2]][j];
        return [cx + sec[0], sec[1], z];
      }, { runs: sign > 0 ? [4, 9] : [], caps: true });
    }
    var meshes = bit(1);
    if (p.double) meshes = meshes.concat(bit(-1));
    else meshes.push(GEO.weld([[G.box(0.05, 0.045, 0.05), [0, 0, -0.035]]]));
    meshes.push(GEO.weld([[G.box(0.075, 0.05, 0.05), [0, 0, 0]]]));
    return out(meshes);
  }

  /* A hammer-family head. p.v: "hammer" | "maul" | "pick" (across the haft), "mace" | "star" |
     "club" (on the end of the haft, along x), "ball" (a ball: shot, a bloom, a flail's head). */
  function hammer(p) {
    var v = p.v || "hammer", k = p.k || 1, meshes;
    if (v === "hammer" || v === "maul" || v === "pick") {
      var big = v === "maul" ? 1.6 : 1;
      var parts = [[G.box(0.055 * big, 0.055 * big, 0.12 * big), [0, 0, 0.01]],
                   [G.cylinder(0.034 * big, 0.03, 14), [0, 0, 0.07 * big + 0.01], [Math.PI / 2, 0, 0]]];
      meshes = [GEO.weld(parts)];
      if (v === "pick") {
        meshes = meshes.concat(blade({ len: 0.2, width: 0.035, thick: 0.03, tip: "point", taper: 0.6 }).meshes.map(function (m) {
          return GEO.weld([[m, [0, 0, -0.05], [0, -Math.PI / 2, 0]]]);
        }));
      } else {
        meshes.push(GEO.weld([[G.box(0.05 * big, 0.03 * big, 0.06 * big), [0, 0, -0.07 * big]]]));
      }
    } else if (v === "mace" || v === "star") {
      var core = [[G.sphere(0.05, 14, 10), [0.07, 0, 0], [0, 0, 0], [1.2, 1, 1]]];
      var nSp = v === "star" ? 10 : 6, spike = G.lathe([[0, 0], [0.018, 0], [0, 0.05]], 6, 60);
      var fl = G.box(0.1, 0.04, 0.012);
      for (var i = 0; i < nSp; i++) {
        var a = i / nSp * TAU;
        if (v === "star") core.push([spike, [0.07 + (i % 2 ? 0.02 : -0.02), Math.cos(a) * 0.045, Math.sin(a) * 0.045], [a, 0, 0]]);
        else core.push([fl, [0.07, Math.cos(a) * 0.045, Math.sin(a) * 0.045], [a, 0, 0]]);
      }
      if (v === "star") core.push([spike, [0.13, 0, 0], [0, 0, -Math.PI / 2]]);
      meshes = [GEO.weld(core)];
    } else if (v === "club") {
      meshes = [GEO.latheX([[0.022, 0], [0.03, 0.12], [0.045, 0.3], [0.04, 0.34], [0, 0.36]], 14)];
    } else {
      meshes = [GEO.weld([[G.sphere(0.05, 14, 10), [0.05, 0, 0], [0.4, 0.7, 0.2], [1.15, 0.85, 1]]])];
    }
    if (k !== 1) meshes = meshes.map(function (m) { return GEO.weld([[m, [0, 0, 0], [0, 0, 0], [k, k, k]]]); });
    return out(meshes);
  }

  /* A spearhead: a leaf blade on a socket. p.tines 3 is a trident's fork; 2 a branched spear. */
  function spear(p) {
    var len = p.len || 0.26, W = p.width || 0.06, tines = p.tines || 1, meshes = [];
    meshes.push(GEO.latheX([[0.02, 0], [0.019, 0.06], [0.012, 0.1], [0, 0.11]], 10));
    if (tines === 1) {
      meshes = meshes.concat(blade({ len: len, width: W, tip: p.tip || "leaf", thick: W * 0.25 }).meshes.map(function (m) {
        return GEO.weld([[m, [0.08, 0, 0]]]);
      }));
    } else {
      var bar = GEO.weld([[G.box(0.02, 0.016, 0.03 * (tines + 1)), [0.1, 0, 0]]]);
      meshes.push(bar);
      for (var t = 0; t < tines; t++) {
        var z = (t - (tines - 1) / 2) * 0.045;
        blade({ len: len * (t === (tines - 1) / 2 ? 1 : 0.8), width: 0.014, thick: 0.01, tip: "point", taper: 0.8 }).meshes.forEach(function (m) {
          meshes.push(GEO.weld([[m, [0.1, 0, z]]]));
        });
      }
    }
    return out(meshes);
  }

  /* A haft back along -x from the socket. p: len, r, over (past the socket), v ("straight" |
     "bow" (an arc of limb, centred) | "lash" (a coiled whip) | "beam" (squared timber)). */
  function haft(p) {
    var len = p.len || 0.6, r = p.r || 0.018, over = p.over === undefined ? 0.03 : p.over, v = p.v || "straight";
    if (v === "bow") {
      var n = 25, bend = p.bend || 0.12;
      return out(GEO.sweep(n, 6, function (i, j) {
        var s = i / (n - 1), x = (s - 0.5) * len, z = -bend * len * (1 - Math.pow(2 * s - 1, 2));
        var rr = r * (1 - 0.55 * Math.abs(2 * s - 1)) + 0.003, a = j / 6 * TAU;
        return [x, Math.sin(a) * rr * 0.8, z + Math.cos(a) * rr];
      }, { caps: true }));
    }
    if (v === "lash") {
      var m = 40, turns = 2.2;
      return out(GEO.sweep(m, 5, function (i, j) {
        var s = i / (m - 1), a = s * turns * TAU, rad = 0.05 + 0.12 * s;
        var c = [-0.05 - Math.cos(a) * rad, 0.01, Math.sin(a) * rad];
        var rr = r * (1 - 0.7 * s) + 0.002, b = j / 5 * TAU;
        return [c[0] + Math.cos(b) * rr * 0.6, c[1] + Math.sin(b) * rr, c[2] + Math.cos(b) * rr * 0.6];
      }, { caps: true }));
    }
    if (v === "beam") return out([GEO.weld([[G.box(len + over, r * 2, r * 2), [-(len - over) / 2, 0, 0]]])]);
    return out([GEO.weld([[GEO.latheX([[r * 1.08, 0], [r, 0.05], [r * 0.95, len * 0.7], [r, len + over - 0.01], [0, len + over]], 12), [-len, 0, 0]]])]);
  }

  /* A grip back along -x: a wrapped spindle and a pommel ("ball" | "disc" | "wheel" | "none"). */
  function grip(p) {
    var len = p.len || 0.2, r = p.r || 0.016, pom = p.pommel || "wheel";
    var parts = [[GEO.latheX([[r * 0.9, 0], [r * 1.1, len * 0.5], [r * 0.95, len]], 12), [-len, 0, 0]]];
    var wraps = Math.max(3, Math.round(len / 0.022)), ring = G.ring(r * 1.05, r * 0.22, 14, 4);
    for (var i = 0; i < wraps; i++) parts.push([ring, [-len * (i + 0.5) / wraps, 0, 0], [0, 0, Math.PI / 2 + 0.25]]);
    if (pom === "ball") parts.push([G.sphere(r * 1.8, 12, 8), [-len - r * 1.2, 0, 0]]);
    else if (pom === "disc" || pom === "wheel") parts.push([G.cylinder(r * (pom === "wheel" ? 2.2 : 1.6), r * 1.4, 14), [-len - r * 1.4, 0, 0], [0, 0, -Math.PI / 2]]);
    return out([GEO.weld(parts)]);
  }

  /* A guard or fitting at the socket. p.v: "cross" | "small" | "disc" (tsuba) | "basket" |
     "collar" (langets round a haft) | "cap" (a butt cap) | "trigger" | "buckle" (armour
     fastenings) | "boss" (a shield's). */
  function guard(p) {
    var v = p.v || "cross", w = p.w || 0.2, parts = [];
    if (v === "cross" || v === "small") {
      var len = v === "small" ? w * 0.5 : w;
      parts.push([G.box(0.022, 0.02, len), [0, 0, 0]]);
      parts.push([G.sphere(0.014, 8, 6), [0, 0, len / 2]], [G.sphere(0.014, 8, 6), [0, 0, -len / 2]]);
    } else if (v === "disc") {
      parts.push([G.cylinder(0.042, 0.008, 18), [0.004, 0, 0], [0, 0, -Math.PI / 2], [1, 1, 0.8]]);
    } else if (v === "basket") {
      parts.push([G.ring(0.045, 0.005, 24, 5), [-0.04, 0, 0.02], [0, 0, Math.PI / 2]]);
      parts.push([G.box(0.02, 0.016, 0.14), [0, 0, 0]]);
    } else if (v === "collar") {
      parts.push([G.box(0.11, 0.046, 0.012), [-0.06, 0, 0.022]], [G.box(0.11, 0.046, 0.012), [-0.06, 0, -0.022]]);
      parts.push([G.ring(0.024, 0.005, 14, 4), [-0.12, 0, 0], [0, 0, Math.PI / 2]]);
    } else if (v === "cap") {
      parts.push([GEO.latheX([[0.021, 0], [0.023, 0.05], [0.012, 0.08], [0, 0.085]], 10), [0, 0, 0], [0, Math.PI, 0]]);
    } else if (v === "trigger") {
      parts.push([G.ring(0.025, 0.004, 16, 4), [0, -0.03, 0], [Math.PI / 2, 0, 0]]);
    } else if (v === "buckle") {
      var sp = p.span || 0.2;
      [-1, 1].forEach(function (s) {
        parts.push([G.box(0.05, 0.006, 0.02), [s * sp * 0.5, 0, 0]]);
        parts.push([G.ring(0.012, 0.003, 12, 4), [s * sp * 0.5, 0.004, 0.012]]);
      });
    } else if (v === "boss") {
      parts.push([G.lathe([[0.07, 0], [0.06, 0.025], [0.03, 0.045], [0, 0.05]], 18, 40), [0, 0, 0]]);
    }
    return out([GEO.weld(parts.length ? parts : [[G.box(0.01, 0.01, 0.01), [0, 0, 0]]])]);
  }

  /* A height field over (u, v) in [0, 1]^2 with normals from its own partial derivatives. */
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

  /* A plate. p.v: "breast" | "banded" | "round" (buckler, shield) | "kite" | "knuckle"
     (gauntlet, knuckles) | "pouch" (a sling's) | "bar" (bar stock: the work before a shape).
     len along x, width along z, bulge up. */
  function plate(p) {
    var v = p.v || "breast", L = p.len || 0.5, W = p.width || 0.36, B = p.bulge === undefined ? 0.08 : p.bulge;
    if (v === "bar") return out([GEO.weld([[G.box(L, p.thick || 0.03, W), [L / 2, (p.thick || 0.03) / 2, 0]]])]);
    var m;
    if (v === "round") {
      var R = p.r || 0.3;
      m = field(10, 36, function (u, a) {
        var t = a * TAU, r = u * R;
        return [Math.cos(t) * r, B * (1 - u * u) + (u > 0.92 ? 0.006 : 0), Math.sin(t) * r];
      });
    } else {
      m = field(20, 16, function (u, v2) {
        var x = (u - 0.5) * L, zz = v2 - 0.5;
        var wk = v === "kite" ? (1 - 0.8 * u) : (v === "breast" ? 0.8 + 0.2 * Math.sin(Math.PI * u) : 1);
        var y = B * (1 - 4 * zz * zz) * (v === "knuckle" ? 1 : (0.75 + 0.25 * Math.sin(Math.PI * u)));
        if (v === "breast") y += 0.012 * Math.max(0, 1 - Math.abs(zz) * 14);   // the medial ridge
        if (v === "banded") y += 0.008 * Math.pow(Math.max(0, Math.sin(u * Math.PI * 7)), 6);
        if (v === "knuckle") y += 0.012 * Math.pow(Math.max(0, Math.sin(v2 * Math.PI * 4)), 4);
        return [x + L / 2, y, zz * W * wk];
      });
    }
    var meshes = [m];
    if (v === "knuckle") {
      var spike = G.lathe([[0, 0], [0.008, 0], [0, 0.03]], 6, 60), sp = [];
      for (var i = 0; i < 4; i++) sp.push([spike, [L * 0.85, B + 0.01, (i - 1.5) * W / 4]]);
      meshes.push(GEO.weld(sp));
    }
    return out(meshes);
  }

  /* A fold of mail: two layers of rings, the top folded back half way. */
  function mail(p) {
    var L = p.len || 0.42, W = p.width || 0.26, s = 0.024, ring = G.ring(0.011, 0.0024, 8, 4), parts = [];
    var nx = Math.round(L / s), nz = Math.round(W / s);
    for (var layer = 0; layer < 2; layer++) {
      var cols = layer ? Math.round(nx * 0.55) : nx;
      for (var i = 0; i < cols; i++) {
        for (var j = 0; j < nz; j++) {
          var x = (i + (j % 2) * 0.5) * s, z = (j - nz / 2) * s * 0.86;
          var y = 0.004 + layer * 0.014 + 0.003 * Math.sin(i * 0.9 + j * 1.3);
          parts.push([ring, [x, y, z], [(i + j) % 2 ? 0.55 : -0.55, 0, 0]]);
        }
      }
    }
    return out([GEO.weld(parts)]);
  }

  /* A row of scales on a leather backing; p.v "splint" lays long narrow strips instead. */
  function scale(p) {
    var L = p.len || 0.46, W = p.width || 0.3, parts = [], strip = p.v === "splint";
    var sc = strip ? G.box(0.03, 0.006, W * 0.9) : G.lathe([[0.028, 0], [0.02, 0.004], [0, 0.006]], 10, 70);
    var rows = strip ? Math.round(L / 0.034) : Math.round(L / 0.036), cols = strip ? 1 : Math.round(W / 0.04);
    for (var i = 0; i < rows; i++) {
      for (var j = 0; j < cols; j++) {
        var x = i * (strip ? 0.034 : 0.036), z = strip ? 0 : (j - (cols - 1) / 2 + (i % 2) * 0.5) * 0.04;
        parts.push([sc, [x + 0.02, 0.012 + 0.002 * (i % 2), z], [0, 0, strip ? 0 : -0.25], strip ? [1, 1, 1] : [1, 1, 1.3]]);
      }
    }
    var meshes = [GEO.weld(parts)];
    meshes.push(GEO.weld([[G.box(L + 0.02, 0.008, W + 0.02), [L / 2, 0.004, 0]]]));
    return out(meshes);
  }

  var BUILD = { "blade.straight": blade, "blade.curved": blade, axe: axe, hammer: hammer, spear: spear,
                haft: haft, grip: grip, guard: guard, plate: plate, mail: mail, scale: scale };

  /* Built once per (family, parameters), then shared: the meshes are never changed after. */
  function build(fam, p) {
    var k = key(fam, p);
    if (!cache[k]) {
      var q = {};
      for (var a in p) q[a] = p[a];
      if (fam === "blade.curved" && !q.curve) q.curve = 0.1;
      cache[k] = BUILD[fam](q);
    }
    return cache[k];
  }

  /* --- which family ------------------------------------------------------------------------- */

  function rowOf(base) {
    if (base && typeof base === "object") return base;
    var id = String(base || "");
    return { id: id, name: id.replace(/[-_]+/g, " ") };
  }
  function sizeOf(row) {
    if (row.light || /light weapons/i.test(row.section || "")) return "light";
    if (+row.hands === 2 || /two-handed/i.test(row.section || "")) return "two";
    return "one";
  }
  function has(row, t) { return (row.traits || []).indexOf(t) >= 0; }
  function types(row) { return (row.types && row.types.length ? row.types : [row.type || ""]).map(String); }

  var POLE = /\b(glaive|naginata|fauchard|bill|guisarme|bardiche|halberd|scythe|switchscythe|rhomphaia|horsechopper|lucerne|bec de corbin|planson|ranseur|longaxe|longhammer|dorn dergar|ripsaw|skull ram|mancatcher|monk s spade|tepoztopilli)\b/;

  /* name → [head family, params] or null. Ordered: the first match wins. */
  var NAME_RULES = [
    [/\b(shield|buckler)\b/, function (r, z) { return ["plate", { v: "round", r: /heavy|war shield/.test(r.n) ? 0.34 : (/light|buckler/.test(r.n) ? 0.24 : 0.3), bulge: 0.05 }]; }],
    [/gauntlet|knuckle|cestus|madu|bracer|handwraps|helmet|kettle|fighting fan|pincher/, function () { return ["plate", { v: "knuckle", len: 0.18, width: 0.12, bulge: 0.04 }]; }],
    [/\b(net|lasso)\b|snag net/, function () { return ["mail", { len: 0.32, width: 0.24 }]; }],
    [/whip|lash|scarf|garrote|cat o nine|rope|urumi|bolas|cord\b/, function () { return ["haft", { v: "lash", r: 0.01 }]; }],
    [/crossbow|pelletbow|stonebow|gastraphetes/, function () { return ["haft", { v: "bow", len: 0.5, r: 0.016, bend: 0.1 }]; }],
    [/\bbow\b|longbow|shortbow|hornbow/, function (r) { return ["haft", { v: "bow", len: /long/.test(r.n) ? 1.2 : 0.9, r: 0.015, bend: 0.12 }]; }],
    [/pistol|musket|rifle|\bgun\b|shotgun|blunderbuss|culverin|pepperbox|cannon|bombard|repeater|revolver|hackbut|fire lance|mortar|machine|dragon|harvester|firedrake|firewyrm|hotchkiss/, function () { return ["haft", { v: "straight", len: 0.5, r: 0.014, over: 0.02 }]; }],
    [/arrow|bolt|dart|thorns\b|shaft/, function () { return ["spear", { len: 0.05, width: 0.02, tip: "point" }]; }],
    [/bullet|shot\b|pellet|cartridge|bomb|stones|balls?\b|keg|powder|grenade|flak|liquid ice|plague|payload|casing/, function () { return ["hammer", { v: "ball", k: 0.5 }]; }],
    [/\bram\b|battering/, function () { return ["hammer", { v: "maul", k: 1.4 }]; }],
    [/catapult|trebuchet|ballista|springal|ladder|tower|gallery|bridge|corvus|crushing wheel|manticore|earthmaul|aasen/, function () { return ["haft", { v: "beam", len: 0.8, r: 0.03 }]; }],
    [/\b(sling|atlatl|kestros|spear sling)\b/, function () { return ["plate", { v: "pouch", len: 0.12, width: 0.08, bulge: 0.02 }]; }],
    [/glaive|naginata|fauchard|\bbill\b|guisarme|scythe|rhomphaia|horsechopper|ripsaw/, function () { return ["blade.curved", { len: 0.42, width: 0.07, curve: 0.18, single: true, tip: "point" }]; }],
    [/bardiche|halberd|longaxe/, function (r) { return ["axe", { edge: /bardiche/.test(r.n) ? 0.3 : 0.2, depth: 0.16, beard: 0.6 }]; }],
    [/bec de corbin|lucerne|longhammer|skull ram|planson/, function (r) { return ["hammer", { v: /corbin|lucerne/.test(r.n) ? "pick" : "maul" }]; }],
    [/ranseur|trident|tiger fork|branched|sanpkhang|quadrens|kumade|mancatcher|monk s spade|lizard king/, function (r) { return ["spear", { len: 0.2, tines: /branched|tiger|mancatcher|spade/.test(r.n) ? 2 : 3 }]; }],
    [/\bpick\b|pickaxe|mattock/, function () { return ["hammer", { v: "pick" }]; }],
    [/mace|morningstar|knobkerrie|aspergillum|iron brush|flick/, function (r) { return ["hammer", { v: /morning|aspergillum|brush/.test(r.n) ? "star" : "mace" }]; }],
    [/flail|meteor|chain hammer|kusarigama|flindbar|nunchaku|sansetsukon|rope gauntlet|chain spear|spiked chain|poi/, function () { return ["hammer", { v: "ball", k: 0.9 }]; }],
    [/hammer|\bmaul\b|earth breaker/, function (r, z) { return ["hammer", { v: z === "two" ? "maul" : "hammer" }]; }],
    [/club|tetsubo|kanabo|\bsap\b|mere|wahaika|taiaha|baton|tonfa|dan bong|jutte|totem/, function () { return ["hammer", { v: "club" }]; }],
    [/staff|\bbo\b|hanbo|stick|crook|lantern/, function () { return ["haft", { v: "straight", len: 0.9, r: 0.02 }]; }],
    [/axe|cleaver|gandasa|urgrosh|chopper/, function (r, z) {
      return ["axe", { edge: z === "two" ? 0.26 : (z === "light" ? 0.11 : 0.17), depth: z === "two" ? 0.2 : 0.14,
                        beard: /hook|beard|dane|boarding|butcher/.test(r.n) ? 0.7 : 0.15, double: /double|twin|orc double/.test(r.n) }];
    }],
    [/spear|lance|pike|javelin|harpoon|doru|sibat|sarissa|gaff|ankus|tongi|stake|pilum|spiked armor/, function (r, z) {
      return ["spear", { len: /lance|pike|sarissa/.test(r.n) ? 0.2 : 0.26, width: 0.055 }];
    }],
    [/scimitar|falchion|sickle|kukri|katana|\bkama\b|khopesh|shotel|tulwar|sabre|saber|cutlass|nodachi|wakizashi|kerambit|falcata|seax|\bsica\b|hook|tamo|shang gou|curve|tailblade|dogslicer|terbutje|machete|double chicken|temple sword|kyoketsu|ogre hook/, function (r, z) {
      var n = r.n;
      var len = z === "two" ? 1.0 : (z === "light" ? 0.38 : 0.75);
      if (/sickle|kama|hook|tamo/.test(n)) return ["blade.curved", { len: 0.28, width: 0.04, curve: 0.55, single: true, tip: "point" }];
      if (/khopesh|shotel/.test(n)) return ["blade.curved", { len: 0.6, width: 0.05, curve: 0.38, single: true }];
      if (/kukri|seax|kerambit|falcata|machete|dogslicer/.test(n)) return ["blade.curved", { len: Math.min(len, 0.45), width: 0.06, curve: -0.08, single: true, taper: 1.1 }];
      if (/falchion|cutlass|terbutje/.test(n)) return ["blade.curved", { len: len, width: 0.07, curve: 0.08, single: true, taper: 1.05 }];
      if (/katana|nodachi|wakizashi/.test(n)) return ["blade.curved", { len: /wakizashi/.test(n) ? 0.5 : len, width: 0.034, curve: 0.05, single: true, tip: "chisel" }];
      return ["blade.curved", { len: len, width: 0.045, curve: 0.13, single: true }];
    }],
    [/sword|dagger|knife|rapier|estoc|blade|gladius|katar|razor|siangham|\bsai\b|piercer|manople|bich hwa|\bpata\b|kunai|starknife|scizore|\bklar\b|stiletto|dirk|bayonet|beard|flambard/, function (r, z) {
      var n = r.n, len = z === "two" ? 1.15 : (z === "light" ? 0.32 : 0.8);
      if (/rapier|estoc|sword cane|spiral/.test(n)) return ["blade.straight", { len: 0.88, width: 0.02, thick: 0.009, tip: "point", taper: 0.85 }];
      if (/bastard|flambard|seven branched/.test(n)) len = /bastard/.test(n) ? 0.92 : 1.1;
      if (/short sword|gladius|butterfly|nine ring|broadsword/.test(n)) len = /nine ring|broadsword/.test(n) ? 0.72 : 0.5;
      if (/sai|jutte|piercer|siangham|kunai|starknife|stiletto/.test(n)) return ["blade.straight", { len: 0.3, width: 0.018, thick: 0.012, tip: "point", taper: 0.6 }];
      return ["blade.straight", { len: len, width: z === "two" ? 0.06 : (z === "light" ? 0.035 : 0.05),
                                  tip: /flambard|wave/.test(n) ? "wave" : (/leaf/.test(n) ? "leaf" : "point") }];
    }]
  ];

  /* components.head words → family, for rows the names did not settle. */
  var HEAD_RULES = [
    [/axehead|twin axe|cleaver/, ["axe", { edge: 0.17, depth: 0.14 }]],
    [/pick/, ["hammer", { v: "pick" }]],
    [/hammer|maul|ram head|crushing/, ["hammer", { v: "hammer" }]],
    [/flanged|knob|bristled|studded/, ["hammer", { v: "mace" }]],
    [/weighted|striking|kettle|crown|baton/, ["hammer", { v: "club" }]],
    [/barrel/, ["haft", { v: "straight", len: 0.5, r: 0.014 }]],
    [/limbs|prod|bow arms/, ["haft", { v: "bow", len: 0.6, r: 0.016 }]],
    [/arrowhead|bolt head|metal point/, ["spear", { len: 0.05, width: 0.02, tip: "point" }]],
    [/bullet|shot|payload|casing|charge|balls/, ["hammer", { v: "ball", k: 0.5 }]],
    [/throwing arm|sling|pouch|cradle/, ["plate", { v: "pouch", len: 0.12, width: 0.08, bulge: 0.02 }]],
    [/weave|net/, ["mail", { len: 0.32, width: 0.24 }]],
    [/lash/, ["haft", { v: "lash", r: 0.01 }]],
    [/rim/, ["plate", { v: "round", r: 0.3, bulge: 0.05 }]],
    [/knuckle|spiked plate/, ["plate", { v: "knuckle", len: 0.18, width: 0.12, bulge: 0.04 }]],
    [/curved|hook|crescent/, ["blade.curved", { len: 0.5, width: 0.05, curve: 0.25, single: true }]],
    [/spearhead|point|tip|tines|prong|needle|trident/, ["spear", { len: 0.24 }]],
    [/blade|edge/, ["blade.straight", { len: 0.7, width: 0.05 }]]
  ];

  function headFor(row) {
    var r = { n: " " + String(row.name || row.id || "").toLowerCase().replace(/[^a-z0-9]+/g, " ") + " " };
    var z = sizeOf(row), i, m;
    for (i = 0; i < NAME_RULES.length; i++) {
      if (NAME_RULES[i][0].test(r.n)) { m = NAME_RULES[i][1](r, z); return { fam: m[0], p: m[1], by: "name" }; }
    }
    var head = String((row.components || {}).head || "").toLowerCase();
    for (i = 0; head && i < HEAD_RULES.length; i++) {
      if (HEAD_RULES[i][0].test(head)) return { fam: HEAD_RULES[i][1][0], p: HEAD_RULES[i][1][1], by: "head" };
    }
    var t = types(row);
    if (t.indexOf("slashing") >= 0) return { fam: "blade.straight", p: { len: z === "two" ? 1.1 : (z === "light" ? 0.35 : 0.75), width: 0.05 }, by: "type" };
    if (t.indexOf("piercing") >= 0) return { fam: "spear", p: { len: 0.24 }, by: "type" };
    if (t.indexOf("bludgeoning") >= 0) return { fam: "hammer", p: { v: z === "two" ? "maul" : "hammer" }, by: "type" };
    return { fam: "hammer", p: { v: "ball", k: 0.6 }, by: "type" };
  }

  /* The whole plan for a weapon row: what fills head, haft and fittings, and where. */
  function weaponPlan(row) {
    var h = headFor(row), z = sizeOf(row), n = " " + String(row.name || row.id || "").toLowerCase().replace(/[^a-z0-9]+/g, " ") + " ";
    var pole = POLE.test(n) || has(row, "reach") || /pole/i.test((row.components || {}).haft || "");
    var plan = { head: { fam: h.fam, p: h.p }, haft: null, fittings: null, by: h.by };
    var hl = pole ? 1.6 : (z === "two" ? 0.85 : (z === "light" ? 0.36 : 0.58));
    switch (h.fam) {
      case "blade.straight":
      case "blade.curved":
        if (pole || /\bkama\b|sickle|scythe|tamo|spider leg/.test(n)) {
          plan.haft = { fam: "haft", p: { len: /kama|sickle|tamo|spider/.test(n) ? 0.34 : hl, r: 0.02 } };
          plan.fittings = { fam: "guard", p: { v: "collar" } };
        } else {
          var gl = z === "two" ? 0.3 : (z === "light" ? 0.1 : 0.2);
          plan.haft = { fam: "grip", p: { len: gl, pommel: /katana|nodachi|wakizashi|tachi/.test(n) ? "none" : (z === "light" ? "ball" : "wheel") } };
          plan.fittings = { fam: "guard", p: { v: /katana|nodachi|wakizashi/.test(n) ? "disc" : (/rapier|spiral/.test(n) ? "basket" : (z === "light" ? "small" : "cross")),
                                               w: z === "two" ? 0.26 : 0.19 } };
        }
        break;
      case "axe":
      case "hammer":
        if (h.p.v === "ball" && !/flail|meteor|chain|kusarigama|nunchaku|sansetsukon|flindbar|poi/.test(n)) break;
        plan.haft = { fam: "haft", p: { len: h.p.v === "club" ? 0.3 : hl, r: h.p.v === "maul" ? 0.022 : 0.018 } };
        plan.fittings = h.p.v === "club" || h.p.v === "ball" ? { fam: "guard", p: { v: "cap" }, at: [-plan.haft.p.len, 0, 0] }
                                                            : { fam: "guard", p: { v: "collar" } };
        break;
      case "spear":
        if (h.p.len <= 0.06) { plan.haft = { fam: "haft", p: { len: 0.6, r: 0.005, over: 0 } }; break; }   // ammunition
        plan.haft = { fam: "haft", p: { len: pole || z === "two" ? 1.6 : 1.1, r: 0.017 } };
        plan.fittings = { fam: "guard", p: { v: "cap" }, at: [-plan.haft.p.len, 0, 0] };
        break;
      case "haft":
        if (h.p.v === "bow") {
          plan.haft = { fam: "grip", p: { len: 0.1, r: 0.02, pommel: "none" }, at: [0.05, 0, 0] };
          if (/crossbow|pelletbow|stonebow|gastraphetes/.test(n)) plan.fittings = { fam: "haft", p: { v: "beam", len: 0.5, r: 0.022, over: 0 }, at: [0, -0.02, -0.06], rot: [0, Math.PI / 2, 0] };
        } else if (h.p.v === "straight" && h.p.len === 0.5) {
          // A firearm: the barrel is the head, the stock the haft, the trigger guard the fitting.
          plan.haft = { fam: "haft", p: { v: "beam", len: 0.4, r: 0.022, over: 0 }, at: [-0.48, -0.01, 0] };
          plan.fittings = { fam: "guard", p: { v: "trigger" }, at: [-0.46, 0, 0] };
        }
        break;
      case "plate":
        if (h.p.v === "round") plan.fittings = { fam: "guard", p: { v: "boss" }, at: [0, h.p.bulge || 0.05, 0] };
        else if (h.p.v === "pouch") plan.haft = { fam: "haft", p: { v: "lash", r: 0.006 } };
        break;
      default:
        break;
    }
    return plan;
  }

  /* Armour and shields (rules/blacksmith.py's FORGED_ARMOUR and FORGED_SHIELDS). */
  function armourPlan(gear, row) {
    var n = String(row.name || row.id || "").toLowerCase();
    var body;
    if (gear === "shield") {
      body = /buckler/.test(n) ? { fam: "plate", p: { v: "round", r: 0.2, bulge: 0.04 } }
           : (/heavy|tower/.test(n) ? { fam: "plate", p: { v: "kite", len: 0.62, width: 0.42, bulge: 0.05 } }
                                    : { fam: "plate", p: { v: "round", r: 0.28, bulge: 0.05 } });
      return { body: body, fastenings: { fam: "guard", p: { v: "boss" }, at: body.p.v === "kite" ? [0.26, 0.05, 0] : [0, body.p.bulge, 0] }, lining: null };
    }
    if (/chain|mail\b|chainmail/.test(n) && !/scale|splint|banded/.test(n)) body = { fam: "mail", p: { len: 0.44, width: 0.28 } };
    else if (/scale|lamellar|brigandine/.test(n)) body = { fam: "scale", p: { len: 0.44, width: 0.3 } };
    else if (/splint/.test(n)) body = { fam: "scale", p: { v: "splint", len: 0.44, width: 0.3 } };
    else if (/banded|half plate|half-plate/.test(n)) body = { fam: "plate", p: { v: "banded", len: 0.5, width: 0.36, bulge: 0.08 } };
    else body = { fam: "plate", p: { v: "breast", len: 0.5, width: 0.38, bulge: 0.09 } };
    var span = body.p.len || 0.44;
    return { body: body, fastenings: { fam: "guard", p: { v: "buckle", span: span }, at: [span / 2, (body.p.bulge || 0.02) * 0.6, (body.p.width || 0.3) * 0.5] }, lining: null };
  }

  /* The plan for what is on the anvil. gear: "weapon" | "armour" | "shield" | ""; base: an id
     string or a table row. No gear and no base: a bar of the head's metal. */
  function planFor(gear, base) {
    if (!gear && !base) return { head: { fam: "plate", p: { v: "bar", len: 0.4, width: 0.05, thick: 0.035 } }, by: "bar" };
    var row = rowOf(base);
    if (gear === "armour" || gear === "shield") return armourPlan(gear, row);
    return weaponPlan(row);
  }

  F.families = { FAMILIES: FAMILIES, build: build, planFor: planFor, headFor: headFor, rowOf: rowOf };
})();
