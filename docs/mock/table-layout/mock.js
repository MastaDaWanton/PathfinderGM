// The table layout mock. Static: it reads window.MOCK_DATA (data.js, generated from the
// engine and a recording) and the two characters below, and answers clicks with canned
// lines. Nothing here reaches a server or a model.
//
// The owner's motion rule holds throughout: every change is instant, and anything that
// opens does so without moving what was under the pointer.
"use strict";

const D = window.MOCK_DATA;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const signed = n => (n >= 0 ? "+" : "") + n;
const mod = score => Math.floor((score - 10) / 2);

// --- The two characters ------------------------------------------------------------------
// Numbers are `pc.summary()` for each fixture, loaded into the Pangrella world
// (rules/sheet.py load_pc). Gear marked `kit` is an example outfitter basket; the rest is
// the fixture's own weapons, armour and the free outfit rules/creation.py grants.
// Icons are chosen by the app's own tables (06-trade-and-page.js TRADE_ITEM_ICONS, and
// 05-sheet.js SPELL_ICONS / SPELL_SCHOOLS): a rapier has no picture of its own, so it
// wears the weapons shelf's broadsword, as it does in the trade window.
const CHARS = {
  kesst: {
    name: "Kesst Vayr", line: "Rogue 1, human of the Zhilakai, she/her",
    hp: 9, hp_max: 9, ac: 15, speed: 30,
    abilities: { str: 12, dex: 17, con: 12, int: 13, wis: 10, cha: 14 },
    saves: { fort: 1, ref: 5, will: 0 },
    skills: { "Stealth": 9, "Acrobatics": 7, "Disable device": 7, "Bluff": 6,
              "Diplomacy": 6, "Sense motive": 6, "Appraise": 5, "Climb": 5,
              "Knowledge (local)": 5, "Perception": 4 },
    feats: ["Weapon Finesse", "Stealthy"],
    xp: [0, 2000], background: "Thief-taker",
    notes: "Zhilakai, flightless, in a city whose nobility is winged. Kesst works the " +
           "seam between the two.",
    gear: [
      ["Rapier", "lorc-broadsword", "Wielded", "Weapons"],
      ["Dagger", "lorc-plain-dagger", "", "Weapons"],
      ["Leather armour", "delapouite-leather-armor", "Worn", "Armour"],
      ["Traveler's outfit", "delapouite-clothes", "Worn", "Gear"],
      ["Thieves' tools", "delapouite-lockpicks", "", "Gear", "kit"],
      ["Backpack", "delapouite-backpack", "Worn", "Gear", "kit"],
      ["Bedroll", "delapouite-sleeping-bag", "", "Gear", "kit"],
      ["Waterskin", "delapouite-water-flask", "", "Gear", "kit"],
      ["Flint and steel", "delapouite-flint-spark", "", "Gear", "kit"],
      ["Silk rope", "delapouite-rope-coil", "", "Gear", "kit"],
      ["Torch", "delapouite-torch", "", "Gear", "kit"],
      ["Trail rations", "delapouite-hot-meal", "", "Consumables", "kit"],
    ],
    caster: null,
  },
  ysolde: {
    name: "Ysolde Marrach", line: "Wizard 1, human, she/her",
    hp: 7, hp_max: 7, ac: 12, speed: 30,
    abilities: { str: 8, dex: 14, con: 12, int: 17, wis: 12, cha: 10 },
    saves: { fort: 1, ref: 2, will: 5 },
    skills: { "Knowledge (arcana)": 7, "Knowledge (nature)": 7, "Spellcraft": 7,
              "Perception": 2 },
    feats: ["Iron Will"],
    xp: [0, 2000], background: "None chosen",
    notes: "The fixture wizard with a real spellbook: every cantrip of the Core Rulebook " +
           "and six first-level spells.",
    gear: [
      ["Quarterstaff", "delapouite-bo", "Wielded", "Weapons"],
      ["Dagger", "lorc-plain-dagger", "", "Weapons"],
      ["Scholar's outfit", "delapouite-clothes", "Worn", "Gear"],
      ["Backpack", "delapouite-backpack", "Worn", "Gear", "kit"],
      ["Ink and quill", "lorc-quill-ink", "", "Gear", "kit"],
      ["Candles", "lorc-candle-light", "", "Gear", "kit"],
      ["Bedroll", "delapouite-sleeping-bag", "", "Gear", "kit"],
      ["Trail rations", "delapouite-hot-meal", "", "Consumables", "kit"],
    ],
    // casting.ensure_prepared on the fixture: 3 cantrips and 2 first-level slots, filled
    // from the book in its own order. DC is 10 + spell level + Int modifier (+3).
    caster: {
      slots: [[0, 3, 13], [1, 2, 14]],
      prepared: ["acid-splash", "arcane-mark", "bleed", "burning-hands", "magic-missile"],
    },
  },
};

