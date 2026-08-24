# Blacksmithing

The second world class, and the first proof of `rules/worldclass.py`'s promise that a new
craft is "three more files rather than three more code paths". The three files are
`content/world-classes/blacksmith.json` (the track — read by the generic loader,
unchanged), `content/materials/blacksmith-materials.json` (the catalogue, 112 entries),
and `rules/blacksmith.py` (the chain semantics). `tests/test_blacksmith.py` pins all of
it.

## The fiction

Anyone may be a Blacksmith, the way anyone may be an Herbalist: a Fighter who works a
forge *is* one. The track grants no BAB, no saves, no hit dice. It levels on what the
character does — smelting, forging, finishing — and what it gates is method and metal: a
Blacksmith 1 hammers bar iron at a field forge; a Blacksmith 5 stands at a starmetal
forge and polishes work that outlives its maker.

A craft is a **chain**: an ordered list of methods applied to a charge of materials, in
the shape of a real base item. The order is physical grammar, not ceremony — you cannot
quench what was never forged, you cannot temper what was never quenched, and the module
refuses each impossibility with a sentence before anything is rolled.

## The methods

Eleven, gated across five levels. `AFTER` in `rules/blacksmith.py` holds the
prerequisites; the track file holds the prose.

| Method | Level | Must follow | Role |
|---|---|---|---|
| smelt | 1 | — | ore → metal; burns fuel; exotic+ metal needs a rare+ fuel |
| forge | 1 | — | shape on the anvil; burns fuel; needs a base item |
| quench | 1 | forge | fix hardness; the bath's nature soaks into the steel |
| flux | 2 | — | cleansing: strips the drawbacks of dirty **ore** (and only ore) |
| rivet | 2 | — | cold-join fittings: hafts, grips, guards, bindings |
| alloy | 3 | smelt | melt metals together; novel same-tier pairs come out one band rarer |
| temper | 3 | quench | brittleness → spring; the first requirement of quality |
| draw | 4 | forge | wire and thin section; a shaping method |
| fold | 4 | forge | pattern-welding; the other shaping method |
| hone | 4 | forge | the final edge; a finishing method |
| polish | 5 | hone | mirror finish; nothing may follow it |

**Quality ladder** (`quality_of`): *plain* by default; *fine* = temper + (hone or
polish); **masterwork** = temper + (fold or draw) + (hone or polish). Masterwork is the
book's rule verbatim — +1 enhancement on attack rolls for a weapon (never damage), check
penalty lessened by 1 for armour — and the chain's DC is never below 20, the Craft
skill's own masterwork-component number.

**DC**: the hardest material's stated `craft_dc`, else 5 + 5 × tier rank; +2 per stage
beyond the first; floor 20 for masterwork.

**Rounding**: costs and penalties round **down**, benefits round **up** — the same rule
`rules/crafting.py` states, restated because the smith's version bites on weight: a 4 lb
longsword in mithral (×0.5) is 2 lb, and a 5 lb one would be 2 lb too.

**The deed**: level 5 requires having worked legendary metal. The gate opens from level
4 by the novel-alloy rule — two *distinct* metals of the same tier alloyed together come
out one band rarer, so two exotic skymetals in one crucible are a legendary melt. The
ceiling checks the inputs, never the stepped-up output; gating on the output is the
unreachable-deed bug the Herbalist's `_deeds_note` records.

## The catalogue

112 materials across eight kinds, every tier populated. Grouped below by kind; each line
is the material's mechanical identity. Anything the effect vocabulary cannot say is
prose in the entry's `text` with **no fake spec** — the creature import's rule.

### Ores (20) — *mined*

| Tier | Entries |
|---|---|
| common | iron ore, bog iron (slag-brittle −1 damage until fluxed), copper ore, tin ore, lead ore, calamine |
| uncommon | cinnabar ore (*risky*: fume save or sickened), silver ore, gold ore, nickel ore, cold iron ore |
| rare | platinum ore, mithral ore |
| exotic | adamantine ore, abysium ore (*risky*: daily save or sickened), djezet seep, inubrix ore, noqual ore, siccatite ore (*risky*: 1 fire/round bare-handed) |
| legendary | horacalcum ore |

