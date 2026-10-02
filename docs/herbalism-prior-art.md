# Herbalism revamp: prior art sweep

Research for the Herbalist crafting revamp in Pathfinder GM: one active method on a "workbench",
an animated tool for each method, dimming ingredients that do not fit, and a short quality minigame
after a successful d20.
Compiled 2026-10-02. Primary sources (developer posts, patch notes, official manuals, rulebook text
via Archives of Nethys, interviews) are preferred and marked **[P]**. Wikis and press summaries are
marked **[S]**. Anything I could not trace to a source is marked **UNCONFIRMED** in the critic
pass at the end.

---

## 0. The headline findings

1. **KCD2 did not add auto-brew. It removed it.** Kingdom Come: Deliverance 1 had Autobrew
   through the Routine perks. KCD2 shipped without it, and I found no KCD2 patch, up to 1.5.3
   (March 2026), that adds it back. Players restored it with mods. KCD2 replaced the
   relief with batch-yield perks: more potions from each manual brew. So the brief's phrase
   "KCD2's change to auto-brew known recipes" is the wrong way round.
2. **Every long-lived crafting game ended up with a way to stop repeating the hands-on part.**
   The forms differ: Witcher 3 refills potions, Potion Craft has the recipe book (and v2.0.2 made
   it cover more), FFXIV has Quick Synthesis (it cannot fail since 5.1, but it rarely gives high
   quality), KCD1 has Routine, Atelier has Auto-Add, and Monster Hunter has auto-craft. The game
   that left this out (KCD2) is the one whose players modded it back in.
3. **Timing minigames in cozy crafting games keep being softened after launch.** Potion Craft
   added Auto Hold because grinding and stirring tired players' hands. It also reworked its timing
   haggle, which players called "too hard" and out of step with the game's pace. KCD1's
   lockpicking was reworked and got an easy mode 19 months after launch. Stardew's creator says
   fishing "starts too hard."
4. **The RPG tradition has mostly moved away from letting player dexterity replace a character
   roll.** Oblivion's persuasion wheel became a pure Speech check in Skyrim. Oblivion's lockpick
   Auto Attempt button is gone in Skyrim. WoW replaced its random "crafting crit" (Inspiration)
   with a deterministic resource you choose when to spend (Concentration). Its stated reason was
   that the crafter had no agency. Where a minigame survives (Skyrim, Stardew, Starfield, KCD2),
   character skill enlarges the target zone or gives hints. Skill never sits idle while the hands
   do all the work.
5. **Tabletop PF1e already has a quality ladder you can borrow.** In Ultimate Wilderness
   herbalism, yield rises with the margin of success: meet the DC, beat it by 5, beat it by 10.
   Each herb also names its own preparation verbs, such as "dried and ground" or "pulped,
   skimmed, refined." Those verbs map directly onto the app's method list.

---

## 1. Video-game alchemy, herbalism and crafting

### Kingdom Come: Deliverance 1 (2018) and 2 (2025)
- **Loop (KCD1):** The player follows a recipe by hand. They pour the base, grind with mortar and
  pestle, add ingredients, boil, and time the steps with an hourglass. Mistakes reduce the yield.
  Brewing perfectly gives the full number of potions, and adding the wrong amount of an ingredient
  always fails the brew. [S] https://kingdomcomedeliverance.wiki.gg/wiki/Alchemy
- **Repetition (KCD1):** Autobrew came with the **Routine I** perk (Alchemy level 10). It
  auto-brews recipes you have brewed once before, one potion at a time. **Routine II** (level 13)
  gives three potions for the price of one. The wiki notes autobrew does not apply the
  Bundle-Alchemist bonus. [S] same page; https://kingdomcomedeliverance.wiki.gg/wiki/Alchemy
- **KCD2 change:** KCD2 has **no autobrew**. Players asked for it, and mods restored it ("Auto
  brew", "Autobrew Returned and Enhanced"). The second mod describes itself as restoring the KCD1
  autobrew selection, which implies the UI hook still exists but is disabled.
  [S] https://www.nexusmods.com/kingdomcomedeliverance2/mods/3573 ,
  https://www.nexusmods.com/kingdomcomedeliverance2/mods/3394 (the page returned 403; the
  description comes from search snippets).
  KCD2 eased the brewing instead. You raise and lower the cauldron rather than reading bubbles
  through the bellows, and the bellows became a separate step for recipes that need a vigorous
  boil. [S] GameSpot guide / Steam threads, via search.
  KCD2 also added yield perks: Secret of Matter I/II add potions per brew (players report up to
  6 potions or 18 powders a brew). Henry's-tier quality needs the level-16 Secret of Secrets perk
  plus perfect steps with fresh ingredients. [S] https://github.com/Omricon/Henrys-Moste-Potente-Potions
- **KCD2 patch notes checked:** 1.2, 1.3, 1.4, 1.5, 1.5.2 and 1.5.3 (March 5, 2026). The alchemy
  changes are cosmetic, drying racks, codex count fixes, and "re-taught to cook eggs." **No
  autobrew.** [S] https://kingdomcomedeliverance2.wiki.fextralife.com/Patch_Notes ;
  [P] https://www.deepsilver.com/games/kingdom-come-deliverance-ii/news/patch-12
