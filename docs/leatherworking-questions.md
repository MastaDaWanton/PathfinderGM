# Leatherworking revamp: the owner's questions

The decision rounds the lead puts to the owner before anything is designed, in the
multiple-choice form used for Herbalism and the Blacksmith. Every question has 2 to 4
options. The recommended one comes first and is marked **(Recommended)**, and each option
carries a one-line consequence. Each round has at most 4 questions.

Grounded in `docs/leatherworking-inventory.md` (cited as **Inv §n**) and
`docs/leatherworking-prior-art.md` (cited as **PA §n**).

**Assumed, not asked.** These cross-craft rulings already made for Herbalism and the forge
are assumed to carry over, so they are not asked again:
- The d20 Craft roll decides success, and one minigame per method climbs the quality tier
  (Crude → Flawless → +N, with the ceiling set by level, and masterwork at Superior). The
  minigame is always played.
- Levels 1 to 3, then endless levels with two perk picks each.
- Real intermediates land on the shelf.
- Properties are discovered through assay, study, teachers, libraries and manuals.
- Materials carry complete typed effect documents with no narrative, and at least 3
  discoverable traits. Book effects win, with house top-ups.
- One material, many shelves.
- No model authors a number.
- Fixes are world-agnostic: World Bible export fields.
- Old saves convert.

Round 9 asks for confirmation only where the research pushes against one of these.

---

## Round 1: What leatherworking is for, and where the forge stops

**Q1.1 What is leatherworking for?**
- **The hunt made wearable (Recommended).** It shares the three kinds of fun with Herbalism and
  the forge: hands-on craft, discovery, and a way to be seen. What is its own is that the beast
  you killed becomes what you wear, so the hide carries something of the creature into the
  item.
  - Consequence: skinning and the hide's grade become a real half of the craft (Round 4), not
    a menu click.
- **Light armour craft.** Leather armour and shields first, everything else second.
  - Consequence: smaller scope. Cloaks, boots and bags stay thin.
- **The outfitter.** Bags, kits, saddles and straps that make other systems work, and armour
  as one product among many.
  - Consequence: needs carrying-capacity and mount rules the app does not have.

**Q1.2 Do leather and hide armour use the forge's armour piece model (body, fastenings,
lining) and its crafted-item record?**
- **Yes: one armour model (Recommended).** The hide or leather is the main **body** piece. The
  fastenings are buckles, studs, rings or lacing. The lining is fur, padding or soft leather.
  The record is the forge's (`gear: armour`, `base`, `pieces`), read by `forge_items.build` and
  `Actor.armour_stats`.
  - Consequence: the measured wear defect disappears (Inv §0.1, §5), masterwork −1 ACP comes
    for free, and the forge's validator fences the data. The cost is that hides gain `pieces`
    and `armour` lists.
- **A separate leather record and reader.**
  - Consequence: two armour models and two sets of stacking rules. This is what the inventory
    found broken today.
- **The forge makes every suit and leatherworking supplies the leather.** This is the book's
  split: armour is Craft (armor), DC 10 + AC bonus (PA §1.1).
  - Consequence: the purest reading of the rules, but leatherworking loses its signature
    product.

**Q1.3 Who makes the mixed suits?**
- **The body piece decides (Recommended).** If the body is hide or leather, it is the
  leatherworker's work: leather, studded leather, hide, leather lamellar, padded, quilted
  cloth. If the body is metal, it is the forge's: armoured coat, the metal suits. Each craft
  buys the other's pieces as fittings or lining, which is already how steel studs work (the
  `steel-studs → steel` link).
  - Consequence: one rule, readable at a glance. Studded leather is the leatherworker's, with
    smith-made studs as its fastenings.
- **By the book's Craft skill.** Every suit is Craft (armor), so the forge makes them all.
  - Consequence: the same as Q1.2's third option.
- **Either craft can make any suit at a penalty outside its own.**
  - Consequence: more freedom, plus a second DC rule to teach.

