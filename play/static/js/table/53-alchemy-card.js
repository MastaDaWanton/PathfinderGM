// The play table, part 53 (the alchemy bench: the formula card). Classic script in one IIFE,
// reached through `window.Alchemy` (50-alchemy-shell.js).
//
// UI plan §6.5. The right column is THE FORMULA CARD, because what an alchemist reads second
// (after the colour and level in the glass) is what the mix could become and what it costs.
// From top to bottom:
//   - what goes in: the inputs, the solvent at Dissolve, the vessel at Bottle (the family
//     and its slots in words), the catalysts beside the work (never spent), the batch, and
//     Transmute's target; or, for the single requests, the reagent to assay, the potion to
//     identify, the writings to learn from;
//   - the formula at Bottle: known formulae for this vessel's family, and Experiment, with
//     what a chosen formula needs and what the mix has, in the server's words;
//   - COULD STILL BECOME N: the possible-formulae count, always visible while building
//     (owner Q5.3: "a count of possible formulae, never their names"; the server's line);
//   - the trait slots: one row per trait the pool offers, a check for each, its grade and
//     its cap in words, and why a trait cannot go in ("a potion cannot carry a trait that
//     works on the skin"); the drawbacks, always listed, never optional;
//   - the DC with every term, the stakes again, the problems, each a sentence;
//   - the paper tag (the herb tag's look, bench.css): the product, the quality ladder to the
//     ceiling, and for a spell potion each rung's caster level and price ("Fine, CL 2,
//     100 gp"), then the result once it lands.
//
// THE PAGE NEVER COMPUTES A NUMBER (UI plan §12): every figure here is a field of lane F's
// check or state, drawn as sent.

