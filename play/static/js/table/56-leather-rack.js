// The play table, part 56 (the leather bench: the rack). Classic script in one IIFE, talking
// to the rest of the bench through `window.Leather` (55-leather-shell.js).
//
// UI plan §6.2, the forge rack's pattern for leather. Only what you CARRY is here (the old
// Leatherworking tab's wall of 127 materials with emoji glyphs is retired, UI plan §2). Rows
// are grouped in the order a tanner works, the group names the server's (`group` on each row):
// Green hides, Salted hides, Pelts, Leather and rawhide, Panels and plates, Bases and grips,
// Scraps, Tannins, Oils and waxes, Threads and lacing, Dyes, Salt and treatments, Fittings,
// Finished work, Old work; then the shared In progress group (37), where a tannage waits.
//
// A row: the form's engraved icon with its rarity rim and the hide's GRADE NOTCHES (four for
// grade 1 down to one for grade 4: shape, never hue, so a colour-blind player reads the grade
// the same way, UI plan §4), the material's swatch (content, never meaning alone), the name,
// the count, the hide units and the grade in words, state badges, and the SPOIL CLOCK of a
// green hide: the server's words first ("spoils in 2 days unless salted or tanned"), then a
// strip of eight segments of six hours each with no filled track behind it. Under twelve
// hours left the words turn --alarm and gain "soon". A row that cannot go on the work now is
// dimmed AND carries the server's reason in words.
//
// NO SCROLL JUMP (UI plan §6.2, the old tab's defect): the list is redrawn in place, its
// scrollTop read before and put back after, and the focused row found again by its key.
//
// THE "?" ONLY (the owner's emergency fix of 2026-10-08): a material's card opens from the
// row's "?" button and nothing else. Hovering or focusing a row opens nothing; a card opened by
// a row covered the rows under it and made the list unusable.

