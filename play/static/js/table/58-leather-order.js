// The play table, part 58 (the leather bench: the work order). Classic script in one IIFE,
// reached through `window.Leather` (55-leather-shell.js).
//
// UI plan §6.5 and §6.6. The right column is a WORK ORDER, the forge's shape for leather:
//   - the piece slots on top, labelled by what is being made: a step's inputs (Hide and
//     Curing salt at Salt; Hide and Tannin at Tan; Piece and Thread at Stitch), and at Assemble
//     Body, Fastenings, Lining. Each is a drop target and a button: filled, it shows the piece
//     with its swatch, grade and laminations and a × to take it off; empty, it says what goes
//     there, and pressing it sends the keyboard to the rack's first row that fits;
//   - what is being made: the pattern picked from the server's list at Cut (never typed) and
//     whether it is the body or the lining; the hair at Tan; the ambition at Assemble; the
//     batch for the methods that take one;
//   - the paper tag (the herb tag's look): the product, and the quality ladder from Crude to
//     the step's ceiling, the hide's GRADE CAP marked on its rung, and the server's words for
//     why the ceiling stops where it does ("grade 2 hide: Superior is the most it allows").
//     Where the body is masterwork by its nature (dragonhide, eel hide, angelskin, darkleaf),
//     the tag says so on every rung, so nobody chases Superior for it;
//   - the base hand-off line ("A base: the forge finishes it into studded leather...");
//   - the build summary and "Show the sum": the forge's own card (`window.BuildCard`).
//
// THE PAGE NEVER COMPUTES A NUMBER (UI plan §12): every cell of the build card, the ceiling,
// the cap and the units are the server's (play/leather_views.py), drawn as sent.

