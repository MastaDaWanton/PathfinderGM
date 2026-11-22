# Item creation feats: a design study

Written 2026-11-22 on `integrate/0.5.1-impl`, for the owner to review and decide. **Nothing here is
built, and no code was changed.** This study looks at the nine PF1e item creation feats and asks
how each could fit the shape the owner chose for the craft revamps (herbalism, blacksmithing,
enchanting, alchemy, leatherworking). Each feat gets its book rule, what the app already does
that overlaps it, two to four options, a recommendation, and the questions only the owner can
answer. The cross-cutting questions come after the feats, and every owner question is numbered
again in §5.

Sources are marked as earlier sweeps marked them. **[P]** is primary: Paizo's PRD on
legacy.aonprd.com, Archives of Nethys (AoN), or the feat text in `content/feats/feats.json`,
which is the PRD's text. **[W]** is a major wiki. **[S]** is a fan wiki, forum, mod page or
search snippet. **[C]** is this repository's own code or documents, read for this study. §6
lists the claims I could not source.

---

## 0. The short version

- **Four of the nine feats are already done by a bench under another name.** Brew Potion is the
  alchemy bench. Craft Wondrous Item, Craft Magic Arms and Armor and Forge Ring are the
  enchanting circle working on vessels from the forge and the leatherworker. The enchanting plan
  says so in as many words: "The **item creation feat** is the class itself"
  (`docs/enchanting-revamp-plan.md` §4.2) **[C]**. The feats still sit in the picker, though,
  and they do nothing. The audit counts them among the 871 of 939 takeable feats that do nothing
  (`docs/implementation-audit-2026-11-22.md`) **[C]**.
- **Five have no item to make.** The catalogue (`content/materials/magic-items.json`) has 180
  rows: 26 weapon properties, 32 armour properties and 122 wondrous items, 17 of them in the ring
  slot. It has no wands, scrolls, staves or constructs, and only one rod: the immovable rod,
  already there as a slotless wondrous row (`mi-immovable-rod`). The one wand vessel material is
  retired, and its own text reads "Wand work leans on the spell side of the craft, which this
  bench does not model yet" **[C]**. The audit is right that no wands or scrolls exist.
- **The machinery a scroll or wand needs is mostly there already**:
  - the item cast door (`partial["item_cast"]`: the item's caster level and DC, no slot), which
    serves magic item powers, spell storing and the temple's paid castings;
  - per-day and one-use counts on item powers (`Actor.reset_item_uses`, `rules/finish_uses.py`);
  - the enchanter's reading of `holds_spell` off any carried stock (`enchanter._spells_held`);
  - the alchemy formula route "copied from a scroll", with its bench handler
    (`play/alchemy_views.py`, `source == "scroll"`).

  The routes are written, but no scroll exists to feed them **[C]**.
- **Recommendation in one line:** build a **spell-item layer** in two steps, scrolls first and
  wands second, as new methods on the enchanting circle. Give each feat one concrete job: a
  caster's own route, or a caster-level stand-in. Take Craft Staff, Craft Rod and Craft
  Construct out of the picker for now, with the reasons given in their sections. The owner
  decides every part of this.

---

## 1. What the app has now (verified in code, 2026-11-22)

### 1.1 The craft shape the owner chose

These rules come from the memory notes and the five world-class documents in
`content/world-classes/`:

- **Crafts are world classes.** Anyone may take one, whatever their class
  (`grantable_at_creation: true`). Each has three fixed levels and then endless levels, with two
  perk picks a level (potency, duration, quality, yield, plus one craft-specific perk). Craft XP
  is 100 for level 2, 260 for level 3, and a flat 400 for every level after, in every craft
  except enchanting (ruling 2026-11-18). Enchanting keeps thresholds 25/65 and a 50 + 10n step.
- **Benches with methods.** Each method is its own d20 check followed by an always-played
  minigame (order, matching, timed window, heat), and the score picks a quality tier under the
  level's ceiling (Crude, Sound, Fine, Superior, Flawless, then +1, +2). Superior and above is
  masterwork. Skill checks at a bench have no natural 1 or 20 (CRB p.180), except the 2026-11-18
  ruling that a natural 20 breaks the quality cap.
- **In Progress.** Any step of an hour or more goes into an In Progress list with a countdown on
  game time (2026-11-18). There is no limit on how many works are in progress (enchanting round
  4). Enchanting counts the book's 8 working hours to a calendar day (`magic_layer.HOURS_PER_DAY`).
- **Materials and essences.** Enchanting is paid in essences (1 mote = 100 gp). Alchemy is paid
  in ingredients only, with no coin when bottling (pricing ruling 2026-10-07). Material rarity
  gates level: L1 common and uncommon, L2 rare and exotic, L3 legendary.
- **Recipes, manuals and renown.** Formulae and recipes are learned from experiment, writings,
  teachers and taking a potion apart. Manuals weigh 1 lb and are read at the bench. Renown and
  deeds are a world system that crafts only feed.
- **Every successful craft pays** (no repeat cap; 2026-10-05). **Typed crafting** makes the base
  item through narration, with a real roll and a real item, and points to the bench for anything
  finer (2026-10-28). Enchanting is always referred to the circle.
- **Tradecraft.** Half the character's Craft ranks add to the matching bench (owner option A,
  2026-10-07).

### 1.2 Magic items, enchanting and potions

- **Enchanting** (`rules/enchanter.py`, `rules/magic_layer.py`). The work runs Prepare, then
  Attune, then Bind on a vessel the smith or the leatherworker made. Products are arms, armour,
  wondrous items and rings (enchanting round 3). Enchanter level is the caster level. Each
  prerequisite spell that is neither known nor carried in a potion or scroll adds +5 DC, and an
  Enchanter level below the item's caster level adds another +5: it is never a refusal (round 1,
  round 4 point 4). A carried potion or scroll holding the spell meets the prerequisite and is
  spent (`binder_of`). Capacity is floor(level / 2), at least +1, plus quality and perks, with no
  ceiling. A miss by 5 or more makes a flawed item with a hidden curse.
