// The play table, part 13 (the engine device). Classic script, sharing one global scope
// with 01-12 and 14-21. Needs `window.DEVICE_GEOMETRY` (img/v2/device-geometry.js,
// loaded just before it, written by the mock's textures/prepare.py).
//
// The owner's brass mechanism (FI 3.4, "The brass status device"; the mock README, "The
// boiler room and the engine device"), carried from docs/mock/table-layout/device.js with
// its model and drawing unchanged. What differs from the mock: its images are found
// beside this script (as 06 finds the item icons), so the packaged app and runserver
// read the same files; the mock's simulated turn and its still-frame proof are gone; and
// it answers the app's own three signals (the foot of this file).
//
// Two gears turn while a turn runs, steam puffing from the foot in time with them; when
// the response lands they ease to a stop (with a burst of steam), and a heartbeat later
// the lever pops up, the lamp turns from amber to green and the tab on the top plate
// slides out glowing green. The prose does not wait for any of it (the owner, 2026-09-29:
// "dont hold back narration for it and dont worry about displaying what its doing"). A
// roll owed stops the gears with the lamp still amber: the engine is waiting on the
// player.
//
// States, on #device as data-state (for tests and for CSS):
//   idle     nothing running; lever up, lamp a calm green, tab in, no steam
//   running  a turn is running; gears turning, lever down, lamp amber, steam puffs
//   waiting  a roll is owed; gears stopped, lever down, lamp amber, a thin trickle
//   ready    the response has landed; gears easing to a stop, then the lever, the green
//            and the tab; when the green settles to its idle glow the tab goes back in
//
// Everything is a pure model advanced in fixed 1/120 s steps, so the gap from the gears'
// stop to the lever is the same arithmetic on every machine.
"use strict";

// Where this script was served from, for the device's own images: "../../img/v2/" from
// "/static/js/table/13-device.js?v=..." is "/static/img/v2/" in the browser and the
// packaged app alike. Never a path built from where the app was installed.
const DEVICE_IMG_BASE = (() => {
  const s = document.querySelector('script[src*="js/table/13-device.js"]');
  try { return new URL("../../img/v2/", s.src).href; }
  catch { return "/static/img/v2/"; }
})();

// --- The gear train ----------------------------------------------------------------------
// The owner, 2026-10-05: "the gears are not synced correctly and are often spinning the
// same direction instead of how they should." The angles were never the fault: the large
// gear's was already derived from the small one's, at -10/16, half a tooth out of phase at
// the mesh (the drawn outlines touch by 0.05 photo px at worst over a full pitch). What
// the eye saw was the wagon wheel. A gear is a pattern that repeats every tooth, so a frame
// that moves it half a tooth or more is read as moving the other way (sampling below twice
// per period reverses apparent motion). At 1.4 turns a second the large gear's 16 teeth
// pass 22.4 a second: 0.37 of a tooth per 60 Hz frame, 0.56 on a frame that caught three
// 1/120 s model steps, 0.75 at 30 fps. Measured in the running app before this fix: frames
// of 20 ms on median, 0.56 of a tooth a frame, 54 of 85 at half a tooth or more. The small
// gear had no lightening holes, so its teeth were its only cue and it read as turning the
// large one's way.
//
// So the gears are drawn from one driver angle that is never allowed to move more than a
// third of a tooth in a frame (a slow frame slows the drawing, it can never reverse it),
// smoothed between model steps (Fiedler's "Fix Your Timestep!": draw the state
// interpolated by the accumulator's remainder, or a 60 Hz frame alternates two steps and
// three), and every gear's angle is derived from it by the train's own ratios: meshing
// with another is -z_other/z and half a tooth of phase so tooth meets gap; on another's
// axle is the same angle. Nothing else turns a gear, so they cannot drift apart.
//
// One entry per gear in DEVICE_GEOMETRY.gears (prepare.py's GEAR_SMALL, GEAR_LARGE): the
// first is the driver; `meshes: i` or `axle: i` names the gear it is driven from.
const DEVICE_TRAIN = [
  { holes: 4, hub: 0.9 },              // the small gear, above: the driver
  { meshes: 0, holes: 5, hub: 1.1 },   // the large gear, below, meshing with it
];
// The most any gear may turn in one drawn frame, in its own teeth. Half a tooth is where
// the motion reverses; a third leaves the forward reading twice as near as the backward.
const DEVICE_MAX_TEETH_PER_FRAME = 1 / 3;