(function () {
  "use strict";
  var A = window.Alchemy;
  if (!A) return;
  var esc = A.esc;
  var root = document.getElementById("alchemy-card-in");
  if (!root) return;

  root.innerHTML =
    '<section class="ac-take" id="alchemy-take" aria-label="What goes in"></section>' +
    '<section class="ac-formula" id="alchemy-formula" aria-label="The formula"></section>' +
    '<section class="ac-sums" id="alchemy-sums" aria-label="The check"></section>' +
    '<div class="bench-tag v2-page-paper ac-tag" id="alchemy-tag"><span class="tag-eyelet" aria-hidden="true"></span>' +
      '<div class="tag-body" id="alchemy-tag-body"></div>' +
      '<div class="tag-result" id="alchemy-tag-result" aria-live="polite"></div>' +
    '</div>';
  var takeEl = document.getElementById("alchemy-take");
  var formulaEl = document.getElementById("alchemy-formula");
  var sumsEl = document.getElementById("alchemy-sums");
  var tagBody = document.getElementById("alchemy-tag-body");
  var resultEl = document.getElementById("alchemy-tag-result");

  // Which shelf group an empty slot sends the keyboard to.
  var PICK = { vessel: "Vessels", solvent: "Solvents", catalysts: "Catalysts and apparatus" };
  var FAMILY = { potion: "potion", oil: "oil", splash: "splash flask", cloud: "cloud", tool: "tool",
                 intermediate: "salt or spirit" };
  function cap(t) { t = String(t || ""); return t.charAt(0).toUpperCase() + t.slice(1); }

  // --- a slot: filled with its ×, or empty and pressable ---------------------------------------
  function filled(label, it, what, key, extra) {
    var badges = (it.badges || []).slice();
    if (it.quality_name) badges.unshift(it.quality_name);
    return '<div class="ac-slot is-full">' +
      '<span class="ac-label">' + esc(label) + '</span>' +
      '<span class="ac-piece">' + A.iconHtml(A.rowIcon(it), { size: 26, tier: it.tier, label: it.name }) +
        (it.swatch ? '<i class="fr-swatch" style="--sw:' + esc(it.swatch) + '" aria-hidden="true"></i>' : "") +
        '<span class="ac-name">' + esc(it.name) + (badges.length ? '<small>' + esc(badges.join(", ")) + '</small>' : "") +
        (extra || "") + '</span></span>' +
      '<button type="button" class="ac-x" data-unput="' + esc(what) + '" data-key="' + esc(key || "") +
        '" aria-label="Take ' + esc(it.name) + ' off the bench">×</button></div>';
  }
  function empty(label, hint, opts) {
    opts = opts || {};
    return '<div class="ac-slot is-empty' + (opts.optional ? " is-optional" : "") + '">' +
      '<button type="button" class="ac-slot-b" data-pick="' + esc(opts.pick || "") + '"' +
      ' aria-label="' + esc(label + ", empty. " + hint) + '"><span class="ac-label">' + esc(label) + '</span>' +
      '<span class="ac-hint">' + esc(hint) + '</span></button></div>';
  }

  // --- what goes in -------------------------------------------------------------------------------
  function drawTake() {
    var o = A.order, m = o.method, c = A.check;
    if (!m || A.loading || A.error) { takeEl.innerHTML = ""; return; }
    var info = A.methodInfo(m) || {};
    var html = "";
    if (m === "assay") {
      var it = A.item(o.assay);
      html += it ? filled("Reagent", it, "assay", it.key, A.card && A.card.id === it.material ?
        '<small>' + esc(A.card.unknown ? A.card.unknown + " of its properties unknown" : "everything about it known") + '</small>' : "")
        : empty("Reagent", "Pick a raw material on the shelf: a pinch of it, a tenth of one", { pick: "inputs" });
      takeEl.innerHTML = html;
      return;
    }
    if (m === "identify") { takeEl.innerHTML = potions(); return; }
    if (m === "learn") { takeEl.innerHTML = writings(); return; }
    // Inputs, each with its ×.
    html += '<h3 class="ac-h">' + esc(cap(info.takes || "What goes in")) + '</h3>';
    if (o.inputs.length) {
      o.inputs.forEach(function (k) {
        var x = A.item(k);
        if (x) html += filled("Input", x, "inputs", k);
      });
    } else {
      html += empty("Input", "Pick from the shelf: " + (info.takes || "what this step takes"), { pick: "inputs" });
    }
    if (m === "dissolve") {
      var sv = A.item(o.solvent);
      html += sv ? filled("Solvent", sv, "solvent", sv.key)
                 : empty("Solvent", "Water, spirits, vinegar, oil or acid", { pick: "solvent" });
    }
    if (m === "bottle") {
      var v = A.item(o.vessel);
      var sl = c && c.slots;
      var line = v && sl && sl.family ? '<small>' + esc((FAMILY[sl.family] || sl.family) + ", " + sl.slots +
        (sl.slots === 1 ? " slot" : " slots") + (c.product && (c.product.how || []).length ? "; " + c.product.how.join(", ") : "")) + '</small>' : "";
      html += v ? filled("Vessel", v, "vessel", v.key, line)
                : empty("Vessel", "A vial, a flask, a bladder, a casing or a rod: it decides what this becomes", { pick: "vessel" });
    }
    if (m === "transmute") html += targets();
    // Catalysts: never spent, so they are always optional.
    o.catalysts.forEach(function (k) {
      var x = A.item(k);
      if (x) html += filled("Catalyst", x, "catalysts", k, '<small>never spent</small>');
    });
    if (!o.catalysts.length) {
      html += empty("Catalyst", "Optional: a catalyst or apparatus beside the work, never spent", { pick: "catalysts", optional: true });
    }
    if (info.bulk) {
      html += '<div class="ac-batch"><span class="ac-label" id="alchemy-batch-l">Batch</span>' +
        '<span class="tb-step v2-recess" role="group" aria-labelledby="alchemy-batch-l">' +
        '<button type="button" class="v2-btn is-small" id="alchemy-batch-less" aria-label="One fewer"' +
          (o.batch <= 1 ? " disabled" : "") + '>−</button>' +
        '<span class="ac-n" aria-live="polite">' + esc(o.batch) + '</span>' +
        '<button type="button" class="v2-btn is-small" id="alchemy-batch-more" aria-label="One more">+</button>' +
        '</span><span class="ac-hint">One roll for the whole batch.</span></div>';
    }
    takeEl.innerHTML = html;
  }

  function targets() {
    var c = A.check || {}, o = A.order;
    var list = c.candidates || [];
    if (!list.length) return "";
    return '<label class="ac-field" for="alchemy-target"><span>It becomes</span>' +
      '<select id="alchemy-target" class="v2-well ac-select"><option value="">Choose</option>' +
      list.map(function (t) {
        return '<option value="' + esc(t.id) + '"' + (o.target === t.id ? " selected" : "") + '>' +
          esc(t.name + " (" + t.tier + (t.shares && t.shares.length ? "; shares " + [].concat(t.shares).join(", ") : "") + ")") +
          '</option>';
      }).join("") + '</select></label>';
  }

  // Identify: the potions carried (the state's `potions`), each a choice.
  function potions() {
    var list = (A.state && A.state.potions) || [];
    if (!list.length) return '<p class="ac-quiet">You carry no potion to study. A potion or a scroll you carry appears here.</p>';
    var o = A.order;
    return '<label class="ac-field" for="alchemy-potion"><span>The potion</span>' +
      '<select id="alchemy-potion" class="v2-well ac-select"><option value="">Choose</option>' +
      list.map(function (p) {
        return '<option value="' + esc(p.key) + '"' + (o.item === p.key ? " selected" : "") + '>' +
          esc(p.name + (p.count > 1 ? " (" + p.count + ")" : "") + (p.known ? ", already known" : "")) + '</option>';
      }).join("") + '</select></label>';
  }

  // Learn: the writings carried (GET formulary), each with its route's check, DC, cost and
  // time in the server's numbers, and Learn. Lane U4's formulary is the fuller door.
  var book = null, bookErr = "";
  A.on("learn", function () {
    if (A.order.method !== "learn") return;
    book = null; bookErr = "";
    drawTake();
    A.api("/api/alchemy/formulary").then(function (d) { book = d; drawTake(); })
      .catch(function (err) { bookErr = err.message || String(err); drawTake(); });
  });
  function routeWords(p) {
    var parts = [];
    if (p.check) parts.push("DC " + p.dc);
    else parts.push("no roll");
    if (p.cost_gp) parts.push(p.cost_gp + " gp");
    if (p.minutes) parts.push(A.minutes(p.minutes));
    if (p.spends === "always") parts.push("spent whatever the roll");
    else if (p.spends === "on_success") parts.push("spent if it works");
    return parts.join(", ");
  }
  function writings() {
    if (bookErr) return '<p class="ac-quiet">' + esc(bookErr) + '</p>';
    if (!book) return '<p class="ac-quiet">Reading what you carry.</p>';
    // Writings first, then each teacher's lessons (by the lesson's own title, the server's
    // list), one list so one index finds the row.
    var list = (book.writings || []).slice();
    (book.teachers || []).forEach(function (t) {
      (t.teaches || []).forEach(function (l) {
        list.push({ route: "teacher", who: t.ref, name: t.name + (t.price ? ", " + t.price : ""),
                    fid: l.fid, formula: l.formula, plan: l.plan, item: "" });
      });
    });
    book.rows = list;
    var html = '<h3 class="ac-h">Writings you carry, and teachers here</h3>';
    if (!list.length) {
      html += '<p class="ac-quiet">Nothing you carry teaches a formula you do not know. A scroll, a potion or a ' +
        'formulary does.</p>';
    } else {
      html += '<ul class="ac-writings">' + list.map(function (w, i) {
        var p = w.plan || {};
        var refused = (p.refused || []).join(" ");
        // An unidentified potion's formula is not sent (it would be the secret): the row
        // says so in words.
        return '<li class="ac-writ"><span class="ac-name">' + esc(w.formula || "Its formula, unknown until you understand it") +
          '<small>' + esc((w.route === "potion" ? "take apart the " : w.route === "teacher" ? "taught by " : "from ") + w.name) + '</small>' +
          '<small>' + esc(refused || routeWords(p)) + '</small></span>' +
          '<button type="button" class="v2-btn is-small' + (refused ? "" : " is-go") + '" data-learn="' + i + '"' +
          (refused ? ' aria-disabled="true"' : "") + '>' + (w.route === "potion" ? "Take it apart" : "Learn") + '</button></li>';
      }).join("") + '</ul>';
    }
    if (window.AlchemyBooks && typeof AlchemyBooks.formulary === "function") {
      html += '<button type="button" class="v2-btn is-small is-quiet" data-alchemy-book="formulary">Open the formulary</button>';
    }
    return html;
  }

  // --- the formula, the count, the slots ------------------------------------------------------
  function drawFormula() {
    var c = A.check, o = A.order, m = o.method;
    if (!c || !m || !A.checked(m) || A.loading || A.error) { formulaEl.innerHTML = ""; return; }
    var html = "";
    if (m === "bottle") {
      var match = c.match || {};
      var known = c.formulae || [];
      html += '<label class="ac-field" for="alchemy-pick-formula"><span>Formula</span>' +
        '<select id="alchemy-pick-formula" class="v2-well ac-select"' + (o.vessel ? "" : " disabled") + '>' +
        '<option value="">Experiment</option>' +
        known.map(function (f) {
          return '<option value="' + esc(f.id) + '"' + (o.formula === f.id ? " selected" : "") + '>' + esc(f.name) + '</option>';
        }).join("") + '</select></label>';
      if (!o.vessel) html += '<p class="ac-quiet">Choose a vessel first: it decides which formulae fit.</p>';
      if (o.formula && match.name) html += '<p class="ac-match">' + esc(match.name) + (match.formula ? ": the mix meets it." : "") + '</p>';
      (match.missing || []).forEach(function (t) { html += '<p class="ac-miss">' + esc(cap(t)) + '.</p>'; });
      if (!o.formula && match.formula && !match.secret && match.name) {
        html += '<p class="ac-match">This mix makes ' + esc(match.name) + ', a formula you know.</p>';
      }
    }
    html += choices(c);
    // Could still become N (owner Q5.3). The server's line; never a name it did not send.
    if (c.could && c.could.line) html += '<p class="ac-could">' + esc(c.could.line) + '</p>';
    else if (c.could && c.could.count === 0) {
      html += '<p class="ac-could">This mix matches no formula. It will bottle as your own compound.</p>';
    }
    (c.notes || []).forEach(function (n) { html += '<p class="ac-quiet">' + esc(n) + '</p>'; });
    var sl = c.slots || {};
    var traits = sl.traits || [], bad = sl.drawbacks || [];
    if (traits.length || bad.length) {
      html += '<h3 class="ac-h">Traits' + (sl.slots ? ' <small>' + esc(sl.slots + (sl.slots === 1 ? " slot, " : " slots, ") +
        sl.free + " free") + '</small>' : "") + '</h3>';
      html += '<ul class="ac-traits">' + traits.map(function (t, i) {
        var id = "ac-t-" + i;
        var off = !!t.reason && !t.picked;
        return '<li class="ac-trait' + (off ? " is-off" : "") + '">' +
          '<input type="checkbox" id="' + id + '" data-trait="' + esc(t.key) + '"' + (t.picked ? " checked" : "") +
          (off ? ' aria-disabled="true" aria-describedby="' + id + '-why"' : "") + '>' +
          '<label for="' + id + '"><span class="ac-ess">' + esc(t.essence + " " + t.grade) + '</span>' +
          '<span>' + esc(t.text || t.key) + '</span>' +
          (t.reason ? '<small id="' + id + '-why">' + esc(t.reason) + '</small>' : "") + '</label></li>';
      }).join("") + '</ul>';
      if (bad.length) {
        html += '<h3 class="ac-h">Drawbacks</h3><ul class="ac-drawbacks">' + bad.map(function (t) {
          return '<li><span class="ac-ess">' + esc(t.essence + " " + t.grade) + '</span><span>' + esc(t.text || t.key) +
            '</span>' + (t.reason ? '<small>' + esc(t.reason) + '</small>' : "") + '</li>';
        }).join("") + '</ul>';
      }
    }
    formulaEl.innerHTML = html;
  }

  // --- what a vessel or a catalyst is told -------------------------------------------------------
  // The server's `check.choices` (alchemy_views._choices), each a picker over options it
  // sent and nothing else (the bench-shell lane, 2026-10-07: `as`, `aim` and `strip` were
  // taken by the server and offered nowhere):
  //   - what a vessel that bottles two families makes ("potion, drunk" or "oil, coated"),
  //     while no formula has decided it;
  //   - the formula orichalcum grains steer an experiment to: the whole table within
  //     reach, never the mix's candidates, which stay a count;
  //   - the drawback a unicorn horn shaving strips.
  function choices(c) {
    var ch = (c && c.choices) || {}, o = A.order, html = "";
    var fam = ch.families;
    if (fam && fam.open && (fam.options || []).length > 1) {
      html += '<label class="ac-field" for="alchemy-as"><span>It becomes</span>' +
        '<select id="alchemy-as" class="v2-well ac-select">' + fam.options.map(function (f) {
          var how = (f.how || []).length ? " (" + f.how.join(", ") + ")" : "";
          return '<option value="' + esc(f.id) + '"' + ((o.as || fam.chosen) === f.id ? " selected" : "") + '>' +
            esc(cap(f.name) + how) + '</option>';
        }).join("") + '</select></label>';
    } else if (fam && !fam.open && fam.chosen) {
      html += '<p class="ac-quiet">' + esc(cap(FAMILY[fam.chosen] || fam.chosen)) + ': the formula decides it.</p>';
    }
    var aim = ch.aim;
    if (aim && (aim.options || []).length) {
      html += '<label class="ac-field" for="alchemy-aim"><span>Name the formula</span>' +
        '<select id="alchemy-aim" class="v2-well ac-select"><option value="">Name none</option>' +
        aim.options.map(function (f) {
          return '<option value="' + esc(f.id) + '"' + (o.aim === f.id ? " selected" : "") + '>' + esc(f.name) + '</option>';
        }).join("") + '</select></label>' +
        '<p class="ac-quiet">' + esc(o.aim ? (aim.named ? "Your orichalcum steers it there: the mix meets it."
          : "The mix does not meet the formula you name, so the orichalcum finds nothing.")
          : "With orichalcum beside the work, an experiment that fits several formulae becomes the one you name, if the mix already meets it.") + '</p>';
    }
    var strip = ch.strip;
    if (strip && (strip.options || []).length) {
      html += '<label class="ac-field" for="alchemy-strip"><span>The catalyst strips</span>' +
        '<select id="alchemy-strip" class="v2-well ac-select">' + strip.options.map(function (r) {
          return '<option value="' + esc(r.key) + '"' + ((o.strip || strip.chosen) === r.key ? " selected" : "") + '>' +
            esc(r.text || r.key) + '</option>';
        }).join("") + '</select></label>';
    }
    return html;
  }

  // --- the DC, the stakes and the problems --------------------------------------------------------
  function drawSums() {
    var c = A.check, m = A.order.method;
    if (!c || !m || !A.checked(m) || A.loading || A.error) { sumsEl.innerHTML = ""; return; }
    var html = "";
    if (c.dc) {
      html += '<div class="ac-dc"><h3 class="ac-h">DC ' + esc(c.dc) + (c.need != null ? ', you need ' + esc(c.need) + ' or better' : "") +
        '</h3><ul class="ac-terms">' + (c.dc_terms || []).map(function (t, i) {
          return '<li><span>' + esc(cap(t.label)) + '</span><b>' + esc(i > 0 && t.value > 0 ? "+" + t.value : t.value) + '</b></li>';
        }).join("") + '</ul></div>';
    }
    var st = c.stakes || {};
    var stakes = [];
    if (st.mishap_line) stakes.push(st.mishap_line);
    (st.toxic || []).forEach(function (t) { stakes.push(t.text + "."); });
    if (stakes.length) {
      html += '<div class="ac-stakes"><h3 class="ac-h">The stakes</h3>' + stakes.map(function (s) {
        return '<p class="ac-warn">' + esc(s) + '</p>'; }).join("") + '</div>';
    }
    if ((c.problems || []).length) {
      html += '<ul class="ac-problems" aria-label="Before you can roll">' + c.problems.map(function (p) {
        return '<li>' + esc(p) + '</li>'; }).join("") + '</ul>';
    }
    sumsEl.innerHTML = html;
  }

  // --- the paper tag --------------------------------------------------------------------------------
  function ladder(rungs, ceiling, at, next) {
    var out = [];
    if (next) out.push('<li class="rung is-next"><span class="rung-name">' + esc(next) + '</span></li>');
    for (var i = rungs.length - 1; i >= 0; i--) {
      var r = rungs[i];
      var here = at != null && r.tier === at;
      var extra = [r.caster_level != null ? "CL " + r.caster_level : "",
                   r.price_gp != null ? r.price_gp + " gp" : ""].filter(Boolean).join(", ");
      out.push('<li class="rung t' + Math.min(4, r.tier) + (r.tier === ceiling ? " is-ceiling" : "") + (here ? " is-at" : "") + '"' +
        (here ? ' aria-current="true"' : "") + '><span class="rung-name">' + esc(r.name) + (extra ? '<small>' + esc(extra) + '</small>' : "") + '</span>' +
        (r.tier === ceiling ? '<span class="rung-ceil">your ceiling</span>' : "") + '</li>');
    }
    return '<ol class="tag-ladder" aria-label="Quality, from the ceiling down">' + out.join("") + '</ol>';
  }
  function drawTag() {
    var s = A.state, c = A.check, o = A.order, m = o.method;
    if (!s || !m) { tagBody.innerHTML = '<p class="tag-empty">Choose a method.</p>'; return; }
    var info = A.methodInfo(m) || {};
    var p = c && c.product;
    var secret = c && c.match && c.match.secret;
    var name = p && p.name ? p.name : secret ? "An experiment" :
      (m === "assay" && A.item(o.assay) ? A.item(o.assay).name : "") ||
      (m === "identify" && A.potion(o.item) ? A.potion(o.item).name : "");
    var html = '<h3 class="tag-name">' + esc(name || info.name || "") + '</h3>' +
      '<p class="tag-line">' + esc(info.name || "") + (info.makes ? ": " + esc(info.makes) : "") + '</p>';
    if (p && (p.lines || []).length) {
      html += '<ul class="ac-lines">' + p.lines.map(function (l) {
        return '<li' + (l.drawback ? ' class="is-bad"' : "") + '>' + esc(l.text || l.trait) + '</li>';
      }).join("") + '</ul>';
    }
    if (secret) html += '<p class="tag-empty">What it becomes is learned when it is made.</p>';
    if (!name && info.takes) html += '<p class="tag-empty">' + esc("Takes " + info.takes + ".") + '</p>';
    if (A.checked(m)) {
      var rungs = c && (c.tiers || []).length ? c.tiers :
        ((s.track && s.track.tiers) || []).map(function (n, i) { return { tier: i, name: n }; });
      var ceiling = c && c.ceiling != null ? Number(c.ceiling) : Number(s.ceiling) || 0;
      var r = A.result, at = r && r.finished && r.finish && r.finish.tier != null ? Number(r.finish.tier) : null;
      if (rungs.length) html += ladder(rungs, ceiling, at, s.track && s.track.next_rung);
    }
    tagBody.innerHTML = html;
  }

  // --- the result ------------------------------------------------------------------------------------
  function mastery(m) {
    var lines = m && m.lines;
    var out = "";
    if (lines && lines.length) {
      out += '<ul class="tr-mastery">' + lines.map(function (l) {
        return '<li><span>' + esc(l.why) + '</span><b>+' + esc(l.mp) + '</b></li>';
      }).join("") + '</ul>';
    }
    ((m && m.levelled) || []).forEach(function (lv) {
      out += '<p class="tr-level">You are now Alchemist ' + esc(typeof lv === "object" ? lv.level : lv) + '.</p>';
    });
    return out;
  }
  function tells(rows, cls) {
    return (rows || []).filter(function (x) { return x && x.tell; }).map(function (x) {
      return '<p class="' + cls + '">' + esc(cap(x.tell)) + '</p>';
    }).join("");
  }
  function paid(rent) {
    return (rent || []).map(function (x) { return '<p class="tr-note">Rent paid: ' + esc(x.words) + '.</p>'; }).join("");
  }
  function drawResult() {
    var r = A.result;
    if (!r) { resultEl.innerHTML = ""; return; }
    var parts = [];
    if (r.failed) {
      if (r.flare) parts.push('<p class="tr-loss tr-flare">Flare.</p>');
      parts.push('<p class="tr-loss">' + esc(r.said || "Failure.") + (r.minutes ? " " + esc(A.minutes(r.minutes)) + " passed." : "") + '</p>');
      parts.push(tells(r.toxic, "tr-loss"));
      parts.push(paid(r.rent));
      parts.push(mastery(r.mastery));
      resultEl.innerHTML = parts.join("");
      return;
    }
    if (r.assay) {
      var d = r.assay;
      parts.push('<p class="tr-made">' + (d.revealed && d.revealed.length ? "You learn: " +
        esc(d.revealed.map(function (x) { return x.text || x.key; }).join("; ")) + "." : "Nothing new in it.") + '</p>');
      if (d.pinch && d.pinch.tenths) {
        parts.push('<p class="tr-note">' + esc((d.pinch.tenths === 1 ? "A tenth" : d.pinch.tenths + " tenths") +
          " of the " + (d.pinch.name || d.name) + " used, and " + A.minutes(d.minutes) + ".") + '</p>');
      }
      (d.dangers || []).forEach(function (x) { parts.push('<p class="tr-loss">' + esc(cap(x.text)) + '.</p>'); });
      parts.push(tells(d.danger_applied, "tr-loss"));
      parts.push(paid(d.rent));
      parts.push(mastery(d.mastery));
      resultEl.innerHTML = parts.join("");
      return;
    }
    if (r.identify) {
      var i = r.identify;
      var what = i.success ? (i.spell ? (i.name || r.name) + ": it holds " + String(i.spell).replace(/-/g, " ") +
        (i.caster_level ? ", caster level " + i.caster_level : "") : (i.name || r.name)) + "." : "It gives up nothing.";
      parts.push('<p class="' + (i.success ? "tr-made" : "tr-note") + '">' + esc(what) + '</p>');
      parts.push('<p class="tr-note">' + esc("d20 " + i.face + " " + A.sign(i.bonus) + ", DC " + i.dc + ".") + '</p>');
      resultEl.innerHTML = parts.join("");
      return;
    }
    if (r.learn) {
      var l = r.learn;
      parts.push('<p class="' + ((l.result || {}).learned ? "tr-made" : "tr-note") + '">' + esc(l.said || "") + '</p>');
      if (l.paid) parts.push('<p class="tr-note">Paid ' + esc(l.paid) + '.</p>');
      parts.push(mastery(l.mastery));
      resultEl.innerHTML = parts.join("");
      return;
    }
    if (r.collected) {
      parts.push('<p class="tr-made">' + esc(r.collected.said || "Collected.") + '</p>');
      resultEl.innerHTML = parts.join("");
      return;
    }
    var f = r.finish || {};
    var made = (f.products || [])[0];
    if (made) {
      parts.push('<p class="tr-made">Made: ' + esc((f.products || []).map(function (x) {
        return x.count + " " + x.name; }).join(", ")) + '.</p>');
    }
    if (f.tier_name) parts.push('<p class="tr-note">Quality: ' + esc(f.tier_name) + '.</p>');
    if (f.found) parts.push('<p class="tr-new">Found by experiment: ' + esc(f.found.name) + '. It is written in your formulary.</p>');
    if (r.stopped) parts.push('<p class="tr-note">Stopped early. You kept what you had.</p>');
    if (r.flat) parts.push('<p class="tr-note">No game for this step in this build: the work was scored at the middle of your range.</p>');
    parts.push(tells(r.toxic, "tr-loss"));
    parts.push(paid(r.rent));
    parts.push(mastery(f.mastery));
    var paidWhy = ((f.mastery || {}).lines || []).map(function (x) { return String(x.why || ""); }).join("\n");
    (f.discoveries || []).forEach(function (d) {
      if (!d.text || paidWhy.indexOf("learned: " + d.name) >= 0) return;
      parts.push('<p class="tr-new">New: ' + esc(d.name) + ', ' + esc(d.text) + '.</p>');
    });
    if (made && Number(made.waits) > 0) {
      // Its countdown is the server's In progress row ("ready in 2 hours"), on game time.
      var key = String(made.key).replace(/^stock:/, "");
      var w = ((A.state && A.state.works) || []).filter(function (x) { return x.key === key; })[0];
      parts.push('<p class="tr-note">' + esc(made.name) + ' sets In progress' + (w && w.ready_words ? ": " + esc(w.ready_words) : "") + '.</p>');
      if (w && w.state !== "ready") {
        parts.push('<button type="button" class="v2-btn is-small is-go" id="alchemy-wait" data-wait="' + esc(key) + '">Wait for it</button>');
      }
    }
    var rec = made && made.record;
    if (rec && rec.family === "intermediate") {
      var next = A.methodInfo("bottle");
      if (next && !next.locked) {
        parts.push('<button type="button" class="v2-btn is-go is-small" id="alchemy-next" data-next="bottle" data-carry="' +
          esc(made.key) + '">Next: Bottle</button>');
      }
    }
    resultEl.innerHTML = parts.join("");
  }

  // Every check redraws the column, and the check after a finish lands a beat after the
  // result: the focused control is found again by its id after every redraw, so "Next:
  // Bottle" keeps the keyboard (the circle's measured defect, 2026-10-06).
  function drawAll() {
    var at = document.activeElement;
    var id = at && root.contains(at) && at.id ? at.id : null;
    drawTake(); drawFormula(); drawSums(); drawTag(); drawResult();
    if (id && document.activeElement !== at) {
      var again = document.getElementById(id);
      if (again && !again.disabled) again.focus();
    }
  }
  ["loading", "error", "state", "check", "order", "method", "result", "rolling", "card"].forEach(function (ev) { A.on(ev, drawAll); });

  // --- the column's own controls ------------------------------------------------------------------
  root.addEventListener("click", function (e) {
    var n = e.target.closest("[data-next]");
    if (n) {
      var going = A.setMethod(n.dataset.next, { carry: n.dataset.carry });
      if (going) going.then(function () {
        A.refocus(["#alchemy-take .ac-slot-b[data-pick='vessel']", "#alchemy-list .as-add:not([aria-disabled='true'])", "alchemy-roll"]);
      });
      return;
    }
    var w = e.target.closest("[data-wait]");
    if (w) { A.waitFor(w.dataset.wait); return; }
    var lb = e.target.closest("[data-learn]");
    if (lb) {
      if (lb.getAttribute("aria-disabled") === "true") return;
      var writ = book && (book.rows || [])[Number(lb.dataset.learn)];
      if (writ) A.learn(writ);
      return;
    }
    var bk = e.target.closest("[data-alchemy-book]");
    if (bk) { A.book(bk.dataset.alchemyBook, bk); return; }
    var x = e.target.closest("[data-unput]");
    if (x && root.contains(x)) {
      e.stopPropagation();
      A.remove(x.dataset.unput, x.dataset.key);
      A.refocus(["#alchemy-take .ac-slot-b", "alchemy-roll"]);
      return;
    }
    if (e.target.id === "alchemy-batch-more") { A.set("batch", A.order.batch + 1); return; }
    if (e.target.id === "alchemy-batch-less") { A.set("batch", A.order.batch - 1); return; }
    var b = e.target.closest(".ac-slot-b");
    if (b) {
      // An empty slot pressed: the keyboard moves to the shelf's first row of the kind it
      // takes that fits, so Enter there fills it.
      var group = PICK[b.dataset.pick] || "";
      var row = document.querySelector("#alchemy-list .as" + (group ? '[data-group="' + group + '"]' : "") +
                                       ":not(.is-dim) .as-add[data-add]") ||
                document.querySelector("#alchemy-list .as:not(.is-dim) .as-add[data-add]");
      if (row) { row.focus(); A.say("Pick what goes here on the shelf."); }
      else A.say("Nothing on your shelf goes here.");
    }
  });
  root.addEventListener("change", function (e) {
    var t = e.target;
    if (t.id === "alchemy-pick-formula") { A.set("formula", t.value); return; }
    if (t.id === "alchemy-target") { A.set("target", t.value); return; }
    if (t.id === "alchemy-potion") { A.set("item", t.value); return; }
    if (t.id === "alchemy-as") { A.set("as", t.value); return; }
    if (t.id === "alchemy-aim") { A.set("aim", t.value); return; }
    if (t.id === "alchemy-strip") { A.set("strip", t.value); return; }
    if (t.matches && t.matches("input[data-trait]")) {
      if (t.getAttribute("aria-disabled") === "true") {
        // Refused here: the reason is beside it in words; the box goes back.
        t.checked = !t.checked;
        A.say(t.parentNode.querySelector("small") ? t.parentNode.querySelector("small").textContent : "");
        return;
      }
      A.set("pick", { key: t.dataset.trait, on: t.checked });
    }
  });
})();
