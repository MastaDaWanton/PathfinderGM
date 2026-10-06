// The play table, part 45 (the enchanting circle: the layer, the flow, the stage column and
// the footer). Classic script; everything lives inside one IIFE and is reached through
// `window.Enchant`, so no name here can shadow one of 01-44's (test_s6_panel_shell's rule
// that no top-level function is declared twice across the table's files).
//
// The design is docs/enchanting-ui-plan.md (§5, §6.1-6.5, §8, §12) as the owner's answers
// amend it (docs/enchanting-answers.md: phases of the day, never planets; capacity with no
// +10 frame; FLAWED and never which curse). The API is lane E's play/enchant_views.py
// (contracts §6). Lane U1 built it FLAT FIRST, the forge's order (UI plan §15): fully
// playable with none of the three other lanes' providers, each looked up at the moment it
// is needed and guarded there (contracts §13):
//   window.EnchantStage  lane U3's circle (47-enchant-stage.js); without it, or without
//                        WebGL (`available()` false), the method's engraved roundel on the
//                        ground, as both earlier benches fall back
//   BenchGames + BenchGameDefs[method] with track "enchant"   lane U2's games; without a
//                        game for the method the step finishes at the middle of the range,
//                        the forge's flat rule, and the result says so in words
//   window.EnchantLedger lane U5's essence card, recipes and Journal section; without it
//                        a shelf row says how many traits are unknown in words
//
// THE FLOW (UI plan §5). Prepare lays a circle round a vessel, Attune seats essences on it,
// Bind rolls the book's creation check and puts the work In progress for its days. Each is
// a check (the server says what fits, the DC with every term, what the vessel holds, the
// motes and days, the two failure lines), a roll on the table's own d20 (29's `rollD20`, the
// mat the player can type their own face into), the step's game, and a finish. Read and
// Identify are one roll each with no game (tasting and assay have none). Refine, Unbind and
// Cleanse are the same three requests as the ritual steps.
//
// THE PAGE NEVER COMPUTES A NUMBER (UI plan §12). The DC and its terms, the face needed, the
// holds pips, the motes and their parts, the days, the phase words and the countdowns are all
// the server's. What this file decides is only where a click puts a thing.
//
// WHO DRAWS WHAT. 29 owns what every bench shares. 45 mounts the circle on it and owns the
// method strip, the stage column (the tool, the info block, Wait for it, Roll), the roll, the
// game call, the finish and the footer's words. 46 draws the shelf, 48 the working (the
// vessel, its seats and choices, holds, costs, the paper tag and the result). They talk
// through `Enchant.on(event, fn)`.
//
// MOTION. Nothing loops: no setInterval and no requestAnimationFrame in any enchant file of
// this lane (tests/test_enchant_ui.py greps for both); an idle circle draws no frames.

