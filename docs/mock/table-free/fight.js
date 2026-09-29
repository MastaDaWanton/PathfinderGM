// Book and ledger: the fight. It happens on the same page as everything else: the story keeps
// its place, the rail becomes the board, the dock grows the turn's budget, and initiative runs
// across the top. Sunless Sea's post-mortem is why: its separate combat screen "yanked the
// player out of our carefully layered atmosphere", and Failbetter scrapped it.
//
// Real: the grid, walls, rough ground and gallery; everyone's square; initiative; Kesst's and
// Borin's numbers; the opening rolls and tell (tests/replay/2026-09-25-fight-bodies-*). Mock: the
// d20s rolled after that, the reach walk (Dijkstra, diagonals at one and a half), and every word
// in a "Mock." line.
"use strict";

const F = D.fight;
const WEST = "6953424c8a82~urban:the-west-crossing";
const DOOR = [4, 8];                       // where Kesst came in, turn 0 of the recording
const COLS = "ABCDEFGHIJKLMNOP";
const sqName = ([c, r]) => `${COLS[c]}${r + 1}`;
const key = (c, r) => c + "," + r;
const cheb = (a, b) => Math.max(Math.abs(a[0] - b[0]), Math.abs(a[1] - b[1]));
const d20 = () => 1 + Math.floor(Math.random() * 20);
const roll = dice => {
  const m = /^(\d+)d(\d+)$/.exec(dice);
  if (!m) return [0];
  return Array.from({ length: +m[1] }, () => 1 + Math.floor(Math.random() * +m[2]));
};

// --- Starting the recorded fight -------------------------------------------------------------------
function startFight() {
  const people = {};
  Object.entries(F.people).forEach(([ref, p]) => { people[ref] = { ...p }; });
  people.pc.hp = sheet().hp.current;
  people.pc.hp_max = sheet().hp.max;
  people.pc.name = sheet().identity.name;
  S.fight = {
    round: F.round, order: F.initiative.map(x => x.slice()), turn: 1,
    pos: JSON.parse(JSON.stringify(F.positions)), people,
    view: "2d", turn3d: 0, target: "c2", plan: [], used: {}, pending: null,
  };
  S.scene = "fight"; S.place = WEST; S.talk = null; S.attached = null;
  document.body.classList.remove("scene-explore"); document.body.classList.add("scene-fight");
  const rolls = F.rolls.map(r => ({ type: "roll", label: r.label, die: r.die, faces: r.faces,
    natural: r.natural, terms: r.terms, total: r.total }));
  rolls[0].vs = { what: "AC", value: F.dc.value, explain: F.dc.explain };
  rolls[0].verdict = "hit"; rolls[0].good = true;
  const tell = F.tells[0] || "";
  S.beats.push(placeBeat(WEST),
    beat("you", F.struck),
    beat("gm", F.prose[0], [...rolls,
      { title: "Tell", text: tell }, { type: "xp", gain: 65, have: 65, next: 2000 }]),
    beat("gm", F.prose[2], [{ title: "Initiative", text: "Borin Lyraxys 16. Kesst Vayr 9: d20 6, Dex +3." },
      { title: "Borin Lyraxys", text: "Moved from E5 to E4. His turn is over." }]),
    beat("oc", "Mock. From here the fight is live: the board is the recording's own, the rolls from now on are this page's.", []));
  renderStory();
  renderRail(); renderFight(); renderDock();
  requestAnimationFrame(() => {
    const box = $("#beats");
    const last = box.lastElementChild;
    box.scrollTop = last ? last.offsetTop - box.clientHeight + last.offsetHeight + 40 : box.scrollHeight;
  });
}
$("#mock-fight").addEventListener("click", () => {
  $("#pagemenu").open = false; setMode("table");
  if (S.scene !== "fight") startFight();
});

