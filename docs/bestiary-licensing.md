# The shipped bestiary and Paizo's Product Identity: options for a decision

**Status: waiting on the project owner. Nothing has been removed or changed.** Written
2026-09-27, in answer to the question `docs/enemy-tactics-plan.md` raised under decision D1.

**This is not legal advice.** It is a measurement of what the repository ships, a reading
of the licences' own words, and a survey of what other open projects did. Where a claim
rests on reading a declaration rather than on a ruling, it says so. Nobody at Paizo has
been asked, and no Paizo staff statement was found that settles the central question (§3).

---

## 1. The question

`content/bestiary/creatures.json` holds 6,406 stat blocks. `tools/build_bestiary.py`
built it from `monster_stat_blocks_full.xlsx`, which is Mike Chopswil's "NPC Database"
spreadsheet. Its Notes sheet has a "Section 15: Copyright Notice – Monster Database"
heading, and under it a single line: "NPC Database. Copyright 2020 Mike Chopswil". The
sheet carries no upstream entry for any of the books its rows came from.

Most of those rows are from Paizo adventures. Paizo's adventure declarations open only
"the game mechanics". They make "proper names (characters, deities, etc.), dialogue,
plots, storylines, locations, characters" Product Identity (PI). The repository is
public, so every clone distributes the file.

Separately, and already recorded in `OGL-NOTICE.md`, Section 15 of `OGL.txt` has not been
written for any of the imported content.

## 2. What the file actually holds (measured)

Reproduce with `python tools/bestiary_provenance.py` (read-only; `--sample N` prints rows
to hand-check). The families come from an explicit table in that file. The source
strings are the spreadsheet's own ("AP 109", "PFS S1-52"), and the grouping into product
lines is the tool's.

| family | rows | sources | generic name | setting word | personal name | ability-text rows |
|---|---:|---:|---:|---:|---:|---:|
| Adventure Path | 2,258 | 138 | 531 | 58 | 1,669 | 835 |
| Society scenario | 1,630 | 193 | 395 | 97 | 1,138 | 585 |
| Module | 409 | 40 | 89 | 6 | 314 | 146 |
| Campaign Setting / Companion | 546 | 42 | 88 | 25 | 433 | 152 |
| **Rulebook** (NPC/Villain/Monster Codex, GMG, Bestiary 3/5/6, Mythic Adv.) | **791** | 8 | 754 | 0 | 37 | 9 |
| Third party (Frog God Games) | 748 | 74 | 287 | 19 | 442 | 288 |
| unclassified | 24 | 7 | 3 | 1 | 20 | 5 |
| **total** | **6,406** | 502 | 2,147 | 206 | 4,053 | 2,020 |

- **Where the rows come from.** Two thirds (4,297) are Paizo adventures: Adventure
  Paths, Society scenarios and modules. Only 791 (12%) come from Paizo rulebooks, where
  names are roles by design. The seven unclassified sources are named in the tool's
  output.
- **How names are classified.** A name counts as *personal* if it has a word that
  appears nowhere lower-case in the shipped rules prose and is not a word from the generic
  galleries or the printed Bestiary names.
- **How accurate that is, hand-checked on 60 random rows per verdict:**
  - "Personal name": 49 of 60 really are people or unique creatures. Of the other 11, 5
    are Golarion setting words ("Priest of Razmir", "Lastwall Border Scout"), 5 are
    generic ("Slush Cube", "Jigsaw Shark") and 1 is unclear.
  - "Generic": about 55 of 60 really are generic. The misses are unique titles such as
    "The Watcher In The Bay" and "The Great Scarab".
  - "Setting word" is mixed: about a third generic, about half setting names, and a few
    people.
  - Best estimate: roughly **3,300–3,700 rows (about 55%) carry a person's or a unique
    creature's name**, and about 3,900 contain some proper noun.
- **The rulebook's 37 flagged rows** are almost all the NPC Codex's 11 iconics at three
  levels ("Seelah Level 1"). The iconics are Paizo characters.
- **Descriptive text ships too.** `special_abilities` holds 1.56 million characters
  across 2,020 rows. Most of it is rules text, which is Open Game Content, but adventure
  rows mix story into it. For example: "Losoni is bonded to the entire clonal colony of
  titan aspen that supports the Court of Spears". **763 rows' ability text uses the
  creature's own proper name**, so renaming the `name` field alone does not remove the
  name.
  - Other text fields: `notes` is one row of flavour ("Codex Archon"). `environment`,
    `organization` and `treasure` are empty in this file. `languages` carries Golarion
    languages ("Varisian" on 363 rows, "Osiriani", "Tien" and others).
