// Book and ledger: the views that replace the table. Character, Gear, Spells, Journal, Map.
// Every number is a button that opens what it is made of (full_sheet's own terms).
"use strict";

const mockSwitch = () => `<div class="playing inview" role="group" aria-label="Mock: which character">
  <span>Mock</span>${[["kesst", "Kesst, rogue"], ["ysolde", "Ysolde, wizard"]].map(([k, l]) =>
    `<button type="button" data-char="${k}" aria-pressed="${S.char === k}">${l}</button>`).join("")}</div>`;
const whyBtn = (label, block, text, cls = "num", note = "") =>
  `<button type="button" class="${cls}" data-why="${whyKey(label, block, note)}">${text}</button>`;

// --- Character -------------------------------------------------------------------------------------
VIEWS.character = function () {
  const s = sheet(), id = s.identity, c = me();
  const abil = s.abilities.map(a => `<button type="button" class="num" data-why="${whyKey(a.name, { total: a.score, terms: [{ source: "base", value: a.base }] }, a.damage || a.drain ? `Damage ${a.damage}, drain ${a.drain}.` : "")}">
      <small>${esc(a.name)}</small><b>${a.score}</b><em>${signed(a.modifier)}</em></button>`).join("");
  const saves = s.saves.map(x => whyBtn(x.name, x, `<small>${esc(x.name)}</small><b>${signed(x.total)}</b>`, "stat num")).join("");
  const attacks = s.attacks.map(a => {
    const iter = a.sequence > 1 ? `${signed(a.attack.total)}/${signed(a.attack.total - 5)}` : signed(a.attack.total);
    const range = a.range_ft ? `${a.range_ft} ft` : "melee, 5 ft";
    return `<tr><td><b>${esc(upper(a.name))}</b>${a.equipped ? `<span class="tag on">wielded</span>` : ""}
        <small>${a.hands === 2 ? "two hands" : "one hand"}</small></td>
      <td class="r">${whyBtn(`${upper(a.name)}: to hit`, a.attack, iter)}</td>
      <td>${whyBtn(`${upper(a.name)}: damage`, a.damage, `${a.damage_dice}${a.damage.total ? signed(a.damage.total) : ""}`)}</td>
      <td>${esc(a.crit)}</td><td>${esc(a.type)}</td><td>${range}</td></tr>`;
  }).join("");
  const mans = s.maneuvers.map(m => `<tr><td><b>${esc(upper(m.name))}</b><small>${esc(m.effect)}</small></td>
      <td class="r">${whyBtn(upper(m.name), m.cmb, signed(m.cmb.total))}</td>
      <td>${m.provokes ? `<span class="provokes">Provokes</span>` : `<span class="safe">No</span>`}</td></tr>`).join("");
  const skills = s.skills.map(k => {
    const usable = k.total !== null;
    return `<div class="skillrow${usable ? "" : " untrained"}"><span>${esc(upper(k.name))}${k.class_skill ? `<span class="cls">class</span>` : ""}</span>
      ${usable ? whyBtn(upper(k.name), k, signed(k.total)) : `<span title="Trained only">untrained</span>`}</div>`;
  }).join("");
  const xp = s.xp;
  $("#view-character").innerHTML = `<div class="viewin">
    <div class="charhead">
      <div class="portrait" id="portrait" style="${c.portrait ? `background-image:url(${c.portrait})` : ""}">${c.portrait ? "" : esc(id.name[0])}
        <label for="portrait-in">${c.portrait ? "Change" : "Add a portrait"}</label>
        <input type="file" id="portrait-in" accept="image/*"></div>
      <div><h1>${esc(id.name)}</h1>
        <p class="sub" style="margin:0">${esc(id.class)}, ${esc(id.heritage ? id.heritage + " " : "")}${esc(id.race)}, ${esc(id.pronouns)}. ${esc(c.background)}.</p></div>
      <div class="xp">${mockSwitch()}<span>Experience: <b>${xp.have.toLocaleString()}</b> of ${xp.next.toLocaleString()} for level 2</span>
        <span class="xpbar"><i style="width:${xp.have / xp.next * 100}%"></i></span></div>
    </div>
    <div class="cols charcols">
      <div class="stack">
        <div class="card"><h2>Abilities</h2><div class="abil">${abil}</div></div>
        <div class="card"><h2>Saving throws</h2><div class="defrow">${saves}</div></div>
        <div class="card"><h2>Body <small>what it needs</small></h2>
          <ul class="plainlist">${s.needs.map(n => `<li><b>${esc(n.label)}</b>: ${esc(n.state)}<small>${esc(tidy(n.detail))}</small></li>`).join("")}</ul>
          <p class="railnote">${s.conditions.length ? "Conditions: " + esc(s.conditions.join(", ")) : "No conditions."}</p></div>
        <div class="card"><h2>Features and feats</h2><ul class="plainlist">
          ${s.class_features.map(f => `<li>${esc(upper(f))}<small>${esc(id.class)}</small></li>`).join("")}
          ${s.feats.map(f => `<li>${esc(f)}<small>Feat</small></li>`).join("")}
          ${s.traits.map(t => `<li>${esc(upper(t.name))}<small>${esc(t.source)}</small></li>`).join("")}</ul></div>
      </div>
      <div class="stack">
        <div class="card"><h2>Life <small>${s.hp.nonlethal ? `${s.hp.nonlethal} nonlethal` : "no nonlethal"}</small></h2>
          <div class="hpline">${whyBtn("Hit points", { total: s.hp.max, terms: s.hp_terms }, `<b>${s.hp.current}</b>`, "num")}
            <span>of ${s.hp.max}</span><span class="lifebar"><i style="width:${Math.max(0, s.hp.current) / s.hp.max * 100}%"></i></span></div>
          <div class="defrow">
            ${whyBtn("Armour class", s.ac, `<small>AC</small><b>${s.ac.total}</b>`, "stat num")}
            ${whyBtn("Touch", s.touch, `<small>Touch</small><b>${s.touch.total}</b>`, "stat num")}
            ${whyBtn("Flat-footed", s.flat, `<small>Flat-footed</small><b>${s.flat.total}</b>`, "stat num")}
            ${whyBtn("CMD", s.cmd, `<small>CMD</small><b>${s.cmd.total}</b>`, "stat num")}
            ${whyBtn("CMD, flat-footed", s.cmd_flat, `<small>CMD flat</small><b>${s.cmd_flat.total}</b>`, "stat num")}
            ${whyBtn("Initiative", s.init, `<small>Initiative</small><b>${signed(s.init.total)}</b>`, "stat num")}
          </div>
          <p class="railnote" style="margin:0">Speed ${s.speed} ft. Base attack ${signed(s.bab)}. CMB ${whyBtn("CMB", s.cmb, signed(s.cmb.total))}.</p></div>
        <div class="card"><h2>Attacks <small>every weapon carried</small></h2>
          <div class="tabscroll"><table class="ledger"><thead><tr><th>Weapon</th><th class="r">To hit</th><th>Damage</th>
            <th>Crit</th><th>Type</th><th>Range</th></tr></thead><tbody>${attacks}</tbody></table></div>
          <p class="railnote">One attack a round at base attack ${signed(s.bab)}. A second, at five less, arrives at +6.</p></div>
        <div class="card"><h2>Combat manoeuvres <small>CMB ${signed(s.cmb.total)}</small></h2>
          <div class="tabscroll"><table class="ledger"><thead><tr><th>Manoeuvre</th><th class="r">Bonus</th><th>Provokes</th></tr></thead>
            <tbody>${mans}</tbody></table></div>
          <p class="railnote">Each provokes an attack of opportunity unless you have its Improved feat.</p></div>
      </div>
      <div class="card"><h2>Skills <small>press a total for its parts</small></h2><div class="skilllist">${skills}</div></div>
    </div></div>`;
};
document.addEventListener("change", e => {
  if (e.target.id !== "portrait-in" || !e.target.files[0]) return;
  const r = new FileReader();
  r.onload = () => { me().portrait = r.result; renderBar(); VIEWS.character(); toast("Mock. Shown here only; nothing is stored."); };
  r.readAsDataURL(e.target.files[0]);
});

