// The play table, part 02 of 6 (state). Split out of
// play/templates/play/table.html on 2026-09-25, in the order it ran; the six
// files are classic scripts, loaded in that order, sharing one global scope.
// --- Death, and who plays next -------------------------------------------------
function showDeath(d) {
  $("#deathtitle").textContent = (STATE.pc && STATE.pc.name) ? STATE.pc.name : "Dead";
  $("#deathtext").textContent = d.death || "";
  // Death is a debt, not a wall: somebody in this world can pay for the raising.
  // First in the list on purpose — continuing the story is the headline offer,
  // rolling a new body is the fallback.
  const raise_ = d.resurrectable ? `
    <button class="pick" id="resurrectbtn">
      <b>Some weeks later&hellip;</b>
      <small>Somebody needed your strength enough to pay the priests.</small>
    </button>` : "";
  $("#deathchoices").innerHTML = raise_ + (d.choices || []).map(ch => `
    <button class="pick" data-source="${esc(ch.source)}">
      <b>${esc(ch.name)}</b>
      <small>${esc(ch.line)} · ${ch.hp} hp</small>
      ${ch.notes ? `<em>${esc(ch.notes)}</em>` : ""}
    </button>`).join("");
  const played = (d.roster || []);
  $("#deathroster").innerHTML = played.length ? `<h3>Played before</h3>` + played.map(e => `
    <div class="grave ${e.status === "dead" ? "dead" : ""}">
      <span><b>${esc(e.name)}</b> — ${esc(e.line)}</span>
      <small>${e.status === "dead" ? "died" : e.status}</small>
    </div>`).join("") : "";
  $("#deathveil").classList.add("on");
}

// The death panel's choices are `.pick` buttons too, and the one listener above already
// handles them. This file used to declare a second one here; both fired on every click,
// so picking a character to switch to also posted /api/character/new with an undefined
// source, and the 404 from that was the error the player saw.

/* --- Two views on one game ------------------------------------------------------
 *
 * The phone and the laptop are two screens on one campaign: `play/campaign.py` keeps
 * the live game in a process-global, so there is exactly one state and nothing to
 * merge. What there is, is a screen that does not know it moved — every render on this
 * page follows *this* client's own fetch, so a view that did not act never learns
 * anything happened. Act on the laptop from a scene the phone has already left, and the
 * engine applies the turn to a world that no longer matches the text you read.
 *
 * The channel carries a number and never a state. A view that is behind re-fetches
 * /api/state through the path it already uses, so there is one serialiser and one
 * render — the alternative is a second copy of the state to keep in step, which is the
 * shape CLAUDE.md's "grep for every copy of it" was written about.
 *
 * `docs/lan-play.md` is the design record; `play/concurrency.py` is the server half.
 */
// Parsed rather than pasted bare. A Django template renders a missing variable as the
// empty string, so `let REVISION = {{ revision }};` would become `let REVISION = ;` —
// a syntax error that takes the whole page down, silently, from a context key somebody
// forgot. Zero is the safe floor: it can only cause one redundant resync.
let REVISION = window.PATHFINDER_BOOT.revision;

// Three seconds. A GM turn is 10-95 s of local model, so anything faster buys nothing a
// player can perceive and costs a wake-up on a phone that is doing nothing else.
const RESYNC_MS = 3000;
let resyncing = false;

function noteRevision(r) {
  const seen = r.headers.get("X-Game-Revision");
  if (seen === null) return;
  const n = parseInt(seen, 10);
  if (!isNaN(n)) REVISION = n;
}

// Every read of the state goes through here, so the revision is recorded in exactly one
// place. A fetch that skipped it would leave this page believing it was current while
// showing something older, which is worse than not knowing at all.
async function getState() {
  const r = await fetch("/api/state", { cache: "no-store" });
  noteRevision(r);
  return readJSON(r);
}

async function resync() { render(await getState()); }

async function checkTheOtherDevice() {
  // Not while this page is hidden: a backgrounded phone is not looking, and it will
  // catch up on `visibilitychange` the moment it is. Not while a turn of our own is in
  // flight either — `busy` is up, the player is waiting on their own answer, and
  // re-rendering underneath it would replace the screen they are about to be given.
  if (resyncing || document.hidden || $("#busy").classList.contains("on")) return;
  resyncing = true;
  try {
    const r = await fetch("/api/revision", { cache: "no-store" });
    if (!r.ok) return;
    const theirs = (await readJSON(r)).revision;
    if (typeof theirs === "number" && theirs !== REVISION) await resync();
  } catch {
    // The server is gone, or saturated by a turn. Neither is this loop's business and a
    // console error every three seconds would bury the ones that matter — same
    // reasoning as `js/keepalive.js`, which has been doing this since 0.1.0.
  } finally {
    resyncing = false;
  }
}

