# Blacksmithing revamp: prior art sweep

Research for the Blacksmith world class, starting with a pass over the 112 entries in
`content/materials/blacksmith-materials.json` so each material carries typed, rules-backed
effects and discoverable traits, the way herbs now do (`docs/herbalism-revamp-plan.md`).
Compiled 2026-10-03. Same conventions as `docs/herbalism-prior-art.md`: primary sources
(rulebook text via Archives of Nethys or Paizo's PRD, developer posts, patch notes, official or
officially partnered wikis) are marked **[P]**. Officially partnered wikis and UESP are marked
**[W]** where it matters. Fan wikis, press and forums are **[S]**. Anything I could not trace is
in the critic pass at the end.

---

## 0. The headline findings

1. **The book already gives most metals a typed effect, and the catalogue gets several of
   them wrong.** PF1e prints exact numbers for every special material (§1.4). Checked against
   the shipped catalogue:
   - **Mithral** says armour counts lighter "for movement and proficiency". The book says the
     decrease "does not apply to proficiency in wearing the armor". The −10% spell failure is
     also missing.
   - **Fire-forged steel** gives armour fire resistance 2 "once it has drunk a round of flame".
     In the book the *armour* resistance is unconditional; it is the *weapon* that needs 10 fire
     damage, and then it deals +1d4 fire for 2 rounds.
   - **Viridium** is a Fort DC 14 "sickened" save. The book: leprosy on any hit, Fort DC 12; on
     a crit, greenblood oil, DC 13; and the *carrier* must save every 24 hours unless it is kept
     in a lead-lined scabbard. The book also calls it volcanic glass, not a metal.
   - **Abysium** is a Fort DC 18 save. The book has **no save**: the carrier is simply sickened
     while carrying it and for 1d4 hours after. DC 18 belongs to abysium *powder*, a poison.
   - **Horacalcum** is a flat +1 initiative. The book: +1/+2/+3 by armour weight, and +1 attack
     for weapons.
   - **Singing steel** is +2 Perform. That is invented. The book makes it count as alchemical
     silver, lightens armour, and lets the wielder start a bardic performance one action faster.
   - **Inubrix** and **noqual** keep the upside and drop the drawbacks. Inubrix weapons deal
     damage as one size smaller, are always broken, and cannot harm iron or steel. Noqual armour
     adds +20% spell failure "to all magic", and any magic item using noqual costs +5,000 gp to
     create.
2. **PF1e has a built-in rule against mixed-material items.** "If you make a suit of armor or a
   weapon out of more than one special material, you get the benefit of only the most prevalent
   material." Darkwood and mithral both say a part-made item gains nothing ("a battleaxe … do
   not gain any special benefit"). That bears directly on the catalogue's **Adamantine
   Edging**, **Cold Iron Blanching** and **Darkwood Haft**. Wyroot is the exception: the book
   allows "a wooden haft".
3. **PF1e's optional rules already define discoverable working traits for raw materials.**
   *Pathfinder Unchained* gives special raw materials four traits: **easily worked** (double
   progress), **flawless** (no difficulty increase for masterwork or special material),
   **malleable** (no material lost on a bad failure) and **pure** (roll the Craft check twice,
   take the better). They are rules-backed "how it behaves at the forge" traits, as distinct
   from "what it does in the item". That is the two-layer split the catalogue needs.
4. **Games split material identity into two channels, and the ones that did not regretted
   it.** WoW and ESO both send the base metal into *quality or level* and get *typed effects*
   from a separate named add-in (missive, embellishment, trait gem). Wurm Online gives every
   metal a small modifier vector against an iron baseline. Pure tier ladders (Valheim,
   Minecraft, Skyrim) erase identity: a metal is just its tier. Dwarf Fortress gives every
   material real physics numbers, and its creator says per-stone differences "was not a data
   entry thing I could tackle".
5. **Every smithing minigame that shipped was softened or made easier to read afterwards.**
   KCD2's patch 1.2 "Generally rebalanced the blacksmithing minigame" and "Improved visual
   indication of workpiece cooling". RuneScape 3's heat bar shipped without its proposed ×0.5
   penalty for cold metal. OSRS automated the Blast Furnace chores. Vintage Story stopped
   resetting temperature on the anvil. The common complaint is the same as for herbalism: a
   mandatory minigame for routine output (KCD2 horseshoes, Blacksmith Master).
6. **Random quality that can make an item worse draws backlash.** WoW removed Inspiration (a
   random quality bump) for "a lack of decision making and agency for the crafter". Monster
   Hunter Rise's Qurious Crafting, which could make armour worse, kept its randomness but added
   steering modes. ESO still destroys the item when an improvement fails, but the player can
   add tempers until the shown chance reaches 100%, so the risk is chosen, not imposed.
7. **Real smithing gives honest, readable minigame bands.** Heat colour (cherry red 815–870 °C
   through yellow-white), quench severity (brine > water > oil), and temper colour (straw 205 °C
   through blue 337 °C) are all documented tables. Each is a band you stop inside, which is
   exactly a target-zone minigame.

---

## 1. PF1e rules: Craft, masterwork and special materials

### 1.1 The Craft procedure (Core Rulebook)

All from the PRD's Craft page **[P]** https://legacy.aonprd.com/coreRulebook/skills/craft.html
unless marked.

