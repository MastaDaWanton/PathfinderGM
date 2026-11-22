# Tutorials, phase 1: for the owner's review

Branch `feat/tutorials-p1`. The plan is `docs/tutorials-plan.md`; this is phase 1 of it:
the framework and the first four cards (the Table, Places, Region travel, the Herbalism
bench). Phases 2 to 6 wait on this review (decision D8).

## Screenshots

In `C:\Users\natha\pgm-work\tutorials-p1-shots\`:

| File | What it shows |
|---|---|
| `01-home-welcome-line.png` | The one first-launch line on the home page (D1), with the Manual (D9) |
| `02-settings-tutorials-home.jpg` | Settings, Tutorials on the home page: every card, seen or not, Show me, Show all tips again, Turn tips off |
| `03-settings-tutorials-in-table.jpg` | The same list inside the table's Settings panel |
| `04-table-card-first-visit.png` | The Table's card on arrival, step 1, the pen ringed |
| `05-table-card-step6-corner.jpg` | The Table's last step: every corner button named |
| `06-places-card-first-visit.jpg` | The Places card the first time Places is pressed |
| `07-region-card-replayed-by-question-mark.jpg` | The Region card replayed with the map's **?** (no "Not now" on a card you asked for) |
| `08-herbalism-card-from-show-me.jpg` | Settings' Show me for the herb bench: the bench opens and the card shows, methods ringed |
| `09-herbalism-card-buttons-step.jpg` | The bench's "Buttons along the foot" step |
| `10-table-card-phone-375.png` | The Table's card at 375x812, docked under the tab strip |
| `11-update-shows-only-the-changed-step.jpg` | After an update (Places raised to v2, one step changed): only that step, headed "New since you last looked" |
| `12-packaged-table-card-1024x700.jpg` | The packaged build's first Table card at 1024x700 |

## The full text of every card

Numbers below are filled from the engine; in the content they are placeholders
(`{hex_hours_open}`, `{march_dc_first}`, ...).

### The table (`table`, 6 steps)

1. **What do you do?** Write what your character does, the way you would tell a GM, and press Say. The rules engine rolls and decides; the GM tells it. A turn takes a while on your own machine. A line starting /gm asks the engine out of character.
2. **Continue** Continue means you keep doing what you were doing, and the world moves a beat. Use it when you have nothing new to say and want the scene to go on.
3. **The ways on** These are the ways on from here. Press one to attach it to your turn, then Say to go; the time on it is real time passing. The suggestions below are offers, never orders: you can always write something else.
4. **Beside the pen**
   - **Craft action** Forage, prospect, skin, gather or buy material, told as part of the story.
   - **Spells** Casters only: choose a spell to cast with this turn.
   - **?** Shows these tips again.
5. **The tabs**
   - **Map** Where everyone stands, and the places you have found.
   - **Sheet** Your character: combat, skills, feats and the next level.
   - **Equipment** Everything you carry, worn and held.
   - **Spells** Casters only: what you know and have prepared.
   - **Trade** Buying and selling, when you stand at a counter.
   - **Journal** Quests, what people said, where you have been, and your notes.
6. **The corner**
   - **Talk** What has been said to you, person by person.
   - **Music** The soundtrack on or off; its level is in Settings.
   - **Settings** Models, sound, tips and reporting a problem, without leaving the game.
   - **Hide sheet** Folds the side panels away and gives the story the width.
   - **Worlds & characters** Back to the shelf of worlds and characters.

### Places (`map.places`, 4 steps)

1. **Places** Places shows the town as you know it, laid out on a tabletop. Press Places again to go back to the ground you are standing on.
2. **The fog** Where you have stood is painted, places you have only seen are grey, and the rest is cloud. It fills in as you find things and never shows what you have not. The layout is a sketch: distance on it is not distance walked.
3. **Going somewhere** Press a place for its card: how you know it and the way there. Walk there attaches the whole walk to your turn, and Say sets off. Something on the way, a meeting or the watch at a gate, can stop you.
4. **The maps above** The names along the top are the maps above this one: the region, the continent, the world. Press one, or zoom out past a map, to open the one above it.
   - **?** Shows the tips for the map you are looking at.

### Region travel (`map.region`, 5 steps)

1. **One hex a move** Each hex is 12 miles across. Press any hex you have seen and you walk there, a hex at a time. For most walkers open plain takes 5 hours a hex and rougher ground 8; slower walkers take longer.
2. **Each stop** Where you stop you look round, and every hex the look covers clears on the map. A meeting, a fight, something new in sight or the end of the day stops you on the way, and the story says which.
3. **Past a day's travel** After 8 hours on the way since you last rested, the day's travel is done. Going on is a forced march: a Constitution check each hour, DC 10 and 2 more every hour, with 1d6 non-lethal and fatigue on a failure.
4. **Water** By a coast the buttons say how you cross: sail in your own ship, row a hired boat, or swim. A swim says what it will cost you before you press it.
5. **Buttons under Travel** Each button names a way you can step, with the ground and the hours it takes.
   - **Walk to** A site you spotted further off, walked a hex at a time.
   - **Go into** Enter the tower, ruin, mine or cave in the hex you stand on.
   - **?** Shows these tips again.

### The herbalism bench (`bench.herbalism`, 5 steps)

1. **Methods** The methods of the craft run along the top, and the number keys pick them too. A locked method opens at a higher herbalism level, and says which.
2. **Your satchel** On the left is what you carry that this method can work. Drag an ingredient onto the tool, click it, or press Enter on it. Anything that cannot go on the tool says why.
3. **Roll Craft** Roll Craft throws your Craft check. On a success a short game plays, and how well you play sets the quality, up to the best your herbalism level allows. The column on the right shows that ladder.
4. **Long work** A step of 1 hour or longer goes In progress. You carry it with you, and it finishes in its own time while you play.
5. **Buttons along the foot**
   - **Recipes** Steps you saved, to run again.
   - **Herbarium** What you know of each herb, in the Journal.
   - **Manuals** Read a herbal manual you carry; reading takes hours.
   - **perks to pick** Past the top level, each level gives perks to choose.
   - **Steady mode** Slower games, and every hold becomes a press.
   - **?** Shows these tips again.
   - **Close** Back to the table. Esc does the same.

## How it behaves (verified live)

- **First visit.** Each card showed once, by itself, at its section: the Table once the story
  was on the page, Places on the first press of Places, Region on the first Region view,
  the herb bench once its methods and satchel were drawn.
- **Never over a decision.** With words in the pen the Table's card waited; emptying the pen
  showed it. Cards also wait under the dice mat, a death, Settings, a bench game or a
  bench's own dialog.
- **Not blocking.** The hit test with a card open found nothing covered and no card over End
  turn, Commit, the pen or Say, at 1400x900, 1024x700, 800x600 and 375x812. The largest
  card was 24.9% of the window (the cap is 25%). Auto cards never take focus.
- **Got it / Not now / Esc.** Got it is kept on the server; Not now and Esc put a card away
  until you open that section again; one Esc closes the card and not the bench under it.
- **?** replays a card from step 1 and moves focus to it; it works with tips off too.
- **Turn tips off** (in every card and in Settings) stops every automatic card, including
  the minigames' first cards; Settings turns tips back on.
- **A second origin** (127.0.0.1 beside localhost, separate browser storage, as a LAN phone
  is) did not show the Table card dismissed on the first.
- **Minigames.** The old per-browser marks (`pgm.games.seen.*`) moved into the store on the
  first table load and were removed from the browser.

## Calls I made by default (say if any should change)

1. **Six steps a card, not four.** D3 widened the content to every button; the plan's 45
   words a step stands, and the buttons are listed one line each (at most 7 rows of at most
   14 words) in a "buttons" step. The Table needs six. The test holds both caps.
2. **Placement is measured, not CSS anchor positioning.** One code path for Electron and
   for a LAN browser without anchor CSS. The card goes where it covers the fewest other
   controls, so on the Table it often sits top-left over the portrait rather than right
   beside the pen; the gold ring marks what it is talking about.
3. **"Not now" lasts until you open that section again**; for the Table, that is the next
   page load.
4. **Turn tips off silences the minigames' first cards too**, since tips off "stops every
   automatic card". Show all tips again brings them back.
5. **The pause words (D7).** The games have no pause key; the **?** on the game's strip
   pauses it, so the card now says "Space or click to begin. The ? pauses the game."
6. **A label check looks three lines either side of the control's `data-tut`**, so a label a
   template literal builds on the line above still counts. Tight enough to catch a rename
   (tested), loose enough for the map's sail/row buttons.
7. **The inline first-time line** (the dice popup, That's wrong, the forced-march prompt) is
   phase 3 and 4's: no phase-1 section needs one, so it is not built yet.
8. **Show all tips again does not turn tips back on** by itself; the two buttons stay
   separate.

## To decide before phases 2-6

- Six steps for the busiest sections (the Table, and likely the Sheet and the fight bar), or
  hold them to four and move the button lists to the manual?
- Is the placement good enough, or should a card always sit right beside its control even
  when that covers a few other buttons for a moment?
- The Travel panel's own paragraph still hardcodes "five hours", "eight", "DC 10" and "1d6"
  in `16-tab-map.js` (found in the plan, §2); phase 6 is to move it onto the engine's
  numbers, the way the cards already are.
- Found while testing, not part of this work: the owner's save still shows a raw ref in the
  narration ("There is no fffcb34e546e~forest:@hex-m52-35 here to go to"), already flagged
  in the plan.

## Proof

- **Suite:** 15,709 passed, 54 skipped, exit 0 (`-n 12`, on the final commit). The first run had 6 failures, all
  pins on markup this work changed on purpose (the herb footer's byte-for-byte string, the
  hit test's return line, two node stubs without `window`); each was updated or made
  stub-safe and the whole suite run again.
- **Packaged build** (`npm run dist`, PyInstaller from the repo root):
  `prove_build.py` ALL CLEAN; `prove_shell.py` ALL CLEAN; `prove_shell.py --packaged` ALL
  CLEAN.
- **Hit test, packaged backend from `win-unpacked`** over a copy of the owner's save with a
  stale `tutorials.json` of `schema: 0` (and `off: true`) seeded: the file read as empty
  (tips on, nothing seen) and was rewritten as `schema: 1` on the first Got it. With cards
  closed and with every step of the Table, Places and Region cards open, at 1024x700 and
  800x600: `covered` empty, `unreachable` empty, `card.problems` empty, no anchor missing.
  Largest card 24.9% of the window. The herb card covered no bench control at any step.
- **LAN, a real second origin:** the door opened from the packaged backend; the table at
  `http://192.168.1.14:<port>/play/` did not show the herb card dismissed on the desktop,
  and Got it on the LAN page was seen by the desktop's API. That run found one bug (the
  Table's card stayed up over the herb bench), fixed in `3c3a35b9`; the rebuild re-checked
  that case.
- **Not verified:** a real phone (the second origin was this machine's LAN address in the
  same browser pane); the no-`popover` fallback on an old Safari (no such browser here).

