// The play table, part 55 (the leather bench: the layer, the flow, the stage column and the
// footer). Classic script; everything lives inside one IIFE and is reached through
// `window.Leather`, so no name here can shadow one of 01-54's (test_s6_panel_shell's rule
// that no top-level function is declared twice across the table's files).
//
// The design is docs/leatherworking-ui-plan.md (§5, §6, §8, §12) as the owner's answers of
// 2026-10-08 amend it (docs/leatherworking-questions.md, the last table: no vat cap, the field
// kit's small kettle; marks, held that morning and kept as planned the same day). The API is
// lane E's play/leather_views.py. FILE NUMBERS:
// the contracts named 45-48 and 50, which the enchanting circle (45-49) and the alchemy bench
// (50-54) took first, so this bench is 55 (shell), 56 (rack) and 58 (work order), with 57 left
// for lane U4's stage adapter. Lane U1 built it FLAT FIRST, the forge's and alchemy's order
// (UI plan §16): fully playable with none of the other lanes' providers, each looked up at the
// moment it is needed and guarded there (contracts §11.1):
//   window.TanneryStage   lane U4's hide on the beam (57-leather-stage.js); without it, or
//                         without WebGL (`available()` false), the method's engraved icon on
//                         the ground with a CSS band gauge beside it, the server's band
//   BenchGameDefs[method] with track "leather"   lane U3's games, given `opts.band`; without
//                         one the step finishes at the middle of the range, said in words
//   window.MaterialLedger lane U5's card and journal; without it the rack's "?" opens a flat
//                         card (what is known, Grade, Ask a tanner) and the footer's Ledger a
//                         flat list, so Grade is never out of reach
//   Sound                 lane U6's `leather.*` events; an unknown event is silent
//
// THE FLOW (UI plan §5, §6). A method is picked; the server says, for every rack row and
// every slot, whether it fits and why not (`check.fits`); rows go into the work order's slots
// by click, Enter or drag; the pattern is picked from the server's list at Cut, never typed;
// Roll Craft throws the table's own d20 (29's `rollD20`); a success is followed by the game
// and a finish, which names the tier; a tannage that waits goes In progress (37), and Wait
// for it passes the days through the server's one clock door and collects. Grade is one
// request with no game, as the forge's assay.
//
// THE PAGE NEVER COMPUTES A NUMBER (UI plan §12). The DC and its terms, the face needed, the
// hide units, grades and caps, the clock, the wait, the rents, the band and the build card are
// the server's. What this file decides is only where a click puts a thing. A HIDDEN SECRET
// NEVER REACHES THE PAGE through this file: an ungraded hide's properties are a count here,
// never a name, and the build card's "from the creature" lines are not drawn (lane E sends
// them; the lead is told).
//
// MOTION. Nothing loops: no setInterval and no requestAnimationFrame in any file of this lane
// (tests/test_leather_ui.py greps for both); an idle bench draws no frames.

