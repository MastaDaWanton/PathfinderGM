// Book and ledger: the table. The story with its ruled margin, the rail (where you are, who is
// here, how your body is), the conversation, and the dock that answers.
"use strict";

// --- Places and exits (play/exits.py, in data.js) ------------------------------------------------
const place = () => D.places[S.place];
const exitsHere = () => (S.wanted ? place().wanted : place().exits);
const reason = i => (i >= 0 ? D.reasons[i].replace("{pc}", sheet().identity.name) : "");
const GROUPS = [["n", "Next door"], ["o", "Outside"], ["r", "Roads"]];
// The engine's time words, turned into the mock clock's minutes.
const MINUTES = { "a few minutes' walk": 5, "a quarter of an hour": 15, "about five days on foot": 7200 };
const walkWords = w => String(w || "").replace(/(?:'s|') walk$/, "");

// The people the recording saw at the gate. Attitude is an EXAMPLE: the recording has none.
const ATTITUDE = { c9: "indifferent", c10: "indifferent" };

// --- The story -------------------------------------------------------------------------------------
let beatSeq = 0;
function beat(kind, text, slips = [], extra = {}) {
  // Each of your turns is dated in the margin, the ledger's own date column, so reading back
  // says when a thing was done without opening the journal.
  const at = kind === "you" ? hhmm(S.minutes) + (S.day > 1 ? `, day ${S.day}` : "") : "";
  return { id: "b" + (++beatSeq), kind, text, slips, at, ...extra };
}
function placeBeat(id) {
  const p = D.places[id];
  const where = p.setting === "outside" ? `Outside Zhilvarnia, ${p.ground} ground`
    : `Zhilvarnia, a city. ${upper(p.ground)} ground`;
  return beat("place", p.name, [], { where });
}

function slipHTML(s) {
  if (s.type === "roll") {
    const nat = s.natural === 20 ? " nat20" : s.natural === 1 ? " nat1" : "";
    const terms = (s.terms || []).map(t =>
      `<li><span>${esc(upper(tidy(t.source)))}</span><span>${signed(t.value)}</span></li>`).join("");
    const verdict = s.verdict ? `<em class="${s.good ? "good" : "bad"}">${esc(s.verdict)}</em>` : "";
    return `<div class="slip roll"><h4><span>${esc(s.label)}</span>${verdict}</h4>
      <div class="sum"><span class="k">${esc(s.die)}</span>
        ${(s.faces || []).map(f => `<span class="die${nat}">${f}</span>`).join("")}
        <span class="tot">${s.total}</span></div>
      ${terms ? `<ul>${terms}</ul>` : ""}
      ${s.vs ? `<div class="vs"><ul><li><span>Against ${esc(s.vs.what || "")}</span><span>${s.vs.value}</span></li></ul>
        ${s.vs.explain ? `<span class="k">${esc(upper(s.vs.explain))}</span>` : ""}</div>` : ""}</div>`;
  }
  if (s.type === "time") {
    return `<div class="slip time"><h4><span>Time</span><span>${esc(s.to)}</span></h4>
      <span class="k">from ${esc(s.from)}, ${esc(s.words)}</span></div>`;
  }
  if (s.type === "move") {
    return `<div class="slip move"><h4><span>Moved</span></h4>
      <span>${esc(upper(s.from))} to ${esc(s.to)}</span></div>`;
  }
  if (s.type === "xp") {
    return `<div class="slip"><h4><span>Experience</span><em class="good">+${s.gain}</em></h4>
      <span class="k">${s.have} of ${s.next.toLocaleString()} for level 2</span></div>`;
  }
  if (s.type === "said") {
    return `<div class="slip"><h4><span>Said</span><span>${s.n} line${s.n > 1 ? "s" : ""}</span></h4>
      <span class="k">${esc(upper(s.who))}, kept in the Journal</span></div>`;
  }
  if (s.type === "cast") {
    return `<div class="slip"><h4><span>${esc(s.name)}</span><em class="${s.slot ? "bad" : "good"}">${
      s.slot ? "slot spent" : "at will"}</em></h4>
      <span class="k">${esc(s.detail)}</span></div>`;
  }
  // A plain engine line: a tell, a refusal, a condition.
  return `<div class="slip"><h4><span>${esc(s.title || "Rules")}</span>${
    s.verdict ? `<em class="${s.good ? "good" : "bad"}">${esc(s.verdict)}</em>` : ""}</h4>
    <span class="k">${esc(tidy(s.text))}</span></div>`;
}

