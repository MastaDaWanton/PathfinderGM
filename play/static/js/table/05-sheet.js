// The play table, part 05 of 6 (sheet). Split out of
// play/templates/play/table.html on 2026-09-25, in the order it ran; the six
// files are classic scripts, loaded in that order, sharing one global scope.
// A plain standing figure, drawn here rather than traced from anyone's artwork. It is
// only a place to hang the slots, so it is deliberately anonymous — no gear, no weapon,
// no gender, nothing that contradicts whoever the character actually is.
// One glyph per body slot, drawn as line art. Deliberately simple: they read at 26px,
// they cost nothing to ship, and they carry no licence. The reference mockup uses
// rendered metal icons — see the note at the end of the Equipment tab about what
// swapping these for real artwork would need.
const SLOT_ICONS = {
  head:      `<path d="M5 13a7 7 0 0 1 14 0v5l-3 3h-8l-3-3z"/><path d="M12 6v12M5 13h14"/>`,
  eyes:      `<circle cx="7.5" cy="13" r="4"/><circle cx="16.5" cy="13" r="4"/>
              <path d="M11.5 13h1M3.5 11 2 9M20.5 11 22 9"/>`,
  shoulders: `<path d="M8 4h8l4 5-2 12H6L4 9z"/><path d="M8 4c0 3 1.7 5 4 5s4-2 4-5"/>`,
  body:      `<path d="M9 3h6l4 4-2 3v11H7V10L5 7z"/><path d="M12 3v18"/>`,
  armor:     `<path d="M12 3 5 6v6c0 5 3 8 7 9 4-1 7-4 7-9V6z"/><path d="M12 3v18M5 11h14"/>`,
  wrists:    `<path d="M6 8h12v8H6z"/><path d="M6 11h12M6 13h12"/><path d="M9 8V6M15 8V6"/>`,
  feet:      `<path d="M8 3h4v9l6 4v5H6V8z"/><path d="M8 12h4"/>`,
  headband:  `<path d="M3 12h18"/><path d="M3 10h18v4H3z"/><path d="m12 10-2 4h4z"/>`,
  neck:      `<path d="M5 4c2 7 5 9 7 9s5-2 7-9"/><circle cx="12" cy="17" r="4"/>
              <circle cx="12" cy="17" r="1.4"/>`,
  chest:     `<path d="M8 4h8l3 4v13H5V8z"/><path d="M12 4v17M9 9h1M14 9h1"/>`,
  hands:     `<path d="M7 11V6a1.5 1.5 0 0 1 3 0v4M10 10V5a1.5 1.5 0 0 1 3 0v5M13 10V6a1.5 1.5 0 0 1 3 0v5"/>
              <path d="M16 9a1.5 1.5 0 0 1 3 0v6a6 6 0 0 1-6 6h-2a5 5 0 0 1-4-2l-3-4"/>`,
  ring:      `<circle cx="12" cy="14" r="6"/><path d="m9 7 3-4 3 4"/><path d="M12 3v4"/>`,
  belt:      `<path d="M2 9h20v6H2z"/><rect x="9" y="7" width="6" height="10" rx="1"/>
              <path d="M12 7v10"/>`,
  shield:    `<path d="M12 2 4 5v7c0 5 3.5 8.5 8 10 4.5-1.5 8-5 8-10V5z"/>
              <path d="M12 2v20M4 11h16"/>`,
};

const medallion = key => `<div class="medallion"><svg viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="1.35" stroke-linecap="round"
  stroke-linejoin="round" aria-hidden="true">${SLOT_ICONS[key] || ""}</svg></div>`;

// The house mark in the header. A blade over a hanging banner — generic on purpose;
// it is not anyone's heraldry until the campaign has some.
const SIGIL_SVG = `
<svg class="sigil" viewBox="0 0 46 62" fill="none" aria-hidden="true">
  <path d="M6 2h34v40l-17 18L6 42z" fill="currentColor" opacity=".55"/>
  <path d="M6 2h34v40l-17 18L6 42z" stroke="#8a6f3e" stroke-width="1.2"/>
  <g stroke="#d9c08a" stroke-width="1.4" stroke-linecap="round">
    <path d="M23 10v34"/><path d="M17 20h12"/><path d="m23 8-3 4h6z"/>
  </g>
</svg>`;

const FIGURE_SVG = `
<svg viewBox="0 0 200 460" role="img" aria-label="Body slot diagram">
  <defs>
    <radialGradient id="glow" cx="50%" cy="42%" r="55%">
      <stop offset="0%" stop-color="#3a2f1e" stop-opacity=".55"/>
      <stop offset="100%" stop-color="#0f0d0b" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="200" height="460" fill="url(#glow)"/>
  <!-- The ring and rays behind the figure: it gives the centre panel somewhere to sit
       instead of floating in the dark. -->
  <g stroke="#6b5836" fill="none" opacity=".55">
    <circle cx="100" cy="196" r="96" stroke-width="1"/>
    <circle cx="100" cy="196" r="88" stroke-width=".6" stroke-dasharray="2 6"/>
    <circle cx="100" cy="196" r="66" stroke-width=".6"/>
    <path d="M100 84 l7 12 -7 12 -7 -12z" stroke-width=".9"/>
    <path d="M100 308 l7 -12 -7 -12 -7 12z" stroke-width=".9"/>
    <path d="M4 196h28M196 196h-28" stroke-width=".9"/>
    <path d="M100 420 q-46 0 -66 -10 M100 420 q46 0 66 -10" stroke-width=".8"/>
  </g>
  <g fill="none" stroke="currentColor" stroke-width="2.2"
     stroke-linecap="round" stroke-linejoin="round">
    <circle cx="100" cy="42" r="26"/>
    <path d="M100 68 v22"/>
    <path d="M62 104 q38 -16 76 0"/>
    <path d="M62 104 q-6 60 2 96 h72 q8 -36 2 -96"/>
    <path d="M64 108 q-22 44 -26 92 q-2 14 6 22"/>
    <path d="M136 108 q22 44 26 92 q2 14 -6 22"/>
    <path d="M40 226 q-6 12 0 20 q8 8 16 2"/>
    <path d="M160 226 q6 12 0 20 q-8 8 -16 2"/>
    <path d="M66 200 q-4 60 2 108 q3 60 6 96"/>
    <path d="M134 200 q4 60 -2 108 q-3 60 -6 96"/>
    <path d="M74 404 h22 M126 404 h-22"/>
    <path d="M68 428 q-10 6 -2 12 h30 q4 -8 -2 -12"/>
    <path d="M132 428 q10 6 2 12 h-30 q-4 -8 2 -12"/>
  </g>
  <g fill="currentColor" opacity=".5">
    <circle cx="100" cy="26" r="3"/><circle cx="100" cy="52" r="3"/>
    <circle cx="100" cy="82" r="3"/><circle cx="100" cy="118" r="3"/>
    <circle cx="100" cy="150" r="3"/><circle cx="100" cy="192" r="3"/>
    <circle cx="46" cy="238" r="3"/><circle cx="154" cy="238" r="3"/>
    <circle cx="100" cy="436" r="3"/>
  </g>
</svg>`;

// The quest log: the tasks taken up, read off the situation cards of kind quest the
// engine keeps. Objectives say what to do next; the facts under them say what has
// happened — Baldur's Gate 3's journal keeps the two apart for the same reason.
function tabQuests() {
  const q = (STATE && STATE.quests) || { active: [], finished: [] };
  const one = (k, done) => `<div class="framed" style="margin:10px 0;padding:10px 14px">
      <h3 style="margin:0 0 4px">${esc(k.title)}${done ? ` <span class="why">— finished</span>` : ""}</h3>
      ${k.giver ? `<div class="why">for ${esc(k.giver)}</div>` : ""}
      <ul style="margin:6px 0 0 18px;padding:0">${k.objectives.map(o =>
        `<li style="${o.done ? "color:var(--dim);text-decoration:line-through" : ""}">${esc(o.text)}</li>`).join("")}</ul>
      ${k.reward ? `<div class="why" style="margin-top:6px">promised: ${esc(k.reward)}</div>` : ""}
      ${k.facts.length ? `<div class="why" style="margin-top:6px">${k.facts.map(esc).join(" · ")}</div>` : ""}
    </div>`;
  return `<h3 style="margin-top:0">Underway</h3>
    ${q.active.length ? q.active.map(k => one(k, false)).join("") : `<p class="why">Nothing taken on yet. When somebody gives you a task and you take it, it is kept here.</p>`}
    ${q.finished.length ? `<h3 style="margin-top:22px">Finished</h3>${q.finished.map(k => one(k, true)).join("")}` : ""}`;
}

const TABS = [
  ["defense",   "Defense",   s => tabDefense(s)],
  ["offense",   "Offense",   s => tabOffense(s)],
  ["skills",    "Skills",    s => tabSkills(s)],
  ["class",     "Class",     s => tabClass(s)],
  ["feats",     "Feats & Traits", s => tabFeats(s)],
  ["spells",    "Spells",    s => tabSpells(s)],
  ["equipment", "Equipment", s => tabEquipment(s)],
  ["inventory", "Inventory", s => tabInventory(s)],
  ["companions","Companions",s => tabEmpty("No animal companion, familiar, cohort or mount.")],
  ["background","Background",s => tabBackground(s)],
  ["quests",    "Quests",    s => tabQuests(s)],
  ["adventures","Adventures",s => tabEmpty("No adventure log yet. Sessions will be recorded here.")],
];

// Using something you made, from the Inventory tab. Straight to the engine — nothing
// in drinking your own tea for a model to decide. This handler was lost once already:
// it lived in the slice a later rewrite replaced wholesale, and the buttons kept
// rendering over nothing. It lives beside the sheet code it serves now, and
// tests/test_page_wiring.py pins /api/use into the served page so the next
// disappearance fails a test instead of a player.
document.addEventListener("click", async e => {
  const wearBtn = e.target.closest("[data-wear]");
  if (wearBtn) {
    busy(true);
    try {
      render(await post("/api/wear", { item: wearBtn.dataset.wear,
                                       off: !!wearBtn.dataset.off }));
      $("#sheeterr") && ($("#sheeterr").textContent = "");
    } catch (err) {
      // Beside the sheet, not behind it: slot refusals are the reason a click did
      // nothing, and the full-screen sheet hides #err completely.
      const box = $("#sheeterr") || $("#err");
      if (box) box.textContent = err.message;
    } finally { busy(false); }
    return;
  }
  const btn = e.target.closest("[data-use]");
  if (!btn) return;
  btn.disabled = true;
  const say = document.getElementById("sheeterr");
  if (say) say.textContent = "";
  try {
    const r = await fetch("/api/use", {
      method: "POST",
      headers: { "Content-Type": "application/json",
                 "X-CSRFToken": document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "" },
      body: JSON.stringify({ item: btn.dataset.use, how: btn.dataset.how }),
    });
    // Text first: a 500 returns an HTML page, and json() on that throws a parse error
    // that says nothing — the exact shape of every silent button this app has had.
    const raw = await r.text();
    let d = {};
    try { d = JSON.parse(raw); } catch { d = { error: `HTTP ${r.status}` }; }
    if (!r.ok) { if (say) say.textContent = d.error || `HTTP ${r.status}`; return; }
    SHEET = d.sheet;
    $("#sheetbody").innerHTML = TABS.find(x => x[0] === SHEET_TAB)[2](SHEET);
    if (say) say.textContent = "";
    $("#err").innerHTML = `<span style="color:var(--gold)">${esc(d.tell)}</span>`;
    render(await getState());
  } catch (err) {
    if (say) say.textContent = err.message;
  } finally {
    btn.disabled = false;
  }
});

