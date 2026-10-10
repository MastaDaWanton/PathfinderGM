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
// It returns {checked, covered}: `covered` lists each visible control whose centre point
// belongs to something else, with what is on top. An empty list is the pass.
(() => {
  const sel = "button, a[href], input:not([type=hidden]), select, textarea, [role=button], [tabindex='0']";
  const seen = [...document.querySelectorAll(sel)].filter((el) => {
    if (el.closest("[hidden]")) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    if (r.bottom < 0 || r.right < 0 || r.top > innerHeight || r.left > innerWidth) return false;
    const cs = getComputedStyle(el);
    return cs.visibility !== "hidden" && cs.display !== "none" && cs.pointerEvents !== "none";
  });
  const name = (el) => el.id ? "#" + el.id
    : el.tagName.toLowerCase() + (el.className && typeof el.className === "string"
      ? "." + el.className.trim().split(/\s+/).join(".") : "");
  const covered = [];
  for (const el of seen) {
    // The middle of the part on screen, not of the whole box: the story pane runs past the
    // window, and the centre of all of it sits under the top bar (a false alarm, measured).
    const r = el.getBoundingClientRect();
    const left = Math.max(r.left, 0), right = Math.min(r.right, innerWidth);
    const upper = Math.max(r.top, 0), lower = Math.min(r.bottom, innerHeight);
    const x = (left + right) / 2, y = (upper + lower) / 2;
    const top = document.elementFromPoint(x, y);
    if (top && top !== el && !el.contains(top) && !top.contains(el)) {
      covered.push({control: name(el), label: (el.innerText || el.value || el.getAttribute("aria-label") || "").trim().slice(0, 40), under: name(top)});
    }
  }
  return {checked: seen.length, covered};
})();
