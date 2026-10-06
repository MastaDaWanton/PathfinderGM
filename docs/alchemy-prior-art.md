# Alchemy revamp: prior art sweep

Research for the Alchemist world-class revamp in Pathfinder GM, step 2 of the same three
steps herbalism and the forge took (inventory, prior art, the owner's questions). The
inventory it answers is `docs/alchemy-inventory.md`; the questions it feeds are
`docs/alchemy-questions.md`.

Compiled 2026-10-04. Same conventions as `docs/herbalism-prior-art.md` and
`docs/blacksmithing-prior-art.md`:
- **[P]** primary: rulebook text through Archives of Nethys or Paizo's PRD, open-licensed
  rulebook text, developer posts, official patch notes and manuals, interviews.
- **[W]** officially partnered wikis (UESP, the official Minecraft wiki).
- **[S]** secondary: fan wikis, press, forums, mod pages.

Anything that could not be traced to a source is in the critic pass at the end (§8).
Findings already established in the two earlier sweeps are cited there and not repeated.
That covers Potion Craft's Auto Hold and haggle rework, KCD1's Routine against KCD2's
missing autobrew, Skyrim's eat-to-learn, WoW's Inspiration giving way to Concentration,
and Atelier's simplification interviews.

---

## 0. The headline findings

1. **PF1e has three alchemies, and the app's world class blurs two of them and lacks the
   third.**
   - Craft (alchemy) items are nonmagical, anyone with the skill makes them, and they cost
     a third of the price.
   - Potions come from Brew Potion: caster level 3, the spell prepared and spent, half the
     price.
   - Extracts, bombs and mutagens are the class's personal daily alchemy, inert in other
     hands.

   PF2e draws the alchemy/magic line in one sentence: alchemical items "can't be dismissed
   or affected by *dispel magic*", and a potion is "a magical liquid" (§1, §2.1).
2. **The book confirms the inventory's contradictions.**
   - A potion's price is 50 gp × spell level × caster level.
   - "Spells with a range of personal cannot be made into potions."
   - Alchemist's fire is 1d6, then 1d6 the next round, plus 1 splash, at Craft DC 20.
   - Antitoxin is +5, at DC 25.

   Every one of these differs from what the bench makes today (§1.1-§1.2).
3. **Atelier is the prior art for traits carried through intermediates** (§3).
   - Ryza passes traits through intermediates even while inactive and makes finished
     goods "DEAD ENDS".
   - Sophie combines listed pairs into higher traits, and Ryza adds same-named levels.
   - When Yumia took traits out of synthesis, players called it shallow.
4. **Secret per-world recipes were tried and dropped, or solved.** Minecraft abandoned
   per-world brewing because it "didn't turn out to be much fun". Noita's per-seed recipes
   were pulled from the files in about a week (§4). What lasts is a fixed table you learn,
   with reactions keyed on tags (Noita), which suits the app's tag law.
5. **Failure that leaves nothing keeps being removed.**
   - Monster Hunter went from 55% combination rates and "Garbage" to 100% from World on.
   - Outward's players wrote a mod so failed alchemy stops eating ingredients.
   - Morrowind's failed brews are gone from Oblivion and Skyrim.

   Randomness moves toward choice: WoW's Concentration, the Artificer's chosen elixirs,
   and the PF2e remaster's end of "complex decisions based on guesswork" (§4, §2.1, §2.2).
6. **Delivery form is a modifier, not an inference.** Minecraft turns a drink into a
   splash with gunpowder and into a lingering cloud with dragon's breath. A fermented spider
   eye inverts an effect, and 1.9 banned stacking extend and strengthen (§4). The bench
   today infers drink, throw or coat from what happens to be in the vessel, which is how a
   sunrod became a blade coating.
7. **Real alchemy gives honest minigame bands** (§5):
   - distillation's heads, hearts and tails by temperature and smell;
   - calcination to a white calx;
   - sal ammoniac's crust re-forming above;
   - mercury "fixed" by sulphur, turning yellow;
   - the colour stages nigredo, albedo, citrinitas, rubedo, which Potion Craft already
     uses for its legendary chain (§3).

---

## 1. PF1e: three alchemies, not one

### 1.1 Craft (alchemy) items (Core Rulebook)

**The procedure** [P] https://www.aonprd.com/Skills.aspx?ItemName=Craft
- **Raw materials:** pay one third of the price.
- **Weekly progress:** on a success, check result × DC in silver pieces; daily checks are
  a seventh of that.
- **Failure:** miss by 4 or less and nothing is made; miss by 5 or more and half the raw
  materials are ruined.
- **Lab:** an alchemist's lab gives a +2 circumstance bonus on Craft (alchemy).
- **Who may craft:** no spellcaster requirement appears. 3.5 had one ("You must be a
  spellcaster to craft any of these items", [S] https://dndtools.net/skills/craft/), and
  PF1e dropped it.

**The items, with their DCs and effects** [P] https://legacy.aonprd.com/coreRulebook/equipment.html;
alchemist's fire also checked at [P] https://www.aonprd.com/EquipmentMiscDisplay.aspx?ItemName=Alchemist%27s+fire

| Item | Craft DC | Price | Effect |
|---|---|---|---|
| Acid | 15 | 10 gp | splash weapon: 1d6 acid on a direct hit, 1 acid to everyone within 5 ft |
| Alchemist's fire | 20 | 20 gp | splash weapon, 10-ft range increment: 1d6 fire and 1 splash; another 1d6 the next round unless put out (a full-round action, DC 15 Reflex) |
| Smokestick | 20 | 20 gp | lit, burns 1 round, then fills a 10-ft cube with opaque smoke for 1 minute |
| Tindertwig | 20 | 1 gp | lights a torch as a standard action |
| Antitoxin | 25 | 50 gp | "+5 alchemical bonus on Fortitude saving throws against poison for 1 hour" |
| Sunrod | 25 | 2 gp | normal light 30 ft, plus one step brighter a further 30 ft, for 6 hours |
| Tanglefoot bag | 25 | 50 gp | thrown: the target is entangled (−2 attack, −4 Dex); DC 15 Reflex or "glued to the floor"; break free with DC 17 Strength or 15 slashing damage |
| Thunderstone | 25 | 30 gp | 10-ft radius: DC 15 Fortitude or "deafened for 1 hour" |

Holy water (25 gp, 2d4 to undead and evil outsiders) and the everburning torch are not
Craft (alchemy) items.

**Alchemical remedies** (Ultimate Equipment) are "used to overcome a negative condition":
- antiplague, DC 25;
- smelling salts, DC 25;
- soothe syrup, DC 15;
- troll oil, DC 30;
- blood-clotter salve, DC 20.

[P] https://aonprd.com/EquipmentMisc.aspx?Category=AlchemicalRemedies

**Stacking.** An alchemical bonus comes from "a non-magical, alchemical substance such as
antitoxin". Bonuses of one type do not stack; the highest applies.
[S] https://www.d20pfsrd.com/basics-ability-scores/glossary/ (the general bonus-stacking
rule is Core).

**Alchemy Manual (Player Companion, 2014)** [P] https://aonprd.com/AlchemicalReagents.aspx
- **Reagents:** 20 named reagents (brimstone, quicksilver, salt, saltpeter, mugwort
  extract, spirit of wine and others), each "purified through long processes from their
  raw states."
- **Power components:** a reagent can also be spent as an *alchemical power component*
  that boosts a spell. Salt gives +1 caster level for necromancy; brimstone +1 damage on
  acid spells.
- **Stacking:** "Reagents do not stack with either themselves or one another."
- **Recipes:** every item gets one, as reagents plus a process plus tools plus time. For
  alchemist's fire: "(12 magnesium + 22 spirit of wine)/congelation, Time: 10 minutes,
  Tools: Alchemist's lab". [P] the AoN alchemist's fire page above.
- **Reception:** a review calls the "spontaneous alchemy" route faster but "more
  expensive", "not a way to run a profitable business", with a mishap on a failure by 5
  or more. [S] https://www.ofdiceandpen.ca/2014/05/alchemy-manual.html

### 1.2 Brew Potion and the potion rules

**The feat** [P] https://legacy.aonprd.com/coreRulebook/feats.html
- **Prerequisite:** caster level 3rd.
- **Which spells:** "You can create a potion of any 3rd-level or lower spell that you know
  and that targets one or more creatures or objects."
- **Time:** "2 hours if its base price is 250 gp or less, otherwise … 1 day for each 1,000
  gp in its base price."
- **Cost:** raw materials of "one half this base price."

**The potion rules** [P] https://legacy.aonprd.com/coreRulebook/magicItems/potions.html
- **Spell limits:** up to 3rd level, a casting time under 1 minute, and the spell must
  target one or more creatures or objects.
- **Price:** "The price of a potion is equal to the level of the spell × the creator's
  caster level × 50 gp." A 0-level spell counts as half a level (25 gp).
- **Who casts:** the drinker is both the target and the caster.
- **Oils:** "similar to potions, except that oils are applied externally rather than
  imbibed."

**Creating potions** [P] https://legacy.aonprd.com/coreRulebook/magicItems/magicItemCreation.html
- **Personal range is barred:** "Spells with a range of personal cannot be made into
  potions."
- **Preparation:** "The creator must have prepared the spell to be placed in the potion (or
  must know the spell, in the case of a sorcerer or bard)."
