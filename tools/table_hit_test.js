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
// It returns {checked, covered}: `covered` lists each visible control whose on-screen middle
// belongs to something else, with what is on top. An empty list is the pass.
(() => {
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
  return {checked: seen.length, covered};
})();
