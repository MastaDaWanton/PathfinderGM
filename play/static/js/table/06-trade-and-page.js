// The play table, part 06 of 6 (trade and page). Split out of
// play/templates/play/table.html on 2026-09-25, in the order it ran; the six
// files are classic scripts, loaded in that order, sharing one global scope.


/* --- the counter --------------------------------------------------------------
   "i single store should not have every possible item ... also nothing has a price
   on it ... its also obvious the vender in this interaction did not actually see
   what i was trying to give her it was completely narrative."

   All three, and the third is why this screen exists rather than a better prompt:
   picking a jar off a list and being paid for it has nothing in it for a model to
   decide, so it goes straight to the engine the way the combat panel does. */
let TRADE = null;

/* The trade window, after the owner's mockup (I7, 2026-09-29): what you carry on the
   left as a list filed under tabs down its side, the deal in the middle as a basket with
   one button, their wares on the right as cards. Before it, the middle column held one
   picked thing at a time and a button that paid for that one thing; the basket is what
   every shop screen since the Ultima VII-era barter window does, and what the owner drew.

   The basket is the page's until the button is pressed, and nothing else: no coin moves
   and nothing is reserved. Each line goes to the engine as its own `buy` or `sell` op on
   /api/trade/do, sales first so their coin can pay for the purchases, exactly as if the
   player had pressed the old Pay button once per line. One basket per counter, so the
   armorer's deal is not the general store's, and walking away (closing) empties them. */
const TRADE_DEALS = new Map();
let TRADE_SHELF = "all";

// The side tabs and the cards' category marks, in the order the tabs run. The ids are
// the server's `shelf` (`play/views.py` SHELVES); the words are the player's.
const TRADE_SHELVES = {
  weapons:     { label: "Weapons",          icon: "lorc-broadsword" },
  armour:      { label: "Armour",           icon: "lorc-breastplate" },
  consumables: { label: "Consumables",      icon: "lorc-bubbling-flask" },
  gear:        { label: "Gear",             icon: "lorc-knapsack" },
  magic:       { label: "Magic items",      icon: "lorc-gem-pendant" },
  valuables:   { label: "Valuables",        icon: "lorc-gems" },
  materials:   { label: "Materials",        icon: "skoll-pestle-mortar" },
  animals:     { label: "Animals and tack", icon: "delapouite-horse-head" },
};
// A thing gets its own picture where the match is plain at 20px, read off its name within
// its shelf; everything else wears its shelf's picture, which is always true and never a
// guess (the Spells page's rule, I5). First match wins, so the crossbow is asked before
// the bow.
const TRADE_ITEM_ICONS = {
  weapons: [
    [/crossbow/, "carl-olsen-crossbow"],
    [/\b(arrows?|bolts?|bullets?|cartridges?|pellets?|shot)\b/, "lorc-arrow-cluster"],
    [/pistol|musket|rifle|blunderbuss|firearm|\bguns?\b/, "skoll-musket"],
    [/bow\b/, "delapouite-bow-arrow"],
    [/axe\b/, "lorc-battle-axe"],
    [/hammer|maul\b/, "delapouite-warhammer"],
    [/mace|morningstar|morning star/, "delapouite-flanged-mace"],
    [/club|cudgel|\bsap\b/, "delapouite-wood-club"],
    [/quarterstaff|\bstaff\b/, "delapouite-bo"],
    [/dagger|knife|kukri|stiletto|\bdirk\b|kerambit/, "lorc-plain-dagger"],
    [/trident/, "lorc-trident"],
    [/spear|javelin|lance\b|\bpike\b|pilum/, "lorc-spears"],
    [/halberd|glaive|guisarme|ranseur|bardiche|corbin|fauchard|lucerne|poleaxe|polearm/,
     "lorc-halberd"],
    [/flail|nunchaku/, "delapouite-flail"],
    [/whip/, "lorc-whip"],
    [/sling/, "delapouite-sling"],
    [/scythe|sickle|\bkama\b/, "lorc-scythe"],
  ],
  armour: [
    [/shield|buckler/, "willdabeast-round-shield"],
    [/chain|mail shirt/, "lorc-mail-shirt"],
    [/scale/, "lorc-scale-mail"],
    [/leather|padded|\bhide\b|studded/, "delapouite-leather-armor"],
  ],
  gear: [
    [/rope/, "delapouite-rope-coil"], [/torch/, "delapouite-torch"],
    [/lantern|\blamp\b/, "lorc-lantern-flame"], [/\btent\b/, "delapouite-camping-tent"],
    [/backpack/, "delapouite-backpack"], [/bedroll|blanket/, "delapouite-sleeping-bag"],
    [/waterskin/, "delapouite-water-flask"], [/flint/, "delapouite-flint-spark"],
    [/healer/, "delapouite-first-aid-kit"], [/grappling|climber/, "lorc-grapple"],
    [/crowbar/, "delapouite-crowbar"], [/hammer|piton/, "lorc-claw-hammer"],
    [/\bsack\b|pouch/, "lorc-swap-bag"], [/mirror/, "lorc-mirror-mirror"],
    [/thieves|lockpick/, "delapouite-lockpicks"], [/holy symbol/, "lorc-holy-symbol"],
    [/manacle|shackle/, "lorc-manacles"], [/candle/, "lorc-candle-light"],
    [/\bink\b|paper|quill/, "lorc-quill-ink"], [/whistle/, "delapouite-whistle"],
    [/\bnet\b/, "lorc-fishing-net"], [/outfit|clothes|clothing/, "delapouite-clothes"],
    [/caltrop/, "delapouite-caltrops"],
  ],
  consumables: [
    [/bread|\bloaf\b/, "delapouite-bread"], [/cheese/, "lorc-cheese-wedge"],
    [/\bmeat\b/, "lorc-meat"], [/\bale\b|beer|mead/, "lorc-beer-stein"],
    [/wine/, "delapouite-wine-bottle"], [/meal|ration|stew/, "delapouite-hot-meal"],
    [/potion|elixir|tincture|draught|tonic|\btea\b|brew|philt/, "caro-asercion-round-potion"],
    [/antitoxin|antidote|\bvial\b|\boil\b/, "sbed-vial"],
  ],
  magic: [
    [/\bring\b/, "delapouite-ring"], [/cloak|cape|mantle/, "lucasms-cloak"],
    [/belt|girdle/, "lucasms-belt"], [/bracer/, "skoll-bracers"],
    [/boots|slippers/, "lorc-boots"], [/wand|\brod\b|\bstaff\b/, "lorc-crystal-wand"],
    [/amulet|necklace|periapt|pendant/, "lorc-gem-necklace"],
    [/elixir|potion/, "caro-asercion-round-potion"],
  ],
  valuables: [
    [/coins?\b|ingot/, "delapouite-two-coins"], [/\bring\b/, "delapouite-ring"],
    [/necklace|pendant|amulet/, "lorc-gem-necklace"],
  ],
  materials: [
    [/\bore\b|ingot|iron|steel|silver|gold|copper|bronze|brass|\blead\b|zinc|pewter|bismuth|metal|mithral|adamant|\btin\b/,
     "lorc-metal-bar"],
  ],
  animals: [
    [/horse|pony/, "delapouite-horse-head"], [/camel/, "delapouite-camel-head"],
    [/\bdog\b|mastiff/, "delapouite-sitting-dog"], [/donkey|mule/, "skoll-donkey"],
    [/feed|fodder|grain|oats/, "lorc-wheat"],
    [/saddle|bridle|\bbit\b|harness|barding/, "delapouite-saddle"],
  ],
};
// Said once, in the player's words. It was "nothing the engine can run", in red, on the
// tack (the owner, 2026-09-29): developer language, and an alarm for what is only the
// reason a price is low.
const TRADE_INERT = "for show, no effect in play";

