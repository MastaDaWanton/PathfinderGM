// The play table, part 43 (the forge: the work order). Classic script in one IIFE,
// reached through `window.Forge` (40-forge-shell.js).
//
// UI plan §6.5 and §6.6. The right column is a WORK ORDER, because the second thing a
// smith reads (after the heat) is how the pieces fit:
//   - the piece slots on top: the method's inputs (Bar and Fuel at Forge; Head, Haft,
//     Fittings at Assemble, or Body, Fastenings, Lining once a plate is the main piece).
//     Each is a drop target and a button: filled, it shows the piece with its swatch and
//     a × to take it off; empty, it says what goes there, and pressing it sends the
//     keyboard to the rack's first row that fits, so Enter there fills THIS slot;
//   - what is being made: the shape picked from the engine's list at Forge (never free
//     text: the old tab's "axes-mortar, air-repeater" field is retired), the ambition at
//     Assemble, the batch for the methods that take one;
//   - the paper tag (the herb tag's look, bench.css): the product, and the quality ladder
//     from Crude to your ceiling with the rung where masterwork begins marked
//     "Superior · masterwork";
//   - the build summary: what the work comes to, one line per target, and the book's
//     powers in words, then "Show the sum", the build card.
//
// THE PAGE NEVER COMPUTES A NUMBER (UI plan §12). Every cell of the build card, the
// summary's lines and the "rounded toward zero" sum are the server's (`preview.card`
// from play/forge_views.py over lane B's `forge_items.build`), drawn as sent.