async function openSheet() {
  $("#sheetpanel").classList.add("on");
  $("#sheetpanel").setAttribute("aria-hidden", "false");
  $("#sheetbody").innerHTML = `<div class="empty">Reading the sheet…</div>`;
  try {
    const r = await fetch("/api/sheet");
    SHEET = await readJSON(r);
    if (!r.ok) throw new Error(SHEET.error || "could not read the sheet");
  } catch (e) {
    $("#sheetbody").innerHTML = `<div class="empty">${esc(e.message)}</div>`;
    return;
  }
  if (!$("#sheethead-sigil")) {
    $(".sheethead").insertAdjacentHTML("afterbegin",
      `<span id="sheethead-sigil">${SIGIL_SVG}</span>`);
  }
  $("#sheetname").textContent = SHEET.identity.name;
  $("#sheetmeta").textContent =
    // Gender and pronouns on the sheet, because the narrator reads both and a player
    // who is being described wrongly needs somewhere to look and see what it was told.
    [SHEET.identity.heritage, SHEET.identity.race, SHEET.identity.class,
     SHEET.identity.size, SHEET.identity.gender,
     SHEET.identity.pronouns].filter(Boolean).join(" · ");
  // Four characters on the roster predate the field and read they/them, which says
  // nothing about a body. Silence is what produced the wrong one in the first place, so
  // an unstated character says so here rather than quietly taking the model's default.
  askGender(!SHEET.identity.gender);
  $("#sheettabs").innerHTML = TABS.map(([k, label]) =>
    `<button role="tab" data-tab="${k}" aria-selected="${k === SHEET_TAB}">${label}</button>`
  ).join("");
  $("#sheettabs").querySelectorAll("button").forEach(b => {
    b.onclick = () => { SHEET_TAB = b.dataset.tab; drawSheet(); };
  });
  drawSheet();
}

function closeSheet() {
  // A spell's details lie over the sheet in the top layer; they go with it.
  if (typeof detailOpen === "function" && detailOpen()) closeDetail(false);
  $("#sheetpanel").classList.remove("on");
  $("#sheetpanel").setAttribute("aria-hidden", "true");
}

function drawSheet() {
  $("#sheettabs").querySelectorAll("button").forEach(b =>
    b.setAttribute("aria-selected", String(b.dataset.tab === SHEET_TAB)));
  const entry = TABS.find(t => t[0] === SHEET_TAB);
  $("#sheetbody").innerHTML = entry ? entry[2](SHEET) : "";
  $("#sheetbody").scrollTop = 0;
}

// --- shared bits ---
const termList = t => `<div class="terms">${
  (t.terms || []).map(m => `<div class="t"><span>${esc(m.source)}</span><b>${sign(m.value)}</b></div>`).join("")
}</div>`;

const statCard = (title, t, suffix = "") => `
  <div class="card">
    <h3>${esc(title)}</h3>
    <div class="bignum">${sign(t.total)} ${suffix ? `<small>${esc(suffix)}</small>` : ""}</div>
    ${termList(t)}
  </div>`;

const tabEmpty = msg => `<div class="empty">${esc(msg)}</div>`;

// --- Defense ---
function tabDefense(s) {
  const d = s.defense;
  return `<div class="cols">
    <!-- The six scores. The sheet has always *sent* them and only ever read Con, to
         work out what number you die at — so the one thing every other number on this
         page is derived from was the one thing it never showed. -->
    <div class="card wide">
      <h3>Abilities</h3>
      <div class="abilities">${s.abilities.map(a => `
        <div class="ab${a.damage || a.drain ? " hurt" : ""}">
          <span class="abk">${esc(a.key.toUpperCase())}</span>
          <b>${a.score}</b>
          <span class="abm">${a.modifier >= 0 ? "+" : ""}${a.modifier}</span>
          ${a.damage ? `<em>-${a.damage} damage</em>` : ""}
          ${a.drain ? `<em>-${a.drain} drain</em>` : ""}
        </div>`).join("")}</div>
      ${(s.class_features && s.class_features.length) ? `<div class="terms">
        ${s.class_features.map(f => `<div class="t"><span>${esc(f)}</span></div>`)
          .join("")}</div>` : ""}
    </div>
    <div class="card">
      <h3>Hit points</h3>
      <div class="bignum">${d.hp.current} <small>of ${d.hp.max}</small></div>
      <div class="terms">
        ${d.hp.temp ? `<div class="t"><span>Temporary${
            d.hp.temp_source ? ` — ${esc(d.hp.temp_source)}` : ""
          }</span><b>+${d.hp.temp}</b></div>` : ""}
        ${(d.dr || []).map(r => `<div class="t"><span>Reduction${
            r.source ? ` — ${esc(r.source)}` : ""}</span><b>${esc(r.label)}</b></div>`).join("")}
        ${d.hp.nonlethal ? `<div class="t"><span>Non-lethal</span><b>${
            d.hp.nonlethal}</b></div>` : ""}
        <div class="t"><span>Unconscious at</span><b>0</b></div>
        <div class="t"><span>Dead at</span><b>-${s.abilities.find(a => a.key === "con").score}</b></div>
        <div class="t"><span>Knocked out by non-lethal at</span><b>${
            d.hp.nonlethal_threshold}</b></div>
      </div>
    </div>
    <div class="card">
      <h3>Armour class</h3>
      <div class="bignum">${d.ac.total}</div>
      ${termList(d.ac)}
      <div class="terms" style="margin-top:10px">
        <div class="t"><span>Touch</span><b>${d.ac_touch.total}</b></div>
        <div class="t"><span>Flat-footed</span><b>${d.ac_flat_footed.total}</b></div>
      </div>
    </div>
    ${(d.gear && d.gear.length) ? `<div class="card">
      <h3>Damaged gear</h3>
      <div class="terms">${d.gear.map(g => `<div class="t"><span>${esc(g.name)} <small>${
          esc(g.material)}, hardness ${g.hardness}</small></span><b>${
          g.state === "destroyed" ? "destroyed" : `${g.hp}/${g.hp_max}${
            g.state === "broken" ? " broken" : ""}`}</b></div>`).join("")}</div>
    </div>` : ""}
    ${d.saves.map(sv => statCard(sv.name + " save", sv)).join("")}
    <div class="card">
      <h3>Combat Maneuver Defense</h3>
      <div class="bignum">${d.cmd.total}</div>
      ${termList(d.cmd)}
      <div class="terms" style="margin-top:10px">
        <div class="t"><span>Flat-footed (no Dex)</span><b>${d.cmd_flat_footed.total}</b></div>
      </div>
    </div>
    <div class="card">
      <h3>Conditions</h3>
      ${d.conditions.length ? d.conditions.map(c => `
        <div style="margin-bottom:10px">
          <b>${esc(c.name)}</b>${c.rounds_left ? ` <span class="pill">${c.rounds_left} rounds</span>` : ""}
          <div class="why">${esc(c.note)}</div>
          ${c.source ? `<div class="why">from: ${esc(c.source)}</div>` : ""}
        </div>`).join("") : `<div class="empty">None.</div>`}
    </div>
  </div>`;
}

// --- Offense ---
function tabOffense(s) {
  const o = s.offense;
  return `<div class="cols" style="margin-bottom:26px">
      ${statCard("Base attack bonus", {total: o.bab, terms: []})}
      ${statCard("Initiative", o.initiative)}
      ${statCard("Combat Maneuver Bonus", o.cmb)}
    </div>
    <div class="card" style="margin-bottom:26px">
      <h3>Attacks</h3>
      <table class="sheet">
        <tr><th>Weapon</th><th>Attack</th><th>Damage</th><th>Critical</th><th>Notes</th></tr>
        ${o.attacks.map(a => `<tr>
          <td><b>${esc(a.name)}</b>${a.equipped ? ' <span class="pill good">in hand</span>' : ""}
              <div class="why">${esc(a.category)}, ${a.hands === 2 ? "two-handed" : "one-handed"}</div></td>
          <td class="num">${sign(a.attack.total)}
              <div class="why" style="font-weight:400">${a.attack.terms.map(m => `${sign(m.value)} ${esc(m.source)}`).join("<br>")}</div></td>
          <td class="num">${esc(a.damage_dice)}${a.damage.total ? sign(a.damage.total) : ""}
              <div class="why" style="font-weight:400">${esc(a.type)}</div></td>
          <td class="num">${esc(a.crit)}</td>
          <td>${a.proficient ? "" : '<span class="pill warn">not proficient (-4)</span>'}
              ${a.sequence > 1 ? `<span class="pill">${a.sequence} attacks on a full attack</span>` : ""}</td>
        </tr>`).join("")}
      </table>
    </div>
    <div class="card">
      <h3>Combat maneuvers — roll CMB against the target's CMD</h3>
      <table class="sheet">
        <tr><th>Maneuver</th><th>Your CMB</th><th>On success</th><th></th></tr>
        ${o.maneuvers.map(m => `<tr>
          <td><b>${esc(m.name)}</b></td>
          <td class="num">${sign(m.cmb.total)}</td>
          <td>${esc(m.effect)}</td>
          <td>${m.size_limit != null ? '<span class="pill">max one size larger</span>' : ""}</td>
        </tr>`).join("")}
      </table>
    </div>`;
}

// --- Skills ---
function tabSkills(s) {
  return `<div class="card">
    <h3>Skills — ${s.skills.filter(k => k.rank > 0).length} trained</h3>
    <table class="sheet">
      <tr><th>Skill</th><th>Total</th><th>Ranks</th><th>Made up of</th></tr>
      ${s.skills.map(k => `<tr class="${k.usable ? "" : "dim"}">
        <td>${esc(title(k.name))}
            ${k.class_skill ? '<span class="pill good">class</span>' : ""}
            ${k.trained_only ? '<span class="pill">trained only</span>' : ""}
            <div class="why">${esc(k.ability.toUpperCase())}${k.armour_check ? " · armour check applies" : ""}</div></td>
        <td class="num">${k.usable ? sign(k.total) : "—"}</td>
        <td class="num">${k.rank || ""}</td>
        <td class="why">${k.usable
          ? k.terms.map(m => `${sign(m.value)} ${esc(m.source)}`).join(", ")
          : "cannot be attempted untrained"}</td>
      </tr>`).join("")}
    </table>
  </div>`;
}

// --- Feats ---
// The browse pane's last result, so a redraw does not lose it and typing does not refetch
// on every keystroke.
let FEAT_RESULTS = null;
let FEAT_QUERY = "";

