// The play table, part 32 (the herbalism bench's 3D stage). Classic script; everything it
// defines lives inside one IIFE and leaves exactly one global, window.BenchStage, because
// the table's numbered modules share a single global scope.
//
// WHAT IT IS. The middle of the bench (UI plan §6.3): the tool for the chosen method on
// the ground you are standing on, lit by the scene's light, with the minigame drawn ON the
// tool. Its interface is the contracts' §5.1, and D and E build against nothing else:
//
//   available() mount(host) unmount() setGround({biome, roofed, minute})
//   setTool(method) addIngredient({key, part, name}) removeIngredient(key)
//   clearIngredients() setDragOver(bool) game(method) flourish(kind) productRect()
//   reducedMotion(bool)
//
// HOW IT IS BUILT. By hand, in WebGL1, from the parts in play/static/js/bench-stage/: the
// app bundles no third-party JavaScript (scene3d.js's header), so the "reuse three.js"
// line in the plan had nothing to reuse. The light is the house light of dice3d.js and
// scene3d.js, one ambient, one diffuse, one tight specular, belonging to the room.
//
// RENDER ON DEMAND (UI plan §10: "No requestAnimationFrame loop runs while the bench is
// idle"). This is the three.js manual's "rendering on demand" pattern: nothing draws
// until something asks, and a frame only schedules the next one while something is still
// moving: a tween, a pose easing in, a live game, a flourish, or a particle not yet dead.
// When the last of those settles, the loop simply does not ask again. `wake` is the only
// place requestAnimationFrame is called, and tests/test_bench_stage.py holds it there.
//
// WHAT IT MAY NOT DO (the owner's rule: no motion that makes a menu harder to use). The
// canvas takes no pointer events, every flourish ends on its own inside 1.1s, and the
// Flawless shake moves the STAGE canvas only, never the page. Nothing here can throw into
// a caller: without WebGL every method is a quiet no-op and `available()` says false, so
// D shows its flat stage and E's games run in their strip.
(function () {
  "use strict";

  var K = window.BenchStageKit || {};
  var M = K.math;
  var READY = !!(K.math && K.Renderer && K.mesh && K.ground && K.Particles && K.props && K.tools);
  var D2R = Math.PI / 180;
  var BG = [13 / 255, 11 / 255, 9 / 255];          // --bg, #0d0b09
  var CANDLE = [0.94, 0.75, 0.44];                  // --candle, #f0c070
  var MAX_PIXELS = 3840 * 2160;                     // see `resize`
  var REF = { lo: [-0.85, 0, -0.55], hi: [0.85, 1.15, 0.55] };

  var S = {
    host: null, canvas: null, r: null, ro: null, mounted: false, lost: false, raf: 0, lastT: 0,
    ground: { biome: "forest", roofed: false, minute: 14 * 60, place: "" },
    groundRec: null, groundNode: null, shadow: null,
    tools: {}, tool: null, leaving: null, swap: null,
    chips: [], chipGroup: null, ringShown: false, ringNode: null,
    product: null, productOn: false,
    particles: null, tweens: [],
    reduced: false, gameLast: 0,
    flare: 0, glint: 0, nudge: 0, nudgeAt: 0, dim: 1, shake: 0, shudder: 0, punch: 0, reveal: 1,
    cssW: 1, cssH: 1, cam: null, frame: null,
    dots: [new Float32Array(2400 * 8), new Float32Array(2400 * 8)], dotN: [0, 0],
    stats: { frames: 0, draws: 0, lastDraws: 0, ms: [], rafs: 0 }
  };

  function now() { return (window.performance && performance.now) ? performance.now() : Date.now(); }
  function sound(name) {
    try { if (window.Sound && typeof window.Sound.play === "function") window.Sound.play(name); } catch (e) { /* silent */ }
  }
  function warn(where, e) {
    if (window.console && console.warn) console.warn("BenchStage." + where + ":", e && e.message ? e.message : e);
  }
  /* Every public method goes through this: a stage bug must never break the bench. */
  function safe(where, fn, fallback) {
    return function () {
      try { return fn.apply(null, arguments); } catch (e) { warn(where, e); return fallback; }
    };
  }

  /* --- the frame loop ------------------------------------------------------------------ */

  // BENCH-STAGE-RAF: the only requestAnimationFrame in the stage. It is reached from
  // wake() and nowhere else, and wake() is only called when something changed.
  function wake() {
    if (S.raf || !S.mounted || S.lost) return;
    S.stats.rafs++;
    S.raf = window.requestAnimationFrame(frame);
  }

  function frame(tms) {
    S.raf = 0;
    if (!S.mounted || S.lost) return;
    var t = now();
    var dt = S.lastT ? Math.min(0.05, (t - S.lastT) / 1000) : 1 / 60;
    S.lastT = t;
    var busy = false;
    try {
      busy = step(dt, t);
      draw();
    } catch (e) { warn("frame", e); busy = false; }
    var ms = now() - t;
    S.stats.frames++;
    S.stats.ms.push(ms);
    if (S.stats.ms.length > 240) S.stats.ms.shift();
    // DIRTY-ONLY: the next frame is asked for only while something is still moving.
    if (busy) wake(); else S.lastT = 0;
    void tms;
  }

  /* Tweens run on the wall clock, so a tween started in a background tab is simply over
     when the tab comes back, rather than resuming from where it froze. */
  function tween(dur, fn, done) {
    var tw = { start: now(), dur: Math.max(1, dur), fn: fn, done: done };
    S.tweens.push(tw);
    fn(0);
    wake();
    return tw;
  }
  function endTween(tw) {
    var i = S.tweens.indexOf(tw);
    if (i < 0) return;
    S.tweens.splice(i, 1);
    tw.fn(1);
    if (tw.done) tw.done();
  }

  function step(dt, t) {
    var busy = false, i;
    for (i = S.tweens.length - 1; i >= 0; i--) {
      var tw = S.tweens[i];
      if (!tw) continue;
      var p = Math.min(1, (t - tw.start) / tw.dur);
      if (p >= 1) endTween(tw); else { tw.fn(p); busy = true; }
    }
    if (S.tweens.length) busy = true;
    var T = S.tool;
    var live = T && T.isLive && (t - S.gameLast) < 300;
    [T, S.leaving].forEach(function (tool) {
      if (tool && tool.step(dt, t / 1000, FX)) busy = true;
    });
    if (live && !S.reduced) T.live(dt, t / 1000, FX);
    if (live) busy = true;
    if (S.particles.alive()) {
      S.particles.step(dt, t / 1000);
      busy = true;
    } else {
      S.particles.counts[0] = S.particles.counts[1] = 0;
    }
    if (S.flare > 0.005) { S.flare *= Math.exp(-dt * 11); busy = true; } else S.flare = 0;
    if (S.punch > 0.005) { S.punch *= Math.exp(-dt * 18); busy = true; } else S.punch = 0;
    if (S.nudge > 0) {
      var np = (t - S.nudgeAt) / 60;
      if (np >= 1) S.nudge = 0; else busy = true;
    }
    return busy;
  }

  /* --- camera ---------------------------------------------------------------------------
     About 50 degrees down onto the kit. The field of view is SOLVED, not fixed, so the
     tool keeps its size across aspects: the tool's own silhouette (its rest-pose vertices,
     thinned to a few hundred) is measured in tan-space each frame, and the view opens just
     enough to hold it at half the stage's height and no more than 80% of its width. On a
     narrow stage the width wins and the view widens, but never past the point where the
     tool would fall under 38% of the stage height (UI plan §4.3): there it would rather
     crop the ground at the sides than shrink the tool. On 21:9 and 3440x1440 the height
     rule holds, so the tool stands exactly as tall as at 16:9, and the ground and vignette
     fill the extra width.

     Two framings were tried first and measured in the harness. One shared box sized for
     the drying rack left the mortar at 37% of a 16:9 stage. Each tool's bounding BOX was
     better but still wrong at narrow aspects (the drying rack at 29%, neutralize at 27%),
     because the corners of a box round a round vessel are air, and the 38% clamp was
     holding the air at 38%. Vertices are what the eye sees, so vertices are what is fit.

     On a swap the framing eases from the old tool's fit to the new one's while the old
     tool lifts away, so the camera never jumps. */
  function extent(pts, view) {
    var lo0 = Infinity, lo1 = Infinity, hi0 = -Infinity, hi1 = -Infinity;
    for (var i = 0; i < pts.length; i += 3) {
      var x = pts[i], y = pts[i + 1], z = pts[i + 2];
      var vx = view[0] * x + view[4] * y + view[8] * z + view[12];
      var vy = view[1] * x + view[5] * y + view[9] * z + view[13];
      var vz = -(view[2] * x + view[6] * y + view[10] * z + view[14]);
      var tx = vx / vz, ty = vy / vz;
      if (tx < lo0) lo0 = tx; if (tx > hi0) hi0 = tx;
      if (ty < lo1) lo1 = ty; if (ty > hi1) hi1 = ty;
    }
    return [lo0, lo1, hi0, hi1];
  }
  var REF_PTS = (function () {
    var a = [];
    for (var i = 0; i < 8; i++) {
      a.push(i & 1 ? REF.hi[0] : REF.lo[0], i & 2 ? REF.hi[1] : REF.lo[1], i & 4 ? REF.hi[2] : REF.lo[2]);
    }
    return a;
  })();

  function camera() {
    var aspect = S.cssW / Math.max(1, S.cssH);
    var pitch = 50 * D2R + S.nudge * Math.max(0, 1 - (now() - S.nudgeAt) / 60) * D2R;
    var fr = S.frame, to = fr ? fr.to : null, from = fr && fr.from ? fr.from : to, k = fr ? fr.k : 1;
    var cA = from ? from.centre : [0, 0.55, 0], cB = to ? to.centre : cA;
    var target = M.lerp3(cA, cB, k), dist = 3.7;
    var eye = [target[0], target[1] + Math.sin(pitch) * dist, target[2] + Math.cos(pitch) * dist];
    var view = M.lookAt(eye, target, [0, 1, 0]);
    var eB = extent(to ? to.pts : REF_PTS, view), e = eB;
    if (from && from !== to && k < 1) {
      var eA = extent(from.pts, view);
      e = [M.lerp(eA[0], eB[0], k), M.lerp(eA[1], eB[1], k), M.lerp(eA[2], eB[2], k), M.lerp(eA[3], eB[3], k)];
    }
    var Tw = e[2] - e[0], Th = e[3] - e[1];
    var tH = Th / (2 * 0.5), tW = Tw / (2 * 0.8 * aspect), tMax = Th / (2 * 0.38);
    var t = Math.min(Math.max(tH, tW), tMax);
    var proj = M.perspective(2 * Math.atan(t), aspect, 0.1, 60);
    // Lens shift: the tool's centre sits a little above the middle, leaving the lower part
    // of the stage for the info line and the rising minigame strip.
    var cy = (e[3] + e[1]) / 2, cx = (e[2] + e[0]) / 2;
    proj[9] = cy / t - 0.12;
    proj[8] = cx / (t * aspect);
    var vp = M.mul(proj, view);
    S.cam = { eye: eye, view: view, proj: proj, vp: vp, t: t, frac: Th / (2 * t) };
    return S.cam;
  }

  /* --- light, by the scene clock ---------------------------------------------------------
     The fill is the sky: cool and high by day, warm and low at dusk, a dim blue moon at
     night. Its direction is the house LIGHT of dice3d.js (high, left, in front), carried
     from the screen's frame into the world's. The key is the camp fire outdoors and the
     lamp under a roof, and it matters most when the sky has gone. */
  var LIGHT = M ? M.norm([-0.42, 0.78, 0.47]) : [0, 1, 0];
  function bell(x, c, w) { var d = (x - c) / w; return Math.exp(-d * d); }
  function lights() {
    var g = S.ground, h = ((((+g.minute || 0) % 1440) + 1440) % 1440) / 60;
    var day = M.smooth(5.5, 7.5, h) * (1 - M.smooth(17.5, 19.5, h));
    var dusk = Math.max(bell(h, 6.5, 1.1), bell(h, 18.6, 1.1));
    var L = {};
    if (g.roofed) {
      L.amb = M.lerp3([0.08, 0.07, 0.065], [0.17, 0.16, 0.15], day);
      L.fillDir = M.norm([-0.7, 0.6, 0.25]);
      var w = 0.45 * day + 0.05;
      L.fillCol = [0.6 * w, 0.66 * w, 0.78 * w];
      L.keyPos = [-1.3, 2.4, 1.2];
      L.keyCol = [1.45, 1.02, 0.58];
    } else {
      L.amb = M.add(M.lerp3([0.045, 0.05, 0.075], [0.44, 0.45, 0.48], day), [0.07 * dusk, 0.035 * dusk, 0.015 * dusk]);
      L.fillDir = LIGHT;
      var moon = (1 - day) * (1 - dusk);
      L.fillCol = M.add(M.add(M.scale([0.9, 0.9, 0.95], 1.0 * day), M.scale([0.7, 0.42, 0.24], 0.6 * dusk)),
                        M.scale([0.24, 0.31, 0.52], 0.4 * moon));
      L.keyPos = [-1.9, 1.1, 1.5];
      // The fire is a pool of warm light round the kit at night, and a faint warmth by day.
      var k = 0.35 + 1.25 * (1 - day);
      L.keyCol = [1.0 * k, 0.6 * k, 0.28 * k];
    }
    return L;
  }

  /* --- the scene ------------------------------------------------------------------------ */

  function collect(n, parent, alpha, glint, out) {
    if (!n || !n.visible) return;
    var m = M.mul(parent, M.compose(n.pos, n.rot, n.scl));
    var a = alpha * (n.alpha === undefined ? 1 : n.alpha);
    if (a <= 0.002) return;
    if (n.mesh && n.mat) out.push({ n: n, m: m, a: a, glint: n.glint ? glint : 0 });
    for (var i = 0; i < n.kids.length; i++) collect(n.kids[i], m, a, glint, out);
  }

  function rootMatrix(T) {
    var n = T.root;
    var m = M.compose(n.pos, n.rot, n.scl);
    return m;
  }

  /* The effects interface a tool sees: particles and guide points in the tool's own
     coordinates, carried into the world through its root (which moves during a drop). */
  var FX = {
    emit: function (kind, pos, opts) {
      if (S.reduced || !S.tool) return;
      var w = M.xform(rootMatrix(S.tool), pos);
      S.particles.emit(kind, [w[0], w[1], w[2]], opts);
      wake();
    },
    dot: function (pos, col, a, size, add) {
      var T = S.tool;
      if (!T) return;
      var w = M.xform(rootMatrix(T), pos), k = add ? 1 : 0, n = S.dotN[k];
      if (n >= 2400) return;
      var d = S.dots[k], o = n * 8;
      d[o] = w[0]; d[o + 1] = w[1]; d[o + 2] = w[2];
      d[o + 3] = col[0]; d[o + 4] = col[1]; d[o + 5] = col[2]; d[o + 6] = a * T.root.alpha; d[o + 7] = size;
      S.dotN[k] = n + 1;
    }
  };

  function draw() {
    var r = S.r;
    if (!r || !r.gl || S.lost) return;
    var cam = camera(), L = lights(), T = S.tool;
    var work = T ? M.xform(rootMatrix(T), T.work) : [0, 0.4, 0];
    var glowPos = [0, -10, 0], glowCol = [0, 0, 0];
    if (T && T.glow) {
      var gp = M.xform(rootMatrix(T), T.glow.pos);
      glowPos = [gp[0], gp[1], gp[2]];
      glowCol = M.scale(T.glow.col, T.root.alpha);
    }
    var fk = S.flare * 2.6;
    r.begin({
      vp: cam.vp, view: cam.view, proj: cam.proj, eye: cam.eye, amb: L.amb, keyPos: L.keyPos, keyCol: L.keyCol,
      fillDir: L.fillDir, fillCol: L.fillCol, glowPos: glowPos, glowCol: glowCol,
      flarePos: [work[0], work[1] + 0.3, work[2] + 0.2], flareCol: [CANDLE[0] * fk, CANDLE[1] * fk, CANDLE[2] * fk],
      exposure: S.dim, reveal: S.reveal, bg: BG, fade: [4.2, 9.5],
      px: r.canvas.height / (2 * cam.t)
    });

    var items = [], I = M.ident();
    if (S.groundNode) collect(S.groundNode, I, 1, 0, items);
    if (S.shadow) S.shadow.alpha = T ? T.root.alpha * Math.max(0, 1 - T.root.pos[1] / 1.4) : 0;
    if (S.leaving) collect(S.leaving.root, I, 1, 0, items);
    // A hit punches the tool: a 3.5% squash that springs back inside a tenth of a second.
    var pk = S.punch;
    if (T) collect(T.root, pk ? M.compose([0, 0, 0], [0, 0, 0], [1 + 0.02 * pk, 1 - 0.035 * pk, 1 + 0.02 * pk]) : I,
                   1, S.glint, items);
    if (S.shadow) collect(S.shadow, I, 1, 0, items);
    collect(S.chipGroup, I, 1, 0, items);
    if (S.ringNode) collect(S.ringNode, I, 1, 0, items);
    if (S.product && S.productOn) collect(S.product, I, 1, S.glint * 0.5, items);

    var opaque = [], fade = [], alpha = [], add = [];
    items.forEach(function (it) {
      var pass = it.n.mat.pass || "opaque";
      if (pass === "opaque") (it.a < 0.999 ? fade : opaque).push(it);
      else if (pass === "alpha") alpha.push(it);
      else add.push(it);
    });
    alpha.forEach(function (it) {
      var dx = it.m[12] - cam.eye[0], dy = it.m[13] - cam.eye[1], dz = it.m[14] - cam.eye[2];
      it.depth = dx * dx + dy * dy + dz * dz;
    });
    alpha.sort(function (a, b) {
      var oa = a.n.mat.order || 0, ob = b.n.mat.order || 0;
      return oa !== ob ? oa - ob : b.depth - a.depth;
    });
    function issue(list) {
      list.forEach(function (it) {
        var rs = it.n.ranges;
        if (rs) rs.forEach(function (rg) { r.draw(it.n.mesh, it.m, it.n.mat, it.a, it.glint, rg); });
        else r.draw(it.n.mesh, it.m, it.n.mat, it.a, it.glint, null);
      });
    }
    r.setBlend("opaque"); issue(opaque);
    r.setBlend("fade"); issue(fade);
    r.setBlend("alpha"); issue(alpha);
    r.setBlend("add"); issue(add);

    S.dotN[0] = S.dotN[1] = 0;
    if (T && T.root.visible) T.dots(FX);
    r.points(S.dots[0], S.dotN[0], false);
    r.points(S.particles.out[0], S.particles.counts[0], false);
    r.points(S.dots[1], S.dotN[1], true);
    r.points(S.particles.out[1], S.particles.counts[1], true);
    S.stats.lastDraws = r.draws;
    S.stats.draws += r.draws;
  }

  /* --- size -----------------------------------------------------------------------------
     Device-pixel aware, capped at 2 as the brief says, and capped again at 4K worth of
     pixels: the owner's 3440x1440 at a ratio of 2 would be a 6880x2880 buffer, five times
     the fill of 1080p, for a soft ground nobody inspects at that size. */
  function resize() {
    if (!S.canvas || !S.host) return;
    var w = Math.max(1, S.host.clientWidth), h = Math.max(1, S.host.clientHeight);
    var dpr = Math.min(2, window.devicePixelRatio || 1);
    if (w * h * dpr * dpr > MAX_PIXELS) dpr = Math.max(1, Math.sqrt(MAX_PIXELS / (w * h)));
    S.cssW = w; S.cssH = h;
    if (S.r) S.r.resize(Math.round(w * dpr), Math.round(h * dpr));
    wake();
  }

  /* --- ground ---------------------------------------------------------------------------- */
  function applyGround() {
    if (!S.mounted) return;
    var kind = K.ground.kindFor(S.ground), rec = K.ground.paint(kind);
    if (S.groundRec && S.groundRec !== rec && S.r) S.r.forgetTexture(S.groundRec);
    S.groundRec = rec;
    var k = 1 / rec.look.tile;
    var mt = K.props.mat("wood", { color: [1, 1, 1], pattern: 0, tex: rec, uvScale: [k, k], ground: 1,
                                   spec: rec.look.spec, shin: rec.look.shin });
    if (!S.groundNode) S.groundNode = K.props.node(K.mesh.plane(40), mt, { glint: false });
    S.groundNode.mat = mt;
    wake();
  }

  /* --- tools ----------------------------------------------------------------------------- */
  function toolFor(method) {
    if (!K.tools || !K.tools.BUILD[method]) return null;
    if (!S.tools[method]) {
      var T = K.tools.BUILD[method]();
      T.step(10, 0, null);          // settle every pose before the silhouette is read
      T.fit = fitOf(T.root);
      S.tools[method] = T;
    }
    return S.tools[method];
  }

  /* The solid parts at rest, as a thinned cloud of world points plus their centre: glows,
     flames and shadows are light, not the tool, and are left out. */
  function fitOf(root) {
    var items = [], pts = [], lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    collect(root, M.ident(), 1, 0, items);
    var total = 0;
    items.forEach(function (it) { if (it.n.mat.pass !== "add" && !it.n.mat.radial) total += it.n.mesh.pos.length / 3; });
    var every = Math.max(1, Math.floor(total / 900));
    items.forEach(function (it) {
      var mt = it.n.mat;
      if (mt.pass === "add" || mt.radial) return;
      var P = it.n.mesh.pos;
      for (var i = 0; i < P.length; i += 3 * every) {
        var w = M.xform(it.m, [P[i], P[i + 1], P[i + 2]]);
        pts.push(w[0], w[1], w[2]);
        for (var k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], w[k]); hi[k] = Math.max(hi[k], w[k]); }
      }
    });
    if (!pts.length) return { pts: REF_PTS, centre: [0, 0.55, 0] };
    return { pts: new Float32Array(pts), centre: [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2] };
  }

  function finishSwap() {
    var sw = S.swap;
    if (!sw) return;
    S.swap = null;
    sw.tweens.forEach(endTween);
    if (sw.timer) clearTimeout(sw.timer);
    if (S.leaving) { S.leaving.root.visible = false; S.leaving = null; }
    var R = sw.tool.root;
    R.pos = [0, 0, 0]; R.scl = [1, 1, 1]; R.rot = [0, 0, 0]; R.alpha = 1;
    S.frame = { from: null, to: sw.tool.fit, k: 1 };
    sw.resolve(true);
  }

  function setTool(method) {
    return new Promise(function (resolve) {
      var T = toolFor(method);
      if (!T) { resolve(false); return; }
      finishSwap();
      var old = S.tool;
      if (old === T) { resolve(true); return; }
      S.tool = T;
      T.isLive = false;
      T.root.visible = true;
      var fromFit = S.frame ? S.frame.to : T.fit;
      S.frame = { from: fromFit, to: T.fit, k: 0 };
      layoutChips(true);
      buildRing();
      if (!S.mounted) {
        if (old) old.root.visible = false;
        S.frame = { from: null, to: T.fit, k: 1 };
        resolve(true);
        return;
      }
      var sw = { tool: T, resolve: resolve, tweens: [] };
      S.swap = sw;
      S.leaving = old;
      var R = T.root, total;
      if (S.reduced) {
        // Reduced motion: a 120ms crossfade, nothing falls (UI plan §10).
        total = 120;
        sw.tweens.push(tween(120, function (p) {
          R.alpha = p; R.pos = [0, 0, 0]; R.scl = [1, 1, 1];
          S.frame.k = p;
          if (old) old.root.alpha = 1 - p;
        }));
      } else {
        // With nothing to lift (the first tool), the drop starts at once.
        var lead = old ? 180 : 0;
        total = lead + 450;
        if (old) {
          var O = old.root;
          sw.tweens.push(tween(180, function (p) {
            var e = M.ease.inQuad(p);
            O.pos = [0, 0.55 * e, 0]; O.alpha = 1 - p;
          }));
        }
        R.alpha = 0; R.pos = [0, 1.4, 0];
        var landed = false;
        // The new tool drops after the old one has gone: 450ms of fall, contact, and a 4%
        // squash that overshoots and settles.
        sw.tweens.push(tween(total, function (p) {
          // The framing travels while the old tool lifts and the new one falls in.
          if (S.frame) S.frame.k = M.ease.inOutSine(Math.min(1, p * total / (lead + 225)));
          var q = (p * total - lead) / 450;
          if (q < 0) { R.alpha = 0; return; }
          if (q < 0.5) {
            var f = q / 0.5;
            R.pos = [0, 1.4 * (1 - f * f), 0];
            R.alpha = Math.min(1, f * 3);
            R.scl = [1, 1 + 0.03 * f, 1];
          } else {
            if (!landed) {
              landed = true;
              FX.emit("dust", [0, 0.02, 0], { count: 8, spread: 0.5, up: 0.2 });
            }
            var s = (q - 0.5) / 0.5;
            var sy = 1 - 0.04 * Math.cos(s * Math.PI * 3) * (1 - s) * (1 - s);
            R.pos = [0, 0, 0]; R.alpha = 1;
            R.scl = [1 + (1 - sy) * 0.5, sy, 1 + (1 - sy) * 0.5];
          }
        }));
      }
      sw.tweens[sw.tweens.length - 1].done = function () { if (S.swap === sw) finishSwap(); };
      // A promise that waits on frames would hang in a background tab; this does not.
      sw.timer = setTimeout(function () { if (S.swap === sw) finishSwap(); }, total + 200);
      wake();
    });
  }

  /* --- ingredient chips ------------------------------------------------------------------ */
  function chipSpot(T, i) {
    var c = T.chip, perRow = c.ground ? 9 : 7;
    var row = Math.floor(i / perRow), k = i % perRow;
    var r = c.r + row * (c.ground ? 0.17 : 0);
    var y = c.ground ? c.y : c.y + row * 0.06;
    var stepA = 0.17 / r, off = (k % 2 ? 1 : -1) * Math.ceil(k / 2) * stepA;
    var a = c.arc * D2R + off + (row % 2) * stepA * 0.5;
    var ox = (T.ring && T.ring.x) || 0, oz = (T.ring && T.ring.z) || 0;
    if (c.ground) { ox = 0; oz = 0; }
    return [ox + Math.cos(a) * r, y, oz + Math.sin(a) * r, a];
  }

  function layoutChips(snap) {
    var T = S.tool;
    if (!T) return;
    S.chips.forEach(function (ch, i) {
      var p = chipSpot(T, i);
      ch.home = p;
      if (snap || !ch.dropping) { ch.node.pos = [p[0], p[1], p[2]]; ch.node.rot = [0, -p[3] + Math.PI / 2, 0]; }
    });
    wake();
  }

  function addIngredient(it) {
    if (!it || it.key === undefined || it.key === null) return;
    var key = String(it.key);
    for (var i = 0; i < S.chips.length; i++) {
      if (S.chips[i].key === key) return;
    }
    var part = it.part || "leaf";
    var ch = { key: key, part: part, name: it.name || "", node: K.props.chip(part), dropping: true };
    S.chips.push(ch);
    S.chipGroup.kids.push(ch.node);
    var T = S.tool;
    var p = T ? chipSpot(T, S.chips.length - 1) : [0, 0, 0.9, Math.PI / 2];
    ch.home = p;
    ch.node.rot = [0, -p[3] + Math.PI / 2, 0];
    sound("bench.drop." + part);
    if (!S.mounted || S.reduced) {
      ch.node.pos = [p[0], p[1], p[2]];
      ch.dropping = false;
      wake();
      return;
    }
    tween(320, function (q) {
      var h = ch.home, e = q < 0.7 ? 1 - Math.pow(q / 0.7, 2) : Math.sin((q - 0.7) / 0.3 * Math.PI) * 0.12;
      ch.node.pos = [h[0], h[1] + 0.6 * e, h[2]];
      ch.node.alpha = Math.min(1, q * 4);
    }, function () {
      ch.dropping = false;
      ch.node.pos = [ch.home[0], ch.home[1], ch.home[2]];
      FX.emit("dust", [ch.home[0], ch.home[1] + 0.02, ch.home[2]], { count: 2, size: 0.5 });
    });
  }

  function dropChip(ch, after) {
    var i = S.chips.indexOf(ch);
    if (i >= 0) S.chips.splice(i, 1);
    function gone() {
      var j = S.chipGroup.kids.indexOf(ch.node);
      if (j >= 0) S.chipGroup.kids.splice(j, 1);
      if (after) after();
    }
    if (!S.mounted || S.reduced) { gone(); return; }
    var y0 = ch.node.pos[1];
    tween(150, function (q) { ch.node.alpha = 1 - q; ch.node.pos[1] = y0 + 0.15 * q; }, gone);
  }

  function removeIngredient(key) {
    key = String(key);
    for (var i = 0; i < S.chips.length; i++) {
      if (S.chips[i].key === key) { dropChip(S.chips[i], function () { layoutChips(false); }); layoutChips(false); return; }
    }
  }

  function clearIngredients() {
    S.chips.slice().forEach(function (ch) { dropChip(ch); });
    wake();
  }

  /* --- the drop ring --------------------------------------------------------------------- */
  function buildRing() {
    var T = S.tool;
    if (!T) { S.ringNode = null; return; }
    if (!T.ringNode) {
      T.ringNode = K.props.dropRing(T.ring.r);
      T.ringNode.pos = [T.ring.x || 0, T.ring.y, T.ring.z || 0];
    }
    S.ringNode = T.ringNode;
    S.ringNode.visible = S.ringShown;
    S.ringNode.alpha = S.ringShown ? 1 : 0;
    S.ringNode.scl = [1, 1, 1];
  }

  function setDragOver(on) {
    on = !!on;
    if (on === S.ringShown) return;
    S.ringShown = on;
    var n = S.ringNode;
    if (!n) return;
    if (S.ringTween) endTween(S.ringTween);
    if (S.reduced || !S.mounted) { n.visible = on; n.alpha = on ? 1 : 0; n.scl = [1, 1, 1]; wake(); return; }
    n.visible = true;
    S.ringTween = tween(on ? 160 : 120, function (p) {
      var e = M.ease.outCubic(p), k = on ? 1.12 - 0.12 * e : 1 + 0.06 * e;
      n.alpha = on ? e : 1 - e;
      n.scl = [k, 1, k];
    }, function () { S.ringTween = null; n.visible = on; });
  }

  /* --- the game -------------------------------------------------------------------------- */
  function game(method) {
    var T = toolFor(method);
    function onTool() { return T && S.tool === T; }
    var view = {
      update: safe("game.update", function (state) {
        if (!T || !state) return;
        if (!T.isLive) { T.isLive = true; T.begin(); }
        T.pose(state);
        S.gameLast = now();
        if (onTool()) wake();
      }),
      hit: safe("game.hit", function (strength) {
        if (!onTool()) return;
        var s = Math.max(0, Math.min(1, +strength || 0));
        T.hit(s, FX);
        S.flare = Math.max(S.flare, 0.45 + 0.75 * s);
        if (!S.reduced) {
          S.nudge = 1.5; S.nudgeAt = now();
          S.punch = Math.max(S.punch, 0.6 + 0.4 * s);
        }
        wake();
      }),
      miss: safe("game.miss", function () {
        if (!onTool()) return;
        T.miss(FX);
        wake();
      }),
      end: safe("game.end", function () {
        if (!T) return;
        T.isLive = false;
        T.end();
        if (onTool()) wake();
      })
    };
    return view;
  }

  /* --- flourishes ------------------------------------------------------------------------ */
  function flourish(kind) {
    return new Promise(function (resolve) {
      if (!S.mounted || !S.tool) { resolve(false); return; }
      var T = S.tool, R = T.root, work = M.xform(rootMatrix(T), T.work);
      var top = [work[0], work[1] + 0.25, work[2]];
      if (kind === "tierUp") {
        sound("bench.tier.up");
        FX.emit("gilt", top, { count: 14, speed: 0.6 });
        S.flare = Math.max(S.flare, 0.9);
        tween(380, function (p) { S.glint = Math.sin(Math.PI * p) * 0.9; }, function () { S.glint = 0; resolve(true); });
      } else if (kind === "flawless") {
        sound("bench.flawless");
        FX.emit("gilt", top, { count: 90, speed: 1.1 });
        FX.emit("spark", top, { count: 24 });
        S.flare = Math.max(S.flare, 1.8);
        var cv = S.canvas, shook = !S.reduced;
        tween(700, function (p) { S.glint = Math.sin(Math.PI * p) * 1.2; }, function () { S.glint = 0; resolve(true); });
        if (shook) {
          // The STAGE canvas shakes, never the page: a transform on this one element.
          tween(250, function (p) {
            var a = 7 * (1 - p) * (1 - p);
            cv.style.transform = p >= 1 ? "" :
              "translate(" + (Math.sin(p * 71) * a).toFixed(2) + "px," + (Math.cos(p * 53) * a).toFixed(2) + "px)";
          }, function () { cv.style.transform = ""; });
        }
      } else if (kind === "fail") {
        sound("bench.fail");
        FX.emit("smoke", top, { count: 6, spread: 0.2 });
        tween(600, function (p) {
          S.dim = p < 0.12 ? 1 - 0.3 * (p / 0.12) : (p < 0.55 ? 0.7 : 0.7 + 0.3 * M.ease.inOutSine((p - 0.55) / 0.45));
          if (!S.reduced) {
            var a = p < 0.6 ? 0.045 * (1 - p / 0.6) : 0;
            R.rot = [0, 0, Math.sin(p * 60) * a];
          }
        }, function () { S.dim = 1; R.rot = [0, 0, 0]; resolve(true); });
      } else if (kind === "land") {
        sound("bench.land");
        showProduct(T, work, resolve);
      } else {
        resolve(false);
      }
      wake();
    });
  }

  function showProduct(T, work, resolve) {
    if (S.product) { var j = S.product; j.visible = false; }
    S.product = K.props.product(T.method, T.liquid);
    S.product.visible = true;
    S.productOn = true;
    var base = [work[0], work[1] + 0.05, work[2]], rise = 0.42;
    S.productTop = [base[0], base[1] + rise, base[2]];
    var P = S.product, k0 = P.base || 1;
    if (S.reduced) {
      // Reduced motion: no rise; it is simply there at the top, then gone.
      P.pos = S.productTop.slice();
      P.scl = [k0, k0, k0];
      tween(1000, function (p) { P.alpha = p < 0.15 ? p / 0.15 : (p > 0.85 ? (1 - p) / 0.15 : 1); },
            function () { S.productOn = false; resolve(true); });
      return;
    }
    FX.emit("gilt", base, { count: 10, speed: 0.4 });
    tween(1050, function (p) {
      var q = Math.min(1, p / 0.43), e = M.ease.outCubic(q);
      P.pos = [base[0], base[1] + rise * e, base[2]];
      P.rot = [0, e * Math.PI * 1.2, 0];
      var k = (0.7 + 0.3 * e) * k0;
      P.scl = [k, k, k];
      P.alpha = p > 0.86 ? (1 - p) / 0.14 : Math.min(1, q * 3);
    }, function () { S.productOn = false; resolve(true); });
  }

  /* Where the product is (or, before `land`, where it will rise to), in viewport pixels,
     so D can fly its own copy from there to the satchel tile. */
  function productRect() {
    var Rect = window.DOMRect || function (x, y, w, h) {
      return { x: x, y: y, width: w, height: h, left: x, top: y, right: x + w, bottom: y + h };
    };
    if (!S.mounted || !S.canvas) {
      if (S.host && S.host.getBoundingClientRect) {
        var hb = S.host.getBoundingClientRect();
        return new Rect(hb.left + hb.width / 2 - 30, hb.top + hb.height / 2 - 30, 60, 60);
      }
      return new Rect(0, 0, 0, 0);
    }
    var T = S.tool;
    var c = S.productOn && S.product ? S.product.pos
      : (T ? M.add(M.xform(rootMatrix(T), T.work).slice(0, 3), [0, 0.47, 0]) : [0, 1, 0]);
    var cam = S.cam || camera();
    var ks = (S.product && S.product.base) || 1.7;
    var mid = [c[0], c[1] + 0.12 * ks, c[2]];
    var v = M.xform(cam.vp, mid);
    var b = S.canvas.getBoundingClientRect();
    var sx = b.left + (v[0] / v[3] * 0.5 + 0.5) * b.width;
    var sy = b.top + (1 - (v[1] / v[3] * 0.5 + 0.5)) * b.height;
    var pxPerUnit = b.height / (2 * cam.t) / v[3];
    var w = Math.max(24, 0.3 * ks * pxPerUnit), h = Math.max(24, 0.36 * ks * pxPerUnit);
    return new Rect(sx - w / 2, sy - h / 2, w, h);
  }

  /* --- mount ----------------------------------------------------------------------------- */
  var available = function () {
    if (!READY) return false;
    try { return K.supported(); } catch (e) { return false; }
  };

  function onLost(e) {
    // Khronos' recipe: claim the loss, or the browser will never offer it back.
    e.preventDefault();
    S.lost = true;
    if (S.raf) { window.cancelAnimationFrame(S.raf); S.raf = 0; }
  }
  function onRestored() {
    S.lost = false;
    if (S.r && S.r.init()) { S.lastT = 0; wake(); }
  }

  function mount(host) {
    return new Promise(function (resolve) {
      try {
        if (!host || !available()) { resolve(false); return; }
        if (S.mounted) unmount();
        var cv = document.createElement("canvas");
        cv.className = "bench-stage-canvas";
        cv.setAttribute("aria-hidden", "true");
        cv.style.cssText = "position:absolute;left:0;top:0;width:100%;height:100%;display:block;" +
                           "pointer-events:none;";
        if (window.getComputedStyle && getComputedStyle(host).position === "static") host.style.position = "relative";
        host.appendChild(cv);
        var r = new K.Renderer(cv);
        if (!r.init()) { host.removeChild(cv); resolve(false); return; }
        S.host = host; S.canvas = cv; S.r = r; S.mounted = true; S.lost = false;
        cv.addEventListener("webglcontextlost", onLost, false);
        cv.addEventListener("webglcontextrestored", onRestored, false);
        if (window.ResizeObserver) {
          S.ro = new ResizeObserver(function () { resize(); });
          S.ro.observe(host);
        } else {
          window.addEventListener("resize", resize);
        }
        resize();
        applyGround();
        buildRing();
        layoutChips(true);
        if (S.tool) S.tool.root.visible = true;
        // The ground fades in from the page's dark, then the tool is simply there.
        S.reveal = 0;
        tween(S.reduced ? 120 : 320, function (p) { S.reveal = M.ease.outCubic(p); });
        draw();
        resolve(true);
      } catch (e) {
        warn("mount", e);
        try { unmount(); } catch (e2) { /* nothing left to undo */ }
        resolve(false);
      }
    });
  }

  function unmount() {
    finishSwap();
    if (S.raf) { window.cancelAnimationFrame(S.raf); S.raf = 0; }
    S.tweens.slice().forEach(endTween);
    S.tweens = [];
    if (S.particles) S.particles.clear();
    if (S.ro) { S.ro.disconnect(); S.ro = null; } else { window.removeEventListener("resize", resize); }
    if (S.canvas) {
      S.canvas.removeEventListener("webglcontextlost", onLost, false);
      S.canvas.removeEventListener("webglcontextrestored", onRestored, false);
    }
    if (S.r) {
      try {
        S.r.dispose();
        var ext = S.r.gl && S.r.gl.getExtension("WEBGL_lose_context");
        // Give the context back now rather than at garbage collection: a page may hold
        // only a handful, and the dice and the bench both want one.
        if (ext) ext.loseContext();
      } catch (e) { /* already gone */ }
    }
    if (S.canvas && S.canvas.parentNode) S.canvas.parentNode.removeChild(S.canvas);
    S.r = null; S.canvas = null; S.host = null; S.mounted = false; S.groundRec = null;
    S.productOn = false; S.dim = 1; S.glint = 0; S.flare = 0;
  }

  function setGround(g) {
    g = g || {};
    S.ground = { biome: g.biome || "", roofed: !!g.roofed, minute: +g.minute || 0, place: g.place || "" };
    applyGround();
  }

  function reducedMotion(on) {
    S.reduced = !!on;
    if (S.reduced && S.particles) S.particles.clear();
    if (S.reduced && S.canvas) S.canvas.style.transform = "";
  }

  /* For the harness and the verification notes: frames drawn, draw calls, frame times,
     and how tall the tool stands on the stage. Not part of the contract. */
  function debug() {
    var ms = S.stats.ms.slice().sort(function (a, b) { return a - b; });
    var sum = ms.reduce(function (a, b) { return a + b; }, 0);
    var out = { frames: S.stats.frames, draws: S.stats.draws, lastDraws: S.stats.lastDraws,
                rafs: S.stats.rafs, raf: !!S.raf, avgMs: ms.length ? sum / ms.length : 0,
                p95Ms: ms.length ? ms[Math.floor(ms.length * 0.95)] : 0,
                maxMs: ms.length ? ms[ms.length - 1] : 0,
                ground: S.groundRec ? S.groundRec.kind : null,
                groundPaintMs: S.groundRec ? S.groundRec.ms : 0,
                tool: S.tool ? S.tool.method : null, particles: S.particles ? S.particles.alive() : 0,
                buffer: S.canvas ? [S.canvas.width, S.canvas.height] : null,
                refFraction: S.cam ? S.cam.frac : null };
    if (S.tool && S.cam && S.mounted) out.toolFraction = toolFraction();
    return out;
  }
  function resetStats() { S.stats.frames = 0; S.stats.draws = 0; S.stats.ms = []; S.stats.rafs = 0; }

  /* The tool's own projected height over the stage's height, from EVERY vertex of its solid
     parts as it stands now: the measurement, kept independent of the thinned fit above. */
  function toolFraction() {
    var items = [], lo = Infinity, hi = -Infinity;
    collect(S.tool.root, M.ident(), 1, 0, items);
    items.forEach(function (it) {
      if (it.n.mat.pass === "add" || it.n.mat.radial) return;
      var P = it.n.mesh.pos;
      for (var i = 0; i < P.length; i += 3) {
        var w = M.xform(it.m, [P[i], P[i + 1], P[i + 2]]), v = M.xform(S.cam.vp, [w[0], w[1], w[2]]);
        var y = v[1] / v[3];
        lo = Math.min(lo, y); hi = Math.max(hi, y);
      }
    });
    return (hi - lo) / 2;
  }

  if (READY) {
    S.particles = new K.Particles();
    S.chipGroup = K.props.group();
    S.shadow = K.props.node(K.mesh.disc(0.85, 40), K.props.mat("shadow", { alpha: 0.5 }), { pos: [0, 0.003, 0], glint: false });
  }

  function noop() {}
  function resolved(v) { return function () { return Promise.resolve(v); }; }
  var NOGAME = { update: noop, hit: noop, miss: noop, end: noop };

  window.BenchStage = READY ? {
    available: safe("available", available, false),
    mount: function (host) { try { return mount(host); } catch (e) { warn("mount", e); return Promise.resolve(false); } },
    unmount: safe("unmount", unmount),
    setGround: safe("setGround", setGround),
    setTool: function (m) { try { return setTool(m); } catch (e) { warn("setTool", e); return Promise.resolve(false); } },
    addIngredient: safe("addIngredient", addIngredient),
    removeIngredient: safe("removeIngredient", removeIngredient),
    clearIngredients: safe("clearIngredients", clearIngredients),
    setDragOver: safe("setDragOver", setDragOver),
    game: function (m) { try { return game(m); } catch (e) { warn("game", e); return NOGAME; } },
    flourish: function (k) { try { return flourish(k); } catch (e) { warn("flourish", e); return Promise.resolve(false); } },
    productRect: safe("productRect", productRect, null),
    reducedMotion: safe("reducedMotion", reducedMotion),
    _debug: safe("_debug", debug, null),
    _resetStats: safe("_resetStats", resetStats)
  } : {
    // The parts did not load: every call is a quiet no-op, and D shows its flat stage.
    available: function () { return false; },
    mount: resolved(false), unmount: noop, setGround: noop, setTool: resolved(false),
    addIngredient: noop, removeIngredient: noop, clearIngredients: noop, setDragOver: noop,
    game: function () { return NOGAME; }, flourish: resolved(false),
    productRect: function () { return window.DOMRect ? new window.DOMRect(0, 0, 0, 0) : null; },
    reducedMotion: noop,
    _debug: function () { return null; }, _resetStats: noop
  };
})();