- **Alchemy** (`rules/formulae.py`, `rules/alchemist.py`). The owner's own rules: a potion holds
  **any** spell, personal range included, overruling the book's 3rd-level cap and its "targets
  one or more creatures" clause. The highest spell level is max(1, floor(Alchemist level / 2)).
  Brewing time follows the Brew Potion feat. Quality raises caster level only.
- **Round 1's fact holds: alchemy bottles only spells whose every part the engine runs**
  (`formulae._executable_all`). Lane B's honest reading of 2026-11-22 left 145 derived spell rows
  plus the 44 authored potions; 280 spells that once derived a potion no longer do, because a part
  of each is told rather than run (`docs/research/2026-11-22-lane-b.md`). That "280 lost
  potions" call is still with the owner.
- **Spells overall** (audit): 376 FULL, 345 PARTIAL, 2,317 NARRATED. A PARTIAL or NARRATED spell
  can still be **cast**. Its run parts resolve, and its told parts reach the narrator as riders
  "for the GM to see" (`spells.casting_plan`) **[C]**. A cast, in other words, is not held to the
  every-part rule that a bottle is. This matters for scrolls (§3.2).

### 1.3 Scrolls, wands, staves, rods, constructs

| Thing | In the app | Evidence **[C]** |
|---|---|---|
| Scrolls | **None.** No item, no shop row, no maker. Three readers wait for one: the alchemy scroll route, the enchanter's `holds_spell` reader, and the wizard text "copied into the book from a scroll or another book". I found no code that copies a spell into a spellbook. | `formulae.LEARN_ROUTES["scroll"]`, `play/alchemy_views.py`, `casting.py` |
| Wands | **None.** A retired material `wand-vessel` (200 gp, "a masterwork wand blank of coldwood or bone"). | `content/materials/enchanter-materials.json` |
| Staves, rods | **No staves.** "Staff" in the code means a quarterstaff, or a keeper's staffing. **One rod**: the immovable rod, a slotless wondrous row (levitate, CL 10, 5,000 gp). | grep; `magic-items.json` `mi-immovable-rod` |
| Constructs | **20 golems in `content/bestiary/core.json`** as stat blocks (Bone through Wood Golem), with no construction lines. Owner house rule (2026-10-01): a broken construct can be mended with Craft or Knowledge (engineering), and a second, harder check "rewrites its loyalty so it becomes yours". | `content/rules/repairs.json` |
| Use Magic Device | No resolved use: "There are no wands or scrolls to activate yet, so nothing calls for it." | `content/rules/skills-explained.json` |
| The feats | All nine are takeable, and all are NARRATED with the reason "item-creation". The wizard class grants Scribe Scroll at 1st level (`content/classes/wizard.json`), and so does the Rune domain (`content/domains/powers.json`). Two of the owner's saves hold Scribe Scroll. Master Craftsman is PARTIAL: "neither feat gates any bench here". | audit JSON |

---

## 2. The book, and what others did

### 2.1 The PF1e rules that bind every feat [P]

