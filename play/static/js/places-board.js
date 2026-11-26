// The Places tabletop. An ES module, loaded by table/16-tab-map.js with a dynamic `import()`
// when WebGL is there. It lives outside table/, whose files are classic scripts sharing one
// global scope, each loaded by its own <script> tag (tests/test_template_scripts.py); without it, or when the context is lost, the
// tab draws the chart (16-places-chart.js) from the same data instead (owner decision 3,
// 2026-11-18: the chart stays as the fallback).
//
// The owner's choice of the three place-map mocks (2026-11-18): the town as painted
// miniatures on a scroll of the game's chart paper, rolled in the game's leather, on a
// candlelit wooden table; above it the Region (the nation you stand in, on 12-mile hexes),
// the Continent (its nations coloured) and the World (a second scroll). Ported from
// `docs/mock/place-map-v2/tabletop.js` (branch mock/place-map-v2); the Site board is phase 4
// of docs/place-map-v2-build-plan.md. The world's layout, land, colours and names are
// table/16-places-world.js (`PlacesWorld`), shared with the slips.
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
// The maps above the town: the hex board under the pointer (Region, Continent), the World's
// sheet and its painted paper (kept per state of knowledge), the names painted flat.
let board = null, worldSheet = null, worldPaper = null, frameD = 100;
const hover = { continent: null, nation: null, x: 0, y: 0 };
// The shared world model (table/16-places-world.js) is a classic script's `const`, which is in
// the page's global scope but not on `window`; the tab hands it over at init.
const PW = () => api.world;

// --- The hour's light: dawn warm, day clear, dusk amber, night blue (the mock's) -----------
function light(h) {
  const k = [[0, [40, 60, 120, .5]], [5, [50, 60, 120, .45]], [6.5, [255, 170, 110, .22]], [8.5, [255, 230, 190, .05]],
             [16, [255, 230, 190, .05]], [18.5, [255, 140, 70, .24]], [20, [60, 60, 130, .42]], [24, [40, 60, 120, .5]]];
  let i = 0; while (i < k.length - 2 && h >= k[i + 1][0]) i++;
  const [h0, a] = k[i], [h1, b] = k[i + 1], t = (h - h0) / (h1 - h0 || 1);
  const c = a.map((v, j) => v + (b[j] - v) * t);
  return { r: c[0] | 0, g: c[1] | 0, b: c[2] | 0, night: h < 6 || h >= 19.5 };
}

// --- Grain: a little texture on the hex maps (owner, 2026-11-21: "too smooth"; clarified the
// same day: the Continent and the Region, the 12-mile hex map, which is the "nation" level
// here). World, Town and Site stay exactly as they were. -------------------------------------
// One small tiling noise tile, made once in code (the packaged app fetches nothing), sampled
// in WORLD space on the three planes and blended by the face's own normal (triplanar), so a
// box, a cone and a Kenney hex carry the same grain at the same scale with no UVs and no seam
// where two pieces meet. It only multiplies the lit colour by a few percent: every colour
// stays its own. Rejected: per-face vertex-colour jitter (Kenney's tiles share one palette
// texture and would need their geometry rewritten, and it reads as facets, not grain); noise
// computed in the shader (three fetches of a 128px tile are cheaper than three octaves of
// hash noise on a weak GPU, and the tile gets mipmaps, so far hexes average to no change
// instead of shimmering). The cloud puffs over the unknown, the haze over hexes seen but not
// searched, the reach rings and the names are never grained, so what is known and what can be
// pressed read as before.
// The painted, primer and Kenney materials are shared by every level (a Kenney house is a
// town miniature and a hex village alike), so the levels are told apart by one shared uniform,
// GRAIN_ON, set as each board is drawn, not by separate materials: one program per material
// kind, and the other levels skip the fetches behind a uniform branch.
// One tile per 4 table units: a miniature (about 3 across) shows a few blotches; at 7 it sat
// inside one and looked as smooth as before. About ±7% of the colour at one sigma.
const GRAIN_N = 128, GRAIN_SCALE = 1 / 4, GRAIN_AMOUNT = .25;
// Tileable value-noise fbm, 0..255, the same every time. Self-contained (tests run it in node).
function grainData(n) {
  let seed = 11; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const out = new Float32Array(n * n), octaves = [[4, .5], [8, .3], [16, .2], [32, .14], [64, .1]];
  octaves.forEach(([cells, amp]) => {
    const lat = Array.from({ length: cells * cells }, rnd), at = (i, j) => lat[((j % cells + cells) % cells) * cells + ((i % cells + cells) % cells)];
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const fx = x / n * cells, fy = y / n * cells, i = Math.floor(fx), j = Math.floor(fy);
      const sx = (fx - i) * (fx - i) * (3 - 2 * (fx - i)), sy = (fy - j) * (fy - j) * (3 - 2 * (fy - j));
      const a = at(i, j) + (at(i + 1, j) - at(i, j)) * sx, b = at(i, j + 1) + (at(i + 1, j + 1) - at(i, j + 1)) * sx;
      out[y * n + x] += (a + (b - a) * sy - .5) * amp;
    } });
  // Centred on its own mean: sixteen lattice values do not average .5, and an off-centre tile
  // darkens every board a little (it was 120 of 128 before this line).
  const px = new Uint8Array(n * n), mean = out.reduce((s, v) => s + v, 0) / out.length;
  out.forEach((v, k) => { px[k] = Math.max(0, Math.min(255, Math.round(128 + (v - mean) * 255))); });
  return px;
}
let GRAIN = null;
const GRAIN_ON = { value: 0 }, GRAIN_LEVELS = new Set(["nation", "continent"]);
function grainTexture() {
  if (GRAIN) return GRAIN;   // made once for every board; a rebuilt board reuses it
  GRAIN = new THREE.DataTexture(grainData(GRAIN_N), GRAIN_N, GRAIN_N, THREE.RedFormat, THREE.UnsignedByteType);
  GRAIN.wrapS = GRAIN.wrapT = THREE.RepeatWrapping; GRAIN.magFilter = THREE.LinearFilter;
  GRAIN.minFilter = THREE.LinearMipmapLinearFilter; GRAIN.generateMipmaps = true; GRAIN.needsUpdate = true;
  return GRAIN;
}
function grained(m) {
  if (m.userData.grained) return m;
  m.userData.grained = true;
  m.onBeforeCompile = sh => {
    sh.uniforms.grainMap = { value: grainTexture() }; sh.uniforms.grainOn = GRAIN_ON;
    sh.vertexShader = sh.vertexShader.replace("#include <common>", "#include <common>\nvarying vec3 vGrainW;")
      .replace("#include <project_vertex>", `#include <project_vertex>
        vec4 grainP = vec4(transformed, 1.);
        #ifdef USE_INSTANCING
          grainP = instanceMatrix * grainP;
        #endif
        vGrainW = (modelMatrix * grainP).xyz;`);
    sh.fragmentShader = sh.fragmentShader.replace("#include <common>", "#include <common>\nuniform sampler2D grainMap; uniform float grainOn; varying vec3 vGrainW;")
      .replace("#include <color_fragment>", `#include <color_fragment>
        if (grainOn > .5) {
          vec3 grainN = normalize(cross(dFdx(vGrainW), dFdy(vGrainW)));   // the face's own normal
          vec3 grainB = pow(abs(grainN), vec3(4.)); grainB /= grainB.x + grainB.y + grainB.z;
          vec3 grainU = vGrainW * ${GRAIN_SCALE.toFixed(5)};
          float grain = texture2D(grainMap, grainU.zy).r * grainB.x + texture2D(grainMap, grainU.xz).r * grainB.y + texture2D(grainMap, grainU.xy).r * grainB.z;
          diffuseColor.rgb *= 1. + (grain - .5) * ${GRAIN_AMOUNT.toFixed(3)} * 2.;
        }`);
  };
  m.customProgramCacheKey = () => "grain";   // every grained material shares its programs
  return m;
}

