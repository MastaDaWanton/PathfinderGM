// The play table, part 12 (the shell). Classic script, sharing one global scope with
// 01-11 and 13-21, loaded after 11-exits.js.
//
// The table rebuild, stage 1 (docs/table-rebuild-inventory.md): the owner's approved
// design (docs/mock/table-layout/) lays the table out as tabs, each a word in the top
// bar, Table, Map, Sheet, Equipment, Spells (a caster's only), Trade and Journal.
// Table, Map and Sheet share the stage (the two sides, and the book, the board or the
// sheet in the centre column); the rest take the whole page. This file switches between
// them and nothing else: `body.mode-<name>`, the tabs' pressed state, and which page is
// shown. What each tab puts on its page is that tab's own script (16-21), which
// registers here with `Shell.tab(name, {enter, leave})`, so stages 2 and 3 can replace a
// tab's body without touching the others.
//
// The tabs follow the WAI-ARIA Authoring Practices' tabs pattern with automatic
// activation: one Tab stop (the chosen tab), the arrow keys move along the row and
// choose, Home and End go to either end. Automatic because showing a tab costs nothing
// here that a person would wait for (APG, "Deciding When to Make Selection Automatically
// Follow Focus"): a tab's page is already on the page, and the ones that read the server
// say so while they do.

const SHELL_MODES = ["table", "map", "sheet", "equipment", "spells", "trade", "journal"];
// The tabs whose page is the sheet panel, scoped to their own pages (17-tab-sheet.js).
const SHELL_SHEET_BACKED = ["sheet", "equipment", "spells", "journal"];
// The tabs that keep the stage (the sides, the device, the tray).
const SHELL_ON_STAGE = ["table", "map", "sheet"];
const SHELL_TABS = {};
let SHELL_MODE = "table";

const shellTab = m => document.getElementById(`tab-${m}`);
const shellVisible = () => SHELL_MODES.filter(m => { const t = shellTab(m); return t && !t.hidden; });

// The row scrolls sideways on a phone; the chosen tab is kept in view without moving
// the page.
function shellKeepTabInView(tab) {
  const row = tab && tab.parentElement;
  if (!row || row.scrollWidth <= row.clientWidth) return;
  const left = tab.offsetLeft - row.offsetLeft;
  if (left < row.scrollLeft) row.scrollLeft = Math.max(0, left - 4);
  else if (left + tab.offsetWidth > row.scrollLeft + row.clientWidth) {
    row.scrollLeft = left + tab.offsetWidth - row.clientWidth + 4;
  }
}

// Draw a mode: the body's class, the tabs, the pages. No tab's own `enter` runs here.
function shellPaint(mode, focusTab) {
  document.body.classList.remove(...SHELL_MODES.map(m => "mode-" + m));
  document.body.classList.add("mode-" + mode);
  for (const m of SHELL_MODES) {
    const t = shellTab(m);
    if (!t) continue;
    const on = m === mode;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
    if (on) {
      shellKeepTabInView(t);
      if (focusTab) t.focus({ preventScroll: true });
    }
  }
  const stage = document.getElementById("stage");
  if (stage) stage.setAttribute("aria-labelledby", `tab-${SHELL_ON_STAGE.includes(mode) ? mode : "table"}`);
  for (const m of SHELL_MODES) {
    const page = document.getElementById(`mode-${m}`);
    if (page) page.hidden = m !== mode;
  }
}

// Leave the tab that is open for `mode`: its own `leave`, then what every change of tab
// closes (the craft hub and the spell picker hang over the desk; the tray lives on the
// stage, so a page that takes the whole window closes it).
function shellSwitch(mode, focusTab) {
  if (!shellVisible().includes(mode)) mode = "table";
  const was = SHELL_MODE;
  if (was !== mode && SHELL_TABS[was] && SHELL_TABS[was].leave) {
    try { SHELL_TABS[was].leave(mode); } catch (err) { console.error("tab leave failed:", err); }
  }
  SHELL_MODE = mode;
  shellPaint(mode, focusTab);
  const craft = document.getElementById("craftpanel");
  if (craft && !craft.hidden) { craft.hidden = true; shellCraftExpanded(false); }
  if (typeof closeSpellPicker === "function") closeSpellPicker();
  if (!SHELL_ON_STAGE.includes(mode) && typeof talkIsOpen === "function" && talkIsOpen()) {
    closeTalk();
  }
  return { was, mode };
}

const Shell = {
  // A tab's script registers what its page does as it opens and closes.
  tab(name, hooks) { SHELL_TABS[name] = hooks || {}; },
  mode() { return SHELL_MODE; },
  sheetBacked(m = SHELL_MODE) { return SHELL_SHEET_BACKED.includes(m); },
  // Open a tab: switch to it and let it fill its page.
  show(mode, { focusTab = false } = {}) {
    const { was, mode: now } = shellSwitch(mode, focusTab);
    const hooks = SHELL_TABS[now];
    if (hooks && hooks.enter) {
      try { hooks.enter(was); } catch (err) { console.error("tab enter failed:", err); }
    }
    return now;
  },
  // Switch to a tab whose page is already being filled by its caller (openTrade fills
  // the counter itself, and calls this so that it is shown).
  enter(mode) { return shellSwitch(mode, false).mode; },
};

