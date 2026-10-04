// The play table, part 40 (the forge: the layer, the flow, the stage column and the
// footer). Classic script; everything lives inside one IIFE and is reached through
// `window.Forge`, so no name here can shadow one of 01-36's (test_s6_panel_shell's rule
// that no top-level function is declared twice across the table's files).
//
// The design is docs/blacksmithing-ui-plan.md (§5, §6.1-6.6, §6.8, §8, §12); the API it
// calls is docs/blacksmithing-contracts.md §7, served by play/forge_views.py. Lane U2
// built it FLAT FIRST (UI plan §15): fully playable with no 3D stage, no forge games and
// no ledger. The three providers are other lanes' and each is optional (contracts §11),
// looked up at the moment it is needed and never at load:
//   window.ForgeStage   lane U4's anvil (42-forge-stage.js); without it, the engraved
//                       icon of the tool on the ground, as the herb bench's fallback
//   BenchGames + BenchGameDefs[method]   lane U3's games in the shared strip; without a
//                       game for the method, the step finishes at a middling score
//   window.ForgeLedger  lane U5's card and Journal section (44-forge-ledger.js); without
//                       it, the rack says how many properties are unknown in words
//
// THE FLOW (UI plan §5): pick a method; the server says, for every rack row and every
// slot, whether it fits and why not; put pieces in the work order's slots by click,
// Enter or drag and ask again; Roll Craft throws the table's own d20 through the bench
// core (29-bench-core.js `rollD20`, the same ask, land and verdict as every roll); on a
// success the game plays and its score goes to the server, which names the tier; the
// product flies to its rack row; on a failure the work order says what was lost.
//
// THE PAGE NEVER COMPUTES A NUMBER (UI plan §12): the DC, the odds, the info line, the
// heat bands, the build card's every cell, the tier and the place line's rent are all
// the server's. What this file decides is only where a click puts a thing: the first
// empty slot the server said it fits.
//
// WHO DRAWS WHAT. 29 owns what every bench shares (the layer, Esc, the trap, the clock,
// the footer frame, the confirm, the flight, the d20). 40 mounts the forge on it and
// owns the method strip, the stage column, the roll, the game call and the footer's
// words. 41 draws the rack, 43 the work order (slots, the paper tag, the build card and
// the result). They talk through `Forge.on(event, fn)`.
//
// MOTION. Nothing loops: no setInterval and no requestAnimationFrame in any forge file
// (tests/test_forge_ui.py greps for both); an idle forge draws no frames.

