// The play table, part 08 of 10 (conversation). Classic script, sharing one global scope
// with 01-07, 09 and 10.
//
// What was said, per person, in a tray of its own (docs/design-f-ui.md §4.2; owner Q42,
// 2026-09-28: "it should be openable and closeable while the buttons to ignore or leave
// conversation should be there as well. It should be removed from the panel."). Since the
// table rebuild the tray takes the right side's column (its own column with the sheet
// hidden, the whole stage on a phone), opened and closed by Talk in the top bar, which
// keeps the id the old left-edge TALK tab had (#talktab) so this file reads it as before.
//
// - The log is `scene.conversation` (the last 80 entries round the people here) plus
//   whatever `GET /api/conversation` has paged in; entries are keyed by their `n`, which
//   the server never reuses, so a page and a turn can be merged without duplicates.
// - Only quoted speech and vocalisations are in it (owner Q43, Q44): the server's
//   `play/aftermath/conversation_log.py` decides that, and this file only draws it.
// - Ignore and Take your leave (#talk, drawn by 02's `renderTalk`) sit below the log's
//   scroll region, never inside it: Disco Elysium's log held its live choices, and
//   scrolling back left players unable to reach them.
// - A conversation starting never opens the tray by itself, at any width: the TALK tab
//   counts the new lines instead ("Conversation, 2 new"). The phone rule is the owner's
//   (G0 Q7); the desktop followed from measuring it. Docked at 1440x900 the story's left
//   margin is 273px against a 400px tray, so it covered the beat about to be read; with
//   the column hidden it cleared the story (448px) but lay over the first 350px of the
//   say box, where the player's words were being typed.
// - Nothing moves on its own: the log follows new lines only when the reader was already
//   at the foot, and says so with "Go to the latest line" when they were not.

const CONVO_KEY = "pgm.table.convo.v1";
const CONVO = {
  game: null,            // which campaign the cache is for (world and character)
  seq: 0,
  entries: new Map(),    // n -> Entry
  people: [],            // scene.conversation.people, as last drawn
  pick: null,            // "all" or a ref the viewer chose; null follows the conversation
  done: new Set(),       // views whose earliest lines have been paged in
  seen: null,            // the newest n this viewer has had on screen
  newBelow: false,       // lines arrived while the reader was scrolled up
  drawn: { people: "", log: "" },   // what was last written, compared as written
};

const talkTray = () => document.getElementById("talktray");
const talkIsOpen = () => { const t = talkTray(); return !!(t && t.classList.contains("on")); };

// Ignore and Take your leave report a failure through `flash`, which 02 has called since
// 2026-09-24 and nothing ever defined: a refused Ignore threw a ReferenceError and the
// player saw nothing at all.
function flash(message) {
  const err = document.getElementById("err");
  if (err) {
    err.textContent = String(message || "");
    err.className = "";
  }
  // And in the tray's own line above the two buttons, held open for it, where the player
  // who pressed one is looking: on a phone the tray covers the desk and #err with it.
  const line = document.getElementById("talksay");
  if (line) line.textContent = String(message || "");
}

function convoGame(s) {
  return `${(s && s.world) || ""}|${(s && s.pc && s.pc.name) || ""}`;
}

// The newest line this viewer has seen, per campaign. Storage throws in a private window;
// then every line is simply new once, which is the harmless way to be wrong.
function convoReadSeen(game) {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(CONVO_KEY) || "null"); } catch { saved = null; }
  const n = saved && saved.seen && saved.seen[game];
  return typeof n === "number" ? n : null;
}

function convoWriteSeen(game, n) {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(CONVO_KEY) || "null"); } catch { saved = null; }
  if (!saved || typeof saved !== "object" || typeof saved.seen !== "object") saved = { seen: {} };
  saved.seen[game] = n;
  try { localStorage.setItem(CONVO_KEY, JSON.stringify(saved)); } catch { /* not remembered */ }
}

const convoNewest = () => Math.max(0, ...CONVO.entries.keys());

function convoMarkSeen() {
  const n = convoNewest();
  if (CONVO.seen !== null && n <= CONVO.seen) return;
  CONVO.seen = n;
  convoWriteSeen(CONVO.game, n);
}

