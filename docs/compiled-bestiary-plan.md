# Compiling the bestiary: no interpretation at play time

*Plan, 2026-10-28. Nothing here is built. It follows `fix/disarm-printed-weapon`, which put a
stat block's weapons on the creature's sheet (`Actor.take_up_printed_arms`,
docs/printed-attacks.md "Possession is the sheet's") and measured what the parser gets wrong
while doing it. The owner asked whether every creature should be set up so nothing is
interpreted; this is the answer and the order of work.*

## Why

Every imported creature's attacks are read off its printed lines at play time by
`rules/statblock_attacks.py`. It is deterministic code, not a model, so the cost is not
randomness: it is guesses hidden in the parser, which nobody reviews and which putting
weapons on the sheet now turns into game state (what can be disarmed, sundered, drawn and
looted). Measured over the 7,111 blocks with an attack line:

| what | count |
|---|---|
| blocks the parser reads nothing from (hungry fog, the witchlights…) | 30 |
| blocks read with fewer attacks than printed (rough regex count) | 331 |
| attacks read | 14,484 |
| made-weapon attacks with words dropped on the sheet ("+2 keen scimitar", "mwk cold iron dagger", "+1 flaming dogslicer") | 1,643 (343 distinct words) |
| attacks neither a table weapon nor a natural attack (rock 146, corrupting touch 68, incorporeal touch 51, swarm 40, tendrils 24, troop 23…) | 1,044 (431 distinct) |
| riders parsed and never fired (grab, poison, trip) | 2,309 |
| attacks standing on the fist (unarmed strike, flurry of blows) | 489 |
| made weapons `weapons.wieldable` refuses (bomb 97, armour spikes 19, shields 28, alchemist's fire 9, ammunition 18, cannons 8) | 179 |

The last two put "unarmed", bombs and armour spikes on sheets in the first cut of the
possession fix; they are excluded now (`Actor.printed_item`), but by rule after the fact.
Known misreads besides: "shuriken flurry of blows" stands on the fist, "thorns" on arrows.

**The book already says what a creature carries, and the import threw it away.** The source
spreadsheet (`monster_stat_blocks_full.xlsx`, "Updated 19Jan2020", 6,748 rows, 102 columns)
has `Gear` (5,048 rows filled) and `OtherGear` (3,593). `tools/build_bestiary.py` keeps
`Melee`, `Ranged` and `Treasure` and drops both. The guard's row: "half-plate, heavy
crossbow with 10 bolts, halberd, heavy flail, sap, 5 gp", plus "potions of cure light
wounds (2)". The fiend-born rager's armour spikes are its "+1 armor spiked breastplate".
Today the guard's possessions are guessed from its attack lines and its coin from its XP
(`bestiary._assemble_kit`, "2d6 sp" at 100 XP or more).

## How it has been done

- **Foundry PF1's statblock converter (SBC)**, the closest prior art: it converts a block
  once, at import, into stored actor data. Its changelog moved toward one shape:
  - v4.6.0, "find attacks from inventory weapons and use those as a source for processing";
  - v5.0.0, "Support for materials in inventory and attack processing";
  - v5.9.0, integrated weapons "processed as attacks even if the item isn't on the actor",
    which is the exception class this plan calls *worn*.

  Read through a summarising fetch of the GitLab changelog, not line by line at source.
- **Foundry PF2e:** a community macro exists to "map their attacks onto weapons and
  ammunition in their inventory" (FVTT-PF2e-Ranged-Combat). That implies NPC strikes and
  inventory are separate by default. I could not confirm the system's own default from its
  primary documentation.
- **The counter-example, adnd2e-foundryvtt PR #38:** it kept stat-block attacks apart from
  items. "Unequipping, including by a relayed disarm, removes the row" — only item-backed
  rows, so a printed attack cannot be disarmed. That is the defect fixed on
  `fix/disarm-printed-weapon`.
- **This repo's own record:** docs/printed-attacks.md chose to read the print live so a
  bench correction reaches every creature already standing in a scene. A compiled record
  keeps that property if the bench edits the record, rather than text a parser reads later.

## The shape

One compiled record per creature, shipped as content and validated, with the parser run
only when a block comes in (the import tool, the bench saving a homebrew creature, a World
Bible export).

- **`attacks`**: the printed options ("or"), each a list of attacks, each attack:
  - `name` as printed;
  - `class`, one of:
    - `item` — stands on a carried thing, with `item` pointing into `carries`;
    - `natural` — UMR family: bite, claw, gore;
    - `fist` — unarmed strike;
    - `body` — touch, tendrils, swarm, troop;
    - `thrown_object` — a giant's rock;
    - `ability` — a bomb, from `special_attacks` "bomb 12/day";
    - `worn` — armour or shield spikes, a shield bash;
  - `mode` — flurry of blows is a way of attacking, not a weapon: "kama flurry of blows" is
    the kama, flurried;
  - the numbers exactly as `statblock_attacks` already reads them (bonuses, dice, crit, type,
    touch, automatic, extra dice, ability damage);
  - riders, structured, still unfired (a separate piece of work), but no longer text.
- **`carries`**: every item from `Gear`, `OtherGear` and the treasure note, each one:
  - `key`, a table key from `weapons`, `armour` or goods;
  - `count`;
  - `enhancement`;
  - `masterwork`;
  - `material`, from content/materials/enchanter-materials.json;
  - `properties`, from content/rules/magic-properties.json (71 rows: keen, flaming, bane…);
  - `slot`: hand, worn armour, shield, pack, coin.
- **`source_hash` + `compiler`**: the hash of the printed lines it was compiled from, and the
  compiler's version. The bench refuses to save a creature whose record is stale, and a test
  refuses a shipped one. This follows CLAUDE.md's rule for derived data: version-stamp it
  and compare content.

The runtime changes:
- `stat_block_attacks` and `_find_stat_block_attack` read `attacks`;
- `take_up_printed_arms` reads `carries` — the armour and shield slots too, and gear records
  carrying enhancement, material and properties in the forge and enchanting record shape;
- the kit's derived wealth gives way to the printed coin and potions where the book prints
  them, still collapsing at first look (Schrödinger's pockets).

The creature's own numbers are unaffected, because the print's totals already include its
enhancement.

**A dependency to be honest about:** a looted "+2 keen scimitar" carries its +2 on the record,
but the wielded-weapon spec channel has no reader yet (stage 9, the states-effects-tells
ledger). In the player's hands it swings as a plain scimitar until stage 9 lands. The record
must still be right, so stage 9 has something to read.

## Phases

1. **Settle licensing first** (docs/bestiary-licensing.md, options A–E). The compile rewrites
   shipped data, and `OtherGear` names AP items. Keep `source` on every row, so removal by
   source family still works whichever option is chosen.
2. **Re-import raw.** Extend `tools/build_bestiary.py` to keep `Gear`, `OtherGear` and
   `Treasure` as text, without interpreting them. Account for the 7,111 creatures against the
   spreadsheet's 6,748 rows (core.json and other sources make up the rest; measure, don't
   assume).
3. **Compile.** `tools/compile_bestiary.py` writes `attacks` and `carries` from the raw lines:
   - reuse `statblock_attacks` for the attack lines;
   - read gear through `goods.known_item`, `weapons.key_for`, the materials file and the
     properties file;
   - fix the measured misreads at the source (shuriken flurry, thorns, frost bomb);
   - the 343 dropped words and 431 unknown names are classified once, in a table, not per
     creature.
4. **Cross-check.** Every `item` attack must find its thing in `carries` (by base and
   enhancement). Every mismatch goes on a review list: the book's own errata, or ours.
5. **Validator test (ratchet).** Every block compiles with no unaccounted attack piece and no
   unknown gear word. Exceptions live in one committed file, each with its reason, and the
   list may only shrink. The docstring carries the counts above.
6. **Switch the runtime** to the compiled record, as above. Keep `take_up_printed_arms` and its
   `print_armed` marker for saves.
7. **World Bible.** Write the same `attacks` and `carries` shape into docs/campaign-format.md
   as what a world's creatures export (fixes are world-agnostic). A world's peoples stay its
   own even when named Orc.
8. **Verify on real content.**
   - Before/after counts over the whole corpus.
   - In the app, spawn a sample across CR bands, then fight, disarm, sunder and loot each.
     Compare what comes off the body with its Gear line.
   - Prove the packaged build loads the compiled content from the install directory.

## For the owner to decide

1. **Licensing first?** The recommendation is yes. Settling it later rewrites the data twice.
2. **Loot is the printed Gear.** A 1e NPC's gear *is* its treasure (NPC wealth by level).
   This injects real magic items and coin from fights where today a guard yields 2d6 sp and,
   since the possession fix, its weapons. Recommended: yes, it is the rule.
3. **Where the record lives:** inline in creatures.json, or a sidecar file keyed by creature
   id. A sidecar keeps the raw import and the compile separately diffable and re-runnable.
   The recommendation is a sidecar.

## Sources

- [PF1 StatBlock Converter changelog (GitLab)](https://gitlab.com/foundryvtt_pathfinder1e/pf1-statblock-converter/-/blob/master/CHANGELOG.md)
- [Pathfinder 1e Statblock Converter (Foundry package)](https://foundryvtt.com/packages/pf1-statblock-converter)
- [FVTT-PF2e-Ranged-Combat README](https://github.com/JDCalvert/FVTT-PF2e-Ranged-Combat)
- [adnd2e-foundryvtt PR #38](https://github.com/PointFrankRange/adnd2e-foundryvtt/pull/38)
- [Disarm, Archives of Nethys](https://aonprd.com/Rules.aspx?Name=Disarm&Category=Combat%20Maneuvers)