// --- Gear ------------------------------------------------------------------------------------------------
const SHELVES = [["all", "All"], ["weapons", "Weapons"], ["armour", "Armour"], ["gear", "Gear"],
                 ["consumables", "Consumables"], ["valuables", "Valuables"]];
const SLOTS = [["hand", "Main hand"], ["off", "Off hand"], ["armour", "Armour"], ["clothes", "Clothing"],
               ["back", "Back"], ["belt", "Belt"]];
function purseLine(cp) {
  const out = [];
  for (const [id, per] of [["pp", 1000], ["gp", 100], ["sp", 10], ["cp", 1]]) {
    const n = Math.floor(cp / per); cp -= n * per;
    if (n) out.push(`<span><b>${n}</b> ${esc(COIN[id][1])}${n > 1 ? "s" : ""}</span>`);
  }
  return out.join("");
}
VIEWS.gear = function () {
  const c = me(), gear = c.gear;
  const worn = SLOTS.map(([slot, label]) => {
    const it = gear.find(g => g.slot === slot && g.where);
    return `<div class="slot${it ? "" : " empty"}">${glyph(it ? iconFor(it.name, it.shelf) : "lorc-knapsack")}
      <span class="where">${label}</span><b>${it ? esc(upper(it.name)) : "Nothing"}</b>
      ${it ? `<button type="button" class="btn small" data-off="${it.id}">Take off</button>` : ""}</div>`;
  }).join("");
  const counts = Object.fromEntries(SHELVES.map(([k]) => [k, k === "all" ? gear.length : gear.filter(g => g.shelf === k).length]));
  const q = S.filter.toLowerCase();
  let list = gear.filter(g => (S.shelf === "all" || g.shelf === S.shelf) && (!q || g.name.toLowerCase().includes(q)));
  if (S.sort === "name") list = list.slice().sort((a, b) => a.name.localeCompare(b.name));
  if (S.sort === "value") list = list.slice().sort((a, b) => b.value * b.qty - a.value * a.qty);
  if (S.sort === "shelf") list = list.slice().sort((a, b) => SHELVES.findIndex(s => s[0] === a.shelf) - SHELVES.findIndex(s => s[0] === b.shelf));
  const total = gear.reduce((n, g) => n + g.value * g.qty, 0);
  const acts = g => {
    const b = [];
    if (g.where) b.push(`<button type="button" class="btn small" data-off="${g.id}">Take off</button>`);
    else if (g.shelf === "weapons" && !/bullets/.test(g.name)) b.push(`<button type="button" class="btn small" data-wield="${g.id}">Wield</button>`);
    else if (g.shelf === "armour" || /outfit|backpack|pouch/.test(g.name)) b.push(`<button type="button" class="btn small" data-wear="${g.id}">Wear</button>`);
    else if (g.shelf === "consumables") b.push(`<button type="button" class="btn small" data-use="${g.id}">Use</button>`);
    b.push(`<button type="button" class="btn small quiet" data-drop="${g.id}">Drop</button>`);
    return b.join("");
  };
  const items = list.length ? list.map(g => `<div class="item${g.where ? " worn" : ""}">${glyph(iconFor(g.name, g.shelf))}
      <b>${esc(upper(g.name))}${g.qty > 1 ? `<span class="qty">&times;${g.qty}</span>` : ""}</b>
      <small>${g.value ? `${money(g.value)}${g.qty > 1 ? " each" : ""}` : "no market price"}${g.note ? `, ${esc(g.note)}` : ""}${g.ex ? ` <span class="ex">(example)</span>` : ""}</small>
      <span class="acts">${acts(g)}</span></div>`).join("")
    : `<p class="empty">Nothing here${q ? ` matches “${esc(S.filter)}”` : ""}.</p>`;
  $("#view-gear").innerHTML = `<div class="viewin">
    <h1>Gear</h1><p class="sub">${gear.length} things carried, worth ${money(total)} at market. Bought and sold at a counter in play, with Trade.</p>
    <div class="cols gearcols">
      <div class="stack">
        <div class="card"><h2>On you</h2>${worn}
          <p class="railnote">Magic item slots (head, eyes, neck, shoulders, wrists, hands, rings, feet): all empty.</p></div>
        <div class="card"><h2>Purse</h2><div class="purse">${purseLine(c.purse)}</div>
          <p class="railnote">The world's coin: coined by the app for Zhilvarnia from its own names.</p></div>
      </div>
      <div class="card">
        <h2>Carried <small>names always shown</small></h2>
        <div class="shelftabs" role="tablist" aria-label="Kinds">${SHELVES.map(([k, l]) => `<button type="button" role="tab"
          aria-selected="${S.shelf === k}" data-shelf="${k}">${l}<small>${counts[k]}</small></button>`).join("")}</div>
        <div class="filter"><label class="vh" for="gearq">Find in your pack</label>
          <input id="gearq" type="search" placeholder="Find in your pack" value="${esc(S.filter)}">
          <label class="vh" for="gearsort">Order</label>
          <select id="gearsort">${[["shelf", "By kind"], ["name", "By name"], ["value", "By value"]].map(([v, l]) =>
            `<option value="${v}"${S.sort === v ? " selected" : ""}>${l}</option>`).join("")}</select></div>
        <div class="items">${items}</div>
      </div>
    </div></div>`;
};
function gearAct(e) {
  const find = id => me().gear.find(g => g.id === id);
  const t = e.target.closest("[data-shelf],[data-off],[data-wield],[data-wear],[data-use],[data-drop]");
  if (!t || S.mode !== "gear") return;
  const d = t.dataset;
  if (d.shelf) S.shelf = d.shelf;
  if (d.off) { const g = find(d.off); g.where = ""; toast(`${upper(g.name)}: taken off, carried.`); }
  if (d.wield) {
    const g = find(d.wield);
    me().gear.filter(x => x.slot === "hand").forEach(x => { x.where = ""; });
    g.slot = "hand"; g.where = "main hand";
    sheet().attacks.forEach(a => { a.equipped = a.name.toLowerCase() === g.name.toLowerCase(); });
    toast(`Wielding the ${g.name}. A move action in a fight.`);
  }
  if (d.wear) {
    const g = find(d.wear);
    const slot = g.shelf === "armour" ? "armour" : /outfit/.test(g.name) ? "clothes" : /pouch/.test(g.name) ? "belt" : "back";
    me().gear.filter(x => x.slot === slot).forEach(x => { x.where = ""; });
    g.slot = slot; g.where = slot; toast(`Wearing the ${g.name}.`);
  }
  if (d.use) { const g = find(d.use); g.qty -= 1; if (!g.qty) me().gear.splice(me().gear.indexOf(g), 1); toast(`Mock. Used one ${g.name}; the engine would apply what it does.`); }
  if (d.drop) {
    const g = find(d.drop); me().gear.splice(me().gear.indexOf(g), 1);
    toast(`Dropped the ${g.name}. It lies at ${place().name}, where you can pick it up again.`);
  }
  const keep = document.activeElement && document.activeElement.id;
  VIEWS.gear(); paintIcons($("#view-gear"));
  if (keep === "gearq") { const i = $("#gearq"); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }
}
document.addEventListener("click", gearAct);
document.addEventListener("input", e => {
  if (e.target.id !== "gearq") return;
  S.filter = e.target.value; VIEWS.gear(); paintIcons($("#view-gear"));
  const i = $("#gearq"); i.focus(); i.setSelectionRange(i.value.length, i.value.length);
});
document.addEventListener("change", e => {
  if (e.target.id !== "gearsort") return;
  S.sort = e.target.value; VIEWS.gear(); paintIcons($("#view-gear"));
});