function tabInventory(s) {
  const d = s.defense || {};
  const carried = d.carrying || [];
  const purse = (d.purse || {}).coins || {};
  const coins = STATE.coinage || [];
  const any = carried.length || Object.keys(purse).length;
  return `<div class="cols">
    <div class="card">
      <h3>Purse</h3>
      <div class="bignum">${purseTotal(purse) ? esc(purseLine(purse, coins))
        : "<small>empty</small>"}</div>
      ${(d.purse || {}).copper ? `<div class="terms"><div class="t">
        <span>In copper</span><b>${d.purse.copper}</b></div></div>` : ""}
    </div>
    <div class="card wide">
      <h3>What you have made</h3>
      ${(d.stock || []).length ? `<table class="sheet">
        <tr><th>Preparation</th><th>How many</th><th>What it does</th><th></th></tr>
        ${d.stock.map(j => `<tr>
          <td><b>${esc(j.name)}</b>${j.poisons && j.poisons.length
            ? ` <span class="poisonmark" title="This will poison whoever drinks it">☠</span>` : ""}</td>
          <td>${j.count}</td>
          <td class="why">${esc((j.effects || []).join(" · ") || "for show, no effect in play")}${
            (j.drawbacks || []).length ? ` <em>${esc(j.drawbacks.join(" "))}</em>` : ""}</td>
          <td class="useact">
            ${j.drinkable ? `<button class="mini" data-use="${esc(j.id)}" data-how="drink"
                >drink</button>` : ""}
            ${j.throwable ? `<button class="mini" data-use="${esc(j.id)}" data-how="throw"
                >throw</button>` : ""}
            ${j.coatable ? `<button class="mini" data-use="${esc(j.id)}" data-how="coat"
                >coat</button>` : ""}
          </td></tr>`).join("")}</table>`
        : `<div class="empty">Nothing crafted yet. The bench is under
           <a href="/craft/">Crafting</a>.</div>`}
    </div>
    <div class="card wide">
      <h3>Carried</h3>
      ${(carried.length || (s.equipment.weapons || []).length) ? `<table class="sheet">
        <tr><th>Thing</th><th>How many</th><th>What the engine knows</th></tr>
        ${(s.equipment.weapons || []).filter(w => w.name !== "unarmed").map(w => `<tr>
          <td><b>${esc(w.name)}</b></td><td>1</td>
          <td class="why">a weapon — ${w.equipped ? "drawn; " : ""}swing it from the
          combat panel</td></tr>`).join("")}
        ${carried.map(i => `<tr class="${i.known ? "" : "dim"}">
          <td><b>${esc(i.name)}</b></td><td>${i.count}</td>
          <td class="why">${esc(i.line)}</td></tr>`).join("")}</table>`
        : `<div class="empty">Nothing but what you are wearing.</div>`}
    </div>
    <div class="card wide">
      <h3>Satchel</h3>
      ${(d.satchel || []).length ? `<table class="sheet">
        <tr><th>Ingredient</th><th>How many</th></tr>
        ${d.satchel.map(h => `<tr><td><b>${esc(h.name)}</b></td>
          <td>${h.count}</td></tr>`).join("")}</table>`
        : `<div class="empty">No raw material. Forage from the crafting bench.</div>`}
    </div>
    <div class="card">
      <h3>In hand</h3>
      <div class="terms">${(s.equipment.weapons || []).map(w => `
        <div class="t"><span>${esc(w.name)}</span><b>${
          w.equipped ? "drawn" : ""}</b></div>`).join("")
        || `<div class="t"><span>unarmed</span><b></b></div>`}</div>
    </div>
  </div>`;
}

function tabClass(s) {
  const p = s.progression;
  if (!p || !p.rows) return tabEmpty("No class data for this character.");
  // Every column the class prints on its own table, gathered from the rows rather
  // than named here — a class with columns this app has never heard of still shows
  // them, which is the whole point of the classes being data.
  const cols = [...new Set(p.rows.flatMap(r => Object.keys(r.columns || {})))];
  return `<div class="cols">
    <div class="card wide">
      <h3>${esc(p.class)}</h3>
      <div class="why">${esc(p.summary || "")}</div>
      <div class="terms">
        <div class="t"><span>Hit die</span><b>${esc(String(p.hit_die))}</b></div>
        <div class="t"><span>Base attack</span><b>${
          esc(String(p.bab).replace(/_/g, " "))}</b></div>
        <div class="t"><span>Good saves</span><b>${
          esc((p.good_saves || []).join(", ") || "none")}</b></div>
        <div class="t"><span>Skill ranks</span><b>${p.skill_ranks}+Int</b></div>
      </div>
      ${(p.paths_offered || []).length ? `
        <h3 style="margin-top:20px">Paths</h3>
        <div class="why">This class follows two paths, in order. Path A runs from 1st
          level; Path B stays shut until its track opens at ${p.unlocks_b || 11}th.
          ${p.paths_taken.length ? `You follow <b>${esc(p.paths_taken[0])}</b> as
            Path A${p.paths_taken[1]
              ? ` and <b>${esc(p.paths_taken[1])}</b> as Path B` : ""}.`
            : "This character has none recorded."}</div>
        <div class="terms">
          <div class="t"><span>Path A — ${esc(p.paths_taken[0] || "not chosen")}</span>
            <b>Control Blood ${(p.control_blood || {}).a || 0}</b></div>
          <div class="t"><span>Path B — ${esc(p.paths_taken[1] || "not chosen")}</span>
            <b>${(p.control_blood || {}).b
              ? "Control Blood " + p.control_blood.b
              : `opens at ${p.unlocks_b || 11}th`}</b></div>
        </div>
        ${p.paths_offered.map(x => {
          const det = (p.path_detail || {})[x] || {};
          const mine = p.paths_taken.includes(x);
          return `<div class="pathblock ${mine ? "mine" : ""}">
            <h4>${esc(det.name || x)}${det.role ? ` <small>${esc(det.role)}</small>` : ""}
              ${mine ? `<span class="pill now">Path ${
                p.paths_taken.indexOf(x) === 0 ? "A" : "B"}</span>` : ""}</h4>
            ${det.summary ? `<div class="why">${esc(det.summary)}</div>` : ""}
            ${det.global_rule ? `<div class="why"><b>Global rule.</b> ${
              esc(det.global_rule)}</div>` : ""}
            ${Object.entries(det.tiers || {}).map(([tier, names]) => `
              <div class="tier"><b>Control Blood ${esc(tier)}</b>
                ${names.map(n => {
                  const key = (det.resolves || {})[n];
                  const up = (det.upgrades || {})[n];
                  const core = (det.core || []).includes(n);
                  const text = key ? (det.abilities || {})[key] : "";
                  return `<div class="ab-line"><span>${glossify(n)}</span>
                    <em>${up ? `<b>${esc(up)}</b> — upgrade of ${esc(key)}: ${esc(text)}`
                      : text ? esc(text)
                      : core ? "a Core Rulebook ability; see the rules reference"
                      : "named on the table; the source does not describe it"}</em>
                  </div>`;
                }).join("")}</div>`).join("")}
          </div>`;
        }).join("")}
        <div class="why" style="margin-top:8px">Abilities are tiered by Control Blood
          level, which is what <b>control blood 1a</b> through <b>5b</b> on the table
          above means. The text is the class document's own; the engine does not
          execute these yet — they are yours to invoke at the table.</div>` : ""}
      ${p.next ? `
        <h3 style="margin-top:20px">Next level</h3>
        <div class="terms">
          <div class="t"><span>Level</span><b>${p.next.level}</b></div>
          ${p.next.bab ? `<div class="t"><span>Base attack</span><b>+${
            p.next.bab}</b></div>` : ""}
          ${Object.entries(p.next.saves || {}).map(([k, v]) =>
            `<div class="t"><span>${esc(k)} save</span><b>+${v}</b></div>`).join("")}
          ${(p.next.grants || []).length ? `<div class="t"><span>Gains</span><b>${
            p.next.grants.map(glossify).join(", ")}</b></div>` : ""}
        </div>
        <button class="go" id="levelup" style="margin-top:14px">Take level ${
          p.next.level}</button>
        <div id="levelerr" class="why"></div>` : `<div class="why"
          style="margin-top:16px">Twentieth level. There is no more table.</div>`}
    </div>
    <div class="card wide">
      <h3>The whole table</h3>
      <table class="sheet">
        <tr><th>Level</th>${cols.map(c => `<th>${esc(c)}</th>`).join("")}
          <th>What it grants</th></tr>
        ${p.rows.map(r => `<tr class="${r.reached ? "" : "dim"}">
          <td><b>${r.level}</b>${r.level === p.level
            ? ' <span class="pill now">here</span>' : ""}</td>
          ${cols.map(c => `<td>${esc((r.columns || {})[c] ?? "")}</td>`).join("")}
          <td class="why">${(r.grants || []).map(glossify).join(", ") || "—"}</td>
        </tr>`).join("")}
      </table>
    </div>
  </div>`;
}

function tabFeats(s) {
  return `<div class="cols">
    <div class="card">
      <h3>Feats</h3>
      <table class="sheet">
        <tr><th>Feat</th><th>What it does</th></tr>
        ${s.feats.map(f => `<tr class="${f.applied ? "" : "dim"}">
          <td><b>${esc(f.name)}</b>${
            f.applied ? "" :
            f.known ? ' <span class="pill">not computed</span>'
                    : ' <span class="pill warn">unknown feat</span>'}
            ${f.prerequisites ? `<small class="prereq">${esc(f.prerequisites)}</small>` : ""}</td>
          <td class="why">${esc(f.effect)}</td>
        </tr>`).join("") || `<tr><td colspan="2" class="empty">None.</td></tr>`}
      </table>
      <div class="why" style="margin-top:10px">
        “Not computed” means the engine carries the feat and its text but applies no
        number for it — sixteen feats have arithmetic the engine owns, and the rest are
        yours to invoke.
      </div>
      ${(s.traits && s.traits.length) ? `
        <h3 style="margin-top:22px">Racial traits</h3>
        <table class="sheet">
          <tr><th>Trait</th><th>From</th></tr>
          ${s.traits.map(t => `<tr>
            <td><b>${glossify(t.name)}</b></td>
            <td class="why">${esc(t.source)}</td></tr>`).join("")}
        </table>` : ""}
      ${(s.body && (Object.keys(s.body.speeds || {}).length > 1 || (s.body.senses || []).length || (s.body.natural_weapons || []).length)) ? `
        <h3 style="margin-top:22px">The body</h3>
        <table class="sheet">
          <tr><th>What</th><th>How</th></tr>
          <tr><td><b>Moves</b></td><td class="why">${esc(Object.entries(s.body.speeds).map(([k, v]) => `${k} ${v} ft`).join(" · "))}</td></tr>
          ${(s.body.senses || []).length ? `<tr><td><b>Senses</b></td><td class="why">${esc(s.body.senses.join(" · "))}</td></tr>` : ""}
          ${(s.body.natural_weapons || []).map(w => `<tr><td><b>${esc(w.name)}</b></td>
            <td class="why">${w.count > 1 ? `${w.count} × ` : ""}${esc(w.damage)} ${esc(w.type)}${w.secondary ? " · secondary" : ""}</td></tr>`).join("")}
          ${(s.body.not_yet || []).map(n => `<tr><td><b>Not yet</b></td><td class="why">${esc(n)}</td></tr>`).join("")}
        </table>` : ""}
      ${(s.class_features && s.class_features.length) ? `
        <h3 style="margin-top:22px">Class features</h3>
        <table class="sheet">
          <tr><th>Feature</th><th>From</th></tr>
          ${s.class_features.map(f => `<tr>
            <td><b>${glossify(f)}</b></td>
            <td class="why">${esc(s.identity.class)}</td></tr>`).join("")}
        </table>` : ""}
    </div>
    <div class="card">
      <h3>Browse</h3>
      <input type="search" id="featq" placeholder="Search 1,474 feats…"
             value="${esc(FEAT_QUERY)}" autocomplete="off">
      <div id="featresults">${featResults()}</div>
    </div>
  </div>`;
}