(function () {
  "use strict";
  var L = window.Leather;
  if (!L) return;
  var esc = L.esc;
  var root = document.getElementById("leather-rack-in");
  if (!root) return;

  var GROUPS = ["Green hides", "Salted hides", "Pelts (fleshed)", "Leather and rawhide", "Panels and plates",
                "Bases and grips", "Scraps", "Tannins", "Oils and waxes", "Threads and lacing", "Dyes",
                "Salt and treatments", "Fittings", "Finished work", "Old work"];
  var SHOWS = [["fits", "What fits"], ["all", "Everything I carry"]];
  // Grade notches by grade, a lookup and not a sum (the page computes no number).
  var NOTCH = { 1: 4, 2: 3, 3: 2, 4: 1 };
  var SEGMENTS = 8, SEGMENT_HOURS = 6;
  var show = "fits", find = "";

  root.innerHTML =
    '<div class="bs-head">' +
      '<label class="bs-label" for="leather-find">Search your rack</label>' +
      '<input type="search" id="leather-find" class="v2-well bs-find" autocomplete="off" spellcheck="false">' +
      '<div class="bs-showrow"><label class="bs-label" for="leather-show">Show</label>' +
      '<select id="leather-show" class="v2-well bs-show">' +
      SHOWS.map(function (s) { return '<option value="' + s[0] + '">' + s[1] + '</option>'; }).join("") +
      '</select></div>' +
    '</div>' +
    '<div class="bs-list lr-list" id="leather-list" aria-live="off"></div>';
  var list = document.getElementById("leather-list");
  var findEl = document.getElementById("leather-find");
  var showEl = document.getElementById("leather-show");
  findEl.addEventListener("input", function () { find = findEl.value.trim().toLowerCase(); draw(); });
  showEl.addEventListener("change", function () { show = showEl.value; draw(); });
  L.showEverything = function () { show = "all"; showEl.value = "all"; draw(); showEl.focus(); };

  function left(it) { return it.count - L.inOrder(it.key); }

  // --- the spoil clock (UI plan §4) --------------------------------------------------------------
  function clockHtml(it) {
    var k = it.clock;
    if (!k || !k.why) return "";
    if (!k.clock) return '<span class="lr-clock is-kept">' + esc(k.why) + '</span>';
    var hours = Number(k.hours_left) || 0;
    var soon = !k.spoiled && hours < 12;
    var segs = "";
    for (var i = 0; i < SEGMENTS; i++) {
      segs += '<i' + (hours > i * SEGMENT_HOURS ? ' class="is-on"' : "") + '></i>';
    }
    return '<span class="lr-clock' + (soon || k.spoiled ? " is-soon" : "") + '">' +
      '<span class="lr-clock-words">' + esc(k.why) + (soon ? ", soon" : "") + '</span>' +
      (k.spoiled ? "" : '<span class="lr-strip" aria-hidden="true">' + segs + '</span>') + '</span>';
  }
  L.clockHtml = clockHtml;
  function notches(it) {
    var n = NOTCH[it.grade];
    if (it.grade == null || it.form === "item") return "";
    var out = "";
    for (var i = 0; i < 4; i++) out += '<i' + (n && i < n ? ' class="is-on"' : "") + '></i>';
    return '<span class="lr-notches" aria-hidden="true">' + out + '</span>';
  }

  // --- a row ---------------------------------------------------------------------------------
  function row(it, why) {
    var dim = !!why;
    var badges = (it.badges || []).slice();
    if (it.quality_name) badges.push(it.quality_name);
    var n = left(it);
    var info = !!it.material && it.form !== "item" && !it.old;
    var unknown = it.unknown > 0;
    var meta = [];
    if (it.units_words) meta.push(it.units_words + (it.count > 1 ? " each" : ""));
    if (it.grade_words) meta.push(it.grade_words);
    var lines = [];
    if (meta.length) lines.push('<span class="lr-meta">' + esc(meta.join(", ")) + '</span>');
    var clock = clockHtml(it);
    if (clock) lines.push(clock);
    if (dim) lines.push('<span class="bt-why" id="lr-why-' + esc(it.key) + '">' + esc(why) + '</span>');
    else if (it.old) lines.push('<span class="bt-why">' + esc(it.old) + '</span>');
    var label = it.name + ", " + n + " on your rack" + (meta.length ? ", " + meta.join(", ") : "") +
      (badges.length ? ", " + badges.join(", ") : "") + (it.clock && it.clock.why ? ", " + it.clock.why : "") +
      (unknown ? ", " + it.unknown + " unknown" : "") + ".";
    var icon = L.iconHtml(L.rowIcon(it), { size: 30, tier: it.tier, label: it.name });
    return '<li class="bt fr lr' + (dim ? " is-dim" : "") + (info ? " has-info" : "") + '" data-key="' + esc(it.key) + '">' +
      '<button type="button" class="bt-add lr-add" data-add="' + esc(it.key) + '"' +
      (dim ? ' aria-disabled="true" aria-describedby="lr-why-' + esc(it.key) + '"' : ' draggable="true"') +
      ' aria-label="' + esc(label) + '">' +
        '<span class="bt-icon fr-icon">' + icon + notches(it) +
          '<i class="fr-swatch" style="--sw:' + esc(it.color || "") + '" aria-hidden="true"></i></span>' +
        '<span class="bt-main"><span class="bt-name">' + esc(it.name) + '</span>' +
          (badges.length ? '<span class="bt-badges">' + badges.map(function (b) {
            return '<span class="bt-badge">' + esc(b) + '</span>'; }).join("") + '</span>' : "") +
          lines.join("") +
        '</span>' +
        '<span class="bt-count">' + esc(n) + '</span>' +
      '</button>' +
      (info ? '<button type="button" class="bt-info' + (unknown ? " is-unknown" : "") + '" data-material="' +
        esc(it.material) + '" data-for="' + esc(it.key) + '" aria-haspopup="dialog" aria-label="About ' +
        esc(it.name) + (unknown ? ", " + it.unknown + " unknown" : "") + '">?</button>' : "") +
      '</li>';
  }

  function group(title, items, whyOf) {
    if (!items.length) return "";
    return '<section class="bs-group"><h3 class="bs-gh">' + esc(title) + '</h3><ul class="bs-rows">' +
      items.map(function (it) { return row(it, whyOf(it)); }).join("") + '</ul></section>';
  }
  function byGroup(items, whyOf) {
    var names = GROUPS.slice();
    items.forEach(function (it) { if (it.group && names.indexOf(it.group) < 0) names.push(it.group); });
    return names.map(function (g) {
      return group(g, items.filter(function (it) { return (it.group || "Other") === g; }), whyOf);
    }).join("");
  }
  function inTown() {
    var w = L.state && L.state.where;
    return !!(w && (w.tannery || w.biome === "urban"));
  }

  // --- the list ---------------------------------------------------------------------------------
  function draw() {
    if (L.loading) { skeleton(); return; }
    if (L.error) {
      list.innerHTML = '<div class="bs-state"><p>Couldn\'t load your rack.</p>' +
        '<p class="bs-detail">' + esc(L.error) + '</p>' +
        '<button type="button" class="v2-btn is-small" data-leather-retry>Retry</button></div>';
      return;
    }
    var all = ((L.state && L.state.rack) || []).filter(function (it) { return it.count > 0; });
    var market = inTown() ? '<button type="button" class="v2-btn is-small" data-leather-market>Buy at the market</button>' : "";
    var html = "";
    if (!all.length) {
      html = '<div class="bs-state"><p>Your rack is empty. Hides, leather, salt, tannins and thread you carry appear here.</p>' +
        (market ? '<div class="bs-acts">' + market + '</div>' : "") + '</div>';
    } else {
      var shown = all.filter(function (it) { return !find || it.name.toLowerCase().indexOf(find) >= 0; });
      var m = L.order.method;
      var checked = !!L.check || m === "grade";
      var why = function (it) { return it.old ? it.old : L.why(it.key); };
      if (show === "all" || !checked) {
        html = byGroup(shown, checked ? why : function () { return ""; });
      } else {
        var fits = shown.filter(function (it) { return !why(it) && left(it) > 0; });
        var not = shown.filter(function (it) { return !!why(it) || left(it) <= 0; });
        // "Nothing you carry can be fleshed" only while the work still wants something.
        var wanting = m === "grade" ? !L.order.grade : L.slots().some(function (s) {
          return !s.optional && !L.order.slots[s.id];
        });
        if (!fits.length && m && !find && wanting) {
          html += '<div class="bs-state"><p>Nothing you carry can be ' + esc(L.DONE[m] || "worked") + '.</p>' +
            '<div class="bs-acts">' + market +
            '<button type="button" class="v2-btn is-small is-quiet" data-leather-everything>Everything I carry</button></div></div>';
        }
        html += byGroup(fits, why);
        html += group("Can't use now", not, function (it) {
          return why(it) || (left(it) <= 0 ? "all of it is on the work already" : "");
        });
      }
      if (!html) html = '<div class="bs-state"><p>Nothing on your rack matches "' + esc(find) + '".</p></div>';
    }
    // The shared In progress group (37-works.js), this craft's rows: a tannage in the vat or a
    // hide in the lime pit, with its countdown on game time and its Collect.
    html += '<div class="wk-host" id="leather-works"></div>';
    var had = document.activeElement && list.contains(document.activeElement) ? document.activeElement : null;
    var hadKey = had ? (had.dataset.add || had.dataset.for) : null;
    var hadInfo = had && had.classList.contains("bt-info");
    var scroll = list.scrollTop;
    list.innerHTML = html;
    works();
    list.scrollTop = scroll;
    rove();
    if (L.landed && Date.now() < L.landed.until) {
      var landed = list.querySelector('.lr[data-key="' + L.cssEsc(L.landed.key) + '"]');
      if (landed) landed.classList.add("is-landed");
    }
    if (hadKey) {
      var again = list.querySelector((hadInfo ? '.bt-info[data-for="' : '.lr-add[data-add="') + L.cssEsc(hadKey) + '"]');
      if (again) again.focus();
    }
  }
  L.drawRack = draw;

  function works() {
    var W = window.Works, host = document.getElementById("leather-works");
    if (!W || !host) return;
    W.group(host, "leatherworker");
  }

  // One Tab stop for the whole list (a roving tabindex): up and down walk it.
  var roveKey = null;
  function rove() {
    var rows = list.querySelectorAll(".lr-add[data-add]");
    if (!rows.length) return;
    var pick = roveKey && list.querySelector('.lr-add[data-add="' + L.cssEsc(roveKey) + '"]');
    if (!pick) pick = rows[0];
    list.querySelectorAll(".lr-add[data-add], .bt-info").forEach(function (b) { b.tabIndex = -1; });
    pick.tabIndex = 0;
    var info = pick.parentNode.querySelector(".bt-info");
    if (info) info.tabIndex = 0;
  }
  list.addEventListener("focusin", function (e) {
    var li = e.target.closest(".lr");
    var add = li && li.querySelector(".lr-add[data-add]");
    if (!add || add.dataset.add === roveKey) return;
    roveKey = add.dataset.add;
    rove();
  });

  function skeleton() {
    var one = '<li class="bt is-skel" aria-hidden="true"><span class="bt-add"><span class="bt-icon"><span class="sk-disc"></span></span>' +
      '<span class="bt-main"><span class="sk-bar"></span><span class="sk-bar is-short"></span></span></span></li>';
    list.innerHTML = '<p class="vh">Loading your rack.</p><ul class="bs-rows">' + new Array(7).join(one) + '</ul>';
  }

  ["loading", "error", "state", "check", "order", "method", "grade"].forEach(function (ev) { L.on(ev, draw); });

  // --- adding: click, Enter, or drag ------------------------------------------------------------
  list.addEventListener("click", function (e) {
    if (e.target.closest("[data-leather-retry]")) { L.reload(); return; }
    if (e.target.closest("[data-leather-market]")) { L.market(); return; }
    if (e.target.closest("[data-leather-everything]")) { L.showEverything(); return; }
    var info = e.target.closest(".bt-info");
    if (info) { L.openCard(info.dataset.material, info); return; }
    var add = e.target.closest(".lr-add[data-add]");
    if (!add) return;
    if (!L.addItem(add.dataset.add)) {
      var li = add.closest(".lr");
      if (li) { li.classList.remove("is-refused"); void li.offsetWidth; li.classList.add("is-refused"); }
    }
  });
  list.addEventListener("keydown", function (e) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    var here = e.target.closest(".lr-add");
    if (!here) return;
    var rows = Array.prototype.slice.call(list.querySelectorAll(".lr-add[data-add]"));
    var to = rows[rows.indexOf(here) + (e.key === "ArrowDown" ? 1 : -1)];
    if (to) { e.preventDefault(); to.focus(); }
  });
  list.addEventListener("dragstart", function (e) {
    var add = e.target.closest && e.target.closest(".lr-add[data-add]");
    if (!add || add.getAttribute("aria-disabled") === "true") { e.preventDefault(); return; }
    L.dragKey = add.dataset.add;
    e.dataTransfer.effectAllowed = "copy";
    e.dataTransfer.setData("text/plain", add.dataset.add);
  });
})();