- **The slot is spent:** "The act of brewing triggers the prepared spell."
- **Time:** "Brewing a potion requires 1 day." **This contradicts the feat's 2-hour rule.**
  The 3.5 rule was one day a potion plus an XP cost
  ([S] https://dndtools.net/feats/players-handbook-v35--6/brew-potion--274/); PF1e changed
  the feat and left the old line in the creation section.
- **The check:** "The DC to create a magic item is 5 + the caster level for the item",
  using Spellcraft or Craft (alchemy). Each missing prerequisite adds +5. Failing by 5 or
  more makes a cursed item.

**The alchemist class brews potions of its extracts** with Brew Potion as a bonus feat,
"using his alchemist level as his caster level. The spell must be one that can be made
into a potion." [P] the APG alchemist page in §1.3. So the personal-range ban applies to
extracts too, and the Infusion discovery is the class's way round it.

### 1.3 The alchemist class (Advanced Player's Guide)

[P] https://legacy.aonprd.com/advancedPlayersGuide/baseClasses/alchemist.html

**Alchemy (class feature):** class level as a competence bonus on Craft (alchemy) to make
alchemical items, and identifying a potion by holding it for 1 round.

**Extracts:**
- "The alchemist doesn't actually cast spells." Extracts come from a formula book of
  formulae.
- An extract is drunk and "always affects only the drinking alchemist."
- An extract "immediately becomes inert if it leaves the alchemist's possession"; the
  Infusion discovery lets others drink one.
- The formula book gains a formula a level, and copies from scrolls and spellbooks at the
  wizard's costs.

**Bombs:**
- class level + Int modifier a day;
- 1d6 fire + Int, plus 1d6 at every odd level;
- splash equal to the minimum damage;
- inert if not thrown in the round it is made.

**Mutagen:** +4 alchemical to one physical ability, +2 natural armour, −2 to a mental
ability, 10 minutes a level. It takes an hour to brew, only one dose exists at a time, and
a non-alchemist who drinks it makes a Fortitude save or is nauseated. The cognatogen
(Ultimate Magic) is the mental mirror.

**Other features:** Throw Anything and Brew Potion as bonus feats; Swift Alchemy (half
time); Instant Alchemy (a full-round action).

**The gp-for-sp speed-up is not a class feature.** It is the **Master Alchemist** feat:
"use the item's gp value as its sp value when determining your progress."
[P] https://www.aonprd.com/FeatDisplay.aspx?ItemName=Master%20Alchemist

**So PF1e has three channels, each with a hard edge:**

| Channel | Magic? | Who | Cost | Who can use it |
|---|---|---|---|---|
| Craft (alchemy) items | no | anyone with the skill | ⅓ price, slow | anyone |
| Brew Potion | yes | caster level 3, the spell prepared and spent | ½ price | anyone |
| Extracts, bombs, mutagens | supernatural, daily | the class | free | the alchemist only |

### 1.4 Pathfinder Unchained alternate crafting

[P] https://legacy.aonprd.com/unchained/skillsAndOptions/craftingAndProfession.html

Written because the core rule's "complex multiplication" took "an unreasonably long time
to create relatively simple items." Fixed difficulty steps with fixed daily progress:

| Step | DC | Progress per day | Alchemy items |
|---|---|---|---|
| Normal | 15 | 2 gp | acid |
| Complex | 20 | 4 gp | alchemist's fire, smokestick, tindertwig |
| Intricate | 25 | 8 gp | antitoxin, sunrod, tanglefoot bag, thunderstone |
| Very intricate | 30 | 16 gp | tangleburn bag, troll oil |

- **Margin ladder:** beating the DC by 5 doubles progress, by 10 triples it, by 15
  quadruples it. That is a ladder like Ultimate Wilderness herbalism's
  (`docs/herbalism-prior-art.md` §3).
- **Raw materials:** "1/4 the cost" (checked on the page), not core's one third.

---

## 2. Other tabletop systems

### 2.1 Pathfinder 2e: potions are magic, elixirs are not

**The boundary** [P] https://2e.aonprd.com/Rules.aspx?ID=3180 ; https://2e.aonprd.com/Traits.aspx?ID=672
- **Alchemical items** run on reagents, "don't radiate magical auras, and they can't be
  dismissed or affected by *dispel magic*." Categories: bombs, elixirs, poisons, tools.
- **A potion** is "a magical liquid" with the potion trait; an elixir is alchemical.
- This is the cleanest rules line between alchemy and magic in any system found: magical
  or not, and *dispel* applies or it does not.

**Grades.** Alchemist's fire runs from lesser (level 1, 3 gp, 1d8 + 1 persistent fire + 1
splash) to major (level 17, 4d8/4/4), with item bonuses to hit.
[P] https://2e.aonprd.com/Equipment.aspx?ID=3287 . Persistent damage is PF2e's rule for
the "burns again next round" shape.

