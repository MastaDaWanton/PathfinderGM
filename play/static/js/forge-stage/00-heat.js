/* The forge's stage, part 0: heat. Temperature to colour, to light, and back down again.
 *
 * Pure arithmetic with no WebGL and no dependence on the herb kit, so the forge games (lane
 * U3) can read the same bands, cooling and reheat from window.ForgeStageKit.heat even when
 * the stage itself is flat. Classic script; one namespace, window.ForgeStageKit.
 *
 * THE BANDS are the prior-art sweep's §3.1 table (docs/blacksmithing-prior-art.md), the one
 * Wikipedia credits to Chapman, Workshop Technology (1972), named and bounded exactly as
 * printed. tests/test_forge_stage.py parses that table out of the doc and compares it with
 * BANDS row by row, so the two cannot drift apart. Chapman's footnote says the colours hold
 * "when viewed in dull light": a smithy is dull light, so the emissive colours below are
 * what the eye sees in a dim room, not the physical blackbody colour. Ethan Buttimer's
 * Berkeley blackbody renderer (ethanbuttimer.github.io/blackbody.html) does it the
 * physical way, Planck's law to sRGB plus Kirchhoff's weighting of reflected against
 * emitted light; a Planck curve at 600 °C converts to a bright orange that no smith would
 * call "very dark red", because the conversion normalises away how little light there is.
 * So each band carries its own seen colour, with its dimness baked in, and the emissive
 * term is simply ADDED to the lit surface (Kirchhoff's sum, without the spectral maths).
 *
 * THE LIGHT the work throws is a second matter: its colour is the band colour at full
 * strength, and its intensity follows the fourth power of absolute temperature
 * (Stefan-Boltzmann), so a blank at yellow heat lights the anvil and dims fast as it falls
 * through orange (UI plan §7.2: "hot metal is a second light").
 *
 * COOLING is Newton's law (convection, proportional to the gap to the room) plus a
 * radiative T^4 term, because at forging heat radiation dominates and a pure Newton curve
 * cools a yellow blank as slowly as a dull red one. Thin pieces and `narrow_window` metals
 * cool faster (plan §7.2); Steady mode halves it (plan §7.2 accessibility).
 *
 * QUENCH SEVERITY is Grossmann's H, the middle of the ranges the sweep's §3.2 quotes
 * (brine 2.0-5.0, water 0.9-2.0, oil 0.25-0.8), so brine > water > oil > air, and the
 * vapour jacket (Leidenfrost) slows water and oil above about 400 °C while brine's salt
 * breaks it up. The TEMPER colours are §3.3's table, also parsed and compared by the tests.
 *
 * Nothing here is a rules number: the engine never reads heat. These are what the stage
 * shows and what a game may feel like; the server owns every number a build is made of.
 */
