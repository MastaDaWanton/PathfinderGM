// Alchemy minigame: Bottle, pour to the mark and stopper it in a lull (alchemy UI plan §9,
// revamp plan §7).
//
// Two beats. First the product pours into the vessel: fill it to the mark (hold to pour, let go
// at the mark; tapping to top it off is how a careful hand does it, and allowed). Then the
// stopper: the warm product breathes out vapour in puffs, a regular beat, and between them
// comes a lull. The vapour is the frame's REACTION gauge (the server's {start: 60, band: [0, 30],
// settle: 8}): it starts high from the pour and settles; on top of that the puffs come and go.
// Stopper it in a lull, when the vapour is low, and it seals clean; stopper it on the fumes and
// it is sealed with them in.
//
// The stopper's moment is a RING that closes on the stopper once each beat, meeting it at the
// lull (the herb bench's steep seal and grind strike use the same ring, the shared kit's `ring`).
// The ring shows gold when the vapour will be in its band at that lull, and grey while the
// product is still fuming, so the player knows which beat to take; a press while the ring is
// far open does nothing, so mashing Space through the pour never seals by accident. A press
// while it is closing but off the mark pops the stopper on the fumes: that seal is final.
//
// REDUCED MOTION: the ring does not close. The beat is counted in instead ("3", "2", "1",
// "Now", the enchant games' counted marks), lit on the same windows, so the lull is met by
// rhythm.
//
// Input: hold Space or the mouse to pour, let go at the mark; then Space or a click on the ring.
// Steady mode (UI plan §9): the pour is a toggle, and the ring's window and the vapour band x1.6.
//
// Scoring: 35% the pour (full within half the mark's tolerance, 0.4 at its edge, 0.1 when it
// overflows the brim), 65% the seal: its timing (full in the inner 40% of the window, 0.4 at the
// edge), and nothing at all if the vapour was above its band when the stopper went in.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var MARK = 0.8, POUR = 0.42, PERIOD = 1.3, PUFF = 34, PUFF_AT = 0.2, PUFF_RISE = 0.15, PUFF_TAU = 0.55;
  var REST = 10, CLOSE = 0.6, IN_HAND = 0.3;

  defs.bottle = {
    id: "bottle",
    track: "alchemy",
    name: "Bottle",
    first: "Pour to the mark. Then stopper it when the ring meets it in a lull of the vapour.",
    hint: function (steady) { return steady ? "Space starts and stops the pour; then Space on the ring" : "Hold Space to pour; then Space when the ring meets the stopper"; },
    KEYS: ["Space"],
    HOLDS: ["Space"],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "alchemy.stopper", miss: "alchemy.miss", pour: "alchemy.pour" },
    REACTION: { label: "Vapour", band: [0, 30], rise: 0, settle: 8, flare_at: 95, start: 60,
      steadyBand: 1.6,
      words: ["", "lull", "fuming", "boiling over"],
      say: { high: "Fuming: wait for a lull", flare: "Boiling over: wait" } },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, R = ctx.react;
      var tol = 0.05 * ctx.baseWin * (ctx.steady ? 1.6 : 1);
      var hw = Math.min(0.3, 0.18 * ctx.band(1.6));    // half the ring's window, seconds
      var settle = R.settle, base = R.v;
      var duration = ctx.seconds * (ctx.steady ? 2.6 : 2) + 1;
      var phase = "pour", level = 0, pouring = false, pourEnd = -1, pq = 0, sq = 0, sealed = false, popped = false;
      var t = 0, pourStarted = false;
      var geo = { ring: null, cx: 40, top: 10 };

      function puff(at) {
        var ph = ((at - PUFF_AT) % PERIOD + PERIOD) % PERIOD;
        if (at < PUFF_AT) return 0;
        if (ph < PUFF_RISE) return PUFF * ph / PUFF_RISE;
        return PUFF * Math.exp(-(ph - PUFF_RISE) / PUFF_TAU);
      }
      // The lull is the cycle's end: the window is centred on each multiple of PERIOD.
      function offset() {
        var n = Math.round(t / PERIOD);
        return t - n * PERIOD;
      }
      function baseAt(at) { return REST + (base - REST) * Math.max(0, 1 - settle * at / Math.max(1e-6, base - REST)); }
      // Will the vapour be in its band at the lull the ring is closing on? The server's numbers
      // and the beat decide it, so the ring can say so before the player commits.
      function lullOk() {
        var n = Math.max(1, Math.round(t / PERIOD));
        var v = baseAt(n * PERIOD) + puff(n * PERIOD);
        return v <= R.band[1];
      }
      function ringOpen() {          // closing for the last CLOSE seconds before a lull, then the window
        var o = offset();
        return phase === "seal" && t - pourEnd >= IN_HAND && o >= -CLOSE && o <= hw;
      }
      function endPour() {
        if (level < MARK - tol) return;            // not there yet: pour again
        var d = Math.abs(level - MARK);
        pq = level >= 1 ? 0.1 : d <= tol * 0.5 ? 1 : d <= tol ? 1 - 0.6 * (d - tol * 0.5) / (tol * 0.5)
          : Math.max(0.1, 0.4 - 0.3 * (d - tol) / tol);
        phase = "seal"; pourEnd = t; pouring = false;
      }
      function seal() {
        if (phase !== "seal" || sealed || !ringOpen()) return;
        var o = Math.abs(offset()), inner = hw * 0.4;
        var tq = o <= inner ? 1 : o <= hw ? 1 - 0.6 * (o - inner) / (hw - inner) : 0;
        // The vapour is go or no-go: in its band, the seal takes; above it, it is sealed on the
        // fumes. Grading the depth of the lull as well was tried first and measured: a bot that
        // took the first gold ring exactly on the mark scored 0.75, because the gold ring said
        // "in band" and the score said "not deep enough". One signal, one meaning.
        var vq = R.inBand() ? 1 : 0;
        sealed = true;
        sq = tq * vq;
        popped = sq <= 0;
        if (popped) ctx.miss(); else ctx.hit(sq, geo.cx, geo.top, "steam");
      }
      // The counted beat (reduced motion): marks at three, two and one beats before the lull,
      // "Now" from half a beat before it to the window's far edge. Evenly spaced, so a player
      // who presses one beat after "1" lands on the lull itself.
      function counted() {
        if (phase !== "seal" || sealed || t - pourEnd < IN_HAND) return 0;
        var o = offset(), b = CLOSE / 3;
        if (o > hw) return 0;
        if (o >= -Math.min(hw, b / 2)) return 4;
        return o >= -b ? 3 : o >= -2 * b ? 2 : o >= -3 * b ? 1 : 0;
      }

      return {
        duration: duration,
        tick: function (dt, now) {
          t = now;
          R.v = k.clamp(baseAt(t) + puff(t), 0, 100);
          if (pouring && phase === "pour") {
            level = Math.min(1.08, level + POUR * dt);
            if (level >= 1.08) endPour();
          }
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          if (phase === "pour") {
            if (ctx.steady && pouring) { pouring = false; endPour(); return true; }
            pouring = true;
            if (!pourStarted) { pourStarted = true; ctx.cue("pour", { level: level }); }
            return true;
          }
          seal();
          return true;
        },
        up: function () {
          if (phase === "pour" && pouring) { pouring = false; endPour(); }
        },
        urgent: function () {
          if (phase === "pour") {
            if (level >= 1) return "Over the brim";
            return level >= MARK - tol ? "At the mark: let go" : null;
          }
          if (sealed) return popped ? "Sealed on the fumes" : "Sealed";
          if (t - pourEnd < IN_HAND) return "The stopper is in your hand";
          return lullOk() ? "Stopper it when the ring meets it" : "Still fuming: wait for a lull";
        },
        progress: function () { return t / duration; },
        state: function () {
          return { phase: phase, level: level, mark: MARK, tol: tol, pouring: pouring, vapour: R.v,
            band: R.band.slice(), in_band: R.inBand(), offset_s: offset(), window_s: hw * 2, ring_open: ringOpen(),
            lull_ok: lullOk(), beat: counted(), sealed: sealed, popped: popped, pour_q: pq, seal_q: sq,
            ringAt: geo.ring };
        },
        score: function () { return 0.35 * pq + 0.65 * sq; },
        done: function () { return sealed; },
        draw: function (g, W, H) {
          geo.cx = 40; geo.top = 10;
          var vb = H - 6, vh = H - 22, vx = geo.cx - 14;
          // The vessel with its mark, filling in the product's level.
          g.save();
          g.strokeStyle = C.goldDim; g.lineWidth = 1.5;
          g.strokeRect(vx, vb - vh, 28, vh);
          g.fillStyle = C.ash;
          var lh = vh * Math.min(1, level);
          g.fillRect(vx + 2, vb - lh, 24, lh - 1);
          g.restore();
          var my = vb - vh * MARK;
          k.notch(g, vx - 3, my, 0, 6, C.gold);
          k.notch(g, vx + 31, my, Math.PI, 6, C.gold);
          k.text(g, "Mark", vx + 38, my, C, { size: 12, colour: phase === "pour" ? C.ink : C.dim });
          var rx = geo.cx + 110, ry = H / 2;
          geo.ring = { x: rx, y: ry };
          if (phase === "seal" && !sealed) {
            var ok = lullOk(), rm = 9, o = offset();
            if (ctx.reduced) {
              k.text(g, "Stopper", rx - 28, ry - 22, C, { size: 12, colour: ok ? C.ink : C.dim });
              k.counted(g, rx - 28, ry, counted(), C);
            } else {
              var open = o < 0 && -o <= CLOSE ? -o / CLOSE : o <= hw && o >= 0 ? 0 : 1;
              var r = rm + 26 * open;
              k.ring(g, rx, ry, rm, Math.max(rm - 4, r), rm + 26 * (hw / CLOSE), Math.max(1, rm - 26 * (hw / CLOSE)),
                ok ? C : Object.assign({}, C, { gold: C.ash, goldDim: C.edge }), Math.abs(o) <= hw);
            }
            k.text(g, ok ? "Lull coming" : "Still fuming", rx + 44, ry, C, { size: 13, colour: ok ? C.gold : C.dim });
          } else if (sealed) {
            k.text(g, popped ? "Sealed on the fumes" : "Sealed", rx - 20, ry, C, { size: 14, display: true, colour: popped ? C.alarm : C.gold });
          } else {
            k.text(g, pouring ? "Pouring" : "Pour to the mark", rx - 20, ry, C, { size: 13, colour: pouring ? C.gold : C.dim });
          }
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
