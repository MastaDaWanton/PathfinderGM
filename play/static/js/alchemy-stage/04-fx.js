/* The alchemy bench's stage, part 4: the flare, vapour, the calx and the crust.
 *
 * Everything that flies is the herb kit's particle pool (bench-stage/04-particles.js, as it
 * is); this file only decides what and where. Each function takes the adapter's `emit`, which
 * refuses under reduced motion and wakes the loop, so nothing here keeps the stage drawing.
 *
 * What each effect is FOR (UI plan §10: every animation has a reason):
 *   flare   a failed roll whose mishap landed (the owner's Q9.4, UI plan §7.5): a bright
 *           burst at the vessel, sparks, then smoke rising; the light spike, the crack and the
 *           lost liquid are the adapter's, because they are states, not particles;
 *   puff    the reaction gauge overshot in a game: a puff of vapour, no crack, no shake (a
 *           quality signal, never a mishap, UI plan §6.4);
 *   scrape  Sublime's crust scraped off the cool wall: a fall of white grit;
 *   wash    a Transmute stage sealed at its peak: a bloom in that stage's colour;
 *   tick    the glass ticking as it heats or is set down: one small glint;
 *   gilt    tier up, Flawless and a formula found, as every bench.
 * calx(color, whiteness) is not a particle: the charge in the crucible whitens as it calcines,
 * and this is the colour it whitens toward (a lime-white ash, not paper white).
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var A = window.AlchemyStageKit = window.AlchemyStageKit || {};
  var M = K.math, LQ = A.liquid;
  if (!M || !LQ) return;

  function flare(emit, at, col) {
    var c = LQ.bright(col || [1, 0.6, 0.2]);
    emit("glint", at, { count: 4, col: [1, 0.92, 0.7], size: 2.2, spread: 0.02 });
    emit("spark", at, { count: 26, col: M.lerp3(c, [1, 0.62, 0.25], 0.5), speed: 1.1, spread: 0.04 });
    emit("ember", at, { count: 8, col: [1, 0.55, 0.2], spread: 0.06 });
    emit("smoke", [at[0], at[1] + 0.05, at[2]], { count: 6, spread: 0.05, size: 0.8, a: 0.32 });
  }
  function puff(emit, at, col) {
    emit("steam", at, { count: 4, col: M.lerp3(col || LQ.WATER, [0.9, 0.9, 0.88], 0.6), spread: 0.03, size: 0.7, a: 0.2 });
  }
  function scrape(emit, at) {
    emit("grit", at, { count: 8, col: [0.9, 0.9, 0.86], speed: 0.4, spread: 0.03 });
  }
  function wash(emit, at, col) {
    emit("glint", at, { count: 3, col: LQ.bright(col), size: 1.2, spread: 0.03 });
    emit("ember", at, { count: 5, col: LQ.bright(col), spread: 0.05, speed: 0.6, life: 0.9 });
  }
  function tick(emit, at) {
    emit("glint", at, { count: 1, col: [0.95, 0.95, 1], size: 0.4, spread: 0.01 });
  }
  function gilt(emit, at, n) { emit("gilt", at, { count: n || 14, spread: 0.06 }); }

  var CALX = [0.9, 0.88, 0.82];
  function calx(col, whiteness) { return M.lerp3(col || [0.5, 0.45, 0.4], CALX, Math.max(0, Math.min(1, +whiteness || 0))); }

  A.fx = { flare: flare, puff: puff, scrape: scrape, wash: wash, tick: tick, gilt: gilt, calx: calx };
})();
