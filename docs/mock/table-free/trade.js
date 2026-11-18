// Book and ledger: the counter. What the seller has, against what you carry, with one basket in
// the middle that holds both what you buy and what you sell, so the price you pay is one number.
// The goods and their prices are rules.goods.goods_at() for the market and the smithy. Selling
// at half the Core price is the book's rule for gear; the haggle is a Diplomacy roll on the
// app's dice mat, and its ten per cent is an EXAMPLE figure, not the engine's.
"use strict";

const COUNTER_NAME = { market: "The market", smithy: "The smith's counter" };
const COUNTER_SELLER = { market: "a stallholder", smithy: "the smith" };
const tradeShelf = g => (g[6] === "weapon" ? "weapons" : shelfOf(g[1]));
// rules/pricing.py: somebody the watch wants pays half again, and is paid that much less.
const markup = () => (S.wanted ? 1.5 : 1);

function openTrade(kind) {
  S.counter = kind; S.basket = []; S.haggle = null; S.tshelf = "all";
  renderTrade();
  $("#trade-back").hidden = false;
  paintIcons($("#tradesheet"));
  $("#tradesheet").querySelector("button").focus();
}
function closeTrade() { $("#trade-back").hidden = true; S.counter = null; $("#trade").focus(); }

function basketTotals() {
  let buy = 0, sell = 0;
  S.basket.forEach(b => { if (b.sell) sell += b.price * b.qty; else buy += b.price * b.qty; });
  const off = S.haggle && S.haggle.good ? Math.round(buy * 0.1 * 100) / 100 : 0;
  return { buy, sell, off, net: buy - off - sell };
}
function renderTrade() {
  const kind = S.counter;
  const wares = (kind === "smithy" ? [...D.counters.smithy, ...D.counters.weapons] : D.counters.market);
  const shelves = ["all", ...new Set(wares.map(tradeShelf))];
  const list = wares.filter(g => S.tshelf === "all" || tradeShelf(g) === S.tshelf);
  const t = basketTotals();
  const purse = me().purse / 100;
  const skill = sheet().skills.find(k => k.name === "diplomacy");
  const counter = list.map(g => `<div class="ware">${glyph(iconFor(g[1], tradeShelf(g)))}
      <b>${esc(upper(g[1]))}${g[5] ? `<small>${g[4]} ${esc(g[4] === 1 ? g[5].replace(/s$/, "") : g[5])}</small>` : ""}</b>
      <span class="price">${money(g[2] * markup())}</span>
      <button type="button" class="btn small" data-buy="${esc(g[0])}" aria-label="Add ${esc(g[1])} to the basket">Add</button></div>`).join("");
  const lines = S.basket.length ? S.basket.map((b, i) => `<div class="bline${b.sell ? " sell" : ""}">
      <b>${esc(upper(b.name))}<small>${b.sell ? "selling" : "buying"}, ${money(b.price)} each</small></b>
      <span class="stepper"><button type="button" data-step="${i}" data-d="-1" aria-label="One fewer">&minus;</button>
        <span>${b.qty}</span><button type="button" data-step="${i}" data-d="1" aria-label="One more">+</button></span>
      <span class="price">${money(b.price * b.qty)}</span></div>`).join("")
    : `<p class="empty">The basket is empty. Add from the counter, or offer something from your pack.</p>`;
  const mine = me().gear.filter(g => !g.where && g.value > 0).map(g => {
    const inB = S.basket.find(b => b.sell && b.id === g.id);
    return `<div class="ware">${glyph(iconFor(g.name, g.shelf))}
      <b>${esc(upper(g.name))}${g.qty > 1 ? `<small>you have ${g.qty}</small>` : ""}</b>
      <span class="price">${money(g.value / 2 / markup())}</span>
      <button type="button" class="btn small" data-sell="${g.id}"${inB && inB.qty >= g.qty ? " disabled" : ""}>Offer</button></div>`;
  }).join("");
  const short = t.net > purse;
  // Every press rebuilds the sheet, so each column's scroll is carried across: without this
  // the counter jumped back to the backpack after every Add.
  const kept = $$("#tradesheet .tradecols, #tradesheet .tradecols > section").map(el => el.scrollTop);
  $("#tradesheet").innerHTML =`<header class="tradehead">
      <div><h2 id="trade-title">${COUNTER_NAME[kind]}</h2>
        <p>${upper(COUNTER_SELLER[kind])} keeps it. Prices in Khy'vyr coin${S.wanted ? ", half again for somebody the watch wants" : ""}. You carry ${money(purse)}.</p></div>
      <span class="sp"></span>
      <button type="button" class="btn basketjump" data-jump>Basket: ${S.basket.length ? `${S.basket.reduce((n, b) => n + b.qty, 0)}, ${money(Math.abs(t.net))}` : "empty"}</button>
      <button type="button" class="btn" data-trade-close>Close</button></header>
    <div class="tradecols">
      <section aria-labelledby="h-counter"><h3 id="h-counter">On the counter <small>${wares.length} kinds</small></h3>
        <div class="shelftabs" role="tablist" aria-label="Kinds">${shelves.map(k => `<button type="button" role="tab"
          aria-selected="${S.tshelf === k}" data-tshelf="${k}">${k === "all" ? "All" : upper(k)}</button>`).join("")}</div>
        ${counter}</section>
      <section class="basket" aria-labelledby="h-basket"><h3 id="h-basket">The basket <small>${((n) => `${n} thing${n === 1 ? "" : "s"}`)(S.basket.reduce((n, b) => n + b.qty, 0))}</small></h3>
        ${lines}
        <div class="totals">
          <div><span>Buying</span><span>${money(t.buy)}</span></div>
          ${t.off ? `<div class="off"><span>Haggled, ten per cent off</span><span>&minus;${money(t.off)}</span></div>` : ""}
          <div><span>Selling</span><span>${t.sell ? "&minus;" + money(t.sell) : "nothing"}</span></div>
          <div class="grand"><span>${t.net >= 0 ? "You pay" : "You receive"}</span><span>${money(Math.abs(t.net))}</span></div>
        </div>
        <div class="haggle">${S.haggle ? `<span><b>Haggled:</b> Diplomacy ${S.haggle.total} (d20 ${S.haggle.nat} ${signed(skill.total)}).
            ${S.haggle.good ? "The seller comes down." : "The seller holds the price."}</span>`
          : `<span><b>Haggle</b> with Diplomacy ${signed(skill.total)}, against the seller. (This roll and its ten per cent are the mock's example; the engine's own haggle caps the ask at a price you agree in talk.)</span>
             <button type="button" class="btn small" data-haggle${t.buy ? "" : " disabled"}>Haggle</button>`}</div>
        ${short ? `<p class="hint bad">You are ${money(t.net - purse)} short. Take something out, or sell something.</p>` : ""}
        <div class="tradego"><button type="button" class="btn quiet" data-clear${S.basket.length ? "" : " disabled"}>Empty the basket</button>
          <button type="button" class="btn primary" data-settle${!S.basket.length || short ? " disabled" : ""}>${t.net >= 0 ? `Pay ${money(t.net)}` : `Take ${money(-t.net)}`}</button></div>
      </section>
      <section class="mine" aria-labelledby="h-mine"><h3 id="h-mine">Your pack <small>sells at half the market price</small></h3>
        ${mine || `<p class="empty">Nothing carried that this counter buys.</p>`}</section>
    </div>`;
  $$("#tradesheet .tradecols, #tradesheet .tradecols > section").forEach((el, i) => { el.scrollTop = kept[i] || 0; });
  paintIcons($("#tradesheet"));
}
document.addEventListener("click", async e => {
  if (!S.counter) return;
  const t = e.target;
  if (t.closest("[data-trade-close]") || t.id === "trade-back") { closeTrade(); return; }
  // On a phone the basket sits under forty wares; the head's summary jumps to it.
  if (t.closest("[data-jump]")) { $("#h-basket").scrollIntoView({ block: "start" }); return; }
  const sh = t.closest("[data-tshelf]");
  if (sh) S.tshelf = sh.dataset.tshelf;
  const b = t.closest("[data-buy]");
  if (b) {
    const g = [...D.counters.market, ...D.counters.smithy, ...D.counters.weapons].find(x => x[0] === b.dataset.buy);
    const have = S.basket.find(x => !x.sell && x.id === g[0]);
    if (have) have.qty += 1; else S.basket.push({ id: g[0], name: g[1], price: g[2] * markup(), qty: 1, shelf: tradeShelf(g) });
  }
  const s = t.closest("[data-sell]");
  if (s) {
    const g = me().gear.find(x => x.id === s.dataset.sell);
    const have = S.basket.find(x => x.sell && x.id === g.id);
    if (have) have.qty = Math.min(g.qty, have.qty + 1);
    else S.basket.push({ id: g.id, name: g.name, price: g.value / 2 / markup(), qty: 1, sell: true });
  }
  const st = t.closest("[data-step]");
  if (st) {
    const line = S.basket[+st.dataset.step];
    line.qty += +st.dataset.d;
    if (line.sell) { const g = me().gear.find(x => x.id === line.id); line.qty = Math.min(line.qty, g.qty); }
    if (line.qty <= 0) S.basket.splice(+st.dataset.step, 1);
  }
  if (t.closest("[data-clear]")) { S.basket = []; }
  if (t.closest("[data-haggle]")) {
    const skill = sheet().skills.find(k => k.name === "diplomacy");
    const nat = 1 + Math.floor(Math.random() * 20), total = nat + skill.total, good = total >= 15;
    if (window.Dice3D) {
      await Dice3D.land({ title: "Haggle", why: `Diplomacy, against ${COUNTER_SELLER[S.counter]}`, sides: 20, result: nat,
        terms: [{ label: "d20", value: nat }, ...skill.terms.map(x => ({ label: x.source, value: signed(x.value) })),
                { label: "Total", value: total, total: true }],
        verdict: { text: good ? "The price comes down" : "The price holds", good } });
    }
    S.haggle = { nat, total, good };
  }
  if (t.closest("[data-settle]")) {
    const tt = basketTotals();
    me().purse = Math.round(me().purse - tt.net * 100);
    S.basket.forEach(l => {
      if (l.sell) {
        const g = me().gear.find(x => x.id === l.id);
        g.qty -= l.qty; if (g.qty <= 0) me().gear.splice(me().gear.indexOf(g), 1);
      } else {
        const g = me().gear.find(x => x.name.toLowerCase() === l.name.toLowerCase() && !x.where);
        if (g) g.qty += l.qty; else me().gear.push(item(l.name, { qty: l.qty, shelf: l.shelf, ex: false, value: l.price }));
      }
    });
    const lines = S.basket.map(l => `${l.qty} ${l.name}`).join(", ");
    S.basket = []; S.haggle = null;
    closeTrade();
    addBeats([beat("you", `I settle at the counter: ${lines}.`),
      beat("oc", "Mock. The engine moves the goods and the coin; the narrator writes the exchange.",
        [{ title: "Trade", text: `${tt.net >= 0 ? "Paid" : "Received"} ${money(Math.abs(tt.net))}${tt.off ? `, ${money(tt.off)} haggled off` : ""}. Purse now ${money(me().purse / 100)}.` },
         advance(5, "a few minutes at the counter")])]);
    return;
  }
  renderTrade();
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && S.counter) closeTrade();
});

// Start at the gate.
resetTable();
