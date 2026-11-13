/* The board's readout (2026-11-13): the strip under the ground board that answers whatever
 * is tapped, pointed at or tabbed to. Ported from the polish mocks' variant D
 * (docs/mock/polish/variants/d-phone-worst-case/polish.js and map.js on mock/polish), the
 * one the owner chose: "add all the things that D has".
 *
 *   - a foe: your own attack total first, then the weapon, then each term, the
 *     situational ones (flanking, higher ground, into melee, range) in gold, and "out of
 *     reach" or "behind cover" in words. NEVER the foe's AC or the roll it needs: the AC
 *     is hidden in the game (an attack roll shows no dc);
 *   - a square: what the move there costs, and "Provokes an attack from X and Y" or "No
 *     attack of opportunity", with a dashed ring on the foes who would swing (Into the
 *     Breach's fix, after outside testers could not tell who was attacking what);
 *   - nothing: whose turn it is, who the latest spell caught, and a hunch as a range.
 *
 * Every fact is the server's (`scene.grid.tactics`, views._tactics, and `grid.areas`):
 * nothing here decides who threatens, who provokes or what a bonus is. A phone has no
 * hover, so nothing is hover-only; a pointer that can hover previews as it passes.
 *
 * Tap to move: a tap on a lit square in a fight both shows its readout and queues the move
 * in the combat bar (04-combat-and-turns.js), as a click always has. The queue is not the
 * move: the bar's own Go is the confirmation, so a second tap is never needed.
 */
const MAPREAD = { sel: null, hover: null, s: null, T: {}, keyOpen: false };

function mapReadout(s, T) {
  MAPREAD.s = s;
  MAPREAD.T = T || {};
  // A selection that is no longer on this board (they left, or went out of sight) is
  // dropped rather than shown as somebody who is not there.
  if (MAPREAD.sel && MAPREAD.sel.ref && !mapActor(MAPREAD.sel.ref)) MAPREAD.sel = null;
  MAPREAD.hover = null;
  mapReadPaint();
}

const mapActor = ref => ((MAPREAD.s && MAPREAD.s.scene.actors) || []).find(a => a.ref === ref && a.at);
const mapSigned = n => (n < 0 ? "−" + Math.abs(n) : "+" + n);
const mapCap = t => String(t).charAt(0).toUpperCase() + String(t).slice(1);
// In running text a name stops at its first comma ("Ünsal the Twice-Drowned, Reeve of the
// Saltmarsh Ossuaries" made a five-name list four lines long); two of one name are told
// apart by their plates (views._marks): "goblin (G1) and goblin (G2)".
function mapName(ref) {
  const a = mapActor(ref);
  if (!a) return "someone";
  const n = String(a.name).split(",")[0].trim();
  const twin = MAPREAD.s.scene.actors.some(b => b !== a && String(b.name).split(",")[0].trim() === n);
  return twin && a.mark ? `${n} (${a.mark})` : n;
}
function mapList(names) {
  return names.length < 2 ? names.join("") : names.slice(0, -1).join(", ") + " and " + names[names.length - 1];
}
const MAP_LIGHT = { bright: "Bright light", normal: "Normal light", dim: "Dim light", dark: "Darkness" };

function mapIdle() {
  const sc = MAPREAD.s.scene, g = sc.grid, T = MAPREAD.T;
  const turnA = sc.in_encounter && sc.turn_ref && mapActor(sc.turn_ref);
  const nm = turnA && String(turnA.name).split(",")[0].trim();
  const who = turnA ? (turnA.is_pc ? "Your turn" : `${nm}${/s$/i.test(nm) ? "'" : "'s"} turn`) : "The ground";
  const light = g.light && MAP_LIGHT[g.light.level];
  const lines = [];
  const areas = (g.areas || []).filter(a => (a.cells || []).length);
  for (const a of areas) {
    const spell = mapCap(String(a.spell || "the spell").replace(/-/g, " "));
    const names = (a.caught || []).map(mapName);
    lines.push(`<span class="mr-spell">${esc(spell)}</span> ${names.length
      ? `caught ${esc(mapList(names))}.` : "caught nobody you can see."}`);
  }
  for (const h of (T.hunches || []))
    lines.push(`<span class="mr-hunch">You sense ${h.count === 1 ? "a foe" : h.count + " foes"} within ${
      h.within_ft} ft</span>, but not where.`);
  const hint = sc.in_encounter ? "Tap or point at a foe for your attack, or a lit square for the move."
    : "Tap or point at somebody, or a square.";
  return `<p class="mr-h mr-one"><span>${esc(who)}</span>${light
    ? `<span class="mr-dim">${esc(light)}</span>` : ""}</p><p>${lines.join(" ")} <span class="mr-dim">${hint}</span></p>`;
}

