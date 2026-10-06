# Alchemy revamp: lane contracts

Written 2026-10-05, before any lane starts. The plans are:
- `docs/alchemy-revamp-plan.md` (rules, data and engine), cited as **plan §n**;
- `docs/alchemy-ui-plan.md` (the interface), cited as **UI §n**.

This file fixes **the shapes that cross lanes** and **who owns which file**, so the lanes can
run in parallel without writing over each other. A lane that needs a shape changed asks the
lead; it does not change it locally. The structure follows `docs/blacksmithing-contracts.md`.

**Integration branch:** `alchemy/revamp`, off `origin/master`, at the commit that carries this
file. Every lane starts with `git switch -c lane/alchemy-<letter> alchemy/revamp` in its own
worktree, and never touches another lane's files.

**Shared infrastructure comes first, and from elsewhere.** The cross-craft **In progress**
section and the **metal tag** are built by the **enchanting lanes**. This revamp consumes them
through the interfaces in §10. If they have not merged when a lane needs them, the lane uses the
fallback named there, and never builds its own copy.

---

## 1. File ownership (wave 1)

| Lane | Plan § | Owns (may create and edit) | Reads only |
|---|---|---|---|
| **A: shelf door and the collision** (plan lane 1, **first**) | §5.7, §13.1 | `rules/materials.py`, `rules/knowledge.py`; `content/ingredients/herbs-and-parts.json` (**only** the `basilisk-eye` merge); `content/materials/alchemist-materials.json` (**only** removing the `basilisk-eye` row); `tests/test_alchemy_shelf.py`; the id-uniqueness test moves from `tests/test_alchemist.py:601` into `tests/test_alchemy_shelf.py` | everything else |
| **B: vocabulary** | §5.3, §5.5, §16.3, §16.4, §16.6, §16.9 | `rules/effectspec.py`; `tests/test_alchemy_vocabulary.py` | |
| **C: engine readers** | §11.3, §16.2 to §16.10 | `rules/engine.py`, `rules/sheet.py`, `rules/consumables.py`, `rules/areas.py`, `rules/dice.py`, `rules/states.py`, `rules/intents.py`, `rules/activeeffect.py`, `content/rules/hazards.json` (the burning row's `not_yet` only); `tests/test_alchemy_engine.py`, `tests/test_splash_weapons.py`, `tests/test_light_model.py`, `tests/test_stacking_switch.py` | `rules/effectspec.py`, `rules/spells.py`, `rules/houserules.py` |
| **D: data pass** | §5, §16.9 | `content/materials/alchemist-materials.json`, `content/materials/alchemist-spell-potions.json`, `content/ingredients/herbs-and-parts.json` (**only** adding `essence` to effects), `tools/alchemy_*.py` (new), `docs/alchemy-review.md` (new); `tests/test_alchemy_materials.py` | `rules/effectspec.py`, `rules/materials.py` |
| **E: formulae** | §10, §11 | `rules/formulae.py` (new), `content/rules/alchemy-formulae.json` (new), `content/rules/alchemy-essences.json` (new); `tests/test_formulae.py` | `rules/spells.py`, `rules/casting.py`, `rules/materials.py` |
| **F: bench rules and API** | §4, §6 to §9, §12, §15 | `rules/alchemist.py`, `rules/alchemy_items.py` (new), `content/world-classes/alchemist.json`, `content/rules/alchemy-grades.json` (new), `rules/benches.py`, `play/alchemy_views.py` (new), `pathfindergm/urls.py` (alchemy routes only); `tests/test_alchemist.py` (rewritten), `tests/test_alchemy_bench.py`, `tests/test_alchemy_api.py` | `rules/formulae.py`, `rules/materials.py`, `rules/knowledge.py`, `rules/places.py` |
| **G: places** | §14 | `rules/places.py`, `rules/market.py`, `content/people/occupations.json`; `tests/test_alchemy_places.py` | |
| **H: prices and shops** | §12.4, §12.5 | `rules/pricing.py`, `rules/goods.py`, `content/rules/gear.json`, `content/rules/stall-lines.json`, `content/rules/alchemy-manuals.json` (new); `tests/test_alchemy_prices.py` | `rules/formulae.py` |

**Order.**
1. **A first, alone.** The collision becomes live the moment the hybrid door opens (plan §5.7).
2. **Then B.**
3. **Then C, D and E in parallel.**
4. **Then F, with G and H beside it.**

**Nobody but the owner edits an owned file.** `tests/test_three_laws.py`, `tests/conftest.py`
and `.claude/launch.json` are **owned by nobody** in this wave; do not commit them. A lane that
needs a dev server adds a local launch entry (a `serve-X.cmd` per worktree) and leaves it
uncommitted.

**Wave 2** (after wave 1 merges):
- the UI lanes U1 to U5 (§11);
- **lane I: migration and World Bible** (plan §18, §19). It owns `rules/worldclass.py` (the
  `alchemy_v2` migration entry only), `docs/campaign-format.md` and `docs/from-world-bible.md`,
  with `tests/test_alchemy_migration.py`.

---

## 2. The effect vocabulary (lane B defines, everyone uses)

### 2.1 New fields on every effect (`COMMON`, validated)

| Field | Values | Notes |
|---|---|---|
| `essence` | an id from `ESSENCES`, read from `content/rules/alchemy-essences.json`. At ship: fire, frost, acid, storm, thunder, light, shadow, vigour, purity, ward, might, grace, mind, lightness, sight, binding, decay, change. | Required on a material's `product` traits (lane D's validator), optional elsewhere. Tag form: `essence.<id>`. |
| `grade` | int ≥ 1, default 1 | |
| `drawback` | bool | A cost to the user. `effectspec.is_drawback` already decides direction for gear; this flag is explicit for product traits. |
| `route` | the herb vocabulary (`ingest`, `skin`, `eyes`, `wound`, `inhale`, `external`) **plus `struck`, `area`, `carried`** | |
| `when` | the grammar `sheet._when_holds` reads: `target: {type, subtype, armour_metal}`, `attacker: {...}`, the comparisons | **Becomes validated.** It is unvalidated today (it is not in `COMMON`). |

