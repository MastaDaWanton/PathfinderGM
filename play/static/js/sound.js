/* The app's sound: `window.Sound` (docs/herbalism-contracts.md §5.3, revamp plan §11).
 *
 *   Sound.play(name, {volume, rate, delay})   one-shot; unknown names are a silent no-op
 *   Sound.loop(name)                          -> {stop()}, for the ambience beds
 *   Sound.unlock()                            resume the context on a user gesture
 *
 * EVERY SOUND IS SYNTHESISED. There are no sample files in this batch and the app
 * downloads nothing (contracts §0): each sound below is a few Web Audio nodes (noise
 * through a filter, an oscillator with a pitch glide, a shaped gain envelope) built at
 * the moment it plays. The same approach as sfxr/jsfxr and ZzFX, which make a whole game's
 * effects from oscillators, noise and envelopes; and the same approach dice3d.js already
 * took for its clack ("a dozen lines of Web Audio and no asset in the installer").
 *
 * NAMES are `<bus>.<what>[.<which>]`; the first segment picks the bus. Buses (ui, dice,
 * bench, ambience, combat, verdict) feed one master gain, then a gentle limiter, then the
 * speakers. Each bus gain follows its PGMPrefs volume live, so a Settings slider moved in
 * another window changes this one's mix too. `verdict` has no slider of its own in the
 * contract's key list; it rides on `sound.dice`, because a verdict only ever follows a die.
 *
 * REPEATS. These are heard thousands of times. Each sound has two to four takes (`n`,
 * the variant index `c.v` changes its parameters) and the same take never plays twice in
 * a row, and every play is pitched within ±5%: a dozen identical samples in a row is the
 * machine-gun effect, the most audible way canned audio gives itself away. Levels err
 * quiet and envelopes err short for the same reason.
 *
 * AUTOPLAY. Browsers (and Electron, which is Chromium) start an AudioContext suspended
 * until the page has had a user gesture, and `resume()` only works inside or after one
 * (Chrome's autoplay policy, developer.chrome.com/blog/autoplay). So the context is made
 * lazily, a one-time pointerdown/keydown listener calls `unlock()`, and a sound asked for
 * before any gesture is dropped rather than queued: a queued sound would fire late, all at
 * once, on the first click.
 *
 * NOTHING HERE THROWS. Every public call is wrapped; a page whose audio fails must play
 * on in silence. No third-party code, as everywhere in play/static/js.
 */
