// The table layout mock. Static: it reads window.MOCK_DATA (data.js, generated from the
// engine and a recording by build_data.py) and answers clicks with canned lines. Nothing
// here reaches a server or a model, and no number on the page is worked out here: every
// one is looked up in data.js, where the engine put it.
//
// The owner's motion rule holds throughout: nothing moves under the pointer on its own,
// and anything that opens does so without shifting what was under the pointer.
"use strict";

const D = window.MOCK_DATA;
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const signed = n => (n >= 0 ? "+" : "") + n;
const cap = t => { t = String(t || ""); return t ? t[0].toUpperCase() + t.slice(1) : t; };
const words = n => ["no", "one", "two", "three", "four", "five", "six"][n] || String(n);

// --- Icons: the repo's own SVGs, inlined so currentColor tints them ----------------------
// The app inlines by fetch rather than using a CSS mask, because a mask needs the server
// to call the file image/svg+xml and on Windows that answer comes from the registry. The
// mock does the same, for the same reason.
const ICON_BASE = { items: "../../../play/static/icons/items/",
                    spells: "../../../play/static/icons/spells/" };
const SVG = new Map();
const glyph = (name, set = "items", cls = "") =>
  `<i class="gi${cls ? " " + cls : ""}" data-icon="${esc(name)}" data-set="${set}"
      aria-hidden="true"></i>`;
function paintIcons(root = document) {
  root.querySelectorAll("i.gi[data-icon]").forEach(i => {
    if (i.firstChild) return;
    const key = i.dataset.set + "/" + i.dataset.icon;
    const have = SVG.get(key);
    if (typeof have === "string") { i.innerHTML = have; return; }
    if (have === null) return;                    // on its way
    SVG.set(key, null);
    fetch(ICON_BASE[i.dataset.set] + encodeURIComponent(i.dataset.icon) + ".svg")
      .then(r => (r.ok ? r.text() : ""))
      .then(text => {
        const svg = text.includes("<svg") ? text : "";
        SVG.set(key, svg);
        document.querySelectorAll(`i.gi[data-set="${i.dataset.set}"][data-icon="${
          CSS.escape(i.dataset.icon)}"]`).forEach(x => { if (!x.firstChild) x.innerHTML = svg; });
      })
      .catch(() => SVG.set(key, ""));
  });
}

// The trade window's shelves and pictures (06-trade-and-page.js TRADE_SHELVES and
// TRADE_ITEM_ICONS), copied so a thing wears the same picture in the pack as on the
// counter: its own where the match is plain at 20px, else its shelf's.
const SHELVES = {
  weapons:     { label: "Weapons",     icon: "lorc-broadsword" },
  armour:      { label: "Armour",      icon: "lorc-breastplate" },
  consumables: { label: "Consumables", icon: "lorc-bubbling-flask" },
  gear:        { label: "Gear",        icon: "lorc-knapsack" },
  magic:       { label: "Magic items", icon: "lorc-gem-pendant" },
  valuables:   { label: "Valuables",   icon: "lorc-gems" },
};
const ITEM_ICONS = {
  weapons: [
    [/crossbow/, "carl-olsen-crossbow"], [/\b(arrows?|bolts?)\b/, "lorc-arrow-cluster"],
    [/bow\b/, "delapouite-bow-arrow"], [/\bsap\b|club/, "delapouite-wood-club"],
    [/quarterstaff|\bstaff\b/, "delapouite-bo"], [/dagger|knife/, "lorc-plain-dagger"],
    [/sling/, "delapouite-sling"],
  ],
  armour: [
    [/shield|buckler/, "willdabeast-round-shield"], [/chain|mail shirt/, "lorc-mail-shirt"],
    [/scale/, "lorc-scale-mail"], [/leather|padded|\bhide\b|studded/, "delapouite-leather-armor"],
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
    [/\bmeat\b/, "lorc-meat"], [/meal|ration|stew/, "delapouite-hot-meal"],
    [/potion|elixir|tincture|draught|tonic|\btea\b|brew|philt/, "caro-asercion-round-potion"],
    [/antitoxin|antidote|\bvial\b|\boil\b/, "sbed-vial"],
  ],
  magic: [
    [/\bring\b/, "delapouite-ring"], [/cloak|cape|mantle/, "lucasms-cloak"],
    [/belt|girdle/, "lucasms-belt"], [/bracer/, "skoll-bracers"], [/boots/, "lorc-boots"],
    [/amulet|necklace|pendant/, "lorc-gem-necklace"],
  ],
  valuables: [
    [/coins?\b|ingot/, "delapouite-two-coins"], [/\bring\b/, "delapouite-ring"],
    [/necklace|pendant|amulet/, "lorc-gem-necklace"],
  ],
};
const itemIcon = x => {
  const hit = (ITEM_ICONS[x.shelf] || []).find(([re]) => re.test(x.name.toLowerCase()));
  return hit ? hit[1] : SHELVES[x.shelf].icon;
};
// What goes in an empty slot, faded, so a blank says what it is waiting for.
const SLOT_ICON = { shoulders: "lucasms-cloak", ring: "delapouite-ring", belt: "lucasms-belt",
                    wrists: "skoll-bracers", feet: "lorc-boots", neck: "lorc-gem-necklace",
                    armor: "delapouite-leather-armor", shield: "willdabeast-round-shield",
                    body: "delapouite-clothes" };

// The Spells page's own tables (05-sheet.js SPELL_SCHOOLS, SPELL_ICONS).
const SCHOOL_ICON = {
  abjuration: "lorc-magic-shield", conjuration: "lorc-magic-portal",
  divination: "lorc-crystal-ball", enchantment: "lorc-psychic-waves",
  evocation: "delapouite-bolt-spell-cast", illusion: "lorc-duality-mask",
  necromancy: "lorc-dread-skull", transmutation: "lorc-potion-ball", universal: "lorc-star-swirl",
};
const SPELL_ICONS = {
  "acid-splash": "lorc-acid-blob", "bleed": "lorc-bleeding-wound",
  "burning-hands": "lorc-glowing-hands", "color-spray": "lorc-rainbow-star",
  "daze": "delapouite-knocked-out-stars", "detect-magic": "lorc-third-eye",
  "disrupt-undead": "lorc-broken-skull", "light": "lorc-candle-light",
  "mage-armor": "lorc-energy-shield", "mage-hand": "lorc-magic-palm",
  "magic-missile": "lorc-missile-swarm", "prestidigitation": "delapouite-magick-trick",
  "ray-of-frost": "lorc-ice-bolt", "shield": "lorc-shield-reflect", "sleep": "lorc-sleepy",
};
const school = sp => (SCHOOL_ICON[sp.school] ? sp.school : "universal");
const spellIcon = sp => SPELL_ICONS[sp.id] || SCHOOL_ICON[school(sp)];

// A framed card's bevel is an element of its own (the ring and the clasps already use
// both pseudo-elements), added wherever a card is drawn.
function rims(root = document) {
  root.querySelectorAll(".framedcard").forEach(el => {
    if (!el.querySelector(":scope > .rim"))
      el.insertAdjacentHTML("afterbegin", `<i class="rim" aria-hidden="true"></i>`);
  });
}

// --- State ----------------------------------------------------------------------------------
const freshEq = c => ({
  hand: c.equipped,
  armour: (c.basket.find(b => b.kind === "armour" && b.state === "worn") || {}).key || "none",
  shield: (c.basket.find(b => b.kind === "shield" && b.state === "worn") || {}).key || "none",
  // Worn slot items by slot: the free outfit starts on the body (rules/creation.py OUTFITS).
  slots: Object.fromEntries(c.basket.filter(b => b.kind === "slot" && b.state === "worn")
    .map(b => [b.slot, b.name])),
});
const S = {
  char: "kesst", place: D.start, wanted: false, mode: "table", sheetHidden: false,
  transcript: D.transcript.map(b => ({ ...b })), confirm: null, why: "",
  spell: null, spellFilter: "all", person: null, attach: null, portraits: {},
  walked: [D.places[D.start].name],
  eq: Object.fromEntries(Object.entries(D.chars).map(([k, c]) => [k, freshEq(c)])),
  shelf: "all", fit: null, eqSay: "",
  talkOpen: false, convoPick: null,
  // The guard's two lines arrived on the last beat and have not been read yet.
  convoSeen: D.conversation.recent.filter(e => e.who !== "c9").slice(-1)[0]?.n ?? 0,
  talkSay: "",
  board: { view: "flat", last: "flat", turn: 0, level: 0, picked: null },
};
const pc = () => D.chars[S.char];
const eq = () => S.eq[S.char];
const place = id => D.places[id || S.place];
const she = () => (pc().pronouns.startsWith("she") ? "she" : pc().pronouns.startsWith("he")
  ? "he" : "they");

