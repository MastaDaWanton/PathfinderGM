# The play table rebuild: inventory

Stage 1 of 3 (the shell) of rebuilding `play/templates/play/table.html` into the owner's
approved design (`docs/mock/table-layout/`, README in full; the shared theme
`play/static/css/theme-v2.css`). Written before the build, from the template at
`table-rebuild-base` (f3f74b0) and all eleven scripts under `play/static/js/table/`,
because of the standing instruction to trace the real path first: every feature,
control, panel, popover, keyboard shortcut and state the table had, and where each one
goes. Nothing may disappear silently.

Stage 2 (2026-09-30) built the rows that stage 1 carried for it: the Sheet, Equipment,
Spells, Trade and Journal tabs in the approved design, every number on them the engine's
(`/api/sheet`, which gained each swing of a full attack, a weapon's range, weight,
finesse and traits, whether a manoeuvre provokes or needs both hands, feint's Bluff,
and `equipment.carried`, the one list Equipment draws). What stage 2 changed and why is
in the rows' own words below (H1 to H22).

`tests/test_table_rebuild.py` reads the tables below. Each row is one item:

- **Stage 1** is one of:
  - `built`: working in the new design now;
  - `carried-2` / `carried-3`: today's panel or behaviour, working, carried as it is into
    the new frame for stage 2 (the Sheet with the full combat block, and Equipment) or
    stage 3 (the Map with the Places fog chart, and the Talk tray's styling) to restyle;
  - `dropped`: removed on purpose, with the owner's ruling cited;
  - `gap`: the design asks for it and the engine or the app has nothing to show, so the
    page says why in words instead.
- **Anchor** is a literal the test looks for. For `built` and `carried` rows it must be
  in the served page (the template plus the scripts it loads); for `dropped` rows it
  must be gone from the template and the scripts' code; for `gap` rows it is the
  sentence or element that says why the thing is absent, and it must be present.

The owner's rulings cited below are in `docs/mock/table-layout/README.md` (README) and
`docs/fix-interfaces.md` §3.4 (FI 3.4).

## The shell

| # | Item | Where it goes | Stage 1 | Anchor |
|---|---|---|---|---|
| S1 | The boiler-room backdrop, with the room's own lift variables | `body.page-backdrop-room` (theme-v2) | built | `page-backdrop-room` |
| S2 | The embers, four layers | `#embers`, fixed, pointer-transparent, as before | built | `id="embers"` |
| S3 | The candle's shade and pool, and the flicker loop | `#cursorshade`, `#cursorlight`, 06's flicker loop | built | `id="cursorlight"` |
| S4 | The candle cursor | `cursor: var(--cursor-candle) 24 0, auto` (theme token) | built | `var(--cursor-candle) 24 0` |
| S5 | Worlds & characters, the way to the landing page | top bar's far left, above the world's name (README, "The doors out of the table") | built | `class="leave" href="/"` |
| S6 | The world's name | top bar, under the link; follows `s.world` | built | `id="world-name"` |
| S7 | The word tabs: Table, Map, Sheet, Equipment, Trade, Journal | top bar, `role="tablist"`, 12-shell.js | built | `id="tab-journal"` |
| S8 | The Spells tab, for casters only (by `spellcasting.kind`) | top bar; absent for a non-caster (README point 3) | built | `id="tab-spells"` |
| S9 | Talk, with its count of new lines | top bar's right, `#talktab` (08's button, moved and restyled) | built | `id="talktab"` |
| S10 | Hide sheet / Show sheet | top bar's right, `#sheettoggle`; remembered under `pgm.table.panels.v1` | built | `id="sheettoggle"` |
| S11 | The three-column stage | `main.stage#stage`: who, the book, the numbers | built | `class="stage"` |
| S12 | The left panel: portrait frame, name, the line under it, In hand and worn | `#side-who`, 14-sides.js | built | `id="loadout"` |
| S13 | The Equipment door | left panel, `#open-equipment` | built | `id="open-equipment"` |
| S14 | The Crafting bench door (`/craft/`) | left panel, under the Equipment door | built | `class="v2-btn door" href="/craft/"` |
| S15 | The right panel: life, ability coins, defence, saves, experience | `#panels` (the numbers), 14-sides.js | built | `id="medals"` |
| S16 | The book: gilt ring, clasps and bosses, the leaf at 50% with a 4px blur | `.book`, `.bookin { --leaf-a: .5 }` | built | `--leaf-a: .5` |
| S17 | One gilt border, no page-stack band | `.book { box-shadow: var(--sh-3) }` (README, "One border, not two") | built | `box-shadow: var(--sh-3)` |
| S18 | The brass status device | `#device`, 13-device.js, on the centre column's left gilt edge 24px down, placed by CSS alone | built | `id="device"` |
| S19 | The device's running state (gears, smoke) on `busy(true)` | 13-device.js listens for `table:busy` | built | `"table:busy"` |
| S20 | The device's answer: gears ease to a stop, about 700ms, lever up, lamp green, tab out, a last burst; never holding back the prose | `Device.ready()` from the response (`table:posted`), after the prose is drawn | built | `HEARTBEAT: 700` |
| S21 | The device's waiting state on `s.awaiting` (gears paused, lamp amber, a trickle) | `Device.wait()` from the render of an awaiting state | built | `Device.wait()` |
| S22 | The device in the head bar on a phone | `#dv-slot`, turned a quarter | built | `id="dv-slot"` |
| S23 | The busy line ("the GM is thinking") | kept as `#busy`, a status for screen readers; the device is its visible form | built | `id="busy"` |
| S24 | The error and hint line | `#err`, in the desk above the pen | built | `id="err"` |
| S25 | The skip link to the story | first focusable element | built | `class="skip"` |

