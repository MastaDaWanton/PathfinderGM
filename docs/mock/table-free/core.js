// Book and ledger: shared state, the two characters, icons, the bar, the clock, the views.
// Static. It reads window.MOCK_DATA (data.js, generated from the engine, the fixtures and two
// recordings) and answers clicks with canned lines that begin "Mock.". Nothing here reaches a
// server or a model.
"use strict";

const D = window.MOCK_DATA;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const signed = n => (n >= 0 ? "+" : "") + n;
const upper = s => (s ? s[0].toUpperCase() + s.slice(1) : s);
const tidy = s => String(s || "");          // engine text is shown as written

// --- Money: the world's coins (rules.goods.coinage, coined for Zhilvarnia) -----------------------
// The long names are "Khy'vyr gold piece" and so on; a row of prices says the metal only, and
// the full name is one hover away. Prices are the Core tables' gold, as the engine keeps them.
const COIN = Object.fromEntries(D.coins.map(c => [c[0], c]));
function money(gp) {
  let cp = Math.round(gp * 100);
  if (cp <= 0) return "free";
  const parts = [];
  for (const [id, per, word] of [["gp", 100, "gold"], ["sp", 10, "silver"], ["cp", 1, "copper"]]) {
    const n = Math.floor(cp / per);
    if (n) { parts.push(`${n} ${word}`); cp -= n * per; }
  }
  return parts.join(" ");
}

// --- The two characters ----------------------------------------------------------------------------
// Numbers come from full_sheet() in data.js. What is added here is what a mock needs to be
// clicked: what each carries (the fixture's own weapons, armour and outfit, then an EXAMPLE
// load of forty-odd things at the Core tables' real prices, to test the gear screen at the size
// the owner said hurts), a purse, and the wizard's prepared list (casting.ensure_prepared).
const shelfOf = name => {
  const n = name.toLowerCase();
  if (/rapier|dagger|staff|sword|crossbow|bow\b|sling|club|axe|sap|whip/.test(n)) return "weapons";
  if (/armour|armor|shield|buckler/.test(n)) return "armour";
  if (/bread|cheese|meat|ale|wine|ration|meal|antitoxin|potion|oil|alchemist|sunrod|water\b/.test(n))
    return "consumables";
  if (/ring|garnet|coin|pearl|necklace|papers|pendant|signet/.test(n)) return "valuables";
  return "gear";
};
function item(name, extra = {}) {
  const shelf = extra.shelf || shelfOf(name);
  const known = [...D.counters.market, ...D.counters.smithy, ...D.counters.tavern,
                 ...D.counters.weapons].find(g => g[1].toLowerCase() === name.toLowerCase());
  return { id: "i" + Math.random().toString(36).slice(2, 8), name, shelf, qty: 1, where: "",
           value: known ? known[2] : 0, unit: known ? known[5] : "", per: known ? known[4] : 1,
           ex: true, ...extra };
}
const kesstLoad = () => [
  item("rapier", { where: "main hand", ex: false, slot: "hand" }),
  item("dagger", { ex: false }),
  item("leather armour", { where: "body", ex: false, slot: "armour", value: 10 }),
  item("traveler's outfit", { where: "clothing", ex: false, slot: "clothes" }),
  item("dagger", { note: "a second, for throwing" }),
  item("sap"), item("Sling"), item("sling bullets", { shelf: "weapons", qty: 10, value: 0.01 }),
  item("backpack", { where: "back", slot: "back" }), item("thieves' tools"),
  item("bedroll"), item("blanket"), item("waterskin", { qty: 2 }), item("flint and steel"),
  item("silk rope"), item("hemp rope"), item("torch", { qty: 4 }), item("hooded lantern"),
  item("flask of oil", { qty: 3 }), item("chalk", { qty: 5 }), item("sack", { qty: 2 }),
  item("grappling hook"), item("crowbar"), item("small steel mirror"), item("signal whistle"),
  item("candle", { qty: 6 }), item("ink and paper"), item("caltrops"), item("pitons", { qty: 6 }),
  item("hammer"), item("whetstone"), item("manacles"), item("cold-weather outfit"),
  item("trail rations", { qty: 4 }), item("loaf of bread", { qty: 2 }),
  item("hunk of cheese"), item("chunk of meat"), item("sunrod", { qty: 2 }),
  item("antitoxin"), item("alchemist's fire", { qty: 2 }),
  item("satchel of trade-papers", { shelf: "valuables", value: 0,
         note: "the recording's own find: taken from the man at the bar" }),
  item("silver signet ring", { shelf: "valuables", value: 25 }),
  item("uncut garnet", { shelf: "valuables", value: 50, qty: 2 }),
];
const ysoldeLoad = () => [
  item("quarterstaff", { where: "both hands", ex: false, slot: "hand", shelf: "weapons" }),
  item("dagger", { ex: false }),
  item("scholar's outfit", { where: "clothing", ex: false, slot: "clothes", shelf: "gear" }),
  item("spellbook", { shelf: "gear", ex: false, note: "twenty cantrips and six first-level spells" }),
  item("spell component pouch", { where: "belt", slot: "belt" }),
  item("backpack", { where: "back", slot: "back" }), item("ink and paper"), item("candle", { qty: 10 }),
  item("bedroll"), item("waterskin"), item("trail rations", { qty: 3 }), item("chalk", { qty: 3 }),
];
const CHARS = {
  kesst: { sheet: D.sheets.kesst, gear: kesstLoad(), purse: 1437, portrait: "",
           background: "Thief-taker", caster: null },
  ysolde: { sheet: D.sheets.ysolde, gear: ysoldeLoad(), purse: 812, portrait: "",
            background: "None chosen",
            caster: { cl: 1, dcBase: 13, prepared: { 0: ["acid-splash", "arcane-mark", "bleed"],
                                                     1: ["burning-hands", "magic-missile"] },
                      spent: { 1: 0 } } },
};

