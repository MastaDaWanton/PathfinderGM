// Style 3, the true 3D tabletop: a parchment map on a wooden table with painted miniatures,
// in Three.js r170 vendored in vendor/ (the packaged app is offline: no CDN). The miniatures
// are Kenney's CC0 Hexagon Kit and Fantasy Town Kit 2.0 (vendor/kenney, License.txt in each),
// downloaded by hand from kenney.nl; any model that fails to load falls back to the
// procedural primitive below, so the board never comes up empty.
//
// Painted miniature = a place you have stood in; grey primer = seen, not yet visited;
// nothing at all = not found. The same model and rules as the other styles (shared/).
import * as THREE from "three";
import { OrbitControls } from "./vendor/addons/controls/OrbitControls.js";
import { GLTFLoader } from "./vendor/addons/loaders/GLTFLoader.js";

const M = MapModel;
const U = 1 / 10;              // town units to metres-ish
let stage, api, renderer, scene, camera, controls, tags, rainCv, V = null, world = null, clock = new THREE.Clock();
let sun, hemi, candles = [], pc, walkAnim = null, pick = [], smoke = [], flags = [], clouds = [], tiltOn = true;
let rt, postScene, postCam, postMat, paperTex, paperImg;
const fps = { n: 0, t: performance.now(), value: 0 };

// --- Materials --------------------------------------------------------------------------
const MATS = new Map();
const mat = (c, o = {}) => { const k = c + JSON.stringify(o); if (!MATS.has(k)) MATS.set(k, new THREE.MeshStandardMaterial({ color: c, roughness: .82, flatShading: true, ...o })); return MATS.get(k); };
const PRIMER = new THREE.MeshStandardMaterial({ color: 0x8d8f93, roughness: 1, flatShading: true });
const WARD = { north: 0xc98f4b, east: 0x6f9a5e, south: 0xb9645a, west: 0x5f7fa6, square: 0xc9a64f };

function init(el, a) {
  stage = el; api = a;
  stage.innerHTML = `<canvas class="surface gl"></canvas><canvas class="surface rain" aria-hidden="true"></canvas><div class="tags"></div>
    <div class="hud"><button type="button" class="toggle" id="tilt" aria-pressed="true">Tilt-shift</button><span id="fps"></span></div>`;
  tags = stage.querySelector(".tags"); rainCv = stage.querySelector(".rain");
  renderer = new THREE.WebGLRenderer({ canvas: stage.querySelector(".gl"), antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.outputColorSpace = THREE.SRGBColorSpace;
  scene = new THREE.Scene(); scene.background = new THREE.Color(0x120d09);
  camera = new THREE.PerspectiveCamera(38, 1, .5, 900);
  camera.position.set(0, 70, 62);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.minDistance = 18; controls.maxDistance = 260;
  controls.minPolarAngle = .25; controls.maxPolarAngle = 1.25; controls.screenSpacePanning = false;
  hemi = new THREE.HemisphereLight(0xfff2dd, 0x2a1e14, .6); scene.add(hemi);
  sun = new THREE.DirectionalLight(0xffeedd, 2.2); sun.position.set(-60, 90, 40); sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024); Object.assign(sun.shadow.camera, { left: -80, right: 80, top: 80, bottom: -80, near: 10, far: 260 });
  sun.shadow.bias = -.0008; scene.add(sun);
  table(); candlesOn();
  post();
  // A click that is not a drag picks the miniature under it.
  let down = null;
  renderer.domElement.addEventListener("pointerdown", ev => { down = [ev.clientX, ev.clientY]; });
  renderer.domElement.addEventListener("pointerup", ev => {
    if (!down || Math.hypot(ev.clientX - down[0], ev.clientY - down[1]) > 5) return;
    const r = renderer.domElement.getBoundingClientRect(), ray = new THREE.Raycaster();
    ray.setFromCamera(new THREE.Vector2((ev.clientX - r.left) / r.width * 2 - 1, -(ev.clientY - r.top) / r.height * 2 + 1), camera);
    const hit = ray.intersectObjects(pick, true)[0];
    if (hit) { let o = hit.object; while (o && !o.userData.id) o = o.parent;
      if (o && o.userData.open) { api.open(...o.userData.open); return; }   // an arrow out of this map
      if (o) { api.pick(o.userData.id); return; } }
    // Nothing pressed but the land: a lit continent or nation opens.
    if (V && V.level === "world" && hover.continent) api.open("continent", hover.continent);
    else if (V && V.level === "continent" && hover.nation) api.open("nation", hover.nation);
  });
  // Zoom between the maps: out past a map's furthest and the one above opens; in hard and the
  // one below opens, the continent or nation under the pointer first, else the one you are in.
  const UP = { town: "nation", nation: "continent", continent: "world" };
  let lastLevelChange = 0;
  renderer.domElement.addEventListener("wheel", ev => {
    if (!V || performance.now() - lastLevelChange < 900) return;
    const d = camera.position.distanceTo(controls.target), go = (...a) => { lastLevelChange = performance.now(); api.open(...a); };
    if (ev.deltaY > 0 && d >= controls.maxDistance * .97 && UP[V.level]) go(UP[V.level]);
    else if (ev.deltaY < 0 && d <= controls.minDistance * 1.05) {
      if (V.level === "world") go("continent", hover.continent || V.continent);
      else if (V.level === "continent") go("nation", hover.nation || V.nation);
      else if (V.level === "nation" && (V.W.cities.find(c => c.id === V.home) || {}).nation === V.nation) go("town");
    }
  }, { passive: true });
  // The name under the pointer always shows, even when it was culled to keep the map clear.
  renderer.domElement.addEventListener("pointermove", ev => {
    const r = renderer.domElement.getBoundingClientRect(), ray = new THREE.Raycaster();
    ray.setFromCamera(new THREE.Vector2((ev.clientX - r.left) / r.width * 2 - 1, -(ev.clientY - r.top) / r.height * 2 + 1), camera);
    const hit = ray.intersectObjects(pick, true)[0]; let o = hit && hit.object; while (o && !o.userData.id) o = o.parent;
    hoverId = o ? o.userData.id : null;
    hover.x = ev.clientX - r.left; hover.y = ev.clientY - r.top;
    let lit = false;
    if (V && V.level === "world" && worldSheet && worldPaper) {
      const h = ray.intersectObject(worldSheet)[0], g = worldPaper.grid;
      const k = h ? Math.floor((1 - h.uv.y) * g.N) * g.N + Math.floor(h.uv.x * g.N) : -1, n = k >= 0 ? g.owner[k] : -1;
      const cont = n >= 0 ? V.W.nations[g.nations[n]].continent : null;
      setHover("continent", cont && g.knownConts.has(cont) ? cont : null); lit = !!hover.continent;
    } else if (V && V.level === "continent" && board) {
      const pt = ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -1.1), new THREE.Vector3());
      const hx = pt && board.hexAt(pt.x, pt.z);
      setHover("nation", hx && board.knownNations.has(hx.nation) ? hx.nation : null); lit = !!hover.nation;
    }
    renderer.domElement.style.cursor = o || lit ? "pointer" : "grab";
  });
  stage.querySelector("#tilt").addEventListener("click", ev => { tiltOn = !tiltOn; ev.currentTarget.setAttribute("aria-pressed", tiltOn); });
  new ResizeObserver(resize).observe(stage); resize();
  renderer.setAnimationLoop(frame);
  window.__three = { camera, controls };  // for screenshots and the perf probe
  renderer.info.autoReset = false;  // count the scene and the tilt-shift pass together, per frame
  window.__perf = () => ({ fps: fps.value, ...renderer.info.memory, calls: lastInfo.calls, triangles: lastInfo.triangles,
                          gl: renderer.getContext().getParameter(renderer.getContext().VERSION) });
}
function resize() {
  const r = stage.getBoundingClientRect(); if (!r.width) return;
  renderer.setSize(r.width, r.height, false); camera.aspect = r.width / r.height; camera.updateProjectionMatrix();
  rainCv.width = r.width; rainCv.height = r.height;
  const s = renderer.getDrawingBufferSize(new THREE.Vector2()); rt && rt.setSize(s.x, s.y);
}

// --- The table, the candles -------------------------------------------------------------
function woodTexture() {
  const c = document.createElement("canvas"); c.width = 512; c.height = 512; const g = c.getContext("2d");
  g.fillStyle = "#5a3a22"; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 90; i++) { const y = Math.random() * 512, a = .05 + Math.random() * .12;
    g.strokeStyle = Math.random() < .5 ? `rgba(30,16,8,${a})` : `rgba(140,96,56,${a})`; g.lineWidth = 1 + Math.random() * 3;
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
    const light = new THREE.PointLight(0xffb060, 300, 140, 1.8); light.position.y = 7 + n * 2 + 2; g.add(light);
    g.position.set(x, 0, z); scene.add(g); candles.push({ light, flame, base: 300 });
  });
}

// --- Tilt-shift: one post pass, blurring by distance from the band in focus ------------------
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

// --- Miniatures ---------------------------------------------------------------------------
function mesh(geo, m, cast = true) { const o = new THREE.Mesh(geo, m); o.castShadow = cast; o.receiveShadow = true; return o; }
const kindOf = n => /cathedral|temple|chapel/.test(n) ? "steeple" : /laborator|alchem/.test(n) ? "lab" : /barrack|guard/.test(n) ? "barracks"
  : /granar|mill/.test(n) ? "mill" : /stable/.test(n) ? "stables" : /guild|hall/.test(n) ? "hall" : /keep|tower/.test(n) ? "keep" : /smith/.test(n) ? "smithy"
  : /inn|tavern/.test(n) ? "inn" : /market|row/.test(n) ? "market" : /well|cistern/.test(n) ? "well" : /grave/.test(n) ? "grave"
  : /green|woods/.test(n) ? "trees" : /gate/.test(n) ? "gate" : /square/.test(n) ? "plaza" : /crossroads|outskirts|crossing/.test(n) ? "post"
  : /road to/.test(n) ? "road" : /desert/.test(n) ? "dunes" : /cave/.test(n) ? "cave" : /warren/.test(n) ? "huts" : /arena/.test(n) ? "arena" : "house";
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
// --- Kenney's models ------------------------------------------------------------------------
const KIT = {}, KIT_FILES = ["hex/building-house", "hex/building-cabin", "hex/building-smelter", "hex/building-castle",
  "hex/building-wizard-tower", "hex/building-market", "hex/building-walls", "hex/building-archery", "hex/building-mill",
  "hex/building-sheep", "hex/building-tower", "hex/building-mine", "hex/building-village", "hex/unit-house", "hex/unit-mansion",
  "hex/sand-desert", "hex/grass", "hex/grass-forest", "hex/water", "hex/stone-hill",
  "town/fountain-round", "town/lantern", "town/tree", "town/tree-high-round", "town/tree-crooked"];
