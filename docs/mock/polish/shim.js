// The globals the board's code reads in the game and that live outside the board's own
// files, copied verbatim from where the game defines them. Loaded before every variant.

// play/static/js/table/01-core.js line 8, with the boot payload replaced by the panel's
// scene (panel.js sets it before the first renderMap, as 02-state.js render() does).
let STATE = null;
// play/static/js/table/01-core.js line 9
const $ = s => document.querySelector(s);
// play/static/js/table/06-trade-and-page.js lines 746-747
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
