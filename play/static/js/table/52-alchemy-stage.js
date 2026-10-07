// The play table, part 52 (the alchemy bench's 3D stage). Classic script; everything it defines
// lives inside one IIFE and leaves exactly one global, window.AlchemyStage, because the table's
// numbered modules share a single global scope.
//
// WHAT IT IS. The middle of the alchemy bench (UI plan §6.3, §7; the owner's Q9.2: "a field kit
// on the ground and a laboratory, with procedural 3D glassware whose liquid colour and level are
// live"). Its interface is contracts §12, and lane U1 builds against nothing else:
//
//   available() mount(host) unmount()
//   setScene({kind: "kit" | "town" | "owned", biome, roofed, minute})
//   setTool(method)
//   setVessel({id, kind, liquid: {color, level, turbidity}, receiver?: {color, level}})
//   liquid({color, level, turbidity}, ms)          animate to a server-sent state
//   heat(celsius) reaction(value)                   drive flame and churn during a game
//   game(method) flourish(kind)                     kind: tier, flawless, land, fail, flare, found
//   productRect() reducedMotion(bool)
//
// THE VESSEL. setVessel's `kind` names a shape (vial, flask, crucible, cucurbit, aludel,
// retort, receiver, phial, pot, bladder, casing, egg, rod, clayflask, ironflask) or `id` a shelf
// vessel ("glass-vial", "waxed-bladder": alchemy-stage/00-glass.js VESSEL_OF). For Bottle that
// is the glass the work goes into; for every other method the method's own apparatus holds the
// work (the crucible for Calcine, the round flask for Dissolve and React, the cucurbit under the
// alembic for Distill, the aludel for Sublime and Transmute), unless `kind` names another
// apparatus. Colours are the server's (lane D's material `color`, the mix colour of
// alchemist.liquid_for), [r, g, b] 0..1 or "#rrggbb"; the stage never invents one. `receiver`
// is Distill's receiver, at the cold spot under the alembic's beak.
//
// THE GAME VIEW. game(method, opts?) returns {update(state), hit(strength, index), miss(index),
// end(), heat(c), reaction(v)}, the shape 33-bench-games.js hands its states to. opts.end is the
// server's end state ({color, level, turbidity, receiver?}): while a game runs, `progress`
// eases the liquid from where it stood to there (UI plan §7.4: "the stage animates between the
// server's start and end states"). Every state key is optional, and the stage shows what it is
// given (UI plan §9's "on the stage" column):
//   heat (°C) or c, and heatRange [lo, hi]      the flame or the coals; Calcine's charge glows
//   reaction 0..100, flare_at                   bubbles and vapour; past flare_at, a puff
//   progress 0..1                               the liquid toward opts.end
//   whiteness 0..1 (Calcine)                    the charge whitens to a calx
//   receiver 0..1 (Distill)                     the receiver's level, else what the cucurbit lost
//   pour 0..1 (Filter, Bottle)                  drops from the funnel's stem, the beaker's lip
//   crust 0..1 (Sublime)                        the crust on the aludel's cool wall; a fall is a scrape
//   stage 0..3 or a name, peak 0..1 (Transmute) nigredo, albedo, citrinitas, rubedo
//   stir 0..1 (Dissolve)                        how fast the rod circles
// hit(s, i): a drop falls (React), a stage is sealed (Transmute), the stopper goes in (Bottle),
// a glint elsewhere. miss(i): a fizz.
//
// HOW IT IS BUILT. By hand, in WebGL1, on the herb stage's renderer, maths, meshes, grounds and
// particles (bench-stage/00-04, with the liquid uniforms added to 01-gl.js, contracts §11), the
// forge's node helpers, sweep, heat colours and painted smithy room (forge-stage/00-03, as they
// are), and the glassware's own parts in alchemy-stage/. No third-party JavaScript.
//
// THE LIGHT. The shader's three point lights: the KEY is the fire (the spirit lamp at the kit,
// the athanor's coals in a laboratory), its strength the heat; the GLOW is the work's own light
// (a calcining charge by its temperature, the forge's T^4 table; the Great Work at rubedo); the
// FLARE is the flare. The fill is the sky outdoors and the window indoors, by the scene clock,
// tinted a little toward the day's phase (rules/sky.py's phases, never a planet).
//
// RENDER ON DEMAND (UI plan §7.6: "the spirit lamp's flicker and the bubbles run only while a
// game is live. Idle, the flame is steady, the liquid is still, and the bench draws no
// frames"). `wake` is the only place requestAnimationFrame is called; a frame asks for the next
// only while something moves (a tween, a live game, a particle not yet dead), and wake refuses
// while the bench is HIDDEN (its box has no size) or the TAB is in the background (Page
// Visibility API): rAF stops by itself for a background tab, never for a hidden element (MDN).
// Tweens carry a timer as well, so a flourish's promise resolves on time even while hidden.
//
// REDUCED MOTION (13-device.js's still(): the OS setting, Short flourishes, or
// reducedMotion(true)): no flicker, no particles, no shake, no swap animation; the liquid jumps
// to its level; the flare keeps the glow spike, the crack and the lost liquid, because those are
// states, not flourishes (UI plan §7.5).
//
// SOUND. The stage rings its flourishes only, on U5's alchemy bus: alchemy.tier.up, .flawless,
// .fail, .land, .found, and .flare with .crack (the glass cracks). The shell plays alchemy.open
// and alchemy.method.<m>, and the games their own hits, drips, chimes, stoppers and hisses, as the
// enchanting bench splits them; a stage that played them too would ring every one twice.
//
// WHAT IT MAY NOT DO. The canvas takes no pointer events, every flourish ends on its own inside
// 1.1 s, and the Flawless and flare shakes move the STAGE canvas only. Nothing here can throw
// into a caller: without WebGL every call is a quiet no-op and `available()` says false, so U1
// shows its flat icon stage with the CSS level bar.
(function () {
  "use strict";

  var K = window.BenchStageKit || {};
  var F = window.ForgeStageKit || {};
  var A = window.AlchemyStageKit || {};
  var M = K.math, G = K.mesh;
  var READY = !!(K.math && K.Renderer && K.mesh && K.ground && K.Particles && K.props &&
                 F.props && F.geo && F.smithy &&
                 A.glass && A.apparatus && A.liquid && A.lab && A.fx);
  var D2R = Math.PI / 180, TAU = Math.PI * 2;
  var BG = [13 / 255, 11 / 255, 9 / 255];          // --bg, #0d0b09
  var MAX_PIXELS = 3840 * 2160;
  var METHODS = ["calcine", "dissolve", "distill", "filter", "react", "sublime", "bottle", "transmute", "assay"];
  // What holds the work, where, and how hot the fire rests while nothing is being played. The
  // rest heat is a pose, not a number of the game's (the flame is steady and lit, UI plan §10:
  // "Open the bench: the lamp or athanor lights").
  var ACT = {
    calcine: { kind: "crucible", spot: "hot", rest: 0.55 },
    dissolve: { kind: "flask", spot: "hot", rest: 0.3, tool: "stir" },
    distill: { kind: "cucurbit", spot: "hot", rest: 0.45, alembic: true },
    filter: { kind: "flask", spot: "work", rest: 0, tool: "funnel" },
    react: { kind: "flask", spot: "hot", rest: 0.25, tool: "dropper" },
    sublime: { kind: "aludel", spot: "hot", rest: 0.4 },
    bottle: { kind: "vial", spot: "work", rest: 0, tool: "beaker" },
    transmute: { kind: "aludel", spot: "hot", rest: 0.6 },
    assay: { kind: "slide", spot: "work", rest: 0 }
  };
  var APPARATUS = ["flask", "crucible", "cucurbit", "aludel", "retort", "receiver", "mortar", "bainmarie"];
  // The heat gauges' ranges, °C, when heat() is given no range: a COPY of the `heat` blocks in
  // content/world-classes/alchemist.json (bench.methods.*.tuning.heat lo/hi), kept only so a
  // flame still answers a bare heat(c). tests/test_alchemy_stage.py holds the two equal.
  var HEAT_RANGE = { calcine: [200, 1100], distill: [60, 100], sublime: [150, 450] };
  var PHASES = ["dawn", "morning", "noon", "afternoon", "dusk", "night", "midnight"];
  var TINT = { dawn: [1.06, 0.9, 0.9], morning: [1.0, 0.99, 0.96], noon: [1, 1, 1],
               afternoon: [1.02, 0.98, 0.92], dusk: [1.1, 0.88, 0.72], night: [0.84, 0.92, 1.1],
               midnight: [0.74, 0.84, 1.16] };

  var S = {
    host: null, canvas: null, r: null, ro: null, mounted: false, lost: false, raf: 0, lastT: 0,
    hiddenBox: false, hiddenTab: false,
    scene: { kind: "kit", biome: "", roofed: false, minute: 12 * 60 },
    sets: {}, set: null, groundRec: null, groundNode: null,
    method: null, vin: null, vesselKey: "", act: null, leaving: null, swap: null, vessels: {}, tools: {},
    liq: null, rec: null, gameStart: null, gameEnd: null, dull: 0, cracked: false,
    heatC: null, heatK: 0, reaction: 0, flareAt: 90, over: false, crust: 0, whiteness: 0, stageX: 0, pourK: 0, stir: 1,
    game: null, gameOn: false, gameLast: 0, flick: 1, emitAt: 0, dripAt: 0,
    particles: null, tweens: [], reduced: false,
    flare: 0, flareCol: [1, 0.6, 0.25], glint: 0, found: 0, dim: 1, reveal: 1, lit: 1,
    cssW: 1, cssH: 1, cam: null, product: null, productOn: false,
    stats: { frames: 0, draws: 0, lastDraws: 0, ms: [], rafs: 0, key: [0, 0, 0], glow: [0, 0, 0], fill: [0, 0, 0], liquids: 0, puffs: 0 }
  };

  function now() { return (window.performance && performance.now) ? performance.now() : Date.now(); }
  function sound(name, opts) {
    try { if (window.Sound && typeof window.Sound.play === "function") window.Sound.play(name, opts); } catch (e) { /* silent */ }
  }
  function warn(where, e) {
    if (window.console && console.warn) console.warn("AlchemyStage." + where + ":", e && e.message ? e.message : e);
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

  /* --- the frame loop ------------------------------------------------------------------ */

  // ALCHEMY-STAGE-RAF: the only requestAnimationFrame in the stage. It is reached from wake()
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
    if (isLive(t)) {
      busy = true;
      liveStep(dt, t / 1000);
    } else {
      S.flick = 1;
    }
    if (S.particles.alive()) { S.particles.step(dt, t / 1000); busy = true; }
    else S.particles.counts[0] = S.particles.counts[1] = 0;
    if (S.flare > 0.005) { S.flare *= Math.exp(-dt * 7.5); busy = true; } else S.flare = 0;
    applyPose(t / 1000, isLive(t));
    return busy;
  }

  /* While a game is live: the flame breathes, the liquid churns as the reaction climbs, vapour
     rises off a hot work, the alembic drips, the rod circles. None of it runs when the game
     stops sending states. */
  function liveStep(dt, ts) {
    if (still()) { S.flick = 1; return; }
    // A slow, low wobble: incommensurate sines, never a strobe (the forge's hearth).
    S.flick = 1 + 0.06 * Math.sin(ts * 7.3) + 0.04 * Math.sin(ts * 12.9 + 1.3) + 0.025 * Math.sin(ts * 21.1);
    if (ts - S.emitAt < 0.07) return;
    S.emitAt = ts;
    var a = S.act, LQ = A.liquid;
    if (!a || !a.v) return;
    var top = liquidTop(a.v), col = (S.liq && S.liq.cur.color) || LQ.WATER;
    var churn = Math.max(clamp01(S.reaction / 100), S.method === "distill" || S.method === "dissolve" ? S.heatK * 0.6 : 0);
    if (top && a.v.liquid && a.v.liquid.visible && churn > 0.02) {
      var depth = top[1] - a.base[1] - a.v.liquid.liquid.lo;
      LQ.bubbles(FX.emit, [top[0], a.base[1] + a.v.liquid.liquid.lo, top[2]], a.v.radiusAt(a.v.liquid.liquid.lo + 0.02), depth, churn, col);
    }
    if (top && (S.reaction > 60 || S.heatK > 0.85)) LQ.vapour(FX.emit, mouthPoint(a), clamp01(Math.max((S.reaction - 60) / 40, S.heatK - 0.85)), col);
    if (S.method === "distill" && a.alembic && S.heatK > 0.4 && ts - S.dripAt > 0.5 / Math.max(0.3, S.heatK)) {
      S.dripAt = ts;
      LQ.drop(FX.emit, a.alembic.drip, (S.rec && S.rec.color) || col);
    }
    if ((S.method === "filter" || S.method === "bottle") && S.pourK > 0.05) {
      if (S.method === "filter" && a.funnel) LQ.drop(FX.emit, a.funnelStem, col);
      if (S.method === "bottle" && a.beaker) LQ.pour(FX.emit, a.lip, mouthPoint(a), col, S.pourK);
    }
  }

  /* --- the sets ------------------------------------------------------------------------- */

  function setFor(kind) {
    if (!S.sets[kind]) S.sets[kind] = kind === "kit" ? A.lab.kit() : A.lab.lab(kind);
    return S.sets[kind];
  }

  function applyScene() {
    var kind = A.lab.kindOf(S.scene);
    S.set = setFor(kind);
    if (kind === "kit") {
      var gk = K.ground.kindFor({ biome: S.scene.biome, roofed: !!S.scene.roofed }), rec = K.ground.paint(gk);
      if (S.groundRec && S.groundRec !== rec && S.r) S.r.forgetTexture(S.groundRec);
      S.groundRec = rec;
      var k = 1 / rec.look.tile;
      var mt = F.props.mat("wood", { color: [1, 1, 1], pattern: 0, tex: rec, uvScale: [k, k], ground: 1,
                                     spec: rec.look.spec, shin: rec.look.shin });
      if (!S.groundNode) S.groundNode = F.props.node(G.plane(40), mt, { glint: false });
      S.groundNode.mat = mt;
    }
    arrange(true);
    wake();
  }

  /* --- the active arrangement: the vessel that holds the work and what serves it ---------- */

  function vesselFor(kind, glassName, tint) {
    var key = kind + ":" + (glassName || "") + ":" + (tint ? tint.join(",") : "");
    if (!S.vessels[key]) S.vessels[key] = A.glass.vessel(kind, glassName, tint);
    return S.vessels[key];
  }
  function toolFor(name) {
    if (!S.tools[name]) S.tools[name] = A.apparatus[name]();
    return S.tools[name];
  }

  /* Which shape holds the work now: Bottle's chosen glass, or the method's apparatus. */
  function activeKind() {
    var act = ACT[S.method] || ACT.dissolve, v = S.vin || {};
    if (act.kind === "slide") return { kind: "slide" };
    if (S.method === "bottle") {
      var got = A.glass.kindOf(v.id) || A.glass.kindOf(v.kind) || ["vial"];
      return { kind: got[0], glass: got[1], tint: got[2] };
    }
    var k = A.glass.kindOf(v.kind);
    if (k && APPARATUS.indexOf(k[0]) >= 0) return { kind: k[0], glass: k[1], tint: k[2] };
    return { kind: act.kind };
  }

  /* How far a vessel's base sits below the tripod ring: a round bottom rests IN the ring, at
     the height where its outside is as wide as the ring; a flat one stands on the gauze. In a
     laboratory the athanor's sand pot takes any bottom, and a round one beds 2 cm in. */
  function seat(def) {
    var o = def && def.outer;
    if (!o) return { y: 0, gauze: true };
    var round = o.length > 2 && o[1][1] > 0.001;
    var ring = S.set.ring;
    if (!ring) return { y: round ? -0.02 : 0, gauze: false };
    if (!round) return { y: 0, gauze: true };
    for (var i = 0; i < o.length - 1; i++) {
      var a = o[i], b = o[i + 1];
      if (a[0] <= ring && b[0] >= ring && b[0] !== a[0]) return { y: -(a[1] + (b[1] - a[1]) * (ring - a[0]) / (b[0] - a[0])), gauze: false };
    }
    return { y: 0, gauze: true };
  }

  var GAUZE = null;
  function gauze() {
    if (!GAUZE) GAUZE = F.props.node(A.glass.once("gauze", function () { return G.box(0.17, 0.003, 0.17); }), F.props.mat("iron", { spec: 0.4 }), { glint: false });
    return GAUZE;
  }

  /* Builds S.act for the current method, vessel and set. Nothing is allocated twice: vessels,
     tools and the alembic's beak are cached, so switching back and forth grows nothing. */
  function arrange(snap) {
    if (!S.set) return;
    var P = F.props, set = S.set, act = ACT[S.method] || null;
    var g = P.group(), a = { root: g, method: S.method, v: null, kind: null };
    Object.keys(set.idle).forEach(function (k) { set.idle[k].visible = true; });
    if (!act) { S.act = a; refocus(); return; }
    var ak = activeKind(), spot = act.spot === "hot" ? set.hot : set.work;
    a.kind = ak.kind;
    if (ak.kind === "slide") {
      var sl = toolFor("slide");
      sl.root.pos = spot.slice();
      P.add(g, sl.root);
      a.slide = sl;
      a.base = spot.slice();
      a.top = [spot[0], spot[1] + 0.01, spot[2]];
    } else {
      var v = vesselFor(ak.kind, ak.glass, ak.tint), def = v.def;
      var st = act.spot === "hot" ? seat(def) : { y: 0, gauze: false };
      var base = [spot[0], spot[1] + st.y, spot[2]];
      // A round bottom set down at the cold spot rests in a cork ring, as the kit's spare flask does.
      if (act.spot === "work" && def.outer && def.outer.length > 2 && def.outer[1][1] > 0.001) {
        base[1] += 0.014;
        P.add(g, P.node(A.glass.once("cork-ring", function () { return G.ring(0.04, 0.012, 24, 6); }),
                        F.props.mat("wood", { color: [0.6, 0.45, 0.3], pattern: 3 }), { pos: [spot[0], spot[1] + 0.012, spot[2]] }));
      }
      v.root.pos = base.slice();
      v.root.rot = [0, 0, 0];
      v.root.scl = [1, 1, 1];
      v.root.alpha = 1;
      P.add(g, v.root);
      if (st.gauze && act.spot === "hot" && set.ring) { var gz = gauze(); gz.pos = [spot[0], spot[1] + 0.0015, spot[2]]; P.add(g, gz); }
      if (v.stopper) v.stopper.visible = false;
      if (v.crust) v.crust.visible = S.method === "sublime";
      a.v = v; a.base = base;
      a.top = [base[0], base[1] + (def.mouth || 0.12), base[2]];
      if (set.idle[ak.kind]) set.idle[ak.kind].visible = false;
      if (ak.kind === "crucible" && set.idle.crucible) set.idle.crucible.visible = false;
      if (act.alembic) {
        var rv = vesselFor("receiver");
        rv.root.pos = [set.work[0], set.work[1] + 0.014, set.work[2]];
        P.add(g, rv.root);
        if (rv.stopper) rv.stopper.visible = false;
        var headAt = [base[0], base[1] + def.mouth - 0.012, base[2]];
        var mouth = [rv.root.pos[0], rv.root.pos[1] + rv.def.mouth, rv.root.pos[2]];
        var key = set.kind + ":alembic:" + ak.kind;
        if (!S.tools[key]) S.tools[key] = A.apparatus.alembic(headAt, mouth);
        a.alembic = S.tools[key];
        P.add(g, a.alembic.root);
        a.receiver = rv;
      }
      if (act.tool === "funnel") {
        var fn = toolFor("funnel");
        fn.root.pos = [base[0], base[1] + def.mouth + 0.032, base[2]];
        P.add(g, fn.root);
        a.funnel = fn;
        a.funnelStem = [base[0], base[1] + def.mouth - 0.03, base[2]];
      } else if (act.tool === "beaker") {
        var bk = toolFor("beaker");
        bk.root.pos = [base[0] - 0.1, base[1] + def.mouth + 0.05, base[2]];
        bk.root.rot = [0, 0, -1.15];
        P.add(g, bk.root);
        a.beaker = bk;
        a.lip = [base[0] - 0.006, base[1] + def.mouth + 0.09, base[2]];
      } else if (act.tool === "dropper") {
        var dr = toolFor("dropper");
        dr.root.pos = [base[0], base[1] + def.mouth + 0.05, base[2]];
        P.add(g, dr.root);
        a.dropper = dr;
        a.tip = [base[0], base[1] + def.mouth + 0.045, base[2]];
      } else if (act.tool === "stir") {
        var sr = toolFor("stirRod");
        sr.pos = [base[0] + 0.012, base[1] + 0.02, base[2]];
        sr.rot = [0, 0, 0.12];
        P.add(g, sr);
        a.stir = sr;
      }
      // The crack belongs to the vessel the flare broke, on its front toward the camera.
      var cy = (def.fill ? (def.fill[0] + def.fill[1]) / 2 : 0.08);
      a.crack = P.add(g, P.node(A.glass.crack(), A.glass.mat("crack"), {
        pos: [base[0] - 0.01, base[1] + cy, base[2] + v.radiusAt(cy) + 0.002], visible: S.cracked, glint: false }));
    }
    S.act = a;
    paintAll();
    refocus();
    void snap;
  }

  /* --- the liquid ------------------------------------------------------------------------- */

  function liquidTop(v) {
    if (!v || !v.liquid || !S.act || !S.act.base) return null;
    var L = v.liquid.liquid, b = S.act.base;
    return [b[0], b[1] + L.lo + L.level * (L.hi - L.lo), b[2]];
  }
  function mouthPoint(a) { return a.top ? a.top.slice() : [0, 0.2, 0]; }

  /* The work's own light (the GLOW): a calcining charge by its temperature (the forge's table:
     it lights only above about 420 °C), the Great Work at rubedo, nothing otherwise. */
  function workGlow() {
    var H = F.heat;
    if (S.method === "calcine" && S.heatC !== null && H) return H.light(S.heatC).map(function (x) { return x * 0.6; });
    if (S.method === "transmute" && S.stageX > 2.2) {
      var k = Math.min(1, S.stageX - 2.2) * 0.8;
      return [0.9 * k, 0.12 * k, 0.06 * k];
    }
    return [0, 0, 0];
  }

  function paintAll() {
    var a = S.act, LQ = A.liquid;
    if (!a) return;
    var cur = S.liq ? S.liq.cur : { color: null, level: 0, turbidity: 0.2 };
    if (a.v && a.v.liquid) {
      var shown = cur;
      if (S.method === "transmute") shown = { color: LQ.stageColor(S.stageX), level: cur.level, turbidity: cur.turbidity };
      else if (S.method === "calcine") shown = { color: A.fx.calx(cur.color, S.whiteness), level: cur.level, turbidity: 1 };
      var glow = null;
      if (S.method === "calcine" && S.heatC !== null && F.heat) glow = F.heat.emit(S.heatC);
      if (S.method === "transmute" && S.stageX > 2.2) glow = [0.3 * Math.min(1, S.stageX - 2.2), 0.02, 0.01];
      LQ.paint(a.v.liquid, shown, { dull: S.dull, glow: glow });
      a.v.liquid.visible = shown.level > 0.004;
      if (a.v.crust) {
        a.v.crust.mat.alpha = 0.12 + 0.78 * S.crust;
        a.v.crust.visible = S.method === "sublime" && S.crust > 0.02;
      }
      // Found by experiment: the vessel glows gold once (UI plan §10).
      a.v.body.mat.emit = S.found > 0 ? [0.9 * S.found, 0.68 * S.found, 0.3 * S.found] : [0, 0, 0];
    }
    if (a.receiver && a.receiver.liquid) {
      var rc = S.rec || { color: null, level: 0 };
      LQ.paint(a.receiver.liquid, { color: rc.color || cur.color, level: rc.level, turbidity: 0 }, {});
      a.receiver.liquid.visible = rc.level > 0.004;
    }
    if (a.funnel) {
      // The cloth takes the precipitate: it darkens toward the work's colour as the filtrate runs.
      var cc = cur.color ? LQ.toBase(cur.color) : [0.6, 0.6, 0.6];
      a.funnel.cloth.color = M.lerp3([0.82, 0.78, 0.68], M.scale(cc, 0.7), 0.15 + 0.6 * clamp01(S.gameProgress || 0));
    }
    if (a.beaker) LQ.paint(a.beaker.liquid, { color: cur.color, level: 0.55 * (1 - clamp01(S.gameProgress || 0)) + 0.1, turbidity: cur.turbidity }, {});
    if (a.slide) {
      var dc = cur.color ? LQ.toBase(cur.color) : LQ.toBase(LQ.WATER);
      a.slide.drop.mat.color = dc;
    }
    if (a.crack) a.crack.visible = S.cracked;
  }

  /* Ease the work's liquid to a server state over ms (0 or reduced motion: at once). */
  function liquidTo(st, ms, rec) {
    var LQ = A.liquid;
    var to = LQ.state(st, S.liq ? S.liq.cur : null);
    if (!S.liq) S.liq = { cur: to };
    var from = { color: S.liq.cur.color, level: S.liq.cur.level, turbidity: S.liq.cur.turbidity };
    if (S.liq.tw) { endTweenQuiet(S.liq.tw); S.liq.tw = null; }
    S.dull = 0;
    ms = num(ms, 0);
    var rTo = rec ? LQ.state(rec, S.rec || { color: null, level: 0, turbidity: 0 }) : null;
    var rFrom = S.rec ? { color: S.rec.color, level: S.rec.level, turbidity: 0 } : null;
    if (ms <= 0 || still() || !S.mounted) {
      S.liq.cur = to;
      if (rTo) S.rec = rTo;
      paintAll(); wake();
      return Promise.resolve(true);
    }
    return new Promise(function (resolve) {
      S.liq.tw = tween(ms, function (p) {
        var e = M.ease.inOutSine(p);
        S.liq.cur = LQ.mix(from, to, e);
        if (rTo) S.rec = rFrom ? LQ.mix(rFrom, rTo, e) : rTo;
        paintAll();
      }, function () { S.liq.tw = null; resolve(true); });
    });
  }
  function endTweenQuiet(tw) {
    var i = S.tweens.indexOf(tw);
    if (i < 0) return;
    S.tweens.splice(i, 1);
    if (tw.timer) clearTimeout(tw.timer);
    if (tw.done) tw.done();
  }

  /* --- light, by the scene clock and the day's phase ------------------------------------- */

  var LIGHT = M ? M.norm([-0.42, 0.78, 0.47]) : [0, 1, 0];
  function bell(x, c, w) { var d = (x - c) / w; return Math.exp(-d * d); }
  /* The phase of the day at a minute, as rules/sky.py draws the windows. */
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
  function tint(c, ph) {
    var t = TINT[ph] || TINT.noon;
    return [c[0] * t[0], c[1] * t[1], c[2] * t[2]];
  }
  function lights() {
    var g = S.scene, h = ((((+g.minute || 0) % 1440) + 1440) % 1440) / 60;
    var day = M.smooth(5.5, 7.5, h) * (1 - M.smooth(17.5, 19.5, h));
    var dusk = Math.max(bell(h, 6.5, 1.1), bell(h, 18.6, 1.1));
    var ph = phaseAt(g.minute), L = {};
    var fire = S.heatK * S.lit * S.flick;
    var kitK = S.set && S.set.kind === "kit";
    if (!kitK) {
      // A laboratory is lit by its fire and its window: a cool grey from the window by day,
      // little else at night.
      L.amb = M.lerp3([0.05, 0.045, 0.042], [0.11, 0.11, 0.115], day);
      L.fillDir = M.norm([-0.4, 0.7, 0.6]);
      L.fillCol = M.add([0.12, 0.1, 0.09], M.scale([0.3, 0.32, 0.36], day));
      L.keyCol = M.scale([1.5, 0.95, 0.5], 0.3 + 1.2 * fire);
      if (S.set.window) S.set.window.setLight(M.lerp3([0.05, 0.07, 0.14], [0.7, 0.78, 0.86], day), 0.6 + 0.3 * day);
    } else {
      // At night the circle's 0.04 left the crucible's camera side a black shape in the live
      // capture; a little more moonlit sky keeps it a crucible.
      L.amb = M.add(M.lerp3([0.07, 0.075, 0.1], [0.36, 0.37, 0.4], day), [0.06 * dusk, 0.03 * dusk, 0.012 * dusk]);
      L.fillDir = LIGHT;
      var moon = (1 - day) * (1 - dusk);
      L.fillCol = M.add(M.add(M.scale([0.86, 0.86, 0.9], 0.85 * day), M.scale([0.7, 0.42, 0.24], 0.55 * dusk)),
                        M.scale([0.22, 0.29, 0.5], 0.42 * moon));
      // The spirit lamp is the key: a pale, slightly blue light, small by day, the light that
      // matters at night.
      var kk = (0.2 + 0.9 * (1 - day)) * (0.15 + 1.1 * fire);
      L.keyCol = [1.25 * kk, 1.0 * kk, 0.7 * kk];
    }
    L.amb = tint(L.amb, ph);
    L.fillCol = tint(L.fillCol, ph);
    L.keyPos = S.set ? S.set.keyPos : [0, 0.2, 0];
    L.phase = ph;
    return L;
  }

  /* --- poses ------------------------------------------------------------------------------ */

  function applyPose(ts, live) {
    var set = S.set, a = S.act;
    if (!set) return;
    set.heat(S.heatK * S.lit, live && !still() ? S.flick : 1);
    if (!a) return;
    if (a.stir) {
      if (live && !still()) {
        var ang = ts * (2.5 + 4 * clamp01(S.stir));
        a.stir.pos = [a.base[0] + Math.cos(ang) * 0.02, a.base[1] + 0.02, a.base[2] + Math.sin(ang) * 0.02];
        a.stir.rot = [Math.sin(ang) * 0.12, 0, Math.cos(ang) * 0.12];
      } else {
        a.stir.pos = [a.base[0] + 0.012, a.base[1] + 0.02, a.base[2]];
        a.stir.rot = [0, 0, 0.12];
      }
    }
    if (a.root) {
      a.root.alpha = S.actAlpha === undefined ? 1 : S.actAlpha;
      a.root.pos = [0, S.actLift || 0, 0];
    }
  }

  /* --- camera --------------------------------------------------------------------------------
     Pitched down onto the work (UI plan §6.3: about 35 degrees at the kit; a laboratory a little
     flatter, so the wall and its window are seen). The field of view is SOLVED from each set's
     own fit points, as every other stage solves it, so the work fills the stage at every aspect
     and nothing falls off its edges. */
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

  /* The frame moves toward the work. Fitted to the whole bench, a 12 cm vial at the laboratory's
     cold spot was about 5% of the stage's height at 1280x720 (the live capture), and the assay's
     drop a few pixels at the kit. So each method has a FOCUS: the set's own fit cloud shrunk
     round the active vessel by FOCUS_SCALE (1 is no focus: Distill keeps the whole bench, it
     needs the athanor and the receiver both). The cloud eases between the two with the swap,
     so the frame glides rather than cuts; reduced motion snaps. */
  var FOCUS_SCALE = { kit: { hot: 1, work: 0.55 }, lab: { hot: 0.72, work: 0.5 } };
  function focusCloud() {
    var fit = S.set.fit, a = S.act, act = ACT[S.method];
    if (!a || !a.base || !act || act.alembic) return null;
    var k = FOCUS_SCALE[S.set.kind === "kit" ? "kit" : "lab"][act.spot];
    if (k >= 0.999) return null;
    var c = [a.base[0], a.base[1] + 0.1, a.base[2]], fc = fit.centre, pts = new Float32Array(fit.pts.length);
    for (var i = 0; i < pts.length; i += 3) {
      pts[i] = c[0] + (fit.pts[i] - fc[0]) * k;
      pts[i + 1] = c[1] + (fit.pts[i + 1] - fc[1]) * k;
      pts[i + 2] = c[2] + (fit.pts[i + 2] - fc[2]) * k;
    }
    return { pts: pts, centre: c, dist: fit.dist * k };
  }
  /* The cloud the camera frames now: from the last frame's toward this arrangement's, by camMix. */
  function cloud() {
    var fit = S.set.fit, to = S.focus || fit, from = S.camFrom;
    if (!from || from.pts.length !== to.pts.length) return to;
    var m = clamp01(S.camMix);
    if (m >= 1) return to;
    var pts = new Float32Array(to.pts.length);
    for (var i = 0; i < pts.length; i++) pts[i] = from.pts[i] + (to.pts[i] - from.pts[i]) * m;
    return { pts: pts, centre: M.lerp3(from.centre, to.centre, m), dist: from.dist + (to.dist - from.dist) * m };
  }
  /* A new arrangement: the frame starts from where it is and eases to the new focus. */
  function refocus() {
    if (!S.set) return;
    // Another set (kit to laboratory) is a cut, not a glide: the clouds are of different rooms.
    var start = S.camSet === S.set ? cloud() : null;
    S.camSet = S.set;
    S.focus = focusCloud();
    if (S.camTw) { endTweenQuiet(S.camTw); S.camTw = null; }
    if (!S.mounted || still() || !start) { S.camFrom = null; S.camMix = 1; return; }
    S.camFrom = start; S.camMix = 0;
    S.camTw = tween(450, function (p) { S.camMix = M.ease.inOutSine(p); }, function () { S.camTw = null; S.camFrom = null; });
  }
  function camera() {
    var aspect = S.cssW / Math.max(1, S.cssH), fit = S.set.fit, cl = cloud();
    var pts = cl.pts, target = cl.centre, dist = cl.dist;
    var pitch = fit.pitch * D2R;
    var eye = [target[0], target[1] + Math.sin(pitch) * dist, target[2] + Math.cos(pitch) * dist];
    var view = M.lookAt(eye, target, [0, 1, 0]);
    var e = extent(pts, view);
    var tH = (e[3] - e[1]) / (2 * fit.h), tW = (e[2] - e[0]) / (2 * fit.w * aspect);
    var t = Math.max(tH, tW);
    var proj = M.perspective(2 * Math.atan(t), aspect, 0.05, 60);
    // Lens shift: the work sits a little above the middle, leaving the lower part of the stage
    // for the info line and the rising minigame strip (as every other stage does).
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

  function draw() {
    var r = S.r;
    if (!r || !r.gl || S.lost || !S.set) return;
    var cam = camera(), L = lights(), a = S.act;
    var at = a && a.top ? a.top : S.set.hot;
    var glowCol = workGlow(), fk = S.flare * 2.6, fc = S.flareCol;
    r.begin({
      vp: cam.vp, view: cam.view, proj: cam.proj, eye: cam.eye, amb: L.amb, keyPos: L.keyPos, keyCol: L.keyCol,
      fillDir: L.fillDir, fillCol: L.fillCol, glowPos: [at[0], at[1] - 0.04, at[2] + 0.06], glowCol: glowCol,
      flarePos: [at[0], at[1] + 0.05, at[2] + 0.15], flareCol: [fc[0] * fk, fc[1] * fk, fc[2] * fk],
      exposure: S.dim, reveal: S.reveal, bg: BG, fade: [4.2, 10.5],
      px: r.canvas.height / (2 * cam.t)
    });
    S.stats.key = L.keyCol.slice();
    S.stats.glow = glowCol.slice();
    S.stats.fill = L.fillCol.slice();
    S.stats.phase = L.phase;

    var items = [], I = M.ident();
    if (S.set.kind === "kit" && S.groundNode) collect(S.groundNode, I, 1, 0, items);
    collect(S.set.root, I, 1, 0, items);
    if (S.leaving) collect(S.leaving, I, 1, 0, items);
    if (a && a.root) collect(a.root, I, 1, S.glint, items);
    if (S.product && S.productOn) collect(S.product, I, 1, S.glint, items);

    var opaque = [], fade = [], liquids = [], alpha = [], add = [];
    items.forEach(function (it) {
      var n = it.n;
      if (n.liquid) {
        // The fill height in the world: the node's own base plus the level's share of its
        // inner height, scaled as the node is (a tilted beaker reads close enough).
        var L2 = n.liquid;
        n.mat.fillY = it.m[13] + it.m[5] * (L2.lo + clamp01(L2.level) * (L2.hi - L2.lo));
        liquids.push(it);
        return;
      }
      var pass = n.mat.pass || "opaque";
      if (pass === "opaque") (it.a < 0.999 ? fade : opaque).push(it);
      else if (pass === "alpha") alpha.push(it);
      else add.push(it);
    });
    alpha.forEach(function (it) {
      var dx = it.m[12] - cam.eye[0], dy = it.m[13] - cam.eye[1], dz = it.m[14] - cam.eye[2];
      it.depth = dx * dx + dy * dy + dz * dz;
    });
    alpha.sort(function (p, q) {
      var oa = p.n.mat.order || 0, ob = q.n.mat.order || 0;
      return oa !== ob ? oa - ob : q.depth - p.depth;
    });
    function issue(list) {
      list.forEach(function (it) {
        if (it.n.ranges) it.n.ranges.forEach(function (rg) { r.draw(it.n.mesh, it.m, it.n.mat, it.a, it.glint, rg); });
        else r.draw(it.n.mesh, it.m, it.n.mat, it.a, it.glint, null);
      });
    }
    r.setBlend("opaque"); issue(opaque);
    r.setBlend("fade"); issue(fade);
    drawLiquids(r, liquids);
    r.setBlend("alpha"); issue(alpha);
    r.setBlend("add"); issue(add);
    r.points(S.particles.out[0], S.particles.counts[0], false);
    r.points(S.particles.out[1], S.particles.counts[1], true);
    S.stats.liquids = liquids.length;
    S.stats.lastDraws = r.draws;
    S.stats.draws += r.draws;
  }

  /* The liquids, in two passes. The shader paints a liquid's BACK faces as its top (01-gl.js);
     drawn in one blended pass, a back face behind the near wall could land after the body in
     front of it and paint the top's colour over the body. So the backs go first, writing depth
     (the "fade" blend), and the fronts after, blended over them: through the opening the top,
     through the wall the body. Face culling is the only state touched, and it is put back. */
  function drawLiquids(r, list) {
    if (!list.length) return;
    var gl = r.gl, cull = gl && typeof gl.enable === "function" && gl.CULL_FACE !== undefined;
    function each() { list.forEach(function (it) { r.draw(it.n.mesh, it.m, it.n.mat, it.a, it.glint, null); }); }
    if (!cull) { r.setBlend("alpha"); each(); return; }
    gl.enable(gl.CULL_FACE);
    gl.cullFace(gl.FRONT);
    r.setBlend("fade");
    each();
    gl.cullFace(gl.BACK);
    r.setBlend("alpha");
    each();
    gl.disable(gl.CULL_FACE);
  }

  /* --- size and visibility --------------------------------------------------------------------- */
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

  /* --- heat and reaction ------------------------------------------------------------------------ */

  function rangeOf(range) {
    if (Array.isArray(range) && range.length >= 2) return [num(range[0], 0), num(range[1], 100)];
    if (range && typeof range === "object" && range.lo !== undefined) return [num(range.lo, 0), num(range.hi, 100)];
    return HEAT_RANGE[S.method] || [20, 100];
  }
  /* The flame follows the heat: 0.15 at the bottom of the gauge, 1.15 at the top. Calcine's
     charge glows by the temperature itself (the forge's table). Marks the stage live. */
  function heat(c, range) {
    c = num(c, null);
    if (c === null) return;
    var rg = rangeOf(range), k = 0.15 + (c - rg[0]) / Math.max(1, rg[1] - rg[0]);
    S.heatC = c;
    S.heatK = Math.max(0, Math.min(1.3, k));
    S.gameLast = now();
    if (!S.gameOn) S.gameOn = true;
    paintAll();
    wake();
  }
  /* The churn follows the reaction (0..100): bubbles and, past 60, vapour. Crossing `flare_at`
     upward is the minigame's overshoot: a puff of vapour (the game rings the hiss), no crack, no shake
     (UI plan §6.4: a quality signal only). */
  function reaction(v, spec) {
    v = num(v, null);
    if (v === null) return;
    if (spec && spec.flare_at !== undefined) S.flareAt = num(spec.flare_at, S.flareAt);
    var was = S.reaction;
    S.reaction = Math.max(0, Math.min(100, v));
    if (was < S.flareAt && S.reaction >= S.flareAt && S.act) {
      S.stats.puffs++;
      A.fx.puff(FX.emit, mouthPoint(S.act), S.liq && S.liq.cur.color);
    }
    S.gameLast = now();
    if (!S.gameOn) S.gameOn = true;
    wake();
  }

  /* --- the game --------------------------------------------------------------------------------- */

  function game(method, opts) {
    opts = opts || {};
    var LQ = A.liquid;
    var g = { method: method, on: false, state: {}, crust: 0 };
    function mine() { return S.game === g; }
    function begin() {
      if (S.game !== g) S.game = g;
      if (g.on) return;
      g.on = true; S.gameOn = true;
      S.gameStart = S.liq ? { color: S.liq.cur.color, level: S.liq.cur.level, turbidity: S.liq.cur.turbidity } : null;
      S.recStart = S.rec ? { color: S.rec.color, level: S.rec.level, turbidity: 0 } : { color: null, level: 0, turbidity: 0 };
      S.gameEnd = opts.end ? LQ.state(opts.end, S.gameStart) : null;
      S.gameRecEnd = opts.end && opts.end.receiver ? LQ.state(opts.end.receiver, S.recStart) : null;
      S.gameProgress = 0;
      if (method === "sublime") S.crust = 0;
      if (method === "calcine") S.whiteness = 0;
      if (method === "transmute") S.stageX = 0;
    }
    var view = {
      update: safe("game.update", function (st) {
        if (!st || typeof st !== "object") return;
        begin();
        g.state = st;
        S.gameLast = now();
        var c = st.heat !== undefined ? st.heat : st.c;
        if (c !== undefined && c !== null) heat(c, st.heatRange);
        if (st.reaction !== undefined) reaction(st.reaction, st);
        if (st.progress !== undefined) {
          var p = clamp01(st.progress);
          S.gameProgress = p;
          if (S.gameEnd && S.gameStart) S.liq.cur = LQ.mix(S.gameStart, S.gameEnd, p);
          if (method === "distill" && st.receiver === undefined) {
            var lost = S.gameStart ? Math.max(0, S.gameStart.level - (S.liq ? S.liq.cur.level : 0)) : 0;
            var rEnd = S.gameRecEnd;
            S.rec = rEnd ? LQ.mix(S.recStart, rEnd, p)
                         : { color: S.recStart.color || (S.liq && S.liq.cur.color), level: Math.min(1, S.recStart.level + lost), turbidity: 0 };
          }
        }
        if (method === "distill" && st.receiver !== undefined) {
          S.rec = { color: (S.rec && S.rec.color) || (S.liq && S.liq.cur.color), level: clamp01(st.receiver), turbidity: 0 };
        }
        if (st.whiteness !== undefined) S.whiteness = clamp01(st.whiteness);
        else if (method === "calcine" && st.progress !== undefined) S.whiteness = clamp01(st.progress);
        if (st.pour !== undefined) S.pourK = clamp01(st.pour);
        if (st.stir !== undefined) S.stir = clamp01(st.stir);
        if (st.crust !== undefined) {
          var cr = clamp01(st.crust);
          if (S.crust - cr > 0.3 && S.act) A.fx.scrape(FX.emit, [S.act.base[0], S.act.base[1] + 0.2, S.act.base[2] + 0.05]);
          S.crust = cr;
        }
        if (st.stage !== undefined) {
          var idx = typeof st.stage === "string" ? LQ.STAGES.indexOf(st.stage.toLowerCase()) : num(st.stage, 0);
          if (idx >= 0) S.stageX = Math.min(3, idx + (st.peak !== undefined ? clamp01(st.peak) * 0.6 : 0));
        }
        paintAll();
        if (mine()) wake();
      }),
      heat: safe("game.heat", function (c, range) { begin(); heat(c, range); }),
      reaction: safe("game.reaction", function (v, spec) { begin(); reaction(v, spec); }),
      hit: safe("game.hit", function (strength, index) {
        if (!mine()) return;
        begin();
        S.gameLast = now();
        var s = clamp01(strength === undefined ? 1 : strength), a = S.act;
        if (!a) return;
        var col = (S.liq && S.liq.cur.color) || LQ.WATER, top = liquidTop(a.v) || a.top;
        if (method === "react" && a.tip) {
          LQ.drop(FX.emit, a.tip, col);
          LQ.bloom(FX.emit, top, col);
        } else if (method === "transmute") {
          A.fx.wash(FX.emit, top, LQ.stageColor(Math.round(S.stageX)));
          S.glint = Math.max(S.glint, 0.5 * s);
        } else if (method === "bottle" && a.v && a.v.stopper && (index === 1 || (S.liq && S.liq.cur.level > 0.05))) {
          a.v.stopper.visible = true;
        } else {
          A.fx.tick(FX.emit, top);
        }
        // A hit is a small light, not a flash: at 0.12 + 0.18 a run of React's drops burned a
        // white blob over the flask in the live capture.
        S.flare = Math.max(S.flare, 0.03 + 0.05 * s); S.flareCol = LQ.bright(col);
        wake();
      }),
      // A miss: a fizz at the surface. Nothing is undone.
      miss: safe("game.miss", function () {
        if (!mine()) return;
        S.gameLast = now();
        var a = S.act;
        if (a) A.liquid.fizz(FX.emit, liquidTop(a.v) || a.top, S.liq && S.liq.cur.color);
        wake();
      }),
      end: safe("game.end", function () {
        g.on = false;
        if (S.game === g) { S.gameOn = false; S.reaction = 0; S.pourK = 0; S.over = false; }
        wake();
      })
    };
    S.game = g;
    return view;
  }

  /* --- flourishes ------------------------------------------------------------------------------ */
  var KINDS = { tier: "tier", tierUp: "tier", flawless: "flawless", land: "land", fail: "fail", flare: "flare", found: "found" };

  function shake(px, ms) {
    var cv = S.canvas;
    if (!cv || still()) return;
    // The STAGE canvas shakes, never the page: a transform on this one element.
    tween(ms, function (q) {
      var a = px * (1 - q) * (1 - q);
      cv.style.transform = q >= 1 ? "" :
        "translate(" + (Math.sin(q * 71) * a).toFixed(2) + "px," + (Math.cos(q * 53) * a).toFixed(2) + "px)";
    }, function () { cv.style.transform = ""; });
  }

  function flourish(kind) {
    return new Promise(function (resolve) {
      var k = KINDS[kind];
      if (!S.mounted || !S.set || !k) { resolve(false); return; }
      var a = S.act, quiet = still();
      var top = a ? ((a.v && liquidTop(a.v)) || a.top || S.set.hot) : S.set.hot;
      var col = (S.liq && S.liq.cur.color) || A.liquid.WATER;
      if (k === "tier") {
        sound("alchemy.tier.up");
        A.fx.gilt(FX.emit, top, 10);
        tween(380, function (q) { S.glint = Math.sin(Math.PI * q) * 0.9; }, function () { S.glint = 0; resolve(true); });
      } else if (k === "flawless") {
        sound("alchemy.flawless");
        A.fx.gilt(FX.emit, top, 70);
        S.flare = Math.max(S.flare, 1.2); S.flareCol = [1, 0.82, 0.48];
        tween(700, function (q) { S.glint = Math.sin(Math.PI * q) * 1.2; }, function () { S.glint = 0; resolve(true); });
        shake(6, 250);
      } else if (k === "found") {
        // A formula found by experiment: the vessel glows gold once (UI plan §10).
        sound("alchemy.found");
        A.fx.gilt(FX.emit, top, 8);
        tween(quiet ? 400 : 800, function (q) { S.found = Math.sin(Math.PI * q); paintAll(); }, function () { S.found = 0; paintAll(); resolve(true); });
      } else if (k === "fail") {
        // The liquid clouds and dulls, and the stage dims 30% for 600ms. The dull stays: it is
        // what the work now is, until another state is sent.
        sound("alchemy.fail");
        tween(600, function (q) {
          S.dim = q < 0.12 ? 1 - 0.3 * (q / 0.12) : (q < 0.55 ? 0.7 : 0.7 + 0.3 * M.ease.inOutSine((q - 0.55) / 0.45));
          S.dull = Math.min(1, q * 2);
          paintAll();
        }, function () { S.dim = 1; S.dull = 1; paintAll(); resolve(true); });
      } else if (k === "flare") {
        // UI plan §7.5, the owner's Q9.4: a failed roll whose mishap landed. The burst, the
        // light's spike, smoke, the crack and the lost liquid; the brass FLARE word is U1's.
        // Reduced motion keeps the spike, the crack and the level: they are states.
        sound("alchemy.flare");
        sound("alchemy.crack");
        S.flare = Math.max(S.flare, 2.2); S.flareCol = [1, 0.62, 0.26];
        S.cracked = true;
        A.fx.flare(FX.emit, top, col);
        var lvl = S.liq ? S.liq.cur.level : 0;
        var lost = { level: lvl * 0.45 };
        liquidTo(lost, quiet ? 0 : 400);
        shake(7, 250);
        paintAll();
        tween(quiet ? 300 : 650, function () {}, function () { resolve(true); });
      } else if (k === "land") {
        sound("alchemy.land");
        land(resolve, top, col);
      }
      wake();
    });
  }

  /* The product lands (UI plan §10): the vial lifts out of the work in its own colour and is
     gone, and U1 flies its own copy from productRect() to the shelf row. Reduced motion: it
     glints, then it is not there. */
  function land(resolve, top, col) {
    var P = K.props;
    if (!S.product) S.product = P.product("vial", A.liquid.toBase(col));
    var pr = S.product;
    // The vial's liquid is the herb kit's plain material: its colour is the work's.
    pr.kids.forEach(function (n) { if (n.mat && n.mat.order === 1) n.mat.color = A.liquid.toBase(col); });
    var at = [top[0], top[1] + 0.02, top[2]];
    pr.pos = at.slice(); pr.scl = [0.6, 0.6, 0.6]; pr.alpha = 1; pr.visible = true;
    S.productOn = true;
    if (still()) {
      tween(500, function (q) { S.glint = q < 0.5 ? 0.4 : 0; },
            function () { S.productOn = false; pr.visible = false; S.glint = 0; resolve(true); });
      return;
    }
    A.fx.gilt(FX.emit, at, 8);
    tween(500, function (q) {
      var e = M.ease.outCubic(Math.min(1, q / 0.7));
      pr.pos = [at[0], at[1] + 0.22 * e, at[2]];
      pr.rot = [0, e * 1.2, 0];
      pr.alpha = q > 0.75 ? (1 - q) / 0.25 : 1;
    }, function () { S.productOn = false; pr.visible = false; resolve(true); });
  }

  /* Where the product is (or the work, when nothing is landing), in viewport pixels. */
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
    var cam = S.cam || camera(), b = S.canvas.getBoundingClientRect(), pts = [], items = [];
    var root = S.productOn && S.product ? S.product : (S.act && S.act.v ? S.act.v.root : null);
    if (root) {
      collect(root, M.ident(), 1, 0, items, true);
      items.forEach(function (it) {
        if (it.n.mat && it.n.mat.unlit) return;
        var bb = it.n.mesh.bounds;
        for (var c = 0; c < 8; c++) pts.push(M.xform(it.m, [c & 1 ? bb.hi[0] : bb.lo[0], c & 2 ? bb.hi[1] : bb.lo[1], c & 4 ? bb.hi[2] : bb.lo[2]]));
      });
    }
    if (!pts.length) pts.push(S.act && S.act.top ? S.act.top : S.set.hot);
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    pts.forEach(function (p) {
      var v = M.xform(cam.vp, [p[0], p[1], p[2]]);
      var sx = b.left + (v[0] / v[3] * 0.5 + 0.5) * b.width, sy = b.top + (1 - (v[1] / v[3] * 0.5 + 0.5)) * b.height;
      x0 = Math.min(x0, sx); x1 = Math.max(x1, sx); y0 = Math.min(y0, sy); y1 = Math.max(y1, sy);
    });
    var w = Math.max(24, x1 - x0), h = Math.max(24, y1 - y0);
    return new Rect((x0 + x1) / 2 - w / 2, (y0 + y1) / 2 - h / 2, w, h);
  }

  /* --- the tool: the method's arrangement swaps --------------------------------------------- */
  function setTool(method) {
    return new Promise(function (resolve) {
      if (METHODS.indexOf(method) < 0) { resolve(false); return; }
      finishSwap();
      var same = S.method === method;
      S.method = method;
      S.heatK = (ACT[method] || {}).rest || 0;
      S.heatC = null;
      if (!S.set) S.set = setFor(A.lab.kindOf(S.scene));
      if (same && S.act) { resolve(true); return; }
      var old = S.act && S.act.root;
      arrange(!S.mounted);
      if (!S.mounted) { resolve(true); return; }
      // The old glass lifts out and the new sets down with a clink, 450ms (UI plan §10); under
      // reduced motion, a 120ms crossfade.
      S.leaving = old || null;
      var sw = { resolve: resolve };
      S.swap = sw;
      var total = still() ? 120 : 450;
      if (still()) {
        sw.tw = tween(total, function (p) { S.actAlpha = p; S.actLift = 0; if (old) old.alpha = 1 - p; });
      } else {
        sw.tw = tween(total, function (p) {
          var lead = old ? 0.3 : 0;
          if (old) { old.alpha = Math.max(0, 1 - p / 0.3); old.pos = [0, 0.15 * Math.min(1, p / 0.3), 0]; }
          var q = p < lead ? 0 : (p - lead) / (1 - lead), e = M.ease.outCubic(q);
          S.actAlpha = Math.min(1, q * 2.5);
          S.actLift = 0.12 * (1 - e);
        });
      }
      sw.tw.done = function () { if (S.swap === sw) finishSwap(); };
      wake();
    });
  }
  function finishSwap() {
    var sw = S.swap;
    if (!sw) return;
    S.swap = null;
    if (sw.tw) endTweenQuiet(sw.tw);
    if (S.leaving) { S.leaving.alpha = 1; S.leaving.pos = [0, 0, 0]; }
    S.leaving = null;
    S.actAlpha = 1; S.actLift = 0;
    sw.resolve(true);
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
        cv.className = "alchemy-stage-canvas";
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
        // A crack and a dulled liquid belong to the work that went wrong, not to the bench.
        S.cracked = false; S.dull = 0;
        applyScene();
        // Open the bench (UI plan §10): the floor fades in from the page's dark and the lamp or
        // the athanor lights; reduced motion, a fade only.
        S.reveal = 0;
        // The fire lights by its own factor, not by tweening the heat: a tween of the heat itself
        // overwrote the rest heat setTool sets right after mount, and the lamp stayed out.
        var quiet = still();
        tween(quiet ? 120 : 320, function (p) { S.reveal = M.ease.outCubic(p); });
        S.lit = quiet ? 1 : 0;
        if (!quiet) tween(420, function (p) { S.lit = M.ease.outCubic(p); });
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
    if (S.liq) S.liq.tw = null;
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
    S.dim = 1; S.glint = 0; S.flare = 0; S.found = 0; S.gameOn = false; S.flick = 1; S.reaction = 0; S.pourK = 0;
    S.game = null; S.cam = null; S.productOn = false;
  }

  function setScene(g) {
    g = g || {};
    var kind = A.lab.kindOf(g);
    S.scene = { kind: kind, biome: g.biome || "", roofed: !!g.roofed, minute: num(g.minute, S.scene.minute) };
    if (S.mounted) applyScene();
    else { S.set = setFor(kind); arrange(true); }
  }

  /* The vessel and what is in it. Rebuilt only when what it is changes; a new vessel clears a
     crack a flare left. The liquid and the receiver are the server's start state. */
  function setVessel(v) {
    v = v && typeof v === "object" ? v : null;
    var key = v ? JSON.stringify([v.id || "", v.kind || ""]) : "";
    S.vin = v ? { id: v.id || "", kind: v.kind || "" } : null;
    if (key !== S.vesselKey) {
      S.vesselKey = key;
      S.cracked = false;
    }
    S.dull = 0;
    var LQ = A.liquid;
    // No liquid sent is an empty vessel: the stage never pours what the server did not.
    S.liq = { cur: LQ.state(v && v.liquid, { color: null, level: 0, turbidity: 0.2 }) };
    S.rec = v && v.receiver ? LQ.state(v.receiver, { color: null, level: 0, turbidity: 0 }) : { color: null, level: 0, turbidity: 0 };
    if (!S.set) S.set = setFor(A.lab.kindOf(S.scene));
    arrange(true);
    wake();
  }

  function liquid(st, ms) { return liquidTo(st, ms, st && st.receiver); }

  function reducedMotion(on) {
    S.reduced = !!on;
    if (S.reduced && S.particles) S.particles.clear();
    if (S.reduced && S.canvas) S.canvas.style.transform = "";
    if (S.reduced) S.flick = 1;
    wake();
  }

  /* For the harness and the verification notes. Not part of the contract. */
  function debug() {
    var ms = S.stats.ms.slice().sort(function (a, b) { return a - b; });
    var sum = ms.reduce(function (a, b) { return a + b; }, 0);
    var a = S.act, lq = a && a.v && a.v.liquid;
    return { frames: S.stats.frames, draws: S.stats.draws, lastDraws: S.stats.lastDraws, rafs: S.stats.rafs, raf: !!S.raf,
             avgMs: ms.length ? sum / ms.length : 0, p95Ms: ms.length ? ms[Math.floor(ms.length * 0.95)] : 0,
             scene: S.set ? S.set.kind : null, method: S.method, vessel: a ? a.kind : null,
             liquid: S.liq ? { color: S.liq.cur.color, level: +S.liq.cur.level.toFixed(4), turbidity: +S.liq.cur.turbidity.toFixed(4) } : null,
             shown: lq ? { color: lq.mat.color.map(function (x) { return +x.toFixed(4); }), turbid: lq.mat.turbid, fillY: lq.mat.fillY, visible: lq.visible } : null,
             receiver: S.rec ? +S.rec.level.toFixed(4) : 0, heatK: +S.heatK.toFixed(4), heatC: S.heatC, reaction: S.reaction,
             flick: S.flick, cracked: S.cracked, dull: S.dull, crust: S.crust, stageX: S.stageX, whiteness: S.whiteness,
             stopper: !!(a && a.v && a.v.stopper && a.v.stopper.visible), liquids: S.stats.liquids,
             key: S.stats.key, glow: S.stats.glow, fill: S.stats.fill, phase: S.stats.phase || null,
             particles: S.particles ? S.particles.alive() : 0, tweens: S.tweens.length,
             hidden: S.hiddenBox || S.hiddenTab, flare: S.flare, puffs: S.stats.puffs,
             gpu: S.r ? { buffers: Object.keys(S.r.bufs || {}).length, textures: Object.keys(S.r.texs || {}).length } : null,
             buffer: S.canvas ? [S.canvas.width, S.canvas.height] : null };
  }
  function resetStats() { S.stats.frames = 0; S.stats.draws = 0; S.stats.ms = []; S.stats.rafs = 0; }

  if (READY) {
    S.particles = new K.Particles();
  }

  function noop() {}
  function resolved(v) { return function () { return Promise.resolve(v); }; }
  var NOGAME = { update: noop, hit: noop, miss: noop, end: noop, heat: noop, reaction: noop };

  window.AlchemyStage = READY ? {
    available: safe("available", available, false),
    mount: function (host) { try { return mount(host); } catch (e) { warn("mount", e); return Promise.resolve(false); } },
    unmount: safe("unmount", unmount),
    setScene: safe("setScene", setScene),
    setTool: function (m) { try { return setTool(m); } catch (e) { warn("setTool", e); return Promise.resolve(false); } },
    setVessel: safe("setVessel", setVessel),
    liquid: function (st, ms) { try { return liquid(st, ms); } catch (e) { warn("liquid", e); return Promise.resolve(false); } },
    heat: safe("heat", heat),
    reaction: safe("reaction", reaction),
    game: function (m, o) { try { return game(m, o); } catch (e) { warn("game", e); return NOGAME; } },
    flourish: function (k) { try { return flourish(k); } catch (e) { warn("flourish", e); return Promise.resolve(false); } },
    productRect: safe("productRect", productRect, null),
    reducedMotion: safe("reducedMotion", reducedMotion),
    _debug: safe("_debug", debug, null),
    _resetStats: safe("_resetStats", resetStats)
  } : {
    // The parts did not load: every call is a quiet no-op, and U1 shows its flat stage.
    available: function () { return false; },
    mount: resolved(false), unmount: noop, setScene: noop, setTool: resolved(false),
    setVessel: noop, liquid: resolved(false), heat: noop, reaction: noop,
    game: function () { return NOGAME; }, flourish: resolved(false),
    productRect: function () { return window.DOMRect ? new window.DOMRect(0, 0, 0, 0) : null; },
    reducedMotion: noop,
    _debug: function () { return null; }, _resetStats: noop
  };
})();
