# Table layout mock

A clickable layout study for the play table, to set beside the real one. It is **not part
of the app**: no Django view, no URL, nothing under `play/`, and `docs/` is not bundled
into the executable (see `pathfindergm.spec`). Nothing on it reaches the engine or a model.

## Opening it

From the repository root:

```
python -m http.server 8765 --bind 127.0.0.1
```

then open <http://127.0.0.1:8765/docs/mock/table-layout/>. It has to be served. Opened
as a file, the browser refuses the icon fetches, and the icon tiles come up empty. The
page links the real fonts, textures, icons, clasps and `scene3d.js` under `play/static/`
by relative path, so it must be served from the root, not from this folder.

The dashed strip across the top is the mock's own and not part of the design. **Viewing**
switches between Kesst Vayr (the recording's rogue) and Ysolde Marrach (the fixture
wizard), and says in words what the switch changes. **Wanted in Zhilvarnia** shows the shut
ways and their reasons. **Start again** goes back to the gate with the story and the gear
as they began.

A link can open any state directly, for sending the owner straight to a thing:
`#char=ysolde&mode=spells`, `#mode=map&view=3d&turn=1`, `#mode=equipment&fit=shoulders`,
`#talk=1`, `#hide=1`, `#wanted=1`.

## What changed in this pass (the owner's verdict, point by point)

> "I like the design but Im not sure about how well it functions."

1. **"I dont see a way to actually choose my gear or access the equipment page."**
   Equipment is now a tab, and the gear section on the left ends in a labelled door
   ("Equipment, 50 things carried"). The page is three parts: the shelves down the side,
   the list of everything carried, and **Worn and wielded**: In hand, then every body slot
   the engine has, in its own order and with its own labels (`rules/tables.py` `SLOTS`,
   `SLOT_ORDER_LEFT`, `SLOT_ORDER_RIGHT`, read through `rules.sheet.body_slots`). Each row
   offers what can be done to it: **Wield**, **Wear**, **Take off**, **Use**, **Drop**.
   Choosing a slot shows only what fits it ("Fits the shoulders"). The head of the page
   says, in the interface's own words, "Wield and wear from what you carry. New things are
   bought at a counter", beside a **Go to Trade** button, and the Trade page says the
   other half: "Buy and sell here. What you buy goes into your pack, and you put it on
   from Equipment." That is the owner's ruling (the outfit page is for making a
   character; in play you buy at a shop and equip what you carry), said where it is used.
   The numbers across the head (AC, touch, flat-footed, the three saves) change as
   things go on, and every combination is the engine's (see "What is real").
2. **"without permanently displayed text telling me what they are it will be painfull
   when i have more gear."** Every icon now has its name beside it, always, with its
   quantity ("Arrows x20", "Silk rope 50 ft", "Candle 6 hours", in the engine's own units
   from `goods.unit_for`). The basket is extended to 50 things for Kesst and 27 for
   Ysolde. The shelves are the trade window's own, in its order, with their counts
   (Everything, Weapons, Armour, Consumables, Gear, Magic items, Valuables), and a shelf
   with nothing on it is not offered, as in the trade window. Each shelf is A to Z.
3. **"There is no spell button ... would a spell casting character have one?"** Yes. A
   caster gets the **Spells** tab and the **Spells** button beside Say; a non-caster gets
   neither, with no empty tab and no disabled button. The switch the owner could not find
   in the old Mock menu is now the first thing on the page, and the line beside it says
   "Kesst casts no spells, so there is no Spells tab and no Spells button." Foundry's PF1
   sheet does the same in code: it removes the spells tab for an actor with no
   spellcasting profile (source below).
4. **"the sheet is missing a ton of information from the available combat maneuvers and
   weapon attacks."** Sheet mode now opens on a Combat card: initiative, base attack,
   CMB, CMD with flat-footed, speed, each with what it is made of; every carried weapon
   with each swing of a full attack, damage and type, critical range and multiplier,
   range increment, hands, finesse, the weapon's traits and weight; the full attack in a
   sentence; and all ten combat manoeuvres plus feint, each with its bonus, whether it
   provokes, what success does and its limits. A Defence card follows with AC, touch,
   flat-footed and the three saves (each with its terms) and conditions. Where the engine
   has no number the page says **not known** in italics, never a guess (listed under
   "What the engine does not know").
5. **"I dont see a map or a communication tab."** Both are back: **Map** as a tab, **Talk**
   as a tray. See "Map is a tab, Talk is a tray" below.
