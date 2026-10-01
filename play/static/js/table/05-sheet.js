// The play table, part 05 (the sheet's pages). Split out of play/templates/play/table.html
// on 2026-09-25; classic scripts, loaded in order, sharing one global scope.
//
// The table rebuild, stage 2 (docs/table-rebuild-inventory.md; the owner's approved
// design, docs/mock/table-layout/, README in full): each of the Sheet, Equipment, Spells
// and Journal tabs is one page of the sheet, drawn here into `#sheetbody`, which
// 17-tab-sheet.js carries into whichever of those tabs is open. The old sheet's twelve
// pages behind a strip of tabs are gone: the Sheet tab is one column of framed cards
// (Combat first, then Defence, Skills, Feats, Class, Background), Equipment is the
// design's shelves, list and Worn and wielded, Spells is the I5 page restyled, and
// Journal is the matters in play and what people said.
//
// Every number drawn here is the engine's, read from `/api/sheet` (rules/sheet.py
// `full_sheet`, plus play/views.py `_carried` for Equipment). Nothing is added up here:
// where the engine has no number the page says "not known" (the mock README, "What the
// engine does not know"), and tests/test_sheet_pages.py runs these functions in node to
// hold them to it.

const TABS = [
  ["sheet",     "Sheet",     s => pageSheet(s)],
  ["equipment", "Equipment", s => pageEquipment(s)],
  ["spells",    "Spells",    s => tabSpells(s)],
  ["journal",   "Journal",   s => pageJournal(s)],
];

// --- shared bits ---------------------------------------------------------------------
const tabEmpty = msg => `<div class="empty">${esc(msg)}</div>`;
const NOT_KNOWN = `<span class="unknown">not known</span>`;
// "base 10, Dex +3": the 10 an AC and a CMD start from is a number, not a bonus; a term
// worth nothing says nothing.
const termLine = t => ((t && t.terms) || []).filter(m => m.value)
  .map(m => `${m.source} ${m.source === "base" ? m.value : sign(m.value)}`).join(", ");
const words = n => ["no", "one", "two", "three", "four", "five", "six"][n] || String(n);
// A framed card: the theme's gilt ring, clasps and bosses on the card leather.
const sheetCard = (id, title, body, cls = "") => `
  <section class="v2-framed v2-card-leather sheetcard${cls ? " " + cls : ""}"
           aria-labelledby="${id}"><i class="v2-rim" aria-hidden="true"></i>
    <h2 id="${id}">${title}</h2>${body}
  </section>`;
// A number standing on its own plaque, with what it is made of beneath it.
const stat = (dt, dd, why = "", small = "") => `<div class="stat v2-plaque"><dt>${dt}</dt>
  <dd>${dd}${small ? ` <small>${small}</small>` : ""}</dd>${
  why ? `<span class="why">${esc(why)}</span>` : ""}</div>`;

// --- The Sheet tab --------------------------------------------------------------------
// "Sheet mode now opens on a Combat card" (the mock README, point 4: "the sheet is
// missing a ton of information from the available combat maneuvers and weapon attacks").
function pageSheet(s) {
  return `<div class="sheetcards">
    ${combatCard(s)}
    ${defenceCard(s)}
    ${skillsCard(s)}
    ${featsCard(s)}
    ${classCard(s)}
    ${backgroundCard(s)}
  </div>`;
}

// Initiative, base attack, CMB, CMD and speed, each with its terms; every carried weapon,
// each swing of a full attack at its own bonus; the full attack in a sentence; all ten
// manoeuvres and feint.
function combatCard(s) {
  const o = s.offense, d = s.defense;
  const speed = d.speed || {};
  const attacks = (o.attacks || []).slice()
    .sort((a, b) => (b.equipped ? 1 : 0) - (a.equipped ? 1 : 0));
  const hands = a => (a.hands === 2 ? "two-handed" : a.light ? "light" : "one-handed");
  const rows = attacks.map(a => {
    const notes = [hands(a), a.finessable ? "finesse" : "", ...(a.traits || []),
                   a.weight_lb != null ? `${a.weight_lb} lb` : ""].filter(Boolean);
    const thrown = a.category === "melee" && a.range_ft;
    const swings = (a.swings && a.swings.length ? a.swings : [a.attack.total]).map(sign);
    // data-label: on a phone each row folds into a small card that says what each is.
    return `<tr class="${a.equipped ? "inhand" : ""}">
      <td class="lead"><b>${esc(a.name)}</b>${a.equipped ? `<span class="chip">in hand</span>` : ""}${
        a.proficient ? "" : `<span class="chip warn">not proficient</span>`}</td>
      <td class="n" data-label="To hit">${swings.join(" / ")}<span class="why">${
        esc(termLine(a.attack)) || "no bonus"}</span></td>
      <td class="n" data-label="Damage">${esc(a.damage_dice)}${a.damage.total ? sign(a.damage.total) : ""}<span
        class="why">${esc(a.type_text || a.type)}</span></td>
      <td class="n" data-label="Critical">${esc(a.crit)}</td>
      <td data-label="Range">${a.range_ft ? `${a.range_ft} ft${thrown ? ", thrown" : ""}`
        : a.category === "melee" ? `<span class="why">melee</span>`
        : a.launcher ? NOT_KNOWN : `<span class="why">not printed</span>`}${
        thrown ? `<span class="why"><span class="unknown">thrown to-hit not known</span></span>` : ""}</td>
      <td class="wide" data-label="Notes"><span class="why">${esc(notes.join(", "))}</span></td>
    </tr>`;
  }).join("");
  const held = attacks.find(a => a.equipped);
  const heldSwings = held && held.swings && held.swings.length ? held.swings : null;
  const full = held && heldSwings
    ? `Full attack with the ${esc(held.name)}: ${words(heldSwings.length)} swing${
      heldSwings.length === 1 ? "" : "s"}, at ${heldSwings.map(sign).join(" then ")}.`
    : "Full attack: nothing in hand.";
  const man = (o.maneuvers || []).map(m => {
    const limits = [m.size_limit != null ? "no more than one size larger" : "",
                    m.two_hands ? "needs both hands free" : ""].filter(Boolean).join("; ");
    return `<tr><td class="lead"><b>${esc(m.name)}</b></td>
      <td class="n" data-label="Bonus">${sign(m.cmb.total)}</td>
      <td data-label="Provokes">${m.provokes ? "Yes" : "No"}</td>
      <td class="wide" data-label="On success">${esc(m.effect)}</td>
      <td class="wide${limits ? "" : " none"}" data-label="Limits"><span class="why">${
        esc(limits)}</span></td></tr>`;
  }).join("");
  const f = o.feint || {};
  const feint = `<tr><td class="lead"><b>feint</b></td>
    <td class="n" data-label="Bonus">${f.usable && f.total != null ? sign(f.total) : NOT_KNOWN}<span
      class="why">Bluff</span></td>
    <td data-label="Provokes">${NOT_KNOWN}</td>
    <td class="wide" data-label="On success">Rolled as a Bluff check. The target losing its
      Dexterity to AC is <span class="unknown">not in the rules yet</span>.</td>
    <td class="wide none" data-label="Limits"></td></tr>`;
  return sheetCard("sc-combat", "Combat", `
    <dl class="statrow">
      ${stat("Initiative", sign(o.initiative.total), termLine(o.initiative))}
      ${stat("Base attack", sign(o.bab))}
      ${stat("CMB", sign(o.cmb.total), termLine(o.cmb))}
      ${stat("CMD", d.cmd.total, termLine(d.cmd), `flat-footed ${d.cmd_flat_footed.total}`)}
      ${stat("Speed", speed.current != null ? `${speed.current} ft` : NOT_KNOWN,
             speed.base != null && speed.base !== speed.current ? `base ${speed.base} ft` : "")}
    </dl>
    <div class="gridwrap"><table class="grid">
      <caption class="vh">Attacks</caption>
      <thead><tr><th scope="col">Weapon</th><th scope="col">To hit</th><th scope="col">Damage</th>
        <th scope="col">Critical</th><th scope="col">Range</th><th scope="col">Notes</th></tr></thead>
      <tbody>${rows || `<tr><td class="lead" colspan="6"><span class="why">No weapon carried.</span></td></tr>`}</tbody>
    </table></div>
    <p class="fullattack">${full}</p>
    <h3 class="cardsub">Combat manoeuvres</h3>
    <p class="why">Each is your bonus rolled against the target's CMD.</p>
    <div class="gridwrap"><table class="grid">
      <caption class="vh">Combat manoeuvres</caption>
      <thead><tr><th scope="col">Manoeuvre</th><th scope="col">Bonus</th>
        <th scope="col">Provokes</th><th scope="col">On success</th><th scope="col">Limits</th></tr></thead>
      <tbody>${man}${feint}</tbody>
    </table></div>
    <p class="why">Provokes is read from the rules' manoeuvre table. No attack of opportunity
      is rolled for a manoeuvre yet: only moving provokes one.</p>`);
}