- **Price to time.** Convert the price to silver pieces. Pay **one-third of the price** in raw
  materials. Each week, a successful check adds *check result × DC* in silver pieces of progress.
  The item is done when progress equals the price in sp. You may check by the day instead of the
  week. [S for the one-third and weekly wording: https://www.d20pfsrd.com/skills/craft/]
- **Failure.** Miss by 4 or less: no progress that week. Miss by 5 or more: **half the raw
  materials are ruined** and you pay half the raw material cost again. [S, same page]
- **Hurrying.** You may add +10 to the DC to work faster (progress is multiplied by a bigger DC).
- **Tools.** Improvised tools: −2. Masterwork artisan's tools: +2 circumstance.
- **The DC table (weapons and armour lines):**

| Item | DC |
|---|---|
| Armor or shield | 10 + AC bonus |
| Longbow, shortbow, arrows | 12 |
| Composite bow | 15 |
| Crossbow or bolts | 15 |
| Simple melee or thrown weapon | 12 |
| Martial melee or thrown weapon | 15 |
| Exotic melee or thrown weapon | 18 |
| Very simple item (wooden spoon) | 5 |
| Typical item (iron pot) | 10 |
| High-quality item (bell) | 15 |
| Complex or superior item (lock) | 20 |

- **Masterwork** is a **separate component** made "as if it were a separate item", at **DC 20**.
  Its price is 300 gp for a weapon, 150 gp for armour or a shield (6 gp per piece of
  ammunition). A masterwork weapon gets +1 enhancement on **attack** rolls only. Masterwork
  armour has its check penalty lessened by 1.
- **Repair** uses the item's original DC and costs one-fifth of its price.
- **The core rules give special materials no Craft DC of their own.** The material raises the
  price, so it raises the time (progress is measured against price). Several materials say
  they are "always masterwork; the masterwork cost is included", which implies the DC 20
  masterwork component is part of the job. I found no core line that says this outright
  (see Could not confirm).

### 1.2 Pathfinder Unchained's alternate crafting (optional rules)

**[P]** https://legacy.aonprd.com/unchained/skillsAndOptions/craftingAndProfession.html and
https://www.aonprd.com/Rules.aspx?Name=Special+Raw+Materials&Category=Crafting

- Items have a **crafting difficulty** step from "Extremely simple (DC 5)" to "Extremely
  intricate (DC 35)", each with a base progress per day.
- "When you're crafting a masterwork item or an item made of a special material, its crafting
  difficulty increases by one step." A special material that is also always masterwork
  (adamantine) raises it **two steps**.
- Failing by 5 or more wastes raw material equal to one day's base progress.
- **Special raw materials** carry one of four **traits**. This is the closest thing in PF1e
  to "a material carries discoverable working properties":
  - **Easily worked:** base progress per day is doubled.
  - **Flawless:** making masterwork or special-material items does not raise the difficulty.
  - **Malleable:** failing by 5 or more does not waste material.
  - **Pure:** roll the Craft check twice and take the better.
  - Special raw materials have a *cost* (to buy and sell) and a *crafting cost* (what they count
    for in crafting), and the crafting cost is **always half** the cost. Table 2–6 lists the
    four trait variants for 28 raw materials, from adamantine down to wood.

### 1.3 Hardness and hit points (Core)

**[P]** https://legacy.aonprd.com/coreRulebook/additionalRules.html

| Substance | Hardness | HP per inch |
|---|---|---|
| Glass | 1 | 1 |
| Paper or cloth | 0 | 2 |
| Rope | 0 | 2 |
| Ice | 0 | 3 |
| Leather or hide | 2 | 5 |
| Wood | 5 | 10 |
| Stone | 8 | 15 |
| Iron or steel | 10 | 30 |
| Mithral | 15 | 30 |
| Adamantine | 20 | 40 |

**Fragile** (Ultimate Equipment): a fragile weapon gains the broken condition on a natural 1
attack roll, and a broken fragile weapon is destroyed on another natural 1. Masterwork and
magical fragile weapons lack the flaw unless the item says otherwise. [S, search summary of
https://legacy.aonprd.com/ultimateEquipment/armsAndArmor/weapons.html]

### 1.4 Every special material, with its rules

Primary text for all of these: the AoN special materials page, which prints the full rules and
source page for each **[P]** https://www.aonprd.com/SpecialMaterials.aspx . The Ultimate
Equipment and Core ones are also on the PRD **[P]**
https://legacy.aonprd.com/ultimateEquipment/armsAndArmor/materials.html .
General rule: "If you make a suit of armor or a weapon out of more than one special material,
you get the benefit of only the most prevalent material." (A double weapon may have a
different material on each head. [S, d20pfsrd])

"MW incl." below means the material is always masterwork and the price includes it.

#### Core Rulebook and Ultimate Equipment (on the PRD)

| Material | Applies to | Effect | Price | Hardness / HP per inch | Craft notes |
|---|---|---|---|---|---|
| **Adamantine** (CRB 154, UE 48) | metal weapons, ammunition, armour; not wholly non-metal items | Weapons ignore hardness below 20 when sundering or attacking objects. Armour gives DR 1/— light, 2/— medium, 3/— heavy. MW incl. Steel-type items get +⅓ hp. | ammo +60 each; light +5,000; medium +10,000; heavy +15,000; weapon +3,000 | 20 / 40 | none stated |
| **Cold iron** (CRB 154, UE 49) | items with metal parts | Overcomes DR/cold iron (demons, fey). | weapon ×2 cost; first magic enhancement +2,000 (once, not per ability); double weapon with one cold-iron head +50% | 10 / 30 | "forged at a lower temperature to preserve its delicate properties" |
| **Mithral** (CRB 154, UE 51) | metal items | Half weight. Armour one category lighter for movement (not proficiency). Spell failure −10%, max Dex +2, check penalty −3 (min 0). Weapons count as silver for DR. MW incl. | light +1,000; medium +4,000; heavy +9,000; shield +1,000; other +500/lb | 15 / 30 | "worked like steel" |
| **Alchemical silver** (CRB 155, UE 48) | metal weapons only; not on adamantine, cold iron or mithral | Overcomes DR/silver. Slashing or piercing silvered weapons take −1 damage (min 1). | ammo +2; light weapon +20; one-handed +90; two-handed +180 | 8 / 10 | "A complex process involving metallurgy and alchemy" bonds it to steel |
| **Darkwood** (CRB 154, UE 49) | wooden or mostly wooden items | Counts as masterwork, half weight. Shield check penalty −2. | +10 gp per lb on top of the MW price | 5 / 10 | — |
| **Dragonhide** (CRB 154, UE 49) | armour, shields | One dragon gives MW hide armour for a creature one size smaller; choice scales give banded (2 sizes smaller), half-plate (3) or breastplate/full plate (4), plus a shield if the dragon is Large+. Immune to the dragon's energy type (the item, not the wearer); adding matching protection costs 25% less. Druids may wear it. | twice MW armour of that type | 10 / 10 (hide ½–1 in. thick) | "takes no longer to make than ordinary armor of that type (double all Craft results)" |
| **Angelskin** (UE 48) | leather, hide, studded leather | Evil aura reduced by 10 HD; spells keyed to evil have 20% chance to treat an evil wearer as neutral. MW incl. | light +1,000; medium +2,000 | 5 / 5 | — |
| **Blood crystal** (UE 48) | piercing or slashing weapons with metal; ammunition. **Never armour** ("would feed on the wearer's own wounds") | +1 damage against a target already bleeding. Weapons have half normal hp. Unworked: 500 gp/lb. | ammo +30; weapon +1,500 | 10 / 10 | colour darkens pink → crimson as it feeds |
| **Darkleaf cloth** (UE 49, ARG 27) | padded, leather, studded leather, hide; clothing. Not rigid items | Spell failure −10% (min 5%), max Dex +2, check penalty −3. Half weight of leather. MW incl. | clothing +500; light +750; medium +1,500; other +375/lb | 10 / 20 | woven from darkwood leaves and bark, then alchemically treated |
| **Eel hide** (UE 50) | leather, hide, studded leather | Check penalty −1, max Dex +1, electricity resistance 2. MW incl. | light +1,200; medium +1,800 | as leather | — |
| **Elysian bronze** (UE 50) | weapons, ammunition, armour | Weapons: +1 damage vs magical beasts and monstrous humanoids (multiplied on a crit); after damaging one, +1 attack vs that specific creature kind for 24 h. Armour: DR as adamantine, but only against those creatures' natural weapons and unarmed strikes. | ammo +20; light +1,000; medium +2,000; heavy +3,000; weapon +1,000 | as steel | — |
| **Fire-forged steel** (UE 50) | weapons, armour, ammunition | Armour: fire resistance 2. Weapon exposed to 10+ fire damage (or held in a campfire 1 round) adds +1d4 fire for 2 rounds; with fire-forged armour too, +1d6 for 4 rounds. Does not stack with *flaming*. MW incl. | ammo +15; light +1,000; medium +2,500; heavy +3,000; weapon +600 | as steel | dwarven; "channels heat in one direction" |
| **Frost-forged steel** (UE 50) | as fire-forged | Same, for cold. The book says it is less useful, since few mundane cold sources exist. MW incl. | as fire-forged | as steel | "a subtle difference in the alignment of the metal during crafting" |
| **Greenwood** (UE 50) | wooden items | Counts as MW. Living: heals 1 hp/hour when damp and in fertile soil, even regrowing pieces. Takes ¼ fire damage. Wood-shaping magic lasts twice as long. Needs weekly watering and an hour in soil. Darkwood cannot become greenwood. | +50 gp/lb on the MW price | as wood | cut from a treant-animated tree, shaped by a dryad |
| **Griffon mane** (UE 51) | cloaks, robes, clothing, padded/quilted armour | +2 competence on Fly. Flight enchantment on it costs 10% less. Twice normal cloth hp. | light armour +200; other +50/lb | 1 / 2× cloth | also chimera and manticore mane |
| **Living steel** (UE 51) | metal items | Self-repairs 2 hp/day (1 if broken). Armour or shield: a metal weapon that rolls a natural 1 against it must save DC 20 Fort or gain broken (destroyed if already broken); not adamantine. | ammo +10; light +500; medium +1,000; heavy +1,500; weapon +500; shield +100; other +250/lb | 15 / 35 | harvested as nuggets from fallen mineral-drawing trees |
| **Viridium** (UE 52) | piercing or slashing weapons, ammunition | Each hit: leprosy, Fort DC 12. Crit: a fragment breaks off, as greenblood oil, Fort DC 13. Carrier saves every 24 h vs leprosy unless kept extradimensional or in a lead-lined scabbard. Oozes, plants and outsiders are immune. Half hardness, fragile; strengthening (+1,000 weapon, +20 ammo) removes fragile. | ammo +20; weapon +200 | ½ base | volcanic glass, knapped |
| **Whipwood** (UE 52, ARG 207) | wooden weapons, wooden hafts | +2 CMD vs sunder of the weapon; +5 hp. Lost under *ironwood*. | +500 | — | vanara; "time-consuming process" |
| **Wyroot** (UE 52, ARG 27) | wooden or wood-hafted melee weapons | On a confirmed crit stores 1 life point (max 1/day, held 1; better ones 3). Wielder with a ki or arcane pool converts 1 point as a swift action. Points vanish at dusk. | 1 point +1,000; 2 points +2,000; 3 points +4,000 | — | — |

#### Ultimate Equipment primitive materials

Any can be magically strengthened for **+100 gp per pound**, which removes the drawbacks noted.

| Material | Applies to | Effect | Price | Hardness |
|---|---|---|---|---|
| **Bone** (also horn, shell, ivory) | light and one-handed weapons, two-handed bludgeoning, spear tips, arrowheads; studded leather, scale, breastplate, wooden shields | Weapons: fragile, −2 damage (min 1). Armour: armour bonus −1, fragile, hardness 5. MW keeps fragile; magic does not. | half | ½ base |
| **Bronze** (also brass, copper, tin) | light and one-handed weapons, spear/axe heads, arrowheads; light and medium metal armour | Weapons fragile, otherwise as steel. Armour hardness 9, fragile. Strengthening removes fragile and allows heavy armour. | as steel | base (weapons), 9 (armour) |
| **Gold** | light piercing/slashing weapons; light and medium metal armour | Gilded: ×3 price, no change. Solid: ×10 price, +50% weight. Weapons −2 damage, fragile. Armour −2 AC, +2 check penalty, hardness 5. | ×10 | ½ base |
| **Obsidian** | light and one-handed piercing/slashing, spear and arrow tips; **no armour** | Fragile. | half; ¾ weight | ½ base |
| **Stone** | light and one-handed bludgeoning, spears, axes, daggers, arrowheads | Fragile. No armour except special stoneplate. | quarter; ¾ weight | ½ base |

#### Pathfinder #61: Shards of Sin (2012): the skymetals

AoN says "seven known types of skymetal": abysium, adamantine, djezet, horacalcum, inubrix,
noqual, siccatite. Each of the six Thassilonian ones is tied to a school of magic and a sin.

| Material | Effect | Price | Hardness / HP | Craft notes |
|---|---|---|---|---|
| **Abysium** ("feverstone") | Works as steel for arms and armour, but the carrier is **sickened** while carrying it and for 1d4 hours after (a poison effect). Glows like a candle. 1 lb can be distilled into abysium powder (ingested poison, Fort DC 18, 1d4 Con plus nausea, 900 gp). | not given | as steel | "Pure or properly refined abysium" powers engines |
| **Djezet** ("quickiron") | Liquid at all temperatures; useless for metal objects except alloys. As a material component, each dose raises effective spell level by +1 (doses needed = spell level). | 200 gp per dose | — | — |
| **Horacalcum** | Weapon: +1 circumstance on attack (not ammunition). Armour: +1/+2/+3 initiative (light/medium/heavy). Items get +¼ hp. MW incl. | weapon +6,000; light +10,000; medium +30,000; heavy +60,000 | 15 / 30 | rarely found in amounts over a pound |
| **Inubrix** ("ghost iron") | Weapon deals damage as one size smaller, is always broken, ignores armour/shield bonuses from iron or steel, cannot damage iron or steel (nor iron golems). Poor for armour. | weapon +5,000 | 5 / 10 | "only slightly less malleable than lead" |
| **Noqual** | Object gets +4 on saves vs magic. Weapon: half weight, +1 enhancement on damage vs constructs and undead made by feats or spells. Armour: half weight, one category lighter, max Dex +2, check penalty −3, **spell failure +20% for all casting**, wearer +2 resistance on saves vs spells and SLAs. | light +4,000; medium +8,000; heavy +12,000; shield +2,000; weapon or other +500; ore 50 gp/lb | 10 / 30 | "can be worked as iron". **Any magic item incorporating noqual costs +5,000 gp to create** ("costly reagents and alchemical supplies") |
| **Siccatite** | Found hot or cold (50/50). Contact deals 1 energy damage per round. Weapon: +1 fire or cold per hit, and 1 of the same to the wielder each round of combat. Armour: 1 per round to the wearer, 1 per round to a grappler; cold siccatite armour gives fire resistance 5, hot gives cold resistance 5. | weapon +1,000; armour +6,000 | not given | hot can ignite objects; cold in water grows a 1-ft ice shell |

Other skymetal alloys appear elsewhere: **glaucite** (iron + adamantine, Pathfinder #85, hardness
15, 30 hp/in, 1.5× steel's weight, "triples the object's total cost to create") **[P, AoN]**;
djezeteel, keep stone and sovereign steel are named by the fan wiki
**[S]** https://pathfinderwiki.com/wiki/Skymetal .

#### Other Paizo materials on the same AoN list (selected)

| Material | Source | Effect (short) | Price | Hardness / HP |
|---|---|---|---|---|
| Nexavaran steel | Faction Guide 55 | As cold iron; first enhancement +3,000 | weapon ×1.5 | as cold iron |
| Singing steel | Adventurer's Armory 2 | Gold–mithral alloy; counts as alchemical silver (−1 dmg); armour one category lighter, ASF −5%, max Dex +1, ACP −1; striking it speeds bardic performance; 10 min of brushing after. MW incl. | weapon +6,000; light +750; medium +9,000; heavy +12,000; shield +7,000 | 10 / 20 |
| Sunsilver | Adventurer's Armory 2 | Counts as alchemical silver; rust-immune; armour can dazzle adjacent foes in bright light (Fort DC 12). MW incl. | +25 gp/lb on MW price | 8 / 10 |
| Silversheen | Qadira, Gateway to the East | Counts as alchemical silver, rust-immune, MW incl. Crafting needs Craft (alchemy) 5 ranks and Craft (weapons) 5 ranks | +750 | 8 / 10 |
| Pyre steel | Goblins #5 | Steel with ground glass; fire resistance 10, can be set alight without breaking, burns 3 minutes; half hp | ×2 base cost (not the MW part) | as steel / ½ hp |
| Voidglass | Armor Master's Handbook | +1/+2/+3 resistance vs mind-affecting (light/medium/heavy); piercing/slashing +1 damage | weapon +1,000; light +1,000; medium +2,000; heavy +4,500; shield +3,000 | 10 / 30 |
| Spiresteel, cryptstone | Pathfinder #139 | Anti-incorporeal armour; anti-undead bludgeons. MW incl. | spiresteel weapon +2,000; cryptstone weapon +500 | as steel |
| Blackwood | Merchant's Manifest | Darkwood variant; ignores DR of water-subtype creatures | +20 gp/lb | 7 / 10 |
| Liquid glass | Merchant's Manifest | Self-repairs 2 hp/day even if destroyed; +1 damage at full hp | weapon +800 | 10 / 10 |
| Bulette armour | Dungeon Denizens Revisited | Bulette plate: as full plate, 65 lb, max Dex +2, hardness 12; one adult bulette yields 2 suits of plate and 4 of leather | up to 10× normal | 12 |
| Blight quartz, blightburn, caphorite, lazurite | Planar Adventures; Heroes of the Darklands | Hazardous radiant or negative-energy minerals; blight quartz gives a negative level to a carrier of 1 lb+ and decays outside its plane | varies | varies |

**Not a PF1e material:** "Umbral" in PF1e is a +3 *magic weapon special ability* (shadow
concealment, darkness on command), not a metal **[P]**
https://www.aonprd.com/MagicWeaponsDisplay.aspx?ItemName=Umbral . "Umbrite" (+3 to Hide
checks) is 3.5-era or third-party; it uses the 3.5 Hide skill, so it is not Paizo PF1e. [S]

### 1.5 Product Identity versus Open Game Content

What can be said with evidence:

- Everything in the CRB and Ultimate Equipment tables above appears on Paizo's own **PRD**
  (legacy.aonprd.com), which Paizo published as Open Game Content under its own declaration:
  mechanics open, proper names PI. **[P]** https://legacy.aonprd.com/openGameLicense.html
  Adamantine, mithral, darkwood, cold iron, alchemical silver and dragonhide come from the
  3.5 SRD, so they were open before Pathfinder.
- The skymetals (abysium, djezet, horacalcum, inubrix, noqual, siccatite), glaucite,
  nexavaran steel, spiresteel and the Darklands minerals come from **Adventure Path and
  Campaign Setting** books, which are **not** on the PRD. The project's own licensing research
  (docs/bestiary-licensing.md §3 and §6) found that AP declarations make "proper names …
  locations" PI, and from 2018 also "all adjectives, names, titles, and descriptive terms
  derived from proper nouns". Names such as *nexavaran* (from Nexavar/Mendev) and
  *Thassilonian* skymetal lore look like PI under that reading. Whether an invented material
  word like *noqual* counts as a "proper name" is **not settled** by anything I found.
- A useful signal: when Paizo left the OGL, the PF2 Remaster renamed **mithral to dawnsilver**
  and **darkwood to duskwood** because those were OGL/SRD words. Paizo still uses its own
  skymetal names in PF2 (noqual and siccatite have entries in AoN's 2e database, e.g.
  https://2e.aonprd.com/Equipment.aspx?ID=1419). That suggests Paizo treats them as its own
  words, not shared SRD vocabulary. It is an inference, not a ruling.
  [S] https://pathfinderwiki.com/wiki/Mithral ; https://en.wikipedia.org/wiki/Paizo
- **The catalogue ships ten skymetal entries** (five ores and five metals, e.g. "Noqual Ore",
  "Siccatite") and "Nexavaran Steel". They carry the same exposure the bestiary licensing
  memo describes. The mechanics may be used; the names are the open question.

---

## 2. How games carry a material into the item

### Dwarf Fortress (Bay 12)

- **Loop.** A dwarf works a bar at a workshop. The item keeps the material's raw numbers, and
  the crafter's skill rolls a quality grade on top.
- **Material numbers** (from the raws, via the community wiki) [S]
  https://dwarffortresswiki.org/index.php/Material_definition_token :
  - `SOLID_DENSITY` "affects blunt-force damage";
  - `SHEAR_YIELD` / `SHEAR_FRACTURE` are "Used for cutting calculations";
  - `IMPACT_YIELD` / `IMPACT_FRACTURE` are "Used for blunt-force combat";
  - `MAX_EDGE` is "How sharp the material is".
- **Edge versus blunt.** For edges, steel is "the clear best", bronze or iron "roughly
  equivalent", copper "a distant third", silver "a very distant last", and adamantine "a
  league above steel". For blunt weapons "heavier is better", so dense silver does well, while
  adamantine is "a terrible choice … roughly the same as … featherwood or cork". The same page
  also says the six standard metals perform "nearly identically" for blunt weapons in practice.
  [S, v53 wiki] https://dwarffortresswiki.org/index.php/Weapon
- **The lesson:** one material can be good on one axis and bad on another. Nothing is simply
  "the better metal".
- **Quality grades:** well-crafted, finely-crafted, superior, exceptional, masterwork, artifact.
  The grade multiplies value (1.1× up to 2×, artifacts 20×) and weapon effect (1.2× up to 2×,
  artifacts 3×). Quality multiplies on top of material; it never replaces it.
  [S] https://dwarffortresswiki.org/index.php/Item_quality
- **Changed.** Before v0.31 (2010) weapons used "hard-coded percentage damage"; 0.31 replaced
  that with material physics. [S] https://dwarffortresswiki.org/index.php/DF2010:Combat
- **The cost.** Tarn Adams, December 2024, on giving each stone its own mechanics: it "was not a
  data entry thing I could tackle". [P, interview transcript]
  https://www.blindirl.com/developing-battle-magic-in-dwarf-fortress-tarn-adams-interview/
  Players mostly learn the physics from the wiki, not from play.

### Kingdom Come: Deliverance 1 (2018) and 2 (2025)

- **KCD1** has no forging. Smithing is the grindstone sharpening minigame. [S]
  https://kingdomcomedeliverance2.wiki.fextralife.com/Blacksmithing
- **KCD2 loop.** Heat the piece with the bellows until it glows the right colour, hammer it
  evenly on the anvil, turn it, reheat as it cools, then a final heat and quench. Guides say to
  heat to straw-yellow across the piece and avoid white heat. [S]
  https://www.destructoid.com/kingdom-come-deliverance-2-blacksmithing-guide-and-tips/ ;
  https://www.thegamer.com/kingdom-come-deliverance-2-black-smithing-forging-crafting-guide/
- **Material.** Recipes fix the ingredients. I found nothing saying that a different metal
  changes the result's stats. Quality comes from the minigame plus Craftsmanship level and
  perks. [S]
- **Patch 1.2 [P]** https://www.deepsilver.com/games/kingdom-come-deliverance-ii/news/patch-12 :
  "Generally rebalanced the blacksmithing minigame." "Improved visual indication of workpiece
  cooling." "Added horseshoe recipes to various merchants and locations." "Removed bezoar from
  alchemy and added it to blacksmithing." The *first* fix was making the heat state readable.
- **Patch 1.5** lets the minigame draw materials from the stash and the horse. [S]
  https://kingdomcomedeliverance2.wiki.fextralife.com/Patch_Notes
- **Complaints.** Players asked for a way to skip forging routine items such as quest
  horseshoes; only mods provide one. A Steam player called the system "about as basic as you
  get … No assembling, no refining". The Legacy of the Forge DLC's smithy was called "grindy and
  slightly repetitive". [S]
  https://www.altchar.com/reviews/kingdom-come-deliverance-2-legacy-of-the-forge-dlc-review-aHStX1j17umB

### Mount & Blade II: Bannerlord (TaleWorlds)

- **Loop.** Refine, smelt and forge share one stamina pool. Two hardwood make one charcoal.
  Metal is refined up a ladder: crude iron, wrought iron, iron, steel, fine steel, Thamaskene
  steel. Weapons are built from parts (blade, guard, handle, pommel). [S, Steam guides]
  https://steamcommunity.com/sharedfiles/filedetails?id=2042515676
- **Material.** The part tier sets which metal grade it costs. As far as I could find, the metal
  grade is a **cost gate, not a stat source**; stats come from the parts. (My inference.)
- **Quality.** Difficulty comes from the part tiers. Skill against difficulty shifts the odds of
  good modifiers: Masterwork +5 damage, +2 speed, +50% price; Legendary +7, +3, +80%. [S]
- **The exploit.** One number, item value, drove income, skill XP and part unlocks at the same
  time. Players reported "3-4 steel" making a two-hander that sold "for 100K". [S]
  https://steamcommunity.com/app/261550/discussions/0/2968398851792500518/
- **The fix, e1.6.0 (live 2 August 2021).** Crafting split into Crafting Orders and Free Build.
  Free Build XP and research were "greatly reduced"; progress moved to orders. TaleWorlds: "We
  will continue to evaluate the values of items produced via the crafting process." [P, quoted
  by a mirror; the official page returned 403]
  https://updatecrazy.com/bannerlord-update-1-6-0-1-6-patch-notes-august-2-2021/
- **Aftermath.** Part unlocks were slowed through e1.8; a player reported "30-45 minutes of pure
  smithing … only unlocked 9 parts". Tuning one end of the shared number broke the other. [S]
  https://steamcommunity.com/app/261550/discussions/0/5069383987783752319/

### World of Warcraft: Dragonflight (2022), The War Within (2024)

- **Loop.** Skill plus bonuses is compared with recipe difficulty. Gear has 5 quality ranks,
  reagents 3. "Crafting with higher quality basic reagents will directly provide bonus skill."
  [P] https://worldofwarcraft.blizzard.com/en-gb/news/23827585/dragonflight-preview-an-eye-on-professions
- **Two channels for materials.**
  1. Basic reagent *quality* feeds the quality number and never adds an effect.
  2. *Optional* reagents add typed effects: Missives choose secondary stats, Embellishments add
     an equip effect, capped at "two Embellished items" worn. [P]
     https://news.blizzard.com/en-us/article/23876529/dragonflight-making-it-with-professions
  Recrafting can swap optional reagents later; the replaced ones "will be destroyed". [P]
  https://news.blizzard.com/en-us/article/23826545/dragonflight-preview-more-on-professions
- **Abandoned: Inspiration** (a random chance of extra skill). Blizzard, April 2024: "a lack of
  decision making and agency for the crafter", "a lack of clarity for customers", and it was
  "based heavily in RNG". Replaced by **Concentration**, a regenerating pool you spend to
  "automatically reach the next level of quality"; the cost depends on how far you are from it.
  [P, blue post] https://www.bluetracker.gg/wow/topic/us-en/1833285-professions-update-concentration-in-the-war-within/
- **Tuned:** June 2024, "Reagents are now 40% of a recipe's difficulty up from 25%". [P]
  https://www.bluetracker.gg/wow/topic/us-en/1870491-concentration-professions-feedback/
- **Simplified:** for Midnight, reagent quality tiers drop from 3 to 2. [S]
  https://www.wowhead.com/news/simplifying-crafting-professions-and-reagents-in-midnight-378932

### Elder Scrolls Online (ZeniMax Online)

- **Loop.** Each input controls one axis. The ingot sets the level band (iron, steel,
  orichalcum, dwarven, ebony, then calcinium to rubedite). The style material sets the look. A
  **trait gem** sets the trait (Sharpened, Infused, Precise and so on). Tempers raise quality
  afterwards. [W] https://en.uesp.net/wiki/Online:Blacksmithing ; https://en.uesp.net/wiki/Online:Traits
- **Risk.** A failed improvement **destroys the item**; adding more tempers raises the chance up
  to 100%. [P, official support]
  https://help.elderscrollsonline.com/app/answers/detail/a_id/4028/~/can-i-destroy-an-item-as-i-attempt-to-improve-it
- **Discovery.** Trait research destroys an item that carries the trait and then runs a
  real-time timer that grows with each trait known.
- **Changed.**
  - Patch 2.4.0 (April 2016) revised traits "to improve the viability and balance of each
    Trait". Niche traits went: Weighted became Decisive, Exploration became Prosperous. [P,
    mirrored on UESP] https://en.uesp.net/wiki/Online:Patch/2.4.0
  - Update 49 (9 March 2026): "We have reduced the time to be able to fully research Crafting
    Traits by over 50%", and the cap fell "from 30 days to 10 days". [P, quoted on UESP]
    https://en.uesp.net/wiki/Online:Update_49