function beatHTML(b) {
  const gloss = `<aside class="gloss" aria-label="What the rules did">${
    b.at ? `<time class="stamp">${esc(b.at)}</time>` : ""}${b.slips.map(slipHTML).join("")}</aside>`;
  if (b.kind === "place") {
    return `<article class="beat place" id="${b.id}">${gloss}<div class="prose"><header class="placehead">
      <h1>${esc(upper(b.text))}</h1><p>${esc(b.where)}</p></header></div></article>`;
  }
  if (b.kind === "you") {
    return `<article class="beat you" id="${b.id}">${gloss}<div class="prose"><p><b>${
      b.say ? "You say" : "You"}</b>${esc(b.say ? `“${b.text}”` : b.text)}</p></div></article>`;
  }
  if (b.kind === "oc") {
    return `<article class="beat oc" id="${b.id}">${gloss}<div class="prose"><p>${esc(b.text)}</p></div></article>`;
  }
  if (b.kind === "writing") {
    return `<article class="beat oc writing" id="${b.id}">${gloss}<div class="prose"><p>${esc(b.text)}</p></div></article>`;
  }
  return `<article class="beat gm" id="${b.id}">${gloss}<div class="prose">${
    tidy(b.text).split(/\n\n+/).map(p => `<p>${esc(p)}</p>`).join("")}</div></article>`;
}

function renderStory() {
  $("#beats").innerHTML = S.beats.map(beatHTML).join("");
}
// A new beat lands with its TOP at the top of the page, not scrolled to the bottom: a long
// paragraph is read from its first line. If the reader has scrolled back, nothing moves under
// them; a button says there is more (BG3's log was criticised for yanking readers down).
function addBeats(list, { reading = true } = {}) {
  const box = $("#beats");
  const nearEnd = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
  list.forEach(b => {
    S.beats.push(b);
    box.insertAdjacentHTML("beforeend", beatHTML(b));
    box.lastElementChild.classList.add("new");
  });
  paintIcons(box);
  const first = document.getElementById(list[0].id);
  if (!reading) return;
  if (nearEnd || !S.readingBack) {
    box.scrollTop = Math.max(0, first.offsetTop - 16);
    $("#newbelow").hidden = true;
  } else {
    $("#newbelow").hidden = false;
    $("#newbelow").dataset.to = list[0].id;
  }
}
$("#beats").addEventListener("scroll", () => {
  const box = $("#beats");
  S.readingBack = box.scrollHeight - box.scrollTop - box.clientHeight > 240;
  if (!S.readingBack) $("#newbelow").hidden = true;
});
$("#newbelow").addEventListener("click", () => {
  const t = document.getElementById($("#newbelow").dataset.to);
  if (t) $("#beats").scrollTop = t.offsetTop - 16;
  $("#newbelow").hidden = true;
});

// The pacing of a local model is designed for, not hidden: the rules answer at once, in the
// margin, and the page says the GM is writing while the prose is slow to come.
function gmWrites(slips, line) {
  const w = beat("writing", "The GM is writing. The rules have already answered, in the margin.", slips);
  addBeats([w]);
  setTimeout(() => {
    const el = document.getElementById(w.id);
    const i = S.beats.indexOf(w);
    const done = beat("oc", line, slips);
    if (i >= 0) S.beats[i] = done;
    if (el) el.outerHTML = beatHTML(done);
    paintIcons($("#beats"));
  }, 1100);
}

