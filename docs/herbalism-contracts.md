# Herbalism revamp: the contracts between lanes

Written 2026-10-02 by the lead, before the lanes branched. It works with the two plans:
`docs/herbalism-revamp-plan.md` (the rules) and `docs/herbalism-ui-plan.md` (the interface).
This file says **who owns which file** and **what each lane may assume about the others**.

A lane builds against these contracts with fakes for anything another lane owns, and never
edits a file it does not own. If a contract has to change, the lane stops and reports it in
its hand-back; it does not change the contract itself.

---

## 0. Ground rules for every lane

- **Branch:** `git switch -c <branch> ui/table-v2` first. Worktrees start at origin/master,
  which does not have this work.
- **Tests:** run **targeted tests only** (your own files plus the ones listed for your lane),
  with `python -m pytest -p no:cacheprovider -v <files>`, and read the exit code. Never use
  `-q` and grep for "passed". The lead runs the full suite at merge. Never edit a `.py` file
  while a test run is going, because `inspect.getsource` tests read live files.
- **Test docstrings name the defect** they prevent, with the measurement.
- **Comments say why**, at the density of the surrounding code.
- **No third-party JavaScript.** The app bundles none on purpose (see the header of
  `play/static/js/scene3d.js`). Write it yourself.
- **No downloads.** Don't fetch icons, textures, sounds, models or libraries from the internet.
  Generate them in code: procedural textures, synthesized sound, built meshes. Icons are the
  lead's job (§5.4).
- **Never touch the owner's real data.** Live checks use a scratch data dir through
  `PATHFINDER_GM_DATA`. Never launch the packaged app or Electron; the owner may be playing.
- **The three laws** (CLAUDE.md): tags, one applicator, severed tells, and no model authoring
  a number. Load the `states-effects-tells` skill if you touch effects.
- **Use the Write/Edit tools for anything with backslashes**, never heredocs or sed into
  source.
- **No em-dashes in new player-facing bench strings** (UI plan §8).
- **Hand back** a summary covering:
  - files changed;
  - the tests you ran and their exit codes;
  - anything you could not do;
  - any contract you think is wrong.

---

## 1. File ownership

Each file has one lane. Anything not listed belongs to nobody in this batch: don't edit it.
Ask in your hand-back if you need it.

| Lane | Branch | Owns |
|---|---|---|
| **A: Data** | `lane/herb-data` | `content/ingredients/**`, `content/materials/**`, `rules/ingredients.py`, `tools/export_herbs_for_tagging.py`, `docs/herb-tagging-prompt.md`, `docs/herbs*.md`, `docs/herbs-for-tagging.json`, `docs/campaign-format.md`, `docs/from-world-bible.md`, new `docs/herbalism-hybrid-review.md`, new `tests/test_ingredient_tags.py`, and existing tests that pin ingredient content |
| **B1: Progression** | `lane/herb-progress` | `rules/worldclass.py`; `content/world-classes/herbalist.json`; in `rules/sheet.py`, **only** `_progress` and `_progress_dict`; `tests/test_worldclass.py`; `tests/test_legendary_catalyst.py`; new `tests/test_herbalist_endless.py` |
| **B2: Bench engine** | `lane/herb-bench-engine` | `rules/crafting.py`, `rules/herbprep.py`, `rules/pricing.py`, `rules/benches.py`, new `content/rules/herbal-methods.json`, `herbal-products.json`, `herbal-quality.json`, `play/bench_views.py`, `play/craft_views.py` (only to retire herbalism from the old bench), `docs/alchemy.md`, the herbalism section of `play/templates/play/manual.html`, `tests/test_crafting.py`, `tests/test_herbprep.py`, `tests/test_power_leaf.py`, `tests/test_benches.py`, `tests/test_pricing.py`, new `tests/test_bench_api.py` |
| **C: Discovery** | `lane/herb-discovery` | `rules/herbknowledge.py`, `rules/engine.py` (the taste op and whatever routing it needs), `play/herb_views.py`, `play/history.py`, **all of `gm/**`** (including removing the retired method words from `gm/judgement.py` and `gm/interpret.py`), new `content/items/herbal-manuals.json` or wherever goods live (a **new** file only), `play/static/js/table/21-tab-journal.js`, new `tests/test_herb_discovery.py` |
| **D: Bench UI** | `lane/bench-ui` | `play/templates/play/table.html`, `play/templates/play/craft.html`, new `play/static/css/bench.css`, new `play/static/js/table/30-bench-shell.js`, `31-bench-satchel.js`, `34-bench-tag.js`, `35-bench-herbarium.js`, `36-bench-perks.js`, new `play/static/js/bench-icons.js`, new `tests/test_bench_ui.py` |
| **E: Games** | `lane/bench-games` | new `play/static/js/table/33-bench-games.js`, new `play/static/js/bench-games/*.js`, new `play/static/css/bench-games.css`, new `tools/bench-harness/games.html`, new `tests/test_bench_games.py` (static checks) |
| **F: Stage** | `lane/bench-stage` | new `play/static/js/table/32-bench-stage.js`, new `play/static/js/bench-stage/*.js`, new `tools/bench-harness/stage.html`, new `tests/test_bench_stage.py` (static checks) |
| **G: Sound** | `lane/sound` | new `play/static/js/sound.js`, new `play/static/js/prefs.js`, `play/templates/play/home.html` (the Settings pane only), and sound calls added to `play/static/js/dice3d.js`, `play/static/js/table/22-roll-verdict.js` and `04-combat-and-turns.js`; new `tests/test_sound.py` |

