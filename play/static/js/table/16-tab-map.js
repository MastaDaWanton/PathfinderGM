// The play table, part 16 (the Map tab). Classic script, sharing one global scope.
//
// The board takes the book's place, with the desk and the pen under it (the approved
// design, docs/mock/table-layout/README.md, "Map is a tab, Talk is a tray"). Three ways of
// looking, in one head row: the ground you stand on, Flat or 3D, drawn by the app's own
// renderers (03's `renderMap`, scene3d.js) exactly as before, a lit square still queuing a
// move in the combat bar (04); and Places, the owner's fog-of-war chart of the town
// (16-places-chart.js draws it from `scene.places_found`).
//
// Places is its own button, left of Flat and 3D, in the space the owner circled ("add
// another button that displays the map you built in your mock-up but with the fog of
// war"), because it is a different map: the town, not the ground. Pressed, the board
// becomes the chart; pressed again, or Flat or 3D, it is the ground again as it was left.
// The ground's own controls keep their room but go out of use (hidden by visibility, not
// removed), so nothing in the head row moves under the pointer that pressed Places.
//
// WALK THERE attaches the DESTINATION as one place chip (11's `exitChip` into 10's
// `attachPlace`, the one chip slot), and one Say walks the whole way: `/api/say` takes a
// far place the chart can walk to (play/views.py `_read_place`, `places_found.walk_to`)
// and the engine walks every hop of it in one turn, rolling once for each place and
// asking the watch at each way out (`Engine._op_travel`). Never sent by the page: the
// owner ruled that a way on "should attach like a spell does and then apply when you
// send".
//
// Stage 3 attached one leg a turn — zMUD's "slow walking" rather than its speedwalk
// (Zuggsoft, "Speedwalking and Slow Walking": a step at a time "with the ability to
// abort", because "once your commands have been sent to the MUD, there is no way to
// cancel them"), chosen so no turn went out unpressed. The owner overruled it after the
// 0.2.0 playtest (2026-09-30): "I should not be forced to play a whole turn for each
// connecting point." What made the slow walk necessary in a MUD is not true here: the
// whole walk is one engine op, and the engine is the thing that stops it — a meeting that
// stops you, the watch at a gate, a fight — and says so in the tell, the roguelike's
// interrupted travel (Angband, DCSS). This is Inform's *Approaches*: GO TO a known place,
// one command, the route walked through visited rooms. So the abort a slow walk gave the
// player is the engine's to give now, and Walk there again goes on from wherever the walk
// was stopped, on the chart's route from there.

const MAPV = {
  places: false,  // the chart is shown instead of the ground
  sel: null,      // the place pressed on the chart
  said: "",       // the line the last Walk there left in the slip
  walk: null,     // { to, name, leg: {from, to, name} } while a walk is under way
  k: 1,           // the chart's drawing units per screen pixel (16-places-chart.js)
  // Which map the tabletop shows (phase 3 of docs/place-map-v2-build-plan.md): the town, the
  // Region (the nation you stand in, or the one opened), the Continent, the World. A nation or
  // continent of "" is the one the party is in. Below the town, the Site (phase 4): a cave, a
  // dungeon or the sewers, `site` its id in `scene.known_places.sites`.
  level: "town", nation: "", continent: "", site: "",
};

// The sites known (play/atlas.py), and the one a place belongs to: its way in, or a room in it.
function mapSites(s) { return ((s && s.scene && s.scene.known_places) || {}).sites || []; }
function siteOfRoom(s, id) { return mapSites(s).find(st => st.rooms.some(r => r.id === id)) || null; }
// The map a site's way up opens: the town when it lies under a place inside the walls, else the
// Region round it (the cave off the woods).
function siteUp(st, pf) {
  const host = pf && pf.nodes.find(n => n.id === st.host);
  return host && host.setting === "in" ? "town" : "nation";
}

// The world for the maps above the town: `atlasFor` (16-places-world.js) reads `/api/atlas`
// once and draws again when it lands; this tab sends nothing itself.
function atlasFor(s) { return placesAtlas(s, () => renderPlaces(STATE)); }

