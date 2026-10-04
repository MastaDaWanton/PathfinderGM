// The play table, part 44 (the forge: the ledger card and the Journal's ledger). Classic
// script in one IIFE, reached through `window.ForgeLedger` (contracts §11).
//
// Blacksmithing UI plan §6.7, the herbarium's counterpart (35-bench-herbarium.js). Two
// surfaces, one renderer:
//
//   ForgeLedger.card(materialId, anchorEl, opts)  the card beside the forge's rack: the
//       engraved icon and the material's swatch, its name, where it is found or bought,
//       each known property with how it was learned ("assayed, day 14"), one "unknown"
//       line per property still unknown, and two actions: Assay (a sliver and ten minutes)
//       and Ask a smith (only when the server names one here).
//   ForgeLedger.journal(host)  the Journal's section: every material met, "3 of 7 known",
//       an "Unknowns first" toggle, and each material's known lines on a disclosure.
//
// Both read `GET /api/forge/ledger` and `GET /api/forge/material/<id>` and show only what
// the character KNOWS: the server sends an unknown property with its text null
// (rules/knowledge.py `properties`), so nothing here can show a secret by mistake, and
// nothing is filled in from the material's own data.
//
// EVERY NUMBER IS THE SERVER'S (UI plan §12). The DC, the count carried, the minutes, the
// roll and its total are read from responses and printed; nothing is compared or summed
// here. In particular the assay's verdict word is shown only when the response carries
// `roll.success`: deciding it from total and DC on the page would be the page authoring
// a result. Fields the card reads when present and leaves out when absent (lane U5's
// hand-back names them as asks of forge_views): `color` (the swatch), `obtain`/`source`/
// `biomes` (where found or bought), `assay_minutes` and `assay_cost`, `smiths_here`,
// `assay_danger` (what testing it does to the assayer, in words).
//
// THE REACTIVE ASSAY (UI plan §6.7, contracts §13.2). Assaying abysium sickens (the
// book) and assaying noqual makes magic recoil, suppressing the assayer's active magic
// for 1d4 rounds (the owner's house rule), so it always asks first, in --alarm words,
// with the safe button focused: "Noqual reacts badly to testing. Assay it anyway?", then
// what it does in the server's words, Assay it / Keep it (the herb bench's "Taste it /
// Keep it" shape). Whether to ask is the server's `assay_danger`, else its `reactive`.
//
// WHERE THE CARD LIVES. Inside the forge's own layer when the anchor is in one (the
// core's trap wraps Tab inside the layer, so a card appended to <body> would have buttons
// the keyboard cannot reach), on the layer's Esc stack (29-bench-core.js, one Esc closes
// one popover); loose on <body> at the table's popover height otherwise.
//
// Styles are injected once from here (`#forge-ledger-style`) with the theme's tokens
// only: this lane owns no stylesheet, and the herb card's classes in bench.css give the
// same leather, rim and type for free. MOTION: nothing loops (no setInterval, no
// requestAnimationFrame); tests/test_forge_ledger_ui.py greps for both.