// --- Icons: the repo's own game-icons.net SVGs, inlined so currentColor tints them ------------------
// The app inlines by fetch rather than a CSS mask, because a mask needs the server to call the
// file image/svg+xml, and on Windows that answer comes from the registry. The same here.
const ICON_BASE = { items: "../../../play/static/icons/items/",
                    spells: "../../../play/static/icons/spells/" };
const SVG = new Map();
const glyph = (name, set = "items", cls = "") =>
  `<i class="gi${cls ? " " + cls : ""}" data-icon="${esc(name)}" data-set="${set}" aria-hidden="true"></i>`;
function paintIcons(root = document) {
  root.querySelectorAll("i.gi[data-icon]").forEach(i => {
    if (i.firstChild) return;
    const key = i.dataset.set + "/" + i.dataset.icon;
    const have = SVG.get(key);
    if (typeof have === "string") { i.innerHTML = have; return; }
    if (have === null) return;
    SVG.set(key, null);
    fetch(ICON_BASE[i.dataset.set] + encodeURIComponent(i.dataset.icon) + ".svg")
      .then(r => (r.ok ? r.text() : ""))
      .then(text => {
        const svg = text.includes("<svg") ? text : "";
        SVG.set(key, svg);
        $$(`i.gi[data-set="${i.dataset.set}"][data-icon="${CSS.escape(i.dataset.icon)}"]`)
          .forEach(x => { if (!x.firstChild) x.innerHTML = svg; });
      })
      .catch(() => SVG.set(key, ""));
  });
}
// The app's own table (06-trade-and-page.js TRADE_ITEM_ICONS), trimmed to what is carried here.
const ITEM_ICONS = [
  [/crossbow/, "carl-olsen-crossbow"], [/bullets?|arrows?|bolts?/, "lorc-arrow-cluster"],
  [/bow\b/, "delapouite-bow-arrow"], [/axe\b/, "lorc-battle-axe"],
  [/quarterstaff|\bstaff\b/, "delapouite-bo"], [/dagger|knife/, "lorc-plain-dagger"],
  [/club|\bsap\b/, "delapouite-wood-club"], [/sling/, "delapouite-sling"], [/whip/, "lorc-whip"],
  [/rapier|sword/, "lorc-broadsword"],
  [/shield|buckler/, "willdabeast-round-shield"], [/leather|padded|hide|studded/, "delapouite-leather-armor"],
  [/chain|mail/, "lorc-mail-shirt"],
  [/rope/, "delapouite-rope-coil"], [/torch/, "delapouite-torch"], [/lantern|lamp|sunrod/, "lorc-lantern-flame"],
  [/tent/, "delapouite-camping-tent"], [/backpack/, "delapouite-backpack"],
  [/bedroll|blanket/, "delapouite-sleeping-bag"], [/waterskin/, "delapouite-water-flask"],
  [/flint/, "delapouite-flint-spark"], [/healer/, "delapouite-first-aid-kit"],
  [/grappling|climber/, "lorc-grapple"], [/crowbar/, "delapouite-crowbar"],
  [/hammer|piton/, "lorc-claw-hammer"], [/sack|pouch|satchel/, "lorc-swap-bag"],
  [/mirror/, "lorc-mirror-mirror"], [/thieves|lockpick/, "delapouite-lockpicks"],
  [/holy symbol/, "lorc-holy-symbol"], [/manacle/, "lorc-manacles"], [/candle/, "lorc-candle-light"],
  [/ink|paper|quill|spellbook/, "lorc-quill-ink"], [/whistle/, "delapouite-whistle"],
  [/net\b/, "lorc-fishing-net"], [/outfit|clothes/, "delapouite-clothes"], [/caltrop/, "delapouite-caltrops"],
  [/bread|loaf/, "delapouite-bread"], [/cheese/, "lorc-cheese-wedge"], [/meat/, "lorc-meat"],
  [/ale\b|beer/, "lorc-beer-stein"], [/wine/, "delapouite-wine-bottle"], [/meal|ration/, "delapouite-hot-meal"],
  [/alchemist|oil|antitoxin|vial/, "sbed-vial"], [/potion/, "caro-asercion-round-potion"],
  [/ring|signet/, "delapouite-ring"], [/garnet|gem/, "lorc-gems"], [/coin/, "delapouite-two-coins"],
  [/whetstone|shovel/, "lorc-metal-bar"], [/chalk/, "lorc-metal-bar"],
];
const SHELF_ICON = { weapons: "lorc-broadsword", armour: "lorc-breastplate", gear: "lorc-knapsack",
                     consumables: "lorc-bubbling-flask", valuables: "lorc-gems" };
