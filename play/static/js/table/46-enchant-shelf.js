// The play table, part 46 (the enchanting circle: the shelf). Classic script in one IIFE,
// talking to the rest of the circle through `window.Enchant` (45-enchant-shell.js).
//
// UI plan §6.2, the herb satchel's pattern for the circle. Only what you CARRY is here, from
// lane E's `state.shelf`: the old Enchanting tab's wall of 117 materials with emoji glyphs is
// retired (UI plan §2). Grouped in the order an enchanter works: Vessels; Prepared and
// attuned (the intermediates, with their quality word and how long an attunement holds);
// Essences; Circle (chalk, salt, ink, treatments); Gems; Catalysts; In progress (lane U4's
// group, this craft's rows only); Can't use now.
//
// A row: an engraved roundel with its rarity rim, the essence's swatch (an 8px disc of the
// server's `color`: content, like heat at the forge, never a second accent and never alone,
// since the name is always beside it), the name, the count (tenths after a Read: "Flaming
// essence 0.9"), state badges (prepared, attuned, flawed, unidentified) and the line that
// matters for the row: a vessel's quality and what it holds, an essence's grant and its
// phase of the day. A row that cannot go into the step now is dimmed AND carries the
// server's reason in words (`check.fits`), so dimming never relies on colour alone.
//
// NO SCROLL JUMP (UI plan §6.2, the forge audit's defect): the list is redrawn in place, its
// scrollTop put back and the focused row found again by its key.

