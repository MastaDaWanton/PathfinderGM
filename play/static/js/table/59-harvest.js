// The play table, part 59 (the harvest sheet: "Harvest the carcass", every craft at once).
// Classic script; everything lives inside one IIFE and is reached through
// `window.HarvestSheet`, so no name here can shadow one of 01-58's (test_s6_panel_shell's rule
// that no top-level function is declared twice across the table's files).
//
// WHAT IT IS (leather UI plan §6.9, contracts §11 lane U2). Taking parts off a dead creature is
// a scene action, not a bench method (revamp plan §5): one sheet over the table lists every
// part the body carries for every craft the character has, grouped by craft, each with its
// skill, DC and terms, the face needed, its yield and time, and, before anything is rolled, in
// words: the dangers this body holds (exposed only on a miss by 5 or more, the owner's answer),
// the curing salt a hide wants and whether the pack covers it, and when taking it is a deed (a
// good outsider or a good dragon): then Take asks first, "Take it" or "Leave it" (the deeds
// plan's UI note, "the confirm shows before the roll"). Humanoids and native outsiders never
// appear, because the server never offers them, so there is nothing here to refuse in words.
// The API is lane C's play/harvest_views.py; its docstrings carry the shapes.
//
// WHERE IT OPENS. The "In the scene" panel's Harvest button beside a carcass (07-panels.js,
// which looks this file up when it draws) and the craft-action hub's "Harvest the carcass",
// which this file adds to the hub itself when the hub is drawn (the four carcass excursions
// left the hub with lane C; UI plan §13: "the hub shows Harvest the carcass in their place").
//
// THE ROLL. The table's own d20 (Dice3D), thrown the way every bench throws it (29's rollD20
// path, unrolled here because a dangerous body throws more than one die): the first part taken
// off a dangerous body faces each danger first, so the player throws one die per danger and
// then the part's own, every face is sent (`face`, `danger_faces`), and each die then lands on
// the face the SERVER names, with its verdict. A skill check has no natural 20 or 1 (CRB
// p.180), so none is passed to the verdict. A hide is then worked off with the harvest game
// (js/leather-games/harvest.js), which reports its DEFECT AREA; the server turns that into the
// grade (`api/harvest/finish`). Without the game in the build the hide keeps the grade it came
// off at, said in words.
//
// THE PAGE NEVER COMPUTES A NUMBER. The DC, the terms, the face needed, units, minutes, salt,
// the grade and the clock are the server's; this file lays them out. Nothing about a hide's
// inherited properties reaches the page here: a creature-derived property is a secret until
// Grade (UI plan §6.7), and the take's answer carries none.
//
// MOTION. Nothing loops: no setInterval and no requestAnimationFrame (tests/test_harvest_ui.py
// greps for both). The layer fades in over 200ms on the core, and not at all in reduced motion.
(function () {
  "use strict";

  var C = window.BenchCore;
  if (!C) return;
  var esc = C.esc;
  var $id = function (id) { return document.getElementById(id); };

  // --- the look: tokens only (theme-v2.css), the bench's semantic layer over them -------------
  // A sheet over the table rather than a full bench layer (UI plan §6.9), on the bench's z 35
  // so Esc, the focus trap and the one-bench-at-a-time rule are the core's. Injected here, as
  // 44-forge-ledger.js and 54-alchemy-books.js inject theirs, so the sheet needs no stylesheet
  // tag of its own in table.html.
  var CSS = [
    "#harvest.bench{display:grid;grid-template-rows:none;place-items:center;padding:16px;",
    "background:color-mix(in srgb,var(--bg) 72%,transparent);overflow:hidden}",
    "#harvest .hv-sheet{position:relative;display:flex;flex-direction:column;width:min(760px,100%);",
    "max-height:calc(100vh - 32px);max-height:calc(100dvh - 32px);border-radius:var(--bench-radius);box-shadow:var(--sh-3),var(--ring-cast);padding:18px 20px 0}",
    "#harvest .hv-sheet>:not(.v2-rim){position:relative;z-index:1}",
    "#harvest .hv-head{display:flex;align-items:flex-start;gap:12px;flex-wrap:wrap}",
    "#harvest .hv-title{flex:1;min-width:0;margin:0;color:var(--bench-accent);font:400 22px/1.2 var(--display);",
    "letter-spacing:.05em;font-variant:small-caps;overflow-wrap:anywhere}",
    "#harvest .hv-body{flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;margin:10px -6px 0;padding:0 6px 14px}",
    "#harvest .hv-sub,#harvest .hv-note{margin:0 0 6px;color:var(--bench-quiet);font-size:15px;line-height:1.45}",
    "#harvest .hv-sub b{color:var(--bench-ink);font-weight:400}",
    "#harvest .hv-group{margin:16px 0 0}",
    "#harvest .hv-group>h3{margin:0 0 6px;color:var(--bench-accent);font:400 16px/1.2 var(--display);",
    "letter-spacing:.06em;font-variant:small-caps;border-bottom:1px solid var(--edge);padding-bottom:4px}",
    "#harvest .hv-rows{list-style:none;margin:0;padding:0;display:grid;gap:2px}",
    "#harvest .hv-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 14px;align-items:center;",
    "padding:8px 0;border-bottom:1px solid var(--edge)}",
    "#harvest .hv-row:last-child{border-bottom:0}",
    "#harvest .hv-name{color:var(--bench-ink);font-size:16px;line-height:1.3}",
    "#harvest .hv-name small{color:var(--bench-quiet);font-size:13px;margin-left:6px}",
    "#harvest .hv-line{grid-column:1;margin:0;color:var(--bench-quiet);font-size:14px;line-height:1.4}",
    "#harvest .hv-line.is-need{color:var(--bench-ink)}",
    "#harvest .hv-line.is-deed{color:var(--bench-ink);border-left:3px solid var(--bench-warn);padding-left:8px}",
    "#harvest .hv-line.is-short{color:var(--bench-ink);border-left:2px solid var(--bench-warn);padding-left:6px}",
    "#harvest .hv-take{grid-column:2;grid-row:1/span 9;align-self:center;min-width:88px}",
    "#harvest .hv-row.is-taken .hv-name{color:var(--bench-quiet)}",
    "#harvest .hv-danger{margin:12px 0 0;padding:8px 12px;border-left:3px solid var(--bench-warn);",
    "background:color-mix(in srgb,var(--sunk) 70%,transparent)}",
    "#harvest .hv-danger h3{margin:0 0 4px;color:var(--bench-ink);font:400 15px/1.2 var(--display);letter-spacing:.06em;font-variant:small-caps}",
    "#harvest .hv-danger ul{margin:0;padding:0 0 0 18px}",
    "#harvest .hv-danger li{color:var(--bench-ink);font-size:14px;line-height:1.45}",
    "#harvest .hv-danger p{margin:4px 0 0;color:var(--bench-quiet);font-size:14px;line-height:1.4}",
    "#harvest .hv-result{margin:12px 0 0;padding:10px 12px;border:1px solid var(--edge);border-radius:var(--bench-radius);",
    "background:color-mix(in srgb,var(--sunk) 70%,transparent)}",
    "#harvest .hv-result h3{margin:0 0 4px;font:400 17px/1.2 var(--display);letter-spacing:.05em;font-variant:small-caps;color:var(--bench-accent)}",
    "#harvest .hv-result.is-failed h3{color:var(--bench-ink)}",
    "#harvest .hv-result p{margin:2px 0;font-size:14px;line-height:1.45;color:var(--bench-ink)}",
    "#harvest .hv-result p.is-quiet{color:var(--bench-quiet)}",
    "#harvest .hv-result p.is-warn{border-left:2px solid var(--bench-warn);padding-left:6px}",
    "#harvest .hv-bodies{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:6px}",
    "#harvest .hv-bodies button{width:100%;text-align:left;padding:10px 12px;border:1px solid var(--edge);",
    "border-radius:var(--bench-radius);color:var(--bench-ink);font-size:16px}",
    "#harvest .hv-bodies button:hover{border-color:var(--bench-accent-deep)}",
    "#harvest .hv-bodies small{display:block;color:var(--bench-quiet);font-size:13px}",
    "#harvest .hv-back{margin:0 0 8px;color:var(--bench-quiet);font-size:14px;text-decoration:underline}",
    "#harvest .hv-game{margin:10px 0 0}",
    "#harvest .hv-game[hidden]{display:none}",
    "#harvest .hv-foot{margin:0 -20px;border-top:1px solid var(--edge)}",
    "#harvest .hv-foot .bench-foot-in{display:flex;align-items:center;gap:12px;flex-wrap:wrap;min-height:44px;padding:4px 20px}",
    "#harvest .hv-foot .bf-track:empty{display:none}",
    "#harvest .hv-err{margin:8px 0 0;color:var(--bench-ink);border-left:3px solid var(--bench-warn);padding-left:8px;font-size:14px}",
    "#harvest .hv-err:empty{display:none}",
    // The scene panel's Harvest button (07-panels.js) on its row, and the breathing body's words.
    ".who.has-harvest{flex-wrap:wrap;align-items:center;gap:4px 10px}",
    ".who .who-harvest{margin-left:auto}",
    ".who .who-breathing{flex-basis:100%;font-style:italic}",
    "@media (max-width:560px){#harvest .hv-sheet{padding:14px 14px 0}#harvest .hv-foot{margin:0 -14px}",
    "#harvest .hv-foot .bench-foot-in{padding:4px 14px}",
    "#harvest .hv-row{grid-template-columns:minmax(0,1fr)}#harvest .hv-take{grid-column:1;grid-row:auto;justify-self:start}}",
  ].join("\n");

  function addStyle() {
    if ($id("harvest-style")) return;
    var st = document.createElement("style");
    st.id = "harvest-style";
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  // --- the layer: built once, in the page, so closing is instant -------------------------------
  function build() {
    var layer = $id("harvest");
    if (layer) return layer;
    addStyle();
    layer = document.createElement("div");
    layer.id = "harvest";
    layer.className = "bench harvest";
    layer.setAttribute("role", "dialog");
    layer.setAttribute("aria-modal", "true");
    layer.setAttribute("aria-labelledby", "harvest-title");
    layer.hidden = true;
    layer.innerHTML =
      '<section class="hv-sheet v2-framed v2-card-leather" aria-describedby="harvest-sub">' +
        '<i class="v2-rim" aria-hidden="true"></i>' +
        '<header class="hv-head">' +
          '<h2 class="hv-title" id="harvest-title">Harvest the carcass</h2>' +
          '<button type="button" class="v2-btn is-quiet bench-close" id="harvest-close">Close</button>' +
        '</header>' +
        '<div class="hv-body" id="harvest-body"></div>' +
        // Where the harvest game rises (contracts §11.1), inside the sheet and outside its
        // scrolled body, so the strip is always on screen while the list above it shrinks.
        '<div class="bench-gamebay hv-game" id="harvest-game" hidden></div>' +
        '<p class="hv-err" id="harvest-err" role="alert"></p>' +
        '<footer class="hv-foot" id="harvest-foot"><div class="bench-foot-in" id="harvest-foot-in"></div></footer>' +
      '</section>' +
      '<div class="bench-pops" id="harvest-pops"></div>' +
      '<div class="vh" id="harvest-say" role="status" aria-live="polite"></div>';
    document.body.appendChild(layer);
    return layer;
  }

  // --- state -------------------------------------------------------------------------------------
  var H = window.HarvestSheet = {
    list: null,         // the last GET api/harvest
    ref: null,          // the carcass on the sheet, or null for the list of carcasses
    sheet: null,        // the last GET api/harvest/<ref> (or the sheet a take or finish sent)
    result: null,       // what the last take said, kept on the sheet until the next
    busy: false, live: null, error: "",
  };

  var layer = build();
  var core = C.mount({
    layer: "harvest", close: "harvest-close", say: "harvest-say", pops: "harvest-pops",
    foot: "harvest-foot", footIn: "harvest-foot-in", home: "craftaction",
    clockId: "harvest-clock", bodyClass: "harvest-on",
    openWith: "[data-harvest-open]",
    openFrom: function (btn) {
      // The hub folds itself first (as the herb bench's opener does); focus comes back to the
      // hub's own button, which stays on the page.
      var panel = $id("craftpanel");
      if (panel && panel.contains(btn)) { panel.hidden = true; return $id("craftaction") || btn; }
      H.ref = btn.getAttribute("data-harvest-open") || null;
      return btn;
    },
    first: ".hv-take:not([disabled]), .hv-bodies button",
    quiet: ".hv-take",
    live: function () { return !!H.live; },
    opened: function () {
      H.result = null;
      H.error = "";
      load();
    },
    closing: function () {
      var strip = $id("harvest-game");
      if (strip) { strip.hidden = true; strip.innerHTML = ""; }
      H.sheet = null;
      // The scene panel asks again on the redraw the core makes as the layer goes.
      if (typeof harvestBoardStale === "function") harvestBoardStale();
    },
    footer: function () {
      var s = H.sheet || H.list;
      return { clock: s && s.clock ? s.clock.label : "" };
    },
  });
  H.close = core.closeLayer;
  H.say = core.say;
  // Open the sheet: on one carcass by its ref, or on the list of what has fallen here.
  H.open = function (ref, from) {
    H.ref = ref || null;
    if (core.open) { H.result = null; load(); return; }
    core.openLayer(from || document.activeElement);
  };
  Object.defineProperty(H, "isOpen", { enumerable: true, get: function () { return core.open; } });

  function sound(name, o) {
    try { if (window.Sound && typeof Sound.play === "function") Sound.play(name, o || {}); }
    catch (err) { /* sound is a nicety; never the reason a harvest fails */ }
  }

  // --- loading ----------------------------------------------------------------------------------
  // The list first (it says which bodies are carcasses, which still breathe, and the clock);
  // then the one carcass's sheet when there is one to show.
  function load() {
    H.busy = true;
    render();
    return C.api("/api/harvest").then(function (list) {
      H.list = list;
      var bodies = list.carcasses || [];
      if (!H.ref && bodies.length === 1) H.ref = bodies[0].ref;
      if (!H.ref) { H.sheet = null; return null; }
      return C.api("/api/harvest/" + encodeURIComponent(H.ref)).then(function (sheet) {
        H.sheet = sheet;
      });
    }).then(function () {
      H.busy = false;
      H.error = "";
      render();
      core.renderFoot();
      core.focusFirst();
    }, function (err) {
      H.busy = false;
      H.sheet = null;
      H.error = err.message || String(err);
      render();
      core.renderFoot();
    });
  }
  H.load = load;

  // --- drawing ----------------------------------------------------------------------------------
  function the(name) {
    var n = String(name || "").trim() || "the carcass";
    var low = n.toLowerCase();
    return /^(a|an|the) /.test(low) || low.indexOf(" the ") >= 0 ? n : "the " + n;
  }
  function cap(t) { t = String(t || ""); return t.charAt(0).toUpperCase() + t.slice(1); }
  function minutes(m) { return C.minutes(m); }
  // "Survival +5, Leatherworker 2 +2, skinning kit (circumstance) +2": the server's terms.
  function termsWords(terms) {
    return (terms || []).map(function (t) { return t.label + " " + C.sign(t.value); }).join(", ");
  }

  function render() {
    var body = $id("harvest-body"), title = $id("harvest-title");
    $id("harvest-err").textContent = H.error || "";
    if (H.busy && !H.sheet && !H.list) {
      body.innerHTML = '<p class="hv-note">Looking over what has fallen here.</p>';
      return;
    }
    if (!H.sheet) { title.textContent = "Harvest the carcass"; body.innerHTML = listHtml(); return; }
    var s = H.sheet, cr = s.creature || {};
    title.textContent = "Harvest the carcass: " + cap(cr.name || "");
    body.innerHTML = sheetHtml(s);
  }

  // The list of what has fallen here: carcasses with something to take, and bodies still
  // breathing (down and dying, not dead: "finish it first", lane C's live finding).
  function listHtml() {
    var l = H.list || {};
    var bodies = l.carcasses || [], breathing = l.breathing || [];
    var out = '<p class="hv-sub" id="harvest-sub">' + (bodies.length
      ? "Pick a body to work."
      : "Nothing has fallen here that you can take anything from.") + "</p>";
    if (bodies.length) {
      out += '<ul class="hv-bodies">' + bodies.map(function (b) {
        var mine = b.parts === 1 ? "1 part for your crafts" : b.parts + " parts for your crafts";
        var others = b.others ? (b.others === 1 ? ", 1 for crafts you do not have" : ", " + b.others + " for crafts you do not have") : "";
        return '<li><button type="button" data-hv-body="' + esc(b.ref) + '">' + esc(cap(b.name)) +
          "<small>" + esc(b.parts ? mine + others : "Nothing for your crafts" + others) + "</small></button></li>";
      }).join("") + "</ul>";
    }
    if (breathing.length) {
      out += breathing.map(function (b) {
        return '<p class="hv-note">' + esc(cap(the(b.name))) + " is still breathing: finish it first.</p>";
      }).join("");
    }
    return out;
  }

  function sheetHtml(s) {
    var cr = s.creature || {};
    var bodies = (H.list && H.list.carcasses) || [];
    var out = "";
    if (bodies.length > 1) out += '<button type="button" class="hv-back" data-hv-list>Every body here</button>';
    var who = [cr.size, cr.cr ? "CR " + cr.cr : ""].filter(Boolean).join(", ");
    out += '<p class="hv-sub" id="harvest-sub">' + (who ? "<b>" + esc(who) + ".</b> " : "") +
      esc([cr.dead_words, cr.keeps_words].filter(Boolean).join(" ")) + "</p>";
    if (!s.harvestable) {
      out += '<p class="hv-note">Nothing can be taken off it: ' + esc(s.why || "") + ".</p>";
    }
    out += '<p class="hv-note">' + esc(s.clock_words || "") + " " + esc(saltCarried(s.salt)) + "</p>";
    out += dangersHtml(s);
    if (H.result) out += resultHtml(H.result);

    // One group per craft, in the order the server listed the parts.
    // The crafts in a fixed order (by name), so taking a part never shuffles the groups: the
    // server lists parts in the body's tag order, and the first live run moved Leatherworker
    // from the top to the foot of the sheet once the dragonhide was taken.
    var groups = [], by = {};
    (s.parts || []).forEach(function (r) {
      if (!by[r.craft]) { by[r.craft] = { word: r.craft_word, rows: [] }; groups.push(r.craft); }
      by[r.craft].rows.push(r);
    });
    groups.sort(function (a, b) { return String(by[a].word).localeCompare(String(by[b].word)); });
    var first = !(s.taken || []).length;
    groups.forEach(function (g) {
      out += '<section class="hv-group" aria-label="' + esc(by[g].word) + '"><h3>' + esc(by[g].word) + "</h3>" +
        '<ul class="hv-rows">' + by[g].rows.map(function (r) { return rowHtml(r, s, first); }).join("") + "</ul></section>";
    });
    if (s.harvestable && !(s.parts || []).length) {
      out += '<p class="hv-note">' + ((s.taken || []).length ? "Everything your crafts can use is taken."
        : "Nothing on this body is any use to your crafts.") + "</p>";
    }
    if ((s.others || []).length) {
      out += '<p class="hv-note">' + esc("Also on it, for crafts you do not have: " + s.others.map(function (o) {
        return o.craft_word + " (" + (o.count === 1 ? "1 part" : o.count + " parts") + ")";
      }).join(", ") + ".") + "</p>";
    }
    if ((s.taken || []).length) {
      out += '<section class="hv-group" aria-label="Taken"><h3>Taken</h3><ul class="hv-rows">' +
        s.taken.map(function (r) {
          return '<li class="hv-row is-taken"><span class="hv-name">' + esc(r.name) +
            "<small>" + esc(r.craft_word) + "</small></span>" +
            '<p class="hv-line">Taken ' + esc(r.taken_words || "") + ". A part comes off a body once.</p></li>";
        }).join("") + "</ul></section>";
    }
    return out;
  }

  function saltCarried(n) {
    n = Number(n) || 0;
    return n ? "You carry " + (n === 1 ? "1 measure" : n + " measures") + " of curing salt."
      : "You carry no curing salt.";
  }

  // The dangers of this body, before anything is rolled (deeds plan §13; the owner: exposed
  // only on a miss by 5 or more). Faced once per body: a danger already faced says so.
  function dangersHtml(s) {
    var list = s.dangers || [];
    if (!list.length) return "";
    var open = list.filter(function (d) { return !d.faced; });
    return '<section class="hv-danger" aria-label="Dangerous to work"><h3>Dangerous to work</h3><ul>' +
      list.map(function (d) {
        return "<li>" + esc(cap(d.words)) + ": DC " + esc(d.dc) +
          (d.dice ? ", " + esc(d.dice) + " " + esc(d.kind) + " if it gets you" : "") +
          (d.faced ? ". Faced already." : ".") + "</li>";
      }).join("") + "</ul>" +
      (open.length ? "<p>The first cut faces " + (open.length === 1 ? "it" : "each of them") +
        " with the same roll's bonus, one die " + (open.length === 1 ? "" : "each ") +
        "before the part's own. A miss by 5 or more and you are exposed; a smaller miss does no harm.</p>"
        : "") + "</section>";
  }

  function rowHtml(r, s, first) {
    var out = '<li class="hv-row" data-hv-key="' + esc(r.key) + '">';
    var tier = r.tier && r.tier !== "common" ? r.tier : "";
    out += '<span class="hv-name">' + esc(r.name) + (tier ? "<small>" + esc(tier) + "</small>" : "") + "</span>";
    out += '<p class="hv-line is-need">' + esc(r.need_words || "") + ".</p>";
    if ((r.terms || []).length) out += '<p class="hv-line">' + esc(termsWords(r.terms)) + ".</p>";
    out += '<p class="hv-line">' + esc(yieldWords(r)) + ".</p>";
    if (r.salt_needed != null) {
      var cls = r.salt_covers ? "hv-line" : "hv-line is-short";
      out += '<p class="' + cls + '">' + esc(saltWords(r, s)) + "</p>";
    }
    if (r.deed_words) {
      out += '<p class="hv-line is-deed">' + esc(r.deed_words) +
        (first ? " You will be asked before the knife goes in." : " The deed is already done on this body.") + "</p>";
    }
    var busy = H.busy || !!H.live || !s.harvestable;
    out += '<button type="button" class="v2-btn is-go hv-take" data-hv-take="' + esc(r.key) + '"' +
      (busy ? " disabled" : "") + ' aria-label="Take the ' + esc(String(r.name).toLowerCase()) + '">Take</button>';
    return out + "</li>";
  }

  function yieldWords(r) {
    // A hide's units are the server's words ("1 unit", "1½ units"); anything else is one piece.
    var hide = r.branch === "hide" || r.branch === "scales";
    var what = hide ? (r.units_words || "") : "One piece";
    return cap(what) + ", " + minutes(r.minutes) + (r.game ? ", worked off with the knife" : "");
  }

  function saltWords(r, s) {
    var need = Number(r.salt_needed) || 0;
    var head = "Salting it on the spot takes " + (need === 1 ? "1 measure" : need + " measures") + " of curing salt";
    return head + (r.salt_covers ? ": you carry enough."
      : ": you carry " + (Number(s.salt) || 0) + ", so what the salt does not cover stays green on its 48-hour clock.");
  }

  // What the last take said: the tells (the same words the story was told), the roll in
  // numbers, the dangers met, what landed, and the mastery it paid. Every number the server's.
  function resultHtml(r) {
    var roll = r.roll || {};
    var good = !!roll.success;
    var out = '<section class="hv-result' + (good ? "" : " is-failed") + '" aria-label="What came of it">' +
      "<h3>" + esc(((r.verdict && r.verdict.word) || (good ? "Success" : "Failure")) + ": " + ((r.part && r.part.name) || "")) + "</h3>";
    (r.tells || []).forEach(function (t) { out += "<p>" + esc(t) + "</p>"; });
    if (roll.face != null) {
      out += '<p class="is-quiet">d20 ' + esc(roll.face) + " " + esc(C.sign(roll.bonus)) + " = " + esc(roll.total) +
        " against DC " + esc(roll.dc) + ".</p>";
    }
    (r.dangers || []).forEach(function (d) {
      out += '<p class="' + (d.exposed ? "is-warn" : "is-quiet") + '">' + esc(cap(d.words)) + ": d20 " + esc(d.face) +
        " " + esc(C.sign(roll.bonus)) + " = " + esc(d.total) + " against DC " + esc(d.dc) + ", " +
        esc(d.exposed ? "exposed." : d.margin >= 0 ? "safe." : "missed by " + (-d.margin) + ", no harm.") + "</p>";
    });
    if (r.lost) out += '<p class="is-warn">' + esc(r.lost) + "</p>";
    (r.stock || []).forEach(function (st) {
      out += "<p>" + esc(st.name) + (H.live || r.waiting ? ": its grade waits on the knife." : r.graded ? ": " + esc(r.graded) + "." : ".") + "</p>";
    });
    (r.carried || []).forEach(function (c) { out += "<p>" + esc(c.name) + " " + "×" + esc(c.count) + ", into your pack.</p>"; });
    if (r.salt_spent) out += '<p class="is-quiet">' + esc(r.salt_spent === 1 ? "1 measure" : r.salt_spent + " measures") + " of curing salt spent.</p>";
    if (r.yielded) out += "<p>A clean, careful job: more of it than usual came away.</p>";
    if (r.deed) out += '<p class="is-warn">This goes on your record: you cut from the body of a good creature.</p>';
    if (r.unplayed) out += '<p class="is-quiet">' + esc(r.unplayed) + "</p>";
    var m = r.mastery || {};
    // Each line is {why, mp} (rules/worldclass.py `_settle`'s reasons).
    (m.lines || []).forEach(function (line) {
      var why = line && typeof line === "object" ? line.why : line;
      var mp = line && typeof line === "object" ? Number(line.mp) || 0 : 0;
      if (why) out += '<p class="is-quiet">' + esc(cap(why) + (mp ? ": " + mp + " mastery" : "") + ".") + "</p>";
    });
    // `levelled` is the levels just reached (rules/worldclass.py `_advance`), in the part's craft.
    (m.levelled || []).forEach(function (l) {
      out += "<p>" + esc(((r.part && r.part.craft_word) || cap((r.part && r.part.craft) || "craft")) + " level " + l + ".") + "</p>";
    });
    return out + "</section>";
  }

  // --- choosing ---------------------------------------------------------------------------------
  layer.addEventListener("click", function (e) {
    var b = e.target.closest("[data-hv-body]");
    if (b) { H.ref = b.getAttribute("data-hv-body"); H.result = null; load(); return; }
    if (e.target.closest("[data-hv-list]")) { H.ref = null; H.sheet = null; H.result = null; load(); return; }
    var t = e.target.closest("[data-hv-take]");
    if (t && !t.disabled) take(t.getAttribute("data-hv-take"));
  });

  function rowOf(key) {
    return ((H.sheet && H.sheet.parts) || []).filter(function (r) { return r.key === key; })[0] || null;
  }

  // Take, after the deed's confirm when there is one (the deeds plan's UI note: before the roll).
  function take(key) {
    var row = rowOf(key), s = H.sheet;
    if (!row || !s || H.busy || H.live) return;
    var first = !(s.taken || []).length;
    var ask = row.deed && first ? core.confirm({
      title: "Take the " + String(row.name).toLowerCase() + "?",
      body: "This is the body of " + deedWho(row.deed) + ". Cutting from it is a bad deed, and it goes on your record whatever the roll says.",
      warn: row.deed_words,
      ok: "Take it", cancel: "Leave it", danger: true,
    }) : Promise.resolve(true);
    return ask.then(function (yes) {
      if (!yes) { core.say("You leave it."); return null; }
      return roll(row, first);
    });
  }
  function deedWho(tag) {
    if (/good-dragon$/.test(tag || "")) return "a good dragon";
    if (/good-outsider$/.test(tag || "")) return "a good outsider";
    return "a creature others would not have cut";
  }

  // --- the roll ---------------------------------------------------------------------------------
  function matShown(row, title, dc, why) {
    return { title: title, why: why, sides: 20, lo: 1, hi: 20, die: "1d20",
             terms: C.rollTerms({ terms: row.terms, bonus: row.bonus, dc: dc }) };
  }

  function roll(row, first) {
    var s = H.sheet;
    var dangers = first ? (s.dangers || []).filter(function (d) { return !d.faced; }) : [];
    var skill = cap(row.skill || "skill");
    var dice = window.Dice3D;
    var faces = {}, face = null;
    H.busy = true;
    H.error = "";
    H.result = null;
    render();
    var asks = Promise.resolve();
    // One die per danger, then the part's own: each face the player's (or the table's, when
    // the mat's own-roll is off: the server then rolls it), all sent together.
    dangers.forEach(function (d) {
      asks = asks.then(function () {
        if (!dice) return null;
        C.focusMat();
        return dice.ask(Object.assign({ hold: true }, matShown(row, skill + ": the first cut", d.dc, cap(d.words))));
      }).then(function (f) { if (f != null) faces[d.kind] = f; });
    });
    var before = s.clock && typeof s.clock.minute === "number" ? s.clock.minute : null;
    var answer = null;
    return asks.then(function () {
      if (!dice) return null;
      C.focusMat();
      return dice.ask(Object.assign({ hold: true }, matShown(row, skill + " (harvest)", row.dc, row.name)));
    }).then(function (f) {
      face = f;
      sound("leather.knife", { surface: row.surface || "" });
      var body = { creature: s.creature.ref, key: row.key };
      if (face != null) body.face = face;
      if (Object.keys(faces).length) body.danger_faces = faces;
      return C.api("/api/harvest/take", body);
    }).then(function (r) {
      answer = r;
      if (r.clock && before != null) C.turnClock(before, r.clock.minute, !!r.token);
      if (!dice) return null;
      // The dangers land first, each on the server's face with its own verdict in the mat.
      var landing = Promise.resolve();
      (r.dangers || []).forEach(function (d) {
        landing = landing.then(function () {
          var shown = matShown(row, skill + ": the first cut", d.dc, cap(d.words));
          var closing = dice.land(Object.assign({}, shown, {
            result: d.face,
            verdict: { text: d.exposed ? "Exposed" : d.margin >= 0 ? "Safe" : "No harm", good: !d.exposed },
            note: (d.tells || []).join(" "),
          }));
          // The throw disables the mat's button, and the keyboard fell to <body> (seen live,
          // keyboard only, 2026-10-08): Close takes it back once the die is at rest.
          var rest = typeof dice.settled === "function" ? dice.settled() : null;
          if (rest) rest.then(C.focusMat);
          return closing;
        });
      });
      return landing.then(function () {
        var shown = matShown(row, skill + " (harvest)", row.dc, row.name);
        var closing = dice.land(Object.assign({}, shown, { result: r.roll.face }));
        var rest = typeof dice.settled === "function" ? dice.settled() : null;
        var v = r.verdict || {};
        if (typeof showVerdict === "function") showVerdict({ verdict: v.verdict, natural: null }, rest);
        if (rest) rest.then(C.focusMat);
        return closing;
      });
    }).then(function () {
      var r = answer;
      H.busy = false;
      H.result = Object.assign({}, r, { waiting: !!r.token });
      if (r.sheet) H.sheet = r.sheet;
      if (!r.roll.success && r.lost) sound("leather.fail");
      render();
      core.renderFoot();
      if (r.token) return play(r);
      if ((r.stock || []).length && r.grade != null) {
        H.result.graded = r.grade === 0 ? "a reject: scraps only" : "grade " + r.grade;
      }
      render();
      core.say(sayResult(H.result));
      focusAfter();
      return null;
    }).catch(function (err) {
      H.busy = false;
      C.releaseClock();
      C.closeMat();
      H.error = err.message || String(err);
      render();
      core.say(H.error);
      focusAfter();
    });
  }

  function sayResult(r) {
    return [(r.verdict && r.verdict.word) || "", (r.tells || []).join(" "), r.lost || "",
            r.graded ? "Graded " + r.graded + "." : ""].filter(Boolean).join(" ");
  }

  function focusAfter() {
    core.refocus([".hv-take:not([disabled])", "harvest-close"]);
  }

  // --- the harvest game (contracts §11.1) ---------------------------------------------------------
  function gameKey() {
    var LG = window.LeatherGames, defs = window.BenchGameDefs || {};
    var games = window.BenchGames;
    if (!games || typeof games.play !== "function") return null;
    var key = LG && typeof LG.key === "function" ? LG.key("harvest") : "leather.harvest";
    var def = defs[key];
    return def && def.track === "leather" && typeof def.create === "function" ? key : null;
  }

  function play(r) {
    var key = gameKey();
    var tuning = r.tuning || {};
    if (!key) {
      // The game is lane U2's own file; a build without it keeps the hide at the grade it came
      // off at (harvest_views: "a reload between the two loses nothing").
      C.releaseClock();
      H.result.waiting = false;
      H.result.graded = r.grade === 0 ? "a reject: scraps only" : "grade " + r.grade;
      H.result.unplayed = "Taken without the knife work: the hide keeps the grade it came off at.";
      render();
      focusAfter();
      return null;
    }
    var strip = $id("harvest-game");
    H.live = { token: r.token };
    strip.hidden = false;
    strip.innerHTML = "";
    render();
    var steady = C.steady(), reduced = C.reduced();
    var game = Promise.resolve(BenchGames.play({
      method: key, tuning: tuning, band: tuning.band || null, mount: strip, stage: null,
      steady: steady, reducedMotion: reduced,
    }));
    return game.then(function (out) {
      out = out || {};
      var defects = typeof out.defects === "number" ? out.defects : 1 - (Number(out.score) || 0);
      return finish(r, defects);
    }, function (err) {
      if (window.console) console.error("harvest game failed:", err);
      return finish(r, null);
    });
  }

  function finish(r, defects) {
    var strip = $id("harvest-game");
    core.endGame();
    var live = H.live;
    H.busy = true;
    var send = defects == null ? Promise.reject(new Error("The knife work did not finish; the hide keeps the grade it came off at."))
      : C.api("/api/harvest/finish", { token: live.token, defects: defects });
    return send.then(function (f) {
      H.live = null;
      H.busy = false;
      strip.hidden = true;
      strip.innerHTML = "";
      C.releaseClock();
      H.result.waiting = false;
      H.result.graded = f.grade_words;
      H.result.stock = f.stock || H.result.stock;
      if (f.tells && f.tells.length) H.result.tells = (H.result.tells || []).concat(f.tells);
      if (f.sheet) H.sheet = f.sheet;
      sound(f.grade === 0 ? "leather.fail" : "leather.land");
      render();
      core.say("The hide comes free: " + f.grade_words + ".");
      focusAfter();
    }, function (err) {
      H.live = null;
      H.busy = false;
      strip.hidden = true;
      strip.innerHTML = "";
      C.releaseClock();
      H.result.waiting = false;
      H.error = err.message || String(err);
      render();
      focusAfter();
    });
  }

  // --- the craft-action hub's entry (UI plan §13) ---------------------------------------------------
  // The hub is drawn by 03-offers-and-map.js from the server's list, which lost the four carcass
  // excursions with lane C. "Harvest the carcass" is put back here, at the head of the list, each
  // time the list is drawn (a MutationObserver: the hub redraws its whole list on every open, and
  // this file must not need a hook in 03). It says why it cannot be used in the server's words.
  function hubEntry() {
    var host = $id("cp-actions");
    if (!host || host.querySelector("[data-hv-hub]")) return;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.setAttribute("data-hv-hub", "");
    btn.disabled = true;
    btn.innerHTML = "Harvest the carcass<small>every craft</small>";
    btn.title = "Looking for a body to work.";
    host.insertBefore(btn, host.firstChild);
    C.api("/api/harvest").then(function (l) {
      var bodies = (l.carcasses || []).filter(function (b) { return b.parts > 0; });
      var breathing = l.breathing || [];
      if (bodies.length) {
        btn.disabled = false;
        btn.setAttribute("data-harvest-open", bodies.length === 1 ? bodies[0].ref : "");
        btn.title = bodies.length === 1 ? "Take what your crafts can use off " + the(bodies[0].name) + "."
          : "Take what your crafts can use off the " + bodies.length + " bodies here.";
      } else if (breathing.length) {
        btn.title = cap(the(breathing[0].name)) + " is still breathing: finish it first.";
      } else {
        btn.title = (l.carcasses || []).length ? "Nothing on the bodies here is any use to your crafts."
          : "Nothing has fallen here to work on.";
      }
    }).catch(function (err) { btn.title = err.message || String(err); });
  }
  // The hub's opener carries its ref in `data-harvest-open` ("" is the list): the core's
  // `openWith` opens the sheet, and `openFrom` folds the hub.
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-hv-hub][data-harvest-open]");
    if (b) H.ref = b.getAttribute("data-harvest-open") || null;
  }, true);
  var hub = $id("cp-actions");
  if (hub && window.MutationObserver) {
    new MutationObserver(function () { hubEntry(); }).observe(hub, { childList: true });
  }
})();
