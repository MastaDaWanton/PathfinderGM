/* The herbalism bench's stage, part 0: the arithmetic.
 *
 * WHY THIS IS HAND-WRITTEN. The bench plan said "reuse three.js", and there is no three.js:
 * the app bundles no third-party JavaScript on purpose (the header of scene3d.js says why:
 * an offline executable, no CDN, and a library would be a bundling decision rather than an
 * import). dice3d.js and scene3d.js each carry their own few vector helpers; this is the
 * same bargain, scaled up to what a WebGL stage needs: column-major 4x4 matrices, a
 * perspective camera, a normal matrix, easing, and a seeded random source so a procedural
 * ground comes out the same every time it is drawn.
 *
 * Everything hangs off window.BenchStageKit, one namespace for the bench-stage/*.js files,
 * so nothing here leaks a name into the table's shared global scope (the table modules are
 * classic scripts sharing one scope, and a stray top-level `const dot` would collide).
 */
(function () {
  "use strict";
  var K = window.BenchStageKit = window.BenchStageKit || {};

  /* --- vectors ------------------------------------------------------------------------ */
  function add(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
  function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function scale(a, k) { return [a[0] * k, a[1] * k, a[2] * k]; }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function cross(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  }
  function norm(a) {
    var l = Math.sqrt(dot(a, a)) || 1;
    return [a[0] / l, a[1] / l, a[2] / l];
  }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function lerp3(a, b, t) { return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)]; }
  function clamp(x, lo, hi) { return x < lo ? lo : (x > hi ? hi : x); }
  function smooth(e0, e1, x) { var t = clamp((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t); }

  /* --- 4x4 matrices, column-major as WebGL wants them --------------------------------- */
  function ident() {
    var m = new Float32Array(16);
    m[0] = m[5] = m[10] = m[15] = 1;
    return m;
  }
  function mul(a, b) {
    var o = new Float32Array(16);
    for (var c = 0; c < 4; c++) {
      var b0 = b[c * 4], b1 = b[c * 4 + 1], b2 = b[c * 4 + 2], b3 = b[c * 4 + 3];
      o[c * 4] = a[0] * b0 + a[4] * b1 + a[8] * b2 + a[12] * b3;
      o[c * 4 + 1] = a[1] * b0 + a[5] * b1 + a[9] * b2 + a[13] * b3;
      o[c * 4 + 2] = a[2] * b0 + a[6] * b1 + a[10] * b2 + a[14] * b3;
      o[c * 4 + 3] = a[3] * b0 + a[7] * b1 + a[11] * b2 + a[15] * b3;
    }
    return o;
  }
  function perspective(fovy, aspect, near, far) {
    var f = 1 / Math.tan(fovy / 2), o = new Float32Array(16);
    o[0] = f / aspect; o[5] = f;
    o[10] = (far + near) / (near - far); o[11] = -1;
    o[14] = 2 * far * near / (near - far);
    return o;
  }
  function lookAt(eye, at, up) {
    var z = norm(sub(eye, at)), x = norm(cross(up, z)), y = cross(z, x);
    var o = new Float32Array(16);
    o[0] = x[0]; o[4] = x[1]; o[8] = x[2];
    o[1] = y[0]; o[5] = y[1]; o[9] = y[2];
    o[2] = z[0]; o[6] = z[1]; o[10] = z[2];
    o[12] = -dot(x, eye); o[13] = -dot(y, eye); o[14] = -dot(z, eye); o[15] = 1;
    return o;
  }
  /* Translate, then rotate Y, X, Z (yaw, pitch, roll), then scale. One fixed order for every
     node, so a pose written as {pos, rot, scl} means the same thing everywhere. */
  function compose(p, r, s) {
    var cx = Math.cos(r[0]), sx = Math.sin(r[0]);
    var cy = Math.cos(r[1]), sy = Math.sin(r[1]);
    var cz = Math.cos(r[2]), sz = Math.sin(r[2]);
    // R = Ry * Rx * Rz, written out.
    var m00 = cy * cz + sy * sx * sz, m01 = -cy * sz + sy * sx * cz, m02 = sy * cx;
    var m10 = cx * sz, m11 = cx * cz, m12 = -sx;
    var m20 = -sy * cz + cy * sx * sz, m21 = sy * sz + cy * sx * cz, m22 = cy * cx;
    var o = new Float32Array(16);
    o[0] = m00 * s[0]; o[1] = m10 * s[0]; o[2] = m20 * s[0];
    o[4] = m01 * s[1]; o[5] = m11 * s[1]; o[6] = m21 * s[1];
    o[8] = m02 * s[2]; o[9] = m12 * s[2]; o[10] = m22 * s[2];
    o[12] = p[0]; o[13] = p[1]; o[14] = p[2]; o[15] = 1;
    return o;
  }
  /* The inverse transpose of the upper 3x3, because a squashed tool (the drop's 4%
     overshoot) carries a non-uniform scale, and the rotation alone would tilt its normals
     the wrong way for the length of the squash. dice3d.js records the same limit as an
     honest error; here it costs nine multiplications to avoid. */
  function normalMat(m) {
    var a00 = m[0], a10 = m[1], a20 = m[2], a01 = m[4], a11 = m[5], a21 = m[6];
    var a02 = m[8], a12 = m[9], a22 = m[10];
    var c00 = a11 * a22 - a12 * a21, c01 = -(a10 * a22 - a12 * a20), c02 = a10 * a21 - a11 * a20;
    var c10 = -(a01 * a22 - a02 * a21), c11 = a00 * a22 - a02 * a20, c12 = -(a00 * a21 - a01 * a20);
    var c20 = a01 * a12 - a02 * a11, c21 = -(a00 * a12 - a02 * a10), c22 = a00 * a11 - a01 * a10;
    var det = a00 * c00 + a01 * c01 + a02 * c02 || 1;
    var o = new Float32Array(9);
    o[0] = c00 / det; o[1] = c10 / det; o[2] = c20 / det;
    o[3] = c01 / det; o[4] = c11 / det; o[5] = c21 / det;
    o[6] = c02 / det; o[7] = c12 / det; o[8] = c22 / det;
    return o;
  }
  function xform(m, p) {
    var x = p[0], y = p[1], z = p[2];
    return [m[0] * x + m[4] * y + m[8] * z + m[12], m[1] * x + m[5] * y + m[9] * z + m[13],
            m[2] * x + m[6] * y + m[10] * z + m[14], m[3] * x + m[7] * y + m[11] * z + m[15]];
  }

  /* --- easing ------------------------------------------------------------------------- */
  var ease = {
    outCubic: function (t) { t = 1 - t; return 1 - t * t * t; },
    inCubic: function (t) { return t * t * t; },
    inQuad: function (t) { return t * t; },
    inOutSine: function (t) { return 0.5 - 0.5 * Math.cos(Math.PI * t); },
    outBack: function (t) { var c = 1.70158; t -= 1; return 1 + (c + 1) * t * t * t + c * t * t; }
  };

  /* --- a seeded source ---------------------------------------------------------------
     mulberry32: four lines, good enough for leaf litter, and repeatable, so the same biome
     paints the same floor on every open instead of a new one each time. */
  function rng(seed) {
    var s = seed >>> 0;
    return function () {
      s = (s + 0x6D2B79F5) >>> 0;
      var t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  K.math = {
    add: add, sub: sub, scale: scale, dot: dot, cross: cross, norm: norm,
    lerp: lerp, lerp3: lerp3, clamp: clamp, smooth: smooth,
    ident: ident, mul: mul, perspective: perspective, lookAt: lookAt, compose: compose,
    normalMat: normalMat, xform: xform, ease: ease, rng: rng
  };
})();
