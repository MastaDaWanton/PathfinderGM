# Tutorials for every section: the plan (0.5.0)

The owner, 2026-11-21: *"Start formulating a plan to have a tutorial for each section that
takes the user through everything they need to know about a page or menu the first time they
interact with it and then a button to view those tutorials again this can be 0.5.0"*

The research behind this plan is in `docs/research/2026-11-21-tutorials.md`. Nothing here has
been built yet.

---

## The short version

**What the player sees:**

- The first time they open a part of the game (the Map, a bench, the Journal, their first
  fight), a small card appears beside it. The card says what that part is for and what is
  not obvious about it, in one to four short steps. Each step points at the real control it
  is talking about.
- The card never covers the whole screen. It never blocks a click and never starts a timer.
  "Got it" or Esc puts it away for good.
- Nothing shows all at once on first launch. The home page gets a single line that says tips
  will come as you go, and where to turn them off.
- **To see a tutorial again:**
  - every section has a small **?** in its own header, which replays that section's card;
  - **Settings → Tutorials** lists every tutorial with a "Show me" button, plus "Show all
    tips again" and "Turn tips off".
- **After an update**, a tutorial whose section changed shows again, but only the new steps,
  headed "New since you last looked".

**What it is built from:**

- No library. It is a small component in the house style, built on the browser's own
  `popover`, like the spell details and skill "?" cards already in the game.
- The words live in `content/tutorials/*.json`, the way the skill descriptions do. Tests fail
  in these cases:
  - a step points at a control that no longer exists;
  - a step names a button whose label has changed;
  - a step states a rules number, because numbers must come from the engine.
- Which tutorials you have seen is kept in your data folder, not in the browser. A phone on
  the LAN, or a launch that lands on a different port, still knows what you have seen.

**How big:**

- 59 sections, with roughly 150 steps between them (a few sections are one inline line).
- One lane proves the framework on three sections: the Table, the Map with Region travel, and
  the Herbalism bench. About 2½ days.
- Then four lanes run in parallel: home and creation, the table's tabs, maps and combat, and
  the benches. A short closing lane follows.
- About 10 lane-days in all, roughly 5 days of wall clock.

**What the owner needs to decide** is listed at the end, each with a recommendation. The
biggest calls are:
- whether tips are on by default (recommended: yes);
- whether they teach PF1e rules or only the screens (recommended: the screens, plus the few
  rules this app enforces in ways a 1e player would not expect);
- whether "seen" belongs to the install or to each character (recommended: the install).

---

## 1. Why this shape (what the research says)

The full notes and sources are in the research file. The parts that decided the design:

- **Front-loaded tutorials do not pay.** NN/g's controlled test of deck-of-cards tutorials
  found no gain in success or time, and the people who read the tutorial rated the tasks
  *harder*. CK3 shipped a 67-box tutorial, found that finishing it was not a major factor in
  whether players stayed, watched it stop covering new mechanics, and cut it to about a
  third. So: **no launch tour.**
- **Teaching in context pays in complex games.** In Andersen et al. (CHI 2012, 45,000
  players), tutorials only mattered in the most complex game, Foldit. There, teaching just
  before a concept was needed gave 40% more progress than an up-front manual. Pathfinder GM
  is a Foldit-class game. So: **the first time you meet a section, at that section.**
- **One hint at a time, short, and never a chain.** Chains of coach marks get dismissed
  faster and make the app look intimidating (NN/g 2014). So: **at most 4 steps, at most 45
  words a step, and one card on screen at a time.** These limits are enforced by test.
