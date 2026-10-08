# Leatherworking revamp: lane contracts

Written 2026-10-05 by the lead, before any lane starts. The plans are
`docs/leatherworking-revamp-plan.md` (rules, data, engine; cited **plan §n**) and
`docs/leatherworking-ui-plan.md` (interface; cited **UI §n**). This file fixes the **shapes that
cross lanes** and **who owns which file**, so the lanes can run in parallel without writing over
each other. It follows `docs/blacksmithing-contracts.md`, whose shapes (the material document,
the crafted-item record, `forge_items.build`) this craft builds into and does not redefine. A lane
that needs a shape changed asks the lead; it does not change it locally.

Integration branch: **`leather/revamp`**, off master (1f88ada or later, with the forge merged).
Every lane starts with `git switch -c lane/leather-<letter> leather/revamp` in its own worktree and
never touches another lane's files.

**Dependency outside this craft.** The **In progress** section and the **metal tag** are built
first by the Enchanting lanes (§6). Lanes here consume them through the named interfaces below. If
the Enchanting contracts fix a different shape, **theirs wins**: the one call site in each lane
adapts, and the lead updates §6 here.

---

## 1. File ownership (wave 1)

| Lane | Owns (may create and edit) | Reads only |
|---|---|---|
| **A: vocabulary** | `rules/effectspec.py`; `tests/test_leather_vocabulary.py` | |
| **B: engine readers** | `rules/forge_items.py`, `rules/sheet.py`, `rules/engine.py`, `rules/tables.py`, `rules/armour.py`, `rules/crafting.py` (**only** `from_stock_dict`'s `base` writer, plan §13.1); `tests/test_leather_engine.py`, `tests/test_leather_items.py`; re-pins `tests/test_aggregator.py:321` | `rules/materials.py` (§3 API) |
| **C: harvest** | NEW `rules/harvest.py`, NEW `rules/deeds.py`, NEW `tools/harvest_tags.py`, `content/bestiary/*.json` (the `tags` field only), `rules/herbprep.py` (the salt reader only), NEW `play/harvest_views.py`, `pathfindergm/urls.py` (harvest routes only), the four `ACQUISITION` carcass rows in `rules/blacksmith.py`, `rules/alchemist.py`, `rules/enchanter.py`, `rules/leatherworker.py` (removal only); `tests/test_harvest.py`, `tests/test_harvest_tags.py` | `rules/materials.py`, `rules/bestiary.py`, `rules/states.py` |
| **D: data pass** | `content/materials/leatherworker-materials.json`, `content/materials/blacksmith-materials.json` (**only** `leather-grip`, `sharkskin-grip`, `dragonhide-grip`, `angelskin-binding`, and `ferrous` on the iron-family metals), `rules/materials.py`, NEW `tools/leather_*.py`, NEW `docs/leatherworking-review.md`; `tests/test_leather_materials.py`; re-pins `tests/test_forge_materials.py:110` | `rules/effectspec.py` |
| **E: bench rules** | `rules/leatherworker.py`, `content/world-classes/leatherworker.json`, `rules/worldclass.py`, NEW `play/leather_views.py`, `pathfindergm/urls.py` (leather routes only); `tests/test_leatherworker.py` (rewritten, plan §23.1), `tests/test_leather_bench.py`, `tests/test_leather_api.py` | `rules/materials.py`, `rules/forge_items.py`, `rules/knowledge.py`, `rules/harvest.py`, the §6.1 interface |
| **F: knowledge** | `rules/knowledge.py`, `rules/goods.py`, NEW `content/rules/leatherworking-manuals.json`; `tests/test_leather_knowledge.py` | `rules/materials.py` |
| **G: tannery places** | `rules/places.py`, `rules/market.py`, `rules/outskirts.py` (the tannery placement only); `tests/test_leather_places.py` | `content/people/occupations.json` |

`tests/test_three_laws.py`, `tests/conftest.py` and `.claude/launch.json` are **owned by nobody in
this wave**: do not commit them. A lane that needs a dev server adds a local launch entry and leaves
it uncommitted.

**Wave 2** (after wave 1 merges): H (forge hand-off), M (metal readers, after the Enchanting metal
tag lands), I (migration), W (World Bible docs), and the UI lanes U1 to U7. Their ownership is §11.

---

## 2. The effect vocabulary (lane A defines, everyone uses)

Added to `rules/effectspec.py` with validators, renderers and catalogue entries, in the forge's
pattern (forge contracts §2: `gear_mod` sign convention, `bonus_type: material`, `book`, `trigger`):

| Addition | Shape | Read by |
|---|---|---|
| `object_immunity` (new type, object category) | `{"type": "object_immunity", "target": "<energy>"}`; target ∈ acid, cold, electricity, fire, sonic | lane B: `Item.take_damage`, `Engine._object_damage` |
| `gear_mod` target `enchant_cost_pct` | `{"type": "gear_mod", "target": "enchant_cost_pct", "amount": -25, "applies_to": "energy_resistance"}`; `applies_to` from a small list the Enchanting lanes extend | the Enchanting cost reader (§6.3) |
| `as_base` (new type) | `{"type": "as_base", "target": "studded leather"}`: the suit takes that table row's statistics with no metal (bulette leather) | lane B |
| `WORKING_TRAITS` gains | `thick`, `fast_tan`, `slow_tan`, `ceiling_up`, `ceiling_down`, `salt_proof`, `tans_white`, `supple`, `fills_tooling`, `strong_seam`, `weatherproof`, `fine_pitch`, `fast_colour`, `fugitive`, `rancid` | lanes E, D |

`executable()` is True for all of them. `narrative` stays legal in the vocabulary but lane D's
validator refuses it in leather documents.

---

## 3. The material document (lane D defines and serves)

`rules/materials.py` stays the one door to every craft material (forge contracts §3). Lane D
extends it:

```python
materials.KINDS          # + "hide", "tannin", "oil", "wax", "thread", "dye"
materials.STRUCTURAL     # + "hide"
materials.GEARS          # + "shield", "worn"
materials.is_judged(doc) -> bool        # replaces is_forge's early return for the leather catalogue
materials.validate(doc) -> list[str]    # hides as structural, the leather consumables as consumables
materials.grip_capable(doc) -> bool     # "haft" in doc["pieces"].get("weapon", [])
materials.is_salt(doc) -> bool          # curing-salt, or "salt": true
```

The hide document (plan §14.2) adds to the forge's normalised shape, every field defaulted:

| Field | Type | Default |
|---|---|---|
| `pieces.shield`, `pieces.worn` | list of piece names | `[]` |
| `shield` | effect list (else `armour` is read, as `forge_items` already falls back) | `[]` |
| `mark` | one effect, consumables only (generalises the forge's `quench_mark`, which stays read) | `null` |
| `surface` | `fur`, `scale`, `smooth`, `feather`, `chitin`, `shell` | `"smooth"` |
| `color` | `#rrggbb` | the kind's default |
| `allowed_bases` | table keys | `[]` (any) |
| `always_masterwork` | bool, with `book: true` | `false` |
| `druid_permitted` | bool, book | `false` |
| `ferrous` | bool (metal documents) | `false` |
| `salt` | bool (treatments) | `false` |
| `tannage` | tannins only: `brain`, `alum`, `bark`, `mineral`, `planar` | `null` |

Validator rules, each refusal naming the fix: a hide has ≥3 `armour` effects with ≥1 negative; a
`weapon` list only when grip-capable, then ≥3 with ≥1 negative; house amounts within `TIER_CEILING`
and at least `HOUSE_FLOOR` (2); combat, save and skill mods typed `material`; no `narrative`; every
material ≥1 working trait and ≥3 discoverable properties; consumables carry no `armour` or `weapon`
lists and at most one `mark`. **Ids and names do not change** (tests pin them), except the forge's
four leather pieces, which keep their ids and gain a `material` link to their leather parent.

---

## 4. Records (lane B computes, lanes C and E write)

### 4.1 Hide stock (lanes C and E write; every lane reads)

Every hide and every intermediate is a stock record in `pc.stock`, never a bare satchel count:

```json
{
  "id": "winter-wolf-pelt", "kind": "leather-stock", "craft": "leatherworker", "count": 1,
  "material": "winter-wolf-pelt", "form": "green",
  "units": 2.0, "grade": 2, "tannage": null, "passes": 0, "marks": [],
  "quality_index": null, "hardened": false,
  "harvested_at": 20160, "salted": false, "salted_at": null,
  "creature": "winter-wolf", "schema": 1
}
```

- `form` ∈ `green`, `salted`, `pelt`, `leather`, `fur`, `rawhide`, `panel`, `plate`, `lacing`,
  `grip`, `scales`, `scrap`.
- `units` in quarters. `grade` 1 to 4 (0 = reject, scraps only).
- `creature` is the bestiary id (or world creature id) a **generic** hide was taken from; the
  generic hide's inherited numbers are derived from it on read (plan §5.4), never stored.
- Freshness is computed on read from `harvested_at` / `salted_at` (48 h green, 6 weeks salted,
  plan §6); lane C serves `harvest.freshness(stock, now) -> {"spoiled": bool, "hours_left": int,
  "why": str}`.

### 4.2 The crafted record and the build (lane B serves; lanes E and H write)

The forge's record (forge contracts §4) with `craft: "leatherworker"`, as plan §13.1. Lane B
extends `forge_items` without changing any existing number:

```python
forge_items.build(record) -> dict        # unchanged shape; now also:
#   masterwork True when the main piece's doc is always_masterwork (book), whatever the tier
#   marks: each material in record["marks"] contributes its doc's `mark`, once, unscaled,
#          listed under build["marks"] = [{"material": id, "effect": {...}}]
#   gear "worn": pieces body/lining; reads `armour` minus ac/acp/max_dex/asf targets
#   allowed_bases: a problem string when the base is not allowed for the main piece
#   as_base: the table row named replaces `base` for statistics
forge_items.PIECES["worn"] == ("body", "lining")
forge_items.MAKER_KEYS == ("smith", "maker")   # read either; writers use "smith" for now
```

The record stores ids, passes, grades and marks, never computed numbers (the read-live rule).
`base` is always a `tables.ARMOUR` / `tables.SHIELDS` key; lane B adds the rows `quilted cloth`,
`leather lamellar`, `horn lamellar`, `armored coat`, `steel lamellar` and the shield `madu`, and
the alias `hide` → `hide armour` in `armour._ALIASES`.

### 4.3 What lane B's readers promise

- A leather suit record in the armour slot reaches `armour_stats()` through `armour_row(base,
  build(rec))`; a shield record through `shield_stats()`.
- The engine's `wear` op dons a leather record by id; the `/api/wear` path without an `op` routes
  crafted records through it.
- `resistance()` reads every worn crafted record's build (suits, shields and `worn` goods), not
  only the suit.
- `object_immunity` is honoured by `Item.take_damage` and `_object_damage`.

---

## 5. Harvest (lane C serves; lanes E and U2 use)

### 5.1 The tag grammar

As plan §5.3, fixed here. Tags live in a stat block's `tags` list (read into standing tags at
`rules/sheet.py:3421`). One branch per craft:

```
harvest.hide.<material-id>          harvest.hide.generic.<surface>
harvest.horn.<material-id>          harvest.bone.<material-id>         harvest.sinew
harvest.scales.<material-id>        harvest.plan.<quadruped|long|winged|serpent|carapace>
harvest.blood.<material-id>         (forge)
harvest.reagent.<ingredient-id>     (alchemy)
harvest.essence.<material-id>       (enchanting)
harvest.part.<ingredient-id>        (herbalism)
body.metal                          (made of metal: shocking grasp, rusting grasp)
```

Which tags each craft owns: the forge, alchemy, enchanting and herbalism rows are **mapped by lane
C** from those crafts' current carcass pools (`rules/blacksmith.py:337` salvage, `rules/alchemist.py:343`
harvest-reagents, `rules/enchanter.py:653` reliquary-harvest), by creature id, by hand, in the same
reviewed table; the crafts' owners review their rows.