function convoUnread() {
  if (CONVO.seen === null) return 0;
  let n = 0;
  for (const e of CONVO.entries.values()) if (e.n > CONVO.seen && e.who !== "you") n++;
  return n;
}

function convoInvolves(e, ref) {
  return e.who === ref || e.to === ref || (e.who === "you" && (e.among || []).includes(ref));
}

function convoMerge(list) {
  for (const e of list || []) {
    if (e && typeof e.n === "number") CONVO.entries.set(e.n, e);
  }
}

// Whose words are on screen: the viewer's choice while it still names somebody, else the
// first person talking, else everyone.
function convoView(s) {
  const talking = (CONVO.people || []).filter(p => p.talking);
  if (CONVO.pick === "all") return "all";
  if (CONVO.pick && (CONVO.people.some(p => p.ref === CONVO.pick)
                     || [...CONVO.entries.values()].some(e => convoInvolves(e, CONVO.pick)))) {
    return CONVO.pick;
  }
  return talking.length ? talking[0].ref : "all";
}

function convoList(view) {
  const all = [...CONVO.entries.values()].sort((a, b) => a.n - b.n);
  return view === "all" ? all : all.filter(e => convoInvolves(e, view));
}

const capFirst = t => { t = String(t || ""); return t ? t[0].toUpperCase() + t.slice(1) : t; };

function convoNameOf(ref) {
  const p = (CONVO.people || []).find(x => x.ref === ref);
  if (p) return p.name;
  for (const e of CONVO.entries.values()) if (e.who === ref) return e.name;
  return "";
}

// One reader's view of the log. Consecutive entries by one speaker on one beat share a
// heading; a new day gets a line of its own. A grunt is a sentence in italics with its
// maker named, "Drenn Ironvale lets out a low, dry grunt.", as the design asked.
function convoRows(list, view) {
  let out = "", day = null, group = null;
  const close = () => { if (group !== null) out += `</div>`; group = null; };
  for (const e of list) {
    const d = Math.floor((e.t || 0) / 1440) + 1;
    if (d !== day) { close(); out += `<div class="cl-day">Day ${d}</div>`; day = d; }
    const you = e.who === "you";
    const key = `${e.who}|${e.beat}`;
    if (group !== key) {
      close();
      const toName = e.to && e.to !== "you" && e.to !== view ? convoNameOf(e.to) : "";
      out += `<div class="cl-turn${you ? " cl-you" : ""}"><span class="cl-name">${
        you ? "You" : esc(capFirst(e.name))}${toName ? `<small>to ${esc(toName)}</small>` : ""
        }</span>`;
      group = key;
    }
    if (e.kind === "vocal") {
      const text = String(e.text || "").replace(/[.!?]+$/, "");
      out += `<p class="cl-vocal">${esc(you ? "You" : capFirst(e.name))} ${esc(text)}.</p>`;
    } else {
      out += `<p><q>${esc(e.text)}</q></p>`;
    }
  }
  close();
  return out;
}

function drawConvoPeople(s, view) {
  const box = document.getElementById("convo-people");
  if (!box) return;
  const here = CONVO.people.filter(p => p.talking || p.present);
  const away = CONVO.people.filter(p => !p.talking && !p.present);
  const btn = (id, label, full) => `<button type="button" class="v2-btn" data-convo="${esc(id)}"
      aria-pressed="${view === id}" title="${esc(full || label)}">${esc(label)}</button>`;
  let html = btn("all", "Everyone", "Everything said with the people here")
    + here.map(p => btn(p.ref, capFirst(p.name), p.name)).join("");
  if (away.length) {
    html += `<select id="convo-earlier" aria-label="Earlier conversations">
      <option value="">Earlier conversations</option>${away.map(p =>
        `<option value="${esc(p.ref)}"${view === p.ref ? " selected" : ""}>${
          esc(capFirst(p.name))}</option>`).join("")}</select>`;
  }
  // Compared with what was written, not with innerHTML, which the browser re-serialises.
  if (CONVO.drawn.people === html && box.childElementCount) return;
  CONVO.drawn.people = html;
  // A redraw under a focused button would drop the focus to the body.
  const had = box.contains(document.activeElement)
    ? (document.activeElement.dataset.convo || document.activeElement.id) : null;
  box.innerHTML = html;
  if (had) {
    const back = box.querySelector(`[data-convo="${CSS.escape(had)}"]`) || document.getElementById(had);
    if (back) back.focus({ preventScroll: true });
  }
}