(function () {
  "use strict";

  var C = window.BenchCore;
  var $id = function (id) { return document.getElementById(id); };
  var layer = $id("forge");
  if (!C || !layer) return;
  var esc = C.esc;

  // --- vocabulary ---------------------------------------------------------------------------
  // The method's tool in a sentence ("Put it on the anvil"), and the empty rack's sentence
  // ("Nothing you carry can be forged."). The METHODS themselves, their order, names and
  // locks are the server's (`state.methods`).
  var TOOL = { smelt: "furnace", alloy: "crucible", forge: "anvil", quench: "trough",
               temper: "hearth", fold: "anvil", hone: "whetstone", assemble: "anvil",
               finish: "bench", strengthen: "anvil", assay: "touchstone" };
  var DONE = { smelt: "smelted", alloy: "alloyed", forge: "forged", quench: "quenched",
               temper: "tempered", fold: "folded", hone: "honed", assemble: "assembled",
               finish: "finished", strengthen: "strengthened", assay: "assayed" };
  // Keys 1-9, 0 and - pick the eleven methods in order (UI plan §6.1).
  var KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-"];

  // Icons (UI plan §4): the forge's 35 engraved icons from game-icons.net (CC BY 3.0,
  // downloaded by the lead with the owner's approval, contracts §13, 86b537c), drawn as
  // the herb icons are: a gilt mask over the brass grain (bench.css `.bicon.is-mask`).
  // The stamped URLs come from the table's `window.FORGE_ICON_URLS`, a registry of the
  // forge's own beside bench-icons.js's: that file pins its 46 herb names to the table's
  // BENCH_ICON_URLS (tests/test_bench_ui.py) and is no lane's this wave. A name with no
  // stamped file falls back to BenchIcons (whose `lock` serves the locks), and a name
  // neither knows to the lettered roundel, two letters for a method (Forge, Fold and
  // Finish all begin with F, and at 1280 wide the strip is icons only).
  var ABBR = { smelt: "Sm", alloy: "Al", forge: "Fo", quench: "Qu", temper: "Te", fold: "Fd",
               hone: "Ho", assemble: "As", finish: "Fi", strengthen: "St", assay: "Ay" };
  var RIMS = { common: "r0", uncommon: "r1", rare: "r2", exotic: "r3", legendary: "r4" };
  function forgeUrl(name) {
    var map = window.FORGE_ICON_URLS;
    var u = map && typeof map === "object" ? map[name] : "";
    return typeof u === "string" && u.indexOf("?v=") > 0 ? u : "";
  }
  // The icon for a rack row: its form, and for a fitting, fuel or finished piece the word
  // in its id or shape that says which ("ash-haft" is a haft, "steel-crossguard" a guard,
  // a chain shirt mail). Words only pick a picture; the name beside it carries the meaning.
  function rowIcon(it) {
    var f = it.form || "", id = String(it.material || it.key || "") + " " + String(it.shape || "");
    if (f === "fitting") {
      if (/haft|core|stave/.test(id)) return "haft";
      if (/guard/.test(id)) return "guard";
      if (/grip|wrap|binding|hilt/.test(id)) return "grip";
      return "rivets";
    }
    if (f === "fuel") return /charcoal/.test(id) ? "charcoal" : "coal";
    if (f === "plate" || f === "item") {
      if (it.gear === "shield" || /shield|buckler/.test(id)) return "shield";
      if (/chain|mail/.test(id) && !/scale/.test(id)) return "mail";
      if (/scale/.test(id)) return "scale-mail";
      if (it.gear === "armour" || /plate|banded|splint/.test(id)) return f === "plate" ? "plate" : "breastplate";
      return f === "item" ? "grip" : "plate";
    }
    if (f === "old") return "anvil";
    return f || "bar";
  }

  var F = window.Forge = {
    TOOL: TOOL, DONE: DONE, esc: esc,
    state: null,          // the last /api/forge/state body
    check: null,          // the last /api/forge/check answer for the order below
    // The work order: the method, what is in each slot (rack keys), the crucible's parts
    // with their counts (Alloy), the shape picked at Forge, the batch, the ambition at
    // Assemble, and which gear's slots are shown (Assemble follows the main piece).
    order: { method: null, slots: {}, parts: [], shape: "", batch: 1, masterwork: true,
             gear: "weapon" },
    busy: false, live: null, result: null, loading: false, error: "",
    slotHint: null,       // an empty slot the player pressed: Enter on a row fills it
    dragKey: null, landed: null,
  };
  var subs = {};
  F.on = function (ev, fn) { (subs[ev] = subs[ev] || []).push(fn); };
  F.emit = function (ev, data) {
    (subs[ev] || []).forEach(function (fn) {
      try { fn(data); } catch (err) { console.error("forge " + ev + " handler failed:", err); }
    });
  };
  F.rowIcon = rowIcon;
  F.api = C.api; F.minutes = C.minutes; F.sign = C.sign; F.sound = C.sound;
  F.reduced = C.reduced; F.steady = C.steady;
  function remember(key, value) { try { window.localStorage.setItem(key, value); } catch (err) { /* */ } }
  function recall(key) { try { return window.localStorage.getItem(key); } catch (err) { return null; } }
  F.cssEsc = function (s) { return window.CSS && CSS.escape ? CSS.escape(s) : String(s).replace(/"/g, '\\"'); };

  // An engraved icon (aria-hidden: the words beside it carry it).
  F.icon = function (name, opts) {
    opts = opts || {};
    var url = forgeUrl(name);
    var el;
    if (url || !window.BenchIcons) {
      el = document.createElement("span");
      el.className = "bicon" + (opts.tier && RIMS[opts.tier] ? " " + RIMS[opts.tier] : "");
      el.setAttribute("aria-hidden", "true");
      el.dataset.icon = name;
      if (opts.size) el.style.setProperty("--bi", Math.round(opts.size) + "px");
      if (url) {
        el.classList.add("is-mask");
        el.style.setProperty("--bi-mask", 'url("' + url.replace(/"/g, "%22") + '")');
      }
      var letter = document.createElement("span");
      letter.className = "bicon-l";
      letter.textContent = String(opts.label || name || "?").charAt(0).toUpperCase();
      el.appendChild(letter);
    } else {
      el = BenchIcons.el(name, opts);
    }
    if (ABBR[name] && !el.classList.contains("is-mask")) {
      var l = el.querySelector(".bicon-l");
      if (l) { l.textContent = ABBR[name]; l.classList.add("is-two"); }
    }
    return el;
  };
  F.iconHtml = function (name, opts) { return F.icon(name, opts).outerHTML; };
  // The perk picker (36, "anvil", "quench", "hone", "ingot") and lane U5's ledger card
  // (44, a material's form) ask BenchIcons for forge names, which its 46-name registry
  // does not hold, so they drew lettered roundels beside the forge's own engraved art.
  // BenchIcons is taught the forge's names here, for a name it has no art for and the
  // forge has: bench-icons.js and its pinned herb list stay as they are.
  if (window.BenchIcons && !BenchIcons.forgeNames) {
    var herbEl = BenchIcons.el;
    BenchIcons.el = function (name, opts) {
      return forgeUrl(name) && !BenchIcons.has(name) ? F.icon(name, opts) : herbEl(name, opts);
    };
    BenchIcons.html = function (name, opts) { return BenchIcons.el(name, opts).outerHTML; };
    BenchIcons.forgeNames = true;
  }

  // --- lookups ------------------------------------------------------------------------------
  F.item = function (key) {
    var r = F.state && F.state.rack;
    if (!r) return null;
    for (var i = 0; i < r.length; i++) if (r[i].key === key) return r[i];
    return null;
  };
  F.methodInfo = function (id) {
    var list = (F.state && F.state.methods) || [];
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
    return null;
  };
  // The slots the work order shows now: the check's own once it has answered for this
  // method (Assemble's follow the main piece's gear), else the state's for the method.
  F.slots = function (gear) {
    var m = F.order.method;
    if (!m) return [];
    var all = (F.state && F.state.slots) || {};
    if (m === "assemble") {
      var g = gear || F.order.gear || "weapon";
      if (g !== "weapon" && all["assemble:armour"]) return all["assemble:armour"];
      return all.assemble || [];
    }
    return all[m] || [];
  };
  // Why this rack key cannot go in this slot, in the server's words; "" when it fits;
  // null while the server has not yet answered for this method.
  F.fit = function (slot, key) {
    var f = F.check && F.check.fits;
    if (!f || !f[slot]) return null;
    var why = f[slot][key];
    return typeof why === "string" ? why : null;
  };
  // Why a row cannot be used for the method at all, or "" when some slot takes it.
  F.why = function (key) {
    var f = F.check && F.check.fits;
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
  // How many of this rack entry the order uses (a slot holds one; a crucible part its count).
  F.inOrder = function (key) {
    var n = 0, o = F.order;
    Object.keys(o.slots).forEach(function (s) { if (o.slots[s] === key) n += 1; });
    o.parts.forEach(function (p) { if (p.key === key) n += p.count; });
    return n;
  };
  F.hasMain = function () {
    return !!(F.order.slots.head || F.order.slots.body);
  };

  // --- the stage, optional (contracts §11) ----------------------------------------------------
  F.stage = function () {
    var s = window.ForgeStage;
    try { return s && typeof s.available === "function" && s.available() ? s : null; }
    catch (err) { return null; }
  };
  var stageMounted = false, stageMounting = null;
  function stageCall(name, arg) {
    var st = F.stage();
    if (!st || !stageMounted || typeof st[name] !== "function") return undefined;
    try { return st[name](arg); } catch (err) { return undefined; }
  }
  F.stageCall = stageCall;

  // --- the layer, mounted on the core -------------------------------------------------------
  var ambience = null;
  var core = C.mount({
    layer: "forge", close: "forge-close", stage: "forge-stage", say: "forge-say",
    pops: "forge-pops", foot: "forge-foot", footIn: "forge-foot-in", home: "open-forge",
    clockId: "forge-clock", hash: "#forge", bodyClass: "forge-on",
    openWith: "[data-forge-open]",
    first: ".bm[aria-checked='true']",
    quiet: ".bm, .fr-add, #forge-roll",
    live: function () { return !!F.live; },
    keys: function (e) {
      var i = KEYS.indexOf(e.key);
      if (i < 0 || e.ctrlKey || e.metaKey || e.altKey) return;
      var list = (F.state && F.state.methods) || [];
      if (!list[i]) return;
      e.preventDefault();
      F.setMethod(list[i].id, { focus: true });
    },
    opened: function () {
      F.sound("forge.open");
      F.emit("open");
      core.focusFirst();
      load();
    },
    closing: function () {
      if (ambience) { try { ambience.stop(); } catch (err) { /* */ } ambience = null; }
      var st = F.stage();
      if (st && stageMounted) { try { st.unmount(); } catch (err) { /* */ } }
      stageMounted = false;
      var host = $id("forge-tool");
      if (host) { host.classList.remove("has-stage"); host.dataset.tool = ""; host.innerHTML = ""; }
      F.emit("close");
    },
    footer: function () { return footParts(); },
  });
  Object.defineProperty(F, "open", { enumerable: true, get: function () { return core.open; } });
  F.openForge = core.openLayer;
  F.closeForge = core.closeLayer;
  F.pushEsc = core.pushEsc;
  F.dropEsc = core.dropEsc;
  F.confirm = core.confirm;
  F.say = core.say;
  F.refocus = core.refocus;

  // /play/#forge, the old /craft/ tab's "Open the forge" (craft.html), opens it on load.
  function fromHash() { if (location.hash === "#forge" && !F.open) F.openForge($id("open-forge")); }
  window.addEventListener("hashchange", fromHash);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fromHash);
  else setTimeout(fromHash, 0);

  // --- loading ------------------------------------------------------------------------------
  var checkSeq = 0;
  function load() {
    F.loading = true; F.error = ""; F.result = null; F.check = null;
    F.emit("loading");
    renderStage();
    return F.api("/api/forge/state").then(function (s) {
      F.loading = false;
      adopt(s);
      var last = recall("pgm.forge.method");
      var m = F.methodInfo(last);
      if (!m || m.locked) {
        var open = (s.methods || []).filter(function (x) { return !x.locked; });
        var forge = open.filter(function (x) { return x.id === "forge"; })[0];
        last = forge ? forge.id : (open[0] ? open[0].id : (s.methods && s.methods[0] ? s.methods[0].id : null));
      }
      F.order = { method: null, slots: {}, parts: [], shape: "", batch: 1, masterwork: true,
                  gear: "weapon" };
      if (last) F.setMethod(last, { quiet: true, force: true });
      var at = document.activeElement;
      if (!at || at === document.body || at.id === "forge-close") core.focusFirst();
      mountStage();
      maybeAmbience();
    }).catch(function (err) {
      F.loading = false;
      F.error = err.message || String(err);
      F.emit("error", F.error);
      renderStage();
    });
  }
  F.reload = load;

  function adopt(s) {
    F.state = s;
    // A slot holding something no longer carried is emptied: the rack is the server's,
    // and an order that disagrees with it is a roll the server would refuse.
    var o = F.order;
    Object.keys(o.slots).forEach(function (slot) {
      var it = F.item(o.slots[slot]);
      if (!it || it.count <= 0) delete o.slots[slot];
    });
    o.parts = o.parts.filter(function (p) {
      var it = F.item(p.key);
      if (!it) return false;
      p.count = Math.min(p.count, it.count);
      return p.count > 0;
    });
    F.emit("state", s);
    renderFoot();
    stageScene();
  }
  F.adopt = adopt;

  F.refresh = function () {
    return F.api("/api/forge/state").then(function (s) { adopt(s); return F.runCheck(); })
      .catch(function (err) { F.say(err.message); });
  };

  // The smithy's roar, or the biome's own ground at the field kit (UI plan §11). Lane U6
  // names `ambience.smithy`; Sound answers an unknown name with silence.
  function maybeAmbience() {
    var w = F.state && F.state.where;
    if (!w || ambience || !F.open || !window.Sound || typeof Sound.loop !== "function") return;
    var name = w.smithy ? "smithy" : (w.biome || "");
    if (!name) return;
    try { ambience = Sound.loop("ambience." + name) || null; } catch (err) { ambience = null; }
  }

  // --- the method -----------------------------------------------------------------------------
  F.setMethod = function (id, opts) {
    opts = opts || {};
    if (F.busy || F.live) return null;
    var info = F.methodInfo(id);
    if (!info) return null;
    if (info.locked) {
      F.say(info.name + " is locked. " + (info.lock_reason || ""));
      F.emit("refused", { method: id, why: info.lock_reason });
      return null;
    }
    if (id === "assay") {
      // An assay is worked from a material's ledger card, not on the anvil (contracts §7).
      F.say("Assay a material from its card in the rack: press ? on its row.");
      return null;
    }
    var changed = F.order.method !== id;
    if (!changed && !opts.force) {
      if (opts.focus) focusMethod(id);
      return F.runCheck();
    }
    F.order.method = id;
    if (changed) {
      F.order.slots = {}; F.order.parts = []; F.order.batch = 1; F.order.gear = "weapon";
      F.slotHint = null;
    }
    if (!opts.keepResult) F.result = null;
    remember("pgm.forge.method", id);
    if (changed && !opts.quiet) F.sound("forge.method." + id);
    F.check = null;
    F.emit("method", id);
    stageCall("setTool", id);
    stageWork();
    renderStage();
    if (opts.focus) focusMethod(id);
    return F.runCheck();
  };
  function focusMethod(id) {
    var btn = layer.querySelector('.bm[data-method="' + id + '"]');
    if (btn) btn.focus();
  }

  // --- the order --------------------------------------------------------------------------------
  F.body = function (extra) {
    var o = F.order, slots = {};
    if (o.method === "alloy") {
      o.parts.forEach(function (p) { slots["part-" + p.key] = { key: p.key, count: p.count }; });
    } else {
      Object.keys(o.slots).forEach(function (s) { slots[s] = o.slots[s]; });
    }
    var body = { method: o.method, slots: slots, batch: o.batch };
    if (o.method === "forge") body.shape = o.shape || "";
    if (o.method === "assemble") body.masterwork = !!o.masterwork;
    if (extra) Object.keys(extra).forEach(function (k) { body[k] = extra[k]; });
    return body;
  };

  // Put a rack entry on the work: into `slot` when given (a drop on a slot, or Enter after
  // pressing an empty slot), else the first empty slot the server said it fits, else the
  // first slot it fits (replacing what is there). At Assemble before a main piece, a
  // piece that fits only the other gear's slots turns the order to that gear.
  F.addItem = function (key, slot) {
    var o = F.order;
    if (F.busy || F.live || !o.method) return false;
    var it = F.item(key);
    if (!it) return false;
    if (!F.check || !F.check.fits) {
      F.say("One moment: the forge is still reading what fits.");
      return false;
    }
    var left = it.count - F.inOrder(key);
    if (o.method === "alloy") {
      var why = F.fit("part", key);
      if (why) return refuse(it, why);
      var part = o.parts.filter(function (p) { return p.key === key; })[0];
      if (left <= 0) { F.say("All your " + it.name + " is in the crucible already."); return false; }
      if (part) part.count += 1; else o.parts.push({ key: key, count: 1 });
      F.say(it.name + " in the crucible, " + (part ? part.count : 1) + " in all.");
      return changed(it);
    }
    var target = slot || F.slotHint || pick(key, F.slots());
    if (!target && o.method === "assemble" && !F.hasMain()) {
      var other = o.gear === "weapon" ? "armour" : "weapon";
      target = pick(key, F.slots(other));
      if (target) o.gear = other;
    }
    if (target && F.fit(target, key)) return refuse(it, F.fit(target, key));
    if (!target) return refuse(it, F.why(key) || "it does not go in any slot here");
    if (o.slots[target] === key) { F.say(it.name + " is in the " + label(target) + " slot already."); return false; }
    if (left <= 0) { F.say("All your " + it.name + " is on the work already."); return false; }
    o.slots[target] = key;
    F.slotHint = null;
    F.say(it.name + " in the " + label(target) + " slot.");
    return changed(it);
  };
  function pick(key, slots) {
    var o = F.order, fits = slots.filter(function (s) { return F.fit(s.id, key) === ""; });
    var empty = fits.filter(function (s) { return !o.slots[s.id]; })[0];
    return empty ? empty.id : (fits[0] ? fits[0].id : null);
  }
  function label(slot) {
    var all = F.slots().concat(F.slots(F.order.gear === "weapon" ? "armour" : "weapon"));
    for (var i = 0; i < all.length; i++) if (all[i].id === slot) return all[i].label.toLowerCase();
    return slot;
  }
  function refuse(it, why) {
    F.say(it.name + ": " + why);
    F.emit("refused", { key: it.key, why: why });
    return false;
  }
  function changed(it) {
    F.result = null;
    if (!(F.stage() && stageMounted)) F.sound("forge.drop." + (it.form || "bar"));
    F.emit("order");
    stageWork();
    renderStage();
    F.runCheck();
    return true;
  }
  F.removeSlot = function (slot) {
    if (F.busy || F.live || !F.order.slots[slot]) return;
    var it = F.item(F.order.slots[slot]);
    delete F.order.slots[slot];
    if (F.order.method === "assemble" && !F.hasMain()) F.order.gear = "weapon";
    if (it) F.say(it.name + " taken off the " + label(slot) + " slot.");
    afterRemove();
  };
  F.setPart = function (key, count) {
    if (F.busy || F.live) return;
    var it = F.item(key);
    var o = F.order;
    count = Math.max(0, Math.round(Number(count) || 0));
    if (it) count = Math.min(count, it.count);
    var part = o.parts.filter(function (p) { return p.key === key; })[0];
    if (!part) return;
    if (count <= 0) {
      o.parts = o.parts.filter(function (p) { return p.key !== key; });
      if (it) F.say(it.name + " taken out of the crucible.");
    } else {
      part.count = count;
      if (it) F.say(it.name + ", " + count + " in the crucible.");
    }
    afterRemove();
  };
  function afterRemove() {
    F.result = null;
    F.emit("order");
    stageWork();
    renderStage();
    F.runCheck();
  }
  F.setShape = function (id) {
    if (F.busy || F.live) return;
    F.order.shape = String(id || "");
    F.emit("order");
    F.runCheck();
  };
  F.setAim = function (on) {
    if (F.busy || F.live) return;
    F.order.masterwork = !!on;
    F.emit("order");
    F.runCheck();
  };
  F.setBatch = function (n) {
    n = Math.max(1, Math.round(Number(n) || 1));
    if (n === F.order.batch || F.busy || F.live) return;
    F.order.batch = n;
    F.emit("order");
    renderStage();
    F.runCheck();
  };

  // Ask the server what fits and what the work makes. The newest question wins: an
  // answer to an older order is dropped rather than drawn over a newer one.
  F.runCheck = function () {
    if (!F.order.method || !F.state) return Promise.resolve(null);
    var seq = ++checkSeq;
    F.emit("checking");
    return F.api("/api/forge/check", F.body()).then(function (c) {
      if (seq !== checkSeq) return null;
      F.check = c;
      if (F.order.method === "assemble" && c.gear && F.hasMain()) F.order.gear = c.gear;
      F.emit("check", c);
      stageWork();
      renderStage();
      return c;
    }).catch(function (err) {
      if (seq !== checkSeq) return null;
      // The rack moved under the order (a 409): read it again, the order trims itself.
      if (err.status === 409) { F.refresh(); return null; }
      F.check = { fits: (F.check && F.check.fits) || {}, problems: [err.message], can_roll: false };
      F.emit("check", F.check);
      renderStage();
      return null;
    });
  };

  // --- the stage column (UI plan §6.3) ---------------------------------------------------------
  function mountStage() {
    var st = F.stage();
    var host = $id("forge-tool");
    if (!st || !host || stageMounted || stageMounting) return;
    host.innerHTML = "";
    host.dataset.tool = "";
    host.classList.add("has-stage");
    try {
      stageMounting = Promise.resolve(st.mount(host)).then(function (ok) {
        if (ok === false) throw new Error("no stage here");
        stageMounted = true; stageMounting = null;
        try { st.reducedMotion(F.reduced()); } catch (err) { /* */ }
        stageScene();
        if (F.order.method) stageCall("setTool", F.order.method);
        stageWork();
      }).catch(function () {
        // A stage that cannot draw is the WebGL fallback's case, not an error to show.
        stageMounted = false; stageMounting = null; host.classList.remove("has-stage"); renderStage();
      });
    } catch (err) { stageMounting = null; host.classList.remove("has-stage"); }
  }
  function stageScene() {
    var s = F.state;
    if (!s || !stageMounted) return;
    var w = s.where || {};
    stageCall("setScene", { kind: w.smithy ? (w.smithy.kind === "owned" ? "owned" : "town") : "kit",
                            biome: w.biome || "", roofed: !!w.smithy,
                            minute: s.clock ? s.clock.minute : 720 });
  }
  // What is on the anvil, for the stage: each slot's material, its colour (the server's),
  // passes and folding, the gear and the shape the check named.
  function stageWork() {
    if (!stageMounted) return;
    var o = F.order, pieces = {};
    var put = function (slot, key) {
      var it = F.item(key);
      if (!it) return;
      pieces[slot] = { material: it.material, color: it.color, passes: it.passes || 0,
                       folded: (it.badges || []).indexOf("folded") >= 0 };
    };
    Object.keys(o.slots).forEach(function (s) { put(s, o.slots[s]); });
    o.parts.forEach(function (p, i) { put("part" + i, p.key); });
    var c = F.check || {};
    var main = F.item(o.slots.head || o.slots.body || o.slots.piece || o.slots.item || "");
    stageCall("setWork", { gear: c.gear || (main && main.gear) || o.gear,
                           base: c.shape || o.shape || (main && main.shape) || "",
                           pieces: pieces, quality_index: main && main.quality != null ? main.quality : null,
                           hot_c: null });
  }

  // The flat stand-in: the tool's engraved icon at 160px on the ground (UI plan §6.3,
  // "WebGL fallback"). It is the whole stage until lane U4's arrives.
  function drawFallbackTool() {
    var host = $id("forge-tool");
    if (!host || host.classList.contains("has-stage")) return;
    var m = F.order.method;
    if (host.dataset.tool === (m || "")) return;
    host.dataset.tool = m || "";
    host.innerHTML = "";
    if (!m) return;
    var ring = document.createElement("div");
    ring.className = "bench-flat forge-flat";
    var info = F.methodInfo(m);
    ring.appendChild(F.icon(m, { size: 160, label: info ? info.name : m }));
    var name = document.createElement("span");
    name.className = "bench-flat-name";
    name.textContent = TOOL[m] || m;
    ring.appendChild(name);
    host.appendChild(ring);
  }

  function renderStage() {
    drawFallbackTool();
    var chips = $id("forge-chips"), info = $id("forge-info"), why = $id("forge-why");
    var roll = $id("forge-roll");
    if (!chips || !info || !why || !roll) return;
    var o = F.order, m = o.method;
    // What is on the work: a chip per filled slot or crucible part, each with its ×.
    var rows = [];
    F.slots().forEach(function (s) {
      var it = o.slots[s.id] && F.item(o.slots[s.id]);
      if (it) rows.push({ it: it, x: 'data-unslot="' + esc(s.id) + '"', what: s.label });
    });
    o.parts.forEach(function (p) {
      var it = F.item(p.key);
      if (it) rows.push({ it: it, n: p.count, x: 'data-unpart="' + esc(p.key) + '"', what: "crucible" });
    });
    chips.innerHTML = rows.map(function (r) {
      return '<li class="bench-chip"><i class="fr-swatch" style="--sw:' + esc(r.it.color || "") +
        '" aria-hidden="true"></i><span>' + esc(r.it.name) + (r.n > 1 ? " ×" + r.n : "") +
        '</span><button type="button" class="bench-chip-x" ' + r.x + ' aria-label="Take ' + esc(r.it.name) +
        ' off the ' + esc(String(r.what).toLowerCase()) + '">×</button></li>';
    }).join("");
    chips.hidden = !rows.length;

    var c = F.check, line = "", reason = "";
    if (!F.loading && !F.error && m && c) {
      line = c.info || "";
      reason = (c.problems && c.problems[0]) || (c.need == null && c.impossible ? "No roll can make it: " + c.impossible + "." : "");
    }
    info.textContent = line;
    why.textContent = F.busy ? "" : reason;
    roll.disabled = !!(F.busy || F.live || F.loading || F.error || !c || !c.can_roll || c.need == null);
  }
  F.renderStage = renderStage;

  layer.addEventListener("click", function (e) {
    var x = e.target.closest("[data-unslot]");
    if (x) { F.removeSlot(x.dataset.unslot); return; }
    var p = e.target.closest("[data-unpart]");
    if (p) { F.setPart(p.dataset.unpart, 0); return; }
    if (e.target.closest("#forge-roll")) { F.roll(); }
  });

  // Dropping a rack row on the stage puts it in the first slot it fits (41 starts the drag,
  // 43 takes drops on a slot itself). Drag is never the only way: click or Enter does it.
  var stageEl = $id("forge-stage");
  function dragging(e) {
    return F.dragKey && e.dataTransfer && Array.prototype.indexOf.call(e.dataTransfer.types || [], "text/plain") >= 0;
  }
  function dragOver(on) {
    var tool = $id("forge-tool");
    if (tool) tool.classList.toggle("is-dragover", on);
  }
  if (stageEl) {
    stageEl.addEventListener("dragover", function (e) {
      if (!dragging(e)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
      dragOver(true);
    });
    stageEl.addEventListener("dragleave", function (e) { if (!stageEl.contains(e.relatedTarget)) dragOver(false); });
    stageEl.addEventListener("drop", function (e) {
      if (!dragging(e)) return;
      e.preventDefault();
      dragOver(false);
      var key = F.dragKey;
      F.dragKey = null;
      F.addItem(key);
    });
  }
  document.addEventListener("dragend", function () { if (F.open) { dragOver(false); F.dragKey = null; } });

  // --- the roll (UI plan §5, step 4) -----------------------------------------------------------
  // The table's own d20, thrown by the core exactly as the herb bench throws it.
  F.roll = function () {
    var c = F.check;
    if (F.busy || F.live || !c || !c.can_roll || c.need == null) return null;
    F.busy = true;
    F.result = null;
    F.emit("rolling");
    renderStage();
    var name = c.product && c.product[0] ? c.product[0].name : "Smithing";
    var info = F.methodInfo(F.order.method);
    var body = F.body();
    var heat = c.heat || null;
    var order = JSON.parse(JSON.stringify(F.order));
    return C.rollD20({
      shown: { title: "Craft (blacksmithing)", why: (info ? info.name + ": " : "") + name,
               sides: 20, lo: 1, hi: 20, die: "1d20", terms: C.rollTerms(c) },
      post: function (face) {
        F.sound("forge.roll");
        body.face = face;
        return F.api("/api/forge/roll", body);
      },
      landed: function (r) { tickClock(r.minutes, r.clock); },
      face: function (r) { return r.roll.face; },
      verdict: function (r) { return r.verdict; },
    }).then(function (r) {
      F.busy = false;
      if (r.roll && r.roll.success && r.token) return play(r, heat, order);
      return failed(r).then(focusAfterRoll);
    }).catch(function (err) {
      F.busy = false;
      C.closeMat();
      $id("forge-why").textContent = err.message || String(err);
      F.say(err.message || String(err));
      renderStage();
      focusAfterRoll();
    });
  };
  // Never <body>: Roll Craft if it can roll again, else the rack's row, else Close.
  function focusAfterRoll() {
    core.refocus(["forge-roll", '#forge-rack .fr-add[tabindex="0"]', "forge-close"]);
  }

  function tickClock(minutes, clock) {
    var s = F.state;
    var before = s && s.clock && typeof s.clock.minute === "number" ? s.clock.minute : null;
    if (clock && s) s.clock = clock;
    if (before != null && clock && typeof clock.minute === "number") C.turnClock(before, clock.minute);
    renderFoot();
  }
  F.tickClock = tickClock;

  // --- the failure --------------------------------------------------------------------------------
  function failed(r) {
    F.result = { failed: true, roll: r.roll, lost: r.lost || [], said: r.said || "",
                 minutes: r.minutes, mastery: r.mastery || null };
    flourish("fail");
    F.emit("result", F.result);
    F.say(r.said || "Failure.");
    // The server took what was ruined; the rack is read again so the order agrees with it.
    return F.refresh();
  }

  // --- the game (contracts §11) ----------------------------------------------------------------
  function play(r, heat, order) {
    F.live = { token: r.token, tuning: r.tuning || {}, heat: heat };
    var strip = $id("forge-game");
    strip.hidden = false;
    strip.innerHTML = "";
    void strip.offsetWidth;
    strip.classList.add("is-up");
    layer.classList.add("is-playing");
    F.emit("play", F.live);
    renderStage();
    var games = window.BenchGames, defs = window.BenchGameDefs || {};
    var method = order.method;
    var game;
    if (games && typeof games.play === "function" && defs[method]) {
      var view = stageCall("game", method) || null;
      game = Promise.resolve(games.play({
        method: method, tuning: r.tuning || {}, heat: heat, mount: strip, stage: view,
        steady: F.steady(), reducedMotion: F.reduced(),
        onScore: function (s) { F.emit("score", s); },
      }));
    } else {
      // The forge games are lane U3's; until one is in the build for this method the step
      // still finishes, at a middling score, rather than leaving the materials reserved.
      F.live.flat = true;
      game = Promise.resolve({ score: 0.5, stopped: false, flat: true });
    }
    return game.then(function (out) {
      out = out || {};
      return finish(Number(out.score) || 0, !!out.stopped, Number(out.reheats) || 0, !!out.flat, order);
    }, function (err) {
      // A game that throws is scored as stopped at nothing: materials are never lost to
      // a stop (revamp plan §3), and the server says what came of it.
      console.error("forge game failed:", err);
      return finish(0, true, 0, false, order);
    });
  }

  // --- the finish and the landing --------------------------------------------------------------
  function finish(score, stopped, reheats, flat, order) {
    var live = F.live;
    var strip = $id("forge-game");
    strip.classList.remove("is-up");
    layer.classList.remove("is-playing");
    F.busy = true;
    renderStage();
    return F.api("/api/forge/finish", { token: live.token, score: score, stopped: stopped, reheats: reheats })
      .then(function (f) {
        F.live = null;
        F.busy = false;
        strip.hidden = true;
        strip.innerHTML = "";
        var from = productRect();
        F.order.slots = {}; F.order.parts = []; F.order.batch = 1; F.slotHint = null;
        if (F.order.method === "assemble") F.order.gear = "weapon";
        F.result = { finished: true, finish: f, stopped: stopped, flat: flat, method: order.method };
        // Working a metal reveals its working traits: the ledger's cached cards are stale.
        if ((f.discoveries || []).length && window.ForgeLedger && ForgeLedger.forget) {
          try { ForgeLedger.forget(); } catch (err) { /* */ }
        }
        if (f.state) adopt(f.state);
        tickClock(0, f.state && f.state.clock);
        F.emit("result", F.result);
        land(f, from);
        stageWork();
        renderStage();
        F.runCheck();
        core.refocus(["forge-next", "forge-roll", '#forge-rack .fr-add[tabindex="0"]']);
      }).catch(function (err) {
        F.live = null;
        F.busy = false;
        strip.hidden = true;
        strip.innerHTML = "";
        $id("forge-why").textContent = err.message || String(err);
        renderStage();
        core.refocus(["forge-roll", "forge-close"]);
      });
  }

  function productRect() {
    var r = stageCall("productRect");
    if (r && r.width) return r;
    var tool = document.querySelector("#forge-tool .bicon") || $id("forge-tool");
    return tool ? tool.getBoundingClientRect() : null;
  }

  function land(f, from) {
    var flawless = (Number(f.tier) || 0) >= 4;
    flourish(flawless ? "flawless" : "land", f.tier_name);
    var made = (f.products || [])[0];
    F.say("Made " + (made ? made.name : "it") + (made && made.count > 1 ? ", " + made.count + " of them" : "") +
          (f.tier_name ? ", " + f.tier_name : "") + ".");
    if (!made) return;
    var row = document.querySelector('#forge-rack .fr[data-key="' + F.cssEsc(made.key) + '"]');
    var pulse = function () {
      F.landed = { key: made.key, until: Date.now() + 1400 };
      var now = document.querySelector('#forge-rack .fr[data-key="' + F.cssEsc(made.key) + '"]');
      if (!now) return;
      now.classList.remove("is-landed");
      void now.offsetWidth;
      now.classList.add("is-landed");
      setTimeout(function () { now.classList.remove("is-landed"); }, 1400);
    };
    if (!row) { pulse(); return; }
    if (row.scrollIntoView) row.scrollIntoView({ block: "nearest" });
    var to = row.getBoundingClientRect();
    if (F.reduced() || !from || !to.width || typeof document.body.animate !== "function") { pulse(); return; }
    var el = F.icon(F.rowIcon(made.item || made), { size: 44, label: made.name });
    C.fly(el, from, to).then(pulse);
  }

  function flourish(kind, word) {
    var st = F.stage();
    var staged = false;
    if (st && stageMounted && typeof st.flourish === "function") {
      try { st.reducedMotion(F.reduced()); st.flourish(kind); staged = true; } catch (err) { staged = false; }
    }
    if (!staged) F.sound("forge." + (kind === "fail" ? "fail" : kind === "flawless" ? "flawless" : "land"));
    if (staged && kind !== "flawless") return;
    var tool = document.querySelector("#forge-tool .forge-flat .bicon") || $id("forge-tool");
    if (kind === "fail") { C.dim($id("forge-stage")); return; }
    if (kind === "flawless") C.word(tool, word || "Flawless", !staged);
  }
  F.flourish = flourish;

  // --- the method strip (UI plan §6.1) -----------------------------------------------------------
  // A radio group: one Tab stop, arrows move and choose, 1-9, 0 and - jump. Locked methods
  // stay in the row with the lock and the reason in words in the label itself: the level
  // ("Blacksmith 2") or the place ("Needs a smithy"), never in a tooltip only.
  function renderMethods() {
    var row = $id("forge-methods");
    if (!row) return;
    var list = (F.state && F.state.methods) || [];
    row.innerHTML = "";
    list.forEach(function (m, i) {
      var on = m.id === F.order.method;
      var b = document.createElement("button");
      b.type = "button";
      b.className = "bm" + (m.locked ? " is-locked" : "") + (m.id === "assay" ? " is-card" : "");
      b.dataset.method = m.id;
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.tabIndex = on || (!F.order.method && i === 0) ? 0 : -1;
      if (m.locked) b.setAttribute("aria-disabled", "true");
      var label = m.name + (m.locked && m.lock_reason ? ", " + m.lock_reason : "") +
        (m.id === "assay" && !m.locked ? ", from a material's card" : "");
      b.setAttribute("aria-label", label + ". Key " + (KEYS[i] || ""));
      b.appendChild(m.locked && window.BenchIcons ? BenchIcons.el("lock", { size: 22, label: "lock" })
                                                  : F.icon(m.id, { size: 22, label: m.name }));
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
  F.on("state", renderMethods);
  F.on("method", function () {
    var row = $id("forge-methods");
    if (!row) return;
    row.querySelectorAll(".bm").forEach(function (b) {
      var on = b.dataset.method === F.order.method;
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.tabIndex = on ? 0 : -1;
    });
  });
  var methodsEl = $id("forge-methods");
  if (methodsEl) {
    methodsEl.addEventListener("click", function (e) {
      var b = e.target.closest(".bm");
      if (b) F.setMethod(b.dataset.method, { focus: true });
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
      var info = F.methodInfo(all[to].dataset.method);
      if (info && !info.locked && info.id !== "assay") F.setMethod(info.id, { focus: true });
      else if (info) F.say(info.name + (info.locked ? " is locked. " + (info.lock_reason || "") :
                                                    ": assay a material from its card in the rack."));
    });
  }

  // --- the footer (UI plan §6.8) -------------------------------------------------------------------
  // The core draws the frame; the forge says what is in it: the clock, where you are (the
  // place line decides which methods and metals are open), "Blacksmith" and its numbers,
  // and the Ledger when lane U5's is in the build.
  function footParts() {
    var s = F.state, t = s && s.track;
    return {
      clock: s && s.clock && s.clock.label ? s.clock.label : "",
      place: s && s.where && s.where.line ? s.where.line : "",
      trackLabel: "Your smithing",
      track: t ? { title: "Blacksmith", level: t.level, mp: t.mp,
                   need: t.to_next && t.to_next.need, have: t.to_next && t.to_next.have } : null,
      picks: t && t.picks_banked,
      buttons: window.ForgeLedger && typeof ForgeLedger.journal === "function"
        ? '<button type="button" class="bf-btn" data-forge-ledger>Ledger</button>' : "",
    };
  }
  function renderFoot() { core.renderFoot(); }
  F.renderFoot = renderFoot;
  var footEl = $id("forge-foot");
  if (footEl) {
    footEl.addEventListener("click", function (e) {
      if (e.target.closest("[data-forge-ledger]")) {
        // The Journal's materials ledger (lane U5), in place of the forge, as the herb
        // bench's Herbarium button does.
        F.closeForge();
        if (F.open) return;
        if (typeof Shell === "object" && Shell && Shell.show) Shell.show("journal");
        document.dispatchEvent(new CustomEvent("forge:ledger"));
        setTimeout(function () {
          var at = $id("jr-ledger");
          if (at && at.scrollIntoView) at.scrollIntoView({ block: "start" });
        }, 120);
        return;
      }
      if (e.target.closest("[data-bench-perks]")) F.openPerks();
    });
  }

  // An assay or a lesson from the ledger card (lane U5's 44) took a sliver and passed
  // time: the rack, the clock and the footer are the server's, so they are read again.
  document.addEventListener("forge:learned", function (e) {
    if (!F.open) return;
    var r = e.detail && e.detail.response;
    if (r && r.clock) tickClock(0, r.clock);
    F.refresh();
  });

  // The perk picker (lane U5's 36-bench-perks.js, parameterised by track): the herb
  // picker with the forge's four perks, inside this layer so the trap holds it.
  F.openPerks = function () {
    var t = F.state && F.state.track;
    var P = window.BenchPerks;
    if (!t || !t.picks_banked) return;
    if (!P || typeof P.open !== "function") { F.say("The perk picker is not in this build."); return; }
    P.open({
      track: "blacksmith", state: t, pops: $id("forge-pops"), esc: esc,
      pushEsc: core.pushEsc, dropEsc: core.dropEsc, sound: F.sound, api: F.api,
      home: function () {
        var foot = $id("forge-foot-in");
        return (foot && foot.querySelector("[data-bench-perks]")) || $id("forge-close");
      },
      saved: function (track, picks) {
        if (F.state) F.state.track = track;
        F.emit("state", F.state);
        renderFoot();
        F.say("Perks taken: " + picks.join(", ") + ".");
      },
      afterClose: function () { F.runCheck(); },
    });
  };

  // Buy at the market (the rack's empty state): the table's Trade tab, in place of the forge.
  F.market = function () {
    F.closeForge();
    if (F.open) return;
    if (typeof Shell === "object" && Shell && Shell.show) Shell.show("trade");
  };
})();