- **Everyday monsters currently come from adventures.** `core.json` (782 creatures from
  the Bestiary PDFs) does not include the commonest animals and humanoids. The ids the
  game resolves today come from:

  | id | source |
  |---|---|
  | `wolf`, `orc`, `human-skeleton` | Crypt of the Everflame |
  | `goblin` | Rappan Athuk |
  | `zombie` | Rappan Athuk |
  | `giant-spider` | PFS S1-30 |
  | `black-bear` | Rappan Athuk |
  | `warhorse` | Rappan Athuk |

  Removing rows by source family removes these too unless `core.json` is completed first.
- **How the names reach the player:**
  - The creatures bench lists and searches every row.
  - A gathering encounter brings a non-humanoid in *under its own name* (`rules/engine.py`
    `_gathering_encounter`). A named unique beast can therefore appear by name: AP 96's
    "Galescream" (an animal) and "Tangletooth" (an animal, from Burnt Offerings) are both
    eligible.
  - The NPC chooser already strips adventure names and keeps only the numbers
    (`rules/npcs.py`: "Numbers, never story").
- **Code and tests that name adventure rows:**
  - `tests/test_npcs.py` uses `jevana-drow-noble-priestess`, `abra-lopati`,
    `captain-gortus-svard`, `caleb-voltiaro-…` and `trillok-captain-of-the-guard`.
  - Saved NPC records (`homebrew/npcs/*.json`) store a block id, so any rename needs an
    id migration.

## 3. What the licences say

Sources, confidence and quotes are in §6. The short version:

- **Mechanics are open, names are not.** Every Paizo declaration read has the same
  shape: the game mechanics are Open Game Content, and proper names, characters,
  locations and deities are PI. That covers AP Player's Guides from 2009, 2015 and 2018,
  modules from 2010, 2011, 2014 and 2018, and the PRD's rulebook declaration. From about
  2018 the wording widens to "all adjectives, names, titles, and descriptive terms
  derived from proper nouns", which reaches "Chelish Marine Officer" and "Aspis Agent" as
  well as "Janiven".
  - Paizo's CTO said declarations "*do* occasionally vary", so each product should be
    checked.
  - The 2007–08 volumes, the Society scenarios themselves and the Campaign Setting books
    could not be read from a legal copy. For those, the reading is inferred, not
    confirmed.
- **The open question.** Is a stat block's *title* part of the open mechanics, or a PI
  name sitting on top of them? **No Paizo ruling was found.** Reading the declaration, the
  name is PI and the numbers are open. d20pfsrd acts on that reading and renames, but that
  is precedent, not endorsement.
