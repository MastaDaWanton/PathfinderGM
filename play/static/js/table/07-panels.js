// The play table, part 07 of 10 (panels). Classic script, sharing one global scope with
// 01-06 and 08-10, loaded after them.
//
// The side column as five panels: Sheet, Scene, Conversation, Map, Rolls
// (docs/design-f-ui.md §4.1). One component, two modes:
//
// - column mode is the docked column the table has always had;
// - drawer mode is the phone's slide-over, used under 760px AND on a desktop after
//   "Hide the column", written once as `body.drawer aside` rules.
//
// Several panels show at once, so this is a toolbar of toggle buttons plus a disclosure
// per panel, not the APG tabs pattern (which assumes one displayed panel — Foundry's
// Sticky Sidebar exists precisely because one-tab-at-a-time was a regression). Every
// renderer that wrote into the old aside writes into the same ids inside a panel body;
// nothing here draws game content.
//
// What it exports (docs/fix-interfaces.md §2.11): `onRender(fn)` for the lanes' render
// hooks, and `Panels = {open, close, collapse, expand, forward, mode}`.

const PANEL_IDS = ["sheet", "scene", "conversation", "map", "rolls"];
// Versioned because Electron's storage outlives every reinstall (CLAUDE.md, the stale
// stylesheet). The pre-paint script at the top of <body> reads the same key for `docked`;
// if this name changes, change it there too.
const PANELS_KEY = "pgm.table.panels.v1";
const PANELS_NARROW = window.matchMedia ? window.matchMedia("(max-width: 760px)") : null;
const PANELS_STILL = window.matchMedia
  ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;

// --- render hooks ----------------------------------------------------------------------
//
// `render()` in 02 calls `runRenderHooks(s, prev)` on every draw. The page's first draw
// happens at the bottom of 06, before this file and 08-10 have loaded, so 02 guards the
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
// {open:{id:bool}, collapsed:{id:bool}, docked:bool}. Unreadable, missing or throwing
// storage means everything open and docked: Foundry v13 shipped a sidebar collapsed by
// default with no setting, and two modules exist only to reopen it on load.
// Conversation's body starts collapsed until the first conversation, and only by default:
// a collapse the viewer chose is remembered as theirs.
function readPanelLayout() {
  const out = { open: {}, collapsed: {}, docked: true, chosen: {} };
  for (const id of PANEL_IDS) { out.open[id] = true; out.collapsed[id] = false; }
  out.collapsed.conversation = true;
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(PANELS_KEY) || "null"); } catch { saved = null; }
  if (!saved || typeof saved !== "object") return out;
  for (const id of PANEL_IDS) {
    // Unknown ids in the saved record are ignored; a missing one keeps its default.
    if (saved.open && typeof saved.open[id] === "boolean") out.open[id] = saved.open[id];
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
  const { open, collapsed, docked, chosen } = PANEL_LAYOUT;
  // Only the collapses somebody chose are written, so a default stays a default.
  const kept = {};
  for (const id of PANEL_IDS) if (chosen[id]) kept[id] = collapsed[id];
  try {
    localStorage.setItem(PANELS_KEY, JSON.stringify({ open, collapsed: kept, docked }));
  } catch { /* private window, blocked storage: the layout simply is not remembered */ }
}

// --- the DOM ---------------------------------------------------------------------------
const panelsAside = () => document.getElementById("panels");
const panelSection = id => document.getElementById(`panel-${id}`);
const panelBody = id => document.getElementById(`panel-${id}-body`);
const panelToggle = id => { const s = panelSection(id); return s && s.querySelector(".paneltoggle"); };
const panelBarButton = id => document.querySelector(`#panelbar .panelbtn[data-panel="${id}"]`);

function isDrawerMode() { return document.body.classList.contains("drawer"); }
function isDrawerOpen() { const a = panelsAside(); return !!(a && a.classList.contains("on")); }

function paintPanels() {
  for (const id of PANEL_IDS) {
    const section = panelSection(id), body = panelBody(id), toggle = panelToggle(id);
    if (!section) continue;
    const open = PANEL_LAYOUT.open[id], collapsed = PANEL_LAYOUT.collapsed[id];
    section.hidden = !open;
    section.classList.toggle("collapsed", collapsed);
    if (body) body.hidden = collapsed;
    if (toggle) toggle.setAttribute("aria-expanded", String(!collapsed));
    const btn = panelBarButton(id);
    if (btn) btn.setAttribute("aria-pressed", String(open));
  }
  const mode = document.getElementById("panelmode");
  if (mode) {
    mode.textContent = PANEL_LAYOUT.docked ? "Hide the column" : "Show the column";
    mode.title = PANEL_LAYOUT.docked
      ? "Give the story the full width. The panels open from tabs on the right edge."
      : "Put the panels back beside the story.";
  }
}

// The edge tabs, which exist only in drawer mode (CSS hides the group in column mode).
// Sheet always; Scene while a fight is on; Conversation while somebody is talking with
// you or there are unread lines, with the count. Map keeps its own left-edge tab.
const EDGE_COUNT = { conversation: 0, scene: 0, sheet: 0, map: 0, rolls: 0 };