From the Core Rulebook's Magic Item Creation chapter
(https://legacy.aonprd.com/coreRulebook/magicItems/magicItemCreation.html), already quoted in
`docs/enchanting-prior-art.md` §1:

- **The check:** DC 5 + the item's caster level. A failure wastes the time and materials, and a
  failure by 5 or more makes a cursed item.
- **Missing prerequisites:** +5 DC for each one, but the item creation feat itself "is
  mandatory". Also: "you cannot create potions, spell-trigger, or spell-completion magic items
  without meeting their spell prerequisites". Spells may come "through another magic item or
  spellcaster".
- **Cost:** materials are half the base price, paid up front.
- **Time:** 8 hours per 1,000 gp, at least 8 hours. Potions and scrolls of 250 gp or less take 2
  hours. "A caster can create no more than one magic item per day." Hurrying the work costs +5
  DC. While adventuring, 4 hours of work nets 2 hours.
- **Spells are spent:** for armour, weapons, rings, rods, staves and wondrous items (and, in
  similar words, wands), working on the item "triggers the prepared spells". For potions and
  scrolls, the spell is unavailable until the caster rests.
- **Prices** (half of each is the cost to make):
  - scroll: 25 gp × spell level × caster level (https://legacy.aonprd.com/coreRulebook/magicItems/scrolls.html);
  - potion: 50 gp × spell level × caster level;
  - wand: 750 gp × spell level × caster level, with 50 charges (https://legacy.aonprd.com/coreRulebook/magicItems/wands.html);
  - a 0-level spell counts as half a level;
  - a material component is added per use, so 50 times over for a wand.
- **Using spell items:**
  - A scroll is spell completion: the spell must be on the reader's class list, the reader needs
    the spell's ability score, and a reader whose caster level is below the scroll's makes a
    caster level check (DC scroll CL + 1). If that check fails, a DC 5 Wisdom check avoids a
    mishap. The writing vanishes when used (scrolls page).
  - A wand is spell trigger, with 50 charges and spells of 4th level or lower (wands page).
  - A staff is spell trigger with 10 charges at most. It uses "the wielder's ability score and
    relevant feats to set the DC", and the wielder's caster level if higher. A caster restores
    one charge a morning by giving up a spell slot of the staff's highest level, and its minimum
    caster level is 8th (https://legacy.aonprd.com/coreRulebook/magicItems/staves.html).
  - "Anyone can use a rod." Rods are priced one by one (a metamagic rod is 3/day, lesser at 3rd
    level or lower); there is no formula, and the cost is half the price
    (https://legacy.aonprd.com/coreRulebook/magicItems/rods.html).
- **Copying a scroll into a spellbook:** "a spell successfully copied from a magic scroll
  disappears from the parchment", and "a failed Spellcraft check does not cause the spell to
  vanish". The wizard spends 1 hour studying the spell first (https://www.aonprd.com/Rules.aspx?ID=237).
  The app's `LEARN_ROUTES["scroll"]` already says `spends: on_success` **[C]**, which matches.
- **Master Craftsman** (CRB p.130, feats page): a character with 5 Craft or Profession ranks
  counts those ranks as caster level for Craft Magic Arms and Armor and Craft Wondrous Item only.
  The chosen skill must be used for the creation check, and the DC still rises for missing
  spells. The feat cannot make "any spell-trigger or spell-activation item".

### 2.2 Paizo's own variants [P]

- **Unchained, Dynamic Magic Item Creation** (https://legacy.aonprd.com/unchained/magic/dynamicMagicItemCreation.html).
  Paizo's reason: the core system "leads to automatic successes during crafting". The variant
  prepares a vessel, meets one challenge per 5,000 gp with two skill choices each, then
  completes the item, and the result picks up perks, quirks or flaws. The app's enchanting circle
  already has this shape (a prepared vessel, steps, a minigame for quality) without the GM's
  random rolls.
- **Unchained, Automatic Bonus Progression** (https://legacy.aonprd.com/unchained/magic/automaticBonusProgression.html):
  the Big Six bonuses come with level. It bears on wands only indirectly; it is Paizo admitting
  that magic gear is bookkeeping.

### 2.3 Other games

- **Owlcat, *Pathfinder: Kingmaker* (2018).** The earlier enchanting sweep recorded that it
  shipped without the item creation feats. The fan mod's README names only Brew Potion, Craft
  Wondrous Items and "Craft Arms and Armor"; Craft Rod and Craft Construct appear only as
  open to-do items (https://github.com/RobRendell/OwlcatKingmakerModCraftMagicItems) **[S]**.
  The Nexus page (https://www.nexusmods.com/pathfinderkingmaker/mods/54) returned 403, so the
  mod's full feat list and the claim about the base game are **unsourced here**. Owlcat gave no
  reason that I could find. The mod's to-do list records the trouble that follows from
  upgradable bonded items: a sell-and-re-equip exploit, and enchantments that stack **[S]**.
- **Owlcat, *Wrath of the Righteous* (2021)** crafts **scrolls and potions only**, plus story
  artefacts from recipes. It needs Brew Potion or Scribe Scroll, a kit (an Alchemist's Kit or a
  Scroll Scriber's Kit), and a learned recipe. A search snippet also gave tiered scriber's kits
  by spell level, which the wiki page I read did not show. A party member with the
  caster level does the work in camp "free time", rolling Knowledge or Lore against a DC, with a
  second character helping (https://pathfinderwrathoftherighteous.wiki.fextralife.com/Crafting)
  **[S]**. Owlcat's dev diary #8 covered "potion brewing and scroll scribing" in the camp system
  (https://rpgcodex.net/article.php?id=11891, summary only) **[S]**. The wiki lists no wands. The
  WotR "copy scroll into spellbook" UI is well known but I did not source it here. The design
  point stands without it: **the studio that adapted PF1e most faithfully kept the two consumable
  feats and dropped wands, rods, staves, rings, wondrous items and arms.**
- **Neverwinter Nights (Hordes of the Underdark)** has Scribe Scroll, Brew Potion and Craft
  Wand. The caster casts the spell onto a blank (a scroll, a bottle, or a wand carved from a bone
  dropped by skeletons) and pays gold and **XP**: a wand costs CL × spell level × 750 gp and × 30
  XP. Spells from feats or special abilities cannot be used (https://nwn.fandom.com/wiki/Craft_wand;
  https://netheril.net/w/index.php/Wand_Making) **[W]/[S]**. The blank as a crafted material is
  the precedent for "the vessel comes from another craft".
- **PF2e** (Player Core, https://2e.aonprd.com/Skills.aspx?ID=37) **[P]**. There are no item
  creation feats per item type. One skill (Crafting) plus the Magical Crafting skill feat covers
  everything. A formula cuts set-up from 2 days to 1 and is needed for uncommon items. Materials
  are half the price up front, and each extra day of work pays down the rest. On a failure the
  materials are salvaged. **A wand is cast once a day**, and can be overcharged once more at the
  risk of breaking (https://2e.aonprd.com/Rules.aspx?ID=3218, GM Core p.282) **[P]**. A basic
  wand needs "a spellcaster expending a spell slot", and "You can't make a wand from a spell that
  comes from another magic item" (same) **[P]**. These were first read through a search snippet
  and then confirmed by the critic pass. PF2e abandoned the 50-charge
  wand outright. The PF1e "wand of cure light wounds" healing economy is the usual reason given,
  but **I could not find Paizo stating that reason**, so treat it as community lore.
- **Foundry VTT, PF1 system**: its changelog (10.5) says "Consumable creation now copies sources
  from the spell to the created item", so the system makes a consumable straight from a spell
  (https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/raw/master/CHANGELOG.md)
  **[P, changelog]**. I could not confirm the UI (drag a spell, pick potion, scroll or wand) or its
  pricing code from a primary page. The design point is that the spell document is the item's
  document, which is the app's own `spells.effects_at` reuse for potions.
- **The enchanting sweep's earlier findings still hold** (`docs/enchanting-prior-art.md` §0):
  - Every lasting system caps an item by its vessel.
  - Randomness in enchanting is the thing most often walked back.
  - Players like order and matching as the craft, and dislike freehand drawing (Arx Fatalis).

---

## 3. The feats, one at a time

Each section gives the book rule, what overlaps it, the options, a recommendation, and the owner
questions (Q numbers run on in §5).

### 3.1 Brew Potion (caster level 3rd)

**Book.** A potion of any 3rd-level or lower spell you know "that targets one or more creatures
or objects". It takes 2 hours if the base price is 250 gp or less, otherwise 1 day per 1,000 gp.
Materials cost half the base price. You set the caster level, which can be no higher than your
own. "Whoever drinks the potion is the target" (feats.json).

**Overlap: complete.** The alchemy bench bottles any spell (the owner's Q4.3 rule), at spell
level max(1, floor(Alchemist level / 2)), at the Brew Potion time, paid in ingredients only. The
spell is learned as a formula (from writings, a teacher, or a potion taken apart), not "known" as
a caster knows it. The alchemy questions doc already records the gap: "Non-casters cannot brew
potions at all" by the book (`docs/alchemy-questions.md`). The owner's answer was to let
everyone brew through the class.

**Options.**
- **A. The caster's route (fold it in, the feat as a perk).** A holder may cast a spell they know
  into the bottle at the alchemy bench. The cast **replaces that spell's essences in the
  formula** and spends the slot or prepared spell, which is the book's "the spell is expended".
  The holder needs no learned formula for a spell they can cast. Their spell-level cap becomes the
  higher of the Alchemist cap and min(3, the highest spell level they can cast). The Bottle method
  is still the Alchemist roll and the minigame. This reads the same pattern as the enchanter's
  `binder_of`, where a source of the spell stands in.
- **B. A head start into the class.** The feat grants Alchemist level 1, or the mastery XP for
  it, and the four starting classics. This is simple, but it duplicates what
  `grantable_at_creation` already offers at creation.
- **C. Cut it from the picker.** Mark it N/A ("the alchemy bench is this feat"), and give every
  current holder a free retrain on load. This is honest, but it removes a book feat a 1e player
  expects to see.

**Recommendation: A**, because it gives a caster a real reason to hold the feat (no essences to
gather for a spell they cast) and keeps the bench as the one door. Make C the fallback if the
owner wants fewer moving parts. The every-part rule still applies, because the result is a
potion: a cast spell with a told part still cannot be bottled.

**Owner questions:** Q1 (A, B or C); Q2 (does the 3rd-level book cap apply to the caster's
route, or does your own any-level rule extend to it?).

### 3.2 Scribe Scroll (caster level 1st)

**Book.** A scroll of any spell you know. It takes 2 hours if the base price is 250 gp or less,
otherwise 1 day per 1,000 gp. Materials cost half the base price (25 gp × spell level × caster
level). Only a reader with the spell on their class list can use it (or a Use Magic Device
check). A reader below the scroll's caster level makes a caster level check, with a mishap on
failure. A wizard may copy a scroll into the spellbook, and the scroll is spent on success.

**Overlap: none for making, three readers waiting for using.** Every wizard gets this feat at
1st level, the Rune domain grants it, and two saves hold it. It does nothing today.

**Options.**
- **A. A Scribe method at the enchanting circle (recommended).** The parchment is the vessel,
  bought or made: vellum is a leatherworker product from harvested hides, which is a natural
  hand-off. The inks are the cost: ink is already an enchanting material, and the spell's
  essences come from alchemy's derivation table (`alchemy-essences.json`), the same table that
  says what a spell is made of. The steps are Prepare (rule the sheet) and Bind (write the
  spell), with an order or timed-window minigame (calligraphy: the strokes in order, no
  freehand). Quality raises caster level, as alchemy's does. Works of an hour or more go In
  Progress. Enchanter L1, with the spell-level cap max(1, floor(Enchanter level / 2)), the same
  curve as alchemy's.
  - **The feat's job:** the caster's route, as in Brew Potion A. A holder who casts the spell
    into the writing pays no spell essences, needs no learned formula, and spends the slot. A
    wizard therefore scribes at 1st level, as the book intends, with no Enchanter levels.
  - **Typed crafting:** "I scribe a scroll of mage armour" makes a base scroll (Sound quality)
    through the typed-craft path, with the real roll and the real item, and points to the circle
    for finer work.
- **B. The feat alone, at any quiet place, with no world class.** Only casters scribe, only
  spells they know, the book's cost in coin and ink, one roll, In Progress for the time. This is
  the WotR shape. It is cheaper to build, but it is the one craft with no levels, no minigame and
  no quality, which breaks the owner's pattern.
- **C. Its own world class (a Scribe or Scrivener).** This is the purest form of the shape, but
  it is a sixth craft built for one product. Alchemy already owns single-use products, and
  enchanting already owns the spell side and the ink.

**What any scroll needs, whichever option makes it**:
1. A scroll item kind. It is a `Stock` row with `holds_spell`, a caster level, and a how of
   "read" rather than "drink". `Stock` already has the fields (`rules/crafting.py`).
2. A read door through the item cast door: the reader casts at the scroll's caster level, with
   the item DC (10 + spell level + the minimum ability modifier, the rule `_use_power` already
   cites), no slot, a standard action that provokes as casting does, and the writing gone.
3. The class-list, tradition and ability-score checks. If the reader's caster level is lower,
   the caster level check against DC scroll CL + 1, then the DC 5 Wisdom mishap check.
4. Use Magic Device for everyone else, which gives that skill its first resolved use.
5. The wizard's copy door. The alchemy route already copies a formula from a scroll. A spellbook
   copy (DC 15 + spell level, 1 hour of study plus writing time, the ink cost, the scroll spent
   on success, one try a week; I did not re-check the writing time, which I believe is 1 hour
   per spell level)
   is the same shape, and `casting.py`'s text already promises it.
6. Shops. As with the 44 classic potions, stock a fixed classic list of scrolls, scaled by the
   settlement's base value.

**The every-part rule.** A scroll is a **cast**, not a bottled effect, so it can honestly hold any
spell the cast door accepts, at the same fidelity as casting it from a slot (§1.2): run parts
run, and told parts go to the narrator as tells. Under that reading a scroll of a NARRATED spell
is as honest as casting it, and nothing more. The stricter choice is alchemy's rule (FULL spells
only). It would leave the scroll catalogue at roughly the 145 + 44 potion set, and wizards could
not scribe most of their book. This is Q4.

**Recommendation: A**, with the feat as the caster's route. Scrolls come first of all the spell
items: they are the cheapest, they bring three dormant readers to life, and they give every
wizard's 1st-level feat a meaning.

**Owner questions:** Q3 (A, B or C); Q4 (do scrolls hold any castable spell, or only FULL
spells?); Q5 (does a non-caster enchanter scribe scrolls they cannot read, by formula and
essences, as an alchemist bottles spells they cannot cast?).

### 3.3 Craft Wand (caster level 5th)

**Book.** A wand of any 4th-level or lower spell you know, with 50 charges. It takes 1 day per
1,000 gp. It costs half of 750 gp × spell level × caster level, plus any material component
fifty times over. A wand is spell trigger, so the class list or Use Magic Device decides who can
use it.

**Overlap.** None for making. The retired `wand-vessel` row and the round 3 answer ("Wands,
staves and scrolls wait for a later pass (charges and spell use)") both expected one. Per-use
counts on item powers exist (`uses`, `uses_count`, `reset_item_uses`).

**Options.**
- **A. The book's wand, at the circle (Enchanter L2).** A wand blank is a vessel: a masterwork
  rod of coldwood or bone, from the leatherworker's harvested bone or a woodworker. It is
  attuned with the spell's essences × 50 charges' worth of motes and bound through the circle's
  ordinary Bind (DC 5 + CL, the curse on a miss by 5). It goes In Progress for the book's days.
  Fifty charges, each a use through the item cast door. The feat is the caster's route, as in
  §3.1 and §3.2.
- **B. PF2e's wand.** One cast a day, plus one overcharge at the risk of breaking. The per-day
  use machinery already exists. This removes the 50-charge stockpile (a wand of cure light
  wounds as a party's whole healing economy), but it departs from the book on a core item.
- **C. Cut wands (the WotR choice).** Scrolls and potions cover single uses. Wands mostly add
  cheap, repeated healing, and the owner already guards against that farming: a deed in
  `deeds.json` is "gated per person per day so a wand of cure light wounds cannot farm it".

**Recommendation: A, built after scrolls,** because the owner has ruled strict-book on every
close call this autumn (drinking in a fight, nonlethal coup de grace), and the 50 charges are
the book. B is the fallback if the playtest shows wands flattening healing. The vessel comes
from another craft, as every enchanting vessel does (the NWN bone blank is the precedent).

**Owner questions:** Q6 (A, B or C); Q7 (who makes the wand blank: leatherworker bone, the
forge, or a bought blank only?).

### 3.4 Craft Staff (caster level 11th)

**Book.** "Any staff whose prerequisites you meet". It takes 1 day per 1,000 gp, costs half the
base price, and holds 10 charges. Each spell costs the charges its staff's own entry lists
(the page gives no general rule; the entries I saw ran from 1 to 3). A caster restores one charge
each morning by giving up a spell slot of the staff's highest level. A staff uses the
**wielder's** ability score, relevant feats and caster level (if higher) (staves page).

**Overlap.** None. It is the only PF1e item that runs on its wielder's casting numbers. The item
cast door takes its caster level and DC from the item today, so a staff would need a new branch
there.

**Options.**
- **A. An Enchanter L3 method on a quarterstaff vessel from the forge,** after wands, with
  recharging as a morning choice that spends a slot through the existing slot machinery.
- **B. Out of the picker for now (N/A, "no staves yet"), revisited after wands ship.**
  - Caster level 11 is far above where the owner's games are played. The saves the audit
    read hold low-level characters; I did not tabulate their levels.
  - Its value is the wielder's own casting, which needs the new door branch above.
  - Paizo prices staves one by one, so each staff is a hand-authored catalogue row.
- **C. Fold staves into wands:** a "staff" as a multi-spell wand with 10 charges and no
  recharge. This loses what makes a staff a staff.

**Recommendation: B**, keeping A as the design to build when wands exist. Hiding the feat is
better than a feat that does nothing.

**Owner questions:** Q8 (B now and A later, or A in the same pass as wands?).

### 3.5 Craft Rod (caster level 9th)

**Book.** Rods take 1 day per 1,000 gp and cost half the base price. Each is priced one by one:
metamagic rods (3 uses a day; lesser for spells of 3rd level or lower, at 3,000 to 35,000 gp),
the immovable rod, the rod of lordly might. "Anyone can use a rod" (rods page). A rod is
therefore not a spell item; it behaves like a wondrous item held in the hand.

**Overlap.** Most of the shape exists. Rods would be **catalogue rows** in `magic-items.json`
(kind `rod`, a held slot) on a vessel from the forge, bound at the circle like any wondrous
item, under the existing wondrous price rule ("ceil(sqrt(gp / 2000))" capacity, round 1).
Metamagic is implemented (lane C, `metamagic.chosen`). The item cast door deliberately applies
no feat ("An item's power applies no feat"), but a rod changes the wielder's own slot cast, not
an item cast, so it would hook the slot cast's metamagic choice: a rod use counts as the feat for
that cast without raising the slot.

**Options.**
- **A. Fold into enchanting as catalogue rows.** The immovable rod is already one (a slotless
  wondrous row), which shows the shape works. Start with the six lesser metamagic rods
  (Empower, Enlarge, Extend, Maximize, Quicken, Silent). Rods are Enchanter L2, since their
  prices fall in the rare band and above.
- **B. Out of the picker until A is built**, the same as staves.
- **C. Cut rods as a class of item** and keep only the metamagic idea, as an Enchanter perk. That
  is not book; I do not recommend it.

**Recommendation: A, with no new bench and no new item kind beyond a held slot.** The feat
itself has the same job as the other permanent-item feats (§3.6). Until A is built, the feat
leaves the picker (B).

**Owner questions:** Q9 (rods now as circle catalogue rows, or later?).

### 3.6 Craft Wondrous Item (CL 3rd), Craft Magic Arms and Armor (CL 5th), Forge Ring (CL 7th)

These three are taken together, because the app already answers all three with one bench.

**Book.** Each makes its family (wondrous items; magic weapons, armour and shields on a
masterwork item you supply; rings) at 1 day per 1,000 gp, for half the base price in materials.
Each can mend a broken item of a kind you could make, for half the cost and half the time.
Master Craftsman lets a smith with 5 ranks in place of caster level take the first two, though
never Forge Ring.

**Overlap: complete for making.** The circle makes all three families, on vessels the forge and
the leatherworker made. A forged piece of Superior quality is masterwork, so "a masterwork item
that you provide" is the forge's Superior tier. The Enchanter track stands in for the feat
(enchanting plan §4.2). Rings are 17 catalogue rows in the ring slot, bound like any other
wondrous item. **One part of the book is missing: mending a broken magic item.** I found no
magic-item mend door; the repair rows in `repairs.json` cover constructs.

**Options.**
- **A. The caster-level stand-in (recommended).**
  - Holding the matching feat lets the holder's **own caster level** stand in for Enchanter
    level in the circle's caster-level term, whenever it is higher. That removes the +5 for an
    item above their Enchanter level and nothing else: capacity, rarity bands and quality
    ceilings still come from Enchanter level.
  - The book gates these feats by caster level, and the app replaced caster level with Enchanter
    level for everyone. A real caster with the feat has a real caster level, so this is the book
    put back for the people it was written for.
  - Master Craftsman then becomes FULL with no extra work: its ranks count as caster level for
    the first two feats, as printed.
- **B. A family speciality.** The holder gets a flat bonus at Bind for items of that family, as
  Skill Focus gives one to a skill. It is simple, but the number is invented.
- **C. Out of the picker ("the circle is this feat"), with a free retrain for holders.** This is
  the current state made honest.

**Add, whichever option:** a **Mend** method at the circle that restores a broken item of a
family the enchanter could bind, for half the motes and half the days (the book's own rule). It
would be the first magic-item repair in the app. It is optional, but it is in all three feats'
text.

**Recommendation: A**, with Mend as a follow-up lane.

**Owner questions:** Q10 (A, B or C); Q11 (build Mend?).

### 3.7 Craft Construct (caster level 5th, plus Craft Magic Arms and Armor and Craft Wondrous Item)

**Book.** "Any construct whose prerequisites you meet". Animating takes 1 day per 1,000 gp of
market price. The materials are half the base price **plus the full cost of the body**, and each
construct has its own construction line (Bestiary, Craft Construct). Examples from the golem
page (https://legacy.aonprd.com/bestiary/golem.html) **[P]**:
- **Flesh golem:** a body of 500 gp in unguents, Craft (leather) or Heal DC 13, CL 8th; animate
  dead, bull's strength, geas/quest and limited wish; price 20,500 gp, cost 10,500 gp.
- **Stone golem:** a 5,000 gp stone body, Craft (sculpture) or Craft (stonemasonry) DC 19, CL
  14th; price 105,000 gp, cost 55,000 gp.

**Overlap: partial and different.** The 20 golems are stat blocks without construction lines.
The owner's house rule already gives a way to **own** a construct: mend a broken one, then
rewrite its loyalty (`repairs.json`). A built construct would be a companion actor that obeys
its creator ("recognizes its creator intuitively and obeys all commands", quoted in
`repairs.json`). That runs into two rulings: companions obey **in character** by spoken orders
(2026-10-01), and a lone PC's encounters are budgeted below their level: APL −2 by the
2026-11-13 ruling, which the code cites (`docs/encounter-budget.md`, `rules/ontheway.py`), and
APL −1 by the 2026-11-18 revision recorded in my notes. Whether the code has the revision yet I
did not check. Either way, a CR 7 flesh golem ally changes that budget.

**Options.**
- **A. Body at a craft bench, animation at the circle.** The forge, the leatherworker, or a
  future stone bench builds the body from the construction line's skill and DC. The circle binds
  it with essences worth half the price. It goes In Progress for the days. The result is a
  claimed construct, through the claim path that already exists. This needs construction lines
  authored for each golem, and that table is a content job.
- **B. Out of the picker for now; the mend-and-claim house rule remains the construct route.**
  Revisit it with the companions and cohorts work, which the audit lists as not in any lane.
- **C. Cut it.** Constructs as built allies stay out of the game.

**Recommendation: B.** The feat's prerequisites (two other item feats) only make sense once §3.6
is decided. The data is missing. The encounter-budget question is the owner's alone.

**Owner questions:** Q12 (B, or A when companions and cohorts are designed?); Q13 (does a
built construct count toward the party's encounter budget like a companion?).

### 3.8 Out of scope, but in the same feat type

The feats file tags two more item creation feats: **Inscribe Magical Tattoo** (Inner Sea Magic,
not takeable: its prerequisites cannot be read) and **Demon Grafter** (an Adventure Path feat).
Neither is studied here. The audit counts eight item creation feats; feats.json tags eleven.

---

## 4. Cross-cutting questions

### 4.1 Do the feats stay feats, or become world-class levels or perks?

The owner's shape makes the **world class** the maker: levels, perks, bench, quality. A book feat
that duplicates the class is either a dead pick or a second door. The recommendation gives every
surviving feat **one job the class cannot do: the book's caster put back**.
- **Spell items** (Brew Potion, Scribe Scroll, Craft Wand): the caster's route. A spell they
  cast replaces that spell's essences and spends the slot. The craft roll, the minigame and
  quality are still the class's.
- **Permanent items** (Craft Wondrous Item, Craft Magic Arms and Armor, Forge Ring, later Craft
  Rod): the holder's caster level stands in for Enchanter level in the caster-level term.
- **Not built yet** (Craft Staff, Craft Rod until its rows exist, Craft Construct): out of the
  picker, marked N/A with the reason in words. Holders get a free retrain on load, which the
  migration pattern already supports.

None of them becomes a world-class level or an endless perk. A perk is something every
crafter of that class can pick; the feats are about being a caster, which a perk cannot make
you. **Q14.**

### 4.2 Cost and time

| | Book | App today | Proposed for spell items |
|---|---|---|---|
| Cost | Half the base price in gp, up front | Essences (1 mote = 100 gp) at the circle; ingredients only at the alchemy bench (owner 2026-10-07) | Scrolls and wands at the circle: ink, plus the spell's essences sized to half the book price in motes (a 1st-level CL 1 scroll costs 12.5 gp to make, a fraction of a mote; Q15 decides whether cheap scrolls round up to one phial or charge coin for the ink) |
| Time | 8 h per 1,000 gp, at least 8 h; 2 h for a potion or scroll of 250 gp or less; one item a day | In Progress for any step of 1 h or more; 8 working hours to a day; no limit on works in progress; Hurry for +5 DC exists (`magic_layer.plan(hurry=)`) | The same: a 2 h scroll goes In Progress (the 2026-11-18 rule), a wand counts book days. The book's "one item per day" is already overruled by "no limit on works in progress"; keep that consistent |
| Slots | Spells "triggered" each day of the work (wondrous items, rods, rings, wands) | Never spent: the Enchanter level stands in | Spent only on the caster's route, once, when the spell is cast into the item |

### 4.3 Caster level and prerequisite spells

- **The book refuses** a spell-completion or spell-trigger item (scrolls, wands, staves) without
  its spell. **The app never refuses at the circle** (+5 a missing spell) and **lets formula plus
  essences replace the spell** at the alchemy bench.
- For scrolls and wands, the alchemy shape is the consistent one: a learned scroll or wand
  formula, and the spell's essences. A missing formula is a refusal, since there is nothing to
  write; a missing spell is not, because the essences are the spell. The caster's route is the
  book's shape, for casters. The Enchanter level caps the spell level, like the Alchemist cap.
- **Item caster level:** the default is the minimum to cast the spell, raised by quality as in
  alchemy, and never above the maker's Enchanter level, or caster level on the caster's route.
- **Q16:** accept this, or keep the book's refusal for spell-trigger and spell-completion items
  even at the circle?

### 4.4 Should a wand and scroll layer exist at all?

**Yes for scrolls, yes later for wands,** and here is what it buys:
1. **Use Magic Device** gets its first resolved use (activate a scroll or wand blind, emulate a
   class or ability score). Without spell items the skill should leave the honesty ledger as
   "cut", not "not yet".
2. **Wizards grow their books** the way the book intends, by copying scrolls; today the only
   source is the level-up picks.
3. **The alchemy scroll route** and the enchanter's "a scroll stands in for a missing spell"
   come alive with no new code on their side.
4. **Non-casters** get spell utility through Use Magic Device, which is the skill's purpose in
   1e.

What it costs:
- a new item kind, a read door and a trigger door on the existing item cast door;
- the class-list check;
- the mishap table;
- shop rows;
- a Scribe method, and later a wand method, at the circle;
- one minigame (calligraphy as order), plus parchment and blank vessels from other crafts.

It is a lane or two, not a revamp. The risk is wand-driven healing (§3.3). **Q17:** build the
layer, or record UMD as cut?

### 4.5 The three laws

- **One vocabulary.** A scroll and a wand are tagged item kinds (`item.scroll`, `item.wand`, and
  `item.staff`, `item.rod` later) beside the existing `property.*` and `metal` tags. Every door
  asks `has_state` or the tag prefix, never a name. "Is this a scroll" is
  `has_tag("item.scroll")`, not a match on "scroll of" (the regex in `compile_block._OF` is the
  bestiary loot reader's and must not become the rule). The spell-completion and spell-trigger
  activation methods are tags too (`activation.completion`, `activation.trigger`), so Use Magic
  Device asks one question.
- **One applicator.** A read or a zap is a **cast through `_op_cast` with `item_cast`**, the door
  magic item powers, spell storing and temple castings already use. Every number it makes is an
  `ActiveEffect` stamped `origin: item:<id>`, and removing it removes its contribution. Charges
  are use counts on the item record, as `uses_count` is today, not a second store. The caster's
  route spends its slot through the existing slot machinery, once. The caster-level stand-in in
  §3.6 is a term in `magic_layer.plan`'s DC, the one place the DC is built, with its own named
  line on the working card ("your caster level 7 stands in").
- **Severed tells.** Every scribe, read, zap, mishap and copy emits a tell; the narrator never
  learns a charge count, DC or caster level except through those tells. A model never writes a
  scroll into being: typed scribing goes through the code-only `make` path, as typed crafting
  does, and prose that claims a scroll the engine did not make is a contradiction the read-back
  already catches (`beat-makes-item`).
- **Validators.** A scroll or wand formula row is refused at load if its spell cannot be cast
  (an unknown id), if a wand's spell is above 4th level, or if its price is not the book formula.
  Each refusal names the fix, as `formulae.formula_problems` does.

---

## 5. Questions only the owner can answer

1. **Brew Potion:**
   - A, the caster's route (a cast spell replaces its essences and spends the slot);
   - B, the feat grants Alchemist level 1;
   - C, out of the picker with a free retrain.
   I recommend A.
2. Does the caster's route for potions keep the book's 3rd-level cap and its "targets a
   creature" clause, or does your own any-spell rule extend to it?
3. **Scribe Scroll:**
   - A, a Scribe method at the enchanting circle, with the feat as the caster's route;
   - B, the feat alone, WotR-style, with no world class;
   - C, a new Scribe world class.
   I recommend A.
4. Do scrolls hold **any castable spell**, at the same fidelity as casting it, or only spells
   whose every part the engine runs (alchemy's rule)? The second leaves roughly the potion set
   (145 derived plus 44 authored), and most wizard spells could not be scribed.
5. May a **non-caster** enchanter scribe scrolls they cannot read (formula and essences), as an
   alchemist bottles spells they cannot cast?
6. **Craft Wand:**
   - A, the book's 50 charges at the circle, Enchanter L2, after scrolls;
   - B, PF2e's once a day plus overcharge;
   - C, no wands.
   I recommend A, with B as the fallback.
7. Who makes a **wand blank**: the leatherworker's harvested bone, the forge, a woodworker, or a
   bought blank only?
8. **Craft Staff:** out of the picker now and built after wands (my recommendation), or in the
   same pass as wands?
9. **Craft Rod:** rods as circle catalogue rows (the six lesser metamagic rods and the immovable
   rod first) now, or later? Out of the picker until then?
10. **Craft Wondrous Item, Craft Magic Arms and Armor, Forge Ring:**
    - A, the holder's own caster level stands in for Enchanter level in the caster-level DC term,
      which also makes Master Craftsman work as printed;
    - B, a flat bonus at Bind for that family;
    - C, out of the picker.
    I recommend A.
11. Build a **Mend** method at the circle (a broken magic item for half the motes and half the
    days)?
12. **Craft Construct:** out of the picker now, with mend-and-claim as the construct route (my
    recommendation), or built (body at a craft bench, animation at the circle) when companions
    and cohorts are designed?
13. If constructs are ever built, does one count toward the party's encounter budget like a
    companion?
14. The general principle: feats keep **one caster-only job** (the caster's route, or the
    caster-level stand-in), and any feat with no built item leaves the picker with a free
    retrain. Is that right, or should every item creation feat simply leave the picker ("the
    world classes are the feats")?
15. **Cheap spell items:** a 1st-level scroll costs 12.5 gp to make, a fraction of a mote. Should
    it round up to one phial of essence, cost coin for ink, or cost ingredients only (as
    potions do)?
16. **Spell prerequisites for scrolls and wands:** formula plus essences, with the spell
    replaced (alchemy's way; my recommendation), or the book's refusal without the spell?
17. **The layer as a whole:** build scrolls (and later wands), or record Use Magic Device as cut
    and leave spell items out of the game?

---

## 6. What I could not source, and what I did not check

- **Owlcat's reasons.** No Owlcat statement explains why Kingmaker shipped without item creation
  feats, or why WotR kept only scrolls and potions. The WotR crafting details come from a fan
  wiki (fextralife). The dev diary was reachable only as a one-paragraph summary.
- **WotR scroll copying into spellbooks.** It is widely known, but I did not source it here.
- **Kingmaker's fan mod mechanics** (time model, +5 DCs): its Nexus page returned 403. Only the
  GitHub README's to-do list was read.
- **Foundry PF1's consumable-from-spell UI and pricing code.** Only the changelog line was read.
- **The critic pass** (a second agent, 2026-11-22) checked §2 against AoN and the cited pages
  and fixed eight claims:
  - the immovable rod already exists;
  - the Kingmaker mod's feat list was overclaimed;
  - which items spend prepared spells;
  - the spellbook writing time;
  - Master Craftsman's limits;
  - the lone-PC APL;
  - the WotR kit tiers;
  - staff charge costs.

  It confirmed the PF2e wand rules on AoN (GM Core p.282).
- **Why PF2e dropped 50-charge wands.** I found no Paizo statement; the CLW-wand reason is
  community lore.
- **The scroll-copy cost.** The AoN rule page read gives the scroll's fate and the hour of study,
  but not the per-page ink price; `formulae.copy_cost_gp` already holds the book's figure, which
  I did not re-check.
- **Narrated spells at the cast door.** "A PARTIAL or NARRATED spell can still be cast, its told
  parts reaching the narrator" is read from `spells.casting_plan`'s contract (riders "for the GM
  to see") and the audit's ran/told split. I did not trace `_op_cast` end to end for a fully
  NARRATED spell. Confirm this before Q4 is answered on its basis.
- **Code.** No code was run; every [C] claim is from reading files on `integrate/0.5.1-impl`.

## 7. Sources

**Primary [P]**
- https://legacy.aonprd.com/coreRulebook/magicItems/magicItemCreation.html
- https://legacy.aonprd.com/coreRulebook/magicItems/scrolls.html
- https://legacy.aonprd.com/coreRulebook/magicItems/wands.html
- https://legacy.aonprd.com/coreRulebook/magicItems/staves.html
- https://legacy.aonprd.com/coreRulebook/magicItems/rods.html
- https://legacy.aonprd.com/coreRulebook/feats.html (the feat texts; also `content/feats/feats.json`)
- https://www.aonprd.com/Rules.aspx?ID=237 (copying spells from scrolls)
- https://legacy.aonprd.com/bestiary/golem.html
- https://legacy.aonprd.com/unchained/magic/dynamicMagicItemCreation.html
- https://legacy.aonprd.com/unchained/magic/automaticBonusProgression.html
- https://2e.aonprd.com/Skills.aspx?ID=37 (PF2e Crafting)
- https://2e.aonprd.com/Rules.aspx?ID=3218 (PF2e wands; read through a search snippet)
- https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/raw/master/CHANGELOG.md

**Wiki and secondary [W]/[S]**
- https://pathfinderwrathoftherighteous.wiki.fextralife.com/Crafting
- https://rpgcodex.net/article.php?id=11891
- https://github.com/RobRendell/OwlcatKingmakerModCraftMagicItems
- https://www.nexusmods.com/pathfinderkingmaker/mods/54 (403 when fetched)
- https://nwn.fandom.com/wiki/Craft_wand
- https://netheril.net/w/index.php/Wand_Making
- Earlier sweeps in this repository: `docs/enchanting-prior-art.md`, `docs/alchemy-prior-art.md`

**This repository [C]:** `rules/enchanter.py`, `rules/magic_layer.py`, `rules/formulae.py`,
`rules/finish_uses.py`, `rules/engine.py` (`_use_power`, `_release_stored`, `_buy_spell`, the
`item_cast` branch of the cast door), `rules/crafting.py` (`Stock`), `rules/creation.py`,
`play/alchemy_views.py`, `content/materials/magic-items.json`,
`content/materials/enchanter-materials.json`, `content/rules/repairs.json`,
`content/rules/skills-explained.json`, `content/world-classes/*.json`,
`content/classes/wizard.json`, `content/domains/powers.json`, `content/bestiary/core.json`,
`docs/implementation-audit-2026-11-22.{md,json}`, `docs/enchanting-answers.md`,
`docs/enchanting-revamp-plan.md`, `docs/alchemy-questions.md`,
`docs/research/2026-11-22-lane-b.md`.
