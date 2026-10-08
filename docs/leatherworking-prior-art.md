# Leatherworking revamp: prior art sweep

Research for the Leatherworker world class, done before any design. It follows the herbalism
and forge sweeps: the PF1e rules first, then games, then the real craft. The aim is that each
hide carries typed, rules-backed effects, the harvest is a real step, and the minigames rest on
variables a real tanner controls. Compiled 2026-10-04 against `docs/leatherworking-inventory.md`.

The conventions are those of `docs/herbalism-prior-art.md` and `docs/blacksmithing-prior-art.md`.

| Mark | Means |
|---|---|
| **[P]** | Primary: rulebook text through Archives of Nethys or Paizo's PRD, patch notes, developer posts and interviews, official sites, museum and conservation bodies. |
| **[W]** | Officially partnered wikis and UESP. |
| **[W\*]** | Wikis whose official status I could not confirm. |
| **[S]** | Fan wikis, press, forums, hobbyist sites and datamines. |

Rules text was read through a fetching tool that summarises pages. Short quotes are what that
tool returned; anything load-bearing is listed again in the critic pass (§7).

---

## 0. The headline findings

1. **In the book, leather armour is Craft (armor), not Craft (leather).** The Core Craft
   table files "Armor or shield" under Craft (armor) at DC 10 + AC bonus, and lists leather as
   a separate Craft with no armour row (§1.1). This settles the forge boundary question
   (`docs/leatherworking-questions.md` Q1.2) on the side of **one armour model**: the book
   already treats every suit as one kind of work. Who sits at the bench is a game decision,
   not a rules one.

2. **Dragonhide does not protect its wearer.** The book: if the dragon was immune to an
   energy type, the armour is immune too, "although this does not confer any protection to the
   wearer". What it does give is a 25% discount on later energy-resistance enchantments.
   - All 11 catalogue dragonhides give the **wearer** `resistance 5`.
   - The book also makes dragonhide armour masterwork by nature, wearable by druids, hardness
     10, and by default **hide armour** for a creature one size smaller than the dragon.
   - The best scales can make banded mail, half-plate, a breastplate or full plate for smaller
     wearers.
   - The app makes `leather` AC 2, and only masterwork if tooled (§1.3; inventory §0.7).

3. **The book has a harvesting rule, and it is not the app's.**
   - **Ultimate Wilderness**: identify with Knowledge, then harvest with Survival for external
     parts such as hide, each at **DC 15 + CR**. Components keep 24 hours. Value and weight
     come from tables by CR and size, and hides weigh double.
   - **Monster Hunter's Handbook**: the *Harvest Parts* feat requires a corpse dead less than
     an hour, values parts at CR² × 10 gp, and has them rot after 2 days.
   - **Dragonhide**: one dragon yields one suit for a wearer one size smaller.
   - **The app**: the DC comes from the crafter's own level, the carcass can be skinned
     forever, and the 48-hour clock is never started (§1.4; inventory §0.3).

4. **Games split on whether the creature reaches the item.** This is an observation, not a
   measurement of how much players care.
   - *Monster Hunter* puts each monster's identity into its armour's skills, and the series is
     built on that link.
   - *Skyrim*, *Kenshi*, *Dwarf Fortress* and *ESO* let the creature set only the tier, the
     count or the value. In ESO a wolf gives whatever tier the player is.
   - Dwarf Fortress names leather after the creature, but every leather shares one armour
     template.
   - The catalogue's 65 hides already lean toward Monster Hunter: each names its creature and
     carries a trait. It needs those traits typed, not more hides (§2).

5. **Studios handled crafting randomness three different ways.**
   - **WoW took it out.** It removed *Inspiration* (random extra quality) in The War Within for
     "a lack of decision making and agency", and replaced it with *Concentration*, a resource
     the player chooses to spend.
   - **ESO kept it.** An improvement can still destroy the item.
   - **Monster Hunter routed around it.**
     - High Rank gem odds in World stayed at 1–2%. Master Rank rates were 5–7%.
     - The producer denied the "desire sensor" (2014).
     - What shipped was deterministic conversion: World's Elder Melder turns Gold Wyverian
       Prints into a chosen gem.
     - *Wilds* kept random Artian bonuses and added rerolls on top.
   - **For hides**: grade should come from the player's hands, and no part should be a 1% roll
     with no conversion path (§2, §6).

6. **Real waits survived in in-world time, and were cut where they gated progression in real
   time.**
   - In-world waits that stayed:
     - *The Long Dark* cures hides on the floor in 3 to 12 in-game days. These figures could
       not be re-checked (§7).
     - *Vintage Story* soaks hides 20 hours, then tans them 3 + 4.5 days in a sealed barrel,
       and the soak stops rot.
   - A real-time gate that was cut: ESO's trait research, after years of complaints, from a
     30-day cap to 10 days (Update 49, March 2026). It also ran in the background, so running
     in the background is not what saves a wait.
   - The evidence is thin: two survival games against one MMO.
   - **Real tanning** is the slowest step of all: bark tanning took months and was sped up only
     in the 19th century (§3).
   - Tanning time can be real **world-clock** time that runs while the character does other
     things. It should never be a real-time gate on progression.