// What the maps above the town are showing.
function mapView(s) {
  const kp = (s && s.scene && s.scene.known_places) || {}, W = atlasFor(s);
  if (!W || !Array.isArray(W.cities)) return null;
  const home = kp.town || "", hc = W.cities.find(c => c.id === home) || {};
  const nation = MAPV.nation || hc.nation || "";
  const continent = MAPV.continent || (W.nations[nation] || {}).continent || hc.continent || "";
  return { W, KP: kp, home, homeNation: hc.nation || "", nation, continent, K: PlacesWorld.worldKnown(W, kp) };
}

// Open a map: from the breadcrumb, an arrow on the board, a slip's button, the zoom gesture.
function mapOpen(level, arg) {
  MAPV.level = ["town", "nation", "continent", "world", "site"].includes(level) ? level : "town";
  MAPV.sel = null;
  if (!MAPV.walk) MAPV.said = "";
  if (MAPV.level === "nation") {
    MAPV.nation = arg || "";
    MAPV.continent = arg && ATLAS.data && ATLAS.data.nations[arg] ? ATLAS.data.nations[arg].continent : "";
  } else if (MAPV.level === "continent") MAPV.continent = arg || MAPV.continent;
  else if (MAPV.level === "site") MAPV.site = arg || MAPV.site;
  mapPaint();
  renderPlaces(STATE);
}

function mapTitle(pf) {
  if (MAPV.level === "site") return upFirst(((mapSites(STATE).find(st => st.id === MAPV.site)) || {}).name || "Below");
  const v = MAPV.level === "town" ? null : mapView(STATE);
  if (!v) return (pf && pf.where) || "The town";
  if (MAPV.level === "nation") return (v.W.nations[v.nation] || {}).name || "The region";
  if (MAPV.level === "continent") return v.W.continents[v.continent] || "The continent";
  return v.W.world || "The world";
}

// The tabletop (js/places-board.js, the owner's choice of the 2026-11-18 mocks): an ES
// module, imported on first use so the rest of the table never waits on Three.js. Without
// WebGL, if the module fails to load, or when the context is lost, Places draws the chart
// above from the same state instead (owner decision 3: the chart stays as the fallback,
// revisited after one release). `state`: "" not tried, "loading", "board", "chart".
const BOARD = { state: "", mod: null, here: "", where: "", ids: null, path: null };

function boardReady() {
  if (BOARD.state === "") {
    const url = window.PATHFINDER_BOOT && window.PATHFINDER_BOOT.placesBoard;
    let gl = false;
    try { gl = !!document.createElement("canvas").getContext("webgl2"); } catch (_) { gl = false; }
    BOARD.state = url && gl ? "loading" : "chart";
    if (BOARD.state === "loading") {
      import(url).then(m => { BOARD.mod = m; BOARD.state = "board"; renderPlaces(STATE); })
        .catch(err => { console.warn("The tabletop did not load; drawing the chart:", err); BOARD.state = "chart"; renderPlaces(STATE); });
    }
  }
  return BOARD.state;
}

function mapShowingPlaces() { return MAPV.places; }

function mapPlacesData(s) {
  const pf = s && s.scene && s.scene.places_found;
  return pf && Array.isArray(pf.nodes) ? pf : null;
}

// The head row and which of the two boards is shown. Called by 03 after every drawing of
// the ground and here after every change of view.
function mapPaint() {
  const frame = document.getElementById("boardframe");
  if (!frame) return;
  const places = MAPV.places;
  frame.classList.toggle("places", places);
  frame.classList.toggle("threed", !places && typeof MAP_3D !== "undefined" && MAP_3D);
  const btn = document.getElementById("placesbtn");
  if (btn) btn.setAttribute("aria-pressed", String(places));
  const ground = document.getElementById("groundctl");
  if (ground) {
    ground.style.visibility = places ? "hidden" : "";
    ground.querySelectorAll("[data-mapview]").forEach(b => {
      const on = !places && (b.dataset.mapview === "3d") === !!(typeof MAP_3D !== "undefined" && MAP_3D);
      b.setAttribute("aria-pressed", String(on));
    });
    // Out of use while hidden: the keyboard cannot reach what the eye cannot see.
    ground.inert = places;
  }
  const wrap = document.getElementById("placeswrap");
  if (wrap) wrap.hidden = !places;
  const name = document.getElementById("board-name");
  if (name) {
    const pf = mapPlacesData(STATE);
    name.textContent = places ? mapTitle(pf) : (frame.dataset.ground || "The ground");
  }
}