// Kenney's hex buildings come moulded onto their own hex tile: on a table that tile is the
// miniature's base, so those get no round base of ours. The Town Kit pieces stand on ours.
const ON_HEX = { house: "hex/building-house", inn: "hex/building-cabin", smithy: "hex/building-smelter", keep: "hex/building-castle",
  steeple: "hex/building-wizard-tower", lab: "hex/building-wizard-tower", market: "hex/building-market", gate: "hex/building-walls",
  barracks: "hex/building-archery", mill: "hex/building-mill", stables: "hex/building-sheep", cave: "hex/building-mine",
  dunes: "hex/sand-desert", town: "hex/building-village" };
let kitReady = null;
function loadKit() {
  if (kitReady) return kitReady;
  const loader = new GLTFLoader();
  kitReady = Promise.all(KIT_FILES.map(f => loader.loadAsync(`vendor/kenney/${f}.glb`).then(g => {
    const o = g.scene;
    o.traverse(m => { if (m.isMesh) { m.castShadow = m.receiveShadow = true; m.geometry.userData.keep = true; m.material.userData.keep = true;
      // Kenney's hex palette is mint; warmed a touch toward the game's parchment and leather.
      if (f.startsWith("hex/")) m.material.color.setRGB(.92, .9, .74); } });
    const size = new THREE.Box3().setFromObject(o).getSize(new THREE.Vector3());
    KIT[f] = { o, w: Math.max(size.x, size.z), h: size.y };
  }).catch(err => console.warn("Kenney model missing, using the primitive:", f, err.message))));
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
// One tile's geometry with its node transform baked in, for instancing the region board.
const TILE = {};
function tileOf(f) {
  if (TILE[f] || !KIT[f]) return TILE[f];
  let m = null; KIT[f].o.traverse(x => { if (x.isMesh && !m) m = x; });
  KIT[f].o.updateMatrixWorld(true);
  const geo = m.geometry.clone().applyMatrix4(m.matrixWorld); geo.userData.keep = true;
  return (TILE[f] = { geo, mat: m.material });
}
function kenneyMini(kind, painted) {
  const g = new THREE.Group(), f = ON_HEX[kind];
  if (f && KIT[f]) {
    const o = kit(f, painted, kind === "town" ? 10.5 : kind === "keep" || kind === "gate" ? 3.4 : 3); g.add(o);
    if (painted && ["house", "inn", "smithy"].includes(kind)) { const ch = new THREE.Object3D(); ch.position.set(.3, o.userData.top, -.3); g.add(ch); smoke.push({ at: ch, seed: Math.random() * 10 }); }
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
      add(mesh(new THREE.CylinderGeometry(.8, .9, .45, 12), P ? mat(0x9aa3ad) : PRIMER), 0, .3, 0);
      add(mesh(new THREE.CylinderGeometry(.6, .6, .05, 12), new THREE.MeshStandardMaterial({ color: 0x6fa0d0, roughness: .1, metalness: .2 })), 0, .5, 0); break;
    case "post": add(mesh(new THREE.CylinderGeometry(.1, .1, 2, 6), P ? mat(0x5a3a22) : PRIMER), 0, 1, 0);
      add(mesh(new THREE.BoxGeometry(1.2, .3, .08), P ? mat(0xe8d6a8) : PRIMER), .45, 1.7, 0); add(mesh(new THREE.BoxGeometry(1.2, .3, .08), P ? mat(0xe8d6a8) : PRIMER), -.4, 1.3, 0).rotation.y = 1; break;
    case "road": add(mesh(new THREE.CylinderGeometry(.1, .1, 1.8, 6), P ? mat(0x5a3a22) : PRIMER), 0, .9, 0);
      add(mesh(new THREE.ConeGeometry(.45, .9, 3), P ? mat(0xe8d6a8) : PRIMER), 0, 2.1, 0); break;
    case "dunes": for (let i = 0; i < 3; i++) add(mesh(new THREE.SphereGeometry(1.1, 8, 4, 0, Math.PI * 2, 0, Math.PI / 2), P ? mat(0xdcbc80) : PRIMER), i * 1.3 - 1.3, 0, -i * .5).scale.y = .45; break;
    case "cave": add(mesh(new THREE.DodecahedronGeometry(1.6, 0), P ? mat(0x8a7d6a) : PRIMER), 0, .6, 0).scale.y = .7;
      add(mesh(new THREE.CircleGeometry(.6, 10), mat(0x0d0905)), 0, .55, 1.25); break;
    case "huts": for (let i = 0; i < 3; i++) add(house(.9, .8, .7, 0xb8a07a, 0x7a5a3a, P), (i - 1) * 1.1, 0, (i % 2) * .7); break;
    case "arena": add(mesh(new THREE.TorusGeometry(1.5, .35, 6, 18), P ? mat(0xa89878) : PRIMER), 0, .3, 0).rotation.x = Math.PI / 2; break;
    case "market": [-1, 1].forEach(x => { add(mesh(new THREE.BoxGeometry(1.4, .6, 1), P ? mat(0xd8c8a0) : PRIMER), x, .3, 0);
      add(mesh(new THREE.ConeGeometry(1, .5, 4), P ? mat(x < 0 ? 0xc0504a : 0xe0d0a0) : PRIMER), x, .85, 0).rotation.y = Math.PI / 4; }); break;
    case "town": for (let i = 0; i < 5; i++) { const a = i * 1.26, r = i ? 1.3 : 0; add(house(.9, .8, .7 + (i % 2) * .4, 0xe0cfa8, 0xb9645a, P), Math.cos(a) * r, 0, Math.sin(a) * r); }
      add(mesh(new THREE.TorusGeometry(2.2, .14, 4, 24), P ? mat(0x9a9284) : PRIMER), 0, .15, 0).rotation.x = Math.PI / 2; break;
    default: add(house(2, 1.5, h, 0xe6d6b4, colour, P));
      if (P && (kind === "inn" || kind === "smithy" || kind === "house")) { const ch = add(mesh(new THREE.BoxGeometry(.3, .8, .3), mat(0x7a6a5a)), .6, h + .6, -.3); smoke.push({ at: ch, seed: Math.random() * 10 }); }
      if (P && kind === "inn") add(mesh(new THREE.BoxGeometry(.06, .5, .7), mat(0x7a4a2a)), 1.05, h * .7, .5);
      if (P && kind === "smithy") add(mesh(new THREE.BoxGeometry(.5, .35, .5), new THREE.MeshStandardMaterial({ color: 0xff7a30, emissive: 0xff5010, emissiveIntensity: 1.5 })), 1.1, .2, .5);
  }
  // Every miniature stands on a black base, like the ones on a real table.
  const base = mesh(new THREE.CylinderGeometry(kind === "town" ? 2.8 : 1.35, kind === "town" ? 2.9 : 1.42, .18, 24), mat(0x3a2c20, { flatShading: false, roughness: .5 }));
  base.position.y = -.1; g.add(base);
  g.traverse(o => { if (o.isMesh && o !== base) o.position.y += .03; });
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

// --- The parchment for the town: paper, ink streets, fog, as one canvas texture --------------
function loadPaper() {
  return new Promise(res => { if (paperImg) return res(paperImg); const im = new Image(); im.onload = () => res(paperImg = im); im.src = "assets/chart-paper.jpg"; });
}
function drawPaper(c, v, half) {
  const g = c.getContext("2d"), S = c.width / (half * 2), P = ([x, y]) => [(x + half) * S, (y + half) * S];
  for (let x = 0; x < c.width; x += 720) for (let y = 0; y < c.height; y += 720) g.drawImage(paperImg, x, y, 720, 720 * paperImg.height / paperImg.width);
  const ink = (a, b, w, col = "#2a2019", dash) => { g.strokeStyle = col; g.lineWidth = w; g.setLineDash(dash || []); g.beginPath(); g.moveTo(...P(a)); g.lineTo(...P(b)); g.stroke(); g.setLineDash([]); };
  const { L, F } = v, found = [...F.found].filter(i => L.pos[i] && v.T.settings[i] === "in");
  const gp = L.gate ? L.pos[L.gate] : [0, -385], wr = L.wall || Math.hypot(...gp);
  g.strokeStyle = "rgba(42,32,25,.6)"; g.lineWidth = 6; g.beginPath(); g.arc(...P([0, 0]), wr * S, 0, 7); g.stroke();
  Object.values(L.crossings).forEach(c2 => { if (F.found.has(c2)) { ink([0, 0], L.pos[c2], 34); ink([0, 0], L.pos[c2], 26, "#e9dcbc"); } });
  if (L.gate && F.found.has(L.gate)) { ink(L.pos[L.street[L.gate]], L.pos[L.gate], 30); ink(L.pos[L.street[L.gate]], L.pos[L.gate], 22, "#e9dcbc"); }
  found.forEach(i => { const s = L.street[i]; if (!s || ["crossing", "gate"].includes(L.kind[i])) return;
    const [x, y] = L.pos[i], [sx, sy] = L.pos[s]; const foot = sx === 0 && s !== L.square ? [0, y] : sy === 0 && s !== L.square ? [x, 0] : [sx, sy];
    ink(foot, [x, y], 5, F.visited.has(i) ? "#2a2019" : "#7d6b55", F.visited.has(i) ? null : [10, 8]); });
  if (L.gate && F.found.has(L.gate)) { const d = Math.hypot(...gp) || 1; ink(gp, [gp[0] + gp[0] / d * 90, gp[1] + gp[1] / d * 90], 5, "#2a2019", [16, 10]); }   // the road out, to the arrow
  // Fog: cloud everywhere but round what is found, so the paper reveals nothing it should not.
  const fog = document.createElement("canvas"); fog.width = c.width; fog.height = c.height; const f = fog.getContext("2d");
  f.fillStyle = "rgba(246,244,240,.93)"; f.fillRect(0, 0, fog.width, fog.height);
  for (let i = 0; i < 260; i++) { const x = (Math.sin(i * 12.9) * .5 + .5) * fog.width, y = (Math.sin(i * 78.2) * .5 + .5) * fog.height, r = 40 + (i % 7) * 18;
    const gr = f.createRadialGradient(x, y, 0, x, y, r); gr.addColorStop(0, i % 3 ? "rgba(255,255,255,.7)" : "rgba(190,196,210,.45)"); gr.addColorStop(1, "rgba(255,255,255,0)"); f.fillStyle = gr; f.fillRect(x - r, y - r, r * 2, r * 2); }
  f.globalCompositeOperation = "destination-out";
  found.forEach(i => { const [x, y] = P(L.pos[i]), r = 125 * S; const gr = f.createRadialGradient(x, y, r * .3, x, y, r); gr.addColorStop(0, "rgba(0,0,0,1)"); gr.addColorStop(1, "rgba(0,0,0,0)"); f.fillStyle = gr; f.fillRect(x - r, y - r, r * 2, r * 2); });
  g.drawImage(fog, 0, 0);
}

// --- Building each map's board ---------------------------------------------------------------
function clear() {
  if (world) { scene.remove(world); world.traverse(o => { if (o.geometry && !o.geometry.userData.keep) o.geometry.dispose(); [].concat(o.material || []).forEach(m => { if (!m.userData.keep && !m.map && m !== PRIMER && ![...MATS.values()].includes(m)) m.dispose(); }); }); }  // the scroll's roll carries an array
  if (paperTex) { paperTex.dispose(); paperTex = null; }
  world = new THREE.Group(); scene.add(world); areas = []; pick = []; board = null; worldSheet = null; hover.continent = hover.nation = null; smoke = []; flags = []; clouds = []; routeObj = null;
  candles = candles.filter(c => !c.site);  // a room's torch goes with its room
}
let lastKey = "", hoverId = null, areas = [], frameD = 100, worldPaper = null, worldSheet = null, board = null;
const hover = { continent: null, nation: null, x: 0, y: 0 };
// Nations in muted inks, by their sorted names, so a nation keeps its colour on both maps.
const NATION_INK = ["#8e2317", "#27406e", "#2e6b4a", "#7a5a1e", "#5b3a7a", "#7a3b55", "#2f6d75", "#6a4a2a"];
const inkOf = (all, name) => NATION_INK[[...all].sort().indexOf(name) % NATION_INK.length];
async function draw(v) {
  V = v;
  const key = v.level + (v.site ? v.site.key : "") + (v.level === "continent" ? v.continent : v.level === "nation" ? v.nation : "");
  const fresh = key !== lastKey; lastKey = key;
  await Promise.all([loadPaper(), loadKit()]);
  clear();
  if (v.level === "town") town(v); else if (v.level === "continent") continentMap(v); else if (v.level === "nation") nationMap(v);
  else if (v.level === "world") worldMap(v); else site(v);
  pc = pcMini(); world.add(pc); placePc();
  routeLine();
  if (fresh) frameCamera();
}
const townXZ = (p, y = 0) => new THREE.Vector3(p[0] * U, y, p[1] * U);
function place(o, id, x, z, size = 1) { o.position.set(x, 0, z); o.userData.id = id; o.userData.size = size; o.scale.setScalar(size); world.add(o); pick.push(o); return o; }

function town(v) {
  // The sheet is as big as the town: a street that has grown longer than the old sheet (the
  // worst case's sixteen-place street ran to 920 units, past a 560 half-sheet) gets more paper.
  // Inside the walls only (the owner, 2026-11-18): the outskirts, crossroads, roads and wild
  // ground are on the region map; the gate is this map's edge and its arrow leads out.
  const { L, F, T } = v, inside = i => T.settings[i] === "in";
  const half = Math.max(560, ...Object.entries(L.pos).filter(([i]) => inside(i)).map(([, p]) => Math.max(Math.abs(p[0]), Math.abs(p[1])) + 130));
  const c = document.createElement("canvas"); c.width = c.height = 2048; drawPaper(c, v, half);
  paperTex = new THREE.CanvasTexture(c); paperTex.colorSpace = THREE.SRGBColorSpace; paperTex.anisotropy = 8;
  const sheet = new THREE.Mesh(new THREE.PlaneGeometry(half * 2 * U, half * 2 * U), new THREE.MeshStandardMaterial({ map: paperTex, roughness: .95 }));
  sheet.rotation.x = -Math.PI / 2; sheet.position.y = .05; sheet.receiveShadow = true; world.add(sheet);
  world.add(scroll(half * 2 * U, half * 2 * U));
  const ward = i => { if (i === L.square) return "square"; const cc = L.kind[i] === "crossing" ? i : L.street[i];
    const m = /(north|east|south|west)-crossing/.exec(cc || ""); return m ? m[1] : "square"; };
  [...F.found].filter(i => L.pos[i] && inside(i)).forEach(i => {
    const storeys = (L.floors[i] || []).filter(f => M.floorOf(f) > 0).length + 1;
    const k = L.kind[i] === "crossing" ? "post" : kindOf(T.names[i]);
    const o = miniature(k, { storeys, colour: WARD[ward(i)], painted: F.visited.has(i) });
    const p = townXZ(L.pos[i]); place(o, i, p.x, p.z, 2.1);
    o.rotation.y = (i.length * 37 % 4) * Math.PI / 2 * .15;  // not every house square to the street
    o.userData.name = M.bare(T.names[i]); o.userData.badge = storeys > 1 ? storeys : ""; o.userData.down = !!MapUI.siteFor(i);
    o.userData.seen = !F.visited.has(i); o.userData.road = L.kind[i] === "roadhead" ? ((T.ways[i] || []).find(w => w.journey) || {}).time_words : "";
    if (v.fresh.has(i) && !v.reduced) { o.scale.setScalar(.01); o.userData.grow = performance.now(); }
  });
  // Out the gate: an arrow past it to the region, pressable.
  if (L.gate && F.found.has(L.gate)) {
    const [gx, gy] = L.pos[L.gate], d = Math.hypot(gx, gy) || 1, ox = gx / d, oy = gy / d;
    const arrow = new THREE.Group(), cone = mesh(new THREE.ConeGeometry(1.4, 3, 12), mat(0x5a3a22));
    cone.rotation.x = Math.PI / 2; cone.rotation.z = -Math.atan2(ox, -oy); cone.position.y = 1.2; arrow.add(cone);
    const p = townXZ([gx + ox * 70, gy + oy * 70]); place(arrow, "out-gate", p.x, p.z, 1);
    arrow.rotation.y = Math.atan2(-ox, -oy) - Math.PI;
    arrow.userData.name = "Out the gate"; arrow.userData.open = ["nation"];
  }
  // Cotton-wool clouds drifting over the fogged paper at the town's edge.
  for (let n = 0; n < 10; n++) { const a = n / 10 * Math.PI * 2, r = 46 + (n % 3) * 6; cloud(Math.cos(a) * r, Math.sin(a) * r, 1 + (n % 3) * .4); }
}
// The town map is a scroll: the same paper on its face, the game's leather (card-leather.jpg,
// the slips' own) on its outside, rolled at the north and south edges round wooden rods.
let LEATHER = null;
function leather(rx, ry) {
  if (!LEATHER) { LEATHER = new THREE.TextureLoader().load("assets/card-leather.jpg"); LEATHER.colorSpace = THREE.SRGBColorSpace; LEATHER.wrapS = LEATHER.wrapT = THREE.RepeatWrapping; }
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
  // The game's leather is near black: its grain as a bump map and a little sheen make it read as
  // hide in the candlelight; gilt bands near the ends, as on the game's gilt-edged cards.
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
function cloud(x, z, s = 1) {
  const g = new THREE.Group(), m = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 1, transparent: true, opacity: .92, flatShading: true });
  for (let i = 0; i < 4; i++) { const b = new THREE.Mesh(new THREE.IcosahedronGeometry(2.2 * s * (1 - i * .15), 0), m); b.position.set((i - 1.5) * 1.8 * s, Math.sin(i) * .6 * s, (i % 2) * s); b.castShadow = true; g.add(b); }
  g.position.set(x, 9 + Math.random() * 3, z); g.userData.drift = Math.random() * 6; world.add(g); clouds.push(g); return g;
}

// The region: a hex board. Every hex near a known town or road is land, field, wood, sand or
// sea by what stands there; every other hex wears a cloud.
const HX = 6.2;
const hexC = (q, r, h) => [h * Math.sqrt(3) * (q + r / 2), h * 1.5 * r];
// The same land the world map paints (blots round every city), so the boards agree with it.
function landAt(W, WL, x, y) {
  return W.cities.some((city, n) => { const [cx, cy] = WL.pos[city.id];
    for (let k = 0; k < 5; k++) { const a = n * 1.7 + k * 1.26, r = 70 + (n * 37 + k * 13) % 40; if (Math.hypot(x - cx - Math.cos(a) * 30, y - cy - Math.sin(a) * 30) < r) return true; }
    return false; });
}
const nearestCity = (list, WL, x, y) => { let best = 1e18, c = null; list.forEach(ci => { const [cx, cy] = WL.pos[ci.id], d = (cx - x) ** 2 + (cy - y) ** 2; if (d < best) { best = d; c = ci; } }); return c; };
// A hex board from a list of hexes {q, r, x, z, tile, plate, plateOpacity, cloud, nation, known}:
// Kenney tiles instanced per kind, translucent nation plates, cloud puffs, border strips where
// nations meet, each known nation's name painted flat along its longest known row.
function hexBoard(hexes, h, wash, names) {
  const byTile = new Map(), puffs = [], q0 = new THREE.Quaternion();
  hexes.forEach(x => {
    if (x.tile) (byTile.get(x.tile) || byTile.set(x.tile, []).get(x.tile)).push(new THREE.Matrix4().compose(new THREE.Vector3(x.x, x.tile === "hex/water" ? -.15 : 0, x.z), q0,
      new THREE.Vector3(h * Math.sqrt(3) * .985, 5, h * Math.sqrt(3) * .985)));
    if (x.cloud) for (let i = 0; i < 4; i++) puffs.push(new THREE.Matrix4().compose(new THREE.Vector3(x.x + (i - 1.5) * h * .27, 2.6 + Math.sin(i + x.q) * .5, x.z + (i % 2) * h * .15), q0, new THREE.Vector3().setScalar(h * .34 * (1 - i * .15))));
  });
  byTile.forEach((list, f) => { const t = tileOf(f); if (!t) return; const im = new THREE.InstancedMesh(t.geo, t.mat, list.length); list.forEach((m, n) => im.setMatrixAt(n, m)); im.receiveShadow = true; world.add(im); });
  if (puffs.length) { const im = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1, 0), new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 1, flatShading: true }), puffs.length);
    puffs.forEach((m, n) => im.setMatrixAt(n, m)); im.castShadow = true; world.add(im); }
  // Nation plates: one instanced mesh per opacity; their indices kept so a hover can light a nation.
  const plateSets = {};
  hexes.filter(x => x.plate).forEach(x => (plateSets[x.plateOpacity] = plateSets[x.plateOpacity] || []).push(x));
  const lit = {};
  Object.entries(plateSets).forEach(([op, list]) => {
    const im = new THREE.InstancedMesh(new THREE.CylinderGeometry(h * .97, h * .97, .05, 6), new THREE.MeshBasicMaterial({ transparent: true, opacity: +op, depthWrite: false }), list.length);
    list.forEach((x, n) => { im.setMatrixAt(n, new THREE.Matrix4().makeTranslation(x.x, 1.06, x.z)); im.setColorAt(n, new THREE.Color(wash[x.nation])); (lit[x.nation] = lit[x.nation] || []).push([im, n]); });
    im.renderOrder = 1; world.add(im); });
  const key = (q, r) => q + "," + r, at = new Map(hexes.map(x => [key(x.q, x.r), x])), strips = [];
  hexes.forEach(x => [[1, 0], [1, -1], [0, -1]].forEach(([dq, dr]) => {
    const o = at.get(key(x.q + dq, x.r + dr));
    if (!o || !o.nation || !x.nation || o.nation === x.nation || !(x.known || o.known) || o.tile === "hex/water" || x.tile === "hex/water") return;
    strips.push(new THREE.Matrix4().compose(new THREE.Vector3((x.x + o.x) / 2, 1.25, (x.z + o.z) / 2),
      new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), -Math.atan2(o.z - x.z, o.x - x.x) + Math.PI / 2), new THREE.Vector3(h * .98, 1, 1)));
  }));
  if (strips.length) { const im = new THREE.InstancedMesh(new THREE.BoxGeometry(1, .5, .45), mat(0x5a1e14, { flatShading: false, roughness: .6 }), strips.length);
    strips.forEach((m, n) => im.setMatrixAt(n, m)); im.castShadow = true; world.add(im); }
  // Names: along the longest row of known hexes that are all that nation's, never over a border.
  Object.keys(names).forEach(n => {
    const rows = {}; hexes.forEach(x => { if (x.nation === n && x.known && x.tile !== "hex/water") (rows[x.r] = rows[x.r] || []).push(x); });
    let best = null;
    Object.values(rows).forEach(list => { list.sort((a, b) => a.q - b.q); let run = [list[0]];
      const keep = () => { if (!best || run.length > best.length) best = run.slice(); };
      for (let i = 1; i < list.length; i++) { if (list[i].q === list[i - 1].q + 1) run.push(list[i]); else { keep(); run = [list[i]]; } } keep(); });
    if (best) world.add(flatName(names[n].toUpperCase(), M.darken(wash[n], .38), best.reduce((a, x) => a + x.x, 0) / best.length, best[0].z, best.length * h * Math.sqrt(3) * .92));
  });
  return { at, lit, hexAt: (sx, sz) => { let bestD = 1e18, bx = null; hexes.forEach(x => { const d = (x.x - sx) ** 2 + (x.z - sz) ** 2; if (d < bestD) { bestD = d; bx = x; } }); return bestD < h * h * 1.2 ? bx : null; } };
}
function setHover(kind, id) {
  if (hover[kind] === id) return;
  hover[kind] = id;
  if (kind === "continent") return paintWorldHighlight();
  if (!board || !board.lit) return;
  Object.entries(board.lit).forEach(([n, list]) => list.forEach(([im, i]) => {
    const c = new THREE.Color(board.wash[n]); if (n === id) c.lerp(new THREE.Color(1, .95, .75), .45); im.setColorAt(i, c); im.instanceColor.needsUpdate = true; }));
}
const dayPegs = (a, b, miles, y) => { const n = miles ? Math.ceil(miles / 24) - 1 : 0;   // a peg a day at 24 miles (speed 30)
  for (let d = 1; d <= n; d++) { const t = d / (n + 1), peg = mesh(new THREE.CylinderGeometry(.32, .32, .9, 8), mat(0xf3ead6)); peg.position.set(a[0] + (b[0] - a[0]) * t, y, a[1] + (b[1] - a[1]) * t); world.add(peg); } };
