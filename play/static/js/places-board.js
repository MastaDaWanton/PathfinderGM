// The Places tabletop. An ES module, loaded by table/16-tab-map.js with a dynamic `import()`
// when WebGL is there. It lives outside table/, whose files are classic scripts sharing one
// global scope, each loaded by its own <script> tag (tests/test_template_scripts.py); without it, or when the context is lost, the
// tab draws the chart (16-places-chart.js) from the same data instead (owner decision 3,
// 2026-11-18: the chart stays as the fallback).
//
// The owner's choice of the three place-map mocks (2026-11-18): the town as painted
// miniatures on a scroll of the game's chart paper, rolled in the game's leather, on a
// candlelit wooden table. Ported from `docs/mock/place-map-v2/tabletop.js` (branch
// mock/place-map-v2), town only; the Region, Continent, World and Site boards are phases 3
// and 4 of docs/place-map-v2-build-plan.md.
//
// Painted miniature = a place stood in; grey primer = seen, not stood in; nothing at all =
// not found. What is known, where everything stands and how to walk there are the
// engine's (`scene.places_found`, with its `town` seats from play/town_seats.py); this file
// draws and decides nothing about what is known.
//
// Three.js r170 and Kenney's CC0 Hexagon Kit and Fantasy Town Kit 2.0 are vendored
// (js/vendor/three-r170/, models/kenney/; docs/asset-licences.md): the packaged app is
// offline. The vendored directory is named for its version, so a cached copy can never be
// a stale one under the same name (CLAUDE.md: derived caches outlive every reinstall). Any
// model that fails to load falls back to the primitive below, so the board never comes up
// empty.
import * as THREE from "./vendor/three-r170/three.module.min.js";
import { OrbitControls } from "./vendor/three-r170/addons/controls/OrbitControls.js";
import { GLTFLoader } from "./vendor/three-r170/addons/loaders/GLTFLoader.js";

const U = 1 / 10;              // seat units to the table's
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const bare = s => String(s || "").replace(/^the /i, "");
let stage, api, renderer, scene, camera, controls, tags, world = null, clock = new THREE.Clock();
let sun, hemi, candles = [], pc, walkAnim = null, pick = [], smoke = [], flags = [], clouds = [], tiltOn = true;
let rt, postScene, postCam, postMat, paperTex, paperImg, V = null, lastSig = "", lastTown = "", routeObj = null;
let hoverId = null, moved = false;

// --- The hour's light: dawn warm, day clear, dusk amber, night blue (the mock's) -----------
function light(h) {
  const k = [[0, [40, 60, 120, .5]], [5, [50, 60, 120, .45]], [6.5, [255, 170, 110, .22]], [8.5, [255, 230, 190, .05]],
             [16, [255, 230, 190, .05]], [18.5, [255, 140, 70, .24]], [20, [60, 60, 130, .42]], [24, [40, 60, 120, .5]]];
  let i = 0; while (i < k.length - 2 && h >= k[i + 1][0]) i++;
  const [h0, a] = k[i], [h1, b] = k[i + 1], t = (h - h0) / (h1 - h0 || 1);
  const c = a.map((v, j) => v + (b[j] - v) * t);
  return { r: c[0] | 0, g: c[1] | 0, b: c[2] | 0, night: h < 6 || h >= 19.5 };
}

// --- Materials ------------------------------------------------------------------------------
const MATS = new Map();
const mat = (c, o = {}) => { const k = c + JSON.stringify(o); if (!MATS.has(k)) MATS.set(k, new THREE.MeshStandardMaterial({ color: c, roughness: .82, flatShading: true, ...o })); return MATS.get(k); };
const PRIMER = new THREE.MeshStandardMaterial({ color: 0x8d8f93, roughness: 1, flatShading: true });
const WARD = { north: 0xc98f4b, east: 0x6f9a5e, south: 0xb9645a, west: 0x5f7fa6, square: 0xc9a64f };