// --- the chart ---------------------------------------------------------------------------
function renderPlaces(s) {
  const wrap = document.getElementById("placeswrap");
  if (!wrap || !MAPV.places) return;
  const pf = mapPlacesData(s);
  if (!pf || !pf.nodes.length) {
    wrap.innerHTML = `<p class="panelempty">Nowhere is charted yet. The chart is drawn from
      the places you have stood in and the ways out of them, as soon as you are standing
      somewhere.</p>`;
    return;
  }
  const how = boardReady();
  if (how === "chart") MAPV.level = "town";   // the chart is of the town only
  const isCity = id => !!(ATLAS.data && Array.isArray(ATLAS.data.cities) && ATLAS.data.cities.some(c => c.id === id));
  if (MAPV.sel && !pf.nodes.some(n => n.id === MAPV.sel && !n.current) && !(MAPV.level !== "town" && isCity(MAPV.sel))) MAPV.sel = null;
  if (how !== "chart") { renderBoard(s, wrap, pf, how); return; }
  const focused = document.activeElement && document.activeElement.closest
    && (document.activeElement.closest("[data-node]") || document.activeElement.closest("[data-walkto]"));
  const refocus = focused ? (focused.dataset.node ? `[data-node="${CSS.escape(focused.dataset.node)}"]`
                                                  : ".walkthere") : null;
  // The chart's scale follows what is found (the frame fits it) and the ink is sized in
  // screen pixels, so the scale and the frame are settled together: a few rounds, each
  // within a percent of the last by the third (the mock's own loop).
  for (let round = 0; round < 5; round++) {
    wrap.innerHTML = `<div class="placemap"><div class="chart v2-chart-paper">${
        PlacesChart.svg(pf, { sel: MAPV.sel, k: MAPV.k })}</div>
      <div class="maprail">${PlacesChart.slip(pf, { sel: MAPV.sel, said: MAPV.said,
        walking: MAPV.walk && MAPV.walk.to })}</div></div>
      <div class="boardfoot"><p class="boardabout" id="places-about">${esc(PlacesChart.header(pf))}</p>
      <p class="boardkey">${PlacesChart.key(pf)}</p></div>`;
    const svg = wrap.querySelector(".chart svg");
    if (!svg) break;
    const vb = svg.viewBox.baseVal, r = svg.getBoundingClientRect();
    if (!r.width || !r.height) break;
    const next = Math.max(vb.width / r.width, vb.height / r.height);
    if (Math.abs(next - MAPV.k) / next < .01) break;
    MAPV.k = next;
  }
  if (refocus) { const again = wrap.querySelector(refocus); if (again) again.focus({ preventScroll: true }); }
}

