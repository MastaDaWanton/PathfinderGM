// The play table, part 49 (the enchanter: the essence card, the recipes, the Journal's
// section, the item card's magic section and Identify). Classic script in one IIFE, reached
// through `window.EnchantLedger` (contracts §13, lane U5).
//
// Enchanting UI plan §6.6 to §6.8, the forge ledger's counterpart (44-forge-ledger.js),
// with one renderer per thing and every surface drawing it:
//
//   EnchantLedger.card(essenceId, anchorEl, opts)   the essence card beside the bench's
//       shelf: swatch, name, where it is found or bought, each KNOWN trait with how it was
//       learned ("read, day 14", "attuned it, day 20"), one "unknown" line for each still
//       unknown, and Read (a tenth of a phial, ten minutes).
//   EnchantLedger.recipes(host, opts)   the recipes known, each with what it needs and what
//       it does; Load (when the bench passes `opts.load`) hands the recipe to the bench,
//       which sets up the vessel and seats. You still roll and play (herbalism §9.6).
//   EnchantLedger.journal(host)   the Journal's "Essences and recipes" section.
//   EnchantLedger.items() / itemSection(card, o) / identify(key, o)   the item card's magic
//       section on the Sheet and Equipment tabs (17, 18) and the graded Identify.
//
// ONLY WHAT THE PLAYER KNOWS. The server sends an essence's known traits and a COUNT of the
// unknown ones (play/enchant_views.py `_essence_row`), never their text, and an item's card
// is lane F's `knowledge.item_card`: the aura before identify, the intent after, the curse's
// words only once the curse check is passed. The page fills nothing in from data of its
// own. Two fields the essence route sends whatever is known are deliberately NOT drawn:
// `volatile` asks the Read confirm only once "volatile" is a known working trait (else the
// confirm would teach the trait before any read), and the family's phase is shown only as
// the known "binds best at noon" trait, plus the server's `phase_words` ("Noon, 42 minutes
// left") when a later version of the route sends them with the phase known. NetHack keeps
// the same two flags apart (an item's identity and its curse status are learned
// separately; nethackwiki.com/wiki/Identification, /wiki/BUC), which is the card's shape:
// "as the maker intended, not yet checked for a curse" until Identify beats the DC by 10.
//
// FLAWED, NEVER WHICH CURSE (owner round 4 point 2). A flawed binding's item says FLAWED in
// words and "which curse it carries is not known"; the curse's words appear only when the
// card carries them, which lane F's card does only once the curse is known. The page never
// sees a curse id (tests/test_enchant_api.py sweeps every response for one).
//
// EVERY NUMBER IS THE SERVER'S (UI plan §12). The DC, the roll, its total, the counts, the
// minutes and the uses left are printed from responses; nothing is summed or compared.
// Identify's verdict word is the server's `result` ("fail", "intent", "curse") said in its
// own `words`; the flourish is "success" for intent or curse and "failure" for fail, a
// mapping of the server's answer, never a total compared with a DC here.
//
// The day's phases are words (dawn, morning, noon, afternoon, dusk, night, midnight): no
// planet appears anywhere (owner round 4 point 10, "this is not earth").
//
// Styles are injected once (`#enchant-ledger-style`), theme tokens only; the herb card's
// classes in bench.css give the leather, rim and type. MOTION: nothing loops (no
// setInterval, no requestAnimationFrame; tests/test_enchant_ledger_ui.py greps for both).

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
  // The core's API when it is loaded; a copy of its lines otherwise, so the Journal and the
  // Equipment tab work on a page with no bench.
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
  function cap(s) { s = String(s == null ? "" : s); return s.charAt(0).toUpperCase() + s.slice(1); }
  function emit(name, detail) {
    try { document.dispatchEvent(new CustomEvent(name, { detail: detail })); } catch (err) { /* old engines */ }
  }

  // --- words ------------------------------------------------------------------------------
  var OBTAIN = { bought: "Bought at a market", harvested: "Harvested", gathered: "Gathered",
                 found: "Found", refined: "Refined at the circle", looted: "Taken as loot" };
  function listWords(xs) {
    xs = (xs || []).filter(Boolean).map(String);
    if (xs.length < 2) return xs.join("");
    return xs.slice(0, -1).join(", ") + " or " + xs[xs.length - 1];
  }
  // Where it is found or bought, from the server's fields when it sends them.
  function foundLine(c) {
    var how = String(c.obtain || "").toLowerCase();
    if (!how) return "";
    if (c.from_creature) return "Taken from " + String(c.from_creature) + ".";
    var head = OBTAIN[how] || cap(how);
    var biomes = (c.biomes || []).length && how !== "bought" ? " in " + listWords(c.biomes) + " country" : "";
    return head + biomes + ".";
  }
  function knows(c, key) {
    return (c.known || []).some(function (t) { return t.key === key; });
  }
  // Read asks first only for an essence KNOWN to be volatile (see the head comment).
  function needsConfirm(c) { return knows(c, "working:volatile"); }
  function readCost(c) {
    var bits = [c.read_cost || "a pinch"];
    if (c.read_minutes != null) bits.push(minutesWords(c.read_minutes));
    return bits.join(", ");
  }
  function swatch(color, big) {
    var ok = typeof color === "string" && /^(#[0-9a-f]{3,8}|rgba?\([\d\s.,%]+\)|hsla?\([\d\s.,%deg]+\))$/i.test(color.trim());
    return ok ? '<span class="el-swatch' + (big ? " is-big" : "") + '" style="background:' + esc(color.trim()) + '" aria-hidden="true"></span>' : "";
  }
  function icon(name, opts) {
    if (!window.BenchIcons || typeof BenchIcons.html !== "function") return "";
    try { return BenchIcons.html(name, opts); } catch (err) { return ""; }
  }

  // --- the essence card's body: one renderer for the card and the Journal -------------------
  function traitsHtml(c) {
    var known = (c.known || []).map(function (t) {
      return '<li><span>' + esc(cap(t.text || t.key)) + '</span>' +
        (t.how ? '<span class="hc-how">' + esc(t.how) + '</span>' : "") + '</li>';
    });
    var n = Math.max(0, Number(c.unknown) || 0);
    var unknown = [];
    for (var i = 0; i < n; i++) {
      unknown.push('<li class="is-unknown"><span class="hc-rule" aria-hidden="true"></span><span>unknown</span></li>');
    }
    if (!known.length && !unknown.length) return '<p class="hc-sub">There is nothing to learn about it.</p>';
    return '<ul class="hc-props">' + known.join("") + unknown.join("") + '</ul>';
  }
  // The phase of the day in words, only when the server sends it (with the phase known).
  function phaseHtml(c) {
    if (!c.phase_words) return "";
    return '<p class="el-phase">' + esc(c.phase_words) + '</p>';
  }
  function actionsHtml(c, o) {
    var none = !(Number(c.carried) > 0);
    return '<div class="hc-acts"><button type="button" class="v2-btn is-small" data-el="read"' +
      (none || o.busy ? " disabled" : "") + (none ? ' aria-describedby="el-read-why"' : "") +
      '>Read<span class="hc-cost">' + esc(readCost(c)) + '</span></button></div>' +
      (none ? '<p class="el-why" id="el-read-why">You carry none of it to take a pinch from.</p>' : "");
  }
  function cardHtml(c, o) {
    o = o || {};
    var carried = Number(c.carried) > 0 ? c.carried + " carried" : "";
    var sub = [c.tier, c.family, carried].filter(Boolean).join(", ");
    var where = foundLine(c);
    return '<i class="v2-rim" aria-hidden="true"></i><div class="hc-in">' +
      '<div class="hc-head"><span class="el-mark">' + icon("essence", { size: 48, tier: c.tier, label: c.name }) +
        swatch(c.color, true) + '</span>' +
        '<div><h3 id="el-card-name">' + esc(c.name) + '</h3>' +
        (sub ? '<p class="hc-sub">' + esc(sub) + '</p>' : "") +
        (where ? '<p class="hc-sub">' + esc(where) + '</p>' : "") + '</div>' +
        (o.pinned ? '<button type="button" class="hc-x" data-el="close" aria-label="Close the card">×</button>' : "") +
      '</div>' + phaseHtml(c) + traitsHtml(c) +
      (o.msg ? '<p class="hc-msg" role="status">' + esc(o.msg) + '</p>' : "") +
      (o.actions ? actionsHtml(c, o) : "") + '</div>';
  }

  // --- the recipes ------------------------------------------------------------------------
  function recipeHtml(r, o) {
    var needs = (r.needs || []).length ? '<p class="el-needs"><span class="hc-k">Needs</span> ' + esc((r.needs || []).join("; ")) + '</p>' : "";
    var book = (r.book || []).length ? '<ul class="el-book">' + (r.book || []).map(function (b) {
      return '<li>' + esc(cap(b)) + '</li>';
    }).join("") + '</ul>' : "";
    var sub = [r.tier, r.vessel ? "on a " + r.vessel : "",
               r.caster_level != null ? "caster level " + r.caster_level : "",
               r.motes != null ? String(r.motes) + (Number(r.motes) === 1 ? " mote" : " motes") : ""].filter(Boolean).join(", ");
    var load = o && o.load ? '<button type="button" class="v2-btn is-small" data-el-load="' + esc(r.id) + '"' +
      (r.can_make ? "" : ' disabled aria-describedby="el-rc-why-' + esc(r.id) + '"') + '>Load</button>' : "";
    return '<li class="el-recipe"><div class="el-rc-head"><b>' + esc(r.name) + '</b>' + load + '</div>' +
      (sub ? '<p class="hc-sub">' + esc(sub) + '</p>' : "") + needs + book +
      (r.can_make ? "" : '<p class="el-why" id="el-rc-why-' + esc(r.id) + '">Beyond your Enchanter level for now.</p>') + '</li>';
  }
  function recipesHtml(list, o) {
    if (list === null) return '<p class="why">Reading your recipes.</p>';
    if (!list.length) {
      return '<p class="why">No recipes yet. Identify or unbind a catalogue item, or study a manual, and its recipe is written here.</p>';
    }
    return '<ul class="plain el-recipes">' + list.map(function (r) { return recipeHtml(r, o); }).join("") + '</ul>';
  }

  // --- the item card's magic section (UI plan §6.6) ------------------------------------------
  // A card is lane F's `item_card` through lane E (rules/enchanter.item_card): {magic, aura,
  // schools, identified, flawed, curse, clings, lines?, caster_level?, as_intended?,
  // learned_by_use?, house?, uses?}. The bench's own fallback card says the curse is
  // unknown with `curse_question` and an empty `curse` instead of null.
  function curseKnown(card) {
    if (card.curse_question) return false;
    return card.curse != null && card.curse !== "";
  }
  function canIdentify(card) {
    return !!card && card.magic !== false && (!card.identified || !curseKnown(card));
  }
  function itemSection(card, o) {
    o = o || {};
    if (!card || card.magic === false) return "";
    var bits = [];
    var schools = (card.schools || []).length ? " (" + card.schools.join(", ") + ")" : "";
    bits.push('<p class="el-aura"><b>Magic</b>, ' + esc(card.aura || "faint") + " aura" + esc(schools) +
      (card.identified ? "" : '. <span class="el-q">Not identified.</span>') + '</p>');
    var known = curseKnown(card);
    if (card.flawed) {
      bits.push('<p class="el-flawed"><span class="el-flaw">FLAWED</span> ' + (known
        ? "Something went wrong in its binding."
        : "Something went wrong in its binding. Which curse it carries is not known.") + '</p>');
    }
    if (card.identified) {
      var lines = (card.lines || []).slice();
      if (lines.length) {
        bits.push('<ul class="el-lines">' + lines.map(function (l) { return '<li>' + esc(cap(l)) + '</li>'; }).join("") + '</ul>');
      }
      // Powers with their uses left today (the server's words, "2 of 3 left today"); a
      // power's bare name already in the lines above is not said twice.
      var uses = (card.uses || []).filter(function (u) { return lines.indexOf(u) < 0; });
      if (uses.length) bits.push('<p class="el-uses"><span class="hc-k">Powers</span> ' + esc(uses.join("; ")) + '</p>');
      (card.house || []).forEach(function (h) { bits.push('<p class="el-house">' + esc(cap(h)) + '</p>'); });
      if (card.caster_level != null) bits.push('<p class="el-cl">Caster level ' + esc(card.caster_level) + '.</p>');
    } else if ((card.learned_by_use || []).length) {
      bits.push('<p class="el-used"><span class="hc-k">Found by use</span> ' + esc(card.learned_by_use.join(", ")) + '</p>');
    }
    if (known) {
      bits.push(card.curse === "none"
        ? '<p class="el-curse">No curse: it is what it was made to be.</p>'
        : '<p class="el-curse is-bad"><span class="hc-k">Curse</span> ' + esc(cap(card.curse)) +
          (card.clings ? " It will not be put down." : "") + '</p>');
    } else if (card.identified) {
      bits.push('<p class="el-q">As the maker intended: not yet checked for a curse.</p>');
    }
    if (o.msg) bits.push('<p class="el-msg" role="status">' + esc(o.msg) + '</p>');
    if (o.button && canIdentify(card) && o.key) {
      bits.push('<button type="button" class="v2-btn is-small" data-el-identify="' + esc(o.key) + '"' +
        (o.name ? ' data-el-name="' + esc(o.name) + '"' : "") + (o.busy ? " disabled" : "") +
        ' aria-label="Identify ' + esc(o.name || "it") + '">Identify</button>');
    }
    return '<div class="el-item" data-el-item="' + esc(o.key || "") + '">' + bits.join("") + '</div>';
  }

  // Identify's answer in one sentence: the roll and the DC as the server sent them, then
  // its own words. A second try the same day is the first answer again (CRB Spellcraft:
  // "additional attempts reveal the same results"), so it says so rather than printing the
  // new die as if it counted.
  function identifyLine(r, name) {
    var roll = r.roll || {};
    var dc = r.dc != null ? r.dc : roll.dc;
    var who = name || r.name || "it";
    var curse = r.result === "curse" && r.curse ? " " + cap(r.curse) : "";
    if (r.repeat) {
      return "You studied the " + who + " today already, and the answer stands (DC " + dc + "): " +
        (r.words || "") + curse +
        // A failed answer's words already say "try again tomorrow"; not twice.
        (r.again_on_day != null && r.result !== "fail" ? " You can study it again on day " + r.again_on_day + "." : "");
    }
    return "Identify the " + who + ": d20 " + roll.face + " " + sign(roll.bonus) + " = " + roll.total +
      " against DC " + dc + ". " + (r.words || "") + curse;
  }

  // --- styles, once -------------------------------------------------------------------------
  function style() {
    if (document.getElementById("enchant-ledger-style")) return;
    var s = document.createElement("style");
    s.id = "enchant-ledger-style";
    s.textContent = [
      ".el-card, .el-confirm, .el-journal, .el-item, .el-recipes { --bench-ink: var(--ink); --bench-quiet: var(--dim);",
      "  --bench-accent: var(--gold); --bench-warn: var(--alarm); --bench-radius: 3px; }",
      ".el-card { position: fixed; width: 340px; max-height: calc(100vh - 16px); z-index: 7; color: var(--ink);",
      "  font: 16px/1.5 var(--body); border-radius: 3px; box-shadow: var(--sh-3), var(--ring-cast); }",
      ".el-card.is-loose { z-index: 30; }",
      ".el-card[hidden] { display: none; }",
      ".el-card .hc-x { position: absolute; right: 8px; top: 8px; width: 30px; height: 30px; display: grid; place-items: center;",
      "  background: none; border: 0; color: var(--dim); font-size: 20px; cursor: pointer; }",
      ".el-card .hc-x:hover { color: var(--ink); }",
      ".el-card .hc-acts .v2-btn { flex-direction: column; align-items: flex-start; gap: 3px; min-height: 40px; height: auto; display: inline-flex; }",
      ".el-mark { position: relative; display: inline-flex; flex: none; }",
      ".el-mark:empty { display: none; }",
      ".el-swatch { display: inline-block; width: 8px; height: 8px; border-radius: 50%; vertical-align: middle;",
      "  box-shadow: 0 0 0 1px var(--edge), 1px 1px 2px rgba(0, 0, 0, .6); }",
      ".el-mark .el-swatch { position: absolute; right: -2px; bottom: -2px; }",
      ".el-swatch.is-big { width: 12px; height: 12px; }",
      ".el-phase { margin: 0 0 8px; color: var(--ink); font-size: 15px; }",
      ".el-why { margin: 6px 0 0; color: var(--dim); font-size: 13px; }",
      ".el-confirm.is-loose { z-index: 31; }",
      ".el-confirm .bench-danger { border-color: var(--alarm); }",
      ".el-alarm { color: var(--alarm); font: 600 19px/1.35 var(--body); }",
      ".el-journal .el-rows { grid-template-columns: repeat(2, minmax(0, 1fr)); }",
      "@media (max-width: 900px) { .el-journal .el-rows { grid-template-columns: minmax(0, 1fr); } }",
      ".el-journal .el-tools { margin: 0 0 8px; }",
      ".el-journal h3.el-sub { margin: 18px 0 8px; color: var(--gold); font: 400 17px/1.2 var(--display); letter-spacing: .04em; font-variant: small-caps; }",
      ".el-row { all: unset; cursor: pointer; display: inline-flex; gap: 10px; align-items: center; }",
      ".el-row:focus-visible { outline: 2px solid var(--gold); outline-offset: 3px; }",
      ".el-jr-body .hc-props { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }",
      ".el-jr-body .hc-props li { display: grid; gap: 1px; }",
      ".el-jr-body .hc-how, .el-jr-body .is-unknown { color: var(--dim); font-size: 13px; }",
      ".el-jr-body .is-unknown { grid-template-columns: 22px 1fr; align-items: center; gap: 8px; }",
      ".el-jr-body .hc-rule { display: block; height: 1px; background: var(--dim); }",
      ".el-recipes { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }",
      ".el-rc-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }",
      ".el-rc-head b { font-weight: 400; color: var(--ink); }",
      ".el-needs, .el-uses, .el-used { margin: 4px 0 0; font-size: 14px; color: var(--ink); }",
      ".el-recipes .hc-k, .el-item .hc-k { color: var(--dim); margin-right: 4px; }",
      ".el-book { margin: 4px 0 0; padding-left: 18px; font-size: 14px; color: var(--ink); }",
      ".el-item { margin: 6px 0 2px; padding: 6px 0 0 10px; border-left: 2px solid var(--gold); font-size: 14px; line-height: 1.4; color: var(--ink); }",
      ".el-item p { margin: 2px 0; }",
      ".el-item .el-aura b { font-weight: 600; color: var(--gold); }",
      ".el-item .el-q, .el-item .el-cl, .el-item .el-house { color: var(--dim); }",
      ".el-item .el-lines { margin: 2px 0; padding-left: 18px; }",
      ".el-item .el-flaw { color: var(--alarm); font: 600 13px/1 var(--display); letter-spacing: .12em; margin-right: 4px; }",
      ".el-item .el-curse.is-bad { border-left: 3px solid var(--alarm); padding-left: 8px; }",
      ".el-item .el-msg { margin-top: 6px; }",
      ".el-item .v2-btn { margin-top: 6px; }",
      ".el-magic-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }",
      ".el-magic-list > li > b { font-weight: 400; color: var(--ink); }",
    ].join("\n");
    document.head.appendChild(s);
  }

  // --- the essence card beside the shelf ----------------------------------------------------
  var el = null, cache = {}, open = null, closeT = 0, msg = "", busy = false, looseEsc = null;

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
      el.className = "bench-card el-card v2-framed v2-card-leather";
      el.id = "enchant-ledger-card";
      el.setAttribute("role", "dialog");
      el.setAttribute("aria-labelledby", "el-card-name");
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
    var shelfEl = (o && o.beside) || (anchor && anchor.closest && anchor.closest("[data-enchant-shelf]")) ||
                  document.getElementById("enchant-shelf");
    var sr = shelfEl && document.contains(shelfEl) ? shelfEl.getBoundingClientRect() : null;
    var ar = anchor && document.contains(anchor) ? anchor.getBoundingClientRect() : sr;
    var w = Math.min(340, innerWidth - 24);
    el.style.width = w + "px";
    var h = el.offsetHeight || 260;
    var left, top;
    if (sr && sr.right + 14 + w <= innerWidth - 8) {
      left = sr.right + 14;
      top = ar ? ar.top - 12 : sr.top;
    } else {
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
        '<div><h3 id="el-card-name">' + esc(open.name || "") + '</h3></div></div><p class="hc-sub">Reading what you know.</p></div>';
      return;
    }
    if (c.error) {
      el.innerHTML = '<i class="v2-rim" aria-hidden="true"></i><div class="hc-in"><h3 id="el-card-name">Couldn\'t load this essence.</h3>' +
        '<p class="hc-sub">' + esc(c.error) + '</p><button type="button" class="v2-btn is-small" data-el="retry">Retry</button></div>';
      return;
    }
    el.innerHTML = cardHtml(c, { actions: true, pinned: open.pinned, msg: msg, busy: busy });
  }
  function fetchCard(id) {
    return api("/api/enchant/essence/" + encodeURIComponent(id)).then(function (c) {
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
  function focusIn() {
    if (!open || !open.wantFocus || !el) return;
    var first = el.querySelector("[data-el]:not([data-el='close']):not([disabled])") || el.querySelector("[data-el]");
    if (first) { open.wantFocus = false; first.focus(); }
  }
  function pushEsc() {
    var h = benchOf(open && open.anchor);
    if (h) { h.pushEsc(escClose); return; }
    if (looseEsc) return;
    // Capture phase, stopped there: one Esc closes the card, not the Journal under it too
    // (the forge ledger's live finding, 2026-10-04).
    looseEsc = function (e) {
      if (e.key !== "Escape" || !open || !open.pinned || document.querySelector(".el-confirm")) return;
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
    if (same && open.pinned && o.peek) return;
    var wasPinned = !!(open && open.pinned);
    var pinned = !o.peek || (same && open.pinned);
    if (open && !same && wasPinned) dropEsc();
    open = { id: id, anchor: anchor, pinned: pinned, opts: o, name: o.name || "", wantFocus: false };
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

  // --- Read --------------------------------------------------------------------------------
  function confirmHtml(c) {
    return '<div class="bench-scrim"></div><div class="bench-dialog v2-framed v2-card-leather">' +
      '<i class="v2-rim" aria-hidden="true"></i>' +
      '<h3 id="el-confirm-t">Read ' + esc(c.name) + '</h3>' +
      '<div id="el-confirm-b"><p class="el-alarm">This essence bites the one who reads it. Read it anyway?</p>' +
      '<p>' + esc("It takes " + readCost(c) + ".") + '</p></div>' +
      '<div class="bench-dialog-acts"><button type="button" class="v2-btn is-quiet" data-no>Keep it</button>' +
      '<button type="button" class="v2-btn is-quiet bench-danger" data-yes>Read it</button></div></div>';
  }
  function confirmVolatile(c) {
    return new Promise(function (done) {
      var host = hostFor(open && open.anchor, open && open.opts);
      var h = benchOf(open && open.anchor);
      var back = document.activeElement;
      var wrap = document.createElement("div");
      wrap.className = "bench-modal bench-confirm el-confirm" + (host === document.body ? " is-loose" : "");
      wrap.setAttribute("role", "alertdialog");
      wrap.setAttribute("aria-modal", "true");
      wrap.setAttribute("aria-labelledby", "el-confirm-t");
      wrap.setAttribute("aria-describedby", "el-confirm-b");
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
  function readLine(r) {
    var roll = r.roll || {};
    var head = "You read a pinch of " + (r.name || "it") + (roll.total != null
      ? " (d20 " + roll.face + " " + sign(roll.bonus) + " = " + roll.total +
        (roll.dc != null ? " against DC " + roll.dc : "") + ")." : ".");
    var found = (r.revealed || []).map(function (t) { return t.text || t.key; });
    var said = found.length ? " Learned: " + found.join("; ") + "." : " Nothing new.";
    var hurt = r.danger_text ? " " + cap(r.danger_text) + "." : "";
    return head + said + hurt + (r.minutes ? " " + minutesWords(r.minutes) + " passed." : "");
  }
  // The table's d20 for the player's own throw, as the forge's assay; the server rolls when
  // there is no mat.
  function throwFor(title, why, ask) {
    var dice = window.Dice3D;
    var shown = { title: title, why: why, sides: 20, lo: 1, hi: 20, die: "1d20", terms: [] };
    var asking = dice && typeof dice.ask === "function" ? dice.ask(Object.assign({ hold: true }, shown)) : Promise.resolve(null);
    var C = core();
    if (dice && C && C.focusMat) C.focusMat();
    return asking.then(function (face) {
      return ask(face == null ? null : face);
    }).then(function (r) {
      return { r: r, dice: dice, shown: shown };
    }, function (err) {
      if (dice && dice.close) { try { dice.close(); } catch (e2) { /* */ } }
      throw err;
    });
  }
  function landIt(t, terms, verdict) {
    var dice = t.dice, roll = (t.r && t.r.roll) || {};
    if (!dice || typeof dice.land !== "function" || roll.face == null) return Promise.resolve(null);
    var closing = dice.land(Object.assign({}, t.shown, { result: roll.face, terms: terms }));
    var rest = typeof dice.settled === "function" ? dice.settled() : null;
    if (verdict && typeof window.showVerdict === "function") {
      window.showVerdict({ verdict: verdict, natural: null }, rest);
    }
    return closing;
  }
  function read(c) {
    var id = c.id;
    busy = true;
    draw();
    var t = null;
    return throwFor("Read " + c.name, "Enchanter", function (face) {
      return api("/api/enchant/read", { essence: id, face: face });
    }).then(function (got) {
      t = got;
      sound("enchant.read");
      var roll = t.r.roll || {};
      var terms = [];
      if (roll.bonus != null) terms.push({ label: "your bonus", value: sign(roll.bonus) });
      if (roll.dc != null) terms.push({ label: "beat", value: roll.dc });
      return landIt(t, terms, typeof roll.success === "boolean" ? (roll.success ? "success" : "failure") : null);
    }).then(function () {
      var r = t.r;
      delete cache[id];
      msg = readLine(r);
      busy = false;
      var detail = { essence: id, response: r, said: msg };
      emit("enchant:learned", detail);
      if (open && open.opts && typeof open.opts.after === "function") {
        try { open.opts.after(detail); } catch (err) { /* the card still redraws */ }
      }
      if (open && open.id === id) { open.wantFocus = true; draw(); return fetchCard(id); }
    }).catch(function (err) {
      busy = false;
      msg = err && err.message ? err.message : String(err);
      if (open && open.id === id) { draw(); open.wantFocus = true; focusIn(); }
    });
  }
  function onClick(e) {
    var b = e.target.closest("[data-el]");
    if (!b || !open) return;
    var id = open.id, c = cache[id];
    var k = b.dataset.el;
    if (k === "close") { hide(true); return; }
    if (k === "retry") { fetchCard(id); return; }
    if (!c || busy) return;
    if (!open.pinned) { open.pinned = true; el.classList.add("is-pinned"); pushEsc(); }
    if (k === "read") {
      if (!needsConfirm(c)) { read(c); return; }
      confirmVolatile(c).then(function (yes) { if (yes && open && open.id === id) read(c); });
    }
  }
  document.addEventListener("pointerdown", function (e) {
    if (!open || !open.pinned || !el || el.contains(e.target)) return;
    if (e.target.closest && (e.target.closest(".el-confirm") || e.target.closest("#d3d-mat") ||
        (open.anchor && open.anchor.contains && open.anchor.contains(e.target)))) return;
    hide(false);
  });
  addEventListener("resize", function () { if (open) place(open.anchor, open.opts); });

  // --- Identify ---------------------------------------------------------------------------
  // One roll on the mat, then the server's graded answer. Returns the response with `said`,
  // the sentence the caller writes where it keeps one.
  function identify(key, o) {
    o = o || {};
    var name = o.name || "item";
    var t = null;
    return throwFor("Identify " + name, "Spellcraft, or your Enchanter check", function (face) {
      return api("/api/enchant/identify", { item: key, face: face });
    }).then(function (got) {
      t = got;
      sound("enchant.identify");
      var r = t.r, roll = r.roll || {};
      var terms = [];
      if (roll.bonus != null) terms.push({ label: "your bonus", value: sign(roll.bonus) });
      if (r.dc != null) terms.push({ label: "beat", value: r.dc });
      var verdict = r.repeat ? null : r.result === "fail" ? "failure"
        : (r.result === "intent" || r.result === "curse") ? "success" : null;
      return landIt(t, terms, verdict);
    }).then(function () {
      var r = t.r;
      r.said = identifyLine(r, o.name || r.name);
      if (r.card) itemCache[key] = { key: key, name: r.name || name, card: r.card };
      emit("enchant:identified", { item: key, response: r, said: r.said });
      return r;
    });
  }

  // What the pack holds that carries a layer, keyed by shelf key: the bench state's shelf,
  // whose every vessel with a layer carries its `card` (rules/enchanter.Vessel.as_item). A
  // full state read, so it is not asked while the bench itself is open (the bench's own
  // state is fresher, and a fresh GET lets a pending roll go, play/enchant_views.py).
  var itemCache = {};
  function items() {
    var C = core();
    if (C && C.current && C.current.open) return Promise.resolve(itemCache);
    return api("/api/enchant/state").then(function (s) {
      var shelf = (s && s.shelf) || {};
      var fresh = {};
      ["vessels", "intermediates", "cant_use"].forEach(function (g) {
        (shelf[g] || []).forEach(function (v) {
          if (v && v.card && v.card.magic !== false) fresh[v.key] = { key: v.key, name: v.name, card: v.card };
        });
      });
      itemCache = fresh;
      return itemCache;
    }).catch(function () { return itemCache; });
  }
  // The entry for a row of the Equipment tab: its id is the shelf key for a pack entry
  // ("stock:<key>"); a name match covers an entry renamed after it was keyed.
  function itemFor(map, id, name) {
    map = map || itemCache;
    if (id && map[id]) return map[id];
    var low = String(name || "").trim().toLowerCase();
    if (!low) return null;
    for (var k in map) {
      if (Object.prototype.hasOwnProperty.call(map, k) && String(map[k].name || "").trim().toLowerCase() === low) return map[k];
    }
    return null;
  }

  // --- the Journal's section ----------------------------------------------------------------
  function rowsHtml(st) {
    if (st.error) {
      return '<p class="why">' + esc(st.error) + '</p>' +
        '<button type="button" class="v2-btn is-small" data-el-retry>Retry</button>';
    }
    if (st.ledger === null) return '<p class="why">Reading the ledger.</p>';
    var rows = st.ledger.slice();
    if (!rows.length) return '<p class="why">No essences yet. Buy, find or harvest one and it appears here.</p>';
    if (st.unknownFirst) {
      rows.sort(function (a, b) { return ((b.unknown || 0) - (a.unknown || 0)) || String(a.name).localeCompare(String(b.name)); });
    }
    return '<ul class="plain matters twocol el-rows">' + rows.map(function (e) {
      var isOpen = st.open === e.id;
      var bodyId = "el-jr-card-" + esc(e.id);
      // The count is the server's `unknown`; the known lines are drawn, never counted.
      var line = [e.tier, e.family, e.unknown ? e.unknown + " still unknown" : "all known",
                  Number(e.carried) > 0 ? e.carried + " carried" : ""].filter(Boolean).join(" · ");
      return '<li class="matter" role="listitem"><h3><button type="button" class="el-row" data-el-ess="' + esc(e.id) + '"' +
        ' aria-expanded="' + isOpen + '" aria-controls="' + bodyId + '">' + swatch(e.color) + esc(e.name) + '</button></h3>' +
        '<p class="why">' + esc(line) + '</p>' +
        '<div id="' + bodyId + '" class="el-jr-body"' + (isOpen ? "" : " hidden") + '>' +
          (isOpen ? traitsHtml(e) : "") + '</div></li>';
    }).join("") + '</ul>';
  }
  function journal(host) {
    if (!host) return null;
    style();
    host.classList.add("el-journal");
    var st = host._enchantLedger;
    if (!st) {
      st = host._enchantLedger = { ledger: null, recipes: null, error: "", open: "", unknownFirst: false };
      host.addEventListener("click", function (e) {
        if (e.target.closest("[data-el-retry]")) { st.read(); return; }
        var sort = e.target.closest("[data-el-sort]");
        if (sort) {
          st.unknownFirst = !st.unknownFirst;
          sort.setAttribute("aria-pressed", String(st.unknownFirst));
          st.draw();
          return;
        }
        var row = e.target.closest("[data-el-ess]");
        if (!row) return;
        var id = row.dataset.elEss;
        st.open = st.open === id ? "" : id;
        st.draw();
        var again = host.querySelector('[data-el-ess="' + (window.CSS && CSS.escape ? CSS.escape(id) : id) + '"]');
        if (again) again.focus();
      });
    }
    st.ledger = null;
    st.recipes = null;
    st.error = "";
    host.innerHTML = '<div class="el-tools"><button type="button" class="v2-btn is-small" data-el-sort aria-pressed="' +
      st.unknownFirst + '">Unknowns first</button></div>' +
      '<div class="el-list" role="list" aria-label="Essences you have met"></div>' +
      '<h3 class="el-sub">Recipes</h3><div class="el-rc"></div>';
    st.draw = function () {
      var box = host.querySelector(".el-list");
      if (box) box.innerHTML = rowsHtml(st);
      var rc = host.querySelector(".el-rc");
      if (rc) rc.innerHTML = st.error ? "" : recipesHtml(st.recipes, {});
    };
    // The ledger route carries the recipes too: one read for the whole section.
    st.read = function () {
      st.error = "";
      st.ledger = null;
      st.recipes = null;
      st.draw();
      return api("/api/enchant/ledger").then(function (d) {
        st.ledger = (d && d.ledger) || [];
        st.recipes = (d && d.recipes) || [];
      }).catch(function (err) {
        st.error = "Couldn't read the ledger. " + (err.message || "");
      }).then(st.draw);
    };
    st.read();
    return { refresh: st.read };
  }

  // --- the bench's recipe list --------------------------------------------------------------
  function recipes(host, o) {
    if (!host) return null;
    o = o || {};
    style();
    var list = null, err = "";
    var drawList = function () {
      host.innerHTML = err ? '<p class="why">' + esc(err) + '</p><button type="button" class="v2-btn is-small" data-el-rc-retry>Retry</button>'
        : recipesHtml(list, o);
    };
    var read = function () {
      list = null; err = ""; drawList();
      return api("/api/enchant/recipes").then(function (d) { list = (d && d.recipes) || []; })
        .catch(function (e) { err = "Couldn't read your recipes. " + (e.message || ""); }).then(drawList);
    };
    if (!host._enchantRecipes) {
      host._enchantRecipes = true;
      host.addEventListener("click", function (e) {
        if (e.target.closest("[data-el-rc-retry]")) { read(); return; }
        var load = e.target.closest("[data-el-load]");
        if (!load || load.disabled) return;
        var r = (list || []).filter(function (x) { return x.id === load.dataset.elLoad; })[0];
        if (!r) return;
        emit("enchant:recipe", { recipe: r });
        if (typeof o.load === "function") o.load(r);
      });
    }
    read();
    return { refresh: read };
  }

  window.EnchantLedger = {
    card: function (essenceId, anchorEl, opts) { show(essenceId, anchorEl, opts); },
    peek: function (essenceId, anchorEl, opts) { show(essenceId, anchorEl, Object.assign({}, opts, { peek: true })); },
    unpeek: function () {
      if (!open || open.pinned) return;
      clearTimeout(closeT);
      closeT = setTimeout(function () { if (open && !open.pinned) hide(false); }, 220);
    },
    close: function () { hide(false); },
    isOpen: function () { return !!open; },
    // After a step at the circle reveals traits (Attune shows polarity and phase; Bind
    // what it grants), the card must be read again.
    forget: function (essenceId) { if (essenceId) delete cache[essenceId]; else cache = {}; },
    recipes: recipes,
    journal: journal,
    items: items,
    itemFor: itemFor,
    itemSection: function (card, o) { style(); return itemSection(card, o); },
    canIdentify: canIdentify,
    identify: identify,
    // The renderers, for tests and for the bench's shell; pure: data in, markup out.
    render: { card: cardHtml, traits: traitsHtml, rows: rowsHtml, recipes: recipesHtml, item: itemSection,
              identifyLine: identifyLine, readLine: readLine, found: foundLine, confirm: confirmHtml,
              needsConfirm: needsConfirm },
  };
})();
