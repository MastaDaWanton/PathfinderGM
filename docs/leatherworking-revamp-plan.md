# Leatherworking revamp: the plan

Drafted 2026-10-05 from nine rounds of the owner's answers (`docs/leatherworking-questions.md`,
35 questions, all answered). The measurements it rests on are `docs/leatherworking-inventory.md`
(cited **Inv §n**) and the sweep is `docs/leatherworking-prior-art.md` (cited **PA §n**). The
interface half is `docs/leatherworking-ui-plan.md`; the lane shapes and file ownership are
`docs/leatherworking-contracts.md`. Nothing here is built. Numbers marked **(proposed)** are my
defaults and need tuning or a ruling; everything else is the owner's decision as given.

This plan mirrors `docs/blacksmithing-revamp-plan.md` and `docs/herbalism-revamp-plan.md`
wherever the cross-craft rulings already settle a question, and says so rather than repeating
them. It was written against local master 1f88ada, which has the forge revamp merged: the forge's
armour piece model (`rules/forge_items.py`), its crafted-item record, `rules/materials.py`,
`rules/knowledge.py` and the sheet's `armour_stats` are the things leather builds into.

---

## 1. What leatherworking is for

**The hunt made wearable** (Q1.1). The same three kinds of fun as herbalism and the forge:
hands-on craft, discovery, and a way to be seen through the world's own systems. What is
leatherworking's own is that **the beast you killed becomes what you wear**, and its hide
carries something of the creature into the item: a winter wolf's pelt keeps out the cold, an
eel's skin turns lightning, a dragon's hide will not burn.

That makes the harvest half of the craft, not a menu click (§5), and it makes the clock real: a
hide starts to rot the hour it comes off (§6), and good leather takes weeks (§8).

**It has to matter in play.** Today a studded leather suit made at the bench cannot be worn as
armour at all (Inv §0.1), and every armour-typed hide bonus is swallowed by the suit (Inv §0.2).
The engine half (§18) is not optional, exactly as it was not for the forge.

---

## 2. The owner's decisions (2026-10-05)

Every recommendation was accepted except where the owner gave **their own rule**, marked ★.

| Area | Decision |
|---|---|
| Purpose (Q1.1) | The hunt made wearable. |
| Armour model (Q1.2) | **One armour model**: the forge's body / fastenings / lining and its crafted-item record, read by `forge_items.build` and `Actor.armour_stats`. |
| ★ Who makes the mixed suits (Q1.3) | **"Leatherworking makes the base and the forge uses the base as an item and finishes it."** The leather or hide base is a finished leatherworker's item that the forge takes as an input and completes (studs, plates, metal fastenings) into studded leather, an armoured coat, lamellar and the like (§4). |
| Products (Q1.4) | Armour, shields, worn gear, grips, carried goods. No barding or tack until mounts exist. |
| Methods (Q2.1) | **Flense, Salt, Tan, Curry, Cut, Stitch, Harden, Tool, Dye, Assemble, Grade**; Line becomes a piece (the lining); Skin becomes the harvest action. Plus **Laminate** (Q2.4). |
| Tanning time (Q2.2) | **Real in-world time by tannage**; a tannery vat holds a hide while you adventure; never a real-time wait. |
| Intermediates (Q2.3) | **Each real stage lands on the shelf**, each sellable. |
| Concentration (Q2.4) | **Laminate**: two leathers of one material into one, every modifier ×1.5; each level after the first cuts the negatives by 10%. |
| Hide modifiers (Q3.1) | **3 armour modifiers on every hide; 3 weapon modifiers only on grip-capable hides**; ≥1 negative per list; house base ±2; the forge's tier ceilings. |
| Consumables (Q3.2) | **Working traits plus at most one small mark.** |
| Carried goods (Q3.3) | **A book rule where one exists, flavour otherwise.** |
| Masterwork (Q3.4) | **The book wins**: dragonhide, eel hide, angelskin and darkleaf cloth are always masterwork; everything else at Superior or better. |
| Skinning (Q4.1) | **One harvest per carcass on the book's numbers** (DC 15 + CR, Survival for hide), yield by size, grade from the harvest minigame. |
| How the beast died (Q4.2) | **No effect.** Grade from your skinning only; the beast sets the tier. |
| Which creatures (Q4.3) | **By the bestiary's type, subtype, size and CR, never by words in the name.** Named hides win; humanoids are never skinned. |
| Spoilage (Q4.4) | **Keep 48 hours, actually start it, and salt in the pack stops it.** |
| One carcass, four crafts (Q5.1) | **One "Harvest the carcass" action** listing every part for every craft the character has, each part taken once. |
| Sentient creatures (Q5.2) | **Allowed by the book, marked as a deed**: dragons and the book's named exceptions yes, humanoids never, a good outsider's harvest recorded for renown and alignment. |
| Yield (Q5.3) | **By size, the book's dragonhide ratio.** |
| Discovery (Q6.1) | **Grade, the leather assay**, plus working, teachers, libraries and manuals. |
| Levels (Q6.2) | **Field work, then the tannery, then legendary.** |
| Perks (Q6.3) | **The forge's four**, with Yield moved to the harvest. |
| Where (Q6.4) | **Field kit plus a tannery** (a town one you pay for, or one you found). |
| Worn leather (Q7.1) | **As the forge's armour record.** Proof of done: a studded leather suit made at the bench raises AC 15 → 16 on `pc-kesst`. |
| Dragonhide (Q7.2) | **Book first plus a house top-up.** |
| ★ Metal (Q7.3) | **"Armor and weapons both need a metal tag because there are spells that affect metal."** Both carry a metal tag from their pieces; the druid's no-metal rule is one reader of it; heat metal, chill metal, rusting grasp and shocking grasp are others (§18.5). |
| Grips (Q7.4) | **The leatherworker makes the haft piece** and the forge's Assemble takes it. |
| Bench (Q8.1) | **Its own bench**, from the herb bench's and the forge's parts. |
| Games (Q8.2) | **The grounded set**: flense, tan, harden, stitch, tool, cut, harvest. |
| Tuning (Q8.3) | **Generous, Steady mode, every band a number and a bar as well as a colour.** |
| Old tab (Q8.4) | **A "moved" card.** |
| Old saves (Q9.1) | **Convert.** |
| ★ World Bible (Q9.2) | **"Apply the tags to the beasts and just have a reader in skinning to find the relevant tag; no list is necessary."** Creatures carry harvest tags in the one tag vocabulary; no fauna list in the export (§5.3, §21). |
| ★ Pacing (Q9.3) | **Keep both** (the 48-hour clock and real tanning time), **and for all crafts an In progress section** where unfinished work sits with countdowns that move with game time until it is collected (§8.3). |
| Licensing (Q9.4) | **Mechanics now, names wait** for the bestiary licensing decision. |

**Cross-craft rulings assumed** (questions doc, "Assumed, not asked"): the d20 decides success
and one always-played minigame per method climbs the tier; levels 1 to 3 then endless levels
with two perk picks; real intermediates; discovery by assay, study, teachers, libraries and
manuals; materials as complete typed effect documents with ≥3 discoverable traits, book effects
winning with house top-ups; one material, many shelves; no model authors a number; fixes are
world-agnostic; old saves convert.

**Shared infrastructure built elsewhere.** The **In progress** section and the **metal tag** are
built first by the Enchanting lanes. This plan consumes both through named interfaces
(contracts §6) and specifies only its own readers of them: the tanning entries (§8.3) and the
druid and spell readers of the metal tag (§18.5).

---

## 3. What the research changes

From `docs/leatherworking-prior-art.md`, plus four rules checked for this plan (marked new):

- **Leather armour is Craft (armor) in the book** (PA §1.1). The book treats every suit as one
  kind of work, which is why one armour model is right. Who sits at which bench is a game rule.
- **Leather armour is boiled leather by definition** (PA §1.2, both Core and Ultimate Equipment).
  So Harden is part of making plain leather armour, not a late-game extra (§7).
- **Hide armour is "the tanned skin of particularly thick-hided beasts"** (PA §1.2). That is
  exactly what a monster hide should make, and it is the craft's AC 4 medium suit.
- **Dragonhide does not protect its wearer**; the suit is immune and later energy protection is
  25% cheaper (PA §1.3, confirmed verbatim in the critic pass). §15.
- **The harvest rule is the book's**: Ultimate Wilderness DC 15 + CR, Survival for hides, parts
  keep 24 hours; Monster Hunter's Handbook rots parts in 2 days; dragonhide's yield is one suit for
  a creature one size smaller (PA §1.4, §1.3). §5.
- **Grade from the player's hands, not the kill** (PA §0.7, §6: RDR2's clean-kill rule needs hit
  locations we do not have and punishes fire users). §5.7.