export function init(el, a) {
  stage = el; api = a;
  stage.insertAdjacentHTML("beforeend", `<canvas class="gl" aria-hidden="true"></canvas><div class="tags" aria-hidden="true"></div>
    <div class="hud"><button type="button" class="hudbtn" data-board="reset">Reset view</button>
    <button type="button" class="hudbtn" data-board="tilt" aria-pressed="true">Tilt-shift</button></div>`);
  tags = stage.querySelector(".tags");
  const canvas = stage.querySelector("canvas.gl");
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.outputColorSpace = THREE.SRGBColorSpace;
  // A lost context hands the tab back to the chart, drawn from the same state.
  canvas.addEventListener("webglcontextlost", ev => { ev.preventDefault(); renderer.setAnimationLoop(null); api.lost(); });
  scene = new THREE.Scene(); scene.background = new THREE.Color(0x120d09);
  camera = new THREE.PerspectiveCamera(38, 1, .5, 900);
  camera.position.set(0, 70, 62);
  // Free orbit with a reset (owner decision 2, 2026-11-18), held above the table: the
  // camera cannot tip under the paper. The battle board keeps its fixed quarter-turns.
  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true; controls.minDistance = 18; controls.maxDistance = 260;
  controls.minPolarAngle = .25; controls.maxPolarAngle = 1.25; controls.screenSpacePanning = false;
  controls.addEventListener("start", () => { moved = true; });   // the player has the camera now
  hemi = new THREE.HemisphereLight(0xfff2dd, 0x2a1e14, .6); scene.add(hemi);
  sun = new THREE.DirectionalLight(0xffeedd, 2.2); sun.position.set(-60, 90, 40); sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024); Object.assign(sun.shadow.camera, { left: -80, right: 80, top: 80, bottom: -80, near: 10, far: 260 });
  sun.shadow.bias = -.0008; scene.add(sun);
  table(); candlesOn(); post();
  // A press that is not a drag picks the miniature under it.
  let down = null;
  const under = ev => {
    const r = canvas.getBoundingClientRect(), ray = new THREE.Raycaster();
    ray.setFromCamera(new THREE.Vector2((ev.clientX - r.left) / r.width * 2 - 1, -(ev.clientY - r.top) / r.height * 2 + 1), camera);
    const hit = ray.intersectObjects(pick, true)[0]; let o = hit && hit.object;
    while (o && !o.userData.id) o = o.parent;
    return o && o.userData.pickable ? o : null;
  };
  canvas.addEventListener("pointerdown", ev => { down = [ev.clientX, ev.clientY]; });
  canvas.addEventListener("pointerup", ev => {
    if (!down || Math.hypot(ev.clientX - down[0], ev.clientY - down[1]) > 5) return;
    const o = under(ev); if (o) api.pick(o.userData.id);
  });
  // The name under the pointer always shows, even when it was held back to keep the map clear.
  canvas.addEventListener("pointermove", ev => { const o = under(ev); hoverId = o ? o.userData.id : null; canvas.style.cursor = o ? "pointer" : "grab"; });
  canvas.addEventListener("pointerleave", () => { hoverId = null; });
  stage.querySelector('[data-board="reset"]').addEventListener("click", () => frameCamera());
  stage.querySelector('[data-board="tilt"]').addEventListener("click", ev => { tiltOn = !tiltOn; ev.currentTarget.setAttribute("aria-pressed", String(tiltOn)); });
  new ResizeObserver(resize).observe(stage); resize();
  renderer.setAnimationLoop(frame);
  window.__placesBoard = { camera, controls, perf: () => ({ ...renderer.info.memory, calls: lastInfo.calls, triangles: lastInfo.triangles }) };
  renderer.info.autoReset = false;  // the scene and the tilt-shift pass, counted together per frame
}
function resize() {
  const r = stage.getBoundingClientRect(); if (!r.width || !r.height) return;
  renderer.setSize(r.width, r.height, false); camera.aspect = r.width / r.height; camera.updateProjectionMatrix();
  const s = renderer.getDrawingBufferSize(new THREE.Vector2()); rt && rt.setSize(s.x, s.y);
  // A well that changes size is framed again, unless the player has turned or zoomed the view.
  if (!moved && world) frameCamera();
}

// --- The table, the candles -----------------------------------------------------------------
function woodTexture() {
  const c = document.createElement("canvas"); c.width = 512; c.height = 512; const g = c.getContext("2d");
  g.fillStyle = "#5a3a22"; g.fillRect(0, 0, 512, 512);
  let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;   // the same grain every time
  for (let i = 0; i < 90; i++) { const y = rnd() * 512, a = .05 + rnd() * .12;
    g.strokeStyle = rnd() < .5 ? `rgba(30,16,8,${a})` : `rgba(140,96,56,${a})`; g.lineWidth = 1 + rnd() * 3;
    g.beginPath(); g.moveTo(0, y); for (let x = 0; x <= 512; x += 32) g.lineTo(x, y + Math.sin(x * .02 + i) * 4); g.stroke(); }
  for (let p = 0; p < 4; p++) { g.fillStyle = "rgba(20,10,4,.6)"; g.fillRect(0, p * 128, 512, 2); }  // plank seams
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(6, 6); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}
function table() {
  const top = new THREE.Mesh(new THREE.PlaneGeometry(420, 420), new THREE.MeshStandardMaterial({ map: woodTexture(), roughness: .7 }));
  top.rotation.x = -Math.PI / 2; top.receiveShadow = true; scene.add(top);
}
function candlesOn() {
  [[-62, 30], [58, -36]].forEach(([x, z], n) => {
    const g = new THREE.Group();
    const wax = new THREE.Mesh(new THREE.CylinderGeometry(1.4, 1.5, 7 + n * 2, 12), mat(0xefe6cf, { flatShading: false, roughness: .5 }));
    wax.position.y = (7 + n * 2) / 2; wax.castShadow = true; g.add(wax);
    const flame = new THREE.Mesh(new THREE.ConeGeometry(.45, 1.6, 8), new THREE.MeshBasicMaterial({ color: 0xffc860 }));
    flame.position.y = 7 + n * 2 + 1; g.add(flame);
    const dish = new THREE.Mesh(new THREE.CylinderGeometry(3, 3.2, .5, 16), mat(0x9a7a3a, { metalness: .6, roughness: .35, flatShading: false }));
    dish.position.y = .25; dish.receiveShadow = true; g.add(dish);
    const lamp = new THREE.PointLight(0xffb060, 300, 140, 1.8); lamp.position.y = 7 + n * 2 + 2; g.add(lamp);
    g.position.set(x, 0, z); scene.add(g); candles.push({ light: lamp, flame, base: 300 });
  });
}

// --- Tilt-shift: one post pass, blurring by distance from the band in focus -----------------
function post() {
  rt = new THREE.WebGLRenderTarget(4, 4, { samples: 4 });
  postScene = new THREE.Scene(); postCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  postMat = new THREE.ShaderMaterial({
    uniforms: { tex: { value: rt.texture }, res: { value: new THREE.Vector2(1, 1) }, amount: { value: 1 } },
    vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0., 1.); }",
    fragmentShader: `uniform sampler2D tex; uniform vec2 res; uniform float amount; varying vec2 vUv;
      void main(){
        float d = clamp(abs(vUv.y - .48) * 2.6 - .35, 0., 1.) * amount;
        vec4 c = vec4(0.); float w = 0.;
        for (int i = -4; i <= 4; i++) for (int j = -4; j <= 4; j++) {
          vec2 o = vec2(float(i), float(j)) * d * 2.2 / res; float k = 1. - length(vec2(i, j)) / 6.;
          if (k > 0.) { c += texture2D(tex, vUv + o) * k; w += k; } }
        vec4 col = c / w;
        gl_FragColor = vec4(col.rgb * mix(1., .82, d * .6), 1.);
        #include <colorspace_fragment>
      }` });
  postScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), postMat));
}

