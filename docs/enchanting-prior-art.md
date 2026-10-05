# Enchanting revamp: prior art sweep

Research for the Enchanter world class: putting magic onto weapons, armour, wondrous items and
possibly rings, wands and staves. It follows the herbalism and blacksmithing revamps
(`docs/herbalism-prior-art.md`, `docs/blacksmithing-prior-art.md`) and the decisions in
`docs/blacksmithing-revamp-plan.md` §1–§3: items built from material pieces with typed effects,
masterwork at Superior quality, the d20 decides success and a minigame climbs quality, properties
are discovered, and there is no random quality. The current design is in `docs/enchanting.md`.
Compiled 2026-10-04. Same conventions as the two earlier sweeps: primary sources (rulebook text
via Archives of Nethys or Paizo's PRD, developer posts, patch notes, official wikis, original
texts) are **[P]**. Major community wikis (UESP, minecraft.wiki, warcraft.wiki.gg) are **[W]**.
Fan wikis, press, forums and search snippets are **[S]**. Anything I could not trace is in the
critic pass at the end.

---

## 0. The headline findings

1. **In the printed rules, a smith can already enchant.** The Core Rulebook lets a crafter roll
   Craft (weapons) or Craft (armor) in place of Spellcraft for magic arms and armour. *Master
   Craftsman* (Core p. 130) lets a non-caster with 5 Craft ranks take Craft Magic Arms and Armor
   and Craft Wondrous Item, using ranks as caster level. Each prerequisite spell the crafter does
   not have adds +5 to the DC. The book also allows a spell to come "through another magic item or
   spellcaster". So `docs/enchanting.md`'s house rule (a potion stands in for knowing the spell) is
   close to the book already. The book's own route for a missing spell is +5 DC, not a refusal.
2. **The book's failure rule is a ready-made discovery hook.** Failing the creation check by 5 or
   more makes a **cursed** item. A curse stays hidden "unless the check made to identify the item
   exceeds the DC by 10 or more"; a plain success shows only "the magic item's original intent".
   Identifying uses Spellcraft against DC 15 + caster level, once per item per day.
3. **Paizo itself said the core system is too automatic.** *Pathfinder Unchained*: the standard
   rules "lead to automatic successes during crafting". Its optional answer gives each 5,000 gp of
   price one challenge, each with two tasks on different skills, and adds perks, quirks and flaws
   that detect magic does not reveal. Its perks and flaws are rolled at random by the GM, which this
   project refuses. Paizo also printed *Automatic Bonus Progression*, which deletes the plain +N
   ladder, and *Scaling Items*, so an old item is not "sold and forgotten".
4. **Every system that lasted caps how much magic one item holds, and ties the cap to the
   vessel.** PF1e caps a weapon at +10 total. PF2e allows as many property runes as the potency
   rune's value. Pillars of Eternity 1 gave every item a 12-point budget. Ars Magica prices the
   "opening" of an item by its material and size. Ultima Online lets a crafted *exceptional* item
   hold more imbuing weight than a normal one (armour 500 against 450). That last point is a direct
   precedent for "a Superior smith's piece holds more magic".