### 2.2 Types made executable

- **`speed`:** `engine=True`. Targets `land`, `climb`, `swim`, `fly`, `jump`. Lane C wires the
  readers.
- **`sense`:** `engine=True`. Targets `darkvision`, `low_light`, `see_invisibility`. It lands as
  a `sense.<target>` tag for its duration.
- **`permission`:** `engine=True`, **as a tag grant only**. `target` becomes a tag id under
  `permission.*` (for example `permission.breathe_water`). Each tag that no reader asks yet is
  listed in lane C's report.

### 2.3 New types

| Type | Fields | Executor (lane C) |
|---|---|---|
| `light` | `radius_ft` (int), `raised_ft` (int), `duration` | `Scene.light_at` |
| `burning` | `dice`, `rounds` (int), `save` `{type, dc}`, `smother_bonus` (int) | an `ActiveEffect` granting `state.burning`, with `periodic` damage per round; the `extinguish` op |

`apply_condition` gains the target **`glued`** (the condition data in `states.py`, owned by C).

### 2.4 `WORKING_TRAITS` additions

`volatile`, `stabilizer`, `catalyst`, `apparatus`, `solid`, `liquid`, `combustible`,
`slow_to_dissolve`, `light_sensitive`, `corrosive`, `toxic_to_handle`, `wild`, `drinkable`,
`shatters`, `bursts`, `struck`, `stick`, `fireproof`, `warded`, `lead_lined`, plus
**`solvent:<kind>`**, where kind is one of `water`, `alcohol`, `vinegar`, `oil` or `acid`.

**Sign and shape rules** are as the forge's (forge contracts §2). `narrative` stays legal in the
vocabulary, and **lane D's validator refuses it** in alchemy materials and formula cores.

---

## 3. The alchemy material document (lane A serves, lane D fills)