7. **Harvest quality from the player's own action was not found removed anywhere we
   checked.** Patch histories were not searched exhaustively.
   - *Red Dead Redemption 2*: a clean kill with the right weapon for the animal's size makes a
     perfect pelt.
   - *Wurm Online*: hide quality comes from skill plus knife quality, and caps the product.
   - *Mortal Online 2*: skinning at a butcher table wastes less than in the field.
   - *Skyrim* left harvesting instant; the depth lives in the *Hunterborn* mod.
   - **Penalising the kill** (RDR2's weapon classes) needs hit locations and weapon classes the
     engine does not model. The skinning step itself is the cleaner place for agency (§2).

8. **Several catalogue entries contradict the book.** Dragonhide (11 entries), eel hide,
   angelskin (in the forge's catalogue), bulette, boiled leather, the Craft DC, the failure
   rule, the harvest numbers, and the unreachable hide armour. Listed in full in
   `docs/leatherworking-questions.md`, "Book versus catalogue".

---

## 1. PF1e rules: Craft, leather armour, special hides, harvesting

### 1.1 The Craft procedure (Core Rulebook) [P]

Sources: https://www.aonprd.com/Skills.aspx?ItemName=Craft,
https://legacy.aonprd.com/coreRulebook/equipment.html

- **The procedure.** Raw materials cost one third of the price. One check a week (daily is
  allowed, at a seventh of the progress). On a success, check result × DC in silver pieces is
  added to progress.
- **Failure:**
  - by 4 or less: no progress that week;
  - by 5 or more: "you ruin half the raw materials and have to pay half the original raw
    material cost again."
- **Leather is a named Craft** ("…jewelry, leather, locks…").
- **The DC table puts armour under Craft (armor):** "Armor or shield | Armor | 10 + AC
  bonus". Other rows: a typical item DC 10, a high-quality item DC 15, a complex or superior
  item DC 20. No row gives Craft (leather) an armour DC.
- **Masterwork:**
  - crafted "as if it were a separate item", DC 20, 150 gp for armour or a shield;
  - masterwork armour lowers the armour check penalty by 1.
- **Tools:**
  - improvised tools: −2;
  - artisan's tools: 5 gp;
  - masterwork artisan's tools: 55 gp, +2 circumstance on Craft.
- **Repair:** the same DC, at one fifth of the price.
- **Hardness** (Core, Breaking Objects): leather or hide is hardness 2, 5 hp per inch.
  Armour's hit points are its armour bonus × 5. `rules/tables.py:436-437` already matches.

### 1.2 The leather suits [P]

Sources: https://www.aonprd.com/EquipmentArmorDisplay.aspx?ItemName=…

Speed is for a 30 ft. / 20 ft. creature. "In app" means a row exists in `tables.ARMOUR`.

| Suit | Class | Cost | AC | Max Dex | ACP | ASF | Speed | Weight | Source | In app |
|---|---|---|---|---|---|---|---|---|---|---|
| Padded | light | 5 gp | +1 | +8 | 0 | 5% | 30/20 | 10 lb | Core | yes |
| Quilted cloth | light | 100 gp | +1 | +8 | 0 | 10% | 30/20 | 15 lb | APG, UE | no |
| Leather | light | 10 gp | +2 | +6 | 0 | 10% | 30/20 | 15 lb | Core | yes |
| Studded leather | light | 25 gp | +3 | +5 | −1 | 15% | 30/20 | 20 lb | Core | yes |
| Wooden | light | 20 gp | +3 | +3 | −1 | 15% | 30/20 | 25 lb | APG, UE | no |
| Lamellar (leather) | light | 60 gp | +4 | +3 | −2 | 20% | 30/20 | 25 lb | UE, UC | no |
| Armored coat | medium | 50 gp | +4 | +3 | −2 | 20% | 20/15 | 20 lb | APG, UE | no |
| Hide | medium | 15 gp | +4 | +4 | −3 | 20% | 20/15 | 25 lb | Core | yes |
| Hide shirt | light | 20 gp | +3 | +4 | −1 | 15% | 30/20 | 18 lb | *Varisia* (campaign setting) | no |
| Leaf armor | light | 500 gp | +3 | +5 | 0 | 15% | 30/20 | 20 lb | *Inner Sea World Guide* | no |
| Spider-silk bodysuit | light | 850 gp | +3 | +6 | −1 | 10% | 30/20 | 4 lb | *Adventurer's Armory 2* | no |

**Rules that matter:**
- **Leather armour** is boiled leather in both books. Ultimate Equipment: "overlapping pieces
  of leather, **boiled** to increase their natural toughness". Core: "hard boiled leather
  carefully sewn together". Boiling is part of plain leather armour, not a level-4 extra.
- **Hide armour** is "the tanned skin of particularly thickhided beasts" (UE; Core says "any
  thick-hided beast"). That is exactly what a monster hide should make, and the bench cannot
  make it.
- **Leather lamellar is light in AoN's table but "Medium" on its own item page.** This doc
  follows the table.
- **Quilted cloth**: DR 3/— against small ranged piercing weapons.
- **Wooden armour**: fire-treated wooden plates sewn over leather.
- **Armored coat**: dons as a move action and layers over other armour.
- **Leaf armour**: always masterwork.

**Leather shield.** The madu (leather version) is 40 gp, +1 AC, ACP −2, 5% ASF, 5 lb, from
Ultimate Equipment and *Adventurer's Armory*. Druids may use the leather version.

**Piecemeal armour** (Ultimate Combat) builds suits from torso, arm and leg pieces in
"hard-boiled leather". The leather torso piece is +1 AC; the leather lamellar torso piece is
+2 AC. These numbers were not cross-checked (§7).

### 1.3 Special hides and leather materials [P]

Sources: https://legacy.aonprd.com/ultimateEquipment/armsAndArmor/materials.html,
https://www.aonprd.com/SpecialMaterials.aspx

| Material | Allowed on | Effect | Masterwork | Cost | Physical |
|---|---|---|---|---|---|
| **Dragonhide** (Core, UE) | any armour or shield an armorsmith makes | the armour is immune to the dragon's energy type, with no protection to the wearer; adding energy protection later costs 25% less; druids may wear it | always | double masterwork price, but double Craft results, so no slower | hardness 10, 10 hp/inch, ½–1 inch thick |
| **Eel hide** (UE) | leather, hide or studded leather | ACP −1 (min 0), max Dex +1, electricity resistance 2 | always | +1,200 gp light, +1,800 gp medium | as leather |
| **Angelskin** (UE) | leather, hide or studded leather | moderate good aura; the wearer's evil aura counts as 10 HD weaker; 20% chance effects aimed at evil treat an evil wearer as neutral | always | +1,000 gp light, +2,000 gp medium | hardness 5, 5 hp/inch |
| **Darkleaf cloth** (UE) | padded, leather, studded leather or hide | ASF −10% (min 5%), max Dex +2, ACP −3 (min 0), half weight | always | +750 gp light, +1,500 gp medium | hardness 10, 20 hp/inch |
| **Griffon mane** (UE) | cloak, robe, clothing, padded or quilted | +2 competence on Fly; flight powers added later cost 10% less | not stated | +200 gp light armour | twice cloth's hp, hardness 1 |
| **Bone** (UE, primitive) | studded leather, scale, breastplate, wooden shield | armour bonus −1; on studded leather, ACP also 1 better (to 0) | not stated | half price | hardness 5, fragile unless magic |
| **Bulette** (*Dungeon Denizens Revisited*, a Chronicles book) | — | see below | — | — | — |

**More on dragonhide:**
- **Yield:** one dragon gives one suit of masterwork **hide armour** for a creature one size
  smaller. If only the best scales are used, it gives instead:
  - banded mail, two sizes smaller;
  - half-plate, three sizes smaller;
  - a breastplate or full plate, four sizes smaller.
- A Large or larger dragon also gives enough for a shield.
- Ultimate Combat's piecemeal dragonhide pieces **do** give immunity, at "double the armor
  piece cost + 100 gp". This is a second, different rule for the same material.

**More on bulette:** one adult bulette yields two Medium suits of bulette plate (65 lb, max Dex
+2, hardness 12) and four Medium suits of leather or studded leather. Bulette leather costs 50
gp and has "the same statistics as studded leather".

**Not PF1e materials:** darkwood cannot make armour (items "not normally made of wood" gain
nothing). There is no PF1e spidersilk material (only the bodysuit and rope), no mammoth hide,
and no cuir bouilli as a named material.

**What the catalogue gets wrong**, against the table above:
- **Dragonhide:** wearer resistance instead of object immunity; not always masterwork; never
  hide armour.
- **Eel hide** (`electric-eel-skin`): has the resistance but lacks ACP −1, max Dex +1, always
  masterwork, and the suit restriction.
- **Angelskin** (the forge's `angelskin-binding`): Will +3, AC +2 and Diplomacy −3 are
  invented. The book's effect is about alignment auras.
- **Bulette** (`bulette-plate`): +3 armour-typed AC; the source says its leather is studded
  leather.

### 1.4 Harvesting creature parts

**Ultimate Wilderness, "Trophies and Treasures" (pp. 162–163)** [P]. Sources:
https://aonprd.com/Rules.aspx?ID=2428 to ID=2432.

- **Three steps, each at DC 15 + CR:**
  1. Identify what is worth taking: Knowledge by creature type, 1 minute.
  2. Harvest: **Survival for external parts (hide, horns, teeth)**, Heal for internal ones.
     10 minutes, up to an hour.
  3. Make the trophy: a Craft, "usually … alchemy, jewelry, leather, or taxidermy".
- **Components stay usable 24 hours from the harvest**, longer with *gentle repose* or *oil of
  timelessness*. Ultimate Wilderness sets no limit on how long the creature has been dead; the
  under-an-hour limit is the Monster Hunter's Handbook's (below).
- **Value by CR** (Table 4-9): CR 1 50 gp, CR 5 300 gp, CR 10 1,000 gp, CR 15 3,900 gp,
  CR 20 13,000 gp.
- **Weight by size** (Table 4-10): Medium 1d6 lb, Large 3d6, Huge 1d6 × 10, Gargantuan
  1d6 × 30, Colossal 1d6 × 100. "Doubled for bones, hides, and skins."
- **Magical affinities:** a part used as raw material for a related item counts 20% higher.
  The examples include a true dragon's breath organs for that energy, and troll liver for
  healing.
- **Not stated:** what a failed check does, and how many parts one creature yields.

**Monster Hunter's Handbook (Player Companion, 2017)** [P]. Source:
https://www.aonprd.com/FeatDisplay.aspx?ItemName=Harvest%20Parts

- ***Harvest Parts*** (p. 24):
  - a Craft or Heal check on a corpse dead under an hour, CR 1 or higher;
  - parts worth CR² × 10 gp, and template or class CR does not count;
  - parts serve only as raw material for items "typically bone or hide, with metal only in
    extraordinary cases", and can supply no more than a quarter of an item's cost;
  - parts rot after 2 days and cannot be bought or sold in most settlements.
- ***Grisly Ornament***: a one-day bonus against that creature type. One ornament per corpse,
  plus one per size above Medium.
- **Taxidermy tools** (80 gp): +2 on harvest checks, and prepared parts last twice as long.

**Core** has no skinning use of Survival. Its only yield rule is dragonhide's (§1.3).

### 1.5 Pathfinder Unchained alternate crafting (pp. 72–75) [P]

Source: https://www.aonprd.com/Rules.aspx?ID=1830

- **Progress and failure:**
  - a daily check; beating the DC by 5, 10 or 15 doubles, triples or quadruples progress;
  - failing by 5 or more wastes one day's base progress of material.
- **Difficulty steps:** light armour is *Simple* (DC 10), medium *Normal* (DC 15), heavy
  *Complex* (DC 20). Masterwork or a special material adds one step each.
- **Special raw-material traits:** easily worked, flawless, malleable and pure, as in the
  forge sweep.
- **Leather has its own row in Table 2-6,** and so do dragonhide, eel hide, angelskin,
  darkleaf cloth and griffon mane. Each priced by trait, e.g. leather "easily worked" at 6 gp
  per pound, dragonhide at 100 gp.
- **For leather, these four traits are rules, not house numbers.** That makes the forge's
  `working` layer directly reusable for hides.

### 1.6 Product Identity versus Open Game Content

- **Open:** Core, APG, Ultimate Equipment, Ultimate Combat, Unchained and Ultimate Wilderness
  are rulebooks whose mechanics Paizo releases as Open Game Content.
- **Possibly Product Identity:** the hide shirt (*Varisia*), leaf armour (*Inner Sea World
  Guide*), bulette armour (*Dungeon Denizens Revisited*) and the spider-silk bodysuit
  (*Adventurer's Armory 2*) come from campaign-setting, Chronicles and Player Companion
  books, whose Golarion names may be Product Identity.
- **Not checked:** each book's Section 15. Same caution as `docs/bestiary-licensing.md` and the
  forge's skymetal decision.

### 1.7 Pathfinder 2e and D&D 5e, briefly

- **PF2e Craft** (Player Core) [P]:
  - set up for 2 days (1 with the formula), then roll;
  - on a success, spend more days to cut the remaining cost, then pay the rest;
  - a failure salvages the materials, and a critical failure loses 10%.
- **PF2e dragonhide** (Player Core 2) [P]:
  - makes anything normally leather or hide, plus plate without metal;
  - the armour is immune to one damage type, and gives +1 circumstance to AC and saves against
    that type.
  - **PF2e gives the wearer a small edge where PF1e gave none.** That is precedent for a house
    top-up.
- **PF2e *Howl of the Wild*** [P] has beast armour whose formula requires a named creature's
  part (Hodag Leather, item 8). That is the Monster Hunter link, in Paizo's own system.
  - PF2e has no general harvesting rule.
  - Third-party *Battlezoo* "Monster Parts" [S] refines and imbues parts.
- **D&D 5e** has no core harvesting rule. *Heliana's Guide to Monster Hunting* is third party
  and was not verified.

---

## 2. Games: from the kill to the item

### Monster Hunter (Capcom): the creature becomes the armour

**The loop:** hunt, then carve or capture, collect parts, and craft armour whose skills are
themed on that monster. That link is the series' identity.

**Rare parts are 1–2% rolls.** World datamine [S]
(https://mhworld.kiranico.com/en/items/rM2Al/rathalos-ruby):

| Source | Rathalos Ruby chance |
|---|---|
| High Rank carves, head break, back break, capture | 1% |
| High Rank tail carve | 2% |
| High Rank gold investigation reward | 14% |
| Master Rank carves, head break, capture | 5–7% |

**The "desire sensor".** In October 2014 producer Ryozo Tsujimoto denied that the game
withholds the part you want, calling it confirmation bias [S, reporting a Siliconera interview]
(https://www.nintendolife.com/news/2014/10/weirdness_monster_hunter_series_producer_denies_existence_of_the_desire_sensor).
High Rank odds stayed at 1–2%. Iceborne's Master Rank rates were 5–7%. Capcom added
**deterministic conversion** alongside: World's Elder Melder melds High Rank gems from Gold
Wyverian Prints [S].

***Wilds* (2025) ties harvest to how you fight.** Director Yuya Tokuda describes repeated hits
opening a wound, and a Focus Strike that destroys the wound gives materials straight away from
a separate wound table [P]
(https://blog.playstation.com/2024/06/13/monster-hunter-wilds-interview-how-capcom-is-evolving-its-apex-franchise/).

**Wilds patches eased the upgrade grind** [S, Fextralife mirror of the notes]
(https://monsterhunterwilds.wiki.fextralife.com/Patch_Notes):

| Version | Date | Change |
|---|---|---|
| 1.020 | 30 Jun 2025 | auto-selected armour spheres |
| 1.040 | 16 Dec 2025 | more smelting points from monster materials; more spheres |

**Artian weapons** (generic parts, random reinforcement bonuses) were found to follow a fixed
sequence per weapon, and reroll and choice systems were added on top [S].

### World of Warcraft: Skinning and Leatherworking

- **Dragonflight (10.0.2, Nov 2022)** [P]
  (https://worldofwarcraft.blizzard.com/en-gb/news/23827585/dragonflight-preview-an-eye-on-professions):
  - gathered hides came in 3 quality ranks, crafted gear in 5;
  - higher-rank reagents added skill to the craft;
  - *Inspiration* gave a random chance of extra skill.
- **Skinning specialisation:** *Elusive Creature Bait* lures a stronger creature with more and
  unique hides, on a 12-hour cooldown that ordinary skinning shortens [S].
- **Crafting orders (10.0.5, Jan 2023)** [P]: Blizzard added "use highest quality reagent" and
  order rejection. Before launch it had pulled public recrafting "to protect customers from
  having their crafts inadvertently lowered in quality".
- **The War Within (blue post, 18 Apr 2024)** [P mirror]
  (https://www.bluetracker.gg/wow/topic/us-en/1833285-professions-update-concentration-in-the-war-within/):
  - *Inspiration* removed: no agency, no clarity for customers, too much chance;
  - replaced by *Concentration*, a regenerating pool that guarantees the next tier when spent.
- **Midnight (news, Aug 2025)** [S]: reagent ranks, leather included, cut from 3 to 2. Gear
  keeps 5.

### Elder Scrolls Online: Clothing

- **The creature does not matter.** Raw leather drops from animals, and its tier follows the
  player's Tailoring passive rank or character level, not the animal [W]
  (https://en.uesp.net/wiki/Online:Rawhide). Scraps are refined in batches.
- **Improvement with tannins is a gamble.** Hemming, embroidery, elegant lining, then Dreugh
  wax. A failure destroys the item [P]
  (https://help.elderscrollsonline.com/app/answers/detail/a_id/4028/). That players routinely
  pay for 100% is a community practice [S], not on the support page.
- **Traits are researched by destroying an item on a real-time timer** that doubles per trait.
  After years of complaints, Update 49 (9 March 2026) cut it by more than half, from a 30-day
  cap to 10 days. ZeniMax wanted to keep a "chase" [W reproducing the notes]
  (https://en.uesp.net/wiki/Online:Update_49).

### Skyrim (Bethesda)

- **No skinning.** The pelt is loot. A tanning rack turns hide into leather, and leather into 4
  strips, instantly. Smiths sell leather, so hunting is optional [W]
  (https://en.uesp.net/wiki/Skyrim:Leather).
- **The creature sets the sale value and conversion count, never the armour.** Several pelts
  are worth more raw than tanned.
- **Survival Mode (Oct 2017)** added warmth to armour and left tanning alone [W].
- **The *Hunterborn* mod** [S] (https://www.nexusmods.com/skyrimspecialedition/mods/7900) adds
  what vanilla lacks:
  - a skinning step;
  - pelt quality that starts poor and rises with a Skinning skill;
  - better knives for better results;
  - harvesting trolls and dragons.

### Red Dead Redemption 2 (Rockstar): harvest quality from the kill

- **Animals show 1 to 3 stars.** Only a 3-star animal killed with one clean shot from the right
  weapon class for its size gives a perfect pelt. Wrong weapon or extra shots downgrade the
  carcass, and carcasses rot faster in heat [S]
  (https://www.gamesradar.com/red-dead-redemption-2-perfect-pelts-how-to-get/).
- **Pelts become items through NPCs:** the Trapper's outfits and Pearson's satchels. Legendary
  pelts unlock unique items.
- **It works because the engine models weapon class and hit location.** Ours does not (§5.3).

### Survival games: yield, tools and waiting

- **Rust** [S]: leather comes straight off the carcass; knives and hatchets give full yield.
- **ARK** [W] (https://ark.wiki.gg/wiki/Hide): the tool sets the ratio (hatchet favours hide,
  pick favours meat); some tames are top harvesters; chitin comes from arthropods. No tanning.
- **Conan Exiles** [S] (https://conanexiles.wiki.fextralife.com/Tannery): a tannery turns hide
  into leather with bark as both agent and fuel. A tanner thrall speeds the queue. Seconds per
  craft.
- **The Long Dark** [S] (https://thelongdark.fandom.com/wiki/Curing):
  - **fresh hides cure on the floor indoors**, in in-game time, even while you are away:
    rabbit 3 days, deer 5, wolf 7, black bear 12;
  - uncured hides lose condition (deer about 3.3% a day on Stalker) and are destroyed at 0;
    cured hides never decay;
  - harvest speed depends on the tool, how frozen the carcass is, and the Carcass Harvesting
    skill.
- **Vintage Story** [W] (https://wiki.vintagestory.at/Leather_working): **the real chain, in
  game time.**
  - Animals drop small, medium, large or huge hides.
  - Soak in limewater or borax for 20 hours (a soaked hide no longer rots), then scrape.
  - Seal in weak tannin for 3 days, then strong for 4.5 days.
  - Yield by size: 1, 2, 3 and 5 leather. The barrel's volume caps the batch.
- **Kenshi** [S]: skins go to a tanning bench, then an armour bench. Armour quality grade comes
  from the crafter's skill, and the creature does not carry through.
- **The Forest** [S]: skins are used raw.
- **Green Hell**: drying times could not be confirmed (§7).

### RuneScape and Old School RuneScape

- **OSRS tanners are NPCs who tan for coin** [W] (https://oldschool.runescape.wiki/w/Tanner):
  cowhide 1 coin, hard leather 3, snakeskin 15, any dragonhide 20.
  - A late spell (*Tan Leather*, Magic 78) removes the trip.
  - Tanning was once planned as part of a separate Tailoring skill.
- **Dragonhide armour is a colour ladder** (green, blue, red, black) gated by Crafting level [W].
  The creature carries over only as tier.
- **RS3's Portable crafter (July 2015)** [W]: tanning anywhere at the tanner's price, +10% XP,
  and a 10% chance to save a hide. **It removed the walk, not the cost.**

### Kingdom Come: Deliverance 1 and 2

- **KCD1** had no crafting of arms or armour [S].
- **KCD2** adds blacksmithing. Armour is repaired, not made: an armourer's kit for metal, a
  tailor's kit for cloth, a cobbler's kit for leather boots and gloves [S].
- **Hunting is poaching.** Deer skin is bought from butchers and saddlers, and guides disagree
  whether hunting gives it [S].
- **No tanning and no hide quality.**

### Valheim

- **Hides are used raw.** The "tanning rack" is a workbench upgrade, not a step [W\*].
- **A pure biome ladder:** deer hide, troll hide, wolf pelt, lox pelt. Higher-star animals drop
  more, and nothing drops better.
- **Themed effects** (frost resistance on wolf gear) are fixed per recipe, not per hide.

### Dwarf Fortress, Wurm Online, Mortal Online 2, Far Cry

- **Dwarf Fortress** [S] (https://dwarffortresswiki.org/index.php/Leather):
  - butchering gives 1 to 3 skins by body size;
  - leather is **named for the creature and valued by it**, but every leather has the same
    armour stats.
- **Wurm Online** [W\*] (https://www.wurmpedia.com/index.php/Leather):
  - hide quality comes from butchering skill, the knife and luck;
  - tanning needs lye (0.10 kg per 3 kg of hide);
  - **the hide's quality caps the product's.**
- **Mortal Online 2** [P] (https://www.mortalonline2.com/features/crafting/): skin in the field
  with a knife, or haul the carcass to a butcher table that wastes less.
- **Far Cry 3 and 4** gated holsters, wallets and bags behind specific animal skins. **Far Cry
  5 (2018) dropped skin crafting entirely** for cash and perks [S].

---

## 3. The real craft, for grounded minigames

This section is for minigames that read as the real craft. Each subsection names a variable a
tanner actually controls, and gives its real range.

### 3.1 Flaying and the cure clock

- **The cure window is hours, not days.**
  - ALLPI (the African Leather and Leather Products Institute) handbook [P]
    (https://allpi.int/courses-and-publications/reports/manuals?download=101%3Ahides-and-skins-improvement-handbook-trainer-s-manual):
    cure within **four hours** of flaying in the tropics, the window lengthening as it gets
    cooler. Uncured hides left folded for a few hours slip their hair. Saturated brine takes
    24 hours.
  - NMSU Extension Guide L-103 [P]
    (https://nmsu.contentdm.oclc.org/digital/api/collection/AgCircs/id/134/download): tan
    within a day or cure promptly. Salt at 1 lb per lb of hide, re-salt when it saturates (2–3
    days); the hide is dry in 10–14 days.
  - FAO [P] (https://www.fao.org/4/x6552e/X6552E10.htm): dry-salting at 25% of green weight.
    About 15% salt keeps a hide for six weeks.
- **Hide grading is by defect area.** UNIDO's Leather Panel standard [P]
  (https://leatherpanel.org/sites/default/files/publications-attachments/grading_of_hides_and_skins_by_quality_eng.pdf):

  | Grade | Defects allowed |
  |---|---|
  | 1 | Clean butt; at most a few scores or one hole in the bellies |
  | 2 | A few small holes or cuts in the butt |
  | 3 | Some putrefaction; defects on up to 30% of the area |
  | 4 | Defects on up to 50% of the area |
  | Reject | Anything worse |

  Flaying defects (cuts, scores, holes) are one of its five defect groups. Curing defects
  (putrefaction, hair slip) are another.
- **The UNIDO standard is a draft** from its Regional Africa scheme (US/RAF/88/100), not a
  universal one. Grade 1 also requires the neck to be clean.
- **Flaying damage is common, even at scale.** At one Ethiopian tannery, flay cuts and scores
  were found on 22.8% of wet-blue cattle hides, 28.7% of goat skins, and 23.8% overall [P]
  (https://pmc.ncbi.nlm.nih.gov/articles/PMC6238661/).
- **A grade ladder of four plus reject**, set by the player's own knife, is grounded and
  readable.

### 3.2 Fleshing, liming, deliming, bating

- **Home liming (NMSU)** [P]: hydrated lime, **6–10 days**, until the hair pushes off by hand.
  Rinse, then delime for 24 hours.
- **Industrial (FAO)** [P]: liming at pH 12–13, deliming and bating at pH 8.5–9.
- **Historically,** hides went through a series of lime pits and were scraped over a beam
  (Colonial Williamsburg, *The Leatherworker in Eighteenth-Century Williamsburg* [P]).
- **Bating** used dog or bird dung until Otto Röhm's pancreatic enzyme from 1907 [P]
  (https://www.roehm.com/en/history-of-rohm).

### 3.3 Tanning methods and their times

**Shrinkage temperature** is the point at which wet leather suddenly shrinks. It is the cleanest
single number separating the tannages. AIC conservation wiki, citing Haines 2011 [P]
(https://conservation-wiki.com/wiki/BPG_Animal_Skin_and_Leather):

| Material | Shrinks at |
|---|---|
| Raw skin | 58–64 °C |
| Alum-tawed | 55–60 °C |
| Vegetable, hydrolysable tannins | 75–80 °C |
| Vegetable, condensed tannins | 80–85 °C |
| Chrome | 100–120 °C |

Oil tanning barely raises it, and brain tan needs smoking to become permanent.

| Tannage | Time | Character | Source |
|---|---|---|---|
| **Oak bark pits** | 3 months in liquors running weak to strong, then 9 months layered with bark: **12 months**. Williamsburg's account says up to 18 months for a heavy hide (not re-checked). | Firm, the only kind that boils and burnishes well | J & FJ Baker, Colyton [P] (https://www.jfjbaker.co.uk/the-process); Williamsburg [P] |
| **Legal minimum** (not re-checked) | 12 months for strong leather. Only bark allowed until 1808. | — | Leather Act 1563, via Riello 2006 [P] (https://wrap.warwick.ac.uk/id/eprint/360/3/WRAP_Riello_HR_riello.pdf) |
| **Alum tawing** | A soak of days (NMSU's 2–5 days, not re-checked), then several weeks of ageing | White, stretchy, **reverts in water** | Etherington & Roberts [P] (https://cool.culturalheritage.org/don/dt/dt3458.html); NMSU |
| **Brain and smoke** | Overnight soak, then continuous working until dry, then hours of smoking | Soft; smoke makes it water-resistant, not waterproof | NMSU [P] |
| **Oil (chamois, buff)** | Fish oils oxidised in the skin | Soft, washable. Buff leather was real armour. | Etherington & Roberts [P] |
| **Chrome** (1858 / 1884) | **6–8 hours** of drumming | Boil-fast; a blue core in the cut | UNIDO [P] (https://www.unido.org/sites/default/files/2009-05/Chrome_management_in_the_tanyard_0.pdf) |

**Bark tanning is done when the hide is "struck through".** Cut it, and the tan colour runs the
full cross-section. The liquor is strengthened step by step to get there [P]
(https://cool.culturalheritage.org/don/dt/dt3685.html). That is a ready-made "is it done?"
check, and a minigame: raise the strength in steps, and finish with a cut test.

### 3.4 Currying and staking

- **Staking** pulls the skin over a blunt blade to soften it [P]
  (https://cool.culturalheritage.org/don/dt/dt3303.html).
- **Currying** works cod oil and tallow (dubbin) in with a slicker, for strength, suppleness and
  water repellency [P] (https://cool.culturalheritage.org/don/dt/dt0935.html).
- **Conservation targets for finished leather:** water 12–20%, fat 2–10%. Outside those ranges
  it deteriorates faster [P] (WA Museum conservation manual,
  https://manual.museum.wa.gov.au/book/export/html/135/).

### 3.5 Cuir bouilli

- **Etherington & Roberts** [P] (https://cool.culturalheritage.org/don/dt/dt0921.html):
  - soaked **vegetable-tanned** leather is moulded and dried, or dipped in boiling water for
    **20–120 seconds**;
  - the tannins set into a hard, resin-like network;
  - **wax filled the tooled hollows; it was not the hardener.**
- **Jean Turner's experiments** [S]
  (https://www.jeanturner.co.uk/static-content/tutorials/CuirBouilliTechnique.pdf):

  | Immersion | Size | Thickness | Result |
  |---|---|---|---|
  | About 30 s in hot water | about 7/8 | about +25% | Hard but flexible |
  | About 40 s in boiling water | about 2/3 | roughly double | Brittle |

  She also says no medieval recipe survives.
- **Waterer** (moulded and dried at 50 °C) and **Dobson** (oven-dried at 70 °C) both argue
  that true boiling makes leather too brittle for armour. Both are known only through secondary
  summaries [S].
- **The band is this doc's synthesis, not a sourced recipe.** The sources disagree on method:
  - Waterer hardens at 50 °C;
  - Dobson at 70 °C;
  - Etherington & Roberts dip briefly in *boiling* water, above the shrink point.

  **What they share** is a trade of time and heat against hardness and brittleness. Too
  little, and the leather stays soft. Too much, or too long, and it shrinks and turns brittle,
  as Turner's 30-second and 40-second results show. A heat-by-time window with that trade is
  grounded; any exact edges are ours.
- **The source describes the method only with vegetable tan.** That alum and brain leather do
  not set is an inference from their low shrinkage and their reversion in water.
- **The shipped catalogue gets two things wrong:**
  - its Harden method *requires* a wax (`rules/leatherworker.py:916`), when wax was a finish;
  - its prose calls raw hide "glue" in the kettle. Raw hide does shrink and gelatinise at 58–64
    °C, so refusing untanned hide is right, but the reason is the tannage, not the wax.

### 3.6 Stitching, casing, tooling

- **Stitch pitch, in stitches per inch (SPI)** [S]
  (https://www.fineleatherworking.com/blog/how-many-stitches-per-inch-leather/,
  https://armitageleather.com/saddle-stitching/):

  | Work | SPI |
  |---|---|
  | Saddle skirts | 9 |
  | Bridle | 10 |
  | Benchmark, show work | 12 |
  | Common in saddlery | 14 |
  | Possible at the fine end | 18 |

  The saddle stitch uses two needles on one thread, so each stitch locks independently.
  Finer pitch means slower, better work, which is a natural quality ladder.
- **Casing** dampens leather before tooling. The target is a surface that has returned to its
  natural colour but still feels cool [S] (Weaver Leather Supply). **No published moisture
  percentage exists**, so a band would be time since wetting.
- **Burnishing** works on vegetable tan only; chrome tan goes fuzzy [S].
- **Thickness is measured in ounces:** 1 oz = 1/64 inch, about 0.4 mm. Harness leather is 9–10
  oz [S].

### 3.7 Did leather armour exist, and who made it?

- **Leather lamellar is real.**
  - Royal Armouries [P]
    (https://royalarmouries.org/objects-and-stories/stories/the-mongols/arms-and-armour-of-the-mongol-empire):
    small plates of hardened leather or iron, pierced and laced, suited to steppe cavalry.
  - Japanese armour mixed iron and leather scales, laced and lacquered [S]. Its hardened rawhide
    is *nerigawa*. Wikipedia's claim that nerigawa is ray skin confuses it with *samegawa*.
  - Rawhide scale is known from Tutankhamun's tomb (UCL Petrie Museum) [P].
- **Buff coats (17th century)** were oil-tanned leather armour, 1.5–5.3 mm thick. Tested
  against 12-bore balls, the whole clothing system (shirt, waistcoat and buff coat) had a
  half-penetration speed of about 102 m/s: limited protection [P]
  (https://pmc.ncbi.nlm.nih.gov/articles/PMC7417417/).
- **The brigandine's construction is documented** [P, British Museum object]: steel plates
  riveted between layers of cloth, or to an outer layer, with only the rivet heads showing.
  - A **common hobbyist explanation** is that "studded leather" misreads the brigandine. I
    found no primary source for it, and other origins are proposed.
  - Either way, the construction supports the questions doc's split: the leatherworker makes
    the body, and the smith's studs or plates are the fastenings.
  - **Roman "leather cuirasses":** there is no surviving example; the idea is popularised by
    film [S].
- **The trades were legally separate.** Medieval Londoners, Fordham [P]
  (https://medievallondoners.ace.fordham.edu/occupations/):

  | Trade | What they made, and their rights |
  |---|---|
  | Cordwainers | New shoes; they had the power to search tanned leather |
  | Cobblers | Old shoes, under a 1395 agreement with the cordwainers ("repairs only" is not on the page) |
  | Curriers | Dressing leather after tanning |
  | Whittawyers | Alum-white leather |
  | Girdlers | Belts |
  | Saddlers | Saddles |
  | Bottlemakers | Leather bottles |

  The Leather Act 1603/4 barred tanners from currying, and curriers from tanning (seen through
  search snippets only). In Paris, the *gainiers* made cuir bouilli sheaths, quivers and cases.
  - **There was no single leatherworkers' guild.** The work was a chain of separate trades,
    and the hardened-leather case-maker had its own guild. Colonial Williamsburg's general
    "leatherworker" is a colonial generalist. That supports one class with several methods,
    and a tannery as a separate place.

### 3.8 Exotic hides

- **Shagreen** (Leather Conservation Centre) [P] (https://leatherconservation.org/spotlight-on-shagreen/):
  - from horse or donkey, it is made by pressing seeds into the skin;
  - from ray or shark, it is **untanned** and parchment-like, its denticles ground smooth.
  - It is a grip material, which matches the forge's `sharkskin-grip`.
- **"Eel skin" leather is hagfish**, sewn from narrow strips of 70 or more skins [P]
  (https://www.adfg.alaska.gov/index.cfm?adfg=wildlifenews.view_article&articles_id=857).
- **Fish leather** has a crossed-fibre structure, strong for its thickness [P-ish, Smithsonian].
- **Thickness by animal** (finished, sellers' figures [S]):

  | Animal | Thickness |
  |---|---|
  | Lamb | 0.5–0.8 mm |
  | Goat | 0.6–1.6 mm |
  | Deer | 1–1.4 mm |
  | Cattle | 1–5+ mm |

### 3.9 Candidate minigame bands

| Method | Real variable | Band (the real number) |
|---|---|---|
| **Harvest** (skinning) | Knife depth along the cut line; defect area | Scored against UNIDO grades 1–4 (clean butt → defects on up to 30% / 50% of area → reject). Under the US #1 standard, any score deeper than half the thickness fails it |
| **Salt** (cure) | Hours since flaying; salt weight | Under about 4 h in heat, about 1 day when cool; salt at 25% of green weight or 1:1 |
| **Flense / lime** | Scraping strokes; lime days | 6–10 days of liming at pH 12–13, until hair pushes off by hand; delime 24 h |
| **Tan** | Liquor strength stepped up; the cut test | Weak to strong over months (bark), until struck through. Alum 2–5 days. Brain overnight plus working to dry. |
| **Harden** | Water temperature × time | Our synthesis, not a sourced band: roughly 50–85 °C for minutes, or 20–120 s boiling. About 30 s gives 7/8 size, hard and flexible; about 40 s boiling gives 2/3 size and brittle |
| **Stitch** | Stitch pitch and rhythm | 8–9 SPI rough, 10–12 good, 14–18 fine |
| **Tool** | Time since casing | Colour returned, still cool. No published percentage, so time-based |
| **Curry** | Fat worked in | 2–10% fat, 12–20% water as the healthy range |

**Shrinkage temperature as a stat, not a game.** Alum 55–60 °C, vegetable 75–85 °C (both
kinds), chrome
100–120 °C. This gives each tannage a grounded heat tolerance, and so a grounded reason for a
fire trait.

---

## 4. Tabletop beyond PF1e

- **PF2e** gives dragonhide a small wearer benefit (+1 circumstance vs its damage type) on top
  of immunity (§1.7). That is a precedent for house top-ups on book entries, which the forge
  already uses.
- **Howl of the Wild** makes a named creature's part a formula requirement. This is the
  Monster Hunter link in Paizo's own system, and the shape of "a hide inherits from its
  creature".
- **Ultimate Wilderness and the Monster Hunter's Handbook** together are the closest thing to a
  harvest system in PF1e:
  - DC by CR;
  - Survival for hides;
  - a freshness window;
  - value by CR, weight by size;
  - a cap on how much of an item's price parts can supply.

---

## 5. What to take

These are recommendations, not findings. Each is tied to the evidence above.

### 5.1 Build into the forge's armour model

- **One armour model.**
  - The book files all suits under one skill (§1.1), and the forge already has the record,
    the build and the sheet readers.
  - A hide is the **body** of leather, studded leather, hide, leather lamellar and padded
    suits.
  - Studs, buckles and rings are the **fastenings**, and are already linked to forge metals.
  - Fur, felt or soft leather is the **lining**.
- **Add the missing suits** to `tables.ARMOUR`: quilted cloth, leather lamellar, wooden
  armour, armored coat, and the madu shield. Licensing permitting, also bulette leather (as
  studded leather) and the hide shirt.

### 5.2 Fix the book entries first

Do it as the forge did:
- **Dragonhide:**
  - the armour is immune to the dragon's energy;
  - always masterwork;
  - hide armour by default (scales for metal-pattern suits at smaller sizes);
  - druid-wearable;
  - hardness 10;
  - −25% on energy-resistance enchantments;
  - any wearer resistance is a house top-up held to the tier ceiling, with PF2e's +1 as
    precedent.
- **Eel hide:** add ACP −1, max Dex +1 and always masterwork.
- **Angelskin:** replace the invented numbers with the aura rule, or mark it house if aura
  rules do not exist.
- **Bone, darkleaf cloth, griffon mane:** add them. Ask whether cloth belongs to this craft.

### 5.3 Harvest: one step, the book's numbers, the player's hands

- **One harvest per carcass**, DC 15 + CR, Survival or Craft (leather). Mark the carcass.
- **Two clocks, both from the books.** The corpse must be fresh at harvest: under an hour, by
  the Monster Hunter's Handbook. The hide's own clock starts at the harvest: 24 hours by
  Ultimate Wilderness, 48 by today's tests. Salt stops it (herbalism's rule).
- **The yield follows creature size** (the dragonhide ratio and Ultimate Wilderness's weight
  table), not the margin of a d20.
- **Grade from the skinning minigame.** Wurm Online's rule, that hide quality caps the
  product's quality, is the clean version: the hide's grade becomes the ceiling for the work
  made from it.
- **Do not grade by the kill.** RDR2's rule needs weapon classes and hit locations, and it
  punishes a player for how a fight went rather than for how they worked.
- **Match the creature by its stat block, never by words in its name.**
  - Type, subtype, size and CR come from the bestiary.
  - A named hide wins where one exists. Otherwise a generic hide carries what the stat block
    says: energy resistance, DR type, natural armour.
  - Humanoids are never skinned.
  - This also makes a World Bible beast with a stat block skinnable.
- **One harvest dialog for all four crafts**, each part taken once, instead of four repeatable
  excursions.

### 5.4 Tanning time: real, in in-world time

- **The Long Dark and Vintage Story kept long cure and tan times in in-world time.** ESO's
  research timers ran in real time and gated progression, and were cut. The evidence is thin
  (§0.6), so treat this as a direction, not a rule.
- **So:** brain or smoke tanning in about a day of bench work; bark tanning for weeks, in a vat
  that holds the hide while you travel, or carried as herbalism's steeping jar is.
- **A tannery vat is the relief valve,** as RS3's Portable crafter removed the walk but kept the
  cost.

### 5.5 The creature reaches the item, by rule

- **Monster Hunter's link, in typed form.** Each named hide carries ≥3 armour modifiers (≥1
  negative), the book's numbers where they exist, house numbers at ±2 otherwise, under the
  forge's validator. Grip-capable hides carry a weapon list too.
- **Generic hides derive theirs from the stat block** (an inherited energy resistance capped by
  tier), so no model authors a number.

### 5.6 No random quality, no 1% parts

- **Quality** comes from the minigame under the level's ceiling, as at the forge (WoW's reason
  for removing Inspiration).
- **If a rare part exists** (a perfect pelt, a dragon's finest scales), make it deterministic or
  convertible (the Elder Melder lesson), not a 1% roll.

### 5.7 Working traits from Unchained

- **Leather has its own row** for easily worked, flawless, malleable and pure, so hides and
  leathers take the forge's `working` layer unchanged.
- **Tannins, oils and waxes** carry working traits and at most one small mark, as quenchants
  do.

### 5.8 World Bible

- Hides as `play.materials[]` rows, the same shape as the forge's.
- A fauna list with type, size, CR and resistances, so a world's own beasts can be harvested.

---

## 6. What others tried and abandoned

| Game | Tried | Abandoned or changed to | Source |
|---|---|---|---|
| WoW | *Inspiration*: random extra quality | *Concentration*, a pool you spend for a sure tier. Reasons: agency, customer clarity, chance | [P mirror] blue post, Apr 2024 |
| WoW | Public recrafting orders | Pulled before launch to protect customers from lowered quality | [P] 10.0.5 notes |
| WoW | 3 reagent ranks, leather included | 2 (Midnight) | [S] Wowhead |
| Monster Hunter | Pure-luck gems at 1–2% (High Rank) | High Rank odds kept; Master Rank 5–7%; conversion added (Elder Melder, Melding Pot), plus better reward channels (investigations) | [S] datamine and wiki |
| Monster Hunter | Players' "desire sensor" belief | Denied by the producer (2014); answered with conversion, not odds | [S] interview report |
| MH Wilds | Manual sphere and Artian material selection | Auto-selected (1.020); more points from monster materials (1.040) | [S] notes mirror |
| ESO | Trait research to a 30-day cap | 10 days, more than 50% faster (Update 49, 2026) | [W] |
| ESO | Improvement that can destroy the item | Kept; players are reported to pay for 100% | [P] support page; [S] community practice |
| RS3 / OSRS | Walk to the tanner | Portable crafter (2015), Tan Leather spell; the coin cost kept | [W] |
| Far Cry 3 → 5 | Gear upgrades gated on specific animal skins | Removed; skins became cash | [S] |
| Skyrim | Instant tanning, no skinning | Kept in the base game; depth added only by mods | [W], [S] |
| KCD1 | No arms or armour crafting (a planned feature cut for time, per an unsourced summary) | KCD2 added smithing, still no leatherwork | [S], unconfirmed |

**Not found removed, in what we checked (patch histories not searched exhaustively):**
- long curing and tanning waits that run in the background (The Long Dark, Vintage Story);
- harvest quality from skill and tools (Wurm, Mortal Online 2, Hunterborn);
- the clean-kill rule in RDR2.

**Things worth refusing, with reasons:**
- **Hides as the player's tier, not the creature's (ESO).** It erases the one thing this craft
  is about.
- **One template for every leather (Dwarf Fortress, Skyrim).** Same reason.
- **1% rare parts with no conversion path (Monster Hunter's base odds).** The backlash is a
  decade old.
- **Destroying an item on a failed improvement (ESO).** The cross-craft rule already says
  materials are lost only to the d20.
- **Grading by how the kill was made (RDR2), here.** It needs engine facts we lack, and it
  would punish fire and acid users.
- **Gating gear on specific rare skins (Far Cry 3–4).** Removed by the same studio.

---

## 7. Critic pass: what is weak or unconfirmed

A second agent re-fetched the primary pages for the load-bearing claims after the draft was
written. Its web-search budget ran out partway, so the later checks used direct fetches only.

### 7.1 Confirmed against the primary text

- **Core Craft:**
  - "leather" is a listed Craft;
  - the DC row reads "Armor or shield | Armor | 10 + AC bonus";
  - fail by 5+ ruins half the materials;
  - masterwork armour is 150 gp at DC 20;
  - repair is one fifth of the price; tools −2 / +2.
- **Dragonhide,** verbatim: "does not confer any protection to the wearer". Also: −25%
  energy protection, the size ladder, the shield, druids, hardness 10, 10 hp per inch, and
  double cost with doubled Craft results.
- **Eel hide, angelskin, darkleaf cloth, griffon mane and bone:** every number in §1.3.
- **The suits table** against AoN's light and medium tables.
- **Ultimate Wilderness,** all of §1.4's numbers. **Harvest Parts:** under an hour, CR² × 10,
  a quarter of the cost, 2 days to rot, page 24.
- **Unchained:** the difficulty steps and Table 2-6's leather and dragonhide rows.
- **WoW:**
  - the 18 April 2024 post's three reasons: agency, clarity for customers, chance;
  - Concentration and Ingenuity;
  - Midnight's two reagent ranks (Wowhead, 28 August 2025).
- **ESO Update 49:** 9 March 2026, from 30 days to 10, "healthy 'chase'".
- **Monster Hunter:** the 2014 desire-sensor denial, and the Rathalos Ruby rates.
- **Vintage Story's** soak and tan times and yields.
- **Real craft:**
  - Etherington & Roberts on cuir bouilli (20–120 s; wax to preserve designs, not to harden)
    and on alum tawing (weeks of ageing; reverts in water);
  - Haines's shrinkage temperatures;
  - the Baker tannery's 3 + 9 months;
  - UNIDO's grade areas;
  - ALLPI's four hours;
  - the buff-coat thickness and V50.

### 7.2 Corrected during the pass

| Claim in the draft | Correction |
|---|---|
| "Capcom never raised the odds" | Master Rank rates are 5–7%. The gold investigation rate is 14%, not 13%. "Reward prints" are Gold Wyverian Prints. |
| "Randomness on the craft was taken out" | Only WoW took it out. ESO kept item destruction; MH Wilds kept random bonuses and added rerolls. |
| Background waits survive; calendar gates get cut | ESO's timers also ran in the background. The real difference is in-world time against real-time progression gates, and the evidence is three games. |
| "After twelve years of complaints" | That is the game's age, not a measured complaint history. Now "after years of complaints". |
| The split "predicts how much players care" | Unmeasured. Now an observation. |
| "Held up wherever it shipped" / "never removed" | Patch histories were not searched. Now "not found removed in what we checked". |
| Ultimate Wilderness's 24 hours on the corpse | The 24 hours runs from the harvest. The corpse-age limit is the Handbook's. |
| "Studded leather is a misreading of brigandine" [P] | No primary source. A hobbyist explanation [S]; only the brigandine's construction is documented. |
| "Roman leather cuirasses are a film invention" | Softened: no surviving example, popularised by film. |
| "There is no leatherworker in history" | Contradicted by the Williamsburg title. Now "no single leatherworkers' guild". |
| Cuir bouilli band "below it nothing sets, above it brittle" | It contradicts Waterer (50 °C) and the boiling dip. The band is labelled as our synthesis. |
| "Alum and brain leather do not set" | An inference, now marked as one. |
| Buff coat V50 of 102 m/s | For the whole clothing system, not the coat alone. |
| Ethiopian flay defects 22.8% | Wet-blue cattle hides only. Goat 28.7%, overall 23.8%. |
| Vegetable shrinkage 75–85 °C | Two ranges: hydrolysable 75–80, condensed 80–85. |
| The Baker tannery's "up to 18 months, two years for ox" | Not on the Baker page; attributed to Williamsburg, unchecked. |
| ESO tier "follows the passive rank" | The passive rank or the character level. "Always pay for 100%" is community practice, not on the support page. |
| The Leather and Hide quotes | They are Ultimate Equipment's wording. Core's differs ("hard boiled leather"; "any thick-hided beast"), and both say boiled. |

### 7.3 Could not confirm

- **The Long Dark:** the curing times (3 / 5 / 7 / 12 days), the indoor rule, the decay
  rates, and that cured hides never decay. The wiki refused the fetch.
- **The Leather Act 1563** twelve-month rule and the bark-only rule until 1808 (Riello was
  unreachable).
- **The Leather Act 1603/4** tanner and currier split (search snippets only).
- **Williamsburg's** 18-month and two-year figures.
- **NMSU's** 2–5 day alum soak.
- **Waterer's 50 °C and Dobson's 70 °C** for cuir bouilli: secondary summaries only. Jean
  Turner's water temperature is printed as "180˚C", presumably meaning °F.
- **The Tutankhamun rawhide scale:** the tomb's armour is generally held in Cairo, not at UCL;
  verify which collection.
- **The nerigawa and samegawa confusion,** and the Royal Armouries Mongol page.
- **Ultimate Combat:** the piecemeal leather pieces' numbers, and piecemeal dragonhide's
  "double the armor piece cost + 100 gp" with immunity.
- **The Monster Hunter's Handbook:** the CR 1 floor, the template and class exclusion, Grisly
  Ornament, and taxidermy tools.
- **The source books in §1.2** for quilted cloth, the hide shirt, leaf armour and the
  spider-silk bodysuit.
- **Bulette armour** (*Dungeon Denizens Revisited*), not re-checked.
- **Sunsilk's** DR 2/bludgeoning.
- **PF2e:** dragonhide's +1 circumstance bonus, and *Howl of the Wild*'s Hodag Leather (the 2e
  search failed on the re-check). The legacy PF2e Craft's 4-day wording.
- **MH Wilds:** the patch dates (1.020, 1.040) and the Tokuda wound quote, re-checked through a
  fan mirror only; Capcom's 1.020 page returned 403. Whether broken-part or wound rewards were
  retuned.
- **KCD1's crafting** "cut for time"; whether KCD2's hunted deer give skins.
- **Skyrim's** per-hide tanning ratios (UESP's pages disagree).
- **WoW:** how Dragonflight decides a gathered hide's rank; the "3-rank gear was tested" claim
  for Midnight.
- **Green Hell's** hide drying; Valheim drop rates; whether Valheim's Weird Gloop wiki and
  Wurmpedia are official.
- **The OGL Section 15** notices of each non-core book (§1.6).
- **No sourced figure for:** casing moisture, grease content in curried leather, over-liming
  damage, raw hide thickness by species (sellers only), or skiving.
- **Not used:** a blog's fish-leather tear strength figure (unsourced), and the claim that no
  European leather torso armour predates the 11th century (a Patreon source).
