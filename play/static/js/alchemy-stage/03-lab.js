/* The alchemy bench's stage, part 3: where the work is done.
 *
 * UI plan §6.3. Two sets, each built once a session:
 *
 *   THE FIELD KIT ("kit"): the leather roll on the ground you stand on (the herb kit's painted
 *   biome grounds, bench-stage/03-ground.js, which the adapter lays), the tripod over the
 *   spirit lamp at its heart, and the portable set round it: crucible, a flask in its cork
 *   ring, mortar and pestle, a rack of four vials.
 *
 *   THE LABORATORY ("town", someone's hired laboratory; "owned", your own): the forge's painted
 *   smithy room (forge-stage/03-smithy.js, as it is: stone flags and a stone wall in town,
 *   planks and timber in a laboratory of your own, so the benches' rooms are of one world), a
 *   workbench, the athanor under its fume hood, the alembic's receiver to its right, a retort
 *   in a sand bath, a bain-marie, shelves of jars and a window on the wall behind.
 *
 * Each set says where things go and the adapter does the rest: `hot` is where the active
 * vessel's base sits over the fire (and `ring`, the tripod ring's radius a round bottom rests
 * in), `work` the cold spot in front for Filter, Bottle and Assay and the alembic's receiver,
 * `heat(k, flick)` poses the fire, `keyPos` is the fire's light, and `fit` the points the
 * camera frames. The props named in `idle` stand aside, and the adapter hides the one whose
 * kind is the active vessel's, so the crucible is never in two places.
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var F = window.ForgeStageKit || {};
  var A = window.AlchemyStageKit = window.AlchemyStageKit || {};
  var G = K.mesh, M = K.math, FP = F.props, GL = A.glass, AP = A.apparatus, LQ = A.liquid;
  if (!G || !M || !FP || !F.smithy || !GL || !AP || !LQ) return;
  var add = FP.add, group = FP.group;

  function place(n, pos, rot) { n.pos = pos.slice(); if (rot) n.rot = rot.slice(); return n; }

  // The rack's four vials and the bain-marie's water: the kit's own stock, colours the shelf
  // sells (brimstone yellow, a green tincture, alum's white, a red) taken from the materials
  // file's own `color`s so the set says nothing the world does not.
  var RACK = [[0.86, 0.78, 0.22], [0.3, 0.55, 0.32], [0.95, 0.95, 0.97], [0.62, 0.16, 0.12]].map(LQ.toBase);

  function kit() {
    var root = group(), set = { kind: "kit", root: root, idle: {}, ring: 0.07 };
    add(root, AP.roll());
    var tri = AP.tripod(0.2), lamp = AP.spiritLamp();
    add(root, tri.root);
    add(root, lamp.root);
    set.hot = [0, tri.top, 0];
    set.heat = function (k, flick) { lamp.flame.set(k, flick); };
    // A little in front of the flame, so the lamp lights the glass's camera side, not only its
    // underside.
    set.keyPos = [0, 0.16, 0.12];
    set.fire = lamp.fire;
    set.work = [0.4, 0, 0.16];
    var cru = GL.vessel("crucible");
    cru.liquid.mat.color = LQ.toBase([0.5, 0.45, 0.4]);
    cru.liquid.liquid.level = 0.35;
    cru.liquid.mat.turbid = 1;
    set.idle.crucible = add(root, place(cru.root, [-0.42, 0, -0.04]));
    var fl = GL.vessel("flask");
    fl.liquid.liquid.level = 0;
    // A round bottom cannot stand: it rests in a cork ring, 14 mm up (the ring's top is 24 mm
    // up, and a sphere of 85 mm meets a 40 mm ring 10 mm above its lowest point).
    var held = group();
    add(held, FP.node(GL.once("cork-ring", function () { return G.ring(0.04, 0.012, 24, 6); }), FP.mat("wood", { color: [0.6, 0.45, 0.3], pattern: 3 }),
                      { pos: [0, 0.012, 0] }));
    add(held, place(fl.root, [0, 0.014, 0]));
    set.idle.flask = add(root, place(held, [-0.1, 0, -0.32]));
    var mo = AP.mortar();
    set.idle.mortar = add(root, place(mo.root, [-0.34, 0, 0.27]));
    var rack = AP.vialRack(RACK);
    set.idle.vial = add(root, place(rack.root, [0.36, 0, -0.24], [0, -0.2, 0]));
    set.rack = rack;
    // The frame: the roll's corners at the ground, and the tallest glass on the tripod.
    var pts = [];
    [[-0.68, 0, -0.42], [0.68, 0, -0.42], [-0.68, 0, 0.42], [0.68, 0, 0.42],
     [-0.5, 0.25, -0.1], [0.5, 0.25, -0.1], [0, 0.55, 0], [0.4, 0.3, 0.16]].forEach(function (p) { pts.push(p[0], p[1], p[2]); });
    set.fit = { pts: new Float32Array(pts), centre: [0, 0.14, 0], pitch: 35, dist: 2.6, h: 0.78, w: 0.9 };
    return set;
  }

  function lab(kind) {
    var owned = kind === "owned";
    var root = group(), set = { kind: owned ? "owned" : "town", root: root, idle: {}, ring: 0 };
    var B = 0.78;
    set.room = F.smithy.room(owned ? "owned" : "town");
    add(root, set.room);
    add(root, place(AP.workbench(B, 2.7, 0.92), [0, 0, -0.16]));
    var ath = AP.athanor();
    var aAt = [-0.25, B, -0.3];
    add(root, place(ath.root, aAt));
    set.hot = [aAt[0], B + ath.top, aAt[2]];
    set.heat = function (k, flick) { ath.setHeat(k, flick); };
    set.keyPos = [aAt[0] + ath.fire[0], B + ath.fire[1] + 0.25, aAt[2] + ath.fire[2] + 0.1];
    set.fire = [aAt[0] + ath.fire[0], B + ath.fire[1], aAt[2] + ath.fire[2]];
    set.work = [0.34, B, 0.02];
    var hood = AP.fumeHood();
    // Low enough that its lip is in frame: at 1.02 only a sliver of it showed at 16:9.
    add(root, place(hood, [aAt[0], B + 0.88, aAt[2] - 0.04]));
    var sb = AP.sandBath();
    add(root, place(sb.root, [-0.98, B, -0.28]));
    var bm = GL.vessel("bainmarie");
    bm.liquid.mat.color = LQ.toBase([0.5, 0.58, 0.6]);
    bm.liquid.mat.surf = LQ.toBase([0.7, 0.76, 0.78]);
    bm.liquid.mat.alpha = 0.4;
    bm.liquid.liquid.level = 0.7;
    add(root, place(bm.root, [0.92, B, -0.36]));
    var cru = GL.vessel("crucible");
    cru.liquid.mat.color = LQ.toBase([0.5, 0.45, 0.4]);
    cru.liquid.liquid.level = 0.35;
    cru.liquid.mat.turbid = 1;
    set.idle.crucible = add(root, place(cru.root, [-0.66, B, -0.44]));
    var mo = AP.mortar();
    set.idle.mortar = add(root, place(mo.root, [-0.78, B, 0.12]));
    var rack = AP.vialRack(RACK);
    set.idle.vial = add(root, place(rack.root, [0.8, B, 0.1], [0, -0.15, 0]));
    set.rack = rack;
    var sh = AP.shelves();
    add(root, place(sh, [0.5, 1.3, -1.32]));
    var win = AP.windowPane();
    add(root, place(win.root, [1.45, 1.75, -1.43]));
    set.window = win;
    var pts = [];
    // Framed on the athanor and the cold spot, not the whole bench: fitted to the bench's ends,
    // a 12 cm vial at the cold spot was a dozen pixels tall at 1280x720 in the live capture.
    [[-0.8, B, -0.55], [0.95, B, -0.55], [-0.8, B, 0.28], [0.95, B, 0.28],
     [aAt[0], B + 0.95, aAt[2]], [0.34, B + 0.25, 0.02]].forEach(function (p) { pts.push(p[0], p[1], p[2]); });
    set.fit = { pts: new Float32Array(pts), centre: [0.05, B + 0.25, -0.15], pitch: 26, dist: 3.0, h: 0.8, w: 0.94 };
    return set;
  }

  /* Which set a scene is: "kit" outdoors (or under a roof, at the kit), "town" or "owned" a
     laboratory. Anything else is the kit, which is never a lie about walls not there. */
  function kindOf(g) {
    var k = String((g && g.kind) || "").toLowerCase();
    if (k === "town" || k === "owned") return k;
    if (k === "lab" || k === "laboratory" || k === "hired") return "town";
    return "kit";
  }

  A.lab = { kit: kit, lab: lab, kindOf: kindOf };
})();