5. **Randomness in enchanting is the most walked-back thing in the genre.** Diablo IV removed
   masterworking failure before launch, added a scroll against bricked items in 2024 ("No more
   bricked items"), and in December 2025 let players choose the tempered affix. WoW replaced
   Inspiration for "a lack of decision making and agency for the crafter". Monster Hunter made
   decorations craftable. Minecraft added a per-player seed so offers stop rerolling. Path of Exile
   is the deliberate exception: it nerfed deterministic Harvest crafting to keep "the feeling of
   closing your eyes and Exalting an item". That reasoning depends on a trading economy that a
   single-player game does not have.
6. **Discovery comes in five tested shapes:** break an item to learn its magic (Skyrim, Kanai's
   Cube, Ultima Online's unravelling); learn a rune by using it (ESO's translation); learn by
   wearing (Final Fantasy IX); graded identification (PF1e Spellcraft); and research questions the
   world must answer (Earthdawn's Key Knowledges). Skyrim's developers said learning by breaking
   "allows us to separate enchanting from the other magical skills better" (search snippet).
7. **No mainstream game shipped a well-liked enchanting minigame.** Arx Fatalis's freehand rune
   drawing is remembered as "an exercise in frustration", though players liked the rune language.
   What players do like is **order as the craft** (Noita's wand slots, D2 runewords) and **matching
   material to effect** (Ars Magica's printed table: ruby +6 for fire, silver +10 against
   lycanthropes). History offers honest shapes: carve then stain (Egil's Saga), work only in the
   planet's hour (Key of Solomon), fill a magic square (Agrippa), hold the gilding heat in a window.
8. **The two studios that put PF1e most faithfully on screen both left magic arms and armour
   crafting out.** Owlcat's *Kingmaker* shipped without the item creation feats (a fan mod added
   them), and *Wrath of the Righteous* crafts scrolls and potions only. I found no stated reason.

---

## 1. PF1e rules: magic item creation, exactly

All quotes below were read from Paizo's own PRD pages (legacy.aonprd.com) or AoN, **[P]**.
The main page is the Core Rulebook's Magic Item Creation chapter, pp. 548–553:
https://legacy.aonprd.com/coreRulebook/magicItems/magicItemCreation.html and
https://www.aonprd.com/Rules.aspx?Name=Magic%20Item%20Creation&Category=Magic%20Items

### 1.1 The item creation feats

From the Core Rulebook feats page **[P]** https://legacy.aonprd.com/coreRulebook/feats.html

| Feat | Caster level | What it makes | Skill that may be rolled instead of Spellcraft |
|---|---|---|---|
| Scribe Scroll | 1st | scrolls | — (Spellcraft) |
| Brew Potion | 3rd | potions of "any 3rd-level or lower spell that you know and that targets one or more creatures or objects" | — |
| Craft Wondrous Item | 3rd | wondrous items; can also mend one "you could make" | the item's Craft, per item |
| Craft Magic Arms and Armor | 5th | magic weapons, armour, shields; can mend them | Craft (armor); Craft (weapons); Craft (bows) |
| Craft Wand | 5th | wands of "any 4th-level or lower spell that you know" | — |
| Forge Ring | 7th | rings | Craft (jewelry) |
| Craft Rod | 9th | rods | Craft (jewelry), Craft (sculptures), Craft (weapons) |
| Craft Staff | 11th | staves | Craft (jewelry), Craft (sculptures), Profession (woodcutter) |

The "skill used in creation" lines are from the creation page above. **A smith may roll Craft
(weapons) or Craft (armor) to make a magic weapon or armour.** That is printed, not a house
rule.

**Master Craftsman** (Core Rulebook p. 130) lets a non-caster in. Prerequisite: "5 ranks in
any Craft or Profession skill." Ranks "count as your caster level for the purposes of
qualifying for the Craft Magic Arms and Armor and Craft Wondrous Item feats", and "You must use
the chosen skill for the check to create the item. The DC to create the item still increases
for any necessary spell requirements." It cannot make "any spell-trigger or spell-activation
item" (so no wands, staves or scrolls). **[P]** same feats page.

### 1.2 The procedure

Quoted from the creation page **[P]**:

- **The check.** "The DC to create a magic item is 5 + the caster level for the item. Failing
  this check means that the item does not function and the materials and time are wasted.
  Failing this check by 5 or more results in a cursed item."
- **Missing prerequisites.** "The DC to create a magic item increases by +5 for each
  prerequisite the caster does not meet. The only exception to this is the requisite item
  creation feat, which is mandatory. In addition, you cannot create potions, spell-trigger, or
  spell-completion magic items without meeting their spell prerequisites."
- **Spells can come from elsewhere.** Prerequisites "take the form of spells that must be known
  by the item's creator (although access through another magic item or spellcaster is
  allowed)."
- **Caster level of the item.** "A creator can create an item at a lower caster level than her
  own, but never lower than the minimum level needed to cast the needed spell."
- **Cost.** "Magic supplies for items are always half of the base price in gp." For arms and
  armour the masterwork item's cost is added to the market price but "does not influence the
  base price (which determines the cost of magic supplies)". "The character must spend the gold
  at the beginning of the construction process."
- **Time.** "8 hours of work per 1,000 gp in the item's base price (or fraction thereof), with a
  minimum of at least 8 hours." Potions and scrolls of 250 gp or less can take 2 hours. "A
  caster can create no more than one magic item per day."
- **Hurrying.** Time can be "accelerated to 4 hours of work per 1,000 gp … by increasing the DC
  to create the item by +5."
- **Adventuring.** "he can devote 4 hours each day to item creation, although he nets only 2
  hours' worth of work … Work that is performed in a distracting or dangerous environment nets
  only half the amount of progress."
- **One at a time.** "A character can work on only one item at a time."
- **The workplace.** "a fairly quiet, comfortable, and well-lit place in which to work. Any
  place suitable for preparing spells is suitable."
- **Spell slots are spent.** For wondrous items, rods, rings and wands, "The act of working on
  the item triggers the prepared spells, making them unavailable for casting during each day of
  the item's creation."
- **Taking 10.** The Core text does not forbid it, and the general take-10 rule allows it when
  not threatened or distracted. That is a reading, not a quoted rule **[S]**. Unchained's own
  introduction (below) says the Core system "leads to automatic successes during crafting".

### 1.3 Weapons and armour

- **Masterwork.** "Only a masterwork weapon can become a magic weapon." "Armor to be made into
  magic armor must be masterwork armor." **[P]** creation page.
- **Tools.** "a heat source and some iron, wood, or leatherworking tools." **[P]**
- **Caster level.** "The creator's caster level must be at least three times the enhancement
  bonus … If an item has both an enhancement bonus and a special ability, the higher of the two
  caster level requirements must be met." **[P]** Whether this "special prerequisite" can be
  skipped for +5 DC is argued both ways on forums; I found no Paizo FAQ settling it.
- **Price.** Enhancement bonus squared × 2,000 gp for weapons (+1 2,000 gp … +10 200,000 gp)
  and squared × 1,000 gp for armour and shields. **[P]** Core Rulebook p. 468, via
  https://www.aonprd.com/Rules.aspx?Name=Magic%20Weapons&Category=Magic%20Items , and the
  "Armor bonus (enhancement) Bonus squared × 1,000 gp" line of Table: Estimating Magic Item Gold
  Piece Values on the creation page.
- **Caps.** Enhancement bonuses run +1 to +5. "A single weapon cannot have a modified bonus
  (enhancement bonus plus special ability bonus equivalents, including those from character
  abilities and spells) higher than +10." "A weapon with a special ability must also have at
  least a +1 enhancement bonus." With only an enhancement bonus, "the caster level is three
  times the enhancement bonus." **[P]** same page.
- **Special abilities as bonus equivalents.** Read from each ability's AoN entry **[P]**:

| Ability | Price | CL | Requires |
|---|---|---|---|
| Flaming | +1 | 10th | *fireball*, *flame blade* or *flame strike* |
| Keen | +1 | 10th | *keen edge* |
| Ghost touch (weapon) | +1 | 9th | *plane shift* |
| Holy | +2 | 7th | *holy smite*; creator must be good |
| Speed | +3 | 7th | *haste* |
| Dancing | +4 | 15th | *animate objects* |
| Vorpal | +5 | 18th | *circle of death*, *keen edge* |
| Ghost touch (armour) | +3 | 15th | *etherealness* |
| Shadow (armour) | **+3,750 gp flat** | 5th | *invisibility*, *silence* |

  Other +1s: frost, shock, bane, defending, merciful, thundering, spell storing. +2: unholy,
  anarchic, axiomatic, the bursts, disruption, wounding (CL 10). +4: brilliant energy (CL 16).
  **[S]** d20pfsrd list; wounding and brilliant energy checked on AoN.
  Some abilities are priced in **flat gold**, read from AoN **[P]**: shadow and slick +3,750 gp,
  glamered +2,700 gp (armour), impervious +3,000 gp (weapon, Ultimate Equipment p. 144). That a
  flat price sits outside the +10 cap is my reading: the cap counts "bonus equivalents" only.
- **Adding to an existing item.** "The cost to add additional abilities to an item is the same as
  if the item was not magical, less the value of the original item." For an item worn in a body
  slot, "the cost of adding any additional ability to that item increases by 50%." Core p. 553
  **[P]** https://www.aonprd.com/Rules.aspx?Name=Adding%20New%20Abilities&Category=Magic%20Item%20Creation
  So a +1 sword becomes a +2 sword for the difference: 8,000 − 2,000 = 6,000 gp market, 3,000 gp
  to make. **Upgrading is native to PF1e.**
- **Special materials.** Cold iron: the first magic enhancement costs +2,000 gp, once, not per
  ability. Noqual: "Any magic item incorporating noqual costs +5,000 gp to create." **[P]**
  https://www.aonprd.com/SpecialMaterials.aspx (already traced in
  `docs/blacksmithing-prior-art.md` §1.4).

### 1.4 Rings, wondrous items, wands, staves, rods, potions, scrolls

From the creation page and Table: Estimating Magic Item Gold Piece Values **[P]**:

- **Formulas.** Ability enhancement bonus² × 1,000; deflection bonus² × 2,000; resistance bonus²
  × 1,000; competence skill bonus² × 100; spell effect "Use-activated or continuous: spell level
  × caster level × 2,000 gp"; command word × 1,800; charges per day divide by (5 ÷ charges);
  "No space limitation: multiply entire cost by 2".
- **Multiple abilities.** Similar abilities on a slotless item: full price for the most costly,
  "75% of the value of the next most costly ability, plus 1/2 the value of any other abilities."
  Different abilities are added; "For items that take up a space on a character's body, each
  additional power not only has no discount but instead has a 50% increase in price."
- **"Use the item prices in the item descriptions as a guideline."** Rings, rods and wondrous
  items are priced by comparison, not formula. The book says outright that "other items require
  at least some judgment calls".
- **Wands.** 375 gp × spell level × caster level to make; "always fully charged (50 charges) when
  created"; fifty of any material component; spell of 4th level or lower.
- **Staves.** "A staff has 10 charges when created" and holds "a maximum of 10 charges". Each
  morning a caster can restore one charge by giving up a spell slot of the staff's highest
  level; "A staff cannot gain more than one charge per day". Minimum caster level 8th. Cost
  formula: 400 gp × highest spell level × caster level, plus 75% of the next, plus half of the
  rest **[S]** d20pfsrd. Staves page **[P]**
  https://legacy.aonprd.com/coreRulebook/magicItems/staves.html
- **Potions** 25 gp × spell level × CL; **scrolls** 12.5 gp × spell level × CL (both half of
  price). **[S]** d20pfsrd, consistent with the PRD's cost tables.

### 1.5 Cursed items: what failing by 5 makes

**[P]** https://legacy.aonprd.com/coreRulebook/magicItems/cursedItems.html

- "Cursed items are almost never made intentionally. Instead they are the result of rushed work,
  inexperienced crafters, or a lack of proper components."
- d% table: 01–15 delusion; 16–35 opposite effect or target; 36–45 intermittent functioning
  (unreliable 5% fail, dependent on a situation, or uncontrolled); 46–60 requirement; 61–75
  drawback; 76–90 completely different effect; 91–100 a specific cursed item.
- **A curse hides from identification.** "unless the check made to identify the item exceeds the
  DC by 10 or more, the curse is not detected. If the check is not made by 10 or more, but still
  succeeds, all that is revealed is the magic item's original intent."
- "Opposite-effect items include weapons that impose penalties on attack and damage rolls rather
  than bonuses."

### 1.6 Identifying: PF1e's own discovery rule

Spellcraft **[P]** https://legacy.aonprd.com/coreRulebook/skills/spellcraft.html

- "Identify the properties of a magic item using *detect magic*": DC 15 + item's caster level.
  It takes 3 rounds per item, and "you can only attempt to ascertain the properties of an
  individual item once per day. Additional attempts reveal the same results."
- An elf gets +2 to identify magic items.
- Combined with the curse rule above, identification is **graded**: succeed and you learn the
  intent; beat it by 10 and you also learn the curse.

### 1.7 Pathfinder Unchained: three optional systems that bear on this

All on Paizo's PRD, so Open Game Content **[P]**.

**Dynamic Magic Item Creation**
https://legacy.aonprd.com/unchained/magic/dynamicMagicItemCreation.html

- Why it exists: "The standard system for the creation of magic items presented in the Core
  Rulebook leads to automatic successes during crafting, and given enough days of downtime, it
  can lead to a wild power imbalance between PCs who opt into the crafting system and all other
  characters."
- Shape: "Prepare the vessel" first, "complete the item" last, and "one additional challenge per
  5,000 gp in the item's market price (minimum 1)" between. Each challenge offers **two tasks
  with different skills**, e.g. *Sesquipedalian elucidation*: Linguistics DC 15 + CL or Use
  Magic Device DC 20 + CL; *Ley line convergence*: Knowledge (arcana) DC 20 + CL or Knowledge
  (geography) DC 25; *Energy overload*: Fortitude DC 20 + CL or Craft DC 20 + CL. There are 23
  random challenges and 8 class-specific ones.
- "Creators can't take 10 or 20 … or benefit from aid another on item creation tasks."
- Prepare the vessel (Craft or Spellcraft, DC 15 + CL): critical success sets cost to 75% of
  market and time to 1 day per 2,000 gp; success 85% and 1 day per 1,000 gp; failure 100%, 1 day
  per 500 gp and **one flaw**; critical failure destroys the vessel.
- Complete the item: Use Magic Device DC 15 + CL **or** "Meet all the item's prerequisites". A
  failure here destroys the item.
- Results add **perks, quirks or flaws**: "These three types of adjustments give an item a
  distinct flavor that sets it apart from others of its kind." Examples: perk *Lightweight*,
  *Durable*, *Potent* (caster level +1); quirk *Noisy*, *Junky*, *Levitating*, *Loyal*; flaw
  *Heavy*, *Fragile*, *Pungent*, *Singing*. "For each flaw beyond the first, add a cumulative +5
  modifier to the d% roll until the item gains a curse."
- **Hidden properties:** "*detect magic* and *identify* typically don't reveal an item's perks,
  quirks, and flaws; *analyze dweomer* does, though only once the item is complete."
- The GM rolls perks, quirks and flaws **at random and in secret**. That is the part this
  project's "no random quality" rule refuses.

**Automatic Bonus Progression**
https://legacy.aonprd.com/unchained/magic/automaticBonusProgression.html

- Characters gain the "Big Six" numbers by level instead of by item: "allowing them to use magic
  item slots for more interesting items." Weapon and armour *attunement* gives +1 at 4th level
  up to +5 at 17th. "Magic weapons and armor do exist, but grant only special abilities, not
  enhancement bonuses." Wealth is halved.
- This is Paizo's own admission that the plain +N ladder is bookkeeping, not fun.

**Scaling Items**
https://legacy.aonprd.com/unchained/magic/scalingItems.html

- "Items come and go from each character's inventory with such frequency that they hardly have
  the chance to impact the game's story. Scaling items, however, increase in power along with the
  characters who carry them, allowing an old and cherished item to develop and retain its
  utility rather than being sold and forgotten."

### 1.8 Open Game Content and Product Identity

- Everything in §1.1–§1.7 is on Paizo's PRD (Core Rulebook, Ultimate Equipment, Unchained), which
  Paizo published as Open Game Content with proper names reserved as Product Identity **[P]**
  https://legacy.aonprd.com/openGameLicense.html . Most of the vocabulary (flaming, keen,
  vorpal, holy, ghost touch, the item creation feats) comes from the 3.5 SRD and was open before
  Pathfinder.