**Shared seams the lead built before branching** (`4ac23be` and the scaffold commit after it):
- `rules/sheet.py`: `Actor.herb_known`, `Actor.manuals_read`, `Progress.perks` and
  `Progress.schema`, each written only when set.
- `rules/worldclass.py`: `PERKS`, `perk_picks_banked`, `ceiling_index` and `award_bonus`.
  B1 may refine the bodies but not the signatures.
- `rules/herbknowledge.py`: stub signatures. C fills them in.
- `play/bench_views.py` and `play/herb_views.py`: stub views. B2 and C fill them in.
- `pathfindergm/urls.py`: every route. **No lane edits `urls.py`.**

**Script tags.** D adds every new script and stylesheet tag to `table.html`, including E's,
F's and G's, in this order:
1. `prefs.js` and `sound.js` early, after `dice3d.js`;
2. `bench-icons.js`;
3. `30` to `36` in number order after `22-roll-verdict.js`;
4. `bench-games/*.js` and `bench-stage/*.js` before `32` and `33`.

E, F and G never edit `table.html`. G adds its own tags to `home.html`.

---

## 2. Vocabulary (fixed)

**Method ids:** `grind`, `mix`, `brew`, `dry`, `reduce`, `extract`, `infuse`, `steep`,
`neutralize`.
- Level 1: grind, mix, brew.
- Level 2: dry, reduce, extract, infuse, steep.
- Level 3: neutralize, plus legendary material.

**Product forms:** `infusion`, `decoction`, `tincture`, `acetum`, `poultice`, `infused-oil`,
`salve`, `balm`, `cream`, `salve-base`, `powder`, `dried`, `extract`, `reduction`.

**Ingredient states:** `raw`, `extracted`, `neutralised`, `ground`, `dried`. The spelling is
`herbprep`'s. The method id stays `neutralize`, mapped as `herbprep._AS_STEP` already does.

**Quality indices:** 0 Crude, 1 Sound, 2 Fine, 3 Superior, 4 Flawless, then 5 "Flawless +1",
and so on. The names come from the server; the UI never builds them.

**Ingredient fields that A adds** (all optional, with defaults; B2 reads them through
`getattr` with the default):

| Field | Values | Default |
|---|---|---|
| `part` | leaf, flower, root, bark, berry, seed, sap, resin, fungus, gland, organ, bone, horn, feather, scale, eye, shell, oil, wax, mineral, liquid | `leaf` for herbs, `organ` for monster parts, `fungus` for fungi |
| `base_for` | list, e.g. `["salve"]` | `[]` |
| `neutralizer` | int strength | `0` |
| `solvent` | `oil`, `alcohol`, `vinegar`, `water`, or empty | `""` |
| `hybrid` | bool | `false` |
| per effect `route` | ingest, skin, eyes, wound, inhale, external | `ingest` |

The `route` is stored on each structured effect dict in `effects`.

Fields must exist on the `Ingredient` dataclass, because `from_dict` drops anything without
one (see the comment there).

**Carriers and reagents.** Oil, alcohol, vinegar, beeswax and neutralizers are ingredients
with `solvent`, `base_for` or `neutralizer` set. A decides whether they live in
`content/ingredients/` or `content/materials/`, and the bench reads them through
`rules/ingredients.py` either way.