### Skyrim, Oblivion, Morrowind (Bethesda)

- **Morrowind and Oblivion** only repair. Oblivion's Expert can repair to 125%, "Expert-improved
  weapons do extra damage". [W] https://en.uesp.net/wiki/Oblivion:Armorer
- **Skyrim.** Smelt ore to ingots (no check), forge, improve. A perk unlocks each material tier
  and doubles improvement for it. Quality names run Fine, Superior, Exquisite, Flawless, Epic,
  Legendary, and depend deterministically on skill. No minigame, no discovery.
  [W] https://en.uesp.net/wiki/Skyrim:Smithing
- **Exploit.** Fortify Restoration potions amplified Fortify Smithing and Enchanting gear in a
  loop. The **Unofficial** Skyrim Patch removed it; I found no official Bethesda fix.
  [W] https://en.uesp.net/wiki/Skyrim:Fortify_Restoration

### RuneScape 3: Mining and Smithing rework (January 2019)

- **Loop.** Bars become an unfinished item with a **progress** bar and a **heat** bar. Each
  strike costs heat; progress per strike is higher when hot. Reheat at a forge beside the anvil.
  Items upgrade from +1 to +5. [W] https://runescape.wiki/w/Smithing
- **Jagex's intent:** heat "lets you choose how active you want the skill to be, from completely
  AFK to very frequent clicks". [P] https://secure.runescape.com/m=news/mining-and-smithing-rework