**Crafting.**
- Craft needs a formula; setup is shorter with one.
- Consumables are made in batches of up to four, and a critical failure costs 10% of the
  materials. [P] https://2e.aonprd.com/Actions.aspx?ID=2385
- The Alchemical Crafting feat adds four common formulae.
  [P] https://2e.aonprd.com/Feats.aspx?ID=752
- Identify Alchemy is 10 minutes of testing.
  [P] https://2e.aonprd.com/Actions.aspx?ID=44&NoRedirect=1

**The alchemist, 2019 → 2020 errata → 2024 remaster.**
- **2019:** a daily pool of infused reagents (level + Int batches); Advanced Alchemy made
  two items a batch; Quick Alchemy spent a batch for one item.
  [P] https://2e.aonprd.com/Classes.aspx?ID=1&NoRedirect=1
- **2020 errata:** a scaling item DC without a feat.
  [S] https://www.enworld.org/threads/pathfinder-2e-errata-2e.676339/
- **Remaster (Player Core 2, 2024):** reagents are gone. Advanced Alchemy makes "up to 4 +
  your Intelligence modifier" items at daily preparation. *Versatile vials* (2 + Int) can
  be thrown as acid bombs or turned into any known item by Quick Alchemy, and two refill
  every 10 minutes of exploration. Research fields are bomber, chirurgeon, mutagenist and
  toxicologist. [P] https://2e.aonprd.com/Classes.aspx?ID=56
- **Paizo's stated reason** (Jason Keeley): the old pool created "very complex decisions
  based on guesswork, which often ended up disappointing."
  [P] https://paizo.com/blog/player-core-2-preview-the-alchemist-remastered
- **What players had complained of** [S] https://paizo.com/threads/rzs43c9t: bombs ran out
  after two encounters at 1st level, accuracy was poor, and the class needed
  "significantly more homework than every other class."

### 2.2 D&D 5e

- **2014:** herbalism kit proficiency is required to make antitoxin and potions of healing.
  [S] https://roll20.net/compendium/dnd5e/Herbalism%20Kit . Xanathar's potion-of-healing
  timetable (1 day and 25 gp up to 4 workweeks and 10,000 gp for supreme) is [S] only.
- **2024 PHB:** each tool has a crafting list; materials cost half; progress is 10 GP a
  day, double the old 5. The herbalism kit makes potions of healing (25 GP, 1 day);
  alchemist's supplies make alchemist's fire.
  [P] https://www.dndbeyond.com/posts/1788-lets-explore-the-crafting-rules-in-the-2024
- **2024 DMG:** magic items need Arcana plus the item's tool, and a spell the item casts
  must be prepared on each crafting day.
  [P] https://www.dndbeyond.com/posts/1836-help-your-players-get-crafty-with-the-2024-dungeon
- **Artificer Alchemist:**
  - Tasha's gives a random elixir (d6) each long rest, and the chosen effect only when a
    spell slot is spent. [S] https://dnd5e.wikidot.com/artificer:alchemist
  - The 2025 revision lets the player choose more of them.
    [S] https://dnd2024.wikidot.com/artificer:alchemist

  That is a move from random toward chosen.

### 2.3 Ars Magica 5e: the lab text

[P] open-licensed text, https://www.redcap.org/page/Ars_Magica_5E_Standard_Edition,_Chapter_Eight:_Laboratory
- **Lab total:** Technique + Form + Intelligence + Magic Theory + aura.
- **A discovery writes a lab text**, and anyone whose lab total meets its level "may
  reproduce it in a single season." The author's own notes are personal shorthand; a text
  others can read is a separate writing job.
- **Experimentation** adds a die and a risk modifier and rolls on an Extraordinary Results
  table.