// The tabletop's frame is built once and kept: the 3D stage lives across states, and only
// the slip, the foot and the keyboard's list of places are written again each time.
function renderBoard(s, wrap, pf, how) {
  let map = wrap.querySelector(".placemap.tabletop");
  if (!map) {
    wrap.innerHTML = `<div class="placemap tabletop"><div class="chart board3d"></div>
      <div class="maprail"></div></div>
      <div class="boardfoot"><p class="boardabout" id="places-about"></p>
      <p class="boardkey"><span class="pk been"></span>stood in, painted
      <span class="pk seen"></span>seen, grey<span class="pk here"></span>you</p></div>`;
    map = wrap.querySelector(".placemap.tabletop");
  }
  const stage = map.querySelector(".board3d");
  if (how === "board" && !stage.dataset.live) {
    stage.dataset.live = "1";
    BOARD.mod.init(stage, {
      statics: (window.PATHFINDER_BOOT && window.PATHFINDER_BOOT.statics) || "/static/",
      pick: id => pickPlace(id),
      open: (level, arg) => mapOpen(level, arg),
      world: PlacesWorld,
      lost: () => { BOARD.state = "chart"; renderPlaces(STATE); },
    });
  }
  // Walked into a site, the Site opens; walked out of the one shown, its way up does.
  if (pf.here !== BOARD.here) {
    const now = siteOfRoom(s, pf.here), was = siteOfRoom(s, BOARD.here);
    const to = now && (!was || was.id !== now.id) ? ["site", now.id]
      : was && !now && MAPV.level === "site" && MAPV.site === was.id ? [siteUp(was, pf), ""] : null;
    if (to) { MAPV.level = to[0]; MAPV.site = to[1] || MAPV.site; MAPV.sel = null; mapPaint(); }
  }
  const site = MAPV.level === "site" ? mapSites(s).find(st => st.id === MAPV.site) : null;
  if (MAPV.level === "site" && !site) { MAPV.level = "town"; mapPaint(); }   // a site of another town, left behind
  const above = MAPV.level !== "town" && MAPV.level !== "site";
  const v = above ? mapView(s) : null;
  atlasFor(s);   // fetched early, so the breadcrumb has names and the first press up is quick
  if (above && !v) {   // the atlas is on its way: renderPlaces runs again when it lands
    map.querySelector(".maprail").innerHTML = mapCrumbs(null, pf) + `<div class="mapnote"><p>Unrolling the map…</p></div>`;
    return;
  }
  const focused = document.activeElement && document.activeElement.closest
    && (document.activeElement.closest("[data-node]") || document.activeElement.closest("[data-walkto]"));
  const refocus = focused ? (focused.dataset.node ? `[data-node="${CSS.escape(focused.dataset.node)}"]`
                                                  : ".walkthere") : null;
  map.querySelector(".maprail").innerHTML = mapCrumbs(v || mapView(s), pf, site) + (v ? mapSlip(v, pf)
    : site && !MAPV.sel ? siteSlip(site, pf)
    : PlacesChart.slip(pf, { sel: MAPV.sel, said: MAPV.said, walking: MAPV.walk && MAPV.walk.to }))
    + (MAPV.level === "town" || (MAPV.level === "nation" && v && v.homeNation === v.nation) ? waysDown(s, pf) : "");
  wrap.querySelector("#places-about").textContent = v ? mapAbout(v) : site ? siteAbout(site) : PlacesChart.header(pf);
  // The board is drawn on a canvas, which the keyboard cannot reach, so every place found is
  // also a button: out of sight until it takes the focus, then a list over the board.
  let keys = stage.querySelector(".boardkeys");
  if (!keys) { stage.insertAdjacentHTML("beforeend", `<div class="boardkeys" aria-label="Places found"></div>`); keys = stage.querySelector(".boardkeys"); }
  keys.innerHTML = (site ? siteKeys(site, pf) : mapKeys(v, pf)).map(([id, name]) =>
    `<button type="button" class="v2-btn" data-node="${esc(id)}" aria-pressed="${MAPV.sel === id}">${esc(upFirst(name))}</button>`).join("");
  if (refocus) { const again = wrap.querySelector(refocus); if (again) again.focus({ preventScroll: true }); }
  if (how !== "board") return;
  // Where the party walked this turn, for the miniature to go the same way: the walk the
  // chart attached, up to where the engine stopped it, else straight from the last place.
  let came = null;
  if (BOARD.here && pf.here !== BOARD.here && pf.where === BOARD.where) {
    const path = BOARD.path || [], k = path.indexOf(pf.here);
    came = path[0] === BOARD.here && k > 0 ? path.slice(0, k + 1) : [BOARD.here, pf.here];
    BOARD.path = null;
  }
  const ids = new Set(pf.nodes.map(n => n.id));
  const fresh = BOARD.ids && pf.where === BOARD.where ? new Set([...ids].filter(i => !BOARD.ids.has(i))) : new Set();
  BOARD.here = pf.here; BOARD.where = pf.where; BOARD.ids = ids;
  const minutes = Number((s.scene || {}).clock_minutes) || 0;
  const route = v && MAPV.sel && v.K.how[MAPV.sel] ? PlacesWorld.worldRoute(v.K, v.home, MAPV.sel) : null;
  BOARD.mod.draw({ level: MAPV.level, pf, sel: MAPV.sel, hour: (minutes % 1440) / 60, came, fresh,
                   reduced: matchMedia("(prefers-reduced-motion: reduce)").matches,
                   ...(v || {}), route: route ? [v.home, ...route.map(l => l.to)] : null,
                   sites: mapSites(s), site, up: site ? siteUp(site, pf) : "" });
}