// --- The board ------------------------------------------------------------------------------------
function grid() {
  const g = F.grid;
  const high = new Set(Object.keys(g.floor || {}));
  const blocked = new Set((g.blocked || []).map(p => key(...p)));
  const rough = new Set((g.difficult || []).map(p => key(...p)));
  return { g, high, blocked, rough };
}
const alive = ref => (S.fight.people[ref].hp > 0);
function foes() {
  return Object.keys(S.fight.pos).filter(r => r !== "pc");
}
function threatened() {
  const t = new Map();
  foes().filter(alive).forEach(ref => {
    const [c, r] = S.fight.pos[ref];
    for (let dc = -1; dc <= 1; dc++) for (let dr = -1; dr <= 1; dr++) {
      if (dc || dr) t.set(key(c + dc, r + dr), ref);
    }
  });
  return t;
}
// Where the PC stands once the planned move is made.
const standAt = () => {
  const mv = S.fight.plan.find(p => p.kind === "move" || p.kind === "step");
  return mv ? mv.to : S.fight.pos.pc;
};
// Every square reachable this turn, and the path to it. Speed 30 is six squares; a diagonal
// costs one and a half (the book's 5/10/5 averaged), rough ground doubles, walls, the gallery
// and other bodies stop you.
function reach(from = S.fight.pos.pc, budget = sheet().speed / 5) {
  const { g, high, blocked, rough } = grid();
  const occupied = new Set(Object.entries(S.fight.pos).filter(([r]) => r !== "pc").map(([, p]) => key(...p)));
  const dist = new Map([[key(...from), 0]]), prev = new Map();
  const queue = [[0, from]];
  while (queue.length) {
    queue.sort((a, b) => a[0] - b[0]);
    const [d, [c, r]] = queue.shift();
    if (d > dist.get(key(c, r))) continue;
    for (let dc = -1; dc <= 1; dc++) for (let dr = -1; dr <= 1; dr++) {
      if (!dc && !dr) continue;
      const nc = c + dc, nr = r + dr, k = key(nc, nr);
      if (nc < 0 || nr < 0 || nc >= g.width || nr >= g.height) continue;
      if (blocked.has(k) || high.has(k) || occupied.has(k)) continue;
      const step = (dc && dr ? 1.5 : 1) * (rough.has(k) ? 2 : 1);
      const nd = d + step;
      if (nd > budget + 1e-9) continue;
      if (!dist.has(k) || nd < dist.get(k)) {
        dist.set(k, nd); prev.set(k, key(c, r)); queue.push([nd, [nc, nr]]);
      }
    }
  }
  const path = to => {
    const out = []; let k = key(...to);
    while (k && k !== key(...from)) { out.unshift(k.split(",").map(Number)); k = prev.get(k); }
    return out;
  };
  return { dist, path };
}
// Who strikes as you go: every foe whose reach covers a square you LEAVE along the way. The
// first square is spared on a withdraw.
function provokers(path, from, withdraw = false) {
  const t = threatened(), hits = new Map();
  const squares = [from, ...path.slice(0, -1)];
  squares.forEach((sq, i) => {
    if (withdraw && i === 0) return;
    const who = t.get(key(...sq));
    if (who && !hits.has(who)) hits.set(who, sq);
  });
  return hits;
}