// The numbers for what is being worn right now: one of the combinations build_data.py
// asked the engine about, never a sum made here.
function loadoutKey() {
  const e = eq(), c = pc();
  const magic = c.basket.filter(b => b.kind === "slot" && b.slot !== "body"
    && e.slots[b.slot] === b.name).map(b => b.name).sort();
  return `${e.armour}|${e.shield}|${magic.join(",")}`;
}
const nums = (key = loadoutKey()) => pc().loadouts[key] || pc().numbers;
const inHand = () => pc().basket.find(b => b.kind === "weapon" && b.attack.key === eq().hand);
const inUse = b => {
  const e = eq();
  if (b.kind === "weapon") return b.attack.key === e.hand;
  if (b.kind === "armour") return b.key === e.armour;
  if (b.kind === "shield") return b.key === e.shield;
  if (b.kind === "slot") return e.slots[b.slot] === b.name;
  return false;
};
const slotLabel = key => {
  const all = [...pc().slots.left, ...pc().slots.right];
  return (all.find(s => s.key === key) || { label: cap(key) }).label;
};

// --- The mock strip ---------------------------------------------------------------------
function renderStrip() {
  $$(".viewing [role=radio]").forEach(b => {
    const on = b.dataset.char === S.char;
    b.setAttribute("aria-checked", String(on));
    b.tabIndex = on ? 0 : -1;
  });
  const c = pc();
  const first = c.name.split(" ")[0];
  $("#mock-say").textContent = c.spells
    ? `${first} is a wizard: the Spells tab and the Spells button by Say are ${
      she() === "she" ? "hers" : "theirs"}.`
    : `${first} casts no spells, so there is no Spells tab and no Spells button.`;
}

// --- The sheet ------------------------------------------------------------------------------
function renderSheet() {
  const c = pc(), n = nums();
  $("#pc-name").textContent = c.name;
  $("#pc-line").textContent = `${c.class}, ${c.race}${c.heritage ? ` of the ${c.heritage}` : ""}, ${
    c.pronouns}`;
  const state = $("#pc-state");
  state.hidden = !S.wanted;
  state.textContent = "Wanted in Zhilvarnia";

  const img = $("#portrait-img"), url = S.portraits[S.char];
  img.hidden = !url; if (url) { img.src = url; img.alt = `Portrait of ${c.name}`; }
  $("#portrait-empty").hidden = !!url;
  $("#portrait-add").textContent = url ? "Change" : "Add a portrait";
  $("#portrait-remove").hidden = !url;

  // In hand and worn: the icons, each with its name beside it, always written out.
  const e = eq(), rows = [];
  const hand = inHand();
  rows.push(["In hand", hand ? hand.name : "nothing, fists", hand ? itemIcon(hand) : ""]);
  const worn = c.basket.filter(b => b.kind !== "weapon" && inUse(b));
  const order = ["armour", "shield", "slot"];
  worn.sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind));
  worn.forEach(b => rows.push([b.kind === "armour" ? "Armour" : b.kind === "shield" ? "Shield"
    : slotLabel(b.slot), b.name, itemIcon(b)]));
  $("#loadout").innerHTML = rows.map(([where, what, icon]) => `<li>
      <span class="tile inuse">${icon ? glyph(icon) : ""}</span>
      <span><span class="where">${esc(where)}</span><span class="what">${esc(what)}</span></span>
    </li>`).join("");
  const count = c.basket.length;
  $("#open-equipment").innerHTML = `Equipment <small>${count} things carried</small>`;
  $("#open-equipment").setAttribute("aria-label", `Open equipment, ${count} things carried`);

  $("#life-bar").style.width = Math.round(100 * c.hp / c.hp_max) + "%";
  $("#life-say").innerHTML = `<b>${c.hp}</b> of ${c.hp_max}`;
  $("#medals").innerHTML = c.abilities.map(a =>
    `<li class="medal"><span class="vh">${a.name} ${a.score}, modifier ${signed(a.modifier)}</span>
      <div aria-hidden="true"><span class="ab">${cap(a.key)}</span><span class="sc">${a.score}</span></div>
      <span class="md" aria-hidden="true">${signed(a.modifier)}</span></li>`).join("");
  const plaque = (dt, dd, small = "") =>
    `<div><dt>${dt}</dt><dd>${dd}${small ? `<small>${small}</small>` : ""}</dd></div>`;
  $("#defence").innerHTML = plaque("AC", n.ac, `touch ${n.touch}, flat ${n.ff}`)
    + plaque("Speed", c.speed + " ft");
  $("#saves").innerHTML = plaque("Fort", signed(n.saves.fort))
    + plaque("Ref", signed(n.saves.ref)) + plaque("Will", signed(n.saves.will));
  $("#xp").textContent = `${c.xp.have.toLocaleString("en")} of ${
    c.xp.next.toLocaleString("en")} for level 2`;

  $("#glance").textContent = `Life ${c.hp} of ${c.hp_max}, AC ${n.ac}`;
  $("#glance").setAttribute("aria-label", `Life ${c.hp} of ${c.hp_max}, armour class ${
    n.ac}. Open the sheet`);
  $("#spells").hidden = !c.spells;
  $("#tab-spells").hidden = !c.spells;
  renderSheetMore();
  paintIcons($("#sheet"));
}

// "base 10, Dex +3": the 10 every AC and CMD starts from is a number, not a bonus.
const termLine = t => (t || []).map(([s, v]) => `${s} ${s === "base" ? v : signed(v)}`).join(", ");
// The engine names people by what they are ("guard"), and a sentence wants "the guard".
const theName = n => (/^(the|a|an) /i.test(n) || /^[A-Z]/.test(n) ? n : `the ${n}`);