**Q1.4 What does it make?**
- **Armour, shields, worn gear, grips, and carried goods (Recommended).** That covers:
  - the light and medium leather suits, and the madu (the book's leather shield);
  - cloaks, boots, gloves, bracers, belts and caps;
  - weapon grips and wraps, filling the forge's `haft` slot as the forge already lets
    `leather-grip` do;
  - sheaths, quivers, satchels and kit rolls.
  - Consequence: matches today's 11 products plus grips and shields. Carried goods need a
    small rule each, or they stay flavour.
- **The above, plus barding and tack.**
  - Consequence: barding is in today's list but no mount wears it. That needs mount rules
    first.
- **Armour and grips only.**
  - Consequence: the tightest scope, but drops the cloaks and boots that carry most of the
    non-AC hide traits.

---

## Round 2: Methods

**Q2.1 Keep, trim or add?**
- **Trim and add (Recommended).** The proposed set:
  - **Flense**: liming and dehairing fold in here.
  - **Salt**: the field cure, which really uses salt.
  - **Tan**: vegetable, brain, alum or mineral, chosen by the tannin.
  - **Curry**: Oil folds in here.
  - **Cut**, **Stitch** and **Harden** (cuir bouilli).
  - **Tool**: stamping and carving.
  - **Dye**.
  - **Assemble**: where pieces join, as at the forge.
  - **Grade**: the assay.
  - Removed: **Line**, which measurably does nothing (Inv §1). Lining becomes a piece at
    Assemble. **Skin** becomes the harvest action (Round 4).
  - Consequence: every method has an input it really consumes and a measurable effect.
- **Keep the eleven and fix what is broken.**
  - Consequence: cure still needs no salt and line still does nothing, unless each gets a rule
    invented to justify it.
- **A short chain: Flense, Tan, Cut, Stitch, Assemble.**
  - Consequence: fewer minigames, but Harden and Tool lose their place, and those are the
    craft's most distinctive steps.

**Q2.2 Is tanning real world time?** Herbalism's steeping is real time: a tincture takes 2
weeks.
- **Yes, by tannage, and the hide travels with you (Recommended).**
  - Brain or smoke tanning takes about a day of work.
  - Alum tawing takes days, then weeks of ageing.
  - Bark tanning took 12 months for strong leather at a working tannery, so the game would
    compress it to weeks.
  - A tanning vat in a tannery can hold a hide while you adventure (PA §3.3).
  - It is in-world clock time, never a real-time gate (PA §0.6).
  - Consequence: thick monster hides become a planned project, which matches the real craft.
    Needs the steeping clock herbalism already has.
- **The time is spent at the bench clock and nothing waits.**
  - Consequence: simpler. Tanning becomes the same as any other step.
- **Instant, as today.**
  - Consequence: no reason to choose a fast tannage over a slow one, so the tannin choice loses
    half its meaning.

**Q2.3 Which intermediates land on the shelf?**
- **Each real stage (Recommended).** Green hide, then salted hide, then rawhide or tanned
  leather (with its grade), then cut panels or hardened plates, then the finished item. Each is
  sellable.
  - Consequence: fixes the measured "every piece is flense-to-finish in one session" (Inv
    §0.5). A tanned hide finally survives a session.
- **Only tanned leather and the finished item.**
  - Consequence: fewer records, but a salted hide still cannot wait on the shelf.

**Q2.4 What is leatherworking's Strengthen (concentration)?**
- **Laminate (Recommended).** Two leathers of one material are glued and stitched into one
  heavy leather. Every modifier is ×1.5, bonuses and negatives alike, and each level after the
  first cuts the negatives by 10%.
  - Consequence: the forge's rule exactly, on grounded practice (doubled leather was a real
    armour build).
- **Harden is the concentration.** Each pass is ×1.5, but makes the leather stiffer: a bigger
  armour check penalty and a lower max Dex.
  - Consequence: one fewer method, but Harden can then only be done once per piece.
- **No concentration in this craft.**
  - Consequence: high-level leather caps out below high-level steel.

---

## Round 3: Products and the item numbers

**Q3.1 Do hides follow the forge's 3 weapon + 3 armour modifiers rule?**
- **3 armour modifiers on every hide, and 3 weapon modifiers only on hides that can be grips
  (Recommended).** At least one negative in each list, house base ±2, and the forge's tier
  ceilings.
  - Consequence: the same fences and validator as metals. Grip-capable hides (sharkskin, ray,
    snake, dragon) get a real weapon list; a bear pelt does not need one.
- **3 + 3 on every hide.**
  - Consequence: about 65 weapon lists, most of them for hides nobody wraps a hilt in.
- **Armour only.**
  - Consequence: the forge's `haft` slot keeps only its own four leather grips.

**Q3.2 The non-structural materials: tannins, oils, waxes, threads, dyes?**
- **Working traits, plus at most one small "mark" (Recommended).** This mirrors fuels and
  fluxes (working traits only) and quenchants (working traits plus one quench mark). Examples:
  - A tannin sets the tanning time and the quality ceiling.
  - Sinew thread makes a weatherproof seam.
  - Salamander oil leaves a small fire resistance on the item.
  - Consequence: fixes the measured leak of tannin prose onto finished items (Inv §0.6), and
    keeps the 3-traits rule satisfiable.
- **All carry item effects.**
  - Consequence: many more numbers to balance, and every dye becomes an armour enchantment.
- **Working traits only.**
  - Consequence: shadow-black dye and void dye lose their Stealth bonus.

