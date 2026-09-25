// The play table, part 03 of 6 (offers and map). Split out of
// play/templates/play/table.html on 2026-09-25, in the order it ran; the six
// files are classic scripts, loaded in that order, sharing one global scope.
// --- what the GM offered -----------------------------------------------------------
//
// Suggestions, not a menu. Clicking one puts the words in the box rather than sending
// them, so the player can change their mind or add to it — a chip that fired the turn
// straight off would quietly turn a nudge into the only three things you can do.
function renderGmView(s) {
  const box = $("#gmview");
  if (!box) { return; }
  const running = s.schemes;
  if (!running) { box.innerHTML = ""; return; }
  if (!running.length) {
    box.innerHTML = `<h2>Behind the screen</h2><div class="sub">No scheme is running.</div>`;
    return;
  }
  box.innerHTML = `<h2>Behind the screen</h2>` + running.map(x => {
    const slots = Object.entries(x.slots || {})
      .map(([k, v]) => `<div class="sub">${esc(k)}: ${esc(v || "unfilled")}</div>`).join("");
    const fired = Object.keys(x.fired || {});
    return `<div class="scheme">
      <div><b>${esc(x.title || x.scheme)}</b></div>
      ${slots}
      ${fired.length ? `<div class="sub">fired: ${esc(fired.join(", "))}</div>` : ""}
      ${(x.skipped || []).length
        ? `<div class="sub">skipped: ${esc((x.skipped || []).join("; "))}</div>` : ""}
      ${x.outcome ? `<div class="sub">outcome: ${esc(x.outcome)}</div>` : ""}
      ${(x.news || []).length ? `<div class="sub">news on its way: ${(x.news || []).length}</div>` : ""}
    </div>`;
  }).join("");
}

function renderSuggestions(s) {
  const box = $("#suggestions");
  const offered = (s.suggestions || []);
  // Hidden entirely while a roll is pending: the only thing to do then is answer it.
  if (!offered.length || s.awaiting) { box.innerHTML = ""; return; }
  box.innerHTML = offered.map(t =>
    `<button type="button" class="sugg">${esc(t)}</button>`).join("");
}

document.addEventListener("click", e => {
  const chip = e.target.closest(".sugg");
  if (!chip) return;
  const input = $("#input");
  input.value = chip.textContent;
  input.focus();
  input.setSelectionRange(input.value.length, input.value.length);
});

// --- the map -------------------------------------------------------------------------
//
// Drawn as an SVG rather than a grid of divs: a 20x20 map is 400 elements either way, and
// the SVG version scales to the panel without every square needing its own size in pixels.
//
// The reachable squares are computed by the engine and sent down, never worked out here.
// Two implementations of the alternating diagonal rule would eventually disagree, and the
// one on screen is the one the player would believe.
// Which floor of the room the map is showing. Not part of STATE: it is a way of looking
// at the board, not a fact about it, and putting it in the server's payload would make
// the server responsible for where the player's attention is.
let MAP_LEVEL = 0;
// Which way the board is being looked at, and whether it is being looked at flat. Both
// are ways of looking rather than facts about the scene, so neither belongs in STATE —
// the server is not responsible for where the player's attention is.
let MAP_TURN = 0, MAP_3D = false;