// AC, touch and flat-footed, the saves with their terms, life's edges, and conditions.
// The abilities and life are on the right-hand panel beside this column.
function defenceCard(s) {
  const d = s.defense;
  const hp = d.hp || {};
  const con = (s.abilities || []).find(a => a.key === "con");
  const saves = (d.saves || []).map(sv => stat(sv.name, sign(sv.total), termLine(sv) || "no bonus")).join("");
  const life = [
    `<div class="t"><span>Hit points</span><b>${hp.current} of ${hp.max}</b></div>`,
    hp.temp ? `<div class="t"><span>Temporary${hp.temp_source ? `, from ${esc(hp.temp_source)}` : ""}</span><b>${sign(hp.temp)}</b></div>` : "",
    ...(d.dr || []).map(r => `<div class="t"><span>Damage reduction${r.source ? `, from ${esc(r.source)}` : ""}</span><b>${esc(r.label)}</b></div>`),
    `<div class="t"><span>Unconscious at</span><b>0</b></div>`,
    con ? `<div class="t"><span>Dead at</span><b>-${con.score}</b></div>` : "",
    `<div class="t"><span>Non-lethal taken</span><b>${hp.nonlethal || 0}</b></div>`,
    `<div class="t"><span>Knocked out by non-lethal at</span><b>${hp.nonlethal_threshold}</b></div>`,
  ].join("");
  const gear = (d.gear || []).length ? `<h3 class="cardsub">Damaged gear</h3>
    <div class="terms">${d.gear.map(g => `<div class="t"><span>${esc(g.name)} <small>${
      esc(g.material)}, hardness ${g.hardness}</small></span><b>${
      g.state === "destroyed" ? "destroyed" : `${g.hp} of ${g.hp_max}${
        g.state === "broken" ? ", broken" : ""}`}</b></div>`).join("")}</div>` : "";
  return sheetCard("sc-defence", "Defence", `
    <dl class="statrow">
      ${stat("AC", d.ac.total, termLine(d.ac))}
      ${stat("Touch", d.ac_touch.total, termLine(d.ac_touch))}
      ${stat("Flat-footed", d.ac_flat_footed.total, termLine(d.ac_flat_footed))}
      ${saves}
    </dl>
    <div class="twocol">
      <div><h3 class="cardsub">Life</h3><div class="terms">${life}</div>${gear}</div>
      <div><h3 class="cardsub">Conditions</h3>
        ${(d.conditions || []).length ? `<ul class="plain conds">${d.conditions.map(c => `<li>
          <b>${esc(c.name)}</b>${c.rounds_left ? ` <span class="chip">${c.rounds_left} rounds</span>` : ""}
          ${c.note ? `<span class="why">${esc(c.note)}</span>` : ""}
          ${c.source ? `<span class="why">from ${esc(c.source)}</span>` : ""}</li>`).join("")}</ul>`
          : `<p>None.</p>`}
      </div>
    </div>`);
}

// Two columns of skills, each total the engine's. What each is made of is one press
// away (the old Skills page showed it on every row, 35 rows of it).
let SKILL_TERMS = false;
function skillsCard(s) {
  const trained = s.skills.filter(k => k.rank > 0).length;
  return sheetCard("sc-skills", "Skills", `
    <p class="cardline"><span class="why">${trained} trained. Untrained-only skills that
      cannot be tried are greyed.</span>
      <button type="button" class="v2-btn is-quiet is-small" id="skillterms"
              aria-pressed="${SKILL_TERMS}">What each is made of</button></p>
    <dl class="skills${SKILL_TERMS ? " showterms" : ""}" id="skilllist">${s.skills.map(k => `
      <div class="${k.usable ? "" : "dim"}">
        <dt>${esc(title(k.name))}${k.class_skill ? ` <small class="cls">class</small>` : ""}${
          k.trained_only ? ` <small>trained only</small>` : ""}</dt>
        <dd>${k.usable ? sign(k.total) : `<span title="Cannot be attempted untrained">untrained</span>`}</dd>
        <span class="why terms-line">${esc(k.ability.toUpperCase())}${
          k.armour_check ? ", armour check applies" : ""}${k.rank ? `, ${k.rank} ranks` : ""}${
          k.usable && k.terms.length ? `: ${esc(k.terms.map(m => `${sign(m.value)} ${m.source}`).join(", "))}` : ""}</span>
      </div>`).join("")}</dl>`);
}
document.addEventListener("click", e => {
  const b = e.target.closest("#skillterms");
  if (!b) return;
  SKILL_TERMS = !SKILL_TERMS;
  b.setAttribute("aria-pressed", String(SKILL_TERMS));
  const list = document.getElementById("skilllist");
  if (list) list.classList.toggle("showterms", SKILL_TERMS);
});

// --- Feats ---
// The browse pane's last result, so a redraw does not lose it and typing does not refetch
// on every keystroke.
let FEAT_RESULTS = null;
let FEAT_QUERY = "";

function featsCard(s) {
  return sheetCard("sc-feats", "Feats and traits", tabFeats(s), "wide");
}

