# Enchanting revamp: lane contracts

Written 2026-10-05, before any lane starts. The plans are `docs/enchanting-revamp-plan.md`
(rules, data, engine, the shared In-progress section and material tag) and
`docs/enchanting-ui-plan.md` (interface). This file fixes the **shapes that cross lanes** and
**who owns which file**, so the lanes can run in parallel without writing over each other. A lane
that needs a shape changed asks the lead; it does not change it locally. Same rules as
`docs/blacksmithing-contracts.md`, which this mirrors.

Integration branch: **`enchant/revamp`**, off master at the commit the lead names when wave 1
starts (on 2026-10-05 local master is 1f88ada and origin/master e028885; local master is not
pushed). Every lane starts with `git switch -c lane/enchant-<letter> enchant/revamp` in its own
worktree and never touches another lane's files.

---

## 1. File ownership (wave 1: rules, data, engine, shared infrastructure)

| Lane | Owns (may create and edit) | Reads only |
|---|---|---|
| **A: vocabulary** | `rules/effectspec.py`; **`content/rules/magic-properties.json` (new)**; `tests/test_enchant_vocabulary.py` | |
| **B: layer and tags** | **`rules/magic_layer.py` (new)**, `rules/forge_items.py`, **`rules/item_tags.py` (new)**, `rules/armour.py`, `rules/states.py` (the `material.*` family only), **`content/rules/base-pieces.json` (new)**; `tests/test_magic_layer.py`, `tests/test_item_tags.py` | `rules/materials.py`, `rules/effectspec.py`, `rules/crafting.py` (the §8 `Stock` fields) |
| **C: engine readers** | `rules/sheet.py`, `rules/engine.py`, `rules/activeeffect.py`, `rules/intents.py`, the op enum and its validator in `gm/` (only for `use_item`); `tests/test_enchant_engine.py`, `tests/test_counts_as_magic.py`, `tests/test_item_powers.py` | `rules/magic_layer.py`, `rules/forge_items.py`, `rules/inprogress.py` |
| **D: data pass** | `content/materials/enchanter-materials.json`, `content/materials/magic-items.json`, `rules/materials.py`, `tools/enchant_*.py` (new), **`docs/enchanting-review.md` (new)**; `tests/test_enchant_materials.py` | `rules/effectspec.py`, `content/rules/magic-properties.json` |
| **E: bench rules and API** | `rules/enchanter.py`, `rules/magicitem.py`, `rules/benches.py`, `content/world-classes/enchanter.json`, `rules/worldclass.py`, **`play/enchant_views.py` (new)**, `pathfindergm/urls.py` (**enchant routes only**); `tests/test_enchanter.py` (rewritten), `tests/test_magicitem.py`, `tests/test_enchant_bench.py`, `tests/test_enchant_api.py` | `rules/magic_layer.py`, `rules/curses.py`, `rules/knowledge.py`, `rules/inprogress.py`, `rules/sky.py`, `rules/places.py` |
| **F: curses, identify, unbind** | **`rules/curses.py` (new)**, **`content/rules/curses.json` (new)**, `rules/knowledge.py`, `rules/goods.py`, **`content/rules/enchanting-manuals.json` (new)**; `tests/test_curses.py`, `tests/test_enchant_knowledge.py` | `rules/magic_layer.py`, `rules/materials.py` |
| **G: In progress and sky** | **`rules/inprogress.py` (new)**, **`rules/sky.py` (new)**, `rules/crafting.py` (the `Stock` fields of §8 and steeping), `play/bench_views.py` (only `_ready`'s steeping call), **`play/works_views.py` (new)**, `pathfindergm/urls.py` (**works routes only**); `tests/test_inprogress.py`, `tests/test_sky.py` | |

Nobody but the owner edits an owned file. `tests/test_three_laws.py`, `tests/conftest.py` and
`.claude/launch.json` are **owned by nobody in this wave**: do not commit them. A lane that needs
a dev server adds a local launch entry and leaves it uncommitted.

**`pathfindergm/urls.py`** is shared by E and G in separate blocks, as the forge's lane D held
"forge routes only": each adds its own block **above** any catch-all, and the lead joins them at
merge.

**`Scene.advance`** lives in `rules/engine.py` (lane C). Lane G provides `inprogress.settle`;
**lane C adds the one call** in `Scene.advance` and the "is ready to collect" line (§9).

**Wave 2** (after wave 1 merges): the UI lanes U1 to U7 and lane H (migration, World Bible).
Their ownership is §12 below, fixed now so wave 1 does not take their files.

---

## 2. The property vocabulary (lane A defines, everyone uses)

### 2.1 New effect types and fields in `rules/effectspec.py`

| Type | Fields |
|---|---|
| `crit_range` | `multiply` (int, 2), `not_with` (a tag prefix, `feat.improved-critical`) |
| `extra_attack` | `on` (`full_attack`), `count` (int), `not_with` (`spell.haste`) |
| `enhancement_to_ac` | `max` (`"enhancement"`); the amount is a per-turn choice param, validated by the engine |
| `fortification` | `percent` (25, 50, 75) |
| `ignore_armour` | `except` (creature types: `undead`, `construct`; `object`) |
| `item_power` | `spell` (a spell id in `content/spells`) **or** `effect` (one effect document), `uses` (`{"per": "day", "n": 1}` or `"at_will"`), `caster_level` (optional, defaults to the item's) |
| `deflect_ranged` | `per` (`round`), `save` (`{"reflex": 20}`) or `auto` (arrow catching) |

Additions to existing lists and fields:
- `STRIKES_AS` gains `magic`, `good`, `evil`, `law`, `chaos`.
- `ITEM_TRIGGERS` gains `wielded` and `worn` (a standing `ActiveEffect` granted while the item is
  held or worn and removed with it, the `carried` mechanism).
- `damage` gains `per_multiplier: bool` (a crit rider's dice step with the weapon's multiplier:
  ×2 1d10, ×3 2d10, ×4 3d10) and `recipient: "wielder"` (vicious).
- Any effect may carry `choice_key` naming a choice the property asks (`"foe"`, `"energy"`), and
  `when` may reference it: `{"target": {"choice": "foe"}}`. `_when_holds` resolves it against the
  property's stored choice (lane C).
- Any effect may carry `"book": true` (printed number, never scaled) as the forge's do, and
  `"house": true` (scaled by binding quality).

Each new type gets a validator, a renderer and a catalogue entry. `executable()` is True for all.
`narrative` stays legal in the vocabulary; **lane D's validator refuses it** in essences and
recipes.

### 2.2 `content/rules/magic-properties.json` (lane A writes, by hand from AoN)

One entry per book weapon and armour ability, keyed by id. **Every number is the book's**,
entered by hand from the AoN pages cited in the revamp plan §8 (no model authors one):

```json
{
  "id": "flaming", "name": "Flaming", "gear": ["weapon"],
  "plus": 1, "gp": null, "cl": 10, "tier": "rare",
  "spells": [["fireball", "flame-blade", "flame-strike"]],
  "requires": {"melee": false, "damage_types_any": null, "creator_alignment": null},
  "choice": null,
  "documents": [
    {"type": "damage", "dice": "1d6", "damage_type": "fire", "trigger": "hit", "book": true}
  ]
}
```

- `plus` (bonus equivalent) **or** `gp` (flat price, outside the +10), never both.
- `spells` is a list of alternatives groups: each inner list is "any one of these" (flaming: any
  of three). Each group not met is one +5 DC (revamp plan §4.2).
- `requires`: weapon restrictions (`melee`, `damage_types_any: ["piercing", "slashing"]` for keen,
  `ranged`, `thrown`), and `creator_alignment` (waived and noted until Q7).
- `choice`: `{"key": "foe", "of": "creature_type" | "subtype" | "damage_type", "options": [...]}`.
- All 26 weapon and 32 armour entries now in `magic-items.json` move here; their ids keep the
  `mi-` alias for old saves (lane H maps).

`effectspec.properties() -> dict[str, dict]` loads and validates the file; `effectspec.property(id)`.

---

## 3. The layer (lane B defines and serves)

### 3.1 The record field

A vessel record (the forge's contract §4 record, a leatherworker armour record, or one from
`record_for_base`) may carry `magic` (revamp plan §6.1):

```json
"magic": {
  "schema": 1,
  "enhancement": 1,
  "properties": [{"id": "bane", "essence": "bane-essence", "choice": {"foe": "undead"}}],
  "flat": [{"id": "shadow", "essence": "shadowstuff"}],
  "powers": [{"recipe": "mi-ring-protection-1"}],
  "binding": {"quality_index": 3, "level": 2, "perks": {"potency": 0}},
  "curse": null,
  "known": {"intent": true, "curse": false, "how": "made"},
  "uses": {"<power id>": 0},
  "made_day": 41
}
```

**Ids and choices only; never a computed number** (the read-live rule). `curse` is lane F's
curse record (§7), opaque to everyone but F and C.

### 3.2 API

```python
magic_layer.capacity(record, *, binder_perks: int = 0) -> dict
#   {"bonus": 8, "powers": None | 2, "cap": 10, "why": "Superior: holds +8"}
magic_layer.plan(record, adds: dict, *, binder, hurry: bool = False) -> dict
#   adds = {"enhancement": int, "properties": [{"id", "choice"}], "flat": [...], "powers": [...]}
#   binder = {"level": int, "perks": {...}, "knows": set[str] (spell ids), "holds": set[str]}
#   -> {"ok": bool, "problems": [str],             # refusals in words, before any roll
#       "total_bonus": int, "caster_level": int,
#       "dc_terms": [{"why": str, "dc": int}],      # 5 + CL, +5 per missing group, +5 hurry
#       "price": {"market_gp", "making_gp", "motes", "surcharges": [{"why", "motes"}],
#                 "hours", "days"},
#       "capacity": {...}, "needs": {"grants": [property ids], "motes": int}}
magic_layer.layer(record) -> dict
#   {"specs": [...], "riders": [...], "strikes_as": [...], "powers": [...],
#    "wielded": [...], "worn": [...], "aura": "moderate", "caster_level": int,
#    "total_bonus": int, "known": {...}, "problems": [...]}
magic_layer.write(record, adds: dict, *, binding: dict, curse: dict | None, day: int) -> dict
#   a new record dict; pure, never mutates
magic_layer.strip(record) -> tuple[dict, dict]     # (record without the layer, the layer): Unbind
```

`forge_items.build(record)` gains a `"magic"` key holding `magic_layer.layer(record)` when the
record has a layer, and merges its `specs` into `roll_specs`/`standing_specs`, its `riders` into
`riders`, and its `strikes_as` into `strikes_as`, so **every existing reader sees the layer
without a second door**. A record with no `magic` builds exactly as today (a test pins byte
equality on the forge fixtures).

```python
forge_items.record_for_base(base: str, *, gear: str, quality_index: int = 3,
                            pieces: dict | None = None) -> dict
#   a §4 record for a bought or found item, default pieces from content/rules/base-pieces.json
```

Maths fixed here (revamp plan §6.3-6.5, all **proposed** numbers live as module constants with
the plan's section in a comment): capacity Superior 8, Flawless 9, Flawless +1 and up 10, +1 per
Capacity pick, cap 10; weapons bonus² × 2,000, armour × 1,000; making cost half; motes = making
gp ÷ 100 rounded up; cold iron +20 motes on the first enhancement; noqual +50 (read from the
material's `enchant_surcharge_gp`); 8 hours per 1,000 gp of base price (the increment's),
minimum 8, halved when hurried; days = hours ÷ 8 rounded up.

### 3.3 Material tags

```python
item_tags.material_tags(thing) -> tuple[str, ...]
#   ("material.metal", "material.metal.cold-iron", "material.main.cold-iron",
#    "material.wood.ash", "material.leather.wolf-hide", ...)
item_tags.has_material(thing, prefix: str) -> bool      # states.matches, never ==
item_tags.main_material(thing) -> str | None
```

`thing` is a record, a `Stock`, an `ARMOUR`/weapon table key, or a worn slot string. The
`material.*` family is registered in `rules/states.py` so the one vocabulary knows it.
`armour.wears_metal(actor)` is rewritten on `has_material(..., "material.metal")` for the worn
suit and shield; `METAL_ARMOUR` and `METAL_SHIELDS` are deleted, and the inubrix clause test
keeps passing.

---

## 4. What lane C's readers promise

- Layered weapon records resolve through `Actor.weapon` and `_crafted_weapon` exactly as forged
  ones (the layer rides on the record). The layer's `+N` reaches attack and damage through the
  weapon scope (`_standing_mods` with `ctx["weapon"]["record"]`), and competes best-only with
  masterwork's +1.
- `Engine._item_riders` (`engine.py:11170`) reads `build["magic"]["riders"]` too; crit riders
  fire on a confirmed crit with `per_multiplier`; `recipient: "wielder"` riders hit the wielder.
- The threat test (`engine.py:5213`) reads `crit_range` (keen), refused with Improved Critical.
- `extra_attack` adds one attack to a full attack, not with haste; `enhancement_to_ac` takes a
  `defending` param from the combat bar (validated, never model-written); `fortification` rolls
  d% against a confirmed crit or sneak attack and says so; `ignore_armour` drops armour and
  shield bonuses from the target's AC except against its `except` list.
- **Counts as magic** (revamp plan §9): `layer()` emits the `strikes_as` traits; C makes the
  incorporeal rule real (`engine.py:5381`): no `magic` trait, no damage; magic, half; ghost
  touch, full. Ammunition from a `+1` or better projectile weapon carries `magic` and the bow's
  alignment traits.
- **Worn readers** for every worn record and catalogue slot item: `resistance`,
  `damage_reduction` (extended from the forged suit), `immunity` (refused at
  `Actor.apply_effect` with a tell), `sense` (tags in `standing_tags()`), `fast_healing` and
  continuous `spell_effect` (`worn` effects), `negative_level` (`wielded`/`worn`).
- **SR**: the cast path makes the caster level check (d20 + CL vs SR) against a target's
  `spell_resistance` from worn items and stat blocks, with a tell either way.
- **`use_item {item, power}`**: an op the engine validates; it runs the power's spell or effect
  through the cast door with `origin: item:<id>` and the item's CL, counts `magic.uses`, and
  `run_periodic("day")` resets the counts. Refused with the uses left named.
- **Bleed** from wounding: an `ActiveEffect` with `periodic: [{"damage": 1}]`, stacking `stack`.
- **`Scene.advance`** calls `inprogress.settle(actor, clock)` for every actor and appends
  "<name> is ready to collect" to `ended` (lane G's §8).
- Dancing and spell storing are **C2**, after the rest is merged.

---

## 5. The essence and recipe documents (lane D defines and serves)

`rules/materials.py` stays the one door (forge contracts §3). An essence normalises to:

```json
{"id", "name", "kind": "essence", "tier", "material", "form": "phial",
 "grants": {"property": "<id in magic-properties>"} | {"power": "<recipe id>"} | {"enhancement": 1} | null,
 "motes": int, "family": str, "planet": "mars", "polarity": "weapon" | "armour" | "ward" | "any",
 "affinity": [material ids], "house": [effects, each "house": true], "working": [{"type": "working", "trait"}],
 "color": "#rrggbb", "obtain", "price_gp": motes * 100, "biomes", "from_creature", "text"}
```

```python
materials.essences() -> dict[str, dict]
materials.recipes() -> dict[str, dict]          # the 112 wondrous items, as revamp plan §7.4
materials.recipe(recipe_id) -> dict | None
materials.validate(doc) -> list[str]            # adds: >= 3 traits, no narrative, grants resolve,
                                                #   price_gp == motes * 100, house within ceilings
materials.HOUSE_CEILING   # {"common": 1, "uncommon": 1, "rare": 2, "exotic": 2, "legendary": 3}
```

**Ids, names and kinds do not change** (old saves and recipes name them). Vessel entries are
retired from the shelf (`kind: vessel` kept loadable, never offered). Working traits added to
`effectspec.WORKING_TRAITS` by **lane A** on D's request: `night_only`, `eager`, `skittish`,
`heavy`, `volatile`, `pure` (already present).

---

## 6. Bench rules and API (lane E serves, wave 2 UI consumes)

Methods (revamp plan §10): `prepare, attune, bind, refine, unbind, cleanse, read, identify`.
Levels, perks (`potency`, `quality`, `yield`, `capacity`), ceilings, the check (three terms, no
naturals), the DC through `magic_layer.plan`, the failure table (plan §10.1), quality capped by
Prepare and Attune + 1, places through `places.for_scene` (a sanctum tag; a hired circle's rent
through `market.forge_rent`'s shape).

Routes, mirroring `play/forge_views.py`, registered **above any catch-all** (`test_bench_routes`):

| Route | Does |
|---|---|
| `GET api/enchant/state` | the shelf (vessels with capacity, intermediates, essences with colours, circle materials, this craft's In-progress rows), methods with locks and reasons, where you are, level, perks banked, ceiling, `hour` (`sky.hour_at`) |
| `POST api/enchant/check` | `{method, vessel, seats: {seat: essence}, choices: {key: value}, circle: [ids], catalyst, hurry, recipe?}` → `{fits, seats (with signs), problems, can_roll, info, dc, dc_terms, bonus, terms, need, lines: {miss_small, miss_big}, plan (magic_layer.plan), ceiling, tiers, hour, minutes}` |
| `POST api/enchant/roll` | `+ face` → `{roll, verdict: "success" | "failure" | "flawed", lost, minutes, token?, tuning?, said?, clock}` |
| `POST api/enchant/finish` | `{token, score, stopped}` → `{tier, tier_name, products: [{key, name, form, item, record?, layer?, card?}], work?: <inprogress row>, mastery, discoveries, minutes, state}` |
| `POST api/enchant/read` | `{essence}` → `knowledge.read` |
| `POST api/enchant/identify` | `{item}` → the roll mat's shown terms, then `knowledge.identify` |
| `POST api/enchant/wait` | `{planet}` → advances the clock through `Scene.advance` to the next hour of it |
| `POST api/enchant/perks` | pick perks |
| `GET api/enchant/ledger`, `GET api/enchant/essence/<id>`, `GET api/enchant/recipes` | ledger, one card, known recipes |

`verdict: "flawed"` is the only new verdict word; the page shows FLAWED and never the curse.
**The page never computes a number.**

Bind's `finish` calls `inprogress.begin` with `craft: "enchanter"` and the vessel's stock key;
the layer is written at **collect** (`inprogress.CRAFTS["enchanter"].collect`, registered by E).

---

## 7. Curses, identify, unbind (lane F serves)

```python
curses.roll(dice, record, layer_plan) -> dict
#   {"d100": 27, "row": "opposite" | "delusion" | "intermittent" | "requirement" | "drawback"
#            | "different" | "specific", "detail": {...}, "tags": ["curse.opposite"], "cl": int}
curses.documents(curse, layer: dict) -> dict      # how the layer is changed: {"replace" | "add" | "suppress" ...}
curses.describe(curse) -> str                     # words for the identify card; never sent unless known
curses.ROWS                                        # from content/rules/curses.json, the refused rows marked
```

The engine (lane C, through `magic_layer.layer`) asks `curses.documents` and applies them; the
page never receives a curse it does not know (a test sweeps every state and API response for the
curse's id while `known.curse` is false).

```python
knowledge.read(actor, essence_id, total: int, *, clock: int) -> dict
#   {"revealed": [key], "cost": {"phial": 0.1}, "minutes": 10, "danger": effect | None}
knowledge.identify(actor, item, total: int, *, day: int) -> dict
#   {"result": "fail" | "intent" | "curse", "learned": [key], "recipe": id | None,
#    "dc": int, "again_on_day": int}   # once per item per day: a second try returns the first result
knowledge.unbind(actor, record) -> dict
#   {"learned": [property type keys], "recipe": id | None, "residue": {"arcane-residue": n}}
knowledge.learn_by_use(actor, item_id, key) -> bool    # the hard way (revamp plan §12.2); C calls it
```

One store, as the forge's lane E: `Actor.herb_known`, keyed by material and recipe id (ids are
disjoint; `test_alchemist.py:601` pins cross-file uniqueness, extended to recipes). Item
knowledge lives on the item's own `magic.known`.

Manuals: `content/rules/enchanting-manuals.json`, a goods table beside the herbal and smithing
manuals.

---

## 8. In progress and sky (lane G serves, every craft uses)

### 8.1 `Stock` fields (lane G adds to `rules/crafting.py`)

Defaulted and written by `as_dict` only when set (old saves round-trip byte for byte):
- `magic: dict | None`: the layer on a stock-kept vessel (lane B reads and writes it through
  `magic_layer`).
- `work: dict | None`: the In-progress block:

```json
{"craft": "enchanter", "label": "Binding a +1 flaming longsword",
 "started": 57600, "minutes": 11520, "where": "carried" | "place:<id>",
 "state": "working" | "ready", "result": { ...craft-owned, never sent to the page... }}
```

`ready_minute` stays the countdown's end (`started + minutes`), so herbalism's existing readers
keep working. `how` gains `"in_progress"`; `"steeping"` stays an accepted alias.

### 8.2 API

```python
inprogress.register(craft: str, *, collect, cancel, icon: str, limit: int | None = None) -> None
inprogress.begin(actor, stock_key, *, craft, minutes, now, where="carried", label, result) -> dict
inprogress.entries(actor, now, *, here: str | None = None, craft: str | None = None) -> list[dict]
#   [{"key", "craft", "icon", "name", "label", "where", "where_words", "state",
#     "ready_at", "ready_in", "ready_day", "ready_words", "fraction",
#     "can_collect": bool, "why_not": str | None, "can_stop": bool, "stop_words": str}]
#   ready first, then working by soonest; every number and word computed here
inprogress.settle(actor, now) -> list[str]        # names that became ready since last settle
inprogress.collect(actor, key, *, now, here) -> dict    # {"ok", "said", "product": {...}} or {"ok": False, "why"}
inprogress.cancel(actor, key, *, now) -> dict
inprogress.summary(actor, now) -> {"ready": int, "working": int, "next": {"name", "ready_words"} | None}
```

Herbalism registers `herbalist` (collect lifts `in_progress` and the jar is the tincture it
always was); `settle_steeping`'s silent lift is retired for the ready state and Collect; old jars
past their minute load as ready.

Routes (lane G, works block of `urls.py`): `GET api/works` → `{rows, summary}`;
`POST api/works/collect {key}`; `POST api/works/cancel {key}`. The table's own state carries
`works: inprogress.summary(...)` so the door's count renders without a fetch (**the field is
added by U4** in the table state view, wave 2).

### 8.3 Sky

```python
sky.PLANETS            # ("saturn", "jupiter", "mars", "sun", "venus", "mercury", "moon"), Chaldean order
sky.planet_of_day(day: int) -> str                # day 1 the Sun's, then the weekday order
sky.hour_at(clock_minutes: int) -> dict           # {"planet", "starts", "ends", "day": bool}
sky.next_hour(planet: str, clock_minutes: int) -> int    # minutes until it begins (0 if now)
sky.words(clock_minutes, planet) -> str           # "Mars hour, 42 minutes left" / "Mars hour in 3 hours"
```

Dawn 06:00, dusk 18:00, 60-minute hours (revamp plan §17), read from one constant pair so a world
with seasons changes one place.

---

## 9. Every lane

- **Search first** for prior art on anything `docs/enchanting-prior-art.md` does not settle, and
  cite it in the docstring.
- **Tests document the defect they prevent**, named in the docstring (revamp plan §21.1 lists
  each lane's).
- **Run the whole suite** (`python -m pytest -n auto -p no:cacheprovider -v`, check the exit
  code; never `-q`), and do not edit `.py` files while it runs.
- **Three laws**: run `tests/test_three_laws.py`; load the `states-effects-tells` skill before
  touching `sheet.py`, `engine.py` or `activeeffect.py`.
- **Live checks** only on scratch data (`PATHFINDER_GM_DATA`), never `%LOCALAPPDATA%\PathfinderGM`.
- **No model authors a number**: book numbers by hand from AoN (cite the page in the data file's
  `source`), house numbers inside validator fences.
- Commit on your lane branch with named paths (`git add <file>`, never `-a`), and report: what was
  built, the test counts, anything measured, anything not done.

---

## 10. Order and joins

| Lane | Starts when | Joins |
|---|---|---|
| A, G | at once | |
| B | A merged | needs G's `Stock.magic` field: B may stub it locally, never commit it |
| C | A and B merged | adds G's `settle` call |
| D | A merged | |
| E | B and D merged (F's API stubbed until F lands) | registers `enchanter` with G |
| F | B merged | |
| C2 | C merged | dancing, spell storing |

---

## 11. What is not in this wave

Wands, staves and scrolls (the owner: a later pass); intelligent items; the spells that read the
material tag (heat metal, chill metal, rusting grasp, shocking grasp) and the druid's metal rule
(the leatherworking plan); jewellery shapes at the forge and leather vessels' `slot` (cross-craft
asks in revamp plan §20); player alignment (Q7).

---

## 12. File ownership (wave 2, fixed now)

| Lane | Owns | Reads only |
|---|---|---|
| **U1: shell and old tab** | NEW `play/static/js/table/45-enchant-shell.js`, `46-enchant-shelf.js`, `48-enchant-working.js`; NEW `play/static/css/enchant.css`; `play/templates/play/table.html` (the `#enchant` layer, its script and link tags, the Enchanting button, and the tags other U lanes report); `play/templates/play/craft.html` (the Enchanting card, the mode row removed); `play/enchant_views.py` (response fields the page needs); `tests/test_enchant_ui.py` | `47-enchant-stage.js`, `49-enchant-ledger.js`, `37-works.js`, `enchant-games/` (their §13 interfaces, flat fallback if absent) |
| **U2: games** | NEW `play/static/js/enchant-games/*.js` (prepare, attune, bind, refine, unbind, cleanse); `play/static/js/table/33-bench-games.js` (the optional hour band; herb and forge games unchanged); NEW `play/static/css/enchant-games.css`; `tests/test_enchant_games.py` | `bench-games/`, `forge-games/` |
| **U3: stage** | NEW `play/static/js/enchant-stage/*.js`, NEW `play/static/js/table/47-enchant-stage.js`; `tests/test_enchant_stage.py` | `bench-stage/`, `forge-stage/` (reuse `02-families.js`, `03-smithy.js` as is) |
| **U4: In progress** | NEW `play/static/js/table/37-works.js`, NEW `play/static/css/works.css`; `play/static/js/table/31-bench-satchel.js` (its Steeping group becomes `Works.group`); `play/static/js/table/41-forge-rack.js` (the group, for future forge work); the table state view (the `works` summary field only); `tests/test_works_ui.py` | `rules/inprogress.py` |
| **U5: ledger, identify, perks** | NEW `play/static/js/table/49-enchant-ledger.js`; `play/static/js/table/36-bench-perks.js` (the `enchanter` row); `play/static/js/table/21-tab-journal.js` (Essences and recipes section); `play/static/js/table/17-tab-sheet.js` and `18-tab-equipment.js` (the item card's magic section and Identify); `tests/test_enchant_ledger_ui.py` | |
| **U6: sound** | `play/static/js/sound.js` (the `enchant` bus, `works.*` events), `play/static/js/prefs.js`, `play/templates/play/home.html` (the Enchanting volume); `tests/test_enchant_sound.py` | |
| **H: migration and World Bible** | `rules/sheet.py` load path (after C merges), `rules/enchanter.py` (old-record migration only), `rules/worldclass.py` (`migrate_enchanter`), `docs/campaign-format.md`, `docs/from-world-bible.md`; `tests/test_enchant_migration.py` | |

Script and link tags for U2 to U5 go in `table.html`, which U1 owns: those lanes report the exact
tags they need and U1 (or the lead at merge) adds them.

## 13. Interfaces between the UI lanes

**Games (U2 provides, U1 calls).** Each registers on `window.BenchGameDefs[method]` with
`track: "enchant"`, as the forge games do; `BenchGames.play(method, opts)` runs it. Enchant games
receive `opts.hour`: `{planet, sign, inside: bool, minutes_left, widen}` and `opts.seq` (Prepare,
Unbind, Cleanse: the glyph sequence the server sent) or `opts.seats` (Attune: `[{seat, sign,
essences}]`), and report the score 0..1. The hour band is part of the strip frame.

**Stage (U3 provides, U1 calls).** `window.EnchantStage` as the UI plan §7.1. Without WebGL every
call is a no-op and `available()` is false; U1 shows the flat icon stage.

**In progress (U4 provides, every bench calls).** `window.Works.open(anchorEl?)`,
`Works.close()`, `Works.group(host, craft)` (the shelf group, re-rendered from state),
`Works.refresh(summary)` (the door's count). Rows come from `GET api/works`; Collect and Stop post
to lane G's routes and dispatch `works:collected` with the product key, which a bench listens for
to fly the row.

**Ledger (U5 provides, U1 calls).** `window.EnchantLedger.card(essenceId, anchorEl)`,
`EnchantLedger.recipes(host)`, `EnchantLedger.journal(host)`, reading lane E's ledger routes.

**Sound (U6 provides).** `Sound.play("enchant.<event>", {planet})` and `Sound.play("works.ready")`;
unknown events are silent, so callers never guard.