// --- The rail: where you are -----------------------------------------------------------------------
function railHead(title) {
  return `<div class="railclose"><b>${esc(title)}</b>
    <button type="button" class="btn small quiet" data-rail-close>Close</button></div>`;
}
function renderRail() {
  if (S.scene === "fight") { renderFightRail(); return; }
  const rows = exitsHere();
  const groups = GROUPS.map(([g, label]) => {
    const mine = rows.filter(r => r[2] === g);
    if (!mine.length) return "";
    // Five doors all "a few minutes" away said it five times; a group sharing one time says
    // it once, beside the group's name (the first mock's measure, kept).
    const shared = mine.length > 1 && mine.every(r => r[3] === mine[0][3]) ? walkWords(mine[0][3]) : "";
    return `<div class="exgroup"><h3><span>${label}</span>${shared ? `<small>${esc(shared)} each</small>` : ""}</h3>
      <div class="exits">${mine.map(r => {
        const [id, name, , time, why, journey] = r;
        const shut = why >= 0;
        return `<button type="button" class="exit${shut ? " shut" : ""}${journey ? " journey" : ""}"
          data-exit="${esc(id)}" aria-expanded="${shut ? String(S.why === id) : "false"}"${
          shut ? ` aria-describedby="why-${esc(id)}"` : ""}>
          <b>${esc(name)}</b><span>${shut ? "shut" : shared ? "" : esc(walkWords(time))}</span></button>${
          shut && S.why === id ? `<p class="shutwhy" id="why-${esc(id)}">${esc(reason(why))}</p>` : ""}`;
      }).join("")}</div></div>`;
  }).join("");

  const people = D.people[S.place] || [];
  const talk = S.talk;
  const peopleHTML = people.length ? people.map(x => `<div class="person">
      <b>The ${esc(x.name)}</b><span class="att">${esc(ATTITUDE[x.ref] || "")}</span>
      <p>${esc(x.face)}</p>
      <div class="talkacts" style="grid-column:1/-1">
        <button type="button" class="btn small" data-talk="${esc(x.ref)}"${talk ? " disabled" : ""}>Talk</button>
        <button type="button" class="btn small quiet" data-fill="I look the ${esc(x.name)} over.">Look</button>
      </div></div>`).join("")
    : `<p class="railnote">Nobody here the rules are tracking. Anyone the story brings in
        appears here with their face.</p>`;

  const needs = sheet().needs.map(n => `<button type="button" class="need${n.danger ? " danger" : ""}"
      data-why="${whyKey(n.label, { total: n.state, terms: [] }, n.detail)}"><b>${esc(n.label)}</b>
      <span>${esc(n.state.replace(" of grace left", " left"))}</span></button>`).join("");

  $("#rail").innerHTML = `${railHead("Here")}
    ${talk ? talkHTML() : ""}
    <section aria-labelledby="h-from"><h2 id="h-from">From here <small>${esc(upper(place().name))}</small></h2>
      ${groups}</section>
    <section aria-labelledby="h-people"><h2 id="h-people">People here</h2>${peopleHTML}</section>
    <section aria-labelledby="h-body"><h2 id="h-body">Your body</h2>
      <div class="needs">${needs}</div>
      <p class="railnote">${sheet().conditions.length ? esc(sheet().conditions.join(", "))
        : "No conditions. Nothing is wearing on you yet."}</p></section>`;
  $("#herebtn").textContent = `Here: ${rows.filter(r => r[4] < 0).length} ways`;
}