function renderMap(s) {
  const g = s.scene.grid;
  if (!g) {
    $("#mapwrap").innerHTML = "";
    // A blank tray reads as broken, so it says why. Since 2026-09-19 the ground is laid
    // when the party ARRIVES somewhere rather than when a fight starts (item 28), so this
    // is now the rare case — a scene with nowhere in it yet, between worlds or before the
    // party has been placed.
    $("#maptrayinner").innerHTML =
      `<div class="empty">No ground is mapped yet. The map is drawn from wherever the
       party is standing, as soon as they are standing somewhere.</div>`;
    return;
  }

  const CELL = 18;
  const reach = new Map((g.reachable || []).map(([c, r, cost]) => [`${c},${r}`, cost]));
  const parts = [];

  // Which floor is being looked at. A room with only one is not asked about — a level
  // picker over a flat market is a control that does nothing, and the first thing a
  // player learns from it is that it does not matter.
  const levels = (g.levels && g.levels.length > 1) ? g.levels : [0];
  if (!levels.includes(MAP_LEVEL)) MAP_LEVEL = levels[0];
  const ground = new Map((g.floor || []).map(([c, r, v]) => [`${c},${r}`, v]));
  const at = (c, r) => ground.get(`${c},${r}`) || 0;

  for (const [c, r] of g.difficult) parts.push(cell(c, r, "difficult"));
  for (const [c, r] of g.obscuring) parts.push(cell(c, r, "obscuring"));
  for (const [c, r] of g.blocked) parts.push(cell(c, r, "blocked"));
  // Raised ground, lighter the higher it stands, drawn under everything else so a token
  // on a dais still reads as a token on a dais.
  for (const [c, r, v] of (g.floor || []))
    parts.push(cell(c, r, `up${Math.min(3, v)}`,
      `<title>${v * 5} ft above the floor</title>`));
  // Rails as edges, not fills. A parapet is a thing to shoot over; a filled square
  // would read as a wall, which is the very mistake the engine was making.
  for (const [c, r, v] of (g.parapet || []))
    parts.push(`<line class="rail" x1="${c * CELL + 2}" y1="${(r + .5) * CELL}" x2="${
      (c + 1) * CELL - 2}" y2="${(r + .5) * CELL}"><title>a rail, ${
      v * 5} ft up</title></line>`);
  for (const [key, cost] of reach) {
    const [c, r] = key.split(",").map(Number);
    // data-sq is what makes the square a *destination* — the combat builder queues a
    // move op from it. Present whether or not the panel is open, harmless when idle.
    // data-sq is what makes the square a destination for the combat builder. The
    // first cut replaced on 'class="cell reach"', which cell() never writes — the
    // legend counted 35 lit squares while zero of them were clickable.
    // A destination carries the level it lands you on, so the combat builder queues a
    // move to a CELL and not merely a square. Walking onto a dais is walking up onto it.
    const lvl = at(c, r);
    parts.push(cell(c, r, "reach", `<title>${cost} ft${
        lvl ? ` · ${lvl * 5} ft up` : ""}</title>`)
      .replace('class="reach"', `class="reach" data-sq="${c},${r}${
        lvl ? "," + lvl : ""}"`));
  }

  // Grid lines last of the terrain, so they sit over the fills and under the tokens.
  for (let c = 0; c <= g.width; c++)
    parts.push(`<line class="rule" x1="${c * CELL}" y1="0" x2="${
      c * CELL}" y2="${g.height * CELL}"/>`);
  for (let r = 0; r <= g.height; r++)
    parts.push(`<line class="rule" x1="0" y1="${r * CELL}" x2="${
      g.width * CELL}" y2="${r * CELL}"/>`);

  // Blood before bodies, so a token stands in its own pool rather than under it.
  for (const b of (s.scene.pools || [])) {
    if (!b.at) continue;
    parts.push(`<circle class="bloodpool" cx="${(b.at[0] + .5) * CELL}" cy="${
      (b.at[1] + .5) * CELL}" r="${CELL * .38}">
      <title>blood pool — ${esc(b.source || b.owner)}</title></circle>`);
  }

  for (const a of s.scene.actors) {
    if (!a.at) continue;
    const [c, r] = a.at;
    const n = a.squares || 1;
    const down = a.hp <= 0;
    const side = a.is_pc ? " pc" : a.side ? (a.side === "pc" || a.side === "you" ? " ally" : " foe")
      : (s.scene.in_encounter ? " bystander" : "");
    // Somebody on another floor of the same room is faded, not hidden. Hiding them is
    // how a player is surprised by an archer who was on the map the whole time; this is
    // the level selector saying "not who you are looking at" rather than "not there".
    const mine = (a.at.length > 2 ? a.at[2] : 0) === MAP_LEVEL;
    const ghost = mine ? "" : " offlevel";
    // A crowd is many people, and a plain filled block of nine squares reads as one big
    // creature (item 33). The unit gets a hatched fill and its count on the glyph, so a
    // 3x3 of townsfolk cannot be mistaken for a giant.
    const unit = a.members != null;
    parts.push(`<rect class="token${side}${down ? " down" : ""}${ghost}${unit ? " unit" : ""}"
      x="${c * CELL + 2}" y="${r * CELL + 2}"
      width="${n * CELL - 4}" height="${n * CELL - 4}" rx="3">
      <title>${esc(a.name)} — ${a.hp}/${a.hp_max}${
        unit ? ` · ${a.members} of ${a.members_max} still standing` : ""}${
        a.at.length > 2 && a.at[2] ? ` · ${a.at[2] * 5} ft up` : ""}</title></rect>`);
    parts.push(`<text class="tok" x="${(c + n / 2) * CELL}" y="${
      (r + n / 2) * CELL + 4}">${unit ? a.members
        : esc(a.name.slice(0, 1).toUpperCase())}</text>`);
  }

  // The same board, drawn two ways. Both read the one geometry payload and both write
  // `data-sq`, so the combat builder cannot tell them apart — which is the whole reason
  // the flat one was built first.
  const svg = MAP_3D
    ? Scene3D.render(g, s.scene.actors || [],
                     { turn: MAP_TURN, level: MAP_LEVEL,
                       reach: !!(STATE.scene && STATE.scene.in_encounter) })
    : `<svg id="map" viewBox="0 0 ${g.width * CELL} ${g.height * CELL}"
         preserveAspectRatio="xMidYMid meet"><defs>
         <pattern id="unithatch-foe" width="6" height="6" patternUnits="userSpaceOnUse"
                  patternTransform="rotate(45)">
           <rect width="6" height="6" fill="#7d1a14"></rect>
           <line x1="0" y1="0" x2="0" y2="6" stroke="#e0261e" stroke-width="3"></line>
         </pattern>
         <pattern id="unithatch-quiet" width="6" height="6" patternUnits="userSpaceOnUse"
                  patternTransform="rotate(45)">
           <rect width="6" height="6" fill="#d9d2c2"></rect>
           <line x1="0" y1="0" x2="0" y2="6" stroke="#f7f2e6" stroke-width="3"></line>
         </pattern>
       </defs>${parts.join("")}</svg>`;
  const pools = (s.scene.pools || []).length;
  const picker = levels.length > 1
    ? `<div class="levelpick"><span class="sub">Looking at</span>${levels.map(v =>
        `<button data-maplevel="${v}" class="${v === MAP_LEVEL ? "on" : ""}">${
          v ? (v > 0 ? `+${v * 5} ft` : `${v * 5} ft`) : "the floor"}</button>`).join("")}${
        g.ceiling ? `<span class="sub">ceiling ${g.ceiling * 5} ft</span>` : ""}</div>`
    : "";
  const view = `<div class="levelpick"><button data-mapview="${MAP_3D ? "flat" : "3d"}">${
      MAP_3D ? "Flat" : "3D"}</button>${MAP_3D
      ? `<button data-mapturn="-1" title="Turn the board left">&#8630;</button>`
        + `<button data-mapturn="1" title="Turn the board right">&#8631;</button>`
      : ""}</div>`;
  const legend = `${view}${picker}${g.speed ? `<div class="sub maplegend">${
      reach.size} squares within ${g.speed} ft</div>` : ""}${
      pools ? `<div class="sub maplegend">${pools} pool${
        pools === 1 ? "" : "s"} of blood on the ground</div>` : ""}`;
  // The place is named, not just drawn. A correct map of the well, while the prose is
  // describing a gate, is indistinguishable from a broken map unless the tray says which
  // place it is — reported 2026-09-21. `about` is the shape's own line about what that
  // kind of place is made of, which is also what the plan was built from.
  const whereHead = g.place ? `The ground · ${esc(g.place)}` : "The ground";
  $("#mapwrap").innerHTML = `<h2>${whereHead} <button class="mapopen" id="mapopen"
      title="Open the map">⤢</button></h2>${svg}${
      g.about ? `<div class="sub maplegend">${esc(g.about)}</div>` : ""}${legend}`;

  // The same SVG at a readable size. The side panel's copy is 18px to the square and
  // legible only as a shape; a grid the player is meant to plan a move on has to be
  // something they can actually look at.
  if ($("#maptray").classList.contains("on")) {
    $("#maptrayinner").innerHTML = svg
      + (g.about ? `<div class="sub maplegend">${esc(g.about)}</div>` : "") + legend;
    // The expanded tray names the place in its own bar, for the same reason the panel
    // does: a map nobody can name is a map nobody can check.
    const bar = document.querySelector("#maptray .traybar b");
    if (bar) bar.textContent = g.place ? `The ground · ${g.place}` : "The ground";
  }

  function cell(c, r, cls, inner = "") {
    return `<rect class="${cls}" x="${c * CELL}" y="${r * CELL}" width="${
      CELL}" height="${CELL}">${inner}</rect>`;
  }
}

