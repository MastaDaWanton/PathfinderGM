// The play table, part 30 (the herbalism bench: the layer, the flow, the stage area and
// the footer). Classic script; everything lives inside one IIFE and is reached through
// `window.Bench`, so no name here can shadow one of 01-22's (test_s6_panel_shell's rule
// that no top-level function is declared twice across the table's files).
//
// The design is docs/herbalism-ui-plan.md; the APIs it calls are docs/herbalism-
// contracts.md §3 and §4; the optional providers it drives are §5 (BenchStage from Lane F,
// BenchGames from Lane E, Sound and PGMPrefs from Lane G). The bench must be fully usable
// with NONE of them (contracts §5): each is looked up at the moment it is needed, never
// at load, so a provider that loads late or not at all changes nothing but the picture.
//
// THE FLOW (UI plan §5): pick a method and ask the server what fits; add ingredients by
// drag, click or Enter and ask again; Roll Craft throws the table's own d20 (Dice3D, the
// same ask, land and verdict as every other roll on the table) at a face the SERVER
// rolled; on a success the minigame plays and its score goes back to the server, which
// names the tier (the page never does, contracts §3.4); the product flies to its satchel
// tile; on a failure the tag says in words what was lost.
//
// WHO DRAWS WHAT. 30 owns the layer, focus, keys, the clock, the stage column and the
// footer. 31 draws the satchel, 34 the result tag, 35 the herbarium card, 36 the perk
// picker and the recipe book. They talk through `Bench.on(event, fn)`.
//
// MOTION (UI plan §10). Chrome moves by transform and opacity only, 200ms at most; the
// product's flight is 500ms; nothing loops while the bench is idle (no setInterval and no
// requestAnimationFrame in any bench file: tests/test_bench_ui.py greps for both). Every
// flourish is pointer-events: none and a click anywhere skips it.

