// The play table, part 29 (the bench core: what every crafting bench over the table
// shares). Classic script; everything lives inside one IIFE and is reached through
// `window.BenchCore`, so no name here can shadow one of 01-22's (test_s6_panel_shell's rule
// that no top-level function is declared twice across the table's files).
//
// WHY THIS FILE EXISTS (docs/blacksmithing-ui-plan.md §3, lane U1). The herb bench's shell,
// 30-bench-shell.js, was 1,240 lines in which the craft-agnostic machinery (the full-screen
// layer at z 35, opening and closing it, Esc one layer at a time with "Stop and keep what
// you have?" while a game is live, the focus trap and focus return, the keys, the scene
// clock, the footer, the flourish layer and the one-second rule) was tangled with the herbs
// (the satchel, the pot, the nine methods). The forge is the second bench; without this
// split it would copy the 1,240 lines and the two benches would drift apart: two Esc
// behaviours, two focus traps, two clocks, two footers. Each bench mounts its own layer on
// this core with `BenchCore.mount(options)` and keeps only what is its craft's own.
//
// THE SHAPE (prior art: the WAI-ARIA modal dialog pattern and the "stacked modal manager"
// it grows into once dialogs nest). One LIFO stack of closers per layer, so one Esc closes
// one popover and never the whole bench; the trap wraps Tab inside the innermost thing that
// owns the screen (the dice mat, then the layer's open popover, then the layer); focus goes
// back to the opener only if it is still on the page and not inert, else to the bench's
// home button; everything a click or Tab could reach behind the layer is made inert. With
// two benches mounted, each one's document-level handlers act only while THAT bench is
// open, and opening one while another is open is refused: two layers at z 35 would each
// trap Tab and each answer Esc, which is the double-handler bug the pattern exists to stop.
//
// WHAT IT DOES NOT DO. It never computes a number and never knows a craft: the method
// strip, the panels, the roll and the minigame call are the bench's (30 for herbs). The
// providers it touches (Sound, PGMPrefs, BenchGames, Dice3D, 09's clock, 22's verdict
// word) are each looked up at the moment they are needed and guarded there (herbalism
// contracts §5): a bench must be fully usable with none of them.
//
// MOTION. Nothing here loops: no setInterval and no requestAnimationFrame, since the
// flight is one Web Animations run that ends; tests/test_bench_core.py greps for both.