// The sheet's middle in Sheet mode: the combat block first, then defence, skills, feats.
function renderSheetMore() {
  const c = pc(), n = nums();
  const stat = (dt, dd, why = "", small = "") => `<div class="stat"><dt>${dt}</dt><dd>${dd}${
    small ? ` <small>${small}</small>` : ""}</dd>${why ? `<span class="why">${esc(why)}</span>` : ""}</div>`;

  const hand = eq().hand;
  // Every carried weapon, the one in hand first: the fixture's own and any in the basket,
  // each computed by the engine's attack_modifiers.
  const weapons = c.basket.filter(b => b.kind === "weapon").map(b => b.attack)
    .sort((a, b) => (b.key === hand) - (a.key === hand));
  const hands = a => a.hands === 2 ? "two-handed" : a.light ? "light" : "one-handed";
  const rows = weapons.map(a => {
    const notes = [hands(a), a.finessable ? "finesse" : "", ...a.traits,
                   a.weight_lb != null ? `${a.weight_lb} lb` : ""].filter(Boolean);
    const thrown = a.category === "melee" && a.range_ft;
    // data-label: on a phone each row folds into a small card and says what each number is.
    return `<tr class="${a.key === hand ? "inhand" : ""}">
      <td class="lead"><b>${esc(a.name)}</b>${a.key === hand ? `<span class="chip">in hand</span>` : ""}${
        a.proficient ? "" : `<span class="chip warn">not proficient</span>`}</td>
      <td class="n" data-label="To hit">${a.swings.map(signed).join(" / ")}<span class="why">${
        esc(termLine(a.attack_terms)) || "base attack +0"}</span></td>
      <td class="n" data-label="Damage">${esc(a.damage)}<span class="why">${esc(a.type)}</span></td>
      <td class="n" data-label="Critical">${esc(a.crit)}</td>
      <td data-label="Range">${a.range_ft ? `${a.range_ft} ft${thrown ? ", thrown" : ""}` : a.category === "melee"
        ? `<span class="why">melee</span>` : `<span class="unknown">not known</span>`}${
        thrown ? `<span class="why unknown">thrown to-hit not known</span>` : ""}</td>
      <td class="wide" data-label="Notes"><span class="why">${esc(notes.join(", "))}</span></td></tr>`;
  }).join("");
  const held = weapons.find(a => a.key === hand);
  const full = held
    ? `Full attack with the ${esc(held.name)}: ${words(held.swings.length)} swing${
      held.swings.length === 1 ? "" : "s"}, at ${held.swings.map(signed).join(" then ")}.`
    : "Full attack: nothing in hand.";
  const man = c.maneuvers.map(m => {
    const limits = [m.size_limit != null ? "no more than one size larger" : "",
                    m.two_hands ? "needs both hands free" : ""].filter(Boolean).join("; ");
    return `<tr><td class="lead"><b>${esc(m.name)}</b></td>
      <td class="n" data-label="Bonus">${signed(m.cmb)}</td>
      <td data-label="Provokes">${m.provokes ? "Yes" : "No"}</td>
      <td class="wide" data-label="On success">${esc(m.effect)}</td>
      <td class="wide${limits ? "" : " none"}" data-label="Limits"><span class="why">${
        esc(limits)}</span></td></tr>`;
  }).join("");
  const feint = `<tr><td class="lead"><b>feint</b></td><td class="n" data-label="Bonus">${
      c.feint_bluff == null ? `<span class="unknown">not known</span>` : signed(c.feint_bluff)}
      <span class="why">Bluff</span></td>
    <td data-label="Provokes"><span class="unknown">not known</span></td>
    <td class="wide" data-label="On success">Rolled as a Bluff check. The target losing its
      Dexterity to AC is <span class="unknown">not in the engine</span>.</td>
    <td class="wide none"></td></tr>`;

  $("#combat").innerHTML = `<h2>Combat</h2>
    <dl class="statrow">
      ${stat("Initiative", signed(c.init.total), termLine(c.init.terms))}
      ${stat("Base attack", signed(c.bab))}
      ${stat("CMB", signed(c.cmb.total), termLine(c.cmb.terms))}
      ${stat("CMD", c.cmd.total, termLine(c.cmd.terms), `flat-footed ${c.cmd_ff}`)}
      ${stat("Speed", c.speed + " ft")}
    </dl>
    <div class="gridwrap"><table class="grid">
      <caption class="vh">Attacks</caption>
      <thead><tr><th scope="col">Weapon</th><th scope="col">To hit</th><th scope="col">Damage</th>
        <th scope="col">Critical</th><th scope="col">Range</th><th scope="col">Notes</th></tr></thead>
      <tbody>${rows}</tbody></table></div>
    <p class="fullattack">${full}</p>
    <h2>Combat manoeuvres</h2>
    <p class="why">Each is your bonus rolled against the target's CMD.</p>
    <div class="gridwrap"><table class="grid">
      <caption class="vh">Combat manoeuvres</caption>
      <thead><tr><th scope="col">Manoeuvre</th><th scope="col">Bonus</th>
        <th scope="col">Provokes</th><th scope="col">On success</th><th scope="col">Limits</th></tr></thead>
      <tbody>${man}${feint}</tbody></table></div>
    <p class="why">Provokes is read from the engine's manoeuvre table. No attack of opportunity
      is rolled for a manoeuvre yet.</p>`;

  const sv = c.saves.map(s => stat(s.name, signed(n.saves[s.key]),
    termLine(n.save_terms[s.key]) || "no bonus")).join("");
  $("#defencecard").innerHTML = `<h2>Defence</h2>
    <dl class="statrow">
      ${stat("AC", n.ac, termLine(n.ac_terms))}
      ${stat("Touch", n.touch)}
      ${stat("Flat-footed", n.ff)}
      ${sv}
    </dl>
    <h2>Conditions</h2>
    <p>${c.conditions.length ? esc(c.conditions.join(", ")) : "None."}</p>`;

  $("#skills").innerHTML = c.skills.map(k =>
    `<div class="${k.usable ? "" : "dim"}"><dt>${esc(k.name)}${k.class_skill
      ? ` <span class="vh">(class skill)</span>` : ""}</dt><dd>${
      k.usable ? signed(k.total) : `<span title="Cannot be attempted untrained">untrained</span>`
    }</dd></div>`).join("");
  $("#feats").innerHTML = c.feats.map(f =>
    `<dt>${esc(f.name)}</dt><dd>${esc(f.effect)}</dd>`).join("");
  $("#background").textContent = c.background
    ? `${c.background.name}. ${c.background.line}` : "None chosen.";
  $("#notes").textContent = c.notes;
  rims($("#sheetmore"));
}

// --- The scene --------------------------------------------------------------------------------
const GROUPS = [["n", "Next door"], ["o", "Outside"], ["r", "Roads"]];
// "a few minutes' walk" reads as "a few minutes" in a row that is all walking (the app's).
const exitTime = w => String(w || "").replace(/(?:'s|') walk$/, "");
const reason = i => (i >= 0 ? D.reasons[i].replace("{pc}", pc().name) : "");
const exitsHere = () => (S.wanted ? place().wanted : place().exits);

function renderScene() {
  const p = place();
  $("#place-name").textContent = p.name;
  const where = p.setting === "outside"
    ? `Near Zhilvarnia, ${p.ground}.` : "Zhilvarnia, a city.";
  $("#where-line").textContent = `${where} ${cap(D.day_part)}.`;
  $("#craft-ground").textContent = p.ground === "urban" ? "a city street" : p.ground;

  const people = D.people[S.place] || [];
  $("#here").hidden = !people.length;
  $("#here-list").innerHTML = people.map(x =>
    `<button type="button" data-person="${esc(x.ref)}" aria-expanded="${S.person === x.ref}"
      aria-controls="face">the ${esc(x.name)}</button>`).join("");
  const who = people.find(x => x.ref === S.person);
  $("#face").hidden = !who;
  $("#face").textContent = who ? who.face : "";

  renderExits();
  renderSuggestions();
  renderTrade();
}

function renderExits() {
  const rows = exitsHere();
  const groups = GROUPS.map(([g, label]) => {
    const mine = rows.filter(r => r[2] === g);
    if (!mine.length) return "";
    // Five doors that are all "a few minutes" away said it five times, and the repeat
    // pushed the row onto a third line. When a group shares one time it is said once,
    // under the group's name; each button still carries it for a screen reader.
    const shared = mine.length > 1 && mine.every(r => r[3] === mine[0][3])
      ? exitTime(mine[0][3]) : "";
    return `<div class="exgroup" role="group" aria-labelledby="exg-${g}">
      <span class="exlabel" id="exg-${g}">${label}${
        shared ? `<small aria-hidden="true">${esc(shared)} each</small>` : ""}</span>
      <div class="exlist">${mine.map(r => {
        const [id, name, , time, why, journey] = r;
        const shut = why >= 0;
        const t = exitTime(time);
        return `<button type="button" class="exitbtn${shut ? " shut" : ""}${
          S.confirm === id ? " asking" : ""}" data-exit="${esc(id)}"${
          shut ? ` aria-disabled="true" aria-describedby="exline"` : ""}${
          journey && !shut ? ` aria-expanded="${S.confirm === id}" aria-controls="exline"` : ""
        }>${esc(name)}${!t ? "" : shared ? `<span class="vh">, ${esc(t)}</span>`
          : `<span class="t">, ${esc(t)}</span>`}${
          shut ? `<span class="vh"> (shut)</span>` : ""}</button>`;
      }).join("")}</div></div>`;
  }).join("");
  // The line under the row exists only where it can be needed, and then always, so the
  // reason or the confirm fills a space that was already there.
  const needLine = rows.some(r => r[4] >= 0 || r[5]);
  let line = "";
  const asking = rows.find(r => r[0] === S.confirm);
  if (asking) {
    line = `<div class="confirm" role="group" aria-label="Confirm the journey">
      <span>${esc(asking[1])}: ${esc(asking[3])}. The days pass on the road.</span>
      <button type="button" class="small go" data-setout="${esc(asking[0])}">Set out</button>
      <button type="button" class="small quiet" data-notnow>Not now</button></div>`;
  } else if (S.why) {
    line = esc(S.why);
  } else if (rows.some(r => r[4] >= 0)) {
    line = `<span class="dimline">Point at a shut way to read why it is shut.</span>`;
  }
  $("#exits").innerHTML = groups
    + (needLine ? `<div class="exline" id="exline" aria-live="polite">${line}</div>` : "");
}

function renderSuggestions() {
  // The recording's own suggestions belong to the gate; anywhere else the mock has none,
  // rather than inventing some.
  const list = S.place === D.start ? D.suggestions : [];
  $("#suggestions").innerHTML = list.map(t =>
    `<button type="button" class="sugg" data-sugg="${esc(t)}">${esc(t)}</button>`).join("");
}

function renderTrade() {
  const near = exitsHere().filter(r => /market|merchants row/.test(r[1]) && r[4] < 0);
  const names = near.map(r => r[1]).join(" and ");
  $("#trade-say").textContent = "Nobody here keeps a counter." + (near.length
    ? ` ${cap(names)} ${near.length > 1 ? "are" : "is"} next door, ${near[0][3]}.` : "");
}

// --- The story -------------------------------------------------------------------------------
function renderStory(scroll = true) {
  const box = $("#story");
  box.innerHTML = S.transcript.map(b => {
    if (b.who === "player") return `<p class="beat player">${esc(b.text)}</p>`;
    if (b.kind === "aside") return `<p class="beat aside">${esc(b.text)}</p>`;
    return `<p class="beat ${b.kind === "consequence" ? "consequence" : "setup"}">${
      esc(b.text)}</p>`;
  }).join("");
  // The story scrolls inside the book on a wide screen, and the book's inside on a phone.
  if (scroll) { box.scrollTop = box.scrollHeight; $("#bookin").scrollTop = $("#bookin").scrollHeight; }
}
function say(player, aside) {
  if (player) S.transcript.push({ who: "player", text: player });
  if (aside) S.transcript.push({ who: "gm", kind: "aside", text: aside });
  renderStory();
}