const tradeShelf = x => (TRADE_SHELVES[x.shelf] ? x.shelf : "gear");
function tradeIcon(x) {
  const shelf = tradeShelf(x);
  const name = String(x.name || "").toLowerCase();
  const hit = (TRADE_ITEM_ICONS[shelf] || []).find(([re]) => re.test(name));
  return hit ? hit[1] : TRADE_SHELVES[shelf].icon;
}
const tradeGlyph = (name, cls = "") =>
  `<i class="tgi${cls ? " " + cls : ""}" data-icon="${esc(name)}" aria-hidden="true"></i>`;
// "Uncommon", only when it is not common: a line saying "common" under every rope and
// torch said nothing, forty times.
const tradeRarity = x => (x.tier && x.tier !== "common"
  ? x.tier.charAt(0).toUpperCase() + x.tier.slice(1) : "");

// Beside this script, wherever the server put it, the way 05-sheet.js finds the spell
// icons: "/static/js/table/06-trade-and-page.js?v=..." resolves "../../icons/items/" to
// "/static/icons/items/" in the browser and the packaged app alike. Inlined by fetch, not
// used as a CSS mask, for I5's reason: a mask needs the static server to call the file
// image/svg+xml, which on Windows is the registry's answer, not ours.
const TRADE_ICON_BASE = (() => {
  const s = document.querySelector('script[src*="js/table/06-trade-and-page.js"]');
  try { return new URL("../../icons/items/", s.src).href; }
  catch { return "/static/icons/items/"; }
})();
const TRADE_ICON_SVG = new Map();
function paintTradeIcons(root) {
  if (!root) return;
  const want = new Set();
  root.querySelectorAll("i.tgi[data-icon]").forEach(i => {
    if (i.firstChild) return;
    const svg = TRADE_ICON_SVG.get(i.dataset.icon);
    if (typeof svg === "string") i.innerHTML = svg;
    else want.add(i.dataset.icon);
  });
  for (const name of want) {
    if (TRADE_ICON_SVG.has(name)) continue;       // already on its way
    TRADE_ICON_SVG.set(name, null);
    // Only names from the tables above reach here, so the path cannot be steered.
    fetch(TRADE_ICON_BASE + encodeURIComponent(name) + ".svg")
      .then(r => (r.ok ? r.text() : ""))
      .then(text => {
        const svg = text.includes("<svg") ? text : "";
        TRADE_ICON_SVG.set(name, svg);
        if (svg) document.querySelectorAll(`i.tgi[data-icon="${CSS.escape(name)}"]`)
          .forEach(i => { if (!i.firstChild) i.innerHTML = svg; });
      })
      .catch(() => TRADE_ICON_SVG.set(name, ""));
  }
}

