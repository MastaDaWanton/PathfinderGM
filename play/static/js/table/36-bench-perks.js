// The play table, part 36 (the herbalism bench: the perk picker and the recipe book, the
// footer's two dialogs). Classic script in one IIFE, reached through `window.Bench`.
//
// THE PERK PICKER (UI plan §6.7). Past Herbalist 3 every level banks two picks from four
// perks, the same one twice allowed (revamp plan §4.2). A 2×2 grid of choices, not three
// equal cards; Confirm stays disabled until the picks are made. Banked picks wait without
// nagging: the footer's "2 perks to pick" is the only reminder, and the picker opens by
// itself once only, on the first open of the bench that finds picks waiting (the
// migration's "perks picked on first load", revamp plan §14).
//
// What a perk does at your next pick is the server's number. CONTRACT GAP (in the lane's
// hand-back): §3.1's `track` carries only `perks` (how many of each) and `picks_banked`,
// so `track.perk_info[id].next` is read when present and otherwise the perk is described
// in words with no number, rather than a number invented here.
//
// THE RECIPE BOOK (UI plan §6.8, revamp plan §9.6). Loading a recipe sets the method and
// pre-drops its ingredients; you still roll and still play, and each finished step offers
// the next ("Next: Mix", 34-bench-tag.js). Save recipe keeps the steps finished since the
// bench opened, and the pot on the tool now.