- **No 1% parts** (PA §6, Monster Hunter's decade-old backlash). Every part a creature carries is
  listed and taken by a roll the player sees, never a hidden drop table.
- **Waits survive in world time, not real time** (PA §0.6: The Long Dark and Vintage Story kept
  long cures; ESO's real-time research gate was cut in Update 49). The owner's In progress ruling
  is the readable form of this.
- **Hide grading is by defect area** (PA §3.1, the UNIDO draft standard: grades 1 to 4 and
  reject). That is the harvest game's scoring.
- **Cuir bouilli hardens by heat and water on vegetable-tanned leather; wax was a finish** (PA
  §3.5). The shipped Harden requires wax (`rules/leatherworker.py:916`): the one enforced input is
  the wrong one. §7.
- **Every crafting minigame in the sweep was softened after launch** (PA §6). Start generous.
- **New, the druid's rule** (Core, druid class, AoN): a druid may wear "padded, leather, or hide
  armor" and is "unable to cast druid spells or use any of her supernatural or spell-like class
  abilities while doing so and for 24 hours thereafter" in metal armour or with a non-wooden
  shield. The text does not mention dragonhide; dragonhide's own entry does (PA §1.3).
- **New, the metal spells** (AoN): *heat metal* and *chill metal* (druid 2) target "metal
  equipment of one creature per two levels"; a creature takes full damage "if its armor, shield,
  or weapon is affected", minimum damage otherwise; 7 rounds, 1d4 / 2d4 / 2d4 / 2d4 / 1d4 across
  rounds 2 to 6; Will negates (object) for magical metal, none for unattended nonmagical metal.
  *Rusting grasp* (druid 4) rusts "one nonmagical ferrous object"; on armour it "destroys 1d6
  points of AC gained from metal armor"; a metal weapon touched is destroyed; "magic items made of
  metal are immune". *Shocking grasp*: "+3 bonus on attack rolls if the opponent is wearing metal
  armor (or is carrying a metal weapon or is made of metal)". §18.5.
- **New, studded leather and metal: the book does not settle it.** Paizo's forums argue both
  ways and no FAQ was found (search 2026-10-05; the claim that the Game Mastery Guide lists it as
  metal armour could not be confirmed). Our piece model answers it mechanically: a suit is metal
  if any of its pieces is (§18.5), so steel studs make it metal and **bone studs** (the book's
  primitive bone material, allowed on studded leather) do not.
- **New, the armoured coat and lamellar** (AoN, Ultimate Equipment / APG): the armoured coat is
  "a sturdy leather coat ... reinforced with metal plates sewn into the lining" (+4, medium);
  lamellar comes as leather (+4 light), horn (+5 medium) and steel (+6 medium). §4.

---

## 4. The boundary with the forge

### 4.1 The owner's rule

**Leatherworking makes the base; the forge takes the base as an item and finishes it.** A suit
whose finished form needs no metal is the leatherworker's from hide to finish. A suit that needs
metal is begun by the leatherworker (the base) and finished by the forge, which adds the metal
pieces at its Assemble. The base is a real item: it is sold, carried, worn as what it already is,
and handed to the forge as one input.

### 4.2 Who makes which suit

Book statistics from PA §1.2 and the AoN tables checked for this plan. "Base" is what the
leatherworker hands over; "the forge adds" is the metal piece.

| Suit | Book row | Made by | Body | Fastenings | Lining | Notes |
|---|---|---|---|---|---|---|
| **Padded** | +1, light | leatherworker | quilted cloth or felt | lacing | none | Cloth, but no tailoring craft exists; kept here (Q1.4). |
| **Quilted cloth** | +1, light (APG, UE) | leatherworker | quilted cloth | lacing | padding | DR 3/— vs small ranged piercing (book). |
| **Leather** | +2, light | leatherworker | **hardened** leather (boiled, §3) | lacing or buckles | soft leather or fur | The base for studded leather and the armoured coat. |
| **Hide** | +4, medium | leatherworker | a **thick** tanned hide | lacing or rings | fur | Needs a hide with the `thick` working trait (§14.4). |
| **Leather lamellar** | +4, light (UE, UC) | leatherworker | hardened leather plates | lacing | soft leather | No metal in the book's row. |
| **Horn lamellar** | +5, medium (UE) | leatherworker | horn plates (harvested horn, §5.3) | lacing | soft leather | **(proposed)**: horn is a harvest part, so this is the hunter's suit. |
| **Bone-studded leather** | studded leather with the book's bone material: AC −1, ACP 1 better | leatherworker | hardened leather | **bone studs** | as leather | No metal, so the druid's studded leather (§18.5). |
| **Studded leather** | +3, light | **forge finishes** | the leather base's body | **metal studs** (forge fittings) | the base's lining | The forge's Assemble replaces the base's lacing with studs. |
| **Armoured coat** | +4, medium (APG, UE) | **forge finishes** | the leather base's body | the base's lacing | **metal plates** sewn into the lining | The book puts the metal in the lining, so the forge fills the lining slot. |
| **Steel lamellar** | +6, medium (UE) | **forge** | steel plates | the leatherworker's **lacing set** | soft leather | Steel is the most prevalent material, so the body is the forge's; the leatherworker supplies the lacing as a piece, as with grips (§4.4). See open point 1. |
| **Dragonhide hide armour** | hide, masterwork by nature | leatherworker | dragonhide | any | any | The book's default dragonhide suit (§15). |
| **Dragon-scale banded, half-plate, breastplate, full plate** | the metal suits' rows, for smaller wearers | **forge** | graded dragon scales (a leatherworker form) | the forge's | the forge's | The book's "best scales" ladder (§15). |

The madu (the book's leather shield, +1, UE) is the leatherworker's whole; it has a body and
fastenings (its grip). Wooden armour and wooden shields are woodworking and out of scope.

### 4.3 What a base is

A base is an ordinary leatherworker crafted record (§13.1) with `"base_for": [<forge suits>]`.
The leather base for studded leather **is** a suit of leather armour: it can be worn as leather
armour until the forge finishes it. The forge's finishing Assemble:
1. takes the base record as one input (consumed), keeping its `pieces` and its maker's record
   under `from_base` for provenance;
2. fills the slot the finish names with its own piece (studs into `fastenings`, plates into
   `lining`), and changes `base` to the finished suit (`studded leather`, `armored coat`);
3. sets the finished item's quality to **the lower of the base's tier and the forge's Assemble
   tier (proposed)**, so neither craft can lift the other's work; masterwork follows §13.4.

A town smith can do the finishing for a fee when the character has no Blacksmith levels **(proposed,
through the forge's keeper and `market.forge_rent`)**. That is "a cross-craft trade of pieces in
stock" (Q7.4) at its smallest.

### 4.4 Grips and lacing: pieces the other way

The leatherworker makes **pieces the forge assembles**:
- **Grips**: a `grip` form of a grip-capable hide (§14.3), which fills the forge's `haft` slot
  (the forge already lets `leather-grip` do so). Wrapped over the haft at the forge's Assemble.
- **Lacing sets**: a `lacing` form, which fills `fastenings` (steel lamellar; any forge armour
  laced rather than riveted).

The forge catalogue's four leather pieces become **forms of leatherworker materials** (one
material, many shelves, Q7.4): `leather-grip` → a form of plain leather, `sharkskin-grip` → of
`sharkskin` (new hide document, grip-capable), `dragonhide-grip` → of `red-dragonhide` (the link
already exists, Inv §2), `angelskin-binding` → of `angelskin` (moved and fixed to the book, §14.5).

### 4.5 What the forge must accept

Measured in code (contracts §9): the forge's rack offers only stock whose `craft` is blacksmith
(`rules/blacksmith.py:1767-1814`), and its Assemble refuses any finished item as a piece
(`fit_reason`, `:1983-1995`); a crafted item is accepted only by Finish. The hand-off therefore
needs three forge changes, owned by lane H here (contracts §11):
1. the rack lists leatherworker stock with a `fills` that the forge can use (grips, lacing,
   bases, dragon scales);
2. Assemble accepts a **base** as its main input for the shapes in its `base_for`, and a grip or
   lacing set in the slot it fills;
3. `FORGED_ARMOUR` gains the finished leather suits (studded leather, armored coat, steel
   lamellar) as shapes reachable **only** from a base.

---

## 5. Harvest the carcass

### 5.1 One action across crafts

Today four crafts each run a repeatable excursion over the same body, matching the creature's
display name, with a d20 whose margin multiplies the haul (Inv §0.3, §4). They are replaced by
**one scene action**, `harvest`, an engine op:

- It lists **every part the carcass carries for every craft the character has** (Leatherworker,
  Blacksmith, Alchemist, Enchanter, and the Herbalist's monster parts), grouped by craft.
- **Each part can be taken once.** The carcass record keeps `harvested: {part_key: minute}`;
  a taken part never reappears.
- **The check for each part is made by the craft that wants it**, on the book's skill (§5.2).
- It is offered only while the carcass is **harvestable** (§5.9) and never for a humanoid.
- Every part taken emits a tell ("you peel the winter wolf's pelt away whole"); the narrator is
  told nothing else about the harvest (law 3).

The four excursions (`skin`, `harvest`, `harvest-reagents`, `reliquary-harvest`) leave the
acquisition hub; their non-carcass siblings (buy, gather, mine, prospect) stay as they are.

### 5.2 The book's numbers

| Part | Check | DC | Time | Source |
|---|---|---|---|---|
| Hide, scales, horn, fangs, sinew, bone (external) | **Survival** | 15 + CR | 10 minutes per hide unit, at most 1 hour **(proposed)** | Ultimate Wilderness, "Trophies and Treasures" (PA §1.4) |
| Glands, organs, blood (internal) | **Heal** | 15 + CR | 10 minutes | the same |

- **CR** is the stat block's `cr_value`. Template and class CR do not count, as the Harvest Parts
  feat says (PA §1.4); a templated creature uses its base block's CR.
- **The craft's level does not add to the roll (proposed).** The book's skill is the book's
  skill. A leatherworker's edge is in the grade (§5.7), the Yield perk (§17.2) and knowing which
  parts are worth taking; a skinning kit gives +2 circumstance as masterwork tools do (PA §1.4:
  taxidermy tools +2, Core: masterwork tools +2).
- Identification (the book's first step, Knowledge by type) is not a separate roll: parts the
  character cannot yet name show as "an unknown part" until Graded or assayed (§16), which is the
  discovery half of every craft already.

### 5.3 Tags on the beast, a reader in the harvest (the owner's rule)

**Creatures carry harvest tags in the one tag vocabulary; the reader finds them. There is no
fauna list** (Q9.2 ★). The bestiary already supports this: a stat block's own `tags` are read
live into the creature's standing tags (`rules/sheet.py:3421-3424`, where `role.guard` lives), and
`has_state` asks prefix questions of them (`rules/states.py:473`).

**The grammar** (each craft owns its branch under `harvest.`):

| Tag | Means | Owner |
|---|---|---|
| `harvest.hide.<material-id>` | this beast yields that named hide | leather |
| `harvest.hide.generic.<surface>` | a generic hide of this surface: `fur`, `scale`, `smooth`, `feather`, `chitin`, `shell` | leather |
| `harvest.horn.<material-id>`, `harvest.bone.<material-id>`, `harvest.sinew` | external parts the leatherworker takes | leather |
| `harvest.scales.<material-id>` | the best scales, for the forge's dragon-scale suits (§15) | leather (the forge consumes) |
| `harvest.blood.<material-id>` | quench bloods (dragon blood, troll blood) | forge |
| `harvest.reagent.<ingredient-id>` | alchemical parts | alchemy |
| `harvest.essence.<material-id>` | ichors, catalysts | enchanting |
| `harvest.part.<ingredient-id>` | the herbalist's monster parts | herbalism |
| `harvest.plan.<plan>` | the body plan the 3D hide is drawn from: `quadruped`, `long`, `winged`, `serpent`, `carapace` | leather (UI only) |

**The reader** (`harvest.parts(creature, actor)`) returns one row per tag whose craft the
character has: the material, the skill and DC (§5.2), the yield (§5.5), the time, and whether
taking it is a deed (§5.6). It reads **only tags and stat-block fields** (type, subtype, size,
CR, resistances, immunities, reductions). It never reads the creature's name.

**Where the tags come from.**
- **Shipped bestiary** (782 + 6,406 + 5 blocks in `core.json`, `creatures.json` and
  `mounts.json`; the inventory measured 7,138 creatures through the bestiary module; none carries
  a harvest tag today): a one-time data pass writes the tags into the stat blocks, reviewed as a table
  by the owner (the forge's review pattern). Named hides are mapped **by the creature's id, by
  hand**, never by name fragment: the 65 shipped hides each get the creatures they come from
  (the winter wolf block gets `harvest.hide.winter-wolf-pelt`; every true dragon block gets only
  its own colour's dragonhide).
- **Generic hides by rule** for the rest, the Q4.3 rule written once as the pass's code and kept
  as the reader's fallback for untagged blocks (so an old world's beast still yields): animals
  and magical beasts give `harvest.hide.generic.fur` unless the block's subtype or tags say
  otherwise; vermin give `chitin`; dragons give `scale`. Monstrous humanoids, aberrations, fey,
  outsiders, plants, oozes, undead and constructs give **nothing** unless tagged by hand.
- **World Bible creatures** carry the same tags on their rows (§21).

**Validators** (the pass and every load): a `harvest.hide*` tag on a `type.humanoid` block is
refused with the fix named ("humanoids are never skinned: remove the tag"); a tag naming a
material that does not exist is refused; a true dragon tagged with a dragonhide of another colour
is refused (the measured red-dragon-offers-11-colours defect, Inv §0.4).

### 5.4 Generic hides from the stat block

A generic hide is one material document per surface (`generic-fur-hide`, `generic-scale-hide`,
`generic-smooth-hide`, `generic-feather-hide`, `generic-chitin`, `generic-shell`), each with its
own ≥3 armour modifiers like any hide (§14). What makes a particular beast's generic hide its own
is read from **its** stat block at build time, never authored by a model and never stored as a
number (the read-live rule: the stock record keeps the creature's id):

| From the stat block | Becomes **(proposed)** |
|---|---|
| CR | the hide's **tier**: CR 0–2 common, 3–5 uncommon, 6–9 rare, 10–14 exotic, 15+ legendary |
| Size | its hide units (§5.5) |
| Energy resistance or immunity (`resist`, `immune`) | one house `resistance <energy>`: resistance ÷ 5, at least 1, immunity counts as the tier ceiling; capped by the tier ceiling (materials `TIER_CEILING`); only the **highest** energy is inherited |
| Natural armour (`ac_note` "+N natural", parsed by `bestiary.ac_parts`) | N ≥ 5 gives the `thick` working trait (it can make hide armour) |
| DR (`reductions`) | nothing in this pass; see open point 6 |

The inherited resistance counts as one of the hide's house modifiers for the 3-modifier rule and
the tier ceiling; it is shown on the ledger card as "from the creature: fire resistance 2".

### 5.5 Yield by size

The book's only printed yield is dragonhide's: one dragon gives one suit for a creature one size
smaller (PA §1.3). Measured in **hide units** (one Medium hide = 1 unit), doubling per size
**(proposed)**:

| Creature size | Hide units | Weight green, lb (UW Table 4-10 doubled, averaged) |
|---|---|---|
| Fine, Diminutive | 0 (scraps only: sinew, no hide) | – |
| Tiny | 0.25 | 3 |
| Small | 0.5 | 4 |
| Medium | 1 | 7 |
| Large | 2 | 21 |
| Huge | 4 | 70 |
| Gargantuan | 8 | 210 |
| Colossal | 16 | 700 |

| Product | Units needed **(proposed)** |
|---|---|
| Suit body for a Medium wearer | 2 (one Large hide, or two Medium; Q5.3) |
| Suit body for Small / Large wearer | 1 / 4 |
| Fur lining for a Medium suit, a cloak | 1 |
| Madu shield | 1 |
| Boots, satchel, quiver | 0.5 |
| Gloves, bracers, belt, cap, sheath, grip, lacing set | 0.25 |

So a Large dragon (2 units) gives one Medium suit, a Huge one a Large suit: the book's ratio. The
book's extra "a Large or larger dragon also gives enough for a shield" is one more unit on true
dragons of Large size and up. Units are stored in quarters; hides of one material and grade
combine at Cut.

### 5.6 Sentient creatures and deeds

- **Humanoids are never harvested** (Q5.2). The action is never offered on a `type.humanoid`
  carcass, and the validator refuses the tag (§5.3).
- **Dragons and the book's named exceptions can be** (dragonhide, angelskin). A named exception is
  simply a tag on the block; there is no list.
- **Harvesting a good outsider is a deed.** A creature with `type.outsider` and `subtype.good`
  makes the harvest of any part from it a **deed** with the tag `deed.harvest.good-outsider`.
  The confirm shows before the roll (UI plan §6.9).
- **What a deed is.** No renown or alignment system exists yet (measured: deeds today are only
  world-class milestones, `rules/worldclass.py:151`; "renown" appears only as a bluff claim kind).
  Herbalism's plan §12 already promised deeds for a separate renown system and none was built. So
  this plan defines the **smallest store the future systems can read** (contracts §5.4): an
  append-only `Actor.deeds` list of `{tag, minute, place, subject, witnesses}`, with the witnesses
  taken from the scene's seen people. The app does not rule on morality; it records what was done
  and who saw it.

### 5.7 Grade from the harvest game

On a successful check, the **harvest game** (UI plan §9: cut along the line, avoiding holes) sets
the hide's **grade**, scored against the UNIDO defect areas (PA §3.1):

| Grade | Defect area | Caps the quality of work from this hide at **(proposed)** |
|---|---|---|
| 1 | clean | no cap (your level's ceiling) |
| 2 | a few small holes or cuts | Superior |
| 3 | up to 30% | Fine |
| 4 | up to 50% | Sound |
| Reject | worse | scraps only: sinew and glue, no leather |

That is Wurm Online's rule (the hide's quality caps the product's, PA §2) on the real standard.
The beast sets the tier (Q4.2); the grade is the only thing the player's hands decide here. How the
beast died does not matter (Q4.2: no fire or acid penalty).

The grade is a property of the hide stock, travels through every intermediate (the lower grade
wins when two hides are laminated or cut together), and is the cap the work order shows on the
ladder (UI plan §6.5).

### 5.8 Failure

The book does not say what a failed harvest does (PA §1.4). Mirroring the Craft rule
**(proposed)**:
- **Fail by 4 or less:** the part comes off, one grade worse than the game would have given (never
  better than Grade 3). The time is spent.
- **Fail by 5 or more:** the part is ruined (marked taken, nothing gained); for a multi-unit hide,
  half the units are ruined, rounded down, the rest at Grade 4.

No retry: the part is taken either way. That is what closes the measured "six skinnings of one
wolf" door (Inv §0.3).

### 5.9 How long a carcass waits

The hide's own clock starts at the harvest (§6). The carcass also needs a window, or a party could
skin a week-old corpse. The books disagree: the Monster Hunter's Handbook says under an hour,
Ultimate Wilderness sets no limit (PA §1.4, critic correction). **(Proposed:)** a carcass is
harvestable for **24 hours after death**, Ultimate Wilderness's own keeping figure applied to the
body, recorded as `died_at` on the scene actor when it drops. Open point 5.

---

## 6. The clock: spoilage and salt

- **48 hours from the harvest** (Q4.4), the number today's tests pin (`FRESH_HOURS`,
  `rules/leatherworker.py:74`, equal to the herbalist's animal clock, `rules/herbprep.py:33`).
- **It actually starts.** The harvest writes the hide as stock with `harvested_at` (the minute).
  Today `craft_excursion` calls `pc.carry(mid, n)` with no `at_minute`, so no clock ever starts
  (Inv §0.3, `play/craft_views.py:1402`).
- **Salt in the pack stops it** (herbalism's rule, `herbprep.preserve_automatically`): a hide
  harvested while the character carries curing salt is salted on the spot. **Unlike herbalism it
  costs salt (proposed)**: one measure of curing salt per hide unit, spent at the harvest, because
  real curing takes salt at 25% of green weight up to 1:1 (PA §3.1) and "carrying salt becomes a
  real decision" (Q4.4). Without enough salt, the remaining units stay green.
- **The Salt method** (§7) salts a green hide later, before it spoils, with its own small game.
- **A salted hide keeps 6 weeks (proposed**, FAO: about 15% salt keeps a hide six weeks, PA §3.1),
  then needs salting again. A tanned leather never spoils.
- **A spoiled hide** becomes scraps (glue stock), never silently deleted.

**One salt reader.** `herbprep.has_salt` matches name fragments over carried goods
(`rules/herbprep.py:136`), which is the shape the three laws refuse. This plan's harvest reads
salt by **material id and kind** (`curing-salt` and anything whose material document says
`"salt": true`), and the herbalism reader is moved onto the same function (grep every copy).

---

## 7. Methods

| Method | In | Out | Level | Where | Notes |
|---|---|---|---|---|---|
| **Flense** | green or salted hide | **pelt** (flesh and fat off; hair on for furs, off for leather) | 1 | kit; **thick** hides need a tannery's lime pit | Liming and dehairing fold in here (Q2.1). Liming a thick hide is a 3-day pit **(proposed)**, registered in In progress (§8.3). |
| **Salt** | green hide + curing salt (1 per unit) | salted hide | 1 | kit | The field cure. Stops the clock for 6 weeks. |
| **Tan** | pelt + tannin | **leather** or **fur** (hair on), with its tannage; or **rawhide** (no tannin, stretched and dried) | 1 brain and smoke; 2 bark, alum, mineral; 3 planar | brain at the kit; alum at the kit; bark, mineral and planar in a tannery vat | Real world time by tannage (§8). The tannin must be within one tier of the hide (today's rule, the one that works, Inv §1). |
| **Curry** | leather + an oil (+ tallow) | curried leather | 2 | kit | Oil folds in here (Q2.1). Applies the oil's mark. Required for Superior and up on soft goods **(proposed**: the forge's "Hone for Superior on edged weapons"). |
| **Cut** | leather, fur or rawhide | panels for a pattern, a lacing set, or a grip strip | 1 | kit | The pattern is picked from the engine's list of products (§13), never typed. Combines hides of one material and grade into the units the pattern needs. |
| **Stitch** | panels + thread | a stitched body (soft goods, padded, linings) | 1 | kit | The thread's working traits and mark apply. |
| **Harden** | **vegetable- or planar-tanned** panels | hardened plates (cuir bouilli) | 2 | **tannery** (the hardening kettle, Q6.4) | **No wax required** (the fix, PA §3.5). Raw, alum and brain leather are refused with the reason ("alum leather softens in water: it will not harden"). |
| **Tool** | leather or a hardened piece (+ a wax to fill the tooling, optional) | tooled piece | 2 | kit | Stamping and carving. Applies the wax's mark when one is used. Required for Flawless **(proposed)**. |
| **Dye** | a piece + a dye (+ mordant salts for a fast colour) | dyed piece | 2 | kit | Applies the dye's mark. Mordant salts now do something: without them the dye's mark is lost the first time the item is soaked **(proposed)**. |
| **Laminate** | 2 leathers of one material | 1 laminated leather, ×1.5 | 2 | kit | The concentration (§12). Repeatable. |
| **Assemble** | body + fastenings + lining | the finished item or a **base** | 1 | kit | Where pieces join and the item's numbers are computed by `forge_items.build` (§13). |
| **Grade** | a scrap | knowledge | 1 | kit | The leather assay (§16). No quality, no minigame. |

**Removed:** Skin (now the harvest, §5), Cure (now Salt, which really takes salt), Oil (into
Curry), Line (now the lining piece at Assemble: measured to do nothing today, Inv §1).

**DCs.**
- **Assemble**: the book's Craft DCs. A suit or shield is **10 + its AC bonus** (Core Craft table,
  PA §1.1); worn and carried goods a "typical item", **DC 10**; a grip **DC 12** (as a simple
  weapon's part, **proposed**).
- **Masterwork**: aiming for Superior adds the book's masterwork component, **DC 20**, unless the
  main material is `flawless` (Unchained) or always masterwork (§13.4). The forge's rule
  (`masterwork_dc`, `blacksmith.json`).
- **Intermediate steps**: the material's DC (an authored `craft_dc`, else 5 + 5 × tier rank), as
  the forge. **No +2 per stage** (the creep the forge plan removed; Inv §1 measured DC 38 for a red
  dragonhide suit).
- **Check**: d20 + Leatherworker level + half character level + Int, as today (`check_terms`,
  `rules/leatherworker.py:502`). A masterwork kit roll adds +2 circumstance (§13.6).

**Order rules**: Flense before any Tan; Tan before Curry, Harden, Tool, Dye; Harden only on
vegetable or planar tannage; Cut before Stitch; Assemble last. Each refusal names the step that is
missing, in words.

**World time per step (proposed)**: Flense 40 min per unit; Salt 10 min per unit; Tan setup 1 h
(then the wait, §8); brain tanning 8 h per unit of bench work; Curry 1 h; Cut 30 min; Stitch 1 h
per unit of body; Harden 30 min; Tool 2 h; Dye 1 h; Laminate 2 h; Assemble 1 h for a suit, 30 min
otherwise; Grade 10 min. All in the rule rows (`content/world-classes/leatherworker.json`
`bench`), as the forge keeps its in `blacksmith.json`.

---

## 8. Tanning in game time

### 8.1 The tannages

| Tannage | Tannins (shipped ids) | Level | Where | Time **(proposed)** | Character (PA §3.3) |
|---|---|---|---|---|---|
| **Brain and smoke** | `brain-paste` | 1 | kit | about a day of work: 8 h of bench time per unit, no wait | soft; smoke makes it water-resistant; **will not harden** |
| **Rawhide (proposed)** | none | 1 | kit | 1 day of drying, in progress | stiff, untanned; grips (shagreen, PA §3.8) and lacing |
| **Alum (tawing)** | `tawing-alum` | 2 | kit | 3 days soak then 3 weeks ageing, compressed to **1 week** | white, stretchy; **reverts in water**; will not harden |
| **Bark (vegetable)** | `oak-bark`, `sumac-leaf`, `hemlock-bark`, `willow-bark`, `tara-pod`, `mangrove-bark`, `bog-liquor`, `ironbark-tannin` | 2 | **tannery vat** | **4 weeks**, **8 weeks** for a thick hide (compressed from the book's 12 months, PA §3.3) | firm; the only tannage that hardens and tools well |
| **Mineral** | `salamander-ash-lye` | 2 (exotic tannin) | tannery vat | 3 days | boil-fast; a high heat tolerance |
| **Planar** | `styx-mordant`, `dragonblood-tannin`, `wyrm-gall` | 3 | tannery vat | 6 weeks | as bark, plus the tannin's mark |

**Each tannin carries working traits** (Q3.2) that set the time and the ceiling:
`fast_tan` (time ×0.5: hemlock, the shipped prose's "halves tanning time" made real),
`slow_tan` (×1.5), `ceiling_up` (+1 quality ceiling: tara, ironbark), `ceiling_down` (−1: willow),
`salt_proof` (a salted hide needs no desalting soak: mangrove, the shipped "salt-proof"),
`tans_white` (dye takes true colour: sumac). Plus the **shrinkage temperature** as a stat of the
tannage, not a game (PA §3.9): alum 55–60 °C, bark 75–85 °C, mineral 100+ °C. It is what decides
whether a leather can Harden, and it gives a fire-trait a grounded reason.

### 8.2 Vats and the hide that travels

- **A tannery vat** holds up to **4 hide units (proposed)** of one tannage. A town tannery rents
  vats by the day (**2 sp a day per vat, proposed**); an owned tannery's vats are free. The hide
  stays in the vat while the character goes anywhere; it is collected there.
- **Carried tannages** (rawhide drying, alum in a sealed skin bag) travel with the character like
  herbalism's steeping jar: an object in the pack under the gear and load rules.
- A vat tannage cannot be carried; a bark tannage started at a tannery is fetched from it.

### 8.3 In progress (consumed interface)

Every tannage, liming pit and drying rawhide is **registered in the shared In progress section**
(Q9.3 ★) through the Enchanting lanes' interface (contracts §6.1): one entry per batch with the
craft, a label ("Elk hide in oak bark"), the stock it will become, the **ready minute**, **where**
it waits (carried, or a place id), and the action that collects it. The countdown moves with the
game clock; real time never matters.

**Collecting** a bark or planar tannage plays the **cut test**, the second half of the Tan game
(UI plan §9): the tier comes from both halves (the strength steps at setup and the cut test at
collection). Collecting early is refused with the minutes left ("not struck through: 9 days
more"). Collecting late costs nothing: leather does not over-tan in this game **(proposed)**.

This replaces today's instant tanning (Inv §0.5). It is the "steeping clock herbalism already has"
(`crafting.settle_steeping`, `rules/crafting.py:1861`) generalised; the generalisation is the
Enchanting lanes' work, not this plan's.

---

## 9. Intermediates and forms

Each real stage lands on the shelf as stock and is sellable (Q2.3). All are **forms** of one
material (one material, many shelves): the winter wolf's pelt, leather, panels and lacing are one
document's forms, so learning the hide teaches every form.

| Form | From | Clock | Sold at **(proposed)** |
|---|---|---|---|
| green hide | the harvest | 48 h | 25% of the leather price; "cannot be bought or sold in most settlements" (Harvest Parts, PA §1.4) applies to the green hide only |
| salted hide | Salt | 6 weeks | 40% |
| pelt | Flense | 48 h unless salted first | 50% |
| leather / fur / rawhide | Tan | none | 100% (the material's `price_gp`) |
| panels, lacing, grip strip | Cut | none | 110% |
| hardened plates | Harden | none | 130% |
| base | Assemble | none | the suit's book price |
| finished item | Assemble | none | §13.5 |

**The stock record** for any of these (contracts §4.1): material id, form, hide units, grade,
tannage, passes (laminations), marks, `harvested_at`, `salted`, the creature's id (for generic
hides, §5.4), and the quality word of the last step. Ids and passes only; every number is computed
on read.

This fixes the measured "every piece is flense-to-finish in one session" (Inv §0.5): a tanned hide
now survives the session as stock, not as a bare count in the satchel.

---

## 10. Where you work

**The field kit** (skinning knife, fleshing beam, round knife, awl and needles, mallet, a small
pot): Flense (thin hides), Salt, brain tanning, rawhide, alum, Curry, Cut, Stitch, Tool, Dye,
Laminate, Assemble, Grade, for common and uncommon hides, anywhere (Q6.4). Q6.4 names Salt,
Flense, brain tanning, Cut, Stitch, Assemble and Grade for the kit; placing **Curry, Tool, Dye,
Laminate, alum tawing and rawhide** at the kit too is **(proposed)**: none of them needs a vat, a
lime pit or a kettle.

**A tannery** adds the lime pit (Flense for thick hides), the **vats** (bark, mineral and planar
tannages), the **hardening kettle** (Harden), and **rare-and-above hides** (Q6.4):
- **A town tannery**: the settlement place row already exists (`rules/places.py:131`, town, trade)
  with a keeper (`:310`). It needs what the smithy has (`smithy_here`, `:2042`): a keeper whose
  occupation carries the `leather` tag (the tanner row, `content/people/occupations.json:225`, is
  tagged `["leather", "animals"]` already), a work rate (**1 sp an hour, proposed**, the forge's)
  and vat rent (§8.2). Real tanneries were kept out of town for the smell (PA §3.7), so a tannery
  sits on the settlement's outskirts **(proposed**, `rules/outskirts.py`), and is rarer than a
  smithy: towns and cities get one only when their own words imply it (the forge's cue-row pattern,
  open point 9).
- **Your own tannery**: founded through the places system's `found` door with the
  `place.tannery` tag; the owner holds `holds.place.<slug>`. This retires the "fixed tools
  deliberately unread" note (Inv §1), as the forge retired it for smithies.

Which you are at is read from the scene's place and its tags, never from the player's words.

**Harden at the tannery means plain leather armour waits for one** (book leather armour is boiled,
§3). A level-1 leatherworker in the field makes padded and quilted suits, hide armour from a thin
enough hide (§14.4), worn goods, grips and lacing. That is what Q6.2 and Q6.4 together say; open
point 3 asks the owner to confirm the consequence.

---

## 11. The bench, rules side

Same as the forge §11 and herbalism §9:
- The d20 Craft roll decides success; the minigame climbs the tier under the **step ceiling**: the
  lowest of your level's ceiling, the hide's grade cap (§5.7), the tannin's ceiling trait, and
  (at Assemble) one above the body piece's own tier, the forge's rule (`rules/blacksmith.py:2616`).
- **Always played.** Salt, Flense, Tan and Cut batch (one roll and one game for hides of one
  material, grade and tannage; world time grows with the batch). **No bulk at Assemble** (the
  forge's ruling).
- **Fail by 4 or less**: time lost, materials kept. **Fail by 5 or more**: half the materials
  ruined (rounded down, at least 1 when there were 2+), unless the material is `malleable`. This
  fixes "every input spent on any failure" (Inv §1, `play/craft_views.py:656`).
- **A minigame miss after a successful roll never takes materials.** Only the d20 does.
- **A natural 20 is not an automatic success** on a bench check (herbalism plan §5.3, the CRB's
  skill rule).
- The server receives a score in 0..1 and answers with the tier; the page never computes a number.

---

## 12. Laminate

The forge's Strengthen, on grounded practice (doubled leather was a real armour build, Q2.4):
- **Two leathers of one material** (same material id, both tanned, the same tannage) are glued and
  stitched into one heavy leather. It records `passes + 1` on the piece, exactly the forge record's
  field, so `forge_items.build` scales it by **×1.5 per pass**, bonuses and negatives alike.
- **The negative cut** is the forge's: each Leatherworker level after the first cuts the negatives
  by 10%, multiplied with Hardening perks, **floored at 50%** (`forge_items.negative_cut`).
- **The lower grade** of the two wins. Units: two pieces of N units make one of N units.
- **Repeatable.** The 2ⁿ hide cost is the brake, as the forge's bar cost is.
- Only leather (not fur, not hardened plates) can be laminated; hardened plates are laminated
  before hardening.

---

## 13. Products and the item maths

### 13.1 The record

Every leatherworker product is **the forge's crafted-item record** (forge contracts §4) with
`craft: "leatherworker"`:

```json
{
  "id": "fine-elk-hide-armour", "name": "Fine Elk Hide Armour",
  "kind": "crafted", "craft": "leatherworker", "count": 1,
  "gear": "armour", "base": "hide armour", "slot": "armor",
  "quality": "fine", "quality_index": 2, "masterwork": false,
  "pieces": {
    "body":       {"material": "elk-hide", "passes": 1, "grade": 2, "tannage": "oak-bark"},
    "fastenings": {"material": "deer-hide", "form": "lacing", "passes": 0, "grade": 1},
    "lining":     {"material": "plain"}
  },
  "marks": ["neatsfoot-oil"], "flaws": [],
  "base_for": [],
  "smith": {"level": 2, "perks": {"potency": 0, "hardening": 0}},
  "schema": 3
}
```

- `base` is **always a table key** (`leather`, `hide armour`, `padded`...), never the item's
  name. That is the measured wear defect (Inv §0.1: `crafting.from_stock_dict` copies the name
  into `base`, `rules/crafting.py:386`, and the engine reads `base` first).
- `marks` lists the consumables whose one mark the item carries (§14.6).
- `smith` keeps the forge's key so `forge_items.build` reads the maker's level and perks unchanged
  (contracts §4.2 records the alias `maker` for later).
- Worn goods use `gear: "worn"` (new, §18.2) with `body` and `lining`; grips use the forge's
  `haft` piece and are not records of their own until fitted.

### 13.2 The suits

`tables.ARMOUR` gains the missing rows (PA §5.1, AoN): **quilted cloth**, **leather lamellar**,
**horn lamellar**, **armored coat**, **steel lamellar**; `tables.SHIELDS` gains the **madu**
(leather). The hide armour key stays `hide armour` (`rules/tables.py:549`), and `armour._ALIASES`
gains `hide` so a `when.armour.weight` clause on a hide suit is not dropped (measured: a bare
"hide" resolves to nothing today).

### 13.3 The item maths: the forge's, unchanged

`forge_items.build` (forge plan §6.2): main piece ×1, the others ×0.5; ×1.5 per pass (Laminate);
bonuses × quality × (1 + potency); negatives × the cut; summed per target, then rounded toward zero.
Material AC folds into the **armour bonus** (`_folds_into_armour`, `rules/forge_items.py:484`), so
it is no longer swallowed (Inv §0.2). Book effects come from the main piece only, unscaled. Marks
are applied once, unscaled, like the quench mark.

**Worked example.** A Fine hide armour (quality ×1.25), Leatherworker 2 (negatives ×0.9). Body:
elk hide, laminated once. Fastenings: deer-hide lacing. Lining: none. Elk's armour list
**(proposed)**: AC +2, ACP −2, Survival +2. Deer's: ACP +2, max Dex +2, hardness −2.

| Target | Elk body (×1, ×1.5) | Deer lacing (×0.5) | Bonus / negative | After quality ×1.25 and cut ×0.9 | Final | On hide armour |
|---|---|---|---|---|---|---|
| AC | +2 × 1.5 = +3 | 0 | +3 / 0 | +3.75 | **+3** | 4 → **7** |
| ACP | −2 × 1.5 = −3 | +2 × 0.5 = +1 | +1 / −3 | +1.25 − 2.7 = −1.45 | **−1** | −3 → **−4** |
| Survival | +2 × 1.5 = +3 | 0 | +3 / 0 | +3.75 | **+3** | |
| max Dex | 0 | +2 × 0.5 = +1 | +1 / 0 | +1.25 | **+1** | 4 → **5** |
| hardness | 0 | −2 × 0.5 = −1 | 0 / −1 | −0.9 | **0** | |

The last row shows the forge's rounding toward zero at work. The build card shows exactly this.

**The proof of done** (Q7.1): `pc-kesst` (rogue, Dex 17, wearing table `leather`) has AC 15. A
leather base made at the leather bench from a hide with no AC modifier, finished at the forge with
plain studs, and worn, gives AC **16** (studded leather's +3 against leather's +2, max Dex 5 still
above Dex +3). With any other hide, the rise is exactly what the build card's AC line says.

### 13.4 Masterwork, by the book

- **Always masterwork** (Q3.4): a suit or shield whose **main piece** is dragonhide, eel hide,
  angelskin or darkleaf cloth is masterwork at any tier (book, PA §1.3), and no DC 20 is added.
  The material document says `"always_masterwork": true` with `"book": true`, and
  `forge_items.build` reads it (contracts §4.2).
- **Everything else** is masterwork at **Superior or better**, as at the forge, and Superior at
  Assemble needs a **masterwork-ready body**: curried (soft goods) or hardened (leather and
  lamellar suits), the leather counterpart of the forge's tempered and honed head.
- Masterwork on armour is the book's −1 ACP (`rule:masterwork`), never scaled.
- This fixes the measured "dragonhide suit is not masterwork without Tool" (Inv §0.7) and "Tool is
  the only road to masterwork".

### 13.5 Prices

The book's suit price plus the material's (eel hide +1,200 gp light / +1,800 gp medium; angelskin
+1,000 / +2,000; darkleaf +750 / +1,500; dragonhide double the masterwork price but double the
Craft results, so no slower), then the quality ladder the forge and herbalism use. Sale price by
`rules/pricing.py`.

### 13.6 Worn and carried goods

Worn goods (cloak, boots, gloves, bracers, belt, cap) carry the hide's modifiers **that mean
something off a suit** (§18.2): skills, saves, resistances. AC, ACP, max Dex and spell failure
are dropped from them (there is no armour bonus to fold into).

Carried goods take a **book rule where one exists, flavour otherwise** (Q3.3):

| Good | Book rule | Hook |
|---|---|---|
| **Kit roll** (the field kit itself) at Superior | masterwork tools: +2 circumstance on the related skill (Core, UE p.77) | +2 on Leatherworker bench checks and on the harvest's Survival (§5.2) |
| **Backpack** at Superior | masterwork backpack: Strength +1 for carrying capacity (Ultimate Equipment, legacy PRD adventuring gear) | the load rules in `rules/gear.py` |
| **Spell component pouch**, **belt pouch** | none beyond the item | flavour; sale value |
| **Satchel** "waterproof" | none in the book | flavour until a system soaks gear |
| **Sheath, quiver, scabbard** | none | flavour; a lead-lined scabbard is the forge's (viridium) |

---

## 14. The hide materials pass

### 14.1 Today (Inv §2)

127 materials: hide 65, tannin 12, dye 12, thread 11, oil 8, fitting 8, treatment 6, wax 5. 96 of
171 effect specs are `narrative`; no material has three traits of any kind; no hide carries a
drawback in executable form. `materials.is_forge` is false for every one, so the validator never
judges them (`rules/materials.py:405`), and hides normalise to empty `armour` lists, so a hide in
a body slot would contribute nothing (measured in code, contracts §9).

### 14.2 The hide document

The forge's document shape (forge contracts §3), with leather's fields:

```json
{
  "id": "winter-wolf-pelt", "name": "Winter Wolf Pelt", "kind": "hide", "tier": "uncommon",
  "form": "hide",
  "pieces": {"armour": ["body", "lining"], "shield": ["body"], "worn": ["body", "lining"]},
  "armour": [
    {"type": "resistance", "target": "cold", "amount": 2},
    {"type": "skill_mod", "target": "stealth", "amount": 2, "bonus_type": "material",
     "when": {"terrain": "snow"}},
    {"type": "gear_mod", "target": "acp", "amount": -2}
  ],
  "weapon": [],
  "working": [{"type": "working", "trait": "forgiving"}],
  "surface": "fur", "color": "#d8dde2",
  "allowed_bases": [], "always_masterwork": false,
  "book": false,
  "forms": ["green", "salted", "pelt", "fur", "leather", "panel", "lacing"]
}
```

- **Kinds** join the forge's vocabulary: `hide`, `tannin`, `oil`, `wax`, `thread`, `dye` (fitting
  and treatment exist). `hide` is **structural**; the others are consumables.
- **`pieces`** names what a hide can fill: `body` and `lining` for armour, `body` for shields,
  `body` and `lining` for worn goods, and `haft` for weapons **only on grip-capable hides**.
- **`armour`**: **≥3 effects, ≥1 negative**, house numbers at the floor ±2 and within the tier
  ceiling (`materials.TIER_CEILING`: common 2, uncommon 2, rare 3, exotic 3, legendary 4), every
  combat, save and skill mod typed `material`. Book effects exempt from the ceiling.
- **`weapon`**: ≥3 with ≥1 negative **only when `pieces.weapon` names `haft`** (Q3.1).
- **`surface`** and **`color`** are for the stage and the swatch (UI plan §4); the forge kept its
  colour table in `play/forge_views.py`, and this plan puts it in the document, where the forge's
  own open item (forge contracts §15.6) says it belongs.
- **`allowed_bases`** carries the book's restrictions (eel hide and angelskin: leather, hide or
  studded leather only; darkleaf: padded, leather, studded leather or hide).
- **"Check penalty one worse"** and **"never reduces max Dex"** (deer, boar, crocodile, monitor
  lizard and seven others, Inv §2) become `gear_mod acp −2` and `gear_mod max_dex +2` (the forge's
  sign convention: the amount is added to the table's number). Narrative goes.

### 14.3 Grip-capable hides

Grips are what a hide becomes in the forge's `haft` slot. Grip-capable **(proposed list)**: the
skins that were real grip materials or are thin and tough: **sharkskin** (new), **ray skin** (new,
shagreen, PA §3.8), viper, crocodile, monitor lizard, frilled lizard, basilisk, wyvern, behir, every
dragonhide, and plain leather. Their weapon lists are about hold: attack +2 (sure grip), CMD vs
disarm +2, with a negative (damage −2 for a slick wrap, hardness −2). The forge's four leather grips
keep their current numbers until the pass re-derives them inside these fences.

### 14.4 The `thick` trait and hide armour

`thick` (a working trait) marks a hide that can be the body of hide armour: the large thick-hided
beasts (bison, elk, boar, dire boar, bear, crocodile, rhinoceros, mammoth, ankheg, bulette, purple
worm, dragon turtle, tarrasque) and any generic hide whose creature has natural armour +5 or more
(§5.4). Thick hides need the tannery's lime pit to flense (§7), which is the grounded reason hide
armour is a tannery suit.

### 14.5 The book fixes (do these first)

Every contradiction in the questions doc's "Book versus catalogue" list is corrected to the
printed rule, with the book's numbers as `"book": true` effects, before any house modifier:

| Material | Book effects (main piece only, fixed) | House top-up to 3 |
|---|---|---|
| **Dragonhide** (11) | §15 | §15 |
| **Eel hide** (`electric-eel-skin`) | `gear_mod acp +1` (min 0), `gear_mod max_dex +1`, `resistance electricity 2` (the wearer: this one is in the book), always masterwork, `allowed_bases` leather / hide / studded leather; +1,200 / +1,800 gp | already ≥3; house negative `gear_mod hardness −2` (thin skin) |
| **Angelskin** (moved from the forge's `angelskin-binding`) | a moderate good aura; the wearer's evil aura counts as 10 HD weaker; a 20% chance that an effect aimed at evil treats an evil wearer as neutral; hardness 5; always masterwork; leather / hide / studded leather only; +1,000 / +2,000 gp | the invented Will +3, AC +2, Diplomacy −3 are **removed** |
| **Darkleaf cloth** (new, UE) | `asf −10` (min 5%), `max_dex +2`, `acp +3`, `weight_pct −50`, hardness 10, 20 hp per inch; always masterwork; padded / leather / studded leather / hide; +750 / +1,500 gp | already ≥3 |
| **Griffon mane** (new, UE) | +2 competence on Fly; flight powers added later cost 10% less; cloak, robe, padded or quilted | house: AC +2 on padded, a negative `gear_mod weight_pct +10` |
| **Bone** (new, UE primitive; a fastenings material) | on studded leather: armour bonus −1, ACP 1 better (to 0); hardness 5 | not a hide: a fitting form |
| **Bulette** (`bulette-plate`) | the source's bulette **leather** has "the same statistics as studded leather": `as_base: "studded leather"` with **no metal** | names wait (§22); the +3 armour-typed AC is removed |
| **Boiled leather** | plain leather armour is Harden's product (§7) | – |

**Angelskin's aura effects** need alignment-targeted effects to read them. None exist in the app
yet; the Enchanting lanes' holy and unholy properties will be the first. Until then angelskin's
book effects show on the card as "book effect, not yet in play" (the forge's honest pattern for
book effects it could not express, forge contracts §15.7).

### 14.6 Consumables: working traits plus one mark

Tannins, oils, waxes, threads and dyes carry **working traits only, plus at most one small mark**
(Q3.2), the forge's fuel-flux-quenchant split. A mark is applied once, unscaled, from the step that
used the consumable, and is listed under the item's build. No tannin, wax or thread prose ever
reaches a finished item again (Inv §0.6).

| Kind | Working traits (examples) | Mark **(proposed**, at most one) |
|---|---|---|
| Tannin | `fast_tan`, `slow_tan`, `ceiling_up`, `ceiling_down`, `salt_proof`, `tans_white` (§8.1) | planar only: `styx-mordant` +1 damage vs outsiders on a grip; `dragonblood-tannin` resistance 2 to the dragon's energy |
| Oil | `supple` (Curry band wider), `rancid` (spoils in a year) | `salamander-oil` fire resistance 1; `troll-fat` hardness +1; `mink-oil` weatherproof (no Dye loss on soaking) |
| Wax | `fills_tooling` (Tool band wider) | `fireproof-wax` fire resistance 1; `ghost-wax` the item can be worn by an incorporeal creature (house) |
| Thread | `strong_seam`, `weatherproof` (sinew), `fine_pitch` (Stitch band wider) | `spider-silk-cord` hardness +1; `shadow-silk` Stealth +1 |
| Dye | `fast_colour` (with mordant), `fugitive` (without) | `shadow-black` Stealth +1 in dim light; `void-dye` Stealth +2 in darkness; others none |

Marks of one kind do not stack with each other (two fire-resistance marks give the higher), and
an item carries **at most one mark per consumable kind** (one tannin, one oil, one wax, one thread,
one dye) **(proposed)**. Consumables need ≥3 discoverable properties between their working traits
and the mark, as the forge's consumables do.

### 14.7 How the pass is done

The forge's pipeline (forge plan §5.8):
1. Export the 127 entries and their text to a tagging file.
2. Fill the book entries **by hand** from PA §1.3 and the table above.
3. Draft the house modifiers with model help **inside the validator's fences**, so nothing invalid
   can land.
4. Validate mechanically; **the owner reviews the house modifiers as a table**
   (`docs/leatherworking-review.md`, the forge's `docs/blacksmithing-review.md` pattern).
5. Rewrite each material's `text` to say what it does in the app.
6. Unify the shared materials: the eight leather fittings already link to forge metals (Inv §2);
   the forge's four leather pieces become leather forms (§4.4).

`materials.validate` stops returning early for the leatherworker catalogue (`:405`): hides are
judged as structural, consumables as consumables, and `knowledge._material_specs`
(`rules/knowledge.py:233`) reads the `mark` list, so marks are discoverable.

---

## 15. Dragonhide, book first

Book (PA §1.3, Core and UE; the wearer line confirmed verbatim):

| Book effect | As data |
|---|---|
| If the dragon was immune to an energy type, **the armour is immune** to it | new effect `object_immunity <energy>` (§18.4), book |
| "does not confer any protection to the wearer" | no wearer resistance from the book |
| Energy-resistance enchantments on it cost **25% less** | `gear_mod enchant_cost_pct −25` with `applies_to: "energy_resistance"`, read by the Enchanting cost reader (contracts §6.3) |
| Always masterwork | `always_masterwork` |
| Druids may wear it | `druid_permitted: true` (§18.5) |
| Hardness 10, 10 hp per inch | `gear_mod hardness`, `hp_per_inch` to reach 10 / 10 |
| Normally **hide armour** for a creature one size smaller; the best scales make banded mail (2 sizes smaller), half-plate (3), a breastplate or full plate (4) | the leather hide armour (§4.2); `harvest.scales.<id>` (§5.3) for the forge's scale suits |
| A Large or larger dragon also gives a shield | +1 unit (§5.5) |
| Double the masterwork cost, double Craft results | §13.5 |

**House top-up** (Q7.2), held to the legendary ceiling ±4: `resistance <energy> 2` for the wearer
(PF2e's dragonhide gives a small wearer edge, the precedent the questions doc cites, PA §1.7),
plus one negative (`gear_mod weight_pct +10`, the scales' weight) and one more positive by colour
(the review table). This fixes the 11 entries that give the wearer resistance 5 as if it were the
book's rule.

**Matching**: each true dragon's block is tagged with its own colour only (§5.3). The umbral
dragon's entry waits on licensing (§22).

---

## 16. Discovery: Grade

The leather assay, the forge's Assay in leather words (Q6.1), through `rules/knowledge.py`
(which already says the store covers this bench, `:29`):
- **Costs a scrap** (a quarter unit, or an offcut from any earlier step), takes **10 minutes**, a
  Craft roll at the material's DC, reveals **one positive and one negative** property.
- **Comparison makes it easier**: −1 DC for each known hide **of the same creature type**, max −4
  (the forge's touchstone rule, keyed on type rather than kind).
- **Working a hide** (any successful step) reveals its working traits.
- **Teachers** (a keeper with the `leather` occupation tag), **libraries** and **manuals** as for
  herbs and metals: a goods table `content/rules/leatherworking-manuals.json`.
- **No danger** in grading (there is no reactive hide); open point 10 if the owner wants one.

The **ledger** (forge plan §9.4) lists every hide met; the hide's source creatures show only as
the ones the player has met (UI plan §6.7).

---

## 17. Progression

### 17.1 Levels 1 to 3 (Q6.2)

| Level | Opens | Hides | Where |
|---|---|---|---|
| 1 | **Salt, Flense, Tan (brain, rawhide), Cut, Stitch, Assemble, Grade** | common, uncommon | field kit |
| 2 | **Tan (bark, alum, mineral), Curry, Dye, Tool, Harden, Laminate** | rare, exotic | Harden and vats at a tannery |
| 3 | **Legendary hides and the planar tannages** (dragonblood, Styx mordant, wyrm gall) | legendary | tannery |

Thresholds 25 and 65 (the herbalist's and the forge's). **Removed**: the level 4 and 5 rows, the
`legendary-hide` milestone and its deed (Inv §1), retired with their tests re-pinned, as theirs
were.

### 17.2 Endless levels

Two perk picks per level, the same one twice allowed, stored as live-read documents on
`Progress.perks` (stage 8's rule). Threshold 50 + 10 × (level − 3).

| Perk | Per pick |
|---|---|
| Potency | +5% to the bonus modifiers of everything you make |
| Hardening | −5% to the negative modifiers, on top of the level cut |
| Quality | +1 to the quality ceiling |
| **Yield** | at the **harvest**: +5% chance per hide taken of **+50% more hide units (proposed)**, rolled by the engine and shown (Q6.3: Yield moved to skinning) |

### 17.3 Ceiling and mastery

The forge's tables: ceiling Fine at level 1, Superior at 2, Flawless at 3, +1 per Quality perk.
Mastery as herbalism §4.4: each successful step (1, +1 per rarity band above common), the quality
bonus, firsts (a property learned, a product kind made, a hide worked, **a creature harvested for
the first time**: +3 each), an unread leatherworking manual (+5 once). `REPEAT_LIMIT` and
`MISHAP_LIMIT` keyed on (method, material).

---

## 18. The engine half

Every item below was confirmed in code by the inventory or by the code map for this plan
(contracts §9).

### 18.1 Worn leather through the forge's armour record (Q7.1)

- A leatherworker suit **is** a forged-shape record (`pieces` and `gear`), so
  `forge_items.is_forged` is true (`rules/forge_items.py:445`), `Actor.armour_record` finds it,
  and `armour_stats` returns `forge_items.armour_row(base, build(rec))` (`rules/sheet.py:815`):
  AC with the material bonus folded in, ACP, max Dex, spell failure, speed and weight from the
  build.
- `_wear_crafted` (`rules/engine.py:15031`) already uses `base`; with `base` a table key it dons.
  **The measured defect** (Inv §0.1, `crafting.from_stock_dict` copying the name into `base`) is
  fixed at the writer, and a test pins the refusal message never appearing for a bench suit.
- The older `/api/wear` path without an `op` (`play/views.py:4512`, the `[data-wear]` buttons),
  which puts the name in the slot and leaves `actor.armour` alone (measured AC 15 → 15), is routed
  through the engine's `wear` op for crafted records.
- **Resistance and DR from worn leather.** `resistance()` and `damage_reduction()` read only the
  worn forged suit's build (`rules/sheet.py:2791`, `:2823`). Because leather suits are now forged
  records they are read; worn goods are covered by §18.2.

### 18.2 Worn goods

A new gear kind `worn` in `forge_items` (pieces `body`, `lining`; the hide's `armour` list minus
`ac`, `acp`, `max_dex`, `asf`, the gear numbers that only mean something on a suit). Its specs
reach the sheet through `_standing_mods` for the item's slot, and its resistances through
`resistance()`, which gains a read of every worn crafted record's build. **`bonus_type: material`
never stacks with itself**, so a wolf-pelt cloak and a wolf-pelt lining do not add their Stealth
twice: the better applies (forge contracts §2).

### 18.3 The stacking defect

Hide AC typed `armour` never stacked with the suit's armour bonus (Inv §0.2;
`tests/test_aggregator.py:321` pins the typing). Under the forge's model hide AC is a `material`
modifier inside the build and folds **into** the armour bonus (`_folds_into_armour`). The aggregator
test is re-pinned: a hide's AC in a material document is `bonus_type: material` inside the
`armour` list, and a leather suit's AC on the sheet equals the table row plus the build's AC line.
The 13 hide specs that "do nothing on any suit" now do something.

### 18.4 Object immunity

Dragonhide's book power is about the **object**. Objects exist (`sheet.Item`, hardness and hp from
`tables.MATERIALS`, `rules/sheet.py:120`; the engine's `_object_damage`, `rules/engine.py:12812`),
but nothing can be immune. A new effect type in the object category of `rules/effectspec.py`:
`object_immunity` with an energy target, read by `Item.take_damage` and `_object_damage` so a red
dragonhide suit takes no fire damage when sundered or caught in a blast. Validated, rendered ("the
armour itself does not burn"), and its tell is "the dragonhide does not char".

### 18.5 The metal tag and its readers (Q7.3 ★)

**The tag is built by the Enchanting lanes** (contracts §6.2). Its proposed shape, which this plan
reads through one call and adapts to if their contract fixes another:
- every armour, shield and weapon record (crafted or table) answers `item_tags(record)` with
  `material.metal` when **any** of its pieces is a metal, `material.metal.ferrous` when any metal
  piece is iron or an iron alloy (a `ferrous: true` field on those metal documents), and
  `material.metal.<piece>` naming which;
- a table item with no record reads its metal from the one table list that exists today
  (`armour.METAL_ARMOUR`, `METAL_SHIELDS`, `rules/armour.py:198`) and a weapon table equivalent;
- the actor's standing tags gain `wears.armour.metal`, `wears.shield.metal`, `wields.metal`
  (and `.ferrous` under each), so every reader asks `has_state` with a prefix (law 1), and
  `armour.wears_metal` (the inubrix `when` clause) becomes a reader of the tag (grep every copy).

The **readers specified here**:

**The druid (prohibited metal).** Class-agnostic, so no class name enters the engine (stage 9's
direction): a class document may carry `"prohibits": {"tags": ["wears.armour.metal",
"wears.shield.metal"], "lapse_hours": 24, "suspends": ["casting.class", "ability.su.class",
"ability.sp.class"], "exempt": "druid_permitted"}`. The druid's document carries it (its
`"no metal armour"` proficiency token, `content/classes/druid.json:25`, is read today by nothing
but the armour-proficiency parser). While a prohibited tag holds, an `ActiveEffect` with origin
`rule:prohibited-metal` suspends the class's casting and supernatural and spell-like class abilities;
taking the item off starts a **24-hour** lapse effect (the Core text). An item whose main piece is
`druid_permitted` (dragonhide, by the book) is exempt; bone studs and leather never carried the tag.
Tells: "the iron on your body stands between you and the green", "the land's voice returns".

**Heat metal and chill metal.** Today their mechanics are a save gate with only narrative inside
(`content/spells/mechanics/part-08.json:3624`, `part-03.json:2686`). Made executable: targets the
metal equipment of the chosen creatures; a creature takes **full** damage if
`wears.armour.metal`, `wears.shield.metal` or `wields.metal`, minimum damage (1 or 2) if it only
carries metal; a periodic `ActiveEffect` (the forge's periodic executor) dealing 0 / 1d4 / 2d4 /
2d4 / 2d4 / 1d4 / 0 fire (cold for chill) over 7 rounds; Will negates (object) for magical metal,
no save for unattended nonmagical metal; each counters and dispels the other; heat metal does half
underwater and chill metal none. A dragonhide suit is not metal, so neither spell finds it (and if
a red dragonhide suit has steel buckles, its `object_immunity fire` protects the suit, not the
wearer).

**Rusting grasp.** Today a plain 3d6 damage spec (`spells-mechanics.json:10500`). Made executable
on `material.metal.ferrous`: a nonmagical ferrous item touched crumbles; magic metal items are
immune; worn armour loses **1d6 of the AC its metal pieces give** (a touch per round), which for a
mixed suit is capped at the metal's share: the finished suit's book AC minus its leather base's
(studded leather 3 − 2 = 1; armoured coat 4 − 2 = 2), so the leather survives the rust; a metal
weapon hit by the touch is destroyed (provoking); a ferrous creature takes 3d6 + 1 per level.
**(Proposed reading of the mixed-suit cap**, open point 7.)

**Shocking grasp.** Today 1d6 per level, cap 5d6 (`spells-mechanics.json:11062`), with the +3 not
implemented anywhere. Made executable: **+3 on the attack roll** when the target
`wears.armour.metal`, `wields.metal`, or is made of metal (a `body.metal` tag on the iron golem and
its kin, added by the bestiary pass, §5.3).

### 18.6 Tells

Law 3: every effect application emits a tell. New: the harvest ("you take the pelt whole", "the
knife slips: the hide tears"), spoiling ("the green hide has begun to stink"), a tannage collected,
dragonhide not charring, the druid's lapse and return, the four spells. The narrator is fed these
and nothing else about leather.

---

## 19. How it obeys the three laws

1. **One vocabulary.** Harvest parts are tags (`harvest.hide.*`), asked by prefix; the metal tag,
   the deed tag, working traits (`working.thick`) and the druid's prohibition are tags. The
   harvest never reads a creature's name; salt is read by material id, not a name fragment.
2. **One applicator.** Item numbers go through `forge_items.build` and the `_standing_mods`
   funnel; the druid's suspension, the spells and marks with triggers are `ActiveEffect`s with an
   origin. Remove the item and its contribution evaporates.
3. **Severed tells; no model authors a number.** Book numbers by hand from the sweep; house numbers
   drafted inside validator fences and reviewed by the owner; generic hides derive their numbers
   from the stat block in code. Validators refuse a hide with fewer than 3 armour modifiers, no
   negative, a narrative effect, a number over its ceiling, a weapon list on a non-grip hide, or a
   harvest tag on a humanoid, with the fix named.

---

## 20. Migrating old saves (Q9.1)

A version-stamped migration (`leatherworking_v2`) runs once per character:
1. **Levels 4 and 5** become level 3 plus perk picks, chosen on first load (herbalism's picker).
2. **Old leather records** (`kind: crafted`, flat `specs`, `armour: "leather"` or
   `"studded leather"`, Inv §1) are re-derived as forge-shape records: body = the hide named in
   `from_materials` (the first hide), fastenings = steel studs if the old record was studded
   leather (else plain lacing), lining plain; quality Sound unless the old record was masterwork,
   which **stays masterwork**; `base` the table key. The old record is kept beside the new one for
   one version so a bad inference can be undone (the forge's rule).
3. **Raw hides in the satchel** (bare counts in `inventory`) become green hide stock at Grade 2
   **(proposed**: neither the best nor the worst) and **start their clock on load with a full 48
   hours**, so no save spoils on load.
4. **Tannins, oils and the rest** keep their counts; a stock of a removed method's product stays
   usable and sellable as "old work".
5. **Proof:** run against the owner's save copy and Bobby, read-only in the scratchpad, and
   round-trip through save and load.

---

## 21. World Bible

Fixes are world-agnostic (standing instruction 2026-09-28). What the next export must carry,
added to `docs/campaign-format.md` as optional fields with defaults and listed in
`docs/from-world-bible.md`:
- **Hides as `play.materials[]` rows** in the forge's shape plus §14.2's fields (`pieces`,
  `armour`, `weapon` for grip-capable hides, `working`, `surface`, `color`, `forms`).
- **Tags on the world's creatures** (Q9.2 ★): wherever World Bible exports a creature (the
  format has no creature section today; `play.flora[]` alone mentions "parts of its own
  creatures"), each row carries `tags` with its `harvest.*` parts in the grammar of §5.3, plus the
  stat-block fields the reader uses (type, subtype, size, CR, resistances, immunities). **No
  separate fauna list.** A world's beast with tags yields its own hides; one without falls back to
  the generic rule (§5.3).
- **Tannin, oil, dye and thread rows** with their working traits and mark.
- World Bible's validator refuses `harvest.hide*` on a humanoid people (the world owns its own
  races, but a person is never a hide).

---

## 22. Licensing (the owner's call, not this plan's)

Mechanics now, names wait (Q9.4): bulette leather and bulette plate (*Dungeon Denizens
Revisited*), the hide shirt (*Varisia*), leaf armour (*Inner Sea World Guide*), the spider-silk
bodysuit (*Adventurer's Armory 2*), and the shipped `umbral-dragonhide` and `shadow-mastiff-hide`
(Golarion creatures) carry the bestiary's exposure (`docs/bestiary-licensing.md`). The Erutaki
coat, do-maru and kikko seen on the AoN medium-armour table come from campaign-setting books and
are not added. This plan renames nothing.

---

## 23. Build lanes

Detail, file ownership and the shapes that cross lanes are in `docs/leatherworking-contracts.md`.

| # | Lane | Contents | Writes (main) |
|---|---|---|---|
| A | **Vocabulary** | `object_immunity`; `enchant_cost_pct`; `as_base`; working traits for leather (`thick`, `fast_tan`, `slow_tan`, `ceiling_up`, `ceiling_down`, `salt_proof`, `tans_white`, `supple`, `fills_tooling`, `strong_seam`, `weatherproof`, `fine_pitch`, `fast_colour`, `fugitive`, `rancid`); validators, renderers | `rules/effectspec.py` |
| B | **Engine readers** | §18.1–18.4: leather bases in `forge_items` (always masterwork, `allowed_bases`, `marks`, gear `worn`), new table rows, the wear-path fix, worn goods' resistances, object immunity | `rules/forge_items.py`, `rules/sheet.py`, `rules/engine.py`, `rules/tables.py`, `rules/armour.py`, `rules/crafting.py` (the `from_stock_dict` writer only) |
| C | **Harvest** | §5, §6: the `harvest` op across crafts, the tag reader, generic hides, yield, grade, failure, deeds store, the clock and salt, the bestiary tag pass and its validator | NEW `rules/harvest.py`, NEW `rules/deeds.py`, `content/bestiary/*.json`, NEW `tools/harvest_tags.py`, `rules/herbprep.py` (the salt reader), `play/harvest_views.py` |
| D | **Data pass** | §14, §15: the hide documents, the book fixes, consumables, the review table, the forge's four leather pieces as forms | `content/materials/leatherworker-materials.json`, `content/materials/blacksmith-materials.json` (the four pieces only), `rules/materials.py`, NEW `docs/leatherworking-review.md` |
| E | **Bench rules** | §7–§13, §17: levels, perks, methods, tanning in time, intermediates, Laminate, masterwork, kit and tannery gating, the bench API | `rules/leatherworker.py`, `content/world-classes/leatherworker.json`, NEW `play/leather_views.py`, `pathfindergm/urls.py` (leather routes) |
| F | **Knowledge** | §16: Grade, comparison by creature type, marks as properties, manuals | `rules/knowledge.py`, `rules/goods.py`, NEW `content/rules/leatherworking-manuals.json` |
| G | **Tannery places** | §10: town tannery cue and keeper, outskirts placement, vat rent, the owned tannery | `rules/places.py`, `rules/market.py` |
| H | **Forge hand-off** | §4.4–4.5: the forge rack and Assemble take bases, grips, lacing and scales; finished leather suits as forge shapes | `rules/blacksmith.py`, `play/forge_views.py`, `content/world-classes/blacksmith.json` |
| M | **Metal readers** | §18.5: the druid's prohibition, heat and chill metal, rusting grasp, shocking grasp, over the Enchanting lanes' metal tag | `content/classes/druid.json`, `content/spells/mechanics/*.json`, `rules/casting.py`, `rules/classfeatures.py` |
| I | **Migration** | §20 | `rules/leatherworker.py` (old-item migration), `rules/sheet.py` load path (through lane B) |
| W | **World Bible docs** | §21 | `docs/campaign-format.md`, `docs/from-world-bible.md` |
| U1–U7 | **UI and 3D** | the UI plan's lanes | `play/static/...`, `play/templates/...` |

**Order.** A first (vocabulary). B and C after A, in parallel. D after A (it needs the types to
validate). E after B and D. F after D. G any time. H after B and E. M after the Enchanting lanes'
metal tag lands, and after B. I after E. U1 as soon as E's API exists. **Why:** as the forge's,
lanes A and B make one hand-written hide do something on the sheet before the 127 are rewritten,
so the data pass is checked in play, not only by validators.

### 23.1 Tests each lane must add

Each names the defect it prevents in its docstring.
- **A:** `object_immunity` validates only with an energy target; a leather working trait outside
  the list is refused with the list named.
- **B:** a studded leather suit made at the leather bench and finished at the forge raises
  `pc-kesst`'s AC from 15 to 16 ("measured 15 → 15 before: the name went into the slot");
  a bench suit never meets "not built on any suit the rules know"; a hide's AC folds into the
  armour bonus ("13 hide specs did nothing on any suit"); a masterwork leather suit's ACP is one
  lighter; a winter-wolf cloak's cold resistance reaches `resistance("cold")`; a red dragonhide
  suit takes no fire damage as an object while its wearer takes full fire damage ("11 entries gave
  the wearer resistance 5").
- **C:** one wolf yields its pelt once and then "taken" ("six skinnings of one wolf ran, three
  succeeded"); a red dragon offers only red dragonhide ("offered all 11 colours"); no humanoid
  offers anything ("109 humanoids yielded a hide"); a lion and a shark yield a generic hide ("lion,
  elephant, mammoth, shark... yielded none"); the DC is 15 + CR whatever the crafter's level
  ("Leatherworker 5 skinned a wolf at DC 22, level 1 at DC 10"); a good roll does not multiply the
  haul (`1 + margin // 5`); a harvested hide's clock reads 48 hours ("`picked_at` was None for
  everything skinned"); salt carried at the harvest is spent, one per unit; a good outsider's
  harvest writes one deed with the witnesses; the reader never reads `actor.name` (a renamed wolf
  still yields its pelt).
- **D:** every hide has ≥3 armour modifiers with ≥1 negative, no narrative ("96 of 171 specs were
  narrative"); only grip-capable hides carry weapon lists; every book material's book effects match
  §14.5 (a set comparison); dragonhide gives the wearer no book resistance; no consumable's prose
  reaches an item ("a boar-hide suit listed 'the standard tanning agent'").
- **E:** a tannage is not collectable before its minute (advance the clock to one minute short,
  then to the minute); Harden refuses alum and brain leather and needs no wax ("Harden's one
  enforced input was the wrong one"); a fail by 4 keeps every input ("every input spent on any
  failure"); a minigame miss after a success takes nothing; a dragonhide suit is masterwork at
  Sound ("not masterwork without Tool"); a grade 3 hide cannot make better than Fine; the worked
  example (§13.3) to the integer; no DC creep ("red dragonhide suit DC 38").
- **F:** Grade reveals one positive and one negative; each known hide of the same creature type
  lowers the DC by 1, max 4.
- **G:** a town with a tanner keeper offers a tannery on its outskirts; the vat holds 4 units.
- **H:** the forge's Assemble accepts a leather base for studded leather and refuses it for full
  plate; a sharkskin grip fills a longsword's haft.
- **M:** a druid in steel-studded leather cannot cast, and can 24 hours after taking it off, not
  23; a druid in dragonhide or bone-studded leather casts; heat metal deals full damage to a
  chainmail wearer and minimum to a creature carrying a dagger; rusting grasp takes at most 1 AC
  from studded leather; shocking grasp gets +3 against a chain shirt and not against hide armour.
- **I:** an old studded leather "Deer Armour" save loads as a wearable forge-shape suit and keeps
  its masterwork; raw hides in an old satchel read 48 hours on load.

---

## 24. Open points for the owner

1. **Steel lamellar.** Q1.3's answer lists "lamellar" among the forge's finishes. The book's
   leather lamellar has no metal, so this plan makes it the leatherworker's whole, and reads the
   forge's lamellar as **steel lamellar**, where the steel plates are the main piece and the
   leatherworker supplies the lacing set (§4.2). Confirm, or should the forge's lamellar take a
   leather base like studded leather?
2. **Finished quality across two crafts** (§4.3): the lower of the base's tier and the forge's
   Assemble tier. The alternative is per-piece quality, which changes the forge's maths.
3. **Harden at the tannery** (Q6.4) puts plain leather armour (book: boiled) behind a tannery, so a
   level-1 leatherworker in the field cannot make it (§10). Accept, or let a small kettle at the
   kit Harden common hides?
4. **The craft's level on the harvest roll** (§5.2): the book's Survival only, with a +2 skinning
   kit. Should the craft's level add, as it does at the bench?
5. **How long a carcass waits** (§5.9): 24 hours after death proposed; the Handbook's 1 hour is
   harsher, Ultimate Wilderness sets none.
6. **DR from the stat block** (§5.4): generic hides inherit energy resistance but not DR. A
   creature with DR 5/silver could give DR 1/silver on a rare-and-up hide. Leave it out?
7. **Rusting grasp on mixed suits** (§18.5): the metal pieces' share of the AC (studded leather
   loses at most 1). Accept?
8. **Salt costs salt** (§6): one measure per hide unit at the harvest, unlike herbalism's free
   preserving. Accept, and should herbalism's animal parts then cost salt too?
9. **Which settlements have a tannery** (§10): proposed only where the settlement's words imply one,
   on the outskirts. The forge put a smithy in every city.
10. **A dangerous grade**: no hide is reactive. Do any (a basilisk's, a behir's) bite back when
    tested, as noqual does at the forge?
11. **Deeds store** (§5.6): `Actor.deeds` is defined here because no renown system exists. Should
    it wait for the renown plan, with the harvest only offering the confirm?
12. **The good-outsider deed only.** Should harvesting a good-aligned dragon (gold, silver) also be
    a deed?
13. **Marks per item** (§14.6): one per consumable kind (up to five). Fewer?
14. **Proposed numbers to tune in play**: tier bands by CR, hide units and product needs, the
    grade caps, the tannage times, vat size and rent, Yield's +50%, Salt's 6-week keep, step times,
    the harvest failure rule. All in rule rows.

---

## Sources checked for this plan

New primary sources, beyond `docs/leatherworking-prior-art.md`:
- Druid, Weapon and Armor Proficiency (Core): https://www.aonprd.com/ClassDisplay.aspx?ItemName=Druid
- *Heat metal*: https://www.aonprd.com/SpellDisplay.aspx?ItemName=Heat%20Metal
- *Chill metal*: https://www.aonprd.com/SpellDisplay.aspx?ItemName=Chill%20Metal
- *Rusting grasp*: https://www.aonprd.com/SpellDisplay.aspx?ItemName=Rusting%20Grasp
- *Shocking grasp*: https://www.aonprd.com/SpellDisplay.aspx?ItemName=Shocking%20Grasp
- Armored coat: https://www.aonprd.com/EquipmentArmorDisplay.aspx?ItemName=Armored%20coat
- Light and medium armour tables (lamellar rows): https://www.aonprd.com/EquipmentArmor.aspx?Category=Light,
  https://www.aonprd.com/EquipmentArmor.aspx?Category=Medium
- Masterwork tool (Core p.158, UE p.77): https://www.aonprd.com/EquipmentMiscDisplay.aspx?ItemName=Masterwork%20tool
- Masterwork backpack (UE): https://legacy.aonprd.com/ultimateEquipment/gear/adventuringGear.html
  (read through a search summary, not fetched directly)
- Studded leather and druids, no ruling found: Paizo forums, e.g. https://paizo.com/threads/rzs42x2u
  and https://paizo.com/threads/rzs2qiq6 (community discussion, [S]); the Game Mastery Guide claim
  in those threads **could not be confirmed**.

**Could not confirm:** whether Ultimate Campaign has a tannery building (the AoN page did not
return it), so vat rent is a house number.
