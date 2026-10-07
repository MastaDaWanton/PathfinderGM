/* The app's sound: `window.Sound` (docs/herbalism-contracts.md §5.3, revamp plan §11).
 *
 *   Sound.play(name, {volume, rate, delay})   one-shot; unknown names are a silent no-op
 *                                             (forge sounds also read {hardness, bath},
 *                                             enchant sounds {phase}, alchemy sounds
 *                                             {pitch, stage, heat, level, seal})
 *   Sound.loop(name)                          -> {stop()}, for the ambience beds
 *   Sound.burner({kind, liquid})              -> {heat(0..1), stop()}, the alchemy games'
 *                                             flame, whose roar and hiss follow the heat
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
 * bench, forge, enchant, alchemy, works, ambience, combat, verdict) feed one master gain, then a
 * makeup gain, then a gentle limiter, then the
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
  // `enchant` is the Enchanting circle's (enchanting UI plan §11), for the same reason.
  // `works` is the shared In progress panel (37-works.js), which every bench opens; it has
  // no slider of its own and rides on `sound.ui`, as `verdict` rides on `sound.dice`: a
  // player who turns the circle down has not asked for a quieter "your work is ready".
  // `alchemy` is the Alchemy bench's (alchemy UI plan §11), beside the others for the same
  // reason: glassware heard louder or quieter than the anvil or the bowls.
  var BUSES = ["ui", "dice", "bench", "forge", "enchant", "alchemy", "works", "ambience",
               "combat", "verdict"];
  var BUS_PREF = {
    ui: "sound.ui", dice: "sound.dice", bench: "sound.bench", forge: "sound.forge",
    enchant: "sound.enchant", alchemy: "sound.alchemy", works: "sound.ui",
    ambience: "sound.ambience", combat: "sound.combat", verdict: "sound.dice",
  };
  var BUS_DEFAULT = { ui: 0.6, dice: 0.8, bench: 0.8, forge: 0.8, enchant: 0.8, alchemy: 0.8,
                      works: 0.6, ambience: 0.4, combat: 0.7, verdict: 0.8 };
  // Simultaneous one-shots allowed before new ones are dropped. A grind game at full tilt
  // plus a verdict plus ambience events is well under this; a runaway caller is not.
  var MAX_VOICES = 28;
  // Makeup gain between the master volume and the limiter, for every sound here (music is
  // music.js's own <audio> and is not touched). The owner, 2026-10-05: "make all the sounds
  // except for music louder, right now they are maxxed out and i can barely hear them."
  // Measured offline by the forge sound lane with every slider at its top: combat.hit peaked
  // at 0.043 of full scale, a forge strike 0.031-0.037, a quench 0.040-0.044, a herb grind
  // hit 0.021 — about 28 dB under full scale, against music's mastered tracks. x6 (+15.6 dB)
  // puts a hit near 0.26; the limiter after it (threshold -10 dB) still catches a crit, a
  // verdict and a flourish landing together, so the louder mix cannot clip. The sliders keep
  // their meaning: this multiplies whatever they set.
  var MAKEUP = 6;

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
      var makeup = ctx.createGain();
      makeup.gain.value = MAKEUP;
      master.connect(makeup);
      makeup.connect(limiter);
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
  //
  // The gain starts at 0.0001 BEFORE the first event, too. A new GainNode's value is 1 until
  // its first automation event, and a buffer source started at the same (sub-sample) time
  // can render its first sample in the quantum before that event lands: one sample of raw
  // noise at full gain, times the makeup x6. Measured 2026-10-06, rendered offline in Chrome
  // with every slider at its top: forge.flawless peaked at 2.4-5.7 of full scale (a hard
  // clip at the speakers) at exactly its shimmer's start, 0.105 s, and 0.53 without it; the
  // highpassed noise passes that step whole where a lowpass would have smeared it.
  function env(g, t, peak, a, d, hold) {
    var top = Math.max(0.0002, peak);
    g.gain.value = 0.0001;
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
    // Rendered offline in Chromium at 0.06/0.025 it peaked at 0.011, half the herb
    // bench's grind hit (0.021): lost under the smithy bed. Raised to sit beside it.
    noise(c, { f: k(c, [2200, 2500, 2000, 2350]), f2: k(c, [3600, 4000, 3300, 3800]),
               q: 2.2, peak: 0.11, a: 0.04, d: 0.16 });
    return grains(c, { n: 8, span: 0.2, f: 3000, q: 1.2, peak: 0.045, d: 0.008,
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

  /* --- enchant: the Enchanting circle (enchanting UI plan §11, contracts §13) --------- *
   * `Sound.play("enchant.<event>", {phase})`. The plan wrote "pitch by planet"; the owner
   * ruled there are no planets ("this is not earth"), so the favourable time is the essence
   * family's DAY PHASE (rules/sky.py PHASES) and that is what keys the pitch. Grounded in
   * how the real things sound:
   *
   * THE BOWL. The circle's bells are singing bowls, not church bells. Wang, Tsai and Wu
   * measured a struck bowl's ring modes ("Vibration Modes and Sound Characteristic Analysis
   * for Different Sizes of Singing Bowls", MATEC 2018; experimental modes 121.1, 361.7,
   * 700.0/712.5 and 1123.4/1135.2 Hz): partials near 1, 2.99, 5.8 times the fundamental, and
   * every mode a DOUBLET split by 1-2%, which is the slow beating a bowl is known for. So
   * bowl() below is two close sines per mode, the upper modes quieter and shorter (their
   * soft-tipped stick excites the low modes most). A bell "slightly off its note" (flawed)
   * is the same bowl with its doublets pulled wide and its second mode flat: the beat goes
   * from a slow swell to a rough flutter, which the ear hears as wrong without being told.
   * A muffled bell (a miss) is the bowl with a hand on it: the ring stops at once.
   *
   * PITCH BY PHASE, ON A PENTATONIC. Seven phases, seven degrees of a major pentatonic
   * (0 2 4 7 9 12 14 semitones), ordered by the sun's height: midnight lowest, then night,
   * dusk, dawn, afternoon, morning, noon highest (the rising half a step above the falling
   * half). Pentatonic because wind chimes are tuned that way for this exact reason: chimes
   * sound in any order and together, and a scale with no semitones has no pair that
   * clashes (en.wikipedia.org "Wind chime"; leehite.org "Chime Design and Build"). Seats
   * of different phases rung one after another always make a chord. With no phase given
   * the pitch is dawn's, the middle of the seven.
   *
   * THE CHALK. Reuter and Oehler's psychoacoustics of chalkboard squeaking (exploresound.org
   * "Psychoacoustics of chalkboard squeaking") found the 2000-4000 Hz band carries most of
   * the unpleasantness, and attenuating it made the sounds far more pleasant. A sigil is
   * drawn hundreds of times a session, so the chalk is a dry scrape kept under 2 kHz: the
   * grit of chalk on stone, never the squeal.
   *
   * LEVELS. Measured against the forge's equivalents after the makeup gain and the limiter
   * (the owner, 2026-10-05: "i can barely hear them"), rendered offline in Chrome with every
   * slider at its top, median of eight renders: a game's hit (chalk 0.26, seat 0.32, bowl
   * 0.32, draw 0.29, unpick 0.24) beside a forge strike (0.30); a miss 0.25 beside the
   * forge's dead thud (0.25); tier up 0.43 against 0.41, flawless 0.73 against 0.69, fail
   * 0.79 against 0.79; the methods within a fifth of the forge's. Flawed (0.58) sits under
   * fail on purpose, and works.ready (0.36) is a chime from the next room, not an alarm.
   * Every peak literal stays under combat.hit's body (0.24), as the forge's do. */

  // The day phases' pentatonic degrees (semitones above midnight). Dawn, the middle, is
  // the reference pitch; a missing or unknown phase is heard as dawn.
  var PHASE_STEP = { midnight: 0, night: 2, dusk: 4, dawn: 7, afternoon: 9, morning: 12,
                     noon: 14 };
  function phaseMul(c) {
    try {
      var p = String((c.o || {}).phase || "").trim().toLowerCase();
      return PHASE_STEP[p] == null ? 1 : Math.pow(2, (PHASE_STEP[p] - 7) / 12);
    } catch (e) { return 1; }
  }

  // A struck singing bowl (see the header): each mode a doublet `split` apart, the second
  // mode at 2.99 (times `flat` for an off-note bowl), the third at 5.8. `damp` < 1 is a
  // hand on the rim, shortening every mode. Returns when the fundamental has died.
  function bowl(c, o) {
    var at = o.at || 0, f = o.f, p = o.peak, d = (o.d || 1.2) * (o.damp || 1);
    var s = o.split == null ? 0.015 : o.split, r2 = 2.99 * (o.flat || 1);
    tone(c, { at: at, f: f * (1 + s), peak: p * 0.4, a: 0.003, d: d * 0.9 });
    tone(c, { at: at, f: f * r2, peak: p * 0.3, a: 0.002, d: d * 0.6 });
    tone(c, { at: at, f: f * r2 * (1 + s * 0.6), peak: p * 0.2, a: 0.002, d: d * 0.55 });
    tone(c, { at: at, f: f * 5.8, peak: p * 0.12, a: 0.002, d: d * 0.3 });
    return tone(c, { at: at, f: f, peak: p * 0.6, a: 0.003, d: d });
  }

  // A hand on the bowl: the mallet's thump, and the ring choked to a tenth of a second.
  // The one miss sound for every circle game (the frame plays a game's `SOUNDS.miss`).
  function muffled(c) {
    knock(c, { f: k(c, [150, 140, 160, 145]), peak: 0.1, lp: 500, d: 0.06, wave: "sine" });
    noise(c, { src: "pink", type: "lowpass", f: 700, q: 0.7, peak: 0.05, a: 0.004, d: 0.06 });
    return bowl(c, { at: 0.004, f: 392 * phaseMul(c), peak: 0.035, d: 1.2, damp: 0.1 });
  }

  def("enchant.open", 3, function (c) {
    // The candles lit: a match struck and flaring, then the bowl answering faintly.
    noise(c, { f: k(c, [1500, 1650, 1400]), f2: 900, q: 1, peak: 0.1, a: 0.003, d: 0.06 });
    noise(c, { at: 0.05, src: "pink", type: "lowpass", f: 600, f2: 1200, q: 0.7, peak: 0.09,
               a: 0.04, d: 0.3 });
    return bowl(c, { at: 0.3, f: 392 * phaseMul(c), peak: 0.025, d: 1.0 });
  });

  // Choosing a method: the tool taken up (UI plan §11, `enchant.method.<name>` over
  // rules/enchanter.py's six methods).
  var ENCHANT_METHOD = {
    prepare: function (c) {      // the chalk box opened, a stick taken out
      knock(c, { f: k(c, [300, 280, 320]), peak: 0.09, lp: 1600, d: 0.035 });
      return noise(c, { at: 0.08, f: 1100, q: 2, peak: 0.05, d: 0.02 });
    },
    attune: function (c) {       // two phials touched together
      bell(c, { f: k(c, [2400, 2550, 2280]), peak: 0.016, d: 0.25 });
      return bell(c, { at: 0.09, f: k(c, [2400, 2550, 2280]) * 1.1225, peak: 0.013, d: 0.3 });
    },
    bind: function (c) {         // the striker lifted against the bowl's lip
      knock(c, { f: 260, peak: 0.04, lp: 1200, d: 0.03 });
      return bowl(c, { at: 0.01, f: 392 * phaseMul(c) * k(c, [1, 1.004, 0.996]), peak: 0.03,
                       d: 0.6 });
    },
    refine: function (c) {       // a glass rod in a phial: two clinks and a swirl
      bell(c, { f: k(c, [3000, 3150, 2850]), peak: 0.014, d: 0.12 });
      bell(c, { at: 0.1, f: k(c, [3000, 3150, 2850]) * 0.94, peak: 0.011, d: 0.12 });
      return noise(c, { at: 0.05, src: "pink", f: 700, f2: 1100, q: 1.4, peak: 0.035,
                        a: 0.06, d: 0.14 });
    },
    unbind: function (c) {       // the unpicking needle drawn: a thin rising shing
      noise(c, { type: "highpass", f: 3500, f2: 5500, q: 1, peak: 0.03, a: 0.04, d: 0.1 });
      return tone(c, { at: 0.1, f: k(c, [3600, 3800, 3400]), peak: 0.01, d: 0.2 });
    },
    cleanse: function (c) {      // salt sprinkled, and the drop that carries it
      grains(c, { n: 8, span: 0.2, f: 4800, q: 1, type: "highpass", peak: 0.01, d: 0.005 });
      return drop(c, { at: 0.18, f: k(c, [650, 700, 610]), peak: 0.018 });
    },
  };
  Object.keys(ENCHANT_METHOD).forEach(function (m) {
    def("enchant.method." + m, 3, ENCHANT_METHOD[m]);
  });

  def("enchant.roll", 3, function (c) {        // the step's d20, rattled in a horn cup
    knock(c, { f: 280, peak: 0.045, lp: 1000, d: 0.04 });
    return rattle(c, k(c, [2200, 2500, 2350]), k(c, [6, 7, 8]), 0.12);
  });

  // --- the circle's materials (Prepare's pieces and the test step).
  def("enchant.chalk", 4, function (c) {
    // One stroke of a sigil: the stick touching stone, a dry scrape, its grit. Under 2 kHz
    // throughout (see the header: the squeak band is what makes chalk unbearable).
    knock(c, { f: k(c, [420, 380, 460, 400]), peak: 0.06, lp: 1500, d: 0.02, wave: "sine" });
    noise(c, { f: k(c, [900, 1050, 820, 980]), f2: k(c, [1300, 1400, 1200, 1350]), q: 1.1,
               peak: 0.23, a: 0.02, d: 0.12 });
    return grains(c, { n: k(c, [6, 7, 5, 6]), span: 0.12, f: 1500, q: 1.4, peak: 0.11,
                       d: 0.006 });
  });
  def("enchant.salt", 3, function (c) {
    // A line of salt poured: a fine, even patter of grains over a whisper.
    noise(c, { type: "highpass", f: 6000, q: 0.6, peak: 0.01, a: 0.05, d: 0.3 });
    return grains(c, { n: k(c, [16, 18, 14]), span: 0.35, f: 5200, q: 0.8, type: "highpass",
                       peak: 0.028, d: 0.004, even: true });
  });
  def("enchant.ink", 3, function (c) {
    // The quill dipped (a small drop) and drawn on the floor-cloth (a soft scratch, kept
    // under the squeak band like the chalk).
    drop(c, { f: k(c, [600, 640, 560]), peak: 0.032 });
    return noise(c, { at: 0.12, f: 1400, f2: 1700, q: 2, peak: 0.05, a: 0.02, d: 0.14 });
  });
  def("enchant.bell", 3, function (c) {
    // The test step: a small hand-bowl tapped once, clear, in the phase's key.
    noise(c, { type: "highpass", f: 3200, q: 0.7, peak: 0.03, a: 0.001, d: 0.01 });
    return bowl(c, { f: 880 * phaseMul(c) * k(c, [1, 1.003, 0.997]), peak: 0.06, d: 0.9 });
  });

  // --- Attune: a phial set in its seat, at the pitch of its essence's phase.
  def("enchant.seat", 4, function (c) {
    bell(c, { f: k(c, [2900, 3100, 2750, 3000]), peak: 0.025, d: 0.08 });
    return bowl(c, { at: 0.006, f: 523.25 * phaseMul(c), peak: 0.07, d: 0.9 });
  });
  def("enchant.unseat", 3, function (c) {
    // Lifted out again: a short glass slide upward, no ring.
    noise(c, { type: "highpass", f: 3000, f2: 4500, q: 1, peak: 0.03, a: 0.02, d: 0.07 });
    return tone(c, { f: k(c, [1800, 1900, 1700]), f2: 2400, peak: 0.014, d: 0.06 });
  });

  // --- Bind: the bowl struck in time, or muffled.
  def("enchant.bind.hit", 4, function (c) {
    knock(c, { f: k(c, [220, 205, 235, 215]), peak: 0.05, lp: 900, d: 0.03 });
    return bowl(c, { at: 0.003, f: 392 * phaseMul(c) * k(c, [1, 1.003, 0.997, 1.002]),
                     peak: 0.06, d: 1.4 });
  });
  def("enchant.bind.miss", 4, muffled);
  // The same muffled bowl under a name that says what it is for: every circle game's miss
  // (lane U2 names `enchant.bind.miss` in all six games' SOUNDS; either name plays this).
  def("enchant.miss", 4, muffled);

  // --- Refine, Unbind and Cleanse's good strokes.
  def("enchant.draw", 3, function (c) {
    // Essence drawn up out of the phial: a liquid "thwip" rising, a breath, a glass tink.
    drop(c, { f: k(c, [420, 450, 390]), rise: 2.2, peak: 0.1, d: 0.06 });
    noise(c, { type: "highpass", f: 5500, q: 0.7, peak: 0.03, a: 0.03, d: 0.12 });
    return bell(c, { at: 0.07, f: k(c, [2200, 2330, 2080]), peak: 0.03, d: 0.2 });
  });
  def("enchant.unpick", 3, function (c) {
    // A thread of the old working picked loose: a tight little pluck and its tick.
    noise(c, { type: "highpass", f: 4000, q: 0.8, peak: 0.09, a: 0.001, d: 0.006 });
    noise(c, { f: 2500, f2: 1500, q: 1.5, peak: 0.07, a: 0.01, d: 0.06 });
    return tone(c, { type: "triangle", f: k(c, [1300, 1450, 1200]), f2: k(c, [1270, 1420, 1175]),
                     lp: 3000, peak: 0.12, d: 0.07 });
  });

  // --- the verdicts (lane U3's stage), each in the phase's key.
  def("enchant.tier.up", 3, function (c) {     // two rising bowls
    var root = k(c, [659, 698, 622]) * phaseMul(c);
    bowl(c, { f: root, peak: 0.035, d: 0.5 });
    return bowl(c, { at: 0.09, f: root * 1.4983, peak: 0.038, d: 0.7 });
  });
  def("enchant.flawless", 3, function (c) {
    // The circle rung on purpose: a pentatonic stack of bowls, then the gilt shimmer.
    var root = k(c, [523, 554, 494]) * phaseMul(c);
    var steps = [1, 1.1225, 1.2599, 1.4983, 2], end = c.t;
    for (var i = 0; i < steps.length; i++) {
      end = Math.max(end, bowl(c, { at: i * 0.07, f: root * steps[i], peak: 0.035,
                                    d: 1.4 + i * 0.15 }));
    }
    noise(c, { at: 0.1, type: "highpass", f: 7500, q: 0.5, peak: 0.012, a: 0.12, d: 0.7 });
    return end;
  });
  def("enchant.flawed", 3, function (c) {
    // A bowl slightly off its note (UI plan §11): doublets pulled wide, the second mode
    // flat, the note sagging; and a candle guttering. It never says which curse.
    var root = k(c, [523, 554, 494]) * phaseMul(c);
    noise(c, { src: "pink", f: 900, f2: 300, q: 0.8, peak: 0.05, a: 0.01, d: 0.25 });
    tone(c, { at: 0.02, f: root, f2: root * 0.97, glide: 0.8, peak: 0.03, a: 0.003, d: 0.9 });
    return bowl(c, { at: 0.02, f: root, peak: 0.09, d: 1.0, split: 0.045, flat: 0.95 });
  });
  def("enchant.fail", 3, function (c) {
    // The glow falls away: the candles snuffed, a dull thud, dust settling.
    noise(c, { src: "pink", f: 800, f2: 250, q: 0.8, peak: 0.06, a: 0.005, d: 0.2 });
    knock(c, { at: 0.04, f: k(c, [70, 64, 76]), peak: 0.18, lp: 300, d: 0.14, drop: 0.6,
               wave: "sine" });
    noise(c, { at: 0.08, src: "pink", type: "lowpass", f: 800, f2: 200, q: 0.7, peak: 0.05,
               a: 0.05, d: 0.6 });
    return grains(c, { at: 0.12, n: 5, span: 0.25, f: 1800, q: 1.5, peak: 0.035, d: 0.01 });
  });
  def("enchant.land", 3, function (c) {
    // Wrapped in its cloth and set on the shelf: a rustle, a soft wooden thump, the faint
    // clink of the work inside.
    noise(c, { src: "pink", f: k(c, [1800, 2000, 1650]), f2: 900, q: 0.7, peak: 0.018,
               a: 0.03, d: 0.15 });
    knock(c, { at: 0.14, f: k(c, [190, 175, 205]), peak: 0.025, lp: 800, d: 0.05 });
    return bell(c, { at: 0.15, f: k(c, [2600, 2750, 2450]), peak: 0.006, d: 0.15 });
  });
  def("enchant.read", 3, function (c) {
    // The essence answers from its phial: a rubbed glass rim swelling and fading (a slow
    // attack, a near-pure tone and its slow beat) over a breath of air.
    var f = k(c, [1046, 1108, 988]) * phaseMul(c);
    tone(c, { f: f * 1.004, peak: 0.011, a: 0.25, hold: 0.2, d: 0.7 });
    noise(c, { type: "highpass", f: 5000, q: 0.6, peak: 0.005, a: 0.2, d: 0.5 });
    return tone(c, { f: f, peak: 0.018, a: 0.25, hold: 0.2, d: 0.7 });
  });
  def("enchant.identify", 3, function (c) {
    // The item's sigils show and fade: three quick glass notes up the pentatonic, and a
    // whisper as they go.
    var root = k(c, [1318, 1397, 1245]) * phaseMul(c), steps = [1, 1.1225, 1.4983], end = c.t;
    for (var i = 0; i < steps.length; i++) {
      end = Math.max(end, bell(c, { at: i * 0.07, f: root * steps[i], peak: 0.015, d: 0.4 }));
    }
    noise(c, { at: 0.05, type: "highpass", f: 4000, f2: 6000, q: 0.7, peak: 0.008, a: 0.1,
               d: 0.4 });
    return end;
  });

  /* --- works: the shared In progress panel (37-works.js), every bench's ------------- */
  def("works.ready", 3, function (c) {
    // Work has become ready while you were away: a soft two-note chime, a shop-door bell
    // heard from the next room, never an alarm.
    var root = k(c, [1568, 1661, 1480]);
    bell(c, { f: root, peak: 0.03, d: 0.6 });
    return bell(c, { at: 0.12, f: root * 1.2599, peak: 0.026, d: 0.7 });
  });
  def("works.collect", 3, function (c) {
    // The finished work lifted from the shelf into the pack: cloth, then leather.
    noise(c, { src: "pink", f: k(c, [1600, 1750, 1450]), f2: 900, q: 0.7, peak: 0.02,
               a: 0.02, d: 0.12 });
    noise(c, { at: 0.1, src: "pink", type: "lowpass", f: k(c, [600, 520, 680]), q: 0.7,
               peak: 0.03, a: 0.006, d: 0.1 });
    return tone(c, { at: 0.1, f: 190, f2: 140, glide: 0.1, peak: 0.015, d: 0.1 });
  });

  /* --- alchemy: the Alchemy bench (alchemy UI plan §11, contracts §11-§12, lane U5) --- *
   * `Sound.play("alchemy.<event>", {pitch, stage, heat, level, seal})`, and `Sound.burner()`
   * for the games' flame. Grounded in how the real things sound:
   *
   * GLASS. A struck glass vessel rings in its flexural ring modes. For a thin ring, Rayleigh's
   * bending modes stand at n(n²-1)/sqrt(n²+1), so 1, 2.83 and 5.42 times the lowest, and
   * a real glass splits each into a close doublet (Jundt, Radu, Fort, Duda, Vach and
   * Fletcher, "Vibrational modes of partly filled wine glasses", JASA 2006: "the splitting
   * is only about 4 Hz" on an empty glass). Liquid LOWERS the ring, as w² = w0²/(1 + a·h^n)
   * with their fitted n of about 5.5, so a clink knows how full the vessel is: almost no
   * change to half full, then a fall of about a third at the brim (a = 1 here, our choice;
   * the paper's constant depends on the glass). Small labware rings high and short.
   *
   * BUBBLES AND DRIPS. A drop's "plink" is the bubble it traps, ringing at its Minnaert
   * frequency, f·a ≈ 3.26 m/s for air in water (a the radius), and rising as the bubble
   * nears the surface (Phillips, Agarwal and Jordan, "The Sound Produced by a Dripping Tap
   * is Driven by Resonant Oscillations of an Entrapped Air Bubble", Scientific Reports
   * 2018). So a 1 mm bubble plinks at 3.3 kHz, a 4 mm one at 800 Hz, and drop() rises.
   * EFFERVESCENCE is the same physics in miniature: champagne's "sizzling or crackling" is
   * short tone bursts a few cycles long, 6.7 kHz for a 0.94 mm bubble (Physics Today,
   * "Champagne acoustics"), so the fizz is many tiny high grains, never a hiss.
   *
   * HEAT AND BOILING. A kettle is loudest BEFORE it boils: subcooled bubbles form on the
   * hot floor and collapse before they reach the surface, ringing the vessel, and the noise
   * peaks near 80-90 °C and drops back somewhat at a full boil (Aljishi and Tatarkiewicz,
   * "Why does heating water in a kettle produce sound?", Am. J. Phys. 1991). So the boil and
   * the burner's liquid layer follow simmer(): rising to a peak at 0.85 of the heat and
   * easing at the top. The FLAME's roar is broadband and low (see the forge bank's header,
   * "Combustion roar of premix burners"), louder and brighter as the fuel is fed; a small
   * flame flickers about ten to fifteen times a second (the pool-fire flicker correlation,
   * f ≈ 1.5/sqrt(D), gives 15 Hz at a centimetre; Hamins, Yang and Kashiwagi 1992, cited
   * from memory of the correlation and not re-read for this lane).
   *
   * POURING. The pitch of a pour is the air column left above the liquid, a quarter-wave
   * pipe, so it climbs as the vessel fills, and people judge "nearly full" from that sound
   * alone (Cabe and Pittenger, "Human sensitivity to acoustic information from vessel
   * filling", JEP:HPP 2000). Bottle's pour to the mark therefore rises with `level`, and a
   * player can hear the mark coming.
   *
   * THE CORK. Pulling a stopper is a Helmholtz resonator, the air in the neck bouncing on
   * the air in the body; a beer bottle's pop measured a single strong peak near 700 Hz
   * ("On the popping sound and liquid sloshing when opening a beer bottle", Physics of
   * Fluids 2025). A vial's neck is smaller, so it pops higher. Pressing one IN is the
   * squeak of cork on glass and a soft seat, no pop.
   *
   * BREAKING GLASS. Glass-break detectors listen for exactly two things: the low thump of
   * the pane flexing, centred near 350 Hz, then the high scatter of fragments centred near
   * 6.5 kHz (Cypress, "Consumer or Industrial Acoustic Glass Break Detector", AN2186). A
   * splash flask's shatter is that pair with the contents' splash, and a thermal crack is
   * the tink alone, without the thump of a break.
   *
   * THE SCRAPE. Scraping a crust off glass is the chalkboard's danger (the enchant bank's
   * header: Reuter and Oehler, the 2000-4000 Hz band), so it stays under 2 kHz.
   *
   * PITCH. `{pitch: n}` is a step on a major pentatonic (0 2 4 7 9, then up an octave), the
   * same no-clash ladder the enchant bowls use, so a game can climb it per drop or per stage
   * and nothing ever jars. `{stage}` names a Transmute colour stage (nigredo 0, albedo 1,
   * citrinitas 2, rubedo 3). Only the tonal events read it; a whump or a shatter ignores it.
   *
   * LEVELS. Measured through the real chain (bus, master, makeup x6, limiter) rendered
   * offline in Chrome, every slider at its top, median of eight renders; see the test file
   * for the figures. Every peak literal stays under combat.hit's body (0.24). */

  var PENTA = [0, 2, 4, 7, 9];
  var STAGE_STEP = { nigredo: 0, albedo: 1, citrinitas: 2, rubedo: 3 };
  // The semitones above the home note that `{pitch}` (or `{stage}`) asks for.
  function degree(c) {
    try {
      var o = c.o || {}, n = o.pitch;
      if (n == null && o.stage != null) {
        var s = STAGE_STEP[String(o.stage).trim().toLowerCase()];
        n = s == null ? 0 : s;
      }
      n = Math.round(Number(n));
      if (!isFinite(n)) return 0;
      n = clamp(n, -5, 14);
      var oct = Math.floor(n / 5);
      return 12 * oct + PENTA[n - oct * 5];
    } catch (e) { return 0; }
  }
  function heatOf(c, dflt) {
    var h = Number((c.o || {}).heat);
    return isFinite(h) && (c.o || {}).heat != null ? clamp(h, 0, 1) : dflt;
  }
  function levelOf(c, dflt) {
    var l = Number((c.o || {}).level);
    return isFinite(l) && (c.o || {}).level != null ? clamp(l, 0, 1) : dflt;
  }
  // The kettle's curve (see the header): quiet cold, loudest just under the boil.
  function simmer(h) {
    h = clamp(h, 0, 1);
    return h <= 0.85 ? Math.pow(h / 0.85, 1.6) : 1 - (h - 0.85) / 0.15 * 0.3;
  }

  // A struck glass vessel (see the header): the contact tick, the lowest ring mode as a
  // doublet 0.6% apart, the 2.83 and 5.42 modes quieter and shorter. `fill` (0..1) lowers
  // and damps it as liquid does.
  function glass(c, o) {
    var at = o.at || 0, p = o.peak, fill = o.fill || 0;
    var f = o.f / Math.sqrt(1 + Math.pow(fill, 5.5));
    var d = (o.d || 0.35) * (1 - 0.45 * fill);
    noise(c, { at: at, type: "highpass", f: 4200, q: 0.7, peak: p * 0.45, a: 0.001,
               d: 0.006 });
    tone(c, { at: at, f: f * 1.006, peak: p * 0.35, a: 0.0015, d: d * 0.9 });
    tone(c, { at: at, f: f * 2.83, peak: p * 0.3, a: 0.0015, d: d * 0.45 });
    tone(c, { at: at, f: f * 5.42, peak: p * 0.12, a: 0.0015, d: d * 0.25 });
    return tone(c, { at: at, f: f, peak: p * 0.6, a: 0.0015, d: d });
  }

  // One bubble, by radius in millimetres (Minnaert, see the header): 3.26 kHz per mm⁻¹.
  function bubble(c, o) {
    return drop(c, { at: o.at, f: 3260 / o.mm, rise: o.rise || 1.5, peak: o.peak,
                     d: o.d || (0.03 + o.mm * 0.012) });
  }

  // A run of fizz: `n` effervescent bursts of a few cycles each, bubbles of 0.5-1.5 mm.
  function fizz(c, o) {
    var end = c.t, at0 = o.at || 0;
    for (var i = 0; i < o.n; i++) {
      var mm = (o.mm || 0.5) + Math.random() * (o.spread || 1);
      var when = at0 + o.span * Math.pow(Math.random(), o.bunch || 1);
      var f = 3260 / mm;
      // One cycle up, four down: a burst a few cycles long, as measured, not a ping.
      end = Math.max(end, tone(c, { at: when, f: f, f2: f * 1.15, glide: 4 / f,
                                    peak: o.peak * (0.5 + Math.random() * 0.5),
                                    a: 1 / f, d: 4 / f }));
    }
    return end;
  }

  // A pour: a stream of noise gurgling on a slow wobble, through the air column's band
  // (see the header) which climbs from `from` to `to` as the vessel fills.
  function pour(c, o) {
    var x = c.x, t = c.t + (o.at || 0), dur = o.dur || 0.45;
    var col = function (lv) { return 650 / (1 - 0.88 * clamp(lv, 0, 0.98)); };
    var src = x.createBufferSource(); src.buffer = buf("pink");
    var f = x.createBiquadFilter(); f.type = "bandpass"; f.Q.value = o.q || 4;
    f.frequency.setValueAtTime(hz(col(o.from) * c.p), t);
    f.frequency.exponentialRampToValueAtTime(hz(col(o.to) * c.p), t + dur);
    var lfo = x.createOscillator(); lfo.frequency.value = o.wobble || 9;
    var depth = x.createGain(); depth.gain.value = col(o.from) * 0.25;
    lfo.connect(depth); depth.connect(f.frequency);
    var g = x.createGain();
    var end = env(g, t, o.peak, 0.04, 0.12, Math.max(0.01, dur - 0.16));
    src.connect(f); f.connect(g); g.connect(o.dest || c.out);
    // The splash under the stream, low and broad.
    noise(c, { at: o.at, src: "pink", type: "lowpass", f: 900, q: 0.6, peak: o.peak * 0.45,
               a: 0.03, hold: Math.max(0.01, dur - 0.13), d: 0.1 });
    src.start(t, Math.random() * 2); src.stop(end + 0.03);
    lfo.start(t); lfo.stop(end + 0.03);
    return end;
  }

  // A defined alchemy sound that reads `{pitch}`: the step's ratio rides on the play's
  // own pitch multiplier, so every partial moves together.
  function pitched(fn) {
    return function (c) {
      var m = Math.pow(2, degree(c) / 12);
      return fn({ x: c.x, out: c.out, t: c.t, p: c.p * m, v: c.v, o: c.o });
    };
  }

  def("alchemy.open", 3, function (c) {
    // The spirit lamp lit (UI plan §10): a match struck, the wick catching with a soft
    // low breath of flame, then the flask on its ring answering with a small clink.
    noise(c, { f: k(c, [1600, 1750, 1450]), f2: 900, q: 1, peak: 0.07, a: 0.003, d: 0.05 });
    noise(c, { at: 0.06, src: "brown", type: "lowpass", f: 180, f2: k(c, [620, 560, 680]),
               q: 0.7, peak: 0.091, a: 0.08, d: 0.4 });
    return glass(c, { at: 0.34, f: k(c, [1180, 1250, 1120]), peak: 0.035, d: 0.4 });
  });

  // Choosing a method: the vessel swapped in (UI plan §10, "a glass clink"), one per
  // operation in rules/alchemist.py METHODS.
  var ALCHEMY_METHOD = {
    dissolve: function (c) {     // the round flask set on its ring, the solvent stirring
      knock(c, { f: k(c, [260, 240, 280]), peak: 0.043, lp: 1200, d: 0.03, wave: "sine" });
      glass(c, { at: 0.005, f: k(c, [900, 960, 850]), fill: 0.5, peak: 0.051, d: 0.35 });
      return noise(c, { at: 0.12, src: "pink", f: 500, f2: 900, q: 1.4, peak: 0.043,
                        a: 0.06, d: 0.14 });
    },
    calcine: function (c) {      // the clay crucible seated in its triangle: a dull ceramic
      knock(c, { f: k(c, [330, 310, 350]), peak: 0.076, lp: 1500, d: 0.04, wave: "sine" });
      return grains(c, { at: 0.03, n: 5, span: 0.1, f: 1400, q: 1.5, peak: 0.043, d: 0.012 });
    },
    filter: function (c) {       // the funnel dropped in its ring, the cloth unfolded
      glass(c, { f: k(c, [1300, 1380, 1230]), peak: 0.05, d: 0.3 });
      return noise(c, { at: 0.1, f: 1800, f2: 1200, q: 1.2, peak: 0.05, a: 0.03, d: 0.12 });
    },
    distill: function (c) {      // the alembic's head seated: a short glass-on-glass grind
      noise(c, { f: k(c, [1500, 1650, 1400]), q: 3, peak: 0.019, a: 0.04, d: 0.12 });
      grains(c, { n: 6, span: 0.14, f: 1700, q: 3, peak: 0.011, d: 0.008, even: true });
      return glass(c, { at: 0.16, f: k(c, [520, 560, 490]), peak: 0.016, d: 0.5 });
    },
    react: function (c) {        // the dropper's bulb squeezed, one drop let fall
      tone(c, { type: "triangle", f: k(c, [320, 300, 340]), f2: 210, glide: 0.08, lp: 800,
                peak: 0.017, a: 0.01, d: 0.08 });
      return bubble(c, { at: 0.14, mm: k(c, [2.6, 2.4, 2.8]), peak: 0.02 });
    },
    sublime: function (c) {      // the aludel's lid set on: ceramic and a glass ring
      knock(c, { f: k(c, [280, 260, 300]), peak: 0.07, lp: 1400, d: 0.035, wave: "sine" });
      return glass(c, { at: 0.01, f: k(c, [740, 790, 700]), peak: 0.04, d: 0.35 });
    },
    bottle: function (c) {       // the rack of vials: three small clinks along the row
      var end = c.t, base = k(c, [2300, 2450, 2200]);
      for (var i = 0; i < 3; i++) {
        end = Math.max(end, glass(c, { at: i * 0.07 + Math.random() * 0.02,
                                       f: base * (1 + i * 0.06), peak: 0.015, d: 0.18 }));
      }
      return end;
    },
    transmute: function (c) {    // the athanor's iron door, and its fire drawing up
      bell(c, { f: k(c, [196, 185, 208]), peak: 0.025, d: 0.35 });
      knock(c, { f: k(c, [120, 110, 130]), peak: 0.04, lp: 600, d: 0.06 });
      return noise(c, { at: 0.1, src: "brown", type: "lowpass", f: 220, f2: 420, q: 0.7,
                        peak: 0.06, a: 0.2, d: 0.5 });
    },
    assay: function (c) {        // a glass slide laid on the bench, drawn a finger's width
      glass(c, { f: k(c, [3000, 3200, 2850]), peak: 0.054, d: 0.15 });
      return noise(c, { at: 0.05, f: 1400, f2: 1700, q: 2, peak: 0.063, a: 0.03, d: 0.1 });
    },
  };
  Object.keys(ALCHEMY_METHOD).forEach(function (m) {
    def("alchemy.method." + m, 3, ALCHEMY_METHOD[m]);
  });

  // A material landing in a slot (UI plan §11: powder, liquid, glass), and the words a
  // caller may have instead: the alchemy kinds (contracts §3) and the intermediate forms
  // (rules/alchemist.py: solution, calx, sublimate, spirit, filtrate, admixture).
  var ALCHEMY_DROP = {
    powder: function (c) {       // a pinch tipped in: a soft sift and its settling
      noise(c, { src: "pink", type: "highpass", f: k(c, [2400, 2700, 2200]), q: 0.6,
                 peak: 0.06, a: 0.02, d: 0.14 });
      return grains(c, { at: 0.02, n: k(c, [8, 10, 9]), span: 0.14, f: 3000, q: 0.9,
                         type: "highpass", peak: 0.035, d: 0.005 });
    },
    liquid: function (c) {       // poured in: a short splash and the bubbles it traps
      noise(c, { f: 1600, f2: 800, q: 0.8, peak: 0.053, a: 0.004, d: 0.12 });
      bubble(c, { at: 0.03, mm: k(c, [3.5, 4, 3.2]), peak: 0.038 });
      return bubble(c, { at: 0.08, mm: k(c, [2.2, 2.6, 2]), peak: 0.022 });
    },
    glass: function (c) {        // a vial or flask set down: wood under, the glass rings
      knock(c, { f: k(c, [230, 215, 245]), peak: 0.038, lp: 1300, d: 0.03 });
      return glass(c, { at: 0.003, f: k(c, [2100, 2250, 1980]), peak: 0.045, d: 0.25 });
    },
    crystal: function (c) {      // a salt or a crust: a dry glassy patter
      grains(c, { n: k(c, [5, 7, 6]), span: 0.1, f: 3800, q: 4, peak: 0.078, d: 0.012 });
      return glass(c, { at: 0.04, f: k(c, [3300, 3500, 3150]), peak: 0.023, d: 0.1 });
    },
    wet: function (c) {          // a gland: soft and wet
      noise(c, { src: "pink", f: 700, f2: 300, q: 2, peak: 0.105, a: 0.01, d: 0.08 });
      return bubble(c, { at: 0.02, mm: 9, rise: 1.4, peak: 0.045, d: 0.05 });
    },
  };
  var ALCHEMY_DROP_ALIAS = {
    reagent: "powder", salt: "crystal", catalyst: "crystal", treatment: "powder",
    calx: "powder", precipitate: "powder", dust: "powder", solid: "powder",
    solvent: "liquid", essence: "liquid", solution: "liquid", filtrate: "liquid",
    spirit: "liquid", admixture: "liquid", intermediate: "liquid",
    sublimate: "crystal", gland: "wet", vessel: "glass", phial: "glass", vial: "glass",
    flask: "glass",
    // A finished product, by its family (alchemist.json bench.families): it is in glass.
    potion: "glass", oil: "glass", splash: "glass", cloud: "glass", tool: "glass",
  };
  Object.keys(ALCHEMY_DROP).forEach(function (f) {
    def("alchemy.drop." + f, 3, ALCHEMY_DROP[f]);
  });
  Object.keys(ALCHEMY_DROP_ALIAS).forEach(function (f) {
    def("alchemy.drop." + f, 3, ALCHEMY_DROP[ALCHEMY_DROP_ALIAS[f]]);
  });

  def("alchemy.roll", 3, function (c) {        // the step's d20, rattled in a horn cup
    knock(c, { f: 270, peak: 0.045, lp: 1000, d: 0.04 });
    rattle(c, k(c, [2300, 2600, 2450]), k(c, [6, 7, 8]), 0.12);
    return glass(c, { at: 0.26, f: k(c, [2900, 3100, 2750]), peak: 0.012, d: 0.1 });
  });

  // --- the work's own sounds, heard in the games and on the stage.
  def("alchemy.pour", 4, function (c) {
    // Into the vessel, the pitch climbing with the level (see the header). `level` is
    // where the liquid stands when this pour starts; each pour fills a little more.
    var lv = levelOf(c, 0.3);
    return pour(c, { from: lv, to: Math.min(0.98, lv + 0.12), peak: 0.068,
                     wobble: k(c, [9, 11, 8, 10]), dur: k(c, [0.42, 0.48, 0.4, 0.45]) });
  });
  def("alchemy.stir", 4, function (c) {
    // A glass rod drawn round the flask: the liquid swirling there and back, and the rod's
    // two light touches on the wall.
    noise(c, { src: "pink", f: 480, f2: k(c, [1000, 1100, 920, 1050]), q: 1.5, peak: 0.102,
               a: 0.08, d: 0.1 });
    noise(c, { at: 0.15, src: "pink", f: 1000, f2: 460, q: 1.5, peak: 0.075, a: 0.04,
               d: 0.12 });
    glass(c, { at: 0.06, f: k(c, [1500, 1600, 1420, 1550]), fill: 0.6, peak: 0.034, d: 0.2 });
    return glass(c, { at: 0.2, f: k(c, [1500, 1600, 1420, 1550]) * 0.97, fill: 0.6,
                      peak: 0.024, d: 0.2 });
  });
  def("alchemy.bubble", 4, pitched(function (c) {
    // One to three bubbles breaking, 2.5-4.5 mm: more of them, and quicker, with `heat`.
    var h = heatOf(c, 0.5), n = 1 + Math.round(h * 2), end = c.t;
    for (var i = 0; i < n; i++) {
      end = Math.max(end, bubble(c, { at: i * (0.09 - h * 0.04) + Math.random() * 0.02,
                                      mm: k(c, [3.2, 2.7, 4.2, 3.6]) * (0.85 + Math.random() * 0.3),
                                      peak: 0.06 * (1 - i * 0.2) }));
    }
    return end;
  }));
  def("alchemy.boil", 3, function (c) {
    // A rolling boil: the vessel's seethe and a run of bubbles of every size, on the
    // kettle's curve (loudest at 0.85 heat, easing at the top).
    var s = simmer(heatOf(c, 0.85)), n = 4 + Math.round(6 * s), end;
    end = noise(c, { src: "pink", f: k(c, [450, 520, 400]), q: 1.6, peak: 0.006 + 0.021 * s,
                     a: 0.06, hold: 0.25, d: 0.25 });
    for (var i = 0; i < n; i++) {
      end = Math.max(end, bubble(c, { at: Math.random() * 0.55, mm: 1.8 + Math.random() * 3.5,
                                      peak: (0.012 + 0.021 * s) * (0.5 + Math.random() * 0.5) }));
    }
    return end;
  });
  def("alchemy.drip", 4, pitched(function (c) {
    // One drop of distillate into the receiver: a tiny tick and the trapped bubble's plink.
    noise(c, { type: "highpass", f: 3500, q: 0.7, peak: 0.025, a: 0.001, d: 0.004 });
    return bubble(c, { at: 0.004, mm: k(c, [2.8, 2.5, 3.1, 2.65]), rise: 1.7, peak: 0.141 });
  }));
  def("alchemy.fizz", 3, function (c) {
    // Effervescence (see the header): a quick cloud of sub-millimetre bursts, thinning.
    return fizz(c, { n: k(c, [26, 32, 22]), span: 0.45, mm: 0.45, spread: 0.9, bunch: 1.8,
                     peak: 0.034 });
  });
  def("alchemy.hiss", 3, function (c) {
    // Vapour escaping: brighter and louder with `heat`, a breath when cool, steam when hot.
    var h = heatOf(c, 0.6);
    return noise(c, { type: "bandpass", f: (2400 + 3200 * h) * k(c, [1, 1.08, 0.93]),
                      f2: (1800 + 2400 * h), q: 0.8, peak: 0.024 + 0.048 * h, a: 0.05,
                      d: 0.35 + 0.25 * h });
  });

  def("alchemy.chime", 3, pitched(function (c) {
    // A Transmute stage sealed at its peak: a glass struck clear, up the pentatonic by
    // `stage` (or `pitch`). Rubedo, the last stage of the Great Work, rings its fifth and
    // octave with it, at the level of the one glass: a chord, not a louder note.
    var f = k(c, [880, 932, 831]);
    if (String((c.o || {}).stage || "").trim().toLowerCase() !== "rubedo") {
      return glass(c, { f: f, peak: 0.12, d: 1.1 });
    }
    glass(c, { f: f, peak: 0.06, d: 1.1 });
    glass(c, { at: 0.06, f: f * 1.4983, peak: 0.035, d: 1.2 });
    return glass(c, { at: 0.12, f: f * 2, peak: 0.025, d: 1.3 });
  }));

  // The stopper going IN: cork squeaking on the glass and seating with a soft thup, or,
  // with `{seal: "wax"}`, a wax seal pressed.
  function cork(c) {
    tone(c, { type: "sawtooth", f: k(c, [980, 1100, 900]), f2: k(c, [1250, 1380, 1150]),
              glide: 0.09, lp: 1800, peak: 0.015, a: 0.01, d: 0.09 });
    noise(c, { f: 1300, q: 3, peak: 0.025, a: 0.01, d: 0.09 });
    return tone(c, { at: 0.11, f: k(c, [620, 660, 590]), f2: 520, glide: 0.04, peak: 0.04,
                     a: 0.002, d: 0.05 });
  }
  function wax(c) {
    noise(c, { src: "pink", type: "lowpass", f: 700, q: 0.7, peak: 0.104, a: 0.01, d: 0.1 });
    knock(c, { at: 0.02, f: k(c, [200, 185, 215]), peak: 0.078, lp: 800, d: 0.05, wave: "sine" });
    return noise(c, { at: 0.12, f: 1100, f2: 800, q: 2, peak: 0.033, a: 0.02, d: 0.08 });
  }
  def("alchemy.stopper", 3, function (c) {
    return String((c.o || {}).seal || "").toLowerCase() === "wax" ? wax(c) : cork(c);
  });
  def("alchemy.seal", 3, wax);
  def("alchemy.uncork", 3, function (c) {
    // Pulled: the squeak, then the Helmholtz pop of the neck, higher than a bottle's.
    tone(c, { type: "sawtooth", f: k(c, [1100, 1200, 1000]), f2: 900, glide: 0.08, lp: 1800,
              peak: 0.009, a: 0.01, d: 0.08 });
    noise(c, { at: 0.09, f: 1200, q: 0.9, peak: 0.02, a: 0.001, d: 0.025 });
    return tone(c, { at: 0.09, f: k(c, [980, 1050, 920]), f2: 900, glide: 0.03, peak: 0.044,
                     a: 0.001, d: 0.06 });
  });

  def("alchemy.glass.tick", 4, pitched(function (c) {
    // A beat pip: the smallest glass tick, the vessel ticking as it warms.
    return glass(c, { f: k(c, [2640, 2800, 2490, 2720]), peak: 0.039, d: 0.09 });
  }));
  def("alchemy.clink", 4, pitched(function (c) {
    // Glass touching glass: the rod on a flask, a vial on the rack.
    return glass(c, { f: k(c, [1760, 1865, 1661, 1820]), fill: levelOf(c, 0), peak: 0.091,
                      d: 0.3 });
  }));
  def("alchemy.crack", 3, function (c) {
    // Glass cracking under heat: a sharp tink and a run of crackle, no break (see the
    // header: no flexing thump, no falling fragments).
    noise(c, { type: "highpass", f: 4500, q: 0.8, peak: 0.12, a: 0.001, d: 0.01 });
    tone(c, { f: k(c, [3600, 3400, 3800]), peak: 0.06, a: 0.001, d: 0.05 });
    return grains(c, { at: 0.02, n: k(c, [6, 8, 7]), span: 0.18, f: 5200, q: 2.5,
                       peak: 0.075, d: 0.006, bunch: 1.6 });
  });
  function shatter(c) {
    // The flex thump (about 350 Hz), the fragments (centred near 6.5 kHz) falling over half
    // a second as single high glass pings, and the contents' splash.
    knock(c, { f: k(c, [350, 330, 370]), peak: 0.14, lp: 900, d: 0.05, wave: "sine" });
    noise(c, { at: 0.005, type: "highpass", f: 5000, q: 0.6, peak: 0.08, a: 0.001, d: 0.08 });
    var end = c.t, n = k(c, [9, 11, 8]);
    for (var i = 0; i < n; i++) {
      var when = 0.01 + 0.5 * Math.pow(Math.random(), 1.7);
      end = Math.max(end, tone(c, { at: when, f: 4500 + Math.random() * 4000,
                                    peak: 0.03 * (0.4 + Math.random() * 0.6),
                                    a: 0.001, d: 0.03 + Math.random() * 0.05 }));
    }
    noise(c, { at: 0.02, src: "pink", f: 1400, f2: 600, q: 0.8, peak: 0.08, a: 0.005, d: 0.2 });
    return Math.max(end, grains(c, { at: 0.03, n: 10, span: 0.45, f: 6500, q: 1.5,
                                     type: "highpass", peak: 0.045, d: 0.008, bunch: 1.5 }));
  }
  def("alchemy.shatter", 3, shatter);
  // A splash flask thrown in a fight breaks on the combat bus, under the Combat slider.
  def("combat.shatter", 3, shatter);

  def("alchemy.flare", 3, function (c) {
    // A volatile mishap (UI plan §7.5): the vapour catching all at once, a low whump of air,
    // the flame's roar rising and falling, then crackle and a fizzling hiss.
    tone(c, { f: k(c, [62, 56, 68]), f2: 38, glide: 0.25, peak: 0.23, a: 0.008, d: 0.3 });
    noise(c, { src: "brown", type: "lowpass", f: 140, f2: 520, q: 0.7, peak: 0.23, a: 0.02,
               d: 0.55 });
    noise(c, { at: 0.04, src: "pink", type: "bandpass", f: 900, f2: 400, q: 0.7, peak: 0.15,
               a: 0.05, d: 0.6 });
    noise(c, { at: 0.2, type: "highpass", f: 3500, q: 0.6, peak: 0.03, a: 0.1, d: 0.6 });
    return grains(c, { at: 0.12, n: k(c, [12, 15, 10]), span: 0.7, f: 3200, q: 1.3,
                       type: "highpass", peak: 0.11, d: 0.007, bunch: 1.4 });
  });

  // --- a game's good beat and its miss (UI plan §10: "a bloom of colour, a soft chime";
  // "a dull fizz, vapour puffs").
  def("alchemy.hit", 4, pitched(function (c) {
    bubble(c, { mm: k(c, [3, 2.7, 3.3, 2.9]), peak: 0.034 });
    return glass(c, { at: 0.03, f: k(c, [1318, 1397, 1245, 1356]), peak: 0.053, d: 0.55 });
  }));
  def("alchemy.miss", 4, function (c) {
    // A dull fizz in the low bands, a puff of vapour, a soft thud: no ring at all, so a
    // miss never sounds like a hit.
    knock(c, { f: k(c, [140, 130, 150, 135]), peak: 0.117, lp: 450, d: 0.05, wave: "sine" });
    noise(c, { src: "pink", type: "bandpass", f: 900, f2: 500, q: 0.9, peak: 0.091, a: 0.01,
               d: 0.12 });
    return grains(c, { at: 0.02, n: 9, span: 0.14, f: 1500, q: 1.2, peak: 0.065, d: 0.008 });
  });
  def("alchemy.spill", 3, function (c) {
    // Too fast: the funnel or the flask overflowing, a slop and a hiss off the hot glass.
    noise(c, { src: "pink", f: 1200, f2: 500, q: 0.9, peak: 0.088, a: 0.01, d: 0.2 });
    bubble(c, { at: 0.04, mm: 5, peak: 0.035 });
    return noise(c, { at: 0.08, type: "highpass", f: 3800, q: 0.6, peak: 0.022, a: 0.03,
                      d: 0.25 });
  });
  def("alchemy.swap", 3, function (c) {
    // Distill's cut: the receiver slid out and the next one under the beak.
    noise(c, { f: k(c, [1300, 1450, 1200]), f2: 1600, q: 2, peak: 0.023, a: 0.02, d: 0.08 });
    return glass(c, { at: 0.1, f: k(c, [1250, 1330, 1180]), peak: 0.032, d: 0.3 });
  });
  def("alchemy.scrape", 3, function (c) {
    // Sublime's crust scraped off the cool wall, under 2 kHz throughout (see the header).
    noise(c, { f: k(c, [800, 900, 750]), f2: k(c, [1300, 1400, 1250]), q: 1.2, peak: 0.204,
               a: 0.02, d: 0.14 });
    return grains(c, { n: k(c, [7, 8, 6]), span: 0.14, f: 1500, q: 1.6, peak: 0.119, d: 0.008 });
  });
  def("alchemy.feed", 3, function (c) {
    // Calcine and Distill's "feed the flame": a breath of air and the fire drawing up.
    noise(c, { src: "pink", f: 500, f2: k(c, [1200, 1100, 1300]), q: 1, peak: 0.06, a: 0.15,
               d: 0.25 });
    return noise(c, { at: 0.06, src: "brown", type: "lowpass", f: 240, f2: 420, q: 0.7,
                      peak: 0.11, a: 0.15, d: 0.35 });
  });
  def("alchemy.bank", 3, function (c) {
    // Banked: the damper slid across, the roar falling away under it.
    noise(c, { f: k(c, [1800, 1650, 1950]), f2: 1300, q: 2.2, peak: 0.04, a: 0.02, d: 0.1 });
    return noise(c, { at: 0.04, src: "brown", type: "lowpass", f: 420, f2: 180, q: 0.7,
                      peak: 0.08, a: 0.02, d: 0.35 });
  });

  // --- the verdicts (lane U3's stage flourishes).
  def("alchemy.tier.up", 3, pitched(function (c) {       // the liquid glints: two glasses
    var root = k(c, [1568, 1661, 1480]);
    glass(c, { f: root, peak: 0.033, d: 0.45 });
    return glass(c, { at: 0.09, f: root * 1.4983, peak: 0.037, d: 0.6 });
  }));
  def("alchemy.flawless", 3, pitched(function (c) {
    // Every glass on the bench rung on purpose: a pentatonic stack, then the gilt shimmer.
    var root = k(c, [1047, 1109, 988]);
    var steps = [1, 1.1225, 1.2599, 1.4983, 2], end = c.t;
    for (var i = 0; i < steps.length; i++) {
      end = Math.max(end, glass(c, { at: i * 0.07, f: root * steps[i], peak: 0.038,
                                     d: 1.0 + i * 0.12 }));
    }
    noise(c, { at: 0.1, type: "highpass", f: 7500, q: 0.5, peak: 0.006, a: 0.12, d: 0.7 });
    return end;
  }));
  def("alchemy.fail", 3, function (c) {
    // The liquid clouds and dulls: one big sour bubble, the flask's dead thunk, and the
    // last of the vapour sighing out.
    bubble(c, { mm: k(c, [11, 12.5, 10]), rise: 1.3, peak: 0.049, d: 0.14 });
    knock(c, { at: 0.06, f: k(c, [74, 68, 80]), peak: 0.11, lp: 300, d: 0.14, drop: 0.6,
               wave: "sine" });
    glass(c, { at: 0.06, f: k(c, [700, 660, 740]), fill: 0.9, peak: 0.018, d: 0.2 });
    return noise(c, { at: 0.12, src: "pink", f: 900, f2: 300, q: 0.8, peak: 0.031, a: 0.06,
                      d: 0.6 });
  });
  def("alchemy.land", 3, function (c) {
    // The vial to its shelf row: a soft wooden seat and its glass touching the next.
    knock(c, { f: k(c, [210, 195, 225]), peak: 0.048, lp: 1100, d: 0.04 });
    return glass(c, { at: 0.012, f: k(c, [2350, 2490, 2220]), fill: 0.7, peak: 0.04, d: 0.25 });
  });
  def("alchemy.assay", 3, function (c) {
    // The pinch meets a drop of reagent on the glass slide: a wisp of fizz, the slide's tink.
    drop(c, { f: k(c, [700, 760, 650]), peak: 0.027 });
    fizz(c, { at: 0.05, n: 10, span: 0.25, mm: 0.5, spread: 0.6, bunch: 1.5, peak: 0.027 });
    return glass(c, { at: 0.3, f: k(c, [3000, 3200, 2850]), peak: 0.022, d: 0.2 });
  });
  def("alchemy.found", 3, pitched(function (c) {
    // A formula found by experiment (UI plan §10, the vessel glowing gold once): a glass
    // rim rubbed into a swell, then answered by a clear struck note.
    var f = k(c, [1046, 1108, 988]);
    tone(c, { f: f * 1.004, peak: 0.014, a: 0.25, hold: 0.15, d: 0.6 });
    tone(c, { f: f, peak: 0.021, a: 0.25, hold: 0.15, d: 0.6 });
    return glass(c, { at: 0.4, f: f * 1.4983, peak: 0.037, d: 0.9 });
  }));

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
    sputter: function (c) {      // a candle wick spitting: two or three tiny wet ticks
      grains(c, { n: 2 + (Math.random() * 2 | 0), span: 0.08, f: 2600, q: 1.4,
                  peak: 0.012, d: 0.006 });
    },
    glasstick: function (c) {    // a flask on the shelf ticking as the room's heat moves
      glass(c, { f: 2200 + Math.random() * 1200, peak: 0.012, d: 0.12 });
    },
    blub: function (c) {         // the bain-marie at a slow simmer: one or two big bubbles
      var n = 1 + (Math.random() * 2 | 0);
      for (var i = 0; i < n; i++) {
        bubble(c, { at: i * 0.12, mm: 4 + Math.random() * 3, peak: 0.016 });
      }
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
    // The enchanter's sanctum (enchanting UI plan §11): "a still room, a candle's hiss".
    // The room is a low, nearly silent tone; the candles a quiet band of pink noise
    // fluttering a few times a second, as a flame does in still air; a thread of hiss; a
    // wick spitting now and then and the rare creak of the room. On the ambience bus.
    sanctum: { beds: [{ src: "brown", type: "lowpass", f: 160, level: 0.04 },
                      { f: 420, q: 1.2, level: 0.012, gust: 3.1, gustDepth: 0.6 },
                      { src: "white", type: "highpass", f: 6500, level: 0.0025, gust: 0.4 }],
               events: [["sputter", 4, 12], ["creak", 20, 50]] },
    // The laboratory (alchemy UI plan §11): "a low athanor roar and the odd glass tick".
    // The athanor is a slow, steady coal furnace, so its roar sits lower and steadier than
    // the smithy's bellows-driven hearth; a quiet flutter of flame, a thread of hiss, and
    // the room's own events: glass ticking, the bain-marie's slow bubble, coals settling.
    // At the field kit there is no laboratory: the bench plays the biome's bed instead.
    laboratory: { beds: [{ src: "brown", type: "lowpass", f: 260, q: 0.7, level: 0.06,
                           gust: 0.04, gustDepth: 0.25 },
                         { f: 380, q: 1.0, level: 0.014, gust: 2.4, gustDepth: 0.5 },
                         { type: "highpass", f: 4000, level: 0.0025, gust: 0.15 }],
                  events: [["glasstick", 5, 14], ["blub", 4, 11], ["coals", 10, 25]] },
  };
  // The app's canonical biomes (rules/biomes.py BIOMES) onto the nearest bed, so
  // `ambience.<biome>` for any ground the bench reports is never silent by accident.
  var AMBIENCE_ALIAS = {
    urban: "road", farmland: "grassland", jungle: "swamp", hills: "grassland",
    mountain: "tundra", water: "coast", deck: "coast", underwater: "cave",
    underground: "cave", ruins: "night", planar: "night", lab: "laboratory",
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
      // `bath` from it (contracts §11), the enchant sounds `phase` (enchanting contracts
      // §13), everything else ignores it.
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

  // The alchemy games' flame (Calcine, Distill, Sublime: UI plan §9's heat gauge), live
  // for as long as the game runs. `heat(v)` takes 0 to 1, the needle's place on the gauge
  // (the page never sends degrees here: each operation's scale is its own). It follows:
  //   the roar, brown noise low-passed where combustion roar lives, louder and a little
  //     brighter as the fire is fed, fluttering at the flame's own flicker;
  //   the hiss, which only comes in high on the gauge, the flame pushed hard;
  //   with `{liquid: true}`, the vessel over it: a seethe and bubbles on the kettle's curve
  //     (simmer(), loudest just under the boil, see the alchemy header).
  // `{kind: "athanor"}` is the laboratory's coal furnace, lower and heavier than the field
  // kit's spirit lamp (the default). On the alchemy bus, so the Alchemy slider owns it.
  var SILENT_BURNER = { heat: function () {}, stop: function () {} };
  function burner(opts) {
    try {
      var x = ensure();
      if (!x || !hasGesture() || masterLevel() <= 0) return SILENT_BURNER;
      opts = opts || {};
      var big = String(opts.kind || "").toLowerCase() === "athanor";
      var out = x.createGain();
      out.gain.value = 0;
      out.connect(buses.alchemy);
      var nodes = [], timers = [], live = true, level = 0;
      var src = function (kind) {
        var s = x.createBufferSource();
        s.buffer = buf(kind); s.loop = true;
        s.playbackRate.value = 0.94 + Math.random() * 0.12;
        nodes.push(s); return s;
      };
      var filt = function (type, f, q) {
        var b = x.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q;
        return b;
      };
      // Roar, with the flicker on its level.
      var roar = src("brown"), rf = filt("lowpass", big ? 220 : 300, 0.7), rg = x.createGain();
      rg.gain.value = 0.0001;
      var flick = x.createOscillator(), fAmt = x.createGain();
      flick.frequency.value = big ? 7 : 13; fAmt.gain.value = 0;
      flick.connect(fAmt); fAmt.connect(rg.gain); nodes.push(flick);
      roar.connect(rf); rf.connect(rg); rg.connect(out);
      // Hiss.
      var hiss = src("white"), hf = filt("bandpass", 3000, 0.8), hg = x.createGain();
      hg.gain.value = 0.0001;
      hiss.connect(hf); hf.connect(hg); hg.connect(out);
      // The vessel's seethe, if there is liquid over the flame.
      var sg = null, sf = null;
      if (opts.liquid) {
        var seethe = src("pink"); sf = filt("bandpass", 420, 1.6); sg = x.createGain();
        sg.gain.value = 0.0001;
        seethe.connect(sf); sf.connect(sg); sg.connect(out);
        (function next() {
          // Bubbles more often the nearer the simmer's peak: every 0.9 s cold, 0.12 s at it.
          var wait = (0.9 - 0.78 * simmer(level)) * (0.6 + Math.random() * 0.8) * 1000;
          timers.push(setTimeout(function () {
            if (!live) return;
            try {
              if (x.state === "running" && level > 0.15) {
                bubble({ x: x, out: out, t: x.currentTime + 0.01, p: 0.95 + Math.random() * 0.1,
                         v: 0, o: {} },
                       { mm: 2 + Math.random() * 3, peak: 0.06 * simmer(level) });
              }
            } catch (e) { /* one bad bubble never stops the flame */ }
            next();
          }, wait));
        })();
      }
      var t0 = x.currentTime + 0.01;
      nodes.forEach(function (n) { try { n.start(t0); } catch (e) { /* */ } });
      out.gain.setTargetAtTime(1, x.currentTime, 0.15);
      var handle = {
        heat: function (v) {
          if (!live) return;
          try {
            v = clamp(Number(v), 0, 1);
            level = v;
            var now = x.currentTime, r = (big ? 0.036 : 0.03) * (0.3 + 0.7 * v);
            rg.gain.setTargetAtTime(r, now, 0.08);
            fAmt.gain.setTargetAtTime(r * 0.35, now, 0.08);
            rf.frequency.setTargetAtTime((big ? 180 : 240) + (big ? 260 : 420) * v, now, 0.1);
            hg.gain.setTargetAtTime(0.0001 + 0.01 * Math.pow(v, 3), now, 0.1);
            hf.frequency.setTargetAtTime(2200 + 2600 * v, now, 0.1);
            if (sg) {
              sg.gain.setTargetAtTime(0.0001 + 0.03 * simmer(v), now, 0.2);
              sf.frequency.setTargetAtTime(320 + 260 * v, now, 0.2);
            }
          } catch (e) { /* */ }
        },
        stop: function () {
          if (!live) return;
          live = false;
          try {
            timers.forEach(clearTimeout);
            var now = x.currentTime;
            out.gain.setTargetAtTime(0, now, 0.15);
            nodes.forEach(function (n) { try { n.stop(now + 0.9); } catch (e) { /* */ } });
            setTimeout(function () { try { out.disconnect(); } catch (e) { /* */ } }, 1000);
          } catch (e) { /* already gone */ }
        },
      };
      handle.heat(opts.heat == null ? 0.5 : opts.heat);
      return handle;
    } catch (e) {
      return SILENT_BURNER;
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
    burner: burner,
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
