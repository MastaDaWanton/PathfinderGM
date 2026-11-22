/* The first-time cards, and the "?" and the Settings list that show them again.
 * `window.Tutorials`. Loaded by the table and the home page.
 *
 * The design is docs/tutorials-plan.md (§3) and the research docs/research/2026-11-21-
 * tutorials.md. The words are the server's (content/tutorials/*.json through
 * play/tutorials.py), numbers filled from the engine; what has been seen is the server's
 * too (`tutorials.json` in the data folder), so a phone on the LAN and a launch on another
 * port know what this install has already read.
 *
 * WHAT THE PLAYER SEES. One card at a time, beside the section it is about, the first time
 * the section is met. Each step may point at one real control with a gold ring drawn on the
 * control itself; nothing is laid over the page. The card is a `popover="manual"` in the top
 * layer: no backdrop, no full-screen box, no ::backdrop (0.2.13 shipped an invisible layer
 * that ate every click, and Intro.js has the same bug open, #2207; tools/table_hit_test.js
 * runs with a card open to prove the card takes nothing but its own box). No timer ever
 * moves it on or away (WCAG 2.2.1).
 *
 * WHEN. `arrive(id)` says the player is at a section. Its card shows if it is due (never
 * seen, or new steps since), tips are on, nothing else is on screen, and nothing is in the
 * player's way: never while the pen holds unsent words, the dice mat waits for a roll, a
 * death or Settings fills the screen, or a bench game is playing. A card that has to wait
 * waits in the queue and tries again on the next key, click or submit; the queue drops a
 * card whose section is no longer on screen. A model turn is a good time to read, so a
 * card is free to show while the engine runs.
 *
 * FOCUS (WAI-ARIA APG dialog, non-modal). Opened by the player (the "?" or Show me), focus
 * goes to the card's heading, Tab stays in the card, Esc closes it and focus returns to
 * what opened it. Opened by itself, focus is never taken (the player may be typing); the
 * step is said through a polite status line, F6 moves into the card, and Esc puts it away
 * as "Not now" unless the player is in a field with words in it.
 *
 * PLACEMENT is measured, not CSS anchor positioning: one path for Electron and for a LAN
 * browser that lacks anchor CSS (Safari before 26). Beside the control, else above or
 * below, else a corner, choosing the place that covers the fewest other controls and never
 * the turn's own (End turn, Commit, the pen, Say) or the control it points at; never more
 * than a quarter of the window. Below 600px wide it docks under the tab strip, where the
 * pen is not.
 *
 * No third-party code, as everywhere in play/static/js.
 */