function roadStrip(a, b, kind, y = 1.08, w = 1.1) {
  const L = Math.hypot(b[0] - a[0], b[1] - a[1]); if (!L) return;
  const strip = mesh(new THREE.BoxGeometry(L, .12, kind === "river" ? w * 1.4 : w), mat(kind === "river" ? 0x4f86b0 : kind === "track" ? 0x9a8058 : 0xb79b6d), false);
  strip.position.set((a[0] + b[0]) / 2, y, (a[1] + b[1]) / 2); strip.rotation.y = -Math.atan2(b[1] - a[1], b[0] - a[0]); world.add(strip);
}

// The continent: its nations coloured, the cities you know as villages, the roads you know with a
// peg a day. From the world's own layout, so a town's bearing here is its bearing on the world.
function continentMap(v) {
  const { W, WL, K } = v, wash = M.nationColours(W), CS = .3, h = 7;
  const cities = W.cities.filter(c => c.continent === v.continent), ctr = WL.centre[v.continent] || [0, 0];
  const S = ([x, y]) => [(x - ctr[0]) * CS, (y - ctr[1]) * CS], inC = new Set(cities.map(c => c.id));
  const knownIds = Object.keys(K.how).filter(id => inC.has(id)), knownPts = knownIds.map(id => WL.pos[id]);
  const roads = K.roads.filter(r => r.by !== "sea" && inC.has(r.a) && inC.has(r.b));
  const knownNations = new Set(knownIds.map(id => W.cities.find(c => c.id === id).nation));
  const hexes = [];
  for (let q = -22; q <= 22; q++) for (let r = -18; r <= 18; r++) {
    const [sx, sz] = hexC(q, r, h), wx = sx / CS + ctr[0], wy = sz / CS + ctr[1];
    if (Math.hypot(wx - ctr[0], wy - ctr[1]) > 420) continue;
    const land = landAt(W, WL, wx, wy);
    const nearLand = land || cities.some(c => Math.hypot(WL.pos[c.id][0] - wx, WL.pos[c.id][1] - wy) < 150);
    if (!nearLand) continue;
    const city = nearestCity(cities, WL, wx, wy), nation = land && city ? city.nation : null;
    const known = land && (knownPts.some(([x, y]) => Math.hypot(x - wx, y - wy) < 75) || roads.some(rd => segD([wx, wy], WL.pos[rd.a], WL.pos[rd.b]) < 24));
    const tile = !land ? "hex/water" : known ? ((q * 7 + r * 3) % 9 === 0 ? "hex/grass-forest" : "hex/grass")
      : ((q * 7 + r * 3) % 5 === 0 ? "hex/grass-forest" : ((q * 5 + r * 11) % 13 === 0 ? "hex/stone-hill" : "hex/grass"));
    hexes.push({ q, r, x: sx, z: sz, tile, nation, known, plate: land && known, plateOpacity: .55, cloud: land && !known });
  }
  const names = Object.fromEntries([...knownNations].map(n => [n, W.nations[n].name]));
  const b = hexBoard(hexes, h, wash, names);
  board = { ...b, wash, knownNations, pos: {} };
  roads.forEach(rd => { const a = S(WL.pos[rd.a]), c = S(WL.pos[rd.b]); roadStrip(a, c, rd.by === "river" ? "river" : "road"); dayPegs(a, c, rd.miles, 1.4); });
  knownIds.forEach(id => {
    const [x, z] = S(WL.pos[id]), how = K.how[id], o = miniature("town", { painted: how.by === "been" });
    place(o, id, x, z, .8); o.userData.name = W.cities.find(c => c.id === id).name; o.userData.seen = how.by !== "been";
    board.pos[id] = new THREE.Vector3(x, 1.05, z);
  });
}