function renderRolls(log) {
  const rolls = [];
  for (const entry of log) {
    for (const o of (entry.outcomes || [])) {
      for (const r of (o.rolls || [])) {
        rolls.push({r, o});
      }
    }
  }
  // Only the player's own rolls ever appear here. The server already strips everyone
  // else's before the state leaves it, so there is nothing to filter and nothing to
  // find in the page source.
  $("#rolls").innerHTML = rolls.slice(-8).reverse().map(({r, o}) => `
    <div class="who" style="display:block">
      <div style="display:flex;justify-content:space-between">
        <span>${esc(r.label || o.op)}</span>
        <span style="color:var(--accent)">${r.total}${
          // Only a d20 is compared against a DC or an AC. Showing the outcome's target
          // beside a damage roll read as "6 vs 10", which looks like a miss.
          o.dc && o.dc.value != null && r.die === "1d20" ? " vs " + o.dc.value : ""}</span>
      </div>
      <small>${r.raw}${
        r.modifiers.map(m => ` ${sign(m.value)} ${esc(m.source)}`).join("")}</small>
    </div>`).join("") || `<div class="sub">Nothing rolled yet.</div>`;
}

function showPopup(p) {
  // The 3D die, asking. `Dice3D.ask` resolves with a number the player rolled on a real
  // die — behind the debug toggle, because a die on the desk is the exception — or null,
  // meaning the table rolls it, which is the default and what the solid is for.
  const lo = p.min != null ? p.min : 1, hi = p.max != null ? p.max : 20;
  const die = p.die || "1d20";
  const terms = p.breakdown.map(m => ({ label: m.source, value: sign(m.value) }));
  // The total row only when there is something to total: with one term the card read
      // "Str x2 +38" over "your modifier +38", the same number twice (2026-09-18, item 3).
      if (p.breakdown.length !== 1) terms.push({ label: "your modifier", value: sign(p.modifier), total: true });
  // `dc_shown` is the engine saying whether this number is a difficulty the
  // player may know or the result of a die already rolled in secret. Absent on
  // a payload from an older save mid-flight, which reads as shown — the same
  // answer it had before the flag existed.
  if (p.dc != null && p.dc_shown !== false) terms.push({ label: "beat", value: p.dc });

  const shown = {
    title: p.label,
    why: p.because || "",
    sides: hi - lo + 1 === 20 ? 20 : (hi - lo + 1),
    lo: lo, hi: hi, die: die,
    terms: terms,
    note: lo === hi ? "" : `${die} (${lo}–${hi})`,
  };
  // `hold` keeps the mat open when the table is doing the rolling, so the die goes
  // straight from the wind-up into its throw. It used to close here and reopen on the
  // far side of the request, which is the blink the player saw as the animation
  // skipping — two throws with a cut between them.
  Dice3D.ask(Object.assign({ hold: true }, shown)).then(face => sendRoll(face, shown));
}