### 5.2 The API

```python
harvest.parts(creature, actor, *, now: int) -> list[dict]
#  one row per harvestable part for the crafts `actor` has:
#  {"key": "hide:winter-wolf-pelt", "craft": "leatherworker", "material": "winter-wolf-pelt",
#   "form": "green", "skill": "survival", "dc": 20, "units": 2.0, "minutes": 20,
#   "deed": "deed.harvest.good-outsider" | None, "taken": None | minute,
#   "game": "harvest" | None}
harvest.harvestable(creature, *, now) -> tuple[bool, str]    # dead under 24 h, not humanoid
harvest.take(actor, creature, key, roll_total: int, score: float | None, *, now, scene) -> dict
#  {"ok": bool, "stock": [record, ...], "grade": int | None, "lost": str, "deed": {...} | None,
#   "salt_spent": int, "tells": [...]}
harvest.generic_for(creature) -> str | None                  # the generic hide id, plan §5.3 rule
harvest.inherited(creature) -> list[effect]                  # plan §5.4, derived in code
harvest.freshness(stock, now) -> dict                        # §4.1
harvest.validate_tags(block) -> list[str]                    # humanoid, unknown material, wrong dragon colour
```

Engine op `harvest` (the gate and applicator belong to the engine). Routes, registered above any
catch-all: `GET api/harvest/<creature_ref>` (the rows) and `POST api/harvest/take` (`{creature,
key, roll, score}`). The carcass keeps `harvested: {key: minute}` and `died_at` on the scene actor.