- **Section 15 is required regardless of the PI question.** OGL §6 requires "the exact
  text of the COPYRIGHT NOTICE of any Open Game Content You are copying" in Section 15.
  - That applies to each of the 502 sources.
  - Each source's own upstream entries come with it. An AP's Section 15 carries lines like
    "Tome of Horrors Complete © 2011, Necromancer Games".
  - The spreadsheet gives "AP 109", not the volume title, so every AP number needs mapping
    to its printed title and year. (#109 is *In Search of Sanity*; the similarly placed
    *In Hell's Bright Shadow* is #97. Getting these right is the transcription work.)
  - The publisher name changed from "Paizo Publishing, LLC" to "Paizo Inc." part-way
    through, and each entry has to be copied as its own book prints it.
- **OGL §7 forbids using PI** "except as expressly licensed in another, independent
  Agreement". **Whether the CUP is that agreement for NPC names is not settled by
  Paizo's text.** The CUP FAQ does answer "Yes" to the §7 question, but only for
  indicating "compatibility or co-adaptability with trademarks from products listed in
  Section 1 of our Community Use Approved Product List". That list was withdrawn in 2024.
  It says nothing about PI names in general. Foundry acts as if the CUP covers names, and
  Paizo has not objected, but that is practice, not permission.
- **The Community Use Policy (CUP).** Paizo reinstated it in August 2024 after the brief
  Fan Content Policy change.
  - It covers software.
  - It lets you "descriptively reference" proper names, places and deities. That is
    narrower than a licence to republish them, and whether a stat block headed "Janiven"
    counts as descriptive reference is itself unruled.
  - It says **nothing** about AI or language models, and nothing about rules compendiums.
    These are silences, not permissions.
  - The project must be free, carry Paizo's notice, reproduce Paizo's copyright notices
    and author credits for every product used, and give contact information.
  - Paizo can withdraw permission "at any time for any reason".
  - Its FAQ adds that you may not "simply republish significant sections of descriptive
    text".
  - It does not cover the Frog God Games books.
- **The OGL itself still stands.** Wizards of the Coast left OGL 1.0a "in place, as is"
  in January 2023. Paizo's ORC licence does not relicense PF1 content: "If you want to
  utilize content that exists solely under the OGL, you must publish it under the OGL".

## 4. What other open projects did

| project | licence basis | what they did with adventure NPCs |
|---|---|---|
| **d20pfsrd.com** | OGL only | Hosts them **renamed to role titles**. "Devargo Barvasi" is published as "Bladed Fist (Human Rogue 4)", with a per-page Section 15 line for the AP volume. Its stated policy: names "may have been renamed, or had the name removed … compliant with the Open Game License". Not applied consistently to unique monsters. |
| **Paizo's PRD / PSRD-Parser** | OGL | **No adventure content at all.** Rulebook line only: Core, APG, Bestiaries, GMG, NPC Codex, Monster Codex and similar. |
| **Foundry PF1 Statblock Library** | GPL code, OGL + **CUP** content | About 10,000 stat blocks from 138 AP books and 192 PFS scenarios, **built from the same Chopswil spreadsheets**. Ships under the CUP notice with a Section 15 of roughly 750 entries. **Names kept.** Its Crimson Throne pack holds `Devargo_Barvasi_….yml`, `Gaedren_Lamm_…` and `Ileosa_Arabasti_…`, confirmed by the critic pass. |
| **Archives of Nethys** | Commercial licence until 24 July 2026; since then a "much less formal" agreement with Paizo | Full names and lore. Its Licenses page still says "under commercial license" and that its content "is not available for use under Paizo's Community Use License"; Paizo's July 2026 post supersedes the first half. Either way, a bespoke arrangement nobody else inherits. |
| **Hero Lab, Fantasy Grounds, Roll20** | Paid licences with Paizo | Sell AP content by agreement. Not available to this project. |

**No project was found shipping named AP NPCs on the OGL alone.** Projects that keep the
names hold a separate agreement: either the CUP or a commercial licence. The two
precedents that started from this exact data split cleanly:

- d20pfsrd, on the OGL, strips "Devargo Barvasi" to "Bladed Fist".
- Foundry, on the CUP, keeps him.

## 5. The options

All options share two facts:

- **Git history.** Whatever ships next, the current file is already in the public history.
  Changing the tree governs future distribution. Scrubbing history is a separate and
  destructive step: a force-push, every clone keeps its copy, and it needs its own
  decision.
- **Section 15.** Every option still needs Section 15 written for whatever content remains.

### A. Keep everything, and collect Section 15 (OGL only)

- **Cost:** transcription for 502 sources plus their cascades. The AP-number-to-title
  mapping has to be built.
- **What it does not fix:** Section 15 attributes the Open Game Content but licenses no
  PI. Under every declaration read, the roughly 3,500 personal names, and the
  setting-word names under the 2018+ wording, stay unlicensed. **On its own, this does
  not answer the question.**

### B. Keep everything under OGL + CUP (the Foundry Statblock Library pattern)

- **What it does:** keeps every row and name, relying on the CUP as the "independent
  Agreement" §7 asks for. **Paizo's text does not say the CUP covers this** (§3): its
  FAQ's §7 answer is about trademark compatibility, and the policy grants "descriptive
  reference". The footing is the Foundry community's practice, and Paizo's tolerance of it
  so far.
- **Cost:**
  - Everything in A, plus the CUP notice.
  - Paizo's copyright notice and author credits for every Paizo product used (roughly 420
    sources).
  - A contact address.
- **Binds the project:**
  - **The app must stay free, permanently**, for anything built on this content.
  - Paizo may withdraw permission at any time. Its July 2024 change briefly did exactly
    that to OGL+CUP mixing before it was reversed.
- **Leaves open:**
  - The 1.56M characters of ability text: the CUP forbids republishing significant
    descriptive text, and adventure rows carry story inside rules text.
  - The 748 Frog God Games rows are not Paizo's to permit. Their declarations were not
    checked.
- **Why it is plausible:** this is the configuration the Foundry community ships today,
  from the same source spreadsheet.

### C. Rename the named rows to role titles (the d20pfsrd pattern)

- **What it does:** retitles each personal-named row from its own mechanics, the way
  d20pfsrd writes "Human Rogue 4" or "Bladed Fist". It also scrubs the name from the
  ability text of the 763 rows that repeat it, and removes the other proper nouns found
  there.
- **Keeps:** all 6,406 stat blocks and the variety. This is the same move `rules/npcs.py`
  already makes at run time.
- **Cost:**
  - Retitling about 4,000 rows. By the project's own rule it would be mechanical: the
    title is built from race, class and level, and no model invents a name.
  - A detector for leftover proper nouns, which `bestiary_provenance.py` is the start of.
  - An id migration for saved NPC records and for the five test ids.
  - Section 15 for all 502 sources, as in A.
- **Unsolved:**
  - Setting words ("Aspis", "Hellknight", "Chelish") are PI under the 2018+ wording.
    Renaming them loses meaning, and keeping them is a judgement call.
  - Some story is so bound into the mechanics that it cannot be separated, for example
    the "Court of Spears" ability. Those rows would need dropping or hand editing.

### D. Ship only the rulebook line; drop adventure-only rows

- **What it does:** keeps the 791 rulebook rows plus `core.json`. The 33 iconic rows are
  renamed or dropped, since Seelah and Sajan are Paizo characters.
