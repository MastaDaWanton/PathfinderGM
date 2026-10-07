// The play table, part 51 (the alchemy bench: the shelf). Classic script in one IIFE,
// talking to the rest of the bench through `window.Alchemy` (50-alchemy-shell.js).
//
// UI plan §6.2, the herb satchel's and the forge rack's pattern. Only what you CARRY is
// here, from lane F's `state.shelf`: the old Alchemy tab's wall of every material with its
// emoji glyph is retired (UI plan §2; the server still sends `glyph` for the old page, and
// nothing here draws it). Grouped in the order an alchemist reaches for things: Reagents,
// Glands and essences, Solvents, Salts and spirits, Solutions and admixtures, Hybrid herbs,
// Catalysts and apparatus, Vessels, Finished work, Old work; then In progress (37's group,
// this craft's rows only) and Can't use now.
//
// A row: the engraved form icon with its rarity rim and the material's swatch (an 8px disc
// of the server's colour: content, never a second accent and never alone, since the name is
// always beside it), the name and the count (tenths after an assay's pinch), the state
// badges, VOLATILE AND TOXIC AS WORDS WITH A SHAPE (a flame or a stoppered bottle beside the
// word, never colour alone), an intermediate's grades ("fire 1") and a finished thing's
// quality word, what time has done to it, and a "?" while anything about it is unknown. A
// row that cannot go into the step now is dimmed AND carries the server's reason in words
// (`check.fits`), so dimming never relies on colour alone.
//
// NO SCROLL JUMP (UI plan §6.2, the forge audit's defect): the list is redrawn in place, its
// scrollTop put back and the focused row found again by its key without scrolling to it.