function iconFor(name, shelf) {
  const n = String(name).toLowerCase();
  const hit = ITEM_ICONS.find(([re]) => re.test(n));
  return hit ? hit[1] : (SHELF_ICON[shelf] || "lorc-knapsack");
}
// The spell icons, by the app's own picks (05-sheet.js SPELL_ICONS).
const SPELL_ICON = {
  "acid-splash": "lorc-acid-blob", "arcane-mark": "lorc-star-swirl", "bleed": "lorc-bleeding-wound",
  "dancing-lights": "delapouite-bolt-spell-cast", "daze": "delapouite-knocked-out-stars",
  "detect-magic": "lorc-third-eye", "detect-poison": "lorc-crystal-ball",
  "disrupt-undead": "lorc-broken-skull", "flare": "delapouite-bolt-spell-cast",
  "ghost-sound": "lorc-duality-mask", "light": "lorc-candle-light", "mage-hand": "lorc-magic-palm",
  "mending": "lorc-potion-ball", "message": "lorc-potion-ball", "open-close": "lorc-potion-ball",
  "prestidigitation": "delapouite-magick-trick", "ray-of-frost": "lorc-ice-bolt",
  "read-magic": "lorc-crystal-ball", "resistance": "lorc-magic-shield",
  "touch-of-fatigue": "lorc-dread-skull", "burning-hands": "lorc-glowing-hands",
  "magic-missile": "lorc-missile-swarm", "color-spray": "lorc-rainbow-star", "sleep": "lorc-sleepy",
  "mage-armor": "lorc-energy-shield", "shield": "lorc-shield-reflect",
};

// --- State --------------------------------------------------------------------------------------------
const S = {
  char: "kesst", mode: "table", scene: "explore",
  place: D.start, wanted: false,
  minutes: 8 * 60 + 10, day: 1,
  beats: [], attached: null, talk: null, fight: null,
  counter: null, basket: [],
  shelf: "all", filter: "", sort: "shelf",
};
const me = () => CHARS[S.char];
const sheet = () => me().sheet;
const isCaster = () => !!me().caster;