**Q3.3 Carried goods (satchels, sheaths, quivers, kits): mechanical or flavour?**
- **A small book-backed rule each where one exists, flavour otherwise (Recommended).** A
  masterwork kit roll counts as masterwork artisan's tools (+2 circumstance on Craft checks,
  PA §1.1). A waterproof satchel protects its contents.
  - Consequence: some goods matter. Each needs a hook in an existing system.
- **Flavour and sale value only.**
  - Consequence: cheap to build. The same as today.

**Q3.4 Masterwork and the "always masterwork" hides?**
- **The book wins (Recommended).** Dragonhide, eel hide, angelskin and darkleaf cloth make
  masterwork armour at any quality tier, as the book says. Every other leather is masterwork
  at Superior or better, as at the forge.
  - Consequence: fixes the measured "dragonhide suit is not masterwork without Tool" (Inv
    §0.7).
- **Superior or better only, for every material.**
  - Consequence: one rule, but it contradicts four book materials.

---

## Round 4: Harvesting and hide quality

**Q4.1 How does skinning work?**
- **One harvest per carcass, on the book's numbers (Recommended).** Ultimate Wilderness: DC
  15 + the creature's CR, Survival for external parts such as hide (PA §1.4).
  - The carcass is marked harvested.
  - The yield follows the creature's size: the dragonhide rule ties suit size to dragon size,
    and Ultimate Wilderness gives part weight by size.
  - The hide's **grade** comes from the skinning minigame.
  - Consequence: fixes four measured defects at once: repeatable skinning, the DC set by the
    crafter's level, the modular pick that skipped the pelt, and the margin multiplier (Inv
    §0.3).
- **Keep the excursion and fix its bugs.**
  - Consequence: smaller change. Skinning stays a menu roll with no hide grade.
- **Hides drop as loot when a fight ends.**
  - Consequence: no skill involved. This is the Valheim and RuneScape shape (PA §2).

**Q4.2 Does how the beast died affect the hide?**
- **No. The hide's grade comes only from your skinning, and the beast sets the tier
  (Recommended).** Prior art warns against penalising the kill and against random part drops
  (PA §2, §6).
  - Consequence: no reason to fight a wolf "carefully". Agency stays at the skinning beam.
- **A little.** A creature killed by fire or acid caps its hide one grade lower.
  - Consequence: a readable trade-off, but fire mages are punished for no fault of their own.
- **Yes, strongly.** The weapon and the wound location matter, as in Red Dead Redemption 2.
  - Consequence: needs hit locations the engine does not have.

**Q4.3 Which creatures can be skinned, and how is the creature matched?**
- **By the bestiary's type, subtype, size and CR, never by words in the name
  (Recommended).**
  - Animals, magical beasts, dragons, and scaled or furred monstrous creatures give a hide.
    Vermin give chitin.
  - A named hide in the catalogue wins where one exists. Otherwise a generic hide of the
    creature's type and size is made, carrying traits read from its own stat block (its energy
    resistance, its DR type).
  - Humanoids are never skinned.
  - Consequence: fixes the 109 skinnable humanoids, the red dragon that offers 11 colours, and
    the lion with no hide (Inv §0.4). A World Bible beast with a stat block works with no
    hand-written entry.
- **Named hides only, matched by id rather than by fragment.**
  - Consequence: correct, but most of the bestiary gives no hide.
- **Keep fragment matching and tighten the fragments.**
  - Consequence: the cheapest option. "Bugbear" and "Battle Mage" style collisions will keep
    recurring with every new creature.

**Q4.4 The spoilage clock?**
- **Keep 48 hours from the harvest, actually start it, and let salt in the pack stop it
  (Recommended).** The book's windows are 24 hours from the harvest (Ultimate Wilderness), 2
  days to rot (Monster Hunter's Handbook), and a corpse dead under an hour to harvest from
  (Handbook). The salt rule is herbalism's.
  - Consequence: the rule the tests pin finally runs in play (Inv §0.3). Carrying salt becomes
    a real decision.
- **Drop the clock.**
  - Consequence: removes a pressure the real craft has, and deletes tested code.

---

## Round 5: One carcass, four crafts, and the hard cases

**Q5.1 Four crafts harvest the same carcass separately. Merge them?**
- **One "Harvest the carcass" action listing every part for every craft the character has
  (Recommended).** Each part can be taken once, with the check for each part made by the craft
  that wants it.
  - Consequence: no more four separate repeatable d20s over one dragon (Inv §4). One place to
    see what a kill is worth.
- **Keep one excursion per craft, each once per carcass.**
  - Consequence: smaller change, but the player still clicks four times per dragon.

**Q5.2 Sentient creatures, and the book's angelskin.** The book prints dragonhide (dragons are
sentient) and angelskin (made from angels).
- **Allowed by the book, marked as a deed (Recommended).**
  - Dragons and the book's named exceptions can be harvested.
  - Humanoids never can.
  - Harvesting a good outsider is recorded as a deed that the world's renown and alignment
    systems can see.
  - Consequence: keeps the book's materials and gives the act weight, without the app ruling
    on morality itself.