// --- Miniatures -----------------------------------------------------------------------------
function mesh(geo, m, cast = true) { const o = new THREE.Mesh(geo, m); o.castShadow = cast; o.receiveShadow = true; return o; }
// Which miniature a place gets, by its name. A look only: nothing about the place is decided.
const kindOf = name => { const n = String(name || "").toLowerCase();
  return /cathedral|temple|chapel|shrine/.test(n) ? "steeple" : /laborator|alchem/.test(n) ? "lab" : /barrack|guard/.test(n) ? "barracks"
  : /granar|mill/.test(n) ? "mill" : /stable/.test(n) ? "stables" : /guild|hall/.test(n) ? "hall" : /keep|tower/.test(n) ? "keep" : /smith|forge/.test(n) ? "smithy"
  : /inn|tavern/.test(n) ? "inn" : /market|row/.test(n) ? "market" : /well|cistern/.test(n) ? "well" : /grave/.test(n) ? "grave"
  : /green|woods|garden/.test(n) ? "trees" : /gate/.test(n) ? "gate" : /square/.test(n) ? "plaza" : /crossing/.test(n) ? "post"
  : /warren/.test(n) ? "huts" : /arena/.test(n) ? "arena" : "house"; };
function house(w, d, h, wall, roofC, painted) {
  const g = new THREE.Group();
  const body = mesh(new THREE.BoxGeometry(w, h, d), painted ? mat(wall) : PRIMER); body.position.y = h / 2; g.add(body);
  const roof = mesh(new THREE.ConeGeometry(Math.max(w, d) * .78, h * .7 + .6, 4), painted ? mat(roofC) : PRIMER);
  roof.rotation.y = Math.PI / 4; roof.scale.set(w / Math.max(w, d), 1, d / Math.max(w, d)); roof.position.y = h + (h * .7 + .6) / 2; g.add(roof);
  return g;
}
function tree(painted, s = 1) {
  const g = new THREE.Group();
  const trunk = mesh(new THREE.CylinderGeometry(.15 * s, .2 * s, .9 * s, 6), painted ? mat(0x5a3a22) : PRIMER); trunk.position.y = .45 * s; g.add(trunk);
  const crown = mesh(new THREE.ConeGeometry(.9 * s, 2 * s, 7), painted ? mat(0x4f7a3c) : PRIMER); crown.position.y = 1.8 * s; g.add(crown);
  return g;
}
// --- Kenney's models --------------------------------------------------------------------------
const KIT = {}, KIT_FILES = ["hex/building-house", "hex/building-cabin", "hex/building-smelter", "hex/building-castle",
  "hex/building-wizard-tower", "hex/building-market", "hex/building-walls", "hex/building-archery", "hex/building-mill",
  "hex/building-sheep", "hex/unit-house", "hex/unit-mansion",
  "town/fountain-round", "town/lantern", "town/tree", "town/tree-high-round", "town/tree-crooked"];
// Kenney's hex buildings come moulded onto their own hex tile: on a table that tile is the
// miniature's base, so those get no round base of ours. The Town Kit pieces stand on ours.
const ON_HEX = { house: "hex/building-house", inn: "hex/building-cabin", smithy: "hex/building-smelter", keep: "hex/building-castle",
  steeple: "hex/building-wizard-tower", lab: "hex/building-wizard-tower", market: "hex/building-market", gate: "hex/building-walls",
  barracks: "hex/building-archery", mill: "hex/building-mill", stables: "hex/building-sheep" };