- **Softened.** The design documents proposed progress ×0.5 at zero heat; the live game uses ×1.
  (My comparison of two wiki pages.) [W]
  https://runescape.wiki/w/Mining_and_Smithing_rework_design_documents
- **Retrospective (May 2024):** it "could have offered more for players who already had 99". [P]
  https://secure.runescape.com/m=news/right-click-examine-future-skilling-content

### Old School RuneScape: Giants' Foundry (June 2022) and Blast Furnace

- **Giants' Foundry loop.** Fill a crucible with bars or items, pour into moulds, then work each
  section with the tool that fits its heat: trip hammer when hot, grindstone at medium,
  polishing wheel when cold. Lava and a waterfall move the heat. [W]
  https://oldschool.runescape.wiki/w/Giants%27_Foundry
- **Alloying beats purity by design:** "an entirely rune sword has a base value of 60, but a
  sword made of equal parts adamant and rune has over double the base value, at 130". [W]
- **Quality** = metal + moulds, and "10 quality points are lost whenever you damage the sword by
  using the wrong tool or at the wrong temperature". Better metal adds sections (3 to 7) and
  makes the bars smaller, so better metal is harder to work. [W]
- **Changes after launch** were quality-of-life only: best moulds shown first, a confirmation
  removed, a timing bug fixed. [P] https://secure.runescape.com/m=news/giants-foundry-changes?oldschool=1
