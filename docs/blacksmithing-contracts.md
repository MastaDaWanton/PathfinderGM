# Blacksmithing revamp: lane contracts

Written 2026-10-03 by the lead, before any lane starts. The plans are
`docs/blacksmithing-revamp-plan.md` (rules, data, engine) and `docs/blacksmithing-ui-plan.md`
(interface). This file fixes the **shapes that cross lanes** and **who owns which file**, so the
lanes can run in parallel without writing over each other. A lane that needs a shape changed
asks the lead; it does not change it locally.

Integration branch: **`forge/revamp`**, off `origin/master` at bfbded3. Every lane starts with
`git switch -c lane/forge-<letter> forge/revamp` in its own worktree and never touches another
lane's files.

---

## 1. File ownership (wave 1)

| Lane | Owns (may create and edit) | Reads only |
|---|---|---|
| **A: vocabulary** | `rules/effectspec.py`; `tests/test_forge_vocabulary.py` | |
| **B: engine readers** | `rules/sheet.py`, `rules/engine.py`, `rules/activeeffect.py`, **`rules/forge_items.py` (new)**; `tests/test_forge_engine.py`, `tests/test_forge_items.py`, `tests/test_periodic_effects.py` | `rules/materials.py` (via §3 API) |
| **C: data pass** | `content/materials/*.json`, **`rules/materials.py` (new)**, `tools/forge_*.py` (new), **`docs/blacksmithing-review.md` (new)**; `tests/test_forge_materials.py` | `rules/effectspec.py` |
| **D: bench rules** | `rules/blacksmith.py`, `content/world-classes/blacksmith.json`, `rules/worldclass.py`, **`play/forge_views.py` (new)**, `pathfindergm/urls.py` (forge routes only); `tests/test_blacksmith.py`, `tests/test_forge_bench.py`, `tests/test_forge_api.py` | `rules/materials.py`, `rules/forge_items.py`, `rules/knowledge.py` |
| **E: knowledge** | `rules/herbknowledge.py`, **`rules/knowledge.py` (new)**, `rules/goods.py`, `content/rules/` manual tables; `tests/test_forge_knowledge.py` | `rules/materials.py` |
| **F: bench core** | **`play/static/js/table/29-bench-core.js` (new)**, `play/static/js/table/30-bench-shell.js`, the script tag in `play/templates/play/table.html`; `tests/test_bench_core.py` | everything else under `play/static/` |
| **G: smithy places** | `rules/places.py`, `rules/market.py`; `tests/test_forge_places.py` | |

Nobody but the owner edits an owned file. `tests/test_three_laws.py`, `tests/conftest.py` and
`.claude/launch.json` are **owned by nobody in this wave**: do not commit them. A lane that needs a
dev server adds a local launch entry and leaves it uncommitted.

**Wave 2** (after wave 1 merges): forge UI shell (U2), games (U3), stage (U4), ledger and perks
(U5), sound (U6), the old `/craft/` tab (U7), and migration (plan §14). Their contracts are
appended here when wave 1 lands.

---

## 2. The effect vocabulary (lane A defines, everyone uses)

Two new effect types and one new bonus type, added to `rules/effectspec.py` with validators,
renderers and catalogue entries:

| Type | `target` values | Other fields |
|---|---|---|
| `gear_mod` | `acp`, `max_dex`, `asf`, `weight_pct`, `hardness`, `hp_per_inch`, `category`, `speed_penalty` | `amount` (int, signed) |
| `strikes_as` | `cold_iron`, `silver`, `adamantine` (extensible list `STRIKES_AS`) | none |
| `working` | a trait id from `WORKING_TRAITS`: `easily_worked`, `flawless`, `malleable`, `pure`, `slaggy`, `sulfurous`, `clean_heat`, `quench_sensitive`, `narrow_window`, `forgiving`, `reactive`, `cleans_slag`, `weld_aid`, `brittle`, `hot_short` | `amount` optional |

- **Sign convention (lane A, merged 7b49a9f):** a `gear_mod` amount is **added to the number as
  `tables.ARMOUR` stores it**. Armour check penalty is stored negative, so a lighter penalty is a
  **positive** amount (mithral `acp +3`) and a heavier one negative (iron `acp −2`); `asf` is a
  positive percentage (mithral −10, noqual +20); `weight_pct −50` is half weight; `category −1`
  is one weight class lighter, for movement only. `effectspec.is_drawback(spec)` decides which
  direction is worse, per target.
- `bonus_type: "material"` joins the bonus-type vocabulary. It stacks with every other type and
  never with itself.
- Any effect may carry `"book": true` (a printed PF1e number: main piece only, never scaled) and
  a `trigger`: `hit`, `crit`, `first_wound_daily`, `carried`. `trigger` is validated by type
  (`carried` only on `apply_condition`, `save_gate`, `ability_damage`).