function tabFeats(s) {
  const feats = (s.feats || []).map(f => `<div class="${f.applied ? "" : "dim"}">
      <dt>${esc(f.name)}${f.applied ? "" : f.known ? ` <span class="chip">not computed</span>`
        : ` <span class="chip warn">unknown feat</span>`}${
        f.prerequisites ? `<small class="prereq">${esc(f.prerequisites)}</small>` : ""}</dt>
      <dd>${esc(f.effect)}</dd></div>`).join("");
  const body = s.body || {};
  const moves = Object.entries(body.speeds || {});
  const showBody = moves.length > 1 || (body.senses || []).length || (body.natural_weapons || []).length;
  return `<div class="twocol">
    <div>
      <dl class="feats">${feats || `<p>None.</p>`}</dl>
      <p class="why">"Not computed" means the rules carry the feat and its text but apply no
        number for it; those are yours to invoke at the table.</p>
      ${(s.traits || []).length ? `<h3 class="cardsub">Racial traits</h3>
        <dl class="feats">${s.traits.map(t => `<div><dt>${glossify(t.name)}</dt>
          <dd>${esc(t.source)}</dd></div>`).join("")}</dl>` : ""}
      ${showBody ? `<h3 class="cardsub">The body</h3><dl class="feats">
        <div><dt>Moves</dt><dd>${esc(moves.map(([k, v]) => `${k} ${v} ft`).join(", "))}</dd></div>
        ${(body.senses || []).length ? `<div><dt>Senses</dt><dd>${esc(body.senses.join(", "))}</dd></div>` : ""}
        ${(body.natural_weapons || []).map(w => `<div><dt>${esc(w.name)}</dt><dd>${
          w.count > 1 ? `${w.count} of them, ` : ""}${esc(w.damage)} ${esc(w.type)}${
          w.secondary ? ", secondary" : ""}</dd></div>`).join("")}
        ${(body.not_yet || []).map(n => `<div><dt>Not yet</dt><dd>${esc(n)}</dd></div>`).join("")}
      </dl>` : ""}
      ${(s.class_features || []).length ? `<h3 class="cardsub">Class features</h3>
        <dl class="feats">${s.class_features.map(f => `<div><dt>${glossify(f)}</dt>
          <dd>${esc(s.identity.class)}</dd></div>`).join("")}</dl>` : ""}
    </div>
    <div>
      <h3 class="cardsub">Browse the feats</h3>
      <label class="vh" for="featq">Search the feats</label>
      <input type="search" id="featq" class="v2-well" placeholder="Search 1,474 feats"
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
        <small>${esc([f.types.join(", "), f.source].filter(Boolean).join(", "))}</small></div>
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

// --- Class, and taking a level ---
function classCard(s) {
  return sheetCard("sc-class", "Class", tabClass(s), "wide");
}

function tabClass(s) {
  const p = s.progression;
  if (!p || !p.rows) return tabEmpty("No class data for this character.");
  // Every column the class prints on its own table, gathered from the rows rather
  // than named here: a class with columns this app has never heard of still shows
  // them, which is the whole point of the classes being data.
  const cols = [...new Set(p.rows.flatMap(r => Object.keys(r.columns || {})))];
  return `<div class="twocol">
    <div>
      <h3 class="cardsub">${esc(p.class)}</h3>
      ${p.summary ? `<p class="why">${esc(p.summary)}</p>` : ""}
      <div class="terms">
        <div class="t"><span>Hit die</span><b>${esc(String(p.hit_die))}</b></div>
        <div class="t"><span>Base attack</span><b>${esc(String(p.bab).replace(/_/g, " "))}</b></div>
        <div class="t"><span>Good saves</span><b>${esc((p.good_saves || []).join(", ") || "none")}</b></div>
        <div class="t"><span>Skill ranks</span><b>${p.skill_ranks} plus Int</b></div>
      </div>
      ${(p.paths_offered || []).length ? `
        <h3 class="cardsub">Paths</h3>
        <p class="why">This class follows two paths, in order. Path A runs from 1st level;
          Path B stays shut until its track opens at ${p.unlocks_b || 11}th.
          ${p.paths_taken.length ? `You follow <b>${esc(p.paths_taken[0])}</b> as Path A${
            p.paths_taken[1] ? ` and <b>${esc(p.paths_taken[1])}</b> as Path B` : ""}.`
            : "This character has none recorded."}</p>
        <div class="terms">
          <div class="t"><span>Path A: ${esc(p.paths_taken[0] || "not chosen")}</span>
            <b>Control Blood ${(p.control_blood || {}).a || 0}</b></div>
          <div class="t"><span>Path B: ${esc(p.paths_taken[1] || "not chosen")}</span>
            <b>${(p.control_blood || {}).b ? "Control Blood " + p.control_blood.b
              : `opens at ${p.unlocks_b || 11}th`}</b></div>
        </div>
        ${p.paths_offered.map(x => {
          const det = (p.path_detail || {})[x] || {};
          const mine = p.paths_taken.includes(x);
          return `<div class="pathblock ${mine ? "mine" : ""}">
            <h4>${esc(det.name || x)}${det.role ? ` <small>${esc(det.role)}</small>` : ""}
              ${mine ? `<span class="chip">Path ${p.paths_taken.indexOf(x) === 0 ? "A" : "B"}</span>` : ""}</h4>
            ${det.summary ? `<div class="why">${esc(det.summary)}</div>` : ""}
            ${det.global_rule ? `<div class="why"><b>Global rule.</b> ${esc(det.global_rule)}</div>` : ""}
            ${Object.entries(det.tiers || {}).map(([tier, names]) => `
              <div class="tier"><b>Control Blood ${esc(tier)}</b>
                ${names.map(n => {
                  const key = (det.resolves || {})[n];
                  const up = (det.upgrades || {})[n];
                  const core = (det.core || []).includes(n);
                  const text = key ? (det.abilities || {})[key] : "";
                  return `<div class="ab-line"><span>${glossify(n)}</span>
                    <em>${up ? `<b>${esc(up)}</b>, the upgrade of ${esc(key)}: ${esc(text)}`
                      : text ? esc(text)
                      : core ? "a Core Rulebook ability; see the rules reference"
                      : "named on the table; the source does not describe it"}</em>
                  </div>`;
                }).join("")}</div>`).join("")}
          </div>`;
        }).join("")}
        <p class="why">Abilities are tiered by Control Blood level, which is what
          <b>control blood 1a</b> through <b>5b</b> on the table means. The text is the
          class document's own; the rules do not run these yet, so they are yours to
          invoke at the table.</p>` : ""}
      ${p.next ? `
        <h3 class="cardsub">Next level</h3>
        <div class="terms">
          <div class="t"><span>Level</span><b>${p.next.level}</b></div>
          ${p.next.bab ? `<div class="t"><span>Base attack</span><b>+${p.next.bab}</b></div>` : ""}
          ${Object.entries(p.next.saves || {}).map(([k, v]) =>
            `<div class="t"><span>${esc(k)} save</span><b>+${v}</b></div>`).join("")}
          ${(p.next.grants || []).length ? `<div class="t"><span>Gains</span><b>${
            p.next.grants.map(glossify).join(", ")}</b></div>` : ""}
        </div>
        <button type="button" class="v2-btn is-go" id="levelup">Take level ${p.next.level}</button>
        <div id="levelerr" class="why" role="status"></div>`
        : `<p class="why">Twentieth level. There is no more table.</p>`}
    </div>
    <div>
      <h3 class="cardsub">The whole table</h3>
      <div class="gridwrap classtable"><table class="grid">
        <caption class="vh">The class table, levels 1 to 20</caption>
        <thead><tr><th scope="col">Level</th>${cols.map(c => `<th scope="col">${esc(c)}</th>`).join("")}
          <th scope="col">What it grants</th></tr></thead>
        <tbody>${p.rows.map(r => `<tr class="${r.reached ? "" : "dim"}${r.level === p.level ? " inhand" : ""}">
          <td class="lead" data-label="Level"><b>${r.level}</b>${r.level === p.level
            ? `<span class="chip">here</span>` : ""}</td>
          ${cols.map(c => `<td class="n" data-label="${esc(c)}">${esc((r.columns || {})[c] ?? "")}</td>`).join("")}
          <td class="wide" data-label="Grants"><span class="why">${
            (r.grants || []).map(glossify).join(", ") || "nothing new"}</span></td>
        </tr>`).join("")}</tbody>
      </table></div>
    </div>
  </div>`;
}


// Using something you made, from the Equipment tab. Straight to the engine: nothing in
// drinking your own tea for a model to decide. This handler was lost once already: it
// lived in the slice a later rewrite replaced wholesale, and the buttons kept rendering
// over nothing. It lives beside the sheet code it serves now, and
// tests/test_page_wiring.py pins /api/use into the served page so the next
// disappearance fails a test instead of a player. The Equipment page's own buttons go
// through `eqAct` (below), which reads the same doors; these two answer any `[data-use]`
// or `[data-wear]` button drawn anywhere else.
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
      // nothing, and the sheet's tab hides #err completely.
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
    // that says nothing, the exact shape of every silent button this app has had.
    const raw = await r.text();
    let d = {};
    try { d = JSON.parse(raw); } catch { d = { error: `HTTP ${r.status}` }; }
    if (!r.ok) { if (say) say.textContent = d.error || `HTTP ${r.status}`; return; }
    SHEET = d.sheet;
    drawSheet();
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
  $("#sheetbody").innerHTML = `<div class="empty">Reading the sheet.</div>`;
  try {
    const r = await fetch("/api/sheet", { cache: "no-store" });
    SHEET = await readJSON(r);
    if (!r.ok) throw new Error(SHEET.error || "could not read the sheet");
  } catch (e) {
    $("#sheetbody").innerHTML = `<div class="empty">${esc(e.message)}</div>`;
    return;
  }
  // Four characters on the roster predate the field and read they/them, which says
  // nothing about a body. Silence is what produced the wrong one in the first place, so
  // an unstated character says so here rather than quietly taking the model's default.
  askGender(!SHEET.identity.gender);
  // The page the open tab asked for (17-tab-sheet.js sets SHEET_TAB), else the first.
  if (!TABS.some(t => t[0] === SHEET_TAB)) SHEET_TAB = TABS[0][0];
  drawSheet();
}

// The sheet is a tab of the table, not a window over it (the table rebuild), so closing
// it is going back to the Table tab. `sheetAway` is the part that only puts the panel
// away, for the shell to call when another tab is chosen.
function sheetAway() {
  // A spell's details lie over the sheet in the top layer; they go with it.
  if (typeof detailOpen === "function" && detailOpen()) closeDetail(false);
  $("#sheetpanel").classList.remove("on");
  $("#sheetpanel").setAttribute("aria-hidden", "true");
}

function closeSheet() {
  if (typeof Shell === "object" && Shell && Shell.sheetBacked()) { Shell.show("table"); return; }
  sheetAway();
}

// `keep`: a redraw after an act on the page keeps the reader where they were, so the
// slot just edited does not jump away from under the pointer.
function drawSheet(keep = false) {
  const entry = TABS.find(t => t[0] === SHEET_TAB);
  const top = $("#sheetbody").scrollTop;
  $("#sheetbody").innerHTML = entry ? entry[2](SHEET) : "";
  $("#sheetbody").scrollTop = keep ? top : 0;
  if (SHEET_TAB === "equipment") drawEqNums();
  if (SHEET_TAB === "journal") journalRead();
}


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
// The Equipment page wears the trade window's item pictures (06's `paintTradeIcons`),
// painted the same way.
new MutationObserver(() => {
  paintSpellIcons($("#sheetbody"));
  if (typeof paintTradeIcons === "function") paintTradeIcons($("#sheetbody"));
  countGrimoire();
})
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
  return `<section class="v2-framed v2-card-leather sx-card sx-stats" aria-labelledby="sx-stats-h">
    <i class="v2-rim" aria-hidden="true"></i>
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
    ${sp.kind === "prepared" ? `<p class="sx-note sx-house">Prepare whenever you like. A slot
      spent today stays spent, and cannot be filled again until a long rest.</p>` : ""}
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
  return `<section class="v2-framed v2-card-leather sx-card sx-today" id="sx-today"
      data-drop="${prepared ? "prepare" : "learn"}"
      aria-labelledby="sx-today-h" aria-describedby="sx-today-hint">
    <i class="v2-rim" aria-hidden="true"></i>
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
  return `<section class="v2-framed v2-card-leather sx-card sx-index" aria-labelledby="sx-index-h">
    <i class="v2-rim" aria-hidden="true"></i>
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
// The approved design's Equipment page (the mock README, "What changed in the second
// pass", points 1 and 2): the shelves down the side in the trade window's own scheme and
// order (06's TRADE_SHELVES), each with its count and only where something is on it;
// everything carried, A to Z, each name always written beside its icon with its
// quantity; and Worn and wielded, In hand and then every body slot the rules have, in
// their own order and labels (rules/tables.py SLOTS, SLOT_ORDER_LEFT and _RIGHT, read
// through `body_slots`). A slot pressed shows only what fits it.
//
// Every row and every act is the server's (play/views.py `_carried`): Wield, Put away and
// Wear run the engine's `wear` op, Take off its `take_off` op (2026-09-30), a bought
// wondrous item goes into its slot through the sheet's own `/api/slots`, a jar is drunk,
// thrown or coated through `/api/use`. The page offers what those doors would take and
// nothing else, and a row with no act carries the server's reason in words (`note`).
// There is no Drop: the rules do not have one yet.
let EQ_SHELF = "all";
let EQ_FIT = null;          // a slot key ("hand", "ring", ...) while a slot is pressed
let EQ_SAY = "";            // the last answer, written in the line kept for it
let EQ_SAY_BAD = false;
let EQ_BEFORE = null;       // the numbers before the last act, to mark what moved

const eqRows = s => ((s.equipment || {}).carried || []);
const eqShelf = r => (TRADE_SHELVES[r.shelf] ? r.shelf : "gear");
const eqIcon = r => tradeIcon({ shelf: eqShelf(r), name: r.name });
const eqQty = r => (r.unit ? `${r.count} ${r.unit}` : r.count > 1 ? `x${r.count}` : "");
const EQ_INERT = "for show, no effect in play";
// What goes in an empty slot, faded, so a blank says what it is waiting for (the mock's).
const EQ_SLOT_ICON = { shoulders: "lucasms-cloak", ring: "delapouite-ring", belt: "lucasms-belt",
                       wrists: "skoll-bracers", feet: "lorc-boots", neck: "lorc-gem-necklace",
                       armor: "delapouite-leather-armor", shield: "willdabeast-round-shield",
                       body: "delapouite-clothes" };
const eqSlots = s => { const sl = (s.equipment || {}).slots || {}; return [...(sl.left || []), ...(sl.right || [])]; };
const eqSlotLabel = (s, key) => (key === "hand" ? "hand"
  : ((eqSlots(s).find(x => x.key === key) || {}).label || key).toLowerCase());

// What the engine says about a thing, in the row's second line. A weapon's numbers are
// its Combat row's; armour's are the armour table's; anything else is the engine's own
// sentence (`goods.describe`, a jar's effects), or the owner's words for "no rules".
function eqFacts(s, r) {
  if (r.kind === "weapon") {
    const a = (s.offense.attacks || []).find(x => x.key === r.key);
    if (!a) return esc(EQ_INERT);
    const bits = [`${a.damage_dice}${a.damage.total ? sign(a.damage.total) : ""} ${a.type_text || a.type}`,
                  a.crit, `${(a.swings && a.swings.length ? a.swings : [a.attack.total]).map(sign).join("/")} to hit`];
    if (a.range_ft) bits.push(`range ${a.range_ft} ft`);
    // "Range not known" only where it is a gap: a launcher whose range the table lacks.
    else if (a.launcher) bits.push("range not known");
    // A launcher names its supply: "58 arrows", or that there is none to shoot.
    if (a.ammo) {
      const left = (a.ammo.carried || []).reduce((n, x) => n + x.count, 0);
      bits.push(left ? `${left} ${a.ammo.families[0]} carried` : `no ${a.ammo.families[0]} carried`);
    }
    if (a.weight_lb != null) bits.push(`${a.weight_lb} lb`);
    if (!a.proficient) bits.push("not proficient");
    return esc(bits.join(", "));
  }
  if (r.armour) {
    const a = r.armour, bits = [`${sign(a.ac)} AC`];
    if (a.max_dex != null && a.max_dex < 90) bits.push(`max Dex ${sign(a.max_dex)}`);
    bits.push(a.acp ? `check penalty ${a.acp}` : "no check penalty");
    if (a.asf) bits.push(`spell failure ${a.asf}%`);
    if (a.weight) bits.push(`${a.weight} armour`);
    if (a.lb) bits.push(`${a.lb} lb`);
    if (a.takes) bits.push(`${r.state === "worn" ? "off" : "on"} in ${a.takes}`);
    return esc(bits.join(", ")) + (a.proficient === false
      ? ` <span class="chip warn">not proficient</span>` : "");
  }
  const tail = String(r.line || "").split(" — ").slice(1).join(" — ");
  const said = r.line && !/no rules for it/.test(r.line) ? (tail || r.line) : "";
  const where = r.fits && r.state === "worn" ? `worn at the ${eqSlotLabel(s, r.fits)}` : "";
  const fits = r.fits && r.state !== "worn" ? `goes at the ${eqSlotLabel(s, r.fits)}` : "";
  const bits = [said || (r.known ? "" : EQ_INERT), where || fits].filter(Boolean);
  return esc(bits.join(", ")) + (r.poisons ? ` <span class="chip warn">poisons whoever drinks it</span>` : "");
}

function eqFitsSlot(r, slot) {
  if (slot === "hand") return r.kind === "weapon";
  return r.fits === slot;
}

function pageEquipment(s) {
  const rows = eqRows(s);
  const counts = {};
  for (const r of rows) counts[eqShelf(r)] = (counts[eqShelf(r)] || 0) + 1;
  if (EQ_SHELF !== "all" && !counts[EQ_SHELF]) EQ_SHELF = "all";
  const railBtn = (id, label, icon, n) => {
    const on = !EQ_FIT && EQ_SHELF === id;
    return `<button type="button" role="tab" class="v2-btn" data-eqshelf="${id}"
      aria-selected="${on}" tabindex="${on || (EQ_FIT && id === "all") ? 0 : -1}"
      aria-controls="eq-list" aria-label="${esc(label)}, ${n}">${tradeGlyph(icon)}<span>${
      esc(label)}</span><small>${n}</small></button>`;
  };
  const fitWord = EQ_FIT ? eqSlotLabel(s, EQ_FIT) : "";
  const rail = railBtn("all", "Everything", "lorc-knapsack", rows.length)
    + Object.keys(TRADE_SHELVES).filter(k => counts[k])
      .map(k => railBtn(k, TRADE_SHELVES[k].label, TRADE_SHELVES[k].icon, counts[k])).join("")
    + (EQ_FIT ? `<div class="fitting">Showing what fits the ${esc(fitWord)}.
        <button type="button" class="v2-btn is-quiet is-small" data-equnfit>Show everything</button></div>` : "");

  // A to Z and nothing else. "In use first" was tried in the mock and moved the row just
  // pressed to the top of the list, out from under the pointer, the one kind of motion
  // the owner has ruled out; what is in use is marked where it stands instead.
  const list = rows.filter(r => (EQ_FIT ? eqFitsSlot(r, EQ_FIT)
    : EQ_SHELF === "all" || eqShelf(r) === EQ_SHELF))
    .sort((a, b) => String(a.name).localeCompare(String(b.name)));
  const head = EQ_FIT ? `Fits the ${fitWord}`
    : EQ_SHELF === "all" ? "Everything you carry" : TRADE_SHELVES[EQ_SHELF].label;
  const items = list.map(r => {
    const on = !!r.state;
    return `<li class="eqrow${on ? " inuse" : ""}" data-eqid="${esc(r.id)}">
      <span class="tile${on ? " inuse" : ""}">${tradeGlyph(eqIcon(r))}</span>
      <span class="eqname"><b>${esc(r.name)}</b>${eqQty(r) ? `<span class="qty">${esc(eqQty(r))}</span>` : ""}${
        on ? `<span class="chip">${esc(r.state)}</span>` : ""}
        <span class="facts">${eqFacts(s, r)}</span>${
        r.note ? `<span class="facts eqnote">${esc(r.note)}</span>` : ""}</span>
      <span class="eqacts">${(r.acts || []).map((a, i) => `<button type="button"
        class="v2-btn is-small${i === 0 ? " is-go" : ""}" data-eqact="${i}" data-eqid="${esc(r.id)}"
        aria-label="${esc(a.label)} ${esc(r.name)}">${esc(a.label)}</button>`).join("")}</span>
    </li>`;
  }).join("");
  const empty = EQ_FIT
    ? `<li class="eqempty">Nothing you carry goes there. A counter may sell one:
        <button type="button" class="v2-btn is-quiet is-small" data-eqtrade>Go to Trade</button></li>`
    : `<li class="eqempty">Nothing of that kind in your pack.</li>`;

  // Worn and wielded. The engine holds one weapon in hand (`Actor.equipped`) and the
  // shield has a body slot of its own, so there is no off-hand weapon to show; the box
  // says so rather than being an empty place to click.
  const held = rows.find(r => r.kind === "weapon" && r.state === "in hand");
  const slotBtn = (key, label, item, icon) => `<button type="button" class="v2-btn slotbtn${
      item ? "" : " empty"}" data-eqslot="${key}" aria-pressed="${EQ_FIT === key}">
      <span class="tile${item ? " inuse" : ""}">${icon ? tradeGlyph(icon) : ""}</span>
      <span><span class="sl">${esc(label)}</span><span class="it">${esc(item || "empty")}</span></span></button>`;
  const col = side => `<div class="slotcol">${(((s.equipment || {}).slots || {})[side] || []).map(sl => {
    const names = sl.items.filter(it => !it.empty).map(it => it.item);
    const worn = names.length && rows.find(r => r.state === "worn" && r.fits === sl.key);
    return slotBtn(sl.key, sl.label, names.join(", "), worn ? eqIcon(worn) : EQ_SLOT_ICON[sl.key] || "");
  }).join("")}</div>`;
  const chosen = EQ_FIT && EQ_FIT !== "hand" ? eqSlots(s).find(x => x.key === EQ_FIT) : null;

  return `<div class="eq">
    <nav class="eqrail" id="eq-rail" role="tablist" aria-orientation="vertical"
         aria-label="What you carry, by kind">${rail}</nav>
    <section class="eqlist" id="eq-list" role="tabpanel" aria-labelledby="eq-listhead">
      <div class="eqlisthead"><h2 id="eq-listhead">${esc(head)}</h2>
        <p class="eqsort">${list.length} ${list.length === 1 ? "thing" : "things"}, A to Z</p></div>
      <p class="eqsay${EQ_SAY_BAD ? " bad" : ""}" id="eq-say" role="status" tabindex="-1">${EQ_SAY ? esc(EQ_SAY)
        : `<span class="why">Wield or wear something, and what the rules say back is written here.</span>`}</p>
      <ul class="eqrows">${items || empty}</ul>
      <p class="eqload"><b>Weight.</b> Weapons, armour and shields carry their weight in the
        rules, written on their rows. Load is <span class="unknown">not tracked</span>, so nothing here slows
        ${esc(String(s.identity.name || "").split(" ")[0])} down.</p>
      <p class="credit">Item icons by Lorc, Delapouite, Skoll, Sbed, Willdabeast, Carl Olsen,
        Caro Asercion and Lucas from <a href="https://game-icons.net" target="_blank"
        rel="noopener">game-icons.net</a>, <a href="https://creativecommons.org/licenses/by/3.0/"
        target="_blank" rel="noopener">CC BY 3.0</a>, recoloured.</p>
    </section>
    <aside class="doll v2-tooled-leather v2-gilt-edge" aria-labelledby="doll-head">
      <h2 id="doll-head">Worn and wielded</h2>
      <div class="hands">${slotBtn("hand", "In hand", held ? held.name : "", held ? eqIcon(held) : "")}
        <div class="slotbtn v2-btn empty offhand" role="note"
             aria-label="Off hand: the rules hold one weapon at a time">
          <span class="tile"></span><span><span class="sl">Off hand</span>
          <span class="it">one weapon at a time</span></span></div></div>
      <div class="slots">${col("left")}${col("right")}</div>
      ${chosen ? slotEditor(chosen) : ""}
      <p class="dollnote">Choose a slot to see what you carry that goes there.</p>
    </aside>
  </div>`;
}

// The chosen slot's own lines, as the old Equipment page had them: a name written in a
// line is worn there (the catalogue joins a known magic item's effects to it), emptying
// the line takes it off, and a slot the rules allow more of can take another line. The
// armour and shield lines are the armour worn, and say so rather than being typed in.
function slotEditor(sl) {
  const canAdd = sl.items.length < sl.max;
  return `<div class="slotedit" data-slot="${sl.key}">
    <h3>${esc(sl.label)} <small>${esc(sl.holds)}${
      sl.max > sl.rules_limit ? `; ${sl.rules_limit} work${sl.rules_limit === 1 ? "s" : ""} at once` : ""}</small></h3>
    ${sl.items.map(it => `<div class="slotrow${it.empty ? " isempty" : ""}${it.beyond_rules ? " beyond" : ""}">
      <label class="vh" for="slotin-${sl.key}-${it.index}">${esc(sl.label)}, line ${it.index + 1}</label>
      <input class="slotinput v2-well" id="slotin-${sl.key}-${it.index}" data-slot="${sl.key}"
             data-index="${it.index}" value="${esc(it.item || "")}" placeholder="empty"
             ${sl.derived ? "disabled" : ""}>
      ${!sl.derived && !it.empty ? `<button type="button" class="v2-btn is-quiet is-small emptyslot"
        data-slot="${sl.key}" data-index="${it.index}"
        aria-label="Empty ${esc(sl.label)} line ${it.index + 1}">Empty</button>` : ""}
      ${sl.items.length > 1 && !sl.derived ? `<button type="button" class="v2-btn is-quiet is-small delslot"
        data-slot="${sl.key}" data-index="${it.index}"
        aria-label="Remove ${esc(sl.label)} line ${it.index + 1}">Remove line</button>` : ""}
    </div>`).join("")}
    ${canAdd && !sl.derived ? `<button type="button" class="v2-btn is-quiet is-small addslot"
      data-slot="${sl.key}">Another ${esc(sl.label.toLowerCase())} line</button>` : ""}
    ${sl.derived ? `<p class="why">What is worn here is the ${sl.key === "armor" ? "armour" : "shield"}
      put on from the list.</p>` : ""}
  </div>`;
}

// The numbers across the Equipment head: the engine's AC, touch, flat-footed and saves
// from the sheet, marked where the last act moved them.
function drawEqNums() {
  const box = document.getElementById("eq-nums");
  if (!box || !SHEET || !SHEET.defense) return;
  const d = SHEET.defense;
  const now = { AC: d.ac.total, Touch: d.ac_touch.total, Flat: d.ac_flat_footed.total };
  for (const sv of d.saves || []) now[sv.name] = sv.total;
  const signed = new Set((d.saves || []).map(sv => sv.name));
  box.innerHTML = Object.entries(now).map(([k, v]) => `<div class="v2-plaque"><dt>${esc(
    k === "Fortitude" ? "Fort" : k === "Reflex" ? "Ref" : k)}</dt><dd class="${
    EQ_BEFORE && EQ_BEFORE[k] !== undefined && EQ_BEFORE[k] !== v ? "moved" : ""}">${
    signed.has(k) ? sign(v) : v}</dd></div>`).join("");
}
const eqNumbers = () => {
  if (!SHEET || !SHEET.defense) return null;
  const d = SHEET.defense, out = { AC: d.ac.total, Touch: d.ac_touch.total, Flat: d.ac_flat_footed.total };
  for (const sv of d.saves || []) out[sv.name] = sv.total;
  return out;
};

function eqRedraw(focus) {
  if (!SHEET || SHEET_TAB !== "equipment") return;
  $("#sheetbody").innerHTML = pageEquipment(SHEET);
  drawEqNums();
  if (!focus) return;
  const again = focus.id && (document.querySelector(`#sheetbody [data-eqid="${CSS.escape(focus.id)}"] button`)
    || document.querySelector(`#sheetbody .eqrow[data-eqid="${CSS.escape(focus.id)}"]`));
  // A button that went with the act (Wield, once the thing is in hand) hands the focus to
  // the answer, so the keyboard is not dropped at the top of the page.
  const to = focus.sel ? document.querySelector(focus.sel)
    : (again && again.tagName === "BUTTON" ? again : document.getElementById("eq-say"));
  if (to) to.focus({ preventScroll: true });
}

// An act on a row: the door the server named, the answer written where the page keeps a
// line for it, the sheet read again, the sides and the story told (a state is drawn).
async function eqAct(btn) {
  const row = eqRows(SHEET).find(r => r.id === btn.dataset.eqid);
  const act = row && (row.acts || [])[Number(btn.dataset.eqact)];
  if (!act) return;
  EQ_BEFORE = eqNumbers();
  btn.disabled = true;
  busy(true);
  let said = "", bad = false;
  try {
    const d = await post(act.api, act.body);
    if (act.api === "/api/use") {
      said = d.tell || "";
      if (d.sheet) SHEET = d.sheet;
      render(await getState());
    } else if (act.api === "/api/slots") {
      if (d && d.equipment) SHEET = d;
      said = `${row.name} is worn at the ${eqSlotLabel(SHEET, act.body.slot)} now.`;
      render(await getState());
    } else {
      said = d.wear_tell || "";
      render(d);
    }
    if (act.api !== "/api/use" && act.api !== "/api/slots") SHEET = await readJSON(await fetch("/api/sheet"));
  } catch (err) {
    said = err.message || String(err);
    bad = true;
  } finally { busy(false); }
  EQ_SAY = said;
  EQ_SAY_BAD = bad;
  eqRedraw({ id: row.id });
}

async function slotAction(payload) {
  EQ_BEFORE = eqNumbers();
  try {
    SHEET = await post("/api/slots", payload);
    EQ_SAY = "";
    EQ_SAY_BAD = false;
    drawSheet(true);
    // The left panel's In hand and worn reads the state, which has moved too.
    render(await getState());
  } catch (e) {
    EQ_SAY = e.message || String(e);
    EQ_SAY_BAD = true;
    drawSheet(true);
  }
}

document.addEventListener("click", e => {
  const act = e.target.closest("#sheetbody [data-eqact]");
  if (act && !act.disabled) { eqAct(act); return; }
  const shelf = e.target.closest("#sheetbody [data-eqshelf]");
  if (shelf) {
    EQ_SHELF = shelf.dataset.eqshelf;
    EQ_FIT = null;
    eqRedraw({ sel: `#sheetbody [data-eqshelf="${CSS.escape(EQ_SHELF)}"]` });
    return;
  }
  const slot = e.target.closest("#sheetbody [data-eqslot]");
  if (slot) {
    EQ_FIT = EQ_FIT === slot.dataset.eqslot ? null : slot.dataset.eqslot;
    eqRedraw({ sel: `#sheetbody [data-eqslot="${CSS.escape(slot.dataset.eqslot)}"]` });
    return;
  }
  if (e.target.closest("#sheetbody [data-equnfit]")) {
    EQ_FIT = null;
    eqRedraw({ sel: `#sheetbody [data-eqshelf="${CSS.escape(EQ_SHELF)}"]` });
    return;
  }
  if (e.target.closest("[data-eqtrade], #eq-trade")) { Shell.show("trade"); return; }
});

// The shelves are one tab stop, walked with the arrows (WAI-ARIA's tabs pattern,
// vertical), as the trade window's are.
document.addEventListener("keydown", e => {
  const here = e.target.closest && e.target.closest("#sheetbody [data-eqshelf]");
  if (!here) return;
  const keys = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 };
  const tabs = [...document.querySelectorAll("#sheetbody [data-eqshelf]")];
  const at = tabs.indexOf(here);
  let to = null;
  if (e.key in keys) to = (at + keys[e.key] + tabs.length) % tabs.length;
  else if (e.key === "Home") to = 0;
  else if (e.key === "End") to = tabs.length - 1;
  if (to === null) return;
  e.preventDefault();
  EQ_SHELF = tabs[to].dataset.eqshelf;
  EQ_FIT = null;
  eqRedraw({ sel: `#sheetbody [data-eqshelf="${CSS.escape(EQ_SHELF)}"]` });
});