// The region: the nation you stand in, at Pathfinder's 12-mile overland hex (Ultimate Campaign).
// Its towns you know; round Featherperch, its wild ground at the walking hours the exits row
// gives, set away from the roads; roads leaving the nation end in an arrow naming where they go.
function nationMap(v) {
  const { W, WL, K, T, F } = v, wash = M.nationColours(W), cont = W.nations[v.nation].continent;
  const contCities = W.cities.filter(c => c.continent === cont), mineC = W.cities.filter(c => c.nation === v.nation);
  // Miles to a world unit, from the roads the world measured (median), so the hex is 12 miles.
  const ratios = W.routes.filter(r => r.miles && r.by !== "sea").map(r => r.miles / Math.hypot(WL.pos[r.a][0] - WL.pos[r.b][0], WL.pos[r.a][1] - WL.pos[r.b][1])).sort((a, b) => a - b);
  const milesPerUnit = ratios[ratios.length >> 1] || 1, rW = 6 / milesPerUnit, h = HX, NS = h / rW;
  const ctr = [mineC.reduce((a, c) => a + WL.pos[c.id][0], 0) / mineC.length, mineC.reduce((a, c) => a + WL.pos[c.id][1], 0) / mineC.length];
  const S = ([x, y]) => [(x - ctr[0]) * NS, (y - ctr[1]) * NS];
  const ofN = (wx, wy) => { if (!landAt(W, WL, wx, wy)) return null; const c = nearestCity(contCities, WL, wx, wy); return c ? c.nation : null; };
  const homeHere = (W.cities.find(c => c.id === v.home) || {}).nation === v.nation;
  const knownTowns = Object.keys(K.how).filter(id => mineC.some(c => c.id === id));
  // The hexes: the nation's land, and a ring of its neighbours' land and sea for context.
  const hexes = [], key = (q, r) => q + "," + r, grid = new Map();
  const span = Math.ceil((Math.max(...mineC.map(c => Math.hypot(WL.pos[c.id][0] - ctr[0], WL.pos[c.id][1] - ctr[1]))) + 160) * NS / (h * 1.5));
  for (let q = -span * 2; q <= span * 2; q++) for (let r = -span; r <= span; r++) {
    const [sx, sz] = hexC(q, r, h), wx = sx / NS + ctr[0], wy = sz / NS + ctr[1];
    grid.set(key(q, r), { q, r, x: sx, z: sz, wx, wy, nation: ofN(wx, wy) });
  }
  const DIRS = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]];
  const mine = [...grid.values()].filter(x => x.nation === v.nation);
  const ring = new Set(); mine.forEach(x => DIRS.forEach(([dq, dr]) => { const o = grid.get(key(x.q + dq, x.r + dr)); if (o && o.nation !== v.nation) ring.add(o); }));
  const hexOf = (wx, wy) => { let best = 1e18, b = null; mine.forEach(x => { const d = (x.wx - wx) ** 2 + (x.wy - wy) ** 2; if (d < best) { best = d; b = x; } }); return b; };
  // Where things stand: towns at their own hex; Featherperch's wild ground placed by rule.
  const pos = {}, known = new Set(), around = (x, n = 1) => { known.add(key(x.q, x.r)); if (n) DIRS.forEach(([dq, dr]) => known.add(key(x.q + dq, x.r + dr))); };
  knownTowns.forEach(id => { const hx = hexOf(...WL.pos[id]); pos[id] = hx; around(hx); });
  const roadsOut = [];
  K.roads.filter(rd => rd.by !== "sea" && (mineC.some(c => c.id === rd.a) || mineC.some(c => c.id === rd.b))).forEach(rd => {
    const from = mineC.some(c => c.id === rd.a) ? rd.a : rd.b, to = from === rd.a ? rd.b : rd.a;
    roadsOut.push({ from, to, by: rd.by, miles: rd.miles, inside: mineC.some(c => c.id === to), bearing: Math.atan2(WL.pos[to][1] - WL.pos[from][1], WL.pos[to][0] - WL.pos[from][0]) });
  });
  // Terrain from the world, as the engine reads it (geography.land_around, in the export):
  // a hex along a road takes the ground that road crosses there (Featherperch's roads all
  // cross forest first, then underground or mountain); the hexes round a town take its near
  // ground; a town's reaches (the desert, 7 miles out, from the land it sits in) get a patch
  // at their miles. Places then go to the hexes of their own ground (the owner: "let the
  // woods and desert go to the desert and forest hexes"); before, pieces were placed first
  // and ground painted under them.
  const TILE_OF = { forest: "hex/grass-forest", jungle: "hex/grass-forest", desert: "hex/sand-desert", mountain: "hex/stone-hill", hills: "hex/stone-hill",
                    underground: "hex/stone-hill", tundra: "hex/grass", farmland: "hex/grass", grassland: "hex/grass", swamp: "hex/grass-forest", coast: "hex/grass" };
  const ground = new Map(), hexMiles = 12, all = [...mine, ...ring].filter(x => x.nation);
  const townOf = x => nearestCity(contCities, WL, x.wx, x.wy);
  const routesOf = c => W.routes.filter(r => r.by !== "sea" && (r.a === c.id || r.b === c.id) && (r.crosses || []).length);
  all.forEach(x => {
    const c = townOf(x); if (!c) return;
    const [cx, cy] = WL.pos[c.id], dHex = Math.hypot(x.wx - cx, x.wy - cy) / (rW * Math.sqrt(3));
    let g = null;
    routesOf(c).forEach(r => { if (g) return; const o = r.a === c.id ? r.b : r.a, [ox, oy] = WL.pos[o];
      if (segD([x.wx, x.wy], [cx, cy], [ox, oy]) > rW * .9) return;
      const L = Math.hypot(ox - cx, oy - cy) || 1, t = ((x.wx - cx) * (ox - cx) + (x.wy - cy) * (oy - cy)) / (L * L);
      if (t < 0 || t > 1) return;
      // Its own half of the road: past the middle the far town's ground begins.
      const cr = r.a === c.id ? r.crosses : [...r.crosses].reverse(); g = cr[Math.min(cr.length - 1, Math.floor(t * cr.length))]; });   // crosses run from this town outward
    if (!g && dHex > .5 && dHex < 1.6) { const near = (c.near || []).filter(n => n !== "desert" && n !== "coast"); g = near.length ? near[(x.q * 7 + x.r * 3 & 1023) % near.length] : null; }
    if (!g && dHex >= 1.6) { const far = c.beyond || []; g = (x.q * 7 + x.r * 3 & 1023) % 4 === 0 && far.length ? far[(x.q + x.r & 1023) % far.length] : null; }
    if (g) ground.set(key(x.q, x.r), g);
  });
  // Reaches the roads do not reach (Featherperch's desert, 'region'): a patch at their miles, in
  // the direction furthest from every road leaving the town.
  const wild = [], homeC = W.cities.find(c => c.id === v.home);
  mineC.forEach(c => (c.reaches || []).filter(rc => !routesOf(c).some(r => (r.crosses || [])[0] === rc.ground)).forEach(rc => {
    const hx0 = hexOf(...WL.pos[c.id]); if (!hx0) return;
    const taken = routesOf(c).map(r => { const o = r.a === c.id ? r.b : r.a; return Math.atan2(WL.pos[o][1] - WL.pos[c.id][1], WL.pos[o][0] - WL.pos[c.id][0]); });
    const n = Math.max(1, Math.round((rc.miles + 6) / hexMiles));   // from the town's middle: its own half-hex, then the reach's miles
    const dir = DIRS.map(([dq, dr]) => { const [dx, dz] = hexC(dq, dr, 1); return [dq, dr, Math.atan2(dz, dx)]; })
      .map(d => [d, Math.min(...taken.map(b2 => Math.abs(Math.atan2(Math.sin(d[2] - b2), Math.cos(d[2] - b2)))), Math.PI)]).sort((p1, p2) => p2[1] - p1[1])[0][0];
    [[0, 0], [dir[0], dir[1]]].forEach(([eq, er]) => { const hx = grid.get(key(hx0.q + dir[0] * n + eq, hx0.r + dir[1] * n + er)); if (hx && hx.nation === v.nation) ground.set(key(hx.q, hx.r), rc.ground); });
  }));
  if (homeHere && pos[v.home]) {
    const home = pos[v.home], gateRow = (T.ways[Object.keys(T.ways).find(i => /urban:the-gate$/.test(i))] || []);
    const minutesTo = id => { const r = gateRow.find(w => w.id === id); return r ? r.minutes : 60; };
    const outside = [...F.found].filter(i => T.settings[i] === "outside");
    const reachOf = i => (homeC.reaches || []).find(rc => T.names[i] === rc.name);
    // Each wild place goes to the nearest hex of its own ground (woods to forest, desert to sand).
    outside.filter(i => !/@the-(outskirts|crossroads)$|@the-road-to-|^.*~underground:/.test(i)).sort().forEach(i => {
      const rc = reachOf(i), want = rc ? rc.ground : /desert/.test(i) ? "desert" : "forest", used = new Set(wild.map(w => key(w.hx.q, w.hx.r)));
      const cands = mine.filter(x => ground.get(key(x.q, x.r)) === want && !(x.q === home.q && x.r === home.r) && !used.has(key(x.q, x.r)))
        .sort((p1, p2) => Math.hypot(p1.x - home.x, p1.z - home.z) - Math.hypot(p2.x - home.x, p2.z - home.z));
      const hx = cands[0] || home;
      pos[i] = hx; around(hx);
      wild.push({ id: i, hx, kind: want === "desert" ? "dunes" : "trees", hours: minutesTo(i) / 60, miles: rc ? rc.miles : null });
    });
    // Just outside the gate: the outskirts and the crossroads, small pieces in the town's own hex.
    outside.filter(i => /@the-(outskirts|crossroads)$/.test(i)).sort().forEach((i, n) => { pos[i] = { ...home, x: home.x + (n ? 2 : -1.8), z: home.z - 2.8 }; wild.push({ id: i, hx: pos[i], kind: "post", small: true }); });   // well inside the town's hex: at 4.2 it sat on the hex beyond
    // The cave and anything else underground hangs off its host's piece.
    outside.filter(i => /~underground:/.test(i)).forEach(i => { const host = outside.find(h => i.includes("/" ) && h.endsWith("@" + i.split(":")[1].split("/")[0])); if (host && pos[host]) pos[i] = pos[host]; });
  }
  roadsOut.forEach(rd => { if (!pos[rd.from]) return;
    for (let t = 0; t < 30; t++) { const hx = hexOf(WL.pos[rd.from][0] + Math.cos(rd.bearing) * t * rW, WL.pos[rd.from][1] + Math.sin(rd.bearing) * t * rW); if (hx) known.add(key(hx.q, hx.r)); } });
  [...mine, ...ring].forEach(x => {
    const k = key(x.q, x.r), isMine = x.nation === v.nation, land = !!x.nation, kn = known.has(k);
    const tile = !land ? "hex/water" : TILE_OF[ground.get(k)] || "hex/grass";
    hexes.push({ q: x.q, r: x.r, x: x.x, z: x.z, tile, nation: x.nation, known: kn || !isMine, plate: land && (isMine ? kn : true), plateOpacity: isMine ? .55 : .25, cloud: isMine && land && !kn });
  });
  const b = hexBoard(hexes, h, wash, { [v.nation]: W.nations[v.nation].name });
  board = { ...b, wash, knownNations: new Set(), pos: {} };
  const P3 = hx => new THREE.Vector3(hx.x, 1.05, hx.z);
  knownTowns.forEach(id => { const hx = pos[id], how = K.how[id], o = miniature("town", { painted: how.by === "been" });
    place(o, id, hx.x, hx.z, .8).position.y = 0; o.userData.name = W.cities.find(c => c.id === id).name; o.userData.seen = how.by !== "been"; board.pos[id] = P3(hx); });
  wild.forEach(w => { const o = miniature(w.kind, { painted: F.visited.has(w.id) });
    place(o, w.id, w.hx.x, w.hx.z, w.small ? 1.1 : 1.8).position.y = 1.05; o.userData.name = M.bare(T.names[w.id]); o.userData.seen = !F.visited.has(w.id);
    o.userData.down = !!MapUI.siteFor(w.id); if (!w.small) o.userData.road = (w.hours < 1.5 ? `${Math.round(w.hours * 60)} minutes` : `about ${Math.round(w.hours)} hours`) + " from the gate" + (w.miles ? `, ${w.miles} miles` : "");
    board.pos[w.id] = P3(w.hx);
    if (!w.small && pos[v.home]) roadStrip([pos[v.home].x, pos[v.home].z], [w.hx.x, w.hx.z], "track", 1.09, .7); });
  Object.keys(pos).forEach(id => { if (!board.pos[id]) board.pos[id] = P3(pos[id]); });
  // Roads: between towns of the nation, a strip; leaving it, a strip to the border and an arrow.
  roadsOut.forEach(rd => { const a = pos[rd.from]; if (!a) return;
    if (rd.inside && pos[rd.to]) { roadStrip([a.x, a.z], [pos[rd.to].x, pos[rd.to].z], rd.by === "river" ? "river" : "road"); return; }
    let last = a; for (let t = 1; t < 40; t++) { const g = grid.get(key(...(() => { const wx = WL.pos[rd.from][0] + Math.cos(rd.bearing) * t * rW * .5, wy = WL.pos[rd.from][1] + Math.sin(rd.bearing) * t * rW * .5;
      let best = 1e18, bq = null; mine.forEach(x => { const d = (x.wx - wx) ** 2 + (x.wy - wy) ** 2; if (d < best) { best = d; bq = x; } }); return best < rW * rW ? [bq.q, bq.r] : [9999, 9999]; })()));
      if (!g) break; last = g; }
    const end = [last.x + Math.cos(rd.bearing) * h * 1.2, last.z + Math.sin(rd.bearing) * h * 1.2];
    roadStrip([a.x, a.z], end, rd.by === "river" ? "river" : "road"); dayPegs([a.x, a.z], end, Math.min(rd.miles || 0, 24 * Math.round(Math.hypot(end[0] - a.x, end[1] - a.z) / (h * 1.73) / 2)), 1.4);
    const arrow = new THREE.Group(), cone = mesh(new THREE.ConeGeometry(1.2, 2.6, 12), mat(0x5a3a22)); cone.rotation.z = -Math.PI / 2; cone.position.y = 1.6; arrow.add(cone);
    place(arrow, "out:" + rd.to, end[0], end[1], 1); arrow.rotation.y = -rd.bearing;
    const to = W.cities.find(c => c.id === rd.to);
    arrow.userData.name = `to ${to.name}`; arrow.userData.road = `${W.nations[to.nation].name}${rd.miles ? `, ${rd.miles} miles` : ""}`;
    arrow.userData.open = ["continent", cont]; });
}

