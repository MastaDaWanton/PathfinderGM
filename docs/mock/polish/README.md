# Board polish mocks

The owner's rule: no visual polish lands in the game until a mock shows the current look
beside the proposed one, on real data. This folder is the harness for that. The left
panel is always the game's own board code, copied unchanged; the right is a variant.

## Opening it

Serve the repository root with any static server and open `docs/mock/polish/`, for
example `http://localhost:8993/docs/mock/polish/`. It needs a server (it fetches
`variants/*.json`); opening the file directly will not work.

Controls, shared by both panels:

- **Scene**: A (the fight), B at dawn, noon and night (the same fight at three hours), C
  and C at night (the same cast in Zhilvarnia's great square, 24 x 24: the city's own
  `size_ft` of 120 by 120, laid by `floorplan.for_place`, set up exactly as A; for zoom).
- **Flat / 3D** and **Turn left / right** (3D only). The board's own buttons inside
  either panel work too, and the other panel follows.
- **Show the burning hands area**: lays `extras.spell_area` into `scene.grid.areas`,
  the shape the game sends after a real cast, so both boards draw it as they would.
- **Proposed**: the variant on the right (from `variants/index.json`).
- **Size**: both iframes are given the same pixel size. 375 wide triggers the game's own
  phone rules (`@media (max-width: 760px)`), because the iframe is the viewport.
- **Side by side / Flick**: Flick shows one panel at a time in the same place; "Show the
  other" or the space bar swaps them.

The address bar keeps the settings (`?v=&scene=&view=&turn=&size=&layout=&spell=`), so a
comparison can be linked.

## How data.js is built, and what is real

`build_data.py` writes `data.js` (`window.POLISH_DATA`). Run it from the repository root
with a throwaway data directory:

    PATHFINDER_GM_DATA=<a temp folder> python docs/mock/polish/build_data.py

Nothing in it is written by hand. The method is `docs/mock/table-layout`'s:

- **World and place**: `fixtures/pangrella-campaign.json`, Zhilvarnia, `the-gate`
  (floorplan `BY_SPOT`: "the gatehouse either side, and the wall-walk over it"). A
  13 x 10 board, a wall-walk 10 ft up on columns 10-11, a rail along column 9.