// Everything that can be gone out and got, here, now — one list from every craft.
// Foraging keeps its own button because it has the narrated hourly run behind it; the
// rest share the plain excursion path.
async function loadCraftActions() {
  try {
    const d = await readJSON(await fetch("/api/craft/actions", { cache: "reload" }));
    $("#cp-biome").textContent = d.biome || "nowhere in particular";
    $("#cp-desc").textContent = d.biome_describe || "";
    const busyWhy = d.blocked || "";
    $("#cp-busy").hidden = !busyWhy;
    $("#cp-busy").textContent = busyWhy;
    $("#cp-biomepick").innerHTML = (d.biomes || []).map(b =>
      `<option value="${esc(b)}" ${b === d.biome ? "selected" : ""}>${esc(b)}</option>`
    ).join("");
    $("#cp-actions").innerHTML = (d.actions || []).map(a => {
      // Foraging goes through the narrated endpoint it always did.
      const id = a.key === "herbalist:forage" ? "cp-forage" : "";
      const attr = id ? `id="cp-forage"` :
        `data-excursion="${esc(a.key)}" data-label="${esc(a.label)}"` +
        (a.targets && a.targets.length
          ? ` data-creature="${esc(a.targets[0].name)}"` : "");
      const tip = [a.blurb || "", a.requires_note || "",
                   a.available ? "" : a.why].filter(Boolean).join("\n\n");
      return `<button type="button" ${attr} ${a.available ? "" : "disabled"}
        title="${esc(tip)}">${esc(a.label)}<small>${esc(a.track)}${
        a.level ? ` ${a.level}` : ""}</small></button>`;
    }).join("") || `<div class="cp-busy">No craft actions here.</div>`;
  } catch (err) { $("#err").textContent = err.message; }
}