// --- Spells: sockets, prepared cards, the book ---------------------------------------------------------
function spellRows(sp, dc) {
  const rows = [["Casting", sp.casting_time], ["Range", sp.range], ["Target", sp.targets || sp.area || sp.effect],
                ["Duration", sp.duration],
                ["Save", sp.saving_throw && sp.saving_throw !== "none" ? `${sp.saving_throw}, DC ${dc}` : "none"],
                ["Resistance", sp.spell_resistance || "no"]];
  return rows.filter(r => r[1]).map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("");
}
VIEWS.spells = function () {
  const c = me().caster, s = sheet();
  if (!c) { $("#view-spells").innerHTML = ""; return; }
  const pools = s.pools;
  const sockets = pools.map(p => {
    const lvl = +p.id.split(" ").pop();
    if (lvl === 0) return `<div class="slotrow"><b>Cantrips</b><div class="sockets">${Array.from({ length: p.max }, () => `<span class="socket" aria-hidden="true"></span>`).join("")}</div>
      <small>${p.max} prepared, cast at will</small></div>`;
    const used = c.spent[lvl] || 0;
    return `<div class="slotrow"><b>Level ${lvl}</b><div class="sockets" role="img" aria-label="${p.max - used} of ${p.max} open">${Array.from({ length: p.max }, (_, i) =>
      `<span class="socket${i >= p.max - used ? " spent" : ""}"></span>`).join("")}</div>
      <small>${p.max - used} of ${p.max} open today${used ? `, ${used} spent` : ""}</small></div>`;
  }).join("");
  const cards = [0, 1].map(lvl => (c.prepared[lvl] || []).map(id => {
    const sp = D.spells[id];
    const out = lvl > 0 && slotsLeft(lvl) <= 0;
    return `<article class="spell${out ? " spent" : ""}">${glyph(SPELL_ICON[id], "spells")}
      <h3>${esc(sp.name)}</h3><span class="meta">${lvl ? `Level ${lvl}` : "Cantrip"}, ${esc(sp.school)}</span>
      <dl>${spellRows(sp, c.dcBase + lvl)}</dl>
      <div class="acts"><button type="button" class="btn small" data-spell="${id}">Details</button>
        <button type="button" class="btn small primary" data-attach="${id}"${out ? " disabled" : ""}>Cast</button></div></article>`;
  }).join("")).join("");
  const book = Object.entries(D.spells).sort((a, b) => a[1].level - b[1].level || a[1].name.localeCompare(b[1].name))
    .map(([id, sp]) => `<button type="button" data-spell="${id}">${glyph(SPELL_ICON[id] || "lorc-potion-ball", "spells")}
      <span>${esc(sp.name)}</span><small>${sp.level ? "level " + sp.level : "cantrip"}</small></button>`).join("");
  $("#view-spells").innerHTML = `<div class="viewin">
    ${mockSwitch()}<h1>Spells</h1><p class="sub">${esc(s.identity.class)}. Save DC 13 plus the spell's level (10, Int +3). Caster level ${c.cl}.</p>
    <div class="cols" style="grid-template-columns:minmax(0,1fr)">
      <div class="card"><h2>Today's slots <small>lit is open, red is spent</small></h2><div class="slots">${sockets}</div>
        <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
          <button type="button" class="btn" id="rest">Rest and prepare, 9 hours</button></div>
        <p class="railnote">Slots return after eight hours' rest and an hour with the book.</p></div>
      <div><h2>Prepared <small>Cast puts the spell on your turn as a chip; it is not sent until you act</small></h2>
        <div class="spellcards">${cards}</div></div>
      <div class="card"><h2>The book <small>${Object.keys(D.spells).length} spells; prepared at rest</small></h2>
        <div class="book-list">${book}</div></div>
    </div></div>`;
};
function spellDetails(id) {
  const sp = D.spells[id], c = me().caster;
  const dlg = $("#details");
  dlg.innerHTML = `<h2>${esc(sp.name)}</h2><p>${sp.level ? `Level ${sp.level}` : "Cantrip"}, ${esc(sp.school)}; ${esc((sp.components || []).join(", "))}</p>
    <dl>${spellRows(sp, (c ? c.dcBase : 13) + sp.level)}</dl>
    <div class="spelltext">${esc(sp.description)}</div>
    <div class="acts"><button type="button" class="btn" data-dlg-close>Close</button>
      ${c && Object.values(c.prepared).flat().includes(id) ? `<button type="button" class="btn primary" data-attach="${id}" data-dlg-close>Cast</button>` : ""}</div>`;
  dlg.showModal();
}
document.addEventListener("click", e => {
  const s = e.target.closest("[data-spell]");
  if (s) spellDetails(s.dataset.spell);
  if (e.target.id === "rest") {
    me().caster.spent = {};
    const slip = advance(9 * 60, "eight hours' sleep and an hour with the book");
    S.beats.push(beat("oc", "Mock. You rest and prepare. Slots are back; the narrator would write the night.", [slip]));
    renderStory(); VIEWS.spells(); paintIcons($("#view-spells"));
  }
});