// A name painted flat on the board: Cinzel capitals in the nation's dark ink with a pale
// halo, as wide as `maxW` world units allows (never wider than its own height suggests).
function flatName(text, ink, x, z, maxW) {
  const fs = 72, c = document.createElement("canvas"), g = c.getContext("2d");
  const font = `600 ${fs}px Cinzel, Palatino Linotype, Georgia, serif`;
  g.font = font; try { g.letterSpacing = "14px"; } catch (e) { /* older canvas */ }
  c.width = Math.ceil(g.measureText(text).width + 48); c.height = Math.ceil(fs * 1.5);
  g.font = font; try { g.letterSpacing = "14px"; } catch (e) { /* as above */ }
  g.textAlign = "center"; g.textBaseline = "middle";
  g.lineWidth = 12; g.strokeStyle = "rgba(244,236,214,.92)"; g.strokeText(text, c.width / 2, c.height / 2);
  g.fillStyle = ink; g.fillText(text, c.width / 2, c.height / 2);
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
  const w = Math.min(maxW, text.length * 3.4), h = w * c.height / c.width;
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false }));
  plane.rotation.x = -Math.PI / 2; plane.position.set(x, 1.3, z); plane.renderOrder = 2;
  return plane;
}
function segD(p, a, b) { const dx = b[0] - a[0], dy = b[1] - a[1], L2 = dx * dx + dy * dy || 1, t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2));
  return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy); }