- **Blast Furnace.** Players once had to pedal, pump and repair the machine. On official worlds
  NPC dwarves took that labour over (2016–17). The chores were automated away. [W]
  https://oldschool.runescape.wiki/w/Blast_Furnace

### Valheim, Minecraft, Terraria: tier ladders

- **Valheim.** Metals are gated by biome (copper and tin to bronze, iron, silver, black metal,
  flametal). Forge upgrades gate recipes. No minigame. A metal is its tier. [S]
  https://valheim.weirdgloop.org/w/Bronze
- **Minecraft.** Fixed tiers. In 2023 the netherite upgrade began to need a Smithing Template;
  snapshot 23w05a raised the template's drop chance from 3.2% to 10% within weeks. Armour-trim
  materials set colour only. [W] https://minecraft.wiki/w/Netherite_Upgrade
- **Terraria 1.2.** Every ore tier has a twin (copper/tin, iron/lead, silver/tungsten,
  gold/platinum and the hardmode pairs). Each world spawns one of each pair. The twins differ
  only slightly. [W] https://terraria.wiki.gg/wiki/Ores
  *Reading:* same-tier twins give a world its own flavour without changing progression. That
  matches "the world owns its own materials".

### Monster Hunter (Capcom)

- **World and Rise.** Weapons sit on trees; each node needs a particular monster's parts. A
  node appears once you have seen the material. [S]
- **Rise: Sunbreak, Qurious Crafting** randomly rerolled armour, and a reroll could make it
  worse. After complaints Capcom kept the randomness and added steering options. [S]
  https://automaton-media.com/en/news/20220817-15005/
- **Wilds, Artian weapons.** The parts set the element by majority (two of the same element),
  and three different elements cancel out to raw damage. Each part's bonus stacks. The random
  reinforcement rolls follow a fixed seeded sequence, not the parts. [S]
  https://dotgg.gg/monster-hunter-wilds/artian-weapons/
  *Reading:* inputs with identity set the deterministic parts of the result.

### Wurm Online: the closest prior art for typed metals

- Every metal is a **small modifier vector against iron**: price, damage taken, decay, shatter
  resistance, improve speed, and a few more. As shown on the wiki template (my reading of the
  table; columns may be slightly misaligned): adamantine −60% damage taken and −60% decay;
  steel −20% damage taken; zinc +25% damage taken and +20% decay; lead 0.75× price. [W, community]
  https://www.wurmpedia.com/index.php/Template:Metal_general_properties
- A developer corrected the list on the forum: "Items made from brass come out at +10% QL". [P via
  forum, March 2018]
  https://forum.wurmonline.com/index.php?%2Ftopic%2F161990-new-metal-type-properties-reference-list%2F=
- **Improving** needs the right tool each step, which you learn by examining the item. Metal
  must stay glowing. A failure damages the item. [W] https://www.wurmpedia.com/index.php/Improving_Guide

### Vintage Story (Anego Studios): heat, voxels, bloomery, assaying

- **Heat.** Metal is workable above about half its melting point; iron blooms above 700 °C.
  Hotter metal moves more. [W] https://wiki.vintagestory.at/Smithing
- **Shaping** is voxel by voxel against a template. The split mode knocks slag out of iron
  blooms and blister steel.
- **Alloys have ratio windows:** tin bronze 88–92% copper, 8–12% tin. Inside the window there is
  no quality gradient. [W] https://wiki.vintagestory.at/Alloy
- **Steel** comes from a cementation furnace (iron + carbon → blister steel), added in 1.14. [P]
  https://www.vintagestory.at/blog.html/news/stable-steel-age-and-character-customization-v1140-r270/
- **Prospecting pick:** density mode gives a probability reading for an area, not location or
  quality; node mode gives direction and size. [W] https://wiki.vintagestory.at/Prospecting_Pick
- **Changed:** 1.12.0, "Anvils no longer reset the temperature of work items". A helve hammer
  automates blooms, steel and plates; tools stay hand-made. [W] https://wiki.vintagestory.at/Anvil ;
  https://wiki.vintagestory.at/Helve_hammer
- **Complaints** about wasted voxels and tedium were answered by mods. I found no developer reply.
  [S] https://www.vintagestory.at/forums/topic/10961-less-blacksmithing-tediousness/

### Others, briefly

- **Mortal Online 2:** a sword's core, grip and head materials each change stats, and **you must
  read lore books before a material can be used**. Discovery is knowledge-gated. [S]
  https://www.magicgameworld.com/mortal-online-2-complete-crafting-guide/
- **Life is Feudal:** output quality is a weighted blend per recipe (one example: 50% from the
  billet, 30% from skill, 10% each from rope and toolkit). [S, Steam guide]
- **Fable II** (2008): a sweeping timing cursor; the target zone shrinks as your multiplier
  climbs. It pays gold and makes no item. [S] https://fable.fandom.com/wiki/Jobs
- **Fable (Playground, 2026):** the developers said the demo smithing was sped up and that
  normally "a single item usually nets you around 20 gold". [S]
  https://www.thegamer.com/fable-blacksmithing-combat-made-easier-gameplay-demo/
- **Blacksmith Master** (early access May 2025): a rhythm minigame per task. A review calls manual
  smithing "unfun and … clunky", with little reason to do it by hand. [S]
  https://www.canbuyornot.com/reviews/games/blacksmith-master-review-price/
- **Moonlighter** and **My Time at Sandrock:** recipe plus materials, no forging minigame. [S]

---

## 3. Real-world smithing, for grounded minigames and traits

Sources are Wikipedia unless marked; Wikipedia articles cite handbooks, and where it matters I
name the handbook the article names. Marked [S] throughout, since none is a primary
metallurgy text. Knife Steel Nerds is written by Larrin Thomas, a metallurgist; still [S].

### 3.1 Heat colour (forging)

- Smiths judged heat by colour before thermometers, heating "to a colour which was known to be
  best for the work". The table below is the one Wikipedia credits to Chapman, *Workshop
  Technology* (1972). A footnote says the colours apply "when viewed in dull light", so
  ambient light changes what you see. https://en.wikipedia.org/wiki/Red_heat

