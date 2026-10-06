# Alchemy revamp: inventory of what exists today

Step 1 of the alchemy revamp, taken 2026-10-04 on branch `alchemy/research` (off
`origin/master` e028885, which already carries the herbalism and blacksmithing revamps).
Nothing here is a design. Every count was produced by running Python against the shipped
files and the live rules modules (scratch scripts, not committed); every claim names a
file and line. Where a number disagrees with `docs/alchemy.md`, the number here is the
measured one and the doc is stale.

The research is `docs/alchemy-prior-art.md`; the owner's questions are
`docs/alchemy-questions.md`.

---

## 0. The headline findings

1. **The chain's potency never reaches the item.** `preview` multiplies react ×1.25,
   sublime ×1.25 and catalyze ×1.5 (`rules/alchemist.py:58-62`, `:750-752`) and reports
   it on the `Result`, but the `output` dict it builds (`:801-814`) has no `potency` key.
   `crafting.from_stock_dict` then defaults it to 1.0 (`rules/crafting.py:388`).
   Measured: alchemist's fire previews at potency 1.25, and the stock on the shelf has
   potency 1.0. Every multiplier in the craft is display-only.
2. **The documented classics do not come out as the classics.** Run through `preview`
   at Alchemist 5 with the recipe table's own materials and chains (`docs/alchemy.md:205-224`):
   - **Antiplague** is refused: Filter "has nothing to hold back" because silver salt and
     camphor carry no harm.
   - **Smokestick** comes out drinkable (no harmful spec, so `_how_for` says drink).
   - **Sunrod** comes out as a **blade coating** that deals 1d4 fire (phosphorus), with
     the light as narration.
   - **Liquid ice** and **itching powder** come out as coatings (no vessel in the recipe).
   - **Alchemist's fire** deals **2d6 fire at once** (brimstone 1d6 plus naphtha 1d6,
     summed), with no attack roll, no splash and no second-round burn. The book is 1d6
     plus 1d6 the next round, a ranged touch attack, and 1 splash.
   - **Antitoxin** is two +1 alchemical bonuses to Fortitude against ingested poison. Two
     bonuses of one type do not stack, so it is +1. The book's antitoxin is +5.
3. **A thrown flask has no attack roll and no splash.** `_op_use_item` says so in its own
   docstring: "That attack is not emitted here" (`rules/engine.py:11243-11245`). The
   damage intents go straight onto the target. `SPLASH_RADIUS_FT` is declared
   (`rules/consumables.py:45`) and read nowhere.
4. **Brewing spell potions loses money, and the book's price is ignored.** A brewed
   potion is priced by tier, not by spell (`rules/pricing.py:33-39`, `:139-170`):

   | Potion | App worth | Book price (50 gp × spell level × caster level) | Bought materials |
   |---|---|---|---|
   | cure light wounds | 6 gp | 50 gp | 28 gp |
   | cure moderate wounds | 20 gp | 300 gp | 26 gp |
   | invisibility | 20 gp | 300 gp | 178 gp |
   | haste, fly | 60 gp | 750 gp | 1,750 gp |

   A potion of haste costs 1,750 gp of azoth and crystal retort and sells for 60 gp.
   The book price is confirmed against the Core Rulebook's potion rules
   (`docs/alchemy-prior-art.md` §1.2).
5. **No discovery is possible on any alchemy material.** All 139 alchemist materials
   resolve through the shared material door (`rules/materials.py:43`), and the knowledge
   module counts properties only in the forge's fields (`weapon`, `armour`, `working`,
   `quench_mark`). Measured: `knowledge.property_keys` returns **0 for all 139**.
6. **Half the shelf does nothing.** 70 of 139 materials have no effects at all, and 5
   more are narrative only: **75 of 139 (54%) carry zero executable effects**. 61 carry
   one, 3 carry two, **none carries three**. The herbalism and forge rule is at least
   three discoverable traits.
