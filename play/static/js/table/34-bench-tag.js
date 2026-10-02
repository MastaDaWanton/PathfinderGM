// The play table, part 34 (the herbalism bench: the result tag). Classic script in one
// IIFE, reached through `window.Bench` (30-bench-shell.js).
//
// UI plan §6.5. A paper tag pinned at the top of the right column with a brass eyelet:
// the one piece of paper on the bench, and it holds what the pot makes. Every number on
// it is the server's (contracts §3.2 `product`, §3.4): the page shows the effect at each
// rung as the server wrote it in `by_tier` and never computes one.
//
// The ladder runs from Crude up to YOUR ceiling, the ceiling marked by a hairline and the
// words "your ceiling", with one greyed rung above it (`track.next_rung`) so the next goal
// is in sight. Quality is shown by metal and weight, never by hue (UI plan §3): five hues
// would be five accents on a page that has one.

(function () {
  "use strict";
  var B = window.Bench;
  if (!B) return;
  var esc = B.esc;
  var root = document.getElementById("bench-tagcol-in");
  if (!root) return;

  // While a game runs, the ladder's pointer follows the live score; the tier the product
  // GETS is the server's (contracts §3.4) and replaces this the moment the finish answers.
  // The preview spreads the bands evenly under the ceiling, as revamp plan §4.3 describes
  // the server doing; it is a picture of progress, never posted and never trusted.
  var preview = null;

  root.innerHTML =
    '<div class="bench-tag v2-page-paper" id="bench-tag"><span class="tag-eyelet" aria-hidden="true"></span>' +
      '<div class="tag-body" id="bench-tag-body"></div>' +
      '<div class="tag-result" id="bench-tag-result" aria-live="polite"></div>' +
    '</div>' +
    '<div class="tag-batch" id="bench-batch-row"></div>';
  var body = document.getElementById("bench-tag-body");
  var result = document.getElementById("bench-tag-result");
  var batchRow = document.getElementById("bench-batch-row");

  // "Heals 1d4" and "Heals 1d4+1" share their first word; the rung reads "at Fine 1d4+1"
  // rather than "at Fine Heals 1d4+1". Presentation only: both strings are the server's.
  function after(base, t) {
    base = String(base || ""); t = String(t || "");
    // "Knits a sprain" and "Knits a sprain, for 30 minutes": the rung adds a clause, so
    // the clause is what is shown ("at Superior for 30 minutes").
    if (base && t.indexOf(base) === 0 && t.length > base.length) return t.slice(base.length).replace(/^[,;:]\s*/, "");
    var a = base.split(" "), b = t.split(" ");
    var i = 0;
    while (i < a.length - 1 && i < b.length - 1 && a[i] === b[i]) i++;
    return b.slice(i).join(" ");
  }

  function keeps(m) {
    if (m == null) return "";
    return "keeps " + B.span(m);
  }

  function tierClass(i) { return "t" + Math.min(4, Math.max(0, i)); }

  function ladder(track, at) {
    var c = track ? Number(track.ceiling) || 0 : 0;
    var rungs = [];
    if (track && track.next_rung) {
      rungs.push('<li class="rung is-next"><span class="rung-name">' + esc(track.next_rung) + '</span></li>');
    }
    for (var i = c; i >= 0; i--) {
      var here = at != null && i === at;
      rungs.push('<li class="rung ' + tierClass(i) + (i === c ? " is-ceiling" : "") + (here ? " is-at" : "") + '"' +
        (here ? ' aria-current="true"' : "") + '><span class="rung-name">' + esc(B.tierName(i)) + '</span>' +
        (i === c ? '<span class="rung-ceil">your ceiling</span>' : "") + '</li>');
    }
    return '<ol class="tag-ladder" aria-label="Quality, from your ceiling down">' + rungs.join("") + '</ol>';
  }

  function lines(list, at, ceil, kind) {
    return (list || []).map(function (e) {
      var i = at != null ? at : ceil;
      var t = e.by_tier && e.by_tier[Math.min(i, e.by_tier.length - 1)];
      var then = t && t !== e.base ? ", at " + B.tierName(i) + " " + after(e.base, t) : "";
      return '<li class="fx' + (kind ? " is-" + kind : "") + '">' +
        (kind === "drawback" ? '<span class="fx-k">Drawback:</span> ' : "") + esc(e.base) + esc(then) + '</li>';
    }).join("");
  }

  function draw() {
    var track = B.state && B.state.track;
    var c = B.check, p = c && c.product;
    var fin = B.result && B.result.finished ? B.result.finish : null;
    if (B.loading || B.error || !B.state) {
      body.innerHTML = '<p class="tag-empty">' + (B.loading ? "Opening your kit." :
        B.error ? "Nothing to show until your satchel loads." : "") + '</p>';
      batchRow.hidden = true;
      return;
    }
    if (!p && !fin) {
      body.innerHTML = '<p class="tag-empty">Put something on the tool to see what it makes.</p>' + ladder(track, null);
      batchRow.hidden = !B.pot.items.length;
      drawBatch();
      return;
    }
    var at = preview != null ? preview : (fin ? fin.tier : null);
    var ceil = track ? Number(track.ceiling) || 0 : 0;
    if (!p && fin && fin.made) {
      // The pot is empty after a finish; the tag still shows what was just made.
      var m = fin.made;
      body.innerHTML = '<h3 class="tag-name">' + esc(m.name) + '</h3>' +
        '<p class="tag-line">' + esc((m.form || "").replace("-", " ")) + '</p>' + ladder(track, fin.tier);
      batchRow.hidden = true;
      return;
    }
    var unknown = p.unknown > 0 ? '<p class="tag-unknown">' + (p.unknown === 1 ? "1 property unknown" :
      esc(p.unknown) + " properties unknown") + '</p>' : "";
    body.innerHTML =
      '<h3 class="tag-name">' + esc(p.name) + '</h3>' +
      '<p class="tag-line">' + esc((p.form || "").replace("-", " ")) + '</p>' +
      (p.taken ? '<p class="tag-line">' + esc(p.taken) + '</p>' : "") +
      (p.keeps_minutes != null ? '<p class="tag-line">' + esc(keeps(p.keeps_minutes)) + '</p>' : "") +
      ladder(track, at) +
      '<ul class="tag-fx">' + lines(p.effects, at, ceil, "") + lines(p.drawbacks, at, ceil, "drawback") + '</ul>' +
      unknown +
      (p.source_text ? '<details class="tag-source"><summary>What the source says</summary><p>' +
        esc(p.source_text) + '</p></details>' : "");
    batchRow.hidden = false;
    drawBatch();
  }

  // --- the batch (UI plan §6.5) ---------------------------------------------------------
  // One roll and one game for the whole stack, which shares one tier; the time is the
  // server's, for the whole batch (revamp plan §6, "Bulk").
  function drawBatch() {
    var n = B.pot.batch, c = B.check;
    var time = c && c.minutes != null ? B.minutes(c.minutes) : "";
    var say = n === 1 ? (time ? "1 dose takes " + time + "." : "") :
      (time ? n + " doses take " + time + " and share one result." : n + " doses share one result.");
    var keep = document.activeElement && batchRow.contains(document.activeElement) ? document.activeElement.dataset.batch : null;
    batchRow.innerHTML =
      '<div class="tb-row"><label class="tb-label" for="bench-batch">Batch</label>' +
      '<div class="tb-step v2-recess">' +
        '<button type="button" class="v2-btn is-small" data-batch="less" aria-label="One dose fewer"' + (n <= 1 ? " disabled" : "") + '>−</button>' +
        '<input type="number" id="bench-batch" class="v2-well tb-n" min="1" step="1" value="' + n + '" data-batch="n">' +
        '<button type="button" class="v2-btn is-small" data-batch="more" aria-label="One dose more">+</button>' +
      '</div>' +
      '<button type="button" class="v2-btn is-small is-quiet" data-batch="all">All</button></div>' +
      '<p class="tb-say">' + esc(say) + '</p>';
    if (keep) {
      var again = batchRow.querySelector('[data-batch="' + keep + '"]');
      if (again && !again.disabled) again.focus();
    }
  }
  batchRow.addEventListener("click", function (e) {
    var b = e.target.closest("[data-batch]");
    if (!b || b.disabled) return;
    var k = b.dataset.batch;
    if (k === "less") B.setBatch(B.pot.batch - 1);
    else if (k === "more") B.setBatch(B.pot.batch + 1);
    else if (k === "all") B.setBatch(B.maxBatch());
  });
  batchRow.addEventListener("change", function (e) {
    if (e.target.id === "bench-batch") B.setBatch(e.target.value);
  });

  // --- what came of it (UI plan §5, steps 4 and 6) -----------------------------------------
  function potLine(lost, pot) {
    // "1 of 2 Comfrey": what the pot held of each, from the pot as it was rolled.
    return lost.map(function (l) {
      var had = 0;
      (pot || []).forEach(function (p) { if (p.key === l.key) had = p.count * (B.pot.batch || 1); });
      return l.count + (had ? " of " + had : "") + " " + l.name;
    }).join(", ");
  }

  function drawResult() {
    var r = B.result;
    if (!r) { result.innerHTML = ""; return; }
    if (r.failed) {
      var miss = r.roll ? Math.abs(Math.min(0, Number(r.roll.margin) || 0)) : 0;
      var head = miss ? "Missed by " + miss + "." : "Failed.";
      var loss = r.lost.length ? " Half the materials are ruined: " + potLine(r.lost, r.pot) + " lost." : " Nothing is lost.";
      var time = r.minutes ? " " + B.minutes(r.minutes) + " passed." : "";
      result.innerHTML = '<p class="tr-loss">' + esc(head + loss + time) + '</p>';
      return;
    }
    var f = r.finish;
    var out = [];
    if (f.made) {
      out.push('<p class="tr-made">Made ' + esc(f.made.name) + (f.count > 1 ? " ×" + esc(f.count) : "") +
        (f.tier_name ? ", " + esc(f.tier_name) : "") + '.</p>');
    }
    if (r.stopped) out.push('<p class="tr-note">Stopped early. You kept what you had.</p>');
    var mast = f.mastery || {};
    if (mast.lines && mast.lines.length) {
      out.push('<ul class="tr-mastery">' + mast.lines.map(function (l) {
        return '<li><span>' + esc(l.why) + '</span><b>+' + esc(l.mp) + '</b></li>';
      }).join("") + '</ul>');
    }
    (mast.levelled || []).forEach(function (lv) {
      out.push('<p class="tr-level">You are now Herbalist ' + esc(typeof lv === "object" ? lv.level : lv) + '.</p>');
    });
    (f.discoveries || []).forEach(function (d) {
      out.push('<p class="tr-new">New: ' + esc(d.name) + ', ' + esc(lowerFirst(d.text)) + '.</p>');
    });
    var next = f.next && f.next.method ? f.next.method : localNext();
    if (next) {
      var info = B.methodInfo(next);
      out.push('<button type="button" class="v2-btn is-go is-small" id="bench-next" data-next="' + esc(next) + '">Next: ' +
        esc(info ? info.name : next) + '</button>');
    }
    result.innerHTML = out.join("");
  }
  function lowerFirst(t) { t = String(t || ""); return t.charAt(0).toLowerCase() + t.slice(1); }

  // A loaded recipe's next step, when the server did not name one (36 loads recipes).
  function localNext() {
    var rec = B.recipe;
    if (!rec || !rec.recipe || !rec.recipe.steps) return null;
    var s = rec.recipe.steps[rec.step + 1];
    return s ? s.method : null;
  }

  result.addEventListener("click", function (e) {
    var n = e.target.closest("[data-next]");
    if (!n) return;
    if (B.recipe && B.recipe.recipe.steps[B.recipe.step + 1] &&
        B.recipe.recipe.steps[B.recipe.step + 1].method === n.dataset.next) {
      B.recipe.step += 1;
      if (B.loadStep) { B.loadStep(B.recipe.recipe.steps[B.recipe.step]); return; }
    }
    B.setMethod(n.dataset.next, { focus: true });
  });

  B.on("loading", draw);
  B.on("error", draw);
  B.on("state", draw);
  B.on("check", draw);
  B.on("pot", function () { draw(); drawResult(); });
  B.on("method", function () { preview = null; draw(); drawResult(); });
  B.on("rolling", function () { preview = null; drawResult(); });
  B.on("play", function () { preview = 0; draw(); });
  B.on("score", function (s) {
    var track = B.state && B.state.track;
    var c = track ? Number(track.ceiling) || 0 : 0;
    var next = Math.min(c, Math.floor(Math.max(0, Math.min(1, Number(s) || 0)) * (c + 1)));
    if (next === preview) return;
    preview = next;
    draw();
  });
  B.on("result", function () { preview = null; draw(); drawResult(); });
})();
