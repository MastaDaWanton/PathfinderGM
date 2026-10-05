# Alchemy revamp: the owner's questions

Step 3 of the alchemy revamp, drafted 2026-10-04. These are the decision rounds the lead
puts to the owner before anything is designed, in the form the herbalism and blacksmithing
rounds used: each question has two to four options, the recommended one first and marked
**(Recommended)**, and one line on what each option leads to. Rounds hold at most four
questions.

Every recommendation is grounded in `docs/alchemy-inventory.md` (cited as **inv §n**) or
`docs/alchemy-prior-art.md` (cited as **art §n**). Rulings already made for herbalism and
the forge are assumed to apply and are **not** asked again:
- the d20 Craft roll decides success;
- one minigame per method climbs the quality tier (Crude to Flawless to +N, ceiling by
  level), always played;
- three levels, then endless levels with two perk picks each;
- real intermediates land on the shelf;
- properties are discovered;
- materials carry complete typed effect documents (no narrative effects), at least three
  discoverable traits each;
- book effects win, with house top-ups;
- one material, many shelves;
- no model authors a number;
- fixes are world-agnostic.

Where alchemy might need an exception to one of those, the question says so.

The book-against-catalogue contradictions found on the way are listed at the end (§11).
They are facts to fix, not questions, except where fixing one forces a choice.

**Urgent, before any round** (a live defect found during the inventory, not a design
question):
- **`basilisk-eye` is the id of both a herb** (`content/ingredients/herbs-and-parts.json`)
  **and an alchemy gland.** `knowledge.resolve("basilisk-eye")` returns the alchemy
  document, because materials are asked first (`rules/knowledge.py:214-218`).
- **The guard is a false claim.** `rules/knowledge.py:17` says the two id spaces are
  disjoint and that `tests/test_alchemist.py` pins it; the test (`:601-617`) compares
  material files with each other, never with herbs.
- **No break in play was found today**, because the herbarium passes the ingredient
  object, not the id. The first caller that passes the id gets the wrong document.
- **The fix belongs in whatever lane touches the shelf first:** rename one of the two, and
  widen the test to herbs (inv §3).

---

## Round 1: what alchemy is for

**Q1.1 Which fun leads?**
1. **Hands-on craft, then discovery, then a way to be seen, as herbalism and the forge
   (Recommended).** The same three in the same order. Alchemy's own flavour is
   *containment*: volatile things handled well.
2. **Discovery first.** The bench is mostly an experiment table, as in Potion Craft's map
   or Skyrim's eating (art §3). The minigames shrink and the codex becomes the game.
3. **Utility first.** Alchemy is mainly a supplier of things the party needs in a fight
   (fire, acid, potions). The bench is quick, and the work happens in play.

**Q1.2 PF1e has three alchemies (inv §6, art §1.3). Which does the world class own?**
1. **Craft (alchemy) items and potions; the class features stay a class's business
   (Recommended).** The world class makes alchemist's fire, antitoxin, tanglefoot bags
   and spell potions and oils. Bombs, mutagens and extracts wait for a PF1e alchemist
   character class, which the app does not have (inv §0.10).
2. **All three.** Bombs and mutagens become world-class products anyone can make. This
   is the furthest from the book: a fighter throws class-feature bombs.
3. **Craft (alchemy) items only.** Potions move to the enchanter, as magic items. That
   breaks the enchanter's potion stand-in (inv §4) unless it moves with them.

**Q1.3 Who may brew a potion that holds a spell?** Today anyone at Alchemist 3 can, with
no spell and no caster level (inv §0.9).
1. **Anyone, through a learned formula: the formula and its reagents stand in for the
   spell (Recommended).** This is the same house rule the enchanter already uses
   ("a potion stands in for knowing the spell"), stated once for both. The gates are the
   formula, the level and the rarity.
2. **The book: Brew Potion needs caster level 3 and the spell prepared and spent (art
   §1.2).** Non-casters cannot brew potions at all, so the enchanter's stand-in would have
   no supplier in a party with no caster.
3. **Anyone, but the spell must be in hand.** A scroll, or a caster in the party,
   provides it and is spent. It keeps the book's shape at the cost of a supply chain.