(function () {
  "use strict";

  var C = window.BenchCore;
  var $id = function (id) { return document.getElementById(id); };
  var layer = $id("leather");
  if (!C || !layer) return;
  var esc = C.esc;

  // --- vocabulary -----------------------------------------------------------------------------
  // The methods, their order, names and locks are the server's (`state.methods`). What is here
  // is copy: the flat stand-in's name for each tool, the empty rack's verb, the gauge's caption
  // and the band's unit. Keys 1 to 9, 0, minus and equals pick the twelve (UI plan §6.1).
  var KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "="];
  var TOOL = { flense: "the beam", salt: "the salt", tan: "the vat", curry: "the currier's table",
               cut: "the round knife", stitch: "the awl and needles", harden: "the kettle",
               tool: "the stamps", dye: "the dye pot", laminate: "the glue and press",
               assemble: "the bench", grade: "a scrap" };
  var DONE = { flense: "fleshed", salt: "salted", tan: "tanned", curry: "curried", cut: "cut",
               stitch: "stitched", harden: "hardened", tool: "tooled", dye: "dyed",
               laminate: "laminated", assemble: "assembled", grade: "graded" };
  // What the flat gauge measures, in the craft's words (UI plan §6.4 and §9: the real variable).
  var GAUGE = { flense: "Scraping depth", salt: "Salt worked to the edges", tan: "Liquor strength",
                curry: "Fat worked in", cut: "Off the line", stitch: "Stitch pitch",
                harden: "Water heat", tool: "Time since wetting", dye: "Dye taken",
                laminate: "Glue spread", assemble: "Seated" };
  var UNIT = { fraction: "", strength: "", percent: "%", celsius: " °C", spi: " stitches an inch",
               minutes: " minutes" };
  var SINGLE = { grade: 1 };
  var RIMS = { common: "r0", uncommon: "r1", rare: "r2", exotic: "r3", legendary: "r4" };

  var L = window.Leather = {
    esc: esc, TOOL: TOOL, DONE: DONE, KEYS: KEYS, SINGLE: SINGLE,
    state: null,          // the last /api/leather/state body
    check: null,          // the last /api/leather/check answer for the order below
    // The work order: the method, the rack key in each slot, the pattern and part at Cut, the
    // hair at Tan ("" is the hide's own way), the ambition at Assemble, the batch, and Grade's
    // one material.
    order: null,
    busy: false, live: null, result: null, loading: false, error: "",
    slotHint: null, dragKey: null, landed: null,
    card: null,           // the material card of what Grade has picked (GET material/<id>)
  };
  function blank(method) {
    return { method: method || null, slots: {}, product: "", part: "body", hair: "", batch: 1,
             masterwork: true, grade: "" };
  }
  L.order = blank(null);
  var subs = {};
  L.on = function (ev, fn) { (subs[ev] = subs[ev] || []).push(fn); };
  L.emit = function (ev, data) {
    (subs[ev] || []).forEach(function (fn) {
      try { fn(data); } catch (err) { console.error("leather " + ev + " handler failed:", err); }
    });
  };
  L.api = C.api; L.minutes = C.minutes; L.sign = C.sign; L.sound = C.sound;
  L.reduced = C.reduced; L.steady = C.steady;
  L.cssEsc = function (s) { return window.CSS && CSS.escape ? CSS.escape(s) : String(s).replace(/"/g, '\\"'); };
  function remember(key, value) { try { window.localStorage.setItem(key, value); } catch (err) { /* */ } }
  function recall(key) { try { return window.localStorage.getItem(key); } catch (err) { return null; } }

  // --- icons (UI plan §4) -----------------------------------------------------------------------
  // The bench's engraved icons from game-icons.net (CC BY 3.0, docs/asset-licences.md), drawn
  // as every bench's are: a gilt mask over the brass grain (bench.css `.bicon.is-mask`). The
  // stamped URLs are the table's `window.LEATHER_ICON_URLS`, a registry of this bench's own
  // named by file; a name it has no file for is asked of the forge's registry and the herb
  // bench's (BenchIcons: plate, grip, rivets, treatment and shield are the forge's; bark, oil,
  // wax and scale the herb bench's), and a name none knows is the lettered roundel.
  var ICON_OF = { tool: "stamp", assemble: "leather-armour", leather: "hide" };
  var ABBR = { flense: "Fl", salt: "Sa", tan: "Ta", curry: "Cu", cut: "Ct", stitch: "St",
               harden: "Ha", tool: "To", dye: "Dy", laminate: "La", assemble: "As", grade: "Gr" };
  function leatherUrl(name) {
    var map = window.LEATHER_ICON_URLS;
    var u = map && typeof map === "object" ? map[name] : "";
    return typeof u === "string" && u.indexOf("?v=") > 0 ? u : "";
  }
  function forgeUrl(name) {
    var map = window.FORGE_ICON_URLS;
    var u = map && typeof map === "object" ? map[name] : "";
    return typeof u === "string" && u.indexOf("?v=") > 0 ? u : "";
  }
  L.icon = function (name, opts) {
    opts = opts || {};
    var key = leatherUrl(name) ? name : (ICON_OF[name] || name);
    var url = leatherUrl(key);
    var el;
    if (!url && window.BenchIcons && (BenchIcons.has(key) || forgeUrl(key))) {
      el = BenchIcons.el(key, opts);
    } else {
      el = document.createElement("span");
      el.className = "bicon" + (opts.tier && RIMS[opts.tier] ? " " + RIMS[opts.tier] : "");
      el.setAttribute("aria-hidden", "true");
      el.dataset.icon = key;
      if (opts.size) el.style.setProperty("--bi", Math.round(opts.size) + "px");
      if (url) {
        el.classList.add("is-mask");
        el.style.setProperty("--bi-mask", 'url("' + url.replace(/"/g, "%22") + '")');
      }
      var letter = document.createElement("span");
      letter.className = "bicon-l";
      letter.textContent = ABBR[name] || String(opts.label || name || "?").charAt(0).toUpperCase();
      if (ABBR[name]) letter.classList.add("is-two");
      el.appendChild(letter);
    }
    return el;
  };
  L.iconHtml = function (name, opts) { return L.icon(name, opts).outerHTML; };
  // The perk picker (36) and In progress (37, a tannage's row carries `icon: "leather"`) ask
  // BenchIcons for this craft's names, which its pinned herb registry does not hold: it is
  // taught them here, for a name it has no art for and this bench has, as 40 and 50 did.
  if (window.BenchIcons && !BenchIcons.leatherNames) {
    var before = BenchIcons.el;
    BenchIcons.el = function (name, opts) {
      var mine = leatherUrl(name) || (name === "leather" && leatherUrl("hide"));
      return mine && !BenchIcons.has(name) ? L.icon(name, opts) : before(name, opts);
    };
    BenchIcons.html = function (name, opts) { return BenchIcons.el(name, opts).outerHTML; };
    BenchIcons.leatherNames = true;
  }
  // The icon for a rack row: its form, and for a finished thing its gear or pattern. Words
  // only pick a picture; the name beside it carries the meaning.
  var FORM_ICON = { green: "hide", salted: "hide", pelt: "hide", scrap: "hide", leather: "leather-roll",
                    fur: "leather-roll", rawhide: "leather-roll", panel: "panel", plate: "plate",
                    lacing: "lacing", grip: "grip", scales: "scale", salt: "salt", tannin: "bark",
                    oil: "oil", wax: "wax", thread: "thread", dye: "dye-pot", treatment: "treatment",
                    fitting: "rivets", old: "leather-armour" };
  L.rowIcon = function (it) {
    var f = it.form || it.kind || "";
    if (f === "item") {
      var rec = it.record || {};
      if (rec.gear === "shield") return "shield";
      if (rec.product === "cloak") return "cloak";
      if (rec.product === "boots") return "boots";
      return "leather-armour";
    }
    return FORM_ICON[f] || FORM_ICON[it.kind] || "hide";
  };

  // --- lookups ----------------------------------------------------------------------------------
  L.item = function (key) {
    var r = L.state && L.state.rack;
    if (!r || !key) return null;
    for (var i = 0; i < r.length; i++) if (r[i].key === key) return r[i];
    return null;
  };
  L.methodInfo = function (id) {
    var list = (L.state && L.state.methods) || [];
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
    return null;
  };
  L.product = function (id) {
    var list = (L.state && L.state.products) || [];
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
    return null;
  };
  // The slots the work order shows now: the check's own once it has answered, else the
  // state's for the method.
  L.slots = function () {
    var m = L.order.method;
    if (!m || SINGLE[m]) return [];
    if (L.check && L.check.slots && L.check.slots.length) return L.check.slots;
    return ((L.state && L.state.slots) || {})[m] || [];
  };
  // Why this rack key cannot go in this slot, in the server's words; "" when it fits; null
  // while the server has not answered for this method.
  L.fit = function (slot, key) {
    var f = L.check && L.check.fits;
    if (!f || !f[slot]) return null;
    var why = f[slot][key];
    return typeof why === "string" ? why : null;
  };
  // Why a row cannot be used for the method at all, or "" when some slot takes it.
  L.why = function (key) {
    if (L.order.method === "grade") {
      var it = L.item(key);
      return it && it.material && it.form !== "item" && !it.old ? "" : "only a material can be graded, not finished work";
    }
    var f = L.check && L.check.fits;
    if (!f) return "";
    var first = "";
    for (var slot in f) {
      if (!Object.prototype.hasOwnProperty.call(f, slot)) continue;
      var w = f[slot][key];
      if (w === "") return "";
      if (typeof w === "string" && !first) first = w;
    }
    return first;
  };
  // How many of this rack entry the order holds (a slot holds one).
  L.inOrder = function (key) {
    var n = 0, o = L.order;
    Object.keys(o.slots).forEach(function (s) { if (o.slots[s] === key) n += 1; });
    return n;
  };
  L.tannery = function () { var w = L.state && L.state.where; return w && w.tannery ? w.tannery : null; };
  // The one reason every method is locked for, or "" (no kit and no tannery locks all twelve).
  L.sharedLock = function () {
    var list = (L.state && L.state.methods) || [];
    if (!list.length) return "";
    var first = list[0].lock_reason || "";
    return first && list.every(function (m) { return m.locked && m.lock_reason === first; }) ? first : "";
  };

  // --- the stage, optional (contracts §11.1) ------------------------------------------------------
  L.stage = function () {
    var s = window.TanneryStage;
    try { return s && typeof s.available === "function" && s.available() ? s : null; }
    catch (err) { return null; }
  };
  var stageMounted = false, stageMounting = null;
  function stageCall(name, arg, more) {
    var st = L.stage();
    if (!st || !stageMounted || typeof st[name] !== "function") return undefined;
    try { return st[name](arg, more); } catch (err) { return undefined; }
  }
  L.stageCall = stageCall;

  // --- the layer, mounted on the core ---------------------------------------------------------
  var core = C.mount({
    layer: "leather", close: "leather-close", stage: "leather-stage", say: "leather-say",
    pops: "leather-pops", foot: "leather-foot", footIn: "leather-foot-in", home: "open-leather",
    clockId: "leather-clock", hash: "#leather", bodyClass: "leather-on",
    openWith: "[data-leather-open]",
    first: ".bm[aria-checked='true']",
    quiet: ".bm, .lr-add, #leather-roll",
    live: function () { return !!L.live; },
    keys: function (e) {
      var i = KEYS.indexOf(e.key);
      if (i < 0 || e.ctrlKey || e.metaKey || e.altKey) return;
      var list = (L.state && L.state.methods) || [];
      if (!list[i]) return;
      e.preventDefault();
      L.setMethod(list[i].id, { focus: true });
    },
    opened: function () {
      L.sound("leather.open");
      L.emit("open");
      core.focusFirst();
      load();
    },
    closing: function () {
      stopAmbience();
      var st = L.stage();
      if (st && stageMounted) { try { st.unmount(); } catch (err) { /* */ } }
      stageMounted = false;
      var host = $id("leather-tool");
      if (host) { host.classList.remove("has-stage"); host.dataset.tool = ""; host.innerHTML = ""; }
      L.emit("close");
    },
    footer: function () { return footParts(); },
  });
  Object.defineProperty(L, "open", { enumerable: true, get: function () { return core.open; } });
  L.openBench = core.openLayer;
  L.closeBench = core.closeLayer;
  L.pushEsc = core.pushEsc;
  L.dropEsc = core.dropEsc;
  L.confirm = core.confirm;
  L.say = core.say;
  L.refocus = core.refocus;

  // /play/#leather (the old /craft/ tab's card, lane U7) opens it on load.
  function fromHash() { if (location.hash === "#leather" && !L.open) L.openBench($id("open-leather")); }
  window.addEventListener("hashchange", fromHash);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fromHash);
  else setTimeout(fromHash, 0);

  // In progress's door (37) goes after the last craft door it knows, and 50 moves it after
  // Alchemy; it follows Leatherwork now, the last craft door (UI plan §5.1), so the left column
  // reads Herbalism, Smithing, Enchanting, Alchemy, Leatherwork, In progress. Moved once, here,
  // as this script runs after 37 has made the door and 50 has moved it.
  (function placeWorksDoor() {
    var mine = $id("open-leather"), works = $id("open-works");
    if (mine && works && mine.parentNode === works.parentNode &&
        (mine.compareDocumentPosition(works) & Node.DOCUMENT_POSITION_PRECEDING)) {
      mine.parentNode.insertBefore(works, mine.nextSibling);
    }
  })();

  // The perk picker (36) knows the herbalist's, smith's, enchanter's and alchemist's perks;
  // the leatherworker's four are the forge's with Yield moved to the harvest (owner Q6.3). The
  // words carry no number: lane E's `perk_info[id].next` says each next pick with its sizes.
  if (window.BenchPerks && BenchPerks.tracks && !BenchPerks.tracks.leatherworker) {
    BenchPerks.tracks.leatherworker = {
      prefix: "leather", title: "Leatherworker", route: "/api/leather/perks",
      perks: [
        { id: "potency", name: "Potency", words: "The bonuses of everything you make are stronger." },
        { id: "hardening", name: "Hardening", words: "The drawbacks of everything you make are softer." },
        { id: "quality", name: "Quality", words: "Your ceiling rises one rung." },
        { id: "yield", name: "Extra yield", words: "A chance of more hide from each carcass you skin." },
      ],
      icon: { potency: "leather-armour", hardening: "harden", quality: "stamp", yield: "hide" },
    };
  }

  // --- loading --------------------------------------------------------------------------------
  var checkSeq = 0;
  function load() {
    L.loading = true; L.error = ""; L.result = null; L.check = null;
    L.emit("loading");
    renderStage();
    return L.api("/api/leather/state").then(function (s) {
      L.loading = false;
      adopt(s);
      var last = recall("pgm.leather.method");
      var m = L.methodInfo(last);
      if (!m || m.locked) {
        var open = (s.methods || []).filter(function (x) { return !x.locked; });
        last = open[0] ? open[0].id : (s.methods && s.methods[0] ? s.methods[0].id : null);
      }
      L.order = blank(null);
      if (last) L.setMethod(last, { quiet: true, force: true });
      var at = document.activeElement;
      if (!at || at === document.body || at.id === "leather-close") core.focusFirst();
      mountStage();
    }).catch(function (err) {
      L.loading = false;
      L.error = err.message || String(err);
      L.emit("error", L.error);
      renderStage();
    });
  }
  L.reload = load;

  function adopt(s) {
    L.state = s;
    // A slot holding something no longer carried is emptied: the rack is the server's, and an
    // order that disagrees with it is a roll the server would refuse.
    var o = L.order;
    Object.keys(o.slots).forEach(function (slot) {
      var it = L.item(o.slots[slot]);
      if (!it || it.count <= 0) delete o.slots[slot];
    });
    if (o.grade && !(s.rack || []).some(function (r) { return r.material === o.grade; })) o.grade = "";
    L.emit("state", s);
    syncWorks();
    renderFoot();
    stageScene();
    ambience();
  }
  L.adopt = adopt;

  // --- old leatherwork, converted (lanes I and W, owner Q9.1 "Convert") ---------------------
  // The first time the bench opens after the revamp, a notice says what the conversion did, in
  // the server's words (`state.conversions`: the leatherworker's own entry, then each old suit
  // re-derived as a forge-shape record with its "Now ..." lines). "Got it" marks each seen
  // (POST api/leather/seen), so it is shown once. Alchemy's notice is the pattern
  // (50-alchemy-shell.js `showConversions`); nothing here is decided by the page.
  var noticeUp = false;
  function lineList(x) {
    if (typeof x === "string") return [x];
    return [].concat(x.changes || [], x.lines || [], x.words ? [x.words] : []).map(String);
  }
  function showConversions() {
    var list = ((L.state && L.state.conversions) || []).filter(function (x) { return x && !x.seen; });
    if (!list.length || noticeUp) return;
    noticeUp = true;
    var pops = $id("leather-pops");
    var back = document.activeElement;
    var wrap = document.createElement("div");
    wrap.className = "bench-modal lw-convert";
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-modal", "true");
    wrap.setAttribute("aria-labelledby", "lw-convert-t");
    wrap.innerHTML = '<div class="bench-scrim"></div><div class="bench-dialog v2-framed v2-card-leather lw-book-d">' +
      '<i class="v2-rim" aria-hidden="true"></i>' +
      '<h3 id="lw-convert-t">Your leatherwork, brought over</h3>' +
      '<p>Leatherwork is worked one step at a time at this bench now. What changed:</p>' +
      '<ul class="lw-book-list lw-convert-list">' + list.map(function (x) {
        var title = typeof x === "string" ? "" : (x.name || x.title || "");
        return '<li>' + (title ? '<b>' + esc(title) + '</b>' : "") +
          lineList(x).map(function (l) { return '<span>' + esc(l) + '</span>'; }).join("") + '</li>';
      }).join("") + '</ul>' +
      '<div class="bench-dialog-acts"><button type="button" class="v2-btn is-go" data-convert-ok>Got it</button></div></div>';
    pops.appendChild(wrap);
    var close = function () {
      core.dropEsc(close);
      wrap.remove();
      noticeUp = false;
      list.forEach(function (x) {
        if (x && x.key) L.api("/api/leather/seen", { key: x.key }).catch(function () { /* shown again next time */ });
      });
      if (L.state) L.state.conversions = [];
      if (!back || !document.contains(back) || back === document.body || back.id === "leather-close") core.focusFirst();
      else if (back.focus) back.focus();
    };
    core.pushEsc(close);
    wrap.querySelector("[data-convert-ok]").addEventListener("click", close);
    wrap.querySelector("[data-convert-ok]").focus();
  }
  L.showConversions = showConversions;
  L.on("state", function () { if (L.open) showConversions(); });

  L.refresh = function () {
    return L.api("/api/leather/state").then(function (s) { adopt(s); return L.runCheck(); })
      .catch(function (err) { L.say(err.message); });
  };

  // The yard's sound while the bench is open (UI plan §11): `ambience.tannery` at a tannery,
  // else the biome's own ground at the field kit. Sound answers an unknown name with silence.
  var bed = null, bedName = "";
  function stopAmbience() {
    if (bed) { try { bed.stop(); } catch (err) { /* */ } }
    bed = null; bedName = "";
  }
  function ambience() {
    var w = L.state && L.state.where;
    var name = core.open && w ? (w.tannery ? "tannery" : String(w.biome || "")) : "";
    if (name === bedName) return;
    stopAmbience();
    if (!name || !window.Sound || typeof Sound.loop !== "function") return;
    try { bed = Sound.loop("ambience." + name) || null; } catch (err) { bed = null; }
    bedName = bed ? name : "";
  }

  // In progress (37) asks for its rows again when the bench's clock or its own count moved,
  // so a tannage's countdown in the rack's group moves on game time.
  function syncWorks() {
    var W = window.Works, s = L.state;
    if (!W || typeof W.sync !== "function" || !s) return;
    W.sync("leather|" + (s.clock ? s.clock.minute : "") + "|" + ((s.works || []).length));
  }

  // --- the method ------------------------------------------------------------------------------
  L.setMethod = function (id, opts) {
    opts = opts || {};
    if (L.busy || L.live) return null;
    var info = L.methodInfo(id);
    if (!info) return null;
    if (info.locked) {
      L.say(info.name + " is locked. " + (info.lock_reason || ""));
      L.emit("refused", { method: id, why: info.lock_reason });
      return null;
    }
    var changed = L.order.method !== id;
    if (!changed && !opts.force) {
      if (opts.focus) focusMethod(id);
      return L.runCheck();
    }
    if (changed) {
      L.order = blank(id);
      L.slotHint = null;
      L.card = null;
    }
    if (!opts.keepResult) L.result = null;
    remember("pgm.leather.method", id);
    if (changed && !opts.quiet) L.sound("leather.method." + id);
    L.check = null;
    L.emit("method", id);
    stageCall("setTool", id);
    stageWork();
    renderStage();
    if (opts.focus) focusMethod(id);
    return L.runCheck();
  };
  function focusMethod(id) {
    var btn = layer.querySelector('.bm[data-method="' + id + '"]');
    if (btn) btn.focus();
  }

  // --- the body the server is asked about ---------------------------------------------------------
  // Only what the method takes: a pattern sent to Flense would be a question about a step the
  // player is not taking. Tan's hair is sent only when the player chose one (empty is not the
  // same as absent: absent is the hide's own way, fur for a pelt, leather for a smooth hide).
  L.body = function (extra) {
    var o = L.order, m = o.method, slots = {};
    Object.keys(o.slots).forEach(function (s) { slots[s] = o.slots[s]; });
    var body = { method: m, slots: slots, batch: o.batch };
    if (m === "cut") { body.product = o.product || ""; body.part = o.part || "body"; }
    if (m === "assemble") body.masterwork = !!o.masterwork;
    if (m === "tan" && o.hair) body.hair = o.hair;
    if (extra) Object.keys(extra).forEach(function (k) { body[k] = extra[k]; });
    return body;
  };

  // --- putting a rack row on the work ------------------------------------------------------------
  // Into `slot` when given (a drop on a slot, or Enter after pressing an empty slot), else the
  // first empty slot the server said it fits, else the first slot it fits. At Grade, the row's
  // material is the one to grade.
  L.addItem = function (key, slot) {
    var o = L.order;
    if (L.busy || L.live || !o.method) return false;
    var it = L.item(key);
    if (!it) return false;
    if (o.method === "grade") {
      var no = L.why(key);
      if (no) return refuse(it, no);
      o.grade = it.material;
      L.say(it.name + " is ready to grade.");
      L.emit("grade", it);
      return changed(it);
    }
    if (!L.check || !L.check.fits) {
      L.say("One moment: the bench is still reading what fits.");
      return false;
    }
    var left = it.count - L.inOrder(key);
    var target = slot || L.slotHint || pick(key, L.slots());
    if (target && L.fit(target, key)) return refuse(it, L.fit(target, key));
    if (!target) return refuse(it, L.why(key) || "it does not go in any slot here");
    if (o.slots[target] === key) { L.say(it.name + " is in the " + label(target) + " slot already."); return false; }
    if (left <= 0) { L.say("All your " + it.name + " is on the work already."); return false; }
    o.slots[target] = key;
    L.slotHint = null;
    L.say(it.name + " in the " + label(target) + " slot.");
    return changed(it);
  };
  function pick(key, slots) {
    var o = L.order, fits = slots.filter(function (s) { return L.fit(s.id, key) === ""; });
    var empty = fits.filter(function (s) { return !o.slots[s.id]; })[0];
    return empty ? empty.id : (fits[0] ? fits[0].id : null);
  }
  function label(slot) {
    var all = L.slots();
    for (var i = 0; i < all.length; i++) if (all[i].id === slot) return all[i].label.toLowerCase();
    return slot;
  }
  L.label = label;
  function refuse(it, why) {
    L.say(it.name + ": " + why);
    L.emit("refused", { key: it.key, why: why });
    return false;
  }
  function changed(it) {
    L.result = null;
    if (it && !(L.stage() && stageMounted)) L.sound("leather.drop." + (it.form || "hide"));
    L.emit("order");
    stageWork();
    renderStage();
    L.runCheck();
    return true;
  }
  L.removeSlot = function (slot) {
    if (L.busy || L.live || !L.order.slots[slot]) return;
    var it = L.item(L.order.slots[slot]);
    delete L.order.slots[slot];
    if (it) L.say(it.name + " taken off the " + label(slot) + " slot.");
    changed(null);
  };
  L.removeGrade = function () {
    if (L.busy || L.live || !L.order.grade) return;
    L.order.grade = "";
    L.card = null;
    changed(null);
  };
  // The work order's own controls (58): the pattern and part at Cut, the hair at Tan, the
  // ambition at Assemble, the batch. Each is the player's choice; what it comes to is asked of
  // the server again.
  L.set = function (field, value) {
    if (L.busy || L.live) return;
    var o = L.order;
    if (field === "product") { o.product = String(value || ""); if (!hasLining(o.product)) o.part = "body"; }
    else if (field === "part") o.part = value === "lining" ? "lining" : "body";
    else if (field === "hair") o.hair = value === "on" || value === "off" ? value : "";
    else if (field === "masterwork") o.masterwork = !!value;
    else if (field === "batch") {
      var n = Math.max(1, Math.round(Number(value) || 1));
      if (n === o.batch) return;
      o.batch = n;
    }
    L.result = null;
    L.emit("order");
    renderStage();
    L.runCheck();
  };
  function hasLining(pid) { var p = L.product(pid); return !!(p && p.lining_units); }
  L.hasLining = hasLining;

  // Ask the server what fits and what the work makes. The newest question wins: an answer to an
  // older order is dropped rather than drawn over a newer one.
  L.runCheck = function () {
    var m = L.order.method;
    if (!m || !L.state) return Promise.resolve(null);
    if (SINGLE[m]) {
      L.check = null;
      L.emit("check", null);
      renderStage();
      return Promise.resolve(null);
    }
    var seq = ++checkSeq;
    L.emit("checking");
    return L.api("/api/leather/check", L.body()).then(function (c) {
      if (seq !== checkSeq) return null;
      L.check = c;
      // The slots follow what is being made (boots have no Fastenings): a piece left in a
      // slot the product does not have comes off, said, and the server is asked again, so
      // nothing sits on the order where no slot shows it.
      if (c && c.slots && c.slots.length) {
        var have = {}, gone = [];
        c.slots.forEach(function (s) { have[s.id] = true; });
        Object.keys(L.order.slots).forEach(function (s) {
          if (have[s]) return;
          var it = L.item(L.order.slots[s]);
          delete L.order.slots[s];
          if (it) gone.push(it.name);
        });
        if (gone.length) {
          L.say(gone.join(", ") + " came off the bench: what you are making has no slot for it.");
          L.emit("order");
          return L.runCheck();
        }
      }
      L.emit("check", c);
      stageWork();
      renderStage();
      return c;
    }).catch(function (err) {
      if (seq !== checkSeq) return null;
      // The rack moved under the order (a 409): read it again, the order trims itself.
      if (err.status === 409) { L.refresh(); return null; }
      L.check = { fits: (L.check && L.check.fits) || {}, problems: [err.message], can_roll: false };
      L.emit("check", L.check);
      renderStage();
      return null;
    });
  };

  // --- the stage column (UI plan §6.3) -------------------------------------------------------------
  function mountStage() {
    var st = L.stage();
    var host = $id("leather-tool");
    if (!st || !host || stageMounted || stageMounting) return;
    host.innerHTML = "";
    host.dataset.tool = "";
    host.classList.add("has-stage");
    try {
      stageMounting = Promise.resolve(st.mount(host)).then(function (ok) {
        if (ok === false) throw new Error("no stage here");
        stageMounted = true; stageMounting = null;
        try { st.reducedMotion(L.reduced()); } catch (err) { /* */ }
        stageScene();
        if (L.order.method) stageCall("setTool", L.order.method);
        stageWork();
      }).catch(function () {
        // A stage that cannot draw is the WebGL fallback's case, not an error to show.
        stageMounted = false; stageMounting = null; host.classList.remove("has-stage"); host.dataset.tool = "";
        renderStage();
      });
    } catch (err) { stageMounting = null; host.classList.remove("has-stage"); }
  }
  function stageScene() {
    var s = L.state;
    if (!s || !stageMounted) return;
    var w = s.where || {}, t = w.tannery;
    // Lane U4's grounds (UI plan §12): the field kit on the biome's ground, a town tannery's
    // yard, or a tannery of the player's own.
    stageCall("setScene", { kind: t ? (t.kind === "owned" ? "owned" : "town") : "kit",
                            biome: w.biome || "", roofed: !!t, minute: s.clock ? s.clock.minute : 720 });
  }
  // What is on the beam for the stage (UI plan §12 `setWork`, lane U4's shape): each slot,
  // by lane E's METHOD_SLOTS ids, carries its whole rack row (the stage keeps only its own
  // keys: material, colour, surface, grade, passes, form...); the product the check named, its
  // table base, the tannage of a Tan and the quality of the main piece.
  function stageWork() {
    if (!stageMounted) return;
    var o = L.order, c = L.check || {}, pieces = {};
    Object.keys(o.slots).forEach(function (slot) {
      var it = L.item(o.slots[slot]);
      if (it) pieces[slot] = it;
    });
    var p = L.product(c.product || o.product);
    var main = pieces.body || pieces.hide || pieces.piece || null;
    stageCall("setWork", { product: c.product || o.product || "", base: p ? p.base : "",
                           tannage: c.tannage || null, pieces: pieces,
                           quality_index: main && main.quality != null ? main.quality : null });
  }

  // The flat stand-in (UI plan §6.3, "WebGL fallback"): the method's engraved icon at 160px on
  // the ground, and beside it a CSS gauge of the step's real variable, the server's band (`check
  // .band`, contracts §11.1): the target outlined, the failing band hatched, where it starts
  // marked, the numbers in their unit and the caption in words. Positions are laid out by CSS
  // from the server's own numbers (`calc()` over --lo, --hi, --max); the page sums nothing. It
  // is the whole stage until lane U4's arrives.
  function gaugeHtml(m, band) {
    if (!band || !band.target || !GAUGE[m]) return "";
    var t = band.target, f = band.fail;
    var unit = UNIT[band.unit] != null ? UNIT[band.unit] : "";
    var top = f ? Math.max(t[1], f[1]) : t[1];
    if (!(top > 0)) return "";
    var say = "Aim for " + t[0] + " to " + t[1] + unit + "." + (f ? " Ruined from " + f[0] + " to " + f[1] + unit + "." : "") +
      (band.narrow ? " A rarer hide: the window is narrower." : "");
    var vars = "--max:" + top + ";--lo:" + t[0] + ";--hi:" + t[1] + ";--at:" + (band.value_start || 0) +
      (f ? ";--flo:" + f[0] + ";--fhi:" + f[1] : "");
    return '<div class="lw-gauge" role="img" aria-label="' + esc(GAUGE[m] + ". " + say) + '">' +
      '<span class="lw-gauge-cap">' + esc(GAUGE[m]) + '</span>' +
      '<span class="lw-gauge-bar" style="' + esc(vars) + '" aria-hidden="true">' +
        '<i class="lw-g-target"></i>' + (f ? '<i class="lw-g-fail"></i>' : "") + '<i class="lw-g-at"></i>' +
      '</span>' +
      '<span class="lw-gauge-words" aria-hidden="true">' + esc(say) + '</span></div>';
  }
  function drawFallbackTool() {
    var host = $id("leather-tool");
    if (!host || host.classList.contains("has-stage")) return;
    var m = L.order.method;
    var band = m && !SINGLE[m] && L.check ? L.check.band : null;
    var sig = (m || "") + "|" + (band ? JSON.stringify(band) : "");
    if (host.dataset.tool === sig) return;
    host.dataset.tool = sig;
    host.innerHTML = "";
    if (!m) return;
    var flat = document.createElement("div");
    flat.className = "bench-flat leather-flat";
    var info = L.methodInfo(m);
    var row = document.createElement("div");
    row.className = "lw-flatrow";
    row.appendChild(L.icon(m, { size: 160, label: info ? info.name : m }));
    var g = gaugeHtml(m, band);
    if (g) row.insertAdjacentHTML("beforeend", g);
    flat.appendChild(row);
    var name = document.createElement("span");
    name.className = "bench-flat-name";
    name.textContent = TOOL[m] || m;
    flat.appendChild(name);
    host.appendChild(flat);
  }

  // The info block under the stage (UI plan §6.3): the step's own line ("1 pelt. 40m. DC 10,
  // you need 7 or better."), the wait of a tannage ("Then 4 weeks in the vat at Hollin's
  // tannery. Ready day 42."), the vats it fills (shown, never a gate: no vat cap), the rent.
  function renderStage() {
    drawFallbackTool();
    var chips = $id("leather-chips"), info = $id("leather-info"), why = $id("leather-why");
    var roll = $id("leather-roll");
    if (!chips || !info || !why || !roll) return;
    var o = L.order, m = o.method, c = L.check;
    var rows = [];
    L.slots().forEach(function (s) {
      var it = o.slots[s.id] && L.item(o.slots[s.id]);
      if (it) rows.push({ it: it, x: 'data-unslot="' + esc(s.id) + '"', what: s.label });
    });
    chips.innerHTML = rows.map(function (r) {
      return '<li class="bench-chip"><i class="fr-swatch" style="--sw:' + esc(r.it.color || "") +
        '" aria-hidden="true"></i><span>' + esc(r.it.name) + '</span><button type="button" class="bench-chip-x" ' +
        r.x + ' aria-label="Take ' + esc(r.it.name) + ' off the ' + esc(String(r.what).toLowerCase()) + '">×</button></li>';
    }).join("");
    chips.hidden = !rows.length;

    var text = [], reason = "", can = false;
    if (!L.loading && !L.error && !m && L.state) {
      // Nothing is open to choose: say why once, in the place's own words.
      var lock = L.sharedLock();
      if (lock) reason = (L.state.where && L.state.where.line) || lock;
    }
    if (!L.loading && !L.error && m) {
      if (m === "grade") {
        var gc = L.card;
        reason = o.grade ? "" : "Pick a material on your rack to take a scrap of.";
        var w = (L.state && L.state.where) || {};
        if (o.grade && !w.at) reason = "You have no leatherworker's field kit with you, and there is no tannery here.";
        can = !!o.grade && !!w.at;
        if (gc && o.grade) {
          text.push("A scrap: " + gc.grade_cost + ", " + L.minutes(gc.grade_minutes) + "." +
                    (gc.grade_dc != null ? " DC " + gc.grade_dc + " to learn something new of it." : ""));
          if (gc.unknown != null) text.push(gc.unknown === 1 ? "1 of its properties is unknown." : gc.unknown + " of its properties are unknown.");
        }
      } else if (c) {
        if (c.info) text.push(c.info);
        // The info line says how long and where ("Then 2 weeks in the vat."); the day it is
        // ready is the wait's own (UI plan §6.3: "Ready Day 42").
        if (c.wait && c.wait.ready_day) text.push("Ready day " + c.wait.ready_day + ".");
        if (c.wait && c.wait.vats) text.push(c.wait.vats === 1 ? "It fills 1 vat." : "It fills " + c.wait.vats + " vats.");
        if (c.rent_cp) text.push("The yard's hours: " + c.rent_cp + " cp.");
        if (c.vat_rent_cp) text.push("The vats for the wait: " + c.vat_rent_cp + " cp, paid as the hides go in.");
        reason = (c.problems && c.problems[0]) ||
          (c.need == null && c.impossible ? "No roll can make it: " + c.impossible + "." : "");
        can = !!c.can_roll && c.need != null;
      }
    }
    info.innerHTML = text.map(function (t) { return '<span>' + esc(t) + '</span>'; }).join("");
    why.textContent = L.busy ? "" : reason;
    roll.textContent = m === "grade" ? "Grade" : "Roll Craft";
    roll.disabled = !!(L.busy || L.live || L.loading || L.error || !can);
  }
  L.renderStage = renderStage;

  layer.addEventListener("click", function (e) {
    var x = e.target.closest("#leather-chips [data-unslot]");
    if (x) { L.removeSlot(x.dataset.unslot); return; }
    if (e.target.closest("#leather-roll")) { L.roll(); }
  });

  // Dropping a rack row on the stage puts it where a click would (56 starts the drag, 58 takes
  // drops on a slot itself). Drag is never the only way: click or Enter does the same.
  var stageEl = $id("leather-stage");
  function dragging(e) {
    return L.dragKey && e.dataTransfer && Array.prototype.indexOf.call(e.dataTransfer.types || [], "text/plain") >= 0;
  }
  function dragOver(on) { var t = $id("leather-tool"); if (t) t.classList.toggle("is-dragover", on); }
  if (stageEl) {
    stageEl.addEventListener("dragover", function (e) {
      if (!dragging(e)) return;
      e.preventDefault(); e.dataTransfer.dropEffect = "copy"; dragOver(true);
    });
    stageEl.addEventListener("dragleave", function (e) { if (!stageEl.contains(e.relatedTarget)) dragOver(false); });
    stageEl.addEventListener("drop", function (e) {
      if (!dragging(e)) return;
      e.preventDefault(); dragOver(false);
      var key = L.dragKey; L.dragKey = null;
      L.addItem(key);
    });
  }
  document.addEventListener("dragend", function () { if (L.open) { dragOver(false); L.dragKey = null; } });

  // --- the roll (UI plan §6.3) ---------------------------------------------------------------------
  // The table's own d20, thrown by the core exactly as every bench throws it.
  L.roll = function () {
    var m = L.order.method;
    if (L.busy || L.live || !m) return null;
    if (m === "grade") return gradeIt();
    var c = L.check;
    if (!c || !c.can_roll || c.need == null) return null;
    L.busy = true;
    L.result = null;
    L.emit("rolling");
    renderStage();
    var info = L.methodInfo(m);
    var made = c.products && c.products[0] ? c.products[0].name : (info ? info.makes || info.name : m);
    var body = L.body();
    var order = JSON.parse(JSON.stringify(L.order));
    return C.rollD20({
      shown: { title: "Craft (leather)", why: (info ? info.name + ": " : "") + made,
               sides: 20, lo: 1, hi: 20, die: "1d20", terms: C.rollTerms(c) },
      post: function (face) {
        L.sound("leather.roll");
        body.face = face;
        return L.api("/api/leather/roll", body);
      },
      // A success is followed by the step's game: the clock face waits for it.
      landed: function (r) { tickClock(r.clock, !!(r.roll && r.roll.success && r.token)); },
      face: function (r) { return r.roll.face; },
      // A Craft check is a skill check: no natural 20 or 1 (CRB p.180), so none is passed.
      verdict: function (r) { var v = r.verdict || {}; return { verdict: v.verdict, natural: null }; },
    }).then(function (r) {
      L.busy = false;
      if (r.roll && r.roll.success && r.token) {
        return Promise.resolve(play(r, order)).then(
          function (x) { C.releaseClock(); return x; },
          function (err) { C.releaseClock(); throw err; });
      }
      return failed(r, order).then(focusAfterRoll);
    }).catch(function (err) {
      L.busy = false;
      C.releaseClock();
      C.closeMat();
      $id("leather-why").textContent = err.message || String(err);
      L.say(err.message || String(err));
      renderStage();
      focusAfterRoll();
    });
  };
  // Never <body>: Roll if it can roll again, else the rack's row, else Close.
  var FITS = L.FITS = '#leather-list .lr-add[data-add]:not([aria-disabled="true"])';
  function focusAfterRoll() {
    core.refocus(["leather-roll", FITS, "#leather-list .lr-add[tabindex='0']", "leather-close"]);
  }
  L.focusAfterRoll = focusAfterRoll;

  function tickClock(clock, hold) {
    var s = L.state;
    var before = s && s.clock && typeof s.clock.minute === "number" ? s.clock.minute : null;
    if (clock && s) s.clock = clock;
    if (before != null && clock && typeof clock.minute === "number") C.turnClock(before, clock.minute, hold);
    renderFoot();
  }
  L.tickClock = tickClock;

  // --- the failure ---------------------------------------------------------------------------------
  // The book's rule (plan §11): a miss by 4 or less loses the time; by 5 or more half of what was
  // on the bench is ruined. The words are the server's.
  function failed(r, order) {
    L.result = { failed: true, roll: r.roll, lost: r.lost || [], said: r.said || "",
                 minutes: r.minutes, mastery: r.mastery || null, method: order.method, rent: r.rent || [] };
    flourish("fail");
    L.emit("result", L.result);
    L.say(r.said || "Failure.");
    return L.refresh();
  }

  // --- the game (contracts §11.1) --------------------------------------------------------------------
  // Lane U3's game for the method, on the shared strip, when one is registered for THIS craft
  // (`track: "leather"`). BenchGameDefs is one registry keyed by method for every bench, and the
  // forge already holds "assemble": a leather game registered there would replace the smith's,
  // so lane U3 registers under "leather.<method>" (its `LeatherGames.key(method)`; the cut
  // test is `LeatherGames.cutTest`). The method's own name is accepted too, track permitting.
  L.gameKey = function (method) {
    var games = window.BenchGames, defs = window.BenchGameDefs || {};
    if (!games || typeof games.play !== "function") return null;
    var LG = window.LeatherGames;
    var keys = [];
    if (LG && method === "cut-test" && LG.cutTest) keys.push(LG.cutTest);
    if (LG && typeof LG.key === "function") keys.push(LG.key(method));
    keys.push("leather." + method, "leather-" + method, method);
    for (var i = 0; i < keys.length; i++) {
      var def = defs[keys[i]];
      if (def && def.track === "leather" && typeof def.create === "function") return keys[i];
    }
    return null;
  };
  function tierWatch(tuning) {
    var b = Array.isArray(tuning.bands) && tuning.bands.length ? tuning.bands.slice() : [0];
    var band = -1;
    return function (s) {
      var i = band < 0 ? 0 : band;
      while (i + 1 < b.length && s >= b[i + 1] + 0.015) i++;
      while (i > 0 && s < b[i] - 0.015) i--;
      var up = band >= 0 && i > band;
      band = i;
      return up;
    };
  }
  function play(r, order) {
    var tuning = r.tuning || {};
    L.live = { token: r.token, tuning: tuning, roll: r };
    var strip = $id("leather-game");
    strip.hidden = false;
    strip.innerHTML = "";
    void strip.offsetWidth;
    strip.classList.add("is-up");
    layer.classList.add("is-playing");
    L.emit("play", L.live);
    renderStage();
    var method = order.method;
    var key = L.gameKey(method);
    var game;
    if (key) {
      // The stage's view of the game (lane U4: `game(method, {band})`, whose update, hit, miss
      // and end the frame calls when they are there).
      var view = stageCall("game", method, { band: r.band || tuning.band || null }) || null;
      var rose = tierWatch(tuning);
      game = Promise.resolve(BenchGames.play({
        method: key, tuning: tuning, band: r.band || tuning.band || null,
        mount: strip, stage: view, steady: L.steady(), reducedMotion: L.reduced(),
        onScore: function (s) {
          L.emit("score", s);
          if (rose(s)) flourish("tier");
        },
      }));
    } else {
      // The leather games are lane U3's; until one is in the build for this method the step
      // still finishes, at the middle of the range, rather than holding the hides.
      L.live.flat = true;
      game = Promise.resolve({ score: 0.5, stopped: false, flat: true });
    }
    return game.then(function (out) {
      out = out || {};
      return finish(Number(out.score) || 0, !!out.stopped, !!out.flat, order);
    }, function (err) {
      // A game that throws is scored as stopped at nothing: materials are never lost to a stop.
      console.error("leather game failed:", err);
      return finish(0, true, false, order);
    });
  }

  // --- the finish and the landing ------------------------------------------------------------------
  function finish(score, stopped, flat, order) {
    var live = L.live;
    var strip = $id("leather-game");
    core.endGame();
    strip.classList.remove("is-up");
    layer.classList.remove("is-playing");
    L.busy = true;
    renderStage();
    return L.api("/api/leather/finish", { token: live.token, score: score, stopped: stopped })
      .then(function (f) {
        L.live = null;
        L.busy = false;
        strip.hidden = true;
        strip.innerHTML = "";
        var from = productRect();
        L.result = { finished: true, finish: f, stopped: stopped, flat: flat, method: order.method,
                     two_halves: !!(live.tuning && live.tuning.two_halves),
                     rent: (live.roll && live.roll.rent) || [] };
        if ((f.discoveries || []).length && window.MaterialLedger && typeof MaterialLedger.forget === "function") {
          try { MaterialLedger.forget(); } catch (err) { /* */ }
        }
        // The work order is cleared: what it made is on the rack (or In progress), and the
        // result's "Next: Flense" carries it there.
        L.order = blank(order.method);
        if (order.method === "cut") { L.order.product = order.product; L.order.part = order.part; }
        if (f.state) adopt(f.state);
        tickClock(f.state && f.state.clock);
        L.emit("result", L.result);
        land(f, from);
        stageWork();
        renderStage();
        L.runCheck();
        core.refocus(["leather-next", "leather-wait", "leather-roll", FITS, "#leather-list .lr-add[tabindex='0']"]);
      }).catch(function (err) {
        L.live = null;
        L.busy = false;
        strip.hidden = true;
        strip.innerHTML = "";
        $id("leather-why").textContent = err.message || String(err);
        renderStage();
        core.refocus(["leather-roll", "leather-close"]);
      });
  }

  function productRect() {
    var r = stageCall("productRect");
    if (r && r.width) return r;
    var tool = document.querySelector("#leather-tool .bicon") || $id("leather-tool");
    return tool ? tool.getBoundingClientRect() : null;
  }

  // The product flies to its rack row: a tannage that waits to its In progress row (37's group),
  // anything else to its row on the rack.
  function land(f, from) {
    var made = (f.products || [])[0];
    // A tannage that waits sinks into the vat (lane U4's "sink"); anything else lands.
    var sinks = made && Number(made.waits) > 0;
    flourish(f.tier_name === "Flawless" ? "flawless" : sinks ? "sink" : "land", f.tier_name);
    if ((f.discoveries || []).length) L.sound("leather.found");
    if (!made) return;
    L.say("Made " + made.name + (made.count > 1 ? ", " + made.count + " of them" : "") +
          (f.tier_name ? ", " + f.tier_name : "") + ".");
    var waits = Number(made.waits) > 0;
    var sel = waits
      ? '#leather-list .wk-row[data-works-key="' + L.cssEsc(String(made.key).replace(/^stock:/, "")) + '"]'
      : '#leather-list .lr[data-key="' + L.cssEsc(made.key) + '"]';
    var pulse = function () {
      L.landed = { key: made.key, until: Date.now() + 1400 };
      var now = document.querySelector(sel);
      if (!now) return;
      now.classList.remove("is-landed");
      void now.offsetWidth;
      now.classList.add("is-landed");
      setTimeout(function () { now.classList.remove("is-landed"); }, 1400);
    };
    var row = document.querySelector(sel);
    if (!row) { pulse(); return; }
    if (row.scrollIntoView) row.scrollIntoView({ block: "nearest" });
    var to = row.getBoundingClientRect();
    if (L.reduced() || !from || !to.width || typeof document.body.animate !== "function") { pulse(); return; }
    var el = L.icon(L.rowIcon(made), { size: 44, label: made.name });
    C.fly(el, from, to).then(pulse);
  }

  // A flourish: the stage's when it is mounted, else the flat stand-in's: the stage dims on a
  // failure and the brass word reads Flawless on the best work; the sound rings either way.
  function flourish(kind, word) {
    var st = L.stage();
    var staged = false;
    if (st && stageMounted && typeof st.flourish === "function") {
      try { st.reducedMotion(L.reduced()); st.flourish(kind); staged = true; } catch (err) { staged = false; }
    }
    if (kind === "tier") { if (!staged) L.sound("leather.tier.up"); return; }
    // Mounted, the stage rings its own flourishes (leather.tier.up, .flawless, .fail, .land,
    // .grade): rung here as well they would sound twice.
    if (!staged) {
      L.sound(kind === "fail" ? "leather.fail" : kind === "flawless" ? "leather.flawless" :
              kind === "grade" ? "leather.grade" : "leather.land");
    }
    var tool = document.querySelector("#leather-tool .leather-flat .bicon") || $id("leather-tool");
    if (kind === "fail") { if (!staged) C.dim($id("leather-stage")); return; }
    if (kind === "flawless") C.word(tool, word || "Flawless", !staged);
  }
  L.flourish = flourish;

  // --- Grade: the leather assay, one roll, no game (plan §16) ------------------------------------
  // The material's card (GET material/<id>) says what a scrap costs, how long it takes and its
  // DC; asked when a material is picked to grade, read only, so a pending step is never let go.
  L.on("grade", function (it) {
    L.card = null;
    if (!it || !it.material) return;
    L.api("/api/leather/material/" + encodeURIComponent(it.material)).then(function (card) {
      if (L.order.grade !== it.material) return;
      L.card = card;
      L.emit("card", card);
      renderStage();
    }).catch(function () { /* the grade still works; the line waits */ });
  });
  L.gradeMaterial = function (mid, from) {
    var it = ((L.state && L.state.rack) || []).filter(function (r) { return r.material === mid && r.form !== "item"; })[0];
    var go = L.order.method === "grade" ? Promise.resolve(true) : L.setMethod("grade", { focus: false });
    return Promise.resolve(go).then(function () {
      if (it) L.addItem(it.key);
      core.refocus(["leather-roll", from]);
    });
  };
  function gradeIt() {
    var mid = L.order.grade;
    if (!mid) return null;
    var it = ((L.state && L.state.rack) || []).filter(function (r) { return r.material === mid; })[0];
    var name = it ? it.name : mid;
    L.busy = true;
    renderStage();
    var g = (L.state && L.state.grade) || {};
    return C.rollD20({
      shown: { title: "Craft (leather)", why: "Grade: " + name, sides: 20, lo: 1, hi: 20, die: "1d20",
               terms: C.rollTerms({ terms: g.terms || [], dc: L.card ? L.card.grade_dc : null }) },
      post: function (face) { return L.api("/api/leather/grade", { material: mid, face: face }); },
      landed: function (r) { tickClock(r.clock); },
      face: function (r) { return r.roll.face; },
      verdict: function (r) { return { verdict: r.success === false ? "failure" : "success", natural: null }; },
    }).then(function (r) {
      L.busy = false;
      L.result = { graded: r, method: "grade" };
      flourish("grade");
      if (r.revealed && r.revealed.length) L.sound("leather.found");
      if (window.MaterialLedger && typeof MaterialLedger.forget === "function") {
        try { MaterialLedger.forget(); } catch (err) { /* */ }
      }
      L.order.grade = "";
      L.card = null;
      L.emit("result", L.result);
      L.say(r.revealed && r.revealed.length ? "You learn: " + r.revealed.map(function (x) { return x.text || x.key; }).join("; ") + "."
                                            : "Nothing new.");
      return L.refresh();
    }).then(focusAfterRoll).catch(function (err) {
      L.busy = false;
      C.closeMat();
      $id("leather-why").textContent = err.message || String(err);
      L.say(err.message || String(err));
      renderStage();
      focusAfterRoll();
    });
  }

  // --- Wait for it: a tannage in the vat or the pack, then collect (lane E's `wait`) -------------
  // The days pass through the server's one clock door (`Scene.advance`) and the work comes out.
  // The tan game's second half, the cut test (UI plan §9), is lane U3's: played here before the
  // collect when its game is in the build, and its score sent; without it the server takes the
  // setup half alone (rules/leatherworker.py `_collect`).
  // A wait of a day or more is asked first, in words: the days pass for the whole character,
  // hunger, thirst and sleep included. Seen live (2026-10-08): one press of Wait for it over a
  // three-week bark tannage passed 21 days in a breath, the scratch character died of thirst
  // in it (twice: the second time carrying forty waterskins, which a wait does not drink
  // from), and the result said only "You waited 21 days. You take the leather out". The
  // server's wait is lane E's; the lead is told. The confirm promises nothing it cannot keep.
  L.waitFor = function (key, twoHalves, minutes) {
    if (L.busy || L.live || !key) return null;
    if (Number(minutes) >= 1440 && !L.waitAsked) {
      return L.confirm({
        title: "Wait " + L.minutes(minutes) + "?",
        body: "The days pass for you too, all at once, and nothing else gets done in them.",
        warn: "Hunger, thirst and sleep run their course while you wait.",
        ok: "Wait", cancel: "Not now",
      }).then(function (yes) {
        if (!yes) return null;
        L.waitAsked = true;
        try { return L.waitFor(key, twoHalves, minutes); } finally { L.waitAsked = false; }
      });
    }
    L.busy = true;
    renderStage();
    var before = L.state && L.state.clock ? L.state.clock.minute : null;
    var cut = twoHalves ? L.gameKey("cut-test") : null;
    var scored = Promise.resolve(null);
    if (cut) {
      var strip = $id("leather-game");
      strip.hidden = false; strip.innerHTML = ""; strip.classList.add("is-up");
      L.live = { token: "", tuning: {}, cutTest: true };
      scored = Promise.resolve(BenchGames.play({ method: cut, tuning: {}, mount: strip,
                                                 steady: L.steady(), reducedMotion: L.reduced() }))
        .then(function (out) { return out ? Number(out.score) || 0 : null; }, function () { return null; })
        .then(function (s) {
          core.endGame(); L.live = null; strip.classList.remove("is-up"); strip.hidden = true; strip.innerHTML = "";
          return s;
        });
    }
    return scored.then(function (score) {
      var body = { key: key, wait: true };
      if (score != null) body.score = score;
      return L.api("/api/leather/collect", body);
    }).then(function (r) {
      L.busy = false;
      if (before != null && r.clock) C.turnClock(before, r.clock.minute);
      L.result = { collected: r, method: L.order.method };
      L.emit("result", L.result);
      L.say((r.waited ? "You wait " + L.minutes(r.waited) + ". " : "") + (r.said || ""));
      try { document.dispatchEvent(new CustomEvent("works:collected", { detail: { key: key, said: r.said } })); } catch (err) { /* */ }
      return L.refresh();
    }).then(function () {
      core.refocus(["leather-next", "leather-roll", ".bm[aria-checked='true']"]);
    }).catch(function (err) {
      L.busy = false;
      L.live = null;
      $id("leather-why").textContent = err.message || String(err);
      L.say(err.message || String(err));
      renderStage();
    });
  };

  // --- the method strip (UI plan §6.1) -------------------------------------------------------------
  // A radio group: one Tab stop, arrows move and choose, the number keys jump. Locked methods
  // stay in the row with the lock and the reason in words in the label itself: the level
  // ("Leatherworker 2") or the place ("Needs a tannery"), never in a tooltip only.
  function renderMethods() {
    var row = $id("leather-methods");
    if (!row) return;
    var list = (L.state && L.state.methods) || [];
    row.innerHTML = "";
    // A lock every method shares (no kit and no tannery) is said once, under the stage, not
    // under each of twelve names; each button's own label still carries it.
    var shared = L.sharedLock();
    list.forEach(function (m, i) {
      var on = m.id === L.order.method;
      var b = document.createElement("button");
      b.type = "button";
      b.className = "bm" + (m.locked ? " is-locked" : "");
      b.dataset.method = m.id;
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.tabIndex = on || (!L.order.method && i === 0) ? 0 : -1;
      if (m.locked) b.setAttribute("aria-disabled", "true");
      var label = m.name + (m.locked && m.lock_reason ? ", " + m.lock_reason : "");
      b.setAttribute("aria-label", label + (KEYS[i] ? ". Key " + KEYS[i] : ""));
      b.appendChild(m.locked && window.BenchIcons ? BenchIcons.el("lock", { size: 22, label: "lock" })
                                                  : L.icon(m.id, { size: 22, label: m.name }));
      var t = document.createElement("span");
      t.className = "bm-name";
      t.textContent = m.name;
      b.appendChild(t);
      if (m.locked && m.lock_reason && !shared) {
        var l = document.createElement("span");
        l.className = "bm-lock";
        l.textContent = m.lock_reason;
        b.appendChild(l);
      }
      var tip = document.createElement("span");
      tip.className = "bm-tip";
      tip.setAttribute("aria-hidden", "true");
      tip.textContent = label;
      b.appendChild(tip);
      row.appendChild(b);
    });
  }
  L.on("state", renderMethods);
  L.on("method", function () {
    var row = $id("leather-methods");
    if (!row) return;
    row.querySelectorAll(".bm").forEach(function (b) {
      var on = b.dataset.method === L.order.method;
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.tabIndex = on ? 0 : -1;
    });
  });
  var methodsEl = $id("leather-methods");
  if (methodsEl) {
    methodsEl.addEventListener("click", function (e) {
      var b = e.target.closest(".bm");
      if (b) L.setMethod(b.dataset.method, { focus: true });
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
      all[to].focus();
      var info = L.methodInfo(all[to].dataset.method);
      if (info && !info.locked) L.setMethod(info.id, { focus: true });
      else if (info) L.say(info.name + " is locked. " + (info.lock_reason || ""));
    });
  }

  // --- the footer (UI plan §5.2) -------------------------------------------------------------------
  // The core draws the frame; the bench says what is in it: the clock, where you are ("At the
  // field kit: common and uncommon hides, and its small kettle", "At Hollin's tannery, 1 sp an
  // hour, vats 2 sp a day each"), "Leatherworker" and its numbers, the Ledger, and In progress
  // (37's own button, drawn by the core).
  function footParts() {
    var s = L.state, t = s && s.track;
    return {
      clock: s && s.clock && s.clock.label ? s.clock.label : "",
      place: s && s.where && s.where.line ? s.where.line : "",
      trackLabel: "Your leatherworking",
      track: t ? { title: "Leatherworker", level: t.level, mp: t.mp,
                   need: t.to_next && t.to_next.need, have: t.to_next && t.to_next.have } : null,
      picks: t && t.picks_banked,
      buttons: ((s && s.manuals && s.manuals.length)
        ? '<button type="button" class="bf-btn" data-leather-manuals aria-haspopup="dialog">Manuals</button>' : "") +
        '<button type="button" class="bf-btn" data-leather-ledger aria-haspopup="dialog">Ledger</button>',
    };
  }
  function renderFoot() { core.renderFoot(); }
  L.renderFoot = renderFoot;
  var footEl = $id("leather-foot");
  if (footEl) {
    footEl.addEventListener("click", function (e) {
      var b = e.target.closest("[data-leather-ledger]");
      if (b) { L.ledger(b); return; }
      var mb = e.target.closest("[data-leather-manuals]");
      if (mb) { L.manuals(mb); return; }
      if (e.target.closest("[data-bench-perks]")) L.openPerks();
    });
  }

  // --- the ledger and a material's card (contracts §11.1: lane U5's `window.MaterialLedger`) ------
  // `.card(track, materialId, anchorEl)` and `.journal(host, track)` when lane U5's file is in
  // the build. Without it, flat stand-ins in the bench's own dialog, read from lane E's routes:
  // every hide met with "3 of 7 known", and a material's card with what is known and how, the
  // unknown as a count (never its group or its words), Grade and Ask a tanner.
  function modal(title, inner, from) {
    var pops = $id("leather-pops");
    var wrap = document.createElement("div");
    wrap.className = "bench-modal lw-book";
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-modal", "true");
    wrap.setAttribute("aria-labelledby", "lw-book-t");
    wrap.innerHTML = '<div class="bench-scrim"></div><div class="bench-dialog v2-framed v2-card-leather lw-book-d">' +
      '<i class="v2-rim" aria-hidden="true"></i><h3 id="lw-book-t">' + esc(title) + '</h3>' +
      '<div class="lw-book-body">' + inner + '</div>' +
      '<div class="bench-dialog-acts"><button type="button" class="v2-btn is-quiet" data-book-close>Close</button></div></div>';
    pops.appendChild(wrap);
    var close = function () {
      core.dropEsc(close);
      wrap.remove();
      if (from && document.contains(from) && from.focus) from.focus();
    };
    core.pushEsc(close);
    wrap.querySelector("[data-book-close]").addEventListener("click", close);
    wrap.querySelector(".bench-scrim").addEventListener("click", close);
    wrap.querySelector("[data-book-close]").focus();
    return { wrap: wrap, close: close };
  }
  L.ledger = function (from) {
    var M = window.MaterialLedger;
    if (M && typeof M.journal === "function") {
      // Lane U5's ledger lives in the Journal ("Tanner's ledger", #jr-hides): the bench
      // closes and the Journal opens on it, as the forge's and the herb bench's Ledger do.
      L.closeBench();
      if (L.open) return;
      if (typeof Shell === "object" && Shell && Shell.show) Shell.show("journal");
      try { document.dispatchEvent(new CustomEvent("leather:ledger")); } catch (err) { /* */ }
      setTimeout(function () {
        var at = $id("jr-hides");
        if (at && at.scrollIntoView) at.scrollIntoView({ block: "start" });
      }, 120);
      return;
    }
    L.api("/api/leather/ledger").then(function (d) {
      var rows = (d.ledger || []).map(function (r) {
        return '<li><i class="fr-swatch" style="--sw:' + esc(r.color || "") + '" aria-hidden="true"></i><b>' + esc(r.name) +
          '</b><span>' + esc(r.known + " of " + r.total + " known") + '</span></li>';
      });
      modal("Tanner's ledger", rows.length ? '<ul class="lw-book-list">' + rows.join("") + '</ul>'
                                           : "<p>No hide or tanner's store met yet.</p>", from);
    }).catch(function (err) { L.say(err.message || String(err)); });
  };
  // The manuals carried (the server's `state.manuals`), each read by one press through lane
  // E's POST api/leather/manual: the hours pass through the server's clock door and a first
  // reading pays its mastery. Nobody else's lane gave the reader a door.
  L.manuals = function (from) {
    var list = (L.state && L.state.manuals) || [];
    var rows = list.map(function (m) {
      var hrs = m.hours === 1 ? "1 hour" : m.hours + " hours";
      return '<li><b>' + esc(m.name) + '</b><span>' + esc(m.read ? "Read before. " + hrs + " again." : hrs + " to read.") +
        '</span><button type="button" class="v2-btn is-small" data-read="' + esc(m.id) + '">Read</button></li>';
    });
    var md = modal("Manuals", (rows.length ? '<ul class="lw-book-list lw-manuals">' + rows.join("") + '</ul>'
      : "<p>You carry no leatherworking manual.</p>") + '<p class="lw-card-said" role="status" aria-live="polite"></p>', from);
    md.wrap.addEventListener("click", function (e) {
      var r = e.target.closest("[data-read]");
      if (!r || r.disabled) return;
      r.disabled = true;
      L.api("/api/leather/manual", { item: r.dataset.read }).then(function (got) {
        var learned = (got.revealed || []).length;
        md.wrap.querySelector(".lw-card-said").textContent = "You read it for " + L.minutes(got.minutes) + ". " +
          (learned ? "You learn " + learned + (learned === 1 ? " thing" : " things") + " about hides and the tanner's stores." :
           "There is nothing new in it for you.");
        if (got.clock) tickClock(got.clock);
        if (learned && window.MaterialLedger && typeof MaterialLedger.forget === "function") {
          try { MaterialLedger.forget(); } catch (err) { /* */ }
        }
        L.refresh();
      }).catch(function (err) {
        r.disabled = false;
        md.wrap.querySelector(".lw-card-said").textContent = err.message || String(err);
      });
    });
  };
  L.openCard = function (mid, el) {
    var M = window.MaterialLedger;
    if (M && typeof M.card === "function") {
      // From the "?" only, pinned (lane U5's `card(track, id, anchor, opts)`); its grade and
      // lessons fire `leather:learned`, heard below.
      try { M.card("leatherworker", mid, el, { pops: $id("leather-pops") }); return; }
      catch (err) { console.error("leather card failed:", err); }
    }
    L.api("/api/leather/material/" + encodeURIComponent(mid)).then(function (c) { flatCard(c, el); })
      .catch(function (err) { L.say(err.message || String(err)); });
  };
  function flatCard(c, from) {
    var known = (c.properties || []).filter(function (p) { return p.known; });
    var unknown = c.unknown != null ? c.unknown : (c.properties || []).length - known.length;
    var lines = known.map(function (p) {
      return '<li><b>' + esc(p.text || "") + '</b>' + (p.how ? '<span>' + esc(p.how) + '</span>' : "") + '</li>';
    });
    var carried = c.carried_units ? (c.carried_units + (c.carried_units === 1 ? " unit" : " units") + " of hide carried")
      : (c.carried ? c.carried + " carried" : "");
    var tanners = (c.tanners_here || []).map(function (t) {
      return '<button type="button" class="v2-btn is-small is-quiet" data-ask="' + esc(t.ref) + '">Ask ' + esc(t.name) +
        (t.price ? ", " + esc(t.price) : "") + '</button>';
    }).join("");
    var inner = '<p class="lw-card-head"><i class="fr-swatch" style="--sw:' + esc(c.color || "") + '" aria-hidden="true"></i>' +
      esc([c.tier, c.kind].filter(Boolean).join(" ")) + (carried ? ", " + esc(carried) : "") + '</p>' +
      (c.text ? '<p>' + esc(c.text) + '</p>' : "") +
      (lines.length ? '<ul class="lw-book-list">' + lines.join("") + '</ul>' : '<p>Nothing known of it yet.</p>') +
      (unknown ? '<p class="lw-card-unknown">' + esc(unknown === 1 ? "1 property not yet known." : unknown + " properties not yet known.") + '</p>' : "") +
      '<div class="lw-card-acts">' +
        (unknown ? '<button type="button" class="v2-btn is-small" data-grade-it>Grade: ' + esc(c.grade_cost || "a scrap") +
          ', ' + esc(L.minutes(c.grade_minutes)) + '</button>' : "") + tanners + '</div>' +
      '<p class="lw-card-said" role="status" aria-live="polite"></p>';
    var m = modal(c.name || "", inner, from);
    m.wrap.addEventListener("click", function (e) {
      if (e.target.closest("[data-grade-it]")) { m.close(); L.gradeMaterial(c.id, from); return; }
      var a = e.target.closest("[data-ask]");
      if (!a || a.disabled) return;
      a.disabled = true;
      L.api("/api/leather/ask", { material: c.id, ref: a.dataset.ask }).then(function (r) {
        var said = r.refused || ("You learn: " + (r.revealed || []).map(function (x) { return x.text || x.key; }).join("; ") +
          "." + (r.paid ? " " + r.paid + " paid." : ""));
        m.wrap.querySelector(".lw-card-said").textContent = said;
        if (r.clock) tickClock(r.clock);
        L.refresh();
      }).catch(function (err) {
        a.disabled = false;
        m.wrap.querySelector(".lw-card-said").textContent = err.message || String(err);
      });
    });
  }
  // Lane U5's card fires `leather:learned` (a grade, a lesson) with the response: the rack, the
  // clock and the footer are the server's, so they are read again.
  document.addEventListener("leather:learned", function (e) {
    if (!L.open) return;
    var r = e.detail && e.detail.response;
    if (r && r.clock) tickClock(r.clock);
    L.refresh();
  });
  // Wait for it from an In progress row (37's `Works.waiters`): a tannage whose first wait was
  // cut short by an empty pack, or whose page was reloaded, had no door to wait out its days
  // (the final pass, live, 2026-10-09: fifteen days of vat left and no button). The bench's
  // own wait, opened first when it is shut, with the cut test when the work is a tannage.
  if (window.Works && window.Works.waiters) {
    window.Works.waiters.leatherworker = function (row) {
      var go = function () {
        return L.waitFor(row.key, row.doing === "tanning", row.ready_in);
      };
      if (L.open && L.state) return go();
      L.openBench($id("open-leather"));
      var tries = 0;
      (function later() {
        if (L.open && L.state && !L.loading) { go(); return; }
        if (++tries < 40) setTimeout(later, 250);
      })();
      return null;
    };
  }
  // Collect or Stop on the rack's In progress group (37): the rack is read again.
  document.addEventListener("works:collected", function () { if (L.open && !L.busy) L.refresh(); });
  document.addEventListener("works:stopped", function () { if (L.open) L.refresh(); });

  // The perk picker (36-bench-perks.js, parameterised by track; the leatherworker's row is
  // registered above).
  L.openPerks = function () {
    var t = L.state && L.state.track;
    var P = window.BenchPerks;
    if (!t || !t.picks_banked) return;
    if (!P || typeof P.open !== "function" || !(P.tracks && P.tracks.leatherworker)) {
      L.say("The perk picker is not in this build.");
      return;
    }
    P.open({
      track: "leatherworker", state: t, pops: $id("leather-pops"), esc: esc,
      pushEsc: core.pushEsc, dropEsc: core.dropEsc, sound: L.sound, api: L.api,
      home: function () {
        var foot = $id("leather-foot-in");
        return (foot && foot.querySelector("[data-bench-perks]")) || $id("leather-close");
      },
      saved: function (track, picks) {
        if (L.state) L.state.track = track;
        L.emit("state", L.state);
        renderFoot();
        L.say("Perks taken: " + picks.join(", ") + ".");
      },
      afterClose: function () { L.runCheck(); },
    });
  };

  // Buy at the market (the rack's empty state): the table's Trade tab, in place of the bench.
  L.market = function () {
    L.closeBench();
    if (L.open) return;
    if (typeof Shell === "object" && Shell && Shell.show) Shell.show("trade");
  };
})();
