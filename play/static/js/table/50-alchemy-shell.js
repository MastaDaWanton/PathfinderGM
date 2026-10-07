// The play table, part 50 (the alchemy bench: the layer, the flow, the stage column and the
// footer). Classic script; everything lives inside one IIFE and is reached through
// `window.Alchemy`, so no name here can shadow one of 01-49's (test_s6_panel_shell's rule
// that no top-level function is declared twice across the table's files).
//
// The design is docs/alchemy-ui-plan.md (§5, §6, §8, §12) as the owner's answers amend it
// (docs/alchemy-questions.md, the rounds and "Plan open points ... answered 2026-10-06").
// The API is lane F's play/alchemy_views.py with the wiring lane's additions (the field kit,
// the laboratory's rent and `where.lab_line`). Lane U1 built it FLAT FIRST, the forge's and
// the circle's order (UI plan §15): fully playable with none of the other lanes' providers,
// each looked up at the moment it is needed and guarded there (contracts §12):
//   window.AlchemyStage  lane U3's glassware (52-alchemy-stage.js); without it, or without
//                        WebGL (`available()` false), the method's engraved icon on the
//                        ground with a CSS level bar beside it in the mix's own colour
//   BenchGames + BenchGameDefs[method] with track "alchemy"   lane U2's games; without a
//                        game for the method the step finishes at the middle of the range,
//                        the forge's flat rule, and the result says so in words
//   window.AlchemyBooks  lane U4's formulary, codex and reagent card; without it the footer's
//                        Formulary and Codex open plain lists and a shelf row says how many
//                        of its properties are unknown in words
//
// THE FLOW (UI plan §5, §6). A method is picked; things from the shelf go into the step (a
// click, Enter, or a drop on the glass), each to the role the server says it fits (inputs,
// the solvent at Dissolve, the vessel at Bottle, catalysts that are never spent); the server
// is asked what that would make (`check`: the DC with every term, the face needed, the
// problems in words, the mishap and toxic lines BEFORE the roll, the possible-formulae count,
// the slots and why each trait fits); Roll Craft throws the table's own d20 (29's
// `rollD20`, the mat the player can type their own face into); a success is followed by the
// method's game and a finish. Assay, Identify and Learn are one request each with no game
// (tasting and the forge's assay have none either).
//
// THE PAGE NEVER COMPUTES A NUMBER (UI plan §12). The DC and its terms, the face needed, the
// count of formulae, the grades and caps, the mix colour and level, the rent, the ladder's
// caster levels and prices and every countdown are the server's. What this file decides is
// only where a click puts a thing. A HIDDEN SECRET NEVER REACHES THE PAGE: an experiment that
// would find an unknown formula comes back with its name and DC withheld (`match.secret`),
// and nothing here could name it.
//
// WHO DRAWS WHAT. 29 owns what every bench shares. 50 mounts the bench on it and owns the
// method strip, the stage column (the tool, the info block, the stakes, Roll), the roll, the
// game call, the finish and the footer's words. 51 draws the shelf, 53 the formula card (what
// goes in, the vessel, the formula, the count, the slots, drawbacks, the DC, the tag and the
// result). They talk through `Alchemy.on(event, fn)`.
//
// MOTION. Nothing loops: no setInterval and no requestAnimationFrame in any file of this lane
// (tests/test_alchemy_ui.py greps for both); an idle bench draws no frames.