// `want` is what the player's own words set out to buy ("a coil of rope"): the turn
// that said it opens this panel with the thing already in the basket, and the server
// matches it against the real shelf, or says the keeper has none, and puts nothing in
// (2026-09-27, the user's ruling: a purchase "should open the trade tab [potentially
// with Rope in the basket]").
// `line` is one of a market's counters (I2: the general store, the armorer, a stall…);
// left out, the server opens on the counter that sells what was wanted, else the one
// the player is talking to, else the general store, never the market's master.
async function openTrade(want, line) {
  // The counter is the Trade tab now (the table rebuild): opening it, from the tab or
  // from a purchase said in words, is going to that tab.
  if (typeof Shell === "object" && Shell) Shell.enter("trade");
  $("#tradepanel").classList.add("on");
  $("#tradepanel").setAttribute("aria-hidden", "false");
  $("#trademsg").textContent = "";
  const body = {};
  if (typeof want === "string" && want) body.want = want;
  if (typeof line === "string" && line) body.line = line;
  try {
    // `post` already reads the body, throws on a bad status and hands back the parsed
    // object. Calling `.json()` on its return is how this screen first shipped, and the
    // panel opened completely empty with "r.json is not a function" in the corner.
    TRADE = await post("/api/trade", body);
  } catch (e) {
    $("#trademsg").textContent = e.message;
    // A shut counter has nobody to haggle with (seen live: the button stood ready).
    $("#tradehaggle").disabled = true;
    return;
  }
  // Put in once, not once per mention: a second "I buy rope" opens on the same basket.
  if (TRADE.pick && !tradeDeal().some(l => l.side === "buy" && l.id === TRADE.pick)) {
    tradeAdd("buy", TRADE.pick, false);
  }
  if (TRADE.want_line) $("#trademsg").textContent = TRADE.want_line;
  drawTrade();
  const card = (TRADE.pick && document.querySelector(
    `#tradtheirs [data-id="${CSS.escape(TRADE.pick)}"]`))
    || document.querySelector("#tradtheirs .tr-card");
  if (card) {
    card.scrollIntoView({ block: "nearest" });
    card.focus({ preventScroll: true });
  }
}

// Close, and Esc, walk away from the counter and back to the Table tab. Choosing
// another tab walks away too, without the second move (12-shell.js calls this).
async function closeTrade() {
  if (typeof Shell === "object" && Shell && Shell.mode() === "trade") {
    Shell.show("table");
    return;
  }
  await leaveCounter();
}

async function leaveCounter() {
  if (!$("#tradepanel").classList.contains("on")) return;
  // The keyboard goes back to the tab that opened the counter, not to the top of the
  // page, which is where a hidden panel's lost focus lands.
  if ($("#tradepanel").contains(document.activeElement) && $("#tab-trade")) {
    $("#tab-trade").focus({ preventScroll: true });
  }
  $("#tradepanel").classList.remove("on");
  $("#tradepanel").setAttribute("aria-hidden", "true");
  // Walking away from the counter puts everything back on it.
  TRADE_DEALS.clear();
  // The purse and the satchel have both moved; the page behind this is now stale, and
  // the transcript has gained a line for every trade that happened.
  render(await getState());
}

// The footer's Trade button went with the table rebuild: the Trade tab is the one door
// (the mock README, "Also: the footer's duplicate Trade button is gone"). The tab follows
// the server's answer rather than keeping its own copy of the rule, and where nobody
// keeps a counter it says so on the page instead of opening onto nothing
// (20-tab-trade.js shows this sentence).
const NO_COUNTER = "Nobody here keeps a counter. Say what you sell or buy, or find a stall.";
function reflectMerchant(s) {
  const tab = $("#tab-trade");
  if (!tab) return;
  const who = (s && s.merchant) || "";
  tab.title = who ? `Trade with ${who}` : NO_COUNTER;
}

// --- the basket ---------------------------------------------------------------------
// This counter's lines, in the order they were put in: [{side, id, n}].
function tradeDeal() {
  const key = (TRADE && (TRADE.line || TRADE.stall)) || "";
  if (!TRADE_DEALS.has(key)) TRADE_DEALS.set(key, []);
  return TRADE_DEALS.get(key);
}
const tradeRowOf = (side, id) =>
  ((side === "sell" ? TRADE.mine : TRADE.theirs) || []).find(r => r.id === id);
// How many one line can hold: what you carry of it, or, at their side, as many as you
// like of a thing the counter always stocks (rope, a longsword) and the one there is of
// a thing drawn onto today's shelf (the engine sells a drawn thing once).
function tradeMax(side, x) {
  if (!x) return 0;
  if (side === "sell") return Math.max(0, x.count || 0);
  return x.staple ? 99 : Math.max(1, x.count || 1);
}
function tradeAdd(side, id, draw = true) {
  const x = tradeRowOf(side, id);
  if (!x) return;
  const lines = tradeDeal();
  const have = lines.find(l => l.side === side && l.id === id);
  if (have) have.n = Math.min(tradeMax(side, x), have.n + 1);
  else lines.push({ side, id, n: 1 });
  if (draw) tradeRedraw();
}
function tradeStep(side, id, by) {
  const lines = tradeDeal();
  const l = lines.find(y => y.side === side && y.id === id);
  if (!l) return;
  l.n = Math.max(1, Math.min(tradeMax(side, tradeRowOf(side, id)), l.n + by));
  tradeRedraw();
}
function tradeDrop(side, id) {
  const lines = tradeDeal();
  const at = lines.findIndex(l => l.side === side && l.id === id);
  if (at >= 0) lines.splice(at, 1);
  tradeRedraw();
}

