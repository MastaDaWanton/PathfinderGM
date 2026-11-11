// What the player may know before committing, worked out once per drawing and read by
// both views, so flat and 3D cannot disagree. Every set here is a straight read of a
// field the engine sent (window.POLISH_SCENE.extras and .light in the mock); nothing is
// computed that the engine did not rule on. The target's AC and the hidden goblin are not
// in the payload, so they cannot leak from here.

// The room's lamp, from the hour. Colours are the theme's own tokens, not new hues:
// --candle by day, --ink at noon (the whitest light the palette has), --ember at the
// turning hours, --player (the cool blue) at night. Strength follows the engine's light
// level. The dice read the same lamp in the game (dice3d.js), so it is published on window
// rather than kept inside the board.
function pvLamp(light) {
  const phase = (light && light.phase && light.phase.phase) || "";
  const ambient = (light && light.ambient) || "normal";
  const hex = { noon: "#e8ddc4", morning: "#f0c070", afternoon: "#f0c070",
                dawn: "rgb(255,176,84)", dusk: "rgb(255,176,84)",
                night: "#8fb0c8", midnight: "#8fb0c8" }[phase] || "#f0c070";
  const rgb = { noon: [232, 221, 196], morning: [240, 192, 112], afternoon: [240, 192, 112],
                dawn: [255, 176, 84], dusk: [255, 176, 84],
                night: [143, 176, 200], midnight: [143, 176, 200] }[phase] || [240, 192, 112];
  const strength = { bright: 1, normal: 0.92, dim: 0.8, dark: 0.66 }[ambient] || 0.92;
  // How far the colour leans the board. Small on purpose: the owner asked for subtle,
  // and the board has to read at night.
  const lean = { noon: 0.18, morning: 0.25, afternoon: 0.25, dawn: 0.45, dusk: 0.45,
                 night: 0.45, midnight: 0.5 }[phase] || 0.25;
  const peak = Math.max(...rgb);
  const mult = rgb.map(v => strength * (1 - lean + lean * v / peak));
  const lamp = { phase, ambient, hex, rgb, strength, mult,
                 // The flat board's multiply wash: how much of the lamp colour to lay over.
                 wash: Math.min(0.42, (1 - strength) * 1.2 + lean * 0.35) };
  window.ROOM_LAMP = lamp;
  return lamp;
}

function pvRead(s) {
  const sc = window.POLISH_SCENE || {};
  const x = sc.extras || {};
  const g = s.scene.grid || {};
  const actors = s.scene.actors || [];
  const byRef = new Map(actors.map(a => [a.ref, a]));
  const threat = new Set();
  for (const sqs of Object.values((x.threatened || {}).by_foe || {}))
    for (const [c, r] of sqs) threat.add(`${c},${r}`);
  const unseen = new Set(((x.sight || {}).squares || [])
    .filter(q => !q[2]).map(q => `${q[0]},${q[1]}`));
  const areasOn = (g.areas || []).some(a => a && (a.cells || []).length);
  // Who the laid area catches is the engine's `areas.caught`; shown only while the area
  // itself is on the board.
  const caught = new Set(areasOn && x.spell_area ? (x.spell_area.caught || []) : []);
  const provokes = (x.provokes || {}).squares || {};
  // A lit square the engine did not list as provoking, while some square does: a move
  // that draws no attack. Only meaningful when the provokes answer is present at all.
  const safe = new Set(Object.keys(provokes).length
    ? (g.reachable || []).map(q => `${q[0]},${q[1]}`).filter(k => !provokes[k]) : []);
  return {
    byRef, threat, unseen, caught, safe, provokes,
    attack: (x.attack_preview || {}).by_foe || {},
    cover: (x.sight || {}).cover || {},
    hunches: (x.awareness || {}).hunches || [],
    spell: areasOn && x.spell_area ? x.spell_area.spell : "",
    turn: s.scene.in_encounter ? s.scene.turn_ref : null,
    pc: actors.find(a => a.stance === "pc" || a.is_pc),
    light: sc.light || null,
    lamp: pvLamp(sc.light),
    reach: new Map((g.reachable || []).map(([c, r, cost, lvl]) => [`${c},${r}`, { cost, lvl }])),
  };
}

let PV_NOW = null;

