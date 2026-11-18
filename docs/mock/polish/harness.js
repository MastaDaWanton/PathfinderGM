// The harness: two panels, one set of controls. Each panel is an iframe (panel.html) so
// a variant's globals and CSS cannot reach the other panel's.
(function () {
  "use strict";
  const $ = s => document.querySelector(s);
  const q = new URLSearchParams(location.search);
  const view = {
    scene: q.get("scene") || "A",
    view: q.get("view") === "3d" ? "3d" : "flat",
    turn: Number(q.get("turn") || 0),
    spell: q.get("spell") === "1",
    level: 0,
  };
  let variant = q.get("v") || "current";
  let size = q.get("size") || "880x600";
  let layout = q.get("layout") === "flick" ? "flick" : "side";
  let showing = "left";
  const frames = { left: $("#frame-left"), right: $("#frame-right") };

  function src(v) {
    const p = new URLSearchParams({ v, scene: view.scene, view: view.view,
                                    turn: String(view.turn), spell: view.spell ? "1" : "0" });
    return `panel.html?${p}`;
  }

  // Kept in the address bar, so a comparison can be linked to.
  function remember() {
    const p = new URLSearchParams({ v: variant, scene: view.scene, view: view.view,
                                    turn: String(view.turn), size, layout });
    if (view.spell) p.set("spell", "1");
    history.replaceState(null, "", `?${p}`);
  }

  function send() {
    for (const f of Object.values(frames)) {
      if (f.contentWindow) f.contentWindow.postMessage({ kind: "set", ...view }, "*");
    }
    paint();
  }

  function paint() {
    document.querySelectorAll("[data-view]").forEach(b =>
      b.setAttribute("aria-pressed", String(b.dataset.view === view.view)));
    document.querySelectorAll("[data-turn]").forEach(b => { b.disabled = view.view !== "3d"; });
    document.querySelectorAll("[data-layout]").forEach(b =>
      b.setAttribute("aria-pressed", String(b.dataset.layout === layout)));
    $("#scene").value = view.scene;
    $("#spell").checked = view.spell;
    $("#size").value = size;
    const [w, h] = size.split("x").map(Number);
    for (const f of Object.values(frames)) { f.style.width = `${w}px`; f.style.height = `${h}px`; }
    const panels = $("#panels");
    panels.className = `panels ${layout}`;
    panels.style.setProperty("--w", `${w}px`);
    panels.style.setProperty("--h", `${h}px`);
    $("#flick").hidden = layout !== "flick";
    $("#left").hidden = layout === "flick" && showing !== "left";
    $("#right").hidden = layout === "flick" && showing !== "right";
    remember();
  }

  function loadFrames() {
    frames.left.src = src("current");
    frames.right.src = src(variant);
    paint();
  }

  async function describe(name) {
    try {
      const meta = await fetch(`variants/${encodeURIComponent(name)}/variant.json`).then(r => r.json());
      $("#right-name").textContent = meta.title || meta.name || name;
      return meta;
    } catch { $("#right-name").textContent = name; return null; }
  }

  async function boot() {
    const list = await fetch("variants/index.json").then(r => r.json());
    const names = list.variants || ["current"];
    if (!names.includes(variant)) variant = "current";
    $("#variant").innerHTML = names.map(n => `<option value="${n}">${n}</option>`).join("");
    $("#variant").value = variant;
    await describe(variant);
    loadFrames();
  }

  document.addEventListener("click", e => {
    const v = e.target.closest("[data-view]");
    if (v) { view.view = v.dataset.view; send(); return; }
    const t = e.target.closest("[data-turn]");
    if (t) { view.turn = (view.turn + Number(t.dataset.turn) + 4) % 4; send(); return; }
    const l = e.target.closest("[data-layout]");
    if (l) { layout = l.dataset.layout; showing = "left"; paint(); return; }
    if (e.target.closest("#flick")) { showing = showing === "left" ? "right" : "left"; paint(); }
  });
  $("#scene").addEventListener("change", e => { view.scene = e.target.value; send(); });
  $("#spell").addEventListener("change", e => { view.spell = e.target.checked; send(); });
  $("#size").addEventListener("change", e => { size = e.target.value; paint(); });
  $("#variant").addEventListener("change", async e => {
    variant = e.target.value;
    await describe(variant);
    frames.right.src = src(variant);
    paint();
  });
  // Space flicks, in flick mode, so the eye can stay on the board.
  document.addEventListener("keydown", e => {
    if (layout === "flick" && e.key === " " && !e.target.closest("select, input")) {
      e.preventDefault();
      showing = showing === "left" ? "right" : "left";
      paint();
    }
  });
  // A panel's own Flat / 3D / Turn / floor buttons: the other panel follows.
  window.addEventListener("message", e => {
    const m = e.data || {};
    if (m.kind !== "view") return;
    view.view = m.view; view.turn = m.turn; view.level = m.level;
    send();
  });

  boot();
})();
