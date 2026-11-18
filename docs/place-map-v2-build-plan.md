# Place map v2: the build plan

How the tabletop map in `docs/mock/place-map-v2/` (branch `mock/place-map-v2`, last commit
`3b467d84`) goes into the game. The mock settled the design with the owner across one
session on 2026-11-18; this plan is the work to ship it.

The owner picked the 3D tabletop. Everything below is for that style only.

## What ships

Five maps with a breadcrumb: **World › Continent › Region › Town › Site**.

- **Town:** inside the walls only.
  - Laid out by rule: the great square in the middle, the crossings at their compass points,
    each place in a fixed seat on its street.
  - Streets grow in rows and never stack.
  - Floors are badges; an arrow out of the gate leads to the Region.
  - Kenney miniatures on a leather-rolled scroll of the game's chart paper.
- **Region:** the nation you stand in, at Pathfinder's 12-mile overland hex.
  - Terrain comes from the engine's own reading of the world (`geography.land_around` and the
    roads' `crosses`).
  - Wild ground stands on hexes of its own kind: the woods on forest, the desert on sand.
  - Roads leaving the nation end in arrows.
- **Continent:** every nation coloured (neighbours never share a colour), named and bordered.
  - Your known towns and roads, with a peg a day at 24 miles.
  - The sea passages from ports you've stood in.
- **World:** continents painted as land, with the fog lifted round the cities you know.
  - A pin by each city in the colour of how you learned of it.
  - Nation names inside their own borders.
- **Site:** a dungeon's rooms as a dollhouse, unexplored rooms blank.
- **Moving between them:** pointing lights a continent or a nation, and pressing or zooming in
  opens it. Zooming out past a map's furthest opens the one above.
- **Names stay readable:** names that can't fit are held back by priority (hover shows them),
  town names fade as you zoom out and nation names grow, and long names end in "…".

**Rulings this carries** (owner, 2026-11-18):
- Anything outside the city belongs on the region map.
- The region is the nation you are in.
- The old region board is the continent.
- Maps are bought at general stores for about 5 gp, one map to a nation, its own nation only.
- What a map teaches is never forgotten.

## Decisions needed before the build starts

1. **Three.js as the app's first bundled third-party JavaScript.** `scene3d.js` says the app
   "bundles no third-party JavaScript at all"; its board and dice are hand-rolled.
   - **The tabletop needs** a real renderer (lighting, shadows, instancing, glTF loading).
     Three.js r170 is MIT-licensed, 690 KB, and fits offline as a vendored file. Hand-rolling
     the same is weeks of work and a worse result.
   - **Recommendation:** adopt Three.js for this map only. Keep it out of the board and dice.
2. **Free orbit, or fixed quarter-turns.** `scene3d.js` deliberately turns the tactical board
   in four fixed quarter-turns, citing XCOM: a free camera disorients over a tactical map.
   - A place map isn't tactical, and the mock orbits freely within limits.
   - **Recommendation:** orbit, with a "reset view" button, and limits that stop the camera
     tipping below the table.
3. **What happens to today's Places chart** (`16-places-chart.js`, `16-tab-map.js`).
   **Recommendation:** keep it as the fallback when WebGL is unavailable or the context is lost
   (old GPUs, driver resets), drawn from the same data. Retire nothing until the tabletop has
   shipped one release.
4. **Small reaches on the Region.** A 3-mile reach (the woods) currently gets a 12-mile hex of
   its own: right in direction, generous in distance. The alternative is to keep reaches under
   6 miles inside the town's hex, as the outskirts are.
5. **Retire the chart and diorama mocks.** Recommendation: yes, once phase 2 lands.
6. **Map item details.** Its weight; whether it can be sold back; whether reading it takes game
   time; what a second copy does.
7. **Where cities "heard of" come from.** NPC speech only, as `heard_places` does today, or also
   notices, books and signs?

## Phases

