# Book and ledger: a free mock of the play table

The owner asked for a second mock with no limitations: "make it the best you can usable and
stylish whatever you want", for Pathfinder GM. This is it. It sits beside
`docs/mock/table-layout/` (the first mock, which preserved the app's leather and gilt) and
shares nothing with it but data.

It is **not part of the app**. There is no Django view and no URL, nothing under `play/`
changed, and `docs/` is not bundled (`pathfindergm.spec`). Nothing on the page reaches the
engine or a model. Every reply to a click is either real engine output copied into
`data.js`, a number computed from the real sheet, or a line that begins "Mock." and is set in
the interface's voice, never the narrator's.

## Opening it

From the repository root:

```
python -m http.server 8767 --bind 127.0.0.1
```

then open <http://127.0.0.1:8767/docs/mock/table-free/>. It must be served from the root: it
loads the app's own `play/static/js/dice3d.js`, `play/static/js/scene3d.js` and the
game-icons SVGs by relative path, and a file:// page cannot fetch the icons.

**Options** (top right) holds the page settings (light: System, Day, Night; story text:
Smaller, Book, Larger) and the mock's scenes: go to the recorded fight, talk to the guard,
stand at the market counter, be wanted in Zhilvarnia, start again. The dashed **Mock: Kesst |
Ysolde** switch in the bar (and at the head of Character and Spells, so a phone has it too)
swaps the rogue for the wizard.

## The design read

Reading this as: a long-session play surface for one person who reads for hours and fights
now and then, where the prose is written slowly by a local model and every number is decided
instantly by a rules engine. Dials: variance 5 (an application, not a landing page), motion 3
(the owner's rule: motion only in answer to an action, or ambient behind content), density 6
(the page airy, the ledger dense).

**The idea, in two sentences.** The table is split by who is speaking: the GM's prose is set
as a book in the centre, and everything the rules engine decides is written in a second,
ledger voice on the ruled margin beside the paragraph it caused. Everything you can do lives
in one dock under the pen, which changes shape with the situation (exploring, talking,
fighting) instead of sending you to another screen, so the eye has two homes: the page and
the dock.

The architecture already severs the two voices: the narrator is fed tells and nothing else
about mechanics, and no model authors a number (`CLAUDE.md`, the three laws). The page shows
that seam instead of hiding it. A player who wants to know why a blow landed looks left, at the
line beside the sentence that said so.

## The token system

### Palette: lamplit slate, with a day paper

| Token | Night | Day | Job |
|---|---|---|---|
| `--room` | `#161a20` | `#d5dbe0` | behind everything |
| `--page` | `#1b2028` | `#f6f7f8` | the book |
| `--panel` | `#212731` | `#ecf0f2` | bar, rail, dock |
| `--ink` | `#e8e2d5` | `#1b222a` | body text |
| `--accent` (verdigris) | `#74b8a8` | `#23695c` | you, open, lit, go |
| `--blood` | `#e2786a` | `#a8322a` | foes, spent, shut, damage |

One accent, and it means "yours / open / go" everywhere: your token, a lit spell socket, a
reachable square, the primary button. Blood is not decoration; it means foe, spent, shut or
hurt, and nothing else. The ledger margin is a mix of page and panel
(`color-mix(in srgb, var(--page) 55%, var(--panel))`), ruled every 22px with a double rule
at its edge, like account paper.

**The lamp.** A faint radial light over the page takes its hue from the hour (the engine's
own `residency.day_part` words, exported for every hour into `data.js`): rose at dawn, almost
nothing by day, amber at dusk, blue at night. It transitions over 2.4s and sits behind the
text. It is the only motion nobody asked for, and it carries information: the page's colour
says what time it is.

**Light and dark.** The default follows the system. NN/g's review found light mode better for
acuity and proofreading, with the gap growing as text gets smaller, and recommends light as
the default with a dark switch; players often play at night, so both are first-class and the
choice is remembered per viewer.

### Type: two voices

- **Literata** (TypeTogether for Google Play Books, drawn for long reading on screens): the
  GM's prose, place names, your own words (italic), suggestions (italic, because they are
  words you might say), people's faces, item and spell names.
- **Sofia Sans Semi Condensed**, tabular figures: the ledger and every control. Condensed,
  because the margin is 13.5rem and a to-hit line has to fit on one rule.

Story text is 20px (18px on a phone) at line-height 1.62, with Smaller / Book / Larger. The
measure is `var(--story-size) * 31.5`, which measured **66 characters a line** on the
recording's gate paragraph at 1440x900 (the first try, 34em, resolved against the 15px UI
size and gave 55; 33 story-sizes gave 69.4). Rello, Pielot and Marcos (CHI 2016) found
fixation times still falling at 18pt; the Larger setting is there for that.