`rules/materials.py` stays **the one door**. Lane A makes the alchemist read through it
(`rules/alchemist.py`'s private loader at 256 retires in lane F), and adds:

```python
materials.alchemy_shelf() -> dict[str, dict]     # alchemist materials + every hybrid ingredient, by id
materials.is_alchemy(doc) -> bool
materials.product_traits(doc) -> list[dict]      # `product`, or legacy `effects`, or a hybrid herb's effects
materials.essences(doc) -> set[str]              # from product traits
```

The normalised alchemy document (every field defaults, so an old file loads):

```json
{
  "id": "brimstone", "name": "Brimstone", "kind": "reagent", "tier": "common",
  "form": "powder", "material": null, "color": [0.86, 0.78, 0.22],
  "product": [ <effect with essence, grade, route, drawback?>, ... ],
  "working": [ {"type": "working", "trait": "volatile"}, ... ],
  "mishap": <effect> | null,
  "toxic": <effect> | null,
  "book": false, "craft_dc": null, "price_gp": 0.5,
  "text": "...", "biomes": [], "obtain": "mined", "market": null
}
```

- **Lane D's validator** (`materials.validate`, the alchemy branch) enforces plan §5.6. It is
  added beside the forge branch, which returns early for non-forge documents today (404-405):
  - at least 3 properties, counting product, working, mishap and toxic;
  - at least 1 drawback;
  - no `narrative`;
  - every product trait has an `essence` and a `route`;
  - house numbers within `TIER_CEILING`, and house dice within the dice ceiling (plan §5.6);
  - `volatile` implies a `mishap`;
  - `toxic_to_handle` implies a `toxic` document.
- **Ids, names and the 8 kinds do not change**, except the deleted `basilisk-eye` row.

---

## 4. Knowledge (lane A)

- `knowledge.MATERIAL_LISTS` counts `product`, `working`, `mishap` and `toxic`. So
  `property_keys` is at least 3 for every alchemy material (it is 0 for all 139 today).
- `knowledge.resolve(id)` gives the merged herb for `basilisk-eye`.
- **One store, `Actor.herb_known`.** Material and ingredient ids are now **pinned disjoint across
  all catalogues and the ingredient file**, and the comment at `knowledge.py:16-17` is corrected
  to say what the test really checks.
- **Formula ids are stored with the prefix `formula:`.** Lane E writes and reads them through
  `knowledge` (§5), never a second store.
- `knowledge.assay`, `assay_dc` and `apply_danger` are reused as they are. Lane F passes the
  alchemy dangers:
  - a failed assay by 5 or more on a volatile reagent applies its `mishap`;
  - an unprotected assay of a toxic reagent applies its `toxic` document.
- `knowledge.identify_potion(actor, stock, total) -> dict`: DC 15 + spell level (plan §11.3).

---

## 5. Formulae (lane E serves)

```python
formulae.all() -> dict[str, dict]                 # authored rows + derived spell rows, authored win
formulae.get(fid) -> dict | None
formulae.for_spell(spell_id) -> dict | None
formulae.signature(family: str | None, essences: set[str]) -> tuple
formulae.match(actor, mix: dict, vessel_id: str, formula_id: str | None) -> dict
#   {"formula": fid | None, "experiment": bool, "found": bool, "ambiguous": int,
#    "missing": ["needs lightness at grade 2; you have 1"], "core": [effect, ...]}
formulae.could_become(actor, mix: dict, vessel_id: str | None) -> dict
#   {"count": int, "known": [fid, ...]}             # unknown formulae counted, never named
formulae.known(actor) -> list[str]
formulae.learn(actor, fid, how: str, *, clock: int) -> bool
formulae.copy_check(actor, fid) -> dict            # {"dc": 15 + spell level, "cost_gp", "hours"}
formulae.spell_level_cap(alchemist_level: int) -> int        # max(1, level // 2)
formulae.caster_level(spell, quality_index: int) -> int      # book minimum + tiers above Sound
formulae.potion_price(spell_level: int, caster_level: int) -> float   # 50 x SL x CL, SL 0 = 0.5
formulae.brew_minutes(price_gp: float) -> int      # 120 if <= 250 gp, else 1440 per 1,000 gp
```

**A formula row** has the shape in plan §10.1. A derived spell row is:

```json
{
  "id": "potion-of-<spell>",
  "kind": "spell",
  "spell": "<id>",
  "family": "potion | oil",
  "requires": {"essences": {"<e>": "<grade>"}},
  "spell_level": "<n>",
  "level": "max(1, 2n)",
  "craft_dc": "5 + CL",
  "book": true
}
```

**The mix** is what the bench pools at a step:

```json
{"traits": [{"key": "damage.fire.struck", "essence": "fire", "grade": 2, "from": ["brimstone", "naphtha"]}],
 "drawbacks": [...], "materials": ["brimstone", "naphtha", "strong-spirits"]}
```

Lane F builds the mix, and lane E only reads it.

**Pinned by lane E's tests:**
- every authored formula's signature is unique;
- a derived row is never findable by experiment unless its signature is unique within the
  actor's reach (plan §10.3);
- `could_become` on three fixed mixes equals a hand count.

---

## 6. The product record and the build (lane F)

Bottle writes the record in plan §12.2. **It stores ids and grades, never computed numbers.**
`rules/alchemy_items.py` serves:

```python
alchemy_items.build(record: dict) -> dict
# {"specs": [effect, ...],        # core (scaled by quality, or at CL) + picked traits at grade + drawbacks,
#                                 #   each with "origin": "item:<id>" and "source": the material(s) or spell
#  "family": "splash", "how": ["throw"], "action": "standard",
#  "splash": {"amount": 1, "damage_type": "fire"} | None,
#  "range_increment_ft": 10 | None,
#  "holds_spell": "<id>" | None, "caster_level": int | None,
#  "price_gp": float, "keeps_minutes": int | None,
#  "lines": [{"trait": "fire", "grade": 2, "cap": 2, "from": [...]}, ...],
#  "version": int}
alchemy_items.preview(mix, *, family, formula, picks, quality_index, level, perks) -> dict   # same shape
```

- `Stock.specs` is filled from `build` **at load, when the stamped `version` differs**. That is
  CLAUDE.md's rule for derived caches: compare the version, not a time.
- **Old work** (`schema` below 4) is never rebuilt.
- **`holds_spell` and `caster_level` are always written** on spell potions. That is the
  enchanter's contract, pinned by `tests/test_magicitem.py:207` and `:254`.

---

## 7. What lane C's readers promise (lanes F, H and U use)

- **`use_item how=throw`** emits an `attack` intent with `mode: "splash"`. The dose is committed
  first.
  - The attack is against `touch_ac`, with no nonproficiency penalty, −2 per full range
    increment, and a maximum of five increments.
  - **A hit:** the direct specs land on the target, then the splash lands on every creature
    within 5 ft (`areas.burst_cells` and `areas.caught`).
  - **A miss:** a 1d8 direction, then range-increment squares; `Scene.place_prop(square=…)`; the
    splash lands on that square and the squares adjacent to it.
  - **A grid-intersection aim** is AC 5.
  - Params: `{"item", "how": "throw", "to" | "square"}`.
- **Clouds and tools:**
  - `use_item how=throw` with a cloud lays its `manifest` at the landing square;
  - `how=light` (a tool) applies the tool's spec to the user: a sunrod's `light`, a smokestick's
    manifest at the user's square, a tindertwig lighting a carried torch.
- **New ops**, in `intents.py` and `engine.py`:
  - `extinguish`: full-round; refused without `state.burning`; Reflex against the effect's DC;
    `+smother_bonus` when the param `roll: true`; water terrain smothers outright.
  - `break_free`: `{"how": "strength" | "slash"}`; DC 17 Strength, or 15 slashing to the goo.
    Hitting the goo is automatic.
- **`Scene.light_at(square) -> str`** gives one of four levels. `Actor.concealment(ctx)` adds the
  light miss chance (dim 20%, dark 50%), honouring `sense.darkvision` and `sense.low_light`.
  `sense.see_invisibility` ignores invisibility's concealment.
- **Fog** gives 20% concealment within 5 ft and 50% beyond. It is no longer total cover. This
  applies to every obscuring manifest, *fog cloud* included.
- **`when` clauses:**
  - consumable specs forward `when`;
  - damage evaluates it against the struck creature;
  - timed buffs evaluate it against the roll's `ctx`.
- **Spell potions.** `consumables.plan` on a stock with `holds_spell` and no authored specs
  resolves through `spells.effects_at(spell, cl)` and `spells.roll_duration`, with the drinker as
  caster and target. An area spell is centred on the drinker.
- **The stacking switch.** `dice.stack(mods, *, magic_stacking: bool)`. With it on, typed bonuses
  from **different `source`s** add, and the same source keeps the better. Every caller passes
  `houserules.magic_stacking()`. The scope is plan §16.10, and **open point 2 must be answered
  before this merges**.
- **Bench intents.** The bench's mishap and toxic effects arrive as ordinary intents with
  `origin: "rule:mishap:<material>"` or `"rule:toxic:<material>"`, through `validate` and `run`.
  There is no private applicator.

---

## 8. Bench rules and API (lane F serves, wave 2 UI consumes)

**Methods:** `calcine, dissolve, distill, filter, react, sublime, bottle, transmute, assay`. Per
method, the rows in `alchemist.json` → `bench.methods` take the forge's shape (`where`, `bulk`,
`minutes`, `tuning`).