- **Art & Academe's experimental philosophy** is a natural magic that works "solely
  through the intrinsic power" of its materials, through "hidden virtues"
  ([P] https://redcap.org/page/Art_&_Academe_Open_Content). That is "properties are
  discovered", stated as a tabletop rule.

### 2.4 Discovering reagent properties at the table

No tabletop system found makes reagent discovery a mechanic:
- **PF1e's Alchemy Manual** lists reagent properties openly.
- **PF2e** identifies finished items only.
- **Ars Magica** comes closest: discover, record, reproduce, teach.
- **Witcher-style substance slots** (any ingredient carrying the substance fills the slot)
  are sourced for the video games only.

---

## 3. Video games: the alchemy benches

### Potion Craft: Alchemist Simulator (niceplay games)

Steam news is cited by gid, because the API's dates for old posts are up to a year off.
All [P] posts come from
https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=1210320&count=100&maxlength=0&feeds=steam_community_announcements

- **The map.** Each ingredient draws a path on a 2D map, and the path shows before the
  ingredient goes in. What you discover is where effects **sit** on the map, not what an
  ingredient does. Each effect has rings for tiers I, II and III: "The closer the player
  can match the potion bottle icon with the recipe bottle image on the map, the stronger
  the potion." [S] https://gamerant.com/potion-craft-make-stronger-potions/
- **Salts are dosed by the pinch** (Devlog #1, gid 4703417046210936996, [P]): "Sometimes it
  will be enough to add just one pinch." Sun Salt and Moon Salt rotate the bottle, so
  fractional dosing is the precision tool.
- **The ingredient system was reworked in Early Access** (Devlog #16, gid
  4292505348840249843, [P]):
  - Before: each element was tied to a direction (Water right, Fire left).
  - After: 8 elements, 58 ingredients, and "iridescent" ingredients that move any way.
- **The map was reworked too** (Devlog #17, gid 4474904295781250797, [P]):
  - swamps slow the bottle;
  - healing zones replace automatic recovery on some maps;
  - some danger zones were made less deadly;
  - maps got borders because "the alchemical potential of water, oil or wine is not
    infinite".
- **Softened after launch** (in addition to Auto Hold and the haggle rework from the
  herbalism sweep):
  - v1.1 brews straight from the Recipe Book (gid 5395938616813249245);
  - the "Enchanted Garden 2.0" update made legendary recipes saveable with "rebalancing to
    reduce tediousness" (gid 1785321795645620);
  - 2.0.2 removed customer requests that could not be met ("sometimes they asked for
    impossible potions") (gid 1803527891514530).
- **The legendary chain is the colour stages.** The Alchemy Machine's legendary recipes are
  Nigredo, Albedo, Citrinitas, Rubedo and the Philosopher's Stone (2.0 notes).
- **Correction to the earlier sweep's framing:** 2.0 was a garden, talents and difficulty
  update, not an alchemy-map overhaul. The map changed in Early Access.

### Kingdom Come: Deliverance 1 and 2 (Warhorse)

- **Both games** follow a recipe by hand: base liquid, grind, add in order, heat, time the
  boil with the hourglass, distil. You can brew without owning the recipe if you know the
  steps. [S] https://kingdomcomedeliverance.wiki.gg/wiki/Alchemy ;
  https://scalacube.com/blog/kingdom-come-deliverance-2/alchemy-explained-in-kingdom-come-deliverance-2
- **KCD1 has no quality tiers.** A perfect brew gives the full count, and "failing steps
  progressively reduces the number of potions." [S] wiki.gg
- **KCD2 has four tiers.** Weak, standard, Strong and Henry's; Aesop's bonus runs +3, +3,
  +5, +7. Henry's needs the level-16 perk and a perfect run, and a fresh herb raises
  quality. [S] https://kingdomcomedeliverance2.wiki.fextralife.com/Potions ;
  https://kingdomcomedeliverance2.wiki.fextralife.com/Alchemy
- **KCD2 makes forgiveness and quantity rival perks** (Secret of Equilibrium against Secret
  of Matter). [S] scalacube
- **KCD2's patches never softened the brewing game itself**; the alchemy notes are fixes
  and logistics. [S] https://kingdomcomedeliverance2.wiki.fextralife.com/Patch_Notes
- **No Warhorse statement** on why alchemy is manual was found.

### Morrowind, Oblivion, Skyrim (Bethesda)

All [W], UESP.
- **Morrowind** https://en.uesp.net/wiki/Morrowind:Alchemy
  - Up to 4 ingredients of 4 effects each; how many you see depends on skill.
  - Hidden effects still fire if two ingredients share them.
  - Brewing can fail and waste the ingredients.
  - The apparatus split: the alembic "reduces the strength and duration of all negative
    effects", the retort boosts the positive, the calcinator both.
- **Oblivion** https://en.uesp.net/wiki/Oblivion:Alchemy
  - An effect appears "if you are combining more than one ingredient with that effect."
  - You see one effect in four at Novice and all four at Expert, and a Master brews from
    one ingredient.
  - The same apparatus split as Morrowind; a Novice alembic can make side effects worse.
  - Positive and negative effects can share a potion, and the drinker takes both.
- **Skyrim** https://en.uesp.net/wiki/Skyrim:Alchemy
  - "Combine two or three ingredients which share a magical effect", at a lab only.
  - Eating reveals the first effect, and the Experimenter perk more.
  - **Purity**: "All negative effects are removed from created potions." That is the
    clean precedent for Filter, as a perk.
- **The Fortify Restoration loop** is unfixed in the base game per UESP, and fixed by the
  Unofficial Patch. [W] https://en.uesp.net/wiki/Skyrim:Fortify_Restoration

### The Witcher 1, 2 and 3 (CD Projekt Red)

- **Witcher 1 and 2: recipes call for substances, so any carrier serves.** The Witcher 2
  REDkit wiki lists nine substances, among them Caelum, Sol and Fulgur. [P-ish, CDPR's
  REDkit wiki] https://redkitwiki.cdprojektred.com/potions+and+recipes.htm
- **Witcher 3 dropped substitution.** Substances became ingredient items of their own.
  [S] https://thewitcher3.wiki.fextralife.com/Substances
- **Witcher 3 tiers take the lower potion as an ingredient.** Enhanced Swallow needs
  "Swallow x 1" plus herbs: an intermediate feeding the next tier. [S]
  https://thewitcher3.wiki.fextralife.com/Enhanced+Swallow
- **Why it changed.** CDPR, relayed from a forum Q&A: "With the open world it quickly
  became a pain to go really far to grab that one plant." The goal was "to get rid of
  pointless repetitions whilst keeping the preparation aspect." [S]
  https://www.criticalhit.net/gaming/alchemy-is-different-and-better-in-the-witcher-3/
- **Patches** [P] Steam news, appid 292030:
  - 1.07: "All crafting components and alchemy ingredients now weigh nothing."
  - 1.10: "potions and bombs can no longer be sold."

### Atelier (Gust): the closest prior art for traits carried through intermediates

All [S] unless marked.
- **Escha & Logy:** each ingredient adds fire, water, wind and earth power to the recipe
  within a cost budget, and you pick up to 3 traits.
  https://moegamer.net/2021/02/19/atelier-escha-logy-alchemists-of-the-dusk-sky-a-question-of-technique/
- **Sophie** https://eruciform.com/games/atelier/atelier-sophie/atelier-sophie-guide/
  - Trait slots open at Alchemy 10, 20 and 30.
  - Listed pairs combine into a stronger trait ("Critical and Critical+" become Critical
    Finish).
  - Players combine on intermediates and carry quality forward through catalysts built to
    999 quality.
- **Sophie 2:** "Two traits will combine into one higher-order trait if they are
  compatible." https://en.wikipedia.org/wiki/Atelier_Sophie_2:_The_Alchemist_of_the_Mysterious_Dream
- **Ryza** https://eruciform.com/games/atelier/atelier-ryza/atelier-ryza-guide/
  - Traits always transfer if they fit the item type, and pass through intermediates even
    while inactive: "Any traits you dump in at any level will be available at the end."
  - "There is NO trait-combining": same-named traits add levels ("Critical Lv 2 and a
    Critical Lv 5 will yield a Critical Lv 7").
  - Finished weapons, armour and usable items are "DEAD ENDS": nothing comes back out.
- **Ryza 2** grades trait families: Quality +15%, Quality+ +30%, Quality++ +50%.
  https://barrelwisdom.com/ryza2/traits/
- **Yumia (2025) took traits out of synthesis.** Hosoi: "you can add the trait after."
  [P, interview] https://lootlevelchill.com/features/atelier-yumia-interview-junzo-hosoi/
  Traits are now found and socketed. Players objected that "Even Ryza 3's system had far
  more going on." [S] https://steamcommunity.com/app/3123410/discussions/0/565870386383722294/
  Gust's first patch added a skip for the synthesis animation. [P]
  https://atelier.games/yumia/us/topics/20250325.html

### Baldur's Gate 3 (Larian)

All [S] https://bg3.wiki/wiki/Alchemy
- Raw ingredients are **extracted into named intermediates** (salts, essences, ashes,
  vitriols, sublimates, suspensions), which combine into potions, grenades and coatings.
- Recipes unlock by extracting, by collecting ingredients, and by "reading certain books or
  notes". No roll or skill affects the result.
- The later patches touched only the interface.

### World of Warcraft alchemy (Blizzard)

All [S].
- **Transmute: Arcanite's 23-hour cooldown was removed in 2.4.0**, which flooded supply.
  https://warcraft.wiki.gg/wiki/Transmute:_Arcanite
- **Transmutation Master** (2.0.3) gave extra output by chance procs.
  https://warcraft.wiki.gg/wiki/Transmutation_Master
- **Dragonflight transmutes ran on charges** (one a day, bank of 7).
  **Experimentation** spent a weekly-capped resource to discover recipes, and a failure
  could set a 4-hour lockout.
  https://www.wow-professions.com/guides/dragonflight-alchemy-guide
- **The War Within:** alchemists "learn nearly all of their recipes via the
  Experimentation mechanic", now aimed at a chosen herb, and the lockout fell to minutes.
  https://www.method.gg/guides/the-war-within-alchemy-profession-leveling-guide

---

## 4. More video games: discovery, failure and delivery forms

### Minecraft brewing (Mojang)

- **Procedural brewing was tried and dropped.** The Mundane Potion is "a remnant of an
  abandoned procedural brewing system". Recipes "were meant to be different each time you
  generated" a world, and it "didn't turn out to be much fun for the player."
  Source: Tom Stone, "Meet the Magma Cube", minecraft.net, 21 Feb 2017. [P, read through a
  search extract and the official wiki's citation; the page timed out]
  https://www.minecraft.net/en-us/article/meet-magma-cube ; [W] https://minecraft.wiki/w/Brewing
- **The cauldron era.** Beta 1.9's first brewing was a cauldron with no interface: about
  150 combinations, many duplicates. The brewing stand and its interface cut that to 25
  potions in 31 combinations. [W] same page
- **Base plus modifiers:**
  - Nether wart makes the Awkward base.
  - Redstone extends a potion and glowstone strengthens it. 1.9 stopped the two stacking on
    one potion.
  - A fermented spider eye **inverts** an effect: swiftness to slowness, healing to harming,
    night vision to invisibility. [W] https://minecraft.wiki/w/Fermented_Spider_Eye
- **Delivery forms are modifiers.** Gunpowder makes a potion a splash (thrown) potion, and
  dragon's breath makes a splash potion lingering (a cloud). [W] https://minecraft.wiki/w/Brewing
- **Fuel was added later.** Blaze powder fuel arrived in 1.9 and was cut from 30 brews to
  20 within a snapshot. [W] https://minecraft.wiki/w/Brewing_Stand . Mojang's stated reason
  was that "each crafting process consumed a resource" ("Meet the Blaze", minecraft.net,
  20 Dec 2016, [P] through a search extract).

### Noita (Nolla Games)

- **Per-seed secret recipes.** Lively Concoction and Alchemic Precursor are each
  "generated from three randomly selected powders and liquids" from the run seed. Found
  honestly, they come "by pure chance". [S] https://noita.wiki.gg/wiki/Alchemy
- **Fixed reactions are the everyday alchemy.** Water and lava make rock; gold or diamond
  with chaotic polymorphine make silver. These are the same every run, and the reactions
  key on **tags** ("regenerative") rather than on material names. [S] same;
  https://noita.wiki.gg/wiki/Lively_Concoction
- **The secret did not last.** A fan found in the files that each recipe was "simply
  randomized according to the world seed", and everything was uncovered in about seven
  days. [S] https://www.indiegamewebsite.com/2020/07/30/how-noita-turned-video-game-alchemy-into-gold/
  A seed calculator now prints the formula: "There isn't any guesswork."
  [S] https://github.com/Neffc/narg
- **No Nolla statement on the recipes was found.** Purho on emergence in general: "There's
  always something new to be discovered, even for us." [P]
  https://www.gamedeveloper.com/game-platforms/road-to-the-igf-nolla-games-i-noita-i-

### Monster Hunter (Capcom)

- **Older games could fail.** The MH Generations manual: "Not all combinations will be
  successful"; failure risks "leaving you with Garbage". Books of Combos raised the odds,
  and every success went into the Combo List. [P]
  https://game.capcom.com/manual/MH_Gen/en/page-52.html
- **From World on, every combination succeeds and the books are gone.** "Every item became
  100% combinable"; the lowest old rate was 55%. Rise and Wilds kept 100%, and auto-craft
  makes an item the moment its last ingredient is picked up.
  [S] https://wikiwiki.jp/nenaiko/システム/調合 ;
  https://monsterhunterworld.wiki.fextralife.com/Crafting
- **No Capcom reason found** in three interviews or a Japanese search (the herbalism sweep
  could not find one either).

### Elden Ring (FromSoftware)

- **Cookbooks gate recipes.** A recipe needs its cookbook and its materials (59 cookbooks in
  8 series), and crafting never fails.
  [S] https://exputer.com/guides/elden-ring-how-to-use-cookbooks-recipes-locations/
  Knowledge is a found item, not a check: the "manual" precedent.
- **The Flask of Wondrous Physick mixes two crystal tears** into one vessel: one use a
  rest, and tears change only at a Site of Grace.
  [S] https://eldenring.wiki.fextralife.com/Flask_of_Wondrous_Physick
- **Individual tears kept being tuned**, with no reasons given:
  - 1.06 fixed one tear;
  - 1.09 cut the Shrouding Cracked Tears in PvP only;
  - 1.12 shortened the Cerulean Hidden Tear for everyone.

  [P] https://en.bandainamcoent.eu/elden-ring/news/elden-ring-patch-notes-106 ;
  https://en.bandainamcoent.eu/elden-ring/news/elden-ring-patch-notes-version-109 ;
  [S] the 1.12 notes as quoted by Dexerto.

### Breath of the Wild and Tears of the Kingdom (Nintendo)

All [S], search extracts of fan wikis only.
- **An elixir splits its jobs.** A critter sets the effect, a monster part sets the
  duration, and two different effects in one pot cancel.
- **A critical cook** adds one random bonus.
- **Tears of the Kingdom saves a recipe once cooked**; Breath of the Wild did not.

  https://www.nintendolife.com/guides/zelda-tears-of-the-kingdom-best-recipes-how-to-cook-full-recipe-list

### Stardew Valley: does quality carry through processing?

- **By default, no:** "For most Artisan Goods, the star quality of the ingredients used is
  ignored." [S, official community wiki] https://stardewvalleywiki.com/Artisan_Goods
- **Three exceptions, each a different rule:**
  - size maps to a tier (large egg to gold mayonnaise);
  - the star is copied (1.6's fish smoker: "The quality of the fish is preserved");
  - time raises the tier (a cask ages wine from silver to iridium, 14 days a step).

  https://stardewvalleywiki.com/Fish_Smoker ; https://stardewvalleywiki.com/Cask

### Outward, Divinity: Original Sin 2, Path of Exile

- **Outward:** making the right combination by hand also unlocks the recipe. A failed
  alchemy attempt destroys the ingredients "and you receive nothing", and a community mod
  exists only to stop that. [S] https://outward.wiki.gg/wiki/Crafting ;
  https://www.nexusmods.com/outward/mods/131
- **Divinity: Original Sin 2:**
  - Recipes are often found in books.
  - The first game's Crafting and Blacksmithing abilities were dropped so anyone can
    craft. That is a community account; no Larian statement was found.

  [S] https://gamerant.com/divinity-original-sin-2-crafting-guide/
- **Path of Exile:** 3.15 reworked flasks toward "considered flask choices", halving charge
  pools and removing the immunity suffixes. [P]
  https://www.pathofexile.com/forum/view-thread/3147479

---

## 5. Real alchemy, for grounded minigames

- **The operations are historical.** Zosimos describes apparatus "for distillation,
  sublimation, filtration, fixation", and Maria's bain-marie gave gentle, controlled heat.
  [P] https://www.sciencehistory.org/stories/magazine/the-secrets-of-alchemy/
- **Fixing has a colour cue.** Sulphur vapour taken up by mercury turns it yellow, and the
  mercury becomes "fixed (that is, nonvolatile)". [P] same source. This is a real shape
  for "stabilize": making a volatile thing stay put.
- **Sublimation.** Sal ammoniac does not melt: it vaporises and re-forms as a crust
  higher up the vessel. It was the classic sublimate, and the Jabirian corpus counted it
  as a fourth "spirit".
  [S] https://www.encyclopedia.com/people/science-and-technology/chemistry-biographies/jabir
- **Calcination.** Strong heat short of melting leaves a powdery calx.
  [S] https://en.wikipedia.org/wiki/Calcination
- **The colour stages of the Great Work.**
  - The order: nigredo (black), albedo (white), citrinitas (yellow), rubedo (red).
    Citrinitas was often folded into rubedo after the 15th century. The peacock's tail is
    sometimes a display of many colours between them.
    [S] https://en.wikipedia.org/wiki/Magnum_opus_(alchemy)
  - Rampling (Ambix, 2024): yellowing is common in medieval recipes but drew less comment.
    [P, abstract]
    https://collaborate.princeton.edu/en/publications/citrination-and-its-discontents-yellow-as-a-sign-of-alchemical-ch/
- **Timing.** Schmechel (Ambix, 2025) on Petrus Bonus describes a "Goldilocks moment" of
  ripeness, past which the fire destroys the work. [P, abstract through search only]
  https://www.tandfonline.com/doi/full/10.1080/00026980.2025.2574788
- **Recipes in code word can be reproduced.** Principe followed George Starkey's
  directions and grew the gold-mercury "Philosophical Tree".
  [S] https://en.wikipedia.org/wiki/George_Starkey
- **Distillation cuts** (modern spirits, the same physics as the alembic):
  - heads come off first, below 78.3 °C, smelling of solvent;
  - hearts follow at about 78.3 to 82 °C;
  - tails come last, as strength falls, smelling of wet cardboard.

  Distillers watch instruments "but they use their senses".
  [S] https://whiskyadvocate.com/Heads-Hearts-and-Tails-of-Whisky-Distillation

---

## 6. What to take

Recommendations, not findings. Each is tied to the evidence above and to
`docs/alchemy-inventory.md`.

### 6.1 Keep PF1e's three channels distinct, and use PF2e's line for the boundary

- **Three channels** (§1.3): Craft (alchemy) items, potions and the class's personal
  alchemy are different things in the book. The world class can own the first two without
  pretending to be the third.
- **The enchanting boundary.** PF2e draws it in one sentence (§2.1): alchemical items are
  not magic, potions are. For this app the more useful line is single-use against
  permanent, because the enchanter already treats potions as consumable stand-ins. Either
  way, the line should be stated once and the enchanter's `holds_spell` contract kept.
- **Who may brew a spell potion.** The book needs caster level 3, the spell prepared and a
  slot spent (§1.2). The enchanter's house rule already lets a potion stand in for knowing
  a spell; letting a learned formula stand in for the spell at the alchemy bench is the
  same rule from the other side. It is the owner's call (questions Q1.3).

### 6.2 Fix the book items first, as the forge did

The book prints exact numbers for every classic (§1.1), and the catalogue misses most of
them (inventory §0.2). Before anything new:
- **Alchemist's fire:** 1d6 + 1d6 next round, a ranged touch attack, 1 splash, DC 20.
- **Antitoxin:** +5 alchemical for an hour, DC 25.
- **Tanglefoot bag:** entangled, plus glued on a failed DC 15 Reflex save.
- **Sunrod, smokestick, thunderstone, tindertwig:** as the table.
- **Potions:**
  - priced at 50 gp × spell level × caster level;
  - no personal-range spells;
  - caster level as the book minimum, raised by quality if the owner agrees.

PF2e's persistent damage (§2.1) is the right shape for "burns again next round", and it
belongs with the forge's periodic executor.

### 6.3 Traits travel through intermediates; finished goods are dead ends

- **Atelier is the closest model** (§3). Ryza's traits pass through intermediates even
  while inactive; finished goods give nothing back.
- **Two merge rules, both data** (§3):
  - same-named traits add their levels (Ryza);
  - listed pairs combine into a named higher trait (Sophie).
- **A cap by crafter level** (Ryza's alchemy level) keeps it bounded.
- **Slots per product family.** Atelier's three trait slots and the Physick flask's two
  tears (§4) both cap how much one vessel carries. Today's "everything sums" is what turns
  alchemist's fire into 2d6.
- **Yumia is the warning** (§3): separating traits from synthesis read as shallow to
  players. Traits should stay bound to the materials that carry them.

### 6.4 Discovery: a fixed, learnable table, several ways in

- **Do not make secret per-world recipes the main loop.**
  - Minecraft dropped per-world brewing as "not much fun" (§4).
  - Noita's per-seed recipes fell to the data files within a week, and players now look
    them up (§4).

  A fixed, learnable reaction table keyed on trait tags (Noita's tags) suits the app's
  tag law and survives being looked up.
- **Several ways in, each a precedent:**
  - skill tiers reveal more (Oblivion);
  - eating or testing reveals one (Skyrim);
  - found books (Elden Ring cookbooks, BG3 notes, DOS2);
  - making it right writes the recipe (Outward, Tears of the Kingdom, Ars Magica's lab
    text);
  - Guild Wars 2's counter of how close you are (herbalism sweep §4).
- **Any discovery mechanic is ours.** No tabletop system found makes reagent discovery a
  rule (§2.4).

### 6.5 Failure, randomness and repetition

- **A failed roll should not leave nothing.** Monster Hunter removed "Garbage" and made
  every combination succeed (§4). Outward's players wrote a mod to stop failed alchemy
  eating ingredients. The app keeps the PF1e rule (fail by 5 or more loses half), which the
  owner already chose for herbalism; volatility can add a real mishap on top, but the
  minigame never costs materials.
- **Randomness is moving toward choice:**
  - WoW Inspiration gave way to Concentration (herbalism sweep);
  - the Artificer's random elixir became chosen (§2.2);
  - the PF2e remaster dropped a daily guessing pool (§2.1, Paizo's own words).

  Mishaps are the one place alchemy should keep chance, and the preview already states the
  stakes.
- **A repeat path.** Potion Craft's recipe book, and the Witcher 3's refills "to get rid of
  pointless repetitions". The owner chose "always play" for the other two crafts, and
  recipe loading with bulk stacks is the softener there.

### 6.6 Methods and minigames grounded in real operations

- **Verbs for modifiers.** Minecraft's extend, strengthen, invert and delivery form (§4)
  are clean one-step operations, and 1.9 forbade stacking extend with strengthen.
- **Delivery form is a choice of vessel.** Gunpowder makes a splash potion, dragon's breath
  a lingering cloud. This matches the inventory's "a vessel is what makes it throwable",
  stated as a method rather than inferred.
- **The apparatus split** (Morrowind, Oblivion): one tool for positive effects, one for
  negative, one for both. A precedent for distinct methods that each touch a different
  part of the product.
- **Grounded bands** (§5):
  - Distil: take the hearts between heads and tails, by temperature and smell.
  - Calcine: drive to a white calx without melting.
  - Sublime: the crust re-forms higher up.
  - Stabilize, really "fix": the volatile stops moving, and turns yellow.
  - The whole work: the "Goldilocks moment".
  - Tier or legendary-chain names: the colour stages, black, white, yellow, red.

  Potion Craft already uses the colour stages for its legendary chain (§3).
- **Start generous and keep softening** (both earlier sweeps); show every gauge as a
  number and bar as well as a colour.

### 6.7 Transmutation needs a budget, not a lockout

WoW went from a 23-hour Arcanite cooldown to none, then to banked charges, then to
minute-long lockouts (§3). If Transmute exists, cost it in materials (two for one, or a
catalyst), as herbalism's concentration does, not in real-time waits.

### 6.8 World Bible

Fixes are world-agnostic. Whatever the pass gives a reagent (product effects, working
traits, volatile, forms of a shared material) should be optional fields with defaults in
`docs/campaign-format.md`, and what the next export should carry belongs in
`docs/from-world-bible.md`. Today that file asks nothing of alchemy (inventory §9).

---

## 7. What others tried and abandoned

| Game or system | Tried | Abandoned or changed to | Source |
|---|---|---|---|
| D&D 3.5 → PF1e | Craft (alchemy) only for spellcasters | Anyone with the skill | [S] dndtools, d20srd search |
| D&D 3.5 → PF1e | Brew Potion: 1 day a potion plus XP | 2 hours or 1 day per 1,000 gp, no XP; the old "1 day" line left in Creating Potions | [P] CRB; [S] dndtools |
| PF1e → Unchained | Check × DC multiplication | Fixed steps and progress, margin multiplies | [P] Unchained |
| PF1e Alchemy Manual | Spontaneous alchemy tracking every reagent dose | Stayed optional; reviewed as costlier than normal crafting | [S] review |
| PF2e 2019 → 2024 | A daily pool of infused reagents | Versatile vials that refill in exploration; "complex decisions based on guesswork" | [P] Paizo blog |
| D&D 5e Artificer | A random elixir each long rest | More player choice (2025) | [S] |
| D&D 5e 2014 → 2024 | 5 gp a day of progress | 10 GP a day | [P] D&D Beyond |
| Minecraft | Procedural brewing, recipes per world | Fixed recipes; "not much fun" | [P via extract] minecraft.net |
| Minecraft | Cauldron brewing, ~150 duplicate-heavy mixes | Brewing stand, 25 potions | [W] |
| Minecraft | Stacking extend and strengthen | Forbidden (1.9) | [W] |
| Minecraft | Free brewing | Blaze powder fuel, 30 then 20 uses | [W]; [P via extract] |
| Monster Hunter | Combination rates (min 55%), Garbage, combo books | 100% from World on; books gone; auto-craft | [P] MHGen manual; [S] |
| Noita | Per-seed secret recipes | Kept, but solved by tools within about a week | [S] |
| Potion Craft | Element tied to direction | 8 elements, iridescent ingredients | [P] Devlog #16 |
| Potion Craft | Legendary chain by hand every time | Saveable, "reduce tediousness" | [P] 2.0 notes |
| Potion Craft | Impossible customer requests | Removed (2.0.2) | [P] |
| KCD1 → KCD2 | Mistakes cost potion count; Routine autobrew | Four quality tiers; no autobrew (modded back) | [S] |
| Morrowind | Brewing could fail and waste ingredients | Not in Oblivion or Skyrim (absence, not a statement) | [W] |
| Oblivion → Skyrim | Portable apparatus, 4 ingredients | Lab only, 2-3 ingredients, Purity perk | [W] |
| Witcher 1/2 → 3 | Substances, any carrier | Named ingredients; refill on meditation | [P-ish] REDkit; [S] |
| Witcher 3 | Weighted ingredients, sellable potions | Weightless (1.07); unsellable (1.10) | [P] |
| Atelier Sophie → Ryza | Pairwise trait combining | Level addition only | [S] |
| Atelier Ryza → Yumia | Traits chosen during synthesis | Socketed afterwards; players call it shallow | [P] interview; [S] |
| WoW | 23-hour transmute cooldown | Removed (2.4.0); later charges; lockouts cut to minutes | [S] |
| Zelda BotW → TotK | No recipe memory | Recipes saved once cooked | [S] |

**Things worth refusing, with reasons:**
- **Secret per-world recipes as the discovery loop** (Minecraft, Noita): abandoned as no
  fun, or solved within a week.
- **Failure that yields garbage or nothing after a successful roll** (Monster Hunter,
  Outward). The herbalism rule holds: materials are lost only to the d20.
- **Unbounded effect stacking** (today's sum; Minecraft 1.9's stacking ban; Skyrim's
  Fortify loop).
- **Real-time cooldowns on transmutation** (WoW walked them back three times).
- **Traits detached from materials** (Yumia's backlash).

---

## 8. Critic pass: what is weak or unconfirmed

Corrections made while checking the helpers' drafts against the sources:
- **"25 gp × level × CL" is the creation cost, not the price.** The price is 50 gp. The
  potion price in the inventory (50 gp) was right; the research brief's 25 was wrong.
  Checked on the PRD potions page.
- **The personal-range ban** was checked verbatim on the PRD's magic-item creation page.
- **The Craft DCs** were checked against Unchained's difficulty list, which agrees with
  the core table for acid (15), alchemist's fire (20), antitoxin, sunrod and tanglefoot
  bag (25). Smokestick and tindertwig (20) and thunderstone (25) come from the helper's
  read of the core table only.
- **Alchemist's fire's second round** (1d6 the next round) was checked on AoN's item page
  by the helper and matches the core equipment text.
- **The brief's "the alchemist class progresses in gp"** was wrong: that is the Master
  Alchemist feat.
- **Potion Craft 2.0** was not a map overhaul; the map changed in Early Access (Devlogs
  #16-17).
- **Witcher 3 substances:** the "any carrier serves" model is Witcher 1 and 2. In Witcher 3
  substances are items of their own.
- **KCD1 had no quality tiers**; the tiers are KCD2's.
- **The Minecraft "not much fun" quote:** the minecraft.net article would not load. Its
  text was confirmed through a search extract of the article itself. The official wiki's
  Mundane Potion page does not carry it.
- **Monster Hunter's 100% from World on and the 55% minimum** were confirmed on wikiwiki.jp
  (fan wiki, [S]). The MH Generations manual's "Garbage" is [P].
- **The Witcher 3 reason** is CDPR's words relayed by a press piece from a forum Q&A, so
  [S], not [P].
- **Hosoi's Yumia quote** "you can add the trait after" was fetched directly. A second
  quote ("a little simpler") could not be found on the page and was left out.

**Could not confirm**
- **Brew Potion time:** the feat (2 hours or 1 day per 1,000 gp) and Creating Potions
  (1 day) disagree in the book itself. No Paizo FAQ was found.
- **Personal-range potions:** no Paizo FAQ found; the PRD line is the only source.
- **Unchained's raw-material fraction** ("1/4 the cost") was read on the page, but I did
  not find whether it supersedes core for alchemy in Paizo's eyes.
- **The Alchemy Manual's costs** ("10-20% above market") came from a pirated-PDF summary
  and were not used.
- **PF2e:**
  - Only Keeley's blog was found on the remaster's reasons; no Sayre or Bonner interview.
  - Legacy Craft setup times were not checked.
- **5e:** the Xanathar's potion table and the 2024 DMG's potion tool row are secondary
  only.
- **Witcher TRPG alchemy:** no licensed source was found.
- **Ars Magica:** Art & Academe's exact lab total for experimental philosophy.
- **Nolla Games** on why the recipes are per seed. **Capcom** on why combining stopped
  failing. **FromSoftware** on any Physick tear change. **Warhorse** on why alchemy is
  manual.
- **Breath of the Wild's** critter/monster-part split and the 5% critical cook: fan-wiki
  extracts only.
- **Stardew:** whether wine ever took fruit quality into account.
- **WoW:**
  - whether the three specialisations were formally removed, and when;
  - the War Within lockout length (10 or 15 minutes);
  - the details of Dragonflight's potion quality ranks.
- **BG3:** the "three of the same ingredient" extraction count, and any Larian design
  statement.
- **Skyrim's Fortify Restoration loop:** UESP says unfixed in the base game, and some
  secondary sources say an official patch weakened it.
- **Atelier:** Item Rebuild in Ryza 2 and 3, and Ryza 3's trait changes.
- **Real alchemy:**
  - precipitation as a named historical operation was not sourced;
  - Schmechel's "Goldilocks moment" was read through an abstract in search results only;
  - the distillation cut temperatures are modern whisky practice, not period alchemy.
- **Not researched:** Potionomics beyond the herbalism sweep, Ostranauts, the Alchemist
  Gnome-style mobile games, Little Alchemy (a combination game with no stats).