- Item names that carry a proper noun are the risk, exactly as for the bestiary
  (`docs/bestiary-licensing.md`): items named after people, deities or places of Golarion, and
  anything from Adventure Path or campaign-setting books, which are not on the PRD. Generic
  ability names are safe to use as mechanics. The skymetal names (noqual among them) are the
  open question already raised in the smithing sweep.

---

## 2. How games model enchanting

Each entry covers the loop, how magic is discovered, how power is gated, randomness, any
minigame, and what changed after launch.

### Morrowind (Bethesda, 2002)

All **[W]** https://en.uesp.net/wiki/Morrowind:Enchant unless marked.

- **Loop.** A filled soul gem, a spell effect you know, and an item. Enchant it yourself (free,
  can fail) or pay an NPC (always succeeds, expensive).
- **Discovery.** You can enchant only an effect you know as a spell.
- **Gating.** Each item has an enchantment capacity (most 1–20; the Daedric tower shield 225), and
  the soul's size caps the effects. Constant effect needs a soul of 400 or more, which only a few
  creatures have, held in a grand soul gem or the reusable Azura's Star.
- **The roll.** `%Success = (0.75 + %Fatigue/2) × (1 − 0.5 × ConstantEffect) × (Enchant + Int/5 +
  Luck/10 − 3 × EnchantPoints)`. A failure destroys the soul gem. Constant effect halves the
  chance.
- **Reputation.** The standard power route is soul-trapping Golden Saints into Azura's Star for
  constant-effect gear. **[S]** forums; UESP's exploits page returned 404.

### Oblivion (2006)

- **Loop.** Altars of Enchanting, mostly in the Arcane University, reached by rising in the Mages
  Guild. Choose a known effect, a soul and an item. Soul size alone sets the magnitude (Fortify
  Magicka 9 with a petty soul, 24 with a grand one). Apparel is always constant effect and takes
  one effect. Some effects are banned: "you cannot do a permanent Restore Health". There is no
  failure chance. **[W]** https://en.uesp.net/wiki/Oblivion:Enchanting
- **Sigil stones** from Oblivion gates carry an effect fixed at random when you pick the stone up,
  tiered by your level. Players save and reload to reroll it. **[W]**
  https://en.uesp.net/wiki/Oblivion:Sigil_Stone
- **Abandoned, in the developers' words.** "Enchanting is no longer a skill. We felt that was too
  unbalanced in Morrowind." **[P, transcribed on UESP; interviewee and date not given]**
  https://en.uesp.net/wiki/General:Oblivion_Fan_Interview_II

### Skyrim (2011)

- **Loop.** Disenchant a found item at an Arcane Enchanter to learn its effect, then enchant: an
  effect, a filled soul gem, a base item. Weapons use charges; armour is always on.
- **Discovery by destruction.** "When you disenchant an item, it will be destroyed and you will
  only learn the type of enchantment that it contained; the magnitude is irrelevant." Staves,
  artifacts "and even most unique items" cannot be disenchanted. **[W]**
  https://en.uesp.net/wiki/Skyrim:Enchanting
- **Why.** From the official fan interview, seen only as a search snippet: "You now learn enchanting
  effects by 'breaking down' a magic item you find, as opposed to them coming from spells you
  know. This allows us to separate enchanting from the other magical skills better." **[P via S,
  snippet]**
- **Gating.** "the magnitude of the enchantment(s) … will be scaled by the magnitude of the soul
  gem's soul." The Enchanter perk adds up to +100%. Extra Effect at skill 100 "allows you to add a
  second enchantment to an item only at the time of enchanting". **[W]**
- **The loop that broke it.** Fortify Restoration potions strengthened Fortify Enchanting and
  Fortify Alchemy gear, which made stronger potions, without limit. UESP credits the fix to "The
  Unofficial Skyrim Patch, version 1.3.0"; I found no Bethesda fix. **[W]**
  https://en.uesp.net/wiki/Skyrim:Fortify_Restoration
- No randomness in the crafting, no minigame.

### Elder Scrolls Online (ZeniMax Online, 2014–)

- **Loop.** A glyph is three runestones: **Potency** (strength and level), **Essence** (the
  effect) and **Aspect** (quality). Anyone can apply a finished glyph. **[W]**
  https://en.uesp.net/wiki/Online:Enchanting
- **Polarity.** Additive potency runes make armour glyphs, subtractive ones weapon glyphs, so the
  same essence means two things: Oko with additive is "Adds X Max Health"; with subtractive it is
  Absorb Health. Additive runes carry "ra" in their names, a hint before you can read them.
  **[W]** https://en.uesp.net/wiki/Online:Runestones
- **Discovery by translation.** Every rune starts untranslated. "If your character doesn't already
  know what the runestones do, you will learn their effects while creating the Glyph." **[W]**
  Making the glyph is the experiment; the cost is the runes.
- **Gating.** Aspect Improvement passive ranks I–IV open white/green, blue, purple, gold aspect
  runes. Potency Improvement plus level gates the potency tiers. **[W]**
  https://en.uesp.net/wiki/Online:Aspect_Improvement
- **Changed: patch 2.4.0 (25 April 2016)** **[P, transcribed on UESP]**
  https://en.uesp.net/wiki/Online:Patch/2.4.0
  - "Enchantment glyphs no longer have an upper limit on the equipment they can be applied to."
  - "All harvestable runestones will now provide at least one Essence and Aspect runestone per
    harvest."
  - "Potency runestones no longer need to be harvested, with every tier of both polarities now
    available for purchase from any enchanting vendor".
  - On the test server, removing potency runes from harvests entirely was softened after feedback
    (a one-in-three chance of a potency rune came back). **[S, snippet of the official forum]**
  - The aim, per that snippet: "every single harvest can translate into a completed glyph".

### World of Warcraft enchanting (Blizzard, 2004–)

- **Loop.** Disenchant unwanted gear into dust, essences, shards and crystals by its quality; spend
  them on permanent slot enchants. **[W]** https://warcraft.wiki.gg/wiki/Enchanting
- **Vellums.** Patch 4.0.1 (2010) replaced level-specific vellums with one Enchanting Vellum, so an
  enchant becomes a tradeable scroll. Kept ever since. **[W]**
  https://warcraft.wiki.gg/wiki/Enchanting_Vellum
- **Abandoned: enchant slots.** Head enchants went in 5.0.4; in *Warlords of Draenor* (6.0) only
  weapons, neck, cloak and rings could be enchanted. **[W]**
  https://warcraft.wiki.gg/wiki/Enchantments_by_slot . Community manager Lore, around BlizzCon
  2013: "We do want to slim down on the overall number of gems and enchants you'll need to put on
  your gear. That's primarily a quality of life change. We want to make it less of a hassle to
  equip a new item." **[P via S]**
  https://www.engadget.com/2013-11-15-will-fewer-gems-and-enchants-in-warlords-of-draenor-affect-profe.html
  Several slots came back in *Shadowlands*; I found no stated reason.