Each phase is its own lane off fresh `origin/master`, named for the work, and merged in order.
The suite runs from a `C:\Users\natha\pgm-work\` worktree.

### Phase 1: the atlas (server)

The data every map draws from, with no UI change.

- **A new `play/atlas.py`.** It returns, per world (static, so cached with a version stamp, per
  the frozen-app lesson in CLAUDE.md):
  - cities: id, name, nation, continent, scale;
  - each city's ground from `geography.land_around`: `near`, `beyond`, and `reaches` with
    miles and source;
  - nations and continents;
  - routes from `play.travel`, with `by`, `miles` and `crosses`;
  - the sea legs `journey.legs_from` derives for ports. The mock found two of these traps: the
    `sea` flag is also set on river legs, so read `by`. And `play.travel` alone lists only two
    of Ledgernook's 17 sea routes.
- **A new endpoint `/api/atlas`**, fetched once per campaign. The world never changes in play,
  so it stays off `/api/state`.
- **Knowledge on `/api/state`** (`scene.known_places`, small, changes with play):
  - the towns stood in (derived from `scene.places_been()`, as `places_found` does);
  - towns heard of (a new store, phase 5; empty until then);
  - maps read (a new store, phase 5; empty until then).
  - These are knowledge, not actor state, like `scene.been`. They only grow. NetHack removed
    map amnesia; `places_found.py` already cites that refusal.
- **The site's data:** a founded dungeon's rooms, from `scene.founded` (role, door, parent,
  exits, been), added to `places_found` or beside it.
- **Tests:**
  - atlas shape on all three fixture worlds (Aurvantis, Pangrella, synthetic);
  - sea legs read `by`, not the `sea` flag;
  - `known_places` grows, never shrinks;
  - the site data matches `scene.founded` on frag's save (copy only).

### Phase 2: the town tabletop

Replaces the Places chart's drawing, with the chart kept as the fallback.

- **Vendor**, in version-named directories so a cached copy can never be stale (the CLAUDE.md
  cache lesson), with each addon's `import 'three'` rewritten to a relative path so no
  importmap is needed:
  - `play/static/js/vendor/three-r170/`: `three.module.min.js` plus `OrbitControls`,
    `GLTFLoader` and `BufferGeometryUtils`;
  - `play/static/models/kenney/`: the 34 GLBs, both `colormap.png` files, and both
    `License.txt` files.
  - Add Three.js (MIT) and Kenney (CC0, credit "Kenney" optional) to `docs/asset-licences.md`.
- **Port the mock into `play/static/js/table/`:**
  - `16-places-model.js`: the mock's `shared/model.js`, minus the fog and route replay (the
    engine owns those). That leaves `townLayout`, `worldLayout`, `nationColours`, `darken` and
    `sites`.
  - `16-places-board.js`: the mock's `tabletop.js`, loaded as a module with dynamic `import()`
    from the classic `16-tab-map.js`.
  - `16-tab-map.js` keeps the slip, Walk there, the breadcrumb and the say door. It chooses
    between the board and the chart with a WebGL check and a `webglcontextlost` listener.
- **Town specifics:**
  - only `setting == "in"` places;
  - seats in endless rows (the `k % 8` wrap the worst case caught);
  - the gate arrow;
  - the paper sized to the town;
  - names culled by priority and faded by zoom.
- **Tests,** run in node like `tests/test_table_places.py`, on the shipped scripts and fed real
  charts:
  - seats never stack (16 places on one street);
  - discovery never moves a seat;
  - fog and route agree with `places_found.chart()` on all three worlds (the mock's
    `selfCheck`);
  - the worst-case fixture (keep `worstCase()` as test data, dev-only).
- **Verify in the running app** (`/run`), not just in tests: walk, press, the gate, night, rain,
  reduced motion.

### Phase 3: Region, Continent, World

- **The three boards** from the mock, drawn from `/api/atlas` and `known_places`:
  - Continent: hex board, nation colours, borders, names along known rows, day pegs.
  - Region: 12-mile hexes from the median of the roads' measured miles, terrain from `land`
    and `crosses`, wild ground on its own ground, arrows out.
  - World: continents painted, nation territories by nearest city, names fitted inside borders
    (shrink, then two lines), the continent glow on hover.
- **Navigation:** the breadcrumb, hover and press, and the zoom gesture between every pair of
  maps.
- **Fix three things the mock got wrong:**
  - The **World paper** repainted on every press: 740 ms, cut to 15 ms by caching per state of
    knowledge.
  - Two **town labels** were placed for the Region's larger miniatures and floated off on the
    World.
  - **A comment pasted mid-line** hid all World labels once. Nothing to port, but a test should
    assert that labels are drawn.
- **Tests:**
  - `worldLayout` is deterministic, and learning a city moves nothing;
  - no two neighbouring nations share a colour, on all three worlds;
  - every known nation's name is placed inside its borders (the mock reads 16 of 16 on
    Aurvantis); worlds where names don't fit get the same test;
  - the Region's terrain matches `land_around` for the home town.

### Phase 4: the Site map

- The dollhouse from the mock, from phase 1's site data.
- "Go down" from the town (an undercroft, the sewers) or the Region (the cave), and back up.
- Underground ignores the hour.
- **Tests:** unexplored rooms aren't drawn; seen rooms are outlines; the route goes through
  entered rooms only.

### Phase 5: engine knowledge

- **Towns heard of.** Extend the beat reader's "places" call with a "towns" list: the names of
  settlements an NPC's line mentions. Code validates each against `world.of_kind("CITY")`, per
  the owner's "models read, code validates" direction (see `gm/beat_reader.py`, schema with
  `required`/`enum`; `contains` is not enforced by Ollama). Record `{city, who, line, turn}`
  on the scene; it only grows.
- **The map item.**
  - A `GEAR` entry in `rules/goods.py`, "map of <nation>": general stores only, about 5 gp,
    the store's own nation.
  - Reading it adds the nation to `maps_read`.
  - Weight and resale per decision 6.
  - A tell on reading, so the narrator learns of it the lawful way (states-effects-tells, law
    3). Load that skill before touching this.
- **Direct routes between wild places.** The woods to the desert without going back through
  town. A way between reaches in `exits.ways_from`, its hours from their miles at the walking
  pace `journey.hours_for` uses. Needs a ruling on which reaches connect: all of them, or only
  neighbours.
- **Tests:** a heard town is recorded once and a made-up name is refused; the map item is sold
  only at its nation's general stores and taught once; direct wild ways appear in the exits row
  and on the Region.

### Phase 6: packaging and the release proof

- **Size:** Three.js plus models add about 2 MB to `play/static`, shipped through
  `pathfindergm.spec` `datas` with no spec change.
- **Prove against the packaged build:**
  - run `win-unpacked` against a throwaway data dir;
  - hit-test every map control (the release-hit-test rule; 0.2.13 shipped with every click
    swallowed);
  - measure the frame rate and VRAM inside Electron with Ollama's model loaded. The mock
    measured only headless Chrome: 120 fps, +3 to +88 MiB.
  - force a WebGL context loss and check the chart fallback takes over.
- **Reduced motion:** check it on screen. It's done in code but never visually checked.

## World Bible asks

These go into `docs/from-world-bible.md`. Each fixes something the mock had to do by rule.

1. **Settlement positions** (or at least bearings between settlements). Today the World,
   Continent and Region are laid out by rule, so a town's direction can differ between
   maps. Positions fix all three at once. `geography` already leaves `bearing` blank until an
   export states one.
2. **Coastlines and water bodies.** The export says a route goes by sea, never where the sea
   is.
3. **A bearing for each reach** ("the desert to the north"). The Region places the desert in
   the direction furthest from the roads; a stated bearing replaces that.
4. **Real lengths for sea passages.** Every sea leg exports `days_apart: 1`, the derived
   default.

## Size and order

The mock is about 1,900 lines (tabletop 1,022, model 454, controller 413), against 530 for
today's chart and tab. Phases 2 and 3 are most of it.

| Phase | Depends on | Rough size |
|---|---|---|
| 1 Atlas | the decisions | small: one module, one endpoint, tests |
| 2 Town tabletop | 1, decisions 1–3 | large: vendoring, port, fallback, tests |
| 3 Region, Continent, World | 1, 2 | large |
| 4 Site | 1, 2 | small |
| 5 Engine knowledge | 1; decisions 6–7 | medium: beat reader, goods, exits |
| 6 Packaging proof | 2–5 | medium: one release cycle |

Phases 4 and 5 can run beside 3. Phase 6 runs once, before the release that ships it.

## Risks

- **First bundled library.** A Three.js upgrade becomes a dependency to maintain. Pin r170;
  upgrade only on purpose.
- **WebGL on weak or old GPUs.** The chart fallback is the answer (decision 3).
- **Stutter while the model generates or the CPU is saturated.** The mock measured hitches of
  1 to 31 s in every style, the 2D ones included, so this comes with sharing the machine, not
  with 3D. The map is mostly open between turns.
- **Layouts are views, not saved state.** Tuning the layout rules moves pins between versions.
  That's acceptable because nothing is stored by position, but say so in release notes when it
  happens.
- **World-agnostic checks.** Everything above was measured on Aurvantis. Pangrella and the
  synthetic world must pass the same tests (the standing instruction that fixes are
  world-agnostic).
