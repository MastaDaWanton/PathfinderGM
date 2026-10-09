// The play table, part 44 (the materials ledger: the card beside a bench's rack and the
// Journal's ledgers). Classic script in one IIFE, reached through `window.MaterialLedger`,
// with `window.ForgeLedger` kept as the forge's thin alias (leatherworking contracts §11.1).
//
// Blacksmithing UI plan §6.7, the herbarium's counterpart (35-bench-herbarium.js), and
// leatherworking UI plan §6.7, which asked for this file "parameterised by track" rather
// than a second copy beside it (as 36-bench-perks.js was): the forge's assay and the
// tanner's Grade differ only in words and routes, and two cards would drift (CLAUDE.md,
// "when you fix a rule, grep for every copy of it"). Two surfaces, one renderer, a row of
// TRACKS below for what differs:
//
//   MaterialLedger.card(track, materialId, anchorEl, opts)  the card beside a bench's
//       rack: the engraved icon and the material's swatch, its name, what it is, each
//       known property with how it was learned ("assayed, day 14", "graded, day 3"), one
//       "unknown" line per property still unknown, and two actions: the track's own test
//       (Assay a sliver; Grade a scrap) and its teacher (Ask a smith; Ask a tanner), the
//       teacher only when the server names one here.
//   MaterialLedger.journal(host, track)  the Journal's section: every material met,
//       "3 of 7 known", an "Unknowns first" toggle, and each material's known lines on a
//       disclosure.
//   ForgeLedger.card(materialId, anchorEl, opts), .peek, .unpeek, .journal(host) ...
//       exactly as before, the blacksmith row of the same code.
//
// Both read the track's `GET <api>/ledger` and `GET <api>/material/<id>` and show only what
// the character KNOWS: the server sends an unknown property with its text null
// (rules/knowledge.py `properties`), so nothing here can show a secret by mistake, and
// nothing is filled in from the material's own data.
//
// UNKNOWN ROWS AND THEIR GROUP. The smith's card files an unknown line under where it acts
// ("that the iron does *something* to a blade is visible on the anvil", knowledge.py), and
// keeps doing so. The tanner's does not: Grade reveals one benefit and one drawback (lane
// F), and an unknown row under "In armour" says where the next one will be before any
// Grade has found it, the leak the alchemy lane closed on 2026-10-07 (its unknown rows
// carry no group). The leather card files unknown lines under no heading of their own
// kind, whatever the server sends with them.
//
// MARKS (leatherworking plan §14.6; held for a day, kept as planned by the owner 2026-10-08):
// a tannin's, oil's, wax's, thread's or dye's one small mark is a property like any other,
// under its own heading ("On the finished item") once known. Unknown, it is a blank row with
// no group like every other unknown on the tanner's card, so the page never learns that a
// consumable has a mark before Grade finds it.
//
// EVERY NUMBER IS THE SERVER'S (UI plan §12). The DC, the count carried, the hide units, the
// minutes, the roll and its total, the mastery are read from responses and printed; nothing
// is compared or summed here beyond "is any carried". In particular the verdict word is
// shown only when the response carries `roll.success`: deciding it from total and DC on the
// page would be the page authoring a result. Fields the card reads when present and leaves
// out when absent: `color` (the swatch), `found`/`obtain`/`source`/`biomes` (where found or
// bought), `assay_minutes`/`grade_minutes` and `grade_cost`, `smiths_here`/`tanners_here`,
// `assay_danger` (what testing it does, in words).
//
// THE REACTIVE ASSAY (blacksmithing UI plan §6.7, contracts §13.2). Assaying abysium
// sickens (the book) and assaying noqual makes magic recoil, suppressing the assayer's
// active magic for 1d4 rounds (the owner's house rule), so it always asks first, in
// --alarm words, with the safe button focused. Whether to ask is the server's
// `assay_danger`, else its `reactive`. A hide never bites when graded (the owner's answer
// 10, 2026-10-08: dangerous creatures force a check while skinning, not at Grade), and the
// leather card sends neither field, so Grade never asks.
//
// WHERE THE CARD LIVES. Inside the bench's own layer when the anchor is in one (the core's
// trap wraps Tab inside the layer, so a card appended to <body> would have buttons the
// keyboard cannot reach), on the layer's Esc stack (29-bench-core.js, one Esc closes one
// popover); loose on <body> at the table's popover height otherwise. One card on the page
// at a time, whichever track opened it.
//
// HOW IT OPENS. A leather row opens its card from its "?" only (`card`, pinned), never by
// hovering or focusing the row: the owner's emergency fix of 2026-10-08 found a card opened
// by a row covering the next rows and making the list unusable. `peek`/`unpeek` stay for the
// forge's alias, whose rack still calls them.
//
// Styles are injected once from here (`#forge-ledger-style`) with the theme's tokens only:
// this lane owns no stylesheet, and the herb card's classes in bench.css give the same
// leather, rim and type for free. MOTION: nothing loops (no setInterval, no
// requestAnimationFrame); tests/test_forge_ledger_ui.py and test_leather_ledger_ui.py grep.

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
          e.data = data;
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

  // --- the tracks ---------------------------------------------------------------------------
  // Which list a property sits in (rules/knowledge.py MATERIAL_LISTS). `shield` is lane F's
  // (leatherworking, 2026-10-08): a hide written with a shield list has properties the card
  // must be able to head, and before this no UI labelled it.
  var GROUP_ORDER = ["product", "weapon", "armour", "shield", "working", "quench_mark", "mark", "mishap", "toxic", ""];
  var TRACKS = {
    blacksmith: {
      api: "/api/forge", test: "assay", testWord: "Assay", testRoute: "/api/forge/assay",
      testWhy: "Craft (blacksmith)", testSound: "forge.assay", testDid: "You assayed ",
      dcField: "assay_dc", minutesField: "assay_minutes", costField: "",
      cost: "a sliver", none: "You carry none of it to take a sliver from.",
      askers: "smiths_here", askWord: "Ask a smith", askRoute: "/api/forge/ask",
      askMissing: "Asking a smith is not in this build yet.",
      event: "forge:learned", rack: "[data-forge-rack]", rackId: "forge-rack",
      groups: { weapon: "In a weapon", armour: "In armour", shield: "In a shield",
                working: "At the anvil", quench_mark: "In the quench" },
      unknownGrouped: true, hide: [],
      list: "Materials you have met",
      empty: "No materials yet. Buy or mine one and it appears here.",
      readFailed: "Couldn't read the ledger. ",
    },
    leatherworker: {
      api: "/api/leather", test: "grade", testWord: "Grade", testRoute: "/api/leather/grade",
      testWhy: "Craft (leatherworker)", testSound: "leather.grade", testDid: "You graded ",
      dcField: "grade_dc", minutesField: "grade_minutes", costField: "grade_cost",
      cost: "a scrap", none: "You carry none of it to take a scrap from.",
      askers: "tanners_here", askWord: "Ask a tanner", askRoute: "/api/leather/ask",
      askMissing: "Asking a tanner is not in this build yet.",
      event: "leather:learned", rack: "[data-leather-rack]", rackId: "leather-rack",
      // Where a hide's property acts. The working traits are the tanner's own (thick,
      // fast_tan, supple, strong_seam: leatherworking contracts §2), read at the beam, the
      // vat and the bench alike, so the heading names the bench rather than one tool.
      groups: { weapon: "In a weapon", armour: "In armour", shield: "In a shield",
                working: "At the bench", mark: "On the finished item" },
      unknownGrouped: false, hide: [],
      // A hide's or a tannin's known drawbacks are drawbacks, not dangers: no hide bites
      // back (the owner's answer 10). The Journal read "You know this is dangerous: Tans
      // slowly" and "...: Weighs 20% more" (the final pass, live, 2026-10-09).
      drawbacksSaid: "Its known drawbacks: ",
      list: "Hides and supplies you have met",
      empty: "No hides or supplies yet. Take one from a carcass or buy one and it appears here.",
      readFailed: "Couldn't read the tanner's ledger. ",
    },
  };
  function rowOf(track) { return TRACKS[track] || TRACKS.blacksmith; }

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
  // The test's cost line: the server's words when it sends them ("a quarter unit of hide",
  // "one measure"), else the track's ("a sliver"); the minutes only when the server said them.
  function testCost(c, T) {
    T = T || TRACKS.blacksmith;
    var bits = [(T.costField && c[T.costField]) || T.cost];
    if (c[T.minutesField] != null) bits.push(minutesWords(c[T.minutesField]));
    return bits.join(", ");
  }
  function reactiveLine(name) { return name + " reacts badly to testing. Assay it anyway?"; }
  // What testing it does to the tester, in the server's words. Abysium sickens (the book);
  // noqual's magic recoils and suppresses the assayer's active magic for 1d4 rounds (the
  // owner's house rule, contracts §13.2). Both are the material's own data, so the page
  // names no metal: it prints `assay_danger` (a sentence, or {text}) when the card carries
  // it, and a plain warning when it does not.
  function dangerWords(c) {
    var d = c.assay_danger;
    var t = d && typeof d === "object" ? d.text : d;
    return typeof t === "string" && t.trim() ? t.trim() : "";
  }
  // Ask first when the server says the test is dangerous. A card that carries
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
  // How much is carried, in the server's own figures: a hide counts in hide units (lane E's
  // `carried_units`, a quarter unit being one scrap), a supply in measures.
  function carriedWords(c) {
    var bits = [];
    if (Number(c.carried_units) > 0) bits.push(c.carried_units + (Number(c.carried_units) === 1 ? " hide unit" : " hide units") + " carried");
    if (Number(c.carried) > 0) bits.push(c.carried + " carried");
    return bits.join(", ");
  }
  function carriesAny(c) { return Number(c.carried) > 0 || Number(c.carried_units) > 0; }

  // --- the card's body: the one renderer both surfaces draw ----------------------------
  // `opts.actions` adds the action row (the card beside the rack); the Journal draws the
  // same lines without it. `opts.track` picks the row (the blacksmith's when absent).
  function propRow(p) {
    if (!p.known) return '<li class="is-unknown"><span class="hc-rule" aria-hidden="true"></span><span>unknown</span></li>';
    return '<li class="' + (p.drawback ? "is-bad" : "") + '"><span>' +
      (p.drawback ? '<span class="hc-k">Drawback:</span> ' : "") + esc(p.text) + '</span>' +
      (p.how ? '<span class="hc-how">' + esc(p.how) + '</span>' : "") + '</li>';
  }
  function propsHtml(c, o) {
    var T = rowOf(o && o.track);
    var props = (c.properties || []).filter(function (p) { return T.hide.indexOf(p.group || "") < 0; });
    if (!props.length) {
      return c.properties === null
        ? '<p class="hc-sub">What is known of it cannot be read in this build yet.</p>'
        : '<p class="hc-sub">There is nothing to learn about it.</p>';
    }
    // A track that does not file unknown lines by group gives them none, whatever came.
    var filed = T.unknownGrouped ? props : props.filter(function (p) { return p.known; });
    var blind = T.unknownGrouped ? [] : props.filter(function (p) { return !p.known; });
    var groups = {};
    filed.forEach(function (p) { var g = p.group || ""; (groups[g] = groups[g] || []).push(p); });
    var heads = Object.keys(groups);
    var several = heads.length > 1 || (heads.length === 1 && !groups[""]);
    var order = GROUP_ORDER.concat(heads.filter(function (g) { return GROUP_ORDER.indexOf(g) < 0; }));
    var html = order.filter(function (g) { return groups[g]; }).map(function (g) {
      return (several ? '<h4 class="fl-group">' + esc(T.groups[g] || "Otherwise") + '</h4>' : "") +
        '<ul class="hc-props">' + groups[g].map(propRow).join("") + '</ul>';
    }).join("");
    if (blind.length) {
      // Under a heading of its own once the known lines have theirs, so a blank never reads
      // as belonging to the group drawn above it.
      html += (several ? '<h4 class="fl-group">Not yet known</h4>' : "") +
        '<ul class="hc-props">' + blind.map(propRow).join("") + '</ul>';
    }
    return html;
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

  function actionsHtml(c, o, T) {
    var acts = [];
    var none = !carriesAny(c);
    acts.push('<button type="button" class="v2-btn is-small" data-fl="' + T.test + '"' + (none || o.busy ? " disabled" : "") +
      (none ? ' aria-describedby="fl-assay-why"' : "") + '>' + T.testWord + '<span class="hc-cost">' + esc(testCost(c, T)) + '</span></button>');
    var askers = (c[T.askers] && c[T.askers].length ? c[T.askers] : (o.smiths || o.tanners || []));
    askers.forEach(function (s) {
      acts.push('<button type="button" class="v2-btn is-small is-quiet" data-fl="ask" data-ref="' + esc(s.ref) + '"' +
        (o.busy ? " disabled" : "") + '>' + T.askWord + '<span class="hc-cost">' +
        esc([s.name, s.price].filter(Boolean).join(", ")) + '</span></button>');
    });
    return '<div class="hc-acts">' + acts.join("") + '</div>' +
      (none ? '<p class="fl-why" id="fl-assay-why">' + T.none + '</p>' : "");
  }

  // What the material is, in one line: its kind and tier, a hide's surface and size (facts
  // anyone holding it can see, lane E's card), and how much is carried.
  function subLine(c) {
    var size = c.size ? c.size + (c.kind === "hide" ? " hide" : "") : "";
    return [c.kind === "hide" && size ? "" : c.kind, size, c.tier, c.surface, carriedWords(c)]
      .filter(Boolean).join(", ");
  }

  function cardHtml(c, o) {
    o = o || {};
    var T = rowOf(o.track);
    var where = foundLine(c);
    var sub = subLine(c);
    return '<i class="v2-rim" aria-hidden="true"></i><div class="hc-in">' +
      '<div class="hc-head"><span class="fl-mark">' +
        icon(c.form || c.kind || "", { size: 48, tier: c.tier, label: c.name }) + swatch(c.color, true) + '</span>' +
        '<div><h3 id="fl-card-name">' + esc(c.name) + '</h3>' +
        (sub ? '<p class="hc-sub">' + esc(sub) + '</p>' : "") +
        (where ? '<p class="hc-sub">' + esc(where) + '</p>' : "") +
        (c.always_masterwork ? '<p class="hc-sub">Always masterwork, by the book.</p>' : "") + '</div>' +
        (o.pinned ? '<button type="button" class="hc-x" data-fl="close" aria-label="Close the card">×</button>' : "") +
      '</div>' + dangerHtml(c) + propsHtml(c, o) +
      (o.msg ? '<p class="hc-msg" role="status">' + esc(o.msg) + '</p>' : "") +
      (o.actions ? actionsHtml(c, o, T) : "") + '</div>';
  }

  // --- the Journal's rows -------------------------------------------------------------------
  function rowsHtml(st) {
    var T = rowOf(st.track);
    if (st.error) {
      return '<p class="why">' + esc(st.error) + '</p>' +
        '<button type="button" class="v2-btn is-small" data-fl-retry>Retry</button>';
    }
    if (st.ledger === null) return '<p class="why">Reading the ledger.</p>';
    var rows = st.ledger.slice();
    if (!rows.length) return '<p class="why">' + T.empty + '</p>';
    if (st.unknownFirst) {
      rows.sort(function (a, b) {
        return ((b.total - b.known) - (a.total - a.known)) || String(a.name).localeCompare(String(b.name));
      });
    }
    var pre = st.track && st.track !== "blacksmith" ? st.track + "-" : "";
    return '<ul class="plain matters twocol fl-rows">' + rows.map(function (e) {
      var open = st.open === e.id;
      var bodyId = "fl-jr-card-" + pre + esc(e.id);
      return '<li class="matter" role="listitem"><h3><button type="button" class="fl-row" data-fl-mat="' + esc(e.id) + '"' +
        ' aria-expanded="' + open + '" aria-controls="' + bodyId + '">' +
        '<span class="fl-mark">' + icon(e.form || e.kind || "", { size: 26, tier: e.tier, label: e.name }) + swatch(e.color) + '</span>' +
        esc(e.name) + '</button></h3>' +
        '<p class="why">' + esc([e.kind, e.known + " of " + e.total + " known",
          Number(e.carried) > 0 ? e.carried + " carried" : ""].filter(Boolean).join(" · ")) + '</p>' +
        (e.danger_known ? '<p class="why">' + (T.drawbacksSaid || "You know this is dangerous: ") +
          esc(e.danger_known) + '.</p>' : "") +
        '<div id="' + bodyId + '" class="fl-jr-body"' + (open ? "" : " hidden") + '>' +
          (open ? journalBody(st, e.id) : "") + '</div></li>';
    }).join("") + '</ul>';
  }
  function journalBody(st, id) {
    var c = st.cards[id];
    if (!c) return '<p class="why">Reading what you know.</p>';
    if (c.error) return '<p class="why">' + esc(c.error) + '</p>';
    return propsHtml(c, { track: st.track });
  }

  // --- styles, once -------------------------------------------------------------------------
  // Tokens only (theme-v2.css), and the bench's semantic names set on the card itself so it
  // reads the same inside the forge's layer, the tanner's, the herb bench's or none.
  // --alarm at 19px and 600 weight: measured 3.4:1 on the card leather, which passes AA as
  // large text and would not as body text, so the reactive line is never set smaller.
  function style() {
    if (document.getElementById("forge-ledger-style")) return;
    var s = document.createElement("style");
    s.id = "forge-ledger-style";
    s.textContent = [
      ".fl-card, .fl-confirm, .fl-journal { --bench-ink: var(--ink); --bench-quiet: var(--dim); --bench-accent: var(--gold);",
      "  --bench-warn: var(--alarm); --bench-radius: 3px; }",
      ".fl-card { position: fixed; width: 340px; max-height: calc(100vh - 16px); overflow-y: auto; z-index: 7; color: var(--ink);",
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
  var el = null;           // the card's element, made on first use, shared by every track
  var cache = {};          // "track:id" -> the card body, until something is learned about it
  var open = null;         // {track, id, anchor, pinned, opts, wantFocus}
  var closeT = 0;
  var msg = "";
  var busy = false;
  var looseEsc = null;     // the document Esc listener while a loose card is pinned

  function ck(track, id) { return track + ":" + id; }

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
    var T = rowOf(open && open.track);
    var rackEl = (o && o.beside) || (anchor && anchor.closest && anchor.closest(T.rack)) ||
                 document.getElementById(T.rackId);
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
    var c = cache[ck(open.track, open.id)];
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
    el.innerHTML = cardHtml(c, { track: open.track, actions: true, pinned: open.pinned, msg: msg, busy: busy,
                                 smiths: open.opts.smiths, tanners: open.opts.tanners });
  }

  function fetchCard(track, id) {
    var key = ck(track, id);
    return api(rowOf(track).api + "/material/" + encodeURIComponent(id)).then(function (c) {
      cache[key] = c;
      return c;
    }).catch(function (err) {
      // The server says this card is another track's (the forge's 409 for a tanner's
      // material names `track` and `card`): open that ledger's card in its place. Before
      // this it read "Couldn't load this material" with a Retry that could only fail
      // again (the leather final-pass list, 2026-10-08).
      var d = err && err.data;
      if (err && err.status === 409 && d && d.track && d.track !== track && TRACKS[d.track]) {
        if (open && open.track === track && open.id === id) open.track = d.track;
        return fetchCard(d.track, id);
      }
      cache[key] = { error: err.message || String(err), transient: true };
      return cache[key];
    }).then(function (c) {
      if (open && open.track === track && open.id === id) { draw(); place(open.anchor, open.opts); focusIn(); }
      if (c && c.transient) delete cache[key];
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

  function show(track, id, anchor, o) {
    o = o || {};
    if (!id) return;
    track = TRACKS[track] ? track : "blacksmith";
    clearTimeout(closeT);
    var same = open && open.track === track && open.id === id;
    if (same && open.pinned && o.peek) return;    // a hover never unpins a pinned card
    var wasPinned = !!(open && open.pinned);
    var pinned = !o.peek || (same && open.pinned);
    if (open && !same && wasPinned) dropEsc();
    open = { track: track, id: id, anchor: anchor, pinned: pinned, opts: o, name: o.name || "", wantFocus: false };
    // A card the player opened is a panel opening; a hover's glance is not.
    if (pinned && !wasPinned) sound("ui.open");
    if (!same) msg = "";
    ensure(hostFor(anchor, o));
    el.hidden = false;
    el.classList.toggle("is-pinned", pinned);
    draw();
    place(anchor, o);
    if (!cache[ck(track, id)]) fetchCard(track, id);
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
  // What was learned, and the mastery it paid in the server's own lines (`STUDY_MP` a
  // property found, leatherworking's 2026-10-08 ruling): a line is matched to the property
  // its `why` names, so "+1 mastery" stands beside what earned it and nothing is summed.
  function learnedLine(r, how) {
    var rev = (r && r.revealed) || [];
    var paid = ((r && r.mastery && r.mastery.lines) || []).slice();
    var bits = rev.map(function (p) {
      var row = p.row || {};
      var text = p.text || p.key;
      var at = -1;
      for (var i = 0; i < paid.length; i++) {
        var why = String((paid[i] && paid[i].why) || "");
        if (p.text && why.slice(-String(p.text).length) === String(p.text)) { at = i; break; }
      }
      var mp = at >= 0 ? paid.splice(at, 1)[0].mp : null;
      return (row.drawback ? "drawback, " : "") + text + (mp ? " (+" + mp + " mastery)" : "");
    });
    var up = ((r && r.mastery && r.mastery.levelled) || []).map(function (n) { return " Level " + n + " reached."; }).join("");
    return (bits.length ? how + " Learned: " + bits.join("; ") + "." : how + " Nothing new.") + up;
  }
  function after(track, id, r, line) {
    delete cache[ck(track, id)];
    msg = line;
    busy = false;
    // The bench's shell redraws the rack, the clock and the footer from this answer (the
    // sliver or the scrap is gone and minutes passed); the card does not own them.
    var detail = { material: id, track: track, response: r, said: line };
    try { document.dispatchEvent(new CustomEvent(rowOf(track).event, { detail: detail })); } catch (err) { /* old engines */ }
    if (open && open.opts && typeof open.opts.after === "function") {
      try { open.opts.after(detail); } catch (err) { /* the card still redraws */ }
    }
    if (open && open.track === track && open.id === id) { open.wantFocus = true; draw(); return fetchCard(track, id); }
  }
  function failed(track, id, err) {
    busy = false;
    msg = err && err.message ? err.message : String(err);
    if (open && open.track === track && open.id === id) { draw(); open.wantFocus = true; focusIn(); }
  }

  function confirmHtml(c) {
    return '<div class="bench-scrim"></div><div class="bench-dialog v2-framed v2-card-leather">' +
      '<i class="v2-rim" aria-hidden="true"></i>' +
      '<h3 id="fl-confirm-t">Assay ' + esc(c.name) + '</h3>' +
      '<div id="fl-confirm-b"><p class="fl-alarm">' + esc(reactiveLine(c.name)) + '</p>' +
      '<p class="fl-alarm">' + esc(dangerWords(c) || "Testing it can turn on you, whatever the roll says.") + '</p>' +
      '<p>' + esc("It takes " + testCost(c, TRACKS.blacksmith) + ".") + '</p></div>' +
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
  // server rolls when there is no mat. The DC shown on the die is the server's: the roll's
  // own `dc` when it sends one, else the card's `assay_dc` / `grade_dc`.
  function learn(track, c) {
    var T = rowOf(track);
    var id = c.id;
    var dice = window.Dice3D;
    var shown = { title: T.testWord + " " + c.name, why: T.testWhy, sides: 20, lo: 1, hi: 20, die: "1d20", terms: [] };
    busy = true;
    draw();
    var asking = dice && typeof dice.ask === "function" ? dice.ask(Object.assign({ hold: true }, shown)) : Promise.resolve(null);
    var C = core();
    if (dice && C && C.focusMat) C.focusMat();
    var r = null;
    return asking.then(function (face) {
      return api(T.testRoute, { material: id, face: face == null ? null : face });
    }).then(function (res) {
      r = res;
      sound(T.testSound);
      if (!dice || !r.roll || typeof dice.land !== "function") return null;
      var roll = r.roll;
      var terms = [];
      if (roll.bonus != null) terms.push({ label: "your bonus", value: sign(roll.bonus) });
      var dc = roll.dc != null ? roll.dc : c[T.dcField];
      if (dc != null) terms.push({ label: "beat", value: dc });
      var closing = dice.land(Object.assign({}, shown, { result: roll.face, terms: terms }));
      var rest = typeof dice.settled === "function" ? dice.settled() : null;
      // The engine's word on it, only when it sent one; never compared here.
      if (typeof showVerdict === "function" && typeof roll.success === "boolean") {
        showVerdict({ verdict: roll.success ? "success" : "failure", natural: roll.face === 20 ? 20 : roll.face === 1 ? 1 : null }, rest);
      }
      return closing;
    }).then(function () {
      var roll = r.roll || {};
      var how = T.testDid + c.name + (roll.total != null
        ? " (d20 " + roll.face + " " + sign(roll.bonus) + " = " + roll.total + ")." : ".");
      var hurt = dangerWords({ assay_danger: r.danger_text || r.danger });
      var line = learnedLine(r, how) + (hurt ? " " + hurt : "") +
        (r.minutes ? " " + minutesWords(r.minutes) + " passed." : "");
      return after(track, id, r, line);
    }).catch(function (err) {
      if (dice && dice.close) { try { dice.close(); } catch (e2) { /* */ } }
      failed(track, id, err);
    });
  }

  function ask(track, c, ref) {
    var T = rowOf(track);
    busy = true;
    draw();
    return api(T.askRoute, { material: c.id, ref: ref }).then(function (r) {
      // A teacher who will not help, or has nothing new, or whom you cannot pay, answers
      // in the server's own sentence; "You asked. Nothing new." would hide why.
      if (r && r.refused) return after(track, c.id, r, String(r.refused));
      return after(track, c.id, r, learnedLine(r, "You asked.") + (r && r.paid ? " " + r.paid + " paid." : ""));
    }).catch(function (err) {
      // A build whose server has no ask route answers with Django's page, not a sentence.
      if (err && err.status === 404 && !/[a-z]/.test(String(err.message).replace(/The server failed \(HTTP 404\)\./, "")))
        err = new Error(T.askMissing);
      failed(track, c.id, err);
    });
  }

  function onClick(e) {
    var b = e.target.closest("[data-fl]");
    if (!b || !open) return;
    var track = open.track, id = open.id, c = cache[ck(track, id)];
    var k = b.dataset.fl;
    if (k === "close") { hide(true); return; }
    if (k === "retry") { fetchCard(track, id); return; }
    if (!c || busy) return;
    // Hovering opened it; acting on it pins it, so the answer stays to be read.
    if (!open.pinned) { open.pinned = true; el.classList.add("is-pinned"); pushEsc(); }
    if (k === "assay" || k === "grade") {
      if (!needsConfirm(c)) { learn(track, c); return; }
      confirmReactive(c).then(function (yes) { if (yes && open && open.track === track && open.id === id) learn(track, c); });
      return;
    }
    if (k === "ask") ask(track, c, b.dataset.ref);
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
  function journal(host, track) {
    if (!host) return null;
    track = TRACKS[track] ? track : "blacksmith";
    var T = TRACKS[track];
    style();
    host.classList.add("fl-journal");
    var st = host._matLedger;
    if (!st) {
      st = host._matLedger = { track: track, ledger: null, error: "", open: "", cards: {}, unknownFirst: false };
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
    st.track = track;
    st.ledger = null;
    st.error = "";
    st.cards = {};
    host.innerHTML = '<div class="fl-tools"><button type="button" class="v2-btn is-small" data-fl-sort aria-pressed="' +
      st.unknownFirst + '">Unknowns first</button></div>' +
      '<div class="fl-list" role="list" aria-label="' + T.list + '"></div>';
    function drawList() {
      var box = host.querySelector(".fl-list");
      if (box) box.innerHTML = rowsHtml(st);
    }
    function read() {
      st.error = "";
      st.ledger = null;
      drawList();
      return api(T.api + "/ledger").then(function (d) {
        st.ledger = (d && d.ledger) || [];
      }).catch(function (err) {
        st.error = err.status === 501 ? err.message : T.readFailed + (err.message || "");
      }).then(drawList);
    }
    function readCard(id) {
      return api(T.api + "/material/" + encodeURIComponent(id)).then(function (c) {
        st.cards[id] = c;
      }).catch(function (err) {
        st.cards[id] = { error: err.message || String(err) };
      }).then(function () { if (st.open === id) drawList(); });
    }
    st.read = read;
    read();
    return { refresh: read };
  }

  var render = { card: cardHtml, props: propsHtml, rows: rowsHtml, found: foundLine, reactive: reactiveLine,
                 confirm: confirmHtml, needsConfirm: needsConfirm, danger: dangerWords, learned: learnedLine };

  window.MaterialLedger = {
    card: function (track, materialId, anchorEl, opts) { show(track, materialId, anchorEl, opts); },
    peek: function (track, materialId, anchorEl, opts) {
      show(track, materialId, anchorEl, Object.assign({}, opts, { peek: true }));
    },
    // A beat before an unpinned card goes, so the pointer can cross from the row onto it.
    unpeek: function () {
      if (!open || open.pinned) return;
      clearTimeout(closeT);
      closeT = setTimeout(function () { if (open && !open.pinned) hide(false); }, 220);
    },
    close: function () { hide(false); },
    isOpen: function (track) { return !!open && (!track || open.track === track); },
    // After a step reveals working traits, the card must be read again.
    forget: function (track, materialId) {
      if (!track) { cache = {}; return; }
      if (materialId) { delete cache[ck(track, materialId)]; return; }
      Object.keys(cache).forEach(function (k) { if (k.indexOf(track + ":") === 0) delete cache[k]; });
    },
    journal: function (host, track) { return journal(host, track); },
    tracks: TRACKS,
    // The renderers, for tests and for the shells; pure: data in, markup out.
    render: render,
  };

  // The forge's names, unchanged (blacksmithing contracts §11): the blacksmith row.
  window.ForgeLedger = {
    card: function (materialId, anchorEl, opts) { show("blacksmith", materialId, anchorEl, opts); },
    peek: function (materialId, anchorEl, opts) { window.MaterialLedger.peek("blacksmith", materialId, anchorEl, opts); },
    unpeek: window.MaterialLedger.unpeek,
    close: window.MaterialLedger.close,
    isOpen: function () { return !!open; },
    forget: function (materialId) {
      if (materialId) delete cache[ck("blacksmith", materialId)];
      else window.MaterialLedger.forget("blacksmith");
    },
    journal: function (host) { return journal(host, "blacksmith"); },
    render: render,
  };

  // The tanner's four perks on the shared picker (36-bench-perks.js, parameterised by track
  // for the forge): the forge's four with Yield read at the harvest (owner Q6.3). What each
  // next pick does is lane E's `perk_info[id].next` with its numbers; these words are only
  // the fallback and carry no number. Registered on the picker's own table, from here,
  // because 36 is read-only to this lane; the leather shell calls
  // `BenchPerks.open({track: "leatherworker", ...})` as the forge calls it with "blacksmith".
  // The icon names are the plan's proposed set (leatherworking UI plan §4): until their art
  // lands, bench-icons.js draws its lettered roundel for each.
  var P = window.BenchPerks;
  if (P && P.tracks && !P.tracks.leatherworker) {
    P.tracks.leatherworker = {
      prefix: "leather", title: "Leatherworker", route: "/api/leather/perks",
      perks: [
        { id: "potency", name: "Potency", words: "The bonuses of everything you make are stronger." },
        { id: "hardening", name: "Hardening", words: "The drawbacks of everything you make are softer." },
        { id: "quality", name: "Quality", words: "Your ceiling rises one rung." },
        { id: "yield", name: "Extra yield", words: "A chance of more hide from each one you harvest." },
      ],
      icon: { potency: "leather-roll", hardening: "kettle", quality: "slicker", yield: "skinning-knife" },
    };
  }
})();