**Q1.4 Where do the book items' numbers come from?**
1. **The book's numbers win, with house top-ups, as the forge (Recommended).** Alchemist's
   fire is 1d6 plus 1d6 next round with splash, and antitoxin is +5 (art §1.1, §6.2).
   Materials and quality adjust them around that base.
2. **The material sum (today).** The product is whatever its materials add up to.
   Alchemist's fire is 2d6 now, and antitoxin +1 (inv §0.2).
3. **The book's numbers only.** No top-ups, so materials change nothing on a classic
   item. That contradicts "materials carry effects".

---

## Round 2: the boundaries

**Q2.1 Hybrid herbs (63 flagged; 49 herbs carry effects the herb bench drops as
"alchemy only") (inv §0.7).**
1. **Make the door two-way: a hybrid herb is on the alchemy shelf, and alchemy can carry
   its external effects (Recommended).** This is what the contract already promises
   (`campaign-format.md:343`), and it gives the dropped effects a home.
2. **Every herb on the alchemy shelf, not only hybrids.** One shelf, many benches, at its
   widest. The alchemy shelf grows by 161 entries, most of them only medicinal.
3. **Keep it one-way.** Hybrid stays a herbalism flag, and the 49 external effects stay
   unreachable.

**Q2.2 Where do potions end and magic items begin (alchemy and enchanting)?**
1. **Single-use things that are drunk, thrown or poured on (potions, oils, elixirs,
   bombs) are alchemy's; anything that keeps working (wands, scrolls, rings, weapon
   properties) is enchanting's (Recommended).** The enchanter keeps consuming potions as
   stand-ins, which is why the single-use line suits this app better than PF2e's
   magical-or-not line (art §6.1).
2. **The book's line: potions are magic items, made by a caster.** Potions move to
   enchanting, and alchemy is only mundane alchemical goods (art §1.2).