- **Abandoned: Inspiration.** The random quality proc was replaced by Concentration in *The War
  Within*. Blizzard, 18 April 2024: "There's a lack of decision making and agency for the
  crafter", "a lack of clarity for customers who just want items made", and "It's based heavily
  in RNG, which was never the goal of the Professions revamp." Concentration lets you
  "automatically reach the next level of quality". **[P]**
  https://www.bluetracker.gg/wow/topic/us-en/1833285-professions-update-concentration-in-the-war-within/
- **Shadowlands Runecarver:** legendary "memories" are earned from content, a profession makes the
  base item, and the player picks the power. **[P]**
  https://news.blizzard.com/en-us/world-of-warcraft/23548763/shadowlands-preview-forge-your-own-legendary-items

### Minecraft (Mojang)

- **Loop.** The enchanting table spends XP levels and lapis; bookshelves (up to 15) raise the
  maximum to level 30. The anvil merges books and items.
- **No discovery.** You do not learn enchantments; you receive random offers, find books, or buy
  them from librarians.
- **Randomness.** Weighted random picks, with a chance of extra enchantments. **[W]**
  https://minecraft.wiki/w/Enchanting_mechanics
- **Changed: 1.3.1** cut the maximum from 50 to 30 and the bookshelves from 30 to 15. **[W]**
  https://minecraft.wiki/w/Enchanting_Table
- **Changed: 1.8 (snapshot 14w02a).** "Enchanting now costs 1 to 3 levels of experience and lapis
  lazuli". "One of the enchantments is displayed in the tooltip." "The enchantments player would
  get do not change until they enchant it, or enchant something else. This enchantment seed is
  stored per player." A partial preview, and no more free rerolling. **[W]**
  https://minecraft.wiki/w/Java_Edition_14w02a . Mojang's reason was not found.
- **The anvil cap.** An operation costing 40 or more levels is "Too Expensive!" in Survival; each
  prior operation raises the cost (now 2ⁿ − 1). **[W]** https://minecraft.wiki/w/Anvil_mechanics
- **Librarians took over** after 1.14: almost any enchanted book can be bought, and a lectern can
  be broken and replaced to reroll the offer before the first trade. **[W]**
  https://minecraft.wiki/w/Trading
- **Tried and not shipped: the Villager Trade Rebalance** (experiment since 23w31a, 2023). Each
  village biome sells particular books, the best only from master librarians. minecraft.wiki
  paraphrases Mojang: librarian trades were "too overpowered compared to using an enchanting table
  or searching for enchanted books". The librarian part is still an experiment, not the default,
  as of the 26.1 snapshots. **[W]** https://minecraft.wiki/w/Villager_Trade_Rebalance
- **1.21 (24w18a)** made enchantments data definitions (supported items, weight, max level,
  exclusive sets, conditional effects). **[W]** https://minecraft.wiki/w/Java_Edition_24w18a

### Diablo II and Diablo II: Resurrected (Blizzard)

- **Loop.** Runewords: put specific runes, in a specific order, into a base item with exactly
  that many sockets. The runeword's fixed bonuses replace the base's own. The Horadric Cube
  combines items by recipe (three low runes make one higher; rerolls; crafted items).
- **Discovery.** Not taught in the game. Players read the recipes on Blizzard's own website, the
  Arreat Summit. **[P]** https://classic.battle.net/diablo2exp/items/runewords-110.shtml