let kitReady = null;
function loadKit() {
  if (kitReady) return kitReady;
  const loader = new GLTFLoader();
  kitReady = Promise.all(KIT_FILES.map(f => loader.loadAsync(`${api.statics}models/kenney/${f}.glb`).then(g => {
    const o = g.scene;
    o.traverse(m => { if (m.isMesh) { m.castShadow = m.receiveShadow = true; m.geometry.userData.keep = true; m.material.userData.keep = true;
      // Kenney's hex palette is mint; warmed a touch toward the game's parchment and leather.
      if (f.startsWith("hex/")) m.material.color.setRGB(.92, .9, .74); } });
    const size = new THREE.Box3().setFromObject(o).getSize(new THREE.Vector3());
    KIT[f] = { o, w: Math.max(size.x, size.z), h: size.y };
  }).catch(err => console.warn("Kenney model missing, using the primitive:", f, err && err.message))));
  return kitReady;
}
// A clone `width` across (or `height` tall); grey primer when the place is only seen.
function kit(f, painted, width, height) {
  const k = KIT[f]; if (!k) return null;
  const o = k.o.clone(true), sc = height ? height / k.h : width / k.w;
  o.scale.setScalar(sc);
  if (!painted) o.traverse(m => { if (m.isMesh) m.material = PRIMER; });
  o.userData.top = k.h * sc;
  return o;
}
function kenneyMini(kind, painted) {
  const g = new THREE.Group(), f = ON_HEX[kind];
  if (f && KIT[f]) {
    const o = kit(f, painted, kind === "keep" || kind === "gate" ? 3.4 : 3); g.add(o);
    if (painted && ["house", "inn", "smithy"].includes(kind)) { const ch = new THREE.Object3D(); ch.position.set(.3, o.userData.top, -.3); g.add(ch); smoke.push({ at: ch, seed: (smoke.length * 2.3) % 10 }); }
    if (painted && (kind === "keep" || kind === "gate")) { const fl = flag(0x8e2317); fl.position.set(kind === "gate" ? -1 : .6, o.userData.top - .2, .3); g.add(fl); flags.push(fl); }
    return g;
  }
  const add = o => { if (o) g.add(o); return o; };
  if (kind === "trees" && KIT["town/tree"]) ["town/tree", "town/tree-high-round", "town/tree-crooked", "town/tree", "town/tree-high-round"]
    .forEach((t, i) => { const o = add(kit(t, painted, 1.2)); if (o) o.position.set(Math.cos(i * 2.4) * 1.1, 0, Math.sin(i * 2.4) * 1.1); });
  else if ((kind === "plaza" || kind === "well") && KIT["town/fountain-round"]) add(kit("town/fountain-round", painted, kind === "plaza" ? 2.4 : 1.6));
  else if (kind === "post" && KIT["town/lantern"]) add(kit("town/lantern", painted, 0, 2.2));
  else if (kind === "huts" && KIT["hex/unit-house"]) [-1, 0, 1].forEach(i => { const o = add(kit("hex/unit-house", painted, 1.1)); if (o) o.position.set(i * 1.05, 0, (i & 1) * .7); });
  else if (kind === "hall" && KIT["hex/unit-mansion"]) add(kit("hex/unit-mansion", painted, 2.2));
  else return null;
  const base = mesh(new THREE.CylinderGeometry(1.35, 1.42, .18, 24), mat(0x3a2c20, { flatShading: false, roughness: .5 }));
  base.position.y = -.1; g.add(base);
  return g;
}
function miniature(kind, { storeys = 1, colour = 0xc9a64f, painted = true }) {
  const fromKit = kenneyMini(kind, painted);
  if (fromKit) return fromKit;
  const g = new THREE.Group(), P = painted, h = 1.2 + (storeys - 1) * .9;
  const add = (o, x = 0, y = 0, z = 0) => { o.position.set(x, y, z); g.add(o); return o; };
  switch (kind) {
    case "steeple": add(house(2.4, 1.6, h + .4, 0xe6d6b4, 0x6a4a3a, P)); add(mesh(new THREE.BoxGeometry(.9, h + 2.4, .9), P ? mat(0xd9cbb0) : PRIMER), 1.2, (h + 2.4) / 2, .4);
      add(mesh(new THREE.ConeGeometry(.75, 2, 4), P ? mat(0x4a5a6a) : PRIMER), 1.2, h + 3.4, .4).rotation.y = Math.PI / 4; break;
    case "keep": add(mesh(new THREE.BoxGeometry(2.4, h + 2.2, 2.4), P ? mat(0xa8a090) : PRIMER), 0, (h + 2.2) / 2, 0);
      for (let i = 0; i < 4; i++) add(mesh(new THREE.BoxGeometry(.5, .5, .5), P ? mat(0xa8a090) : PRIMER), (i % 2 ? 1 : -1) * .95, h + 2.45, (i < 2 ? 1 : -1) * .95);
      if (P) flags.push(add(flag(0x8e2317), .95, h + 2.7, .95)); break;
    case "gate": [-1.4, 1.4].forEach(x => add(mesh(new THREE.CylinderGeometry(.75, .8, 3.4, 8), P ? mat(0xa8a090) : PRIMER), x, 1.7, 0));
      add(mesh(new THREE.BoxGeometry(2.2, .8, 1), P ? mat(0x9a9284) : PRIMER), 0, 2.6, 0); if (P) flags.push(add(flag(0x8e2317), -1.4, 3.4, 0)); break;
    case "well": add(mesh(new THREE.CylinderGeometry(.9, .9, .6, 12, 1, true), P ? mat(0x8a8a8a) : PRIMER), 0, .3, 0);
      add(mesh(new THREE.ConeGeometry(1.2, .8, 4), P ? mat(0x7a4a30) : PRIMER), 0, 1.9, 0).rotation.y = Math.PI / 4;
      [-.8, .8].forEach(x => add(mesh(new THREE.BoxGeometry(.12, 1.6, .12), P ? mat(0x5a3a22) : PRIMER), x, .8, 0)); break;
    case "grave": for (let i = 0; i < 6; i++) add(mesh(new THREE.BoxGeometry(.3, .55, .12), P ? mat(0xb0aca4) : PRIMER), (i % 3 - 1) * .8, .28, (i < 3 ? -.5 : .5)); add(tree(P, .7), 1.6, 0, 0); break;
    case "trees": for (let i = 0; i < 5; i++) add(tree(P, .9 + (i % 2) * .3), Math.cos(i * 2.4) * 1.2, 0, Math.sin(i * 2.4) * 1.2); break;
    case "plaza": add(mesh(new THREE.CylinderGeometry(2.6, 2.6, .12, 20), P ? mat(0xcdbf9f) : PRIMER, false), 0, .06, 0);
      add(mesh(new THREE.CylinderGeometry(.8, .9, .45, 12), P ? mat(0x9aa3ad) : PRIMER), 0, .3, 0); break;
    case "post": add(mesh(new THREE.CylinderGeometry(.1, .1, 2, 6), P ? mat(0x5a3a22) : PRIMER), 0, 1, 0);
      add(mesh(new THREE.BoxGeometry(1.2, .3, .08), P ? mat(0xe8d6a8) : PRIMER), .45, 1.7, 0); add(mesh(new THREE.BoxGeometry(1.2, .3, .08), P ? mat(0xe8d6a8) : PRIMER), -.4, 1.3, 0).rotation.y = 1; break;
    case "huts": for (let i = 0; i < 3; i++) add(house(.9, .8, .7, 0xb8a07a, 0x7a5a3a, P), (i - 1) * 1.1, 0, (i % 2) * .7); break;
    case "arena": add(mesh(new THREE.TorusGeometry(1.5, .35, 6, 18), P ? mat(0xa89878) : PRIMER), 0, .3, 0).rotation.x = Math.PI / 2; break;
    case "market": [-1, 1].forEach(x => { add(mesh(new THREE.BoxGeometry(1.4, .6, 1), P ? mat(0xd8c8a0) : PRIMER), x, .3, 0);
      add(mesh(new THREE.ConeGeometry(1, .5, 4), P ? mat(x < 0 ? 0xc0504a : 0xe0d0a0) : PRIMER), x, .85, 0).rotation.y = Math.PI / 4; }); break;
    default: add(house(2, 1.5, h, 0xe6d6b4, colour, P));
  }
  // Every miniature stands on a dark base, like the ones on a real table.
  const base = mesh(new THREE.CylinderGeometry(1.35, 1.42, .18, 24), mat(0x3a2c20, { flatShading: false, roughness: .5 }));
  base.position.y = -.1; g.add(base);
  return g;
}
function flag(c) {
  const g = new THREE.Group();
  g.add(mesh(new THREE.CylinderGeometry(.04, .04, 1.2, 5), mat(0x3a2a1a))).position.y = .6;
  const cloth = new THREE.Mesh(new THREE.PlaneGeometry(.8, .45, 8, 1), new THREE.MeshStandardMaterial({ color: c, side: THREE.DoubleSide, roughness: .9 }));
  cloth.position.set(.42, 1, 0); cloth.userData.base = cloth.geometry.attributes.position.array.slice(); g.add(cloth); g.userData.cloth = cloth;
  return g;
}
function pcMini() {
  const g = new THREE.Group();
  g.add(mesh(new THREE.CylinderGeometry(.75, .8, .2, 20), mat(0x18120c, { flatShading: false })));
  const body = mesh(new THREE.CylinderGeometry(.32, .55, 1.6, 10), mat(0x27406e)); body.position.y = .95; g.add(body);
  const head = mesh(new THREE.SphereGeometry(.32, 12, 8), mat(0xe8c9a8, { flatShading: false })); head.position.y = 2; g.add(head);
  const cloak = mesh(new THREE.ConeGeometry(.6, 1.3, 10, 1, true), mat(0x1d2f52)); cloak.position.y = 1.05; g.add(cloak);
  const lamp = new THREE.PointLight(0xffc070, 0, 14, 2); lamp.position.set(.5, 1.6, .3); g.add(lamp); g.userData.lamp = lamp;
  return g;
}