// A line whose thing has gone (sold out, or no longer carried) leaves the basket, and a
// count above what there is comes down to it.
function tradeTidy() {
  const lines = tradeDeal();
  for (let i = lines.length - 1; i >= 0; i--) {
    const x = tradeRowOf(lines[i].side, lines[i].id);
    if (!x || tradeMax(lines[i].side, x) < 1) lines.splice(i, 1);
    else lines[i].n = Math.min(lines[i].n, tradeMax(lines[i].side, x));
  }
  return lines;
}

// Everything the button needs to know, in copper so nothing drifts by a rounding: the
// sales first, each capped by what is still in the till after the ones before it (a
// stall short of the asking price puts down what it has, and taking it is the player's
// call: "i can still sell to them if i am willing to any get what they can give").
function tradeSums() {
  const cp = gp => Math.round((gp || 0) * 100);
  let till = Math.max(0, cp(TRADE.till.gp));
  const out = { buys: [], sells: [], buy: 0, ask: 0, got: 0 };
  for (const l of tradeTidy()) {
    const x = tradeRowOf(l.side, l.id);
    const worth = cp(x.gp) * l.n;
    if (l.side === "buy") {
      out.buys.push({ ...l, x, worth });
      out.buy += worth;
    } else {
      const got = Math.min(worth, till);
      till -= got;
      out.sells.push({ ...l, x, worth, got });
      out.ask += worth;
      out.got += got;
    }
  }
  out.net = out.buy - out.got;                    // > 0: you pay; < 0: you take
  out.purse = cp(TRADE.purse_gp);
  out.short = Math.max(0, out.buy - out.got - out.purse);
  return out;
}

// --- drawing ------------------------------------------------------------------------
// The market's counters, as the sheet's tab strip. Only at a market: a smithy or an
// inn is one counter, and a strip of one tab is noise.
function drawLines() {
  const nav = $("#tradelines");
  const lines = (TRADE && TRADE.lines) || [];
  nav.hidden = lines.length < 2;
  nav.innerHTML = lines.map(l => {
    const on = l.id === TRADE.line;
    return `<button type="button" role="tab" data-line="${esc(l.id)}"
      aria-selected="${on}" title="${esc(l.seller ? `${l.label}, kept by ${l.seller}` : l.label)}"
      >${esc(l.label.replace(/^the /, ""))}</button>`;
  }).join("");
  // On a phone the strip scrolls: the counter a purchase opened on (the horse lines,
  // last of nine) is brought into view rather than left off the edge.
  const on = nav.querySelector('[aria-selected="true"]');
  if (on && !nav.hidden) on.scrollIntoView({ block: "nearest", inline: "nearest" });
}

async function switchLine(id) {
  if (!TRADE || id === TRADE.line) return;
  $("#trademsg").textContent = "";
  try {
    TRADE = await post("/api/trade", { line: id });
  } catch (e) {
    $("#trademsg").textContent = e.message;
    return;
  }
  drawTrade();
}

$("#tradelines").addEventListener("click", e => {
  const b = e.target.closest("[data-line]");
  if (b) switchLine(b.dataset.line);
});

function drawTrade() {
  // Which counter, and who keeps it: "The armorer", then her name. A counter with no
  // name of its own (a tavern, a smithy) keeps the old heading.
  const label = TRADE.counter || "";
  $("#tradename").textContent = label
    ? label.replace(/^the /, "").replace(/^./, c => c.toUpperCase())
    : "At the counter";
  const who = (TRADE.seller && TRADE.seller.name) || TRADE.stall;
  // `TRADE.day` is the shelf's key (`market.day_of`, counted from 0); every clock the
  // player reads counts from 1 (`fmtClock` below, the bench's "Day 2"), so add one here.
  $("#trademeta").textContent = `${who} · day ${Number(TRADE.day || 0) + 1}`;
  drawLines();
  $("#tradepurse").textContent = TRADE.purse;
  $("#tradetill").textContent = `${TRADE.till.text} in the till`;
  drawHaggle();
  tradeRedraw();
}

// The haggle (rules/tradecraft.py, the engine's `haggle` op): once a counter a day, and
// what it won is said on the button, so a moved price is a price the player can see moved.
function drawHaggle() {
  const b = $("#tradehaggle");
  if (!b) return;
  const got = Number(TRADE.haggled || 0);
  b.disabled = !TRADE.can_haggle;
  b.textContent = got ? `Haggled: ${got}% your way` : TRADE.can_haggle ? "Haggle" : "Haggled today";
  b.title = TRADE.can_haggle
    ? "Your Profession against the keeper's Sense Motive: beat it and today's prices here move 2% your way, and 1% more for every point you beat it by, up to 25%."
    : "Once a counter a day.";
}

// Waiting on the die the haggle asked for: the answer to that roll redraws the counter.
let HAGGLE_LINE = null;
$("#tradehaggle").addEventListener("click", async () => {
  if (!TRADE || !TRADE.can_haggle) return;
  const b = $("#tradehaggle");
  b.disabled = true;
  const line = TRADE.line || "";
  try {
    const d = await post("/api/tradeskill", line ? { use: "haggle", line } : { use: "haggle" });
    if (d.awaiting) HAGGLE_LINE = line;
    render(d);
    if (!d.awaiting) {
      $("#trademsg").textContent = d.trade_tell || "";
      TRADE = await post("/api/trade", line ? { line } : {});
      drawTrade();
    }
  } catch (err) {
    $("#trademsg").textContent = err.message;
    b.disabled = false;
  }
});
document.addEventListener("table:posted", e => {
  if (HAGGLE_LINE === null || !e.detail || e.detail.awaiting) return;
  // The roll's own answer, not the face it posts first (`/api/roll/face`, which answers
  // before the turn is told and found the table busy when this listened to both).
  if (!/\/api\/roll$/.test(String(e.detail.url || ""))) return;
  const line = HAGGLE_LINE;
  HAGGLE_LINE = null;
  // After the roll's answer is drawn: the counter again, at the prices the haggle set.
  setTimeout(() => { if ($("#tradepanel").classList.contains("on")) openTrade(undefined, line); }, 0);
});

