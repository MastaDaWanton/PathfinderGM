/* The enchanting bench's stage, part 4: motes, the stream, smoke and the chalk's dust.
 *
 * Everything that flies is the herb kit's particle pool (bench-stage/04-particles.js, reused as
 * is) in the circle's colours; this file only decides WHAT to emit and where. Each function
 * takes `emit(kind, pos, opts)`, the adapter's emitter, which refuses under reduced motion and
 * wakes the frame loop, so nothing here can keep the stage drawing on its own.
 *
 * What each effect is FOR (UI plan §10: every animation has a reason):
 *   motes   an essence answering: a few slow motes of its colour rise from its phial while a
 *           game is live (Attune, Bind), never while idle;
 *   stream  a good press at Bind: the essence's light pours from the ring into the vessel;
 *   scuff   a wrong pick at Prepare, or a miss at Unbind: a puff of chalk dust;
 *   mist    a sigil unpicked: its essence rises from it as a thin mist;
 *   snuff   a candle guttering out (Flawed): a thread of smoke from the wick;
 *   gilt    tier up and Flawless, as both other benches.
 */
(function () {
  "use strict";
  var E = window.EnchantStageKit = window.EnchantStageKit || {};

  function bright(c) {
    // An essence colour lifted toward its own brightest channel, so a dark essence (the dead,
    // shadow) still shows as a coloured light on the additive pass rather than as nothing.
    var m = Math.max(c[0], c[1], c[2], 0.05), k = Math.min(2.5, 0.9 / m);
    return [Math.min(1, c[0] * k), Math.min(1, c[1] * k), Math.min(1, c[2] * k)];
  }

  function motes(emit, pos, col, n) {
    emit("ember", pos, { count: n || 1, col: bright(col), spread: 0.02, speed: 0.6, size: 0.9, life: 1.4 });
  }

  /* From a point on the ring toward the vessel: motes thrown along the line, so the eye follows
     the light into the work. */
  function stream(emit, from, to, col, strength) {
    var s = Math.max(0.2, Math.min(1, +strength || 0));
    var d = [to[0] - from[0], 0.35, to[2] - from[2]];
    emit("ember", from, { count: Math.round(6 + 14 * s), col: bright(col), dir: d, speed: 2.6, spread: 0.03, size: 1.1, life: 0.5 });
    emit("glint", to, { count: 1, col: bright(col) });
  }

  function scuff(emit, pos) {
    emit("dust", pos, { count: 4, col: [0.8, 0.78, 0.72], spread: 0.05, up: 0.15, size: 0.6 });
  }

  function mist(emit, pos, col) {
    emit("smoke", pos, { count: 3, col: bright(col), spread: 0.03, size: 0.5, a: 0.22 });
  }

  function snuff(emit, pos) {
    emit("smoke", pos, { count: 4, col: [0.5, 0.48, 0.46], spread: 0.01, size: 0.35, a: 0.3 });
  }

  function gilt(emit, pos, n) {
    emit("gilt", pos, { count: n || 14, spread: 0.08 });
  }

  E.fx = { bright: bright, motes: motes, stream: stream, scuff: scuff, mist: mist, snuff: snuff, gilt: gilt };
})();