// --- The paper: chart paper, ink streets, fog, as one canvas texture ------------------------
function loadPaper() {
  return new Promise(res => { if (paperImg) return res(paperImg);
    const im = new Image(); im.onload = () => res(paperImg = im); im.onerror = () => res(paperImg = null);
    im.src = `${api.statics}img/v2/chart-paper.jpg`; });
}
function drawPaper(c, v, half) {
  const g = c.getContext("2d"), S = c.width / (half * 2), P = ([x, y]) => [(x + half) * S, (y + half) * S];
  if (paperImg) { for (let x = 0; x < c.width; x += 720) for (let y = 0; y < c.height; y += 720) g.drawImage(paperImg, x, y, 720, 720 * paperImg.height / paperImg.width); }
  else { g.fillStyle = "#e6d8b6"; g.fillRect(0, 0, c.width, c.height); }
  const ink = (a, b, w, col = "#2a2019", dash) => { g.strokeStyle = col; g.lineWidth = w; g.setLineDash(dash || []); g.beginPath(); g.moveTo(...P(a)); g.lineTo(...P(b)); g.stroke(); g.setLineDash([]); };
  const T = v.town, drawn = v.drawn;
  g.strokeStyle = "rgba(42,32,25,.6)"; g.lineWidth = 6; g.beginPath(); g.arc(...P([0, 0]), T.wall * S, 0, 7); g.stroke();
  // Streets first (a crossing's and a gate's road, wide), then each place's lane to its street.
  drawn.forEach(n => { const s = T.seats[n.id]; if (!s.foot || !["crossing", "gate"].includes(s.kind)) return;
    ink(s.foot, s.at, s.kind === "gate" ? 30 : 34); ink(s.foot, s.at, s.kind === "gate" ? 22 : 26, "#e9dcbc"); });
  drawn.forEach(n => { const s = T.seats[n.id]; if (!s.foot || ["crossing", "gate"].includes(s.kind)) return;
    ink(s.foot, s.at, 5, n.visited ? "#2a2019" : "#7d6b55", n.visited ? null : [10, 8]); });
  if (T.gate) { const gp = T.seats[T.gate].at, d = Math.hypot(...gp) || 1; ink(gp, [gp[0] + gp[0] / d * 90, gp[1] + gp[1] / d * 90], 5, "#2a2019", [16, 10]); }   // the road out, to the arrow
  // Fog: cloud everywhere but round what is found, so the paper shows nothing it should not.
  const fog = document.createElement("canvas"); fog.width = c.width; fog.height = c.height; const f = fog.getContext("2d");
  f.fillStyle = "rgba(246,244,240,.93)"; f.fillRect(0, 0, fog.width, fog.height);
  for (let i = 0; i < 260; i++) { const x = (Math.sin(i * 12.9) * .5 + .5) * fog.width, y = (Math.sin(i * 78.2) * .5 + .5) * fog.height, r = 40 + (i % 7) * 18;
    const gr = f.createRadialGradient(x, y, 0, x, y, r); gr.addColorStop(0, i % 3 ? "rgba(255,255,255,.7)" : "rgba(190,196,210,.45)"); gr.addColorStop(1, "rgba(255,255,255,0)"); f.fillStyle = gr; f.fillRect(x - r, y - r, r * 2, r * 2); }
  f.globalCompositeOperation = "destination-out";
  drawn.forEach(n => { const [x, y] = P(T.seats[n.id].at), r = 125 * S; const gr = f.createRadialGradient(x, y, r * .3, x, y, r); gr.addColorStop(0, "rgba(0,0,0,1)"); gr.addColorStop(1, "rgba(0,0,0,0)"); f.fillStyle = gr; f.fillRect(x - r, y - r, r * 2, r * 2); });
  g.drawImage(fog, 0, 0);
}