// The fixture wizard's spellbook: [id, name, level, school, icon].
const BOOK = [
  ["acid-splash", "Acid Splash", 0, "conjuration", "lorc-acid-blob"],
  ["arcane-mark", "Arcane Mark", 0, "universal", "lorc-star-swirl"],
  ["bleed", "Bleed", 0, "necromancy", "lorc-bleeding-wound"],
  ["dancing-lights", "Dancing Lights", 0, "evocation", "delapouite-bolt-spell-cast"],
  ["daze", "Daze", 0, "enchantment", "delapouite-knocked-out-stars"],
  ["detect-magic", "Detect Magic", 0, "divination", "lorc-third-eye"],
  ["detect-poison", "Detect Poison", 0, "divination", "lorc-crystal-ball"],
  ["disrupt-undead", "Disrupt Undead", 0, "necromancy", "lorc-broken-skull"],
  ["flare", "Flare", 0, "evocation", "delapouite-bolt-spell-cast"],
  ["ghost-sound", "Ghost Sound", 0, "illusion", "lorc-duality-mask"],
  ["light", "Light", 0, "evocation", "lorc-candle-light"],
  ["mage-hand", "Mage Hand", 0, "transmutation", "lorc-magic-palm"],
  ["mending", "Mending", 0, "transmutation", "lorc-potion-ball"],
  ["message", "Message", 0, "transmutation", "lorc-potion-ball"],
  ["open-close", "Open/Close", 0, "transmutation", "lorc-potion-ball"],
  ["prestidigitation", "Prestidigitation", 0, "universal", "delapouite-magick-trick"],
  ["ray-of-frost", "Ray of Frost", 0, "evocation", "lorc-ice-bolt"],
  ["read-magic", "Read Magic", 0, "divination", "lorc-crystal-ball"],
  ["resistance", "Resistance", 0, "abjuration", "lorc-magic-shield"],
  ["touch-of-fatigue", "Touch of Fatigue", 0, "necromancy", "lorc-dread-skull"],
  ["burning-hands", "Burning Hands", 1, "evocation", "lorc-glowing-hands"],
  ["magic-missile", "Magic Missile", 1, "evocation", "lorc-missile-swarm"],
  ["color-spray", "Color Spray", 1, "illusion", "lorc-rainbow-star"],
  ["sleep", "Sleep", 1, "enchantment", "lorc-sleepy"],
  ["mage-armor", "Mage Armor", 1, "conjuration", "lorc-energy-shield"],
  ["shield", "Shield", 1, "abjuration", "lorc-shield-reflect"],
];
const SPELL = Object.fromEntries(BOOK.map(b => [b[0], b]));

// --- Icons: the repo's own SVGs, inlined so currentColor tints them ----------------------
// The app inlines by fetch rather than using a CSS mask, because a mask needs the server
// to call the file image/svg+xml and on Windows that answer comes from the registry. The
// mock does the same, for the same reason.
const ICON_BASE = { items: "../../../play/static/icons/items/",
                    spells: "../../../play/static/icons/spells/" };