- **Gating** is rarity: high runes are very rare. Outcomes are fixed apart from rolled ranges.
- **Changed.** Patch 1.10 made runewords Ladder-only; 1.11 opened them to everyone **[S]**.
  D2R repeated it: patch 2.4 added Ladder-only runewords, and 2.6 (February 2023) made "All
  Runewords and horadric cube recipes that were introduced in Patch 2.4" available in
  Non-Ladder. **[S, Maxroll's copy of the notes]**
  https://maxroll.gg/d2/news/patch-2-6-final-patch-notes

### Diablo III (Blizzard)

- **The Mystic was cut before launch** (announced January 2012) and returned in *Reaper of Souls*
  (2014). Fan sources give the reason as enchanting "wasn't adding any depth to the item game";
  I did not find the primary post. **[S]**
  https://www.gamespot.com/articles/diablo-iii-director-jay-wilson-on-crafting-artisans/1100-6273927/
- **Loop when it returned.** Pick one affix and reroll it from a short list. After that, only
  that affix can ever be rerolled on that item. Cost rises per attempt **[S]**.
- **Beta.** Old items were barred from enchanting. A community manager: "Artifacts of the old
  itemization system could become overpowered through enchanting." **[S quoting P]**
  https://blizzpro.com/2014/02/06/enchanting-controversy/
- **Auction House removed** 18 March 2014, because "it ultimately undermines Diablo's core game
  play: kill monsters to get cool loot". **[P]**
  https://news.blizzard.com/en-gb/article/10974978/diablo-iii-auction-house-update
- **Kanai's Cube** (patch 2.3) destroys a legendary item and keeps its power in a permanent
  collection; you then wear one weapon, one armour and one jewellery power from it. Destroy to
  learn. **[S]**

### Diablo IV (Blizzard): the clearest record of randomness walked back

- **Launch: the Occultist** rerolls one affix (D3's lock), with escalating gold cost. Season 2
  cut the escalation: "Subsequent Enchanting will continue to escalate at a significantly reduced
  rate". **[S reproducing notes]**
  https://www.icy-veins.com/d4/news/enchant-costs-reduced-in-diablo-4-season-2/
- **Season 4, Loot Reborn (2024)** **[P]**
  https://news.blizzard.com/en-us/diablo4/24077223/galvanize-your-legend-in-season-4-loot-reborn
  - **Tempering:** "As you find and learn Tempering Manuals, Blacksmiths across Sanctuary will be
    able to use these manuals". "Each Crafting Manual contains a small number of affixes". A roll
    picks one at random. "the Tempering Durability indicates how many times you can Temper an
    item". At zero the item can no longer be changed.
  - **Masterworking:** "at every 4th tier, massively upgrades one of your equipped affixes" (a
    random one). "you can reset and begin the process again."
- **Walked back, one step at a time:**
  1. On the Season 4 test realm, masterworking could fail. Before launch: "There is no longer a
     chance for Masterworking to fail". **[S reporting P]**
     https://www.wowhead.com/classic/news/masterworking-can-no-longer-fail-in-diablo-4-season-4-339193
  2. At the Season 4 Campfire Chat the developers still approved of "preserving the possibility of
     hard bricking items" but added extra tempering charges. **[S, Maxroll recap]**
     https://maxroll.gg/d4/news/season-4-campfire-chat-wrap-up
  3. *Vessel of Hatred* (October 2024) added a scroll to restore tempering charges. Lead game
     designer Rex Dickson: "No more bricked items." Once per item. **[S quoting P]**
     https://www.dexerto.com/diablo/diablo-4-vessel-of-hatred-introduces-new-item-to-limit-bricking-gear-2872151/
  4. Season 11 (patch 2.5.0, December 2025): you **choose** the tempered affix; only its value
     rolls. Restoration becomes unlimited. **[S]**
     https://blizzardwatch.com/2025/12/11/small-mighty-changes-diablo-4-patch-2-5-0/
  5. Season 11 also added *Sanctification*, a random permanent upgrade. Test-realm results that
     were downsides were changed to upgrades only before launch. **[S, search snippet]**
     https://gamerant.com/diablo-4-patch-250-notes-temper-masterworking-changes-sanctification-rng/
- **Pattern.** Over about eighteen months Blizzard removed the failure state, then the
  permanence, then the randomness of the choice. I found no Blizzard sentence giving the reason
  for step 4.

### Path of Exile 1 and 2 (Grinding Gear Games): the deliberate counter-example

- **Loop.** Currency orbs are the crafting tools (Chaos rerolls all, Exalted adds a random
  affix). Essences, fossils and the crafting bench narrow the odds. Bench recipes are found in the
  world.
- **Harvest, nerfed on purpose.** Chris Wilson, Development Manifesto, 10 March 2021 **[P]**
  https://www.pathofexile.com/forum/view-thread/3069670
  - "We're concerned by how deterministic some Harvest Crafts are and how easily players can craft
    near-perfect items."
  - "We don't want to take away the feeling of closing your eyes and Exalting an item, scared to
    see whether you ruined it or not."
  - "Why would I use a regular Exalted/Divine/Annul Orb when I can get one through Harvest that
    has a deterministic result?"
- **Why this is the opposite of Diablo IV:** PoE has a player trading economy and an endless
  chase. Determinism there flattens prices and ends the chase. A single-player game has neither.
- **PoE 2.** Jonathan Rogers: "Players will be encouraged to craft more frequently, including
  casually picking up items and using a Chaos Orb", with a focus on "midgame crafting as opposed
  to high end projects and perfect items." **[S, interview summary]**
  https://maxroll.gg/poe/news/wudijo-path-of-exile-2-interview-with-jonathan-rogers

### Owlcat's Pathfinder CRPGs: PF1e rules in a video game

- *Pathfinder: Kingmaker* (2018) shipped **without** the item creation feats. A fan mod adds
  Scribe Scroll, Brew Potion, Craft Wand, Craft Rod, Craft Wondrous Item, Craft Magic Arms and
  Armor and Forge Ring. **[S, the mod's own pages]**
  https://github.com/RobRendell/OwlcatKingmakerModCraftMagicItems ;
  https://www.nexusmods.com/pathfinderkingmaker/mods/54
- *Wrath of the Righteous* (2021) has crafting for **scrolls and potions only**. **[S]**
  https://pathfinderwrathoftherighteous.wiki.fextralife.com/Crafting
- I found **no Owlcat statement** saying why arms, armour and wondrous crafting were left out.
  The two studios that adapted PF1e most faithfully both declined this part of it.

### Pillars of Eternity 1 and 2 (Obsidian)

- **PoE 1:** any weapon or armour can be enchanted up to a point budget: "a maximum of 12 points
  … increased to 14 points" with *The White March Part II*. Each enchantment costs points by
  strength; quality steps (Fine, Exceptional, Superb) are enchantments too and can be replaced by
  a better one; other enchantments "cannot be removed". Higher quality needs character level 8
  (Exceptional) and 12 (Superb). **[W, the Official Pillars of Eternity Wiki, read through its
  MediaWiki API]** https://pillarsofeternity.fandom.com/wiki/Pillars_of_Eternity_enchantments
  This is PF1e's +10 cap in another costume.
- **Deadfire (PoE 2, 2018):** "Only items marked as "unique" can be upgraded with new
  enchantments." Each unique item has its own upgrade paths, often a choice of two that exclude
  each other. **[W, same wiki]**
  https://pillarsofeternity.fandom.com/wiki/Pillars_of_Eternity_II:_Deadfire_enchantments
  Players who missed enchanting any found gear complained on Steam **[S]**. I found no Obsidian
  statement of the reason.

### Ultima Online imbuing (Stygian Abyss, 2009)

All from the official UO wiki **[P]** https://uo.com/wiki/ultima-online-wiki/skills/imbuing/

- **Unravel to get ingredients.** Breaking a magic item down gives "Magical Residue, obtainable by
  an unskilled artificer", "Enchanted Essence, obtainable from 45.1 skill" and "Relic Fragments,
  obtainable from 90.1 skill", by the strength of the item.
- **Imbue a chosen property at a chosen intensity.** "An imbued item may have up to 5 properties
  in total." "The more properties, and higher intensities you try to squeeze into a piece the lower
  your percentage success chance." The chance is shown before you commit.
- **The vessel's quality sets the cap.** Each item type has a maximum total weight, and an
  *exceptional* (crafter-made) item holds more: armour 450 → 500, two-handed weapons 550 → 600.
- **Place matters.** Imbuing at the Royal City forge or the Queen's Soulforge raises the chance
  (78.5% at the Queen's Soulforge against 73.5% at a player's own, in the wiki's example).
- **Failure never destroys the item.** "Failure will cause the loss of some of your type one and
  type two resources."

### Baldur's Gate 3 (Larian, 2023)

- No general enchanting. Weapon coatings last a while. The Adamantine Forge makes a fixed item
  from a found mould, and there are only two mithral ores, so two uses a playthrough. **[S]**
- Fans report a crafting bench and enchanting in Early Access plans, with ingots and gems left as
  vendor trash. I found no Larian statement. **[S]**

### Kingdom Come: Deliverance 1 and 2

- No magic. Blade oils are alchemy. KCD1's Autobrew (Routine I perk, Alchemy 10) lets you skip
  the minigame for known recipes **[W]** https://kingdomcomedeliverance.wiki.gg/wiki/Autobrew .
  KCD2 removed it (see `docs/herbalism-prior-art.md` §0).

### Noita (Nolla Games)

- **Wand building.** A wand has capacity (slots), mana, cast delay, recharge and spread. Spells
  fire left to right, and a modifier changes the next projectile, so **order is the craft**.
  **[W]** https://noita.wiki.gg/wiki/Wands
- **Gated by place:** "Wands can usually only be edited while inside the Holy Mountain or with
  the Tinker with Wands Everywhere perk." **[W]**
  https://noita.wiki.gg/wiki/Tinker_with_Wands_Everywhere
- **Discovery:** a Progress list records spells you have seen. No minigame; the build is the
  puzzle.

### Dragon Age (BioWare)

- **Origins:** runes slot into weapons and armour at a camp NPC; they come out again at no cost.
  **Inquisition:** runes are crafted from schematics and slotted. **The Veilguard:** gear
  enchantments come from one NPC whose power grows with quest rewards. **[S/W]**
- Direction across the series: free, reversible slots → crafted schematics → one upgrade track.

### The Witcher 3 (CD Projekt Red)

- Runestones (weapons) and glyphs (armour) go into 1–3 sockets.
- **Hearts of Stone runewright** (an unnamed Ofieri craftsman) is a patron you invest in: 5,000,
  10,000 and 15,000 crowns unlock better tiers of runewords and glyphwords. The item must have
  three sockets; the enchantment replaces any runes in them and fills every slot. **[S]**
- **Correction to the brief:** Yoana is an unrelated armourer in Skellige; the runewright is not
  her husband.

### Final Fantasy VII and IX (Square)

- **FF VII materia:** materia sit in weapon and armour slots; *linked* slots pair a support materia
  with another. Materia grows with AP, and a mastered materia spawns a new copy. **[W]**
- **Remake and Rebirth:** mastered materia no longer spawn copies **[W]**. No developer reason
  found.
- **FF IX:** equipment teaches its ability while worn; after enough AP the character keeps the
  ability. **Learn by wearing.** **[W/S]**

### Monster Hunter (Capcom)

- **World:** decorations (skill jewels) were random drops, the best very rare. After complaints the
  Iceborne Elder Melder let players turn materials into chosen decorations; version 13.50 (April
  2020) widened the list. **[S reporting P]**
  https://www.siliconera.com/monster-hunter-world-iceborne-ver-13-50-adds-master-rank-kulve-taroth-and-elder-melder-features/
- **Rise:** decorations became craftable; talismans stayed random through the Melding Pot, with
  some modes letting you fix one skill. **Wilds** (August 2025) added "Appraised Talismans" with
  random skills as hard-quest rewards. **[S]**
- **Pattern:** the core build parts become chosen; one slot stays a lottery for the long tail.

### Enchanting minigames, gestures and odds

- **Arx Fatalis (2002):** about 20 runes with meanings, combined 2–4 at a time into about 50
  spells, **drawn freehand** with the mouse. Players liked the rune language and disliked the
  drawing: strict recognition, misreads, drawing under pressure. One retrospective calls it "an
  exercise in frustration". **[S]**
  https://www.superjumpmagazine.com/arx-fatalis-magic-was-ahead-of-its-time-and-technology/
- **Black & White (2001):** gesture casting. Peter Molyneux's postmortem lists it under "What Went
  Right" **[P]** https://www.gamedeveloper.com/design/postmortem-lionhead-studios-i-black-white-i-
  ; player reviews complain of misread gestures **[S]**. The developer and the players disagreed.
- **Two Worlds II (2010):** spells are built from cards (an effect, a carrier, modifiers) found in
  the world. Reviewers praised the depth and said "almost none of this is explained". **[S]**
- **Kingdoms of Amalur (2012):** sagecrafting combines shards into gems for typed sockets.
  Deterministic, no minigame. **[W]**
- **Atelier** synthesis grids: players lean on auto-fill as the puzzles grow fiddly. **[S]**
- **Pity counters.** Lost Ark's "Artisan's Energy" fills on each failed upgrade and guarantees
  success at 100%; Black Desert's failstacks raise the chance after each failure. **[S]**
- **Hidden odds are treated as deception.** In January 2024 Korea's Fair Trade Commission fined
  Nexon 11.6 billion won for secretly lowering MapleStory's Cube enhancement odds, some to zero.
  **[S]** https://www.gamedeveloper.com/business/maplestory-dev-nexon-fined-8-9-million-by-korean-regulator-for-misleading-players

---

## 3. Tabletop beyond PF1e

### D&D 5e: three editions, three answers

- **DMG 2014, pp. 128–129.** You need a formula, every spell the item casts, and a minimum
  level by rarity. Progress is 25 gp a day. **[S]** https://www.flutesloot.com/5e-crafting-magic-items/
  (I did not read the DMG page.)

| Rarity | Cost | Min. level | Days |
|---|---|---|---|
| Common | 100 gp | 3rd | 4 |
| Uncommon | 500 gp | 3rd | 20 |
| Rare | 5,000 gp | 6th | 200 |
| Very rare | 50,000 gp | 11th | 2,000 |
| Legendary | 500,000 gp | 17th | 20,000 |

- **Xanathar's Guide (2017).** A formula, plus an **exotic material won from a creature** whose
  CR scales with rarity (common CR 1–3, uncommon 4–8, rare 9–12, very rare 13–18, legendary
  19+), plus gold and workweeks (1, 2, 10, 25, 50). **[S]** (table reproduced in
  `docs/blacksmithing-prior-art.md` §4.)
- **2024 DMG / SRD 5.2.** Arcana proficiency plus the item's tool; time and cost by rarity:
  common 5 days / 50 gp, uncommon 10 / 200, rare 50 / 2,000, very rare 125 / 20,000, legendary
  250 / 100,000. Consumables half. **[P, D&D Beyond post; table S]**
  https://www.dndbeyond.com/posts/1836-help-your-players-get-crafty-with-the-2024-dungeon
- **The drift:** gold and spell slots (2014) → a quest for a monster part (2017) → skill and tool
  proficiency plus time (2024). In every version the DM decides whether the material exists. I
  found no designer statement of why. **[S]** https://www.wargamer.com/dnd/crafting-magic-items-2024

### Pathfinder 2e: runes

All **[P]** GM Core p. 224, https://2e.aonprd.com/Rules.aspx?ID=3162

- **Fundamental runes** carry the numbers: *weapon potency* +1 to +3 to hit, *striking* adds
  damage dice; *armor potency* and *resilient* for armour. Shields take *reinforcing* only.
- **Property runes** carry the named powers (flaming, ghost touch). "The number of property runes
  a weapon or armor can have is equal to the value of its potency rune."
- **Etching:** "You must be able to Craft magic items, have the item you're adding the rune to in
  your possession throughout the etching process, and meet any special Craft Requirements."
- **Transfer:** "The Price of the transfer is 10% of the rune's Price" and "It takes 1 day
  (instead of the 4 days usually needed to Craft)". Swaps must be like for like. Runestones hold a
  rune between items, and moving from one is free.
- **Automatic Bonus Progression** (GM Core p. 83) exists in PF2e too: potency by level, and
  items "provide unique special abilities rather than numerical increases". **[P]**
  https://2e.aonprd.com/Rules.aspx?ID=2741
- **Why runes.** A 2018 playtest article quotes a Paizo blog: "Good armor and a powerful weapon
  are still critical to the game, but you no longer have to carry a host of other smaller
  trinkets". **[S]** https://geekdad.com/2018/03/pathfinder-second-edition-first-impressions/
  The common claim that runes exist so you "keep your favourite weapon" I could **not** trace to
  a Paizo designer.
- **Reading:** the item is a chassis with a bounded number of slots. The +N rune sets how many
  named powers fit. Moving power between items is cheap.

### Ars Magica 5th edition

- **Licence.** Atlas Games released "the TEXT of the game books", 53 books including ArM5, under
  **CC BY-SA 4.0**; art, trade dress and some trademarked names are excluded. **[P]**
  https://www.atlas-games.com/arsmagica/openars . The rules can be adapted with attribution and
  share-alike.
- **Item types** (ArM5 ch. 8) **[P, Project Redcap's HTML]**
  https://www.redcap.org/page/Ars_Magica_5E_Standard_Edition,_Chapter_Eight:_Laboratory
  - *Lesser enchanted device:* one effect in one season; the lab total must be at least twice the
    effect level; one pawn of vis per 10 levels.
  - *Invested device:* first **opened** for a season with Vim vis equal to material × size, then
    filled effect by effect over many seasons.
  - *Charged item:* no vis; charges from how far the lab total beats the effect.
  - *Talisman:* attuned to its maker; only they can add to it.
- **Opening cost.** Material base: cloth or glass 1, wood or leather 2, bone 3, hard stone 4, base
  metal 5, silver 6, gold 10, semi-precious gem 12, precious gem 15, priceless gem 20. Size: tiny
  ×1 to huge ×5. **The vessel's material sets its capacity.**
- **Vis is typed** by Art (fire vis for fire effects): a coloured currency.
- **Shape and material bonuses** add to the lab total when they match the effect, capped by Magic
  Theory. From Atlas's official index **[P]**
  https://www.atlas-games.com/pdf_storage/ArM5IndexS&MbyShape.pdf : ruby +6 fire; iron +7 harm or
  repel faeries; silver +10 harm lycanthropes; lead +4 wards; sword +4 harm bodies; ring +2
  constant effect.
- **Lab texts** let another magus repeat an effect in one season, at a lower lab total.
- **Reading:** "match the material to the effect" is a skill, with a printed table of what helps
  what, and it is open-licensed.

### 13th Age (Pelgrane): items with temperaments

**[P, Archmage Engine SRD, read from the PDF]** https://pelgranepress.com/media/SRD/MagicItems.pdf

- "Each item has a personality that is largely defined by its quirk. What you can count on as a
  default is that nearly all magic items want to be used and used well."
- "you can handle a number of true magic items equal to your level. Items one tier above you count
  as two items". At or under that, quirks "tug at you … But you'll be in charge." Over it, "the
  magic items are, to some extent, running you."
- One item per body "chakra", each with a default bonus. No item-creation rules in the SRD.

### Earthdawn (FASA): discovery as play

**[S throughout; I could not reach a FASA primary]**

- To use a thread item's higher ranks you weave a thread to it, paying Legend Points.
- Each rank may need a **Key Knowledge**: first the item's Name, later its maker, its material,
  who commissioned it, its last owner. In 4th edition a successful Item History test reveals
  **the question**; the answer must be found through research or adventure. Some ranks need a
  **Deed**.
- **Reading:** the engine tells you what you do not know; the world holds the answer.

### RuneQuest and Mythras: the maker pays with themself

- RuneQuest: Glorantha: matrix creation costs 1 point of **permanent POW** per point of spell.
  **[P]** https://rqwiki.chaosium.com/rules/rune-spells.html
- Mythras: enchanting lowers the sorcerer's Magic Points attribute permanently; the points return if
  the enchantment is unmade or the object destroyed. **[S]**

### Shadowrun and Burning Wheel (brief)

- **Shadowrun 5e foci:** bonding costs karma = Force × a multiplier (power foci ×6). Bonded foci
  are capped by the Magic attribute. Making one needs a formula, a prepared object (telesma) and a
  lodge, and the maker takes Drain. Too much active Force risks **focus addiction**. **[S]**
  The official addiction text was not found.
- **Burning Wheel (Magic Burner):** imbuing must draw on a lore skill (Folklore, Ancient
  History, Astrology and others), and the power must relate to it. A new item's obstacle sums
  choices of vessel, name, source, effect and duration. **[S, forum quotes of the book]**

---

## 4. Folklore and history, for grounded minigames

Brief, and each with the shape it suggests. **[P]** here means the original text (in
translation); **[W]/[S]** as before.

| Source | What it says | Minigame shape |
|---|---|---|
| *Egil's Saga* ch. 44 **[P]** https://en.wikisource.org/wiki/The_Story_of_Egil_Skallagrimsson/Chapter_44 | Egill cuts his palm, carves runes on a poisoned horn and reddens them with blood; the horn bursts. | Carve, then redden, in that order. The staining wakes the carving. |
| *Egil's Saga*, Helga's sickness (Green, ch. LXXV) **[P]** https://sacred-texts.com/neu/egil/egil76.htm | A youth's mis-carved love-runes on whalebone make a girl ill. Egill shaves them off, burns the bone, and carves correct runes. His verse: no one should carve runes who cannot read them. | A wrong stroke backfires. Repair is unmake, burn, re-carve. Reading is the safety check. |
| *Hávamál* 144 **[P, Old Norse]** | Eight verbs: *rísta, ráða, fá, freista, biðja, blóta, senda, sóa* (carve, read, stain, test, ask, offer, send, spend). Translations vary; "stain" for *fá* is an interpretation. | An ordered ritual with a "test" step before release. |
| Kragehul I spear shaft **[W]** | "ek erilaz … muha haite, gagaga": "I, the rune-master, am called Muha", then repeated bind-runes. | The maker signs the work; a repeated sign is the charge. |
| Ulfberht swords **[S]** | About 170 blades marked +VLFBERH+T; the well-spelt mark goes with good steel, misspelt ones with poor blades (Alan Williams; the crucible-steel claim is disputed). | A mark can be forged: appraise the mark *and* test the metal. |
| Blade invocations (Wagner et al. 2009) **[S]** https://diva-portal.org/smash/get/diva2:289664/FULLTEXT01.pdf | Maker's name on one face, a blessing such as INNOMINEDOMINI on the other; abbreviated letter strings. | Two faces, two jobs. |
| *Wið færstice* (Lacnunga) **[W]** | Herbs boiled in butter; a knife dipped in it and laid on the pain. | Brew a medium, then dip the blade: a bridge from herbalism. |
| *Key of Solomon* (Mathers 1889) **[P via esotericarchives; parts via summary]** https://www.esotericarchives.com/solomon/ksol.htm | Planet metals: Saturn lead, Jupiter tin, Mars iron, Sun gold, Venus copper, Moon silver (Mercury uncertain). Colours per planet. Make pentacles in the planet's day and hour, with pure parchment and consecrated pens. | Match metal and colour to the power; act inside its hour; prepare a pure vessel first. |
| Planetary hours **[S]** | Day and night each split into 12 unequal hours; the first hour after sunrise belongs to the day's planet, then the Chaldean order (Saturn, Jupiter, Mars, Sun, Venus, Mercury, Moon). | A window computable from the game clock. Wait for it (time) or work outside it (difficulty). |
| Agrippa, *Occult Philosophy* II.22 **[P]** https://www.esotericarchives.com/agrippa/agrippa2.htm | Seven planetary magic squares. Saturn's 3×3 square sums to 15 on every line. A Jupiter table on silver, made under Jupiter, brings favour. | A number-placement puzzle, engraved on the right metal at the right time. |
| *Picatrix* (Attrell and Porreca, 2019) **[S]** | Talismans: a figure engraved on the planet's stone or metal at a chosen astrological moment. | Stone + figure + moment: a three-way match. |
| Greek Magical Papyri XII.270–350 **[S]** | A ring for "success and favor and victory": a gem engraved with Helios, consecrated at set lunar times, and woken with a spoken invocation each use. | Engrave, consecrate, then a spoken key to wake it (compare Earthdawn's Name). |
| Fire-gilding (Theophilus; Met Museum) **[S]** https://www.metmuseum.org/essays/fire-gilding-of-arms-and-armor | Gold–mercury amalgam brushed on; heated until the mercury fumes off (toxic); burnished. | Apply, hold the heat in a window, burnish. A hazard on the maker. |
| Ultramarine (Cennino Cennini) **[S]** | Lapis paste kneaded in lye; the first extraction is the deepest blue, each later one paler, down to "ultramarine ash". | Repeated draws from one batch, each a lower grade. You choose when to stop. |
| Iron gall ink **[S]** | Goes on pale and darkens over days; corrodes pens and, in time, the page. | A delayed reveal; wear on tools. |

**Not historical:** "dove's blood ink" appears only in modern occult-supply sources; I found no
medieval grimoire for it.

---

## 5. What to take

Recommendations, not findings. Each is tied to the evidence above. Where the current design
(`docs/enchanting.md`) is affected, I say so.

### 5.1 Keep the book's frame, and fix two places where the current design departs from it

- **The check.** The book's DC is 5 + the item's caster level, +5 per missing prerequisite, +5 to
  rush (§1.2). The circle mode's DC is 10 + 5 × essence rank instead. That is a house scale, which
  is fine, but it should say so, the way the book mode already does.
- **Missing spells.** The book mode refuses a working when the spell is neither known nor held in a
  potion. The book's own answer is **+5 DC** for arms, armour, rings and wondrous items. Refusal
  is right only for potions, scrolls, wands and staves ("you cannot create potions, spell-trigger,
  or spell-completion magic items without meeting their spell prerequisites"). Suggest: a potion
  removes the +5; without one, the working is harder, not forbidden.
- **The skill.** The book lets Craft (weapons) or Craft (armor) stand in for Spellcraft, and
  *Master Craftsman* turns Craft ranks into caster level for arms, armour and wondrous items. That
  is the printed bridge between the Blacksmith and the Enchanter.
- **Prices and caps stay exactly the book's:** bonus² × 2,000 (weapons) or × 1,000 (armour);
  enhancement +1 to +5; total +10; at least +1 before a property; caster level 3 × enhancement;
  half price to make; 8 hours per 1,000 gp; one item at a time. Cold iron's +2,000 on the first
  enhancement and noqual's +5,000 belong in the cost line, with the material named.
- **Upgrading is native.** "The cost to add additional abilities to an item is the same as if the
  item was not magical, less the value of the original item", +50% for a body-slot item. Unchained
  wrote *Scaling Items* because items were "sold and forgotten". A cherished sword that grows is
  already PF1e.

### 5.2 Capacity: the smith's quality sets how much the item holds

- Every lasting system caps magic per item (§0.4). The book's cap is +10 per weapon or armour.
- **Proposal:** the masterwork piece (Superior quality, as the smithing plan rules) unlocks
  enchanting at all, as the book requires. Higher smithing tiers raise a **capacity** inside the
  book's +10, never past it. Ultima Online's exceptional bonus (+50 weight on 450–550) is the
  precedent, and it is small. The focus capacity in `docs/enchanting.md` already does the same job
  on the enchanter's side; the two can be one number read from both crafts.
- PF2e's rule "property runes = potency value" is a readable alternative: the +N is the number of
  named powers the item can carry.
- **Material affinity** (Ars Magica): a material that suits the effect lowers the DC or widens the
  minigame window. Ars Magica prints the table; the smith's materials already carry typed
  effects, so iron against fey and silver against lycanthropes line up with the book's cold iron
  and alchemical silver.

### 5.3 Discovery: break, translate, identify

These fit the herbalism and smithing rules (tasting, assay, study, people, books):

- **Unravel** (Skyrim, Kanai's Cube, Ultima Online): destroying a found magic item teaches its
  property *type*, not its strength ("the magnitude is irrelevant"). The cost is the item. This is
  the enchanter's version of tasting.
- **Translate by use** (ESO): an essence or rune whose nature you do not know reveals itself the
  first time you bind it. The working is the experiment. ESO's hint in the name ("ra" marks
  additive runes) is a good way to give partial knowledge before the first use.
- **Identify, graded** (PF1e): Spellcraft DC 15 + caster level reveals the intent. Beating it by
  10 reveals a curse. Once a day per item.
- **Questions the world answers** (Earthdawn): for named or legendary items, the bench can tell the
  player *what* they do not yet know (its maker, its material) and the world holds the answer.
- **Learn by wearing** (Final Fantasy IX) is a fit for attunement-style items, if any.

### 5.4 Risk: chosen, shown, and never after a success

- **The d20 decides success; failure by 5 or more is a curse**, as printed. That keeps the book's
  only real risk and makes it a discovery problem: a cursed item looks like what you meant to make
  until someone identifies it by 10.
- **Show the odds before the roll** (Ultima Online shows the imbuing chance; Minecraft's 1.8
  preview). Hidden odds are treated as deception (the MapleStory fine).
- **Never destroy or worsen an item after a successful roll.** Diablo IV took eighteen months to
  undo exactly that. Ultima Online's failed imbue costs ingredients, never the item.
- **Refuse rolled perks and flaws.** Unchained's dynamic creation is the best tabletop source for
  item character, but its perks, quirks and flaws are rolled in secret. If items get quirks, they
  should come from the materials and from choices the player makes, which matches the smithing
  plan's rule that every material carries a negative.
- **A resource that buys a sure step** (WoW Concentration) is the accepted alternative to luck.

### 5.5 Minigames: order and matching, not freehand drawing

- **Avoid freehand drawing with strict recognition** (Arx Fatalis). If runes are traced, trace
  along a shown guide with generous tolerance, and keep the Steady mode the herbalism plan
  requires.
- **Order is the craft.** Hávamál's sequence (carve, read, stain, test), Egil's carve-then-redden,
  Noita's left-to-right wand slots, D2's rune order. A short ordered sequence with a test step
  before sealing is grounded and readable.
- **Timed windows from the world clock:** the planetary hour of the property's planet. Working
  inside it is easier; waiting costs game time. This uses the clock the herbalist already reads.
- **A number-placement puzzle** (Agrippa's magic squares; Saturn's 3×3 sums to 15) suits a
  higher-tier method, and it can be generous.
- **A heat window** (fire-gilding with powdered gold) borrows the smithing minigame's heat band.
- **Diminishing draws** (Cennini's ultramarine: each extraction paler) suit refining an essence:
  draw again for more, each draw weaker.

### 5.6 Things that must not feed back into themselves

- Skyrim's Fortify Restoration loop: gear that improves enchanting, made by enchanting, improved
  by potions, without limit. Items that buff the Enchanter's own check should not stack with each
  other, or should not apply to making the same kind of item.

### 5.7 World Bible and licensing

- **World Bible.** Fixes are world-agnostic. Essences, foci and material affinities should be
  optional fields in `docs/campaign-format.md`, so a world's own materials can carry an affinity
  (fire, warding, the dead) and its own named items can carry Earthdawn-style knowledge.
- **PF1e:** the Core Rulebook, Ultimate Equipment and Unchained text quoted here is on Paizo's
  PRD as Open Game Content. Proper names are the risk, as for the bestiary.
- **Ars Magica** is CC BY-SA 4.0. Using its *ideas* (material × size, affinity bonuses) is
  ordinary design borrowing; copying its *text or tables* would bring the share-alike terms. That
  is the owner's call, not this sweep's.

---

## 6. What others tried and abandoned

| Game or system | Tried | Abandoned or changed to | Source |
|---|---|---|---|
| Morrowind → Oblivion | Enchant skill with a failure roll that destroyed the gem | No skill, no failure; a Mages Guild perk. "too unbalanced in Morrowind" | [P via UESP] |
| Oblivion → Skyrim | Effects learned from spells you know | Effects learned by disenchanting found items, "to separate enchanting from the other magical skills" | [W]; reason [P via snippet] |
| Skyrim | Fortify Enchanting/Alchemy/Restoration loop | Fixed only by the community's Unofficial Patch | [W] |
| ESO | Potency runes only by harvesting; glyph level caps | All potency runes sold by vendors; no upper limit; every harvest makes a glyph (2.4.0, April 2016). Full removal from harvests softened on the test server | [P via UESP]; [S] |
| WoW | Many enchantable slots | WoD: weapon, neck, cloak, rings only: "less of a hassle to equip a new item". Some slots back in Shadowlands | [P via S] |
| WoW | Inspiration: a random quality proc | Concentration, a resource you spend for a sure step | [P] Apr 2024 |
| Minecraft | Max level 50, 30 bookshelves | 30 and 15 (1.3.1) | [W] |
| Minecraft | Free rerolls of table offers | Per-player seed, partial preview, lapis cost (1.8) | [W] |
| Minecraft | Librarians sell almost any book | Biome-limited trades tested since 2023, still not default | [W] |
| Diablo II / D2R | Ladder-only runewords | Opened to everyone (1.11; D2R 2.6) | [S] |
| Diablo III | The Mystic at launch | Cut in January 2012; returned in 2014 with a one-affix lock | [S] |
| Diablo III | Auction House | Removed March 2014: it "undermines Diablo's core game play" | [P] |
| Diablo IV | Masterworking could fail (test realm) | Cannot fail at launch | [S reporting P] |
| Diablo IV | Tempering with limited, permanent charges | Restore scroll (2024), then chosen affixes and unlimited restores (Dec 2025) | [S quoting P] |
| Diablo IV | Sanctification with downsides (test realm) | Upgrades only | [S] |
| Path of Exile | Deterministic Harvest crafting | Nerfed in 3.14 to keep the gamble ("closing your eyes and Exalting") | [P] Mar 2021 |
| Pillars of Eternity | Enchant any item within a 12-point budget | Deadfire: only unique items, on fixed upgrade paths | [W] |
| Monster Hunter World | Decorations by random drop only | Elder Melder lets you craft chosen ones (Iceborne, 2020) | [S reporting P] |
| FF VII → Remake | Mastered materia spawns a copy | No copies | [W] |
| Dragon Age | Free, reversible rune slots (Origins) | Crafted runes (Inquisition), then one upgrade track (Veilguard) | [S/W] |
| Owlcat PF1e CRPGs | The tabletop's item creation feats | Not shipped in Kingmaker; scrolls and potions only in Wrath | [S] |
| D&D 5e | Gold, spell slots and level minimums (2014) | A monster-part quest (2017), then skill and tool proficiency plus time (2024) | [S]; [P] D&D Beyond |
| PF1e → PF2e | Many "Big Six" numeric items | Runes on two items; ABP as a variant in both editions | [P] rules; reason [S] |
| PF1e Core → Unchained | Automatic, take-10 crafting | Optional challenges, perks, quirks, flaws | [P] |

**Worth refusing, with reasons:**

- **Random results after a successful roll**, and items bricked by bad luck (Diablo IV, WoW
  Inspiration). The project's rule already says no.
- **Secretly rolled perks and flaws** (Unchained's dynamic creation). Good flavour, wrong source of
  it here.
- **Freehand gesture recognition** as the core input (Arx Fatalis).
- **Endless rerolling against a random table** (Minecraft before 1.8, Oblivion's save-scummed
  sigil stones). Players will route around it, and the routing becomes the game.
- **A crafting output that boosts the same craft without a cap** (Skyrim).
- **Too many enchant slots per character** (WoW cut them as "a hassle").

---

## 7. Critic pass: what is weak or unconfirmed

I re-checked the strongest claims after drafting. Corrections made during the pass:

- **The brief's "Yoana's husband" runewright is wrong.** The Hearts of Stone runewright is an
  unnamed Ofieri craftsman; Yoana is an unrelated armourer in Skellige.
- **A summary said slick, shadow and glamered armour were "+2 bonus equivalents".** AoN prints
  flat prices: shadow and slick +3,750 gp, glamered +2,700 gp. Corrected; ghost touch armour is
  +3 (CL 15), also checked.
- **Unchained's critical success** is defined by tasks, not margins: one creator attempting one
  task gets success or failure; two creators attempting both get a critical success if both
  succeed. Read from the page text, not a summary.
- **My first draft named Thassilonian "runeforged" items** as a Product Identity example. I did
  not trace their source book, so the licensing line now speaks of Adventure Path and setting
  books in general.
- **Taking 10.** I first wrote that PF1e allows taking 10 on item creation. The Core text neither
  allows nor forbids it on that page; the general take-10 rule implies it. Marked as a reading.
- Re-fetched and confirmed against the primary page: the Path of Exile manifesto quotes, the
  Diablo III Auction House quote, the Diablo IV Season 4 blog's tempering and masterworking text,
  the Oblivion interview quote, the ESO 2.4.0 lines, the Skyrim disenchanting lines, PF2e's rune
  limit and transfer cost, Ars Magica's licence, and 13th Age's capacity rule (from the SRD PDF).
- Fan-wiki claims re-checked: Pillars of Eternity's 12/14-point budget and Deadfire's unique-only
  rule, through the official wiki's own page source; Ultima Online's imbuing, through the official
  uo.com wiki (unravel tiers, 5-property cap, exceptional weight caps, no item loss on failure).
  Owlcat: the base games' lack of arms and armour crafting is confirmed only by fan wikis and the
  mod's own pages; no Owlcat statement was found.

**Could not confirm**

- **PF1e:** whether the "caster level 3 × enhancement" special prerequisite can be bypassed for
  +5 DC (forums disagree; no Paizo FAQ found). The staff cost formula and potion/scroll per-level
  formulas came from d20pfsrd, consistent with the PRD's tables. The d20pfsrd list of +1/+2
  abilities was spot-checked on AoN for flaming, keen, ghost touch, holy, speed, dancing, vorpal,
  wounding and brilliant energy only.
- **Skyrim's design reason** for disenchanting comes from a search snippet of a fan transcription;
  the interviewee and date are unknown. The same for the Oblivion interview.
- **ESO:** the verbatim 2.4.0 rationale and the test-server walk-back (forum pages returned 403).
- **WoW:** Lore's quote reached me through Engadget, not a blue post; no reason found for
  restoring slots in Shadowlands; no verbatim Hazzikostas quote on Runecarver versus Legion.
- **Minecraft:** why lapis was added in 1.8; Mojang's own wording for the trade rebalance.
- **Diablo:** the primary post cutting the Mystic in 2012; the Mystic's cost formula; any Blizzard
  reason for making tempering deterministic in Season 11; masterworking changes in seasons 5–10.
  The Rex Dickson and Campfire quotes come through press and Maxroll recaps.
- **Path of Exile 2:** whether runes replace the bench, in a developer's own words.
- **Ultima Online:** the 2009 *Stygian Abyss* date for imbuing is from memory; the official wiki
  page does not give it. Later changes to imbuing were not researched.
- **Pillars, BG3, Owlcat, Monster Hunter, Final Fantasy:** no developer reason found for any of
  their changes. Tokuda's August 2025 letter returned 403.
- **Witcher 3:** whether runewright enchantments can be removed, and Blood and Wine's changes.
- **Dragon Age II** runes; Inquisition rune removal.
- **D&D 5e:** I did not read the 2014 DMG or Xanathar's directly; the 2024 table is from snippets
  that agree with each other.
- **PF2e:** no Paizo designer statement linking runes to "keep your favourite weapon".
- **Earthdawn:** no FASA primary reached; the Test Knowledge / Research Knowledge split is from fan
  sources.
- **Shadowrun** focus addiction rules; **Burning Wheel** permanence and failure rules.
- **Folklore:** the Key of Solomon's metal for Mercury and its ink recipes (sacred-texts returned
  403); the Ulfberht crucible-steel finding is disputed; Hávamál's "stain" is an interpretation
  of *fá*; "dove's blood ink" has no medieval source I could find.
- **Not researched:** Okami, Magicka, Hogwarts Legacy, Starfield, Fable, Arcanum, Dragon's Dogma,
  Avowed, Guild Wars 2.