- `when` clauses use the existing grammar (`_when_holds`): `{"target": {"type": "fey"}}` is new
  and lane B evaluates it against the defender.
- `effectspec.executable()` is True for all three new types. `narrative` stays legal in the
  vocabulary but **lane C's validator refuses it** in material documents.

---

## 3. The material document (lane C defines and serves)

`rules/materials.py` is the **one door** to every craft material (blacksmith, alchemist,
enchanter and leatherworker files). It replaces nobody's loader yet; it reads the same files.

```python
materials.get(material_id: str) -> dict | None          # normalised document, read-only
materials.all() -> dict[str, dict]
materials.of_kind(kind: str) -> list[dict]
materials.material_of(id: str) -> str                   # a form's parent material ("mithral-fittings" -> "mithral")
materials.validate(doc: dict) -> list[str]              # problems, with the fix named
materials.TIER_CEILING  # {"common": 2, "uncommon": 2, "rare": 3, "exotic": 3, "legendary": 4}
```

The normalised document (every field defaults, so an old file loads):

```json
{
  "id": "iron", "name": "Iron", "kind": "metal", "tier": "common",
  "form": "bar",
  "material": "iron",
  "pieces": {"weapon": ["head", "fittings"], "armour": ["body", "fastenings"]},
  "weapon": [ <effect>, <effect>, <effect> ],
  "armour": [ <effect>, <effect>, <effect> ],
  "working": [ {"type": "working", "trait": "forgiving"} ],
  "quench_mark": null,
  "book": false,
  "price_gp": 1, "text": "...", "biomes": [], "obtain": "bought"
}
```

Rules lane C's validator enforces (plan §5.7): structural kinds (`metal`, `alloy`, `fitting`)
have ≥3 `weapon` and ≥3 `armour` effects **where their `pieces` names that gear**, ≥1 negative in
each list, no `narrative`, house numbers within `TIER_CEILING`, base house value ±2; every
material has ≥1 `working` trait; quenchants have a `quench_mark`; every material has ≥3
discoverable properties (effects plus working traits plus mark). **Ids, names and the 8 kinds do
not change** (tests pin them).

Piece names: weapon `head`, `haft`, `fittings`; armour and shield `body`, `fastenings`, `lining`.

---

## 4. The crafted item record and the build (lane B computes, lane D writes)

Lane D's Assemble writes this record into `pc.stock` (and `Actor.wear` keeps it in `worn`):

```json
{
  "id": "fine-iron-longsword", "name": "Fine Iron Longsword",
  "kind": "crafted", "craft": "blacksmith", "count": 1,
  "gear": "weapon", "base": "longsword", "slot": "hands",
  "quality": "fine", "quality_index": 2, "masterwork": false,
  "pieces": {
    "head":     {"material": "iron", "passes": 1},
    "haft":     {"material": "ash-haft", "passes": 0},
    "fittings": {"material": "brass-guard", "passes": 0}
  },
  "quench": "water", "finish": [], "flaws": [],
  "smith": {"level": 2, "perks": {"potency": 0, "hardening": 0}},
  "schema": 3
}
```

The record stores **ids and passes, never computed numbers** (the read-live rule). Lane B serves:

```python
forge_items.build(record: dict) -> dict
# {
#   "specs":      [effect, ...],   # weapon or armour modifiers after the §6.2 sum, rounded toward zero,
#                                  #   each with "origin": "item:<id>" and "source": material id(s)
#   "book":       [effect, ...],   # main piece's book effects, unscaled
#   "strikes_as": ["cold_iron"],
#   "gear":       {"acp": -2, "max_dex": 0, "asf": 0, "weight_pct": 0, "hardness": 5, ...},
#   "riders":     [effect, ...],   # trigger-bearing effects (hit, crit, first_wound_daily, carried)
#   "sum":        [{"target": "attack", "pieces": {"head": -3, "haft": 1, "fittings": 0},
#                   "bonus": 1.25, "negative": -2.7, "final": -1}, ...],
#   "masterwork": bool
# }
forge_items.preview(pieces: dict, *, gear, base, quality_index, level, perks) -> dict   # same shape, no record
```

Maths exactly as plan §6.2–6.3: main piece ×1, others ×0.5; Strengthen ×1.5 per pass; quality
multiplies bonuses (Crude 0.75, Sound 1, Fine 1.25, Superior 1.5, Flawless 1.75, +0.25 per +N);
negatives × 0.9^(level−1) × 0.95^hardening, floored at 0.5; bonuses and negatives summed
separately per target, then added, then **rounded toward zero**. Book effects, masterwork, the
quench mark and finishes are not in the sum. The worked example (plan §6.4: +3 damage, −1 attack,
+5 hardness) is a test.

---