3. **PF2e's line: anything magical is enchanting's** (alchemical items "can't be ...
   affected by *dispel magic*", art §2.1). Potions and oils move; nonmagical elixirs, bombs
   and tools stay.

**Q2.3 Who owns poisons?**
1. **Both crafts, split by route: herbalism the body's own (ingested, on a wound),
   alchemy the ones that reach outside (thrown, inhaled clouds, contact traps)
   (Recommended).** It follows the owner's body-against-outside boundary.
2. **Alchemy owns all poisons.** Herbalism's toxic herbs become alchemy reagents. That
   takes a large part of herbalism away from it.
3. **As today.** Each bench makes whatever its shelf allows. Overlaps stay unresolved.

**Q2.4 Transmutation ("potions, transmutation" is the owner's own word).**
1. **A Transmute method that turns a material into another of the same kind, one band
   rarer, at a cost (two for one, or a catalyst) (Recommended).** WoW's transmutes are
   the model, costed in materials rather than the real-time cooldowns WoW walked back
   (art §3, §6.7). Level 3 work, and the way legendary catalysts finally do something.
2. **Transmutation as product effects only.** Potions that change the drinker (enlarge,
   gaseous form, barkskin). No material ever becomes another.
3. **Both.**

---

## Round 3: methods

**Q3.1 The nine methods. Five have no rule of their own (inv §1).**
1. **Trim and add, as the forge did (Recommended).**
   - **Keep:** Calcine, Dissolve, Distill, Filter, React, Sublime, Bottle.
     - Distill is free again, because herbalism retired it, and it is alchemy's most
       iconic operation (art §5).
     - Bottle is Seal renamed: it picks the vessel, and the vessel decides drink, throw
       or coat. Minecraft's gunpowder and dragon's breath make delivery form a choice
       (art §4, §6.6).
   - **Fold in:**
     - Precipitate becomes the solid end of Dissolve or Filter.
     - Stabilize becomes a **stabilizer ingredient**, as Flux became an ingredient of
       Smelt.
     - Catalyze becomes a **catalyst trait** that is never spent.
   - **Add:** Transmute, if Q2.4 says so.
2. **Keep all nine and give each a rule and a minigame.** Most variety, most to learn,
   and nine games to tune.
3. **Five methods only** (Dissolve, Distill, React, Bottle, Transmute). Fewest games,
   least alchemical texture.

**Q3.2 Volatility.**
1. **Keep it as alchemy's signature and make it real (Recommended).**
   - A failed roll by 5 or more on a volatile step applies the mishap the preview
     already promises, to the alchemist, through the effect system.
   - A minigame miss still only lowers quality.
   - Failure that leaves nothing keeps being removed elsewhere (art §4, §6.5). Here the
     mishap is the cost of a chosen risk, stated in the preview before the roll.
2. **Keep it as a DC surcharge only (today, in effect).** The written stakes stay words.
3. **Drop it.** Alchemy loses the one rule herbalism has no counterpart for.

**Q3.3 Concentration in alchemy.**
1. **Yes, as herbalism's rule: two make one at ×1.5, uncapped, each step harder
   (Recommended).** Distill concentrates liquids and Sublime solids, so depth is a choice
   the player makes. Minecraft's ban on stacking extend with strengthen is the caution
   (art §4).
2. **No concentration.** Strength comes only from materials, quality and perks.
3. **Concentration only through catalysts.** Rare, legendary-gated depth.

**Q3.4 The handler's tax (quicksilver, lead dust).** Today it lands on whoever uses the
product (inv §0.8).
1. **It becomes a working trait (`toxic to handle`): it hurts the alchemist at the bench
   unless a mask, gloves or a fume hood is used (Recommended).** It reaches the product
   only if the effect is meant to be a poison.
2. **Drop the tax.** Quicksilver becomes an ordinary reagent.
3. **Keep it as a product effect.** The drinker pays the alchemist's price, which is
   today's bug.

---

## Round 4: products

**Q4.1 Which product families?**
1. **Potion, oil, splash flask (bomb), cloud (smoke and powder), tool (sunrod,
   tindertwig, smokestick), and salts and spirits as sellable intermediates
   (Recommended).** Each family decides how the thing is used and which effects it can
   carry, as herbalism's product rows do. PF2e's categories are bombs, elixirs, poisons
   and tools (art §2.1).
2. **The same, plus elixirs.** Elixirs are body-only alchemical drinks (PF2e's
   nonmagical liquids, art §2.1). They overlap herbalism's tinctures on the body side of the boundary.
3. **Potion and splash flask only.** Smallest scope; the CRB tools stay shop goods.

**Q4.2 How does a spell potion get made?**
1. **A formula plus reagents that carry the right trait: any reagent with the "lightness"
   trait serves a potion of fly (Recommended).** The model is Witcher 1 and 2's
   substances (Witcher 3 dropped them) and Noita's tag-keyed reactions (art §3, §4). The
   formula is learned (Round 5). Today's 30 effectless "key" materials gain a real job.
2. **The exact recipe (today).** The exact material set and method sequence, and a
   near-miss makes an ordinary preparation.
3. **The formula alone.** Any reagents of the right tier, so materials matter only by
   rarity.

**Q4.3 Which spells may be potions?**
1. **The book's rule: 3rd level or lower, targets a creature, not personal range (art
   §1.2); the five personal-range potions become oils, elixirs or are retired
   (Recommended).** The
   alchemist extract list (408 spells, 273 of levels 1 to 3, in the corpus) can supply
   more later.
2. **Keep the 44 as they are.**
3. **Widen to the whole alchemist extract list at levels 1 to 3.** Many more potions,
   each needing hand-encoded effects.

**Q4.4 What is an alchemical product worth?** Today a potion of haste sells for 60 gp and
costs 1,750 gp of materials; the book price is 750 gp (inv §0.4).
1. **The book's price for book items (CRB alchemical goods, 50 × spell level × caster
   level for potions), the tier ladder for house products, quality multiplying both, and
   material prices checked against them (Recommended).** Book prices are in art §1.1 and
   §1.2.
2. **The tier ladder for everything (today).** Brewing potions keeps losing money.
3. **Book prices only.** House products would need a price rule written for each.

---

## Round 5: discovery