### Layout

```
1440x900, exploring
+-------------------------------------------------------------------------------------+
| (K) Kesst Vayr   Life 9/9 ===   AC 15   Touch, flat 13 12 | 08:10 Early morning,  |
|                                                            day 1 | Table Character ... |
+---------------+------------------------------------------------+--------------------+
| ledger margin | the book, 66 characters                        | Here               |
|  07:52        |  You: I ask the smith about the ore he uses.   |  From here         |
|  Said, 4 lines|  The smith looks at the ore...                 |   Next door ...    |
|               |  The gate                                      |   Outside ...      |
|  Moved        |  The heat of the smithy fades...               |  People here       |
|  Time 08:10   |                                                |   The guard [Talk] |
|---------------+------------------------------------------------|  Your body         |
|    Suggested  |  I tell him I'm headed for the outskirts.      |   Thirst Hunger    |
|               |  [ What do you do?                     ] [Act] |   Rest             |
|               |  Say  Continue  Craft action  Trade  Cast      |                    |
+---------------+------------------------------------------------+--------------------+

In a fight the same page grows a ribbon and the rail becomes the board:
| Round 1 | (16) Borin Lyraxys, has acted | (9) Kesst Vayr, your turn |
| margin: rolls |  prose                                   | The board [Flat|3D]   |
| Your turn     |  Strike Full attack Ability Swift Free   | Targets (distance)    |
|  o Standard   |  plan: Move to D4 x  Strike Borin x  [End turn] [Commit turn]  |
|  o Move ...   |  [ Add words for the GM ]         [Add]  | Ways out (withdraw)   |
```

The margin and the book share one centred grid lane, and the dock sits on the same lane, so
the margin runs down into the dock: in a fight the turn's budget (Standard, Move, Swift, Free)
is written in the margin column, beside the actions that spend it.

- **1240px and up**: three columns, as drawn.
- **860 to 1239px** (1024x768): the margin folds into the page. Each beat's entries become
  slips in a row above the paragraph they belong to, so the link between roll and sentence is
  kept by position when the margin is gone.
- **Below 860px** (375px): one column. The rail becomes a sheet: **Here** (first in the dock
  row, outlined) in exploration, **Board** (first in the action row) in a fight. The mode tabs
  are a second bar row that scrolls sideways. Suggestions become one sideways row of cards.

Alignment: text is left-aligned throughout; numbers right-aligned in their column.

### Shape and principles

- Radius: 3px on every control and card, 6px on anything that floats over the page
  (menus, dialogs, the counter, the dice mat), a full circle only where a circle means
  something (a spell socket, an action pip, a token, an initiative number).
- **Every number opens to its parts.** Press AC, a save, a skill, a to-hit, a damage figure,
  CMB, a manoeuvre, a need: a card lists `full_sheet()`'s own terms (base 10, leather armour
  +2, Dex +3). It stays open until dismissed.
- **Rolls are shown in full, not collapsed.** Each entry lists the die, every modifier with
  its source, the total, and what it was against with the engine's own explanation
  ("AC 10 (flat-footed) with cover").
- **The engine answers first.** A new turn writes its entries in the margin at once, and the
  page says "The GM is writing. The rules have already answered, in the margin." while the
  prose is slow. The brief measured local latency in minutes; this is designed for, not hidden.
- **Nothing yanks the reader.** A new beat lands with its first line at the top of the page,
  not scrolled to the bottom. If you have scrolled back to reread, nothing moves under you; a
  "New lines below" button appears instead.