// --- the slips of the maps above the town ----------------------------------------------------
function mapCrumbs(v, pf, site) {
  const W = v && v.W, here = MAPV.level;
  const rows = [["world", (W && W.world) || "World", ""],
                ["continent", (W && W.continents[v.continent]) || "Continent", (v && v.continent) || ""],
                ["nation", (W && (W.nations[v.nation] || {}).name) || "Region", (v && v.nation) || ""],
                ["town", (pf && pf.where) || "Town", ""]];
  if (site) rows.push(["site", upFirst(site.name), site.id]);
  return `<nav class="mapcrumbs" aria-label="Maps">${rows.map(([lv, name, arg]) =>
    `<button type="button" class="v2-btn" data-maplevel="${esc(lv)}" data-maparg="${esc(arg)}"${here === lv ? ' aria-current="page"' : ""}>${esc(name)}</button>`).join("")}</nav>`;
}

function mapAbout(v) {
  const n = Object.keys(v.K.how).length;
  return `${n} ${n === 1 ? "city" : "cities"} known. Point at the land to light it; press it, or zoom in, to go in. Zoom out past a map to open the one above.`;
}

const HOW_WORDS = { been: "stood in", road: "from road signs", heard: "heard of", map: "from maps" };
function mapHow(v, h) {
  const nm = id => (v.W.cities.find(c => c.id === id) || {}).name || "";
  return h.by === "been" ? "You have stood here."
    : h.by === "road" ? `A road out of ${esc(nm(h.from))} is signed for it.`
    : h.by === "heard" ? `Heard of in talk${h.who ? `, from ${esc(h.who)}` : ""}: “${esc(h.line)}”`
    : `On the map of ${esc((v.W.nations[h.nation] || {}).name || "")} you read.`;
}

function mapCitySlip(v, id) {
  const W = v.W, c = W.cities.find(x => x.id === id), h = v.K.how[id];
  if (!c || !h) return "";
  const nm = x => (W.cities.find(y => y.id === x) || {}).name || "";
  const legs = id === v.home ? null : PlacesWorld.worldRoute(v.K, v.home, id);
  const miles = legs ? legs.reduce((a, l) => a + (l.miles || 0), 0) : 0;
  const way = l => (l.by === "sea" ? "by sea" : `${l.miles ? `${l.miles} miles` : ""}${l.by === "river" ? " by river" : ""}`);
  const buttons = [
    MAPV.level === "continent" ? `<button type="button" class="v2-btn" data-maplevel="nation" data-maparg="${esc(c.nation)}">Open ${esc((W.nations[c.nation] || {}).name || "")}</button>` : "",
    id === v.home ? `<button type="button" class="v2-btn" data-maplevel="town" data-maparg="">Open the town map</button>` : "",
  ].join("");
  return `<div class="mapnote"><h3>${esc(c.name)}${id === v.home ? " <small>you are here</small>" : h.by === "been" ? "" : " <small>not yet visited</small>"}</h3>
    <p>${mapHow(v, h)}</p><p>${esc((W.nations[c.nation] || {}).name || "")}, ${esc(W.continents[c.continent] || "")}.</p>${
    legs ? `<ol class="route">${legs.map(l => `<li>${esc(nm(l.to))}<span>${esc(way(l))}</span></li>`).join("")}</ol>
      <p>About ${Math.max(1, Math.ceil(miles / 24))} days ${legs.every(l => l.by !== "sea" && l.by !== "river") ? "on foot" : "of travel"}${miles ? `, ${Number(miles)} miles` : ""}, by the roads you know. Journeys set out from the road out of town.</p>`
    : id === v.home ? "" : `<p class="shutwhy">No road you know goes there.</p>`}${buttons ? `<p>${buttons}</p>` : ""}</div>`;
}