const SVG = new Map();
const glyph = (name, set, cls = "") =>
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

// --- State ----------------------------------------------------------------------------------
const S = {
  char: "kesst", place: D.start, wanted: false, mode: "table", sheetHidden: false,
  transcript: D.transcript.map(b => ({ ...b })), confirm: null, why: "",
  gear: null, spell: null, person: null, attach: null, portraits: {},
};
const pc = () => CHARS[S.char];
const place = id => D.places[id || S.place];

// --- The sheet ------------------------------------------------------------------------------
const ABILITY_WORDS = [["str", "Str"], ["dex", "Dex"], ["con", "Con"],
                       ["int", "Int"], ["wis", "Wis"], ["cha", "Cha"]];
const ABILITY_NAMES = { str: "Strength", dex: "Dexterity", con: "Constitution",
                        int: "Intelligence", wis: "Wisdom", cha: "Charisma" };

function renderSheet() {
  const c = pc();
  $("#pc-name").textContent = c.name;
  $("#pc-line").textContent = c.line;
  const state = $("#pc-state");
  state.hidden = !S.wanted;
  state.textContent = "Wanted in Zhilvarnia";

  const img = $("#portrait-img"), url = S.portraits[S.char];
  img.hidden = !url; if (url) { img.src = url; img.alt = `Portrait of ${c.name}`; }
  $("#portrait-empty").hidden = !!url;
  $("#portrait-add").textContent = url ? "Change" : "Add a portrait";
  $("#portrait-remove").hidden = !url;

  $("#gear").innerHTML = c.gear.map(([name, icon, where], i) =>
    `<button type="button" data-gear="${i}" aria-pressed="${S.gear === i}"
      aria-label="${esc(name)}${where ? ", " + where.toLowerCase() : ""}"
      ${where ? `class="worn"` : ""}>${glyph(icon, "items")}</button>`).join("");
  gearSay(S.gear);

  $("#life-bar").style.width = Math.round(100 * c.hp / c.hp_max) + "%";
  $("#life-say").innerHTML = `<b>${c.hp}</b> of ${c.hp_max}`;
  $("#medals").innerHTML = ABILITY_WORDS.map(([k, w]) =>
    `<li class="medal"><span class="vh">${ABILITY_NAMES[k]} ${c.abilities[k]}, modifier ${
      signed(mod(c.abilities[k]))}</span><div aria-hidden="true"><span class="ab">${w}</span>
      <span class="sc">${c.abilities[k]}</span></div>
      <span class="md" aria-hidden="true">${signed(mod(c.abilities[k]))}</span></li>`).join("");
  const plaque = (dt, dd) => `<div><dt>${dt}</dt><dd>${dd}</dd></div>`;
  $("#defence").innerHTML = plaque("AC", c.ac) + plaque("Speed", c.speed + " ft");
  $("#saves").innerHTML = plaque("Fort", signed(c.saves.fort))
    + plaque("Ref", signed(c.saves.ref)) + plaque("Will", signed(c.saves.will));
  $("#xp").textContent = `${c.xp[0].toLocaleString("en")} of ${
    c.xp[1].toLocaleString("en")} for level 2`;

  $("#skills").innerHTML = Object.entries(c.skills).map(([k, v]) =>
    `<div><dt>${esc(k)}</dt><dd>${signed(v)}</dd></div>`).join("");
  $("#feats").innerHTML = c.feats.map(f => `<li>${esc(f)}</li>`).join("");
  $("#background").textContent = c.background;
  $("#notes").textContent = c.notes;

  $("#glance").textContent = `Life ${c.hp} of ${c.hp_max}, AC ${c.ac}`;
  $("#glance").setAttribute("aria-label", `Life ${c.hp} of ${c.hp_max}, armour class ${
    c.ac}. Open the sheet`);
  $("#spells").hidden = !c.caster;
  paintIcons($("#sheet"));
}