6. **"the floating lights and the special cursor are gone and the corner pngs are not
   aligned."** The four-layer embers, the candle's shade and pool with its flicker, and
   the candlestick cursor are copied from the real table (`table.html` `#embers`,
   `#cursorshade`, `#cursorlight`, the `cursor-candle.png` rule, and the flicker loop in
   `06-trade-and-page.js`). The clasps were wrong because the first mock invented its own
   geometry (78px corners hung 14px outside the frame, so the whole piece sat off the
   edge). They are now placed exactly as the real table places them on `.card`: the
   pseudo-element reaches 34px past the panel, 96px corners sit 24px in (a 10px overhang,
   the arm lying along the gilt), and the four 40px bosses sit astride the edge 21px in.
   Screenshot-checked at 1440x900, 1024x768 and 375x812: each corner square covers its
   frame's corner the same way at all three. On a phone the book keeps its frame and
   clasps (the old phone layout hid them) and scrolls inside it instead.
7. **"I want everything to be more 3d."** One lamp for everything, the one `scene3d.js`
   lights the board with (`LIGHT = norm(-0.42, -0.78, 0.47)`: high, left, in front), so
   every lit edge is a top or left edge and every shadow falls down and to the right, half
   as far across as down. The book is a right-hand page: a stack of leaves shows along the
   edges away from the lamp, the page dips into a gutter at the binding, the gilt ring
   has a lit lip and throws a shadow onto the page, and the clasps cast theirs. Buttons
   stand on a lip and sink into it when pressed (a 3px press, the only movement, and it
   answers the pointer). Tabs and view switches sit in a recess and the chosen one is
   pressed in. The ability scores are struck coins with a glinting rim, a beaded inner
   ring and a sunk field with the score raised off it. Leather panels are embossed, their
   headings are tooled grooves, the pen is a trough cut into the desk, spell slots are
   domed gems. No hue, palette or texture is new.

Also: the footer's duplicate **Trade** button is gone (the tab is the one door).

## Map is a tab, Talk is a tray

The open question was "should the map become a tab and Talk stay a tray". Yes to both,
for different reasons.

**Map is a tab**, and it keeps the desk. The board is something to look at and plan on,
and it needs size: the app's own side-panel copy is 18px a square, "legible only as a
shape" by its own comment (`03-offers-and-map.js`), and even its tray was a second copy
at a readable size. So in Map mode the board takes the book's place, taller than the book
is (64% of the height against 45%), with Flat and 3D, turn left and right, and the floors
("the floor", "+10 ft") above it. The desk stays under it, because choosing a square
feeds the combat bar and the pen: a map that hid them would make the player switch back
to act. The two traditions agree on size and disagree on the rest: Foundry makes the
board the whole canvas, and Owlcat and Larian open a large map on a key (BG3 also keeps a
minimap). Neither lets it cover the controls you act with.

**Talk is a tray**, because it goes with the story rather than replacing it: the lines
are read beside the beat that produced them and answered in the pen. The owner ruled it
openable and closeable with Ignore and Take your leave in it (Q42), and Foundry keeps its
chat in the sidebar beside the board for the same reason. Where it opens was measured: the
real app's slide-over covered the beat being read (`08-conversation.js`), so here the tray
takes the numbers' column and covers nothing of the book or the pen. With the sheet
hidden it takes a column of its own beside the book. On a phone it takes the whole stage
(laid over the book alone, the log was left 30px). As in the app, it never opens by
itself; the Talk button counts new lines ("2 new"), the log is dialogue only (Q43/Q44),
and the two ways out sit below the log, never inside its scroll.

## What is real

- **Exits**: `play/exits.py exits()` run on the Pangrella fixture for all 43 places in
  Zhilvarnia at 08:00, plain and wanted.
- **Story, suggestions, people, faces, what was said, the ground**:
  `tests/replay/2026-09-25-town-tags-retag-gemma4-12b.jsonl.gz`. The story is its turns
  asking the smith about his ore, walking to the gate and asking the gate guard what lies
  north, verbatim. The scene is the save made after them, still at the gate, loaded with
  the app's own `Campaign.load` and read through `play/views.py _state` (the function
  behind `/api/state`), so the map's grid, floors, rail, tokens and the 81 reachable
  squares are exactly what the page is sent. The 3D board is `play/static/js/scene3d.js`
  itself, loaded unchanged and handed that payload; the flat board is
  `03-offers-and-map.js renderMap`'s drawing on it. The player's private corpora are not
  used.
