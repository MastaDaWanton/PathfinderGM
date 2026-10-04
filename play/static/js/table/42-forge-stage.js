// The play table, part 42 (the forge's 3D stage). Classic script; everything it defines
// lives inside one IIFE and leaves exactly one global, window.ForgeStage, because the
// table's numbered modules share a single global scope.
//
// WHAT IT IS. The middle of the forge bench (UI plan §6.3, §7): the anvil at the centre, the
// hearth to its left, the quench and the tool rack to its right, on the ground you stand on
// (the field kit) or in a smithy, with the work built from its pieces on the anvil and lit
// by its own heat. Its interface is the contracts' §11, and lane U2 builds against nothing
// else:
//
//   available() mount(host) unmount() setScene({kind, biome, roofed, minute})
//   setTool(method) setWork({gear, base, pieces, quality_index, hot_c}) heat(celsius)
//   game(method) flourish(kind) productRect() reducedMotion(bool)
//
// `base` may be the weapon or armour id (the record's `base`) or the table row itself; with a
// row the family is read from its category, damage type, hands and components (UI plan §7.3),
// with an id from the id's words (forge-stage/02-families.js). `pieces[slot].color` is the
// server's material colour ("#rrggbb", or [r, g, b] in 0..1 or 0..255).
//
// THE GAME VIEW. game(method) returns {update(state), hit(strength, index), miss(index),
// end()}, as the herb stage's does. Every state key is optional, and the stage shows what it
// is given (UI plan §9's "on the stage" column):
//   heat_c   the metal's temperature, every method (the needle on the strip's gauge)
//   ring 0..1, struck   Forge, Fold, Strengthen, Assemble: the hammer rises as the beat ring
//                       closes and comes down on `struck`
//   pump 0..1           Smelt: the bellows press and the hearth brightens
//   tap                 Smelt: slag runs
//   pour 0..1           Alloy: the crucible tips
//   plunged, bath       Quench: the work goes under; steam and the vapour jacket follow
//   temper_c            Temper: the oxide colour run along the blade
//   pass 0..1           Hone: the edge slides along the stone, which turns
//   coverage 0..1       Finish: the bluing takes
//   folds               Fold: the banding tightens with every fold
//
// HOW IT IS BUILT. By hand, in WebGL1, on the herb stage's renderer, maths, meshes, biome
// ground and particles (play/static/js/bench-stage/00-04, reused as is), with the forge's own
// parts in play/static/js/forge-stage/. The app bundles no third-party JavaScript.
//
// THE LIGHT. Three point lights is what the house shader has, and the forge spends them on
// the three things that glow: the HEARTH is the key (warm, and flickering only while a game is
// live), the HOT METAL is the second (its colour and intensity from the prior-art heat table
// and the fourth power of its temperature, so a blank at yellow heat lights the anvil and dims
// as it cools, UI plan §7.2), and a STRIKE throws the third as a flash. The sky, or a smithy's
// hanging lamp, is the directional fill, by the scene clock.
//
// RENDER ON DEMAND (UI plan §7.4: "idle, the hearth is lit steadily and the bench draws no
// frames"). The three.js manual's "rendering on demand": nothing draws until something asks,
// and a frame only schedules the next while something still moves: a tween, a pose easing in,
// the heat shown catching up with the heat given, a live game, or a particle not yet dead. The
// hearth's flicker is the one thing that would keep a loop alive for ever, so it runs only
// while a game is sending states; when the states stop, the flicker stops with them. `wake` is
// the only place requestAnimationFrame is called, and tests/test_forge_stage.py holds it there
// and counts zero frames over ten idle seconds.
//
// WHAT IT MAY NOT DO (the owner's rule: no motion that makes a menu harder to use). The canvas
// takes no pointer events, every flourish ends on its own inside 1.1 s, and the Flawless shake
// moves the STAGE canvas only. Nothing here can throw into a caller: without WebGL every call
// is a quiet no-op and `available()` says false, so U2 shows its flat icon stage.
(function () {
  "use strict";

  var K = window.BenchStageKit || {};
  var F = window.ForgeStageKit || {};
  var M = K.math;
  var READY = !!(K.math && K.Renderer && K.mesh && K.ground && K.Particles &&
                 F.heat && F.geo && F.props && F.families && F.smithy && F.fx);
  var D2R = Math.PI / 180;
  var BG = [13 / 255, 11 / 255, 9 / 255];          // --bg, #0d0b09
  var CANDLE = [0.94, 0.75, 0.44];                  // --candle, #f0c070
  var MAX_PIXELS = 3840 * 2160;
  var METHODS = ["smelt", "alloy", "forge", "quench", "temper", "fold", "hone", "assemble", "finish",
                 "strengthen", "assay"];
  var SLOTS = { weapon: ["head", "haft", "fittings"], armour: ["body", "fastenings", "lining"],
                shield: ["body", "fastenings", "lining"] };
  // Methods where the blank alone is on the anvil: the haft and fittings join at Assemble.
  var HEAD_ONLY = { forge: 1, fold: 1, strengthen: 1, quench: 1, temper: 1, hone: 1 };
  // Methods that strike with a hammer, so the hammer answers the beat ring.
  var STRIKES = { forge: 1, fold: 1, strengthen: 1, assemble: 1 };

  var S = {
    host: null, canvas: null, r: null, ro: null, mounted: false, lost: false, raf: 0, lastT: 0,
    scene: { kind: "kit", biome: "forest", roofed: false, minute: 14 * 60 },
    sets: {}, set: null, groundRec: null, groundNode: null,
    method: null, tools: {}, tool: null, leaving: null, swap: null,
    work: null, workRoot: null, workFit: null, workGone: false, arcs: [],
    heatT: 20, heatShown: 20, hearthK: 0.55, hearthT: 0.55,
    sp: null, game: null, gameOn: false, gameLast: 0, flick: 1, emberAt: 0,
    particles: null, tweens: [], reduced: false,
    flare: 0, glint: 0, nudge: 0, nudgeAt: 0, dim: 1, punch: 0, reveal: 1,
    cssW: 1, cssH: 1, cam: null, frame: null,
    stats: { frames: 0, draws: 0, lastDraws: 0, ms: [], rafs: 0, key: [0, 0, 0], glow: [0, 0, 0] }
  };

  function now() { return (window.performance && performance.now) ? performance.now() : Date.now(); }
  function sound(name) {
    try { if (window.Sound && typeof window.Sound.play === "function") window.Sound.play(name); } catch (e) { /* silent */ }
  }
  function warn(where, e) {
    if (window.console && console.warn) console.warn("ForgeStage." + where + ":", e && e.message ? e.message : e);
  }
  /* Every public method goes through this: a stage bug must never break the bench. */
  function safe(where, fn, fallback) {
    return function () {
      try { return fn.apply(null, arguments); } catch (e) { warn(where, e); return fallback; }
    };
  }
  function num(x, d) { x = +x; return isFinite(x) ? x : d; }
  function clamp01(x) { x = +x; return isFinite(x) ? Math.max(0, Math.min(1, x)) : 0; }

  /* Eased values: a pose is a target and each value closes a fixed fraction of its gap per
     second, so motion is smooth at any update rate and, more to the point, it ENDS. */
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
      if (Math.abs(d) > 1e-4) { this.v[k] += d * (1 - Math.exp(-dt * (this.r[k] || 10))); moving = true; }
      else this.v[k] = this.t[k];
    }
    return moving;
  };

  /* --- the frame loop ------------------------------------------------------------------ */

  // FORGE-STAGE-RAF: the only requestAnimationFrame in the stage. It is reached from wake()
  // and nowhere else, and wake() is only called when something changed.
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

  /* Tweens run on the wall clock, so a tween started in a background tab is simply over when
     the tab comes back. */
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
    if (S.sp.step(dt)) busy = true;
    // The heat shown catches up with the heat given in about a fifth of a second, then rests.
    var dh = S.heatT - S.heatShown;
    if (Math.abs(dh) > 0.5) { S.heatShown += dh * (1 - Math.exp(-dt * 14)); busy = true; } else S.heatShown = S.heatT;
    var dk = S.hearthT - S.hearthK;
    if (Math.abs(dk) > 0.002) { S.hearthK += dk * (1 - Math.exp(-dt * 6)); busy = true; } else S.hearthK = S.hearthT;
    var live = isLive(t);
    if (live) {
      busy = true;
      liveStep(dt, t / 1000);
    } else {
      S.flick = 1;
    }
    if (S.particles.alive()) { S.particles.step(dt, t / 1000); busy = true; }
    else S.particles.counts[0] = S.particles.counts[1] = 0;
    if (S.flare > 0.005) { S.flare *= Math.exp(-dt * 11); busy = true; } else S.flare = 0;
    if (S.punch > 0.005) { S.punch *= Math.exp(-dt * 18); busy = true; } else S.punch = 0;
    if (S.nudge > 0) { if ((t - S.nudgeAt) / 60 >= 1) S.nudge = 0; else busy = true; }
    applyPose();
    return busy;
  }

  /* While a game is live: the hearth breathes, embers rise, the bath answers the metal, the
     wheel turns. None of it runs when the game stops sending states. */
  function liveStep(dt, ts) {
    var set = S.set, g = S.game || {};
    if (!S.reduced) {
      // A slow, low wobble: two incommensurate sines, never a strobe (UI plan §6.3).
      S.flick = 1 + 0.07 * Math.sin(ts * 7.3) + 0.05 * Math.sin(ts * 12.9 + 1.7) + 0.03 * Math.sin(ts * 23.1);
      if (ts - S.emberAt > 0.12) {
        S.emberAt = ts;
        F.fx.embers(FX.emit, set.firePos, S.hearthK);
      }
    } else S.flick = 1;
    var st = g.state || {};
    // On a cadence, not per frame: emitted every frame, the steam at 60 frames a second piled
    // into a flat white blob over the bucket in the harness.
    if (S.method === "quench" && st.plunged && set.props.quench && ts - (S.bathAt || 0) > 0.09) {
      S.bathAt = ts;
      var phase = F.heat.quenchPhase(S.heatShown, st.bath || "water");
      var surf = set.quenchSurface;
      F.fx.bubble(FX.emit, surf, set.props.quench.obj.r * 0.5, phase);
      if (phase === "boil" || phase === "jacket") F.fx.steam(FX.emit, [surf[0], surf[1] + 0.03, surf[2]], phase === "boil" ? 0.5 : 0.15);
    }
    if (S.method === "hone" && set.props.wheel) {
      S.wheelA = (S.wheelA || 0) + dt * (2 + 6 * clamp01(st.pass));
      set.props.wheel.obj.spin(S.wheelA);
    }
  }

  /* --- the scene: kit or smithy ---------------------------------------------------------- */

  /* Where everything stands. Two layouts, one composition (UI plan §6.3): the anvil at the
     centre, the hearth to its left, the quench and the rack to its right. */
  function buildSet(smithy) {
    var P = F.props, root = P.group(), props = {};
    function place(name, obj, pos, ry) {
      var n = obj.root || obj;
      n.pos = pos; n.rot = [0, ry || 0, 0];
      P.add(root, n);
      props[name] = { obj: obj, node: n, pos: pos };
      return obj;
    }
    var anvil = place("anvil", smithy ? P.smithyAnvil() : P.campAnvil(), [0, 0, 0]);
    // The smithy is drawn in close: with the furnace against a wall at -1.75 the first harness
    // capture framed the anvil and lost the furnace above the top of the stage entirely.
    var hearth = smithy ? place("hearth", P.furnaceMouth(), [-1.3, 0, -0.95], 0.25)
                        : place("hearth", P.fieldHearth(), [-1.25, 0, -0.15]);
    // Turned so the nozzle (the bellows' own -x) points at the fire.
    place("bellows", P.bellows(!smithy), smithy ? [-2.15, 0, -0.45] : [-1.85, 0, 0.25], 3.73);
    var quench = smithy ? place("quench", P.quenchTrough(), [1.35, 0, -0.1], -0.1)
                        : place("quench", P.quenchBucket(), [1.05, 0, 0.12]);
    place("wheel", P.whetWheel(!smithy), smithy ? [1.45, 0, -0.95] : [1.3, 0, -0.62], smithy ? -0.3 : 0);
    place("rack", P.toolRack(!smithy), smithy ? [0.35, 0, -1.3] : [0.55, 0, -0.62]);
    var cru = place("crucible", P.crucible(), smithy ? [-0.85, 0, -0.55] : [-0.75, 0, 0.42]);
    var tg = P.tongs();
    tg.pos = smithy ? [-0.62, 0.01, -0.42] : [-0.52, 0.01, 0.5];
    tg.rot = [0, 0.7, 0];
    P.add(root, tg);
    if (smithy) {
      place("stock", P.barStock(), [0.85, 0, 0.6], 0.3);
      place("lamp", P.lamp(), [0.7, 1.95, -0.6]);
    }
    var fireL = M.xform(M.compose(props.hearth.pos, props.hearth.node.rot, [1, 1, 1]), hearth.fire);
    fireL = [fireL[0], fireL[1], fireL[2]];
    var surf = M.add(props.quench.pos, quench.surface);
    var wheelP = props.wheel.pos, edge = props.wheel.obj.edge;
    return {
      smithy: smithy, root: root, props: props, anvil: anvil, hearth: hearth, crucible: cru,
      face: anvil.face, firePos: fireL, quenchSurface: surf,
      wheelEdge: [wheelP[0] + edge[0], wheelP[1] + edge[1], wheelP[2] + edge[2]],
      room: null, fits: {}
    };
  }

  function setFor(kind) {
    var smithy = kind === "town" || kind === "owned";
    var k = smithy ? "smithy" : "kit";
    if (!S.sets[k]) S.sets[k] = buildSet(smithy);
    var set = S.sets[k];
    if (smithy) {
      if (!set.rooms) set.rooms = {};
      if (!set.rooms[kind]) set.rooms[kind] = F.smithy.room(kind);
      set.room = set.rooms[kind];
    }
    return set;
  }

  function applyScene() {
    var old = S.set;
    S.set = setFor(S.scene.kind);
    if (!S.set.smithy) {
      var gk = K.ground.kindFor(S.scene), rec = K.ground.paint(gk);
      if (S.groundRec && S.groundRec !== rec && S.r) S.r.forgetTexture(S.groundRec);
      S.groundRec = rec;
      var k = 1 / rec.look.tile;
      var mt = F.props.mat("wood", { color: [1, 1, 1], pattern: 0, tex: rec, uvScale: [k, k], ground: 1,
                                     spec: rec.look.spec, shin: rec.look.shin });
      if (!S.groundNode) S.groundNode = F.props.node(K.mesh.plane(40), mt, { glint: false });
      S.groundNode.mat = mt;
    }
    if (old !== S.set) {
      // The hand tool is re-seated by applyPose at the new set's rest spot; the work is rebuilt
      // because the longest thing an anvil can frame differs between the camp and the smithy.
      buildWork(null);
      layoutWork(true);
      setFrame(true);
    }
    wake();
  }

  /* --- light, by the scene clock ----------------------------------------------------------
     Outdoors the fill is the sky (the herb stage's day, dusk and moon); in a smithy or under a
     roof it is the hanging lamp, warm and from above, with a little cool daylight from the
     door by day. The key is always the fire. */
  var LIGHT = M ? M.norm([-0.42, 0.78, 0.47]) : [0, 1, 0];
  function bell(x, c, w) { var d = (x - c) / w; return Math.exp(-d * d); }
  function lights() {
    var g = S.scene, h = ((((+g.minute || 0) % 1440) + 1440) % 1440) / 60;
    var day = M.smooth(5.5, 7.5, h) * (1 - M.smooth(17.5, 19.5, h));
    var dusk = Math.max(bell(h, 6.5, 1.1), bell(h, 18.6, 1.1));
    var L = {}, fire = S.hearthK * S.flick;
    if (S.set.smithy || g.roofed) {
      L.amb = M.lerp3([0.05, 0.045, 0.04], [0.1, 0.095, 0.09], day);
      L.fillDir = M.norm([0.35, 0.9, 0.3]);
      L.fillCol = M.add([0.36, 0.27, 0.17], M.scale([0.16, 0.18, 0.22], day));
      L.keyCol = M.scale([1.55, 0.78, 0.32], 0.35 + 1.05 * fire);
    } else {
      L.amb = M.add(M.lerp3([0.045, 0.05, 0.075], [0.4, 0.41, 0.44], day), [0.07 * dusk, 0.035 * dusk, 0.015 * dusk]);
      L.fillDir = LIGHT;
      var moon = (1 - day) * (1 - dusk);
      L.fillCol = M.add(M.add(M.scale([0.9, 0.9, 0.95], 0.95 * day), M.scale([0.7, 0.42, 0.24], 0.6 * dusk)),
                        M.scale([0.24, 0.31, 0.52], 0.4 * moon));
      var kk = (0.3 + 1.2 * (1 - day)) * (0.4 + 0.9 * fire);
      L.keyCol = [1.05 * kk, 0.58 * kk, 0.26 * kk];
    }
    L.keyPos = [S.set.firePos[0] + 0.25, S.set.firePos[1] + 0.35, S.set.firePos[2] + 0.35];
    return L;
  }

  /* --- the work ---------------------------------------------------------------------------- */

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
  // sRGB swatch to the linear-ish base the house shader lights (it does no gamma).
  function toBase(c) { return [Math.pow(c[0], 1.6), Math.pow(c[1], 1.6), Math.pow(c[2], 1.6)]; }

  var NON_METAL = /wood|haft|ash\b|oak|hickory|yew|bamboo|leather|cord|bone|horn|cloth|linen|padd|felt|hide|rope|ivory|darkwood|ironwood/;
  function isMetal(piece, slot) {
    var id = String((piece && piece.material) || "").toLowerCase();
    if (id) return !NON_METAL.test(id);
    return slot !== "haft" && slot !== "lining";
  }
  var DEFAULT = { metal: [0.55, 0.55, 0.57], wood: [0.42, 0.27, 0.15], grip: [0.25, 0.15, 0.08] };

  /* The surface of one piece (UI plan §7.3): base colour from the material, finish from the
     quality (rough at Crude, mirror at Flawless), hammer-scale on unhoned work, banding on
     folded or pattern steel. The house shader carries one pattern per surface, so the order
     is: unhoned (scale hides everything) > folded (the banding is the point) > finish. */
  function pieceMat(piece, slot, fam) {
    var P = F.props, metal = isMetal(piece, slot);
    var sw = parseColor(piece && piece.color, null);
    var base = sw ? toBase(sw) : (metal ? DEFAULT.metal : (fam === "grip" ? DEFAULT.grip : DEFAULT.wood));
    var w = S.work || {}, q = Math.max(0, Math.min(1.25, num(w.quality_index, 1) / 4));
    if (!metal) {
      var wm = P.mat(fam === "grip" ? "leather" : "wood", { color: base });
      wm.metal_ = false;
      return wm;
    }
    var honed = w.honed !== undefined ? !!w.honed : !(S.method in HEAD_ONLY) || S.method === "hone";
    var o = { color: base.slice(), spec: 0.45 + 0.75 * q, shin: 18 + 60 * q, metal: 0.75, emit: [0, 0, 0] };
    if (!honed) { o.pattern = 5; o.color = M.scale(base, 0.62); o.spec = 0.35; o.shin = 16; }
    else if (piece && (piece.folded || piece.pattern)) { o.pattern = 1; o.patScale = 2.2 + 0.6 * num(piece.passes, 0); }
    else { o.pattern = 4; o.bump = Math.max(0, 0.9 - 0.9 * q); o.patScale = 2.5; }
    var m = P.mat("steel", o);
    m.metal_ = true;
    m.base_ = o.color.slice();
    return m;
  }

  function slotsOf(w) { return SLOTS[w.gear] || (w.gear ? SLOTS.weapon : ["head"]); }

  /* Builds the work from its pieces: one node per piece, one child per run of the head (for
     the temper colour run and the heat along the blade). */
  function buildWork(prev) {
    var w = S.work, P = F.props;
    S.workRoot = null; S.workFit = null;
    if (!w) return;
    var plan = F.families.planFor(w.gear || "", w.base || "");
    var pieces = w.pieces || {}, root = P.group(), any = false, slots = slotsOf(w);
    var mainSlot = slots[0];
    root.pieces = {};
    slots.forEach(function (slot, i) {
      var pc = plan[slot === "body" ? "body" : slot] || (i === 0 ? plan.head || plan.body : null);
      if (!pc) return;
      var piece = pieces[slot];
      // No gear: a bar of the head's metal stands in for what Forge has not yet shaped.
      if (!piece && !(i === 0 && !w.gear && (pieces.head || w.hot_c))) return;
      if (S.method in HEAD_ONLY && i > 0) return;
      var built = F.families.build(pc.fam, pc.p);
      var g = P.group({ pos: pc.at || [0, 0, 0], rot: pc.rot || [0, 0, 0] });
      g.slot = slot; g.segs = [];
      built.meshes.forEach(function (mesh) {
        var m = pieceMat(piece, slot, pc.fam);
        g.segs.push(P.add(g, P.node(mesh, m)));
      });
      g.metal = g.segs.length && g.segs[0].mat.metal_;
      g.main = slot === mainSlot;
      root.pieces[slot] = P.add(root, g);
      any = true;
    });
    if (!any) return;
    // Lay it on the anvil: its own centre over the anvil's, its underside on the face, and
    // scaled so the longest thing on the anvil is no longer than the stage can frame (a
    // longspear is 1.9 m; at true size it would push the hearth off the stage).
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
    var span = Math.max(hi[0] - lo[0], hi[2] - lo[2]), maxLen = S.set && S.set.smithy ? 1.2 : 1.0;
    var s = span > maxLen ? maxLen / span : 1;
    var inner = P.group({ pos: [-(lo[0] + hi[0]) / 2 * s, -lo[1] * s, -(lo[2] + hi[2]) / 2 * s], scl: [s, s, s] });
    inner.kids = root.kids;
    inner.pieces = root.pieces;
    var outer = P.group();
    outer.kids = [inner];
    outer.inner = inner;
    outer.pieces = root.pieces;
    outer.size = [(hi[0] - lo[0]) * s, (hi[1] - lo[1]) * s, (hi[2] - lo[2]) * s];
    S.workRoot = outer;
    // Pieces dropped in since the last build arc onto the anvil and seat (UI plan §10).
    if (prev && S.mounted && !S.reduced) {
      Object.keys(outer.pieces).forEach(function (slot) {
        if (prev.pieces && prev.pieces[slot]) return;
        arcIn(outer.pieces[slot], slot);
      });
    }
    paintWork();
  }

  function arcIn(g, slot) {
    var home = g.pos.slice();
    var piece = (S.work.pieces || {})[slot] || {};
    sound("forge.drop." + (piece.form || slot));
    tween(320, function (q) {
      var e = q < 0.7 ? 1 - Math.pow(q / 0.7, 2) : Math.sin((q - 0.7) / 0.3 * Math.PI) * 0.06;
      g.pos = [home[0] + 0.5 * e, home[1] + 0.5 * e, home[2] + 0.25 * e];
      g.alpha = Math.min(1, q * 4);
    }, function () {
      g.pos = home; g.alpha = 1;
      FX.emit("dust", workPoint(), { count: 2, size: 0.4 });
    });
  }

  /* Heat, temper and finish onto the work's materials. Cheap: a few dozen vectors. */
  function paintWork() {
    var root = S.workRoot;
    if (!root) return;
    var st = (S.game && S.game.state) || {}, c = S.heatShown;
    Object.keys(root.pieces).forEach(function (slot) {
      var g = root.pieces[slot];
      if (!g.metal) return;
      var n = g.segs.length;
      var heats = g.main ? F.fx.heatRun(c, n) : F.fx.heatRun(c - 60, n);
      var temper = S.method === "temper" && st.temper_c !== undefined && g.main
        ? F.fx.temperRun(num(st.temper_c, 20), n, g.segs[0].mat.base_) : null;
      var cov = S.method === "finish" ? clamp01(st.coverage) : 0;
      g.segs.forEach(function (seg, i) {
        var m = seg.mat, base = m.base_ || m.color;
        var col = temper ? temper[i] : base;
        if (cov) col = M.lerp3(col, [0.06, 0.07, 0.11], cov * 0.85);
        m.color = col;
        m.emit = F.heat.emit(heats[i]);
      });
    });
  }

  /* Where the work stands for the method: on the anvil, over or under the quench, at the
     wheel, or (Smelt, Alloy) put away while the bloom and the crucible take the stage. */
  function workSpot() {
    var set = S.set, st = (S.game && S.game.state) || {};
    var face = set.face;
    if (S.method === "quench" && S.game && S.game.on) {
      var q = set.quenchSurface;
      return st.plunged ? [q[0], q[1] - 0.06, q[2]] : [q[0], q[1] + 0.22, q[2]];
    }
    if (S.method === "hone") {
      var e = set.wheelEdge;
      return set.smithy ? [e[0] - 0.05, e[1] - 0.04, e[2] + 0.22] : [e[0], e[1] + 0.005, e[2]];
    }
    return [0, face, 0];
  }

  function layoutWork(snap) {
    if (!S.set) return;
    var p = workSpot();
    var away = S.method === "smelt" || S.method === "alloy";
    if (snap) { S.sp.snap("wx", p[0]); S.sp.snap("wy", p[1]); S.sp.snap("wz", p[2]); S.sp.snap("wa", away ? 0 : 1); }
    else { S.sp.set("wx", p[0], 7); S.sp.set("wy", p[1], 7); S.sp.set("wz", p[2], 7); S.sp.set("wa", away ? 0 : 1, 8); }
    wake();
  }

  function workPoint() {
    var R = S.workRoot;
    var p = [S.sp.get("wx") || 0, S.sp.get("wy") || 0, S.sp.get("wz") || 0];
    if (!R) return [p[0], p[1] + 0.03, p[2]];
    return [p[0], p[1] + R.size[1] + 0.01, p[2]];
  }

  /* --- hand tools ---------------------------------------------------------------------------- */
  function toolNode(name) {
    if (!S.tools[name]) S.tools[name] = F.props.HAND_BUILD[name]();
    return S.tools[name];
  }
  function toolRest(name) {
    // At rest beside the anvil on the right, on the ground: in reach, never over the work.
    var set = S.set, small = !set.smithy;
    return { pos: [small ? 0.36 : 0.42, 0.025, small ? 0.3 : 0.32], rot: [0, -0.5, 0] };
  }

  function setTool(method) {
    return new Promise(function (resolve) {
      if (METHODS.indexOf(method) < 0) { resolve(false); return; }
      finishSwap();
      var prevMethod = S.method;
      S.method = method;
      var name = F.props.HAND[method], T = toolNode(name), old = S.tool;
      var rest = toolRest(name);
      buildWork(null);
      layoutWork(!S.mounted);
      setFrame(!S.mounted || prevMethod === null);
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
      if (S.reduced) {
        // Reduced motion: a 120ms crossfade, nothing falls (UI plan §10).
        total = 120;
        T.pos = rest.pos.slice(); T.rot = rest.rot.slice();
        sw.tweens.push(tween(120, function (p) {
          T.alpha = p; T.scl = [1, 1, 1];
          if (old) old.alpha = 1 - p;
        }));
      } else {
        var lead = old ? 180 : 0;
        total = lead + 450;
        if (old) {
          var o0 = old.pos.slice();
          sw.tweens.push(tween(180, function (p) {
            var e = M.ease.inQuad(p);
            old.pos = [o0[0], o0[1] + 0.5 * e, o0[2]]; old.alpha = 1 - p;
          }));
        }
        T.alpha = 0; T.rot = rest.rot.slice();
        var landed = false;
        // The new tool drops after the old one has gone: 450ms of fall, contact, and a 4%
        // squash that overshoots and settles.
        sw.tweens.push(tween(total, function (p) {
          var q = (p * total - lead) / 450;
          if (q < 0) { T.alpha = 0; return; }
          if (q < 0.5) {
            var f = q / 0.5;
            T.pos = [rest.pos[0], rest.pos[1] + 0.9 * (1 - f * f), rest.pos[2]];
            T.alpha = Math.min(1, f * 3);
            T.scl = [1, 1 + 0.03 * f, 1];
          } else {
            if (!landed) { landed = true; FX.emit("dust", rest.pos, { count: 5, spread: 0.2, up: 0.2 }); }
            var s = (q - 0.5) / 0.5;
            var sy = 1 - 0.04 * Math.cos(s * Math.PI * 3) * (1 - s) * (1 - s);
            T.pos = rest.pos.slice(); T.alpha = 1;
            T.scl = [1 + (1 - sy) * 0.5, sy, 1 + (1 - sy) * 0.5];
          }
        }));
      }
      sw.tweens[sw.tweens.length - 1].done = function () { if (S.swap === sw) finishSwap(); };
      // A promise that waits on frames would hang in a background tab; this does not.
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

  /* --- poses ------------------------------------------------------------------------------------ */

  /* Everything the springs drive, written onto the nodes once per frame. */
  function applyPose() {
    var set = S.set, sp = S.sp;
    if (!set) return;
    var R = S.workRoot;
    if (R) {
      R.pos = [sp.get("wx"), sp.get("wy"), sp.get("wz")];
      R.alpha = sp.get("wa");
      R.visible = !S.workGone && R.alpha > 0.01;
      R.rot = [0, 0.1, 0];
    }
    paintWork();
    // The hearth's own heat: coals, glow, flame.
    set.hearth.setHeat(S.hearthK * S.flick);
    set.props.bellows.obj.setPump(sp.get("pump") || 0);
    // The bloom (Smelt) and the melt (Alloy) glow by the same table as the work.
    if (set.bloom) {
      set.bloom.visible = S.method === "smelt";
      set.bloom.kids.forEach(function (n) { n.mat.emit = F.heat.emit(S.heatShown); });
    }
    var cm = set.crucible.melt;
    cm.emit = S.method === "alloy" ? F.heat.emit(S.heatShown) : [0, 0, 0];
    cm.color = S.method === "alloy" && S.heatShown > 500 ? [0.3, 0.25, 0.2] : [0.2, 0.2, 0.2];
    set.props.crucible.node.rot = [0, 0, -0.9 * (sp.get("pour") || 0)];
    // The hammer answers the beat ring while a striking game is live.
    var T = S.tool;
    if (T && !S.swap && S.game && S.game.on && S.method in STRIKES && S.tool === S.tools[F.props.HAND[S.method]]) {
      var wp = workPoint();
      T.pos = [wp[0] + 0.02, wp[1] + 0.03 + sp.get("hy"), wp[2] + 0.02];
      T.rot = [0, Math.PI, sp.get("hz")];
    } else if (T && !S.swap) {
      var rest = toolRest();
      T.pos = rest.pos.slice(); T.rot = rest.rot.slice();
    }
  }

  function ensureBloom() {
    var set = S.set;
    if (set.bloom) return;
    var P = F.props, b = F.families.build("hammer", { v: "ball", k: 1.5 });
    var g = P.group({ pos: [set.firePos[0], set.firePos[1] - 0.05, set.firePos[2]] });
    b.meshes.forEach(function (m) { P.add(g, P.node(m, P.mat("iron", { color: [0.2, 0.17, 0.15], pattern: 7, emit: [0, 0, 0] }))); });
    g.visible = false;
    set.bloom = g;
  }

  /* --- camera --------------------------------------------------------------------------------
     About 40 degrees down, looking along the anvil (UI plan §6.3). The field of view is
     SOLVED, as the herb stage's is: the method's subject (the work on the anvil, the furnace
     and bellows for Smelt, the quench for Quench) is fitted from its own vertices to a share
     of the stage's height and width, so the hearth and the quench sit at the edges of the
     frame at every aspect rather than at one aspect only. Between methods the framing eases
     from the old fit to the new while the tools swap. */
  var FRAME = {
    smelt: { props: ["hearth", "bellows"], h: 0.66, w: 0.8 },
    alloy: { props: ["crucible", "hearth"], h: 0.6, w: 0.75 },
    quench: { props: ["quench", "anvil"], h: 0.5, w: 0.75 },
    hone: { props: ["wheel"], h: 0.55, w: 0.6, work: true },
    none: { props: ["anvil", "hearth", "quench"], h: 0.7, w: 0.92 },
    // While a striking game is live the camera pushes in on the anvil: in the establishing
    // frame the anvil stood at about a fifth of the stage height in the harness, too small to
    // read a strike on. The push is the only camera move a game makes, in and back out.
    close: { props: ["anvil"], h: 0.52, w: 0.7, work: true, mirror: true }
  };
  function frameKey() {
    return S.game && S.game.on && (S.method in STRIKES || S.method === "temper" || S.method === "finish") ? "close" : S.method;
  }
  // The anvil and the hearth together: framed on the anvil alone (0.48 of the height) the
  // smithy's furnace fell off the top-left corner in the harness, and the plan's composition
  // is the two of them, the fire to the left of the work.
  // `mirror` reflects the cloud about the anvil, so the fit is symmetric and the anvil stays
  // at the centre with the fire at the left edge (and the quench, which stands about as far to
  // the right, at the right edge). Without it the fit's centre fell between anvil and furnace.
  var DEFAULT_FRAME = { props: ["anvil", "hearth"], h: 0.6, w: 0.92, work: true, mirror: true };

  function cloud(nodes, mirrorX) {
    var items = [];
    nodes.forEach(function (n) { if (n) collect(n, M.ident(), 1, 0, items, true); });
    items = items.filter(function (it) { return !it.n.noFit; });
    var total = 0;
    items.forEach(function (it) { if (solid(it.n.mat)) total += it.n.mesh.pos.length / 3; });
    var every = Math.max(1, Math.floor(total / 900)), pts = [];
    var lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    items.forEach(function (it) {
      if (!solid(it.n.mat)) return;
      var P = it.n.mesh.pos;
      for (var i = 0; i < P.length; i += 3 * every) {
        var w = M.xform(it.m, [P[i], P[i + 1], P[i + 2]]);
        var ws = mirrorX === undefined ? [w] : [w, [2 * mirrorX - w[0], w[1], w[2]]];
        ws.forEach(function (v) {
          pts.push(v[0], v[1], v[2]);
          for (var k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], v[k]); hi[k] = Math.max(hi[k], v[k]); }
        });
      }
    });
    if (!pts.length) return null;
    return { pts: new Float32Array(pts), centre: [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2] };
  }
  function solid(m) { return m && m.pass !== "add" && !m.radial && m.pass !== "alpha"; }

  function fitFor(method) {
    var set = S.set, f = FRAME[method || "none"] || DEFAULT_FRAME;
    var key = (method || "none") + (f.work && S.workRoot ? ":" + S.workRoot.size.join(",") : "");
    if (set.fits[key]) return set.fits[key];
    var nodes = f.props.map(function (p) { return set.props[p] && set.props[p].node; });
    if (f.work && S.workRoot) {
      // The work where it will rest, not where it is mid-flight.
      var spot = workSpot(), R = S.workRoot, saved = [R.pos, R.alpha, R.visible];
      R.pos = spot; R.alpha = 1; R.visible = true;
      var mx = f.mirror ? spot[0] : undefined;
      var fit = cloud(nodes.concat([R]), mx);
      R.pos = saved[0]; R.alpha = saved[1]; R.visible = saved[2];
      fit = fit || cloud(nodes, mx);
      fit.h = f.h; fit.w = f.w;
      set.fits[key] = fit;
      return fit;
    }
    var c = cloud(nodes, f.mirror ? 0 : undefined) || { pts: new Float32Array([0, 0, 0, 0, 1, 0]), centre: [0, 0.5, 0] };
    c.h = f.h; c.w = f.w;
    set.fits[key] = c;
    return c;
  }

  function setFrame(snap) {
    if (!S.set) return;
    var to = fitFor(frameKey());
    if (snap || !S.frame || !S.mounted || S.reduced) { S.frame = { from: null, to: to, k: 1 }; wake(); return; }
    if (S.frame.to === to) return;
    var from = S.frame.to, fr = { from: from, to: to, k: 0 };
    S.frame = fr;
    tween(450, function (p) { fr.k = M.ease.inOutSine(p); });
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
    var pitch = 40 * D2R + S.nudge * Math.max(0, 1 - (now() - S.nudgeAt) / 60) * D2R;
    var fr = S.frame || { from: null, to: fitFor(frameKey()), k: 1 };
    var to = fr.to, from = fr.from || to, k = fr.k;
    var target = M.lerp3(from.centre, to.centre, k), dist = 4.6;
    var eye = [target[0], target[1] + Math.sin(pitch) * dist, target[2] + Math.cos(pitch) * dist];
    var view = M.lookAt(eye, target, [0, 1, 0]);
    var e = extent(to.pts, view), h = to.h, w = to.w;
    if (from !== to && k < 1) {
      var eA = extent(from.pts, view);
      e = [M.lerp(eA[0], e[0], k), M.lerp(eA[1], e[1], k), M.lerp(eA[2], e[2], k), M.lerp(eA[3], e[3], k)];
      h = M.lerp(from.h, to.h, k); w = M.lerp(from.w, to.w, k);
    }
    var Tw = e[2] - e[0], Th = e[3] - e[1];
    var tH = Th / (2 * h), tW = Tw / (2 * w * aspect), tMax = Th / (2 * Math.min(h, 0.32));
    var t = Math.min(Math.max(tH, tW), Math.max(tMax, tH));
    var proj = M.perspective(2 * Math.atan(t), aspect, 0.1, 60);
    // Lens shift: the subject sits a little above the middle, leaving the lower part of the
    // stage for the info line and the rising minigame strip (as the herb stage does).
    var cy = (e[3] + e[1]) / 2, cx = (e[2] + e[0]) / 2;
    proj[9] = cy / t - 0.12;
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
      if (S.reduced || !S.mounted) return;
      S.particles.emit(kind, [pos[0], pos[1], pos[2]], opts);
      wake();
    }
  };

  function draw() {
    var r = S.r;
    if (!r || !r.gl || S.lost || !S.set) return;
    var cam = camera(), L = lights(), set = S.set;
    var wp = workPoint();
    var glowCol = [0, 0, 0], glowPos = [0, -10, 0];
    var c = S.heatShown;
    if (S.method === "smelt" && set.bloom) glowPos = set.bloom.pos;
    else if (S.method === "alloy") glowPos = M.add(set.props.crucible.pos, [0, 0.3, 0]);
    else if (S.workRoot && S.workRoot.visible) glowPos = [wp[0], wp[1] + 0.1, wp[2] + 0.05];
    // At 0.85 a cherry blank left the anvil under it dark in the harness; 1.5 lets the heat
    // read on the iron and the stump while still falling off within half a metre.
    // Capped at 1.8 on its brightest channel: uncapped, yellow heat (2.5) burned a light wooden
    // stump top to flat white.
    if (glowPos[1] > -5) {
      glowCol = M.scale(F.heat.light(c), 1.5);
      var gm = Math.max(glowCol[0], glowCol[1], glowCol[2]);
      if (gm > 1.8) glowCol = M.scale(glowCol, 1.8 / gm);
    }
    var fk = S.flare * 2.6;
    var fc = c > 700 ? F.fx.heatCol(c) : CANDLE;
    r.begin({
      vp: cam.vp, view: cam.view, proj: cam.proj, eye: cam.eye, amb: L.amb, keyPos: L.keyPos, keyCol: L.keyCol,
      fillDir: L.fillDir, fillCol: L.fillCol, glowPos: glowPos, glowCol: glowCol,
      flarePos: [wp[0], wp[1] + 0.25, wp[2] + 0.2], flareCol: [fc[0] * fk, fc[1] * fk, fc[2] * fk],
      exposure: S.dim, reveal: S.reveal, bg: BG, fade: [4.6, 10.5],
      px: r.canvas.height / (2 * cam.t)
    });
    S.stats.key = L.keyCol.slice();
    S.stats.glow = glowCol.slice();

    var items = [], I = M.ident();
    if (set.smithy && set.room) collect(set.room, I, 1, 0, items);
    else if (S.groundNode) collect(S.groundNode, I, 1, 0, items);
    collect(set.root, I, 1, 0, items);
    if (set.bloom) collect(set.bloom, I, 1, 0, items);
    if (S.leaving) collect(S.leaving, I, 1, 0, items);
    if (S.tool) collect(S.tool, I, 1, 0, items);
    if (S.workRoot) {
      // A hit punches the work: a 3.5% squash that springs back inside a tenth of a second.
      var pk = S.punch;
      collect(S.workRoot, pk ? M.compose([0, 0, 0], [0, 0, 0], [1 + 0.02 * pk, 1 - 0.035 * pk, 1 + 0.02 * pk]) : I,
              1, S.glint, items);
    }

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
    function issue(list) { list.forEach(function (it) { r.draw(it.n.mesh, it.m, it.n.mat, it.a, it.glint, null); }); }
    r.setBlend("opaque"); issue(opaque);
    r.setBlend("fade"); issue(fade);
    r.setBlend("alpha"); issue(alpha);
    r.setBlend("add"); issue(add);
    r.points(S.particles.out[0], S.particles.counts[0], false);
    r.points(S.particles.out[1], S.particles.counts[1], true);
    S.stats.lastDraws = r.draws;
    S.stats.draws += r.draws;
  }

  /* --- size ----------------------------------------------------------------------------------
     Device-pixel aware, capped at 2, and again at 4K worth of pixels (the herb stage's
     measurement: 3440x1440 at a ratio of 2 is five times 1080p's fill). */
  function resize() {
    if (!S.canvas || !S.host) return;
    var w = Math.max(1, S.host.clientWidth), h = Math.max(1, S.host.clientHeight);
    var dpr = Math.min(2, window.devicePixelRatio || 1);
    if (w * h * dpr * dpr > MAX_PIXELS) dpr = Math.max(1, Math.sqrt(MAX_PIXELS / (w * h)));
    S.cssW = w; S.cssH = h;
    if (S.r) S.r.resize(Math.round(w * dpr), Math.round(h * dpr));
    wake();
  }

  /* --- the game ------------------------------------------------------------------------------- */
  function pieceIndex(i) { return typeof i === "number" && isFinite(i) && i >= 0 ? Math.floor(i) : null; }

  function game(method) {
    var g = { method: method, on: false, state: {} };
    function mine() { return S.method === method && S.game === g; }
    function begin() {
      if (S.game !== g) { S.game = g; }
      if (!g.on) {
        g.on = true; S.gameOn = true;
        S.sp.snap("hy", 0.25); S.sp.snap("hz", 0.3);
        if (method === "smelt") ensureBloom();
        layoutWork(false);
        setFrame(false);
      }
    }
    var view = {
      update: safe("game.update", function (st) {
        if (!st || typeof st !== "object") return;
        begin();
        g.state = st;
        S.gameLast = now();
        if (st.heat_c !== undefined) S.heatT = num(st.heat_c, S.heatT);
        if (method === "smelt") {
          S.sp.set("pump", clamp01(st.pump), 16);
          S.hearthT = 0.55 + 0.65 * clamp01(st.pump);
          if (st.tap && !g.tapped) { F.fx.slag(FX.emit, S.set.firePos); }
          g.tapped = !!st.tap;
        } else S.hearthT = 0.7;
        if (method === "alloy") S.sp.set("pour", clamp01(st.pour), 8);
        if (method in STRIKES) {
          if (st.struck) { S.sp.set("hy", 0.0, 45); S.sp.set("hz", 0, 30); }
          else { S.sp.set("hy", 0.06 + 0.32 * Math.sin(clamp01(st.ring) * Math.PI / 2), 14); S.sp.set("hz", 0.25, 12); }
        }
        if (method === "quench") layoutWork(false);
        if (mine()) wake();
      }),
      // `index` names the piece the hit belongs to (a rivet at Assemble); the stage strikes
      // at the work's centre without one.
      hit: safe("game.hit", function (strength, index) {
        if (!mine()) return;
        var s = clamp01(strength), p = workPoint();
        void pieceIndex(index);
        if (method in STRIKES) {
          S.sp.set("hy", 0.0, 60);
          F.fx.strike(FX.emit, p, s * (method === "assemble" ? 0.4 : 1), S.heatShown);
        } else if (method === "hone") {
          F.fx.grind(FX.emit, S.set.wheelEdge, [0.2, 0.5, 0.9]);
        } else if (method === "smelt") {
          F.fx.slag(FX.emit, S.set.firePos);
        } else if (method === "quench") {
          FX.emit("splash", S.set.quenchSurface, { count: 10, col: [0.5, 0.55, 0.55], speed: 0.8 });
        } else {
          FX.emit("glint", p, { count: 2 });
        }
        S.flare = Math.max(S.flare, 0.4 + 0.7 * s);
        if (!S.reduced && method in STRIKES) {
          S.nudge = 1.5; S.nudgeAt = now();
          S.punch = Math.max(S.punch, 0.6 + 0.4 * s);
        }
        wake();
      }),
      // A miss: a dull thud, no sparks (UI plan §10, "out of band").
      miss: safe("game.miss", function (index) {
        if (!mine()) return;
        void pieceIndex(index);
        if (method in STRIKES) { S.sp.set("hy", 0.02, 40); FX.emit("grit", workPoint(), { count: 3, col: [0.3, 0.28, 0.26], speed: 0.5 }); }
        wake();
      }),
      end: safe("game.end", function () {
        g.on = false;
        if (S.game === g) { S.gameOn = false; S.hearthT = 0.55; S.sp.set("pump", 0, 8); S.sp.set("pour", 0, 8); }
        layoutWork(false);
        setFrame(false);
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
      var p = workPoint(), top = [p[0], p[1] + 0.2, p[2]];
      if (kind === "tierUp") {
        sound("forge.tier.up");
        F.fx.gilt(FX.emit, top, 14);
        S.flare = Math.max(S.flare, 0.9);
        tween(380, function (q) { S.glint = Math.sin(Math.PI * q) * 0.9; }, function () { S.glint = 0; resolve(true); });
      } else if (kind === "flawless") {
        sound("forge.flawless");
        F.fx.gilt(FX.emit, top, 90);
        FX.emit("spark", top, { count: 24 });
        S.flare = Math.max(S.flare, 1.8);
        var cv = S.canvas, shook = !S.reduced;
        tween(700, function (q) { S.glint = Math.sin(Math.PI * q) * 1.2; }, function () { S.glint = 0; resolve(true); });
        if (shook) {
          // The STAGE canvas shakes, never the page: a transform on this one element.
          tween(250, function (q) {
            var a = 7 * (1 - q) * (1 - q);
            cv.style.transform = q >= 1 ? "" :
              "translate(" + (Math.sin(q * 71) * a).toFixed(2) + "px," + (Math.cos(q * 53) * a).toFixed(2) + "px)";
          }, function () { cv.style.transform = ""; });
        }
      } else if (kind === "fail") {
        // The work cracks or dulls: smoke, a shudder, and the stage dims 30% for 600ms.
        sound("forge.fail");
        FX.emit("smoke", top, { count: 6, spread: 0.2 });
        var R = S.workRoot;
        tween(600, function (q) {
          S.dim = q < 0.12 ? 1 - 0.3 * (q / 0.12) : (q < 0.55 ? 0.7 : 0.7 + 0.3 * M.ease.inOutSine((q - 0.55) / 0.45));
          if (R && !S.reduced) R.inner.rot = [0, 0, q < 0.6 ? Math.sin(q * 60) * 0.03 * (1 - q / 0.6) : 0];
        }, function () { S.dim = 1; if (R) R.inner.rot = [0, 0, 0]; resolve(true); });
      } else if (kind === "quench") {
        // The plume, the hiss (U6's), and the glow dies.
        sound("forge.quench");
        var from = S.heatT;
        F.fx.steam(FX.emit, [S.set.quenchSurface[0], S.set.quenchSurface[1] + 0.05, S.set.quenchSurface[2]], 1.4);
        tween(900, function (q) { S.heatT = from + (60 - from) * M.ease.outCubic(q); S.heatShown = S.heatT; },
              function () { resolve(true); });
      } else if (kind === "land") {
        sound("forge.land");
        land(resolve);
      } else {
        resolve(false);
      }
      wake();
    });
  }

  /* The product lifts from the anvil, turns, and is gone (UI plan §10): U2 flies its own copy
     from productRect() to the rack row. Reduced motion: no rise; it is there, then not. */
  function land(resolve) {
    var R = S.workRoot;
    if (!R) { resolve(false); return; }
    var base = [S.sp.get("wx"), S.sp.get("wy"), S.sp.get("wz")];
    S.workGone = false;
    if (S.reduced) {
      tween(1000, function (q) { S.glint = q < 0.5 ? 0.4 : 0; },
            function () { S.workGone = true; S.glint = 0; resolve(true); });
      return;
    }
    F.fx.gilt(FX.emit, base, 10);
    var s0 = R.inner.scl.slice();
    tween(1050, function (q) {
      var e = M.ease.outCubic(Math.min(1, q / 0.43));
      S.sp.snap("wy", base[1] + 0.42 * e);
      R.inner.rot = [0, e * Math.PI * 0.6, 0];
      R.inner.scl = M.scale(s0, 0.85 + 0.15 * e);
      S.sp.snap("wa", q > 0.86 ? (1 - q) / 0.14 : 1);
    }, function () {
      S.workGone = true;
      R.inner.rot = [0, 0, 0]; R.inner.scl = s0;
      S.sp.snap("wy", base[1]); S.sp.snap("wa", 1);
      resolve(true);
    });
  }

  /* Where the work is (or would be), in viewport pixels, so U2 can fly its copy to the rack. */
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
    var R = S.workRoot, pts = [];
    if (R) {
      var items = [];
      collect(R, M.ident(), 1, 0, items, true);
      items.forEach(function (it) {
        var bb = it.n.mesh.bounds;
        for (var c = 0; c < 8; c++) pts.push(M.xform(it.m, [c & 1 ? bb.hi[0] : bb.lo[0], c & 2 ? bb.hi[1] : bb.lo[1], c & 4 ? bb.hi[2] : bb.lo[2]]));
      });
    }
    if (!pts.length) pts.push(workPoint());
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
        cv.className = "forge-stage-canvas";
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
        applyScene();
        buildWork(null);
        layoutWork(true);
        setFrame(true);
        if (S.tool) { var rest = toolRest(); S.tool.pos = rest.pos.slice(); S.tool.rot = rest.rot.slice(); S.tool.alpha = 1; S.tool.visible = true; }
        // Open the forge (UI plan §10): the ground fades in from the page's dark and the
        // hearth flares from embers; reduced motion fades only.
        S.reveal = 0;
        tween(S.reduced ? 120 : 320, function (p) { S.reveal = M.ease.outCubic(p); });
        if (!S.reduced) {
          S.hearthK = 0.1;
          tween(700, function (p) { S.hearthK = 0.1 + (S.hearthT - 0.1) * M.ease.outCubic(p); });
        }
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
        var ext = S.r.gl && S.r.gl.getExtension && S.r.gl.getExtension("WEBGL_lose_context");
        // Give the context back now: a page holds only a handful, and the dice want one.
        if (ext) ext.loseContext();
      } catch (e) { /* already gone */ }
    }
    if (S.canvas && S.canvas.parentNode) S.canvas.parentNode.removeChild(S.canvas);
    S.r = null; S.canvas = null; S.host = null; S.mounted = false; S.groundRec = null;
    S.dim = 1; S.glint = 0; S.flare = 0; S.gameOn = false; S.flick = 1;
  }

  function setScene(g) {
    g = g || {};
    var kind = g.kind === "town" || g.kind === "owned" ? g.kind : "kit";
    S.scene = { kind: kind, biome: g.biome || "", roofed: !!g.roofed, minute: num(g.minute, 14 * 60) };
    if (S.mounted) applyScene();
    else S.set = setFor(kind);
  }

  /* The work on the anvil. Rebuilt only when its shape or its pieces change; a heat or quality
     change repaints the materials in place. null clears the anvil. */
  function setWork(w) {
    var prev = S.workRoot;
    var same = w && S.work && w.gear === S.work.gear && JSON.stringify(w.base || "") === JSON.stringify(S.work.base || "");
    S.work = w && typeof w === "object" ? {
      gear: w.gear || "", base: w.base || "", pieces: w.pieces || {}, quality_index: num(w.quality_index, 1),
      hot_c: w.hot_c, honed: w.honed
    } : null;
    S.workGone = false;
    if (S.work && S.work.hot_c !== undefined && S.work.hot_c !== null) {
      S.heatT = num(S.work.hot_c, S.heatT);
      if (!S.mounted) S.heatShown = S.heatT;
    }
    if (!S.set) S.set = setFor(S.scene.kind);
    buildWork(same ? prev : null);
    if (S.set) { S.set.fits = {}; setFrame(!S.mounted); }
    wake();
  }

  function heat(c) {
    S.heatT = Math.max(-50, Math.min(2000, num(c, S.heatT)));
    if (!S.mounted) S.heatShown = S.heatT;
    wake();
  }

  function reducedMotion(on) {
    S.reduced = !!on;
    if (S.reduced && S.particles) S.particles.clear();
    if (S.reduced && S.canvas) S.canvas.style.transform = "";
    if (S.reduced) S.flick = 1;
  }

  /* For the harness and the verification notes. Not part of the contract. */
  function debug() {
    var ms = S.stats.ms.slice().sort(function (a, b) { return a - b; });
    var sum = ms.reduce(function (a, b) { return a + b; }, 0);
    return { frames: S.stats.frames, draws: S.stats.draws, lastDraws: S.stats.lastDraws, rafs: S.stats.rafs, raf: !!S.raf,
             avgMs: ms.length ? sum / ms.length : 0, p95Ms: ms.length ? ms[Math.floor(ms.length * 0.95)] : 0,
             scene: S.scene.kind, smithy: !!(S.set && S.set.smithy), method: S.method,
             pieces: S.workRoot ? Object.keys(S.workRoot.pieces) : [], heat: S.heatShown,
             band: (F.heat.band(S.heatShown) || {}).name || null, key: S.stats.key, glow: S.stats.glow, flick: S.flick,
             particles: S.particles ? S.particles.alive() : 0, tweens: S.tweens.length,
             buffer: S.canvas ? [S.canvas.width, S.canvas.height] : null };
  }
  function resetStats() { S.stats.frames = 0; S.stats.draws = 0; S.stats.ms = []; S.stats.rafs = 0; }

  if (READY) {
    S.particles = new K.Particles();
    S.sp = new Springs();
    S.sp.snap("hy", 0.25); S.sp.snap("hz", 0.3); S.sp.snap("pump", 0); S.sp.snap("pour", 0);
    S.sp.snap("wx", 0); S.sp.snap("wy", 0.5); S.sp.snap("wz", 0); S.sp.snap("wa", 1);
  }

  function noop() {}
  function resolved(v) { return function () { return Promise.resolve(v); }; }
  var NOGAME = { update: noop, hit: noop, miss: noop, end: noop };

  window.ForgeStage = READY ? {
    available: safe("available", available, false),
    mount: function (host) { try { return mount(host); } catch (e) { warn("mount", e); return Promise.resolve(false); } },
    unmount: safe("unmount", unmount),
    setScene: safe("setScene", setScene),
    setTool: function (m) { try { return setTool(m); } catch (e) { warn("setTool", e); return Promise.resolve(false); } },
    setWork: safe("setWork", setWork),
    heat: safe("heat", heat),
    game: function (m) { try { return game(m); } catch (e) { warn("game", e); return NOGAME; } },
    flourish: function (k) { try { return flourish(k); } catch (e) { warn("flourish", e); return Promise.resolve(false); } },
    productRect: safe("productRect", productRect, null),
    reducedMotion: safe("reducedMotion", reducedMotion),
    _debug: safe("_debug", debug, null),
    _resetStats: safe("_resetStats", resetStats)
  } : {
    // The parts did not load: every call is a quiet no-op, and U2 shows its flat stage.
    available: function () { return false; },
    mount: resolved(false), unmount: noop, setScene: noop, setTool: resolved(false),
    setWork: noop, heat: noop,
    game: function () { return NOGAME; }, flourish: resolved(false),
    productRect: function () { return window.DOMRect ? new window.DOMRect(0, 0, 0, 0) : null; },
    reducedMotion: noop,
    _debug: function () { return null; }, _resetStats: noop
  };
})();
