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
let TRADE = null, PICK = null;

async function openTrade() {
  $("#tradepanel").classList.add("on");
  $("#tradepanel").setAttribute("aria-hidden", "false");
  $("#trademsg").textContent = "";
  PICK = null;
  try {
    // `post` already reads the body, throws on a bad status and hands back the parsed
    // object. Calling `.json()` on its return is how this screen first shipped, and the
    // panel opened completely empty with "r.json is not a function" in the corner.
    TRADE = await post("/api/trade", {});
  } catch (e) {
    $("#trademsg").textContent = e.message;
    return;
  }
  drawTrade();
}

async function closeTrade() {
  $("#tradepanel").classList.remove("on");
  $("#tradepanel").setAttribute("aria-hidden", "true");
  // The purse and the satchel have both moved; the page behind this is now stale, and
  // the transcript has gained a line for every trade that happened.
  render(await getState());
}

$("#tradeaction").onclick = openTrade;

// The button follows the server's answer rather than keeping its own copy of the rule.
// Disabled is deliberate over hidden: a player who wonders why sees the reason in the
// title, instead of wondering where the button went.
function reflectMerchant(s) {
  const btn = $("#tradeaction");
  if (!btn) return;
  const who = (s && s.merchant) || "";
  btn.disabled = !who;
  btn.title = who ? `Trade with ${who}`
                  : "Nobody here keeps a counter — say what you sell or buy, "
                    + "or find a stall.";
}

function tradeRow(x, side) {
  const on = PICK && PICK.side === side && PICK.id === x.id ? " on" : "";
  return `<button class="traderow${on}" data-side="${side}" data-id="${esc(x.id)}">
    <span><b>${esc(x.name)}</b>${x.count > 1 ? ` ×${x.count}` : ""}
      <span class="why${x.does_something ? "" : " inert"}">${
        x.tier}${x.does_something ? "" : " · nothing the engine can run"}</span></span>
    <span class="gp">${esc(x.price)}</span></button>`;
}

function drawTrade() {
  $("#trademeta").textContent = `${TRADE.stall} · day ${TRADE.day}`;
  $("#tradepurse").textContent = TRADE.purse;
  $("#tradetill").textContent = `${TRADE.till.text} in the till`;
  $("#tradmine").innerHTML = TRADE.mine.length
    ? TRADE.mine.map(x => tradeRow(x, "sell")).join("")
    : `<div class="empty">You are carrying nothing anyone would buy.</div>`;
  $("#tradtheirs").innerHTML = TRADE.theirs.length
    ? TRADE.theirs.map(x => tradeRow(x, "buy")).join("")
    : `<div class="empty">The stall is bare today.</div>`;
  drawDeal();
}

function drawDeal() {
  const go = $("#tradego");
  if (!PICK) {
    $("#tradewhat").textContent = "Pick something from either side.";
    $("#tradesum").textContent = "";
    $("#tradeshort").textContent = "";
    go.disabled = true; go.textContent = "—";
    return;
  }
  const rows = PICK.side === "sell" ? TRADE.mine : TRADE.theirs;
  const x = rows.find(r => r.id === PICK.id);
  if (!x) { PICK = null; return drawDeal(); }

  if (PICK.side === "sell") {
    // The whole reason the middle column exists. A stall short of the asking price
    // puts down what it has and says so — "i can still sell to them if i am willing
    // to any get what they can give" — and taking it is the player's call.
    const offered = Math.min(x.gp, TRADE.till.gp);
    $("#tradewhat").textContent = `You hand over ${x.name}.`;
    $("#tradesum").textContent = coinText(offered);
    $("#tradeshort").textContent = offered < x.gp
      ? `They cannot raise the ${x.price} it is worth — that is everything in the till.`
      : "";
    go.disabled = offered <= 0;
    go.textContent = offered <= 0 ? "They have nothing left today"
                                  : `Take ${coinText(offered)}`;
  } else {
    const short = x.gp > TRADE.purse_gp;
    $("#tradewhat").textContent = `You buy ${x.name}.`;
    $("#tradesum").textContent = x.price;
    $("#tradeshort").textContent = short
      ? `You have ${TRADE.purse}.` : "";
    go.disabled = short;
    go.textContent = short ? "You cannot afford it" : `Pay ${x.price}`;
  }
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

$("#tradepanel").addEventListener("click", e => {
  const row = e.target.closest("[data-side]");
  if (!row) return;
  PICK = { side: row.dataset.side, id: row.dataset.id };
  drawTrade();
});

$("#tradego").addEventListener("click", async () => {
  if (!PICK) return;
  const rows = PICK.side === "sell" ? TRADE.mine : TRADE.theirs;
  const x = rows.find(r => r.id === PICK.id);
  const body = { op: PICK.side, item: PICK.id, count: 1 };
  // The agreed price travels with a sale, so what the screen offered is what the
  // engine pays. It can only ever lower the ask — see `_op_sell`.
  if (PICK.side === "sell") body.accept = Math.min(x.gp, TRADE.till.gp);

  $("#tradego").disabled = true;
  try {
    $("#trademsg").textContent = (await post("/api/trade/do", body)).tell;
  } catch (err) {
    $("#trademsg").textContent = err.message;
  }
  PICK = null;
  TRADE = await post("/api/trade", {});
  drawTrade();
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