function mapSlip(v, pf) {
  const W = v.W, said = MAPV.said ? `<div class="mapnote said"><p>${esc(MAPV.said)}</p></div>` : "";
  const sel = MAPV.sel, node = sel && pf.nodes.find(n => n.id === sel);
  const known = Object.keys(v.K.how);
  if (MAPV.level === "nation") {
    // A wild place round the town is the engine's own place: its slip, its Walk there.
    if (node) return PlacesChart.slip(pf, { sel, said: MAPV.said, walking: MAPV.walk && MAPV.walk.to });
    const N = W.nations[v.nation] || {}, homeHere = v.homeNation === v.nation;
    return said + (sel ? mapCitySlip(v, sel) : "") + `<div class="mapnote"><h3>${esc(N.name || "")}</h3>
      <p>${homeHere ? `You are in ${esc(pf.where || "")}. ` : ""}Each hex is about 12 miles across, some four hours on foot (Pathfinder's overland hex). Roads leaving ${esc(N.name || "")} end in an arrow with where they go.</p>
      <p>${homeHere ? `<button type="button" class="v2-btn" data-maplevel="town" data-maparg="">${esc(pf.where || "The town")}</button> ` : ""}<button type="button" class="v2-btn" data-maplevel="continent" data-maparg="${esc(N.continent || "")}">${esc(W.continents[N.continent] || "The continent")}</button></p></div>`;
  }
  if (MAPV.level === "continent") {
    const inC = id => (W.cities.find(c => c.id === id) || {}).continent === v.continent;
    const here = W.cities.find(c => c.id === v.home);
    const mine = known.filter(inC);
    const nations = [...new Set(mine.map(id => W.cities.find(c => c.id === id).nation))]
      .sort((a, b) => String(W.nations[a].name).localeCompare(W.nations[b].name));
    // Sea passages from the ports stood in: the engine's own (journey.legs_from, in the atlas).
    const ports = (v.KP.been || []).filter(inC).map(p => [p, W.routes.filter(r => r.by === "sea" && (r.a === p || r.b === p)).map(r => (r.a === p ? r.b : r.a))])
      .filter(x => x[1].length);
    const nm = id => (W.cities.find(c => c.id === id) || {}).name || "";
    return said + (sel ? mapCitySlip(v, sel) : "") + `<div class="mapnote"><h3>${esc(W.continents[v.continent] || "")}</h3>
      <p>${here && here.continent === v.continent ? `You are in ${esc(here.name)}, ${esc((W.nations[here.nation] || {}).name || "")}. ` : ""}${mine.length} ${mine.length === 1 ? "city" : "cities"} known here. Point at a nation to light it; press it, or zoom in on it, to open its region.</p>
      <p>${nations.map(n => `<button type="button" class="v2-btn" data-maplevel="nation" data-maparg="${esc(n)}">${esc(W.nations[n].name)}</button>`).join(" ")}</p></div>${
      ports.map(([p, to]) => `<div class="mapnote"><h3>By sea from ${esc(nm(p))}</h3><p>${to.map(nm).sort().map(esc).join(", ")}.</p></div>`).join("")}`;
  }
  const counts = { been: 0, road: 0, heard: 0, map: 0 };
  known.forEach(id => { counts[v.K.how[id].by]++; });
  const here = W.cities.find(c => c.id === v.home) || {};
  return said + (sel ? mapCitySlip(v, sel) : "") + `<div class="mapnote"><h3>${esc(W.world || "The world")}</h3>
    <p>${known.length} ${known.length === 1 ? "city" : "cities"} known: ${Object.entries(counts).map(([k, n]) => `${Number(n)} ${esc(HOW_WORDS[k])}`).join(", ")}.</p>
    <p>Point at a continent to light it; press it, or zoom in on it, to go in.</p>
    <p><button type="button" class="v2-btn" data-maplevel="continent" data-maparg="${esc(here.continent || "")}">${esc(W.continents[here.continent] || "Your continent")}</button></p></div>`;
}

