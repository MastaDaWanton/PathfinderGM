/* The enchanting bench's stage, part 3: where the circle is drawn.
 *
 * UI plan §6.3: at camp the circle is chalked on the biome ground (bench-stage/03-ground.js);
 * under a roof, on planks (the same painter's indoor floor); in a sanctum, or at someone else's
 * circle you have hired, on STONE FLAGS with a worn rug under the circle and a lectern and a
 * shelf at the back (the plan's proposal, Q-UI4, taken until the owner says otherwise). The
 * flags and the wall are forge-stage/03-smithy.js's town smithy room, reused as it is: the same
 * painted stone, so the two benches' rooms are of one world.
 *
 * Grounds are painted once a session and cached by their painters; this file only arranges.
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var F = window.ForgeStageKit || {};
  var E = window.EnchantStageKit = window.EnchantStageKit || {};
  var G = K.mesh, M = K.math, FP = F.props, P = E.props;
  if (!G || !M || !FP || !F.smithy || !P) return;

  /* Which room a scene is: "camp" | "roofed" | "sanctum" | "hired". Anything else is camp, the
     circle on the ground, which is never a lie about walls that are not there. */
  function kindOf(g) {
    var k = String((g && g.kind) || "").toLowerCase();
    if (k === "sanctum" || k === "hired") return k;
    if (k === "roofed" || (g && g.roofed)) return "roofed";
    return "camp";
  }

  /* The sanctum: the smithy's flags and stone wall, a rug, a lectern at the back left and a
     shelf at the back right. Built once a session per kind. */
  var rooms = {};
  function sanctum(kind) {
    if (rooms[kind]) return rooms[kind];
    var room = F.smithy.room("town"), g = FP.group();
    FP.add(g, room);
    // A hired circle is someone else's room: the same stone, a plainer, darker rug.
    var rug = P.rug();
    if (kind === "hired") rug.mat = P.mat("rug", { color: [0.13, 0.11, 0.09] });
    FP.add(g, rug);
    var lec = P.lectern(); lec.pos = [-1.45, 0, -1.05]; lec.rot = [0, 0.5, 0];
    FP.add(g, lec);
    var sh = P.shelf(); sh.pos = [1.3, 0, -1.3]; sh.rot = [0, -0.15, 0];
    FP.add(g, sh);
    rooms[kind] = { root: g, recs: room.recs, back: [lec, sh] };
    return rooms[kind];
  }

  E.room = { kindOf: kindOf, sanctum: sanctum };
})();
