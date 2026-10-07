/* What a skill does in this game, shown beside its name. `window.SkillHelp`.
 *
 * The owner, 2026-10-06: "in the character creator you should be able to hover on the
 * skills when choosing skill ranks to see what the skill affects in game." Loaded by the
 * forge (home.html) and the table (the level-up rank picker on the Class tab); the words
 * are the server's (content/rules/skills-explained.json via rules/skillhelp.py), so the
 * page never claims a use the code does not make.
 *
 *   SkillHelp.use(getter)      -> where the words come from: () => {general, skills}
 *   SkillHelp.row(id, inner)   -> a skill row: the trigger, its "?" and its description
 *   SkillHelp.info(id)         -> the "?" and the description alone, for a row that is
 *                                 its own [data-skillhelp] wrapper
 *   SkillHelp.descId(id)       -> the id of the screen-reader description, for
 *                                 aria-describedby on the row's own controls
 *
 * Hover alone fails keyboard and touch players (Inclusive Components, "Tooltips &
 * Toggletips", Pickering 2016), so the same card opens three ways: the pointer over the
 * row, keyboard focus on any control in the row, and a tap on the row's "?" (a toggletip,
 * pinned until tapped again, Escape, or a tap elsewhere). WCAG 2.1 SC 1.4.13 asks custom
 * hover content to be dismissible (Escape), hoverable (the pointer may cross onto the card
 * without it vanishing) and persistent; all three are kept below. A screen reader hears
 * the words through aria-describedby on the row's controls, which is why the floating
 * card itself is aria-hidden: read twice is read once too many. The "?" is out of the
 * tab order (tabindex -1): a keyboard player already gets the card on the checkbox or the
 * +/- button, and 35 extra stops would make the list a chore to cross.
 *
 * Not the title attribute: a browser tooltip never shows on touch or keyboard focus, and
 * SC 1.4.13 leaves it to the browser, which is to say to nobody.
 *
 * No third-party code, as everywhere in play/static/js.
 */