**Q5.1 How does an alchemist learn what a reagent does?**
1. **Assay at the bench (a pinch, 10 minutes, the player's roll), revealing one positive
   and one negative trait, plus study, teachers, libraries and manuals as the other crafts
   (Recommended).** Volatile and toxic materials make the assay dangerous for real, as
   noqual and abysium do at the forge. PF2e's Identify Alchemy is 10 minutes of testing,
   and Oblivion reveals more effects as skill rises (art §2.1, §3, §6.4).
2. **Tasting, as herbalism.** Tasting brimstone or alkahest is either lethal or
   meaningless.
3. **By brewing only.** Effects show when a product carrying them is made, as in Skyrim's
   combining. Slow, but discovery happens at the bench.

**Q5.2 How does an alchemist learn a formula (the recipe for a potion or a classic)?**
1. **Both ways: from a formula book (manuals, teachers, buying formulae), or by
   experiment (Recommended).** When an experiment first makes a known-to-the-world
   formula, it is written down (Guild Wars 2's discovery: "this looks like something").
   Precedents for both routes:
   - Elden Ring's cookbooks, BG3's notes and DOS2's books;
   - Outward, Tears of the Kingdom and Ars Magica's lab text, where making it right
     writes it down (art §2.3, §3, §4).

   The formulae are a fixed table, never secret per world: Minecraft dropped that as "not
   much fun", and Noita's fell to the data files in a week (art §4).
2. **Experiment only.** As Skyrim and Potion Craft.
3. **Books and teachers only.** Nothing is found at the bench (Elden Ring's model).

**Q5.3 How much does the bench hint during an experiment?**
1. **A count of the formulae the current mix could still become, never their names
   (Recommended).** GW2's counter tells you how close you are without spoiling it
   (`docs/herbalism-prior-art.md` §4).
2. **No hints.** Pure trial and error, the Noita and Skyrim end (art §3, §4).
3. **Name the nearest formula.** Fast, and discovery stops being discovery.

**Q5.4 What does a new alchemist already know?**
1. **The common reagents of their homeland's trade, and the four book classics
   (alchemist's fire, acid flask, antitoxin, tanglefoot bag) as formulae (Recommended).**
   As herbalism's homeland rule.
2. **Nothing.** Everything is learned.
3. **Every common reagent and every common formula.**

---

## Round 6: levels, perks and where you work

**Q6.1 Levels 1 to 3: what each opens.**
1. **Level 1:** Dissolve, Calcine, Bottle; common and uncommon; the four book classics.
   **Level 2:** Distill, Filter, React; rare and exotic; spell potions of 1st and 2nd
   level. **Level 3:** Sublime, Transmute; legendary; 3rd-level potions
   **(Recommended).** Same rarity bands as herbalism.
2. **Keep today's five-level table and append endless levels.** It does not match the
   other two crafts.
3. **Potions from level 1.** It cheapens the enchanter's stand-in.

**Q6.2 The endless perks (two picks a level).**
1. **Potency, duration, quality, yield, and Containment (−1 DC a pick on volatile steps,
   and a smaller mishap) (Recommended).** The first four are herbalism's; Containment is
   alchemy's own.
2. **The four herbalism perks only.**
3. **Add a sixth: Formula (learn one formula per pick).**

**Q6.3 Where can alchemy be done?** The fixed tools were "declared and deliberately
unread" until property existed (inv §1); property exists now.
1. **A field kit anywhere for common and uncommon work; a laboratory (a town one rented
   by the hour, or your own) for rare and above and for Distill and Sublime
   (Recommended).** This is the forge's kit-and-smithy rule. The PF1e alchemist's lab
   gives +2 (art §1.1), and Skyrim brews only at a lab (art §3).
2. **Anywhere (today).** The fixed tools stay words.
3. **A laboratory for everything.** No field alchemy.

**Q6.4 What does a quality tier do to a book item?**
1. **Stronger, longer, softer drawbacks, worth more, as herbalism; for a spell potion,
   each tier above Sound adds +1 caster level to the effect (Recommended).** Book potions
   already scale by caster level, and the price follows it (art §1.2). KCD2's four
   potion tiers are the game precedent (art §3).
2. **Herbalism's multipliers only.** Dice and durations scale; caster level stays the
   book minimum.
3. **Price only.** The item does the book's thing at every tier.

---

## Round 7: the materials pass

**Q7.1 How many traits, and of what kind?**
1. **At least three discoverable traits per reagent, at least one a drawback, as two
   layers: product effects and working traits (Recommended).**
   - Product effects are what it puts in the bottle.
   - Working traits are how it behaves at the bench: volatile, toxic to handle,
     corrosive, light-sensitive, slow to dissolve.
   - The forge's split, applied here. The apparatus split in Morrowind and Oblivion
     (positive, negative, both) and Noita's tags are the game precedents (art §3, §4).
2. **Three product effects each, no working layer.** Volatility stays the only working
   rule.
3. **Leave the 75 with no executable effect alone and pass only the rest.**

**Q7.2 How do traits carry from reagent to product (trait inheritance)?**
1. **The product carries the effects of its inputs up to its family's slots (a potion
   three, a flask two), and the player picks which (Recommended).** Atelier's model
   (art §3, §6.3):
   - traits travel through intermediates, so a well-made salt carries its traits into the
     flask;
   - same-named traits add their levels, capped by level;
   - finished goods are dead ends.

   Physick's two tears in one flask are the same cap (art §4).
2. **Only the effects every input shares.** Skyrim's and Oblivion's model (art §3):
   precise, and the combinations become a puzzle.
3. **Everything sums (today).** Effects stack without limit; alchemist's fire becomes
   2d6. Unbounded stacking is on the refuse list (art §7).

**Q7.3 Vessels, solvents, stabilizers and catalysts.**
1. **Working traits only, as the forge's fuels and fluxes; vessels decide the product
   family (Recommended).**
   - A glass vial is drunk, a clay flask thrown, a bladder bursts.
   - A catalyst is never spent.
   - Minecraft's gunpowder and dragon's breath are vessel-like delivery modifiers
     (art §4).
2. **Give them product effects too.** A salamander-glass flask adds fire resistance to
   the drink.
3. **Retire them.** The bench assumes a vessel, and 13 vessels leave the shelf.

**Q7.4 The 40 inert materials and the legendary transformers (inv §3).**
1. **Give each three traits in the pass; prima materia and philosopher's mercury get real
   rules (a wild trait that copies another input's; a catalyst never spent)
   (Recommended).**
2. **Trim the shelf to what has a job.** Fewer, deeper materials, as Angry GM advises.
3. **Leave them as recipe keys.** Only if Q4.2 keeps exact recipes.

---

## Round 8: the engine half (what alchemical items must do in play)

**Q8.1 Throwing a flask.**
1. **A real ranged touch attack through the attack op, with 1 splash damage to everyone
   within 5 feet, and a miss lands at a nearby square (Recommended).** PF1e's splash
   rules (art §1.1). Today the damage lands with no roll (inv §0.3).
2. **An attack roll, no splash.** Simpler, half the book.
3. **As today.** No roll.

**Q8.2 Which effect types must become executable?**
1. **All of these (Recommended):**
   - speed (the branch exists but is gated off: inv §4);
   - senses (darkvision, see invisibility);
   - light (sunrod);
   - an area cloud (smokestick, flash powder);
   - burning next round (alchemist's fire);
   - glued and entangled (tanglefoot);
   - "against X only" damage (holy, sunmetal).

   They go through the forge's periodic executor and item-scoped riders. PF2e's
   persistent damage is the shape for "burns again next round" (art §2.1, §6.2).
2. **Speed and senses only now; the rest later.**
3. **Leave narrative effects narrated.** Breaks "no narrative effects".

**Q8.3 Bought alchemist's fire, antitoxin and sunrod (inert today).**
1. **The same documents as the crafted ones, at Sound quality (Recommended).** One item,
   whether bought or made.
2. **Give the shop items their own book rows.** Two sources of truth.
3. **Leave them inert.**

**Q8.4 Do alchemical bonuses stack?**
1. **No, PF1e's rule: alchemical bonuses of one type take the highest (Recommended, art
   §1.1).**
   That already holds through `bonus_type`. Antitoxin's +5 then matters, and two +1 jars
   do not make +2.
2. **They stack** (house rule). Drinking six potions becomes a strategy.

---

## Round 9: the bench, the stage and the minigames

**Q9.1 Its own bench, or the shared one?**
1. **Its own bench, built from the herb bench's parts, as the forge (Recommended).** It
   opens over the table, and the old `/craft/` Alchemy tab retires when it lands.
2. **The herb bench with an alchemy mode.** Less code; the two crafts look alike.
3. **Keep the old chain bench and add minigames to it.**

**Q9.2 The stage and its mood.**
1. **A field kit on the ground (crucible, spirit lamp, a few vials) and a laboratory
   (alembic, athanor, retort), with procedural 3D glassware where the liquid's colour
   and level are live (Recommended).** The apparatus is the real alchemist's: alembic,
   retort, bain-marie (art §5).
2. **The laboratory only.** Field work shows as a flat panel.
3. **Flat UI only.** No 3D.

**Q9.3 What the minigames are built from.**
1. **Real operations, each a band you stop inside, with skill widening the band
   (Recommended).**
   - Calcine: hold the heat until the calx whitens.
   - Distill: take the heart of the run between the heads and the tails, read by
     temperature.
   - Dissolve: stir until clear.
   - Filter: pour rate.
   - React: add drop by drop, keeping the reaction gauge in its band.
   - Sublime: hold a narrow temperature and scrape the crystal.
   - Bottle: stopper timing.
   - Transmute: the colour stages of the Great Work in order.

   Every gauge is a number and a bar as well as a colour. The bands come from art §5
   and §6.6; start generous, as both earlier sweeps found every crafting minigame was
   softened after launch.
2. **One shared mechanism with different skins.** Less to build, less to learn, and
   less character.
3. **Potion Craft's map as the single game** (art §3). A big build; Potion Craft itself
   reworked its map and ingredients in Early Access, and it moves alchemy to discovery
   first (Q1.1).

**Q9.4 How volatile work looks on the stage.**
1. **A visible reaction gauge (number, bar and colour) that climbs while you work, and a
   real flare on a failed roll; reduced motion respected (Recommended).**
2. **No special treatment.** Volatile work looks like any other step.

---

## Round 10: old saves

**Q10.1 Convert, as herbalism and the forge did?**
1. **Convert (Recommended).**
   - Alchemist levels above 3 become endless levels, with perks picked on first load.
   - Old products stay usable and sellable, marked as old work.
   - Old chain recipes are dropped with a note.
2. **Convert, and reset the level to the new table.** Simpler to build and harsher on the
   player.
3. **Keep both systems.** Old saves stay on the old bench.

**Q10.2 Old spell potions and the enchanter.**
1. **Keep every potion id and `holds_spell` exactly, so a stored potion still stands in
   for its spell (Recommended).** Pinned today by `tests/test_magicitem.py:207`.
2. **Re-derive old potions under the new rules on load.** Their strength may change.

---

## 11. Book against catalogue: contradictions found

Facts for the materials pass, from inv §0 and art §1.1-§1.2 (rule text cited there):

1. **Alchemist's fire.**
   - Book: 1d6 fire, then 1d6 the next round, a ranged touch attack, 1 splash.
   - Catalogue: 2d6 fire at once, no attack roll, no splash, no second round.
   - Book Craft DC 20 against the bench's 24.
2. **Antitoxin.** Book +5 alchemical on Fortitude against poison for an hour. Catalogue:
   two +1 alchemical bonuses, which do not stack, so +1.
3. **Sunrod.** Book: struck, it lights 30 ft for 6 hours (Craft DC 25). Catalogue chain: a
   blade coating that deals 1d4 fire.
4. **Smokestick.** Book: lit, it fills a 10-ft cube with smoke for 1 minute (Craft DC 20).
   Catalogue: drinkable, and the smoke is narration.
5. **Liquid ice and itching powder.** The recipe table has no vessel, so both come out as
   blade coatings.
6. **Antiplague.** The recipe table's chain is refused by its own Filter rule.
7. **Tanglefoot bag.** The book: a hit entangles (−2 attack, −4 Dex), and a failed DC 15
   Reflex save also glues the target to the floor (DC 17 Strength or 15 slashing to break
   free); Craft DC 25. The catalogue gives two entangles, the pitch's unconditional and
   the mucus's behind the save, and no glue.
8. **Potions of personal-range spells.** Longstrider, expeditious retreat, comprehend
   languages, see invisibility and false life cannot be potions by the book.
9. **Potion prices.** Tier-priced at 6 to 60 gp against the book's 50 × spell level ×
   caster level.
10. **Brew Potion.** Needs caster level 3 and the spell in the book; the bench asks for
    neither.
11. **Handler effects.** Quicksilver and lead dust tax whoever uses the product.
12. **Restricted damage.** Sunmetal filings and saint's tallow hurt the living; their
    "undead only" sits in an unread note.
13. **The weapon table's "Alchemist's fire"** is siege ammunition (200 gp, 10 lb, two
    hands), not the CRB splash weapon.
14. **`docs/alchemy.md`** counts 116 and then 137 materials; there are 139.
15. **`campaign-format.md:343`** promises hybrid herbs on the alchemist's shelf; they are
    not there.
16. **`rules/knowledge.py:17`** says herb and material ids are disjoint and that a test
    pins it. `basilisk-eye` is both, and the test checks material files only.

---

## The owner's answers

### Round 1 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Q1.1 Which fun leads | **Hands-on craft, then discovery, then a way to be seen** (recommended). Alchemy's flavour: containment. |
| Q1.2 Which alchemies | **Craft (alchemy) items and potions**; bombs, mutagens and extracts wait for a PF1e alchemist class (recommended). |
| Q1.3 Who brews spell potions | **Anyone, through a learned formula**: formula and reagents stand in for the spell, as the enchanter's rule (recommended). |
| Q1.4 Where the numbers come from | **The book's numbers win, with house top-ups**, as the forge (recommended). |

### Round 2 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Q2.1 Hybrid herbs | **Make the door two-way**: hybrid herbs sit on the alchemy shelf and alchemy carries their external effects (recommended). |
| Q2.2 Potions vs magic items | **Single-use is alchemy's** (potions, oils, elixirs, bombs); anything that keeps working is enchanting's (recommended). |
| Q2.3 Poisons | **Split by route**: herbalism the body's own, alchemy the ones that reach outside (recommended). |
| Q2.4 Transmutation | **A Transmute method**: a material to another of its kind, one band rarer, at a cost; level 3 (recommended). |

### Round 3 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Q3.1 Methods | **Trim and add**: Calcine, Dissolve, Distill, Filter, React, Sublime, Bottle; Precipitate folds in, Stabilize becomes an ingredient, Catalyze a catalyst trait; add Transmute (recommended). |
| Q3.2 Volatility | **Make it real**: a 5+ fail on a volatile step applies the promised mishap to the alchemist, stated before the roll (recommended). |
| Q3.3 Concentration | **As herbalism's**: two make one at x1.5, uncapped, each step harder (recommended). |
| Q3.4 Handler's tax | **Toxic to handle**: a working trait that hurts the alchemist at the bench unless protected (recommended). |

### Round 4 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Q4.1 Product families | **Six families**: potion, oil, splash flask (bomb), cloud (smoke and powder), tool (sunrod, tindertwig, smokestick), and salts and spirits as sellable intermediates (recommended). |
| Q4.2 Spell potions | **A formula plus reagents that carry the right trait** (recommended). |
| Q4.3 Which spells | **The owner's own rule: "I want potions to hold any spell and the max spell level should be 1/2 alchemy level with a minimum of 1. I understand that this allows personal range spells to become ranged, i am okay with this."** So: any spell, including personal range (it then works on whoever drinks it); highest spell level = max(1, floor(Alchemist level / 2)), which the endless levels carry to 9th at Alchemist 18. The book's 3rd-level cap and personal-range ban are deliberately overruled. Open for the plan: the caster level a potion is priced and resolved at (the book's minimum caster level for the spell level is the natural default). |
| Q4.4 Prices | **Book prices for book items**, the tier ladder for house products, quality multiplying both, material prices checked against them (recommended). |

### Round 5 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Q5.1 Learning reagents | **Assay at the bench plus the herb routes**; volatile/toxic assays are dangerous for real (recommended). |
| Q5.2 Learning formulae | **Books and experiment**; a fixed table, never secret per world (recommended). |
| Q5.3 Hints | **A count of possible formulae, never their names** (recommended). |
| Q5.4 Starting knowledge | **Homeland reagents and the four book classics** as formulae (recommended). |

### Round 6 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Q6.1 Levels 1-3 | **Classics, then distilling, then transmuting** (asked reworded to fit the owner's Q4.3 potion rule): L1 Dissolve, Calcine, Bottle, common/uncommon, the four classics, 1st-level potions; L2 Distill, Filter, React, rare/exotic; L3 Sublime, Transmute, legendary. Spell level grows by the Q4.3 rule. |
| Q6.2 Perks | **Herbalism's four plus Containment** (-1 DC a pick on volatile steps, a smaller mishap) (recommended). |
| Q6.3 Where | **Field kit plus a laboratory** (town by the hour, or owned) for rare+ and for Distill and Sublime (recommended). |
| Q6.4 Quality on book items | **Stronger, longer, softer drawbacks, worth more; each tier above Sound adds +1 caster level** to a spell potion (recommended). |