(function () {
  "use strict";
  var B = window.Bench;
  if (!B) return;
  var esc = B.esc;
  var pops = document.getElementById("bench-pops");
  var foot = document.getElementById("bench-foot");
  if (!pops) return;

  var PERKS = [
    { id: "potency", name: "Potency", words: "Your products are stronger." },
    { id: "duration", name: "Duration", words: "Your products last longer." },
    { id: "quality", name: "Quality", words: "Your ceiling rises one rung." },
    { id: "yield", name: "Extra yield", words: "A chance of an extra dose from each batch." },
  ];
  var ICON = { potency: "reagent", duration: "steeping", quality: "salve", yield: "seed" };

  // A modal of the bench's own, inside its stacking context, with its own Esc and the
  // focus handed back on close (the shell's trap wraps Tab inside `.bench-modal`).
  function modal(labelId) {
    var wrap = document.createElement("div");
    wrap.className = "bench-modal";
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-modal", "true");
    wrap.setAttribute("aria-labelledby", labelId);
    pops.appendChild(wrap);
    return wrap;
  }

  // --- perks ------------------------------------------------------------------------------
  var picker = null;
  function openPerks() {
    var t = B.state && B.state.track;
    if (!t || !t.picks_banked || picker) return;
    var back = document.activeElement;
    var need = Math.min(2, t.picks_banked);
    var picks = [];
    var err = "";
    var wrap = modal("bench-perks-t");
    picker = wrap;
    B.sound("ui.open");
    var close = function () {
      B.dropEsc(close);
      wrap.remove();
      picker = null;
      B.sound("ui.close");
      var again = foot && foot.querySelector("[data-bench-perks]");
      ((back && document.contains(back)) ? back : again || document.getElementById("bench-close")).focus();
    };
    B.pushEsc(close);
    var draw = function (focusId) {
      var info = t.perk_info || {};
      wrap.innerHTML = '<div class="bench-scrim"></div><div class="bench-dialog bench-perks v2-framed v2-card-leather">' +
        '<i class="v2-rim" aria-hidden="true"></i>' +
        '<h3 id="bench-perks-t">' + (need === 1 ? "Pick a perk" : "Pick two perks") + '</h3>' +
        '<p>Herbalist ' + esc(t.level) + '. The same perk twice is allowed.</p>' +
        '<div class="pk-grid">' + PERKS.map(function (p) {
          var mine = picks.filter(function (x) { return x === p.id; }).length;
          var taken = (t.perks && t.perks[p.id]) || 0;
          var next = info[p.id] && info[p.id].next ? info[p.id].next : p.words;
          return '<button type="button" class="pk' + (mine ? " is-on" : "") + '" data-perk="' + p.id + '" aria-pressed="' + (mine > 0) + '">' +
            (window.BenchIcons ? BenchIcons.html(ICON[p.id], { size: 34, label: p.name }) : "") +
            '<span class="pk-main"><b>' + esc(p.name) + (mine ? ' <span class="pk-x">×' + mine + '</span>' : "") + '</b>' +
            '<span class="pk-next">' + esc(next) + '</span>' +
            '<span class="pk-taken">' + (taken ? "Taken " + taken + (taken === 1 ? " time" : " times") : "Not taken yet") + '</span></span></button>';
        }).join("") + '</div>' +
        '<p class="pk-left" role="status">' + (picks.length < need ? (need - picks.length) + " to pick" : "Ready to confirm") + '</p>' +
        (err ? '<p class="bench-warnline">' + esc(err) + '</p>' : "") +
        '<div class="bench-dialog-acts"><button type="button" class="v2-btn is-quiet" data-pk="later">Later</button>' +
        '<button type="button" class="v2-btn is-quiet" data-pk="clear"' + (picks.length ? "" : " disabled") + '>Clear</button>' +
        '<button type="button" class="v2-btn is-go" data-pk="ok"' + (picks.length === need ? "" : " disabled") + '>Confirm</button></div></div>';
      var f = focusId ? wrap.querySelector(focusId) : wrap.querySelector(".pk");
      if (f && !f.disabled) f.focus(); else { var any = wrap.querySelector(".pk"); if (any) any.focus(); }
    };
    wrap.addEventListener("click", function (e) {
      var p = e.target.closest("[data-perk]");
      if (p) {
        var id = p.dataset.perk;
        if (picks.length < need) picks.push(id);
        else {
          var at = picks.lastIndexOf(id);
          if (at >= 0) picks.splice(at, 1);
        }
        err = "";
        draw('[data-perk="' + id + '"]');
        return;
      }
      var a = e.target.closest("[data-pk]");
      if (!a) { if (e.target.closest(".bench-scrim")) close(); return; }
      if (a.dataset.pk === "later") { close(); return; }
      if (a.dataset.pk === "clear") { picks = []; draw(); return; }
      if (a.dataset.pk === "ok" && picks.length === need) {
        a.disabled = true;
        B.api("/api/bench/perks", { picks: picks.slice() }).then(function (track) {
          if (B.state) B.state.track = track;
          B.emit("state", B.state);
          B.renderFoot();
          B.say("Perks taken: " + picks.join(", ") + ".");
          close();
          B.runCheck();
        }).catch(function (e2) {
          // The picks are kept, so a retry is one press (UI plan §7).
          err = "Couldn't save your picks. " + (e2.message || "") + " Try again.";
          draw('[data-pk="ok"]');
        });
      }
    });
    draw();
  }
  B.openPerks = openPerks;

  var prompted = false;
  B.on("state", function (s) {
    if (prompted || !B.open || !s || !s.track || !s.track.picks_banked) return;
    try { if (window.sessionStorage.getItem("pgm.bench.perks.asked") === "1") { prompted = true; return; } }
    catch (err) { /* private window: ask once per page */ }
    prompted = true;
    try { window.sessionStorage.setItem("pgm.bench.perks.asked", "1"); } catch (err) { /* */ }
    setTimeout(openPerks, 60);
  });

  // --- recipes ----------------------------------------------------------------------------
  var book = null;
  function stepsNow() {
    var steps = B.chain.slice();
    if (B.pot.items.length) {
      steps.push({ method: B.pot.method, items: B.pot.items.map(function (p) {
        var it = B.item(p.key);
        return { ingredient_id: it ? it.ingredient_id : null, count: p.count };
      }).filter(function (x) { return x.ingredient_id; }) });
    }
    return steps.filter(function (s) { return s.items.length; });
  }
  function methodName(id) { var m = B.methodInfo(id); return m ? m.name : id; }

  function openRecipes() {
    if (book) return;
    var back = document.activeElement;
    var wrap = modal("bench-recipes-t");
    book = wrap;
    var note = "";
    var close = function () {
      B.dropEsc(close);
      wrap.remove();
      book = null;
      if (back && document.contains(back)) back.focus();
    };
    B.pushEsc(close);
    var draw = function (focusSel) {
      var list = (B.state && B.state.recipes) || [];
      var steps = stepsNow();
      var suggest = B.check && B.check.product ? B.check.product.name : "";
      wrap.innerHTML = '<div class="bench-scrim"></div><div class="bench-dialog bench-recipes v2-framed v2-card-leather">' +
        '<i class="v2-rim" aria-hidden="true"></i>' +
        '<h3 id="bench-recipes-t">Recipes</h3>' +
        (list.length ? '<ul class="rc-list">' + list.map(function (r) {
          return '<li><span class="rc-main"><b>' + esc(r.name) + '</b><span class="rc-steps">' +
            esc((r.steps || []).map(function (s) { return methodName(s.method); }).join(", then ")) + '</span></span>' +
            '<button type="button" class="v2-btn is-small" data-rc-load="' + esc(r.id) + '">Load</button>' +
            '<button type="button" class="v2-btn is-small is-quiet" data-rc-del="' + esc(r.id) + '" aria-label="Delete ' + esc(r.name) + '">Delete</button></li>';
        }).join("") + '</ul>' : '<p class="rc-empty">No recipes yet. Make something, then save the steps you took.</p>') +
        '<div class="rc-save"><label for="bench-rc-name">Name</label>' +
        '<input type="text" id="bench-rc-name" class="v2-well" value="' + esc(suggest) + '" autocomplete="off">' +
        '<button type="button" class="v2-btn is-small" data-rc-save' + (steps.length ? "" : " disabled") + '>Save recipe</button></div>' +
        '<p class="rc-note" role="status">' + esc(note || (steps.length ? "Saves " + steps.map(function (s) { return methodName(s.method); }).join(", then ") + "." :
          "Nothing to save yet: finish a step or put something on the tool.")) + '</p>' +
        '<div class="bench-dialog-acts"><button type="button" class="v2-btn is-quiet" data-rc-close>Close</button></div></div>';
      var f = focusSel && wrap.querySelector(focusSel);
      (f || wrap.querySelector("[data-rc-load]") || wrap.querySelector("#bench-rc-name")).focus();
    };
    wrap.addEventListener("click", function (e) {
      if (e.target.closest("[data-rc-close]") || e.target.closest(".bench-scrim")) { close(); return; }
      var load = e.target.closest("[data-rc-load]");
      if (load) {
        var r = ((B.state && B.state.recipes) || []).filter(function (x) { return x.id === load.dataset.rcLoad; })[0];
        if (!r || !r.steps || !r.steps.length) return;
        close();
        B.recipe = { recipe: r, step: 0 };
        loadStep(r.steps[0]);
        return;
      }
      var del = e.target.closest("[data-rc-del]");
      if (del) {
        var id = del.dataset.rcDel;
        B.confirm({ title: "Delete this recipe?", body: "It goes from your recipe book for good.", ok: "Delete", cancel: "Keep it", danger: true })
          .then(function (yes) {
            if (!yes) return;
            return B.api("/api/bench/recipe", { "delete": id }).then(function (res) {
              if (B.state) B.state.recipes = res.recipes;
              note = "Recipe deleted.";
              draw("[data-rc-close]");
            });
          }).catch(function (err) { note = err.message; draw(); });
        return;
      }
      if (e.target.closest("[data-rc-save]")) {
        var name = (wrap.querySelector("#bench-rc-name").value || "").trim();
        if (!name) { note = "Give the recipe a name."; draw("#bench-rc-name"); return; }
        B.api("/api/bench/recipe", { name: name, steps: stepsNow() }).then(function (res) {
          if (B.state) B.state.recipes = res.recipes;
          B.chain = [];
          note = "Saved " + name + ".";
          draw("[data-rc-close]");
        }).catch(function (err) { note = err.message; draw("[data-rc-save]"); });
      }
    });
    draw();
  }

  // Set the step's method, then pre-drop what it calls for from what is carried. A thing
  // not carried is said, not guessed at: the bench never swaps in a substitute.
  function loadStep(step) {
    return Promise.resolve(B.setMethod(step.method, { focus: true })).then(function () {
      var missing = [];
      (step.items || []).forEach(function (want) {
        var have = ((B.state && B.state.satchel) || []).filter(function (it) {
          return it.ingredient_id === want.ingredient_id && it.count > 0 && !B.why(it.key);
        })[0];
        if (!have) { missing.push(want.ingredient_id); return; }
        B.addItem(have.key, want.count);
      });
      if (missing.length) B.say("Not carried, or not ready for this step: " + missing.join(", ") + ".");
    });
  }
  B.loadStep = loadStep;

  if (foot) {
    foot.addEventListener("click", function (e) {
      if (e.target.closest("[data-bench-perks]")) { openPerks(); return; }
      if (e.target.closest("[data-bench-recipes]")) { openRecipes(); }
    });
  }
})();