function convoAtFoot(log) {
  return log.scrollHeight - log.scrollTop - log.clientHeight < 24;
}

function drawConvoLog(view, toFoot) {
  const log = document.getElementById("convo-log");
  if (!log) return;
  const list = convoList(view);
  const first = list.length ? list[0].n : 0;
  const more = !CONVO.done.has(view) && (!list.length || first > 1);
  const html = (more ? `<button type="button" class="v2-btn is-quiet is-small convo-more" data-convo-more="${
    esc(view)}">Show earlier lines</button>` : "")
    + (list.length ? convoRows(list, view)
       : `<p class="trayempty">Nothing said with ${view === "all" ? "anybody here"
           : esc(convoNameOf(view) || "them")} yet.</p>`);
  const atFoot = convoAtFoot(log);
  if (CONVO.drawn.log !== html || !log.childElementCount) {
    const grew = CONVO.drawn.log !== "" && !toFoot;
    CONVO.drawn.log = html;
    log.innerHTML = html;
    // Appended below the reader, the text they are reading has not moved; only follow
    // the new lines if they were already at the foot.
    if (toFoot || atFoot) log.scrollTop = log.scrollHeight;
    else if (grew) CONVO.newBelow = true;
  } else if (toFoot) {
    log.scrollTop = log.scrollHeight;
  }
  if (convoAtFoot(log)) CONVO.newBelow = false;
  const latest = document.getElementById("convo-latest");
  if (latest) latest.hidden = !CONVO.newBelow;
}

function drawConvo(s, toFoot) {
  const box = document.getElementById("convo");
  if (!box) return;
  const has = CONVO.entries.size > 0 || CONVO.people.length > 0;
  box.hidden = !has;
  if (!has) return;
  const view = convoView(s);
  drawConvoPeople(s, view);
  drawConvoLog(view, toFoot);
}

function paintTalkTab() {
  const tab = document.getElementById("talktab");
  if (!tab) return;
  const n = talkIsOpen() ? 0 : convoUnread();
  const count = tab.querySelector(".edgecount");
  // "2 new", as the approved design words it (the mock README: "the Talk button counts
  // new lines"), where a bare "2" beside Talk could be read as two people.
  if (count) { count.textContent = n ? `${n} new` : ""; count.hidden = !n; }
  // The name starts with the word on the button, so a voice user saying "Talk" reaches
  // it (WCAG 2.5.3); the old edge tab said "Conversation" and showed "TALK".
  tab.setAttribute("aria-label", n ? `Talk, ${n} new` : "Talk");
  tab.setAttribute("aria-expanded", String(talkIsOpen()));
}

function openTalk({ focus = true } = {}) {
  const tray = talkTray();
  if (!tray) return;
  // The tray lives on the stage, so a tab that takes the whole page gives way to the
  // Table first (the approved design's rule: Talk opens beside the story).
  if (typeof Shell === "object" && Shell && !["table", "map", "sheet"].includes(Shell.mode())) {
    Shell.show("table");
  }
  tray.classList.add("on");
  tray.inert = false;
  document.body.classList.add("talkopen");
  drawConvo(STATE, true);
  convoMarkSeen();
  paintTalkTab();
  if (focus) {
    const to = tray.querySelector('#convo-people [aria-pressed="true"]')
      || document.getElementById("talkclose");
    if (to) to.focus({ preventScroll: true });
  }
}

function closeTalk() {
  const tray = talkTray();
  if (!tray || !tray.classList.contains("on")) return;
  const hadFocus = tray.contains(document.activeElement);
  tray.classList.remove("on");
  tray.inert = true;
  document.body.classList.remove("talkopen");
  paintTalkTab();
  if (hadFocus) { const tab = document.getElementById("talktab"); if (tab) tab.focus({ preventScroll: true }); }
}

