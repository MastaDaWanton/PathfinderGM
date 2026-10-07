/* The alchemy bench's stage, part 2: the liquid model.
 *
 * UI plan §7.3-7.4. The liquid is three numbers the SERVER authors per step (the mix colour,
 * computed from the inputs' `color`s weighted by amount; the level, 0..1 of the vessel; the
 * turbidity, cloudy 1 to clear 0) and the stage only draws them, or eases between two it was
 * sent. "The page never computes a number" holds: these are presentation values, and the one
 * colour table here, Transmute's four stages, is the Great Work's own (black, white, yellow,
 * red: nigredo, albedo, citrinitas, rubedo; art §5), named in words on the strip as well.
 *
 * A state is {color: [r, g, b] 0..1 or "#rrggbb", level: 0..1, turbidity: 0..1}. Without a
 * colour (the server sends null when no input carries one) the liquid is a clear, pale tint:
 * water, which is never a claim about what the mix is.
 *
 * The rest is what flies (bench-stage/04-particles.js, as it is): bubbles, the pour, a drop,
 * the fizz. Each takes the adapter's `emit`, which refuses under reduced motion and wakes the
 * loop, so nothing here can keep the stage drawing on its own.
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var A = window.AlchemyStageKit = window.AlchemyStageKit || {};
  var M = K.math;
  if (!M) return;

  var WATER = [0.72, 0.78, 0.8];

  function num(x, d) { x = +x; return isFinite(x) ? x : d; }
  function clamp01(x) { x = +x; return isFinite(x) ? Math.max(0, Math.min(1, x)) : 0; }

  function parse(c, d) {
    if (Array.isArray(c) && c.length >= 3) {
      var big = c[0] > 1 || c[1] > 1 || c[2] > 1, k = big ? 1 / 255 : 1;
      return [clamp01(num(c[0], 0) * k), clamp01(num(c[1], 0) * k), clamp01(num(c[2], 0) * k)];
    }
    if (typeof c === "string") {
      var m = /^#?([0-9a-f]{6})$/i.exec(c.trim());
      if (m) {
        var v = parseInt(m[1], 16);
        return [(v >> 16 & 255) / 255, (v >> 8 & 255) / 255, (v & 255) / 255];
      }
    }
    return d === undefined ? null : d;
  }
  /* sRGB swatch to the linear-ish base the house shader lights (it does no gamma): the
     forge's and the circle's rule. */
  function toBase(c) { return [Math.pow(c[0], 1.6), Math.pow(c[1], 1.6), Math.pow(c[2], 1.6)]; }

  /* A clean state from whatever came: missing parts keep `prev`'s. */
  function state(s, prev) {
    s = s && typeof s === "object" ? s : {};
    prev = prev || { color: null, level: 0, turbidity: 0 };
    var col = s.color === undefined ? prev.color : parse(s.color, null);
    return { color: col, level: s.level === undefined ? prev.level : clamp01(s.level),
             turbidity: s.turbidity === undefined ? prev.turbidity : clamp01(s.turbidity) };
  }
  function mix(a, b, t) {
    t = clamp01(t);
    var ca = a.color || WATER, cb = b.color || WATER;
    return { color: (a.color || b.color) ? M.lerp3(ca, cb, t) : null,
             level: a.level + (b.level - a.level) * t, turbidity: a.turbidity + (b.turbidity - a.turbidity) * t };
  }

  /* Paint a liquid node (00-glass.js) with a state. `dull` (0..1) greys and darkens it (a
     failure); `glow` adds its own light (the Great Work's red, a hot calx). */
  function paint(n, s, o) {
    if (!n || !n.mat) return;
    o = o || {};
    var c = s.color || WATER, body = toBase(c);
    if (o.dull) body = M.lerp3(body, M.scale([0.32, 0.31, 0.3], 0.6 + 0.4 * (body[0] + body[1] + body[2]) / 3), clamp01(o.dull) * 0.7);
    n.mat.color = body;
    // The top is the body lifted toward white: a lit surface reads lighter than the depth
    // under it, and the eye reads the line between them as the level.
    n.mat.surf = M.lerp3(body, [1, 1, 1], 0.22);
    var clear = !s.color;
    n.mat.turbid = clamp01(s.turbidity + (o.dull ? 0.4 * o.dull : 0));
    n.mat.alpha = clear ? 0.28 : 0.55;
    n.mat.emit = o.glow ? o.glow.slice() : [0, 0, 0];
    if (n.liquid) n.liquid.level = clamp01(s.level);
  }

  /* --- Transmute's four stages -------------------------------------------------------------- */
  var STAGES = ["nigredo", "albedo", "citrinitas", "rubedo"];
  var STAGE_COLOR = { nigredo: [0.06, 0.055, 0.06], albedo: [0.9, 0.9, 0.88], citrinitas: [0.92, 0.74, 0.18],
                      rubedo: [0.72, 0.08, 0.06] };
  /* The colour at a position along the work: 0 is nigredo, 3 rubedo, fractions between. */
  function stageColor(x) {
    if (typeof x === "string") { var i = STAGES.indexOf(x.toLowerCase()); x = i < 0 ? 0 : i; }
    x = Math.max(0, Math.min(STAGES.length - 1, num(x, 0)));
    var lo = Math.floor(x), hi = Math.min(STAGES.length - 1, lo + 1);
    return M.lerp3(STAGE_COLOR[STAGES[lo]], STAGE_COLOR[STAGES[hi]], x - lo);
  }

  /* --- what flies ----------------------------------------------------------------------------- */
  function bright(c) {
    var m = Math.max(c[0], c[1], c[2], 0.05), k = Math.min(2.5, 0.9 / m);
    return [Math.min(1, c[0] * k), Math.min(1, c[1] * k), Math.min(1, c[2] * k)];
  }

  /* Bubbles from the bottom of the liquid: small pale points rising and catching the light
     (the herb kit's ember, which rises and shrinks; its steam GROWS by half a unit a second,
     and as a bubble it ballooned to the size of the flask). Short-lived, so they die near the
     top. k: 0..1, the churn. */
  function bubbles(emit, at, r, depth, k, col) {
    var n = Math.random() < k * 0.9 ? 1 + Math.round(k * 2) : 0;
    var c = M.lerp3(col || WATER, [1, 1, 1], 0.55);
    for (var i = 0; i < n; i++) {
      var a = Math.random() * Math.PI * 2, d = Math.random() * r * 0.6;
      emit("ember", [at[0] + Math.cos(a) * d, at[1] + 0.006, at[2] + Math.sin(a) * d],
           { count: 1, col: c, size: 0.35 + 0.35 * k, a: 0.4, speed: 0.5, spread: 0.002, life: Math.max(0.2, depth * 3) });
    }
  }
  /* Vapour off the top: the herb kit's steam, in the liquid's colour washed pale. */
  function vapour(emit, at, k, col) {
    if (k <= 0 || Math.random() > 0.25 + 0.6 * k) return;
    emit("steam", at, { count: 1, col: M.lerp3(col || WATER, [0.9, 0.9, 0.88], 0.7), spread: 0.02, size: 0.5 + 0.6 * k, a: 0.08 + 0.12 * k });
  }
  /* A stream of drops from a lip to a mouth (Bottle's pour, Filter's stem). */
  function pour(emit, from, to, col, k) {
    var c = bright(col || WATER);
    emit("drop", from, { count: 1 + Math.round(2 * k), col: c, dir: [to[0] - from[0], -0.3, to[2] - from[2]], speed: 0.6,
                         spread: 0.004, size: 0.5, life: 0.35 });
  }
  /* One drop: React's dropper, the alembic's beak, the funnel's stem. */
  function drop(emit, at, col) {
    emit("drop", at, { count: 1, col: bright(col || WATER), spread: 0.001, size: 0.45, life: 0.32 });
  }
  /* A drop blooming into the liquid: a soft flash of its colour at the surface. */
  function bloom(emit, at, col) {
    emit("glint", at, { count: 1, col: bright(col || WATER), spread: 0.02, size: 0.2, a: 0.5 });
  }
  /* The fizz of too hard a stir or too much at once: a spit of drops and a puff. */
  function fizz(emit, at, col) {
    emit("splash", at, { count: 6, col: bright(col || WATER), speed: 0.5, up: 1.2, size: 0.5 });
    emit("steam", at, { count: 2, col: [0.85, 0.85, 0.82], spread: 0.03, size: 0.5, a: 0.18 });
  }

  A.liquid = { WATER: WATER, parse: parse, toBase: toBase, state: state, mix: mix, paint: paint,
               STAGES: STAGES, STAGE_COLOR: STAGE_COLOR, stageColor: stageColor, bright: bright,
               bubbles: bubbles, vapour: vapour, pour: pour, drop: drop, bloom: bloom, fizz: fizz };
})();
