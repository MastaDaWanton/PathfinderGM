/* Zoom and pan for the ground board, both views, no library (2026-11-12).
 *
 * The owner, 2026-11-12: "yes build zoom and middle mouse pan", asked with the board's cap
 * lifted outside town interiors (rules/floorplan.py MAX_SQUARES), so a street or a square
 * can be far more than 24 squares across. Ported from the polish mocks' variant E
 * (docs/mock/polish/variants/e-phone-terrain-zoom/zoom.js on mock/polish), which the owner
 * saw on 2026-11-11, with the inputs changed to the owner's ask:
 *
 *   - the WHEEL zooms at the pointer. Variant E zoomed only on ctrl + wheel and refused a
 *     plain wheel, so the page could still be scrolled past the board; the owner asked for
 *     the map-site habit instead. Kept from E's reason: at Fit, a wheel that would zoom
 *     OUT is left to the page, so the page still scrolls;
 *   - the MIDDLE button drags the board while zoomed (and never starts the browser's
 *     autoscroll there); the left button or one finger pans too, after 8 px of movement,
 *     so a tap is still a tap on a square;
 *   - pinch zooms and pans on a touch screen; buttons +, minus, Fit and You, and the keys
 *     + - 0 and the arrows while the board has focus.
 *
 * HOW. By the SVG's own viewBox, not a CSS transform: the board stays vector, hit-testing
 * needs no correction and every data-sq / data-ref target is the element it was. The view
 * remembers a zoom factor k (1 is Fit) and the point ON THE BOARD at its middle, in squares,
 * so a quarter-turn or Flat to 3D keeps looking at the same place (Scene3D.toBoard/toUser).
 * A new place starts again at Fit.
 *
 * The flat board's coordinate letters and numbers stay pinned to the edge of the view while
 * zoomed, at their own size, so "L9" can still be read off a board scrolled to its middle.
 */
