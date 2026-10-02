/* The herbalism bench's stage, part 4: particles.
 *
 * Grit from the mortar, steam off the pot, smoke under the rack, sparks from the fire,
 * splashes from the jar, and gilt for a Flawless. All of it is feedback (UI plan §10: "each
 * minigame hit: particles"), and all of it is cut by reduced motion: the stage refuses to
 * emit while the flag is on, rather than each caller remembering to check.
 *
 * A fixed pool, simulated on the CPU and uploaded as one buffer per blend mode per frame.
 * The pool's size is the cap: when it is full the oldest particle is reused, so a player
 * hammering Grind cannot grow memory. Live particles are what keep the frame loop awake,
 * and when the last one dies the loop is allowed to stop (32-bench-stage.js, `busy`).
 */
(function () {
  "use strict";
  var K = window.BenchStageKit = window.BenchStageKit || {};

  var CAP = 1600, F = 18;   // floats per particle
  // x y z vx vy vz life max size grow r g b a grav drag add twinkle

  var KIND = {
    grit: { life: [0.7, 1.2], speed: [0.6, 1.6], up: 0.9, size: [0.018, 0.034], grow: 0,
            col: [0.42, 0.36, 0.28], a: 1, grav: -7, drag: 0.6, add: 0, bounce: true },
    dust: { life: [0.7, 1.1], speed: [0.15, 0.45], up: 0.25, size: [0.14, 0.24], grow: 0.35,
            col: [0.62, 0.55, 0.44], a: 0.28, grav: 0.15, drag: 2.5, add: 0 },
    steam: { life: [1.2, 2.0], speed: [0.05, 0.2], up: 1, size: [0.12, 0.2], grow: 0.5,
             col: [0.88, 0.86, 0.82], a: 0.2, grav: 0.55, drag: 1.2, add: 0, wobble: true },
    smoke: { life: [1.8, 2.8], speed: [0.04, 0.14], up: 1, size: [0.16, 0.26], grow: 0.45,
             col: [0.42, 0.4, 0.38], a: 0.26, grav: 0.4, drag: 1.0, add: 0, wobble: true },
    spark: { life: [0.35, 0.7], speed: [1.4, 2.8], up: 1.3, size: [0.03, 0.05], grow: -0.02,
             col: [1.0, 0.58, 0.22], a: 1, grav: -5.5, drag: 0.8, add: 1 },
    ember: { life: [0.9, 1.6], speed: [0.1, 0.35], up: 1, size: [0.02, 0.035], grow: -0.01,
             col: [1.0, 0.5, 0.16], a: 0.9, grav: 0.7, drag: 0.6, add: 1, wobble: true },
    gilt: { life: [0.8, 1.3], speed: [1.2, 2.6], up: 1.6, size: [0.035, 0.06], grow: -0.02,
            col: [1.0, 0.84, 0.48], a: 1, grav: -3.2, drag: 1.1, add: 1, twinkle: true },
    splash: { life: [0.4, 0.7], speed: [0.5, 1.3], up: 1.4, size: [0.025, 0.04], grow: 0,
              col: [0.6, 0.5, 0.3], a: 0.85, grav: -7.5, drag: 0.4, add: 0 },
    drop: { life: [0.5, 0.5], speed: [0, 0], up: 0, size: [0.035, 0.035], grow: 0,
            col: [0.7, 0.8, 0.75], a: 0.9, grav: -4.5, drag: 0, add: 0 },
    glint: { life: [0.25, 0.4], speed: [0, 0.1], up: 0, size: [0.12, 0.2], grow: 0.4,
             col: [1.0, 0.9, 0.62], a: 0.8, grav: 0, drag: 0, add: 1 }
  };

  function Particles() {
    this.d = new Float32Array(CAP * F);
    this.n = 0;
    this.head = 0;
    this.out = [new Float32Array(CAP * 8), new Float32Array(CAP * 8)];
    this.counts = [0, 0];
    this.rnd = Math.random;
  }

  /* opts: {count, col, spread, speed, up, size, life} overrides; origin [x,y,z]. */
  Particles.prototype.emit = function (kind, origin, opts) {
    var k = KIND[kind];
    if (!k) return;
    opts = opts || {};
    var count = opts.count || 1, r = this.rnd;
    for (var i = 0; i < count; i++) {
      var slot;
      if (this.n < CAP) { slot = this.n++; } else { slot = this.head; this.head = (this.head + 1) % CAP; }
      var o = slot * F, d = this.d;
      var sp = opts.spread === undefined ? 0.05 : opts.spread;
      var speed = (opts.speed || 1) * (k.speed[0] + r() * (k.speed[1] - k.speed[0]));
      var ang = r() * Math.PI * 2, up = opts.up === undefined ? k.up : opts.up;
      var dir = [Math.cos(ang), up * (0.6 + r() * 0.8), Math.sin(ang)];
      if (opts.dir) dir = [opts.dir[0] + (r() - 0.5) * 0.6, opts.dir[1] + (r() - 0.5) * 0.3, opts.dir[2] + (r() - 0.5) * 0.6];
      var l = Math.sqrt(dir[0] * dir[0] + dir[1] * dir[1] + dir[2] * dir[2]) || 1;
      d[o] = origin[0] + (r() - 0.5) * sp * 2;
      d[o + 1] = origin[1] + (r() - 0.5) * sp * 0.5;
      d[o + 2] = origin[2] + (r() - 0.5) * sp * 2;
      d[o + 3] = dir[0] / l * speed; d[o + 4] = dir[1] / l * speed; d[o + 5] = dir[2] / l * speed;
      var life = opts.life || (k.life[0] + r() * (k.life[1] - k.life[0]));
      d[o + 6] = life; d[o + 7] = life;
      d[o + 8] = (opts.size || 1) * (k.size[0] + r() * (k.size[1] - k.size[0]));
      d[o + 9] = k.grow;
      var c = opts.col || k.col, j = 0.88 + r() * 0.24;
      d[o + 10] = Math.min(1, c[0] * j); d[o + 11] = Math.min(1, c[1] * j); d[o + 12] = Math.min(1, c[2] * j);
      d[o + 13] = opts.a === undefined ? k.a : opts.a;
      d[o + 14] = k.grav; d[o + 15] = k.drag; d[o + 16] = k.add;
      d[o + 17] = (k.twinkle ? 1 : 0) + (k.wobble ? 2 : 0) + (k.bounce ? 4 : 0) + r() * 0.001;
    }
  };

  Particles.prototype.step = function (dt, t) {
    var d = this.d, i = 0;
    this.counts[0] = this.counts[1] = 0;
    while (i < this.n) {
      var o = i * F;
      d[o + 6] -= dt;
      if (d[o + 6] <= 0) {
        // Swap the last one into this slot.
        var last = (this.n - 1) * F;
        if (last !== o) for (var q = 0; q < F; q++) d[o + q] = d[last + q];
        this.n--;
        if (this.head >= this.n) this.head = 0;
        continue;
      }
      var flags = d[o + 17];
      var drag = Math.exp(-d[o + 15] * dt);
      d[o + 3] *= drag; d[o + 5] *= drag;
      d[o + 4] = d[o + 4] * drag + d[o + 14] * dt;
      if (flags >= 2 && (Math.floor(flags) & 2)) {
        d[o + 3] += Math.sin(t * 2.3 + o) * 0.25 * dt;
        d[o + 5] += Math.cos(t * 1.9 + o) * 0.25 * dt;
      }
      d[o] += d[o + 3] * dt; d[o + 1] += d[o + 4] * dt; d[o + 2] += d[o + 5] * dt;
      if ((Math.floor(flags) & 4) && d[o + 1] < 0.01) {
        d[o + 1] = 0.01; d[o + 4] = -d[o + 4] * 0.3; d[o + 3] *= 0.5; d[o + 5] *= 0.5;
      }
      d[o + 8] = Math.max(0.004, d[o + 8] + d[o + 9] * dt);
      var lf = d[o + 6] / d[o + 7];
      // Fade in fast, out slow: a puff should arrive, not pop.
      var a = d[o + 13] * Math.min(1, (1 - lf) * 8) * Math.min(1, lf * 2.2);
      if (Math.floor(flags) & 1) a *= 0.55 + 0.45 * Math.sin(t * 22 + o * 1.7);
      var w = d[o + 16] > 0.5 ? 1 : 0, out = this.out[w], c = this.counts[w] * 8;
      out[c] = d[o]; out[c + 1] = d[o + 1]; out[c + 2] = d[o + 2];
      out[c + 3] = d[o + 10]; out[c + 4] = d[o + 11]; out[c + 5] = d[o + 12]; out[c + 6] = a;
      out[c + 7] = d[o + 8];
      this.counts[w]++;
      i++;
    }
  };

  Particles.prototype.clear = function () { this.n = 0; this.head = 0; this.counts[0] = this.counts[1] = 0; };
  Particles.prototype.alive = function () { return this.n; };

  K.Particles = Particles;
})();