- **No sentient creature at all.** Dragonhide and angelskin come from traders only.
  - Consequence: removes the most iconic trophy material from the hunt.
- **No restriction beyond the creature type.**
  - Consequence: simple, but puts outsider-skinning on the same footing as deer.

**Q5.3 How many pieces does one creature give?**
- **By size, from the book's dragonhide ratio (Recommended).** A creature yields hide for one
  suit for a wearer one size smaller. Smaller hides combine (a cloak needs one Medium hide, a
  suit needs one Large or two Medium).
  - Consequence: grounded in the only printed yield rule (PA §1.3). Big beasts are worth more.
- **Always one hide, of a fixed size per entry, as today.**
  - Consequence: a young dragon and a great wyrm give the same hide (Inv §2).

---

## Round 6: Discovery, levels and perks

**Q6.1 How are a hide's properties discovered?**
- **Grade, the leather assay (Recommended).** It costs a scrap, takes 10 minutes, and reveals
  one positive and one negative property. It works as the forge's assay does, and is easier
  for each known hide of the same creature type. Working a hide reveals its working traits.
  Teachers, libraries and manuals are as for herbs.
  - Consequence: the same knowledge store as the forge (`rules/knowledge.py` already names
    this bench).
- **Known on sight.** The creature you skinned tells you what its hide does.
  - Consequence: no discovery half for this craft.

**Q6.2 What do levels 1 to 3 open?**
- **Field work, then the tannery, then legendary (Recommended).**
  - Level 1: Salt, Flense, brain tanning, Cut, Stitch, Assemble and Grade, for common and
    uncommon hides.
  - Level 2: bark and alum tanning, Curry, Dye, Tool, Harden and Laminate, for rare and exotic
    hides.
  - Level 3: legendary hides and the planar tannages (dragonblood, Styx mordant).
  - Consequence: the same shape as herbalism and the forge. The level-5 `legendary-hide`
    milestone is retired, as theirs were.
- **Harden at level 3.** Cuir bouilli is the master's work.
  - Consequence: hard leather armour waits until level 3.

**Q6.3 Perks for the endless levels?**
- **The forge's four, with Yield moved to skinning (Recommended).**
  - Potency: +5% to bonuses.
  - Hardening: −5% to negatives.
  - Quality: +1 to the ceiling.
  - Yield: +5% chance of an extra hide piece at the harvest, rolled and shown.
  - Consequence: one perk table across three crafts. Yield rewards the hunt.
