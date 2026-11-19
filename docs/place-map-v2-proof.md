# Place map v2: the packaged proof (phase 6)

Phase 6 of `docs/place-map-v2-build-plan.md` (branch `mock/place-map-v2`): the five maps proved
against the PACKAGED app, 2026-11-19, built from `feat/place-map-knowledge` (phases 1–5 stacked).
Not a release: `electron/package.json` still read 0.4.3, and nothing was tagged.

## How it was run

- `npm ci`, then `npm run dist` in `electron/` (PyInstaller backend 119 MB, then
  `release/win-unpacked` and the installer).
- `tools/prove_build.py`: ALL CLEAN. `tools/prove_shell.py --packaged`: ALL CLEAN.
- `release/win-unpacked/Pathfinder GM.exe` over a throwaway data directory
  (`PATHFINDER_GM_DATA`, a copy of frag's save standing in the sewers under Thornstead,
  Aurvantis), with `--remote-debugging-port`, driven over the DevTools protocol by a Node
  script: every map opened in turn, `tools/table_hit_test.js` run in the page, board pieces
  pressed with real mouse events (`Input.dispatchMouseEvent`), screenshots taken.
- Ollama had `gemma-4-12B` loaded throughout: 8.3 GB of the RTX 3080's 12 GB, 10.7 GB in
  use before the app opened.

## What was found and fixed

**The keyboard list read as covered.** The board's list of places for the keyboard
(`.boardkeys`) was hidden with `clip-path: inset(50%)` alone. Its buttons kept their full
size under the canvas, and the release hit test reported every one covered: 5 to 9 on each
map. A mouse can never reach them by design, so no click was lost, but the release rule is
that `covered` is empty. The list is now the standard visually-hidden box (1px, overflow
hidden) until a button in it takes the focus, then opens whole (159 × 395 px measured).
Rebuilt and re-proved: `covered` and `unreachable` empty on all five maps.
`tests/test_places_world.py::test_the_keyboard_list_is_hidden_the_way_the_hit_test_reads`.

## Measured

| | Site | Town | Region | Continent | World |
|---|---|---|---|---|---|
| hit test: covered / unreachable | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| frame cost, median (ms) | 8.8 | 9.4 | 9.3 | 7.7 | 7.9 |
| frame cost, 95th percentile (ms) | 12.7 | 16.8 | 15.6 | 12.6 | 14.3 |
| triangles | 1,860 | 19,440 | 99,444 | 30,180 | 10,310 |

- **Frame cost, not frame rate.** Counted with `requestAnimationFrame`, the board read a flat
  30 fps on every map, 1,860 triangles or 99,444 alike, while the chart in the same window
  read 65–110 fps, and with the window behind others the count stopped altogether. Chromium
  throttles a window the desktop hides, so the rate measured the desktop. Each frame was
  timed inside itself instead (the board's callback, then `gl.finish()`), with
  `--disable-backgrounding-occluded-windows --disable-renderer-backgrounding`. The 95th
  percentile is under 16.7 ms on four maps and 16.8 on the town: 60 fps holds with the
  model loaded. Tilt-shift off changed nothing measurable (World 14.3 → 14.1 ms).
- **The canvas was small**: 462 × 307 to 522 × 350 in a 1424 × 925 window, the table's well.
  A larger well costs more; not measured.
- **VRAM:** about +300 to +450 MiB with the board open, against the table alone (11.0–11.5 GB
  in use of 12 with the model loaded). No allocation failed.
- **Real presses:** the town's gate arrow, pressed by mouse at its projected spot, opened the
  Region; the World breadcrumb, pressed by mouse, opened the World.
- **Reduced motion** (emulated `prefers-reduced-motion: reduce`, page reloaded): the board
  draws, still; screenshot checked.
- **A lost context** (`WEBGL_lose_context.loseContext()`): the tab handed over to the chart,
  drawn from the same state, all 28 of Thornstead's places on it; screenshot checked.

## Not proved

- The installer was built but not installed; `win-unpacked` was what ran.
- Frame cost on a weaker GPU, or at a larger window, was not measured.
- The frame rate as a person sees it on screen was not measured: the window was not in front
  for most of the run, and taking the user's focus was refused on purpose.