- **Complaint/feel:** PC Gamer ran a column titled "After 75 hours, I finally cracked what I was
  doing wrong in KCD2's terribly explained alchemy system." The body would not load. The title
  alone says the manual-step system is opaque.
  https://www.pcgamer.com/games/rpg/after-75-hours-i-finally-cracked-what-i-was-doing-wrong-in-kingdom-come-deliverance-2s-terribly-explained-alchemy-system/
- **Influence:** Potion Craft's creator says KCD's alchemy minigame inspired him. He liked the
  atmosphere but found the controls inflexible. [P, interview]
  https://www.shacknews.com/article/127752/how-kingdom-come-deliverance-influenced-potion-craft-alchemist-simulator

### Potion Craft: Alchemist Simulator (niceplay games, 2021 EA, 2022 1.0)
- **Loop:** Grind in the mortar, which sets how far an ingredient's path extends. Then add to the
  cauldron, stir with the spoon to move along the path, add water to pull back toward the centre,
  and work the bellows/heat for some effects. The potion is a marker travelling over a
  **fog-of-war alchemy map**. Its effect comes from the icon it ends on, and its tier from how
  precisely it lands. Grinding is **continuous and partial**: you can stop "at almost any pixel."
  It is a quantity you control, not a reflex test. [S] https://potion-craft.fandom.com/wiki/Mortar_and_Pestle
  (via search); [S] https://en.wikipedia.org/wiki/Potion_Craft
- **Tool feel:** The creator: "If I couldn't make the control perfect, the game would never work."
  He says the replay value comes from optimising, for example using fewer ingredients. [P]
  https://www.gamereactor.eu/potion-craft-creator-if-i-couldnt-make-the-control-perfect-the-game-would-never-work-1459873/
- **Discovery:** The map starts fogged. A potion reveals the area around it as it travels, and
  revealed fog stays clear. Unknown effects appear as bottles with a "?" until you reach them.
  A talent widens how far you can see. [S] https://potion-craft.fandom.com/wiki/Alchemy_Map (via search)
- **Repetition:** A brewed potion can be saved as a recipe and brewed again from the Recipe Book
  in quantity, skipping the hands-on steps and spending the noted ingredients. [S, search
  snippet; the fandom page returned 402]. Devlog #30 lets you brew by clicking a recipe's picture
  in the book. [P, Steam news API] Patch **2.0.2** made salt and Philosopher's Stone recipes
  savable "so you don't have to create them all manually every time." It also rebalanced the
  final chapters so the main game takes "less grinding." [P/S]
  https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=1210320 ;
  https://techraptor.net/gaming/news/potion-craft-overhauls-alchemy-map-in-major-update
- **Abandoned or softened:**
  - **Devlog #14 "Accessibility – Auto Hold" (5 Apr 2022)** [P]. It was added after "a
    significant number of players reported getting hand fatigue" from holding the left mouse
    button to **grind ingredients, stir with the spoon, and drag shop items**. The setting lives
    in a new Accessibility section. *Directly relevant: our grind minigame is exactly this
    input.*
  - **Devlog #13 "Haggling minigame rework" (26 Mar 2022)** [P]. The haggle was a timing game:
    a moving arrow on a tilting scale with bonus zones, and difficulty raised arrow speed and
    tilt speed. Some players found it "too hard"; others said it "does not fit with the pace of
    the game." In the rework you choose one of five conversation themes, each with its own
    difficulty. Easy themes carry no profit loss, harder ones are riskier and pay more, and each
    visitor finds different themes easy. Profit is now shown clearly, and the haggle **ends
    automatically once maximum profit is reached**.
  - **Difficulty modes (v2.0, Dec 2023)** [P interview]. "Before, you only had one difficulty."
    The team saw three groups: those who were fine, those starved of ingredients, and those who
    found it too easy. They added Explorer, Classic, Grand Master and Suffering.
- **Complaints:** Reviews say late-game brewing is the same act at higher tedium, and that the
  manual process gets boring after a few hours. [S] Metacritic and Steam reviews via search;
  https://www.nintendolife.com/reviews/switch-eshop/potion-craft-alchemist-simulator (controller
  play was poor and touch was needed; top-tier precision is "frustratingly" tricky).

### Potionomics (Voracious Games, 2022)
- **Loop:** Pick ingredients so the cauldron's five "magimins" match the potion's target ratio.
  Quality comes from (a) how close the ratio is (up to 3 stars) and (b) the total magimin count,
  which sets the tier: six tiers, each with 0–5 stars. Brewing takes in-game time while you go
  out. [S] https://steamcommunity.com/app/1874490/discussions/0/3493130356491283030/
- **What happened:** The quality maths is deterministic, so players wrote a **linear-programming
  optimiser (PuLP)** to solve recipes outside the game.
  [S] https://steamcommunity.com/app/1874490/discussions/0/4631483574657222060/
  Players also asked for a "save current recipe / use recipe" button because they were "tired of
  solving the same puzzle." UNCONFIRMED whether the Masterwork Edition added it.
  [S] https://steamcommunity.com/app/1874490/discussions/0/3493130356503750607/
- **Design history:** Haggling began as a "guess the price" system like Recettear's and became a
  deckbuilder to add depth. [S] https://gamerant.com/potionomics-interview-romance-humor-personality/ (via search)