// The craft-action excursion. The server narrates the setting-out, rolls the same
// forage op the bench uses, narrates the finding and hands back three suggestions;
// this only sequences what the player sees — opening first, the die landing on a real
// d100 from the run, then the full turn with the tally and the question.
document.addEventListener("click", async e => {
  if (e.target.closest("#craftaction")) {
    const panel = $("#craftpanel");
    panel.hidden = !panel.hidden;
    if (!panel.hidden) await loadCraftActions();
    return;
  }

  // The debug teleport, on the hub rather than the bench.
  if (e.target.closest("#cp-debug")) {
    const pick = $("#cp-biomepick");
    pick.hidden = !pick.hidden;
    return;
  }

  // Everything that is not foraging: one excursion, one check, a haul into the pack.
  const go = e.target.closest("[data-excursion]");
  if (go) {
    const hours = Math.max(1, Math.min(12, Number($("#cp-h").value) || 1));
    $("#craftpanel").hidden = true;
    busy(true);
    try {
      const d = await post("/api/craft/excursion",
        { action: go.dataset.excursion, hours, creature: go.dataset.creature || "" });
      busy(false);
      await Dice3D.land({
        title: go.dataset.label || "Excursion",
        why: `DC ${d.dc}${d.bonus ? ` · your bonus +${d.bonus}` : ""}`,
        sides: 20, result: d.roll,
        note: d.found && d.found.length
          ? d.found.map(h => `${h.name} ×${h.count}`).join(" · ")
          : "Nothing worth carrying.",
      });
      render(await getState());
    } catch (err) { busy(false); $("#err").textContent = err.message; }
    return;
  }

  if (!e.target.closest("#cp-forage")) return;

  const hours = Math.max(1, Math.min(48, Number($("#cp-h").value) || 1));
  $("#craftpanel").hidden = true;
  busy(true);
  try {
    let d = await post("/api/craftaction", { action: "forage", hours });
    busy(false);
    // The opening lands in the book at once, so the die falls inside the fiction
    // rather than in front of it.
    $("#story").insertAdjacentHTML("beforeend",
      `<p class="beat fresh">${esc(d.opening)}</p>`);
    // Counted as seen, or the full render a moment later re-runs its entrance.
    window._beatsSeen = (window._beatsSeen || 0) + 1;
    $("#story").scrollTop = $("#story").scrollHeight;
    if (d.roll) {
      // The Survival check is the player's own now — same solid, same terms as every
      // awaiting popup, but the face goes back to the excursion rather than /api/roll
      // so the tally and the closing beat still happen.
      const p = d.roll;
      const terms = p.breakdown.map(m => ({ label: m.source, value: sign(m.value) }));
      // The total row only when there is something to total: with one term the card read
      // "Str x2 +38" over "your modifier +38", the same number twice (2026-09-18, item 3).
      if (p.breakdown.length !== 1) terms.push({ label: "your modifier", value: sign(p.modifier), total: true });
      // `dc_shown` is the engine saying whether this number is a difficulty the
  // player may know or the result of a die already rolled in secret. Absent on
  // a payload from an older save mid-flight, which reads as shown — the same
  // answer it had before the flag existed.
  if (p.dc != null && p.dc_shown !== false) terms.push({ label: "beat", value: p.dc });
      // Held open, and then landed on its number before the turn is posted — the same
      // shape the table's own roll uses, and for the same reason.
      //
      // Two things were wrong here until 2026-09-17. The ask took no `hold`, so the mat
      // shut the instant the player threw and the Survival die NEVER LANDED: they wound
      // up, the die went, and the mat vanished with no number on it. That is the defect
      // reported on 2026-09-09 for the main path, still living on this one. And the
      // closing narration — a second model call, the slow half of a forage — ran before
      // anything came back, so the player watched nothing at all for the length of it.
      let face = await Dice3D.ask({
        hold: true,
        title: p.label, why: p.because || "", sides: 20, lo: 1, hi: 20, die: "1d20",
        terms,
      });
      // `null` means "the table rolls it". Ask what it shows before asking what it did:
      // the excursion's prompt is a pending roll like any other, so the same endpoint
      // answers, and it still changes nothing by answering.
      if (face == null) {
        try { face = (await post("/api/roll/face", {})).face; } catch { face = null; }
      }
      let survival = null;
      if (face != null) {
        survival = Dice3D.land({
          title: p.label, why: p.because || "", die: "1d20",
          sides: 20, lo: 1, hi: 20, result: face, terms,
        });
      }
      busy(true);
      try {
        d = await post("/api/craftaction", { face: face == null ? "auto" : face });
      } catch (err) {
        // A held mat over a dead request is a die spinning on a page that has stopped.
        Dice3D.close();
        throw err;
      } finally {
        busy(false);
      }
      // The haul is a second die, and it may not open on top of the first. The player
      // closes the Survival check when they have read it; the d100 follows.
      if (survival) await survival; else Dice3D.close();
    }
    if (d.rolls && d.rolls.length) {
      await Dice3D.land({
        title: "Foraging", why: `${d.hours} hour${d.hours === 1 ? "" : "s"} on the ground`,
        sides: 100, lo: 1, hi: 100, result: d.rolls[0],
        note: d.rolls.length > 1
          ? `The first of ${d.rolls.length} sweeps — the log has the rest.` : "",
      });
    } else if (d.checks && d.checks.length) {
      // A barren day found nothing to pick, so there is no d100 — but the Survival
      // checks were real dice, and the first of them is what lands.
      await Dice3D.land({
        title: "Foraging", why: `Survival check, DC ${d.checks[0].dc}`,
        sides: 20, result: Math.min(20, Math.max(1, d.checks[0].roll)),
        note: d.checks.length > 1
          ? `The first of ${d.checks.length} hours — none of them found a thing.` : "",
      });
    }
    render(await getState());
  } catch (err) {
    busy(false);
    $("#err").textContent = err.message;
  }
});
// The debug teleport itself. `travel` is the real op — the ground moves, and the
// scene's own clock and biome move with it.
document.addEventListener("change", async e => {
  if (!e.target.closest("#cp-biomepick")) return;
  busy(true);
  try {
    await post("/api/travel", { biome: e.target.value });
    await loadCraftActions();
    render(await getState());
  } catch (err) { $("#err").textContent = err.message; }
  finally { busy(false); }
});