---

## 3. The bench API (B2 builds, D consumes)

All JSON. Errors are `{"error": "<plain sentence>"}` with status 400 (the player's input was
wrong) or 409 (the state changed).

**Satchel item** (used everywhere below):

```json
{"key": "opaque string the UI posts back", "name": "Comfrey", "ingredient_id": "comfrey",
 "kind": "herb", "part": "root", "tier": "common", "state": "raw", "form": null,
 "quality": null, "quality_name": null, "count": 3, "unknown": 1,
 "spoils_in": 9840, "ready_at": null, "crafted": false}
```

`spoils_in` and `ready_at` are in minutes. `form`, `quality` and `quality_name` are set for
crafted things. `ready_at` is set for a steeping jar.

### 3.1 `GET /api/bench/state`

```json
{"track": {"id": "herbalist", "level": 2, "mp": 30, "to_next": {"need": 65, "have": 30},
           "ceiling": 3, "ceiling_name": "Superior", "perks": {"quality": 1},
           "picks_banked": 0, "next_rung": "Flawless at Herbalist 3"},
 "methods": [{"id": "grind", "name": "Grind", "level": 1, "locked": false,
              "lock_reason": ""}],
 "satchel": [<item>, ...],
 "ground": {"biome": "forest", "roofed": false, "minute": 20160, "place": "The Outskirts"},
 "recipes": [{"id": "r1", "name": "Comfrey poultice",
              "steps": [{"method": "grind", "items": [{"ingredient_id": "comfrey", "count": 2}]}]}],
 "clock": {"day": 14, "label": "Day 14, 6:20pm"}}
```

### 3.2 `POST /api/bench/check`

Request: `{"method": "grind", "items": [{"key": "...", "count": 2}], "batch": 1}`

Response:
```json
{"fits": {"<every satchel key>": "" or "reason in words"},
 "problems": ["..."], "can_roll": true, "minutes": 30, "dc": 12, "bonus": 6,
 "terms": [{"label": "Herbalist 2", "value": 2}], "need": 6,
 "impossible": "",
 "product": {"name": "Comfrey Poultice", "form": "poultice", "taken": "bound on a wound",
             "keeps_minutes": 1440, "routes": ["wound", "skin"], "unknown": 1,
             "effects": [{"base": "Heals 1d4", "by_tier": ["Heals 1d3", "Heals 1d4", "Heals 1d4+1", "Heals 1d6", "Heals 1d6+1"]}],
             "drawbacks": [{"base": "...", "by_tier": ["..."]}],
             "source_text": "what the source says"}}
```

- `fits` covers **every** satchel item for the active method and the current pot. This is what
  dims tiles.
- `need` is the d20 face needed. It is `null` with `impossible` filled in when no face can
  succeed (plan §5.3: no automatic natural 20 on bench checks).
- `by_tier` runs from 0 to the ceiling.

### 3.3 `POST /api/bench/roll`

Request: the same as `check`, plus `"face": int` or `null`. A null face means the server
rolls, the same convention as the old bench's `craft_do`.

Response:
```json
{"roll": {"face": 14, "bonus": 6, "total": 20, "dc": 12, "success": true, "margin": 8},
 "verdict": {"word": "Success", ...},
 "lost": [{"key": "...", "name": "Comfrey", "count": 1}],
 "minutes": 30, "clock": {...},
 "token": "opaque, present only on success",
 "tuning": {"method": "grind", "part": "root", "difficulty": 0.6, "seconds": 6,
            "beats": 8, "infusion": false}}
```

- The materials are **reserved** on success and spent at finish.
- On a failure the book rule applies at once: miss by 4 or less and nothing is lost; miss by
  5 or more and half is ruined, rounded up. `lost` says what.
- Time passes either way.
- `verdict` has the same shape `/api/roll` returns.

### 3.4 `POST /api/bench/finish`

Request: `{"token": "...", "score": 0.0-1.0, "stopped": false}`

Response:
```json
{"tier": 2, "tier_name": "Fine", "score": 0.71, "ceiling": 3,
 "made": <item>, "count": 2,
 "mastery": {"lines": [{"why": "Grind, comfrey", "mp": 1}, {"why": "first poultice", "mp": 3}],
             "total": 34, "level": 2, "levelled": []},
 "discoveries": [{"ingredient_id": "comfrey", "name": "Comfrey", "text": "Heals 1d4"}],
 "next": {"method": "mix"} or null,
 "state": <the 3.1 body, refreshed>}
```