async function convoPageBack(view) {
  const list = convoList(view);
  const before = list.length ? list[0].n : 0;
  const q = new URLSearchParams({ with: view, limit: "50" });
  if (before) q.set("before", String(before));
  let data;
  try { data = await readJSON(await fetch(`/api/conversation?${q}`, { cache: "no-store" })); }
  catch (err) { flash(err.message || String(err)); return; }
  const log = document.getElementById("convo-log");
  const height = log ? log.scrollHeight : 0, top = log ? log.scrollTop : 0;
  convoMerge(data.entries);
  if (!data.more || !(data.entries || []).length) CONVO.done.add(view);
  drawConvoLog(view, false);
  // Earlier lines go in above the reader; the view is held where it was.
  if (log && before) log.scrollTop = top + (log.scrollHeight - height);
}

onRender(function conversationTray(s, prev) {
  const scene = (s && s.scene) || {};
  const convo = scene.conversation || { people: [], recent: [], seq: 0 };
  const game = convoGame(s);
  // Another campaign, or this one begun again: nothing in the cache is about it.
  if (game !== CONVO.game || (convo.seq || 0) < CONVO.seq) {
    CONVO.game = game;
    CONVO.entries = new Map();
    CONVO.done = new Set();
    CONVO.pick = null;
    CONVO.newBelow = false;
    CONVO.drawn = { people: "", log: "" };
    CONVO.seen = convoReadSeen(game);
  }
  CONVO.seq = convo.seq || 0;
  CONVO.people = convo.people || [];
  convoMerge(convo.recent);
  // A mark past the log's own counter was left by an earlier log under the same world and
  // name (a character begun again): measured 2026-09-30, an earlier game's mark of 10 left
  // this game's lines 2 to 5 uncounted, and would have kept every line up to the tenth from
  // counting as new. It is no mark at all.
  if (CONVO.seen !== null && CONVO.seen > CONVO.seq) CONVO.seen = null;
  // A viewer this page has never seen starts with the history read, not counted as new.
  if (CONVO.seen === null) { CONVO.seen = convoNewest(); convoWriteSeen(game, CONVO.seen); }

  const talking = (scene.talk || []).length > 0;
  const started = !!prev && talking && !(((prev.scene || {}).talk) || []).length;
  // The conversation that just began is the one shown the next time the tray opens; a
  // reader who has it open keeps the page they chose rather than having it swapped under
  // them.
  if (started && !talkIsOpen()) CONVO.pick = null;
  if (talkIsOpen()) convoMarkSeen();
  drawConvo(s, started && !talkIsOpen());
  paintTalkTab();
});

// --- controls ---------------------------------------------------------------------------
document.addEventListener("click", e => {
  const t = e.target;
  // Talk opens the tray and closes it again: a button in the top bar that is pressed in
  // while the tray is out, as the design has it.
  if (t.closest("#talktab")) { if (talkIsOpen()) closeTalk(); else openTalk(); return; }
  if (t.closest("#talkclose")) { closeTalk(); return; }
  const pick = t.closest("[data-convo]");
  if (pick) { CONVO.pick = pick.dataset.convo; drawConvo(STATE, true); return; }
  const more = t.closest("[data-convo-more]");
  if (more) { more.disabled = true; convoPageBack(more.dataset.convoMore); return; }
  if (t.closest("#convo-latest")) {
    const log = document.getElementById("convo-log");
    if (log) log.scrollTop = log.scrollHeight;
    CONVO.newBelow = false;
    t.closest("#convo-latest").hidden = true;
    if (log) log.focus({ preventScroll: true });
  }
}, true);

document.addEventListener("change", async e => {
  const pick = e.target.closest && e.target.closest("#convo-earlier");
  if (!pick || !pick.value) return;
  CONVO.pick = pick.value;
  // Somebody no longer here: their lines are not in the state's recent window.
  if (!convoList(pick.value).length) await convoPageBack(pick.value);
  drawConvo(STATE, true);
});

document.addEventListener("keydown", e => {
  if (e.key === "Escape" && talkIsOpen()) {
    const a = document.activeElement;
    if (!a || a === document.body || talkTray().contains(a)) closeTalk();
  }
});

(function watchConvoScroll() {
  const log = document.getElementById("convo-log");
  if (!log) return;
  log.addEventListener("scroll", () => {
    if (!convoAtFoot(log)) return;
    CONVO.newBelow = false;
    const latest = document.getElementById("convo-latest");
    if (latest) latest.hidden = true;
  }, { passive: true });
})();
