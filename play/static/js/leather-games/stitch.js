// Leather minigame: Stitch, the saddle stitch at its pitch (leather UI plan §9, revamp plan §11).
//
// A saddle stitch is two needles on one thread, each stitch locked on its own, and its pitch is
// counted in stitches per inch: 8 to 9 rough, 10 to 12 good work, 14 to 18 fine (prior art §3.6:
// fineleatherworking.com; Armitage Leather). The pitch is the awl's spacing: punch too soon and
// the holes crowd and weaken the edge like a perforation; too late and the stitch is long and
// loose and pulls. So as the awl travels along the seam the gauge reads the pitch a punch NOW
// would make, sweeping from crowded down through the server's band to loose; the player punches
// while it reads in the band. The ring closing on the hole mark is the same timing, drawn as a
// shape for a player who does not watch the gauge.
//
// Input: Space or a click punches and pulls the stitch through. After each pull the next stitch
// starts; presses during the pull do nothing. A stitch left until the pitch reads loose is a
// loose stitch, and the next begins. The server's `drift` jitters each stitch's tempo a little
// (a hand is not a metronome). Steady mode (UI plan §9): the ring's window x1.6 (the band), the
// tempo x0.75. Nothing is held. Reduced motion: the sweep and the ring are the timing itself, so
// they stay (WCAG 2.3.3 exempts essential motion), and the counted beat is drawn beside them.
//
// Scoring: six stitches, each earning the gauge's quality at its pitch (1 in the band's inner
// half, 0.6 at its rim, nothing crowded or loose). The score is the mean of the six.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var N = 6, MARK = 0.62, PULL = 0.16;

  defs["leather.stitch"] = {
    id: "leather.stitch",
    track: "leather",
    name: "Stitch",
    first: "Punch each stitch as the ring meets the mark: even stitches, not crowded, not loose.",
    hint: function () { return "Space or click when the ring meets the mark"; },
    KEYS: ["Space"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "leather.stitch.pull", miss: "leather.stitch.pull" },
    BAND: { unit: "spi", label: "Pitch", target: [10, 12], fail: [0, 7], value_start: 6, drift: 0.4,
      steadyBand: 1.6, words: { low: "long", in: "even", high: "crowded", fail: "loose" },
      say: { fail: "Loose" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, G = ctx.gauge;
      var mid = (G.target[0] + G.target[1]) / 2;
      var base = MARK / ctx.baseSpeed / (ctx.steady ? 0.75 : 1);
      var res = [], start = 0, pull = 0, tm = base, t = 0, pitches = [];
      var geo = { cx: 40, cy: 40 };
      var lo = G.scale[0], hi = G.scale[1];

      function newStitch(at) {
        start = at;
        G.v = hi;                 // a punch at once would crowd the last hole: the reading says so
        tm = base * (1 + 0.05 * G.drift * (ctx.rng() - 0.5));
      }
      // The pitch a punch at `e` seconds into the stitch makes. The awl slows as it nears the
      // spacing a hand knows (it has gone sqrt(e / tm) of it), so the pitch is the band's middle
      // over that share. Measured with the straight share (e / tm) first: the band lasted 0.13s
      // of a 0.63s stitch, a twitch game; the slowing awl holds it for 0.27s.
      function pitchAt(e) { return k.clamp(mid * Math.sqrt(tm / Math.max(1e-3, e)), lo, hi); }
      // When the pitch reads loose (the fail band's top), the stitch has gone on too long.
      var looseAt = function () { var p = G.fail ? Math.max(lo + 0.01, G.fail[1]) : lo; return tm * (mid / p) * (mid / p); };

      function punch() {
        if (pull > 0 || res.length >= N) return;
        var q = G.quality(0.5, 0.6);
        res.push(q); pitches.push(G.v);
        pull = PULL;
        if (q > 0) ctx.hit(q, geo.cx, geo.cy, "grit"); else ctx.miss();
      }

      newStitch(0);
      return {
        duration: N * (base * 2.6 + PULL) + 0.5,
        tick: function (dt, now) {
          t = now;
          if (pull > 0) {
            pull -= dt;
            if (pull <= 0) { pull = 0; if (res.length < N) newStitch(now); }
            return;
          }
          if (res.length >= N) return;
          var e = now - start;
          G.v = pitchAt(e);
          if (e > looseAt()) { res.push(0); pitches.push(G.v); ctx.miss(); pull = PULL; }
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          punch();
          return true;
        },
        hint: function () {
          if (pull > 0 && pitches.length) {
            var p = pitches[pitches.length - 1], s = G.statusAt(p);
            return s === "in" ? null : s === "high" ? "Crowded: too soon" : "Long: too late";
          }
          return null;
        },
        state: function () {
          var e = t - start;
          return { pitch: G.v, band: G.band.slice(), e: e, mark: tm, pulling: pull > 0, stitches: res.length,
            of: N, results: res.slice(), in_band: G.inBand(), quality: G.quality(0.5, 0.6),
            ring: pull > 0 ? 1 : k.clamp(e / tm, 0, 2) };
        },
        score: function () { var s = 0; res.forEach(function (q) { s += q; }); return k.clamp(s / N, 0, 1); },
        done: function () { return res.length >= N && pull <= 0; },
        draw: function (g, W, H) {
          geo.cx = 40; geo.cy = Math.round(H / 2 + 2);
          var e = t - start, f = pull > 0 ? 1 : k.clamp(e / tm, 0, 1.6);
          // The ring closes on the hole mark as the awl reaches the good spacing.
          var rm = 8, r0 = 34, r = Math.max(2, r0 - (r0 - rm) * f);
          var inW = G.inBand() && pull <= 0;
          k.ring(g, geo.cx, geo.cy, rm, r, rm + 6, Math.max(1, rm - 4), C, inW);
          if (ctx.reduced && pull <= 0) {
            // The counted beat: three marks light as the awl closes on the mark, "Now" at it.
            k.counted(g, geo.cx + 46, 12, f >= 1 ? 4 : f >= 0.75 ? 3 : f >= 0.5 ? 2 : f >= 0.25 ? 1 : 0, C);
          }
          // The seam: the stitches made, each drawn at its own spacing (crowded close, loose long).
          var x = geo.cx + 46, y = geo.cy + 16, gap = Math.max(10, Math.min(22, (W - x - 10) / N));
          for (var i = 0; i < N; i++) {
            var px = x + i * gap;
            if (i < res.length) {
              var len = k.clamp(gap * (11 / Math.max(4, pitches[i])) * 0.7, 3, gap * 1.2);
              g.save(); g.strokeStyle = res[i] > 0 ? C.gold : C.alarm; g.lineWidth = 2;
              g.beginPath(); g.moveTo(px, y); g.lineTo(px + len, y); g.stroke(); g.restore();
            } else { g.beginPath(); g.arc(px, y, 1.6, 0, Math.PI * 2); g.fillStyle = C.ash; g.fill(); }
          }
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