(function () {
  "use strict";
  var A = window.Alchemy;
  if (!A) return;
  var esc = A.esc;
  var root = document.getElementById("alchemy-shelf-in");
  if (!root) return;

  var SHOWS = [["fits", "What fits"], ["all", "Everything I carry"]];
  var show = "fits", find = "";

  root.innerHTML =
    '<div class="bs-head">' +
      '<label class="bs-label" for="alchemy-find">Search the shelf</label>' +
      '<input type="search" id="alchemy-find" class="v2-well bs-find" autocomplete="off" spellcheck="false">' +
      '<div class="bs-showrow"><label class="bs-label" for="alchemy-show">Show</label>' +
      '<select id="alchemy-show" class="v2-well bs-show">' +
      SHOWS.map(function (s) { return '<option value="' + s[0] + '">' + s[1] + '</option>'; }).join("") +
      '</select></div>' +
    '</div>' +
    '<div class="bs-list as-list" id="alchemy-list" aria-live="off"></div>';
  var list = document.getElementById("alchemy-list");
  var findEl = document.getElementById("alchemy-find");
  var showEl = document.getElementById("alchemy-show");
  findEl.addEventListener("input", function () { find = findEl.value.trim().toLowerCase(); draw(); });
  showEl.addEventListener("change", function () { show = showEl.value; draw(); });
  A.showEverything = function () { show = "all"; showEl.value = "all"; draw(); showEl.focus(); };

  // The groups, as the server names them (`rules/alchemist.GROUPS`), in the alchemist's order.
  var ORDER = ["Reagents", "Glands and essences", "Solvents", "Salts and spirits",
               "Solutions and admixtures", "Hybrid herbs", "Catalysts and apparatus", "Vessels",
               "Finished work", "Old work"];
  // A hazard's shape: the icon beside the word (UI plan §6.2, "a small flame glyph and the
  // word volatile").
  var HAZARD = { "volatile": "hot", "toxic to handle": "toxic", "catalyst": "catalyst",
                 "apparatus": "catalyst" };
  // What a method takes, in words, for the empty state: "Nothing you carry can be dissolved."
  var VERB = { dissolve: "dissolved", calcine: "calcined", filter: "filtered", distill: "distilled",
               react: "worked in a reaction", sublime: "sublimed", bottle: "bottled",
               transmute: "transmuted", assay: "assayed" };

  function amount(it) {
    var have = it.amount != null ? it.amount : it.count;
    // Tenths only when the server sent them; whole units in the step never make one.
    return Math.round((have - A.inOrder(it.key)) * 10) / 10;
  }

  // The line under a row's name: what the thing IS for this craft, in the server's words.
  function sub(it) {
    var parts = [];
    if (it.quality_name) parts.push(it.quality_name);
    if ((it.grades || []).length) {
      parts.push(it.grades.map(function (g) { return g.essence + " " + g.grade; }).join(", "));
    }
    if (!parts.length && it.tier) parts.push(it.tier);
    if (it.keeps_until_day && !it.spoiled) parts.push("keeps until day " + it.keeps_until_day);
    if (it.old) parts.push(it.old);
    return parts.join(", ");
  }

  // --- a row -----------------------------------------------------------------------------------
  function row(it, why) {
    var dim = !!why;
    var badges = (it.badges || []).slice();
    var left = amount(it);
    var books = !!(window.AlchemyBooks && typeof AlchemyBooks.card === "function") && !!it.material;
    var unknown = it.unknown > 0;
    var lines = ['<span class="bt-time as-sub">' + esc(sub(it)) + '</span>'];
    if (it.spoiled) lines.push('<span class="bt-time as-warn">' + esc(cap(it.spoiled)) + '</span>');
    if (it.faded) lines.push('<span class="bt-time as-warn">' + esc(cap(it.faded)) + '</span>');
    if (dim) lines.push('<span class="bt-why" id="as-why-' + esc(slug(it.key)) + '">' + esc(why) + '</span>');
    if (unknown && !books) {
      lines.push('<span class="bt-time">' + (it.unknown === 1 ? "1 property unknown" : esc(it.unknown) + " properties unknown") + '</span>');
    }
    var label = it.name + ", " + left + " on your shelf" + (badges.length ? ", " + badges.join(", ") : "") +
      ". " + sub(it) + (unknown ? ", " + it.unknown + " unknown" : "") + ".";
    var icon = A.iconHtml(A.rowIcon(it), { size: 30, tier: it.tier, label: it.name });
    var swatch = it.swatch ? '<i class="fr-swatch" style="--sw:' + esc(it.swatch) + '" aria-hidden="true"></i>' : "";
    return '<li class="bt as' + (dim ? " is-dim" : "") + (books ? " has-info" : "") + '" data-key="' + esc(it.key) +
      '" data-group="' + esc(it.group || "") + '">' +
      '<button type="button" class="bt-add as-add" data-add="' + esc(it.key) + '"' +
      (dim ? ' aria-disabled="true" aria-describedby="as-why-' + esc(slug(it.key)) + '"' : ' draggable="true"') +
      ' aria-label="' + esc(label) + '">' +
        '<span class="bt-icon fr-icon">' + icon + swatch + '</span>' +
        '<span class="bt-main"><span class="bt-name">' + esc(it.name) + '</span>' +
          (badges.length ? '<span class="bt-badges">' + badges.map(badge).join("") + '</span>' : "") +
          lines.join("") +
        '</span>' +
        '<span class="bt-count">' + esc(left) + '</span>' +
      '</button>' +
      (books ? '<button type="button" class="bt-info' + (unknown ? " is-unknown" : "") + '" data-material="' +
        esc(it.material) + '" data-for="' + esc(it.key) + '" aria-haspopup="dialog" aria-label="About ' +
        esc(it.name) + (unknown ? ", " + it.unknown + " unknown" : "") + '">?</button>' : "") +
      '</li>';
  }
  function badge(b) {
    var shape = HAZARD[b];
    var warn = b === "volatile" || b === "toxic to handle";
    return '<span class="bt-badge' + (warn ? " is-warn" : "") + '">' +
      (shape ? A.iconHtml(shape, { size: 14, label: b }) : "") + esc(b) + '</span>';
  }
  function cap(t) { t = String(t || ""); return t.charAt(0).toUpperCase() + t.slice(1); }
  function slug(k) { return String(k).replace(/[^A-Za-z0-9_-]/g, "_"); }

  function group(title, items, whyOf) {
    if (!items.length) return "";
    return '<section class="bs-group"><h3 class="bs-gh">' + esc(title) +
      '</h3><ul class="bs-rows">' + items.map(function (it) { return row(it, whyOf(it)); }).join("") + '</ul></section>';
  }

  // Why a row cannot go into the step now. The server's `fits` answers for every row it was
  // asked about; the single requests say what they take in plain words, so a greyed row
  // never says nothing (the herb bench's lesson).
  function whyOf(it) {
    var m = A.order.method;
    if (!m) return "";
    if (m === "assay") return it.material && !it.family ? "" : "Assay takes a raw material, not worked stock";
    if (m === "identify") return "Identify studies a potion: pick one in the card";
    if (m === "learn") return "Learn copies a formula: pick a writing in the card";
    var w = A.why(it.key);
    return w === null ? "" : w;
  }

  // --- the list -----------------------------------------------------------------------------------
  function draw() {
    if (A.loading) { skeleton(); return; }
    if (A.error) {
      list.innerHTML = '<div class="bs-state"><p>Couldn\'t load your shelf.</p>' +
        '<p class="bs-detail">' + esc(A.error) + '</p>' +
        '<button type="button" class="v2-btn is-small" data-alchemy-retry>Retry</button></div>';
      return;
    }
    var all = ((A.state && A.state.shelf) || []).filter(function (it) { return !it.work; });
    var html = "";
    var m = A.order.method;
    if (!all.length) {
      html = '<div class="bs-state"><p>Your shelf is empty. Reagents, solvents, vessels and herbs you carry ' +
        'appear here; markets sell the common ones.</p></div>';
    } else {
      var match = function (it) { return !find || String(it.name).toLowerCase().indexOf(find) >= 0; };
      var not = [];
      var any = false;
      ORDER.forEach(function (g) {
        var items = all.filter(function (it) { return it.group === g && match(it); });
        var fits = show === "all" ? items : items.filter(function (it) { return !whyOf(it) && amount(it) > 0; });
        if (fits.length) any = true;
        if (show !== "all") items.forEach(function (it) { if (fits.indexOf(it) < 0) not.push(it); });
        html += group(g, fits, show === "all" ? whyOf : function () { return ""; });
      });
      // A group the server names that this file does not (a later lane's) still shows.
      var extra = all.filter(function (it) { return ORDER.indexOf(it.group) < 0 && match(it); });
      if (extra.length) html += group("Other", extra, show === "all" ? whyOf : function () { return ""; });
      if (show !== "all" && !any && m && VERB[m] && !find) {
        html = '<div class="bs-state"><p>Nothing you carry can be ' + esc(VERB[m]) + '.</p>' +
          '<button type="button" class="v2-btn is-small" data-alchemy-everything>Everything I carry</button></div>';
      }
      if (show !== "all") {
        html += group("Can't use now", not, function (it) {
          return whyOf(it) || (amount(it) <= 0 ? "all of it is on the bench already" : "");
        });
      }
      if (!html) html = '<div class="bs-state"><p>Nothing on your shelf matches "' + esc(find) + '".</p></div>';
    }
    // The shared In progress group (37-works.js), the alchemist's rows only: a setting
    // potion or a Transmute waits here with its countdown on game time until it is collected.
    html += '<div class="wk-host" id="alchemy-works-group"></div>';
    var had = document.activeElement && list.contains(document.activeElement) ? document.activeElement : null;
    var hadKey = had ? (had.dataset.add || had.dataset.for) : null;
    var hadInfo = had && had.classList.contains("bt-info");
    var scroll = list.scrollTop;
    list.innerHTML = html;
    works();
    list.scrollTop = scroll;
    rove();
    if (A.landed && Date.now() < A.landed.until) {
      var landed = list.querySelector('.as[data-key="' + A.cssEsc(A.landed.key) + '"]');
      if (landed) landed.classList.add("is-landed");
    }
    if (hadKey) {
      var again = list.querySelector((hadInfo ? '.bt-info[data-for="' : '.as-add[data-add="') + A.cssEsc(hadKey) + '"]');
      if (again) again.focus({ preventScroll: true });
    }
  }
  A.drawShelf = draw;

  function works() {
    var W = window.Works, host = document.getElementById("alchemy-works-group");
    if (!W || !host) return;
    W.group(host, "alchemist");
  }

  // One Tab stop for the whole list (a roving tabindex), as the satchel: Up and Down walk it.
  var roveKey = null;
  function rove() {
    var rows = list.querySelectorAll(".as-add[data-add]");
    if (!rows.length) return;
    var pick = roveKey && list.querySelector('.as-add[data-add="' + A.cssEsc(roveKey) + '"]');
    if (!pick) pick = rows[0];
    list.querySelectorAll(".as-add[data-add], .bt-info").forEach(function (b) { b.tabIndex = -1; });
    pick.tabIndex = 0;
    var info = pick.parentNode.querySelector(".bt-info");
    if (info) info.tabIndex = 0;
  }
  list.addEventListener("focusin", function (e) {
    var li = e.target.closest(".as");
    var add = li && li.querySelector(".as-add[data-add]");
    if (!add || add.dataset.add === roveKey) return;
    roveKey = add.dataset.add;
    rove();
  });

  function skeleton() {
    var one = '<li class="bt is-skel" aria-hidden="true"><span class="bt-add"><span class="bt-icon"><span class="sk-disc"></span></span>' +
      '<span class="bt-main"><span class="sk-bar"></span><span class="sk-bar is-short"></span></span></span></li>';
    list.innerHTML = '<p class="vh">Loading your shelf.</p><ul class="bs-rows">' + new Array(7).join(one) + '</ul>';
  }

  ["loading", "error", "state", "check", "order", "method"].forEach(function (ev) { A.on(ev, draw); });

  // --- adding: click, Enter, or drag ----------------------------------------------------------------
  list.addEventListener("click", function (e) {
    if (e.target.closest("[data-alchemy-retry]")) { A.reload(); return; }
    if (e.target.closest("[data-alchemy-everything]")) { A.showEverything(); return; }
    var info = e.target.closest(".bt-info[data-material]");
    if (info) { A.openCard(info.dataset.material, info, A.item(info.dataset.for)); return; }
    var add = e.target.closest(".as-add[data-add]");
    if (!add) return;
    if (!A.addItem(add.dataset.add)) {
      var li = add.closest(".as");
      if (li) { li.classList.remove("is-refused"); void li.offsetWidth; li.classList.add("is-refused"); }
    }
  });
  list.addEventListener("keydown", function (e) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    var here = e.target.closest(".as-add");
    if (!here) return;
    var rows = Array.prototype.slice.call(list.querySelectorAll(".as-add[data-add]"));
    var to = rows[rows.indexOf(here) + (e.key === "ArrowDown" ? 1 : -1)];
    if (to) { e.preventDefault(); to.focus(); }
  });
  list.addEventListener("dragstart", function (e) {
    var add = e.target.closest && e.target.closest(".as-add[data-add]");
    if (!add || add.getAttribute("aria-disabled") === "true") { e.preventDefault(); return; }
    A.dragKey = add.dataset.add;
    e.dataTransfer.effectAllowed = "copy";
    e.dataTransfer.setData("text/plain", add.dataset.add);
  });
})();
