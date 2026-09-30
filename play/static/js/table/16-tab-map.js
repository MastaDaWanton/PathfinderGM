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
// WALK THERE goes by the real movement path, one leg at a time, each leg a real turn the
// player sends. It attaches the first leg as the exits row does (11's `exitChip` into 10's
// `attachPlace`, the one chip slot), and Say sends it through `/api/say`'s place chip
// (play/views.py `_read_place`, `_take_the_exit`). When the party arrives at the end of
// that leg, the next is attached the same way, and so on to the place pressed. Never sent
// by the page: the owner ruled that a way on "should attach like a spell does and then
// apply when you send", and a walk of four legs is four ways on.
//
// Chosen over sending the legs as consecutive turns on one press, which would put
// several model turns (tens of seconds each on the local model) in flight with nobody
// having pressed Say, and would need its own rules for stopping when a fight starts or a
// die is owed half way. This is zMUD's "slow walking" rather than its speedwalk (Zuggsoft,
// "Speedwalking and Slow Walking": a step at a time "with the ability to abort", the next
// step sent only once the last one is confirmed, because "once your commands have been
// sent to the MUD, there is no way to cancel them"); Mudlet's mappers grew a pause and a
// stop for their speedwalks for the same reason (Mudlet issue #5608). Here the
// confirmation is the engine's: `places_found.here` is the leg's far end. Anything else
// (a fight, a roll owed, the chip taken back, the party somewhere the leg did not lead,
// the next way shut) ends the walk and the slip says why; Walk there again picks it up
// from wherever the party stands, on the engine's own route from there.

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

// Attach the first leg of the engine's route to `id` as the exits row would attach it.
// Returns the chip's leg, or null with the reason said.
function mapAttachLeg(s, dest) {
  const scene = (s && s.scene) || {};
  const pf = mapPlacesData(s);
  const node = pf && pf.nodes.find(n => n.id === dest);
  const leg = node && node.walk && node.walk.legs && node.walk.legs[0];
  if (!leg) return { why: (node && node.why) || "No way there by the ways you know." };
  const way = (scene.exits || []).find(x => x.id === leg.to);
  if (!way || way.blocked) {
    return { why: way ? way.blocked : `${upFirst(leg.name)} is not a way on from here now.` };
  }
  attachPlace(exitChip(way, !!scene.in_encounter));
  return { leg, node };
}

function walkThere(dest) {
  const got = mapAttachLeg(STATE, dest);
  if (!got.leg) { MAPV.walk = null; mapWalkSay(got.why); renderPlaces(STATE); return; }
  const legs = got.node.walk.legs.length;
  MAPV.walk = { to: dest, name: got.node.name, leg: got.leg };
  mapWalkSay(legs > 1
    ? `${upFirst(got.leg.name)} is attached to your turn, the first of ${legs} legs. Press Say to walk it; the next leg is attached when you arrive.`
    : `${upFirst(got.leg.name)} is attached to your turn. Press Say to go.`);
  renderPlaces(STATE);
}

// After each state: the leg walked, the next attached; anything else ends the walk.
onRender(function walkOn(s) {
  const w = MAPV.walk;
  if (!w) return;
  const pf = mapPlacesData(s);
  const here = pf && pf.here;
  const stop = line => { MAPV.walk = null; mapWalkSay(line); };
  if (here === w.leg.from) {
    // Not gone yet. A refusal or a busy table keeps the chip (04's `takeTurn`); a chip
    // the player took back, or swapped for a spell, is the walk set aside.
    const c = typeof attachedChip === "function" ? attachedChip() : null;
    if (!c || c.kind !== "place" || c.id !== w.leg.to) {
      stop(`The walk to ${w.name} is set aside. Walk there again to pick it up.`);
    }
    return;
  }
  if (here !== w.leg.to) { stop(`The walk to ${w.name} stopped: you are not where the way led.`); return; }
  if (here === w.to) { MAPV.walk = null; MAPV.sel = null; mapWalkSay(`You are at ${w.name}.`); return; }
  const at = (pf.nodes.find(n => n.current) || {}).name || "here";
  if (s.ended || s.awaiting || (s.scene && s.scene.in_encounter)) {
    stop(`The walk to ${w.name} stopped at ${at}: ${s.awaiting ? "a roll is owed"
      : s.ended ? "the story has ended" : "there is a fight"}. Walk there again when you are ready.`);
    return;
  }
  // 04's `takeTurn` draws the state and only then clears the chip the turn spent, so the
  // next leg is attached after it has finished, not before.
  setTimeout(() => {
    if (MAPV.walk !== w) return;
    const got = mapAttachLeg(STATE, w.to);
    if (!got.leg) { stop(`The walk to ${w.name} stopped at ${at}: ${got.why}`); renderPlaces(STATE); return; }
    w.leg = got.leg;
    const left = got.node.walk.legs.length;
    mapWalkSay(`You are at ${at}. ${upFirst(got.leg.name)} is attached, ${left === 1
      ? "the last leg" : `${left} legs to go`}. Press Say to walk on.`);
    renderPlaces(STATE);
  }, 0);
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
