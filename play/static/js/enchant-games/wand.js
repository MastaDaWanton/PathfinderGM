// Enchant minigame: Wand, cut a wand's sigils down the blank in their order (the spell-items
// lane, 2026-11-22; docs/item-creation-feats-study.md §3.3). Prepare's order game with a
// carver's pieces: the server's sequence (rules/enchanter.py `tuning_for`) notches the blank,
// then a sigil and a rune for each spell level, and the seal binds it. Played, scored and
// drawn by prepare.js's `create`, read through `this` for these names; prepare.js loads first.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  defs.wand = {
    id: "wand",
    track: "enchant",
    name: "Wand",
    first: "Watch the sigils run down the blank, then cut each in its place. The seal binds it.",
    hint: function (steady) { return steady ? "1 to 6, or click the sigil" : "Watch, then 1 to 6 or click"; },
    KEYS: ["1", "2", "3", "4", "5", "6", "ArrowLeft", "ArrowRight", "Space", "Enter"],
    HOLDS: [],
    HOLDS_STEADY: [],
    NAMES: { quarter: "Notch", sigil: "Sigil", enhancement: "Rune", bell: "Seal",
             focus: "Knot", catalyst: "Spark" },
    POOL: ["quarter", "sigil", "enhancement", "bell", "focus", "catalyst"],
    SOUNDS: { hit: "enchant.chalk", bell: "enchant.bell", miss: "enchant.miss" },
    create: function (ctx) { return defs.prepare.create.call(this, ctx); },
  };
})();
