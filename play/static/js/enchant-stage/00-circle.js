/* The enchanting bench's stage, part 0: the circle of chalk and inks.
 *
 * The owner's ruling (enchanting answers, round 3): "the item on a circle of chalk and inks, lit
 * by candles and the essence's glow". The circle is the ritual's progress, drawn, not a meter
 * (UI plan §7.2): Prepare draws the rings and cuts the sigils one by one, Attune lights each
 * seat's mark in its essence's colour, Unbind and Cleanse unpick sigils last-cut first.
 *
 * TWO LAYERS, because they change at different rates:
 *
 *   DUST. The old chalk under every circle: smudged rings from earlier workings, a scatter of
 *   chalk dust, two ink stains and salt grains. It never changes, so it is PAINTED once into a
 *   texture the way bench-stage/03-ground.js paints a ground (value noise and canvas strokes,
 *   seeded, cached for the session) and laid on the floor as one quad. It is drawn ADDITIVE and
 *   lit: the house shader takes its alpha from the material, never from the texture (01-gl.js
 *   uses the texture's alpha as gloss), so black texels add nothing and chalk-white ones lighten
 *   whatever floor is under them, a biome at camp or a sanctum's flags, with the candles on it.
 *
 *   LINES. The working's own circle: three rings, an eight-point figure and the quarter ticks,
 *   and the sigils. These draw ON as the game scores them, so they are geometry, not texture:
 *   a ring is bench-stage/02-meshes.js's angle-major ring, and any contiguous index run of it is
 *   a stretch of arc (`arcRanges`), so "the chalk draws round" is a sub-range of one buffer per
 *   frame rather than a texture upload per frame (a 512x512 re-upload is a megabyte a frame).
 *   Flattened to a tenth of their height, the rings read as chalk lying on the floor.
 *
 * THE SIGILS are the Elder Futhark's twenty-four rune shapes, as straight strokes (UI plan
 * §7.1: "a fixed rune set (Elder Futhark shapes, public domain), never drawn by the player").
 * The shapes are the common stave forms (the Kylver stone's row, c. 400 AD, is the oldest full
 * futhark; the stroke lists below are the textbook staves, simplified to two to five strokes).
 * The circle cuts them in a sequence seeded from the vessel, so the same vessel always shows the
 * same sigils and two vessels rarely match. The world is not Earth (round 4, point 10): runes
 * here are shapes, never named on the page.
 *
 * Every mesh is finished through K.mesh.merge, so its id comes from the herb kit's own counter
 * (the renderer keys GPU buffers by mesh id; tests/test_forge_stage.py records why a second
 * counter would make two meshes share a buffer). The dust texture counts from 9501, above the
 * forge's painted smithy (9001 up) and the herb ground (1 up).
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var E = window.EnchantStageKit = window.EnchantStageKit || {};
  var G = K.mesh, M = K.math;
  if (!G || !M) return;   // the herb kit did not load; the adapter goes flat
  var TAU = Math.PI * 2;

  /* --- the geometry of the circle ----------------------------------------------------------
     Radii in metres; the vessel lies inside INNER, the sigils and seats share BAND, the candles
     stand outside OUTER. Twelve slots round the band, every thirty degrees from +x: the three
     facing the camera (+z) are the seats' (a vessel has at most three, enchanter.json's seats),
     the other nine are the sigils'. */
  var R = { OUTER: 0.95, OUTER2: 0.905, INNER: 0.7, BAND: 0.8, CANDLES: 1.1, LINE: 0.0085 };
  var SLOTS = 12;
  var SEAT_SLOTS = [3, 2, 4];          // 90°, 60°, 120°: front centre first, then either side
  var SIGIL_SLOTS = [0, 1, 5, 6, 7, 8, 9, 10, 11];
  function slotAngle(i) { return i / SLOTS * TAU; }

  /* --- the runes ----------------------------------------------------------------------------
     Each is a list of polylines in a unit box: u across (-0.5..0.5), v up (0..1). */
  var RUNES = [
    [[[0, 0], [0, 1]], [[0, 0.5], [0.38, 0.78]], [[0, 0.74], [0.38, 1]]],                         // fehu
    [[[-0.3, 0], [-0.3, 1], [0.3, 0.62], [0.3, 0]]],                                                 // uruz
    [[[0, 0], [0, 1]], [[0, 0.72], [0.34, 0.5], [0, 0.28]]],                                         // thurisaz
    [[[0, 0], [0, 1]], [[0, 1], [0.34, 0.76]], [[0, 0.74], [0.34, 0.5]]],                            // ansuz
    [[[0, 0], [0, 1], [0.32, 0.78], [0, 0.56], [0.34, 0]]],                                          // raido
    [[[0.26, 1], [-0.18, 0.5], [0.26, 0]]],                                                          // kaunan
    [[[-0.34, 0], [0.34, 1]], [[-0.34, 1], [0.34, 0]]],                                              // gebo
    [[[0, 0], [0, 1], [0.32, 0.8], [0, 0.6]]],                                                       // wunjo
    [[[-0.3, 0], [-0.3, 1]], [[0.3, 0], [0.3, 1]], [[-0.3, 0.64], [0.3, 0.38]]],                     // hagalaz
    [[[0, 0], [0, 1]], [[-0.3, 0.66], [0.3, 0.4]]],                                                  // naudiz
    [[[0, 0], [0, 1]]],                                                                              // isaz
    [[[-0.04, 0.9], [-0.34, 0.66], [-0.04, 0.42]], [[0.04, 0.58], [0.34, 0.34], [0.04, 0.1]]],       // jera
    [[[0, 0], [0, 1]], [[0, 1], [0.3, 0.8]], [[0, 0], [-0.3, 0.2]]],                                 // eihwaz
    [[[0, 0], [0, 1]], [[0, 1], [0.3, 0.82], [0.3, 0.66]], [[0, 0], [0.3, 0.18], [0.3, 0.34]]],      // perth
    [[[0, 0], [0, 1]], [[0, 0.58], [-0.34, 0.98]], [[0, 0.58], [0.34, 0.98]]],                       // algiz
    [[[0.3, 1], [-0.3, 0.62], [0.3, 0.38], [-0.3, 0]]],                                              // sowilo
    [[[0, 0], [0, 1]], [[-0.34, 0.7], [0, 1], [0.34, 0.7]]],                                         // tiwaz
    [[[0, 0], [0, 1], [0.32, 0.77], [0, 0.5], [0.32, 0.23], [0, 0]]],                                // berkanan
    [[[-0.3, 0], [-0.3, 1], [0, 0.7], [0.3, 1], [0.3, 0]]],                                          // ehwaz
    [[[-0.3, 0], [-0.3, 1], [0.3, 0.56]], [[0.3, 0], [0.3, 1], [-0.3, 0.56]]],                       // mannaz
    [[[0, 0], [0, 1], [0.3, 0.7]]],                                                                  // laguz
    [[[0, 1], [0.3, 0.5], [0, 0], [-0.3, 0.5], [0, 1]]],                                             // ingwaz
    [[[-0.34, 0], [-0.34, 1], [0.34, 0], [0.34, 1], [-0.34, 0]]],                                    // dagaz
    [[[-0.32, 0], [0.3, 0.62], [0, 1], [-0.3, 0.62], [0.32, 0]]]                                     // othala
  ];

  /* A flat stroke on the floor from a to b ([x, z]), w wide: a thin box, so its long faces catch
     the candle light a little and it reads as a line of chalk with body, not a painted decal. */
  var unitBox = null;
  function strokePart(a, b, w, y) {
    if (!unitBox) unitBox = G.box(1, 1, 1);
    var dx = b[0] - a[0], dz = b[1] - a[1], len = Math.sqrt(dx * dx + dz * dz);
    return { mesh: unitBox, m: M.compose([(a[0] + b[0]) / 2, y || 0.0015, (a[1] + b[1]) / 2],
                                         [0, -Math.atan2(dz, dx), 0], [len + w * 0.6, 0.003, w]) };
  }
  function polyParts(lines, w, map) {
    var parts = [];
    lines.forEach(function (pl) {
      for (var i = 0; i < pl.length - 1; i++) parts.push(strokePart(map(pl[i]), map(pl[i + 1]), w));
    });
    return parts;
  }

  /* One rune as a mesh in the sigil's own frame: u along x, v toward -z (away from the viewer
     when the sigil stands at the front), centred, `size` tall. Cached per rune and size. */
  var runeCache = {};
  function runeMesh(i, size) {
    var k = i + ":" + size.toFixed(3);
    if (!runeCache[k]) {
      runeCache[k] = G.merge(polyParts(RUNES[i % RUNES.length], size * 0.085,
                                       function (p) { return [p[0] * size, -(p[1] - 0.5) * size]; }));
    }
    return runeCache[k];
  }

  /* The flattened ring: K.mesh.ring keeps its arcRanges (angle-major), squashed to chalk height
     by the node's scale, never by rebuilding. */
  var ringCache = {};
  function chalkRing(r, w) {
    var k = r.toFixed(3) + ":" + w.toFixed(4);
    if (!ringCache[k]) ringCache[k] = G.ring(r, w, 120, 4);
    return ringCache[k];
  }

  /* The eight-point figure (two squares on the inner ring) and the four quarter ticks, one mesh.
     It draws on as a whole (alpha), after the rings. */
  var figureMesh = null;
  function figure() {
    if (figureMesh) return figureMesh;
    var parts = [], i, r = R.INNER - 0.005;
    for (var sq = 0; sq < 2; sq++) {
      for (i = 0; i < 4; i++) {
        var a0 = sq * TAU / 8 + i * TAU / 4, a1 = a0 + TAU / 4;
        parts.push(strokePart([Math.cos(a0) * r, Math.sin(a0) * r], [Math.cos(a1) * r, Math.sin(a1) * r], R.LINE * 1.3));
      }
    }
    for (i = 0; i < 4; i++) {
      var a = i * TAU / 4;
      parts.push(strokePart([Math.cos(a) * (R.INNER - 0.06), Math.sin(a) * (R.INNER - 0.06)],
                            [Math.cos(a) * (R.OUTER + 0.07), Math.sin(a) * (R.OUTER + 0.07)], R.LINE * 1.6));
    }
    figureMesh = G.merge(parts);
    return figureMesh;
  }

  /* Salt at the quarters: four low heaps of grains on the outer ring, one mesh. */
  var saltMesh = null;
  function salt() {
    if (saltMesh) return saltMesh;
    var parts = [], r = M.rng(4211), grain = G.sphere(0.008, 6, 4);
    for (var q = 0; q < 4; q++) {
      var a = q * TAU / 4 + TAU / 8, cx = Math.cos(a) * R.OUTER, cz = Math.sin(a) * R.OUTER;
      parts.push({ mesh: G.sphere(0.038, 12, 6), m: M.compose([cx, 0, cz], [0, 0, 0], [1, 0.32, 1]) });
      for (var g = 0; g < 14; g++) {
        var d = 0.03 + r() * 0.05, t = r() * TAU;
        parts.push({ mesh: grain, m: M.compose([cx + Math.cos(t) * d, 0.002, cz + Math.sin(t) * d], [0, 0, 0], [1, 0.6, 1]) });
      }
    }
    saltMesh = G.merge(parts);
    return saltMesh;
  }

  /* A seat's mark: a small ring with a dot, flat on the band. */
  var seatRing = null, seatDot = null;
  function seatMark() {
    if (!seatRing) {
      seatRing = G.ring(0.068, 0.006, 48, 4);
      seatDot = G.disc(0.012, 16);
    }
    return { ring: seatRing, dot: seatDot };
  }

  /* The sigils a vessel shows: nine rune indices drawn without repeats from a seed, so a vessel
     keeps its own sigils from one open to the next. */
  function sigilsFor(seedText) {
    var h = 2166136261, s = String(seedText || "circle");
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    var r = M.rng(h >>> 0), pool = RUNES.map(function (_, j) { return j; }), out = [];
    while (out.length < SIGIL_SLOTS.length) out.push(pool.splice(Math.floor(r() * pool.length), 1)[0]);
    return out;
  }

  /* --- the dust under the circle: painted once ------------------------------------------------ */
  var S = 512, dustRec = null, nextTex = 9501;
  function paintDust() {
    if (dustRec) return dustRec;
    var t0 = window.performance ? performance.now() : 0;
    var c = document.createElement("canvas");
    c.width = c.height = S;
    var g = c.getContext("2d", { willReadFrequently: true }), r = M.rng(9173);
    var px = S / 2.6;                        // pixels per metre: the quad is 2.6 m across
    var C = S / 2;
    g.fillStyle = "#000";
    g.fillRect(0, 0, S, S);
    // Old rings: wiped and redrawn many times, so a blur of faint arcs near the radii in use.
    g.lineCap = "round";
    [R.OUTER, R.OUTER2, R.INNER, R.BAND].forEach(function (rad) {
      for (var k = 0; k < 7; k++) {
        var a0 = r() * TAU, span = 0.6 + r() * 2.2, rr = (rad + (r() - 0.5) * 0.03) * px;
        g.strokeStyle = "rgba(215,208,190," + (0.05 + r() * 0.08).toFixed(3) + ")";
        g.lineWidth = 2 + r() * 5;
        g.beginPath(); g.arc(C, C, rr, a0, a0 + span); g.stroke();
      }
    });
    // Smears where a palm or a boot went through the chalk.
    for (var s2 = 0; s2 < 9; s2++) {
      var a = r() * TAU, d = (0.55 + r() * 0.5) * px, x = C + Math.cos(a) * d, y = C + Math.sin(a) * d;
      var grad = g.createRadialGradient(x, y, 0, x, y, 14 + r() * 22);
      grad.addColorStop(0, "rgba(200,194,178,0.16)");
      grad.addColorStop(1, "rgba(200,194,178,0)");
      g.fillStyle = grad;
      g.beginPath(); g.ellipse(x, y, 26, 11, a, 0, TAU); g.fill();
    }
    // Dust: fine grains, densest on the rings.
    for (var i = 0; i < 2600; i++) {
      var ang = r() * TAU, rad2 = [R.OUTER, R.INNER, R.BAND][i % 3] + (r() - 0.5) * (i % 5 === 0 ? 0.5 : 0.08);
      var gx = C + Math.cos(ang) * rad2 * px, gy = C + Math.sin(ang) * rad2 * px;
      g.fillStyle = "rgba(230,224,208," + (0.12 + r() * 0.3).toFixed(3) + ")";
      g.fillRect(gx, gy, 1 + r() * 1.4, 1 + r() * 1.4);
    }
    // Two ink stains: dark ink would subtract, which an additive layer cannot, so a stain is a
    // faint rim of the ink's own sheen (the dried edge of a spill catches the candle light).
    for (var k2 = 0; k2 < 2; k2++) {
      var ia = (0.15 + k2 * 0.5 + r() * 0.1) * TAU, idd = (0.98 + r() * 0.1) * px;
      var ix = C + Math.cos(ia) * idd, iy = C + Math.sin(ia) * idd;
      g.strokeStyle = "rgba(70,60,96,0.35)";
      g.lineWidth = 1.5;
      g.beginPath(); g.ellipse(ix, iy, 9 + r() * 6, 6 + r() * 4, r() * 3, 0, TAU); g.stroke();
    }
    // Copied out half a tile shifted in both directions: the floor quad's uv is in world units
    // centred on the circle (02-meshes.js's plane), so texel (0, 0) lands at the circle's
    // centre. Painted unshifted, the first capture showed the old rings round the quad's four
    // corners instead of under the circle.
    var src = g.getImageData(0, 0, S, S).data, data = new Uint8Array(S * S * 4), H = S / 2;
    for (var y2 = 0; y2 < S; y2++) {
      for (var x2 = 0; x2 < S; x2++) {
        var o = (y2 * S + x2) * 4, q = (((y2 + H) % S) * S + (x2 + H) % S) * 4;
        data[o] = src[q]; data[o + 1] = src[q + 1]; data[o + 2] = src[q + 2];
        data[o + 3] = 40;                     // gloss: chalk is matt
      }
    }
    dustRec = { id: nextTex++, kind: "chalk-dust", size: S, data: data,
                look: { spec: 0.1, shin: 8, tile: 2.6 }, span: 2.6,
                ms: (window.performance ? performance.now() : 0) - t0 };
    return dustRec;
  }

  E.circle = {
    R: R, SLOTS: SLOTS, SEAT_SLOTS: SEAT_SLOTS, SIGIL_SLOTS: SIGIL_SLOTS, RUNES: RUNES,
    slotAngle: slotAngle, runeMesh: runeMesh, chalkRing: chalkRing, figure: figure, salt: salt,
    seatMark: seatMark, sigilsFor: sigilsFor, paintDust: paintDust, strokePart: strokePart
  };
})();