// --- The map ----------------------------------------------------------------------------------
// The flat board is 03-offers-and-map.js renderMap's drawing, on the recorded grid; the
// 3D board is scene3d.js itself, loaded from play/static and handed the same payload.
function renderBoard() {
  const G = D.ground, g = G.grid, B = S.board;
  $$("[data-view]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.view === B.view)));
  // Places (places.js) is the town, not the ground: the controls for the ground keep their
  // places but go out of use, hidden by visibility, so nothing in the head row moves under
  // the pointer that pressed Places. Turn keeps whatever room it had (it shows in 3D).
  const places = B.view === "places" && window.Places;
  $("#turnctl").hidden = (places ? B.last : B.view) !== "3d";
  $("#turnctl").style.visibility = places ? "hidden" : "";
  $("#levelctl").style.visibility = places ? "hidden" : "";
  $("#board").classList.toggle("threed", B.view === "3d");
  $("#board").classList.toggle("places", !!places);
  const levels = (g.levels && g.levels.length > 1) ? g.levels : [0];
  $("#levelctl").hidden = levels.length < 2;
  if (places) { renderLevels(levels); window.Places.render(); return; }
  $("#board-name").textContent = g.place ? `The ground · ${g.place}` : "The ground";
  renderLevels(levels);
  drawGround(G, g, B, levels);
}
function renderLevels(levels) {
  const B = S.board;
  $("#levelctl").innerHTML = `<span class="seglabel">Looking at</span>` + levels.map(v =>
    `<button type="button" data-level="${v}" aria-pressed="${v === B.level}">${
      v ? `+${v * 5} ft` : "the floor"}</button>`).join("");
}
function drawGround(G, g, B, levels) {
  const CELL = 18, parts = [];
  const ground = new Map((g.floor || []).map(([c, r, v]) => [`${c},${r}`, v]));
  const cell = (c, r, cls, inner = "") => `<rect class="${cls}" x="${c * CELL}" y="${
    r * CELL}" width="${CELL}" height="${CELL}">${inner}</rect>`;
  let svg;
  if (B.view === "3d" && window.Scene3D) {
    svg = window.Scene3D.render(g, G.actors, { turn: B.turn, level: B.level,
                                               reach: !!G.in_encounter });
  } else {
    for (const [c, r] of g.difficult) parts.push(cell(c, r, "difficult"));
    for (const [c, r] of g.obscuring) parts.push(cell(c, r, "obscuring"));
    for (const [c, r] of g.blocked) parts.push(cell(c, r, "blocked"));
    for (const [c, r, v] of (g.floor || []))
      parts.push(cell(c, r, `up${Math.min(3, v)}`, `<title>${v * 5} ft above the floor</title>`));
    for (const [c, r, v] of (g.parapet || []))
      parts.push(`<line class="rail" x1="${c * CELL + 2}" y1="${(r + .5) * CELL}" x2="${
        (c + 1) * CELL - 2}" y2="${(r + .5) * CELL}"><title>a rail, ${v * 5} ft up</title></line>`);
    for (const [c, r, cost] of (g.reachable || [])) {
      const lvl = ground.get(`${c},${r}`) || 0;
      parts.push(cell(c, r, "reach", `<title>${cost} ft${lvl ? `, ${lvl * 5} ft up` : ""}</title>`)
        .replace('class="reach"', `class="reach" data-sq="${c},${r}" data-cost="${cost}"`));
    }
    for (let c = 0; c <= g.width; c++)
      parts.push(`<line class="rule" x1="${c * CELL}" y1="0" x2="${c * CELL}" y2="${g.height * CELL}"/>`);
    for (let r = 0; r <= g.height; r++)
      parts.push(`<line class="rule" x1="0" y1="${r * CELL}" x2="${g.width * CELL}" y2="${r * CELL}"/>`);
    if (B.picked) parts.push(`<rect class="picked" x="${B.picked[0] * CELL + 1}" y="${
      B.picked[1] * CELL + 1}" width="${CELL - 2}" height="${CELL - 2}" rx="2"/>`);
    for (const a of G.actors) {
      if (!a.at) continue;
      const [c, r] = a.at, n = a.squares || 1;
      const side = a.is_pc ? " pc" : a.side ? (a.side === "pc" || a.side === "you" ? " ally" : " foe")
        : (G.in_encounter ? " bystander" : "");
      const ghost = (a.at.length > 2 ? a.at[2] : 0) === B.level ? "" : " offlevel";
      parts.push(`<rect class="token${side}${ghost}" x="${c * CELL + 2}" y="${r * CELL + 2}"
        width="${n * CELL - 4}" height="${n * CELL - 4}" rx="3"><title>${esc(a.name)}, ${
        a.hp} of ${a.hp_max}</title></rect>`);
      parts.push(`<text class="tok" x="${(c + n / 2) * CELL}" y="${(r + n / 2) * CELL + 4}">${
        esc(a.name.slice(0, 1).toUpperCase())}</text>`);
    }
    svg = `<svg id="map" viewBox="0 0 ${g.width * CELL} ${g.height * CELL}"
      preserveAspectRatio="xMidYMid meet" role="img" aria-label="The ground, seen from above">${
      parts.join("")}</svg>`;
  }
  $("#boardview").innerHTML = svg;
  $("#board-about").textContent = g.about || "";
  const who = G.actors.filter(a => !a.is_pc).map(a => `the ${a.name}`);
  $("#board-key").innerHTML = B.view === "flat"
    ? `<i style="background:var(--gold)"></i>You <i style="background:#6b4a3a"></i>${
      esc(cap(who.join(" and ")))} <i style="background:#4a4130"></i>raised ground, ${
      levels.slice(-1)[0] * 5} ft <i style="background:rgba(221,196,142,.35)"></i>${
      (g.reachable || []).length} squares within ${g.speed || pc().speed} ft`
    : `Turned ${B.turn * 90} degrees. The lamp stays where it is when the board turns.`;
  $("#board-say").innerHTML = B.say ? `<span class="say-aside">${esc(B.say)}</span>`
    : B.view === "flat" ? `<span class="why">Choose a lit square to see how far away it is.</span>` : "";
}

// --- Spells page ---------------------------------------------------------------------------
const lvlWord = l => (l ? `Level ${l}` : "Cantrip");
function renderSpells() {
  const c = pc();
  const box = $("#spells3");
  if (!c.spells) { box.innerHTML = ""; return; }
  const sp = c.spells;
  const slots = sp.slots.map(sl => `<div class="slotrow">
      <div class="lv"><b>${sl.level ? "Level " + sl.level : "Cantrips"}</b><span>DC ${sl.dc}</span></div>
      <div class="sockets" role="img" aria-label="${sl.left} of ${sl.max} ready">${
        "<i></i>".repeat(sl.left)}</div>
    </div>`).join("");
  const prepared = sp.known.filter(k => k.prepared > 0);
  const today = prepared.map(k => `<li class="sc-${school(k)}">${glyph(spellIcon(k), "spells")}
      <span style="color:var(--ink)">${esc(k.name)}${k.prepared > 1 ? ` <small>x${k.prepared}</small>` : ""}</span>
      <small>${lvlWord(k.level)}</small></li>`).join("");
  const shown = S.spellFilter === "prepared" ? prepared : sp.known;
  const levels = [...new Set(shown.map(k => k.level))].sort((a, b) => a - b);
  const grid = levels.map(lv => `<h3>${lv ? "Level " + lv : "Cantrips"}</h3><div class="spellgrid">${
    shown.filter(k => k.level === lv).map(k => `<button type="button" class="sc-${school(k)}${
      k.prepared ? " prep" : ""}" data-spell="${k.id}" aria-pressed="${S.spell === k.id}">${
      glyph(spellIcon(k), "spells")}<span style="color:var(--ink)">${esc(k.name)}</span>${
      k.prepared ? `<span class="vh">, prepared</span>` : ""}</button>`).join("")}</div>`).join("");
  const pick = sp.known.find(k => k.id === S.spell);
  box.innerHTML = `
    <div class="framedcard"><h2>Slots today</h2>${slots}
      <p class="why" style="margin-top:10px">${esc(sp.note)}</p></div>
    <div class="framedcard"><h2>Prepared today</h2><ul class="plain today">${today}</ul></div>
    <div class="framedcard book-grid"><h2>Spellbook</h2>
      <div class="seg" role="group" aria-label="Show" style="margin-bottom:12px">
        <button type="button" data-spellfilter="all" aria-pressed="${S.spellFilter === "all"}">All ${
          sp.known.length}</button>
        <button type="button" data-spellfilter="prepared" aria-pressed="${
          S.spellFilter === "prepared"}">Prepared ${prepared.length}</button></div>
      ${grid}
      <p class="spellsay" aria-live="polite">${pick ? `<b>${esc(pick.name)}</b>. ${lvlWord(pick.level)}, ${
        esc(pick.school)}. Range ${esc(pick.range)}. Lasts ${esc(pick.duration)}. Save ${
        esc(pick.save)}. ${esc((pick.components || []).join(", "))}.${
        pick.prepared ? " Prepared today." : ""}` : `<span class="why">Choose a spell to read it.</span>`}</p>
      <p class="credit">Spell icons from <a href="https://game-icons.net">game-icons.net</a>,
      <a href="https://creativecommons.org/licenses/by/3.0/">CC BY 3.0</a>, recoloured by
      school.</p></div>`;
  rims(box);
  paintIcons(box);
}