// --- The conversation: speech only, sticky until you leave it (ruling 2026-09-24) ----------------
function talkHTML() {
  const t = S.talk;
  if (!t.open) {
    return `<section class="talk"><div class="talkhead"><b>Talking with the ${esc(t.name)}</b>
      <button type="button" class="btn small" data-talk-open>Open</button></div></section>`;
  }
  return `<section class="talk" aria-labelledby="h-talk">
    <div class="talkhead"><h2 id="h-talk">Talking with the ${esc(t.name)}</h2>
      <button type="button" class="btn small quiet" data-talk-hide>Hide</button></div>
    <div class="regard" data-why="${whyKey("Regard", { total: `${t.regard} of 100`, terms: [] },
      "Example value. The engine keeps a 0 to 100 regard per person, with a devoted step.")}">
      <span>Regard</span><i style="--w:${t.regard}%"></i><span>${esc(t.att)}</span></div>
    <div class="talklog" id="talklog">${t.lines.map(l => `<p class="line${l.mine ? " mine" : ""}${l.oc ? " oc" : ""}">
      <b>${l.mine ? "You" : l.oc ? "Mock" : "The " + esc(t.name)}</b>${esc(tidy(l.text))}</p>`).join("")}</div>
    <div class="talkacts">
      <button type="button" class="btn small" data-talk-ignore>Ignore</button>
      <button type="button" class="btn small" data-talk-leave>Take your leave</button>
    </div></section>`;
}
function startTalk(ref) {
  const p = (D.people[S.place] || []).find(x => x.ref === ref);
  if (!p) return;
  const opening = D.said.filter(s => s.who === "the " + p.name).map(s => ({ text: s.line }));
  S.talk = { ref, name: p.name, open: true, regard: 50, att: ATTITUDE[ref] || "indifferent",
             lines: opening.length ? opening : [{ text: "(Nothing said yet.)" }] };
  renderRail(); renderDock(); openRail(true);
  $("#pen").focus();
}
function endTalk(how) {
  const name = S.talk.name;
  S.talk = null;
  addBeats([beat("oc", how === "ignore"
    ? `Mock. You turn from the ${name} without answering. The conversation ends, and the rules note that you ignored them.`
    : `Mock. You take your leave of the ${name}. The conversation ends on your word, free of any roll.`,
    [{ title: "Conversation", text: how === "ignore" ? `Ignored the ${name}` : `Left the ${name}` }])]);
  renderRail(); renderDock();
}

// --- The dock ----------------------------------------------------------------------------------------
function currentSuggestions() {
  if (S.scene === "fight") return S.fight ? D.fight.suggestions : [];
  return S.place === D.start && !S.talk ? D.suggestions : [];
}
function renderDock() {
  const fight = S.scene === "fight";
  $("#dock-combat").hidden = !fight;
  if (fight) renderCombatDock();
  const sug = currentSuggestions();
  $("#suggest").hidden = !sug.length;
  $("#suggest").innerHTML = `<span class="lab">Suggested</span><div class="list">${sug.map(t =>
    `<button type="button" class="sugg" data-fill="${esc(t)}">${esc(t)}</button>`).join("")}</div>`;
  const att = S.attached;
  $("#attached").hidden = !att;
  $("#attached").innerHTML = att ? `<div class="row"><span class="chipbtn">${glyph(SPELL_ICON[att] || "lorc-potion-ball", "spells")}
      Cast ${esc(D.spells[att].name)}<button type="button" class="x" data-detach aria-label="Take ${esc(D.spells[att].name)} off the turn">&times;</button></span></div>` : "";
  const talking = !!S.talk;
  $("#pen").placeholder = talking ? `Say something to the ${S.talk.name}`
    : fight ? "Add words for the GM, or describe what you do" : S.sayMode ? "What do you say?" : "What do you do?";
  $("#act").textContent = talking || S.sayMode ? "Say" : fight ? "Add" : "Act";
  $("#say").setAttribute("aria-pressed", String(!!S.sayMode));
  $("#say").hidden = talking;
  $("#cast").hidden = !isCaster();
  $("#craft").hidden = fight;
  $("#trade").hidden = fight;
  renderCarried();
  paintIcons($("#dock"));
}
// The balance carried forward at the foot of the ledger leaf. Only where the leaf is shown
// (the CSS hides it when the margin folds away); the bar carries the same facts everywhere.
function renderCarried() {
  const el = $("#carried");
  if (!el) return;
  const s = sheet();
  el.hidden = S.scene === "fight";
  el.innerHTML = `<h4>Carried forward</h4><ul>
    <li><span>Day ${S.day}</span><span>${hhmm(S.minutes)}</span></li>
    <li><span>Life</span><span>${s.hp.current} / ${s.hp.max}</span></li>
    <li><span>Purse, gold</span><span>${(me().purse / 100).toFixed(2)}</span></li></ul>`;
}
// Wrap the desk buttons in the lane's second column once.
(function laneDesk() {
  const row = $("#deskrow");
  const kids = Array.from(row.children);
  const wrap = document.createElement("div"); wrap.className = "row";
  kids.forEach(k => wrap.appendChild(k));
  row.appendChild(wrap);
})();

