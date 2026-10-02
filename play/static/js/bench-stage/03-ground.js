/* The herbalism bench's stage, part 3: the ground the kit unfolds on.
 *
 * The UI plan (§6.3) wanted CC0 photo textures from ambientCG or Poly Haven. This lane may
 * download nothing (contracts §0), so every floor is PAINTED here: tileable value noise for
 * the body of the ground, then canvas strokes for what lies on it (leaves, blades, pebbles,
 * planks). The result goes into a raw RGBA array rather than straight from the canvas,
 * because the alpha channel carries a GLOSS map (wet mud and varnished bar tops shine, leaf
 * litter does not) and a canvas would premultiply it into the colour.
 *
 * Tileable by construction: the noise lattice wraps at the texture's edge, and every stroke
 * near an edge is drawn again on the far side, so the floor repeats without a seam.
 *
 * Seeded, so the same biome paints the same floor every time the bench opens. Each floor is
 * painted once per session and cached (about 60-120ms at 512 pixels, measured in the
 * harness); 512 is under the plan's 1K ceiling and plenty at the stage's viewing angle.
 */
(function () {
  "use strict";
  var K = window.BenchStageKit = window.BenchStageKit || {};
  var M = K.math;
  var S = 512;

  function hash2(ix, iy, seed) {
    var h = (Math.imul(ix, 374761393) + Math.imul(iy, 668265263) + Math.imul(seed, 1442695041)) | 0;
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    h ^= h >>> 16;
    return (h >>> 0) / 4294967296;
  }
  function vnoise(x, y, px, py, seed) {
    var ix = Math.floor(x), iy = Math.floor(y), fx = x - ix, fy = y - iy;
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
    var x0 = ((ix % px) + px) % px, x1 = (x0 + 1) % px;
    var y0 = ((iy % py) + py) % py, y1 = (y0 + 1) % py;
    var a = hash2(x0, y0, seed), b = hash2(x1, y0, seed);
    var c = hash2(x0, y1, seed), d = hash2(x1, y1, seed);
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
  }
  /* u, v in 0..1; P lattice cells across at the first octave. Periodic at every octave. */
  function fbm(u, v, P, oct, seed) {
    var sum = 0, amp = 0.5, tot = 0;
    for (var o = 0; o < oct; o++) {
      var p = P << o;
      sum += vnoise(u * p, v * p, p, p, seed + o * 31) * amp;
      tot += amp; amp *= 0.5;
    }
    return sum / tot;
  }
  function mix(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
  function css(c, a) {
    return "rgba(" + Math.round(c[0]) + "," + Math.round(c[1]) + "," + Math.round(c[2]) + "," +
      (a === undefined ? 1 : a) + ")";
  }
  function jitter(c, r, k) { var f = 1 + (r() - 0.5) * k; return [c[0] * f, c[1] * f, c[2] * f]; }

  /* Draw a stroke, and again across any edge it is near, so the tile has no seam. */
  function wrap(x, y, rad, fn) {
    for (var dx = -1; dx <= 1; dx++) {
      for (var dy = -1; dy <= 1; dy++) {
        var X = x + dx * S, Y = y + dy * S;
        if (X + rad < 0 || X - rad > S || Y + rad < 0 || Y - rad > S) continue;
        fn(X, Y);
      }
    }
  }

  function baseFill(img, fn) {
    var d = img.data;
    for (var y = 0; y < S; y++) {
      for (var x = 0; x < S; x++) {
        var c = fn(x / S, y / S, x, y), i = (y * S + x) * 4;
        d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2]; d[i + 3] = 255;
      }
    }
  }

  function leafStroke(g, x, y, len, wid, ang, col, rib) {
    g.save();
    g.translate(x, y); g.rotate(ang);
    g.fillStyle = css(col);
    g.beginPath();
    g.moveTo(-len / 2, 0);
    g.quadraticCurveTo(0, -wid, len / 2, 0);
    g.quadraticCurveTo(0, wid, -len / 2, 0);
    g.fill();
    if (rib) {
      g.strokeStyle = css(rib, 0.55); g.lineWidth = 0.8;
      g.beginPath(); g.moveTo(-len / 2, 0); g.lineTo(len / 2 + 1.5, 0); g.stroke();
    }
    g.restore();
  }

  function blob(g, x, y, rx, ry, ang, col, a) {
    g.save(); g.translate(x, y); g.rotate(ang);
    g.fillStyle = css(col, a); g.beginPath(); g.ellipse(0, 0, rx, ry, 0, 0, Math.PI * 2); g.fill();
    g.restore();
  }

  function pebbles(g, r, n, cols, rmin, rmax) {
    for (var i = 0; i < n; i++) {
      var x = r() * S, y = r() * S, rx = rmin + r() * (rmax - rmin), ry = rx * (0.6 + r() * 0.4);
      var c = jitter(cols[Math.floor(r() * cols.length)], r, 0.3), ang = r() * Math.PI;
      wrap(x, y, rx + 2, function (X, Y) {
        blob(g, X + 1, Y + 1.2, rx, ry, ang, [20, 16, 12], 0.35);
        blob(g, X, Y, rx, ry, ang, c, 1);
        blob(g, X - rx * 0.25, Y - ry * 0.3, rx * 0.45, ry * 0.35, ang, mix(c, [255, 245, 225], 0.25), 0.6);
      });
    }
  }

  var PAINT = {
    forest: function (g, img, r) {
      baseFill(img, function (u, v) {
        var n = fbm(u, v, 8, 4, 1), m = fbm(u, v, 3, 2, 7);
        return mix(mix([30, 22, 16], [64, 46, 31], n), [52, 50, 30], m * 0.35);
      });
      g.putImageData(img, 0, 0);
      var pal = [[104, 66, 32], [128, 84, 38], [86, 52, 28], [150, 104, 48], [70, 58, 30],
                 [96, 90, 44], [60, 38, 22], [118, 72, 34]];
      for (var layer = 0; layer < 2; layer++) {
        var n = layer ? 900 : 700, dim = layer ? 1 : 0.62;
        for (var i = 0; i < n; i++) {
          var x = r() * S, y = r() * S, len = 7 + r() * 9, wid = len * (0.32 + r() * 0.16);
          var c = jitter(pal[Math.floor(r() * pal.length)], r, 0.35);
          c = [c[0] * dim, c[1] * dim, c[2] * dim];
          var ang = r() * Math.PI * 2, rib = [c[0] * 0.55, c[1] * 0.55, c[2] * 0.55];
          wrap(x, y, len, function (X, Y) { leafStroke(g, X, Y, len, wid, ang, c, rib); });
        }
      }
      g.lineCap = "round";
      for (var t = 0; t < 46; t++) {
        var tx = r() * S, ty = r() * S, tl = 14 + r() * 30, ta = r() * Math.PI * 2, tw = 1.2 + r() * 1.6;
        var tc = jitter([78, 60, 42], r, 0.4);
        wrap(tx, ty, tl, function (X, Y) {
          g.strokeStyle = css(tc); g.lineWidth = tw;
          g.beginPath(); g.moveTo(X, Y);
          g.quadraticCurveTo(X + Math.cos(ta) * tl * 0.5 + 4, Y + Math.sin(ta) * tl * 0.5 - 3,
                             X + Math.cos(ta) * tl, Y + Math.sin(ta) * tl);
          g.stroke();
        });
      }
    },
    mud: function (g, img, r) {
      baseFill(img, function (u, v) {
        var n = fbm(u, v, 6, 4, 3), w = fbm(u, v, 3, 3, 11);
        var f = fbm(u, v, 24, 3, 4);
        var c = mix([50, 38, 27], [90, 70, 47], n * 0.75 + f * 0.25);
        // Puddles: darker and wet, but not holes. Blended fully to near-black they read as
        // shadows of something that was not there (the first harness capture).
        if (w > 0.56) c = mix(c, [40, 34, 28], M.smooth(0.56, 0.64, w) * 0.6);
        return c;
      });
      g.putImageData(img, 0, 0);
      pebbles(g, r, 90, [[96, 86, 72], [70, 62, 52]], 1.5, 4.5);
      g.lineCap = "round";
      for (var i = 0; i < 700; i++) {
        var x = r() * S, y = r() * S, l = 5 + r() * 9, a = -Math.PI / 2 + (r() - 0.5) * 1.6;
        var c = jitter([62, 70, 34], r, 0.4);
        wrap(x, y, l, function (X, Y) {
          g.strokeStyle = css(c, 0.8); g.lineWidth = 1.1;
          g.beginPath(); g.moveTo(X, Y); g.lineTo(X + Math.cos(a) * l, Y + Math.sin(a) * l); g.stroke();
        });
      }
    },
    snow: function (g, img, r) {
      baseFill(img, function (u, v) {
        var n = fbm(u, v, 5, 4, 5);
        var c = mix([170, 182, 202], [238, 242, 248], M.smooth(0.25, 0.75, n));
        return c;
      });
      g.putImageData(img, 0, 0);
      for (var i = 0; i < 26; i++) {
        var x = r() * S, y = r() * S, rx = 18 + r() * 30, ang = r() * Math.PI;
        wrap(x, y, rx, function (X, Y) { blob(g, X, Y, rx, rx * 0.35, ang, [120, 140, 175], 0.07); });
      }
      pebbles(g, r, 9, [[70, 66, 62], [52, 48, 44]], 2, 5);
      g.lineCap = "round";
      for (var t = 0; t < 10; t++) {
        var tx = r() * S, ty = r() * S, tl = 10 + r() * 16, ta = r() * Math.PI * 2;
        wrap(tx, ty, tl, function (X, Y) {
          g.strokeStyle = "rgba(58,46,36,0.85)"; g.lineWidth = 1.4;
          g.beginPath(); g.moveTo(X, Y); g.lineTo(X + Math.cos(ta) * tl, Y + Math.sin(ta) * tl); g.stroke();
        });
      }
    },
    sand: function (g, img, r) {
      baseFill(img, function (u, v) {
        var n = fbm(u, v, 6, 4, 6), w = fbm(u, v, 4, 3, 5);
        var rip = Math.sin((v * 22 + w * 3.2 + u * 2) * Math.PI * 2) * 0.5 + 0.5;
        var c = mix([176, 148, 104], [214, 188, 142], n);
        return mix(c, [150, 122, 84], Math.pow(rip, 3) * 0.45);
      });
      g.putImageData(img, 0, 0);
      pebbles(g, r, 70, [[150, 128, 98], [124, 108, 88], [168, 150, 120]], 1.2, 3.2);
      pebbles(g, r, 5, [[132, 116, 96], [110, 98, 84]], 9, 18);
    },
    rock: function (g, img, r) {
      baseFill(img, function (u, v) {
        var n = fbm(u, v, 5, 5, 8), cr = Math.abs(fbm(u, v, 4, 3, 9) - 0.5);
        var lic = fbm(u, v, 6, 3, 13);
        var c = mix([74, 70, 64], [128, 122, 110], n);
        if (lic > 0.6) c = mix(c, [116, 120, 80], M.smooth(0.6, 0.7, lic) * 0.55);
        var g2 = fbm(u, v, 40, 2, 10);
        c = mix(c, [c[0] * 1.2, c[1] * 1.2, c[2] * 1.2], g2 - 0.5);
        if (cr < 0.006) c = mix(c, [46, 43, 40], (1 - cr / 0.006) * 0.7);
        return c;
      });
      g.putImageData(img, 0, 0);
      pebbles(g, r, 140, [[110, 104, 96], [86, 82, 76], [140, 132, 120]], 1, 3);
    },
    grass: function (g, img, r) {
      baseFill(img, function (u, v) {
        var n = fbm(u, v, 6, 4, 14);
        return mix([34, 38, 20], [60, 66, 32], n);
      });
      g.putImageData(img, 0, 0);
      var pal = [[74, 102, 40], [92, 122, 48], [60, 86, 34], [110, 128, 56], [128, 124, 62], [84, 96, 40]];
      g.lineCap = "round";
      for (var i = 0; i < 9000; i++) {
        var x = r() * S, y = r() * S, l = 4 + r() * 9, a = r() * Math.PI * 2;
        var c = jitter(pal[Math.floor(r() * pal.length)], r, 0.4), w = 0.9 + r() * 0.8;
        wrap(x, y, l, function (X, Y) {
          g.strokeStyle = css(c); g.lineWidth = w;
          g.beginPath(); g.moveTo(X, Y);
          g.quadraticCurveTo(X + Math.cos(a) * l * 0.5 + 1.5, Y + Math.sin(a) * l * 0.5,
                             X + Math.cos(a) * l, Y + Math.sin(a) * l);
          g.stroke();
        });
      }
      for (var f = 0; f < 34; f++) {
        var fx = r() * S, fy = r() * S, fc = r() < 0.5 ? [206, 192, 120] : [168, 150, 188];
        wrap(fx, fy, 3, function (X, Y) { blob(g, X, Y, 1.6, 1.6, 0, fc, 0.9); });
      }
    },
    earth: function (g, img, r) {
      baseFill(img, function (u, v) {
        var n = fbm(u, v, 7, 4, 15), w = fbm(u, v, 3, 2, 16);
        var c = mix([84, 66, 48], [120, 98, 74], n);
        var rut = Math.min(Math.abs(v - 0.3 - (w - 0.5) * 0.1), Math.abs(v - 0.72 - (w - 0.5) * 0.1));
        if (rut < 0.05) c = mix(c, [64, 50, 38], (1 - rut / 0.05) * 0.5);
        return c;
      });
      g.putImageData(img, 0, 0);
      pebbles(g, r, 600, [[128, 112, 92], [72, 62, 50], [150, 132, 108]], 0.8, 2.6);
      pebbles(g, r, 14, [[110, 100, 86], [92, 84, 74]], 5, 9);
    },
    planks: function (g, img, r) { boards(g, img, r, 5, [[126, 86, 52], [116, 78, 46], [134, 94, 58],
      [108, 72, 44], [122, 84, 50]], false); },
    bar: function (g, img, r) { boards(g, img, r, 3, [[88, 48, 28], [80, 44, 26], [94, 54, 32]], true); }
  };

  /* Boards run along u. Grain is long noise plus a wavering stripe; seams and staggered
     end joints are what make planks read as planks rather than as stripes. */
  function boards(g, img, r, n, tints, polished) {
    var bh = S / n, seamX = [];
    for (var b = 0; b < n; b++) seamX.push(Math.floor(r() * S));
    baseFill(img, function (u, v, x, y) {
      var bi = Math.floor(y / bh), t = tints[bi % tints.length];
      var gr = vnoise(u * 6, v * 120, 6, 120, 40 + bi);
      var wob = vnoise(u * 5, v * 24, 5, 24, 60 + bi) * 18;
      var st = Math.sin((y + wob) * 0.85) * 0.5 + 0.5;
      var k = 0.8 + 0.18 * gr + 0.1 * st;
      if (polished) k *= 0.92 + 0.16 * fbm(u, v, 2, 2, 70);
      return [t[0] * k, t[1] * k, t[2] * k];
    });
    g.putImageData(img, 0, 0);
    g.fillStyle = "rgba(20,12,8,0.85)";
    for (var i = 0; i < n; i++) {
      g.fillRect(0, Math.round(i * bh) - 1, S, 2);
      g.fillRect(seamX[i], Math.round(i * bh), 2, Math.round(bh));
      g.fillStyle = "rgba(24,18,14,0.9)";
      [0.2, 0.8].forEach(function (f) {
        blob(g, seamX[i] - 7, i * bh + bh * f, 1.6, 1.6, 0, [30, 26, 24], 0.9);
        blob(g, (seamX[i] + 9) % S, i * bh + bh * f, 1.6, 1.6, 0, [30, 26, 24], 0.9);
      });
      g.fillStyle = "rgba(20,12,8,0.85)";
    }
    for (var k = 0; k < (polished ? 3 : 6); k++) {
      var kx = r() * S, ky = r() * S, kr = 4 + r() * 6;
      wrap(kx, ky, kr * 3, function (X, Y) {
        for (var q = 3; q >= 1; q--) blob(g, X, Y, kr * q * 0.9, kr * q * 0.45, 0, [50, 30, 18], 0.18);
        blob(g, X, Y, kr * 0.6, kr * 0.4, 0, [42, 24, 14], 0.85);
      });
    }
    if (polished) {
      for (var s = 0; s < 6; s++) {
        var sx = r() * S, sy = r() * S, sr = 14 + r() * 10;
        wrap(sx, sy, sr + 3, function (X, Y) {
          g.strokeStyle = "rgba(36,18,10,0.28)"; g.lineWidth = 2.2;
          g.beginPath(); g.arc(X, Y, sr, 0, Math.PI * 2); g.stroke();
        });
      }
    }
  }

  /* Gloss per texel, 0..255, into the alpha channel. */
  var GLOSS = {
    forest: function (u, v, lum) { return 30 + lum * 50; },
    mud: function (u, v) { var w = fbm(u, v, 3, 3, 11); return w > 0.56 ? 235 : 80; },
    snow: function (u, v, lum, rnd) { return rnd < 0.006 ? 255 : 90; },
    sand: function () { return 26; },
    rock: function (u, v, lum) { return 30 + lum * 50; },
    grass: function (u, v, lum) { return 40 + lum * 60; },
    earth: function () { return 30; },
    planks: function (u, v, lum) { return 60 + lum * 80; },
    bar: function (u, v, lum) { return 150 + lum * 105; }
  };

  /* How each floor is lit: specular strength and tightness, and its scale in the world (one
     texture repeat per this many units; the tool is about 1.4 units across). */
  var LOOK = {
    forest: { spec: 0.35, shin: 14, tile: 2.6 },
    mud: { spec: 1.1, shin: 48, tile: 3.0 },
    snow: { spec: 0.6, shin: 70, tile: 4.0 },
    sand: { spec: 0.2, shin: 10, tile: 3.0 },
    rock: { spec: 0.35, shin: 18, tile: 3.2 },
    grass: { spec: 0.25, shin: 12, tile: 2.0 },
    earth: { spec: 0.2, shin: 12, tile: 2.8 },
    planks: { spec: 0.5, shin: 26, tile: 3.4 },
    bar: { spec: 1.0, shin: 64, tile: 3.8 }
  };

  var SEED = { forest: 11, mud: 12, snow: 13, sand: 14, rock: 15, grass: 16, earth: 17,
               planks: 18, bar: 19 };
  var cache = {};
  var nextTex = 1;

  function paint(kind) {
    if (cache[kind]) return cache[kind];
    var t0 = (window.performance ? performance.now() : 0);
    var c = document.createElement("canvas");
    c.width = c.height = S;
    var g = c.getContext("2d");
    var img = g.createImageData(S, S);
    var r = M.rng(SEED[kind] * 7919);
    PAINT[kind](g, img, r);
    var px = g.getImageData(0, 0, S, S).data;
    var data = new Uint8Array(S * S * 4), gl = GLOSS[kind], gr = M.rng(SEED[kind] * 104729);
    for (var y = 0; y < S; y++) {
      for (var x = 0; x < S; x++) {
        var i = (y * S + x) * 4;
        data[i] = px[i]; data[i + 1] = px[i + 1]; data[i + 2] = px[i + 2];
        var lum = (px[i] + px[i + 1] + px[i + 2]) / 765;
        data[i + 3] = Math.max(0, Math.min(255, gl(x / S, y / S, lum, gr())));
      }
    }
    var look = LOOK[kind];
    var rec = { id: nextTex++, kind: kind, size: S, data: data, look: look,
                ms: (window.performance ? performance.now() : 0) - t0 };
    cache[kind] = rec;
    return rec;
  }

  /* The scene's place, read as a floor. Biome words are rules/biomes.py's canonical set.
     A roof wins over the biome (indoors is a table, whatever the region outside is), and
     a tavern is the bar top. Anything unknown is packed earth: neutral, and never a lie
     about water or snow that is not there. */
  function kindFor(g) {
    g = g || {};
    var biome = String(g.biome || "").toLowerCase(), place = String(g.place || "").toLowerCase();
    if (biome === "tavern" || (g.roofed && /tavern|inn\b|alehouse|taproom|bar\b/.test(place))) return "bar";
    if (g.roofed || biome === "indoors" || biome === "deck") return "planks";
    var map = { forest: "forest", jungle: "forest", swamp: "mud", water: "mud", tundra: "snow",
                desert: "sand", coast: "sand", mountain: "rock", hills: "rock",
                underground: "rock", ruins: "rock", planar: "rock", grassland: "grass",
                farmland: "grass", urban: "earth", road: "earth" };
    return map[biome] || "earth";
  }

  K.ground = { paint: paint, kindFor: kindFor, kinds: Object.keys(PAINT), size: S };
})();
