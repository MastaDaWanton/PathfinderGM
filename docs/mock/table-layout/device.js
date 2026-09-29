// The engine device: the owner's brass mechanism, bolted to the book's left gilt edge just
// below the top of the gutter, showing where a turn is. Two gears turn while the pipeline
// runs, steam puffing from the foot in time with them; they ease to a stop when the
// narrator is ready (with a burst of steam), and a heartbeat later the lever pops up, the
// lamp turns from amber to green and the tab on the top plate slides out glowing green,
// and only then does the prose appear. A roll owed stops the gears with the lamp still
// amber: the engine is waiting on the player.
//
// States, on #device as data-state (for tests and for CSS):
//   idle     nothing running; lever up, lamp a calm green, tab in, no steam
//   running  the pipeline is at work; gears turning, lever down, lamp amber, steam puffs
//   waiting  a roll is owed; gears stopped, lever down, lamp amber, a thin trickle
//   ready    the narrator is ready; gears easing to a stop, then the lever, the green and
//            the tab; when the green settles to its idle glow the tab goes back in
//
// Motion here answers the player's own action (Say, Continue, a way on), which the owner
// asked for in as many words. Nothing moves under the pointer: the device and its steam
// sit in the gap beside the pen and pass the pointer through.
//
// Everything is a pure model advanced in fixed 1/120 s steps, so a still frame at any
// moment of a scripted turn can be drawn exactly (#devicet=ms, used for the frame proof),
// and the live page and the proof run the same arithmetic.
"use strict";