### Atelier series (Gust)
- **Loop (Ryza 2, official manual):** Pick a recipe, fill Material Loops with materials, then
  choose up to 3 traits to carry over. Trait slots open only once the matching loop is levelled.
  Quality is "determined by the materials used." The recipe list uses colour to show whether
  you can make each item, which is an eligibility cue.
  [P] https://www.koeitecmoamerica.com/manual/ryza2/en/4200.html
- **Repetition:** **Auto-Add Materials** can favour high- or low-quality materials and skips
  favourited items. Quantity Up skills enlarge batches. [P] same manual.
  Yumia (2025) has four Auto-Add modes: Prioritize Quality, Prioritize Effects, Bare Minimum and
  Custom. It also has "Simple Synthesis" for consumables anywhere, and Item Rebuilding to add
  material to finished items. [S] https://atelieryumia.wiki.fextralife.com/Synthesis
- **Abandoned or softened:** Producer Junzo Hosoi said the series had grown hard for new players.
  The "Mysterious" games moved to a visual synthesis meant to be "graphical and fun." Ryza 2 added
  the Base Material Loop because "the minimum required ingredients was unclear." He also named
  "looping the quality traits to prepare the highest quality ingredient" as too complicated for
  newcomers. [P interview] https://www.siliconera.com/interview-atelier-ryza-2s-producer-on-her-design-relationship-with-klaudia-and-friends/ ;
  https://www.rpgsite.net/interview/13286-atelier-ryza-3-alchemist-of-the-end-the-secret-key-interview-junzo-hosoi-on-ryzas-latest-adventure (via search)
- **Older failure model:** In Atelier Marie and Elie, synthesis could **fail**. The chance rose
  with alchemy level and fell with fatigue and a dirty workshop, and failures produced "Industrial
  Waste." [S] https://atelier.fandom.com/wiki/Atelier_Marie:_The_Alchemist_of_Salburg (via search).
  Modern Atelier synthesis does not fail: **UNCONFIRMED as a sourced claim.**
- Sophie's Tetris-like placement grid was kept and expanded in Sophie 2, not dropped.
  [S] https://www.rpgfan.com/review/atelier-sophie-2-the-alchemist-of-the-mysterious-dream/ (via search)

### The Witcher 3 (CD Projekt Red, 2015)
- **Loop:** Craft a potion once from its formula. After that you hold a limited stock that
  **refills automatically when you meditate**, provided you carry strong alcohol. There is no
  minigame.
- **Designer's words (Damien Monnier, Senior Game Designer) [P, Q&A]:** once you make the potion
  "it is yours and you can refill it automatically." Elsewhere he says he is not usually a fan of
  crafting and that the team doesn't send you on "a mad dash across the world for materials."
  https://www.dualshockers.com/the-witcher-3-wild-hunt-designer-responds-to-a-gazillion-questions-about-everything-really/
- **Witcher 1 (2007):** Formulae call for *substances* (Vitriol, Rebis, Aether…), so any
  ingredient carrying the substance will do. If every ingredient shares a secondary substance
  (albedo, nigredo or rubedo), the potion gets a bonus. [S] https://witcher.fandom.com/wiki/The_Witcher_alchemy
  This is a direct precedent for **eligibility by property rather than by named ingredient**.

### Skyrim (Bethesda, 2011)
- **Loop:** At a lab you pick 2–3 ingredients. Any effect they share becomes the potion. Strength
  comes from the Alchemy skill, perks and Fortify Alchemy gear. There is no minigame.
  [S, UESP] https://en.uesp.net/wiki/Skyrim:Alchemy
- **Discovery:** Eating an ingredient reveals its first effect. The Experimenter perk reveals 2,
  3, then all 4. Combining ingredients reveals the effects they share, and a failed mix still
  gives a little XP. [S, UESP] same page
- **Exploit:** Drinking Fortify Restoration amplified Fortify Alchemy gear, so each round of
  potions came out stronger than the last. The 1.6 fix is UNCONFIRMED here (search snippet only).

### Stardew Valley fishing (ConcernedApe, 2016)
- **Loop:** Holding the button raises a green bar and releasing lets it fall. Keep the fish
  inside the bar to fill a meter. The bar is 96 px at Fishing 0 and grows 8 px per level to 176 px
  at level 10. A Cork Bobber adds 25 px. [S, official wiki] https://stardewvalleywiki.com/Fishing
- **Quality:** A base quality comes from fish size. A **perfect catch**, where the fish never
  leaves the bar, upgrades quality one step, and a Quality Bobber adds another.
  **This is the closest precedent for "minigame sets the quality tier."** [S] same
- **Developer regret [P interview, PC Gamer, May 2025, via GameRant]:** "A lot of people hate it,
  but I think it's fun." He regrets that it **starts too hard**: the early bar should have been
  bigger, with difficulty climbing as players reach harder fish. He added the **Training Rod**
  (easier, but only common, normal-quality fish) and says many players don't know it exists. The
  minigame was inspired by the barrel sections of DKC: Tropical Freeze.
  https://gamerant.com/stardew-valley-creator-fishing-minigame-difficulty/ ;
  https://www.pcgamer.com/games/life-sim/a-lot-of-people-hate-it-but-i-think-its-fun-eric-barone-backs-stardew-valleys-fishing-minigame-but-does-admit-that-it-starts-too-hard/
