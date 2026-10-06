// The play table, part 48 (the enchanting circle: the working). Classic script in one IIFE,
// reached through `window.Enchant` (45-enchant-shell.js).
//
// UI plan §6.5. The right column is THE WORKING, because what an enchanter reads second
// (after where each essence wants to sit) is what the vessel can hold and what it costs:
//   - the vessel on top: its name, quality and what it holds, with × back to the shelf;
//   - what the step takes: the circle's materials at Prepare (a line of chalk or salt, an
//     ink, a treatment, a focus for a ring or an amulet); the SEATS at Attune and Bind, one
//     row per seat on this vessel, each with its sign in words and what is seated, and the
//     choice a seated essence asks (Bane against [undead]), listing only the engine's own
//     options; the catalyst and Hurry it at Bind; the dropper at Refine;
//   - HOLDS: pips, never a filled track (the design skill's ban), the vessel's capacity as
//     the inside pips and what the working takes as the filled ones, "+2 of +2" in words
//     beside them. The owner's capacity has no +10 frame (round 4): the server sends as
//     many pips as the larger of ten and the capacity, and they wrap;
//   - COSTS: the motes and their parts, the hours and the days, in the server's words;
//   - the DC with every term and the problems, each a sentence;
//   - the paper tag (the herb tag's look, bench.css): the product, the quality ladder from
//     Crude to the ceiling this binding can reach, and the result once it lands.
//
// THE PAGE NEVER COMPUTES A NUMBER (UI plan §12): every figure here is a field of lane E's
// check or state, drawn as sent.

