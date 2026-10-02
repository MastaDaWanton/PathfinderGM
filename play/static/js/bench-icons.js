/* The herbalism bench's icons (docs/herbalism-contracts.md §5.4).
 *
 * `BenchIcons.el(name, {size, tier, label})` returns an element for a part id (leaf,
 * root, gland ...), a method id (grind, brew ...), a state id (dried, ground ...), a
 * product form (tincture, salve ...), or one of `lock`, `recipe`, `taste`, `study`,
 * `reagent`. `BenchIcons.html(...)` is the same element as markup.
 *
 * THE ART. The owner approved the game-icons.net set (CC BY 3.0, credited in the app's
 * About and the manual): 46 SVGs in play/static/img/icons/<name>.svg, each one black glyph
 * on a transparent ground. Each is drawn as a CSS `mask-image` over the `--gilt` brass and
 * its grain, with a drop-shadow pair matching `--engraved`, so one set reads as struck
 * brass at any size (UI plan §3). The names are a static list here, so the page never asks
 * the server for a file that may not exist: a probe per name (`new Image()`) would have put
 * a 404 in the console for every name without art.
 *
 * THE STAMP. The table also hands over `window.BENCH_ICON_URLS`, one `{% asset %}` per name,
 * which stamps "?v=<hash>" on a file it found. Where that map is present, its stamped URL is
 * used (the Electron disk cache outlives reinstalls, CLAUDE.md), and a name it could not
 * stamp is not in this build, so it stays a roundel rather than a broken mask. Pages
 * without the map (the lanes' harnesses) use the plain /static/ path.
 *
 * THE FALLBACK, for an unknown name only: a lettered brass roundel, the first letter in
 * Cinzel cut into a `--gilt` disc. There is no hand-drawn icon in this file (the skill's
 * rule; tests/test_bench_ui.py greps for SVG path data).
 *
 * Tiles are told apart by name, rarity rim, state badge and count (UI plan §6.2), never by
 * the icon alone, so every element is aria-hidden: the words beside it carry it.
 */
(function () {
  "use strict";

  // The 46 names with art (lead, 2026-10-02; ui/table-v2 b4ea7cf).
  var NAMES = [
    // parts
    "leaf", "flower", "root", "bark", "berry", "seed", "sap", "resin", "fungus", "gland",
    "organ", "bone", "horn", "feather", "scale", "eye", "shell", "oil", "wax", "mineral",
    "liquid",
    // methods
    "grind", "mix", "brew", "dry", "reduce", "extract", "infuse", "steep", "neutralize",
    // states
    "dried", "ground", "neutralised", "steeping",
    // misc
    "lock", "recipe", "taste", "study", "reagent",
    // forms
    "infusion", "decoction", "tincture", "acetum", "poultice", "salve", "cream",
  ];
  // Forms and kinds with no glyph of their own, onto the nearest one (the lead's mapping).
  var ALIAS = {
    "balm": "salve", "salve-base": "salve", "infused-oil": "oil", "powder": "ground",
    "reduction": "decoction", "monster part": "organ", "neutralized": "neutralised",
    "herb": "leaf",
  };
  var HAS = {};
  NAMES.forEach(function (n) { HAS[n] = true; });

  // The rarity rim, hairline to gilt (UI plan §6.2). Metal and weight, never hue (§3).
  var RIMS = { common: "r0", uncommon: "r1", rare: "r2", exotic: "r3", legendary: "r4" };

  // /static/ as this file was served from, so the path holds under runserver and in the
  // packaged app alike (never a path anchored on where the code sits, CLAUDE.md).
  var BASE = (function () {
    var me = document.currentScript && document.currentScript.src;
    var at = me ? me.indexOf("/js/bench-icons.js") : -1;
    return at > 0 ? me.slice(0, at) + "/img/icons/" : "/static/img/icons/";
  })();

  function resolve(name) {
    var key = String(name || "").toLowerCase();
    if (HAS[key]) return key;
    if (ALIAS[key] && HAS[ALIAS[key]]) return ALIAS[key];
    return "";
  }

  function urlFor(key) {
    if (!key) return "";
    var map = window.BENCH_ICON_URLS;
    if (map && typeof map === "object") {
      var u = map[key];
      return typeof u === "string" && u.indexOf("?v=") > 0 ? u : "";
    }
    return BASE + key + ".svg";
  }

  function el(name, opts) {
    opts = opts || {};
    var key = resolve(name);
    var span = document.createElement("span");
    span.className = "bicon" + (opts.tier && RIMS[opts.tier] ? " " + RIMS[opts.tier] : "");
    span.setAttribute("aria-hidden", "true");
    span.dataset.icon = key || String(name || "");
    if (opts.size) span.style.setProperty("--bi", Math.round(opts.size) + "px");
    var url = urlFor(key);
    if (url) {
      span.classList.add("is-mask");
      // A custom property, read by bench.css's `mask-image: var(--bi-mask)`. Quoted, so no
      // character of a URL can end the url() early.
      span.style.setProperty("--bi-mask", 'url("' + url.replace(/"/g, "%22") + '")');
    }
    // The letter is always there for the roundel; bench.css hides it under a mask.
    var letter = document.createElement("span");
    letter.className = "bicon-l";
    letter.textContent = (opts.label || name || "?").toString().charAt(0).toUpperCase();
    span.appendChild(letter);
    return span;
  }

  function html(name, opts) { return el(name, opts).outerHTML; }

  window.BenchIcons = { el: el, html: html, names: NAMES.slice(),
                        has: function (n) { return !!urlFor(resolve(n)); } };
})();