(function () {
  "use strict";

  var core = function () { return window.BenchCore || null; };
  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  function csrf() {
    var m = (document.cookie || "").match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }
  // The core's API when it is loaded (the same errors, the same status on them); a copy of
  // its eight lines otherwise, so the Journal's section works on a page with no bench.
  function api(path, body) {
    var C = core();
    if (C && typeof C.api === "function") return C.api(path, body);
    var opts = body === undefined ? { cache: "no-store" } : {
      method: "POST", body: JSON.stringify(body),
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
    };
    return fetch(path, opts).then(function (r) {
      return r.text().then(function (raw) {
        var data = null;
        try { data = JSON.parse(raw); } catch (err) { data = null; }
        if (!r.ok || !data) {
          var e = new Error((data && data.error) || ("The server failed (HTTP " + r.status + ")."));
          e.status = r.status;
          throw e;
        }
        return data;
      });
    });
  }
  function sound(name) {
    var C = core();
    if (C && typeof C.sound === "function") { C.sound(name); return; }
    try { if (window.Sound && typeof Sound.play === "function") Sound.play(name); } catch (err) { /* */ }
  }
  function minutesWords(m) {
    var C = core();
    if (C && typeof C.minutes === "function") return C.minutes(m);
    m = Math.round(Number(m) || 0);
    return m + (m === 1 ? " minute" : " minutes");
  }
  function sign(v) { v = Number(v) || 0; return (v >= 0 ? "+" : "") + v; }

  // --- words --------------------------------------------------------------------------------
  // Which list a property sits in is shown even while the property is unknown (rules/
  // knowledge.py: "that the iron does *something* to a blade is visible on the anvil"), so
  // the card groups its lines under where they act.
  var GROUP = { weapon: "In a weapon", armour: "In armour", working: "At the anvil",
                quench_mark: "In the quench" };
  var GROUP_ORDER = ["weapon", "armour", "working", "quench_mark", ""];
  var OBTAIN = { bought: "Bought at a market", mined: "Mined", gathered: "Gathered",
                 harvested: "Harvested", smelted: "Smelted from its ore", alloyed: "Alloyed at the crucible" };

  function listWords(xs) {
    xs = (xs || []).filter(Boolean).map(String);
    if (xs.length < 2) return xs.join("");
    return xs.slice(0, -1).join(", ") + " or " + xs[xs.length - 1];
  }
  // Where it is found or bought, in words, from the server's fields when it sends them.
  function foundLine(c) {
    if (c.found) return String(c.found);
    var how = String(c.obtain || c.source || "").toLowerCase();
    if (!how) return "";
    if (c.source === "monster") return "Taken from monsters.";
    var head = OBTAIN[how] || (how.charAt(0).toUpperCase() + how.slice(1));
    var biomes = (c.biomes || []).length && how !== "bought" ? " in " + listWords(c.biomes) + " country" : "";
    return head + biomes + ".";
  }
  // The assay's cost line: "a sliver" always, the minutes only when the server said them.
  function assayCost(c) {
    var bits = ["a sliver"];
    if (c.assay_minutes != null) bits.push(minutesWords(c.assay_minutes));
    return bits.join(", ");
  }
  function reactiveLine(name) { return name + " reacts badly to testing. Assay it anyway?"; }
  // What testing it does to the assayer, in the server's words. Abysium sickens (the
  // book); noqual's magic recoils and suppresses the assayer's active magic for 1d4 rounds
  // (the owner's house rule, contracts §13.2). Both are the material's own data, so the
  // page names no metal: it prints `assay_danger` (a sentence, or {text}) when the card
  // carries it, and a plain warning when it does not.
  function dangerWords(c) {
    var d = c.assay_danger;
    var t = d && typeof d === "object" ? d.text : d;
    return typeof t === "string" && t.trim() ? t.trim() : "";
  }
  // Ask first when the server says the assay is dangerous. A card that carries
  // `assay_danger` says it exactly (null for a reactive ore with no effect on a handler);
  // one that does not falls back on the `reactive` flag, which over-asks rather than
  // letting a dangerous assay through without a word.
  function needsConfirm(c) {
    return Object.prototype.hasOwnProperty.call(c, "assay_danger") ? !!c.assay_danger : !!c.reactive;
  }
  // A colour is drawn only when it is a plain colour value: it goes into a style attribute.
  function swatch(color, big) {
    var ok = typeof color === "string" && /^(#[0-9a-f]{3,8}|rgba?\([\d\s.,%]+\)|hsla?\([\d\s.,%deg]+\))$/i.test(color.trim());
    return ok ? '<span class="fl-swatch' + (big ? " is-big" : "") + '" style="background:' + esc(color.trim()) + '" aria-hidden="true"></span>' : "";
  }
  function icon(name, opts) {
    if (!window.BenchIcons || typeof BenchIcons.html !== "function") return "";
    try { return BenchIcons.html(name, opts); } catch (err) { return ""; }
  }

  // --- the card's body: the one renderer both surfaces draw ----------------------------
  // `opts.actions` adds the action row (the card beside the rack); the Journal draws the
  // same lines without it.
  function propsHtml(c) {
    var props = c.properties || [];
    if (!props.length) {
      return c.properties === null
        ? '<p class="hc-sub">What is known of it cannot be read in this build yet.</p>'
        : '<p class="hc-sub">There is nothing to learn about it.</p>';
    }
    var groups = {};
    props.forEach(function (p) { var g = p.group || ""; (groups[g] = groups[g] || []).push(p); });
    var several = Object.keys(groups).length > 1 || !groups[""];
    return GROUP_ORDER.filter(function (g) { return groups[g]; }).map(function (g) {
      var rows = groups[g].map(function (p) {
        if (!p.known) return '<li class="is-unknown"><span class="hc-rule" aria-hidden="true"></span><span>unknown</span></li>';
        return '<li class="' + (p.drawback ? "is-bad" : "") + '"><span>' +
          (p.drawback ? '<span class="hc-k">Drawback:</span> ' : "") + esc(p.text) + '</span>' +
          (p.how ? '<span class="hc-how">' + esc(p.how) + '</span>' : "") + '</li>';
      }).join("");
      return (several ? '<h4 class="fl-group">' + esc(GROUP[g] || "Otherwise") + '</h4>' : "") +
        '<ul class="hc-props">' + rows + '</ul>';
    }).join("");
  }
  // No "3 of 7 known" on the card: the material endpoint sends no such count, and counting
  // rows here would be the page making a number. The card shows a line per unknown
  // instead, and the Journal's row prints the ledger's own `known` and `total`.
  function dangerHtml(c) {
    var known = (c.properties || []).filter(function (p) { return p.known && p.drawback; })
      .map(function (p) { return p.text; });
    var said = c.danger_known || known.join("; ");
    return said && c.reactive ? '<p class="hc-danger">You know this is dangerous: ' + esc(said) + '.</p>' : "";
  }

  function actionsHtml(c, o) {
    var acts = [];
    var none = !(Number(c.carried) > 0);
    acts.push('<button type="button" class="v2-btn is-small" data-fl="assay"' + (none || o.busy ? " disabled" : "") +
      (none ? ' aria-describedby="fl-assay-why"' : "") + '>Assay<span class="hc-cost">' + esc(assayCost(c)) + '</span></button>');
    var smiths = (c.smiths_here && c.smiths_here.length ? c.smiths_here : (o.smiths || []));
    smiths.forEach(function (s) {
      acts.push('<button type="button" class="v2-btn is-small is-quiet" data-fl="ask" data-ref="' + esc(s.ref) + '"' +
        (o.busy ? " disabled" : "") + '>Ask a smith<span class="hc-cost">' +
        esc([s.name, s.price].filter(Boolean).join(", ")) + '</span></button>');
    });
    return '<div class="hc-acts">' + acts.join("") + '</div>' +
      (none ? '<p class="fl-why" id="fl-assay-why">You carry none of it to take a sliver from.</p>' : "");
  }

  function cardHtml(c, o) {
    o = o || {};
    var where = foundLine(c);
    var carried = Number(c.carried) > 0 ? c.carried + " carried" : "";
    var sub = [c.kind, c.tier, carried].filter(Boolean).join(", ");
    return '<i class="v2-rim" aria-hidden="true"></i><div class="hc-in">' +
      '<div class="hc-head"><span class="fl-mark">' +
        icon(c.form || c.kind || "", { size: 48, tier: c.tier, label: c.name }) + swatch(c.color, true) + '</span>' +
        '<div><h3 id="fl-card-name">' + esc(c.name) + '</h3>' +
        (sub ? '<p class="hc-sub">' + esc(sub) + '</p>' : "") +
        (where ? '<p class="hc-sub">' + esc(where) + '</p>' : "") + '</div>' +
        (o.pinned ? '<button type="button" class="hc-x" data-fl="close" aria-label="Close the card">×</button>' : "") +
      '</div>' + dangerHtml(c) + propsHtml(c) +
      (o.msg ? '<p class="hc-msg" role="status">' + esc(o.msg) + '</p>' : "") +
      (o.actions ? actionsHtml(c, o) : "") + '</div>';
  }

  // --- the Journal's rows -------------------------------------------------------------------
  function rowsHtml(st) {
    if (st.error) {
      return '<p class="why">' + esc(st.error) + '</p>' +
        '<button type="button" class="v2-btn is-small" data-fl-retry>Retry</button>';
    }
    if (st.ledger === null) return '<p class="why">Reading the ledger.</p>';
    var rows = st.ledger.slice();
    if (!rows.length) return '<p class="why">No materials yet. Buy or mine one and it appears here.</p>';
    if (st.unknownFirst) {
      rows.sort(function (a, b) {
        return ((b.total - b.known) - (a.total - a.known)) || String(a.name).localeCompare(String(b.name));
      });
    }
    return '<ul class="plain matters twocol fl-rows">' + rows.map(function (e) {
      var open = st.open === e.id;
      var bodyId = "fl-jr-card-" + esc(e.id);
      return '<li class="matter" role="listitem"><h3><button type="button" class="fl-row" data-fl-mat="' + esc(e.id) + '"' +
        ' aria-expanded="' + open + '" aria-controls="' + bodyId + '">' +
        '<span class="fl-mark">' + icon(e.form || e.kind || "", { size: 26, tier: e.tier, label: e.name }) + swatch(e.color) + '</span>' +
        esc(e.name) + '</button></h3>' +
        '<p class="why">' + esc([e.kind, e.known + " of " + e.total + " known",
          Number(e.carried) > 0 ? e.carried + " carried" : ""].filter(Boolean).join(" · ")) + '</p>' +
        (e.danger_known ? '<p class="why">You know this is dangerous: ' + esc(e.danger_known) + '.</p>' : "") +
        '<div id="' + bodyId + '" class="fl-jr-body"' + (open ? "" : " hidden") + '>' +
          (open ? journalBody(st, e.id) : "") + '</div></li>';
    }).join("") + '</ul>';
  }
  function journalBody(st, id) {
    var c = st.cards[id];
    if (!c) return '<p class="why">Reading what you know.</p>';
    if (c.error) return '<p class="why">' + esc(c.error) + '</p>';
    return propsHtml(c);
  }

  // --- styles, once -------------------------------------------------------------------------
  // Tokens only (theme-v2.css), and the bench's semantic names set on the card itself so it
  // reads the same inside the forge's layer, the herb bench's or none. --alarm at 19px and
  // 600 weight: measured 3.4:1 on the card leather, which passes AA as large text and would
  // not as body text, so the reactive line is never set smaller.
  function style() {
    if (document.getElementById("forge-ledger-style")) return;
    var s = document.createElement("style");
    s.id = "forge-ledger-style";
    s.textContent = [
      ".fl-card, .fl-confirm, .fl-journal { --bench-ink: var(--ink); --bench-quiet: var(--dim); --bench-accent: var(--gold);",
      "  --bench-warn: var(--alarm); --bench-radius: 3px; }",
      ".fl-card { position: fixed; width: 340px; max-height: calc(100vh - 16px); z-index: 7; color: var(--ink);",
      "  font: 16px/1.5 var(--body); border-radius: 3px; box-shadow: var(--sh-3), var(--ring-cast); }",
      ".fl-card.is-loose { z-index: 30; }",
      ".fl-card[hidden] { display: none; }",
      ".fl-card .hc-x { position: absolute; right: 8px; top: 8px; width: 30px; height: 30px; display: grid; place-items: center;",
      "  background: none; border: 0; color: var(--dim); font-size: 20px; cursor: pointer; }",
      ".fl-card .hc-x:hover { color: var(--ink); }",
      ".fl-card .hc-acts .v2-btn { flex-direction: column; align-items: flex-start; gap: 3px; min-height: 40px; height: auto; display: inline-flex; }",
      ".fl-mark { position: relative; display: inline-flex; flex: none; }",
      ".fl-swatch { position: absolute; right: -2px; bottom: -2px; width: 8px; height: 8px; border-radius: 50%;",
      "  box-shadow: 0 0 0 1px var(--edge), 1px 1px 2px rgba(0, 0, 0, .6); }",
      ".fl-swatch.is-big { width: 12px; height: 12px; }",
      ".fl-group { margin: 10px 0 4px; color: var(--dim); font: 400 13px/1.2 var(--display); letter-spacing: .06em; font-variant: small-caps; }",
      ".fl-group:first-of-type { margin-top: 2px; }",
      ".fl-why { margin: 6px 0 0; color: var(--dim); font-size: 13px; }",
      ".fl-confirm.is-loose { z-index: 31; }",
      ".fl-confirm .bench-danger { border-color: var(--alarm); }",
      ".fl-alarm { color: var(--alarm); font: 600 19px/1.35 var(--body); }",
      ".fl-journal .fl-rows { grid-template-columns: repeat(2, minmax(0, 1fr)); }",
      "@media (max-width: 900px) { .fl-journal .fl-rows { grid-template-columns: minmax(0, 1fr); } }",
      ".fl-journal .fl-tools { margin: 0 0 8px; }",
      ".fl-row { all: unset; cursor: pointer; display: inline-flex; gap: 10px; align-items: center; }",
      ".fl-row:focus-visible { outline: 2px solid var(--gold); outline-offset: 3px; }",
      ".fl-mark:empty { display: none; }",
      ".fl-jr-body .hc-props { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }",
      ".fl-jr-body .hc-props li { display: grid; gap: 1px; }",
      ".fl-jr-body .hc-how, .fl-jr-body .is-unknown { color: var(--dim); font-size: 13px; }",
      ".fl-jr-body .is-unknown { grid-template-columns: 22px 1fr; align-items: center; gap: 8px; }",
      ".fl-jr-body .hc-rule { display: block; height: 1px; background: var(--dim); }",
    ].join("\n");
    document.head.appendChild(s);
  }

  // --- the card beside the rack ----------------------------------------------------------
  var el = null;           // the card's element, made on first use
  var cache = {};          // id -> the card body, until something is learned about it
  var open = null;         // {id, anchor, pinned, opts, wantFocus}
  var closeT = 0;
  var msg = "";
  var busy = false;
  var looseEsc = null;     // the document Esc listener while a loose card is pinned

  // The open bench's handle (29-bench-core.js) when the anchor sits in its layer.
  function benchOf(anchor) {
    var C = core();
    var h = C && C.current;
    return h && h.open && h.layer && anchor && h.layer.contains(anchor) ? h : null;
  }
  function hostFor(anchor, o) {
    if (o && o.pops) return o.pops;
    var h = benchOf(anchor);
    if (h) {
      var pops = h.options && h.options.pops && document.getElementById(h.options.pops);
      return pops || h.layer;
    }
    return document.body;
  }
  function ensure(host) {
    style();
    if (!el) {
      el = document.createElement("div");
      el.className = "bench-card fl-card v2-framed v2-card-leather";
      el.id = "forge-ledger-card";
      el.setAttribute("role", "dialog");
      el.setAttribute("aria-labelledby", "fl-card-name");
      el.hidden = true;
      el.addEventListener("click", onClick);
      el.addEventListener("mouseenter", function () { clearTimeout(closeT); });
      el.addEventListener("mouseleave", function () {
        if (open && !open.pinned) closeT = setTimeout(function () { if (open && !open.pinned) hide(false); }, 220);
      });
    }
    if (el.parentNode !== host) host.appendChild(el);
    el.classList.toggle("is-loose", host === document.body);
  }

  function place(anchor, o) {
    if (!el) return;
    var rackEl = (o && o.beside) || (anchor && anchor.closest && anchor.closest("[data-forge-rack]")) ||
                 document.getElementById("forge-rack");
    var sr = rackEl && document.contains(rackEl) ? rackEl.getBoundingClientRect() : null;
    var ar = anchor && document.contains(anchor) ? anchor.getBoundingClientRect() : sr;
    var w = Math.min(340, innerWidth - 24);
    el.style.width = w + "px";
    var h = el.offsetHeight || 260;
    var left, top;
    if (sr && sr.right + 14 + w <= innerWidth - 8) {
      // Beside the rack, level with the row (the desktop layout).
      left = sr.right + 14;
      top = ar ? ar.top - 12 : sr.top;
    } else {
      // Stacked layouts, or no rack: under the row.
      left = Math.max(8, Math.min(innerWidth - w - 8, (ar ? ar.left : 8) + 12));
      top = ar ? ar.bottom + 6 : 80;
    }
    top = Math.max(8, Math.min(innerHeight - h - 8, top));
    el.style.left = Math.round(left) + "px";
    el.style.top = Math.round(top) + "px";
  }

  function draw() {
    if (!open || !el) return;
    var c = cache[open.id];
    if (!c) {
      el.innerHTML = '<i class="v2-rim" aria-hidden="true"></i><div class="hc-in"><div class="hc-head">' +
        '<span class="sk-disc is-big"></span><div><h3 id="fl-card-name">' + esc(open.name || "") +
        '</h3><span class="sk-bar"></span></div></div><span class="sk-bar"></span>' +
        '<span class="sk-bar is-short"></span><p class="vh">Loading.</p></div>';
      return;
    }
    if (c.error) {
      el.innerHTML = '<i class="v2-rim" aria-hidden="true"></i><div class="hc-in"><h3 id="fl-card-name">Couldn\'t load this material.</h3>' +
        '<p class="hc-sub">' + esc(c.error) + '</p><button type="button" class="v2-btn is-small" data-fl="retry">Retry</button></div>';
      return;
    }
    el.innerHTML = cardHtml(c, { actions: true, pinned: open.pinned, msg: msg, busy: busy, smiths: open.opts.smiths });
  }

  function fetchCard(id) {
    return api("/api/forge/material/" + encodeURIComponent(id)).then(function (c) {
      cache[id] = c;
      return c;
    }).catch(function (err) {
      cache[id] = { error: err.message || String(err), transient: true };
      return cache[id];
    }).then(function (c) {
      if (open && open.id === id) { draw(); place(open.anchor, open.opts); focusIn(); }
      if (c && c.transient) delete cache[id];
      return c;
    });
  }

  // A pinned card takes the keyboard to its first action once there is one: on a first
  // visit the card is still a skeleton when it opens, and focus waits for the answer.
  function focusIn() {
    if (!open || !open.wantFocus || !el) return;
    var first = el.querySelector("[data-fl]:not([data-fl='close']):not([disabled])") || el.querySelector("[data-fl]");
    if (first) { open.wantFocus = false; first.focus(); }
  }

  function pushEsc() {
    var h = benchOf(open && open.anchor);
    if (h) { h.pushEsc(escClose); return; }
    if (looseEsc) return;
    // Capture phase, and stopped there: the table closes its Journal sheet on Esc from a
    // document listener, and seen live (2026-10-04) one Esc closed the card AND the
    // Journal under it. One Esc, one layer.
    looseEsc = function (e) {
      if (e.key !== "Escape" || !open || !open.pinned || document.querySelector(".fl-confirm")) return;
      e.preventDefault();
      e.stopPropagation();
      escClose();
    };
    document.addEventListener("keydown", looseEsc, true);
  }
  function dropEsc() {
    var C = core();
    if (C && C.current && C.current.dropEsc) C.current.dropEsc(escClose);
    if (looseEsc) { document.removeEventListener("keydown", looseEsc, true); looseEsc = null; }
  }

  function show(id, anchor, o) {
    o = o || {};
    if (!id) return;
    clearTimeout(closeT);
    var same = open && open.id === id;
    if (same && open.pinned && o.peek) return;    // a hover never unpins a pinned card
    var wasPinned = !!(open && open.pinned);
    var pinned = !o.peek || (same && open.pinned);
    if (open && !same && wasPinned) dropEsc();
    open = { id: id, anchor: anchor, pinned: pinned, opts: o, name: o.name || "", wantFocus: false };
    // A card the player opened is a panel opening; a hover's glance is not.
    if (pinned && !wasPinned) sound("ui.open");
    if (!same) msg = "";
    ensure(hostFor(anchor, o));
    el.hidden = false;
    el.classList.toggle("is-pinned", pinned);
    draw();
    place(anchor, o);
    if (!cache[id]) fetchCard(id);
    if (pinned) {
      if (!wasPinned || !same) pushEsc();
      open.wantFocus = true;
      focusIn();
    }
  }

  function hide(back) {
    clearTimeout(closeT);
    var was = open;
    dropEsc();
    open = null;
    if (el) el.hidden = true;
    if (was && was.pinned) sound("ui.close");
    if (back && was && was.anchor && document.contains(was.anchor) && was.anchor.focus) was.anchor.focus();
  }
  function escClose() { hide(true); }

  // --- learning ------------------------------------------------------------------------------
  function learnedLine(r, how) {
    var rev = (r && r.revealed) || [];
    var bits = rev.map(function (p) {
      var row = p.row || {};
      return (row.drawback ? "drawback, " : "") + (p.text || p.key);
    });
    return bits.length ? how + " Learned: " + bits.join("; ") + "." : how + " Nothing new.";
  }
  function after(id, r, line) {
    delete cache[id];
    msg = line;
    busy = false;
    // The forge's shell redraws the rack, the clock and the footer from this answer (the
    // sliver is gone and ten minutes passed); the card does not own them.
    var detail = { material: id, response: r, said: line };
    try { document.dispatchEvent(new CustomEvent("forge:learned", { detail: detail })); } catch (err) { /* old engines */ }
    if (open && open.opts && typeof open.opts.after === "function") {
      try { open.opts.after(detail); } catch (err) { /* the card still redraws */ }
    }
    if (open && open.id === id) { open.wantFocus = true; draw(); return fetchCard(id); }
  }
  function failed(id, err) {
    busy = false;
    msg = err && err.message ? err.message : String(err);
    if (open && open.id === id) { draw(); open.wantFocus = true; focusIn(); }
  }

  function confirmHtml(c) {
    return '<div class="bench-scrim"></div><div class="bench-dialog v2-framed v2-card-leather">' +
      '<i class="v2-rim" aria-hidden="true"></i>' +
      '<h3 id="fl-confirm-t">Assay ' + esc(c.name) + '</h3>' +
      '<div id="fl-confirm-b"><p class="fl-alarm">' + esc(reactiveLine(c.name)) + '</p>' +
      '<p class="fl-alarm">' + esc(dangerWords(c) || "Testing it can turn on you, whatever the roll says.") + '</p>' +
      '<p>' + esc("It takes " + assayCost(c) + ".") + '</p></div>' +
      '<div class="bench-dialog-acts"><button type="button" class="v2-btn is-quiet" data-no>Keep it</button>' +
      '<button type="button" class="v2-btn is-quiet bench-danger" data-yes>Assay it</button></div></div>';
  }

  // A modal of the card's own: the safe button first and focused, Esc is the safe one.
  // Inside the bench's layer it is a `.bench-modal`, so the core's trap holds Tab in it.
  function confirmReactive(c) {
    return new Promise(function (done) {
      var host = hostFor(open && open.anchor, open && open.opts);
      var h = benchOf(open && open.anchor);
      var back = document.activeElement;
      var wrap = document.createElement("div");
      wrap.className = "bench-modal bench-confirm fl-confirm" + (host === document.body ? " is-loose" : "");
      wrap.setAttribute("role", "alertdialog");
      wrap.setAttribute("aria-modal", "true");
      wrap.setAttribute("aria-labelledby", "fl-confirm-t");
      wrap.setAttribute("aria-describedby", "fl-confirm-b");
      wrap.innerHTML = confirmHtml(c);
      host.appendChild(wrap);
      var onKey = null;
      var finish = function (v) {
        if (h) h.dropEsc(onEsc);
        if (onKey) document.removeEventListener("keydown", onKey, true);
        wrap.remove();
        if (back && document.contains(back) && back.focus) back.focus();
        done(v);
      };
      var onEsc = function () { finish(false); };
      if (h) h.pushEsc(onEsc);
      else {
        onKey = function (e) { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); finish(false); } };
        document.addEventListener("keydown", onKey, true);
      }
      wrap.querySelector("[data-no]").addEventListener("click", function () { finish(false); });
      wrap.querySelector("[data-yes]").addEventListener("click", function () { finish(true); });
      wrap.querySelector(".bench-scrim").addEventListener("click", function () { finish(false); });
      wrap.querySelector("[data-no]").focus();
    });
  }

  // The table's d20 for the player's own throw, as the herb bench's Study does (35); the
  // server rolls when there is no mat. The DC shown on the die is the card's `assay_dc`.
  function assay(c) {
    var id = c.id;
    var dice = window.Dice3D;
    var shown = { title: "Assay " + c.name, why: "Craft (blacksmith)", sides: 20, lo: 1, hi: 20, die: "1d20", terms: [] };
    busy = true;
    draw();
    var asking = dice && typeof dice.ask === "function" ? dice.ask(Object.assign({ hold: true }, shown)) : Promise.resolve(null);
    var C = core();
    if (dice && C && C.focusMat) C.focusMat();
    var r = null;
    return asking.then(function (face) {
      return api("/api/forge/assay", { material: id, face: face == null ? null : face });
    }).then(function (res) {
      r = res;
      sound("forge.assay");
      if (!dice || !r.roll || typeof dice.land !== "function") return null;
      var roll = r.roll;
      var terms = [];
      if (roll.bonus != null) terms.push({ label: "your bonus", value: sign(roll.bonus) });
      if (c.assay_dc != null) terms.push({ label: "beat", value: c.assay_dc });
      var closing = dice.land(Object.assign({}, shown, { result: roll.face, terms: terms }));
      var rest = typeof dice.settled === "function" ? dice.settled() : null;
      // The engine's word on it, only when it sent one; never compared here.
      if (typeof showVerdict === "function" && typeof roll.success === "boolean") {
        showVerdict({ verdict: roll.success ? "success" : "failure", natural: roll.face === 20 ? 20 : roll.face === 1 ? 1 : null }, rest);
      }
      return closing;
    }).then(function () {
      var roll = r.roll || {};
      var how = "You assayed " + c.name + (roll.total != null
        ? " (d20 " + roll.face + " " + sign(roll.bonus) + " = " + roll.total + ")." : ".");
      var hurt = dangerWords({ assay_danger: r.danger_text || r.danger });
      var line = learnedLine(r, how) + (hurt ? " " + hurt : "") +
        (r.minutes ? " " + minutesWords(r.minutes) + " passed." : "");
      return after(id, r, line);
    }).catch(function (err) {
      if (dice && dice.close) { try { dice.close(); } catch (e2) { /* */ } }
      failed(id, err);
    });
  }

  function ask(c, ref) {
    busy = true;
    draw();
    return api("/api/forge/ask", { material: c.id, ref: ref }).then(function (r) {
      return after(c.id, r, learnedLine(r, "You asked."));
    }).catch(function (err) {
      // A build whose server has no ask route answers with Django's page, not a sentence.
      if (err && err.status === 404 && !/[a-z]/.test(String(err.message).replace(/The server failed \(HTTP 404\)\./, "")))
        err = new Error("Asking a smith is not in this build yet.");
      failed(c.id, err);
    });
  }

  function onClick(e) {
    var b = e.target.closest("[data-fl]");
    if (!b || !open) return;
    var id = open.id, c = cache[id];
    var k = b.dataset.fl;
    if (k === "close") { hide(true); return; }
    if (k === "retry") { fetchCard(id); return; }
    if (!c || busy) return;
    // Hovering opened it; acting on it pins it, so the answer stays to be read.
    if (!open.pinned) { open.pinned = true; el.classList.add("is-pinned"); pushEsc(); }
    if (k === "assay") {
      if (!needsConfirm(c)) { assay(c); return; }
      confirmReactive(c).then(function (yes) { if (yes && open && open.id === id) assay(c); });
      return;
    }
    if (k === "ask") ask(c, b.dataset.ref);
  }

  // A click outside a pinned card puts it away (the confirm and the dice mat excepted).
  document.addEventListener("pointerdown", function (e) {
    if (!open || !open.pinned || !el || el.contains(e.target)) return;
    if (e.target.closest && (e.target.closest(".fl-confirm") || e.target.closest("#d3d-mat") ||
        (open.anchor && open.anchor.contains && open.anchor.contains(e.target)))) return;
    hide(false);
  });
  addEventListener("resize", function () { if (open) place(open.anchor, open.opts); });

  // --- the Journal's section ----------------------------------------------------------------
  function journal(host) {
    if (!host) return null;
    style();
    host.classList.add("fl-journal");
    var st = host._forgeLedger;
    if (!st) {
      st = host._forgeLedger = { ledger: null, error: "", open: "", cards: {}, unknownFirst: false };
      host.addEventListener("click", function (e) {
        if (e.target.closest("[data-fl-retry]")) { read(); return; }
        var sort = e.target.closest("[data-fl-sort]");
        if (sort) {
          st.unknownFirst = !st.unknownFirst;
          sort.setAttribute("aria-pressed", String(st.unknownFirst));
          drawList();
          return;
        }
        var row = e.target.closest("[data-fl-mat]");
        if (!row) return;
        var id = row.dataset.flMat;
        st.open = st.open === id ? "" : id;
        drawList();
        var again = host.querySelector('[data-fl-mat="' + (window.CSS && CSS.escape ? CSS.escape(id) : id) + '"]');
        if (again) again.focus();
        if (st.open) readCard(id);
      });
    }
    st.ledger = null;
    st.error = "";
    st.cards = {};
    host.innerHTML = '<div class="fl-tools"><button type="button" class="v2-btn is-small" data-fl-sort aria-pressed="' +
      st.unknownFirst + '">Unknowns first</button></div>' +
      '<div class="fl-list" role="list" aria-label="Materials you have met"></div>';
    function drawList() {
      var box = host.querySelector(".fl-list");
      if (box) box.innerHTML = rowsHtml(st);
    }
    function read() {
      st.error = "";
      st.ledger = null;
      drawList();
      return api("/api/forge/ledger").then(function (d) {
        st.ledger = (d && d.ledger) || [];
      }).catch(function (err) {
        st.error = err.status === 501 ? err.message : "Couldn't read the ledger. " + (err.message || "");
      }).then(drawList);
    }
    function readCard(id) {
      return api("/api/forge/material/" + encodeURIComponent(id)).then(function (c) {
        st.cards[id] = c;
      }).catch(function (err) {
        st.cards[id] = { error: err.message || String(err) };
      }).then(function () { if (st.open === id) drawList(); });
    }
    st.read = read;
    read();
    return { refresh: read };
  }

  window.ForgeLedger = {
    card: function (materialId, anchorEl, opts) { show(materialId, anchorEl, opts); },
    peek: function (materialId, anchorEl, opts) { show(materialId, anchorEl, Object.assign({}, opts, { peek: true })); },
    // A beat before an unpinned card goes, so the pointer can cross from the row onto it.
    unpeek: function () {
      if (!open || open.pinned) return;
      clearTimeout(closeT);
      closeT = setTimeout(function () { if (open && !open.pinned) hide(false); }, 220);
    },
    close: function () { hide(false); },
    isOpen: function () { return !!open; },
    // After a step at the forge reveals working traits, the card must be read again.
    forget: function (materialId) { if (materialId) delete cache[materialId]; else cache = {}; },
    journal: journal,
    // The renderers, for tests and for the forge's shell; pure: data in, markup out.
    render: { card: cardHtml, props: propsHtml, rows: rowsHtml, found: foundLine, reactive: reactiveLine,
              confirm: confirmHtml, needsConfirm: needsConfirm, danger: dangerWords },
  };
})();