| Colour | °C |
|---|---|
| Black red | 426–593 |
| Very dark red | 594–704 |
| Dark red | 705–814 |
| Cherry red | 815–870 |
| Light cherry red | 871–981 |
| Orange | 982–1,092 |
| Yellow | 1,093–1,258 |
| Yellow-white | 1,259–1,314 |
| White | 1,315+ |

- **Hot forging** of steel happens at **950–1250 °C**, above recrystallisation, so the work
  does not harden as you hammer. Cold work does harden it.
  https://en.wikipedia.org/wiki/Forging
- **Forge welding** heats: pure iron near white (1,400–1,500 °C); 2% carbon steel at
  orange-yellow (900–1,100 °C); common steel "at a bright yellow heat".
  https://en.wikipedia.org/wiki/Forge_welding
- **Too hot:** sparks from the steel or bubbling on the surface mean it is burning. Overheating
  grows the grain, which makes it brittle; grain can be refined again by thermal cycling, but
  decarburisation cannot be undone. [S, blacksmith supplier blogs]
  https://www.orchardblacksmith.com/blog/overheating-steel-signs-consequences-and-how-to-avoid-it
  Knife Steel Nerds shows visibly coarser grain in 1084 heated to 1095 °C than at 800 °C.
  https://knifesteelnerds.com/2021/09/23/how-to-heat-treat-knife-steel-in-a-forge/
- **The magnet test:** steel goes non-magnetic when it turns to austenite (iron's Curie point
  is about 770 °C). This is the old smith's cue for "hot enough to harden". Knife Steel Nerds
  warns that non-magnetic is not the same as fully ready: some steels need more heat to dissolve
  carbides. Same source.

### 3.2 Quench media

- **Water** gives maximum hardness, but "there is a small chance that it may cause distortion
  and tiny cracking". **Oil** is used "when hardness can be sacrificed"; it cools much more
  slowly. https://en.wikipedia.org/wiki/Quenching
- **The vapour jacket:** at first "the object is fully surrounded by vapor which insulates it"
  (the Leidenfrost stage). Same page.
- **Brine** cools faster than plain water because the salt breaks up that vapour blanket.
  Grossmann quench severity (H) figures quoted in a ScienceDirect overview: **brine 2.0–5.0,
  water 0.9–2.0, quench oils 0.25–0.8**. So the order is brine > water > oil > air.
  [S] https://www.sciencedirect.com/topics/engineering/grossmann
- **Trade-off, in one line:** faster quench = harder and more brittle, with more risk of
  cracking or warping. Slower = softer, safer.

### 3.3 Tempering colours

After quenching, steel is too brittle. Tempering reheats it to "achieve greater toughness by
decreasing the hardness". The oxide colour on bright steel shows the temperature.
https://en.wikipedia.org/wiki/Tempering_(metallurgy)

| Colour | °C | Typical use (as listed) |
|---|---|---|
| Faint yellow | 176 | gravers, razors, scrapers |
| Light straw | 205 | rock drills, reamers, metal-cutting saws |
| Dark straw | 226 | scribers, planer blades |
| Brown | 260 | taps, dies, drill bits, hammers, cold chisels |
| Purple | 282 | surgical tools, punches, stone-carving tools |
| Dark blue | 310 | screwdrivers, wrenches |
| Light blue | 337 | springs, wood saws |
| Grey-blue | 371+ | structural steel |

**Differential tempering** gives "a very hard edge while softening the spine". Same page. This
is a natural minigame: stop the colour run at the right band for the tool.

### 3.4 Flux

- Forge welding needs very clean surfaces. Flux "mixes with the oxides … and lowers the melting
  temperature and the viscosity of the oxides", so they squeeze out when hammered.
  https://en.wikipedia.org/wiki/Forge_welding
- "The oldest flux used for forge welding was fine silica sand." **Borax** is the common modern
  flux, sometimes with iron filings. Same page.
- In smelting, limestone and other fluxes carry impurities into slag (general knowledge; the
  crucible-steel article lists sand, glass and ashes as fluxes in the crucible).
  https://en.wikipedia.org/wiki/Crucible_steel

### 3.5 Folding and pattern welding

- Pattern welding folds or twists several pieces, forge-welded together. Early bloomery iron was
  poor, so smiths combined steels of different carbon content for "a desired mix of hardness
  and toughness" and to reduce impurities. Later it was also decorative.
  https://en.wikipedia.org/wiki/Pattern_welding
- It "fell out of use in Europe" after better steel arrived; modern steel makes blending and
  homogenising unnecessary. Today it is mainly for looks. Same page.
- **It is not the same as Damascus (wootz) steel**, which is a crucible steel with its own
  pattern. Same page.
- *Design reading:* folding was a fix for **dirty, uneven iron**. It improves bad metal and adds
  little to good metal. That is a grounded rule: fold helps low-grade bloom iron most.

### 3.6 Bloomery versus crucible steel

- A **bloomery** never melts the iron. It makes a porous "bloom" of iron and slag that "must be
  beaten with heavy hammers to both compress voids and drive out any molten slag". Carbon
  content varies across a single bloom. Fuel is charcoal, roughly one-to-one with ore.
  https://en.wikipedia.org/wiki/Bloomery
- **Crucible steel** melts everything, so carbon spreads evenly and slag separates. Wootz came
  from southern India and Sri Lanka from the mid-1st millennium BCE. Huntsman's 1740s
  coke-fired furnace reached about 1,600 °C, using blister steel and a glass flux.
  https://en.wikipedia.org/wiki/Crucible_steel
- *Design reading:* bloom iron is uneven (variance), crucible steel is even (consistency).

### 3.7 Fuels: charcoal, coal, coke

- All blast furnaces burned charcoal until **Abraham Darby used coke in 1709**. Coke's
  "superior crushing strength" let furnaces grow taller. Charcoal ran short as coppiced forests
  could not keep up. https://en.wikipedia.org/wiki/Coke_(fuel)
- **Sulfur** is the problem with raw coal: it makes steel **hot-short** (brittle at red heat)
  because iron sulfide gathers at grain boundaries and melts low.
  https://en.wikipedia.org/wiki/Red-short_carbon_steel
- Charcoal iron stayed prized for "heat-resistance, toughness, and malleability" even after coke.
  https://en.wikipedia.org/wiki/Charcoal_iron (search summary)
- *Design reading:* fuel can carry a trait: coal is hot but **sulfurous** (risk of a brittle
  flaw unless coked), charcoal is clean, coke is clean and hot.

### 3.8 Assaying: identifying a metal

- **Touchstone:** streak the metal on dark stone and compare the streak with needles of known
  purity; acid on the streak refines it. Used since the Harappan period (c. 2600–1900 BC).
  https://en.wikipedia.org/wiki/Touchstone_(assaying_tool)
- **Spark testing:** hold iron or steel to a grinding wheel and read the sparks. Mild steel
  gives white sparks with small forks; high-carbon steel a "bushy" pattern; wrought iron
  straight lines with leaf-like tails. It cannot identify a material "positively", only
  classify it. https://en.wikipedia.org/wiki/Spark_testing
- **Fire assay and cupellation** are covered in Agricola's *De re metallica* (1556), Book VII,
  which also describes reading ore veins from surface signs.
  https://en.wikipedia.org/wiki/De_re_metallica
- *Design reading:* real assaying is **comparison against known references**. That fits a
  discovery system where each known sample makes the next identification easier.

---

## 4. Tabletop prior art beyond PF1e

### D&D 5e

- **Xanathar's Guide to Everything (2017)**, crafting magic items: needs a formula, an
  **exotic material** won on an adventure, tool proficiency, gold and workweeks. The material's
  source creature has a recommended CR by rarity. [S, summarised by several fan sites; I did not
  read the book] https://www.flutesloot.com/5e-crafting-magic-items/

| Rarity | Material CR | Cost | Workweeks |
|---|---|---|---|
| Common | 1–3 | 50 gp | 1 |
| Uncommon | 4–8 | 200 gp | 2 |
| Rare | 9–12 | 2,000 gp | 10 |
| Very rare | 13–18 | 20,000 gp | 25 |
| Legendary | 19+ | 100,000 gp | 50 |

  Consumables halve cost and time. The key idea: **the special material is a quest, not a
  shop item**, and its source's danger matches the result's power.
- 5e's special materials are few. In the SRD, adamantine armour turns any critical hit
  against the wearer into a normal hit, and mithral armour removes the Strength requirement and
  the Stealth disadvantage. There is no material-quality ladder. [S, from memory of SRD 5.1;
  not re-checked in this pass]

### Pathfinder 2e

- **Grades.** Precious materials come in **low, standard and high grade**. "Only an expert
  crafter can create a low-grade item, only a master can create a standard-grade item, and only
  a legendary crafter can create a high-grade item." Your level must be at least the
  material's level. **[P, GM Core 252]** https://2e.aonprd.com/Rules.aspx?ID=729