// The line under the gear: the tile pointed at or focused, else the one chosen.
function gearSay(i) {
  const g = i != null ? pc().gear[i] : null;
  $("#gear-say").textContent = g
    ? `${g[0]}. ${g[2] ? g[2] + ". " : ""}${g[3]}.${g[4] ? " From the example kit." : ""}`
    : "Point at a tile, or choose one, to read what it is.";
}
["mouseover", "focusin"].forEach(ev => $("#gear").addEventListener(ev, e => {
  const b = e.target.closest("[data-gear]");
  if (b) gearSay(Number(b.dataset.gear));
}));
["mouseleave", "focusout"].forEach(ev => $("#gear").addEventListener(ev, e => {
  if (ev === "focusout" && $("#gear").contains(e.relatedTarget)) return;
  gearSay(S.gear);
}));

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
  $("#where-line").textContent = `${where} ${D.day_part[0].toUpperCase()}${
    D.day_part.slice(1)}.`;
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
          : `<span class="t"> &middot; ${esc(t)}</span>`}${
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
    ? ` ${names[0].toUpperCase() + names.slice(1)} ${near.length > 1 ? "are" : "is"
      } next door, ${near[0][3]}.` : "");
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
  // The story scrolls inside the book on a wide screen, and the book itself on a phone.
  if (scroll) { box.scrollTop = box.scrollHeight; $("#book").scrollTop = $("#book").scrollHeight; }
}
function say(player, aside) {
  if (player) S.transcript.push({ who: "player", text: player });
  if (aside) S.transcript.push({ who: "gm", kind: "aside", text: aside });
  renderStory();
}

// --- Spells page ---------------------------------------------------------------------------
function renderSpells() {
  const c = pc();
  const box = $("#spells3");
  if (!c.caster) {
    box.innerHTML = `<div class="card" style="grid-column:1/-1;max-width:620px;margin:0 auto">
      <h2>Spells</h2><p>${esc(c.name)} casts no spells.</p>
      <p class="mocknote">Switch the mock to Ysolde Marrach, in the Mock menu, to see this
      page with a spellbook.</p></div>`;
    return;
  }
  const slots = c.caster.slots.map(([lv, n, dc]) => `<div class="slotrow">
      <div class="lv"><b>${lv ? "Level " + lv : "Cantrips"}</b><span>DC ${dc}</span></div>
      <div class="sockets" aria-label="${n} of ${n} ready">${"<i></i>".repeat(n)}</div>
    </div>`).join("");
  const today = c.caster.prepared.map(id => {
    const [, name, lv, school, icon] = SPELL[id];
    return `<li class="sc-${school}">${glyph(icon, "spells")}<span style="color:var(--ink)">${
      esc(name)}</span><small>${lv ? "Level " + lv : "Cantrip"}</small></li>`;
  }).join("");
  const grid = lv => BOOK.filter(b => b[2] === lv).map(([id, name, , school, icon]) =>
    `<button type="button" class="sc-${school}${c.caster.prepared.includes(id) ? " prep" : ""}"
      data-spell="${id}" aria-pressed="${S.spell === id}">${glyph(icon, "spells")}
      <span style="color:var(--ink)">${esc(name)}</span></button>`).join("");
  const sp = S.spell ? SPELL[S.spell] : null;
  box.innerHTML = `
    <div class="card"><h2>Slots today</h2>${slots}
      <p class="mocknote" style="margin-top:10px">Every slot is ready; spent ones would show
      as red sockets until a long rest.</p></div>
    <div class="card"><h2>Prepared today</h2><ul class="plain today">${today}</ul></div>
    <div class="card book-grid"><h2>Spellbook</h2>
      <h3>Cantrips</h3><div class="spellgrid">${grid(0)}</div>
      <h3>Level 1</h3><div class="spellgrid">${grid(1)}</div>
      <p class="spellsay" aria-live="polite">${sp ? `${esc(sp[1])}. ${
        sp[2] ? "Level " + sp[2] : "Cantrip"}, ${sp[3]}.${
        c.caster.prepared.includes(sp[0]) ? " Prepared today." : ""}` : ""}</p>
      <p class="credit">Spell icons from <a href="https://game-icons.net">game-icons.net</a>,
      <a href="https://creativecommons.org/licenses/by/3.0/">CC BY 3.0</a>, recoloured by
      school.</p></div>`;
  paintIcons(box);
}