- **Each choice appears once.** A move is an exit in the rail, never also a chip; chips are
  everything else and fill the pen, never send.
- **Your turns are dated** in the margin (the ledger's date column), so reading back says when.

## What the table does, and where

| Asked for | Where it is |
|---|---|
| The story, long-form | The book. Recorded prose verbatim; place headings in Literata |
| The pen, Say, Continue, Craft action, suggestions | The dock. Enter acts; Say toggles speech (your line is set in quotes); Continue adds a beat and moves the clock (ruling 2026-09-18: the PC keeps their action, the world advances); Craft action opens hours (1 to 48) and the ways of gathering on this ground; suggestions fill the pen |
| Exits, journeys, shut ways | The rail's **From here**: Next door, Outside, Roads, with time in words (a shared time said once per group). Wanted in Zhilvarnia greys the watched ways; pressing one opens the engine's reason under it. The road to Xylorvotha asks before five days pass |
| Leaving mid-fight is a withdraw | The fight rail's **Ways out**: every way is a withdraw (your whole turn), and the line above says whose reach covers the way to the door before you commit. A committed withdraw rolls those foes' strikes and leaves the fight |
| Initiative, whose turn, round | The ribbon over the stage |
| Action economy, Strike, Full attack, Ability, Cast, Swift, Free, Commit, End turn | The combat dock. Actions are planned as chips and nothing happens until Commit. Full attack is refused once you have moved. Strike out of reach is refused with the squares named ("Borin Lyraxys is at E4, 15 ft from B4. Your rapier reaches 5 ft") |
| Targets with attitude | The fight rail's **Targets**, with distance from where you will stand after your planned move |
| 2D grid and 3D view | The board, Flat or 3D. Flat shows walls, the gallery and its rail, rough ground, reachable squares, foes' reach, the door, and your planned path. A move whose path leaves a threatened square says who gets the attack of opportunity; a single clean square is a 5-foot step and says it does not provoke. 3D is the app's own `Scene3D.render`, fed the same grid, turned in quarter turns; its reachable squares are clickable too |
| Dice | The app's own `Dice3D.land` for your rolls (attack, manoeuvre, haggle), re-dressed in this page's tokens: pewter dice, a verdigris face where it lands. Foes' rolls are the engine's and go straight to the margin |
| The character | **Character**: portrait slot, abilities, saves, needs, features and feats, life, AC/touch/flat-footed, CMD, initiative, every weapon's to-hit (iteratives written +a/+b when there are any), damage, crit, type and range; every manoeuvre with its bonus and whether it provokes; every skill, class skills marked, trained-only ones "untrained" |
| Conditions, XP, body's needs | Bar (life, AC, touch, flat, conditions when any), rail (needs), Character (XP bar, needs with the engine's own detail) |
| Equipment | **Gear**: what is on you by slot, the purse in the world's coin, and what you carry with names always shown, kind tabs with counts, a find box, order by kind / name / value; Wield, Wear, Take off, Use, Drop on every row. 43 things for the rogue |
| Spells | **Spells** (casters only): sockets per level (lit open, red spent), prepared cards with the numbers on the card (range, target, save and DC), Details, Cast. Cast puts the spell on your turn as a chip under the pen; it is not sent. Rest and prepare (9 hours) brings slots back and pops the clock |
| Trade | Trade, only where somebody keeps a counter (the market, the merchants row), else it names the nearest counter. One basket holds buying and selling with steppers, the net price, a haggle roll, and "you are N short" before you can pay |
| Conversation | **Talk** on a person: the rail's top becomes the conversation (speech only), with regard, Ignore and Take your leave. Hide folds it to one line without ending it; it is sticky until you leave it (ruling 2026-09-24) |
| Journal, clock, map | **Journal**: matters in play, the road so far, what people said word for word. **Clock** in the bar; an hour or more pops a dial that sweeps the hours and counts the days, then closes itself (the margin keeps the record). **Map**: the 43 places of Zhilvarnia as the exits join them; press one for the route and Walk there |

## Research, and what it changed

The standing instruction is to search before designing. A research pass collected primary
sources where they could be reached; claims it could not source are marked here as such.

