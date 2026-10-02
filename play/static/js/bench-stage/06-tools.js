/* The herbalism bench's stage, part 6: the nine tools, and how each one plays its game.
 *
 * Revamp plan §9.3 names the tool for every method; UI plan §9 says what each game looks
 * like on it. Each builder returns a TOOL:
 *
 *   root                   the node tree, standing on y = 0 round the origin
 *   ring {r, y, x, z}      where the gold drop ring sits (the rim, or the footprint)
 *   chip {r, y, arc, ground}  where ingredient chips are laid
 *   work [x, y, z]         where the work happens: hit particles and the ember flare
 *   glow                   the tool's own fire, {pos, col}, or null
 *   liquid                 the colour of what it makes, for the product vial
 *   begin() / end()        a game starts or stops
 *   pose(state)            the contracts §5.1 GameView state for this method
 *   step(dt, t, fx)        ease toward the pose; returns true while anything still moves
 *   live(dt, t, fx)        continuous emitters (steam, smoke) while a game runs
 *   hit(strength, fx) / miss(fx)
 *   dots(fx)               guide points drawn on the tool (the Mix stroke, the incision)
 *
 * WHY POSES EASE RATHER THAN SNAP. The games run at whatever rate E updates them, and a
 * pestle that jumped to each new height would stutter at any rate under the display's.
 * Every pose is a TARGET; `step` closes a fixed fraction of the gap per second, so motion
 * is smooth at any update rate and, more to the point here, it ENDS: once every value has
 * arrived, `step` returns false and the stage is allowed to stop drawing.
 *
 * Nothing here decides anything. A state comes in from the game, and the tool shows it.
 */
