// One panel: one variant drawing one scene. Loaded in its own iframe, so two variants'
// globals and stylesheets never meet.
//
// URL: panel.html?v=<variant>&scene=<A|B-dawn|B-noon|B-night>&view=<flat|3d>&turn=<0-3>
//      &spell=<0|1>
// The harness then sends {kind: "set", ...the same keys} by postMessage; the panel tells
// the harness {kind: "view", view, turn, level} whenever its own board controls change
// them, so both panels stay looking the same way.
(function () {
  "use strict";
  const q = new URLSearchParams(location.search);
  const want = {
    v: q.get("v") || "current",
    scene: q.get("scene") || "A",
    view: q.get("view") || "flat",
    turn: Number(q.get("turn") || 0),
    spell: q.get("spell") === "1",
  };
  const base = `variants/${encodeURIComponent(want.v)}/`;

  function fail(msg) {
    document.body.insertAdjacentHTML("beforeend", `<pre id="polish-error">${esc(msg)}</pre>`);
    throw new Error(msg);
  }

  // A deep copy of the scene's state, with the spell's area laid into grid.areas when
  // asked: the shape views._latest_areas sends after a real cast.
  function stateFor(name, spell) {
    const sc = window.POLISH_DATA.scenes[name];
    if (!sc) fail(`no scene ${name} in data.js`);
    const s = JSON.parse(JSON.stringify(sc.state));
    if (spell && s.scene.grid) s.scene.grid.areas = [sc.extras.spell_area.as_grid_area];
    // The extras ride along for variants that draw previews; the game's renderMap never
    // reads them.
    window.POLISH_SCENE = sc;
    return s;
  }

  function draw() {
    STATE = stateFor(want.scene, want.spell);
    MAP_3D = want.view === "3d";
    MAP_TURN = ((want.turn % 4) + 4) % 4;
    renderMap(STATE);
  }

  function load(src, kind) {
    return new Promise((ok, no) => {
      const el = kind === "css" ? document.createElement("link") : document.createElement("script");
      if (kind === "css") { el.rel = "stylesheet"; el.href = base + src; }
      else { el.src = base + src; el.async = false; }
      el.onload = ok;
      el.onerror = () => no(new Error(`${want.v}: could not load ${src}`));
      document.head.appendChild(el);
    });
  }

  async function boot() {
    const meta = await fetch(base + "variant.json").then(r => {
      if (!r.ok) throw new Error(`no variant ${want.v} (${r.status})`);
      return r.json();
    });
    const files = meta.files || {};
    const markup = await fetch(base + (files.markup || "board.html")).then(r => r.text());
    document.body.insertAdjacentHTML("afterbegin", markup);
    await Promise.all((files.styles || ["board.css"]).map(f => load(f, "css")));
    for (const f of (files.scripts || ["scene3d.js", "map.js"])) await load(f, "js");
    draw();
    document.documentElement.dataset.ready = "1";
  }

  window.addEventListener("message", e => {
    const m = e.data || {};
    if (m.kind !== "set") return;
    for (const k of ["scene", "view", "turn", "spell"]) if (k in m) want[k] = m[k];
    if ("level" in m) MAP_LEVEL = m.level;
    draw();
  });

  // After the board's own Flat / 3D / Turn / floor buttons have done their work (the
  // timeout lets the variant's own listener, registered later, run first), tell the
  // harness.
  document.addEventListener("click", e => {
    if (!e.target.closest("[data-mapview], [data-mapturn], [data-maplevel]")) return;
    setTimeout(() => {
      want.view = MAP_3D ? "3d" : "flat";
      want.turn = MAP_TURN;
      parent.postMessage({ kind: "view", from: want.v, view: want.view, turn: MAP_TURN,
                           level: MAP_LEVEL }, "*");
    });
  });

  boot().catch(err => fail(err.message));
})();