(function () {
  "use strict";
  var E = window.Enchant;
  if (!E) return;
  var esc = E.esc;
  var root = document.getElementById("enchant-shelf-in");
  if (!root) return;

  var SHOWS = [["fits", "What fits"], ["all", "Everything I carry"]];
  var show = "fits", find = "";

  root.innerHTML =
    '<div class="bs-head">' +
      '<label class="bs-label" for="enchant-find">Search the shelf</label>' +
      '<input type="search" id="enchant-find" class="v2-well bs-find" autocomplete="off" spellcheck="false">' +
      '<div class="bs-showrow"><label class="bs-label" for="enchant-show">Show</label>' +
      '<select id="enchant-show" class="v2-well bs-show">' +
      SHOWS.map(function (s) { return '<option value="' + s[0] + '">' + s[1] + '</option>'; }).join("") +
      '</select></div>' +
    '</div>' +
    '<div class="bs-list es-list" id="enchant-list" aria-live="off"></div>';
  var list = document.getElementById("enchant-list");
  var findEl = document.getElementById("enchant-find");
  var showEl = document.getElementById("enchant-show");
  findEl.addEventListener("input", function () { find = findEl.value.trim().toLowerCase(); draw(); });
  showEl.addEventListener("change", function () { show = showEl.value; draw(); });
  E.showEverything = function () { show = "all"; showEl.value = "all"; draw(); showEl.focus(); };

  // The groups, as the server sends them (`state.shelf`), in the enchanter's order.
  var ORDER = [["intermediates", "Prepared and attuned"], ["vessels", "Vessels"], ["essences", "Essences"],
               ["circle", "Circle"], ["gems", "Gems"], ["catalysts", "Catalysts"]];

  function amount(it) {
    var have = it.amount != null ? it.amount : it.count;
    // Tenths only when the server sent them; whole units in the working never make one.
    return Math.round((have - E.inOrder(it.key)) * 10) / 10;
  }

  // The line under a row's name: what the thing IS for this craft, in the server's words.
  function sub(it) {
    if (it.group === "Vessels") {
      var h = it.holds || {};
      var parts = [it.quality_name];
      if (h.masterwork === false) parts.push("not masterwork");
      else if (h.bonus != null) parts.push("holds +" + h.bonus, h.used ? "+" + h.used + " used" : "");
      if (it.attuned) parts.push("attuned, " + it.attuned.left_words + " left");
      else if (it.prepared) parts.push("prepared at " + it.prepared.quality_name);
      return parts.filter(Boolean).join(", ");
    }
    if (it.group === "Essences") {
      var ph = it.phase ? it.phase.charAt(0).toUpperCase() + it.phase.slice(1) : "";
      return [it.grants, it.motes != null ? String(it.motes) + (Number(it.motes) === 1 ? " mote" : " motes") : "", ph ? "favours " + ph.toLowerCase() : ""]
        .filter(Boolean).join(", ");
    }
    if (it.dc_mod) return (it.dc_mod < 0 ? "" : "+") + it.dc_mod + " to Bind's DC";
    if (it.lifts) return "lifts " + it.lifts;
    return it.tier || "";
  }

  // --- a row ---------------------------------------------------------------------------------
  function row(it, why) {
    var dim = !!why;
    var badges = (it.badges || []).slice();
    var left = amount(it);
    var ledger = it.group === "Essences" && !!(window.EnchantLedger && typeof EnchantLedger.card === "function");
    var unknown = it.unknown > 0;
    var lines = ['<span class="bt-time es-sub">' + esc(sub(it)) + '</span>'];
    if (dim) lines.push('<span class="bt-why" id="es-why-' + esc(it.key) + '">' + esc(why) + '</span>');
    if (unknown && !ledger) {
      lines.push('<span class="bt-time">' + (it.unknown === 1 ? "1 trait unknown" : esc(it.unknown) + " traits unknown") + '</span>');
    }
    var label = it.name + ", " + left + " on your shelf" + (badges.length ? ", " + badges.join(", ") : "") +
      ". " + sub(it) + (unknown ? ", " + it.unknown + " unknown" : "") + ".";
    var icon = E.iconHtml(E.rowIcon(it), { size: 30, tier: it.tier, label: it.name });
    var swatch = it.color ? '<i class="fr-swatch" style="--sw:' + esc(it.color) + '" aria-hidden="true"></i>' : "";
    return '<li class="bt es' + (dim ? " is-dim" : "") + (ledger ? " has-info" : "") + '" data-key="' + esc(it.key) +
      '" data-group="' + esc(it.group || "") + '">' +
      '<button type="button" class="bt-add es-add" data-add="' + esc(it.key) + '"' +
      (dim ? ' aria-disabled="true" aria-describedby="es-why-' + esc(it.key) + '"' : ' draggable="true"') +
      ' aria-label="' + esc(label) + '">' +
        '<span class="bt-icon fr-icon">' + icon + swatch + '</span>' +
        '<span class="bt-main"><span class="bt-name">' + esc(it.name) + '</span>' +
          (badges.length ? '<span class="bt-badges">' + badges.map(function (b) {
            return '<span class="bt-badge' + (b === "flawed" ? " is-warn" : "") + '">' + esc(b) + '</span>'; }).join("") + '</span>' : "") +
          lines.join("") +
        '</span>' +
        '<span class="bt-count">' + esc(left) + '</span>' +
      '</button>' +
      (ledger ? '<button type="button" class="bt-info' + (unknown ? " is-unknown" : "") + '" data-essence="' +
        esc(it.id) + '" data-for="' + esc(it.key) + '" aria-haspopup="dialog" aria-label="About ' +
        esc(it.name) + (unknown ? ", " + it.unknown + " unknown" : "") + '">?</button>' : "") +
      '</li>';
  }

  function group(title, items, whyOf, id) {
    if (!items.length) return "";
    return '<section class="bs-group"' + (id ? ' id="' + id + '"' : "") + '><h3 class="bs-gh">' + esc(title) +
      '</h3><ul class="bs-rows">' + items.map(function (it) { return row(it, whyOf(it)); }).join("") + '</ul></section>';
  }

  // Why a row cannot go into the step now. The server's `fits` answers for the rows it
  // was asked about; a row of a group the step takes nothing from says which step does,
  // in plain words, so a greyed row never says nothing (the herb bench's lesson: a rule
  // that only speaks after the button is pressed reads as no rule).
  function whyOf(it) {
    var m = E.order.method;
    if (m === "read") return it.group === "Essences" ? "" : "Read takes an essence";
    if (m === "identify") return it.card ? "" : "Identify takes a magic item";
    if (it.why_not) return it.why_not;
    if (!m) return "";
    var w = E.why(it.key);
    if (w !== null) return w;
    if (!E.check) return "";
    var g = it.group;
    if (g === "Essences") return m === "attune" || m === "refine" ? "" : "Essences go in at Attune or Refine";
    if (g === "Vessels") return E.usesVessel(m) ? "" : "This step takes no vessel";
    if (it.kind === "catalyst") return "A catalyst goes in at Bind";
    return "Circle materials go in at Prepare";
  }

  // --- the list ---------------------------------------------------------------------------------
  function draw() {
    if (E.loading) { skeleton(); return; }
    if (E.error) {
      list.innerHTML = '<div class="bs-state"><p>Couldn\'t load your shelf.</p>' +
        '<p class="bs-detail">' + esc(E.error) + '</p>' +
        '<button type="button" class="v2-btn is-small" data-enchant-retry>Retry</button></div>';
      return;
    }
    var s = (E.state && E.state.shelf) || {};
    var all = [];
    ORDER.forEach(function (g) { (s[g[0]] || []).forEach(function (it) { all.push(it); }); });
    var bad = s.cant_use || [];
    var html = "";
    if (!all.length && !bad.length) {
      html = '<div class="bs-state"><p>Your shelf is empty. A forged weapon or armour of Superior work, essences, ' +
        'chalk and ink you carry appear here.</p></div>';
    } else {
      var match = function (it) { return !find || String(it.name).toLowerCase().indexOf(find) >= 0; };
      var not = [];
      ORDER.forEach(function (g) {
        var items = (s[g[0]] || []).filter(match);
        var fits = show === "all" ? items : items.filter(function (it) { return !whyOf(it) && amount(it) > 0; });
        if (show !== "all") {
          items.forEach(function (it) { if (fits.indexOf(it) < 0) not.push(it); });
        }
        html += group(g[1], fits, show === "all" ? whyOf : function () { return ""; });
      });
      not = not.concat(bad.filter(match));
      if (show === "all") not = bad.filter(match);
      html += group("Can't use now", not, function (it) {
        return whyOf(it) || (amount(it) <= 0 ? "all of it is in the working already" : "");
      });
      if (!html) html = '<div class="bs-state"><p>Nothing on your shelf matches "' + esc(find) + '".</p></div>';
    }
    // The shared In progress group (37-works.js), the enchanter's rows only: a binding waits
    // here with its countdown on game time until it is collected.
    html += '<div class="wk-host" id="enchant-works-group"></div>';
    var had = document.activeElement && list.contains(document.activeElement) ? document.activeElement : null;
    var hadKey = had ? (had.dataset.add || had.dataset.for) : null;
    var hadInfo = had && had.classList.contains("bt-info");
    var scroll = list.scrollTop;
    list.innerHTML = html;
    works();
    list.scrollTop = scroll;
    rove();
    if (E.landed && Date.now() < E.landed.until) {
      var landed = list.querySelector('.es[data-key="' + E.cssEsc(E.landed.key) + '"]');
      if (landed) landed.classList.add("is-landed");
    }
    if (hadKey) {
      // Found again WITHOUT scrolling to it: a chalk put in the circle moves down to "Can't
      // use now", and following it there jumped the list 343px, leaving the ink the player
      // was reaching for above the fold (seen live, 2026-10-06).
      var again = list.querySelector((hadInfo ? '.bt-info[data-for="' : '.es-add[data-add="') + E.cssEsc(hadKey) + '"]');
      if (again) again.focus({ preventScroll: true });
    }
  }
  E.drawShelf = draw;

  function works() {
    var W = window.Works, host = document.getElementById("enchant-works-group");
    if (!W || !host) return;
    W.group(host, "enchanter");
  }

  // One Tab stop for the whole list (a roving tabindex), as the satchel: Up and Down walk it.
  var roveKey = null;
  function rove() {
    var rows = list.querySelectorAll(".es-add[data-add]");
    if (!rows.length) return;
    var pick = roveKey && list.querySelector('.es-add[data-add="' + E.cssEsc(roveKey) + '"]');
    if (!pick) pick = rows[0];
    list.querySelectorAll(".es-add[data-add], .bt-info").forEach(function (b) { b.tabIndex = -1; });
    pick.tabIndex = 0;
    var info = pick.parentNode.querySelector(".bt-info");
    if (info) info.tabIndex = 0;
  }
  list.addEventListener("focusin", function (e) {
    var li = e.target.closest(".es");
    var add = li && li.querySelector(".es-add[data-add]");
    if (!add || add.dataset.add === roveKey) return;
    roveKey = add.dataset.add;
    rove();
  });

  function skeleton() {
    var one = '<li class="bt is-skel" aria-hidden="true"><span class="bt-add"><span class="bt-icon"><span class="sk-disc"></span></span>' +
      '<span class="bt-main"><span class="sk-bar"></span><span class="sk-bar is-short"></span></span></span></li>';
    list.innerHTML = '<p class="vh">Loading your shelf.</p><ul class="bs-rows">' + new Array(7).join(one) + '</ul>';
  }

  ["loading", "error", "state", "check", "order", "method"].forEach(function (ev) { E.on(ev, draw); });

  // --- adding: click, Enter, or drag ------------------------------------------------------------
  list.addEventListener("click", function (e) {
    if (e.target.closest("[data-enchant-retry]")) { E.reload(); return; }
    var info = e.target.closest(".bt-info[data-essence]");
    if (info) { openCard(info.dataset.essence, info); return; }
    var add = e.target.closest(".es-add[data-add]");
    if (!add) return;
    if (!E.addItem(add.dataset.add)) {
      var li = add.closest(".es");
      if (li) { li.classList.remove("is-refused"); void li.offsetWidth; li.classList.add("is-refused"); }
    }
  });
  list.addEventListener("keydown", function (e) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    var here = e.target.closest(".es-add");
    if (!here) return;
    var rows = Array.prototype.slice.call(list.querySelectorAll(".es-add[data-add]"));
    var to = rows[rows.indexOf(here) + (e.key === "ArrowDown" ? 1 : -1)];
    if (to) { e.preventDefault(); to.focus(); }
  });
  list.addEventListener("dragstart", function (e) {
    var add = e.target.closest && e.target.closest(".es-add[data-add]");
    if (!add || add.getAttribute("aria-disabled") === "true") { e.preventDefault(); return; }
    E.dragKey = add.dataset.add;
    e.dataTransfer.effectAllowed = "copy";
    e.dataTransfer.setData("text/plain", add.dataset.add);
  });

  // --- the ledger card (lane U5, contracts §13) --------------------------------------------------
  // "?" opens `EnchantLedger.card(essenceId, anchorEl)` beside the shelf when lane U5's file
  // is in the build; without it the row says how many traits are unknown in words.
  function openCard(id, el) {
    var L = window.EnchantLedger;
    if (!L || typeof L.card !== "function" || !id) return;
    try { L.card(id, el); } catch (err) { console.error("enchant ledger card failed:", err); }
  }
})();