- **How much of the material is in the item:** low grade at least 10% of the investment,
  standard at least 25%, high grade all of it. Same page.
- **The cap on magic:** low-grade items hold magic up to item level 8, standard up to 15, high
  any. Same page. Fan guides read this as the whole point of grades: a precious material makes
  you pay again before your runes can climb. That reading is **[S]**
  https://scribe.pf2.tools/v/bFpw9VX8-ch6-precious-materials ; I found no Paizo designer
  statement of intent.
- Some materials skip grades: "adamantine can't be low grade, and orichalcum must be high
  grade." **[P]** https://2e.aonprd.com/Equipment.aspx?Category=22
- **Example:** standard-grade adamantine weapon is item level 11, 1,400 gp + 140 gp per Bulk;
  high grade is level 17, 13,500 gp + 1,350 per Bulk. Adamantine weapons treat an object's
  Hardness as halved unless it is harder than the weapon. [S]
  https://pf2.d20pfsrd.com/equipment/standard-grade-adamantine-weapon/
- **Hardness is a table by material, grade and thickness** (thin items / items / structures).
  Iron or steel item: Hardness 9, HP 36, BT 18. [S] https://pf2.d20pfsrd.com/rules/crafting-treasure/
- **What changed from PF1e, and why (as far as sourced):**
  1. PF1e materials are a flat price add-on; anyone with the gold gets the full effect. PF2e
     gates them by **crafter proficiency and level**, and caps the magic they can carry by grade.
  2. PF1e's armour materials change many numbers (Dex cap, ACP, spell failure, DR). PF2e's
     materials mostly do **one thing** (cold iron vs fey, silver vs devils, adamantine vs
     hardness) plus hardness and Bulk.
  3. The Remaster (2023) renamed mithral to **dawnsilver** and darkwood to **duskwood** to leave
     OGL vocabulary behind. [S] https://pathfinderwiki.com/wiki/Mithral
  Paizo's stated reason for (1) and (2) is **not sourced** here; see Could not confirm.

### Burning Wheel (Luke Crane)

- Weapons and armour come in **three qualities**: poor, run of the mill, superior. A superior
  weapon gives **balance dice** to strikes, blocks and similar actions. Making a superior
  weapon adds **+2 Ob** (obstacle) to the Weaponsmith test, and **failing it yields an inferior
  weapon**. [S, Burning Wheel forums and fan reference]
  https://forums.burningwheel.com/t/making-superior-quality-weapons/14094
- *Reading:* the crafter **chooses the ambition before rolling**. Aiming high costs difficulty
  and risks a worse result. That is a choice, not a minigame.

### Blades in the Dark (John Harper)

- Crafting is a downtime **Tinker** roll. Base quality equals the crew's Tier: 1–3 gives Tier
  −1, 4/5 gives Tier, 6 gives Tier +1, a critical gives Tier +2. Spend coin for +1 quality
  each; a Workshop upgrade adds +1. The GM names a **minimum quality** the item must reach.
  Inventing a new design is a long-term project clock (usually 8 segments).
  **[P, the official SRD]** https://bladesinthedark.com/crafting
- *Reading:* quality is a ladder relative to your standing, and **resources can buy steps** —
  close to WoW's Concentration.

### The Angry GM (already in the herbalism sweep)

- Crafting fails when it becomes a second gold. Ingredients should be concrete things with
  few descriptors (rarity, type, one special quality). **[P essays]**
  https://theangrygm.com/crafting-in-the-raw/

---

## 5. What to take

Recommendations, not findings. Each is tied to the evidence above.

### 5.1 Two layers on every material

Give each material two separate sets of fields, the way WoW and ESO split them and the way
*Unchained* splits raw-material traits from material effects:

1. **Item effects**: what the finished item does. Typed, from the book where the book has a
   number (§1.4). This is the "rarity, type, one special quality" layer the Angry GM asks for.
2. **Working traits**: how it behaves at the forge. Start from Unchained's four (easily worked,
   flawless, malleable, pure), which are already rules. Add grounded ones from §3 where they earn
   a place: *sulfurous* (coal: risk of a hot-short flaw unless coked), *slaggy* (bloom iron:
   folding helps it), *quench-sensitive* (cracks in brine), *narrow window* (Giants' Foundry:
   better metal, tighter heat band).

Fuels, fluxes and quenchants mostly belong in layer 2. A few (dragon blood, blessed water)
also carry a layer-1 effect into the item.

### 5.2 Correct the book-backed entries first

