// The play table, part 07 (panels). Classic script, sharing one global scope with 01-06
// and 08-21, loaded after 06.
//
// Two things live here, and the first is unchanged since the 2026-09-28 panel shell:
//
// 1. The render hooks (`onRender`, `runRenderHooks`), which every later part of the
//    table draws through (docs/fix-interfaces.md §2.11).
// 2. The panels. Until the table rebuild (docs/table-rebuild-inventory.md) the side
//    column was four panels, Sheet, Scene, Map and Rolls, with a bar of toggles, a close
//    on each, "Hide the column" and a phone drawer with tabs on the right edge. The
//    owner's approved design replaced that column with the stage's two sides and the
//    tabs on top (docs/mock/table-layout/README.md): the sheet in brief is the two sides
//    (14-sides.js), the map is a tab, the phone's sheet is a tab. What is left of the
//    panels is the two the design had no other place for, "In the scene" and "Rolls",
//    as disclosures at the foot of the right side, folded or open and remembered.
//    "Hide the column" became Hide sheet, the same choice under the same stored key.
//
// What it exports (§2.11): `onRender(fn)` for the lanes' render hooks, and
// `Panels = {open, close, collapse, expand, forward, mode}`, the same names with the
// meanings the new layout gives them (each says below).

const PANEL_IDS = ["scene", "rolls"];
// Versioned because Electron's storage outlives every reinstall (CLAUDE.md, the stale
// stylesheet). The pre-paint script at the top of <body> reads the same key for `docked`;
// if this name changes, change it there too. `docked: false` is "the sheet is hidden".
const PANELS_KEY = "pgm.table.panels.v1";
const PANELS_NARROW = window.matchMedia ? window.matchMedia("(max-width: 760px)") : null;
const PANELS_STILL = window.matchMedia
  ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;

// --- render hooks ----------------------------------------------------------------------
//
// `render()` in 02 calls `runRenderHooks(s, prev)` on every draw. The page's first draw
// happens at the bottom of 06, before this file and 08-21 have loaded, so 02 guards the
// call and the hooks are primed once the document has finished parsing: every hook then
// sees the state on screen with `prev === null`, which is how a hook tells the first
// draw (never a reason to pop a clock or bring a panel forward) from a turn.
const RENDER_HOOKS = [];
let RENDER_HOOKS_PRIMED = false;

function onRender(fn) {
  if (typeof fn === "function") RENDER_HOOKS.push(fn);
}

function runRenderHooks(s, prev) {
  // Before priming, the prime itself will catch up with whatever is on screen.
  if (!RENDER_HOOKS_PRIMED) return;
  for (const fn of RENDER_HOOKS) {
    // One lane's broken hook must not stop the table drawing, or stop the others.
    try { fn(s, prev); } catch (err) { console.error("render hook failed:", err); }
  }
}

function primeRenderHooks() {
  if (RENDER_HOOKS_PRIMED) return;
  RENDER_HOOKS_PRIMED = true;
  if (STATE) runRenderHooks(STATE, null);
}

// --- the layout, remembered per viewer -------------------------------------------------
//
// {collapsed:{id:bool}, docked:bool}. Unreadable, missing or throwing storage means
// everything open and the sheet shown: Foundry v13 shipped a sidebar collapsed by default
// with no setting, and two modules exist only to reopen it on load. A record written by
// the old column (it also held `open` for the four panels) reads the same: the unknown
// ids are ignored.
function readPanelLayout() {
  const out = { collapsed: {}, docked: true, chosen: {} };
  for (const id of PANEL_IDS) out.collapsed[id] = false;
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(PANELS_KEY) || "null"); } catch { saved = null; }
  if (!saved || typeof saved !== "object") return out;
  for (const id of PANEL_IDS) {
    if (saved.collapsed && typeof saved.collapsed[id] === "boolean") {
      out.collapsed[id] = saved.collapsed[id];
      out.chosen[id] = true;
    }
  }
  if (saved.docked === false) out.docked = false;
  return out;
}

const PANEL_LAYOUT = readPanelLayout();

function savePanelLayout() {
  const { collapsed, docked, chosen } = PANEL_LAYOUT;
  // Only the folds somebody chose are written, so a default stays a default.
  const kept = {};
  for (const id of PANEL_IDS) if (chosen[id]) kept[id] = collapsed[id];
  try {
    localStorage.setItem(PANELS_KEY, JSON.stringify({ collapsed: kept, docked }));
  } catch { /* private window, blocked storage: the layout simply is not remembered */ }
}

// --- the DOM ---------------------------------------------------------------------------
const panelsAside = () => document.getElementById("panels");
const panelSection = id => document.getElementById(`panel-${id}`);
const panelBody = id => document.getElementById(`panel-${id}-body`);
const panelToggle = id => { const s = panelSection(id); return s && s.querySelector(".paneltoggle"); };

function sheetHidden() { return document.body.classList.contains("sheet-hidden"); }