// `var`, not `const`: `typeof MapZoom` in renderMap must never meet a binding not yet made.
var MapZoom = (function () {
  "use strict";
  const CELL = 18, SLOP = 8, MARGIN = 44, MAX_CELL_PX = 72, READ_CELL_PX = 40;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  const Z = { k: 1, b: null, sig: "", mode: "", base: null, svg: null, view: null, pc: null,
              raf: 0, suppress: false, tw: 0 };

  const is3d = () => typeof MAP_3D !== "undefined" && MAP_3D;
  const turn = () => (typeof MAP_TURN !== "undefined" ? MAP_TURN : 0);
  // A flat board drawn transposed (flatTurned in 03, `data-turned`, kept in Z.tw): board
  // (x, y) is drawn at (y, x).
  const toUser = b => is3d() ? Scene3D.toUser(b[0], b[1], turn())
    : Z.tw ? [b[1] * CELL, b[0] * CELL] : [b[0] * CELL, b[1] * CELL];
  const toBoard = (u, v) => is3d() ? Scene3D.toBoard(u, v, turn())
    : Z.tw ? [v / CELL, u / CELL] : [u / CELL, v / CELL];
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
    const vw = b[2] / Z.k, vh = b[3] / Z.k;
    Z.svg.setAttribute("viewBox", `${(u - vw / 2).toFixed(2)} ${(v - vh / 2).toFixed(2)} ${vw.toFixed(2)} ${vh.toFixed(2)}`);
    Z.view.classList.toggle("is-zoomed", Z.k > 1);
    pin(u - bx.W / (2 * s), v - bx.H / (2 * s));
    const btn = n => Z.view.querySelector(`[data-mapzoom="${n}"]`);
    if (btn("in")) {
      btn("in").disabled = Z.k >= kMax(bx) - 1e-3;
      btn("out").disabled = btn("fit").disabled = Z.k === 1;
    }
    return Math.abs(u - before[0]) + Math.abs(v - before[1]) > 1e-3;
  }
  function apply() { const c = centre(); set(Z.k, c[0], c[1]); }

  // Where a long board (2 : 1 or more in squares) opens: filling the box, its short way
  // across, rather than fitted whole inside it. Measured 2026-11-13: a ship's deck (6 x 17
  // with its sea) in a 692 x 245 board box, 3D, fitted into 341 x 245 with its hull a thin
  // diagonal, because an isometric board is as wide as it is long whichever way it is
  // turned; filled, it is 692 wide. A flat one is transposed instead (flatTurned in 03), so
  // this is near 1 there. Any other board opens at Fit, as before.
  function opening(g) {
    const long = Math.max(g.width, g.height), short = Math.min(g.width, g.height);
    const bx = box();
    if (!short || long < 2 * short || !bx.W || !bx.H) return 1;
    const sx = bx.W / Z.base[2], sy = bx.H / Z.base[3];
    const fill = Math.max(sx, sy) / Math.min(sx, sy);
    return fill < 1.25 ? 1 : Math.min(kMax(bx), fill);
  }

  // The flat board's letters across and numbers down (03-offers-and-map.js), kept at the
  // view's top and left edges and at their Fit size while zoomed. (x0, y0) is the view's
  // top-left corner in board units.
  function pin(x0, y0) {
    if (is3d()) return;
    const k = Z.k;
    Z.svg.querySelectorAll("text.coord").forEach(t => {
      if (!t.dataset.x) { t.dataset.x = t.getAttribute("x"); t.dataset.y = t.getAttribute("y"); }
      const col = t.classList.contains("col");
      t.style.fontSize = k > 1 ? `${8.5 / k}px` : "";
      // A transposed board (Z.tw) has its letters down the left and its numbers across the
      // top: a letter's own y is drawn as x, a number's x as y, so each pins to the other
      // edge (the letter's baseline sits 3 units under its middle).
      if (Z.tw) {
        if (col) t.setAttribute("y", k > 1 ? Math.max(Number(t.dataset.y), x0 + 11 / k) : t.dataset.y);
        else t.setAttribute("x", k > 1 ? Math.max(Number(t.dataset.x), y0 + 6 / k) : t.dataset.x);
      } else if (col) t.setAttribute("y", k > 1 ? Math.max(Number(t.dataset.y), y0 + 9 / k) : t.dataset.y);
      else t.setAttribute("x", k > 1 ? Math.max(Number(t.dataset.x), x0 + 8 / k) : t.dataset.x);
      t.classList.toggle("pinned", k > 1);
      // Over the tokens once pinned, or a figure at the edge hides the name of its row. In
      // its own group, so a transposed board's label stays transposed.
      if (k > 1 && t.nextSibling) t.parentNode.appendChild(t);
    });
  }

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
  // Pan by a screen distance: the board follows the hand.
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
    if (!Z.svg || !Z.svg.isConnected) return;
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
    Z.tw = Number(Z.svg.dataset.turned) || 0;
    const sig = `${g.place}|${g.width}x${g.height}`, mode = is3d() ? "3d" : "flat";
    if (sig !== Z.sig) { Z.sig = sig; Z.k = Z.opened = 1; Z.b = null; Z.mode = ""; }
    // A view shown at the zoom it opened at (or Fit) opens at its own opening zoom; one the
    // player zoomed keeps looking where it was (Flat to 3D), and Fit still shows it whole.
    if (mode !== Z.mode) {
      if (Z.k === 1 || Z.k === Z.opened) { Z.k = Z.opened = opening(g); Z.b = null; }
      Z.mode = mode;
    }
    Z.pc = (scene.actors || []).find(a => a.at && a.stance === "pc") || null;
    Z.view.tabIndex = 0;
    Z.view.setAttribute("aria-label",
      "The board. The wheel or plus and minus zoom, 0 fits it, the middle button or arrows pan.");
    Z.view.insertAdjacentHTML("beforeend", `<div class="mapzoom" role="group" aria-label="Zoom">
      <button type="button" class="v2-btn" data-mapzoom="in" aria-label="Zoom in" title="Zoom in (wheel, +)">+</button>
      <button type="button" class="v2-btn" data-mapzoom="out" aria-label="Zoom out" title="Zoom out (wheel, minus)">&minus;</button>
      <button type="button" class="v2-btn" data-mapzoom="fit" aria-label="Fit the whole board" title="Fit the whole board (0)">Fit</button>
      <button type="button" class="v2-btn" data-mapzoom="me" aria-label="Centre on you" title="Centre on you"${Z.pc ? "" : " disabled"}>You</button>
    </div>`);
    apply();
  }

  // --- pointers: tap, pan, pinch, momentum ------------------------------------------------
  const P = new Map();            // pointerId -> [x, y]
  let G = null;                   // the gesture: { panning, mid, trail, start }
  const mid = () => { const v = [...P.values()]; return v.length > 1
    ? [(v[0][0] + v[1][0]) / 2, (v[0][1] + v[1][1]) / 2, Math.hypot(v[0][0] - v[1][0], v[0][1] - v[1][1])]
    : [v[0][0], v[0][1], 0]; };
  const onBoard = e => Z.view && Z.view.isConnected && e.target.closest &&
    e.target.closest("#mapwrap .boardview") && !e.target.closest(".mapzoom");

  document.addEventListener("pointerdown", e => {
    Z.suppress = false;
    if (!onBoard(e) || (e.pointerType === "mouse" && e.button !== 0 && e.button !== 1)) return;
    // The middle button: the board's own drag, never the browser's autoscroll over it.
    const middle = e.pointerType === "mouse" && e.button === 1;
    if (middle) e.preventDefault();
    stop();
    P.set(e.pointerId, [e.clientX, e.clientY]);
    G = { panning: P.size > 1 || middle, start: [e.clientX, e.clientY], mid: mid(), trail: [] };
  });
  // Chrome starts autoscroll on mousedown, not pointerdown.
  document.addEventListener("mousedown", e => { if (e.button === 1 && onBoard(e)) e.preventDefault(); });
  document.addEventListener("auxclick", e => { if (e.button === 1 && onBoard(e)) e.preventDefault(); });
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
    if (Math.hypot(e.clientX - G.start[0], e.clientY - G.start[1]) >= SLOP) Z.suppress = true;
  });
  function end(e) {
    if (!P.has(e.pointerId)) return;
    P.delete(e.pointerId);
    if (!G) return;
    if (P.size) { G.mid = mid(); G.trail = []; return; }   // pinch to one finger: carry on
    const tr = G.trail, panned = G.panning;
    G = null;
    if (!panned || reduce.matches || tr.length < 2 || performance.now() - tr[tr.length - 1][0] > 60) return;
    // Release velocity from the last 90 ms, then glide: the hand's speed handed on.
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
  // A pan or pinch that ran is never also a click on whatever square it ended over.
  document.addEventListener("click", e => {
    if (Z.suppress && e.target.closest && e.target.closest("#mapwrap")) {
      e.stopPropagation(); e.preventDefault();
    }
    Z.suppress = false;
  }, true);

  // --- wheel -------------------------------------------------------------------------------
  document.addEventListener("wheel", e => {
    if (!onBoard(e) || !Z.svg || !Z.svg.isConnected) return;
    const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1;
    // At Fit, scrolling down is the page's: there is nothing further out to zoom to.
    if (Z.k === 1 && e.deltaY >= 0) return;
    e.preventDefault();
    stop();
    const bx = box();
    zoomAt(Math.exp(clamp(-e.deltaY * unit * 0.0025, -0.5, 0.5)), e.clientX - bx.left, e.clientY - bx.top);
  }, { passive: false });

  // --- keys and buttons ----------------------------------------------------------------------
  document.addEventListener("keydown", e => {
    Z.suppress = false;
    if (e.ctrlKey || e.metaKey || e.altKey || !Z.view || !e.target.closest ||
        !e.target.closest("#mapwrap .boardview")) return;
    const bx = Z.svg && Z.svg.isConnected && box(), pan = bx ? Math.min(bx.W, bx.H) * 0.2 : 0;
    const keys = { "+": () => command("in"), "=": () => command("in"),
                   "-": () => command("out"), "_": () => command("out"), "0": () => command("fit"),
                   ArrowLeft: () => (stop(), panBy(pan, 0)), ArrowRight: () => (stop(), panBy(-pan, 0)),
                   ArrowUp: () => (stop(), panBy(0, pan)), ArrowDown: () => (stop(), panBy(0, -pan)) };
    if (!keys[e.key] || (e.key.startsWith("Arrow") && Z.k === 1)) return;
    e.preventDefault();
    keys[e.key]();
  });
  document.addEventListener("click", e => {
    const b = e.target.closest && e.target.closest("[data-mapzoom]");
    if (b && !b.disabled) command(b.dataset.mapzoom);
  });
  // The board's box changes with the window: keep the view where it was.
  if (typeof ResizeObserver === "function")
    new ResizeObserver(() => { if (Z.svg && Z.svg.isConnected) apply(); })
      .observe(document.getElementById("mapwrap") || document.body);

  return { mount, command, get k() { return Z.k; }, get board() { return Z.b; } };
})();