## 5. What lane B's readers promise (lanes D, U use)

- `Actor.weapon(key)` resolves a crafted weapon record held in `stock` or `worn` by its `id` or
  `name`; the result carries `crafted_record` and the base weapon's statistics.
- The engine's `wear` op accepts a crafted record id from stock.
- `Actor._standing_mods(kind, target, ctx=None)`: a weapon record's modifiers apply only when
  `ctx["weapon"]["key"]` is that record; armour while it is in the armour slot. **The open door is
  closed**: a masterwork record in the hands slot no longer raises every attack.
- Weapon hits pass `strikes_as` as damage traits to `_apply_damage`; `damage_reduction()` and
  `resistance()` read worn armour's build.
- Riders land as `ActiveEffect`s with `origin: "item:<id>"`; carried effects are granted while the
  item is in the pack and removed with it.
- `ActiveEffect.periodic` gains `heal` and `damage` executors (per round and per day).
- `_op_prospect` writes stock the forge can read (fix the `"smithing"` vs `"blacksmith"` craft id,
  run it first to confirm the defect).

---

## 6. Knowledge (lane E serves)

```python
knowledge.property_keys(material_or_ingredient) -> list[str]
knowledge.properties(actor, doc) -> list[dict]        # herbknowledge.properties, for any doc
knowledge.assay(actor, material_id, total: int, *, clock: int) -> dict
#   {"revealed": [key, ...], "cost": {"bars": 0.1} | {"ore": 1}, "minutes": 10,
#    "danger": effect | None}           # reactive metals apply their carrier effect for real
knowledge.assay_dc(doc, actor) -> int                 # rarity DC, −1 per known same-kind material, max −4
knowledge.ledger(actor) -> list[dict]                 # the herbarium for materials
```

One store: **`Actor.herb_known`**, keyed by material id (material ids and herb ids are disjoint;
the test in `test_alchemist.py:601` already pins cross-file uniqueness). No new Actor field in
this wave; a rename is a later migration. `rules/herbknowledge.py` keeps every current name
working (re-exports or thin wrappers), so the herb bench is untouched.

Smithing manuals: a goods table beside the herbal manuals, `content/rules/smithing-manuals.json`.

---

## 7. Bench rules and API (lane D serves, wave 2 UI consumes)

Methods (plan §7): `smelt, alloy, forge, quench, temper, fold, hone, assemble, finish, strengthen,
assay`. Levels, perks (`potency`, `hardening`, `quality`, `yield`), masterwork at Superior, no
bulk at Assemble, field kit vs smithy gating (asked through lane G's §8 API).

API, mirroring `play/bench_views.py` and registered **above any catch-all** (the herb bench's
route-order bug, `test_bench_routes`):

| Route | Does |
|---|---|
| `GET api/forge/state` | the rack (carried materials and worked pieces), methods with locks and reasons, where you are, level, perks banked, ceiling |
| `POST api/forge/check` | method + slots + batch → info line, DC, "you need N+", problems in words, and `forge_items.preview` |
| `POST api/forge/roll` | the player's d20 for the step → success or the loss in words |
| `POST api/forge/finish` | the game score 0..1 → tier, product (and its `build`), mastery lines, discoveries, minutes passed |
| `POST api/forge/assay` | material id → `knowledge.assay` result |
| `POST api/forge/perks` | pick perks |
| `GET api/forge/ledger`, `GET api/forge/material/<id>` | the ledger and one card |

The page never computes a number; every number in a response comes from the engine.

---

## 8. Places (lane G serves)

```python
places.smithy_here(scene) -> dict | None
#   {"kind": "town" | "owned", "place": place_id, "keeper": ref | None, "rate_cp_per_hour": int}
places.has_field_kit(actor) -> bool                    # the kit is a goods item carried
market.forge_rent(scene, hours: float) -> int           # copper pieces
```

A town smithy is a place whose keeper is a smith (occupation) in a settlement; an owned smithy is
a founded place with the `smithy` tag whose owner holds `holds.place.<slug>`. Never read from the
player's words.

---

## 9. Every lane

- **Search first** for prior art on anything not settled by `docs/blacksmithing-prior-art.md`.
- **Tests document the defect they prevent**, named in the docstring.
- **Run the whole suite** (`python -m pytest -n auto -p no:cacheprovider -v`, check the exit code;
  never `-q`), and do not edit `.py` files while it runs.
- **Three laws**: run `tests/test_three_laws.py`; load the `states-effects-tells` skill before
  touching `sheet.py`, `engine.py` or `activeeffect.py`.
- **Live checks** only on scratch data (`PATHFINDER_GM_DATA`), never `%LOCALAPPDATA%\PathfinderGM`.
- Commit on your lane branch with named paths (`git add <file>`, never `-a`), and report: what was
  built, the test counts, anything measured, anything not done.