function renderSpellPick() {
  const c = pc();
  if (!c.spells) return;
  $("#spellpick").innerHTML = c.spells.known.filter(k => k.prepared > 0).map(k =>
    `<button type="button" data-attach="${k.id}"><span class="sc-${school(k)}">${
      glyph(spellIcon(k), "spells")}</span><span>${esc(k.name)}</span><small>${
      lvlWord(k.level)}</small></button>`).join("");
  paintIcons($("#spellpick"));
}
const spellById = id => (pc().spells ? pc().spells.known.find(k => k.id === id) : null);

function renderAttach() {
  const box = $("#attach"), sp = S.attach && spellById(S.attach);
  box.hidden = !sp;
  box.innerHTML = sp ? `<span class="chip sc-${school(sp)}">${esc(sp.name)}<button type="button"
    class="small quiet" data-detach aria-label="Remove ${esc(sp.name)} from this turn">Remove</button></span>` : "";
}

// --- Equipment --------------------------------------------------------------------------------
const qty = b => (b.unit ? `${b.count} ${b.unit}` : b.count > 1 ? `x${b.count}` : "");
const INERT = "for show, no effect in play";

// "Wearing it" in the engine's numbers: what this item would change against what is worn
// now, as looked up among the combinations build_data.py asked the engine about.
function gain(b) {
  const e = eq(), now = nums();
  let key = null;
  const magic = pc().basket.filter(x => x.kind === "slot" && x.slot !== "body"
    && e.slots[x.slot] === x.name).map(x => x.name);
  if (b.kind === "armour") key = `${b.key}|${e.shield}|${[...magic].sort().join(",")}`;
  if (b.kind === "shield") key = `${e.armour}|${b.key}|${[...magic].sort().join(",")}`;
  if (b.kind === "slot" && b.slot !== "body") {
    const keep = magic.filter(n => pc().basket.find(x => x.name === n).slot !== b.slot);
    key = `${e.armour}|${e.shield}|${[...keep, b.name].sort().join(",")}`;
  }
  const then = key && pc().loadouts[key];
  if (!then) return "";
  const out = [];
  if (then.ac !== now.ac) out.push(`AC ${now.ac} to ${then.ac}`);
  if (then.touch !== now.touch) out.push(`touch ${now.touch} to ${then.touch}`);
  if (then.ff !== now.ff) out.push(`flat-footed ${now.ff} to ${then.ff}`);
  for (const [k, w] of [["fort", "Fort"], ["ref", "Ref"], ["will", "Will"]])
    if (then.saves[k] !== now.saves[k]) out.push(`${w} ${signed(now.saves[k])} to ${signed(then.saves[k])}`);
  return out.length ? `Wearing it: ${out.join(", ")}.` : "";
}

function facts(b) {
  const bits = [];
  if (b.kind === "weapon") {
    const a = b.attack;
    bits.push(`${a.damage} ${a.type}, ${a.crit}, ${a.swings.map(signed).join("/")} to hit`);
    if (a.range_ft) bits.push(`range ${a.range_ft} ft`);
    else if (a.category !== "melee") bits.push("range not known");
    if (a.weight_lb != null) bits.push(`${a.weight_lb} lb`);
    if (!a.proficient) bits.push("not proficient");
  } else if (b.kind === "armour" || b.kind === "shield") {
    const a = b.armour;
    bits.push(`${signed(a.ac)} AC`);
    if (b.kind === "armour" && a.max_dex != null && a.max_dex < 90) bits.push(`max Dex ${signed(a.max_dex)}`);
    bits.push(a.acp ? `check ${a.acp}` : "no check penalty");
    if (a.class) bits.push(`${a.class} armour`);
  } else if (b.kind === "slot" && b.slot === "body") {
    bits.push("clothing, worn on the body", INERT);
  } else if (b.kind === "slot") {
    bits.push(`worn at the ${slotLabel(b.slot).toLowerCase()}`);
  } else {
    bits.push(INERT);
  }
  const g = !inUse(b) ? gain(b) : "";
  return `${esc(bits.join(", "))}${g ? `. <span class="gain">${esc(g)}</span>` : ""}`;
}

// Which buttons a row offers: what the thing can be asked to do, given where it is now.
function actionsFor(b) {
  const on = inUse(b), acts = [];
  if (b.kind === "weapon" && !on) acts.push(["wield", "Wield", true]);
  if (["armour", "shield", "slot"].includes(b.kind)) {
    acts.push(on ? ["take off", "Take off", false] : ["wear", "Wear", true]);
  }
  if (b.kind === "consumable") acts.push(["use", "Use", false]);
  acts.push(["drop", "Drop", false]);
  return acts;
}

function fits(b, slot) {
  if (slot === "hand") return b.kind === "weapon";
  if (slot === "armor") return b.kind === "armour";
  if (slot === "shield") return b.kind === "shield";
  return b.kind === "slot" && b.slot === slot;
}