// --- the Site --------------------------------------------------------------------------------
// The site's own slip, when no room is pressed (a room pressed has the town's slip, with its
// Walk there: a room is a place like any other, and the engine walks to it through rooms
// stood in only, `places_found.route`).
function siteSlip(st, pf) {
  const entered = st.rooms.filter(r => r.visited).length, seen = st.rooms.length - entered;
  const here = st.rooms.find(r => r.id === st.here), host = pf.nodes.find(n => n.id === st.host);
  const said = MAPV.said ? `<div class="mapnote said"><p>${esc(MAPV.said)}</p></div>` : "";
  return said + `<div class="mapnote"><h3>${esc(upFirst(st.name))}</h3>
    ${here ? `<p>You are in ${esc(here.name)}${here.about ? `: ${esc(here.about)}` : ""}.</p>` : ""}
    <p>${Number(entered)} ${entered === 1 ? "room" : "rooms"} entered${seen ? `, ${Number(seen)} seen and not yet entered` : ""}. Press a room for the way there.</p>
    <p><button type="button" class="v2-btn" data-maplevel="${esc(siteUp(st, pf))}" data-maparg="">Back up${host ? ` to ${esc(host.name)}` : ""}</button></p></div>`;
}
function siteAbout(st) {
  return "Rooms entered are built; rooms only seen are chalk outlines. Underground, the hour makes no difference. Zoom out past the site to go back up.";
}
function siteKeys(st, pf) {
  return st.rooms.filter(r => r.id !== pf.here).map(r => [r.id, r.name]);
}
// On the town and the Region round it: every site known beneath a place found, to go down to.
function waysDown(s, pf) {
  const down = mapSites(s).filter(st => pf.nodes.some(n => n.id === st.host));
  if (!down.length) return "";
  return `<div class="mapnote"><h3>Below ground</h3><p>${down.map(st => {
    const host = pf.nodes.find(n => n.id === st.host);
    return `<button type="button" class="v2-btn" data-maplevel="site" data-maparg="${esc(st.id)}">${esc(upFirst(st.name))}</button> <small>under ${esc(host.name)}</small>`;
  }).join("<br>")}</p></div>`;
}

// What the keyboard's list of places offers on each map: what that map's board can press.
function mapKeys(v, pf) {
  if (!v) return pf.nodes.filter(n => !n.current).map(n => [n.id, n.name]);
  const city = id => v.W.cities.find(c => c.id === id) || {};
  let ids = Object.keys(v.K.how);
  if (MAPV.level === "continent") ids = ids.filter(id => city(id).continent === v.continent);
  if (MAPV.level === "nation") ids = ids.filter(id => city(id).nation === v.nation);
  const out = ids.map(id => [id, city(id).name]).sort((a, b) => String(a[1]).localeCompare(b[1]));
  if (MAPV.level === "nation" && v.homeNation === v.nation) {
    pf.nodes.filter(n => n.setting === "outside" && !n.current && !/:@the-road-to-/.test(n.id)).forEach(n => out.push([n.id, n.name]));
  }
  return out;
}

// A place pressed, on the chart, the board, or the board's list of places.
function pickPlace(id) {
  MAPV.sel = id === MAPV.sel ? null : id;
  if (!MAPV.walk) MAPV.said = "";
  renderPlaces(STATE);
}

function mapShowPlaces(on) {
  MAPV.places = !!on;
  if (!on) MAPV.said = "";
  mapPaint();
  if (on) renderPlaces(STATE);
}

// --- walking by the chart ------------------------------------------------------------------
function mapWalkSay(line) {
  MAPV.said = line;
  if (typeof spellSay === "function") spellSay(line);
}

// Attach the place pressed as the turn's one place chip: the exits row's own way when it
// is next door, else the far way the chart walks to (11's `farWay`), the same rule the say
// door takes it by. Returns the node and its legs, or the reason it cannot be attached.
function mapAttachWalk(s, dest) {
  const scene = (s && s.scene) || {};
  const pf = mapPlacesData(s);
  const node = pf && pf.nodes.find(n => n.id === dest);
  const legs = (node && node.walk && node.walk.legs) || [];
  if (!legs.length) return { why: (node && node.why) || "No way there by the ways you know." };
  const first = (scene.exits || []).find(x => x.id === legs[0].to);
  if (!first || first.blocked) {
    return { why: first ? first.blocked : `${upFirst(legs[0].name)} is not a way on from here now.` };
  }
  const way = (scene.exits || []).find(x => x.id === dest) || farWay(s, dest);
  attachPlace(exitChip(way, !!scene.in_encounter));
  return { node, legs };
}