function featResults() {
  if (FEAT_RESULTS === null) {
    return `<div class="empty">Type to search, or see what you qualify for.</div>`;
  }
  if (!FEAT_RESULTS.length) return `<div class="empty">Nothing matches.</div>`;
  return FEAT_RESULTS.map(f => {
    // Three states, not two: "you qualify", "you are short by something specific", and
    // "this asks for something the sheet cannot check". Collapsing the last into a no
    // would be a lie about a feat the player may well be entitled to.
    const state = f.held ? ["held", "have it"]
      : f.qualifies ? ["ok", "can take"]
      : f.unmet.length ? ["no", "needs " + f.unmet.join(", ")]
      : ["maybe", "ask your GM: " + f.unknown.join("; ")];
    return `<div class="featrow ${state[0]}">
      <div><b>${esc(f.name)}</b>
        <small>${esc(f.types.join(", "))}${f.source ? " · " + esc(f.source) : ""}</small></div>
      <div class="why">${esc(f.benefit || f.description)}</div>
      <div class="verdict ${state[0]}">${esc(state[1])}</div>
    </div>`;
  }).join("");
}

let featTimer = null;
document.addEventListener("input", e => {
  const box = e.target.closest("#featq");
  if (!box) return;
  FEAT_QUERY = box.value;
  clearTimeout(featTimer);
  // Debounced: 1,474 feats is fast to filter and slow to re-render on every keystroke.
  featTimer = setTimeout(async () => {
    try {
      const r = await fetch(`/api/feats?q=${encodeURIComponent(FEAT_QUERY)}&limit=40`);
      FEAT_RESULTS = (await readJSON(r)).feats;
    } catch (err) {
      FEAT_RESULTS = [];
    }
    const box2 = $("#featresults");
    if (box2) box2.innerHTML = featResults();
  }, 180);
});

// --- Spells ---
// Three columns, after the owner's mockup (Phase 3 task I5, 2026-09-29): what the caster
// has to spend on the left, what is in their head today in the middle, the whole book on
// the right. The DC sits on the slot row rather than on each spell, because it is a
// property of the level and repeating it against forty spells is forty chances to read
// the wrong one.
//
// Art is game-icons.net (CC BY 3.0; credited in play/static/icons/spells/CREDITS.txt and
// on the manual's licence line). Each file is the upstream glyph with its black square
// removed and its fill set to currentColor, so one CSS colour per school tints it.
// Inlined rather than used as a CSS mask: a mask needs the static server to call the file
// image/svg+xml, and on Windows Python reads that answer from the registry, which is the
// same trap `.js` fell into (pathfindergm/urls.py). A fetch reads the text whatever the
// server calls it.
const SPELL_SCHOOLS = {
  abjuration:    { label: "Abjuration",    icon: "lorc-magic-shield" },
  conjuration:   { label: "Conjuration",   icon: "lorc-magic-portal" },
  divination:    { label: "Divination",    icon: "lorc-crystal-ball" },
  enchantment:   { label: "Enchantment",   icon: "lorc-psychic-waves" },
  evocation:     { label: "Evocation",     icon: "delapouite-bolt-spell-cast" },
  illusion:      { label: "Illusion",      icon: "lorc-duality-mask" },
  necromancy:    { label: "Necromancy",    icon: "lorc-dread-skull" },
  transmutation: { label: "Transmutation", icon: "lorc-potion-ball" },
  universal:     { label: "Universal",     icon: "lorc-star-swirl" },
};
// A spell gets its own picture only where the match is plain at 20px; everything else
// wears its school's sigil, which is always true and never a guess.
const SPELL_ICONS = {
  "acid-splash": "lorc-acid-blob", "animate-dead": "skoll-raise-zombie",
  "bleed": "lorc-bleeding-wound", "bless": "lorc-prayer",
  "burning-hands": "lorc-glowing-hands", "charm-person": "lorc-charm",
  "color-spray": "lorc-rainbow-star", "create-water": "sbed-water-drop",
  "daze": "delapouite-knocked-out-stars", "detect-magic": "lorc-third-eye",
  "disrupt-undead": "lorc-broken-skull", "expeditious-retreat": "lorc-run",
  "feather-fall": "lorc-feathered-wing", "fireball": "lorc-fireball",
  "fly": "lorc-feathered-wing", "grease": "delapouite-oil-can", "haste": "lorc-sprint",
  "identify": "lorc-magnifying-glass", "invisibility": "delapouite-invisible",
  "light": "lorc-candle-light", "lightning-bolt": "lorc-lightning-branches",
  "mage-armor": "lorc-energy-shield", "mage-hand": "lorc-magic-palm",
  "magic-missile": "lorc-missile-swarm", "mirror-image": "lorc-mirror-mirror",
  "prestidigitation": "delapouite-magick-trick", "ray-of-frost": "lorc-ice-bolt",
  "scorching-ray": "lorc-fire-ray", "shield": "lorc-shield-reflect",
  "sleep": "lorc-sleepy", "spiritual-weapon": "lorc-winged-sword", "web": "lorc-spider-web",
};
const schoolKey = s => (SPELL_SCHOOLS[String(s || "").toLowerCase()]
  ? String(s).toLowerCase() : "universal");
const spellIcon = sp => SPELL_ICONS[sp.id]
  || (/^cure-.*-wounds$/.test(sp.id || "") ? "delapouite-healing" : "")
  || SPELL_SCHOOLS[schoolKey(sp.school)].icon;
// The box is sized before the glyph arrives, so nothing moves when it does.
const glyph = (name, cls = "") =>
  `<i class="gi${cls ? " " + cls : ""}" data-icon="${esc(name)}" aria-hidden="true"></i>`;

// Beside this script, wherever the server put it: "/static/js/table/05-sheet.js?v=…"
// resolves "../../icons/spells/" to "/static/icons/spells/" in the browser and the
// packaged app alike.
const SPELL_ICON_BASE = (() => {
  const s = document.querySelector('script[src*="js/table/05-sheet.js"]');
  try { return new URL("../../icons/spells/", s.src).href; }
  catch { return "/static/icons/spells/"; }
})();
const SPELL_ICON_SVG = new Map();
// CC BY 3.0 asks for the authors and the licence where the work is used: the foot of the
// grimoire, the Background tab's licence note and the manual's footer all say it.
const spellIconCredit = () => `Spell icons by Lorc, Delapouite, Sbed and Skoll from
  <a href="https://game-icons.net" target="_blank" rel="noopener">game-icons.net</a>,
  <a href="https://creativecommons.org/licenses/by/3.0/" target="_blank"
  rel="noopener">CC BY 3.0</a>, recoloured.
  <a href="${esc(SPELL_ICON_BASE)}CREDITS.txt" target="_blank" rel="noopener">Which icon is
  whose</a>.`;

function paintSpellIcons(root) {
  if (!root) return;
  const want = new Set();
  root.querySelectorAll("i.gi[data-icon]").forEach(i => {
    if (i.firstChild) return;
    const svg = SPELL_ICON_SVG.get(i.dataset.icon);
    if (typeof svg === "string") i.innerHTML = svg;
    else want.add(i.dataset.icon);
  });
  for (const name of want) {
    if (SPELL_ICON_SVG.has(name)) continue;     // already on its way
    SPELL_ICON_SVG.set(name, null);
    // Only names from the two tables above reach here, so the path cannot be steered.
    fetch(SPELL_ICON_BASE + encodeURIComponent(name) + ".svg")
      .then(r => (r.ok ? r.text() : ""))
      .then(text => {
        const svg = text.includes("<svg") ? text : "";
        SPELL_ICON_SVG.set(name, svg);
        if (svg) document.querySelectorAll(`i.gi[data-icon="${CSS.escape(name)}"]`)
          .forEach(i => { if (!i.firstChild) i.innerHTML = svg; });
      })
      .catch(() => SPELL_ICON_SVG.set(name, ""));
  }
}
// Whoever draws the sheet (drawSheet, a level-up, the inventory's use button), the
// pictures follow: one observer rather than a call at every place that sets innerHTML.
new MutationObserver(() => { paintSpellIcons($("#sheetbody")); countGrimoire(); })
  .observe($("#sheetbody"), { childList: true, subtree: true });

// --- plain words for the rules text ------------------------------------------------------
// The catalogue keeps durations and ranges parsed, "minutes/level (10)" and "feet (60)";
// the page says them the way a player would read them aloud.
const spellCap = t => (t ? t.charAt(0).toUpperCase() + t.slice(1) : t);
function plainMeasure(text) {
  return String(text || "").trim().replace(
    /\b(rounds?|minutes?|hours?|days?|feet|miles?)(\/level)?\s*\((\d+)\)/gi,
    (_m, unit, per, n) => {
      const u = unit.toLowerCase();
      if (u === "feet") return `${n} ft${per ? " per level" : ""}`;
      const one = u.replace(/s$/, "");
      return `${n} ${n === "1" ? one : one + "s"}${per ? " per level" : ""}`;
    });
}
function rangeShort(r) {
  const m = /^(close|medium|long)\b/i.exec(String(r || "").trim());
  return m ? spellCap(m[1].toLowerCase()) : spellCap(plainMeasure(r)) || "None";
}
// The same, as a phrase for a summary line: "close range", "60 ft", "touch".
function rangePhrase(r) {
  const short = rangeShort(r);
  if (/^(Close|Medium|Long)$/.test(short)) return `${short.toLowerCase()} range`;
  return short === "None" ? "" : short.charAt(0).toLowerCase() + short.slice(1);
}
const saveShort = s => (!s || /^none$/i.test(String(s).trim()) ? "None" : spellCap(String(s).trim()));
// "conjuration (creation) · [acid] · wizard 1, …": the subschool and descriptors are
// the only parts of the index line a card does not already show another way.
function schoolLine(sp) {
  const label = SPELL_SCHOOLS[schoolKey(sp.school)].label;
  const head = String(sp.line || "").split("·");
  const sub = /\(([^)]+)\)/.exec(head[0] || "");
  const desc = /\[([^\]]+)\]/.exec(sp.line || "");
  return `${label}${sub ? ` (${sub[1]})` : ""}${desc ? `, ${desc[1]}` : ""}`;
}
const ABILITY_NAMES = { int: "Intelligence", wis: "Wisdom", cha: "Charisma" };
const levelName = n => (n === 0 ? "Cantrips" : `Level ${n}`);

// --- the tab ------------------------------------------------------------------------------
function tabSpells(s) {
  const sp = s.spells;
  if (!sp) {
    return tabEmpty(`${esc(s.identity.name)} does not cast spells.`);
  }
  return `<div class="spells3">
    ${casterStats(sp)}
    ${preparedToday(sp)}
    ${grimoireIndex(sp)}
  </div>`;
}