// The site: a dollhouse. Each room an open box, back walls only; passages between; rooms not
// entered are not built; rooms only seen are a chalk outline on the table.
const sitePos = (v, id) => [(v.S.col[id] - (v.S.cols - 1) / 2) * 15, (v.S.row[id] - (v.S.rows - 1) / 2) * 13];
function site(v) {
  const { S, site: st } = v, seen = new Set();
  st.been.forEach(i => (S.adj[i] || []).forEach(n => { if (!st.been.has(n)) seen.add(n); }));
  const grid = new THREE.GridHelper(160, 40, 0x6a5a40, 0x4a3a28); grid.position.y = .06; grid.material.opacity = .35; grid.material.transparent = true; world.add(grid);
  S.passages.forEach(([a, b]) => { if (!st.been.has(a) && !st.been.has(b)) return; const p = sitePos(v, a), q = sitePos(v, b), mid = (p[0] + q[0]) / 2;
    [[p, [mid, p[1]]], [[mid, p[1]], [mid, q[1]]], [[mid, q[1]], q]].forEach(([s, e]) => { const L = Math.hypot(e[0] - s[0], e[1] - s[1]); if (!L) return;
      const f = mesh(new THREE.BoxGeometry(L + 2.2, .3, 2.2), mat(0x4a3f32)); f.position.set((s[0] + e[0]) / 2, .15, (s[1] + e[1]) / 2); f.rotation.y = -Math.atan2(e[1] - s[1], e[0] - s[0]); world.add(f); }); });
  Object.keys(S.col).forEach(i => {
    const [x, z] = sitePos(v, i), r = st.rooms.find(q => q.id === i), been = st.been.has(i);
    if (!been && !seen.has(i)) return;
    const g = new THREE.Group(), W = 10, D = 8, H = 4;
    if (been) {
      g.add(mesh(new THREE.BoxGeometry(W, .4, D), mat(i === v.here ? 0x7a6a52 : 0x655845)));
      const back = mesh(new THREE.BoxGeometry(W, H, .5), mat(0x4d4234)); back.position.set(0, H / 2, -D / 2); g.add(back);
      const side = mesh(new THREE.BoxGeometry(.5, H, D), mat(0x5a4d3c)); side.position.set(-W / 2, H / 2, 0); g.add(side);
      if (r.role === "climax") { const t = mesh(new THREE.BoxGeometry(2.4, 2, 1.6), mat(0x6a3030)); t.position.set(2, 1, -2); g.add(t); }
      if (i === v.here) { const torch = new THREE.PointLight(0xffa850, 120, 26, 1.8); torch.position.set(-4, 3.2, -2.5); g.add(torch); candles.push({ light: torch, base: 120, site: true });
        const fl = new THREE.Mesh(new THREE.ConeGeometry(.25, .7, 6), new THREE.MeshBasicMaterial({ color: 0xffc060 })); fl.position.copy(torch.position); g.add(fl); }
    } else {
      const edge = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(W, .2, D)), new THREE.LineDashedMaterial({ color: 0xe8dcc0, dashSize: .6, gapSize: .4 }));
      edge.computeLineDistances(); g.add(edge);
      const pad = new THREE.Mesh(new THREE.BoxGeometry(W, .1, D), new THREE.MeshBasicMaterial({ transparent: true, opacity: 0 })); g.add(pad);
    }
    place(g, i, x, z); g.userData.name = been ? M.bare(r.name) : "?"; g.userData.seen = !been;
  });
}