function renderEquipment() {
  const c = pc(), n = nums();
  const counts = {};
  c.basket.forEach(b => { counts[b.shelf] = (counts[b.shelf] || 0) + 1; });
  if (S.shelf !== "all" && !counts[S.shelf]) S.shelf = "all";
  const railBtn = (id, label, icon, count) => `<button type="button" role="tab" data-shelf="${id}"
      aria-selected="${!S.fit && S.shelf === id}" tabindex="${!S.fit && S.shelf === id ? 0 : -1}"
      aria-controls="eq-list">${glyph(icon)}<span>${esc(label)}</span><small>${count}</small></button>`;
  $("#eq-rail").innerHTML = railBtn("all", "Everything", "lorc-knapsack", c.basket.length)
    + Object.entries(SHELVES).filter(([id]) => counts[id])
      .map(([id, s]) => railBtn(id, s.label, s.icon, counts[id])).join("")
    + (S.fit ? `<div class="fitting">Showing what fits the ${esc(
        S.fit === "hand" ? "hand" : slotLabel(S.fit).toLowerCase())}.<br>
        <button type="button" class="quiet" data-unfit>Show everything</button></div>` : "");

  const list = c.basket.filter(b => (S.fit ? fits(b, S.fit)
    : S.shelf === "all" || b.shelf === S.shelf))
    // A to Z and nothing else. "In use first" was tried and moved the row just pressed to
    // the top of the list, out from under the pointer, which is the one kind of motion the
    // owner has ruled out; what is in use is marked where it stands instead.
    .sort((a, b) => a.name.localeCompare(b.name));
  $("#eq-listhead").textContent = S.fit
    ? `Fits the ${S.fit === "hand" ? "hand" : slotLabel(S.fit).toLowerCase()}`
    : S.shelf === "all" ? "Everything you carry" : SHELVES[S.shelf].label;
  $("#eq-sort").textContent = `${list.length} ${list.length === 1 ? "thing" : "things"}, A to Z`;
  // The reply line is always there, so a reply arriving never pushes the list down.
  $("#eq-say").innerHTML = S.eqSay ? `<span class="say-aside">${esc(S.eqSay)}</span>`
    : `<span class="why">Wield, wear or take something off, and what the engine says back is written here.</span>`;
  $("#eq-rows").innerHTML = list.length ? list.map(b => {
    const on = inUse(b);
    const where = on ? (b.kind === "weapon" ? "in hand" : "worn") : "";
    return `<li class="eqrow${on ? " inuse" : ""}" data-item="${esc(b.id)}">
      <span class="tile${on ? " inuse" : ""}">${glyph(itemIcon(b))}</span>
      <span class="eqname"><b>${esc(b.name)}</b>${qty(b) ? `<span class="qty">${esc(qty(b))}</span>` : ""}${
        where ? `<span class="chip">${where}</span>` : ""}
        <span class="facts">${facts(b)}</span></span>
      <span class="eqacts">${actionsFor(b).map(([act, label, main]) =>
        `<button type="button" class="${main ? "go" : "quiet"}" data-act="${act}" data-item="${
          esc(b.id)}" aria-label="${label} ${esc(b.name)}">${label}</button>`).join("")}</span>
    </li>`;
  }).join("") : `<li class="why">Nothing you carry goes there. A counter may sell one: Trade.</li>`;

  const known = c.basket.filter(b => b.weight_lb != null);
  const lb = known.reduce((s, b) => s + b.weight_lb * (b.unit ? 1 : b.count), 0);
  $("#eq-load").innerHTML = `<b>Weight.</b> ${lb} lb that the engine knows of, from the ${
    words(known.length)} weapons; nothing else it carries has a weight yet. <b>Load</b> is <span
    class="unknown">not tracked</span>, so nothing here slows ${esc(c.name.split(" ")[0])} down.`;

  // The numbers across the head move when something is put on, and say so by colour.
  const base = c.numbers;
  const nd = (dt, now, was, sign = false) => `<div><dt>${dt}</dt><dd class="${
    now !== was ? "moved" : ""}">${sign ? signed(now) : now}</dd></div>`;
  $("#eq-nums").innerHTML = nd("AC", n.ac, base.ac) + nd("Touch", n.touch, base.touch)
    + nd("Flat", n.ff, base.ff) + nd("Fort", n.saves.fort, base.saves.fort, true)
    + nd("Ref", n.saves.ref, base.saves.ref, true) + nd("Will", n.saves.will, base.saves.will, true);

  // Worn and wielded. The engine holds one weapon in hand (`Actor.equipped`), and the
  // shield is its own body slot; there is no off-hand weapon to show, so the box says so.
  const hand = inHand();
  const slotBtn = (key, label, item, icon) => `<button type="button" class="slotbtn${
      item ? "" : " empty"}" data-slot="${key}" aria-pressed="${S.fit === key}">
      <span class="tile${item ? " inuse" : ""}">${icon ? glyph(icon) : ""}</span>
      <span><span class="sl">${esc(label)}</span><span class="it">${esc(item || "empty")}</span></span></button>`;
  $("#hands").innerHTML = slotBtn("hand", "In hand", hand ? hand.name : "", hand ? itemIcon(hand) : "")
    + `<div class="slotbtn empty" aria-label="Off hand: the engine holds one weapon at a time">
        <span class="tile"></span><span><span class="sl">Off hand</span>
        <span class="it">one weapon at a time</span></span></div>`;
  const e = eq();
  const col = side => `<div class="slotcol">${c.slots[side].map(s => {
    let item = "";
    if (s.key === "armor") item = e.armour !== "none"
      ? (c.basket.find(b => b.key === e.armour) || {}).name : "";
    else if (s.key === "shield") item = e.shield !== "none"
      ? (c.basket.find(b => b.key === e.shield) || {}).name : "";
    else item = e.slots[s.key] || "";
    const worn = item && c.basket.find(b => b.name === item);
    return slotBtn(s.key, s.label, item, worn ? itemIcon(worn) : SLOT_ICON[s.key] || "");
  }).join("")}</div>`;
  $("#slots").innerHTML = col("left") + col("right");
  paintIcons($("#mode-equipment"));
}

// The engine's own tells for what the Equipment page can do, word for word where one
// exists (rules/engine.py _op_wear, play/views.py wear_item), and a plain refusal where the
// engine has nothing to do it with.
function act(action, id) {
  const c = pc(), e = eq(), b = c.basket.find(x => x.id === id);
  if (!b) return;
  const before = nums();
  let line = "";
  if (action === "wield") {
    e.hand = b.attack.key;
    line = `${c.name} draws the ${b.name}.`;
  } else if (action === "wear" && (b.kind === "armour" || b.kind === "shield")) {
    if (b.kind === "armour") e.armour = b.key; else e.shield = b.key;
    const after = nums();
    line = `${c.name} puts on the ${b.name}.${after.ac !== before.ac
      ? ` Armour class ${before.ac} to ${after.ac}.` : ""}`;
  } else if (action === "wear") {
    const held = e.slots[b.slot];
    if (held) {
      line = `${slotLabel(b.slot)} is already holding ${held}. Take that off first.`;
    } else {
      e.slots[b.slot] = b.name;
      line = `${c.name} puts on ${b.name} (${b.slot}).`;
    }
  } else if (action === "take off" && (b.kind === "armour" || b.kind === "shield")) {
    line = `Mock. The engine cannot take ${b.kind === "armour" ? "armour" : "a shield"} off yet: ` +
      `its wear op swaps one for another, and nothing removes it.`;
  } else if (action === "take off") {
    delete e.slots[b.slot];
    line = `${c.name} takes off ${b.name}.`;
  } else if (action === "use") {
    line = `Mock. Using it goes to the engine's use op, which drinks, throws or coats as the ` +
      `thing allows. For a bought ${b.name} the engine has no rules yet.`;
  } else if (action === "drop") {
    line = `Mock. The engine has no drop yet: nothing puts a carried thing down. To part ` +
      `with it today, sell it at a counter (Trade).`;
  }
  S.eqSay = line;
  renderEquipment();
  renderSheet();
  const again = document.querySelector(`#eq-rows [data-item="${CSS.escape(id)}"] button`);
  if (again) again.focus();
}

// --- Talk ---------------------------------------------------------------------------------------
// 08-conversation.js, drawn from the recorded lines: a person picker, the log with a
// heading per speaker, and Ignore and Take your leave below the log, never in its scroll.
const convo = D.conversation;
const convoName = ref => (convo.people.find(p => p.ref === ref) || {}).name
  || (convo.recent.find(e => e.who === ref) || {}).name || "";
const convoView = () => S.convoPick
  || (convo.people.find(p => p.talking) || {}).ref || "all";
const convoInvolves = (e, ref) => e.who === ref || e.to === ref;
const unread = () => convo.recent.filter(e => e.n > S.convoSeen && e.who !== "you").length;

function renderTalk() {
  const n = S.talkOpen ? 0 : unread();
  $("#talkcount").textContent = n ? `${n} new` : "";
  $("#talkbtn").setAttribute("aria-expanded", String(S.talkOpen));
  $("#talkbtn").setAttribute("aria-label", n ? `Talk, ${n} new lines` : "Talk");
  $("#talk").hidden = !S.talkOpen;
  document.body.classList.toggle("talkopen", S.talkOpen);
  if (!S.talkOpen) return;
  const view = convoView();
  const here = convo.people.filter(p => p.present), away = convo.people.filter(p => !p.present);
  $("#convo-people").innerHTML = `<button type="button" data-convo="all" aria-pressed="${
      view === "all"}">Everyone</button>` + here.map(p => `<button type="button" data-convo="${
      p.ref}" aria-pressed="${view === p.ref}">${esc(cap(p.name))}</button>`).join("")
    + (away.length ? `<select id="convo-earlier" aria-label="Earlier conversations">
        <option value="">Earlier conversations</option>${away.map(p => `<option value="${
        p.ref}"${view === p.ref ? " selected" : ""}>${esc(cap(p.name))}</option>`).join("")}</select>` : "");
  const list = convo.recent.filter(e => view === "all" || convoInvolves(e, view));
  let out = "", day = null, group = null;
  const close = () => { if (group !== null) out += `</div>`; group = null; };
  for (const e of list) {
    const d = Math.floor((e.t || 0) / 1440) + 1;
    if (d !== day) { close(); out += `<p class="cl-day">Day ${d}</p>`; day = d; }
    const key = `${e.who}|${e.beat}`;
    if (group !== key) {
      close();
      out += `<div class="cl-turn"><span class="cl-name">${esc(cap(e.name))}</span>`;
      group = key;
    }
    out += `<p><q>${esc(e.text)}</q></p>`;
  }
  close();
  const log = $("#convo-log");
  log.innerHTML = out || `<p class="why">Nothing said with ${view === "all" ? "anybody here"
    : esc(convoName(view))} yet.</p>`;
  log.scrollTop = log.scrollHeight;
  const talking = convo.people.filter(p => p.talking);
  // The reply sits above the two buttons, in a line kept for it, so they never move.
  $("#talkfoot").innerHTML = `<p class="say-aside">${esc(S.talkSay)}</p>`
    + (talking.length ? talking.map(p => `<div class="talker">
      <span>In conversation with ${esc(theName(p.name))}</span>
      <button type="button" class="quiet small" data-ignore="${p.ref}"
              title="Do not answer them">Ignore</button></div>`).join("")
    + `<button type="button" class="quiet" id="takeleave" title="End the conversation">Take your leave</button>`
    : `<p class="why">Nobody is talking with you.</p>`);
}
function openTalk() {
  if (!["table", "map", "sheet"].includes(S.mode)) setMode("table");
  S.talkOpen = true;
  S.convoSeen = Math.max(...convo.recent.map(e => e.n));
  renderTalk();
  const to = $('#convo-people [aria-pressed="true"]') || $("#talkclose");
  if (to) to.focus({ preventScroll: true });
}
function closeTalk() {
  const had = $("#talk").contains(document.activeElement);
  S.talkOpen = false;
  renderTalk();
  if (had) $("#talkbtn").focus();
}