// --- Journal ----------------------------------------------------------------------------------------------
VIEWS.journal = function () {
  const by = {};
  D.said.forEach(s => { (by[s.who] = by[s.who] || []).push(s.line); });
  const today = S.beats.flatMap(b => b.slips.filter(x => x.type === "time" || x.type === "move").map(x =>
    x.type === "time" ? `<li><time>${esc(x.to)}</time><span>${esc(upper(x.words))}</span></li>`
      : `<li><time></time><span>${esc(upper(x.from))} to ${esc(x.to)}</span></li>`)).join("");
  $("#view-journal").innerHTML = `<div class="viewin">
    <h1>Journal</h1><p class="sub">Day ${S.day}, ${hhmm(S.minutes)}, ${esc(partOf(S.minutes))}. What is afoot, and what people said.</p>
    <div class="cols jcols">
      <div class="stack">
        <div class="card"><h2>Matters in play</h2>
          <div class="matter"><b>A meal you could afford and the name of somebody who hires</b><small>Opened at the start</small></div>
          <div class="matter"><b>Economic competition between Khy'vyr clans and Nirkor merchants</b><small>From the smith, at the merchants row</small></div>
          <p class="railnote">Both names are the recording's own.</p></div>
        <div class="card"><h2>The road so far</h2><ul class="daylog">${today || "<li>Nothing yet.</li>"}</ul></div>
      </div>
      <div class="card"><h2>What people said <small>word for word</small></h2>
        ${Object.entries(by).map(([who, lines]) => `<p class="saidby">${esc(upper(who))}</p>${lines.map(l => `<p class="saidline">${esc(tidy(l))}</p>`).join("")}`).join("")}</div>
    </div></div>`;
};

