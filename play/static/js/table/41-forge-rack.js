// The play table, part 41 (the forge: the rack). Classic script in one IIFE, talking to
// the rest of the forge through `window.Forge` (40-forge-shell.js).
//
// UI plan §6.2, the herb satchel's pattern for metal. Only what you CARRY is here: the old
// Blacksmithing tab's wall of all 112 materials, most of them greyed "beyond your tier",
// is retired (UI plan §2). Rows grouped by form, in the order a smith works (Ore, Ingots,
// Bars, Blanks and plates, fittings, Fuel, Flux, Quenchants, Treatments, Finished work);
// the group names are the server's (`group` on each row).
//
// A row: the form's engraved icon with its rarity rim, the material's swatch (an 8px
// disc of the server's `color`: content, like heat, never a second accent, and never
// alone, since the name is always beside it), the name, the count (tenths after an
// assay, "Iron bar 1.9"), state badges and the quality word. A row that cannot go on the
// work now is dimmed AND carries the server's reason in words (`check.fits`), so dimming
// never relies on colour alone.
//
// NO SCROLL JUMP (UI plan §2, the old tab's defect: "the shelf jumps its scroll position
// on every click"). The list is redrawn in place: its scrollTop is read before and put
// back after, and the focused row is found again by its key.

(function () {
  "use strict";
  var F = window.Forge;
  if (!F) return;
  var esc = F.esc;
  var root = document.getElementById("forge-rack-in");
  if (!root) return;

  var GROUPS = ["Ore", "Ingots", "Bars", "Blanks and plates", "Hafts, grips and fittings", "Fuel",
                "Flux", "Quenchants", "Treatments", "Finished work", "Old work"];
  var SHOWS = [["fits", "What fits"], ["all", "Everything I carry"]];
  var show = "fits", find = "";

  root.innerHTML =
    '<div class="bs-head">' +
      '<label class="bs-label" for="forge-find">Search your rack</label>' +
      '<input type="search" id="forge-find" class="v2-well bs-find" autocomplete="off" spellcheck="false">' +
      '<div class="bs-showrow"><label class="bs-label" for="forge-show">Show</label>' +
      '<select id="forge-show" class="v2-well bs-show">' +
      SHOWS.map(function (s) { return '<option value="' + s[0] + '">' + s[1] + '</option>'; }).join("") +
      '</select></div>' +
    '</div>' +
    '<div class="bs-list fr-list" id="forge-list" aria-live="off"></div>';
  var list = document.getElementById("forge-list");
  var findEl = document.getElementById("forge-find");
  var showEl = document.getElementById("forge-show");
  findEl.addEventListener("input", function () { find = findEl.value.trim().toLowerCase(); draw(); });
  showEl.addEventListener("change", function () { show = showEl.value; draw(); });
  F.showEverything = function () { show = "all"; showEl.value = "all"; draw(); showEl.focus(); };

  function amount(it) {
    var left = (it.amount != null ? it.amount : it.count) - F.inOrder(it.key);
    // Tenths only when the server sent a part bar; the subtraction of whole units in the
    // order cannot make one. Shown, never computed into anything.
    return Math.round(left * 10) / 10;
  }

  // --- a row ---------------------------------------------------------------------------------
  function row(it, why) {
    var dim = !!why;
    var badges = (it.badges || []).slice();
    if (it.quality_name) badges.push(it.quality_name);
    var left = amount(it);
    var ledger = !!(window.ForgeLedger && typeof ForgeLedger.card === "function") && !!it.material && !it.old;
    var unknown = it.unknown > 0;
    var lines = [];
    if (dim) lines.push('<span class="bt-why" id="fr-why-' + esc(it.key) + '">' + esc(why) + '</span>');
    else if (it.old) lines.push('<span class="bt-why">' + esc(it.old) + '</span>');
    if (unknown && !ledger) {
      lines.push('<span class="bt-time">' + (it.unknown === 1 ? "1 property unknown" : esc(it.unknown) + " properties unknown") + '</span>');
    }
    var label = it.name + ", " + left + " on your rack" + (badges.length ? ", " + badges.join(", ") : "") +
      (unknown ? ", " + it.unknown + " unknown" : "") + ".";
    var icon = F.iconHtml(F.rowIcon(it), { size: 30, tier: it.tier, label: it.name });
    return '<li class="bt fr' + (dim ? " is-dim" : "") + (ledger ? " has-info" : "") + '" data-key="' + esc(it.key) + '">' +
      '<button type="button" class="bt-add fr-add" data-add="' + esc(it.key) + '"' +
      (dim ? ' aria-disabled="true" aria-describedby="fr-why-' + esc(it.key) + '"' : ' draggable="true"') +
      ' aria-label="' + esc(label) + '">' +
        '<span class="bt-icon fr-icon">' + icon +
          '<i class="fr-swatch" style="--sw:' + esc(it.color || "") + '" aria-hidden="true"></i></span>' +
        '<span class="bt-main"><span class="bt-name">' + esc(it.name) + '</span>' +
          (badges.length ? '<span class="bt-badges">' + badges.map(function (b) {
            return '<span class="bt-badge">' + esc(b) + '</span>'; }).join("") + '</span>' : "") +
          lines.join("") +
        '</span>' +
        '<span class="bt-count">' + esc(left) + '</span>' +
      '</button>' +
      (ledger ? '<button type="button" class="bt-info' + (unknown ? " is-unknown" : "") + '" data-material="' +
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
    var w = F.state && F.state.where;
    return !!(w && (w.smithy || w.biome === "urban"));
  }

  // --- the list ---------------------------------------------------------------------------------
  function draw() {
    if (F.loading) { skeleton(); return; }
    if (F.error) {
      list.innerHTML = '<div class="bs-state"><p>Couldn\'t load your rack.</p>' +
        '<p class="bs-detail">' + esc(F.error) + '</p>' +
        '<button type="button" class="v2-btn is-small" data-forge-retry>Retry</button></div>';
      return;
    }
    var all = ((F.state && F.state.rack) || []).filter(function (it) { return it.count > 0 || it.amount > 0; });
    var market = inTown() ? '<button type="button" class="v2-btn is-small" data-forge-market>Buy at the market</button>' : "";
    if (!all.length) {
      list.innerHTML = '<div class="bs-state"><p>Your rack is empty. Ore, bars, fuel and fittings you carry appear here.</p>' +
        (market ? '<div class="bs-acts">' + market + '</div>' : "") + '</div>';
      return;
    }
    var shown = all.filter(function (it) { return !find || it.name.toLowerCase().indexOf(find) >= 0; });
    var why = function (it) { return it.old ? it.old : F.why(it.key); };
    var html = "";
    if (show === "all" || !F.check) {
      html = byGroup(shown, F.check ? why : function () { return ""; });
    } else {
      var fits = shown.filter(function (it) { return !why(it) && amount(it) > 0; });
      var not = shown.filter(function (it) { return !!why(it) || amount(it) <= 0; });
      var m = F.order.method;
      if (!fits.length && m && !find) {
        html += '<div class="bs-state"><p>Nothing you carry can be ' + esc(F.DONE[m] || "worked") + '.</p>' +
          '<div class="bs-acts">' + market +
          '<button type="button" class="v2-btn is-small is-quiet" data-forge-everything>Everything I carry</button></div></div>';
      }
      html += byGroup(fits, why);
      html += group("Can't use now", not, function (it) {
        return why(it) || (amount(it) <= 0 ? "all of it is on the work already" : "");
      });
    }
    if (!html) html = '<div class="bs-state"><p>Nothing on your rack matches "' + esc(find) + '".</p></div>';
    var had = document.activeElement && list.contains(document.activeElement) ? document.activeElement : null;
    var hadKey = had ? (had.dataset.add || had.dataset.for) : null;
    var hadInfo = had && had.classList.contains("bt-info");
    var scroll = list.scrollTop;
    list.innerHTML = html;
    list.scrollTop = scroll;
    rove();
    if (F.landed && Date.now() < F.landed.until) {
      var landed = list.querySelector('.fr[data-key="' + F.cssEsc(F.landed.key) + '"]');
      if (landed) landed.classList.add("is-landed");
    }
    if (hadKey) {
      var again = list.querySelector((hadInfo ? '.bt-info[data-for="' : '.fr-add[data-add="') + F.cssEsc(hadKey) + '"]');
      if (again) again.focus();
    }
  }
  F.drawRack = draw;

  // One Tab stop for the whole list (a roving tabindex), as the satchel: ↑ and ↓ walk it.
  var roveKey = null;
  function rove() {
    var rows = list.querySelectorAll(".fr-add[data-add]");
    if (!rows.length) return;
    var pick = roveKey && list.querySelector('.fr-add[data-add="' + F.cssEsc(roveKey) + '"]');
    if (!pick) pick = rows[0];
    list.querySelectorAll(".fr-add[data-add], .bt-info").forEach(function (b) { b.tabIndex = -1; });
    pick.tabIndex = 0;
    var info = pick.parentNode.querySelector(".bt-info");
    if (info) info.tabIndex = 0;
  }
  list.addEventListener("focusin", function (e) {
    var li = e.target.closest(".fr");
    var add = li && li.querySelector(".fr-add[data-add]");
    if (!add || add.dataset.add === roveKey) return;
    roveKey = add.dataset.add;
    rove();
  });

  function skeleton() {
    var one = '<li class="bt is-skel" aria-hidden="true"><span class="bt-add"><span class="bt-icon"><span class="sk-disc"></span></span>' +
      '<span class="bt-main"><span class="sk-bar"></span><span class="sk-bar is-short"></span></span></span></li>';
    list.innerHTML = '<p class="vh">Loading your rack.</p><ul class="bs-rows">' + new Array(7).join(one) + '</ul>';
  }

  ["loading", "error", "state", "check", "order", "method"].forEach(function (ev) { F.on(ev, draw); });

  // --- adding: click, Enter, or drag ------------------------------------------------------------
  list.addEventListener("click", function (e) {
    if (e.target.closest("[data-forge-retry]")) { F.reload(); return; }
    if (e.target.closest("[data-forge-market]")) { F.market(); return; }
    if (e.target.closest("[data-forge-everything]")) { F.showEverything(); return; }
    var info = e.target.closest(".bt-info");
    if (info) { openCard(info.dataset.material, info); return; }
    var add = e.target.closest(".fr-add[data-add]");
    if (!add) return;
    if (!F.addItem(add.dataset.add)) {
      var li = add.closest(".fr");
      if (li) { li.classList.remove("is-refused"); void li.offsetWidth; li.classList.add("is-refused"); }
    }
  });
  list.addEventListener("keydown", function (e) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    var here = e.target.closest(".fr-add");
    if (!here) return;
    var rows = Array.prototype.slice.call(list.querySelectorAll(".fr-add[data-add]"));
    var to = rows[rows.indexOf(here) + (e.key === "ArrowDown" ? 1 : -1)];
    if (to) { e.preventDefault(); to.focus(); }
  });
  list.addEventListener("dragstart", function (e) {
    var add = e.target.closest && e.target.closest(".fr-add[data-add]");
    if (!add || add.getAttribute("aria-disabled") === "true") { e.preventDefault(); return; }
    F.dragKey = add.dataset.add;
    e.dataTransfer.effectAllowed = "copy";
    e.dataTransfer.setData("text/plain", add.dataset.add);
  });

  // --- the ledger card (lane U5, contracts §11) --------------------------------------------------
  // Hover, focus or "?" opens `ForgeLedger.card(materialId, anchorEl)` beside the rack when
  // lane U5's file is in the build. Hover waits a beat so a pointer crossing the list does
  // not flash a card per row; hover is never required.
  function openCard(mid, el) {
    var L = window.ForgeLedger;
    if (!L || typeof L.card !== "function" || !mid) return;
    try { L.card(mid, el); } catch (err) { console.error("forge ledger card failed:", err); }
  }
  var hoverT = 0;
  list.addEventListener("mouseover", function (e) {
    var li = e.target.closest(".fr.has-info");
    clearTimeout(hoverT);
    if (!li) return;
    var info = li.querySelector(".bt-info");
    hoverT = setTimeout(function () { openCard(info.dataset.material, li); }, 280);
  });
  list.addEventListener("mouseleave", function () { clearTimeout(hoverT); });
})();