function mapForActor(a) {
  const T = MAPREAD.T;
  const where = a.at.length > 2 && a.at[2] ? `, ${a.at[2] * 5} ft up` : "";
  // Cover is something the player can see (the wall is on the board); its number goes to
  // the hidden AC and is never shown.
  const cover = (T.cover || {})[a.ref];
  const cv = cover ? `, ${cover === "total" ? "total cover" : cover === "soft" ? "soft cover" : "behind cover"}` : "";
  const caught = (MAPREAD.s.scene.grid.areas || []).some(x => (x.caught || []).includes(a.ref));
  // One line: the name gives way (ellipsis, whole on the token's own label), the numbers
  // never do. A two-line name on a phone pushed the attack bonus below the box's fold.
  const out = [`<p class="mr-h mr-one mr-who"><span class="mr-name" title="${esc(a.name)}">${esc(a.name)}</span><span class="mr-dim">${
    a.hp}/${a.hp_max}${where}${a.hp <= 0 ? ", down" : ""}${cv}</span>${caught ? `<span class="mr-spell">caught</span>` : ""}</p>`];
  const rows = (T.attack || {})[a.ref] || [];
  // Weapons that come to the same bonus by the same terms are one line ("Rapier or dagger
  // +5"): the box has two lines on a phone, and a repeat spends one.
  const groups = new Map();
  for (const w of rows) {
    const k = JSON.stringify([w.bonus, w.terms, w.in_reach]);
    if (!groups.has(k)) groups.set(k, { w, names: [] });
    groups.get(k).names.push(w.name || w.weapon);
  }
  for (const { w, names } of groups.values()) {
    const terms = (w.terms || []).map(([t, v]) => {
      const sit = (w.situational || []).some(([u]) => u === t);
      return `<span class="mr-term${sit ? " sit" : ""}">${esc(mapCap(t))}&nbsp;${mapSigned(v)}</span>`;
    }).join(" ");
    // The total first, then what it is with, then why: the number is what a player compares.
    out.push(`<p class="mr-atk"><b class="mr-bonus">${mapSigned(w.bonus)}</b> <span class="mr-wpn">${
      esc(mapCap(names.join(" or ")))}</span>${w.in_reach ? "" : ` <span class="mr-warn">out of reach</span>`}${
      cover === "total" ? ` <span class="mr-warn">behind total cover</span>` : ""} ${terms}</p>`);
  }
  return out.join("");
}

function mapForSquare(sq) {
  const g = MAPREAD.s.scene.grid, T = MAPREAD.T, k = `${sq[0]},${sq[1]}`;
  const e = (g.reachable || []).find(p => p[0] === sq[0] && p[1] === sq[1]);
  const name = typeof sqName === "function" ? sqName(sq[0], sq[1]) + ": " : "";
  const out = [`<p class="mr-h">${name}${e ? `${e[2]} ft to here` : "out of your move"}${
    e && e[3] ? `<span class="mr-dim">${e[3] * 5} ft up</span>` : ""}</p>`];
  const bits = [];
  if ((T.unseen || []).some(p => p[0] === sq[0] && p[1] === sq[1])) bits.push(`<span class="mr-dim">You cannot see this square.</span>`);
  const pr = (T.provokes || {})[k];
  if (e && T.provokes) bits.push(pr && pr.length
    ? `<span class="mr-warn">Provokes</span> an attack from ${esc(mapList(pr.map(mapName)))}.`
    : "No attack of opportunity.");
  const th = (T.threat || {})[k];
  if (th && th.length) bits.push(`<span class="mr-dim">Threatened there by ${esc(mapList(th.map(mapName)))}.</span>`);
  if (bits.length) out.push(`<p>${bits.join(" ")}</p>`);
  return out.join("");
}

