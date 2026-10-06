// The play table, part 31 (the herbalism bench: the satchel). Classic script in one IIFE,
// talking to the rest of the bench through `window.Bench` (30-bench-shell.js).
//
// UI plan §6.2. Only what you CARRY is here: herbs you have met and do not carry live in
// the herbarium, which retires the old bench's 161-tile wall that showed every herb in
// the game and so gave away properties you had never found. Rows, not a grid, because a
// list of names reads faster than a wall of identical icons (and every leaf looks alike
// until the art arrives, and after it).
//
// Each row says why it cannot go on the tool now, in the server's own words from
// `/api/bench/check` `fits` (contracts §3.2): a dimmed row ALWAYS carries its reason line,
// so dimming never relies on colour alone. The reasons are never worked out here; the
// preparation rules live in one place on the server and this is a picture of them.

(function () {
  "use strict";
  var B = window.Bench;
  if (!B) return;
  var esc = B.esc;
  var root = document.getElementById("bench-satchel-in");
  if (!root) return;

  // The groups, in the order a herbalist works (UI plan §6.2), headed in plain sentence
  // case: no uppercase tracked labels.
  // A jar put up to steep is not on this list: it is In progress until it is collected
  // (the owner's ruling, rules/inprogress.py), and sits in the shared In progress group at
  // the foot (37-works.js, `Works.group`), with the section's own countdown and Collect.
  // Until 2026-10-05 it was this file's own "Steeping" group, with a countdown worked out
  // here from `ready_at` and no Collect at all: a finished jar said "ready now" and could
  // be neither used nor taken out (lane G's report; no Collect button anywhere).
  var GROUPS = ["Fresh herbs", "Dried", "Powders", "Oils", "Bases", "Liquids", "Monster parts",
                "Crafted"];
  var BEAST = { gland: 1, organ: 1, bone: 1, horn: 1, feather: 1, scale: 1, eye: 1, shell: 1 };
  var SHOWS = [["fits", "What fits"], ["all", "Everything I carry"], ["crafted", "Crafted"]];
  var show = "fits", find = "";

  function held(it) { return it.ready_at != null; }
  function groupOf(it) {
    if (it.form === "infused-oil" || it.part === "oil") return "Oils";
    if (it.form === "salve-base" || it.part === "wax") return "Bases";
    if (it.crafted) return "Crafted";
    if (it.state === "dried") return "Dried";
    if (it.state === "ground") return "Powders";
    if (it.part === "liquid") return "Liquids";
    if (BEAST[it.part] || it.kind === "monster part") return "Monster parts";
    return "Fresh herbs";
  }

  // The frame: the search with its label ABOVE the field (never a placeholder standing in
  // for one), the filter beside it, and the list. Drawn once; the list is redrawn.
  root.innerHTML =
    '<div class="bs-head">' +
      '<label class="bs-label" for="bench-find">Search your satchel</label>' +
      '<input type="search" id="bench-find" class="v2-well bs-find" autocomplete="off" spellcheck="false">' +
      '<div class="bs-showrow"><label class="bs-label" for="bench-show">Show</label>' +
      '<select id="bench-show" class="v2-well bs-show">' +
      SHOWS.map(function (s) { return '<option value="' + s[0] + '">' + s[1] + '</option>'; }).join("") +
      '</select></div>' +
    '</div>' +
    '<div class="bs-list" id="bench-list" aria-live="off"></div>';
  var list = document.getElementById("bench-list");
  var findEl = document.getElementById("bench-find");
  var showEl = document.getElementById("bench-show");
  findEl.addEventListener("input", function () { find = findEl.value.trim().toLowerCase(); draw(); });
  showEl.addEventListener("change", function () { show = showEl.value; draw(); });
  B.showEverything = function () { show = "all"; showEl.value = "all"; draw(); showEl.focus(); };

  // --- a row ------------------------------------------------------------------------------
  function row(it, why) {
    var left = it.count - B.inPot(it.key);
    var dim = !!why;
    var badges = [];
    if (it.state && it.state !== "raw") badges.push(it.state);
    if (it.crafted && it.form) badges.push(it.form.replace("-", " "));
    if (it.quality_name) badges.push(it.quality_name);
    var lines = [];
    if (it.spoils_in != null && it.spoils_in <= 1440) {
      lines.push('<span class="bt-time is-soon">spoils in ' + esc(B.span(it.spoils_in)) + '</span>');
    }
    if (dim) lines.push('<span class="bt-why" id="bt-why-' + esc(it.key) + '">' + esc(why) + '</span>');
    var herb = it.ingredient_id && !it.crafted;
    var glyph = it.form || it.part || it.kind || "leaf";
    var icon = window.BenchIcons ? BenchIcons.html(glyph,
                                                    { size: 30, tier: it.tier, label: it.name }) : "";
    var unknown = it.unknown > 0;
    var label = it.name + ", " + left + " in your satchel" +
      (badges.length ? ", " + badges.join(", ") : "") + (unknown ? ", " + it.unknown + " unknown" : "") + ".";
    return '<li class="bt' + (dim ? " is-dim" : "") + (herb ? " has-info" : "") + '" data-key="' + esc(it.key) + '">' +
      '<button type="button" class="bt-add" data-add="' + esc(it.key) + '"' +
      (dim ? ' aria-disabled="true" aria-describedby="bt-why-' + esc(it.key) + '"' : ' draggable="true"') +
      ' aria-label="' + esc(label) + '">' +
        '<span class="bt-icon">' + icon + '</span>' +
        '<span class="bt-main"><span class="bt-name">' + esc(it.name) + '</span>' +
          (badges.length ? '<span class="bt-badges">' + badges.map(function (b) {
            return '<span class="bt-badge">' + esc(b) + '</span>'; }).join("") + '</span>' : "") +
          lines.join("") +
        '</span>' +
        '<span class="bt-count">' + esc(left) + '</span>' +
      '</button>' +
      (herb ? '<button type="button" class="bt-info' + (unknown ? " is-unknown" : "") + '" data-herb="' +
        esc(it.ingredient_id) + '" data-for="' + esc(it.key) + '" aria-haspopup="dialog" aria-label="About ' +
        esc(it.name) + (unknown ? ", " + it.unknown + " unknown" : "") + '">?</button>' : "") +
      '</li>';
  }

  function group(title, items, whyOf) {
    if (!items.length) return "";
    return '<section class="bs-group"><h3 class="bs-gh">' + esc(title) + '</h3><ul class="bs-rows">' +
      items.map(function (it) { return row(it, whyOf(it)); }).join("") + '</ul></section>';
  }

  // --- the list ---------------------------------------------------------------------------
  function draw() {
    if (B.loading) { skeleton(); return; }
    if (B.error) {
      list.innerHTML = '<div class="bs-state"><p>Couldn\'t load your satchel.</p>' +
        '<p class="bs-detail">' + esc(B.error) + '</p>' +
        '<button type="button" class="v2-btn is-small" data-bench-retry>Retry</button></div>';
      return;
    }
    var all = ((B.state && B.state.satchel) || []).filter(function (it) { return it.count > 0; });
    if (!all.length) {
      list.innerHTML = '<div class="bs-state"><p>Your satchel is empty. Forage or buy herbs and they appear here.</p>' +
        '<button type="button" class="v2-btn is-small" data-bench-forage>Forage here</button></div>';
      return;
    }
    // In progress is not the satchel's: those jars are drawn by the shared group below.
    var free = all.filter(function (it) { return !held(it); });
    var shown = free.filter(function (it) { return !find || it.name.toLowerCase().indexOf(find) >= 0; });
    var why = function (it) { return B.why(it.key); };
    var html = "";
    var byGroup = function (items, whyOf) {
      var out = "";
      GROUPS.forEach(function (g) {
        out += group(g, items.filter(function (it) { return groupOf(it) === g; }), whyOf);
      });
      return out;
    };
    if (show === "crafted") {
      html = byGroup(shown.filter(function (it) { return it.crafted; }), why);
      if (!html && !find) html = '<div class="bs-state"><p>Nothing crafted yet.</p></div>';
    } else if (show === "all") {
      html = byGroup(shown, why);
    } else {
      // What fits first, by kind; then everything that cannot go on the tool now, each
      // with its reason; then (below) what is in progress.
      var fits = shown.filter(function (it) { return !why(it); });
      var not = shown.filter(function (it) { return !!why(it); });
      var m = B.pot.method;
      if (!fits.length && m && free.length) {
        html += '<div class="bs-state"><p>Nothing you carry can be ' + esc(B.DONE[m]) + '.</p>' +
          '<div class="bs-acts"><button type="button" class="v2-btn is-small" data-bench-forage>Forage here</button>' +
          '<button type="button" class="v2-btn is-small is-quiet" data-bench-everything>Everything I carry</button></div></div>';
      }
      html += byGroup(fits, why);
      html += group("Can't use now", not, why);
    }
    if (!html && find) html = '<div class="bs-state"><p>Nothing in your satchel matches "' + esc(find) + '".</p></div>';
    else if (!html && !free.length) html = '<div class="bs-state"><p>Everything you carry is in progress.</p></div>';
    // The shared In progress group (37-works.js), this craft's rows only, at the foot.
    html += '<div class="wk-host" id="bench-works"></div>';
    // Keep the keyboard where it was: a redraw replaces the rows, so the focused row is
    // found again by its key.
    var had = document.activeElement && list.contains(document.activeElement) ? document.activeElement : null;
    var hadKey = had ? (had.dataset.add || had.dataset.for) : null;
    var hadInfo = had && had.classList.contains("bt-info");
    var scroll = list.scrollTop;
    list.innerHTML = html;
    works(all);
    list.scrollTop = scroll;
    rove();
    if (B.landed && Date.now() < B.landed.until) {
      var landed = list.querySelector('.bt[data-key="' + cssEsc(B.landed.key) + '"]');
      if (landed) landed.classList.add("is-landed");
    }
    if (hadKey) {
      var again = list.querySelector((hadInfo ? '.bt-info[data-for="' : '.bt-add[data-add="') + cssEsc(hadKey) + '"]');
      if (again) again.focus();
    }
  }
  function cssEsc(s) { return window.CSS && CSS.escape ? CSS.escape(s) : String(s); }

  // The group is drawn from the rows the section last sent, and asked again when the clock
  // has turned or what is in progress has changed (a jar put up, one collected): every step
  // at the bench passes time, so the countdown moves with each one, on game time.
  function works(all) {
    var W = window.Works, host = document.getElementById("bench-works");
    if (!W || !host) return;
    W.group(host, "herbalist");
    var clock = B.state && B.state.clock;
    var keys = all.filter(held).map(function (it) { return it.key + ":" + (it.work_state || ""); }).join(",");
    W.sync("bench|" + (clock && clock.minute != null ? clock.minute : "") + "|" + keys);
  }
  // A jar collected from the group comes back onto the shelf as the tincture it always was:
  // the satchel is read again and the row it landed on pulses, as a finished step's does.
  document.addEventListener("works:collected", function (e) {
    if (!B.open) return;
    var made = e.detail && e.detail.product;
    Promise.resolve(B.refresh()).then(function () {
      if (!made || !made.key) return;
      B.landed = { key: made.key, until: Date.now() + 1400 };
      draw();
      var tile = list.querySelector('.bt[data-key="' + cssEsc(made.key) + '"]');
      if (tile && tile.scrollIntoView) tile.scrollIntoView({ block: "nearest" });
      // The Collect pressed has gone with its row; the keyboard goes where the jar went,
      // not to <body>.
      var add = tile && tile.querySelector(".bt-add");
      var at = document.activeElement;
      if (add && (!at || at === document.body || !document.contains(at))) add.focus();
    });
  });
  document.addEventListener("works:stopped", function () { if (B.open) B.refresh(); });

  // One Tab stop for the whole list (a roving tabindex): the row last visited, else the
  // first, and its "?". ↑ and ↓ walk the rows. Without it every row was two Tab stops: 26
  // stops in the list alone on the fake's fourteen things (counted from the markup), all
  // between the search box and Roll Craft.
  var roveKey = null;
  function rove() {
    var rows = list.querySelectorAll(".bt-add[data-add]");
    if (!rows.length) return;
    var pick = roveKey && list.querySelector('.bt-add[data-add="' + cssEsc(roveKey) + '"]');
    if (!pick) pick = rows[0];
    list.querySelectorAll(".bt-add[data-add], .bt-info").forEach(function (b) { b.tabIndex = -1; });
    pick.tabIndex = 0;
    var info = pick.parentNode.querySelector(".bt-info");
    if (info) info.tabIndex = 0;
  }
  list.addEventListener("focusin", function (e) {
    var add = e.target.closest(".bt-add[data-add]") || (e.target.closest(".bt") && e.target.closest(".bt").querySelector(".bt-add[data-add]"));
    if (!add || add.dataset.add === roveKey) return;
    roveKey = add.dataset.add;
    rove();
  });

  // Six rows shaped like tiles while the satchel loads (no spinner, UI plan §7).
  function skeleton() {
    var one = '<li class="bt is-skel" aria-hidden="true"><span class="bt-add"><span class="bt-icon"><span class="sk-disc"></span></span>' +
      '<span class="bt-main"><span class="sk-bar"></span><span class="sk-bar is-short"></span></span></span></li>';
    list.innerHTML = '<p class="vh">Loading your satchel.</p><ul class="bs-rows">' + new Array(7).join(one) + '</ul>';
  }

  B.on("loading", draw);
  B.on("error", draw);
  B.on("state", draw);
  B.on("check", draw);
  B.on("pot", draw);
  B.on("method", draw);

  // --- adding: click, Enter, or drag (UI plan §5, step 3) -------------------------------
  list.addEventListener("click", function (e) {
    if (e.target.closest("[data-bench-retry]")) { B.reload(); return; }
    if (e.target.closest("[data-bench-forage]")) { B.forage(); return; }
    if (e.target.closest("[data-bench-everything]")) { B.showEverything(); return; }
    var info = e.target.closest(".bt-info");
    if (info) { B.emit("herb", { id: info.dataset.herb, key: info.dataset.for, el: info, pin: true }); return; }
    var add = e.target.closest(".bt-add[data-add]");
    if (!add) return;
    if (!B.addItem(add.dataset.add)) {
      // Refused: the reason is already on the row; bring it forward for a beat.
      var li = add.closest(".bt");
      if (li) { li.classList.remove("is-refused"); void li.offsetWidth; li.classList.add("is-refused"); }
    }
  });

  // ↑ and ↓ move along the rows, so a long satchel is one Tab stop's worth of travel.
  list.addEventListener("keydown", function (e) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    var here = e.target.closest(".bt-add");
    if (!here) return;
    var rows = Array.prototype.slice.call(list.querySelectorAll(".bt-add[data-add]"));
    var i = rows.indexOf(here);
    var to = rows[i + (e.key === "ArrowDown" ? 1 : -1)];
    if (to) { e.preventDefault(); to.focus(); }
  });

  list.addEventListener("dragstart", function (e) {
    var add = e.target.closest && e.target.closest(".bt-add[data-add]");
    if (!add || add.getAttribute("aria-disabled") === "true") { e.preventDefault(); return; }
    B.dragKey = add.dataset.add;
    e.dataTransfer.effectAllowed = "copy";
    e.dataTransfer.setData("text/plain", add.dataset.add);
  });

  // --- the herbarium card on hover and focus (UI plan §6.2) ------------------------------
  // Hover is never required: the card also opens on focus and on the "?" button. Hover
  // waits a beat so a pointer crossing the list does not flash a card per row.
  var hoverT = 0;
  function peek(el, now) {
    var li = el && el.closest(".bt.has-info");
    clearTimeout(hoverT);
    if (!li) { B.emit("unpeek"); return; }
    var info = li.querySelector(".bt-info");
    var go = function () { B.emit("herb", { id: info.dataset.herb, key: info.dataset.for, el: li, pin: false }); };
    if (now) go(); else hoverT = setTimeout(go, 280);
  }
  list.addEventListener("mouseover", function (e) {
    if (e.target.closest(".bt.has-info")) peek(e.target, false);
  });
  list.addEventListener("mouseleave", function () { clearTimeout(hoverT); B.emit("unpeek"); });
  list.addEventListener("focusin", function (e) {
    if (e.target.closest(".bt-add")) peek(e.target, true);
  });
  list.addEventListener("focusout", function (e) {
    if (!list.contains(e.relatedTarget)) { clearTimeout(hoverT); B.emit("unpeek"); }
  });
})();