function board2D() {
  const f = S.fight, { g, high, blocked, rough } = grid();
  const C = 30, M = 18;
  const W = g.width * C + M + 4, H = g.height * C + M + 4;
  const t = threatened();
  const moved = f.plan.some(p => p.kind === "move" || p.kind === "step");
  const r = moved ? null : reach();
  let cells = "";
  for (let y = 0; y < g.height; y++) for (let x = 0; x < g.width; x++) {
    const k = key(x, y);
    let cls = "sq";
    if (blocked.has(k)) cls += " blocked";
    else if (high.has(k)) cls += " high";
    else if (rough.has(k)) cls += " rough";
    const canGo = r && r.dist.has(k) && k !== key(...f.pos.pc);
    if (t.has(k) && !blocked.has(k)) cls += " threat";
    if (canGo) cls += " reach";
    if (x === DOOR[0] && y === DOOR[1]) cls += " door";
    const tgt = f.target && f.pos[f.target] && key(...f.pos[f.target]) === k;
    if (tgt) cls += " aim";
    cells += `<rect class="${cls}" x="${M + x * C}" y="${M + y * C}" width="${C}" height="${C}"${
      canGo ? ` data-sqgo="${x},${y}" tabindex="0" role="button" aria-label="Move to ${sqName([x, y])}"` : ""}><title>${sqName([x, y])}${
      high.has(k) ? ", the gallery, ten feet up" : blocked.has(k) ? ", wall" : rough.has(k) ? ", rough ground" : ""}${
      t.has(k) ? `, in ${f.people[t.get(k)].name}'s reach` : ""}</title></rect>`;
  }
  const rail = Object.keys(g.parapet || {}).map(s => {
    const [x, y] = s.split(",").map(Number);
    return `<line class="parapet" x1="${M + x * C}" y1="${M + y * C}" x2="${M + x * C + C}" y2="${M + y * C}"/>`;
  }).join("");
  const coords = Array.from({ length: g.width }, (_, x) =>
    `<text class="coord" x="${M + x * C + C / 2}" y="12" text-anchor="middle">${COLS[x]}</text>`).join("") +
    Array.from({ length: g.height }, (_, y) =>
      `<text class="coord" x="8" y="${M + y * C + C / 2 + 3}" text-anchor="middle">${y + 1}</text>`).join("");
  const mv = f.plan.find(p => p.kind === "move" || p.kind === "step");
  const path = mv ? `<polyline class="path" points="${[f.pos.pc, ...mv.path].map(([x, y]) =>
    `${M + x * C + C / 2},${M + y * C + C / 2}`).join(" ")}"/>` : "";
  const toks = Object.entries(f.pos).map(([ref, [x, y]]) => {
    const p = f.people[ref];
    const side = ref === "pc" ? "pc" : "foe";
    const at = ref === "pc" && mv ? mv.to : [x, y];
    const initials = p.name.replace(/^the /i, "")[0].toUpperCase();
    return `<g class="tok ${side}${p.hp <= 0 ? " down" : ""}" filter="url(#tokshadow)" ${ref === "pc" ? "" : `data-pick="${ref}"`}>
      <circle cx="${M + at[0] * C + C / 2}" cy="${M + at[1] * C + C / 2}" r="${C / 2 - 4}"/>
      <text x="${M + at[0] * C + C / 2}" y="${M + at[1] * C + C / 2 + 4}" text-anchor="middle">${esc(initials)}</text>
      <title>${esc(p.name)}, ${sqName(at)}</title></g>`;
  }).join("");
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="The board, ${g.width} by ${g.height} squares">
    <defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="6" stroke="currentColor" stroke-opacity=".35" stroke-width="2"/></pattern>
      <pattern id="inkhatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect width="4" height="4" fill="#3b2d22" fill-opacity=".55"/>
        <line x1="0" y1="0" x2="0" y2="4" stroke="#2a2019" stroke-width="1.6"/></pattern>
      <!-- Counters: turned wood, lit from the upper left like the 3D board (scene3d.js LIGHT). -->
      <radialGradient id="woodpc" cx=".35" cy=".3" r=".75"><stop offset="0" stop-color="#8ea3dc"/>
        <stop offset=".5" stop-color="#2b4596"/><stop offset="1" stop-color="#142457"/></radialGradient>
      <radialGradient id="woodfoe" cx=".35" cy=".3" r=".75"><stop offset="0" stop-color="#e08a78"/>
        <stop offset=".5" stop-color="#a3291b"/><stop offset="1" stop-color="#4e1108"/></radialGradient>
      <radialGradient id="woodby" cx=".35" cy=".3" r=".75"><stop offset="0" stop-color="#d9c9ad"/>
        <stop offset=".6" stop-color="#8f7c60"/><stop offset="1" stop-color="#4f4232"/></radialGradient>
      <filter id="tokshadow" x="-40%" y="-40%" width="200%" height="200%">
        <feDropShadow dx="1.6" dy="3" stdDeviation="1.4" flood-color="#220e04" flood-opacity=".5"/></filter></defs>
    ${coords}${cells}${rail}${path}${toks}</svg>`;
}
function board3D() {
  const f = S.fight, g = F.grid;
  const moved = f.plan.some(p => p.kind === "move" || p.kind === "step");
  const r = moved ? null : reach();
  const payload = {
    width: g.width, height: g.height, blocked: g.blocked, difficult: g.difficult, obscuring: g.obscuring,
    floor: Object.entries(g.floor || {}).map(([k, v]) => [...k.split(",").map(Number), v]),
    parapet: Object.entries(g.parapet || {}).map(([k, v]) => [...k.split(",").map(Number), v]),
    reachable: r ? [...r.dist.keys()].map(k => [...k.split(",").map(Number), 0]) : [],
  };
  const actors = Object.entries(f.pos).map(([ref, at]) => ({
    at: ref === "pc" && moved ? standAt() : at, is_pc: ref === "pc", side: ref === "pc" ? "pc" : "them",
    hp: f.people[ref].hp, hp_max: f.people[ref].hp_max, name: f.people[ref].name }));
  return window.Scene3D ? Scene3D.render(payload, actors, { turn: f.turn3d, level: 0, reach: !moved })
    : "<p class='railnote'>The 3D view needs play/static/js/scene3d.js.</p>";
}

const hpWords = p => (p.hp <= 0 ? "down, dying" : p.hp >= p.hp_max ? "unhurt"
  : p.hp > p.hp_max / 2 ? "wounded" : "badly wounded");

function renderFightRail() {
  const f = S.fight;
  const from = standAt();
  const targets = foes().map(ref => {
    const p = f.people[ref], at = f.pos[ref];
    const d = cheb(from, at) * 5;
    return `<button type="button" class="target" data-pick="${ref}" aria-pressed="${f.target === ref}">
      <span class="dot foe"></span><b>${esc(upper(p.name))}</b>
      <span class="dist">${d} ft</span>
      <small>Hostile, ${hpWords(p)}, ${sqName(at)}</small></button>`;
  }).join("");
  // The ways out: in a fight, leaving is a withdraw, and anyone whose reach covers the way out
  // still strikes (the owner's rule). Said on the row, before you commit (Wrath shows the
  // attacks of opportunity along a path before the move is made).
  const r = reach(f.pos.pc, 12);
  const doorPath = r.path(DOOR);
  const hits = provokers(doorPath, f.pos.pc, true);
  const risk = hits.size ? [...hits].map(([ref, sq]) => `${f.people[ref].name} strikes as you pass ${sqName(sq)}`).join("; ")
    : "nobody's reach covers the way to the door";
  const ways = exitsHere().filter(x => x[4] < 0).map(x => `<button type="button" class="exit${hits.size ? " risky" : ""}" data-exit="${esc(x[0])}">
      <b>${esc(x[1])}</b><span>withdraw</span></button>`).join("");
  $("#rail").innerHTML = `${railHead("The fight")}
    <section aria-labelledby="h-board"><h2 id="h-board">The board <small>${esc(upper(place().name))}</small></h2>
      <div class="boardtabs" role="group" aria-label="View">
        <button type="button" class="btn small" data-view="2d" aria-pressed="${f.view === "2d"}">Flat</button>
        <button type="button" class="btn small" data-view="3d" aria-pressed="${f.view === "3d"}">3D</button>
      </div>
      <div class="board" id="board">${f.view === "2d" ? board2D() : board3D()}
        ${f.view === "3d" ? `<div class="turns"><button type="button" class="btn small" data-turn="-1" aria-label="Turn the board left">Turn left</button>
          <button type="button" class="btn small" data-turn="1" aria-label="Turn the board right">Turn right</button></div>` : ""}</div>
      <p class="legend"><span><i style="background:var(--lapis)"></i>you</span>
        <span><i style="background:var(--rubric)"></i>foes, and their reach</span>
        <span><i style="background:var(--lapis-wash);border:1px solid var(--lapis)"></i>you can reach</span>
        <span><i style="background:rgba(150,120,80,.3);border:1px solid var(--rule-ink-2)"></i>the gallery</span></p></section>
    <section aria-labelledby="h-targets"><h2 id="h-targets">Targets <small>from ${sqName(from)}</small></h2>${targets}</section>
    <section aria-labelledby="h-ways"><h2 id="h-ways">Ways out <small>a withdraw, your whole turn</small></h2>
      <p class="railnote" style="margin:0 0 8px">Through the door at ${sqName(DOOR)}: ${esc(risk)}.</p>
      <div class="exits">${ways}</div></section>`;
}

function renderRibbon() {
  const f = S.fight;
  $("#ribbon").hidden = false;
  $("#ribbon").innerHTML = `<div class="round"><b>Round <span>${f.round}</span></b><small>${f.order.length} in the fight</small></div>` +
    f.order.map(([ref, init], i) => {
      const p = f.people[ref];
      const cls = ref === "pc" ? "you" : "foe";
      const now = i === f.turn;
      const state = now ? (ref === "pc" ? "your turn" : "acting") : i < f.turn ? "has acted" : "waiting";
      return `<button type="button" class="turn ${cls}${now ? " now" : ""}${i < f.turn ? " done" : ""}"
        ${ref === "pc" ? "" : `data-pick="${ref}"`} aria-current="${now ? "step" : "false"}">
        <span class="init">${init}</span><b>${esc(upper(p.name))}</b><small>${state}${ref === "pc" ? `, ${p.hp} of ${p.hp_max}` : `, ${hpWords(p)}`}</small></button>`;
    }).join("");
}

// --- The turn's budget and its plan -----------------------------------------------------------------
const ECON = [["standard", "Standard", "strike, cast, manoeuvre"], ["move", "Move", "move, draw, stand"],
              ["swift", "Swift", "one a round"], ["free", "Free", "a few"]];
function spent() {
  const u = { standard: false, move: false, swift: false, full: false };
  S.fight.plan.forEach(p => {
    if (p.cost === "full") { u.standard = u.move = u.full = true; }
    else if (p.cost) u[p.cost] = true;
  });
  return u;
}
function renderCombatDock() {
  const f = S.fight, u = spent();
  const mine = f.order[f.turn][0] === "pc";
  const pips = ECON.map(([k, label, what]) => `<div class="pip${u[k] ? " used" : ""}"><i></i>
      <span>${label}</span><small>${u[k] ? "used" : k === "free" ? "any" : "open"}</small></div>`).join("");
  const plan = f.plan.length ? f.plan.map((p, i) => `<span class="chipbtn">${esc(p.text)}
      <button type="button" class="x" data-unplan="${i}" aria-label="Take off: ${esc(p.text)}">&times;</button></span>`).join("")
    : `<span>Plan your turn: a square on the board to move, then an action. Nothing happens until you commit.</span>`;
  $("#dock-combat").innerHTML = `<div class="economy" aria-label="Actions left this turn">
      <h3>${mine ? "Your turn" : "Waiting"}</h3>${pips}</div>
    <div class="cacts">
      <div class="row">
        <button type="button" class="btn boardbtn" data-board aria-controls="rail">Board</button>
        <button type="button" class="btn" data-cact="strike"${!mine || u.standard ? " disabled" : ""}>Strike</button>
        <button type="button" class="btn" data-cact="full"${!mine || u.standard || u.move ? " disabled" : ""}>Full attack</button>
        <button type="button" class="btn" data-cmenu="ability"${!mine ? " disabled" : ""}>Ability</button>
        ${isCaster() ? `<button type="button" class="btn" data-cmenu="cast"${!mine || u.standard ? " disabled" : ""}>Cast</button>` : ""}
        <button type="button" class="btn" data-cmenu="swift"${!mine || u.swift ? " disabled" : ""}>Swift</button>
        <button type="button" class="btn" data-cmenu="free"${!mine ? " disabled" : ""}>Free</button>
      </div>
      <div class="row commitrow">
        <div class="plan" aria-live="polite">${plan}</div>
        <button type="button" class="btn" data-cact="end"${!mine ? " disabled" : ""}>End turn</button>
        <button type="button" class="btn primary" data-cact="commit"${!mine || !f.plan.length ? " disabled" : ""}>Commit turn</button>
      </div>
      ${f.hint ? `<p class="hint${f.hintBad ? " bad" : ""}">${esc(f.hint)}</p>` : ""}
    </div>`;
}
function renderFight() {
  if (S.scene !== "fight") return;
  renderRibbon(); renderFightRail(); renderCombatDock(); paintIcons($("#dock"));
}
function hint(text, bad = false) { S.fight.hint = text; S.fight.hintBad = bad; renderCombatDock(); }

function addToPlan(p) {
  const f = S.fight;
  if (p.kind === "cast") {
    const sp = D.spells[p.spell];
    p = { kind: "cast", cost: sp.casting_time.startsWith("standard") ? "standard" : "full", spell: p.spell,
          text: `Cast ${sp.name}${f.target ? ` at ${f.people[f.target].name}` : ""}` };
  }
  f.plan = f.plan.filter(x => !(x.kind === p.kind && p.kind !== "free"));
  f.plan.push(p);
  f.hint = ""; renderFight(); renderDock();
}
function removeFromPlan(kind) {
  S.fight.plan = S.fight.plan.filter(p => p.kind !== kind);
  renderFight();
}

// Picking a square: a move (a move action), or a five-foot step when it is one square away.
function planMove(x, y) {
  const f = S.fight, u = spent();
  const r = reach();
  const to = [x, y], path = r.path(to);
  if (!path.length) return;
  const step = path.length === 1 && !grid().rough.has(key(x, y));
  if (!step && (u.move || u.full)) { hint("Your move action is already spent this turn.", true); return; }
  const hits = step ? new Map() : provokers(path, f.pos.pc);
  const warn = hits.size ? `, provokes ${[...hits.keys()].map(k => f.people[k].name).join(" and ")}` : "";
  addToPlan({ kind: step ? "step" : "move", cost: step ? "" : "move", to, path, hits: [...hits.keys()],
              text: step ? `5-foot step to ${sqName(to)}, does not provoke` : `Move to ${sqName(to)}${warn}` });
  if (hits.size) hint(`Leaving ${[...hits.values()].map(sqName).join(", ")} gives ${[...hits.keys()].map(k => f.people[k].name).join(" and ")} an attack of opportunity. A 5-foot step would not.`, true);
}

function weapon() { return sheet().attacks.find(a => a.equipped) || sheet().attacks[0]; }
// Melee blows are refused out of reach, with the square named (merged 2026-09-28).
function inReach(ref) {
  const d = cheb(standAt(), S.fight.pos[ref]);
  return d <= 1;
}
function planStrike(full) {
  const f = S.fight;
  if (!f.target) { hint("Pick a target first: on the board or in the list.", true); return; }
  const p = f.people[f.target], w = weapon();
  if (!inReach(f.target)) {
    hint(`${upper(p.name)} is at ${sqName(f.pos[f.target])}, ${cheb(standAt(), f.pos[f.target]) * 5} ft from ${sqName(standAt())}. Your ${w.name} reaches 5 ft: move next to them first.`, true);
    return;
  }
  const seq = w.attack.total;
  addToPlan({ kind: "strike", cost: full ? "full" : "standard", target: f.target, full,
              text: `${full ? "Full attack" : "Strike"} ${p.name}, ${w.name} ${signed(seq)}, ${w.damage_dice}${w.damage.total ? signed(w.damage.total) : ""}` });
  if (full) hint(`At base attack +${sheet().bab} a full attack is one swing. Iteratives arrive at +6.`);
}

// Menus: the ability list holds the combat manoeuvres, each with its bonus and whether it provokes.
function combatMenu(kind) {
  const pop = $("#pop-craft"), s = sheet(), f = S.fight;
  let body = "";
  if (kind === "ability") {
    const feats = s.class_features.length ? `<p>${esc(upper(s.class_features.join(", ")))}: always on, applied by the engine when they apply.</p>` : "";
    body = `<h3><span>Ability</span><button type="button" class="btn small quiet" data-close-pop>Close</button></h3>${feats}
      <p class="grouplab">Combat manoeuvres, a standard action. CMB ${signed(s.cmb.total)}</p>
      <div class="optgrid">${s.maneuvers.map(m => `<button type="button" class="opt" data-man="${esc(m.name)}">
        <b>${esc(upper(m.name))} ${signed(m.cmb.total)}</b>
        <small>${esc(m.effect)}. <span class="${m.provokes ? "provokes" : "safe"}">${m.provokes ? "Provokes" : "Does not provoke"}</span></small></button>`).join("")}</div>`;
  } else if (kind === "swift") {
    body = `<h3><span>Swift</span><button type="button" class="btn small quiet" data-close-pop>Close</button></h3>
      <p>Nothing on this sheet is swift yet. A class feature or spell that is would be listed here.</p>`;
  } else if (kind === "free") {
    body = `<h3><span>Free</span><button type="button" class="btn small quiet" data-close-pop>Close</button></h3>
      <div class="optgrid">${[["Drop what you hold", "Lets go of the " + weapon().name], ["Drop prone", "Onto the floor where you stand"],
        ["Speak", "A few words, while you fight"]].map(([n, d]) => `<button type="button" class="opt" data-free="${esc(n)}"><b>${esc(n)}</b><small>${esc(d)}</small></button>`).join("")}</div>`;
  } else if (kind === "cast") {
    renderCastPop();
    $("#pop-cast").hidden = false; paintIcons($("#pop-cast"));
    return;
  }
  pop.innerHTML = body; pop.hidden = false;
  const first = pop.querySelector(".opt"); if (first) first.focus();
}

// --- Resolving: the player's own d20 on the app's dice mat, then the engine's reply -----------------
async function commitTurn() {
  const f = S.fight, s = sheet(), slips = [];
  const plan = f.plan.slice();
  const said = plan.filter(p => p.kind === "words").map(p => p.words);
  f.plan = []; f.hint = "";
  let dropped = false;
  for (const p of plan) {
    if (p.kind === "move" || p.kind === "step") {
      for (const ref of p.hits || []) {
        slips.push(await foeAttack(ref, "Attack of opportunity"));
      }
      slips.push({ type: "move", from: sqName(f.pos.pc), to: sqName(p.to) });
      f.pos.pc = p.to;
    }
    if (p.kind === "strike") {
      const t = f.people[p.target], w = weapon();
      const nat = d20(), total = nat + w.attack.total;
      const hit = nat === 20 || (nat !== 1 && total >= t.ac);
      if (window.Dice3D) {
        await Dice3D.land({ title: `Attack with ${w.name}`, why: `Against ${t.name}`, sides: 20, result: nat,
          terms: [{ label: "d20", value: nat }, ...w.attack.terms.map(x => ({ label: x.source, value: signed(x.value) })),
                  { label: "Total", value: total, total: true }],
          verdict: { text: hit ? `Hits AC ${t.ac}` : `Misses AC ${t.ac}`, good: hit } });
      }
      slips.push({ type: "roll", label: `Attack with ${w.name}`, die: "1d20", faces: [nat], natural: nat,
                   terms: w.attack.terms, total, vs: { what: "AC", value: t.ac, explain: `${t.name}, not flat-footed now` },
                   verdict: hit ? "hit" : "miss", good: hit });
      if (hit) {
        const faces = roll(w.damage_dice), dmg = Math.max(1, faces.reduce((a, b) => a + b, 0) + w.damage.total);
        t.hp -= dmg;
        slips.push({ type: "roll", label: `Damage (${w.name})`, die: w.damage_dice, faces, terms: w.damage.terms, total: dmg });
        slips.push({ title: "Tell", text: `${s.identity.name} hits ${t.name} for ${dmg} ${w.type}.${t.hp <= 0 ? ` ${upper(t.name)} is down.` : ""}` });
      }
    }
    if (p.kind === "man") {
      const m = s.maneuvers.find(x => x.name === p.name);
      const nat = d20(), total = nat + m.cmb.total;
      if (m.provokes) slips.push(await foeAttack(p.target, "Attack of opportunity"));
      if (window.Dice3D) await Dice3D.land({ title: upper(m.name), why: `Against ${f.people[p.target].name}`, sides: 20, result: nat,
        terms: [{ label: "d20", value: nat }, ...m.cmb.terms.map(x => ({ label: x.source, value: signed(x.value) })), { label: "Total", value: total, total: true }] });
      slips.push({ type: "roll", label: `${upper(m.name)} (CMB)`, die: "1d20", faces: [nat], natural: nat, terms: m.cmb.terms, total,
                   vs: { what: "CMD", value: "?", explain: "the engine rolls against their CMD" } });
    }
    if (p.kind === "cast") {
      const sp = D.spells[p.spell];
      if (sp.level > 0) me().caster.spent[sp.level] = (me().caster.spent[sp.level] || 0) + 1;
      slips.push({ type: "cast", name: sp.name, slot: sp.level > 0, detail: `${sp.casting_time}, ${sp.range.replace(/ \(.*\)/, "")}` });
      if (p.spell === "magic-missile" && f.target) {
        const faces = roll("1d4"), dmg = faces[0] + 1;
        f.people[f.target].hp -= dmg;
        slips.push({ type: "roll", label: "Magic Missile, force", die: "1d4", faces, terms: [{ source: "missile", value: 1 }], total: dmg });
      }
      S.attached = null; renderDock();
    }
    if (p.kind === "free" && /^Drop what/.test(p.text)) dropped = true;
    if (p.kind === "withdraw") {
      for (const [ref] of p.hits) slips.push(await foeAttack(ref, "Strikes as you withdraw"));
      endFight(p.row, slips);
      return;
    }
  }
  const words = plan.map(p => p.text).join(". ") + ".";
  addBeats([beat("you", said.length ? `${words} ${said.join(" ")}` : words)]);
  gmWrites(slips, `Mock. The narrator writes this turn from the tells in the margin, and nothing else.${dropped ? " The weapon is on the floor now." : ""}`);
  nextTurn();
}
async function foeAttack(ref, label) {
  const f = S.fight, foe = f.people[ref], a = foe.attack;
  const nat = d20(), total = nat + a.bonus, ac = sheet().ac.total;
  const hit = nat === 20 || (nat !== 1 && total >= ac);
  if (hit) {
    const faces = roll(a.dice), dmg = Math.max(1, faces.reduce((x, y) => x + y, 0) + a.dmg);
    f.people.pc.hp -= dmg; sheet().hp.current = f.people.pc.hp;
    renderBar();
    return { type: "roll", label: `${label}: ${foe.name}, ${a.name}`, die: "1d20", faces: [nat], natural: nat,
             terms: [{ source: "attack", value: a.bonus }], total, vs: { what: "your AC", value: ac },
             verdict: `hit, ${dmg} ${/unarmed/.test(a.name) ? "nonlethal" : "damage"}`, good: false };
  }
  return { type: "roll", label: `${label}: ${foe.name}, ${a.name}`, die: "1d20", faces: [nat], natural: nat,
           terms: [{ source: "attack", value: a.bonus }], total, vs: { what: "your AC", value: ac }, verdict: "miss", good: true };
}
// The engine plays the foes, rolls their dice itself (never on the player's mat), and hands the
// narrator the tells.
async function nextTurn() {
  const f = S.fight;
  f.turn += 1;
  if (f.turn >= f.order.length) { f.turn = 0; f.round += 1; }
  renderFight();
  const [ref] = f.order[f.turn];
  if (ref === "pc") return;
  if (!alive(ref)) { nextTurn(); return; }
  if (foes().filter(alive).length === 0) return;
  await new Promise(r => setTimeout(r, 900));
  const slips = [];
  const at = f.pos[ref];
  if (cheb(at, f.pos.pc) > 1) {
    // Close in: the free square beside the PC nearest to him.
    const r = reach(at, 6);
    let best = null;
    for (let dc = -1; dc <= 1; dc++) for (let dr = -1; dr <= 1; dr++) {
      const sq = [f.pos.pc[0] + dc, f.pos.pc[1] + dr];
      if ((dc || dr) && r.dist.has(key(...sq)) && (!best || r.dist.get(key(...sq)) < r.dist.get(key(...best)))) best = sq;
    }
    if (best) { slips.push({ type: "move", from: sqName(at), to: sqName(best) }); f.pos[ref] = best; }
  }
  if (cheb(f.pos[ref], f.pos.pc) <= 1) slips.push(await foeAttack(ref, "Attack"));
  addBeats([beat("oc", `Mock. ${upper(f.people[ref].name)}'s turn, played by the engine. The narrator writes it from these tells.`, slips)]);
  nextTurn();
}
function endTurn(fromContinue) {
  if (S.scene !== "fight") return;
  const f = S.fight;
  if (f.order[f.turn][0] !== "pc") return;
  if (f.plan.length && !fromContinue) { commitTurn(); return; }
  f.plan = [];
  addBeats([beat("you", fromContinue ? "Continue: I hold my ground." : "I end my turn.")]);
  nextTurn();
}
function withdraw(row) {
  const f = S.fight;
  const r = reach(f.pos.pc, 12);
  const hits = provokers(r.path(DOOR), f.pos.pc, true);
  f.plan = [{ kind: "withdraw", cost: "full", row, hits: [...hits],
              text: `Withdraw to ${row[1]}${hits.size ? `, ${[...hits.keys()].map(k => f.people[k].name).join(" and ")} strikes` : ""}` }];
  hint(`A withdraw takes the whole turn. Commit to go.`);
  renderFight();
}
function endFight(row, slips) {
  S.scene = "explore"; S.fight = null; S.place = row[0];
  document.body.classList.remove("scene-fight"); document.body.classList.add("scene-explore");
  $("#ribbon").hidden = true;
  addBeats([beat("you", `I withdraw to ${row[1]}.`, []), placeBeat(row[0]),
            beat("oc", "Mock. You are out of the fight. The narrator writes the escape from the tells.", [...slips,
              { type: "move", from: "the west crossing", to: row[1] }, advance(1, "a round")])]);
  renderRail(); renderDock();
}
function fightWords(text) {
  if (!text) return;
  addToPlan({ kind: "words", cost: "", words: text, text: `Say: ${text.length > 40 ? text.slice(0, 40) + "…" : text}` });
}

