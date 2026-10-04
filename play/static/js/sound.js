/* The app's sound: `window.Sound` (docs/herbalism-contracts.md §5.3, revamp plan §11).
 *
 *   Sound.play(name, {volume, rate, delay})   one-shot; unknown names are a silent no-op
 *                                             (forge sounds also read {hardness, bath})
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
 * bench, forge, ambience, combat, verdict) feed one master gain, then a gentle limiter, then the
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

  // `forge` is the Blacksmithing bench's own bus (blacksmithing UI plan §11, §6.8), beside
  // the herb bench's, so a player can hear the anvil louder or quieter than the mortar.
  var BUSES = ["ui", "dice", "bench", "forge", "ambience", "combat", "verdict"];
  var BUS_PREF = {
    ui: "sound.ui", dice: "sound.dice", bench: "sound.bench", forge: "sound.forge",
    ambience: "sound.ambience", combat: "sound.combat", verdict: "sound.dice",
  };
  var BUS_DEFAULT = { ui: 0.6, dice: 0.8, bench: 0.8, forge: 0.8, ambience: 0.4, combat: 0.7,
                      verdict: 0.8 };
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

  // --- the engine device (13-device.js): the brass status mechanism beside the story.
  // The owner, 2026-10-02: "this needs sound as well, not too loud", then "make the device
  // sounds a bit louder" (every peak doubled). It is heard on every turn, so every peak
  // still stays under a ui.click's. Ticks come from the large gear's own turning (the device paces them), the
  // puffs from its own steam, and the settle, sigh and lever from its own events.
  def("ui.device.tick", 4, function (c) {
    // One tooth of a cog meeting the next: a small, soft metallic click with a hint of
    // ring, not a clock's tick. Dense at speed (the device paces them off both gears), so
    // each one is quiet; the bed (machine(), below) carries the motion between them.
    noise(c, { f: k(c, [3600, 3200, 4100, 3400]), q: 5, peak: 0.028, d: 0.006 });
    return tone(c, { type: "sine", f: k(c, [2350, 2600, 2150, 2480]),
                     peak: 0.008, a: 0.001, d: 0.03 });
  });
  def("ui.device.puff", 3, function (c) {
    // A short breath of steam from the foot, soft and low in the mix.
    return noise(c, { src: "pink", type: "bandpass", f: k(c, [1400, 1250, 1550]), f2: 900,
                      q: 0.9, peak: 0.03, a: 0.02, d: 0.16 });
  });
  def("ui.device.settle", 2, function (c) {
    // The gears coming to rest: a low wooden-brass thunk, felt more than heard.
    return knock(c, { f: k(c, [180, 200]), peak: 0.055, lp: 600, d: 0.06 });
  });
  def("ui.device.sigh", 2, function (c) {
    // The burst of steam as the machine stops on an answer: a longer, falling hiss.
    return noise(c, { src: "pink", type: "bandpass", f: 1800, f2: 700, q: 0.8,
                      peak: 0.055, a: 0.05, d: 0.7 });
  });
  def("ui.device.lever", 3, function (c) {
    // The lever popping up and the tab sliding out: a spring-loaded brass click and a
    // faint ring of the plate, the "your turn is ready" of the machine.
    noise(c, { f: k(c, [3000, 3300, 2800]), q: 4, peak: 0.055, d: 0.012 });
    return bell(c, { at: 0.015, f: k(c, [1320, 1400, 1250]), peak: 0.022, d: 0.35 });
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

  /* --- forge: the Blacksmithing bench (blacksmithing UI plan §11, contracts §11) ------ *
   * `Sound.play("forge.<event>", {hardness, bath})`. Grounded in how the real things sound,
   * rather than in what an anvil sounds like in films:
   *
   * THE ANVIL. A good anvil "will ring like a bell"; a soft, cast or cracked one gives "a
   * dull thud" and the hammer "will feel dead on impact" (the smiths' ring and rebound
   * tests, blacksmithtalk.com/threads/quick-test-for-anvil-rebound.480 and the bushcraftuk
   * anvil buyers' guide). And it is not an orchestra's anvil: a real one has "a remarkably
   * high-pitched ping" and does not "vibrate very long because of how large they are"
   * (LA Opera's percussionist on the Anvil Chorus, laopera.org "Secret Sounds: Inside the
   * Anvil Chorus"). So a strike in band is a short, high, inharmonic ping over the dull
   * squash of hot iron, and a strike out of band is the thud with no ping at all.
   *
   * PITCH BY HARDNESS. A struck body's modes scale with its speed of sound, c = sqrt(E/rho):
   * a thin rod carries sound at 5180 m/s in 1%-carbon steel, 3480 in brass, 2030 in gold
   * (engineeringtoolbox.com/sound-speed-solids-d_713.html), and bell bronze 3400 (KIT,
   * ifm.kit.edu 2006_AS_GB_KS_1). Same shape, softer metal, lower ring. The game has no
   * modulus for adamantine, but it has hardness, which orders the metals the same way, so
   * the ring's fundamental is a hundred hertz per point: bronze (8) 800 Hz, steel (12)
   * 1200, mithral (15) 1500, adamantine (20) 2000. The partials are a free bar's (bell()).
   *
   * THE QUENCH. The noise of a quench is loudest where the vapour film breaks into
   * nucleate boiling, bubbles forming and collapsing (researchgate "Investigation of
   * sound phenomena during quenching process"); boiling noise moves from about 200-250 Hz
   * to 400-500 Hz as the heat flux climbs (the RIT boiling-sound thesis). Brine's salt
   * nucleates boiling and breaks the vapour blanket at once, a loud crackling discharge,
   * while oil holds a longer vapour stage and boils slower and gentler (heat-treat
   * references: fractory.com "Quenching Explained", paulo.com on oil quenching). So: brine
   * is the brightest hiss with the most crackle, water a little softer, oil a low,
   * muffled seethe with a burble and almost no crackle.
   *
   * THE FIRE. Combustion roar is continuous broadband noise peaking low, around 250-500 Hz
   * for open turbulent flames (Combustion and Flame, "Combustion roar of premix burners";
   * the IFRF handbook on combustion noise). The smithy bed and the bellows sit there.
   *
   * LEVELS. The owner asked device sounds to be "not too loud", then "a bit louder"
   * (2026-10-02). A strike is heard dozens of times a craft, so every forge peak stays
   * under combat.hit's body (0.24) and the loudest is the dead thud of a miss. */

  // Hardness by material, for a caller that has the material and not the number. The
  // game's house model is PF1's base hardness 10 plus the material's own `hardness`
  // gear_mod (content/materials/blacksmith-materials.json), which lands on the rulebook's
  // own figures where it has them: mithral 15, adamantine 20. A number is always better;
  // this table is only the fallback, and a name it lacks is iron.
  var HARDNESS = {
    iron: 12, "wrought-iron": 8, copper: 9, tin: 8, lead: 10, zinc: 10, bismuth: 10,
    silver: 8, gold: 5, platinum: 10, "cold-iron": 8, "star-iron": 12, viridium: 5,
    mithral: 15, adamantine: 20, abysium: 12, djezet: 10, inubrix: 5, noqual: 10,
    siccatite: 10, horacalcum: 15, steel: 12, bronze: 8, brass: 8, pewter: 8, electrum: 8,
    "bell-bronze": 12, "high-carbon-steel": 12, "pattern-steel": 8, "nexavaran-steel": 8,
    "elysian-bronze": 8, "living-steel": 15, "fire-forged-steel": 8,
    "frost-forged-steel": 8, "singing-steel": 10, wyrmsteel: 10,
  };
  function hardnessOf(c) {
    try {
      var o = c.o || {}, h = o.hardness != null ? o.hardness : o.material;
      if (typeof h === "string") {
        var key = h.trim().toLowerCase();
        h = HARDNESS[key] != null ? HARDNESS[key] : Number(key);
      }
      h = Number(h);
      return isFinite(h) && h > 0 ? clamp(h, 3, 30) : 10;
    } catch (e) { return 10; }
  }
  // The anvil's ping for this work: the fundamental (100 Hz per point of hardness) and a
  // ring a little longer on harder work, still well under a second (the anvil is massive).
  function ping(c, o) {
    var h = hardnessOf(c);
    return bell(c, { at: o.at, f: 100 * h * (o.mul || 1), peak: o.peak,
                     d: (o.d || 0.3) + 0.012 * h });
  }

  // Quench baths. The id is the quenchant's (content/materials: water, quenching-brine,
  // quenching-oil, whale-oil, glacier-melt, mercury-bath, blessed-water, troll-blood,
  // wyvern-blood, dragon-blood, styx-water), read by the word in it, so a homebrew
  // "sea-brine" or "linseed-oil" is heard as its family. Unknown or none is water.
  //   hiss   the steam's band, falling as the film collapses
  //   crack  grains of vapour discharge (brine's "explosive" breakup)
  //   burble low bubbles (a thick bath boiling slowly)
  var BATH = {
    brine:   { hiss: 5200, q: 0.8, crack: 14, crackF: 4400, peak: 0.075, d: 0.9, burble: 0,
               splash: 2200 },
    water:   { hiss: 4000, q: 0.7, crack: 8, crackF: 3400, peak: 0.065, d: 1.1, burble: 0,
               splash: 1900 },
    blood:   { hiss: 2800, q: 0.9, crack: 5, crackF: 2400, peak: 0.055, d: 1.2, burble: 3,
               splash: 1400 },
    mercury: { hiss: 2200, q: 1.2, crack: 4, crackF: 1900, peak: 0.045, d: 0.8, burble: 2,
               splash: 900 },
    oil:     { hiss: 1500, q: 0.6, crack: 2, crackF: 1300, peak: 0.05, d: 1.6, burble: 5,
               splash: 1100 },
  };
  function bathOf(c) {
    try {
      var b = String((c.o || {}).bath || "").toLowerCase();
      if (b.indexOf("brine") >= 0 || b.indexOf("salt") >= 0) return BATH.brine;
      if (b.indexOf("oil") >= 0) return BATH.oil;
      if (b.indexOf("blood") >= 0) return BATH.blood;
      if (b.indexOf("mercury") >= 0) return BATH.mercury;
    } catch (e) { /* water */ }
    return BATH.water;
  }

  def("forge.open", 3, function (c) {
    // The hearth flaring from embers (UI plan §10): a low whump of air catching, then
    // the anvil's quiet ping as it comes into the light.
    noise(c, { src: "brown", type: "lowpass", f: 220, f2: k(c, [700, 640, 760]), q: 0.7,
               peak: 0.12, a: 0.12, d: 0.5 });
    noise(c, { at: 0.05, src: "pink", type: "highpass", f: 2800, q: 0.6, peak: 0.012,
               a: 0.15, d: 0.4 });
    return ping(c, { at: 0.32, peak: 0.022, d: 0.25 });
  });

  // Choosing a method: the tool coming off the rack (UI plan §10, "tools swap").
  var FORGE_METHOD = {
    smelt: function (c) {        // the clay crucible pushed into the coals
      knock(c, { f: k(c, [240, 220, 260]), peak: 0.08, lp: 1300, d: 0.05, wave: "sine" });
      return grains(c, { at: 0.03, n: 6, span: 0.15, f: 1600, q: 1.5, peak: 0.05,
                         d: 0.012 });
    },
    alloy: function (c) {        // the ladle against the crucible's lip, then a heavy slosh
      bell(c, { f: k(c, [620, 590, 660]), peak: 0.03, d: 0.25 });
      return noise(c, { at: 0.1, src: "pink", f: 380, f2: 700, q: 1.6, peak: 0.07, a: 0.06,
                        d: 0.16 });
    },
    forge: function (c) {        // the hammer set down on the anvil face: a light ping
      knock(c, { f: k(c, [170, 160, 185]), peak: 0.05, lp: 900, d: 0.03 });
      return ping(c, { at: 0.005, peak: 0.03, d: 0.2 });
    },
    quench: function (c) {       // a hand in the slack tub: wood and a slap of water
      knock(c, { f: k(c, [150, 140, 165]), peak: 0.06, lp: 700, d: 0.05 });
      return noise(c, { at: 0.04, f: 1200, f2: 600, q: 1, peak: 0.05, a: 0.01, d: 0.14 });
    },
    temper: function (c) {       // the tongs: two small iron clicks
      noise(c, { f: k(c, [3400, 3100, 3700]), q: 4, peak: 0.05, d: 0.01 });
      return bell(c, { at: 0.09, f: k(c, [2100, 1980, 2250]), peak: 0.018, d: 0.12 });
    },
    fold: function (c) {         // the hot-cut chisel seated in the hardy hole
      knock(c, { f: k(c, [210, 195, 230]), peak: 0.07, lp: 1400, d: 0.035 });
      return bell(c, { at: 0.01, f: k(c, [1650, 1560, 1750]), peak: 0.025, d: 0.18 });
    },
    hone: function (c) {         // the whetstone laid down and drawn once
      knock(c, { f: k(c, [200, 185, 215]), peak: 0.06, lp: 1100, d: 0.03 });
      return noise(c, { at: 0.08, f: 3200, f2: 4200, q: 2, peak: 0.035, a: 0.03, d: 0.12 });
    },
    assemble: function (c) {     // the rivet tin shaken
      return grains(c, { n: k(c, [7, 9, 8]), span: 0.2, f: 3800, q: 5, peak: 0.05,
                         d: 0.02 });
    },
    finish: function (c) {       // the file picked up: one short rasp
      return grains(c, { n: 14, span: 0.18, f: 2600, q: 1.4, peak: 0.035, d: 0.01,
                         even: true, fade: false });
    },
    strengthen: function (c) {   // the sledge leaned on the anvil: a low, heavy ring
      knock(c, { f: k(c, [110, 100, 120]), peak: 0.09, lp: 600, d: 0.06 });
      return ping(c, { at: 0.01, mul: 0.5, peak: 0.025, d: 0.3 });
    },
    assay: function (c) {        // the touchstone and the balance pan
      return bell(c, { f: k(c, [2640, 2790, 2490]), peak: 0.022, d: 0.25 });
    },
  };
  Object.keys(FORGE_METHOD).forEach(function (m) {
    def("forge.method." + m, 3, FORGE_METHOD[m]);
  });

  // A piece landing in a slot on the anvil (UI plan §10, "a metal clink"), by its rack
  // form (rules/blacksmith.py GROUPS and Material.rack_form). Metal forms clink at the
  // pitch of their hardness when the caller says it.
  var FORGE_DROP = {
    ore: function (c) {          // a lump of rock: stone, gritty
      knock(c, { f: k(c, [180, 165, 200]), peak: 0.09, lp: 1200, d: 0.04 });
      return grains(c, { n: 4, span: 0.06, f: 2200, q: 2, peak: 0.04, d: 0.01 });
    },
    bar: function (c) {          // a bar on the anvil: a clank and a short ring
      knock(c, { f: k(c, [190, 175, 205]), peak: 0.07, lp: 1000, d: 0.035 });
      return ping(c, { at: 0.004, mul: 0.8, peak: 0.03, d: 0.18 });
    },
    ingot: function (c) {        // heavier and shorter than a bar
      knock(c, { f: k(c, [150, 140, 160]), peak: 0.09, lp: 800, d: 0.045 });
      return ping(c, { at: 0.004, mul: 0.65, peak: 0.022, d: 0.12 });
    },
    blank: function (c) {
      knock(c, { f: k(c, [210, 200, 225]), peak: 0.06, lp: 1200, d: 0.03 });
      return ping(c, { at: 0.004, mul: 1.1, peak: 0.028, d: 0.2 });
    },
    plate: function (c) {        // a sheet: a flat slap with a wobbling shimmer
      noise(c, { f: k(c, [2400, 2200, 2600]), q: 1.2, peak: 0.05, a: 0.002, d: 0.08 });
      return ping(c, { at: 0.006, mul: 0.6, peak: 0.025, d: 0.35 });
    },
    item: function (c) {         // finished work laid down with care
      knock(c, { f: k(c, [230, 215, 245]), peak: 0.05, lp: 1400, d: 0.03 });
      return ping(c, { at: 0.005, peak: 0.024, d: 0.25 });
    },
    fitting: function (c) {      // a haft, a grip, a guard: wood and leather, a soft knock
      return knock(c, { f: k(c, [320, 295, 345]), peak: 0.07, lp: 1800, d: 0.035,
                        wave: "sine" });
    },
    fuel: function (c) {         // a shovel of charcoal: dry crunch
      return grains(c, { n: k(c, [6, 8, 7]), span: 0.12, f: 1500, q: 1.2, peak: 0.06,
                         d: 0.014 });
    },
    flux: function (c) {         // borax sprinkled: a fine patter
      return grains(c, { n: k(c, [8, 10, 9]), span: 0.18, f: 4800, q: 1, type: "highpass",
                         peak: 0.025, d: 0.006 });
    },
    quenchant: function (c) {    // a stoppered jug set down: ceramic and a slosh
      knock(c, { f: k(c, [280, 260, 300]), peak: 0.06, lp: 1400, d: 0.04, wave: "sine" });
      return noise(c, { at: 0.05, src: "pink", f: 600, f2: 1100, q: 1.4, peak: 0.035,
                        a: 0.04, d: 0.1 });
    },
    treatment: function (c) {    // a small pot or packet
      return knock(c, { f: k(c, [360, 340, 390]), peak: 0.05, lp: 1800, d: 0.03,
                        wave: "sine" });
    },
    old: function (c) {          // pre-revamp work: an iron clunk, nothing fancy
      return knock(c, { f: k(c, [160, 150, 170]), peak: 0.08, lp: 900, d: 0.05 });
    },
  };
  // The fittings' own words (rules/blacksmith.py _FITTING_FORMS) all sound as a fitting.
  ["haft", "grip", "guard", "binding", "core", "lining", "fastening", "fastenings",
   "wrap"].forEach(function (f) { FORGE_DROP[f] = FORGE_DROP.fitting; });
  Object.keys(FORGE_DROP).forEach(function (f) {
    def("forge.drop." + f, 3, FORGE_DROP[f]);
  });

  def("forge.roll", 3, function (c) {          // the step's d20, rattled on the anvil face
    rattle(c, k(c, [2600, 3000, 2800]), k(c, [5, 7, 6]), 0.12);
    return bell(c, { at: 0.24, f: k(c, [2900, 3100, 2750]), peak: 0.01, d: 0.12 });
  });

  def("forge.strike.hit", 4, function (c) {
    // The hammer face meeting the work: a bright contact click, the dull squash of hot
    // iron, and the anvil's ping at the pitch of the work's hardness.
    noise(c, { type: "highpass", f: k(c, [3400, 3800, 3100, 3600]), q: 0.7, peak: 0.06,
               a: 0.001, d: 0.012 });
    knock(c, { f: k(c, [140, 128, 152, 135]), peak: 0.1, lp: 900, d: 0.045 });
    return ping(c, { at: 0.002, mul: k(c, [1, 1.02, 0.98, 1.01]), peak: 0.05, d: 0.28 });
  });
  def("forge.strike.miss", 4, function (c) {
    // Out of band: the work too cold to move, a dead thud and no ring at all (a soft or
    // cracked anvil's "dull thud", the hammer "dead on impact"). Nothing above 400 Hz is
    // tuned; a miss that pinged would read as a hit.
    noise(c, { type: "lowpass", f: k(c, [500, 450, 560, 480]), q: 0.6, peak: 0.1,
               a: 0.002, d: 0.07 });
    return tone(c, { type: "sine", f: k(c, [96, 88, 104, 92]), f2: 58, glide: 0.1,
                     peak: 0.13, a: 0.003, d: 0.12 });
  });

  def("forge.bellows", 3, function (c) {
    // One pump of a leather bellows: the breath through the tuyere (a swell of band-passed
    // noise that rises and falls), the fire roaring up under it at the combustion peak,
    // and the faint creak of the board.
    noise(c, { src: "pink", f: 500, f2: k(c, [1300, 1150, 1450]), q: 1.1, peak: 0.07,
               a: 0.25, d: 0.35 });
    noise(c, { at: 0.12, src: "brown", type: "lowpass", f: 280, f2: 420, q: 0.7,
               peak: 0.1, a: 0.2, d: 0.5 });
    return tone(c, { type: "sawtooth", f: k(c, [130, 120, 145]), f2: 112, glide: 0.25,
                     lp: 500, peak: 0.006, a: 0.06, d: 0.22 });
  });

  def("forge.quench", 3, function (c) {
    var b = bathOf(c), end;
    // The plunge.
    noise(c, { f: b.splash, f2: b.splash * 0.5, q: 0.9, peak: 0.06, a: 0.003, d: 0.1 });
    // The hiss: steam off the film, falling as the film collapses into boiling.
    end = noise(c, { at: 0.02, type: "bandpass", f: b.hiss, f2: b.hiss * 0.6, q: b.q,
                     peak: b.peak, a: 0.03, d: b.d * k(c, [1, 0.92, 1.08]) });
    // The vapour discharge: brine crackles, oil barely does.
    end = Math.max(end, grains(c, { at: 0.04, n: b.crack, span: b.d * 0.6, f: b.crackF,
                                    q: 1.5, peak: b.peak * 0.7, d: 0.008, bunch: 1.6 }));
    // A thick bath boils slowly: low bubbles under the seethe.
    for (var i = 0; i < b.burble; i++) {
      end = Math.max(end, drop(c, { at: 0.1 + i * b.d / (b.burble + 1),
                                    f: 160 + Math.random() * 90, rise: 1.6,
                                    peak: 0.03, d: 0.06 }));
    }
    return end;
  });

  def("forge.temper", 3, function (c) {
    // Tempering is gentle heat: a soft sizzle as oil is wiped on warm steel, and the
    // small ticks of the metal moving as it cools.
    noise(c, { type: "highpass", f: k(c, [3600, 3300, 3900]), q: 0.6, peak: 0.022,
               a: 0.05, d: 0.45 });
    return grains(c, { at: 0.1, n: k(c, [3, 4, 2]), span: 0.5, f: 5200, q: 6,
                       peak: 0.035, d: 0.01 });
  });
  def("forge.grind", 4, function (c) {
    // A stroke on the stone: a rasp that brightens as the edge bites, grit under it.
    noise(c, { f: k(c, [2200, 2500, 2000, 2350]), f2: k(c, [3600, 4000, 3300, 3800]),
               q: 2.2, peak: 0.06, a: 0.04, d: 0.16 });
    return grains(c, { n: 8, span: 0.2, f: 3000, q: 1.2, peak: 0.025, d: 0.008,
                       even: true, fade: false });
  });
  def("forge.rivet", 3, function (c) {
    // Peening a rivet: three quick light taps, each a small tight ring.
    var end = c.t, gaps = [0, 0.11, 0.2];
    for (var i = 0; i < gaps.length; i++) {
      noise(c, { at: gaps[i], type: "highpass", f: 3000, q: 0.8, peak: 0.035, a: 0.001,
                 d: 0.008 });
      end = Math.max(end, bell(c, { at: gaps[i], f: k(c, [2300, 2180, 2420]) * (1 + i * 0.02),
                                    peak: 0.022, d: 0.08 }));
    }
    return end;
  });
  def("forge.weld", 3, function (c) {
    // A forge weld: a heavy blow at white heat and the flux and scale spitting off it.
    knock(c, { f: k(c, [105, 96, 114]), peak: 0.13, lp: 600, d: 0.07 });
    noise(c, { at: 0.01, type: "highpass", f: 3200, q: 0.6, peak: 0.03, a: 0.005, d: 0.3 });
    return grains(c, { at: 0.01, n: k(c, [12, 15, 10]), span: 0.35, f: 4200, q: 1.3,
                       type: "highpass", peak: 0.04, d: 0.006, bunch: 1.8 });
  });

  def("forge.tier.up", 3, function (c) {       // the work glints: two rising steel pings
    var root = k(c, [1568, 1661, 1480]);
    bell(c, { f: root, peak: 0.032, d: 0.35 });
    return bell(c, { at: 0.09, f: root * 1.4983, peak: 0.036, d: 0.5 });
  });
  def("forge.flawless", 3, function (c) {
    // The anvil rung on purpose: a struck chord of steel pings, then the gilt shimmer.
    var root = k(c, [1175, 1109, 1245]);
    var steps = [1, 1.2599, 1.4983, 2], end = c.t;
    knock(c, { f: 150, peak: 0.07, lp: 900, d: 0.04 });
    for (var i = 0; i < steps.length; i++) {
      end = Math.max(end, bell(c, { at: 0.01 + i * 0.07, f: root * steps[i], peak: 0.035,
                                    d: 0.9 + i * 0.15 }));
    }
    noise(c, { at: 0.1, type: "highpass", f: 7500, q: 0.5, peak: 0.01, a: 0.12, d: 0.6 });
    return end;
  });
  def("forge.fail", 3, function (c) {
    // A quench crack: the sharp "tink" smiths dread, then the work falling dull.
    noise(c, { type: "highpass", f: 4200, q: 0.8, peak: 0.06, a: 0.001, d: 0.012 });
    bell(c, { f: k(c, [3300, 3100, 3500]), peak: 0.02, d: 0.06 });
    knock(c, { at: 0.08, f: k(c, [80, 74, 86]), peak: 0.15, lp: 320, d: 0.12, drop: 0.6,
               wave: "sine" });
    return grains(c, { at: 0.1, n: 4, span: 0.08, f: 2600, q: 2, peak: 0.03, d: 0.01 });
  });
  def("forge.land", 3, function (c) {          // onto the rack: wood under, a short clink
    knock(c, { f: k(c, [210, 195, 225]), peak: 0.08, lp: 1100, d: 0.05 });
    return ping(c, { at: 0.01, mul: 0.9, peak: 0.018, d: 0.15 });
  });
  def("forge.assay", 3, function (c) {
    // The touchstone: the metal drawn across black stone, then the balance's small tink.
    noise(c, { f: k(c, [3000, 3300, 2800]), f2: 2200, q: 1.8, peak: 0.035, a: 0.03,
               d: 0.14 });
    return bell(c, { at: 0.22, f: k(c, [2640, 2790, 2490]), peak: 0.02, d: 0.3 });
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
    coals: function (c) {        // the bed of coals settling: a few dry, glassy clinks
      grains(c, { n: 3 + (Math.random() * 3 | 0), span: 0.25, f: 2000, q: 3,
                  peak: 0.014, d: 0.015 });
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
    // The smithy (blacksmithing UI plan §11): a furnace's low roar. Combustion roar is
    // broadband and peaks around 250-500 Hz (see the forge bank's header), so the body is
    // brown noise low-passed there, breathing slowly as the draw rises and falls; a pink
    // band at the peak flutters faster, the flames themselves; a thread of hiss on top.
    // Events: the fire's crackle, a coal popping, the coals settling. It rides the
    // ambience bus like every bed (the Ambience slider), not the forge bus: a player who
    // turns the anvil down has not asked for a quieter room.
    smithy: { beds: [{ src: "brown", type: "lowpass", f: 320, q: 0.7, level: 0.07,
                       gust: 0.07, gustDepth: 0.35 },
                     { f: 420, q: 0.9, level: 0.022, gust: 0.8, gustDepth: 0.5 },
                     { type: "highpass", f: 3500, level: 0.003, gust: 0.2 }],
              events: [["crackle", 0.4, 1.6], ["pop", 3, 9], ["coals", 6, 15]] },
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
      // `o` is the caller's options as given: the forge's sounds read `hardness` and
      // `bath` from it (contracts §11), everything else ignores it.
      var c = { x: x, out: out, t: x.currentTime + 0.005 + delay,
                p: rate * (0.95 + Math.random() * 0.1), v: pickTake(name, s.n), o: opts };
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

  // The engine device's running bed (13-device.js). The owner's reference, 2026-10-02, was
  // "{ASMR} Gears Spinning Cog Machine": not a clock's discrete tick but cogs meshing
  // continuously. Three quiet layers, all following the gears' speed (0 to 1), so the
  // machine winds up when a turn starts and winds down as the gears ease to a stop:
  //   a low rumble of bearings (brown noise, band-passed low),
  //   the fine "zzz" of teeth meshing (pink noise, band-passed high, pulsed at the tooth
  //   rate by a sine LFO, so it has the flutter of cogs rather than a hiss),
  //   and a faint hum under both.
  // On the ui bus, and kept under the ticks: it is a bed, never a drone.
  var SILENT_MACHINE = { speed: function () {}, stop: function () {} };
  function machine() {
    try {
      var x = ensure();
      if (!x || !hasGesture() || masterLevel() <= 0) return SILENT_MACHINE;
      var out = x.createGain();
      out.gain.value = 0;
      out.connect(buses.ui);
      var nodes = [];
      var src = function (kind) {
        var s = x.createBufferSource();
        s.buffer = buf(kind); s.loop = true;
        s.playbackRate.value = 0.94 + Math.random() * 0.12;
        nodes.push(s); return s;
      };
      var band = function (f, q) {
        var b = x.createBiquadFilter(); b.type = "bandpass"; b.frequency.value = f; b.Q.value = q;
        return b;
      };
      // Rumble.
      var rumble = src("brown"), rb = band(240, 0.8), rg = x.createGain();
      rg.gain.value = 0.55;
      rumble.connect(rb); rb.connect(rg); rg.connect(out);
      // Meshing teeth: a pulsed band of pink noise.
      var mesh = src("pink"), mb = band(2600, 2.2), mg = x.createGain();
      mg.gain.value = 0.18;
      var lfo = x.createOscillator(), lfoAmt = x.createGain();
      lfo.type = "sine"; lfo.frequency.value = 10; lfoAmt.gain.value = 0.16;
      lfo.connect(lfoAmt); lfoAmt.connect(mg.gain);
      mesh.connect(mb); mb.connect(mg); mg.connect(out);
      nodes.push(lfo);
      // Hum.
      var hum = x.createOscillator(), hg = x.createGain();
      hum.type = "triangle"; hum.frequency.value = 72; hg.gain.value = 0.12;
      hum.connect(hg); hg.connect(out);
      nodes.push(hum);
      var t0 = x.currentTime + 0.01;
      nodes.forEach(function (n) { try { n.start(t0); } catch (e) { /* */ } });
      var stopped = false;
      return {
        // 0 to 1: the gears' speed. Loudness, the tooth rate and a little pitch follow it.
        speed: function (v) {
          if (stopped) return;
          v = clamp(Number(v), 0, 1);
          var now = x.currentTime;
          out.gain.setTargetAtTime(0.07 * v, now, 0.08);
          lfo.frequency.setTargetAtTime(4 + 16 * v, now, 0.1);
          rb.frequency.setTargetAtTime(160 + 140 * v, now, 0.1);
          hum.frequency.setTargetAtTime(52 + 30 * v, now, 0.1);
        },
        stop: function () {
          if (stopped) return;
          stopped = true;
          var now = x.currentTime;
          out.gain.setTargetAtTime(0, now, 0.12);
          setTimeout(function () {
            nodes.forEach(function (n) { try { n.stop(); } catch (e) { /* */ } });
            try { out.disconnect(); } catch (e) { /* */ }
          }, 900);
        },
      };
    } catch (e) {
      return SILENT_MACHINE;
    }
  }

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
    machine: machine,
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