setInterval(checkTheOtherDevice, RESYNC_MS);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) checkTheOtherDevice();
});

// Every response the page reads goes through here. A reply that is not JSON is a server
// error page, and `r.json()` on it throws "JSON.parse: unexpected character at line 1
// column 1" — which is what the player sees instead of the actual failure. Measured in
// play: that string appeared in the transcript with no way to tell what had gone wrong.
// `post` had this; eight direct `r.json()` calls did not (2026-09-25). Read the body once
// as text and decide, so a 500 reports itself as a 500 — and the 500 the server now
// answers in JSON ("it was not saved") is shown in its own words.
async function readJSON(r) {
  const raw = await r.text();
  try {
    return JSON.parse(raw);
  } catch {
    const first = raw.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim().slice(0, 160);
    throw new Error(`The server failed (HTTP ${r.status}). ${first || "No detail."}`);
  }
}

async function post(url, body) {
  const headers = {"Content-Type": "application/json", "X-CSRFToken": csrf()};
  // What this screen was drawn from. The server refuses the write if it has moved on,
  // which is the only thing standing between a stale screen and a turn taken against a
  // world that has already changed. Optional by design on the server: the forge, the
  // benches and the builders post without it and are untouched.
  headers["X-Game-Revision"] = String(REVISION);
  const r = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body || {}),
  });
  noteRevision(r);
  // A response that is not JSON is a server error page, and `r.json()` on it throws
  // "JSON.parse: unexpected character at line 1 column 1" — which is what the player
  // sees instead of the actual failure. Measured in play: that string appeared in the
  // transcript with no way to tell what had gone wrong. Read the body once as text and
  // decide, so a 500 reports itself as a 500.
  const data = await readJSON(r);
  // 422 is the table pushing a turn back across the table rather than an error: the
  // player said what the world does, which is the GM's half. The text they typed is
  // deliberately left in the box so they can rewrite it.
  if (r.status === 422) { const e = new Error(data.hint); e.hint = true; throw e; }
  if (r.status === 410) { showDeath(data); const e = new Error(""); e.handled = true; throw e; }
  // 412 and 409 are the two halves of the second-device story and they are deliberately
  // different codes, because the player has to do different things about them.
  //
  // 412 — this screen was stale. The turn was NOT taken. Catch the page up first, so
  // the sentence "take another look" is true by the time they read it.
  if (r.status === 412) {
    await resync();
    const e = new Error("Another device moved the game on. This screen has caught up — "
                        + "take another look before you act.");
    e.hint = true;
    throw e;
  }
  // 409 with `busy` — the table is mid-turn on the other device. Nothing is wrong and
  // nothing is lost; the text stays in the box. Told as a hint rather than an error for
  // the same reason 422 is: the player has not done anything wrong.
  if (r.status === 409 && data.busy) {
    const e = new Error(data.error); e.hint = true; throw e;
  }
  if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
  return data;
}

/* `hold` defers only the dice popup, not the drawing.

   Since 2026-09-16 the page renders a turn's result while the previous die's mat may
   still be open — the player closes it when they please, which was the whole point of
   landing the die early. A turn that asks for ANOTHER roll would then reset that mat
   under their eyes, mid-read, and replace the number they had just been shown. So the
   caller that knows a mat is open passes `hold` and opens the next popup itself once
   the player has closed the last one. */