// --- the tabs --------------------------------------------------------------------------
document.addEventListener("click", e => {
  const tab = e.target.closest && e.target.closest(".modes [role=tab]");
  if (tab) { Shell.show(tab.dataset.mode); return; }
  if (e.target.closest("#glance")) { Shell.show("sheet"); return; }
  if (e.target.closest("#open-equipment")) { Shell.show("equipment"); return; }
});

document.addEventListener("keydown", e => {
  const here = e.target.closest && e.target.closest(".modes [role=tab]");
  if (!here) return;
  const tabs = shellVisible().map(shellTab);
  const i = tabs.indexOf(here);
  let to = null;
  if (e.key === "ArrowRight") to = tabs[(i + 1) % tabs.length];
  else if (e.key === "ArrowLeft") to = tabs[(i - 1 + tabs.length) % tabs.length];
  else if (e.key === "Home") to = tabs[0];
  else if (e.key === "End") to = tabs[tabs.length - 1];
  if (!to) return;
  e.preventDefault();
  Shell.show(to.dataset.mode, { focusTab: true });
});

// --- the craft hub, a popover over the story's foot -------------------------------------
// 03 opens and closes #craftpanel; this keeps its button's state and its Close in step.
function shellCraftExpanded(open) {
  const b = document.getElementById("craftaction");
  if (b) b.setAttribute("aria-expanded", String(!!open));
}
document.addEventListener("click", e => {
  if (e.target.closest("#craftclose")) {
    const panel = document.getElementById("craftpanel");
    if (panel) panel.hidden = true;
    shellCraftExpanded(false);
    const b = document.getElementById("craftaction");
    if (b) b.focus({ preventScroll: true });
    return;
  }
  // After 03's own listener has toggled it (this one is registered later).
  if (e.target.closest("#craftaction")) {
    const panel = document.getElementById("craftpanel");
    shellCraftExpanded(panel && !panel.hidden);
  }
});
document.addEventListener("keydown", e => {
  const panel = document.getElementById("craftpanel");
  if (e.key === "Escape" && panel && !panel.hidden) {
    panel.hidden = true;
    shellCraftExpanded(false);
  }
});

// --- the world's name in the top bar -----------------------------------------------------
onRender(function shellWorld(s) {
  const name = document.getElementById("world-name");
  if (name && s && typeof s.world === "string") name.textContent = s.world;
});

shellPaint(SHELL_MODE, false);

// The background music (music.js): it starts in the mode the table opened in, and the
// Music button turns it on or off without touching its level (the Settings slider's).
(function () {
  const btn = document.getElementById("musictoggle");
  const on = () => { try { return !window.PGMPrefs || PGMPrefs.get("music.on") !== false; } catch (err) { return true; } };
  const paint = () => {
    if (!btn) return;
    btn.setAttribute("aria-pressed", on() ? "true" : "false");
    btn.textContent = on() ? "Music" : "Music off";
  };
  if (window.Music) {
    const fighting = !!(STATE && STATE.scene && STATE.scene.in_encounter);
    try { Music.start(fighting ? "battle" : "ambient"); } catch (err) { /* silence */ }
  }
  if (btn) {
    btn.addEventListener("click", () => {
      try { if (window.PGMPrefs) PGMPrefs.set("music.on", !on()); } catch (err) { /* */ }
      paint();
    });
    try { if (window.PGMPrefs) PGMPrefs.on("music.on", paint); } catch (err) { /* */ }
    paint();
  }
})();

// Settings without leaving the table (the owner, 2026-10-05: "as it is now i have to go to
// the main page then to settings"). The panel holds the shelf's own Settings page in a frame
// (`/?tab=settings&embed=1`), loaded fresh on each open, so there is one Settings page and
// it always shows what is set now. Sound and music levels changed in it reach this window
// at once through the `storage` event prefs.js already listens to.
(function () {
  const btn = document.getElementById("settingsbtn");
  const layer = document.getElementById("settingslayer");
  const frame = document.getElementById("settingsframe");
  const close = document.getElementById("settingsclose");
  if (!btn || !layer || !frame || !close) return;
  function open(at, note) {
    // `at` opens a part of Settings already unfolded: "report" is the stalled model's
    // "Make a report" (04-combat-and-turns.js), and `note` the sentence it stood beside.
    let src = "/?tab=settings&embed=1";
    if (at === "report") {
      src += "&report=1" + (note ? "&note=" + encodeURIComponent(String(note).slice(0, 600)) : "");
    }
    frame.src = src;
    layer.hidden = false;
    close.focus();
  }
  // Named `showSettingsAt` because it shows a panel, never a window: nothing on the table
  // pops a window out (tests/test_s6_panel_shell.py greps for the browser's own call).
  window.showSettingsAt = open;
  function shut() {
    if (layer.hidden) return;
    layer.hidden = true;
    frame.src = "about:blank";
    btn.focus();
  }
  btn.addEventListener("click", () => open());
  close.addEventListener("click", shut);
  // Esc on the panel's own bar; inside the frame the page posts `close-settings`, because a
  // key pressed in a frame never reaches the page around it.
  layer.addEventListener("keydown", e => {
    if (e.key === "Escape") { e.preventDefault(); shut(); }
    // The panel is modal: Tab from Close goes into the frame and back, never to the table.
    if (e.key === "Tab" && e.target === close) { e.preventDefault(); frame.focus(); }
  });
  window.addEventListener("message", e => {
    if (e.origin === location.origin && e.data && e.data.pgm === "close-settings") shut();
  });
  layer.addEventListener("click", e => { if (e.target === layer) shut(); });
})();