// --- Building the board -----------------------------------------------------------------------
function clear() {
  if (world) { scene.remove(world); world.traverse(o => { if (o.geometry && !o.geometry.userData.keep) o.geometry.dispose();
    // A multi-material mesh (the scroll's roll) carries an array.
    [].concat(o.material || []).forEach(m => { if (!m.userData.keep && m !== PRIMER && ![...MATS.values()].includes(m)) { if (m.map && m.map !== LEATHER) m.map.dispose(); m.dispose(); } }); }); }
  if (paperTex) { paperTex.dispose(); paperTex = null; }
  world = new THREE.Group(); scene.add(world); pick = []; smoke = []; flags = []; clouds = []; routeObj = null;
}
const townXZ = (p, y = 0) => new THREE.Vector3(p[0] * U, y, p[1] * U);
function place(o, id, x, z, size = 1) { o.position.set(x, 0, z); o.userData.id = id; o.userData.size = size; o.scale.setScalar(size); world.add(o); pick.push(o); return o; }

// What `draw` is handed (16-tab-map.js): { pf: scene.places_found, sel, hour, came: [ids]
// walked this turn, fresh: Set of ids found this turn, reduced }. The board is rebuilt only
// when what is found or where the party stands changes; a press only moves the route.
export async function draw(v) {
  const pf = v.pf, T = pf.town || { seats: {}, wall: 385, half: 560, gate: "" };
  const drawn = pf.nodes.filter(n => n.setting === "in" && T.seats[n.id] && T.seats[n.id].drawn && T.seats[n.id].at);
  V = { ...v, town: T, drawn, here: pf.here };
  const sig = pf.where + "|" + pf.here + "|" + pf.nodes.map(n => n.id + (n.visited ? "+" : "")).join(",");
  const freshTown = pf.where !== lastTown;
  if (sig !== lastSig) {
    await Promise.all([loadPaper(), loadKit()]);
    if (V !== null && V.pf !== pf) return;   // a newer state arrived while the models loaded
    lastSig = sig; lastTown = pf.where;
    clear(); town(V);
    pc = pcMini(); world.add(pc); placePc();
  }
  routeLine();
  if (freshTown) frameCamera();
  if (v.came && v.came.length > 1) walk(v.came);
}

function town(v) {
  const T = v.town, half = T.half;
  const c = document.createElement("canvas"); c.width = c.height = 2048; drawPaper(c, v, half);
  paperTex = new THREE.CanvasTexture(c); paperTex.colorSpace = THREE.SRGBColorSpace; paperTex.anisotropy = 8;
  const sheet = new THREE.Mesh(new THREE.PlaneGeometry(half * 2 * U, half * 2 * U), new THREE.MeshStandardMaterial({ map: paperTex, roughness: .95 }));
  sheet.rotation.x = -Math.PI / 2; sheet.position.y = .05; sheet.receiveShadow = true; world.add(sheet);
  world.add(scroll(half * 2 * U, half * 2 * U));
  v.drawn.forEach(n => {
    const s = T.seats[n.id];
    const k = s.kind === "crossing" ? "post" : s.kind === "gate" ? "gate" : s.kind === "square" ? "plaza" : kindOf(n.name);
    const o = miniature(k, { storeys: s.storeys, colour: WARD[s.ward] || WARD.square, painted: n.visited });
    const p = townXZ(s.at); place(o, n.id, p.x, p.z, 2.1);
    o.rotation.y = (n.id.length * 37 % 4) * Math.PI / 2 * .15;  // not every house square to the street
    Object.assign(o.userData, { pickable: !n.current, name: bare(n.name), badge: s.storeys > 1 ? s.storeys : "", seen: !n.visited });
    if (v.fresh && v.fresh.has(n.id) && !v.reduced) { o.scale.setScalar(.01); o.userData.grow = performance.now(); }
  });
  // Out the gate: an arrow past it, the way to the land outside (the Region map, phase 3).
  if (T.gate) {
    const [gx, gy] = T.seats[T.gate].at, d = Math.hypot(gx, gy) || 1, ox = gx / d, oy = gy / d;
    const arrow = new THREE.Group(), cone = mesh(new THREE.ConeGeometry(1.4, 3, 12), mat(0x5a3a22));
    cone.rotation.x = -Math.PI / 2; cone.position.y = 1.2; arrow.add(cone);
    const p = townXZ([gx + ox * 70, gy + oy * 70]); arrow.position.set(p.x, 0, p.z); world.add(arrow);
    arrow.rotation.y = Math.atan2(-ox, -oy);   // the cone points -z; turned to point out (ox, oy)
  }
  // Cotton-wool clouds drifting over the fogged paper at the town's edge.
  const R = half * U * .82;
  for (let n = 0; n < 10; n++) { const a = n / 10 * Math.PI * 2, r = R + (n % 3) * 6; cloud(Math.cos(a) * r, Math.sin(a) * r, 1 + (n % 3) * .4, n); }
}
// The scroll: the same paper on its face, the game's leather (the slips' card-leather) on its
// outside, rolled at the north and south edges round wooden rods (the owner, 2026-11-18).
let LEATHER = null;
function leather(rx, ry) {
  if (!LEATHER) { LEATHER = new THREE.TextureLoader().load(`${api.statics}img/v2/card-leather.jpg`); LEATHER.colorSpace = THREE.SRGBColorSpace; LEATHER.wrapS = LEATHER.wrapT = THREE.RepeatWrapping; }
  const t = LEATHER.clone(); t.needsUpdate = true; t.repeat.set(rx, ry); return t;
}
function spiralTex() {
  const c = document.createElement("canvas"); c.width = c.height = 256; const g = c.getContext("2d");
  g.fillStyle = "#e6d8b6"; g.fillRect(0, 0, 256, 256);
  g.strokeStyle = "#5a3a22"; g.lineWidth = 5; g.beginPath();
  for (let a = 0; a < Math.PI * 12; a += .05) { const r = 8 + a * 3.1; g.lineTo(128 + Math.cos(a) * r, 128 + Math.sin(a) * r); }
  g.stroke(); g.lineWidth = 14; g.beginPath(); g.arc(128, 128, 121, 0, 7); g.stroke();
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
function scroll(width, depth) {
  const g = new THREE.Group(), r = 3.2, L = width + 3;
  // The game's leather is near black: its grain as a bump map and a little sheen make it read
  // as hide in the candlelight; gilt bands near the ends, as on the game's gilt-edged cards.
  const hide = leather(1, 5);
  const side = new THREE.MeshStandardMaterial({ map: hide, bumpMap: hide, bumpScale: 3, roughness: .42, color: new THREE.Color(2.6, 2.2, 1.8) });
  const gilt = mat(0xc9a05a, { flatShading: false, metalness: .85, roughness: .3 });
  const cap = new THREE.MeshStandardMaterial({ map: spiralTex(), roughness: .9 });
  const wood = mat(0x3a2414, { flatShading: false, roughness: .35 });
  [-1, 1].forEach(s => {
    const z = s * (depth / 2 + r * .3);
    const roll = mesh(new THREE.CylinderGeometry(r, r, L, 48), [side, cap, cap]); roll.rotation.z = Math.PI / 2; roll.position.set(0, r, z); g.add(roll);
    const rod = mesh(new THREE.CylinderGeometry(.55, .55, L + 5, 12), wood); rod.rotation.z = Math.PI / 2; rod.position.set(0, r, z); g.add(rod);
    [-1, 1].forEach(e => { const k = mesh(new THREE.SphereGeometry(1.1, 18, 12), wood); k.position.set(e * (L / 2 + 2.8), r, z); g.add(k);
      const band = mesh(new THREE.CylinderGeometry(r + .06, r + .06, 1.2, 48), gilt); band.rotation.z = Math.PI / 2; band.position.set(e * (L / 2 - 3.5), r, z); g.add(band); });
  });
  const back = new THREE.Mesh(new THREE.PlaneGeometry(width, depth), new THREE.MeshStandardMaterial({ map: leather(4, 4), side: THREE.BackSide }));
  back.rotation.x = -Math.PI / 2; back.position.y = .04; g.add(back);
  return g;
}
function cloud(x, z, s, n) {
  const g = new THREE.Group(), m = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 1, transparent: true, opacity: .92, flatShading: true });
  for (let i = 0; i < 4; i++) { const b = new THREE.Mesh(new THREE.IcosahedronGeometry(2.2 * s * (1 - i * .15), 0), m); b.position.set((i - 1.5) * 1.8 * s, Math.sin(i) * .6 * s, (i % 2) * s); b.castShadow = true; g.add(b); }
  g.position.set(x, 9 + (n % 4) * .8, z); g.userData.drift = n * 1.7; world.add(g); clouds.push(g); return g;
}

