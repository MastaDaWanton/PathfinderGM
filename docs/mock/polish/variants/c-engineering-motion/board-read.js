/* c-engineering-motion: reading the board, and inspecting it by pointer or keyboard.
 *
 * One model is built from the payload (`STATE.scene` plus `POLISH_SCENE.extras/.light`)
 * and both views draw the same lists from it, so flat and 3D cannot disagree about what a
 * square means. It adds no facts: every line below names the field it reads. What the game
 * hides stays hidden: no target AC, no needed roll, no square for a hunch.
 *
 * Inspecting is one state, `UI.cur`, shared by hover and the keyboard. Into the Breach's
 * rule is the model: what happens next is shown on the board before you commit, and the
 * thing that would hit you is the thing that lights up (Justin Ma, Game Developer
 * interview: "sacrifice cool ideas for the sake of clarity every time").
 */
const BoardRead = (function () {
  "use strict";
  const CELL = 18;
  const key = (c, r) => c + "," + r;
  const sign = v => (v < 0 ? "-" : "+") + Math.abs(v);
  const cap = t => t ? t[0].toUpperCase() + t.slice(1) : "";
  const and = xs => xs.length < 2 ? (xs[0] || "")
    : xs.slice(0, -1).join(", ") + " and " + xs[xs.length - 1];

  // PF1 distance: diagonals alternate 5 and 10 ft (Core Rulebook, Moving diagonally).
  function feet(a, b) {
    const dx = Math.abs(a[0] - b[0]), dy = Math.abs(a[1] - b[1]);
    const d = Math.min(dx, dy), s = Math.max(dx, dy) - d;
    return (s + d + Math.floor(d / 2)) * 5;
  }

  /* The room lamp from the hour. Colour from the phase (sky.phase_at), strength from the
     ambient level (Scene.ambient_light). Both tints are the theme's own: --ember for the
     low sun, --player for night. A multiply colour: white changes nothing. Kept gentle on
     purpose (the brief: subtle, readable at night); the people are spared most of it. */
  const EMBER = [255, 176, 84], PLAYER = [143, 176, 200];
  function lamp(light) {
    if (!light) return null;
    const phase = (light.phase && light.phase.phase) || "";
    const strength = { bright: 1, normal: 1, dim: 0.76, dark: 0.62, darkness: 0.62 }[light.ambient] || 1;
    const tint = /dawn|dusk|sunrise|sunset/.test(phase) ? EMBER
      : /night|evening|midnight/.test(phase) ? PLAYER : null;
    const k = tint ? 0.42 : 0;
    const mul = [0, 1, 2].map(i =>
      Math.round((255 + ((tint ? tint[i] : 255) - 255) * k) * strength));
    const when = /morning|afternoon|evening/.test(phase) ? "in the " + phase
      : phase ? "at " + phase : "";
    return { mul, css: `rgb(${mul.join(",")})`,
             text: `${cap(light.ambient || "")} light ${when}`.trim() };
  }

  // The outline of a set of squares: each side of a member whose neighbour is not one.
  function outline(set) {
    const out = [];
    for (const k of set) {
      const [c, r] = k.split(",").map(Number);
      if (!set.has(key(c, r - 1))) out.push({ c, r, side: "n" });
      if (!set.has(key(c, r + 1))) out.push({ c, r, side: "s" });
      if (!set.has(key(c - 1, r))) out.push({ c, r, side: "w" });
      if (!set.has(key(c + 1, r))) out.push({ c, r, side: "e" });
    }
    return out;
  }

  function model(s) {
    const sc = window.POLISH_SCENE || {}, x = sc.extras || {}, g = s.scene.grid;
    const actors = (s.scene.actors || []).filter(a => a.at);
    const byRef = new Map(actors.map(a => [a.ref, a]));
    const pc = actors.find(a => a.is_pc);
    const blind = new Set(((x.sight || {}).squares || []).filter(q => !q[2]).map(q => key(q[0], q[1])));
    const threat = new Map(), zones = {};
    for (const [ref, cells] of Object.entries((x.threatened || {}).by_foe || {})) {
      zones[ref] = cells.map(([c, r]) => key(c, r));
      for (const k of zones[ref]) (threat.get(k) || threat.set(k, []).get(k)).push(ref);
    }
    const reach = new Map((g.reachable || []).map(e => [key(e[0], e[1]), e[2]]));
    const provokes = (x.provokes && x.provokes.squares) || {};
    // A reachable square the move op would not be provoked on (reactions.provoked_by_move).
    const safe = new Set([...reach.keys()].filter(k => !(provokes[k] || []).length));
    const hunches = (x.awareness && x.awareness.hunches) || [];
    const hunchFt = Math.max(0, ...hunches.map(h => h.within_ft || 0));
    const near = new Set();
    if (pc && hunchFt)
      for (let c = 0; c < g.width; c++) for (let r = 0; r < g.height; r++)
        if (feet(pc.at, [c, r]) <= hunchFt) near.add(key(c, r));
    // Who the spell catches, only when the area on the board is that very area.
    const sa = x.spell_area, areas = g.areas || [];
    const laid = sa && areas.some(a => a.spell === sa.spell &&
                                  JSON.stringify(a.cells) === JSON.stringify(sa.cells));
    const spellCells = new Set();
    for (const a of areas) for (const cl of (a.cells || [])) spellCells.add(key(cl[0], cl[1]));
    return {
      g, x, actors, byRef, pc, blind, threat, zones, reach, provokes, safe, hunches,
      hunchFt, near, spellCells, spellName: areas.length ? String(areas[0].spell || "a spell").replace(/-/g, " ") : "",
      caught: new Set(laid ? (sa.caught || []) : []), cover: (x.sight || {}).cover || {},
      atk: (x.attack_preview || {}).by_foe || {}, active: s.scene.turn_ref,
      heights: new Map((g.floor || []).map(f => [key(f[0], f[1]), f[2]])),
      blocked: new Set((g.blocked || []).map(b => key(b[0], b[1]))),
      difficult: new Set((g.difficult || []).map(b => key(b[0], b[1]))),
      lamp: lamp(sc.light),
    };
  }

  /* What both views draw from the model. Marks lie on a square; strips are one side of
     one. Zone and ring marks are drawn hidden and only switched on (class `on`) while the
     thing they explain is being inspected, so the board at rest stays quiet: Into the
     Breach's early builds drew every indicator at once and testers "couldn't tell who was
     attacking what". */
  function readings(m) {
    const marks = [], strips = [];
    for (const k of m.blind) { const [c, r] = k.split(",").map(Number); marks.push({ c, r, kind: "fog" }); }
    for (const [ref, ks] of Object.entries(m.zones))
      for (const k of ks) { const [c, r] = k.split(",").map(Number); marks.push({ c, r, kind: "zone", ref }); }
    for (const s of outline(new Set(m.threat.keys()))) strips.push({ ...s, kind: "threat" });
    if (m.spellCells.size) for (const s of outline(m.spellCells)) strips.push({ ...s, kind: "spell" });
    if (m.near.size) for (const s of outline(m.near)) strips.push({ ...s, kind: "hunch" });
    for (const a of m.actors) {
      const [c, r] = a.at;
      if (a.stance === "foe") marks.push({ c, r, kind: "ring", ref: a.ref, n: a.squares || 1 });
      if (m.caught.has(a.ref)) marks.push({ c, r, kind: "caught", n: a.squares || 1 });
      if (m.active === a.ref) marks.push({ c, r, kind: "active", n: a.squares || 1 });
    }
    return { marks, strips };
  }

  function covers(a, c, r) {
    const n = a.squares || 1;
    return c >= a.at[0] && c < a.at[0] + n && r >= a.at[1] && r < a.at[1] + n;
  }
  const nameOf = (m, ref) => (m.byRef.get(ref) || {}).name || "someone";

  // The inspector's words for one square. Returns html for the card, plain text for the
  // live region, and which foes to light (their threat zone, or a ring as provoker).
  function describe(m, c, r) {
    const k = key(c, r), rows = [], zones = [], rings = [];
    let head = "";
    const who = m.actors.find(a => covers(a, c, r));
    if (who) {
      const side = who.is_pc ? "You" : { foe: "Foe", ally: "Ally" }[who.stance] || "Bystander";
      head = `${esc(who.name)} <span class="cardside">${side}</span>`;
      if (m.active === who.ref) rows.push(["turn", who.is_pc ? "Your turn" : "Their turn"]);
      rows.push(["", `${who.hp} of ${who.hp_max} hit points${who.hp <= 0 ? ", down" : ""}`]);
      const up = who.at.length > 2 ? who.at[2] : 0;
      if (up) rows.push(["", `${up * 5} ft above the floor`]);
      // The PC's own itemised bonus and the situational terms; never the target's AC.
      // Weapons that come to the same bonus from the same terms share one line ("Rapier
      // or dagger +5"): the card is read in passing, and two identical blocks hide the board.
      const same = new Map();
      for (const w of (m.atk[who.ref] || [])) {
        const sig = JSON.stringify([w.bonus, w.terms, w.in_reach]);
        if (same.has(sig)) same.get(sig).name += " or " + w.name;
        else same.set(sig, { ...w });
      }
      for (const w of same.values()) {
        const sit = new Set((w.situational || []).map(t => t[0]));
        const terms = (w.terms || []).map(([n, v]) =>
          `<span class="${sit.has(n) ? "sit" : ""}">${esc(n)} ${sign(v)}</span>`).join(", ");
        rows.push(["atk", `<b>${esc(cap(w.name))} ${sign(w.bonus)}</b>${w.in_reach
          ? "" : ' <span class="cardoff">out of reach</span>'}<br><span class="terms">${terms}</span>`,
          `${cap(w.name)} ${sign(w.bonus)}${w.in_reach ? "" : ", out of reach"}: ${
            (w.terms || []).map(([n, v]) => `${n} ${sign(v)}`).join(", ")}`]);
      }
      const cv = m.cover[who.ref];
      if (cv && cv !== "none")
        rows.push(["", { cover: "Has cover from you", soft: "Has soft cover from you",
                         total: "Has total cover from you" }[cv] || cap(cv)]);
      if (m.caught.has(who.ref)) rows.push(["spell", `Caught in the ${esc(m.spellName)}`]);
      if (m.zones[who.ref]) zones.push(who.ref);
    } else {
      const h = m.heights.get(k) || 0;
      head = m.blocked.has(k) ? "Blocked" : h ? `Raised ground` : m.difficult.has(k) ? "Difficult ground" : "Open ground";
      if (h) rows.push(["", `${h * 5} ft above the floor`]);
      if (m.reach.has(k)) {
        const cost = m.reach.get(k), by = m.provokes[k] || [];
        rows.push(["", cost === 5 ? "A 5 ft step" : `Moving here costs ${cost} ft`]);
        if (by.length) {
          rows.push(["warn", `Provokes attacks of opportunity from ${esc(and(by.map(f => nameOf(m, f))))}`]);
          rings.push(...by);
        } else rows.push(["ok", "Does not provoke"]);
      } else if (m.pc && !m.blocked.has(k) && !covers(m.pc, c, r)) {
        rows.push(["", `${feet(m.pc.at, [c, r])} ft away, out of reach this turn`]);
      }
      const t = m.threat.get(k);
      if (t && !m.reach.has(k)) rows.push(["warn", `Threatened by ${esc(and(t.map(f => nameOf(m, f))))}`]);
    }
    if (m.blind.has(k)) rows.push(["", "Out of your line of sight"]);
    if (!who && m.spellCells.has(k)) rows.push(["spell", `Inside the ${esc(m.spellName)}`]);
    const html = `<p class="cardhead">${head}</p>` +
      rows.map(([cls, h]) => `<p class="cardrow ${cls}">${h}</p>`).join("");
    const text = [head.replace(/<[^>]+>/g, " ")]
      .concat(rows.map(r => (r[2] || r[1]).replace(/<[^>]+>/g, ""))).join(". ");
    return { html, text, zones, rings };
  }

  /* --- inspecting ------------------------------------------------------------------- */
  const UI = { cur: null, kb: false, m: null, hold: false };
  const surface = () => document.querySelector("#mapwrap #map, #mapwrap #view3d");

  function after(m) { UI.m = m; show(); }

  function setCur(c, r, kb) {
    const g = UI.m && UI.m.g;
    if (!g) return;
    c = Math.max(0, Math.min(g.width - 1, c)); r = Math.max(0, Math.min(g.height - 1, r));
    if (UI.cur && UI.cur[0] === c && UI.cur[1] === r && UI.kb === kb) return;
    UI.cur = [c, r]; UI.kb = kb; show();
  }
  function clear() { UI.cur = null; show(); }

  function show() {
    const m = UI.m, svg = surface();
    if (!m || !svg) return;
    const view = svg.closest(".boardview"), card = view && view.querySelector(".boardcard");
    svg.querySelectorAll(".on").forEach(e => e.classList.remove("on"));
    svg.querySelectorAll(".cur").forEach(e => e.classList.remove("cur"));
    const flat = svg.querySelector("#boardcursor");
    if (!UI.cur || UI.hold) {
      if (card) card.classList.remove("on");
      if (flat) flat.setAttribute("visibility", "hidden");
      return;
    }
    const [c, r] = UI.cur, k = key(c, r);
    let anchor;
    if (flat) {
      flat.setAttribute("x", c * CELL); flat.setAttribute("y", r * CELL);
      flat.setAttribute("visibility", "visible");
      anchor = flat;
    } else {
      const tops = svg.querySelectorAll(`[data-cell="${k}"].face-top`);
      tops.forEach(f => f.classList.add("cur"));
      anchor = tops[tops.length - 1];
    }
    const d = describe(m, c, r);
    // Cause and effect land together: the square is the lead, and the foes it concerns
    // light in the same frame on one 120 ms fade, so the pair reads as one statement.
    for (const ref of d.zones) svg.querySelectorAll(`[data-zone="${ref}"]`).forEach(e => e.classList.add("on"));
    for (const ref of d.rings) svg.querySelectorAll(`[data-ring="${ref}"]`).forEach(e => e.classList.add("on"));
    if (!card) return;
    card.innerHTML = d.html;
    card.classList.add("on");
    place(card, anchor, view);
    if (UI.kb) { const say = document.getElementById("boardsay"); if (say) say.textContent = d.text; }
  }

  // Beside the square, flipped or dropped below when it would leave the well. Moved by
  // transform with no transition: a card that slid after the pointer would lag it.
  function place(card, anchor, view) {
    if (!anchor) return;
    // Screen rects divided back into the well's own pixels, in case anything above scales it.
    const k = view.getBoundingClientRect().width / (view.offsetWidth || 1) || 1;
    const r = anchor.getBoundingClientRect(), o = view.getBoundingClientRect();
    const a = { left: (r.left - o.left) / k, right: (r.right - o.left) / k,
                top: (r.top - o.top) / k, bottom: (r.bottom - o.top) / k };
    const v = { left: 0, top: 0, width: view.offsetWidth, height: view.offsetHeight };
    const cw = card.offsetWidth, ch = card.offsetHeight, gap = 8;
    let x = a.right - v.left + gap, y = a.top - v.top - 4;
    if (x + cw > v.width - 4) x = a.left - v.left - gap - cw;
    if (x < 4) { x = Math.max(4, Math.min(v.width - cw - 4, a.left - v.left)); y = a.bottom - v.top + gap; }
    if (y + ch > v.height - 4) y = Math.max(4, a.top - v.top - gap - ch);
    card.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
  }

  /* --- pointer and keys --------------------------------------------------------------- */
  document.addEventListener("pointermove", e => {
    const svg = e.target.closest && e.target.closest("#mapwrap #map, #mapwrap #view3d");
    if (!svg || !UI.m) return;
    if (svg.id === "map") {
      const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(svg.getScreenCTM().inverse());
      const c = Math.floor(p.x / CELL), r = Math.floor(p.y / CELL);
      if (c >= 0 && r >= 0 && c < UI.m.g.width && r < UI.m.g.height) setCur(c, r, false);
      else if (!UI.kb) clear();
    } else {
      const t = e.target.closest("[data-cell]");
      if (t) { const [c, r] = t.dataset.cell.split(",").map(Number); setCur(c, r, false); }
    }
  });
  document.addEventListener("pointerout", e => {
    const from = e.target.closest && e.target.closest("#mapwrap .boardview");
    if (!from || from.contains(e.relatedTarget)) return;
    if (document.activeElement !== surface()) clear();
  });
  document.addEventListener("focusin", e => {
    if (e.target !== surface() || UI.cur || !UI.m || !UI.m.pc) return;
    setCur(UI.m.pc.at[0], UI.m.pc.at[1], true);
  });
  document.addEventListener("focusout", e => { if (e.target === surface()) clear(); });

  const ARROWS = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };
  document.addEventListener("keydown", e => {
    const svg = surface();
    if (e.target !== svg || !UI.m) return;
    const cur = UI.cur || (UI.m.pc ? UI.m.pc.at : [0, 0]);
    if (ARROWS[e.key]) {
      e.preventDefault();
      let [dx, dy] = ARROWS[e.key];
      // In 3D an arrow means the way it points on screen, whichever way the board is turned.
      if (svg.id === "view3d") [dx, dy] = Scene3D.stepFor(dx, dy, typeof MAP_TURN === "number" ? MAP_TURN : 0);
      setCur(cur[0] + dx, cur[1] + dy, true);
    } else if (e.key === "Home" && UI.m.pc) {
      e.preventDefault(); setCur(UI.m.pc.at[0], UI.m.pc.at[1], true);
    } else if (e.key === "Escape") {
      clear();
    } else if ((e.key === "Enter" || e.key === " ") && UI.cur) {
      // The same click the pointer makes on a lit square, so the combat builder cannot
      // tell a key from a click. Nothing else on the board is a destination.
      e.preventDefault();
      const [c, r] = UI.cur;
      const t = svg.querySelector(`[data-sq="${c},${r}"], [data-sq^="${c},${r},"]`);
      if (t) t.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    }
  });

  function hold(on) { UI.hold = on; show(); }

  return { CELL, key, model, readings, after, hold, describe };
})();