// Everything the basket touches, redrawn together, with the keyboard's place kept: a
// press of + on a stepper redraws the line it is on, and the focus has to still be on
// that + afterwards or the next press goes nowhere.
function tradeRedraw() {
  const a = document.activeElement;
  const hold = a && $("#tradepanel").contains(a) && a.closest("[data-id]")
    ? { id: a.closest("[data-id]").dataset.id, side: a.closest("[data-side]").dataset.side,
        role: a.dataset.act || (a.classList.contains("tr-line") ? "line" : "item"),
        where: a.closest("#tradewhat") ? "#tradewhat" : a.closest("#tradmine")
          ? "#tradmine" : "#tradtheirs" }
    : a && a.closest && a.closest("#tradeshelves") ? { shelf: a.dataset.shelf } : null;
  tradeTidy();
  drawMine();
  drawWares();
  drawDeal();
  paintTradeIcons($("#tradepanel"));
  if (!hold) return;
  let back = null;
  if (hold.shelf) {
    back = document.querySelector(`#tradeshelves [data-shelf="${CSS.escape(hold.shelf)}"]`);
  } else {
    const box = document.querySelector(`${hold.where} [data-side="${hold.side}"][data-id="${
      CSS.escape(hold.id)}"]`);
    back = box && (hold.role === "line" || hold.role === "item" ? box
      : box.querySelector(`[data-act="${hold.role}"]:not(:disabled)`) || box);
    // A removed line hands the focus to the one after it, else to the button.
    if (!back && hold.where === "#tradewhat") {
      back = document.querySelector("#tradewhat .tr-line") || $("#tradego");
    }
  }
  if (back) back.focus({ preventScroll: true });
}

function drawMine() {
  const mine = TRADE.mine || [];
  const nav = $("#tradeshelves");
  const counts = {};
  for (const x of mine) counts[tradeShelf(x)] = (counts[tradeShelf(x)] || 0) + 1;
  const shelves = Object.keys(TRADE_SHELVES).filter(k => counts[k]);
  if (TRADE_SHELF !== "all" && !counts[TRADE_SHELF]) TRADE_SHELF = "all";
  nav.hidden = !mine.length;
  const tab = (id, label, icon, n) => {
    const on = TRADE_SHELF === id;
    return `<button type="button" role="tab" data-shelf="${id}" aria-selected="${on}"
      tabindex="${on ? 0 : -1}" aria-controls="tradmine" aria-label="${esc(label)}, ${n}">
      ${tradeGlyph(icon)}<span class="tr-lab">${esc(label)}</span><small>${n}</small></button>`;
  };
  nav.innerHTML = tab("all", "All", "lorc-knapsack", mine.length)
    + shelves.map(k => tab(k, TRADE_SHELVES[k].label, TRADE_SHELVES[k].icon, counts[k]))
      .join("");
  // Sorted by name within a tab: this is a list you look something up in.
  const shown = mine.filter(x => TRADE_SHELF === "all" || tradeShelf(x) === TRADE_SHELF)
    .slice().sort((a, b) => String(a.name).localeCompare(String(b.name)));
  const inDeal = new Set(tradeDeal().filter(l => l.side === "sell").map(l => l.id));
  $("#tradmine").setAttribute("aria-label",
    TRADE_SHELF === "all" ? "Everything you carry" : TRADE_SHELVES[TRADE_SHELF].label);
  $("#tradmine").innerHTML = shown.length ? shown.map(x => {
    // Rarity only. "For show" is said once, on the deal's line, where the price is
    // decided: under every row it was eight lines of the same sentence in a pack of eight.
    const notes = tradeRarity(x) ? `<span class="tr-rare">${esc(tradeRarity(x))}</span>` : "";
    return `<button type="button" class="traderow${inDeal.has(x.id) ? " on" : ""}"
      data-side="sell" data-id="${esc(x.id)}"
      aria-label="Sell ${esc(x.name)}${x.count > 1 ? `, you have ${x.count}` : ""}, ${
        esc(x.price)}${x.count > 1 ? " each" : ""}">
      ${tradeGlyph(tradeIcon(x))}
      <span class="tr-nm"><b>${esc(x.name)}</b>${
        x.count > 1 ? ` <span class="tr-n">×${x.count}</span>` : ""}${
        notes ? `<span class="tr-note">${notes}</span>` : ""}</span>
      <span class="gp">${esc(x.price)}${x.count > 1 ? "<small>each</small>" : ""}</span>
    </button>`;
  }).join("") : `<p class="tr-empty">${mine.length
    ? "Nothing of that kind in your pack."
    : "You are carrying nothing a shop would buy."}</p>`;
}