// --- The world: a second scroll, every city the PC knows of, and how --------------------
// The land is painted for the whole world (it is the paper, not knowledge); fog covers all
// of it but round the cities known, as the town's paper does. A city stood in is a painted
// village; one known from a road sign, talk or a map is primer grey, with a flag in the
// colour of how it was learned.
const WU = .07, HOW_FLAG = { been: 0x27406e, road: 0x8a6a3a, heard: 0x2e7d5b, map: 0x8e2317 };
let gridOut = null;
function drawWorld(c, v, half) {
  const g = c.getContext("2d"), S = c.width / (half * 2), P = ([x, y]) => [(x + half) * S, (y + half) * S];
  for (let x = 0; x < c.width; x += 720) for (let y = 0; y < c.height; y += 720) g.drawImage(paperImg, x, y, 720, 720 * paperImg.height / paperImg.width);
  g.fillStyle = "rgba(70,110,140,.28)"; g.fillRect(0, 0, c.width, c.height);   // the sea, a wash over the paper
  // Land: a blot round every city, merged, with an inked coast (drawn twice: the ink, then the land over it).
  const land = document.createElement("canvas"); land.width = c.width; land.height = c.height; const l = land.getContext("2d");
  const blots = (ctx, grow) => v.W.cities.forEach((city, n) => { const [x, y] = P(v.WL.pos[city.id]);
    for (let k = 0; k < 5; k++) { const a = n * 1.7 + k * 1.26, r = (70 + (n * 37 + k * 13) % 40) * S + grow; ctx.beginPath(); ctx.arc(x + Math.cos(a) * 30 * S, y + Math.sin(a) * 30 * S, r, 0, 7); ctx.fill(); } });
  l.fillStyle = "#3b2a1c"; blots(l, 5 * S * 4); l.globalCompositeOperation = "source-over";
  l.fillStyle = "#e8dcbc"; blots(l, 0);
  g.globalAlpha = .9; g.drawImage(land, 0, 0); g.globalAlpha = 1;
  // Nations: every bit of land belongs to its nearest city's nation (a Voronoi partition over
  // the cities, as Azgaar's generator partitions its cells). A faint wash of the nation's
  // ink, and a dotted line where two nations meet. Drawn on a 4 px grid of the 2048 sheet.
  const nations = Object.keys(v.W.nations), names = nations.map(n => v.W.nations[n].name);
  const N = 512, cell = c.width / N, owner = new Int16Array(N * N).fill(-1);
  gridOut = { N, owner, nations, knownConts: new Set(Object.keys(v.K.how).map(id => (v.W.cities.find(x => x.id === id) || {}).continent)) };
  const la = l.getImageData(0, 0, c.width, c.height).data;
  const cities = v.W.cities.map(ci => { const [x, y] = P(v.WL.pos[ci.id]); return [x, y, nations.indexOf(ci.nation)]; });
  for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
    const x = (i + .5) * cell, y = (j + .5) * cell;
    if (la[((y | 0) * c.width + (x | 0)) * 4 + 3] < 128) continue;   // sea
    let best = 1e18, who = -1;
    for (const [cx, cy, n] of cities) { const d = (cx - x) ** 2 + (cy - y) ** 2; if (d < best) { best = d; who = n; } }
    owner[j * N + i] = who;
  }
  // A clear watercolour wash per nation (it was .13 of a dark ink: the owner could not tell
  // nations apart), in colours chosen so neighbours never match.
  const wash = M.nationColours(v.W);
  g.globalAlpha = .38;
  for (let k = 0; k < N * N; k++) if (owner[k] >= 0) { g.fillStyle = wash[nations[owner[k]]]; g.fillRect((k % N) * cell, Math.floor(k / N) * cell, cell + .5, cell + .5); }
  g.globalAlpha = .85; g.fillStyle = "#4a1e14";
  for (let j = 0; j < N - 1; j++) for (let i = 0; i < N - 1; i++) {
    const a = owner[j * N + i]; if (a < 0) continue;
    const r = owner[j * N + i + 1], d = owner[(j + 1) * N + i];
    if ((i + j) % 3 === 0) continue;   // dotted, not solid: a border, not a coast
    if (r >= 0 && r !== a) g.fillRect((i + 1) * cell - 1.5, j * cell, 3, cell);
    if (d >= 0 && d !== a) g.fillRect(i * cell, (j + 1) * cell - 1.5, cell, 3);
  }
  g.globalAlpha = 1;
  // Roads you know.
  v.K.roads.forEach(r => { const a = P(v.WL.pos[r.a]), b = P(v.WL.pos[r.b]), both = v.K.how[r.a].by === "been" && v.K.how[r.b].by === "been";
    g.strokeStyle = r.by === "sea" ? "#2f5d7c" : r.by === "river" ? "#3d6a8a" : "#3b2a1c"; g.lineWidth = r.by === "road" ? 5 : 4;
    g.setLineDash(r.by === "sea" ? [4, 10] : both ? [] : [16, 10]); g.beginPath(); g.moveTo(...a); g.lineTo(...b); g.stroke(); });
  g.setLineDash([]);
  // Fog: a sheet of cloud with a hole round every city known.
  const fog = document.createElement("canvas"); fog.width = c.width; fog.height = c.height; const f = fog.getContext("2d");
  f.fillStyle = "rgba(246,244,240,.94)"; f.fillRect(0, 0, fog.width, fog.height);
  f.globalCompositeOperation = "destination-out";
  Object.keys(v.K.how).forEach(id => { const [x, y] = P(v.WL.pos[id]), r = 150 * S; const gr = f.createRadialGradient(x, y, r * .3, x, y, r);
    gr.addColorStop(0, "rgba(0,0,0,1)"); gr.addColorStop(1, "rgba(0,0,0,0)"); f.fillStyle = gr; f.fillRect(x - r, y - r, r * 2, r * 2); });
  g.drawImage(fog, 0, 0);
  // A nation's name once one of its cities is known, in its ink, spaced capitals at the middle
  // of its cities. Drawn over the fog: you know the name, if not the land.
  const knownNations = new Set(Object.keys(v.K.how).map(id => (v.W.cities.find(x => x.id === id) || {}).nation));
  g.textAlign = "center"; g.textBaseline = "middle"; g.font = `600 ${Math.round(9 * S * 3)}px Cinzel, Palatino Linotype, Georgia, serif`;
  try { g.letterSpacing = `${Math.round(4 * S)}px`; } catch (e) { /* older canvas: no spacing */ }
  // Where each name goes: the point of its territory farthest from any border or coast (the
  // "pole of inaccessibility" Mapbox's polylabel finds), from a chamfer distance over the
  // owner grid. At the middle of its towns, three of Featherperch's neighbours' names landed
  // on top of each other: their towns sit close, their land does not.
  const dist = new Float32Array(N * N);
  for (let k = 0; k < N * N; k++) {
    const i = k % N, j = (k / N) | 0, o = owner[k];
    dist[k] = o < 0 || i === 0 || j === 0 || i === N - 1 || j === N - 1 || owner[k - 1] !== o || owner[k + 1] !== o || owner[k - N] !== o || owner[k + N] !== o ? 0 : 1e9;
  }
  for (let j = 1; j < N; j++) for (let i = 1; i < N - 1; i++) { const k = j * N + i; if (dist[k]) dist[k] = Math.min(dist[k], dist[k - 1] + 1, dist[k - N] + 1, dist[k - N - 1] + 1.41, dist[k - N + 1] + 1.41); }
  for (let j = N - 2; j >= 0; j--) for (let i = N - 2; i > 0; i--) { const k = j * N + i; if (dist[k]) dist[k] = Math.min(dist[k], dist[k + 1] + 1, dist[k + N] + 1, dist[k + N + 1] + 1.41, dist[k + N - 1] + 1.41); }
  // Obstacles a nation's name keeps clear of: each known town's pin (not its floating tag,
  // which moves with the camera; reserving room for it left Ledgernook's own nation, Undertide
  // Warrens, with no spot at all) and the continent names (drawn below, at fixed spots).
  const placedNames = Object.keys(v.K.how).map(id => { const [x, y] = P(v.WL.pos[id]); return [x - 18 * S, y - 18 * S, x + 18 * S, y + 18 * S]; });
  g.save(); g.font = `italic ${Math.round(16 * S * 3)}px Palatino Linotype, Georgia, serif`;
  const contSeen = new Set(Object.keys(v.K.how).map(id => (v.W.cities.find(x => x.id === id) || {}).continent));
  Object.entries(v.WL.centre).forEach(([cid, [x, y]]) => { if (!contSeen.has(cid)) return; const [px, py] = P([x, y - 250]), cw = g.measureText(v.W.continents[cid]).width, ch = 16 * S * 3;
    placedNames.push([px - cw / 2, py - ch, px + cw / 2, py + ch * .4]); });
  g.restore();
  // Every name lies wholly inside its own nation (the owner's rule): a spot counts only if all
  // the land under the name's box is that nation's. Deepest spots first; if none fits, the name
  // is set a size smaller, down to a floor, before it gives up.
  const tally = { placed: [], missed: [] };   // read by the check: a name that found no room is reported, not lost quietly
  knownNations.forEach(n => { if (!n || !v.W.nations[n]) return;
    const me = nations.indexOf(n), text = v.W.nations[n].name.toUpperCase();
    const spots = [];
    for (let k = 0; k < N * N; k++) if (owner[k] === me && dist[k] > 1) spots.push(k);
    spots.sort((x, y) => dist[y] - dist[x]);
    // One line at shrinking sizes; then, for a narrow nation, the name broken over two lines
    // (Undertide Warrens' wedge held no single line even at the smallest size).
    const words = text.split(" "), cut = Math.ceil(words.length / 2);
    const tries = [9, 7.5, 6.2, 5, 4].map(size => [size, [text]]).concat(words.length > 1 ? [7.5, 6.2, 5, 4].map(size => [size, [words.slice(0, cut).join(" "), words.slice(cut).join(" ")]]) : []);
    for (const [size, lines] of tries) {
      const fs = Math.round(size * S * 3);
      g.font = `600 ${fs}px Cinzel, Palatino Linotype, Georgia, serif`;
      try { g.letterSpacing = `${Math.round(size * .45 * S)}px`; } catch (e) { /* older canvas */ }
      const w = Math.max(...lines.map(x => g.measureText(x).width)) + 8, h = fs * 1.15 * lines.length, hw = Math.ceil(w / 2 / cell), hh = Math.ceil(h / 2 / cell);
      const inside = (ci, cj) => { for (let dj = -hh; dj <= hh; dj++) for (let di = -hw; di <= hw; di += 1) {
        const ii = ci + di, jj = cj + dj; if (ii < 0 || jj < 0 || ii >= N || jj >= N || owner[jj * N + ii] !== me) return false; } return true; };
      const free = (x, y) => !placedNames.some(b => x - w / 2 < b[2] && x + w / 2 > b[0] && y - h / 2 < b[3] && y + h / 2 > b[1]);
      const k = spots.find(k => dist[k] >= hh && inside(k % N, (k / N) | 0) && free(((k % N) + .5) * cell, (((k / N) | 0) + .5) * cell));
      if (k === undefined) continue;
      const px = ((k % N) + .5) * cell, py = (((k / N) | 0) + .5) * cell;
      placedNames.push([px - w / 2, py - h / 2, px + w / 2, py + h / 2]);
      g.lineWidth = Math.max(3, fs / 6); g.strokeStyle = "rgba(244,236,214,.9)"; g.fillStyle = M.darken(wash[n], .42);
      lines.forEach((line, li) => { const ly = py + (li - (lines.length - 1) / 2) * fs * 1.1; g.strokeText(line, px, ly); g.fillText(line, px, ly); });
      tally.placed.push(text + (lines.length > 1 ? " (2 lines)" : "") + " @" + size);
      return;
    }
    tally.missed.push(text);
  });
  window.__nationNames = tally;
  try { g.letterSpacing = "0px"; } catch (e) { /* as above */ }
  // A continent's name only once a city on it is known: the paper does not name what you have not heard of.
  g.fillStyle = "rgba(59,42,28,.55)"; g.textAlign = "center"; g.font = `italic ${Math.round(16 * S * 3)}px Palatino Linotype, Georgia, serif`;  // the worst case ran two continent names together at 46
  const seen = new Set(Object.keys(v.K.how).map(id => (v.W.cities.find(x => x.id === id) || {}).continent));
  Object.entries(v.WL.centre).forEach(([cid, [x, y]]) => { if (!seen.has(cid)) return; const [px, py] = P([x, y - 250]); g.fillText(v.W.continents[cid], px, py); });
}
function worldMap(v) {
  const xs = Object.values(v.WL.pos), half = Math.max(...xs.map(p => Math.max(Math.abs(p[0]), Math.abs(p[1])))) + 160;
  // The paper is painted once per state of knowledge: pressing a city changes nothing on it,
  // and painting the nations (a nearest-city pass over 512x512 cells) blocked a press 740 ms.
  const key = Object.keys(v.K.how).sort().join() + "|" + half;
  if (!worldPaper || worldPaper.key !== key) {
    const cv = document.createElement("canvas"); cv.width = cv.height = 2048; drawWorld(cv, v, half); worldPaper = { key, c: cv, grid: gridOut, hl: {} }; }
  const c = worldPaper.c;
  paperTex = new THREE.CanvasTexture(c); paperTex.colorSpace = THREE.SRGBColorSpace; paperTex.anisotropy = 8;
  const size = half * 2 * WU;
  const sheet = new THREE.Mesh(new THREE.PlaneGeometry(size, size), new THREE.MeshStandardMaterial({ map: paperTex, roughness: .95 }));
  sheet.rotation.x = -Math.PI / 2; sheet.position.y = .05; sheet.receiveShadow = true; world.add(sheet); worldSheet = sheet;
  // The highlight layer: a lit continent painted on a sheet just above the paper.
  const hlC = document.createElement("canvas"); hlC.width = hlC.height = 512;
  const hl = new THREE.Mesh(new THREE.PlaneGeometry(size, size), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(hlC), transparent: true, depthWrite: false }));
  hl.rotation.x = -Math.PI / 2; hl.position.y = .09; hl.renderOrder = 2; world.add(hl); worldPaper.hlMesh = hl; worldPaper.hlCanvas = hlC;
  world.add(scroll(size, size));
  Object.entries(v.K.how).forEach(([id, how]) => {
    const city = v.W.cities.find(x => x.id === id), [x, z] = [v.WL.pos[id][0] * WU, v.WL.pos[id][1] * WU];
    const o = miniature("town", { painted: how.by === "been" });
    place(o, id, x, z, .2);
    // A map pin by each town, coloured by how you know it (stood in, road sign, talk, map).
    const pin = mesh(new THREE.ConeGeometry(.22, .9, 8), mat(HOW_FLAG[how.by])); pin.rotation.x = Math.PI; pin.position.set(x + 1.3, 1.6, z - .6); world.add(pin);
    const head = mesh(new THREE.SphereGeometry(.3, 12, 8), mat(HOW_FLAG[how.by], { flatShading: false })); head.position.set(x + 1.3, 2.1, z - .6); world.add(head);
    o.userData.name = city.name; o.userData.seen = how.by !== "been";
  });
}

// Light the continent under the pointer: its land in a warm glow with a gold edge.
function paintWorldHighlight() {
  if (!worldPaper || !worldPaper.hlCanvas) return;
  const g = worldPaper.grid, c = worldPaper.hlCanvas, x = c.getContext("2d"), N = g.N;
  x.clearRect(0, 0, c.width, c.height);
  if (hover.continent) {
    const inC = new Int8Array(N * N); for (let k = 0; k < N * N; k++) inC[k] = g.owner[k] >= 0 && V.W.nations[g.nations[g.owner[k]]].continent === hover.continent ? 1 : 0;
    x.fillStyle = "rgba(255,226,150,.30)"; for (let k = 0; k < N * N; k++) if (inC[k]) x.fillRect(k % N, (k / N) | 0, 1, 1);
    x.fillStyle = "rgba(196,140,40,.95)";
    for (let k = N; k < N * N - N; k++) if (inC[k] && (!inC[k - 1] || !inC[k + 1] || !inC[k - N] || !inC[k + N])) x.fillRect((k % N) - .5, ((k / N) | 0) - .5, 2, 2);
  }
  worldPaper.hlMesh.material.map.needsUpdate = true;
}