(function () {
  "use strict";
  var F = window.Forge;
  if (!F) return;
  var esc = F.esc;
  var root = document.getElementById("forge-order-in");
  if (!root) return;

  root.innerHTML =
    '<section class="fo-slots" id="forge-slots" aria-label="The work order"></section>' +
    '<div class="fo-make" id="forge-make"></div>' +
    '<div class="bench-tag v2-page-paper fo-tag" id="forge-tag"><span class="tag-eyelet" aria-hidden="true"></span>' +
      '<div class="tag-body" id="forge-tag-body"></div>' +
      '<div class="tag-result" id="forge-tag-result" aria-live="polite"></div>' +
    '</div>' +
    '<div class="fo-build" id="forge-build"></div>';
  var slotsEl = document.getElementById("forge-slots");
  var makeEl = document.getElementById("forge-make");
  var tagBody = document.getElementById("forge-tag-body");
  var resultEl = document.getElementById("forge-tag-result");
  var buildEl = document.getElementById("forge-build");

  // While a game runs the ladder's pointer follows the live score; the tier the work GETS
  // is the server's and replaces this the moment the finish answers. The bands are the
  // server's (`tuning.bands`), so this is a picture of progress, never posted.
  var preview = null;

  // --- the slots --------------------------------------------------------------------------------
  function drawSlots() {
    var o = F.order, m = o.method;
    if (!m || F.loading || F.error) { slotsEl.innerHTML = ""; return; }
    var keep = document.activeElement && slotsEl.contains(document.activeElement) ? document.activeElement : null;
    var keepSel = keep ? (keep.dataset.slot ? '[data-slot="' + keep.dataset.slot + '"]' + (keep.classList.contains("fo-x") ? ".fo-x" : ".fo-slot-b")
                          : keep.dataset.part ? '[data-part="' + F.cssEsc(keep.dataset.part) + '"][data-step="' + keep.dataset.step + '"]' : null) : null;
    var html = "";
    if (m === "alloy") {
      html += '<h3 class="fo-h">Crucible</h3>';
      if (!o.parts.length) {
        html += '<div class="fo-slot is-empty" data-slot="part"><button type="button" class="fo-slot-b" data-slot="part">' +
          '<span class="fo-label">Metals</span><span class="fo-hint">Add two or more metals, or press Enter on them in the rack</span></button></div>';
      }
      html += '<ul class="fo-parts">' + o.parts.map(function (p) {
        var it = F.item(p.key);
        if (!it) return "";
        return '<li class="fo-part"><i class="fr-swatch" style="--sw:' + esc(it.color || "") + '" aria-hidden="true"></i>' +
          '<span class="fo-name">' + esc(it.name) + '</span>' +
          '<span class="tb-step v2-recess">' +
            '<button type="button" class="v2-btn is-small" data-part="' + esc(p.key) + '" data-step="less" aria-label="One ' + esc(it.name) + ' fewer">−</button>' +
            '<span class="fo-n" aria-live="polite">' + esc(p.count) + '</span>' +
            '<button type="button" class="v2-btn is-small" data-part="' + esc(p.key) + '" data-step="more" aria-label="One ' + esc(it.name) + ' more"' +
              (p.count >= it.count ? " disabled" : "") + '>+</button>' +
          '</span></li>';
      }).join("") + '</ul>';
    } else {
      F.slots().forEach(function (s) {
        var key = o.slots[s.id];
        var it = key && F.item(key);
        if (it) {
          var badges = (it.badges || []).slice();
          if (it.quality_name) badges.push(it.quality_name);
          html += '<div class="fo-slot is-full" data-slot="' + esc(s.id) + '">' +
            '<span class="fo-label">' + esc(s.label) + '</span>' +
            '<span class="fo-piece">' + F.iconHtml(F.rowIcon(it), { size: 26, tier: it.tier, label: it.name }) +
              '<i class="fr-swatch" style="--sw:' + esc(it.color || "") + '" aria-hidden="true"></i>' +
              '<span class="fo-name">' + esc(it.name) + (badges.length ? '<small>' + esc(badges.join(", ")) + '</small>' : "") + '</span></span>' +
            '<button type="button" class="fo-x" data-slot="' + esc(s.id) + '" aria-label="Take ' + esc(it.name) +
              ' off the ' + esc(s.label.toLowerCase()) + ' slot">×</button></div>';
        } else {
          var hinted = F.slotHint === s.id;
          html += '<div class="fo-slot is-empty' + (s.optional ? " is-optional" : "") + (hinted ? " is-hinted" : "") + '" data-slot="' + esc(s.id) + '">' +
            '<button type="button" class="fo-slot-b" data-slot="' + esc(s.id) + '" aria-label="' + esc(s.label + ", empty. " + s.empty) + '">' +
            '<span class="fo-label">' + esc(s.label) + '</span>' +
            '<span class="fo-hint">' + esc(s.empty) + '</span></button></div>';
        }
      });
    }
    slotsEl.innerHTML = html;
    if (keepSel) {
      var again = slotsEl.querySelector(keepSel);
      if (again && !again.disabled) again.focus();
    }
  }

  slotsEl.addEventListener("click", function (e) {
    var x = e.target.closest(".fo-x");
    if (x) { F.removeSlot(x.dataset.slot); F.refocus(['[data-slot="' + x.dataset.slot + '"].fo-slot-b', "forge-roll"]); return; }
    var step = e.target.closest("[data-step]");
    if (step && !step.disabled) {
      var p = F.order.parts.filter(function (q) { return q.key === step.dataset.part; })[0];
      if (p) F.setPart(p.key, p.count + (step.dataset.step === "more" ? 1 : -1));
      return;
    }
    var b = e.target.closest(".fo-slot-b");
    if (b) {
      // An empty slot pressed: the next row picked in the rack goes here. The keyboard
      // moves to the first row that fits this slot, so Enter fills it.
      var slot = b.dataset.slot;
      F.slotHint = slot === "part" ? null : slot;
      drawSlots();
      var rows = Array.prototype.slice.call(document.querySelectorAll("#forge-list .fr-add[data-add]"));
      var row = rows.filter(function (r) { return F.fit(slot, r.dataset.add) === ""; })[0];
      if (row) { row.focus(); F.say("Pick what goes in the " + slot + " slot."); }
      else F.say("Nothing you carry goes in the " + slot + " slot.");
    }
  });

  // A drop on a slot puts the dragged row in THAT slot.
  function slotOf(e) { var s = e.target.closest && e.target.closest(".fo-slot"); return s ? s.dataset.slot : null; }
  slotsEl.addEventListener("dragover", function (e) {
    if (!F.dragKey || !slotOf(e)) return;
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "copy";
    var s = e.target.closest(".fo-slot");
    slotsEl.querySelectorAll(".is-dragover").forEach(function (x) { if (x !== s) x.classList.remove("is-dragover"); });
    s.classList.add("is-dragover");
  });
  slotsEl.addEventListener("dragleave", function (e) {
    var s = e.target.closest && e.target.closest(".fo-slot");
    if (s && !s.contains(e.relatedTarget)) s.classList.remove("is-dragover");
  });
  slotsEl.addEventListener("drop", function (e) {
    var slot = slotOf(e);
    if (!F.dragKey || !slot) return;
    e.preventDefault();
    e.stopPropagation();
    slotsEl.querySelectorAll(".is-dragover").forEach(function (x) { x.classList.remove("is-dragover"); });
    var key = F.dragKey;
    F.dragKey = null;
    F.addItem(key, slot === "part" ? null : slot);
  });

  // --- what is being made: shape, ambition, batch ------------------------------------------------
  // The shape picker is built once per method and redrawn only when its list changes;
  // after that only its value follows the order. Rebuilt on every check (as it first
  // was), a keyboard player's type-ahead died at the first letter: "l" chose a light
  // hammer, the check's answer replaced the select, and "o" began a new search (seen
  // live, 2026-10-04, at 1280x720 with the keyboard only).
  var shapeSig = "";
  function drawMake() {
    var o = F.order, m = o.method;
    if (!m || F.loading || F.error) { makeEl.innerHTML = ""; shapeSig = ""; return; }
    var fams = (F.state && F.state.shapes) || [];
    var sig = m === "forge" ? "forge:" + fams.length : "none";
    var rest = makeEl.querySelector(".fo-rest");
    if (sig !== shapeSig || !rest) {
      makeEl.innerHTML = '<div class="fo-shapebox">' + (m === "forge" ? shapeHtml(fams, o.shape) : "") +
        '</div><div class="fo-rest"></div>';
      shapeSig = sig;
      rest = makeEl.querySelector(".fo-rest");
    } else if (m === "forge") {
      var sel = document.getElementById("forge-shape");
      if (sel && sel.value !== (o.shape || "")) sel.value = o.shape || "";
    }
    drawRest(rest);
  }
  function shapeHtml(fams, shape) {
    return '<div class="fo-field"><label class="bs-label" for="forge-shape">What to forge</label>' +
      '<select id="forge-shape" class="v2-well bs-show fo-shape"><option value="">Choose from the list</option>' +
      fams.map(function (f) {
        return '<optgroup label="' + esc(f.family) + '">' + (f.shapes || []).map(function (s) {
          return '<option value="' + esc(s.id) + '"' + (s.id === shape ? " selected" : "") + '>' + esc(s.name) +
            ', ' + esc(s.bars) + (s.bars === 1 ? " bar" : " bars") + ', DC ' + esc(s.dc) + '</option>';
        }).join("") + '</optgroup>';
      }).join("") + '</select></div>';
  }
  function drawRest(host) {
    var o = F.order, m = o.method, c = F.check || {};
    var keep = document.activeElement && host.contains(document.activeElement) ? document.activeElement.id : null;
    var keepBatch = document.activeElement && host.contains(document.activeElement) ? document.activeElement.dataset.batch : null;
    var html = "";
    if (m === "assemble") {
      var mw = c.masterwork || null;
      html += '<div class="fo-field fo-aim"><label class="fo-check"><input type="checkbox" id="forge-aim"' +
        (o.masterwork ? " checked" : "") + '> Aim for masterwork</label>' +
        (mw && mw.why ? '<p class="tb-say">' + esc(capital(mw.why)) + '.</p>' :
          '<p class="tb-say">Aiming raises the DC to the book\'s; not aiming caps the work below masterwork.</p>') + '</div>';
    }
    var info = F.methodInfo(m);
    if (info && info.bulk) {
      var n = o.batch, most = c.max_batch;
      html += '<div class="tag-batch fo-batch"><div class="tb-row"><label class="tb-label" for="forge-batch">Batch</label>' +
        '<div class="tb-step v2-recess">' +
          '<button type="button" class="v2-btn is-small" data-batch="less" aria-label="One fewer"' + (n <= 1 ? " disabled" : "") + '>−</button>' +
          '<input type="number" id="forge-batch" class="v2-well tb-n" min="1" step="1" value="' + n + '" data-batch="n">' +
          '<button type="button" class="v2-btn is-small" data-batch="more" aria-label="One more"' + (most != null && n >= most ? " disabled" : "") + '>+</button>' +
        '</div>' +
        (most > 1 ? '<button type="button" class="v2-btn is-small is-quiet" data-batch="all">All ' + esc(most) + '</button>' : "") + '</div>' +
        (n > 1 ? '<p class="tb-say">One roll and one game for all ' + esc(n) + '; they share one result.</p>' : "") + '</div>';
    }
    host.innerHTML = html;
    var again = keep ? document.getElementById(keep)
      : keepBatch ? host.querySelector('[data-batch="' + keepBatch + '"]') : null;
    if (again && !again.disabled) again.focus();
    else if (keepBatch) F.refocus(["forge-batch"]);
  }
  function capital(t) { t = String(t || ""); return t.charAt(0).toUpperCase() + t.slice(1); }
  makeEl.addEventListener("change", function (e) {
    if (e.target.id === "forge-shape") F.setShape(e.target.value);
    else if (e.target.id === "forge-aim") F.setAim(e.target.checked);
    else if (e.target.id === "forge-batch") F.setBatch(e.target.value);
  });
  makeEl.addEventListener("click", function (e) {
    var b = e.target.closest("[data-batch]");
    if (!b || b.disabled || b.tagName === "INPUT") return;
    var k = b.dataset.batch;
    if (k === "less") F.setBatch(F.order.batch - 1);
    else if (k === "more") F.setBatch(F.order.batch + 1);
    else if (k === "all" && F.check && F.check.max_batch) F.setBatch(F.check.max_batch);
  });

  // --- the paper tag and its ladder --------------------------------------------------------------
  function tierName(i) {
    var c = F.check, t = F.state && F.state.track;
    if (c && c.tiers && c.tiers[i]) return c.tiers[i];
    if (t && t.tiers && t.tiers[i]) return t.tiers[i];
    return "";
  }
  function ladder(at) {
    var c = F.check, t = F.state && F.state.track;
    var ceil = c && c.ceiling != null ? Number(c.ceiling) : (t ? Number(t.ceiling) || 0 : 0);
    var mw = t && t.masterwork_index != null ? Number(t.masterwork_index) : -1;
    var rungs = [];
    if (t && t.next_rung) rungs.push('<li class="rung is-next"><span class="rung-name">' + esc(t.next_rung) + '</span></li>');
    for (var i = ceil; i >= 0; i--) {
      var here = at != null && i === at;
      var name = tierName(i);
      rungs.push('<li class="rung t' + Math.min(4, i) + (i === ceil ? " is-ceiling" : "") + (here ? " is-at" : "") + '"' +
        (here ? ' aria-current="true"' : "") + '><span class="rung-name">' + esc(name) +
        (i === mw ? ' · masterwork' : "") + '</span>' +
        (i === ceil ? '<span class="rung-ceil">your ceiling</span>' : "") + '</li>');
    }
    return '<ol class="tag-ladder" aria-label="Quality, from your ceiling down">' + rungs.join("") + '</ol>';
  }

  function drawTag() {
    var c = F.check, fin = F.result && F.result.finished ? F.result.finish : null;
    if (F.loading || F.error || !F.state) {
      tagBody.innerHTML = '<p class="tag-empty">' + (F.loading ? "Laying out your tools." : "Nothing to show until your rack loads.") + '</p>';
      return;
    }
    var p = c && c.product && c.product[0];
    var at = preview != null ? preview : (fin ? fin.tier : null);
    if (!p && fin && fin.products && fin.products[0]) {
      var made = fin.products[0];
      tagBody.innerHTML = '<h3 class="tag-name">' + esc(made.name) + '</h3>' +
        '<p class="tag-line">' + esc(made.form === "item" ? "finished work" : made.form) + '</p>' + ladder(fin.tier);
      return;
    }
    if (!p) {
      tagBody.innerHTML = '<p class="tag-empty">' + (F.order.method ? "Fill the slots to see what the work makes." : "Choose a method.") +
        '</p>' + ladder(null);
      return;
    }
    var count = 0;
    (c.product || []).forEach(function (x) { if (x === p) count = x.count; });
    tagBody.innerHTML =
      '<h3 class="tag-name">' + esc(p.name) + '</h3>' +
      '<p class="tag-line">' + esc(p.form === "item" ? "finished work" : p.form) + (count > 1 ? ", " + esc(count) + " of them" : "") + '</p>' +
      (c.rent_cp ? '<p class="tag-line">The smith charges ' + esc(c.rent_cp) + ' cp for the hours.</p>' : "") +
      ladder(at);
  }

  // --- the build summary and the build card (UI plan §6.5, §6.6) ----------------------------------
  function drawBuild() {
    var c = F.check, fin = F.result && F.result.finished ? F.result.finish : null;
    var card = c && c.preview && c.preview.card;
    var as = c && c.preview && c.preview.as;
    var made = fin && fin.products && fin.products[0];
    if (!card && made && made.card) { card = made.card; as = ""; }
    if (!card) { buildEl.innerHTML = ""; return; }
    var lines = card.summary && card.summary.length ? card.summary.join(", ") : "No numbers from the metal.";
    buildEl.innerHTML =
      '<h3 class="fo-h">Build</h3>' +
      (as ? '<p class="fo-as">' + esc(as) + ':</p>' : "") +
      '<p class="fo-sum">' + esc(lines) + '</p>' +
      (card.powers && card.powers.length ? '<p class="fo-powers">' + esc(card.powers.join(", ")) + '</p>' : "") +
      '<button type="button" class="v2-btn is-small is-quiet" id="forge-sum" aria-haspopup="dialog">Show the sum</button>';
  }
  buildEl.addEventListener("click", function (e) {
    if (!e.target.closest("#forge-sum")) return;
    var c = F.check, fin = F.result && F.result.finished ? F.result.finish : null;
    var card = (c && c.preview && c.preview.card) || (fin && fin.products && fin.products[0] && fin.products[0].card);
    if (card) F.showCard(card, e.target.closest("#forge-sum"));
  });

  // The build card, a modal of the layer's own: Esc and Close shut it and give focus back
  // to "Show the sum". The core's trap holds Tab inside it (`.bench-modal`).
  //
  // ONE CARD FOR EVERY BENCH (leatherworking contracts §11.1, lane U1): the leather bench's
  // "Show the sum" draws this same card from the same server shape (play/leather_views.py
  // `_card` mirrors play/forge_views.py's), so it is exported as `window.BuildCard.open(card,
  // anchorEl)`. It opens in the popover host of whichever bench the anchor is in, and takes
  // its Esc from that bench's stack (BenchCore.current); a second copy in the leather files
  // would have been the two drifting cards the contract exists to prevent.
  function benchOf(back) {
    var layer = back && back.closest ? back.closest(".bench") : null;
    return layer && !layer.hidden ? layer : document.getElementById("forge");
  }
  F.showCard = function (card, back) { openCard(card, back, document.getElementById("forge-pops"), F.pushEsc, F.dropEsc); };
  // The tanner's marks (leatherworking plan §14.6), one line each, in the server's words: the
  // step and the consumable, what it leaves, and why not when a higher mark of the same kind
  // stands over it. The server sends only the marks the character KNOWS
  // (play/leather_views.py `_marks_card`); nothing here can name one it did not send.
  function markLines(card) {
    return ((card && card.marks) || []).map(function (m) {
      return m.step + " with " + m.material + ": " + m.text +
        (m.applied ? "" : " (not applied: " + m.why + ")");
    });
  }
  window.BuildCard = {
    markLines: markLines,
    open: function (card, anchor) {
      var layer = benchOf(anchor);
      var pops = layer ? layer.querySelector(".bench-pops") : null;
      var core = window.BenchCore && BenchCore.current;
      if (!pops || !core) return false;
      openCard(card, anchor, pops, core.pushEsc, core.dropEsc);
      return true;
    },
  };
  function openCard(card, back, pops, pushEsc, dropEsc) {
    if (!pops || !card) return;
    var cols = card.columns || [];
    var head = '<tr><th scope="col">Target</th>' + cols.map(function (k) {
      return '<th scope="col">' + esc(k.label) + '<small>' + esc(k.material) + ', ' + esc(k.weight) + '</small></th>';
    }).join("") + '<th scope="col">' + esc(card.bonus_head) + '</th><th scope="col">' + esc(card.negative_head) +
      '</th><th scope="col">Final</th></tr>';
    var body = (card.rows || []).map(function (r) {
      return '<tr><th scope="row">' + esc(r.label) + (r.when ? '<small>when it applies</small>' : "") + '</th>' +
        cols.map(function (k) { return '<td>' + esc((r.cells || {})[k.slot] || "0") + '</td>'; }).join("") +
        '<td>' + esc(r.bonus) + '</td><td>' + esc(r.negative) + '</td><td class="fc-final">' + esc(r.final) + '</td></tr>';
    }).join("");
    var wrap = document.createElement("div");
    wrap.className = "bench-modal fc";
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-modal", "true");
    wrap.setAttribute("aria-labelledby", "forge-card-t");
    wrap.innerHTML = '<div class="bench-scrim"></div><div class="bench-dialog fc-dialog v2-framed v2-card-leather">' +
      '<i class="v2-rim" aria-hidden="true"></i>' +
      '<h3 id="forge-card-t">The sum' + (card.quality ? ", at " + esc(card.quality) : "") + '</h3>' +
      '<div class="fc-scroll"><table class="fc-table"><thead>' + head + '</thead><tbody>' + body + '</tbody></table></div>' +
      '<p class="fc-round">Final numbers are rounded toward zero.</p>' +
      (card.powers && card.powers.length ? '<p class="fc-book"><span class="fx-k">By the book, from the main piece:</span> ' +
        esc(card.powers.join(", ")) + '</p>' : "") +
      // The leather card (it carries `by_nature`) is armour and worn goods, where the book's
      // masterwork is not +1 to attack: it says only that the book's masterwork applies.
      (markLines(card).length ? '<p class="fc-book"><span class="fx-k">Marks, once each and never scaled:</span> ' +
        esc(markLines(card).join("; ")) + '</p>' : "") +
      (card.masterwork ? '<p class="fc-book">' + ("by_nature" in card
        ? (card.by_nature ? "Masterwork by its nature, by the book, apart from this sum." : "Masterwork, by the book, apart from this sum.")
        : "Masterwork: the book's +1 to attack, apart from this sum.") + '</p>' : "") +
      '<p class="fc-how">' + esc(card.how || "") + '</p>' +
      '<div class="bench-dialog-acts"><button type="button" class="v2-btn is-quiet" data-close>Close</button></div></div>';
    pops.appendChild(wrap);
    var done = function () {
      dropEsc(done);
      wrap.remove();
      if (back && document.contains(back)) back.focus();
    };
    pushEsc(done);
    wrap.querySelector("[data-close]").addEventListener("click", done);
    wrap.querySelector(".bench-scrim").addEventListener("click", done);
    wrap.querySelector("[data-close]").focus();
  }

  // --- what came of it ---------------------------------------------------------------------------
  function drawResult() {
    var r = F.result;
    if (!r) { resultEl.innerHTML = ""; return; }
    if (r.failed) {
      var out = '<p class="tr-loss">' + esc(r.said || "Failed.") + (r.minutes ? " " + esc(F.minutes(r.minutes)) + " passed." : "") + '</p>';
      if (r.mastery && r.mastery.lines && r.mastery.lines.length) out += mastery(r.mastery.lines);
      resultEl.innerHTML = out;
      return;
    }
    var f = r.finish, parts = [];
    var made = (f.products || [])[0];
    if (made) {
      parts.push('<p class="tr-made">Made ' + esc(made.name) + (made.count > 1 ? " ×" + esc(made.count) : "") +
        (f.tier_name ? ", " + esc(f.tier_name) : "") + '.</p>');
    }
    if (r.stopped) parts.push('<p class="tr-note">Stopped early. You kept what you had.</p>');
    if (r.flat) parts.push('<p class="tr-note">No game for this step in this build: the work was scored at the middle of your range.</p>');
    var mast = f.mastery || {};
    if (mast.lines && mast.lines.length) parts.push(mastery(mast.lines));
    (mast.levelled || []).forEach(function (lv) {
      parts.push('<p class="tr-level">You are now Blacksmith ' + esc(typeof lv === "object" ? lv.level : lv) + '.</p>');
    });
    // A discovery already paid as a "learned: Iron, ..." mastery line is not said twice
    // (seen live: four properties learned on the first forging read as eight lines).
    var paid = (mast.lines || []).map(function (l) { return String(l.why || ""); }).join("\n");
    (f.discoveries || []).forEach(function (d) {
      if (paid.indexOf("learned: " + d.name) >= 0) return;
      parts.push('<p class="tr-new">New: ' + esc(d.name) + ', ' + esc(lower(d.text)) + '.</p>');
    });
    var next = made && made.next ? F.methodInfo(made.next) : null;
    if (next && !next.locked) {
      parts.push('<button type="button" class="v2-btn is-go is-small" id="forge-next" data-next="' + esc(next.id) +
        '" data-carry="' + esc(made.key) + '">Next: ' + esc(next.name) + '</button>');
    } else if (next && next.locked) {
      parts.push('<p class="tr-note">Next is ' + esc(next.name) + ': ' + esc(next.lock_reason) + '.</p>');
    }
    resultEl.innerHTML = parts.join("");
  }
  function mastery(lines) {
    return '<ul class="tr-mastery">' + lines.map(function (l) {
      return '<li><span>' + esc(l.why) + '</span><b>+' + esc(l.mp) + '</b></li>';
    }).join("") + '</ul>';
  }
  function lower(t) { t = String(t || ""); return t.charAt(0).toLowerCase() + t.slice(1); }

  // "Next: Quench" takes the product with it: the method changes and the piece goes in
  // the first slot it fits, once the server has said what fits.
  resultEl.addEventListener("click", function (e) {
    var n = e.target.closest("[data-next]");
    if (!n) return;
    var carry = n.dataset.carry;
    var going = F.setMethod(n.dataset.next, { focus: !carry });
    // Then Roll Craft when the work is whole, else the rack's row, where the next piece
    // (the quenchant, the haft) is picked: never <body>, since this button just went.
    if (going && carry) {
      going.then(function () {
        if (F.item(carry)) F.addItem(carry);
        return F.runCheck();
      }).then(function () { F.refocus(["forge-roll", F.FITS, '#forge-list .fr-add[tabindex="0"]', ".bm[aria-checked='true']"]); });
    }
  });

  function drawAll() { drawSlots(); drawMake(); drawTag(); drawBuild(); }
  F.on("loading", drawAll);
  F.on("error", drawAll);
  F.on("state", drawAll);
  F.on("check", drawAll);
  F.on("order", drawAll);
  F.on("method", function () { preview = null; drawAll(); drawResult(); });
  F.on("rolling", function () { preview = null; drawResult(); });
  F.on("play", function () { preview = 0; drawTag(); });
  F.on("score", function (s) {
    var bands = F.live && F.live.tuning && F.live.tuning.bands;
    if (!bands || !bands.length) return;
    var v = Math.max(0, Math.min(1, Number(s) || 0)), next = 0;
    for (var i = 0; i < bands.length; i++) if (v >= bands[i]) next = i;
    if (next === preview) return;
    preview = next;
    drawTag();
  });
  F.on("result", function () { preview = null; drawAll(); drawResult(); });
})();