- **Don't block.** Stencils, which only let you click the thing being taught, improved
  engagement in none of Andersen's games. Our own 0.2.13 shipped an invisible layer that ate
  every click, and Intro.js has the same bug open today (#2207). So: **no overlay, no
  backdrop, nothing full-screen.**
- **Easy to dismiss, easy to find again** (NN/g 2023). So: the **?** per section, and the
  index in Settings. BG3 has a "Reset Tutorials" option for the same reason.
- **The words drift.** CK3's tutorial stopped describing the game it was in, and every tour
  vendor treats a missing anchor as a runtime incident. We already solved this for skill
  descriptions: `skills-explained.json` names the code that makes each sentence true, and
  `tests/test_skill_help.py` reads it back. So: **the same mechanism for tutorials.**
- **Licences.** Shepherd.js (from 14.0) and Intro.js are AGPL or paid, which binds a
  distributed `.exe`. driver.js is MIT, but it draws a click-taking full-screen SVG overlay,
  and it is a dependency for something the platform's `popover` already does in the top
  layer. The house rule is "No third-party code, as everywhere in play/static/js". So: **home-built.**

---

## 2. Inventory: every section the player meets

**How this was gathered:**
- Walked live on the dev server (port 8982) over a copy of the owner's 2026-11-20 save. That
  covered Shadow, in the ruins near Branford, at 1400×900 and at phone width.
- Read from `play/templates/play/*.html` and `play/static/js/table/*.js`.

**Marks:**
- **L** means seen live.
- **C** means read from code only. A fight, a model turn or a different character was needed
  to reach it, and the shared Ollama was not used for this plan.

**Triggers:**
- *open* means the section becomes visible because the player did something: a tab, a bench,
  a popup.
- *event* means the engine put it there: a fight starts, a roll is asked for, a march goes
  past eight hours.

### Home and setup

| # | Section | What the player must know | What is not obvious | First trigger | Seen |
|---|---|---|---|---|---|
| H1 | Home, **Available worlds** tab | Worlds come from World Bible; pick one to make a character in | A world "ships with the app" vs imported; entity/event counts are the world's size, not difficulty | first visit to `/` (the one welcome line only) | L |
| H2 | **Campaign card** (Continue / Crafting bench) | Continue resumes the last game; Crafting bench opens the benches without playing a turn | That the bench here and the bench at the table are the same work | first time a campaign card exists | L |
| H3 | **Import a world** | A World Bible `.json` export; checked before it lands | A refused file is refused whole, with the reason; nothing half-imports | open (button) | L (button), C (flow) |
| H4 | **Homebrew** tab | 14 workbenches for your own classes, races, spells, creatures, rules | Homebrew is per install and applies to new characters; world classes vs character classes | open | L |
| H5 | **Recent characters** tab | Play as, Delete, Forge a character | Delete is permanent; a dead character's campaign stays readable | open | L |
| H6 | **Settings: Before you can play** (first run) | Ollama and the models download from here, with a button | The 10 GB download is one-time; local is slow on purpose | open (also shown by preflight) | C (preflight passed here) |
| H7 | **Settings: Play on your phone** (LAN) | Open the door, then scan the QR | Off until pressed; the pass dies when the app closes | open | L |
| H8 | **Settings: Who does which job** (models, API keys) | Four jobs, each a model; local is the default | Hosted is optional; keys never come back out | open | L |
| H9 | **Settings: How the narrator writes / Your GM at the table / Which GM** | Free vs Planned; GM voice Off / Big moments / Always; four GM tones | Planned is measurably more accurate (0.04 vs 0.59 err/beat) but slower | open | L |
| H10 | **Settings: Sound and motion** | Levels, Steady mode, Flourishes | Steady mode makes every bench game forgiving; reduced motion is followed automatically | open | L |
| H11 | **Settings: Report a problem** | Make a report for the developer | What goes in the zip, and that it is saved, not sent | open | L |
| H12 | **Manual** (header link) | The full reference | Every tutorial links into it | none; it *is* the pull reference | L |

### Character creation

| # | Section | What the player must know | What is not obvious | First trigger | Seen |
|---|---|---|---|---|---|
| K1 | **Creator: Who / World / Race** | Pronouns come from Who; races are the world's own peoples first | "Orc of Aurvantis" is the world's people, not the rulebook's; RP is race points | open (the creator) | L |
| K2 | **Creator: Before this / Class / Paths** | Background, class, archetype paths | Paths change class features; the world's own classes run alongside | scroll into view (first time Class is reached) | C |
| K3 | **Creator: Abilities (point buy) / Favoured class** | Point buy, ceiling | The legality check runs as you go and says what is wrong | Abilities reached | C |
| K4 | **Creator: Skills** | Ranks per level; the **?** beside each skill | The **?** says what the skill does *in this game*, not just in the book | Skills reached | C |
| K5 | **Creator: Feats / Spells / Domains** | Search, prerequisites shown | Illegal picks are refused with the rule named | Feats reached | C |
| K6 | **Outfit** (`/outfit/`) | Starting gear and purse | Weight and coin are real from the first turn | open | C |
| K7 | **Homebrew builders** (class / race / spell) | Build your own; priced and checked | Race points are priced by the Race Builder | open | C |

### The table: frame and story

| # | Section | What the player must know | What is not obvious | First trigger | Seen |
|---|---|---|---|---|---|
| T1 | **The Table** (story, pen, Say, Continue) | Type what you do and press Say; the GM narrates, the engine rolls | **Continue** means your character keeps doing what they are doing and the world moves a beat; turns take a while on a local model | first `/play/` after the opening narration renders | L |
| T2 | **Exits / chips row** (Outside, Roads, suggestions) | Press a way to go there; suggestions are offers, not orders | Times on the chips are real travel time; you can always type something else | first time chips show (same visit as T1, queued after it) | L |
| T3 | **Here** chip and people | Who is present | Anyone the narration shows is really there and can be spoken to or fought | first person present | L |
| T4 | **Craft action** | Do a craft through narration | Base items made this way are real rolls and real items; it points to the bench for the full craft | open | L (button), C (panel) |
| T5 | **The left side** (portrait, in hand and worn, purse, bench buttons) | What you hold; the benches open from here | Purse coins are named for the nation | first focus or press inside the left side | L |
| T6 | **The right side / Hide sheet** | Life, body clocks (thirst, hunger, rest), abilities, defence, saves, XP | The body clocks are grace periods, and running out costs checks; Hide sheet gives the story the width | first time the body clock drops below grace, or Hide sheet pressed | L |
| T7 | **"In the scene" and Rolls panels**, **The record** | Turn order and the board in a fight; every roll shown; The record holds the engine's account of a beat | Panels fold and remember it; The record is what the engine decided, word for word | first roll recorded | C |
| T8 | **GM view** | The seams, shown only under that house rule | Only appears when the house rule is on | first time it fills | C |
| T9 | **"That's wrong"** under a beat | Tell the game it got something wrong | It pinpoints and logs; it never takes the turn back | first narrated beat (one line, inline, not a card) | C |
| T10 | **Dice popup** | Your rolls are yours to roll | NPC and hidden rolls are rolled for you; the verdict shows the maths | first roll asked of the player (inline line inside the popup, not a card over it) | C |
| T11 | **Clock / time-skip** | Time passes visibly when you rest or travel | The clock line says how long passed and why | first skip | C |
| T12 | **Talk tray** (conversation) | What was said, per person; Ignore; Take your leave | A conversation is sticky until you leave it; leaving is free | first conversation | C (tray empty here) |
| T13 | **Music** | Toggle the owner's soundtrack | The level lives in Settings | none (self-evident; index only) | L |
| T14 | **Death veil** | Who plays next | A death is final for that character | first death | C |

### The table: tabs

| # | Section | What the player must know | What is not obvious | First trigger | Seen |
|---|---|---|---|---|---|
| S1 | **Sheet** tab | Combat, manoeuvres, defence, conditions, skills, feats, class features, deeds | **Next level** is here; Earn a living; the skill **?** | open | L |
| S2 | **Level-up** (Next level) | Picking the level's choices | Choices are checked as you go | first time a level is available | C |
| E1 | **Equipment** tab | Everything carried; worn and wielded slots; Fill, Eat, Drink | Drinking in a fight is a standard action that provokes; weight counts | open | L |
| P1 | **Spells** tab and the Spells button by Say | Casters only: cast from here or type it | Prepared vs spontaneous; a refused cast says why and offers the fix | open (casters only) | C (Shadow is not a caster) |
| R1 | **Trade** tab (the counter) | Buy, sell, haggle; cargo for trade goods | The tab only works at a counter; Diplomacy haggles; trade goods follow the world's routes | open (and "no counter here" when away) | L (no counter), C (counter) |
| J1 | **Journal** tab | Matters in play (quests), what people said, where you have been, notes, the drawn map, herbarium, ledgers | Quests come from the world; a dungeon found is a quest with a map mark | open | L |

### Maps and travel

| # | Section | What the player must know | What is not obvious | First trigger | Seen |
|---|---|---|---|---|---|
| M1 | **Map tab: the ground board** | Where everyone stands; Flat/3D; looking at a floor; zoom, centre on you | Everyone keeps a square; tap a square or a person for the readout below; Key | open | L |
| M2 | **Places: town level** (3D tabletop) | Places found; press one for the way there | **Fog**: stood-in is painted, seen is grey, the rest is cloud; distance on it means nothing (no coordinates) | first Places open | L |
| M3 | **Places: Region hex board + Travel panel** | One hex a move: 5 h open, 8 h rough; press a seen hex to walk there | Each stop clears the fog in sight; a meeting or the day's end stops you; **forced march** after 8 h (Con check, rising DC, non-lethal, fatigued) | first Region view | L |
| M4 | **Forced march prompt** | Push on or stop | The numbers, from the engine | event: first time the day's travel is done | C |
| M5 | **Continent / World levels** | The world's shape; press to go in | Zooming out past a map opens the one above | first visit to each | L (crumbs only) |
| M6 | **Sea hexes / ships / passage** | Board, sail, passage chips | At sea, only aquatic creatures and ships are met; a dockless coast means swimming or a boat | event: first passage offer | C |
| M7 | **Site / dungeon boards** | A found way down becomes a quest and a map mark | Done = boss beaten OR all trials | event: first site entered | C |

### Combat

| # | Section | What the player must know | What is not obvious | First trigger | Seen |
|---|---|---|---|---|---|
| F1 | **Combat bar** | Strike, Full attack, Cast, Ability, Move, Swift, Free, Manoeuvres, Plan, Commit, End turn | One standard + one move a turn; **Commit** carries out the plan; reach is enforced and says the square; drinking provokes | event: first fight | C |
| F2 | **Turn order / the board in a fight** | Initiative order; threatened squares | Attacks of opportunity come from the squares a creature threatens | same fight, step 2 | C |
| F3 | **Nonlethal / down** | Punches and saps knock out | Nonlethal over HP = down, never dead; up and down at 0 | event: first nonlethal damage | C |

### Benches and crafts

| # | Section | What the player must know | What is not obvious | First trigger | Seen |
|---|---|---|---|---|---|
| B1 | **Herbalism bench** | Methods across the top (locked by level), satchel left, the tool, Roll Craft, the quality ladder right | Your ceiling is your level; Steady mode; Recipes, Herbarium, In progress in the footer | open | L |
| B2 | **Forge** | Rack, work order, stage, methods | Materials ledger; 1 h+ work goes In progress | open | C |
| B3 | **Enchanting circle** | Shelf, working, hours | Essence; Identify | open | C |
| B4 | **Alchemy bench** | Shelf, formula card, Formulary | Reagents; Identify a potion | open | C |
| B5 | **Leatherworking bench** | Rack, order, the vat and kettle | Harvest feeds it | open | C |
| B6 | **Minigames** (about 45: 9 herbal, 10 forge, 8 alchemy, 6 enchant, about 12 leather) | Each already has a first-time card | **Already shipped** (`33-bench-games.js`); fold into the store and index, don't rewrite | first play of each game | C |
| B7 | **Perks / recipes / herbarium dialogs** | Perk picks at level; recipe book | Perks are endless after level 3 | open | C |
| B8 | **In progress** (Works) | Unfinished work of every craft | Crafts of 1 h or more wait here and finish on time | open | C |
| B9 | **Harvest the carcass** sheet | Every craft's take from one body, at once | What each craft can take | event: first harvest | C |
| B10 | **Crafting bench page** (`/craft/`, from home) | The same benches without a turn | Time still passes for the character | open | C |

**Count: 59 sections** (12 home and setup, 7 creation, 14 table frame, 6 tabs, 7 maps, 3
combat, 10 benches). The minigames are one row that holds about 45 existing cards.

- **Seen live:** 28, four of them only in part (H3, T4, R1, M5). **Code only:** 31.
- **Not a tutorial:** hirelings and quests are worked by narration and the Journal, not by a
  screen of their own. They are covered in T1/J1 copy and the manual, not given their own
  card.

**Found while walking (not part of this work):**

- The owner's save shows a raw ref in the narration: *"There is no
  fffcb34e546e~forest:@hex-m52-35 here to go to."* That breaks the "refs never on the page"
  ruling. Flagged for the master session.
- `16-tab-map.js:126` hardcodes the forced-march numbers ("DC 10, 2 more each hour, 1d6").
  `rules/survival.py` owns them (`forced_march_dc`, `FORCED_MARCH_DAMAGE`). Phase 6 moves
  the line onto the engine's numbers.

---

## 3. The design

### 3.1 Format: section cards, and inline lines for things that are already a popup

There are two kinds of tutorial, and no tour.

1. **Section card**, for most sections.
   - **Content:** 1 to 4 steps. Each step has a short title, at most 45 words, and
     optionally points at one real control.
   - **The pointer** is a gold ring drawn on the control itself, an outline plus a
     box-shadow in `--accent`. Nothing is laid over the page.
   - **Buttons:**
     - **Next** and **Back**;
     - **Got it**, which marks the card seen;
     - **Not now**, which hides it and shows it again next time the section opens;
     - a small **Turn tips off** link.
   - The last step may carry **"More in the manual"**, linking to the matching
     `/manual#anchor`.
2. **Inline first-time line**, for anything that is already a dialog or a narrow strip: the
   dice popup (T10), "That's wrong" (T9), and the forced-march prompt (M4).
   - It is one sentence inside that element, shown the first time and then never again.
   - A card floating over a modal is a card over a card. The bench minigames' first-time
     cards (B6) are this kind already, and stay as they are.

**Why 4 steps and 45 words:**
- NN/g found chains get dismissed and one hint at a time works best.
- CK3's 67 boxes are the cautionary tale.
- Four steps is enough for the densest section (B1 Herbalism: methods, satchel, tool and
  quality, footer). Anything more belongs in the manual, which the last step links to.
- A test enforces both numbers. Raising them means editing the test, which is a deliberate
  act.

**Why not a guided tour that walks you through doing things:** Andersen measured no gain
from forcing the action, and it would stop the player playing. The card explains; the player
acts when they like.

### 3.2 When each fires

- **Only on the first interaction with that section** (the trigger column above). Never
  several on first launch.
- **On first launch**, the home page shows a single line under the header: "Tips will show
  the first time you open each part of the game. You can turn them off in Settings." It is
  not a card, and it goes away when dismissed.
- **One card at a time.** A second trigger while a card is open is queued. The queue drops
  anything whose section is no longer on screen.
- **Never over a decision in progress:**
  - never while the dice popup waits for a roll;
  - never while the player has unsent words in the pen, so a card waits until the pen is
    empty or Say is pressed;
  - in a fight, the F1 card shows when it is the player's turn and its words are short. A
    fight is when people most need the bar explained, and the card covers nothing the turn
    needs (see 3.7).
- **Waiting is a good time to read.** A local model turn takes seconds to minutes. A card
  queued while the engine device is busy shows during the wait rather than after it. This is
  the one place this app's slowness helps.
- **No timers.** Nothing auto-dismisses (WCAG 2.2.1; BG3's vanishing tips).
- **Tips off** stops every automatic card and inline line. The **?** buttons and the
  Settings index still work: help the player asks for always works, as Pendo found.

### 3.3 The "view again" buttons and the index

**A "?" per section**, the pull half:
- **Where it sits:** in an existing header row of each section: the tab page's head, the Map
  panel's head beside Places, the bench footer beside Steady mode, the combat bar's end, the
  Settings group headings. Never in the top bar, which is full at phone width.
- **What it does:** replays that section's card from step 1.
- **How it is built:** the same toggletip look and keyboard rules as the skill **?**
  (`skillhelp.js`).

**Settings → Tutorials**, the index:
- A new group in the Settings pane, grouped like section 2 (Home, Creating a character, The
  table, Tabs, Maps and travel, Fights, Benches).
- Each entry shows its title, "seen" or "not yet", and a **Show me** button.
- Show me takes you to the section when it can be reached from where you are, and replays
  the card. When it can't be reached ("Fights: you're not in one"), it shows the card's
  words in place in the index, without the pointers.
- Two buttons at the bottom: **Show all tips again** (clears seen) and **Turn tips off /
  on**.
- The table's Settings is an iframe of the same pane (`#settingsframe`), so one index serves
  both.

### 3.4 Where "seen" is kept: the data folder, per install

**The file:** `tutorials.json` in the user data directory, beside `models.json`.

```json
{"schema": 1, "off": false,
 "seen": {"map.places": {"v": 2, "at": "2026-12-01"}, "bench.herbalism": {"v": 1}},
 "welcome_dismissed": true}
```

**Why not `localStorage`:**
- **The origin changes.** `desktop.py` falls back to port 0 when 8917 is busy, and a new
  port is a new origin with empty storage, so every tip would come back.
- **The LAN device** is a different browser on a different origin, so a phone would replay
  everything the desktop has already seen.
- **The pattern exists.** Seen state is per player, not per browser (Appcues, Pendo).

`prefs.js` stays in `localStorage` on purpose ("a quiet room is quiet whatever game is
open"). Tutorials are about the player, not the room.

**Why per install and not per character or campaign:** the tutorials teach the screens, and
the screens are the same for every character. If a second person plays on the same install
(it has happened), they press **Show all tips again**. This is an owner decision (§6, D4).

**Rules for the file:**
- It is derived data in the user directory, so it carries `schema`. An unknown or broken
  file is treated as empty and rewritten. It is never fatal, and never "fresh" by timestamp
  (the World Bible stylesheet lesson in CLAUDE.md).
- It survives a reinstall on purpose: a player who reinstalls has still seen the Map.
  Per-tutorial versions (§3.5) handle the case where the Map changed.
- Writes go through the same small JSON helper `modelcfg.py` uses: read fresh, write whole.
- **API:** `GET /api/tutorials` returns the words and what has been seen. `POST
  /api/tutorials` takes `seen`, `reset` or `off`, and is LAN-token-guarded like every other
  POST.

**Migration:** the existing `pgm.games.seen.<id>` keys (B6) are read once on the table, and
any marked "1" is posted as seen. After that the store is the source. The minigame keeps its
own "until you score 0.6" rule, because that is a rule about learning the game and not about
having read a card.

### 3.5 Version stamping: show what is new

- **Each tutorial** has an integer `v`. **Each step** has `since`, the `v` it arrived or last
  changed in.
- **seen v < tutorial v:** the next time the section opens, the card shows *only the steps
  with `since` > seen v*, under the head "New since you last looked". If no step qualifies
  (a version bumped by a pure rename), seen is quietly brought up to date.
- **Never seen:** all steps show.
- **Prior art:** no vendor re-shows only the changed steps; Usetiful and PostHog make you
  restart the whole tour or mint a new id. This is our own design. It is small, and it falls
  back to the whole-tour pattern if `since` is left at 1.
- **Forgetting to bump is caught mechanically.** `content/tutorials/versions.lock` stores a
  hash of each tutorial's steps. If a step's words, anchor or control names change and `v`
  doesn't, the test fails, naming the tutorial and the step. The same test fails if `v` goes
  up while no step's `since` matches the new `v`.

### 3.6 Authoring, and keeping the words true

**Files:** `content/tutorials/<area>.json`, one per group in §2. A step looks like this:

```json
{"id": "region-travel", "v": 1, "section": "map.region", "manual": "playing",
 "steps": [
  {"since": 1, "anchor": "hex-board", "title": "One hex a move",
   "words": "Press any hex you have seen to walk there. Open ground takes {hex_hours_open} hours a hex, rough ground {hex_hours_rough}."},
  {"since": 1, "anchor": "travel-panel", "title": "Past a day's travel",
   "words": "After {march_free_hours} hours on the road, going on is a forced march: a Constitution check each hour, harder every hour, and non-lethal damage on a failure.",
   "controls": [{"tut": "hexmarch", "label": "Push on (forced march)"}],
   "source": {"file": "rules/survival.py", "literal": "def forced_march_dc("}}
 ]}
```

**The rules for authoring, each enforced by a test in `tests/test_tutorials.py`:**

1. **Anchors are `data-tut="…"` attributes, never ids or classes.** Styling selectors change
   for styling reasons; a `data-tut` exists only for this, as Appcues, Intercom and PostHog
   all advise. The test greps `play/templates` and `play/static/js` for every
   `data-tut="<anchor>"`. A missing one fails with *"tutorial map.region step region-travel
   points at data-tut=hex-board, which no template or script draws"*.
2. **A control a step names must still carry that label.** `controls` lists each `data-tut`
   and its visible label, and the test finds the element's source and checks the label text.
   This catches "the button was renamed and the tutorial still says the old name".
3. **No digit in `words` that is not a placeholder.** Every number in a tutorial comes from
   `{name}`, filled by `rules/tutorialfacts.py` from the engine's own constants: for example
   `survival.forced_march_dc(1)`, `journey.HOURS_PER_DAY`, the hex hours from
   `rules/hexes.py`. An unknown placeholder fails the test, and so does a bare digit. This is
   the "no model authors a number" law applied to us.
4. **A rules claim carries `source: {file, literal}`**, read back by the test exactly as
   `test_skill_help.py` does. If the code that makes a sentence true is deleted, the sentence
   fails.
5. **`manual` must be an anchor that exists in `manual.html`.**
6. **At most 4 steps, at most 45 words a step, and every section in §2 has an entry or an
   explicit `"none": "why"`.** The test reads the section ids from a small list in the same
   file, so a new tab or bench without a tutorial is a failing test, not a forgotten one.
7. **The page is never sent `source` or `controls`** (the same rule as `skillhelp.for_page`,
   and the "refs never on the page" ruling).

The browser side is checked live, not only by grep: the extended hit test (§3.7) opens each
reachable card and reports any anchor it could not find on the page.

### 3.7 The hit test and the overlay

The release hit test (`tools/table_hit_test.js`) asks the browser what is under the middle of
every visible control. The card is built so the two coexist:

- **The card is the only new box.** It is a `popover="manual"` element in the top layer:
  - no backdrop and no full-screen element;
  - no `::backdrop` styling;
  - the pointer ring is CSS on the target itself.
- **A static test** fails if the tutorial CSS gives any element `inset: 0`, `100vw`/`100vh`,
  or a `::backdrop`.
- **The hit test grows a mode.** `tools/table_hit_test.js` gains `{tutorial: "<id>"}`, which
  opens that card and runs the same check with these rules:
  - controls under the card's own rectangle are allowed to be covered;
  - nothing in `MUST_SHOW` may be covered (End turn, Commit, the pen, Say);
  - the card may take no more than 25% of the viewport.
- **The release check runs twice:** once with tips off, exactly as today, and once per table
  card that can be reached at the four release sizes. `docs/packaging.md` gains the step.
- **Placement** tries beside the anchor, then above, then below (CSS anchor positioning in
  Electron), and falls back to measured placement where anchor CSS is missing (a LAN Safari
  before 26).
  - It never sits over the pen row or the combat bar's commit and end buttons.
  - At phone width it docks under the tab strip, at the top of the stage, never at the
    bottom where the pen is.

### 3.8 Accessibility

| Case | What happens |
|---|---|
| **Opened by the player** (? or Show me) | Focus moves to the card's heading. Tab stays in the card while it is open, and Esc closes it. Focus goes back to the **?**, or to the section if the **?** is gone (WAI-ARIA APG dialog). |
| **Opened automatically** | **Focus is not taken.** The player may be typing in the pen. The card's first step is announced through the table's existing polite status region. F6 moves focus into the card, and Esc dismisses it as "Not now" when focus is not in a text field with words in it. |
| **Markup** | `role="dialog"`, non-modal (no `aria-modal`, because the page behind it stays live, which is the APG's rule), with `aria-labelledby` pointing at the step title. Next, Back and Got it are real buttons. |
| **WCAG 2.4.11** | Placement must never wholly cover the focused element. The hit-test mode also checks `document.activeElement`. |
| **Motion** | A 120 ms fade, and none under `prefers-reduced-motion` or the Flourishes "Short" preference (`PGMPrefs`). The ring does not pulse. |
| **Timing** | No auto-advance, ever. |

The existing minigame card's 2-second auto-start is the one exception in the app, and it is
raised as an owner decision.

### 3.9 Rules in tutorials

- Rules are named and explained in a clause: "a forced march", "non-lethal damage", "an
  attack of opportunity". General PF1e is left to the manual.
- **The cards teach the rules this app enforces in ways a player would not guess:**
  - forced march;
  - nonlethal knocks out and never kills;
  - drinking in a fight provokes;
  - melee reach is refused with the square named;
  - fog clears only where you have looked;
  - a craft of an hour or more goes to In progress;
  - Continue means the world moves a beat.
- Every number is a placeholder filled from the engine (§3.6 rule 3), so an engine change
  updates the tutorial by itself, and a deleted rule fails the test.

### 3.10 Tone

- **The game's own voice:** second person, plain, short. The same register as the Travel
  panel ("On foot, one hex a move …") and the manual.
- **No UI jargon:** "the pen", not "the input field". A mechanic may be named.
- **The words must not get ahead of the code.** No "you can…" for something the engine
  doesn't do. Rule 4 enforces this for rules claims; review enforces it for the rest.

**Example, T1 (the Table), 3 steps:**

> **What do you do?** Write it here as you would say it to a GM, and press **Say**. The GM
> tells the scene; the rules decide what happens. A turn takes a little while: the model is
> running on your own machine.
>
> **Continue** You keep doing what you are doing, and the world moves a beat.
>
> **The ways on** Press a way to go there. The time on it is real time passing. These are
> offers; you can always write something else.

### 3.11 Narrow widths and the LAN device

- **At phone width:**
  - the card is a strip docked under the tab strip, full width less the 16 px gutters;
  - Back and Next sit on one row;
  - the ring still marks the target, and the stage scrolls the target into view first.
- **The LAN device** reads and writes the same `tutorials.json` through the server. A card
  dismissed on the phone is dismissed on the desktop.
- **Without `popover`** (old Safari), the card falls back to an absolutely placed element.
  The house does the same feature check (`HAS_POPOVER` in `10-spells.js`). That path gets one
  test at 375×812 in the browser.

---

## 4. Build plan

All work is in worktrees under `C:\Users\natha\pgm-work\`, on branches off fresh master, with
Conventional Commits. Every lane:
- runs the whole suite;
- verifies live on its own port, at 1400×900 and 375×812;
- runs the hit test with a card open.

UI lanes load **frontend-design** and **design-taste-frontend** and keep the existing colours,
`v2-` button classes and fonts. Plain JS, no React.

### Phase 1: the framework and the first slice (one lane, about 2½ days, blocks the rest)

**Scope:**
- the store and the API;
- the card component;
- the inline-line helper;
- the **?** button;
- the Settings index;
- the tests;
- the hit-test mode;
- three real sections, proving each kind:
  - **T1+T2, the Table:** auto on arrival, queued behind the opening narration, the
    pen-has-words rule;
  - **M2+M3, Places and the Region board:** fog, travel, the forced-march words from engine
    placeholders;
  - **B1, the Herbalism bench:** a card inside a full-screen bench layer, the **?** in the
    footer, the minigame-store migration.

**Files:**
- **New:** `play/tutorials.py` (store and view), `rules/tutorialfacts.py`,
  `content/tutorials/{table,maps,benches}.json`, `content/tutorials/versions.lock`,
  `play/static/js/tutorials.js` (one IIFE, `window.Tutorials`), `tests/test_tutorials.py`.
- **Changed:**
  - `pathfindergm/urls.py`;
  - `play/templates/play/home.html` (the Settings group and the welcome line);
  - `table.html` (`data-tut` attributes, CSS, script tag);
  - `16-tab-map.js` and `30-bench-shell.js` (`data-tut`, ? and triggers);
  - `33-bench-games.js` (seen migration);
  - `tools/table_hit_test.js`;
  - `docs/packaging.md`.

**Tests:**
- the seven authoring rules (§3.6);
- store robustness: missing, broken or unknown-schema file, and a second device;
- the versions lock;
- the static no-overlay CSS test;
- what's-new filtering.

**Done means:**
- all three sections fire once, live, at both sizes;
- Got it, Not now, ?, Show me, Show all tips again and tips off all work;
- a phone on the LAN sees nothing it already dismissed on the desktop;
- the hit test is clean with each card open;
- **the packaged build** (`win-unpacked`, run over a throwaway data dir) does the same, with
  a stale `tutorials.json` of `schema: 0` seeded to prove the fallback;
- the owner has looked at the three cards before the other lanes start.

### Phases 2 to 5: the sections (four lanes in parallel, after phase 1)

Each lane writes its JSON, adds `data-tut` and triggers to its own files, and adds its
section ids to the coverage list.

| Phase | Lane | Sections (§2) | Files | Estimate |
|---|---|---|---|---|
| 2 | `feat/tutorials-home` | H1–H12, K1–K7 | `home.html`, `outfit.html`, the three builders, `content/tutorials/home.json`, `creation.json` | 1½ days |
| 3 | `feat/tutorials-table` | T3–T14, S1–S2, E1, P1, R1, J1 | `table.html`, `02-state.js` (record), `04-combat-and-turns.js` (dice popup line), `08-conversation.js`, `09-clock.js`, `12-shell.js`, `17`–`21` tab scripts, `22-roll-verdict.js`, `23-thats-wrong.js`, `content/tutorials/table.json` | 2½ days |
| 4 | `feat/tutorials-maps-fights` | M1, M4–M7, F1–F3 | `16-tab-map.js`, `16-places-world.js`, `24`/`25` map scripts, `places-board.js` (DOM anchors only, never a 3D object), `04-combat-and-turns.js` (combat bar), `content/tutorials/maps.json`, `fights.json` | 2 days |
| 5 | `feat/tutorials-benches` | B2–B5, B7–B10 (B6 indexed only) | `40`/`45`/`50`/`55` shells, `36-bench-perks.js`, `37-works.js`, `59-harvest.js`, `craft.html`, `content/tutorials/benches.json` | 2 days |

**Overlap.** Phases 3 and 4 both touch `04-combat-and-turns.js`. Phase 3 only adds the dice
popup's inline line; phase 4 owns the combat bar. Each keeps its edit small and says so.

**Done means, per lane:**
- every section in its rows fires live or, for an event that cannot be staged cheaply, is
  driven by a scripted scene (the existing `tools/` probes);
- the coverage test lists no missing section of its own;
- the hit test is clean;
- the whole suite passes.

### Phase 6: close (one lane, about 1 day)

- `16-tab-map.js`'s forced-march line takes its numbers from `rules/tutorialfacts.py` (the
  drift found in §2).
- The manual gains a "Tips and tutorials" paragraph.
- Write the release notes.
- Run the full packaged hit test at four sizes with every reachable card, plus the LAN check
  from a second browser.
- Release 0.5.0.

**Total:** about 11½ lane-days. With phases 2 to 5 in parallel, about 6 days of wall clock.

### Risks

| Risk | Guard |
|---|---|
| A card eats clicks (0.2.13 again) | Top-layer popover, no backdrop, static CSS test, hit test with a card open, run in the packaged build |
| The words go stale | `data-tut` anchors, label checks, engine placeholders, `source` read-back, versions lock. None of these catch a sentence that is merely misleading, so each lane that changes a section is asked to re-read its tutorial; this is review, not a test, and stated as such |
| Too much text | 4 × 45 cap, owner review of the first slice before phases 2–5 |
| Cards annoy during play | One at a time, never over the pen with words in it, shown during model waits, tips off in one press |
| Two people on one install | Show all tips again; owner decision D4 |
| A LAN browser lacks `popover` or anchor CSS | Feature-detected fallback, tested at phone size |
| Events that are hard to reach in testing (first death, first harvest) | Scripted scenes; marked unverified-live in the lane report if they could not be staged |
| A 3D board has no DOM anchor | Anchor to the board's frame, never a 3D object |
| `tutorials.json` broken by a crash mid-write | Write to a temp file and replace; a broken file reads as empty, so the worst case is tips again |

---

## 5. What was considered and turned down

| Option | Why not |
|---|---|
| **driver.js** (MIT) | Its overlay is a full-screen SVG that takes clicks, our 0.2.13 bug class. It is 15 KB gzipped for what `popover` gives free, against the house "no third-party code" rule. It stays the fallback if the home-built card proves hard. |
| **Shepherd.js / Intro.js** | AGPL (Shepherd from 14.0, Intro.js from 2.x). A distributed `.exe` would owe its source or a paid licence. Intro.js also has a click-swallowing layer bug open. |
| **One first-launch tour of everything** | NN/g: no gain and tasks felt harder. CK3 cut its 67 boxes. It also breaks the owner's "first time they interact with it". |
| **A dimmed backdrop with a cutout** | It blocks play, which is Andersen's stencil result, and it is exactly what the hit test exists to catch. |
| **Per-browser `localStorage` for seen** | Lost on a port fallback, not shared with the LAN device. |
| **Per-character seen** | The screens don't change per character. A fourth character would replay everything. Kept as an owner option. |
| **Tutorial words in the JS** | They could not be tested against the engine, and the forced-march line shows the drift that follows. |
| **Help that guesses when you're stuck** (Clippy-style) | NN/g: bad inference is worse than none. The **?** is the pull, and the player chooses it. |

---

## 6. Owner decisions

| # | Question | Recommendation | Why |
|---|---|---|---|
| D1 | How much shows on first launch? | **One dismissible line on the home page**, nothing else. The first real card is the Table's, after the opening scene. | Front-loaded tours measured worse; the owner's own words say "the first time they interact with it". |
| D2 | Are tips on automatically, or opt-in? | **On by default**, with Turn tips off in every card and in Settings. | NN/g says show at first encounter; Civ VII ships tutorials on by default; opt-in tips are found by the people who need them least. |
| D3 | UI only, or PF1e rules too? | **The UI, plus the rules this app applies in ways a 1e player wouldn't guess** (§3.9), one clause each, numbers from the engine. General 1e stays in the manual, linked from the card. | Keeps cards short; the depth is the product, but the manual is where depth belongs. |
| D4 | Is seen per install or per character? | **Per install**, with Show all tips again for a new person. | The screens are the same for every character; LAN and port changes need it on the server anyway. |
| D5 | A ? per section as well as the Settings index? | **Both.** | Easy to find again at the point of use (NN/g); the index answers "what is there to learn?". |
| D6 | After an update, show what changed automatically? | **Yes, the changed steps only, once**, headed "New since you last looked". | It replaces the three hand-built "after the revamp" notices with one mechanism. Those three stay as they are; they convert saves, not just words. |
| D7 | The minigame first cards start the game by themselves after 2 seconds. Keep that? | **Keep it, and add the pause key to the card's words.** Or wait for a press under Steady mode. | Timed starts trouble WCAG 2.2.1; Steady mode is where players who need time already are. |
| D8 | Ship it all at once as 0.5.0, or the first slice early? | **All at once as 0.5.0**, after the owner reviews the first slice. | One coherent feature with one version stamp baseline (`v: 1` everywhere). |
| D9 | Should the welcome line also offer the manual? | **Yes: "or read the Manual"**, linking the header's Manual. | The manual already exists and is good; this is the cheapest pull. |
