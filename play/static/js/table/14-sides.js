// The play table, part 14 (the two sides). Classic script, sharing one global scope with
// 01-13 and 15-21.
//
// One sheet, split round the story (the approved design, docs/mock/table-layout/): who
// the character is on the left, their numbers on the right. This is the side column's
// old "Sheet" panel, redrawn: every field it read from `s.pc` is read here, and each
// lands where the design puts it (docs/table-rebuild-inventory.md, N1-N7). Skills and
// feats, which the old panel listed in full, are the Sheet tab's Skills and Feats pages.
//
// The state carries only `pc.ac`, and nothing names the armour or the shield. Those two,
// and touch and flat-footed AC, are read from /api/sheet (the Sheet tab's own source)
// after each state is drawn, and fill in when it answers; a failure leaves the sides as
// the state alone draws them, which is still true, only shorter.

let SIDES_SHEET = null;
let SIDES_FOR = "";
let SIDES_TIMER = 0;

const sidesUp = t => { t = String(t || ""); return t ? t[0].toUpperCase() + t.slice(1) : t; };

// The In hand and worn rows: [where, what, icon shelf]. The icon is the trade window's
// own art for a thing of that kind (06 `tradeIcon`), so a rapier looks the same here and
// at the counter.
function sidesLoadout(pc, sheet) {
  const rows = [["In hand", pc.weapon || "nothing", "weapons"]];
  const eq = sheet && sheet.equipment;
  if (eq && eq.armour && eq.armour.ac) rows.push(["Armour", eq.armour.name, "armour"]);
  if (eq && eq.shield && eq.shield.ac) rows.push(["Shield", eq.shield.name, "armour"]);
  for (const w of pc.worn || []) rows.push(["Worn", w, "magic"]);
  return rows;
}

function sidesTile(name, shelf) {
  if (typeof tradeIcon !== "function" || typeof tradeGlyph !== "function") {
    return `<span class="tile inuse" aria-hidden="true"></span>`;
  }
  return `<span class="tile inuse" aria-hidden="true">${tradeGlyph(tradeIcon({ shelf, name }))}</span>`;
}

