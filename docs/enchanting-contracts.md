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

**As built by lane A (2026-10-05).** Where this differs from the table first written here, the
reason is in the code comment beside it and in brief in the "Changed" column. Every type is
**standing** (no trigger; `_STANDING_TYPES`) except `slay` and `item_power`; all are in the new
`magic_item` catalogue category with a validator and a renderer. **`engine` is False for all ten
until lane C's readers land**, not True as first drafted: the existing honesty ratchet
(`tests/test_effectspec_extensions.py::test_every_executable_type_has_something_that_executes_it`)
refuses a type that claims the engine runs it when nothing does, and the first full run failed
on exactly these ten. `effectspec.AWAITING_READER` lists each with its reader's site; **lane C
deletes a type's line when its reader lands** (and adds the type, with the site, to that
test's `already` set), which makes it executable. Consequences now: `materials.validate`
refuses these types inside a material's own effects (lane D: essences name properties through
`grants`, never these documents), and `consumables` narrates them.

| Type | Fields | Changed from the first draft, and why |
|---|---|---|
| `crit_range` | `multiply` (int, default 2), `stacking` (group, default `"threat-range"`) | `not_with: "feat.improved-critical"` named a tag nothing grants (Improved Critical has no feat document, keen edge is prose). The book's rule is a stacking rule ("doesn't stack with any other effect that expands the threat range"): the reader applies the best of each `stacking` group once. |
| `extra_attack` | `on` (`full_attack`), `count` (int, 1), `stacking` (default `"haste"`) | Same reason: speed is "not cumulative with similar effects, such as a haste spell"; haste's extra attack joins the `haste` group when it gets a document. |
| `enhancement_raise` | `amount` (int) | **New.** Bane: "its enhancement bonus is +2 better". As a `combat_mod` +2 enhancement it collides with the sword's own +1 in `dice.stack` and the +1 bane sword hits at +2, not the book's +3 (measured in the test). It raises the weapon's enhancement for attack, damage and the DR thresholds (Q8). |
| `enhancement_to_ac` | `max` (`"enhancement"`) | As drafted. The amount is a per-turn param from the combat bar, validated by the engine; the AC bonus is untyped ("stacks with all others"). |
| `fortification` | `percent` (1-100; the book's 25, 50, 75) | As drafted. |
| `ignore_armour` | `cannot_harm` (list of creature types and `object`) | `except` read as "the armour still counts against these"; the book says brilliant energy "cannot harm undead, constructs, or objects" at all. |
| `deflect_ranged` | `per` (`round`), `save` (`ref`), `dc` (int), `dc_adds_enhancement` (bool), `draws_ft` (int), `deflection` (int) | `{"reflex": 20}` split into `save` + `dc` (save_gate's shape). `auto` dropped: no shield in the book catches automatically (that is Snatch Arrows, a feat). Arrow catching is `draws_ft: 5` + `deflection: 1`. |
| `weapon_lethality` | `lethality` (`nonlethal`), `suppressible` (bool) | **New.** Merciful: "all damage it deals is nonlethal ... on command, suppresses this ability". Read where `weapons.lethality_of` reads a sap's. |
| `slay` | `natural` (int, optional), `except` (creature types) | **New.** Vorpal (`trigger: crit`, `natural: 20`) and disruption (inside a `save_gate`'s `on_failure`): the creature dies through `Actor.die`. |
| `item_power` | exactly one of `spell` (spell id), `effect` (one document) or `tell` (a power that changes no number: glamered); `caster_level`; `area` (`{"shape": "burst", "ft": 20}`, class_abilities' shape); **`uses` required** | Uses are the `uses`/`uses_count` every effect already carries (`"per_day"`, 2; `"unlimited"` is at will), not a second `{"per", "n"}` spelling. Required, so a power cannot be at will by accident. |

Additions to existing lists and fields:
- `STRIKES_AS` gains `magic`, `good`, `evil`, **`lawful`, `chaotic`** (not `law`/`chaos`: the
  bestiary prints "DR 10/chaotic" and "DR 5/lawful", and `bypassed_by` compares words).
  `ENHANCEMENT_STRIKES_AS` and `strikes_as_for_enhancement(n)` give the glossary thresholds
  (+1 magic, +3 cold iron and silver, +4 adamantine, +5 the four alignments) for lane B's layer;
  pass the enhancement *as raised* against the creature struck.
- `ITEM_TRIGGERS` gains `wielded` and `worn`, valid on `WORN_TYPES`: the carried three plus
  `fast_healing`, `sense`, `spell_effect`, `immunity`, `negative_level`. A plain modifier on a
  worn item takes **no** trigger (it is a standing spec) and `worn` on one is refused.
- `damage` gains `per_multiplier: bool` (crit damage only; dice × (multiplier − 1)). Vicious's
  wielder damage is **`recipient: "self"`** ("The one who has it", already in the vocabulary),
  not a new `"wielder"`.
- `bleed` gains `stacks: bool` (wounding).
- Any effect may carry `choice_key`; a `when` may reference it as `{"target": {"choice": key}}`
  and the validator requires the two to agree. **Lane C does not resolve choices in
  `_when_holds`:** `effectspec.bind(prop, choice)` fills them before any document leaves the
  table — bane bound against undead carries `when: {"target": {"type": "undead"}}`, the clause
  `_when_holds` already reads (`{"subtype": ...}` for a humanoid or outsider foe). For an
  energy or skill choice, `bind` writes the chosen value into `target`.
- Booleans with no form field, validated as `book` is (`_BOOLEAN_KEYS`): `book`, `house`,
  `per_multiplier`, `stacks`, `suppressible`, `dc_adds_enhancement`. `book` and `house` together
  are refused.
- `GEAR_TARGETS` gains `range_pct` (distance: +100) and `throw_range_ft` (throwing: 10).
- `FORMULA_VARS` gains `bonus`: a scaled property's documents say `"amount": "bonus"` and `bind`
  works it out.
- `WORKING_TRAITS` gains `night_only`, `eager`, `skittish`, `heavy`, `volatile` (lane D's §5
  request, done now so D is not blocked).
- `when.target.alignment` is legal in property documents and **not read** by `_when_holds` yet
  (`WHEN_NOT_READ`); every property using it says so in `not_yet` (the validator holds it to
  that). Lane C reads it from a creature's printed alignment, as `Engine._could_be_evil` does.

`narrative` stays legal in the vocabulary; **lane D's validator refuses it** in essences and
recipes, and the property table refuses it outright.

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

- `plus` (bonus equivalent) **or** `gp` (flat price, outside the +10) **or** `scaled`, exactly
  one. `scaled` is the ring and wondrous pricing table's "bonus squared × K":
  `{"values": [1, 2, 3, 4, 5], "gp_per_square": 2000, "creator_cl_per_bonus": 3, "tiers": [...]}`;
  the bonus is bound like a choice, under the key `bonus`.
- `spells` is a list of alternatives groups: each inner list is "any one of these" (flaming: any
  of three; shadow is two groups, invisibility **and** silence). Each group not met is one +5 DC
  (revamp plan §4.2). Ids are the Spells bench's (`summon-monster-1`), checked by the test.
- `requires`: vessel restrictions, a refusal — `melee`, `ranged`, `thrown` (only that kind),
  `launcher: false` (brilliant energy: not the bow itself), `damage_types_any` — each the
  ability's own restriction sentence, never the random table it appears on. Creator clauses,
  each one more +5 DC: `creator_alignment` (waived, Q7), `creator_class` (ki focus: monk),
  `creator_caster_level` (spell storing: 12).
- `choice`: `{"key": "foe", "of": "creature_type" | "damage_type" | "skill", "options": [...]}`.
  A `creature_type` choice is a type, or `{"subtype": "goblinoid"}` for `humanoid`/`outsider`
  (the book: "pick one subtype"; subtypes are the world's own and not listed).
- `wielder`: `{"alignment": "evil", "negative_levels": 1}` for the holy family, data only (Q7).
- `reads_tag`: for a property with no documents, whose whole effect is a rule a reader asks of
  its tag `property.<id>` (returning, seeking, ki focus, mighty cleaving, ghost touch armour,
  wild, bashing, animated, dancing and spell storing): names the reader. Such a property must
  also carry a `not_yet`.
- `not_yet`: every clause of the book nothing executes yet, said out loud. `house`: which of the
  entry's numbers are not the book's (only `skill-competence`, whose free-form CL and cap the
  book does not print).
- `aliases`: `{"mi-energy-resistance-fire": {"energy": "fire"}, ...}` — **every one of the 58** old
  weapon and armour ids, with the choice it implies. `mi-bane` maps to `{}`: the old bane never
  named its foe, so the migration (lane H) must ask. `mi-silent-moves` maps to `shadow` (Pathfinder
  folded it in).
- `aura`: `{"strength", "school": [...]}`, `source` (the AoN page), `text` (the card line).

API:

```python
effectspec.properties() -> dict[str, dict]       # by id; validated on load (BadProperties)
effectspec.property(id_or_old_id) -> dict | None
effectspec.from_alias("mi-...") -> (property id, choice) | None      # lane H
effectspec.bind(prop | id, choice=None) -> list[dict]
#   the documents with choice and bonus filled, deep-copied, each "source": "property:<id>";
#   raises ValueError (choice_problems) for bane with no foe, a scaled one with no bonus...
effectspec.choice_problems(prop, choice) -> list[str]
effectspec.price_of(prop, bonus=None) -> {"plus": n} | {"gp": n}
effectspec.property_lines(prop | id, choice=None) -> list[str]   # card lines, "against undead"
effectspec.property_tag(id) -> "property.<id>"
effectspec.strikes_as_for_enhancement(n) -> tuple[str, ...]
effectspec.property_problems(entry, spell_ids=None), all_property_problems(entries, spell_ids=None)
```

The table is shipped data with no homebrew overlay, cached with `lru_cache`
(`effectspec._property_table.cache_clear()` in a test that swaps the file).

Counts: 71 entries — 32 weapon, 28 armour and shield (9 armour only, 6 shield only, 13 both),
11 ring and wondrous (deflection, natural armour, armour bonus, resistance, six ability
bonuses, skill competence). Free-form *spell* powers on wondrous items (continuous or command
word, priced spell level × CL × 2,000/1,800) are **not** in the table: they stay recipes
(lane D) until a free-form spell pricing rule is agreed.

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

### 3.4 As built (lane B, 2026-10-05)

Where this differs from §3.1-3.3 the reason is in the module docstring; in brief:

- **Capacity is the owner's round 4 ruling**, not §3.2's maths: `capacity(record, *,
  binder_level=None, binder_perks=None)` (a **new `binder_level` argument**; both default to
  the record's last `binding`) returns `{"bonus", "used", "left", "cap": None, "level",
  "from_level", "from_quality", "from_perks", "masterwork", "why"}` with bonus =
  floor(level / 2) + max(0, quality_index − 3) + Capacity perks, **no ceiling**. Arms and armour
  below Superior hold 0 ("not masterwork"). The plan's power-count column for rings and
  wondrous items is gone: **one budget for every vessel**, a wondrous power counting as the plus
  a weapon would carry at its price, ceil(sqrt(gp ÷ 2,000)) (a reading; the book has no bonus
  equivalent for wondrous items).
- **Kept from the book:** +5 the highest enhancement, and a special ability on arms or armour
  needs at least +1 enhancement. Gold-priced abilities (`flat`) are outside capacity.
- `plan(record, adds, *, binder, hurry=False, helps=())`: `adds["enhancement"]` is the number of
  steps to **add** (+1 → +2 is 1). `binder` also takes `classes` (ki focus's monk). `helps` are
  the bench's own DC terms (affinity, catalyst), added as given. The result also carries `dc`
  (the sum), `notes` (waived alignment clauses), `gear`, `creator_level`, `aura`;
  `price` also carries `item_market_gp` and `was_gp`; `needs.enhancement` is `{"from", "to"}`
  or None and `needs.powers` the recipe ids.
- Surcharges: noqual's from its document (`enchant_surcharge_gp`, any piece); cold iron's
  2,000 gp from the book as `magic_layer.WEAPON_MAIN_SURCHARGE_GP` (weapon, main piece) because
  the cold iron document carries no `enchant_surcharge_gp` — a material's own field wins when
  it has one. Both only when the record has no layer yet.
- `write(record, adds, *, binding, curse=None, day=None)`: raises ValueError for an unknown
  property or recipe or an unanswered choice; stores `{"id", "essence", "choice"}` per entry,
  files a gold-priced property under `flat` whichever list it came in; adds `worked_day`.
- `layer(record, *, believed=False)` returns `specs, riders, wielded, worn, strikes_as, raises,
  powers, tags, enhancement, aura, schools, caster_level, total_bonus, price_gp, capacity,
  known, problems, gear, schema`. Weapon +N: `combat_mod` attack and damage, `bonus_type:
  enhancement`; armour/shield +N: `combat_mod` ac, `bonus_type: armour` (folded by
  `armour_row`). `raises` are bane's `enhancement_raise` documents; lane C asks
  `raised_enhancement(lay, holds)` / `strikes_as_against(lay, holds)` with `holds = lambda
  when: _when_holds(when, ctx)`. `powers` rows: `{"key", "source", "spec", "uses",
  "uses_count", "used"}`. `tags`: `property.<id>` for every bound property. A curse is applied
  through `curses.documents(curse, layer) -> {"suppress": bool, "replace": {list: [...]},
  "add": {list: [...]}, "enhancement": int}` when rules/curses.py exists (lane F); the curse's
  id never appears in the output.
- **Riders are NOT merged into `build["riders"]`**; they stay in `build["magic"]["riders"]`,
  which is what §4 says lane C reads. Measured: `Engine._item_riders` turns a rider into a
  damage intent through `consumables._spec_to_intents`, which never asks the rider's `when`,
  so a merged bane rider would have put +2d6 on every foe (the very note-only defect bane's
  `when` exists to close), and its tell would have read "The property:bane in ...". Specs and
  `strikes_as` ARE merged: `_standing_mods` asks every spec's `when`.
- `magic_layer.record_specs(record)`: a NON-forged record's flat specs plus its layer's, for
  lane C's `_record_specs` (rings and cloaks have no forge build).
- `forge_items.record_for_base(base, *, gear, quality_index=3, pieces=None, item_id=None,
  name=None)`: default pieces marked `plain` (named, not summed); `craft: "bought"`; pass
  `item_id` for a unique id. `forge_items.record_of` carries a plain forge `Stock`'s
  `Stock.magic` into the rebuilt record.
- Tags: `item_tags.material_tags / has_material / main_material` as §3.3, plus
  `materials_in`, `substance_of`, `root_material`, `default_pieces`; tag text
  `material.<substance>.<root id>` (`material.wood.ash`, `material.metal.cold-iron`),
  `material.<substance>`, `material.main.<root id>`, written only by
  `states.material_tag` / `main_material_tag`. Substances (`states.SUBSTANCES`): metal, wood,
  leather, bone, horn, cloth, cord, stone, glass. A finish (alchemical silver) adds no
  substance. `armour.worn_things(actor)` is the suit and shield as tag-readable things.

---

## 4. What lane C's readers promise

- Layered weapon records resolve through `Actor.weapon` and `_crafted_weapon` exactly as forged
  ones (the layer rides on the record). The layer's `+N` reaches attack and damage through the
  weapon scope (`_standing_mods` with `ctx["weapon"]["record"]`), and competes best-only with
  masterwork's +1.
- `Engine._item_riders` (`engine.py:11170`) reads `build["magic"]["riders"]` too; crit riders
  fire on a confirmed crit with `per_multiplier`; `recipient: "self"` riders hit the wielder
  (vicious; §2.1).
- The threat test (`engine.py:5213`) reads `crit_range` (keen), best of each `stacking` group
  once (keen with Improved Critical doubles once). `enhancement_raise` (bane) raises the
  weapon's enhancement for attack, damage and `strikes_as_for_enhancement`.
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

**As built (lane G, 2026-10-05).** The owner's Round 4 rulings override the above where they
differ: **no limit** in any craft (`register(..., limit=...)` raises, naming the ruling); `begin`
also takes `where_name` (how the page says the place) and `doing` (the gerund refusals use, "still
binding"); `register` also takes `stop_words` (the confirm's consequence, a string or `f(item)`);
rows also carry `ready_when` ("day 15, morning"). Readers for doors: `inprogress.held_back(item,
now) -> str` (why it cannot be used yet, "" when free), `work_of`, `state_of`, `end_of`.
`Scene.advance` calls `settle` (lane G added the one call, since the tell was in its brief) and
buffers "<name>'s <thing> is ready to collect." on `Scene._works_said`, told at the end of each
engine op and batch by `Engine._works_settles` (op `works`), as the body's tolls are. A forged
vessel's block is kept in `record["work"]` too, because `ForgedStock.as_dict` writes only its
record. Herbalism's jars have no Stop (a steep cannot be hurried; the owner may rule otherwise).

### 8.3 Sky

**Replaced by the owner (Round 4, point 10): phases of the day, not planets.** As built:

```python
sky.PHASES             # ("dawn", "morning", "noon", "afternoon", "dusk", "night", "midnight")
sky.OWNER_PHASES       # the six the owner named; `afternoon` exists so 15:00 is never "noon"
sky.phase_at(clock_minutes) -> dict      # {"phase", "starts", "ends", "left"}, absolute minutes
sky.inside(phase, clock_minutes) -> bool
sky.next_phase(phase, clock_minutes) -> int   # minutes until it begins (0 if now)
sky.words(clock_minutes, phase) -> str   # "Noon, 42 minutes left" / "Midnight in 3 hours 10 minutes"
sky.windows() -> list[dict]              # one day's windows, for a dial
sky.span_words(minutes) -> str           # the countdowns' words, shared with In progress
```

Dawn 06:00 and dusk 18:00 (the engine's), one constant pair; each turning point (dawn, noon, dusk,
midnight) holds the two hours centred on it, morning, afternoon and night fill between. Sources
in `rules/sky.py`'s docstring. An essence family names its `phase` in data (lane D) and an unknown
phase raises by name.

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