function autosize() {
  const t = $("#pen");
  t.style.height = "auto";
  t.style.height = Math.min(t.scrollHeight + 2, window.innerHeight * .3) + "px";
}
$("#pen").addEventListener("input", autosize);
$("#pen").addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#dock").requestSubmit(); }
});

$("#dock").addEventListener("submit", e => {
  e.preventDefault();
  const pen = $("#pen");
  const text = pen.value.trim();
  if (S.scene === "fight") { fightWords(text); pen.value = ""; autosize(); return; }
  if (!text && !S.attached) { pen.focus(); return; }
  if (S.talk) {
    S.talk.lines.push({ mine: true, text });
    S.talk.lines.push({ oc: true, text: `The ${S.talk.name}'s answer would be written here, in their own voice.` });
    pen.value = ""; autosize(); renderRail();
    const log = $("#talklog"); if (log) log.scrollTop = log.scrollHeight;
    return;
  }
  const slips = [];
  let words = text;
  if (S.attached) {
    const sp = D.spells[S.attached];
    const lvl = sp.level;
    if (lvl > 0) me().caster.spent[lvl] = (me().caster.spent[lvl] || 0) + 1;
    slips.push({ type: "cast", name: sp.name, slot: lvl > 0,
                 detail: `${sp.casting_time}, ${sp.range}${lvl > 0 ? `; ${slotsLeft(lvl)} of level ${lvl} left today` : ""}` });
    if (!words) words = `I cast ${sp.name}.`;
    S.attached = null;
  }
  addBeats([beat("you", words, [], { say: !!S.sayMode })]);
  gmWrites(slips.concat([advance(1, "a moment")]),
    "Mock. The GM would propose what this calls for, the engine would roll it in the margin, and the narrator would write the beat here.");
  pen.value = ""; autosize(); renderDock();
});

$("#say").addEventListener("click", () => {
  S.sayMode = !S.sayMode; renderDock(); $("#pen").focus();
});
$("#continue").addEventListener("click", () => {
  if (S.scene === "fight") { endTurn(true); return; }
  // Ruling 2026-09-18: Continue keeps the PC's standing action and moves the world a beat.
  addBeats([beat("you", "Continue", [], {})]);
  gmWrites([advance(10, "a beat passes")], "Mock. You keep doing what you were doing. The world moves a beat: " +
    "the people here act on their own, and the narrator writes what changed.");
});

// Suggestions and small "fill" buttons fill the pen; they never send.
document.addEventListener("click", e => {
  const f = e.target.closest("[data-fill]");
  if (!f) return;
  const pen = $("#pen");
  pen.value = f.dataset.fill; autosize(); pen.focus();
  pen.setSelectionRange(pen.value.length, pen.value.length);
  openRail(false);
});