function render(s, hold) {
  STATE = s;
  // The shell's title bar follows the world the state is in, not the one the page was
  // opened on: the table page's picker can begin again in another campaign without a
  // reload, and the title used to be the shipped world's name typed into the template.
  if (s && typeof s.world === "string") {
    document.title = "Pathfinder GM" + (s.world ? " — " + s.world : "");
  }
  renderCombat(s);
  reflectMerchant(s);
  // `fresh` marks only the beats that were not on the page a moment ago, because this
  // rebuilds the whole transcript each state: without the gate, every line re-ran its
  // ink-bleed entrance on every turn, which reads as the book flickering rather than
  // being written in.
  const seen = window._beatsSeen || 0;
  $("#story").innerHTML = s.transcript.map((b, i) =>
    `<p class="beat ${b.who === "player" ? "player" : (b.kind || "")}${
      i >= seen ? " fresh" : ""}">${said(b.text)}</p>`
  ).join("");
  window._beatsSeen = s.transcript.length;
  $("#story").scrollTop = $("#story").scrollHeight;

  const pc = s.pc;
  if (pc) {
    // Temporary hit points scale against hp_max, so 6 temp on a 9 hp character reads as
    // two thirds of a bar again — which is what they are worth.
    const temp = pc.temp_hp || 0;
    const pct = Math.max(0, Math.round(100 * pc.hp / pc.hp_max));
    const tpct = Math.max(0, Math.round(100 * temp / pc.hp_max));
    // Non-lethal is shown against its own threshold rather than against hp_max. The two
    // are not the same line and for a Blood Bender they are rarely close: the class buys
    // its abilities with non-lethal damage and counts temporary hit points before it
    // drops, so the number that matters moves as their wards go up and down.
    const nl = pc.nonlethal || 0;
    const nlLimit = pc.nonlethal_threshold ?? pc.hp;
    $("#sheet").innerHTML = `
      <div class="name">${esc(pc.name)}</div>
      <div class="sub">${esc(pc.heritage)} ${esc(pc.class)} · ${esc(pc.race)}</div>
      ${s.scene.biome ? `<div class="biome" title="${esc(s.scene.what_it_is || s.scene.biome_describe)}">
        ${esc(s.scene.location)}${s.scene.scale ? ` · ${esc(s.scene.scale)}` : ""} · ${
          esc(s.scene.biome)} · ${fmtClock(s.scene.clock_minutes)}</div>` : ""}
      <div class="bar"><i style="width:${pct}%"></i>${
        temp ? `<i class="temp" style="width:${tpct}%"></i>` : ""}</div>
      <div class="row"><span>Hit points</span><span>${pc.hp} / ${pc.hp_max}${
        temp ? ` <small>+${temp} temp</small>` : ""}</span></div>
      ${nl ? `<div class="row${nl >= nlLimit ? " danger" : ""}"><span>Non-lethal</span>
        <span>${nl} <small>of ${nlLimit}</small></span></div>` : ""}
      ${pc.xp ? `<div class="row"><span>Experience</span><span>${
        pc.xp.have.toLocaleString()} <small>of ${pc.xp.next.toLocaleString()}</small>${
        pc.xp.ready ? ` <small class="cd" title="Sleep to take the level">ready</small>`
                    : ""}</span></div>` : ""}
      ${(pc.needs || []).length ? `<h2>The body</h2>${pc.needs.map(n => `
        <div class="row${n.danger ? " danger" : ""}" title="${esc(n.detail)}">
          <span>${esc(n.label)}</span><span>${esc(n.state)}</span></div>`).join("")}` : ""}
      ${(pc.dr && pc.dr.length)
        ? `<div class="row"><span>Damage reduction</span><span>${
             pc.dr.map(esc).join(", ")}</span></div>` : ""}
      ${(pc.pools || []).map(p => `<div class="row"><span>${esc(title(p.id))}</span>
        <span>${p.current} <small>of ${p.max}</small>${
          p.ready ? "" : ` <small class="cd">${p.cooldown_left}r</small>`}</span></div>`).join("")}
      <div class="row"><span>Armour class</span><span>${pc.ac}</span></div>
      <h2>Abilities</h2>
      <div class="grid">${Object.entries(pc.abilities).map(([k, v]) => {
        // A 10 that used to be a 14 is not the same as a 10.
        const hurt = (pc.ability_damage || {})[k] || 0;
        return `<div class="cell${hurt ? " hurt" : ""}"><b>${k}</b><span>${v} <small>(${
          sign(Math.floor((v-10)/2))})</small></span>${
          hurt ? `<em>-${hurt}</em>` : ""}</div>`;
      }).join("")}</div>
      ${(pc.carrying && pc.carrying.length) || (s.coinage && purseTotal(pc.purse))
        ? `<h2>Carrying</h2>${
          purseTotal(pc.purse) ? `<div class="row"><span>Purse</span><span>${
            esc(purseLine(pc.purse, s.coinage))}</span></div>` : ""}${
          (pc.carrying || []).map(i => `<div class="row"><span>${esc(i.name)}</span>
            <span>${i.count}</span></div>`).join("")}` : ""}
      <!-- The satchel and the drink/throw/coat buttons used to live here. Raw material
           belongs at the bench that consumes it, and using an item belongs in the
           inventory panel where the player already goes for it: two places to do one
           thing is clutter, and the side panel is the one thing on screen every turn. -->

      ${(pc.world_classes && pc.world_classes.length) ? `<h2>World classes</h2>${
        pc.world_classes.map(w => `
          <div class="row"><span>${esc(w.name)} ${w.level}</span><span>${
            w.missing ? "<small>unknown track</small>"
            : w.to_next ? `<small>${w.to_next.need} to next</small>`
            : "<small>mastered</small>"}</span></div>
          ${w.missing ? "" : `<div class="sub" style="margin:-4px 0 8px">${
            esc(w.max_tier)} · ${w.known} recipe${w.known === 1 ? "" : "s"}</div>`}
        `).join("")}` : ""}
      <h2>Saves</h2>
      ${Object.entries(pc.saves).map(([k, v]) =>
        `<div class="row"><span>${{fort:"Fortitude",ref:"Reflex",will:"Will"}[k]}</span><span>${sign(v)}</span></div>`
      ).join("")}
      <h2>Skills</h2>
      ${Object.entries(pc.skills).map(([k, v]) =>
        `<div class="row"><span>${title(k)}</span><span>${sign(v)}</span></div>`
      ).join("")}
      <h2>Feats</h2>
      <div class="sub">${pc.feats.map(esc).join(", ")}</div>
      <button class="opensheet" id="opensheet">Full character sheet</button>
      <a class="opensheet" href="/craft/">Crafting bench</a>
      <a class="opensheet" href="/">Worlds &amp; characters</a>
      <button class="opensheet" id="openroster">Who is playing</button>`;
    $("#opensheet").onclick = openSheet;
    $("#openroster").onclick = openRoster;
  }

  // Turn order, only while a fight is on. Without it the player cannot tell whose turn
  // it is or who is still standing, which makes combat unplayable however correct the
  // maths underneath is.
  $("#order").innerHTML = s.scene.in_encounter ? `
    <h2>Round ${s.scene.round}</h2>
    ${s.scene.initiative.map(i => `
      <div class="who${i.up ? " up" : ""}${i.out ? " out" : ""}">
        <span>${i.up ? "▸ " : ""}${esc(i.name)}</span>
        <small>${i.out ? "down" : i.score}</small>
      </div>`).join("")}` : "";

  renderMap(s);
  renderSuggestions(s);
  renderAbilities(s);

  $("#board").innerHTML = s.scene.actors.map(a =>
    `<div class="who"><span>${esc(a.name)} <small>${a.ref}</small></span>
     <small>${a.hp}/${a.hp_max}${a.conditions.length ? " · " + a.conditions.join(", ") : ""}</small></div>`
  ).join("") + `<div class="sub" style="margin-top:8px">${esc(s.scene.location)}</div>`;
  renderTalk(s);

  // The crafting hub is shut while you are talking or fighting, and the button says
  // why in the engine's own words rather than letting you find out after the click.
  const craft = $("#craftaction");
  if (craft) {
    const busy = (s.scene && s.scene.busy) || "";
    craft.disabled = !!busy;
    craft.title = busy || "Forage, prospect, skin, gather, buy — every way of getting material";
    if (busy) $("#craftpanel").hidden = true;
  }

  // Behind the screen. `schemes` arrives on the state only when the GM view house rule
  // is on — the server decides, so the seams cannot leak into an ordinary session by a
  // front-end mistake. It had been arriving and going nowhere: the rule had a reader in
  // `play/views.py` and no renderer anywhere, so turning it on did nothing visible.
  renderGmView(s);

  renderRolls(s.log);

  if (hold) return;
  if (s.awaiting) showPopup(s.awaiting); else $("#veil").classList.remove("on");
}