function renderSpellPick() {
  const c = pc();
  if (!c.caster) return;
  $("#spellpick").innerHTML = c.caster.prepared.map(id => {
    const [, name, lv, school, icon] = SPELL[id];
    return `<button type="button" data-attach="${id}"><span class="sc-${school}">${
      glyph(icon, "spells")}</span><span>${esc(name)}</span><small>${
      lv ? "Level " + lv : "Cantrip"}</small></button>`;
  }).join("");
  paintIcons($("#spellpick"));
}

function renderAttach() {
  const box = $("#attach");
  box.hidden = !S.attach;
  box.innerHTML = S.attach ? `<span class="chip sc-${SPELL[S.attach][3]}">${
    esc(SPELL[S.attach][1])}<button type="button" class="small quiet" data-detach
    aria-label="Remove ${esc(SPELL[S.attach][1])} from this turn">Remove</button></span>` : "";
}

// --- Modes ------------------------------------------------------------------------------------
const MODES = ["table", "sheet", "spells", "trade", "journal"];
function setMode(mode, focusTab = false) {
  S.mode = mode;
  document.body.classList.remove(...MODES.map(m => "mode-" + m));
  document.body.classList.add("mode-" + mode);
  document.querySelectorAll(".modes [role=tab]").forEach(t => {
    const on = t.dataset.mode === mode;
    t.setAttribute("aria-selected", on);
    t.tabIndex = on ? 0 : -1;
    if (on && focusTab) t.focus();
  });
  $("#stage").setAttribute("aria-labelledby", mode === "sheet" ? "tab-sheet" : "tab-table");
  $("#stage").hidden = !(mode === "table" || mode === "sheet");
  $("#mode-spells").hidden = mode !== "spells";
  $("#mode-trade").hidden = mode !== "trade";
  $("#mode-journal").hidden = mode !== "journal";
  closePops();
  if (mode === "spells") renderSpells();
  if (mode === "table") renderStory();
}

function closePops() {
  ["craftpop", "spellpop"].forEach(id => { $("#" + id).hidden = true; });
  $("#craft").setAttribute("aria-expanded", "false");
  $("#spells").setAttribute("aria-expanded", "false");
}

