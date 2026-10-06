// Enchant minigame: Attune, match each essence to its seat (enchanting UI plan §9, revamp plan
// §10; the owner's ruling: "match essence to vessel").
//
// The server's roll sends the vessel's seats (`opts.seats`, rules/enchanter.py seat_signs):
// each seat's name, its sign in words ("takes weapon or any essences; suits what loves cold
// iron"), the material it sits on, and the essence the working put on it. The phials come off
// their seats and stand in a row; the player sets each back on a seat whose sign it answers.
// A phial answers a seat by the MATERIAL its own seat sits on (the affinity the server prices
// at -1 DC), or, on a seat with no material, by the sign's words: so a blade's point and edge
// (both on its head) take each other's phials, and its guard (the fittings) takes only its own.
// Matching material to effect is the shape players liked (Ars Magica's printed table, prior
// art §0 item 7); the sign is written on the phial and on every seat, so this is reading, not
// guessing, and a right match lights the seat in the essence's colour, its swatch a circle.
// A wrong seat refuses the phial: it goes back to the row, and that phial's credit drops.
//
// Input: click a phial, then its seat (or drag it there, outside Steady mode); keyboard, the
// arrows choose, Enter picks up or sets down, Backspace lifts the last seated phial again.
// Steady mode (UI plan §9): no clock, and a wrong seat costs half as much.
//
// Scoring per phial: 1, less 0.34 for each refusal (0.17 in Steady), times its pace: full
// within 1.4s of the last phial set (two actions, a pick and a set), falling to 0.6 at 4s, when
// the phial settles on its own at 0. The score is the mean over the phials. Lifting a seated
// phial with Backspace takes its credit back until it is set again.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  var LIMIT = 4, COST = 0.34;
  // A demonstration vessel for a console call with no seats; the bench always sends its own.
  var DEMO = [
    { seat: "point", name: "Point", material: "cold iron", sign: "takes weapon or any essences; suits what loves cold iron", essence: "Flaming essence", color: null },
    { seat: "edge", name: "Edge", material: "cold iron", sign: "takes weapon or any essences; suits what loves cold iron", essence: null },
    { seat: "guard", name: "Guard", material: "brass", sign: "takes weapon or any essences; suits what loves brass", essence: "Arcane essence", color: null }
  ];

  function signOf(row) { return row.material ? "loves " + row.material : (row.sign || "any seat"); }
  function keyOf(row) { return row.material ? "m:" + row.material : "s:" + (row.sign || ""); }
  function short(g, text, w) {
    if (g.measureText(text).width <= w) return text;
    while (text.length > 1 && g.measureText(text + "…").width > w) text = text.slice(0, -1);
    return text + "…";
  }

  defs.attune = {
    id: "attune",
    track: "enchant",
    name: "Attune",
    first: "Set each essence on a seat whose sign it answers. The sign is written on both.",
    hint: function (steady) { return steady ? "Click a phial, then its seat" : "Pick a phial, then its seat"; },
    KEYS: ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Enter", "Space", "Backspace"],
    HOLDS: [],
    HOLDS_STEADY: [],
    SOUNDS: { hit: "enchant.seat", miss: "enchant.bind.miss", lift: "enchant.unseat" },
    create: function (ctx) {
      var k = ctx.kit, C = ctx.C, steady = ctx.steady;
      var rows = (ctx.seats && ctx.seats.length ? ctx.seats : DEMO).map(function (r, i) {
        r = r || {};
        return { seat: String(r.seat || "seat" + i), name: String(r.name || r.seat || "Seat " + (i + 1)),
          material: r.material ? String(r.material) : "", sign: r.sign ? String(r.sign) : "",
          essence: r.essence || null, essences: Array.isArray(r.essences) ? r.essences : null,
          color: r.color || null };
      });
      // The phials: each seated essence (the server's `essence`), or each of a seat's
      // `essences` (the contracts' first shape), remembering the seat it came from.
      var phials = [];
      rows.forEach(function (r, si) {
        var list = r.essences ? r.essences : r.essence ? [{ name: r.essence, color: r.color }] : [];
        list.forEach(function (e) {
          var name = typeof e === "string" ? e : String((e && (e.name || e.essence || e.key)) || "Essence");
          phials.push({ name: name, color: (e && e.color) || r.color || null, home: si, key: keyOf(r),
            sign: signOf(r), at: -1, wrong: 0, q: null });
        });
      });
      // Shuffled once, so the row does not simply repeat the seats' order.
      for (var i = phials.length - 1; i > 0; i--) {
        var j = Math.floor(ctx.rng() * (i + 1)), tmp = phials[i]; phials[i] = phials[j]; phials[j] = tmp;
      }
      var n = phials.length;
      var cost = steady ? COST / 2 : COST;
      var share = 1.4 / ctx.baseSpeed;
      var t = 0, since = 0, held = -1, row = "phials", focus = 0, seatFocus = 0, order = [], dragFrom = -1;
      var seatBoxes = [], phialBoxes = [];
      // What each seat holds: as many phials as came off it (one at least), so a seat that
      // sent two essences in the contracts' `essences` shape takes two back.
      var occupied = rows.map(function () { return []; });
      var cap = rows.map(function (r, si) {
        var c = 0; phials.forEach(function (p) { if (p.home === si) c++; }); return Math.max(1, c);
      });
      function room(si) { return occupied[si].length < cap[si]; }

      function pace(dt) {
        if (steady || dt <= share) return 1;
        return dt >= LIMIT ? 0.6 : 1 - 0.4 * (dt - share) / (LIMIT - share);
      }
      function free() { var out = []; phials.forEach(function (p, i) { if (p.at < 0) out.push(i); }); return out; }
      function placed() { var c = 0; phials.forEach(function (p) { if (p.at >= 0) c++; }); return c; }
      function pickUp(pi) {
        if (pi < 0 || pi >= n || phials[pi].at >= 0) return;
        held = pi; row = "seats";
        // Start the seat cursor on the first empty seat.
        for (var s = 0; s < rows.length; s++) if (room(s)) { seatFocus = s; break; }
      }
      function setDown(si) {
        if (held < 0 || si < 0 || si >= rows.length || !room(si)) return;
        var p = phials[held], box = seatBoxes[si] || { x: 0, y: 0 };
        if (keyOf(rows[si]) === p.key) {
          p.at = si; occupied[si].push(held);
          p.q = Math.max(0, 1 - p.wrong * cost) * pace(t - since);
          order.push(held);
          ctx.hit(p.q, box.x, box.y, "spark", si);
          since = t;
          held = -1; row = "phials";
          var f = free(); focus = f.length ? f[0] : 0;
        } else {
          p.wrong++;
          ctx.miss(si);
          held = -1; row = "phials";
        }
      }
      function lift() {
        if (!order.length) return;
        var pi = order.pop(), p = phials[pi];
        occupied[p.at].splice(occupied[p.at].indexOf(pi), 1); p.at = -1; p.q = null;
        ctx.cue("lift");
        focus = pi; held = -1; row = "phials";
      }
      function hitBox(list, x, y) {
        for (var q = 0; q < list.length; q++) {
          var b = list[q];
          if (b && x >= b.x - b.w / 2 && x <= b.x + b.w / 2 && y >= b.y - b.h / 2 && y <= b.y + b.h / 2) return q;
        }
        return -1;
      }
      function move(dir) {
        if (row === "seats") { seatFocus = (seatFocus + dir + rows.length) % rows.length; return; }
        var f = free();
        if (!f.length) return;
        var at = f.indexOf(focus);
        focus = f[((at < 0 ? 0 : at + dir) + f.length) % f.length];
      }

      return {
        duration: steady ? 600 : n * LIMIT + 0.3,
        tick: function (dt, now) {
          t = now;
          // A phial left too long settles on its own seat at no credit, so the circle is
          // never left half attuned when the clock runs out (Simon's timeout, per piece).
          if (!steady && n && placed() < n && t - since >= LIMIT) {
            var f = free(), pi = f[0], p = phials[pi];
            var home = p.home;
            if (!room(home)) { for (var s = 0; s < rows.length; s++) if (room(s) && keyOf(rows[s]) === p.key) { home = s; break; } }
            p.at = home; occupied[home].push(pi); p.q = 0; order.push(pi);
            if (held === pi) { held = -1; row = "phials"; }
            ctx.miss(home);
            since = t;
          }
        },
        down: function (inp) {
          if (inp.src === "key") {
            if (inp.key === "Backspace") lift();
            else if (inp.key === "ArrowLeft" || inp.key === "ArrowUp") move(-1);
            else if (inp.key === "ArrowRight" || inp.key === "ArrowDown") move(1);
            else if (row === "phials") pickUp(focus);
            else setDown(seatFocus);
            return true;
          }
          if (!inp.inside) return false;
          var s = hitBox(seatBoxes, inp.x, inp.y);
          if (s >= 0 && held >= 0) { seatFocus = s; setDown(s); dragFrom = -1; return true; }
          var pi = hitBox(phialBoxes, inp.x, inp.y);
          if (pi >= 0 && phials[pi].at < 0) { focus = pi; pickUp(pi); dragFrom = pi; return true; }
          return false;
        },
        // A drag: let go over a seat to set the phial there. Steady mode never hears this.
        up: function (inp) {
          if (inp.src !== "pointer" || dragFrom < 0 || held !== dragFrom) { dragFrom = -1; return; }
          var s = hitBox(seatBoxes, inp.x, inp.y);
          dragFrom = -1;
          if (s >= 0) { seatFocus = s; setDown(s); }
        },
        hint: function () {
          if (!n || placed() >= n) return null;
          if (held >= 0) return phials[held].name + ": it " + phials[held].sign + ". Its seat?";
          return "Phial " + (placed() + 1) + " of " + n;
        },
        progress: function () { return n ? placed() / n : 1; },
        state: function () {
          return { phials: phials.map(function (p) { return { name: p.name, sign: p.sign, home: rows[p.home].seat,
            at: p.at >= 0 ? rows[p.at].seat : null, color: p.color, wrong: p.wrong }; }),
            seats: rows.map(function (r, si) { return { seat: r.seat, name: r.name, sign: signOf(r), lit: occupied[si].length > 0,
              room: room(si), color: occupied[si].length ? phials[occupied[si][0]].color : null, answers: phials.map(function (p, pi) {
                return keyOf(r) === p.key ? pi : -1; }).filter(function (x) { return x >= 0; }) }; }),
            held: held, row: row, focus: focus, seatFocus: seatFocus, placed: placed(), count: n,
            // Where the seats and phials were last drawn (null for a phial already seated).
            seatAt: seatBoxes.map(function (b) { return { x: b.x, y: b.y }; }),
            phialAt: phialBoxes.map(function (b) { return b ? { x: b.x, y: b.y } : null; }) };
        },
        score: function () {
          if (!n) return 1;
          var sum = 0; phials.forEach(function (p) { if (typeof p.q === "number") sum += p.q; }); return sum / n;
        },
        done: function () { return placed() >= n; },
        draw: function (g, W, H) {
          g.save(); g.font = "12px " + C.body;
          // The seats, along the top: name, sign, and the essence's swatch once matched.
          var cols = rows.length, sw = Math.max(60, (W - 16) / cols - 6), sh = Math.min(44, H * 0.42);
          var x0 = (W - cols * (sw + 6) + 6) / 2;
          seatBoxes = [];
          rows.forEach(function (r, si) {
            var cx = x0 + si * (sw + 6) + sw / 2, cy = 4 + sh / 2;
            seatBoxes.push({ x: cx, y: cy, w: sw, h: sh });
            var focused = row === "seats" && si === seatFocus;
            g.strokeStyle = focused ? C.gold : occupied[si].length ? C.goldDim : C.edge;
            g.lineWidth = focused ? 2 : 1;
            g.strokeRect(cx - sw / 2 + 0.5, cy - sh / 2 + 0.5, sw - 1, sh - 1);
            g.textAlign = "left"; g.textBaseline = "middle";
            g.fillStyle = C.ink; g.fillText(short(g, r.name, sw - 22), cx - sw / 2 + 6, cy - sh / 4);
            g.fillStyle = C.dim; g.fillText(short(g, signOf(r), sw - 10), cx - sw / 2 + 6, cy + sh / 4);
            if (occupied[si].length) {
              var col = phials[occupied[si][0]].color || C.gold;
              g.beginPath(); g.arc(cx + sw / 2 - 9, cy - sh / 4, 4.5, 0, Math.PI * 2);
              g.fillStyle = col; g.fill(); g.strokeStyle = C.gold; g.lineWidth = 1; g.stroke();
            }
          });
          // The phials, along the foot: the essence's name and the sign it answers.
          var fr = free(), pw = Math.max(60, Math.min(150, (W - 16) / Math.max(1, n) - 6)), ph = Math.min(36, H - sh - 16);
          var py = H - ph / 2 - 3, px0 = (W - n * (pw + 6) + 6) / 2;
          phialBoxes = [];
          phials.forEach(function (p, pi) {
            var cx = px0 + pi * (pw + 6) + pw / 2;
            if (p.at >= 0) { phialBoxes.push(null); return; }
            phialBoxes.push({ x: cx, y: py, w: pw, h: ph });
            var on = (row === "phials" && pi === focus) || pi === held;
            g.strokeStyle = on ? C.gold : C.goldDim; g.lineWidth = on ? 2 : 1;
            g.strokeRect(cx - pw / 2 + 0.5, py - ph / 2 + 0.5, pw - 1, ph - 1);
            if (pi === held) k.notch(g, cx, py - ph / 2 - 3, Math.PI / 2, 4, C.gold);
            if (p.color) { g.beginPath(); g.arc(cx - pw / 2 + 8, py - ph / 4, 3.5, 0, Math.PI * 2); g.fillStyle = p.color; g.fill(); }
            g.textAlign = "left"; g.textBaseline = "middle";
            g.fillStyle = C.ink; g.fillText(short(g, p.name, pw - 20), cx - pw / 2 + 15, py - ph / 4);
            g.fillStyle = C.dim; g.fillText(short(g, p.sign, pw - 10), cx - pw / 2 + 6, py + ph / 4);
            for (var w = 0; w < p.wrong; w++) k.pip(g, cx + pw / 2 - 7 - w * 9, py - ph / 4, 3, "miss", C);
          });
          g.restore();
          if (!fr.length) k.text(g, "Every essence is seated", W / 2, H - 14, C, { size: 13, align: "center", colour: C.ink });
          var pt = ctx.pointer;
          if (pt.inside && pt.y >= 0 && pt.y <= H) k.reticle(g, pt.x, pt.y, C, pt.down);
        }
      };
    }
  };
})();