The server clamps the score and computes the tier against the ceiling. The page never names a
tier.

### 3.5 `POST /api/bench/perks`

Request: `{"picks": ["quality", "quality"]}`. Exactly as many as are banked, or two.

The response is the 3.1 `track` object.

### 3.6 `POST /api/bench/recipe`

Request: `{"name": "...", "steps": [...]}` to save, or `{"delete": "r1"}`.

The response is `{"recipes": [...]}`.

---

## 4. The discovery API (C builds, D consumes the bench parts)

### 4.1 `GET /api/herbarium`

```json
{"entries": [{"id": "comfrey", "name": "Comfrey", "kind": "herb", "part": "root",
              "tier": "common", "known": 3, "total": 5, "biomes": ["forest"], "carried": 2}]}
```

### 4.2 `GET /api/herb/<id>`

```json
{"id": "comfrey", "name": "Comfrey", "kind": "herb", "part": "root", "tier": "common",
 "biomes": ["forest"], "danger_known": "",
 "properties": [{"key": "p0", "known": true, "text": "Heals 1d4", "drawback": false,
                 "how": "tasted, day 14"},
                {"key": "p1", "known": false, "text": null, "drawback": null, "how": null}],
 "can_study": true, "study_minutes": 10, "can_taste": true,
 "teachers_here": [{"ref": "npc3", "name": "Old Marta", "price": "2 sp"}],
 "library_here": {"name": "Temple archive", "price": "5 sp", "minutes": 60} or null}
```

### 4.3 `POST /api/herb/study`

Request: `{"id": "comfrey", "face": null}`

Response: `{"roll": {...}, "revealed": [<property>], "minutes": 10, "clock": {...}}`

### 4.4 `POST /api/herb/taste`

Request: `{"id": "comfrey"}`

Response: `{"revealed": [<property>], "tells": ["..."], "minutes": 1, "down": false}`

`down` is true if the taster dropped. The table's existing deathveil handles death.

### 4.5 `POST /api/herb/ask` and `POST /api/herb/library`

Request: `{"id": "...", "ref": "npc3"}` for ask, or `{"id": "..."}` for library.

Response: `{"revealed": [...], "paid": "2 sp", "minutes": ..., "refused": ""}`

### 4.6 `POST /api/herb/manual`

Request: `{"item": "<manual id>"}`

Response: `{"revealed": [...], "mastery": {...}, "minutes": ...}`

### 4.7 Python seams C owns, which others call

These are in `rules/herbknowledge.py`:
- `property_keys(ingredient)`;
- `known_keys(actor, ingredient)`;
- `unknown_count(actor, ingredient)`;
- `reveal(actor, ingredient_id, keys, how) -> new keys`.

B2 calls `reveal` when a product shows what it carries, and `unknown_count` for satchel
tiles.

---

## 5. Front-end interfaces

All are globals on `window`, plain ES5/ES2017 functions in IIFEs like the rest of
`play/static/js`. **Every consumer must work when a provider is missing.** D's bench must
run with no stage, no games and no sound (flat fallbacks), so each lane can be verified
alone.

### 5.1 `window.BenchStage` (F provides, D and E consume)

```js
BenchStage.available()                 // -> bool: WebGL works here
BenchStage.mount(hostEl)               // -> Promise; draws into a canvas it creates
BenchStage.unmount()
BenchStage.setGround({biome, roofed, minute})
BenchStage.setTool(method)             // -> Promise, resolves when the drop settles
BenchStage.addIngredient({key, part, name}); BenchStage.removeIngredient(key); BenchStage.clearIngredients()
BenchStage.setDragOver(bool)           // the gold rim ring while a tile is dragged over
BenchStage.game(method)                // -> GameView (below), for the minigame's 3D half
BenchStage.flourish(kind)              // 'tierUp' | 'flawless' | 'fail' | 'land'
BenchStage.productRect()               // -> DOMRect where the product appears, for the fly-to-satchel
BenchStage.reducedMotion(bool)         // set by D from the prefers-reduced-motion query and PGMPrefs
```

**GameView**: `{update(state), hit(strength0to1, index?), miss(index?), end()}`. The `state`
for each method:

| Method | State |
|---|---|
| grind | `{ring: 0..1 (1 = closed on the mark), struck: bool}` |
| mix | `{guide: [[x,y]...] in 0..1, trace: [[x,y]...], gloss: 0..1}` |
| brew | `{heat: 0..1, band: [lo, hi], boil: bool}` |
| dry | `{bundles: [{cure: 0..1, band: [lo, hi], turned: bool}]}` |
| reduce | `{level: 0..1, line: 0..1, heat: 0..1, band: [lo, hi], scorch: x}` |
| extract | `{path: [[x,y]...], at: 0..1, pace: 0..1, nicked: bool, nodes: [u...]}` |
| infuse | `{heat: 0..1, cold: x, scorch: y, fill: 0..1}` |
| steep | `{fill: 0..1, mark: 0..1, sealing: bool, seal: 0..1}` |
| neutralize | `{needle: -1..1, safe: [lo, hi], drops: n}` |

Fields added after the lanes merged. Every one is optional: a game may leave it out, and a
stage given the older state must draw what it can and never throw.

- **extract `nodes`** (added 2026-10-02, optional): the stop points, as 0..1 positions along
  the path in the same units as `at`. The stage draws each on the incision path by shape: an
  open ring for one still ahead (the next one larger), a notch across the path once the knife
  has passed it.
- **reduce `band`** (added 2026-10-02, optional): the good simmer range `[lo, hi]`, in heat
  units (0..1, the same scale as `heat`).
- **reduce `scorch`** (added 2026-10-02, optional): the heat at which the crust forms, in heat
  units. The stage shows `band` and `scorch` on a brass dial on the pan's handle: the band a
  gold arc notched at both ends, the scorch zone hatched. Without them the dial shows the
  game's defaults, `[0.55, 0.77]` and `0.9`, as Brew's dial does.
- **`hit(strength, index)` and `miss(index)`** (added 2026-10-02, optional second and first
  argument): which piece of the tool the result belongs to, for a game with several (Dry's
  bundle, 0-based). Without it the stage falls back to its own guess, the bundle the last
  state showed turning, which is a frame behind the press.

The stage draws the game on the tool: the pestle, the needle on the pot, the bundles.
Rendering only on demand: **no animation loop while idle** (UI plan §10).

### 5.2 `window.BenchGames` (E provides, D consumes)

```js
BenchGames.play({method, part, tuning, mount: stripEl, stage: GameView|null,
                 steady: bool, reducedMotion: bool,
                 onScore: function (score0to1) {}})   // -> Promise<{score, stopped, hits, misses}>
BenchGames.stop()        // the player pressed Esc and confirmed: resolve now with stopped:true
BenchGames.pause(); BenchGames.resume()   // D calls these on window blur and focus
```

- With `stage: null`, the game draws its whole picture in the strip. That is the flat
  fallback, and it must be fully playable.
- Mouse and keyboard work in every game. Steady mode as in UI plan §9: no hold longer than one
  press, and halved speeds.
- E plays sounds through `window.Sound` if present: `bench.hit.<method>`,
  `bench.miss.<method>`.

### 5.3 `window.Sound` and `window.PGMPrefs` (G provides, everyone consumes)

```js
Sound.play(name, {volume, rate})       // unknown names are a silent no-op
Sound.loop(name)                       // -> {stop()}
Sound.unlock()                         // called on the first user gesture
PGMPrefs.get(key); PGMPrefs.set(key, v); PGMPrefs.on(key, fn)
```

- **Pref keys:** `steady` (bool), `flourishes` (`'full'` or `'short'`), `sound.master`,
  `sound.ui`, `sound.dice`, `sound.bench`, `sound.ambience`, `sound.combat` (each 0..1), and
  `sound.mute`.
- **Sound names** use the bus as their first segment: `ui.*`, `dice.*`, `bench.*`,
  `ambience.*`, `combat.*`, `verdict.*`.
- **The bench names** are in UI plan §11.
- **Synthesis:** G synthesizes every sound with Web Audio (noise, filters, envelopes); there
  are no sample files in this batch.

### 5.4 Icons (D's registry, the lead fills the art)

`window.BenchIcons.el(name)` returns an element. `name` is a part id, method id, state id,
or one of `lock`, `recipe`, `taste`, `study`.

Until the owner approves downloading the game-icons.net set, the registry draws a
**lettered brass roundel** (the first letter in Cinzel on the `--gilt` disc). That is a
stand-in, not hand-drawn icon paths. When the SVGs arrive, the lead drops them into
`play/static/img/icons/` and the registry switches to `mask-image` with no other change.