// --- Events -----------------------------------------------------------------------------------
document.addEventListener("click", e => {
  const t = e.target.closest("button, [data-exit]");
  if (!t) return;

  if (t.matches(".modes [role=tab]")) { setMode(t.dataset.mode); return; }

  if (t.id === "sheettoggle") {
    S.sheetHidden = !S.sheetHidden;
    document.body.classList.toggle("sheet-hidden", S.sheetHidden);
    t.textContent = S.sheetHidden ? "Show the sheet" : "Hide the sheet";
    t.setAttribute("aria-expanded", String(!S.sheetHidden));
    return;
  }
  if (t.id === "glance") { setMode("sheet"); return; }

  if (t.dataset.exit) {
    const row = exitsHere().find(r => r[0] === t.dataset.exit);
    if (!row) return;
    if (row[4] >= 0) { S.why = reason(row[4]); renderExits(); return; }
    if (row[5] && S.confirm !== row[0]) {
      S.confirm = row[0]; S.why = ""; renderExits();
      const go = $("[data-setout]"); if (go) go.focus();
      return;
    }
    walk(row);
    return;
  }
  if (t.dataset.setout) {
    const row = exitsHere().find(r => r[0] === t.dataset.setout);
    S.confirm = null;
    say(`I go to ${row[1]}.`, `Mock. The journey to ${row[1]} is declared and ${
      row[3].replace(/^about /, "")} pass on the road. The mock ends at the road head, so ` +
      `you are still standing here.`);
    renderExits();
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
    say("", `Mock. Continue: ${pc().name} keeps to what she was doing and the scene moves ` +
      `a beat. People act, the guard answers or loses patience, and the narrator tells it.`);
    return;
  }
  if (t.id === "craft") {
    const open = $("#craftpop").hidden;
    closePops();
    $("#craftpop").hidden = !open;
    t.setAttribute("aria-expanded", String(open));
    return;
  }
  if (t.id === "trade") { setMode("trade"); return; }
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

  if (t.dataset.gear) {
    const i = Number(t.dataset.gear);
    S.gear = S.gear === i ? null : i;
    renderSheet();
    const again = document.querySelector(`[data-gear="${i}"]`); if (again) again.focus();
    return;
  }
  if (t.dataset.spell) {
    S.spell = S.spell === t.dataset.spell ? null : t.dataset.spell;
    renderSpells();
    const again = document.querySelector(`[data-spell="${S.spell || t.dataset.spell}"]`);
    if (again) again.focus();
    return;
  }

  if (t.id === "portrait-add") { $("#portrait-file").click(); return; }
  if (t.id === "portrait-remove") {
    URL.revokeObjectURL(S.portraits[S.char]); delete S.portraits[S.char];
    renderSheet(); $("#portrait-add").focus();
    return;
  }
  if (t.id === "mock-reset") { reset(); return; }
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
  if (!text && !S.attach) { input.focus(); return; }
  if (!text && S.attach) text = `I cast ${SPELL[S.attach][1]}.`;
  const cast = S.attach ? ` with ${SPELL[S.attach][1]} attached` : "";
  say(text, `Mock. The turn goes to the engine${cast}; the narrator's answer arrives here.`);
  input.value = ""; S.attach = null; renderAttach(); input.focus();
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

// Tabs: arrows move along the row, Home and End jump (the ARIA tabs pattern).
$(".modes").addEventListener("keydown", e => {
  const i = MODES.indexOf(S.mode);
  const to = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: MODES.length - 1 }[e.key];
  if (to === undefined) return;
  e.preventDefault();
  setMode(MODES[(to + MODES.length) % MODES.length], true);
});

document.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  if (!$("#craftpop").hidden) { closePops(); $("#craft").focus(); return; }
  if (!$("#spellpop").hidden) { closePops(); $("#spells").focus(); return; }
  const m = document.querySelector(".mockctl[open]");
  if (m) { m.open = false; m.querySelector("summary").focus(); }
});

$("#mock-char").addEventListener("change", e => {
  S.char = e.target.value; S.gear = null; S.spell = null; S.attach = null;
  renderAttach(); renderSheet(); renderScene();
  if (S.mode === "spells") renderSpells();
});
$("#mock-wanted").addEventListener("change", e => {
  S.wanted = e.target.checked; S.confirm = null; S.why = "";
  renderSheet(); renderScene();
});

function reset() {
  S.place = D.start; S.confirm = null; S.why = ""; S.person = null; S.attach = null;
  S.transcript = D.transcript.map(b => ({ ...b }));
  renderAttach(); renderScene(); renderStory();
}

function renderSaid() {
  const by = new Map();
  D.said.forEach(s => { if (!by.has(s.who)) by.set(s.who, []); by.get(s.who).push(s.line); });
  $("#said").innerHTML = [...by].map(([who, lines]) =>
    `<p class="who">${esc(who[0].toUpperCase() + who.slice(1))}</p>${
      lines.map(l => `<q>${esc(l)}</q>`).join("")}`).join("");
}

renderSheet();
renderScene();
renderStory();
renderSaid();
