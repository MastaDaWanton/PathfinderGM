/* The tannery's stage, part 3: where the work is done.
 *
 * UI plan §6.3. Two kinds of set, each built once a session:
 *
 *   THE FIELD KIT ("kit"): on the ground you stand on (the herb kit's painted biome grounds,
 *   bench-stage/03-ground.js, which the adapter lays). The fleshing beam at the centre, a log
 *   on two legs with its low end on the ground; the stretching frame behind it; the kit roll
 *   open on the ground with its knives, awl, needles and mallet; a board laid flat for the
 *   flat work; the stitching pony; and the small pot over a fire, the brain-tan pot and the
 *   field kit's small kettle in one (the owner's 2026-10-08 answer).
 *
 *   THE TANNERY YARD ("town", someone's tannery; "owned", your own): flagstones under a
 *   lean-to in town, packed earth before a plank shed in a tannery of your own (the plan's
 *   proposal). The beam, the currier's table, three vats sunk in a row behind, the hardening
 *   kettle on its stand, the drying rack with the yard's other hides hung over it, the frame
 *   and the pony, and a lantern on the post that is lit at night.
 *
 * A set names its SPOTS, the places the work can be: `beam`, `flat` (the board or the
 * currier's table), `frame`, `pot`, `vat`, `kettle` and `pony`. Each spot gives the drape a
 * hide lies in there and the box the camera frames when the work is there. The adapter asks
 * the method which spot it wants and does the rest.
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var F = window.ForgeStageKit || {};
  var T = window.TanneryStageKit = window.TanneryStageKit || {};
  var G = K.mesh, M = K.math, FP = F.props, P = T.props, H = T.hide;
  if (!G || !M || !FP || !P || !H) return;
  var add = FP.add, group = FP.group;

  function place(n, pos, ry) { n.pos = pos.slice(); if (ry) n.rot = [0, ry, 0]; return n; }
  // A spot's camera box, and its own pitch where the set's would look through something: the
  // vat is seen from high (at the set's 30 degrees the beam and the currier's table stood
  // in front of it in the first capture), the frame and the pony from low and in front.
  function box(c, h, pitch) { return { c: c, h: h, pitch: pitch || 0 }; }

  /* The beam's drape in the set's frame: the log's axis moved to where the beam stands. */
  function beamDrape(at, beam) {
    var a = beam.axis;
    return { kind: "beam", at: [at[0] + a.at[0], at[1] + a.at[1], at[2] + a.at[2]], R: a.R, tilt: a.tilt };
  }

  // The yard's other hides on the drying rack: their own tannage colours (scene content only).
  var HUNG = [
    { color: "#9a6236", surface: "smooth", form: "leather", tannage_kind: "bark", plan: "quadruped", units: 0.62 },
    { color: "#6b4a30", surface: "fur", form: "fur", plan: "quadruped", units: 0.55 }
  ];

  function hungHides(root, rack, at) {
    HUNG.forEach(function (h, i) {
      var x = at[0] - rack.len / 2 + (i + 0.5) * rack.len / HUNG.length;
      var spec = { plan: h.plan, units: h.units, seed: H.seedOf("yard" + i),
                   drape: { kind: "beam", at: [x, at[1] + rack.pole[1], at[2]], R: 0.03, tilt: 0 } };
      // Hung by the spine over the pole, the two sides hanging, as hides are hung to dry.
      var mesh = H.hide(spec), f = H.faces(h);
      add(root, FP.node(mesh.out, f.out, { glint: false }));
      add(root, FP.node(mesh.under, f.under, { glint: false }));
    });
  }

  function kit() {
    var root = group(), set = { kind: "kit", root: root, spots: {}, props: {} };
    var beam = P.fleshingBeam(), bAt = [-0.05, 0, 0.05];
    add(root, place(beam.root, bAt));
    var fr = P.stretchFrame(0.9, 1.0), fAt = [0.05, 0, -0.95];
    add(root, place(fr.root, fAt));
    var roll = P.kitRoll();
    add(root, place(roll.root, [-0.95, 0, 0.55], 0.25));
    var board = P.table(0.84, 0.62, 0.05), boAt = [0.55, 0, 0.72];
    add(root, place(board.root, boAt, -0.12));
    var pot = P.potOverFire(), pAt = [1.25, 0, -0.35];
    add(root, place(pot.root, pAt));
    var pony = P.stitchingPony(), pyAt = [-1.1, 0, -0.3];
    add(root, place(pony.root, pyAt));
    var salt = P.saltSack();
    add(root, place(salt.root, [1.15, 0, 0.55], 0.4));
    set.props = { beam: beam, frame: fr, roll: roll, board: board, pot: pot, pony: pony, salt: salt };
    set.fire = { node: pot.fire, at: M.add(pAt, pot.fire.light) };
    set.lantern = null;
    set.spots = {
      beam: { drape: beamDrape(bAt, beam), fit: box([bAt[0], 0.42, bAt[2]], [0.95, 0.45, 0.6]), tool: [bAt[0] + 0.12, 0.6, bAt[2] + 0.02] },
      flat: { drape: { kind: "slab", at: [boAt[0], board.top, boAt[2]], h: 0.004, hx: board.hx, hz: board.hz, yaw: -0.12 }, top: [boAt[0], board.top, boAt[2]],
              hx: board.hx, fit: box([boAt[0], 0.1, boAt[2]], [0.62, 0.15, 0.48]), tool: [boAt[0] + 0.18, board.top + 0.035, boAt[2] + 0.1] },
      frame: { drape: { kind: "frame", at: M.add(fAt, fr.centre), lean: fr.lean, hl: fr.hl, hw: fr.hw }, frame: fr, origin: fAt,
               fit: box([fAt[0], 0.62, fAt[2] - 0.05], [0.68, 0.62, 0.4], 20) },
      pot: { drape: { kind: "vat", at: M.add(pAt, [0, pot.water.pos[1] + 0.004, 0]), r: pot.r }, water: pot.water, surface: M.add(pAt, [0, pot.water.pos[1], 0]),
             fit: box([pAt[0], 0.38, pAt[2]], [0.38, 0.38, 0.38], 50) },
      pony: { at: M.add(pyAt, pony.jaw), fit: box([pyAt[0], 0.55, pyAt[2]], [0.32, 0.32, 0.3], 24) }
    };
    // The kit's small kettle is the pot: Harden in the field over the same fire.
    set.spots.kettle = { water: pot.water, surface: set.spots.pot.surface, fit: set.spots.pot.fit, mouth: M.add(pAt, pot.mouth) };
    var pts = [];
    [[-1.3, 0, -1.1], [1.55, 0, -1.1], [-1.3, 0, 1.05], [1.55, 0, 1.05], [0, 1.15, -1.0], [1.25, 0.65, -0.35]].forEach(function (p) { pts.push(p[0], p[1], p[2]); });
    set.fit = { pts: new Float32Array(pts), centre: [0.1, 0.35, 0], pitch: 35, h: 0.8, w: 0.92 };
    return set;
  }

  function yard(kind) {
    var owned = kind === "owned";
    var root = group(), set = { kind: owned ? "owned" : "town", root: root, spots: {}, props: {} };
    if (!owned) add(root, place(P.flagstones(5.2, 3.6), [0, 0, -0.4]));
    add(root, place(P.shelter(owned).root, [0, 0, -2.0]));
    var beam = P.fleshingBeam(), bAt = [-0.7, 0, 0.25];
    add(root, place(beam.root, bAt));
    var tb = P.table(1.1, 0.7, 0.82), tAt = [0.75, 0, 0.35];
    add(root, place(tb.root, tAt));
    var vats = [], vx = [-1.1, 0, 1.1];
    vx.forEach(function (x) { var v = P.sunkVat(0.42); vats.push(v); add(root, place(v.root, [x, 0, -1.15])); });
    // The other vats hold the yard's own work: a darker liquor, a hide's back showing.
    vats[0].liquor.mat.color = [0.12, 0.07, 0.04];
    vats[2].liquor.mat.color = [0.2, 0.15, 0.1];
    var ket = P.kettleStand(), kAt = [1.95, 0, -0.35];
    add(root, place(ket.root, kAt));
    var rack = P.dryingRack(2.1), rAt = [0.2, 0, -2.45];
    add(root, place(rack.root, rAt));
    hungHides(root, rack, rAt);
    var fr = P.stretchFrame(0.9, 1.0), fAt = [-2.0, 0, -0.55];
    add(root, place(fr.root, fAt));
    var pony = P.stitchingPony(), pyAt = [-2.15, 0, 1.0];
    add(root, place(pony.root, pyAt));
    var salt = P.saltSack();
    add(root, place(salt.root, [1.55, 0, 0.75], -0.5));
    var lan = P.lantern();
    add(root, place(lan.root, [1.7, 1.75, -1.6]));
    set.props = { beam: beam, table: tb, vats: vats, kettle: ket, rack: rack, frame: fr, pony: pony, salt: salt };
    set.fire = { node: ket.fire, at: M.add(kAt, ket.fire.light) };
    set.lantern = { node: lan, at: [1.7, 1.84, -1.6] };
    var vAt = [vx[1], 0, -1.15];
    set.spots = {
      beam: { drape: beamDrape(bAt, beam), fit: box([bAt[0], 0.42, bAt[2]], [0.95, 0.45, 0.6]), tool: [bAt[0] + 0.12, 0.6, bAt[2] + 0.02] },
      flat: { drape: { kind: "slab", at: [tAt[0], tb.top, tAt[2]], h: 0.004, hx: tb.hx, hz: tb.hz }, top: [tAt[0], tb.top, tAt[2]],
              hx: tb.hx, fit: box([tAt[0], 0.75, tAt[2]], [0.68, 0.32, 0.5]), tool: [tAt[0] + 0.22, tb.top + 0.035, tAt[2] + 0.12] },
      frame: { drape: { kind: "frame", at: M.add(fAt, fr.centre), lean: fr.lean, hl: fr.hl, hw: fr.hw }, frame: fr, origin: fAt,
               fit: box([fAt[0], 0.62, fAt[2] - 0.05], [0.7, 0.62, 0.45], 20) },
      vat: { drape: { kind: "vat", at: M.add(vAt, [0, vats[1].surface[1] + 0.004, 0]), r: vats[1].r }, water: vats[1].liquor, surface: M.add(vAt, vats[1].surface),
             fit: box([vAt[0], 0.15, vAt[2]], [0.62, 0.3, 0.55], 58) },
      kettle: { water: ket.water, surface: M.add(kAt, [0, ket.water.pos[1], 0]), mouth: M.add(kAt, ket.mouth),
                fit: box([kAt[0], 0.6, kAt[2]], [0.5, 0.45, 0.45], 34) },
      pony: { at: M.add(pyAt, pony.jaw), fit: box([pyAt[0], 0.55, pyAt[2]], [0.34, 0.32, 0.32], 24) }
    };
    set.spots.pot = set.spots.vat;
    var pts = [];
    [[-2.3, 0, -1.6], [2.3, 0, -1.6], [-2.3, 0, 1.0], [2.3, 0, 1.0], [0, 1.4, -2.4], [1.95, 0.7, -0.35]].forEach(function (p) { pts.push(p[0], p[1], p[2]); });
    set.fit = { pts: new Float32Array(pts), centre: [0, 0.5, -0.5], pitch: 30, h: 0.8, w: 0.94 };
    return set;
  }

  /* Which set a scene is: "kit" in the field, "town" or "owned" a tannery. Anything else is
     the kit, which is never a lie about a yard not there. */
  function kindOf(g) {
    var k = String((g && g.kind) || "").toLowerCase();
    if (k === "town" || k === "owned") return k;
    if (k === "tannery" || k === "yard") return "town";
    return "kit";
  }

  T.yard = { kit: kit, yard: yard, kindOf: kindOf };
})();