(function () {
  "use strict";
  var F = window.ForgeStageKit = window.ForgeStageKit || {};

  var AMBIENT = 20;

  /* Prior art §3.1, Chapman (1972). `rgb` is the seen colour in dull light, linear 0..1,
     dimness included; `hi` null is "and above". */
  var BANDS = [
    { name: "Black red", lo: 426, hi: 593, rgb: [0.16, 0.012, 0.0] },
    { name: "Very dark red", lo: 594, hi: 704, rgb: [0.34, 0.03, 0.004] },
    { name: "Dark red", lo: 705, hi: 814, rgb: [0.56, 0.06, 0.008] },
    { name: "Cherry red", lo: 815, hi: 870, rgb: [0.78, 0.11, 0.02] },
    { name: "Light cherry red", lo: 871, hi: 981, rgb: [0.95, 0.2, 0.04] },
    { name: "Orange", lo: 982, hi: 1092, rgb: [1.0, 0.4, 0.07] },
    { name: "Yellow", lo: 1093, hi: 1258, rgb: [1.0, 0.66, 0.2] },
    { name: "Yellow-white", lo: 1259, hi: 1314, rgb: [1.0, 0.85, 0.5] },
    { name: "White", lo: 1315, hi: null, rgb: [1.0, 0.96, 0.86] }
  ];

  /* Prior art §3.3, the oxide colours on bright steel. `rgb` is the film's colour, linear. */
  var TEMPER = [
    { name: "Faint yellow", c: 176, rgb: [0.78, 0.72, 0.5] },
    { name: "Light straw", c: 205, rgb: [0.8, 0.64, 0.34] },
    { name: "Dark straw", c: 226, rgb: [0.68, 0.48, 0.22] },
    { name: "Brown", c: 260, rgb: [0.46, 0.27, 0.12] },
    { name: "Purple", c: 282, rgb: [0.4, 0.17, 0.36] },
    { name: "Dark blue", c: 310, rgb: [0.12, 0.13, 0.42] },
    { name: "Light blue", c: 337, rgb: [0.3, 0.46, 0.66] },
    { name: "Grey-blue", c: 371, rgb: [0.42, 0.48, 0.54] }
  ];

  /* Grossmann quench severity H, the middle of each quoted range; air is still air. */
  var BATH = { brine: 3.5, water: 1.45, oil: 0.5, air: 0.05 };

  function num(x, d) { x = +x; return isFinite(x) ? x : d; }
  function clamp(x, lo, hi) { return x < lo ? lo : (x > hi ? hi : x); }
  function smooth(e0, e1, x) { var t = clamp((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t); }
  function mix3(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }

  /* One anchor per band at its middle (White at 1,400), interpolated between. */
  var ANCHORS = BANDS.map(function (b) { return [b.hi === null ? 1400 : (b.lo + b.hi) / 2, b.rgb]; });
  function seen(c) {
    if (c <= ANCHORS[0][0]) return ANCHORS[0][1].slice();
    for (var i = 1; i < ANCHORS.length; i++) {
      if (c <= ANCHORS[i][0]) {
        var a = ANCHORS[i - 1], b = ANCHORS[i];
        return mix3(a[1], b[1], (c - a[0]) / (b[0] - a[0]));
      }
    }
    return ANCHORS[ANCHORS.length - 1][1].slice();
  }

  /* The band a temperature sits in, or null below black red (the metal shows its own colour). */
  function band(c) {
    c = num(c, AMBIENT);
    for (var i = BANDS.length - 1; i >= 0; i--) if (c >= BANDS[i].lo) return BANDS[i];
    return null;
  }

  /* Emissive colour for the work's surface. Off below about 450 °C (UI plan §7.2), faded in
     over black red rather than switched on, so a cooling blank goes out, not off. */
  function emit(c) {
    c = num(c, AMBIENT);
    var k = smooth(400, 480, c);
    if (k <= 0) return [0, 0, 0];
    var s = seen(c);
    return [s[0] * k, s[1] * k, s[2] * k];
  }

  /* The point light at the work: band colour at full strength, intensity by T^4. 1,315 °C
     (white) is 2.6; cherry is about 0.75; black red a few hundredths. */
  function light(c) {
    c = num(c, AMBIENT);
    var k = smooth(420, 520, c);
    if (k <= 0) return [0, 0, 0];
    var s = seen(c), m = Math.max(s[0], s[1], s[2]) || 1;
    var tk = (c + 273.15) / 1588.15, i = Math.min(3.2, 2.6 * tk * tk * tk * tk) * k;
    return [s[0] / m * i, s[1] / m * i, s[2] / m * i];
  }

  /* The oxide colour over bright steel `base` at temperature c. Under 150 °C the steel is
     bright; it tints in through faint yellow and holds grey-blue past 371 °C. */
  function temper(c, base) {
    c = num(c, AMBIENT);
    base = base || [0.66, 0.66, 0.68];
    if (c < 150) return base.slice();
    if (c < TEMPER[0].c) return mix3(base, TEMPER[0].rgb, (c - 150) / (TEMPER[0].c - 150));
    for (var i = 1; i < TEMPER.length; i++) {
      if (c <= TEMPER[i].c) return mix3(TEMPER[i - 1].rgb, TEMPER[i].rgb, (c - TEMPER[i - 1].c) / (TEMPER[i].c - TEMPER[i - 1].c));
    }
    return TEMPER[TEMPER.length - 1].rgb.slice();
  }
  function temperBand(c) {
    c = num(c, AMBIENT);
    for (var i = TEMPER.length - 1; i >= 0; i--) if (c >= TEMPER[i].c) return TEMPER[i];
    return null;
  }

  /* One step of cooling in air. o: {rate (multiplier, the server's cool_rate), thin (0..1),
     narrow (bool), steady (bool), ambient}. Substepped, so a long dt from a background tab
     cannot overshoot below the room. At rate 1 a blank at 1,100 °C loses about 39 °C a
     second, at 800 °C about 18, at 500 °C about 8. */
  function cool(c, dt, o) {
    o = o || {};
    c = num(c, AMBIENT);
    dt = Math.max(0, num(dt, 0));
    var amb = num(o.ambient, AMBIENT);
    var k = Math.max(0, num(o.rate, 1)) * (1 + clamp(num(o.thin, 0), 0, 1)) * (o.narrow ? 1.6 : 1) * (o.steady ? 0.5 : 1);
    var ta4 = Math.pow(amb + 273.15, 4);
    var n = Math.max(1, Math.ceil(dt / 0.05)), h = dt / n;
    for (var i = 0; i < n; i++) {
      var tk = c + 273.15;
      var d = (0.0072 * (c - amb) + 8e-12 * (tk * tk * tk * tk - ta4)) * k * h;
      c = Math.max(amb, c - d);
    }
    return c;
  }

  /* Back in the fire: toward the hearth's heat with a 0.7 s time constant, so most of the way
     in a second and all but there in two (UI plan §7.2: "over a second or two"). */
  function reheat(c, hearth, dt, o) {
    o = o || {};
    c = num(c, AMBIENT);
    hearth = num(hearth, 1150);
    var tau = 0.7 * (o.steady ? 1.4 : 1);
    return hearth + (c - hearth) * Math.exp(-Math.max(0, num(dt, 0)) / tau);
  }

  /* Under the bath. Above about 400 °C water and oil wear the vapour jacket, which insulates
     (prior art §3.2), so they cool at a third of their severity there; brine's salt breaks
     the jacket and keeps most of its bite. */
  function quench(c, dt, bath, o) {
    o = o || {};
    c = num(c, AMBIENT);
    var H = BATH[bath] === undefined ? BATH.water : BATH[bath];
    var amb = num(o.ambient, AMBIENT), n = Math.max(1, Math.ceil(Math.max(0, num(dt, 0)) / 0.02));
    var h = Math.max(0, num(dt, 0)) / n;
    for (var i = 0; i < n; i++) {
      var jacket = c > 400 && bath !== "air" ? (bath === "brine" ? 0.8 : 0.33) : 1;
      c = amb + (c - amb) * Math.exp(-H * 1.6 * jacket * h * (o.steady ? 0.5 : 1));
    }
    return c;
  }
  /* What the bath is doing, for steam and bubbles: "jacket" (a quiet skin of vapour, few big
     bubbles), "boil" (the jacket collapsed, violent), "still" (done), or "dry" (in air). */
  function quenchPhase(c, bath) {
    c = num(c, AMBIENT);
    if (bath === "air") return "dry";
    if (c > 400) return bath === "brine" ? "boil" : "jacket";
    if (c > 110) return "boil";
    return "still";
  }

  F.heat = {
    AMBIENT: AMBIENT, BANDS: BANDS, TEMPER: TEMPER, BATH: BATH,
    band: band, emit: emit, light: light, temper: temper, temperBand: temperBand,
    cool: cool, reheat: reheat, quench: quench, quenchPhase: quenchPhase
  };
})();
