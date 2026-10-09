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

// The error a failed POST throws. A model that stopped answering (`gm.client.ModelStalled`)
// marks it `report`, and the page offers "Make a report" beside the sentence
// (04-combat-and-turns.js, `showStalled`).
function refusedWith(r, data) {
  const e = new Error(data.error || ("HTTP " + r.status));
  if (data.report) e.report = true;
  return e;
}

async function post(url, body) {
  // The clock this screen showed when the player acted, for `table:posted` below.
  const clockBefore = (STATE && STATE.scene) ? STATE.scene.clock_minutes : null;
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
  // The same code carries a refusal the player can fix (docs/fix-interfaces.md §2.6:
  // `{"error", "refusal": {"text", "code", "fix"}}`), handed on whole so the page can
  // offer the fix; the turn was not taken, and nothing in the box is lost.
  if (r.status === 422) {
    const e = new Error(data.hint || data.error || "");
    e.hint = true;
    if (data.refusal) e.refusal = data.refusal;
    throw e;
  }
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
  if (!r.ok) throw refusedWith(r, data);
  // This page's own POST succeeded. Dispatched before the caller renders the answer, so
  // a listener (the time-skip clock, 09-clock.js) can arm on it and fire from the render
  // hook that follows. Never on load, a resync or the other device's turn: none of those
  // pass through here. A listener that throws is reported, not raised into this turn.
  // `awaiting` says whether the answer owes a roll, for the engine device (13-device.js),
  // which shows the engine waiting on the player rather than a turn done.
  document.dispatchEvent(new CustomEvent("table:posted", {
    detail: { url, clockBefore, awaiting: !!(data && data.awaiting) } }));
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
  // What was on screen before this draw, for the render hooks below.
  const prev = STATE;
  STATE = s;
  // The shell's title bar follows the world the state is in, not the one the page was
  // opened on: the table page's picker can begin again in another campaign without a
  // reload, and the title used to be the shipped world's name typed into the template.
  if (s && typeof s.world === "string") {
    document.title = "Pathfinder GM" + (s.world ? " — " + s.world : "");
  }
  renderCombat(s);
  // The soundtrack follows the fight (music.js): battle while the scene is in an
  // encounter, the calm playlist once it has stayed over a few seconds.
  if (window.Music) {
    try { Music.mode(s && s.scene && s.scene.in_encounter ? "battle" : "ambient"); }
    catch (err) { /* music is a nicety; never the reason the table fails to draw */ }
  }
  reflectMerchant(s);
  // `fresh` marks only the beats that were not on the page a moment ago, because this
  // rebuilds the whole transcript each state: without the gate, every line re-ran its
  // ink-bleed entrance on every turn, which reads as the book flickering rather than
  // being written in.
  const seen = window._beatsSeen || 0;
  // A player beat sent with an attachment (a spell chip, docs/fix-interfaces.md §2.10)
  // shows the chip before the words, so "I cast Burning Hands." is never the only trace.
  // A place chip is drawn only beside the player's own words (play/views.py `say`):
  // "I slip out quietly." must still say where they went.
  const chips = b => (b.attachments || []).map(a =>
    `<span class="chip" data-kind="${esc(a.kind || "")}" data-id="${esc(a.id || "")}">${
      a.kind === "spell" ? `<span class="vh">Spell: </span>`
        : a.kind === "place" ? `<span class="vh">Going to: </span>` : ""}${
      esc(a.name || a.id || "")}</span> `).join("");
  $("#story").innerHTML = s.transcript.map((b, i) =>
    `<p class="beat ${b.who === "player" ? "player" : (b.kind || "")}${
      i >= seen ? " fresh" : ""}">${chips(b)}${said(b.text)}</p>`
  ).join("");
  window._beatsSeen = s.transcript.length;
  // Where the page opens is the book's (15-book.js `storyLand`, a render hook): the new
  // beat's first line at the top, and a reader rereading left alone. Sent to the foot
  // here only before that script has loaded (the page's very first draw, which the hook
  // then lands properly once the book's head is drawn).
  if (typeof storyLand !== "function") $("#story").scrollTop = $("#story").scrollHeight;

  // The character's sheet in brief, which this block drew into the side column's #sheet,
  // is drawn by 14-sides.js into the two sides of the new stage (the table rebuild,
  // docs/table-rebuild-inventory.md N1): who on the left, the numbers on the right, from
  // the same fields of `s.pc`. Its place line (geography's `where_label` and
  // `where_detail` before today's location, scale and biome) moved to the book's head
  // (15-book.js). Both are render hooks, so the first draw below reaches them once 07
  // has primed the hooks.

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

  // The lanes' hooks (07-panels.js `onRender`). Guarded because the page's first draw,
  // at the bottom of 06, runs before 07 has defined them; 07 primes every hook with the
  // state on screen once the document has loaded. Before `hold`, so a held dice mat
  // never keeps a hook from seeing the turn.
  if (typeof runRenderHooks === "function") runRenderHooks(s, prev);

  // A death the enemies' turns dealt is shown with the turn that dealt it, whichever door
  // the turn came through. Measured 2026-10-08: the combat panel's Attack and the roll
  // both ran the creatures' turns, the player died in one of them, and the death screen
  // waited for a typed line — while the panel stayed live and its next click came back
  // 409 "… is in no condition to act." `_state` carries `ended` once the campaign has.
  if (s && s.ended && typeof showDeath === "function") showDeath(s);

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
  // The tray's foot, as the approved design draws it (the mock's `.talkfoot`): a line held
  // open for the answer to either button (08's `flash`), so one arriving never moves them;
  // each person "In conversation with" and their Ignore; Take your leave last. The regard
  // bar only while the state carries a regard (the mock's recording had none, and drew the
  // row without it).
  box.innerHTML = `<p class="talksay" id="talksay" aria-live="polite"></p>` + talk.map(t => {
    const has = typeof t.regard === "number";
    const max = t.regard_max || 100;
    const pct = has ? Math.max(0, Math.min(100, Math.round(100 * t.regard / max))) : 0;
    const how = [t.attitude || "", has ? `regard ${t.regard} of ${max}` : ""].filter(Boolean);
    return `<div class="talker">
      <p class="talkwho">In conversation with <b>${esc(t.name)}</b>${
        how.length ? ` <small>${esc(how.join(", "))}</small>` : ""}</p>
      <button type="button" class="v2-btn is-quiet is-small talkignore" data-ignore="${esc(t.ref)}"
              title="Do not answer them">Ignore</button>${has ? `
      <div class="regard" role="img" aria-label="Regard ${t.regard} of ${max}"><i style="width:${
        pct}%"></i></div>` : ""}
    </div>`;
  }).join("") + `<button type="button" class="v2-btn is-quiet" id="takeleave"
      title="End the conversation">Take your leave</button>`;
}

document.addEventListener("click", async e => {
  // Cast attaches, it does not send (item 21.1): "I cast burning hands into the tree tops"
  // did nothing because this button could only aim at a person and fired at once. Now the
  // spell lands before the input as a chip (10-spells.js) and the player writes where it
  // goes, which is the one route typed and attached casts share. The sheet closes so the
  // box it went to is in view. In a fight it goes into the combat panel's turn instead,
  // beside the move (`chooseSpell`, 10-spells.js; the owner, 2026-10-01).
  const cast = e.target.closest(".castbtn");
  if (cast) {
    const went = chooseSpell({ id: cast.dataset.spell, name: cast.dataset.name,
                               range: cast.dataset.range || "" });
    if (typeof closeSheet === "function") closeSheet();
    focusAfterChoosing(went);
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
      title="${esc(a.path)}${a.tier != null ? ` · Control Blood ${a.tier}` : ""}${
        a.toggle ? (a.active ? " · ACTIVE — click to dismiss" : " · off — click to form") : ""}${
        a.choices ? " · name one: " + esc(a.choices.join(", ")) : ""}${
        a.text ? " — " + esc(a.text) : ""}">${esc(a.name)}${
        a.uses != null ? ` (${a.uses}/${a.max})` : ""}${
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