function paintPanels() {
  for (const id of PANEL_IDS) {
    const section = panelSection(id), body = panelBody(id), toggle = panelToggle(id);
    if (!section) continue;
    const collapsed = PANEL_LAYOUT.collapsed[id];
    section.classList.toggle("collapsed", collapsed);
    if (body) body.hidden = collapsed;
    if (toggle) toggle.setAttribute("aria-expanded", String(!collapsed));
  }
  const toggle = document.getElementById("sheettoggle");
  if (toggle) {
    const hidden = sheetHidden();
    toggle.textContent = hidden ? "Show sheet" : "Hide sheet";
    toggle.setAttribute("aria-expanded", String(!hidden));
    toggle.title = hidden
      ? "Put your character and your numbers back beside the story."
      : "Give the story the full width. The Sheet tab still has everything.";
  }
}

// Hide sheet is a desktop's choice; under 760px the sheet is a tab of its own and the
// choice waits for a wider window (the pre-paint script reads it the same way).
function applyPanelMode() {
  const narrow = !!(PANELS_NARROW && PANELS_NARROW.matches);
  document.body.classList.toggle("sheet-hidden", !narrow && !PANEL_LAYOUT.docked);
  paintPanels();
}

// `onlyIfHidden` for what the page brings forward by itself: a heading already in view
// stays where the player is reading it rather than the side jumping to line it up.
function scrollToPanel(id, smooth, onlyIfHidden) {
  const aside = panelsAside(), section = panelSection(id);
  if (!aside || !section || section.hidden) return;
  // At 1180px and below the two sides are one scrolled column, `.sheet`.
  const box = aside.scrollHeight > aside.clientHeight ? aside
    : (aside.closest(".sheet") || aside);
  const top = Math.max(0, section.offsetTop - 12);
  if (onlyIfHidden) {
    const head = section.querySelector(".panelhead");
    const h = head ? head.offsetHeight : 30;
    if (section.offsetTop >= box.scrollTop
        && section.offsetTop + h <= box.scrollTop + box.clientHeight) return;
  }
  const still = PANELS_STILL && PANELS_STILL.matches;
  if (box.scrollTo) box.scrollTo({ top, behavior: smooth && !still ? "smooth" : "auto" });
}

// A short fade on a body the viewer just opened, so the change reads as theirs. Opacity
// only and 140ms: nothing under the pointer moves, and it never blocks the next click.
function markArrived(id) {
  const body = panelBody(id);
  if (!body) return;
  body.classList.remove("arrive");
  void body.offsetWidth;
  body.classList.add("arrive");
}

// --- the API ---------------------------------------------------------------------------
const Panels = {
  // "scene" or "rolls": unfold it and bring it into view, showing the sheet first if it
  // was hidden. "sheet" shows the sheet (on a phone, the Sheet tab); "map" is the Map tab.
  open(id = "sheet", { focus = true } = {}) {
    if (id === "map") { if (typeof showMap === "function") showMap(true); return; }
    if (PANELS_NARROW && PANELS_NARROW.matches) {
      if (typeof Shell === "object" && Shell) Shell.show("sheet");
    } else if (sheetHidden()) {
      Panels.mode("column");
    }
    if (!PANEL_IDS.includes(id)) return;
    if (PANEL_LAYOUT.collapsed[id]) { Panels.expand(id); }
    scrollToPanel(id, true);
    const toggle = panelToggle(id);
    if (focus && toggle) toggle.focus({ preventScroll: true });
  },

  // There is no drawer to close and no panel to take off the side any more: the two
  // disclosures fold (`collapse`). Kept, a harmless no-op, for the callers that close
  // "whatever is sliding over the story" before opening something of their own.
  close() {},

  collapse(id) {
    if (!PANEL_IDS.includes(id)) return;
    PANEL_LAYOUT.collapsed[id] = true;
    PANEL_LAYOUT.chosen[id] = true;
    savePanelLayout();
    paintPanels();
  },

  expand(id) {
    if (!PANEL_IDS.includes(id)) return;
    const was = PANEL_LAYOUT.collapsed[id];
    PANEL_LAYOUT.collapsed[id] = false;
    PANEL_LAYOUT.chosen[id] = true;
    savePanelLayout();
    paintPanels();
    if (was) markArrived(id);
  },

  // Something started that this panel shows: a fight. Edge-triggered by the caller, and
  // it never moves focus: unfold "In the scene" and bring it into view in the side if
  // the side is on screen. A hidden sheet stays hidden (the fight is on the desk, in the
  // combat bar, and the player chose the width); a phone's sheet stays a tab.
  forward(id) {
    if (!PANEL_IDS.includes(id)) return;
    PANEL_LAYOUT.collapsed[id] = false;
    paintPanels();
    if (!sheetHidden()) scrollToPanel(id, true, true);
  },

  // "column" (the sheet shown) or "drawer" (hidden), the old names kept for their
  // callers. Given one, it sets the desktop's choice; it returns the one in force.
  mode(set) {
    if (set === "column" || set === "drawer") {
      PANEL_LAYOUT.docked = set === "column";
      savePanelLayout();
      applyPanelMode();
    }
    return sheetHidden() ? "drawer" : "column";
  },
};