// The left column. Slots are gem sockets, lit while a prepared spell waits in one, red
// once spent today, dark while open (`slotSockets`), so "how much have I got" is read at
// a glance before the numbers are.
function casterStats(sp) {
  // Cantrips are never spent ("not expended when cast", AoN, Wizard; "do not consume any
  // slots", Sorcerer), so their row counts nothing down. A prepared caster's gems there
  // are the cantrips prepared today, lit one per cantrip held; a spontaneous caster's
  // row just says at will. It showed "3 of 3 left" draining until 2026-09-29.
  const heldCantrips = cantripsToday(sp).length;
  const sockets = (sp.slots || []).map(sl => sl.level === 0 ? `
    <li class="sock-level">
      <div class="sock-head"><span>${levelName(0)}</span>
        <span class="sock-dc">DC ${sl.dc}</span></div>
      ${sp.kind === "prepared" ? `<div class="sock-gems" role="img"
           aria-label="${Math.min(heldCantrips, sl.max)} of ${sl.max} cantrips prepared">${
        Array.from({ length: sl.max }, (_, i) =>
          `<i class="gem${i < heldCantrips ? " lit" : ""}"></i>`).join("")}</div>
      <div class="sock-count">${Math.min(heldCantrips, sl.max)} of ${sl.max} prepared, at will</div>`
      : `<div class="sock-count">At will</div>`}
    </li>` : slotSockets(sp, sl)).join("");
  return `<section class="card sx-stats" aria-labelledby="sx-stats-h">
    <h3 id="sx-stats-h">Caster stats</h3>
    <div class="terms">
      <div class="t"><span>Caster level</span><b>${sp.caster_level}</b></div>
      <div class="t"><span>Casting ability</span><b>${esc(ABILITY_NAMES[sp.ability]
        || String(sp.ability || "").toUpperCase())}</b></div>
      <div class="t"><span>Highest spell level</span><b>${sp.highest}</b></div>
    </div>
    <h4 class="sx-sub">Spell slots</h4>
    ${sockets ? `<ul class="sockets">${sockets}</ul>` : tabEmpty("No slots at this level.")}
    ${(sp.domain_slots || []).length ? `
      <h4 class="sx-sub">Domain slots</h4>
      <div class="terms">${sp.domain_slots.map(d => `
        <div class="t"><span>Level ${d.level}</span><b>${d.max}</b></div>`).join("")}</div>
      <p class="note">One a level, and only a domain spell goes in it.</p>` : ""}
    ${(sp.domains || []).length ? `
      <h4 class="sx-sub">Domains</h4>
      <div class="terms">${sp.domains.map(d => `
        <div class="t"><span>${esc(d.name)}</span>
          <b>${d.spells.length} <small>spell${d.spells.length === 1 ? "" : "s"}</small></b>
        </div>`).join("")}</div>` : ""}
    ${sp.note ? `<p class="sx-note">${esc(sp.note)}</p>` : ""}
  </section>`;
}

// A spell level's sockets, one per slot, in three states (owner, 2026-09-29: "perhaps a
// red bubble instead of a bronze one to indicate a spent slot"):
//   lit (bronze)  a prepared spell waiting in it;
//   spent (red)   cast today, and not refilled until a rest: "He cannot... fill a slot
//                 that is empty because he has cast a spell in the meantime" (CRB,
//                 Preparing Wizard Spells);
//   dark          open, nothing prepared in it yet.
// Until then a spent socket was dark like an open one, and the page could not show the
// difference the owner's Ysolde fell into: 1 of 2 left, and that one already full.
// Each socket names its state and the line under them says it in words (WCAG 1.4.1),
// so the colour is never the only way to read it. The counts are the sheet's own
// (`held`, `open`, from rules/casting.py); a spontaneous caster has no held spells, so
// their unspent slots are all ready.
function slotSockets(sp, sl) {
  const spent = Math.max(0, sl.max - sl.left);
  const prepared = sp.kind === "prepared";
  const ready = prepared ? Math.min(sl.held || 0, sl.left) : sl.left;
  const open = prepared ? Math.max(0, sl.left - ready) : 0;
  const name = `Level ${sl.level} slot`;
  const gems = [
    ...Array.from({ length: ready }, () =>
      `<i class="gem lit" role="img" aria-label="${name}: ${prepared ? "prepared, ready" : "ready"}"></i>`),
    ...Array.from({ length: open }, () =>
      `<i class="gem" role="img" aria-label="${name}: open"></i>`),
    ...Array.from({ length: spent }, () =>
      `<i class="gem spent" role="img" aria-label="${name}: spent today"></i>`),
  ].join("");
  const words = prepared ? `${ready} ready, ${spent} spent, ${open} open`
                         : `${sl.left} left, ${spent} spent`;
  return `
    <li class="sock-level">
      <div class="sock-head"><span>${levelName(sl.level)}</span>
        <span class="sock-dc">DC ${sl.dc}</span></div>
      <div class="sock-gems" role="group" aria-label="Level ${sl.level} slots">${gems}</div>
      <div class="sock-count${sl.left ? "" : " spent"}">${words}</div>
    </li>`;
}

// Why Prepare is off at a level, or "": the engine's own sentence (rules/casting.py
// `prepare_refusal`, sent per level as `blocked`), the one the endpoint would refuse with.
// A short form sits in a grimoire row, where the sentence would repeat down the list.
const prepBlocked = (sp, level) => {
  const sl = (sp.slots || []).find(x => x.level === level);
  return sp.kind === "prepared" && sl && sl.blocked ? sl : null;
};
// The owner's words for a spent level (2026-09-29).
const prepShort = sl => (sl.level > 0 && !sl.left
  ? "Spent for today; it comes back after a long rest." : "No open slot; unprepare one first.");
const prepNoteId = level => `sx-full-${level}`;

// The cantrips this caster may cast right now: a prepared caster's prepared ones (a
// wizard "can prepare a number of cantrips… each day", and a cleric's orisons read the
// same), a spontaneous caster's known ones. Until 2026-09-29 this took every cantrip in
// the book and on the class list, because the engine skipped the prepared check at level
// 0 and spent a slot instead; both halves were the wrong way round, and both are fixed.
function cantripsToday(sp) {
  const prepared = sp.kind === "prepared";
  return (sp.known || []).filter(k => !k.missing && k.level === 0
                                      && (!prepared || k.prepared > 0));
}

// The middle column. A prepared caster sees what is prepared; anyone else sees what they
// know. Cantrips are listed apart, as a short list: prepared like any spell, then cast at
// will — "not expended when cast and may be used again" (AoN, Wizard) — so their rows
// carry no count.
function preparedToday(sp) {
  const prepared = sp.kind === "prepared";
  const known = (sp.known || []).filter(k => !k.missing && k.level !== null && k.level !== undefined);
  const missing = (sp.known || []).filter(k => k.missing);
  const today = known.filter(k => k.level > 0 && (!prepared || k.prepared > 0));
  const slots = new Map((sp.slots || []).map(sl => [sl.level, sl]));

  const cantrips = new Map(cantripsToday(sp).map(k => [k.id, k]));
  const cantripRoom = slots.get(0) ? slots.get(0).max : 0;

  // The slot count once, in the level's header. It sat on every card until 2026-09-29,
  // so two cards read "1 of 2 level 1 slots left" each and looked like two free slots.
  // Under the header, when Prepare is off at this level, the reason, which every card's
  // disabled Prepare points to.
  const levels = [...new Set(today.map(k => k.level))].sort((a, b) => a - b);
  const cards = levels.map(lvl => {
    const sl = slots.get(lvl);
    const off = prepared ? prepBlocked(sp, lvl) : null;
    return `
    <h4 class="sx-sub sx-levelhead">${levelName(lvl)}${
      sl ? ` <small>DC ${sl.dc}, ${sl.left} of ${sl.max} slots left</small>` : ""}</h4>
    ${off ? `<p class="sx-full" id="${prepNoteId(lvl)}">${esc(off.blocked)}</p>` : ""}
    <div class="spcards">${today.filter(k => k.level === lvl)
      .map(k => spellCard(k, off, prepared)).join("")}</div>`;
  }).join("");

  const cantripRows = [...cantrips.values()].sort((a, b) => a.name.localeCompare(b.name));
  const heading = prepared ? "Prepared today" : "Known";
  return `<section class="card sx-today" id="sx-today" data-drop="${prepared ? "prepare" : "learn"}"
      aria-labelledby="sx-today-h" aria-describedby="sx-today-hint">
    <h3 id="sx-today-h">${heading}</h3>
    <p class="sx-hint" id="sx-today-hint">${prepared
      ? "Drag a spell here from the grimoire, or press its Prepare button."
      : "Drag a spell here from the list, or press its Learn button."}
      Cast attaches the spell to what you say next.</p>
    <p class="sx-say" id="spellsay" role="status" aria-live="polite"></p>
    ${cards || `<div class="sx-empty">${prepared
      ? "Nothing prepared yet. Choose from the grimoire beside this."
      : "Nothing known yet. Choose from the list beside this."}</div>`}
    ${cantripRows.length || (prepared && cantripRoom) ? `
      <h4 class="sx-sub sx-levelhead">Cantrips${
        slots.get(0) ? ` <small>DC ${slots.get(0).dc}</small>` : ""}</h4>
      <p class="sx-hint">At will: casting one spends nothing.${prepared
        ? ` ${cantripRows.length} of ${cantripRoom} prepared today; prepare the others from the grimoire.`
        : ""}</p>
      ${cantripRows.length ? `<ul class="sx-cantrips">${cantripRows.map(c => `
        <li class="sx-cantrip" style="--school: var(--sc-${schoolKey(c.school)})">
          ${glyph(spellIcon(c))}
          <span class="sx-cname"><b>${esc(c.name)}</b>
            <small>${esc([SPELL_SCHOOLS[schoolKey(c.school)].label, rangePhrase(c.range),
                          plainMeasure(c.duration)].filter(Boolean).join(", "))}</small>
            ${detailsButton(c, "sx-more")}</span>
          <span class="sx-cantrip-act" style="display: flex; gap: 6px; align-items: center">
          <button type="button" class="prepbtn castbtn" data-spell="${esc(c.id)}"
                  data-name="${esc(c.name)}" aria-label="Cast ${esc(c.name)}">Cast</button>${
          prepared ? `
          <button type="button" class="spbtn quiet" data-spell="${esc(c.id)}"
                  data-action="unprepare" data-name="${esc(c.name)}"
                  aria-label="Unprepare ${esc(c.name)}">Unprepare</button>` : ""}</span>
        </li>`).join("")}</ul>`
      : `<div class="sx-empty">No cantrip prepared yet. Choose from the grimoire beside this.</div>`}` : ""}
    ${missing.length ? `<p class="sx-note">Not in this build, so not shown:
      ${missing.map(k => esc(k.name)).join(", ")}.</p>` : ""}
  </section>`;
}

