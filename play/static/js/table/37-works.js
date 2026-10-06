// The play table, part 37 (In progress: every craft's unfinished work, one panel). Classic
// script in one IIFE, reached through `window.Works` (docs/enchanting-contracts.md §13), so
// no name here can shadow one of 01-36's.
//
// WHAT IT IS (enchanting UI plan §6.10; the owner, Round 4 point 5 and leatherworking Q9.3:
// "for all crafts there should be an in progress section where all the crafts sit before
// they can be collected ... countdown timers that move with game time"). One non-modal
// panel, "In progress", opened from three places that all say the same count:
//   - a door in the left column under the craft doors ("In progress" with "1 ready" struck
//     in gilt when something is ready), made here so it sits after whichever craft doors
//     this build has;
//   - an "In progress" button in every bench's footer (the core draws it, 29);
//   - each bench's shelf, whose In progress group (`Works.group`) shows that craft's rows.
//
// PRIOR ART (rules/inprogress.py's docstring carries the search): EVE Online's industry
// window, where a finished job's button becomes Deliver; Stardew Valley's most-installed
// quality-of-life mods, one list across every location sorted ready-then-busy. Hence one
// list grouped by STATE, not craft: Ready to collect first, then Working, soonest first,
// each row carrying its craft's icon so the craft still reads at a glance. The count on the
// door is in its visible words ("1 ready"), not an icon badge with an aria-label: a
// static aria-label replaces a button's text in the accessible name and the count goes
// unread (the pattern the accessible-badge write-ups warn about), so the words ARE the name.
//
// THE PAGE COMPUTES NOTHING. Every number and word on a row (the countdown "ready in 6 days",
// "day 15, morning", the dial's fraction, why a row cannot be collected here) is the
// server's, from `GET api/works`. The countdown moves with GAME time: the rows are asked
// again when the clock has turned (the table's state lands with a new minute, or a bench's
// state does), never on a timer. There is no setInterval and no requestAnimationFrame in
// this file (tests/test_works_ui.py greps for both): a real-time tick would count down a
// steep while the player sat at the menu, which is exactly what "game time" rules out.
//
// WHERE IT STANDS. Over the table it is a sidebar at z 34, under the bench layers (35) and
// over the table's popovers (30). Opened from inside a bench it must be inside that bench:
// the bench is modal, makes everything behind it inert and traps Tab in its layer, so a
// panel left at z 34 would be under it and unreachable. It moves into the bench's own
// popover host, as 29 moves the scene clock onto the bench's stage, and takes its Esc
// from the bench's stack (one Esc closes the panel, the next the bench).

