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
};

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
    name.textContent = places ? ((pf && pf.where) || "The town") : (frame.dataset.ground || "The ground");
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
  if (MAPV.sel && !pf.nodes.some(n => n.id === MAPV.sel && !n.current)) MAPV.sel = null;
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
    MAPV.sel = node.dataset.node === MAPV.sel ? null : node.dataset.node;
    if (!MAPV.walk) MAPV.said = "";
    renderPlaces(STATE);
    const again = document.querySelector(`#placeswrap [data-node="${CSS.escape(node.dataset.node)}"]`);
    if (again) again.focus({ preventScroll: true });
    return;
  }
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
