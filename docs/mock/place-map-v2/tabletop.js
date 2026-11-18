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
    if (hit) { let o = hit.object; while (o && !o.userData.id) o = o.parent; if (o) api.pick(o.userData.id); }
  });
  // Zoom out past the region's furthest and the world opens; zoom in hard on the world and
  // the region comes back. The breadcrumb does the same; this is the gesture the owner asked for.
  let lastLevelChange = 0;
  renderer.domElement.addEventListener("wheel", ev => {
    if (!V || performance.now() - lastLevelChange < 900) return;
    const d = camera.position.distanceTo(controls.target);
    if (V.level === "region" && ev.deltaY > 0 && d >= controls.maxDistance * .97) { lastLevelChange = performance.now(); api.open("world"); }
    else if (V.level === "world" && ev.deltaY < 0 && d <= controls.minDistance * 1.05) { lastLevelChange = performance.now(); api.open("region"); }
  }, { passive: true });
  // The name under the pointer always shows, even when it was culled to keep the map clear.
  renderer.domElement.addEventListener("pointermove", ev => {
    const r = renderer.domElement.getBoundingClientRect(), ray = new THREE.Raycaster();
    ray.setFromCamera(new THREE.Vector2((ev.clientX - r.left) / r.width * 2 - 1, -(ev.clientY - r.top) / r.height * 2 + 1), camera);
    const hit = ray.intersectObjects(pick, true)[0]; let o = hit && hit.object; while (o && !o.userData.id) o = o.parent;
    hoverId = o ? o.userData.id : null; renderer.domElement.style.cursor = o ? "pointer" : "grab";
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
  const { L, F } = v, found = [...F.found].filter(i => L.pos[i]);
  const gp = L.gate ? L.pos[L.gate] : [0, -385], wr = L.wall || Math.hypot(...gp);
  g.strokeStyle = "rgba(42,32,25,.6)"; g.lineWidth = 6; g.beginPath(); g.arc(...P([0, 0]), wr * S, 0, 7); g.stroke();
  Object.values(L.crossings).forEach(c2 => { if (F.found.has(c2)) { ink([0, 0], L.pos[c2], 34); ink([0, 0], L.pos[c2], 26, "#e9dcbc"); } });
  if (L.gate && F.found.has(L.gate)) { ink(L.pos[L.street[L.gate]], L.pos[L.gate], 30); ink(L.pos[L.street[L.gate]], L.pos[L.gate], 22, "#e9dcbc"); }
  found.forEach(i => { const s = L.street[i]; if (!s || ["crossing", "gate"].includes(L.kind[i])) return;
    const [x, y] = L.pos[i], [sx, sy] = L.pos[s]; const foot = sx === 0 && s !== L.square ? [0, y] : sy === 0 && s !== L.square ? [x, 0] : [sx, sy];
    ink(foot, [x, y], 5, F.visited.has(i) ? "#2a2019" : "#7d6b55", F.visited.has(i) ? null : [10, 8]); });
  const cr = found.find(i => /crossroads$/.test(i));
  if (cr) { ink(gp, L.pos[cr], 5, "#2a2019", [16, 10]); found.filter(i => ["roadhead", "sign"].includes(L.kind[i])).forEach(i => ink(L.pos[cr], L.pos[i], 4, "#2a2019", [14, 10])); }
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
  world = new THREE.Group(); scene.add(world); areas = []; pick = []; smoke = []; flags = []; clouds = []; routeObj = null;
  candles = candles.filter(c => !c.site);  // a room's torch goes with its room
}
let lastKey = "", hoverId = null, areas = [], frameD = 100, worldPaper = null;
// Nations in muted inks, by their sorted names, so a nation keeps its colour on both maps.
const NATION_INK = ["#8e2317", "#27406e", "#2e6b4a", "#7a5a1e", "#5b3a7a", "#7a3b55", "#2f6d75", "#6a4a2a"];
const inkOf = (all, name) => NATION_INK[[...all].sort().indexOf(name) % NATION_INK.length];
async function draw(v) {
  V = v;
  const key = v.level + (v.site ? v.site.key : "");
  const fresh = key !== lastKey; lastKey = key;
  await Promise.all([loadPaper(), loadKit()]);
  clear();
  if (v.level === "town") town(v); else if (v.level === "region") region(v); else if (v.level === "world") worldMap(v); else site(v);
  pc = pcMini(); world.add(pc); placePc();
  routeLine();
  if (fresh) frameCamera();
}
const townXZ = (p, y = 0) => new THREE.Vector3(p[0] * U, y, p[1] * U);
function place(o, id, x, z, size = 1) { o.position.set(x, 0, z); o.userData.id = id; o.userData.size = size; o.scale.setScalar(size); world.add(o); pick.push(o); return o; }

function town(v) {
  // The sheet is as big as the town: a street that has grown longer than the old sheet (the
  // worst case's sixteen-place street ran to 920 units, past a 560 half-sheet) gets more paper.
  const { L, F, T } = v, half = Math.max(560, ...Object.values(L.pos).map(p => Math.max(Math.abs(p[0]), Math.abs(p[1])) + 130));
  const c = document.createElement("canvas"); c.width = c.height = 2048; drawPaper(c, v, half);
  paperTex = new THREE.CanvasTexture(c); paperTex.colorSpace = THREE.SRGBColorSpace; paperTex.anisotropy = 8;
  const sheet = new THREE.Mesh(new THREE.PlaneGeometry(half * 2 * U, half * 2 * U), new THREE.MeshStandardMaterial({ map: paperTex, roughness: .95 }));
  sheet.rotation.x = -Math.PI / 2; sheet.position.y = .05; sheet.receiveShadow = true; world.add(sheet);
  world.add(scroll(half * 2 * U, half * 2 * U));
  const ward = i => { if (i === L.square) return "square"; const cc = L.kind[i] === "crossing" ? i : L.street[i];
    const m = /(north|east|south|west)-crossing/.exec(cc || ""); return m ? m[1] : "square"; };
  [...F.found].filter(i => L.pos[i]).forEach(i => {
    const storeys = (L.floors[i] || []).filter(f => M.floorOf(f) > 0).length + 1;
    const k = L.kind[i] === "crossing" ? "post" : kindOf(T.names[i]);
    const o = miniature(k, { storeys, colour: WARD[ward(i)], painted: F.visited.has(i) });
    const p = townXZ(L.pos[i]); place(o, i, p.x, p.z, 2.1);
    o.rotation.y = (i.length * 37 % 4) * Math.PI / 2 * .15;  // not every house square to the street
    o.userData.name = M.bare(T.names[i]); o.userData.badge = storeys > 1 ? storeys : ""; o.userData.down = !!MapUI.siteFor(i);
    o.userData.seen = !F.visited.has(i); o.userData.road = L.kind[i] === "roadhead" ? ((T.ways[i] || []).find(w => w.journey) || {}).time_words : "";
    if (v.fresh.has(i) && !v.reduced) { o.scale.setScalar(.01); o.userData.grow = performance.now(); }
  });
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
const hexCentre = (q, r) => [HX * Math.sqrt(3) * (q + r / 2), HX * 1.5 * r];
function region(v) {
  const { G } = v, R = 3.4;
  const pts = [...G.shown].map(i => G.pos[i]).concat(G.wild.filter(w => v.wildFound.has(w.id)).map(w => w.pos));
  const near = (x, y, d) => pts.some(p => Math.hypot(p[0] * U * R / 3.4 - x, p[1] * U * R / 3.4 - y) < d);
  const P = p => [p[0] * U * R, p[1] * U * R];
  const roadNear = (x, y) => G.roads.some(r => { const a = P(G.pos[r.a]), b = P(G.pos[r.b]); return segD([x, y], a, b) < 7; });
  // Instanced: one draw per colour of hex and one for every cloud puff. As separate meshes,
  // ~400 clouded hexes of four puffs each cost most of the frame.
  const hexGeo = new THREE.CylinderGeometry(HX * .98, HX * .98, 1, 6), byCol = new Map(), puffs = [];
  const seaAt = G.harbours.map(h => P(G.pos[h.id])), m4 = new THREE.Matrix4(), q0 = new THREE.Quaternion();
  const hexes = new Map(), townList = [...G.shown].map(i => [P(G.pos[i]), (G.towns[i].region || [])[0] || ""]);
  const nationId = Object.fromEntries(Object.entries(v.W.nations).map(([id, n]) => [n.name, id])), wash = M.nationColours(v.W);
  const nationAt = (x, z) => { let best = 1e9, n = ""; townList.forEach(([[tx, tz], nm]) => { const d = Math.hypot(tx - x, tz - z); if (d < best) { best = d; n = nm; } }); return n; };
  for (let q = -18; q <= 18; q++) for (let r = -15; r <= 15; r++) {
    const [x, z] = hexCentre(q, r); if (Math.hypot(x, z) > 132) continue;
    const known = pts.some(p => { const [px, pz] = P(p); return Math.hypot(px - x, pz - z) < 16; }) || roadNear(x, z);
    // The world exports no coastline: a harbour town gets a little water off its docks, nothing more.
    const sea = seaAt.some(([sx, sz]) => Math.hypot(x - sx - 17, z - sz) < 13) && !roadNear(x, z);
    const desert = G.wild.some(w => w.kind === "desert" && v.wildFound.has(w.id) && Math.hypot(P(w.pos)[0] - x, P(w.pos)[1] - z) < 9);
    const col = sea ? "hex/water" : desert ? "hex/sand-desert" : known ? "hex/grass"
      : ((q * 7 + r * 3) % 5 === 0 ? "hex/grass-forest" : ((q * 5 + r * 11) % 13 === 0 ? "hex/stone-hill" : "hex/grass"));
    // Kenney's tiles are 1 across the flats, 1.15 point to point: scaled to this board's hexes,
    // and half height, so grass tops out level with the roads.
    if (tileOf(col)) m4.compose(new THREE.Vector3(x, sea ? -.15 : 0, z), q0, new THREE.Vector3(HX * Math.sqrt(3) * .985, 5, HX * Math.sqrt(3) * .985));
    else m4.compose(new THREE.Vector3(x, sea ? -.3 : .5 + (((q * 13 + r * 7) % 3 + 3) % 3) * .08, z), q0, new THREE.Vector3(1, sea ? .6 : 1, 1));
    (byCol.get(col) || byCol.set(col, []).get(col)).push(m4.clone());
    const nat = sea ? "" : nationAt(x, z);
    if (!sea) hexes.set(q + "," + r, { q, r, x, z, known, nation: nat });

    if (!known) for (let i = 0; i < 4; i++) puffs.push(new THREE.Matrix4().compose(new THREE.Vector3(x + (i - 1.5) * 1.7, 2.6 + Math.sin(i + q) * .5, z + (i % 2) * .9),
      q0, new THREE.Vector3().setScalar(2.1 * (1 - i * .15))));
  }
  // Borders: a raised ink strip along every hex edge where two nations meet, drawn only where
  // a known hex touches it (the fog hides the rest); each nation's name over its known hexes.
  const allNations = new Set(townList.map(t => t[1])), strips = [];
  hexes.forEach(h => [[1, 0], [1, -1], [0, -1]].forEach(([dq, dr]) => {
    const o = hexes.get((h.q + dq) + "," + (h.r + dr));
    if (!o || o.nation === h.nation || !(h.known || o.known)) return;
    const mx = (h.x + o.x) / 2, mz = (h.z + o.z) / 2, ang = Math.atan2(o.z - h.z, o.x - h.x);
    strips.push(new THREE.Matrix4().compose(new THREE.Vector3(mx, 1.25, mz), new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), -ang + Math.PI / 2),
      new THREE.Vector3(HX * .98, 1, 1)));
  }));
  if (strips.length) { const im = new THREE.InstancedMesh(new THREE.BoxGeometry(1, .5, .45), mat(0x5a1e14, { flatShading: false, roughness: .6 }), strips.length);
    strips.forEach((m, n) => im.setMatrixAt(n, m)); im.castShadow = true; world.add(im); }
  // Each nation's name painted flat on its own hexes, along the longest row of hexes you know
  // that are all that nation's, and sized to that row: lying on the board, it cannot stray
  // over a border from any angle (a floating label could, and did).
  allNations.forEach(nm => { if (!nm) return;
    const rows = {};
    hexes.forEach(h => { if (h.nation === nm && h.known) (rows[h.r] = rows[h.r] || []).push(h); });
    let best = null;
    Object.values(rows).forEach(list => { list.sort((a, b) => a.q - b.q);
      let run = [list[0]];
      const consider = () => { if (!best || run.length > best.length) best = run.slice(); };
      for (let i = 1; i < list.length; i++) { if (list[i].q === list[i - 1].q + 1) run.push(list[i]); else { consider(); run = [list[i]]; } }
      consider(); });
    if (!best) return;
    const x = best.reduce((s, h) => s + h.x, 0) / best.length, z = best[0].z;
    world.add(flatName(nm.toUpperCase(), M.darken(wash[nationId[nm]] || "#6a4a2a", .38), x, z, best.length * HX * Math.sqrt(3) * .92));
  });
  const fallback = { "hex/water": 0x4a7899, "hex/sand-desert": 0xd9bd85, "hex/grass-forest": 0x6f9a52, "hex/stone-hill": 0x9a9284, "hex/grass": 0x86a85e };
  byCol.forEach((list, col) => { const t = tileOf(col), im = new THREE.InstancedMesh(t ? t.geo : hexGeo, t ? t.mat : mat(fallback[col]), list.length);
    list.forEach((m, n) => im.setMatrixAt(n, m)); im.receiveShadow = true; world.add(im); });
  // Each nation's colour as a translucent plate over the hexes you know. Multiplying the colour
  // into Kenney's green tiles (tried first) turned every nation the same muddy green.
  const plates = [...hexes.values()].filter(h => h.known && h.nation && wash[nationId[h.nation]]);
  if (plates.length) {
    const im = new THREE.InstancedMesh(new THREE.CylinderGeometry(HX * .97, HX * .97, .05, 6), new THREE.MeshBasicMaterial({ transparent: true, opacity: .55, depthWrite: false }), plates.length);
    plates.forEach((h, n) => { im.setMatrixAt(n, new THREE.Matrix4().makeTranslation(h.x, 1.06, h.z)); im.setColorAt(n, new THREE.Color(wash[nationId[h.nation]])); });
    im.renderOrder = 1; world.add(im);
  }
  if (puffs.length) { const im = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1, 0), new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 1, flatShading: true }), puffs.length);
    puffs.forEach((m, n) => im.setMatrixAt(n, m)); im.castShadow = true; world.add(im); clouds.push(Object.assign(im, { userData: { drift: 0 } })); }
  G.roads.forEach(rd => { const a = P(G.pos[rd.a]), b = P(G.pos[rd.b]), L = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const strip = mesh(new THREE.BoxGeometry(L, .12, rd.by === "river" ? 1.6 : 1.1), mat(rd.by === "river" ? 0x4f86b0 : 0xb79b6d), false);
    strip.position.set((a[0] + b[0]) / 2, 1.08, (a[1] + b[1]) / 2); strip.rotation.y = -Math.atan2(b[1] - a[1], b[0] - a[0]); world.add(strip);
    for (let d = 1; d < rd.days; d++) { const t = d / rd.days, peg = mesh(new THREE.CylinderGeometry(.35, .35, .9, 8), mat(0xf3ead6));
      peg.position.set(a[0] + (b[0] - a[0]) * t, 1.4, a[1] + (b[1] - a[1]) * t); world.add(peg); } });   // a peg a day: where journey events pin
  G.shown.forEach(i => { const [x, z] = P(G.pos[i]), o = miniature("town", { painted: v.visited.has(i) }); place(o, i, x, z, KIT["hex/building-village"] ? 1 : 1.5).position.y = KIT["hex/building-village"] ? 0 : 1.05;
    o.userData.name = G.towns[i].name; o.userData.seen = !v.visited.has(i); });
  G.wild.forEach(w => { if (!v.wildFound.has(w.id)) return; const [x, z] = P(w.pos), o = miniature(w.kind === "woods" ? "trees" : w.kind, { painted: v.wildVisited.has(w.id) });
    place(o, w.id, x, z, 1.5).position.y = 1.05; o.userData.name = M.bare(w.name); o.userData.seen = !v.wildVisited.has(w.id); o.userData.down = w.kind === "cave"; });
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
    const cv = document.createElement("canvas"); cv.width = cv.height = 2048; drawWorld(cv, v, half); worldPaper = { key, c: cv }; }
  const c = worldPaper.c;
  paperTex = new THREE.CanvasTexture(c); paperTex.colorSpace = THREE.SRGBColorSpace; paperTex.anisotropy = 8;
  const size = half * 2 * WU;
  const sheet = new THREE.Mesh(new THREE.PlaneGeometry(size, size), new THREE.MeshStandardMaterial({ map: paperTex, roughness: .95 }));
  sheet.rotation.x = -Math.PI / 2; sheet.position.y = .05; sheet.receiveShadow = true; world.add(sheet);
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