- **Add a fifth, Trophy.** A chance that the harvest also gives a trophy, worth CR² × 10 gp
  (Monster Hunter's Handbook, PA §1.4).
  - Consequence: more choice, and one more economy number to tune.

**Q6.4 Where can you work?**
- **A field kit plus a tannery (Recommended).**
  - The kit does Salt, Flense, brain tanning, Cut, Stitch, Assemble and Grade, anywhere.
  - A tannery (a town one you pay for, or one you found) adds vat tanning, liming, the
    hardening kettle, and rare-and-above hides.
  - Consequence: the forge's smithy rule, retiring the "fixed tools deliberately unread" note
    (Inv §1). Real tanneries were kept out of town for the smell, which gives a grounded
    reason they are rarer than smithies.
- **Kit only, anywhere.**
  - Consequence: simpler, but the declared tannery tools stay dead.

---

## Round 7: The engine half

**Q7.1 How does worn leather reach the sheet?**
- **As the forge's armour record (Recommended).** The hide's AC folds into the suit's armour
  bonus as a material bonus, so it is no longer swallowed. ACP, max Dex and spell failure come
  from the build. Resistances apply while worn.
  - Consequence: fixes Inv §0.1 and §0.2 together.
  - Proof of done: a studded leather suit made at the bench raises AC from 15 to 16 on the
    pc-kesst fixture.
- **Keep the flat record and fix the wear path and stacking.**
  - Consequence: a second armour reader to maintain beside the forge's.

**Q7.2 Dragonhide's book power is that the armour is immune to the dragon's energy, but the
wearer is not protected.**
- **Book first, plus a house top-up (Recommended).**
  - The suit itself is immune: it takes no damage from that energy when it is sundered.
  - It counts as metal-free for druids.
  - Energy-resistance enchantments on it cost 25% less.
  - House modifiers, held to the tier ceiling, give the wearer a small resistance.
  - Consequence: fixes the 11 entries that give the wearer resistance 5 as if it were the
    book's rule (PA §1.3). Needs the druid metal rule (Q7.3).
- **Keep wearer resistance 5 and mark it as a house rule.**
  - Consequence: no engine work, but it is not the book, and it would sit in the book field.

**Q7.3 Should the engine enforce the druid's no-metal-armour rule?**
- **Yes (Recommended).** Armour gets a `metal` tag from its body piece. A druid in a metal suit
  loses spells and supernatural abilities until 24 hours after taking it off, as the Core
  Rulebook says.
  - Consequence: gives leather and dragonhide their book reason to exist.
- **No, leave it to the player.**
  - Consequence: the "druid may wear it" property stays prose.

**Q7.4 Grips and wraps on forged weapons?**
- **The leatherworker makes the `haft` piece and the forge's Assemble takes it (Recommended).**
  The four leather grips now in the forge catalogue become forms of leatherworker materials.
  - Consequence: one material, many shelves, in the other direction. Needs a cross-craft trade
    of pieces in stock.
- **Leave grips in the forge's catalogue.**
  - Consequence: a leatherworker's sharkskin never reaches a hilt.

---

## Round 8: The bench, the stage and the minigames

**Q8.1 Its own bench, or the forge's?**
- **Its own bench, built from the herb bench and forge parts (Recommended).** The stage is a
  field kit on the ground or a tannery yard. The work is built from its pieces in 3D, with
  engraved icons.
  - Consequence: the same build pattern as the forge's lanes U1 to U6.
- **The forge bench with a leather mode.**
  - Consequence: less to build, but the 3D props (anvil and quench) are wrong for the craft.

**Q8.2 Which minigames?** One per method, on real controllable variables (PA §3, §5).
- **The grounded set (Recommended):**
  - **Flense:** scrape strokes at the right angle and pressure without cutting through.
  - **Tan:** keep the liquor strength rising in steps, and finish with a cut test.
  - **Harden:** trade heat against time: soft if under, shrunk and brittle if over.
  - **Stitch:** keep an even stitch pitch and rhythm.
  - **Tool:** case the leather to the right moisture, then strike.
  - **Cut:** follow the pattern line.
  - **The harvest:** cut along the line, avoiding holes.
  - Consequence: every game reads as the real craft.
- **Fewer games: one shared "precision" game reskinned per method.**
  - Consequence: faster to build, and the methods blur together.

**Q8.3 How generous do they start?**
- **Generous, with Steady mode, and every band shown as a number and a bar as well as a colour
  (Recommended).** Every crafting minigame in the prior art was softened after launch (PA §6).
  - Consequence: the forge's and herbalism's rule, unchanged.
- **Tuned hard, then softened in playtest.**
  - Consequence: repeats the mistake the prior art documents.

**Q8.4 The old `/craft/` Leatherworking tab?**
- **It shows a "moved" card when the new bench ships, as herbalism's does (Recommended).**
  - Consequence: one bench per craft, and the old chain code retires with its tests re-pinned
    (Inv §7).
- **Keep both for a version.**
  - Consequence: two benches disagreeing about the same hide.

---

## Round 9: Old saves, World Bible, and confirmations

**Q9.1 Old saves?**
- **Convert (Recommended), as herbalism and the forge did.**
  - Levels above 3 become endless levels with perks picked on first load.
  - Old leather records are re-derived as armour records (body = the hide named in
    `from_materials`), and old masterwork stays masterwork.
  - Raw hides in the satchel start their clock on load, with a full 48 hours.
  - Consequence: no one loses a suit. The 48-hour grace avoids a save spoiling on load.
- **Leave old items as "old work" that can be worn or sold, not worked further.**
  - Consequence: what the forge did for its old items. Simpler, but old leather armour still
    cannot be worn (Inv §0.1) unless the wear path is fixed anyway.

**Q9.2 What should World Bible export for leather?**
- **Hides as `play.materials[]` rows, plus a fauna list with stat-block fields
  (Recommended).** The materials rows have the same shape as the forge's (`pieces`, `armour`,
  `weapon`, `working`). The fauna list gives type, size, CR, and energy resistance or DR, so a
  world's own beasts can be skinned by Q4.3's rule.
  - Consequence: fixes are world-agnostic. Today a world's own beast yields only generic goods
    (Inv §4).
- **Materials rows only.**
  - Consequence: world beasts stay unskinnable until they enter the bestiary.

**Q9.3 Confirm: does the 48-hour clock plus real tanning time make leatherworking too
slow to enjoy?**
- **Keep both, with salt and a tannery vat as the relief valves (Recommended).**
  - Consequence: the craft's pacing is its identity, and the relief valves are player choices.
- **Keep the clock, and make tanning bench time only.**
  - Consequence: faster, with less planning.