- **Every number on the sheet**: `rules.sheet.full_sheet` (behind `/api/sheet`) and
  `Actor.summary()` for `fixtures/pc-kesst.json` and `fixtures/pc-caster.json`. Each swing
  of an attack is `Actor.attack_modifiers` at that iteration. The wizard's slots, DCs and
  prepared spells are `casting.ensure_prepared` on the fixture, and each spell's range,
  duration, save and components are the engine's.
- **What wearing a thing does**: every reachable combination of armour, shield and slot
  items (16 for Kesst, 2 for Ysolde) was put on a scratch copy of the character and asked
  of the engine (`ac`, `touch_ac`, flat-footed, `save_modifiers`). The page looks the
  answer up; it never adds bonuses itself. So "Wearing it: AC 15 to 16, touch 13 to 14"
  on the Ring of Protection +1 is the engine's arithmetic, as is AC 18 with studded
  leather, buckler and ring together.
- **The replies** to Wield, Wear and Take off are the engine's own tells, word for word
  (`_op_wear`: "Kesst Vayr draws the sap.", "puts on the studded leather. Armour class 16
  to 17."; `play/views.py wear_item`: "puts on Cloak of Resistance +1 (shoulders)."). Where
  the engine has nothing to do it with, the reply says so, starting "Mock.".
- **The conversation log**: the recording predates `scene.conversation`, so the tray's
  entries are rebuilt from the `said` lines each GM beat carried, in the log's own shape
  (numbered, speaker, addressee, beat, day). The words are verbatim.
- **Example, not real**: everything in the pack beyond the fixture's weapons and armour
  and the outfit `rules/creation.py OUTFITS` grants at first level. The names are the
  engine's own where it has one (`goods.GEAR`, the weapons table, the magic-item
  catalogue), and each is filed and described by the engine: `goods.kind_of` and the
  server's shelf rules for its shelf, `goods.describe` for its line ("for show, no effect
  in play" is the owner's wording for the engine's "has no rules for it"). The same
  recorded story is shown for both characters.

`data.js` is generated by `build_data.py` (run it from the repository root). Nothing in it
is written by hand.

## What the engine does not know (shown as "not known" or refused)

Each of these was found by asking the engine for the number and not getting one.

- **Weight and load.** Only weapons have a weight (`weight_lb` in
  `content/weapons/weapons.json`). The armour table carries a class (light, medium,
  heavy), not pounds; the gear list (`goods.GEAR`) carries prices and no weights; there is
  no carrying capacity anywhere in `rules/`. The Equipment page says "7 lb that the
  engine knows of, from the four weapons ... Load is not tracked". The real sheet already
  says "Encumbrance is not tracked." Larian had to fix the inventory's weight display
  after launch (BG3 Patch 3), which argues for putting weight in before the list grows.
- **The light crossbow's range and weight.** The curated `light crossbow` entry answers
  `range_ft: None` and `weight_lb: None`, where the shortbow answers 60 ft and 2 lb. Shown
  as "range not known".
- **A thrown weapon's to-hit.** The attack table is computed for the weapon's category
  only, so the dagger's 10 ft range comes with "thrown to-hit not known" (for Ysolde it
  would be Dex, not Str).
- **Whether a manoeuvre provokes, in play.** `MANEUVERS` carries `provokes: True` on all
  ten, and the Sheet shows it, but nothing in `rules/` reads the key: no attack of
  opportunity is rolled for a manoeuvre, and Improved Trip and the rest do not switch it
  off. The page says so under the table.
- **Feint.** There is no feint action: `rules/intents.py` files "feint" as a Bluff check,
  and `rules/classfeatures.py` says the target losing its Dexterity to AC is not
  implemented. The row shows the Bluff bonus and "not known" for the rest.
- **An off hand.** The engine holds one weapon in hand (`Actor.equipped`); the shield is
  its own body slot. The Off hand box says "one weapon at a time".
- **Taking armour or a shield off.** `_op_wear` swaps one for another; nothing sets
  armour back to none. Take off on those rows is answered with a refusal.
- **Dropping anything.** There is no drop op (disarm is the only way a thing leaves a
  hand). Drop is answered with a refusal that points at selling it at a counter.
- **Filing by name.** `goods.kind_of` reads only the eleven curated weapons, so `sling`
  (a weapon to `weapons.has`) is "gear" to it and a `wear` op would refuse to wield it;
  arrows and crossbow bolts file under Gear, not Weapons; and `kind_of("leather armour")`
  is "gear" because the table's key is `leather`, so a `wear` op naming the armour by the
  sheet's own name would be refused. A bought wondrous item ("Cloak of Resistance +1") is
  also "gear" to `kind_of`; the mock files it under Magic items by the catalogue.
