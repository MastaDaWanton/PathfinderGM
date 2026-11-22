// Enchant minigame: Scribe, write a scroll's strokes in their order (the spell-items lane,
// 2026-11-22; docs/item-creation-feats-study.md §3.2: "calligraphy: the strokes in order, no
// freehand", the owner's own rule for the circle). Prepare's order game with a pen's pieces:
// the server's sequence (rules/enchanter.py `tuning_for`) rules the sheet, wets the pen, then
// a stroke and a rune for each spell level, and the seal closes it. Played, scored and drawn
// by prepare.js's `create`, read through `this` for these names; prepare.js loads first.
(function () {
  "use strict";
  var defs = window.BenchGameDefs = window.BenchGameDefs || {};
  defs.scroll = {
    id: "scroll",
    track: "enchant",
    name: "Scribe",
    first: "Watch the strokes in their order, then write each one. The seal closes it.",
    hint: function (steady) { return steady ? "1 to 6, or click the stroke" : "Watch, then 1 to 6 or click"; },
    KEYS: ["1", "2", "3", "4", "5", "6", "ArrowLeft", "ArrowRight", "Space", "Enter"],
    HOLDS: [],
    HOLDS_STEADY: [],
    NAMES: { quarter: "Rule", ink: "Ink", sigil: "Stroke", enhancement: "Rune", bell: "Seal",
             chalk: "Margin", catalyst: "Flourish" },
    POOL: ["quarter", "ink", "sigil", "enhancement", "bell", "chalk", "catalyst"],
    // The pen's drip for every stroke, the bell for the seal, the circle's muffled bowl for
    // a wrong piece: UI plan §11's own names.
    SOUNDS: { hit: "enchant.ink", ink: "enchant.ink", bell: "enchant.bell", miss: "enchant.miss" },
    create: function (ctx) { return defs.prepare.create.call(this, ctx); },
  };
})();
