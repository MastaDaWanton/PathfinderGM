// Enchant minigame: Bind, at the crests (enchanting UI plan §9, revamp plan §10; the owner's
// ruling: "bind at timed windows"). The book's creation check has already been made; this game
// sets the binding's quality under the ceiling, nothing else (plan §10.2).
//
// Light runs round the candle ring, one turn per crest, and crests at the top of the ring, over
// the vessel drawn at its centre; press as it crests. Four to six crests (five at the middle difficulty). The window is
// measured in time, never in pixels (so it means the same on any width): the press is scored
// on how far it lands from the crest's moment. Rhythm games print their judgements that way,
// "Great" about +-50 to 70 ms (rhythm-games.com's survey; hinata-ya.tech's tutorial: "within
// 67ms is a PERFECT" whatever the scroll speed). This window is wider on purpose, as every
// smithing game had to be softened after launch (forge prior art §0): +-146 ms at the middle
// difficulty, full credit in its inner 40% (+-58 ms).
//
// THE DAY PHASE. In the essence family's phase the windows are x1.5 wider (owner, round 4
// points 9 and 10), x1.65 with an eager essence; the server folds both into `tuning.widen`
// (rules/enchanter.py tuning_for), which wins; only without it does the game read
// `opts.hour.widen` itself, and then only while `inside`. One source, so the hour is never
// counted twice. The frame draws the day-phase band under the ring and says why (HOUR).
//
// Input: Space or a click, one press per crest; nothing is held. Steady mode (UI plan §9):
// windows x1.6 and the light at half speed.
//
// REDUCED MOTION: the light does not travel. Each crest is counted in instead, three marks
// lighting in turn a quarter-turn apart ("3", "2", "1") and "Now" on the fourth beat, exactly
// when the moving light would crest, so the player meets it by rhythm (Rhythm Heaven is played
// by its cues; its Night Mode on sound alone). The windows are the same moments, so the scoring
// is unchanged: nothing about the timing depends on seeing anything move.
//
// Scoring per crest: 1 in the inner 40% of the window, falling to 0.4 at its edge; a press
// just early, or none at all, is a miss. The score is the mean over the crests.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var HALF = 0.13;           // s: the window's half-width at x1 before the frame's generosity

  defs.bind = {
    id: "bind",
    track: "enchant",
    name: "Bind",
    first: "Light runs round the candles. Press as it crests at the vessel.",
    hint: function () { return "Space or click at the crest"; },
    KEYS: ["Space"],
    HOLDS: [],
    HOLDS_STEADY: [],
    HOUR: true,
    SOUNDS: { hit: "enchant.bind.hit", miss: "enchant.bind.miss" },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C;
      var crests = Math.round(k.clamp(+ctx.tuning.crests || Math.round(4 + 2 * ctx.difficulty), 4, 6));
      var period = ((ctx.seconds - 0.4) / crests) / ctx.baseSpeed * (ctx.steady ? 2 : 1);
      var tw = +ctx.tuning.widen, H = ctx.hour;
      var widen = isFinite(tw) && tw > 0 ? tw : (H && H.inside ? H.widen : 1);
      widen = k.clamp(widen, 0.5, 2);
      var markAt = 0.75, tm = markAt * period, beat = period / 4;
      var hw = Math.min(HALF * ctx.baseWin * (ctx.steady ? 1.6 : 1) * widen, period * (1 - markAt) * 0.9, beat * 0.9);
      var res = [];
      for (var i = 0; i < crests; i++) res.push(null);
      var t = 0;
      var geo = { cx: 60, cy: 44, R: 34 };

      function crestAt(time) { return Math.floor(time / period); }
      function resolved() { var n = 0; res.forEach(function (q) { if (q !== null) n++; }); return n; }
      function counted(tb) {
        var rem = tm - tb;
        if (Math.abs(rem) <= hw) return 4;
        if (rem < 0) return 0;
        return rem <= beat ? 3 : rem <= 2 * beat ? 2 : rem <= 3 * beat ? 1 : 0;
      }
      function press() {
        var i = crestAt(t);
        if (i >= crests || res[i] !== null) return;
        var err = (t - i * period) - tm;
        if (Math.abs(err) <= hw) {
          var a = Math.abs(err), inner = hw * 0.4;
          res[i] = a <= inner ? 1 : 1 - 0.6 * ((a - inner) / (hw - inner));
          ctx.hit(res[i], geo.cx, geo.cy - geo.R, "spark", i);
        } else if (err < -hw && err > -3 * hw) {
          res[i] = "miss"; ctx.miss(i);
        }
      }

      return {
        widen: widen,
        duration: crests * period + 0.15,
        tick: function (dt, now) {
          t = now;
          var cur = crestAt(t);
          for (var i = 0; i < crests; i++) {
            if (res[i] !== null) continue;
            if (i < cur || (i === cur && (t - i * period) > tm + hw)) { res[i] = "miss"; ctx.miss(i); }
          }
        },
        down: function (inp) {
          if (inp.src === "pointer" && !inp.inside) return false;
          press();
          return true;
        },
        state: function () {
          var i = Math.min(crestAt(t), crests - 1), tb = t - i * period;
          return { crest: i, crests: crests, light: k.clamp(tb / tm, 0, 1), beat: counted(tb),
            open: Math.abs(tb - tm) <= hw && res[i] === null, offset_s: tb - tm, struck: res[i] !== null,
            widen: widen, window_s: hw * 2, phase: H ? H.phase : null, inside: !!(H && H.inside) };
        },
        score: function () { var s = 0; res.forEach(function (q) { if (typeof q === "number") s += q; }); return s / crests; },
        done: function () { return resolved() >= crests; },
        draw: function (g, W, H2) {
          // Room above the ring for the window's band (7px) and its notches (another 7px):
          // measured live, R = H/2 - 8 put the notches off the top of an 88px meter.
          geo.cy = H2 / 2 + 5;
          geo.R = Math.max(14, Math.min(32, H2 / 2 - 15));
          geo.cx = geo.R + 16;
          var i = Math.min(crestAt(t), crests - 1), tb = t - i * period;
          var open = Math.abs(tb - tm) <= hw && res[i] === null;
          var top = -Math.PI / 2, span = (hw / period) * Math.PI * 2;
          // The ring of candles: twelve marks, the crest's window a hatched, notched wedge at
          // the top, wider when the day phase widens it.
          for (var c = 0; c < 12; c++) {
            var a = top + c * Math.PI / 6;
            k.flame(g, geo.cx + Math.cos(a) * geo.R, geo.cy + Math.sin(a) * geo.R + 3, 5, false, C);
          }
          k.dialBand(g, geo.cx, geo.cy, geo.R - 7, geo.R + 7, top - span, top + span, C.gold,
            { notches: true, gap: 4 });
          // The vessel at the centre: the cut-stone figure, gold while the window is open.
          k.glyph(g, "focus", geo.cx, geo.cy, Math.max(6, geo.R * 0.32), open ? C.gold : C.dim, 1.6);
          if (ctx.reduced) {
            // The counted beat: nothing travels.
            k.counted(g, geo.cx + geo.R + 22, geo.cy, counted(tb), C);
          } else {
            // The light, one turn per crest, arriving at the top at the crest's moment.
            var la = top + ((tb - tm) / period) * Math.PI * 2;
            var lx = geo.cx + Math.cos(la) * geo.R, ly = geo.cy + Math.sin(la) * geo.R;
            g.save();
            g.beginPath(); g.arc(lx, ly, open ? 6 : 4.5, 0, Math.PI * 2);
            g.fillStyle = C.candle; g.fill();
            g.strokeStyle = open ? C.gold : C.ink; g.lineWidth = open ? 2 : 1; g.stroke();
            g.restore();
          }
          // The crests, as pips.
          var px = geo.cx + geo.R + (ctx.reduced ? 136 : 26), gap = Math.min(24, Math.max(14, (W - px - 20) / crests));
          for (var b = 0; b < crests; b++) k.pip(g, px + gap * b + gap / 2, geo.cy, 6, res[b], C, b === i && res[b] === null);
          k.text(g, "Crest " + Math.min(i + 1, crests) + " of " + crests, px, geo.cy + 22, C, { size: 13 });
          var p = ctx.pointer;
          if (p.inside && p.y >= 0 && p.y <= H2) k.reticle(g, p.x, p.y, C, p.down);
        }
      };
    }
  };
})();