// --- Materials ------------------------------------------------------------------------------
const MATS = new Map();
const mat = (c, o = {}) => { const k = c + JSON.stringify(o); if (!MATS.has(k)) MATS.set(k, grained(new THREE.MeshStandardMaterial({ color: c, roughness: .82, flatShading: true, ...o }))); return MATS.get(k); };
const PRIMER = grained(new THREE.MeshStandardMaterial({ color: 0x8d8f93, roughness: 1, flatShading: true }));
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
    return { o: o && (o.userData.pickable || o.userData.open || o.userData.enter) ? o : null, ray };
  };
  canvas.addEventListener("pointerdown", ev => { down = [ev.clientX, ev.clientY]; });
  canvas.addEventListener("pointerup", ev => {
    if (!down || Math.hypot(ev.clientX - down[0], ev.clientY - down[1]) > 5) return;
    const { o, ray } = under(ev);
    if (o && o.userData.enter) { api.hexEnter(); return; }   // the spotted site in the party's hex
    if (o && o.userData.open) { api.open(...o.userData.open); return; }   // an arrow out of this map
    if (o) { api.pick(o.userData.id); return; }
    // Nothing pressed but the land: a lit continent or nation opens.
    if (V && V.level === "world" && hover.continent) api.open("continent", hover.continent);
    else if (V && V.level === "continent" && hover.nation) api.open("nation", hover.nation);
    else if (V && V.level === "nation" && board) {   // a lit hex beside the party: travel there
      const pt = ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -1.1), new THREE.Vector3());
      const hx = pt && board.hexAt(pt.x, pt.z);
      if (hx && (hx.reach || hx.go)) api.hexMove(hx.q, hx.r);
    }
  });
  // The name under the pointer always shows, even when it was held back to keep the map clear;
  // on the World a continent lights under it, on a Continent a nation.
  canvas.addEventListener("pointermove", ev => {
    const { o, ray } = under(ev), r = canvas.getBoundingClientRect();
    hoverId = o ? o.userData.id : null; hover.x = ev.clientX - r.left; hover.y = ev.clientY - r.top;
    let lit = false;
    if (V && V.level === "world" && worldSheet && worldPaper) {
      const h = ray.intersectObject(worldSheet)[0], g = PW().ownerGrid(V.W);
      const k = h ? Math.floor((1 - h.uv.y) * g.N) * g.N + Math.floor(h.uv.x * g.N) : -1, n = k >= 0 ? g.owner[k] : -1;
      const cont = n >= 0 ? (V.W.nations[g.nations[n]] || {}).continent : null;
      setHover("continent", cont && worldPaper.knownConts.has(cont) ? cont : null); lit = !!hover.continent;
    } else if (V && V.level === "continent" && board) {
      const pt = ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -1.1), new THREE.Vector3());
      const hx = pt && board.hexAt(pt.x, pt.z);
      setHover("nation", hx && board.knownNations.has(hx.nation) ? hx.nation : null); lit = !!hover.nation;
    } else if (V && V.level === "nation" && board) {
      const pt = ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -1.1), new THREE.Vector3());
      const hx = pt && board.hexAt(pt.x, pt.z); lit = !!(hx && (hx.reach || hx.go));
    }
    canvas.style.cursor = o || lit ? "pointer" : "grab";
  });
  // Zoom between the maps: out past a map's furthest and the one above opens; in hard and the
  // one below opens, the continent or nation under the pointer first, else the one you are in.
  const UP = { town: "nation", nation: "continent", continent: "world" };
  let lastLevelChange = 0;
  canvas.addEventListener("wheel", ev => {
    if (!V || performance.now() - lastLevelChange < 900) return;
    const d = camera.position.distanceTo(controls.target), go = (...a) => { lastLevelChange = performance.now(); api.open(...a); };
    const up = V.level === "site" ? V.up : UP[V.level];
    if (ev.deltaY > 0 && d >= controls.maxDistance * .97 && up) go(up);
    else if (ev.deltaY < 0 && d <= controls.minDistance * 1.05) {
      if (V.level === "world") go("continent", hover.continent || V.continent);
      else if (V.level === "continent") go("nation", hover.nation || V.nation);
      else if (V.level === "nation" && V.homeNation === V.nation) go("town");
    }
  }, { passive: true });
  canvas.addEventListener("pointerleave", () => { hoverId = null; });
  stage.querySelector('[data-board="reset"]').addEventListener("click", () => frameCamera());
  stage.querySelector('[data-board="tilt"]').addEventListener("click", ev => { tiltOn = !tiltOn; ev.currentTarget.setAttribute("aria-pressed", String(tiltOn)); });
  new ResizeObserver(resize).observe(stage); resize();
  renderer.setAnimationLoop(frame);
  // For the checks and the frame-rate probe: the camera, the pieces on the board, the route
  // drawn, the cost.
  window.__placesBoard = { camera, controls, pieces: () => pick.map(o => ({ id: o.userData.id, name: o.userData.name || "", seen: !!o.userData.seen, at: o.position.toArray() })),
                           route: () => (routeObj ? routeObj.geometry.parameters.path.points.map(p => p.toArray().map(n => +n.toFixed(2))) : null),
                           perf: () => ({ ...renderer.info.memory, calls: lastInfo.calls, triangles: lastInfo.triangles }) };
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
  "hex/building-sheep", "hex/building-mine", "hex/building-village", "hex/unit-house", "hex/unit-mansion",
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
  kitReady = Promise.all(KIT_FILES.map(f => loader.loadAsync(`${api.statics}models/kenney/${f}.glb`).then(g => {
    const o = g.scene;
    o.traverse(m => { if (m.isMesh) { m.castShadow = m.receiveShadow = true; m.geometry.userData.keep = true; m.material.userData.keep = true;
      // Kenney's hex palette is mint; warmed a touch toward the game's parchment and leather.
      if (f.startsWith("hex/")) m.material.color.setRGB(.92, .9, .74);
      grained(m.material); } });
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
    const o = kit(f, painted, kind === "town" ? 10.5 : kind === "keep" || kind === "gate" ? 3.4 : 3); g.add(o);
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
    case "road": add(mesh(new THREE.CylinderGeometry(.1, .1, 1.8, 6), P ? mat(0x5a3a22) : PRIMER), 0, .9, 0);
      add(mesh(new THREE.ConeGeometry(.45, .9, 3), P ? mat(0xe8d6a8) : PRIMER), 0, 2.1, 0); break;
    case "dunes": for (let i = 0; i < 3; i++) add(mesh(new THREE.SphereGeometry(1.1, 8, 4, 0, Math.PI * 2, 0, Math.PI / 2), P ? mat(0xdcbc80) : PRIMER), i * 1.3 - 1.3, 0, -i * .5).scale.y = .45; break;
    case "cave": add(mesh(new THREE.DodecahedronGeometry(1.6, 0), P ? mat(0x8a7d6a) : PRIMER), 0, .6, 0).scale.y = .7;
      add(mesh(new THREE.CircleGeometry(.6, 10), mat(0x0d0905)), 0, .55, 1.25); break;
    case "town": for (let i = 0; i < 5; i++) { const a = i * 1.26, r = i ? 1.3 : 0; add(house(.9, .8, .7 + (i % 2) * .4, 0xe0cfa8, 0xb9645a, P), Math.cos(a) * r, 0, Math.sin(a) * r); }
      add(mesh(new THREE.TorusGeometry(2.2, .14, 4, 24), P ? mat(0x9a9284) : PRIMER), 0, .15, 0).rotation.x = Math.PI / 2; break;
    case "market": [-1, 1].forEach(x => { add(mesh(new THREE.BoxGeometry(1.4, .6, 1), P ? mat(0xd8c8a0) : PRIMER), x, .3, 0);
      add(mesh(new THREE.ConeGeometry(1, .5, 4), P ? mat(x < 0 ? 0xc0504a : 0xe0d0a0) : PRIMER), x, .85, 0).rotation.y = Math.PI / 4; }); break;
    default: add(house(2, 1.5, h, 0xe6d6b4, colour, P));
  }
  // Every miniature stands on a dark base, like the ones on a real table.
  const base = mesh(new THREE.CylinderGeometry(kind === "town" ? 2.8 : 1.35, kind === "town" ? 2.9 : 1.42, .18, 24), mat(0x3a2c20, { flatShading: false, roughness: .5 }));
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
  board = null; worldSheet = null; hover.continent = hover.nation = null;
  candles = candles.filter(c => !c.site);   // a room's torch goes with its room
}
const townXZ = (p, y = 0) => new THREE.Vector3(p[0] * U, y, p[1] * U);
function place(o, id, x, z, size = 1) { o.position.set(x, 0, z); o.userData.id = id; o.userData.size = size; o.scale.setScalar(size); world.add(o); pick.push(o); return o; }

// What `draw` is handed (16-tab-map.js): { level: town | nation | continent | world,
// pf: scene.places_found, sel, hour, came: [ids] walked this turn, fresh: Set of ids found this
// turn, reduced } and, above the town, { W: /api/atlas, KP: scene.known_places, home: the
// settlement the party is in, homeNation, nation, continent, route: [city ids] to the city
// pressed }; on every map { sites: scene.known_places.sites }, and on the Site map { site: the
// site shown, up: the map its way up opens }. A board is rebuilt only when the map, what is known, or where the party stands
// changes; a press only moves the route.
export async function draw(v) {
  const pf = v.pf || { nodes: [], here: "", where: "" }, T = pf.town || { seats: {}, wall: 385, half: 560, gate: "" };
  const level = v.level || "town";
  const drawn = pf.nodes.filter(n => n.setting === "in" && T.seats[n.id] && T.seats[n.id].drawn && T.seats[n.id].at);
  const mine = { ...v, level, pf, town: T, drawn, at: pf.here, here: level === "town" || level === "site" ? pf.here : v.home, sites: v.sites || [] };
  if (level !== "town" && level !== "site") { mine.WL = PW().worldLayout(v.W); mine.K = PW().worldKnown(v.W, v.KP); }
  // Every state is a new view, and a press only moves the route: the site's centre is worked
  // out here, not in siteMap, or the route of a press found every room at NaN.
  if (level === "site") { const all = v.site.rooms.concat(v.site.out ? [v.site.out] : []), cols = all.map(r => r.at[0]), rows = all.map(r => r.at[1]);
    mine.siteMid = [(Math.min(...cols) + Math.max(...cols)) / 2, (Math.min(...rows) + Math.max(...rows)) / 2]; }
  V = mine;
  const subject = level === "nation" ? v.nation : level === "continent" ? v.continent : level === "town" ? pf.where : level === "site" ? v.site.id : "";
  const sig = level + "|" + subject + "|" + pf.where + "|" + pf.here + "|" + pf.nodes.map(n => n.id + (n.visited ? "+" : "")).join(",")
    + "|" + (mine.K ? Object.keys(mine.K.how).sort().join() : "")
    + "|" + mine.sites.map(st => st.id + ":" + (st.out ? st.out.id + ">" : "") + st.rooms.map(r => r.id + (r.visited ? "+" : "")).join()).join(";")
    + "|" + (v.hexgrid ? "hx" : "") + JSON.stringify((v.KP && v.KP.hexes) || {});
  const freshView = level + "|" + subject !== lastTown;
  if (sig !== lastSig) {
    await Promise.all([loadPaper(), loadKit()]);
    if (V !== mine) return;   // a newer state or another map arrived while the models loaded
    lastSig = sig; lastTown = level + "|" + subject;
    clear();
    GRAIN_ON.value = GRAIN_LEVELS.has(level) ? 1 : 0;   // with the board it belongs to, never before
    if (level === "town") town(V); else if (level === "continent") continentMap(V); else if (level === "nation") nationMap(V);
    else if (level === "site") siteMap(V); else worldMap(V);
    pc = pcMini(); world.add(pc); placePc();
  }
  routeLine();
  if (freshView) frameCamera();
  if ((level === "town" || level === "site") && v.came && v.came.length > 1) walk(v.came);
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
  // Out the gate: an arrow past it, pressable, to the land outside (the Region map).
  if (T.gate) {
    const [gx, gy] = T.seats[T.gate].at, d = Math.hypot(gx, gy) || 1, ox = gx / d, oy = gy / d;
    const arrow = new THREE.Group(), cone = mesh(new THREE.ConeGeometry(1.4, 3, 12), mat(0x5a3a22));
    cone.rotation.x = -Math.PI / 2; cone.position.y = 1.2; arrow.add(cone);
    const p = townXZ([gx + ox * 70, gy + oy * 70]); place(arrow, "out-gate", p.x, p.z, 1);
    arrow.rotation.y = Math.atan2(-ox, -oy);   // the cone points -z; turned to point out (ox, oy)
    Object.assign(arrow.userData, { name: "Out the gate", open: ["nation"] });
  }
  v.sites.forEach(st => { const s = T.seats[st.host]; if (s && s.at && s.drawn) { const p = townXZ(s.at); downArrow(st, p.x - 4.2, p.z + 3.2, 1.3); } });
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

// --- The boards above the town ----------------------------------------------------------------
// A hex board from a list of hexes {q, r, x, z, tile, plate, plateOpacity, cloud, nation, known}:
// Kenney tiles instanced per kind, translucent nation plates, cloud puffs where nothing is
// known, border strips where nations meet, each known nation's name painted flat along its
// longest known row, never over a border.
const HX = 6.2;
const hexC = (q, r, h) => [h * Math.sqrt(3) * (q + r / 2), h * 1.5 * r];
const HEX_DIRS = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]];
function tileOf(f) {
  if (!KIT[f]) return null;
  if (KIT[f].tile) return KIT[f].tile;
  let m = null; KIT[f].o.traverse(x => { if (x.isMesh && !m) m = x; });
  KIT[f].o.updateMatrixWorld(true);
  const geo = m.geometry.clone().applyMatrix4(m.matrixWorld); geo.userData.keep = true;
  return (KIT[f].tile = { geo, mat: m.material });
}
function hexBoard(hexes, h, wash, names) {
  const byTile = new Map(), puffs = [], q0 = new THREE.Quaternion();
  hexes.forEach(x => {
    if (x.tile) (byTile.get(x.tile) || byTile.set(x.tile, []).get(x.tile)).push(new THREE.Matrix4().compose(
      new THREE.Vector3(x.x, x.tile === "hex/water" ? -.15 : 0, x.z), q0, new THREE.Vector3(h * Math.sqrt(3) * .985, 5, h * Math.sqrt(3) * .985)));
    if (x.cloud) for (let i = 0; i < 4; i++) puffs.push(new THREE.Matrix4().compose(new THREE.Vector3(x.x + (i - 1.5) * h * .27, 2.6 + Math.sin(i + x.q) * .5, x.z + (i % 2) * h * .15), q0, new THREE.Vector3().setScalar(h * .34 * (1 - i * .15))));
  });
  byTile.forEach((list, f) => { const t = tileOf(f); if (!t) return; const im = new THREE.InstancedMesh(t.geo, t.mat, list.length); list.forEach((m, n) => im.setMatrixAt(n, m)); im.receiveShadow = true; world.add(im); });
  if (puffs.length) { const im = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1, 0), new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 1, flatShading: true }), puffs.length);
    puffs.forEach((m, n) => im.setMatrixAt(n, m)); im.castShadow = true; world.add(im); }
  // Open sea against the coast's own water (rules/hexes.py `sea`): a deep-water wash over the tile.
  const deep = hexes.filter(x => x.deep && !x.cloud);
  if (deep.length) { const im = new THREE.InstancedMesh(new THREE.CylinderGeometry(h * .97, h * .97, .05, 6), new THREE.MeshBasicMaterial({ color: 0x1d3a52, transparent: true, opacity: .28, depthWrite: false }), deep.length);
    deep.forEach((x, n) => im.setMatrixAt(n, new THREE.Matrix4().makeTranslation(x.x, 1.02, x.z))); im.renderOrder = 1; world.add(im); }
  // Ground seen but not searched: a pale haze over the tile, lighter than the clouds of the
  // unknown (ruling 10). The hexes a click can move the party to: a gilt hexagon on each.
  const hazy = hexes.filter(x => x.haze);
  if (hazy.length) { const im = new THREE.InstancedMesh(new THREE.CylinderGeometry(h * .97, h * .97, .05, 6), new THREE.MeshBasicMaterial({ color: 0xf4ecd6, transparent: true, opacity: .3, depthWrite: false }), hazy.length);
    hazy.forEach((x, n) => im.setMatrixAt(n, new THREE.Matrix4().makeTranslation(x.x, 1.14, x.z))); im.renderOrder = 1; world.add(im); }
  const lit2 = hexes.filter(x => x.reach);
  if (lit2.length) { const ring = new THREE.RingGeometry(h * .74, h * .9, 6, 1, Math.PI / 2); ring.rotateX(-Math.PI / 2);
    const im = new THREE.InstancedMesh(ring, new THREE.MeshBasicMaterial({ color: 0xe8c25a, transparent: true, opacity: .9, depthWrite: false, side: THREE.DoubleSide }), lit2.length);
    lit2.forEach((x, n) => im.setMatrixAt(n, new THREE.Matrix4().makeTranslation(x.x, 1.2, x.z))); im.renderOrder = 3; world.add(im); }
  // Nation plates: one instanced mesh per opacity, their indices kept so a hover can light a nation.
  const plateSets = {}, lit = {};
  hexes.filter(x => x.plate && wash[x.nation]).forEach(x => (plateSets[x.plateOpacity] = plateSets[x.plateOpacity] || []).push(x));
  Object.entries(plateSets).forEach(([op, list]) => {
    // Grained too: the plates are most of what the Region and Continent show, and a flat wash
    // over grained tiles still read smooth. The haze, clouds and rings above stay plain.
    const im = new THREE.InstancedMesh(new THREE.CylinderGeometry(h * .97, h * .97, .05, 6), grained(new THREE.MeshBasicMaterial({ transparent: true, opacity: +op, depthWrite: false })), list.length);
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
  Object.keys(names).forEach(n => {
    const rows = {}; hexes.forEach(x => { if (x.nation === n && x.known && x.tile !== "hex/water") (rows[x.r] = rows[x.r] || []).push(x); });
    let best = null;
    Object.values(rows).forEach(list => { list.sort((a, b) => a.q - b.q); let run = [list[0]];
      const keep = () => { if (!best || run.length > best.length) best = run.slice(); };
      for (let i = 1; i < list.length; i++) { if (list[i].q === list[i - 1].q + 1) run.push(list[i]); else { keep(); run = [list[i]]; } } keep(); });
    if (best) world.add(flatName(String(names[n]).toUpperCase(), PW().darken(wash[n] || "#8a6a3a", .38), best.reduce((a, x) => a + x.x, 0) / best.length, best[0].z, best.length * h * Math.sqrt(3) * .92));
  });
  return { at, lit, wash, hexAt: (sx, sz) => { let bestD = 1e18, bx = null; hexes.forEach(x => { const d = (x.x - sx) ** 2 + (x.z - sz) ** 2; if (d < bestD) { bestD = d; bx = x; } }); return bestD < h * h * 1.2 ? bx : null; } };
}
function setHover(kind, id) {
  if (hover[kind] === id) return;
  hover[kind] = id;
  if (kind === "continent") return paintWorldHighlight();
  if (!board || !board.lit) return;
  Object.entries(board.lit).forEach(([n, list]) => list.forEach(([im, i]) => {
    const c = new THREE.Color(board.wash[n]); if (n === id) c.lerp(new THREE.Color(1, .95, .75), .45); im.setColorAt(i, c); im.instanceColor.needsUpdate = true; }));
}
// A peg a day at 24 miles (speed 30, Pathfinder's overland pace).
function dayPegs(a, b, miles, y) {
  const n = miles ? Math.ceil(miles / 24) - 1 : 0;
  for (let d = 1; d <= n; d++) { const t = d / (n + 1), peg = mesh(new THREE.CylinderGeometry(.32, .32, .9, 8), mat(0xf3ead6)); peg.position.set(a[0] + (b[0] - a[0]) * t, y, a[1] + (b[1] - a[1]) * t); world.add(peg); }
}
function roadStrip(a, b, kind, y = 1.08, w = 1.1) {
  const L = Math.hypot(b[0] - a[0], b[1] - a[1]); if (!L) return;
  const strip = mesh(new THREE.BoxGeometry(L, .12, kind === "river" ? w * 1.4 : w), mat(kind === "river" ? 0x4f86b0 : kind === "track" ? 0x9a8058 : 0xb79b6d), false);
  strip.position.set((a[0] + b[0]) / 2, y, (a[1] + b[1]) / 2); strip.rotation.y = -Math.atan2(b[1] - a[1], b[0] - a[0]); world.add(strip);
}
// A name painted flat on the board: capitals in the nation's dark ink with a pale halo, as wide
// as `maxW` allows.
function flatName(text, ink, x, z, maxW) {
  const fs = 72, c = document.createElement("canvas"), g = c.getContext("2d");
  const font = `600 ${fs}px Cinzel, Palatino Linotype, Georgia, serif`;
  g.font = font; try { g.letterSpacing = "14px"; } catch (e) { /* an older canvas has no spacing */ }
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
const cityOf = (W, id) => W.cities.find(c => c.id === id);

// The continent: its nations coloured, the cities you know as villages, the roads you know with
// a peg a day. From the world's own layout, so a town's bearing here is its bearing on the World.
function continentMap(v) {
  const { W, WL, K } = v, P = PW(), wash = P.nationColours(W), CS = .3, h = 7;
  const cities = W.cities.filter(c => c.continent === v.continent), ctr = WL.centre[v.continent] || [0, 0];
  const S = ([x, y]) => [(x - ctr[0]) * CS, (y - ctr[1]) * CS], inC = new Set(cities.map(c => c.id));
  const knownIds = Object.keys(K.how).filter(id => inC.has(id)), knownPts = knownIds.map(id => WL.pos[id]);
  const roads = K.roads.filter(r => r.by !== "sea" && inC.has(r.a) && inC.has(r.b));
  const knownNations = new Set(knownIds.map(id => cityOf(W, id).nation));
  const hexes = [];
  for (let q = -22; q <= 22; q++) for (let r = -18; r <= 18; r++) {
    const [sx, sz] = hexC(q, r, h), wx = sx / CS + ctr[0], wy = sz / CS + ctr[1];
    if (Math.hypot(wx - ctr[0], wy - ctr[1]) > 420) continue;
    const land = P.landAt(W, WL, wx, wy);
    const nearLand = land || cities.some(c => Math.hypot(WL.pos[c.id][0] - wx, WL.pos[c.id][1] - wy) < 150);
    if (!nearLand) continue;
    const city = P.nearestCity(cities, WL, wx, wy), nation = land && city ? city.nation : null;
    const known = land && (knownPts.some(([x, y]) => Math.hypot(x - wx, y - wy) < 75) || roads.some(rd => P.segD([wx, wy], WL.pos[rd.a], WL.pos[rd.b]) < 24));
    const tile = !land ? "hex/water" : known ? ((q * 7 + r * 3) % 9 === 0 ? "hex/grass-forest" : "hex/grass")
      : ((q * 7 + r * 3) % 5 === 0 ? "hex/grass-forest" : ((q * 5 + r * 11) % 13 === 0 ? "hex/stone-hill" : "hex/grass"));
    hexes.push({ q, r, x: sx, z: sz, tile, nation, known, plate: land && known, plateOpacity: .55, cloud: land && !known });
  }
  const names = Object.fromEntries([...knownNations].map(n => [n, W.nations[n].name]));
  board = { ...hexBoard(hexes, h, wash, names), knownNations, pos: {} };
  roads.forEach(rd => { const a = S(WL.pos[rd.a]), c = S(WL.pos[rd.b]); roadStrip(a, c, rd.by === "river" ? "river" : "road"); dayPegs(a, c, rd.miles, 1.4); });
  knownIds.forEach(id => {
    const [x, z] = S(WL.pos[id]), how = K.how[id], o = miniature("town", { painted: how.by === "been" });
    place(o, id, x, z, .8);
    Object.assign(o.userData, { pickable: true, name: cityOf(W, id).name, seen: how.by !== "been" });
    board.pos[id] = new THREE.Vector3(x, 1.05, z);
  });
}

// The Region: the nation you stand in, at Pathfinder's 12-mile overland hex (Ultimate Campaign).
// Its towns you know; round the town you are in, its wild ground on hexes of its own kind;
// roads leaving the nation end in an arrow naming where they go, pressable to the Continent.
const TILE_OF = { forest: "hex/grass-forest", jungle: "hex/grass-forest", desert: "hex/sand-desert", mountain: "hex/stone-hill", hills: "hex/stone-hill",
                  underground: "hex/stone-hill", tundra: "hex/grass", farmland: "hex/grass", grassland: "hex/grass", swamp: "hex/grass-forest", coast: "hex/grass" };
const MINI_OF = { desert: "dunes", mountain: "cave", hills: "cave", underground: "cave" };
// A hex's site (rules/hexes.py `SITES_BY_GROUND`) as a miniature, and its name on hover.
const SITE_MINI = { tower: "steeple", ruins: "keep", mine: "cave", cave: "cave" };
const SITE_NAME = { tower: "the tower", ruins: "the ruins", mine: "the old mine", cave: "the cave" };
const spotOf = id => (String(id).split("~")[1] || "");
const groundOf = id => spotOf(id).split(":")[0];
function nationMap(v) {
  const { W, WL, K } = v, P = PW(), wash = P.nationColours(W), cont = W.nations[v.nation].continent;
  const contCities = W.cities.filter(c => c.continent === cont), mineC = W.cities.filter(c => c.nation === v.nation);
  const inMine = id => mineC.some(c => c.id === id);
  // Miles to a world unit, from the roads the world measured (the median), so a hex is 12 miles.
  const ratios = W.routes.filter(r => r.miles && r.by !== "sea" && WL.pos[r.a] && WL.pos[r.b])
    .map(r => r.miles / (Math.hypot(WL.pos[r.a][0] - WL.pos[r.b][0], WL.pos[r.a][1] - WL.pos[r.b][1]) || 1)).sort((a, b) => a - b);
  // The engine's hex size when its grid is here (rules/hexes.py, the same median): one grid.
  const milesPerUnit = ratios[ratios.length >> 1] || 1, rW = v.hexgrid ? v.hexgrid.size : 6 / milesPerUnit, h = HX, NS = h / rW;
  const ctr = [mineC.reduce((a, c) => a + WL.pos[c.id][0], 0) / mineC.length, mineC.reduce((a, c) => a + WL.pos[c.id][1], 0) / mineC.length];
  const ofN = (wx, wy) => { if (!P.landAt(W, WL, wx, wy)) return null; const c = P.nearestCity(contCities, WL, wx, wy); return c ? c.nation : null; };
  const homeHere = v.homeNation === v.nation;
  const knownTowns = Object.keys(K.how).filter(inMine);
  // The hexes: the nation's land, and a ring of its neighbours' land and sea round it.
  const key = (q, r) => q + "," + r, grid = new Map();
  if (v.hexgrid) {
    // The engine's grid (`/api/hexes`, rules/hexes.py): one world-wide axial grid, so a hex
    // here is the hex the engine moves the party across, and its ground the ground the
    // engine forages and charges hours on. Drawn round the hex at the nation's middle.
    const rf = ctr[1] / (1.5 * rW), qf = ctr[0] / (Math.sqrt(3) * rW) - rf / 2;
    let q0 = Math.round(qf), r0 = Math.round(rf); const s0 = Math.round(-qf - rf);
    const dq = Math.abs(q0 - qf), dr = Math.abs(r0 - rf), ds = Math.abs(s0 + qf + rf);
    if (dq > dr && dq > ds) q0 = -r0 - s0; else if (dr > ds) r0 = -q0 - s0;
    v.hexgrid.hexes.forEach(hx => {
      const [wx, wy] = hexC(hx.q, hx.r, rW), [sx, sz] = hexC(hx.q - q0, hx.r - r0, h);
      grid.set(key(hx.q, hx.r), { q: hx.q, r: hx.r, x: sx, z: sz, wx, wy, nation: hx.land ? hx.nation : null, ground: hx.ground, town: hx.town, sea: hx.sea || "" });
    });
  } else {
    const span = Math.min(40, Math.ceil((Math.max(...mineC.map(c => Math.hypot(WL.pos[c.id][0] - ctr[0], WL.pos[c.id][1] - ctr[1]))) + 160) * NS / (h * 1.5)));
    for (let q = -span * 2; q <= span * 2; q++) for (let r = -span; r <= span; r++) {
      const [sx, sz] = hexC(q, r, h), wx = sx / NS + ctr[0], wy = sz / NS + ctr[1];
      grid.set(key(q, r), { q, r, x: sx, z: sz, wx, wy, nation: ofN(wx, wy) });
    }
  }
  const mine = [...grid.values()].filter(x => x.nation === v.nation);
  const ring = new Set(); mine.forEach(x => HEX_DIRS.forEach(([dq, dr]) => { const o = grid.get(key(x.q + dq, x.r + dr)); if (o && o.nation !== v.nation) ring.add(o); }));
  const hexOf = (wx, wy) => { let best = 1e18, b = null; mine.forEach(x => { const d = (x.wx - wx) ** 2 + (x.wy - wy) ** 2; if (d < best) { best = d; b = x; } }); return b; };
  const pos = {}, known = new Set(), around = (x, n = 1) => { known.add(key(x.q, x.r)); if (n) HEX_DIRS.forEach(([dq, dr]) => known.add(key(x.q + dq, x.r + dr))); };
  knownTowns.forEach(id => { const t = v.hexgrid && v.hexgrid.towns[id], hx = (t && grid.get(key(t[0], t[1]))) || hexOf(...WL.pos[id]); if (hx) { pos[id] = hx; around(hx); } });
  const roadsOut = [];
  K.roads.filter(rd => rd.by !== "sea" && (inMine(rd.a) || inMine(rd.b))).forEach(rd => {
    const from = inMine(rd.a) ? rd.a : rd.b, to = from === rd.a ? rd.b : rd.a;
    roadsOut.push({ from, to, by: rd.by, miles: rd.miles, inside: inMine(to), bearing: Math.atan2(WL.pos[to][1] - WL.pos[from][1], WL.pos[to][0] - WL.pos[from][0]) });
  });
  // Terrain as the engine reads it (geography.land_around, in the atlas): a hex along a road
  // takes the ground that road crosses there, the hexes round a town its near ground, a few
  // further out its ground beyond; a reach no road crosses gets a patch at its miles, in the
  // direction furthest from every road out.
  const ground = new Map(), all = v.hexgrid ? [] : [...mine, ...ring].filter(x => x.nation);
  if (v.hexgrid) grid.forEach(x => { if (x.nation && x.ground && x.ground !== "water") ground.set(key(x.q, x.r), x.ground); });
  const townOf = x => P.nearestCity(contCities, WL, x.wx, x.wy);
  const routesOf = c => W.routes.filter(r => r.by !== "sea" && (r.a === c.id || r.b === c.id) && (r.crosses || []).length && WL.pos[r.a] && WL.pos[r.b]);
  all.forEach(x => {
    const c = townOf(x); if (!c) return;
    const [cx, cy] = WL.pos[c.id], dHex = Math.hypot(x.wx - cx, x.wy - cy) / (rW * Math.sqrt(3));
    let g = null;
    routesOf(c).forEach(r => { if (g) return; const o = r.a === c.id ? r.b : r.a, [ox, oy] = WL.pos[o];
      if (P.segD([x.wx, x.wy], [cx, cy], [ox, oy]) > rW * .9) return;
      const L = Math.hypot(ox - cx, oy - cy) || 1, t = ((x.wx - cx) * (ox - cx) + (x.wy - cy) * (oy - cy)) / (L * L);
      if (t < 0 || t > 1) return;
      const cr = r.a === c.id ? r.crosses : [...r.crosses].reverse();   // crosses run from this town outward
      g = cr[Math.min(cr.length - 1, Math.floor(t * cr.length))]; });
    if (!g && dHex > .5 && dHex < 1.6) { const near = (c.near || []).filter(n => n !== "desert" && n !== "coast"); g = near.length ? near[(x.q * 7 + x.r * 3 & 1023) % near.length] : null; }
    if (!g && dHex >= 1.6) { const far = c.beyond || []; g = (x.q * 7 + x.r * 3 & 1023) % 4 === 0 && far.length ? far[(x.q + x.r & 1023) % far.length] : null; }
    if (g) ground.set(key(x.q, x.r), g);
  });
  if (!v.hexgrid) mineC.forEach(c => (c.reaches || []).filter(rc => !routesOf(c).some(r => (r.crosses || [])[0] === rc.ground)).forEach(rc => {
    const hx0 = hexOf(...WL.pos[c.id]); if (!hx0) return;
    const taken = routesOf(c).map(r => { const o = r.a === c.id ? r.b : r.a; return Math.atan2(WL.pos[o][1] - WL.pos[c.id][1], WL.pos[o][0] - WL.pos[c.id][0]); });
    const n = Math.max(1, Math.round((rc.miles + 6) / 12));   // from the town's middle: its own half-hex, then the reach's miles
    const dir = HEX_DIRS.map(([dq, dr]) => { const [dx, dz] = hexC(dq, dr, 1); return [dq, dr, Math.atan2(dz, dx)]; })
      .map(d => [d, taken.length ? Math.min(...taken.map(b2 => Math.abs(Math.atan2(Math.sin(d[2] - b2), Math.cos(d[2] - b2))))) : Math.PI]).sort((p1, p2) => p2[1] - p1[1])[0][0];
    [[0, 0], [dir[0], dir[1]]].forEach(([eq, er]) => { const hx = grid.get(key(hx0.q + dir[0] * n + eq, hx0.r + dir[1] * n + er)); if (hx && hx.nation === v.nation) ground.set(key(hx.q, hx.r), rc.ground); });
  }));
  // Round the town you are in: its wild places found, each on the nearest hex of its own ground
  // (the owner, 2026-11-18: "let the woods and desert go to the desert and forest hexes"); its
  // ground is the engine's, read off the place's id. Near wild ground gets its own hex beside
  // the town (decision 4); the label keeps the real distance.
  const wild = [];
  if (homeHere && pos[v.home]) {
    const home = pos[v.home], homeC = cityOf(W, v.home) || {};
    // A hex of open ground (rules/hexes.py) stands on its own hex, not as a wild place of the
    // town's: left in, each one walked was drawn as woods with a track back to the gate.
    const outside = v.pf.nodes.filter(n => n.setting === "outside" && String(n.id).split("~")[0] === v.home
                                         && !String(n.id).includes(":@hex-"));
    const isPost = n => /^[^:]*:@the-(outskirts|crossroads)$/.test(spotOf(n.id));
    const isRoad = n => /:@the-road-to-/.test(spotOf(n.id));
    const isUnder = n => spotOf(n.id).split(":")[1] && spotOf(n.id).split(":")[1].includes("/");
    const used = new Set([key(home.q, home.r)]);
    outside.filter(n => !isPost(n) && !isRoad(n) && !isUnder(n)).sort((a, b) => (a.id < b.id ? -1 : 1)).forEach(n => {
      const rc = (homeC.reaches || []).find(x => x.name === n.name), want = (rc && rc.ground) || groundOf(n.id) || "forest";
      const byDist = list => list.sort((p1, p2) => Math.hypot(p1.x - home.x, p1.z - home.z) - Math.hypot(p2.x - home.x, p2.z - home.z));
      let hx = byDist(mine.filter(x => ground.get(key(x.q, x.r)) === want && !used.has(key(x.q, x.r))))[0];
      // No hex of its own ground: the nearest free hex of the nation takes that ground. Not only
      // the six beside the town: a port like Ledgernook has few of its own nation's hexes there,
      // and its shore, heights and desert found none (measured 2026-11-18).
      if (!hx) { hx = byDist(mine.filter(x => !used.has(key(x.q, x.r))))[0]; if (hx) ground.set(key(hx.q, hx.r), want); }
      if (!hx) return;
      used.add(key(hx.q, hx.r)); pos[n.id] = hx; around(hx);
      const mins = n.walk ? n.walk.minutes : 0;
      wild.push({ n, hx, kind: MINI_OF[want] || "trees",
        road: [rc && rc.miles ? `${rc.miles} miles` : "", mins ? (mins < 90 ? `${mins} minutes on foot` : `about ${Math.round(mins / 60)} hours on foot`) : ""].filter(Boolean).join(", ") });
    });
    // Just outside the gate: the outskirts and the crossroads, small pieces in the town's own hex.
    outside.filter(isPost).sort((a, b) => (a.id < b.id ? -1 : 1)).forEach((n, k) => {
      pos[n.id] = { ...home, x: home.x + (k ? 2 : -1.8), z: home.z - 2.8 }; wild.push({ n, hx: pos[n.id], kind: "post", small: true }); });
    // A cave or anything beneath a wild place hangs off its host's piece.
    outside.filter(isUnder).forEach(n => { const first = spotOf(n.id).split(":")[1].split("/")[0];
      const host = outside.find(o => spotOf(o.id).split(":")[1] === first); if (host && pos[host.id]) pos[n.id] = pos[host.id]; });
  }
  roadsOut.forEach(rd => { if (!pos[rd.from]) return;
    for (let t = 0; t < 30; t++) { const hx = hexOf(WL.pos[rd.from][0] + Math.cos(rd.bearing) * t * rW, WL.pos[rd.from][1] + Math.sin(rd.bearing) * t * rW); if (hx) known.add(key(hx.q, hx.r)); } });
  // What the party did on the hexes (scene.known_places.hexes, rules/hexes.py). Three looks
  // (the owner, 2026-11-19: "there should be a visible difference between hexes that have
  // been perception checked"): cloud where nothing is known, a pale haze over ground seen but
  // never searched (a hex ridden through looks like this), clear where a look covered it.
  const HS = (v.KP && v.KP.hexes) || {}, touched = HS.touched || {};
  const reach = new Set(v.hexgrid ? (HS.reach || []).map(([q, r]) => key(q, r)) : []);
  const hexes = [], partyK = HS.party ? key(HS.party[0], HS.party[1]) : "";
  // The nation's waters out from its coast (rules/hexes.py `Grid.region`, feat/sea-hexes): the
  // engine's grid sends them; under fog like the land until sailed, swum or seen from the shore.
  const sea = v.hexgrid ? [...grid.values()].filter(x => !x.nation && !ring.has(x)) : [];
  [...mine, ...ring, ...sea].forEach(x => {
    const k = key(x.q, x.r), isMine = x.nation === v.nation, land = !!x.nation, t = touched[k] || {};
    const kn = known.has(k) || !!t.entered || !!t.searched || reach.has(k);
    const tile = !land ? "hex/water" : TILE_OF[ground.get(k)] || "hex/grass";
    hexes.push({ q: x.q, r: x.r, x: x.x, z: x.z, tile, nation: x.nation, known: kn || !isMine, plate: land && (isMine ? kn : true), plateOpacity: isMine ? .55 : .25,
                 cloud: (isMine && land && !kn) || (!!v.hexgrid && !land && !kn), haze: !!v.hexgrid && isMine && land && kn && !t.searched,
                 deep: !land && x.sea === "open", reach: reach.has(k), ground: ground.get(k) || "",
                 // Click-to-travel (owner 2026-11-21): any seen land hex past a move's reach is a
                 // destination; the engine walks the way there a hex at a time (`hex_move`).
                 go: !!v.hexgrid && !!partyK && land && kn && !reach.has(k) && k !== partyK });
  });
  board = { ...hexBoard(hexes, h, wash, { [v.nation]: W.nations[v.nation].name }), knownNations: new Set(), pos: {} };
  const P3 = hx => new THREE.Vector3(hx.x, 1.05, hx.z);
  // The party out on a hex: its figure stands there, wherever it is in the hex (a site too).
  const partyHex = HS.party && grid.get(key(HS.party[0], HS.party[1]));
  // Only on a hex's own place (`{town}~{ground}:@hex-q-r`, and its site below it): standing in
  // the woods off a town, the figure stays on the woods' piece as it always did.
  if (partyHex && v.pf && String(v.pf.here || "").includes(":@hex-")) board.pos[v.pf.here] = P3(partyHex);
  // Aboard a ship the PC holds, out on a hex: the figure stands on her hex (the deck has no hex in its id).
  if (partyHex && v.pf && HS.afloat === "ship" && v.pf.here) board.pos[v.pf.here] = P3(partyHex);
  // A site's rooms hang off its hex's own place (`posOf` walks a room up to its host), so
  // every hex place named is stood on its hex, read off the id (`hexes.slug`: m is minus).
  [...(v.sites || []).map(st => st.host), ...((v.pf && v.pf.nodes) || []).map(n => n.id)].forEach(id => {
    const m = /:@hex-(m?\d+)-(m?\d+)$/.exec(String(id || "")); if (!m) return;
    const n = t => (t[0] === "m" ? -Number(t.slice(1)) : Number(t)), hx = grid.get(key(n(m[1]), n(m[2])));
    if (hx && !board.pos[id]) board.pos[id] = P3(hx);
  });
  // Sites spotted from a look (ruling 3: "if you find something a model is placed on the hex"):
  // grey primer until the party has been inside, painted after; the one in the party's own
  // hex is pressed to go in.
  Object.entries(HS.spotted || {}).forEach(([k, kind]) => {
    const hx = grid.get(k); if (!hx) return;
    const done = !!(touched[k] && touched[k].explored), ours = !!partyHex && key(partyHex.q, partyHex.r) === k;
    const o = miniature(SITE_MINI[kind] || "keep", { painted: done });
    place(o, "hexsite:" + k, hx.x + 1.6, hx.z - 1.4, 1.5).position.y = 1.05;
    Object.assign(o.userData, { pickable: false, enter: ours && !HS.in_site, name: SITE_NAME[kind] || "a site",
                                seen: !done, road: ours && !HS.in_site ? "press to go in" : "" });
  });
  knownTowns.forEach(id => { const hx = pos[id]; if (!hx) return; const how = K.how[id], o = miniature("town", { painted: how.by === "been" });
    place(o, id, hx.x, hx.z, .8).position.y = 0;
    Object.assign(o.userData, { pickable: true, name: cityOf(W, id).name, seen: how.by !== "been" }); board.pos[id] = P3(hx); });
  wild.forEach(w => { const o = miniature(w.kind, { painted: w.n.visited });
    place(o, w.n.id, w.hx.x, w.hx.z, w.small ? 1.1 : 1.8).position.y = 1.05;
    Object.assign(o.userData, { pickable: !w.n.current, name: bare(w.n.name), seen: !w.n.visited, road: w.small ? "" : w.road });
    board.pos[w.n.id] = P3(w.hx);
    if (!w.small && pos[v.home]) roadStrip([pos[v.home].x, pos[v.home].z], [w.hx.x, w.hx.z], "track", 1.09, .7); });
  // Across country between two wild places, where the chart knows the way (phase 5: every
  // reach joins every other, rules/outskirts.py): a track hex to hex, not back through town.
  const big = new Map(wild.filter(w => !w.small).map(w => [w.n.id, w.hx]));
  const drawnWays = new Set();
  (v.pf.edges || []).forEach(ed => { const a = big.get(ed.from), b = big.get(ed.to), k = [ed.from, ed.to].sort().join("|");
    if (a && b && a !== b && !drawnWays.has(k)) { drawnWays.add(k); roadStrip([a.x, a.z], [b.x, b.z], "track", 1.09, .7); } });
  Object.keys(pos).forEach(id => { if (!board.pos[id]) board.pos[id] = P3(pos[id]); });
  v.sites.forEach(st => { const at = wild.some(w => w.n.id === st.host) && board.pos[st.host]; if (at) downArrow(st, at.x - 3, at.z + 2.4, 1).position.y = 1.05; });
  // Roads: between the nation's towns, a strip; leaving it, a strip to the border and an arrow.
  roadsOut.forEach(rd => { const a = pos[rd.from]; if (!a) return;
    if (rd.inside && pos[rd.to]) { roadStrip([a.x, a.z], [pos[rd.to].x, pos[rd.to].z], rd.by === "river" ? "river" : "road"); return; }
    let last = a;
    for (let t = 1; t < 40; t++) {
      const wx = WL.pos[rd.from][0] + Math.cos(rd.bearing) * t * rW * .5, wy = WL.pos[rd.from][1] + Math.sin(rd.bearing) * t * rW * .5;
      let best = 1e18, bq = null; mine.forEach(x => { const d = (x.wx - wx) ** 2 + (x.wy - wy) ** 2; if (d < best) { best = d; bq = x; } });
      if (!bq || best >= rW * rW) break; last = bq; }
    const end = [last.x + Math.cos(rd.bearing) * h * 1.2, last.z + Math.sin(rd.bearing) * h * 1.2];
    roadStrip([a.x, a.z], end, rd.by === "river" ? "river" : "road");
    dayPegs([a.x, a.z], end, Math.min(rd.miles || 0, 24 * Math.round(Math.hypot(end[0] - a.x, end[1] - a.z) / (h * 1.73) / 2)), 1.4);
    const arrow = new THREE.Group(), cone = mesh(new THREE.ConeGeometry(1.2, 2.6, 12), mat(0x5a3a22)); cone.rotation.z = -Math.PI / 2; cone.position.y = 1.6; arrow.add(cone);
    place(arrow, "out:" + rd.to, end[0], end[1], 1); arrow.rotation.y = -rd.bearing;
    const to = cityOf(W, rd.to) || {};
    Object.assign(arrow.userData, { name: `to ${to.name || "?"}`, road: `${(W.nations[to.nation] || {}).name || ""}${rd.miles ? `, ${rd.miles} miles` : ""}`, open: ["continent", cont] });
  });
}

// --- The Site: a dungeon's rooms as a dollhouse ------------------------------------------------
// Each room entered is an open box, back and side walls only so the camera sees in; a room only
// seen is a chalk outline on the table; a room not yet seen is not sent at all (play/atlas.py).
// Seats are the server's, dealt over the whole site, so finding a room moves nothing. Darkest
// Dungeon's corridor map: depth below the way in runs left to right.
const SITE_COL = 15, SITE_ROW = 13;
function siteXZ(v, at) { return [(at[0] - v.siteMid[0]) * SITE_COL, (at[1] - v.siteMid[1]) * SITE_ROW]; }
function siteMap(v) {
  const st = v.site, rooms = st.rooms, by = Object.fromEntries(rooms.map(r => [r.id, r]));
  const grid = new THREE.GridHelper(160, 40, 0x6a5a40, 0x4a3a28); grid.position.y = .06;
  grid.material.opacity = .35; grid.material.transparent = true; world.add(grid);
  // Passages: room to the room beneath it, and the side ways; drawn when either end was entered.
  const pairs = [];
  rooms.forEach(r => { if (by[r.parent]) pairs.push([r.parent, r.id]); r.exits.forEach(x => { if (by[x] && x > r.id) pairs.push([r.id, x]); }); });
  pairs.forEach(([a, b]) => { if (!by[a].visited && !by[b].visited) return;
    const p = siteXZ(v, by[a].at), q = siteXZ(v, by[b].at), mid = (p[0] + q[0]) / 2;
    [[p, [mid, p[1]]], [[mid, p[1]], [mid, q[1]]], [[mid, q[1]], q]].forEach(([s0, e]) => { const L = Math.hypot(e[0] - s0[0], e[1] - s0[1]); if (!L) return;
      const f = mesh(new THREE.BoxGeometry(L + 2.2, .3, 2.2), mat(0x4a3f32)); f.position.set((s0[0] + e[0]) / 2, .15, (s0[1] + e[1]) / 2);
      f.rotation.y = -Math.atan2(e[1] - s0[1], e[0] - s0[0]); world.add(f); }); });
  const W = 10, D = 8, H = 4;
  rooms.forEach(r => {
    const [x, z] = siteXZ(v, r.at), g = new THREE.Group(), here = r.id === v.here;
    if (r.visited) {
      g.add(mesh(new THREE.BoxGeometry(W, .4, D), mat(here ? 0xa08c66 : 0x857458)));
      const back = mesh(new THREE.BoxGeometry(W, H, .5), mat(0x6a5a46)); back.position.set(0, H / 2, -D / 2); g.add(back);
      const side = mesh(new THREE.BoxGeometry(.5, H, D), mat(0x76644d)); side.position.set(-W / 2, H / 2, 0); g.add(side);
      if (r.role === "climax") { const t = mesh(new THREE.BoxGeometry(2.4, 2, 1.6), mat(0x6a3030)); t.position.set(2, 1, -2); g.add(t); }
      if (here) { const torch = new THREE.PointLight(0xffa850, 120, 26, 1.8); torch.position.set(-4, 3.2, -2.5); g.add(torch);
        const fl = new THREE.Mesh(new THREE.ConeGeometry(.25, .7, 6), new THREE.MeshBasicMaterial({ color: 0xffc060 })); fl.position.copy(torch.position); g.add(fl);
        candles.push({ light: torch, flame: fl, base: 120, site: true }); }
    } else {
      const edge = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(W, .2, D)), new THREE.LineDashedMaterial({ color: 0xe8dcc0, dashSize: .6, gapSize: .4 }));
      edge.computeLineDistances(); g.add(edge);
      g.add(new THREE.Mesh(new THREE.BoxGeometry(W, .1, D), new THREE.MeshBasicMaterial({ transparent: true, opacity: 0 })));   // something to press
    }
    // A trap found and still armed (playtest 2026-11-23 O5): a dark pit ringed in the warning
    // red of the slip, on the floor of a room built or chalked, and named on hover.
    if (r.trap) { const ring = mesh(new THREE.CylinderGeometry(1.7, 1.7, .14, 20), mat(0x8a3a2c), false); ring.position.set(2.2, .3, 1.4); g.add(ring);
      const pit = mesh(new THREE.CylinderGeometry(1.3, 1.3, .16, 20), mat(0x120d09), false); pit.position.set(2.2, .32, 1.4); g.add(pit); }
    place(g, r.id, x, z);
    Object.assign(g.userData, { pickable: !here, name: bare(r.name) + (r.trap ? " (trap found)" : ""), seen: !r.visited });
  });
  // The way out (owner ask 2026-11-26 A3): the ground the site lies under (its hex, or the town
  // place over the sewers) as a slab of open ground joined to the way in, no walls: pressed, it
  // is a place like any other, and its slip's Walk there sends the engine the real way up.
  const root = by[st.id], out = st.out;
  if (root && out) { const p = siteXZ(v, out.at), q = siteXZ(v, root.at), L = q[0] - p[0];
    const f = mesh(new THREE.BoxGeometry(L, .3, 2.2), mat(0x4a3f32)); f.position.set((p[0] + q[0]) / 2, .15, p[1]); world.add(f);
    const g = new THREE.Group(); g.add(mesh(new THREE.BoxGeometry(W, .4, D), mat(0x5f6b3e)));
    const stair = mesh(new THREE.BoxGeometry(2.2, .9, 2.2), mat(0x6a5a46)); stair.position.set(W / 2 - 1.4, .45, 0); g.add(stair);
    place(g, out.id, p[0], p[1]);
    Object.assign(g.userData, { pickable: true, name: "Way out: " + bare(out.name), seen: false }); }
  // The way up, before the way in: an arrow pointing up, to the map the site lies under.
  if (root && v.up) { const [x, z] = siteXZ(v, out ? out.at : root.at), a = new THREE.Group(), cone = mesh(new THREE.ConeGeometry(1.4, 3, 12), mat(0x5a3a22));
    cone.position.y = 1.6; a.add(cone); place(a, "up:" + st.id, x - SITE_COL * .75, z, 1);
    Object.assign(a.userData, { name: "Back up", open: [v.up] }); }
}
// A way down beside the piece a site lies under, on the town and the Region: pressed, the Site.
function downArrow(st, x, z, size) {
  const a = new THREE.Group(), cone = mesh(new THREE.ConeGeometry(1, 2.2, 12), mat(0x2a2019));
  cone.rotation.x = Math.PI; cone.position.y = 1.4; a.add(cone);
  const hole = mesh(new THREE.CylinderGeometry(1.3, 1.3, .12, 16), mat(0x120d09), false); hole.position.y = .08; a.add(hole);
  place(a, "down:" + st.id, x, z, size);
  Object.assign(a.userData, { name: "Down: " + bare(st.name), open: ["site", st.id] });
  return a;
}