// --- Craft action: every way of getting material, where you stand -----------------------------------
const CRAFT = [
  ["Forage", "Herbalist", "Search the ground for herbs and roots", "urban forest coast plains hills"],
  ["Prospect", "Miner", "Look for ore and stone worth working", "hills mountains coast"],
  ["Gather wood", "Carpenter", "Cut and carry timber", "forest"],
  ["Scavenge", "Tinker", "Pick through what others threw away", "urban"],
  ["Skin", "Hunter", "Needs a carcass here, and there is none", ""],
];
function renderCraft() {
  const ground = place().ground;
  $("#pop-craft").innerHTML = `<h3><span>Craft action</span>
      <button type="button" class="btn small quiet" data-close-pop>Close</button></h3>
    <p>Where you stand: ${esc(ground)} ground, ${esc(place().name)}. Mock: the real list is each
      craft's own declaration for this ground.</p>
    <div class="range"><label for="craft-h">Hours</label>
      <input type="range" id="craft-h" min="1" max="48" value="2"><b id="craft-hn">2 hours</b></div>
    <div class="optgrid">${CRAFT.map(([name, by, what, where]) => {
      const ok = where.split(" ").includes(ground);
      return `<button type="button" class="opt" data-craft="${esc(name)}"${ok ? "" : " disabled"}>
        <b>${esc(name)}</b><small>${esc(by)}. ${esc(ok ? what : where ? `Not on ${ground} ground` : what)}</small></button>`;
    }).join("")}</div>`;
}
$("#craft").addEventListener("click", () => togglePop("craft"));
function togglePop(which) {
  const pop = $("#pop-" + which), btn = $("#" + which);
  const open = pop ? pop.hidden : false;
  $$(".pop").forEach(p => { p.hidden = true; });
  $$("#craft, #cast").forEach(b => b.setAttribute("aria-expanded", "false"));
  if (!pop || !open) return;
  if (which === "craft") renderCraft(); else renderCastPop();
  pop.hidden = false; btn.setAttribute("aria-expanded", "true");
  paintIcons(pop);
  const first = pop.querySelector("button:not([disabled]):not([data-close-pop]), input");
  if (first) first.focus();
}
document.addEventListener("input", e => {
  if (e.target.id === "craft-h") {
    const h = +e.target.value;
    $("#craft-hn").textContent = `${h} hour${h > 1 ? "s" : ""}`;
  }
});
document.addEventListener("click", e => {
  if (e.target.closest("[data-close-pop]")) { togglePop("none"); return; }
  const c = e.target.closest("[data-craft]");
  if (c) {
    const h = +$("#craft-h").value;
    togglePop("none");
    addBeats([beat("you", `${c.dataset.craft}, for ${h} hour${h > 1 ? "s" : ""}.`)]);
    gmWrites([advance(h * 60, `${h} hour${h > 1 ? "s" : ""} of ${c.dataset.craft.toLowerCase()}`),
              { title: c.dataset.craft, text: "Example: the engine rolls the craft's check and says what was found." }],
      "Mock. What you found would be counted into your pack, and the narrator would write the finding.");
  }
  if (!e.target.closest(".pop, #craft, #cast")) {
    if ($$(".pop").some(p => !p.hidden)) togglePop("none");
  }
});

