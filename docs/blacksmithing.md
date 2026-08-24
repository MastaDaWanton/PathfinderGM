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
| temper | 3 | quench | brittleness → spring; half of the quality ladder |
| hone | 3 | forge | the final edge; the other half of the quality ladder |
| draw | 4 | forge | wire and thin section; mail and springs |
| fold | 4 | forge | pattern-welding; named and watered steels |
| polish | 5 | hone | mirror finish; stands in for hone; nothing may follow it |

**Quality ladder** (`quality_of`): *plain* by default; *fine* = temper **or** a finishing
method; **masterwork** = temper **and** a finishing method (hone or polish). Masterwork
is the book's rule verbatim — +1 enhancement on attack rolls for a weapon (never damage),
check penalty lessened by 1 for armour — and the chain's DC is never below 20, the Craft
skill's own masterwork-component number.

`method_help` in the track file carries the structured tooltip for every method —
`does` (the effect in numbers), `needs` (what makes it legal), `for` (what a player
reaches for it to accomplish). A test asserts the tooltip set and the method set match
exactly, because a method with no tooltip is a button whose effect the player can only
learn by spending materials on it.

### Masterwork reachability — a measured finding

**Masterwork is reachable at Blacksmith 3, DC 20**, for both vessels the enchanter is
likely to be handed:

| Piece | Level | Chain | DC |
|---|---|---|---|
| Masterwork longsword | 3 | smelt → forge → quench → temper → hone (steel, charcoal) | 20 |
| Masterwork breastplate | 3 | smelt → forge → quench → temper → hone (steel, charcoal) | 20 |

This is a **change from phase one, made because the first ladder was a dead end.**
`rules/enchanter.py` refuses every binding whose vessel is not masterwork — at Enchanter
*1*, with the message "Commission one from the smith or the leatherworker first". The
original ladder also required a shaping method, and fold and draw are Blacksmith 4, so
the entire enchanting economy sat behind 140 MP of a track the enchanter may never have
taken. In 1e masterwork is DC 20 professional work, purchasable in any city — not a
legendary feat — so it belongs with the professional methods, and `hone` moved to level
3 to put it there. Fold and draw stay at 4 as what they always were: pattern-welding and
wire-drawing, which make named steels and mail, not quality by themselves.

The gate is still real rather than a formality — a Blacksmith 2 attempting it is told
"Temper is learned at Blacksmith 3" — and buying a masterwork item remains the early
enchanter's path, exactly as the book intends.

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

## The dispatch surface

The bench renders five crafts through one template, so this module exposes the shape
`rules/crafting.py` established:

| Call | Does |
|---|---|
| `chain_from_body(body)` | the bench's POST JSON → a `Chain`. Tolerant: a missing key is an empty chain, not an error. Accepts `base`/`item`/`weapon`/`armour` for the base item, and comma-joined strings for scriptless forms |
| `stock_from_body(body)` | `{"stock": {...}}` → `{material id: count}`, discarding junk |
| `check_terms(actor, level)` | itemised **d20 + track level + ½ character level + Intelligence** |
| `check_bonus(actor, level)` | the sum of those terms |
| `preview(level, chain, stock=None, actor=None)` | the whole result; with an `actor` it also carries `bonus`, `terms` and `chance` |
| `Result.as_dict()` | name, tier, rank, stages, dc, risky, problems, effects, specs, consumes, output, bonus, terms, chance |

**Intelligence, not Wisdom.** Craft is an Int skill in 1e and smithing is Craft (weapons)
or Craft (armour). Herbalism's Wisdom is authored in the Herbalist document, which speaks
for that track alone — it is not the precedent for a track whose skill has its own
governing ability.

## The output contract

`Result.output` is the inventory item, so a forged sword can actually be wielded rather
than being a paragraph:

```
{"id", "name", "kind": "crafted", "craft": "blacksmith", "tier", "rank", "count": 1,
 "effects": [str], "specs": [validated effectspec], "from_materials": [ids],
 "masterwork": bool, "quality": "plain|fine|masterwork", "weight_lb",
 "weapon": "<weapons.json key>" | None, "armour": "<tables.ARMOUR key>" | None,
 "slot": "armor" | "shield" | "hands" | None,
 "wearable": bool, "usable": False, "how": []}
```

`masterwork` is surfaced as its own boolean rather than left implicit in `quality`,
because it is the fact *another track* asks about — the enchanter refuses a vessel that
does not assert it, and re-deriving that from a quality string on the far side would be
a second copy of the rule waiting to drift. `usable`/`how` are stated and empty: a forged
piece is equipment, nothing is drunk or thrown, and a pack rendering every craft's output
should not have to special-case this one.

## Icons

`KIND_GLYPH`, one distinct emoji per kind, from the forge's own vocabulary. Herbalism
owns 🌿 🍄 🦴 ☠️ and nothing here reuses them.

| ⛏️ ore | 🪨 metal | ⚙️ alloy | 🔥 fuel | 🧱 flux | 💧 quenchant | 🔩 fitting | 🛠️ treatment |
|---|---|---|---|---|---|---|---|

## Acquisition

The craft-action button is the one hub for *obtaining* material. This track supplies the
data; the page supplies the UI. Every material carries `obtain` — `mined`, `bought`,
`gathered` or `harvested` — and whatever that excursion needs to promise: a biome to dig,
a price to pay, a creature to cut.

| Excursion | Serves | Requires | Entries |
|---|---|---|---|
| `prospect` — "Prospect for ore" | mined | a biome | 36 |
| `buy` — "Buy from the market" | bought | a market | 54 |
| `gather` — "Gather from the land" | gathered | a biome | 11 |
| `salvage` — "Harvest from a carcass" | harvested | a carcass | 11 |