(function () {
  var getter = function () { return null; };
  var card = null, owner = null, pinned = false, hideTimer = null;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function data() { try { return getter() || null; } catch (e) { return null; } }
  function entry(id) {
    var d = data();
    return d && d.skills ? d.skills[String(id || "").toLowerCase()] || null : null;
  }
  function slug(id) { return "skh-" + String(id).toLowerCase().replace(/[^a-z0-9]+/g, "-"); }

  var ABILITY = { STR: "Strength", DEX: "Dexterity", CON: "Constitution",
                  INT: "Intelligence", WIS: "Wisdom", CHA: "Charisma" };
  // "Wisdom. Trained only: you need a rank before you can try it." The forge's list marks
  // neither, so the card says both.
  function keyLine(e) {
    var ab = ABILITY[e.ability] || "";
    var s = ab ? "Uses " + ab + "." : "";
    if (e.trained_only) s += (s ? " " : "") + "Trained only: you need a rank before you can try it.";
    return s;
  }

  // The same words as the card, as one paragraph for a screen reader.
  function plain(id) {
    var e = entry(id);
    if (!e) return "";
    var out = [e.book];
    if (keyLine(e)) out.push(keyLine(e));
    if (e.uses && e.uses.length) out.push("In this game: " + e.uses.join(" "));
    else out.push("In this game: nothing rolls it on its own yet; only a check the GM asks for.");
    if (e.not_yet) out.push("Not in play yet: " + e.not_yet);
    return out.join(" ");
  }

  // The "?" and the screen-reader description, for a row that draws its own wrapper
  // (the level-up picker's <dl>, where a row may hold only <dt> and <dd>).
  function info(id) {
    var e = entry(id);
    if (!e) return "";
    return '<button type="button" class="skh-info" tabindex="-1" data-skillinfo="' + esc(id) +
      '" aria-label="What ' + esc(e.name) + ' does in this game" aria-describedby="' +
      slug(id) + '">?</button><span class="skh-vh" id="' + slug(id) + '">' +
      esc(plain(id)) + "</span>";
  }

  function row(id, inner) {
    if (!entry(id)) return "<div>" + inner + "</div>";
    return '<div class="skh-row" data-skillhelp="' + esc(id) + '">' + inner + info(id) + "</div>";
  }

  function ensureCard() {
    if (card) return card;
    card = document.createElement("div");
    card.id = "skillcard";
    card.setAttribute("aria-hidden", "true");
    card.addEventListener("mouseenter", function () { clearTimeout(hideTimer); });
    card.addEventListener("mouseleave", function () { if (!pinned) later(); });
    document.body.appendChild(card);
    return card;
  }

  function show(el, pin) {
    var id = el.getAttribute("data-skillhelp");
    var e = entry(id);
    if (!e) return;
    clearTimeout(hideTimer);
    var c = ensureCard();
    var uses = e.uses && e.uses.length
      ? "<ul>" + e.uses.map(function (u) { return "<li>" + esc(u) + "</li>"; }).join("") + "</ul>"
      : '<p class="skh-none">Nothing rolls it on its own yet. It counts only when the GM ' +
        "asks for a check.</p>";
    var d = data() || {};
    c.innerHTML = "<h4>" + esc(e.name) + "</h4>" +
      '<p class="skh-book">' + esc(e.book) + "</p>" +
      (keyLine(e) ? '<p class="skh-key">' + esc(keyLine(e)) + "</p>" : "") +
      '<p class="skh-head">In this game</p>' + uses +
      (e.not_yet ? '<p class="skh-not"><b>Not in play yet:</b> ' + esc(e.not_yet) + "</p>" : "") +
      (d.general ? '<p class="skh-gen">' + esc(d.general) + "</p>" : "");
    c.classList.add("on");
    owner = el;
    pinned = !!pin;
    place(el);
  }

  // Beside the row, kept on screen: below it if there is room, else above.
  function place(el) {
    var r = el.getBoundingClientRect();
    var w = Math.min(400, innerWidth - 16);
    card.style.width = w + "px";
    card.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.left)) + "px";
    var h = card.offsetHeight;
    var top = r.bottom + 6;
    if (top + h > innerHeight - 8) top = Math.max(8, r.top - h - 6);
    card.style.top = top + "px";
  }

  function hide() {
    clearTimeout(hideTimer);
    if (card) card.classList.remove("on");
    owner = null;
    pinned = false;
  }
  // Long enough to cross the gap onto the card (SC 1.4.13 "hoverable").
  function later() { clearTimeout(hideTimer); hideTimer = setTimeout(hide, 220); }

  document.addEventListener("mouseover", function (ev) {
    var el = ev.target.closest && ev.target.closest("[data-skillhelp]");
    if (el && el !== owner && !pinned) show(el, false);
    else if (el && el === owner) clearTimeout(hideTimer);
  });
  document.addEventListener("mouseout", function (ev) {
    var el = ev.target.closest && ev.target.closest("[data-skillhelp]");
    if (!el || el !== owner || pinned) return;
    if (ev.relatedTarget && (el.contains(ev.relatedTarget) ||
        (card && card.contains(ev.relatedTarget)))) return;
    later();
  });
  document.addEventListener("focusin", function (ev) {
    var el = ev.target.closest && ev.target.closest("[data-skillhelp]");
    if (el) show(el, false);
    else if (owner && !pinned) hide();
  });
  document.addEventListener("focusout", function (ev) {
    var el = ev.target.closest && ev.target.closest("[data-skillhelp]");
    if (el && el === owner && !pinned &&
        !(ev.relatedTarget && el.contains(ev.relatedTarget))) later();
  });
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest("[data-skillinfo]");
    if (b) {
      var el = b.closest("[data-skillhelp]");
      if (pinned && owner === el) hide(); else if (el) show(el, true);
      return;
    }
    if (pinned && !(card && card.contains(ev.target))) hide();
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && card && card.classList.contains("on")) hide();
  });
  // A fixed card over a list that scrolled away would point at nothing.
  document.addEventListener("scroll", function () { if (owner) hide(); }, true);
  // A repaint replaces the row under the card (every +/- redraws the picker).
  // The root, not <body>: the table loads this file in <head>, before there is a body.
  new MutationObserver(function () {
    if (owner && !document.documentElement.contains(owner)) hide();
  }).observe(document.documentElement, { childList: true, subtree: true });

  window.SkillHelp = {
    use: function (fn) { getter = fn; },
    row: row,
    info: info,
    descId: function (id) { return entry(id) ? slug(id) : ""; },
    plain: plain,
  };
})();
