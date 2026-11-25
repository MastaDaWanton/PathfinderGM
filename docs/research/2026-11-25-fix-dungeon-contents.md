# Research note: fix/dungeon-contents (playtest 2026-11-23 items 6-10, O7, O8)

Searched 2026-11-25. Where a claim could not be sourced it says so. A critic pass re-read
the UE appendix, the poltergeist, telekinesis, CRB Survival and Selling Treasure, and
Inform 17.11-17.12: the gem formulas, UE's quotes, the poltergeist and violent thrust
(1 point to 1d6 per 25 lb, 25 lb per caster level) were confirmed; three overclaims
(dowsing in the CRB, gems under the CRB's trade goods, Inform's section) are corrected below.

## Reproduced first (the owner's save, `owner-1125-data`, and the turn record)

- **O7 / 7.** Turn [396]: `travel` into the death room resolved "The road is not empty: two
  chickens are on it". The dungeon rooms carry the ruin's terrain ("ruins"), so the hop
  rolled `ontheway.road`; the meeting opened a fight, and `Engine._op_travel` skipped
  `dungeons.arrived` whenever a fight was on that the walk had not brought along. The room
  was marked stocked only on the second visit ([502]), which is when the poltergeist (c14)
  and the coffer appeared. The save's death room lists `foes: ["c14"]`; the chickens were
  never the room's.
- **O8.** The coffer's record was `{"purse": {"gp": 150}, "goods": {}}`: the dungeon's
  treasure was always coin (`dungeons.generate`, "as coin in a container").
- **6.** The trace "Words are scrawled in the dust of a table, the same three words written
  over and over." named no words, anywhere in content/dungeons/.
- **8.** Turn [515]: "I talk to the ghost" read as a talk with no words; `acts_to_ops._greet`
  asked `scope.in_the_room(scene, "ghost")`, which matched names, trades and
  `bestiary.kind_names` (the block name and "undead"), so "ghost" found nobody.
- **9.** content/bestiary/core.json's poltergeist had `"melee": ""` and a `ranged` column
  holding the ability's prose ("attack roll of +3 when using telekinesis to hurl
  objects..."); the compiler read no attack from it, and `wielded_key` fell to the fist.
  It was the only block with no Strength score and no readable attack (scan of every
  block).
- **10.** The craft panel's Gather (`blacksmith:gather`, own kinds fitting, quenchant,
  alloy, fuel) on "ruins": the smith's shelf offered exactly one material there, Water,
  because Water's `biomes` was `[]` and `blacksmith.obtainable` reads an empty list as
  "any ground" ("water is water wherever you are standing"). The guarded band then booked
  3x the haul: 24 Water. The guard, a clockwork spy, came off the open-ground table
  inside a dungeon room.

## Items, sources, choices