`obtainable(kind, biome=..., creature=...)` answers what an excursion could turn up
*here*. Mining is the flagship and the reason every ore carries biomes: a smith in the
mountains prospects up iron and silver ore, and never bog iron or silica sand. A material
with **no** biomes is available on any ground (water is water wherever you stand) — which
is deliberately not the same as one whose biomes exclude here. Naming no creature yields
**nothing** rather than everything, so a player cannot skin thin air and walk away with a
phoenix ember; creatures match on name fragments, so "young red dragon" finds the dragon
entries without a bestiary lookup.

### One shelf, two questions

`content/materials` is a single shelf shared by all five crafts, and `kind` cannot tell
them apart — `treatment` appears in all four shipped catalogues and `fitting` in two. So
provenance decides: each entry is stamped with the file it shipped in, and

- `materials()` stays **shelf-wide** — a smith may rivet a leatherworker's grip onto a
  blade, and a chain naming one must resolve it;
- `mine()` is the narrower question the bench and the excursions ask.

Measured when this was missed: prospecting for ore in the mountains turned up wyvern hide
and wyvern sinew. Homebrew, attributable to no shipped catalogue, shows on every bench
rather than none — the convention the shelf commit already settled.

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

Temper follows quench, fold and hone follow forge. Temper + hone is what makes it
masterwork; the fold is the smith signing it — a pattern-welded head, one more stage of
MP and DC, and no change to the quality it would have had without it. DC: adamantine
states 25, +10 for five extra stages = **35** (well above the masterwork floor of 20 —
this is hard). Result: *Masterwork Adamantine Warhammer*, exotic: +1 enhancement on
attack (masterwork, the real spec), ignoring hardness below 20, never losing its edge,
DR if ever worn as armour — and six stages of chain pay 10 MP on top of first-time's 3.

### Prospecting for the metal in the first place

A smith standing in the mountains calls `obtainable("mined", biome="mountain")` through
the craft-action button and gets 22 entries — iron, copper, lead, silver, gold, nickel,
platinum, mithral and horacalcum ore, the mountain skymetals (djezet, noqual, siccatite),
star iron, viridium, cinnabar, coal, dragonfire coal and crushed quartz. In a swamp the
same button offers exactly one thing: **bog iron**. (Peat is in that swamp too, but it is
`gathered`, not mined — a different excursion and a different button.) Adamantine,
abysium and inubrix are `underground`: they want a delve, not a hillside.

## INTEGRATION NOTES

Things this class wanted from shared code and deliberately did not touch, because
sibling classes were being built against the same files in parallel:

- **`rules/registry.py` — a "materials" Kind.** `blacksmith.materials()` carries its own
  shipped-plus-homebrew walk (the `worldclass.tracks()` pattern) instead of registering
  `Kind(id="materials", folder="materials", key="materials", ...)`. Registering it would
  give the homebrew bench a generated editor for metals for free, and would let
  `registry.load_raw("materials")` replace the private loader. One entry in `KINDS` plus
  deleting `blacksmith.load_dir`/the cache is the whole change.
- **Bench UI wiring (`play/craft_views.py`, templates).** The dispatch surface is now
  complete on this side — `chain_from_body`, `stock_from_body`, `check_terms`,
  `check_bonus`, `preview(..., actor=)` and an `as_dict` carrying every key the brief
  named. Nothing renders it yet; the page is yours.
- **Dispatch in the craft-action flow.** The routing table still does not exist. It
  belongs wherever `craft_action` currently assumes herbalism:
  `{"herbalist": crafting, "blacksmith": blacksmith, ...}[track]`, with no module
  importing another.
- **Putting `Result.output` in the pack.** The item is built and shaped for the
  inventory, but nothing writes it to a character. Whoever owns `rules/sheet.py` needs
  to accept `kind: "crafted"` items and honour `slot`, `weapon` and `armour` so the
  thing can be equipped; this module deliberately did not touch the sheet.
- **Worn-item effects reaching the Actor.** `output["specs"]` are validated effectspec
  and the masterwork +1 is a real `combat_mod`, but nothing applies a *worn* item's
  specs to a character — the same gap `docs`' sibling notes record. A masterwork sword
  in the pack is correct data that currently changes no roll.
- **Acquisition UI.** The data half is done: `obtain` on all 112 entries, `ACQUISITION`
  declaring four excursions, and `obtainable()` filtering by biome and by creature. The
  excursion flow, the roll that decides how much is found, and the button itself are
  yours. `preview(stock=None)` still assumes the smith has what the chain names, which
  is what the rules tests want.
- **A shared `obtain` dialect.** This track writes a flat `obtain: "bought"` beside
  `price_gp`/`from_creatures`/`biomes`, per its brief; the alchemist catalogue writes a
  nested `{"how": ..., "market": ..., "price_gp": ...}`. `from_dict` reads **both**, so
  nothing is silently dropped either way, but the shelf would be better with one shape.
  Normalising is a data pass over four files plus one loader — not this track's call to
  make alone.
- **`mine()` vs `materials()` should probably be a shared helper.** Every track needs
  the same "whose material is this" split now that the shelf is shared, and four copies
  of a provenance rule is the shape CLAUDE.md warns about. It is eight lines here and
  wants to be eight lines in `rules/registry.py` instead.
- **Engine craft-op glue and MP award.** `worldclass.award` already scores a blacksmith
  craft (stages, risky, tier gap, the deed via `deed_done`) with zero changes — the
  glue that calls it after a successful forge roll is the same glue the herbalist bench
  uses and was not duplicated here.
- **Scene-state tool gating.** `fixed_tools` lists the furnace and the two high forges;
  like the herbalist's still, whether the smith is standing near one is scene state the
  bench must ask the scene, not the sheet.