## The story

| # | Item | Where it goes | Stage 1 | Anchor |
|---|---|---|---|---|
| B1 | The transcript, rebuilt each state | `#story` inside the book's leaf | built | `id="story"` |
| B2 | The ink-bleed entrance on fresh beats only | `.beat.fresh` | built | `.beat.fresh` |
| B3 | The drop cap on the GM's passages | `.beat.setup::first-letter` | built | `.beat.setup::first-letter` |
| B4 | Speech and action told apart (quotes, asterisks) | `said()` in 06, `q.said`, `em.did` | built | `q.said` |
| B5 | The out-of-character aside (the engine answering) | `.beat.aside` | built | `.beat.aside` |
| B6 | A chip sent with a player beat, drawn before the words | `.beat .chip` | built | `.beat .chip` |
| B7 | The place head row: where you are, in words, and the clock | `#place-name`, `#where-line`, 15-book.js (the old sheet's biome line moved here) | built | `id="where-line"` |
| B8 | The Here chips: who is in the scene, each opening a line about them | `#here-list`, `#face` | built | `id="here-list"` |
| B9 | The glance on a phone (life and AC, opening the Sheet) | `#glance` in the book head | built | `id="glance"` |

## The desk and the pen

| # | Item | Where it goes | Stage 1 | Anchor |
|---|---|---|---|---|
| P1 | The say box | `#input` in the pen | built | `id="input"` |
| P2 | Say | `#send` | built | `id="send"` |
| P3 | Continue (the scene moves; nothing typed) | `#carryon`, posts `carry_on` | built | `id="carryon"` |
| P4 | Craft action, opening the hub where you stand | `#craftaction` and the `#craftpanel` popover over the story's foot | built | `id="craftpanel"` |
| P5 | The bench door from the Craft action popover ("Open the full bench") | `#craftpanel`, beside Close | built | `Open the full bench` |
| P6 | Spells, for casters only, opening the picker | `#spellbtn` in the pen | built | `id="spellbtn"` |
| P7 | The chip slot: a spell or a place attached to the turn | `#attachments` before `#input` in `#sayform` | built | `id="attachments"` |
| P8 | The chip's remove button | `.chip-x` | built | `chip-x` |
| P9 | Two-press Backspace at the start of the box | 10-spells.js `SPELLS.armed` | built | `SPELLS.armed = true` |
| P10 | Esc takes back an armed chip, or a place chip from the exits row | 10-spells.js | built | `e.key === "Escape" && SPELLS.chips[0].kind === "place"` |
| P11 | The unfinished-words hint (the rest put back in the box) | `showUnfinished`, into `#err` | built | `function showUnfinished(` |
| P12 | A 422 refusal with its fix button (prepare, go) | `showRefusal`, `.errfix` in `#err` | built | `class="quiet errfix"` |
| P13 | The chip's line held open under the exits row (42px), so the row never moves | `.desk` rule while `#exits` is shown | built | `min-height: 42px` |
| P14 | The placeholder that says what to do with the chip | 10-spells.js `drawAttachments` | built | `How do you go to` |
| P15 | 412 stale screen, 409 busy table, 410 death | 02's `post()` | built | `r.status === 412` |
| P16 | The Trade button in the footer | removed: Trade is a tab (README, "Also: the footer's duplicate Trade button is gone") | dropped | `id="tradeaction"` |

## Suggestions and the ways on

| # | Item | Where it goes | Stage 1 | Anchor |
|---|---|---|---|---|
| X1 | The GM's suggestions, a click filling the box | `#suggestions` in the desk | built | `id="suggestions"` |
| X2 | A bare move to an exit dropped from the suggestions | 11-exits.js `dropDuplicateSuggestions` | built | `function dropDuplicateSuggestions(` |
| X3 | The exits row, grouped: next door, outside, roads | `#exits` in the desk | built | `id="exits"` |
| X4 | A shut way stays, with the rules' reason on hover or focus | `.exitbtn.shut`, `#exits-why` | built | `exits-why` |
| X5 | The withdraw mark mid-fight | `.exitbtn.risky .ex-risk` | built | `#exits .exitbtn.risky` |
| X6 | A click attaches the way; Say sends it | 11-exits.js `toggleExit` | built | `function toggleExit(` |
| X7 | The class-ability buttons (a free or toggled one goes straight to the engine) | `#abilities` in the desk | built | `id="abilities"` |

## The fight

| # | Item | Where it goes | Stage 1 | Anchor |
|---|---|---|---|---|
| C1 | The combat bar, shown in a fight | `#combatbar` at the top of the desk | built | `id="combatbar"` |
| C2 | Round and whose turn | `#cb-round`, `#cb-turn` | built | `id="cb-turn"` |
| C3 | The targets | `#cb-targets` | built | `id="cb-targets"` |
| C4 | The planned turn (move, standard, swift, frees), each removable | `#cb-plan`, `[data-unplan]` | built | `id="cb-plan"` |
| C5 | Strike (and which weapon, when a toggle grants two) | `#cb-strike` | built | `id="cb-strike"` |
| C6 | Full attack, slot by slot | `#cb-fullatk`, `#cb-fullok` | built | `id="cb-fullatk"` |
| C7 | Coup de grace on a helpless target | `#cb-coup` | built | `id="cb-coup"` |
| C8 | Ability, Swift, Free menus | `#cb-ability`, `#cb-swift`, `#cb-free`, `#cb-menu` | built | `id="cb-free"` |
| C9 | Cast, through the one spell picker | `#cb-cast` | built | `id="cb-cast"` |
| C10 | Clear, Commit turn, End turn | `#cb-clear`, `#cb-commit`, `#cb-end` | built | `id="cb-commit"` |
| C11 | The hint line | `#cb-hint` | built | `id="cb-hint"` |
| C12 | A lit square on the map queues a move | `[data-sq]` in both boards | built | `data-sq` |
| C13 | Free actions (a free ability leaves the turn open) | `data-free`, `/api/combat/act` with `end_turn: false` | built | `end_turn: false` |
| C14 | Turn order | `#order` in the right panel's "In the scene" | built | `id="order"` |

## Dice, the clock, the conversation

| # | Item | Where it goes | Stage 1 | Anchor |
|---|---|---|---|---|
| D1 | The 3D die asking and landing on the server's face | dice3d.js, over everything | built | `Dice3D.ask` |
| D2 | Entering your own die ("my own roll") | dice3d.js's own toggle | built | `js/dice3d.js` |
| D3 | The popup fallback veil | `#veil`, `#popup` | built | `id="veil"` |
| D4 | The time-skip clock for an hour or more, on this page's own post | `#clockpop` inside `main`, 09-clock.js | built | `id="clockpop"` |
| D5 | The clock's sentence for a screen reader | `#clocksay` | built | `id="clocksay"` |
| T1 | The conversation tray, opened and closed by the player | `#talktray` in the numbers' column (its own column with the sheet hidden; the whole stage on a phone), in the design's gilt-edged leather (stage 3) | built | `id="talktray"` |
| T2 | Whose words: Everyone, the people here, earlier conversations | `#convo-people`, pressed-in buttons and the earlier-conversations list | built | `id="convo-people"` |
| T3 | The log, paged back with "Show earlier lines" | `#convo-log`, a sunk page of its own, dialogue only | built | `id="convo-log"` |
| T4 | Go to the latest line | `#convo-latest`, floating over the log's foot | built | `id="convo-latest"` |
| T5 | Ignore and Take your leave, below the log | `#talk` (02's `renderTalk`): "In conversation with" each person and their Ignore, then Take your leave, under a line held open for the answer (`#talksay`) | built | `id="takeleave"` `id="talksay"` |
| T6 | The regard bars | `.regard`, drawn only when the state carries a regard | built | `class="regard"` |
| T7 | The new-lines badge, never opening the tray by itself | `.edgecount` inside `#talktab` | built | `class="edgecount` |

## The panels

| # | Item | Where it goes | Stage 1 | Anchor |
|---|---|---|---|---|
| N1 | The Sheet panel's summary (name, line, where, life, AC, abilities, carrying, world classes, saves, skills, feats) | split between the left and right panels (14-sides.js); skills and feats are on the Sheet tab in full | built | `function renderSides(` |
| N2 | Non-lethal against its threshold, temporary hit points | right panel, Life | built | `Non-lethal` |
| N3 | The body (needs) | right panel, Life | built | `The body` |
| N4 | Damage reduction and ability pools | right panel, Defence | built | `Damage reduction` |
| N5 | Purse and carrying | left panel (purse), Equipment tab (what is carried) | built | `id="purse"` |
| N6 | World classes | right panel, under Experience | built | `World classes` |
| N7 | Ability damage on a score | the coin's plaque | built | `ability_damage` |
| N8 | "In the scene": who is here and how they stand, the GM view | right panel, a disclosure | built | `id="panel-scene"` |
| N9 | Behind the screen (schemes, when the house rule is on) | `#gmview` in "In the scene" | built | `id="gmview"` |
| N10 | Rolls: the last eight of the player's own | right panel, a disclosure | built | `id="panel-rolls"` |
| N11 | Folding a panel, remembered per viewer | `.paneltoggle`, `pgm.table.panels.v1` | built | `class="paneltoggle"` |
| N12 | The panel bar of toggles and each panel's close | removed: the right panel shows its two disclosures always; nothing to restore them from (the design has no bar) | dropped | `id="panelbar"` |
| N13 | Hide the column | became Hide sheet (S10) | dropped | `id="panelmode"` |
| N14 | The phone drawer | the Sheet tab is the sheet on a phone (README, "Phone (375px) ... the sheet as a mode") | dropped | `body.drawer aside {` |
| N15 | The edge tabs (SHEET, SCENE) | the tabs on top (README, same ruling) | dropped | `id="edgetabs"` `id="sheettab"` |
| N16 | Full character sheet button | replaced by the Sheet tab, the one door to the sheet (README, "One sheet, split round the story") | dropped | `id="opensheet"` |
| N17 | Who is playing (the roster) | left panel, a door under the bench | built | `id="openroster"` |
| N18 | Worlds & characters, in the side panel | moved to the top bar (S5) | built | `Worlds &amp; characters` |
| N19 | The portrait | a frame that says portraits are not kept; the app stores none | gap | `Portraits are not kept yet` |
| N20 | Touch and flat-footed AC beside AC | the right panel's AC plaque, read from /api/sheet after each state (the state carries only `ac`); until it answers, a line says where they are | built | `ac_touch.total` `Touch and flat-footed are on the Sheet` |
| N21 | The Sheet panel in the column | replaced by the stage's two sides (README, "One sheet, split round the story") | dropped | `id="panel-sheet"` `id="panel-sheet-body"` `id="panel-sheet-title"` |
| N22 | The Map panel in the column | replaced by the Map tab (README, "Map is a tab, Talk is a tray") | dropped | `id="panel-map"` `id="panel-map-body"` `id="panel-map-title"` |
| N23 | "Every panel is closed" | nothing on the side closes any more (the design has no bar, N12) | dropped | `id="panelsnone"` |

## The map

| # | Item | Where it goes | Stage 1 | Anchor |
|---|---|---|---|---|
| M1 | The flat board (stone relief, reach wash, tokens by side, crowds, blood pools, spell areas) | the Map tab's board, `#mapwrap` (03's `renderMap`), filling the stone well | built | `id="mapwrap"` |
| M2 | The 3D board, turned in quarter turns | Map tab, `Scene3D.render`, its turn in the head row's `#groundctl` | built | `data-mapturn` |
| M3 | The floors ("the floor", "+10 ft") | Map tab head, `data-maplevel` in `#groundctl` ("Looking at") | built | `data-maplevel` |
| M4 | The place's name and what it is made of | Map tab head (`#board-name`) and foot | built | `The ground` |
| M5 | The map tray, its MAP edge tab and its close | removed: Map is a tab (README, "Map is a tab, Talk is a tray") | dropped | `id="maptray"` `id="maptab"` `id="mapclose"` `id="maptrayinner"` |
| M6 | The map panel's small copy and its open button | removed with the tray: the tab replaces both (README, same section: 18px a square, "legible only as a shape") | dropped | `id="mapopen"` |
| M7 | The Places chart under the fog | the Map tab's Places button, left of Flat and 3D: 16-places-chart.js draws `scene.places_found`, 16-tab-map.js walks by it, a leg a turn through the place chip | built | `places_found` `id="placesbtn"` `Walk there` |

## The sheet, the spells page, the trade window, the journal

| # | Item | Where it goes | Stage 1 | Anchor |
|---|---|---|---|---|
| H1 | The full sheet: Defense, Offense, Skills, Class, Feats & Traits, Companions, Background | the Sheet tab's one column of framed cards, Combat first (initiative, base attack, CMB, CMD with flat-footed, speed; every carried weapon, each swing of a full attack; the full attack in a sentence), then Defence (AC, touch, flat-footed, saves with their terms, life's edges, conditions), Skills, Feats and traits, Class, Background and notes (stage 2, 05 `pageSheet`) | built | `function pageSheet(` `function combatCard(` |
| H2 | The sheet's header: sigil, name, identity line, error line, Close and Esc | the identity line (people, race, class, size, gender, pronouns) moved to the Background card; the error line is `#sheetnote` above every sheet page; Esc goes back to Table (the sigil, the name and Close: H18) | built | `class="idline"` `id="sheeterr"` |
| H3 | The gender prompt | `#sheetnote`, above every sheet page | built | `id = "genderask"` |
| H4 | The tab strip that scrolls on a phone and fades its edges | removed: the design has no strip, each tab is its own page (README, "One sheet, split round the story") | dropped | `function sheetTabEdges(` `id="sheettabs"` |
| H5 | The glossary popover on a named feature | `[data-gloss]`, `#glosscard`, in the details' obsidian and gilt edge | built | `id = "glosscard"` |
| H6 | Taking a level (the hit-point die lands first) | the Sheet tab's Class card, `#levelup`; a refusal (not enough experience) in `#levelerr` | built | `id="levelup"` |
| H7 | Equipment slots (add and remove a line in a slot) | Equipment's Worn and wielded: every slot the rules have, in their order; a slot pressed shows what you carry that fits it and its own lines (write in one, empty one, add or remove a line) | built | `function slotEditor(` `data-eqslot` |
| H8 | The inventory with its actions: drink, throw, coat, wear | Equipment's list (play/views.py `_carried`): the trade window's shelves down the side with counts, A to Z, every name written beside its icon with its quantity; Wield and Wear run the engine's `wear` op, a wondrous item goes into its slot through `/api/slots`, a jar is drunk, thrown or coated through `/api/use` | built | `function pageEquipment(` `data-eqact` |
| H9 | Take off and drop | not offered: the engine has neither op (README, "What the engine does not know") | gap | `There is no drop and no take off` |
| H10 | The Spells page: slots as gem sockets, prepared cards, the grimoire index, prepare, drag to prepare, Details | the Spells tab, on the design's framed cards: sockets lit while unspent and red once spent today, prepared cards with Details, cantrips at will, Cast attaching a chip, the house rule said beside the sockets | built | `function tabSpells(` `sx-house` |
| H11 | The spell picker popover (find, arrows, "Open your spells") | `#spellpop`, from Spells and from Cast | built | `id="spellpop"` |
| H12 | A spell's details popover, Esc first | `#spelldetail`, restyled | built | `id = "spelldetail"` |
| H13 | The trade window: counters, shelves, what you carry, the basket, their wares, one Trade button, Esc | the Trade tab, `#tradepanel` as the design's framed card, with the owner's sentence and a door to Equipment in its head | built | `id="tradepanel"` `Buy and sell here. What you buy goes into your pack` |
| H14 | Trade with nobody keeping a counter | the Trade tab says why, in the words the old button's title used | built | `Nobody here keeps a counter` |
| H15 | A purchase in words opens the counter with the thing in the basket | `openTrade(s.trade.want)` now enters the Trade tab | built | `openTrade(s.trade.want)` |
| H16 | The quest log and the adventure log | the Journal tab: Matters in play (the quest cards), What people said (`/api/conversation`, a person at a time), Where you have been; the adventure log is not kept yet, and the page says so | built | `function tabQuests(` `function journalSaid(` |
| H17 | Companions | the Sheet tab's Background card, a line of its own | built | `data-page="companions"` |
| H18 | The sheet's own header: its sigil, the name in capitals, the identity line under it, Close | removed: the design has no sheet header; the name is the left panel's, the identity line moved to the Background card (H2), and the tabs are the way out (README, "One sheet, split round the story") | dropped | `id="sheetname"` `id="sheetmeta"` `id="closesheet"` `id="sheethead-sigil"` |
| H19 | All ten combat manoeuvres and feint, each with its bonus, whether it provokes, what success does and its limits | the Combat card, a row each; feint's Bluff where the engine has it, "not known" for the rest | built | `<b>feint</b>` `function combatCard(` |
| H20 | Go to Trade from Equipment, and Open equipment from Trade (the owner's ruling: buy at a counter, equip what you carry) | Equipment's head `#eq-trade`; the trade window's head and its empty notice | built | `id="eq-trade"` `data-open-equipment` |
| H21 | The numbers wearing moves (AC, touch, flat-footed, the saves) | Equipment's head, from the engine's sheet, marked where the last act moved them | built | `id="eq-nums"` |
| H22 | Where you have been | the Journal, from `scene.places_found` | built | `Where you have been` |

## Death, the downed, the roster

| # | Item | Where it goes | Stage 1 | Anchor |
|---|---|---|---|---|
| E1 | The downed: conditions and a life bar at or below nothing, and the server resolving the turn | the left panel's red state line and the Life bar; the pen stays (the server answers Say and Continue) | built | `id="pc-state"` |
| E2 | The ended state: the death panel, raising, somebody new | `#deathveil`, `showDeath` | built | `id="deathveil"` |
| E3 | Some weeks later (resurrection) | `#resurrectbtn` | built | `id="resurrectbtn"` |
| E4 | Switching character, and somebody new | `openRoster`, `.pick` | built | `function openRoster(` |

## Words typed at the table, and keys

| # | Item | Where it goes | Stage 1 | Anchor |
|---|---|---|---|---|
| K1 | /gm, a question out of character | the pen; the box's title says how | built | `/gm asks the engine` |
| K2 | /cheat, making something true | the pen; the same title | built | `/cheat makes something true` |
| K3 | m toggles the map | now the Map tab and back | built | `e.key === "m"` |
| K4 | Esc: closes the spell details, then a sheet-backed tab, the counter, the clock, the tray, the picker | each owner's own handler; a sheet-backed tab and the counter go back to Table | built | `e.key === "Escape"` |
| K5 | Arrow keys along the tabs (the APG tabs pattern), Home and End | 12-shell.js | built | `ArrowRight` |
| K6 | The trade basket's + and minus and Delete, the shelves' arrows | 06, unchanged; the Equipment shelves walk the same way | built | `"+": 1, "=": 1` |
| K7 | The spell picker's arrows | 10 | built | `e.key !== "ArrowDown" && e.key !== "ArrowUp"` |

## Behind the page

| # | Item | Where it goes | Stage 1 | Anchor |
|---|---|---|---|---|
| G1 | The second device: resync on a new revision every 3s | 02 | built | `RESYNC_MS = 3000` |
| G2 | The title bar follows the world | 02's `render` | built | `document.title = "Pathfinder GM"` |
| G3 | The keepalive heartbeat for the packaged app | `js/keepalive.js` | built | `js/keepalive.js` |
| G4 | The ember under the cursor on buttons | 06's `--mx`/`--my` listener | built | `--mx` |
| G5 | Render hooks (`onRender`) primed after load | 07 | built | `function onRender(fn)` |
| G6 | The debug teleport on the craft hub | `#cp-debug`, `#cp-biomepick` | built | `id="cp-debug"` |

## What the engine or the app does not have (gaps)

Each is said on the page in words, not hidden, by the owner's ruling "a visible, not
hidden, reason where a thing is absent":

- **Portraits.** Nothing in the app stores one. The left panel's frame says so (N19).
- **Take off and drop.** `_op_wear` swaps, nothing sets armour or a shield back to none,
  and there is no drop op (README, "What the engine does not know"). The Equipment tab
  offers neither; its head says so (H9). A name written in any other slot comes off by
  emptying its line (`/api/slots`), which the old Equipment page could do too.
- **An off hand.** The engine holds one weapon (`Actor.equipped`); Worn and wielded's Off
  hand box says "one weapon at a time".
- **Weight and load.** Only weapons carry a weight in the rules; Equipment writes it on
  their rows and says load is not tracked. A thrown weapon's to-hit is not computed
  (the Combat card says "thrown to-hit not known"), nor is feint's effect.
- **Touch and flat-footed AC, and the armour's name, in the state.** `/api/state` carries
  `pc.ac` only and names no armour or shield; the sides read both from `/api/sheet`
  after each state is drawn (N20), one GET a turn. The state could carry them.
- **A face for the people here.** The actor payload has no appearance, so a Here chip
  opens a line about how the person stands (hurt or not, conditions), from the same data
  the old "In the scene" panel showed (B8). The engine has `names.appearance_for`; the
  state would have to send it.

## The seams left for stages 2 and 3

- **One container per tab.** `main#stage` holds Table (`#book`), Map (`#board`) and Sheet
  (`#sheetmore`); Equipment, Spells, Trade and Journal are `section.modepage#mode-*`.
  12-shell.js switches `body.mode-*` and nothing else about them.
- **One script per tab.** Each tab registers its `enter` and `leave` with
  `Shell.tab(name, {...})`: `16-tab-map.js`, `17-tab-sheet.js`, `18-tab-equipment.js`,
  `19-tab-spells.js`, `20-tab-trade.js`, `21-tab-journal.js`. Stage 2 replaces 17's and
  18's bodies (the Sheet's combat block, the Equipment page); stage 3 replaces 16's
  (the Places chart beside Flat and 3D) and restyles `#talktray`. Stage 3 is built: the
  chart's drawing is its own script, `16-places-chart.js`, loaded before `16-tab-map.js`;
  the head row (`#board-name`, `#placesbtn`, `#groundctl`) is the board's own markup now,
  and 03's `renderMap` fills only `#groundctl` and `#mapwrap`
  (`tests/test_table_places.py`).
- **The sheet panel is one element, moved.** `#sheetpanel` is carried into whichever of
  Sheet, Equipment, Spells and Journal is open (17-tab-sheet.js), and 05's `TABS` draws
  that tab's own page into it: `pageSheet`, `pageEquipment`, `tabSpells`, `pageJournal`.
  Stage 2 kept the move rather than four bodies, because everything that acts on the
  sheet (Prepare and its kept scroll, a spell's details, the drink button, taking a
  level, the gender prompt) finds it by `#sheetbody`.
- **The sides** are drawn by 14-sides.js from the state alone; the Sheet tab's cards read
  `/api/sheet`.
- **The device** knows three signals and nothing else: `table:busy` (06's `busy`),
  `table:posted` (02's `post`) and the render of a state with or without `awaiting`.