(function () {
  "use strict";

  var $id = function (id) { return document.getElementById(id); };
  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };

  var C = window.BenchCore = { esc: esc, current: null };

  // --- time in words (herb UI plan §8) --------------------------------------------------
  // Prose: "30 minutes", "2 hours 30 minutes", "3 days". Compact, for a stage's info line
  // only: "30m", "2h 30m", "3d".
  C.minutes = function (m, compact) {
    m = Math.max(0, Math.round(Number(m) || 0));
    var d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), n = m % 60;
    var parts = [];
    var unit = function (v, one, many, short) {
      if (!v) return;
      parts.push(compact ? v + short : v + " " + (v === 1 ? one : many));
    };
    unit(d, "day", "days", "d");
    unit(h, "hour", "hours", "h");
    if (!d) unit(n, "minute", "minutes", "m");
    return parts.length ? parts.join(" ") : (compact ? "0m" : "no time");
  };
  // A coarse span for a rack's or satchel's lines: "5 hours", "3 days", "40 minutes".
  C.span = function (m) {
    m = Math.max(0, Math.round(Number(m) || 0));
    if (m >= 2880) return Math.round(m / 1440) + " days";
    if (m >= 1440) return "1 day";
    if (m >= 120) return Math.round(m / 60) + " hours";
    if (m >= 60) return "1 hour";
    return m + (m === 1 ? " minute" : " minutes");
  };
  C.sign = function (v) { v = Number(v) || 0; return (v >= 0 ? "+" : "") + v; };

  // --- providers and preferences, each optional (herb contracts §5) ----------------------
  C.sound = function (name) {
    try { if (window.Sound && typeof Sound.play === "function") Sound.play(name); }
    catch (err) { /* sound is a nicety; never the reason a craft fails */ }
  };
  var STILL = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  // Reduced motion: the OS asked, or the player chose Short flourishes (herb UI plan §6.9).
  C.reduced = function () {
    var short = false;
    try { short = !!(window.PGMPrefs && PGMPrefs.get("flourishes") === "short"); }
    catch (err) { short = false; }
    return !!(STILL && STILL.matches) || short;
  };
  // Steady mode (herb UI plan §9): PGMPrefs when it is here, else this page's own key. One
  // setting for every bench: a player who needs the games held still needs it at the forge
  // as much as at the mortar.
  C.steady = function () {
    try {
      if (window.PGMPrefs && typeof PGMPrefs.get === "function") return !!PGMPrefs.get("steady");
    } catch (err) { /* fall through to the page's own key */ }
    try { return window.localStorage.getItem("pgm.steady") === "1"; } catch (err) { return false; }
  };
  C.setSteady = function (on) {
    try {
      if (window.PGMPrefs && typeof PGMPrefs.set === "function") { PGMPrefs.set("steady", !!on); return; }
    } catch (err) { /* fall through */ }
    try { window.localStorage.setItem("pgm.steady", on ? "1" : "0"); } catch (err) { /* private */ }
  };

  // --- the API ---------------------------------------------------------------------------
  function csrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }
  // GET when there is no body. Errors are the server's own sentence (`{"error": "<plain
  // sentence>"}`), carried with the status so a 409 can be told apart.
  C.api = function (path, body) {
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
  };

  // --- the dice mat -----------------------------------------------------------------------
  // Where the keyboard goes while the table's d20 (Dice3D) is up for a bench's roll.
  C.focusMat = function () {
    setTimeout(function () {
      // The player's own die (the mat's debug toggle) wants its number typed first.
      var own = document.querySelector("#d3d-own.on #d3d-face");
      var go = document.getElementById("d3d-go");
      if (own && go && !go.disabled && go.textContent === "Roll") own.focus();
      else if (go && !go.disabled) go.focus();
    }, 40);
  };

  // --- the scene clock --------------------------------------------------------------------
  // A step of an hour or more turns the table's clock face (09-clock.js) with its own
  // animation, which waits for the dice mat to close before it shows. 09 keeps its own rule
  // (an hour or more) and its own reduced-motion face; the bench only says when.
  C.turnClock = function (before, after) {
    if (after - before >= 60 && typeof clockWhenClear === "function") {
      try { clockWhenClear(before, after, ""); } catch (err) { /* the label still moved */ }
    }
  };

  // --- the flourish layer and the one-second rule (herb UI plan §10) ---------------------
  // No flourish takes input away: each lives on its own fixed element with pointer-events:
  // none (`.bench-fly`, at the verdict layer's height, 66), so it covers nothing a click
  // needs, and any click anywhere completes every flight at once.
  var flying = [];
  // 500ms along a curve: up off the tool, then over to the tile. `el` is the 44px roundel
  // the bench drew for the thing that flies; the offsets below centre it on both ends.
  C.fly = function (el, from, to) {
    el.classList.add("bench-fly");
    document.body.appendChild(el);
    var x0 = from.left + from.width / 2 - 22, y0 = from.top + from.height / 2 - 22;
    var x1 = to.left + 18 - 22 + 8, y1 = to.top + to.height / 2 - 22;
    var lift = Math.min(160, Math.max(60, (y0 - Math.min(y0, y1)) + 80));
    var at = function (p) {
      // A quadratic Bezier through a control point above both ends: the arc of a thrown thing.
      var cx = (x0 + x1) / 2, cy = Math.min(y0, y1) - lift;
      var x = (1 - p) * (1 - p) * x0 + 2 * (1 - p) * p * cx + p * p * x1;
      var y = (1 - p) * (1 - p) * y0 + 2 * (1 - p) * p * cy + p * p * y1;
      var s = p < 0.2 ? 1 + p : 1.2 - 0.5 * p;
      return { transform: "translate(" + x.toFixed(1) + "px," + y.toFixed(1) + "px) scale(" + s.toFixed(3) + ")",
               opacity: p > 0.92 ? (1 - p) / 0.08 : 1, offset: p };
    };
    var frames = [0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 1].map(at);
    var anim = el.animate(frames, { duration: 500, easing: "cubic-bezier(.3,.1,.3,1)", fill: "forwards" });
    flying.push(anim);
    return anim.finished.catch(function () { /* skipped */ }).then(function () {
      flying = flying.filter(function (a) { return a !== anim; });
      el.remove();
    });
  };
  // Any click skips a flourish (the one-second rule): it completes at once.
  document.addEventListener("pointerdown", function () {
    if (!flying.length) return;
    flying.slice().forEach(function (a) { try { a.finish(); } catch (err) { /* */ } });
  }, true);

  // The cast brass word over a bench's tool: the table's own (22-roll-verdict.js
  // `verdictWord`), with its gilt sparks when `sparks` is asked for and motion is allowed.
  // A WebGL stage draws no words, so the word is always the page's, over a stage or a flat
  // stand-in alike; the sparks are for a flat stand-in only (a stage throws its own).
  C.word = function (tool, word, sparks) {
    if (typeof verdictWord !== "function" || !tool) return;
    var r = tool.getBoundingClientRect();
    var at = { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    var still = C.reduced();
    try {
      verdictWord({ good: true, word: word, text: word, sub: "",
                    still: still, ms: still ? 1200 : 1300 }, at, Math.min(r.width, r.height));
    } catch (err) { /* the word is a nicety */ }
    if (sparks && !still && typeof VerdictSparks === "object" && VerdictSparks) {
      try { VerdictSparks.burst("triumph", at.x, at.y, 1300, Math.min(r.width, r.height) * 0.4); } catch (err) { /* */ }
    }
  };
  // A failure dims the stage for 600ms (the CSS animation on `.is-dim`), restarted if it
  // was already dimmed.
  C.dim = function (el) {
    if (!el) return;
    el.classList.remove("is-dim");
    void el.offsetWidth;
    el.classList.add("is-dim");
  };

  // The first gesture unlocks audio (herb contracts §5.3), once for the whole page.
  document.addEventListener("pointerdown", function once() {
    document.removeEventListener("pointerdown", once, true);
    try { if (window.Sound && Sound.unlock) Sound.unlock(); } catch (err) { /* */ }
  }, true);

  // --- a bench's layer ----------------------------------------------------------------------
  // What a layer makes inert while it is open: everything a click or Tab could reach on the
  // table. Not the deathveil (40), which must be able to cover a bench, and not the dice
  // mat, which dice3d.js builds on first use and which this list never names.
  var BEHIND = [".topbar", "#stage", ".modepage", "#tradepanel", "#sheetpanel", ".skip", "#veil",
                "#talktray"];

  // BenchCore.mount(o) wires one bench's layer and returns its handle. Element options are
  // ids in the page (the layer is served in the template, so closing is instant):
  //   layer      the dialog itself (required)            close    its Close button
  //   stage      where 09's clock stands while open      say      the polite status line
  //   pops       the layer's own popovers' host          foot     the footer (clicks)
  //   footIn     the footer's inner row (drawn)          home     the opener focus falls back to
  //   clockId    the footer clock's id (default "<layer>-clock")
  // Behaviour options:
  //   hash       the location hash while open ("#bench"); omitted, the URL is left alone
  //   bodyClass  set on <body> while open
  //   openWith   a selector: a click on a match anywhere opens this bench
  //   openFrom   fn(button) -> the element focus returns to (a panel may shut itself first)
  //   first      selector for what takes focus on open, else Close
  //   quiet      selector for buttons with a sound of their own (no `ui.click` for them)
  //   behind     the selectors made inert (default: the table's)
  //   live       fn() -> true while a minigame runs (Esc then asks before stopping)
  //   keys       fn(event) for the bench's own keys, called only when the player is not
  //              typing, no game is live and no popover is open
  //   opened     fn() after the layer is up and focus is placed
  //   closing    fn() as the layer goes, before the hash is cleared and the table redrawn
  //   footer     fn() -> the footer's parts (see renderFoot)
  C.mount = function (o) {
    var layer = $id(o.layer);
    var h = { open: false, layer: layer, options: o };
    var opener = null, wasInert = [], clockHome = null;
    var escStack = [];
    var stopAsking = false;
    var live = function () { try { return !!(o.live && o.live()); } catch (err) { return false; } };

    h.say = function (text) {
      var s = o.say && $id(o.say);
      if (!s) return;
      s.textContent = "";
      setTimeout(function () { s.textContent = text; }, 30);
    };

    h.focusFirst = function () {
      if (!layer) return;
      var active = (o.first && layer.querySelector(o.first)) || (o.close && $id(o.close));
      if (active) active.focus();
    };

    h.openLayer = function (from) {
      if (!layer || h.open) return;
      // One bench at a time: a second layer at z 35 would trap Tab and answer Esc too.
      if (C.current && C.current !== h) return;
      h.open = true;
      C.current = h;
      opener = from || document.activeElement;
      wasInert = [];
      (o.behind || BEHIND).forEach(function (sel) {
        document.querySelectorAll(sel).forEach(function (el) {
          if (el === layer || layer.contains(el)) return;
          wasInert.push([el, el.inert]);
          el.inert = true;
        });
      });
      // The time-skip clock (09-clock.js) lives in #stage at z-index 8, under the layer. A
      // step of an hour or more turns the scene clock with that same animation, so while a
      // bench is open the clock's element stands on the bench's stage; 09 finds it by id,
      // wherever it is.
      var clock = $id("clockpop");
      var stage = o.stage && $id(o.stage);
      if (clock && stage && clock.parentNode !== stage) {
        clockHome = { parent: clock.parentNode, next: clock.nextSibling };
        stage.appendChild(clock);
      }
      if (o.bodyClass) document.body.classList.add(o.bodyClass);
      layer.hidden = false;
      layer.classList.toggle("bench-still", C.reduced());
      void layer.offsetWidth;            // so the 200ms fade starts from nothing
      layer.classList.add("is-in");
      if (o.hash && location.hash !== o.hash) {
        try { history.replaceState(null, "", o.hash); } catch (err) { /* file: URL */ }
      }
      if (o.opened) o.opened();
      // Focus is the bench's to place as it opens (the herb bench does it between its
      // `open` event and its first load); one that placed none still gets focus inside.
      if (!layer.contains(document.activeElement)) h.focusFirst();
    };

    h.closeLayer = function () {
      if (!h.open) return;
      if (live()) { h.askStop(); return; }       // never drop a live game on the floor
      h.open = false;
      if (C.current === h) C.current = null;
      layer.classList.remove("is-in");
      layer.hidden = true;
      if (o.bodyClass) document.body.classList.remove(o.bodyClass);
      wasInert.forEach(function (p) { p[0].inert = p[1]; });
      wasInert = [];
      var clock = $id("clockpop");
      if (clock && clockHome) {
        clockHome.parent.insertBefore(clock, clockHome.next);
        clockHome = null;
      }
      if (o.closing) o.closing();
      if (o.hash && location.hash === o.hash) {
        try { history.replaceState(null, "", location.pathname + location.search); } catch (err) { /* */ }
      }
      // Time passed and what is carried changed: the table under the layer is drawn again
      // from the server, the same way every other action of the table's ends.
      if (typeof render === "function" && typeof getState === "function") {
        getState().then(function (s) { render(s); }).catch(function () { /* resync catches up */ });
      }
      var back = opener && document.contains(opener) && !opener.closest("[inert]") ? opener
               : (o.home && $id(o.home));
      opener = null;
      if (back && typeof back.focus === "function") back.focus();
    };

    // What may hold focus right now: the dice mat while it shows a roll, else the layer's
    // open modal popover, else the layer. The trap wraps Tab inside it.
    function trapRoot() {
      var mat = document.querySelector("#d3d-mat.on");
      if (mat) return mat;
      var modal = layer.querySelector(".bench-modal:not([hidden])");
      return modal || layer;
    }
    function focusables(root) {
      return Array.prototype.filter.call(root.querySelectorAll(
        "button, [href], input, select, textarea, summary, [tabindex]:not([tabindex='-1'])"),
        function (el) {
          return !el.disabled && el.getClientRects().length && !el.closest("[hidden]") &&
                 el.getAttribute("tabindex") !== "-1";
        });
    }
    document.addEventListener("keydown", function (e) {
      if (!h.open || e.key !== "Tab") return;
      if (document.querySelector("#deathveil.on")) return;    // death owns the screen
      var root = trapRoot();
      var list = focusables(root);
      if (!list.length) return;
      var first = list[0], last = list[list.length - 1];
      var at = document.activeElement;
      if (!root.contains(at)) { e.preventDefault(); first.focus(); return; }
      if (e.shiftKey && at === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && at === last) { e.preventDefault(); first.focus(); }
    }, true);

    // --- Esc, one layer at a time ------------------------------------------------------
    // The popovers (a card, a confirm, the perks, the recipes) push a closer; Esc runs the
    // newest.
    h.pushEsc = function (fn) { escStack.push(fn); };
    h.dropEsc = function (fn) { escStack = escStack.filter(function (f) { return f !== fn; }); };
    h.escOpen = function () { return escStack.length > 0; };

    layer && layer.addEventListener("keydown", function (e) {
      var tag = e.target && e.target.tagName;
      var typing = /^(INPUT|TEXTAREA|SELECT)$/.test(tag);
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        if (escStack.length) { escStack[escStack.length - 1](); return; }
        if (live()) { h.askStop(); return; }
        if (document.querySelector("#d3d-mat.on")) return;
        h.closeLayer();
        return;
      }
      if (o.keys && !typing && !live() && !escStack.length) o.keys(e);
      // The table's own shortcuts listen on the document ("m" opens the map, Esc closes the
      // sheet's details): none of them may act on a table that is behind the bench. While a
      // game is live its keys go through, because the games frame may listen on the document.
      if (!live()) e.stopPropagation();
    });

    // A game running while the player's attention is elsewhere would score time they were
    // not there for: it pauses on blur. It does NOT carry on by itself on focus: the line is
    // "Paused. Press Space to carry on.", and resuming the instant the window came back
    // would start the clock before the player's hand was on the key. The frame waits.
    window.addEventListener("blur", function () {
      if (live() && window.BenchGames && BenchGames.pause) { try { BenchGames.pause(); } catch (err) { /* */ } }
    });

    // --- a confirm inside the layer (taste, stop, delete) --------------------------------
    // A small modal of the layer's own: two buttons, the safe one focused first, Esc is the
    // safe one. Resolves true for the first button.
    h.confirm = function (c) {
      return new Promise(function (done) {
        var pops = $id(o.pops);
        var back = document.activeElement;
        var wrap = document.createElement("div");
        wrap.className = "bench-modal bench-confirm";
        wrap.setAttribute("role", "alertdialog");
        wrap.setAttribute("aria-modal", "true");
        var id = o.layer + "-confirm-" + Date.now();
        wrap.setAttribute("aria-labelledby", id + "-t");
        wrap.setAttribute("aria-describedby", id + "-b");
        wrap.innerHTML = '<div class="bench-scrim"></div><div class="bench-dialog v2-framed v2-card-leather">' +
          '<i class="v2-rim" aria-hidden="true"></i>' +
          '<h3 id="' + id + '-t">' + esc(c.title) + '</h3>' +
          '<p id="' + id + '-b">' + esc(c.body || "") + '</p>' +
          (c.warn ? '<p class="bench-warnline">' + esc(c.warn) + '</p>' : "") +
          '<div class="bench-dialog-acts"><button type="button" class="v2-btn is-quiet" data-no>' +
          esc(c.cancel || "Cancel") + '</button><button type="button" class="v2-btn ' +
          (c.danger ? "is-quiet bench-danger" : "is-go") + '" data-yes>' + esc(c.ok || "OK") +
          '</button></div></div>';
        pops.appendChild(wrap);
        var finish = function (v) {
          h.dropEsc(onEsc);
          wrap.remove();
          if (back && document.contains(back) && back.focus) back.focus();
          done(v);
        };
        var onEsc = function () { finish(false); };
        h.pushEsc(onEsc);
        wrap.querySelector("[data-no]").addEventListener("click", function () { finish(false); });
        wrap.querySelector("[data-yes]").addEventListener("click", function () { finish(true); });
        wrap.querySelector(".bench-scrim").addEventListener("click", function () { finish(false); });
        wrap.querySelector("[data-no]").focus();
      });
    };

    // Esc or Close during a game: "Stop and keep what you have?" (herb UI plan §4.1).
    // Stopping scores the run so far, through BenchGames.stop(), which resolves the game's
    // promise; the bench's own finish then runs as for any ending. Materials are never lost
    // to a stop (revamp plan §3), whichever bench it is.
    h.askStop = function () {
      if (stopAsking || !live()) return;
      stopAsking = true;
      var games = window.BenchGames;
      if (games && games.pause) { try { games.pause(); } catch (err) { /* */ } }
      h.confirm({
        title: "Stop and keep what you have?",
        body: "The run so far is scored. No materials are lost to a stop.",
        ok: "Stop", cancel: "Keep playing",
      }).then(function (yes) {
        stopAsking = false;
        if (!live()) return;
        if (yes) {
          if (games && typeof games.stop === "function") { try { games.stop(); } catch (err) { /* */ } }
        } else if (games && games.resume) {
          try { games.resume(); } catch (err) { /* */ }
        }
      });
    };

    // --- the openers ------------------------------------------------------------------
    if (o.openWith) {
      document.addEventListener("click", function (e) {
        var go = e.target.closest && e.target.closest(o.openWith);
        if (!go) return;
        h.openLayer(o.openFrom ? o.openFrom(go) : go);
      });
    }
    o.close && $id(o.close) && $id(o.close).addEventListener("click", function () { h.closeLayer(); });

    // A press of any plain button answers with `ui.click`; the ones with a sound of their
    // own (the bench names them in `quiet`) do not double it.
    layer && layer.addEventListener("click", function (e) {
      var btn = e.target.closest("button");
      if (btn && !btn.disabled && !(o.quiet && btn.closest(o.quiet))) C.sound("ui.click");
    });

    // --- the footer -----------------------------------------------------------------------
    // The bench says what goes in it (`footer()`): the scene clock's label, its track
    // ({title, level, have, need, mp}) and the track's group name (`trackLabel`), the perk
    // picks it has banked and its own buttons as markup. The core draws the rest the same for every bench: the clock first,
    // the level with a thin mastery line (no background track: a brass line on the leather,
    // the numbers beside it), the picks, a gap, the bench's buttons, and Steady mode last.
    h.renderFoot = function () {
      var foot = o.footIn && $id(o.footIn);
      if (!foot) return;
      var f = (o.footer && o.footer()) || {};
      var t = f.track;
      var prog = "";
      if (t) {
        var need = t.need, have = t.have;
        var frac = need ? Math.max(0, Math.min(1, have / need)) : 1;
        prog = '<span class="bf-level">' + esc(t.title) + ' ' + esc(t.level) + '</span>' +
          '<span class="bf-line" aria-hidden="true"><i style="transform:scaleX(' + frac.toFixed(3) + ')"></i></span>' +
          '<span class="bf-mp">' + (need ? esc(have) + " / " + esc(need) : esc(t.mp) + " mastery") + '</span>';
      }
      var picks = f.picks ? '<button type="button" class="bf-btn bf-perks" data-bench-perks>' +
        (f.picks === 1 ? "1 perk to pick" : f.picks + " perks to pick") + '</button>' : "";
      var steady = C.steady();
      foot.innerHTML =
        '<span class="bf-clock" id="' + esc(o.clockId || o.layer + "-clock") + '">' + esc(f.clock || "") + '</span>' +
        '<span class="bf-track" role="group" aria-label="' + esc(f.trackLabel || "") + '">' + prog + '</span>' + picks +
        '<span class="bf-gap"></span>' + (f.buttons || "") +
        '<button type="button" class="bf-btn bf-steady" role="switch" aria-checked="' + steady +
        '" data-bench-steady>Steady mode<span class="bf-switch" aria-hidden="true"></span></button>';
    };
    var footEl = o.foot && $id(o.foot);
    if (footEl) {
      footEl.addEventListener("click", function (e) {
        if (!e.target.closest("[data-bench-steady]")) return;
        C.setSteady(!C.steady());
        h.renderFoot();
        var s = footEl.querySelector("[data-bench-steady]");
        if (s) s.focus();
        h.say(C.steady() ? "Steady mode on." : "Steady mode off.");
      });
    }

    // Reduced motion can change while a bench is open (the OS setting, or Settings).
    var still = function () { if (layer) layer.classList.toggle("bench-still", C.reduced()); };
    if (STILL && STILL.addEventListener) STILL.addEventListener("change", still);
    try {
      if (window.PGMPrefs && typeof PGMPrefs.on === "function") {
        PGMPrefs.on("flourishes", still);
        PGMPrefs.on("steady", h.renderFoot);
      }
    } catch (err) { /* prefs are optional */ }

    return h;
  };
})();