function paintEdgeTabs() {
  const s = STATE || {};
  const scene = s.scene || {};
  const shown = {
    sheet: true,
    scene: !!scene.in_encounter || EDGE_COUNT.scene > 0,
    conversation: (scene.talk || []).length > 0 || EDGE_COUNT.conversation > 0,
  };
  const drawerOpen = isDrawerOpen();
  document.querySelectorAll("#edgetabs .edgetab").forEach(tab => {
    const id = tab.dataset.panel;
    tab.hidden = !shown[id];
    tab.setAttribute("aria-expanded", String(drawerOpen));
    const n = EDGE_COUNT[id] || 0;
    const count = tab.querySelector(".edgecount");
    if (count) { count.textContent = n ? String(n) : ""; count.hidden = !n; }
    const name = tab.dataset.name || id;
    tab.setAttribute("aria-label", n ? `${name}, ${n} new` : name);
  });
}

// --- modes -----------------------------------------------------------------------------
function applyPanelMode() {
  const narrow = !!(PANELS_NARROW && PANELS_NARROW.matches);
  const drawer = narrow || !PANEL_LAYOUT.docked;
  document.body.classList.toggle("drawer", drawer);
  const aside = panelsAside();
  if (aside) {
    if (!drawer) aside.classList.remove("on");
    // An off-screen drawer is not in the Tab order. Before this, on a phone, Tab walked
    // the whole invisible sheet before reaching anything on screen.
    aside.inert = drawer && !aside.classList.contains("on");
  }
  paintPanels();
  paintEdgeTabs();
  const current = document.querySelector('#panelbar button[tabindex="0"]');
  panelBarRove(current);
}

let DRAWER_OPENER = null;

function openDrawer(from) {
  const aside = panelsAside();
  if (!aside || !isDrawerMode()) return;
  if (!aside.classList.contains("on")) DRAWER_OPENER = from || null;
  aside.classList.add("on");
  aside.inert = false;
  // Two slide-overs on one screen must never both be open: on a 375px phone the second
  // lands on top of the first (the rule `showSheet` carried since the phone layout).
  if (typeof showMap === "function") showMap(false);
  paintEdgeTabs();
}

function closeDrawer() {
  const aside = panelsAside();
  if (!aside || !aside.classList.contains("on")) return;
  const hadFocus = aside.contains(document.activeElement);
  aside.classList.remove("on");
  aside.inert = isDrawerMode();
  const back = DRAWER_OPENER;
  DRAWER_OPENER = null;
  paintEdgeTabs();
  // Focus goes back where it came from only when it was inside the drawer, which is now
  // inert. A click outside that landed on the input keeps the input.
  if (hadFocus) {
    const to = (back && document.contains(back) && !back.hidden) ? back
      : (document.getElementById("sheettab") || document.getElementById("input"));
    if (to) to.focus({ preventScroll: true });
  }
}

// `onlyIfHidden` for what the page brings forward by itself: a heading already in view
// stays where the player is reading it rather than the column jumping to line it up.
function scrollToPanel(id, smooth, onlyIfHidden) {
  const aside = panelsAside(), section = panelSection(id);
  if (!aside || !section || section.hidden) return;
  const top = Math.max(0, section.offsetTop - 12);
  if (onlyIfHidden) {
    const head = section.querySelector(".panelhead");
    const h = head ? head.offsetHeight : 30;
    if (section.offsetTop >= aside.scrollTop
        && section.offsetTop + h <= aside.scrollTop + aside.clientHeight) return;
  }
  const still = PANELS_STILL && PANELS_STILL.matches;
  aside.scrollTo({ top, behavior: smooth && !still ? "smooth" : "auto" });
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
  // Restore a panel, expand it and bring it into view. In drawer mode this also slides
  // the drawer in; `from` is the control focus returns to when it closes.
  open(id = "sheet", { from = null, focus = true } = {}) {
    if (!PANEL_IDS.includes(id)) return;
    const wasShut = !PANEL_LAYOUT.open[id] || PANEL_LAYOUT.collapsed[id];
    PANEL_LAYOUT.open[id] = true;
    if (PANEL_LAYOUT.collapsed[id]) { PANEL_LAYOUT.collapsed[id] = false; PANEL_LAYOUT.chosen[id] = true; }
    savePanelLayout();
    paintPanels();
    if (wasShut) markArrived(id);
    if (isDrawerMode()) {
      EDGE_COUNT[id] = 0;
      openDrawer(from);
      scrollToPanel(id, false);
    } else {
      scrollToPanel(id, true);
    }
    const toggle = panelToggle(id);
    if (focus && toggle) toggle.focus({ preventScroll: true });
    paintEdgeTabs();
  },

  // With an id, take that panel off the column (its bar button reads unpressed). With
  // none, close the drawer: the one "close" there is for the whole column.
  close(id) {
    if (id === undefined) { closeDrawer(); return; }
    if (!PANEL_IDS.includes(id)) return;
    const section = panelSection(id);
    const hadFocus = section && section.contains(document.activeElement);
    PANEL_LAYOUT.open[id] = false;
    savePanelLayout();
    paintPanels();
    if (hadFocus) { const b = panelBarButton(id); if (b) b.focus({ preventScroll: true }); }
  },

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

  // Something started that this panel shows: a conversation, a fight. Edge-triggered by
  // the caller, and it never moves focus.
  //   column: restore, expand, and scroll it into view inside the column;
  //   drawer: do NOT open the drawer (it would cover the beat about to be read; G0 Q7).
  //           The panel's edge tab shows instead, with `count` when one is given.
  // A player who closes the panel mid-conversation keeps it closed, because nothing
  // calls this again until the next one starts.
  forward(id, { count } = {}) {
    if (!PANEL_IDS.includes(id)) return;
    if (typeof count === "number" && count >= 0) EDGE_COUNT[id] = count;
    if (isDrawerMode()) { paintEdgeTabs(); return; }
    PANEL_LAYOUT.open[id] = true;
    PANEL_LAYOUT.collapsed[id] = false;
    PANEL_LAYOUT.chosen[id] = true;
    savePanelLayout();
    paintPanels();
    scrollToPanel(id, true, true);
  },

  // "column" or "drawer". Given one, it sets the desktop's choice ("Hide the column");
  // under 760px the drawer is the only mode and the choice waits for a wider window.
  mode(set) {
    if (set === "column" || set === "drawer") {
      PANEL_LAYOUT.docked = set === "column";
      savePanelLayout();
      applyPanelMode();
    }
    return isDrawerMode() ? "drawer" : "column";
  },
};

