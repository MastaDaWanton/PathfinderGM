/* The enchanting bench's stage, part 2: the vessels the forge has no family for.
 *
 * Forged weapons, armour and shields come from forge-stage/02-families.js as they are (UI plan
 * §7.1), built from their pieces in their own metals. A ring, an amulet, a circlet, a cloak,
 * boots, a belt, gloves and bracers are not forged pieces, so they are eight small families
 * here, on the same terms: procedural, no per-item model, each lying flat on the floor of the
 * circle with its own origin at its centre.
 *
 * A family returns a list of PARTS, each {mesh, part, pos, rot, scl}. `part` names what the
 * part is made of in general ("metal", "leather", "cloth", "gem"), and the adapter colours it:
 * the vessel's main material for metal, the essence of the seat it carries for a gem.
 *
 * WHICH FAMILY. A ring's gear is "ring"; everything else the book prices as wondrous (rules/
 * magic_layer.vessel_kind), so the family is read from the item's slot (rules/enchanter.BLANKS:
 * ring, neck, shoulders; a leatherworker's wearables: head, feet, waist or belt, hands, wrists,
 * body), then from words in its name, then an amulet, the plainest thing to lay on a cloth.
 */
(function () {
  "use strict";
  var K = window.BenchStageKit || {};
  var E = window.EnchantStageKit = window.EnchantStageKit || {};
  var G = K.mesh, M = K.math;
  if (!G || !M) return;
  var TAU = Math.PI * 2;

  var FAMILIES = ["ring", "amulet", "circlet", "cloak", "boots", "belt", "gloves", "bracers"];

  function at(mesh, part, pos, rot, scl) {
    return { mesh: mesh, part: part, pos: pos || [0, 0, 0], rot: rot || [0, 0, 0], scl: scl || [1, 1, 1] };
  }
  function weld(list) {
    return G.merge(list.map(function (p) { return { mesh: p[0], m: M.compose(p[1] || [0, 0, 0], p[2] || [0, 0, 0], p[3] || [1, 1, 1]) }; }));
  }

  var BUILD = {
    /* A band lying flat with its stone standing up at the front. */
    ring: function () {
      return [
        at(G.ring(0.05, 0.009, 40, 8), "metal", [0, 0.009, 0], [0, 0, 0], [1, 1.4, 1]),
        at(weld([[G.cylinder(0.018, 0.014, 6), [0, 0, 0]], [G.ring(0.017, 0.004, 16, 5), [0, 0.012, 0]]]), "metal", [0, 0.012, 0.055], [Math.PI / 2, 0, 0]),
        at(G.sphere(0.016, 10, 6), "gem", [0, 0.024, 0.066], [0, 0, 0], [1, 0.8, 1])
      ];
    },
    /* A disc on a chain laid in a loose loop above it. */
    amulet: function () {
      var links = [], r = M.rng(55);
      for (var i = 0; i < 26; i++) {
        var t = (i / 26 - 0.5) * 1.7 * Math.PI, rr = 0.13 + (r() - 0.5) * 0.01;
        links.push([G.ring(0.009, 0.0025, 10, 4), [Math.sin(t) * rr, 0.003, -Math.cos(t) * rr * 0.8 - 0.07], [Math.PI / 2 * (i % 2), t, 0]]);
      }
      return [
        at(weld(links), "metal"),
        at(G.cylinder(0.055, 0.01, 28), "metal", [0, 0, 0.05]),
        at(G.ring(0.05, 0.004, 28, 5), "metal", [0, 0.01, 0.05]),
        at(G.sphere(0.022, 12, 8), "gem", [0, 0.012, 0.05], [0, 0, 0], [1, 0.55, 1])
      ];
    },
    /* A thin band in an oval, a little higher at the brow, with a stone at the front. */
    circlet: function () {
      return [
        at(G.ring(0.1, 0.006, 56, 6), "metal", [0, 0.008, 0], [0, 0, 0], [1, 1.6, 0.85]),
        at(G.lathe([[0, 0], [0.022, 0], [0, 0.04]], 4, 80), "metal", [0, 0.008, 0.085], [-Math.PI / 2 + 0.2, 0, 0]),
        at(G.sphere(0.014, 10, 6), "gem", [0, 0.024, 0.09])
      ];
    },
    /* A folded drape: a slab with a rolled hem and a clasp. */
    cloak: function () {
      var folds = [];
      for (var i = 0; i < 5; i++) folds.push([G.capsule(0.022, 0.5, 8), [-0.25, 0.018, -0.13 + i * 0.065], [0, 0, -Math.PI / 2], [1, 1, 0.8 + (i % 2) * 0.3]]);
      return [
        at(G.box(0.52, 0.03, 0.34), "cloth", [0, 0.015, 0]),
        at(weld(folds), "cloth", [0, 0.012, 0]),
        at(G.cylinder(0.028, 0.012, 16), "metal", [0.2, 0.04, 0.12]),
        at(G.sphere(0.012, 10, 6), "gem", [0.2, 0.054, 0.12], [0, 0, 0], [1, 0.6, 1])
      ];
    },
    /* A pair: a shaft and a foot each, lying on their sides. */
    boots: function () {
      var one = weld([[G.capsule(0.045, 0.24, 12), [0, 0, 0], [0, 0, -Math.PI / 2], [1, 1, 0.7]],
                      [G.capsule(0.04, 0.16, 12), [-0.005, 0, 0.0], [Math.PI / 2, 0, 0], [1.1, 1, 0.75]]]);
      return [
        at(one, "leather", [-0.12, 0.035, -0.06], [0, 0.25, 0]),
        at(one, "leather", [0.1, 0.035, 0.04], [0, 0.05, 0]),
        at(G.ring(0.045, 0.006, 20, 5), "metal", [0.1, 0.035, -0.04], [0, 0, Math.PI / 2]),
        at(G.sphere(0.012, 10, 6), "gem", [0.215, 0.05, 0.04])
      ];
    },
    /* A coiled strap with its buckle at the front. */
    belt: function () {
      var strap = [];
      for (var i = 0; i < 40; i++) {
        var t = i / 40 * TAU * 1.15, rr = 0.08 + i * 0.0018;
        strap.push([G.box(0.032, 0.01, 0.04), [Math.cos(t) * rr, 0.005, Math.sin(t) * rr], [0, -t, 0]]);
      }
      return [
        at(weld(strap), "leather"),
        at(weld([[G.box(0.06, 0.008, 0.012), [0, 0, 0.026]], [G.box(0.06, 0.008, 0.012), [0, 0, -0.026]],
                 [G.box(0.012, 0.008, 0.06), [0.026, 0, 0]], [G.box(0.012, 0.008, 0.06), [-0.026, 0, 0]]]), "metal", [0.155, 0.012, 0.03]),
        at(G.sphere(0.011, 10, 6), "gem", [0.155, 0.02, 0.03])
      ];
    },
    /* A pair of gloves, palms down: a cuff, a palm and four fingers and a thumb each. */
    gloves: function () {
      var hand = [[G.box(0.09, 0.024, 0.1), [0, 0, 0]], [G.capsule(0.05, 0.06, 10), [-0.07, 0, 0], [0, 0, -Math.PI / 2], [1, 1, 0.5]]];
      for (var f = 0; f < 4; f++) hand.push([G.capsule(0.011, 0.075, 8), [0.04, 0, -0.035 + f * 0.023], [0, 0, -Math.PI / 2], [1, 1, 0.9]]);
      hand.push([G.capsule(0.012, 0.06, 8), [0.0, 0, 0.055], [0, 0.9, -Math.PI / 2]]);
      var one = weld(hand);
      return [
        at(one, "leather", [-0.08, 0.014, -0.08], [0, 0.35, 0]),
        at(one, "leather", [0.08, 0.014, 0.07], [0, -0.2, 0], [1, 1, -1]),
        at(G.sphere(0.01, 10, 6), "gem", [0.02, 0.03, 0.06])
      ];
    },
    /* A pair of open cuffs with metal bands. */
    bracers: function () {
      var cuff = G.lathe([[0.045, 0], [0.05, 0], [0.042, 0.16], [0.037, 0.16]], 18, 60);
      return [
        at(cuff, "leather", [-0.09, 0.045, -0.04], [0, 0.2, Math.PI / 2], [1, 1, 0.8]),
        at(cuff, "leather", [0.09, 0.045, 0.06], [0, -0.15, Math.PI / 2], [1, 1, 0.8]),
        at(G.ring(0.05, 0.005, 24, 5), "metal", [-0.09, 0.045, -0.04], [0, 0.2, Math.PI / 2]),
        at(G.ring(0.05, 0.005, 24, 5), "metal", [0.09, 0.045, 0.06], [0, -0.15, Math.PI / 2]),
        at(G.sphere(0.01, 10, 6), "gem", [0.1, 0.095, 0.06])
      ];
    }
  };

  var cache = {};
  function build(fam) {
    if (!BUILD[fam]) fam = "amulet";
    if (!cache[fam]) cache[fam] = BUILD[fam]();
    return cache[fam];
  }

  var SLOT = { ring: "ring", neck: "amulet", throat: "amulet", shoulders: "cloak", cloak: "cloak", body: "cloak",
               chest: "cloak", head: "circlet", headband: "circlet", eyes: "circlet", feet: "boots",
               waist: "belt", belt: "belt", hands: "gloves", wrists: "bracers", wrist: "bracers" };
  var WORDS = [[/ring\b/, "ring"], [/amulet|pendant|necklace|periapt|medallion|brooch|scarab|torc/, "amulet"],
               [/circlet|crown|headband|diadem|tiara|hat|helm|mask|goggles/, "circlet"],
               [/cloak|cape|mantle|robe|shawl|vest|shirt|tunic/, "cloak"], [/boot|slipper|shoe|sandal/, "boots"],
               [/belt|girdle|sash/, "belt"], [/glove|gauntlet|mitt/, "gloves"], [/bracer|bracelet|vambrace|cuff/, "bracers"]];

  /* The family for a vessel that is not a forged weapon, armour or shield. */
  function familyFor(gear, slot, name) {
    if (gear === "ring") return "ring";
    var s = String(slot || "").toLowerCase();
    if (SLOT[s]) return SLOT[s];
    var n = String(name || "").toLowerCase();
    for (var i = 0; i < WORDS.length; i++) if (WORDS[i][0].test(n)) return WORDS[i][1];
    return "amulet";
  }

  E.vessels = { FAMILIES: FAMILIES, build: build, familyFor: familyFor };
})();