// --- Modes ------------------------------------------------------------------------------------
const MODES = ["table", "map", "sheet", "equipment", "spells", "trade", "journal"];
const visibleModes = () => MODES.filter(m => !$(`#tab-${m}`).hidden);
function setMode(mode, focusTab = false) {
  if (!visibleModes().includes(mode)) mode = "table";
  S.mode = mode;
  document.body.classList.remove(...MODES.map(m => "mode-" + m));
  document.body.classList.add("mode-" + mode);
  $$(".modes [role=tab]").forEach(t => {
    const on = t.dataset.mode === mode;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
    if (on && focusTab) t.focus();
    // On a phone the row scrolls sideways; the chosen tab is kept in view.
    if (on) $(".modes").scrollLeft = Math.max(0, Math.min($(".modes").scrollLeft,
      t.offsetLeft - 4), t.offsetLeft + t.offsetWidth - $(".modes").clientWidth + 4);
  });
  $("#stage").setAttribute("aria-labelledby", `tab-${["map", "sheet"].includes(mode) ? mode : "table"}`);
  ["equipment", "spells", "trade", "journal"].forEach(m => { $("#mode-" + m).hidden = mode !== m; });
  if (!["table", "map", "sheet"].includes(mode) && S.talkOpen) { S.talkOpen = false; renderTalk(); }
  closePops();
  if (mode === "spells") renderSpells();
  if (mode === "table") renderStory();
  if (mode === "map") renderBoard();
  if (mode === "equipment") renderEquipment();
  if (mode === "journal") renderJournal();
}

function closePops() {
  ["craftpop", "spellpop"].forEach(id => { $("#" + id).hidden = true; });
  $("#craft").setAttribute("aria-expanded", "false");
  $("#spells").setAttribute("aria-expanded", "false");
}

function renderJournal() {
  $("#walked").innerHTML = S.walked.map(n => `<li>${esc(n)}</li>`).join("");
  rims($("#mode-journal"));
}

// --- Events -----------------------------------------------------------------------------------
document.addEventListener("click", e => {
  const t = e.target.closest("button, [data-exit], [data-sq]");
  if (!t) return;

  if (t.matches(".viewing [role=radio]")) { setChar(t.dataset.char); return; }
  if (t.matches(".modes [role=tab]")) { setMode(t.dataset.mode); return; }

  if (t.id === "sheettoggle") {
    S.sheetHidden = !S.sheetHidden;
    document.body.classList.toggle("sheet-hidden", S.sheetHidden);
    t.textContent = S.sheetHidden ? "Show sheet" : "Hide sheet";
    t.setAttribute("aria-expanded", String(!S.sheetHidden));
    return;
  }
  if (t.id === "glance") { setMode("sheet"); return; }
  if (t.id === "open-equipment" || t.id === "trade-equipment") { setMode("equipment"); return; }
  if (t.id === "eq-trade") { setMode("trade"); return; }
  if (t.id === "talkbtn") { if (S.talkOpen) closeTalk(); else openTalk(); return; }
  if (t.id === "talkclose") { closeTalk(); return; }
  if (t.dataset.convo) { S.convoPick = t.dataset.convo; renderTalk();
    const again = $(`[data-convo="${t.dataset.convo}"]`); if (again) again.focus(); return; }
  if (t.dataset.ignore) {
    S.talkSay = `Mock. Ignore goes to /api/talk: you stop answering ${
      theName(convoName(t.dataset.ignore))}, who may take it well or badly, and the conversation ` +
      `stays open until you leave it.`;
    renderTalk(); return;
  }
  if (t.id === "takeleave") {
    S.talkSay = "Mock. Take your leave goes to /api/talk and ends the conversation. The " +
      "log stays here to read.";
    renderTalk(); return;
  }

  if (t.dataset.exit) {
    const row = exitsHere().find(r => r[0] === t.dataset.exit);
    if (!row) return;
    if (row[4] >= 0) { S.why = reason(row[4]); renderExits(); return; }
    if (row[5] && S.confirm !== row[0]) {
      S.confirm = row[0]; S.why = ""; renderExits();
      const go = $("[data-setout]"); if (go) go.focus();
      return;
    }
    // Every move is a turn: the engine and the narrator run before the page moves on
    // (device.js). The arrival is drawn when the prose appears, as in the app.
    Turn.take(() => walk(row));
    return;
  }
  if (t.dataset.setout) {
    const row = exitsHere().find(r => r[0] === t.dataset.setout);
    Turn.take(() => {
      S.confirm = null;
      say(`I go to ${row[1]}.`, `Mock. The journey to ${row[1]} is declared and ${
        row[3].replace(/^about /, "")} pass on the road. The mock ends at the road head, so ` +
        `you are still standing here.`);
      renderExits();
    });
    return;
  }
  if (t.hasAttribute("data-notnow")) {
    const was = S.confirm; S.confirm = null; renderExits();
    const back = was && document.querySelector(`[data-exit="${CSS.escape(was)}"]`);
    if (back) back.focus();
    return;
  }

  if (t.dataset.person) {
    S.person = S.person === t.dataset.person ? null : t.dataset.person;
    renderScene();
    return;
  }
  if (t.dataset.sugg) {
    // The app's own behaviour: a suggestion fills the pen; Say sends it.
    const input = $("#input");
    input.value = t.dataset.sugg;
    input.focus();
    return;
  }
  if (t.id === "continue") {
    Turn.take(() => say("", `Mock. Continue: ${pc().name} keeps to what ${she()} was doing ` +
      `and the scene moves a beat. People act, the guard answers or loses patience, and the ` +
      `narrator tells it.`));
    return;
  }
  if (t.id === "craft") {
    const open = $("#craftpop").hidden;
    closePops();
    $("#craftpop").hidden = !open;
    t.setAttribute("aria-expanded", String(open));
    return;
  }
  if (t.id === "spells") {
    const open = $("#spellpop").hidden;
    closePops();
    if (open) renderSpellPick();
    $("#spellpop").hidden = !open;
    t.setAttribute("aria-expanded", String(open));
    if (open) { const first = $("#spellpick button"); if (first) first.focus(); }
    return;
  }
  if (t.dataset.attach) {
    S.attach = t.dataset.attach; closePops(); renderAttach();
    $("#input").focus();
    return;
  }
  if (t.hasAttribute("data-detach")) { S.attach = null; renderAttach(); $("#input").focus(); return; }
  if (t.dataset.close) { closePops(); return; }

  if (t.dataset.spell) {
    S.spell = S.spell === t.dataset.spell ? null : t.dataset.spell;
    renderSpells();
    const again = document.querySelector(`[data-spell="${t.dataset.spell}"]`);
    if (again) again.focus();
    return;
  }
  if (t.dataset.spellfilter) {
    S.spellFilter = t.dataset.spellfilter; renderSpells();
    const again = $(`[data-spellfilter="${S.spellFilter}"]`); if (again) again.focus();
    return;
  }

  // The board.
  if (t.dataset.view) {
    // Places is its own button: pressed again, it goes back to the ground as it was left.
    const B = S.board, v = t.dataset.view;
    if (v === "places") B.view = B.view === "places" ? B.last : "places";
    else { B.view = v; B.last = v; }
    B.say = ""; renderBoard();
    $(`[data-view="${t.dataset.view}"]`).focus(); return; }
  if (t.dataset.turn) { S.board.turn = (S.board.turn + Number(t.dataset.turn) + 4) % 4;
    renderBoard(); $(`[data-turn="${t.dataset.turn}"]`).focus(); return; }
  if (t.dataset.level) { S.board.level = Number(t.dataset.level); renderBoard();
    $(`[data-level="${t.dataset.level}"]`).focus(); return; }
  if (t.dataset.sq) {
    const [c, r] = t.dataset.sq.split(",").map(Number);
    S.board.picked = [c, r];
    S.board.say = `Mock. ${t.dataset.cost} ft away. In a fight, a move would go here; ` +
      `out of one, you walk by the ways on.`;
    renderBoard();
    return;
  }

  // Equipment.
  if (t.dataset.shelf) { S.shelf = t.dataset.shelf; S.fit = null; S.eqSay = ""; renderEquipment();
    $(`#eq-rail [data-shelf="${t.dataset.shelf}"]`).focus(); return; }
  if (t.hasAttribute("data-unfit")) { S.fit = null; renderEquipment();
    $(`#eq-rail [aria-selected="true"]`).focus(); return; }
  if (t.dataset.slot) {
    S.fit = S.fit === t.dataset.slot ? null : t.dataset.slot; S.eqSay = "";
    renderEquipment();
    const again = $(`#doll [data-slot="${t.dataset.slot}"]`); if (again) again.focus();
    return;
  }
  if (t.dataset.act) { act(t.dataset.act, t.dataset.item); return; }

  if (t.id === "portrait-add") { $("#portrait-file").click(); return; }
  if (t.id === "portrait-remove") {
    URL.revokeObjectURL(S.portraits[S.char]); delete S.portraits[S.char];
    renderSheet(); $("#portrait-add").focus();
    return;
  }
  if (t.id === "mock-reset") { reset(); return; }
});