// --- Clicks ---------------------------------------------------------------------------------------------
document.addEventListener("click", e => {
  if (S.scene !== "fight") return;
  const f = S.fight;
  const go = e.target.closest("#board [data-sqgo], #board [data-sq]");
  if (go) {
    const [x, y] = (go.dataset.sqgo || go.dataset.sq).split(",").map(Number);
    planMove(x, y); return;
  }
  const pick = e.target.closest("[data-pick]");
  if (pick) { f.target = pick.dataset.pick; renderFight(); return; }
  const v = e.target.closest("[data-view]");
  if (v) { f.view = v.dataset.view; renderFightRail(); return; }
  const t = e.target.closest("[data-turn]");
  if (t) { f.turn3d = (f.turn3d + +t.dataset.turn + 4) % 4; renderFightRail(); return; }
  const c = e.target.closest("[data-cact]");
  if (c) {
    if (c.dataset.cact === "strike") planStrike(false);
    if (c.dataset.cact === "full") planStrike(true);
    if (c.dataset.cact === "commit") commitTurn();
    if (c.dataset.cact === "end") endTurn(false);
    return;
  }
  if (e.target.closest("[data-board]")) { openRail(true); return; }
  const m = e.target.closest("[data-cmenu]");
  if (m) { combatMenu(m.dataset.cmenu); return; }
  const man = e.target.closest("[data-man]");
  if (man) {
    $("#pop-craft").hidden = true;
    if (!f.target || !inReach(f.target)) { hint("A manoeuvre needs a target within your reach.", true); return; }
    const mm = sheet().maneuvers.find(x => x.name === man.dataset.man);
    addToPlan({ kind: "man", cost: "standard", name: mm.name, target: f.target,
                text: `${upper(mm.name)} ${f.people[f.target].name}, CMB ${signed(mm.cmb.total)}${mm.provokes ? ", provokes" : ""}` });
    return;
  }
  const fr = e.target.closest("[data-free]");
  if (fr) { $("#pop-craft").hidden = true; addToPlan({ kind: "free", cost: "", text: fr.dataset.free }); return; }
  const un = e.target.closest("[data-unplan]");
  if (un) {
    const p = f.plan[+un.dataset.unplan];
    if (p && p.kind === "cast") S.attached = null;
    f.plan.splice(+un.dataset.unplan, 1); f.hint = ""; renderFight(); renderDock();
  }
});
document.addEventListener("keydown", e => {
  if (S.scene !== "fight") return;
  const go = e.target.closest && e.target.closest("#board [data-sqgo]");
  if (go && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); go.dispatchEvent(new MouseEvent("click", { bubbles: true })); }
});