// --- Cast: a spell attaches to the turn as a chip; it is never sent on its own ------------------------
function slotsLeft(lvl) {
  const c = me().caster;
  const pool = sheet().pools.find(p => p.id === "spell slot " + lvl);
  return (pool ? pool.max : 0) - (c.spent[lvl] || 0);
}
function renderCastPop() {
  const c = me().caster;
  const rows = [0, 1].map(lvl => {
    const list = c.prepared[lvl] || [];
    const left = lvl ? slotsLeft(lvl) : Infinity;
    return `<p class="grouplab">${lvl ? `Level ${lvl}: ${left} of ${sheet().pools.find(p => p.id === "spell slot 1").max} left today`
      : "Cantrips, at will"}</p><div class="optgrid">${list.map(id => {
        const sp = D.spells[id];
        return `<button type="button" class="opt withicon" data-attach="${esc(id)}"${left <= 0 ? " disabled" : ""}>
          ${glyph(SPELL_ICON[id], "spells")}<b>${esc(sp.name)}</b>
          <small>${esc(sp.range.replace(/ \(.*\)/, ""))}${sp.saving_throw && sp.saving_throw !== "none" ? `, ${esc(sp.saving_throw)} DC ${c.dcBase + lvl}` : ""}</small></button>`;
      }).join("")}</div>`;
  }).join("");
  $("#pop-cast").innerHTML = `<h3><span>Cast</span>
      <button type="button" class="btn small quiet" data-close-pop>Close</button></h3>
    <p>The spell joins your turn as a chip under the pen. Add words if you like, then act.</p>${rows}`;
}
$("#cast").addEventListener("click", () => togglePop("cast"));
document.addEventListener("click", e => {
  const a = e.target.closest("[data-attach]");
  if (a) {
    S.attached = a.dataset.attach;
    togglePop("none");
    if (S.mode !== "table") setMode("table");
    renderDock();
    if (S.scene === "fight") { addToPlan({ kind: "cast", spell: a.dataset.attach }); }
    $("#pen").focus();
  }
  if (e.target.closest("[data-detach]")) {
    if (S.scene === "fight") removeFromPlan("cast");
    S.attached = null; renderDock();
  }
});

// --- Trade: only where somebody keeps a counter ---------------------------------------------------
const COUNTERS = { "the market": "market", "the merchants row": "smithy" };
$("#trade").addEventListener("click", () => {
  const here = COUNTERS[place().name];
  if (here) { openTrade(here); return; }
  const near = exitsHere().filter(r => COUNTERS[r[1]] && r[4] < 0);
  toast(near.length ? `Nobody here keeps a counter. ${upper(near[0][1])} is next door, ${walkWords(near[0][3])}.`
    : "Nobody here keeps a counter.");
});

// --- Walking ------------------------------------------------------------------------------------------
function walk(row) {
  const [id, name, , time] = row;
  const from = place().name;
  S.place = id; S.why = null; S.talk = null;
  addBeats([beat("you", `I go to ${name}.`),
            placeBeat(id),
            beat("oc", `Mock. The narrator's beat for the walk and the arrival would follow here. The ways on are the engine's own for ${name}.`,
                 [{ type: "move", from, to: name }, advance(MINUTES[time] || 5, walkWords(time))])]);
  renderRail(); renderDock(); openRail(false);
}
function journey(row) {
  const dlg = $("#journey");
  dlg.innerHTML = `<h2>Set out for ${esc(row[1].replace(/^the road to /, ""))}?</h2>
    <p>${esc(upper(row[3]))}. The days pass on the road: the engine charges food and water as
      you go and rolls what the road brings. You arrive on day ${S.day + 5}.</p>
    <div class="acts"><button type="button" class="btn quiet" value="no" data-dlg-close>Not now</button>
      <button type="button" class="btn primary" data-setout="${esc(row[0])}">Set out</button></div>`;
  dlg.showModal();
}
document.addEventListener("click", e => {
  const x = e.target.closest("[data-exit]");
  if (x) {
    const row = exitsHere().find(r => r[0] === x.dataset.exit);
    if (!row) return;
    if (S.scene === "fight") { withdraw(row); return; }
    if (row[4] >= 0) { S.why = S.why === row[0] ? null : row[0]; renderRail(); return; }
    if (row[5]) { journey(row); return; }
    walk(row);
    return;
  }
  const so = e.target.closest("[data-setout]");
  if (so) {
    $("#journey").close();
    const row = exitsHere().find(r => r[0] === so.dataset.setout);
    const dest = row[1].replace(/^the road to /, "");
    addBeats([beat("you", `I set out for ${dest}.`),
      beat("oc", `Mock. Five days on the road. The engine would charge rations and water each day and roll the road's encounters; the story would pick up at ${dest}. The mock stays in Zhilvarnia.`,
        [{ type: "move", from: place().name, to: `the road to ${dest}` }, advance(7200, "about five days on foot")])]);
    return;
  }
  if (e.target.closest("[data-dlg-close]")) e.target.closest("dialog").close();
  const t = e.target.closest("[data-talk]");
  if (t) startTalk(t.dataset.talk);
  if (e.target.closest("[data-talk-hide]")) { S.talk.open = false; renderRail(); }
  if (e.target.closest("[data-talk-open]")) { S.talk.open = true; renderRail(); }
  if (e.target.closest("[data-talk-ignore]")) endTalk("ignore");
  if (e.target.closest("[data-talk-leave]")) endTalk("leave");
  if (e.target.closest("[data-rail-close]")) openRail(false);
});