- **Why it is safe:** this is the PRD's own shape and PSRD-Parser's. Section 15 shrinks
  to about a dozen books (Bestiary 1–6, the three Codexes, GMG, Mythic Adventures) and
  their cascades. Most are transcribable from the PRD's own Section 15, but Villain Codex
  and the later Bestiaries need checking against their own printed pages.
- **Cost:**
  - About 5,600 rows, and with them roughly 1,000 generic adventure rows ("Morlock
    Slave", "Dire Tiger Fast Zombie").
  - **`core.json` must first be completed** from the Bestiaries, or the game loses `wolf`,
    `orc`, `goblin`, `zombie` and `giant-spider`.
  - The NPC chooser's tier-2 pool empties, so named-role fallbacks would come only from
    the galleries.
- **This is the "narrow what ships" option `OGL-NOTICE.md` already describes as cheap and
  safe.**

### E. D, plus a user-side import for the rest

- **What it does:** ships D. The user can point the app at their own copy of the
  spreadsheet, and `tools/build_bestiary.py` already exists. The result lands in the
  user's data directory (`homebrew/creatures/` is already read by `rules/bestiary.py`).
- **Why:** the public repository then distributes only what it can attribute. The
  variety returns for anyone who supplies the data themselves.
- **Cost:** a user-facing import step, which the standalone .exe must support without a
  terminal, and a line in the manual.

### Recommendation, for what it is worth

**D, with E**, unless keeping every named NPC in the public build matters enough to
accept B's permanent free-only commitment, its revocability and its unconfirmed footing.

- D+E is the only option whose attribution burden can be finished from primary sources.
  It depends on no unruled reading of a declaration.
- It costs the least engine work: completing `core.json` is work the bestiary wanted
  anyway.
- C keeps more rows, but it is a large content rewrite that still leaves the setting-word
  question open.

The owner's call either way.

## 6. Sources

Confidence: **P** = primary source read, **S** = secondary, **U** = could not confirm.

Three passes produced these sources: two researchers, then a critic that re-fetched each
load-bearing claim. The critic corrected three overclaims, all reflected above:

- The CUP grants "descriptive reference", not free use of names.
- The FAQ's §7 "Yes" is about trademark compatibility, not PI in general.
- The Archives of Nethys Licenses page is stale since July 2026.

**Declarations**

- **P** Hell's Rebels Player's Guide (2015). PI covers "proper names (characters, deities,
  etc.), dialogue, plots, storylines, locations, characters, artwork, and trade dress".
  Open Content is "the game mechanics of this Paizo game product".
  https://downloads.paizo.com/HellsRebels_PlayersGuide.pdf. Same wording in Council of
  Thieves Player's Guide (2009).
- **P** Tyrant's Grasp Player's Guide (2018). PI covers "proper nouns (characters,
  deities, locations, etc., as well as all adjectives, names, titles, and descriptive
  terms derived from proper nouns)". https://downloads.paizo.com/TyrantsGrasp_PlayersGuide.pdf
- **P** Modules: We Be Goblins! (2011), Risen from the Sands (2014) and Master of the
  Fallen Fortress (2010) use the 2009–15 wording. We Be 5uper Goblins! (2018) uses the
  2018 wording. downloads.paizo.com
- **P** The PRD's own declaration, the same shape as above:
  https://legacy.aonprd.com/openGameLicense.html
- **P** The GMG NPC Gallery and Monster Codex title their stat blocks by role. The NPC
  Codex does too, but its flavour text names examples ("Corwyn Klas").
  legacy.aonprd.com
- **P**, forum. Vic Wertz, Paizo CTO, 2011: declarations "*do* occasionally vary … check
  each product". https://paizo.com/threads/rzs2mz9c