// Delegated so the handlers survive every redraw.
document.addEventListener("click", e => {
  const add = e.target.closest(".addslot");
  if (add) return slotAction({action: "add", slot: add.dataset.slot});
  const del = e.target.closest(".delslot");
  if (del) return slotAction({action: "remove", slot: del.dataset.slot,
                              index: Number(del.dataset.index)});
  // Emptying a line is taking off whatever was written in it: the sheet's own `set`
  // with nothing, and the effects stop because `worn_items` asks the slots.
  const clear = e.target.closest(".emptyslot");
  if (clear) return slotAction({action: "set", slot: clear.dataset.slot,
                                index: Number(clear.dataset.index), item: ""});
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

// --- Background, notes, companions ---
function backgroundCard(s) {
  const b = s.background, i = s.identity;
  // The identity line the old sheet's header carried, gender and pronouns included,
  // "because the narrator reads both and a player who is being described wrongly needs
  // somewhere to look and see what it was told".
  const who = [i.heritage, i.race, i.class, i.size, i.gender, i.pronouns].filter(Boolean);
  return sheetCard("sc-background", "Background and notes", `<div class="twocol">
    <div>
      <p class="idline">${esc(who.join(", "))}</p>
      <h3 class="cardsub">In the world</h3>
      <div class="terms">
        <div class="t"><span>People</span><b>${esc(b.heritage || "none named")}</b></div>
        <div class="t"><span>World Bible id</span><b>${esc(i.world_people_id || "none")}</b></div>
      </div>
      <p class="why">The rules race and the world's people are different things, and the
        sheet carries both. ${esc(i.heritage || "This people")} is who ${esc(i.name)} is in
        the world; ${esc(i.race)} is what the rules use.</p>
      ${b.past ? `
      <h3 class="cardsub">Before this</h3>
      <div class="terms"><div class="t"><span>Background</span><b>${esc(b.past.name)}</b></div></div>
      ${b.past.line ? `<p class="why">${esc(b.past.line)}</p>` : ""}
      ${b.past.ties.length ? b.past.ties.map(t => `<p>${esc(t)}</p>`).join("")
        : `<p class="why">Chosen, but this world has not filled it in yet: the names arrive
             when the campaign begins.</p>`}` : ""}
      <h3 class="cardsub">Companions</h3>
      <p class="why" data-page="companions">No animal companion, familiar, cohort or mount.</p>
    </div>
    <div>
      <h3 class="cardsub">Notes</h3>
      ${b.notes ? `<p class="notes">${esc(b.notes)}</p>` : `<p class="why">None.</p>`}
      <h3 class="cardsub">The manual</h3>
      <p class="why">How the app works, what it needs, and what the slash commands do:
        <a href="/manual" target="_blank" rel="noopener">open the manual</a>.</p>
      <h3 class="cardsub">Rules content</h3>
      <p class="why">The Pathfinder rules this app runs on (spells, creatures, feats, weapons
        and the tables behind them) are Open Game Content under the
        <a href="/licence" target="_blank" rel="noopener">Open Game Licence v1.0a</a>,
        which section 10 requires travel with it. This project is not published by,
        endorsed by, or affiliated with Paizo Inc.</p>
      <p class="why">${spellIconCredit()}</p>
    </div>
  </div>`);
}

// --- The Journal tab ---
// The matters in play (the quest cards the engine keeps), what people said (the
// conversation log, read a person at a time from `/api/conversation`, which only reads),
// and the places walked. What is said is answered in Talk; this is the record.
function pageJournal(s) {
  const nodes = ((((STATE || {}).scene || {}).places_found || {}).nodes || []);
  const walked = nodes.filter(n => n.visited);
  return `<div class="journal">
    ${sheetCard("jr-matters", "Matters in play", tabQuests(s), "jr-matters")}
    ${sheetCard("jr-said", "What people said", journalSaid(), "jr-said")}
    ${sheetCard("jr-walked", "Where you have been", walked.length
      ? `<ol class="plain walked">${walked.map(n => `<li>${esc(n.name)}${
          n.current ? ` <span class="chip">here</span>` : ""}</li>`).join("")}</ol>
        <p class="why">The Map tab draws these, and the ways between them.</p>`
      : `<p class="why">Nowhere yet: the places you walk to are kept here.</p>`, "jr-walked")}
    <p class="jr-log why">The adventure log, a record of each session, is not kept yet.</p>
  </div>`;
}

// The quest log: the tasks taken up, read off the situation cards of kind quest the
// engine keeps. Objectives say what to do next; the facts under them say what has
// happened (Baldur's Gate 3's journal keeps the two apart for the same reason).
function tabQuests() {
  const q = (STATE && STATE.quests) || { active: [], finished: [] };
  const one = (k, done) => `<li class="matter${done ? " done" : ""}">
      <h3>${esc(k.title)}${done ? ` <span class="chip">finished</span>` : ""}</h3>
      ${k.giver ? `<p class="why">for ${esc(k.giver)}</p>` : ""}
      ${k.objectives.length ? `<ul class="objectives">${k.objectives.map(o =>
        `<li class="${o.done ? "done" : ""}">${esc(o.text)}${o.done ? `<span class="vh">, done</span>` : ""}</li>`).join("")}</ul>` : ""}
      ${k.reward ? `<p class="why">Promised: ${esc(k.reward)}</p>` : ""}
      ${k.facts.length ? `<p class="why">${k.facts.map(esc).join(" ")}</p>` : ""}
    </li>`;
  return `${q.active.length ? `<ul class="plain matters">${q.active.map(k => one(k, false)).join("")}</ul>`
      : `<p class="why">Nothing taken on yet. When somebody gives you a task and you take it,
          it is kept here.</p>`}
    ${q.finished.length ? `<h3 class="cardsub">Finished</h3>
      <ul class="plain matters">${q.finished.map(k => one(k, true)).join("")}</ul>` : ""}`;
}

let JOURNAL_WITH = "all";
let JOURNAL_LOG = null;         // the entries last read, for the person shown
function journalSaid() {
  const people = ((((STATE || {}).scene || {}).conversation || {}).people || []);
  const pick = people.length ? `<div class="v2-recess jr-people" role="group" aria-label="Whose words">
      <button type="button" class="v2-btn" data-jrwith="all" aria-pressed="${JOURNAL_WITH === "all"}">Everyone</button>
      ${people.map(p => `<button type="button" class="v2-btn" data-jrwith="${esc(p.ref)}"
        aria-pressed="${JOURNAL_WITH === p.ref}">${esc(title(p.name))}</button>`).join("")}
    </div>` : "";
  return `${pick}<div class="jr-log-lines" id="jr-log" tabindex="0" role="log" aria-live="off"
      aria-label="What was said">${journalLines()}</div>
    <p class="why">To answer anybody, open Talk from the Table.</p>`;
}
function journalLines() {
  if (JOURNAL_LOG === null) return `<p class="why">Reading what was said.</p>`;
  if (!JOURNAL_LOG.length) return `<p class="why">Nobody has spoken with you yet. What people
    say to you, and what you say back, is kept here.</p>`;
  let out = "", group = null;
  for (const e of JOURNAL_LOG) {
    const key = `${e.who}|${e.beat}`;
    if (key !== group) {
      if (group !== null) out += `</div>`;
      out += `<div class="jr-turn"><span class="jr-name">${esc(e.who === "you" ? "You" : title(e.name || e.who))}</span>`;
      group = key;
    }
    out += `<p><q>${esc(e.text)}</q></p>`;
  }
  return out + (group !== null ? `</div>` : "");
}
async function journalRead() {
  try {
    const d = await readJSON(await fetch(`/api/conversation?with=${encodeURIComponent(JOURNAL_WITH)}&limit=200`,
                                         { cache: "no-store" }));
    JOURNAL_LOG = d.entries || [];
  } catch (err) {
    JOURNAL_LOG = [];
  }
  const box = document.getElementById("jr-log");
  if (box) { box.innerHTML = journalLines(); box.scrollTop = box.scrollHeight; }
}
document.addEventListener("click", e => {
  const b = e.target.closest("#sheetbody [data-jrwith]");
  if (!b) return;
  JOURNAL_WITH = b.dataset.jrwith;
  document.querySelectorAll("#sheetbody [data-jrwith]").forEach(x =>
    x.setAttribute("aria-pressed", String(x === b)));
  journalRead();
});

/* An existing character with nothing said about what they are.
   The forge asks everyone made since the field existed, but the roster still holds four
   who predate it and read they/them, which says nothing about a body, so nothing can be
   derived from it and guessing from a name is the thing the field exists to stop. */
function askGender(missing) {
  // Into the sheet's own notice line above its page (scoped to the sheet panel: the
  // trade panel once shared a class name and took a prompt meant for the sheet).
  const note = $("#sheetpanel #sheetnote");
  let bar = $("#genderask");
  if (!missing) { if (bar) bar.remove(); return; }
  if (bar || !note) return;
  bar = document.createElement("div");
  bar.id = "genderask";      // styled in table.html, so a phone can give it a line
  bar.innerHTML = `Nothing on this sheet says what they are, so the narration will
    pick for them.
    <button type="button" class="v2-btn is-quiet is-small" data-setgender="woman">woman</button>
    <button type="button" class="v2-btn is-quiet is-small" data-setgender="man">man</button>`;
  note.insertBefore(bar, $("#sheeterr"));
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
  // Drawn again where it is: the sheet is a tab now, and closing it would leave the tab.
  openSheet();
});

document.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  // One Esc, one layer: a spell's details close first and the sheet stays open behind
  // them. Without this the same key shut both, and focus had nowhere to go back to.
  if (typeof detailOpen === "function" && detailOpen()) {
    e.preventDefault();
    closeDetail(true);
    return;
  }
  // Then the page itself goes back to the Table, as Close did before the tabs.
  if ($("#sheetpanel").classList.contains("on")) closeSheet();
});