// The train as a table: each gear's centre in the device's box, tooth count, pitch (deg a
// tooth), and its angle as `phase + ratio * driver` (ratio signed: + turns with the driver,
// - against it).
function deviceGears(G, train = DEVICE_TRAIN) {
  const [ox, oy] = G.origin;
  const frac = v => ((v % 1) + 1) % 1;
  const gears = [];
  G.gears.forEach(([x, y, z], i) => {
    const t = train[i] || {};
    const g = { i, x: x - ox, y: y - oy, z, pitch: 360 / z, holes: t.holes || 0,
                hub: t.hub || 1, meshes: t.meshes ?? null, axle: t.axle ?? null,
                ratio: 1, phase: 0 };
    if (g.meshes != null) {
      const p = gears[g.meshes];
      g.ratio = -p.ratio * p.z / g.z;
      // Where they touch, on the line between the centres: a tooth of one must sit in a
      // gap of the other. Angles run clockwise on screen, so at the contact point the two
      // gears' angles run opposite ways along the tangent: the fraction of a pitch past a
      // tooth on one is half a pitch less that fraction on the other.
      const toward = Math.atan2(g.y - p.y, g.x - p.x) * 180 / Math.PI;
      const fP = frac((toward - p.phase) / p.pitch);
      g.phase = (frac((toward + 180) / g.pitch) - frac(0.5 - fP)) * g.pitch;
    } else if (g.axle != null) {
      const p = gears[g.axle];
      g.ratio = p.ratio; g.phase = p.phase;
    }
    gears.push(g);
  });
  return gears;
}
// Each gear's angle, in degrees, for one driver angle.
function deviceGearAngles(gears, driver) {
  return gears.map(g => g.phase + g.ratio * driver);
}
// The most the driver may turn in a frame so that no gear turns more than the cap.
function deviceFrameCap(gears) {
  return Math.min(...gears.map(g => DEVICE_MAX_TEETH_PER_FRAME * g.pitch / Math.abs(g.ratio)));
}
// One drawn frame: the model's driver angle (`target`, interpolated) moves the drawn one
// on by what it moved since the last frame, capped, never back. `shown` is {from, angle}.
function deviceShow(shown, target, cap) {
  shown.angle += Math.max(0, Math.min(cap, target - shown.from));
  shown.from = target;
  return shown.angle;
}