// `off` is the level's blocked slot row (`prepBlocked`) or null: Prepare is disabled and
// described by the level's reason line, so the button that does nothing says why.
function spellCard(k, off, prepared) {
  const school = schoolKey(k.school);
  // The mockup's strip reads Range, Casting time, Saving throw. The sheet does not send
  // a casting time (rules/sheet.py `_spell_sheet`); components stand in until it does,
  // and the cell switches to Casting time by itself the day the field arrives. "Parts",
  // not "Components": measured 2026-09-29, the label was cut to "COMPONEN…" in its
  // column at desktop; the full word stays in the cell's title.
  const middle = k.casting_time
    ? ["Cast time", spellCap(String(k.casting_time)), "Casting time"]
    : ["Parts", (k.components || []).join(", ") || "None", "Components"];
  const save = saveShort(k.save);
  return `<article class="spcard" style="--school: var(--sc-${school})"
      aria-label="${esc(k.name)}">
    <header class="spcard-head">
      ${glyph(spellIcon(k), "gi-lg")}
      <div class="spcard-title"><h5>${esc(k.name)}</h5>
        <span>${esc(schoolLine(k))}</span></div>
    </header>
    <dl class="spcard-strip">
      <div><dt>Range</dt><dd title="${esc(k.range || "")}">${esc(rangeShort(k.range))}</dd></div>
      <div><dt title="${middle[2]}">${middle[0]}</dt><dd>${esc(middle[1])}</dd></div>
      <div><dt>Save</dt><dd title="${esc(k.save || "")}">${esc(save)}</dd></div>
    </dl>
    <p class="spcard-line">Duration: ${esc(spellCap(plainMeasure(k.duration)) || "not stated")}</p>
    ${prepared ? `<p class="spcard-count"><b>${k.prepared}</b> prepared</p>` : ""}
    <div class="spcard-act">
      <button type="button" class="prepbtn castbtn" data-spell="${esc(k.id)}"
              data-name="${esc(k.name)}" aria-label="Cast ${esc(k.name)}">Cast</button>
      ${prepared ? `
        <button type="button" class="spbtn" data-spell="${esc(k.id)}" data-action="prepare"
                data-name="${esc(k.name)}" aria-label="Prepare another ${esc(k.name)}"${
                off ? ` disabled aria-describedby="${prepNoteId(k.level)}"` : ""}>Prepare</button>
        <button type="button" class="spbtn quiet" data-spell="${esc(k.id)}"
                data-action="unprepare" data-name="${esc(k.name)}"
                aria-label="Unprepare one ${esc(k.name)}">Unprepare</button>` : ""}
      ${detailsButton(k)}
    </div>
  </article>`;
}

// The right column: the whole book (a wizard) or the whole list (a cleric), searchable,
// sorted, filtered by school. A cleric chooses from 179 castable spells at first level,
// and a list that long is unusable without the search (item 26). The filters redraw the
// list alone, so the search box keeps its caret and the page keeps its place.
let SPELL_FIND = "", SPELL_SCHOOL = "", SPELL_SORT = "level";
function grimoireIndex(sp) {
  const prepared = sp.kind === "prepared";
  const groups = sp.choose_from || [];
  const schools = [...new Set(groups.flatMap(g => g.spells.map(s => schoolKey(s.school))))]
    .sort();
  return `<section class="card sx-index" aria-labelledby="sx-index-h">
    <h3 id="sx-index-h">${prepared ? "Grimoire index" : "What can be learned"}</h3>
    ${groups.length ? `
    <div class="gx-tools">
      <label class="gx-field gx-find"><span>Search</span>
        <input id="spellfind" class="findbox" type="search" value="${esc(SPELL_FIND)}"
               autocomplete="off" placeholder="Spell name"></label>
      <label class="gx-field"><span>Sort</span>
        <select id="spellsort">
          <option value="level"${SPELL_SORT === "level" ? " selected" : ""}>Lowest level</option>
          <option value="level-desc"${SPELL_SORT === "level-desc" ? " selected" : ""}>Highest level</option>
          <option value="name"${SPELL_SORT === "name" ? " selected" : ""}>Name</option>
        </select></label>
      <label class="gx-field"><span>School</span>
        <select id="spellschool">
          <option value="">All schools</option>
          ${schools.map(k => `<option value="${k}"${SPELL_SCHOOL === k ? " selected" : ""}>${
            SPELL_SCHOOLS[k].label}</option>`).join("")}
        </select></label>
    </div>
    <p class="gx-count" id="gx-count" aria-live="polite"></p>
    <div id="gx-list">${grimoireList(sp)}</div>` : tabEmpty("Nothing on this caster's list yet.")}
    <p class="gx-credit">${spellIconCredit()}</p>
  </section>`;
}

function grimoireRows(sp) {
  const find = SPELL_FIND.trim().toLowerCase();
  const rows = [];
  let total = 0;
  for (const g of sp.choose_from || []) {
    total += g.spells.length;
    for (const s of g.spells) {
      if (find && !s.name.toLowerCase().includes(find)) continue;
      if (SPELL_SCHOOL && schoolKey(s.school) !== SPELL_SCHOOL) continue;
      rows.push({ ...s, level: g.level, castable: g.castable });
    }
  }
  const byName = (a, b) => a.name.localeCompare(b.name);
  rows.sort(SPELL_SORT === "name" ? byName
    : SPELL_SORT === "level-desc" ? (a, b) => b.level - a.level || byName(a, b)
    : (a, b) => a.level - b.level || byName(a, b));
  return { rows, total };
}

function grimoireList(sp) {
  const prepared = sp.kind === "prepared";
  const action = prepared ? "prepare" : "learn";
  const verb = prepared ? "Prepare" : "Learn";
  const { rows, total } = grimoireRows(sp);
  const row = s => {
    const school = schoolKey(s.school);
    // A cantrip is prepared like any spell, then cast at will (AoN, Wizard: "can prepare
    // a number of cantrips… each day"), so a prepared caster's cantrip row casts once it
    // is prepared and prepares until then; one copy is all a cantrip ever needs. A
    // spontaneous caster's known cantrips cast. A level not reachable yet is shown (so
    // the player sees what is coming) but offers nothing.
    const castIt = `<button type="button" class="prepbtn castbtn" data-spell="${esc(s.id)}"
           data-name="${esc(s.name)}" aria-label="Cast ${esc(s.name)}">Cast</button>`;
    const cantripReady = s.level === 0 && (!prepared || s.prepared > 0);
    // No open slot at this level: Prepare stays in its place, disabled, with the short
    // reason under the name and the engine's whole sentence as its description. Until
    // 2026-09-29 it stayed live and the press came back as red text at the column's top.
    const off = !cantripReady && s.castable ? prepBlocked(sp, s.level) : null;
    const whyId = off ? `gx-why-${esc(s.id)}` : "";
    const act = cantripReady ? castIt
      : s.castable
        ? `<button type="button" class="spbtn" data-spell="${esc(s.id)}" data-action="${action}"
             data-name="${esc(s.name)}" aria-label="${verb} ${esc(s.name)}"${
             off ? ` disabled aria-describedby="${whyId}"` : ""}>${verb}</button>`
        : `<span class="gx-notyet">Not yet</span>`;
    const drag = s.castable && !cantripReady && !off;
    return `<li class="gx-row" style="--school: var(--sc-${school})"
        data-spell="${esc(s.id)}" data-name="${esc(s.name)}"${drag ? ` draggable="true"` : ""}>
      <span class="gx-grip${drag ? "" : " off"}" aria-hidden="true"></span>
      ${glyph(spellIcon(s))}
      <span class="gx-text"><b>${esc(s.name)}</b>
        <small>${esc([SPELL_SCHOOLS[school].label, rangePhrase(s.range),
                      plainMeasure(s.duration)].filter(Boolean).join(", "))}</small>
        ${s.prepared ? `<small class="gx-have">${s.prepared} prepared</small>` : ""}
        ${off ? `<small class="gx-why" id="${whyId}" title="${esc(off.blocked)}">${
          prepShort(off)}</small>` : ""}
        ${detailsButton(s, "sx-more")}</span>
      <span class="gx-lvl" title="Spell level ${s.level}"><span class="sr">Level </span>${s.level}</span>
      ${act}
    </li>`;
  };
  // A level with more spells than the sheet sends says so; the search reaches only what
  // was sent (rules/sheet.py `_CHOOSE_PAGE`, 60 a level).
  const unsent = (sp.choose_from || []).reduce((n, g) => n + Math.max(0, g.total - g.spells.length), 0);
  return `${rows.length ? `<ul class="gx-rows">${rows.map(row).join("")}</ul>`
      : `<div class="sx-empty">No spell matches.</div>`}
    ${unsent ? `<p class="sx-note">${unsent} more on this list are not shown here.</p>` : ""}
    <span hidden data-gx-shown="${rows.length}" data-gx-total="${total}"></span>`;
}

function redrawGrimoire() {
  const box = document.getElementById("gx-list");
  if (!box || !SHEET || !SHEET.spells) return;
  box.innerHTML = grimoireList(SHEET.spells);
  countGrimoire();
}
function countGrimoire() {
  const mark = document.querySelector("#gx-list [data-gx-shown]");
  const out = document.getElementById("gx-count");
  if (!mark || !out) return;
  const shown = Number(mark.dataset.gxShown), total = Number(mark.dataset.gxTotal);
  const text = shown === total ? `${total} spell${total === 1 ? "" : "s"}`
    : `Showing ${shown} of ${total}`;
  // Only when it changed: the observer that calls this watches the node it writes to,
  // and an unconditional write would wake it again forever.
  if (out.textContent !== text) out.textContent = text;
}

// --- what the spell does ------------------------------------------------------------------
// Owner, 2026-09-29: "the spell cards need a button to see ... the description of what the
// spell does. For the sake of space a button might be better." One popover for the whole
// tab, anchored to the Details button that opened it: it lies over the page rather than
// opening inside a card, so no card below moves and no line being read is pushed down.
// The text is the catalogue's own, from `GET /api/spells/<id>` (home_views.spell_detail),
// fetched once a spell and kept; the sheet's spells block carries no description.
//
// Popover "auto" gives Esc and a click outside for free (Baseline 2025, Electron 33's
// Chromium 130 has it); the class fallback below does both by hand for anything older.
const SPELL_DETAIL = { cache: new Map(), button: null, downOnOpen: false, returnFocus: false };

function detailsButton(sp, cls = "spbtn quiet") {
  return `<button type="button" class="${cls} sx-details" data-details="${esc(sp.id)}"
      data-name="${esc(sp.name)}" aria-expanded="false" aria-controls="spelldetail"
      aria-label="Details: ${esc(sp.name)}">Details</button>`;
}

function detailPop() {
  let p = document.getElementById("spelldetail");
  if (p) return p;
  p = document.createElement("div");
  p.id = "spelldetail";
  p.setAttribute("role", "dialog");
  p.setAttribute("aria-labelledby", "spelldetail-h");
  p.tabIndex = -1;
  if (typeof p.showPopover === "function") {
    p.setAttribute("popover", "auto");
    p.addEventListener("toggle", e => { if (e.newState === "closed") detailClosed(); });
  }
  document.body.appendChild(p);
  return p;
}
const detailOpen = () => {
  const p = document.getElementById("spelldetail");
  return !!p && (p.classList.contains("open")
                 || (typeof p.showPopover === "function" && p.matches(":popover-open")));
};

function markDetailButton(b, open) {
  if (!b) return;
  b.setAttribute("aria-expanded", String(open));
  b.textContent = open ? "Hide details" : "Details";
  b.setAttribute("aria-label", `${open ? "Hide details" : "Details"}: ${b.dataset.name}`);
}