(function () {
  "use strict";

  var D = null;                 // the server's answer: {off, welcome_dismissed, tutorials, games_seen}
  var BY = {};                  // id -> tutorial
  var queue = [];               // [{id, opts}] waiting their turn
  var snoozed = {};             // id -> true: "Not now" until the section is entered again
  var reach = {};               // id -> fn(): go to the section on this page (the table)
  var readyFns = [];
  var open = null;              // {id, steps, i, auto, from, opts}
  var card = null, ringed = null, status = null;

  // What a card never covers: the turn's own controls (tools/table_hit_test.js MUST_SHOW).
  var MUST_SHOW = ["#cb-commit", "#cb-end", "#input", "#sayform button[type=submit]"];
  var HAS_POPOVER = typeof HTMLElement !== "undefined" && HTMLElement.prototype.hasOwnProperty("popover");

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function csrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }
  function adopt(d) {
    if (!d || !Array.isArray(d.tutorials)) return;
    D = d; BY = {};
    d.tutorials.forEach(function (t) { BY[t.id] = t; });
    document.dispatchEvent(new CustomEvent("tutorials:change"));
  }
  function post(body) {
    return fetch("/api/tutorials", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify(body)
    }).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d) adopt(d); return d; })
      .catch(function () { return null; });   // offline for a moment: the card shows again, that is all
  }
  function load() {
    return fetch("/api/tutorials", { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) return;
        adopt(d);
        // A version raised by a rename alone: nothing new to show, so the mark catches up.
        var quiet = d.tutorials.filter(function (t) { return t.updated && !t.due.length; })
          .map(function (t) { return t.id; });
        if (quiet.length) post({ seen: quiet });
        var fns = readyFns; readyFns = [];
        fns.forEach(function (fn) { try { fn(); } catch (e) { console.error(e); } });
        pump();
      })
      .catch(function () { /* no tips this load; the game is unaffected */ });
  }

  // --- what is on screen ------------------------------------------------------------------
  function visible(el) {
    if (!el || !el.getClientRects().length || el.closest("[hidden]") || el.closest("[inert]")) return false;
    var cs = getComputedStyle(el);
    return cs.visibility !== "hidden" && cs.display !== "none";
  }
  function anchorEl(name) {
    if (!name) return null;
    var all = document.querySelectorAll('[data-tut="' + name + '"]');
    for (var i = 0; i < all.length; i++) if (visible(all[i])) return all[i];
    return null;
  }
  // On screen and in reach: the section's own test, if it gave one, and its root drawn and
  // not under a layer that made it inert (a bench open over the map).
  function still(id, opts) {
    try { if (opts && typeof opts.still === "function" && !opts.still()) return false; } catch (e) { return false; }
    var t = BY[id];
    return !!(t && anchorEl(t.root));
  }
  // Something the player is in the middle of, which no automatic card may interrupt. A
  // bench's own dialog blocks every card but the one about that dialog (the perk picker's).
  function blocked(q) {
    if (!D || D.off) return true;
    var pen = document.getElementById("input");
    if (pen && pen.value.trim() && visible(pen)) return true;   // unsent words: wait for Say or an empty pen
    if (document.querySelector("#d3d-mat.on, #deathveil.on")) return true;
    var set = document.getElementById("settingslayer");
    if (set && !set.hidden) return true;
    if (document.querySelector(".bench:not([hidden]) .bench-gamebay:not([hidden])")) return true;
    var modal = document.querySelector(".bench:not([hidden]) .bench-modal:not([hidden])");
    if (modal) {
      var root = q && BY[q.id] && anchorEl(BY[q.id].root);
      if (!root || !modal.contains(root)) return true;
    }
    return false;
  }

  // --- the queue --------------------------------------------------------------------------
  function pump() {
    if (open) {
      // An asked-for card stays put unless the section it was shown on has gone (the perk
      // picker's "?" card stayed over the bench after Later, phase 5).
      if (!open.auto ? !(open.rooted && !anchorEl(BY[open.id].root)) : still(open.id, open.opts)) return;
      hide();   // its section went away under it: it waits for the next arrival
    }
    queue = queue.filter(function (q) { return still(q.id, q.opts); });
    var k = queue.findIndex(function (x) { return !blocked(x); });
    if (k < 0) return;
    var q = queue.splice(k, 1)[0], t = BY[q.id];
    if (t && t.due.length && !snoozed[q.id]) present(q.id, t.due, true, null, q.opts);
  }

  function arrive(id, opts) {
    opts = opts || {};
    if (!D) { readyFns.push(function () { arrive(id, opts); }); return; }
    var t = BY[id];
    if (!t || D.off) return;
    if (opts.entered) delete snoozed[id];
    if (snoozed[id] || !t.due.length || (open && open.id === id)) return;
    if (!queue.some(function (q) { return q.id === id; })) queue.push({ id: id, opts: opts });
    pump();
  }

  // --- the card ---------------------------------------------------------------------------
  function say(text) {
    if (!status) {
      status = document.createElement("div");
      status.className = "tut-vh";
      status.setAttribute("role", "status");
      document.body.appendChild(status);
    }
    status.textContent = "";
    setTimeout(function () { status.textContent = text; }, 30);
  }

  function ensureCard(host) {
    if (!card) {
      card = document.createElement("div");
      card.className = "tut-card";
      card.setAttribute("role", "dialog");
      card.setAttribute("aria-labelledby", "tut-h");
      if (HAS_POPOVER) card.setAttribute("popover", "manual");
      card.addEventListener("click", onCardClick);
      card.addEventListener("keydown", onCardKey);
    }
    // Inside a bench's layer when the section is a bench: the layer makes everything else
    // inert and keeps Tab inside itself (29-bench-core.js), and the card must be in reach.
    if (card.parentNode !== host) {
      if (HAS_POPOVER && card.matches(":popover-open")) card.hidePopover();
      host.appendChild(card);
    }
    return card;
  }

  function stepHtml() {
    var t = BY[open.id], k = open.steps[open.i], s = t.steps[k], n = open.steps.length;
    var kick = (open.auto && t.updated ? "New since you last looked" : esc(t.title)) +
      (n > 1 ? ", " + (open.i + 1) + " of " + n : "");
    var btns = (s.buttons || []).map(function (b) {
      return "<li><b>" + esc(b.label) + "</b> " + esc(b.words) + "</li>";
    }).join("");
    var last = open.i === n - 1;
    return '<p class="tut-kick">' + kick + "</p>" +
      '<h3 id="tut-h" tabindex="-1">' + esc(s.title) + "</h3>" +
      '<div class="tut-body">' + (s.words ? '<p class="tut-words">' + esc(s.words) + "</p>" : "") +
      (btns ? '<ul class="tut-btns">' + btns + "</ul>" : "") +
      (last && t.manual ? '<p class="tut-more"><a href="/manual#' + esc(t.manual) + '" target="_blank" rel="noopener">More in the manual</a></p>' : "") +
      "</div>" +
      '<div class="tut-nav">' +
      (open.i > 0 ? '<button type="button" class="v2-btn is-quiet is-small" data-tut-act="back">Back</button>' : "") +
      (last ? "" : '<button type="button" class="v2-btn is-small" data-tut-act="next">Next</button>') +
      '<button type="button" class="v2-btn is-small' + (last ? " is-go" : " is-quiet") + '" data-tut-act="done">Got it</button>' +
      (open.auto ? '<button type="button" class="v2-btn is-quiet is-small" data-tut-act="later">Not now</button>' : "") +
      // In the button row, not a footer of its own: on a phone the card is a quarter of the
      // window and every line of chrome is a line of words scrolled away (seen at 375x812).
      '<button type="button" class="tut-link" data-tut-act="off">Turn tips off</button>' +
      "</div>";
  }

  function present(id, steps, auto, from, opts) {
    var t = BY[id];
    if (!t || !steps.length) return;
    if (open) hide();
    var a = anchorEl(t.root) || anchorEl(t.steps[steps[0]].anchor);
    var host = (a && a.closest(".bench:not([hidden])")) || document.body;
    open = { id: id, steps: steps, i: 0, auto: auto, from: from || null, opts: opts || {}, rooted: !!anchorEl(t.root) };
    ensureCard(host);
    showStep(!auto);
    say((auto ? "Tip: " : "") + t.steps[steps[0]].title + ". " + (t.steps[steps[0]].words || ""));
  }

  function showStep(takeFocus) {
    var t = BY[open.id], s = t.steps[open.steps[open.i]];
    card.innerHTML = stepHtml();
    card.classList.add("on");
    if (HAS_POPOVER && !card.matches(":popover-open")) card.showPopover();
    ring(anchorEl(s.anchor));
    place();
    if (takeFocus) {
      var h = card.querySelector("#tut-h");
      if (h) h.focus({ preventScroll: true });
    }
  }

  function ring(el) {
    if (ringed) ringed.classList.remove("tut-ring");
    ringed = el || null;
    if (!ringed) return;
    ringed.classList.add("tut-ring");
    var r = ringed.getBoundingClientRect();
    // Off the window, or on it but under something else: a bench's strip lies over its
    // scrolled frame, and the forge's Roll Craft sat ringed beneath it (phase 5, 1024x700).
    var cx = (r.left + r.right) / 2, cy = (r.top + r.bottom) / 2;
    // What lies there under the card itself, which is about to move.
    var over = cx >= 0 && cx < innerWidth && cy >= 0 && cy < innerHeight
      ? document.elementsFromPoint(cx, cy).filter(function (e) { return !(card && card.contains(e)); })[0] : null;
    var hid = !over || !(ringed.contains(over) || over.contains(ringed));
    // Centred, not "nearest": nearest leaves it at the top edge, under that strip.
    if (hid || r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) {
      ringed.scrollIntoView({ block: "center", inline: "nearest" });
    }
  }

  function hide() {
    if (!card) return;
    if (HAS_POPOVER && card.matches(":popover-open")) card.hidePopover();
    card.classList.remove("on");
    card.innerHTML = "";
    ring(null);
    var was = open;
    open = null;
    // Focus back to what opened it, only when the player opened it and focus is in the card.
    if (was && !was.auto && was.from && document.contains(was.from) && !was.from.closest("[inert]")) {
      try { was.from.focus({ preventScroll: true }); } catch (e) { /* gone */ }
    }
  }

  function finish(how) {
    if (!open) return;
    var id = open.id, t = BY[id];
    if (how === "done") {
      t.seen = true; t.due = []; t.updated = false;
      post({ seen: [id] });
    } else if (how === "later") {
      snoozed[id] = true;
    } else if (how === "off") {
      if (D) D.off = true;
      post({ off: true });
      say("Tips are off. Settings, Tutorials turns them back on.");
    }
    hide();
    pump();
  }

  function onCardClick(e) {
    var b = e.target.closest("[data-tut-act]");
    if (!b || !open) return;
    var act = b.dataset.tutAct;
    if (act === "next" && open.i < open.steps.length - 1) { open.i++; showStep(true); }
    else if (act === "back" && open.i > 0) { open.i--; showStep(true); }
    else if (act === "done" || act === "later" || act === "off") finish(act);
  }

  // Tab stays in the card while focus is in it (the APG dialog); Esc is handled below.
  function onCardKey(e) {
    if (e.key !== "Tab") return;
    var list = Array.prototype.filter.call(card.querySelectorAll("button, a[href], [tabindex='-1']#tut-h"),
      function (el) { return el.getClientRects().length; });
    if (!list.length) return;
    var first = list[0], last = list[list.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  // Esc and F6, ahead of the bench's and the sheet's own Esc: one key closes one thing.
  document.addEventListener("keydown", function (e) {
    if (!open) return;
    var inCard = card && card.contains(document.activeElement);
    if (e.key === "F6" && !inCard) {
      e.preventDefault();
      var h = card.querySelector("#tut-h");
      if (h) h.focus();
      return;
    }
    if (e.key !== "Escape") return;
    var t = e.target, typing = t && /^(INPUT|TEXTAREA)$/.test(t.tagName) && String(t.value || "").trim();
    if (!inCard && typing) return;
    e.preventDefault();
    e.stopPropagation();
    finish(open.auto ? "later" : "close");
  }, true);

  // --- placement --------------------------------------------------------------------------
  function rectOf(el) { var r = el.getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom }; }
  function overlap(a, b) {
    var w = Math.min(a.r, b.r) - Math.max(a.l, b.l), h = Math.min(a.b, b.b) - Math.max(a.t, b.t);
    return w > 0 && h > 0 ? w * h : 0;
  }
  function guarded() {
    var out = [];
    MUST_SHOW.forEach(function (s) {
      // Inert under a bench still counts: the release hit test holds the card off the pen and
      // Say whatever lies between (the circle's card sat on both at 1024x700, phase 5).
      document.querySelectorAll(s).forEach(function (el) {
        if (el.getClientRects().length && !el.closest("[hidden]")) out.push(rectOf(el));
      });
    });
    var f = document.activeElement;
    if (f && f !== document.body && !(card && card.contains(f)) && visible(f)) out.push(rectOf(f));
    return out;
  }
  function controls() {
    return Array.prototype.filter.call(document.querySelectorAll(
      "button, a[href], input:not([type=hidden]), select, textarea, [role=button]"), function (el) {
      return !(card && card.contains(el)) && visible(el);
    }).map(rectOf);
  }

  function place() {
    if (!card || !open) return;
    var W = innerWidth, H = innerHeight, G = 16;
    var narrow = W < 600;
    var w = Math.min(narrow ? W - 2 * G : 340, W - 2 * G);
    // At most a quarter of the window, whatever the words: the body scrolls inside.
    var maxH = Math.max(120, Math.min(H - 2 * G, Math.floor(0.25 * W * H / w)));
    card.style.width = w + "px";
    card.style.maxHeight = maxH + "px";
    var h = Math.min(card.scrollHeight, maxH);
    var a = ringed ? rectOf(ringed) : null;
    var keep = guarded(), ctl = controls();
    // The control it points at is never covered; a whole panel it points at (a bench's work
    // order, stacked at 1024x700 to fill the window) may be, at a price, since no place
    // beside it was left and the card fell to the top over the method strip (phase 5).
    var big = a && (a.r - a.l) * (a.b - a.t) > W * H / 4;
    if (a && !big) keep.push(a);
    var cands = [];
    var clampX = function (x) { return Math.max(G, Math.min(W - G - w, x)); };
    var clampY = function (y) { return Math.max(G, Math.min(H - G - h, y)); };
    if (narrow) {
      // Under the tab strip (or the bench's strip), at the top of the stage: never at the
      // bottom, where the pen is.
      var strip = document.querySelector(".bench:not([hidden]) .bench-strip") || document.querySelector(".topbar, body > header");
      var top = strip && visible(strip) ? strip.getBoundingClientRect().bottom + 8 : G;
      cands.push([G, top]);
      if (a) cands.push([G, a.b + 8], [G, a.t - 8 - h]);
      cands.push([G, H - G - h]);
    } else {
      if (a) {
        cands.push([a.r + 12, a.t], [a.l - 12 - w, a.t], [a.l, a.b + 10], [a.l, a.t - 10 - h],
                   [a.r + 12, a.b - h], [a.l - 12 - w, a.b - h], [a.r - w, a.b + 10], [a.r - w, a.t - 10 - h]);
      }
      // Centred under or over the control (a bench's method strip runs the width of the
      // window, and the open stage under it holds no controls), then the corners.
      if (a) cands.push([(W - w) / 2, a.b + 10], [(W - w) / 2, a.t - 10 - h]);
      cands.push([W - G - w, 64], [G, 64], [(W - w) / 2, 64], [W - G - w, H - G - h], [G, H - G - h]);
      // Then a sweep down the window. At 1024x700 the forge stacks its columns, and with the
      // foot ringed every place beside it lay over the rack's full-width search box (seen
      // live, phase 5); the open text higher up held no control at all.
      for (var gy = G; gy <= H - G - h; gy += 32) cands.push([G, gy], [(W - w) / 2, gy], [W - G - w, gy]);
    }
    var best = null;
    cands.forEach(function (c) {
      var x = clampX(c[0]), y = clampY(c[1]);
      var box = { l: x, t: y, r: x + w, b: y + h };
      if (keep.some(function (k) { return overlap(box, k) > 0; })) return;
      var cost = ctl.reduce(function (n, k) { return n + (overlap(box, k) > 0 ? 1 : 0); }, 0) +
        (big && overlap(box, a) > 0 ? 0.5 : 0);
      // Nearer the control it is about is better, all else equal.
      var dist = a ? Math.abs((x + w / 2) - (a.l + a.r) / 2) + Math.abs((y + h / 2) - (a.t + a.b) / 2) : 0;
      var score = cost * 10000 + dist;
      if (!best || score < best.s) best = { s: score, x: x, y: y };
    });
    if (!best) best = { x: clampX(cands[0][0]), y: G };   // nowhere clean: the top, never over the pen
    card.style.left = Math.round(best.x) + "px";
    card.style.top = Math.round(best.y) + "px";
  }
  window.addEventListener("resize", function () { if (open) place(); });

  // Another try for anything waiting, after the things that can unblock it; and a look at
  // the open card, whose section a bench opening over it may have just taken away (seen
  // live on the LAN phone: the Table's card stayed up over the herb bench). Focus moves
  // when any layer opens, so `focusin` catches what a click alone did not.
  ["input", "submit", "click", "keyup", "focusin"].forEach(function (ev) {
    document.addEventListener(ev, function () { if (queue.length || open) setTimeout(pump, 0); }, true);
  });

  // --- asked for: the "?" and Show me ---------------------------------------------------
  function show(id, from) {
    if (!D) { readyFns.push(function () { show(id, from); }); return; }
    var t = BY[id];
    if (!t) return;
    if (reach[id]) { try { reach[id](); } catch (e) { console.error(e); } }
    var all = t.steps.map(function (_, i) { return i; });
    // The section draws its controls after it opens (the bench reads its state first).
    setTimeout(function () { present(id, all, false, from || document.activeElement); }, reach[id] ? 120 : 0);
  }

  // --- the inline first-time line (plan §3.1) ---------------------------------------------
  // For what is already a prompt (the forced-march line): one sentence inside it, where a
  // card would be a card over a card. The caller writes the returned HTML into its own
  // markup. Due and tips on, it is marked seen the first time it is drawn and kept for the
  // rest of this page, so a redraw of the prompt does not snatch it away mid-read. The "?"
  // and Show me still show it as a card. Written by phase 4 in the shape §3.1 gives; phase 3
  // builds the same helper for the dice popup, and the merge keeps one.
  var inlined = {};             // id -> the line, once drawn on this page
  function inline(id) {
    var t = D && BY[id];
    if (!t) return "";
    if (!(id in inlined)) {
      if (D.off || !t.due.length) return "";
      inlined[id] = t.due.map(function (k) { return t.steps[k].words || ""; }).join(" ");
      t.seen = true; t.due = []; t.updated = false;
      post({ seen: [id] });
    }
    return '<span class="tut-inline">' + esc(inlined[id]) + "</span>";
  }

  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-tut-help]");
    if (b) { e.preventDefault(); show(b.dataset.tutHelp, b); return; }
    var s = e.target.closest && e.target.closest("[data-tut-show]");
    if (s) { e.preventDefault(); showMe(s.dataset.tutShow, s); return; }
    if (e.target.closest && e.target.closest("[data-tut-reset]")) { e.preventDefault(); post({ reset: true }).then(function () { say("Every tip will show again."); }); return; }
    var o = e.target.closest && e.target.closest("[data-tut-toggle]");
    if (o) { e.preventDefault(); post({ off: !(D && D.off) }); return; }
    if (e.target.closest && e.target.closest("[data-tut-welcome]")) {
      e.preventDefault();
      var line = e.target.closest(".tut-welcome");
      if (line) line.remove();
      post({ welcome: true });
    }
  });

  // --- Settings, Tutorials (the index) ----------------------------------------------------
  // Show me goes to the section when this page has it (the table registers `reach`), or
  // asks the table around the Settings frame to, or says the words in place.
  function showMe(id, from) {
    if (reach[id]) { show(id, from); return; }
    if (window.parent && window.parent !== window) {
      window.parent.postMessage({ pgm: "tutorial-show", id: id }, location.origin);
      return;
    }
    var box = document.querySelector('[data-tut-words="' + id + '"]');
    if (box) box.hidden = !box.hidden;
  }

  function index() {
    if (!D) return '<p class="note">Reading the tips…</p>';
    var groups = [];
    D.tutorials.forEach(function (t) { if (groups.indexOf(t.group) < 0) groups.push(t.group); });
    return '<p class="note">Each part of the game shows a short card the first time you open it. ' +
      "The <b>?</b> beside a part shows its card again.</p>" +
      groups.map(function (g) {
        return '<h3 class="subsect">' + esc(g) + "</h3>" + D.tutorials.filter(function (t) { return t.group === g; })
          .map(function (t) {
            return '<div class="tut-row"><span class="tut-name">' + esc(t.title) + "</span>" +
              '<span class="pill' + (t.seen && !t.updated ? " now" : "") + '">' + (t.updated ? "changed" : t.seen ? "seen" : "not yet") + "</span>" +
              '<button type="button" class="v2-btn is-small" data-tut-show="' + esc(t.id) + '">Show me</button></div>' +
              '<div class="tut-inplace" data-tut-words="' + esc(t.id) + '" hidden>' + t.steps.map(function (s) {
                return "<p><b>" + esc(s.title) + ".</b> " + esc(s.words || "") + "</p>" + ((s.buttons || []).length
                  ? "<ul>" + s.buttons.map(function (b) { return "<li><b>" + esc(b.label) + "</b> " + esc(b.words) + "</li>"; }).join("") + "</ul>" : "");
              }).join("") + "</div>";
          }).join("");
      }).join("") +
      '<div class="tut-actions"><button type="button" class="v2-btn" data-tut-reset>Show all tips again</button> ' +
      '<button type="button" class="v2-btn is-quiet" data-tut-toggle>' + (D.off ? "Turn tips on" : "Turn tips off") + "</button></div>";
  }

  // The one line on the home page's first launch (owner decision D1, with the Manual, D9).
  function welcome() {
    if (!D || D.off || D.welcome_dismissed) return "";
    return '<p class="tut-welcome"><span>Tips will show the first time you open each part of the game. ' +
      'You can turn them off in Settings, or read the <a href="/manual">Manual</a>.</span>' +
      '<button type="button" class="v2-btn is-quiet is-small" data-tut-welcome>Got it</button></p>';
  }

  // --- the minigames' first cards (33-bench-games.js) -----------------------------------------
  // Their marks were `pgm.games.seen.<id>` in this browser's storage; read once here and
  // posted, then removed, so the store is the one source from then on.
  function migrateGames() {
    var ids = [], keys = [];
    try {
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        var m = /^pgm\.games\.seen\.([a-z][a-z_-]*)$/.exec(k || "");
        if (m && localStorage.getItem(k) === "1") { ids.push("game." + m[1]); keys.push(k); }
      }
    } catch (e) { return; }
    if (!ids.length) return;
    post({ seen: ids }).then(function (d) {
      if (!d) return;   // kept for the next load
      try { keys.forEach(function (k) { localStorage.removeItem(k); }); } catch (e) { /* */ }
    });
  }

  window.Tutorials = {
    load: load,
    ready: function () { return !!D; },
    arrive: arrive,
    show: show,
    inline: inline,
    reach: function (id, fn) { reach[id] = fn; },
    isOpen: function () { return open ? open.id : ""; },
    close: function () { if (open) finish(open.auto ? "later" : "close"); },
    index: index,
    welcome: welcome,
    off: function () { return !!(D && D.off); },
    // A minigame's first card is due unless its game was scored well before, or tips are off.
    gameSeen: function (method) {
      if (!D) return null;
      return D.off || D.games_seen.indexOf(method) >= 0;
    },
    markGame: function (method) {
      if (D && D.games_seen.indexOf(method) < 0) D.games_seen.push(method);
      return post({ seen: ["game." + method] });
    },
    migrateGames: migrateGames,
    // For tools/table_hit_test.js: the card's box and the anchors it could not find.
    report: function () {
      if (!open || !card) return null;
      var t = BY[open.id], r = card.getBoundingClientRect();
      return {
        id: open.id, step: open.i, area: (r.width * r.height) / (innerWidth * innerHeight),
        rect: { left: r.left, top: r.top, right: r.right, bottom: r.bottom },
        missing: t.steps.map(function (s) { return s.anchor; }).filter(function (n) { return n && !anchorEl(n); })
      };
    },
    card: function () { return card; },
    // A page that draws itself again from strings (home.html's `render`) throws away the
    // ringed control with the rest: ring its new copy, without scrolling, and place again.
    refresh: function () {
      if (!open || !card) return;
      var el = anchorEl(BY[open.id].steps[open.steps[open.i]].anchor);
      if (el !== ringed) {
        if (ringed) ringed.classList.remove("tut-ring");
        ringed = el || null;
        if (ringed) ringed.classList.add("tut-ring");
      }
      place();
    },
  };

  load();
})();
