// The play table, part 35 (the herbalism bench: the herbarium card). Classic script in
// one IIFE, reached through `window.Bench` (30-bench-shell.js).
//
// UI plan §6.6. The card opens beside the satchel on hover (after a beat), on keyboard
// focus, and pinned on a click of a row's "?". It reads `/api/herb/<id>` (contracts §4.2)
// and shows only what the character KNOWS: known properties one per line with how each was
// learned, and one line per property still unknown. Discovery is the point (revamp plan
// §8), so nothing here is ever filled in from the ingredient's own data.
//
// Four ways to learn more, each the server's to decide:
// - Study: 10 minutes and the player's own roll, thrown with the table's d20 (§4.3);
// - Taste: uses a dose and applies the raw effect for real (revamp plan §8.2), so it
//   always asks first, in plain words, and says so in --alarm when a study has already
//   flagged a danger. The buttons read "Taste it" and "Keep it" (UI plan §8);
// - Ask: only when someone here knows (`teachers_here`), at their price (§4.5);
// - Library: only when a library is here (`library_here`), at its price and time (§4.5).

(function () {
  "use strict";
  var B = window.Bench;
  if (!B) return;
  var esc = B.esc;
  var pops = document.getElementById("bench-pops");
  if (!pops) return;

  var card = document.createElement("div");
  card.className = "bench-card v2-framed v2-card-leather";
  card.id = "bench-card";
  card.setAttribute("role", "dialog");
  card.setAttribute("aria-labelledby", "bench-card-name");
  card.hidden = true;
  pops.appendChild(card);

  var cache = {};          // id -> the §4.2 body, until something is learned about it
  var open = null;         // {id, key, anchor, pinned}
  var closeT = 0;
  var msg = "";            // the last thing learned, said on the card

  function place(anchor) {
    var sat = document.getElementById("bench-satchel");
    var sr = sat ? sat.getBoundingClientRect() : null;
    var ar = anchor && document.contains(anchor) ? anchor.getBoundingClientRect() : sr;
    var w = Math.min(340, innerWidth - 24);
    card.style.width = w + "px";
    var h = card.offsetHeight || 260;
    var left, top;
    if (sr && sr.right + 14 + w <= innerWidth - 8) {
      // Beside the satchel, level with the row (the desktop layout).
      left = sr.right + 14;
      top = ar ? ar.top - 12 : sr.top;
    } else {
      // Stacked layouts: under the row, over the satchel itself.
      left = Math.max(8, Math.min(innerWidth - w - 8, (ar ? ar.left : 8) + 12));
      top = ar ? ar.bottom + 6 : 80;
    }
    top = Math.max(8, Math.min(innerHeight - h - 8, top));
    card.style.left = Math.round(left) + "px";
    card.style.top = Math.round(top) + "px";
  }

  function skeleton(name) {
    card.innerHTML = '<i class="v2-rim" aria-hidden="true"></i><div class="hc-in">' +
      '<div class="hc-head"><span class="sk-disc is-big"></span><div><h3 id="bench-card-name">' +
      esc(name || "") + '</h3><span class="sk-bar"></span></div></div>' +
      '<span class="sk-bar"></span><span class="sk-bar is-short"></span><p class="vh">Loading.</p></div>';
  }

  function draw(h) {
    var known = h.properties.filter(function (p) { return p.known; });
    var unknown = h.properties.length - known.length;
    var acts = [];
    if (h.can_study) {
      acts.push('<button type="button" class="v2-btn is-small" data-hc="study">Study<span class="hc-cost">' +
        esc(B.minutes(h.study_minutes || 10)) + '</span></button>');
    }
    if (h.can_taste) acts.push('<button type="button" class="v2-btn is-small is-quiet" data-hc="taste">Taste<span class="hc-cost">uses 1 dose</span></button>');
    (h.teachers_here || []).forEach(function (t) {
      acts.push('<button type="button" class="v2-btn is-small is-quiet" data-hc="ask" data-ref="' + esc(t.ref) + '">Ask ' +
        esc(t.name) + '<span class="hc-cost">' + esc(t.price) + '</span></button>');
    });
    if (h.library_here) {
      acts.push('<button type="button" class="v2-btn is-small is-quiet" data-hc="library">Look it up<span class="hc-cost">' +
        esc(h.library_here.name) + ', ' + esc(h.library_here.price) +
        (h.library_here.minutes ? ", " + esc(B.minutes(h.library_here.minutes)) : "") + '</span></button>');
    }
    var where = (h.biomes || []).length ? "Found in " + h.biomes.join(", ") + "." : "";
    card.innerHTML = '<i class="v2-rim" aria-hidden="true"></i><div class="hc-in">' +
      '<div class="hc-head">' + (window.BenchIcons ? BenchIcons.html(h.part || "leaf", { size: 48, tier: h.tier, label: h.name }) : "") +
        '<div><h3 id="bench-card-name">' + esc(h.name) + '</h3>' +
        '<p class="hc-sub">' + esc([h.kind, h.part, h.tier].filter(Boolean).join(", ")) + '</p>' +
        (where ? '<p class="hc-sub">' + esc(where) + '</p>' : "") + '</div>' +
        (open && open.pinned ? '<button type="button" class="hc-x" data-hc="close" aria-label="Close the card">×</button>' : "") +
      '</div>' +
      (h.danger_known ? '<p class="hc-danger">You know this is dangerous: ' + esc(h.danger_known) + '.</p>' : "") +
      '<ul class="hc-props">' +
        known.map(function (p) {
          return '<li class="' + (p.drawback ? "is-bad" : "") + '"><span>' + (p.drawback ? '<span class="hc-k">Drawback:</span> ' : "") +
            esc(p.text) + '</span>' + (p.how ? '<span class="hc-how">' + esc(p.how) + '</span>' : "") + '</li>';
        }).join("") +
        new Array(unknown + 1).join('<li class="is-unknown"><span class="hc-rule" aria-hidden="true"></span><span>unknown</span></li>') +
      '</ul>' +
      (!h.properties.length ? '<p class="hc-sub">Nothing is known about it yet.</p>' : "") +
      (msg ? '<p class="hc-msg" role="status">' + esc(msg) + '</p>' : "") +
      (acts.length ? '<div class="hc-acts">' + acts.join("") + '</div>' : "") +
      '</div>';
  }

  function show(o) {
    if (B.live || B.busy) return;
    clearTimeout(closeT);
    var same = open && open.id === o.id;
    if (same && open.pinned && !o.pin) return;     // a hover never unpins a pinned card
    var wasPinned = !!(open && open.pinned);
    open = { id: o.id, key: o.key, anchor: o.el, pinned: !!o.pin || (same && open.pinned) };
    // A card the player opened is a panel opening; a hover's glance is not (Lane G's
    // `ui.open`, which would chatter on every row the pointer crossed).
    if (open.pinned && !wasPinned) B.sound("ui.open");
    if (!same) msg = "";
    card.hidden = false;
    card.classList.toggle("is-pinned", open.pinned);
    if (cache[o.id]) draw(cache[o.id]);
    else {
      var it = o.key ? B.item(o.key) : null;
      skeleton(it ? it.name : "");
      fetchCard(o.id);
    }
    place(o.el);
    if (open.pinned) {
      B.pushEsc(escClose);
      open.wantFocus = true;
      focusIn();
    }
  }
  // A pinned card takes the keyboard to its first action, once there is one: on a first
  // visit the card is still a skeleton when it opens, and focus waits for the answer.
  function focusIn() {
    if (!open || !open.wantFocus) return;
    var first = card.querySelector("[data-hc]:not([data-hc='close'])") || card.querySelector("[data-hc]");
    if (first) { open.wantFocus = false; first.focus(); }
  }

  function fetchCard(id) {
    return B.api("/api/herb/" + encodeURIComponent(id)).then(function (h) {
      cache[id] = h;
      if (open && open.id === id) { draw(h); place(open.anchor); focusIn(); }
      return h;
    }).catch(function (err) {
      if (!open || open.id !== id) return;
      card.innerHTML = '<i class="v2-rim" aria-hidden="true"></i><div class="hc-in"><h3 id="bench-card-name">Couldn\'t load this herb.</h3>' +
        '<p class="hc-sub">' + esc(err.message) + '</p><button type="button" class="v2-btn is-small" data-hc="retry">Retry</button></div>';
    });
  }

  function hide(back) {
    clearTimeout(closeT);
    var was = open;
    B.dropEsc(escClose);
    open = null;
    card.hidden = true;
    if (was && was.pinned) B.sound("ui.close");
    if (back && was && was.pinned) {
      var again = document.querySelector('#bench-satchel .bt-info[data-for="' + (window.CSS && CSS.escape ? CSS.escape(was.key) : was.key) + '"]');
      if (again) again.focus();
    }
  }
  function escClose() { hide(true); }

  B.on("herb", show);
  B.on("unpeek", function () {
    if (!open || open.pinned) return;
    clearTimeout(closeT);
    // A beat, so the pointer can cross from the row onto the card and stay.
    closeT = setTimeout(function () { if (open && !open.pinned) hide(false); }, 220);
  });
  card.addEventListener("mouseenter", function () { clearTimeout(closeT); });
  card.addEventListener("mouseleave", function () {
    if (open && !open.pinned) closeT = setTimeout(function () { if (open && !open.pinned) hide(false); }, 220);
  });
  B.on("close", function () { hide(false); });
  B.on("play", function () { hide(false); });
  B.on("method", function () { if (open && !open.pinned) hide(false); });
  // A click outside a pinned card puts it away.
  document.addEventListener("pointerdown", function (e) {
    if (!open || !open.pinned || card.contains(e.target)) return;
    if (e.target.closest && (e.target.closest(".bt-info") || e.target.closest(".bench-modal") || e.target.closest("#d3d-mat"))) return;
    hide(false);
  });

  // --- learning (contracts §4.3 to §4.5) ------------------------------------------------
  function learned(r, how) {
    var rev = (r && r.revealed) || [];
    var bits = rev.map(function (p) { return (p.drawback ? "drawback, " : "") + p.text; });
    if (r && r.refused) return r.refused;
    if (!bits.length) return how + " Nothing new.";
    return how + " Learned: " + bits.join("; ") + "." + (r.paid ? " Paid " + r.paid + "." : "");
  }
  function after(id, r, line) {
    delete cache[id];
    msg = line;
    B.say(line);
    if (r && r.minutes) B.tickClock(r.minutes, r.clock);
    B.refresh();
    // The card is drawn again from the server's answer and the button that was pressed
    // may be gone (a last dose tasted takes Taste with it): the keyboard goes back to the
    // card's first action rather than falling to <body>.
    if (open && open.id === id) { open.wantFocus = true; return fetchCard(id); }
  }

  function study(id, name) {
    var dice = window.Dice3D;
    var shown = { title: "Study " + name, why: "Knowledge (nature), or the herbalist's eye", sides: 20, lo: 1, hi: 20, die: "1d20", terms: [] };
    var asking = dice ? dice.ask(Object.assign({ hold: true }, shown)) : Promise.resolve(null);
    focusMat();
    var r = null;
    return asking.then(function (face) {
      return B.api("/api/herb/study", { id: id, face: face == null ? null : face });
    }).then(function (res) {
      r = res;
      B.sound("bench.study");
      if (!dice || !r.roll) return null;
      var roll = r.roll;
      var terms = [];
      if (roll.bonus != null) terms.push({ label: "your bonus", value: B.sign(roll.bonus) });
      if (roll.dc != null) terms.push({ label: "beat", value: roll.dc });
      var closing = dice.land(Object.assign({}, shown, { result: roll.face, terms: terms }));
      var rest = typeof dice.settled === "function" ? dice.settled() : null;
      // The engine's word on it (§4.3 `roll.success`); never compared here.
      if (typeof showVerdict === "function" && typeof roll.success === "boolean") {
        showVerdict({ verdict: roll.success ? "success" : "failure", natural: roll.face === 20 ? 20 : roll.face === 1 ? 1 : null }, rest);
      }
      if (rest) rest.then(focusMat);
      return closing;
    }).then(function () {
      return after(id, r, learned(r, r.roll && r.roll.success === false ? "The study came to nothing." : "You studied it."));
    }).catch(function (err) {
      if (dice && dice.close) dice.close();
      msg = err.message;
      if (cache[id]) draw(cache[id]);
    });
  }
  function focusMat() { B.focusMat(); }

  function taste(h) {
    return B.confirm({
      title: "Taste " + h.name + "?",
      body: "It uses 1 dose, and its raw effect takes hold of you for real. You learn one good thing about it, and one bad thing if it has one.",
      warn: h.danger_known ? "You know this is dangerous: " + h.danger_known + "." : "",
      ok: "Taste it", cancel: "Keep it", danger: true,
    }).then(function (yes) {
      if (!yes) return;
      return B.api("/api/herb/taste", { id: h.id }).then(function (r) {
        B.sound("bench.taste");
        var line = learned(r, "You tasted it.") + (r.tells && r.tells.length ? " " + r.tells.join(" ") : "");
        if (r.down) {
          // The taster dropped: the table's own deathveil and state take it from here.
          B.say(line);
          hide(false);
          B.closeBench();
          return;
        }
        return after(h.id, r, line);
      }).catch(function (err) { msg = err.message; draw(h); });
    });
  }

  card.addEventListener("click", function (e) {
    var b = e.target.closest("[data-hc]");
    if (!b || !open) return;
    var id = open.id, h = cache[id];
    var k = b.dataset.hc;
    if (k === "close") { hide(true); return; }
    if (k === "retry") { fetchCard(id); return; }
    if (!h) return;
    // Hovering opened it; acting on it pins it, so the answer stays to be read.
    if (!open.pinned) { open.pinned = true; card.classList.add("is-pinned"); B.pushEsc(escClose); }
    if (k === "study") { study(id, h.name); return; }
    if (k === "taste") { taste(h); return; }
    if (k === "ask") {
      B.api("/api/herb/ask", { id: id, ref: b.dataset.ref }).then(function (r) { return after(id, r, learned(r, "You asked.")); })
        .catch(function (err) { msg = err.message; draw(h); });
      return;
    }
    if (k === "library") {
      B.api("/api/herb/library", { id: id }).then(function (r) { return after(id, r, learned(r, "You looked it up.")); })
        .catch(function (err) { msg = err.message; draw(h); });
    }
  });
  addEventListener("resize", function () { if (open) place(open.anchor); });
})();