// Below the button when there is room, above it when there is more there; never wider
// than the screen less its gutters, so a phone reads it whole.
function placeDetail() {
  const p = document.getElementById("spelldetail"), b = SPELL_DETAIL.button;
  if (!p || !b || !detailOpen()) return;
  const r = b.getBoundingClientRect();
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  if (r.bottom < 0 || r.top > vh) { closeDetail(false); return; }
  const w = Math.min(440, vw - 24);
  p.style.width = `${w}px`;
  p.style.left = `${Math.round(Math.max(12, Math.min(r.left, vw - w - 12)))}px`;
  const below = vh - r.bottom - 14, above = r.top - 14;
  if (below >= 280 || below >= above) {
    p.style.top = `${Math.round(r.bottom + 6)}px`; p.style.bottom = "auto";
    p.style.maxHeight = `${Math.round(Math.max(160, below))}px`;
  } else {
    p.style.top = "auto"; p.style.bottom = `${Math.round(vh - r.top + 6)}px`;
    p.style.maxHeight = `${Math.round(Math.max(160, above))}px`;
  }
}

function detailFacts(d, level) {
  const comps = (d.components || []).join(", ")
    + (d.component_cost ? ` (${d.component_cost})` : "");
  const facts = [
    ["Level", level === null || level === undefined ? "" : String(level)],
    ["Casting time", spellCap(d.casting_time || "")],
    ["Components", comps],
    ["Range", spellCap(plainMeasure(d.range))],
    ["Area", spellCap(plainMeasure(d.area))], ["Effect", spellCap(plainMeasure(d.effect))],
    ["Targets", spellCap(plainMeasure(d.targets))],
    ["Duration", spellCap(plainMeasure(d.duration))],
    ["Saving throw", spellCap(d.saving_throw || "")],
    ["Spell resistance", spellCap(d.spell_resistance || "")],
  ].filter(([, v]) => v);
  return `<dl class="sd-facts">${facts.map(([k, v]) =>
    `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join("")}</dl>`;
}

function detailHtml(id, name, d) {
  const sp = (SHEET && SHEET.spells) || {};
  const mine = (sp.known || []).find(k => k.id === id)
    || (sp.choose_from || []).flatMap(g => g.spells.map(s => ({ ...s, level: g.level })))
         .find(s => s.id === id) || {};
  const head = `<div class="sd-head"><h4 id="spelldetail-h">${esc(name)}</h4>
    <button type="button" class="spbtn quiet sd-close" aria-label="Close details of ${esc(name)}">Close</button></div>`;
  if (!d) return `${head}<p class="sd-wait">Reading the spell.</p>`;
  if (d.error) return `${head}<p class="sd-wait">${esc(d.error)}</p>`;
  const school = SPELL_SCHOOLS[schoolKey(d.school)].label
    + (d.subschool ? ` (${d.subschool})` : "")
    + ((d.descriptors || []).length ? `, ${d.descriptors.join(", ")}` : "");
  const text = String(d.description || "").trim();
  return `${head}<p class="sd-school">${esc(school)}</p>
    ${detailFacts(d, mine.level)}
    <div class="sd-text">${text
      ? text.split(/\n\s*\n|\n/).filter(Boolean).map(p => `<p>${esc(p)}</p>`).join("")
      : "<p>The catalogue has no description for this spell.</p>"}</div>`;
}

async function openDetail(button) {
  const p = detailPop();
  const id = button.dataset.details, name = button.dataset.name;
  if (SPELL_DETAIL.button && SPELL_DETAIL.button !== button) markDetailButton(SPELL_DETAIL.button, false);
  SPELL_DETAIL.button = button;
  p.style.setProperty("--school", button.closest("[style*='--school']")
    ? button.closest("[style*='--school']").style.getPropertyValue("--school") : "var(--sc-universal)");
  p.innerHTML = detailHtml(id, name, SPELL_DETAIL.cache.get(id));
  if (typeof p.showPopover === "function") { if (!p.matches(":popover-open")) p.showPopover(); }
  else p.classList.add("open");
  markDetailButton(button, true);
  placeDetail();
  p.focus({ preventScroll: true });
  if (SPELL_DETAIL.cache.has(id)) return;
  let d;
  try {
    const r = await fetch(`/api/spells/${encodeURIComponent(id)}`);
    d = await readJSON(r);
    if (!r.ok) d = { error: d.error || "The spell could not be read." };
  } catch (err) {
    d = { error: err.message || "The spell could not be read." };
  }
  if (!d.error) SPELL_DETAIL.cache.set(id, d);
  // Filled only if it is still this spell's popover that is open.
  if (detailOpen() && SPELL_DETAIL.button === button) {
    const had = p.contains(document.activeElement);
    p.innerHTML = detailHtml(id, name, d);
    placeDetail();
    if (had || document.activeElement === document.body) p.focus({ preventScroll: true });
  }
}

function closeDetail(returnFocus = true) {
  const p = document.getElementById("spelldetail");
  if (!p) return;
  SPELL_DETAIL.returnFocus = returnFocus;
  if (typeof p.showPopover === "function" && p.matches(":popover-open")) p.hidePopover();
  if (p.classList.contains("open")) { p.classList.remove("open"); detailClosed(); }
}

// Focus goes back to the button only when the player shut it on purpose: Esc, Close, or
// the same button again. A click elsewhere is its own answer to "where am I", so the
// browser's light dismiss (which arrives here with no `closeDetail` call) leaves it be.
// Unconditional once asked, because the browser's own restore picks the element focused
// when the popover FIRST opened: opened from Magic Missile, switched to Daze, closed
// with Close, and focus landed on Magic Missile (measured 2026-09-29).
function detailClosed() {
  const b = SPELL_DETAIL.button;
  const back = SPELL_DETAIL.returnFocus === true;
  SPELL_DETAIL.returnFocus = false;
  markDetailButton(b, false);
  SPELL_DETAIL.button = null;
  if (back && b && document.contains(b)) b.focus({ preventScroll: true });
}

// --- Equipment ---
// The body-slot page: a figure with the slots arranged down either side, roughly where
// each thing is worn. Empty slots are drawn as blanks rather than hidden — showing what
// is *not* filled is the whole reason for laying it out on a body.
function slotBox(sl, side) {
  const canAdd = sl.items.length < sl.max;
  return `
    <div class="slot ${side}" data-slot="${sl.key}">
      ${medallion(sl.key)}
      <div class="slothead">
        <span>${esc(sl.label)}</span>
        ${canAdd ? `<button class="addslot" data-slot="${sl.key}" title="Add another ${esc(sl.label.toLowerCase())} slot">+</button>` : ""}
      </div>
      ${sl.items.map(it => `
        <div class="slotrow${it.empty ? " isempty" : ""}${it.beyond_rules ? " beyond" : ""}">
          <input class="slotinput" data-slot="${sl.key}" data-index="${it.index}"
                 value="${esc(it.item || "")}" placeholder="empty"
                 ${sl.derived ? "disabled" : ""}>
          ${sl.items.length > 1 && !sl.derived
            ? `<button class="delslot" data-slot="${sl.key}" data-index="${it.index}" title="Remove this slot">×</button>`
            : ""}
        </div>`).join("")}
      <div class="slotholds">${esc(sl.holds)}${
        sl.max > sl.rules_limit ? ` · ${sl.rules_limit} work${sl.rules_limit === 1 ? "s" : ""} at once` : ""}</div>
    </div>`;
}

function tabEquipment(s) {
  const e = s.equipment, sl = e.slots;
  return `
    <div class="bodylayout">
      <div class="slotcol">${sl.left.map(x => slotBox(x, "left")).join("")}</div>
      <div class="figure">${FIGURE_SVG}
        <div class="figcap">${sl.filled} of ${sl.total} slots filled</div>
      </div>
      <div class="slotcol">${sl.right.map(x => slotBox(x, "right")).join("")}</div>
    </div>

    <div class="cols" style="margin-top:26px">
      <div class="card">
        <h3>Armour and shield</h3>
        <table class="sheet">
          <tr><th>Item</th><th>AC</th><th>Max Dex</th><th>Check penalty</th></tr>
          <tr><td>${esc(e.armour.name)}</td><td class="num">${sign(e.armour.ac)}</td>
              <td class="num">${e.armour.max_dex > 90 ? "—" : sign(e.armour.max_dex)}</td>
              <td class="num">${e.armour.acp || "—"}</td></tr>
          <tr><td>${esc(e.shield.name)}</td><td class="num">${sign(e.shield.ac)}</td>
              <td class="num">—</td><td class="num">${e.shield.acp || "—"}</td></tr>
        </table>
        <div class="why" style="margin-top:10px">
          Total armour check penalty ${e.armour_check_penalty || 0}, applied to
          Acrobatics, Climb, Disable Device, Escape Artist, Fly, Ride, Sleight of Hand,
          Stealth and Swim. The armour and shield slots are filled from here, so there
          is only one place that says what you are wearing.
        </div>
      </div>
      <div class="card">
        <h3>Carried weapons</h3>
        ${e.weapons.length
          ? `<ul style="margin:0;padding-left:18px">${e.weapons.map(w => `<li>${esc(w)}</li>`).join("")}</ul>`
          : `<div class="empty">Nothing.</div>`}
        <div class="why" style="margin-top:10px">
          A worn magic item the catalogue knows — a ring of protection, a cloak of
          resistance, a belt of giant strength — applies to your numbers while it sits
          in a slot, with its bonus named in every dice popup. A name the catalogue
          does not know is recorded and does nothing, and slots past the rules limit
          are worn, not working. Encumbrance is not tracked.
        </div>
      </div>
    </div>`;
}

async function slotAction(payload) {
  try {
    SHEET = await post("/api/slots", payload);
    drawSheet();
  } catch (e) {
    alert(e.message);
  }
}

// Delegated so the handlers survive every redraw.
document.addEventListener("click", e => {
  const add = e.target.closest(".addslot");
  if (add) return slotAction({action: "add", slot: add.dataset.slot});
  const del = e.target.closest(".delslot");
  if (del) return slotAction({action: "remove", slot: del.dataset.slot,
                              index: Number(del.dataset.index)});
  // `data-action` is required, not implied. The Cast button carries `prepbtn` too (it is
  // how 02-state.js's attach handler and its tests find it), and the old `.prepbtn`
  // match sent it here with no action — which the server reads as "prepare". Measured
  // 2026-09-29 on the old tab: every Cast press also prepared the spell once more.
  const prep = e.target.closest("#sheetbody [data-spell][data-action]");
  if (prep && !prep.disabled) {
    return prepareSpell(prep.dataset.spell, prep.dataset.action, prep.dataset.name, prep);
  }
});

function spellsSay(text) {
  const out = document.getElementById("spellsay");
  if (!out) return;
  // Emptied first and filled a beat later, so a region that was just redrawn still
  // announces, and the same sentence twice is still spoken twice.
  out.textContent = "";
  setTimeout(() => { out.textContent = text; }, 30);
}

// A refusal goes beside the card or row it is about, in the page's quiet notice style,
// not at the column's top in red. Measured 2026-09-29 (the owner's screenshot): "Ysolde
// Marrach has 2 level 1 slots and has already prepared 2" sat in red above both cards,
// naming neither and reading like a crash. The endpoint's words are plain sentences now
// (rules/casting.py `prepare_refusal`), and the note lands in the pressed button's card,
// row or cantrip line; a drop has no button, so it lands on the grimoire row the spell
// was carried from (the column's live region only if that row is filtered away).
function spellsRefused(spell, text, from) {
  document.querySelectorAll("#sheetbody .sx-refused").forEach(n => n.remove());
  const near = (from && from.closest && from.closest(".spcard, .gx-row, .sx-cantrip"))
    || document.querySelector(`#sheetbody .gx-row[data-spell="${CSS.escape(spell)}"]`);
  const note = document.createElement("p");
  note.className = "sx-refused";
  note.setAttribute("role", "status");
  if (!near) { spellsSay(text); return; }
  note.textContent = text;
  const slot = near.querySelector(".spcard-act, .gx-text, .sx-cname");
  (slot || near).insertAdjacentElement(slot && slot.classList.contains("spcard-act")
    ? "beforebegin" : "beforeend", note);
}