- **U** The 2007–08 AP volumes: the one 2007 Paizo PDF read (Hollow's Last Hope) has no
  PI declaration at all.
- **U** The Society scenarios' own pages, the Campaign Setting and Player Companion lines,
  and all Frog God Games books.

**Licences**

- **P** OGL v1.0a §§1(d), 1(e), 6, 7 and 8, via https://legacy.aonprd.com/openGameLicense.html
- **P** Community Use Policy, updated 22 Aug 2024: https://paizo.com/licenses/communityuse
  The FAQ is at https://paizo.com/community/communityuse/faq
- **P** July 2024 Fan Content change: https://paizo.com/blog/new-and-revised-licenses
  The August reversal: https://paizo.com/blog/updates-on-the-community-use-policy-and-fan-content-policy
- **P** Wizards of the Coast on OGL 1.0a:
  https://www.dndbeyond.com/posts/1439-ogl-1-0a-creative-commons
  Paizo on ORC and OGL-only content: https://paizo.com/licenses

**Precedents**

- **P** d20pfsrd renaming policy: https://www.d20pfsrd.com/bestiary/tools/monster-filter/
  The Devargo Barvasi page, published as "Bladed Fist":
  https://www.d20pfsrd.com/bestiary/npc-s/npcs-cr-3/devargo-barvasi/
- **P** PSRD-Parser: https://github.com/devonjones/PSRD-Parser
  PSRD-Data: https://github.com/devonjones/PSRD-Data
  The PRD's book list: https://legacy.aonprd.com/updates.html
- **P** Foundry PF1 Statblock Library: https://gitlab.com/foundryvtt_pathfinder1e/pf1-statblock-library
- **P** Archives of Nethys: https://aonprd.com/Licenses.aspx
  Paizo on the July 2026 change:
  https://paizo.com/blog/paizo-archives-of-nethys-moving-forward-together
- **S** Hero Lab, Fantasy Grounds and Roll20 sell AP content under agreements with Paizo.
  PCGen's publisher-permission process could not be read (pcgen.org refused connections).

**Not found:** any Paizo statement on whether a proper-name *title* over an open stat
block is PI. Also not found: the Frog God Games declarations for Rappan Athuk, Sword of
Air, The Lost City of Barakus and Tome of Horrors. Their 748 rows need the same check
before any option that keeps them.

---

## 7. Follow-up, 2026-10-29: Golarion names outside the bestiary

**Status: decided 2026-10-29 — F3, falling back to F2 (the owner's words: "go with F3,
falling back to F2"). Applied the same day by `tools/strip_golarion.py` from the table in
`tools/golarion_rewrites.py`:**

- **Renamed:** 36 spells, 12 feats and 2 weapons, plus 7 feat ids re-slugged. Examples:
  Spellbane, Touch of Truthtelling, Dueling Sword Mastery, the dueling sword.
- **Prose rewritten:** 136 rows edited sentence by sentence (109 spells, 27 feats), with
  the mechanics untouched.
- **Columns cleared:** the deity and bloodline column entries.
- **Deity gates:** 13 feats now ask for a god by portfolio ("a god of battle").
- **Product prefixes:** stripped from the book citations.
- **Dropped, the F2 fallback:**
  - 17 prestige-award feats;
  - Improved Day Job, Eagle Knight Candidate and Osirionology;
  - an import duplicate of Lastwall Phalanx;
  - Cultural Adaptation (Taldan), the rulebook's spell with a Taldan origin story;
  - What Grows Within, which was built on AP 113's Great Old One.
- **Result:** spells 3,040 → 3,038, feats 1,474 → 1,453, and zero Golarion names in
  shipped content outside the bestiary. `tests/test_no_golarion_names.py` holds that.
- **Old saves:** they resolve through `content/spells/aliases.json`,
  `content/feats/aliases.json` and the weapon aliases in `rules/weapons.py`.
- **The myth names went the same way on 2026-10-30** (the owner: "rewrite the myth names
  too, same way"). That is the 27 myth-only rows, plus every myth name in other rows and
  columns:
  - Apsu and Dahak became a good and an evil dragon god.
  - Asmodeus became the lord of Hell, or a god of tyranny in feat gates.
  - Lamashtu became a demon goddess, or a god of monsters in feat gates.
  - Mammon became an archdevil of greed, and Hastur the god of the sign.
  - Abaddon became the daemon wastes, and Charon's River Styx the river of forgetting.
  - 6 spells were renamed: Shining Scales, Blessing of the Bull, Ferryman's Dispensation,
    Draconic Release, Vision of Nightmares and Foul Waters. Nothing was dropped.
- **Left as they were, on purpose:**
  - Cosmology words (Boneyard, Elysium, First World), which were never ruled on.
- **The app's own river materials were renamed on 2026-10-30** (the owner: "rename the Styx
  materials too"). Styx Water is now Oblivion Water, quenching "Oblivion-quenched"; Styx
  Mordant is now Oblivion Mordant. Their text already called it "the river of forgetting".
  Old ids resolve through `materials.RENAMED`, and saves are rewritten on load
  (`sheet._current_materials`). "Styx" is on the deny-list now.
- **The cosmology words, 2026-10-30** (the owner: "rename the cosmology words too").
  Paizo's own plane names became what each place is:
  - the Boneyard → the court of the dead;
  - the Maelstrom → the churning chaos;
  - Axis → the city of law;
  - Elysium → the free heavens;
  - Nirvana → the serene heavens;
  - the First World → the fey realm;
  - the Great Beyond → the planes beyond;
  - the River of Souls → the river of the dead;
  - the Akashic Record → the memory of the cosmos.

  Five spells were renamed: Memory Communion, Remembered Form, Glimpse of All Memory, Fey
  Revisions and Fey Kiss. The SRD's generic planes (Heaven, Hell, the Abyss, the Shadow,
  Ethereal, Astral and Material Planes) and book titles in `source` stay.
- **Golarion's coined metals, the same day** (the owner: "rename the skymetals and
  nexavaran steel too, using the adjective skymetal is fine"). Each is named for what its
  own entry says it does:

  | was | now |
  |---|---|
  | abysium | fever skymetal |
  | djezet | quick skymetal |
  | inubrix | ghost skymetal |
  | noqual | null skymetal |
  | siccatite | searing skymetal |
  | horacalcum | time skymetal |
  | nexavaran steel | frontier steel |
  | elysian bronze | celestial bronze |
  | the herb Elysium | nullgrass |

  Their ores follow. Old ids resolve through `materials.RENAMED` and
  `ingredients.RENAMED`, and saves are rewritten on load.
  - Updated: code, tests, data passes, the generated review pages, and the contract docs
    (`campaign-format.md`, `from-world-bible.md`).
  - Not updated: the dated design records (plans, prior art, contracts, questions). They
    still quote the book's names, as a record of what was read.
- **Still outstanding:** Section 15 for the setting books.

The section below is the measurement and the options as they were put.

The owner chose option D for the bestiary on 2026-10-28: ship Paizo's rulebook line and no
Product Identity. The spells and feats came in through the same kind of spreadsheet import, from
the whole Pathfinder line. This section measures how much Golarion they carry and sets out
the options. The letters run F1–F4 so they cannot be confused with A–E above.

### 7.1 How it was measured

Reproduce with `python tools/content_provenance.py`. It is read-only, like
`tools/bestiary_provenance.py`. Add `--rows` for every hit row (a worklist) and
`--sample N` for random hits with context.

- **A deny-list, not a guess.** 519 Golarion proper nouns in six classes: deity,
  place, people (and their languages), organisation, character (iconics included) and
  calendar. They were taken from four places:
  - §2 of this doc.
  - The spreadsheets' own source titles.
  - The spells' `deity` column.
  - A discovery pass: every capitalised word in shipped content that is never written in
    lower case anywhere, read by hand.

  Matching is case-sensitive and on word boundaries. Ids are checked too, because an id is
  the slugged name (`aroden-s-spellbane`). Names that are also ordinary English words were
  left off the list, so **the counts are a floor**.
- **Counted apart, not in the Golarion total:**
  - `myth`: names older than Paizo that Golarion adopted (Asmodeus, Lamashtu, Hastur,
    Abaddon).
  - `product`: Paizo titles cited in rules text ("see Pathfinder RPG Bestiary").
  - `cosmology`: Paizo planes that read as ordinary words (Boneyard, First World,
    Elysium).
- **Where in a row the name sits** matters, because it decides what a fix costs:
  - its **name** or id;
  - its **prose** (description, benefit, special);
  - only a **list column**: the spells' `deity` and `bloodline` columns, or the feats'
    prerequisites.
- **Family** comes from each row's `source`, using an explicit table:
  - rulebook: the Roleplaying Game line;
  - setting: Campaign Setting and Player Companion together;
  - adventure: Adventure Path, module and Society;
  - other: blog, comic and card deck.

  All 208 source strings are placed, and none is unclassified. After folding the
  spreadsheets' case and title variants ("Qadira" and "Qadira, Jewel of the East"), that
  is 17 rulebooks, about 117 setting books, 53 adventures and 3 others.
- **Hand check:**
  - 40 random hits: all 40 were real Golarion, myth or title mentions. Two class labels
    are loose: Kalistrade is a prophet filed as a deity, and Nex is both a wizard and his
    nation.
  - 40 random setting or adventure rows with no hit: none carried a Golarion name in the
    text read.
  - A third pass listed the capitalised words left in the rows with no hit. It found six
    more names (Ninth Battalion, Risen Guard, Bloodstone Swords, Old Cults, Shaine, and
    "Pathf inder Society" split by the PDF). They are now on the list.
- **A correction to the first count.** The 2026-10-29 grep (52 lines in spells.json, 77
  in feats.json) mostly matched the `source` column, for example `"source": "Kobolds Of
  Golarion"`. That is the book title, not the row's text. The real figures are below.

### 7.2 What ships (measured)

| file | family | rows | name | prose only | column only | **Golarion total** | myth only | product title only |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| spells.json | rulebook | 1,997 | 3 | 16 | 7 | **26** | 2 | 49 |
| spells.json | setting | 931 | 30 | 64 | 55 | **149** | 12 | 35 |
| spells.json | adventure | 101 | 2 | 11 | 13 | **26** | 7 | 6 |
| spells.json | other | 11 | 0 | 1 | 0 | **1** | 1 | 0 |
| feats.json | rulebook | 1,091 | 0 | 0 | 0 | **0** | 0 | 6 |
| feats.json | setting | 378 | 19 | 26 | 24 | **69** | 5 | 13 |
| feats.json | adventure | 5 | 0 | 0 | 0 | **0** | 0 | 1 |
| **total** | | **4,514** | **54** | **118** | **99** | **271** | **27** | **110** |

- **271 of 4,514 rows (6%) name Golarion.** Most of the rest are plain mechanics.
- **Setting books are mostly mechanics.** 1,426 rows come from setting, adventure and
  other books. 1,181 of them (83%) carry no Golarion name. Examples are Hollow Blades,
  Rain of Arrows and Diminished Detection.
- **Where the named rows come from:**

  | source | named rows |
  |---|---:|
  | Inner Sea Gods | 54 |
  | Inner Sea World Guide | 22 |
  | Inner Sea Magic | 21 |
  | Faction Guide | 17 |
  | Adventurer's Guide | 16 |
  | Dwarves of Golarion | 9 |
  | 61 other sources | 132 |

- **The rulebook line is not clean either. 26 spells name Golarion; no rulebook feat
  does.**
  - 16 are from the *Adventurer's Guide*. It is a Roleplaying Game hardcover, but it was
    built around Golarion's organisations (Red Mantis, Lantern Bearers, Cyphermages,
    Aldori, Sarzari).
  - 7 are Core or APG spells whose only hit is "Harrow" in the `bloodline` column. That
    is the Harrowed bloodline, a setting bloodline, listed against augury, weird and
    others.
  - 2 are from *Planar Adventures*: Pharasma in judgment undone, and the Witchwood in
    soulseeker.
  - 1 is from *Occult Adventures*: Shelyn in foster hatred.
- **Which kinds of name appear** (rows mentioning each class):

  | class | rows | most common names |
  |---|---:|---|
  | deity | 176 | Aroden, Abadar, Zon-Kuthon, Calistria, Pharasma |
  | place | 101 | Golarion, Inner Sea, Nex, Irrisen, the Worldwound |
  | people | 65 | Shoanti, Aldori, Varisian, Azlanti, Taldan |
  | organisation | 60 | the Harrow, Cyphermages, Whispering Way, Pathfinders, Hellknight |
  | character | 49 | Aram Zey, Kreighton Shaine, Jatembe, Hao Jin, Alaznist |

- **The `deity` column is not read by any code.**
  - 96 spells fill it, and 70 of those name Golarion only there. Only the importer
    (`tools/build_spells.py`) writes it.
  - The ruling of 2026-09-19, "grab whatever the belief system of the world is", keeps
    deity out of the engine, and `tests/test_spellcasting.py` enforces that.
  - Deleting those column entries therefore changes no behaviour.
- **The 54 name rows:**
  - 7 are feats whose *name* is clean but whose id carries the book title as a reprint
    tie-breaker, for example `gore-fiend-orcs-of-golarion`.
  - That leaves 47 that really need renaming.
- **Feats nobody here can take.**
  - 17 *Faction Guide* feats require Pathfinder Society faction prestige, for example
    "Kitharodian Academy 15 TPA".
  - That is an organised-play currency this app does not have, so these rows are dead
    whatever is decided.
- **Copies elsewhere that would have to follow any change:**
  - 55 entries in the spell mechanics files (`content/spells/mechanics/part-*.json`,
    `spells-mechanics.json`) are keyed by a named id or repeat the name in their own
    `target` or `notes` prose. Any rename or drop has to follow them there.
  - Saves store spellbooks and feats as strings (`rules/sheet.py`), so a rename or a drop
    needs aliases, as `content/bestiary/aliases.json` does for creatures.
- **Other shipped content:**
  - `weapons.json` has "Aldori dueling sword" and "Shoanti bolas". `rules/base-pieces.json`
    repeats the bolas.
  - Two `_source` notes cite "Archives of Nethys" and the "Pathfinder Society FAQ". These
    are citations, not lore.
  - Everything else in `content/` outside the bestiary is clean.
  - Code mentions are comments only. The two "Harrow" hits in `gm/prompts.py` are an
    invented example place name, not the deck.
- **Out of scope here, but on record:** `reference/books/` is not packaged but is in the
  public repository. It holds 23 Golarion mentions in its extracted Bestiary 4–6, Mythic
  and Ultimate Equipment text.

### 7.3 Prior art for this exact case

- **d20pfsrd** publishes setting-book spells **renamed, with the names taken out of the
  prose**, and keeps a per-page Section 15 for the setting book:
  - Inner Sea Magic's "Aroden's spellbane" is published as **"Spellbane"**. Its text names
    no one, and the page credits "Pathfinder Campaign Setting: Inner Sea Magic. © 2011,
    Paizo Publishing, LLC".
  - Inner Sea Gods' "Abadar's truthtelling" is published as **"Touch of Truthtelling"**.
    The deity is replaced by a generic line that the spell "is associated with a
    particular deity", and the page credits Inner Sea Gods © 2014.

  This is option C's pattern, applied to spells, by the site that applies it to NPCs (§4).
- **The PRD and PSRD-Data** carry the rulebook line only (§4).
- **Foundry**, under the CUP, keeps the names (§4).

Sources: https://www.d20pfsrd.com/magic/all-spells/s/aroden-s-spellbane/ and
https://www.d20pfsrd.com/magic/all-spells/t/touch-of-truthtelling/ (both read 2026-10-29,
**P**). Not confirmed: whether d20pfsrd does this for every setting spell. Two pages were
read, not a sweep.