document.addEventListener("input", e => {
  if (e.target.closest("#cp-h")) $("#cp-hn").textContent = e.target.value;
});

// The glossary: any named feature on the sheet answers a click with what it does.
// "there is nowhere the user can look to see what any of the blood bender abilities
// actually do" — the text was in the class data the whole time; this is the door to it.
function glossFor(name) {
  const g = (SHEET && SHEET.glossary) || {};
  let key = String(name || "").toLowerCase().replace(/\s+/g, " ").trim();
  while (key) {
    if (g[key]) return g[key];
    // The sheet's own computed feat lines answer too ("+1 AC" for Dodge).
    const feat = (SHEET.feats || []).find(f => f.name.toLowerCase() === key);
    if (feat && feat.effect) return { name: feat.name, text: feat.effect,
      source: feat.source || "feat" };
    const parts = key.split(" ");
    if (parts.length > 1 && /\d/.test(parts[parts.length - 1])) {
      key = parts.slice(0, -1).join(" ");
    } else break;
  }
  return null;
}

function glossify(name) {
  // A span the click handler recognises; names with no entry stay plain text, so a
  // dotted underline is a promise the click will be answered.
  return glossFor(name)
    ? `<span class="gloss" data-gloss="${esc(name)}">${esc(name)}</span>`
    : esc(name);
}

document.addEventListener("click", e => {
  const hit = e.target.closest("[data-gloss]");
  let card = document.getElementById("glosscard");
  if (!card) {
    card = document.createElement("div");
    card.id = "glosscard";
    document.body.appendChild(card);
  }
  if (!hit) { card.classList.remove("on"); return; }
  const entry = glossFor(hit.dataset.gloss);
  if (!entry) { card.classList.remove("on"); return; }
  card.innerHTML = `<h4>${esc(entry.name)}</h4>
    <div class="src">${esc(entry.source || "")}</div>
    <p>${esc(entry.text)}</p>`;
  card.classList.add("on");
  // Beside the click, kept on screen.
  const r = hit.getBoundingClientRect();
  card.style.left = Math.min(innerWidth - 440, Math.max(8, r.left)) + "px";
  card.style.top = Math.min(innerHeight - 160, r.bottom + 8) + "px";
});