### 5.3 Salt

```python
herbprep.has_salt(actor) -> bool         # rewritten over materials.is_salt by id and kind,
                                         # not name fragments; herbalism's callers unchanged
harvest.salt_measures(actor) -> int      # how many measures of curing salt are carried
```

### 5.4 Deeds

The smallest store a future renown or alignment system can read (plan §5.6). Lane C owns it:

```python
deeds.record(actor, tag: str, *, minute: int, place: str | None, subject: str | None,
             witnesses: list[str]) -> dict
deeds.of(actor, prefix: str = "deed.") -> list[dict]
Actor.deeds: list[dict]     # append-only; serialised with the actor; defaults to []
```

Tags begin `deed.`; the first is `deed.harvest.good-outsider`. Lane C adds the `deeds` field
through lane B (who owns `sheet.py`): lane C sends the exact field and its serialisation lines to
lane B, or the lead adds them at merge.

---

## 6. Consumed interfaces (built by the Enchanting lanes)

These are **not built in this craft**. The names and shapes are proposed; the Enchanting
contracts decide. Each consuming lane keeps its use behind one function so an adaptation is one
edit.

### 6.1 In progress

```python
inprogress.register(actor, *, craft: str, kind: str, label: str, produces: dict,
                    ready_minute: int, where: dict, collect: str, game: str | None = None) -> str
#   where: {"kind": "carried"} | {"kind": "place", "place": place_id}
#   collect: an op name the engine runs on Collect ("leather.collect")
#   game: a second-half game played at Collect ("tan.cut-test") or None
inprogress.entries(actor, now: int) -> list[dict]   # id, craft, label, ready_minute, ready_in,
                                                    # where (in words), collectable_here: bool
inprogress.collect(actor, entry_id: str, *, now: int, scene) -> dict
```