### Metals (21)

| Tier | Entries |
|---|---|
| common | iron, wrought iron, bismuth, copper, tin, lead (lining blocks scrying), zinc |
| uncommon | silver (plated: bites lycanthropes), gold, cold iron (bypasses DR of demons and fey; **costs double** — the metal forgives no reworking), viridium (*risky*: wounds fester, Fort 14 or sickened a day) |
| rare | platinum, star iron (counts as cold iron; sky-fallen), mithral (**weight ×0.5**; armour a category lighter, max Dex +2, ACP −3) |
| exotic | adamantine (ignores hardness < 20; keeps its masterwork edge; armour DR 3/2/1 —), abysium (*risky*: Fort 18 or sickened per unshielded day; glows), djezet (liquid always; quickens spellwork), inubrix (ghost iron: passes through iron and steel), noqual (magic slides off; +2 saves vs spells as armour), siccatite (*risky*: 1 fire **or** 1 cold per round of bare contact — including the wielder's grip) |
| legendary | horacalcum (+1 initiative; time runs slow around it) |

No two same-tier metals are reskins, and the test suite pins the three famous ones:
cold iron's identity is *whom it hurts*, mithral's is *what it weighs*, adamantine's is
*what it ignores* — three different effect sets, asserted pairwise unequal.

### Alloys (15)

common: steel, bronze, brass, pewter · uncommon: electrum, bell bronze (signal ring),
high-carbon steel (holds its edge), pattern steel (watered spring), nexavaran steel
(cold iron at 1.5× instead of 2×) · rare: elysian bronze (+1 damage vs magical beasts
and monstrous humanoids), living steel (self-repairing; harvested), fire-forged steel
(fire resist 2), frost-forged steel (cold resist 2) · exotic: singing steel (+2 Perform
with the metal in the act) · legendary: wyrmsteel (fire resist 5; adamantine's contempt
for hardness; more legend than recipe).

### Fuels (10)

common: peat, coal, charcoal · uncommon: coke, bone char · rare: dwarven hearthcoal,
**dragonfire coal** (*risky*; the rare-tier fuel that exotic+ smelting requires — the
"adamantine does not melt over charcoal" rule made purchasable) · exotic: salamander
cinder (*risky*, 1 fire nearby), efreet brand · legendary: phoenix ash ember (relights
itself).

### Fluxes (9)

common: limestone, silica sand, potash · uncommon: borax, bone ash, crushed quartz ·
rare: consecrated chalk (work counts as blessed for rites) · exotic: abyssal salt
(*risky*; the work reads faintly evil) · legendary: stardust flux (makes skymetals
miscible).

### Quenchants (11)

common: water, quenching brine, quenching oil · uncommon: whale oil, glacier melt, mercury bath
(*risky*: fume save) · rare: blessed water (edge counts blessed; undead flinch), troll
blood (*risky*; metal knits its cracks), wyvern blood (*risky*: first wound carries the
venom, Fort 17 or 1d4 Con) · exotic: dragon blood (*risky*; fire resist 2 on armour),
styx water (*risky*: Will 16 or lose the last minute).

### Fittings (16)

common: ash haft, oak haft, bone grip, leather grip, cord-wrapped grip, brass guard,
steel crossguard · uncommon: wire-wrapped grip (+2 CMD vs disarm), sharkskin grip (never
slips wet), mammoth ivory grip, darkwood haft (**weight ×0.5**) · rare: ironwood haft
(wood for druids, strength of steel), wyroot haft (stores a point of ki), dragonhide
grip (never burns) · exotic: angelskin binding (muffles evil auras), fiend bone core
(*risky*; it whispers).

### Treatments (10)

common: bluing (rust-proof), oil blackening (+1 Stealth in darkness), acid etching ·
uncommon: cold iron blanching (counts as cold iron until worn), alchemical silver
plating (bypasses DR/silver at −1 damage), gold gilding, lead lining (blocks scrying) ·
rare: ghost salt blanching (strikes incorporeal at half), holy anointing (blessed for
one battle) · exotic: adamantine edging (the edge ignores hardness; the blade beneath
does not).

## Worked examples

### A cold iron longsword, start to finish (Blacksmith 2)

Charge: **cold iron ore** (uncommon, mined underground), **charcoal**. Base:
`longsword`. Chain: **smelt → forge → quench**.

Cold iron ore is uncommon, so a Blacksmith 2 (ceiling: uncommon) may work it. Charcoal
feeds the fire; quench follows forge, so the grammar holds. DC: the ore states 15, +2 ×
2 extra stages = **19**. Quality: plain (no temper). Result: *Cold Iron Longsword*,
uncommon, 4 lb, carrying the ore's effect — smelts to cold iron, bypasses the DR of
demons and fey — and the text's warning that the work costs double. Success is a
first-time craft at the smith's own band: 3 MP + 4 MP for the two extra stages.

### A mithral shirt (Blacksmith 3)

Charge: **mithral** (rare, bought), **charcoal**. Base: `chain shirt`. Chain: **smelt →
forge → quench**.

Mithral is rare — exactly a Blacksmith 3's ceiling. DC: mithral states 20, +4 for
stages = **24**. Result: *Mithral Chain Shirt*, rare, carrying mithral's identity: half
weight, one category lighter, max Dex +2, ACP eased by 3 (prose, honestly marked — the
vocabulary has no ACP type, so no fake spec).

### An adamantine masterwork warhammer (Blacksmith 4)

Charge: **adamantine** (exotic), **dragonfire coal** (rare fuel — charcoal would be
refused: exotic metal does not melt over it). Base: `warhammer`. Chain: **smelt → forge
→ quench → temper → fold → hone**.

Temper follows quench, fold and hone follow forge; temper + fold + hone is the
masterwork ladder. DC: adamantine states 25, +10 for five extra stages = **35** (well
above the masterwork floor of 20 — this is hard). Result: *Masterwork Adamantine
Warhammer*, exotic: +1 enhancement on attack (masterwork, the real spec), ignoring
hardness below 20, never losing its edge, DR if ever worn as armour — and six stages of
chain pay 10 MP on top of first-time's 3.

## INTEGRATION NOTES

Things this class wanted from shared code and deliberately did not touch, because
sibling classes were being built against the same files in parallel:

- **`rules/registry.py` — a "materials" Kind.** `blacksmith.materials()` carries its own
  shipped-plus-homebrew walk (the `worldclass.tracks()` pattern) instead of registering
  `Kind(id="materials", folder="materials", key="materials", ...)`. Registering it would
  give the homebrew bench a generated editor for metals for free, and would let
  `registry.load_raw("materials")` replace the private loader. One entry in `KINDS` plus
  deleting `blacksmith.load_dir`/the cache is the whole change.
- **Bench UI wiring (`play/craft_views.py`, templates).** `preview(level, chain, stock)`
  returns the same shape of problems/name/dc/effects contract as `crafting.preview`
  precisely so a bench page can be wired the way the herbalist bench was: grey the
  button on problems, show the itemised DC, list effects and removals. Nothing renders
  it yet.
- **Dispatch in the craft-action flow.** `TRACK_ID`, `CraftError`, `Chain` and `preview`
  mirror `rules/crafting.py`'s names so the GM's craft op can route on the track id —
  `{"herbalist": crafting, "blacksmith": blacksmith}[track].preview(...)` — without
  either module importing the other. The routing table does not exist yet and belongs
  wherever `craft_action` currently assumes herbalism.
- **Acquisition: mining excursions.** `source: "mined"` and `biomes` are populated on
  every ore precisely so the foraging/excursion system (`rules/foraging.py`, the
  survival flow) can offer "prospect here" the way it offers "forage here". Until then
  `preview(stock=None)` assumes the smith has what the chain names, exactly as the
  herbalist tests' satchel-less calls do.
- **Engine craft-op glue and MP award.** `worldclass.award` already scores a blacksmith
  craft (stages, risky, tier gap, the deed via `deed_done`) with zero changes — the
  glue that calls it after a successful forge roll is the same glue the herbalist bench
  uses and was not duplicated here.
- **Scene-state tool gating.** `fixed_tools` lists the furnace and the two high forges;
  like the herbalist's still, whether the smith is standing near one is scene state the
  bench must ask the scene, not the sheet.