**Q9.4 Licensing of the non-core book materials?** Bulette armour (Dungeon Denizens
Revisited), the hide shirt (Varisia), leaf armour (Inner Sea World Guide) and spider-silk
(Adventurer's Armory 2) come from campaign-setting and Chronicles books (PA §1.6).
- **Use the open mechanics and leave the names to the bestiary licensing decision
  (Recommended).** This is the forge's skymetal ruling.
  - Consequence: consistent with `docs/bestiary-licensing.md`.
- **Use only Core, APG, Ultimate Equipment, Ultimate Combat, Unchained and Ultimate
  Wilderness.**
  - Consequence: the safest choice. Loses bulette leather and leaf armour.

---

## Round sizes

| Round | Topic | Questions |
|---|---|---|
| 1 | Purpose and the forge boundary | 4 |
| 2 | Methods | 4 |
| 3 | Products and item numbers | 4 |
| 4 | Harvesting and hide quality | 4 |
| 5 | One carcass, four crafts, hard cases | 3 |
| 6 | Discovery, levels, perks, where | 4 |
| 7 | The engine half | 4 |
| 8 | Bench, stage, minigames | 4 |
| 9 | Old saves, World Bible, confirmations | 4 |
| | **Total** | **35** |

---

## Book versus catalogue: the contradictions found

Checked against the Archives of Nethys text (PA §1). Each is a defect in the shipped
catalogue or code, whatever the owner rules above.

1. **Dragonhide (11 entries).**
   - Each gives the **wearer** `resistance <energy> 5`. The book makes the **armour** immune
     to the dragon's energy "although this does not confer any protection to the wearer".
     What it does give: energy-resistance enchantments on the suit cost 25% less.
   - The book also makes dragonhide armour masterwork by nature, druid-wearable, hardness 10
     with 10 hp per inch, and normally **hide armour** (the best scales can make banded mail,
     half-plate, a breastplate or full plate for smaller wearers).
   - The code: masterwork only with Tool, and the output is always `leather` AC 2 (Inv §0.7,
     §1).
2. **Eel hide.** `electric-eel-skin` (uncommon) is electricity resistance 2 only. The book
   adds:
   - ACP −1 and max Dex +1;
   - always masterwork;
   - leather, hide or studded leather only;
   - +1,200 gp (light) or +1,800 gp (medium).
3. **Angelskin.** The forge's `angelskin-binding` gives Will +3, AC +2 and Diplomacy −3. The
   book gives a moderate good aura and makes the wearer's evil aura read as 10 Hit Dice weaker,
   with a 20% chance that effects aimed at evil treat the wearer as neutral. It is always
   masterwork, for leather, hide or studded leather only, hardness 5.
4. **Bulette.** `bulette-plate` (rare) gives +3 armour-typed AC and "check penalty two worse".
   The source (Dungeon Denizens Revisited, not Core) has two products from one bulette:
   - bulette plate mail: 65 lb, max Dex +2, hardness 12;
   - bulette **leather**, with "the same statistics as studded leather".
5. **Boiled leather is plain leather armour.** The book's leather armour is already "boiled to
   increase their natural toughness". The catalogue makes Harden a level-4 method that adds
   ×1.25 potency, so ordinary leather armour is made without it.
6. **The Craft skill.** The book files armour under **Craft (armor)**, DC 10 + AC bonus, with
   masterwork a separate DC 20 component (+150 gp). The bench uses `5 + 5 × tier + 2 per
   stage` and its own tool step.
7. **Failure.** The book ruins half the raw materials on a fail by 5 or more and nothing on a
   fail by 4 or less. The bench spends every input on any failure
   (`play/craft_views.py:656`).
8. **Harvest numbers.** The book's numbers:
   - Ultimate Wilderness: DC 15 + CR, Survival for hides, components usable 24 hours.
   - Monster Hunter's Handbook: the creature dead under an hour, parts rot after 2 days.

   The app's: the DC comes from the crafter's own level, the 48-hour clock is never armed, and
   there is no time-since-death check (Inv §0.3).
9. **Hide armour is unreachable.** The book's AC 4 medium suit "made from the tanned skin of
   particularly thickhided beasts" is exactly what a monster hide should make, but the bench
   can only emit `leather` or `studded leather`. Leather lamellar, quilted cloth, wooden armour
   and the madu are missing from `tables.ARMOUR` entirely.
10. **Missing book materials.** Darkleaf cloth and griffon mane (Ultimate Equipment) are absent
    from every catalogue. Bone (primitive material, allowed for studded leather) is absent from
    the leatherworker's shelf.
11. **"Check penalty one worse" and "never reduces max Dex"** (deer, boar, crocodile, monitor
    lizard and seven others) are narrative. The book's own leather traits, such as eel hide's
    ACP and max Dex, are typed gear numbers, so these should be too: the forge's `gear_mod`.
12. **Cuir bouilli and wax** (history, not the book). Harden requires a wax on the bench
    (`rules/leatherworker.py:916`). The conservation dictionary says wax filled the tooled
    hollows to preserve the design; the hardening is done by water and heat on
    vegetable-tanned leather (PA §3.5). So the method's one enforced input is the wrong one.

---

## The owner's answers

### Round 1 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Q1.1 What it is for | **The hunt made wearable** (recommended). |
| Q1.2 Armour model | **One armour model**: the forge's body/fastenings/lining and its crafted-item record (recommended). |
| Q1.3 Who makes the mixed suits | **The owner's own answer: "leatherworking makes the base and the forge uses the base as an item and finishes it."** A leather or hide base (the body) is a finished leatherworker's item that the forge takes as its input and completes (studs, plates, metal fastenings) into studded leather, armoured coat, lamellar and the like. |
| Q1.4 What it makes | **Armour, shields, worn gear, grips, carried goods** (recommended). |

### Round 2 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Q2.1 Methods | **Trim and add**: Flense, Salt, Tan, Curry, Cut, Stitch, Harden, Tool, Dye, Assemble, Grade; Line becomes a piece, Skin becomes the harvest action (recommended). |
| Q2.2 Tanning time | **Real in-world time by tannage**, a tannery vat holding a hide while you adventure; never real-time waiting (recommended). |
| Q2.3 Intermediates | **Each real stage** lands on the shelf, each sellable (recommended). |
| Q2.4 Concentration | **Laminate**: two leathers into one, x1.5, levels cut negatives 10% (recommended). |

### Round 3 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Q3.1 Hide modifiers | **3 armour on every hide; 3 weapon only on grip-capable hides** (recommended). |
| Q3.2 Consumables | **Working traits plus at most one small mark** (recommended). |
| Q3.3 Carried goods | **A book rule where one exists, flavour otherwise** (recommended). |
| Q3.4 Masterwork | **The book wins**: dragonhide, eel hide, angelskin, darkleaf are always masterwork; others at Superior+ (recommended). |

### Round 4 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Q4.1 Skinning | **One harvest per carcass on the book's numbers** (DC 15 + CR, Survival), yield by size, grade from the skinning minigame (recommended). |
| Q4.2 How the beast died | **No effect**: grade from skinning only, the beast sets the tier (recommended). |
| Q4.3 Which creatures | **By the bestiary's type, subtype, size and CR**, never names; named hides win; humanoids never skinned (recommended). |
| Q4.4 Spoilage | **Keep 48 hours, actually start it, salt in the pack stops it** (recommended). |

### Round 5 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Q5.1 One carcass, four crafts | **One "Harvest the carcass" action** listing every part for every craft the character has, each part taken once (recommended). |
| Q5.2 Sentient creatures | **Allowed by the book, marked as a deed**: dragons and the book's named exceptions yes, humanoids never, a good outsider's harvest recorded for renown and alignment (recommended). |
| Q5.3 Yield | **By size, the book's dragonhide ratio** (recommended). |

### Round 6 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Q6.1 Discovery | **Grade, the leather assay**, plus working, teachers, libraries, manuals (recommended). |
| Q6.2 Levels 1-3 | **Field work, then the tannery, then legendary** (recommended). |
| Q6.3 Perks | **The forge's four, Yield moved to skinning** (recommended). |
| Q6.4 Where | **Field kit plus a tannery** (town or founded) (recommended). |

### Round 7 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Q7.1 Worn leather | **As the forge's armour record** (recommended). |
| Q7.2 Dragonhide | **Book first plus a house top-up** (recommended). |
| Q7.3 Druid metal rule | **Yes, and wider: "yes armor and weapons both need a metal tag because there are spells that affect metal."** Both armour and weapons carry a metal tag from their pieces (heat metal, chill metal, rusting grasp, shocking grasp's +3 vs metal armour all read it); the druid's no-metal-armour rule (spells and supernatural abilities lost until 24 h after removing it) is one reader of that tag. |
| Q7.4 Grips | **The leatherworker makes the haft piece** and the forge's Assemble takes it (recommended). |

### Round 8 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Q8.1 Bench | **Its own bench**, built from the herb bench and forge parts (recommended). |
| Q8.2 Minigames | **The grounded set** (flense, tan, harden, stitch, tool, cut, harvest) (recommended). |
| Q8.3 Tuning | **Generous, with Steady mode, bands as numbers and bars as well as colour** (recommended). |
| Q8.4 Old tab | **A "moved" card** when the new bench ships (recommended). |

### Round 9 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Q9.1 Old saves | **Convert** (recommended). |
| Q9.2 World Bible | **The owner's own answer: "apply the tags to the beasts and just have a reader in skinning to find the relevant tag with that no list is necessary."** Creatures carry harvest tags (in the one tag vocabulary) and the skinning reader finds the relevant tag; no separate fauna list in the export. World Bible's creature rows carry the tags. |
| Q9.3 Pacing | **The owner's own answer: "keep both and for all crafts there should be an in progress section where all the crafts sit before they can be collected. they should be displayed in that section with countdown timers that move with game time."** Keep the 48-hour clock and real tanning time, AND a cross-craft "In progress" section (herbalism steeping, tanning, alchemy, enchanting, the forge) where unfinished work sits with countdowns on game time until collected. |
| Q9.4 Licensing | **Mechanics now, names wait** for the bestiary licensing decision (recommended). |

All nine rounds answered (2026-10-05). The plan can be written.

---

## Plan open points (revamp plan §24), answered 2026-10-08

The owner's words are quoted where they changed the plan; "as recommended" means the plan's
proposal stands. These override the plan and the contracts wherever they differ.

| # | Point | Answer |
|---|---|---|
| 1 | Steel lamellar | As recommended: leather lamellar is the leatherworker's whole; the forge's lamellar is **steel lamellar** with the leatherworker's lacing set. |
| 2 | Quality across two crafts | As recommended: the **lower** of the base's tier and the forge's Assemble tier. |
| 3 | Harden at the tannery | **"add a small kettle to the field kit."** The field kit Hardens **common and uncommon** hides (the kit's own tier reach, §10); rare and above still need the tannery's hardening kettle. Plain leather armour is therefore makeable at level 1 in the field. |
| 4 | The craft's level on the harvest roll | **"add leatherworking level to the survival check."** The harvest roll is Survival (or Heal for internal parts) **+ Leatherworker level** + the skinning kit's +2. The DC stays 15 + CR (the "no DC creep" rule is unchanged: the level goes on the roll, never the DC). |
| 5 | How long a carcass waits | As recommended: 24 hours after death. |
| 6 | DR from the stat block | **"add the reduced DR."** A generic hide from a creature with DR N/x gives **DR max(1, N ÷ 5)/x** on a **rare-and-up** hide, capped by the tier ceiling, counted as one of the hide's house modifiers (the energy-resistance rule's shape, §5.4). Only the highest DR is inherited. |
| 7 | Rusting grasp on mixed suits | As recommended: the metal pieces' share of the AC (studded leather loses at most 1). |
| 8 | Salt costs salt | As recommended: one measure per hide unit at the harvest, **and herbalism's animal parts cost salt too**, through the one salt reader. |
| 9 | Which settlements have a tannery | **"every town has a leatherworker and that person does not necessarily have a tannery but every town should have access to leatherworking supplies and the things needed to use the craft."** Every settlement (village, town and city: the owner's "every town" read as every settlement, flagged to the owner 2026-10-08) has a **leatherworker keeper** whose counter sells the craft's supplies: curing salt, tannins, oils, waxes, threads, dyes, a field kit, common hides. A **tannery** (vats, lime pit, hardening kettle for rare-and-up) stays where the settlement's own words imply one, on the outskirts, per the plan. |
| 10 | A dangerous grade | **"dangerous hides should not bite they should force another round of checks to avoid poison, acid or elemental dmg while skinning."** No Grade hazard. Instead, skinning a creature whose body is dangerous (a poison special attack or poisonous flesh, an acid or energy subtype, a breath weapon, a body that burns or shocks to the touch — read from the stat block's tags, never a name list) forces a **second check** during the harvest; a failure deals that creature's hazard: poison through the one poison door (its save and track), acid or energy as damage of that type, small and by the book's scale. |
| 11 | Deeds store | **"Build out a deeds system that tracks good or bad things you do, most actions should only have a small impact, otherwise people will not mean to do certain things and it goes from a funny accident to a source of frustration very quickly if they are punished too heavily. for now just track this as a number positive for good deed and -negative for bad deeds. you should be able to look at this number in your sheet but i dont want it to affect anything yet."** A deeds system of its own (not a leatherworking detail): an append-only record of deeds with a signed value from rule rows (small for most acts), a running total shown on the sheet, read by nothing else yet. Research first (karma and reputation systems, what they tried and abandoned). |
| 12 | Good dragons | As recommended: harvesting a good-aligned dragon (by kind; alignment is not tracked) is a deed too, recorded the same way, with a negative value. |
| 13 | Marks per item | **Owner asked for an explanation before deciding** (2026-10-08). Hold marks until answered: lanes build without them, and the data pass keeps mark rows separable. |
| 14 | Numbers to tune | As recommended: the proposed numbers, all in rule rows, tuned in play. |
