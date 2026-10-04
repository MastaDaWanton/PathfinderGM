/* The forge's stage, part 3: the smithy room.
 *
 * UI plan §6.3: the field kit stands on the biome ground (bench-stage/03-ground.js, reused as
 * is); a smithy has its own floor: STONE FLAGS for a town smithy, PACKED EARTH WITH A PLANK
 * FLOOR for a founded one (proposed), and a back wall with the furnace mouth in it. The plan
 * named CC0 photo textures; this lane may download nothing, so, as 03-ground.js did for the
 * herb bench, every surface is PAINTED: tileable value noise for the body, canvas strokes for
 * joints and boards, a gloss map in the alpha channel (worn flags shine where boots go, soot
 * does not).
 *
 * The texture records have the same shape as 03-ground's ({id, kind, size, data, look}) so the
 * herb renderer uploads them unchanged. Their ids start at 9001, far from 03-ground's own
 * counter: the renderer keys textures by id, and two floors sharing an id would share a
 * texture.
 *
 * Painted once per session and cached, seeded, so the same smithy looks the same every time.
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var F = window.ForgeStageKit = window.ForgeStageKit || {};
  var G = K.mesh, M = K.math, P = F.props;
  if (!G || !M || !P) return;

  function hash2(ix, iy, seed) {
    var h = (Math.imul(ix, 374761393) + Math.imul(iy, 668265263) + Math.imul(seed, 1442695041)) | 0;
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    h ^= h >>> 16;
    return (h >>> 0) / 4294967296;
  }
  function vnoise(x, y, p, seed) {
    var ix = Math.floor(x), iy = Math.floor(y), fx = x - ix, fy = y - iy;
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
    var x0 = ((ix % p) + p) % p, x1 = (x0 + 1) % p, y0 = ((iy % p) + p) % p, y1 = (y0 + 1) % p;
    var a = hash2(x0, y0, seed), b = hash2(x1, y0, seed), c = hash2(x0, y1, seed), d = hash2(x1, y1, seed);
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
  }
  /* Periodic at every octave, so the tile has no seam. */
  function fbm(u, v, P0, oct, seed) {
    var sum = 0, amp = 0.5, tot = 0;
    for (var o = 0; o < oct; o++) {
      var p = P0 << o;
      sum += vnoise(u * p, v * p, p, seed + o * 31) * amp;
      tot += amp; amp *= 0.5;
    }
    return sum / tot;
  }
  function mix(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }

  /* Each painter fills rgb and gloss per texel from (u, v) in [0, 1). */
  var PAINT = {
    /* Stone flags: irregular rectangles in staggered courses, each flag its own tint, with
       dark mortar joints, a little soot drift and boot-worn shine in the middle of each. */
    flags: function (u, v, r) {
      var rows = 4, row = Math.floor(v * rows), fv = v * rows - row;
      var off = hash2(row, 0, 5) * 0.5, cols = 3;
      var cu = (u + off) * cols, col = Math.floor(cu), fu = cu - col;
      col = ((col % cols) + cols) % cols;
      var t = hash2(col, row, 9), t2 = hash2(col, row, 13);
      var base = mix([78, 74, 68], [112, 104, 92], t);
      base = mix(base, [92, 84, 70], t2 * 0.4);
      var n = fbm(u, v, 8, 4, 3), fine = fbm(u, v, 64, 2, 4);
      var c = mix(base, [base[0] * 1.15, base[1] * 1.15, base[2] * 1.15], n - 0.4);
      c = mix(c, [c[0] * 0.85, c[1] * 0.85, c[2] * 0.85], fine);
      var jw = 0.018 + 0.01 * vnoise(u * 40, v * 40, 40, 7);
      var edge = Math.min(fu, 1 - fu) / cols * 3, edgeV = Math.min(fv, 1 - fv) / rows * 3;
      var j = Math.min(edge, edgeV);
      var gloss = 40 + 70 * Math.max(0, 1 - Math.abs(fv - 0.5) * 2.2) * (1 - fine);
      if (j < jw) { c = mix([34, 30, 26], c, j / jw * 0.5); gloss = 10; }
      var soot = fbm(u, v, 3, 3, 21);
      if (soot > 0.55) c = mix(c, [40, 36, 32], (soot - 0.55) * 1.2);
      return [c, gloss];
    },
    /* Packed earth under worn boards: planks run along u, earth shows in the gaps and where
       boards have gone. */
    owned: function (u, v) {
      var earth = mix([70, 54, 38], [104, 84, 60], fbm(u, v, 7, 4, 15));
      var n = 6, bi = Math.floor(v * n), fv = v * n - bi;
      var missing = hash2(bi, 3, 2) < 0.18;
      var seamU = hash2(bi, 1, 4), fu = (u - seamU + 1) % 1;
      var tint = mix([110, 76, 46], [134, 94, 58], hash2(bi, 2, 6));
      var grain = vnoise(u * 6, v * 120, 6, 40 + bi) * 0.18 + 0.82;
      var wob = Math.sin((v * 512 + vnoise(u * 5, v * 24, 5, 60 + bi) * 18) * 0.85) * 0.05;
      var c = [tint[0] * (grain + wob), tint[1] * (grain + wob), tint[2] * (grain + wob)];
      var gap = fv < 0.04 || fv > 0.96 || fu < 0.004;
      if (missing || gap) return [mix(earth, [40, 32, 24], gap ? 0.4 : 0), 26];
      var dirt = fbm(u, v, 5, 3, 19);
      if (dirt > 0.6) c = mix(c, earth, (dirt - 0.6) * 1.6);
      return [c, 60 + 40 * grain];
    },
    /* The town smithy's wall: rough coursed stone, sooted toward the top. */
    stonewall: function (u, v) {
      var rows = 8, row = Math.floor(v * rows), fv = v * rows - row;
      var cu = (u + hash2(row, 0, 3) * 0.5) * 5, col = Math.floor(cu), fu = cu - col;
      var t = hash2(((col % 5) + 5) % 5, row, 11);
      var c = mix([70, 64, 56], [104, 96, 84], t);
      c = mix(c, [c[0] * 1.2, c[1] * 1.2, c[2] * 1.2], fbm(u, v, 16, 3, 2) - 0.45);
      var j = Math.min(Math.min(fu, 1 - fu) / 5, Math.min(fv, 1 - fv) / rows) * 8;
      if (j < 0.05) c = mix([30, 27, 24], c, j / 0.05 * 0.6);
      return [c, 20];
    },
    /* A founded smithy's wall: vertical timber boards. */
    timber: function (u, v) {
      var n = 7, bi = Math.floor(u * n), fu = u * n - bi;
      var tint = mix([74, 50, 32], [96, 66, 42], hash2(bi, 5, 8));
      var g = vnoise(u * 120, v * 6, 120, 30 + bi) * 0.22 + 0.8;
      var c = [tint[0] * g, tint[1] * g, tint[2] * g];
      if (fu < 0.03 || fu > 0.97) c = [26, 18, 12];
      return [c, 30];
    }
  };
  var LOOK = {
    flags: { spec: 0.6, shin: 30, tile: 2.0 },
    owned: { spec: 0.4, shin: 22, tile: 3.4 },
    stonewall: { spec: 0.15, shin: 12, tile: 3.0 },
    timber: { spec: 0.25, shin: 14, tile: 3.0 }
  };
  var SIZE = { flags: 512, owned: 512, stonewall: 256, timber: 256 };
  var SEED = { flags: 31, owned: 32, stonewall: 33, timber: 34 };
  var cache = {}, nextTex = 9001;

  function paint(kind) {
    if (cache[kind]) return cache[kind];
    var t0 = window.performance ? performance.now() : 0, S = SIZE[kind], fn = PAINT[kind];
    var data = new Uint8Array(S * S * 4), r = M.rng(SEED[kind] * 7919);
    for (var y = 0; y < S; y++) {
      for (var x = 0; x < S; x++) {
        var px = fn(x / S, y / S, r), c = px[0], i = (y * S + x) * 4;
        data[i] = Math.max(0, Math.min(255, c[0]));
        data[i + 1] = Math.max(0, Math.min(255, c[1]));
        data[i + 2] = Math.max(0, Math.min(255, c[2]));
        data[i + 3] = Math.max(0, Math.min(255, px[1]));
      }
    }
    var rec = { id: nextTex++, kind: kind, size: S, data: data, look: LOOK[kind],
                ms: (window.performance ? performance.now() : 0) - t0 };
    cache[kind] = rec;
    return rec;
  }

  function surface(rec, extra) {
    var k = 1 / rec.look.tile;
    var o = { color: [1, 1, 1], pattern: 0, tex: rec, uvScale: [k, k], ground: 1, spec: rec.look.spec, shin: rec.look.shin };
    if (extra) for (var a in extra) o[a] = extra[a];
    return P.mat("stone", o);
  }

  /* The room: floor and back wall, both fading into the page's dark through the ground flag
     (the herb shader's distance fade and vignette), so no edge of the room ever shows. */
  function room(kind) {
    var owned = kind === "owned";
    var floorRec = paint(owned ? "owned" : "flags"), wallRec = paint(owned ? "timber" : "stonewall");
    var g = P.group();
    g.floor = P.add(g, P.node(G.plane(40), surface(floorRec), { glint: false }));
    // The wall: a plane stood up (its +y normal turned to face the camera), 8 units square.
    g.wall = P.add(g, P.node(G.plane(8), surface(wallRec, { color: [0.85, 0.82, 0.78] }),
                             { pos: [0, 4, -1.45], rot: [Math.PI / 2, 0, 0], glint: false }));
    g.recs = [floorRec, wallRec];
    return g;
  }

  F.smithy = { paint: paint, room: room, kinds: Object.keys(PAINT) };
})();
