/* Variant e-phone-terrain-zoom: zoom and pan for both views, no library.
 *
 * HOW IT ZOOMS. By the SVG's own viewBox, not a CSS transform: the board stays vector at
 * every zoom, hit-testing needs no correction, and every data-sq and data-ref target is
 * the same element it was. The viewBox keeps the base's shape, so the board's layout is
 * D's to the pixel; a screen pixel maps to board units by one number, s = fit scale x k.
 *
 * WHAT IT REMEMBERS. A zoom factor k (1 is Fit) and the point on the BOARD at the middle
 * of the view, in squares, not in screen or SVG units. The flat board and every quarter
 * turn of the 3D board put that square somewhere different on screen; keeping the square
 * is what lets a turn, or Flat to 3D, keep looking at the same place (Scene3D.toBoard and
 * toUser do the 3D arithmetic). A new place, or the worst case, starts again at Fit.
 *
 * INPUTS, and what each hands back (apple-design: track 1:1, start from where things are,
 * never lock out the next input):
 *   - pinch: the midpoint stays under the fingers and the two-finger drag pans, both in
 *     the same move, so zoom and pan are one gesture as on a phone's map;
 *   - one finger or the mouse, once zoomed: pans after 8 px of movement (the slop that
 *     keeps a tap a tap); a pan that ran is never also a click on a square;
 *   - release: the pan carries on at the finger's speed and decays (Apple's 0.998 per ms
 *     projection), and any new touch, wheel or key stops it where it is;
 *   - ctrl + wheel, and a trackpad pinch (which browsers send as ctrl + wheel): zoom at
 *     the pointer, continuously;
 *   - plain wheel or two-finger trackpad scroll: pans, and ONLY while there is somewhere
 *     to pan to. At Fit, or against an edge, the event is left alone, so the page scrolls
 *     as it would without the board. Zooming on a plain wheel (the map-site habit) was
 *     refused: in the game the board sits in a page, and a wheel that zooms is a page
 *     that cannot be scrolled past the board;
 *   - buttons +, minus, Fit and You, and the keys + - 0 (and arrows to pan) while focus
 *     is on the board: the one place with an eased step, 180 ms, because a press is a
 *     single event and a jump would lose the eye; reduced motion makes it a jump.
 * LIMITS. Fit at the bottom; at the top, a square about 72 px across, where a token's
 * letters are large and nothing is yet absurd. Pan stops at the board's edge plus a
 * small margin, so the edge squares can be brought clear of the zoom buttons.
 */