(function () {
  "use strict";

  var C = window.BenchCore;
  var $id = function (id) { return document.getElementById(id); };
  var layer = $id("enchant");
  if (!C || !layer) return;
  var esc = C.esc;

  // --- vocabulary ---------------------------------------------------------------------------
  // The methods themselves, their order, names and locks are the server's (`state.methods`).
  // What is here is copy: the Roll button's words, the flat stand-in's name for the step, and
  // the empty working's sentence. Keys 1-8 pick the eight methods in order (UI plan §6.1).
  var KEYS = ["1", "2", "3", "4", "5", "6", "7", "8"];
  var ROLL = { prepare: "Roll Prepare", attune: "Roll Attune", bind: "Roll Bind",
               refine: "Roll Refine", unbind: "Roll Unbind", cleanse: "Roll Cleanse",
               read: "Read", identify: "Identify" };
  var TOOL = { prepare: "the circle", attune: "the seats", bind: "the binding",
               refine: "the dropper", unbind: "the sigils", cleanse: "the curse",
               read: "a pinch", identify: "the study" };
  // Two letters per method on the roundel: Read and Refine share an R, and at 1280 wide the
  // strip is icons only (bench.css). The engraved art waits on the owner's icon approval
  // (UI plan Q-UI1); a lettered roundel is the bench's own fallback, not a broken mask.
  var ABBR = { prepare: "Pr", attune: "At", bind: "Bi", refine: "Rf", unbind: "Ub",
               cleanse: "Cl", read: "Rd", identify: "Id" };
  // The ritual's path (UI plan §6.1: "Prepare, then Attune, then Bind", the herb bench's
  // next-step button). Which step a vessel is ready for follows from its state, which is
  // the server's word on the shelf row.
  var NEXT = { prepared: "attune", attuned: "bind" };
  var VESSEL_METHODS = { prepare: 1, attune: 1, bind: 1, unbind: 1, cleanse: 1, identify: 1 };
  var RIMS = { common: "r0", uncommon: "r1", rare: "r2", exotic: "r3", legendary: "r4" };

  var E = window.Enchant = {
    esc: esc, ROLL: ROLL, NEXT: NEXT, KEYS: KEYS,
    state: null,          // the last /api/enchant/state body
    check: null,          // the last /api/enchant/check answer for the order below
    // The working: the method, the vessel's shelf key, the circle (Prepare), the focus gem
    // (a ring or an amulet), the essence on each seat and each seat's choice (Attune), the
    // catalyst and hurry (Bind), the phials and their counts (Refine), the essence to read
    // and the item to identify.
    order: null,
    busy: false, live: null, result: null, loading: false, error: "",
    seatHint: null,       // the seat the player pressed: the next essence goes there
    landed: null,
  };
  function blank(method) {
    return { method: method || null, vessel: "", circle: [], focus: "", seats: {}, choices: {},
             catalyst: "", hurry: false, phials: {}, essence: "", item: "", recipe: "" };
  }
  E.order = blank(null);
  var subs = {};
  E.on = function (ev, fn) { (subs[ev] = subs[ev] || []).push(fn); };
  E.emit = function (ev, data) {
    (subs[ev] || []).forEach(function (fn) {
      try { fn(data); } catch (err) { console.error("enchant " + ev + " handler failed:", err); }
    });
  };
  E.api = C.api; E.minutes = C.minutes; E.sign = C.sign; E.sound = C.sound;
  E.reduced = C.reduced; E.steady = C.steady;
  E.cssEsc = function (s) { return window.CSS && CSS.escape ? CSS.escape(s) : String(s).replace(/"/g, '\\"'); };
  function remember(key, value) { try { window.localStorage.setItem(key, value); } catch (err) { /* */ } }
  function recall(key) { try { return window.localStorage.getItem(key); } catch (err) { return null; } }

  // --- icons (UI plan §4) -------------------------------------------------------------------
  // An engraved icon (aria-hidden: the words beside it carry it). A name the table has art
  // for (the herb and forge registries, through BenchIcons, which 40 taught the forge's
  // names) is drawn as a gilt mask; any other is the lettered roundel, two letters for a
  // method. No new art is fetched here: the enchanting icons wait on the owner (Q-UI1).
  E.icon = function (name, opts) {
    opts = opts || {};
    var el;
    // BenchIcons.has answers for the herb registry only; 40 taught BenchIcons.el the
    // forge's stamped names without teaching `has`, so a forge name is asked for there too
    // (the longsword's "blank" drew a lettered S, seen live 2026-10-06).
    var forge = window.FORGE_ICON_URLS && typeof FORGE_ICON_URLS[name] === "string" &&
                FORGE_ICON_URLS[name].indexOf("?v=") > 0;
    if (window.BenchIcons && (BenchIcons.has(name) || forge)) {
      el = BenchIcons.el(name, opts);
    } else {
      el = document.createElement("span");
      el.className = "bicon" + (opts.tier && RIMS[opts.tier] ? " " + RIMS[opts.tier] : "");
      el.setAttribute("aria-hidden", "true");
      el.dataset.icon = name;
      if (opts.size) el.style.setProperty("--bi", Math.round(opts.size) + "px");
      var letter = document.createElement("span");
      letter.className = "bicon-l";
      letter.textContent = ABBR[name] || String(opts.label || name || "?").charAt(0).toUpperCase();
      if (ABBR[name]) letter.classList.add("is-two");
      el.appendChild(letter);
    }
    return el;
  };
  E.iconHtml = function (name, opts) { return E.icon(name, opts).outerHTML; };
  // The icon for a shelf row: a word that picks a picture, never the meaning (the name
  // beside it carries that). Borrowed from the art the table already ships.
  E.rowIcon = function (it) {
    var g = it.group || "", k = it.kind || "", gear = it.gear || "";
    if (g === "Essences") return "liquid";
    if (k === "ink") return "oil";
    if (k === "treatment") return "treatment";
    if (k === "catalyst") return "reagent";
    if (k === "chalk" || k === "salt" || k === "focus") return "mineral";
    if (gear === "shield") return "shield";
    if (gear === "armour") return "breastplate";
    if (gear === "weapon") return "blank";
    return it.name ? String(it.name).charAt(0) : "?";
  };

  // --- lookups ------------------------------------------------------------------------------
  var GROUPS = ["vessels", "intermediates", "essences", "circle", "gems", "catalysts", "cant_use"];
  E.item = function (key) {
    var s = E.state && E.state.shelf;
    if (!s || !key) return null;
    for (var g = 0; g < GROUPS.length; g++) {
      var list = s[GROUPS[g]] || [];
      for (var i = 0; i < list.length; i++) if (list[i].key === key) return list[i];
    }
    return null;
  };
  E.methodInfo = function (id) {
    var list = (E.state && E.state.methods) || [];
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
    return null;
  };
  // Why this shelf key cannot go into the step now, in the server's words; "" when it
  // fits; null while the server has not answered for it.
  E.why = function (key) {
    var f = E.check && E.check.fits;
    if (!f || !f[key]) return null;
    return f[key].ok ? "" : String(f[key].why || "");
  };
  E.isVessel = function (it) { return !!it && it.group === "Vessels"; };
  E.usesVessel = function (m) { return !!VESSEL_METHODS[m || (E.order && E.order.method)]; };
  E.vessel = function () { return E.item(E.order.vessel); };
  // How many of a shelf entry the working holds: the seats, the dropper, the circle's
  // materials, the focus and the catalyst. The vessel is not counted: it lies in the
  // circle and stays on its row, which says so. A chalk in the circle read "1 on your
  // shelf" beside the chip saying it was in the circle (seen live, 2026-10-06).
  E.inOrder = function (key) {
    var n = 0, o = E.order;
    Object.keys(o.seats).forEach(function (s) { if (o.seats[s] === key) n += 1; });
    if (o.phials[key]) n += o.phials[key];
    o.circle.forEach(function (k) { if (k === key) n += 1; });
    if (o.focus === key) n += 1;
    if (o.catalyst === key) n += 1;
    return n;
  };

  // --- the stage, optional (contracts §13) ----------------------------------------------------
  E.stage = function () {
    var s = window.EnchantStage;
    try { return s && typeof s.available === "function" && s.available() ? s : null; }
    catch (err) { return null; }
  };
  var stageMounted = false, stageMounting = null;
  function stageCall(name, arg) {
    var st = E.stage();
    if (!st || !stageMounted || typeof st[name] !== "function") return undefined;
    try { return st[name](arg); } catch (err) { return undefined; }
  }
  E.stageCall = stageCall;

  // --- the layer, mounted on the core -------------------------------------------------------
  var core = C.mount({
    layer: "enchant", close: "enchant-close", stage: "enchant-stage", say: "enchant-say",
    pops: "enchant-pops", foot: "enchant-foot", footIn: "enchant-foot-in", home: "open-enchant",
    clockId: "enchant-clock", hash: "#enchant", bodyClass: "enchant-on",
    openWith: "[data-enchant-open]",
    first: ".bm[aria-checked='true']",
    quiet: ".bm, .es-add, #enchant-roll",
    live: function () { return !!E.live; },
    keys: function (e) {
      var i = KEYS.indexOf(e.key);
      if (i < 0 || e.ctrlKey || e.metaKey || e.altKey) return;
      var list = (E.state && E.state.methods) || [];
      if (!list[i]) return;
      e.preventDefault();
      E.setMethod(list[i].id, { focus: true });
    },
    opened: function () {
      E.sound("enchant.open");
      E.emit("open");
      core.focusFirst();
      load();
    },
    closing: function () {
      stopAmbience();
      var st = E.stage();
      if (st && stageMounted) { try { st.unmount(); } catch (err) { /* */ } }
      stageMounted = false;
      var host = $id("enchant-tool");
      if (host) { host.classList.remove("has-stage"); host.dataset.tool = ""; host.innerHTML = ""; }
      E.emit("close");
    },
    footer: function () { return footParts(); },
  });
  Object.defineProperty(E, "open", { enumerable: true, get: function () { return core.open; } });
  E.openBench = core.openLayer;
  E.closeBench = core.closeLayer;
  E.pushEsc = core.pushEsc;
  E.dropEsc = core.dropEsc;
  E.confirm = core.confirm;
  E.say = core.say;
  E.refocus = core.refocus;

  // /play/#enchant, the old /craft/ tab's "Open the circle" (craft.html), opens it on load.
  function fromHash() { if (location.hash === "#enchant" && !E.open) E.openBench($id("open-enchant")); }
  window.addEventListener("hashchange", fromHash);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fromHash);
  else setTimeout(fromHash, 0);

  // --- loading ------------------------------------------------------------------------------
  var checkSeq = 0;
  function load() {
    E.loading = true; E.error = ""; E.result = null; E.check = null;
    E.emit("loading");
    renderStage();
    return E.api("/api/enchant/state").then(function (s) {
      E.loading = false;
      adopt(s);
      var last = recall("pgm.enchant.method");
      var m = E.methodInfo(last);
      if (!m || m.locked) {
        var open = (s.methods || []).filter(function (x) { return !x.locked; });
        last = open[0] ? open[0].id : (s.methods && s.methods[0] ? s.methods[0].id : null);
      }
      E.order = blank(null);
      if (last) E.setMethod(last, { quiet: true, force: true });
      var at = document.activeElement;
      if (!at || at === document.body || at.id === "enchant-close") core.focusFirst();
      mountStage();
    }).catch(function (err) {
      E.loading = false;
      E.error = err.message || String(err);
      E.emit("error", E.error);
      renderStage();
    });
  }
  E.reload = load;

  function adopt(s) {
    E.state = s;
    // What the working holds that is no longer on the shelf is lifted: the shelf is the
    // server's, and a working that disagrees with it is a roll the server would refuse.
    var o = E.order;
    if (o.vessel && !E.item(o.vessel)) o.vessel = "";
    o.circle = o.circle.filter(function (k) { return !!E.item(k); });
    if (o.focus && !E.item(o.focus)) o.focus = "";
    if (o.catalyst && !E.item(o.catalyst)) o.catalyst = "";
    if (o.essence && !E.item(o.essence)) o.essence = "";
    if (o.item && !E.item(o.item)) o.item = "";
    Object.keys(o.seats).forEach(function (seat) {
      if (!E.item(o.seats[seat])) { delete o.seats[seat]; delete o.choices[seat]; }
    });
    Object.keys(o.phials).forEach(function (k) {
      var it = E.item(k);
      if (!it) delete o.phials[k];
      else o.phials[k] = Math.min(o.phials[k], it.count);
    });
    E.emit("state", s);
    syncWorks();
    renderFoot();
    stageScene();
    ambience();
  }
  E.adopt = adopt;

  // The room's sound while the circle is open (UI plan §11): `ambience.sanctum`, "a still
  // room, a candle's hiss", at a sanctum (owned or hired), else the biome's own ground, as
  // the forge plays the smithy or the field kit's ground. Lane U6 made the bed and nothing
  // started it (the final pass, 2026-10-06). One bed at a time: a state that moves the
  // circle (a wait that ends somewhere else, a sanctum hired) swaps it; the same place
  // keeps the bed playing rather than restarting it on every check. Sound answers an
  // unknown name with silence, so a biome without a bed costs nothing.
  var bed = null, bedName = "";
  function ambienceName() {
    var w = E.state && E.state.where;
    if (!w) return "";
    return w.sanctum ? "sanctum" : String(w.biome || "");
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
  E.ambienceName = ambienceName;

  // --- old enchanted items, converted (lane H, owner round 3 "Old saves: convert") ---------
  // The first time the circle opens after the revamp, a notice lists every item the
  // conversion changed (its change lines, in the server's words) and every question still
  // open, such as the old bane that never named its foe. Each question is answered from the
  // engine's own options; "Got it" marks the items seen, and an open question stays on the
  // item's card in the working until it is answered. Nothing here is decided by the page.
  E.questionHtml = function (key, q) {
    var id = "eq-" + String(key).replace(/[^A-Za-z0-9_-]/g, "_") + "-" + q.property;
    var opts = (q.options || []).map(function (o) {
      var v = typeof o === "object" ? JSON.stringify(o) : String(o);
      return '<option value="' + esc(v) + '">' + esc(v.replace(/-/g, " ")) + '</option>';
    }).join("");
    var sub = q.of === "creature_type" ?
      '<label class="eq-field eq-sub" for="' + id + '-s" hidden><span>Which subtype (the world\'s own word)</span>' +
      '<input type="text" id="' + id + '-s" class="v2-well" data-sub autocomplete="off" spellcheck="false"></label>' : "";
    var bonus = (q.bonus_values || []).length ?
      '<label class="eq-field" for="' + id + '-b"><span>Bonus</span><select id="' + id + '-b" class="v2-well" data-bonus>' +
      q.bonus_values.map(function (n) { return '<option value="' + esc(n) + '">+' + esc(n) + '</option>'; }).join("") +
      '</select></label>' : "";
    return '<form class="eq-q" data-question data-key="' + esc(key) + '" data-property="' + esc(q.property) +
      '" data-choice="' + esc(q.key || "") + '">' +
      '<p class="eq-words">' + esc(q.words || "") + '</p>' +
      (opts ? '<label class="eq-field" for="' + id + '"><span>' + esc(q.of === "creature_type" ? "Its foe" :
        q.of === "damage_type" ? "Its energy" : q.of === "skill" ? "Its skill" : "Choose") + '</span>' +
        '<select id="' + id + '" class="v2-well" data-value><option value="">Choose</option>' + opts + '</select></label>' : "") +
      sub + bonus +
      '<div class="eq-acts"><button type="submit" class="v2-btn is-small is-go">Name it</button>' +
      '<span class="eq-why" role="status"></span></div></form>';
  };
  layer.addEventListener("change", function (e) {
    var sel = e.target.closest("form[data-question] select[data-value]");
    if (!sel) return;
    var sub = sel.form.querySelector(".eq-sub");
    // A humanoid or outsider foe is one of the world's subtypes, typed (lane A's choice:
    // "pick one subtype"; the subtypes are the world's own and never listed).
    if (sub) sub.hidden = !(sel.value === "humanoid" || sel.value === "outsider");
  });
  layer.addEventListener("submit", function (e) {
    var f = e.target.closest("form[data-question]");
    if (!f) return;
    e.preventDefault();
    var why = f.querySelector(".eq-why");
    var answer = {}, k = f.dataset.choice;
    var val = f.querySelector("[data-value]"), sub = f.querySelector("[data-sub]"), bonus = f.querySelector("[data-bonus]");
    if (val && k) {
      var v = val.value;
      if (sub && !sub.closest("[hidden]") && sub.value.trim()) v = { subtype: sub.value.trim() };
      if (v === "") { why.textContent = "Choose one first."; return; }
      answer[k] = v;
    }
    if (bonus) answer.bonus = Number(bonus.value);
    why.textContent = "";
    E.api("/api/enchant/answer", { key: f.dataset.key, property: f.dataset.property, answer: answer })
      .then(function (r) {
        var lines = (r.lines || []).join("; ");
        E.say(lines ? "Named. " + lines + "." : "Named.");
        if (r.state) adopt(r.state);
        var left = f.closest(".eq-item");
        f.outerHTML = '<p class="eq-done">' + esc(lines ? "Named: " + lines + "." : "Named.") + '</p>';
        if (left && !left.querySelector("form[data-question]")) left.classList.add("is-answered");
        E.runCheck();
      }).catch(function (err) { why.textContent = err.message || String(err); });
  });

  var noticeUp = false;
  function showConversions() {
    var list = ((E.state && E.state.conversions) || []).filter(function (x) { return !x.seen; });
    if (!list.length || noticeUp) return;
    noticeUp = true;
    var pops = $id("enchant-pops");
    var back = document.activeElement;
    var wrap = document.createElement("div");
    wrap.className = "bench-modal en-convert";
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-modal", "true");
    wrap.setAttribute("aria-labelledby", "en-convert-t");
    wrap.innerHTML = '<div class="bench-scrim"></div><div class="bench-dialog v2-framed v2-card-leather en-convert-d">' +
      '<i class="v2-rim" aria-hidden="true"></i>' +
      '<h3 id="en-convert-t">Your enchanted things, brought over</h3>' +
      '<p>Enchanting works on a layer over the smith\'s work now. What changed on each item you carry:</p>' +
      '<ul class="eq-list">' + list.map(function (x) {
        return '<li class="eq-item"><b>' + esc(x.name) + '</b>' +
          ((x.changes || []).length ? '<ul class="eq-changes">' + x.changes.map(function (c) {
            return '<li>' + esc(c) + '</li>'; }).join("") + '</ul>' : "") +
          (x.questions || []).map(function (q) { return E.questionHtml(x.key, q); }).join("") + '</li>';
      }).join("") + '</ul>' +
      '<p class="eq-note">A question left open waits on the item\'s card until you answer it.</p>' +
      '<div class="bench-dialog-acts"><button type="button" class="v2-btn is-go" data-convert-ok>Got it</button></div></div>';
    pops.appendChild(wrap);
    var close = function () {
      core.dropEsc(close);
      wrap.remove();
      noticeUp = false;
      list.forEach(function (x) { E.api("/api/enchant/seen", { key: x.key }).catch(function () { /* shown again next time */ }); });
      if (back && document.contains(back) && back.focus) back.focus();
    };
    core.pushEsc(close);
    wrap.querySelector("[data-convert-ok]").addEventListener("click", close);
    var first = wrap.querySelector("select, [data-convert-ok]");
    if (first) first.focus();
  }
  E.showConversions = showConversions;
  E.on("state", function () { if (E.open) showConversions(); });

  E.refresh = function () {
    return E.api("/api/enchant/state").then(function (s) { adopt(s); return E.runCheck(); })
      .catch(function (err) { E.say(err.message); });
  };

  // In progress (lane U4's 37-works.js) asks for its rows again when the circle's clock or
  // its own count has moved, so a binding's countdown in the shelf's group moves on game
  // time and a fresh binding appears in it the moment Bind finishes.
  function syncWorks() {
    var W = window.Works, s = E.state;
    if (!W || typeof W.sync !== "function" || !s) return;
    W.sync("enchant|" + (s.clock ? s.clock.minute : "") + "|" + ((s.works || []).length));
  }

  // --- the method -----------------------------------------------------------------------------
  E.setMethod = function (id, opts) {
    opts = opts || {};
    if (E.busy || E.live) return null;
    var info = E.methodInfo(id);
    if (!info) return null;
    if (info.locked) {
      E.say(info.name + " is locked. " + (info.lock_reason || ""));
      E.emit("refused", { method: id, why: info.lock_reason });
      return null;
    }
    var changed = E.order.method !== id;
    if (!changed && !opts.force) {
      if (opts.focus) focusMethod(id);
      return E.runCheck();
    }
    var keepVessel = changed && opts.carry ? opts.carry : (changed ? "" : E.order.vessel);
    if (changed) {
      E.order = blank(id);
      if (keepVessel && E.usesVessel(id)) {
        if (id === "identify") E.order.item = keepVessel; else E.order.vessel = keepVessel;
      }
      E.seatHint = null;
    }
    if (!opts.keepResult) E.result = null;
    remember("pgm.enchant.method", id);
    if (changed && !opts.quiet) E.sound("enchant.method." + id);
    E.check = null;
    E.emit("method", id);
    stageCall("setTool", id);
    stageWork();
    renderStage();
    if (opts.focus) focusMethod(id);
    return E.runCheck();
  };
  function focusMethod(id) {
    var btn = layer.querySelector('.bm[data-method="' + id + '"]');
    if (btn) btn.focus();
  }

  // --- the body the server is asked about -----------------------------------------------------
  // Only what the method takes: a body carrying a stale seat into Prepare would be a
  // question about a step the player is not taking.
  E.body = function (extra) {
    var o = E.order, m = o.method, body = { method: m };
    if (m === "prepare") {
      body.vessel = o.vessel; body.circle = o.circle.slice();
      if (o.focus) body.focus = o.focus;
    } else if (m === "attune") {
      body.vessel = o.vessel; body.seats = Object.assign({}, o.seats);
      body.choices = JSON.parse(JSON.stringify(o.choices));
      if (o.recipe) body.recipe = o.recipe;
    } else if (m === "bind") {
      body.vessel = o.vessel; body.hurry = !!o.hurry;
      if (o.catalyst) body.catalyst = o.catalyst;
    } else if (m === "refine") {
      body.phials = Object.assign({}, o.phials);
    } else if (m === "unbind" || m === "cleanse") {
      body.vessel = o.vessel;
    }
    if (extra) Object.keys(extra).forEach(function (k) { body[k] = extra[k]; });
    return body;
  };
  // Read and Identify have no check (contracts §6: single requests). Their working is the
  // one thing picked.
  E.checked = function (m) { return m && m !== "read" && m !== "identify"; };

  // --- putting a shelf row into the working ----------------------------------------------------
  // A click, Enter or a drop on the stage. Where it goes is decided by the method and the
  // row's group; whether it may go is the server's (`check.fits`), said in its words.
  E.addItem = function (key) {
    var o = E.order, m = o.method;
    if (E.busy || E.live || !m) return false;
    var it = E.item(key);
    if (!it) return false;
    var why = E.why(key);
    // Read and Identify ask nothing of a vessel's state: a sword in hand can be studied
    // (its "take it off first" is for working it, not for looking at it).
    if (it.why_not && m !== "identify" && m !== "read") return refuse(it, it.why_not);
    if (m === "read") {
      if (it.group !== "Essences") return refuse(it, "Read takes a pinch of an essence");
      o.essence = key;
      E.say(it.name + " is ready to read.");
      return changed(it);
    }
    if (m === "identify") {
      if (!it.card) return refuse(it, "there is no magic in it to identify");
      o.item = key;
      E.say(it.name + " is ready to study.");
      return changed(it);
    }
    if (E.checked(m) && E.check === null) {
      E.say("One moment: the circle is still reading what fits.");
      return false;
    }
    if (why) return refuse(it, why);
    if (E.isVessel(it)) {
      if (!E.usesVessel(m)) return refuse(it, "this step takes no vessel");
      if (o.vessel === key) { E.say(it.name + " is in the circle already."); return false; }
      o.vessel = key; o.seats = {}; o.choices = {};
      E.say(it.name + " is laid in the circle.");
      return changed(it);
    }
    if (it.group === "Essences") {
      var left = (it.count || 0) - E.inOrder(key);
      if (m === "refine") {
        if (left <= 0) { E.say("All your " + it.name + " is in the dropper already."); return false; }
        o.phials[key] = (o.phials[key] || 0) + 1;
        E.say(it.name + " in the dropper, " + o.phials[key] + " in all.");
        return changed(it);
      }
      if (m === "attune") {
        var v = E.vessel();
        if (!v) return refuse(it, "lay a prepared vessel in the circle first");
        if (left <= 0) { E.say("All your " + it.name + " is seated already."); return false; }
        var seats = v.seats || [];
        var target = E.seatHint;
        if (!target) {
          var free = seats.filter(function (s) { return !o.seats[s.id]; })[0];
          target = free ? free.id : null;
        }
        if (!target) return refuse(it, "every seat on the " + v.name + " is taken: lift one first");
        o.seats[target] = key;
        delete o.choices[target];
        E.seatHint = null;
        var seatName = (seats.filter(function (s) { return s.id === target; })[0] || {}).name || target;
        E.say(it.name + " seated at the " + String(seatName).toLowerCase() + ".");
        E.sound("enchant.seat");
        return changed(it);
      }
      return refuse(it, "essences go in at Attune or Refine");
    }
    if (m === "prepare") {
      if (it.kind === "focus") { o.focus = key; E.say(it.name + " set as the focus."); return changed(it); }
      // One line (chalk or salt), one ink and at most one treatment make a circle: a second
      // of a kind takes the first one's place rather than piling up (the server would refuse
      // the pile, `_build_prepare`).
      var same = function (k) {
        var x = E.item(k);
        var line = function (y) { return y && (y.kind === "chalk" || y.kind === "salt"); };
        return x && (x.kind === it.kind || (line(x) && line(it)));
      };
      o.circle = o.circle.filter(function (k) { return !same(k); });
      o.circle.push(key);
      E.say(it.name + " in the circle.");
      return changed(it);
    }
    if (m === "bind" && it.kind === "catalyst") {
      o.catalyst = key;
      E.say(it.name + " set beside the vessel.");
      return changed(it);
    }
    return refuse(it, "it does not go into this step");
  };
  function refuse(it, why) {
    E.say(it.name + ": " + why);
    E.emit("refused", { key: it.key, why: why });
    return false;
  }
  function changed() {
    E.result = null;
    E.emit("order");
    stageWork();
    renderStage();
    E.runCheck();
    return true;
  }
  E.changed = changed;
  // Take a thing out of the working: a seat lifted, a circle material, the vessel itself.
  E.remove = function (what, key) {
    if (E.busy || E.live) return;
    var o = E.order;
    if (what === "vessel") { o.vessel = ""; o.seats = {}; o.choices = {}; }
    else if (what === "seat") { delete o.seats[key]; delete o.choices[key]; E.sound("enchant.unseat"); }
    else if (what === "circle") o.circle = o.circle.filter(function (k) { return k !== key; });
    else if (what === "focus") o.focus = "";
    else if (what === "catalyst") o.catalyst = "";
    else if (what === "essence") o.essence = "";
    else if (what === "item") o.item = "";
    else if (what === "phial") {
      o.phials[key] = (o.phials[key] || 0) - 1;
      if (o.phials[key] <= 0) delete o.phials[key];
    }
    changed();
  };
  E.setChoice = function (seat, k, value) {
    if (E.busy || E.live) return;
    var c = E.order.choices[seat] = E.order.choices[seat] || {};
    if (value === "" || value == null) delete c[k]; else c[k] = value;
    E.emit("order");
    E.runCheck();
  };
  E.setHurry = function (on) {
    if (E.busy || E.live) return;
    E.order.hurry = !!on;
    E.emit("order");
    E.runCheck();
  };

  // Ask the server what fits and what the working comes to. The newest question wins: an
  // answer to an older working is dropped rather than drawn over a newer one.
  E.runCheck = function () {
    var m = E.order.method;
    if (!m || !E.state) return Promise.resolve(null);
    if (!E.checked(m)) {
      E.check = null;
      E.emit("check", null);
      renderStage();
      return Promise.resolve(null);
    }
    var seq = ++checkSeq;
    E.emit("checking");
    return E.api("/api/enchant/check", E.body()).then(function (c) {
      if (seq !== checkSeq) return null;
      E.check = c;
      E.emit("check", c);
      stageWork();
      renderStage();
      return c;
    }).catch(function (err) {
      if (seq !== checkSeq) return null;
      if (err.status === 409) { E.refresh(); return null; }
      E.check = { fits: (E.check && E.check.fits) || {}, problems: [err.message], can_roll: false };
      E.emit("check", E.check);
      renderStage();
      return null;
    });
  };

  // --- the stage column (UI plan §6.3) ---------------------------------------------------------
  function mountStage() {
    var st = E.stage();
    var host = $id("enchant-tool");
    if (!st || !host || stageMounted || stageMounting) return;
    host.innerHTML = "";
    host.dataset.tool = "";
    host.classList.add("has-stage");
    try {
      stageMounting = Promise.resolve(st.mount(host)).then(function (ok) {
        if (ok === false) throw new Error("no stage here");
        stageMounted = true; stageMounting = null;
        try { st.reducedMotion(E.reduced()); } catch (err) { /* */ }
        stageScene();
        if (E.order.method) stageCall("setTool", E.order.method);
        stageWork();
      }).catch(function () {
        // A stage that cannot draw is the WebGL fallback's case, not an error to show.
        stageMounted = false; stageMounting = null; host.classList.remove("has-stage"); renderStage();
      });
    } catch (err) { stageMounting = null; host.classList.remove("has-stage"); }
  }
  function stageScene() {
    var s = E.state;
    if (!s || !stageMounted) return;
    var w = s.where || {};
    // Lane U3's four grounds: an owned sanctum, a hired circle, a roof, or the open ground.
    var kind = w.sanctum ? (w.sanctum.kind === "hired" ? "hired" : "sanctum") : (w.roofed ? "roofed" : "camp");
    stageCall("setScene", { kind: kind, biome: w.biome || "", roofed: kind !== "camp",
                            minute: s.clock ? s.clock.minute : 720 });
    stageCall("hour", E.check && E.check.hour ? E.check.hour : (s.hour || null));
  }
  // What lies in the circle, for the stage: the vessel as the forge built it (its gear, base
  // and pieces from the shelf row) and each seat with its essence and colour.
  function stageWork() {
    if (!stageMounted) return;
    // Identify studies an item rather than laying a vessel, and the circle stood empty while
    // it did (the final pass, 2026-10-06): the item studied lies at its heart the same way.
    var v = E.vessel() || (E.order.method === "identify" && E.order.item ? E.item(E.order.item) : null);
    // `family` is for the jewellery and wearable vessels only (a ring, an amulet): a forged
    // weapon, suit or shield is built from its own pieces, and a family given for one makes
    // the stage skip them. Passing the gear as the family drew the Superior longsword as a
    // pair of gloves, read off its "hands" slot (the final pass, 2026-10-06).
    var forged = v && (v.gear === "weapon" || v.gear === "armour" || v.gear === "shield");
    stageCall("setVessel", v ? { key: v.key, name: v.name, gear: v.gear, base: v.base, pieces: v.pieces || {},
                                 family: forged ? "" : v.gear, quality_index: v.quality_index, slot: v.slot } : null);
    var c = E.check || {};
    stageCall("setSeats", (c.seats || []).map(function (s) {
      var it = s.seated ? E.item(s.seated) : null;
      return { seat: s.seat, essence: s.essence, color: s.color, phase: s.phase || (it ? it.phase : ""),
               seated: !!s.seated, lit: !!s.seated };
    }));
    if (c.hour) stageCall("hour", c.hour);
  }

  // The flat stand-in: the method's roundel at 160px on the ground (UI plan §6.3, "WebGL
  // fallback"). It is the whole stage until lane U3's circle arrives.
  function drawFallbackTool() {
    var host = $id("enchant-tool");
    if (!host || host.classList.contains("has-stage")) return;
    var m = E.order.method;
    if (host.dataset.tool === (m || "")) return;
    host.dataset.tool = m || "";
    host.innerHTML = "";
    if (!m) return;
    var ring = document.createElement("div");
    ring.className = "bench-flat enchant-flat";
    var info = E.methodInfo(m);
    ring.appendChild(E.icon(m, { size: 160, label: info ? info.name : m }));
    var name = document.createElement("span");
    name.className = "bench-flat-name";
    name.textContent = TOOL[m] || m;
    ring.appendChild(name);
    host.appendChild(ring);
  }

  // The info block under the stage (UI plan §5.2): the step's own lines, the DC and the face
  // it needs, and the two failure lines BEFORE the roll, in words (revamp plan §4.4: the
  // curse is the craft's only risk, so it is never a footnote). Then the phase of the day
  // the lead essence favours, with Wait for it when it is not now.
  function renderStage() {
    drawFallbackTool();
    var chips = $id("enchant-chips"), info = $id("enchant-info"), why = $id("enchant-why");
    var lines = $id("enchant-lines"), hour = $id("enchant-hour"), roll = $id("enchant-roll");
    if (!chips || !info || !why || !roll) return;
    var o = E.order, m = o.method, c = E.check;
    // What is in the circle: a chip per thing, each with its ×.
    var rows = [];
    var put = function (key, what, n) {
      var it = E.item(key);
      if (it) rows.push({ it: it, what: what, key: key, n: n });
    };
    if (o.vessel) put(o.vessel, "vessel");
    o.circle.forEach(function (k) { put(k, "circle"); });
    if (o.focus) put(o.focus, "focus");
    Object.keys(o.seats).forEach(function (s) { put(o.seats[s], "seat:" + s); });
    if (o.catalyst) put(o.catalyst, "catalyst");
    Object.keys(o.phials).forEach(function (k) { put(k, "phial", o.phials[k]); });
    if (o.essence) put(o.essence, "essence");
    if (o.item) put(o.item, "item");
    chips.innerHTML = rows.map(function (r) {
      var parts = r.what.split(":");
      return '<li class="bench-chip">' + (r.it.color ? '<i class="fr-swatch" style="--sw:' + esc(r.it.color) +
        '" aria-hidden="true"></i>' : "") + '<span>' + esc(r.it.name) + (r.n > 1 ? " ×" + esc(r.n) : "") +
        '</span><button type="button" class="bench-chip-x" data-unput="' + esc(parts[0]) + '" data-key="' +
        esc(parts[1] || r.key) + '" aria-label="Take ' + esc(r.it.name) + ' out of the circle">×</button></li>';
    }).join("");
    chips.hidden = !rows.length;

    var text = [], reason = "", can = false;
    if (!E.loading && !E.error && m) {
      if (E.checked(m)) {
        if (c) {
          (c.info || []).forEach(function (t) { text.push(t); });
          if (c.dc && c.need != null) {
            text.push("DC " + c.dc + ": you need " + c.need + " or better on the d20.");
          }
          reason = (c.problems && c.problems[0]) ||
            (c.need == null && c.impossible ? "No roll can make it: it " + c.impossible + "." : "");
          can = !!c.can_roll && c.need != null;
        }
      } else if (m === "read") {
        reason = o.essence ? "" : "Pick an essence on the shelf to take a pinch of.";
        can = !!o.essence;
        if (o.essence) text.push("A tenth of the phial and ten minutes, for one trait.");
      } else if (m === "identify") {
        reason = o.item ? "" : "Pick a magic item on the shelf to study.";
        can = !!o.item;
        if (o.item) text.push("Beat the item's DC to learn what it was made to do; by 10 to see a curse. Once a day for each item.");
      }
    }
    info.innerHTML = text.map(function (t) { return '<span>' + esc(t) + '</span>'; }).join("");
    if (lines) {
      var l = c && c.lines;
      lines.innerHTML = l && (l.miss_small || l.miss_big) ?
        '<li>' + esc(l.miss_small) + '</li><li class="is-warn">' + esc(l.miss_big) + '</li>' : "";
      lines.hidden = !lines.innerHTML;
    }
    if (hour) drawHour(hour, c);
    why.textContent = E.busy ? "" : reason;
    roll.textContent = ROLL[m] || "Roll";
    roll.disabled = !!(E.busy || E.live || E.loading || E.error || !can);
  }
  E.renderStage = renderStage;

  // The favourable phase of the day (owner round 4 point 10, round 5): the lead essence's
  // family names one of the seven phases, and inside it Bind's windows are wider. The words
  // and the wait are the server's (`check.hour`, sky.words); "Wait for it" moves the clock
  // there through POST wait, the one door (`Scene.advance`), never by writing the clock.
  function drawHour(host, c) {
    var h = c && c.hour;
    if (!h || !E.order.method || E.order.method === "read" || E.order.method === "identify") {
      host.innerHTML = ""; host.hidden = true; return;
    }
    var phase = String(h.phase || "");
    // Which seated essence the phase is for: the one whose family names this phase on its
    // shelf row. Every seated name was first said here, and "Noon favours Flaming Essence,
    // Bane Essence" was wrong for bane, a dusk essence (seen live, 2026-10-06).
    var lead = (c.seats || []).filter(function (s) {
      var it = s.seated ? E.item(s.seated) : null;
      return s.essence && (s.phase || (it && it.phase)) === phase;
    }).map(function (s) { return s.essence; });
    var name = phase.charAt(0).toUpperCase() + phase.slice(1);
    var line = h.inside
      ? '<span class="eh-in">' + esc(h.words) + '</span><span class="eh-why">' +
        (E.order.method === "bind" ? "The binding's windows are wider now." : "Bind in it and the windows are wider.") + '</span>'
      : '<span class="eh-out">' + esc(h.words) + '</span><span class="eh-why">' + esc(name) +
        ' favours ' + (lead && lead.length ? esc(lead.join(", ")) : "this essence") + ': Bind\'s windows are wider then.</span>';
    host.innerHTML = '<span class="eh-mark" aria-hidden="true"></span><span class="eh-words">' + line + '</span>' +
      (!h.inside && h.minutes_until > 0 ? '<button type="button" class="v2-btn is-small is-quiet" id="enchant-wait" data-wait="' +
        esc(phase) + '">Wait for it</button>' : "");
    host.hidden = false;
  }

  // Wait for it: the clock moves to the phase's start. An attunement holds a day; a wait
  // that would outlast it is said before it is taken, in the server's own words for both.
  E.wait = function (phase) {
    if (E.busy || E.live || !phase) return;
    var v = E.vessel(), h = E.check && E.check.hour;
    var s = E.state;
    // Whether the wait outlasts the attunement is the server's answer (`hour.lapses`).
    var go = v && v.attuned && h && h.lapses ? E.confirm({
      title: "Wait for " + phase + "?",
      body: "The attunement on the " + v.name + " holds " + v.attuned.left_words + " more; " + phase + " is later than that.",
      warn: "The essences drift back to the shelf when it lapses. You would attune again.",
      ok: "Wait", cancel: "Keep working",
    }) : Promise.resolve(true);
    go.then(function (yes) {
      if (!yes) return;
      E.busy = true;
      renderStage();
      var before = s && s.clock ? s.clock.minute : null;
      E.api("/api/enchant/wait", { phase: phase }).then(function (w) {
        E.busy = false;
        if (before != null && w.clock) C.turnClock(before, w.clock.minute);
        E.say(w.waited ? "You wait " + E.minutes(w.waited) + ". " + w.words + "." : w.words + ".");
        (w.ended || []).forEach(function (t) { E.say(t); });
        return E.refresh();
      }).then(function () {
        core.refocus(["enchant-roll", ".bm[aria-checked='true']"]);
      }).catch(function (err) {
        E.busy = false;
        $id("enchant-why").textContent = err.message || String(err);
        renderStage();
      });
    });
  };

  layer.addEventListener("click", function (e) {
    var x = e.target.closest("[data-unput]");
    if (x) {
      var what = x.dataset.unput, key = x.dataset.key;
      E.remove(what === "seat" ? "seat" : what, key);
      return;
    }
    var w = e.target.closest("[data-wait]");
    if (w) { E.wait(w.dataset.wait); return; }
    if (e.target.closest("#enchant-roll")) { E.roll(); }
  });

  // Dropping a shelf row on the stage puts it where a click would (46 starts the drag).
  // Drag is never the only way: click or Enter does the same.
  var stageEl = $id("enchant-stage");
  function dragging(e) {
    return E.dragKey && e.dataTransfer && Array.prototype.indexOf.call(e.dataTransfer.types || [], "text/plain") >= 0;
  }
  function dragOver(on) { var t = $id("enchant-tool"); if (t) t.classList.toggle("is-dragover", on); }
  if (stageEl) {
    stageEl.addEventListener("dragover", function (e) {
      if (!dragging(e)) return;
      e.preventDefault(); e.dataTransfer.dropEffect = "copy"; dragOver(true);
    });
    stageEl.addEventListener("dragleave", function (e) { if (!stageEl.contains(e.relatedTarget)) dragOver(false); });
    stageEl.addEventListener("drop", function (e) {
      if (!dragging(e)) return;
      e.preventDefault(); dragOver(false);
      var key = E.dragKey; E.dragKey = null;
      E.addItem(key);
    });
  }
  document.addEventListener("dragend", function () { if (E.open) { dragOver(false); E.dragKey = null; } });

  // --- the roll (UI plan §5, step 4) -----------------------------------------------------------
  // The table's own d20, thrown by the core exactly as both other benches throw it, with the
  // player's own face typed on the mat when they roll their own dice.
  E.roll = function () {
    var m = E.order.method;
    if (E.busy || E.live || !m) return null;
    if (m === "read") return readEssence();
    if (m === "identify") return identifyItem();
    var c = E.check;
    if (!c || !c.can_roll || c.need == null) return null;
    if (m === "unbind") {
      var v = E.vessel();
      return E.confirm({
        title: "Unbind the " + (v ? v.name : "item") + "?",
        body: "The layer comes off whole and the item stays the smith's. A quarter of its motes come back as residue.",
        warn: c.lines && c.lines.miss_big ? c.lines.miss_big : "",
        ok: "Unbind it", cancel: "Keep it", danger: true,
      }).then(function (yes) { return yes ? throwStep(c) : null; });
    }
    return throwStep(c);
  };
  function throwStep(c) {
    E.busy = true;
    E.result = null;
    E.emit("rolling");
    renderStage();
    var m = E.order.method;
    var info = E.methodInfo(m);
    var name = c.product && c.product.name ? c.product.name : (E.vessel() ? E.vessel().name : "the circle");
    var body = E.body();
    var order = JSON.parse(JSON.stringify(E.order));
    return C.rollD20({
      shown: { title: "Enchanting", why: (info ? info.name + ": " : "") + name,
               sides: 20, lo: 1, hi: 20, die: "1d20", terms: C.rollTerms(c) },
      post: function (face) {
        E.sound("enchant.roll");
        body.face = face;
        return E.api("/api/enchant/roll", body);
      },
      // A step that takes is followed by its game: the clock face waits for it.
      landed: function (r) { tickClock(r.minutes, r.clock, !!r.token); },
      face: function (r) { return r.roll.face; },
      // The engine's word, shown by the table's verdict once the die is at rest, FLAWED
      // included (22's third word): the player reads it on the mat beside the margin. An
      // enchanting check has no naturals (a skill check, CRB p.180), so none is passed and a
      // 20 never reads "natural 20". Which curse is never sent and never said.
      verdict: function (r) {
        var v = r.verdict || {};
        return { verdict: v.verdict, natural: null };
      },
    }).then(function (r) {
      E.busy = false;
      if (r.token) {
        return Promise.resolve(play(r, order)).then(
          function (x) { C.releaseClock(); return x; },
          function (err) { C.releaseClock(); throw err; });
      }
      return failed(r).then(focusAfterRoll);
    }).catch(function (err) {
      E.busy = false;
      C.releaseClock();
      C.closeMat();
      $id("enchant-why").textContent = err.message || String(err);
      E.say(err.message || String(err));
      renderStage();
      focusAfterRoll();
    });
  }
  // Never <body>: Roll if it can roll again, else the shelf's row, else Close.
  function focusAfterRoll() {
    core.refocus(["enchant-roll", "#enchant-list .es-add[tabindex='0']", "enchant-close"]);
  }
  E.focusAfterRoll = focusAfterRoll;

  function tickClock(minutes, clock, hold) {
    var s = E.state;
    var before = s && s.clock && typeof s.clock.minute === "number" ? s.clock.minute : null;
    if (clock && s) s.clock = clock;
    if (before != null && clock && typeof clock.minute === "number") C.turnClock(before, clock.minute, hold);
    renderFoot();
  }
  E.tickClock = tickClock;

  // --- the failure --------------------------------------------------------------------------------
  function failed(r) {
    E.result = { failed: true, roll: r.roll, lost: r.lost || [], said: r.said || "",
                 minutes: r.minutes, mastery: r.mastery || null, method: E.order.method };
    flourish("fail");
    E.emit("result", E.result);
    E.say(r.said || "Failure.");
    return E.refresh();
  }

  // --- the game (contracts §13) -------------------------------------------------------------------
  // Lane U2's game for the method, on the shared strip, when one is registered for this
  // craft (`track: "enchant"`: a method name another bench registered must not run here).
  // It gets the server's tuning, the phase of the day (`opts.hour`, lane E's own shape:
  // {phase, now, inside, minutes_left, minutes_until, words, widen}), the sequence for the
  // order games and the seats for Attune, exactly as the server sent them.
  E.gameFor = function (method) {
    var games = window.BenchGames, defs = window.BenchGameDefs || {};
    var def = defs[method];
    if (!games || typeof games.play !== "function" || !def || def.track !== "enchant") return null;
    return games;
  };
  function play(r, order) {
    var tuning = r.tuning || {};
    E.live = { token: r.token, tuning: tuning, flawed: (r.verdict || {}).verdict === "flawed" };
    var strip = $id("enchant-game");
    strip.hidden = false;
    strip.innerHTML = "";
    void strip.offsetWidth;
    strip.classList.add("is-up");
    layer.classList.add("is-playing");
    E.emit("play", E.live);
    renderStage();
    var method = order.method;
    var games = E.gameFor(method);
    var game;
    if (games) {
      var view = stageCall("game", method) || null;
      game = Promise.resolve(games.play({
        // The clock's minute rides with the phase so Bind's band can draw a needle at now
        // (lane U2's ask); it is the server's minute, attached, never computed.
        method: method, tuning: tuning,
        hour: tuning.hour ? Object.assign({}, tuning.hour, { minute: E.state && E.state.clock ? E.state.clock.minute : null }) : null,
        seq: tuning.seq || null,
        seats: tuning.seats || null, mount: strip, stage: view,
        steady: E.steady(), reducedMotion: E.reduced(),
        onScore: function (s) { E.emit("score", s); },
      }));
    } else {
      // The enchanting games are lane U2's; until one is in the build for this method the
      // step still finishes, at the middle of the range, rather than holding the working.
      E.live.flat = true;
      game = Promise.resolve({ score: 0.5, stopped: false, flat: true });
    }
    return game.then(function (out) {
      out = out || {};
      return finish(Number(out.score) || 0, !!out.stopped, !!out.flat, order);
    }, function (err) {
      console.error("enchant game failed:", err);
      return finish(0, true, false, order);
    });
  }

  // --- the finish and the landing --------------------------------------------------------------
  function finish(score, stopped, flat, order) {
    var live = E.live;
    var strip = $id("enchant-game");
    core.endGame();
    strip.classList.remove("is-up");
    layer.classList.remove("is-playing");
    E.busy = true;
    renderStage();
    return E.api("/api/enchant/finish", { token: live.token, score: score, stopped: stopped })
      .then(function (f) {
        E.live = null;
        E.busy = false;
        strip.hidden = true;
        strip.innerHTML = "";
        var from = productRect();
        E.result = { finished: true, finish: f, stopped: stopped, flat: flat, method: order.method,
                     flawed: f.verdict === "flawed" };
        if ((f.discoveries || []).length && window.EnchantLedger && EnchantLedger.forget) {
          try { EnchantLedger.forget(); } catch (err) { /* */ }
        }
        // The working is cleared: the vessel has moved on to its next state, and the
        // result's "Next: Attune" carries it there (a prepared vessel's key is its new
        // split-off stack, `products[0].key`, never the old one).
        E.order = blank(E.order.method);
        if (f.state) adopt(f.state);
        tickClock(0, f.state && f.state.clock);
        E.emit("result", E.result);
        land(f, from);
        stageWork();
        renderStage();
        E.runCheck();
        core.refocus(["enchant-next", "enchant-works", "enchant-roll", "#enchant-list .es-add[tabindex='0']"]);
      }).catch(function (err) {
        E.live = null;
        E.busy = false;
        strip.hidden = true;
        strip.innerHTML = "";
        $id("enchant-why").textContent = err.message || String(err);
        renderStage();
        core.refocus(["enchant-roll", "enchant-close"]);
      });
  }

  function productRect() {
    var r = stageCall("productRect");
    if (r && r.width) return r;
    var tool = document.querySelector("#enchant-tool .bicon") || $id("enchant-tool");
    return tool ? tool.getBoundingClientRect() : null;
  }

  // The product flies to its shelf row: a binding to its In progress row (lane U4's group),
  // a prepared or attuned vessel to its row under Prepared and attuned.
  function land(f, from) {
    var made = (f.products || [])[0];
    var flawless = (Number(f.tier) || 0) >= 4 && f.verdict !== "flawed";
    flourish(f.verdict === "flawed" ? "flawed" : flawless ? "flawless" :
             made && made.state === "in_progress" ? "bind" : "land", f.tier_name);
    E.say(f.said || (made ? made.name : "Done."));
    if (!made) return;
    var sel = made.state === "in_progress"
      ? '#enchant-list .wk-row[data-works-key="' + E.cssEsc(String(made.key).replace(/^stock:/, "")) + '"]'
      : '#enchant-list .es[data-key="' + E.cssEsc(made.key) + '"]';
    var pulse = function () {
      E.landed = { key: made.key, until: Date.now() + 1400 };
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
    if (E.reduced() || !from || !to.width || typeof document.body.animate !== "function") { pulse(); return; }
    var it = E.item(made.key) || { group: "Vessels", gear: (E.vessel() || {}).gear, name: made.name };
    var el = E.icon(E.rowIcon(it), { size: 44, label: made.name });
    C.fly(el, from, to).then(pulse);
  }

  function flourish(kind, word) {
    var st = E.stage();
    var staged = false;
    if (st && stageMounted && typeof st.flourish === "function") {
      try { st.reducedMotion(E.reduced()); st.flourish(kind); staged = true; } catch (err) { staged = false; }
    }
    // Read and Identify: the stage's eye over the phial or the item, which rings its own
    // `enchant.read` / `enchant.identify`; the flat stand-in rings it here. Both used to
    // play it as the die was thrown as well, so on a WebGL stage it sounded twice (the
    // final pass, 2026-10-06, counted with a Sound.play spy).
    if (kind === "read" || kind === "identify") {
      if (!staged) E.sound("enchant." + kind);
      return;
    }
    if (!staged) E.sound("enchant." + (kind === "fail" ? "fail" : kind === "flawless" ? "flawless" :
                                       kind === "flawed" ? "flawed" : "land"));
    if (staged && kind !== "flawless") return;
    var tool = document.querySelector("#enchant-tool .enchant-flat .bicon") || $id("enchant-tool");
    if (kind === "fail" || kind === "flawed") { C.dim($id("enchant-stage")); return; }
    if (kind === "flawless") C.word(tool, word || "Flawless", !staged);
  }
  E.flourish = flourish;

  // --- Read and Identify: one roll each, no game ----------------------------------------------
  // The terms the mat shows are the server's (`state.rolls`): the Enchanter check for a
  // Read, and for Identify the better of it and Spellcraft, as the server will take it.
  function rolled(kind) { return (E.state && E.state.rolls && E.state.rolls[kind]) || null; }

  function readEssence() {
    var it = E.item(E.order.essence);
    if (!it) return null;
    E.busy = true;
    renderStage();
    // A volatile essence bites the one who reads it (UI plan §6.7): asked first, in words.
    var card = E.api("/api/enchant/essence/" + encodeURIComponent(it.id)).catch(function () { return null; });
    return card.then(function (doc) {
      if (!doc || !doc.volatile) return true;
      E.busy = false;
      return E.confirm({ title: "Read " + it.name + "?", body: "This essence bites the one who reads it.",
                         warn: "Read it anyway?", ok: "Read it", cancel: "Keep it", danger: true })
        .then(function (yes) { E.busy = !!yes; return yes; });
    }).then(function (yes) {
      if (!yes) { E.busy = false; renderStage(); return null; }
      var t = rolled("read") || {};
      var shown = { title: "Enchanting", why: "Read: " + it.name, sides: 20, lo: 1, hi: 20, die: "1d20",
                    terms: C.rollTerms({ terms: t.terms || [], bonus: t.bonus }) };
      return C.rollD20({
        shown: shown,
        post: function (face) {
          return E.api("/api/enchant/read", { essence: it.key, face: face });
        },
        landed: function (r) { tickClock(r.minutes, r.clock); },
        face: function (r) { return r.roll.face; },
        verdict: function (r) {
          return { verdict: r.roll && r.roll.success === false ? "failure" : "success", natural: null };
        },
      }).then(function (r) {
        E.busy = false;
        E.result = { read: r, method: "read" };
        flourish("read");
        if (r.shelf && E.state) { E.state.shelf = r.shelf; }
        E.order.essence = r.pinch && r.pinch.key && r.pinch.left > 0 ? r.pinch.key : "";
        if (window.EnchantLedger && EnchantLedger.forget) { try { EnchantLedger.forget(); } catch (err) { /* */ } }
        E.emit("result", E.result);
        E.say(r.revealed && r.revealed.length ? "You learn: " + r.revealed.map(function (x) { return x.text; }).join("; ") + "."
                                              : "Nothing new.");
        return E.refresh();
      }).then(focusAfterRoll).catch(function (err) {
        E.busy = false;
        C.closeMat();
        $id("enchant-why").textContent = err.message || String(err);
        renderStage();
        focusAfterRoll();
      });
    });
  }

  function identifyItem() {
    var it = E.item(E.order.item);
    if (!it) return null;
    E.busy = true;
    renderStage();
    var t = rolled("identify") || {};
    return C.rollD20({
      shown: { title: "Enchanting", why: "Identify: " + it.name, sides: 20, lo: 1, hi: 20, die: "1d20",
               terms: C.rollTerms({ terms: t.terms || [], bonus: t.bonus }) },
      post: function (face) {
        return E.api("/api/enchant/identify", { item: it.key, face: face });
      },
      landed: function (r) { tickClock(r.minutes, r.clock); },
      face: function (r) { return r.roll.face; },
      verdict: function (r) { return { verdict: r.result === "fail" ? "failure" : "success", natural: null }; },
    }).then(function (r) {
      E.busy = false;
      E.result = { identify: r, method: "identify" };
      flourish("identify");
      E.emit("result", E.result);
      E.say(r.words || "");
      return E.refresh();
    }).then(focusAfterRoll).catch(function (err) {
      E.busy = false;
      C.closeMat();
      $id("enchant-why").textContent = err.message || String(err);
      renderStage();
      focusAfterRoll();
    });
  }

  // --- the method strip (UI plan §6.1) -----------------------------------------------------------
  // A radio group: one Tab stop, arrows move and choose, 1-8 jump. Locked methods stay in
  // the row with the lock and the reason in words in the label itself: the level
  // ("Enchanter 2") or the place ("Needs a sanctum"), never in a tooltip only.
  function renderMethods() {
    var row = $id("enchant-methods");
    if (!row) return;
    var list = (E.state && E.state.methods) || [];
    row.innerHTML = "";
    list.forEach(function (m, i) {
      var on = m.id === E.order.method;
      var b = document.createElement("button");
      b.type = "button";
      b.className = "bm" + (m.locked ? " is-locked" : "");
      b.dataset.method = m.id;
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.tabIndex = on || (!E.order.method && i === 0) ? 0 : -1;
      if (m.locked) b.setAttribute("aria-disabled", "true");
      var label = m.name + (m.locked && m.lock_reason ? ", " + m.lock_reason : "");
      b.setAttribute("aria-label", label + ". Key " + (KEYS[i] || ""));
      b.appendChild(m.locked && window.BenchIcons ? BenchIcons.el("lock", { size: 22, label: "lock" })
                                                  : E.icon(m.id, { size: 22, label: m.name }));
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
  E.on("state", renderMethods);
  E.on("method", function () {
    var row = $id("enchant-methods");
    if (!row) return;
    row.querySelectorAll(".bm").forEach(function (b) {
      var on = b.dataset.method === E.order.method;
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.tabIndex = on ? 0 : -1;
    });
  });
  var methodsEl = $id("enchant-methods");
  if (methodsEl) {
    methodsEl.addEventListener("click", function (e) {
      var b = e.target.closest(".bm");
      if (b) E.setMethod(b.dataset.method, { focus: true });
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
      var info = E.methodInfo(all[to].dataset.method);
      if (info && !info.locked) E.setMethod(info.id, { focus: true });
      else if (info) E.say(info.name + " is locked. " + (info.lock_reason || ""));
    });
  }

  // --- the footer (UI plan §6.9) -------------------------------------------------------------------
  // The core draws the frame; the circle says what is in it: the clock, where you are,
  // "Enchanter" and its numbers, and Recipes and Ledger when lane U5's file is in the build.
  function footParts() {
    var s = E.state, t = s && s.track;
    var L = window.EnchantLedger;
    return {
      clock: s && s.clock && s.clock.label ? s.clock.label : "",
      place: s && s.where && s.where.label ? s.where.label : "",
      trackLabel: "Your enchanting",
      track: t ? { title: "Enchanter", level: t.level, mp: t.mp,
                   need: t.to_next && t.to_next.need, have: t.to_next && t.to_next.have } : null,
      picks: t && t.picks_banked,
      buttons: (L && typeof L.recipes === "function" ? '<button type="button" class="bf-btn" data-enchant-recipes>Recipes</button>' : "") +
               (L && typeof L.journal === "function" ? '<button type="button" class="bf-btn" data-enchant-ledger>Ledger</button>' : ""),
    };
  }
  function renderFoot() { core.renderFoot(); }
  E.renderFoot = renderFoot;
  var footEl = $id("enchant-foot");
  if (footEl) {
    footEl.addEventListener("click", function (e) {
      var L = window.EnchantLedger;
      if (e.target.closest("[data-enchant-recipes]") && L && L.recipes) {
        try { L.recipes($id("enchant-pops"), e.target.closest("button")); } catch (err) { console.error(err); }
        return;
      }
      if (e.target.closest("[data-enchant-ledger]")) {
        // The Journal's essences and recipes (lane U5), in place of the circle, as the
        // forge's Ledger button does.
        E.closeBench();
        if (E.open) return;
        if (typeof Shell === "object" && Shell && Shell.show) Shell.show("journal");
        document.dispatchEvent(new CustomEvent("enchant:ledger"));
        return;
      }
      if (e.target.closest("[data-bench-perks]")) E.openPerks();
    });
  }

  // A Read or a lesson from lane U5's card took a pinch and passed time: the shelf, the
  // clock and the footer are the server's, so they are read again.
  // Lane U5's card fires `enchant:learned` (a Read or a lesson), `enchant:identified` and
  // `enchant:recipe` ({recipe}); each changed what the shelf may show.
  ["enchant:learned", "enchant:identified", "enchant:recipe"].forEach(function (name) {
    document.addEventListener(name, function (e) {
      if (!E.open) return;
      var r = e.detail && e.detail.response;
      if (r && r.clock) tickClock(0, r.clock);
      E.refresh();
    });
  });
  // Collect or Stop on the shelf's In progress group (37): the shelf is read again.
  document.addEventListener("works:collected", function () { if (E.open) E.refresh(); });
  document.addEventListener("works:stopped", function () { if (E.open) E.refresh(); });

  // The perk picker (36-bench-perks.js, parameterised by track). Lane U5 adds the
  // enchanter's row; until it is in the build the picker says so rather than opening the
  // wrong craft's perks.
  E.openPerks = function () {
    var t = E.state && E.state.track;
    var P = window.BenchPerks;
    if (!t || !t.picks_banked) return;
    if (!P || typeof P.open !== "function" || !(P.tracks && P.tracks.enchanter)) {
      E.say("The enchanting perks are not in this build yet.");
      return;
    }
    P.open({
      track: "enchanter", state: t, pops: $id("enchant-pops"), esc: esc,
      pushEsc: core.pushEsc, dropEsc: core.dropEsc, sound: E.sound, api: E.api,
      home: function () {
        var foot = $id("enchant-foot-in");
        return (foot && foot.querySelector("[data-bench-perks]")) || $id("enchant-close");
      },
      saved: function (track, picks) {
        if (E.state) E.state.track = track;
        E.emit("state", E.state);
        renderFoot();
        E.say("Perks taken: " + picks.join(", ") + ".");
      },
      afterClose: function () { E.runCheck(); },
    });
  };
})();
