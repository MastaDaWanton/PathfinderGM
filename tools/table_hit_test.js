// Every control the player can see on the table, hit-tested where a mouse would land.
//
// 0.2.13 shipped with an invisible full-screen layer over the table (#harvest, opacity 0,
// z 35, laid out because its own display rule outranked [hidden]), and every real click
// landed on it. Nothing caught it: the provers check the backend and the shell's lifecycle,
// and the tests that click do it with element.click(), which never asks the browser what
// is under the pointer. This asks exactly that.
//
// Run it in the page (the preview tools' javascript_exec, or a browser console) on /play/
// served by the PACKAGED backend over scratch data, as docs/packaging.md's release steps say.
// It returns {checked, covered, unreachable}: `covered` lists each visible control whose
// on-screen middle belongs to something else, with what is on top; `unreachable` lists each
// control a turn cannot do without (MUST_SHOW) that sits in a box too short to show it
// whole at any scroll, with the box's height. Both empty is the pass.
//
// Why the second list: a control scrolled wholly out of its box is not "seen", so it was
// never checked. On integrate/0.2.25 and master 0.2.24 alike, in a fight at 794x608, the
// desk's choices were a 17px strip holding the 355px combat bar; End turn (34px) could not
// be shown whole at any scroll, a mouse wheel's 100px step skipped past it, and this
// script passed. Below the foot of a box that can show it (End turn 3 to 63px under the
// choices at 1000x609, 1024x700 and 1280x720) is one scroll away, and is not listed: the
// book keeps 45% of the stage and the desk's choices scroll past that by design.
(() => {
  // What a fight cannot be played without, and the pen. Up and down only: on a phone the
  // turn's buttons are one row that scrolls sideways by design (the mock README's phone).
  const MUST_SHOW = ["#cb-commit", "#cb-end", "#input", "#sayform button[type=submit]"];
  // The part of a control the player can actually see: its box cut to the window and to
  // every ancestor that clips its overflow. Two false alarms measured on 2026-10-10, both
  // "That's wrong" links on beats scrolled out of the story pane (#bookin): inside the
  // window, outside the pane, so the point "on" them was the music toggle and the Say form.
  // And the middle of that part, not of the whole box: the story pane itself runs past the
  // window, and the centre of all of it sits under the top bar.
  const shown = (el) => {
    const r = el.getBoundingClientRect();
    let left = Math.max(r.left, 0), right = Math.min(r.right, innerWidth);
    let upper = Math.max(r.top, 0), lower = Math.min(r.bottom, innerHeight);
    for (let p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.overflowX === "visible" && cs.overflowY === "visible") continue;
      const c = p.getBoundingClientRect();
      left = Math.max(left, c.left); right = Math.min(right, c.right);
      upper = Math.max(upper, c.top); lower = Math.min(lower, c.bottom);
    }
    return right - left >= 2 && lower - upper >= 2 ? {x: (left + right) / 2, y: (upper + lower) / 2} : null;
  };
  const sel = "button, a[href], input:not([type=hidden]), select, textarea, [role=button], [tabindex='0']";
  const seen = [...document.querySelectorAll(sel)].filter((el) => {
    if (el.closest("[hidden]")) return false;
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || cs.display === "none" || cs.pointerEvents === "none") return false;
    return shown(el) !== null;
  });
  const name = (el) => el.id ? "#" + el.id
    : el.tagName.toLowerCase() + (el.className && typeof el.className === "string"
      ? "." + el.className.trim().split(/\s+/).join(".") : "");
  const covered = [];
  for (const el of seen) {
    const {x, y} = shown(el);
    const top = document.elementFromPoint(x, y);
    if (top && top !== el && !el.contains(top) && !top.contains(el)) {
      covered.push({control: name(el), label: (el.innerText || el.value || el.getAttribute("aria-label") || "").trim().slice(0, 40), under: name(top)});
    }
  }
  // The tallest the window onto a control can be: the window cut to every ancestor that
  // clips up and down, wherever the control itself is scrolled to.
  const room = (el) => {
    let upper = 0, lower = innerHeight;
    for (let p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
      if (getComputedStyle(p).overflowY === "visible") continue;
      const c = p.getBoundingClientRect();
      upper = Math.max(upper, c.top); lower = Math.min(lower, c.bottom);
    }
    return Math.max(0, lower - upper);
  };
  const unreachable = [];
  for (const el of MUST_SHOW.flatMap((s) => [...document.querySelectorAll(s)])) {
    if (el.closest("[hidden]")) continue;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || el.getClientRects().length === 0) continue;
    const box = room(el), of = el.getBoundingClientRect().height;
    if (box < of) unreachable.push({control: name(el), box: Math.round(box), of: Math.round(of)});
  }
  return {checked: seen.length, covered, unreachable};
})();