function renderSides(s) {
  const pc = s && s.pc;
  const who = document.getElementById("side-who");
  if (!who) return;
  if (!pc) {
    $("#pc-name").textContent = "Nobody is being played";
    $("#pc-line").textContent = "";
    $("#loadout").innerHTML = "";
    return;
  }
  const sheet = SIDES_FOR === pc.name ? SIDES_SHEET : null;

  // Who.
  $("#pc-name").textContent = pc.name;
  $("#pc-line").textContent = [pc.class,
    `${pc.race || ""}${pc.heritage ? ` of the ${pc.heritage}` : ""}`].filter(Boolean).join(", ");
  // What the character is suffering, in the engine's own names: the downed read here as
  // plainly as a poisoning. The page states them and interprets none of them.
  const conds = (pc.conditions || []).map(c => c.name).filter(Boolean);
  const state = $("#pc-state");
  state.hidden = !conds.length;
  state.textContent = conds.length ? sidesUp(conds.join(", ")) : "";

  $("#loadout").innerHTML = sidesLoadout(pc, sheet).map(([where, what, shelf]) => `<li>
      ${sidesTile(what, shelf)}
      <span><span class="where">${esc(where)}</span><span class="what">${esc(what)}</span></span>
    </li>`).join("");
  const purse = $("#purse");
  const coins = (typeof purseTotal === "function" && purseTotal(pc.purse))
    ? purseLine(pc.purse, s.coinage) : "";
  purse.innerHTML = `<b>Purse</b>${esc(coins || "empty")}`;
  const carried = (pc.carrying || []).length + (pc.stock || []).length
    + ((sheet && sheet.equipment && sheet.equipment.weapons) || []).length;
  $("#open-equipment").innerHTML = `Equipment <small>${carried} ${
    carried === 1 ? "thing" : "things"} carried</small>`;
  $("#open-equipment").setAttribute("aria-label", `Open equipment, ${carried} ${
    carried === 1 ? "thing" : "things"} carried`);
  if (typeof paintTradeIcons === "function") paintTradeIcons(who);

  // Life. Temporary hit points scale against hp_max, so 6 temp on a 9 hp character reads
  // as two thirds of a bar again, which is what they are worth. Non-lethal is shown
  // against its own threshold rather than against hp_max: for a Blood Bender the two are
  // rarely close, because the class buys its abilities with non-lethal damage.
  const temp = pc.temp_hp || 0;
  const pct = Math.max(0, Math.min(100, Math.round(100 * pc.hp / pc.hp_max)));
  const tpct = Math.max(0, Math.min(100 - pct, Math.round(100 * temp / pc.hp_max)));
  const nl = pc.nonlethal || 0;
  const nlLimit = pc.nonlethal_threshold ?? pc.hp;
  $("#life").innerHTML = `
    <div class="lifebar" aria-hidden="true"><i style="width:${pct}%"></i>${
      temp ? `<i class="temp" style="width:${tpct}%"></i>` : ""}</div>
    <p class="lifesay"><b>${pc.hp}</b> of ${pc.hp_max} hit points${
      temp ? ` <small>and ${temp} temporary</small>` : ""}</p>
    ${nl ? `<div class="row${nl >= nlLimit ? " danger" : ""}"><span>Non-lethal</span>
      <span>${nl} <small>of ${nlLimit}</small></span></div>` : ""}
    ${(pc.needs || []).length ? `<h4>The body</h4>${pc.needs.map(n => `
      <div class="row${n.danger ? " danger" : ""}" title="${esc(n.detail)}">
        <span>${esc(n.label)}</span><span>${esc(n.state)}</span></div>`).join("")}` : ""}`;

  // Six struck coins, a score raised off each, the modifier on the plaque across its
  // foot; a score that has been damaged or drained says by how much.
  const hurt = pc.ability_damage || {};
  $("#medals").innerHTML = Object.entries(pc.abilities || {}).map(([k, v]) => {
    const mod = Math.floor((v - 10) / 2), down = hurt[k] || 0;
    return `<li class="v2-coin${down ? " hurt" : ""}"><span class="vh">${sidesUp(k)} ${v}, modifier ${
        sign(mod)}${down ? `, ${down} lost` : ""}</span>
      <div aria-hidden="true"><span class="ab">${esc(sidesUp(k))}</span><span class="sc">${v}</span></div>
      <span class="md${down ? " hurt" : ""}" aria-hidden="true">${sign(mod)}${down ? ` (-${down})` : ""}</span></li>`;
  }).join("");

  const plaque = (dt, dd, small = "") => `<div class="v2-plaque"><dt>${dt}</dt><dd>${dd}${
    small ? `<small>${small}</small>` : ""}</dd></div>`;
  const d = sheet && sheet.defense;
  $("#defence").innerHTML = plaque("AC", pc.ac, d
      ? `touch ${d.ac_touch.total}, flat ${d.ac_flat_footed.total}` : "")
    + (pc.speed ? plaque("Speed", `${pc.speed} ft`) : "");
  $("#defence-more").innerHTML = `${(pc.dr && pc.dr.length)
      ? `<div class="row"><span>Damage reduction</span><span>${pc.dr.map(esc).join(", ")}</span></div>` : ""}${
    (pc.pools || []).map(p => `<div class="row"><span>${esc(title(p.id))}</span>
      <span>${p.current} <small>of ${p.max}</small>${
        p.ready ? "" : ` <small>${p.cooldown_left}r</small>`}</span></div>`).join("")}${
    d ? "" : `<p class="note">Touch and flat-footed are on the Sheet's Defense page.</p>`}`;
  const saves = pc.saves || {};
  $("#saves").innerHTML = plaque("Fort", sign(saves.fort || 0)) + plaque("Ref", sign(saves.ref || 0))
    + plaque("Will", sign(saves.will || 0));

  // Experience, and the world's own classes under it.
  const xp = pc.xp;
  $("#xp").innerHTML = `${xp ? `<p>${xp.have.toLocaleString()} <small>of ${
      xp.next.toLocaleString()} for the next level</small></p>${
      xp.ready ? `<p class="ready">Ready to level: sleep to take it.</p>` : ""}` : ""}${
    (pc.world_classes && pc.world_classes.length) ? `<h4>World classes</h4>${
      pc.world_classes.map(w => `<div class="row"><span>${esc(w.name)} ${w.level}</span><span>${
        w.missing ? "<small>unknown track</small>"
        : w.to_next ? `<small>${w.to_next.need} to next</small>` : "<small>mastered</small>"}</span></div>
        ${w.missing ? "" : `<p class="note">${esc(w.max_tier)}, ${w.known} recipe${
          w.known === 1 ? "" : "s"}</p>`}`).join("")}` : ""}`;

  // The phone's glance, in the book's head: life and AC, and the way to the whole sheet.
  const glance = $("#glance");
  if (glance) {
    glance.textContent = `Life ${pc.hp} of ${pc.hp_max}, AC ${pc.ac}`;
    glance.setAttribute("aria-label", `Life ${pc.hp} of ${pc.hp_max}, armour class ${pc.ac}. Open the sheet`);
  }
}

// The sheet's own numbers for what the state does not carry, read after each draw.
async function sidesReadSheet(name) {
  try {
    const r = await fetch("/api/sheet", { cache: "no-store" });
    if (!r.ok) return;
    const sheet = await readJSON(r);
    if (!sheet || !sheet.identity || !STATE || !STATE.pc) return;
    SIDES_SHEET = sheet;
    SIDES_FOR = name;
    renderSides(STATE);
  } catch { /* the sides keep what the state alone draws */ }
}

onRender(function sides(s) {
  renderSides(s);
  // One read per burst of draws: a turn can draw twice in a breath (a held die, then the
  // page), and the sheet is the same after both.
  clearTimeout(SIDES_TIMER);
  if (s && s.pc) SIDES_TIMER = setTimeout(() => sidesReadSheet(s.pc.name), 200);
});

document.addEventListener("click", e => {
  if (e.target.closest("#openroster")) openRoster();
});
