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
          <td class="why">${esc((j.effects || []).join(" · ") || "nothing the engine can run")}${
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
// --- Spells ---
// Slots across the top, the book underneath. The DC sits on the slot row rather than on
// each spell, because it is a property of the level and repeating it against forty spells
// is forty chances to read the wrong one.
function tabSpells(s) {
  const sp = s.spells;
  if (!sp) {
    return tabEmpty(`${esc(s.identity.name)} does not cast spells.`);
  }

  const byLevel = new Map();
  for (const k of sp.known) {
    const lvl = k.level === null || k.level === undefined ? "?" : k.level;
    if (!byLevel.has(lvl)) byLevel.set(lvl, []);
    byLevel.get(lvl).push(k);
  }

  const slots = sp.slots.map(sl => `
    <div class="t"><span>Level ${sl.level}${
      sl.level > 0 ? ` <small>DC ${sl.dc}</small>` : ""}</span>
      <b class="${sl.left ? "" : "spent"}">${sl.left} <small>of ${sl.max}</small></b></div>`
  ).join("");

  const book = [...byLevel.entries()].sort((a, b) => (a[0] === "?") - (b[0] === "?")
                                                     || a[0] - b[0]).map(([lvl, list]) => `
    <h3>Level ${lvl}</h3>
    ${list.map(k => `
      <div class="spellrow${k.missing ? " missing" : ""}">
        <div class="spellname">
          <b>${esc(k.name)}</b>
          ${k.missing
            ? `<small>not in this build</small>`
            : `<small>${esc([k.school, k.range, k.duration].filter(Boolean).join(" · "))}${
                 k.save ? ` · ${esc(k.save)}` : ""}</small>`}
        </div>
        ${k.missing ? "" : `
          <div class="prep">
            <button class="prepbtn" data-spell="${esc(k.id)}" data-action="unprepare"
                    ${k.prepared ? "" : "disabled"} title="Unprepare">−</button>
            <span class="prepcount${k.prepared ? " has" : ""}">${k.prepared}</span>
            <button class="prepbtn" data-spell="${esc(k.id)}" data-action="prepare"
                    title="Prepare">+</button>
            <!-- Cast from here, fight or no fight (2026-09-24). The combat bar was the
                 only door and it is hidden outside an encounter, so a wizard in a
                 tavern had no way to cast light. The target is a person in the room,
                 yourself, or nobody, and the intent goes to the engine as declared. -->
            <select class="casttarget" data-spell="${esc(k.id)}" title="Target">
              <option value="">nobody</option>
              <option value="self">yourself</option>
              ${((STATE && STATE.scene && STATE.scene.actors) || []).filter(a => !a.is_pc).map(a =>
                `<option value="${esc(a.ref)}">${esc(a.name)}</option>`).join("")}
            </select>
            <button class="prepbtn castbtn" data-spell="${esc(k.id)}"
                    data-name="${esc(k.name)}" title="Cast ${esc(k.name)}">Cast</button>
          </div>`}
      </div>`).join("")}`).join("");

  return `<div class="cols">
    <div class="card">
      <h3>Slots</h3>
      <div class="terms">${slots || tabEmpty("No slots at this level.")}</div>
      <div class="terms" style="margin-top:10px">
        <div class="t"><span>Caster level</span><b>${sp.caster_level}</b></div>
        <div class="t"><span>Casting ability</span><b>${esc(sp.ability.toUpperCase())}</b></div>
        <div class="t"><span>Highest spell</span><b>Level ${sp.highest}</b></div>
      </div>
      ${(sp.domain_slots || []).length ? `
        <h3 style="margin-top:12px">Domain slots</h3>
        <div class="terms">${sp.domain_slots.map(d => `
          <div class="t"><span>Level ${d.level}</span><b>${d.max}</b></div>`).join("")}</div>
        <p class="note">One a level, and only a domain spell goes in it.</p>` : ""}
      ${(sp.domains || []).length ? `
        <h3 style="margin-top:12px">Domains</h3>
        <div class="terms">${sp.domains.map(d => `
          <div class="t"><span>${esc(d.name)}</span>
            <b>${d.spells.length} <small>spell${d.spells.length === 1 ? "" : "s"}</small></b>
          </div>`).join("")}</div>` : ""}
      ${sp.note ? `<div class="sub" style="margin-top:10px">${esc(sp.note)}</div>` : ""}
    </div>
    <div class="card">
      <h3>${sp.kind === "prepared" ? "Prepared today" : "Known"}</h3>
      ${book || tabEmpty(sp.kind === "prepared"
        ? "Nothing prepared yet — choose from the list beside this."
        : "Nothing in the book yet.")}
    </div>
    <div class="card">
      <h3>${sp.kind === "prepared" ? "What can be prepared" : "What can be learned"}</h3>
      ${spellChoices(sp)}
    </div>
  </div>`;
}

// The third region, and the reported half of item 26: "this spells panel should show a
// list of all known spells as well". A cleric prepares from the whole cleric list — 1,143
// spells, of which 179 are castable at first level — so it is grouped by spell level,
// searchable, and each level folds. A wizard's book needs none of that and gets the same
// widget with nothing to hide.
let SPELL_FIND = "";
function spellChoices(sp) {
  const groups = sp.choose_from || [];
  if (!groups.length) return tabEmpty("Nothing on this caster's list yet.");
  const find = SPELL_FIND.trim().toLowerCase();
  return `
    <input id="spellfind" class="findbox" type="search" placeholder="Find a spell…"
           value="${esc(SPELL_FIND)}" autocomplete="off">
    ${groups.map(g => {
      const rows = g.spells.filter(s => !find || s.name.toLowerCase().includes(find));
      // Levels they cannot cast yet are folded shut: they are there so a player can see
      // what is coming, not so they can scroll past it every time.
      const open = g.castable || find ? " open" : "";
      const hidden = g.total - g.spells.length;
      return `<details${open}><summary>Level ${g.level}
        <small>${g.total} spell${g.total === 1 ? "" : "s"}${
          g.castable ? "" : " · not yet"}</small></summary>
        ${rows.map(s => `
          <div class="spellrow">
            <div class="spellname"><b>${esc(s.name)}</b>
              <small>${esc([s.school, s.range, s.duration].filter(Boolean).join(" · "))}</small>
            </div>
            <div class="prep">
              <span class="prepcount${s.prepared ? " has" : ""}">${s.prepared || ""}</span>
              <button class="prepbtn" data-spell="${esc(s.id)}"
                data-action="${sp.kind === "prepared" ? "prepare" : "learn"}"
                title="${sp.kind === "prepared" ? "Prepare this" : "Add to the book"}"
                ${g.castable ? "" : "disabled"}>+</button>
            </div>
          </div>`).join("") || `<p class="note">Nothing here matches.</p>`}
        ${hidden > 0 && !find
          ? `<p class="note">and ${hidden} more — search to find them.</p>` : ""}
      </details>`;
    }).join("")}`;
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
  const prep = e.target.closest(".prepbtn");
  if (prep) return prepareSpell(prep.dataset.spell, prep.dataset.action);
});

// The server refuses over-preparing and casting what was never prepared; the page only
// asks. Checking the slot arithmetic here as well would be a second implementation of a
// rule, and the one on screen is the one the player would believe.
async function prepareSpell(spell, action) {
  try {
    SHEET = await post("/api/spells/prepare", {action, spell});
    drawSheet();
  } catch (e) {
    alert(e.message);
  }
}
// The spell search redraws the list as it is typed. The value is kept in SPELL_FIND
// rather than read off the node, because `drawSheet` replaces the node — and the caret is
// put back at the end, which is where somebody typing expects it.
document.addEventListener("input", e => {
  const find = e.target.closest("#spellfind");
  if (!find) return;
  SPELL_FIND = find.value;
  drawSheet();
  const again = document.getElementById("spellfind");
  if (again) { again.focus(); again.setSelectionRange(again.value.length, again.value.length); }
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
  if (e.key === "Escape" && $("#sheetpanel").classList.contains("on")) closeSheet();
});
