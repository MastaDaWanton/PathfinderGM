/* The forge's stage, part 4: sparks, steam, bubbles, slag and the temper colour run.
 *
 * Everything that flies is the herb kit's particle pool (bench-stage/04-particles.js, reused
 * as is) with forge colours and counts; this file only decides WHAT to emit and where. Each
 * function takes `emit(kind, pos, opts)`, the adapter's emitter, which already refuses under
 * reduced motion and wakes the frame loop, so nothing here can keep the stage drawing.
 *
 * What each effect is FOR (UI plan §10, every animation has a reason):
 *   strike  a hit in band: sparks the colour of the metal's heat, more the hotter it is and
 *           the harder the blow; a cold strike throws a few dull flakes (a dead thud);
 *   steam   the quench: a plume, heaviest when the jacket collapses;
 *   bubble  the vapour jacket: a few large slow bubbles while it holds, a rush when it boils;
 *   slag    Smelt's tap: dark orange gobbets that fall;
 *   grind   Hone: a fan of fine sparks off the wheel;
 *   embers  the hearth breathing while a game is live (never while idle);
 *   gilt    tier up and Flawless.
 *
 * The TEMPER RUN is not particles: it is colour along the blade, one value per run of the
 * head's mesh (02-families.js cuts a blade into eight). The heat is put in at the base, so
 * the oxide colours rise from the ricasso toward the point as the temperature climbs: straw,
 * brown, purple, blue (prior art §3.3; UI plan §9, "the oxide colour runs along the cleaned
 * steel").
 */
(function () {
  "use strict";
  var F = window.ForgeStageKit = window.ForgeStageKit || {};
  var H = F.heat;
  if (!H) return;

  function heatCol(c) {
    var l = H.light(c), m = Math.max(l[0], l[1], l[2]);
    return m > 0 ? [l[0] / m, l[1] / m, l[2] / m] : [0.55, 0.5, 0.45];
  }

  function strike(emit, pos, strength, c) {
    var s = Math.max(0, Math.min(1, +strength || 0)), hot = c >= 700;
    if (!hot) {
      emit("grit", pos, { count: 3, col: [0.3, 0.28, 0.26], speed: 0.6 });
      return;
    }
    var k = Math.min(1.6, (c - 600) / 500);
    emit("spark", pos, { count: Math.round(10 + 28 * s * k), col: heatCol(c + 120), speed: 0.8 + 0.6 * s, spread: 0.06 });
    emit("ember", pos, { count: Math.round(3 + 4 * s), col: heatCol(c), spread: 0.08 });
  }

  function steam(emit, pos, k) {
    k = Math.max(0, Math.min(1.5, +k || 0));
    if (k <= 0) return;
    emit("steam", pos, { count: Math.round(1 + 8 * k), spread: 0.14, size: 1 + 0.6 * k, a: 0.1 + 0.08 * k });
  }

  function bubble(emit, pos, r, phase) {
    var n = phase === "boil" ? 6 : (phase === "jacket" ? 1 : 0);
    for (var i = 0; i < n; i++) {
      var a = Math.random() * Math.PI * 2, d = Math.random() * r * 0.8;
      emit("ember", [pos[0] + Math.cos(a) * d, pos[1] + 0.004, pos[2] + Math.sin(a) * d],
           { count: 1, col: [0.55, 0.62, 0.62], size: phase === "jacket" ? 1.4 : 0.8, speed: 0.4, life: 0.35, a: 0.5 });
    }
  }

  function slag(emit, pos) {
    emit("splash", pos, { count: 8, col: [0.75, 0.3, 0.06], speed: 0.8, up: 0.6 });
    emit("spark", pos, { count: 6, col: [1.0, 0.5, 0.15], speed: 0.6 });
    emit("smoke", pos, { count: 2, spread: 0.06 });
  }

  function grind(emit, pos, dir) {
    emit("spark", pos, { count: 7, col: [1.0, 0.78, 0.45], speed: 1.1, dir: dir || [0.3, 0.4, 0.8], spread: 0.01 });
  }

  function embers(emit, pos, k) {
    if (Math.random() < 0.25 + 0.5 * k) emit("ember", pos, { count: 1, spread: 0.15 });
  }

  function gilt(emit, pos, n) { emit("gilt", pos, { count: n || 14, speed: 0.7 }); }

  /* The oxide colour on each of n runs along a blade, heat put in at the base: the base sits
     at `c`, the point `spread` degrees cooler, so the band edges travel toward the point as c
     climbs. Below 150 °C every run is the bright `base`. */
  function temperRun(c, n, base, spread) {
    var out = [], sp = spread === undefined ? 150 : spread;
    for (var i = 0; i < n; i++) out.push(H.temper(c - sp * (n > 1 ? i / (n - 1) : 0), base));
    return out;
  }

  /* Heat along the work: the point loses heat first. */
  function heatRun(c, n) {
    var out = [];
    for (var i = 0; i < n; i++) out.push(c - 45 * (n > 1 ? i / (n - 1) : 0) * Math.min(1, Math.max(0, (c - 300) / 600)));
    return out;
  }

  F.fx = { strike: strike, steam: steam, bubble: bubble, slag: slag, grind: grind, embers: embers,
           gilt: gilt, temperRun: temperRun, heatRun: heatRun, heatCol: heatCol };
})();