// The server refuses over-preparing and casting what was never prepared; the page only
// asks. Checking the slot arithmetic here as well would be a second implementation of a
// rule, and the one on screen is the one the player would believe: a disabled Prepare
// reads the sheet's `blocked` sentence, which is the endpoint's own refusal.
//
// The redraw keeps the reader where they were: `drawSheet` scrolls to the top, and a
// Prepare pressed halfway down the grimoire used to throw the list away from under the
// pointer. The scroll positions and the focused button come back after it.
async function prepareSpell(spell, action, name, from = null) {
  const body = $("#sheetbody");
  const list = () => document.querySelector("#gx-list .gx-rows");
  const keep = { top: body.scrollTop, list: list() ? list().scrollTop : 0,
                 focus: document.activeElement && document.activeElement.dataset
                   ? { spell: document.activeElement.dataset.spell,
                       action: document.activeElement.dataset.action || "" } : null };
  const who = name || spell;
  try {
    SHEET = await post("/api/spells/prepare", {action, spell});
  } catch (e) {
    spellsRefused(spell, e.message || String(e), from);
    return;
  }
  drawSheet();
  body.scrollTop = keep.top;
  if (list()) list().scrollTop = keep.list;
  if (keep.focus && keep.focus.spell) {
    const sel = s => document.querySelector(`#sheetbody ${s}[data-spell="${CSS.escape(keep.focus.spell)}"]`);
    const again = (keep.focus.action && sel(`[data-action="${keep.focus.action}"]`))
      || sel("#gx-list [data-action]") || sel(".castbtn");
    if (again && !again.disabled) again.focus({ preventScroll: true });
  }
  spellsSay(action === "prepare" ? `${who} prepared.`
    : action === "unprepare" ? `${who} unprepared.`
    : action === "learn" ? `${who} added to the book.` : `${who} done.`);
}

// Dragging a row from the grimoire into "Prepared today" prepares it (the owner's
// mockup). The row's own Prepare button is the same act for a keyboard or a touch
// screen, where HTML drag and drop does not reach. The drop zone lights at once and
// nothing slides: the owner's rule is no motion that makes a page harder to use.
let SPELL_DRAG = null;
const dropZone = t => (t && t.closest ? t.closest("#sheetbody #sx-today") : null);
document.addEventListener("dragstart", e => {
  const row = e.target.closest && e.target.closest('#sheetbody .gx-row[draggable="true"]');
  if (!row) return;
  SPELL_DRAG = { id: row.dataset.spell, name: row.dataset.name };
  e.dataTransfer.effectAllowed = "copy";
  e.dataTransfer.setData("text/plain", row.dataset.name);
  row.classList.add("dragging");
  const zone = document.getElementById("sx-today");
  if (zone) zone.classList.add("droppable");
});
document.addEventListener("dragend", () => {
  SPELL_DRAG = null;
  document.querySelectorAll("#sheetbody .dragging, #sheetbody .droppable, #sheetbody .dropping")
    .forEach(el => el.classList.remove("dragging", "droppable", "dropping"));
});
document.addEventListener("dragover", e => {
  const zone = dropZone(e.target);
  if (!zone || !SPELL_DRAG) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = "copy";
  zone.classList.add("dropping");
});
document.addEventListener("dragleave", e => {
  const zone = dropZone(e.target);
  if (zone && !zone.contains(e.relatedTarget)) zone.classList.remove("dropping");
});
document.addEventListener("drop", e => {
  const zone = dropZone(e.target);
  if (!zone || !SPELL_DRAG) return;
  e.preventDefault();
  const d = SPELL_DRAG;
  SPELL_DRAG = null;
  zone.classList.remove("dropping", "droppable");
  prepareSpell(d.id, zone.dataset.drop || "prepare", d.name);
});

// Details: one button opens, the same button (now "Hide details") or Close or Esc or a
// click outside shuts. The popover's own light dismiss runs on pointerdown, before the
// click, so a press on the open button would shut it and then open it again; noted here
// so the click reads "it was open" and leaves it shut (10-spells.js met the same).
document.addEventListener("pointerdown", e => {
  const b = e.target.closest && e.target.closest(".sx-details");
  SPELL_DETAIL.downOnOpen = !!b && b === SPELL_DETAIL.button && detailOpen();
}, true);
document.addEventListener("click", e => {
  const b = e.target.closest(".sx-details");
  if (b) {
    const wasOpen = SPELL_DETAIL.downOnOpen || (detailOpen() && SPELL_DETAIL.button === b);
    SPELL_DETAIL.downOnOpen = false;
    if (wasOpen) closeDetail(true); else openDetail(b);
    return;
  }
  if (e.target.closest("#spelldetail .sd-close")) { closeDetail(true); return; }
  // The fallback has no light dismiss of its own.
  const p = document.getElementById("spelldetail");
  if (p && p.classList.contains("open") && !p.contains(e.target)) closeDetail(false);
});
// It follows its button while the sheet scrolls, and goes when the button does (a redraw
// after Prepare replaces every button on the tab).
// Captured, because the grimoire's list scrolls inside the page and scroll events do not
// bubble. A button scrolled out of sight takes its popover with it (`placeDetail`).
$("#sheetbody").addEventListener("scroll", () => {
  if (detailOpen()) requestAnimationFrame(placeDetail);
}, { passive: true, capture: true });
window.addEventListener("resize", () => { if (detailOpen()) placeDetail(); });
new MutationObserver(() => {
  if (SPELL_DETAIL.button && !document.contains(SPELL_DETAIL.button)) closeDetail(false);
}).observe($("#sheetbody"), { childList: true, subtree: true });

// The search, the sort and the school filter redraw the list alone: the box keeps its
// caret and focus because it is never replaced.
document.addEventListener("input", e => {
  const find = e.target.closest("#spellfind");
  if (!find) return;
  SPELL_FIND = find.value;
  redrawGrimoire();
});
document.addEventListener("change", e => {
  if (e.target.id === "spellsort") { SPELL_SORT = e.target.value; redrawGrimoire(); return; }
  if (e.target.id === "spellschool") { SPELL_SCHOOL = e.target.value; redrawGrimoire(); }
});
document.addEventListener("change", e => {
  const input = e.target.closest(".slotinput");
  if (input) slotAction({action: "set", slot: input.dataset.slot,
                         index: Number(input.dataset.index), item: input.value});
});

// --- Background ---
function tabBackground(s) {
  const b = s.background, i = s.identity;
  return `<div class="cols">
    <div class="card">
      <h3>In the world</h3>
      <div class="terms">
        <div class="t"><span>People</span><b>${esc(b.heritage || "—")}</b></div>
        <div class="t"><span>World Bible id</span><b>${esc(i.world_people_id || "—")}</b></div>
      </div>
      <div class="why" style="margin-top:10px">
        The rules race and the world's people are different things, and the sheet
        carries both. ${esc(i.heritage || "This people")} is who
        ${esc(i.name)} is in the world; ${esc(i.race)} is what the rules use.
      </div>

      ${b.past ? `
      <h3 style="margin-top:16px">Before this</h3>
      <div class="terms">
        <div class="t"><span>Background</span><b>${esc(b.past.name)}</b></div>
      </div>
      ${b.past.line ? `<div class="why" style="margin-top:6px">${esc(b.past.line)}</div>` : ""}
      ${b.past.ties.length
        ? b.past.ties.map(t => `<div style="margin-top:10px">${esc(t)}</div>`).join("")
        : `<div class="empty" style="margin-top:10px">Chosen, but this world has not
             filled it in yet — the names arrive when the campaign begins.</div>`}
      ` : ""}
    </div>
    <div class="card">
      <h3>Notes</h3>
      ${b.notes ? `<div style="white-space:pre-wrap">${esc(b.notes)}</div>`
                : `<div class="empty">None.</div>`}
      <h3 style="margin-top:16px">The manual</h3>
      <div class="why">
        How the app works, what it needs, and what the slash commands do —
        <a href="/manual" target="_blank" rel="noopener">open the manual</a>.
      </div>

      <h3 style="margin-top:16px">Rules content</h3>
      <div class="why">
        The Pathfinder rules this app runs on — spells, creatures, feats, weapons and the
        tables behind them — are Open Game Content under the
        <a href="/licence" target="_blank" rel="noopener">Open Game Licence v1.0a</a>,
        which section 10 requires travel with it. This project is not published by,
        endorsed by, or affiliated with Paizo Inc.
      </div>
      <div class="why" style="margin-top:8px">${spellIconCredit()}</div>
    </div>
  </div>`;
}

/* An existing character with nothing said about what they are.
   The forge asks everyone made since the field existed, but the roster still holds four
   who predate it and read they/them — which says nothing about a body, so nothing can be
   derived from it and guessing from a name is the thing the field exists to stop. */
function askGender(missing) {
  // Scoped to the sheet, not `$(".sheethead")`. The trade panel reuses that class and
  // sits earlier in the document, so the bare selector returned *its* header — and
  // `insertBefore` threw "the node before which the new node is to be inserted is not a
  // child of this node", silently, with the prompt never appearing.
  const head = $("#sheetpanel .sheethead");
  let bar = $("#genderask");
  if (!missing) { if (bar) bar.remove(); return; }
  if (bar) return;
  bar = document.createElement("div");
  bar.id = "genderask";
  bar.style.cssText = "flex:1;display:flex;gap:8px;align-items:center;"
    + "font:13px/1.4 var(--body);color:var(--ink-dim)";
  bar.innerHTML = `Nothing on this sheet says what they are, so the narration will
    pick for them.
    <button class="quiet" data-setgender="woman">woman</button>
    <button class="quiet" data-setgender="man">man</button>`;
  head.insertBefore(bar, $("#closesheet"));
}

$("#sheetpanel").addEventListener("click", async e => {
  const pick = e.target.closest("[data-setgender]");
  if (!pick) return;
  try {
    await post("/api/character/gender", { gender: pick.dataset.setgender });
  } catch (err) {
    $("#sheeterr").textContent = err.message;
    return;
  }
  closeSheet();
  openSheet();
});

$("#closesheet").onclick = closeSheet;
document.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  // One Esc, one layer: a spell's details close first and the sheet stays open behind
  // them. Without this the same key shut both, and focus had nowhere to go back to.
  if (typeof detailOpen === "function" && detailOpen()) {
    e.preventDefault();
    closeDetail(true);
    return;
  }
  if ($("#sheetpanel").classList.contains("on")) closeSheet();
});
