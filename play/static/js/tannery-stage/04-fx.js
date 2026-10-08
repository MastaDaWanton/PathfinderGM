/* The tannery's stage, part 4: what flies off the work.
 *
 * Everything that flies is the herb kit's particle pool (bench-stage/04-particles.js, as it
 * is); this file only decides what and where. Each function takes the adapter's `emit`, which
 * refuses under reduced motion and wakes the loop, so nothing here keeps the stage drawing.
 *
 * What each is FOR (UI plan §10: every animation has a reason):
 *   curl     a good stroke on the beam: flesh and fat curl away from the knife (Flense), a
 *            shaving off the edge (Cut), a smear of oil worked in (Curry)
 *   nick     a miss: a dull scrape, a little dust, nothing else (the hint is the strip's)
 *   grains   salt thrown on the flesh side (Salt)
 *   steam    off the kettle while the piece is in it (Harden), off the pot while it is hot
 *   ripple   the liquor moving as the hide goes down or the strength steps up (Tan)
 *   bleed    the dye taking under the brush (Dye)
 *   stamp    the stamp striking cased leather: a puff and a glint at the face (Tool)
 *   pull     a stitch drawn tight: a tiny glint on the thread (Stitch)
 *   gilt     tier up, Flawless and a landed product, as every bench
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var T = window.TanneryStageKit = window.TanneryStageKit || {};
  var M = K.math;
  if (!M) return;

  var FAT = [0.93, 0.85, 0.7];
  function curl(emit, at, col) {
    emit("grit", at, { count: 5, col: col || FAT, speed: 0.6, spread: 0.03, size: 1.3 });
  }
  function nick(emit, at) {
    emit("dust", at, { count: 2, col: [0.55, 0.48, 0.4], size: 0.5, spread: 0.02 });
  }
  function grains(emit, at) {
    emit("grit", at, { count: 10, col: [0.95, 0.95, 0.93], speed: 0.35, spread: 0.08, size: 0.6 });
  }
  function steam(emit, at, k) {
    // Wisps, not a cloud: at four puffs of size 1.4 every 90 ms the first capture hid the
    // kettle and the piece in it under one white blob.
    var n = Math.max(1, Math.round(1 + 1.5 * (k === undefined ? 1 : k)));
    emit("steam", at, { count: n, spread: 0.14, size: 0.9, a: 0.06 + 0.07 * (k || 0) });
  }
  function ripple(emit, at, col) {
    emit("splash", at, { count: 6, col: col || [0.3, 0.2, 0.1], speed: 0.35, spread: 0.1 });
  }
  function bleed(emit, at, col) {
    emit("dust", at, { count: 2, col: col || [0.4, 0.2, 0.15], size: 0.25, spread: 0.03, a: 0.5 });
  }
  function stamp(emit, at) {
    emit("dust", at, { count: 2, col: [0.6, 0.52, 0.42], size: 0.35, spread: 0.01 });
    emit("glint", at, { count: 1, col: [1, 0.92, 0.75], size: 0.4, spread: 0.005 });
  }
  function pull(emit, at) {
    emit("glint", at, { count: 1, col: [1, 0.95, 0.85], size: 0.3, spread: 0.005 });
  }
  function gilt(emit, at, n) { emit("gilt", at, { count: n || 14, spread: 0.08 }); }

  T.fx = { curl: curl, nick: nick, grains: grains, steam: steam, ripple: ripple, bleed: bleed,
           stamp: stamp, pull: pull, gilt: gilt };
})();