// Both views write data-ref on every part of a body and data-sq on every square that can
// be moved to, so one function lights both. It changes classes and one text box: nothing
// is redrawn, nothing moves, nothing under the pointer shifts.
function mapTarget(el) {
  const t = el && el.closest && el.closest("[data-ref], [data-sq]");
  const wrap = document.getElementById("mapwrap");
  if (!t || !wrap || !wrap.contains(t)) return null;
  if (t.dataset.ref) return { ref: t.dataset.ref };
  return { sq: t.dataset.sq.split(",").map(Number) };
}
function mapReadPaint() {
  const box = document.getElementById("mapread");
  if (!box || !MAPREAD.s || !MAPREAD.s.scene.grid) return;
  const t = MAPREAD.hover || MAPREAD.sel;
  document.querySelectorAll("#mapwrap .is-sel, #mapwrap .is-warn").forEach(e =>
    e.classList.remove("is-sel", "is-warn"));
  if (t && t.ref && mapActor(t.ref)) {
    document.querySelectorAll(`#mapwrap [data-ref="${CSS.escape(t.ref)}"]`).forEach(e => e.classList.add("is-sel"));
    box.innerHTML = mapForActor(mapActor(t.ref));
    return;
  }
  if (t && t.sq) {
    const k = `${t.sq[0]},${t.sq[1]}`;
    document.querySelectorAll(`#mapwrap [data-sq^="${k}"]`).forEach(e => {
      if (e.dataset.sq.split(",").slice(0, 2).join(",") === k) e.classList.add("is-sel");
    });
    // Ring who would take the swing: the attacker made plain.
    for (const ref of ((MAPREAD.T.provokes || {})[k] || []))
      document.querySelectorAll(`#mapwrap [data-ref="${CSS.escape(ref)}"]`).forEach(e => e.classList.add("is-warn"));
    box.innerHTML = mapForSquare(t.sq);
    return;
  }
  box.innerHTML = mapIdle();
}

(function () {
  const fine = matchMedia("(hover: hover) and (pointer: fine)");
  const same = (a, b) => !!(a && b && (a.ref ? a.ref === b.ref
    : !b.ref && a.sq[0] === b.sq[0] && a.sq[1] === b.sq[1]));
  const onBoard = e => e.target.closest && e.target.closest("#mapwrap .boardview");
  document.addEventListener("pointerover", e => {
    if (!fine.matches || e.pointerType === "touch" || !onBoard(e)) return;
    const t = mapTarget(e.target);
    if (same(t, MAPREAD.hover) || (!t && !MAPREAD.hover)) return;
    MAPREAD.hover = t; mapReadPaint();
  });
  document.addEventListener("pointerout", e => {
    if (!MAPREAD.hover || !onBoard(e)) return;
    const to = e.relatedTarget;
    if (to && to.closest && to.closest("#mapwrap .boardview")) return;
    MAPREAD.hover = null; mapReadPaint();
  });
  document.addEventListener("click", e => {
    if (!onBoard(e)) return;
    const t = mapTarget(e.target);
    // A second tap on the same body lets it go; a tap on bare ground clears. A square stays
    // chosen on a second tap: in a fight that tap queues the same move again (04).
    MAPREAD.sel = t && t.ref && same(t, MAPREAD.sel) ? null : t;
    MAPREAD.hover = null;
    mapReadPaint();
  });
  document.addEventListener("focusin", e => {
    // Keyboard focus only: a tap focuses the token too, and selecting on that focus made
    // the click that follows read as a second tap and let go at once (found in the mock).
    if (!e.target.matches || !e.target.matches(":focus-visible")) return;
    const t = mapTarget(e.target);
    if (t) { MAPREAD.sel = t; mapReadPaint(); }
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && MAPREAD.sel && onBoard(e)) { MAPREAD.sel = null; mapReadPaint(); }
  });
  document.addEventListener("toggle", e => {
    if (e.target.classList && e.target.classList.contains("mapkey")) MAPREAD.keyOpen = e.target.open;
  }, true);
})();