(function () {
  "use strict";

  var BUSES = ["ui", "dice", "bench", "ambience", "combat", "verdict"];
  var BUS_PREF = {
    ui: "sound.ui", dice: "sound.dice", bench: "sound.bench",
    ambience: "sound.ambience", combat: "sound.combat", verdict: "sound.dice",
  };
  var BUS_DEFAULT = { ui: 0.6, dice: 0.8, bench: 0.8, ambience: 0.4, combat: 0.7, verdict: 0.8 };
  // Simultaneous one-shots allowed before new ones are dropped. A grind game at full tilt
  // plus a verdict plus ambience events is well under this; a runaway caller is not.
  var MAX_VOICES = 28;

  var ctx = null, failed = false, master = null, limiter = null;
  var buses = {}, buffers = {}, lastTake = {}, voices = 0, gestured = false;

  /* --- preferences ------------------------------------------------------------------ */

  function pref(key, dflt) {
    try {
      var p = window.PGMPrefs;
      if (!p || typeof p.get !== "function") return dflt;
      var v = p.get(key);
      return v === undefined || v === null ? dflt : v;
    } catch (e) { return dflt; }
  }
  function masterLevel() {
    return pref("sound.mute", false) ? 0 : clamp(Number(pref("sound.master", 0.8)), 0, 1);
  }
  function busLevel(b) {
    return clamp(Number(pref(BUS_PREF[b], BUS_DEFAULT[b])), 0, 1);
  }
  function clamp(n, lo, hi) { return isFinite(n) ? Math.max(lo, Math.min(hi, n)) : lo; }

  function follow(node, level) {
    try { node.gain.setTargetAtTime(level, ctx.currentTime, 0.03); }
    catch (e) { try { node.gain.value = level; } catch (e2) { /* */ } }
  }

  function bindPrefs() {
    var p = window.PGMPrefs;
    if (!p || typeof p.on !== "function") return;
    var redoMaster = function () { if (master) follow(master, masterLevel()); };
    p.on("sound.master", redoMaster);
    p.on("sound.mute", redoMaster);
    BUSES.forEach(function (b) {
      p.on(BUS_PREF[b], function () { if (buses[b]) follow(buses[b], busLevel(b)); });
    });
  }

  /* --- the context ------------------------------------------------------------------ */

  function ensure() {
    if (ctx || failed) return ctx;
    try {
      var C = window.AudioContext || window.webkitAudioContext;
      if (!C) { failed = true; return null; }
      ctx = new C();
      // A soft limiter on the master: a crit, a verdict and a flourish landing together
      // must not clip. Threshold high enough that a single sound never touches it.
      limiter = ctx.createDynamicsCompressor();
      limiter.threshold.value = -10;
      limiter.knee.value = 8;
      limiter.ratio.value = 6;
      limiter.attack.value = 0.003;
      limiter.release.value = 0.2;
      master = ctx.createGain();
      master.gain.value = masterLevel();
      master.connect(limiter);
      limiter.connect(ctx.destination);
      BUSES.forEach(function (b) {
        var g = ctx.createGain();
        g.gain.value = busLevel(b);
        g.connect(master);
        buses[b] = g;
      });
      bindPrefs();
    } catch (e) {
      ctx = null; failed = true;
    }
    return ctx;
  }

  function hasGesture() {
    if (gestured) return true;
    try {
      return !!(navigator.userActivation && navigator.userActivation.hasBeenActive);
    } catch (e) { return false; }
  }

  function unlock() {
    try {
      gestured = true;
      var x = ensure();
      if (x && x.state !== "running" && typeof x.resume === "function") {
        var p = x.resume();
        if (p && typeof p.catch === "function") p.catch(function () { /* next gesture */ });
      }
    } catch (e) { /* silence is the fallback */ }
  }

  // The one-time gesture listener. It stays until the context is actually running,
  // because a resume() refused once (a gesture the browser did not count) must be able
  // to succeed on the next one.
  (function installUnlock() {
    var kinds = ["pointerdown", "keydown", "touchstart"];
    function onGesture() {
      unlock();
      try {
        if (ctx && ctx.state === "running") {
          kinds.forEach(function (k) { window.removeEventListener(k, onGesture, true); });
        }
      } catch (e) { /* keep listening */ }
    }
    try {
      kinds.forEach(function (k) {
        window.addEventListener(k, onGesture, { capture: true, passive: true });
      });
    } catch (e) { /* no events: unlock() can still be called by hand */ }
  })();

  /* --- raw material: noise ---------------------------------------------------------- */

  // White, pink and brown noise, each made once per context. Pink by Paul Kellet's
  // economy filter; brown by integrating white with a leak. Two to four seconds each, and
  // every play starts at a random offset, so no two bursts are the same grains.
  function buf(kind) {
    if (buffers[kind]) return buffers[kind];
    var sr = ctx.sampleRate, secs = kind === "white" ? 2 : 4;
    var b = ctx.createBuffer(1, (sr * secs) | 0, sr);
    var d = b.getChannelData(0), i, w;
    if (kind === "pink") {
      var b0 = 0, b1 = 0, b2 = 0;
      for (i = 0; i < d.length; i++) {
        w = Math.random() * 2 - 1;
        b0 = 0.99765 * b0 + w * 0.0990460;
        b1 = 0.96300 * b1 + w * 0.2965164;
        b2 = 0.57000 * b2 + w * 1.0526913;
        d[i] = (b0 + b1 + b2 + w * 0.1848) * 0.2;
      }
    } else if (kind === "brown") {
      var last = 0;
      for (i = 0; i < d.length; i++) {
        w = Math.random() * 2 - 1;
        last = (last + 0.02 * w) / 1.02;
        d[i] = last * 3.5;
      }
    } else {
      for (i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    }
    buffers[kind] = b;
    return b;
  }

  function hz(f) { return clamp(f, 20, ctx.sampleRate * 0.45); }

  /* --- building blocks -------------------------------------------------------------- *
   * Each takes the play context `c` ({x, out, t, p, v}) and an options object, schedules
   * its nodes on the audio clock at `c.t + o.at`, and returns the time it ends. `c.p` is
   * the pitch multiplier (the ±5% jitter and the caller's `rate`). */

  // A gain envelope: silence, a ramp to `peak` in `a`, an optional hold, a decay of `d`.
  // Exponential ramps from 0.0001 rather than linear from 0: a linear ramp from silence
  // clicks at the start, and an exponential one cannot reach zero.
  function env(g, t, peak, a, d, hold) {
    var top = Math.max(0.0002, peak);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(top, t + a);
    if (hold) g.gain.setValueAtTime(top, t + a + hold);
    g.gain.exponentialRampToValueAtTime(0.0001, t + a + (hold || 0) + d);
    return t + a + (hold || 0) + d;
  }

  // Filtered noise: the scrape, the hiss, the crunch, the thump's body.
  function noise(c, o) {
    var x = c.x, t = c.t + (o.at || 0);
    var a = o.a || 0.004, d = o.d || 0.05;
    var s = x.createBufferSource();
    s.buffer = buf(o.src || "white");
    var f = x.createBiquadFilter();
    f.type = o.type || "bandpass";
    f.frequency.setValueAtTime(hz(o.f * c.p), t);
    if (o.f2) f.frequency.exponentialRampToValueAtTime(hz(o.f2 * c.p), t + a + (o.hold || 0) + d);
    f.Q.value = o.q == null ? 1 : o.q;
    var g = x.createGain();
    var end = env(g, t, o.peak, a, d, o.hold);
    s.connect(f); f.connect(g); g.connect(o.dest || c.out);
    var span = s.buffer.duration - (end - t) - 0.05;
    s.start(t, span > 0 ? Math.random() * span : 0);
    s.stop(end + 0.03);
    return end;
  }

  // An oscillator with a glide: the body under a knock, a blip, a chime's partial.
  function tone(c, o) {
    var x = c.x, t = c.t + (o.at || 0);
    var a = o.a || 0.004, d = o.d || 0.1;
    var osc = x.createOscillator();
    osc.type = o.type || "sine";
    osc.frequency.setValueAtTime(hz(o.f * c.p), t);
    if (o.f2) osc.frequency.exponentialRampToValueAtTime(hz(o.f2 * c.p), t + (o.glide || a + d));
    var g = x.createGain();
    var end = env(g, t, o.peak, a, d, o.hold);
    if (o.lp) {
      var f = x.createBiquadFilter();
      f.type = "lowpass"; f.frequency.value = hz(o.lp * c.p); f.Q.value = 0.7;
      osc.connect(f); f.connect(g);
    } else {
      osc.connect(g);
    }
    g.connect(o.dest || c.out);
    osc.start(t);
    osc.stop(end + 0.03);
    return end;
  }

  // A struck bell or glass: a fundamental and two inharmonic partials (2.76 and 5.4, the
  // ratios of a free bar), the upper ones quieter and shorter, as real metal rings.
  function bell(c, o) {
    var at = o.at || 0, f = o.f, p = o.peak, d = o.d || 0.6;
    tone(c, { at: at, f: f, peak: p, a: 0.002, d: d });
    tone(c, { at: at, f: f * 2.76, peak: p * 0.32, a: 0.002, d: d * 0.55 });
    return tone(c, { at: at, f: f * 5.4, peak: p * 0.12, a: 0.002, d: d * 0.3 });
  }

  // A scatter of tiny clicks: crackle, rattle, grit, a page riffle. `n` grains over
  // `span` seconds, each a few milliseconds of band-passed noise, fading as they go.
  function grains(c, o) {
    var end = c.t, at0 = o.at || 0;
    for (var i = 0; i < o.n; i++) {
      var k = o.n > 1 ? i / (o.n - 1) : 0;
      var when = at0 + o.span * (o.even ? k : Math.pow(Math.random(), o.bunch || 1));
      var fade = o.fade === false ? 1 : 1 - k * 0.6;
      end = Math.max(end, noise(c, {
        at: when, f: o.f * (0.8 + Math.random() * 0.4), q: o.q == null ? 2 : o.q,
        type: o.type || "bandpass", peak: o.peak * fade * (0.6 + Math.random() * 0.4),
        a: 0.001, d: o.d || 0.012,
      }));
    }
    return end;
  }

  // A wooden or stone knock: a short thump of low noise and a falling body tone.
  function knock(c, o) {
    noise(c, { at: o.at, type: "lowpass", f: o.lp || 900, q: 0.7, peak: o.peak * 0.7,
               a: 0.002, d: o.d || 0.06 });
    return tone(c, { at: o.at, type: o.wave || "triangle", f: o.f, f2: o.f * (o.drop || 0.7),
                     peak: o.peak, a: 0.003, d: (o.d || 0.06) * 1.6 });
  }

  // A liquid drop: a sine whose pitch leaps up as the bubble closes. This is how a real
  // drop sounds (a resonating bubble shrinking), and why a falling blip reads as a laser.
  function drop(c, o) {
    return tone(c, { at: o.at, f: o.f, f2: o.f * (o.rise || 2.4), glide: o.d || 0.05,
                     peak: o.peak, a: 0.002, d: o.d || 0.05 });
  }

  /* --- the bank --------------------------------------------------------------------- */

  var SOUNDS = {};
  function def(name, takes, fn) { SOUNDS[name] = { n: takes, fn: fn }; }
  // Pick the take's own value from a list: `c.k([a, b, c])` is take v's entry.
  function k(c, list) { return list[c.v % list.length]; }

  // --- ui: quiet, short, papery. Heard on every panel.
  def("ui.click", 3, function (c) {
    noise(c, { f: k(c, [3200, 3800, 2900]), q: 3, peak: 0.07, d: 0.018 });
    return tone(c, { f: k(c, [1650, 1900, 1500]), peak: 0.025, d: 0.02 });
  });
  def("ui.open", 3, function (c) {
    noise(c, { src: "pink", f: 600, f2: k(c, [1900, 2200, 1700]), q: 1.2, peak: 0.07,
               a: 0.04, d: 0.16 });
    return tone(c, { at: 0.02, f: k(c, [520, 494, 554]), f2: k(c, [780, 740, 830]),
                     peak: 0.02, a: 0.02, d: 0.14 });
  });
  def("ui.close", 3, function (c) {
    noise(c, { src: "pink", f: k(c, [1800, 2100, 1600]), f2: 520, q: 1.2, peak: 0.06,
               a: 0.02, d: 0.15 });
    return knock(c, { at: 0.12, f: k(c, [260, 240, 280]), peak: 0.05, lp: 700, d: 0.04 });
  });
  def("ui.page", 4, function (c) {
    // One leaf turned: a swish that brightens, then the soft slap as it lies flat.
    noise(c, { f: k(c, [2600, 3000, 2300, 2800]), f2: 1300, q: 0.9, peak: 0.05,
               a: 0.05, d: 0.13 });
    return noise(c, { at: 0.16, type: "lowpass", f: 1400, q: 0.6, peak: 0.035, d: 0.04 });
  });

  // --- dice: the rattle in the hand and the landing clack (dice3d.js's own clack,
  // moved here so it obeys the volume and the mute).
  function rattle(c, f, n, peak) {
    return grains(c, { n: n, span: 0.24, f: f, q: 3.5, peak: peak, d: 0.01, bunch: 0.8 });
  }
  def("dice.roll", 3, function (c) {
    // Measured at 0.009 peak against the landing's 0.105 with 0.06 here: the rattle was
    // inaudible beside the clack it leads into. Ten-millisecond grains through a narrow
    // band carry little energy, so the level is higher than the other sounds' numbers.
    return rattle(c, k(c, [2400, 2900, 2600]), k(c, [6, 8, 7]), 0.16);
  });
  def("dice.land", 4, function (c) {
    noise(c, { f: k(c, [1650, 1800, 1550, 1720]), q: 1.1, peak: 0.15, a: 0.004, d: 0.056 });
    return tone(c, { type: "triangle", f: 210, f2: 120, glide: 0.07, peak: 0.085,
                     a: 0.006, d: 0.094 });
  });

  // --- verdict: a sting, never a fanfare.
  def("verdict.success", 3, function (c) {
    var root = k(c, [659, 698, 622]);
    bell(c, { f: root, peak: 0.06, d: 0.9 });
    return bell(c, { at: 0.075, f: root * 1.5, peak: 0.05, d: 1.0 });
  });
  def("verdict.failure", 3, function (c) {
    knock(c, { f: k(c, [130, 120, 140]), peak: 0.14, lp: 500, d: 0.09, wave: "sine" });
    tone(c, { at: 0.04, f: k(c, [233, 220, 247]), f2: k(c, [196, 185, 208]), glide: 0.5,
              peak: 0.04, a: 0.02, d: 0.55, lp: 900, type: "triangle" });
    return c.t + 0.6;
  });

  // --- combat.
  def("combat.hit", 4, function (c) {
    noise(c, { type: "lowpass", f: k(c, [900, 1100, 800, 1000]), q: 0.8, peak: 0.24,
               a: 0.002, d: 0.1 });
    noise(c, { f: 2600, q: 1.5, peak: 0.05, a: 0.001, d: 0.025 });
    return tone(c, { f: k(c, [110, 95, 120, 104]), f2: 55, glide: 0.14, peak: 0.2,
                     a: 0.003, d: 0.15 });
  });
  def("combat.miss", 4, function (c) {
    return noise(c, { f: k(c, [1300, 1500, 1150, 1400]), f2: k(c, [480, 520, 420, 560]),
                      q: 1.6, peak: 0.13, a: 0.05, d: 0.17 });
  });
  def("combat.crit", 3, function (c) {
    noise(c, { type: "lowpass", f: 1200, q: 0.8, peak: 0.28, a: 0.002, d: 0.12 });
    noise(c, { type: "highpass", f: 3500, q: 0.7, peak: 0.07, a: 0.001, d: 0.05 });
    tone(c, { f: k(c, [98, 90, 104]), f2: 48, glide: 0.18, peak: 0.24, a: 0.003, d: 0.2 });
    return bell(c, { at: 0.02, f: k(c, [1245, 1320, 1175]), peak: 0.035, d: 0.45 });
  });

  // --- bench.
  def("bench.open", 3, function (c) {
    knock(c, { f: k(c, [180, 165, 195]), peak: 0.1, lp: 800, d: 0.07 });
    return noise(c, { at: 0.05, src: "pink", type: "lowpass", f: 2200, q: 0.5,
                      peak: 0.035, a: 0.05, d: 0.25 });
  });

  // Choosing a method: the tool being set on the bench.
  var METHOD_SELECT = {
    grind: function (c) {        // the stone mortar set down
      knock(c, { f: k(c, [150, 135, 165]), peak: 0.13, lp: 700, d: 0.08 });
      return noise(c, { at: 0.01, f: 750, q: 2, peak: 0.05, d: 0.07 });
    },
    mix: function (c) {          // a wooden paddle tapped twice on the bowl's rim
      knock(c, { f: k(c, [420, 460, 390]), peak: 0.06, lp: 2000, d: 0.035, wave: "sine" });
      return knock(c, { at: 0.11, f: k(c, [440, 480, 410]), peak: 0.045, lp: 2000, d: 0.03,
                        wave: "sine" });
    },
    brew: function (c) {         // the pot's lid settling: dull iron
      return bell(c, { f: k(c, [196, 185, 208]), peak: 0.05, d: 0.35 });
    },
    dry: function (c) {          // a bundle of stems laid down
      return grains(c, { n: 9, span: 0.2, f: 4200, q: 1, type: "highpass", peak: 0.03,
                         d: 0.02 });
    },
    reduce: function (c) {       // the pan on the trivet, a short scrape
      bell(c, { f: k(c, [370, 349, 392]), peak: 0.04, d: 0.22 });
      return noise(c, { f: 2400, f2: 1800, q: 2, peak: 0.025, a: 0.02, d: 0.09 });
    },
    extract: function (c) {      // the knife drawn: a thin rising shing
      noise(c, { type: "highpass", f: 3500, f2: 6500, q: 1, peak: 0.035, a: 0.05, d: 0.12 });
      return tone(c, { at: 0.12, f: k(c, [3200, 3400, 3000]), peak: 0.012, d: 0.25 });
    },
    infuse: function (c) {       // the oil crock, ceramic
      knock(c, { f: k(c, [300, 280, 320]), peak: 0.08, lp: 1400, d: 0.05, wave: "sine" });
      return tone(c, { f: 820, peak: 0.02, d: 0.12 });
    },
    steep: function (c) {        // a glass jar, clinked
      return bell(c, { f: k(c, [1760, 1865, 1661]), peak: 0.035, d: 0.35 });
    },
    neutralize: function (c) {   // a vial and its dropper
      bell(c, { f: k(c, [2637, 2794, 2489]), peak: 0.025, d: 0.22 });
      return drop(c, { at: 0.16, f: 700, peak: 0.03 });
    },
  };

  // A good stroke in each method's minigame (UI plan §11; revamp plan §11's list: stone
  // crunch, stir slosh, simmer bubble, dry crackle, knife slice, oil sizzle, pour, drip).
  // `s` scales it: 1 for a hit, lower and duller for the matching miss.
  var METHOD_STROKE = {
    grind: function (c, s) {     // stone crunch
      grains(c, { n: 5, span: 0.05, f: 1100 * s, q: 0.9, peak: 0.12 * s, d: 0.018 });
      return knock(c, { f: k(c, [95, 85, 105]) * (s < 1 ? 0.85 : 1), peak: 0.12, lp: 600,
                        d: 0.05 });
    },
    mix: function (c, s) {       // stir slosh: a swell of wet low noise, there and back
      noise(c, { src: "pink", f: 500, f2: 1400 * s, q: 1.4, peak: 0.16 * s, a: 0.07,
                 d: 0.1 });
      return noise(c, { at: 0.12, src: "pink", f: 1300 * s, f2: 450, q: 1.4,
                        peak: 0.12 * s, a: 0.04, d: 0.12 });
    },
    brew: function (c, s) {      // simmer bubbles
      var end = c.t, n = k(c, [3, 4, 5]);
      for (var i = 0; i < n; i++) {
        end = Math.max(end, drop(c, { at: i * 0.05 + Math.random() * 0.03,
                                      f: (260 + Math.random() * 160) * s, rise: 1.8,
                                      peak: 0.05 * s, d: 0.045 }));
      }
      return end;
    },
    dry: function (c, s) {       // dry crackle
      return grains(c, { n: s < 1 ? 6 : 12, span: 0.28, f: 5200 * s, q: 1.2,
                         type: "highpass", peak: 0.06 * s, d: 0.006 });
    },
    reduce: function (c, s) {    // a thick, slower bubble and a breath of steam
      drop(c, { f: 180 * s, rise: 1.6, peak: 0.07 * s, d: 0.07 });
      return noise(c, { at: 0.03, type: "highpass", f: 4500, q: 0.7, peak: 0.02 * s,
                        a: 0.03, d: 0.2 });
    },
    extract: function (c, s) {   // knife slice
      noise(c, { f: 2500 * s, f2: 6000 * s, q: 2.2, peak: 0.07 * s, a: 0.01, d: 0.09 });
      return knock(c, { at: 0.09, f: 600 * s, peak: 0.035, lp: 2400, d: 0.02, wave: "sine" });
    },
    infuse: function (c, s) {    // oil sizzle
      noise(c, { type: "highpass", f: 4200 * s, q: 0.6, peak: 0.035 * s, a: 0.01, d: 0.3 });
      return grains(c, { n: 7, span: 0.3, f: 6000 * s, q: 1, type: "highpass",
                         peak: 0.04 * s, d: 0.004 });
    },
    steep: function (c, s) {     // pour: band-passed noise whose band wobbles, the gurgle
      var x = c.x, t = c.t, dur = 0.38;
      var src = x.createBufferSource(); src.buffer = buf("pink");
      var f = x.createBiquadFilter(); f.type = "bandpass"; f.Q.value = 3;
      f.frequency.value = hz(900 * s * c.p);
      var lfo = x.createOscillator(); lfo.frequency.value = k(c, [9, 11, 8]);
      var depth = x.createGain(); depth.gain.value = 300 * s;
      lfo.connect(depth); depth.connect(f.frequency);
      var g = x.createGain();
      var end = env(g, t, 0.09 * s, 0.05, dur - 0.05, 0.1);
      src.connect(f); f.connect(g); g.connect(c.out);
      src.start(t, Math.random() * 2); src.stop(end + 0.03);
      lfo.start(t); lfo.stop(end + 0.03);
      return end;
    },
    neutralize: function (c, s) { // drip
      return drop(c, { f: k(c, [520, 580, 470]) * s, rise: s < 1 ? 1.3 : 2.6,
                       peak: 0.06 * s, d: 0.06 });
    },
  };

  // An ingredient landing on the tool, by what it is (contracts §2's part list).
  var DROP_KIND = {
    root: "clunk", bark: "clunk", bone: "clack", horn: "clack", shell: "clack",
    mineral: "stone", leaf: "tick", flower: "tick", feather: "tick", scale: "tick",
    seed: "patter", berry: "patter", fungus: "squelch", gland: "squelch",
    organ: "squelch", eye: "squelch", liquid: "splash", sap: "hiss", resin: "hiss",
    oil: "hiss", wax: "hiss",
  };
  var DROP = {
    clunk: function (c) {        // heavy and woody
      return knock(c, { f: k(c, [120, 108, 132]), peak: 0.16, lp: 650, d: 0.08 });
    },
    clack: function (c) {        // hard and hollow
      knock(c, { f: k(c, [320, 290, 350]), peak: 0.08, lp: 2200, d: 0.04 });
      return noise(c, { f: 1500, q: 2.5, peak: 0.06, d: 0.03 });
    },
    stone: function (c) {
      knock(c, { f: k(c, [210, 190, 230]), peak: 0.1, lp: 1500, d: 0.035 });
      return noise(c, { f: 3000, q: 3, peak: 0.04, d: 0.02 });
    },
    tick: function (c) {         // a leaf or a petal: barely there
      return noise(c, { src: "pink", type: "highpass", f: k(c, [2500, 2800, 2200]), q: 0.7,
                        peak: 0.03, a: 0.006, d: 0.05 });
    },
    patter: function (c) {
      return grains(c, { n: k(c, [3, 4, 5]), span: 0.09, f: 2600, q: 2.5, peak: 0.09,
                         d: 0.01 });
    },
    squelch: function (c) {      // soft and wet
      noise(c, { src: "pink", f: 700, f2: 300, q: 2, peak: 0.07, a: 0.01, d: 0.08 });
      return drop(c, { at: 0.02, f: 240, rise: 1.4, peak: 0.025, d: 0.05 });
    },
    splash: function (c) {
      noise(c, { f: 1800, f2: 900, q: 0.8, peak: 0.07, a: 0.004, d: 0.14 });
      drop(c, { at: 0.03, f: 480, peak: 0.035 });
      return drop(c, { at: 0.08, f: 620, peak: 0.02 });
    },
    hiss: function (c) {         // sap, resin, oil, wax: a slow sticky hiss
      return noise(c, { type: "highpass", f: k(c, [3800, 4400, 3400]), q: 0.6, peak: 0.03,
                        a: 0.03, d: 0.22 });
    },
  };

  Object.keys(METHOD_SELECT).forEach(function (m) {
    def("bench.method." + m, 3, METHOD_SELECT[m]);
    def("bench.hit." + m, 3, function (c) { return METHOD_STROKE[m](c, 1); });
    // A miss: the same gesture gone wrong (duller, lower, quieter) under a dead thud,
    // so the ear hears which game it is and that the stroke failed.
    def("bench.miss." + m, 3, function (c) {
      METHOD_STROKE[m](c, 0.6);
      return knock(c, { f: k(c, [140, 125, 150]), peak: 0.06, lp: 400, d: 0.05, drop: 0.6,
                        wave: "sine" });
    });
  });
  Object.keys(DROP_KIND).forEach(function (part) {
    def("bench.drop." + part, 3, DROP[DROP_KIND[part]]);
  });

  def("bench.roll", 3, function (c) {          // the bench's own check: a wooden cup
    knock(c, { f: 260, peak: 0.04, lp: 900, d: 0.04 });
    return rattle(c, k(c, [1900, 2200, 2000]), k(c, [6, 7, 8]), 0.12);
  });
  def("bench.tick", 4, function (c) {          // a beat pip: a tiny wooden tick
    noise(c, { f: 4200, q: 4, peak: 0.03, d: 0.01 });
    return tone(c, { f: k(c, [1180, 1240, 1120, 1210]), peak: 0.03, d: 0.03 });
  });
  def("bench.tier.up", 3, function (c) {       // two rising notes
    var root = k(c, [784, 831, 740]);
    bell(c, { f: root, peak: 0.04, d: 0.4 });
    return bell(c, { at: 0.09, f: root * 1.4983, peak: 0.045, d: 0.55 });
  });
  def("bench.flawless", 3, function (c) {      // a bright metallic chime stack
    var root = k(c, [1047, 988, 1109]);
    var steps = [1, 1.2599, 1.4983, 2];        // a major chord and its octave
    var end = c.t;
    for (var i = 0; i < steps.length; i++) {
      end = Math.max(end, bell(c, { at: i * 0.06, f: root * steps[i], peak: 0.04,
                                    d: 1.1 + i * 0.15 }));
    }
    noise(c, { type: "highpass", f: 7000, q: 0.5, peak: 0.012, a: 0.1, d: 0.6 });
    return end;
  });
  def("bench.fail", 3, function (c) {          // a low thud and a crack
    knock(c, { f: k(c, [72, 66, 78]), peak: 0.2, lp: 300, d: 0.14, drop: 0.6, wave: "sine" });
    noise(c, { at: 0.05, type: "highpass", f: 2200, q: 0.8, peak: 0.08, a: 0.001, d: 0.04 });
    return grains(c, { at: 0.07, n: 4, span: 0.08, f: 3000, q: 2, peak: 0.04, d: 0.01 });
  });
  def("bench.land", 3, function (c) {          // into the satchel: leather, a soft thump
    noise(c, { src: "pink", type: "lowpass", f: k(c, [600, 520, 680]), q: 0.7, peak: 0.08,
               a: 0.006, d: 0.12 });
    return tone(c, { f: 190, f2: 140, glide: 0.1, peak: 0.04, d: 0.1 });
  });
  def("bench.taste", 3, function (c) {         // a small sip
    noise(c, { f: 1400, f2: 2600, q: 3, peak: 0.035, a: 0.03, d: 0.08 });
    return drop(c, { at: 0.1, f: k(c, [380, 420, 350]), rise: 1.5, peak: 0.025, d: 0.04 });
  });
  def("bench.study", 3, function (c) {         // a page riffle
    var n = k(c, [7, 9, 8]), end = c.t;
    for (var i = 0; i < n; i++) {
      end = Math.max(end, noise(c, { at: i * 0.045 + Math.random() * 0.01,
                                     f: 2800 + Math.random() * 1200, q: 1,
                                     peak: 0.04 * (1 - i / (n * 1.6)), a: 0.004, d: 0.03 }));
    }
    return end;
  });

  /* --- ambience: beds that loop ----------------------------------------------------- *
   * A bed is continuous noise through a filter whose level breathes on a slow LFO (wind
   * gusts), plus scheduled one-shots (a bird, a cricket's chirp, a crackle, a drip) at
   * random intervals. Generated, so it never audibly loops. Quiet: it sits under play. */

  function bed(x, out, o) {
    var src = x.createBufferSource();
    src.buffer = buf(o.src || "pink");
    src.loop = true;
    var f = x.createBiquadFilter();
    f.type = o.type || "bandpass";
    f.frequency.value = hz(o.f);
    f.Q.value = o.q == null ? 0.7 : o.q;
    var g = x.createGain();
    g.gain.value = o.level;
    var nodes = [src];
    if (o.gust) {   // the level breathing
      var lfo = x.createOscillator();
      lfo.frequency.value = o.gust;
      var depth = x.createGain();
      depth.gain.value = o.level * (o.gustDepth || 0.5);
      lfo.connect(depth); depth.connect(g.gain);
      lfo.start(); nodes.push(lfo);
    }
    if (o.sweep) {  // the filter wandering, the whistle in a cold wind
      var lfo2 = x.createOscillator();
      lfo2.frequency.value = o.sweep;
      var d2 = x.createGain();
      d2.gain.value = o.sweepDepth || o.f * 0.4;
      lfo2.connect(d2); d2.connect(f.frequency);
      lfo2.start(); nodes.push(lfo2);
    }
    src.connect(f); f.connect(g); g.connect(out);
    src.start(0, Math.random() * (src.buffer.duration - 0.1));
    return nodes;
  }

  // One-shot ambient events, each `fn(c)` with the same building blocks as the bank.
  var EVENT = {
    bird: function (c) {
      var f = 2400 + Math.random() * 1400, n = 2 + (Math.random() * 3 | 0);
      for (var i = 0; i < n; i++) {
        tone(c, { at: i * 0.11, f: f, f2: f * (1.15 + Math.random() * 0.25), glide: 0.06,
                  peak: 0.012, a: 0.01, d: 0.07 });
      }
    },
    cricket: function (c) {
      var f = 4200 + Math.random() * 500;
      for (var i = 0; i < 3; i++) tone(c, { at: i * 0.045, f: f, peak: 0.008, a: 0.004, d: 0.02 });
    },
    crackle: function (c) {
      grains(c, { n: 2 + (Math.random() * 4 | 0), span: 0.12, f: 3000, q: 1.2,
                  type: "highpass", peak: 0.03, d: 0.006 });
    },
    pop: function (c) {
      knock(c, { f: 160, peak: 0.03, lp: 600, d: 0.03 });
    },
    drip: function (c) {
      drop(c, { f: 500 + Math.random() * 400, peak: 0.015, d: 0.05 });
    },
    frog: function (c) {
      var n = 2 + (Math.random() * 3 | 0), f = 85 + Math.random() * 30;
      for (var i = 0; i < n; i++) {
        tone(c, { at: i * 0.16, type: "sawtooth", f: f, f2: f * 0.85, glide: 0.08, lp: 420,
                  peak: 0.02, a: 0.01, d: 0.08 });
      }
    },
    owl: function (c) {
      tone(c, { f: 380, f2: 360, glide: 0.3, peak: 0.012, a: 0.06, d: 0.3, lp: 800 });
      tone(c, { at: 0.55, f: 372, f2: 340, glide: 0.5, peak: 0.01, a: 0.08, d: 0.5, lp: 800 });
    },
    gravel: function (c) {
      for (var i = 0; i < 3; i++) {
        grains(c, { at: i * 0.55, n: 4, span: 0.06, f: 1800, q: 1, peak: 0.012, d: 0.01 });
      }
    },
    clink: function (c) {
      bell(c, { f: 2400 + Math.random() * 600, peak: 0.008, d: 0.3 });
    },
    creak: function (c) {
      tone(c, { type: "sawtooth", f: 140, f2: 120, glide: 0.4, lp: 600, peak: 0.006,
                a: 0.1, d: 0.35 });
    },
  };

  // Each ambience: its beds and its events ([name, min seconds, max seconds] apart).
  var AMBIENCE = {
    forest: { beds: [{ f: 900, q: 0.5, level: 0.05, gust: 0.07, gustDepth: 0.6 },
                     { type: "highpass", f: 5000, level: 0.006, gust: 0.11 }],
              events: [["bird", 3, 9], ["crackle", 8, 20]] },
    swamp: { beds: [{ src: "white", type: "highpass", f: 2600, q: 0.5, level: 0.018,
                      gust: 0.05, gustDepth: 0.3 },               // drizzle
                    { src: "brown", type: "lowpass", f: 300, level: 0.05 }],
             events: [["drip", 0.4, 1.8], ["frog", 3, 8], ["cricket", 2, 6]] },
    tundra: { beds: [{ f: 650, q: 2.2, level: 0.05, gust: 0.06, gustDepth: 0.7,
                       sweep: 0.09, sweepDepth: 320 },            // the whistle
                     { src: "white", type: "highpass", f: 6000, level: 0.004, gust: 0.13 }],
              events: [] },
    desert: { beds: [{ src: "brown", type: "lowpass", f: 480, level: 0.07, gust: 0.05,
                       gustDepth: 0.7 },
                     { src: "white", type: "highpass", f: 7000, level: 0.003, gust: 0.08,
                       gustDepth: 0.9 }],                          // sand on the wind
              events: [] },
    grassland: { beds: [{ f: 700, q: 0.7, level: 0.04, gust: 0.08, gustDepth: 0.6 }],
                 events: [["cricket", 1.5, 4], ["bird", 6, 15]] },
    road: { beds: [{ f: 650, q: 0.6, level: 0.035, gust: 0.06, gustDepth: 0.5 }],
            events: [["bird", 8, 18], ["gravel", 10, 25]] },
    indoors: { beds: [{ src: "brown", type: "lowpass", f: 180, level: 0.06 },
                      { type: "highpass", f: 3000, level: 0.003 }],
               events: [["creak", 15, 40]] },
    tavern: { beds: [{ src: "brown", type: "lowpass", f: 200, level: 0.05 },
                     { f: 380, q: 1.3, level: 0.025, gust: 0.7, gustDepth: 0.5 }],  // murmur
              events: [["crackle", 0.3, 1.4], ["pop", 4, 12], ["clink", 6, 16]] },
    night: { beds: [{ f: 500, q: 0.6, level: 0.025, gust: 0.05, gustDepth: 0.5 }],
             events: [["cricket", 0.6, 2], ["owl", 15, 35]] },
    // Two the app's biomes need that the first list did not have (rules/biomes.py).
    coast: { beds: [{ src: "brown", type: "lowpass", f: 520, level: 0.08, gust: 0.09,
                      gustDepth: 0.85 },                            // the swell of surf
                    { type: "highpass", f: 3500, level: 0.008, gust: 0.09, gustDepth: 0.9 }],
             events: [["bird", 10, 25]] },
    cave: { beds: [{ src: "brown", type: "lowpass", f: 140, level: 0.06 }],
            events: [["drip", 1.5, 5]] },
  };
  // The app's canonical biomes (rules/biomes.py BIOMES) onto the nearest bed, so
  // `ambience.<biome>` for any ground the bench reports is never silent by accident.
  var AMBIENCE_ALIAS = {
    urban: "road", farmland: "grassland", jungle: "swamp", hills: "grassland",
    mountain: "tundra", water: "coast", deck: "coast", underwater: "cave",
    underground: "cave", ruins: "night", planar: "night",
  };

  function startAmbience(spec) {
    var x = ctx, out = x.createGain(), live = true, timers = [];
    out.gain.setValueAtTime(0.0001, x.currentTime);
    out.gain.exponentialRampToValueAtTime(1, x.currentTime + 1.5);
    out.connect(buses.ambience);
    var nodes = [];
    spec.beds.forEach(function (b) { nodes = nodes.concat(bed(x, out, b)); });
    spec.events.forEach(function (ev) {
      var fn = EVENT[ev[0]], lo = ev[1], hi = ev[2];
      (function next() {
        var wait = (lo + Math.random() * (hi - lo)) * 1000;
        timers.push(setTimeout(function () {
          if (!live) return;
          try {
            if (x.state === "running") {
              fn({ x: x, out: out, t: x.currentTime + 0.02, p: 0.95 + Math.random() * 0.1,
                   v: 0 });
            }
          } catch (e) { /* one bad event never stops the bed */ }
          next();
        }, wait));
      })();
    });
    return {
      stop: function () {
        if (!live) return;
        live = false;
        try {
          timers.forEach(clearTimeout);
          var now = x.currentTime;
          out.gain.cancelScheduledValues(now);
          out.gain.setValueAtTime(Math.max(0.0001, out.gain.value), now);
          out.gain.exponentialRampToValueAtTime(0.0001, now + 0.8);
          nodes.forEach(function (n) { try { n.stop(now + 0.85); } catch (e) { /* */ } });
          setTimeout(function () { try { out.disconnect(); } catch (e) { /* */ } }, 1000);
        } catch (e) { /* already gone */ }
      },
    };
  }

  /* --- the public face -------------------------------------------------------------- */

  function pickTake(name, n) {
    if (n <= 1) return 0;
    var last = lastTake[name], v = Math.random() * n | 0;
    if (v === last) v = (v + 1 + (Math.random() * (n - 1) | 0)) % n;
    lastTake[name] = v;
    return v;
  }

  function play(name, opts) {
    try {
      var s = SOUNDS[name];
      if (!s) return false;
      if (!hasGesture()) return false;            // dropped, not queued (see the header)
      var x = ensure();
      if (!x) return false;
      if (x.state === "suspended") unlock();
      if (masterLevel() <= 0) return false;       // muted: build nothing at all
      var bus = buses[String(name).split(".")[0]];
      if (!bus || voices >= MAX_VOICES) return false;
      opts = opts || {};
      var vol = opts.volume == null ? 1 : clamp(Number(opts.volume), 0, 2);
      if (vol <= 0) return false;
      var rate = opts.rate == null ? 1 : clamp(Number(opts.rate), 0.25, 4);
      var delay = opts.delay == null ? 0 : clamp(Number(opts.delay), 0, 10);
      var out = x.createGain();
      out.gain.value = vol;
      out.connect(bus);
      var c = { x: x, out: out, t: x.currentTime + 0.005 + delay,
                p: rate * (0.95 + Math.random() * 0.1), v: pickTake(name, s.n) };
      var end = s.fn(c);
      var life = Math.max(0.05, (isFinite(end) ? end : c.t + 1) - x.currentTime) + 0.3;
      voices += 1;
      setTimeout(function () {
        voices = Math.max(0, voices - 1);
        try { out.disconnect(); } catch (e) { /* */ }
      }, life * 1000);
      return true;
    } catch (e) {
      return false;
    }
  }

  var SILENT_LOOP = { stop: function () {} };

  function loop(name) {
    try {
      var parts = String(name).split(".");
      if (parts[0] !== "ambience") return SILENT_LOOP;
      var key = AMBIENCE[parts[1]] ? parts[1] : AMBIENCE_ALIAS[parts[1]];
      var spec = key && AMBIENCE[key];
      if (!spec) return SILENT_LOOP;
      var x = ensure();
      if (!x) return SILENT_LOOP;
      // A bed may be asked for before any gesture (the bench opening on load); it is
      // built now and starts sounding when the context is unlocked, which for a quiet
      // continuous bed is exactly right.
      return startAmbience(spec);
    } catch (e) {
      return SILENT_LOOP;
    }
  }

  function names() {
    var list = Object.keys(SOUNDS);
    Object.keys(AMBIENCE).concat(Object.keys(AMBIENCE_ALIAS)).forEach(function (b) {
      list.push("ambience." + b);
    });
    return list.sort();
  }

  window.Sound = {
    play: play,
    loop: loop,
    unlock: unlock,
    names: names,
    has: function (name) {
      try {
        var p = String(name).split(".");
        return !!SOUNDS[name] || (p[0] === "ambience" &&
          !!(AMBIENCE[p[1]] || AMBIENCE_ALIAS[p[1]]));
      } catch (e) { return false; }
    },
    state: function () { try { return ctx ? ctx.state : "none"; } catch (e) { return "none"; } },
  };
})();