// The conversation panel. Each person in it with the step they are at and their regard
// as a number out of a hundred — the quantified attitude the player asked for — and
// the exits: take your leave of everybody, or refuse one person who spoke to you.
function renderTalk(s) {
  const box = $("#talk");
  if (!box) return;
  const talk = (s.scene && s.scene.talk) || [];
  box.hidden = !talk.length;
  if (!talk.length) { box.innerHTML = ""; return; }
  box.innerHTML = `<div class="talkhead">In conversation</div>` + talk.map(t => {
    const pct = Math.max(0, Math.min(100, Math.round(100 * t.regard / (t.regard_max || 100))));
    return `<div class="talker">
      <div class="talkwho"><b>${esc(t.name)}</b> <small>${esc(t.attitude)} · ${t.regard} of ${
        t.regard_max || 100}</small></div>
      <div class="regard"><i style="width:${pct}%"></i></div>
      <button type="button" class="quiet talkignore" data-ignore="${esc(t.ref)}"
              title="Do not answer them">Ignore</button>
    </div>`;
  }).join("") + `<button type="button" class="quiet" id="takeleave"
      title="End the conversation">Take your leave</button>`;
}

document.addEventListener("click", async e => {
  const cast = e.target.closest(".castbtn");
  if (cast) {
    const row = cast.closest(".prep");
    const pick = row && row.querySelector(".casttarget");
    const at = pick ? pick.value : "";
    const who = pick && pick.selectedIndex > 1 ? pick.options[pick.selectedIndex].text : "";
    const label = `I cast ${cast.dataset.name}` + (at === "self" ? " on myself" :
                  who ? ` at ${who}` : "");
    cast.disabled = true;
    try {
      render(await post("/api/cast", { spell: cast.dataset.spell, at, label }));
      const sheet = $("#sheetpanel");
      if (sheet) { sheet.classList.remove("on"); sheet.setAttribute("aria-hidden", "true"); }
    } catch (err) { flash(err.message || String(err)); cast.disabled = false; }
    return;
  }
  const ignore = e.target.closest("[data-ignore]");
  if (ignore) {
    try { render(await post("/api/talk", { do: "ignore", who: ignore.dataset.ignore })); }
    catch (err) { flash(err.message || String(err)); }
    return;
  }
  if (e.target.closest("#takeleave")) {
    try { render(await post("/api/talk", { do: "leave" })); }
    catch (err) { flash(err.message || String(err)); }
  }
});

