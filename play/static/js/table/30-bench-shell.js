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
// WHO DRAWS WHAT. 29-bench-core.js owns what every bench shares: the layer, open and
// close, Esc and "Stop and keep what you have?", the focus trap and its return, the clock,
// the footer's frame, the confirm, the flourish layer and the one-second rule (split out
// 2026-10-03 so the forge can mount on the same machinery instead of copying it; see the
// head of 29). 30 mounts the herb bench on it and owns the herbs: the method strip, the
// pot, the stage column, the roll, the minigame call and what the footer holds. 31 draws
// the satchel, 34 the result tag, 35 the herbarium card, 36 the perk picker and the recipe
// book. They talk through `Bench.on(event, fn)`, and `window.Bench` keeps every name it had
// before the split, so 31-36 did not change.
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

  var C = window.BenchCore;
  var $id = function (id) { return document.getElementById(id); };
  var esc = C.esc;

  var B = window.Bench = {
    METHODS: METHODS, TOOL: TOOL, DONE: DONE, esc: esc,
    state: null,          // the last /api/bench/state body (contracts §3.1)
    check: null,          // the last /api/bench/check answer for the pot below (§3.2)
    pot: { method: null, items: [], batch: 1 },   // items: [{key, count}]
    // `open` is the core's (a getter, defined where the layer is mounted below).
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

  // --- the shared helpers, from the core (29-bench-core.js) ----------------------------
  // Time in words (UI plan §8), the API with its CSRF and its error sentences, sound,
  // reduced motion and Steady mode are every bench's, so they live in the core; the names
  // stay on `Bench` because 31-36 call them there.
  B.minutes = C.minutes;
  B.span = C.span;
  B.sign = C.sign;
  B.sound = C.sound;
  B.reduced = C.reduced;
  B.steady = C.steady;
  B.setSteady = C.setSteady;
  B.api = C.api;

  // --- the herb stage, optional (contracts §5) -----------------------------------------
  B.stage = function () {
    var s = window.BenchStage;
    try { return s && typeof s.available === "function" && s.available() ? s : null; }
    catch (err) { return null; }
  };
  function remember(key, value) {
    try { window.localStorage.setItem(key, value); } catch (err) { /* private window */ }
  }
  function recall(key) {
    try { return window.localStorage.getItem(key); } catch (err) { return null; }
  }

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

  // --- the layer, mounted on the core (UI plan §4.1) ------------------------------------
  // Open, close, inert, the clock on the stage, Esc one layer at a time, "Stop and keep
  // what you have?", the focus trap and its return, the blur pause and the footer's frame
  // are 29-bench-core.js's. What is the herb bench's own is said here: its ids, its hash
  // (the old /craft/ page's door), the Craft action panel that shuts as the bench opens,
  // the 1-9 keys for the nine methods, and what opening and closing do to the herbs.
  var bench = $id("bench");
  var ambience = null;
  var core = C.mount({
    layer: "bench", close: "bench-close", stage: "bench-stage", say: "bench-say",
    pops: "bench-pops", foot: "bench-foot", footIn: "bench-foot-in", home: "open-bench",
    clockId: "bench-clock", hash: "#bench", bodyClass: "bench-on",
    openWith: "[data-bench-open]",
    // From the Craft action panel: shut it first, so the bench's focus comes back to the
    // panel's own button rather than to a control inside a closed popover.
    openFrom: function (go) {
      var panel = $id("craftpanel");
      if (panel && panel.contains(go)) {
        panel.hidden = true;
        if (typeof shellCraftExpanded === "function") shellCraftExpanded(false);
        return $id("craftaction") || go;
      }
      return go;
    },
    first: ".bm[aria-checked='true']",
    // A method, an ingredient, the roll, the card's study and taste have sounds of their own.
    quiet: ".bm, .bt-add, #bench-roll, [data-hc]",
    live: function () { return !!B.live; },
    // 1-9 pick a method (UI plan §6.1); the core asks only when the player is not typing,
    // no game has the keys and no popover is open.
    keys: function (e) {
      if (/^[1-9]$/.test(e.key) && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        B.setMethod(METHODS[Number(e.key) - 1], { focus: true });
      }
    },
    opened: function () {
      B.sound("bench.open");
      B.emit("open");
      focusFirst();
      load();
    },
    closing: function () {
      if (ambience) { try { ambience.stop(); } catch (err) { /* */ } ambience = null; }
      var stage = B.stage();
      if (stage && stageMounted) { try { stage.unmount(); } catch (err) { /* */ } stageMounted = false; }
      B.emit("close");
    },
    footer: function () { return footParts(); },
  });
  Object.defineProperty(B, "open", { enumerable: true, get: function () { return core.open; } });
  B.openBench = core.openLayer;
  B.closeBench = core.closeLayer;
  B.pushEsc = core.pushEsc;
  B.dropEsc = core.dropEsc;
  B.confirm = core.confirm;
  // Said once to a screen reader (the layer's own status line).
  B.say = core.say;
  function focusFirst() { core.focusFirst(); }

  // /play/#bench, the old bench's "Open the herbalism bench" (craft.html), opens it on load.
  function fromHash() { if (location.hash === "#bench" && !B.open) B.openBench($id("open-bench")); }
  window.addEventListener("hashchange", fromHash);
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

  // (A plain button's `ui.click` is the core's, which skips the ones named in `quiet`.)
  bench && bench.addEventListener("click", function (e) {
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
  // The d20 is the table's own, thrown by the core (29-bench-core.js `rollD20`, moved there
  // 2026-10-04 so the forge throws the same die the same way): Dice3D.ask holds the mat,
  // the server rolls the face (a null face, the old bench's convention, contracts §3.3),
  // Dice3D.land throws it onto that face and showVerdict plays the engine's word. The
  // herb bench says only what goes on the mat and where the face is posted. The game
  // rises only after the player closes the mat, so nothing starts under a mat being read.
  var focusMat = C.focusMat;
  B.focusMat = focusMat;

  B.roll = function () {
    var c = B.check;
    if (B.busy || B.live || !c || !c.can_roll || c.need == null || !B.pot.items.length) return;
    B.busy = true;
    B.result = null;
    B.emit("rolling");
    renderStage();
    var name = c.product && c.product.name ? c.product.name : "Herbalism";
    var body = potBody();
    return C.rollD20({
      shown: { title: "Craft (herbalism)", why: name, sides: 20, lo: 1, hi: 20, die: "1d20",
               terms: C.rollTerms(c) },
      post: function (face) {
        B.sound("bench.roll");
        body.face = face;
        return B.api("/api/bench/roll", body);
      },
      // A success is followed by the step's game: the clock face waits for it (29's turnClock).
      landed: function (r) { tickClock(r.minutes, r.clock, !!(r.roll && r.roll.success && r.token)); },
      face: function (r) { return r.roll.face; },
      verdict: function (r) { return r.verdict; },
    }).then(function (roll) {
      B.busy = false;
      if (roll.roll && roll.roll.success && roll.token) {
        return Promise.resolve(play(roll)).then(
          function (x) { C.releaseClock(); return x; },
          function (e) { C.releaseClock(); throw e; });
      }
      return failed(roll).then(focusAfterRoll);
    }).catch(function (err) {
      B.busy = false;
      C.releaseClock();
      C.closeMat();
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
  function tickClock(minutes, clock, hold) {
    var g = B.state && B.state.ground;
    if (clock && B.state) B.state.clock = clock;
    if (g && typeof g.minute === "number" && minutes) {
      var before = g.minute, after = before + minutes;
      g.minute = after;
      C.turnClock(before, after, hold);
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
      // The games ship with the bench; without them (a broken install) the step still
      // finishes, at a middling score, rather than leaving the materials reserved.
      game = Promise.resolve({ score: 0.5, stopped: false });
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

  // Esc or Close during a game asks "Stop and keep what you have?" (UI plan §4.1): the
  // core's `askStop`, which stops through BenchGames.stop() and so resolves the promise
  // above, and `finish` runs as for any ending.

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
        // Roll Craft is still disabled while the check above answers, and a disabled
        // button refuses focus: the core's refocus never lets it fall to <body> (lane F's
        // found bug, fixed 2026-10-04).
        core.refocus(["bench-next", "bench-roll", '#bench-list .bt-add[tabindex="0"]']);
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

  // The flight itself (500ms along a curve, pointer-events: none, any click finishes it)
  // is the core's; the herb bench only says what flies: the product's own roundel.
  function fly(item, from, to) {
    var el = window.BenchIcons ? BenchIcons.el(item.form || item.part || "leaf", { size: 44, label: item.name })
                               : document.createElement("span");
    return C.fly(el, from, to);
  }

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
    if (kind === "fail") { C.dim($id("bench-stage")); return; }
    // The stage throws its own gilt sparks; the page's are for the flat stand-in only.
    if (kind === "flawless") C.word(tool, word || "Flawless", !staged);
  }
  B.flourish = flourish;

  // (The confirm inside the layer, for taste, stop and delete, is the core's: B.confirm.)

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
  // The core draws the frame (the clock first, the track's level and mastery line, the
  // picks, a gap, then Steady mode last, and the Steady switch's click); the herb bench
  // says what is in it: the scene clock's label, "Herbalist" and its numbers, and its two
  // buttons, Recipes (36 opens it) and Herbarium (below).
  function footParts() {
    var s = B.state, t = s && s.track;
    return {
      clock: s && s.clock && s.clock.label ? s.clock.label : "",
      trackLabel: "Your herbalism",
      track: t ? { title: "Herbalist", level: t.level, mp: t.mp,
                   need: t.to_next && t.to_next.need, have: t.to_next && t.to_next.have } : null,
      picks: t && t.picks_banked,
      buttons: '<button type="button" class="bf-btn" data-bench-recipes aria-haspopup="dialog">Recipes</button>' +
        '<button type="button" class="bf-btn" data-bench-herbarium>Herbarium</button>',
    };
  }
  function renderFoot() { core.renderFoot(); }
  B.renderFoot = renderFoot;
  var footEl = $id("bench-foot");
  if (footEl) {
    footEl.addEventListener("click", function (e) {
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

  // (Reduced motion changing while the bench is open, Steady mode changed in Settings, and
  // the first gesture that unlocks audio are the core's, wired by `mount` above.)

})();