function walkThere(dest) {
  const got = mapAttachWalk(STATE, dest);
  if (!got.legs) { MAPV.walk = null; mapWalkSay(got.why); renderPlaces(STATE); return; }
  const n = got.legs.length;
  MAPV.walk = { to: dest, name: got.node.name, from: (mapPlacesData(STATE) || {}).here };
  BOARD.path = [MAPV.walk.from, ...got.legs.map(l => l.to)];
  mapWalkSay(n > 1
    ? `${upFirst(got.node.name)} is attached to your turn: the whole way, ${n} legs by the ways you know, in one turn. Press Say to go.`
    : `${upFirst(got.node.name)} is attached to your turn. Press Say to go.`);
  renderPlaces(STATE);
}

// After each state: arrived, stopped on the way (the engine's tell says by what), or not
// gone yet. The engine walked the whole way or stopped it; the page only says which.
onRender(function walkOn(s) {
  const w = MAPV.walk;
  if (!w) return;
  const pf = mapPlacesData(s);
  const here = pf && pf.here;
  const stop = line => { MAPV.walk = null; mapWalkSay(line); };
  if (here === w.from) {
    // Not gone yet. A refusal or a busy table keeps the chip (04's `takeTurn`); a chip
    // the player took back, or swapped for a spell, is the walk set aside.
    const c = typeof attachedChip === "function" ? attachedChip() : null;
    if (!c || c.kind !== "place" || c.id !== w.to) {
      stop(`The walk to ${w.name} is set aside. Walk there again to pick it up.`);
    }
    return;
  }
  if (here === w.to) { MAPV.walk = null; MAPV.sel = null; mapWalkSay(`You are at ${w.name}.`); return; }
  const at = (pf && (pf.nodes.find(n => n.current) || {}).name) || "here";
  stop(`The walk to ${w.name} stopped at ${at}${s.awaiting ? ": a roll is owed"
    : s.ended ? ": the story has ended" : (s.scene && s.scene.in_encounter) ? ": there is a fight"
    : ""}. Walk there again to go on from here.`);
});

onRender(function placesChart(s) {
  if (typeof Shell === "object" && Shell && Shell.mode() === "map") {
    mapPaint();
    renderPlaces(s);
  }
});

// --- the controls ----------------------------------------------------------------------------
document.addEventListener("click", e => {
  const t = e.target;
  if (!t.closest) return;
  if (t.closest("#placesbtn")) {
    mapShowPlaces(!MAPV.places);
    const b = document.getElementById("placesbtn");
    if (b) b.focus({ preventScroll: true });
    return;
  }
  // Flat or 3D (04 has already drawn the ground): back to the ground.
  if (t.closest("#groundctl [data-mapview]") && MAPV.places) { mapShowPlaces(false); return; }
  const node = t.closest("#placeswrap [data-node]");
  if (node) {
    pickPlace(node.dataset.node);
    const again = document.querySelector(`#placeswrap [data-node="${CSS.escape(node.dataset.node)}"]`);
    if (again) again.focus({ preventScroll: true });
    return;
  }
  const lv = t.closest("#placeswrap [data-maplevel]");
  if (lv) { mapOpen(lv.dataset.maplevel, lv.dataset.maparg || ""); return; }
  const go = t.closest("#placeswrap [data-walkto]");
  if (go) { walkThere(go.dataset.walkto); return; }
});

document.addEventListener("keydown", e => {
  const node = e.target.closest && e.target.closest("#placeswrap [data-node]");
  if (node && (e.key === "Enter" || e.key === " ")) {
    e.preventDefault();
    node.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  }
});

// A chart laid out in pixels is laid out again when the window changes size.
window.addEventListener("resize", () => { if (MAPV.places) renderPlaces(STATE); });

Shell.tab("map", {
  enter() {
    if (STATE && typeof renderMap === "function") renderMap(STATE);
    mapPaint();
    renderPlaces(STATE);
  },
});