// --- what comes forward on its own ------------------------------------------------------
// Both edge-triggered from the state the page already has: `scene.talk` going from empty
// to not, and `scene.in_encounter` turning on. Lane F's conversation log adds its own
// trigger (a new line while the panel is collapsed) through `Panels.forward`.
onRender((s, prev) => {
  const scene = (s && s.scene) || {};
  const talking = (scene.talk || []).length > 0;
  if (!prev) {
    // The first draw. A conversation already running when the page opens is shown, but
    // only over the default collapse; one the viewer collapsed themselves stays as it is.
    if (talking && !PANEL_LAYOUT.chosen.conversation && !isDrawerMode()) {
      PANEL_LAYOUT.collapsed.conversation = false;
      paintPanels();
    }
    paintEdgeTabs();
    return;
  }
  const before = (prev && prev.scene) || {};
  if (talking && !(before.talk || []).length) Panels.forward("conversation");
  if (scene.in_encounter && !before.in_encounter) Panels.forward("scene");
  paintEdgeTabs();
});

// --- controls --------------------------------------------------------------------------
document.addEventListener("click", e => {
  const btn = e.target.closest("#panelbar .panelbtn");
  if (btn) {
    const id = btn.dataset.panel;
    if (PANEL_LAYOUT.open[id]) Panels.close(id);
    else Panels.open(id, { focus: false });
    return;
  }
  if (e.target.closest("#panelmode")) {
    const hiding = PANEL_LAYOUT.docked;
    Panels.mode(hiding ? "drawer" : "column");
    // The button that was pressed has just slid off screen with the column; the Sheet
    // edge tab is where the column is now reached from.
    if (hiding) { const t = document.getElementById("sheettab"); if (t) t.focus({ preventScroll: true }); }
    return;
  }
  const toggle = e.target.closest(".paneltoggle");
  if (toggle) {
    const id = toggle.closest(".panel").dataset.panel;
    if (PANEL_LAYOUT.collapsed[id]) Panels.expand(id); else Panels.collapse(id);
    return;
  }
  const shut = e.target.closest(".panelclose");
  if (shut) Panels.close(shut.closest(".panel").dataset.panel);
});

// The toolbar is one Tab stop with the arrow keys inside it (APG toolbar pattern).
function panelBarItems() {
  return [...document.querySelectorAll("#panelbar button")].filter(b => b.offsetParent !== null);
}
function panelBarRove(to) {
  const items = panelBarItems();
  // A stop that is no longer shown (the column button under 760px) hands its place to
  // the first one, or the toolbar would drop out of the Tab order altogether.
  if (!to || !items.includes(to)) to = items[0];
  if (!to) return;
  document.querySelectorAll("#panelbar button").forEach(b => { b.tabIndex = b === to ? 0 : -1; });
}
document.addEventListener("keydown", e => {
  const here = e.target.closest && e.target.closest("#panelbar button");
  if (!here) return;
  const items = panelBarItems();
  const i = items.indexOf(here);
  let to = null;
  if (e.key === "ArrowRight" || e.key === "ArrowDown") to = items[(i + 1) % items.length];
  else if (e.key === "ArrowLeft" || e.key === "ArrowUp") to = items[(i - 1 + items.length) % items.length];
  else if (e.key === "Home") to = items[0];
  else if (e.key === "End") to = items[items.length - 1];
  if (!to) return;
  e.preventDefault();
  panelBarRove(to);
  to.focus();
});
document.addEventListener("focusin", e => {
  const b = e.target.closest && e.target.closest("#panelbar button");
  if (b) panelBarRove(b);
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