(function () {
  "use strict";
  var L = window.Leather;
  if (!L) return;
  var esc = L.esc;
  var root = document.getElementById("leather-order-in");
  if (!root) return;

  root.innerHTML =
    '<section class="fo-slots lo-slots" id="leather-slots" aria-label="The work order"></section>' +
    '<div class="fo-make lo-make" id="leather-make"></div>' +
    '<div class="bench-tag v2-page-paper fo-tag" id="leather-tag"><span class="tag-eyelet" aria-hidden="true"></span>' +
      '<div class="tag-body" id="leather-tag-body"></div>' +
      '<div class="tag-result" id="leather-tag-result" aria-live="polite"></div>' +
    '</div>' +
    '<div class="fo-build" id="leather-build"></div>';
  var slotsEl = document.getElementById("leather-slots");
  var makeEl = document.getElementById("leather-make");
  var tagBody = document.getElementById("leather-tag-body");
  var resultEl = document.getElementById("leather-tag-result");
  var buildEl = document.getElementById("leather-build");

  // While a game runs the ladder's pointer follows the live score; the tier the work GETS is
  // the server's and replaces this the moment the finish answers.
  var preview = null;

  function capital(t) { t = String(t || ""); return t.charAt(0).toUpperCase() + t.slice(1); }
  function lower(t) { t = String(t || ""); return t.charAt(0).toLowerCase() + t.slice(1); }

  // --- the slots --------------------------------------------------------------------------------
  function pieceHtml(it) {
    var bits = [];
    if (it.units_words) bits.push(it.units_words);
    if (it.grade_words) bits.push(it.grade_words);
    (it.badges || []).forEach(function (b) { bits.push(b); });
    if (it.quality_name) bits.push(it.quality_name);
    return '<span class="fo-piece">' + L.iconHtml(L.rowIcon(it), { size: 26, tier: it.tier, label: it.name }) +
      '<i class="fr-swatch" style="--sw:' + esc(it.color || "") + '" aria-hidden="true"></i>' +
      '<span class="fo-name">' + esc(it.name) + (bits.length ? '<small>' + esc(bits.join(", ")) + '</small>' : "") + '</span></span>';
  }
  function drawSlots() {
    var o = L.order, m = o.method;
    if (!m || L.loading || L.error) { slotsEl.innerHTML = ""; return; }
    var keep = document.activeElement && slotsEl.contains(document.activeElement) ? document.activeElement : null;
    var keepSel = keep && keep.dataset.slot ? '[data-slot="' + keep.dataset.slot + '"]' + (keep.classList.contains("fo-x") ? ".fo-x" : ".fo-slot-b") : null;
    var html = "";
    if (m === "grade") {
      var it = o.grade ? ((L.state && L.state.rack) || []).filter(function (r) { return r.material === o.grade; })[0] : null;
      if (it) {
        html = '<div class="fo-slot is-full" data-slot="grade"><span class="fo-label">Scrap of</span>' + pieceHtml(it) +
          '<button type="button" class="fo-x" data-slot="grade" aria-label="Put the ' + esc(it.name) + ' back">×</button></div>';
      } else {
        html = '<div class="fo-slot is-empty" data-slot="grade"><button type="button" class="fo-slot-b" data-slot="grade" ' +
          'aria-label="Scrap of, empty. Pick a material on your rack to grade">' +
          '<span class="fo-label">Scrap of</span><span class="fo-hint">Pick a material on your rack to grade</span></button></div>';
      }
    } else {
      L.slots().forEach(function (s) {
        var key = o.slots[s.id];
        var it = key && L.item(key);
        if (it) {
          html += '<div class="fo-slot is-full" data-slot="' + esc(s.id) + '">' +
            '<span class="fo-label">' + esc(s.label) + '</span>' + pieceHtml(it) +
            '<button type="button" class="fo-x" data-slot="' + esc(s.id) + '" aria-label="Take ' + esc(it.name) +
              ' off the ' + esc(s.label.toLowerCase()) + ' slot">×</button></div>';
        } else {
          var hinted = L.slotHint === s.id;
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
    if (x) {
      if (x.dataset.slot === "grade") L.removeGrade(); else L.removeSlot(x.dataset.slot);
      L.refocus(['[data-slot="' + x.dataset.slot + '"].fo-slot-b', "leather-roll"]);
      return;
    }
    var b = e.target.closest(".fo-slot-b");
    if (!b) return;
    // An empty slot pressed: the next row picked in the rack goes here. The keyboard moves to
    // the first row that fits this slot, so Enter fills it.
    var slot = b.dataset.slot;
    L.slotHint = slot === "grade" ? null : slot;
    drawSlots();
    var rows = Array.prototype.slice.call(document.querySelectorAll("#leather-list .lr-add[data-add]"));
    var row = rows.filter(function (r) {
      return slot === "grade" ? L.why(r.dataset.add) === "" : L.fit(slot, r.dataset.add) === "";
    })[0];
    var name = slot === "grade" ? "a material to grade" : "what goes in the " + L.label(slot) + " slot";
    if (row) { row.focus(); L.say("Pick " + name + "."); }
    else L.say("Nothing you carry " + (slot === "grade" ? "can be graded." : "goes in the " + L.label(slot) + " slot."));
  });

  // A drop on a slot puts the dragged row in THAT slot.
  function slotOf(e) { var s = e.target.closest && e.target.closest(".fo-slot"); return s ? s.dataset.slot : null; }
  slotsEl.addEventListener("dragover", function (e) {
    if (!L.dragKey || !slotOf(e)) return;
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
    if (!L.dragKey || !slot) return;
    e.preventDefault();
    e.stopPropagation();
    slotsEl.querySelectorAll(".is-dragover").forEach(function (x) { x.classList.remove("is-dragover"); });
    var key = L.dragKey;
    L.dragKey = null;
    L.addItem(key, slot === "grade" ? null : slot);
  });

  // --- what is being made: the pattern, the part, the hair, the ambition, the batch -------------
  // The pattern picker is built once per method and redrawn only when its list changes, so a
  // keyboard player's type-ahead survives the check that answers each choice (the forge's
  // lesson, seen live 2026-10-04: "l" chose a light hammer and the redraw ate the "o").
  var pickSig = "";
  function drawMake() {
    var o = L.order, m = o.method;
    if (!m || L.loading || L.error) { makeEl.innerHTML = ""; pickSig = ""; return; }
    var prods = (L.state && L.state.products) || [];
    var sig = m + ":" + prods.length + ":" + (m === "cut" && L.hasLining(o.product) ? "l" : "");
    var rest = makeEl.querySelector(".lo-rest");
    if (sig !== pickSig || !rest) {
      makeEl.innerHTML = '<div class="lo-pickbox">' + (m === "cut" ? patternHtml(prods, o) : m === "tan" ? hairHtml(o) : "") +
        '</div><div class="lo-rest"></div>';
      pickSig = sig;
      rest = makeEl.querySelector(".lo-rest");
    } else {
      var sel = document.getElementById("leather-pattern");
      if (sel && sel.value !== (o.product || "")) sel.value = o.product || "";
      var part = document.getElementById("leather-part");
      if (part && part.value !== o.part) part.value = o.part;
      var hair = document.getElementById("leather-hair");
      if (hair && hair.value !== o.hair) hair.value = o.hair;
    }
    drawRest(rest);
  }
  function patternHtml(prods, o) {
    var made = prods.filter(function (p) { return p.gear !== "piece"; });
    var pieces = prods.filter(function (p) { return p.gear === "piece"; });
    // The hide each pattern's body takes, not its book DC: the DC there is Assemble's, and
    // beside Cut's own "DC 10" in the info line it read as two DCs for one step (seen live,
    // 2026-10-08: "Leather Armour, 2 units, DC 12" over "DC 10, you need 7 or better").
    var opt = function (p) {
      return '<option value="' + esc(p.id) + '"' + (p.id === o.product ? " selected" : "") + '>' + esc(p.name) +
        ', ' + esc(p.body_words) + '</option>';
    };
    var html = '<div class="fo-field"><label class="bs-label" for="leather-pattern">What to cut</label>' +
      '<select id="leather-pattern" class="v2-well bs-show fo-shape"><option value="">Choose from the patterns</option>' +
      '<optgroup label="Armour, shields and worn goods">' + made.map(opt).join("") + '</optgroup>' +
      '<optgroup label="Pieces">' + pieces.map(opt).join("") + '</optgroup></select></div>';
    var p = L.product(o.product);
    if (p && p.lining_units) {
      html += '<div class="fo-field"><label class="bs-label" for="leather-part">Cut it for</label>' +
        '<select id="leather-part" class="v2-well bs-show fo-shape">' +
        '<option value="body"' + (o.part !== "lining" ? " selected" : "") + '>The body, ' + esc(p.body_words) + '</option>' +
        '<option value="lining"' + (o.part === "lining" ? " selected" : "") + '>The lining, ' + esc(p.lining_words) + '</option>' +
        '</select></div>';
    }
    return html;
  }
  function hairHtml(o) {
    return '<div class="fo-field"><label class="bs-label" for="leather-hair">The hair</label>' +
      '<select id="leather-hair" class="v2-well bs-show fo-shape">' +
      '<option value=""' + (!o.hair ? " selected" : "") + '>As the hide suits it</option>' +
      '<option value="off"' + (o.hair === "off" ? " selected" : "") + '>Off: leather</option>' +
      '<option value="on"' + (o.hair === "on" ? " selected" : "") + '>On: fur</option></select></div>';
  }
  function drawRest(host) {
    var o = L.order, m = o.method, c = L.check || {};
    var keep = document.activeElement && host.contains(document.activeElement) ? document.activeElement.id : null;
    var keepBatch = document.activeElement && host.contains(document.activeElement) ? document.activeElement.dataset.batch : null;
    var html = "";
    if (m === "assemble") {
      var mw = c.masterwork || null;
      html += '<div class="fo-field fo-aim"><label class="fo-check"><input type="checkbox" id="leather-aim"' +
        (o.masterwork ? " checked" : "") + (mw && mw.by_nature ? " disabled" : "") + '> Aim for masterwork</label>' +
        (mw && mw.why ? '<p class="tb-say">' + esc(capital(mw.why)) + '.</p>' :
          '<p class="tb-say">Aiming raises the DC to the book\'s; not aiming keeps the work below masterwork.</p>') + '</div>';
    }
    var info = L.methodInfo(m);
    if (info && info.bulk) {
      var n = o.batch, most = c.max_batch;
      html += '<div class="tag-batch fo-batch"><div class="tb-row"><label class="tb-label" for="leather-batch">Batch</label>' +
        '<div class="tb-step v2-recess">' +
          '<button type="button" class="v2-btn is-small" data-batch="less" aria-label="One fewer"' + (n <= 1 ? " disabled" : "") + '>−</button>' +
          '<input type="number" id="leather-batch" class="v2-well tb-n" min="1" step="1" value="' + n + '" data-batch="n">' +
          '<button type="button" class="v2-btn is-small" data-batch="more" aria-label="One more"' + (most != null && n >= most ? " disabled" : "") + '>+</button>' +
        '</div>' +
        (most > 1 ? '<button type="button" class="v2-btn is-small is-quiet" data-batch="all">All ' + esc(most) + '</button>' : "") + '</div>' +
        (n > 1 ? '<p class="tb-say">One roll and one game for all ' + esc(n) + '; they share one result.</p>' : "") + '</div>';
    }
    host.innerHTML = html;
    var again = keep ? document.getElementById(keep)
      : keepBatch ? host.querySelector('[data-batch="' + keepBatch + '"]') : null;
    if (again && !again.disabled) again.focus();
  }
  makeEl.addEventListener("change", function (e) {
    if (e.target.id === "leather-pattern") L.set("product", e.target.value);
    else if (e.target.id === "leather-part") L.set("part", e.target.value);
    else if (e.target.id === "leather-hair") L.set("hair", e.target.value);
    else if (e.target.id === "leather-aim") L.set("masterwork", e.target.checked);
    else if (e.target.id === "leather-batch") L.set("batch", e.target.value);
  });
  makeEl.addEventListener("click", function (e) {
    var b = e.target.closest("[data-batch]");
    if (!b || b.disabled || b.tagName === "INPUT") return;
    var k = b.dataset.batch;
    if (k === "less") L.set("batch", L.order.batch - 1);
    else if (k === "more") L.set("batch", L.order.batch + 1);
    else if (k === "all" && L.check && L.check.max_batch) L.set("batch", L.check.max_batch);
  });

  // --- the paper tag and its ladder --------------------------------------------------------------
  function tierName(i) {
    var c = L.check, t = L.state && L.state.track;
    if (c && c.tiers && c.tiers[i]) return c.tiers[i];
    if (t && t.tiers && t.tiers[i]) return t.tiers[i];
    return "";
  }
  function ladder(at) {
    var c = L.check, t = L.state && L.state.track;
    var ceil = c && c.ceiling != null ? Number(c.ceiling) : (t ? Number(t.ceiling) || 0 : 0);
    var mw = t && t.masterwork_index != null ? Number(t.masterwork_index) : -1;
    var cap = c && c.grade_cap != null ? Number(c.grade_cap) : null;
    var nature = !!(c && c.masterwork && c.masterwork.by_nature);
    var rungs = [];
    if (t && t.next_rung) rungs.push('<li class="rung is-next"><span class="rung-name">' + esc(t.next_rung) + '</span></li>');
    for (var i = ceil; i >= 0; i--) {
      var here = at != null && i === at;
      rungs.push('<li class="rung t' + Math.min(4, i) + (i === ceil ? " is-ceiling" : "") + (here ? " is-at" : "") + '"' +
        (here ? ' aria-current="true"' : "") + '><span class="rung-name">' + esc(tierName(i)) +
        (nature ? ' · masterwork by its nature' : i === mw ? ' · masterwork' : "") + '</span>' +
        (i === ceil ? '<span class="rung-ceil">' + (cap != null && cap === ceil ? "the hide's grade cap" : "your ceiling") + '</span>' : "") + '</li>');
    }
    return '<ol class="tag-ladder" aria-label="Quality, from the ceiling down">' + rungs.join("") + '</ol>';
  }
  function drawTag() {
    var c = L.check, fin = L.result && L.result.finished ? L.result.finish : null;
    if (L.loading || L.error || !L.state) {
      tagBody.innerHTML = '<p class="tag-empty">' + (L.loading ? "Laying out your tools." : "Nothing to show until your rack loads.") + '</p>';
      return;
    }
    if (L.order.method === "grade") {
      tagBody.innerHTML = '<h3 class="tag-name">Grade</h3><p class="tag-line">' +
        esc(L.card ? L.card.name + ": " + L.card.grade_cost + " for one benefit and one drawback" :
            "A scrap of a material shows one benefit and one drawback.") + '</p>';
      return;
    }
    var p = c && c.products && c.products[0];
    var at = preview != null ? preview : (fin ? fin.tier : null);
    if (!p && fin && fin.products && fin.products[0]) {
      var made = fin.products[0];
      tagBody.innerHTML = '<h3 class="tag-name">' + esc(made.name) + '</h3>' +
        '<p class="tag-line">' + esc(made.form === "item" ? "finished work" : [made.form, made.units_words].filter(Boolean).join(", ")) + '</p>' +
        ladder(fin.tier);
      return;
    }
    if (!p) {
      tagBody.innerHTML = '<p class="tag-empty">' + (L.order.method ? "Fill the slots to see what the work makes." : "Choose a method.") +
        '</p>' + ladder(null);
      return;
    }
    var line = [p.form === "item" ? "finished work" : p.form, p.units_words, p.count > 1 ? p.count + " of them" : ""].filter(Boolean).join(", ");
    var offcut = (c.products || []).filter(function (x) { return x.offcut; })[0];
    tagBody.innerHTML =
      '<h3 class="tag-name">' + esc(p.name) + '</h3>' +
      '<p class="tag-line">' + esc(line) + '</p>' +
      (offcut ? '<p class="tag-line">The offcut goes back on your rack: ' + esc(offcut.name) + ', ' + esc(offcut.units_words) + '.</p>' : "") +
      ladder(at) +
      ((c.ceiling_why || []).length ? '<ul class="lo-why">' + c.ceiling_why.map(function (w) {
        return '<li>' + esc(capital(w)) + '</li>'; }).join("") + '</ul>' : "") +
      (c.base_line ? '<p class="lo-base">' + esc(c.base_line) + '</p>' : "");
  }

  // --- the build summary and the build card (UI plan §6.5, §6.6) ----------------------------------
  // The card is the forge's (43-forge-order.js `window.BuildCard`), one card for every bench.
  // The server's "from the creature" lines are not drawn here: a generic hide's inherited
  // resistance is a property the player learns by Grade, not one the order should name.
  function cardNow() {
    var c = L.check, fin = L.result && L.result.finished ? L.result.finish : null;
    var card = c && c.preview && c.preview.card;
    var made = fin && fin.products && fin.products[0];
    if (!card && made && made.card) return { card: made.card, as: "" };
    return card ? { card: card, as: c.preview.as || "" } : null;
  }
  function drawBuild() {
    var got = L.order.method === "grade" ? null : cardNow();
    if (!got) { buildEl.innerHTML = ""; return; }
    var card = got.card;
    var lines = card.summary && card.summary.length ? card.summary.join(", ") : "No numbers from the hide.";
    var canCard = !!(window.BuildCard && typeof BuildCard.open === "function");
    buildEl.innerHTML =
      '<h3 class="fo-h">Build</h3>' +
      (got.as ? '<p class="fo-as">' + esc(got.as) + ':</p>' : "") +
      '<p class="fo-sum">' + esc(lines) + '</p>' +
      (card.powers && card.powers.length ? '<p class="fo-powers">By the book: ' + esc(card.powers.join(", ")) + '</p>' : "") +
      (card.by_nature ? '<p class="fo-powers">Masterwork by its nature.</p>' : "") +
      (canCard ? '<button type="button" class="v2-btn is-small is-quiet" id="leather-sum" aria-haspopup="dialog">Show the sum</button>' : "");
  }
  buildEl.addEventListener("click", function (e) {
    var b = e.target.closest("#leather-sum");
    var got = cardNow();
    if (!b || !got || !window.BuildCard) return;
    BuildCard.open(got.card, b);
  });

  // --- what came of it ---------------------------------------------------------------------------
  function mastery(lines) {
    return '<ul class="tr-mastery">' + lines.map(function (l) {
      return '<li><span>' + esc(l.why) + '</span><b>+' + esc(l.mp) + '</b></li>';
    }).join("") + '</ul>';
  }
  function levelled(list) {
    return (list || []).map(function (lv) {
      return '<p class="tr-level">You are now Leatherworker ' + esc(typeof lv === "object" ? lv.level : lv) + '.</p>';
    }).join("");
  }
  function drawResult() {
    var r = L.result;
    if (!r) { resultEl.innerHTML = ""; return; }
    var parts = [];
    if (r.failed) {
      parts.push('<p class="tr-loss">' + esc(r.said || "Failed.") + (r.minutes ? " " + esc(L.minutes(r.minutes)) + " passed." : "") + '</p>');
      if (r.mastery && r.mastery.lines && r.mastery.lines.length) parts.push(mastery(r.mastery.lines));
      resultEl.innerHTML = parts.join("");
      return;
    }
    if (r.graded) {
      var g = r.graded;
      parts.push('<p class="tr-made">' + esc(g.name) + ': ' + (g.revealed && g.revealed.length
        ? esc(g.revealed.map(function (x) { return lower(x.text || x.key); }).join("; ")) : "nothing new") + '.</p>');
      if (g.minutes) parts.push('<p class="tr-note">' + esc(L.minutes(g.minutes)) + ' passed, and a scrap is gone.</p>');
      if (g.mastery && g.mastery.lines && g.mastery.lines.length) parts.push(mastery(g.mastery.lines));
      parts.push(levelled(g.mastery && g.mastery.levelled));
      resultEl.innerHTML = parts.join("");
      return;
    }
    if (r.collected) {
      var k = r.collected;
      parts.push('<p class="tr-made">' + (k.waited ? esc("You waited " + L.minutes(k.waited) + ". ") : "") + esc(k.said || "") + '</p>');
      resultEl.innerHTML = parts.join("");
      return;
    }
    var f = r.finish;
    var made = (f.products || [])[0];
    if (made) {
      parts.push('<p class="tr-made">Made ' + esc(made.name) + (made.count > 1 ? " ×" + esc(made.count) : "") +
        (f.tier_name ? ", " + esc(f.tier_name) : "") + '.</p>');
    }
    // What was paid: the yard's hours at the roll, the vats as the hides went in.
    (r.rent || []).concat(f.paid || []).forEach(function (p) {
      parts.push('<p class="tr-note">Paid ' + esc(p.cp) + ' cp for ' + esc(p["for"]) + '.</p>');
    });
    if (r.stopped) parts.push('<p class="tr-note">Stopped early. You kept what you had.</p>');
    if (r.flat) parts.push('<p class="tr-note">No game for this step in this build: the work was scored at the middle of your range.</p>');
    var mast = f.mastery || {};
    if (mast.lines && mast.lines.length) parts.push(mastery(mast.lines));
    parts.push(levelled(mast.levelled));
    // A discovery already paid as a "learned: Deer Hide, ..." mastery line is not said twice.
    var paid = (mast.lines || []).map(function (l) { return String(l.why || ""); }).join("\n");
    (f.discoveries || []).forEach(function (d) {
      if (paid.indexOf("learned: " + d.name) >= 0) return;
      parts.push('<p class="tr-new">New: ' + esc(d.name) + ', ' + esc(lower(d.text)) + '.</p>');
    });
    if (made && Number(made.waits) > 0) {
      // A tannage in the vat or the pack, or a hide in the lime pit: In progress has it, with
      // its countdown on game time. Wait for it lets the days pass and takes it out.
      var where = String(made.where || "").indexOf("place:") === 0 ? "in the vat" : "in your pack";
      parts.push('<p class="tr-note">It waits ' + esc(L.minutes(made.waits)) + ' ' + esc(where) + '. It is In progress until then.</p>');
      parts.push('<button type="button" class="v2-btn is-go is-small" id="leather-wait" data-wait="' + esc(made.key) +
        '" data-wait-min="' + esc(made.waits) + '">Wait for it</button>');
    } else {
      var next = made && made.next ? L.methodInfo(made.next) : null;
      if (next && !next.locked) {
        parts.push('<button type="button" class="v2-btn is-go is-small" id="leather-next" data-next="' + esc(next.id) +
          '" data-carry="' + esc(made.key) + '">Next: ' + esc(next.name) + '</button>');
      } else if (next && next.locked) {
        parts.push('<p class="tr-note">Next is ' + esc(next.name) + ': ' + esc(next.lock_reason) + '.</p>');
      }
    }
    resultEl.innerHTML = parts.join("");
  }

  // "Next: Flense" takes the product with it: the method changes and the piece goes in the
  // first slot it fits, once the server has said what fits. Wait for it lets the days pass.
  resultEl.addEventListener("click", function (e) {
    var w = e.target.closest("[data-wait]");
    if (w) { L.waitFor(w.dataset.wait, !!(L.result && L.result.two_halves), w.dataset.waitMin); return; }
    var n = e.target.closest("[data-next]");
    if (!n) return;
    var carry = n.dataset.carry;
    var going = L.setMethod(n.dataset.next, { focus: !carry });
    if (going && carry) {
      going.then(function () {
        if (L.item(carry)) L.addItem(carry);
        return L.runCheck();
      }).then(function () { L.refocus(["leather-roll", L.FITS, '#leather-list .lr-add[tabindex="0"]', ".bm[aria-checked='true']"]); });
    }
  });

  function drawAll() { drawSlots(); drawMake(); drawTag(); drawBuild(); }
  L.on("loading", drawAll);
  L.on("error", drawAll);
  L.on("state", drawAll);
  L.on("check", drawAll);
  L.on("order", drawAll);
  L.on("card", drawAll);
  L.on("grade", drawAll);
  L.on("method", function () { preview = null; drawAll(); drawResult(); });
  L.on("rolling", function () { preview = null; drawResult(); });
  L.on("play", function () { preview = 0; drawTag(); });
  L.on("score", function (s) {
    var bands = L.live && L.live.tuning && L.live.tuning.bands;
    if (!bands || !bands.length) return;
    var v = Math.max(0, Math.min(1, Number(s) || 0)), next = 0;
    for (var i = 0; i < bands.length; i++) if (v >= bands[i]) next = i;
    if (next === preview) return;
    preview = next;
    drawTag();
  });
  L.on("result", function () { preview = null; drawAll(); drawResult(); });
})();