These catalogue entries name a PF1e material and disagree with its printed rule. Fix the data
before adding anything new (all rules text: https://www.aonprd.com/SpecialMaterials.aspx).

| Entry | Catalogue now | Book |
|---|---|---|
| Mithral | lighter "for movement and proficiency"; Dex +2, ACP −3 | **not** for proficiency; also spell failure −10%; half weight; counts as silver vs DR; shield +1,000 |
| Fire-Forged Steel | fire resistance 2 "once it has drunk a round of flame" | armour: fire resistance 2, always. Weapon: after 10+ fire damage, +1d4 fire for 2 rounds (1d6 for 4 with matching armour); no stacking with *flaming* |
| Frost-Forged Steel | cold resistance 2 after a round of cold | same as fire-forged, for cold |
| Viridium | Fort DC 14, sickened a day | leprosy on any hit, Fort DC 12; crit: greenblood oil, DC 13; carrier saves every 24 h unless lead-lined; half hardness, fragile; a volcanic **glass** |
| Abysium | Fort DC 18 per day, sickened | **no save**: sickened while carried and 1d4 h after (poison effect); glows as a candle. DC 18 is abysium powder |
| Horacalcum | +1 initiative | armour +1/+2/+3 initiative by weight; weapon +1 attack (not ammunition); +¼ hp |
| Singing Steel | +2 Perform | counts as alchemical silver (−1 damage); armour one category lighter, ASF −5%, Dex +1, ACP −1; faster start to bardic performance |
| Inubrix | touch attack vs iron/steel wearers | ignores iron/steel armour and shield bonuses, **but** damage as one size smaller, always broken, cannot damage iron or steel |
| Noqual | +2 vs spells | also +4 object saves vs magic, half weight, lighter category, Dex +2, ACP −3, **ASF +20% to all casting**, +1 enhancement damage vs constructs and made undead, **+5,000 gp to make any magic item with it** |
| Elysian Bronze | +1 damage vs magical beasts and monstrous humanoids | also +1 attack vs that creature kind for 24 h after damaging one; armour gives DR as adamantine vs their natural attacks |
| Living Steel | self-repairs overnight; strikers risk notching | 2 hp/day (1 if broken); a metal weapon rolling a natural 1 against it saves DC 20 Fort or breaks; not adamantine |
| Alchemical Silver Plating | −1 damage | −1 only for slashing or piercing; cannot be applied to adamantine, cold iron or mithral |
| Darkwood Haft, Adamantine Edging, Cold Iron Blanching, Angelskin Binding, Dragonhide Grip | partial-material effects | the book gives **no benefit** to part-made items ("only the most prevalent material"; darkwood and mithral say so outright). Angelskin is armour only. Dragonhide is armour and shields. The PF1e grip material is *dragonskin* (+2 CMD vs disarm, *Dragonslayer's Handbook*). Keep these only as named house rules. |

Materials with **no** PF1e source (Star Iron, Wyrmsteel, Bell Bronze, Pattern Steel,
High-Carbon Steel, Dragonfire Coal, Phoenix Ash Ember, Stardust Flux, Troll Blood, Styx Water and
others) are homebrew. That is fine, but they should borrow book shapes and sizes: +1 damage
against a creature type (Elysian bronze), energy resistance 2 (fire-forged, eel hide), DR 1/2/3
by armour weight (adamantine), ±1 attack, fragile.

### 5.3 Quality: keep the d20, follow Burning Wheel and Concentration

- **The d20 decides success; masterwork stays DC 20.** The book's masterwork rule is the only
  quality step PF1e prints (+1 attack, or ACP −1). Everything above it must stay small.
- **Let the smith choose ambition before the roll** (Burning Wheel: superior is +2 Ob, failure
  makes it inferior) **or spend a resource for a sure step** (WoW Concentration, Blades in the
  Dark coin). Never a hidden random bump (WoW's Inspiration).
- **Quality multiplies on top of material and never replaces it** (Dwarf Fortress). A crude
  adamantine sword is still adamantine.

### 5.4 Minigames: real bands, generous, readable

- **Heat:** a colour band to stop inside (cherry red through orange for forging, yellow for
  welding). White means burning: sparks and lost quality. KCD2's first patch made cooling
  readable, so show heat as a bar or number as well as a colour (colour alone also fails
  accessibility; see the herbalism sweep, §5).
- **Quench:** choose the bath, then time the plunge. Brine is hardest and riskiest, oil is
  softest and safest. A trait like *quench-sensitive* widens or narrows the band.
- **Temper:** watch the oxide colour run and stop at the band the item needs (straw for edges,
  blue for springs). Differential tempering, hard edge and soft spine, is a natural upgrade.
- **Better metal, tighter window** (Giants' Foundry) is a grounded way for rarity to raise
  difficulty without raising the DC.
- **Start generous** and drop the harshest penalty (RS3 shipped without its ×0.5).

### 5.5 Discovery: assay by comparison

- Real assaying compares an unknown against known references: touchstone streaks against
  needles of known purity, sparks against a chart (§3.8). Spark testing "cannot identify a
  material positively". So identification can be **partial and graded**: a classification
  first, certainty later.
- Ways in that fit the herbalism plan: a test at the bench (streak or spark, which costs a
  sliver of the sample); asking a smith who knows; a manual (Mortal Online's lore books gate
  materials this way); and **working it**, which reveals the working traits.
- Vintage Story's density reading is a good model for prospecting: a probability, not a
  location.

### 5.6 Alloying

- **Mixing should be able to beat purity** (Giants' Foundry: rune+adamant 130 against pure rune
  60). The catalogue's "novel same-tier pair comes out one band rarer" rule fits.
- **Ratio windows** (Vintage Story) are simple and readable. Bronze is a window, not an exact
  ratio.
- PF1e precedent: singing steel is gold + mithral, glaucite is iron + adamantine (and "triples
  the object's total cost to create"). Alloys may *lose* properties as well as gain them.

### 5.7 World Bible

Fixes are world-agnostic. The two layers (item effects, working traits) should be optional
fields with defaults in `docs/campaign-format.md`, so a world's own metals carry them. Terraria's
same-tier twins are a model for a world's local metal that stands in for iron or silver.

### 5.8 Licensing

The CRB and Ultimate Equipment materials are on Paizo's PRD as Open Game Content. The
skymetal names and *nexavaran* come from Adventure Path and Campaign Setting books whose
declarations make proper names PI (see `docs/bestiary-licensing.md`). Treat their names with the
same caution as the bestiary: the mechanics are open, the names are the open question.

---

## 6. What others tried and abandoned

| Game | Tried | Abandoned or changed to | Source |
|---|---|---|---|
| WoW | Inspiration: random chance of higher quality | Concentration: a pool you choose to spend for a sure step. Reason: "a lack of decision making and agency for the crafter" | [P] blue post, Apr 2024 |
| WoW | Reagents 25% of difficulty | 40% | [P] blue post, Jun 2024 |
| WoW | 3 reagent quality tiers | 2 (Midnight) | [S] Wowhead |
| Bannerlord | Item value drove income, XP and unlocks at once | Orders split from Free Build; Free Build XP "greatly reduced"; unlocks slowed, which drew grind complaints | [P via mirror] e1.6.0, Aug 2021 |
| KCD2 | Blacksmithing minigame at launch | "Generally rebalanced"; cooling made visible | [P] patch 1.2 |
| KCD1 → KCD2 | No forging (grindstone only) | Full forge minigame, still recipe-fixed materials | [S] |
| RuneScape 3 | Proposed ×0.5 progress on cold metal | Shipped at ×1 | [W] design docs vs live |
| OSRS | Players pedal, pump and repair the Blast Furnace | NPC dwarves do it on official worlds | [W] |
| Vintage Story | Anvil reset a workpiece's temperature | Removed in 1.12.0 | [W] |
| Dwarf Fortress | Hard-coded weapon damage | Material physics (0.31); full per-stone data never finished | [S] wiki; [P] Tarn Adams |
| ESO | Niche traits (Weighted, Exploration) | Replaced in 2.4.0 | [P via UESP] |
| ESO | Trait research up to 30 days per trait | Over 50% faster; cap 10 days (Update 49, 2026) | [P via UESP] |
| Monster Hunter Rise | Pure-random armour reroll that could make gear worse | Randomness kept; steering modes added | [S] |
| Minecraft | Netherite template at 3.2% drop | 10% within one snapshot | [W] |
| Skyrim | Uncapped Fortify loop into smithing | Fixed by the community's Unofficial Patch only | [W] |
| PF2e (vs PF1e) | Materials as a flat price add-on with many armour numbers | Grades gated by crafter proficiency and level; mostly one effect each; caps on magic per grade | [P] GM Core |

**Things worth refusing, with reasons:**

- **Real-physics numbers for every material** (Dwarf Fortress). Its creator could not finish the
  data entry, and players learn it from the wiki. Use a few typed fields instead.
- **A single value number that feeds money, XP and unlocks** (Bannerlord).
- **Random quality bumps, or random losses after a successful roll** (WoW Inspiration, Qurious
  Crafting). The herbalism plan's rule holds here too: materials are lost only to the d20.
- **Real-time waiting as discovery** (ESO research). ZeniMax cut it by more than half after
  twelve years.
- **Mandatory minigames for routine output with no relief** (KCD2 horseshoes, Blacksmith
  Master, Vintage Story voxels). The owner chose "always play" for herbalism. If that carries
  over, bulk work and short games are the softeners, and this is the first thing to watch in
  playtest.

---

## 7. Critic pass: what is weak or unconfirmed

I re-checked the strongest claims after drafting. Corrections made during the pass:

- A research note said better metal in Giants' Foundry made each heat window "more forgiving".
  The wiki says the opposite: higher difficulty swords have smaller bars. Corrected above.
- A note said Dwarf Fortress silver "beats steel" for blunt weapons. The wiki page also says the
  six standard metals perform "nearly identically" for blunt weapons. Both are now stated.
- ESO: a note said the temper "can result in breaks" without saying what breaks. The official
  support page confirms the **item** is destroyed. Corrected.
- The catalogue comparison (§0 and §5.2) was checked line by line against the AoN text.

**Could not confirm**

- **PF1e special materials and Craft DC.** The core rules give no Craft DC change for special
  materials; they act through price (time) and through the masterwork component. I found no
  core sentence that says an "always masterwork" material requires the DC 20 component check.
  A search snippet listed DC modifiers (darkwood +2, mithral +4, dragonhide +4) that I could not
  trace to any Paizo book; they look like a homebrew or 3.5 variant. **Not used.**
- **Fragile quality text** comes from a search summary of the Ultimate Equipment page, not a
  direct read.
- **Masterwork prices** (300 gp weapon, 150 gp armour, 6 gp ammunition) come from a search
  summary of AoN's masterwork rules pages. They match the well-known Core values.
- **Mithral shield price.** AoN's text says +1,000 gp; a model summary of the PRD page said
  +1,500. AoN's verbatim line is used. Check the book before relying on it.
- **Whether a material name like "noqual" is Product Identity.** No Paizo ruling found. The PF2
  Remaster renaming of mithral and darkwood, and Paizo's continued use of skymetal names, is an
  inference, not a statement.
- **Dragonskin grip** (+2 CMD vs disarm, *Dragonslayer's Handbook*) comes from d20pfsrd only.
- **Umbrite** is 3.5-era or third-party; I did not identify its source book.
- **Xanathar's crafting table** comes from fan summaries; I did not read the book.
- **5e SRD adamantine and mithral armour** effects are stated from memory and not re-checked.
- **PF2e's design reason** for grades and level gates: no Paizo designer statement found. The
  "grades exist to make you pay before runes can climb" reading is from fan guides.
- **Burning Wheel** quality rules come from the official forums and a fan index, not the book.
- **KCD2:** the number and names of quality tiers, the scoring rule, and the patch 1.2 date
  (sources say 13 March 2025; the official page shows no date). Why KCD1 had no forging.
- **Bannerlord:** that metal grade does not change weapon stats (my inference); any patch that
  cut crafted-weapon prices directly (none found); the e1.6.0 quotes come through a mirror.
- **Valheim 1.0 Forge of Potential** item-destruction odds (one secondary source); left out.
- **WoW Midnight** gear-rank changes: Wowhead headlines conflict; only the reagent cut is used.
- **ESO** temper percentages, launch research timers, and when the 30-day cap began.
- **Terraria:** Redigit's reason for twin ores.
- **Wurm Online:** the modifier table was read through a page extraction that may have shifted
  columns. Treat individual numbers as approximate; the *shape* (a vector against iron) is
  certain.
- **Real-world:** the heat-colour table is Chapman's as reported by Wikipedia; colour
  perception depends on light, so other tables differ by tens of degrees. The quench severity H
  values come from a ScienceDirect topic overview, not the original handbook. The overheating
  and "sparks mean burning" claims come from blacksmith-supplier blogs and Knife Steel Nerds.
- **Not researched:** My Time at Portia's quality maths, Blacksmith Legends, Forge Industry,
  Swordsmith VR, and the Hammer & Anvil-style mobile games. No reliable sources were found.