(function () {
  "use strict";

  // --- vocabulary (contracts §2) --------------------------------------------------------
  // The nine methods in the order of the craft (UI plan §6.1).
  var METHODS = ["grind", "mix", "brew", "dry", "reduce", "extract", "infuse", "steep",
                 "neutralize"];
  // What the tool is called in a sentence ("Add a herb to the mortar").
  var TOOL = { grind: "mortar", mix: "bowl", brew: "pot", dry: "drying rack", reduce: "pan",
               extract: "board", infuse: "oil crock", steep: "jar", neutralize: "dish" };
  // The empty satchel's sentence: "Nothing you carry can be ground."
  var DONE = { grind: "ground", mix: "mixed", brew: "brewed", dry: "dried",
               reduce: "reduced", extract: "extracted", infuse: "infused", steep: "steeped",
               neutralize: "neutralized" };

  var $id = function (id) { return document.getElementById(id); };
  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };

  var B = window.Bench = {
    METHODS: METHODS, TOOL: TOOL, DONE: DONE, esc: esc,
    state: null,          // the last /api/bench/state body (contracts §3.1)
    check: null,          // the last /api/bench/check answer for the pot below (§3.2)
    pot: { method: null, items: [], batch: 1 },   // items: [{key, count}]
    open: false,
    busy: false,          // a roll or a finish in flight
    live: null,           // a minigame running: {token, tuning}
    result: null,         // the last finish (§3.4) or failed roll (§3.3), for the tag
    loading: false, error: "",
    recipe: null,         // a loaded recipe: {recipe, step}
    chain: [],            // steps finished since the bench opened, for Save recipe
  };

  // --- events: the modules' one channel ----------------------------------------------
  var subs = {};
  B.on = function (ev, fn) { (subs[ev] = subs[ev] || []).push(fn); };
  B.emit = function (ev, data) {
    (subs[ev] || []).forEach(function (fn) {
      try { fn(data); } catch (err) { console.error("bench " + ev + " handler failed:", err); }
    });
  };

  // --- time in words (UI plan §8) -------------------------------------------------------
  // Prose: "30 minutes", "2 hours 30 minutes", "3 days". Compact, for the stage's info
  // line only: "30m", "2h 30m", "3d".
  B.minutes = function (m, compact) {
    m = Math.max(0, Math.round(Number(m) || 0));
    var d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), n = m % 60;
    var parts = [];
    var unit = function (v, one, many, short) {
      if (!v) return;
      parts.push(compact ? v + short : v + " " + (v === 1 ? one : many));
    };
    unit(d, "day", "days", "d");
    unit(h, "hour", "hours", "h");
    if (!d) unit(n, "minute", "minutes", "m");
    return parts.length ? parts.join(" ") : (compact ? "0m" : "no time");
  };
  // A coarse span for the satchel's lines: "5 hours", "3 days", "40 minutes".
  B.span = function (m) {
    m = Math.max(0, Math.round(Number(m) || 0));
    if (m >= 2880) return Math.round(m / 1440) + " days";
    if (m >= 1440) return "1 day";
    if (m >= 120) return Math.round(m / 60) + " hours";
    if (m >= 60) return "1 hour";
    return m + (m === 1 ? " minute" : " minutes");
  };
  B.sign = function (v) { v = Number(v) || 0; return (v >= 0 ? "+" : "") + v; };

  // --- providers, each optional (contracts §5) ---------------------------------------
  B.stage = function () {
    var s = window.BenchStage;
    try { return s && typeof s.available === "function" && s.available() ? s : null; }
    catch (err) { return null; }
  };
  B.sound = function (name) {
    try { if (window.Sound && typeof Sound.play === "function") Sound.play(name); }
    catch (err) { /* sound is a nicety; never the reason a craft fails */ }
  };
  var STILL = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  // Reduced motion: the OS asked, or the player chose Short flourishes (UI plan §6.9).
  B.reduced = function () {
    var short = false;
    try { short = !!(window.PGMPrefs && PGMPrefs.get("flourishes") === "short"); }
    catch (err) { short = false; }
    return !!(STILL && STILL.matches) || short;
  };
  // Steady mode (UI plan §9): PGMPrefs when Lane G is here, else this page's own key.
  B.steady = function () {
    try {
      if (window.PGMPrefs && typeof PGMPrefs.get === "function") return !!PGMPrefs.get("steady");
    } catch (err) { /* fall through to the page's own key */ }
    try { return window.localStorage.getItem("pgm.steady") === "1"; } catch (err) { return false; }
  };
  B.setSteady = function (on) {
    try {
      if (window.PGMPrefs && typeof PGMPrefs.set === "function") { PGMPrefs.set("steady", !!on); return; }
    } catch (err) { /* fall through */ }
    try { window.localStorage.setItem("pgm.steady", on ? "1" : "0"); } catch (err) { /* private */ }
  };
  function remember(key, value) {
    try { window.localStorage.setItem(key, value); } catch (err) { /* private window */ }
  }
  function recall(key) {
    try { return window.localStorage.getItem(key); } catch (err) { return null; }
  }

  // Said once to a screen reader (the layer's own status line).
  B.say = function (text) {
    var s = $id("bench-say");
    if (!s) return;
    s.textContent = "";
    setTimeout(function () { s.textContent = text; }, 30);
  };

  // --- the API ---------------------------------------------------------------------------
  function csrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }
  // GET when there is no body. Errors are the server's own sentence (contracts §3:
  // `{"error": "<plain sentence>"}`), carried with the status so a 409 can be told apart.
  B.api = function (path, body) {
    if (FAKE) return FAKE.handle(path, body);   // MERGE: remove fake
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
  };

  // --- lookups -------------------------------------------------------------------------
  B.item = function (key) {
    var s = B.state && B.state.satchel;
    if (!s) return null;
    for (var i = 0; i < s.length; i++) if (s[i].key === key) return s[i];
    return null;
  };
  B.inPot = function (key) {
    for (var i = 0; i < B.pot.items.length; i++) if (B.pot.items[i].key === key) return B.pot.items[i].count;
    return 0;
  };
  B.methodInfo = function (id) {
    var list = (B.state && B.state.methods) || [];
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
    return null;
  };
  // Why this tile cannot go on the tool now, in the server's words, or "".
  B.why = function (key) {
    var fits = B.check && B.check.fits;
    return fits && typeof fits[key] === "string" ? fits[key] : "";
  };
  // The quality ladder's rung names. CONTRACT GAP (reported in the lane's hand-back):
  // §3.1 names only the ceiling (`ceiling_name`), and §2 says the names come from the
  // server and the UI never builds them, yet the tag's ladder (UI plan §6.5) shows every
  // rung from Crude up. `track.tiers` is read first, so a server that sends the list wins
  // at once; the fallback is §2's own fixed vocabulary, used only for display.
  var TIER_FALLBACK = ["Crude", "Sound", "Fine", "Superior", "Flawless"];
  B.tierName = function (i) {
    var t = B.state && B.state.track;
    if (t && Array.isArray(t.tiers) && t.tiers[i]) return t.tiers[i];
    if (t && i === t.ceiling && t.ceiling_name) return t.ceiling_name;
    return i < TIER_FALLBACK.length ? TIER_FALLBACK[i] : "Flawless +" + (i - 4);
  };

  // --- the layer: open, close, focus ----------------------------------------------------
  var bench = $id("bench");
  var opener = null;
  // What the layer makes inert while it is open: everything a click or Tab could reach on
  // the table. Not the deathveil (40), which must be able to cover the bench, and not the
  // dice mat, which dice3d.js builds on first use and which this list never names.
  var BEHIND = [".topbar", "#stage", ".modepage", "#tradepanel", "#sheetpanel", ".skip", "#veil",
                "#talktray"];
  var wasInert = [];
  var clockHome = null;
  var ambience = null;

  B.openBench = function (from) {
    if (!bench) return;
    if (B.open) return;
    B.open = true;
    opener = from || document.activeElement;
    wasInert = [];
    BEHIND.forEach(function (sel) {
      document.querySelectorAll(sel).forEach(function (el) {
        if (el === bench || bench.contains(el)) return;
        wasInert.push([el, el.inert]);
        el.inert = true;
      });
    });
    // The time-skip clock (09-clock.js) lives in #stage at z-index 8, under this layer. A
    // step of an hour or more turns the scene clock with that same animation (UI plan
    // §4.1), so while the bench is open the clock's element stands on the bench's stage;
    // 09 finds it by id, wherever it is.
    var clock = $id("clockpop");
    var stage = $id("bench-stage");
    if (clock && stage && clock.parentNode !== stage) {
      clockHome = { parent: clock.parentNode, next: clock.nextSibling };
      stage.appendChild(clock);
    }
    document.body.classList.add("bench-on");
    bench.hidden = false;
    bench.classList.toggle("bench-still", B.reduced());
    void bench.offsetWidth;            // so the 200ms fade starts from nothing
    bench.classList.add("is-in");
    if (location.hash !== "#bench") {
      try { history.replaceState(null, "", "#bench"); } catch (err) { /* file: URL */ }
    }
    B.sound("bench.open");
    B.emit("open");
    focusFirst();
    load();
  };

  B.closeBench = function () {
    if (!B.open) return;
    if (B.live) { askStop(); return; }       // never drop a live game on the floor
    B.open = false;
    bench.classList.remove("is-in");
    bench.hidden = true;
    document.body.classList.remove("bench-on");
    wasInert.forEach(function (p) { p[0].inert = p[1]; });
    wasInert = [];
    var clock = $id("clockpop");
    if (clock && clockHome) {
      clockHome.parent.insertBefore(clock, clockHome.next);
      clockHome = null;
    }
    if (ambience) { try { ambience.stop(); } catch (err) { /* */ } ambience = null; }
    var stage = B.stage();
    if (stage && stageMounted) { try { stage.unmount(); } catch (err) { /* */ } stageMounted = false; }
    B.emit("close");
    if (location.hash === "#bench") {
      try { history.replaceState(null, "", location.pathname + location.search); } catch (err) { /* */ }
    }
    // Time passed and the satchel changed: the table under the layer is drawn again from
    // the server, the same way every other action of the table's ends.
    if (typeof render === "function" && typeof getState === "function") {
      getState().then(function (s) { render(s); }).catch(function () { /* resync catches up */ });
    }
    var back = opener && document.contains(opener) && !opener.closest("[inert]") ? opener : $id("open-bench");
    opener = null;
    if (back && typeof back.focus === "function") back.focus();
  };

  function focusFirst() {
    var active = bench.querySelector(".bm[aria-checked='true']") || $id("bench-close");
    if (active) active.focus();
  }

  // What may hold focus right now: the dice mat while it shows a roll, else the bench's
  // open modal popover, else the bench. The trap wraps Tab inside it (UI plan §4.1).
  function trapRoot() {
    var mat = document.querySelector("#d3d-mat.on");
    if (mat) return mat;
    var modal = bench.querySelector(".bench-modal:not([hidden])");
    return modal || bench;
  }
  function focusables(root) {
    return Array.prototype.filter.call(root.querySelectorAll(
      "button, [href], input, select, textarea, summary, [tabindex]:not([tabindex='-1'])"),
      function (el) {
        return !el.disabled && el.getClientRects().length && !el.closest("[hidden]") &&
               el.getAttribute("tabindex") !== "-1";
      });
  }
  document.addEventListener("keydown", function (e) {
    if (!B.open || e.key !== "Tab") return;
    if (document.querySelector("#deathveil.on")) return;    // death owns the screen
    var root = trapRoot();
    var list = focusables(root);
    if (!list.length) return;
    var first = list[0], last = list[list.length - 1];
    var at = document.activeElement;
    if (!root.contains(at)) { e.preventDefault(); first.focus(); return; }
    if (e.shiftKey && at === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && at === last) { e.preventDefault(); first.focus(); }
  }, true);

  // --- Esc, one layer at a time ----------------------------------------------------------
  // The popovers (card, confirm, perks, recipes) push a closer; Esc runs the newest.
  var escStack = [];
  B.pushEsc = function (fn) { escStack.push(fn); };
  B.dropEsc = function (fn) { escStack = escStack.filter(function (f) { return f !== fn; }); };

  bench && bench.addEventListener("keydown", function (e) {
    var tag = e.target && e.target.tagName;
    var typing = /^(INPUT|TEXTAREA|SELECT)$/.test(tag);
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      if (escStack.length) { escStack[escStack.length - 1](); return; }
      if (B.live) { askStop(); return; }
      if (document.querySelector("#d3d-mat.on")) return;
      B.closeBench();
      return;
    }
    // 1-9 pick a method (UI plan §6.1), unless the player is typing or a game has the keys.
    if (!typing && !B.live && !escStack.length && /^[1-9]$/.test(e.key) &&
        !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      B.setMethod(METHODS[Number(e.key) - 1], { focus: true });
    }
    // The table's own shortcuts listen on the document ("m" opens the map, Esc closes the
    // sheet's details): none of them may act on a table that is behind the bench. While a
    // game is live its keys go through, because Lane E may listen on the document.
    if (!B.live) e.stopPropagation();
  });

  // A game running while the player's attention is elsewhere would score time they were
  // not there for (UI plan §7): it pauses on blur. It does NOT carry on by itself on
  // focus: the UI plan's line is "Paused. Press Space to carry on.", and resuming the
  // instant the window came back would start the clock before the player's hand was on
  // the key (the games lane's note at merge). The frame waits for Space or a click.
  window.addEventListener("blur", function () {
    if (B.live && window.BenchGames && BenchGames.pause) { try { BenchGames.pause(); } catch (err) { /* */ } }
  });

  // --- the opener buttons and the #bench hash (UI plan §4.1) ----------------------------
  document.addEventListener("click", function (e) {
    var go = e.target.closest && e.target.closest("[data-bench-open]");
    if (!go) return;
    // From the Craft action panel: shut it first, so the bench's focus comes back to the
    // panel's own button rather than to a control inside a closed popover.
    var panel = $id("craftpanel");
    var from = go;
    if (panel && panel.contains(go)) {
      panel.hidden = true;
      if (typeof shellCraftExpanded === "function") shellCraftExpanded(false);
      from = $id("craftaction") || go;
    }
    B.openBench(from);
  });
  $id("bench-close") && $id("bench-close").addEventListener("click", function () { B.closeBench(); });
  function fromHash() { if (location.hash === "#bench" && !B.open) B.openBench($id("open-bench")); }
  window.addEventListener("hashchange", fromHash);
  // /play/#bench, the old bench's "Open the herbalism bench" (craft.html), opens it on load.
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fromHash);
  else setTimeout(fromHash, 0);

  // --- loading the bench ------------------------------------------------------------------
  var checkSeq = 0;
  function load() {
    B.loading = true; B.error = ""; B.result = null;
    B.emit("loading");
    renderStage();
    return B.api("/api/bench/state").then(function (s) {
      B.loading = false;
      adoptState(s);
      var last = recall("pgm.bench.method");
      var m = B.methodInfo(last);
      if (!m || m.locked) {
        var open = (s.methods || []).filter(function (x) { return !x.locked; })[0];
        last = open ? open.id : METHODS[0];
      }
      B.pot = { method: null, items: [], batch: 1 };
      var ready = B.setMethod(last, { quiet: true });
      // MERGE: remove fake. `?benchfake=demo` starts with comfrey on the mortar, for the
      // lane's saved screenshots, which cannot click.
      if (FAKE && FAKE.demo && ready) ready.then(function () { B.addItem("s1", 2); });
      // The methods did not exist when the layer opened, so focus waited on Close; it
      // moves to the chosen method unless the player has already gone somewhere.
      var at = document.activeElement;
      if (!at || at === document.body || at.id === "bench-close") focusFirst();
      maybeAmbience();
    }).catch(function (err) {
      B.loading = false;
      B.error = err.message || String(err);
      B.emit("error", B.error);
      renderStage();
    });
  }
  B.reload = load;

  function adoptState(s) {
    B.state = s;
    // Pot entries for things no longer carried, or carried in fewer, are trimmed: the
    // satchel is the server's, and a pot that disagrees with it is a roll the server
    // would refuse.
    B.pot.items = B.pot.items.filter(function (p) {
      var it = B.item(p.key);
      if (!it) return false;
      p.count = Math.min(p.count, it.count);
      return p.count > 0;
    });
    B.emit("state", s);
    renderFoot();
  }
  B.adoptState = adoptState;

  B.refresh = function () {
    return B.api("/api/bench/state").then(function (s) { adoptState(s); return B.runCheck(); })
      .catch(function (err) { B.say(err.message); });
  };

  // The ground's sound under the stage, from open to close (Lane G's rule, 2026-10-02):
  // indoors under a roof, the tavern's room in a tavern or an inn, the night outdoors at
  // night, else the biome itself (Sound knows an alias for every biome in rules/biomes.py).
  // Night here is 8pm to 6am by the scene's own minute of the day.
  B.ambienceName = function (g) {
    if (!g) return "";
    if (g.roofed) return /\b(tavern|inn|alehouse)\b/i.test(g.place || "") ? "tavern" : "indoors";
    if (/\b(tavern|inn)\b/i.test(g.place || "")) return "tavern";
    var mod = typeof g.minute === "number" ? ((g.minute % 1440) + 1440) % 1440 : 720;
    if (mod >= 20 * 60 || mod < 6 * 60) return "night";
    return g.biome || "";
  };
  function maybeAmbience() {
    var name = B.ambienceName(B.state && B.state.ground);
    if (!name || ambience || !B.open || !window.Sound || typeof Sound.loop !== "function") return;
    try { ambience = Sound.loop("ambience." + name) || null; } catch (err) { ambience = null; }
  }

  // --- the method -----------------------------------------------------------------------
  B.setMethod = function (id, opts) {
    opts = opts || {};
    if (B.busy || B.live) return;
    var info = B.methodInfo(id);
    if (!info) return;
    if (info.locked) {
      B.say(info.name + " is locked. " + (info.lock_reason || ""));
      B.emit("refused", { method: id, why: info.lock_reason });
      return;
    }
    var changed = B.pot.method !== id;
    B.pot.method = id;
    if (changed && !opts.keepPot) {
      B.pot.items = [];
      var st = B.stage();
      if (st && stageMounted) { try { st.clearIngredients(); } catch (err) { /* */ } }
    }
    if (!opts.keepResult) B.result = null;
    remember("pgm.bench.method", id);
    if (changed && !opts.quiet) B.sound("bench.method." + id);
    B.emit("method", id);
    mountStage();
    renderStage();
    if (opts.focus) {
      var btn = bench.querySelector('.bm[data-method="' + id + '"]');
      if (btn) btn.focus();
    }
    return B.runCheck();
  };

  // --- the pot --------------------------------------------------------------------------
  // `fits` is the server's answer to "can this go on the tool now" for every carried item
  // (contracts §3.2), so a refusal here is the server's reason, said, and nothing added.
  B.addItem = function (key, n) {
    if (B.busy || B.live || !B.pot.method) return false;
    var it = B.item(key);
    if (!it) return false;
    var why = B.why(key);
    if (why) { B.say(it.name + ": " + why); B.emit("refused", { key: key, why: why }); return false; }
    var have = B.inPot(key);
    var add = Math.min(n || 1, it.count - have);
    if (add <= 0) { B.say("All your " + it.name + " is on the " + TOOL[B.pot.method] + " already."); return false; }
    var entry = B.pot.items.filter(function (p) { return p.key === key; })[0];
    if (entry) entry.count += add; else B.pot.items.push({ key: key, count: add });
    var st = B.stage();
    if (st && stageMounted && !entry) {
      try { st.addIngredient({ key: key, part: it.part, name: it.name }); } catch (err) { /* */ }
    }
    B.result = null;
    // The stage plays the drop itself as the item lands on its rim; only the flat
    // stand-in needs the page to play it, or it sounds twice.
    if (!(st && stageMounted)) B.sound("bench.drop." + (it.part || "leaf"));
    B.say(it.name + " on the " + TOOL[B.pot.method] + ", " + (have + add) + " in all.");
    B.emit("pot");
    renderStage();
    B.runCheck();
    return true;
  };
  B.removeItem = function (key) {
    if (B.busy || B.live) return;
    var before = B.pot.items.length;
    B.pot.items = B.pot.items.filter(function (p) { return p.key !== key; });
    if (before === B.pot.items.length) return;
    var st = B.stage();
    if (st && stageMounted) { try { st.removeIngredient(key); } catch (err) { /* */ } }
    var it = B.item(key);
    if (it) B.say(it.name + " taken off the " + TOOL[B.pot.method] + ".");
    B.emit("pot");
    renderStage();
    B.runCheck();
  };
  B.setBatch = function (n) {
    n = Math.max(1, Math.round(Number(n) || 1));
    if (n === B.pot.batch) return;
    B.pot.batch = n;
    B.emit("pot");
    renderStage();
    B.runCheck();
  };
  // The most doses the pot's materials allow, from the satchel's counts. CONTRACT GAP: the
  // check has no batch ceiling, so "all" counts carried things against what one dose puts
  // on the tool; the server still refuses a batch it cannot make, in its own words.
  B.maxBatch = function () {
    if (!B.pot.items.length) return 1;
    var most = Infinity;
    B.pot.items.forEach(function (p) {
      var it = B.item(p.key);
      if (it && p.count > 0) most = Math.min(most, Math.floor(it.count / p.count));
    });
    return Math.max(1, most === Infinity ? 1 : most);
  };

  function potBody(extra) {
    var body = { method: B.pot.method, batch: B.pot.batch,
                 items: B.pot.items.map(function (p) { return { key: p.key, count: p.count }; }) };
    if (extra) Object.keys(extra).forEach(function (k) { body[k] = extra[k]; });
    return body;
  }

  // Ask the server what fits and what the pot makes. The newest question wins: an answer
  // to an older pot is dropped rather than drawn over a newer one.
  B.runCheck = function () {
    if (!B.pot.method || !B.state) return Promise.resolve(null);
    var seq = ++checkSeq;
    B.emit("checking");
    return B.api("/api/bench/check", potBody()).then(function (c) {
      if (seq !== checkSeq) return null;
      B.check = c;
      B.emit("check", c);
      renderStage();
      return c;
    }).catch(function (err) {
      if (seq !== checkSeq) return null;
      B.check = { fits: {}, problems: [err.message], can_roll: false };
      B.emit("check", B.check);
      renderStage();
      return null;
    });
  };

  // --- the stage column (UI plan §6.3) ----------------------------------------------------
  var stageMounted = false, stageMounting = null;
  function mountStage() {
    var st = B.stage();
    var host = $id("bench-tool");
    if (!st || !host) return;
    try { st.reducedMotion(B.reduced()); } catch (err) { /* */ }
    var ground = (B.state && B.state.ground) || {};
    var after = function () {
      // `place` too: a tavern is not a biome, and the stage can only find the bar top in
      // the place's own name (Lane F's note at merge).
      try { st.setGround({ biome: ground.biome, roofed: !!ground.roofed, minute: ground.minute,
                           place: ground.place }); } catch (err) { /* */ }
      try { if (B.pot.method) st.setTool(B.pot.method); } catch (err) { /* */ }
    };
    if (stageMounted) { after(); return; }
    if (stageMounting) { stageMounting.then(after); return; }
    host.innerHTML = "";
    host.classList.add("has-stage");
    try {
      stageMounting = Promise.resolve(st.mount(host)).then(function (ok) {
        // `mount` resolves false, not rejects, when WebGL refuses on this machine: the
        // flat stand-in takes over exactly as for a rejection.
        if (ok === false) throw new Error("no stage here");
        stageMounted = true; stageMounting = null; after();
        B.pot.items.forEach(function (p) {
          var it = B.item(p.key);
          if (it) try { st.addIngredient({ key: p.key, part: it.part, name: it.name }); } catch (err) { /* */ }
        });
      }).catch(function () {
        // A stage that cannot draw is the WebGL fallback's case, not an error to show.
        stageMounted = false; stageMounting = null; host.classList.remove("has-stage"); renderStage();
      });
    } catch (err) { stageMounting = null; host.classList.remove("has-stage"); }
  }

  // The flat stand-in: the tool's engraved icon at 160px on the ground (UI plan §6.3,
  // "WebGL fallback"). It is also the whole stage until Lane F's arrives.
  function drawFallbackTool() {
    var host = $id("bench-tool");
    if (!host || host.classList.contains("has-stage")) return;
    var m = B.pot.method;
    if (host.dataset.tool === (m || "")) return;
    host.dataset.tool = m || "";
    host.innerHTML = "";
    if (!m) return;
    var ring = document.createElement("div");
    ring.className = "bench-flat";
    ring.appendChild(window.BenchIcons ? BenchIcons.el(m, { size: 160 }) : document.createTextNode(""));
    var name = document.createElement("span");
    name.className = "bench-flat-name";
    name.textContent = TOOL[m];
    ring.appendChild(name);
    host.appendChild(ring);
  }

  function renderStage() {
    if (!bench) return;
    drawFallbackTool();
    var chips = $id("bench-chips"), info = $id("bench-info"), why = $id("bench-why");
    var roll = $id("bench-roll");
    var m = B.pot.method;
    // The chips on the tool's rim: what is on it, each with its own ×.
    chips.innerHTML = B.pot.items.map(function (p) {
      var it = B.item(p.key);
      if (!it) return "";
      return '<li class="bench-chip"><span>' + esc(it.name) + (p.count > 1 ? " ×" + p.count : "") +
        '</span><button type="button" class="bench-chip-x" data-unpot="' + esc(p.key) +
        '" aria-label="Take ' + esc(it.name) + ' off the ' + esc(TOOL[m] || "tool") + '">×</button></li>';
    }).join("");
    chips.hidden = !B.pot.items.length;

    var c = B.check, empty = !B.pot.items.length;
    var line = "", reason = "";
    if (B.loading) {
      line = "";
    } else if (B.error) {
      reason = "";
    } else if (!m) {
      reason = "";
    } else if (empty) {
      reason = "Add a herb to the " + TOOL[m] + ".";
    } else if (c) {
      var doses = B.pot.batch === 1 ? "1 dose." : B.pot.batch + " doses.";
      var bits = [doses];
      if (c.minutes != null) bits.push(B.minutes(c.minutes, true) + ".");
      if (c.dc != null) {
        if (c.need != null) bits.push("DC " + c.dc + ", you need " + c.need + " or better.");
        else bits.push("DC " + c.dc + ".");
      }
      line = bits.join(" ");
      reason = (c.problems && c.problems[0]) || c.impossible || "";
    }
    info.textContent = line;
    why.textContent = B.busy ? "" : reason;
    roll.disabled = !!(B.busy || B.live || B.loading || B.error || empty || !c || !c.can_roll || c.need == null);
  }
  B.renderStage = renderStage;

  bench && bench.addEventListener("click", function (e) {
    // A press of any plain button answers with `ui.click`; the ones with a sound of their
    // own (a method, an ingredient, the roll, the card's study and taste) do not double it.
    var btn = e.target.closest("button");
    if (btn && !btn.disabled && !btn.closest(".bm, .bt-add, #bench-roll, [data-hc]")) B.sound("ui.click");
    var x = e.target.closest("[data-unpot]");
    if (x) { B.removeItem(x.dataset.unpot); return; }
    if (e.target.closest("#bench-roll")) { B.roll(); }
  });

  // Dropping a satchel tile on the tool (31 starts the drag). Drag is never the only way:
  // a click or Enter on the tile does the same (UI plan §5, step 3).
  var stageEl = $id("bench-stage");
  function dragging(e) {
    return B.dragKey && e.dataTransfer && Array.prototype.indexOf.call(e.dataTransfer.types || [], "text/plain") >= 0;
  }
  function dragOver(on) {
    var tool = $id("bench-tool");
    if (tool) tool.classList.toggle("is-dragover", on);
    var st = B.stage();
    if (st && stageMounted) { try { st.setDragOver(on); } catch (err) { /* */ } }
  }
  if (stageEl) {
    stageEl.addEventListener("dragover", function (e) {
      if (!dragging(e)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
      dragOver(true);
    });
    stageEl.addEventListener("dragleave", function (e) {
      if (!stageEl.contains(e.relatedTarget)) dragOver(false);
    });
    stageEl.addEventListener("drop", function (e) {
      if (!dragging(e)) return;
      e.preventDefault();
      dragOver(false);
      var key = B.dragKey;
      B.dragKey = null;
      B.addItem(key);
    });
  }
  document.addEventListener("dragend", function () { if (B.open) { dragOver(false); B.dragKey = null; } });

  // --- the roll (UI plan §5, step 4) ------------------------------------------------------
  // The d20 is the table's own: Dice3D.ask winds it up and holds the mat open (`hold`),
  // the server rolls the face (a null face, the old bench's convention, contracts §3.3),
  // Dice3D.land throws it onto that face, and showVerdict (22-roll-verdict.js) plays the
  // engine's word once the die is at rest. Exactly the path 04's sendRoll takes.
  function focusMat() {
    setTimeout(function () {
      // The player's own die (the mat's debug toggle) wants its number typed first.
      var own = document.querySelector("#d3d-own.on #d3d-face");
      var go = document.getElementById("d3d-go");
      if (own && go && !go.disabled && go.textContent === "Roll") own.focus();
      else if (go && !go.disabled) go.focus();
    }, 40);
  }
  B.focusMat = focusMat;
  function rollTerms(c) {
    var terms = (c.terms || []).map(function (t) { return { label: t.label, value: B.sign(t.value) }; });
    if (c.terms && c.terms.length !== 1 && c.bonus != null) {
      terms.push({ label: "your modifier", value: B.sign(c.bonus), total: true });
    }
    if (c.dc != null) terms.push({ label: "beat", value: c.dc });
    return terms;
  }

  B.roll = function () {
    var c = B.check;
    if (B.busy || B.live || !c || !c.can_roll || c.need == null || !B.pot.items.length) return;
    B.busy = true;
    B.result = null;
    B.emit("rolling");
    renderStage();
    var name = c.product && c.product.name ? c.product.name : "Herbalism";
    var shown = { title: "Craft (herbalism)", why: name, sides: 20, lo: 1, hi: 20, die: "1d20",
                  terms: rollTerms(c) };
    var dice = window.Dice3D;
    var asking = dice ? dice.ask(Object.assign({ hold: true }, shown)) : Promise.resolve(null);
    if (dice) focusMat();
    var body = potBody();
    var roll = null;
    return asking.then(function (face) {
      B.sound("bench.roll");
      body.face = face == null ? null : face;
      return B.api("/api/bench/roll", body);
    }).then(function (r) {
      roll = r;
      tickClock(r.minutes, r.clock);
      if (!dice) return null;
      var closing = dice.land(Object.assign({}, shown, { result: r.roll.face }));
      var rest = typeof dice.settled === "function" ? dice.settled() : null;
      if (typeof showVerdict === "function") showVerdict(r.verdict, rest);
      if (rest) rest.then(focusMat);
      // The mat is the player's to close (dice3d.js: `land` resolves on Close), and the
      // game rises only after it, so nothing starts under a mat still being read.
      return closing;
    }).then(function () {
      B.busy = false;
      if (roll.roll && roll.roll.success && roll.token) return play(roll);
      return failed(roll).then(focusAfterRoll);
    }).catch(function (err) {
      B.busy = false;
      if (dice && typeof dice.close === "function") dice.close();
      $id("bench-why").textContent = err.message || String(err);
      B.say(err.message || String(err));
      renderStage();
      focusAfterRoll();
    });
  };

  // Where the keyboard goes when the mat closes on a failure: Roll Craft again if the pot
  // can still be rolled, else the satchel's row (a ruined pot is empty), never <body>,
  // which is where it fell when the disabled Roll was asked to take it.
  function focusAfterRoll() {
    var r = $id("bench-roll");
    var row = document.querySelector('#bench-list .bt-add[tabindex="0"]');
    var to = r && !r.disabled ? r : row || $id("bench-close");
    if (to) to.focus();
  }

  // The scene clock, moved by the step's time (UI plan §4.1). The footer reads the API's
  // own label; a step of an hour or more also turns the table's clock face (09-clock.js),
  // which waits for the dice mat to close before it shows.
  function tickClock(minutes, clock) {
    var g = B.state && B.state.ground;
    if (clock && B.state) B.state.clock = clock;
    if (g && typeof g.minute === "number" && minutes) {
      var before = g.minute, after = before + minutes;
      g.minute = after;
      // 09 keeps its own rule (an hour or more) and its own reduced-motion face.
      if (minutes >= 60 && typeof clockWhenClear === "function") {
        try { clockWhenClear(before, after, ""); } catch (err) { /* the label still moved */ }
      }
    }
    renderFoot();
  }
  B.tickClock = tickClock;

  // --- the failure (UI plan §5, step 4) ---------------------------------------------------
  function failed(r) {
    B.result = { failed: true, roll: r.roll, lost: r.lost || [], minutes: r.minutes,
                 pot: B.pot.items.map(function (p) { return { key: p.key, count: p.count }; }) };
    flourish("fail");          // plays its own sting, once (stage or page)
    B.emit("result", B.result);
    var lost = r.lost || [];
    B.say(lost.length ? "Failure. Some materials were ruined." : "Failure. Nothing was lost.");
    // The server already took what was ruined; the satchel is read again so its counts
    // and the pot agree with it.
    return B.refresh();
  }

  // --- the minigame (UI plan §5, step 5; contracts §5.2) ---------------------------------
  var stopAsking = false;
  function play(r) {
    B.live = { token: r.token, tuning: r.tuning || {} };
    var strip = $id("bench-game");
    strip.hidden = false;
    strip.innerHTML = "";
    void strip.offsetWidth;
    strip.classList.add("is-up");
    bench.classList.add("is-playing");
    B.emit("play", B.live);
    renderStage();
    var games = window.BenchGames;
    var tuning = r.tuning || {};
    var game;
    if (games && typeof games.play === "function") {
      var view = null, st = B.stage();
      if (st && stageMounted && typeof st.game === "function") {
        try { view = st.game(B.pot.method); } catch (err) { view = null; }
      }
      game = Promise.resolve(games.play({
        method: B.pot.method, part: tuning.part, tuning: tuning, mount: strip, stage: view,
        steady: B.steady(), reducedMotion: B.reduced(),
        onScore: function (s) { B.emit("score", s); },
      }));
    } else {
      game = devFinish(strip);      // MERGE: remove dev fallback
    }
    return game.then(function (out) {
      out = out || {};
      return finish(Number(out.score) || 0, !!out.stopped);
    }, function (err) {
      // A game that throws is scored as stopped at nothing: materials are never lost to a
      // stop (revamp plan §3), and the server says what came of it.
      console.error("bench game failed:", err);
      return finish(0, true);
    });
  }

  // MERGE: remove dev fallback. Until Lane E's games land, a success posts a middling
  // score from one button, so the whole flow (finish, land, mastery) runs end to end.
  function devFinish(strip) {
    return new Promise(function (done) {
      strip.innerHTML = '<div class="bench-devgame"><p>The minigame for this method is not ' +
        'built yet.</p><button type="button" class="v2-btn is-go" id="bench-devfinish">' +
        'Finish (no minigame yet)</button></div>';
      var b = $id("bench-devfinish");
      b.addEventListener("click", function () { done({ score: 0.5, stopped: false }); });
      B.devStop = function () { done({ score: 0, stopped: true }); };
      b.focus();
    });
  }

  // Esc during a game: "Stop and keep what you have?" (UI plan §4.1). Stopping scores the
  // run so far, through BenchGames.stop(), which resolves the game's promise.
  function askStop() {
    if (stopAsking || !B.live) return;
    stopAsking = true;
    var games = window.BenchGames;
    if (games && games.pause) { try { games.pause(); } catch (err) { /* */ } }
    B.confirm({
      title: "Stop and keep what you have?",
      body: "The run so far is scored. No materials are lost to a stop.",
      ok: "Stop", cancel: "Keep playing",
    }).then(function (yes) {
      stopAsking = false;
      if (!B.live) return;
      if (yes) {
        if (games && typeof games.stop === "function") { try { games.stop(); } catch (err) { /* */ } }
        else if (B.devStop) B.devStop();
      } else if (games && games.resume) {
        try { games.resume(); } catch (err) { /* */ }
      }
    });
  }

  // --- the finish and the landing (UI plan §5, step 6) ------------------------------------
  function finish(score, stopped) {
    var live = B.live;
    var strip = $id("bench-game");
    strip.classList.remove("is-up");
    bench.classList.remove("is-playing");
    B.busy = true;
    renderStage();
    return B.api("/api/bench/finish", { token: live.token, score: score, stopped: stopped })
      .then(function (f) {
        B.live = null;
        B.busy = false;
        strip.hidden = true;
        strip.innerHTML = "";
        B.chain.push({ method: B.pot.method, items: B.pot.items.map(function (p) {
          var it = B.item(p.key);
          return { ingredient_id: it ? it.ingredient_id : null, count: p.count };
        }).filter(function (x) { return x.ingredient_id; }) });
        var from = productRect();
        B.pot.items = [];
        var st = B.stage();
        if (st && stageMounted) { try { st.clearIngredients(); } catch (err) { /* */ } }
        B.result = { finished: true, finish: f, stopped: stopped };
        if (f.state) adoptState(f.state);
        B.emit("result", B.result);
        land(f, from);
        renderStage();
        B.runCheck();
        var next = $id("bench-next");
        (next || $id("bench-roll")).focus();
      }).catch(function (err) {
        B.live = null;
        B.busy = false;
        strip.hidden = true;
        strip.innerHTML = "";
        $id("bench-why").textContent = err.message || String(err);
        renderStage();
      });
  }

  function productRect() {
    var st = B.stage();
    if (st && stageMounted && typeof st.productRect === "function") {
      try { var r = st.productRect(); if (r && r.width) return r; } catch (err) { /* */ }
    }
    var tool = document.querySelector("#bench-tool .bicon") || $id("bench-tool");
    return tool ? tool.getBoundingClientRect() : null;
  }

  // The tier's flourish, then the product's flight to its tile (UI plan §10). Flawless is
  // index 4 and up on the fixed ladder (contracts §2); the server named the index.
  function land(f, from) {
    var flawless = (Number(f.tier) || 0) >= 4;
    if (flawless) flourish("flawless", f.tier_name);
    else flourish("land");
    var made = f.made;
    B.say("Made " + (made ? made.name : "it") + (f.count > 1 ? ", " + f.count + " of them" : "") +
          ", " + (f.tier_name || "") + ".");
    if (!made) return;
    var tile = document.querySelector('#bench-satchel .bt[data-key="' + cssEscape(made.key) + '"]');
    if (!tile) return;
    if (tile.scrollIntoView) tile.scrollIntoView({ block: "nearest" });
    var to = tile.getBoundingClientRect();
    var pulse = function () {
      // The satchel may have been redrawn while the product flew (the check after a
      // finish answers in that time), so the tile is found again by its key, and 31 keeps
      // the mark on it through any redraw in the next moment.
      B.landed = { key: made.key, until: Date.now() + 1400 };
      var now = document.querySelector('#bench-satchel .bt[data-key="' + cssEscape(made.key) + '"]');
      if (!now) return;
      now.classList.remove("is-landed");
      void now.offsetWidth;
      now.classList.add("is-landed");
      // Reduced motion holds the highlight still instead of pulsing it; either way it goes.
      setTimeout(function () { now.classList.remove("is-landed"); }, 1400);
    };
    if (B.reduced() || !from || !to.width || typeof document.body.animate !== "function") { pulse(); return; }
    fly(made, from, to).then(pulse);
  }
  function cssEscape(s) { return window.CSS && CSS.escape ? CSS.escape(s) : String(s).replace(/"/g, '\\"'); }

  // 500ms along a curve: up off the tool, then over to the tile, as a brass roundel. On its
  // own fixed element with pointer-events: none, at the verdict layer's height (66), so it
  // covers nothing a click needs; a click anywhere finishes it at once.
  var flying = [];
  function fly(item, from, to) {
    var el = window.BenchIcons ? BenchIcons.el(item.form || item.part || "leaf", { size: 44, label: item.name })
                               : document.createElement("span");
    el.classList.add("bench-fly");
    document.body.appendChild(el);
    var x0 = from.left + from.width / 2 - 22, y0 = from.top + from.height / 2 - 22;
    var x1 = to.left + 18 - 22 + 8, y1 = to.top + to.height / 2 - 22;
    var lift = Math.min(160, Math.max(60, (y0 - Math.min(y0, y1)) + 80));
    var at = function (p) {
      // A quadratic Bezier through a control point above both ends: the arc of a thrown thing.
      var cx = (x0 + x1) / 2, cy = Math.min(y0, y1) - lift;
      var x = (1 - p) * (1 - p) * x0 + 2 * (1 - p) * p * cx + p * p * x1;
      var y = (1 - p) * (1 - p) * y0 + 2 * (1 - p) * p * cy + p * p * y1;
      var s = p < 0.2 ? 1 + p : 1.2 - 0.5 * p;
      return { transform: "translate(" + x.toFixed(1) + "px," + y.toFixed(1) + "px) scale(" + s.toFixed(3) + ")",
               opacity: p > 0.92 ? (1 - p) / 0.08 : 1, offset: p };
    };
    var frames = [0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 1].map(at);
    var anim = el.animate(frames, { duration: 500, easing: "cubic-bezier(.3,.1,.3,1)", fill: "forwards" });
    flying.push(anim);
    return anim.finished.catch(function () { /* skipped */ }).then(function () {
      flying = flying.filter(function (a) { return a !== anim; });
      el.remove();
    });
  }
  // Any click skips a flourish (UI plan §10, the one-second rule): it completes at once.
  document.addEventListener("pointerdown", function () {
    if (!flying.length) return;
    flying.slice().forEach(function (a) { try { a.finish(); } catch (err) { /* */ } });
  }, true);

  // Flourishes through the stage when it is there, else the flat ones: Flawless borrows
  // the table's own cast brass word (22-roll-verdict.js `verdictWord`) and its gilt sparks;
  // a failure dims the stage for 600ms. Short flourishes keep the word and drop the rest.
  function flourish(kind, word) {
    var st = B.stage();
    var staged = false;
    if (st && stageMounted && typeof st.flourish === "function") {
      // The stage plays its own sting with its flourish (bench.fail, bench.flawless,
      // bench.land, bench.tier.up), so the page plays none here or every one sounds twice.
      try { st.reducedMotion(B.reduced()); st.flourish(kind); staged = true; }
      catch (err) { staged = false; }
    }
    if (!staged) B.sound("bench." + (kind === "tierUp" ? "tier.up" : kind));
    // The cast brass word is the page's, over the stage or the flat stand-in alike: the
    // UI plan's Flawless is the 0.2.3 verdict word, which a WebGL canvas does not draw.
    if (staged && kind !== "flawless") return;
    // From the tool's own disc, not its whole cell: from the cell the gilt ring opened
    // 300px wide round empty ground (first screenshot of the flourish).
    var tool = document.querySelector("#bench-tool .bench-flat .bicon") || $id("bench-tool");
    if (kind === "fail") {
      var stage = $id("bench-stage");
      stage.classList.remove("is-dim");
      void stage.offsetWidth;
      stage.classList.add("is-dim");
      return;
    }
    if (kind === "flawless" && typeof verdictWord === "function" && tool) {
      var r = tool.getBoundingClientRect();
      var at = { x: r.left + r.width / 2, y: r.top + r.height / 2 };
      var still = B.reduced();
      try {
        verdictWord({ good: true, word: word || "Flawless", text: word || "Flawless", sub: "",
                      still: still, ms: still ? 1200 : 1300 }, at, Math.min(r.width, r.height));
      } catch (err) { /* the word is a nicety */ }
      // The stage throws its own gilt sparks; the page's are for the flat stand-in only.
      if (!staged && !still && typeof VerdictSparks === "object" && VerdictSparks) {
        try { VerdictSparks.burst("triumph", at.x, at.y, 1300, Math.min(r.width, r.height) * 0.4); } catch (err) { /* */ }
      }
    }
  }
  B.flourish = flourish;

  // --- a confirm inside the layer (taste, stop) ----------------------------------------
  // A small modal of the bench's own: two buttons, the safe one focused first, Esc is the
  // safe one. Resolves true for the first button.
  B.confirm = function (o) {
    return new Promise(function (done) {
      var pops = $id("bench-pops");
      var back = document.activeElement;
      var wrap = document.createElement("div");
      wrap.className = "bench-modal bench-confirm";
      wrap.setAttribute("role", "alertdialog");
      wrap.setAttribute("aria-modal", "true");
      var id = "bench-confirm-" + Date.now();
      wrap.setAttribute("aria-labelledby", id + "-t");
      wrap.setAttribute("aria-describedby", id + "-b");
      wrap.innerHTML = '<div class="bench-scrim"></div><div class="bench-dialog v2-framed v2-card-leather">' +
        '<i class="v2-rim" aria-hidden="true"></i>' +
        '<h3 id="' + id + '-t">' + esc(o.title) + '</h3>' +
        '<p id="' + id + '-b">' + esc(o.body || "") + '</p>' +
        (o.warn ? '<p class="bench-warnline">' + esc(o.warn) + '</p>' : "") +
        '<div class="bench-dialog-acts"><button type="button" class="v2-btn is-quiet" data-no>' +
        esc(o.cancel || "Cancel") + '</button><button type="button" class="v2-btn ' +
        (o.danger ? "is-quiet bench-danger" : "is-go") + '" data-yes>' + esc(o.ok || "OK") +
        '</button></div></div>';
      pops.appendChild(wrap);
      var finish = function (v) {
        B.dropEsc(onEsc);
        wrap.remove();
        if (back && document.contains(back) && back.focus) back.focus();
        done(v);
      };
      var onEsc = function () { finish(false); };
      B.pushEsc(onEsc);
      wrap.querySelector("[data-no]").addEventListener("click", function () { finish(false); });
      wrap.querySelector("[data-yes]").addEventListener("click", function () { finish(true); });
      wrap.querySelector(".bench-scrim").addEventListener("click", function () { finish(false); });
      wrap.querySelector("[data-no]").focus();
    });
  };

  // --- the method strip (UI plan §6.1) ---------------------------------------------------
  // A radio group: one stop in the Tab order, ← and → move and choose, 1-9 jump. Locked
  // methods stay in the row with the lock icon and the level in words in the label itself,
  // never in a tooltip only.
  function renderMethods() {
    var row = $id("bench-methods");
    if (!row) return;
    var list = (B.state && B.state.methods) || METHODS.map(function (id) {
      return { id: id, name: id.charAt(0).toUpperCase() + id.slice(1), locked: false, lock_reason: "" };
    });
    row.innerHTML = "";
    list.forEach(function (m, i) {
      var on = m.id === B.pot.method;
      var b = document.createElement("button");
      b.type = "button";
      b.className = "bm" + (m.locked ? " is-locked" : "");
      b.dataset.method = m.id;
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.tabIndex = on || (!B.pot.method && i === 0) ? 0 : -1;
      if (m.locked) b.setAttribute("aria-disabled", "true");
      var label = m.name + (m.locked && m.lock_reason ? ", " + m.lock_reason : "");
      b.setAttribute("aria-label", label + ". Key " + (i + 1));
      b.appendChild(window.BenchIcons ? BenchIcons.el(m.locked ? "lock" : m.id, { size: 22, label: m.locked ? "lock" : m.name })
                                      : document.createElement("span"));
      var t = document.createElement("span");
      t.className = "bm-name";
      t.textContent = m.name;
      b.appendChild(t);
      if (m.locked && m.lock_reason) {
        var l = document.createElement("span");
        l.className = "bm-lock";
        l.textContent = m.lock_reason;
        b.appendChild(l);
      }
      // The words, shown on hover and focus when the strip is down to icons (1280 wide).
      var tip = document.createElement("span");
      tip.className = "bm-tip";
      tip.setAttribute("aria-hidden", "true");
      tip.textContent = label;
      b.appendChild(tip);
      row.appendChild(b);
    });
  }
  B.on("state", renderMethods);
  B.on("method", function () {
    var row = $id("bench-methods");
    if (!row) return;
    row.querySelectorAll(".bm").forEach(function (b) {
      var on = b.dataset.method === B.pot.method;
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.tabIndex = on ? 0 : -1;
    });
  });
  var methodsEl = $id("bench-methods");
  if (methodsEl) {
    methodsEl.addEventListener("click", function (e) {
      var b = e.target.closest(".bm");
      if (b) B.setMethod(b.dataset.method, { focus: true });
    });
    methodsEl.addEventListener("keydown", function (e) {
      var b = e.target.closest(".bm");
      if (!b) return;
      var all = Array.prototype.slice.call(methodsEl.querySelectorAll(".bm"));
      var i = all.indexOf(b), to = -1;
      if (e.key === "ArrowRight" || e.key === "ArrowDown") to = (i + 1) % all.length;
      else if (e.key === "ArrowLeft" || e.key === "ArrowUp") to = (i - 1 + all.length) % all.length;
      else if (e.key === "Home") to = 0;
      else if (e.key === "End") to = all.length - 1;
      if (to < 0) return;
      e.preventDefault();
      // Arrows choose what they land on, as a radio group does; a locked one takes focus
      // and says why, and the choice stays where it was.
      all[to].focus();
      if (!all[to].classList.contains("is-locked")) B.setMethod(all[to].dataset.method, { focus: true });
      else {
        var info = B.methodInfo(all[to].dataset.method);
        B.say((info ? info.name : "") + " is locked. " + (info && info.lock_reason ? info.lock_reason : ""));
      }
    });
  }
  renderMethods();

  // --- the footer (UI plan §6.8) ----------------------------------------------------------
  function renderFoot() {
    var foot = $id("bench-foot-in");
    if (!foot) return;
    var s = B.state, t = s && s.track;
    var clock = s && s.clock && s.clock.label ? s.clock.label : "";
    var prog = "";
    if (t) {
      var need = t.to_next && t.to_next.need, have = t.to_next && t.to_next.have;
      var frac = need ? Math.max(0, Math.min(1, have / need)) : 1;
      prog = '<span class="bf-level">Herbalist ' + esc(t.level) + '</span>' +
        '<span class="bf-line" aria-hidden="true"><i style="transform:scaleX(' + frac.toFixed(3) + ')"></i></span>' +
        '<span class="bf-mp">' + (need ? esc(have) + " / " + esc(need) : esc(t.mp) + " mastery") + '</span>';
    }
    var picks = t && t.picks_banked ? '<button type="button" class="bf-btn bf-perks" data-bench-perks>' +
      (t.picks_banked === 1 ? "1 perk to pick" : t.picks_banked + " perks to pick") + '</button>' : "";
    var steady = B.steady();
    foot.innerHTML =
      '<span class="bf-clock" id="bench-clock">' + esc(clock) + '</span>' +
      '<span class="bf-track" role="group" aria-label="Your herbalism">' + prog + '</span>' + picks +
      '<span class="bf-gap"></span>' +
      '<button type="button" class="bf-btn" data-bench-recipes aria-haspopup="dialog">Recipes</button>' +
      '<button type="button" class="bf-btn" data-bench-herbarium>Herbarium</button>' +
      '<button type="button" class="bf-btn bf-steady" role="switch" aria-checked="' + steady +
      '" data-bench-steady>Steady mode<span class="bf-switch" aria-hidden="true"></span></button>';
  }
  B.renderFoot = renderFoot;
  var footEl = $id("bench-foot");
  if (footEl) {
    footEl.addEventListener("click", function (e) {
      if (e.target.closest("[data-bench-steady]")) {
        B.setSteady(!B.steady());
        renderFoot();
        var s = footEl.querySelector("[data-bench-steady]");
        if (s) s.focus();
        B.say(B.steady() ? "Steady mode on." : "Steady mode off.");
        return;
      }
      if (e.target.closest("[data-bench-herbarium]")) {
        // The Journal's herbarium (Lane C, 21-tab-journal.js), in place of the bench: the
        // bench closes and the Journal opens; `bench:herbarium` tells it which section.
        B.closeBench();
        if (B.open) return;
        if (typeof Shell === "object" && Shell && Shell.show) Shell.show("journal");
        document.dispatchEvent(new CustomEvent("bench:herbarium"));
      }
    });
  }
  renderFoot();

  // Forage here (the satchel's empty state): the table's own Craft action, opened.
  B.forage = function () {
    B.closeBench();
    if (B.open) return;
    var btn = $id("craftaction"), panel = $id("craftpanel");
    if (btn && panel && panel.hidden) btn.click();
  };

  // Reduced motion can change while the bench is open (the OS setting, or Settings).
  if (STILL && STILL.addEventListener) {
    STILL.addEventListener("change", function () { if (bench) bench.classList.toggle("bench-still", B.reduced()); });
  }
  try {
    if (window.PGMPrefs && typeof PGMPrefs.on === "function") {
      PGMPrefs.on("flourishes", function () { if (bench) bench.classList.toggle("bench-still", B.reduced()); });
      PGMPrefs.on("steady", renderFoot);
    }
  } catch (err) { /* prefs are optional */ }
  // The first gesture unlocks audio (contracts §5.3).
  document.addEventListener("pointerdown", function once() {
    document.removeEventListener("pointerdown", once, true);
    try { if (window.Sound && Sound.unlock) Sound.unlock(); } catch (err) { /* */ }
  }, true);

  // ======================================================================================
  // MERGE: remove fake. `?benchfake=1` answers every bench and herb call from canned JSON
  // in exactly the shapes of contracts §3 and §4, so the UI can be driven end to end while
  // the API lanes (B2, C) are still stubs that answer 501. `?benchfake=perks` starts with
  // two perk picks banked; `?benchfake=error` fails the state call, for the error state.
  // ======================================================================================
  var FAKE = /[?&]benchfake=/.test(location.search) ? makeFake(location.search) : null;

  function makeFake(search) {
    var mode = (search.match(/benchfake=([a-z0-9]+)/) || [])[1] || "1";
    var minute = 14 * 1440 + 18 * 60 + 20;
    var level = mode === "perks" ? 4 : 2;
    var perks = {};
    var serial = 20;
    var dc = 12, bonus = 6;
    var HERBS = {
      comfrey: { name: "Comfrey", kind: "herb", part: "root", tier: "common", biomes: ["forest"],
        props: [{ text: "Heals 1d4", drawback: false, known: true, how: "tasted, day 9" },
                { text: "Knits a sprain", drawback: false, known: true, how: "studied, day 11" },
                { text: "Nauseates if eaten raw", drawback: true, known: false },
                { text: "Draws out splinters", drawback: false, known: false }] },
      garlic: { name: "Garlic", kind: "herb", part: "root", tier: "common", biomes: ["grassland"],
        props: [{ text: "Wards off sickness for a day", drawback: false, known: true, how: "told by Old Marta" }] },
      yarrow: { name: "Yarrow", kind: "herb", part: "flower", tier: "uncommon", biomes: ["grassland", "road"],
        props: [{ text: "Stops bleeding", drawback: false, known: true, how: "tasted, day 12" },
                { text: "Sickened 1 round", drawback: true, known: false },
                { text: "Eases a fever", drawback: false, known: false }] },
      willow: { name: "Willow bark", kind: "herb", part: "bark", tier: "common", biomes: ["swamp"],
        props: [{ text: "Dulls pain, +1 on saves against pain", drawback: false, known: true, how: "studied, day 3" }] },
      barley: { name: "Barley", kind: "herb", part: "seed", tier: "common", biomes: ["grassland"],
        props: [{ text: "Binds a poultice", drawback: false, known: true, how: "studied, day 2" }] },
      hemlock: { name: "Hemlock", kind: "herb", part: "leaf", tier: "rare", biomes: ["forest"],
        danger: "it can paralyse",
        props: [{ text: "Numbs a wound", drawback: false, known: false },
                { text: "Paralysis, Fortitude DC 16", drawback: true, known: true, how: "studied, day 13" }] },
      spider: { name: "Spider venom gland", kind: "monster part", part: "gland", tier: "uncommon", biomes: ["forest"],
        props: [{ text: "Poison, 1d2 Strength", drawback: true, known: true, how: "studied, day 6" }] },
      olive: { name: "Olive oil", kind: "oil", part: "oil", tier: "common", biomes: [], props: [] },
      beeswax: { name: "Beeswax", kind: "base", part: "wax", tier: "common", biomes: [], props: [] },
      spirit: { name: "Grain spirit", kind: "solvent", part: "liquid", tier: "common", biomes: [], props: [] },
      dragon: { name: "Dragon's tongue", kind: "herb", part: "leaf", tier: "legendary", biomes: ["mountain"],
        props: [{ text: "Fire resistance 10", drawback: false, known: false }] },
      mint: { name: "Mint", kind: "herb", part: "leaf", tier: "common", biomes: ["grassland"],
        props: [{ text: "Settles the stomach", drawback: false, known: true, how: "tasted, day 1" }] },
    };
    function unknownOf(id) {
      var h = HERBS[id];
      return h ? h.props.filter(function (p) { return !p.known; }).length : 0;
    }
    function item(key, id, extra) {
      var h = HERBS[id] || {};
      var it = { key: key, name: h.name || id, ingredient_id: id, kind: h.kind || "herb",
                 part: h.part || "leaf", tier: h.tier || "common", state: "raw", form: null,
                 quality: null, quality_name: null, count: 1, unknown: unknownOf(id),
                 spoils_in: 9840, ready_at: null, crafted: false };
      Object.keys(extra || {}).forEach(function (k) { it[k] = extra[k]; });
      return it;
    }
    var satchel = [
      item("s1", "comfrey", { count: 3 }),
      item("s2", "garlic", { count: 1 }),
      item("s3", "yarrow", { count: 4, spoils_in: 290 }),
      item("s4", "willow", { count: 2 }),
      item("s5", "barley", { count: 2, state: "ground", name: "Barley, ground" }),
      item("s6", "hemlock", { count: 1 }),
      item("s7", "spider", { count: 1, spoils_in: 1200 }),
      item("s8", "olive", { count: 2, spoils_in: null }),
      item("s9", "beeswax", { count: 1, spoils_in: null }),
      item("s10", "spirit", { count: 1, spoils_in: null }),
      item("s11", "dragon", { count: 1 }),
      item("s12", "mint", { count: 2, state: "dried", name: "Mint, dried", spoils_in: 40000 }),
      item("s13", "yarrow", { name: "Yarrow infusion", form: "infusion", quality: 2, quality_name: "Fine",
                              crafted: true, count: 1, spoils_in: 600, unknown: 0 }),
      item("s14", "comfrey", { name: "Comfrey tincture", form: "tincture", crafted: true, count: 1,
                               ready_at: minute + 9 * 1440, spoils_in: null, unknown: 0 }),
    ];
    var recipes = [{ id: "r1", name: "Comfrey poultice", steps: [
      { method: "grind", items: [{ ingredient_id: "comfrey", count: 2 }] },
      { method: "mix", items: [{ ingredient_id: "comfrey", count: 1 }, { ingredient_id: "barley", count: 1 }] }] }];
    var mp = mode === "perks" ? 210 : 30;
    var pending = null;
    var firsts = {};

    function ceiling() { return { 1: 2, 2: 3, 3: 4 }[Math.min(level, 3)] + (perks.quality || 0); }
    function banked() {
      var earned = Math.max(0, level - 3) * 2, spent = 0;
      Object.keys(perks).forEach(function (k) { spent += perks[k]; });
      return Math.max(0, earned - spent);
    }
    function label(m) {
      var day = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), n = m % 60;
      var hh = h % 12 || 12, ap = h < 12 ? "am" : "pm";
      return "Day " + day + ", " + hh + ":" + (n < 10 ? "0" : "") + n + ap;
    }
    function track() {
      var c = ceiling();
      return { id: "herbalist", level: level, mp: mp, to_next: { need: level * 30 + 5, have: mp % (level * 30 + 5) },
               ceiling: c, ceiling_name: c <= 4 ? TIER_FALLBACK[c] : "Flawless +" + (c - 4),
               perks: Object.assign({}, perks), picks_banked: banked(),
               next_rung: level < 3 ? "Flawless at Herbalist 3" : "Flawless +" + (c - 3) + " at your next Quality perk" };
    }
    var LEVEL_OF = { grind: 1, mix: 1, brew: 1, dry: 2, reduce: 2, extract: 2, infuse: 2, steep: 2, neutralize: 3 };
    function state() {
      return { track: track(),
        methods: METHODS.map(function (id) {
          var locked = LEVEL_OF[id] > level;
          return { id: id, name: id.charAt(0).toUpperCase() + id.slice(1), level: LEVEL_OF[id],
                   locked: locked, lock_reason: locked ? "Herbalist " + LEVEL_OF[id] : "" };
        }),
        satchel: satchel.filter(function (s) { return s.count > 0; }).map(function (s) { return Object.assign({}, s); }),
        ground: { biome: "forest", roofed: false, minute: minute, place: "The Outskirts" },
        recipes: recipes.slice(), clock: { day: Math.floor(minute / 1440), label: label(minute) } };
    }
    var SOLID = { leaf: 1, flower: 1, root: 1, bark: 1, berry: 1, seed: 1, fungus: 1 };
    function fit(method, s) {
      if (s.ready_at != null) return "it is still steeping";
      if (s.tier === "legendary" && level < 3) return "Herbalist 3 for legendary";
      if (s.crafted) return "a finished product can't be worked again";
      if (s.part === "gland" && method !== "extract") return "it has to be extracted before anything else can be done with it";
      var volatile = s.ingredient_id === "hemlock";
      switch (method) {
        case "grind":
          if (volatile) return "it is volatile, neutralize it first";
          if (s.state === "ground") return "already ground";
          if (!SOLID[s.part]) return "only a solid can be ground";
          return "";
        case "mix":
          if (s.state === "ground" || s.part === "wax" || s.part === "oil") return "";
          return "grind it first";
        case "brew":
          if (!SOLID[s.part]) return "only a plant part can be brewed";
          return "";
        case "dry":
          if (s.state === "dried") return "already dried";
          if (!SOLID[s.part]) return "only a solid can be dried";
          if (s.count < 2) return "you need 2 to make 1 dried";
          return "";
        case "reduce":
          if (s.part !== "liquid") return "only a liquid can be reduced";
          if (s.count < 2) return "you need 2 to make 1";
          return "";
        case "extract":
          return s.part === "gland" ? "" : "there is nothing in it to extract";
        case "infuse":
          if (s.part === "oil" || s.state === "dried") return "";
          return "dry it first";
        case "steep":
          if (s.part === "liquid" || SOLID[s.part]) return "";
          return "only a herb or a spirit can be steeped";
        default:
          return "Herbalist 3";
      }
    }
    var PER_DOSE = { grind: 10, mix: 10, brew: 30, dry: 480, reduce: 60, extract: 30, infuse: 240,
                     steep: 10, neutralize: 20 };
    var FORM = { grind: "powder", mix: "poultice", brew: "infusion", dry: "dried", reduce: "reduction",
                 extract: "extract", infuse: "infused-oil", steep: "tincture", neutralize: "extract" };
    var TAKEN = { powder: "stirred into food or drink", poultice: "bound on a wound", infusion: "drunk",
                  decoction: "drunk", dried: "kept for later work", reduction: "drunk",
                  extract: "kept for later work", "infused-oil": "not used directly; sold or mixed",
                  tincture: "drops on the tongue", "salve-base": "kept for mixing" };
    var KEEPS = { powder: 43200, poultice: 1440, infusion: 1440, decoction: 4320, dried: 129600, reduction: 10080,
                  extract: 43200, "infused-oil": 43200, tincture: 525600, "salve-base": 129600 };
    function byKey(k) { return satchel.filter(function (s) { return s.key === k; })[0]; }
    function check(b) {
      var fits = {};
      satchel.forEach(function (s) { if (s.count > 0) fits[s.key] = fit(b.method, s); });
      var items = (b.items || []).map(function (p) { return { s: byKey(p.key), count: p.count }; })
        .filter(function (p) { return p.s; });
      var problems = [];
      var batch = Math.max(1, b.batch || 1);
      items.forEach(function (p) {
        if (fits[p.s.key]) problems.push(p.s.name + ": " + fits[p.s.key] + ".");
        if (p.count * batch > p.s.count) problems.push("You carry " + p.s.count + " " + p.s.name + ", not " + p.count * batch + ".");
      });
      if (b.method === "infuse" && items.length && !items.some(function (p) { return p.s.part === "oil"; })) problems.push("Add 1 oil.");
      if (b.method === "steep" && items.length && !items.some(function (p) { return p.s.part === "liquid"; })) problems.push("Add a spirit or vinegar.");
      if (b.method === "mix" && items.length === 1) problems.push("Mixing needs two prepared things.");
      var first = items[0] && items[0].s;
      var form = FORM[b.method];
      if (b.method === "grind" && first && (first.part === "bark")) form = "salve-base";
      if (b.method === "brew" && first && (first.part === "root" || first.part === "bark")) form = "decoction";
      var c = ceiling();
      var effects = [], drawbacks = [], unknown = 0;
      items.forEach(function (p) {
        var h = HERBS[p.s.ingredient_id];
        if (!h) return;
        unknown += unknownOf(p.s.ingredient_id);
        h.props.forEach(function (pr) {
          if (!pr.known) return;
          var m = pr.text.match(/^(.*?)(\d+)d(\d+)(.*)$/);
          var tiers = [];
          for (var i = 0; i <= c; i++) {
            tiers.push(m ? m[1] + m[2] + "d" + (Number(m[3]) + Math.max(0, i - 1) * 2) + m[4] : pr.text + (i > 1 ? ", for " + (i * 10) + " minutes" : ""));
          }
          (pr.drawback ? drawbacks : effects).push({ base: pr.text, by_tier: tiers });
        });
      });
      var name = first ? (first.name.replace(/, (ground|dried)$/, "") + " " + form.replace("-", " ")) : "";
      var dcHere = dc + (items.some(function (p) { return p.s.tier === "rare"; }) ? 4 : 0);
      var need = dcHere - bonus;
      return { fits: fits, problems: problems, can_roll: !!items.length && !problems.length,
        minutes: PER_DOSE[b.method] * batch, dc: dcHere, bonus: bonus,
        terms: [{ label: "Herbalist " + level, value: level }, { label: "Wisdom", value: 2 },
                { label: "Craft (alchemy) ranks", value: bonus - level - 2 }],
        need: need > 20 ? null : Math.max(2, need),
        impossible: need > 20 ? "No roll of the d20 can make this yet." : "",
        product: first ? { name: name.charAt(0).toUpperCase() + name.slice(1), form: form, taken: TAKEN[form] || "",
          keeps_minutes: KEEPS[form] || 1440, routes: ["ingest"], unknown: unknown,
          effects: effects, drawbacks: drawbacks,
          source_text: "Pound the fresh root to a pulp and bind it on the hurt with clean linen; change it at dusk." } : null };
    }
    function roll(b) {
      var c = check(b);
      if (!c.can_roll) throw Object.assign(new Error(c.problems[0] || "Nothing on the tool."), { status: 400 });
      var face = b.face == null ? 1 + Math.floor(Math.random() * 20) : Number(b.face);
      var total = face + bonus, ok = total >= c.dc, margin = total - c.dc;
      var lost = [];
      if (!ok && margin <= -5) {
        b.items.forEach(function (p) {
          var s = byKey(p.key);
          var n = Math.ceil(p.count * (b.batch || 1) / 2);
          s.count -= n;
          lost.push({ key: s.key, name: s.name, count: n });
        });
      }
      minute += c.minutes;
      var token = ok ? "t" + (++serial) : undefined;
      if (ok) pending = { token: token, body: b, check: c };
      var first = byKey(b.items[0].key);
      return { roll: { face: face, bonus: bonus, total: total, dc: c.dc, success: ok, margin: margin },
        verdict: { verdict: ok ? "success" : "failure", natural: face === 20 ? 20 : face === 1 ? 1 : null },
        lost: lost, minutes: c.minutes, clock: { day: Math.floor(minute / 1440), label: label(minute) },
        token: token,
        tuning: { method: b.method, part: first.part, difficulty: 0.6, seconds: 6, beats: 8,
                  infusion: b.method === "brew" && (first.part === "leaf" || first.part === "flower") } };
    }
    function finish(b) {
      if (!pending || pending.token !== b.token) throw Object.assign(new Error("That roll has already been finished."), { status: 409 });
      var p = pending; pending = null;
      var c = ceiling();
      var score = Math.max(0, Math.min(1, Number(b.score) || 0));
      var tier = Math.min(c, Math.floor(score * (c + 1)));
      var batch = p.body.batch || 1;
      p.body.items.forEach(function (it) { var s = byKey(it.key); s.count -= it.count * batch; });
      var first = byKey(p.body.items[0].key);
      var made = item("s" + (++serial), first.ingredient_id, {
        name: p.check.product.name, form: p.check.product.form, quality: tier,
        quality_name: tier <= 4 ? TIER_FALLBACK[tier] : "Flawless +" + (tier - 4), crafted: true,
        count: batch, unknown: 0, spoils_in: p.check.product.keeps_minutes,
        state: p.body.method === "dry" ? "dried" : p.body.method === "grind" ? "ground" : "raw" });
      if (made.form === "salve-base" || made.form === "infused-oil" || p.body.method === "dry" || p.body.method === "grind") made.crafted = false;
      satchel.push(made);
      var lines = [{ why: p.body.method.charAt(0).toUpperCase() + p.body.method.slice(1) + ", " + first.name.toLowerCase(), mp: 1 }];
      if (!firsts[made.form]) { firsts[made.form] = 1; lines.push({ why: "first " + made.form.replace("-", " "), mp: 3 }); }
      if (tier >= 2) lines.push({ why: "quality bonus", mp: tier - 1 });
      var gained = lines.reduce(function (a, l) { return a + l.mp; }, 0);
      mp += gained;
      var discoveries = [];
      var h = HERBS[first.ingredient_id];
      var hid = h && h.props.filter(function (pr) { return !pr.known && !pr.drawback; })[0];
      if (hid) { hid.known = true; hid.how = "worked, day " + Math.floor(minute / 1440); discoveries.push({ ingredient_id: first.ingredient_id, name: h.name, text: hid.text }); }
      satchel.forEach(function (s) { if (!s.crafted) s.unknown = unknownOf(s.ingredient_id); });
      var nxt = null;
      if (p.body.method === "grind" && first.ingredient_id === "comfrey") nxt = { method: "mix" };
      return { tier: tier, tier_name: made.quality_name, score: score, ceiling: c, made: Object.assign({}, made),
        count: batch, mastery: { lines: lines, total: mp, level: level, levelled: [] },
        discoveries: discoveries, next: nxt, state: state() };
    }
    function herb(id) {
      var h = HERBS[id];
      if (!h) throw Object.assign(new Error("You have not met that herb."), { status: 400 });
      return { id: id, name: h.name, kind: h.kind, part: h.part, tier: h.tier, biomes: h.biomes,
        danger_known: h.props.some(function (p) { return p.drawback && p.known; }) ? (h.danger || "it has a drawback you know of") : "",
        properties: h.props.map(function (p, i) {
          return p.known ? { key: "p" + i, known: true, text: p.text, drawback: p.drawback, how: p.how || "" }
                         : { key: "p" + i, known: false, text: null, drawback: null, how: null };
        }),
        can_study: h.props.some(function (p) { return !p.known; }), study_minutes: 10,
        can_taste: satchel.some(function (s) { return s.ingredient_id === id && !s.crafted && s.count > 0; }),
        teachers_here: id === "yarrow" || id === "comfrey" ? [{ ref: "npc3", name: "Old Marta", price: "2 sp" }] : [],
        library_here: id === "hemlock" ? { name: "Temple archive", price: "5 sp", minutes: 60 } : null };
    }
    function reveal(id, how, wantBad) {
      var h = HERBS[id], out = [];
      if (!h) return out;
      var good = h.props.filter(function (p) { return !p.known && !p.drawback; })[0];
      var bad = wantBad ? h.props.filter(function (p) { return !p.known && p.drawback; })[0] : null;
      [good, bad].forEach(function (p) {
        if (!p) return;
        p.known = true; p.how = how + ", day " + Math.floor(minute / 1440);
        out.push({ key: "p" + h.props.indexOf(p), known: true, text: p.text, drawback: p.drawback, how: p.how });
      });
      satchel.forEach(function (s) { if (!s.crafted) s.unknown = unknownOf(s.ingredient_id); });
      return out;
    }
    function handle(path, body) {
      var answer = function () {
        if (mode === "error" && path === "/api/bench/state") {
          throw Object.assign(new Error("not built yet: docs/herbalism-contracts.md §3.1"), { status: 501 });
        }
        if (path === "/api/bench/state") return state();
        if (path === "/api/bench/check") return check(body);
        if (path === "/api/bench/roll") return roll(body);
        if (path === "/api/bench/finish") return finish(body);
        if (path === "/api/bench/perks") {
          (body.picks || []).forEach(function (k) { perks[k] = (perks[k] || 0) + 1; });
          return track();
        }
        if (path === "/api/bench/recipe") {
          if (body["delete"]) recipes = recipes.filter(function (r) { return r.id !== body["delete"]; });
          else recipes.push({ id: "r" + (++serial), name: body.name, steps: body.steps });
          return { recipes: recipes.slice() };
        }
        if (path === "/api/herb/study") {
          var face = body.face == null ? 1 + Math.floor(Math.random() * 20) : body.face;
          var ok = face + 5 >= 13;
          minute += 10;
          return { roll: { face: face, bonus: 5, total: face + 5, dc: 13, success: ok, margin: face + 5 - 13 },
                   revealed: ok ? reveal(body.id, "studied", false) : [], minutes: 10,
                   clock: { day: Math.floor(minute / 1440), label: label(minute) } };
        }
        if (path === "/api/herb/taste") {
          var s = satchel.filter(function (x) { return x.ingredient_id === body.id && !x.crafted && x.count > 0; })[0];
          if (s) s.count -= 1;
          minute += 1;
          return { revealed: reveal(body.id, "tasted", true), tells: ["A bitter taste spreads across your tongue."],
                   minutes: 1, down: false };
        }
        if (path === "/api/herb/ask") {
          minute += 20;
          return { revealed: reveal(body.id, "told by Old Marta", false), paid: "2 sp", minutes: 20, refused: "" };
        }
        if (path === "/api/herb/library") {
          minute += 60;
          return { revealed: reveal(body.id, "read in the Temple archive", true), paid: "5 sp", minutes: 60, refused: "" };
        }
        var m = path.match(/^\/api\/herb\/([^/]+)$/);
        if (m) return herb(decodeURIComponent(m[1]));
        throw Object.assign(new Error("The fake has no answer for " + path + "."), { status: 404 });
      };
      // A little latency, so the loading states are seen as they will be.
      return new Promise(function (done, fail) {
        setTimeout(function () {
          try { done(JSON.parse(JSON.stringify(answer()))); } catch (err) { fail(err); }
        }, path === "/api/bench/state" ? 350 : 120);
      });
    }
    return { handle: handle, demo: mode === "demo" };
  }
  // ======================================================================== end of fake
})();
