// The play table, part 54 (the alchemist's books: the reagent card, the Formulary, the codex,
// and Identify on a potion in the pack). Classic script in one IIFE, reached through
// `window.AlchemyBooks` (alchemy contracts §12, lane U4).
//
// Alchemy UI plan §6.7 and §6.8, the enchanter's ledger's counterpart (49-enchant-ledger.js),
// with one renderer per thing and every surface drawing it:
//
//   AlchemyBooks.card(materialId, anchorEl, opts)   the reagent card beside the bench's shelf:
//       swatch, name, where it is found or bought, each KNOWN property with how it was learned
//       ("assayed, day 14", "taught by Mirela, day 20") in two groups, in the bottle and at
//       the bench, one "unknown" line for each still unknown, and two acts: Assay (a pinch,
//       ten minutes) and Ask an alchemist (one button per alchemist standing here).
//   AlchemyBooks.formulary(host, opts)   the formula book: known formulae by family, each with
//       what it needs in essences and how it was learned; the writings carried (a scroll, a
//       formulary) with Learn from a writing; a potion in hand with Identify and Take it apart.
//   AlchemyBooks.codex(host, opts)   the reagents met, "3 of 7 known", Unknowns first; the
//       Journal's "Alchemist's codex" section (21-tab-journal.js) is this.
//
// ONLY WHAT THE PLAYER KNOWS. The card is `GET api/alchemy/material/<id>` (play/alchemy_views.py),
// lane A's `knowledge.properties`: a known row says what it does and how it was learned, an
// unknown row says nothing at all, not even its list. The route does send an unknown row's
// list (`group`: "toxic", "mishap"), and it is deliberately NOT drawn: "toxic" beside an
// unknown line would teach the danger before any assay. An unknown is placed only by the
// server's `where` ("in the bottle", "at the bench"), which every reagent has both of. A
// drawback is marked harmful only once known, and the danger line is the server's
// `danger_known`, read from known drawbacks alone.
//
// THE DANGEROUS ASSAY (UI plan §6.8). Assay asks first, in --alarm words, when the reagent is
// KNOWN to be volatile or toxic to handle: its mishap or toxic row is known, or the bench's
// shelf (which names those two hazards whether or not the rest is known, plan §8.1, because the
// stakes are stated before every roll) passes them in `opts.hazards`. Keyed on anything the
// page was not told, the confirm itself would be the leak (the enchanter's card found that
// with `volatile`, 2026-10-04).
//
// NEVER AN UNKNOWN FORMULA'S NAME (owner Q5.3). The Formulary lists known formulae. A
// writing's formula is named only where the writing names it itself: a scroll carries its
// spell's name, a formulary is read cover to cover. A potion is listed by its own name and
// never by the formula it would teach: the route's `formula` field is not drawn.
//
// EVERY NUMBER IS THE SERVER'S (UI plan §12). DCs, rolls, totals, counts ("3 of 7 known"),
// costs, minutes and spell and caster levels are printed from responses; nothing is summed
// or compared here. A verdict word is a mapping of the server's own `success`.
//
// Styles are injected once (`#alchemy-books-style`), theme tokens only; the herb card's
// classes in bench.css give the leather, rim and type. MOTION: nothing loops (no setInterval,
// no requestAnimationFrame; tests/test_alchemy_books_ui.py greps for both).