// --- The PC, the route, the walk ----------------------------------------------------------
function posOf(id) {
  const v = V;
  if (v.level === "town") { const p = v.T.settings[id] === "outside" ? (v.L.gate ? v.L.pos[v.L.gate] : null) : M.anchor(v.L, id); return p && townXZ(p); }   // outside the walls: at the gate
  if (v.level === "world") { const p = v.WL.pos[id]; return p && new THREE.Vector3(p[0] * WU, .1, p[1] * WU); }
  if (v.level === "continent" || v.level === "nation") {
    if (board && board.pos[id]) return board.pos[id];
    if (v.level === "nation" && v.T.settings[id] === "in" && board && board.pos[v.home]) return board.pos[v.home];   // a walk out starts in town
    return null;
  }
  const p = sitePos(v, id); return new THREE.Vector3(p[0], .4, p[1]);
}
function placePc() {
  const id = V.level === "nation" && V.T.settings[V.at] === "outside" && board && board.pos[V.at] ? V.at : V.here;
  const p = posOf(id); if (!p) return;
  pc.position.copy(p).add(new THREE.Vector3(V.level === "site" ? 1.5 : V.level === "world" ? 1 : 3.6, 0, V.level === "site" ? 1 : V.level === "world" ? 1 : 3.6)); pc.scale.setScalar(V.level === "site" ? 1.2 : V.level === "continent" || V.level === "nation" ? 1.2 : V.level === "world" ? .45 : 2);
}
let routeObj = null;
function routeLine() {
  if (!V.route) return;
  const pts = V.route.map(posOf).filter(Boolean).map(p => p.clone().setY(p.y + .35));
  const curve = new THREE.CatmullRomCurve3(pts, false, "catmullrom", .1);
  const geo = new THREE.TubeGeometry(curve, Math.max(8, pts.length * 12), .28, 6, false);
  routeObj = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: 0x3a5a9e, transparent: true, opacity: .85 }));
  world.add(routeObj);
}
function walk(ids, done) {
  const pts = ids.map(posOf).filter(Boolean);
  if (pts.length < 2 || api.reduced()) { done(); return; }
  const curve = new THREE.CatmullRomCurve3(pts, false, "catmullrom", .1), len = curve.getLength();
  walkAnim = { curve, start: performance.now(), dur: Math.min(3600, 800 + len * 60), done, over: false };
  setTimeout(() => endWalk(), walkAnim.dur + 150);   // a hidden window gets no frames; the walk still ends
}
function endWalk() { if (!walkAnim || walkAnim.over) return; walkAnim.over = true; const d = walkAnim.done; walkAnim = null; d(); }

function frameCamera() {
  const box = new THREE.Box3(); pick.forEach(o => box.expandByObject(o));
  if (box.isEmpty()) return;
  const c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3()).length();
  controls.target.copy(c);
  const d = Math.min(Math.max(size * (V.level === "site" ? 1.25 : V.level === "continent" ? 1.15 : V.level === "nation" ? 1.25 : V.level === "world" ? .9 : .95), 30), 240);
  camera.position.set(c.x - d * .05, d * .86, c.z + d * .56);
  // Room past the opening view to fade the town names out before the zoom-out gesture
  // (region -> world) fires at the furthest distance.
  frameD = d; controls.maxDistance = Math.max(260, d * 1.6);
  controls.update();
}

// --- Each frame ---------------------------------------------------------------------------
const tmp = new THREE.Vector3();
function frame() {
  const t = clock.getElapsedTime(), still = api.reduced(), now = performance.now();
  controls.update();
  fps.n++; if (now - fps.t > 1000) { fps.value = Math.round(fps.n * 1000 / (now - fps.t)); fps.n = 0; fps.t = now; const f = stage.querySelector("#fps"); if (f) f.textContent = fps.value + " fps"; }
  if (V && world) {
    // The hour: the window light swings and warms; at night the candles carry the table.
    const L = V.light, h = V.hour, day = Math.max(0, Math.sin((h - 6) / 12 * Math.PI));
    sun.color.setRGB(L.night ? .45 : 1, L.night ? .55 : (L.r / 255 * .3 + .7) * (L.g / 255 * .25 + .75), L.night ? .9 : .82 + L.b / 255 * .18);
    sun.intensity = L.night ? .35 : .6 + day * 2.2; sun.position.set(-90 * Math.cos((h - 6) / 12 * Math.PI), 30 + day * 80, 40);
    hemi.intensity = L.night ? .14 : .3 + day * .45;
    if (V.level === "site") { sun.intensity = .25; hemi.intensity = .18; }  // underground: the torch and the candles carry it
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
    if (world) world.children.forEach(o => { if (o.userData.grow) { const u = Math.min(1, (now - o.userData.grow) / 900); o.scale.setScalar((o.userData.size || 1) * (.01 + .99 * (1 - Math.pow(1 - u, 3)))); if (u >= 1) delete o.userData.grow; } });
    if (walkAnim && pc) { const u = Math.min(1, (now - walkAnim.start) / walkAnim.dur), e = u < .5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;
      const p = walkAnim.curve.getPointAt(e), q = walkAnim.curve.getPointAt(Math.min(1, e + .01));
      pc.position.set(p.x, p.y + Math.abs(Math.sin(e * walkAnim.curve.getLength() * .9)) * .6, p.z); pc.lookAt(q.x, pc.position.y, q.z);
      if (u >= 1) endWalk(); }
  }
  if (tiltOn) { renderer.setRenderTarget(rt); renderer.render(scene, camera); renderer.setRenderTarget(null);
    const s = renderer.getDrawingBufferSize(new THREE.Vector2()); postMat.uniforms.res.value.copy(s); renderer.render(postScene, postCam); }
  else renderer.render(scene, camera);
  lastInfo = { calls: renderer.info.render.calls, triangles: renderer.info.render.triangles }; renderer.info.reset();
  labels(); rain(t, still);
}
let lastInfo = { calls: 0, triangles: 0 };

// Names on the board: HTML tags over each miniature, nudged up when they would overlap.
function labels() {
  const r = stage.getBoundingClientRect(), placed = [];
  // Zoom fading, on the region and the world (the owner's idea, 2026-11-18): town names are
  // full at the view the map opens at and fade out as you pull back further, while the nation
  // names come up; where you are, the place pressed, the place under the pointer and your route
  // never fade. A faded name takes no room, so it cannot push a nation's name aside.
  const dist = camera.position.distanceTo(controls.target);
  const fade = ["region", "world", "continent", "nation"].includes(V.level) ? Math.min(1, Math.max(0, (dist - frameD) / (frameD * .4))) : 0;
  let html = "";
  // Names that cannot find room are not drawn: the place stays, pressable, and its name shows
  // on hover, when pressed, or as you zoom in and room opens up. This is how map labelling
  // keeps a dense place readable (Mapbox and Google Maps drop colliding labels by priority).
  const here = V.level === "town" ? M.baseOf(V.here) : V.here;
  const rank = o => { const id = o.userData.id; return id === here ? 0 : id === V.sel ? 1 : id === hoverId ? 2 : (V.route || []).includes(id) ? 3 : o.userData.seen ? 5 : 4; };
  pick.slice().sort((a, b) => rank(a) - rank(b)).forEach(o => {
    o.getWorldPosition(tmp); tmp.y += V && V.level === "site" ? 1 : V.level === "town" ? 7.5 : V.level === "world" ? 1.6 : V.level === "continent" ? 3.4 : 4.2; tmp.project(camera);  // the world's villages are small: a tag 5 up floated off them
    if (tmp.z > 1) return;
    let x = (tmp.x + 1) / 2 * r.width, y = (1 - tmp.y) / 2 * r.height;
    if (x < -40 || x > r.width + 40 || y < -10 || y > r.height + 40) return;
    const name = o.userData.name || "", w = Math.min(Math.max(name.length * 7.2, String(o.userData.road || "").length * 6.2), 190) + 16   /* a two-line tag is as wide as its longer line */ + (o.userData.badge ? 22 : 0) + (o.userData.down ? 22 : 0);
    const h = o.userData.road ? 34 : 20;   // a road's tag has its days on a second line
    const hit = yy => placed.some(b => x - w / 2 < b[2] + 4 && x + w / 2 > b[0] - 4 && yy - h < b[3] + 2 && yy > b[1] - 2);
    const must = rank(o) <= 3;
    let n = 0; while (n < 3 && hit(y)) { y -= h + 2; n++; }
    if (hit(y) && !must) return;
    const op = must ? 1 : 1 - fade;
    if (op < .04) return;
    if (op > .5) placed.push([x - w / 2, y - h, x + w / 2, y]);
    const id = o.userData.id, cls = (V.sel === id ? " sel" : "") + (o.userData.seen ? " seen" : "") + (V.here === id || (V.level === "town" && M.baseOf(V.here) === id) ? " here" : "");
    html += `<span class="tag${cls}" style="opacity:${op.toFixed(2)};transform:translate(${x.toFixed(0)}px,${y.toFixed(0)}px) translate(-50%,-100%)" title="${name}"><span class="nm">${name}</span>${
      o.userData.badge ? `<b>${o.userData.badge}</b>` : ""}${o.userData.down ? `<b class="dn">↓</b>` : ""}${o.userData.road ? `<i>${String(o.userData.road).replace(/^about /, "").replace(/ on foot$/, "")}</i>` : ""}</span>`;
  });
  // Nation names on the region: stepped up or down until clear of each other (Sandmere Shire
  // and Kharzun Delve met over Featherperch, their known hexes being the same few).
  const areaBoxes = [];
  const ar = areas.map(a => { tmp.copy(a.at).project(camera); if (tmp.z > 1) return "";
    const x = (tmp.x + 1) / 2 * r.width, w = a.text.length * (13 + 5 * fade) + 20;  // wider as they grow
    let y = (1 - tmp.y) / 2 * r.height;
    const clash = yy => areaBoxes.concat(placed).some(b => x - w / 2 < b[2] && x + w / 2 > b[0] && yy - 12 < b[3] && yy + 12 > b[1]);  // clear of town tags too
    for (const dy of [0, 26, -26, 52, -52, 78, -78, 104]) if (!clash(y + dy)) { y += dy; break; }
    areaBoxes.push([x - w / 2, y - 12, x + w / 2, y + 12]);
    return `<span class="area" style="opacity:${(.8 + .2 * fade).toFixed(2)};font-size:${(15 + 5 * fade).toFixed(1)}px;color:${a.ink};transform:translate(${x.toFixed(0)}px,${y.toFixed(0)}px) translate(-50%,-50%)">${a.text}</span>`; }).join("");
  // What pressing the land would open, by the pointer.
  const lit = V.level === "world" && hover.continent ? V.W.continents[hover.continent] : V.level === "continent" && hover.nation ? V.W.nations[hover.nation].name : "";
  const hx = Math.min(hover.x + 14, r.width - lit.length * 10 - 50);   // kept on the board near the right edge
  const hint = lit ? `<span class="hint" style="transform:translate(${hx}px,${hover.y + 10}px)">Open ${lit}</span>` : "";
  tags.innerHTML = ar + html + hint;
}
let drops = [];
function rain(t, still) {
  const c = rainCv.getContext("2d"), W = rainCv.width, H = rainCv.height; c.clearRect(0, 0, W, H);
  if (!V || !V.rain) return;
  c.fillStyle = "rgba(30,40,60,.18)"; c.fillRect(0, 0, W, H);
  if (drops.length < 280) drops = Array.from({ length: 280 }, () => [Math.random() * W, Math.random() * H, .6 + Math.random() * .8]);
  c.strokeStyle = "rgba(200,215,235,.4)"; c.lineWidth = 1; c.beginPath();
  drops.forEach(d => { if (!still) { d[1] += 14 * d[2]; d[0] -= 3 * d[2]; if (d[1] > H) { d[1] = -10; d[0] = Math.random() * W * 1.1; } } c.moveTo(d[0], d[1]); c.lineTo(d[0] + 3 * d[2], d[1] - 12 * d[2]); });
  c.stroke();
}

window.TabletopRenderer = { init, draw, walk, levels: ["world", "continent", "nation"] };