document.addEventListener("change", e => {
  if (e.target.id === "convo-earlier" && e.target.value) {
    S.convoPick = e.target.value; renderTalk(); $("#convo-earlier").focus();
  }
});

function walk(row) {
  const [id, name, , time] = row;
  S.confirm = null; S.why = ""; S.person = null;
  const from = place().name;
  if (!D.places[id]) {
    say(`I go to ${name}.`, `Mock. ${name} is not a place the mock holds.`);
    return;
  }
  S.place = id;
  S.walked.push(name);
  // Every move in the mock comes through here (the exits row) or through the chart's Walk
  // there, so the chart's visited set is kept here. The mock has no place chips in the pen.
  if (window.Places) window.Places.visit(id);
  say(`I go to ${name}.`, `Mock. The engine moves you from ${from} to ${name}, ${
    time}. The narrator's beat for the walk and the arrival would follow here. The ways on ` +
    `below are the engine's own for ${name}.`);
  renderScene();
}

// Shut ways say why while they are pointed at or focused, in the line held open for it.
document.addEventListener("mouseover", e => {
  const b = e.target.closest && e.target.closest(".exitbtn.shut");
  if (!b || S.confirm) return;
  const row = exitsHere().find(r => r[0] === b.dataset.exit);
  const why = row ? reason(row[4]) : "";
  if (why !== S.why) { S.why = why; renderExitLine(); }
});
document.addEventListener("focusin", e => {
  const b = e.target.closest && e.target.closest(".exitbtn");
  if (!b || S.confirm) return;
  const row = exitsHere().find(r => r[0] === b.dataset.exit);
  const why = row && row[4] >= 0 ? reason(row[4]) : "";
  if (why !== S.why) { S.why = why; renderExitLine(); }
});
// Only the line is rewritten, never the buttons, so hovering does not rebuild what is
// under the pointer.
function renderExitLine() {
  const line = $("#exline");
  if (!line) return;
  line.innerHTML = S.why ? esc(S.why)
    : `<span class="dimline">Point at a shut way to read why it is shut.</span>`;
}

$("#sayform").addEventListener("submit", e => {
  e.preventDefault();
  const input = $("#input");
  let text = input.value.trim();
  const sp = S.attach && spellById(S.attach);
  if (!text && !sp) { input.focus(); return; }
  if (!text && sp) text = `I cast ${sp.name}.`;
  const cast = sp ? ` with ${sp.name} attached` : "";
  // The words stay in the box until the turn is taken, as the app keeps them through a
  // refusal or a busy table (04-combat-and-turns.js takeTurn).
  Turn.take(() => {
    say(text, `Mock. The turn goes to the engine${cast}; the narrator's answer arrives here.`);
    input.value = ""; S.attach = null; renderAttach(); input.focus();
  });
});

$("#portrait-file").addEventListener("change", e => {
  const f = e.target.files && e.target.files[0];
  if (!f || !f.type.startsWith("image/")) return;
  if (S.portraits[S.char]) URL.revokeObjectURL(S.portraits[S.char]);
  S.portraits[S.char] = URL.createObjectURL(f);
  e.target.value = "";
  renderSheet();
  $("#portrait-add").focus();
});

// Tabs: arrows move along the row, Home and End jump (the ARIA tabs pattern), skipping a
// tab this character does not have.
$(".modes").addEventListener("keydown", e => {
  const modes = visibleModes(), i = modes.indexOf(S.mode);
  const to = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: modes.length - 1 }[e.key];
  if (to === undefined) return;
  e.preventDefault();
  setMode(modes[(to + modes.length) % modes.length], true);
});
$("#eq-rail").addEventListener("keydown", e => {
  const tabs = $$("#eq-rail [role=tab]"), i = tabs.indexOf(document.activeElement);
  const to = { ArrowDown: i + 1, ArrowUp: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
  if (to === undefined || i < 0) return;
  e.preventDefault();
  const next = tabs[(to + tabs.length) % tabs.length];
  S.shelf = next.dataset.shelf; S.fit = null; renderEquipment();
  $(`#eq-rail [data-shelf="${S.shelf}"]`).focus();
});
$(".viewing").addEventListener("keydown", e => {
  if (!["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].includes(e.key)) return;
  e.preventDefault();
  setChar(S.char === "kesst" ? "ysolde" : "kesst");
  $(`.viewing [data-char="${S.char}"]`).focus();
});

document.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  if (!$("#craftpop").hidden) { closePops(); $("#craft").focus(); return; }
  if (!$("#spellpop").hidden) { closePops(); $("#spells").focus(); return; }
  if (S.talkOpen) closeTalk();
});

function setChar(id) {
  if (id === S.char) return;
  S.char = id; S.spell = null; S.attach = null; S.fit = null; S.eqSay = "";
  renderStrip(); renderAttach(); renderSheet(); renderScene();
  // A tab this character does not have is not left open.
  setMode(S.mode);
}
$("#mock-wanted").addEventListener("change", e => {
  S.wanted = e.target.checked; S.confirm = null; S.why = "";
  renderSheet(); renderScene();
  if (S.mode === "map") renderBoard();   // the chart marks the ways the watch holds
});

function reset() {
  S.place = D.start; S.confirm = null; S.why = ""; S.person = null; S.attach = null;
  S.transcript = D.transcript.map(b => ({ ...b }));
  S.walked = [D.places[D.start].name];
  S.eq = Object.fromEntries(Object.entries(D.chars).map(([k, c]) => [k, freshEq(c)]));
  S.eqSay = ""; S.fit = null; S.talkSay = "";
  if (window.Places) window.Places.reset();
  renderAttach(); renderScene(); renderStory(); renderSheet();
  setMode(S.mode);
}

// The carried flame (06-trade-and-page.js). Position comes from the pointer; intensity
// from noise: three sine waves at irrational frequency ratios plus a bounded random walk,
// written to CSS variables so the browser only composites transforms and opacity. The
// shadows do not follow it here: the brief fixes one lamp for every surface, scene3d.js's.
{
  const root = document.documentElement.style;
  document.addEventListener("pointermove", e => {
    root.setProperty("--cx", `${e.clientX}px`);
    root.setProperty("--cy", `${e.clientY}px`);
  }, { passive: true });
  let walkNoise = 0;
  const tick = now => {
    const t = now / 1000;
    walkNoise = Math.max(-0.5, Math.min(0.5, walkNoise + (Math.random() - 0.5) * 0.04));
    const flick = 0.72 + 0.14 * Math.sin(t * 1.7) + 0.09 * Math.sin(t * 4.3 + 1.3)
      + 0.05 * Math.sin(t * 9.1 + 4.1) + 0.12 * walkNoise;
    root.setProperty("--flick", flick.toFixed(3));
    root.setProperty("--jx", `${(Math.sin(t * 2.9) * 1.2).toFixed(2)}px`);
    root.setProperty("--jy", `${(Math.sin(t * 3.7 + 2) * 0.9).toFixed(2)}px`);
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

rims();
renderStrip();
renderSheet();
renderScene();
renderStory();
renderTalk();

// A link can open the mock at a state: #char=ysolde&mode=spells&talk=1&view=3d&wanted=1.
// For sending the owner straight to a thing, and for screenshotting every state.
{
  const q = new URLSearchParams(location.hash.slice(1));
  if (q.get("char") && D.chars[q.get("char")]) setChar(q.get("char"));
  if (q.get("wanted")) { $("#mock-wanted").checked = true; S.wanted = true; renderSheet(); renderScene(); }
  if (q.get("view")) S.board.view = ["3d", "places"].includes(q.get("view")) ? q.get("view") : "flat";
  if (S.board.view === "3d") S.board.last = "3d";
  if (q.get("turn")) S.board.turn = Number(q.get("turn")) & 3;
  if (q.get("shelf")) S.shelf = q.get("shelf");
  if (q.get("fit")) S.fit = q.get("fit");
  if (q.get("hide")) $("#sheettoggle").click();
  setMode(q.get("mode") || "table");
  if (q.get("talk")) openTalk();
}