(function () {
  "use strict";
  var E = window.Enchant;
  if (!E) return;
  var esc = E.esc;
  var root = document.getElementById("enchant-working-in");
  if (!root) return;

  root.innerHTML =
    '<section class="ew-take" id="enchant-take" aria-label="What the step takes"></section>' +
    '<section class="ew-sums" id="enchant-sums" aria-label="What it holds and costs"></section>' +
    '<div class="bench-tag v2-page-paper ew-tag" id="enchant-tag"><span class="tag-eyelet" aria-hidden="true"></span>' +
      '<div class="tag-body" id="enchant-tag-body"></div>' +
      '<div class="tag-result" id="enchant-tag-result" aria-live="polite"></div>' +
    '</div>';
  var takeEl = document.getElementById("enchant-take");
  var sumsEl = document.getElementById("enchant-sums");
  var tagBody = document.getElementById("enchant-tag-body");
  var resultEl = document.getElementById("enchant-tag-result");

  // What a choice is called in its seat row, by what it chooses among (lane A's `of`).
  var CHOICE = { creature_type: "Against", damage_type: "Energy", skill: "Skill" };
  function cap(t) { t = String(t || ""); return t.charAt(0).toUpperCase() + t.slice(1); }
  function words(t) { return cap(String(t || "").replace(/-/g, " ")); }

  // --- a slot: filled with its ×, or empty and pressable ------------------------------------
  // An empty slot is a button: pressed, the keyboard goes to the shelf's first row that
  // fits (so Enter there fills it), the forge's work-order pattern.
  function filled(label, it, what, key, extra) {
    var badges = (it.badges || []).slice();
    if (it.quality_name) badges.unshift(it.quality_name);
    return '<div class="ew-slot is-full">' +
      '<span class="ew-label">' + esc(label) + '</span>' +
      '<span class="ew-piece">' + E.iconHtml(E.rowIcon(it), { size: 26, tier: it.tier, label: it.name }) +
        (it.color ? '<i class="fr-swatch" style="--sw:' + esc(it.color) + '" aria-hidden="true"></i>' : "") +
        '<span class="ew-name">' + esc(it.name) + (badges.length ? '<small>' + esc(badges.join(", ")) + '</small>' : "") +
        (extra || "") + '</span></span>' +
      '<button type="button" class="ew-x" data-unput="' + esc(what) + '" data-key="' + esc(key || "") +
        '" aria-label="Take ' + esc(it.name) + ' out of the ' + esc(label.toLowerCase()) + '">×</button></div>';
  }
  function empty(label, hint, opts) {
    opts = opts || {};
    return '<div class="ew-slot is-empty' + (opts.optional ? " is-optional" : "") + (opts.hinted ? " is-hinted" : "") + '">' +
      '<button type="button" class="ew-slot-b" data-pick="' + esc(opts.pick || "") + '"' +
      (opts.seat ? ' data-seat="' + esc(opts.seat) + '"' : "") +
      ' aria-label="' + esc(label + ", empty. " + hint) + '"><span class="ew-label">' + esc(label) + '</span>' +
      '<span class="ew-hint">' + esc(hint) + '</span></button></div>';
  }

  // --- what the step takes ----------------------------------------------------------------------
  function drawTake() {
    var o = E.order, m = o.method;
    if (!m || E.loading || E.error) { takeEl.innerHTML = ""; return; }
    var keep = document.activeElement && takeEl.contains(document.activeElement) ? document.activeElement : null;
    var keepSel = keep ? (keep.id ? "#" + keep.id : keep.dataset.seat ? '[data-seat="' + E.cssEsc(keep.dataset.seat) + '"]' +
                          (keep.tagName === "SELECT" ? "select" : keep.classList.contains("ew-x") ? ".ew-x" : "") : null) : null;
    var html = "";
    var v = E.vessel();
    if (E.usesVessel(m) && m !== "identify") {
      if (v) {
        var h = v.holds || {};
        var line = h.masterwork === false ? "not masterwork" : "holds +" + h.bonus;
        html += filled("Vessel", v, "vessel", "", '<small>' + esc(line) +
          (v.attuned ? ", attuned, " + esc(v.attuned.left_words) + " left" : "") + '</small>');
      } else {
        html += empty("Vessel", m === "prepare" ? "A Superior weapon or armour, a ring or an amulet from the shelf"
                                 : m === "attune" ? "A prepared vessel from the shelf"
                                 : m === "bind" ? "An attuned vessel from the shelf"
                                 : "A magic item from the shelf", { pick: "vessel" });
      }
    }
    if (m === "prepare") html += circleSlots();
    if (m === "attune" || m === "bind") html += seatRows(m);
    if (m === "bind") html += bindExtras();
    if (m === "refine") html += dropper();
    if (m === "read") {
      var es = E.item(o.essence);
      html += '<h3 class="ew-h">Essence</h3>' + (es ? filled("Essence", es, "essence") :
        empty("Essence", "Pick an essence on the shelf: a pinch of it, a tenth of the phial", { pick: "essence" }));
    }
    if (m === "identify") {
      var it = E.item(o.item);
      html += '<h3 class="ew-h">Item</h3>' + (it ? filled("Item", it, "item") :
        empty("Item", "Pick a magic item on the shelf to study", { pick: "item" }));
      if (it && it.card) html += cardLines(it.card);
    }
    takeEl.innerHTML = html;
    if (keepSel) {
      var again = takeEl.querySelector(keepSel);
      if (again && !again.disabled) again.focus();
    }
  }

  function circleSlots() {
    var o = E.order, html = '<h3 class="ew-h">The circle</h3>';
    var of = function (kinds) {
      return o.circle.map(E.item).filter(function (x) { return x && kinds.indexOf(x.kind) >= 0; })[0];
    };
    var line = of(["chalk", "salt"]), ink = of(["ink"]), treat = of(["treatment"]);
    html += line ? filled("Line", line, "circle", line.key) : empty("Line", "Chalk or salt: the circle's line", { pick: "circle" });
    html += ink ? filled("Ink", ink, "circle", ink.key) : empty("Ink", "An ink to cut the sigils", { pick: "circle" });
    html += treat ? filled("Treatment", treat, "circle", treat.key)
                  : empty("Treatment", "Optional: a treatment the circle carries", { pick: "circle", optional: true });
    var focus = E.item(o.focus);
    var v = E.vessel();
    var jewel = v && (v.gear === "ring" || v.slot === "neck");
    if (focus) html += filled("Focus", focus, "focus");
    else if (jewel) html += empty("Focus", "A gem set in the ring or amulet", { pick: "focus" });
    return html;
  }

  // The seats (UI plan §6.5): the check's own rows once it has answered (each with its sign
  // in words and the choice its essence asks), else the vessel's seats as the state sent them.
  function seatRows(m) {
    var v = E.vessel();
    if (!v) return "";
    var c = E.check || {};
    var rows = c.seats && c.seats.length ? c.seats : (v.seats || []).map(function (s) {
      return { seat: s.id, name: s.name, sign: "", essence: null };
    });
    var o = E.order, html = '<h3 class="ew-h">Seats</h3><div class="ew-seats">';
    // At Bind the seats are what the attunement holds: read only. At Attune they are the
    // drop targets.
    var attuned = m === "bind" && v.attuned ? v.attuned.seats || {} : null;
    rows.forEach(function (s) {
      var key = attuned ? (attuned[s.seat] || {}).key : o.seats[s.seat];
      var it = key ? E.item(key) : null;
      var name = s.essence || (attuned && attuned[s.seat] ? attuned[s.seat].name : it ? it.name : "");
      var sign = s.sign ? '<span class="ew-sign">' + esc(cap(s.sign)) + '</span>' : "";
      if (!name) {
        if (m === "attune") {
          html += '<div class="ew-seat is-empty">' + empty(s.name || words(s.seat), (s.sign ? cap(s.sign) + ". " : "") +
            "Pick an essence on the shelf to seat here", { pick: "seat", seat: s.seat, hinted: E.seatHint === s.seat }) + '</div>';
        } else {
          html += '<div class="ew-seat is-empty"><div class="ew-slot is-empty is-still"><span class="ew-label">' +
            esc(s.name || words(s.seat)) + '</span><span class="ew-hint">empty</span></div></div>';
        }
        return;
      }
      var color = s.color || (it && it.color) || "";
      var choice = "";
      if (s.choice) {
        var cid = "ew-c-" + s.seat;
        choice = '<label class="ew-choice" for="' + cid + '"><span>' + esc(CHOICE[s.choice.of] || words(s.choice.key)) + '</span>' +
          '<select id="' + cid + '" class="v2-well ew-select" data-seat="' + esc(s.seat) + '" data-choice="' + esc(s.choice.key) + '"' +
          (m !== "attune" ? " disabled" : "") + '>' +
          '<option value="">Choose</option>' + (s.choice.options || []).map(function (op) {
            var val = typeof op === "object" ? JSON.stringify(op) : String(op);
            return '<option value="' + esc(val) + '"' + (s.choice.chosen === op ? " selected" : "") + '>' + esc(words(val)) + '</option>';
          }).join("") + '</select></label>';
      }
      if (s.bonus) {
        var bid = "ew-b-" + s.seat;
        choice += '<label class="ew-choice" for="' + bid + '"><span>Bonus</span>' +
          '<select id="' + bid + '" class="v2-well ew-select" data-seat="' + esc(s.seat) + '" data-choice="bonus"' +
          (m !== "attune" ? " disabled" : "") + '>' + (s.bonus.options || []).map(function (n) {
            return '<option value="' + esc(n) + '"' + (Number(s.bonus.chosen) === Number(n) ? " selected" : "") + '>+' + esc(n) + '</option>';
          }).join("") + '</select></label>';
      }
      html += '<div class="ew-seat is-full" data-seat-row="' + esc(s.seat) + '">' +
        '<span class="ew-label">' + esc(s.name || words(s.seat)) + '</span>' +
        '<span class="ew-piece"><i class="fr-swatch" style="--sw:' + esc(color) + '" aria-hidden="true"></i>' +
          '<span class="ew-name">' + esc(name) + (s.grants ? '<small>' + esc(s.grants) + (s.motes != null ? ", " + esc(s.motes) + " motes" : "") + '</small>' : "") +
          sign + '</span></span>' +
        (m === "attune" ? '<button type="button" class="ew-x" data-unput="seat" data-key="' + esc(s.seat) +
          '" data-seat="' + esc(s.seat) + '" aria-label="Lift ' + esc(name) + ' off the ' + esc(String(s.name || s.seat).toLowerCase()) + '">×</button>' : "") +
        choice + '</div>';
    });
    return html + '</div>';
  }

  function bindExtras() {
    var o = E.order, cat = E.item(o.catalyst), html = '<h3 class="ew-h">Beside the vessel</h3>';
    html += cat ? filled("Catalyst", cat, "catalyst")
                : empty("Catalyst", "Optional: a catalyst eases the binding", { pick: "catalyst", optional: true });
    html += '<label class="ew-check"><input type="checkbox" id="enchant-hurry"' + (o.hurry ? " checked" : "") + '>' +
      '<span>Hurry it<small>Half the time, and harder</small></span></label>';
    return html;
  }

  function dropper() {
    var o = E.order, keys = Object.keys(o.phials), html = '<h3 class="ew-h">The dropper</h3>';
    if (!keys.length) return html + empty("Phials", "Two or more phials of one essence family, from the shelf", { pick: "essence" });
    return html + '<ul class="ew-parts">' + keys.map(function (k) {
      var it = E.item(k);
      if (!it) return "";
      return '<li class="ew-part"><i class="fr-swatch" style="--sw:' + esc(it.color || "") + '" aria-hidden="true"></i>' +
        '<span class="ew-name">' + esc(it.name) + '</span>' +
        '<span class="tb-step v2-recess">' +
          '<button type="button" class="v2-btn is-small" data-unput="phial" data-key="' + esc(k) + '" aria-label="One ' + esc(it.name) + ' fewer">−</button>' +
          '<span class="ew-n" aria-live="polite">' + esc(o.phials[k]) + '</span>' +
          '<button type="button" class="v2-btn is-small" data-more="' + esc(k) + '" aria-label="One ' + esc(it.name) + ' more"' +
            (o.phials[k] >= it.count ? " disabled" : "") + '>+</button>' +
        '</span></li>';
    }).join("") + '</ul>';
  }

  // The item card's magic section, as lane E/F send it (UI plan §6.6): an unidentified item
  // says only "Magic, faint aura"; a flawed one says FLAWED and never which curse until it
  // is identified for one.
  function cardLines(card) {
    var out = [];
    if (card.summary && !card.identified) out.push('<p class="ew-card-sum">' + esc(card.summary) + '</p>');
    (card.lines || []).forEach(function (l) { out.push('<li>' + esc(l) + '</li>'); });
    (card.powers || []).forEach(function (l) { out.push('<li>' + esc(l) + '</li>'); });
    (card.house || []).forEach(function (l) { out.push('<li class="is-quiet">' + esc(l) + '</li>'); });
    var lis = out.filter(function (x) { return x.indexOf("<li") === 0; });
    var html = out.filter(function (x) { return x.indexOf("<li") !== 0; }).join("") +
      (lis.length ? '<ul class="ew-card">' + lis.join("") + '</ul>' : "");
    if (card.flawed) html += '<p class="ew-flawed">Flawed' + (card.curse ? ": " + esc(card.curse) : "") + '</p>';
    else if (card.curse) html += '<p class="ew-flawed">' + esc(card.curse) + '</p>';
    if (card.curse_question) html += '<p class="ew-quiet">' + esc(cap(card.curse_question)) + '</p>';
    if (card.aura || card.caster_level) {
      html += '<p class="ew-quiet">' + esc([card.aura ? cap(card.aura) + " aura" : "",
                                            card.caster_level ? "caster level " + card.caster_level : ""].filter(Boolean).join(", ")) + '</p>';
    }
    return html;
  }

  // --- holds, costs, the DC and the problems ---------------------------------------------------
  function drawSums() {
    var c = E.check, m = E.order.method;
    if (!c || !m || E.loading || E.error) { sumsEl.innerHTML = ""; return; }
    var html = "";
    if (c.holds) {
      var h = c.holds;
      html += '<div class="ew-holds"><h3 class="ew-h">Holds</h3>' +
        '<p class="ew-pips" role="img" aria-label="' + esc(h.words + (h.why ? ". " + h.why : "")) + '">' +
        (h.pips || []).map(function (p) {
          return '<i class="ew-pip' + (p.filled ? " is-filled" : "") + (p.inside ? " is-inside" : " is-outside") + '"></i>';
        }).join("") + '</p>' +
        '<p class="ew-words"><b>' + esc(h.words) + '</b>' + (h.why ? '<span>' + esc(h.why) + '</span>' : "") + '</p></div>';
    }
    if (c.costs) {
      html += '<div class="ew-costs"><h3 class="ew-h">Costs</h3><p>' + esc(c.costs.words) + '</p>' +
        '<p class="ew-quiet">' + esc(c.costs.time_words) + '</p>' +
        (c.costs.have != null ? '<p class="ew-quiet">The seated essences carry ' + esc(c.costs.have) + ' motes.</p>' : "") + '</div>';
    }
    if (c.dc) {
      html += '<div class="ew-dc"><h3 class="ew-h">DC ' + esc(c.dc) + '</h3><ul class="ew-terms">' +
        (c.dc_terms || []).map(function (t) {
          return '<li><span>' + esc(cap(t.why)) + '</span><b>' + esc(t.dc > 0 && (c.dc_terms || []).indexOf(t) > 0 ? "+" + t.dc : t.dc) + '</b></li>';
        }).join("") + '</ul></div>';
    }
    if ((c.notes || []).length) {
      html += '<ul class="ew-notes">' + c.notes.map(function (n) { return '<li>' + esc(n) + '</li>'; }).join("") + '</ul>';
    }
    if ((c.problems || []).length) {
      html += '<ul class="ew-problems" aria-label="Before you can roll">' + c.problems.map(function (p) {
        return '<li>' + esc(p) + '</li>'; }).join("") + '</ul>';
    }
    sumsEl.innerHTML = html;
  }

  // --- the paper tag -----------------------------------------------------------------------------
  function ladder(names, ceiling, at, next) {
    var rungs = [];
    if (next) rungs.push('<li class="rung is-next"><span class="rung-name">' + esc(next) + '</span></li>');
    for (var i = ceiling; i >= 0; i--) {
      var here = at != null && i === at;
      rungs.push('<li class="rung t' + Math.min(4, i) + (i === ceiling ? " is-ceiling" : "") + (here ? " is-at" : "") + '"' +
        (here ? ' aria-current="true"' : "") + '><span class="rung-name">' + esc(names[i] || "") + '</span>' +
        (i === ceiling ? '<span class="rung-ceil">' + (E.order.method === "bind" ? "this binding's ceiling" : "your ceiling") + '</span>' : "") + '</li>');
    }
    return '<ol class="tag-ladder" aria-label="Quality, from the ceiling down">' + rungs.join("") + '</ol>';
  }
  function drawTag() {
    var s = E.state, c = E.check, o = E.order, m = o.method;
    if (!s || !m) { tagBody.innerHTML = '<p class="tag-empty">Choose a method.</p>'; return; }
    var info = E.methodInfo(m) || {};
    var v = E.vessel();
    var name = (c && c.product && c.product.name) || (v && v.name) ||
      (m === "read" && E.item(o.essence) ? E.item(o.essence).name : "") ||
      (m === "identify" && E.item(o.item) ? E.item(o.item).name : "");
    var names = (c && c.tiers) || (s.track && s.track.tiers) || [];
    var ceiling = c && c.ceiling != null ? Number(c.ceiling) : Number(s.ceiling) || 0;
    var at = null;
    var r = E.result;
    if (r && r.finished && r.finish && r.finish.tier != null) at = Number(r.finish.tier);
    var html = '<h3 class="tag-name">' + esc(name || info.name || "") + '</h3>' +
      '<p class="tag-line">' + esc(info.name || "") + (info.makes ? ": " + esc(info.makes) : "") + '</p>';
    if (!name) html += '<p class="tag-empty">' + esc(info.takes ? "Takes " + info.takes + "." : "") + '</p>';
    if (E.checked(m) && names.length) html += ladder(names, Math.min(ceiling, names.length - 1), at, s.track && s.track.next_rung);
    tagBody.innerHTML = html;
  }

  // --- the result ---------------------------------------------------------------------------------
  function mastery(lines) {
    if (!lines || !lines.length) return "";
    return '<ul class="tr-mastery">' + lines.map(function (l) {
      return '<li><span>' + esc(l.why) + '</span><b>+' + esc(l.mp) + '</b></li>';
    }).join("") + '</ul>';
  }
  function drawResult() {
    var r = E.result;
    if (!r) { resultEl.innerHTML = ""; return; }
    var parts = [];
    if (r.failed) {
      parts.push('<p class="tr-loss">' + esc(r.said || "Failure.") + (r.minutes ? " " + esc(E.minutes(r.minutes)) + " passed." : "") + '</p>');
      parts.push(mastery(r.mastery && r.mastery.lines));
      resultEl.innerHTML = parts.join("");
      return;
    }
    if (r.read) {
      var d = r.read;
      parts.push('<p class="tr-made">' + (d.revealed && d.revealed.length ? "You learn: " +
        esc(d.revealed.map(function (x) { return x.text; }).join("; ")) + "." : "Nothing new in it.") + '</p>');
      if (d.pinch) parts.push('<p class="tr-note">' + esc(d.name) + ": " + esc(d.pinch.left) + " of the phial left.</p>");
      if (d.danger_text) parts.push('<p class="tr-loss">' + esc(d.danger_text) + '</p>');
      parts.push(mastery(d.mastery && d.mastery.lines));
      resultEl.innerHTML = parts.join("");
      return;
    }
    if (r.identify) {
      var i = r.identify;
      parts.push('<p class="' + (i.result === "fail" ? "tr-note" : "tr-made") + '">' + esc(i.words) + '</p>');
      if (i.card) parts.push(cardLines(i.card));
      if (i.result === "fail" && i.again_on_day) parts.push('<p class="tr-note">You can try again on day ' + esc(i.again_on_day) + '.</p>');
      parts.push(mastery(i.mastery && i.mastery.lines));
      resultEl.innerHTML = parts.join("");
      return;
    }
    var f = r.finish || {};
    var made = (f.products || [])[0];
    if (r.flawed) parts.push('<p class="tr-loss">Flawed. It took, but something went wrong in the binding.</p>');
    if (f.said) parts.push('<p class="tr-made">' + esc(f.said) + '</p>');
    if (f.tier_name && r.method !== "bind") parts.push('<p class="tr-note">Quality: ' + esc(f.tier_name) + '.</p>');
    if (f.tier_name && r.method === "bind") parts.push('<p class="tr-note">Bound at ' + esc(f.tier_name) + '.</p>');
    if (r.stopped) parts.push('<p class="tr-note">Stopped early. You kept what you had.</p>');
    if (r.flat) parts.push('<p class="tr-note">No game for this step in this build: the work was scored at the middle of your range.</p>');
    var mast = f.mastery || {};
    parts.push(mastery(mast.lines));
    (mast.levelled || []).forEach(function (lv) {
      parts.push('<p class="tr-level">You are now Enchanter ' + esc(typeof lv === "object" ? lv.level : lv) + '.</p>');
    });
    var paid = (mast.lines || []).map(function (l) { return String(l.why || ""); }).join("\n");
    (f.discoveries || []).forEach(function (d) {
      if (!d.text || paid.indexOf("learned: " + d.name) >= 0) return;
      parts.push('<p class="tr-new">New: ' + esc(d.name) + ', ' + esc(d.text) + '.</p>');
    });
    var next = made && E.NEXT[made.state] ? E.methodInfo(E.NEXT[made.state]) : null;
    if (next && !next.locked) {
      parts.push('<button type="button" class="v2-btn is-go is-small" id="enchant-next" data-next="' + esc(next.id) +
        '" data-carry="' + esc(made.key) + '">Next: ' + esc(next.name) + '</button>');
    } else if (next && next.locked) {
      parts.push('<p class="tr-note">Next is ' + esc(next.name) + ': ' + esc(next.lock_reason) + '.</p>');
    }
    if (made && made.state === "in_progress" && window.Works && typeof Works.open === "function") {
      parts.push('<button type="button" class="v2-btn is-small" id="enchant-works">In progress</button>');
    }
    resultEl.innerHTML = parts.join("");
  }

  // Every check redraws the column, and the check after a finish lands a beat after the
  // result: redrawn under it, "Next: Attune" lost the keyboard to <body> (seen live,
  // 2026-10-06, the first Prepare on scratch data). The focused control is found again by
  // its id.
  function drawAll() {
    var at = document.activeElement;
    var id = at && root.contains(at) && at.id ? at.id : null;
    drawTake(); drawSums(); drawTag(); drawResult();
    if (id && document.activeElement !== at) {
      var again = document.getElementById(id);
      if (again && !again.disabled) again.focus();
    }
  }
  ["loading", "error", "state", "check", "order", "method", "result", "rolling"].forEach(function (ev) { E.on(ev, drawAll); });

  // --- the column's own controls ------------------------------------------------------------------
  root.addEventListener("click", function (e) {
    var n = e.target.closest("[data-next]");
    if (n) {
      // "Next: Attune" takes the vessel with it (its key after this step), then the keyboard
      // goes to where the next thing is picked: the shelf's first fitting row, or Roll.
      var going = E.setMethod(n.dataset.next, { carry: n.dataset.carry });
      if (going) going.then(function () {
        E.refocus(["#enchant-take .ew-slot-b", "#enchant-list .es-add:not([aria-disabled='true'])", "enchant-roll"]);
      });
      return;
    }
    if (e.target.closest("#enchant-works")) { Works.open(e.target.closest("#enchant-works")); return; }
    var x = e.target.closest("[data-unput]");
    if (x && root.contains(x)) {
      e.stopPropagation();
      E.remove(x.dataset.unput, x.dataset.key);
      E.refocus(["#enchant-take .ew-slot-b", "enchant-roll"]);
      return;
    }
    var more = e.target.closest("[data-more]");
    if (more && !more.disabled) { E.addItem(more.dataset.more); return; }
    var b = e.target.closest(".ew-slot-b");
    if (b) {
      // An empty slot pressed: the keyboard moves to the shelf's first row that fits, so
      // Enter there fills it. An empty seat remembers itself as where that essence goes.
      if (b.dataset.seat) E.seatHint = b.dataset.seat;
      drawTake();
      var row = document.querySelector("#enchant-list .es-add[data-add]:not([aria-disabled='true'])");
      if (row) { row.focus(); E.say("Pick what goes here on the shelf."); }
      else E.say("Nothing on your shelf goes here.");
    }
  });
  root.addEventListener("change", function (e) {
    var sel = e.target.closest("select[data-choice]");
    if (sel) {
      var v = sel.value;
      if (sel.dataset.choice === "bonus") v = v === "" ? "" : Number(v);
      E.setChoice(sel.dataset.seat, sel.dataset.choice, v);
      return;
    }
    if (e.target.id === "enchant-hurry") E.setHurry(e.target.checked);
  });
})();