- **Owlcat, Pathfinder: Kingmaker, "Update #37: the combat log, it's how we roll"**
  (<https://forum.owlcatgames.com/t/update-37-the-combat-log-its-how-we-roll/12771>): every
  combat line opens to every bonus and penalty with its source. Taken whole: the margin
  entries and the press-any-number breakdowns. (The Kickstarter copy returned 403; the content
  was confirmed from the forum post and search excerpts.)
- **Larian, Baldur's Gate 3, Nick Pechenin on the dice UI**
  (<https://www.gamedeveloper.com/design/tides-of-chaos-how-i-baldur-s-gate-3-i-tackles-the-rng-of-d-d-inspired-dice-rolls>):
  a minimalist single number confused players, who took the sum of bonuses for the DC; Larian
  moved to showing how the number is made. Taken: the total is always beside its parts and
  what it was against.
- **BG3 forums on the combat log**
  (<https://forums.larian.com/ubbthreads.php?ubb=showflat&Number=821911>): auto-scroll made it
  "near impossible to consult older entries". Taken: new beats land at their top, and never
  move a reader who has scrolled back.
- **BG3 Early Access Patch 7** (<https://forums.larian.com/ubbthreads.php?ubb=showflat&Number=807744>):
  the hotbar that auto-filled with every spell was replaced by decks, and turn order moved to
  the top centre. Taken: initiative across the top; the Cast menu lists only what is prepared,
  grouped by level.
- **Foundry VTT chat and combat**
  (<https://foundryvtt.com/article/chat/>, issue <https://github.com/foundryvtt/foundryvtt/issues/11456>,
  v13 notes <https://foundryvtt.com/releases/13.332>): rolls collapsed by default are
  "often problematic/tedious" to users; v13's fading UI and timed notifications drew
  complaints. Taken: breakdowns open and stay open; the toast carries nothing the ledger does
  not also keep; nothing fades while you read.
- **Owlcat, Wrath of the Righteous turn-based mode** (<https://wrath.owlcat.games/news/16>):
  the planned path shows the attacks of opportunity along it before you commit. Taken: the
  planned move names who strikes, and the ways out say it before a withdraw.
- **Failbetter, Sunless Sea post-mortem**
  (<https://www.gamedeveloper.com/audio/postmortem-failbetter-games-i-sunless-sea-i->): the
  separate combat screen "yanked the player out of our carefully layered atmosphere" and was
  scrapped. Taken as the structural decision: the fight happens on the same page as the story.
- **Failbetter, Fallen London redesign**
  (<https://community.failbettergames.com/t/dev-blog-insights-into-the-fallen-london-redesign/18507>):
  a card-flip animation made testers nauseous and was cut; a scroll bar that hid equipment
  from comparison was cut; information that affects a decision went back onto the card. Taken:
  no reveal animations on menus; spell cards carry range, target and save DC on their face;
  gear is a list you can see whole.
- **Disco Elysium, ZA/UM devblog on active checks**
  (<https://discoelysium.com/devblog/2016/10/06/active-skill-checks>): a check is shown as the
  attempt, with its odds, before commitment. Taken in spirit: the plan is a set of chips you
  can remove before Commit. I could not source any designer statement on the column's width.
- **Latitude, AI Dungeon** (<https://help.aidungeon.com/faq/how-to-play>, Heroes dev log #7
  <https://latitude.io/news/heroes-dev-logs/7>, the latter from search excerpts only): Do /
  Say / Story modes, Continue, and clickable suggested actions added because players did not
  feel creative enough, kept beside free text. Taken: Say as a mode of the one pen, Continue,
  suggestions that fill the pen.
- **inkle, Jon Ingold on text density**
  (<https://narrativenews.substack.com/p/inkles-jon-ingold-on-the-craft-of>): readers judge a
  wall of text before reading a word. Taken: a heading per place, generous leading, the
  measure held at 66.
- **Readability**: Bringhurst's 45 to 75 characters, 66 ideal (<http://webtypography.net/2.1.2>);
  Dyson and Haselgrove 2001 on screen line length
  (<https://www.researchgate.net/publication/220106760>); Rello, Pielot and Marcos, CHI 2016, on
  size (<https://pielot.org/2016/01/optimal-font-size-for-web-pages/>); NN/g on dark mode
  (<https://www.nngroup.com/articles/dark-mode/>).
- **Could not source**: how Solasta shows spell slots and its action bar (the dev diary
  returned 403); any inkle statement on 80 Days' clock. The dial here is not modelled on 80
  Days for that reason.

## Decisions, and what was rejected

- **Rejected: a combat log panel.** The app's table keeps rolls in a separate Rolls panel
  (`#panel-rolls`). A log panel is where Owlcat, Larian and Foundry all put it, and all three
  then spent patches making it readable. The margin puts each roll beside its sentence, which
  a log cannot do.
- **Rejected: a separate combat screen** (Sunless Sea, above).
- **Rejected: an icon grid for gear.** The owner said icon-only is painful with lots of gear,
  and Wrath's inventory was fixed by modders with search and filters. Names, counts, a find box.
- **Rejected: pills for suggestions.** They are words you might say, so they are set as your
  own italic lines, hung off a rule, not as buttons in the SaaS style.
- **Rejected: boxes in the margin.** The first build drew each roll as a bordered card on the
  ruled margin; on screen it read as a stack of sticky notes. Entries are now written on the
  rules, one 22px line each. The boxes return only where there are no rules to write on (the
  folded margin at 1024).
- **Rejected: auto-closing popovers and fading chrome** (Foundry v13's complaints).
- **Rejected: odds before a strike.** Disco Elysium shows odds, but the player in 1e does not
  know a foe's AC, and printing it would leak what the engine knows. The to-hit is shown; the
  AC arrives with the roll.
- **Rejected: a stat sidebar always on screen.** The bar carries life, AC, touch and
  flat-footed, conditions and the clock; the whole sheet is one tab away, and every figure on it
  explains itself.
- **Kept from the first mock**: exits from the place graph, one choice in one place, shut ways
  that say why, the journey confirm, the free outfit page's absence (gear comes from counters).
- **The fight stays on the page's palette.** Foes are blood, you are verdigris, bystanders are
  ink. The 3D view is the app's renderer with the app's own materials (it keeps its brown
  stone); the dice mat is re-dressed from outside by CSS.
- **Motion, all of it**: a new beat fades in over 0.22s (it answers your action); the counter
  and the phone sheet rise 0.2s when opened; the dice tumble (the app's own); the clock dial
  sweeps 1.4s when an hour or more passes; the lamp shifts hue over 2.4s behind the text.
  Menus and popovers open instantly and never move what was under the pointer.

## What is real and what is example

Real, generated by `build_data.py` (run from the repository root; nothing in `data.js` is
hand-written):

- **Exits**: `play/exits.py exits()` at all 43 places of Zhilvarnia at 08:00, plain and wanted.
- **The gate**: the story, suggestions and the two people with their faces, from
  `tests/replay/2026-09-25-town-tags-retag-gemma4-12b.jsonl.gz` (as the first mock).
- **The fight**: `tests/replay/2026-09-25-fight-bodies-gemma4-12b.jsonl.gz`, the save before
  turn 4: the 10x9 grid with its walls, rough square, raised gallery and rail; everyone's
  square; initiative (Borin Lyraxys 16, Kesst 9); round 1; the opening attack with its terms
  and DC explanation, the sneak attack, the damage, the tell, the XP; and the prose, verbatim.
  Borin's AC 13 and unarmed strike (+3, 1d3-1) are `full_sheet()` read back through
  `rules.sheet.from_dict`.
- **Both sheets**: `rules.sheet.full_sheet()` and `summary()` for `fixtures/pc-kesst.json` and
  `fixtures/pc-caster.json`, every term. Each manoeuvre's "provokes" is
  `rules.tables.MANEUVERS[...]["provokes"]` unless the sheet has its Improved feat. Weapon range
  is `rules.tables.WEAPONS[...]["range_ft"]`.
- **Counters and coin**: `rules.goods.goods_at("market")` (40 kinds), `goods_at("smithy")`,
  `goods_at("tavern")`, a slice of `table_goods("weapons")`; the coins are
  `rules.goods.coinage()` for Zhilvarnia ("Khy'vyr gold piece", coined by the app). Selling at
  half is `rules.pricing.SHOP_BUYS_AT`; the wanted markup of half again is
  `rules.pricing`'s own rule.
- **Spells**: `content/spells/spells.json` for the wizard's 26 book spells; slots are the
  sheet's pools (3 cantrips, 2 first-level). DC 13 plus level.
- **The clock's words**: `rules.residency.day_part()` for every hour.

Example, and said so on the page where it shows:

- The rogue's load past the fixture's rapier, dagger, leather armour and outfit (marked
  "(example)" on each row, at the Core tables' real prices); the wizard's spellbook row and
  kit; both purses.
- Attitudes ("indifferent", "hostile") and the 0 to 100 regard value: the recordings have none.
- Every d20 after the recorded opening; the foe's turn logic (close in, strike); the reach walk
  (Dijkstra, diagonals at one and a half squares, rough ground doubled, the gallery out of
  reach); the door at E9 (the square Kesst entered by in turn 0).
- The Craft action list; the haggle's Diplomacy roll against 15 and its ten per cent (the
  engine's real haggle caps the ask at a price agreed in talk).
- The two matter names are the recording's own; "the road so far" is built from this page's
  own moves.

Shown verbatim though flawed, because they are the recording's: "man with a thick" is a
naming defect of that session, and "I punch him in the face" rolled a rapier because the
recording predates the nonlethal-strikes fix.

## What the real app would need to adopt it

- **Fonts, bundled.** Literata and Sofia Sans Semi Condensed are both SIL OFL on Google Fonts.
  The mock links Google Fonts; the executable is offline, so the woff2 files (Literata
  variable roman and italic, Sofia Sans Semi Condensed variable) go into `play/static/fonts/`
  beside Cinzel with their OFL text, and an `@font-face` replaces the link. No other
  third-party asset is used.
- **A tell-to-beat link.** The margin needs each outcome attached to the beat it produced.
  The turn log already records outcomes per turn (`added_turn_log` in the recordings); the
  page needs the beat id alongside, and the rolls' `modifiers` and `dc.explain`, which the
  engine already produces.
- **Render the engine's answer before the prose.** Today the page waits for the turn. The
  margin entries could be sent as soon as the engine resolves, with the prose streaming after:
  the single change that most helps a slow local model.
- **Per-number terms on the sheet.** `full_sheet()` already returns terms for everything
  shown; the sheet view would render them as the breakdown cards.
- **Weapon ranges.** `rules.tables.WEAPONS["dagger"]` has no thrown range, so the Range column
  says "melee, 5 ft" for a dagger. A data gap to fill in the tables, not a UI one.
- **Distance for targets and the board's reach.** The engine already has the grid and reach
  (`rules/grid.py`, `Scene.positions`, the melee-reach refusals); the mock's own Dijkstra
  would be replaced by the server's `reachable` payload, which `scene3d.js` already reads.
- **Withdraw risk per exit.** The mock measures the path to one door. The engine would name,
  per way out, which foes' reach covers it.
- **A theme and size setting**, stored per viewer (the mock uses localStorage).

## Unfinished, honestly

- The 3D view keeps the app's brown materials; only the flat board and the dice are in this
  page's palette.
- The map is a spring layout of the exits: it is legible at 1440 and pans on a phone, but some
  labels touch ("west crossing" and "well"), and positions mean nothing geographic. Walk there
  moves you in one step, where the engine would walk each leg.
- The body's needs do not change as time passes here, not even across a five-day road.
- A five-foot step, a withdraw and attacks of opportunity follow the book in outline only; the
  withdraw measures the path to the door for every way out.
- The spell cast in exploration spends its slot and says so, but targets are not chosen outside
  a fight.
- Iteratives render as "+a/+b" when the sheet's `sequence` is above one, but both fixtures are
  level 1, so that path has not been seen with real data.
- Reduced motion is not specially handled (the brief did not ask); `dice3d.js` handles its own.
- Checked in the browser at 1440x900, 1024x768 and 375x812, night and day, with no console
  errors across every mode and flow described above. Not checked in the packaged Electron app,
  since nothing here is part of it.