- **Regard in conversation.** The recording has no talk state (it predates it), so the
  tray shows who you are talking with and the two buttons, without the regard bar.

## The design decisions (standing)

- **Redesign, preserve.** The app's `:root` tokens copied verbatim, its textures
  (`grimoire-leather`, `card-leather`, `leather-tile`), its gilt, clasps and bosses,
  Cinzel and the Palatino stack, its radius scale (2px controls, 3px surfaces, 12px
  suggestion seals, round medallions), and its engraved-bronze letter shadows. No new
  accent colour. One lighter step of `--dim` inside the leather sides, because the app's
  own value measured 3.0:1 there.
- **The story is the centrepiece.** A gilt-framed book in the middle, a drop cap on each
  GM passage, a 58ch measure at 18px (67 characters a line on the recorded beat). The book
  keeps at least 45% of the height; past that the desk's choices scroll and the pen stays.
- **One sheet, split round the story.** Who the character is on the left (portrait,
  name, what is in hand and worn, the door to Equipment), their numbers on the right. In
  Sheet mode the right side drops Defence and Saves, because the Defence card in the
  middle has them with their terms.
- **Moves come from the exits, and everything else is a chip**, each choice once.
- **Motion.** The embers and the candle's pool are ambient and pointer-transparent. A
  button pressed sinks 3px into its lip. Nothing lifts or slides on hover, and every line
  a reply lands in is held open beforehand, so a reply never pushes a button away (see
  "Tried and dropped").
- **Phone (375px).** The tabs keep their words and the row scrolls sideways, keeping the
  chosen tab in view. The book's inside scrolls with its head. The tables of attacks and
  manoeuvres fold into one labelled card a row. Equipment puts what is worn first, then
  the shelves (a sideways row) and the list. Map keeps the board and the pen and drops the
  choices, which are in Table.

## Tried and dropped in this pass

- **"In use first" sorting.** Pressing Wear moved the row to the top of the list, out
  from under the pointer: the one kind of motion the owner has ruled out. Now A to Z, and
  what is in use is marked where it stands.
- **Reply lines that appear.** The Equipment reply, the board's answer and the tray's
  answer each pushed the controls below them when they arrived. Each now has its line
  held open.
- **The tray over the book with the sheet hidden.** It hid "the merchant" and the right of
  the page and left the log four lines. It takes its own column instead.
- **The tray over the book alone on a phone.** 30px of log. It takes the stage.
- **The figure below the list at 1024px.** Fifty rows from the Wear buttons that fill it.
  It stays beside the list down to 960px and goes above it below that.
- **Three equal columns in the top bar at 1024px.** Seven tabs, Talk and the sheet toggle
  overran; the world's name gives way instead.
- **Tilting panels towards the cursor.** Not tried here because the real app already did
  and removed it: "The tilt that was here read as seasickness once the corner clasps gave
  the panels real weight; hardware does not flex" (`table.html`). Depth comes from light
  and shadow, not from movement.

## The research used

Prior art was gathered for this pass and checked by a second pass; claims it could not
confirm are marked.

- **Foundry VTT, PF1 system** (read from source, the strongest evidence here). Inventory
  is a labelled list in sections (weapons, armour and shields, equipment, consumables,
  gear, ammo, misc, trade goods, containers; `sheetSections.inventory` in
  [config.mjs](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/master/module/config.mjs)),
  each row with quantity, value, weight and separate carried and equipped toggles, light,
  medium and heavy load meters, and empty sections removed
  ([actor-inventory-contents.hbs](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/master/public/templates/actors/parts/actor-inventory-contents.hbs)).
  Adopted: labelled rows, shelves, empty shelves hidden, weight shown where known.
  The spells tab is removed for an actor with no spellcasting profile
  ([base-character-sheet.mjs](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/master/module/applications/actor/abstract/base-character-sheet.mjs)).
  Adopted: no Spells tab for Kesst. The combat tab shows BAB with iteratives, one CMB box
  and a row per attack, and does **not** list the manoeuvres one by one
  ([character-combat.hbs](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/master/public/templates/actors/character/character-combat.hbs)).
  Here the owner asked for every manoeuvre, so the mock lists all ten plus feint: a
  deliberate divergence. Foundry shows the full-attack line only as a tooltip; the mock
  writes it out.