const pvName = (ref, pv) => (pv.byRef.get(ref) || {}).name || "someone";
const pvSigned = n => (n < 0 ? `-${-n}` : `+${n}`);
const pvCap = t => t ? t[0].toUpperCase() + t.slice(1) : t;
function pvList(items) {
  if (items.length < 2) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

// The line under the board when nothing is pointed at.
function pvIdle(pv) {
  const who = pv.turn && pv.byRef.get(pv.turn);
  const head = who ? `${esc(who.name)}'s turn` : "Out of combat";
  let tail = who && who === pv.pc
    ? "Point at a foe for your attack, or at a lit square for the move."
    : "";
  if (pv.spell && pv.caught.size)
    tail = `${esc(pvCap(pv.spell.replace(/-/g, " ")))} catches ${
      esc(pvList([...pv.caught].map(r => pvName(r, pv))))}.`;
  return `<span class="rd-head">${head}</span><span class="rd-body">${tail}</span>`;
}

// A foe pointed at: the PC's own itemised bonus per weapon. Never the target's AC and
// never a roll needed: the game rolls without a dc and hides both.
function pvFoe(ref, pv) {
  const a = pv.byRef.get(ref);
  if (!a) return pvIdle(pv);
  const rows = pv.attack[ref];
  const head = `${esc(a.name)}`;
  if (!rows) {
    const what = a === pv.pc ? "you" : a.stance === "ally" ? "on your side"
      : a.stance === "foe" ? "a foe" : "standing by";
    return `<span class="rd-head">${head}</span><span class="rd-body">${esc(what)}</span>`;
  }
  const cover = pv.cover[ref];
  const coverLine = cover && cover !== "none"
    ? `<span class="rd-note">${cover === "total" ? "Total cover from you" :
        cover === "soft" ? "Soft cover from you" : "Has cover from you"}</span>` : "";
  const reachRows = rows.filter(w => w.in_reach);
  if (!reachRows.length)
    return `<span class="rd-head">${head}</span><span class="rd-body">Out of reach of your ${
      esc(pvList(rows.map(w => w.name)))}.</span>${coverLine}`;
  // Weapons that come to the same bonus from the same terms are one line ("Rapier or
  // dagger"): two identical rows read as two different choices.
  const groups = new Map();
  for (const w of reachRows) {
    const k = JSON.stringify([w.bonus, w.terms]);
    if (!groups.has(k)) groups.set(k, { w, names: [] });
    groups.get(k).names.push(w.name);
  }
  const weapons = [...groups.values()].map(({ w, names }) => {
    const sit = new Set((w.situational || []).map(t => t[0]));
    const terms = (w.terms || []).map(([k, v]) =>
      `<span class="${sit.has(k) ? "rd-sit" : "rd-term"}">${esc(k)} ${pvSigned(v)}</span>`).join(", ");
    const called = pvCap(names.join(" or "));
    return `<span class="rd-weapon"><b>${esc(called)} ${pvSigned(w.bonus)}</b> ${terms}</span>`;
  }).join("");
  return `<span class="rd-head">${head}</span><span class="rd-body">${weapons}</span>${coverLine}`;
}

// A square pointed at: how far, and whether leaving for it provokes.
function pvSquare(sq, pv) {
  const [c, r] = sq.split(",");
  const k = `${c},${r}`;
  const at = pv.reach.get(k);
  if (!at) return pvIdle(pv);
  const by = pv.provokes[k] || [];
  const up = at.lvl ? `, ${at.lvl * 5} ft up` : "";
  const moveLine = by.length
    ? `<span class="rd-warn">Provokes attacks from ${
        esc(pvList(by.map(ref => pvName(ref, pv))))}.</span>`
    : `<span class="rd-safe">Does not provoke.</span>`;
  const threat = pv.threat.has(k) ? `<span class="rd-note">Threatened.</span>` : "";
  return `<span class="rd-head">${at.cost} ft away${up}</span><span class="rd-body">${
    moveLine}${threat}</span>`;
}

function pvShow(html) {
  const el = document.getElementById("boardread");
  if (el && el.innerHTML !== html) el.innerHTML = html;
}

function pvPoint(e) {
  if (!PV_NOW || !e.target.closest) return;
  const t = e.target.closest("#mapwrap [data-ref], #mapwrap [data-sq]");
  if (!t) return pvShow(pvIdle(PV_NOW));
  pvShow(t.dataset.ref ? pvFoe(t.dataset.ref, PV_NOW) : pvSquare(t.dataset.sq, PV_NOW));
}
document.addEventListener("mouseover", pvPoint);
document.addEventListener("focusin", pvPoint);

// The key: only the marks this board is actually showing, so a quiet board has a quiet
// foot. Swatches are the marks themselves at small size.
function pvKey(pv, g, reachCount) {
  const items = [];
  if (g.speed) items.push(`<span class="key"><i class="sw sw-reach"></i>${reachCount} squares within ${g.speed} ft</span>`);
  if (Object.keys(pv.provokes).length) items.push(`<span class="key"><i class="sw sw-provoke"></i>Provokes</span>`);
  if (pv.safe.size) items.push(`<span class="key"><i class="sw sw-safe"></i>Does not provoke</span>`);
  if (pv.threat.size) items.push(`<span class="key"><i class="sw sw-threat"></i>Threatened</span>`);
  if (pv.unseen.size) items.push(`<span class="key"><i class="sw sw-unseen"></i>Out of sight</span>`);
  for (const h of pv.hunches)
    items.push(`<span class="key"><i class="sw sw-hunch"></i>Someone unseen within ${h.within_ft} ft</span>`);
  if (pv.light) {
    const L = pv.light;
    items.push(`<span class="key"><i class="sw sw-lamp" style="background:${pv.lamp.hex}"></i>${
      esc(pvCap(L.ambient || "normal"))} light, ${esc(L.day_part || L.phase && L.phase.phase || "")}</span>`);
  }
  return `<div class="boardkeys">${items.join("")}</div>`;
}