**Perks:** `potency`, `duration`, `quality`, `yield`, `containment`.

**The API mirrors `play/forge_views.py`.** It is registered **above any catch-all**, and the
pending roll is held in module memory keyed by campaign id with a token, as `_PENDING` is in the
forge (`forge_views.py:38-41`).

| Route | Does |
|---|---|
| `GET api/alchemy/state` | the shelf (carried materials, intermediates, finished work, In progress), methods with locks and reasons, where you are, the level, banked perks, the ceiling, colours per material |
| `POST api/alchemy/check` | method, roles (inputs, solvent, vessel), formula or `experiment`, picks and batch. Answers with the info line, the DC, "you need N+", problems in words, the **mishap and toxic lines**, `could_become`, the slots with reasons, the mix colour, level and turbidity, the reaction or heat tuning, and `alchemy_items.preview` |
| `POST api/alchemy/roll` | the player's d20. Success, or the loss in words **and the mishap's applied effects** (`flare: true` when one applied) |
| `POST api/alchemy/finish` | the game score 0..1, which gives the tier, the product and its `build`, mastery lines, discoveries (a formula found by experiment), minutes passed, and any In progress row |
| `POST api/alchemy/assay` | a material id, which gives the `knowledge.assay` result and any danger applied |
| `POST api/alchemy/learn` | `{fid, from: "scroll" | "spellbook" | "teacher" | "companion" | "formulary" | "potion", item?}` → the check and the result |
| `POST api/alchemy/collect` | an In progress row id, which gives the stock row (through §10's interface) |
| `POST api/alchemy/perks` | pick perks |
| `POST api/alchemy/recipe` | save or load a recipe |
| `GET api/alchemy/formulary`, `GET api/alchemy/codex`, `GET api/alchemy/material/<id>` | the books and one card |

**Every number in a response comes from the engine.** The page computes none, not even the
count or the colour.

---

## 9. Places (lane G serves)

```python
places.laboratory_here(scene, known=()) -> dict | None
#   {"kind": "town" | "owned", "place": place_id, "keeper": ref | None,
#    "rate_cp_per_hour": int, "fume_hood": True}
places.has_alchemy_kit(actor) -> bool          # "alchemist's field kit", carried
market.lab_rent(scene, hours: float, known=()) -> int     # copper pieces
LAB = "place.laboratory"; ALCHEMY_WORK = "alchemy"        # place tag; occupation tag
```

- **A town laboratory** is urban ground whose keeper's occupation carries the `alchemy` tag.
  The new `alchemist` occupation carries it.
- **An owned laboratory** is a founded place tagged `laboratory`, whose holder has
  `holds.place.<slug>`.
- **Guaranteed city laboratories** wait on open point 7. Lane G builds them behind the same
  appended-to-authored mechanism as smithies (`places.py:1088`), off until the owner answers.
- **Never read from the player's words.**

---

## 10. Shared infrastructure consumed (built by the enchanting lanes)

The interfaces alchemy needs, named so the enchanting lanes can build them once for every craft.
**If the enchanting lanes choose other names, they win**, and lane F adapts in one place
(`rules/alchemist.py`'s `_inprogress` and `_metal` helpers). The *capabilities* below are what
must exist.

### 10.1 In progress (owner, leatherworking Q9.3)

```python
inprogress.add(actor, *, craft: str, label: str, product: dict, started_minute: int,
               ready_minute: int, where: str | None = None) -> str        # row id
inprogress.rows(actor, now_minute: int, craft: str | None = None) -> list[dict]
#   [{"id", "craft", "label", "ready_minute", "ready_in_minutes", "ready_day", "done": bool}]
inprogress.collect(actor, row_id: str, now_minute: int) -> dict | None   # the product, added to stock
```

- **The use door refuses anything still in progress.** `engine._op_use_item` already refuses a
  steeping jar (`ready_minute`), and the shared section must keep that guarantee for every
  craft.
- **The UI** shows a cross-craft In progress section with game-time countdowns. Alchemy's shelf
  group links to it (UI §6.9).
- **Fallback until it lands:** alchemy writes `Stock.ready_minute` (`crafting.py:131`), which
  the herb bench and the use door already honour. The shelf's In progress group reads it. When
  the shared section ships, lane F moves the rows with a one-time migration in the same commit.

**Alchemy's rows:**
- spell potions setting for their Brew Potion time;
- Transmutes (one day);
- any step longer than 8 hours (plan §12.3).

### 10.2 The metal tag (owner, leatherworking Q7.3)

```python
materials.is_metal(material_id: str) -> bool          # from the material document (or its parent's)
items.is_metal(record_or_key) -> bool                 # a weapon, armour or vessel, from its pieces
actor.wears_metal() -> bool                           # body armour from a metal body piece
```

**Alchemy reads it in three places** (plan §16.11):
1. a `corrosive` input refuses a metal vessel;
2. gray ooze core and aqua regia damage the struck creature's **metal** armour and weapon
   (`object_damage`);
3. a metal vessel never `shatters`.

**Fallback until it lands:** the three cases read the alchemy material's own `material` link
(`material_of` resolves to a forge metal). That covers iron flask and brass casing, which are
the only metal vessels. The armour case waits for the tag, and lane C names it in its report.

---

## 11. Wave 2: the UI lanes

Every lane starts with `git switch -c lane/alchemy-<id> alchemy/revamp`.

| Lane | Owns | Reads only |
|---|---|---|
| **U1: shell and old tab** | NEW `play/static/js/table/50-alchemy-shell.js`, `51-alchemy-shelf.js`, `53-alchemy-card.js`; NEW `play/static/css/alchemy.css`; `play/templates/play/table.html` (the `#alchemy` layer markup, its script and link tags, the Alchemy button, `ALCHEMY_ICON_URLS`); `play/templates/play/craft.html` (the Alchemy "moved" card); `play/alchemy_views.py` (any response field the page needs); `docs/asset-licences.md` (the icon rows); `tests/test_alchemy_ui.py` | `52`, `54`, `alchemy-games/`, `alchemy-stage/` (call their §12 interfaces if present, flat fallback if not) |
| **U2: games** | NEW `play/static/js/alchemy-games/*.js` (8); `play/static/js/table/33-bench-games.js` (**adds** the `REACTION` gauge and the colour-stage track; herb and forge games unchanged); NEW `play/static/css/alchemy-games.css`; `tests/test_alchemy_games.py` | `bench-games/`, `forge-games/` |
| **U3: stage** | NEW `play/static/js/alchemy-stage/*.js`, NEW `play/static/js/table/52-alchemy-stage.js` (global `window.AlchemyStage`); `play/static/js/bench-stage/01-gl.js` (**additive only**: `uFillY`, `uSurf`, `uTurbid` with no-op defaults); `tests/test_alchemy_stage.py` | `bench-stage/00,02-06`, `forge-stage/` |
| **U4: books and perks** | NEW `play/static/js/table/54-alchemy-books.js`; `play/static/js/table/21-tab-journal.js` (the codex section); `play/static/js/table/36-bench-perks.js` (the `alchemist` track entry); `tests/test_alchemy_books_ui.py` | |
| **U5: sound** | `play/static/js/sound.js` (the `alchemy` bus and its events), `play/static/js/prefs.js`, `play/templates/play/home.html` (the Alchemy volume); `tests/test_alchemy_sound.py` | |

Script and link tags for U2 to U5 go in `table.html`, which U1 owns. Those lanes report the exact
tags they need, and U1 (or the lead at merge) adds them.

---

## 12. Interfaces between the UI lanes

**Games (U2 provides, U1 calls).**
- Each game registers on `window.BenchGameDefs[method]` with `track: "alchemy"`, exactly as the
  forge games do.
- `BenchGames.play(method, opts)` runs it.
- Alchemy games receive:
  - `opts.heat`, for Calcine, Distill and Sublime: the forge's shape, plus `bands: [{name, lo,
    hi}]` so the gauge prints "heads, hearts, tails";
  - `opts.reaction`: `{start, band: [lo, hi], rise, settle, flare_at}`;
  - `opts.stages`: for Transmute, `["nigredo", "albedo", "citrinitas", "rubedo"]` with
    per-stage windows.
- Every one comes from the server's check response. The score reports 0..1 as today.

**Stage (U3 provides, U1 calls).** `window.AlchemyStage` mirrors `ForgeStage`:

```
available() mount(host) unmount()
setScene({kind: "kit" | "town" | "owned", biome, roofed, minute})
setTool(method)
setVessel({id, kind, liquid: {color, level, turbidity}, receiver?: {color, level}})
liquid({color, level, turbidity}, ms)          // animate to a server-sent state
heat(celsius) reaction(value)                   // drive flame and churn during a game
game(method) flourish(kind)                     // kind: "tier", "flawless", "land", "fail", "flare", "found"
productRect() reducedMotion(bool)
```

Without WebGL every call is a no-op and `available()` is false. U1 then shows the flat icon stage
with a CSS level bar.

**Books (U4 provides, U1 calls).** `window.AlchemyBooks`:
- `.card(materialId, anchorEl)`;
- `.formulary(host)`;
- `.codex(host)`.

They read `GET api/alchemy/codex`, `GET api/alchemy/formulary` and
`GET api/alchemy/material/<id>`.

**Sound (U5 provides).** `Sound.play("alchemy.<event>", {pitch?})` for every event in UI §11.
Unknown events are silent, so callers never guard.

---

## 13. Every lane

- **Search first** for prior art on anything not settled by `docs/alchemy-prior-art.md` or the
  plans' §22. Cite primary sources.
- **Load the `states-effects-tells` skill** before touching `sheet.py`, `engine.py`,
  `activeeffect.py`, `consumables.py` or `effectspec.py`. Run `tests/test_three_laws.py`.
- **Tests document the defect they prevent**, named in the docstring with the measurement (plan
  §20.1 lists them).
- **Run the whole suite** (`python -m pytest -n auto -p no:cacheprovider -v`, then check the exit
  code; never `-q`). Do not edit `.py` files while it runs.
- **Grep every copy** when a rule changes. The old method words live in at least ten files (plan
  §15.4).
- **Live checks only on scratch data** (`PATHFINDER_GM_DATA`), never `%LOCALAPPDATA%\PathfinderGM`.
- **Commit on your lane branch with named paths** (`git add <file>`, never `-a`). Report:
  - what was built;
  - the test counts;
  - anything measured;
  - anything not done, including **every `permission.*` tag or `when` clause that no reader asks
    yet**.

---

## 14. Answers the lanes are waiting on

From plan §21. A lane that reaches one of these stops and asks; it does not choose.

| Open point | Blocks |
|---|---|
| 1 (the essence vocabulary) | lane D's essences, lane E's derivation table |
| 2 (the stacking switch's reach) | lane C's `dice.stack` merge |
| 3 (house splash) | lane F's `build` for house splash flasks |
| 4 (experiment against writings) | lane E's experiment rule |
| 5 (harmful spells in potions) | lane E's derived rows for harmful spells |
| 6 (quality and spell potion price) | lanes E and H |
| 7 (city laboratories) | lane G's guaranteed rows |
| 8 (the light model's reach) | lane C, beyond miss chance |
| 9 (learning from a potion) | lane E's `learn(from="potion")` |
| 10 (the Transmute flag ratio) | lane D's review table |
| 11 (icons) | lane U1's download |
| 12 (the extract list) | nothing; recorded |