function drawWares() {
  const theirs = TRADE.theirs || [];
  const n = new Map(tradeDeal().filter(l => l.side === "buy").map(l => [l.id, l.n]));
  $("#tradtheirs").innerHTML = theirs.length ? theirs.map(x => {
    const shelf = TRADE_SHELVES[tradeShelf(x)];
    const inDeal = n.get(x.id);
    return `<button type="button" class="tr-card${inDeal ? " in" : ""}" data-side="buy"
      data-id="${esc(x.id)}" aria-label="Buy ${esc(x.name)}${
        tradeRarity(x) ? ` (${esc(tradeRarity(x).toLowerCase())})` : ""}, ${esc(x.price)}${
        inDeal ? `, ${inDeal} in the deal` : ""}">
      ${tradeGlyph(tradeIcon(x), "tr-art")}
      <span class="tr-cname">${esc(x.name)}${tradeRarity(x)
        ? `<span class="tr-note tr-rare">${esc(tradeRarity(x))}</span>` : ""}</span>
      <span class="tr-foot"><span title="${esc(shelf.label)}">${
        tradeGlyph(shelf.icon, "tr-mark")}</span><span class="gp">${esc(x.price)}</span></span>
      ${inDeal ? `<span class="tr-in" aria-hidden="true">${inDeal} in the deal</span>` : ""}
    </button>`;
  }).join("") : `<p class="tr-empty">The counter is bare today.</p>`;
}

function drawDeal() {
  const s = tradeSums();
  const go = $("#tradego");
  const line = (l, got) => {
    const x = l.x;
    const max = tradeMax(l.side, x);
    // Beside the number it explains: a thing the engine runs nothing from is priced as
    // such (a quarter, when you sell it; `pricing.what_a_shop_pays`).
    const note = x.does_something ? "" : TRADE_INERT;
    return `<li class="tr-line" tabindex="0" data-side="${l.side}" data-id="${esc(l.id)}"
      aria-label="${esc(x.name)}, ${l.n}. Plus and minus change how many, Delete removes it.">
      ${tradeGlyph(tradeIcon(x))}
      <span class="tr-nm">${esc(x.name)}${note ? `<span class="tr-note">${note}</span>` : ""}</span>
      <span class="gp">${coinText(got / 100)}${
        l.side === "sell" && got < l.worth ? `<small>of ${coinText(l.worth / 100)}</small>` : ""}</span>
      <span class="tr-ctl">
        <span class="tr-step" role="group" aria-label="How many ${esc(x.name)}">
          <button type="button" data-act="dec" aria-label="One fewer"${
            l.n <= 1 ? " disabled" : ""}>−</button>
          <output aria-live="polite">${l.n}</output>
          <button type="button" data-act="inc" aria-label="One more"${
            l.n >= max ? " disabled" : ""}>+</button>
        </span>
        <button type="button" class="tr-drop" data-act="drop">Remove</button>
      </span>
    </li>`;
  };
  const parts = [];
  if (s.buys.length) {
    parts.push(`<h3>You buy</h3><ul class="tr-lines">${
      s.buys.map(l => line(l, l.worth)).join("")}</ul>`);
  }
  if (s.sells.length) {
    parts.push(`<h3>You sell</h3><ul class="tr-lines">${
      s.sells.map(l => line(l, l.got)).join("")}</ul>`);
  }
  $("#tradewhat").innerHTML = parts.join("") || `<p class="tr-empty">Nothing in the deal
    yet.</p><p class="tr-hint">Choose from their wares to buy, or from what you carry to
    sell. Enter adds the one in focus; on a line, + and − change how many.</p>`;

  const short = $("#tradeshort");
  short.classList.remove("bad");
  short.textContent = "";
  const empty = !s.buys.length && !s.sells.length;
  $("#tradetotlab").textContent = empty ? "Total"
    : s.net > 0 ? "You pay" : s.net < 0 ? "You receive" : "Even";
  $("#tradesum").textContent = empty ? "" : coinText(Math.abs(s.net) / 100);
  if (empty) {
    go.disabled = true;
    go.textContent = "Trade";
    return;
  }
  // Said beside the number, in the dim ink: an offer below the worth is the till's
  // answer, not an error, and taking it is the player's call.
  if (s.got < s.ask) {
    short.textContent = s.got <= 0
      ? `There is nothing left in the till today, so your goods fetch nothing here.`
      : `The till holds ${coinText(s.got / 100)} of the ${coinText(s.ask / 100)} your goods `
        + `are worth. That is everything they have today.`;
  }
  if (s.short > 0) {
    short.classList.add("bad");
    short.textContent = `You are ${coinText(s.short / 100)} short. Your purse holds `
      + `${TRADE.purse}.`;
  }
  const nothing = !s.buys.length && s.got <= 0;
  go.disabled = s.short > 0 || nothing;
  go.textContent = s.net > 0 ? `Trade, pay ${coinText(s.net / 100)}`
    : s.net < 0 ? `Trade, take ${coinText(-s.net / 100)}` : "Trade";
}

// Whole gold down to copper, in the same shape `pricing.as_text` writes server-side.
// Duplicated deliberately and kept trivial: the alternative is a round trip to price a
// number the browser already has.
function coinText(gp) {
  const cp = Math.round((gp || 0) * 100);
  const parts = [];
  if (Math.floor(cp / 100)) parts.push(`${Math.floor(cp / 100).toLocaleString()} gp`);
  if (Math.floor((cp % 100) / 10)) parts.push(`${Math.floor((cp % 100) / 10)} sp`);
  if (cp % 10) parts.push(`${cp % 10} cp`);
  return parts.join(" ") || "0 cp";
}