// --- The party's miniature, the route, the walk -----------------------------------------------
function posOf(id) { const s = V && V.town.seats[id]; return s && s.at ? townXZ(s.at) : null; }
function placePc() {
  const p = posOf(V.here); pc.visible = !!p; if (!p) return;
  pc.position.copy(p).add(new THREE.Vector3(3.6, 0, 3.6)); pc.scale.setScalar(2);
}
function routeLine() {
  if (routeObj) { world.remove(routeObj); routeObj.geometry.dispose(); routeObj.material.dispose(); routeObj = null; }
  const node = V.sel && V.pf.nodes.find(n => n.id === V.sel);
  const legs = (node && node.walk && node.walk.legs) || [];
  const pts = [V.here, ...legs.map(l => l.to)].map(posOf).filter(Boolean);
  if (pts.length < 2) return;
  const lift = pts.map(p => p.clone().setY(p.y + .35));
  const curve = new THREE.CatmullRomCurve3(lift, false, "catmullrom", .1);
  routeObj = new THREE.Mesh(new THREE.TubeGeometry(curve, Math.max(8, lift.length * 12), .28, 6, false),
    new THREE.MeshBasicMaterial({ color: 0x3a5a9e, transparent: true, opacity: .85 }));
  world.add(routeObj);
}
// The walk the engine made this turn, shown after the fact: the party's miniature goes the
// way it went. Under reduced motion, or a hidden window that gets no frames, it is simply
// there (the timer still ends it).
function walk(ids) {
  const pts = ids.map(posOf).filter(Boolean);
  if (pts.length < 2 || V.reduced || !pc) return;
  const curve = new THREE.CatmullRomCurve3(pts, false, "catmullrom", .1), len = curve.getLength();
  const dur = Math.min(3600, 800 + len * 60);
  walkAnim = { curve, start: performance.now(), dur };
  setTimeout(() => { if (walkAnim && walkAnim.curve === curve) { walkAnim = null; placePc(); } }, dur + 150);
}

export function frameCamera() {
  const box = new THREE.Box3(); pick.forEach(o => box.expandByObject(o));
  if (box.isEmpty()) return;
  const c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3()).length();
  controls.target.copy(c);
  // Far enough that the found places fit the well, by its own shape: the mock's `size * .95`
  // assumed a whole window, and in the table's well (about 440 by 360) it showed six of
  // Ledgernook's fourteen places. The narrower of the two angles of view decides.
  const vfov = camera.fov * Math.PI / 180, hfov = 2 * Math.atan(Math.tan(vfov / 2) * camera.aspect);
  const d = Math.min(Math.max(size / 2 / Math.sin(Math.min(vfov, hfov) / 2) * .9, 30), 300);
  const dir = new THREE.Vector3(-.05, .86, .56).normalize();
  camera.position.copy(c).addScaledVector(dir, d);
  controls.maxDistance = Math.max(260, d * 1.6); moved = false;
  controls.minDistance = Math.min(18, d * .5);
  controls.update();
}

