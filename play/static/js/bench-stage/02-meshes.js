/* The herbalism bench's stage, part 2: meshes built from primitives.
 *
 * The revamp plan (§10) settled it: "the vessels are low-poly and built in code (lathe a
 * mortar, extrude a rack)". A mortar, a bowl, a pot, a crock, a jar and a bottle are all
 * surfaces of revolution, so one lathe builder makes most of the kit; boxes, rings, discs
 * and a bent leaf card make the rest.
 *
 * THE LATHE'S NORMALS come from the profile, not from the triangles: the profile's own
 * tangent, turned a quarter, is the surface normal in the (radius, height) plane, and the
 * sweep carries it round. Neighbouring segments share a smoothed normal unless they meet
 * at more than the crease angle, so a mortar's curved belly reads round while its lip
 * keeps a sharp edge. Profiles are written outside-up, over the lip, inside-down, and that
 * order is what makes every normal point out of the material.
 *
 * Every mesh is {id, pos, nrm, uv, idx} with Float32/Uint16 arrays kept on the CPU, which
 * is what lets the renderer rebuild everything after a lost context (01-gl.js).
 */
(function () {
  "use strict";
  var K = window.BenchStageKit = window.BenchStageKit || {};
  var M = K.math;
  var nextId = 1;

  function finish(pos, nrm, uv, idx) {
    return { id: nextId++, pos: new Float32Array(pos), nrm: new Float32Array(nrm),
             uv: new Float32Array(uv), idx: new Uint16Array(idx), bounds: bounds(pos) };
  }

  function bounds(pos) {
    var lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (var i = 0; i < pos.length; i += 3) {
      for (var k = 0; k < 3; k++) {
        if (pos[i + k] < lo[k]) lo[k] = pos[i + k];
        if (pos[i + k] > hi[k]) hi[k] = pos[i + k];
      }
    }
    return { lo: lo, hi: hi };
  }

  /* profile: [[r, y], ...]; seg: steps round; crease: degrees. */
  function lathe(profile, seg, crease) {
    seg = seg || 32;
    var cosC = Math.cos((crease === undefined ? 40 : crease) * Math.PI / 180);
    var n = profile.length, segN = [];
    for (var i = 0; i < n - 1; i++) {
      var dr = profile[i + 1][0] - profile[i][0], dy = profile[i + 1][1] - profile[i][1];
      var l = Math.sqrt(dr * dr + dy * dy);
      segN.push(l > 1e-6 ? [dy / l, -dr / l] : null);
    }
    function vnorm(v, s) {
      var a = segN[v - 1] || null, b = segN[v] || null;
      if (!a) return b || segN[s];
      if (!b) return a;
      if (a[0] * b[0] + a[1] * b[1] >= cosC) {
        var x = a[0] + b[0], y = a[1] + b[1], ll = Math.sqrt(x * x + y * y) || 1;
        return [x / ll, y / ll];
      }
      return segN[s];
    }
    // Arc length down the profile, for a v coordinate that does not stretch.
    var acc = [0];
    for (var q = 1; q < n; q++) {
      var ddr = profile[q][0] - profile[q - 1][0], ddy = profile[q][1] - profile[q - 1][1];
      acc.push(acc[q - 1] + Math.sqrt(ddr * ddr + ddy * ddy));
    }
    var total = acc[n - 1] || 1;
    var pos = [], nrm = [], uv = [], idx = [];
    for (var s = 0; s < n - 1; s++) {
      if (!segN[s]) continue;
      var nA = vnorm(s, s), nB = vnorm(s + 1, s);
      var base = pos.length / 3;
      for (var j = 0; j <= seg; j++) {
        var th = j / seg * Math.PI * 2, c = Math.cos(th), sn = Math.sin(th);
        var pa = profile[s], pb = profile[s + 1];
        pos.push(pa[0] * c, pa[1], pa[0] * sn, pb[0] * c, pb[1], pb[0] * sn);
        nrm.push(nA[0] * c, nA[1], nA[0] * sn, nB[0] * c, nB[1], nB[0] * sn);
        uv.push(j / seg, acc[s] / total, j / seg, acc[s + 1] / total);
      }
      for (var k = 0; k < seg; k++) {
        var a0 = base + 2 * k;
        idx.push(a0, a0 + 1, a0 + 2, a0 + 2, a0 + 1, a0 + 3);
      }
    }
    return finish(pos, nrm, uv, idx);
  }

  function cylinder(r, h, seg, r2) {
    var t = r2 === undefined ? r : r2;
    return lathe([[0, 0], [r, 0], [t, h], [0, h]], seg || 24, 30);
  }

  function sphere(r, seg, rings) {
    rings = rings || 12;
    var prof = [];
    for (var i = 0; i <= rings; i++) {
      var a = i / rings * Math.PI;
      prof.push([Math.sin(a) * r, -Math.cos(a) * r]);
    }
    return lathe(prof, seg || 20, 90);
  }

  /* A capsule standing on y = 0, for fingers, handles and tongs' ends. */
  function capsule(r, len, seg) {
    var prof = [], i, a;
    for (i = 0; i <= 5; i++) { a = i / 5 * Math.PI / 2; prof.push([Math.sin(a) * r, r - Math.cos(a) * r]); }
    for (i = 0; i <= 5; i++) { a = i / 5 * Math.PI / 2; prof.push([Math.cos(a) * r, len - r + Math.sin(a) * r]); }
    return lathe(prof, seg || 12, 90);
  }

  function box(w, h, d) {
    var x = w / 2, y = h / 2, z = d / 2;
    var F = [
      [[1, 0, 0], [[x, -y, -z], [x, y, -z], [x, y, z], [x, -y, z]]],
      [[-1, 0, 0], [[-x, -y, z], [-x, y, z], [-x, y, -z], [-x, -y, -z]]],
      [[0, 1, 0], [[-x, y, -z], [-x, y, z], [x, y, z], [x, y, -z]]],
      [[0, -1, 0], [[-x, -y, z], [-x, -y, -z], [x, -y, -z], [x, -y, z]]],
      [[0, 0, 1], [[-x, -y, z], [x, -y, z], [x, y, z], [-x, y, z]]],
      [[0, 0, -1], [[x, -y, -z], [-x, -y, -z], [-x, y, -z], [x, y, -z]]]
    ];
    var pos = [], nrm = [], uv = [], idx = [];
    F.forEach(function (f) {
      var b = pos.length / 3;
      f[1].forEach(function (p, i) {
        pos.push(p[0], p[1], p[2]);
        nrm.push(f[0][0], f[0][1], f[0][2]);
        uv.push(i === 1 || i === 2 ? 1 : 0, i >= 2 ? 1 : 0);
      });
      idx.push(b, b + 1, b + 2, b, b + 2, b + 3);
    });
    return finish(pos, nrm, uv, idx);
  }

  /* A ring lying flat in XZ, built ANGLE-MAJOR: every step round adds one contiguous run of
     6 * sides indices, so drawing [step0 * per, steps * per] draws just that stretch of
     arc. That is how a dial band, a closing ring of light and a scored mark are one mesh. */
  function ring(R, r, seg, sides) {
    seg = seg || 64; sides = sides || 8;
    var pos = [], nrm = [], uv = [], idx = [];
    for (var j = 0; j <= seg; j++) {
      var th = j / seg * Math.PI * 2, c = Math.cos(th), s = Math.sin(th);
      for (var k = 0; k < sides; k++) {
        var ph = k / sides * Math.PI * 2, cp = Math.cos(ph), sp = Math.sin(ph);
        var rr = R + r * cp;
        pos.push(rr * c, r * sp, rr * s);
        nrm.push(cp * c, sp, cp * s);
        uv.push(j / seg, k / sides);
      }
    }
    for (var a = 0; a < seg; a++) {
      for (var b = 0; b < sides; b++) {
        var i0 = a * sides + b, i1 = a * sides + (b + 1) % sides;
        var j0 = i0 + sides, j1 = i1 + sides;
        idx.push(i0, j0, i1, i1, j0, j1);
      }
    }
    var m = finish(pos, nrm, uv, idx);
    m.seg = seg; m.per = sides * 6;
    return m;
  }

  /* [first, count] for the arc between two angles (radians, counter-clockwise from +x in
     the ring's own plane). Returns one or two ranges, because an arc may cross zero. */
  function arcRanges(m, a0, a1) {
    var TAU = Math.PI * 2;
    if (a1 < a0) { var t = a0; a0 = a1; a1 = t; }
    var span = a1 - a0;
    if (span >= TAU) return [[0, m.seg * m.per]];
    a0 = ((a0 % TAU) + TAU) % TAU;
    a1 = a0 + span;
    var s0 = Math.floor(a0 / TAU * m.seg), s1 = Math.ceil(a1 / TAU * m.seg);
    if (s1 <= m.seg) return [[s0 * m.per, Math.max(1, s1 - s0) * m.per]];
    return [[s0 * m.per, (m.seg - s0) * m.per], [0, (s1 - m.seg) * m.per]];
  }

  /* A flat disc in XZ with radial uv (centre 0, rim length 1), for shadows, glows,
     liquid surfaces and the ground's ash bed. */
  function disc(r, seg) {
    seg = seg || 40;
    var pos = [0, 0, 0], nrm = [0, 1, 0], uv = [0, 0], idx = [];
    for (var j = 0; j <= seg; j++) {
      var th = j / seg * Math.PI * 2, c = Math.cos(th), s = Math.sin(th);
      pos.push(r * c, 0, r * s); nrm.push(0, 1, 0); uv.push(c, s);
    }
    for (var k = 1; k <= seg; k++) idx.push(0, k + 1, k);
    return finish(pos, nrm, uv, idx);
  }

  /* The ground: a square in XZ with uv in world units, so the texture's scale is set by
     the material's uvScale rather than by the plane's size. */
  function plane(size) {
    var h = size / 2;
    return finish([-h, 0, -h, h, 0, -h, h, 0, h, -h, 0, h], [0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0],
                  [-h, -h, h, -h, h, h, -h, h], [0, 2, 1, 0, 3, 2]);
  }

  /* A leaf card hanging along -y, bent along its length and cupped across it; for drying
     bundles, leaf chips and the jar's steeping herbs. */
  function leaf(len, wid, bend) {
    var rows = 6, cols = 2, pos = [], nrm = [], uv = [], idx = [];
    bend = bend === undefined ? 0.25 : bend;
    for (var i = 0; i <= rows; i++) {
      var t = i / rows, w = Math.sin(Math.PI * Math.min(1, t * 1.08)) * wid / 2 + 0.002;
      for (var j = 0; j <= cols; j++) {
        var u = j / cols * 2 - 1;
        var x = u * w, z = bend * t * t * len + Math.abs(u) * w * 0.35, y = -t * len;
        pos.push(x, y, z);
        var nz = 1, nx = -u * 0.35;
        var l = Math.sqrt(nx * nx + nz * nz);
        nrm.push(nx / l, 0.3 * t, nz / l);
        uv.push(j / cols, t);
      }
    }
    for (var a = 0; a < rows; a++) {
      for (var b = 0; b < cols; b++) {
        var i0 = a * (cols + 1) + b;
        idx.push(i0, i0 + cols + 1, i0 + 1, i0 + 1, i0 + cols + 1, i0 + cols + 2);
      }
    }
    return finish(pos, nrm, uv, idx);
  }

  /* Several meshes welded into one, each placed by a matrix, for static clusters (stones
     round a fire, logs, a glove's fingers) that would otherwise be a draw call apiece. */
  function merge(parts) {
    var pos = [], nrm = [], uv = [], idx = [];
    parts.forEach(function (p) {
      var m = p.m, mesh = p.mesh, base = pos.length / 3, nm = M.normalMat(m);
      for (var i = 0; i < mesh.pos.length; i += 3) {
        var w = M.xform(m, [mesh.pos[i], mesh.pos[i + 1], mesh.pos[i + 2]]);
        pos.push(w[0], w[1], w[2]);
        var nx = mesh.nrm[i], ny = mesh.nrm[i + 1], nz = mesh.nrm[i + 2];
        var v = M.norm([nm[0] * nx + nm[3] * ny + nm[6] * nz, nm[1] * nx + nm[4] * ny + nm[7] * nz,
                        nm[2] * nx + nm[5] * ny + nm[8] * nz]);
        nrm.push(v[0], v[1], v[2]);
      }
      for (var u = 0; u < mesh.uv.length; u++) uv.push(mesh.uv[u]);
      for (var k = 0; k < mesh.idx.length; k++) idx.push(mesh.idx[k] + base);
    });
    return finish(pos, nrm, uv, idx);
  }

  /* Radius of a lathe profile at height y, read off its outside or inside wall, so a
     liquid surface or a scored mark meets the wall it sits against. */
  function radiusAt(profile, y, inside) {
    var best = null;
    for (var i = 0; i < profile.length - 1; i++) {
      var a = profile[i], b = profile[i + 1];
      if ((y - a[1]) * (y - b[1]) > 0 || a[1] === b[1]) continue;
      var r = a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]);
      if (best === null || (inside ? r < best : r > best)) best = r;
    }
    return best === null ? 0 : best;
  }

  K.mesh = { lathe: lathe, cylinder: cylinder, sphere: sphere, capsule: capsule, box: box,
             ring: ring, arcRanges: arcRanges, disc: disc, plane: plane, leaf: leaf,
             merge: merge, radiusAt: radiusAt };
})();