// --- input --------------------------------------------------------------------------
// A card or a row is a button: a click, Enter or Space puts one in the deal (or one
// more). The stepper and Remove are their own buttons; on a basket line, + and − and
// Delete do the same from the keyboard.
$("#tradepanel").addEventListener("click", e => {
  const act = e.target.closest("[data-act]");
  if (act) {
    const l = act.closest(".tr-line");
    if (!l) return;
    if (act.dataset.act === "inc") tradeStep(l.dataset.side, l.dataset.id, +1);
    else if (act.dataset.act === "dec") tradeStep(l.dataset.side, l.dataset.id, -1);
    else if (act.dataset.act === "drop") tradeDrop(l.dataset.side, l.dataset.id);
    return;
  }
  const shelf = e.target.closest("[data-shelf]");
  if (shelf) {
    TRADE_SHELF = shelf.dataset.shelf;
    tradeRedraw();
    return;
  }
  const row = e.target.closest(".traderow[data-side], .tr-card[data-side]");
  if (row) tradeAdd(row.dataset.side, row.dataset.id);
});

$("#tradewhat").addEventListener("keydown", e => {
  const l = e.target.closest(".tr-line");
  if (!l || e.ctrlKey || e.metaKey || e.altKey) return;
  const by = { "+": 1, "=": 1, "-": -1, "_": -1, "−": -1 }[e.key];
  if (by) {
    e.preventDefault();
    tradeStep(l.dataset.side, l.dataset.id, by);
  } else if ((e.key === "Delete" || e.key === "Backspace") && e.target === l) {
    e.preventDefault();
    tradeDrop(l.dataset.side, l.dataset.id);
  }
});

// The side tabs are one tab stop, walked with the arrows (WAI-ARIA's tabs pattern,
// vertical here), and choosing one shows it at once.
$("#tradeshelves").addEventListener("keydown", e => {
  const keys = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 };
  const tabs = [...$("#tradeshelves").querySelectorAll("[data-shelf]")];
  const at = tabs.indexOf(e.target.closest("[data-shelf]"));
  if (at < 0) return;
  let to = null;
  if (e.key in keys) to = (at + keys[e.key] + tabs.length) % tabs.length;
  else if (e.key === "Home") to = 0;
  else if (e.key === "End") to = tabs.length - 1;
  if (to === null) return;
  e.preventDefault();
  TRADE_SHELF = tabs[to].dataset.shelf;
  tradeRedraw();
  const now = document.querySelector(`#tradeshelves [data-shelf="${CSS.escape(TRADE_SHELF)}"]`);
  if (now) now.focus();
});

$("#tradego").addEventListener("click", async () => {
  if (!TRADE) return;
  const s = tradeSums();
  if (s.short > 0) return;
  const go = $("#tradego");
  go.disabled = true;
  go.textContent = "Trading";
  const line = TRADE.line;
  const done = [], tells = [];
  let failed = "";
  // Sales first, so what the stall pays is in the purse before the purchases ask for it.
  for (const l of [...s.sells, ...s.buys]) {
    if (l.side === "sell" && l.got <= 0) continue;
    const body = { op: l.side, item: l.id, count: l.n };
    // The counter this is, at a market: the armorer's rack, not the general store's.
    if (line) body.line = line;
    // The agreed price travels with a sale, so what the screen offered is what the
    // engine pays. It can only ever lower the ask (see `_op_sell`).
    if (l.side === "sell") body.accept = l.got / 100;
    try {
      const r = await post("/api/trade/do", body);
      if (r.tell) tells.push(r.tell);
      done.push(l);
    } catch (err) {
      failed = err.message;
      break;
    }
  }
  // What went through leaves the basket; what did not stays, with the reason beside it.
  const lines = tradeDeal();
  for (const d of done) {
    const at = lines.findIndex(y => y.side === d.side && y.id === d.id);
    if (at >= 0) lines.splice(at, 1);
  }
  $("#trademsg").textContent = [...tells, failed].filter(Boolean).join(" ");
  try {
    TRADE = await post("/api/trade", line ? { line } : {});
  } catch (err) {
    $("#trademsg").textContent = [...tells, err.message].filter(Boolean).join(" ");
  }
  drawTrade();
  // The button has gone quiet with the basket empty; the wares are where the keyboard
  // goes next.
  if (document.activeElement === go || !$("#tradepanel").contains(document.activeElement)) {
    const next = go.disabled ? document.querySelector("#tradtheirs .tr-card") : go;
    if (next) next.focus({ preventScroll: true });
  }
});

$("#closetrade").onclick = closeTrade;
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && $("#tradepanel").classList.contains("on")) closeTrade();
});

function busy(on) {
  $("#busy").classList.toggle("on", on);
  $("#send").disabled = on;
  // And every other control that takes an action. Only #send was disabled, so the
  // combat bar, the Cast and Use buttons and the talk panel stayed live mid-turn and the
  // server's lock had to refuse the second press with a 409 (2026-09-25). The lock is
  // still the authority; this stops the page offering what it would refuse.
  document.body.classList.toggle("resolving", on);
  // The engine device (13-device.js) listens for this: running while a turn is, and
  // its halt when the answer lands. It holds nothing back.
  document.dispatchEvent(new CustomEvent("table:busy", { detail: { on: !!on } }));
}
// Money, in this world's words. The names arrive with the state rather than being
// written here, because what a coin is called is the world's business — see
// rules/goods.py on why the ratios stay 1e's while the names do not.
const purseTotal = p => Object.values(p || {}).reduce((n, v) => n + (v || 0), 0);
function purseLine(purse, coinage) {
  const names = Object.fromEntries((coinage || []).map(c => [c.id, c]));
  return (coinage || []).slice().reverse()
    .map(c => [(purse || {})[c.id] || 0, c])
    .filter(([n]) => n)
    .map(([n, c]) => `${n} ${n === 1 ? c.name : c.plural}`)
    .join(", ") || "empty";
}