// --- Map: the place graph the exits walk ----------------------------------------------------------------
// Laid out here by a small spring model from the exits alone. The world export has no
// coordinates, so any drawing is an arrangement, not a survey; the README says so.
let LAYOUT = null;
function layout() {
  if (LAYOUT) return LAYOUT;
  const ids = Object.keys(D.places);
  const edges = [];
  const seen = new Set();
  ids.forEach(a => D.places[a].exits.forEach(x => {
    const b = x[0];
    if (!D.places[b]) return;
    const k = [a, b].sort().join("|");
    if (!seen.has(k)) { seen.add(k); edges.push([a, b, x[2] === "o" || x[2] === "r"]); }
  }));
  // Rings by distance from the great square: a stable start the springs only tidy.
  const hub = ids.find(i => /great-square/.test(i)) || ids[0];
  const depth = { [hub]: 0 }, q = [hub];
  while (q.length) {
    const a = q.shift();
    D.places[a].exits.forEach(x => { if (D.places[x[0]] && depth[x[0]] === undefined) { depth[x[0]] = depth[a] + 1; q.push(x[0]); } });
  }
  const rings = {};
  ids.forEach(i => { const d = depth[i] ?? 6; (rings[d] = rings[d] || []).push(i); });
  const P = {};
  Object.entries(rings).forEach(([d, list]) => list.forEach((id, k) => {
    const a = (k / list.length) * Math.PI * 2 + d * .7;
    P[id] = [Math.cos(a) * (d * 95 + 10), Math.sin(a) * (d * 70 + 8)];
  }));
  for (let it = 0; it < 420; it++) {
    const F2 = Object.fromEntries(ids.map(i => [i, [0, 0]]));
    for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
      const a = P[ids[i]], b = P[ids[j]];
      let dx = a[0] - b[0], dy = a[1] - b[1]; const d2 = dx * dx + dy * dy + .01, d = Math.sqrt(d2);
      const rep = 5200 / d2;
      F2[ids[i]][0] += dx / d * rep; F2[ids[i]][1] += dy / d * rep;
      F2[ids[j]][0] -= dx / d * rep; F2[ids[j]][1] -= dy / d * rep;
    }
    edges.forEach(([a, b]) => {
      const pa = P[a], pb = P[b]; const dx = pb[0] - pa[0], dy = pb[1] - pa[1];
      const d = Math.sqrt(dx * dx + dy * dy) + .01, f = (d - 78) * .045;
      F2[a][0] += dx / d * f; F2[a][1] += dy / d * f; F2[b][0] -= dx / d * f; F2[b][1] -= dy / d * f;
    });
    ids.forEach(i => { P[i][0] += Math.max(-8, Math.min(8, F2[i][0])); P[i][1] += Math.max(-8, Math.min(8, F2[i][1])) * .8; });
  }
  // Squash to a landscape frame, the shape of the column it is drawn in: the springs settle
  // tall, and a tall map had the gate below the fold at 1440x900.
  let xs = ids.map(i => P[i][0]), ys = ids.map(i => P[i][1]);
  const wide = Math.max(...xs) - Math.min(...xs), tall = Math.max(...ys) - Math.min(...ys);
  if (tall / wide > .62) ids.forEach(i => { P[i][1] *= .62 * wide / tall; });
  xs = ids.map(i => P[i][0]); ys = ids.map(i => P[i][1]);
  const x0 = Math.min(...xs) - 70, y0 = Math.min(...ys) - 30;
  LAYOUT = { P, edges, ids, box: [x0, y0, Math.max(...xs) - x0 + 70, Math.max(...ys) - y0 + 30] };
  return LAYOUT;
}
function route(to) {
  const prev = { [S.place]: null }, q = [S.place];
  while (q.length) {
    const a = q.shift();
    if (a === to) break;
    (S.wanted ? D.places[a].wanted : D.places[a].exits).forEach(x => {
      if (x[4] >= 0 || x[5] || !D.places[x[0]] || x[0] in prev) return;
      prev[x[0]] = [a, x]; q.push(x[0]);
    });
  }
  if (!(to in prev)) return null;
  const legs = []; let k = to;
  while (prev[k]) { legs.unshift(prev[k][1]); k = prev[k][0]; }
  return legs;
}
VIEWS.map = function () {
  const L = layout();
  const near = new Set(exitsHere().map(x => x[0]));
  const sel = S.mapSel;
  const edges = L.edges.map(([a, b, road]) => `<line class="edge${road ? " road" : ""}" x1="${L.P[a][0]}" y1="${L.P[a][1]}" x2="${L.P[b][0]}" y2="${L.P[b][1]}"/>`).join("");
  const nodes = L.ids.map(id => {
    const p = D.places[id], [x, y] = L.P[id];
    const cls = id === S.place ? " here" : near.has(id) ? " near" : "";
    return `<g class="node${cls}${p.setting === "outside" ? " out" : ""}${sel === id ? " sel" : ""}" data-node="${esc(id)}" tabindex="0" role="button"
      aria-label="${esc(p.name)}${id === S.place ? ", you are here" : ""}"><circle cx="${x}" cy="${y}" r="${id === S.place ? 8 : 6}"/>
      <text x="${x + 10}" y="${y + 4}">${esc(p.name.replace(/^the /, ""))}</text></g>`;
  }).join("");
  let side = `<div class="card"><h2>${esc(upper(place().name))} <small>you are here</small></h2>
      <p class="railnote" style="margin:0">Press a place for the way there. The drawing comes from the exits alone; the world gives no coordinates, so distance on it means nothing.</p></div>`;
  if (sel && sel !== S.place) {
    const legs = route(sel);
    const mins = legs ? legs.reduce((n, x) => n + (MINUTES[x[3]] || 5), 0) : 0;
    side = `<div class="card"><h2>${esc(upper(D.places[sel].name))}</h2>
      ${legs ? `<ol class="route">${legs.map(x => `<li>${esc(upper(x[1]))}<span>${esc(walkWords(x[3]))}</span></li>`).join("")}</ol>
        <p class="railnote" style="margin:0 0 10px">About ${mins} minutes on foot, by the way above.</p>
        <button type="button" class="btn primary" data-walkto="${esc(sel)}">Walk there</button>`
      : `<p class="shutwhy">No open way there from ${esc(place().name)}${S.wanted ? ": the watch holds the ways you would need" : ""}.</p>`}</div>` + side;
  }
  const [x0, y0, w, h] = L.box;
  $("#view-map").innerHTML = `<div class="viewin"><h1>Zhilvarnia</h1>
    <p class="sub">${L.ids.length} places the rules know, joined by their ways. Solid lines are next door; dashed lead outside the walls.</p>
    <div class="cols mapcols"><div class="mapwrap"><svg viewBox="${x0} ${y0} ${w} ${h}" role="group" aria-label="The place graph">${edges}${nodes}</svg></div>
      <div class="maprail">${side}</div></div></div>`;
};
document.addEventListener("click", e => {
  const n = e.target.closest("[data-node]");
  if (n && S.mode === "map") { S.mapSel = n.dataset.node; VIEWS.map(); return; }
  const w = e.target.closest("[data-walkto]");
  if (w) {
    const legs = route(w.dataset.walkto);
    if (!legs) return;
    const from = place().name;
    const mins = legs.reduce((k, x) => k + (MINUTES[x[3]] || 5), 0);
    S.place = w.dataset.walkto; S.talk = null; S.mapSel = null;
    S.beats.push(beat("you", `I walk to ${D.places[S.place].name}, by ${legs.slice(0, -1).map(x => x[1]).join(", ") || "the nearest way"}.`),
      placeBeat(S.place),
      beat("oc", "Mock. The engine walks each leg in turn and stops the walk if anything happens on the way.",
        [{ type: "move", from, to: D.places[S.place].name }, advance(mins, `${legs.length} leg${legs.length > 1 ? "s" : ""} on foot`)]));
    setMode("table"); renderStory(); renderRail(); renderDock();
    const box = $("#beats"); box.scrollTop = box.scrollHeight;
  }
});
document.addEventListener("keydown", e => {
  const n = e.target.closest && e.target.closest("[data-node]");
  if (n && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); S.mapSel = n.dataset.node; VIEWS.map(); $(`[data-node="${CSS.escape(S.mapSel)}"]`).focus(); }
});