- **People**: `fixtures/pc-kesst.json` (Kesst Vayr, rogue), a `watchman` on her side, and
  four bestiary `goblin`s, set up through `begin_encounter` (origin `author:test`, as the
  engine's tests do).
- **The state**: the scene is saved with `Campaign.save`, loaded with `Campaign.load` and
  read through `play/views.py _state`, the function behind `/api/state`.
  `scenes.<name>.state` keeps `scene`, `pc`, `attacks` and `awaiting` from it unchanged;
  the board reads only `scene`.
- **Placed rather than played** (and why):
  - Positions are written into `scene.positions` after `begin_encounter`, the way
    `tests/test_sneak_attack.py` does. There is no op that stands a creature on a chosen
    square.
  - It is the PC's turn because of initiative: the dice seed is the first from 0 on which
    Kesst wins it (seed 5). Creature turns are model calls in the app, so a later round
    cannot be reached without a model: this is round 1. The goblins have not acted yet,
    so they are flat-footed, which only the hidden AC would show.
  - One goblin is hidden with the Hidden effect the engine's Stealth success applies
    (as `tests/test_hidden_state.py` does), and Kesst has a hunch about it from
    `awareness.hunch`.
  - The watchman is there because flanking needs an ally opposite the PC
    (`position.flanking_with`) and Kesst has no companion in the fixture.
- **The tactics on the board**: Kesst at (4,5) flanks the first goblin (5,5) with the
  watchman (6,5); the second goblin (4,6) is beside her, so walking off provokes from both
  and a 5-ft step does not; the third goblin is on the wall-walk at (10,5), 10 ft up, with
  hard cover from her; the fourth is hidden at (7,8) behind the stone at (6,8).

### The extras (`scenes.<name>.extras`), each with its source

Only what the player could legitimately know. Each field also carries a `source` string.

| Field | What | Engine function |
|---|---|---|
| `threatened.by_foe` | squares each locatable foe threatens | `reactions.threatened_by` (wraps `grid.threatened_squares` with reach) |
| `provokes.squares` | `"x,y": [refs]` for each reachable square whose move would provoke | `reactions.provoked_by_move(pc, here, square)`, the call the move op makes; 5-ft steps never provoke |
| `sight.squares` | `[x, y, 1/0]` line of sight from the PC to every square | `Grid.line_of_sight` |
| `sight.cover` | `none`, `cover`, `soft` or `total` per locatable foe | `position.cover_of` |
| `attack_preview.by_foe` | per foe, per weapon: `bonus`, itemised `terms`, `situational` terms (flanking, higher ground, into melee, compulsion), `in_reach` | `Actor.attack_modifiers(defender, range_ft)` + `compulsion.penalty_against` + `position.attack_mods`, as the swing loop in `engine.py` builds it |
| `spell_area` | burning hands (CL 1) aimed at the goblin beside Kesst: shape, origin, direction, `cells`, `caught`, and `as_grid_area` | `areas.lay`, `areas.caught` |
| `awareness` | `pinpoint` refs, and one `{within_ft: 30}` per hunch | `awareness.locates`, `awareness.has_hunch` |
| `roles` | which goblin is which in the set-up above | the build script's own labels |

`scenes.<name>.light`: `ambient` (`Scene.ambient_light`), `at_square` (`Scene.light_at`
per square, as Kesst sees it), `phase` (`sky.phase_at`) and `day_part`
(`residency.day_part`). Dawn is 05:30 (sky's dawn window, before `DAWN_MINUTE`, so dim),
noon 12:00 (bright), night 21:00 (dim).

### What is left out, and why

- **The target's AC, its itemised AC and a needed d20.** The target's AC is hidden in the
  game, so the preview shows only the player's own bonus (the attack path rolls without a
  dc, and the dice card prints "beat" only when a dc is shown).
- **The hidden goblin** in any extra: no ref, no square, no threatened squares, and it is
  dropped from `provokes` and `spell_area.caught`. A hunch is shown as a count with the
  30 ft notice range, not who or where.
- **Per-square light that varies.** Nothing on the board carries a light, so
  `at_square` is the ambient level everywhere. Giving the watchman a lit torch through
  the engine would make it vary; not done.
- **Scene B differs from A only in the hour.** The board code does not draw light, so the
  Current panel looks the same at all three; the hour is there for variants to use.

### Found while building it (game behaviour, not the mock's)

- `_state` drops the hidden goblin from `scene.actors` but lists it in
  `scene.initiative` with its name and score, and `02-state.js` prints that list in the
  turn order. The player can read "fourth goblin" there. `build_data.py` asserts this so
  the README is updated if it changes.
- `grid.reachable` routes round the hidden goblin's square, so the lit squares have a
  hole where it stands ((7,8) is not reachable).
- The goblin on the wall-walk at (10,5,2) threatens (9,5) and (9,6), squares at the
  wall's foot 10 ft below it: `threatened_by` answers flat squares with no level. Not
  followed further; it may be ruled elsewhere when a swing is actually made.

## The variant contract

A variant is a folder `variants/<name>/` and one line in `variants/index.json`.

- **Files.** Its own copies of `board.html` (the board's markup), `board.css`,
  `scene3d.js` and `map.js`, plus anything new. Copy them from `variants/current/` and
  change the copies; never edit `current`.
- **`variant.json`**:

      {
        "name": "<folder name>",
        "title": "<shown above the right panel>",
        "skills": ["<skills used>"],
        "summary": "<one paragraph>",
        "changes": [{"change": "<what>", "reason": "<why>"}],
        "files": {"markup": "board.html", "styles": ["board.css"],
                  "scripts": ["scene3d.js", "map.js"]}
      }

  `files` lists what the panel loads, in order; scripts run as classic scripts sharing
  one global scope, as the game's do.
- **What the panel provides** (`panel.html`, `shim.js`, `panel.js`): the real
  `theme-v2.css` (textures and fonts from `play/static/`), `body.page-backdrop-room
  mode-map`, the globals `STATE`, `$` and `esc` exactly as the game defines them, and
  `window.POLISH_SCENE` (the whole scene from `data.js`, extras and light included).
- **What a variant must provide**: global `renderMap(state)` and the `let` globals
  `MAP_3D`, `MAP_TURN`, `MAP_LEVEL`. The panel sets those three and calls
  `renderMap(STATE)` on load and whenever a control changes. The board's own controls
  keep the attributes `data-mapview`, `data-mapturn`, `data-maplevel`, so the harness can
  keep both panels in step.
- **Isolation**: each panel is its own iframe (`panel.html?v=<name>&scene=...`), so two
  variants' globals and stylesheets cannot collide.
- **Data**: read `STATE.scene` as the game would; previews read
  `window.POLISH_SCENE.extras` and `.light`. Draw nothing the player could not know.

## Known differences between Current and the game

- **The stage.** The game sizes the board as a cell of `.stage` (Map mode: at least 64%
  of the stage's height, at most 880px wide, beside the sheet or not). The harness puts
  the board alone in a fixed-size frame with the stage's padding (`body.polish-stage` in
  `panel.html`), so its height is the size you pick, not what a given window would give.
  The real board's height at a given window was not measured.
- **What surrounds it.** No top bar, sheet, desk, device, embers or candle light; the
  backdrop is the same room image but not with those layered over it.
- **Places** does nothing: the town chart (`16-places-chart.js`) is a different map and
  is not copied. Its button is drawn because it is part of the board's head row.
- **Clicks on lit squares** do nothing: in the game they queue a move in the combat bar
  (04), which is not here.
- **The level picker** works inside a panel, and the other panel follows; the harness bar
  has no picker of its own.
- **Not compared against the running app.** The Current panel was checked by reading
  `table.html` and the JS it copies, not by running the game with this save side by side.

## How it was checked

Opened at `http://localhost:8993/docs/mock/polish/` in the desktop app's browser pane:
scene A flat and 3D, turned with a panel's own button (both panels followed), the spell
area on, B-night at 375 x 520 in Flick. No console messages; every request answered 200
or 304, including every texture and both Cinzel faces from `play/static/`.