(function () {
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
    PROSE_AFTER_LEVER: 280,// ms: the lever has overshot and settled before the text lands
    CALM: 2600,            // ms for the green to settle to its idle glow; the tab goes in
    // Steam. The owner, twice: puffs "in time with the gears", then "increase the smoke a
    // bunch". Every half turn of the large gear read as a leak; a third of a turn (about
    // four a second at speed) reads as a machine working.
    PUFF_EVERY: 1 / 3,     // turns of the large gear between puffs, running
    PUFF_LIFE: 1700,
    TRICKLE: 950, TRICKLE_LIFE: 2300,    // waiting on a die: a lazy thread, by the clock
    BURST: 4, BURST_GAP: 70, BURST_LIFE: 2100,   // the halt: a cloud, just before the lever
  };
  const [zS, zL] = [G.gears[0][2], G.gears[1][2]];
  const RATIO = zL / zS;                               // the small gear turns this much faster
  const LARGE_RPS = 1.4;                               // large gear, turns a second, at speed
  const OMEGA = LARGE_RPS * 360 * RATIO;               // small gear, degrees a second
  const LEVER_UP = -46, LEVER_DOWN = 34;               // degrees, about the knob
  // Mesh: where the gears touch (straight below the small one, straight above the large),
  // a tooth of one must sit in a gap of the other. Worked out from the tooth counts, so
  // other counts mesh too.
  const MESH = (() => {
    const pS = 360 / zS, pL = 360 / zL;
    // Where each gear's tooth pattern stands at the contact, as a fraction of its pitch
    // (0 a tooth centre, .5 a gap). The two run opposite ways along the contact, so tooth
    // meets gap when the fractions sum to one half.
    const fS = ((90 / pS) % 1 + 1) % 1;
    const want = ((0.5 - fS) % 1 + 1) % 1, have = ((270 / pL) % 1 + 1) % 1;
    return (have - want) * pL;
  })();

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
  const gears = svg("dv-gears");
  const [[sx, sy], [lx, ly]] = [P(G.gears[0][0], G.gears[0][1]), P(G.gears[1][0], G.gears[1][1])];
  gears.innerHTML = `<defs>${brass("dvgS", sx, sy, G.m * zS / 2)}${brass("dvgL", lx, ly, G.m * zL / 2)}
      <radialGradient id="dvhub"><stop offset="0" stop-color="#1a1209"/><stop offset="1" stop-color="#3a2a14"/></radialGradient></defs>
    <g id="dvL"><path d="${gearPath(lx, ly, zL, G.m, 5)}" fill="url(#dvgL)" fill-rule="evenodd"
      stroke="#2a1c0a" stroke-width="1.6" stroke-linejoin="round"/></g>
    <g id="dvS"><path d="${gearPath(sx, sy, zS, G.m, 0)}" fill="url(#dvgS)" fill-rule="evenodd"
      stroke="#2a1c0a" stroke-width="1.6" stroke-linejoin="round"/></g>
    <circle cx="${lx}" cy="${ly}" r="${G.m * 1.1}" fill="#6e5226" stroke="#2a1c0a" stroke-width="1.2"/>
    <circle cx="${sx}" cy="${sy}" r="${G.m * 0.9}" fill="#6e5226" stroke="#2a1c0a" stroke-width="1.2"/>`;
  el.querySelector(".dv-chamber").after(gears);
  const gS = gears.querySelector("#dvS"), gL = gears.querySelector("#dvL");
  const gradS = gears.querySelector("#dvgS"), gradL = gears.querySelector("#dvgL");

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

  // The tab (the owner's "glowing bit that pops out green"): the photograph's own piece,
  // cut out by prepare.py, under the frame so that pulled in it is inside the body. Out, it
  // glows: its face lit green (a copy of the piece through a colour matrix, screened onto
  // it), and a halo (below, outside the body) that blooms onto the brass beside it and
  // spills faintly onto whatever the device is mounted over.
  const [tbx, tby, tbw, tbh] = G.tab, TAB_TRAVEL = G.tabTravel;
  const [tx, ty] = P(tbx, tby);
  const tabSvg = svg("dv-tab");
  tabSvg.innerHTML = `<defs><filter id="dvtablit" color-interpolation-filters="sRGB">
      <feColorMatrix type="matrix" values="0.14 0.30 0.06 0 0.06  0.28 0.62 0.12 0 0.30
        0.12 0.26 0.05 0 0.05  0 0 0 1 0"/></filter></defs>
    <g class="dv-tabmove">
      <image href="textures/device-tab.png" x="${tx}" y="${ty}" width="${tbw}" height="${tbh}"
        preserveAspectRatio="none"/>
      <image class="dv-tablit" href="textures/device-tab.png" x="${tx}" y="${ty}" width="${tbw}"
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
    t: 0, mode: "idle", omega: 0, aS: 0, largeTurns: 0, nextPuff: T.PUFF_EVERY,
    halt: null, stopAt: null, leverAt: null, readyAt: null,
    lever: LEVER_UP, leverV: 0, leverTarget: LEVER_UP,
    tab: 0, tabV: 0, tabTarget: 0,                       // 0 in, 1 out
    green: 1, lampLevel: 0.5, puffs: [], seq: 0, nextTrickle: 0, log: [],
  });
  let M = fresh();

  // Each event with the model's time and, live, the wall clock (for the measured gap).
  function event(name) { M.log.push([name, Math.round(M.t), Math.round(performance.now())]); }

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
        } else {
          M.nextTrickle = M.t + T.TRICKLE * 0.6;
        }
      }
    }
    M.aS += M.omega * dt / 1000;
    M.largeTurns += M.omega * dt / 1000 / RATIO / 360;
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
    }
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
  // Where the device lives: on the book's left edge, or on a phone lying in the head bar.
  const home = el.parentElement, slot = document.getElementById("dv-slot");
  const phone = matchMedia("(max-width: 760px)");
  let turned = false;
  function place() {
    turned = phone.matches && !!slot;
    if (turned) slot.appendChild(el);
    else if (el.parentElement !== home) home.insertBefore(el, home.querySelector(".bookin"));
    draw();
  }
  phone.addEventListener("change", place);
  function draw() {
    const aL = MESH - M.aS / RATIO;                     // turned so tooth meets gap
    gS.setAttribute("transform", `rotate(${M.aS.toFixed(2)} ${sx} ${sy})`);
    gL.setAttribute("transform", `rotate(${aL.toFixed(2)} ${lx} ${ly})`);
    gradS.setAttribute("gradientTransform", `rotate(${(-M.aS).toFixed(2)} ${sx} ${sy})`);
    gradL.setAttribute("gradientTransform", `rotate(${(-aL).toFixed(2)} ${lx} ${ly})`);
    lever.setAttribute("transform", `rotate(${M.lever.toFixed(2)} ${kx} ${ky})`);
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
    el.dataset.t = Math.round(M.t);
    el.dataset.puffs = M.puffs.length;
    el.dataset.lamp = el.style.getPropertyValue("--lamp");
    const s = px(), w = G.box[0] * s;
    // The steam's path, in device widths. Upright: up the gutter, drifting left (away from
    // the story, over the side panel's margin), billowing as it rises; measured so that it
    // never reaches past the device's own right edge or the side panel's text (README).
    // Turned on a phone: a short rise (the head bar is 30px) and a drift along the device,
    // away from the world's name beside its foot.
    // Measured on the first frames of the bigger steam: a puff born at a third of its size
    // and fading as (1-u)^1.6 had lost most of its density before it had any size, so a
    // running turn showed wisps. Born at 0.6 and fading as (1-u)^0.9, it reads as steam.
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
    const say = { idle: "The engine is at rest.", running: "The engine is working.",
      waiting: "The engine is waiting on your roll.", ready: "The narrator is ready." };
    el.setAttribute("aria-label", say[M.mode]);
  }

  // --- The live loop: running only while something moves ------------------------------
  let raf = 0, last = 0, acc = 0;
  function loop(now) {
    // Up to a second of catch-up: the turn is real time, so a slow frame (or a tab in the
    // background) must not stretch the heartbeat. Capped only so a long-hidden tab does
    // not replay minutes of steam on return.
    acc += Math.min(1000, now - last); last = now;
    while (acc >= T.STEP) { step(T.STEP); acc -= T.STEP; }
    draw();
    for (const f of pending.splice(0)) if (M.t >= f.at) f.fn(); else pending.push(f);
    const moving = M.mode !== "idle" || M.omega > 0.01 || M.puffs.length
      || Math.abs(M.lever - M.leverTarget) > 0.05 || Math.abs(M.leverV) > 0.05
      || Math.abs(M.tab - M.tabTarget) > 0.002 || Math.abs(M.tabV) > 0.002;
    if (moving || pending.length) raf = requestAnimationFrame(loop); else raf = 0;
  }
  function wake() { if (!raf) { last = performance.now(); raf = requestAnimationFrame(loop); } }
  const pending = [];
  const at = (ms, fn) => pending.push({ at: M.t + ms, fn });

  const api = {
    run() { M.halt = null; M.stopAt = null; M.leverAt = null; M.readyAt = null;
            M.mode = "running"; M.leverTarget = LEVER_DOWN; M.tabTarget = 0;
            M.nextPuff = M.largeTurns + T.PUFF_EVERY; event("running"); wake(); },
    wait() { M.mode = "waiting"; M.halt = { t0: M.t, w0: M.omega, then: "wait" };
             M.stopAt = null; M.tabTarget = 0; event("waiting"); wake(); },
    // Resolves when the prose may appear: gears stopped, a heartbeat, the lever up.
    ready() {
      M.mode = "ready"; M.halt = { t0: M.t, w0: M.omega, then: "ready" }; M.stopAt = null;
      event("ready"); wake();
      return new Promise(res => {
        const check = () => {
          if (M.readyAt != null && M.t >= M.readyAt + T.PROSE_AFTER_LEVER) { res(); return; }
          at(T.STEP, check);
        };
        at(T.STEP, check);
      });
    },
    log: () => M.log.slice(),
    model: () => M,
  };
  window.Device = api;

  // --- A still frame of a scripted turn (#devicet=ms) ---------------------------------
  // The same model, advanced from rest in the same fixed steps: running from 0, the
  // narrator ready at READY_AT. Used by the frame proof in the README; never on a page
  // someone is playing.
  const q = new URLSearchParams(location.hash.slice(1));
  if (q.has("devicet")) {
    const READY_AT = Number(q.get("deviceready") || 3200), until = Number(q.get("devicet"));
    // #devicewait=ms instead: the roll is owed at that moment, and the frame shows the
    // engine waiting on it.
    const WAIT_AT = q.has("devicewait") ? Number(q.get("devicewait")) : Infinity;
    api.run();
    cancelAnimationFrame(raf); raf = 0;
    while (M.t + T.STEP <= until) {
      if (M.mode === "running" && M.t >= WAIT_AT) {
        M.mode = "waiting"; M.halt = { t0: M.t, w0: M.omega, then: "wait" }; event("waiting");
      } else if (M.mode === "running" && M.t >= READY_AT && WAIT_AT === Infinity) {
        M.mode = "ready"; M.halt = { t0: M.t, w0: M.omega, then: "ready" }; event("ready");
      }
      step(T.STEP);
    }
    // The words the page shows at that moment, so a still frame reads as the live one.
    const stageLine = document.getElementById("stage-say");
    if (stageLine) stageLine.textContent = { running: "The engine resolves it.",
      waiting: "A roll is owed. The engine waits on your die.",
      ready: M.readyAt == null ? "The narrator is ready." : "" }[M.mode] || "";
    if (M.mode === "waiting") document.getElementById("rollpop").hidden = false;
    requestAnimationFrame(draw);
    document.documentElement.dataset.devicelog = JSON.stringify(M.log);
  } else {
    draw();
  }
  place();
})();

// --- The turn: a simulated pipeline with the app's own stages ------------------------
// Stage names and order are the real turn's (play/views.py `say`): the model plans the
// turn (GMAgent.plan_turn), the engine resolves it (`_advance`), and the narrator writes
// the beat; a roll owed stops it with `awaiting` set until the player rolls (/api/roll).
// Durations are compressed for the mock; on a local model the plan and the narration
// each take tens of seconds (README, "The engine device").
window.Turn = (function () {
  const stage = document.getElementById("stage-say");
  const owe = document.getElementById("mock-owe");
  const pop = document.getElementById("rollpop");
  const D = { PLAN: 1400, ENGINE: 900, ROLL: 700, NARRATE: 1800 };
  let busy = false;
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const say = text => { if (stage) stage.textContent = text; };
  function lock(on) {
    busy = on;
    document.body.classList.toggle("resolving", on);
    ["#say", "#continue"].forEach(s => { const b = document.querySelector(s); if (b) b.disabled = on; });
  }
  async function take(done) {
    if (busy) return false;
    lock(true);
    const D2 = window.Device;
    D2 && D2.run();
    say("Planning the turn.");
    await wait(D.PLAN);
    say("The engine resolves it.");
    await wait(D.ENGINE);
    if (owe && owe.checked) {
      D2 && D2.wait();
      say("A roll is owed. The engine waits on your die.");
      pop.hidden = false;
      const roll = pop.querySelector("button");
      roll.focus();
      await new Promise(r => roll.addEventListener("click", r, { once: true }));
      pop.hidden = true;
      D2 && D2.run();
      say("The engine resolves the roll.");
      await wait(D.ROLL);
    }
    say("The narrator writes.");
    await wait(D.NARRATE);
    say("The narrator is ready.");
    if (D2) await D2.ready();
    done();
    say("");
    lock(false);
    return true;
  }
  return { take, get busy() { return busy; } };
})();