### 7.4 The options

All four options share these steps:

- Product-title citations become plain book names ("see Pathfinder RPG Bestiary" becomes
  "see the Bestiary"). They appear in 131 rows, and in 110 of those they are the only
  hit. This is a mechanical rewrite.
- The 2 weapons are renamed, and the 55 mechanics entries and the saves' aliases follow
  every rename or drop.
- `tools/content_provenance.py` becomes a test that holds the Golarion count at zero,
  so a later import cannot bring the names back. The rule is the one used for models:
  detect the defect in code.
- The 27 myth-only rows (Waters of Lamashtu, the yellow sign of Hastur, Asmodeus's
  spellcasting contracts) are a separate call. Each name is public myth, but the Golarion
  god built on it is Paizo's.

#### F1. Rulebook line only: option D, applied to spells and feats

- **What it does:**
  - Drops all 1,426 setting, adventure and other rows: 1,043 spells and 383 feats.
  - Drops or rewrites the 26 rulebook spells that still name Golarion. Dropping all 16
    *Adventurer's Guide* rows and removing "Harrow" from the bloodline column covers 23 of
    them.
- **Why it is safe:** it is the PRD's shape and the same rule the bestiary now follows.
  Section 15 shrinks to the rulebook line, 17 books, and most of them can be transcribed
  from the PRD (§5 D's caveat about the later books applies).
- **Cost:**
  - 1,181 rows of plain mechanics that name nothing.
  - Some of them are features players use, for example Ultimate Wilderness is kept but
    Arcane Anthology, Magic Tactics Toolbox and Dirty Tactics Toolbox go.
  - Characters holding a dropped spell or feat need an alias to a rulebook equivalent, or
    a refund.

#### F2. Keep the mechanics, drop the named rows

- **What it does:**
  - Keeps the 1,181 setting rows that carry no name.
  - Drops the 245 named setting and adventure rows.
  - Fixes the 26 rulebook spells as in F1.
- **Keeps:** almost all the variety, with no prose rewritten.
- **Cost:**
  - Section 15 for every source still shipped: up to 173 setting, adventure and other
    sources, most of them lines whose declarations §6 marks **U** (could not be read).
  - "Mechanics are open" is the reading for every Paizo declaration that *was* read. It
    is not confirmed for the Campaign Setting and Player Companion lines.

#### F3. Keep every row, rewrite the names: the d20pfsrd pattern, and the one used for creatures and adventure items

What it does, in order of cost:

1. **Column-only rows (99).**
   - Delete the deity and bloodline entries. No code reads them.
   - Replace the 24 feats' deity prerequisites with something world-agnostic. One choice
     is no gate. Another is "a worshipper of a god of war", read from the world's own
     belief system.
2. **Prose-only rows (118).**
   - Rewrite only the sentences that carry the name; the mechanics stay.
   - Done the project's way: the deny-list finds the defect, a targeted call rewrites that
     sentence, and the deny-list re-checks the result.
3. **Name rows (47 real, plus 7 ids to re-slug).**
   - Retitle from the mechanics, as d20pfsrd did: Spellbane, Touch of Truthtelling.
   - Then alias the old ids.

- **Rows that do not survive a rewrite** are dropped, because the setting *is* their
  mechanics:
  - the 17 prestige-award feats;
  - Totem Spirit, keyed to Shoanti tribes;
  - Varisian Tattoo;
  - the Hellknight-rank feats.
- **Cost:**
  - Section 15 for every source, as in F2.
  - Hand review of every rewritten row, because these are rules text.
- **World Bible.** Following the standing rule that fixes are world-agnostic: if
  deity-gated rows are to mean anything in a World Bible world, the export has to name the
  world's gods **with their portfolios or domains**. A spell "associated with a god of
  trade" can then attach to the world's own god of trade. This is a new item for the next
  export, and it is needed only if F3 keeps the gates.

#### F4. F1, plus a user-side import

This is option E's pattern. The public build ships F1. A user who owns the books points
`tools/build_spells.py` and `tools/build_feats.py` at their own spreadsheets, and the
result lands in their data directory. As in E, this needs an import step in the packaged
app that does not use a terminal.

### Recommendation, for what it is worth

**F3 for the rows worth keeping, falling back to F2 where a rewrite would gut the row.**

- The PI problem is narrow: 6% of rows, and 99 of the 271 are fixed by deleting a column
  entry nobody reads.
- d20pfsrd has shown that this exact rewrite works on these exact spells.
- F1 would throw away 1,181 rows that name nothing to remove 245 that do.

**The real price of F2 and F3 is Section 15 for up to 173 non-rulebook sources whose
declarations nobody here has read.** If that transcription is not wanted, F1 is the
consistent choice with the bestiary's D: the same line, the same reasons, and an
attribution burden that can be finished from primary sources.

The owner's call.