(function () {
  "use strict";
  var K = window.BenchStageKit = window.BenchStageKit || {};
  var G = K.mesh, P = K.props, M = K.math;
  var TAU = Math.PI * 2, D2R = Math.PI / 180;
  var clamp = function (x) { x = +x; return isFinite(x) ? Math.max(0, Math.min(1, x)) : 0; };

  function Springs() { this.v = {}; this.t = {}; this.r = {}; }
  Springs.prototype.set = function (k, v, rate) {
    if (!(k in this.v)) this.v[k] = v;
    this.t[k] = v;
    if (rate) this.r[k] = rate;
  };
  Springs.prototype.snap = function (k, v) { this.v[k] = this.t[k] = v; };
  Springs.prototype.get = function (k) { return this.v[k]; };
  Springs.prototype.step = function (dt) {
    var moving = false;
    for (var k in this.t) {
      var d = this.t[k] - this.v[k];
      if (Math.abs(d) > 1e-4) {
        this.v[k] += d * (1 - Math.exp(-dt * (this.r[k] || 10)));
        moving = true;
      } else {
        this.v[k] = this.t[k];
      }
    }
    return moving;
  };

  function base(method) {
    return {
      method: method, root: P.group(), sp: new Springs(), isLive: false, glow: null,
      ring: { r: 0.6, y: 0.5, x: 0, z: 0 }, chip: { r: 0.85, y: 0, arc: 90, ground: true },
      work: [0, 0.3, 0], liquid: [0.55, 0.4, 0.18],
      begin: function () {}, end: function () {}, pose: function () {},
      step: function (dt) { return this.sp.step(dt); }, live: function () {},
      hit: function () {}, miss: function () {}, dots: function () {}
    };
  }

  function lerpCol(a, b, t) { return M.lerp3(a, b, Math.max(0, Math.min(1, t))); }

  /* A fire bed sits IN the ground, not on it: a soft scorch darkens the floor round it and
     a faint ember glow warms its middle. Without these the ash read as a grey coaster laid
     on the leaves (first harness capture of Dry and Infuse). */
  function scorch(root, r) {
    P.add(root, P.node(G.disc(r * 1.7, 40), P.mat("shadow", { alpha: 0.7, radial: 0.9 }),
                       { pos: [0, 0.002, 0], glint: false }));
    P.add(root, P.node(G.disc(r * 0.8, 32), P.mat("gold", { color: [1, 0.36, 0.1], alpha: 0.25, radial: 1.5 }),
                       { pos: [0, 0.09, 0], glint: false }));
  }

  /* --- grind: stone mortar and pestle ----------------------------------------------------
     A ring of light closes on the strike mark in the bowl; the pestle rises as it closes
     and comes down on `struck`. Each hit grinds the powder finer: lighter, finer-grained,
     and the coarse lumps shrink away. */
  function grind() {
    var T = base("grind"), sp = T.sp;
    var prof = [[0, 0], [0.5, 0], [0.56, 0.05], [0.6, 0.28], [0.62, 0.5], [0.6, 0.58], [0.5, 0.6],
                [0.46, 0.5], [0.36, 0.3], [0.2, 0.21], [0, 0.19]];
    P.add(T.root, P.node(G.lathe(prof, 44, 45), P.mat("stone")));
    var COARSE = [0.36, 0.34, 0.21], FINE = [0.62, 0.58, 0.45];
    var pm = P.mat("ash", { color: COARSE.slice(), patScale: 0.6, spec: 0.06 });
    P.add(T.root, P.node(G.lathe([[0.275, 0.222], [0.2, 0.25], [0.1, 0.268], [0, 0.274]], 36, 80), pm));
    var lump = G.sphere(0.028, 8, 6), lumps = [], r = M.rng(5);
    for (var i = 0; i < 9; i++) {
      var a = r() * TAU, d = 0.05 + r() * 0.16;
      lumps.push(P.add(T.root, P.node(lump, P.mat("clay", { color: [0.3, 0.3, 0.16], patScale: 6 }),
        { pos: [Math.cos(a) * d, 0.258 - d * 0.12, Math.sin(a) * d], rot: [r() * 3, r() * 3, r() * 3] })));
    }
    P.add(T.root, P.node(G.ring(0.045, 0.008, 32, 6), P.mat("gold", { alpha: 0.6 }),
                         { pos: [0, 0.265, 0], glint: false }));
    var pestle = P.add(T.root, P.node(G.lathe([[0, 0], [0.09, 0.005], [0.125, 0.05], [0.12, 0.13],
      [0.075, 0.24], [0.06, 0.62], [0.072, 0.7], [0.06, 0.76], [0, 0.77]], 28, 50),
      P.mat("stone", { color: [0.58, 0.55, 0.5] })));
    var ring = null;
    T.ring = { r: 0.62, y: 0.6, x: 0, z: 0 };
    T.chip = { r: 0.55, y: 0.6, arc: -90, ground: false };
    T.work = [0, 0.28, 0];
    T.liquid = FINE;
    function rest() {
      sp.set("px", -0.05, 9); sp.set("py", 0.22, 9); sp.set("rz", -0.5, 9);
      ring = null;
    }
    sp.snap("fine", 0);
    rest();
    T.begin = function () { sp.set("fine", 0, 6); };
    T.end = rest;
    T.pose = function (s) {
      ring = clamp(s.ring);
      if (s.struck) {
        sp.set("py", 0.25, 45); sp.set("px", 0, 30); sp.set("rz", 0, 30);
      } else {
        sp.set("py", 0.27 + 0.42 * Math.sin(ring * Math.PI / 2), 14);
        sp.set("px", 0, 12); sp.set("rz", 0, 12);
      }
    };
    T.step = function (dt) {
      var moving = sp.step(dt);
      pestle.pos = [sp.get("px"), sp.get("py"), 0];
      pestle.rot = [0, 0, sp.get("rz")];
      var f = sp.get("fine");
      pm.color = lerpCol(COARSE, FINE, f);
      pm.patScale = 0.6 + 2.6 * f;
      for (var i = 0; i < lumps.length; i++) {
        var k = Math.max(0, 1 - f * (1.2 + i * 0.08));
        lumps[i].scl = [k, k, k];
        lumps[i].visible = k > 0.02;
      }
      return moving;
    };
    // Grains on the powder, fewer and smaller as it grinds fine: the mound read as a flat
    // coaster without them.
    var grains = [], gr = M.rng(7);
    for (var q = 0; q < 70; q++) {
      var ga = gr() * TAU, gd = Math.sqrt(gr()) * 0.25;
      grains.push([Math.cos(ga) * gd, 0.277 - (gd / 0.275) * 0.052, Math.sin(ga) * gd]);
    }
    T.dots = function (fx) {
      var f = sp.get("fine"), ng = Math.round(grains.length * (1 - 0.75 * f));
      for (var g = 0; g < ng; g++) fx.dot(grains[g], [0.17, 0.15, 0.09], 0.75, 0.018 * (1 - 0.5 * f), false);
      if (ring === null) return;
      var R = M.lerp(0.34, 0.05, ring), n = 44;
      for (var i = 0; i < n; i++) {
        var a = i / n * TAU;
        fx.dot([Math.cos(a) * R, 0.272, Math.sin(a) * R], [1, 0.8, 0.45], 0.45 + 0.55 * ring, 0.03, true);
      }
    };
    T.hit = function (s, fx) {
      fx.emit("grit", [0, 0.28, 0], { count: Math.round(8 + 14 * s), col: pm.color });
      fx.emit("dust", [0, 0.3, 0], { count: 3, col: lerpCol(pm.color, [0.8, 0.75, 0.6], 0.4) });
      sp.set("fine", Math.min(1, sp.t.fine + 0.08 + 0.08 * s), 6);
    };
    T.miss = function (fx) {
      fx.emit("grit", [0, 0.3, 0], { count: 9, spread: 0.18, speed: 1.5, col: [0.3, 0.27, 0.2] });
    };
    return T;
  }

  /* --- mix: wooden bowl and paddle -------------------------------------------------------
     The stroke guide is drawn in brass points on the base, the player's trace in ink; the
     paddle follows the trace's head. Gloss turns the lumpy base smooth and shining: the
     bump in the shader calms and the highlight tightens. */
  function mix() {
    var T = base("mix"), sp = T.sp;
    P.add(T.root, P.node(G.lathe([[0, 0], [0.34, 0], [0.37, 0.04], [0.64, 0.3], [0.72, 0.42],
      [0.7, 0.45], [0.63, 0.43], [0.58, 0.32], [0.3, 0.1], [0, 0.08]], 48, 45), P.mat("wood")));
    var bm = P.mat("wood", { color: [0.8, 0.68, 0.44], pattern: 4, bump: 1, spec: 0.2, shin: 12, patScale: 1 });
    P.add(T.root, P.node(G.lathe([[0.545, 0.288], [0.3, 0.305], [0, 0.312]], 56, 80), bm));
    var paddle = P.add(T.root, P.group());
    P.add(paddle, P.node(G.box(0.15, 0.2, 0.022), P.mat("wood", { color: [0.6, 0.42, 0.24] }), { pos: [0, 0.1, 0] }));
    P.add(paddle, P.node(G.capsule(0.03, 0.62, 12), P.mat("wood", { color: [0.6, 0.42, 0.24] }), { pos: [0, 0.17, 0] }));
    var st = null;
    T.ring = { r: 0.72, y: 0.45, x: 0, z: 0 };
    T.chip = { r: 0.68, y: 0.45, arc: -90, ground: false };
    T.work = [0, 0.31, 0];
    T.liquid = [0.82, 0.7, 0.45];
    function map(p) { return [(clamp(p[0]) - 0.5) * 0.86, 0.315, (clamp(p[1]) - 0.5) * 0.86]; }
    function rest() {
      sp.set("x", 0.3, 8); sp.set("y", 0.3, 8); sp.set("z", -0.08, 8);
      sp.set("rz", -0.65, 8); sp.set("rx", 0, 8);
    }
    sp.snap("gloss", 0.15);
    rest();
    T.begin = function () { sp.set("gloss", 0.1, 4); };
    T.end = function () { st = null; rest(); };
    T.pose = function (s) {
      st = s;
      var tr = s.trace || [];
      if (tr.length) {
        var h = map(tr[tr.length - 1]), pr = tr.length > 1 ? map(tr[tr.length - 2]) : h;
        sp.set("x", h[0], 22); sp.set("y", 0.29, 22); sp.set("z", h[2], 22);
        sp.set("rz", -0.25 - (h[0] - pr[0]) * 3, 14); sp.set("rx", (h[2] - pr[2]) * 3, 14);
      }
      sp.set("gloss", clamp(s.gloss), 6);
    };
    T.step = function (dt) {
      var moving = sp.step(dt);
      paddle.pos = [sp.get("x"), sp.get("y"), sp.get("z")];
      paddle.rot = [sp.get("rx"), 0, sp.get("rz")];
      var g = sp.get("gloss");
      bm.bump = 1.1 * (1 - g);
      bm.spec = 0.15 + 1.1 * g;
      bm.shin = 10 + 60 * g;
      return moving;
    };
    T.dots = function (fx) {
      if (!st) return;
      var gd = st.guide || [], tr = st.trace || [];
      var step = Math.max(1, Math.ceil(gd.length / 120)), i;
      for (i = 0; i < gd.length; i += step) fx.dot(map(gd[i]), [1, 0.82, 0.48], 0.7, 0.024, true);
      step = Math.max(1, Math.ceil(tr.length / 160));
      for (i = 0; i < tr.length; i += step) fx.dot(map(tr[i]), [0.13, 0.08, 0.05], 0.85, 0.02, false);
    };
    T.hit = function (s, fx) {
      fx.emit("splash", [paddle.pos[0], 0.32, paddle.pos[2]], { count: Math.round(3 + 5 * s), col: bm.color, speed: 0.6 });
      fx.emit("glint", [paddle.pos[0], 0.33, paddle.pos[2]], { count: 1 });
    };
    T.miss = function (fx) {
      fx.emit("splash", [paddle.pos[0], 0.32, paddle.pos[2]], { count: 4, col: [0.55, 0.45, 0.28], speed: 0.9 });
    };
    return T;
  }

  /* A dial for the pot and the glass dial: a face, a bezel, a band drawn as a sub-range of
     one ring, and a needle. Angles are the needle's, from straight up, clockwise. */
  function dial(parent, R, faceMat, sweep) {
    var d = P.add(parent, P.group());
    P.add(d, P.node(G.ring(R, R * 0.12, 48, 8), P.mat("brass"), { rot: [Math.PI / 2, 0, 0] }));
    P.add(d, P.node(G.disc(R * 0.98, 40), faceMat, { rot: [Math.PI / 2, 0, 0], pos: [0, 0, -0.004] }));
    var bandMesh = G.ring(R * 0.74, R * 0.08, 72, 6);
    var band = P.add(d, P.node(bandMesh, P.mat("gold", { color: [0.94, 0.75, 0.44] }),
                               { rot: [Math.PI / 2, 0, 0], pos: [0, 0, 0.004], glint: false }));
    var tick = G.box(R * 0.05, R * 0.16, R * 0.03);
    [-sweep, 0, sweep].forEach(function (a) {
      var ar = a * D2R;
      P.add(d, P.node(tick, P.mat("brass"), { pos: [Math.sin(ar) * R * 0.9, Math.cos(ar) * R * 0.9, 0.006], rot: [0, 0, -ar] }));
    });
    var needle = P.add(d, P.group({ pos: [0, 0, 0.012] }));
    P.add(needle, P.node(G.box(R * 0.07, R * 0.82, R * 0.04), P.mat("brass", { color: [0.95, 0.8, 0.5], emit: [0.12, 0.08, 0.03] }),
                         { pos: [0, R * 0.36, 0] }));
    P.add(needle, P.node(G.cylinder(R * 0.1, R * 0.06, 12), P.mat("brass"), { rot: [Math.PI / 2, 0, 0] }));
    return {
      group: d,
      setBand: function (a0, a1) {
        // Ring theta (in the face's plane) = needle angle - 90 degrees; see the note above.
        band.ranges = G.arcRanges(bandMesh, (a0 - 90) * D2R, (a1 - 90) * D2R);
      },
      setNeedle: function (a) { needle.rot = [0, 0, -a * D2R]; }
    };
  }
  /* The dial faces the camera: the stage's camera sits 50 degrees up, so the face is
     tipped back by the same 50 degrees. */
  var FACE_CAMERA = -50 * D2R;

  /* --- brew: blackened camp pot on a small fire, a brass dial on the rim ---------------- */
  function brew() {
    var T = base("brew"), sp = T.sp;
    var stone = G.sphere(1, 12, 8), parts = [], r = M.rng(9), i;
    for (i = 0; i < 9; i++) {
      var a = i / 9 * TAU + r() * 0.2;
      parts.push({ mesh: stone, m: M.compose([Math.cos(a) * 0.52, 0.05, Math.sin(a) * 0.52], [r(), r() * 3, 0],
                                              [0.12 + r() * 0.04, 0.06 + r() * 0.03, 0.1 + r() * 0.03]) });
    }
    P.add(T.root, P.node(G.merge(parts), P.mat("stone", { color: [0.3, 0.29, 0.27], patScale: 0.6 })));
    P.add(T.root, P.node(G.disc(0.44, 32), P.mat("ash"), { pos: [0, 0.006, 0] }));
    var log = G.capsule(0.05, 0.78, 10), logs = [];
    for (i = 0; i < 3; i++) {
      logs.push({ mesh: log, m: M.compose([Math.cos(i * 2.1) * 0.36, 0.05, Math.sin(i * 2.1) * 0.36],
                                          [0, -i * 2.1, Math.PI / 2 - 0.12], [1, 1, 1]) });
    }
    P.add(T.root, P.node(G.merge(logs), P.mat("charred")));
    var em = P.mat("gold", { color: [1, 0.42, 0.12], alpha: 0.5, radial: 1.2 });
    P.add(T.root, P.node(G.disc(0.34, 32), em, { pos: [0, 0.03, 0], glint: false }));
    var flame = G.lathe([[0, 0], [0.09, 0.04], [0.08, 0.14], [0.035, 0.26], [0, 0.32]], 12, 60);
    var flames = [], fm = P.mat("flame");
    for (i = 0; i < 5; i++) {
      var fa = i / 5 * TAU;
      flames.push(P.add(T.root, P.node(flame, fm, { pos: [Math.cos(fa) * 0.1, 0.04, Math.sin(fa) * 0.1], glint: false })));
    }
    var potProf = [[0, 0.18], [0.28, 0.18], [0.4, 0.24], [0.5, 0.42], [0.5, 0.6], [0.46, 0.68], [0.48, 0.7],
                   [0.46, 0.72], [0.42, 0.68], [0.46, 0.58], [0.46, 0.42], [0.37, 0.27], [0, 0.23]];
    P.add(T.root, P.node(G.lathe(potProf, 44, 40), P.mat("iron")));
    var lm = P.mat("wood", { color: [0.26, 0.3, 0.13], pattern: 0, spec: 1.0, shin: 50 });
    P.add(T.root, P.node(G.disc(0.452, 40), lm, { pos: [0, 0.6, 0] }));
    var bail = G.ring(0.47, 0.012, 48, 6);
    P.add(T.root, P.node(bail, P.mat("iron"), { pos: [0, 0.7, 0], rot: [-Math.PI / 2, 0.35, 0],
                                               ranges: G.arcRanges(bail, 0, Math.PI) }));
    // The dial stands on the front-right of the rim, so it never covers the pot's mouth.
    var mount = P.add(T.root, P.group({ pos: [0.44, 0.86, 0.34], rot: [FACE_CAMERA, -0.6, 0] }));
    P.add(T.root, P.node(G.box(0.06, 0.16, 0.035), P.mat("brass"), { pos: [0.4, 0.72, 0.31], rot: [0, -0.6, 0] }));
    var dl = dial(mount, 0.18, P.mat("enamel"), 120);
    var st = null;
    T.ring = { r: 0.5, y: 0.72, x: 0, z: 0 };
    T.chip = { r: 0.82, y: 0, arc: 90, ground: true };
    T.work = [0, 0.62, 0];
    T.liquid = [0.36, 0.32, 0.12];
    T.glow = { pos: [0, 0.18, 0], col: [0, 0, 0] };
    function rest() { sp.set("heat", 0.3, 4); st = null; dl.setBand(-30, 30); }
    rest();
    T.end = rest;
    T.pose = function (s) {
      st = s;
      sp.set("heat", clamp(s.heat), 10);
      var b = s.band || [0.4, 0.6];
      dl.setBand(-120 + 240 * clamp(b[0]), -120 + 240 * clamp(b[1]));
    };
    T.step = function (dt, t) {
      var moving = sp.step(dt), h = sp.get("heat");
      dl.setNeedle(-120 + 240 * h);
      // Flames flicker only while a game runs; at rest they are a still picture, because
      // a flicker would need a frame loop and an idle bench draws nothing (UI plan §10).
      for (var i = 0; i < flames.length; i++) {
        var fl = T.isLive ? 0.85 + 0.3 * Math.sin(t * (9 + i * 2.3) + i * 1.7) : 1;
        var k = (0.45 + 1.1 * h) * fl;
        flames[i].scl = [0.8 + 0.4 * h, k, 0.8 + 0.4 * h];
      }
      em.alpha = 0.3 + 0.5 * h;
      var g = 0.4 + 2.2 * h;
      T.glow.col = [1.0 * g, 0.5 * g, 0.18 * g];
      lm.color = st && st.boil ? [0.32, 0.34, 0.16] : [0.26, 0.3, 0.13];
      return moving;
    };
    T.live = function (dt, t, fx) {
      var h = sp.get("heat"), rate = (st && st.boil ? 40 : 4 + 16 * h) * dt;
      if (Math.random() < rate % 1) rate += 1;
      if (rate >= 1) fx.emit("steam", [0, 0.62, 0], { count: Math.floor(rate), spread: 0.3 });
      if (st && st.boil && Math.random() < dt * 30) fx.emit("splash", [0, 0.61, 0], { count: 1, spread: 0.3, col: lm.color, speed: 0.4 });
      if (Math.random() < dt * 6 * h) fx.emit("ember", [0, 0.1, 0], { count: 1, spread: 0.15 });
    };
    T.hit = function (s, fx) {
      fx.emit("spark", [0, 0.15, 0], { count: Math.round(6 + 10 * s), spread: 0.15 });
      fx.emit("steam", [0, 0.64, 0], { count: 4, spread: 0.25 });
    };
    T.miss = function (fx) { fx.emit("smoke", [0, 0.2, 0], { count: 5, spread: 0.2 }); };
    return T;
  }

  /* --- dry: a rack with hanging bundles over smoke ---------------------------------------
     Each bundle curls as it cures: its leaves splay and narrow, and the colour goes from
     green, to the gold of a good cure inside its band, to brown-black past it. `turned`
     swings the bundle half a turn on its string. */
  function dry() {
    var T = base("dry"), sp = T.sp, i;
    var leg = G.capsule(0.036, 1.2, 10), wood = P.mat("wood", { color: [0.4, 0.27, 0.15] });
    [-0.74, 0.74].forEach(function (x) {
      P.add(T.root, P.node(leg, wood, { pos: [x, 0, 0.3], rot: [-0.25, 0, 0] }));
      P.add(T.root, P.node(leg, wood, { pos: [x, 0, -0.3], rot: [0.25, 0, 0] }));
    });
    P.add(T.root, P.node(G.capsule(0.04, 1.62, 10), wood, { pos: [-0.81, 1.12, 0], rot: [0, 0, -Math.PI / 2] }));
    scorch(T.root, 0.46);
    P.add(T.root, P.node(G.lathe([[0.46, 0], [0.32, 0.04], [0.18, 0.065], [0, 0.07]], 32, 80), P.mat("ash", { color: [0.17, 0.16, 0.15] })));
    var ember = G.sphere(0.032, 8, 6), embers = [], r = M.rng(21);
    for (i = 0; i < 9; i++) {
      var a = r() * TAU, d = r() * 0.3;
      embers.push({ mesh: ember, m: M.compose([Math.cos(a) * d, 0.07 - d * 0.1, Math.sin(a) * d], [r(), r(), 0], [1, 0.7, 1]) });
    }
    var emM = P.mat("ember", { emit: [0.5, 0.14, 0.03] });
    P.add(T.root, P.node(G.merge(embers), emM));
    var leaf = G.leaf(0.5, 0.15, 0.3), string = G.cylinder(0.007, 0.14, 6);
    var bundles = [], st = null;
    function build(n) {
      bundles.forEach(function (b) {
        var at = T.root.kids.indexOf(b.node);
        if (at >= 0) T.root.kids.splice(at, 1);
      });
      var out = [];
      for (var k = 0; k < n; k++) {
        var x = n > 1 ? M.lerp(-0.52, 0.52, k / (n - 1)) : 0;
        var g = P.add(T.root, P.group({ pos: [x, 1.1, 0] }));
        P.add(g, P.node(string, P.mat("cloth"), { pos: [0, -0.14, 0] }));
        P.add(g, P.node(G.ring(0.035, 0.012, 16, 6), P.mat("cloth", { color: [0.55, 0.25, 0.15] }), { pos: [0, -0.15, 0] }));
        var lm = P.mat("clay", { color: [0.3, 0.46, 0.18], spec: 0.3, shin: 14, patScale: 5 }), leaves = [];
        for (var j = 0; j < 9; j++) {
          leaves.push(P.add(g, P.node(leaf, lm, { pos: [0, -0.14, 0], rot: [0.12, j / 9 * TAU + k, 0] })));
        }
        out.push({ node: g, mat: lm, leaves: leaves, key: "b" + k });
        sp.snap("c" + k, 0.25); sp.snap("t" + k, 0);
      }
      bundles = out;
    }
    build(4);
    T.ring = { r: 0.72, y: 0.02, x: 0, z: 0 };
    T.chip = { r: 0.92, y: 0, arc: 90, ground: true };
    T.work = [0, 0.8, 0];
    T.liquid = [0.55, 0.5, 0.26];
    T.glow = { pos: [0, 0.1, 0], col: [0.3, 0.1, 0.02] };
    var lastTurned = 0;
    function rest() {
      st = null;
      for (var k = 0; k < bundles.length; k++) { sp.set("c" + k, 0.25, 3); sp.set("t" + k, 0, 6); }
    }
    T.end = rest;
    T.pose = function (s) {
      st = s;
      var b = s.bundles || [];
      var n = Math.max(1, Math.min(5, b.length || 4));
      if (n !== bundles.length) build(n);
      for (var k = 0; k < bundles.length; k++) {
        var bk = b[k] || {};
        sp.set("c" + k, clamp(bk.cure), 8);
        var turned = bk.turned ? Math.PI : 0;
        if (sp.t["t" + k] !== turned) lastTurned = k;
        sp.set("t" + k, turned, 7);
        bundles[k].band = bk.band || [0.6, 0.8];
      }
    };
    T.step = function (dt) {
      var moving = sp.step(dt);
      for (var k = 0; k < bundles.length; k++) {
        var b = bundles[k], c = sp.get("c" + k), band = b.band || [0.6, 0.8], col;
        if (c < band[0]) col = lerpCol([0.3, 0.46, 0.18], [0.5, 0.5, 0.24], c / Math.max(0.01, band[0]));
        else if (c <= band[1]) col = [0.62, 0.53, 0.28];
        else col = lerpCol([0.5, 0.36, 0.18], [0.16, 0.1, 0.05], (c - band[1]) / Math.max(0.01, 1 - band[1]));
        b.mat.color = col;
        for (var j = 0; j < b.leaves.length; j++) {
          b.leaves[j].rot = [0.12 + c * 0.75, j / 9 * TAU + k, 0];
          b.leaves[j].scl = [1 - 0.45 * c, 1 - 0.18 * c, 1];
        }
        b.node.rot = [0, sp.get("t" + k), 0];
      }
      return moving;
    };
    T.live = function (dt, t, fx) {
      if (Math.random() < dt * 9) fx.emit("smoke", [0, 0.12, 0], { count: 1, spread: 0.3 });
      if (Math.random() < dt * 3) fx.emit("ember", [0, 0.1, 0], { count: 1, spread: 0.2 });
    };
    function bundlePos() {
      var b = bundles[lastTurned] || bundles[0];
      return [b.node.pos[0], 0.8, 0];
    }
    T.hit = function (s, fx) {
      var p = bundlePos();
      fx.emit("glint", p, { count: 1 });
      fx.emit("grit", p, { count: Math.round(3 + 4 * s), col: [0.55, 0.5, 0.25], speed: 0.6 });
    };
    T.miss = function (fx) {
      fx.emit("grit", bundlePos(), { count: 6, col: [0.3, 0.2, 0.1], speed: 0.8 });
    };
    return T;
  }

  /* --- reduce: a small pan on a brazier ---------------------------------------------------
     The level falls toward a scored brass line; the liquor darkens as it thickens and
     goes to char once it is let fall past the line. */
  function reduce() {
    var T = base("reduce"), sp = T.sp, i;
    var iron = P.mat("iron");
    var leg = G.capsule(0.02, 0.2, 8);
    for (i = 0; i < 3; i++) {
      var a = i / 3 * TAU + 0.5;
      P.add(T.root, P.node(leg, iron, { pos: [Math.cos(a) * 0.24, 0, Math.sin(a) * 0.24], rot: [0, -a, 0.25] }));
    }
    P.add(T.root, P.node(G.lathe([[0, 0.12], [0.2, 0.12], [0.32, 0.2], [0.34, 0.24], [0.3, 0.22], [0.18, 0.16], [0, 0.155]], 32, 40), iron));
    var coal = G.sphere(0.04, 8, 6), coals = [], r = M.rng(33);
    for (i = 0; i < 8; i++) {
      var ca = r() * TAU, cd = r() * 0.17;
      coals.push({ mesh: coal, m: M.compose([Math.cos(ca) * cd, 0.17, Math.sin(ca) * cd], [r(), r(), 0], [1, 0.7, 1]) });
    }
    var cm = P.mat("ember", { emit: [0.4, 0.1, 0.02] });
    P.add(T.root, P.node(G.merge(coals), cm));
    var panProf = [[0, 0.28], [0.36, 0.28], [0.44, 0.32], [0.5, 0.47], [0.48, 0.48], [0.42, 0.34], [0.35, 0.31], [0, 0.31]];
    P.add(T.root, P.node(G.lathe(panProf, 44, 40), iron));
    P.add(T.root, P.node(G.capsule(0.022, 0.5, 8), iron, { pos: [0.47, 0.44, 0], rot: [0, 0, -78 * D2R] }));
    P.add(T.root, P.node(G.capsule(0.034, 0.2, 10), P.mat("darkwood"), { pos: [0.9, 0.53, 0], rot: [0, 0, -78 * D2R] }));
    // Slightly translucent, so the scored line still glows through once the level is above it.
    var liq = P.mat("wood", { color: [0.5, 0.32, 0.15], pattern: 0, spec: 1.1, shin: 55, alpha: 0.88,
                              pass: "alpha", order: 1 });
    var surf = P.add(T.root, P.node(G.disc(1, 44), liq));
    var lineMesh = G.ring(1, 0.012, 64, 6);
    var line = P.add(T.root, P.node(lineMesh, P.mat("gold", { alpha: 0.75 }), { glint: false }));
    var st = null;
    T.ring = { r: 0.52, y: 0.48, x: 0, z: 0 };
    T.chip = { r: 0.82, y: 0, arc: 110, ground: true };
    T.work = [0, 0.4, 0];
    T.liquid = [0.36, 0.2, 0.08];
    T.glow = { pos: [0, 0.2, 0], col: [0, 0, 0] };
    function yAt(level) { return 0.31 + clamp(level) * 0.15; }
    function rAt(y) { return Math.max(0.05, G.radiusAt(panProf, y, true) - 0.004); }
    function rest() { st = null; sp.set("level", 0.85, 4); sp.set("line", 0.4, 4); sp.set("heat", 0.3, 4); }
    rest();
    T.end = rest;
    T.pose = function (s) {
      st = s;
      sp.set("level", clamp(s.level), 10); sp.set("line", clamp(s.line), 10); sp.set("heat", clamp(s.heat), 10);
    };
    T.step = function (dt) {
      var moving = sp.step(dt);
      var lv = sp.get("level"), ln = sp.get("line"), h = sp.get("heat");
      var y = yAt(lv), ry = rAt(y);
      surf.pos = [0, y, 0]; surf.scl = [ry, 1, ry];
      var yl = yAt(ln), rl = rAt(yl) + 0.004;
      line.pos = [0, yl, 0]; line.scl = [rl, 0.6, rl];
      var thick = M.smooth(0.9, 0.2, lv), burnt = M.smooth(ln - 0.02, ln - 0.12, lv);
      liq.color = lerpCol(lerpCol([0.5, 0.32, 0.15], [0.26, 0.13, 0.05], thick), [0.07, 0.045, 0.03], burnt);
      cm.emit = [0.25 + 0.8 * h, 0.06 + 0.2 * h, 0.01];
      var g = 0.2 + 1.6 * h;
      T.glow.col = [g, 0.4 * g, 0.12 * g];
      return moving;
    };
    T.live = function (dt, t, fx) {
      var h = sp.get("heat"), y = yAt(sp.get("level"));
      if (Math.random() < dt * (3 + 12 * h)) fx.emit("steam", [0, y, 0], { count: 1, spread: 0.25 });
      if (Math.random() < dt * 22 * h) fx.emit("splash", [0, y, 0], { count: 1, spread: 0.28, col: liq.color, speed: 0.35 });
      if (sp.get("level") < sp.get("line") - 0.08 && Math.random() < dt * 10) fx.emit("smoke", [0, y, 0], { count: 1, spread: 0.2 });
    };
    T.hit = function (s, fx) {
      var y = yAt(sp.get("level"));
      fx.emit("steam", [0, y, 0], { count: Math.round(3 + 4 * s), spread: 0.25 });
      fx.emit("glint", [0.1, y + 0.01, 0.1], { count: 1 });
    };
    T.miss = function (fx) {
      var y = yAt(sp.get("level"));
      fx.emit("splash", [0, y, 0], { count: 6, spread: 0.2, col: liq.color });
      fx.emit("smoke", [0, y, 0], { count: 3, spread: 0.2 });
    };
    return T;
  }

  /* --- extract: a board with knife and tongs ---------------------------------------------
     The incision path is dotted on the gland in brass; the knife's point follows it at
     `at`, tipped further as the pace climbs. A nick bursts the sac: a dark splash, and the
     gland sags. */
  function extract() {
    var T = base("extract"), sp = T.sp;
    P.add(T.root, P.node(G.box(1.36, 0.07, 0.8), P.mat("wood", { color: [0.56, 0.4, 0.25], patScale: 0.8 }), { pos: [0, 0.035, 0] }));
    var gm = P.mat("wood", { color: [0.5, 0.27, 0.24], pattern: 4, bump: 0.5, spec: 0.45, shin: 30, patScale: 0.6 });
    var gland = P.add(T.root, P.node(G.sphere(1, 28, 16), gm, { pos: [0, 0.07, 0], scl: [0.3, 0.12, 0.2] }));
    var steel = P.mat("steel");
    var knife = P.add(T.root, P.group());
    P.add(knife, P.node(G.box(0.26, 0.05, 0.008), steel, { pos: [0.13, 0.025, 0] }));
    P.add(knife, P.node(G.capsule(0.022, 0.18, 10), P.mat("darkwood"), { pos: [0.25, 0.03, 0], rot: [0, 0, -Math.PI / 2] }));
    var tongs = P.add(T.root, P.group({ pos: [-0.62, 0.1, 0.04] }));
    P.add(tongs, P.node(G.box(0.4, 0.02, 0.03), steel, { pos: [0.2, 0, 0.035], rot: [0, -0.08, 0] }));
    P.add(tongs, P.node(G.box(0.4, 0.02, 0.03), steel, { pos: [0.2, 0, -0.035], rot: [0, 0.08, 0] }));
    P.add(tongs, P.node(G.ring(0.03, 0.01, 16, 6), steel, { rot: [Math.PI / 2, 0, 0] }));
    var st = null, wasNicked = false;
    T.ring = { r: 0.78, y: 0.075, x: 0, z: 0 };
    T.chip = { r: 0.95, y: 0, arc: 90, ground: true };
    T.work = [0, 0.15, 0];
    T.liquid = [0.62, 0.42, 0.3];
    function map(p) {
      var X = -0.28 + 0.56 * clamp(p[0]), Z = -0.17 + 0.34 * clamp(p[1]);
      var k = 1 - (X / 0.3) * (X / 0.3) - (Z / 0.2) * (Z / 0.2);
      return [X, 0.07 + 0.12 * Math.sqrt(Math.max(0, k)) * gland.scl[1] / 0.12 + 0.006, Z];
    }
    function along(path, at) {
      if (!path || !path.length) return null;
      if (path.length === 1) return { p: map(path[0]), d: [1, 0] };
      var lens = [0], tot = 0, i;
      for (i = 1; i < path.length; i++) {
        tot += Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]);
        lens.push(tot);
      }
      var want = clamp(at) * tot;
      for (i = 1; i < path.length; i++) if (lens[i] >= want) break;
      i = Math.min(i, path.length - 1);
      var seg = lens[i] - lens[i - 1] || 1, f = (want - lens[i - 1]) / seg;
      var a = path[i - 1], b = path[i];
      return { p: map([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]), d: [b[0] - a[0], b[1] - a[1]] };
    }
    function rest() {
      st = null;
      sp.set("x", 0.2, 8); sp.set("y", 0.072, 8); sp.set("z", 0.3, 8); sp.set("yaw", 0.25, 8); sp.set("tilt", 0, 8);
    }
    sp.snap("sag", 1);
    rest();
    T.begin = function () { wasNicked = false; sp.set("sag", 1, 6); };
    T.end = rest;
    T.pose = function (s) {
      st = s;
      var h = along(s.path, s.at);
      if (h) {
        sp.set("x", h.p[0], 20); sp.set("y", h.p[1], 20); sp.set("z", h.p[2], 20);
        var yaw = Math.atan2(h.d[1], -h.d[0]);
        var cur = sp.t.yaw;
        while (yaw - cur > Math.PI) yaw -= TAU;
        while (yaw - cur < -Math.PI) yaw += TAU;
        sp.set("yaw", yaw, 12);
        sp.set("tilt", 0.45 + 0.4 * clamp(s.pace), 12);
      }
      if (s.nicked && !wasNicked) { wasNicked = true; sp.set("sag", 0.82, 5); T.pendingNick = true; }
    };
    T.step = function (dt, t, fx) {
      var moving = sp.step(dt);
      knife.pos = [sp.get("x"), sp.get("y"), sp.get("z")];
      knife.rot = [0, sp.get("yaw"), sp.get("tilt")];
      gland.scl = [0.3, 0.12 * sp.get("sag"), 0.2];
      T.work = knife.pos.slice();
      if (T.pendingNick && fx) {
        T.pendingNick = false;
        fx.emit("splash", knife.pos, { count: 14, col: [0.42, 0.1, 0.08], speed: 1.1 });
      }
      return moving;
    };
    T.dots = function (fx) {
      if (!st || !st.path) return;
      var path = st.path, at = clamp(st.at), n = 70;
      for (var i = 0; i <= n; i++) {
        var q = along(path, i / n);
        if (!q) return;
        var cut = i / n <= at;
        fx.dot(q.p, cut ? [0.35, 0.08, 0.06] : [1, 0.82, 0.48], cut ? 0.9 : 0.75, cut ? 0.016 : 0.02, !cut);
      }
    };
    T.hit = function (s, fx) {
      fx.emit("glint", knife.pos, { count: 1 });
      fx.emit("splash", knife.pos, { count: Math.round(2 + 3 * s), col: [0.85, 0.8, 0.62], speed: 0.5 });
    };
    T.miss = function (fx) { fx.emit("splash", knife.pos, { count: 5, col: [0.42, 0.12, 0.1], speed: 0.7 }); };
    return T;
  }

  /* --- infuse: a clay oil crock in warm ashes --------------------------------------------
     Embers glow with the heat; the oil rises as the infusion fills and goes from gold to
     dark once the heat passes the scorch line, with smoke to say so. */
  function infuse() {
    var T = base("infuse"), sp = T.sp, i;
    scorch(T.root, 0.6);
    P.add(T.root, P.node(G.lathe([[0.6, 0], [0.48, 0.04], [0.34, 0.08], [0, 0.09]], 40, 80), P.mat("ash", { color: [0.17, 0.16, 0.15] })));
    var ember = G.box(0.07, 0.04, 0.05), list = [], r = M.rng(41);
    for (i = 0; i < 12; i++) {
      var a = r() * TAU, d = 0.36 + r() * 0.16;
      list.push({ mesh: ember, m: M.compose([Math.cos(a) * d, 0.075 - (d - 0.36) * 0.2, Math.sin(a) * d], [r(), r() * 3, r() * 0.5],
                                            [0.7 + r() * 0.6, 0.7 + r() * 0.5, 0.7 + r() * 0.6]) });
    }
    var em = P.mat("ember", { emit: [0.3, 0.08, 0.02] });
    P.add(T.root, P.node(G.merge(list), em));
    var prof = [[0, 0.06], [0.3, 0.06], [0.38, 0.16], [0.44, 0.36], [0.42, 0.54], [0.36, 0.64], [0.36, 0.68],
                [0.39, 0.7], [0.33, 0.71], [0.31, 0.64], [0.37, 0.54], [0.39, 0.36], [0.33, 0.16], [0, 0.12]];
    P.add(T.root, P.node(G.lathe(prof, 44, 40), P.mat("clay")));
    var GOLDOIL = [0.64, 0.44, 0.12], BURNT = [0.22, 0.12, 0.04];
    var om = P.mat("wood", { color: GOLDOIL.slice(), pattern: 0, spec: 1.2, shin: 70 });
    var oil = P.add(T.root, P.node(G.disc(1, 44), om));
    var flecks = [], fr = M.rng(43);
    for (i = 0; i < 12; i++) flecks.push([(fr() - 0.5) * 1.4, (fr() - 0.5) * 1.4]);
    var st = null;
    T.ring = { r: 0.44, y: 0.71, x: 0, z: 0 };
    T.chip = { r: 0.85, y: 0, arc: 90, ground: true };
    T.work = [0, 0.5, 0];
    T.liquid = GOLDOIL;
    T.glow = { pos: [0, 0.1, 0], col: [0, 0, 0] };
    function yAt(f) { return 0.16 + clamp(f) * 0.42; }
    function rest() {
      st = null;
      sp.set("heat", 0.3, 4); sp.set("fill", 0.5, 4); sp.set("burn", 0, 4); sp.set("chill", 0, 4);
    }
    rest();
    T.end = rest;
    T.pose = function (s) {
      st = s;
      var h = clamp(s.heat), sc = s.scorch === undefined ? 0.8 : +s.scorch;
      var cold = s.cold === undefined ? 0.3 : +s.cold;
      sp.set("heat", h, 10); sp.set("fill", clamp(s.fill), 8);
      if (h > sc) sp.set("burn", Math.min(1, sp.t.burn + 0.05), 3);
      // Under the cold line the infusion stalls: the oil clouds and its shimmer stops.
      sp.set("chill", h < cold ? Math.min(1, (cold - h) / 0.2) : 0, 6);
    };
    T.step = function (dt, t) {
      var moving = sp.step(dt), h = sp.get("heat"), y = yAt(sp.get("fill"));
      var rr = Math.max(0.05, G.radiusAt(prof, y, true) - 0.005);
      oil.pos = [0, y, 0]; oil.scl = [rr, 1, rr];
      var chill = sp.get("chill");
      om.color = lerpCol(lerpCol(GOLDOIL, BURNT, sp.get("burn")), [0.62, 0.56, 0.42], chill * 0.6);
      // The shimmer is a moving highlight, so it only runs while the game keeps frames
      // coming; at rest the oil is still.
      om.spec = (T.isLive ? 1.0 + 0.5 * Math.sin(t * 7.3) * (1 - chill) : 1.2) * (1 - 0.6 * chill);
      em.emit = [0.12 + 0.6 * h, 0.03 + 0.12 * h, 0.005];
      var g = 0.2 + 1.4 * h;
      T.glow.col = [g, 0.42 * g, 0.12 * g];
      T.oilY = y; T.oilR = rr;
      return moving;
    };
    T.dots = function (fx) {
      var y = T.oilY || yAt(0.5), rr = T.oilR || 0.3;
      for (var i = 0; i < flecks.length; i++) {
        fx.dot([flecks[i][0] * rr * 0.6, y + 0.004, flecks[i][1] * rr * 0.6], [0.22, 0.3, 0.1], 0.9, 0.022, false);
      }
    };
    T.live = function (dt, t, fx) {
      var sc = st && st.scorch !== undefined ? +st.scorch : 0.8, h = sp.get("heat"), y = T.oilY || 0.4;
      if (h > sc && Math.random() < dt * 14) fx.emit("smoke", [0, y, 0], { count: 1, spread: 0.2 });
      else if (Math.random() < dt * 3 * h) fx.emit("steam", [0, y, 0], { count: 1, spread: 0.2, a: 0.1 });
      if (Math.random() < dt * 4 * h) fx.emit("ember", [0.4, 0.1, 0], { count: 1, spread: 0.4 });
    };
    T.hit = function (s, fx) { fx.emit("spark", [0.42, 0.1, 0.1], { count: Math.round(4 + 6 * s), spread: 0.25, speed: 0.7 }); };
    T.miss = function (fx) { fx.emit("dust", [0.4, 0.1, 0.1], { count: 4, col: [0.5, 0.48, 0.46] }); };
    return T;
  }

  /* --- steep: a glass jar and a bottle ----------------------------------------------------
     Glass is drawn last and blended, with a fresnel rim, so the spirit and the herbs read
     through it. The bottle tips over the jar while the fill rises, and the lid comes down
     and twists as the seal is made. */
  function steep() {
    var T = base("steep"), sp = T.sp, i;
    var JX = -0.14;
    var jar = P.add(T.root, P.group({ pos: [JX, 0, 0] }));
    var spirit = P.mat("wood", { color: [0.74, 0.56, 0.26], pattern: 0, spec: 1.2, shin: 60, alpha: 0.5,
                                 pass: "alpha", order: 1 });
    var liquid = P.add(jar, P.node(G.cylinder(0.295, 1, 36), spirit, { pos: [0, 0.03, 0] }));
    var herb = G.leaf(0.22, 0.08, 0.3), hm = P.mat("clay", { color: [0.24, 0.34, 0.14], spec: 0.3 });
    var hr = M.rng(55);
    for (i = 0; i < 6; i++) {
      P.add(jar, P.node(herb, hm, { pos: [(hr() - 0.5) * 0.3, 0.26, (hr() - 0.5) * 0.3], rot: [0.3 + hr(), hr() * TAU, 0] }));
    }
    var jarProf = [[0, 0], [0.3, 0], [0.33, 0.03], [0.33, 0.7], [0.28, 0.76], [0.28, 0.84], [0.25, 0.84],
                   [0.25, 0.76], [0.3, 0.7], [0.3, 0.03], [0, 0.03]];
    P.add(jar, P.node(G.lathe(jarProf, 48, 40), P.mat("glass")));
    var mark = P.add(jar, P.node(G.ring(0.335, 0.0045, 64, 6), P.mat("gold", { color: [0.9, 0.68, 0.34], alpha: 0.55 }),
                                 { glint: false }));
    var lid = P.add(T.root, P.group());
    P.add(lid, P.node(G.cylinder(0.29, 0.05, 32), P.mat("brass", { color: [0.66, 0.6, 0.5] })));
    P.add(lid, P.node(G.sphere(0.04, 12, 8), P.mat("brass"), { pos: [0, 0.06, 0] }));
    var bottle = P.add(T.root, P.group());
    var bProf = [[0, 0], [0.14, 0], [0.16, 0.04], [0.16, 0.42], [0.1, 0.52], [0.05, 0.6], [0.05, 0.74], [0.06, 0.76], [0, 0.76]];
    var bSpirit = P.mat("wood", { color: [0.74, 0.56, 0.26], pattern: 0, spec: 1, shin: 50, alpha: 0.55, pass: "alpha", order: 1 });
    P.add(bottle, P.node(G.cylinder(0.14, 0.36, 24), bSpirit, { pos: [0, 0.02, 0] }));
    P.add(bottle, P.node(G.lathe(bProf, 32, 40), P.mat("glass", { color: [0.45, 0.55, 0.35], alpha: 0.22 })));
    P.add(bottle, P.node(G.capsule(0.045, 0.1, 10), P.mat("cork"), { pos: [0, 0.72, 0] }));
    var stream = P.add(T.root, P.node(G.cylinder(0.014, 1, 8), P.mat("wood", { color: [0.8, 0.62, 0.3], pattern: 0,
      alpha: 0.6, pass: "alpha", order: 2, spec: 1 }), { visible: false }));
    var st = null, lastFill = 0, pourT = 0;
    T.ring = { r: 0.38, y: 0.84, x: JX, z: 0 };
    T.chip = { r: 0.85, y: 0, arc: 100, ground: true };
    T.work = [JX, 0.6, 0];
    T.liquid = [0.74, 0.56, 0.26];
    function fillY(f) { return 0.03 + clamp(f) * 0.66; }
    function rest() {
      st = null;
      sp.set("fill", 0.35, 4); sp.set("mark", 0.75, 4);
      sp.set("lx", -0.66, 6); sp.set("ly", 0, 6); sp.set("lz", 0.12, 6); sp.set("lr", 0, 6);
      sp.set("bx", 0.56, 6); sp.set("by", 0, 6); sp.set("br", 0, 6);
    }
    rest();
    T.begin = function () { lastFill = 0; pourT = 0; };
    T.end = rest;
    T.pose = function (s) {
      st = s;
      var f = clamp(s.fill);
      if (f > lastFill + 1e-4) pourT = 0.25;
      lastFill = f;
      sp.set("fill", f, 14); sp.set("mark", clamp(s.mark), 10);
      if (s.sealing) {
        var k = clamp(s.seal);
        sp.set("lx", JX, 10); sp.set("ly", 0.84 + 0.12 * (1 - k), 12); sp.set("lz", 0, 10); sp.set("lr", k * Math.PI * 1.5, 12);
      } else {
        sp.set("lx", -0.66, 6); sp.set("ly", 0, 6); sp.set("lz", 0.12, 6); sp.set("lr", 0, 6);
      }
    };
    T.step = function (dt) {
      pourT = Math.max(0, pourT - dt);
      var pouring = pourT > 0 && st && !st.sealing;
      sp.set("bx", pouring ? 0.6 : 0.56, 9); sp.set("by", pouring ? 1.24 : 0, 9); sp.set("br", pouring ? 1.9 : 0, 9);
      var moving = sp.step(dt) || pourT > 0;
      var f = sp.get("fill"), top = fillY(f);
      liquid.scl = [1, Math.max(0.002, top - 0.03), 1];
      mark.pos = [0, fillY(sp.get("mark")), 0];
      lid.pos = [sp.get("lx"), sp.get("ly"), sp.get("lz")];
      lid.rot = [0, sp.get("lr"), 0];
      bottle.pos = [sp.get("bx"), sp.get("by"), 0];
      bottle.rot = [0, 0, sp.get("br")];
      var tipped = sp.get("br") > 1.6;
      stream.visible = !!(pouring && tipped);
      if (stream.visible) {
        // The neck's tip, carried through the bottle's tilt: (0, 0.76) turned by rotZ.
        var tipY = bottle.pos[1] + 0.76 * Math.cos(sp.get("br"));
        stream.pos = [JX, top, 0];
        stream.scl = [1, Math.max(0.01, tipY - top), 1];
      }
      T.work = [JX, top, 0];
      return moving;
    };
    T.live = function (dt, t, fx) {
      if (stream.visible && Math.random() < dt * 25) fx.emit("splash", [JX, fillY(sp.get("fill")) + 0.01, 0], { count: 1, col: spirit.color, speed: 0.4, spread: 0.03 });
    };
    T.hit = function (s, fx) { fx.emit("glint", [lid.pos[0], lid.pos[1] + 0.06, lid.pos[2]], { count: 1 }); };
    T.miss = function (fx) { fx.emit("splash", [JX + 0.25, 0.84, 0], { count: 6, col: spirit.color }); };
    return T;
  }

  /* --- neutralize: a dropper, gloves and a glass dial ------------------------------------ */
  function neutralize() {
    var T = base("neutralize"), sp = T.sp, i;
    var DX = -0.22, DZ = 0.12;
    P.add(T.root, P.node(G.lathe([[0, 0], [0.2, 0], [0.25, 0.05], [0.23, 0.065], [0.19, 0.028], [0, 0.022]], 40, 40),
                         P.mat("glaze"), { pos: [DX, 0, DZ] }));
    var VOL = [0.6, 0.66, 0.24], CALM = [0.5, 0.46, 0.3];
    var mm = P.mat("wood", { color: VOL.slice(), pattern: 4, bump: 0.6, spec: 0.9, shin: 40, patScale: 2 });
    P.add(T.root, P.node(G.sphere(1, 20, 12), mm, { pos: [DX, 0.03, DZ], scl: [0.15, 0.04, 0.12] }));
    var dropper = P.add(T.root, P.group({ pos: [DX + 0.02, 0.5, DZ], scl: [1.5, 1.5, 1.5] }));
    P.add(dropper, P.node(G.lathe([[0, 0], [0.012, 0.02], [0.02, 0.07], [0.02, 0.3], [0, 0.3]], 16, 50), P.mat("glass", { alpha: 0.2 })));
    P.add(dropper, P.node(G.cylinder(0.013, 0.16, 10), P.mat("wood", { color: [0.6, 0.75, 0.7], pattern: 0, alpha: 0.6,
      pass: "alpha", order: 1, spec: 1 }), { pos: [0, 0.03, 0] }));
    var bulb = P.add(dropper, P.node(G.sphere(0.05, 16, 10), P.mat("rubber"), { pos: [0, 0.33, 0], scl: [1, 1.3, 1] }));
    var glove = (function () {
      var parts = [], s = G.sphere(1, 14, 8), f = G.capsule(0.028, 0.15, 8);
      parts.push({ mesh: s, m: M.compose([0, 0.04, 0], [0, 0, 0], [0.13, 0.04, 0.16]) });
      for (var k = 0; k < 4; k++) {
        parts.push({ mesh: f, m: M.compose([-0.075 + k * 0.05, 0.035, -0.12], [-Math.PI / 2 + 0.08, 0, 0], [1, 1, 1]) });
      }
      parts.push({ mesh: f, m: M.compose([0.12, 0.035, -0.02], [-Math.PI / 2, -1.0, 0], [1, 1, 1]) });
      parts.push({ mesh: G.cylinder(0.12, 0.14, 16), m: M.compose([0, 0.04, 0.16], [Math.PI / 2, 0, 0], [1, 1, 0.35]) });
      return G.merge(parts);
    })();
    var leather = P.mat("leather");
    P.add(T.root, P.node(glove, leather, { pos: [-0.66, 0, -0.18], rot: [0, 0.5, 0] }));
    P.add(T.root, P.node(glove, leather, { pos: [-0.5, 0.05, -0.36], rot: [0.1, -0.4, 0.06], scl: [-1, 1, 1] }));
    // The glass dial on its brass stand, to the right and a little back.
    var brass = P.mat("brass");
    P.add(T.root, P.node(G.cylinder(0.14, 0.04, 24), brass, { pos: [0.42, 0, -0.08] }));
    P.add(T.root, P.node(G.capsule(0.02, 0.4, 10), brass, { pos: [0.42, 0.03, -0.08] }));
    var mount = P.add(T.root, P.group({ pos: [0.42, 0.66, -0.08], rot: [FACE_CAMERA, -0.3, 0] }));
    var dl = dial(mount, 0.24, P.mat("enamel", { color: [0.12, 0.11, 0.1] }), 80);
    P.add(mount, P.node(G.cylinder(0.235, 0.012, 40), P.mat("glass", { alpha: 0.08 }), { rot: [Math.PI / 2, 0, 0], pos: [0, 0, 0.02] }));
    var st = null, lastDrops = 0, pending = [];
    T.ring = { r: 0.3, y: 0.07, x: DX, z: DZ };
    T.chip = { r: 0.9, y: 0, arc: 100, ground: true };
    T.work = [DX, 0.08, DZ];
    T.liquid = [0.6, 0.75, 0.7];
    function rest() { st = null; sp.set("needle", 0.55, 4); sp.set("squeeze", 0, 8); dl.setBand(-20, 20); }
    rest();
    T.begin = function () { lastDrops = 0; pending = []; };
    T.end = rest;
    T.pose = function (s) {
      st = s;
      var nd = +s.needle;
      sp.set("needle", isFinite(nd) ? Math.max(-1, Math.min(1, nd)) : 0, 9);
      var sf = s.safe || [-0.15, 0.15];
      dl.setBand(sf[0] * 80, sf[1] * 80);
      var d = s.drops | 0;
      if (d > lastDrops) {
        for (var k = 0; k < Math.min(3, d - lastDrops); k++) pending.push({ t: k * 0.12, fired: false });
        sp.snap("squeeze", 1); sp.set("squeeze", 0, 8);
      }
      lastDrops = d;
    };
    T.step = function (dt, t, fx) {
      var moving = sp.step(dt);
      var nd = sp.get("needle");
      dl.setNeedle(nd * 80);
      var sf = (st && st.safe) || [-0.15, 0.15];
      var calm = nd >= sf[0] && nd <= sf[1] ? 1 : Math.max(0, 1 - Math.abs(nd) * 1.2);
      mm.color = lerpCol(VOL, CALM, calm);
      mm.bump = 0.2 + 0.7 * (1 - calm);
      var q = sp.get("squeeze");
      bulb.scl = [1 + 0.25 * q, 1.3 - 0.4 * q, 1 + 0.25 * q];
      for (var i = pending.length - 1; i >= 0; i--) {
        var p = pending[i];
        p.t -= dt;
        if (!p.fired && p.t <= 0) {
          p.fired = true; p.t = 0.48;
          if (fx) fx.emit("drop", [DX + 0.02, 0.48, DZ], { count: 1, spread: 0, col: [0.65, 0.82, 0.76] });
        } else if (p.fired && p.t <= 0) {
          if (fx) fx.emit("splash", [DX + 0.02, 0.06, DZ], { count: 5, col: [0.65, 0.82, 0.76], speed: 0.5, spread: 0.01 });
          pending.splice(i, 1);
        }
      }
      return moving || pending.length > 0;
    };
    T.live = function (dt, t, fx) {
      var nd = sp.get("needle"), sf = (st && st.safe) || [-0.15, 0.15];
      var wild = nd < sf[0] ? sf[0] - nd : (nd > sf[1] ? nd - sf[1] : 0);
      if (Math.random() < dt * 16 * wild) fx.emit("steam", [DX, 0.06, DZ], { count: 1, spread: 0.08, col: [0.66, 0.72, 0.56], a: 0.22 });
    };
    T.hit = function (s, fx) { fx.emit("glint", [0.42, 0.66, -0.08], { count: 1 }); };
    T.miss = function (fx) { fx.emit("steam", [DX, 0.06, DZ], { count: 5, spread: 0.1, col: [0.66, 0.72, 0.56], a: 0.3 }); };
    return T;
  }

  var BUILD = { grind: grind, mix: mix, brew: brew, dry: dry, reduce: reduce, extract: extract,
                infuse: infuse, steep: steep, neutralize: neutralize };

  K.tools = { BUILD: BUILD, METHODS: Object.keys(BUILD) };
})();
