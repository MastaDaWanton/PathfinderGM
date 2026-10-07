/* The alchemy bench's stage, part 1: the apparatus round the glass.
 *
 * UI plan §6.3. THE FIELD KIT (common and uncommon work) unrolls on the ground: an iron
 * tripod over a SPIRIT LAMP (a blue-yellow flame, the scene's key light), a crucible, a
 * round-bottom flask, a mortar, a cloth filter in a funnel and a rack of four vials, on a
 * leather roll. THE LABORATORY (rare and up) is a workbench of dark planks: the ATHANOR, a
 * brick furnace with its tower, whose coals are the key light; the alembic on it; a retort in
 * a sand bath; a bain-marie pot; shelves of jars on the wall behind; and a FUME HOOD over the
 * athanor, because the hood is what protects against toxic work (plan §8.4), so it is seen.
 *
 * Built in code from the herb kit's primitives (bench-stage/02-meshes.js) with the forge's
 * node helpers and its SWEEP (forge-stage/01-props.js, both as they are): the alembic's beak
 * and the retort's neck are a circle carried along a curve, which a lathe cannot make.
 *
 * THE FLAMES ARE NOT LIGHTS. As at the circle, each flame is an unlit additive mesh and a
 * halo; the stage spends the shader's one key light on the lamp or the coals as a whole.
 * Nothing here keeps time: setHeat(k) poses a flame for a heat 0 (out) .. 1.3 (roaring), and
 * the adapter (table/52-alchemy-stage.js) decides when.
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var F = window.ForgeStageKit || {};
  var A = window.AlchemyStageKit = window.AlchemyStageKit || {};
  var G = K.mesh, M = K.math, FP = F.props, FG = F.geo, GL = A.glass;
  if (!G || !M || !FP || !FG || !GL) return;
  var TAU = Math.PI * 2;
  var node = FP.node, add = FP.add, group = FP.group, once = GL.once, mat = GL.mat;

  function weld(parts) { return FG.weld(parts); }

  /* --- the field kit ----------------------------------------------------------------------- */

  /* An iron tripod: three splayed legs and a ring the round-bottom glass sits in. `ring` is
     the height of the ring's top. */
  function tripod(ring) {
    var g = group(), parts = [];
    for (var i = 0; i < 3; i++) {
      var a = i / 3 * TAU + 0.5;
      // Each leg leans in, so the feet stand wider than the ring (a z-roll tips +y toward -x,
      // an x-pitch tips it toward +z).
      parts.push([G.cylinder(0.006, ring + 0.01, 6), [Math.cos(a) * 0.12, 0, Math.sin(a) * 0.12], [-Math.sin(a) * 0.22, 0, Math.cos(a) * 0.22]]);
    }
    add(g, node(once("tripod-legs:" + ring.toFixed(3), function () { return weld(parts); }), FP.mat("iron")));
    add(g, node(once("tripod-ring", function () { return G.ring(0.07, 0.006, 40, 6); }), FP.mat("iron"), { pos: [0, ring - 0.006, 0] }));
    add(g, GL.shadow(0.14));
    return { root: g, top: ring };
  }

  /* The flame shape: a few tongues, an inner core and an outer sheath, posed by setHeat. */
  function flame(parent, at, size, blue) {
    var shape = once("tongue", function () {
      return G.lathe([[0, 0], [0.012, 0.008], [0.014, 0.026], [0.008, 0.05], [0.003, 0.07], [0, 0.078]], 10, 70);
    });
    var outer = FP.mat("flame", { color: [1.0, 0.72, 0.34], alpha: 0.4 });
    var core = FP.mat("flame", { color: [0.36, 0.55, 1.0], alpha: 0.6 });
    var halo = FP.mat("glow", { color: [1.0, 0.7, 0.36], alpha: 0.2 });
    var spots = [[0, 0, 1], [0.008, 0.006, 0.7], [-0.007, -0.006, 0.75]];
    var nodes = spots.map(function (s, i) {
      return add(parent, node(shape, outer, { pos: [at[0] + s[0] * size, at[1], at[2] + s[1] * size],
                                             rot: [0, i * 1.7, 0], glint: false, base: s[2] * size }));
    });
    var c = add(parent, node(shape, core, { pos: at.slice(), glint: false, base: 0.45 * size }));
    var h = add(parent, node(once("halo-disc", function () { return G.disc(0.12, 24); }), halo, { pos: [at[0], at[1] + 0.04 * size, at[2]], glint: false }));
    h.noFit = true;
    return {
      nodes: nodes, halo: h,
      set: function (k, flick) {
        k = Math.max(0, Math.min(1.3, +k || 0));
        var f = flick || 1, on = k > 0.01;
        // A spirit lamp burns pale blue at its root and yellow at its tips; a low flame is
        // nearly all blue, a high one mostly yellow.
        outer.color = M.lerp3(blue ? [0.55, 0.62, 1.0] : [1.0, 0.5, 0.18], [1.0, 0.76, 0.38], Math.min(1, k));
        outer.alpha = (0.12 + 0.4 * k) * (on ? 1 : 0);
        core.alpha = (blue ? 0.55 : 0.25) * (on ? 1 : 0);
        halo.alpha = (0.05 + 0.22 * k) * f * (on ? 1 : 0);
        nodes.forEach(function (n, i) {
          var hh = n.base * (0.35 + 0.95 * k) * (i ? f : 1 + (f - 1) * 0.6);
          n.scl = [n.base * (0.8 + 0.3 * k), Math.max(0.001, hh), n.base * (0.8 + 0.3 * k)];
          n.visible = on;
        });
        c.scl = [c.base, Math.max(0.001, c.base * (0.6 + 0.5 * k)), c.base];
        c.visible = on;
        h.visible = on;
      }
    };
  }

  /* The spirit lamp: a squat glass reservoir of spirit, a brass collar and a wick, its flame
     at `fire`. */
  function spiritLamp() {
    var g = group();
    var body = [[0, 0], [0.045, 0], [0.05, 0.02], [0.046, 0.045], [0.02, 0.06], [0.016, 0.07]];
    add(g, node(once("lamp-glass", function () { return G.lathe(GL.wall(body, 0.003), 20, 40); }), mat("glass", { alpha: 0.2 })));
    var spirit = mat("liquid", { color: [0.55, 0.6, 0.62], alpha: 0.3, surf: [0.7, 0.74, 0.76] });
    var sp = add(g, node(once("lamp-spirit", function () { return G.lathe(GL.liquidProfile(body, 0.003), 20, 40); }), spirit));
    sp.liquid = { lo: 0.004, hi: 0.04, level: 0.7 };
    add(g, node(once("lamp-collar", function () { return G.cylinder(0.019, 0.012, 12); }), FP.mat("brass"), { pos: [0, 0.066, 0] }));
    add(g, node(once("lamp-wick", function () { return G.cylinder(0.004, 0.012, 6); }), FP.mat("soot"), { pos: [0, 0.078, 0] }));
    add(g, GL.shadow(0.08));
    var fl = flame(g, [0, 0.088, 0], 1, true);
    return { root: g, flame: fl, fire: [0, 0.12, 0] };
  }

  /* A funnel with a folded cloth in it, its stem down into the vessel below. */
  function funnel() {
    var g = group();
    var cone = [[0.009, -0.06], [0.009, 0], [0.065, 0.07], [0.07, 0.074]];
    add(g, node(once("funnel", function () { return G.lathe(cone, 24, 30); }), mat("glass", { alpha: 0.16 })));
    var clothM = FP.mat("cloth", { color: [0.82, 0.78, 0.68], patScale: 4 });
    add(g, node(once("funnel-cloth", function () { return G.lathe([[0.0, 0.012], [0.056, 0.064], [0.066, 0.08]], 16, 50); }), clothM));
    return { root: g, cloth: clothM, stem: [0, -0.06, 0], top: [0, 0.07, 0] };
  }

  /* A wooden rack of four vials, each with its own small liquid. */
  function vialRack(colors) {
    var g = group();
    add(g, node(once("rack", function () {
      return weld([[G.box(0.26, 0.012, 0.07), [0, 0.012, 0]], [G.box(0.26, 0.012, 0.07), [0, 0.07, 0]],
                   [G.box(0.012, 0.09, 0.07), [-0.124, 0.045, 0]], [G.box(0.012, 0.09, 0.07), [0.124, 0.045, 0]]]);
    }), FP.mat("wood")));
    var vials = [];
    (colors || []).slice(0, 4).forEach(function (c, i) {
      var v = GL.vessel("vial");
      v.root.pos = [-0.09 + i * 0.06, 0.018, 0];
      v.root.scl = [0.9, 0.9, 0.9];
      v.liquid.mat.color = c.slice();
      v.liquid.mat.surf = M.lerp3(c, [1, 1, 1], 0.3);
      v.liquid.liquid.level = 0.45 + 0.13 * ((i * 7) % 4);
      if (v.stopper) v.stopper.visible = i !== 1;
      add(g, v.root);
      vials.push(v);
    });
    add(g, GL.shadow(0.16));
    return { root: g, vials: vials };
  }

  /* A mortar and its pestle, the alchemist's grinding stone. */
  function mortar() {
    var v = GL.vessel("mortar");
    v.liquid.visible = false;
    add(v.root, node(once("pestle", function () { return G.capsule(0.016, 0.16, 10); }), FP.mat("stone", { color: [0.5, 0.48, 0.45] }),
                     { pos: [0.02, 0.03, 0], rot: [0, 0, -0.55] }));
    return v;
  }

  /* The leather roll the kit is laid out on. */
  function roll() {
    var g = group();
    add(g, node(once("roll", function () { return G.box(1.36, 0.008, 0.8); }), FP.mat("leather", { color: [0.3, 0.19, 0.1] }), { pos: [0, 0.004, 0] }));
    add(g, node(once("roll-end", function () { return G.cylinder(0.045, 0.8, 12); }), FP.mat("leather"), { rot: [Math.PI / 2, 0, 0], pos: [0.72, 0.045, -0.4] }));
    return g;
  }

  /* --- the laboratory ---------------------------------------------------------------------- */

  /* The workbench: thick dark planks on four legs, its top at `h`. */
  function workbench(h, w, d) {
    var g = group();
    add(g, node(once("bench:" + h + ":" + w + ":" + d, function () {
      var legs = [];
      [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(function (s) {
        legs.push([G.box(0.08, h - 0.06, 0.08), [s[0] * (w / 2 - 0.08), (h - 0.06) / 2, s[1] * (d / 2 - 0.08)]]);
      });
      legs.push([G.box(w, 0.06, d), [0, h - 0.03, 0]]);
      legs.push([G.box(w - 0.2, 0.03, 0.06), [0, 0.16, 0]]);
      return weld(legs);
    }), FP.mat("darkwood", { patScale: 0.9 })));
    add(g, GL.shadow(Math.max(w, d) * 0.55));
    return g;
  }

  /* The athanor: a brick tower furnace, its arched mouth showing the coals, a sand pot on its
     top where the work sits, and its flue rising behind. setHeat(k) is 0 (banked) .. 1.3. */
  function athanor() {
    var g = group(), H = 0.36;
    add(g, node(once("athanor", function () {
      // The tower stands at the back edge. At z -0.14 its front face (-0.07) sat inside the
      // cucurbit's back wall (radius 0.106), and the live capture showed the brick cutting
      // through the glass and the liquid as an untinted orange slab.
      return weld([[G.box(0.36, H, 0.34), [0, H / 2, 0]], [G.box(0.4, 0.04, 0.38), [0, H + 0.02, 0]],
                   [G.box(0.14, 0.42, 0.12), [0, H + 0.21, -0.22]]]);
    }), FP.mat("brick")));
    // The flue is tall; leaving it out of the camera's fit keeps the work the subject.
    var flue = add(g, node(once("athanor-flue", function () { return G.box(0.12, 0.6, 0.12); }), FP.mat("brick", { color: [0.3, 0.16, 0.11] }),
                           { pos: [0, H + 0.72, -0.22] }));
    flue.noFit = true;
    var recessM = FP.mat("soot", { emit: [0.2, 0.05, 0.01] });
    add(g, node(once("athanor-mouth", function () { return G.box(0.16, 0.12, 0.06); }), recessM, { pos: [0, 0.1, 0.15] }));
    var coalM = FP.mat("coal");
    add(g, node(once("athanor-coals", function () {
      var r = M.rng(5), lump = G.sphere(0.018, 7, 5), parts = [];
      for (var i = 0; i < 14; i++) parts.push([lump, [(r() - 0.5) * 0.13, 0.05 + r() * 0.02, 0.15 + (r() - 0.5) * 0.04], [r() * 3, r() * 3, 0], [1, 0.7, 1]]);
      return weld(parts);
    }), coalM, { glint: false }));
    var glowM = FP.mat("glow", { alpha: 0.4 });
    var gl = add(g, node(once("athanor-glow", function () { return G.disc(0.14, 24); }), glowM,
                         { pos: [0, 0.11, 0.185], rot: [Math.PI / 2, 0, 0], glint: false }));
    gl.noFit = true;
    var fl = flame(g, [0, 0.06, 0.16], 0.9, false);
    // The sand pot on the top: an iron ring the glass sits in.
    add(g, node(once("athanor-pot", function () { return G.lathe([[0.1, 0], [0.11, 0.03], [0.1, 0.035], [0.09, 0.008], [0, 0.008]], 24, 40); }),
                FP.mat("iron"), { pos: [0, H + 0.04, 0] }));
    add(g, node(once("athanor-sand", function () { return G.disc(0.092, 24); }), FP.mat("clay", { color: [0.7, 0.6, 0.42], pattern: 3, patScale: 12 }),
                { pos: [0, H + 0.062, 0] }));
    function setHeat(k, flick) {
      k = Math.max(0, Math.min(1.3, +k || 0));
      coalM.emit = [0.55 * k + 0.08, 0.15 * k + 0.012, 0.025 * k];
      recessM.emit = [0.1 + 0.45 * k, 0.025 + 0.16 * k * k, 0.004 + 0.04 * k * k];
      glowM.alpha = (0.1 + 0.36 * k) * (flick || 1);
      fl.set(k, flick);
    }
    setHeat(0.5);
    return { root: g, setHeat: setHeat, top: H + 0.064, fire: [0, 0.12, 0.2] };
  }

  /* A sand bath: a shallow iron tray of sand, a retort bedded in it with its neck swept out
     over the edge (the forge's sweep). */
  function sandBath() {
    var g = group();
    add(g, node(once("sandbath", function () { return G.lathe([[0, 0], [0.15, 0], [0.16, 0.05], [0.15, 0.055], [0.14, 0.008], [0, 0.008]], 24, 40); }), FP.mat("iron")));
    add(g, node(once("sandbath-sand", function () { return G.disc(0.142, 24); }), FP.mat("clay", { color: [0.72, 0.62, 0.44], pattern: 3, patScale: 12 }),
                { pos: [0, 0.04, 0] }));
    var r = GL.vessel("retort");
    r.root.pos = [0, 0.02, 0];
    r.liquid.liquid.level = 0.5;
    r.liquid.mat.color = [0.42, 0.18, 0.1];
    r.liquid.mat.surf = [0.6, 0.32, 0.2];
    add(g, r.root);
    add(g, node(once("retort-neck", function () {
      return tube([0, 0.16, 0], [0.12, 0.2, 0.02], [0.2, 0.13, 0.03], [0.26, 0.06, 0.03], 0.016, 0.007, 14);
    }), mat("glass", { alpha: 0.14 }), { pos: [0, 0.02, 0] }));
    add(g, GL.shadow(0.2));
    return { root: g, retort: r };
  }

  /* A glass tube along a cubic curve, tapering from r0 to r1: the alembic's beak, the retort's
     neck. One sheet of glass (it is thin), built with the forge's sweep. */
  function tube(p0, p1, p2, p3, r0, r1, n) {
    n = n || 14;
    var k = 8;
    function at(t) {
      var u = 1 - t;
      return [u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
              u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1],
              u * u * u * p0[2] + 3 * u * u * t * p1[2] + 3 * u * t * t * p2[2] + t * t * t * p3[2]];
    }
    var C = [], T = [];
    for (var i = 0; i < n; i++) C.push(at(i / (n - 1)));
    for (i = 0; i < n; i++) T.push(M.norm(M.sub(C[Math.min(n - 1, i + 1)], C[Math.max(0, i - 1)])));
    var meshes = FG.sweep(n, k, function (i, j) {
      var t = T[i], ref = Math.abs(t[1]) > 0.9 ? [1, 0, 0] : [0, 1, 0];
      var nn = M.norm(M.cross(t, ref)), b = M.cross(t, nn);
      var r = r0 + (r1 - r0) * i / (n - 1), a = j / k * TAU;
      return M.add(C[i], M.add(M.scale(nn, Math.cos(a) * r), M.scale(b, Math.sin(a) * r)));
    });
    return meshes[0];
  }

  /* The alembic: the head on the cucurbit, and the beak from the head's side down into the
     receiver. `head` and `mouth` are where the head sits and where the receiver's mouth is, in
     the parent's frame. */
  function alembic(head, mouth) {
    var g = group();
    var H = GL.vessel("head");
    H.root.pos = head.slice();
    add(g, H.root);
    var from = [head[0] + 0.06, head[1] + 0.05, head[2]];
    var to = [mouth[0], mouth[1] + 0.012, mouth[2]];
    var key = "beak:" + from.concat(to).map(function (x) { return x.toFixed(3); }).join(",");
    add(g, node(once(key, function () {
      // The beak leaves the head nearly level and falls into the receiver's neck: the first
      // curve rose to a high arch and read as a wire, not a spout.
      return tube(from, [from[0] + 0.14, from[1] - 0.01, from[2]], [to[0] - 0.02, to[1] + 0.16, to[2]], to, 0.014, 0.007, 16);
    }), mat("glass", { alpha: 0.14 }), { glint: false }));
    return { root: g, head: H, drip: to, path: [from, to] };
  }

  /* Shelves of jars on the back wall, built once: a frame, and jars of a few colours. */
  function shelves() {
    var g = group();
    add(g, node(once("lab-shelf", function () {
      var parts = [];
      [0.0, 0.42, 0.84].forEach(function (y) { parts.push([G.box(1.3, 0.03, 0.24), [0, y, 0]]); });
      [-0.65, 0.65].forEach(function (x) { parts.push([G.box(0.04, 1.0, 0.24), [x, 0.42, 0]]); });
      return weld(parts);
    }), FP.mat("darkwood")));
    var r = M.rng(911), jar = once("jar", function () { return G.lathe([[0, 0], [0.04, 0], [0.045, 0.1], [0.025, 0.13], [0.028, 0.14], [0, 0.14]], 12, 50); });
    [0.015, 0.435].forEach(function (y) {
      for (var i = 0; i < 7; i++) {
        var c = [0.2 + r() * 0.45, 0.16 + r() * 0.3, 0.12 + r() * 0.3];
        add(g, node(jar, FP.mat("clay", { color: c, spec: 0.7, shin: 40 }), { pos: [-0.54 + i * 0.18 + r() * 0.03, y, 0], scl: [1, 0.7 + r() * 0.6, 1] }));
      }
    });
    return g;
  }

  /* The fume hood: a sloped timber canopy over the athanor, its flue into the dark. Left out of
     the camera's fit, as the forge's hood is: it is tall, and fitting it shrank the work. */
  function fumeHood() {
    var g = group({ noFit: true });
    add(g, node(once("hood", function () {
      return weld([[G.lathe([[0.42, 0], [0.12, 0.36]], 4, 10), [0, 0, 0], [0, Math.PI / 4, 0], [1, 1, 0.8]],
                   [G.box(0.16, 0.9, 0.16), [0, 0.8, -0.04]]]);
    }), FP.mat("darkwood", { color: [0.24, 0.15, 0.09] }), { noFit: true }));
    return g;
  }

  /* A window in the back wall: its pane is the day's light, an emissive card, and its mullions
     wood. setLight(c) colours the pane. */
  function windowPane() {
    var g = group();
    var paneM = FP.mat("glow", { color: [0.5, 0.6, 0.75], alpha: 0.85, radial: 0 });
    paneM.pass = "alpha";
    add(g, node(once("window-pane", function () { return G.box(0.5, 0.62, 0.01); }), paneM, { glint: false }));
    add(g, node(once("window-frame", function () {
      return weld([[G.box(0.56, 0.04, 0.04), [0, 0.31, 0]], [G.box(0.56, 0.04, 0.04), [0, -0.31, 0]],
                   [G.box(0.04, 0.66, 0.04), [-0.27, 0, 0]], [G.box(0.04, 0.66, 0.04), [0.27, 0, 0]],
                   [G.box(0.03, 0.62, 0.03), [0, 0, 0.01]], [G.box(0.5, 0.03, 0.03), [0, 0, 0.01]]]);
    }), FP.mat("darkwood"), { glint: false }));
    return { root: g, setLight: function (c, a) { paneM.color = c; paneM.alpha = a; } };
  }

  /* --- hand tools at the work ------------------------------------------------------------- */

  /* A pouring beaker with a lip, for Bottle: tilted over the vessel while it pours. */
  function beaker() {
    var g = group();
    var prof = [[0, 0], [0.04, 0], [0.042, 0.004], [0.042, 0.1], [0.046, 0.106]];
    add(g, node(once("beaker", function () { return G.lathe(GL.wall(prof, 0.0025), 20, 40); }), mat("glass", { alpha: 0.14 })));
    var liq = mat("liquid");
    var l = add(g, node(once("beaker-liquid", function () { return G.lathe(GL.liquidProfile(prof, 0.0025), 20, 40); }), liq));
    l.liquid = { lo: 0.004, hi: 0.09, level: 0.5 };
    return { root: g, liquid: l, lip: [0.046, 0.106, 0] };
  }
  function dropper() {
    var g = group();
    add(g, node(once("dropper-glass", function () { return G.lathe([[0, 0], [0.003, 0.004], [0.006, 0.03], [0.007, 0.11], [0, 0.11]], 10, 60); }),
                mat("glass", { alpha: 0.3 })));
    add(g, node(once("dropper-bulb", function () { return G.sphere(0.015, 12, 8); }), FP.mat("leather", { color: [0.32, 0.12, 0.08] }), { pos: [0, 0.12, 0], scl: [1, 1.4, 1] }));
    return { root: g, tip: [0, 0, 0] };
  }
  function stirRod() {
    var g = group();
    add(g, node(once("stir", function () { return G.cylinder(0.004, 0.3, 8); }), mat("glass", { alpha: 0.35 })));
    return g;
  }
  /* The assay's glass slide and the drop of reagent on it. */
  function slide() {
    var g = group();
    // Twice a real slide's size: at true size the assay's drop was a few pixels on the stage.
    add(g, node(once("slide", function () { return G.box(0.24, 0.006, 0.09); }), mat("glass", { alpha: 0.25 }), { pos: [0, 0.003, 0] }));
    var dropM = mat("liquid", { alpha: 0.85, pass: "alpha" });
    dropM.fillY = 1e4;
    var d = add(g, node(once("slide-drop", function () { return G.sphere(0.022, 14, 8); }), dropM, { pos: [0, 0.007, 0], scl: [1, 0.4, 1] }));
    add(g, GL.shadow(0.1));
    return { root: g, drop: d };
  }

  A.apparatus = { tripod: tripod, flame: flame, spiritLamp: spiritLamp, funnel: funnel, vialRack: vialRack,
                  mortar: mortar, roll: roll, workbench: workbench, athanor: athanor, sandBath: sandBath,
                  tube: tube, alembic: alembic, shelves: shelves, fumeHood: fumeHood, windowPane: windowPane,
                  beaker: beaker, dropper: dropper, stirRod: stirRod, slide: slide };
})();
