/* What this variant adds to the board, shared by the flat map (map.js) and the 3D view
 * (scene3d.js) so the two cannot disagree: one reading of the scene's extras, one lamp,
 * one set of labels, one card per foe and one readout line.
 *
 * Everything here is derived from `STATE.scene` and `window.POLISH_SCENE.extras/.light`
 * (the engine's own answers). Nothing is invented: no AC, no needed roll, no square for
 * a foe known only by a hunch.
 */
(function () {
  "use strict";

  function key(c, r) { return c + "," + r; }

  /* The room lamp, from the hour and the light level.
     Colour comes from the theme's own tokens rather than new hues: night leans toward
     --ember (255,176,84), dawn toward --player (#8fb0c8), noon is the plain lamp. Strength
     keeps a floor of .74 so the board still reads at night; tokens are never dimmed by it
     in the flat view, and only a third as much in 3D, because who is where must stay the
     brightest thing on the board whatever the hour. */
  var EMBER = [1, 176 / 255, 84 / 255], COOL = [143 / 200, 176 / 200, 1];
  function mix(a, b, t) { return [0, 1, 2].map(function (i) { return a[i] + (b[i] - a[i]) * t; }); }
  function lamp(light) {
    light = light || {};
    var phase = (light.phase && light.phase.phase) || "";
    var dim = light.ambient === "dim", dark = light.ambient === "dark" || light.ambient === "darkness";
    var tint = [1, 1, 1], strength = 1, name = "";
    if (phase === "night" || phase === "dusk" || phase === "evening") { tint = mix(tint, EMBER, 0.32); name = phase; }
    else if (phase === "dawn") { tint = mix(tint, COOL, 0.38); name = "dawn"; }
    else if (phase === "morning" || phase === "afternoon") { tint = mix(tint, EMBER, 0.06); name = phase; }
    else if (phase) name = phase;
    if (dim) strength = phase === "night" ? 0.74 : 0.8;
    if (dark) strength = 0.62;
    return { tint: tint, strength: strength, ambient: light.ambient || "", phase: name };
  }

  /* Short labels. Three goblins all reading "G" (or "G", "S", "T" from "second goblin" and
     "third goblin", which says they are three different things) is the who-is-who problem
     on this board. An ordinal at the front of a name becomes a number after the initial;
     a plain name that shares its rest with a numbered one is number 1. From names only. */
  var ORD = { first: 1, second: 2, third: 3, fourth: 4, fifth: 5, sixth: 6, seventh: 7,
              eighth: 8, ninth: 9, tenth: 10 };
  function labels(actors) {
    var out = {}, bases = {};
    (actors || []).forEach(function (a) {
      var m = /^(\w+)\s+(.+)$/.exec(String(a.name || "").toLowerCase());
      if (m && ORD[m[1]]) bases[m[2]] = true;
    });
    (actors || []).forEach(function (a) {
      var n = String(a.name || "?"), low = n.toLowerCase();
      var m = /^(\w+)\s+(.+)$/.exec(low);
      if (a.members != null) out[a.ref] = String(a.members);
      else if (m && ORD[m[1]]) out[a.ref] = m[2].charAt(0).toUpperCase() + ORD[m[1]];
      else if (bases[low]) out[a.ref] = n.charAt(0).toUpperCase() + "1";
      else out[a.ref] = n.charAt(0).toUpperCase();
    });
    return out;
  }

  /* The outline of a set of squares: every edge with a square of the set on one side
     and not on the other, and which side the set is on (n, s, w, e). One function for
     the threat edge, the spell's edge and raised ground's lip, in both views. */
  function edges(set) {
    var out = [];
    Object.keys(set).forEach(function (k) {
      var p = k.split(",").map(Number), c = p[0], r = p[1];
      if (!set[key(c, r - 1)]) out.push([c, r, c + 1, r, "n", c, r]);
      if (!set[key(c, r + 1)]) out.push([c, r + 1, c + 1, r + 1, "s", c, r]);
      if (!set[key(c - 1, r)]) out.push([c, r, c, r + 1, "w", c, r]);
      if (!set[key(c + 1, r)]) out.push([c + 1, r, c + 1, r + 1, "e", c, r]);
    });
    return out;
  }

  /* Everything the board's previews need, read once per draw. */
  function read(s) {
    var sc = window.POLISH_SCENE || {}, x = sc.extras || {}, scene = s.scene || {};
    var actors = scene.actors || [], byRef = {};
    actors.forEach(function (a) { byRef[a.ref] = a; });
    var pc = actors.filter(function (a) { return a.stance === "pc"; })[0] || null;

    var threat = {};
    var tb = (x.threatened && x.threatened.by_foe) || {};
    Object.keys(tb).forEach(function (ref) {
      tb[ref].forEach(function (q) { (threat[key(q[0], q[1])] = threat[key(q[0], q[1])] || []).push(ref); });
    });
    var provokes = (x.provokes && x.provokes.squares) || {};
    var unseen = {};
    ((x.sight && x.sight.squares) || []).forEach(function (q) { if (!q[2]) unseen[key(q[0], q[1])] = true; });

    // A spell's catch is shown only while its area is on the board (the harness lays it
    // into grid.areas, as the game does after a cast); the extras' own `caught` list is
    // the engine's answer for that same area.
    var g = scene.grid || {}, sa = x.spell_area, caught = [];
    var laid = (g.areas || []).some(function (a) { return sa && a && a.spell === sa.spell; });
    if (laid) caught = sa.caught || [];

    var hunches = ((x.awareness && x.awareness.hunches) || []);
    var turn = scene.in_encounter ? (scene.turn_ref ||
      ((scene.initiative || []).filter(function (i) { return i.up; })[0] || {}).ref) : null;

    return {
      byRef: byRef, pc: pc, threat: threat, threatBy: tb, provokes: provokes, unseen: unseen,
      caught: caught, spell: laid ? sa.spell : null, hunches: hunches, turn: turn,
      preview: (x.attack_preview && x.attack_preview.by_foe) || {},
      cover: (x.sight && x.sight.cover) || {},
      lamp: lamp(sc.light), labels: labels(actors), light: sc.light || {}
    };
  }
  function readAndKeep(s) { lastP = read(s); return lastP; }

  function names(refs, byRef) {
    var n = refs.map(function (r) { return byRef[r] ? byRef[r].name : "a foe"; });
    if (n.length < 2) return n.join("");
    return n.slice(0, -1).join(", ") + " and " + n[n.length - 1];
  }
  function signed(v) { return (v >= 0 ? "+" : "") + v; }
  function cap1(t) { t = String(t); return t.charAt(0).toUpperCase() + t.slice(1); }

  /* The card shown on pointing at a foe: the player's OWN bonus with each weapon and what
     it is made of. Never the foe's AC or a roll needed: the game hides both. */
  function card(P, ref) {
    var a = P.byRef[ref]; if (!a) return "";
    var rows = P.preview[ref] || [];
    var cover = P.cover[ref];
    var out = '<p class="fc-name">' + esc(cap1(a.name)) + "</p>";
    if (!rows.length) return out + '<p class="fc-note">No attack to preview.</p>';
    // Weapons built from the same terms share one breakdown, so two identical lines are
    // not printed twice; different terms get a breakdown each.
    var same = rows.every(function (w) { return JSON.stringify(w.terms) === JSON.stringify(rows[0].terms); });
    out += '<table class="fc-rows">';
    rows.forEach(function (w) {
      out += "<tr" + (w.in_reach === false ? ' class="far"' : "") + "><th>" + esc(cap1(w.name)) +
        "</th><td>" + signed(w.bonus) + "</td></tr>";
      if (!same) out += terms(w.terms);
    });
    if (same) out += terms(rows[0].terms);
    out += "</table>";
    var far = rows.filter(function (w) { return w.in_reach === false; });
    if (far.length) out += '<p class="fc-note">' + (far.length === rows.length ? "Out of reach"
      : cap1(far.map(function (w) { return w.name; }).join(" and ")) + " out of reach") + " from where you stand.</p>";
    if (cover === "cover" || cover === "soft") out += '<p class="fc-note">Has ' + (cover === "soft" ? "soft " : "") + "cover from you.</p>";
    if (cover === "total") out += '<p class="fc-note">Total cover from you.</p>';
    return out;
    function terms(t) {
      return (t || []).map(function (p) {
        return '<tr class="term"><th>' + esc(cap1(p[0])) + "</th><td>" + signed(p[1]) + "</td></tr>";
      }).join("");
    }
  }

  /* What a square would mean: its distance, and whether walking there provokes. */
  function squareLine(P, c, r, cost) {
    var who = P.provokes[key(c, r)];
    var d = cost + " ft";
    if (who && who.length) return d + ". Walking there provokes from " + names(who, P.byRef) + ".";
    return (cost <= 5 ? "A 5-ft step" : d) + ". Does not provoke.";
  }

  function restLine(P) {
    var a = P.turn && P.byRef[P.turn];
    if (!a) return "";
    return a.stance === "pc" ? "Your turn. Point at a square or a foe to see what it means."
                             : esc(cap1(a.name)) + "'s turn.";
  }

  var lastP = null;

  /* One pointer and focus handler for both views, installed once. Colour and opacity
     only: nothing moves or resizes under the pointer. */
  function readout(text) {
    var el = document.getElementById("boardreadout");
    if (el && el.textContent !== text) el.textContent = text;
  }
  function hideCard() {
    var c = document.getElementById("foecard");
    if (c) c.classList.remove("on");
    document.querySelectorAll(".foehot").forEach(function (n) { n.classList.remove("foehot"); });
  }
  function showCard(target, ref) {
    var view = target.closest(".boardview"), c = document.getElementById("foecard");
    if (!view || !c || !lastP) return;
    c.innerHTML = card(lastP, ref);
    view.querySelectorAll('[data-foe="' + ref + '"], [data-of="' + ref + '"]')
      .forEach(function (n) { n.classList.add("foehot"); });
    var v = view.getBoundingClientRect(), t = target.getBoundingClientRect();
    if (target.closest(".fig")) {
      // A figure in 3D is many polygons; anchor to all of them together.
      var all = view.querySelectorAll('[data-foe="' + ref + '"]'), L = 1e9, T = 1e9, R = -1e9, B = -1e9;
      all.forEach(function (n) { var b = n.getBoundingClientRect();
        L = Math.min(L, b.left); T = Math.min(T, b.top); R = Math.max(R, b.right); B = Math.max(B, b.bottom); });
      t = { left: L, top: T, right: R, bottom: B };
    }
    // Client rects are in screen pixels and the card is placed in CSS pixels; `k` makes
    // the two agree under any zoom or transform of the page.
    var k = view.offsetWidth / (v.width || 1);
    var tl = (t.left - v.left) * k, tr = (t.right - v.left) * k,
        tt = (t.top - v.top) * k, tb = (t.bottom - v.top) * k, VW = view.offsetWidth, VH = view.offsetHeight;
    var w = c.offsetWidth, h = c.offsetHeight, gap = 8;
    var clampX = function (x) { return Math.max(6, Math.min(VW - w - 6, x)); };
    var clampY = function (y) { return Math.max(6, Math.min(VH - h - 6, y)); };
    var cx = (tl + tr) / 2 - w / 2, cy = (tt + tb) / 2 - h / 2;
    // Above, right, left, below: the first place that covers nobody on the board, because
    // a card over the neighbours a flank is made of hides the reason for the +2.
    var spots = [[clampX(cx), tt - gap - h, "bottom"], [tr + gap, clampY(cy), "left"],
                 [tl - gap - w, clampY(cy), "right"], [clampX(cx), tb + gap, "top"]];
    var people = [];
    view.querySelectorAll(".token, .fig.face-top").forEach(function (n) {
      var b = n.getBoundingClientRect();
      people.push([(b.left - v.left) * k, (b.top - v.top) * k, (b.right - v.left) * k, (b.bottom - v.top) * k]);
    });
    var fits = spots.filter(function (p) {
      return p[0] >= 6 && p[1] >= 6 && p[0] + w <= VW - 6 && p[1] + h <= VH - 6; });
    var pick = fits.filter(function (p) {
      return !people.some(function (q) {
        return p[0] < q[2] && p[0] + w > q[0] && p[1] < q[3] && p[1] + h > q[1]; });
    })[0] || fits[0] || [clampX(cx), clampY(tb + gap), "top"];
    var x = pick[0], y = pick[1], side = pick[2];
    c.style.left = Math.round(x) + "px"; c.style.top = Math.round(y) + "px";
    c.dataset.from = side;
    c.classList.add("on");
    var a = lastP.byRef[ref];
    readout(a ? cap1(a.name) + ". Your bonus only; the foe's defences are not shown." : "");
  }

  function over(e) {
    if (!lastP) return;
    var foe = e.target.closest && e.target.closest("[data-foe]");
    if (foe) { hideCard(); showCard(foe, foe.getAttribute("data-foe")); return; }
    hideCard();
    var sq = e.target.closest && e.target.closest("[data-sq]");
    if (sq) {
      var p = sq.getAttribute("data-sq").split(",").map(Number);
      var cost = Number(sq.getAttribute("data-cost"));
      readout(squareLine(lastP, p[0], p[1], cost));
      return;
    }
    readout(restLine(lastP));
  }

  if (!window.__polishWired) {
    window.__polishWired = true;
    document.addEventListener("pointerover", over);
    document.addEventListener("focusin", over);
    document.addEventListener("focusout", function (e) {
      if (e.target.closest && e.target.closest("[data-foe]")) hideCard(); });
    document.documentElement.addEventListener("pointerleave", function () {
      hideCard(); if (lastP) readout(restLine(lastP)); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") hideCard(); });
  }

  /* The key under the board: shapes that are data, the same ones the board draws. */
  function key_(P, has) {
    var sw = function (inner) {
      return '<svg class="kz" viewBox="0 0 12 12" aria-hidden="true">' + inner + "</svg>";
    };
    var items = [];
    if (has.safe) items.push(sw('<rect class="k-safe" x="1" y="1" width="10" height="10" rx="1"/>') + "Safe to move");
    if (has.prov) items.push(sw('<rect class="k-reach" x="1" y="1" width="10" height="10" rx="1"/><rect x="1" y="1" width="10" height="10" rx="1" fill="url(#k-hatch)"/>') + "Provokes");
    if (has.threat) items.push(sw('<rect x="1.5" y="1.5" width="9" height="9" fill="none" class="k-threat"/>') + "Threatened");
    if (has.unseen) items.push(sw('<rect class="k-unseen" x="1" y="1" width="10" height="10" rx="1"/>') + "Out of sight");
    if (has.spell) items.push(sw('<rect class="k-spell" x="1" y="1" width="10" height="10" rx="1"/>') + cap1(String(P.spell).replace(/-/g, " ")));
    if (!items.length) return "";
    return '<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>' +
      '<pattern id="k-hatch" width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">' +
      '<line x1="0" y1="0" x2="0" y2="3" class="hatchline"/></pattern></defs></svg>' +
      '<p class="boardkey2">' + items.map(function (i) { return "<span>" + i + "</span>"; }).join("") + "</p>";
  }

  /* The lines under the board: the light, what the spell catches, the hunch. */
  function notes(P) {
    var out = [];
    var L = P.lamp, light = [];
    if (L.ambient) light.push(cap1(L.ambient) + " light");
    if (L.phase) light.push(L.phase);
    if (P.spell) {
      var nm = cap1(String(P.spell).replace(/-/g, " "));
      out.push(P.caught.length ? nm + " catches " + names(P.caught, P.byRef) + "."
                               : nm + " catches nobody you can see.");
    }
    if (P.hunches.length) {
      var n = P.hunches.length, ft = P.hunches[0].within_ft;
      out.push("You sense " + (n === 1 ? "a foe" : n + " foes") + " you cannot see, within " +
               ft + " ft (the dashed ring), but not where.");
    }
    if (light.length) out.push(light.join(", "));
    return out;
  }

  window.Polish = { read: readAndKeep, edges: edges, key: key, keyHtml: key_, notes: notes,
                    restLine: restLine };
})();