- **Baldur's Gate 3 patch notes** (Larian's own): Patch 2 made Equip the default click
  and added rarity filters
  ([notes](https://forums.larian.com/ubbthreads.php?ubb=showflat&Number=890331)); Patch 3
  fixed the inventory's maximum weight
  ([notes](https://forums.larian.com/ubbthreads.php?ubb=showflat&Number=901393)); Patch 7
  added a list view to the spellbook and speaker portraits to dialogue history
  ([notes](https://forums.larian.com/ubbthreads.php?ubb=showflat&Number=948592)). Read as:
  icon grids without names were walked back, weight was a late fix, dialogue history is
  its own record. A community thread calls the inventory unwieldy
  ([thread](https://forums.larian.com/ubbthreads.php?ubb=showflat&Number=894823)); its
  claim that there is no search conflicts with guides and is not relied on.
- **Solasta** players complain of per-character inventories with no sorting tabs and of
  managing weight per character
  ([Steam thread](https://steamcommunity.com/app/1096530/discussions/0/3389534247566508297/)).
  Community evidence only.
- **Pathfinder: Wrath of the Righteous**: mods add inventory search, per-slot filters and
  subtype sorting ([mod 137](https://www.nexusmods.com/pathfinderwrathoftherighteous/mods/137),
  [mod 1114](https://www.nexusmods.com/pathfinderwrathoftherighteous/mods/1114)), which
  suggests the base game lacked them at some version. Not confirmed which. The map opens
  on M ([controls](https://pathfinderwrathoftherighteous.wiki.fextralife.com/Controls));
  whether it is full-screen was not confirmed.
- **Pathfinder: Kingmaker**: a pre-release Owlcat update planned the log as tabs
  (combat, dialogue, events; Kickstarter update 37, seen only as a search snippet, the page
  refused the request). Its spellbook layout (known spells in a central book, slots below)
  comes from a guide ([gamerguides](https://www.gamerguides.com/pathfinder-kingmaker/walkthrough)),
  not from Owlcat.
- **Disco Elysium** puts its dialogue in one column at the lower right that "flows
  upward", where Robert Kurvitz says players look
  ([Kotaku](https://kotaku.com/disco-elysiums-dialogue-system-is-as-addictive-as-any-s-1841046831)).
  Nothing found on what they tried first.
- **Foundry core** keeps chat and the combat tracker as tabs of one sidebar and had to add
  pop-outs so both can be seen at once ([combat](https://foundryvtt.com/article/combat/),
  [chat](https://foundryvtt.com/article/chat/)). Read as: do not make the player choose
  between the conversation and the fight, which is why Talk is a tray beside the book and
  not a tab that replaces it.
- **Could not confirm**: a BG3 inventory list view (only the spellbook got one), a Pillars
  of Eternity II inventory rework, WotR's offense page layout or whether it hides the
  spellbook for non-casters, Pathbuilder's attack cards, Solasta's preparation screen.
- **The app's own code**, which outranks all of the above for materials:
  `play/templates/play/table.html` (embers, candle, cursor, clasps, bosses, the abandoned
  tilt), `play/static/js/table/06-trade-and-page.js` (flicker, shelves, item icons),
  `08-conversation.js` (the tray, Ignore and Take your leave, never opening by itself),
  `03-offers-and-map.js` and `scene3d.js` (the boards and the one lamp), `05-sheet.js` (the
  slots, the Offense tab, the spell icons).

## How it was checked

Every tab for both characters was screenshotted at 1440x900 and 1024x768 with headless
Chrome through the `#char=...&mode=...` links, and at 375x812 in the preview pane's phone
emulation (headless Chrome will not make a window narrower than 500px, so its phone shots
are not evidence). At 375px the page measured `scrollWidth` 375 in all seven modes for both
characters and with the tray open; before the last two fixes it measured 427 (the tab row
sizing itself to its seven tabs) and 395 (the clasps' box). The Equipment actions, the
tray, the boards and the spell pages were driven in the page, with no console errors and
every file answering 200.

## Open questions for the owner

- **Encumbrance.** Should the engine carry weights for gear and armour and a carrying
  capacity, so the Equipment page can show a load bar the way Foundry does? Today it can
  only show the weapons' pounds.
- **Take off and Drop.** Both are offered on every row and answered with a refusal,
  because the engine has neither for armour, shields or dropping. Keep the buttons as a
  promise, or hide them until the engine can?
- **Two weapons.** The engine holds one weapon. Is an off hand wanted (two-weapon
  fighting, a dagger with the rapier), or is one weapon and a shield slot the model?
- **Manoeuvres and provocation.** The sheet says every manoeuvre provokes because the
  engine's table does; no attack of opportunity is actually rolled. Worth wiring, with
  the Improved feats switching it off?
- **The desk in Map mode.** On a phone the choices are dropped so the board has room; on
  a desktop they stay and scroll. Is that the right split?
