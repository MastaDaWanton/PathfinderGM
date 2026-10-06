// The play table, part 47 (the enchanting bench's 3D stage). Classic script; everything it
// defines lives inside one IIFE and leaves exactly one global, window.EnchantStage, because the
// table's numbered modules share a single global scope.
//
// WHAT IT IS. The middle of the enchanting bench (UI plan §6.3, §7; the owner's ruling, answers
// round 3: "the item on a circle of chalk and inks, lit by candles and the essence's glow"): the
// vessel at the heart of a chalk circle, eight candles round it, the essence phials on their
// seats at the front of the circle, ink, chalk and the method's tool at the edges, on the ground
// you stand on at camp, on planks under a roof, or on a sanctum's flags. Its interface is the UI
// plan §7.1 with the owner's correction that there are no planets (answers round 4, point 10:
// the day's phases), and lane U1 builds against nothing else:
//
//   available() mount(host) unmount() setScene({kind, biome, roofed, minute})
//   setTool(method) setVessel({gear, base, pieces, family, quality_index, slot, name, key})
//   setSeats([{seat, essence, color, phase, seated, lit}]) hour({phase, now, inside,
//   minutes_left, widen}) game(method) flourish(kind) productRect() reducedMotion(bool)
//
// `kind` is "camp" | "roofed" | "sanctum" | "hired". `base` may be the weapon or armour id or
// the table row (forge-stage/02-families.js reads either); `pieces[slot].color` is the server's
// swatch ("#rrggbb", or [r, g, b]); without one a small table of common metals stands in.
// `family` forces one of the jewellery and wearable families (enchant-stage/02-vessels.js);
// without it a ring is a ring and any other wondrous vessel's family is read from its slot.
// A seat's `color` is its essence's own (lane D's `color`, "#rrggbb"): it lights the phial, the
// seat's mark and the glow. `hour` accepts lane E's `state.hour` ({phase: now}) and its check
// `hour` ({phase: the essence's, now, inside}); the phase NOW tints the light a little, and the
// essence's own phase, when the clock is inside it, warms its glow a little more.
//
// THE GAME VIEW. game(method) returns {update(state), hit(strength, index), miss(index), end()},
// the shape both other stages have, so 33-bench-games.js hands it states unchanged. Every state
// key is optional, and the stage shows what it is given (UI plan §9's "on the stage" column):
//   prepare  seq [kinds], placed n   the rings, the figure, the salt and the sigils draw on as
//                                    chalk, salt and ink are placed; hit(s, i) places step i,
//                                    miss(i) scuffs the chalk; a bell step flashes the bell
//   attune   seats [{matched}]       each matched seat's mark lights in its essence's colour;
//                                    hit(s, i) lights seat i, miss(i) puffs dust at it
//   bind     light 0..1, window 0..1, pour 0..1
//                                    the light runs round the ring to crest at the front; the
//                                    window is the crest's arc (wider in the essence's phase);
//                                    hit(s) pours the essence's light into the vessel
//   refine   draw 0..1, purity 0..1  motes rise from the first seat's phial; hit/miss
//   unbind, cleanse  seq [kinds], picked n, curse [indices]
//                                    the item's sigils glow; each pick (hit(s, i)) fades the
//                                    last-cut sigil and lets its essence out as mist; Cleanse
//                                    shows the curse's sigils in a darker line
//
// HOW IT IS BUILT. By hand, in WebGL1, on the herb stage's renderer, maths, meshes, grounds and
// particles (play/static/js/bench-stage/00-04, as they are), the forge's node helpers, weapon
// and armour families and painted smithy room (forge-stage/01-03, as they are), and the
// circle's own parts in play/static/js/enchant-stage/. The app bundles no third-party JavaScript.
//
// THE LIGHT. The house shader's three point lights are spent on the circle's three lights (UI
// plan §6.3): the CANDLE RING is the key, warm, at the circle's centre above the vessel; the
// ESSENCE is the second, the seated essences' colour, brightening as the binding pours into the
// work; the BIND FLASH is the third. Each candle flame is an emissive mesh with a halo card, not
// a light. The fill is the sky outdoors and a little cool daylight indoors, by the scene clock,
// tinted (never more than about a fifth) toward the day's phase: rose at dawn, white at noon,
// amber at dusk, blue at night and midnight.
//
// RENDER ON DEMAND (UI plan §7.3: "idle, the candles are lit steadily and the bench draws no
// frames"). Nothing draws until something asks, and a frame only schedules the next while
// something still moves: a tween, a line drawing on, a live game, a particle not yet dead. The
// candle flicker would keep a loop alive for ever, so it runs only while a game is sending
// states. `wake` is the only place requestAnimationFrame is called, and it refuses while the
// bench is HIDDEN (its box has no size: the layer is closed or display:none) or the TAB is in
// the background (the Page Visibility API's `document.hidden`): a hidden canvas drawing at 60
// frames a second costs the same GPU as a visible one, and rAF only stops by itself for a
// background tab, never for a hidden element (MDN, Page Visibility API). Tweens carry a timer as
// well as the frame clock, so a flourish's promise resolves on time even while hidden.
//
// REDUCED MOTION (the device lane's pattern, 13-device.js `still()`): the OS setting, the
// player's Short flourishes, or reducedMotion(true). Held still: no flicker, no particles, no
// shake, no drop; the circle's lines appear instead of drawing on, the candles are all lit at
// once, and the flourishes keep only what carries information (a seat lights, a candle is out).
//
// WHAT IT MAY NOT DO (the owner's rule: no motion that makes a menu harder to use). The canvas
// takes no pointer events, every flourish ends on its own inside 1.1 s, and the Flawless shake
// moves the STAGE canvas only. Nothing here can throw into a caller: without WebGL every call is
// a quiet no-op and `available()` says false, so U1 shows its flat icon stage.
(function () {
  "use strict";

  var K = window.BenchStageKit || {};
  var F = window.ForgeStageKit || {};
  var E = window.EnchantStageKit || {};
  var M = K.math, G = K.mesh;
  var READY = !!(K.math && K.Renderer && K.mesh && K.ground && K.Particles &&
                 F.props && F.families && F.smithy &&
                 E.circle && E.props && E.vessels && E.room && E.fx);
  var D2R = Math.PI / 180, TAU = Math.PI * 2;
  var BG = [13 / 255, 11 / 255, 9 / 255];          // --bg, #0d0b09
  var CANDLE = [0.94, 0.75, 0.44];                  // --candle, #f0c070
  var MAX_PIXELS = 3840 * 2160;
  var PITCH = 50;                                   // UI plan §6.3: "about 50° looking down"
  var METHODS = ["prepare", "attune", "bind", "refine", "unbind", "cleanse", "read", "identify"];
  var SLOTS = { weapon: ["head", "haft", "fittings"], armour: ["body", "fastenings", "lining"],
                shield: ["body", "fastenings", "lining"] };
  // The day's phases (rules/sky.py) and the tint each puts on the fill. Kept small on purpose:
  // the phase is a time of day, not a filter, and the candles stay the light that matters.
  var PHASES = ["dawn", "morning", "noon", "afternoon", "dusk", "night", "midnight"];
  var TINT = { dawn: [1.06, 0.9, 0.9], morning: [1.0, 0.99, 0.96], noon: [1, 1, 1],
               afternoon: [1.02, 0.98, 0.92], dusk: [1.1, 0.88, 0.72], night: [0.84, 0.92, 1.1],
               midnight: [0.74, 0.84, 1.16] };

  var S = {
    host: null, canvas: null, r: null, ro: null, mounted: false, lost: false, raf: 0, lastT: 0,
    hiddenBox: false, hiddenTab: false,
    scene: { kind: "camp", biome: "", roofed: false, minute: 21 * 60 },
    sets: {}, set: null, groundRec: null, groundNode: null,
    method: null, tools: {}, tool: null, leaving: null, swap: null,
    vessel: null, vesselRoot: null, vesselGone: false, vesselKey: "",
    seats: [], hour: null, flawed: false,
    sp: null, game: null, gameOn: false, gameLast: 0, flick: 1, moteAt: 0,
    particles: null, tweens: [], reduced: false,
    flare: 0, flareCol: CANDLE, glint: 0, nudge: 0, nudgeAt: 0, dim: 1, reveal: 1, pour: 0,
    sigFlash: 0, runA: null, cssW: 1, cssH: 1, cam: null, fit: null,
    stats: { frames: 0, draws: 0, lastDraws: 0, ms: [], rafs: 0, key: [0, 0, 0], glow: [0, 0, 0], fill: [0, 0, 0] }
  };

  function now() { return (window.performance && performance.now) ? performance.now() : Date.now(); }
  function sound(name, opts) {
    try { if (window.Sound && typeof window.Sound.play === "function") window.Sound.play(name, opts); } catch (e) { /* silent */ }
  }
  function warn(where, e) {
    if (window.console && console.warn) console.warn("EnchantStage." + where + ":", e && e.message ? e.message : e);
  }
  /* Every public method goes through this: a stage bug must never break the bench. */
  function safe(where, fn, fallback) {
    return function () {
      try { return fn.apply(null, arguments); } catch (e) { warn(where, e); return fallback; }
    };
  }
  function num(x, d) { x = +x; return isFinite(x) ? x : d; }
  function clamp01(x) { x = +x; return isFinite(x) ? Math.max(0, Math.min(1, x)) : 0; }

  // Reduced motion, asked the way 13-device.js's still() asks it (the OS setting or Short
  // flourishes), plus the bench's own reducedMotion(true).
  var STILL = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  function still() {
    if (S.reduced) return true;
    try {
      if (STILL && STILL.matches) return true;
      return !!(window.PGMPrefs && window.PGMPrefs.get("flourishes") === "short");
    } catch (err) { return false; }
  }

  /* Eased values (the forge's): each closes a fixed fraction of its gap a second, and ENDS. */
  function Springs() { this.v = {}; this.t = {}; this.r = {}; this.lin = {}; }
  Springs.prototype.set = function (k, v, rate) {
    if (!(k in this.v)) this.v[k] = v;
    this.t[k] = v;
    if (rate) this.r[k] = rate;
  };
  /* A value that moves at a constant speed (units a second): a chalk line draws on at a
     hand's pace, it does not ease in like a camera. */
  Springs.prototype.linear = function (k, v, speed) {
    if (!(k in this.v)) this.v[k] = v;
    this.t[k] = v; this.lin[k] = speed;
  };
  Springs.prototype.snap = function (k, v) { this.v[k] = this.t[k] = v; };
  Springs.prototype.get = function (k) { return this.v[k] === undefined ? 0 : this.v[k]; };
  Springs.prototype.step = function (dt) {
    var moving = false;
    for (var k in this.t) {
      var d = this.t[k] - this.v[k];
      if (Math.abs(d) <= 1e-4) { this.v[k] = this.t[k]; continue; }
      moving = true;
      if (this.lin[k]) {
        var s = this.lin[k] * dt;
        this.v[k] = Math.abs(d) <= s ? this.t[k] : this.v[k] + (d > 0 ? s : -s);
      } else {
        this.v[k] += d * (1 - Math.exp(-dt * (this.r[k] || 10)));
      }
    }
    return moving;
  };
  Springs.prototype.settle = function () { for (var k in this.t) this.v[k] = this.t[k]; };

  /* --- the frame loop ------------------------------------------------------------------ */

  // ENCHANT-STAGE-RAF: the only requestAnimationFrame in the stage. It is reached from wake()
  // and nowhere else, wake() is only called when something changed, and it asks for no frame
  // while the bench is hidden or the tab is in the background.
  function wake() {
    if (S.raf || !S.mounted || S.lost || S.hiddenBox || S.hiddenTab) return;
    S.stats.rafs++;
    S.raf = window.requestAnimationFrame(frame);
  }

  function frame(tms) {
    S.raf = 0;
    if (!S.mounted || S.lost || S.hiddenBox || S.hiddenTab) { S.lastT = 0; return; }
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

  /* Tweens run on the wall clock, and each carries a timer too: a frame-only tween started
     while the bench is hidden would never end, and a flourish's promise would hang with it. */
  function tween(dur, fn, done) {
    var tw = { start: now(), dur: Math.max(1, dur), fn: fn, done: done };
    S.tweens.push(tw);
    fn(0);
    tw.timer = setTimeout(function () { endTween(tw); }, tw.dur + 120);
    wake();
    return tw;
  }
  function endTween(tw) {
    var i = S.tweens.indexOf(tw);
    if (i < 0) return;
    S.tweens.splice(i, 1);
    if (tw.timer) clearTimeout(tw.timer);
    tw.fn(1);
    if (tw.done) tw.done();
    wake();
  }

  function isLive(t) { return S.gameOn && (t - S.gameLast) < 300; }

  function step(dt, t) {
    var busy = false, i;
    for (i = S.tweens.length - 1; i >= 0; i--) {
      var tw = S.tweens[i];
      if (!tw) continue;
      var p = Math.min(1, (t - tw.start) / tw.dur);
      if (p >= 1) endTween(tw); else { tw.fn(p); busy = true; }
    }
    if (S.tweens.length) busy = true;
    if (still()) S.sp.settle();
    if (S.sp.step(dt)) busy = true;
    if (isLive(t)) {
      busy = true;
      liveStep(dt, t / 1000);
    } else {
      S.flick = 1;
    }
    if (S.particles.alive()) { S.particles.step(dt, t / 1000); busy = true; }
    else S.particles.counts[0] = S.particles.counts[1] = 0;
    if (S.flare > 0.005) { S.flare *= Math.exp(-dt * 9); busy = true; } else S.flare = 0;
    if (S.nudge > 0) { if ((t - S.nudgeAt) / 60 >= 1) S.nudge = 0; else busy = true; }
    applyPose(t / 1000, isLive(t));
    return busy;
  }

  /* While a game is live: the candles breathe and the seated essences send up a mote now and
     then. None of it runs when the game stops sending states. */
  function liveStep(dt, ts) {
    if (still()) { S.flick = 1; return; }
    // A slow, low wobble: incommensurate sines, never a strobe (the forge's hearth, quieter).
    S.flick = 1 + 0.05 * Math.sin(ts * 6.1) + 0.035 * Math.sin(ts * 11.3 + 1.7) + 0.02 * Math.sin(ts * 19.7);
    if (ts - S.moteAt > 0.35 && (S.method === "attune" || S.method === "bind" || S.method === "refine")) {
      S.moteAt = ts;
      S.set.seatNodes.forEach(function (sn, k) {
        if (sn.seat && sn.seat.seated && (S.method !== "refine" || k === 0)) E.fx.motes(FX.emit, phialTop(k), sn.col, 1);
      });
    }
  }

  /* --- the set: candles, circle, seats, near props (built once a session) ---------------- */

  function buildSet() {
    // The whole set stands 3 mm up: the chalk is drawn 2 mm off the floor, and a sanctum's rug
    // is 2 mm thick, which buried every line in the first sanctum capture.
    var P = E.props, C = E.circle, FP = F.props, root = FP.group({ pos: [0, 0.003, 0] });
    var set = { root: root, candles: [], rings: [], sigils: [], seatNodes: [], props: {} };
    // The dust under the circle: painted once, laid as one additive quad (00-circle.js).
    var dust = C.paintDust();
    set.dust = FP.add(root, FP.node(G.plane(dust.span), FP.mat("chalk", {
      color: [0.9, 0.88, 0.82], tex: dust, uvScale: [1 / dust.span, 1 / dust.span], pass: "add", alpha: 0.55,
      spec: 0.05, shin: 6, pattern: 0, order: 0 }), { pos: [0, 0.001, 0], glint: false }));
    set.dust.noFit = true;
    var chalk = P.mat("chalk");
    set.chalkMat = chalk;
    // Three rings, each starting its draw-on at a different angle so the chalk is seen to go
    // round by hand rather than all three growing in step.
    [[C.R.OUTER, C.R.LINE * 1.15, Math.PI * 0.5], [C.R.OUTER2, C.R.LINE * 0.7, Math.PI * 1.1],
     [C.R.INNER, C.R.LINE, Math.PI * 1.6]].forEach(function (d) {
      var mesh = C.chalkRing(d[0], d[1]);
      var n = FP.add(root, FP.node(mesh, chalk, { pos: [0, 0.0016, 0], scl: [1, 0.2, 1], glint: false }));
      n.a0 = d[2];
      set.rings.push(n);
    });
    set.figure = FP.add(root, FP.node(C.figure(), P.mat("chalk"), { glint: false }));
    set.salt = FP.add(root, FP.node(C.salt(), P.mat("salt"), { glint: false }));
    // The sigils: a node per slot, its mesh chosen per vessel (setVessel), its own material so
    // each can glow, fade and darken on its own.
    C.SIGIL_SLOTS.forEach(function (slot) {
      var a = C.slotAngle(slot);
      var n = FP.add(root, FP.node(C.runeMesh(0, 0.12), P.mat("chalk", { emit: [0, 0, 0] }), {
        pos: [Math.cos(a) * C.R.BAND, 0.0012, Math.sin(a) * C.R.BAND],
        rot: [0, Math.atan2(-Math.cos(a), -Math.sin(a)), 0], glint: false }));
      n.slot = slot;
      set.sigils.push(n);
    });
    // The seats' marks, at the front of the band; their phials are made per seat (setSeats).
    var sm = C.seatMark();
    C.SEAT_SLOTS.forEach(function (slot) {
      var a = C.slotAngle(slot), pos = [Math.cos(a) * C.R.BAND, 0, Math.sin(a) * C.R.BAND];
      var g = FP.add(root, FP.group({ pos: pos, visible: false }));
      var ringM = P.mat("chalk", { emit: [0, 0, 0] });
      var mark = FP.add(g, FP.node(sm.ring, ringM, { pos: [0, 0.0016, 0], scl: [1, 0.25, 1], glint: false }));
      var dot = FP.add(g, FP.node(sm.dot, ringM, { pos: [0, 0.0018, 0], glint: false }));
      var glow = FP.add(g, FP.node(G.disc(0.16, 32), P.mat("seatglow", { alpha: 0 }), { pos: [0, 0.006, 0], glint: false }));
      glow.noFit = true;
      set.seatNodes.push({ root: g, mark: mark, dot: dot, glow: glow, ringMat: ringM, pos: pos, slot: slot,
                           phial: null, col: [0.8, 0.78, 0.7], seat: null });
    });
    // Eight candles: at the quarters (taller) and between (shorter), each burnt down a little
    // differently, so the ring reads as candles that have been used before.
    var rnd = M.rng(1307);
    for (var i = 0; i < 8; i++) {
      var a = i / 8 * TAU, quarter = i % 2 === 0;
      var h = (quarter ? 0.2 : 0.13) * (0.72 + rnd() * 0.28);
      var cd = P.candle(Math.round(h * 200) / 200, quarter ? 0.03 : 0.024);
      cd.root.pos = [Math.cos(a) * C.R.CANDLES, 0, Math.sin(a) * C.R.CANDLES];
      FP.add(root, cd.root);
      cd.halo.noFit = true;
      cd.ang = a; cd.seed = rnd() * 10; cd.out = false; cd.i = i;
      set.candles.push(cd);
    }
    // The eight wax bodies, and the eight shadow discs, each welded into one mesh: two draw
    // calls, not sixteen. The flames and halos stay apart, because each lights, breathes and
    // gutters on its own.
    var bodies = set.candles.map(function (cd) { return { mesh: cd.body.mesh, m: M.compose(cd.root.pos, [0, 0, 0], [1, 1, 1]) }; });
    FP.add(root, FP.node(G.merge(bodies), set.candles[0].body.mat));
    var shParts = set.candles.map(function (cd) {
      return { mesh: G.disc(0.075, 16), m: M.compose([cd.root.pos[0], 0.004, cd.root.pos[2]], [0, 0, 0], [1, 1, 1]) };
    });
    var sh = FP.add(root, FP.node(G.merge(shParts), FP.mat("shadow", { alpha: 0.4 }), { glint: false }));
    sh.noFit = true;
    // The running light of Bind: a gold ring over the outer chalk ring, drawn as an arc.
    set.run = FP.add(root, FP.node(G.ring(C.R.OUTER, 0.012, 120, 4), P.mat("line", { color: [1, 0.8, 0.45], alpha: 0 }),
                                   { pos: [0, 0.004, 0], scl: [1, 0.3, 1], visible: false, glint: false }));
    set.window = FP.add(root, FP.node(G.ring(C.R.OUTER + 0.04, 0.006, 120, 4), P.mat("line", { color: [0.95, 0.85, 0.6], alpha: 0 }),
                                      { pos: [0, 0.003, 0], scl: [1, 0.3, 1], visible: false, glint: false }));
    set.run.noFit = set.window.noFit = true;
    // The near edge: ink and chalk at the left, the method's tool at the right (out of the
    // strip's way: the minigame strip rises over the bottom of the stage).
    var ink = P.inkPot(); ink.pos = [-1.32, 0, 0.5]; FP.add(root, ink);
    var ch = P.chalkStick(); ch.pos = [-1.28, 0, 0.72]; ch.rot = [0, 0.6, 0]; FP.add(root, ch);
    set.props.ink = ink;
    set.toolRest = { pos: [1.32, 0, 0.56], rot: [0, -0.5, 0] };
    set.bell = null;
    return set;
  }

  function setFor() {
    if (!S.sets.main) S.sets.main = buildSet();
    return S.sets.main;
  }

  function applyScene() {
    S.set = setFor();
    var kind = E.room.kindOf(S.scene);
    S.roomKind = kind;
    S.room = null;
    if (kind === "sanctum" || kind === "hired") {
      S.room = E.room.sanctum(kind);
    } else {
      var gk = K.ground.kindFor({ biome: S.scene.biome, roofed: kind === "roofed" }), rec = K.ground.paint(gk);
      if (S.groundRec && S.groundRec !== rec && S.r) S.r.forgetTexture(S.groundRec);
      S.groundRec = rec;
      var k = 1 / rec.look.tile;
      var mt = F.props.mat("wood", { color: [1, 1, 1], pattern: 0, tex: rec, uvScale: [k, k], ground: 1,
                                     spec: rec.look.spec, shin: rec.look.shin });
      if (!S.groundNode) S.groundNode = F.props.node(G.plane(40), mt, { glint: false });
      S.groundNode.mat = mt;
    }
    wake();
  }

  /* --- light, by the scene clock and the day's phase --------------------------------------- */

  var LIGHT = M ? M.norm([-0.42, 0.78, 0.47]) : [0, 1, 0];
  function bell(x, c, w) { var d = (x - c) / w; return Math.exp(-d * d); }
  /* The phase of the day at a minute, as rules/sky.py draws the windows: each turning point
     (dawn 06:00, noon, dusk 18:00, midnight) holds the two hours centred on it. */
  function phaseAt(minute) {
    var h = ((((+minute || 0) % 1440) + 1440) % 1440) / 60;
    if (h >= 23 || h < 1) return "midnight";
    if (h < 5) return "night";
    if (h < 7) return "dawn";
    if (h < 11) return "morning";
    if (h < 13) return "noon";
    if (h < 17) return "afternoon";
    if (h < 19) return "dusk";
    return "night";
  }
  function phaseNow() {
    var h = S.hour || {};
    var p = String(h.now || "").toLowerCase();
    if (PHASES.indexOf(p) >= 0) return p;
    p = String(h.phase || "").toLowerCase();
    // lane E's state.hour names the phase now; its check's hour names the essence's, with `now`.
    if (PHASES.indexOf(p) >= 0 && (h.inside || h.now === undefined && h.inside === undefined)) return p;
    return phaseAt(S.scene.minute);
  }
  function tint(c, ph) {
    var t = TINT[ph] || TINT.noon;
    return [c[0] * t[0], c[1] * t[1], c[2] * t[2]];
  }
  function litFraction() {
    var n = 0, s = 0;
    S.set.candles.forEach(function (cd) { n++; s += cd.out ? 0 : S.sp.get("lit" + cd.i); });
    return n ? s / n : 0;
  }
  function lights() {
    var g = S.scene, h = ((((+g.minute || 0) % 1440) + 1440) % 1440) / 60;
    var day = M.smooth(5.5, 7.5, h) * (1 - M.smooth(17.5, 19.5, h));
    var dusk = Math.max(bell(h, 6.5, 1.1), bell(h, 18.6, 1.1));
    var ph = phaseNow(), L = {};
    var candles = litFraction() * S.flick;
    if (S.roomKind !== "camp") {
      // A room is the candles' room: little else lights it, a cool grey from a window by day.
      L.amb = M.lerp3([0.04, 0.036, 0.034], [0.085, 0.085, 0.09], day);
      L.fillDir = M.norm([0.3, 0.9, -0.35]);
      L.fillCol = M.add([0.12, 0.1, 0.09], M.scale([0.2, 0.22, 0.26], day));
      L.keyCol = M.scale([1.5, 1.05, 0.55], 0.25 + 1.1 * candles);
    } else {
      L.amb = M.add(M.lerp3([0.04, 0.045, 0.07], [0.36, 0.37, 0.4], day), [0.06 * dusk, 0.03 * dusk, 0.012 * dusk]);
      L.fillDir = LIGHT;
      var moon = (1 - day) * (1 - dusk);
      L.fillCol = M.add(M.add(M.scale([0.86, 0.86, 0.9], 0.85 * day), M.scale([0.7, 0.42, 0.24], 0.55 * dusk)),
                        M.scale([0.22, 0.29, 0.5], 0.42 * moon));
      var kk = (0.25 + 1.05 * (1 - day)) * (0.2 + 1.0 * candles);
      L.keyCol = [1.45 * kk, 1.02 * kk, 0.52 * kk];
    }
    L.amb = tint(L.amb, ph);
    L.fillCol = tint(L.fillCol, ph);
    L.keyPos = [0, 0.7, 0.18];
    L.phase = ph;
    return L;
  }

  /* --- colour ------------------------------------------------------------------------------ */

  function parseColor(c, d) {
    if (Array.isArray(c) && c.length >= 3) {
      var big = c[0] > 1 || c[1] > 1 || c[2] > 1, k = big ? 1 / 255 : 1;
      return [num(c[0], 0) * k, num(c[1], 0) * k, num(c[2], 0) * k];
    }
    if (typeof c === "string") {
      var m = /^#?([0-9a-f]{6})$/i.exec(c.trim());
      if (m) {
        var v = parseInt(m[1], 16);
        return [(v >> 16 & 255) / 255, (v >> 8 & 255) / 255, (v & 255) / 255];
      }
    }
    return d;
  }
  // sRGB swatch to the linear-ish base the house shader lights (it does no gamma), the forge's.
  function toBase(c) { return [Math.pow(c[0], 1.6), Math.pow(c[1], 1.6), Math.pow(c[2], 1.6)]; }

  // When the server sends no swatch: the commonest vessel metals, close to forge_views.py's
  // material_color table, so a cold iron sword is not drawn as plain steel.
  var METAL = { "cold-iron": "#5b6066", iron: "#8a8d91", "wrought-iron": "#7d7f82", steel: "#a9adb2",
                silver: "#c9ccd2", "alchemical-silver": "#c4c8cf", mithral: "#d5dce6", adamantine: "#3f4a4f",
                gold: "#d4af37", bronze: "#b08d57", copper: "#b87333", brass: "#c9a35a", darkwood: "#4a3326" };
  var NON_METAL = /wood|haft|ash\b|oak|hickory|yew|bamboo|leather|cord|bone|horn|cloth|linen|padd|felt|hide|rope|ivory|darkwood|ironwood/;
  function isMetal(piece, slot) {
    var id = String((piece && piece.material) || "").toLowerCase();
    if (id) return !NON_METAL.test(id);
    return slot !== "haft" && slot !== "lining";
  }
  function pieceColor(piece, fallback) {
    var c = parseColor(piece && piece.color, null);
    if (c) return c;
    var id = String((piece && piece.material) || "").toLowerCase();
    if (METAL[id]) return parseColor(METAL[id], fallback);
    for (var k in METAL) if (id.indexOf(k) === 0) return parseColor(METAL[k], fallback);
    return fallback;
  }

  /* One surface: the forge's rule (finish from quality: rough at Crude, mirror at Flawless). */
  function surfaceMat(kind, rgb) {
    var P = F.props, v = S.vessel || {}, q = Math.max(0, Math.min(1.25, num(v.quality_index, 3) / 4));
    if (kind === "metal") {
      var base = toBase(rgb);
      var m = P.mat("steel", { color: base, spec: 0.5 + 0.8 * q, shin: 20 + 60 * q, metal: 0.75, pattern: 4,
                               bump: Math.max(0, 0.7 - 0.7 * q), patScale: 2.5, emit: [0, 0, 0] });
      m.metal_ = true; m.base_ = base.slice();
      return m;
    }
    if (kind === "gem") return P.mat("steel", { color: toBase(rgb), spec: 1.6, shin: 90, metal: 0.2, emit: M.scale(toBase(rgb), 0.25) });
    if (kind === "cloth") return P.mat("cloth", { color: toBase(rgb), patScale: 2.2 });
    return P.mat("leather", { color: toBase(rgb) });
  }

  /* --- the vessel ----------------------------------------------------------------------------- */

  function leadColor() {
    for (var i = 0; i < S.seats.length; i++) {
      var c = parseColor(S.seats[i] && S.seats[i].color, null);
      if (c && S.seats[i].seated) return c;
    }
    return null;
  }

  var WELD = new WeakMap();
  function buildVessel() {
    var v = S.vessel, P = F.props;
    S.vesselRoot = null;
    if (!v) return;
    var root = P.group(), any = false, gear = v.gear || "";
    root.parts = [];
    var forged = gear === "weapon" || gear === "armour" || gear === "shield";
    if (forged && !v.family) {
      var plan = F.families.planFor(gear, v.base || "");
      var pieces = v.pieces || {}, slots = SLOTS[gear];
      slots.forEach(function (slot, i) {
        var pc = plan[slot] || (i === 0 ? plan.head || plan.body : null);
        if (!pc) return;
        var piece = pieces[slot] || {};
        var metal = isMetal(piece, slot);
        var col = pieceColor(piece, metal ? [0.6, 0.6, 0.62] : (pc.fam === "grip" ? [0.4, 0.26, 0.16] : [0.55, 0.4, 0.26]));
        var built = F.families.build(pc.fam, pc.p);
        var g = P.group({ pos: pc.at || [0, 0, 0], rot: pc.rot || [0, 0, 0] });
        // The forge cuts a blade into eight runs so its temper colour can run along it; the
        // circle shows no temper, so the runs are welded into one mesh, once, on the forge's own
        // cached build (a longsword was ten draw calls, now three).
        // Kept in a map of our own, so the forge's cached builds are never written to.
        var one = WELD.get(built);
        if (!one) {
          var verts = built.meshes.reduce(function (a, m) { return a + m.pos.length / 3; }, 0);
          one = built.meshes.length > 1 && verts < 60000
            ? [G.merge(built.meshes.map(function (m) { return { mesh: m, m: M.ident() }; }))] : built.meshes;
          WELD.set(built, one);
        }
        one.forEach(function (mesh) {
          var m = metal ? surfaceMat("metal", col) : P.mat(pc.fam === "grip" ? "leather" : "wood", { color: toBase(col) });
          root.parts.push(P.add(g, P.node(mesh, m)));
        });
        P.add(root, g);
        any = true;
      });
    } else {
      var fam = v.family && E.vessels.FAMILIES.indexOf(v.family) >= 0 ? v.family : E.vessels.familyFor(gear, v.slot, v.name || v.base);
      var main = (v.pieces || {}).head || (v.pieces || {}).body || (v.pieces || {}).focus || {};
      var metalCol = pieceColor(main, [0.83, 0.7, 0.42]);
      var gem = leadColor() || [0.75, 0.82, 0.9];
      var def = { metal: metalCol, leather: [0.42, 0.27, 0.16], cloth: [0.2, 0.24, 0.36], gem: gem };
      E.vessels.build(fam).forEach(function (p) {
        var m = surfaceMat(p.part, def[p.part]);
        if (p.part === "gem") m.gem_ = true;
        root.parts.push(P.add(root, P.node(p.mesh, m, { pos: p.pos, rot: p.rot, scl: p.scl })));
      });
      root.family = fam;
      any = true;
    }
    if (!any) return;
    // Lay it at the circle's heart: centred, its underside on the floor, and scaled so it is
    // neither lost (a ring at true size is a few pixels across) nor over the inner ring (a
    // longspear is 1.9 m).
    var items = [];
    collect(root, M.ident(), 1, 0, items);
    var lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    items.forEach(function (it) {
      var b = it.n.mesh.bounds;
      for (var c = 0; c < 8; c++) {
        var p = M.xform(it.m, [c & 1 ? b.hi[0] : b.lo[0], c & 2 ? b.hi[1] : b.lo[1], c & 4 ? b.hi[2] : b.lo[2]]);
        for (var k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], p[k]); hi[k] = Math.max(hi[k], p[k]); }
      }
    });
    var span = Math.max(hi[0] - lo[0], hi[2] - lo[2], 0.01);
    // Measured live at 960x560: a longsword at true size (about a metre) read as a thin grey line
    // across the circle, so a vessel is drawn at least 1.25 m long, never past the inner ring.
    var s = Math.min(1.3 / span, Math.max(1.25 / Math.max(span, 0.5), 0.55 / span));
    var inner = P.group({ pos: [-(lo[0] + hi[0]) / 2 * s, -lo[1] * s + 0.004, -(lo[2] + hi[2]) / 2 * s], scl: [s, s, s] });
    inner.kids = root.kids;
    var outer = P.group({ rot: [0, 0.1, 0] });
    outer.kids = [];
    // Jewellery lies on a small cloth (UI plan §6.3).
    if (!forged && /ring|amulet|circlet/.test(root.family || "")) {
      var cl = E.props.cloth();
      cl.scl = [Math.max(1, span * s / 0.36), 1, Math.max(1, span * s / 0.36)];
      outer.kids.push(cl);
      inner.pos[1] += 0.006;
    }
    outer.kids.push(inner);
    outer.inner = inner;
    outer.parts = root.parts;
    outer.size = [(hi[0] - lo[0]) * s, (hi[1] - lo[1]) * s, (hi[2] - lo[2]) * s];
    S.vesselRoot = outer;
  }

  /* The seated essences' colour in the gems, and the glow they cast. */
  function paintVessel() {
    var R = S.vesselRoot;
    if (!R) return;
    var col = leadColor();
    R.parts.forEach(function (n) {
      if (n.mat.gem_ && col) { n.mat.color = toBase(col); n.mat.emit = M.scale(toBase(col), 0.3 + 0.6 * S.pour); }
    });
  }

  function vesselPoint() {
    var R = S.vesselRoot, y = R ? R.size[1] : 0;
    return [0, (S.sp.get("vy") || 0) + y + 0.02, 0];
  }

  /* --- seats ----------------------------------------------------------------------------------- */

  function applySeats() {
    var set = S.set;
    set.seatNodes.forEach(function (sn, i) {
      var seat = S.seats[i] || null;
      sn.seat = seat;
      sn.root.visible = !!seat;
      var col = parseColor(seat && seat.color, [0.8, 0.78, 0.7]);
      sn.col = col;
      var want = seat && seat.seated ? (col.join(",")) : "";
      if (want !== sn.phialKey) {
        if (sn.phial) { var k = sn.root.kids.indexOf(sn.phial.root); if (k >= 0) sn.root.kids.splice(k, 1); }
        sn.phial = null;
        if (want) {
          sn.phial = E.props.phial(toBase(col));
          sn.phial.liquid.mat.emit = M.scale(toBase(col), 0.18);
          // The phial stands just outside its mark, toward the camera, so the mark stays readable.
          sn.phial.root.pos = [0, 0, 0];
          F.props.add(sn.root, sn.phial.root);
        }
        sn.phialKey = want;
      }
      var lit = seat ? (seat.lit !== undefined ? !!seat.lit : !!seat.seated) : false;
      S.sp.set("seat" + i, lit ? 1 : 0, 6);
    });
    paintVessel();
    wake();
  }

  function phialTop(i) {
    var sn = S.set.seatNodes[i];
    return [sn.pos[0], 0.12, sn.pos[2]];
  }

  /* --- the circle's lines ------------------------------------------------------------------------ */

  // What the circle shows. Outside Prepare it is whole. Prepare starts it empty (only the old
  // dust) and each placed step draws its part on: chalk the rings and the figure, salt the
  // heaps, ink the sigils (split between however many ink steps the sequence has).
  var DEFAULT_SEQ = ["chalk", "salt", "ink", "bell"];
  function circleTargets(placed, seq) {
    seq = seq && seq.length ? seq : DEFAULT_SEQ;
    var done = seq.slice(0, Math.max(0, placed)), has = function (list, k) { return list.indexOf(k) >= 0; };
    var rings = has(done, "chalk") || (!has(seq, "chalk") && done.length > 0) ? 1 : 0;
    var saltOn = has(done, "salt") || (!has(seq, "salt") && rings) ? 1 : 0;
    var inks = seq.filter(function (k) { return k === "ink"; }).length;
    var inked = done.filter(function (k) { return k === "ink"; }).length;
    var n = E.circle.SIGIL_SLOTS.length;
    var sig = inks ? Math.round(n * inked / inks) : (rings ? n : 0);
    return { rings: rings, fig: rings, salt: saltOn, sig: sig };
  }
  function drawCircle(tg, snap) {
    var sp = S.sp, fn = snap || still() ? function (k, v) { sp.snap(k, v); } : function (k, v, sp_) { sp.linear(k, v, sp_); };
    fn("rings", tg.rings, 1.7);
    fn("fig", tg.fig, 2.4);
    fn("salt", tg.salt, 3);
    fn("sig", tg.sig, 13);
    wake();
  }
  function wholeCircle(snap) { drawCircle({ rings: 1, fig: 1, salt: 1, sig: E.circle.SIGIL_SLOTS.length }, snap); }

  /* The vessel's own sigils for Unbind and Cleanse: as many as the sequence names, the last cut
     first (index 0 of the sequence is the last sigil cut). */
  function magicSigils(seq) {
    var n = Math.min(E.circle.SIGIL_SLOTS.length, (seq && seq.length) || 3);
    var out = [];
    for (var i = 0; i < n; i++) out.push(n - 1 - i);
    return out;
  }

  function setSigilMeshes() {
    var runes = E.circle.sigilsFor((S.vessel && (S.vessel.key || S.vessel.name || S.vessel.base)) || "circle");
    S.set.sigils.forEach(function (n, i) {
      n.mesh = E.circle.runeMesh(runes[i], 0.12);
      S.sp.snap("pick" + i, 1);
      S.sp.snap("sglow" + i, 0);
    });
  }

  /* --- hand tools ------------------------------------------------------------------------------- */
  function toolNode(name) {
    if (!S.tools[name]) S.tools[name] = E.props.TOOL_BUILD[name]();
    return S.tools[name];
  }

  function setTool(method) {
    return new Promise(function (resolve) {
      if (METHODS.indexOf(method) < 0) { resolve(false); return; }
      finishSwap();
      S.method = method;
      if (!S.set) S.set = setFor();
      // Prepare begins empty only once its game starts; until then the circle is shown whole,
      // so a bench opened on Prepare is not an empty floor.
      if (method !== "prepare" || !(S.game && S.game.on)) wholeCircle(!S.mounted);
      var name = E.props.TOOL[method], T = toolNode(name), old = S.tool;
      var rest = S.set.toolRest;
      if (old === T) { resolve(true); return; }
      S.tool = T;
      T.visible = true;
      if (!S.mounted) {
        T.pos = rest.pos.slice(); T.rot = rest.rot.slice(); T.alpha = 1; T.scl = [1, 1, 1];
        if (old) old.visible = false;
        resolve(true);
        return;
      }
      var sw = { tool: T, resolve: resolve, tweens: [], rest: rest };
      S.swap = sw;
      S.leaving = old;
      var total;
      if (still()) {
        // Reduced motion: a 120ms crossfade, nothing falls (UI plan §10).
        total = 120;
        T.pos = rest.pos.slice(); T.rot = rest.rot.slice();
        sw.tweens.push(tween(120, function (p) {
          T.alpha = p; T.scl = [1, 1, 1];
          if (old) old.alpha = 1 - p;
        }));
      } else {
        // The old tool lifts away and the new one is set down: 450ms (UI plan §10).
        var lead = old ? 160 : 0;
        total = lead + 450;
        if (old) {
          var o0 = old.pos.slice();
          sw.tweens.push(tween(160, function (p) {
            old.pos = [o0[0], o0[1] + 0.3 * M.ease.inQuad(p), o0[2]]; old.alpha = 1 - p;
          }));
        }
        T.alpha = 0; T.rot = rest.rot.slice();
        sw.tweens.push(tween(total, function (p) {
          var q = (p * total - lead) / 450;
          if (q < 0) { T.alpha = 0; return; }
          var e = M.ease.outCubic(Math.min(1, q));
          T.pos = [rest.pos[0], rest.pos[1] + 0.35 * (1 - e), rest.pos[2]];
          T.alpha = Math.min(1, q * 2.5);
        }));
      }
      sw.tweens[sw.tweens.length - 1].done = function () { if (S.swap === sw) finishSwap(); };
      sw.timer = setTimeout(function () { if (S.swap === sw) finishSwap(); }, total + 200);
      wake();
    });
  }

  function finishSwap() {
    var sw = S.swap;
    if (!sw) return;
    S.swap = null;
    sw.tweens.forEach(endTween);
    if (sw.timer) clearTimeout(sw.timer);
    if (S.leaving && S.leaving !== sw.tool) S.leaving.visible = false;
    S.leaving = null;
    var T = sw.tool;
    T.pos = sw.rest.pos.slice(); T.rot = sw.rest.rot.slice(); T.scl = [1, 1, 1]; T.alpha = 1;
    sw.resolve(true);
  }

  /* --- poses: everything the springs drive, written onto the nodes once a frame ------------ */

  function applyPose(ts, live) {
    var set = S.set, sp = S.sp, C = E.circle;
    if (!set) return;
    // The rings: a stretch of arc from each ring's own start angle.
    var rp = sp.get("rings");
    set.rings.forEach(function (n) {
      n.visible = rp > 0.002;
      n.ranges = rp >= 0.999 ? null : G.arcRanges(n.mesh, n.a0, n.a0 + TAU * rp);
    });
    set.figure.alpha = sp.get("fig");
    set.figure.visible = set.figure.alpha > 0.01;
    set.salt.alpha = sp.get("salt");
    set.salt.visible = set.salt.alpha > 0.01;
    // The sigils: drawn on one by one (`sig`), picked out (`pick<i>`), glowing (`sglow<i>`).
    var shown = sp.get("sig"), g = S.game && S.game.on ? S.game : null, st = (g && g.state) || {};
    var unpick = S.method === "unbind" || S.method === "cleanse";
    var magic = unpick ? magicSigils(st.seq || (g && g.seq)) : [];
    // Cleanse's curse: `curse` names positions in the sequence; without it, every sigil the
    // sequence names is the curse's (lane E sends Cleanse three, all of them the curse's).
    var curse = S.method !== "cleanse" ? [] : (Array.isArray(st.curse)
      ? st.curse.map(function (k) { return magic[k]; }).filter(function (k) { return k !== undefined; }) : magic);
    var lead = leadColor() || [0.95, 0.8, 0.5];
    set.sigils.forEach(function (n, i) {
      var a = Math.max(0, Math.min(1, shown - i)) * sp.get("pick" + i);
      n.alpha = a;
      n.visible = a > 0.01;
      var glow = sp.get("sglow" + i) + S.sigFlash;
      var isMagic = magic.indexOf(i) >= 0, isCurse = curse.indexOf(i) >= 0;
      var base = set.chalkMat.color;
      if (isCurse) {
        n.mat.color = [0.2, 0.12, 0.24];
        // At half this the curse's sigils were barely there on a night floor in the live capture.
        n.mat.emit = M.scale([0.5, 0.16, 0.66], 0.6 + 0.4 * glow);
      } else if (isMagic || glow > 0.01) {
        n.mat.color = base;
        n.mat.emit = M.scale(E.fx.bright(lead), 0.12 + 0.8 * (isMagic ? Math.max(0.35, glow) : glow));
      } else {
        n.mat.color = base;
        n.mat.emit = [0, 0, 0];
      }
    });
    // The seats: each mark lit in its essence's colour by `seat<i>`.
    set.seatNodes.forEach(function (sn, i) {
      if (!sn.seat) return;
      var k = sp.get("seat" + i), c = E.fx.bright(sn.col);
      sn.ringMat.emit = M.scale(c, 0.85 * k);
      sn.ringMat.color = M.lerp3(set.chalkMat.color, toBase(sn.col), 0.5 * k);
      sn.glow.mat.color = c;
      // 0.42 burned to white over sunlit planks in the live capture; this keeps the colour.
      sn.glow.mat.alpha = 0.26 * k;
      sn.glow.visible = k > 0.01;
    });
    // Candles: lit one by one on open (`lit<i>`), a breathing flame while a game is live, one
    // guttered out when the binding is flawed. Halos are turned to the camera.
    var face = (90 - PITCH) * D2R;
    var runA = S.runA !== null ? S.runA : (S.method === "bind" && g ? runAngle(st) : null);
    set.candles.forEach(function (cd, i) {
      var l = cd.out ? sp.get("gutter") : sp.get("lit" + i);
      var f = l;
      if (live && !still()) f *= 1 + 0.08 * Math.sin(ts * (7 + i * 0.37) + cd.seed) + 0.05 * Math.sin(ts * (13.1 + i) + cd.seed * 2);
      if (runA !== null) {
        var d = Math.abs(((cd.ang - runA) % TAU + TAU + Math.PI) % TAU - Math.PI);
        f *= 1 + 0.6 * Math.max(0, 1 - d / 0.7);
      }
      cd.flame.scl = [Math.max(0.001, 0.85 + 0.15 * f) * (l > 0.01 ? 1 : 0.001), Math.max(0.001, f), Math.max(0.001, 0.85 + 0.15 * f) * (l > 0.01 ? 1 : 0.001)];
      cd.flame.visible = l > 0.01;
      cd.halo.visible = l > 0.01;
      cd.halo.mat.alpha = 0.26 * l * (0.85 + 0.15 * f);
      cd.halo.rot = [face, 0, 0];
    });
    // Bind's running light and its crest window.
    if (S.runA !== null) {
      set.window.visible = false;
      set.run.visible = true;
      set.run.mat.color = E.fx.bright(lead);
      set.run.mat.alpha = 0.9;
      set.run.ranges = G.arcRanges(set.run.mesh, runA - 0.5, runA + 0.04);
    } else if (S.method === "bind" && g) {
      var w = clamp01(st.window === undefined ? 0.12 : st.window), crest = Math.PI / 2;
      set.window.visible = true;
      set.window.mat.alpha = 0.35;
      set.window.ranges = G.arcRanges(set.window.mesh, crest - w * Math.PI, crest + w * Math.PI);
      set.run.visible = runA !== null;
      if (runA !== null) {
        set.run.mat.color = E.fx.bright(lead);
        set.run.mat.alpha = 0.9;
        set.run.ranges = G.arcRanges(set.run.mesh, runA - 0.22, runA + 0.04);
      }
    } else {
      set.window.visible = false;
      set.run.visible = false;
    }
    // The vessel.
    var R = S.vesselRoot;
    if (R) {
      R.pos = [0, sp.get("vy"), 0];
      R.alpha = sp.get("va");
      R.visible = !S.vesselGone && R.alpha > 0.01;
    }
    paintVessel();
    // The hand tool rests at the right edge whenever it is not mid-swap.
    var T = S.tool;
    if (T && !S.swap) { T.pos = set.toolRest.pos.slice(); T.rot = set.toolRest.rot.slice(); }
  }

  /* Where Bind's light is: it runs once round the ring per pass and crests at the front (+z,
     toward the player) when `light` reaches 1. */
  function runAngle(st) {
    if (st.light === undefined || st.light === null) return null;
    return Math.PI / 2 - TAU * (1 - clamp01(st.light));
  }

  /* --- camera --------------------------------------------------------------------------------
     About 50 degrees down into the circle (UI plan §6.3). The field of view is SOLVED, as both
     other stages solve it: the candle ring and the near props are fitted from their own points
     to a share of the stage's height and width, so the circle fills the stage at every aspect
     and the candles never fall off its edges. */
  function fitCloud() {
    if (S.fit) return S.fit;
    var pts = [], r = E.circle.R.CANDLES + 0.12;
    for (var i = 0; i < 32; i++) {
      var a = i / 32 * TAU;
      pts.push(Math.cos(a) * r, 0, Math.sin(a) * r, Math.cos(a) * r, 0.24, Math.sin(a) * r);
    }
    // The ink pot and the tool at the edges.
    pts.push(-1.42, 0, 0.5, 1.42, 0, 0.56, -1.42, 0.08, 0.5, 1.42, 0.08, 0.56);
    S.fit = { pts: new Float32Array(pts), centre: [0, 0.08, 0], h: 0.8, w: 0.94 };
    return S.fit;
  }

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

  function camera() {
    var aspect = S.cssW / Math.max(1, S.cssH);
    var pitch = PITCH * D2R + S.nudge * Math.max(0, 1 - (now() - S.nudgeAt) / 60) * D2R;
    var fit = fitCloud(), target = fit.centre, dist = 4.4;
    var eye = [target[0], target[1] + Math.sin(pitch) * dist, target[2] + Math.cos(pitch) * dist];
    var view = M.lookAt(eye, target, [0, 1, 0]);
    var e = extent(fit.pts, view), h = fit.h, w = fit.w;
    var Tw = e[2] - e[0], Th = e[3] - e[1];
    var tH = Th / (2 * h), tW = Tw / (2 * w * aspect);
    var t = Math.max(tH, tW);
    var proj = M.perspective(2 * Math.atan(t), aspect, 0.1, 60);
    // Lens shift: the circle sits a little above the middle, leaving the lower part of the
    // stage for the info block and the rising minigame strip (as both other stages do).
    var cy = (e[3] + e[1]) / 2, cx = (e[2] + e[0]) / 2;
    proj[9] = cy / t - 0.1;
    proj[8] = cx / (t * aspect);
    var vp = M.mul(proj, view);
    S.cam = { eye: eye, view: view, proj: proj, vp: vp, t: t };
    return S.cam;
  }

  /* --- drawing ------------------------------------------------------------------------------ */

  function collect(n, parent, alpha, glint, out, all) {
    if (!n || (!n.visible && !all)) return;
    var m = M.mul(parent, M.compose(n.pos, n.rot, n.scl));
    var a = alpha * (n.alpha === undefined ? 1 : n.alpha);
    if (a <= 0.002 && !all) return;
    if (n.mesh && n.mat) out.push({ n: n, m: m, a: a, glint: n.glint ? glint : 0 });
    for (var i = 0; i < n.kids.length; i++) collect(n.kids[i], m, a, glint, out, all);
  }

  /* The emitter every effect uses: refused under reduced motion, and it wakes the loop so the
     particle lives out its life and the loop then stops. */
  var FX = {
    emit: function (kind, pos, opts) {
      if (still() || !S.mounted) return;
      S.particles.emit(kind, [pos[0], pos[1], pos[2]], opts);
      wake();
    }
  };

  function glowLight() {
    // The essence's light: the seated essences' lead colour, brightening as the binding pours
    // in; a fifth warmer when the clock stands in the essence's own phase; a shade darker on a
    // flawed binding (UI plan §7.2: "the glow settles a shade darker").
    var col = leadColor();
    if (!col || !S.vesselRoot) return [0, 0, 0];
    var lit = 0;
    S.set.seatNodes.forEach(function (sn, i) { if (sn.seat && sn.seat.seated) lit = Math.max(lit, S.sp.get("seat" + i)); });
    // Measured live: at 0.18 + 0.35 a seated fire essence washed a sanctum's floor red before
    // anything was bound; the resting glow is a hint, and the binding is what brightens it.
    var k = (0.08 + 0.2 * lit + 1.25 * S.pour) * (S.hour && S.hour.inside ? 1.2 : 1) * (S.flawed ? 0.62 : 1);
    var c = E.fx.bright(col);
    return [c[0] * k, c[1] * k, c[2] * k];
  }

  function draw() {
    var r = S.r;
    if (!r || !r.gl || S.lost || !S.set) return;
    var cam = camera(), L = lights(), set = S.set;
    var vp = vesselPoint();
    var glowCol = glowLight(), glowPos = [vp[0], vp[1] + 0.12, vp[2] + 0.05];
    var fk = S.flare * 2.4, fc = S.flareCol;
    r.begin({
      vp: cam.vp, view: cam.view, proj: cam.proj, eye: cam.eye, amb: L.amb, keyPos: L.keyPos, keyCol: L.keyCol,
      fillDir: L.fillDir, fillCol: L.fillCol, glowPos: glowPos, glowCol: glowCol,
      flarePos: [vp[0], vp[1] + 0.3, vp[2] + 0.15], flareCol: [fc[0] * fk, fc[1] * fk, fc[2] * fk],
      exposure: S.dim, reveal: S.reveal, bg: BG, fade: [4.2, 10.5],
      px: r.canvas.height / (2 * cam.t)
    });
    S.stats.key = L.keyCol.slice();
    S.stats.glow = glowCol.slice();
    S.stats.fill = L.fillCol.slice();
    S.stats.phase = L.phase;

    var items = [], I = M.ident();
    if (S.room) collect(S.room.root, I, 1, 0, items);
    else if (S.groundNode) collect(S.groundNode, I, 1, 0, items);
    collect(set.root, I, 1, 0, items);
    if (S.leaving) collect(S.leaving, I, 1, 0, items);
    if (S.tool) collect(S.tool, I, 1, 0, items);
    if (S.vesselRoot) collect(S.vesselRoot, I, 1, S.glint, items);

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
        if (it.n.ranges) it.n.ranges.forEach(function (rg) { r.draw(it.n.mesh, it.m, it.n.mat, it.a, it.glint, rg); });
        else r.draw(it.n.mesh, it.m, it.n.mat, it.a, it.glint, null);
      });
    }
    r.setBlend("opaque"); issue(opaque);
    r.setBlend("fade"); issue(fade);
    r.setBlend("alpha"); issue(alpha);
    r.setBlend("add"); issue(add);
    r.points(S.particles.out[0], S.particles.counts[0], false);
    r.points(S.particles.out[1], S.particles.counts[1], true);
    S.stats.lastDraws = r.draws;
    S.stats.draws += r.draws;
  }

  /* --- size and visibility ---------------------------------------------------------------------
     Device-pixel aware, capped at 2, and again at 4K worth of pixels (the herb stage's
     measurement: 3440x1440 at a ratio of 2 is five times 1080p's fill). A host with no size is
     a hidden bench: the loop stops until it has a size again. */
  function resize() {
    if (!S.canvas || !S.host) return;
    var cw = S.host.clientWidth, ch = S.host.clientHeight;
    var hidden = !(cw > 0 && ch > 0);
    var was = S.hiddenBox;
    S.hiddenBox = hidden;
    if (hidden) {
      if (S.raf) { window.cancelAnimationFrame(S.raf); S.raf = 0; }
      return;
    }
    var w = Math.max(1, cw), h = Math.max(1, ch);
    var dpr = Math.min(2, window.devicePixelRatio || 1);
    if (w * h * dpr * dpr > MAX_PIXELS) dpr = Math.max(1, Math.sqrt(MAX_PIXELS / (w * h)));
    S.cssW = w; S.cssH = h;
    if (S.r) S.r.resize(Math.round(w * dpr), Math.round(h * dpr));
    if (was) S.lastT = 0;
    wake();
  }
  function onVisibility() {
    var hid = !!(document && document.hidden);
    S.hiddenTab = hid;
    if (hid) { if (S.raf) { window.cancelAnimationFrame(S.raf); S.raf = 0; } }
    else { S.lastT = 0; wake(); }
  }

  /* --- the game ------------------------------------------------------------------------------- */

  function game(method) {
    var g = { method: method, on: false, state: {}, seq: null, placed: 0, picked: 0 };
    function mine() { return S.method === method && S.game === g; }
    function begin() {
      if (S.game !== g) S.game = g;
      if (g.on) return;
      g.on = true; S.gameOn = true;
      if (method === "prepare") drawCircle({ rings: 0, fig: 0, salt: 0, sig: 0 }, true);
      if (method === "attune") S.set.seatNodes.forEach(function (sn, i) { if (sn.seat) S.sp.snap("seat" + i, 0); });
      if (method === "bind") S.pour = 0;
      if (method === "unbind" || method === "cleanse") S.set.sigils.forEach(function (n, i) { S.sp.snap("pick" + i, 1); });
    }
    function placeTo(n) {
      g.placed = Math.max(0, n);
      drawCircle(circleTargets(g.placed, g.seq));
    }
    function pickSigil(k) {
      var magic = magicSigils(g.seq), i = magic[Math.max(0, Math.min(magic.length - 1, k))];
      if (i === undefined) return;
      // A fade that ends (400ms, at a constant pace), not an ease that only approaches nothing.
      S.sp.linear("pick" + i, 0, 2.5);
      var n = S.set.sigils[i];
      E.fx.mist(FX.emit, n.pos, leadColor() || [0.8, 0.7, 0.5]);
    }
    var view = {
      update: safe("game.update", function (st) {
        if (!st || typeof st !== "object") return;
        begin();
        g.state = st;
        S.gameLast = now();
        if (Array.isArray(st.seq)) g.seq = st.seq;
        if (method === "prepare" && st.placed !== undefined && num(st.placed, g.placed) !== g.placed) placeTo(num(st.placed, 0));
        if (method === "attune" && Array.isArray(st.seats)) {
          st.seats.forEach(function (s, i) { if (s && s.matched !== undefined) S.sp.set("seat" + i, s.matched ? 1 : 0, 6); });
        }
        if (method === "bind" && st.pour !== undefined) S.pour = clamp01(st.pour);
        if ((method === "unbind" || method === "cleanse") && st.picked !== undefined) {
          var p = Math.max(0, Math.floor(num(st.picked, 0)));
          while (g.picked < p) pickSigil(g.picked++);
        }
        if (method === "refine" && st.purity !== undefined && S.set.seatNodes[0].phial) {
          S.set.seatNodes[0].phial.liquid.mat.alpha = 0.55 + 0.4 * clamp01(st.purity);
        }
        if (mine()) wake();
      }),
      hit: safe("game.hit", function (strength, index) {
        if (!mine()) return;
        begin();
        S.gameLast = now();
        var s = clamp01(strength === undefined ? 1 : strength), i = typeof index === "number" && isFinite(index) ? Math.floor(index) : null;
        var vp = vesselPoint();
        if (method === "prepare") {
          var seq = g.seq && g.seq.length ? g.seq : DEFAULT_SEQ, at = i === null ? g.placed : i;
          placeTo(Math.max(g.placed, at + 1));
          if (seq[at] === "bell" && S.tool) {
            S.flare = Math.max(S.flare, 0.5); S.flareCol = [0.85, 0.88, 0.95];
            FX.emit("glint", [S.set.toolRest.pos[0], 0.12, S.set.toolRest.pos[2]], { count: 2 });
          }
        } else if (method === "attune") {
          var k = i === null ? 0 : i;
          if (S.set.seatNodes[k]) { S.sp.set("seat" + k, 1, still() ? 100 : 7); FX.emit("glint", phialTop(k), { count: 2, col: E.fx.bright(S.set.seatNodes[k].col) }); }
        } else if (method === "bind") {
          S.pour = Math.min(1, S.pour + 0.12 + 0.18 * s);
          var crest = Math.PI / 2, R = E.circle.R.OUTER;
          E.fx.stream(FX.emit, [Math.cos(crest) * R, 0.04, Math.sin(crest) * R], vp, leadColor() || CANDLE, s);
          S.flare = Math.max(S.flare, 0.35 + 0.5 * s); S.flareCol = E.fx.bright(leadColor() || CANDLE);
          if (!still()) { S.nudge = 1; S.nudgeAt = now(); }
        } else if (method === "refine") {
          E.fx.motes(FX.emit, phialTop(0), (S.set.seatNodes[0] && S.set.seatNodes[0].col) || CANDLE, 4);
        } else if (method === "unbind" || method === "cleanse") {
          pickSigil(i === null ? g.picked : i);
          g.picked = Math.max(g.picked, (i === null ? g.picked : i) + 1);
        } else {
          FX.emit("glint", vp, { count: 2 });
        }
        wake();
      }),
      // A miss: the chalk scuffs, or the light falls short. Nothing is undone.
      miss: safe("game.miss", function (index) {
        if (!mine()) return;
        S.gameLast = now();
        var i = typeof index === "number" && isFinite(index) ? Math.floor(index) : null;
        if (method === "attune" && i !== null && S.set.seatNodes[i]) E.fx.scuff(FX.emit, S.set.seatNodes[i].pos);
        else if ((method === "unbind" || method === "cleanse") && i !== null) {
          var m = magicSigils(g.seq)[i];
          E.fx.scuff(FX.emit, m !== undefined ? S.set.sigils[m].pos : [0, 0, 0.8]);
        } else if (method === "bind") {
          FX.emit("dust", [0, 0.02, E.circle.R.OUTER], { count: 2, col: [0.6, 0.55, 0.45], size: 0.5 });
        } else {
          var a = Math.random() * TAU;
          E.fx.scuff(FX.emit, [Math.cos(a) * E.circle.R.BAND, 0.01, Math.sin(a) * E.circle.R.BAND]);
        }
        wake();
      }),
      end: safe("game.end", function () {
        g.on = false;
        if (S.game === g) { S.gameOn = false; }
        wake();
      })
    };
    S.game = g;
    return view;
  }

  /* --- flourishes ------------------------------------------------------------------------------ */
  function flourish(kind) {
    return new Promise(function (resolve) {
      if (!S.mounted || !S.set) { resolve(false); return; }
      var p = vesselPoint(), top = [p[0], p[1] + 0.15, p[2]];
      var ph = { phase: (S.seats[0] && S.seats[0].phase) || (S.hour && S.hour.phase) || phaseNow() };
      var quiet = still();
      if (kind === "tierUp") {
        sound("enchant.tier.up", ph);
        E.fx.gilt(FX.emit, top, 14);
        S.flare = Math.max(S.flare, 0.8); S.flareCol = CANDLE;
        tween(380, function (q) { S.glint = Math.sin(Math.PI * q) * 0.9; }, function () { S.glint = 0; resolve(true); });
      } else if (kind === "flawless") {
        sound("enchant.flawless", ph);
        E.fx.gilt(FX.emit, top, 90);
        S.flare = Math.max(S.flare, 1.6); S.flareCol = CANDLE;
        var cv = S.canvas;
        tween(700, function (q) { S.glint = Math.sin(Math.PI * q) * 1.2; S.sigFlash = Math.sin(Math.PI * q) * 0.8; },
              function () { S.glint = 0; S.sigFlash = 0; resolve(true); });
        if (!quiet) {
          // The STAGE canvas shakes, never the page: a transform on this one element.
          tween(250, function (q) {
            var a = 6 * (1 - q) * (1 - q);
            cv.style.transform = q >= 1 ? "" :
              "translate(" + (Math.sin(q * 71) * a).toFixed(2) + "px," + (Math.cos(q * 53) * a).toFixed(2) + "px)";
          }, function () { cv.style.transform = ""; });
        }
      } else if (kind === "bind") {
        // The moment of binding (UI plan §0, where the boldness is spent): the light runs once
        // round the ring and into the work, the sigils flash and cool to a faint scored line.
        var col = E.fx.bright(leadColor() || CANDLE);
        S.flareCol = col;
        tween(quiet ? 300 : 900, function (q) {
          if (!quiet) {
            var a = Math.PI / 2 + TAU * q, R = E.circle.R.OUTER;
            S.runA = q < 1 ? a : null;
            if (q < 0.8 && Math.random() < 0.5) E.fx.motes(FX.emit, [Math.cos(a) * R, 0.03, Math.sin(a) * R], col, 1);
          }
          S.sigFlash = q < 0.7 ? q / 0.7 : (1 - q) / 0.3 * 1;
          S.flare = Math.max(S.flare, q > 0.7 ? 1.2 * (1 - q) / 0.3 : 0);
          S.pour = Math.max(S.pour, q);
        }, function () { S.sigFlash = 0; S.runA = null; resolve(true); });
      } else if (kind === "flawed") {
        // One candle gutters out and the glow settles darker: something went wrong, and the
        // stage does not say what (the curse rule, revamp plan §11.1).
        sound("enchant.flawed", ph);
        var cd = S.set.candles[5];
        S.flawed = true;
        S.sp.snap("gutter", 1);
        cd.out = true;
        tween(quiet ? 200 : 650, function (q) {
          var flick = quiet ? 1 : 0.6 + 0.4 * Math.sin(q * 40);
          S.sp.snap("gutter", Math.max(0, (1 - q) * flick));
        }, function () {
          S.sp.snap("gutter", 0);
          E.fx.snuff(FX.emit, [cd.root.pos[0], cd.tip + 0.03, cd.root.pos[2]]);
          resolve(true);
        });
      } else if (kind === "fail") {
        // The glow falls away: dust, a shudder of the light, the stage dims 30% for 600ms.
        sound("enchant.fail", ph);
        E.fx.scuff(FX.emit, top);
        var pour0 = S.pour;
        tween(600, function (q) {
          S.dim = q < 0.12 ? 1 - 0.3 * (q / 0.12) : (q < 0.55 ? 0.7 : 0.7 + 0.3 * M.ease.inOutSine((q - 0.55) / 0.45));
          S.pour = pour0 * (1 - q);
        }, function () { S.dim = 1; S.pour = 0; resolve(true); });
      } else if (kind === "read" || kind === "identify") {
        // Read: the essence answers from its phial. Identify: the item's sigils show and fade.
        sound("enchant." + kind, ph);
        tween(800, function (q) {
          var s2 = Math.sin(Math.PI * q);
          if (kind === "identify") S.sigFlash = 0.7 * s2; else S.glint = 0.5 * s2;
        }, function () { S.sigFlash = 0; S.glint = 0; resolve(true); });
        if (kind === "read" && S.set.seatNodes[0].seat) E.fx.motes(FX.emit, phialTop(0), S.set.seatNodes[0].col, 8);
        else E.fx.gilt(FX.emit, top, 6);
      } else if (kind === "land") {
        sound("enchant.land", ph);
        land(resolve);
      } else {
        resolve(false);
      }
      wake();
    });
  }

  /* Into In progress (UI plan §10): the work lifts from the circle and is gone, and U1 flies its
     own copy from productRect() to the shelf's In progress row. Reduced motion: it glints, then
     it is not there. */
  function land(resolve) {
    var R = S.vesselRoot;
    if (!R) { resolve(false); return; }
    S.vesselGone = false;
    if (still()) {
      tween(500, function (q) { S.glint = q < 0.5 ? 0.4 : 0; },
            function () { S.vesselGone = true; S.glint = 0; resolve(true); });
      return;
    }
    E.fx.gilt(FX.emit, vesselPoint(), 10);
    var s0 = R.inner.scl.slice();
    tween(700, function (q) {
      var e = M.ease.outCubic(Math.min(1, q / 0.6));
      S.sp.snap("vy", 0.35 * e);
      R.inner.scl = M.scale(s0, 1 - 0.15 * e);
      S.sp.snap("va", q > 0.7 ? (1 - q) / 0.3 : 1);
    }, function () {
      S.vesselGone = true;
      R.inner.scl = s0;
      S.sp.snap("vy", 0); S.sp.snap("va", 1);
      resolve(true);
    });
  }

  /* Where the vessel is (or would be), in viewport pixels, so U1 can fly its copy. */
  function productRect() {
    var Rect = window.DOMRect || function (x, y, w, h) {
      return { x: x, y: y, width: w, height: h, left: x, top: y, right: x + w, bottom: y + h };
    };
    if (!S.mounted || !S.canvas || !S.set) {
      if (S.host && S.host.getBoundingClientRect) {
        var hb = S.host.getBoundingClientRect();
        return new Rect(hb.left + hb.width / 2 - 30, hb.top + hb.height / 2 - 30, 60, 60);
      }
      return new Rect(0, 0, 0, 0);
    }
    var cam = S.cam || camera(), b = S.canvas.getBoundingClientRect();
    var R = S.vesselRoot, pts = [];
    if (R) {
      var items = [];
      collect(R, M.ident(), 1, 0, items, true);
      items.forEach(function (it) {
        var bb = it.n.mesh.bounds;
        for (var c = 0; c < 8; c++) pts.push(M.xform(it.m, [c & 1 ? bb.hi[0] : bb.lo[0], c & 2 ? bb.hi[1] : bb.lo[1], c & 4 ? bb.hi[2] : bb.lo[2]]));
      });
    }
    if (!pts.length) pts.push(vesselPoint());
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    pts.forEach(function (p) {
      var v = M.xform(cam.vp, [p[0], p[1], p[2]]);
      var sx = b.left + (v[0] / v[3] * 0.5 + 0.5) * b.width, sy = b.top + (1 - (v[1] / v[3] * 0.5 + 0.5)) * b.height;
      x0 = Math.min(x0, sx); x1 = Math.max(x1, sx); y0 = Math.min(y0, sy); y1 = Math.max(y1, sy);
    });
    var w = Math.max(24, x1 - x0), h = Math.max(24, y1 - y0);
    return new Rect((x0 + x1) / 2 - w / 2, (y0 + y1) / 2 - h / 2, w, h);
  }

  /* --- mount ----------------------------------------------------------------------------------- */
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
        cv.className = "enchant-stage-canvas";
        cv.setAttribute("aria-hidden", "true");
        cv.style.cssText = "position:absolute;left:0;top:0;width:100%;height:100%;display:block;" +
                           "pointer-events:none;";
        if (window.getComputedStyle && getComputedStyle(host).position === "static") host.style.position = "relative";
        host.appendChild(cv);
        var r = new K.Renderer(cv);
        if (!r.init()) { host.removeChild(cv); resolve(false); return; }
        S.host = host; S.canvas = cv; S.r = r; S.mounted = true; S.lost = false;
        S.hiddenBox = false;
        S.hiddenTab = !!(document && document.hidden);
        cv.addEventListener("webglcontextlost", onLost, false);
        cv.addEventListener("webglcontextrestored", onRestored, false);
        if (document && document.addEventListener) document.addEventListener("visibilitychange", onVisibility, false);
        if (window.ResizeObserver) {
          S.ro = new ResizeObserver(function () { resize(); });
          S.ro.observe(host);
        } else {
          window.addEventListener("resize", resize);
        }
        resize();
        // A guttered candle belongs to the binding that went wrong, not to the bench: seen live,
        // reopening the bench on the same vessel still showed one candle out.
        S.flawed = false;
        if (S.sets.main) S.sets.main.candles.forEach(function (cd) { cd.out = false; });
        applyScene();
        if (!S.method) wholeCircle(true);
        buildVessel();
        setSigilMeshes();
        applySeats();
        S.sp.snap("vy", 0); S.sp.snap("va", 1);
        if (S.tool) { S.tool.pos = S.set.toolRest.pos.slice(); S.tool.rot = S.set.toolRest.rot.slice(); S.tool.alpha = 1; S.tool.visible = true; }
        // Open the bench (UI plan §10): the floor fades in from the page's dark and the candles
        // light one by one round the circle in 600ms; reduced motion, all at once, fade only.
        S.reveal = 0;
        var quiet = still();
        tween(quiet ? 120 : 320, function (p) { S.reveal = M.ease.outCubic(p); });
        S.set.candles.forEach(function (cd, i) {
          cd.i = i;
          if (quiet) { S.sp.snap("lit" + i, 1); return; }
          S.sp.snap("lit" + i, 0);
          var at = 70 + i * 66;
          tween(at + 140, function (q) { S.sp.snap("lit" + i, Math.max(0, Math.min(1, (q * (at + 140) - at) / 140))); });
        });
        if (!S.stats.paintMs) S.stats.paintMs = E.circle.paintDust().ms;
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
    if (document && document.removeEventListener) document.removeEventListener("visibilitychange", onVisibility, false);
    if (S.canvas) {
      S.canvas.removeEventListener("webglcontextlost", onLost, false);
      S.canvas.removeEventListener("webglcontextrestored", onRestored, false);
    }
    if (S.r) {
      try {
        // Every buffer and texture this mount uploaded, then the context itself: a page holds
        // only a handful (Chromium drops the oldest at sixteen), and the dice want one.
        S.r.dispose();
        var ext = S.r.gl && S.r.gl.getExtension && S.r.gl.getExtension("WEBGL_lose_context");
        if (ext) ext.loseContext();
      } catch (e) { /* already gone */ }
    }
    if (S.canvas && S.canvas.parentNode) S.canvas.parentNode.removeChild(S.canvas);
    S.r = null; S.canvas = null; S.host = null; S.mounted = false; S.groundRec = null;
    S.dim = 1; S.glint = 0; S.flare = 0; S.gameOn = false; S.flick = 1; S.sigFlash = 0;
    S.game = null; S.cam = null; S.runA = null;
  }

  function setScene(g) {
    g = g || {};
    var kinds = ["camp", "roofed", "sanctum", "hired"];
    var kind = kinds.indexOf(g.kind) >= 0 ? g.kind : (g.roofed ? "roofed" : "camp");
    S.scene = { kind: kind, biome: g.biome || "", roofed: !!g.roofed || kind === "roofed", minute: num(g.minute, S.scene.minute) };
    if (S.mounted) applyScene();
    else S.set = setFor();
  }

  /* The vessel at the circle's heart. Rebuilt only when what it is changes; a new vessel relights
     a candle a flawed binding put out. null clears the circle's heart. */
  function setVessel(v) {
    var key = v && typeof v === "object" ? JSON.stringify([v.key || "", v.gear || "", v.base || "", v.family || "", v.slot || "", v.name || "", v.pieces || {}, num(v.quality_index, 3)]) : "";
    S.vessel = v && typeof v === "object" ? {
      key: v.key || "", gear: String(v.gear || ""), base: v.base || "", pieces: v.pieces || {}, family: v.family || "",
      quality_index: num(v.quality_index, 3), slot: v.slot || "", name: v.name || ""
    } : null;
    if (!S.set) S.set = setFor();
    if (key !== S.vesselKey) {
      var was = S.vesselKey ? JSON.parse(S.vesselKey)[0] : "", is = key ? JSON.parse(key)[0] : "";
      var same = !!(was && is && was === is);
      S.vesselKey = key;
      S.vesselGone = false;
      if (!same && S.flawed) {
        S.flawed = false;
        S.set.candles.forEach(function (cd) { cd.out = false; });
      }
      buildVessel();
      setSigilMeshes();
    }
    S.sp.snap("vy", 0); S.sp.snap("va", 1);
    wake();
  }

  /* The essences on their seats: [{seat, essence, color, phase, seated, lit}], one per seat of
     the vessel (at most three, enchanter.json's seats), in the order the working lists them. */
  function setSeats(list) {
    S.seats = (Array.isArray(list) ? list : []).slice(0, E.circle.SEAT_SLOTS.length).map(function (s) {
      s = s || {};
      return { seat: String(s.seat || ""), essence: s.essence || null, color: s.color || null,
               phase: s.phase || null, seated: !!(s.seated || s.essence), lit: s.lit };
    });
    if (!S.set) S.set = setFor();
    applySeats();
  }

  /* The phase of the day (rules/sky.py), lane E's `hour` as it comes. */
  function hour(h) {
    S.hour = h && typeof h === "object" ? {
      phase: String(h.phase || "").toLowerCase(), now: h.now === undefined ? undefined : String(h.now || "").toLowerCase(),
      inside: h.inside === undefined ? undefined : !!h.inside, minutes_left: num(h.minutes_left, 0), widen: num(h.widen, 1)
    } : null;
    wake();
  }

  function reducedMotion(on) {
    S.reduced = !!on;
    if (S.reduced && S.particles) S.particles.clear();
    if (S.reduced && S.canvas) S.canvas.style.transform = "";
    if (S.reduced) { S.flick = 1; if (S.sp) S.sp.settle(); }
    wake();
  }

  /* For the harness and the verification notes. Not part of the contract. */
  function debug() {
    var ms = S.stats.ms.slice().sort(function (a, b) { return a - b; });
    var sum = ms.reduce(function (a, b) { return a + b; }, 0);
    var sp = S.sp;
    return { frames: S.stats.frames, draws: S.stats.draws, lastDraws: S.stats.lastDraws, rafs: S.stats.rafs, raf: !!S.raf,
             avgMs: ms.length ? sum / ms.length : 0, p95Ms: ms.length ? ms[Math.floor(ms.length * 0.95)] : 0,
             scene: S.scene.kind, room: S.roomKind || null, method: S.method, phase: S.stats.phase || null,
             vessel: S.vesselRoot ? (S.vesselRoot.inner.kids.length + ":" + (S.vessel && (S.vessel.family || S.vessel.gear))) : null,
             family: S.vesselRoot ? (S.vesselRoot.parts.length) : 0,
             circle: { rings: sp.get("rings"), fig: sp.get("fig"), salt: sp.get("salt"), sig: sp.get("sig") },
             picks: S.set ? S.set.sigils.map(function (n, i) { return +sp.get("pick" + i).toFixed(3); }) : [],
             seats: S.set ? S.set.seatNodes.map(function (sn, i) { return sn.seat ? +sp.get("seat" + i).toFixed(3) : null; }) : [],
             candles: S.set ? S.set.candles.map(function (cd, i) { return cd.out ? 0 : +sp.get("lit" + i).toFixed(3); }) : [],
             flawed: S.flawed, pour: S.pour, key: S.stats.key, glow: S.stats.glow, fill: S.stats.fill, flick: S.flick,
             particles: S.particles ? S.particles.alive() : 0, tweens: S.tweens.length,
             hidden: S.hiddenBox || S.hiddenTab, gpu: S.r ? { buffers: Object.keys(S.r.bufs || {}).length, textures: Object.keys(S.r.texs || {}).length } : null,
             paintMs: S.stats.paintMs || 0, buffer: S.canvas ? [S.canvas.width, S.canvas.height] : null };
  }
  function resetStats() { S.stats.frames = 0; S.stats.draws = 0; S.stats.ms = []; S.stats.rafs = 0; }

  if (READY) {
    S.particles = new K.Particles();
    S.sp = new Springs();
    S.sp.snap("vy", 0); S.sp.snap("va", 1); S.sp.snap("gutter", 0);
    for (var ci = 0; ci < 8; ci++) S.sp.snap("lit" + ci, 1);
  }

  function noop() {}
  function resolved(v) { return function () { return Promise.resolve(v); }; }
  var NOGAME = { update: noop, hit: noop, miss: noop, end: noop };

  window.EnchantStage = READY ? {
    available: safe("available", available, false),
    mount: function (host) { try { return mount(host); } catch (e) { warn("mount", e); return Promise.resolve(false); } },
    unmount: safe("unmount", unmount),
    setScene: safe("setScene", setScene),
    setTool: function (m) { try { return setTool(m); } catch (e) { warn("setTool", e); return Promise.resolve(false); } },
    setVessel: safe("setVessel", setVessel),
    setSeats: safe("setSeats", setSeats),
    hour: safe("hour", hour),
    game: function (m) { try { return game(m); } catch (e) { warn("game", e); return NOGAME; } },
    flourish: function (k) { try { return flourish(k); } catch (e) { warn("flourish", e); return Promise.resolve(false); } },
    productRect: safe("productRect", productRect, null),
    reducedMotion: safe("reducedMotion", reducedMotion),
    _debug: safe("_debug", debug, null),
    _resetStats: safe("_resetStats", resetStats)
  } : {
    // The parts did not load: every call is a quiet no-op, and U1 shows its flat stage.
    available: function () { return false; },
    mount: resolved(false), unmount: noop, setScene: noop, setTool: resolved(false),
    setVessel: noop, setSeats: noop, hour: noop,
    game: function () { return NOGAME; }, flourish: resolved(false),
    productRect: function () { return window.DOMRect ? new window.DOMRect(0, 0, 0, 0) : null; },
    reducedMotion: noop,
    _debug: function () { return null; }, _resetStats: noop
  };
})();