(function () {
  "use strict";

  var $id = function (id) { return document.getElementById(id); };
  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var STILL = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  function reduced() {
    if (window.BenchCore && typeof BenchCore.reduced === "function") return BenchCore.reduced();
    return !!(STILL && STILL.matches);
  }
  function sound(name) {
    // Lane U6 names these on the sound buses; an unknown event is silent, so the call is
    // made now and the sound arrives with that lane (contracts §13, "Sound").
    try { if (window.Sound && typeof Sound.play === "function") Sound.play(name); }
    catch (err) { /* sound is a nicety */ }
  }
  function csrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }
  // The core's API when it is on the page (the same CSRF and error sentences); this file's
  // own copy otherwise, so a page without the benches still has its In progress.
  function api(path, body) {
    if (window.BenchCore && typeof BenchCore.api === "function") return BenchCore.api(path, body);
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

  var W = window.Works = { esc: esc };

  // --- what the server last said ---------------------------------------------------------
  var rows = null;           // null until the first answer; [] is "nothing in progress"
  var summary = null;        // {ready, working, next}
  var error = "";
  var stamp = null;          // the clock (and what is in progress) the rows were asked at
  var inflight = null, again = false;
  var said = "";             // the last Collect or Stop sentence, shown in the panel
  var asking = null;         // the key whose Stop is being confirmed
  var groups = [];           // [{host, craft}] shelves showing a group

  function load() {
    if (inflight) { again = true; return inflight; }
    inflight = api("/api/works").then(function (d) {
      error = "";
      adopt(d);
    }).catch(function (err) {
      error = err.message || String(err);
      drawAll();
    }).then(function () {
      inflight = null;
      if (again) { again = false; load(); }
    });
    return inflight;
  }
  function adopt(d) {
    if (d && Array.isArray(d.rows)) rows = d.rows;
    if (d && d.summary) W.refresh(d.summary);
    if (asking && !(rows || []).some(function (r) { return r.key === asking; })) asking = null;
    drawAll();
  }

  // Ask again only when the clock (or what is in progress) has changed since the rows were
  // asked, so a bench redrawing its shelf on every pick does not fetch on every pick.
  W.sync = function (key) {
    key = String(key == null ? "" : key);
    if (rows !== null && key === stamp) return;
    stamp = key;
    // Nothing on screen shows the rows: they are asked when the panel opens or a shelf
    // draws its group, so a turn at the table costs no second request.
    if (shown()) load();
  };
  function shown() { return isOpen() || live().length > 0; }
  W.rows = function (craft) {
    return (rows || []).filter(function (r) { return !craft || r.craft === craft; });
  };

  // --- the count, on every door and footer button ----------------------------------------
  // "1 ready" in gilt when anything waits to be collected (the arrival is noticed by the
  // count appearing, struck in the theme's gilt `v2-count`, not by a pop-up over play: plan
  // §6.10, "nothing pops over play"); "2 working" in quiet words when only work is under
  // way; nothing at all when nothing is.
  function countHtml(s) {
    if (s && s.ready > 0) return '<span class="v2-count wk-ready">' + esc(s.ready) + ' ready</span>';
    if (s && s.working > 0) return '<small class="wk-working">' + esc(s.working) + ' working</small>';
    return "";
  }
  W.countHtml = countHtml;
  W.refresh = function (s) {
    if (!s || typeof s !== "object") return;
    var before = summary;
    summary = { ready: Number(s.ready) || 0, working: Number(s.working) || 0, next: s.next || null };
    var more = before && summary.ready > before.ready;
    document.querySelectorAll("[data-works-open]").forEach(function (b) {
      var slot = b.querySelector(".wk-count");
      if (slot) slot.innerHTML = countHtml(summary);
      if (more) mark(b);
    });
    // The ready chime is lane U6's; only a rise is a reason for it (a first draw is not).
    if (more) sound("works.ready");
  };
  // One glint on the door when something new becomes ready: once, 600ms, opacity only, and
  // none under reduced motion, where the gilt count alone says it.
  function mark(b) {
    if (reduced()) return;
    b.classList.remove("wk-new");
    void b.offsetWidth;
    b.classList.add("wk-new");
    setTimeout(function () { b.classList.remove("wk-new"); }, 700);
  }
  W.summary = function () { return summary; };

  // The footer button every bench's footer carries (29's `renderFoot` asks for it).
  W.footButton = function () {
    return '<button type="button" class="bf-btn wk-foot" data-works-open aria-haspopup="dialog"' +
      ' aria-controls="works">In progress<span class="wk-count">' + countHtml(summary) + '</span></button>';
  };

  // --- a row (UI plan §6.10) -------------------------------------------------------------
  // Icon; the name and what is being done; where it is and the countdown in words with the
  // day and part of day under it; a small arc dial for the fraction elapsed (a circle, the
  // shape lock's exception for dials, no filled track); and the row's one action. Collect
  // is gold only on a ready row at hand. A ready row that must be collected elsewhere keeps
  // its Collect, refused (aria-disabled, so it can still be focused and read) with the
  // reason in words beside it, "Collect at Brannoc's tannery": never colour alone.
  function dial(f) {
    var n = typeof f === "number" ? Math.max(0, Math.min(1, f)) : 0;
    var arc = (n * 100).toFixed(1);
    return '<svg class="wk-dial" viewBox="0 0 36 36" aria-hidden="true" focusable="false">' +
      '<circle class="wk-dial-rim" cx="18" cy="18" r="15"></circle>' +
      (n > 0 ? '<circle class="wk-dial-arc" cx="18" cy="18" r="15" pathLength="100" ' +
               'stroke-dasharray="' + arc + ' 100" transform="rotate(-90 18 18)"></circle>' : "") +
      '</svg>';
  }
  function icon(r) {
    if (window.BenchIcons && typeof BenchIcons.html === "function") {
      return BenchIcons.html(r.icon || r.craft || "work", { size: 30, label: r.name });
    }
    return "";
  }
  function rowHtml(r, where) {
    var id = "wk-" + where + "-" + String(r.key).replace(/[^A-Za-z0-9_-]/g, "_");
    var ready = r.state === "ready";
    var acts = "";
    if (asking === r.key) {
      acts = '<div class="wk-confirm" role="group" aria-labelledby="' + id + '-q">' +
        '<p class="wk-q" id="' + id + '-q">Stop work on ' + esc(r.name) + '?' +
        (r.stop_words ? ' <span>' + esc(r.stop_words) + '</span>' : "") + '</p>' +
        '<div class="wk-acts"><button type="button" class="v2-btn is-small is-quiet" data-works-keep="' +
        esc(r.key) + '">Keep working</button><button type="button" class="v2-btn is-small is-quiet wk-danger" ' +
        'data-works-stop-yes="' + esc(r.key) + '">Stop</button></div></div>';
    } else {
      var collect = "";
      if (ready && r.can_collect) {
        collect = '<button type="button" class="v2-btn is-small is-go" data-works-collect="' + esc(r.key) +
          '">Collect</button>';
      } else if (ready) {
        collect = '<button type="button" class="v2-btn is-small" aria-disabled="true" aria-describedby="' +
          id + '-why" data-works-collect="' + esc(r.key) + '">Collect</button>' +
          '<span class="wk-why" id="' + id + '-why">' + esc(r.why_not || "It cannot be collected here") + '</span>';
      }
      var stop = r.can_stop ? '<button type="button" class="v2-btn is-small is-quiet" data-works-stop="' +
        esc(r.key) + '">Stop</button>' : "";
      if (collect || stop) acts = '<div class="wk-acts">' + collect + stop + '</div>';
    }
    // What is being done and where, on one quiet line ("Steeping, carried"; "Curing in the
    // vat, at Brannoc's tannery"). The countdown is its own line under it, in ink, with the
    // day and part of day beneath: in a column of its own beside the name it squeezed a
    // three-word name onto two lines at the panel's 380px (seen live, 2026-10-05).
    var what = [r.label && r.label !== r.name ? r.label : "", r.where_words || ""].filter(Boolean).join(", ");
    return '<li class="wk-row' + (ready ? " is-ready" : "") + '" data-works-key="' + esc(r.key) + '">' +
      '<span class="wk-icon">' + icon(r) + '</span>' +
      '<span class="wk-main">' +
        '<span class="wk-name">' + esc(r.name) + '</span>' +
        (what ? '<span class="wk-where">' + esc(what) + '</span>' : "") +
        '<span class="wk-left">' + esc(r.ready_words || "") + '</span>' +
        (!ready && r.ready_when ? '<span class="wk-when">' + esc(r.ready_when) + '</span>' : "") +
      '</span>' +
      '<span class="wk-time">' + dial(r.fraction) + '</span>' +
      acts +
    '</li>';
  }
  W.rowHtml = rowHtml;

  // --- the panel -------------------------------------------------------------------------
  var EMPTY = "Nothing is working. A jar put up to steep, and any other work that takes days, " +
              "waits here until it is ready to collect.";
  function listHtml() {
    if (error && rows === null) {
      return '<div class="wk-state"><p>Couldn\'t load what is in progress.</p><p class="wk-detail">' +
        esc(error) + '</p><button type="button" class="v2-btn is-small" data-works-retry>Retry</button></div>';
    }
    if (rows === null) {
      // Rows shaped like rows while the first answer comes (no spinner, as the benches).
      var one = '<li class="wk-row is-skel" aria-hidden="true"><span class="wk-icon"><span class="sk-disc"></span></span>' +
        '<span class="wk-main"><span class="sk-bar"></span><span class="sk-bar is-short"></span></span></li>';
      return '<p class="vh">Loading what is in progress.</p><ul class="wk-rows">' + one + one + '</ul>';
    }
    if (!rows.length) return '<div class="wk-state"><p>' + esc(EMPTY) + '</p></div>';
    var ready = rows.filter(function (r) { return r.state === "ready"; });
    var working = rows.filter(function (r) { return r.state !== "ready"; });
    var part = function (title, list, id) {
      if (!list.length) return "";
      return '<section class="wk-part" aria-labelledby="' + id + '"><h3 class="wk-ph" id="' + id + '">' +
        esc(title) + '</h3><ul class="wk-rows">' +
        list.map(function (r) { return rowHtml(r, "p"); }).join("") + '</ul></section>';
    };
    return part("Ready to collect", ready, "wk-h-ready") + part("Working", working, "wk-h-working");
  }

  var panel = null, body = null, sayEl = null, opener = null, inBench = null, benchEsc = null;
  var home = null;
  function build() {
    if (panel) return panel;
    panel = document.createElement("section");
    panel.id = "works";
    // The benches' own card (their confirm and herbarium card): framed card leather, the
    // gilt ring with its clasps. No new surface.
    panel.className = "works v2-framed v2-card-leather";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "false");
    panel.setAttribute("aria-labelledby", "works-title");
    panel.hidden = true;
    panel.innerHTML = '<i class="v2-rim" aria-hidden="true"></i>' +
      '<header class="wk-head"><h2 class="wk-title" id="works-title">In progress</h2>' +
      '<button type="button" class="v2-btn is-quiet is-small" data-works-close>Close</button></header>' +
      '<div class="wk-body" id="works-body"></div>' +
      '<p class="wk-said" id="works-said" role="status" aria-live="polite"></p>';
    document.body.appendChild(panel);
    home = document.body;
    body = panel.querySelector("#works-body");
    sayEl = panel.querySelector("#works-said");
    panel.addEventListener("click", onClick);
    panel.addEventListener("keydown", function (e) {
      // Over the table the panel answers its own Esc; inside a bench the bench's stack
      // does (it hears the key first, on its layer, and runs the newest closer).
      if (e.key === "Escape" && !inBench) { e.preventDefault(); e.stopPropagation(); W.close(); }
    });
    return panel;
  }
  function isOpen() { return !!(panel && !panel.hidden); }
  W.isOpen = isOpen;

  function drawPanel() {
    if (!isOpen()) return;
    var had = document.activeElement && panel.contains(document.activeElement) ? document.activeElement : null;
    var hadSel = null;
    if (had) {
      var li = had.closest(".wk-row");
      var attr = ["data-works-collect", "data-works-stop", "data-works-keep", "data-works-stop-yes"]
        .filter(function (a) { return had.hasAttribute(a); })[0];
      if (li && attr) hadSel = { key: li.dataset.worksKey, attr: attr };
    }
    var scroll = body.scrollTop;
    body.innerHTML = listHtml();
    body.scrollTop = scroll;
    sayEl.textContent = said;
    // Keep the keyboard where it was through a redraw; a row that went (collected) leaves
    // focus on the panel's first control rather than on <body>.
    if (hadSel) {
      var again = body.querySelector('.wk-row[data-works-key="' + cssEsc(hadSel.key) + '"] [' + hadSel.attr + ']') ||
                  body.querySelector('.wk-row[data-works-key="' + cssEsc(hadSel.key) + '"] button');
      (again || panel.querySelector("[data-works-close]")).focus();
    }
    place();
  }
  function cssEsc(s) { return window.CSS && CSS.escape ? CSS.escape(s) : String(s).replace(/"/g, '\\"'); }

  // Over the table: a sidebar beside the door that opened it, its top level with the door
  // and pulled up to fit, never off the window. Inside a bench: on the right, above the
  // footer, where the footer's button is. On a phone: the width of the screen.
  function place() {
    if (!isOpen()) return;
    panel.style.left = panel.style.top = panel.style.right = panel.style.bottom = "";
    if (inBench || window.innerWidth <= 760) return;      // the stylesheet places these
    var w = panel.offsetWidth, h = panel.offsetHeight;
    // Beside the column the door is in, clear of its gilt frame and clasps, not beside the
    // door itself: 14px from the door laid the panel over the column's own ring.
    var beside = opener && document.contains(opener) ? (opener.closest(".side") || opener) : null;
    var r = beside ? beside.getBoundingClientRect() : null;
    var o = opener && document.contains(opener) ? opener.getBoundingClientRect() : null;
    var left = r ? r.right + 24 : 16;
    if (left + w > window.innerWidth - 16) left = Math.max(16, window.innerWidth - 16 - w);
    var top = o ? o.top - 20 : 72;
    top = Math.max(16, Math.min(top, window.innerHeight - 16 - h));
    panel.style.left = Math.round(left) + "px";
    panel.style.top = Math.round(top) + "px";
  }
  window.addEventListener("resize", function () { if (isOpen()) place(); });

  W.open = function (anchor) {
    build();
    var layer = anchor && anchor.closest ? anchor.closest(".bench") : null;
    if (layer && layer.hidden) layer = null;
    opener = anchor || document.activeElement;
    // Re-homed on every open: the bench's popover host when a bench opened it, else the page.
    var host = layer ? layer.querySelector(".bench-pops") : null;
    if (host) {
      if (panel.parentNode !== host) host.appendChild(panel);
      inBench = layer;
      panel.classList.add("is-in-bench");
      var core = window.BenchCore && BenchCore.current;
      if (core && core.pushEsc && !benchEsc) {
        benchEsc = function () { W.close(); };
        core.pushEsc(benchEsc);
      }
    } else {
      if (panel.parentNode !== home) home.appendChild(panel);
      inBench = null;
      panel.classList.remove("is-in-bench");
    }
    said = "";
    panel.hidden = false;
    document.querySelectorAll("[data-works-open]").forEach(function (b) { b.setAttribute("aria-expanded", "true"); });
    drawPanel();
    var first = panel.querySelector("[data-works-collect]:not([aria-disabled])") || panel.querySelector("[data-works-close]");
    if (first) first.focus();
    load();
  };
  W.close = function (quiet) {
    if (!isOpen()) return;
    panel.hidden = true;
    asking = null;
    document.querySelectorAll("[data-works-open]").forEach(function (b) { b.setAttribute("aria-expanded", "false"); });
    if (benchEsc) {
      var core = window.BenchCore && BenchCore.current;
      if (core && core.dropEsc) core.dropEsc(benchEsc);
      benchEsc = null;
    }
    inBench = null;
    var back = opener;
    opener = null;
    if (!quiet && back && document.contains(back) && !back.closest("[inert]") && back.focus) back.focus();
  };
  W.toggle = function (anchor) { if (isOpen()) W.close(); else W.open(anchor); };

  // A bench closing with the panel inside it takes the panel with it (it would otherwise sit
  // in a hidden layer and still count as open); a bench opening over the panel left open on
  // the table closes it too, or it would wait at z 34 under the bench, out of reach of the
  // bench's focus trap, and be there again, stale, when the bench closed. One observer on
  // every bench layer's `hidden`, set up once.
  var watching = false;
  function watchLayer() {
    if (watching || typeof MutationObserver !== "function") return;
    watching = true;
    var seen = new MutationObserver(function (changes) {
      changes.forEach(function (ch) {
        var layer = ch.target;
        if (!isOpen()) return;
        if (layer.hidden && inBench === layer) W.close(true);
        else if (!layer.hidden && !inBench) W.close(true);
      });
    });
    document.querySelectorAll(".bench").forEach(function (layer) {
      seen.observe(layer, { attributes: true, attributeFilter: ["hidden"] });
    });
  }

  // --- a shelf's group (contracts §13: `Works.group(host, craft)`) -----------------------
  // The bench's shelf shows only its own craft's rows, under "In progress", with the same
  // words and the same Collect. Drawn from what the server last said, at once (a shelf is
  // redrawn synchronously on every pick); asked for once if nothing has been asked yet.
  function live() {
    groups = groups.filter(function (g) { return document.contains(g.host); });
    return groups;
  }
  function groupHtml(craft) {
    var list = W.rows(craft);
    if (!list.length) return "";
    return '<section class="bs-group wk-group" aria-labelledby="wk-g-' + esc(craft) + '">' +
      '<h3 class="bs-gh" id="wk-g-' + esc(craft) + '">In progress</h3><ul class="wk-rows">' +
      list.map(function (r) { return rowHtml(r, "g"); }).join("") + '</ul></section>';
  }
  W.group = function (host, craft) {
    if (!host) return;
    live();
    if (!groups.some(function (g) { return g.host === host; })) {
      groups.push({ host: host, craft: craft });
      if (!host.dataset.worksWired) {
        host.dataset.worksWired = "1";
        host.addEventListener("click", onClick);
      }
    }
    host.innerHTML = groupHtml(craft);
    if (rows === null && !inflight) load();
  };
  function drawGroups() {
    live().forEach(function (g) {
      var had = document.activeElement && g.host.contains(document.activeElement) ? document.activeElement : null;
      var key = had && had.closest(".wk-row") ? had.closest(".wk-row").dataset.worksKey : null;
      g.host.innerHTML = groupHtml(g.craft);
      if (key) {
        var again = g.host.querySelector('.wk-row[data-works-key="' + cssEsc(key) + '"] button');
        if (again) again.focus();
      }
    });
  }
  function drawAll() { drawPanel(); drawGroups(); }

  // --- Collect and Stop ----------------------------------------------------------------
  function onClick(e) {
    var t = e.target.closest ? e.target.closest("button") : null;
    if (!t) return;
    if (t.hasAttribute("data-works-close")) { W.close(); return; }
    if (t.hasAttribute("data-works-retry")) { error = ""; drawAll(); load(); return; }
    var key;
    if ((key = t.getAttribute("data-works-collect")) != null) {
      if (t.getAttribute("aria-disabled") === "true") {
        // Refused here: the reason is already beside it; bring it forward for a beat.
        var why = t.parentNode.querySelector(".wk-why");
        if (why && !reduced()) { why.classList.remove("is-nudged"); void why.offsetWidth; why.classList.add("is-nudged"); }
        return;
      }
      collect(key, t);
      return;
    }
    if ((key = t.getAttribute("data-works-stop")) != null) { asking = key; drawAll(); focusIn(key, "data-works-keep"); return; }
    if ((key = t.getAttribute("data-works-keep")) != null) { asking = null; drawAll(); focusIn(key, "data-works-stop"); return; }
    if ((key = t.getAttribute("data-works-stop-yes")) != null) { stop(key, t); return; }
  }
  function focusIn(key, attr) {
    var b = document.querySelector('[' + attr + '="' + cssEsc(key) + '"]');
    if (b) b.focus();
  }
  var busy = false;
  function collect(key, btn) {
    if (busy) return;
    busy = true;
    if (btn) btn.setAttribute("aria-busy", "true");
    api("/api/works/collect", { key: key }).then(function (d) {
      busy = false;
      said = d.said || "";
      sound("works.collect");
      adopt(d);
      done("works:collected", { key: key, product: d.product || null, said: said });
    }).catch(function (err) {
      busy = false;
      said = err.message || String(err);
      if (btn) btn.removeAttribute("aria-busy");
      drawAll();
      load();
    });
  }
  function stop(key, btn) {
    if (busy) return;
    busy = true;
    if (btn) btn.setAttribute("aria-busy", "true");
    api("/api/works/cancel", { key: key }).then(function (d) {
      busy = false;
      asking = null;
      said = d.said || "";
      adopt(d);
      done("works:stopped", { key: key, said: said });
    }).catch(function (err) {
      busy = false;
      asking = null;
      said = err.message || String(err);
      drawAll();
      load();
    });
  }
  // What a collect or stop changed is the shelf and the log: a bench open on its shelf
  // listens (`works:collected`) and reloads it; over the table, the table is drawn again from
  // the server, as every other action of the table's ends, so the log line and the pack's
  // new tincture (and its Drink) are there.
  function done(name, detail) {
    try { document.dispatchEvent(new CustomEvent(name, { detail: detail })); } catch (err) { /* old engine */ }
    var bench = window.BenchCore && BenchCore.current;
    // A Collect pressed on a shelf's group has no panel status line to speak in; the
    // bench's own polite line says it (it still said the last roll's "Failure. Some
    // materials were ruined." after a collect, seen live 2026-10-05).
    if (bench && typeof bench.say === "function" && detail && detail.said) bench.say(detail.said);
    if (!bench && typeof render === "function" && typeof getState === "function") {
      getState().then(function (s) { render(s); }).catch(function () { /* resync catches up */ });
    }
  }

  // --- the door in the left column -----------------------------------------------------
  // After the last craft door this build has (Herbalism, Smithing, and Enchanting when lane
  // U1 adds it), so it reads as the fourth of them (UI plan §6.10).
  function door() {
    var side = $id("side-who");
    if (!side || $id("open-works")) return;
    var crafts = side.querySelectorAll("[data-bench-open].door, [data-forge-open].door, [data-enchant-open].door");
    var after = crafts.length ? crafts[crafts.length - 1] : null;
    var b = document.createElement("button");
    b.type = "button";
    b.id = "open-works";
    b.className = "v2-btn door wk-door";
    b.setAttribute("data-works-open", "");
    b.setAttribute("aria-haspopup", "dialog");
    b.setAttribute("aria-controls", "works");
    b.setAttribute("aria-expanded", "false");
    b.innerHTML = '<span>In progress</span><span class="wk-count">' + countHtml(summary) + '</span>';
    if (after) after.parentNode.insertBefore(b, after.nextSibling);
    else side.appendChild(b);
  }

  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-works-open]");
    if (!b) return;
    e.preventDefault();
    W.toggle(b);
  });

  // Every turn's state carries `works` (the door's count) and the clock: the count is drawn
  // from it with no fetch, and the rows are asked again, if anything is showing them, when
  // the clock or the count has moved (07's render hooks run on every draw).
  function onState(s) {
    if (!s) return;
    if (s.works) W.refresh(s.works);
    var minute = s.scene && s.scene.clock_minutes;
    var w = s.works || {};
    W.sync(minute + "|" + (w.ready || 0) + "/" + (w.working || 0));
  }
  // Wired as the script runs, not on DOMContentLoaded: the scripts sit at the foot of the
  // body, so the left column is already there, and 07 primes its render hooks on that same
  // event from a listener added before this file's, so a hook added then would miss the
  // first draw and the door would wait a whole turn for its count.
  door();
  // The benches' layers are in the template above the scripts, so they are all here now.
  watchLayer();
  var boot = window.PATHFINDER_BOOT && window.PATHFINDER_BOOT.state;
  if (boot && boot.works) W.refresh(boot.works);
  if (typeof onRender === "function") onRender(onState);
})();