// --- The rail as a sheet on a phone -----------------------------------------------------------------
function openRail(on) {
  if (window.innerWidth >= 860) return;
  document.body.classList.toggle("rail-open", on);
  $("#herebtn").setAttribute("aria-expanded", String(on));
}
$("#herebtn").addEventListener("click", () => openRail(!document.body.classList.contains("rail-open")));

// --- Mock controls -------------------------------------------------------------------------------------
function resetTable() {
  S.scene = "explore"; S.fight = null; S.talk = null; S.attached = null; S.place = D.start;
  S.minutes = 8 * 60 + 10; S.day = 1; S.why = null;
  document.body.classList.remove("scene-fight"); document.body.classList.add("scene-explore");
  $("#ribbon").hidden = true;
  const smith = D.transcript;
  S.beats = [
    beat("you", smith[0].text, [], { at: "07:52" }),
    beat("gm", smith[1].text, [{ type: "said", who: "the smith", n: 4 }]),
    beat("you", smith[2].text, [], { at: "08:04" }),
    placeBeat(D.start),
    beat("gm", smith[3].text, [{ type: "move", from: "the merchants row", to: "the gate" },
      { type: "time", from: "08:04", to: "08:10", words: "a few minutes' walk" }]),
  ];
  renderClock(); renderBar(); renderStory(); renderRail(); renderDock();
  const box = $("#beats");
  requestAnimationFrame(() => { box.scrollTop = box.scrollHeight; });
}
$("#mock-reset").addEventListener("click", () => { $("#pagemenu").open = false; resetTable(); setMode("table"); });
$("#mock-wanted").addEventListener("change", e => { S.wanted = e.target.checked; renderRail(); });
$("#mock-talk").addEventListener("click", () => {
  $("#pagemenu").open = false;
  if (S.scene === "fight" || S.place !== D.start) resetTable();
  setMode("table"); startTalk("c9");
});
$("#mock-trade").addEventListener("click", () => { $("#pagemenu").open = false; setMode("table"); openTrade("market"); });
// The mock's character switch: in the bar on wide screens, and at the head of the Character
// and Spells views everywhere, so a phone can see both characters too.
document.addEventListener("click", e => {
  const b = e.target.closest(".playing [data-char]");
  if (!b || b.dataset.char === S.char) return;
  S.char = b.dataset.char; S.attached = null;
  if (S.fight) {
    const pc = S.fight.people.pc;
    pc.name = sheet().identity.name; pc.hp = sheet().hp.current; pc.hp_max = sheet().hp.max;
    S.fight.plan = []; S.fight.hint = "";
  }
  renderBar(); renderRail(); renderDock();
  if (S.scene === "fight") renderFight();
  if (S.mode === "spells" && !isCaster()) setMode("table"); else setMode(S.mode);
  toast(`Mock. Playing ${sheet().identity.name}.`);
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape") { togglePop("none"); openRail(false); }
});