- **Accessibility complaint:** A player with a motor disability calls the reflex test "physically
  impossible." They point out that the rest of the game needs no such reflexes while community
  center goals require fishing, and they ask for an official accommodation rather than mods.
  https://steamcommunity.com/app/413150/discussions/0/385428458178548706/
  The vanilla game still has **no skip**. The "Skip Fishing Minigame" and "Auto Catch" mods are
  the community's answer. https://www.nexusmods.com/stardewvalley/mods/2697
  Version 1.6 tutors players who haven't fished by late spring of Year 1. [S] official wiki.

### Final Fantasy XIV (Square Enix)
- **Loop:** Each craft is a turn-based rotation with a Progress bar, a Quality bar, Durability and
  CP. The condition changes at random (Good ×1.5 quality, Excellent ×4, Poor ×0.5), and the
  chance of a high-quality result rises with the Quality bar.
  [S] https://ffxiv.consolegameswiki.com/wiki/Crafting
- **Repetition:** **Quick Synthesis.** Patch 5.1 notes [P]: Quick Synthesis "will no longer fail"
  if you meet the recommended Craftsmanship, Control now meaningfully improves its HQ chance, and
  multi-crafts run faster per item.
  https://na.finalfantasyxiv.com/lodestone/topics/detail/3a23a8ba13b2c4152681ec4fa5716915b851002f
  6.0 let some recipes be quick-synthesised without a prior manual craft. [P via search]
  https://eu.finalfantasyxiv.com/lodestone/topics/detail/66a742165e9415790247c1a1f7d909abf5becb5c/
  The wiki notes Quick Synthesis rarely gives high quality, and expert recipes can't use it.
- **"Solved" crafting:** Standard recipes are run as macros generated by optimisers (Teamcraft,
  Raphael). **Expert recipes (5.21)** add extra random conditions, and are described as resisting
  macros. [S] https://ffxiv.consolegameswiki.com/wiki/Expert_Recipes (via search)
- **Abandoned:** In **6.0** high-quality versions of **gathered and dropped materials were
  removed** "to reduce inventory bloat." Existing HQ materials became "HQ in name only."
  [S quoting P] https://nosygamer.blogspot.com/2021/09/explaining-removal-of-hq-materials-in.html
  *Lesson: a quality tier on raw ingredients multiplies the inventory, and a large MMO cut it.*
- **5.1 also added** a recipe tree and a raw-materials list to the Crafting Log. [P] 5.1 notes.

### World of Warcraft professions (Blizzard)
- **No minigame.** In **Dragonflight (2022)**, final skill is compared with recipe difficulty. If
  skill exceeds difficulty you get maximum quality; otherwise quality depends on where skill
  falls. Higher-quality reagents add skill. The stated goal was for quality to be worth the effort
  without making the lowest tier feel worthless. [P dev blog]
  http://worldofwarcraft.blizzard.com/en-us/news/23876529
- **Abandoned: Inspiration, a random "crit" for extra skill, removed in The War Within (2024).**
  Blizzard cited three problems: **"a lack of decision making and agency for the crafter,"**
  confusion for customers, and heavy RNG, "which was never the goal." Crafters were charging per
  re-roll until it crit. It was replaced by **Concentration**: a per-profession pool that
  regenerates over time, which you choose to spend to guarantee the next quality tier. The cost
  shrinks the closer you already are. [P blue post]
  https://www.bluetracker.gg/wow/topic/us-en/1833285-professions-update-concentration-in-the-war-within/
  *Lesson for us: a chance-based quality bump was replaced with a deterministic resource the
  player chooses to spend, explicitly for the sake of player agency.*

### Monster Hunter (Capcom)
- **Old model:** Combining could fail and produce **Garbage**, and Books of Combos raised the
  odds. [P, MH Generations manual] https://game.capcom.com/manual/MH_Gen/en/page-52.html