// The character's own class abilities, as buttons. Clicking one sends the turn
// directly rather than putting words in the box: the engine looks the ability up by
// name, so there is nothing for the player to phrase and nothing for the model to
// mishear. The tooltip is the author's own sentence.
function renderAbilities(s) {
  const list = s.abilities || [];
  if (!list.length) { $("#abilities").innerHTML = ""; return; }
  $("#abilities").innerHTML = `<div class="abrow-label">Your abilities</div>` +
    list.map(a => `<button class="abilitybtn${a.active ? " on" : ""}"
      data-ability="${esc(a.name)}"
      data-toggle="${a.toggle ? "1" : "0"}"
      data-free="${(a.toggle || actionKind(a.text) === "free") ? "1" : "0"}"
      title="${esc(a.path)} · Control Blood ${a.tier}${
        a.toggle ? (a.active ? " · ACTIVE — click to dismiss" : " · off — click to form") : ""}${
        a.text ? " — " + esc(a.text) : ""}">${esc(a.name)}${
        a.toggle ? (a.active ? " ●" : " ○") : ""}</button>`).join("");
}

document.addEventListener("click", async e => {
  const btn = e.target.closest("[data-ability]");
  if (!btn) return;
  const foe = (STATE.scene.actors || []).find(a => !a.is_pc && a.hp > 0);
  const name = btn.dataset.ability;

  // A free action does not cost you the round. Forming the armament went through the
  // spoken-turn path, which ends the turn and runs every NPC after it — so a free
  // action handed the bear a swing. Toggles and free actions go straight to the engine
  // with the turn left open; everything else is a turn as it always was.
  // In a fight or out of one: a free action goes straight to the engine either way.
  // The out-of-combat branch used to fall through to the spoken path, which cost a
  // whole narrated turn, let the model reinvent the toggle as a Knowledge (Arcana)
  // check, and let an advance_time ride along — a free action spending an afternoon.
  if (btn.dataset.free === "1") {
    busy(true);
    try {
      render(await post("/api/combat/act", {
        actions: [{ op: "use_ability", params: { ability: name },
                    target: foe ? foe.ref : null }],
        label: `free: ${name}`, end_turn: false }));
    } catch (err) { $("#err").textContent = err.message; }
    finally { busy(false); }
    return;
  }
  // Who, if anyone, this is aimed at. `foe` is "the first actor that is not the player
  // and is still standing" — there is no hostility on the actor payload to test — so
  // out of a fight it is whoever happens to be in the scene, and a toggle that arms
  // your own body came out as an act against them. Measured on a quiet step in
  // Zhilvarnia: forming the blood armament sent "I use Extracorporeal Blood Armament on
  // the stranger sharing the step", and the narrator wrote it exactly as it read — the
  // stranger flinched from a claw held inches from their face and nearly bolted.
  //
  // So: nobody is named outside a fight, because outside a fight there is no foe; and a
  // toggle never names anybody, because entering a stance is not something you do to a
  // person. Inside a fight an ordinary ability aims as it always did.
  const fighting = !!(STATE.scene && STATE.scene.in_encounter);
  const aimed = (fighting && btn.dataset.toggle !== "1" && foe) ? ` on ${foe.name}` : "";
  takeTurn({ text: `I use ${name}${aimed}.` }, false);
});