// --- what comes forward on its own ------------------------------------------------------
// Edge-triggered from the state the page already has: `scene.in_encounter` turning on.
// A conversation starting is the conversation tray's to answer (08-conversation.js).
onRender((s, prev) => {
  const scene = (s && s.scene) || {};
  if (!prev) return;
  const before = (prev && prev.scene) || {};
  if (scene.in_encounter && !before.in_encounter) Panels.forward("scene");
});

// --- "In the scene": Harvest beside a carcass (leather UI plan §6.9, lane U2) -----------
// A dead creature's row in the scene panel gets a Harvest button, "only while the carcass is
// harvestable and the character has a craft that wants a part"; a body still breathing (down
// and dying, not dead: lane C measured a wolf at -12 after the fight's last blow) says so
// instead, so the player is not left wondering why nothing is offered. Humanoids never get
// one: the server never lists them (`api/harvest`), so there is nothing here to refuse.
// The button opens the sheet in 59-harvest.js (`window.HarvestSheet`, looked up when the panel
// is drawn); without that file in the build no button is drawn at all. #board is redrawn
// whole on every render (02-state.js), so the buttons are put back from the last answer each
// time, and the server is asked again only when a body's hit points, the set of actors or the
// hour changes, and never while a fight is on (the take refuses in a fight anyway).
const HARVEST_BOARD = { sig: "", list: null };

function harvestBoardPaint(s) {
  const board = document.getElementById("board");
  const list = HARVEST_BOARD.list;
  if (!board || !list) return;
  const rows = board.querySelectorAll(":scope > .who");
  const actors = (s && s.scene && s.scene.actors) || [];
  const bodies = new Map((list.carcasses || []).filter(b => b.parts > 0).map(b => [b.ref, b]));
  const breathing = new Set((list.breathing || []).map(b => b.ref));
  actors.forEach((a, i) => {
    const row = rows[i];
    if (!row) return;
    // A fresh answer replaces what the last one drew: painting over the old buttons left a
    // wolf with nothing left on it still offering Harvest (seen live, 2026-10-08).
    row.querySelectorAll(".who-harvest, .who-breathing").forEach(el => el.remove());
    row.classList.remove("has-harvest");
    if (bodies.has(a.ref)) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "v2-btn is-quiet is-small who-harvest";
      b.setAttribute("data-harvest-open", a.ref);
      b.textContent = "Harvest";
      // The body's name as the scene gives it, never wrapped in an article of ours: a name
      // that carries its own read "Harvest the a grey wolf" (the final pass, live, 2026-10-09).
      b.setAttribute("aria-label", `Harvest: ${a.name}`);
      row.classList.add("has-harvest");
      row.appendChild(b);
    } else if (breathing.has(a.ref)) {
      const w = document.createElement("small");
      w.className = "who-breathing";
      w.textContent = "still breathing: finish it first";
      row.classList.add("has-harvest");
      row.appendChild(w);
    }
  });
}

// The sheet says when a take has changed what a body still offers (59-harvest.js, on close),
// since no hit point or hour has to change for the last part to go.
function harvestBoardStale() { HARVEST_BOARD.sig = ""; }

onRender(s => {
  const scene = (s && s.scene) || {};
  const actors = scene.actors || [];
  const fallen = actors.some(a => !a.is_pc && Number(a.hp) <= 0);
  if (!window.HarvestSheet || scene.in_encounter || !fallen) {
    HARVEST_BOARD.list = null;
    HARVEST_BOARD.sig = "";
    return;
  }
  harvestBoardPaint(s);
  const sig = actors.map(a => `${a.ref}:${a.hp}`).join("|") + "@" + Math.floor((scene.clock_minutes || 0) / 60);
  if (sig === HARVEST_BOARD.sig) return;
  HARVEST_BOARD.sig = sig;
  fetch("/api/harvest", { cache: "no-store" })
    .then(r => readJSON(r))
    .then(list => {
      if (!list || HARVEST_BOARD.sig !== sig) return;
      HARVEST_BOARD.list = list;
      harvestBoardPaint(STATE);
    })
    .catch(() => { /* the panel simply shows no button; the hub still opens the sheet */ });
});

// --- controls --------------------------------------------------------------------------
document.addEventListener("click", e => {
  if (e.target.closest("#sheettoggle")) {
    Panels.mode(sheetHidden() ? "column" : "drawer");
    return;
  }
  const toggle = e.target.closest(".paneltoggle");
  if (toggle) {
    const id = toggle.closest(".panel").dataset.panel;
    if (PANEL_LAYOUT.collapsed[id]) Panels.expand(id); else Panels.collapse(id);
  }
});

if (PANELS_NARROW) {
  const onChange = () => applyPanelMode();
  if (PANELS_NARROW.addEventListener) PANELS_NARROW.addEventListener("change", onChange);
  else if (PANELS_NARROW.addListener) PANELS_NARROW.addListener(onChange);
}

applyPanelMode();

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", primeRenderHooks);
} else {
  setTimeout(primeRenderHooks, 0);
}