(function () {
  "use strict";

  var core = function () { return window.BenchCore || null; };
  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  function csrf() {
    var m = (document.cookie || "").match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }
  // The core's API when it is loaded; the same few lines otherwise, so the Journal and the
  // Equipment tab work on a page with no bench open.
  function api(path, body) {
    var C = core();
    if (C && typeof C.api === "function") return C.api(path, body);
    var opts = body === undefined ? { cache: "no-store" } : {
      method: "POST", body: JSON.stringify(body),
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
    };
    return fetch(path, opts).then(function (r) {
      return r.text().then(function (raw) {
        var data = null;
        try { data = JSON.parse(raw); } catch (err) { data = null; }
        if (!r.ok || !data) {
          var e = new Error((data && data.error) || ("The server failed (HTTP " + r.status + ")."));
          e.status = r.status;
          throw e;
        }
        return data;
      });
    });
  }
  function sound(name) {
    var C = core();
    if (C && typeof C.sound === "function") { C.sound(name); return; }
    try { if (window.Sound && typeof Sound.play === "function") Sound.play(name); } catch (err) { /* */ }
  }
  function minutesWords(m) {
    var C = core();
    if (C && typeof C.minutes === "function") return C.minutes(m);
    // BenchCore.minutes' own words, for a page with no bench: "4 hours", "1 hour 30 minutes".
    m = Math.max(0, Math.round(Number(m) || 0));
    var d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), n = m % 60, parts = [];
    if (d) parts.push(d + (d === 1 ? " day" : " days"));
    if (h) parts.push(h + (h === 1 ? " hour" : " hours"));
    if (!d && n) parts.push(n + (n === 1 ? " minute" : " minutes"));
    return parts.length ? parts.join(" ") : "no time";
  }
  function sign(v) { v = Number(v) || 0; return (v >= 0 ? "+" : "") + v; }
  function cap(s) { s = String(s == null ? "" : s); return s.charAt(0).toUpperCase() + s.slice(1); }
  function emit(name, detail) {
    try { document.dispatchEvent(new CustomEvent(name, { detail: detail })); } catch (err) { /* old engines */ }
  }
  function words(id) { return String(id == null ? "" : id).replace(/[-_]+/g, " "); }

  // --- words ------------------------------------------------------------------------------
  var OBTAIN = { bought: "Bought at a market", mined: "Mined", harvested: "Harvested",
                 gathered: "Gathered", found: "Found", distilled: "Distilled",
                 refined: "Refined at the bench", looted: "Taken as loot", made: "Made at the bench" };
  function listWords(xs) {
    xs = (xs || []).filter(Boolean).map(String);
    if (xs.length < 2) return xs.join("");
    return xs.slice(0, -1).join(", ") + " or " + xs[xs.length - 1];
  }
  // Where it is found or bought, from the server's fields.
  function foundLine(c) {
    var how = String(c.obtain || "").toLowerCase();
    if (!how) return "";
    var head = OBTAIN[how] || cap(how);
    var biomes = (c.biomes || []).length && how !== "bought" ? " in " + listWords(c.biomes) + " country" : "";
    return head + biomes + ".";
  }
  // A reagent's colour is the server's, sent as [r, g, b] in 0..1 (the material document,
  // plan §5.2) or as a CSS colour. Only a plain colour reaches the style attribute: a value
  // with a semicolon would let a document restyle the card.
  function cssColour(color) {
    if (Array.isArray(color) && color.length >= 3 && color.slice(0, 3).every(function (v) {
      return typeof v === "number" && isFinite(v) && v >= 0 && v <= 1;
    })) {
      return "rgb(" + color.slice(0, 3).map(function (v) { return Math.round(v * 255); }).join(", ") + ")";
    }
    if (typeof color === "string" && /^(#[0-9a-f]{3,8}|rgba?\([\d\s.,%]+\)|hsla?\([\d\s.,%deg]+\))$/i.test(color.trim())) {
      return color.trim();
    }
    return "";
  }
  function swatch(color, big) {
    var css = cssColour(color);
    return css ? '<span class="ab-swatch' + (big ? " is-big" : "") + '" style="background:' + esc(css) + '" aria-hidden="true"></span>' : "";
  }
  function icon(name, opts) {
    if (!window.BenchIcons || typeof BenchIcons.html !== "function") return "";
    try { return BenchIcons.html(name, opts); } catch (err) { return ""; }
  }

  // --- the card's body: one renderer for the card, the codex and the Journal --------------
  function inBottle(p) {
    return p.where ? p.where === "in the bottle" : String(p.key || "").charAt(0) === "p";
  }
  function propRow(p) {
    if (!p.known) {
      return '<li class="is-unknown"><span class="hc-rule" aria-hidden="true"></span><span>unknown</span></li>';
    }
    var chips = (p.essence ? '<span class="ab-ess">' + esc(words(p.essence)) + '</span>' : "") +
      (p.drawback ? '<span class="ab-harm">harmful</span>' : "");
    return '<li><span>' + esc(cap(p.text || "")) + chips + '</span>' +
      (p.how ? '<span class="hc-how">' + esc(p.how) + '</span>' : "") + '</li>';
  }
  function propsHtml(c) {
    var props = c.properties || [];
    if (!props.length) return '<p class="hc-sub">There is nothing to learn about it.</p>';
    var groups = [["In the bottle", props.filter(inBottle)],
                  ["At the bench", props.filter(function (p) { return !inBottle(p); })]];
    return groups.filter(function (g) { return g[1].length; }).map(function (g) {
      return '<h4 class="ab-group">' + g[0] + '</h4><ul class="hc-props">' + g[1].map(propRow).join("") + '</ul>';
    }).join("");
  }
  function dangerHtml(c) {
    return c.danger_known ? '<p class="ab-danger">You know this can hurt you: ' + esc(c.danger_known) + '.</p>' : "";
  }
  function transmutesHtml(c) {
    var t = c.transmutes || [];
    if (!t.length) return "";
    return '<p class="ab-trans"><span class="hc-k">Transmutes into</span> ' + esc(t.map(function (x) {
      return x.name + " (" + [x.tier, (x.shares || []).map(words).join(", ")].filter(Boolean).join(", ") + ")";
    }).join("; ")) + '</p>';
  }
  function assayCost(c) {
    var a = c.assay || {};
    var bits = [a.cost || "a pinch"];
    if (a.minutes != null) bits.push(minutesWords(a.minutes));
    return bits.join(", ");
  }
  function actionsHtml(c, o) {
    var none = !(Number(c.carried) > 0);
    var busy = o.busy ? " disabled" : "";
    var asks = (c.teachers || []).map(function (t) {
      return '<button type="button" class="v2-btn is-small" data-ab="ask" data-ab-ref="' + esc(t.ref) + '"' + busy +
        ' aria-label="Ask ' + esc(t.name) + ' about ' + esc(c.name) + '">Ask ' + esc(t.name) +
        (t.price ? '<span class="hc-cost">' + esc(t.price) + '</span>' : "") + '</button>';
    }).join("");
    return '<div class="hc-acts"><button type="button" class="v2-btn is-small" data-ab="assay"' +
      (none || o.busy ? " disabled" : "") + (none ? ' aria-describedby="ab-assay-why"' : "") +
      '>Assay<span class="hc-cost">' + esc(assayCost(c)) + '</span></button>' + asks + '</div>' +
      (none ? '<p class="ab-why" id="ab-assay-why">You carry none of it to take a pinch from.</p>' : "");
  }
  function cardHtml(c, o) {
    o = o || {};
    var carried = Number(c.carried) > 0 ? c.carried + " carried" : "";
    var sub = [c.tier, c.kind, carried, c.hybrid ? "also a herb" : ""].filter(Boolean).join(", ");
    var where = foundLine(c);
    return '<i class="v2-rim" aria-hidden="true"></i><div class="hc-in">' +
      '<div class="hc-head"><span class="ab-mark">' + icon("reagent", { size: 48, tier: c.tier, label: c.name }) +
        swatch(c.color, true) + '</span>' +
        '<div><h3 id="ab-card-name">' + esc(c.name) + '</h3>' +
        (sub ? '<p class="hc-sub">' + esc(sub) + '</p>' : "") +
        (where ? '<p class="hc-sub">' + esc(where) + '</p>' : "") + '</div>' +
        (o.pinned ? '<button type="button" class="hc-x" data-ab="close" aria-label="Close the card">×</button>' : "") +
      '</div>' + dangerHtml(c) + propsHtml(c) + transmutesHtml(c) +
      (o.msg ? '<p class="hc-msg" role="status">' + esc(o.msg) + '</p>' : "") +
      (o.actions ? actionsHtml(c, o) : "") + '</div>';
  }

  // --- hazards and the dangerous-assay confirm ----------------------------------------------
  // What the player KNOWS can bite at the bench: the server's `hazards` when a route sends
  // them, the shelf's badge words passed in, and the mishap and toxic rows once known.
  function hazardsOf(c, o) {
    var out = { volatile: false, toxic: false };
    [].concat(c.hazards || [], (o && o.hazards) || []).forEach(function (h) {
      var w = String(h || "").toLowerCase().replace(/_/g, " ");
      if (w === "volatile") out.volatile = true;
      if (w === "toxic to handle" || w === "toxic") out.toxic = true;
    });
    (c.properties || []).forEach(function (p) {
      if (!p.known) return;
      if (p.group === "mishap") out.volatile = true;
      if (p.group === "toxic") out.toxic = true;
    });
    return out;
  }
  // `protectedBy` is the bench's `where.protected` ("the laboratory's fume hood", "your mask
  // and gloves", or ""); null when the caller did not say, so nothing is claimed about it.
  function needsConfirm(c, o) {
    var hz = hazardsOf(c, o);
    var prot = o && o.where ? String(o.where.protected || "") : null;
    return hz.volatile || (hz.toxic && !prot);
  }
  function confirmHtml(c, o) {
    var hz = hazardsOf(c, o);
    var prot = o && o.where ? String(o.where.protected || "") : null;
    var lines = [];
    if (hz.toxic) {
      lines.push(prot ? cap(c.name) + " is toxic to handle; " + prot + " keep it off you."
        : prot === "" ? cap(c.name) + " is toxic to handle, and you wear no mask."
        : cap(c.name) + " is toxic to handle.");
    }
    if (hz.volatile) lines.push(cap(c.name) + " is volatile: a failure by 5 or more flares in your hands.");
    return '<div class="bench-scrim"></div><div class="bench-dialog v2-framed v2-card-leather">' +
      '<i class="v2-rim" aria-hidden="true"></i>' +
      '<h3 id="ab-confirm-t">Assay ' + esc(c.name) + '</h3>' +
      '<div id="ab-confirm-b"><p class="ab-alarm">' + esc(lines.join(" ")) + ' Assay it anyway?</p>' +
      '<p>' + esc("It takes " + assayCost(c) + ".") + '</p></div>' +
      '<div class="bench-dialog-acts"><button type="button" class="v2-btn is-quiet" data-no>Keep it</button>' +
      '<button type="button" class="v2-btn is-quiet bench-danger" data-yes>Assay it</button></div></div>';
  }

  // --- the Formulary -------------------------------------------------------------------------
  var FAMILY = [["potion", "Potions"], ["oil", "Oils"], ["splash", "Splash flasks"],
                ["cloud", "Clouds and powders"], ["tool", "Tools"], ["intermediate", "Salts and spirits"]];
  function familyName(id) {
    for (var i = 0; i < FAMILY.length; i++) if (FAMILY[i][0] === id) return FAMILY[i][1];
    return id ? cap(words(id)) : "Other work";
  }
  // A book source is printed as the book cites itself ("CRB, Goods and Services"); what
  // follows it, after a semicolon, a colon or in brackets (the page it was checked against,
  // the book's own line quoted for the reviewer), is not for the reader. Measured live: the
  // antitoxin's source carried its whole rules line after a colon.
  function sourceWords(s) {
    return String(s || "").split(/\s*[;:(]/)[0].trim();
  }
  function formulaHtml(f) {
    var facts = [];
    if (f.spell_level != null) facts.push("spell level " + f.spell_level);
    if (f.caster_level != null) facts.push("caster level " + f.caster_level);
    if (f.price_gp != null) facts.push(f.price_gp + " gp");
    var needs = f.requires_words || (f.requires || []).map(function (r) {
      return words(r.essence) + (Number(r.grade) > 1 ? " " + r.grade : "");
    }).join(", ");
    var to = f.delivers && (f.delivers[f.family] || "");
    var src = f.book && f.kind === "classic" ? sourceWords(f.source) : "";
    var why = (f.reach || []).concat(f.brewable === false
      ? ["It waits on the rules for " + listWords((f.waiting || []).map(words)) + "."] : []);
    return '<li class="ab-formula" data-ab-formula="' + esc(f.id) + '">' +
      '<b>' + esc(f.name) + '</b>' +
      (facts.length ? '<p class="hc-sub">' + esc(facts.join(", ")) + '</p>' : "") +
      (needs ? '<p class="ab-needs"><span class="hc-k">Needs</span> ' + esc(needs) + '</p>' : "") +
      (to ? '<p class="ab-needs"><span class="hc-k">Works on</span> ' + esc(to) + '</p>' : "") +
      (f.how ? '<p class="hc-how">' + esc(cap(f.how)) + '</p>' : "") +
      (src ? '<p class="hc-how">' + esc(src) + '</p>' : "") +
      why.map(function (w) { return '<p class="ab-why">' + esc(w) + '</p>'; }).join("") + '</li>';
  }
  function knownHtml(list) {
    if (list === null) return '<p class="why">Reading your formulary.</p>';
    if (!list.length) return '<p class="why">No formulae yet. Experiment at the bench, or learn one from a writing.</p>';
    var order = FAMILY.map(function (f) { return f[0]; });
    var fams = [];
    list.forEach(function (f) { if (fams.indexOf(f.family) < 0) fams.push(f.family); });
    fams.sort(function (a, b) {
      var i = order.indexOf(a), j = order.indexOf(b);
      return (i < 0 ? 99 : i) - (j < 0 ? 99 : j) || String(a).localeCompare(String(b));
    });
    return fams.map(function (fam) {
      var rows = list.filter(function (f) { return f.family === fam; })
        .sort(function (a, b) { return String(a.name).localeCompare(String(b.name)); });
      return '<h4 class="ab-group">' + esc(familyName(fam)) + '</h4><ul class="plain ab-formulae">' +
        rows.map(formulaHtml).join("") + '</ul>';
    }).join("");
  }
  // What a writing's route asks, in words, from lane E's `learn_route` as the server sent it.
  function planWords(w) {
    var p = w.plan || {};
    var bits = [];
    bits.push(p.check ? "An Alchemist check against DC " + p.dc : "No check");
    if (p.cost_gp) bits.push(p.cost_gp + " gp in inks and paper");
    if (p.minutes) bits.push(minutesWords(p.minutes));
    var spends = p.spends === "always" ? "The potion is spent whatever the roll."
      : p.spends === "on_success" ? "The " + (w.route === "scroll" ? "scroll" : "writing") + " is used up if you succeed; a failure keeps it, and you may try again in a week."
      : "The writing is kept.";
    return bits.join(", ") + ". " + spends;
  }
  function writingHtml(w, st) {
    var refused = (w.plan && w.plan.refused) || [];
    var busy = st.busy ? " disabled" : "";
    var dis = refused.length || st.busy ? " disabled" : "";
    var whyId = "ab-wr-why-" + esc(String(w.item) + "-" + w.fid).replace(/[^a-z0-9_-]/gi, "-");
    var potion = w.route === "potion";
    // A potion is named by itself; what it would teach is learned by taking it apart.
    var teaches = potion ? "" : '<p class="ab-needs"><span class="hc-k">Writes down</span> ' + esc(w.formula || "") + '</p>';
    var said = st.said && st.said[w.item + "|" + w.fid];
    var acts = potion
      ? '<button type="button" class="v2-btn is-small" data-ab-identify="' + esc(w.item) + '" data-ab-name="' + esc(w.name) + '"' + busy +
          ' aria-label="Identify ' + esc(w.name) + '">Identify</button>' +
        '<button type="button" class="v2-btn is-small bench-danger" data-ab-learn="' + esc(w.item) + '" data-ab-fid="' + esc(w.fid) + '"' + dis +
          (refused.length ? ' aria-describedby="' + whyId + '"' : "") + '>Take it apart</button>'
      : '<button type="button" class="v2-btn is-small" data-ab-learn="' + esc(w.item) + '" data-ab-fid="' + esc(w.fid) + '"' + dis +
          (refused.length ? ' aria-describedby="' + whyId + '"' : "") + '>Learn from a writing</button>';
    return '<li class="ab-writing"><b>' + esc(w.name) + '</b>' + teaches +
      '<p class="hc-how">' + esc(planWords(w)) + '</p>' +
      (refused.length ? '<p class="ab-why" id="' + whyId + '">' + esc(refused.join(" ")) + '</p>' : "") +
      '<div class="hc-acts">' + acts + '</div>' +
      (said ? '<p class="hc-msg" role="status">' + esc(said) + '</p>' : "") + '</li>';
  }
  function writingsHtml(list, st) {
    if (list === null) return "";
    if (!list.length) {
      return '<p class="why">No writings carried. A scroll, a formulary or a potion in your pack can teach a formula.</p>';
    }
    return '<ul class="plain ab-writings">' + list.map(function (w) { return writingHtml(w, st); }).join("") + '</ul>';
  }
  function formularyHtml(st) {
    if (st.error) {
      return '<p class="why">' + esc(st.error) + '</p><button type="button" class="v2-btn is-small" data-ab-retry>Retry</button>';
    }
    var d = st.data;
    return (st.msg ? '<p class="hc-msg" role="status">' + esc(st.msg) + '</p>' : "") +
      (d && d.spell_level_cap != null ? '<p class="hc-sub">You bottle spells up to level ' + esc(d.spell_level_cap) + '.</p>' : "") +
      '<div class="ab-known">' + knownHtml(d ? d.formulae || [] : null) + '</div>' +
      (d ? '<h3 class="ab-sub">Learn from a writing</h3>' + writingsHtml(d.writings || [], st) : "");
  }

  // The answers, each in one sentence from the server's own numbers.
  function rollWords(face, bonus, total, dc) {
    if (face == null) return "";
    return "d20 " + face + " " + sign(bonus) + " = " + total + (dc != null ? " against DC " + dc : "");
  }
  // The learn route sends the face and the total but not the bonus between them, and the
  // page does not make one by subtracting: the line says "d20 20, total 22".
  function learnLine(r) {
    var res = r.result || {};
    var roll = r.face != null ? " (d20 " + r.face + ", total " + r.total +
      (res.dc != null ? " against DC " + res.dc : "") + ")" : "";
    var head = (res.learned ? "You learn the formula for " + r.name : "You cannot make out the formula") + roll + ".";
    var from = r.route && r.route.source;
    var spent = res.spent ? " The " + (from === "potion" || from === "scroll" ? from : "writing") + " is spent." : "";
    var paid = r.paid ? " Paid " + r.paid + "." : "";
    var time = r.minutes ? " " + cap(minutesWords(r.minutes)) + " passed." : "";
    var refused = (res.refused || []).length ? " " + res.refused.join(" ") : "";
    return head + spent + paid + time + refused;
  }
  function identifyLine(r, name) {
    var who = name || "potion";
    var head = "Identify the " + who + ": " + rollWords(r.face, r.bonus, r.total, r.dc) + ". ";
    if (!r.success) {
      return head + "It gives up nothing." + (r.repeat ? " You have identified one of this brewing before." : "");
    }
    var facts = [];
    if (r.spell) facts.push("it holds " + words(r.spell));
    if (r.spell_level != null) facts.push("spell level " + r.spell_level);
    if (r.caster_level != null) facts.push("caster level " + r.caster_level);
    return head + (facts.length ? cap(facts.join(", ")) + "." : "It is " + (r.name || "what it seems") + ".");
  }
  function assayLine(r) {
    var roll = r.roll || {};
    var head = "You assay a pinch of " + (r.name || "it") +
      (roll.total != null ? " (" + rollWords(roll.face, roll.bonus, roll.total, roll.dc) + ")." : ".");
    var found = (r.revealed || []).map(function (t) { return t.text || t.key; });
    var said = found.length ? " Learned: " + found.join("; ") + "." : " Nothing new.";
    var hurt = (r.danger_applied || []).map(function (d) { return d.tell; }).filter(Boolean);
    var paid = (r.rent || []).map(function (p) { return p.words; }).filter(Boolean);
    return head + said + (hurt.length ? " " + hurt.join(" ") : "") +
      (paid.length ? " Paid " + paid.join(", ") + " for the laboratory." : "") +
      (r.minutes ? " " + cap(minutesWords(r.minutes)) + " passed." : "");
  }
  function askLine(r, who) {
    if (r.refused) return r.refused;
    var found = (r.revealed || []).map(function (t) { return t.text || t.key; });
    return (who ? who + " tells you: " : "Learned: ") + found.join("; ") + "." +
      (r.paid ? " Paid " + r.paid + "." : "");
  }

  // --- the codex ---------------------------------------------------------------------------
  function codexRowsHtml(st) {
    if (st.error) {
      return '<p class="why">' + esc(st.error) + '</p>' +
        '<button type="button" class="v2-btn is-small" data-ab-cx-retry>Retry</button>';
    }
    if (st.codex === null) return '<p class="why">Reading the codex.</p>';
    var rows = st.codex.slice();
    if (!rows.length) return '<p class="why">No reagents yet. Buy, find or gather one and it appears here.</p>';
    if (st.unknownFirst) {
      rows.sort(function (a, b) {
        return ((b.total - b.known) - (a.total - a.known)) || String(a.name).localeCompare(String(b.name));
      });
    }
    return '<ul class="plain matters twocol ab-rows">' + rows.map(function (e) {
      var isOpen = st.open === e.id;
      var bodyId = "ab-cx-card-" + esc(e.id);
      // "3 of 7 known" is the server's two numbers, side by side; nothing is counted here.
      var line = [e.tier, e.kind, e.known + " of " + e.total + " known",
                  Number(e.carried) > 0 ? e.carried + " carried" : "", e.hybrid ? "also a herb" : ""]
        .filter(Boolean).join(" · ");
      var card = st.cards[e.id];
      var body = !isOpen ? "" : !card ? '<p class="why">Reading what you know.</p>'
        : card.error ? '<p class="why">' + esc(card.error) + '</p>'
        : dangerHtml(card) + propsHtml(card) + transmutesHtml(card);
      return '<li class="matter" role="listitem"><h3><button type="button" class="ab-row" data-ab-cx="' + esc(e.id) + '"' +
        ' aria-expanded="' + isOpen + '" aria-controls="' + bodyId + '">' + esc(e.name) + '</button></h3>' +
        '<p class="why">' + esc(line) + '</p>' +
        (e.danger_known ? '<p class="ab-danger is-small">' + esc(cap(e.danger_known)) + '.</p>' : "") +
        '<div id="' + bodyId + '" class="ab-cx-body"' + (isOpen ? "" : " hidden") + '>' + body + '</div></li>';
    }).join("") + '</ul>';
  }

  // --- styles, once -------------------------------------------------------------------------
  function style() {
    if (document.getElementById("alchemy-books-style")) return;
    var s = document.createElement("style");
    s.id = "alchemy-books-style";
    s.textContent = [
      ".ab-card, .ab-confirm, .ab-codex, .ab-formulary, .ab-item { --bench-ink: var(--ink); --bench-quiet: var(--dim);",
      "  --bench-accent: var(--gold); --bench-warn: var(--alarm); --bench-radius: 3px; }",
      ".ab-card { position: fixed; width: 340px; max-height: calc(100vh - 16px); overflow-y: auto; z-index: 7; color: var(--ink);",
      "  font: 16px/1.5 var(--body); border-radius: 3px; box-shadow: var(--sh-3), var(--ring-cast); }",
      ".ab-card.is-loose { z-index: 30; }",
      ".ab-card[hidden] { display: none; }",
      ".ab-card .hc-x { position: absolute; right: 8px; top: 8px; width: 30px; height: 30px; display: grid; place-items: center;",
      "  background: none; border: 0; color: var(--dim); font-size: 20px; cursor: pointer; }",
      ".ab-card .hc-x:hover { color: var(--ink); }",
      ".ab-card .hc-acts { display: flex; flex-wrap: wrap; gap: 8px; }",
      ".ab-card .hc-acts .v2-btn { flex-direction: column; align-items: flex-start; gap: 3px; min-height: 40px; height: auto; display: inline-flex; }",
      ".ab-mark { position: relative; display: inline-flex; flex: none; }",
      ".ab-mark:empty { display: none; }",
      ".ab-swatch { display: inline-block; width: 8px; height: 8px; border-radius: 50%; vertical-align: middle;",
      "  box-shadow: 0 0 0 1px var(--edge), 1px 1px 2px rgba(0, 0, 0, .6); }",
      ".ab-mark .ab-swatch { position: absolute; right: -2px; bottom: -2px; }",
      ".ab-swatch.is-big { width: 12px; height: 12px; }",
      ".ab-group { margin: 12px 0 4px; color: var(--gold); font: 400 15px/1.2 var(--display); letter-spacing: .05em; font-variant: small-caps; }",
      ".ab-card .hc-props, .ab-cx-body .hc-props { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }",
      ".ab-card .hc-props li, .ab-cx-body .hc-props li { display: grid; gap: 1px; }",
      ".ab-cx-body .hc-how, .ab-cx-body .is-unknown { color: var(--dim); font-size: 13px; }",
      ".ab-cx-body .is-unknown { grid-template-columns: 22px 1fr; align-items: center; gap: 8px; }",
      ".ab-cx-body .hc-rule { display: block; height: 1px; background: var(--dim); }",
      ".ab-ess { margin-left: 8px; color: var(--gold); font: 400 13px/1 var(--display); letter-spacing: .08em; font-variant: small-caps; }",
      ".ab-harm { margin-left: 8px; color: var(--alarm); font: 600 12px/1 var(--display); letter-spacing: .1em; font-variant: small-caps; }",
      ".ab-danger { margin: 4px 0 8px; color: var(--alarm); font-size: 15px; }",
      ".ab-danger.is-small { margin: 2px 0 0; font-size: 14px; }",
      ".ab-trans { margin: 10px 0 0; font-size: 14px; }",
      ".ab-why { margin: 6px 0 0; color: var(--dim); font-size: 13px; }",
      ".ab-alarm { color: var(--alarm); font: 600 19px/1.35 var(--body); }",
      ".ab-confirm.is-loose { z-index: 31; }",
      ".ab-confirm .bench-danger { border-color: var(--alarm); }",
      ".ab-formulary .bench-danger { border-color: var(--alarm); }",
      ".ab-codex .ab-rows { grid-template-columns: repeat(2, minmax(0, 1fr)); }",
      "@media (max-width: 900px) { .ab-codex .ab-rows { grid-template-columns: minmax(0, 1fr); } }",
      ".ab-codex .ab-tools { margin: 0 0 8px; }",
      ".ab-row { all: unset; cursor: pointer; display: inline-flex; gap: 10px; align-items: center; }",
      ".ab-row:focus-visible { outline: 2px solid var(--gold); outline-offset: 3px; }",
      ".ab-formulary h3.ab-sub { margin: 18px 0 8px; color: var(--gold); font: 400 17px/1.2 var(--display); letter-spacing: .04em; font-variant: small-caps; }",
      ".ab-formulae, .ab-writings { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }",
      ".ab-formulae { grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); }",
      ".ab-formula b, .ab-writing b { font-weight: 400; color: var(--ink); }",
      ".ab-formula p, .ab-writing p { margin: 2px 0 0; }",
      ".ab-formulary .hc-how { color: var(--dim); font-size: 13px; }",
      ".ab-formulary .hc-sub { color: var(--dim); font-size: 14px; margin: 2px 0 0; }",
      ".ab-needs { font-size: 14px; color: var(--ink); }",
      ".ab-formulary .hc-k, .ab-card .hc-k, .ab-cx-body .hc-k { color: var(--dim); margin-right: 4px; }",
      ".ab-writing .hc-acts { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }",
      ".ab-formulary .hc-msg { margin: 0 0 10px; }",
      ".ab-item { margin: 6px 0 2px; padding: 6px 0 0 10px; border-left: 2px solid var(--gold); font-size: 14px; line-height: 1.4; color: var(--ink); }",
      ".ab-item p { margin: 2px 0; }",
      ".ab-item .ab-q { color: var(--dim); }",
    ].join("\n");
    document.head.appendChild(s);
  }

  // --- the dice -----------------------------------------------------------------------------
  // The table's d20 for the player's own throw, as the enchanter's Read; the server rolls when
  // there is no mat (face null).
  function throwFor(title, why, ask) {
    var dice = window.Dice3D;
    var shown = { title: title, why: why, sides: 20, lo: 1, hi: 20, die: "1d20", terms: [] };
    var asking = dice && typeof dice.ask === "function" ? dice.ask(Object.assign({ hold: true }, shown)) : Promise.resolve(null);
    var C = core();
    if (dice && C && C.focusMat) C.focusMat();
    return asking.then(function (face) {
      return ask(face == null ? null : face);
    }).then(function (r) {
      return { r: r, dice: dice, shown: shown };
    }, function (err) {
      if (dice && dice.close) { try { dice.close(); } catch (e2) { /* */ } }
      throw err;
    });
  }
  function landIt(t, face, bonus, dc, success) {
    var dice = t.dice;
    if (!dice || typeof dice.land !== "function" || face == null) {
      if (dice && dice.close) { try { dice.close(); } catch (e2) { /* */ } }
      return Promise.resolve(null);
    }
    var terms = [];
    if (bonus != null) terms.push({ label: "your bonus", value: sign(bonus) });
    if (dc != null) terms.push({ label: "beat", value: dc });
    var closing = dice.land(Object.assign({}, t.shown, { result: face, terms: terms }));
    var rest = typeof dice.settled === "function" ? dice.settled() : null;
    if (typeof success === "boolean" && typeof window.showVerdict === "function") {
      window.showVerdict({ verdict: success ? "success" : "failure", natural: null }, rest);
    }
    return closing;
  }

  // A confirm of the bench's own when the card is on a bench (its Esc stack and trap), or a
  // loose one over the page.
  function confirmBox(html, h, host, labelId, bodyId) {
    return new Promise(function (done) {
      var back = document.activeElement;
      var wrap = document.createElement("div");
      wrap.className = "bench-modal bench-confirm ab-confirm" + (host === document.body ? " is-loose" : "");
      wrap.setAttribute("role", "alertdialog");
      wrap.setAttribute("aria-modal", "true");
      wrap.setAttribute("aria-labelledby", labelId);
      wrap.setAttribute("aria-describedby", bodyId);
      wrap.innerHTML = html;
      host.appendChild(wrap);
      var onKey = null;
      var finish = function (v) {
        if (h) h.dropEsc(onEsc);
        if (onKey) document.removeEventListener("keydown", onKey, true);
        wrap.remove();
        if (back && document.contains(back) && back.focus) back.focus();
        done(v);
      };
      var onEsc = function () { finish(false); };
      if (h) h.pushEsc(onEsc);
      else {
        onKey = function (e) { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); finish(false); } };
        document.addEventListener("keydown", onKey, true);
      }
      wrap.querySelector("[data-no]").addEventListener("click", function () { finish(false); });
      wrap.querySelector("[data-yes]").addEventListener("click", function () { finish(true); });
      wrap.querySelector(".bench-scrim").addEventListener("click", function () { finish(false); });
      wrap.querySelector("[data-no]").focus();
    });
  }
  function benchOf(anchor) {
    var C = core();
    var h = C && C.current;
    return h && h.open && h.layer && anchor && h.layer.contains(anchor) ? h : null;
  }
  function hostFor(anchor, o) {
    if (o && o.pops) return o.pops;
    var h = benchOf(anchor);
    if (h) {
      var pops = h.options && h.options.pops && document.getElementById(h.options.pops);
      return pops || h.layer;
    }
    return document.body;
  }

  // --- the reagent card beside the shelf ----------------------------------------------------
  var el = null, cache = {}, open = null, closeT = 0, msg = "", busy = false, looseEsc = null;

  function ensure(host) {
    style();
    if (!el) {
      el = document.createElement("div");
      el.className = "bench-card ab-card v2-framed v2-card-leather";
      el.id = "alchemy-books-card";
      el.setAttribute("role", "dialog");
      el.setAttribute("aria-labelledby", "ab-card-name");
      el.hidden = true;
      el.addEventListener("click", onClick);
      el.addEventListener("mouseenter", function () { clearTimeout(closeT); });
      el.addEventListener("mouseleave", function () {
        if (open && !open.pinned) closeT = setTimeout(function () { if (open && !open.pinned) hide(false); }, 220);
      });
    }
    if (el.parentNode !== host) host.appendChild(el);
    el.classList.toggle("is-loose", host === document.body);
  }
  function place(anchor, o) {
    if (!el) return;
    var shelfEl = (o && o.beside) || (anchor && anchor.closest && anchor.closest("[data-alchemy-shelf]")) ||
                  document.getElementById("alchemy-shelf");
    var sr = shelfEl && document.contains(shelfEl) ? shelfEl.getBoundingClientRect() : null;
    var ar = anchor && document.contains(anchor) ? anchor.getBoundingClientRect() : sr;
    // 16px gutters at phone width (the UI standing rule); measured live at 375px, the
    // enchanter's 8px clamp put this card 12px from the left edge.
    var w = Math.min(340, innerWidth - 32);
    el.style.width = w + "px";
    var h = el.offsetHeight || 260;
    var left, top;
    if (sr && sr.right + 14 + w <= innerWidth - 16) {
      left = sr.right + 14;
      top = ar ? ar.top - 12 : sr.top;
    } else {
      left = Math.max(16, Math.min(innerWidth - w - 16, (ar ? ar.left : 16) + 12));
      top = ar ? ar.bottom + 6 : 80;
    }
    top = Math.max(8, Math.min(innerHeight - h - 8, top));
    el.style.left = Math.round(left) + "px";
    el.style.top = Math.round(top) + "px";
  }
  function draw() {
    if (!open || !el) return;
    var c = cache[open.id];
    if (!c) {
      el.innerHTML = '<i class="v2-rim" aria-hidden="true"></i><div class="hc-in"><div class="hc-head">' +
        '<div><h3 id="ab-card-name">' + esc(open.name || "") + '</h3></div></div><p class="hc-sub">Reading what you know.</p></div>';
      return;
    }
    if (c.error) {
      el.innerHTML = '<i class="v2-rim" aria-hidden="true"></i><div class="hc-in"><h3 id="ab-card-name">Couldn\'t load this reagent.</h3>' +
        '<p class="hc-sub">' + esc(c.error) + '</p><button type="button" class="v2-btn is-small" data-ab="retry">Retry</button></div>';
      return;
    }
    el.innerHTML = cardHtml(c, { actions: true, pinned: open.pinned, msg: msg, busy: busy });
  }
  function fetchCard(id) {
    return api("/api/alchemy/material/" + encodeURIComponent(id)).then(function (c) {
      cache[id] = c;
      return c;
    }).catch(function (err) {
      cache[id] = { error: err.message || String(err), transient: true };
      return cache[id];
    }).then(function (c) {
      if (open && open.id === id) { draw(); place(open.anchor, open.opts); focusIn(); }
      if (c && c.transient) delete cache[id];
      return c;
    });
  }
  function focusIn() {
    if (!open || !open.wantFocus || !el) return;
    var first = el.querySelector("[data-ab]:not([data-ab='close']):not([disabled])") || el.querySelector("[data-ab]");
    if (first) { open.wantFocus = false; first.focus(); }
  }
  function pushEsc() {
    var h = benchOf(open && open.anchor);
    if (h) { h.pushEsc(escClose); return; }
    if (looseEsc) return;
    // Capture phase, stopped there: one Esc closes the card, not the Journal under it too
    // (the forge ledger's live finding, 2026-10-04).
    looseEsc = function (e) {
      if (e.key !== "Escape" || !open || !open.pinned || document.querySelector(".ab-confirm")) return;
      e.preventDefault();
      e.stopPropagation();
      escClose();
    };
    document.addEventListener("keydown", looseEsc, true);
  }
  function dropEsc() {
    var C = core();
    if (C && C.current && C.current.dropEsc) C.current.dropEsc(escClose);
    if (looseEsc) { document.removeEventListener("keydown", looseEsc, true); looseEsc = null; }
  }
  function show(id, anchor, o) {
    o = o || {};
    if (!id) return;
    clearTimeout(closeT);
    var same = open && open.id === id;
    if (same && open.pinned && o.peek) return;
    var wasPinned = !!(open && open.pinned);
    var pinned = !o.peek || (same && open.pinned);
    if (open && !same && wasPinned) dropEsc();
    open = { id: id, anchor: anchor, pinned: pinned, opts: o, name: o.name || "", wantFocus: false };
    if (pinned && !wasPinned) sound("ui.open");
    if (!same) msg = "";
    ensure(hostFor(anchor, o));
    el.hidden = false;
    el.classList.toggle("is-pinned", pinned);
    draw();
    place(anchor, o);
    if (!cache[id]) fetchCard(id);
    if (pinned) {
      if (!wasPinned || !same) pushEsc();
      open.wantFocus = true;
      focusIn();
    }
  }
  function hide(back) {
    clearTimeout(closeT);
    var was = open;
    dropEsc();
    open = null;
    if (el) el.hidden = true;
    if (was && was.pinned) sound("ui.close");
    if (back && was && was.anchor && document.contains(was.anchor) && was.anchor.focus) was.anchor.focus();
  }
  function escClose() { hide(true); }

  function after(detail) {
    if (open && open.opts && typeof open.opts.after === "function") {
      try { open.opts.after(detail); } catch (err) { /* the card still redraws */ }
    }
  }
  function assay(c) {
    var id = c.id;
    busy = true;
    draw();
    var t = null;
    return throwFor("Assay " + c.name, "Alchemist", function (face) {
      return api("/api/alchemy/assay", { material: id, face: face });
    }).then(function (got) {
      t = got;
      sound("alchemy.assay");
      var roll = t.r.roll || {};
      if (t.r.flare) sound("alchemy.flare");
      return landIt(t, roll.face, roll.bonus, roll.dc, typeof roll.success === "boolean" ? roll.success : null);
    }).then(function () {
      var r = t.r;
      delete cache[id];
      msg = assayLine(r);
      busy = false;
      var detail = { material: id, response: r, said: msg };
      emit("alchemy:assayed", detail);
      after(detail);
      if (open && open.id === id) { open.wantFocus = true; draw(); return fetchCard(id); }
    }).catch(function (err) {
      busy = false;
      msg = err && err.message ? err.message : String(err);
      if (open && open.id === id) { draw(); open.wantFocus = true; focusIn(); }
    });
  }
  function ask(c, ref) {
    var id = c.id;
    var who = ((c.teachers || []).filter(function (t) { return t.ref === ref; })[0] || {}).name || "";
    busy = true;
    draw();
    return api("/api/alchemy/ask", { material: id, ref: ref }).then(function (r) {
      delete cache[id];
      msg = askLine(r, who);
      busy = false;
      var detail = { material: id, response: r, said: msg };
      emit("alchemy:asked", detail);
      after(detail);
      if (open && open.id === id) { open.wantFocus = true; draw(); return fetchCard(id); }
    }).catch(function (err) {
      busy = false;
      msg = err && err.message ? err.message : String(err);
      if (open && open.id === id) { draw(); open.wantFocus = true; focusIn(); }
    });
  }
  function onClick(e) {
    var b = e.target.closest("[data-ab]");
    if (!b || !open) return;
    var id = open.id, c = cache[id];
    var k = b.dataset.ab;
    if (k === "close") { hide(true); return; }
    if (k === "retry") { fetchCard(id); return; }
    if (!c || busy || b.disabled) return;
    if (!open.pinned) { open.pinned = true; el.classList.add("is-pinned"); pushEsc(); }
    if (k === "ask") { ask(c, b.dataset.abRef); return; }
    if (k === "assay") {
      if (!needsConfirm(c, open.opts)) { assay(c); return; }
      confirmBox(confirmHtml(c, open.opts), benchOf(open.anchor), hostFor(open.anchor, open.opts),
                 "ab-confirm-t", "ab-confirm-b")
        .then(function (yes) { if (yes && open && open.id === id) assay(c); });
    }
  }
  document.addEventListener("pointerdown", function (e) {
    if (!open || !open.pinned || !el || el.contains(e.target)) return;
    if (e.target.closest && (e.target.closest(".ab-confirm") || e.target.closest("#d3d-mat") ||
        (open.anchor && open.anchor.contains && open.anchor.contains(e.target)))) return;
    hide(false);
  });
  addEventListener("resize", function () { if (open) place(open.anchor, open.opts); });

  // --- Identify and Learn: one door each, for the Formulary and the Equipment tab -----------
  // Each returns the response with `said`, the sentence the caller writes where it keeps one.
  function identify(key, o) {
    o = o || {};
    var name = o.name || "potion";
    var t = null;
    return throwFor("Identify " + name, "Alchemist", function (face) {
      return api("/api/alchemy/identify", { item: key, face: face });
    }).then(function (got) {
      t = got;
      sound("alchemy.assay");
      return landIt(t, t.r.face, t.r.bonus, t.r.dc, typeof t.r.success === "boolean" ? t.r.success : null);
    }).then(function () {
      var r = t.r;
      r.said = identifyLine(r, name);
      emit("alchemy:identified", { item: key, response: r, said: r.said });
      return r;
    });
  }
  function learn(w, o) {
    o = o || {};
    var body = { from: w.route, item: w.item, fid: w.fid };
    var check = !!(w.plan && w.plan.check);
    var call = function (face) {
      if (face != null) body.face = face;
      return api("/api/alchemy/learn", body);
    };
    var go = check
      ? throwFor(w.route === "potion" ? "Take apart " + w.name : "Copy from " + w.name, "Alchemist", call)
        .then(function (t) {
          var r = t.r, res = r.result || {};
          return landIt(t, r.face, r.bonus != null ? r.bonus : null, res.dc,
                        typeof res.success === "boolean" ? res.success : null)
            .then(function () { return r; });
        })
      : call(null);
    return go.then(function (r) {
      r.said = learnLine(r);
      sound(r.result && r.result.learned ? "alchemy.chime" : "alchemy.fail");
      emit("alchemy:learned", { fid: r.fid, from: w.route, response: r, said: r.said });
      return r;
    });
  }

  // --- the Formulary in a host ---------------------------------------------------------------
  function formulary(host, o) {
    if (!host) return null;
    o = o || {};
    style();
    host.classList.add("ab-formulary");
    var st = host._alchemyFormulary;
    if (!st) {
      st = host._alchemyFormulary = { data: null, error: "", msg: "", busy: false, said: {} };
      var find = function (btn) {
        var d = st.data || {};
        return (d.writings || []).filter(function (w) {
          return w.item === btn.dataset.abLearn && w.fid === btn.dataset.abFid;
        })[0];
      };
      host.addEventListener("click", function (e) {
        if (e.target.closest("[data-ab-retry]")) { st.read(); return; }
        var idb = e.target.closest("[data-ab-identify]");
        if (idb && !idb.disabled && !st.busy) {
          var key = idb.dataset.abIdentify, nm = idb.dataset.abName || "";
          st.busy = true;
          st.draw();
          identify(key, { name: nm }).then(function (r) {
            (st.data.writings || []).forEach(function (w) { if (w.item === key) st.said[w.item + "|" + w.fid] = r.said; });
          }).catch(function (err) {
            st.msg = err.message || String(err);
          }).then(function () {
            st.busy = false;
            st.draw();
            var again = host.querySelector('[data-ab-identify="' + (window.CSS && CSS.escape ? CSS.escape(key) : key) + '"]');
            if (again) again.focus();
          });
          return;
        }
        var lb = e.target.closest("[data-ab-learn]");
        if (!lb || lb.disabled || st.busy) return;
        var w = find(lb);
        if (!w) return;
        var ready = w.route === "potion"
          ? confirmBox('<div class="bench-scrim"></div><div class="bench-dialog v2-framed v2-card-leather">' +
              '<i class="v2-rim" aria-hidden="true"></i><h3 id="ab-apart-t">Take apart ' + esc(w.name) + '</h3>' +
              '<div id="ab-apart-b"><p class="ab-alarm">The potion is spent. Take it apart?</p>' +
              '<p>' + esc(planWords(w)) + '</p></div>' +
              '<div class="bench-dialog-acts"><button type="button" class="v2-btn is-quiet" data-no>Keep it</button>' +
              '<button type="button" class="v2-btn is-quiet bench-danger" data-yes>Take it apart</button></div></div>',
              benchOf(host), hostFor(host, o), "ab-apart-t", "ab-apart-b")
          : Promise.resolve(true);
        ready.then(function (yes) {
          if (!yes) return;
          st.busy = true;
          st.draw();
          return learn(w, o).then(function (r) {
            st.msg = r.said;
            if (typeof o.after === "function") { try { o.after({ fid: r.fid, response: r, said: r.said }); } catch (err) { /* */ } }
          }).catch(function (err) {
            st.msg = err.message || String(err);
          }).then(function () {
            st.busy = false;
            return st.read(true);
          });
        });
      });
    }
    st.draw = function () { host.innerHTML = formularyHtml(st); };
    // `keep` holds the last answer line across the re-read that follows an act.
    st.read = function (keep) {
      st.error = "";
      if (!keep) st.msg = "";
      st.draw();
      return api("/api/alchemy/formulary").then(function (d) {
        st.data = d || {};
      }).catch(function (err) {
        st.error = "Couldn't read your formulary. " + (err.message || "");
      }).then(function () {
        st.draw();
        var m = host.querySelector(".hc-msg");
        if (keep && m && m.focus) { m.setAttribute("tabindex", "-1"); m.focus(); }
      });
    };
    st.read();
    return { refresh: function () { return st.read(); } };
  }

  // --- the codex in a host (the Journal's section, and the bench's) --------------------------
  function codex(host, o) {
    if (!host) return null;
    o = o || {};
    style();
    host.classList.add("ab-codex");
    var st = host._alchemyCodex;
    if (!st) {
      st = host._alchemyCodex = { codex: null, error: "", open: "", unknownFirst: false, cards: {} };
      host.addEventListener("click", function (e) {
        if (e.target.closest("[data-ab-cx-retry]")) { st.read(); return; }
        var sort = e.target.closest("[data-ab-cx-sort]");
        if (sort) {
          st.unknownFirst = !st.unknownFirst;
          sort.setAttribute("aria-pressed", String(st.unknownFirst));
          st.draw();
          return;
        }
        var row = e.target.closest("[data-ab-cx]");
        if (!row) return;
        var id = row.dataset.abCx;
        st.open = st.open === id ? "" : id;
        st.draw();
        var again = host.querySelector('[data-ab-cx="' + (window.CSS && CSS.escape ? CSS.escape(id) : id) + '"]');
        if (again) again.focus();
        if (st.open && !st.cards[id]) {
          api("/api/alchemy/material/" + encodeURIComponent(id)).then(function (c) { st.cards[id] = c; })
            .catch(function (err) { st.cards[id] = { error: err.message || String(err) }; })
            .then(function () {
              if (st.open === id) {
                st.draw();
                var b = host.querySelector('[data-ab-cx="' + (window.CSS && CSS.escape ? CSS.escape(id) : id) + '"]');
                if (b) b.focus();
              }
              if (st.cards[id] && st.cards[id].error) delete st.cards[id];
            });
        }
      });
    }
    host.innerHTML = '<div class="ab-tools"><button type="button" class="v2-btn is-small" data-ab-cx-sort aria-pressed="' +
      st.unknownFirst + '">Unknowns first</button></div>' +
      '<div class="ab-list" role="list" aria-label="Reagents you have met"></div>';
    st.draw = function () {
      var box = host.querySelector(".ab-list");
      if (box) box.innerHTML = codexRowsHtml(st);
    };
    st.read = function () {
      st.error = "";
      st.codex = null;
      st.cards = {};
      st.draw();
      return api("/api/alchemy/codex").then(function (d) {
        st.codex = (d && d.codex) || [];
      }).catch(function (err) {
        st.error = "Couldn't read the codex. " + (err.message || "");
      }).then(st.draw);
    };
    st.read();
    return { refresh: st.read };
  }

  // --- a potion's section on the Equipment tab (the item card, UI plan §6.6's pattern) -----
  // 05-sheet.js draws the page and 18-tab-equipment.js adds the enchanter's magic section after
  // each draw (an observer on #sheetbody's children). A potion that holds a spell is not one
  // of the enchanter's vessels, so it has no section there; this adds the potion's own, in the
  // same place and the same way, with Identify among the row's acts: DC 15 + spell level
  // (plan §11.3, owner confirmed), the alchemist's check, a round. Which rows are potions is
  // the server's word (the Formulary's `writings`, route "potion"), never guessed from a name.
  var POTIONS = null;       // "stock:<id>" -> writing, or null while unread
  var POTION_SEEN = "";     // the row ids the last read was for
  var POTION_SAY = {};      // "stock:<id>" -> the last Identify answer
  var POTION_BUSY = "";
  function potionSection(key, w) {
    var said = POTION_SAY[key];
    return '<div class="ab-item" data-ab-item="' + esc(key) + '"><p><b>Potion</b>, it holds a spell.' +
      (said ? "" : ' <span class="ab-q">Identify it to learn which, and how strong.</span>') + '</p>' +
      (said ? '<p class="ab-msg" role="status">' + esc(said) + '</p>' : "") + '</div>';
  }
  function equipmentRows() {
    return Array.prototype.slice.call(document.querySelectorAll("#sheetbody .eqrow[data-eqid]"));
  }
  function onEquipment() {
    return typeof SHEET_TAB !== "undefined" && SHEET_TAB === "equipment";
  }
  function potionDraw() {
    if (!onEquipment() || !POTIONS) return;
    style();
    equipmentRows().forEach(function (row) {
      var key = row.dataset.eqid, w = POTIONS[key];
      if (!w || row.querySelector(".ab-item")) return;
      var nameEl = row.querySelector(".eqname");
      if (nameEl) nameEl.insertAdjacentHTML("beforeend", potionSection(key, w));
      var acts = row.querySelector(".eqacts");
      if (acts && !acts.querySelector("[data-ab-identify]")) {
        acts.insertAdjacentHTML("beforeend", '<button type="button" class="v2-btn is-small" data-ab-identify="' + esc(key) +
          '" data-ab-name="' + esc(w.name) + '"' + (POTION_BUSY ? " disabled" : "") +
          ' aria-label="Identify ' + esc(w.name) + '">Identify</button>');
      }
    });
  }
  function potionRead() {
    return api("/api/alchemy/formulary").then(function (d) {
      var map = {};
      ((d && d.writings) || []).forEach(function (w) { if (w.route === "potion") map[w.item] = w; });
      POTIONS = map;
    }).catch(function () { POTIONS = POTIONS || {}; }).then(potionDraw);
  }
  function potionWatch() {
    if (!onEquipment()) return;
    var ids = equipmentRows().map(function (r) { return r.dataset.eqid; }).join("|");
    if (!ids) return;
    // Read again only when what is carried has changed (a potion drunk, bought, taken apart);
    // a redraw of the same rows reuses the answer.
    if (ids !== POTION_SEEN || POTIONS === null) { POTION_SEEN = ids; potionRead(); return; }
    potionDraw();
  }
  (function watchTheEquipment() {
    var body = document.getElementById("sheetbody");
    if (!body || typeof MutationObserver !== "function") return;
    new MutationObserver(potionWatch).observe(body, { childList: true });
  })();
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("#sheetbody [data-ab-identify]");
    if (!b || b.disabled || POTION_BUSY) return;
    var key = b.dataset.abIdentify, name = b.dataset.abName || "";
    POTION_BUSY = key;
    b.disabled = true;
    identify(key, { name: name }).then(function (r) {
      POTION_SAY[key] = r.said;
    }).catch(function (err) {
      POTION_SAY[key] = err.message || String(err);
    }).then(function () {
      POTION_BUSY = "";
      var row = b.closest(".eqrow");
      var sec = row && row.querySelector(".ab-item");
      if (sec && POTIONS && POTIONS[key]) sec.outerHTML = potionSection(key, POTIONS[key]);
      if (document.contains(b)) { b.disabled = false; b.focus(); }
    });
  });

  window.AlchemyBooks = {
    card: function (materialId, anchorEl, opts) { show(materialId, anchorEl, opts); },
    peek: function (materialId, anchorEl, opts) { show(materialId, anchorEl, Object.assign({}, opts, { peek: true })); },
    unpeek: function () {
      if (!open || open.pinned) return;
      clearTimeout(closeT);
      closeT = setTimeout(function () { if (open && !open.pinned) hide(false); }, 220);
    },
    close: function () { hide(false); },
    isOpen: function () { return !!open; },
    // After a step at the bench reveals properties (working a reagent teaches its working
    // traits), the card must be read again.
    forget: function (materialId) { if (materialId) delete cache[materialId]; else cache = {}; },
    formulary: formulary,
    codex: codex,
    identify: identify,
    learn: learn,
    // The renderers, for tests and for the bench's shell; pure: data in, markup out.
    render: { card: cardHtml, props: propsHtml, codexRows: codexRowsHtml, formulary: formularyHtml,
              known: knownHtml, writing: writingHtml, planWords: planWords, potion: potionSection,
              assayLine: assayLine, learnLine: learnLine, identifyLine: identifyLine, askLine: askLine,
              confirm: confirmHtml, needsConfirm: needsConfirm, hazards: hazardsOf, found: foundLine,
              colour: cssColour },
  };
})();