7. **The hybrid door is one-way.** 63 herbs are flagged `hybrid`, and the contract says a
   hybrid "then also appears on the alchemist's shelf" (`docs/campaign-format.md:343`).
   It does not: `alchemist.get("phoenix-feather")` raises KeyError, and so do Shadowvine
   and Glowvine. Meanwhile **49 herbs carry `external` effects** that the herbal bench
   drops as "alchemy only", and no bench can use them. The other direction does work: 8
   alchemist rows (spirits, vinegar, oil, beeswax and the neutralizers) serve the herb
   bench (`rules/ingredients.py:345-375`).
8. **Volatility's stakes are written and never applied.** The preview writes the mishap
   sentence (`rules/alchemist.py:907-923`), but nothing in `play/craft_views.py` or the
   engine applies it. A failed volatile chain loses the materials and nothing else.
   Quicksilver's and lead dust's "to the handler" tax is encoded as a `damage` spec
   (`content/materials/alchemist-materials.json`), so it lands on whoever **drinks or is
   hit by** the product, never on the alchemist.
9. **Spell potions have no caster requirement.** Any character at Alchemist 3 brews a
   potion of invisibility; Alchemist 4 brews haste. PF1e's Brew Potion needs the feat,
   caster level 3 and the spell. Five of the 44 are **personal-range** spells
   (longstrider, expeditious retreat, comprehend languages, see invisibility, false
   life). PF1e bars them: "Spells with a range of personal cannot be made into potions"
   (`docs/alchemy-prior-art.md` §1.2).
10. **The PF1e alchemist character class does not exist in the app.** `content/classes/`
    has 12 classes and no alchemist. No code knows bombs, mutagens or extracts. The spell
    corpus does carry the class's extract list: **408 spells** on the `alchemist` list
    (273 at levels 1-3), and 33 of the 44 shipped potions are on it.

---

## 1. The world class (`content/world-classes/alchemist.json`)

- **Namespace:** the file says outright that this is the world class, not the PF1e
  character class, and that "the two namespaces never meet in code" (line 6).
- **Thresholds** 25 / 65 / 50 / 100 (line 8): the Herbalist's pre-revamp curve.
- **Five levels, not three** (lines 24-86). The herbalist and blacksmith now run three
  levels plus endless levels with two perk picks each (`herbalist.json:13`,
  `blacksmith.json:13` carry `endless`). The alchemist has **no `endless` block** and is not
  `capped`, so levels 6 and up exist but grant nothing (`rules/worldclass.py:296-300`).
- **Milestone:** level 5 waits on the deed `legendary-work`, any successful craft at
  legendary tier (lines 14-23).