// --- The PC, the route, the walk ----------------------------------------------------------
function posOf(id) {
  const v = V;
  if (v.level === "town") { const p = M.anchor(v.L, id); return p && townXZ(p); }
  if (v.level === "world") { const p = v.WL.pos[id]; return p && new THREE.Vector3(p[0] * WU, .1, p[1] * WU); }
  if (v.level === "region") { const p = v.G.pos[id] || (v.G.wild.find(w => w.id === id) || {}).pos; return p && new THREE.Vector3(p[0] * U * 3.4, 1.05, p[1] * U * 3.4); }
  const p = sitePos(v, id); return new THREE.Vector3(p[0], .4, p[1]);
}
function placePc() {
  const id = V.level === "town" ? V.here : V.level === "region" ? V.here : V.here;
  const p = posOf(id); if (!p) return;
  pc.position.copy(p).add(new THREE.Vector3(V.level === "site" ? 1.5 : V.level === "world" ? 1 : 3.6, 0, V.level === "site" ? 1 : V.level === "world" ? 1 : 3.6)); pc.scale.setScalar(V.level === "site" ? 1.2 : V.level === "region" ? 1.2 : V.level === "world" ? .45 : 2);
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
  const d = Math.min(Math.max(size * (V.level === "site" ? 1.25 : V.level === "region" ? 1.1 : V.level === "world" ? .9 : .95), 30), 240);
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
  const fade = V.level === "region" || V.level === "world" ? Math.min(1, Math.max(0, (dist - frameD) / (frameD * .4))) : 0;
  let html = "";
  // Names that cannot find room are not drawn: the place stays, pressable, and its name shows
  // on hover, when pressed, or as you zoom in and room opens up. This is how map labelling
  // keeps a dense place readable (Mapbox and Google Maps drop colliding labels by priority).
  const here = V.level === "town" ? M.baseOf(V.here) : V.here;
  const rank = o => { const id = o.userData.id; return id === here ? 0 : id === V.sel ? 1 : id === hoverId ? 2 : (V.route || []).includes(id) ? 3 : o.userData.seen ? 5 : 4; };
  pick.slice().sort((a, b) => rank(a) - rank(b)).forEach(o => {
    o.getWorldPosition(tmp); tmp.y += V && V.level === "site" ? 1 : V.level === "town" ? 7.5 : V.level === "world" ? 1.6 : 5; tmp.project(camera);  // the world's villages are small: a tag 5 up floated off them
    if (tmp.z > 1) return;
    let x = (tmp.x + 1) / 2 * r.width, y = (1 - tmp.y) / 2 * r.height;
    if (x < -40 || x > r.width + 40 || y < -10 || y > r.height + 40) return;
    const name = o.userData.name || "", w = Math.min(name.length * 7.2, 190) + 16 + (o.userData.badge ? 22 : 0) + (o.userData.down ? 22 : 0);
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
  tags.innerHTML = ar + html;
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

window.TabletopRenderer = { init, draw, walk, levels: ["world"] };