// The World: a second scroll, every city the party knows of and how. The land is the paper,
// not knowledge, so it is painted whole; fog covers it but round the cities known. A city
// stood in is a painted village; one known from a road sign, talk or a map is primer grey,
// with a pin in the colour of how it was learned.
const WU = .07, HOW_FLAG = { been: 0x27406e, road: 0x8a6a3a, heard: 0x2e7d5b, map: 0x8e2317 };
function drawWorld(c, v) {
  const P = PW(), G = P.ownerGrid(v.W), N = G.N, cell = c.width / N, S = c.width / (G.half * 2);
  const at = ([x, y]) => [(x + G.half) * S, (y + G.half) * S];
  const g = c.getContext("2d");
  if (paperImg) { for (let x = 0; x < c.width; x += 720) for (let y = 0; y < c.height; y += 720) g.drawImage(paperImg, x, y, 720, 720 * paperImg.height / paperImg.width); }
  else { g.fillStyle = "#e6d8b6"; g.fillRect(0, 0, c.width, c.height); }
  g.fillStyle = "rgba(70,110,140,.28)"; g.fillRect(0, 0, c.width, c.height);   // the sea, a wash over the paper
  // The land and its inked coast, from the same grid as the nations (PlacesWorld.ownerGrid).
  const o = G.owner;
  for (let k = 0; k < N * N; k++) { if (o[k] < 0) continue; const i = k % N, j = (k / N) | 0;
    const coast = i === 0 || j === 0 || i === N - 1 || j === N - 1 || o[k - 1] < 0 || o[k + 1] < 0 || o[k - N] < 0 || o[k + N] < 0;
    g.fillStyle = coast ? "#3b2a1c" : "#e8dcbc"; g.fillRect(i * cell, j * cell, cell + .5, cell + .5); }
  // A clear watercolour wash per nation, in colours chosen so neighbours never match, and a
  // dotted line where two nations meet.
  const wash = P.nationColours(v.W);
  g.globalAlpha = .38;
  for (let k = 0; k < N * N; k++) if (o[k] >= 0) { g.fillStyle = wash[G.nations[o[k]]]; g.fillRect((k % N) * cell, ((k / N) | 0) * cell, cell + .5, cell + .5); }
  g.globalAlpha = .85; g.fillStyle = "#4a1e14";
  for (let j = 0; j < N - 1; j++) for (let i = 0; i < N - 1; i++) {
    const a = o[j * N + i]; if (a < 0 || (i + j) % 3 === 0) continue;   // dotted, not solid: a border, not a coast
    const r = o[j * N + i + 1], d = o[(j + 1) * N + i];
    if (r >= 0 && r !== a) g.fillRect((i + 1) * cell - 1.5, j * cell, 3, cell);
    if (d >= 0 && d !== a) g.fillRect(i * cell, (j + 1) * cell - 1.5, cell, 3);
  }
  g.globalAlpha = 1;
  v.K.roads.forEach(r => { const a = at(v.WL.pos[r.a]), b = at(v.WL.pos[r.b]), both = v.K.how[r.a].by === "been" && v.K.how[r.b].by === "been";
    g.strokeStyle = r.by === "sea" ? "#2f5d7c" : r.by === "river" ? "#3d6a8a" : "#3b2a1c"; g.lineWidth = r.by === "sea" || r.by === "river" ? 4 : 5;
    g.setLineDash(r.by === "sea" ? [4, 10] : both ? [] : [16, 10]); g.beginPath(); g.moveTo(...a); g.lineTo(...b); g.stroke(); });
  g.setLineDash([]);
  // Fog: a sheet of cloud with a hole round every city known.
  const fog = document.createElement("canvas"); fog.width = c.width; fog.height = c.height; const f = fog.getContext("2d");
  f.fillStyle = "rgba(246,244,240,.94)"; f.fillRect(0, 0, fog.width, fog.height);
  f.globalCompositeOperation = "destination-out";
  Object.keys(v.K.how).forEach(id => { const [x, y] = at(v.WL.pos[id]), r = 150 * S; const gr = f.createRadialGradient(x, y, r * .3, x, y, r);
    gr.addColorStop(0, "rgba(0,0,0,1)"); gr.addColorStop(1, "rgba(0,0,0,0)"); f.fillStyle = gr; f.fillRect(x - r, y - r, r * 2, r * 2); });
  g.drawImage(fog, 0, 0);
  // Names over the fog: you know a nation's name once one of its cities is known, if not its
  // land. Each lies wholly inside its own borders (PlacesWorld.placeNames).
  const measure = (text, px, sp) => { g.font = `600 ${px}px Cinzel, Palatino Linotype, Georgia, serif`;
    try { g.letterSpacing = `${sp}px`; } catch (e) { /* an older canvas has no spacing */ } return g.measureText(text).width; };
  const names = P.placeNames(v.W, v.K, measure, c.width);
  g.textAlign = "center"; g.textBaseline = "middle";
  Object.entries(names.placed).forEach(([n, at2]) => {
    g.font = `600 ${at2.size}px Cinzel, Palatino Linotype, Georgia, serif`; try { g.letterSpacing = `${at2.spacing}px`; } catch (e) { /* as above */ }
    g.lineWidth = Math.max(3, at2.size / 6); g.strokeStyle = "rgba(244,236,214,.9)"; g.fillStyle = P.darken(wash[n], .42);
    at2.lines.forEach((line, li) => { const ly = at2.y + (li - (at2.lines.length - 1) / 2) * at2.size * 1.1; g.strokeText(line, at2.x, ly); g.fillText(line, at2.x, ly); });
  });
  try { g.letterSpacing = "0px"; } catch (e) { /* as above */ }
  // A continent's name only once a city on it is known.
  g.fillStyle = "rgba(59,42,28,.55)";
  names.continents.forEach(cn => { g.font = `italic ${cn.size}px Palatino Linotype, Georgia, serif`; g.fillText(cn.name, cn.x, cn.y); });
  window.__placesNames = { placed: Object.keys(names.placed).length, missed: names.missed.slice() };   // for the checks: a name that found no room is reported
}
function worldMap(v) {
  const half = v.WL.half;
  // Painted once per state of knowledge: pressing a city changes nothing on the paper, and the
  // mock's repaint on every press cost 740 ms.
  const key = Object.keys(v.K.how).sort().join() + "|" + v.W.world;
  if (!worldPaper || worldPaper.key !== key) {
    const cv = document.createElement("canvas"); cv.width = cv.height = 2048; drawWorld(cv, v);
    worldPaper = { key, c: cv, knownConts: new Set(Object.keys(v.K.how).map(id => (cityOf(v.W, id) || {}).continent)) };
  }
  paperTex = new THREE.CanvasTexture(worldPaper.c); paperTex.colorSpace = THREE.SRGBColorSpace; paperTex.anisotropy = 8;
  const size = half * 2 * WU;
  const sheet = new THREE.Mesh(new THREE.PlaneGeometry(size, size), new THREE.MeshStandardMaterial({ map: paperTex, roughness: .95 }));
  sheet.rotation.x = -Math.PI / 2; sheet.position.y = .05; sheet.receiveShadow = true; world.add(sheet); worldSheet = sheet;
  // The highlight layer: a lit continent painted on a sheet just above the paper.
  const hlC = document.createElement("canvas"); hlC.width = hlC.height = PW().ownerGrid(v.W).N;
  const hl = new THREE.Mesh(new THREE.PlaneGeometry(size, size), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(hlC), transparent: true, depthWrite: false }));
  hl.rotation.x = -Math.PI / 2; hl.position.y = .09; hl.renderOrder = 2; world.add(hl); worldPaper.hlMesh = hl; worldPaper.hlCanvas = hlC;
  world.add(scroll(size, size));
  Object.entries(v.K.how).forEach(([id, how]) => {
    const city = cityOf(v.W, id); if (!city) return;
    const [x, z] = [v.WL.pos[id][0] * WU, v.WL.pos[id][1] * WU];
    const o = miniature("town", { painted: how.by === "been" });
    place(o, id, x, z, .2);
    // A map pin by each town, coloured by how you know it (stood in, road sign, talk, map).
    const pin = mesh(new THREE.ConeGeometry(.22, .9, 8), mat(HOW_FLAG[how.by])); pin.rotation.x = Math.PI; pin.position.set(x + 1.3, 1.6, z - .6); world.add(pin);
    const head = mesh(new THREE.SphereGeometry(.3, 12, 8), mat(HOW_FLAG[how.by], { flatShading: false })); head.position.set(x + 1.3, 2.1, z - .6); world.add(head);
    Object.assign(o.userData, { pickable: true, name: city.name, seen: how.by !== "been" });
  });
}
// Light the continent under the pointer: its land in a warm glow with a gold edge.
function paintWorldHighlight() {
  if (!worldPaper || !worldPaper.hlCanvas || !V || !V.W) return;
  const g = PW().ownerGrid(V.W), c = worldPaper.hlCanvas, x = c.getContext("2d"), N = g.N;
  x.clearRect(0, 0, c.width, c.height);
  if (hover.continent) {
    const inC = new Int8Array(N * N);
    for (let k = 0; k < N * N; k++) inC[k] = g.owner[k] >= 0 && (V.W.nations[g.nations[g.owner[k]]] || {}).continent === hover.continent ? 1 : 0;
    x.fillStyle = "rgba(255,226,150,.30)"; for (let k = 0; k < N * N; k++) if (inC[k]) x.fillRect(k % N, (k / N) | 0, 1, 1);
    x.fillStyle = "rgba(196,140,40,.95)";
    for (let k = N; k < N * N - N; k++) if (inC[k] && (!inC[k - 1] || !inC[k + 1] || !inC[k - N] || !inC[k + N])) x.fillRect((k % N) - .5, ((k / N) | 0) - .5, 2, 2);
  }
  worldPaper.hlMesh.material.map.needsUpdate = true;
}