Lane E registers: every bark, alum, mineral and planar tannage, rawhide drying, and a thick hide's
lime pit (plan §7, §8.3). Until the Enchanting lanes land it, lane E writes its entries through a
local adapter with the same signature, backed by the steeping jar's `ready_minute` field, and the
lead switches the adapter at merge.

### 6.2 The metal tag

```python
itemtags.of(record_or_key, gear: str) -> frozenset[str]
#   material.metal, material.metal.ferrous, material.metal.<piece>
Actor.standing_tags()   # gains wears.armour.metal, wears.shield.metal, wields.metal (+ .ferrous)
```

Lane M reads only `actor.has_state("wears.armour.metal")` and its siblings, plus
`itemtags.of(...)` for the spell targets. Lane D sets `ferrous: true` on iron, steel, cold iron,
high-carbon steel, pattern steel and the other iron alloys, which the tag needs.

### 6.3 The enchanting cost discount

The Enchanting cost reader applies a vessel's `gear_mod enchant_cost_pct` with `applies_to`
matching the property's family (dragonhide: −25% on energy resistance). Lane D writes the effect;
lane A validates it; nothing in this craft reads it.

---

## 7. Bench rules and API (lane E serves, the UI lanes consume)

Methods (plan §7): `flense, salt, tan, curry, cut, stitch, harden, tool, dye, laminate, assemble,
grade`. Levels, perks (`potency`, `hardening`, `quality`, `yield`; Yield is read by lane C at the
harvest), masterwork by the book, kit vs tannery gating (asked through lane G's §8 API), the step
ceiling (level, grade cap, tannin trait, one above the body's tier).

Every proposed number lives in `content/world-classes/leatherworker.json` under `bench`, as the
forge's do in `blacksmith.json`: method rows (`where`, `bulk`, `minutes`, `tuning`), tannages
(`level`, `where`, `minutes`, `carried`), hide units per product, grade caps, `masterwork_dc`,
`book_dc`, vat size, salted keep, the CR tier bands.

API, mirroring `play/forge_views.py`, registered **above any catch-all** (the herb bench's
route-order bug, `test_bench_routes`):

| Route | Does |
|---|---|
| `GET api/leather/state` | the rack (carried stock grouped by form, with clocks and grades; plus what waits at this tannery), methods with locks and reasons, where you are, level, perks banked, ceiling, In progress count |
| `POST api/leather/check` | method + slots + batch → info line, DC, "you need N+", problems in words, the step ceiling and its reason (grade cap, tannin), the wait for a tannage, and `forge_items.preview` at Assemble |
| `POST api/leather/roll` | the player's d20 for the step → success or the loss in words |
| `POST api/leather/finish` | the game score 0..1 → tier, product and its `build`, mastery lines, discoveries, minutes passed, any In progress entry registered |
| `POST api/leather/collect` | an In progress entry id (+ the cut-test score) → the product |
| `POST api/leather/grade` | material id → `knowledge.assay` result in leather words |
| `POST api/leather/perks` | pick perks |
| `GET api/leather/ledger`, `GET api/leather/material/<id>` | the ledger and one card |

Every material row in the state response carries `color` and `surface` from the document (UI §4).
The page never computes a number.

---

## 8. Places (lane G serves)

```python
places.tannery_here(scene, known=()) -> dict | None
#   {"kind": "town" | "owned", "place": place_id, "keeper": ref | None,
#    "rate_cp_per_hour": int, "vat_rate_cp_per_day": int, "vats": int, "vats_free": int}
places.TANNERY = "place.tannery"
places.has_field_kit(actor, craft="leatherworker") -> bool
market.tannery_rent(scene, hours: float) -> int
market.vat_rent(scene, days: int, vats: int) -> int
```

A town tannery is the settlement place row (`rules/places.py:131`) with a keeper whose occupation's
tags contain `leather` (`content/people/occupations.json:225`), placed on the outskirts; an owned
tannery is a founded place with the `place.tannery` tag whose owner holds `holds.place.<slug>`.
Never read from the player's words.

---

## 9. The code each lane starts from (measured on master 1f88ada)

So no lane re-derives it:
- `forge_items.is_forged` needs `pieces` dict and `gear` in `PIECES` (`:445`); `build` (`:218`);
  `armour_row` folds `gear_mod`s (`:499-526`); material AC folds into the armour bonus via
  `_folds_into_armour` (`:484`, `_FOLDS_INTO_ARMOUR` `:89`); masterwork at `MASTERWORK_AT` 3 or
  `rec.masterwork`, armour ACP +1 (`:361`); shields read `shield` else `armour` (`:117`).
- The forge's rack lists only `craft` blacksmith or smithing stock (`rules/blacksmith.py:1767`);
  Assemble's main piece must be a forged blank or plate (`fit_reason`, `:1983-1995`); a finished
  item is accepted only by Finish; `FORGED_ARMOUR` (`:967`) is the eight metal suits; Assemble's
  cap is one above the main piece's tier (`:2616-2627`).
- `Actor.armour_stats` (`rules/sheet.py:815`), `armour_record` (`:792`), `_standing_mods(kind,
  target, ctx)` (`:1056`), `resistance` (`:2791`) and `damage_reduction` (`:2823`) read only the
  worn forged suit's build; `_wear_crafted` (`rules/engine.py:15031`) sets `actor.armour` from
  `base`.
- `materials.validate` returns early for the leatherworker catalogue (`rules/materials.py:405`);
  hides normalise to empty `armour` lists; their effects sit in a legacy `effects` list nothing
  reads; `knowledge._material_specs` reads only `weapon`, `armour`, `working`, `quench_mark`
  (`rules/knowledge.py:233`).
- `Actor.carry(..., at_minute=None)` sets `picked_at` and `preserved` only when `at_minute` is
  given (`rules/sheet.py:3184`); `craft_excursion` never passes it (`play/craft_views.py:1402`);
  `herbprep.has_salt` matches name fragments (`rules/herbprep.py:136`).
- Steeping: `ready_minute` on stock, set in `crafting.make` (`rules/crafting.py:2470`), cleared by
  `settle_steeping` (`:1861`) on every bench request (`play/bench_views.py:236`).
- Bestiary stat blocks have no `tags` today but the field is read live into standing tags
  (`rules/sheet.py:3421`); `type.` and `subtype.` tags come from `states.type_tags` (`:359`);
  scene actors link by `from_template` (`rules/bestiary.py:245`); `_fallen` matches the display
  name (`play/craft_views.py:1095`).
- Metal today: `armour.METAL_ARMOUR` and `METAL_SHIELDS` by table key (`rules/armour.py:198`),
  read only by inubrix's `when.target.armour_metal` (`rules/sheet.py:4908`); no weapon metal; the
  druid's `"no metal armour"` token (`content/classes/druid.json:25`) enforced by nothing; heat
  metal and chill metal are narrative save gates, rusting grasp a plain 3d6, shocking grasp's +3
  absent.
- Deeds exist only as world-class milestones (`rules/worldclass.py:151`); no renown or alignment
  system.
- The tannery place row (`rules/places.py:131`) and keeper (`:310`) exist; `smithy_here`
  (`:2042`) is the model; there is no tannery cue row.
- `tests/test_leatherworker.py`: 39 tests. Others naming the leatherworker: `conftest.py`,
  `test_aggregator.py`, `test_alchemist.py`, `test_api_robustness.py`, `test_benches.py`,
  `test_blacksmith.py`, `test_forge_knowledge.py`, `test_forge_materials.py`,
  `test_herbalist_endless.py`.

---

## 10. Every lane

- **Search first** for prior art on anything not settled by `docs/leatherworking-prior-art.md`
  and the plan's "Sources checked".
- **Tests document the defect they prevent**, with the measurement in the docstring (plan §23.1).
- **Run the whole suite** (`python -m pytest -n auto -p no:cacheprovider -v`, check the exit
  code; never `-q`), and do not edit `.py` files while it runs.
- **Three laws**: run `tests/test_three_laws.py`; load the `states-effects-tells` skill before
  touching `sheet.py`, `engine.py` or `activeeffect.py`.
- **Live checks** only on scratch data (`PATHFINDER_GM_DATA`), never `%LOCALAPPDATA%\PathfinderGM`.
- **Fixes are world-agnostic**: anything that changes what a world must carry is reported to lane W.
- Commit on your lane branch with named paths (`git add <file>`, never `-a`), and report: what was
  built, the test counts, anything measured, anything not done.

---

## 11. File ownership (wave 2)

Every lane starts with `git switch -c lane/leather-<id> leather/revamp`.

| Lane | Owns | Reads only |
|---|---|---|
| **H: forge hand-off** | `rules/blacksmith.py` (rack, `fit_reason`, Assemble from a base, `FORGED_ARMOUR` shapes from bases only), `play/forge_views.py`, `content/world-classes/blacksmith.json`; `tests/test_leather_forge_handoff.py` | `rules/forge_items.py`, `rules/leatherworker.py` |
| **M: metal readers** | `content/classes/druid.json` (the `prohibits` block), `rules/classfeatures.py`, `rules/casting.py`, `content/spells/mechanics/part-03.json` (chill metal), `part-08.json` (heat metal), `content/spells/spells-mechanics.json` (rusting grasp, shocking grasp); `tests/test_metal_readers.py` | the §6.2 interface, `rules/activeeffect.py` (the periodic executor) |
| **I: migration** | `rules/leatherworker.py` (the migration function only, after E merges); `tests/test_leather_migration.py` | `rules/sheet.py` (asks B's successor or the lead for the load hook) |
| **W: World Bible docs** | `docs/campaign-format.md`, `docs/from-world-bible.md` | |
| **U1: shell** | NEW `play/static/js/table/45-leather-shell.js`, `46-leather-rack.js`, `48-leather-order.js`, NEW `play/static/css/leather.css`; `play/templates/play/table.html` (the `#leather` layer, its script and link tags, the Leatherwork button); `play/static/js/table/43-forge-order.js` (**only** to export the build card as `window.BuildCard.open(build, anchor)`); `tests/test_leather_ui.py` | `29-bench-core.js`, `33-bench-games.js`, `34-bench-tag.js` |
| **U2: harvest sheet** | NEW `play/static/js/table/50-harvest.js`; the scene panel's Harvest button in `play/static/js/table/07-panels.js`; `tests/test_harvest_ui.py` | `29-bench-core.js` |
| **U3: games** | NEW `play/static/js/leather-games/*.js`; `play/static/js/table/33-bench-games.js` (the band gauge type, plan UI §6.4; herb and forge games unchanged); NEW `play/static/css/leather-games.css`; `tests/test_leather_games.py` | `bench-games/`, `forge-games/` |
| **U4: stage** | NEW `play/static/js/tannery-stage/*.js`, NEW `play/static/js/table/57-leather-stage.js` (`window.TanneryStage`); `tests/test_leather_stage.py` | `bench-stage/` (00 to 04 as is), `forge-stage/02-families.js` (the haft) |
| **U5: ledger and perks** | `play/static/js/table/44-forge-ledger.js` (parameterise by track), `play/static/js/table/21-tab-journal.js` (the hide ledger section); `tests/test_leather_ledger_ui.py` | `36-bench-perks.js` |
| **U6: sound** | `play/static/js/sound.js` (the `leather` bus), `play/static/js/prefs.js`, `play/templates/play/home.html` (its volume); `tests/test_leather_sound.py` | |
| **U7: old tab** | `play/craft_views.py` (the `moved` string and the hub's excursion change), `play/templates/play/craft.html` (the card); re-pins `tests/test_benches.py` | |

Script and link tags for U2 to U6 go in `table.html`, which U1 owns: those lanes report the exact
tags and U1 (or the lead at merge) adds them.

### 11.1 Interfaces between the UI lanes

- **Games (U3 provides, U1 and U2 call).** Each leather game registers on
  `window.BenchGameDefs[method]` exactly as the herb and forge games do. Leather games receive
  `opts.band`: `{unit: "fraction" | "strength" | "celsius" | "spi" | "minutes" | "percent",
  value_start, target: [lo, hi], fail: [lo, hi] | null, drift, narrow: bool}` from the check
  response, and report the score 0..1. The harvest game also reports `defects` (0..1 area) so the
  server can grade it; the server, not the page, turns that into a grade.
- **Stage (U4 provides, U1 calls).** `window.TanneryStage` (UI §12). Without WebGL every call is a
  no-op and `available()` is false.
- **Build card (U1 exports from the forge's file).** `window.BuildCard.open(build, anchorEl)`, the
  forge's card unchanged, so both benches and the sheet draw one card.
- **Ledger (U5 provides).** `window.MaterialLedger.card(track, materialId, anchorEl)` and
  `.journal(host, track)`; the forge's `window.ForgeLedger` stays as a thin alias.
- **Sound (U6 provides).** `Sound.play("leather.<event>", {...})`; unknown events are silent.
- **In progress (the Enchanting lanes provide).** U1 calls their open function from the footer
  link; it draws nothing of its own.