const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

// Speech and action, told apart on the page. The convention is older than any of this
// — the IRC emote, the MUSH pose, every roleplay tool since — and it is what the player
// already knows: *asterisks are what you did*, "quotes are what you said". Presentation
// only, deliberately: no source could be found claiming it improves what a model
// writes, and we do not claim it either (docs/speech-vs-action.md). What it does buy is
// a page you can read at a glance, and a player who marks their own speech is telling
// the engine where it is — which is exactly what the fight detector needs to leave
// alone.
const said = s => esc(s)
  .replace(/&quot;([^]*?)&quot;/g, '<q class="said">&quot;$1&quot;</q>')
  .replace(/\*([^*\n]+)\*/g, '<em class="did">$1</em>');
const sign = n => (n >= 0 ? "+" : "") + n;
const title = s => s.replace(/\b\w/g, c => c.toUpperCase());


// The carried flame. Position comes from the pointer; intensity comes from noise —
// three sine waves at irrational frequency ratios plus a bounded random walk, which
// never falls into a rhythm a person can catch. Everything lands in CSS variables on
// the root, so the shade and the light read one source and the browser only ever
// composites transforms and opacity. Under prefers-reduced-motion the loop never
// starts and the flame holds a steady mid value.
{
  const root = document.documentElement.style;
  document.addEventListener("pointermove", e => {
    root.setProperty("--cx", `${e.clientX}px`);
    root.setProperty("--cy", `${e.clientY}px`);
    // Shadow direction: away from the light. One global vector — the panels
    // to the candle's right lean their shadows right — which is the cheap
    // approximation of per-panel geometry, and at room scale it reads true.
    const dx = (innerWidth / 2 - e.clientX) / innerWidth;
    const dy = (innerHeight / 2 - e.clientY) / innerHeight;
    root.setProperty("--sdx", `${(dx * 10).toFixed(1)}px`);
    root.setProperty("--sdy", `${(4 + dy * 8).toFixed(1)}px`);
  }, { passive: true });

  if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
    // Two channels from one flame. --flick updates every frame and feeds only
    // compositor-cheap properties (opacity, transform). --flicks is the same
    // signal quantised to ~10Hz and a minimum step, and it feeds the expensive
    // consumers — box-shadows and text-shadows repaint what they touch, and
    // sixty repaints a second of every card is how a laptop grows a fan noise.
    let walk = 0, slow = 0.8, slowAt = 0;
    const tick = now => {
      const t = now / 1000;
      walk = Math.max(-0.5, Math.min(0.5, walk + (Math.random() - 0.5) * 0.04));
      const flick = 0.72
        + 0.14 * Math.sin(t * 1.7)
        + 0.09 * Math.sin(t * 4.3 + 1.3)
        + 0.05 * Math.sin(t * 9.1 + 4.1)
        + 0.12 * walk;
      root.setProperty("--flick", flick.toFixed(3));
      root.setProperty("--jx", `${(Math.sin(t * 2.9) * 1.2).toFixed(2)}px`);
      root.setProperty("--jy", `${(Math.sin(t * 3.7 + 2) * 0.9).toFixed(2)}px`);
      if (now - slowAt > 100 && Math.abs(flick - slow) > 0.04) {
        slow = flick; slowAt = now;
        root.setProperty("--flicks", flick.toFixed(3));
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  } else {
    root.setProperty("--flick", "0.8");
  }
}

// The ember under the cursor. One delegated listener feeds --mx/--my to whatever
// interactive surface the pointer is inside, and the CSS paints a warm radial there.
// Delegated because the buttons are rebuilt on every render — a per-element listener
// would be lost each time, and hundreds of listeners for one glow is the wrong trade.
document.addEventListener("pointermove", e => {
  const t = e.target.closest("button, .sugg, .pick");
  if (!t) return;
  const r = t.getBoundingClientRect();
  t.style.setProperty("--mx", `${e.clientX - r.left}px`);
  t.style.setProperty("--my", `${e.clientY - r.top}px`);
}, { passive: true });

// Elapsed campaign time, from the engine's own clock. Elapsed rather than a time of day,
// because the engine has no notion of when the campaign started — "day 2, hour 3" is a
// fact the clock can state, and "9 in the morning" would be an invention. The playtest
// foraged for eight real hours and slept a full night and the page never showed a minute
// of it; the number was in the payload all along and nothing rendered it.
const fmtClock = mins => {
  mins = mins || 0;
  const day = Math.floor(mins / 1440), h = Math.floor((mins % 1440) / 60), m = mins % 60;
  if (!day && !h) return m ? `${m}m in` : "the first hour";
  const hm = m ? `${h}h ${m}m` : `${h}h`;
  return day ? `day ${day + 1}, ${hm} in` : `${hm} in`;
};

render(STATE);