// --- The party's miniature, the route, the walk -----------------------------------------------
function posOf(id) {
  if (!V) return null;
  if (V.level === "site") { const r = V.site.rooms.find(x => x.id === id) || (V.site.out && V.site.out.id === id ? V.site.out : null); if (!r) return null; const [x, z] = siteXZ(V, r.at); return new THREE.Vector3(x, .4, z); }
  // Underground, on the town or the Region: the party stands at the place the site lies under.
  const st = V.sites.find(x => x.rooms.some(r => r.id === id));
  if (st && st.host !== id) return posOf(st.host);
  if (V.level === "town") { const s = V.town.seats[id]; return s && s.at ? townXZ(s.at) : null; }
  if (V.level === "world") { const p = V.WL.pos[id]; return p ? new THREE.Vector3(p[0] * WU, .1, p[1] * WU) : null; }
  if (board && board.pos[id]) return board.pos[id];
  // On the Region, a place inside the town (where a walk out starts) is the town's own hex.
  if (V.level === "nation" && String(id).split("~")[0] === V.home && board && board.pos[V.home]) return board.pos[V.home];
  return null;
}
function placePc() {
  const id = V.level === "nation" && posOf(V.at) ? V.at : V.here;
  const p = posOf(id); pc.visible = !!p; if (!p) return;
  const off = V.level === "world" ? 1 : V.level === "site" ? 1.5 : 3.6;
  pc.position.copy(p).add(new THREE.Vector3(off, 0, V.level === "site" ? 1 : off));
  pc.scale.setScalar(V.level === "town" ? 2 : V.level === "world" ? .45 : 1.2);
}
function routeLine() {
  if (routeObj) { world.remove(routeObj); routeObj.geometry.dispose(); routeObj.material.dispose(); routeObj = null; }
  const node = V.sel && V.pf.nodes.find(n => n.id === V.sel);
  const legs = (node && node.walk && node.walk.legs) || [];
  // A city pressed: the journeys by known roads (the tab works them out); a place pressed: the
  // engine's own walk to it, from where the party stands.
  const ids = V.level !== "town" && V.route ? V.route : [V.level === "town" ? V.here : V.at, ...legs.map(l => l.to)];
  const pts = ids.map(posOf).filter(Boolean)
    .filter((p, k, all) => !k || p.distanceTo(all[k - 1]) > .01);   // walks inside the town are one hex
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
  // A site is a long, flat row of rooms: its diagonal in the narrower angle put frag's nine
  // sewers rooms 156 away in a 382 by 249 well, rooms a dozen pixels wide and every tag stacked
  // above the next. Its width is fitted to the wide angle and its depth (foreshortened) to the
  // tall one.
  const s3 = box.getSize(new THREE.Vector3());
  const d = Math.min(Math.max(V && V.level === "site"
    ? Math.max(s3.x / 2 / Math.tan(hfov / 2), s3.z * .7 / 2 / Math.tan(vfov / 2)) * 1.15
    : size / 2 / Math.sin(Math.min(vfov, hfov) / 2) * .9, 30), 300);
  frameD = d;
  const dir = new THREE.Vector3(-.05, .86, .56).normalize();
  camera.position.copy(c).addScaledVector(dir, d);
  // Room past the opening view to fade the town names out before the zoom-out gesture opens
  // the map above, at the furthest distance.
  controls.maxDistance = Math.max(V && V.level === "town" ? 260 : 0, d * 1.6); moved = false;
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
    // Underground ignores the hour: one cool, fixed light, the same at noon and midnight, with
    // the torch in the room you stand in. The mock's .25 and .18 were tuned on a whole window;
    // in the table's well the rooms could not be told from the table.
    if (V.level === "site") { sun.color.setRGB(.75, .8, 1); sun.position.set(-50, 90, 40); sun.intensity = .8; hemi.intensity = .55; if (pc) pc.userData.lamp.intensity = 18;
      candles.forEach((c, n) => { c.light.intensity = c.base * (still ? 1 : .82 + .18 * Math.sin(t * 11 + n) * Math.sin(t * 7.3 + n * 2)); }); }
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
// Above the town, names fade as you pull back from the view the map opened at (the owner's
// idea, 2026-11-18), and the nations' painted names carry the map; a faded name takes no room.
const LIFT = { town: 7.5, nation: 4.2, continent: 3.4, world: 1.6, site: 1.5 };   // the World's villages are small: a tag 5 up floated off them
function labels() {
  const r = stage.getBoundingClientRect(), placed = [];
  const node = V.sel && V.pf.nodes.find(n => n.id === V.sel);
  const route = new Set(V.level !== "town" && V.route ? V.route : ((node && node.walk && node.walk.legs) || []).map(l => l.to));
  const rank = o => { const id = o.userData.id; return id === V.here ? 0 : id === V.sel ? 1 : id === hoverId ? 2 : route.has(id) ? 3 : o.userData.seen ? 5 : 4; };
  const dist = camera.position.distanceTo(controls.target);
  const fade = V.level === "town" ? 0 : Math.min(1, Math.max(0, (dist - frameD) / (frameD * .4)));
  let html = "";
  pick.slice().sort((a, b) => rank(a) - rank(b)).forEach(o => {
    o.getWorldPosition(tmp); tmp.y += LIFT[V.level] || 4; tmp.project(camera);
    if (tmp.z > 1) return;
    let x = (tmp.x + 1) / 2 * r.width, y = (1 - tmp.y) / 2 * r.height;
    if (x < -40 || x > r.width + 40 || y < -10 || y > r.height + 40) return;
    const name = o.userData.name || "", road = o.userData.road || "";
    // A two-line tag is as wide as its longer line.
    const w = Math.min(Math.max(name.length * 7.2, road.length * 6.2), 190) + 16 + (o.userData.badge ? 22 : 0), h = road ? 34 : 20;
    const hit = yy => placed.some(b => x - w / 2 < b[2] + 4 && x + w / 2 > b[0] - 4 && yy - h < b[3] + 2 && yy > b[1] - 2);
    const must = rank(o) <= 3;
    let n = 0; while (n < 3 && hit(y)) { y -= h + 2; n++; }
    if (hit(y) && !must) return;
    const op = must ? 1 : 1 - fade;
    if (op < .04) return;
    if (op > .5) placed.push([x - w / 2, y - h, x + w / 2, y]);
    const id = o.userData.id;
    const cls = (V.sel === id ? " sel" : "") + (o.userData.seen ? " seen" : "") + (V.here === id ? " here" : "");
    html += `<span class="tag${cls}" style="opacity:${op.toFixed(2)};transform:translate(${x.toFixed(0)}px,${y.toFixed(0)}px) translate(-50%,-100%)"><span class="nm">${esc(name)}</span>${
      o.userData.badge ? `<b>${Number(o.userData.badge)}</b>` : ""}${road ? `<i>${esc(road)}</i>` : ""}</span>`;
  });
  // What pressing the land would open, by the pointer.
  const lit = V.level === "world" && hover.continent ? V.W.continents[hover.continent]
    : V.level === "continent" && hover.nation ? (V.W.nations[hover.nation] || {}).name : "";
  if (lit) { const hx = Math.min(hover.x + 14, r.width - String(lit).length * 10 - 50);
    html += `<span class="hint" style="transform:translate(${hx.toFixed(0)}px,${(hover.y + 10).toFixed(0)}px)">Open ${esc(lit)}</span>`; }
  tags.innerHTML = html;
}