const PVZoom = (function () {
  "use strict";
  const CELL = 18, SLOP = 8, MARGIN = 44, MAX_CELL_PX = 72, READ_CELL_PX = 40;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  const Z = { k: 1, b: null, sig: "", base: null, svg: null, view: null, pc: null,
              raf: 0, suppress: false };

  const is3d = () => typeof MAP_3D !== "undefined" && MAP_3D;
  const turn = () => (typeof MAP_TURN !== "undefined" ? MAP_TURN : 0);
  const toUser = b => is3d() ? Scene3D.toUser(b[0], b[1], turn()) : [b[0] * CELL, b[1] * CELL];
  const toBoard = (u, v) => is3d() ? Scene3D.toBoard(u, v, turn()) : [u / CELL, v / CELL];
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

  // --- geometry --------------------------------------------------------------------------
  function box() {
    const r = Z.svg.getBoundingClientRect();
    return { W: r.width, H: r.height, left: r.left, top: r.top };
  }
  function sFit(bx) { return Math.min(bx.W / Z.base[2], bx.H / Z.base[3]); }
  function kMax(bx) { return Math.max(2, MAX_CELL_PX / (sFit(bx) * CELL)); }
  function centre() {
    const b = Z.base;
    return Z.b ? toUser(Z.b) : [b[0] + b[2] / 2, b[1] + b[3] / 2];
  }
  // One axis of the clamp: the whole board centred when it fits, otherwise the view may
  // not leave the board (plus MARGIN screen px).
  function axis(c, x0, w0, half, m) {
    if (2 * half >= w0 + 2 * m) return x0 + w0 / 2;
    return clamp(c, x0 - m + half, x0 + w0 + m - half);
  }
  // Set the view to zoom k about the user point (cu, cv), clamped, and draw it. Returns
  // whether the centre moved, which is how a pan knows it has hit an edge.
  function set(k, cu, cv) {
    if (!Z.svg || !Z.svg.isConnected) return false;
    const bx = box();
    if (!bx.W || !bx.H) return false;
    const before = centre();
    Z.k = clamp(k, 1, kMax(bx));
    if (Z.k < 1.001) { Z.k = 1; Z.b = null; }
    const s = sFit(bx) * Z.k, hw = bx.W / (2 * s), hh = bx.H / (2 * s), m = MARGIN / s;
    const b = Z.base;
    if (Z.b !== null || Z.k > 1) {
      const u = axis(cu, b[0], b[2], hw, m), v = axis(cv, b[1], b[3], hh, m);
      Z.b = Z.k > 1 ? toBoard(u, v) : null;
    }
    const [u, v] = centre();
    // The viewBox keeps the base's shape and `meet` centres it; what shows past its sides
    // is the rest of the board, because an outer svg clips to its box, not its viewBox.
    // Giving it the element's shape instead fed back into layout: the board's height is
    // partly its content's, and in a fresh render it settled 80px shorter than D's.
    const vw = b[2] / Z.k, vh = b[3] / Z.k;
    Z.svg.setAttribute("viewBox", `${(u - vw / 2).toFixed(2)} ${(v - vh / 2).toFixed(2)} ${vw.toFixed(2)} ${vh.toFixed(2)}`);
    Z.view.classList.toggle("is-zoomed", Z.k > 1);
    const btn = n => Z.view.querySelector(`[data-pvz="${n}"]`);
    if (btn("in")) {
      btn("in").disabled = Z.k >= kMax(bx) - 1e-3;
      btn("out").disabled = btn("fit").disabled = Z.k === 1;
    }
    return Math.abs(u - before[0]) + Math.abs(v - before[1]) > 1e-3;
  }
  function apply() { const c = centre(); set(Z.k, c[0], c[1]); }

  // Screen point (px from the board's top-left) to SVG units, through the live viewBox.
  function userAt(px, py) {
    const bx = box(), s = sFit(bx) * Z.k, c = centre();
    return [c[0] - bx.W / (2 * s) + px / s, c[1] - bx.H / (2 * s) + py / s, s];
  }
  // Zoom by f with the board point under (px, py) staying under it.
  function zoomAt(f, px, py) {
    const bx = box(), [u, v, s] = userAt(px, py);
    const k2 = clamp(Z.k * f, 1, kMax(bx)), s2 = sFit(bx) * k2;
    return set(k2, u - px / s2 + bx.W / (2 * s2), v - py / s2 + bx.H / (2 * s2));
  }
  // Pan by a screen distance: the board follows the finger.
  function panBy(dx, dy) {
    if (Z.k === 1) return false;
    const s = sFit(box()) * Z.k, c = centre();
    return set(Z.k, c[0] - dx / s, c[1] - dy / s);
  }

  // --- the eased step (buttons and keys only) --------------------------------------------
  function stop() { if (Z.raf) cancelAnimationFrame(Z.raf); Z.raf = 0; }
  function step(k2, c2) {
    stop();
    const bx = box();
    k2 = clamp(k2, 1, kMax(bx));
    if (!c2) c2 = k2 === 1 ? [Z.base[0] + Z.base[2] / 2, Z.base[1] + Z.base[3] / 2] : centre();
    if (reduce.matches) { set(k2, c2[0], c2[1]); return; }
    // From where the view IS, so a second press mid-step carries on rather than jumping.
    const k1 = Z.k, c1 = centre(), t0 = performance.now(), T = 180;
    const tick = now => {
      const t = Math.min(1, (now - t0) / T), e = 1 - Math.pow(1 - t, 3);
      // k in log space: equal steps of time are equal steps of magnification.
      set(k1 * Math.pow(k2 / k1, e), c1[0] + (c2[0] - c1[0]) * e, c1[1] + (c2[1] - c1[1]) * e);
      Z.raf = t < 1 ? requestAnimationFrame(tick) : 0;
    };
    Z.raf = requestAnimationFrame(tick);
  }
  function youAt() {
    const pc = Z.pc;
    if (!pc) return null;
    const n = pc.squares || 1;
    return toUser([pc.at[0] + n / 2, pc.at[1] + n / 2]);
  }
  function command(what) {
    const bx = box();
    if (what === "in") step(Z.k * 1.6);
    else if (what === "out") step(Z.k / 1.6);
    else if (what === "fit") step(1);
    else if (what === "me" && youAt())
      step(Math.max(Z.k, Math.min(kMax(bx), READ_CELL_PX / (sFit(bx) * CELL))), youAt());
  }

  // --- mount, once per renderMap ---------------------------------------------------------
  function mount(g, scene) {
    Z.view = document.querySelector("#mapwrap .boardview");
    Z.svg = Z.view && Z.view.querySelector("svg");
    if (!Z.svg) return;
    stop();
    Z.base = Z.svg.getAttribute("viewBox").trim().split(/[\s,]+/).map(Number);
    const sig = `${g.place}|${g.width}x${g.height}|${typeof PV !== "undefined" && PV.worst}`;
    if (sig !== Z.sig) {
      Z.sig = sig; Z.k = 1; Z.b = null;
      // ?pvz=k,col,row opens the panel zoomed there: for linking a comparison, the way the
      // harness keeps its other settings in the address.
      const q = new URLSearchParams(location.search).get("pvz");
      const v = q ? q.split(",").map(Number) : [];
      if (v.length === 3 && v.every(isFinite) && v[0] > 1) { Z.k = v[0]; Z.b = [v[1], v[2]]; }
    }
    Z.pc = (scene.actors || []).find(a => a.at && (a.stance === "pc" || a.is_pc)) || null;
    Z.view.tabIndex = 0;
    Z.view.setAttribute("aria-label", "The board. Plus and minus zoom, 0 fits it, arrows pan.");
    Z.view.insertAdjacentHTML("beforeend", `<div class="pvz" role="group" aria-label="Zoom">
      <button type="button" class="v2-btn" data-pvz="in" aria-label="Zoom in" title="Zoom in (+)">+</button>
      <button type="button" class="v2-btn" data-pvz="out" aria-label="Zoom out" title="Zoom out (minus)">&minus;</button>
      <button type="button" class="v2-btn" data-pvz="fit" aria-label="Fit the whole board" title="Fit the whole board (0)">Fit</button>
      <button type="button" class="v2-btn" data-pvz="me" aria-label="Centre on you" title="Centre on you"${Z.pc ? "" : " disabled"}>You</button>
    </div>`);
    apply();
  }

  // --- pointers: tap, pan, pinch, momentum ------------------------------------------------
  const P = new Map();            // pointerId -> [x, y]
  let G = null;                   // the gesture: { panning, mid, dist, trail }
  const mid = () => { const v = [...P.values()]; return v.length > 1
    ? [(v[0][0] + v[1][0]) / 2, (v[0][1] + v[1][1]) / 2, Math.hypot(v[0][0] - v[1][0], v[0][1] - v[1][1])]
    : [v[0][0], v[0][1], 0]; };
  const onBoard = e => Z.view && Z.view.isConnected && e.target.closest &&
    e.target.closest("#mapwrap .boardview") && !e.target.closest(".pvz");

  document.addEventListener("pointerdown", e => {
    Z.suppress = false;
    if (!onBoard(e) || (e.pointerType === "mouse" && e.button !== 0)) return;
    stop();
    P.set(e.pointerId, [e.clientX, e.clientY]);
    const m = mid();
    G = { panning: P.size > 1, start: [e.clientX, e.clientY], mid: m, trail: [] };
  });
  document.addEventListener("pointermove", e => {
    if (!G || !P.has(e.pointerId)) return;
    P.set(e.pointerId, [e.clientX, e.clientY]);
    const m = mid();
    if (!G.panning) {
      // One pointer: a pan only once it has moved past the slop, and only when zoomed;
      // until then it may still be a tap.
      if (Z.k === 1 || Math.hypot(e.clientX - G.start[0], e.clientY - G.start[1]) < SLOP) return;
      G.panning = true;
      G.mid = m;
    }
    try { Z.view.setPointerCapture(e.pointerId); } catch (err) { /* already released */ }
    const bx = box();
    if (P.size > 1 && G.mid[2] && m[2]) zoomAt(m[2] / G.mid[2], m[0] - bx.left, m[1] - bx.top);
    panBy(m[0] - G.mid[0], m[1] - G.mid[1]);
    G.mid = m;
    const now = performance.now();
    G.trail.push([now, m[0], m[1]]);
    while (G.trail.length > 2 && now - G.trail[0][0] > 90) G.trail.shift();
    Z.suppress = true;
  });
  function end(e) {
    if (!P.has(e.pointerId)) return;
    P.delete(e.pointerId);
    if (!G) return;
    if (P.size) { G.mid = mid(); G.trail = []; return; }   // pinch to one finger: carry on
    const tr = G.trail, panned = G.panning;
    G = null;
    if (!panned || reduce.matches || tr.length < 2 || performance.now() - tr[tr.length - 1][0] > 60) return;
    // Release velocity from the last 90 ms, then glide: the finger's speed handed on.
    const a = tr[0], b = tr[tr.length - 1], dt = Math.max(8, b[0] - a[0]);
    let vx = (b[1] - a[1]) / dt, vy = (b[2] - a[2]) / dt, last = performance.now();
    if (Math.hypot(vx, vy) < 0.25) return;
    const glide = now => {
      const d = now - last; last = now;
      const moved = panBy(vx * d, vy * d);
      const f = Math.pow(0.998, d); vx *= f; vy *= f;
      Z.raf = moved && Math.hypot(vx, vy) > 0.02 ? requestAnimationFrame(glide) : 0;
    };
    Z.raf = requestAnimationFrame(glide);
  }
  document.addEventListener("pointerup", end);
  document.addEventListener("pointercancel", end);
  // A pan or pinch that ran is never also a tap on whatever square it ended over.
  document.addEventListener("click", e => {
    if (Z.suppress && e.target.closest && e.target.closest("#mapwrap")) {
      e.stopPropagation(); e.preventDefault();
    }
    Z.suppress = false;
  }, true);

  // --- wheel -------------------------------------------------------------------------------
  document.addEventListener("wheel", e => {
    if (!onBoard(e)) return;
    const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1;
    const bx = box();
    if (e.ctrlKey) {
      e.preventDefault();
      stop();
      zoomAt(Math.exp(clamp(-e.deltaY * unit * 0.0045, -0.7, 0.7)), e.clientX - bx.left, e.clientY - bx.top);
      return;
    }
    // Plain wheel: pan while there is room; otherwise it is the page's.
    if (Z.k > 1) {
      stop();
      if (panBy(-e.deltaX * unit, -e.deltaY * unit)) e.preventDefault();
    }
  }, { passive: false });

  // --- keys and buttons ----------------------------------------------------------------------
  document.addEventListener("keydown", e => {
    // A touch pan fires no click, so its guard would otherwise wait for the next click,
    // and Enter on a zoom button is one.
    Z.suppress = false;
    if (e.ctrlKey || e.metaKey || e.altKey || !Z.view || !e.target.closest ||
        !e.target.closest("#mapwrap .boardview")) return;
    const bx = Z.svg && box(), pan = bx ? Math.min(bx.W, bx.H) * 0.2 : 0;
    const keys = { "+": () => command("in"), "=": () => command("in"),
                   "-": () => command("out"), "_": () => command("out"), "0": () => command("fit"),
                   ArrowLeft: () => (stop(), panBy(pan, 0)), ArrowRight: () => (stop(), panBy(-pan, 0)),
                   ArrowUp: () => (stop(), panBy(0, pan)), ArrowDown: () => (stop(), panBy(0, -pan)) };
    if (!keys[e.key] || (e.key.startsWith("Arrow") && Z.k === 1)) return;
    e.preventDefault();
    keys[e.key]();
  });
  document.addEventListener("click", e => {
    const b = e.target.closest && e.target.closest("[data-pvz]");
    if (b && !b.disabled) command(b.dataset.pvz);
  });
  // The board's box changes with the window (and the phone's URL bar): keep the view.
  if (typeof ResizeObserver === "function")
    new ResizeObserver(() => { if (Z.svg && Z.svg.isConnected) apply(); })
      .observe(document.getElementById("mapwrap") || document.body);

  return { mount, get k() { return Z.k; }, get board() { return Z.b; }, command };
})();