- **Fixed tools** (laboratory, athanor, philosopher's bench) are "declared and
  deliberately unread" until property ownership exists (lines 147-153). The PF1e
  alchemist's lab (+2 Craft) has no counterpart in play.

| Level | Methods | Max tier | Tools |
|---|---|---|---|
| 1 | calcine, dissolve, seal | common / mundane | travelling alchemy kit, iron crucible |
| 2 | filter, precipitate | uncommon / volatile | glass alembic, filter frames |
| 3 | react, stabilize | rare / magical | alchemical laboratory |
| 4 | sublime | exotic / planar | athanor |
| 5 | catalyze | legendary / mythic | philosopher's bench |

### What each method does (`method_help`, lines 99-146; rules in `rules/alchemist.py`)

| Method | Rule in code | Potency | Shape word |
|---|---|---|---|
| calcine | none beyond being legal; "a material that survives fire" is prose, not checked | ×1.0 | Calx |
| dissolve | none; "needs a solvent" is prose, not checked | ×1.0 | Solution |
| seal | must be last (`FINISHING`, `:69`, `:735-737`); seal before react refused (`:830-842`) | ×1.0 | Sealed Flask |
| filter | strips every poison and penalty from the specs; refused when there is nothing to strip (`:757-783`) | ×1.0 | Filtrate |
| precipitate | none; "a solution" is prose, not checked | ×1.0 | Precipitate |
| react | needs a solvent or a pouring herbal intermediate (`:845-864`) | ×1.25 | Admixture |
| stabilize | lifts the two-volatile refusal and `needs_stabilizer` (`:867-884`) | ×1.0 | none |
| sublime | none; "needs the athanor" is prose, not checked | ×1.25 | Sublimate |
| catalyze | none; "legendary material" is prose, not checked | ×1.5 | Arcanum |

Five of the nine methods have **no rule of their own**: calcine, dissolve, precipitate,
sublime and catalyze are legal in any order on anything. What they do differently is
only a word in the product's name and, for two of them, a multiplier that never reaches
the item (finding 1).

---

## 2. The rules module (`rules/alchemist.py`, 948 lines)

- **Shape:** the pre-revamp chain bench. One `Chain` (methods plus materials) is judged
  whole by `preview` (`:680-827`) and rolled once. There are no intermediates: nothing a
  chain makes partway lands on the shelf. The herbalist moved to one roll and one minigame
  per method on 2026-10-02, and the smith to the same on 2026-10-04.
- **The check:** d20 + Alchemist level + half character level + Int (`:570-595`). The
  shown chance clamps to 5-95 and the bench honours natural 1 and 20 (`:598-607`;
  `play/craft_views.py:625`). The herbal bench has no naturals on a skill check
  (`docs/alchemy.md:467-473` records this as an open call).
- **The DC** (`:887-904`): the highest authored `craft_dc`, otherwise 5 + 5 × tier rank;
  +2 per stage past the first; +3 per volatile past the first. A six-stage legendary chain
  reaches DC 46 (`docs/alchemy.md:415`).
- **Gating:** method by level, material by tier ceiling (`:717-728`); two volatiles need
  Stabilize; `needs_stabilizer` needs it alone; react needs a medium; seal is last.
- **Tier of the product** = the rarest material's (`:745-748`).
- **How it is used** is inferred (`_how_for`, `:665-677`): anything harmful in a vessel is
  thrown; harmful without a vessel is a coating; anything else is drunk. Spell potions
  declare their own `how`.
- **Spell potions** match on the exact material set **and** the exact method sequence
  (`:496-510`). A match replaces the materials' specs with the potion's (`:790-796`).
- **Output** (`:801-814`): `id, name, kind="crafted", craft, tier, rank, count, effects,
  specs, from_materials, usable, how, wearable, slot, holds_spell, caster_level, glyph`.
  **No `potency`, no `quality`, no price.**
- **Mastery:** the per-recipe award `worldclass.award` (`rules/worldclass.py:525-560`):
  first time 3, repeat 1 (three times), risky 2, +2 per stage past the first, mishap 1.
- **Acquisition** (`:343-414`): four excursions (market run, quarry, field gathering,
  harvest from a kill), all data.

### Batch

The old bench rolls **one d20 per dose** (`play/craft_views.py:493-613`, "A batch is N
separate attempts"). The herbal and forge benches roll once for a whole stack, by the
owner's ruling.

---

## 3. The materials (`content/materials/alchemist-materials.json`)

**139 materials** (the doc says 116 in one place and 137 in another; both are stale).

| Kind | Common | Uncommon | Rare | Exotic | Legendary | Total |
|---|---|---|---|---|---|---|
| reagent | 24 | 13 | 4 | 3 | 2 | 46 |
| gland | 3 | 5 | 9 | 3 | 3 | 23 |
| solvent | 8 | 5 | 2 | 1 | 0 | 16 |
| vessel | 4 | 3 | 3 | 2 | 1 | 13 |
| salt | 5 | 3 | 2 | 1 | 0 | 11 |
| treatment | 7 | 2 | 2 | 0 | 0 | 11 |
| essence | 1 | 2 | 1 | 4 | 2 | 10 |
| catalyst | 3 | 1 | 3 | 0 | 2 | 9 |
| **total** | **55** | **34** | **26** | **14** | **10** | **139** |

- **Flags:** 29 volatile, 46 risky, 3 `needs_stabilizer`.
- **Effects:** 72 effect entries across the shelf, by type: damage 32, save_gate 14,
  narrative 5, save_mod 4, heal 4, remove_condition 3, resistance 3, skill_mod 2,
  fast_healing 2, apply_condition 1, combat_mod 1, temp_hp 1. `effectspec.executable`
  passes 67 of them and fails the 5 narratives.
- **Per material:** 70 have no effects, 5 are narrative only (fire beetle gland, smoke
  resin, slick jelly, oil of cloves, ectoplasm residuum), 61 carry one executable effect,
  3 carry two, **0 carry three**.
- **No drawbacks of their own.** No material carries a negative for its user except as
  the product's harm. There is no working layer (how it behaves at the bench) at all.
- **Effect notes that change the meaning, which the engine does not read:**
  - quicksilver and lead dust: "to the handler" (finding 8);
  - sunmetal filings: "harms only undead";
  - saint's tallow: "against undead only";
  - pyre gel and white phosphorus: "burns again the following round";
  - drake's breath sac: "a 15-foot cone";
  - gray ooze core: "corrodes metal and wood";
  - the save_mods' "against ingested poison" or "against disease".

  As specs, sunmetal deals 1d6 to the living, and a cone is a single target.
- **Acquisition:** bought 73, harvested 36, gathered 17, mined 13. Every row declares one.

### Dead weight

- **40 materials have no effect and appear in no spell potion.** They are only names in
  the recipe table, or not used at all: saltpetre, turpentine, distilled water, brine,
  sal ammoniac, verdigris, quick-match cord, quenching clay, every vessel but the glass
  vial and the crystal retort, and all four legendary transformers (prima materia,
  philosopher's mercury, orichalcum grains, world-egg shell).
- **Legendary is hollow.** Prima materia ("becomes anything the chain asks") and
  philosopher's mercury ("never itself spent") have no effects and no rule. Catalyze does
  not leave the catalyst unspent: `consumes` takes it like anything else.
- **30 effectless materials exist only as spell-potion keys:** the animal hairs, feathers,
  fur, gum arabic, talc, agate, licorice, reed, gauze and so on.

### Links to the other shelves

- **Forge metals, through `material`** (9 rows): iron filings and the iron flask → iron;
  lead dust → lead; cinnabar → quicksilver; brass casing → brass; mithral dust → mithral;
  star-iron dust → star-iron; the adamantine crucible → adamantine; powdered silver →
  silver. Each parent is a forge document (`star-iron` is
  `content/materials/blacksmith-materials.json:1362`), except quicksilver, whose parent
  is the alchemist's own row (`alchemist-materials.json:745`).
- **Herbs, through the shared reagent rows:** 8 alchemist rows carry the herbalist's
  `solvent`, `base_for` or `neutralizer` fields and appear on the herb bench (willow
  charcoal, slaked lime, strong spirits, white vinegar, olive oil, beeswax, fuller's
  earth, rectified spirits).
- **Herbs, through `hybrid`:** none from this file. See finding 7.
- **One id on two shelves:** `basilisk-eye` is both a herb (`content/ingredients/herbs-and-parts.json`)
  and an alchemist gland. `knowledge.resolve("basilisk-eye")` returns the **alchemist**
  document (material first, `rules/knowledge.py:214-218`). `rules/knowledge.py:17` says
  the two id spaces are disjoint and that `tests/test_alchemist.py` pins it; the test
  (`:601-617`) checks material files against each other, not against herbs. I found no
  path where this breaks play today, because the herbarium passes the ingredient object.
  It is a trap waiting for the first caller that passes the id.

---

## 4. Spell potions (`content/materials/alchemist-spell-potions.json`)

**44 potions**: 15 of 1st level (CL 1, uncommon), 20 of 2nd (CL 3, rare), 9 of 3rd (CL 5,
exotic). 40 are drunk and 4 are oils (`how: coat`: magic weapon, magic fang, align
weapon, keen edge). Chains: 33 are `dissolve → react → seal`; 11 add `stabilize`.

- **Effects:** 69 specs, by type: combat_mod 16, ability_mod 10, save_mod 9, heal 3,
  remove_condition 3, speed 5, skill_mod 2, sense 2, immunity 2, temp_hp 2, resistance 1,
  damage_reduction 1, narrative 20.
- **What lands when drunk:** `effectspec.executable` passes 49 and fails 27: the 20
  narratives, plus **all 5 `speed`** and both `sense` specs. `consumables` has a `speed`
  branch (`rules/consumables.py:406-418`), but `_resolve` asks `executable` first and
  narrates anything it fails (`:680-692`). Measured: a potion of longstrider produces no
  intents, only "+10 ft land speed for 1 hour" as narration; haste's +30 ft is narrated.
- **Fully executable potions:** 19 of 44. **Narrative only:** 8 (endure elements,
  comprehend languages, pass without trace, blur, align weapon, water breathing,
  protection from energy, keen edge).
- **Every spell id resolves** in `content/spells/spells.json` (pinned,
  `tests/test_alchemist.py:284`).
- **Personal range in the corpus:** longstrider, expeditious retreat, comprehend
  languages, see invisibility, false life. Invisibility reads "personal or touch".
- **Not on the PF1e alchemist's extract list** (11): mage armor, shield of faith,
  protection from evil, remove fear, longstrider, pass without trace, magic weapon, magic
  fang, remove paralysis, align weapon, keen edge.
- **The cross-craft contract:** `holds_spell` plus `caster_level`. The enchanter's
  book mode consumes such a potion in place of knowing the prerequisite spell
  (`rules/magicitem.py:13-18`, `:392-402`, `:524-545`; pinned by
  `tests/test_magicitem.py:207` and `:254`). It does not check caster level
  (`docs/enchanting.md:472-480`). **Any change to potion ids or `holds_spell` breaks
  enchanting.**

---

## 5. How alchemical things reach play today

| Path | What happens | Where |
|---|---|---|
| **Brew at the old bench** | `/craft/`, Alchemy tab: build a chain, preview, roll, the product lands in `pc.stock` with `craft: "alchemist"` | `play/craft_views.py:38-39`, `:380-430`, `:493-698`; `play/templates/play/craft.html` (1,415 lines) |
| **Drink** | `use_item how=drink` → `consumables.plan` → intents through validation, stamped `origin=item:<id>` | `rules/engine.py:11234-11352`; `rules/consumables.py:595-677` |
| **Throw** | allowed if harmful; damage and conditions land directly on the target; **no attack roll, no splash** | `rules/engine.py:11243-11245`; `rules/consumables.py:641-644` |
| **Coat** | harmful → a `Coating` held for the next hit; benign (declared `coat`) → buffs the wielder | `rules/consumables.py:634-648`; `rules/engine.py:11296-11315` |
| **Apply by route** | herbal products only: `ROUTE_USE` offers ingest, eyes, wound, skin, inhale; `external` is not a route a player can choose | `rules/consumables.py:553-580` |
| **Buy the book items** | alchemist's fire 20 gp, antitoxin 50 gp, sunrod 2 gp are `GEAR` rows with a price and no effect; the outfitting and stall shelves sell them | `rules/goods.py:444`, `:461-462`; `content/rules/stall-lines.json:51` |
| **Weapon row** | the only "Alchemist's fire" in the weapon table is **siege ammunition**: exotic, two hands, 10 lb, 200 gp, no damage | `content/weapons/weapons.json:474-500` |
| **Enchanter** | a `holds_spell` potion is consumed as the prerequisite spell | `rules/magicitem.py:524-545` |
| **Sheet** | `drinkable`, `throwable` and `coatable` are read from the declared `how`, otherwise asked of `consumables.plan` | `rules/sheet.py:4195-4217`; `play/views.py:1365-1425` |

**So, today:**
- A bought alchemist's fire, antitoxin or sunrod does nothing in play (no gear row in
  `content/rules/gear.json`, no specs).
- A brewed alchemist's fire does 2d6 fire with no roll to hit.
- A brewed potion works through the drink door, minus its speed and sense lines.
- The preview's itemised DC (`dc_terms`), volatile marks and mishap line **never reach
  the page**: `craft.html` reads none of them (`docs/alchemy.md:485-489` asked for them;
  never built).

---

## 6. PF1e's three alchemies, and how the app blurs them

| PF1e has | What it is | In the app |
|---|---|---|
| **Craft (alchemy) items** | mundane alchemical goods, made with the Craft skill: alchemist's fire, acid, antitoxin, tanglefoot bag, smokestick, sunrod, thunderstone, tindertwig | the world class's chain bench makes look-alikes from materials; the bought ones are inert gear |
| **Brew Potion** | a magic-item creation feat: caster level 3, the spell, potions of 3rd level or lower that target creatures | the same world class makes 44 spell potions with **no caster requirement**, gated only by Alchemist level and tier |
| **The alchemist class** | bombs, extracts (personal, from a formula book), mutagens, discoveries | **absent**; the corpus carries the 408-spell extract list and nothing uses it |

The world class merges the first two into one bench and one roll, and leaves the third
out. The herbalism boundary (herbalism plan §1) puts "potions, transmutation" on the
alchemy side, which is the second column. The enchanter's potion stand-in makes that
column the hinge between alchemy and enchanting.

---

## 7. Tests that pin today's shape

`grep -l alchemist tests/` finds 16 files. The ones that would move with a revamp:

| File | Tests | What it pins |
|---|---|---|
| `tests/test_alchemist.py` | 50 | five tiers in order; react and stabilize learned together; no method collides with herbalism; volatility ≥ a fifth; the refusals (two volatiles, seal before react, no medium, needs-stabilizer); the volatile DC step; mishap text; herbal intermediates accepted; every potion spell id resolves; potion tier derives from materials; strict potion matching; enlarge person's size buff; Int-based check; output shape; acquisition shape; no id claimed by two crafts (`:601`); glyphs |
| `tests/test_worldclass.py` | 22 (13 mentions) | the alchemist's thresholds and levels through the shared loader |
| `tests/test_benches.py` | 23 (6 mentions) | dispatch through `rules/benches.py:38` |
| `tests/test_magicitem.py` | `:207`, `:254` | a `holds_spell` potion stands in for the spell; a wrong one does not |
| `tests/test_market.py`, `test_i2_market.py`, `test_i7_trade_window.py`, `test_herb_manuals_market.py` | | the alchemist's stall and its priced materials |
| `tests/test_ingredient_tags.py`, `test_use_by_route.py`, `test_materials_shelf.py`, `test_forge_materials.py`, `test_forge_knowledge.py`, `test_herbalist_endless.py`, `test_enchanter.py` | | shared-shelf rows (the 8 herbal reagents), forms of shared metals, the alchemist not offered endless perks |

---

## 8. Old saves

What a save can hold that a revamp must convert or keep:
- `Actor.tracks["alchemist"]`: level (possibly 4 or 5 or more, with no perks), MP,
  `crafted` and `mishaps` keyed by recipe name;
- stock rows with `craft: "alchemist"`: sealed flasks, admixtures, spell potions with
  `holds_spell` (the enchanter consumes these);
- `campaign.recipes` rows with `craft: "alchemy"` (`play/craft_views.py:700-732`);
- herbal jars whose ids carry shape words, which the alchemist accepts as intermediates
  (`rules/alchemist.py:292-318`).

---

## 9. World Bible

`docs/from-world-bible.md:173-211` asks the next export for herbs (`hybrid`, `base_for`,
`solvent`, `neutralizer`) and forge materials (`play.materials[]` with `pieces`,
`weapon`, `armour`, `working`). It asks nothing of alchemy: no reagent fields, no
volatile flag, no potion or formula list. `play.materials[]` (`docs/campaign-format.md:350`)
is described as forge material and would carry an alchemist reagent only by accident.