(function () {
  "use strict";

  var C = window.BenchCore;
  var $id = function (id) { return document.getElementById(id); };
  var layer = $id("alchemy");
  if (!C || !layer) return;
  var esc = C.esc;

  // --- vocabulary -----------------------------------------------------------------------------
  // The methods, their order, names and locks are the server's (`state.methods`). What is
  // here is copy: the Roll button's words and the flat stand-in's name for each tool. Keys 1
  // to 9, then 0 and minus, pick the eleven in order (UI plan §6.1).
  var KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-"];
  var ROLL = { assay: "Assay", identify: "Identify", learn: "Learn" };
  var TOOL = { dissolve: "the flask", calcine: "the crucible", filter: "the funnel",
               distill: "the still", react: "the dropper", sublime: "the aludel",
               bottle: "the vessel", transmute: "the great work", assay: "a pinch",
               identify: "the vial in the light", learn: "the formulary" };
  // Two letters per method for a name with no art in this build (Distill and Dissolve share
  // a D); the engraved art is game-icons.net's, downloaded with the owner's approval.
  var ABBR = { dissolve: "Ds", calcine: "Ca", filter: "Fi", distill: "Di", react: "Re",
               sublime: "Su", bottle: "Bo", transmute: "Tr", assay: "As", identify: "Id",
               learn: "Le" };
  // Methods that are one request each, with no check and no game.
  var SINGLE = { assay: 1, identify: 1, learn: 1 };
  // Methods that work one input at a time: a second one takes the first one's place rather
  // than being refused by the server ("Filter one liquid at a time").
  var ONE = { filter: 1, distill: 1, sublime: 1, transmute: 1 };
  var RIMS = { common: "r0", uncommon: "r1", rare: "r2", exotic: "r3", legendary: "r4" };

  var A = window.Alchemy = {
    esc: esc, ROLL: ROLL, KEYS: KEYS, SINGLE: SINGLE,
    state: null,          // the last /api/alchemy/state body
    check: null,          // the last /api/alchemy/check answer for the order below
    // The step being built: the method; the shelf keys put in, by role; the formula at
    // Bottle ("" is Experiment), the family a vessel that bottles two is asked for, the
    // traits picked for the slots (null until the player touches one: the server's own
    // picks stand until then), Transmute's target, the batch; and the single requests'
    // one thing (the reagent to assay, the potion to identify).
    order: null,
    busy: false, live: null, result: null, loading: false, error: "",
    landed: null, dragKey: null,
  };
  function blank(method) {
    // `aim` and `strip` are what a catalyst beside the work is told: the formula orichalcum
    // steers an experiment to, the drawback a unicorn horn takes out (`check.choices`).
    return { method: method || null, inputs: [], solvent: "", vessel: "", catalysts: [],
             formula: "", as: "", picks: null, target: "", batch: 1, assay: "", item: "",
             aim: "", strip: "" };
  }
  A.order = blank(null);
  var subs = {};
  A.on = function (ev, fn) { (subs[ev] = subs[ev] || []).push(fn); };
  A.emit = function (ev, data) {
    (subs[ev] || []).forEach(function (fn) {
      try { fn(data); } catch (err) { console.error("alchemy " + ev + " handler failed:", err); }
    });
  };
  A.api = C.api; A.minutes = C.minutes; A.sign = C.sign; A.sound = C.sound;
  A.reduced = C.reduced; A.steady = C.steady;
  A.cssEsc = function (s) { return window.CSS && CSS.escape ? CSS.escape(s) : String(s).replace(/"/g, '\\"'); };
  function remember(key, value) { try { window.localStorage.setItem(key, value); } catch (err) { /* */ } }
  function recall(key) { try { return window.localStorage.getItem(key); } catch (err) { return null; } }

  // --- icons (UI plan §4) -----------------------------------------------------------------------
  // The bench's engraved icons from game-icons.net (CC BY 3.0, docs/asset-licences.md),
  // drawn as the herb and forge icons are: a gilt mask over the brass grain (bench.css
  // `.bicon.is-mask`). The stamped URLs are the table's `window.ALCHEMY_ICON_URLS`, a registry
  // of this bench's own; a name it has no file for is asked of the forge's registry and the
  // herb bench's (BenchIcons), and a name none knows is the lettered roundel.
  var ALIAS = { assay: "assay", identify: "study", learn: "recipe", alchemy: "potion",
                solution: "liquid", admixture: "liquid", filtrate: "liquid", precipitate: "calx",
                sublimate: "crystal", salt: "calx", essence: "liquid", gland: "gland",
                reagent: "reagent", volatile: "hot", setting: "steeping", oil: "oil" };
  function alchemyUrl(name) {
    var map = window.ALCHEMY_ICON_URLS;
    var u = map && typeof map === "object" ? map[name] : "";
    return typeof u === "string" && u.indexOf("?v=") > 0 ? u : "";
  }
  function forgeUrl(name) {
    var map = window.FORGE_ICON_URLS;
    var u = map && typeof map === "object" ? map[name] : "";
    return typeof u === "string" && u.indexOf("?v=") > 0 ? u : "";
  }
  A.icon = function (name, opts) {
    opts = opts || {};
    var key = alchemyUrl(name) ? name : (ALIAS[name] || name);
    var url = alchemyUrl(key);
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
  A.iconHtml = function (name, opts) { return A.icon(name, opts).outerHTML; };
  // The perk picker (36) and In progress (37, a row's `icon: "alchemy"`) ask BenchIcons for
  // this craft's names, which its pinned 46-name registry does not hold: it is taught them
  // here, for a name it has no art for and this bench has, as 40 taught it the forge's.
  if (window.BenchIcons && !BenchIcons.alchemyNames) {
    var before = BenchIcons.el;
    BenchIcons.el = function (name, opts) {
      var mine = alchemyUrl(name) || (name === "alchemy" && alchemyUrl("potion"));
      return mine && !BenchIcons.has(name) ? A.icon(name, opts) : before(name, opts);
    };
    BenchIcons.html = function (name, opts) { return BenchIcons.el(name, opts).outerHTML; };
    BenchIcons.alchemyNames = true;
  }
  // The icon for a shelf row: a word that picks a picture, never the meaning (the name
  // beside it carries that).
  A.rowIcon = function (it) {
    var g = it.group || "", k = it.kind || "", f = it.form || "", fam = it.family || "";
    var name = String(it.material || it.name || "").toLowerCase();
    if (it.work) return "setting";
    if (fam && fam !== "intermediate") return fam === "potion" ? "potion" : fam === "oil" ? "oil" : fam;
    if (f === "spirit") return "spirit";
    if (f === "calx" || f === "precipitate") return "calx";
    if (f === "sublimate") return "crystal";
    if (f) return "liquid";
    if (g === "Vessels") return /vial/.test(name) ? "vial" : /bladder|skin/.test(name) ? "bladder" : "flask";
    if (g === "Solvents") return "solvent";
    if (g === "Catalysts and apparatus") return "catalyst";
    if (g === "Hybrid herbs") return k === "fungus" ? "fungus" : k === "monster part" ? "organ" : "leaf";
    if (k === "gland") return "gland";
    if (k === "essence") return "liquid";
    if (k === "salt") return "calx";
    if (k === "treatment") return "treatment";
    if (k === "old") return "potion";
    return "reagent";
  };

  // --- lookups ----------------------------------------------------------------------------------
  A.item = function (key) {
    var s = A.state && A.state.shelf;
    if (!s || !key) return null;
    for (var i = 0; i < s.length; i++) if (s[i].key === key) return s[i];
    return null;
  };
  A.potion = function (key) {
    var p = (A.state && A.state.potions) || [];
    for (var i = 0; i < p.length; i++) if (p[i].key === key) return p[i];
    return null;
  };
  A.methodInfo = function (id) {
    var list = (A.state && A.state.methods) || [];
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
    return null;
  };
  A.checked = function (m) { return !!m && !SINGLE[m]; };
  // The roles the method takes, in the order a click tries them (the server's `fits` has a
  // map for each). A vessel goes to the vessel slot, a solvent to Dissolve's solvent, a
  // catalyst beside the work; the rest is an input.
  A.roles = function (m) {
    m = m || A.order.method;
    var f = A.check && A.check.fits;
    if (!f) return [];
    return ["vessel", "solvent", "catalysts", "inputs"].filter(function (r) { return !!f[r]; });
  };
  // Why this shelf key cannot go into the step now, in the server's words; "" when it fits
  // some role; null while the server has not answered for it.
  A.why = function (key) {
    var f = A.check && A.check.fits;
    if (!f) return null;
    var roles = A.roles(), first = null;
    for (var i = 0; i < roles.length; i++) {
      var map = f[roles[i]] || {};
      if (!(key in map)) continue;
      if (map[key] === "") return "";
      if (first === null || roles[i] === "inputs") first = map[key];
    }
    return first;
  };
  // How many of a shelf entry the step holds (the vessel and the solvent count one a unit;
  // the catalysts are never spent and are not counted against the shelf).
  A.inOrder = function (key) {
    var o = A.order, n = 0;
    o.inputs.forEach(function (k) { if (k === key) n += 1; });
    if (o.solvent === key) n += 1;
    if (o.vessel === key) n += 1;
    return n;
  };

  // --- the stage, optional (contracts §12) --------------------------------------------------------
  A.stage = function () {
    var s = window.AlchemyStage;
    try { return s && typeof s.available === "function" && s.available() ? s : null; }
    catch (err) { return null; }
  };
  var stageMounted = false, stageMounting = null;
  function stageCall(name, a, b) {
    var st = A.stage();
    if (!st || !stageMounted || typeof st[name] !== "function") return undefined;
    try { return st[name](a, b); } catch (err) { return undefined; }
  }
  A.stageCall = stageCall;

  // --- the layer, mounted on the core ---------------------------------------------------------
  var core = C.mount({
    layer: "alchemy", close: "alchemy-close", stage: "alchemy-stage", say: "alchemy-say",
    pops: "alchemy-pops", foot: "alchemy-foot", footIn: "alchemy-foot-in", home: "open-alchemy",
    clockId: "alchemy-clock", hash: "#alchemy", bodyClass: "alchemy-on",
    openWith: "[data-alchemy-open]",
    first: ".bm[aria-checked='true']",
    quiet: ".bm, .as-add, #alchemy-roll",
    live: function () { return !!A.live; },
    keys: function (e) {
      var i = KEYS.indexOf(e.key);
      if (i < 0 || e.ctrlKey || e.metaKey || e.altKey) return;
      var list = (A.state && A.state.methods) || [];
      if (!list[i]) return;
      e.preventDefault();
      A.setMethod(list[i].id, { focus: true });
    },
    opened: function () {
      A.sound("alchemy.open");
      A.emit("open");
      core.focusFirst();
      load();
    },
    closing: function () {
      stopAmbience();
      var st = A.stage();
      if (st && stageMounted) { try { st.unmount(); } catch (err) { /* */ } }
      stageMounted = false;
      var host = $id("alchemy-tool");
      if (host) { host.classList.remove("has-stage"); host.dataset.tool = ""; host.innerHTML = ""; }
      A.emit("close");
    },
    footer: function () { return footParts(); },
  });
  Object.defineProperty(A, "open", { enumerable: true, get: function () { return core.open; } });
  A.openBench = core.openLayer;
  A.closeBench = core.closeLayer;
  A.pushEsc = core.pushEsc;
  A.dropEsc = core.dropEsc;
  A.confirm = core.confirm;
  A.say = core.say;
  A.refocus = core.refocus;

  // /play/#alchemy, the old /craft/ tab's "Open the alchemy bench" (craft.html), opens it on
  // load.
  function fromHash() { if (location.hash === "#alchemy" && !A.open) A.openBench($id("open-alchemy")); }
  window.addEventListener("hashchange", fromHash);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fromHash);
  else setTimeout(fromHash, 0);

  // In progress's door (37) goes after the last craft door it knows (Herbalism, Smithing,
  // Enchanting), which put it between Enchanting and Alchemy. It follows Alchemy (UI plan
  // §5.1: "after Enchanting, before In progress"); 37 is no lane's file in this wave, so the
  // door is moved here, once, as this script runs after 37 has made it.
  (function placeWorksDoor() {
    var mine = $id("open-alchemy"), works = $id("open-works");
    if (mine && works && mine.parentNode === works.parentNode &&
        (mine.compareDocumentPosition(works) & Node.DOCUMENT_POSITION_PRECEDING)) {
      mine.parentNode.insertBefore(works, mine.nextSibling);
    }
  })();

  // --- loading --------------------------------------------------------------------------------
  var checkSeq = 0;
  function load() {
    A.loading = true; A.error = ""; A.result = null; A.check = null;
    A.emit("loading");
    renderStage();
    return A.api("/api/alchemy/state").then(function (s) {
      A.loading = false;
      adopt(s);
      var last = recall("pgm.alchemy.method");
      var m = A.methodInfo(last);
      if (!m || m.locked) {
        var open = (s.methods || []).filter(function (x) { return !x.locked; });
        last = open[0] ? open[0].id : (s.methods && s.methods[0] ? s.methods[0].id : null);
      }
      A.order = blank(null);
      if (last) A.setMethod(last, { quiet: true, force: true });
      var at = document.activeElement;
      if (!at || at === document.body || at.id === "alchemy-close") core.focusFirst();
      mountStage();
    }).catch(function (err) {
      A.loading = false;
      A.error = err.message || String(err);
      A.emit("error", A.error);
      renderStage();
    });
  }
  A.reload = load;

  function adopt(s) {
    A.state = s;
    // What the step holds that is no longer on the shelf is lifted: the shelf is the
    // server's, and a step that disagrees with it is a roll the server would refuse.
    var o = A.order;
    o.inputs = o.inputs.filter(function (k) { return !!A.item(k); });
    o.catalysts = o.catalysts.filter(function (k) { return !!A.item(k); });
    if (o.solvent && !A.item(o.solvent)) o.solvent = "";
    if (o.vessel && !A.item(o.vessel)) o.vessel = "";
    if (o.assay && !A.item(o.assay)) o.assay = "";
    if (o.item && !A.potion(o.item)) o.item = "";
    A.emit("state", s);
    syncWorks();
    renderFoot();
    stageScene();
    ambience();
  }
  A.adopt = adopt;

  // --- old alchemy, converted (lane I, owner Q10.1 "Convert") ---------------------------------
  // The first time the bench opens after the revamp, a notice says what the conversion did,
  // in the server's words (`state.conversions`): the level kept and the perk picks banked,
  // the formulae learned, the materials now known, what was kept as old work, the chains
  // that were dropped, and each converted thing's "Now called X (it was Y)". "Got it" marks
  // each seen (POST api/alchemy/seen), so it is shown once. The circle's notice is the
  // pattern (45-enchant-shell.js `showConversions`); nothing here is decided by the page.
  var noticeUp = false;
  function lineList(x) {
    if (typeof x === "string") return [x];
    return [].concat(x.changes || [], x.lines || [], x.words ? [x.words] : []).map(String);
  }
  function showConversions() {
    var list = ((A.state && A.state.conversions) || []).filter(function (x) { return x && !x.seen; });
    if (!list.length || noticeUp) return;
    noticeUp = true;
    var pops = $id("alchemy-pops");
    var back = document.activeElement;
    var wrap = document.createElement("div");
    wrap.className = "bench-modal al-convert";
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-modal", "true");
    wrap.setAttribute("aria-labelledby", "al-convert-t");
    wrap.innerHTML = '<div class="bench-scrim"></div><div class="bench-dialog v2-framed v2-card-leather al-book-d">' +
      '<i class="v2-rim" aria-hidden="true"></i>' +
      '<h3 id="al-convert-t">Your alchemy, brought over</h3>' +
      '<p>Alchemy is worked one step at a time at this bench now. What changed:</p>' +
      '<ul class="al-book-list">' + list.map(function (x) {
        var lines = lineList(x);
        var title = typeof x === "string" ? "" : (x.name || x.title || "");
        return '<li>' + (title ? '<b>' + esc(title) + '</b>' : "") +
          lines.map(function (l) { return '<span>' + esc(l) + '</span>'; }).join("") + '</li>';
      }).join("") + '</ul>' +
      '<div class="bench-dialog-acts"><button type="button" class="v2-btn is-go" data-convert-ok>Got it</button></div></div>';
    pops.appendChild(wrap);
    var close = function () {
      core.dropEsc(close);
      wrap.remove();
      noticeUp = false;
      list.forEach(function (x) {
        if (x && x.key) A.api("/api/alchemy/seen", { key: x.key }).catch(function () { /* shown again next time */ });
      });
      if (!back || !document.contains(back) || back === document.body || back.id === "alchemy-close") core.focusFirst();
      else if (back.focus) back.focus();
    };
    core.pushEsc(close);
    wrap.querySelector("[data-convert-ok]").addEventListener("click", close);
    wrap.querySelector("[data-convert-ok]").focus();
  }
  A.showConversions = showConversions;
  A.on("state", function () { if (A.open) showConversions(); });

  A.refresh = function () {
    return A.api("/api/alchemy/state").then(function (s) { adopt(s); return A.runCheck(); })
      .catch(function (err) { A.say(err.message); });
  };

  // The room's sound while the bench is open (UI plan §11): `ambience.laboratory` in a
  // laboratory, else the biome's own ground, one bed at a time. Sound answers an unknown
  // name with silence, so a bed lane U5 has not made yet costs nothing.
  var bed = null, bedName = "";
  function ambienceName() {
    var w = A.state && A.state.where;
    if (!w) return "";
    return w.lab ? "laboratory" : String(w.biome || "");
  }
  function stopAmbience() {
    if (bed) { try { bed.stop(); } catch (err) { /* */ } }
    bed = null; bedName = "";
  }
  function ambience() {
    var name = core.open ? ambienceName() : "";
    if (name === bedName) return;
    stopAmbience();
    if (!name || !window.Sound || typeof Sound.loop !== "function") return;
    try { bed = Sound.loop("ambience." + name) || null; } catch (err) { bed = null; }
    bedName = bed ? name : "";
  }

  // In progress (37-works.js) asks for its rows again when the bench's clock or its own
  // count has moved, so a setting potion's countdown in the shelf's group moves on game time
  // and a fresh one appears in it the moment Bottle finishes.
  function syncWorks() {
    var W = window.Works, s = A.state;
    if (!W || typeof W.sync !== "function" || !s) return;
    W.sync("alchemy|" + (s.clock ? s.clock.minute : "") + "|" + ((s.works || []).length));
  }

  // --- the method ------------------------------------------------------------------------------
  A.setMethod = function (id, opts) {
    opts = opts || {};
    if (A.busy || A.live) return null;
    var info = A.methodInfo(id);
    if (!info) return null;
    if (info.locked) {
      A.say(info.name + " is locked. " + (info.lock_reason || ""));
      A.emit("refused", { method: id, why: info.lock_reason });
      return null;
    }
    var changed = A.order.method !== id;
    if (!changed && !opts.force) {
      if (opts.focus) focusMethod(id);
      return A.runCheck();
    }
    if (changed) {
      A.order = blank(id);
      // "Next: Bottle" carries what was just made into the new step as its input.
      if (opts.carry && A.item(opts.carry)) A.order.inputs = [opts.carry];
    }
    if (!opts.keepResult) A.result = null;
    remember("pgm.alchemy.method", id);
    if (changed && !opts.quiet) A.sound("alchemy.method." + id);
    A.check = null;
    A.emit("method", id);
    stageCall("setTool", id);
    stageWork();
    renderStage();
    if (opts.focus) focusMethod(id);
    if (id === "learn") A.emit("learn");
    return A.runCheck();
  };
  function focusMethod(id) {
    var btn = layer.querySelector('.bm[data-method="' + id + '"]');
    if (btn) btn.focus();
  }

  // --- the body the server is asked about --------------------------------------------------------
  // Only what the method takes: a body carrying a stale vessel into Dissolve would be a
  // question about a step the player is not taking.
  A.body = function (extra) {
    var o = A.order, m = o.method, body = { method: m };
    if (!A.checked(m)) return body;
    body.inputs = o.inputs.slice();
    if (o.catalysts.length) body.catalysts = o.catalysts.slice();
    if (m === "dissolve" && o.solvent) body.solvent = o.solvent;
    if (m === "bottle") {
      if (o.vessel) body.vessel = o.vessel;
      body.formula = o.formula || "experiment";
      if (o.as) body.as = o.as;
      if (o.aim && !o.formula) body.aim = o.aim;
    }
    if (o.strip && o.catalysts.length) body.strip = o.strip;
    if (m === "transmute" && o.target) body.target = o.target;
    // Empty is not the same as absent (CLAUDE.md): an untouched slot list leaves the
    // server's own picks standing; once the player has touched one, the whole list is sent,
    // empty included, so taking every trait out really takes them out.
    if (o.picks !== null) body.picks = o.picks.slice();
    if (o.batch > 1) body.batch = o.batch;
    if (extra) Object.keys(extra).forEach(function (k) { body[k] = extra[k]; });
    return body;
  };

  // --- putting a shelf row into the step -----------------------------------------------------------
  // A click, Enter or a drop on the glass. Where it goes is decided by the roles the method
  // takes and the server's word on each (`check.fits`); whether it may go is the server's,
  // said in its words.
  A.addItem = function (key) {
    var o = A.order, m = o.method;
    if (A.busy || A.live || !m) return false;
    var it = A.item(key);
    if (!it) return false;
    if (m === "assay") {
      if (!it.material || it.family) return refuse(it, "assay takes a pinch of a raw material, not worked stock");
      o.assay = key;
      A.say(it.name + " is ready to assay.");
      A.emit("assay", it);
      return changed();
    }
    if (m === "identify" || m === "learn") {
      return refuse(it, m === "identify" ? "Identify studies a potion you carry: pick one in the card"
                                         : "Learn copies a formula from a writing: pick one in the card");
    }
    if (A.check === null) {
      A.say("One moment: the bench is still reading what fits.");
      return false;
    }
    var f = A.check.fits || {};
    var roles = A.roles();
    var role = null;
    var prefer = it.group === "Vessels" ? "vessel" : it.group === "Solvents" ? "solvent" :
                 it.group === "Catalysts and apparatus" ? "catalysts" : "inputs";
    if (f[prefer] && f[prefer][key] === "") role = prefer;
    if (!role) {
      for (var i = 0; i < roles.length; i++) {
        if ((f[roles[i]] || {})[key] === "") { role = roles[i]; break; }
      }
    }
    if (!role) return refuse(it, A.why(key) || "it does not go into this step");
    var left = (it.count || 0) - A.inOrder(key);
    if (role === "vessel") {
      if (o.vessel === key) { A.say(it.name + " is on the bench already."); return false; }
      o.vessel = key;
      A.say(it.name + ": the vessel.");
      A.sound("alchemy.drop.glass");
      return changed();
    }
    if (role === "solvent") {
      if (o.solvent === key) { A.say(it.name + " is the solvent already."); return false; }
      if (left <= 0) { A.say("All your " + it.name + " is on the bench already."); return false; }
      o.solvent = key;
      A.say(it.name + ": the solvent.");
      A.sound("alchemy.drop.liquid");
      return changed();
    }
    if (role === "catalysts") {
      if (o.catalysts.indexOf(key) >= 0) { A.say(it.name + " is beside the work already."); return false; }
      o.catalysts.push(key);
      A.say(it.name + " set beside the work. It is never spent.");
      return changed();
    }
    if (o.inputs.indexOf(key) >= 0) { A.say(it.name + " is in the step already."); return false; }
    if (left <= 0) { A.say("All your " + it.name + " is on the bench already."); return false; }
    if (ONE[m]) o.inputs = [key]; else o.inputs.push(key);
    // A thing put in changes what the slots can hold: the player's picks start again from
    // the server's own.
    o.picks = null;
    A.say(it.name + " in the " + (TOOL[m] || "step").replace(/^the /, "") + ".");
    A.sound("alchemy.drop." + (it.liquid ? "liquid" : "powder"));
    return changed();
  };
  function refuse(it, why) {
    A.say(it.name + ": " + why);
    A.emit("refused", { key: it.key, why: why });
    return false;
  }
  function changed() {
    A.result = null;
    A.emit("order");
    stageWork();
    renderStage();
    A.runCheck();
    return true;
  }
  A.changed = changed;
  // Take a thing out of the step: an input, the solvent, the vessel, a catalyst.
  A.remove = function (what, key) {
    if (A.busy || A.live) return;
    var o = A.order;
    if (what === "inputs") { o.inputs = o.inputs.filter(function (k) { return k !== key; }); o.picks = null; }
    else if (what === "solvent") o.solvent = "";
    else if (what === "vessel") { o.vessel = ""; o.formula = ""; o.as = ""; o.picks = null; }
    else if (what === "catalysts") {
      o.catalysts = o.catalysts.filter(function (k) { return k !== key; });
      // What the catalyst was told goes with it.
      if (!o.catalysts.length) { o.aim = ""; o.strip = ""; }
    }
    else if (what === "assay") o.assay = "";
    else if (what === "item") o.item = "";
    changed();
  };
  // The card's own controls (53): the formula, the family, a trait's slot, the target, the
  // batch. Each is the player's choice; what it comes to is asked of the server again.
  A.set = function (field, value) {
    if (A.busy || A.live) return;
    var o = A.order;
    if (field === "formula") { o.formula = value || ""; o.picks = null; }
    else if (field === "as") { o.as = value || ""; o.picks = null; }
    else if (field === "aim") { o.aim = value || ""; o.picks = null; }
    else if (field === "strip") { o.strip = value || ""; o.picks = null; }
    else if (field === "target") o.target = value || "";
    else if (field === "batch") o.batch = Math.max(1, Math.round(Number(value) || 1));
    else if (field === "item") o.item = value || "";
    else if (field === "pick") {
      // `value` is {key, on}: the slots' current picks as the server last drew them, with
      // this one turned on or off.
      var rows = (A.check && A.check.slots && A.check.slots.traits) || [];
      var now = o.picks !== null ? o.picks.slice() :
        rows.filter(function (r) { return r.picked; }).map(function (r) { return r.key; });
      now = now.filter(function (k) { return k !== value.key; });
      if (value.on) now.push(value.key);
      o.picks = now;
    }
    A.result = null;
    A.emit("order");
    renderStage();
    if (field !== "item") A.runCheck(); else A.emit("check", A.check);
  };

  // Ask the server what fits and what the step comes to. The newest question wins: an answer
  // to an older step is dropped rather than drawn over a newer one.
  A.runCheck = function () {
    var m = A.order.method;
    if (!m || !A.state) return Promise.resolve(null);
    if (!A.checked(m)) {
      A.check = null;
      A.emit("check", null);
      renderStage();
      return Promise.resolve(null);
    }
    var seq = ++checkSeq;
    A.emit("checking");
    return A.api("/api/alchemy/check", A.body()).then(function (c) {
      if (seq !== checkSeq) return null;
      A.check = c;
      // A formula no longer offered for this vessel goes back to Experiment.
      var o = A.order;
      if (o.formula && !(c.formulae || []).some(function (f) { return f.id === o.formula; })) o.formula = "";
      A.emit("check", c);
      stageWork();
      renderStage();
      return c;
    }).catch(function (err) {
      if (seq !== checkSeq) return null;
      if (err.status === 409) { A.refresh(); return null; }
      A.check = { fits: (A.check && A.check.fits) || {}, problems: [err.message], can_roll: false };
      A.emit("check", A.check);
      renderStage();
      return null;
    });
  };

  // --- the stage column (UI plan §6.3) -------------------------------------------------------------
  function mountStage() {
    var st = A.stage();
    var host = $id("alchemy-tool");
    if (!st || !host || stageMounted || stageMounting) return;
    host.innerHTML = "";
    host.dataset.tool = "";
    host.classList.add("has-stage");
    try {
      stageMounting = Promise.resolve(st.mount(host)).then(function (ok) {
        if (ok === false) throw new Error("no stage here");
        stageMounted = true; stageMounting = null;
        try { st.reducedMotion(A.reduced()); } catch (err) { /* */ }
        stageScene();
        if (A.order.method) stageCall("setTool", A.order.method);
        stageWork();
      }).catch(function () {
        // A stage that cannot draw is the WebGL fallback's case, not an error to show.
        stageMounted = false; stageMounting = null; host.classList.remove("has-stage"); host.dataset.tool = "";
        renderStage();
      });
    } catch (err) { stageMounting = null; host.classList.remove("has-stage"); }
  }
  function stageScene() {
    var s = A.state;
    if (!s || !stageMounted) return;
    var w = s.where || {}, sc = w.scene || {};
    // Lane U3's two grounds (contracts §12): a field kit on the biome's ground, or a
    // laboratory (a town's, rented, or the alchemist's own).
    stageCall("setScene", { kind: sc.kind || "kit", biome: sc.biome || w.biome || "",
                            roofed: !!w.lab, minute: s.clock ? s.clock.minute : 720 });
  }
  // What stands on the bench for the stage: the active vessel and the step's liquid, the
  // server's start state (colour, level, turbidity), never a colour the page made.
  function stageWork() {
    if (!stageMounted) return;
    var c = A.check || {}, liq = c.liquid && c.liquid.start;
    var v = A.order.vessel ? A.item(A.order.vessel) : null;
    // Lane U3's contract: Bottle names the shelf vessel by `id`; every other method stands
    // on its own apparatus, named by `kind`.
    var liquid = liq ? { color: liq.color, level: liq.level, turbidity: liq.turbidity } : null;
    stageCall("setVessel", !A.order.method ? null : v && A.order.method === "bottle"
      ? { id: v.material || v.key, liquid: liquid } : { kind: A.order.method, liquid: liquid });
  }

  // The flat stand-in (UI plan §6.3, "WebGL fallback"): the method's engraved icon at 160px on
  // the ground, with a level bar beside it in the mix's own colour, its level and its words,
  // all the server's (`check.liquid.start`). It is the whole stage until lane U3's arrives.
  function drawFallbackTool() {
    var host = $id("alchemy-tool");
    if (!host || host.classList.contains("has-stage")) return;
    var m = A.order.method;
    // The glass is empty until something is in the step: the server's liquid for an empty
    // step is its resting level, and "20% full" over an empty flask read as a mistake.
    var liq = A.order.inputs.length && A.check && A.check.liquid && A.check.liquid.start;
    var sig = (m || "") + "|" + (liq ? [liq.css, liq.level, liq.words].join(",") : "");
    if (host.dataset.tool === sig) return;
    host.dataset.tool = sig;
    host.innerHTML = "";
    if (!m) return;
    var flat = document.createElement("div");
    flat.className = "bench-flat alchemy-flat";
    var info = A.methodInfo(m);
    var glass = document.createElement("div");
    glass.className = "al-glass";
    glass.appendChild(A.icon(m, { size: 160, label: info ? info.name : m }));
    if (liq && liq.level != null && A.checked(m)) {
      var bar = document.createElement("div");
      bar.className = "al-level";
      bar.setAttribute("role", "img");
      bar.setAttribute("aria-label", "In the glass: " + (liq.words || ""));
      bar.style.setProperty("--lv", String(Number(liq.level) || 0));
      if (liq.css) bar.style.setProperty("--sw", liq.css);
      bar.innerHTML = '<span class="al-level-tube" aria-hidden="true"><i></i></span>' +
        '<span class="al-level-words">' + esc(liq.words || "") + '</span>';
      glass.appendChild(bar);
    }
    flat.appendChild(glass);
    var name = document.createElement("span");
    name.className = "bench-flat-name";
    name.textContent = TOOL[m] || m;
    flat.appendChild(name);
    host.appendChild(flat);
  }

  // The info block under the stage (UI plan §6.3): the step's own line ("3 flasks. 30
  // minutes. DC 20, you need 12 or better."), the rent before the step, where a laboratory
  // is; then the STAKES, the mishap and toxic lines, before the roll and in words, the
  // server's own (plan §8.1: "the page never composes it").
  function renderStage() {
    drawFallbackTool();
    var chips = $id("alchemy-chips"), info = $id("alchemy-info"), why = $id("alchemy-why");
    var lines = $id("alchemy-lines"), roll = $id("alchemy-roll");
    if (!chips || !info || !why || !roll) return;
    var o = A.order, m = o.method, c = A.check, s = A.state || {}, w = s.where || {};
    // What is on the bench: a chip per thing, each with its ×.
    var rows = [];
    var put = function (key, what, label) {
      var it = A.item(key);
      if (it) rows.push({ it: it, what: what, key: key, label: label });
    };
    o.inputs.forEach(function (k) { put(k, "inputs"); });
    if (o.solvent) put(o.solvent, "solvent", "solvent");
    if (o.vessel) put(o.vessel, "vessel", "vessel");
    o.catalysts.forEach(function (k) { put(k, "catalysts", "never spent"); });
    if (o.assay) put(o.assay, "assay");
    chips.innerHTML = rows.map(function (r) {
      return '<li class="bench-chip">' + (r.it.swatch ? '<i class="fr-swatch" style="--sw:' + esc(r.it.swatch) +
        '" aria-hidden="true"></i>' : "") + '<span>' + esc(r.it.name) +
        (r.label ? ' <small>' + esc(r.label) + '</small>' : "") + '</span>' +
        '<button type="button" class="bench-chip-x" data-unput="' + esc(r.what) + '" data-key="' +
        esc(r.key) + '" aria-label="Take ' + esc(r.it.name) + ' off the bench">×</button></li>';
    }).join("");
    chips.hidden = !rows.length;

    var text = [], reason = "", can = false, stakes = [];
    if (!A.loading && !A.error && m) {
      if (A.checked(m)) {
        if (c) {
          if (c.info) text.push(c.info);
          if (c.rent_line) text.push(c.rent_line);
          reason = (c.problems && c.problems[0]) ||
            (c.need == null && c.impossible ? "No roll can make it: it " + c.impossible + "." : "") ||
            (!c.units && !o.inputs.length ? "Put something from the shelf in the step." : "");
          can = !!c.can_roll && c.need != null;
          var st = c.stakes || {};
          if (st.mishap_line) stakes.push({ warn: true, text: st.mishap_line });
          if (st.toxic_line) stakes.push({ warn: true, text: st.toxic_line + "." });
          (st.stabilized || []).forEach(function (t) { stakes.push({ text: t.charAt(0).toUpperCase() + t.slice(1) + "." }); });
          if (st.protected && (st.toxic || []).length === 0 && hasToxic()) {
            stakes.push({ text: "Protected by " + st.protected + "." });
          }
        }
      } else if (m === "assay") {
        reason = o.assay ? "" : "Pick a raw material on the shelf to take a pinch of.";
        can = !!o.assay && !!(w.lab || w.kit);
        if (o.assay && !(w.lab || w.kit)) reason = "You have no field kit with you, and there is no laboratory here.";
        if (A.card && A.card.assay && o.assay) {
          text.push("A pinch: " + A.card.assay.cost + ", " + A.minutes(A.card.assay.minutes) +
                    ". DC " + A.card.assay.dc + " to learn something new of it.");
        }
        var it = A.item(o.assay);
        if (it) {
          var danger = assayDanger(it);
          if (danger) stakes.push({ warn: true, text: danger });
        }
      } else if (m === "identify") {
        reason = o.item ? "" : "Pick a potion you carry in the card.";
        can = !!o.item;
        if (o.item) text.push("Held to the light for a round: beat DC 15 and the spell's level to know what it is.");
      } else if (m === "learn") {
        reason = "Pick a writing to learn from in the card.";
      }
      // Where you are, when a laboratory would open more (the wiring lane's line): "There is
      // a laboratory to rent here: ..." or "<town> has no laboratory to rent". Said only
      // outside one; inside, the footer says where you are.
      if (!w.lab && w.lab_line) text.push(w.lab_line);
    }
    info.innerHTML = text.map(function (t) { return '<span>' + esc(t) + '</span>'; }).join("");
    if (lines) {
      lines.innerHTML = stakes.map(function (x) {
        return '<li' + (x.warn ? ' class="is-warn"' : "") + '>' + esc(x.text) + '</li>';
      }).join("");
      lines.hidden = !stakes.length;
    }
    why.textContent = A.busy ? "" : reason;
    roll.textContent = ROLL[m] || "Roll Craft";
    roll.hidden = m === "learn";
    roll.disabled = !!(A.busy || A.live || A.loading || A.error || !can);
  }
  A.renderStage = renderStage;
  function hasToxic() {
    var o = A.order;
    return o.inputs.concat(o.solvent ? [o.solvent] : [], o.catalysts).some(function (k) {
      var it = A.item(k);
      return it && (it.badges || []).indexOf("toxic to handle") >= 0;
    });
  }
  // An assay of a volatile or toxic reagent is dangerous for real (Q5.1): said before the
  // pinch is taken, in words, from the shelf row's own badges (the hazards are always named,
  // `_ALWAYS` in the API) and where the alchemist stands (`where.protected`).
  function assayDanger(it) {
    var b = it.badges || [], w = (A.state && A.state.where) || {};
    var parts = [];
    if (b.indexOf("toxic to handle") >= 0 && !w.protected) {
      parts.push(it.name + " is toxic to handle, and you wear no mask and stand under no fume hood");
    }
    if (b.indexOf("volatile") >= 0) parts.push(it.name + " is volatile: a miss by 5 or more flares in your face");
    return parts.length ? parts.join(". ") + "." : "";
  }
  A.assayDanger = assayDanger;

  layer.addEventListener("click", function (e) {
    var x = e.target.closest("#alchemy-chips [data-unput]");
    if (x) { A.remove(x.dataset.unput, x.dataset.key); return; }
    if (e.target.closest("#alchemy-roll")) { A.roll(); }
  });

  // Dropping a shelf row on the glass puts it where a click would (51 starts the drag).
  // Drag is never the only way: click or Enter does the same.
  var stageEl = $id("alchemy-stage");
  function dragging(e) {
    return A.dragKey && e.dataTransfer && Array.prototype.indexOf.call(e.dataTransfer.types || [], "text/plain") >= 0;
  }
  function dragOver(on) { var t = $id("alchemy-tool"); if (t) t.classList.toggle("is-dragover", on); }
  if (stageEl) {
    stageEl.addEventListener("dragover", function (e) {
      if (!dragging(e)) return;
      e.preventDefault(); e.dataTransfer.dropEffect = "copy"; dragOver(true);
    });
    stageEl.addEventListener("dragleave", function (e) { if (!stageEl.contains(e.relatedTarget)) dragOver(false); });
    stageEl.addEventListener("drop", function (e) {
      if (!dragging(e)) return;
      e.preventDefault(); dragOver(false);
      var key = A.dragKey; A.dragKey = null;
      A.addItem(key);
    });
  }
  document.addEventListener("dragend", function () { if (A.open) { dragOver(false); A.dragKey = null; } });

  // --- the roll (UI plan §6.3, §6.6) ---------------------------------------------------------------
  // The table's own d20, thrown by the core exactly as every bench throws it. A step with
  // one volatile input opens no modal: its line is already on the screen (the forge's choice
  // for routine steps). A second volatile asks once (UI plan §6.6).
  A.roll = function () {
    var m = A.order.method;
    if (A.busy || A.live || !m) return null;
    if (m === "assay") return assayIt();
    if (m === "identify") return identifyIt();
    var c = A.check;
    if (!c || !c.can_roll || c.need == null) return null;
    var st = c.stakes || {};
    if ((st.volatile_count || 0) >= 2) {
      return A.confirm({
        title: "Two volatile reagents in one step",
        body: "Both mishaps apply if it fails by 5 or more. Work it anyway?",
        warn: st.mishap_line || "",
        ok: "Work it", cancel: "Take one out", danger: true,
      }).then(function (yes) { return yes ? throwStep(c) : null; });
    }
    return throwStep(c);
  };
  function throwStep(c) {
    A.busy = true;
    A.result = null;
    A.emit("rolling");
    renderStage();
    var m = A.order.method;
    var info = A.methodInfo(m);
    // An experiment's product is a secret until it is made (owner Q5.3): the mat says so.
    var name = c.product && c.product.name ? c.product.name :
      c.match && c.match.secret ? "an experiment" : (info ? info.makes || info.name : m);
    var body = A.body();
    var order = JSON.parse(JSON.stringify(A.order));
    return C.rollD20({
      shown: { title: "Alchemy", why: (info ? info.name + ": " : "") + name,
               sides: 20, lo: 1, hi: 20, die: "1d20", terms: C.rollTerms(c) },
      post: function (face) {
        A.sound("alchemy.roll");
        body.face = face;
        return A.api("/api/alchemy/roll", body);
      },
      // A step that takes is followed by its game: the clock face waits for it.
      landed: function (r) { tickClock(r.clock, !!r.token); },
      face: function (r) { return r.roll.face; },
      // The engine's word, shown by the table's verdict once the die is at rest. A Craft
      // check has no naturals (a skill check, CRB p.180), so none is passed and a 20 never
      // reads "natural 20".
      verdict: function (r) {
        var v = r.verdict || {};
        return { verdict: v.verdict, natural: null };
      },
    }).then(function (r) {
      A.busy = false;
      if (r.token) {
        return Promise.resolve(play(r, order)).then(
          function (x) { C.releaseClock(); return x; },
          function (err) { C.releaseClock(); throw err; });
      }
      return failed(r, order).then(focusAfterRoll);
    }).catch(function (err) {
      A.busy = false;
      C.releaseClock();
      C.closeMat();
      $id("alchemy-why").textContent = err.message || String(err);
      A.say(err.message || String(err));
      renderStage();
      focusAfterRoll();
    });
  }
  // Never <body>: Roll if it can roll again, else the shelf's row, else Close.
  function focusAfterRoll() {
    core.refocus(["alchemy-roll", "#alchemy-list .as-add[tabindex='0']", "alchemy-close"]);
  }
  A.focusAfterRoll = focusAfterRoll;

  function tickClock(clock, hold) {
    var s = A.state;
    var before = s && s.clock && typeof s.clock.minute === "number" ? s.clock.minute : null;
    if (clock && s) s.clock = clock;
    if (before != null && clock && typeof clock.minute === "number") C.turnClock(before, clock.minute, hold);
    renderFoot();
  }
  A.tickClock = tickClock;

  // --- the failure ---------------------------------------------------------------------------------
  // A miss by 4 or less loses the time; by 5 or more half the materials are ruined and every
  // unstabilised volatile input's mishap lands on the alchemist, once (`flare`). The flare is
  // the stage's (UI plan §7.5); flat, the stage dims and the brass word reads Flare.
  function failed(r, order) {
    A.result = { failed: true, roll: r.roll, lost: r.lost || [], said: r.said || "",
                 minutes: r.minutes, mastery: r.mastery || null, method: order.method,
                 flare: !!r.flare, mishap: r.mishap || [], toxic: r.toxic || [], rent: r.rent || [] };
    flourish(r.flare ? "flare" : "fail");
    A.emit("result", A.result);
    A.say(r.said || "Failure.");
    return A.refresh();
  }

  // --- the game (contracts §12) --------------------------------------------------------------------
  // Lane U2's game for the method, on the shared strip, when one is registered for this craft
  // (`track: "alchemy"`: a method name another bench registered must not run here). It gets
  // the server's tuning and its gauges exactly as sent: `heat` for Calcine, Distill and
  // Sublime, `reaction` for Dissolve, React and Bottle, `stages` for Transmute, and the
  // liquid's two states for the stage to move between.
  A.gameFor = function (method) {
    var games = window.BenchGames, defs = window.BenchGameDefs || {};
    var def = defs[method];
    if (!games || typeof games.play !== "function" || !def || def.track !== "alchemy") return null;
    return games;
  };
  // Which quality band a live score sits in, by the game strip's own rule (33's `bandOf`):
  // the server's `tuning.bands`, and a 0.015 margin either side of a bound so a needle
  // resting on an edge does not ring the tier-up over and over.
  function tierWatch(tuning) {
    var names = Array.isArray(tuning.names) && tuning.names.length ? tuning.names : null;
    var n = names ? names.length : 5;
    var b = Array.isArray(tuning.bands) && tuning.bands.length === n ? tuning.bands.slice()
      : Array.apply(null, Array(n)).map(function (_, i) { return i / n; });
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
    A.live = { token: r.token, tuning: tuning, roll: r };
    var strip = $id("alchemy-game");
    strip.hidden = false;
    strip.innerHTML = "";
    void strip.offsetWidth;
    strip.classList.add("is-up");
    layer.classList.add("is-playing");
    A.emit("play", A.live);
    renderStage();
    var method = order.method;
    var games = A.gameFor(method);
    var game;
    if (games) {
      // The stage eases the liquid toward the server's end state as the game progresses.
      var view = stageCall("game", method, { end: (r.liquid || {}).end || null }) || null;
      var rose = tierWatch(tuning);
      game = Promise.resolve(games.play({
        method: method, tuning: tuning,
        heat: tuning.heat || null, reaction: tuning.reaction || null,
        stages: tuning.stages || null, pour: tuning.pour || null,
        liquid: r.liquid || null,
        // The flame under the work (lane U2): the athanor in a laboratory, the spirit lamp
        // at the field kit.
        burner: A.state && A.state.where && A.state.where.lab ? "athanor" : "lamp",
        mount: strip, stage: view,
        steady: A.steady(), reducedMotion: A.reduced(),
        onScore: function (s) {
          A.emit("score", s);
          if (rose(s)) flourish("tier");
        },
      }));
    } else {
      // The alchemy games are lane U2's; until one is in the build for this method the step
      // still finishes, at the middle of the range, rather than holding the work.
      A.live.flat = true;
      game = Promise.resolve({ score: 0.5, stopped: false, flat: true });
    }
    return game.then(function (out) {
      out = out || {};
      return finish(Number(out.score) || 0, !!out.stopped, !!out.flat, order, r);
    }, function (err) {
      console.error("alchemy game failed:", err);
      return finish(0, true, false, order, r);
    });
  }

  // --- the finish and the landing --------------------------------------------------------------
  function finish(score, stopped, flat, order, rolled) {
    var live = A.live;
    var strip = $id("alchemy-game");
    core.endGame();
    strip.classList.remove("is-up");
    layer.classList.remove("is-playing");
    A.busy = true;
    renderStage();
    return A.api("/api/alchemy/finish", { token: live.token, score: score, stopped: stopped })
      .then(function (f) {
        A.live = null;
        A.busy = false;
        strip.hidden = true;
        strip.innerHTML = "";
        var from = productRect();
        A.result = { finished: true, finish: f, stopped: stopped, flat: flat, method: order.method,
                     toxic: (rolled && rolled.toxic) || [], rent: (rolled && rolled.rent) || [] };
        if (((f.discoveries || []).length || f.found) && window.AlchemyBooks &&
            typeof AlchemyBooks.forget === "function") {
          try { AlchemyBooks.forget(); } catch (err) { /* */ }
        }
        // The step is cleared: what it made is on the shelf (or In progress), and the
        // result's "Next: Bottle" carries an intermediate there.
        A.order = blank(order.method);
        if (f.state) adopt(f.state);
        tickClock(f.state && f.state.clock);
        A.emit("result", A.result);
        land(f, from);
        stageCall("liquid", (live.roll && live.roll.liquid || {}).end || null, A.reduced() ? 0 : 600);
        stageWork();
        renderStage();
        A.runCheck();
        core.refocus(["alchemy-next", "alchemy-wait", "alchemy-roll", "#alchemy-list .as-add[tabindex='0']"]);
      }).catch(function (err) {
        A.live = null;
        A.busy = false;
        strip.hidden = true;
        strip.innerHTML = "";
        $id("alchemy-why").textContent = err.message || String(err);
        renderStage();
        core.refocus(["alchemy-roll", "alchemy-close"]);
      });
  }

  function productRect() {
    var r = stageCall("productRect");
    if (r && r.width) return r;
    var tool = document.querySelector("#alchemy-tool .bicon") || $id("alchemy-tool");
    return tool ? tool.getBoundingClientRect() : null;
  }

  // The product flies to its shelf row in its own colour: a setting potion to its In
  // progress row (37's group), anything else to its row on the shelf.
  function land(f, from) {
    var made = (f.products || [])[0];
    var flawless = f.tier_name === "Flawless";
    flourish(f.found ? "found" : flawless ? "flawless" : "land", f.tier_name);
    if (!made) return;
    var waits = Number(made.waits) > 0;
    var sel = waits
      ? '#alchemy-list .wk-row[data-works-key="' + A.cssEsc(String(made.key).replace(/^stock:/, "")) + '"]'
      : '#alchemy-list .as[data-key="' + A.cssEsc(made.key) + '"]';
    var pulse = function () {
      A.landed = { key: made.key, until: Date.now() + 1400 };
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
    if (A.reduced() || !from || !to.width || typeof document.body.animate !== "function") { pulse(); return; }
    var el = A.icon(A.rowIcon({ family: (made.record || {}).family, form: (made.record || {}).form,
                                work: waits ? "setting" : "" }), { size: 44, label: made.name });
    if (made.swatch) el.style.setProperty("--sw", made.swatch);
    C.fly(el, from, to).then(pulse);
  }

  // A flourish: the stage's when it is mounted (its burst, glow and crack, UI plan §7.5, §10),
  // else the flat stand-in's: the stage dims on a failure, the brass word reads Flare on a
  // mishap and Flawless on the best work, and the sound rings either way.
  function flourish(kind, word) {
    var st = A.stage();
    var staged = false;
    if (st && stageMounted && typeof st.flourish === "function") {
      try { st.reducedMotion(A.reduced()); st.flourish(kind); staged = true; } catch (err) { staged = false; }
    }
    if (kind === "tier") { if (!staged) A.sound("alchemy.tier.up"); return; }
    if (!staged) {
      A.sound(kind === "flare" ? "alchemy.flare" : kind === "fail" ? "alchemy.fail" :
              kind === "flawless" ? "alchemy.flawless" : kind === "assay" ? "alchemy.assay" :
              kind === "found" ? "alchemy.found" : "alchemy.land");
    }
    var tool = document.querySelector("#alchemy-tool .alchemy-flat .bicon") || $id("alchemy-tool");
    if (kind === "fail" || kind === "flare") {
      if (!staged) C.dim($id("alchemy-stage"));
      // The brass word is the page's over a stage or a flat stand-in alike (a WebGL stage
      // draws no words): FLARE on a mishap (UI plan §7.5), reduced motion its short form.
      if (kind === "flare") C.word(tool, "Flare", false);
      return;
    }
    if (kind === "flawless") C.word(tool, word || "Flawless", !staged);
  }
  A.flourish = flourish;

  // --- Assay and Identify: one roll each, no game ------------------------------------------------
  // The terms the mat shows are the server's (`state.rolls`), since neither has a check.
  function rolled(kind) { return (A.state && A.state.rolls && A.state.rolls[kind]) || null; }

  // The reagent's card, for the assay's DC, cost and time (GET material/<id>); asked when a
  // reagent is picked to assay, read only, so a pending step is never let go by it.
  A.card = null;
  A.on("assay", function (it) {
    A.card = null;
    if (!it || !it.material) return;
    A.api("/api/alchemy/material/" + encodeURIComponent(it.material)).then(function (card) {
      if (A.order.assay !== it.key) return;
      A.card = card;
      A.emit("card", card);
      renderStage();
    }).catch(function () { /* the step still assays; the line waits */ });
  });

  function assayIt() {
    var it = A.item(A.order.assay);
    if (!it) return null;
    var danger = assayDanger(it);
    var go = danger ? A.confirm({
      title: "Assay " + it.name + "?", body: danger, warn: "Assay it anyway?",
      ok: "Assay it", cancel: "Keep it", danger: true,
    }) : Promise.resolve(true);
    return go.then(function (yes) {
      if (!yes) return null;
      A.busy = true;
      renderStage();
      var t = rolled("assay") || {};
      var shown = { title: "Alchemy", why: "Assay: " + it.name, sides: 20, lo: 1, hi: 20, die: "1d20",
                    terms: C.rollTerms({ terms: t.terms || [], bonus: t.bonus,
                                         dc: A.card && A.card.assay ? A.card.assay.dc : null }) };
      return C.rollD20({
        shown: shown,
        post: function (face) {
          return A.api("/api/alchemy/assay", { material: it.material, face: face });
        },
        landed: function (r) { tickClock(r.clock); },
        face: function (r) { return r.roll.face; },
        verdict: function (r) {
          return { verdict: r.roll && r.roll.success === false ? "failure" : "success", natural: null };
        },
      }).then(function (r) {
        A.busy = false;
        A.result = { assay: r, method: "assay" };
        flourish(r.flare ? "flare" : "assay");
        if (r.shelf && A.state) A.state.shelf = r.shelf;
        if (window.AlchemyBooks && typeof AlchemyBooks.forget === "function") {
          try { AlchemyBooks.forget(); } catch (err) { /* */ }
        }
        A.emit("result", A.result);
        A.say(r.revealed && r.revealed.length ? "You learn: " + r.revealed.map(function (x) { return x.text || x.key; }).join("; ") + "."
                                              : "Nothing new.");
        return A.refresh();
      }).then(focusAfterRoll).catch(function (err) {
        A.busy = false;
        C.closeMat();
        $id("alchemy-why").textContent = err.message || String(err);
        renderStage();
        focusAfterRoll();
      });
    });
  }

  function identifyIt() {
    var p = A.potion(A.order.item);
    if (!p) return null;
    A.busy = true;
    renderStage();
    var t = rolled("identify") || {};
    return C.rollD20({
      shown: { title: "Alchemy", why: "Identify: " + p.name, sides: 20, lo: 1, hi: 20, die: "1d20",
               terms: C.rollTerms({ terms: t.terms || [], bonus: t.bonus }) },
      post: function (face) {
        return A.api("/api/alchemy/identify", { item: p.key, face: face });
      },
      landed: function (r) { tickClock(r.clock); },
      face: function (r) { return r.face; },
      verdict: function (r) { return { verdict: r.success ? "success" : "failure", natural: null }; },
    }).then(function (r) {
      A.busy = false;
      A.result = { identify: r, method: "identify", name: p.name };
      flourish("assay");
      A.emit("result", A.result);
      A.say(r.success ? p.name + ": identified." : "The " + p.name + " gives up nothing.");
      return A.refresh();
    }).then(focusAfterRoll).catch(function (err) {
      A.busy = false;
      C.closeMat();
      $id("alchemy-why").textContent = err.message || String(err);
      renderStage();
      focusAfterRoll();
    });
  }

  // --- Learn: a formula from a writing, a potion or a formulary (plan §10.4) --------------------
  // The route's check, DC, cost and time are the server's (`formulary.writings[].plan`); a
  // potion taken apart is spent whatever the roll (the owner's open point 9), so it is asked
  // in --alarm words first. Lane U4's formulary does this with more around it; this is the
  // bench's own door so Learn works without it.
  A.learn = function (w) {
    if (A.busy || A.live || !w) return null;
    var plan = w.plan || {};
    var spent = w.route === "potion" ? A.confirm({
      title: "Take the " + w.name + " apart?", body: "The potion is spent, whatever the roll.",
      warn: "Take it apart?", ok: "Take it apart", cancel: "Keep it", danger: true,
    }) : Promise.resolve(true);
    return spent.then(function (yes) {
      if (!yes) return null;
      A.busy = true;
      renderStage();
      var body = { from: w.route, fid: w.fid, item: w.item };
      if (w.who) body.who = w.who;
      var send = function (face) {
        if (face != null) body.face = face;
        return A.api("/api/alchemy/learn", body);
      };
      var t = rolled("identify") || {};
      var go = plan.check ? C.rollD20({
        shown: { title: "Alchemy", why: "Learn: " + (w.formula || "the " + w.name), sides: 20, lo: 1, hi: 20, die: "1d20",
                 terms: C.rollTerms({ terms: t.terms || [], bonus: t.bonus, dc: plan.dc }) },
        post: send,
        landed: function (r) { tickClock(r.clock); },
        face: function (r) { return r.face; },
        verdict: function (r) { return { verdict: (r.result || {}).learned ? "success" : "failure", natural: null }; },
      }) : send(null).then(function (r) { tickClock(r.clock); return r; });
      return go.then(function (r) {
        A.busy = false;
        A.result = { learn: r, method: "learn" };
        if ((r.result || {}).learned) flourish("found");
        A.emit("result", A.result);
        A.say(r.said || "");
        return A.refresh().then(function () { A.emit("learn"); });
      }).catch(function (err) {
        A.busy = false;
        C.closeMat();
        $id("alchemy-why").textContent = err.message || String(err);
        A.say(err.message || String(err));
        renderStage();
      });
    });
  };

  // --- Wait for it: a setting potion, then collect (lane U1's `wait` on api/alchemy/collect) ---
  A.waitFor = function (key) {
    if (A.busy || A.live || !key) return null;
    A.busy = true;
    renderStage();
    var before = A.state && A.state.clock ? A.state.clock.minute : null;
    return A.api("/api/alchemy/collect", { key: key, wait: true }).then(function (r) {
      A.busy = false;
      if (before != null && r.clock) C.turnClock(before, r.clock.minute);
      A.result = { collected: r, method: A.order.method };
      A.emit("result", A.result);
      A.say((r.waited ? "You wait " + A.minutes(r.waited) + ". " : "") + (r.said || ""));
      try { document.dispatchEvent(new CustomEvent("works:collected", { detail: { key: key, said: r.said } })); } catch (err) { /* */ }
      return A.refresh();
    }).then(function () {
      core.refocus(["alchemy-roll", ".bm[aria-checked='true']"]);
    }).catch(function (err) {
      A.busy = false;
      $id("alchemy-why").textContent = err.message || String(err);
      A.say(err.message || String(err));
      renderStage();
    });
  };

  // --- the method strip (UI plan §6.1) -------------------------------------------------------------
  // A radio group: one Tab stop, arrows move and choose, the number keys jump. Locked
  // methods stay in the row with the lock and the reason in words in the label itself: the
  // level ("Alchemist 2") or the place ("Needs a laboratory"), never in a tooltip only.
  function renderMethods() {
    var row = $id("alchemy-methods");
    if (!row) return;
    var list = (A.state && A.state.methods) || [];
    row.innerHTML = "";
    list.forEach(function (m, i) {
      var on = m.id === A.order.method;
      var b = document.createElement("button");
      b.type = "button";
      b.className = "bm" + (m.locked ? " is-locked" : "");
      b.dataset.method = m.id;
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.tabIndex = on || (!A.order.method && i === 0) ? 0 : -1;
      if (m.locked) b.setAttribute("aria-disabled", "true");
      var label = m.name + (m.locked && m.lock_reason ? ", " + m.lock_reason : "");
      b.setAttribute("aria-label", label + (KEYS[i] ? ". Key " + KEYS[i] : ""));
      b.appendChild(m.locked && window.BenchIcons ? BenchIcons.el("lock", { size: 22, label: "lock" })
                                                  : A.icon(m.id, { size: 22, label: m.name }));
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
      var tip = document.createElement("span");
      tip.className = "bm-tip";
      tip.setAttribute("aria-hidden", "true");
      tip.textContent = label;
      b.appendChild(tip);
      row.appendChild(b);
    });
  }
  A.on("state", renderMethods);
  A.on("method", function () {
    var row = $id("alchemy-methods");
    if (!row) return;
    row.querySelectorAll(".bm").forEach(function (b) {
      var on = b.dataset.method === A.order.method;
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.tabIndex = on ? 0 : -1;
    });
  });
  var methodsEl = $id("alchemy-methods");
  if (methodsEl) {
    methodsEl.addEventListener("click", function (e) {
      var b = e.target.closest(".bm");
      if (b) A.setMethod(b.dataset.method, { focus: true });
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
      var info = A.methodInfo(all[to].dataset.method);
      if (info && !info.locked) A.setMethod(info.id, { focus: true });
      else if (info) A.say(info.name + " is locked. " + (info.lock_reason || ""));
    });
  }

  // --- the footer (UI plan §6.10) ------------------------------------------------------------------
  // The core draws the frame; the bench says what is in it: the clock, where you are ("A
  // field kit on the ground", "In a laboratory, rented by the hour"), "Alchemist" and its
  // numbers, and the two books.
  function footParts() {
    var s = A.state, t = s && s.track;
    return {
      clock: s && s.clock && s.clock.label ? s.clock.label : "",
      place: s && s.where && s.where.label ? s.where.label : "",
      trackLabel: "Your alchemy",
      track: t ? { title: "Alchemist", level: t.level, mp: t.mp,
                   need: t.to_next && t.to_next.need, have: t.to_next && t.to_next.have } : null,
      picks: t && t.picks_banked,
      buttons: '<button type="button" class="bf-btn" data-alchemy-formulary aria-haspopup="dialog">Formulary</button>' +
               '<button type="button" class="bf-btn" data-alchemy-codex aria-haspopup="dialog">Codex</button>',
    };
  }
  function renderFoot() { core.renderFoot(); }
  A.renderFoot = renderFoot;
  var footEl = $id("alchemy-foot");
  if (footEl) {
    footEl.addEventListener("click", function (e) {
      var b = e.target.closest("[data-alchemy-formulary], [data-alchemy-codex]");
      if (b) { A.book(b.hasAttribute("data-alchemy-formulary") ? "formulary" : "codex", b); return; }
      if (e.target.closest("[data-bench-perks]")) A.openPerks();
    });
  }

  // --- the books (contracts §12: lane U4's `window.AlchemyBooks`) -----------------------------------
  // `.formulary(host)` and `.codex(host)` when lane U4's file is in the build; without it, a
  // plain list in the bench's own dialog: the formulae known, with what each needs and how it
  // was learned, and the reagents met, "3 of 7 known". Read only, from the server's routes.
  A.book = function (which, from) {
    var B = window.AlchemyBooks;
    if (B && typeof B[which] === "function") {
      try { B[which]($id("alchemy-pops"), { after: afterBook, from: from }); return; }
      catch (err) { console.error("alchemy " + which + " failed:", err); }
    }
    var url = which === "formulary" ? "/api/alchemy/formulary" : "/api/alchemy/codex";
    A.api(url).then(function (d) { flatBook(which, d, from); })
      .catch(function (err) { A.say(err.message || String(err)); });
  };
  function flatBook(which, d, from) {
    var rows = which === "formulary" ? (d.formulae || []).map(function (f) {
      return '<li><b>' + esc(f.name) + '</b><span>' + esc([f.family, f.requires_words ? "needs " + f.requires_words : "",
        f.how].filter(Boolean).join("; ")) + '</span>' +
        ((f.reach || []).length ? '<span class="is-warn">' + esc(f.reach.join(" ")) + '</span>' : "") + '</li>';
    }) : (d.codex || []).map(function (r) {
      return '<li><b>' + esc(r.name) + '</b><span>' + esc(r.known + " of " + r.total + " known" +
        (r.danger_known ? "; " + r.danger_known : "")) + '</span></li>';
    });
    var title = which === "formulary" ? "Formulary" : "Alchemist's codex";
    var empty = which === "formulary" ? "No formula is written in your book yet." : "No reagent met yet.";
    var pops = $id("alchemy-pops");
    var wrap = document.createElement("div");
    wrap.className = "bench-modal al-book";
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-modal", "true");
    wrap.setAttribute("aria-labelledby", "al-book-t");
    wrap.innerHTML = '<div class="bench-scrim"></div><div class="bench-dialog v2-framed v2-card-leather al-book-d">' +
      '<i class="v2-rim" aria-hidden="true"></i><h3 id="al-book-t">' + esc(title) + '</h3>' +
      (rows.length ? '<ul class="al-book-list">' + rows.join("") + '</ul>' : '<p>' + esc(empty) + '</p>') +
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
  }

  // A reagent's card (lane U4's `.card(materialId, anchorEl)`), from the shelf's "?".
  // Lane U4's options: the row's hazards (always named), where the alchemist stands (for the
  // dangerous-assay confirm: a fume hood or a mask), the bench's popover host, and `after`,
  // run when the card's assay or lesson changed what is known, to read the shelf again.
  A.openCard = function (materialId, el, row) {
    var B = window.AlchemyBooks;
    if (!B || typeof B.card !== "function" || !materialId) return false;
    try {
      B.card(materialId, el, { hazards: (row && row.badges) || [], where: (A.state && A.state.where) || {},
                               pops: $id("alchemy-pops"), after: afterBook });
      return true;
    } catch (err) { console.error("alchemy card failed:", err); return false; }
  };
  function afterBook(detail) {
    var r = detail && (detail.response || detail);
    if (r && r.clock) tickClock(r.clock);
    if (A.open) A.refresh();
  }

  // Lane U4's books fire `alchemy:learned` (an assay, a lesson, a formula copied) and
  // `alchemy:recipe` ({recipe}); each changed what the shelf may show, so it is read again.
  ["alchemy:learned", "alchemy:assayed", "alchemy:recipe"].forEach(function (name) {
    document.addEventListener(name, function (e) {
      if (!A.open) return;
      var r = e.detail && e.detail.response;
      if (r && r.clock) tickClock(r.clock);
      A.refresh();
    });
  });
  // Collect or Stop on the shelf's In progress group (37): the shelf is read again.
  document.addEventListener("works:collected", function () { if (A.open && !A.busy) A.refresh(); });
  document.addEventListener("works:stopped", function () { if (A.open) A.refresh(); });

  // The perk picker (36-bench-perks.js, parameterised by track). Lane U4 adds the
  // alchemist's row; until it is in the build the picker says so rather than opening the
  // wrong craft's perks.
  A.openPerks = function () {
    var t = A.state && A.state.track;
    var P = window.BenchPerks;
    if (!t || !t.picks_banked) return;
    if (!P || typeof P.open !== "function" || !(P.tracks && P.tracks.alchemist)) {
      A.say("The alchemy perks are not in this build yet.");
      return;
    }
    P.open({
      track: "alchemist", state: t, pops: $id("alchemy-pops"), esc: esc,
      pushEsc: core.pushEsc, dropEsc: core.dropEsc, sound: A.sound, api: A.api,
      home: function () {
        var foot = $id("alchemy-foot-in");
        return (foot && foot.querySelector("[data-bench-perks]")) || $id("alchemy-close");
      },
      saved: function (track, picks) {
        if (A.state) A.state.track = track;
        A.emit("state", A.state);
        renderFoot();
        A.say("Perks taken: " + picks.join(", ") + ".");
      },
      afterClose: function () { A.runCheck(); },
    });
  };
})();