(function buildDevice() {
  const G = window.DEVICE_GEOMETRY;
  const el = document.getElementById("device");
  if (!G || !el) return;
  const NS = "http://www.w3.org/2000/svg";
  const [ox, oy] = G.origin;
  const P = (x, y) => [x - ox, y - oy];               // photograph px to the device's box
  const LIGHT = G.light;                               // scene3d.js's lamp, for the gears

  // --- Timings. Heartbeat is the owner's "the gears should stop a heartbeat before the
  // lever lifts up": 700 ms, the length of one beat at 86 per minute.
  const T = {
    STEP: 1000 / 120,
    SPIN_UP: 260,          // ms time constant of the gears coming up to speed
    HALT: 520,             // ms from full speed to still (an ease-out, never a snap)
    HEARTBEAT: 700,        // ms between the gears stopping and the lever lifting
    CALM: 2600,            // ms for the green to settle to its idle glow; the tab goes in
    // Steam. The owner, twice: puffs "in time with the gears", then "increase the smoke a
    // bunch". Every half turn of the large gear read as a leak; a third of a turn (about
    // four a second at speed) reads as a machine working.
    PUFF_EVERY: 1 / 3,     // turns of the large gear between puffs, running
    PUFF_LIFE: 1700,
    TRICKLE: 950, TRICKLE_LIFE: 2300,    // waiting on a die: a lazy thread, by the clock
    BURST: 4, BURST_GAP: 70, BURST_LIFE: 2100,   // the halt: a cloud, just before the lever
  };
  // The train (deviceGears, above): gear 0 drives, the large gear is the last. M.aS is the
  // driver's angle in the model; the drawing derives every gear's from it.
  const GEARS = deviceGears(G);
  const LARGEST = GEARS.reduce((a, g) => (g.z > a.z ? g : a));
  const RATIO = 1 / Math.abs(LARGEST.ratio);           // the driver turns this much faster
  const LARGE_RPS = 1.4;                               // large gear, turns a second, at speed
  const OMEGA = LARGE_RPS * 360 * RATIO;               // the driver, degrees a second
  const FRAME_CAP = deviceFrameCap(GEARS);             // driver degrees a drawn frame, at most
  const LEVER_UP = -46, LEVER_DOWN = 34;               // degrees, about the knob

  // --- Drawing: the gears, procedurally, from tooth count and module ------------------
  function gearPath(cx, cy, z, m, holes) {
    const R = m * z / 2, Ra = R + 0.9 * m, Rf = R - 1.1 * m, p = 2 * Math.PI / z;
    const pt = (r, a) => `${(cx + r * Math.cos(a)).toFixed(2)} ${(cy + r * Math.sin(a)).toFixed(2)}`;
    let d = "";
    for (let i = 0; i < z; i++) {
      const th = i * p;
      const a0 = th - 0.27 * p, a1 = th - 0.16 * p, a2 = th + 0.16 * p, a3 = th + 0.27 * p;
      const next = th + 0.73 * p;
      d += (i ? " L " : "M ") + pt(Rf, a0) + " L " + pt(Ra, a1)
        + ` A ${Ra} ${Ra} 0 0 1 ` + pt(Ra, a2) + " L " + pt(Rf, a3)
        + ` A ${Rf} ${Rf} 0 0 1 ` + pt(Rf, next);
    }
    d += " Z";
    const circle = (x, y, r) => ` M ${(x + r).toFixed(2)} ${y.toFixed(2)} A ${r} ${r} 0 1 0 ${
      (x - r).toFixed(2)} ${y.toFixed(2)} A ${r} ${r} 0 1 0 ${(x + r).toFixed(2)} ${y.toFixed(2)} Z`;
    d += circle(cx, cy, R * 0.2);                      // the arbor hole
    for (let i = 0; i < holes; i++) {                  // lightening holes, so turning shows
      const a = i * 2 * Math.PI / holes;
      d += circle(cx + R * 0.55 * Math.cos(a), cy + R * 0.55 * Math.sin(a), R * 0.15);
    }
    return d;
  }
  function svg(cls) {
    const s = document.createElementNS(NS, "svg");
    s.setAttribute("viewBox", `0 0 ${G.box[0]} ${G.box[1]}`);
    s.setAttribute("class", cls);
    s.setAttribute("aria-hidden", "true");
    return s;
  }
  // A gradient laid across the gear from the lamp's side to the far side. It is counter-
  // rotated every frame (gradientTransform), so the light stays in the room while the
  // gear turns under it: the same rule scene3d.js keeps for the board.
  function brass(id, cx, cy, r) {
    const k = r * 1.05;
    return `<linearGradient id="${id}" gradientUnits="userSpaceOnUse"
        x1="${cx + LIGHT[0] * k}" y1="${cy + LIGHT[1] * k}" x2="${cx - LIGHT[0] * k}" y2="${cy - LIGHT[1] * k}">
        <stop offset="0" stop-color="#dcbc7c"/><stop offset=".4" stop-color="#a47d3e"/>
        <stop offset=".75" stop-color="#6a4c20"/><stop offset="1" stop-color="#34240e"/></linearGradient>`;
  }
  // Every gear of the table, the largest underneath; then the hubs over them all. The small
  // gear had no lightening holes until 2026-10-05: its teeth were all that showed it turn.
  const gears = svg("dv-gears");
  const under = [...GEARS].sort((a, b) => b.z - a.z);
  gears.innerHTML = `<defs>${GEARS.map(g => brass(`dvbrass${g.i}`, g.x, g.y, G.m * g.z / 2)).join("")}</defs>
    ${under.map(g => `<g id="dvgear${g.i}"><path d="${gearPath(g.x, g.y, g.z, G.m, g.holes)}"
      fill="url(#dvbrass${g.i})" fill-rule="evenodd" stroke="#2a1c0a" stroke-width="1.6"
      stroke-linejoin="round"/></g>`).join("")}
    ${under.map(g => `<circle cx="${g.x}" cy="${g.y}" r="${G.m * g.hub}" fill="#6e5226"
      stroke="#2a1c0a" stroke-width="1.2"/>`).join("")}`;
  el.querySelector(".dv-chamber").after(gears);
  const gearEls = GEARS.map(g => gears.querySelector(`#dvgear${g.i}`));
  const gradEls = GEARS.map(g => gears.querySelector(`#dvbrass${g.i}`));

  // The lamp in the top plate's socket, its bloom on the brass, and the lever on the knob.
  const top = svg("dv-top");
  const [lpx, lpy] = P(G.lamp[0], G.lamp[1]), lr = G.lamp[2];
  const [kx, ky] = P(G.knob[0], G.knob[1]), kr = G.knob[2];
  top.innerHTML = `<defs>
      <radialGradient id="dvbloom"><stop offset="0" stop-color="var(--lamp)" stop-opacity=".9"/>
        <stop offset=".35" stop-color="var(--lamp)" stop-opacity=".35"/>
        <stop offset="1" stop-color="var(--lamp)" stop-opacity="0"/></radialGradient>
      <radialGradient id="dvglass" cx=".36" cy=".32" r=".75">
        <stop offset="0" stop-color="#fffbe8"/><stop offset=".35" stop-color="var(--lamp)"/>
        <stop offset="1" stop-color="var(--lamp-deep)"/></radialGradient>
      <linearGradient id="dvarm" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#f0d69c"/><stop offset=".5" stop-color="#a98040"/>
        <stop offset="1" stop-color="#4f3817"/></linearGradient>
      <radialGradient id="dvball" cx=".35" cy=".3" r=".8">
        <stop offset="0" stop-color="#fff0c8"/><stop offset=".45" stop-color="#b98f4e"/>
        <stop offset="1" stop-color="#3f2c12"/></radialGradient></defs>
    <circle class="dv-bloom" cx="${lpx}" cy="${lpy}" r="${lr * 6}" fill="url(#dvbloom)"/>
    <circle cx="${lpx}" cy="${lpy}" r="${lr * 0.95}" fill="url(#dvglass)" class="dv-glass"
      stroke="#3a2a12" stroke-width="2"/>
    <g class="dv-lever">
      <rect x="${kx}" y="${ky - 5}" width="${kr * 6.2}" height="10" rx="5" fill="url(#dvarm)"
        stroke="#2a1c0a" stroke-width="1.4"/>
      <circle cx="${kx + kr * 6.2}" cy="${ky}" r="${kr * 0.8}" fill="url(#dvball)"
        stroke="#2a1c0a" stroke-width="1.4"/>
    </g>
    <circle cx="${kx}" cy="${ky}" r="${kr * 0.95}" fill="url(#dvball)" stroke="#2a1c0a" stroke-width="1.6"/>`;
  el.querySelector(".dv-frame").after(top);
  const lever = top.querySelector(".dv-lever"), bloom = top.querySelector(".dv-bloom");
  const footEl = el.querySelector(".dv-foot");

  // The tab (the owner's "glowing bit that pops out green"): the photograph's own piece,
  // cut out by prepare.py, under the frame so that pulled in it is inside the body. Out, it
  // glows: its face lit green (a copy of the piece through a colour matrix, screened onto
  // it), and a halo (below, outside the body) that blooms onto the brass beside it and
  // spills faintly onto whatever the device is mounted over.
  const [tbx, tby, tbw, tbh] = G.tab, TAB_TRAVEL = G.tabTravel;
  const [tx, ty] = P(tbx, tby);
  const tabSvg = svg("dv-tab");
  const tabHref = DEVICE_IMG_BASE + "device-tab.png";
  tabSvg.innerHTML = `<defs><filter id="dvtablit" color-interpolation-filters="sRGB">
      <feColorMatrix type="matrix" values="0.14 0.30 0.06 0 0.06  0.28 0.62 0.12 0 0.30
        0.12 0.26 0.05 0 0.05  0 0 0 1 0"/></filter></defs>
    <g class="dv-tabmove">
      <image href="${tabHref}" x="${tx}" y="${ty}" width="${tbw}" height="${tbh}"
        preserveAspectRatio="none"/>
      <image class="dv-tablit" href="${tabHref}" x="${tx}" y="${ty}" width="${tbw}"
        height="${tbh}" preserveAspectRatio="none" filter="url(#dvtablit)" opacity="0"/>
    </g>`;
  el.querySelector(".dv-frame").before(tabSvg);
  const tabMove = tabSvg.querySelector(".dv-tabmove"), tabLit = tabSvg.querySelector(".dv-tablit");
  // The halo's centre: the tab's outer half, out.
  const hx = tx + 10, hy = ty + tbh / 2;
  const halo = svg("dv-halo");
  halo.innerHTML = `<defs><radialGradient id="dvtabhalo">
      <stop offset="0" stop-color="#b8ffa8" stop-opacity=".95"/>
      <stop offset=".3" stop-color="#8ef07e" stop-opacity=".5"/>
      <stop offset=".65" stop-color="#5fd24e" stop-opacity=".16"/>
      <stop offset="1" stop-color="#5fd24e" stop-opacity="0"/></radialGradient></defs>
    <ellipse cx="${hx}" cy="${hy}" rx="46" ry="${tbh * 0.78}" fill="url(#dvtabhalo)"/>`;
  el.querySelector(".dv-body").after(halo);

  // Steam: soft sprites, moved by transform and faded by opacity only. The pool is the
  // most that can be alive at once: a puff every third of a turn of the large gear for
  // PUFF_LIFE, and the burst at the halt on top.
  const smoke = el.querySelector(".dv-smoke");
  const POOL = 18;
  for (let i = 0; i < POOL; i++) smoke.insertAdjacentHTML("beforeend", `<i></i>`);
  const sprites = [...smoke.children];
  const [fx, fy] = P(G.foot[0], G.foot[1]);

  // --- The model ---------------------------------------------------------------------
  const fresh = () => ({
    t: 0, mode: "idle", omega: 0, aS: 0, aPrev: 0, largeTurns: 0, nextPuff: T.PUFF_EVERY, nextTick: 0,
    halt: null, stopAt: null, leverAt: null, readyAt: null,
    lever: LEVER_UP, leverV: 0, leverTarget: LEVER_UP,
    tab: 0, tabV: 0, tabTarget: 0,                       // 0 in, 1 out
    green: 1, lampLevel: 0.5, puffs: [], seq: 0, nextTrickle: 0, log: [],
    foot: 0, footV: 0,                                   // photo px down from rest
  });
  const M = fresh();

  // Each event with the model's time and the wall clock (for the measured gap).
  function event(name) {
    M.log.push([name, Math.round(M.t), Math.round(performance.now())]);
    sound(EVENT_SOUND[name]);
  }

  // --- Its sound (the owner, 2026-10-02: "this needs sound as well, not too loud"). Each
  // is one of the model's own moments, so the ear and the eye cannot disagree: a puff of
  // steam is heard as it is drawn, the settle as the gears stop, the lever as it lifts.
  // The ticks are the large gear's teeth passing, paced by its real speed, so they slow
  // as it eases to a stop. All on the quiet ui bus (sound.js "ui.device.*").
  const EVENT_SOUND = {
    "puff": "ui.device.puff", "gears-stopped": "ui.device.settle",
    "last-puff": "ui.device.sigh", "lever-up": "ui.device.lever",
  };
  // Tooth clicks (the owner's reference: a spinning cog machine, not a clock): one every
  // eighth of a turn of the large gear, each at a slightly different pitch and spacing, so
  // the stream reads as teeth meshing rather than a metronome.
  const TICK_EVERY = 1 / 8;                            // turns of the large gear per click

  // --- The foot (the owner, 2026-10-02: "if we could make this go up and down a bit with
  // the smoke puffs that would be excellent"). The stem under the bottom plate is its own
  // piece (device-foot.png, beneath the frame), kicked down by each puff as the puff
  // appears, in proportion to its size, and brought back by a stiff spring with a slight
  // bounce: a steady bob while the gears run, a deeper one with the burst at the stop.
  // Clamped inside the stem's hidden extension under the plate (prepare.py FOOT_LIFT: eight
  // rows of the 0.45-scale sheet, 17 photo px), so a dip never opens a gap. The kick was
  // 130 at first and measured a 0.6-pixel bob at the table's size: there, but invisible.
  const FOOT = { KICK: 650, K: 1100, C: 36, MAX: 15, MIN: -4 };
  // A tab brought back from the background catches the model up in one frame's worth of
  // steps; without this every tick and puff it missed would sound at once.
  const lastSaid = {};
  function sound(name, opts) {
    if (!name || !window.Sound) return;
    const now = performance.now();
    if (now - (lastSaid[name] || -1e9) < (name === "ui.device.tick" ? 28 : 70)) return;
    lastSaid[name] = now;
    try { Sound.play(name, opts); } catch (err) { /* the machine works in silence too */ }
  }
  // The running bed: started when the gears begin to turn, its speed set from theirs every
  // frame, stopped once they are still.
  let bed = null;
  function bedFollow() {
    if (!window.Sound || typeof Sound.machine !== "function") return;
    const v = Math.min(1, M.omega / OMEGA);
    if (v > 0.01 && !bed) bed = Sound.machine();
    if (!bed) return;
    if (v <= 0.01) { bed.stop(); bed = null; } else bed.speed(v);
  }

  function step(dt) {
    M.t += dt;
    // Gears: toward speed while running; a fixed ease-out to zero when halting.
    if (M.mode === "running" && !M.halt) {
      M.omega += (OMEGA - M.omega) * (1 - Math.exp(-dt / T.SPIN_UP));
    } else if (M.halt) {
      const s = Math.min(1, (M.t - M.halt.t0) / T.HALT);
      M.omega = M.halt.w0 * (1 - s) * (1 - s);
      if (s >= 1 && M.stopAt == null) {
        M.omega = 0; M.stopAt = M.t; event("gears-stopped");
        if (M.halt.then === "ready") {
          // The machine comes to rest with a burst: a few big puffs a beat apart, which
          // billow up the gutter while the heartbeat passes.
          for (let i = 0; i < T.BURST; i++) {
            spawn(1.55 + 0.18 * i, T.BURST_LIFE, i * T.BURST_GAP, i ? null : "last-puff");
          }
          M.leverAt = M.t + T.HEARTBEAT;
        } else if (M.halt.then === "idle") {
          // A turn that came back with nothing done (a refusal, a busy table, a failed
          // request): it simply comes to rest, lever up and the calm green, no flourish.
          M.mode = "idle"; M.leverTarget = LEVER_UP; M.tabTarget = 0; M.halt = null;
          event("idle");
        } else {
          M.nextTrickle = M.t + T.TRICKLE * 0.6;
        }
      }
    }
    M.aPrev = M.aS;                                     // for drawing between steps
    M.aS += M.omega * dt / 1000;
    M.largeTurns += M.omega * dt / 1000 / RATIO / 360;
    if (M.omega > 1 && M.largeTurns >= M.nextTick) {
      const v = Math.min(1, M.omega / OMEGA);
      sound("ui.device.tick", { volume: 0.55 + 0.45 * v, rate: 0.9 + 0.2 * Math.random() });
      M.nextTick = M.largeTurns + TICK_EVERY * (0.8 + 0.4 * Math.random());
    }
    // (run() re-arms nextPuff from where the gear is: the halt turns it past the old mark,
    // and a test that the mark was crossed this step then never fired again. Measured:
    // turns three to five of a live run had no steam at all.)
    if (M.mode === "running" && !M.halt && M.largeTurns >= M.nextPuff) {
      // Sizes vary a little, from the golden-ratio sequence, so no two read alike.
      spawn(1.05 + 0.4 * ((M.seq * 0.618) % 1), T.PUFF_LIFE); M.nextPuff += T.PUFF_EVERY;
    }
    if (M.mode === "waiting" && M.stopAt != null && M.t >= M.nextTrickle) {
      spawn(0.62, T.TRICKLE_LIFE, 0, "trickle"); M.nextTrickle += T.TRICKLE;
    }
    // The lever: a damped spring toward its target, so it overshoots a little and settles.
    // The tab comes out on the same beat, on its own stiffer spring.
    if (M.leverAt != null && M.t >= M.leverAt && M.leverTarget !== LEVER_UP) {
      M.leverTarget = LEVER_UP; M.tabTarget = 1; M.green = 1; M.readyAt = M.t; event("lever-up");
    }
    const k = 520, c = 26;                              // per second squared, per second
    const acc = k * (M.leverTarget - M.lever) - c * M.leverV;
    M.leverV += acc * dt / 1000; M.lever += M.leverV * dt / 1000;
    // Stiffer and a touch less damped than the lever (damping ratio 0.56): it overshoots
    // by about a tenth of its travel, 1px at 1440, and is still in 0.4 s.
    const tacc = 900 * (M.tabTarget - M.tab) - 34 * M.tabV;
    M.tabV += tacc * dt / 1000; M.tab += M.tabV * dt / 1000;
    // The lamp: amber and steady while working; a flash of green at the lever, settling.
    if (M.mode === "running" || M.mode === "waiting" || (M.mode === "ready" && M.readyAt == null)) {
      M.lampLevel += (1 - M.lampLevel) * (1 - Math.exp(-dt / 180));
    } else if (M.readyAt != null) {
      const u = Math.min(1, (M.t - M.readyAt) / T.CALM);
      M.lampLevel = 1.35 - 0.85 * (1 - Math.pow(1 - u, 3));
      // Settled to its idle glow, the tab goes back in: it is out only while the green is
      // the answer to a turn, not the table's resting light.
      if (u >= 1 && M.mode === "ready") { M.mode = "idle"; M.tabTarget = 0; event("idle"); }
    } else if (M.mode === "idle") {
      M.lampLevel += (0.5 - M.lampLevel) * (1 - Math.exp(-dt / 400));
    }
    for (const p of M.puffs) {
      if (!p.kicked && M.t >= p.t0) { p.kicked = true; M.footV += FOOT.KICK * p.size; }
    }
    const facc = -FOOT.K * M.foot - FOOT.C * M.footV;
    M.footV += facc * dt / 1000; M.foot += M.footV * dt / 1000;
    if (M.foot > FOOT.MAX) { M.foot = FOOT.MAX; M.footV = Math.min(0, M.footV); }
    if (M.foot < FOOT.MIN) { M.foot = FOOT.MIN; M.footV = Math.max(0, M.footV); }
    M.puffs = M.puffs.filter(p => M.t - p.t0 < p.life);
  }
  function spawn(size, life, delay = 0, name = "puff") {
    M.puffs.push({ t0: M.t + delay, size, life, seed: (M.seq++ * 0.618) % 1 });
    if (name) event(name);
  }

  // --- Drawing a model state -----------------------------------------------------------
  // Layout width, not the drawn box: on a phone the device is turned a quarter, and its
  // bounding box is then its height.
  const px = () => el.offsetWidth / G.box[0];                      // device px per photo px
  // Where it lives: on the stage, on the gilt edge of the centre column (CSS alone places
  // it there); or on a phone, lying in the head bar. Moving or hiding the element never
  // restarts or freezes a turn: the model is not touched by any of this.
  const home = el.parentElement, slot = document.getElementById("dv-slot");
  const phone = window.matchMedia("(max-width: 760px)");
  let turned = false;
  function place() {
    turned = phone.matches && !!slot;
    if (turned) slot.appendChild(el);
    else if (el.parentElement !== home) home.prepend(el);
    draw();
  }
  if (phone.addEventListener) phone.addEventListener("change", place);
  // The drawn driver (deviceShow): it follows the model's, a third of a tooth a frame at
  // most. `alpha` is how far the clock is into the next model step (the loop's remainder).
  const shown = { from: 0, angle: 0 };
  let alpha = 0;
  function draw() {
    const driver = deviceShow(shown, M.aPrev + (M.aS - M.aPrev) * alpha, FRAME_CAP);
    deviceGearAngles(GEARS, driver).forEach((a, i) => {
      const g = GEARS[i];
      gearEls[i].setAttribute("transform", `rotate(${a.toFixed(2)} ${g.x} ${g.y})`);
      gradEls[i].setAttribute("gradientTransform", `rotate(${(-a).toFixed(2)} ${g.x} ${g.y})`);
    });
    lever.setAttribute("transform", `rotate(${M.lever.toFixed(2)} ${kx} ${ky})`);
    if (footEl) footEl.style.transform = `translateY(${(M.foot * px()).toFixed(2)}px)`;
    bedFollow();
    const green = M.leverTarget === LEVER_UP && M.mode !== "running" && M.mode !== "waiting";
    el.style.setProperty("--lamp", green ? "#8ef07e" : "#ffb23c");
    el.style.setProperty("--lamp-deep", green ? "#1e6a1a" : "#8a4a08");
    bloom.style.opacity = (Math.min(1.3, M.lampLevel) * (green ? 0.8 : 0.9)).toFixed(3);
    // The tab: out is 0 offset (where prepare.py put it), in is TAB_TRAVEL to the right.
    // Its glow follows how far out it is, so it dims as it goes in and never shows inside.
    const out = Math.max(0, Math.min(1, M.tab));
    tabMove.setAttribute("transform", `translate(${(TAB_TRAVEL * (1 - M.tab)).toFixed(2)} 0)`);
    tabLit.setAttribute("opacity", (0.9 * out).toFixed(3));
    halo.style.opacity = (out * out).toFixed(3);
    el.dataset.state = M.mode;
    el.dataset.omega = Math.round(M.omega);
    el.dataset.lever = Math.round(M.lever);
    el.dataset.tab = M.tab.toFixed(2);
    el.dataset.puffs = M.puffs.length;
    const s = px(), w = G.box[0] * s;
    // The steam's path, in device widths. Upright: up the gutter, drifting left (away from
    // the story, over the side panel's margin), billowing as it rises; measured so that it
    // never reaches past the device's own right edge or the side panel's text (README).
    // Turned on a phone: a short rise (the head bar is 30px) and a drift along the device.
    const F = turned ? { rise: 0.5, drift: -0.35, born: 0.45, grow: 0.5, dens: 0.8 }
                     : { rise: 2.7, drift: 0.55, born: 0.6, grow: 1.3, dens: 1 };
    sprites.forEach((sp, i) => {
      const p = M.puffs[i];
      const u = p ? (M.t - p.t0) / p.life : -1;
      if (u < 0) { sp.style.opacity = "0"; return; }
      const sdx = -w * (F.drift * (1 - (1 - u) * (1 - u)) + 0.06 * Math.sin(u * 5.2 + p.seed * 6));
      const sdy = -w * F.rise * Math.pow(u, 0.85);
      const [ldx, ldy] = turned ? [sdy, -sdx] : [sdx, sdy];
      const x = fx * s + ldx, y = fy * s + ldy;
      const sc = p.size * (F.born + F.grow * Math.sqrt(u));
      // A little turn of its own so no two puffs share a silhouette; on a phone, turned
      // back a quarter so its bright lobe still faces the lamp.
      const rot = (turned ? -90 : 0) + (p.seed - 0.5) * 40;
      sp.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) translate(-50%, -50%) rotate(${rot.toFixed(1)}deg) scale(${sc.toFixed(3)})`;
      sp.style.opacity = (F.dens * Math.min(1, u * 5) * Math.pow(1 - u, 0.9)).toFixed(3);
    });
  }

  // --- The live loop: running only while something moves ------------------------------
  let raf = 0, last = 0, acc = 0;
  function loop(now) {
    // Up to a second of catch-up: the turn is real time, so a slow frame (or a tab in the
    // background) must not stretch the heartbeat. Capped only so a long-hidden tab does
    // not replay minutes of steam on return.
    acc += Math.min(1000, now - last); last = now;
    while (acc >= T.STEP) { step(T.STEP); acc -= T.STEP; }
    alpha = acc / T.STEP;
    draw();
    const moving = M.mode !== "idle" || M.omega > 0.01 || M.puffs.length || M.halt
      || Math.abs(M.lever - M.leverTarget) > 0.05 || Math.abs(M.leverV) > 0.05
      || Math.abs(M.tab - M.tabTarget) > 0.002 || Math.abs(M.tabV) > 0.002
      || Math.abs(M.foot) > 0.02 || Math.abs(M.footV) > 0.05;
    raf = moving ? requestAnimationFrame(loop) : 0;
  }
  function wake() { if (!raf) { last = performance.now(); acc = 0; raf = requestAnimationFrame(loop); } }

  window.Device = {
    run() { M.halt = null; M.stopAt = null; M.leverAt = null; M.readyAt = null;
            M.mode = "running"; M.leverTarget = LEVER_DOWN; M.tabTarget = 0;
            M.nextPuff = M.largeTurns + T.PUFF_EVERY; event("running"); wake(); },
    wait() { M.mode = "waiting"; M.halt = { t0: M.t, w0: M.omega, then: "wait" };
             M.stopAt = null; M.leverAt = null; M.readyAt = null; M.leverTarget = LEVER_DOWN;
             M.tabTarget = 0; event("waiting"); wake(); },
    // The response has landed: the gears ease to a stop, a heartbeat, then the lever, the
    // green and the tab. Nothing waits on it (the owner's ruling, 2026-09-29: "dont hold
    // back narration for it"); the prose is already on the page.
    ready() {
      M.mode = "ready"; M.halt = { t0: M.t, w0: M.omega, then: "ready" }; M.stopAt = null;
      M.leverAt = null; M.readyAt = null; event("ready"); wake();
    },
    // A turn that ended with no answer to show: to rest, without the flourish.
    stop() {
      if (M.mode === "idle" && !M.halt) return;
      M.halt = { t0: M.t, w0: M.omega, then: "idle" }; M.stopAt = null; M.leverAt = null;
      event("stop"); wake();
    },
    state: () => M.mode,
    log: () => M.log.slice(),
  };
  draw();
  place();
})();

// --- The signals: what the page already knows, and nothing more -------------------------
// The owner, 2026-09-29: "dont hold back narration for it and dont worry about displaying
// what its doing." So the device knows only what this page's own client knows, and never
// delays the story:
//
//   running  `busy(true)` (06 dispatches `table:busy`): around /api/say in takeTurn, and
//            likewise /api/roll, /api/combat/act, the craft hub and a free ability.
//   answer   the POST's reply (`table:posted`, 02's `post`, dispatched before the caller
//            draws it): `ready()`, or `wait()` when the reply owes a roll (`awaiting`),
//            resumed by /api/roll, which is a turn of its own.
//   no answer  `busy(false)` with nothing landed (a 422 refusal, a busy table, a stale
//            screen, a failed request): `stop()`, back to rest without the green flourish.
//
// Posts outside a turn (a counter's deal, a talk button, preparing a spell, the die's
// face) never move it: only one that lands while a turn is in flight answers.
const DEVICE_TURN = { inFlight: false, told: false };

function deviceSay(what) {
  const D = window.Device;
  if (D && typeof D[what] === "function") D[what]();
}

document.addEventListener("table:busy", e => {
  const on = !!(e.detail && e.detail.on);
  if (on) {
    DEVICE_TURN.inFlight = true;
    DEVICE_TURN.told = false;
    deviceSay("run");
    return;
  }
  if (DEVICE_TURN.inFlight && !DEVICE_TURN.told) deviceSay("stop");
  DEVICE_TURN.inFlight = false;
});

document.addEventListener("table:posted", e => {
  if (!DEVICE_TURN.inFlight || DEVICE_TURN.told) return;
  DEVICE_TURN.told = true;
  // `Device.wait()` for a roll owed, `Device.ready()` for a turn done.
  deviceSay(e.detail && e.detail.awaiting ? "wait" : "ready");
});

// A roll owed that no turn of this page's asked for: a page opened (or reloaded) with a
// die pending, or the other device's turn drawn here by the resync. The state says the
// engine is waiting on the player, so the device says so too; and when a drawn state
// owes nothing while the device still waits (the other device rolled it), it comes to
// rest. Found live: a page reloaded over a pending attack roll showed the device idle.
onRender(function deviceWaits(s) {
  if (DEVICE_TURN.inFlight) return;
  const D = window.Device;
  if (!D || typeof D.state !== "function") return;
  const owed = !!(s && s.awaiting);
  if (owed && D.state() === "idle") D.wait();
  else if (!owed && D.state() === "waiting") D.stop();
});