// --- Each frame -----------------------------------------------------------------------------
const tmp = new THREE.Vector3();
let lastInfo = { calls: 0, triangles: 0 };
function frame() {
  // Off screen (another tab, the ground board shown, the window hidden): nothing is drawn.
  if (!stage.isConnected || stage.offsetParent === null) return;
  const t = clock.getElapsedTime(), still = !!(V && V.reduced), now = performance.now();
  controls.update();
  if (V && world) {
    // The hour: the window light swings and warms; at night the candles carry the table.
    const h = V.hour, L = light(h), day = Math.max(0, Math.sin((h - 6) / 12 * Math.PI));
    sun.color.setRGB(L.night ? .45 : 1, L.night ? .55 : (L.r / 255 * .3 + .7) * (L.g / 255 * .25 + .75), L.night ? .9 : .82 + L.b / 255 * .18);
    sun.intensity = L.night ? .35 : .6 + day * 2.2; sun.position.set(-90 * Math.cos((h - 6) / 12 * Math.PI), 30 + day * 80, 40);
    hemi.intensity = L.night ? .14 : .3 + day * .45;
    candles.forEach((c, n) => { const fl = still ? 1 : .82 + .18 * Math.sin(t * 11 + n) * Math.sin(t * 7.3 + n * 2);
      c.light.intensity = c.base * fl * (L.night ? 1.6 : .55); if (c.flame) c.flame.scale.y = .8 + fl * .4; });
    if (pc) pc.userData.lamp.intensity = L.night ? 18 : 0;
    if (!still) {
      smoke.forEach(s => { if (!s.puffs) { s.puffs = [0, 1, 2].map(() => { const m = new THREE.Mesh(new THREE.SphereGeometry(.25, 6, 4), new THREE.MeshBasicMaterial({ color: 0xdedede, transparent: true, opacity: .5 })); world.add(m); return m; }); }
        s.at.getWorldPosition(tmp); s.puffs.forEach((m, n) => { const a = ((t * .35 + n / 3 + s.seed) % 1); m.position.set(tmp.x + a * .8, tmp.y + .4 + a * 3, tmp.z); m.scale.setScalar(1 + a * 3); m.material.opacity = .45 * (1 - a); }); });
      flags.forEach((f, n) => { const cl = f.userData.cloth, p = cl.geometry.attributes.position, b = cl.userData.base;
        for (let i = 0; i < p.count; i++) { const x = b[i * 3]; p.array[i * 3 + 2] = Math.sin(t * 6 + x * 6 + n) * .12 * (x + .4); } p.needsUpdate = true; });
      clouds.forEach((c, n) => { c.position.x += Math.sin(t * .2 + c.userData.drift) * .01; c.position.y += Math.sin(t * .6 + n) * .004; });
      if (routeObj) routeObj.material.opacity = .65 + .25 * Math.sin(t * 3);
    }
    world.children.forEach(o => { if (o.userData.grow) { const u = Math.min(1, (now - o.userData.grow) / 900); o.scale.setScalar((o.userData.size || 1) * (.01 + .99 * (1 - Math.pow(1 - u, 3)))); if (u >= 1) delete o.userData.grow; } });
    if (walkAnim && pc) { const u = Math.min(1, (now - walkAnim.start) / walkAnim.dur), e = u < .5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;
      const p = walkAnim.curve.getPointAt(e), q = walkAnim.curve.getPointAt(Math.min(1, e + .01));
      pc.position.set(p.x, p.y + Math.abs(Math.sin(e * walkAnim.curve.getLength() * .9)) * .6, p.z); pc.lookAt(q.x, pc.position.y, q.z);
      if (u >= 1) { walkAnim = null; placePc(); } }
  }
  if (tiltOn) { renderer.setRenderTarget(rt); renderer.render(scene, camera); renderer.setRenderTarget(null);
    const s = renderer.getDrawingBufferSize(new THREE.Vector2()); postMat.uniforms.res.value.copy(s); renderer.render(postScene, postCam); }
  else renderer.render(scene, camera);
  lastInfo = { calls: renderer.info.render.calls, triangles: renderer.info.render.triangles }; renderer.info.reset();
  if (V) labels();
}

// Names on the board: tags over each miniature, stepped up when they would overlap, and held
// back by priority when there is no room (Mapbox and Google Maps drop colliding labels the
// same way). Where you are, the place pressed, the place under the pointer and your route
// always show; the rest show as room opens up when you zoom in. A long name ends in "…" and
// is whole in the slip.
function labels() {
  const r = stage.getBoundingClientRect(), placed = [];
  const node = V.sel && V.pf.nodes.find(n => n.id === V.sel);
  const route = new Set(((node && node.walk && node.walk.legs) || []).map(l => l.to));
  const rank = o => { const id = o.userData.id; return id === V.here ? 0 : id === V.sel ? 1 : id === hoverId ? 2 : route.has(id) ? 3 : o.userData.seen ? 5 : 4; };
  let html = "";
  pick.slice().sort((a, b) => rank(a) - rank(b)).forEach(o => {
    o.getWorldPosition(tmp); tmp.y += 7.5; tmp.project(camera);
    if (tmp.z > 1) return;
    let x = (tmp.x + 1) / 2 * r.width, y = (1 - tmp.y) / 2 * r.height;
    if (x < -40 || x > r.width + 40 || y < -10 || y > r.height + 40) return;
    const name = o.userData.name || "", w = Math.min(name.length * 7.2, 190) + 16 + (o.userData.badge ? 22 : 0), h = 20;
    const hit = yy => placed.some(b => x - w / 2 < b[2] + 4 && x + w / 2 > b[0] - 4 && yy - h < b[3] + 2 && yy > b[1] - 2);
    const must = rank(o) <= 3;
    let n = 0; while (n < 3 && hit(y)) { y -= h + 2; n++; }
    if (hit(y) && !must) return;
    placed.push([x - w / 2, y - h, x + w / 2, y]);
    const id = o.userData.id;
    const cls = (V.sel === id ? " sel" : "") + (o.userData.seen ? " seen" : "") + (V.here === id ? " here" : "");
    html += `<span class="tag${cls}" style="transform:translate(${x.toFixed(0)}px,${y.toFixed(0)}px) translate(-50%,-100%)"><span class="nm">${esc(name)}</span>${
      o.userData.badge ? `<b>${Number(o.userData.badge)}</b>` : ""}</span>`;
  });
  tags.innerHTML = html;
}