- **World/Rise:** Combining has no listed failure rate (the claim that it is always 100% comes
  from search snippets, and Capcom's reason is UNCONFIRMED). **Auto-craft** combines an item the
  moment you pick up its last ingredient; for example, herbs become Potions in the field.
  [S] https://monsterhunterworld.wiki.fextralife.com/Crafting
  *Lesson: a field-staple consumable is crafted by a standing order, not by hand.*

### Guild Wars 2 (ArenaNet)
- **Discovery tab:** Drop up to 4 ingredients in and the panel counts what is left: "**N possible
  unknown recipes! Add more compatible ingredients!**" or "0… try removing some." When the
  combination is right it says "This looks like something! Craft the item to save the recipe."
  The **first discovery gives 100–150% bonus crafting XP**. Only items that belong to an
  undiscovered recipe are offered, which is an eligibility filter.
  [S, official wiki] https://wiki.guildwars2.com/wiki/Crafting
- **Batching:** Each consecutive copy crafts in half the time of the previous, up to a cap.
  Crafting criticals give only XP, never better stats. [S] same.

### Strange Horticulture (Bad Viking, 2022)
- **Identification is the game.** An incomplete plant book and close inspection (scent, touch)
  let you identify the right plant. The designer says there is always some piece of information
  that singles out the plant you need, even when it is deliberately vague. The team tuned it by
  trial and error and patched for colour-blind players after launch. [P interview]
  https://www.gamedeveloper.com/design/strange-horticulture---bad-viking

### Botany Manor (Balloon Studios, 2024)
- The player completes a **herbarium** by reading clues around the manor about what each plant
  needs (sun, shade, soil) and then growing it. The finished book is the reward. [S]
  https://en.wikipedia.org/wiki/Botany_Manor ; https://videochums.com/article/explore-botany-manor

### Moonstone Island, Wylde Flowers
- **Moonstone Island:** brewing uses fixed recipes found in chests: a primary, a secondary and a
  bottle. There is no minigame or property play. Reviewers mention too many crafting stations
  and menus. [S] https://moonstoneisland.wiki.gg/wiki/Cauldron ; https://hardcoregamer.com/reviews/review-moonstone-island/471128/
- **Wylde Flowers:** a basement cauldron makes spells and potions with no notable minigame.
  Reviewers praise early spells that **reduce grind** (stamina brew, auto-collect).
  [S] https://www.gamesasylum.com/2022/10/22/wylde-flowers-review/ (via search)

### Cooking Mama (Office Create) / method minigames
- Each recipe step (chop, stir, grate, fry) is its own minigame, **usually under 10 seconds**.
  The recurring criticism: across 70 recipes, "the steps to cook the recipes are all very
  similar." [S] https://en.wikipedia.org/wiki/Cooking_Mama ; user review via search.
- **Old School RuneScape, Giants' Foundry:** a sword is worked through a sequence of tools
  (trip hammer when hot, grindstone at medium heat, polishing wheel when cold). Quality is
  materials plus moulds, **minus 10 for each wrong tool or temperature**. Better alloys add steps
  and narrow the temperature windows. [S official wiki] https://oldschool.runescape.wiki/w/Giants%27_Foundry
  This closely matches a multi-method chain with an animated tool for each step.

### Fable (Playground, 2026)
- The developers confirmed the demo's blacksmith job was sped up and its payout inflated. In the
  final game you will need to "put some shifts in." [S] https://www.thegamer.com/fable-blacksmithing-combat-made-easier-gameplay-demo/
  The detail that Fable 2's blacksmith timing bar sped up at higher star ratings comes only from
  GameFAQs: **UNCONFIRMED**.

---

## 2. Player skill versus character skill

| Game | What the minigame does | How character skill enters | Outcome |
|---|---|---|---|
| Oblivion lockpick | timing on tumblers | Security slows the tumblers; masteries keep set tumblers after a break; **Auto Attempt** button resolves the lock from skill and spends picks | A level-1 character can pick hard locks by hand, so the skill felt irrelevant [S UESP https://en.uesp.net/wiki/Oblivion:Security ; essay https://www.terminally-incoherent.com/blog/2009/01/19/skill-checks-vs-minigames/index.html] |
| Oblivion persuasion | rotating wedge wheel | Speechcraft gives a free rotation, slower decay, etc. | Widely mocked. **Skyrim replaced it with a pure skill check:** "Chances of success depend solely upon your Speech skill." [S UESP https://en.uesp.net/wiki/Oblivion:Persuasion , https://en.uesp.net/wiki/Skyrim:Speech] |
| Skyrim lockpick | angle-finding | sweet spot ×(1+0.6·skill/100), picks last ×1.5 at 100, perks per lock tier; **no Auto Attempt** | Skill widens the zone; the hand still decides [S UESP https://en.uesp.net/wiki/Skyrim:Lockpicking] |
| Fallout 3 terminals | word deduction | Science gates which terminals you may try and reduces the number of decoys | Skill gates the attempt and simplifies it [S https://fallout.fandom.com/wiki/Hacking_(Fallout_3)] |
| Starfield digipick | ring puzzle | Security unlocks lock tiers, **banks auto-attempts** (2–5), rings turn blue when a pick fits (R2), can eliminate unneeded keys (R4) | Skill shows up as **hints and auto-solves**, not reflex easing [S https://starfieldwiki.net/wiki/Starfield:Security_(Tech_Skill)] |
| KCD2 lockpick | keep a cursor in a moving zone while rotating | the cursor grows with Thievery | Players with hand tremor report they cannot do it [S search: Steam threads, guides] |
| KCD1 lockpick | same family | — | Warhorse said "we are working on the lockpicking controls" (Feb 2018) and added an **"easy mode" setting on 9 Sep 2019** [P] https://www.gamewatcher.com/2018-14-02-warhorse-are-reworking-lockpicking-in-kingdom-come-deliverance ; Steam news API appid 379430 |
| Mass Effect 2 → 3 | Bypass and Hack minigames | — | **Removed in ME3** in favour of a timed hold that lets you keep moving. BioWare's reason is UNCONFIRMED [S https://masseffect.fandom.com/wiki/Bypass] |
| Outer Worlds | none | pure stat check | Fans attribute this to Obsidian's preference for pass/fail point checks: UNCONFIRMED as a dev statement |
| Stardew fishing | keep-in-zone | the bar grows with Fishing level; the Training Rod sets an effective level of 5 but caps the catch | The developer regrets the early difficulty [P] |

**Synthesis for a d20 game.** The camp that wants stat checks (essay above) has a point:
when dexterity fully overrides the stat, the stat stops mattering. The surviving pattern in
modern games is:
- **(a) The stat decides whether you can and whether you succeed.** Fallout gates on skill;
  Skyrim speech is a pure check.
- **(b) The minigame only moves the result within a band.** Stardew's perfect catch adds +1
  quality step.
- **(c) Skill widens the zone or adds hints.** Skyrim, Stardew, Starfield and KCD2 all do this.
- **(d) A no-hands path exists that resolves from the stat.** Oblivion's Auto Attempt, Starfield's
  banked auto-attempts, Potion Craft's recipe book.

---

## 3. Tabletop herbalism

### PF1e Craft and Profession
- **Craft (core).** Raw materials cost 1/3 of the price. Each week (or day), multiply the check by
  the DC to get progress in silver pieces. Failing by 4 or less makes no progress; failing by 5
  or more **ruins half the materials**. You may add +10 to the DC to work faster. An alchemist's
  lab gives +2 to Craft (alchemy). [S quoting P] https://www.d20pfsrd.com/skills/craft/
- **Ultimate Wilderness herbalism (pp. 152–154).** [P via AoN, the licensed rules site]
  https://www.aonprd.com/Rules.aspx?ID=2416
  - **Gather** with Profession (herbalist) or Knowledge (nature), or Survival in a favored
    terrain. You declare the target herb at the start of the day. Gathering while travelling
    halves overland speed. **Success gives 1 yield, beating the DC by 5 gives 2, by 10 gives 3.**
    An area supports 1d4 expeditions, then needs 2d6 months to regrow. With 5+ ranks you can
    search for 2 herbs, plus one more per 5 ranks (up to 5).
  - **Prepare** with Craft (alchemy), or Profession (herbalist) at DC+5. Failing by 5 or more
    ruins the dose; smaller failures may retry. Each day you prepare **one herb type, in doses
    equal to your Profession ranks**; 7 ranks allow 2 types and 14 ranks allow 3.
  - **Spoilage:** raw herbs spoil in 24 h; prepared herbs last 1 month.
  - **Each herb has its own preparation.** Leechwort (gather DC 16, 1d4 doses, warm
    forest or swamp) is "dried and ground" over 1 week, up to a dozen doses at once, DC 15 Craft
    (alchemy); failure spoils the batch. It gives +1 to Heal, +2 to staunch bleeding.
    https://www.aonprd.com/EquipmentMiscDisplay.aspx?ItemName=Leechwort
    Bloody mandrake (DC 20) is pulped, the sap skimmed and refined, DC 15 and 1d4 h per yield.
    It adds +1 caster level to certain spells.
    https://www.aonprd.com/EquipmentMiscDisplay.aspx?ItemName=Bloody%20Mandrake
    The book lists 24 herbs. https://www.aonprd.com/EquipmentMisc.aspx?Category=Herbs
  - **Herbalist alchemist archetype** (vine leshy only): uses Profession (herbalist) for Craft
    (alchemy) and Wisdom as the key ability, adds half alchemist level to herbal crafting and
    foraging, and throws seedpods instead of bombs.
    https://www.d20pfsrd.com/classes/base-classes/alchemist/archetypes/paizo-alchemist-archetypes/herbalist-alchemist-archetype/
- **Why Profession (herbalist) felt like bookkeeping:** a Paizo forum thread asks "what is the
  point." Posters call the skill vestigial from 3.0 (it used to aid Heal) and note it costs skill
  points that could buy Perception or Stealth. Sean K Reynolds answers that GMs should make
  players' skill choices matter. https://paizo.com/threads/rzs2kjkx

### D&D 5e: Xanathar's herbalism kit
- The kit identifies plants and harvests them safely, and its holder can craft potions of
  healing. Its contents include a **mortar and pestle**, clippers, gloves and jars. The DC table
  (find plants DC 15, identify poison DC 20) comes from secondary summaries.
  [S] https://arcaneeye.com/dnd-items/the-herbalism-kit-in-dnd-5e-updated-for-the-2024-rules/ (via search)

### Heliana's Guide to Monster Hunting (Hit Point Press)
- **Harvest list:** before carving, the players choose the parts and their order. **DCs add up**,
  so parts late in the list may become impossible. Each harvesting check is Assessment (Int)
  plus Carving (Dex), and allies add their proficiency. It takes 5 minutes to 12 hours by size,
  must start before the body degrades, and can't be interrupted.
- **Crafting always succeeds.** Quality varies by **quirks** (boons or flaws), set by how far
  the check beats or misses the DC. The design aims to give everyone's tool proficiencies a use.
  [P, D&D Beyond feature] https://www.dndbeyond.com/posts/1958-turning-monsters-into-loot-with-helianas-guide-to
- Critics praise how modular it is but warn it is extra admin if a table doesn't use the whole
  system. [S] https://dungeonmister.com/guides/helianas-guide-to-monster-hunting-dd-5e-review/ (via search)
- "Hero's Handbook-style harvesting tables": **I could not identify a product by that name**
  with harvest tables. Heliana's per-creature harvest tables are the nearest match.

### The Witcher TRPG (R. Talsorian)
- Formulae call for alchemical substances, and an Alchemy (Crafting) roll is made against the
  formula's DC. **UNCONFIRMED.** I could not reach the rulebook text. The substance-substitution
  model is sourced only for the Witcher 1 video game (section 1).

### Ryuutama (Kotodama Heavy Industries)
- Each morning a STR+WIS (or INT; sources differ) roll is made against a terrain-and-weather
  target. Success gives one **terrain-specific** Healing Herb (crown morning glory on prairie,
  moonflower liverwort in forest). A **critical gives 3**; a **fumble gives Poison 6**. Herbs keep
  1 day, or 7 in an herb bottle. [S] https://writeups.letsyouandhimfight.com/professorprof/ryuutama/ ;
  https://philgamer.wordpress.com/2015/08/17/lets-study-ryuutama-natural-fantasy-rpg-part-4-the-rules-of-the-journey/ (via search)

### What makes tabletop crafting rewarding instead of bookkeeping
- **The Angry GM** [P essays]: crafting disappoints when it becomes a second currency that works
  like gold. Ingredients should be **concrete things in the world** that players seek for a
  purpose, and every use should consume them. Avoid "pages and pages of charts." He proposes
  that each ingredient carry only **three descriptors (rarity, type, special quality)**, giving
  roughly 50–100 ingredients rather than thousands. Acquisition should come naturally from
  adventures, not from farming.
  https://theangrygm.com/crafting-disappointment/ ; https://theangrygm.com/crafting-in-the-raw/
- Common threads in PF1e UW, Heliana and Ryuutama:
  - yield or quality ladders read off the **margin** of success;
  - **spoilage clocks** that create urgency;
  - **terrain-specific finds** that make the world matter;
  - **always-succeed crafting with graded quality** (Heliana), so a roll is never wasted.

---

## 4. Discovery systems

| System | How hidden properties are revealed | Reward |
|---|---|---|
| Skyrim | eat (first effect; more with the Experimenter perk); combine (shared effects); a failed mix still gives a little XP | the effect list fills in |
| Potion Craft | the map is fogged and travel clears it for good; unknown effects show as "?" bottles | the map itself is the codex |
| GW2 Discovery | a live counter of possible unknown recipes for the current mix | bonus XP on first craft; recipe saved |
| Witcher 1 | substances show on ingredients; matching secondary substances give a bonus potion | stronger brews |
| Strange Horticulture | read the book and inspect plants; there is always some distinguishing feature | labels, story progress |
| Botany Manor | clues about growing conditions found around the house | herbarium pages |
| Atelier | recipe colours show what is craftable; traits are inherited | encyclopedia entries (UNCONFIRMED detail) |

Two repeated lessons. First, **tell the player how close they are** (GW2's counter, Potion
Craft's visible path). Second, **make discovery permanent** (fog stays cleared, and a recipe is
saved after the first success).

---

## 5. Accessibility of timing minigames

- **Game Accessibility Guidelines** [P] https://gameaccessibilityguidelines.com/full-list/
  - Motor, intermediate: "Avoid repeated inputs (button-mashing/quick time events)."
  - Motor, advanced: "Do not make precise timing essential to gameplay – offer alternatives,
    actions that can be carried out while paused, or a skip mechanism."
  - Motor, intermediate: avoid held buttons, or provide alternatives.
  - General, intermediate: "Offer a means to bypass gameplay elements that aren't part of the
    core mechanic."
  - Motor and cognitive, basic: offer an option to adjust game speed.
  - Vision, basic: never convey essential information by colour alone. *This matters for the
    green/red zones and for dimming ineligible ingredients.*
  - Cognitive and vision: an option to hide background movement.
- **Xbox Accessibility Guideline 107** [P] https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/107
  - Avoid QTEs, long holds and simultaneous presses. Where unavoidable, offer a less demanding
    input or let players bypass the event.
  - Examples: **Gears 5** lets "Button Tap Challenges" use press-and-hold instead of taps. **The
    Long Dark**'s "accessible interactions" turn every press-and-hold into a single press.
    Activate controls on mouse-up so a misclick can be cancelled.
- **WCAG 2.2 (applies directly because the UI is web/Electron)** [P]
  - 2.3.3 Animation from Interactions: let users disable motion animation unless it is
    essential; `prefers-reduced-motion` is the named technique.
    https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html
  - 2.2.1 Timing Adjustable: for content time limits, offer turn off, adjust or extend, unless
    the timing is essential. https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html
- **Toggles shipped by games:**
  - Potion Craft Auto Hold [P].
  - KCD1 lockpicking easy mode, added post-launch [P].
  - Fae Farm "simple fishing": click to start reeling and click to stop, instead of holding. The
    setting is sourced; when it shipped is UNCONFIRMED.
  - Marvel's Spider-Man "Skip Puzzles" (since the 2018 game; Spider-Man 2 had it at launch).
    [S] https://www.gamesradar.com/dont-like-puzzles-marvels-spider-man-2-lets-you-totally-skip-them/
  - Stardew: no vanilla skip; a mod fills the gap [S].

---

## 6. What this suggests for the Herbalist revamp

Recommendations, not findings. Each one is tied to the evidence above.

1. **Keep the d20 as the authority on success.** Let the minigame only move quality within a
   band. The precedents are Stardew's perfect catch (+1 step) and Heliana's quirks by margin.
   Map the band to PF1e's own ladder: meet the DC, beat by 5, beat by 10 (UW yields). The
   minigame then shifts the result by at most one step.
2. **Let character skill change the minigame.** Ranks or mastery should widen the zone or slow
   the pointer (Skyrim, Stardew, KCD2) or add hints (Starfield). Start generous; Barone's regret
   is that his started too small.
3. **Offer a hands-off path from day one.** Call it "Steady hands" or "Let the character work":
   it resolves the quality step from the roll's margin alone, with no penalty, or at most capped
   at the middle tier. This is the GAG/XAG requirement, and Potion Craft, KCD1 and Spider-Man
   all added such toggles, mostly after launch.
4. **Handle repetition explicitly.** Repeat crafts of a mastered recipe should go through a
   recipe book or "Routine": no minigame, batch quantity, quality equal to the tier achieved
   before or to the margin tier. KCD2 dropping this is the cautionary tale. Witcher 3's
   "it is yours" refill and Monster Hunter's auto-craft are the far end of the same idea.
5. **Make grind a held quantity, not a reflex test.** Potion Craft's grind is how far you grind,
   chosen by the player. If grind uses rhythm clicks, keep it under ~10 s (Cooking Mama's
   length), allow hold-or-tap (Gears 5, Long Dark), and support Auto Hold.
6. **Never let the minigame consume ingredients on a timing miss** once the d20 has succeeded.
   PF1e already punishes failing the roll by 5 or more. A second penalty layer is the "two
   sources of RNG" trap WoW removed.
7. **Show eligibility by property as well as colour.** Use dimming plus a reason ("needs a
   bitter herb") and a GW2-style count of matches. Never colour alone (GAG vision basic).
8. **Don't add a quality tier to raw ingredients** unless it earns its keep. FFXIV removed
   gathered-material HQ to cut inventory bloat. Spoilage (UW: 24 h raw, 1 month prepared) gives
   urgency more cheaply.
9. **Make discovery permanent and visible.** Record properties learned by use in a
   herbarium/codex. This fits the owner's fog-of-war map wish, since Potion Craft's map is
   literally a fog-cleared codex.

---

## 7. Critic pass: what is weak or unconfirmed

Second pass over the claims above, flagging anything that rests only on summaries.

- **KCD2 has no autobrew.** This is a negative claim and cannot be fully proven. The evidence:
  - several Steam threads and mod pages say so;
  - the fextralife patch-notes digest through 1.5.3 lists no such feature;
  - I read only the Patch 1.2 notes directly on Deep Silver's site.

  The Steam threads themselves would not render (age gate). Treat this as **strongly supported,
  not primary-confirmed**. KCD1's Routine details come from community wikis, not Warhorse text.
- **"KCD2 boiling is easier than KCD1"** comes from guide and Steam snippets: secondary.
- **Potion Craft recipe-book auto-brew mechanics** ("brew one or more, uses noted ingredients")
  come from a search snippet; the fandom page returned 402. The Devlog #30 quote and the 2.0.2
  "save legendary recipes" lines come from the Steam news API (primary). *The claim that saving
  needs 5 prior brews belongs to Potion Permit, a different game. That snippet surfaced in the
  same search, so I left it out.*
- **Potion Craft haggling "moving arrow on a scale with zones"**: the devlog names arrow speed
  and scale-tilt speed as difficulty levers, so the mechanism is inferred from that list.
  Partially confirmed.
- **Potionomics:** whether a save-recipe feature was ever added is **UNCONFIRMED**.
- **Modern Atelier synthesis never fails:** **UNCONFIRMED**. The Marie/Elie failure model is
  secondary.
- **Monster Hunter World combining at 100% success:** comes from search summaries only.
  **UNCONFIRMED** as a Capcom statement, and Capcom's reason is unknown.
- **Mass Effect 3 removing minigames:** the removal is well established (wiki). The **reason is
  UNCONFIRMED**. The memory-limit claim is forum lore.
- **Outer Worlds' rationale:** **UNCONFIRMED**. Fan attribution only.
- **Skyrim Fortify Restoration fixed in 1.6:** **UNCONFIRMED** (snippet only).
- **Fable 2 blacksmith bar speeding up with stars:** **UNCONFIRMED** (GameFAQs only).
- **FFXIV:**
  - "Expert recipes resist macros" is a community characterisation, not a developer quote.
  - "Yoshida wants people to stop using macros" appeared in a forum post. **UNCONFIRMED**, and
    I left it out of the main text.
  - The Quick Synthesis HQ rate ("minimal") comes from the community wiki.
- **Witcher TRPG mechanics:** **UNCONFIRMED** (no rulebook access). Witcher 1's substance system
  comes from the fandom wiki (secondary).
- **D&D 5e herbalism kit DCs:** secondary; I did not check Xanathar's directly.
- **Ryuutama roll attributes:** sources disagree (STR+WIS vs STR+INT). **UNCONFIRMED** which is
  correct.
- **Stardew:**
  - Barone's quotes are confirmed through GameRant's write-up of a PC Gamer video interview. I
    could not load the PC Gamer page itself.
  - The bar pixel values come from the official-community wiki. That wiki is maintained by fans
    and is not authored by ConcernedApe.
  - An earlier fetch summary said "Training Rod introduced in 1.4." That is **UNCONFIRMED and
    likely wrong**, and is not used above.
- **Steam's "Playable without timed input" tag** is reportedly misused. That comes from one blog
  (https://access-ability.uk/2025/11/07/...) and I did not verify it.
- **WCAG 2.2.1 scope:** WCAG governs web content, not games. Applying it here is my
  interpretation, justified because the app's UI is web content. Whether a crafting minigame's
  timing counts as "essential" under the exception is a judgement call, not settled.
- **Hosoi's "graphical and fun" and "looping quality traits" lines** come from search snippets
  of the RPGSite/Noisy Pixel interviews, which I did not open. The Siliconera quotes were fetched
  directly.
- **Overcooked, Ostranauts:** I did not research them. They are not relevant enough to justify
  the time.