// --- Settings: light and text size, kept per viewer ----------------------------------------------------
function store(k, v) { try { localStorage.setItem("pfgm.mockfree." + k, v); } catch (e) { /* private */ } }
function recall(k) { try { return localStorage.getItem("pfgm.mockfree." + k); } catch (e) { return null; } }
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  $$("[data-theme-set]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.themeSet === t)));
  store("theme", t);
}
function setSize(s) {
  document.documentElement.dataset.size = s;
  $$("[data-size-set]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.sizeSet === s)));
  store("size", s);
}

// --- The clock ------------------------------------------------------------------------------------------
const hhmm = m => `${String(Math.floor(m / 60) % 24).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
const partOf = m => D.day_parts[Math.floor(m / 60) % 24];
// The lamp over the page, by the engine's own words for the hour.
function lampFor(m) {
  const h = Math.floor(m / 60) % 24;
  if (h >= 5 && h < 8) return "dawn";
  if (h >= 8 && h < 17) return "day";
  if (h >= 17 && h < 21) return "dusk";
  return "night";
}
function renderClock() {
  $("#clock-time").textContent = hhmm(S.minutes);
  $("#clock-day").innerHTML = `<span class="dp">${esc(upper(partOf(S.minutes)))}, </span>day ${S.day}`;
  document.body.dataset.daypart = lampFor(S.minutes);
}
// Moves the clock and returns the ledger slip that records it. An hour or more pops the dial,
// which answers the action and then gets out of the way; the slip keeps the record, so a player
// who looked away loses nothing when it closes.
function advance(minutes, words) {
  const from = { m: S.minutes, d: S.day };
  let total = S.minutes + minutes;
  S.day += Math.floor(total / 1440);
  S.minutes = total % 1440;
  renderClock();
  if (minutes >= 60) clockPop(from, minutes, words);
  return { type: "time", from: `${hhmm(from.m)}${from.d !== S.day ? `, day ${from.d}` : ""}`,
           to: `${hhmm(S.minutes)}${from.d !== S.day ? `, day ${S.day}` : ""}`, words };
}
let clockTimer = 0;
function clockPop(from, minutes, words) {
  const pop = $("#clockpop");
  const turns = minutes / 720;                      // a turn of the hand is twelve hours
  const start = ((from.m % 720) / 720) * 360;
  const ticks = Array.from({ length: 12 }, (_, i) => {
    const a = i * 30 * Math.PI / 180;
    return `<line class="tick" x1="${75 + Math.sin(a) * 58}" y1="${75 - Math.cos(a) * 58}"
      x2="${75 + Math.sin(a) * 66}" y2="${75 - Math.cos(a) * 66}"/>`;
  }).join("");
  const days = Math.floor((from.m + minutes) / 1440);
  pop.innerHTML = `<div class="clockcard" role="img" aria-label="Time passes: ${esc(words)}">
    <svg class="dial" viewBox="0 0 150 150" aria-hidden="true">
      <circle class="face-c" cx="75" cy="75" r="70"/>${ticks}
      <line class="hand" x1="75" y1="75" x2="75" y2="24" style="transform: rotate(${start}deg)"/>
      <circle class="hub" cx="75" cy="75" r="5"/></svg>
    <b>${hhmm(S.minutes)}</b>
    <span class="days">${days ? `${days} day${days > 1 ? "s" : ""} later, day ${S.day}` :
      upper(partOf(S.minutes))}</span>
    <p>${esc(upper(words))}</p></div>`;
  pop.hidden = false;
  const hand = $(".hand", pop);
  // The hand sweeps the hours that passed, at most three turns so a five-day road does not
  // blur into a spinner; the day count says the rest.
  const sweep = Math.min(turns, 3) * 360 + ((minutes % 720) / 720) * 360 * (turns > 3 ? 1 : 0);
  hand.animate([{ transform: `rotate(${start}deg)` },
                { transform: `rotate(${start + (turns > 3 ? sweep : turns * 360)}deg)` }],
               { duration: 1400, easing: "cubic-bezier(.3,.1,.2,1)", fill: "forwards" });
  clearTimeout(clockTimer);
  clockTimer = setTimeout(() => { pop.hidden = true; }, 3400);
}
$("#clockpop").addEventListener("click", () => { $("#clockpop").hidden = true; });

// --- The bar --------------------------------------------------------------------------------------------
const WHY = new Map();       // the reasons behind every number on screen, by key
function whyKey(label, block, note = "") {
  const k = "w" + WHY.size;
  WHY.set(k, { label, block, note });
  return k;
}
function renderBar() {
  const s = sheet(), id = s.identity;
  const face = $("#bar-face");
  face.textContent = me().portrait ? "" : id.name[0];
  face.style.backgroundImage = me().portrait ? `url(${me().portrait})` : "";
  $("#bar-name").textContent = id.name;
  $("#bar-line").textContent = `${id.class}, ${id.heritage ? id.heritage + " " : ""}${id.race}`;
  const hp = s.hp, pct = Math.max(0, hp.current) / hp.max * 100;
  const conds = s.conditions.length ? s.conditions.join(", ") : "";
  $("#vitals").innerHTML = `
    <button type="button" class="vital life" data-why="${whyKey("Hit points", { total: hp.max, terms: s.hp_terms }, `${hp.current} of ${hp.max} now.`)}">
      <span class="k">Life</span>
      <span class="v">${hp.current}<small>of ${hp.max}</small></span>
      <span class="lifebar${pct <= 35 ? " low" : ""}"><i style="width:${pct}%"></i></span></button>
    <button type="button" class="vital ac" data-why="${whyKey("Armour class", s.ac)}">
      <span class="k">AC</span><span class="v">${s.ac.total}</span></button>
    <button type="button" class="vital touch" data-why="${whyKey("Touch and flat-footed", { total: `${s.touch.total} / ${s.flat.total}`, terms: [...s.touch.terms.map(t => ({ ...t, source: "touch: " + t.source })), ...s.flat.terms.map(t => ({ ...t, source: "flat: " + t.source }))] })}">
      <span class="k">Touch, flat</span><span class="v">${s.touch.total}<small>${s.flat.total}</small></span></button>
    ${conds ? `<span class="vital"><span class="k">Now</span><span class="v">${esc(conds)}</span></span>` : ""}`;
  $$(".playing [data-char]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.char === S.char)));
  $("#tab-spells").hidden = !isCaster();
}

// --- A number's reasons: every figure on the page opens to what it is made of ---------------------------
// BG3 shipped one bare number and found players took it for the DC; Owlcat's log shows every
// source on hover. Here a press opens it, and it stays open until dismissed, because Foundry's
// players asked for breakdowns that do not collapse on them.
function showWhy(anchor) {
  const w = WHY.get(anchor.dataset.why);
  if (!w) return;
  const box = $("#why");
  const terms = (w.block.terms || []).map(t =>
    `<li><span>${esc(upper(tidy(t.source)))}</span><span>${typeof t.value === "number" ? signed(t.value) : esc(t.value)}</span></li>`).join("");
  box.innerHTML = `<h4><span>${esc(w.label)}</span><span>${esc(w.block.total)}</span></h4>
    <ul>${terms || "<li><span>No modifiers</span><span></span></li>"}</ul>${w.note ? `<p>${esc(w.note)}</p>` : ""}`;
  box.hidden = false;
  const r = anchor.getBoundingClientRect();
  const x = Math.min(window.innerWidth - 286, Math.max(8, r.left));
  const below = r.bottom + 8 + box.offsetHeight < window.innerHeight;
  box.style.left = x + "px";
  box.style.top = (below ? r.bottom + 8 : r.top - box.offsetHeight - 8) + "px";
  box.dataset.for = anchor.dataset.why;
}
document.addEventListener("click", e => {
  const a = e.target.closest("[data-why]");
  const box = $("#why");
  if (a) {
    if (!box.hidden && box.dataset.for === a.dataset.why) { box.hidden = true; return; }
    showWhy(a); return;
  }
  if (!e.target.closest("#why")) box.hidden = true;
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape") { $("#why").hidden = true; $("#clockpop").hidden = true; }
});

// --- Toast: said once, and the ledger keeps anything that matters -----------------------------------------
let toastTimer = 0;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg; t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 2600);
}

// --- Views ----------------------------------------------------------------------------------------------------
const VIEWS = {};            // filled by views.js: name -> render()
function setMode(mode) {
  if (mode === "spells" && !isCaster()) mode = "table";
  S.mode = mode;
  document.body.className = document.body.className.replace(/\bmode-\w+/g, "").trim() + " mode-" + mode;
  $$("#modes [role=tab]").forEach(b => {
    const on = b.dataset.mode === mode;
    b.setAttribute("aria-selected", String(on));
    b.tabIndex = on ? 0 : -1;
  });
  $$(".view").forEach(v => { v.hidden = v.id !== "view-" + mode; });
  if (VIEWS[mode]) { VIEWS[mode](); paintIcons($("#view-" + mode)); }
  $("#why").hidden = true;
}
$("#modes").addEventListener("click", e => {
  const b = e.target.closest("[data-mode]");
  if (b) setMode(b.dataset.mode);
});
$("#modes").addEventListener("keydown", e => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
  const tabs = $$("#modes [role=tab]").filter(t => !t.hidden);
  let i = tabs.findIndex(t => t.getAttribute("aria-selected") === "true");
  i = e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1
    : (i + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
  tabs[i].focus(); setMode(tabs[i].dataset.mode);
  e.preventDefault();
});
document.addEventListener("click", e => {
  const g = e.target.closest("[data-go]");
  if (g) setMode(g.dataset.go);
});
$$("[data-theme-set]").forEach(b => b.addEventListener("click", () => setTheme(b.dataset.themeSet)));
$$("[data-size-set]").forEach(b => b.addEventListener("click", () => setSize(b.dataset.sizeSet)));
setTheme(recall("theme") || "system");
setSize(recall("size") || "m");
