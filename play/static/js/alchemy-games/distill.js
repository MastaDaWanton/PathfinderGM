// Alchemy minigame: Distill, make the cuts (alchemy UI plan §9, revamp plan §7).
//
// The real operation (alchemy prior art §5; Whisky Advocate, "Heads, Hearts and Tails of Whisky
// Distillation"; Brewhaus, "Using a Pot Still: Where To Make Your Cuts"): a distiller watches the
// still head's temperature and switches the receiver at each CUT. The heads come over first and
// are thrown away; the hearts follow and are kept; as the pot's spirit runs out the head's
// temperature climbs on its own and the tails begin, and the distiller cuts back to the waste.
// A still makes three things in order, and the skill is knowing when each one has begun.
//
// So the game has two controls, the fire and the receiver:
//   - The fire is the frame's FLAME: hold Up (or the mouse on the still) to feed it, let go to
//     bank it, Down to damp it. The gauge's bands are the server's: heads, hearts, tails.
//   - Space (or a click on a vessel) swaps what stands under the beak: the jar (heads and tails,
//     thrown away) or the flask (the hearts, kept). A swap takes 0.15s, and what drips in that
//     moment falls on the bench.
// What comes over: nothing below the heads band; the heads, whatever the heat, until they are
// gone (shown draining in their own pips); then the hearts while the heat is in the hearts band;
// above it, tails smeared through the hearts. As the hearts run out the head creeps hotter by
// itself, so a steady fire has to be banked a little more as the run goes. When the hearts are
// all over, the tails follow after a short pause: cut back to the jar and the run is done.
//
// The words lead the cuts ("Hearts now: swap to the flask"), the pips show what is left before
// each cut comes (anticipation, not reflex), and the flask's own pips show what it holds.
// Steady mode (UI plan §9): the hearts band x1.5, the drift at half speed, the fire a toggle,
// and a longer pause before the tails.
//
// Scoring: yield times purity. Yield is the share of the pot's hearts that reached the flask;
// purity is hearts / (hearts + 2 x the heads and tails in it). A perfect run (cut as the heads
// end, hold the hearts band, cut back when the hearts are done) scores 1. Holding the fire on
// and never swapping keeps nothing (0); swapping by mashing Space spills what drips mid-swap.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var HEADS = 0.18, SWAP_S = 0.15, CREEP = 4, PIPS = 6;

  defs.distill = {
    id: "distill",
    track: "alchemy",
    name: "Distill",
    first: "Heads to the jar, hearts to the flask, tails to the jar. Space swaps; Up feeds the fire.",
    hint: function (steady) {
      return steady ? "Up lights or banks the fire; Space swaps the vessel" : "Hold Up to feed the fire; Space swaps the vessel";
    },
    KEYS: ["Space", "ArrowUp", "ArrowDown"],
    HOLDS: ["ArrowUp", "ArrowDown"],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "alchemy.drip", miss: "alchemy.hiss", swap: "alchemy.swap", feed: "alchemy.feed",
      bank: "alchemy.bank" },
    FLAME: { label: "Still head", lo: 60, hi: 100, start: 65, target: "hearts", steadyBand: 1.5,
      bands: [{ name: "heads", lo: 70, hi: 78 }, { name: "hearts", lo: 78, hi: 88 },
        { name: "tails", lo: 88, hi: 100 }] },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, heat = ctx.heat;
      var need = ctx.seconds * 0.65;                       // seconds of hearts in the pot
      var flow = 1 / need, grace = 0.6 * (ctx.steady ? 1.5 : 1);
      var duration = ctx.seconds * (ctx.steady ? 2.4 : 1.8) + 1;
      var dripFrom = heat.bands.length ? heat.bands[0].lo : heat.band[0];
      var heads = HEADS, hearts = 1;                       // what is left in the pot
      var flask = { hearts: 0, heads: 0, tails: 0 }, jar = { hearts: 0, heads: 0, tails: 0 };
      var spilt = 0, under = "jar", swapping = 0, swaps = 0, spentAt = -1, ended = false, t = 0;
      var now = "", lastPip = 0, fouled = false;
      var geo = { jar: null, flask: null };

      function swap(to) {
        if (ended || swapping > 0) return;
        var want = to || (under === "jar" ? "flask" : "jar");
        if (want === under) return;
        under = want; swapping = SWAP_S; swaps++;
        ctx.cue("swap");
      }
      var cuedAt = -1;
      // The fire fed or banked is heard once as it changes (lane U5's alchemy.feed and .bank);
      // the burner the frame holds carries the roar in between.
      function feed(on) {
        // At most one every quarter second: a hand pulsing the fire answers each pulse, a bot
        // flicking it every frame (84 cues in 5.7s, measured live) does not stutter the bus.
        if (on !== heat.fed && t - cuedAt >= 0.25) { cuedAt = t; ctx.cue(on ? "feed" : "bank"); }
        heat.fed = on; if (on) heat.damp = false;
      }

      return {
        duration: duration,
        tick: function (dt, tnow) {
          t = tnow;
          if (ended) return;
          if (swapping > 0) swapping = Math.max(0, swapping - dt);
          var c = heat.c, got = { hearts: 0, heads: 0, tails: 0 };
          now = "";
          if (c >= dripFrom) {
            if (heads > 0) {
              var h = Math.min(heads, flow * dt * (c >= heat.band[0] ? 1 : 0.6));
              heads -= h; got.heads = h; now = "heads";
            } else if (hearts > 0) {
              if (c >= heat.band[0]) {
                // Too hot, the tails smear through: half the hearts' rate, the tails' at full.
                var hot = c > heat.band[1];
                var hh = Math.min(hearts, flow * dt * (hot ? 0.5 : 1));
                hearts -= hh; got.hearts = hh; now = "hearts";
                if (hot) { got.tails = flow * dt; now = "tails"; }
              }
              // The pot running dry: the head climbs by itself (the tails' onset).
              heat.add(CREEP * (1 - hearts) * dt);
            } else {
              if (spentAt < 0) spentAt = t;
              if (t - spentAt >= grace || c > heat.band[1]) { got.tails = flow * dt * 0.8; now = "tails"; }
            }
          }
          var into = swapping > 0 ? null : under === "flask" ? flask : jar;
          Object.keys(got).forEach(function (key) {
            if (!got[key]) return;
            if (into) into[key] += got[key]; else spilt += got[key];
          });
          var pip = Math.floor(flask.hearts * PIPS + 1e-9);
          if (pip > lastPip) { lastPip = pip; ctx.hit(1, geo.flask ? geo.flask.x : null, geo.flask ? geo.flask.y : null, "steam"); }
          // Heads or tails into the flask: one dull hiss as it starts, not one a frame.
          var fouling = into === flask && (got.heads > 0 || got.tails > 0);
          if (fouling && !fouled) ctx.miss();
          fouled = fouling;
          // The run ends when the hearts are all over and the jar is back under the beak, or when
          // the tails have run a while.
          if (hearts <= 0 && ((under === "jar" && swapping === 0 && spentAt >= 0) || (spentAt >= 0 && t - spentAt > grace + 1.5))) ended = true;
        },
        down: function (inp) {
          if (ended) return false;
          if (inp.src === "key") {
            if (inp.key === "Space") { swap(); return true; }
            if (inp.key === "ArrowDown") {
              feed(false); heat.damp = ctx.steady ? !heat.damp : true; return true;
            }
            if (inp.key === "ArrowUp") { if (ctx.steady) feed(!heat.fed); else feed(true); return true; }
            return false;
          }
          if (!inp.inside) return false;
          var hitV = function (b) { return b && inp.x >= b.x - b.w / 2 - 6 && inp.x <= b.x + b.w / 2 + 6 && inp.y >= b.y - b.h && inp.y <= b.y + 8; };
          if (hitV(geo.jar)) { swap("jar"); return true; }
          if (hitV(geo.flask)) { swap("flask"); return true; }
          if (ctx.steady) feed(!heat.fed); else feed(true);
          return true;
        },
        up: function (inp) {
          if (inp.src === "key" && inp.key === "ArrowDown") { heat.damp = false; return; }
          if (inp.src === "key" && inp.key === "Space") return;
          feed(false);
        },
        // The cuts, in words, ahead of the fire's own.
        urgent: function () {
          if (ended) return null;
          if (now === "heads" && under === "flask") return "Heads in the flask: swap to the jar (Space)";
          if (heads <= 0 && hearts > 0 && under === "jar" && heat.c >= heat.band[0]) return "Hearts now: swap to the flask (Space)";
          if (hearts <= 0 && under === "flask") return "Hearts done: swap to the jar (Space)";
          return null;
        },
        hint: function () {
          if (ended) return null;
          if (now === "heads") return "Heads coming over: keep the jar";
          if (now === "hearts" && under === "flask") return "Hearts: hold the fire here";
          return null;
        },
        progress: function () { return ended ? 1 : t / duration; },
        state: function () {
          return { heat_c: heat.c, in_band: heat.inBand(), status: heat.status(), fed: heat.fed, under: under,
            swapping: swapping > 0, swaps: swaps, dripping: now, heads_left: heads / HEADS, hearts_left: hearts,
            flask: { hearts: flask.hearts, heads: flask.heads, tails: flask.tails }, spilt: spilt, band: heat.band.slice(),
            spent: hearts <= 0, done: ended, jarAt: geo.jar, flaskAt: geo.flask };
        },
        score: function () {
          var y = Math.min(1, flask.hearts), bad = flask.heads + flask.tails;
          return y > 0 ? y * (y / (y + 2 * bad)) : 0;
        },
        done: function () { return ended; },
        draw: function (g, W, H) {
          var cy = H / 2 + 6, px = 34;
          // The still: the pot on its fire, the head, the beak running right to the vessels.
          k.flame(g, px, H - 4, 22, heat.fed, C);
          g.save();
          g.strokeStyle = C.goldDim; g.lineWidth = 1.5;
          g.beginPath(); g.arc(px, cy + 4, 16, 0, Math.PI * 2); g.stroke();
          g.beginPath(); g.moveTo(px - 5, cy - 12); g.lineTo(px - 5, cy - 26); g.lineTo(px + 5, cy - 26); g.lineTo(px + 5, cy - 12); g.stroke();
          var bx = px + 64;
          g.beginPath(); g.moveTo(px + 5, cy - 24); g.lineTo(bx, cy - 12); g.stroke();
          g.restore();
          // The two vessels under the beak, the one in use outlined in gold and named.
          var vw = 22, vh = 26;
          geo.jar = { x: bx - 4, y: cy + 22, w: vw, h: vh };
          geo.flask = { x: bx + 30, y: cy + 22, w: vw, h: vh };
          [["jar", geo.jar, "Jar"], ["flask", geo.flask, "Flask"]].forEach(function (v) {
            var on = under === v[0], b = v[1];
            g.save();
            g.strokeStyle = on ? C.gold : C.ash; g.lineWidth = on ? 2 : 1.2;
            g.strokeRect(b.x - b.w / 2, b.y - b.h, b.w, b.h);
            g.restore();
            k.text(g, v[2], b.x, b.y - b.h - 7, C, { size: 12, align: "center", colour: on ? C.ink : C.dim });
          });
          // The drip: a dot falling from the beak into whichever vessel is under it.
          if (now && swapping === 0) {
            var dx = under === "jar" ? geo.jar.x : geo.flask.x;
            g.save(); g.fillStyle = C.ink; g.beginPath(); g.arc(dx, cy - 8, 2, 0, Math.PI * 2); g.fill(); g.restore();
          }
          // The words and the two pip rows: the heads still to come off, and the hearts kept.
          var x = bx + 64;
          k.text(g, now ? "Dripping: " + now : swapping > 0 ? "Swapping" : heat.c < dripFrom ? "Nothing coming over" : "Waiting",
            x, 12, C, { size: 13, colour: now ? C.ink : C.dim });
          var gap = Math.max(13, Math.min(20, (W - x - 64) / PIPS));
          k.text(g, "Heads", x, cy - 8, C, { size: 12 });
          var hl = heads / HEADS;
          for (var i = 0; i < 3; i++) {
            var f = k.clamp(hl * 3 - i, 0, 1);
            k.pip(g, x + 56 + gap * i, cy - 8, 4.5, f > 0 ? f : null, C, false);
          }
          k.text(g, "Hearts", x, cy + 14, C, { size: 12 });
          for (var j = 0; j < PIPS; j++) {
            var fh = k.clamp(flask.hearts * PIPS - j, 0, 1);
            k.pip(g, x + 56 + gap * j, cy + 14, 4.5, fh > 0 ? fh : null, C, false);
          }
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