### O8: the hoard as things
- **PF1, Ultimate Equipment, Treasure Generation**
  (https://legacy.aonprd.com/ultimateEquipment/appendix.html). Treasure types A-I: A coins
  only; B coins and gems; C art objects; D coins and small objects (potions, rings,
  scrolls, wands); E armour and weapons; F combatant gear; G spellcaster gear; H lair
  treasure; I treasure hoard. Method: "Select a number of rewards whose total gold piece
  value is equal to the total value of the treasure", take "the largest reward her budget
  allows", fill with "lesser rewards and coins". Gem grades: least semi-precious 5+2d4 gp, lesser
  25+2d4x5, semi-precious 50+2d4x10, greater semi-precious 250+2d4x50, lesser precious
  500+2d4x100, greater precious 2,500+2d4x500, with the stones of each grade named. Types B
  and C "can generally be traded for their full value" (that is UE's own text: the CRB's
  trade-goods exception to half price lists commodities only, not gems). Undead: types A, B, D, E (F and G
  if intelligent).
- **3.5 SRD** (d20srd.org treasure page answered 403; from memory, not confirmed this
  session): the per-encounter value rolled in three parts, coins, goods (gems and art) and
  items.
- **D&D 5e DMG** (community copies and blogofholding.com/?p=7753): one d100 per hoard fixes
  coins, gems or art and magic-item tables together; the blog's complaint is that "Every
  randomly rolled treasure must contain money". Not confirmed against the printed book.
- **Chosen:** `treasure.hoard`, UE's method over the catalogue's own rewards at their own
  prices (the 44 classic potions and oils, scrolls, wands and wondrous items, a short list
  of Core arms, UE's gems), a kind picked at random each step and one of the dearest
  third of what fits, at most six rewards, the remainder coin. Delivered through
  `goods.deliver`, so a looted potion is drinkable. Gems sell at full value.
- **Rejected:** a type letter per tag (UE itself gives no rule for choosing among types,
  and a Paizo thread says the section is "not complete enough"; https://paizo.com/threads/rzs42r76).
  Art objects: no names could be read off the UE page (the section was cut off in the
  fetch), and inventing them breaks "ground every name". Masterwork or magic arms: the
  goods router has no masterwork key. Rolling gem values: a gem's name is its price
  wherever it is sold, so each grade is at its mean.
- **Also:** the climax's value is the CRB's Treasure Values per Encounter row one above the
  APL, because the climax is drawn as a guarded fight ("challenging or hard sometimes",
  `encounter_budget`). The CRB prices an encounter by its CR; the guarded fight's CR is
  APL+1 on average. An owner call in degree, by the book in shape.

### O8: the haunt's anchor
- **Bestiary 2, poltergeist** (https://legacy.aonprd.com/bestiary2/poltergeist.html): "A
  poltergeist is bound to a specific place, usually a building, room, or recognizable
  area", typically where it died or where its remains rest; Site Bound 120 ft;
  rejuvenation until the reason for its existence is set right.
- **Chosen:** a tag's optional `anchor` (content/dungeons/tags.json): the weeping ghost's
  body and the dagger the revelation already describes, placed in the lair as props a hand
  can take. Laying the spirit to rest through it is NOT built (an owner call: what sets a
  poltergeist right is "created specifically for each ... poltergeist ... by the GM").

### O7 and 7: settled once, there the first time
- **B/X, Old-School Essentials:** keyed rooms are stocked when the dungeon is made;
  wandering monsters are a separate check, 1-in-6 every two turns, drawn from the dungeon
  level's own table (recedingrules.blogspot.com/2010/05/wandering-monster-checks.html;
  martinralya.com, "Wandering monsters: OD&D vs. B/X D&D"). Never the wilderness table.
- **Dungeon Crawl Stone Soup** keeps a level once generated (persistent levels): from
  general knowledge of the game, not re-confirmed this session.
- **Chosen:** no road or street table on a hop into a dungeon room (the dungeon's own,
  like the existing under-the-ground rule), no open-ground gathering encounter in a
  dungeon room, and `dungeons.arrived` runs on every arrival, a meeting or not.
- **Rejected for now:** a B/X wandering check drawn from the tag's own enemies. It is the
  tradition's answer, but the owner asked for contents "settled once"; listed as an owner
  call.

### 6: readable dressing
- **Chosen:** the trace names its three words ("I trusted them."), authored, no names
  invented; a save minted with the old sentence is mended on load (`dungeons.mend_traces`,
  matched on the whole old sentence, never re-filled from slots that could name another
  town).
- **Prior art:** Sly Flourish's "every room can tell a story" (already cited in
  rules/dungeons.py) and the Alexandrian's "Jaquaying" both assume a clue the players can
  read; no source was found that argues for unreadable writing. Inform's Recipe Book treats
  readable things as having text the READ action prints (from general knowledge; not
  re-fetched).

### 8: the ghost can be addressed
- **Inform 7, Writing with Inform 17.11**
  (https://ganelson.github.io/inform-website/book/WI_17_11.html): a synonym is written by
  the author ("Understand "lamp" as the lantern"), and words can be given to a whole kind
  of thing ("Understand "machine" as a device"). Property-based words ("as describing")
  are in a later section of chapter 17 (not 17.11 or 17.12; section not confirmed).
- **CircleMUD:** a mob answers to its keyword list (the building manual already cited in
  rules/engine.py `_lies_in_wait`).
- **Chosen:** `bestiary.kind_names` adds "ghost" and "spirit" for any undead with the
  incorporeal subtype, read off the block's type and subtype (Inform's kind-wide words),
  so `scope.in_the_room` finds the poltergeist. Whether it can answer is the bestiary's:
  the poltergeist lists Common (Int 5).
- **Rejected:** a synonym row in content/people/synonyms.json (the population finder holds
  people, not creatures), and a word list in the reader's prompt.

### 9: the poltergeist's attack
- **Bestiary 2** (same page): no Melee or Ranged line; "A poltergeist has no method of
  attacking apart from telekinesis", ranged attack +3, objects up to 75 lb.
- **CRB, telekinesis (violent thrust):** hurled objects deal from 1 point per 25 lb to 1d6
  per 25 lb for hard, dense objects; 75 lb is up to 3d6 (from the spell's text as
  remembered; the spell page was not re-fetched this session).
- **Chosen:** the block's ranged column corrected to "telekinesis +3 (3d6 bludgeoning)",
  the record recompiled for that block alone. **Rejected:** a no-Strength-no-fist rule in
  code (the scan found one block it would touch), and the full telekinesis spell (combat
  maneuvers, the Will save to resist being hurled): not built, an owner call. Natural
  invisibility and frightener are not built either.

### 10: water as a smith's find
- **CRB Survival** (https://legacy.aonprd.com/coreRulebook/skills/survival.html): getting
  along in the wild, DC 10 (feeding others; the page has no water-finding rule). A dowsing
  use (DC 15 for water, pointing at the largest fresh-water source) exists in a later book
  (probably Heroes of the Wild, needing psychic casting or Psychic Sensitivity); the
  critic pass could not open it, so it is cited only as a sign that later rules treat
  water as a thing a place has or lacks. Ultimate Wilderness's water rules could not be
  read this session.
- **Chosen:** Water's material row lists its ground (every land biome but desert and ruins,
  plus coast and open water; not underground, so a dungeon floor stays dry whatever its
  terrain becomes). **Rejected:** keeping "any ground" and guarding the dungeon case only
  (it would still put water in a desert), and a rank gate on the guarded "find of a
  lifetime" (touches every trade's tables; not needed once the defect's source is gone).
  Underground is a judgement call: a natural cave may hold a pool.
