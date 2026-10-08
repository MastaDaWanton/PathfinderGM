// The play table, part 57 (the leather bench's 3D stage). Classic script; everything it defines
// lives inside one IIFE and leaves exactly one global, window.TanneryStage, because the table's
// numbered modules share a single global scope. 57, not the plan's 47: 45-49 are the enchanting
// bench's and 50-54 the alchemy bench's now, and the leather files take the plan's numbers plus
// ten (shell 55, rack 56, stage 57, order 58).
//
// WHAT IT IS. The middle of the leather bench (UI plan §6.3, §7, §10): the hide on the
// fleshing beam or the stretching frame, on the ground you stand on (the field kit) or in a
// tannery yard; its colour and surface from lane E's state (`color`, `surface` on every rack
// row); the vat or the pot it tans in; the kettle and its steam for Harden; the stitching in
// the pony; and the finished piece built from its pieces. Its interface is UI plan §12 and
// contracts §11.1, and lane U1 builds against nothing else:
//
//   available() mount(host) unmount()
//   setScene({kind: "kit" | "town" | "owned", biome, roofed, minute})
//   setTool(method)
//   setWork({product, base, tannage, pieces: {slot: {material, color, surface, grade, passes,
//            defects, form, units, plan, tannage_kind, hardened}}, quality_index})
//   game(method, opts?) flourish(kind) productRect() reducedMotion(bool)
//
// THE WORK. `pieces` is keyed by the bench's slot ids (rules/leatherworker.py METHOD_SLOTS:
// hide, salt, tannin, piece, oil, thread, wax, dye, mordant, body, fastenings, lining), and a
// slot's value is the rack row the player put there, as lane E sends it. The stage READS ONLY
// the keys above, through `clean`, and copies nothing else: a rack row is never stored whole,
// so whatever a row carries that the player has not learned (an ungraded hide's properties)
// could not be drawn by this file if a later change tried. The work is the slot the method
// works (`hide` for Flense, Salt, Tan and Cut; `piece` for the rest; `body` at Assemble); the
// consumables colour what serves it (the tannin the liquor, the dye the pot, the thread the
// stitches, the oil the sheen). `plan` is the harvest tag's body plan (quadruped, long,
// serpent, winged, carapace; quadruped when absent), `units` the hide units, `defects` the
// harvest's holes and scores (a 0..1 area or a list of {u, v, kind}). `product` is the pattern
// id from lane E's products list, which decides the cut piece's outline and the finished
// shape; `tannage` (or the tannin slot's `tannage_kind`) decides vat, pot or frame at Tan.
//
// THE GAME VIEW. game(method) returns {update(state), hit(strength, index), miss(index),
// end(), heat(celsius)}, the shape 33-bench-games.js hands its states to. Every key is
// optional, and the stage shows what it is given (UI plan §9's "on the stage" column):
//   progress 0..1      how far the work has gone: the flesh cleared off the beam (Flense), the
//                      knife along the chalk (Cut), the stitches along the seam (Stitch), the
//                      hide down into the liquor (Tan), the sheen worked in (Curry), the pieces
//                      seated (Assemble)
//   coverage 0..1      Salt's salt, Dye's colour, Laminate's glue (progress stands in)
//   value, band        the band gauge's needle in its own unit (contracts §11.1): Harden's
//                      °C makes the steam, Tan's strength darkens the liquor, Tool's minutes
//                      since wetting dry the leather back to its colour
//   heat (°C)          as `value` for Harden; heat(c) does the same
//   dipped             Harden: the piece is in the kettle
//   harden 0..1        Harden: how far the piece has darkened and shrunk (7/8 at 1, PA §3.5)
//   strength 0..1      Tan: the liquor's strength (step by step)
//   cut 0..1           Tan's cut test: how far the tan has run through the cross-section
//   wet 0..1           Tool: casing moisture (dark when wet)
//   strikes, stitches  counts, when the game keeps them; else each hit adds one
//   defects            the harvest's, drawn into the hide as they happen
// hit(s, i): a curl off the beam, salt thrown, a stamp struck, a stitch pulled, a clamp
// closed. miss(i): a dull scrape. Nothing a game sends is a number the player is shown here;
// the stage draws, and the strip prints the numbers (UI plan §6.4).
//
// HOW IT IS BUILT. By hand, in WebGL1, on the herb stage's renderer, maths, meshes, biome
// grounds and particles (bench-stage/00-04, as they are), the forge's node helpers and
// welding (forge-stage/01-props.js) and its haft family for the grip (forge-stage/02-
// families.js), as they are, and the tannery's own parts in tannery-stage/. No third-party
// JavaScript, no textures, no downloads.
//
// THE LIGHT. The fill is the sky by the scene clock, tinted toward the day's phase
// (rules/sky.py's phases, never a planet). The KEY is the fire under the pot or the kettle,
// lit and steady (UI plan §6.3: no flicker loop), joined at night in a yard by the lantern on
// its post. The second light is the work's own gleam for a tier up or a Flawless, the third a
// flourish's flash.
//
// RENDER ON DEMAND (UI plan §7.4: "There is no flame, so idle draws zero frames with no
// exception; steam and the liquor ripple run only while a game is live"). `wake` is the only
// place requestAnimationFrame is called; a frame asks for the next only while something moves
// (a tween, a live game, a particle not yet dead), and wake refuses while the bench is HIDDEN
// (its box has no size) or the TAB is in the background. Tweens carry a timer as well, so a
// flourish's promise resolves on time even while hidden.
//
// REDUCED MOTION (13-device.js's still(): the OS setting, Short flourishes, or
// reducedMotion(true)): nothing flies, nothing shakes, no stroke or swap animation; states
// still show at once (the cleared flesh, the stitches, the shrink, the cut test), because they
// are what the work now is.
//
// SOUND. The stage rings its flourishes only, on U6's leather bus: leather.tier.up,
// .flawless, .fail, .land, .grade. The shell plays leather.open and leather.method.<m>, and the
// games their knives, scrapes, slosh, steam, stitches and stamps; a stage that played them too
// would ring every one twice (the alchemy bench's measured lesson).
//
// WHAT IT MAY NOT DO. The canvas takes no pointer events, every flourish ends on its own inside
// 1.1 s, and the Flawless shake moves the STAGE canvas only. Nothing here can throw into a
// caller: without WebGL every call is a quiet no-op and `available()` says false, so U1 shows
// its flat engraved-icon stage.
(function () {
  "use strict";

  var K = window.BenchStageKit || {};
  var F = window.ForgeStageKit || {};
  var T = window.TanneryStageKit || {};
  var M = K.math, G = K.mesh;
  var READY = !!(K.math && K.Renderer && K.mesh && K.ground && K.Particles &&
                 F.props && F.geo && F.families &&
                 T.hide && T.props && T.pieces && T.yard && T.fx);
  var D2R = Math.PI / 180;
  var BG = [13 / 255, 11 / 255, 9 / 255];          // --bg, #0d0b09
  var MAX_PIXELS = 3840 * 2160;
  var METHODS = ["flense", "salt", "tan", "curry", "cut", "stitch", "harden", "tool", "dye",
                 "laminate", "assemble", "grade"];
  // Where each method's work lies, which slot is the work, and which hand tool serves it.
  var ACT = {
    flense: { spot: "beam", slot: "hide", tool: "flense", fat: true },
    salt: { spot: "flat", slot: "hide" },
    tan: { spot: "pot", slot: "hide" },
    curry: { spot: "flat", slot: "piece", tool: "curry" },
    cut: { spot: "flat", slot: "hide", tool: "cut", chalk: true },
    stitch: { spot: "pony", slot: "piece", tool: "stitch", shape: true },
    harden: { spot: "kettle", slot: "piece", shape: true },
    tool: { spot: "flat", slot: "piece", tool: "tool" },
    dye: { spot: "flat", slot: "piece", tool: "dye" },
    laminate: { spot: "flat", slot: "piece", tool: "laminate" },
    assemble: { spot: "flat", slot: "body", product: true },
    grade: { spot: "flat", slot: "hide", tool: "grade" }
  };
  // The only keys of a piece the stage reads (see the header: the hidden-secret rule).
  var PIECE_KEYS = ["material", "color", "surface", "grade", "passes", "defects", "form", "units",
                    "plan", "tannage_kind", "tannage", "hardened"];
  // Forms that are a whole hide (drawn as the hide); everything else is a cut piece.
  var HIDE_FORMS = { green: 1, salted: 1, pelt: 1, leather: 1, fur: 1, rawhide: 1 };
  // Tannages that dry on the frame rather than in a vat or the pot (rawhide is dried
  // stretched; alum-tawed skins are staked and dried; PA §3.3).
  var ON_FRAME = { rawhide: 1, alum: 1 };
  var PHASES = ["dawn", "morning", "noon", "afternoon", "dusk", "night", "midnight"];
  var TINT = { dawn: [1.06, 0.9, 0.9], morning: [1.0, 0.99, 0.96], noon: [1, 1, 1],
               afternoon: [1.02, 0.98, 0.92], dusk: [1.1, 0.88, 0.72], night: [0.84, 0.92, 1.1],
               midnight: [0.74, 0.84, 1.16] };
  var STITCHES = 26, STAMPS = 24, DASHES = 48;

  var S = {
    host: null, canvas: null, r: null, ro: null, mounted: false, lost: false, raf: 0, lastT: 0,
    hiddenBox: false, hiddenTab: false,
    scene: { kind: "kit", biome: "", roofed: false, minute: 12 * 60 },
    sets: {}, set: null, groundRec: null, groundNode: null,
    method: null, work: null, workKey: "", act: null, leaving: null, swap: null, tools: {},
    look: {}, game: null, gameOn: false, gameLast: 0, emitAt: 0, hits: 0,
    particles: null, tweens: [], reduced: false,
    flare: 0, flareCol: [1, 0.85, 0.55], glint: 0, dim: 1, reveal: 1, settle: 0, flex: 0, dull: 0,
    cssW: 1, cssH: 1, cam: null, productOn: false, actAlpha: 1, actLift: 0,
    stats: { frames: 0, draws: 0, lastDraws: 0, ms: [], rafs: 0, key: [0, 0, 0], fill: [0, 0, 0], steam: 0 }
  };

  function now() { return (window.performance && performance.now) ? performance.now() : Date.now(); }
  function sound(name, opts) {
    try { if (window.Sound && typeof window.Sound.play === "function") window.Sound.play(name, opts); } catch (e) { /* silent */ }
  }
  function warn(where, e) {
    if (window.console && console.warn) console.warn("TanneryStage." + where + ":", e && e.message ? e.message : e);
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

  // TANNERY-STAGE-RAF: the only requestAnimationFrame in the stage. It is reached from wake()
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
  function endTweenQuiet(tw) {
    var i = S.tweens.indexOf(tw);
    if (i < 0) return;
    S.tweens.splice(i, 1);
    if (tw.timer) clearTimeout(tw.timer);
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
    if (isLive(t)) { busy = true; liveStep(t / 1000); }
    if (S.particles.alive()) { S.particles.step(dt, t / 1000); busy = true; }
    else S.particles.counts[0] = S.particles.counts[1] = 0;
    if (S.flare > 0.005) { S.flare *= Math.exp(-dt * 7.5); busy = true; } else S.flare = 0;
    applyPose();
    return busy;
  }

  /* While a game is live: the kettle steams by its heat while the piece is in it, the vat's
     liquor stirs. Nothing here runs when the game stops sending states. */
  function liveStep(ts) {
    if (still() || ts - S.emitAt < 0.09) return;
    S.emitAt = ts;
    var a = S.act, L = S.look;
    if (!a) return;
    if (S.method === "harden" && a.surface) {
      var k = L.heatK === undefined ? 0.6 : L.heatK;
      if (k > 0.25 || L.dipped) { T.fx.steam(FX.emit, [a.surface[0] + 0.08, a.surface[1] + 0.03, a.surface[2] - 0.05], Math.max(k, L.dipped ? 0.8 : 0)); S.stats.steam++; }
    } else if (S.method === "tan" && a.surface && L.strength > 0.02 && Math.random() < 0.25) {
      T.fx.ripple(FX.emit, [a.surface[0], a.surface[1] + 0.01, a.surface[2]], liquorColor());
    }
  }

  /* --- the sets ------------------------------------------------------------------------- */

  function setFor(kind) {
    if (!S.sets[kind]) S.sets[kind] = kind === "kit" ? T.yard.kit() : T.yard.yard(kind);
    return S.sets[kind];
  }

  function applyScene() {
    var kind = T.yard.kindOf(S.scene);
    S.set = setFor(kind);
    // The kit lies on the biome's own ground; a yard on packed earth (the town's flagstones
    // are geometry laid over it).
    var gk = kind === "kit" ? K.ground.kindFor({ biome: S.scene.biome, roofed: !!S.scene.roofed }) : "earth";
    var rec = K.ground.paint(gk);
    if (S.groundRec && S.groundRec !== rec && S.r) S.r.forgetTexture(S.groundRec);
    S.groundRec = rec;
    var k = 1 / rec.look.tile;
    var mt = F.props.mat("wood", { color: [1, 1, 1], pattern: 0, tex: rec, uvScale: [k, k], ground: 1,
                                   spec: rec.look.spec, shin: rec.look.shin });
    if (!S.groundNode) S.groundNode = F.props.node(G.plane(40), mt, { glint: false });
    S.groundNode.mat = mt;
    arrange();
    wake();
  }

  /* --- the work --------------------------------------------------------------------------- */

  /* A piece as the stage keeps it: the listed keys and nothing else. */
  function clean(p) {
    if (!p || typeof p !== "object") return null;
    var o = {};
    PIECE_KEYS.forEach(function (k) {
      var v = p[k];
      if (v === undefined || v === null) return;
      if (k === "defects") { o.defects = Array.isArray(v) ? v.map(function (d) { return d ? { u: d.u, v: d.v, kind: d.kind, len: d.len } : null; }) : num(v, 0); return; }
      if (typeof v === "object") return;
      o[k] = v;
    });
    return o;
  }

  function mainPiece() {
    var w = S.work, act = ACT[S.method];
    if (!w || !act) return null;
    var p = w.pieces;
    return p[act.slot] || p.hide || p.piece || p.body || null;
  }

  function tannageOf() {
    var w = S.work || {}, t = (w.pieces && w.pieces.tannin) || {};
    var words = [w.tannage, t.tannage_kind, t.tannage, t.material].map(function (x) { return String(x || "").toLowerCase(); }).join(" ");
    var m = /\b(rawhide|alum|bark|brain|mineral|planar)\b/.exec(words) || /(alum|bark|oak|brain|smoke|chrome|mineral|planar|rawhide)/.exec(words);
    if (!m) return "";
    return { oak: "bark", smoke: "brain", chrome: "mineral" }[m[1]] || m[1];
  }

  /* The spot the method's work goes to here. Tan: a frame for rawhide and alum, else the vat
     at a tannery and the pot at the kit. */
  function spotName() {
    var act = ACT[S.method];
    if (!act) return "flat";
    if (S.method === "tan") return ON_FRAME[tannageOf()] ? "frame" : (S.set.kind === "kit" ? "pot" : "vat");
    return act.spot;
  }

  function hideSpec(piece, spot) {
    var d = spot.drape, plan = T.hide.planOf(piece.plan), units = Math.max(0.25, num(piece.units, 1));
    var seed = T.hide.seedOf(piece.material || "hide");
    // Bounded drapes say how much room the hide has: inside a vat's curb, between a frame's
    // poles (a Large hide on a Medium frame was drawn past the top bar in the first capture).
    if (d.kind === "vat") d = { kind: "vat", at: d.at, r: d.r, fit: [2.1 * d.r, 1.9 * d.r] };
    else if (d.kind === "frame") d = { kind: "frame", at: d.at, lean: d.lean, hl: d.hl, hw: d.hw, fit: [2 * d.hl * 0.92, 2 * d.hw * 0.86] };
    return { plan: plan, units: +units.toFixed(2), seed: seed, drape: d };
  }

  function partMat(role, w) {
    var P = F.props, pc = w.pieces, L = lookFor();
    var main = pc.body || mainPiece() || {};
    if (role === "body") return T.hide.faces(main, L).out;
    if (role === "under") return T.hide.faces(main, L).under;
    if (role === "lining") return pc.lining ? T.hide.faces(pc.lining, {}).out : null;
    if (role === "haft") return P.mat("wood");
    if (role === "fit") return P.mat("brass", { spec: 0.9 });
    if (role === "lace") {
      var th = pc.thread || pc.fastenings;
      var c = th && T.hide.parseColor(th.color, null);
      return T.props.m("sinew", c ? { color: T.hide.toBase(c) } : null);
    }
    if (role === "fastenings") {
      var f = pc.fastenings, fc = f && T.hide.parseColor(f.color, null);
      if (f && /lacing|thread/.test(String(f.form || ""))) return T.props.m("sinew", fc ? { color: T.hide.toBase(fc) } : null);
      return P.mat("brass", fc ? { color: T.hide.toBase(fc), spec: 0.9 } : { spec: 0.9 });
    }
    return P.mat("leather");
  }

  /* The look the game's state and the method give the work's faces right now. */
  function lookFor() {
    var L = S.look, w = S.work || {}, m = S.method, o = {};
    o.quality = Math.max(0, Math.min(1.25, num(w.quality_index, 2) / 4));
    o.dull = S.dull;
    if (m === "salt") o.salt = L.coverage;
    if (m === "curry") o.sheen = L.progress;
    if (m === "tool") o.wet = L.wet;
    if (m === "harden") o.harden = L.harden;
    if (m === "dye") { var d = w.pieces && w.pieces.dye; if (d) o.dye = [d.color, L.coverage]; }
    if (m === "laminate") o.sheen = L.coverage * 0.6;
    return o;
  }

  /* Builds S.act for the method, the spot and the work. Meshes are cached in the parts, so
     switching back and forth builds nothing twice; only the small node tree is new. */
  function arrange() {
    if (!S.set) return;
    var P = F.props, set = S.set, act = ACT[S.method], w = S.work;
    var g = P.group(), a = { root: g, method: S.method, spot: null, main: [], extras: {} };
    S.act = a;
    if (!act) { refocus(); return; }
    var sn = spotName(), spot = set.spots[sn] || set.spots.flat;
    a.spot = sn; a.fit = spot.fit; a.surface = spot.surface || null;
    if (spot.water) {
      a.water = spot.water;
      a.waterBase = spot.water.mat.color.slice();
    }
    var piece = mainPiece();
    var form = piece ? String(piece.form || "leather").toLowerCase() : "";
    if (piece && (HIDE_FORMS[form] || !form) && !act.shape && !act.product && spot.drape) {
      buildHide(a, piece, spot, sn, act);
    } else if (piece || (act.product && w && w.product)) {
      buildPiece(a, piece || {}, spot, sn, act);
    }
    // The hand tool for the method, at its rest by the work.
    if (act.tool && T.props.HAND[act.tool]) {
      var tl = toolFor(act.tool);
      var at = spot.tool || (spot.at ? [spot.at[0] + 0.12, spot.at[1] + 0.12, spot.at[2] + 0.06] : (a.top || [0, 0.3, 0]));
      tl.root.pos = at.slice();
      tl.root.rot = sn === "beam" ? [0, 0.4, 0.25] : [0, 0.5, 0];
      tl.home = at.slice();
      P.add(g, tl.root);
      a.tool = tl;
    }
    // What serves the work: the dye pot by a dyed piece, the oil by a curried one, the spool
    // by the pony, clamps on a lamination, the cut test's slab by the vat.
    var pcs = (w && w.pieces) || {};
    var base = a.top || (spot.top ? spot.top.slice() : [0, 0.3, 0]);
    if (S.method === "dye") {
      var dp = toolFor("dyePot:" + (pcs.dye ? pcs.dye.color : ""), function () { return T.props.dyePot(pcs.dye ? T.hide.toBase(T.hide.parseColor(pcs.dye.color, [0.3, 0.2, 0.12])) : null); });
      dp.root.pos = dishSpot(spot, base);
      P.add(g, dp.root);
    } else if (S.method === "curry") {
      var of = toolFor("oil:" + (pcs.oil ? pcs.oil.color : ""), function () { return T.props.oilFlask(pcs.oil ? T.hide.toBase(T.hide.parseColor(pcs.oil.color, [0.5, 0.36, 0.2])) : null); });
      of.root.pos = dishSpot(spot, base);
      P.add(g, of.root);
    } else if (S.method === "stitch") {
      var sp = toolFor("spool:" + (pcs.thread ? pcs.thread.color : ""), function () { return T.props.spool(pcs.thread ? T.hide.toBase(T.hide.parseColor(pcs.thread.color, [0.85, 0.8, 0.66])) : null); });
      var pony = set.spots.pony.at;
      sp.root.pos = [pony[0] + 0.12, pony[1] - 0.3, pony[2] + 0.06];
      P.add(g, sp.root);
    } else if (S.method === "laminate" && a.top) {
      [-1, 1].forEach(function (s, i) {
        var c = toolFor("clamp" + i, T.props.clamp2);
        c.root.pos = [a.top[0] + s * 0.2 - 0.05, a.top[1] - 0.05, a.top[2] + 0.12];
        c.root.rot = [0, s > 0 ? Math.PI : 0, 0];
        P.add(g, c.root);
      });
    }
    if (S.method === "tan" && a.surface) {
      var ct = toolFor("cut-test", cutTest);
      ct.root.pos = [a.surface[0] + (sn === "pot" ? 0.32 : 0.6), 0.004, a.surface[2] + 0.3];
      ct.root.visible = false;
      P.add(g, ct.root);
      a.extras.cutTest = ct;
    }
    paintAll();
    refocus();
  }

  /* Where a pot or a flask stands by flat work: on the ground beside the board or the table, on
     its left, so it never sits on the piece (the first capture had the dye pot on the cloak). */
  function dishSpot(spot, base) {
    var t = spot.top || base;
    return [t[0] - (spot.hx || 0.4) - 0.16, 0, t[2] + 0.12];
  }

  /* Tan's cut test (UI plan §9: "a cut and its cross-section"): a slab of the hide's section,
     the tanned layers in from both faces, the raw core between them narrowing as the tan
     strikes through. */
  function cutTest() {
    var P = F.props, g = P.group();
    var cube = T.props.once("unit-box", function () { return G.box(1, 1, 1); });
    var top = P.add(g, P.node(cube, P.mat("leather", { color: [0.35, 0.2, 0.1] })));
    var bot = P.add(g, P.node(cube, P.mat("leather", { color: [0.35, 0.2, 0.1] })));
    var core = P.add(g, P.node(cube, P.mat("leather", { color: [0.86, 0.72, 0.62], pattern: 0 })));
    function set(k) {
      var t = 0.03, half = t / 2 * Math.max(0.04, k);
      top.scl = [0.14, half, 0.08]; top.pos = [0, t - half / 2, 0];
      bot.scl = [0.14, half, 0.08]; bot.pos = [0, half / 2, 0];
      core.scl = [0.14, Math.max(0.0005, t - 2 * half), 0.08]; core.pos = [0, t / 2, 0]; core.visible = k < 0.995;
    }
    set(0);
    return { root: g, set: set };
  }

  function toolFor(name, make) {
    if (!S.tools[name]) S.tools[name] = make ? make() : T.props.HAND[name]();
    return S.tools[name];
  }

  /* The whole hide, draped on the spot: two sheets, the fat while it is on, the scars, and
     whatever the method draws on it (the chalk and the cut, the lacing on the frame). */
  function buildHide(a, piece, spot, sn, act) {
    var P = F.props, spec = hideSpec(piece, spot);
    var layers = { fat: act.fat && /green|salted/.test(String(piece.form || "green")), passes: num(piece.passes, 0) };
    var h = T.hide.hide(spec, layers), faces = T.hide.faces(piece, lookFor());
    var g = P.group();
    a.hideNodes = {
      out: P.add(g, P.node(h.out, faces.out)),
      under: P.add(g, P.node(h.under, faces.under)),
      fat: h.fat ? P.add(g, P.node(h.fat, faces.fat)) : null,
      laminae: h.laminae.map(function (m) { return P.add(g, P.node(m, faces.under)); })
    };
    var sc = T.hide.scars(spec, piece.defects);
    if (sc) a.hideNodes.scars = P.add(g, P.node(sc, T.props.m("ink", { alpha: 0.9 }), { glint: false }));
    a.spec = spec; a.hideMesh = h;
    var mid = T.hide.pointAt(spec, 0.5, 0);
    a.top = mid.p.slice();
    if (sn === "vat" || sn === "pot") a.top = [spot.surface[0], spot.surface[1] + 0.04, spot.surface[2]];
    if (sn === "frame") {
      var edge = [];
      for (var i = 1; i < 10; i++) { edge.push(T.hide.pointAt(spec, i / 10, 0.98).p, T.hide.pointAt(spec, i / 10, -0.98).p); }
      var lm = T.props.lacing(edge, spot.frame, spot.origin, JSON.stringify(spec));
      if (lm) P.add(g, P.node(lm, T.props.m("sinew"), { glint: false }));
    }
    if (act.chalk) {
      var pat = T.pieces.patternOf((S.work || {}).product);
      var k = Math.min(1, 0.82 * h.size.L / pat.L, 0.82 * h.size.W / pat.W);
      var key = pat.shape + k.toFixed(3);
      var pts = T.pieces.edgeOf(pat.shape, pat.L * k, pat.W * k, 16);
      var line = T.pieces.outline(pts, DASHES, key);
      var top = spot.top || a.top;
      var yaw = (spot.drape && spot.drape.yaw) || 0;
      var lg = P.add(g, P.group({ pos: [top[0], top[1] + 0.0085, top[2]], rot: [0, yaw, 0] }));
      a.chalk = P.add(lg, P.node(line, T.props.m("chalk"), { glint: false }));
      a.cutLine = P.add(lg, P.node(line, T.props.m("ink"), { pos: [0, 0.0006, 0], glint: false }));
      a.cutLine.ranges = [[0, 0]];
    }
    if (h.fat) a.fatRows = h.fat.rows;
    a.mainGroup = P.add(a.root, g);
    a.main = [g];
  }

  /* A cut piece or a finished item: the product's family, coloured per role, laid on the
     table, clamped in the pony, or held over the kettle. */
  function buildPiece(a, piece, spot, sn, act) {
    var P = F.props, w = S.work || {}, form = String(piece.form || "panel").toLowerCase(), built;
    if (act.product || form === "item") built = T.pieces.build(w.product, w.base);
    else if (form === "lacing") built = T.pieces.build("lacing");
    else if (form === "grip") built = T.pieces.build("grip");
    else {
      var pat = T.pieces.patternOf(w.product);
      built = { parts: [{ mesh: T.pieces.panel(pat.shape, pat.L, pat.W, form === "plate" ? 0.06 : 0.008), role: "body" }], pat: pat };
      built.lo = built.parts[0].mesh.bounds.lo; built.hi = built.parts[0].mesh.bounds.hi;
    }
    var inner = P.group(), roles = {};
    built.parts.forEach(function (pt) {
      var mt = partMat(pt.role, w);
      if (!mt) return;
      var n = P.add(inner, P.node(pt.mesh, mt, pt.at ? { pos: pt.at } : null));
      (roles[pt.role] = roles[pt.role] || []).push(n);
      if (pt.wrap) { n.ranges = [[0, pt.mesh.count * pt.mesh.per]]; a.wrap = n; }
    });
    // Laminated plies under a panel, one per pass.
    if (!act.product && form !== "lacing" && form !== "grip" && built.pat) {
      var plies = Math.min(4, num(piece.passes, 0) + (S.method === "laminate" ? 1 : 0));
      for (var i = 0; i < plies; i++) (roles.under = roles.under || []).push(P.add(inner, P.node(built.parts[0].mesh, partMat("under", w), { pos: [0, -0.005 * (i + 1), 0] })));
    }
    a.roles = roles;
    var span = Math.max(built.hi[0] - built.lo[0], built.hi[2] - built.lo[2]);
    var fitTo = sn === "pony" ? 0.36 : (sn === "kettle" ? (S.set.kind === "kit" ? 0.26 : 0.44) : (sn === "flat" ? 0.9 : 0.6));
    var s = span > fitTo ? fitTo / span : 1;
    // Harden shrinks the piece to about 7/8 of its size at the right heat and time (PA §3.5).
    var g = P.group({ scl: [s, s, s] });
    g.kids = [inner];
    inner.pos = [-(built.lo[0] + built.hi[0]) / 2, -built.lo[1], -(built.lo[2] + built.hi[2]) / 2];
    var outer = P.group();
    outer.kids = [g];
    a.scaleNode = g; a.baseScale = s;
    var top;
    if (sn === "pony") {
      // Upright in the jaws, the seam along the top edge.
      // Its lower edge 7 cm down in the jaws, the rest standing above them.
      var j = spot.at, halfW = (built.hi[2] - built.lo[2]) * s / 2;
      outer.pos = [j[0], j[1] + halfW - 0.07, j[2]];
      // A quarter turn about x stands it up with its face (+y) toward the camera (+z); the other
      // way round, the first capture showed the piece's back and no seam.
      g.rot = [Math.PI / 2, 0, 0];
      g.pos = [0, 0, 0];
      top = [j[0], j[1] + 2 * halfW - 0.07, j[2]];
      if (built.pat) {
        // Turned up that way, the -z edge is the top: the seam runs along it, a little in.
        var half = T.pieces.edgeOf(built.pat.shape, built.pat.L, built.pat.W, 12).slice(13).map(function (p) { return [p[0], 0.004, p[2] + 0.014]; });
        var sm = T.pieces.seam(half, STITCHES, built.pat.shape + "top");
        var th = (w.pieces || {}).thread, tc = th && T.hide.parseColor(th.color, null);
        a.seam = P.add(inner, P.node(sm, T.props.m("sinew", tc ? { color: T.hide.toBase(tc) } : null), { glint: false }));
        a.seam.ranges = [[0, 0]];
      }
    } else if (sn === "kettle") {
      // Held upright over the kettle, face to the camera, and dipped to a little under half
      // its height. The first draft turned it on its edge to the eye and sank it half way: the
      // live capture showed a line in the water and nothing else.
      var m0 = spot.mouth, half = (built.hi[2] - built.lo[2]) * s / 2;
      g.rot = [Math.PI / 2, 0, 0];
      outer.pos = [m0[0], m0[1] + half + 0.03, m0[2]];
      a.kettleHome = outer.pos.slice();
      a.kettleDip = [m0[0], spot.surface[1] + half * 0.1, m0[2]];
      top = outer.pos.slice();
    } else {
      var t0 = spot.top || (spot.surface ? [spot.surface[0], spot.surface[1] + 0.02, spot.surface[2]] : [0, 0.3, 0]);
      outer.pos = [t0[0], t0[1] + 0.002, t0[2]];
      outer.rot = [0, (spot.drape && spot.drape.yaw) || 0, 0];
      top = [t0[0], t0[1] + (built.hi[1] - built.lo[1]) * s, t0[2]];
    }
    if (S.method === "tool" && built.pat) {
      a.stamps = P.add(inner, P.node(stampGrid(built.pat), T.props.m("ink", { alpha: 0.55 }), { pos: [0, 0.0105, 0], glint: false }));
      a.stamps.ranges = [[0, 0]];
    }
    a.top = top;
    a.mainGroup = P.add(a.root, outer);
    a.main = [outer];
  }

  /* The stamp impressions Tool lays down, a border round the panel, welded in order so the
     first k strikes are indices [0, k * per]. */
  function stampGrid(pat) {
    return T.props.once("stamps" + pat.shape + pat.L + pat.W, function () {
      var pts = T.pieces.edgeOf(pat.shape, pat.L * 0.8, pat.W * 0.8, STAMPS / 2 - 1), disc = G.disc(0.012, 10), parts = [];
      pts.slice(0, STAMPS).forEach(function (p) { parts.push({ mesh: disc, m: M.compose(p, [0, 0, 0], [1, 1, 1]) }); });
      var m = G.merge(parts);
      m.per = disc.idx.length;
      return m;
    });
  }

  /* Paints the faces and draws what the game state says onto the work. Cheap: a few vectors
     and a few index ranges. */
  function liquorColor() {
    var w = S.work || {}, t = w.pieces && w.pieces.tannin, L = S.look;
    var tc = t ? T.hide.parseColor(t.color, null) : null;
    var tk = T.hide.TANNAGE[tannageOf()];
    var col = tc || tk || [0.45, 0.32, 0.2];
    // The liquor darkens toward the tannin's own colour step by step as the strength rises.
    return M.lerp3([0.42, 0.42, 0.38], M.scale(col, 0.55), 0.35 + 0.65 * clamp01(L.strength));
  }
  function paintAll() {
    var a = S.act, L = S.look;
    if (!a) return;
    var piece = mainPiece();
    if (a.hideNodes && piece) {
      var f = T.hide.faces(piece, lookFor());
      a.hideNodes.out.mat = f.out;
      a.hideNodes.under.mat = f.under;
      a.hideNodes.laminae.forEach(function (n) { n.mat = f.under; });
      if (a.hideNodes.fat) {
        // Flense: the fat is drawn only over the rows the knife has not reached, from the
        // tail end up.
        var rows = a.fatRows, cleared = Math.round(clamp01(L.progress) * rows);
        var per = a.hideNodes.fat.mesh.rowIdx;
        a.hideNodes.fat.ranges = [[cleared * per, Math.max(0, rows - cleared) * per]];
        a.hideNodes.fat.visible = cleared < rows;
      }
    }
    if (a.roles) {
      var w = S.work || {};
      ["body", "under"].forEach(function (r) {
        (a.roles[r] || []).forEach(function (n) { n.mat = partMat(r, w); });
      });
      if (a.roles.fastenings) a.roles.fastenings.forEach(function (n) { n.alpha = S.method === "assemble" ? 0.25 + 0.75 * clamp01(L.progress === undefined ? 1 : L.progress) : 1; });
    }
    if (a.cutLine) {
      var mesh = a.cutLine.mesh, k = Math.round(clamp01(L.progress) * DASHES);
      a.cutLine.ranges = [[0, k * mesh.per]];
      a.cutLine.visible = k > 0;
    }
    if (a.seam) {
      var n = L.stitches !== undefined ? Math.round(num(L.stitches, 0)) : Math.round(clamp01(L.progress) * STITCHES);
      n = Math.max(0, Math.min(STITCHES, n));
      a.seam.ranges = [[0, n * a.seam.mesh.per]];
      a.seam.visible = n > 0;
    }
    if (a.stamps) {
      var ns = Math.max(0, Math.min(STAMPS, Math.round(L.strikes !== undefined ? num(L.strikes, 0) : S.hits)));
      a.stamps.ranges = [[0, ns * a.stamps.mesh.per]];
      a.stamps.visible = ns > 0;
    }
    if (a.wrap) {
      var nw = a.wrap.mesh.count, kw = S.method === "cut" || S.method === "assemble" ? Math.max(1, Math.round(clamp01(L.progress === undefined ? 1 : L.progress) * nw)) : nw;
      a.wrap.ranges = [[0, kw * a.wrap.mesh.per]];
    }
    if (a.water && S.method === "tan") a.water.mat.color = T.hide.toBase(liquorColor());
    if (a.extras.cutTest) {
      a.extras.cutTest.root.visible = L.cut !== undefined;
      if (L.cut !== undefined) a.extras.cutTest.set(clamp01(L.cut));
    }
  }

  /* --- poses -------------------------------------------------------------------------------- */
  function applyPose() {
    var a = S.act, L = S.look;
    if (!a) return;
    a.root.alpha = S.actAlpha;
    a.root.pos = [0, S.actLift, 0];
    var g = a.mainGroup;
    if (g) {
      var settle = S.settle, sink = 0;
      if (S.method === "tan" && (a.spot === "vat" || a.spot === "pot")) sink = -0.05 * clamp01(L.progress === undefined ? 0 : L.progress);
      if (a.kettleHome) {
        var d = L.dipped ? 1 : 0;
        if (S.dip === undefined) S.dip = d;
        S.dip += (d - S.dip) * (still() ? 1 : 0.35);
        if (Math.abs(S.dip - d) < 0.01) S.dip = d;
        g.pos = M.lerp3(a.kettleHome, a.kettleDip, S.dip);
        if (S.dip !== d) wake();
      } else if (a.hideNodes) {
        g.pos = [0, settle + sink, 0];
      } else {
        var bp = g.home || (g.home = g.pos.slice());
        g.pos = [bp[0], bp[1] + settle + sink, bp[2]];
      }
      if (a.scaleNode) {
        var sh = 1 - 0.125 * (S.method === "harden" ? clamp01(L.harden) : 0);
        var flex = 1 + 0.05 * Math.sin(S.flex * Math.PI);
        var s = a.baseScale * sh;
        a.scaleNode.scl = [s * flex, s, s];
      } else if (a.hideNodes) {
        g.scl = [1, 1 + 0.04 * Math.sin(S.flex * Math.PI), 1];
      }
    }
  }

  /* A stroke of the hand tool: down to the work and along, then back (200 ms). */
  function stroke(strength) {
    var t = S.act && S.act.tool;
    if (!t || still()) return;
    var home = t.home, dir = S.method === "tool" ? [0, -0.05, 0] : [0.09, -0.04, 0];
    if (t.tw) endTweenQuiet(t.tw);
    t.tw = tween(200, function (q) {
      var e = Math.sin(Math.PI * q) * (0.6 + 0.4 * clamp01(strength));
      t.root.pos = M.add(home, M.scale(dir, e));
    }, function () { t.root.pos = home.slice(); t.tw = null; });
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
    var moon = (1 - day) * (1 - dusk);
    L.amb = M.add(M.lerp3([0.08, 0.085, 0.11], [0.36, 0.37, 0.4], day), [0.06 * dusk, 0.03 * dusk, 0.012 * dusk]);
    L.fillDir = LIGHT;
    L.fillCol = M.add(M.add(M.scale([0.86, 0.86, 0.9], 0.85 * day), M.scale([0.7, 0.42, 0.24], 0.55 * dusk)),
                      M.scale([0.22, 0.29, 0.5], 0.42 * moon));
    // The key: the lantern at night in a yard, else the fire under the pot or the kettle. A
    // steady light (no flicker loop), strong only when the sky is not.
    var lan = S.set && S.set.lantern, night = 1 - day;
    if (lan && night > 0.3) {
      L.keyPos = lan.at;
      var kl = 0.3 + 0.8 * night;
      L.keyCol = [1.3 * kl, 0.98 * kl, 0.62 * kl];
    } else {
      L.keyPos = S.set && S.set.fire ? S.set.fire.at : [0, 0.3, 0];
      var kk = 0.15 + 0.9 * night;
      L.keyCol = [1.25 * kk, 0.82 * kk, 0.45 * kk];
    }
    if (lan) lan.node.light.visible = night > 0.3;
    L.amb = tint(L.amb, ph);
    L.fillCol = tint(L.fillCol, ph);
    L.phase = ph;
    return L;
  }

  /* --- camera --------------------------------------------------------------------------------
     Pitched down onto the work (UI plan §6.3: "camera at about 35° looking down the beam" at
     the kit; a yard a little flatter so the vats and the rack behind are seen). The field of
     view is SOLVED from the points to frame, as every other stage solves it, so the work fills
     the stage at every aspect and nothing falls off its edges. Each spot has its own box; the
     frame glides from one to the next with the swap, and cuts between sets. */
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
  function boxCloud(b) {
    var pts = new Float32Array(24), i = 0;
    for (var c = 0; c < 8; c++) {
      pts[i++] = b.c[0] + (c & 1 ? b.h[0] : -b.h[0]);
      pts[i++] = Math.max(0, b.c[1] + (c & 2 ? b.h[1] : -b.h[1]));
      pts[i++] = b.c[2] + (c & 4 ? b.h[2] : -b.h[2]);
    }
    return { pts: pts, centre: b.c.slice(), dist: 1.6 + 2.2 * Math.max(b.h[0], b.h[2]) };
  }
  function focusCloud() {
    var a = S.act;
    if (!a || !a.fit) {
      var f = S.set.fit, pts = f.pts;
      return { pts: pts, centre: f.centre, dist: 4.2 };
    }
    return boxCloud(a.fit);
  }
  function cloud() {
    var to = S.focus || focusCloud(), from = S.camFrom;
    if (!from || from.pts.length !== to.pts.length) return to;
    var m = clamp01(S.camMix);
    if (m >= 1) return to;
    var pts = new Float32Array(to.pts.length);
    for (var i = 0; i < pts.length; i++) pts[i] = from.pts[i] + (to.pts[i] - from.pts[i]) * m;
    return { pts: pts, centre: M.lerp3(from.centre, to.centre, m), dist: from.dist + (to.dist - from.dist) * m };
  }
  function refocus() {
    if (!S.set) return;
    var start = S.camSet === S.set && S.focus ? cloud() : null;
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
    var pitch = ((S.act && S.act.fit && S.act.fit.pitch) || fit.pitch) * D2R;
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
    var at = a && a.top ? a.top : [0, 0.4, 0];
    var gk = S.glint;
    r.begin({
      vp: cam.vp, view: cam.view, proj: cam.proj, eye: cam.eye, amb: L.amb, keyPos: L.keyPos, keyCol: L.keyCol,
      fillDir: L.fillDir, fillCol: L.fillCol,
      glowPos: [at[0], at[1] + 0.3, at[2] + 0.2], glowCol: [0.9 * gk, 0.75 * gk, 0.45 * gk],
      flarePos: [at[0], at[1] + 0.25, at[2] + 0.3], flareCol: M.scale(S.flareCol, S.flare * 2.4),
      exposure: S.dim, reveal: S.reveal, bg: BG, fade: [4.6, 11.5],
      px: r.canvas.height / (2 * cam.t)
    });
    S.stats.key = L.keyCol.slice();
    S.stats.fill = L.fillCol.slice();
    S.stats.phase = L.phase;
    var items = [], I = M.ident();
    if (S.groundNode) collect(S.groundNode, I, 1, 0, items);
    collect(S.set.root, I, 1, 0, items);
    if (S.leaving) collect(S.leaving, I, 1, 0, items);
    if (a && a.root) collect(a.root, I, 1, S.glint, items);
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
    alpha.sort(function (p, q) {
      var oa = p.n.mat.order || 0, ob = q.n.mat.order || 0;
      return oa !== ob ? oa - ob : q.depth - p.depth;
    });
    function issue(list) {
      list.forEach(function (it) {
        if (it.n.ranges) it.n.ranges.forEach(function (rg) { if (rg[1] > 0) r.draw(it.n.mesh, it.m, it.n.mat, it.a, it.glint, rg); });
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

  /* --- the game --------------------------------------------------------------------------------- */

  // Harden's water heat, as a pose: steam rises past about 50 °C (the bottom of the server's
  // Harden band in content/world-classes/leatherworker.json is the first heat that works the
  // leather) and is full at the boil. Only the look: the band and its number are the strip's.
  function heatK(c) { return clamp01((num(c, 20) - 30) / 70); }

  function readState(st, method) {
    var L = S.look, band = st.band || {};
    if (st.progress !== undefined) L.progress = clamp01(st.progress);
    if (st.coverage !== undefined) L.coverage = clamp01(st.coverage);
    else if (st.progress !== undefined && (method === "salt" || method === "dye" || method === "laminate")) L.coverage = clamp01(st.progress);
    var unit = String(band.unit || st.unit || "");
    var v = st.value !== undefined ? num(st.value, null) : null;
    var c = st.heat !== undefined ? st.heat : (st.c !== undefined ? st.c : (unit === "celsius" || method === "harden" ? v : null));
    if (c !== null && c !== undefined) L.heatK = heatK(c);
    if (st.dipped !== undefined) L.dipped = !!st.dipped;
    if (st.harden !== undefined) L.harden = clamp01(st.harden);
    if (st.strength !== undefined) L.strength = clamp01(st.strength);
    else if (v !== null && (unit === "strength" || method === "tan")) L.strength = clamp01(v);
    if (st.cut !== undefined) L.cut = clamp01(st.cut);
    if (st.wet !== undefined) L.wet = clamp01(st.wet);
    // Tool's needle is minutes since wetting: dark when just wetted, its colour back by about
    // 40 minutes (the casing band's far edge in the content is 40).
    else if (v !== null && (unit === "minutes" || method === "tool")) L.wet = clamp01(1 - v / 40);
    if (st.strikes !== undefined) L.strikes = num(st.strikes, 0);
    if (st.stitches !== undefined) L.stitches = num(st.stitches, 0);
    if (st.defects !== undefined && S.work) {
      var p = mainPiece();
      if (p) {
        var d = clean({ defects: st.defects }).defects;
        if (JSON.stringify(d) !== JSON.stringify(p.defects)) { p.defects = d; arrange(); }
      }
    }
  }

  function game(method, opts) {
    opts = opts || {};
    var g = { method: method, on: false };
    function mine() { return S.game === g; }
    function begin() {
      if (S.game !== g) S.game = g;
      if (g.on) return;
      g.on = true; S.gameOn = true;
      S.hits = 0;
      S.look = { progress: 0, coverage: 0, strength: 0, wet: method === "tool" ? 1 : 0, harden: 0 };
      if (opts.band) readState({ band: opts.band, value: opts.band.value_start }, method);
      paintAll();
    }
    var view = {
      update: safe("game.update", function (st) {
        if (!st || typeof st !== "object") return;
        begin();
        S.gameLast = now();
        readState(st, method);
        paintAll();
        if (mine()) wake();
      }),
      heat: safe("game.heat", function (c) {
        begin();
        S.gameLast = now();
        S.look.heatK = heatK(c);
        wake();
      }),
      hit: safe("game.hit", function (strength) {
        if (!mine()) return;
        begin();
        S.gameLast = now();
        S.hits++;
        var a = S.act, s = clamp01(strength === undefined ? 1 : strength);
        if (!a) return;
        var at = a.top || [0, 0.4, 0], w = S.work || {}, pcs = w.pieces || {};
        if (method === "flense") T.fx.curl(FX.emit, at);
        else if (method === "salt") T.fx.grains(FX.emit, [at[0], at[1] + 0.15, at[2]]);
        else if (method === "tan" && a.surface) T.fx.ripple(FX.emit, a.surface, liquorColor());
        else if (method === "curry") T.fx.curl(FX.emit, at, pcs.oil ? T.hide.parseColor(pcs.oil.color, null) : [0.6, 0.45, 0.25]);
        else if (method === "cut") T.fx.curl(FX.emit, at, T.hide.faces(mainPiece() || {}, {}).rgb);
        else if (method === "tool") T.fx.stamp(FX.emit, at);
        else if (method === "dye") T.fx.bleed(FX.emit, at, pcs.dye ? T.hide.parseColor(pcs.dye.color, null) : null);
        else T.fx.pull(FX.emit, at);
        stroke(s);
        S.flare = Math.max(S.flare, 0.03 + 0.04 * s); S.flareCol = [1, 0.88, 0.62];
        paintAll();
        wake();
      }),
      // A miss: a dull scrape. Nothing is undone.
      miss: safe("game.miss", function () {
        if (!mine()) return;
        S.gameLast = now();
        if (S.act) T.fx.nick(FX.emit, S.act.top || [0, 0.4, 0]);
        wake();
      }),
      end: safe("game.end", function () {
        g.on = false;
        if (S.game === g) S.gameOn = false;
        wake();
      })
    };
    S.game = g;
    return view;
  }

  /* --- flourishes ------------------------------------------------------------------------------ */
  var KINDS = { tier: "tier", tierUp: "tier", flawless: "flawless", land: "land", fail: "fail", sink: "sink", grade: "grade" };

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
      var top = a && a.top ? a.top : [0, 0.4, 0];
      if (k === "tier") {
        // The leather sheens (UI plan §10).
        sound("leather.tier.up");
        T.fx.gilt(FX.emit, top, 10);
        tween(380, function (q) { S.glint = Math.sin(Math.PI * q) * 0.9; }, function () { S.glint = 0; resolve(true); });
      } else if (k === "flawless") {
        sound("leather.flawless");
        T.fx.gilt(FX.emit, top, 60);
        S.flare = Math.max(S.flare, 1.1); S.flareCol = [1, 0.82, 0.48];
        tween(700, function (q) { S.glint = Math.sin(Math.PI * q) * 1.2; }, function () { S.glint = 0; resolve(true); });
        shake(5, 250);
      } else if (k === "fail") {
        // The work dulls, and the stage dims 30% for 600ms. The dull stays: it is what the work
        // now is, until another work is sent.
        sound("leather.fail");
        tween(600, function (q) {
          S.dim = q < 0.12 ? 1 - 0.3 * (q / 0.12) : (q < 0.55 ? 0.7 : 0.7 + 0.3 * M.ease.inOutSine((q - 0.55) / 0.45));
          S.dull = Math.min(1, q * 2);
          paintAll();
        }, function () { S.dim = 1; S.dull = 1; paintAll(); resolve(true); });
      } else if (k === "sink") {
        // Tanning starts (UI plan §10): the hide sinks into the vat. The look's progress is the
        // sink, so it stays down after; reduced motion puts it there at once.
        if (S.act && S.act.surface) T.fx.ripple(FX.emit, S.act.surface, liquorColor());
        if (quiet) { S.look.progress = 1; paintAll(); wake(); resolve(true); return; }
        var p0 = clamp01(S.look.progress);
        tween(700, function (q) { S.look.progress = p0 + (1 - p0) * M.ease.inOutSine(q); }, function () { resolve(true); });
      } else if (k === "grade") {
        // Grade has no game (UI plan §9): a short flex and a look, then the result in words.
        sound("leather.grade");
        tween(quiet ? 200 : 650, function (q) { S.flex = quiet ? 0 : Math.sin(Math.PI * 2 * q) * (1 - q); }, function () { S.flex = 0; resolve(true); });
      } else if (k === "land") {
        sound("leather.land");
        land(resolve, top);
      }
      wake();
    });
  }

  /* The product lands (UI plan §10): the work lifts and is gone, and U1 flies its own copy from
     productRect() to the rack row. Reduced motion: it glints, then it is not there. */
  function land(resolve, top) {
    var a = S.act;
    var g = a && a.mainGroup;
    if (!g) { tween(300, function () {}, function () { resolve(true); }); return; }
    S.productOn = true;
    if (still()) {
      tween(500, function (q) { S.glint = q < 0.5 ? 0.4 : 0; }, function () { S.productOn = false; g.visible = false; S.glint = 0; resolve(true); });
      return;
    }
    T.fx.gilt(FX.emit, top, 8);
    tween(500, function (q) {
      var e = M.ease.outCubic(Math.min(1, q / 0.7));
      S.settle = 0.25 * e;
      g.alpha = q > 0.75 ? (1 - q) / 0.25 : 1;
    }, function () { S.productOn = false; g.visible = false; g.alpha = 1; S.settle = 0; resolve(true); });
  }

  /* Where the work is, in viewport pixels. */
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
    var a = S.act;
    if (a && a.mainGroup) {
      collect(a.root, M.ident(), 1, 0, items, true);
      items.forEach(function (it) {
        if (it.n.mat && (it.n.mat.unlit || it.n.mat.pass === "alpha")) return;
        var bb = it.n.mesh.bounds;
        for (var c = 0; c < 8; c++) pts.push(M.xform(it.m, [c & 1 ? bb.hi[0] : bb.lo[0], c & 2 ? bb.hi[1] : bb.lo[1], c & 4 ? bb.hi[2] : bb.lo[2]]));
      });
    }
    if (!pts.length) pts.push(a && a.top ? a.top : [0, 0.4, 0]);
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    pts.forEach(function (p) {
      var v = M.xform(cam.vp, [p[0], p[1], p[2]]);
      var sx = b.left + (v[0] / v[3] * 0.5 + 0.5) * b.width, sy = b.top + (1 - (v[1] / v[3] * 0.5 + 0.5)) * b.height;
      x0 = Math.min(x0, sx); x1 = Math.max(x1, sx); y0 = Math.min(y0, sy); y1 = Math.max(y1, sy);
    });
    x0 = Math.max(b.left, x0); y0 = Math.max(b.top, y0); x1 = Math.min(b.left + b.width, x1); y1 = Math.min(b.top + b.height, y1);
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
      if (!S.set) S.set = setFor(T.yard.kindOf(S.scene));
      if (same && S.act) { resolve(true); return; }
      // No look until a game sends one: a piece shown between games is shown as it is.
      S.look = {};
      S.hits = 0; S.dip = undefined;
      var old = S.act && S.act.root;
      arrange();
      if (!S.mounted) { resolve(true); return; }
      // The old work lifts away and the new arrangement sets down, 450ms (UI plan §10: "tools
      // swap on the kit roll"); under reduced motion, a 120ms crossfade.
      S.leaving = old || null;
      var sw = { resolve: resolve };
      S.swap = sw;
      if (still()) {
        sw.tw = tween(120, function (p) { S.actAlpha = p; S.actLift = 0; if (old) old.alpha = 1 - p; });
      } else {
        sw.tw = tween(450, function (p) {
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

  /* --- the work arrives -------------------------------------------------------------------- */
  function workKey(w) {
    if (!w) return "";
    var p = w.pieces, out = [w.product || "", w.base || "", w.tannage || ""];
    Object.keys(p).sort().forEach(function (k) {
      var q = p[k];
      out.push(k, q.material || "", q.form || "", q.plan || "", q.units || "", q.passes || "", q.color || "", q.surface || "", q.tannage_kind || "", JSON.stringify(q.defects || 0));
    });
    return out.join("|");
  }
  function setWork(w) {
    w = w && typeof w === "object" ? w : null;
    var next = null;
    if (w) {
      next = { product: String(w.product || ""), base: String(w.base || ""), tannage: String(w.tannage || ""),
               quality_index: num(w.quality_index, 2), pieces: {} };
      var src = w.pieces && typeof w.pieces === "object" ? w.pieces : {};
      Object.keys(src).forEach(function (slot) {
        var c = clean(src[slot]);
        if (c) next.pieces[String(slot).toLowerCase()] = c;
      });
    }
    var key = workKey(next), changed = key !== S.workKey;
    var hadMain = !!(S.act && S.act.mainGroup);
    S.work = next;
    S.workKey = key;
    if (!S.set) S.set = setFor(T.yard.kindOf(S.scene));
    if (changed) {
      // A new work clears what the last one's failure and the last game's look left on it.
      S.dull = 0;
      S.look = {}; S.hits = 0; S.dip = undefined;
      arrange();
      // Drop into a slot (UI plan §10): the piece lays onto the beam, the frame or the table.
      if (S.mounted && S.act && S.act.mainGroup && !still()) {
        if (S.settleTw) endTweenQuiet(S.settleTw);
        S.settleTw = tween(hadMain ? 260 : 420, function (q) { S.settle = 0.18 * (1 - M.ease.outCubic(q)); }, function () { S.settle = 0; S.settleTw = null; });
      }
    } else {
      S.work.quality_index = next ? next.quality_index : 2;
      paintAll();
    }
    wake();
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
        cv.className = "tannery-stage-canvas";
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
        S.dull = 0;
        applyScene();
        // Open the bench (UI plan §10): the ground fades in from the page's dark and the hide
        // settles on the beam; reduced motion, a fade only.
        S.reveal = 0;
        var quiet = still();
        tween(quiet ? 120 : 320, function (p) { S.reveal = M.ease.outCubic(p); });
        if (!quiet) tween(480, function (p) { S.settle = 0.22 * (1 - M.ease.outCubic(p)); }, function () { S.settle = 0; });
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
    S.settleTw = null; S.camTw = null;
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
    S.dim = 1; S.glint = 0; S.flare = 0; S.gameOn = false; S.settle = 0; S.flex = 0;
    S.game = null; S.cam = null; S.productOn = false;
    if (S.act && S.act.mainGroup) S.act.mainGroup.visible = true;
  }

  function setScene(g) {
    g = g || {};
    var kind = T.yard.kindOf(g);
    S.scene = { kind: kind, biome: g.biome || "", roofed: !!g.roofed, minute: num(g.minute, S.scene.minute) };
    if (S.mounted) applyScene();
    else { S.set = setFor(kind); arrange(); }
  }

  function reducedMotion(on) {
    S.reduced = !!on;
    if (S.reduced && S.particles) S.particles.clear();
    if (S.reduced && S.canvas) S.canvas.style.transform = "";
    wake();
  }

  /* For the harness and the verification notes. Not part of the contract. */
  function debug() {
    var ms = S.stats.ms.slice().sort(function (a, b) { return a - b; });
    var sum = ms.reduce(function (a, b) { return a + b; }, 0);
    var a = S.act, hn = a && a.hideNodes, piece = mainPiece();
    function rng(n) { return n && n.visible ? (n.ranges ? n.ranges[0][1] : -1) : 0; }
    return { frames: S.stats.frames, draws: S.stats.draws, lastDraws: S.stats.lastDraws, rafs: S.stats.rafs, raf: !!S.raf,
             avgMs: ms.length ? sum / ms.length : 0, p95Ms: ms.length ? ms[Math.floor(ms.length * 0.95)] : 0,
             scene: S.set ? S.set.kind : null, method: S.method, spot: a ? a.spot : null,
             shape: a ? (hn ? "hide" : (a.mainGroup ? "piece" : null)) : null,
             plan: a && a.spec ? a.spec.plan : null, size: a && a.hideMesh ? a.hideMesh.size : null,
             color: hn ? hn.out.mat.color.map(function (x) { return +x.toFixed(4); }) : (a && a.roles && a.roles.body ? a.roles.body[0].mat.color.map(function (x) { return +x.toFixed(4); }) : null),
             pattern: hn ? hn.out.mat.pattern : null, underPattern: hn ? hn.under.mat.pattern : null,
             fat: rng(hn && hn.fat), scars: !!(hn && hn.scars), cut: rng(a && a.cutLine), seam: rng(a && a.seam), stamps: rng(a && a.stamps),
             cutTest: a && a.extras.cutTest ? a.extras.cutTest.root.visible : false,
             scale: a && a.scaleNode ? +a.scaleNode.scl[1].toFixed(4) : null, dip: S.dip === undefined ? null : +(+S.dip).toFixed(3),
             liquor: a && a.water ? a.water.mat.color.map(function (x) { return +x.toFixed(4); }) : null,
             piece: piece ? JSON.parse(JSON.stringify(piece)) : null, work: S.work ? JSON.parse(JSON.stringify(S.work)) : null,
             key: S.stats.key, fill: S.stats.fill, phase: S.stats.phase || null, steam: S.stats.steam,
             particles: S.particles ? S.particles.alive() : 0, tweens: S.tweens.length, dull: S.dull,
             hidden: S.hiddenBox || S.hiddenTab, flare: S.flare,
             gpu: S.r ? { buffers: Object.keys(S.r.bufs || {}).length, textures: Object.keys(S.r.texs || {}).length } : null,
             buffer: S.canvas ? [S.canvas.width, S.canvas.height] : null };
  }
  function resetStats() { S.stats.frames = 0; S.stats.draws = 0; S.stats.ms = []; S.stats.rafs = 0; }

  if (READY) S.particles = new K.Particles();

  function noop() {}
  function resolved(v) { return function () { return Promise.resolve(v); }; }
  var NOGAME = { update: noop, hit: noop, miss: noop, end: noop, heat: noop };

  window.TanneryStage = READY ? {
    available: safe("available", available, false),
    mount: function (host) { try { return mount(host); } catch (e) { warn("mount", e); return Promise.resolve(false); } },
    unmount: safe("unmount", unmount),
    setScene: safe("setScene", setScene),
    setTool: function (m) { try { return setTool(m); } catch (e) { warn("setTool", e); return Promise.resolve(false); } },
    setWork: safe("setWork", setWork),
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
    setWork: noop, game: function () { return NOGAME; }, flourish: resolved(false),
    productRect: function () { return window.DOMRect ? new window.DOMRect(0, 0, 0, 0) : null; },
    reducedMotion: noop,
    _debug: function () { return null; }, _resetStats: noop
  };
})();
