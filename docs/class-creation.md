# Making a class

Everything a Pathfinder class is in this app, named — and how to author one, from a fighter
that fills in two sections to a Blood Bender that fills in all nine.

The reference implementation is `content/classes/blood-bending.json`. Nothing in it is
special-cased in the engine: every part of it is a field some module reads, and this
document is the list of those fields. If a mechanism is not here, no class has it.

- The machine-readable version is `CLASS_SCHEMA` in `rules/classbuilder.py`. The builder
  page generates its whole form from it, so this table and the form cannot drift.
- The tool is at **`/homebrew/classes/`**.
- `rules/classbuilder.py:validate_class` refuses a class that would misbehave, and every
  message says the fix rather than the fault.

---

## 1. The classification

`Required` means the class does not work without it. `Advanced` means a simple class should
never see the field — the builder hides those sections behind a divider, and the "simple
martial class" scaffold uses none of them.

### Identity

| Field | Type | Required | Read by |
|---|---|---|---|
| `id` | text | yes | `rules/classes.py:all_classes` — the key everything resolves by, and the filename. Lower case, and **permanent**: a character sheet stores this string. |
| `name` | text | yes | Every page that shows a class. |
| `summary` | text | no | `rules/creation.py:options` (the forge card) and the Class tab. |
| `source` | text | no | **Nothing.** Provenance only. |
| `alignment` | text | no | **Nothing.** The sheet has no alignment field. |

### The numbers

| Field | Type | Required | Read by |
|---|---|---|---|
| `hit_die` | number or dice | yes | `rules/creation.py:max_hit_die` for first level (maximised), `rules/leveling.py:level_up` rolls it every level after. `8` or `"2d8"` — notation is why it is not an integer. |
| `hit_dice_per_level` | number | no (adv) | `rules/classes.py:apply` → `Actor.hit_dice`. 1 unless stated. Two changes every "per Hit Die" number in the game. |
| `bab` | `full` \| `three_quarter` \| `half` | yes | `rules/tables.py:bab_for` → `Actor.bab` and every attack. |
| `good_saves` | list of `fort`/`ref`/`will` | yes | `rules/tables.py:save_for`, `rules/leveling.py:gains_at`. |
| `saves` | map save → track or 20 numbers | no (adv) | `rules/classes.py:save_base`. A **named track** (`good`, `good_plus_1`, `good_minus_1`, `poor`) is derived and cannot arrive mistyped. **Twenty integers** are for a printed column that is not regular — Blood Bending's Will, where deriving a number would mean inventing one. |
| `skill_ranks` | number | yes | `rules/creation.py:build`, `rules/leveling.py:gains_at`. Before Intelligence. |
| `class_skills` | list | no | `rules/sheet.py` — the +3 trained bonus. |
| `proficiencies` | list | no | `rules/sheet.py:is_proficient`. Groups (`simple`, `martial`, `exotic`) or single weapons by name. |
| `starting_wealth` | text | no | **Nothing.** No starting gold is rolled; a new character is given a kit. |

### The level table — `levels`

A list of twenty rows. Read by `rules/classes.py:features_at` and `table_at`, and drawn by
`rules/leveling.py:preview`.

| Key on a row | Meaning |
|---|---|
| `level` | 1–20. **One row per level, no gaps** — a missing row grants nothing and prints no dice, and nothing anywhere says why. |
| `grants` | Names, not sentences. They appear on the sheet's class-features list, on the class tab, and answer a glossary click. |
| *anything else* | A **die column**. `fist`, `blood`, `squall` — any name. `rules/leveling.py:table_die` reads it by name, the class tab draws whatever columns it finds, and an effect can multiply one with `dice_from`. |

### Features in full — `features`

A map of feature name → its rules text, verbatim. Read by `rules/glossary.py:build`, which
is what puts the paragraph behind the name on the sheet. A stored text always beats a
paraphrase: Blood Bond lives here.

### Rules this class does not play by — `overrides` *(advanced)*

Read by `rules/classes.py:overrides_for` → `Actor.overrides` → `Actor.allows()`. **Six
rules exist**, and only six; an unknown one is collected and reported by `classes.apply`
rather than granted, because the alternative is a class feature that silently never
happens.

| Rule | What it does | Asked by |
|---|---|---|
| `temp_hp.stacks` | Temporary hit points from different sources add up. | `rules/sheet.py:gain_temp_hp` |
| `nonlethal.counts_temp_hp` | Non-lethal damage must pass hit points **plus** temporary ones. | `rules/sheet.py:nonlethal_threshold` |
| `heal.overflow_temp_hp` | Healing at full hit points banks as temporary ones. | `rules/sheet.py:heal` |
| `needs.no_sleep` | Never rolls to stay upright, however long awake. | `rules/survival.py:exempt` |
| `needs.no_food` | Never makes a hunger check. | `rules/survival.py:exempt` |
| `needs.no_water` | Never makes a thirst check. | `rules/survival.py:exempt` |

Each entry: `rule`, `from_level` (default 1), `value` (default true), `why` (read by nobody
but the next person).

### Permanent ability growth — `ability_growth` *(advanced)*

`ability`, `every`, `amount`, `why`. Read by `rules/leveling.py:level_up`, applied to the
base score so it survives every recompute. Blood Bond's "+2 Constitution every 5 levels".

### Pools *(advanced)*

Read by `rules/classes.py:pools_for` → `rules/resources.py:define`.

| Key | Meaning |
|---|---|
| `id` | What the sheet calls it. |
| `from_level` | When the character gets it. |
| `max` | **A formula**, so it resizes on a level-up instead of freezing: `floor(level/2) + con_mod`. May use `level`, `hit_dice`, `hp`, `hp_max`, `temp_hp`, `bab`, `control_blood`, `control_blood_a`/`_b`, any ability score or its `_mod`, and `floor`/`ceil`/`min`/`max`/`round`. Parsed by a whitelisted AST walk, never `eval`. |
| `starts` | `max`, or a number. |
| `refresh` | `rest.night`, `rest.any`, `encounter.end`, `round.start`, `never`. |
| `scope` | `self`, or `target` for a resource that lives on the enemy — blood stacks are applied by one ability and spent by four others. |
| `cap` | `none` for a pool with no ceiling. |
| `cooldown` | Rolled, not fixed: `1d3` turns. |
| `upkeep` | `{amount, resource}` — paid every round or the thing it sustains ends. |

### Spellcasting — `casting` *(advanced)*

Read by `rules/casting.py:caster_data`, **off the class file**, so a homebrew caster needs no
edit to the engine. `ability`, `kind` (`prepared`/`spontaneous`), `progression` (`full`,
`spontaneous_full`, `six_level`, `four_level`), `list` (which printed spell list), and
`prepare_from` (`spellbook` / `list` / `known`).

Slots become ordinary pools, so they refresh on a night, survive a save and show on the
sheet with no second mechanism. What a spell *does* is still its prose — the engine computes
the slots, the caster level and the DC, and hands the rest to the GM.

### Paths *(advanced)*

A map of **lower-case id** → path. This is the biggest piece of machinery a class can have.

| Key | Read by |
|---|---|
| `name`, `role`, `summary`, `global_rule` | The Class tab. |
| `tiers` | `"1"`–`"5"` → the ability names that unlock at each. `rules/leveling.py:find_ability`, `tier_needed`, `has_passive`; `play/views.py:_usable_abilities`. |
| `abilities` | Name → rules text, verbatim. Keyed by the **resolved** name. |
| `resolves` | Name-as-listed-on-a-tier → the ability it is. `Iron Clot (DR 8/-)` → `Iron Clot`. This is how five level-scaled variants share one paragraph and one effect list. |
| `effects` | Resolved name → a list of effect specs. `rules/leveling.py:resolve_effect` → `rules/engine.py:_op_use_ability`. |
| `passive` | Always-active abilities. `rules/leveling.py:is_passive` keeps them off the ability bar — clicking Swift Strikes as a button swallowed the attack it existed to modify. |
| `toggles` | Ability → condition name. A standing state with no clock, visible wherever conditions are. |
| `upgrades` | Tier-listed name → what it improves. The Class tab. |
| `core` | A tier name the Core Rulebook already defines (Uncanny Dodge). Tells the tab to say "see the rules reference" rather than "the source does not describe it". |
| `needs`, `undescribed`, `effects_converted` | **Nothing.** Provenance written by the importers. |

`max_paths` caps how many branches a character may take; left out, it is counted from the
tracks the level table grants.

---

## 2. How tiers actually unlock — read this before authoring paths

A path ability is usable when the character's tier **on that path** is at or above the
ability's tier. That tier is not level, and it is not stored on the sheet. It is counted off
the level table by `rules/leveling.py:control_blood`, which matches this regular expression
against every grant:

    control blood\s*(\d+)\s*([ab])

So:

- The phrase **`control blood`** is matched **literally**, whatever your class is called. A
  Storm Caller grants `control blood 1a` and reads it as "Squall Mastery 1" on the page if
  it likes, but the string in `grants` has to be that one.
- The letter is the **path slot**, not the path: the first path a character takes runs on
  the `a` track, the second on the `b` track. That is what makes "take one path, or both"
  work, and it is why `max_paths` is 2 for a table with both tracks.
- A class that declares paths and never grants a track has **zero usable abilities at every
  level** and looks perfectly healthy on screen. `validate_class` refuses it.

This is the one class-specific string left in an otherwise class-agnostic engine. See
Integration notes below.

---

## 3. Effects on a path ability

Effects use the shared vocabulary in `rules/effectspec.py` — the same one items, ingredients
and creatures use, and the same one the effect builder on the homebrew page generates forms
for. On top of it, the **class layer** adds three ways to say "this number comes from
somewhere else", filled in at resolve time by `rules/leveling.py:resolve_effect`:

| Extension | Means | Example |
|---|---|---|
| `dice_from` + `times` | Roll the class table's own column, multiplied. | `{"type": "damage", "dice_from": "blood", "times": 3}` — three times the Blood die at this level |
| `formula` | Evaluate against the sheet; the result becomes `amount`. | `{"type": "combat_mod", "target": "ac", "formula": "3 + control_blood"}` |
| `scales_by: "control_blood"` + `by_tier` | Pick the highest rung at or below the tier reached. | DR 2 at tier 1, DR 5 at tier 2, DR 8 at tier 3 — and **DR 8 at tier 4**, because tier 4 grants nothing new |

And one thing that is not an effect at all:

| `type: "engine_op"` | `op` | What `_op_use_ability` does |
|---|---|---|
| | `blood_pool` | Leaves a pool in the scene, under whoever it came out of |
| | `spend_pools` | Takes pools back off the ground; `count` is a number or `"all"` |

**What the engine actually executes** when an ability is used, today: `damage` (lethal and
non-lethal, and non-lethal is charged to the user as the cost), `heal`, `temp_hp`, the two
engine ops. `damage_reduction`, `combat_mod` and `apply_condition` are **reported in the
tell but not applied**. Everything else is counted and announced as "yours to narrate" —
never silently dropped.

---

## 4. Building a Blood-Bending-like class

Load the **path-based** scaffold (Storm Caller) at `/homebrew/classes/` and read it against
this list; it contains one of everything below.

1. **Identity and numbers.** Pick the id first and do not change it later.
2. **The level table.** Add a die column (`squall`) if abilities are going to scale off one.
   Put `control blood 1a` on the level the first path opens, `2a`, `3a`… where its tiers
   open, and the `b` set for the second path slot (Blood Bending opens `1b` at 11th).
3. **Paths.** Add a path with a lower-case id. Add abilities at a tier — the builder wires
   the `resolves` entry and a blank ability text at the same moment, because those are three
   maps in the file and one act to an author.
4. **Passives and toggles** on the ability line itself. A passive is never used; a toggle is
   a standing state and the condition name is what the sheet shows while it holds.
5. **Variants.** A level-scaled ability is several tier entries all resolving to one
   ability: `Stormskin (DR 2/-)` and `Stormskin (DR 5/-)` → `Stormskin`, with one paragraph
   and one `scales_by` effect between them.
6. **Effects** as JSON, keyed by the resolved name. Everything is checked live against
   `effectspec` plus the three extensions.
7. **Pools, overrides, ability growth** if the class's economy needs them.
8. **Save.** It is written to `<data>/homebrew/classes/<id>.json`, layered over what ships,
   and it is playable immediately — the creation forge offers it on the next load, with no
   restart.

---

## 5. Deliberately not supported

- **Multiclassing.** A character has one class. Nothing here would stop a second one being
  authored; there is nowhere to put it on the sheet.
- **Prestige classes and archetypes.** A class is a whole class. An archetype would be an
  overlay that swaps table entries, and no such mechanism exists.
- **More than five tiers, or a third path slot.** The level table carries two tracks of five.
- **Class features that are code.** A feature is text, a grant, an override from the list of
  six, a pool, or an effect spec. There is no place to write a condition that fires on
  another creature's turn — that is the reactions system, and it is not authorable.
- **A spell list of your own.** `casting.list` names a printed list. A new name is a list
  with no spells on it, so nothing would be castable.
- **Skill lists of your own.** `class_skills` is checked against the 35 skills the sheet
  computes.

## 6. Recorded but unread

Named in the schema with an empty consumer, because dropping them would lose them on a
round trip and describing them as read would be a lie the author discovers in play:
`source`, `alignment`, `starting_wealth`, an override's `why`, ability growth's `why`, a
path's `needs`, `undescribed` and `effects_converted`, and a casting block's `note`.

## 7. Known gaps in the shipped reference class

`validate_class` on `content/classes/blood-bending.json` reports **nine** problems as of
2026-08-24. They are real, and they are the file's, not the validator's:

- **Eight `save_gate` effects with no `dc`.** They were converted from the author's own
  sentences and carry a note reading `DC 10+12LVL+CONmod`, which is prose the engine cannot
  read. Written as a formula — `10 + level/2 + con_mod`, or whatever the author's intent
  turns out to be — they would resolve.
- **One `bonus_type: "armor"`** on Coagulated Plate. `effectspec.VOCAB` has no plain armour
  bonus at all: it lists `natural armour` and `shield` and nothing between them. Either the
  effect changes, or the vocabulary gains `armour` (see the integration notes).

A naive run of `effectspec.validate` over the same file reports 24. The other fifteen are
the class-layer extensions above and are not errors.

---

## 8. Integration notes

For anyone working in the files this document's implementation could not touch.

**`rules/registry.py` — the `classes` Kind.** It currently declares four fields (`hit_die`,
`bab`, `skill_ranks`, `class_skills`), which is a class with no level table, no paths, no
pools and no saves. `rules/classbuilder.py` exports the full classification for it:

```python
from . import classbuilder

"classes": Kind(
    id="classes", label="Character classes", folder="classes", key="classes",
    shipped_loader="rules.classes:all_classes",
    fields=list(classbuilder.registry_fields()),
),
```

`ClassField` subclasses `registry.Field`, so the registry needs no knowledge of any of
this — it reads `name`, `label`, `type`, `choices`, `help` and `required` exactly as it does
for a weapon and ignores `consumer`, `advanced`, `of` and the rest. Note that the class
editor's own types (`table`, `paths`, `map`, `object`, `group`, `formula`, `dice`, `tiers`,
`effects_map`) are **not** ones the generic homebrew form knows how to draw; the bench should
link to `/homebrew/classes/` rather than try. `play/homebrew.py:Bench.builder` derives
`"effects"` for every kind in `registry.KINDS`, so the classes bench currently offers the
flat effects form for something that is not a flat form.

**`play/homebrew.py`.** The classes bench's `waiting` text still reads "What a class still
cannot declare here is a path — its Coagulator and Blood Commander branches are not in the
file." Both statements are now false: the paths are in the file, and a class can declare
them. A link to `/homebrew/classes/` belongs on that card.

**`rules/leveling.py:control_blood`.** The literal `control blood` phrase is the only
class-specific string in the engine. The generalisation is small and backward compatible:
read a track name off the class (`d.get("track_name", "control blood")`) and build the regex
from it, so a Storm Caller's table can read `squall mastery 1a`. Everything else about paths
is already class-agnostic. Until that lands, `validate_class` tells the author to use the
phrase verbatim and says why.

**`rules/glossary.py:build`.** It treats a path's `upgrades` map as *name → the ability it
upgrades* (`abilities.get(base)`), while `play/templates/play/table.html` treats the same
map as *name → what the upgrade changes* — and the shipped data is the second. The glossary
entry for Greater Blood Rage therefore reads "Upgrade of +3 attack/damage, +3 Temp HP/HD."
One of the two should move; the schema documents the table's reading, because that is what
the data does.

**`rules/leveling.py:level_up`.** It ends with
`actor.rebuild_pools() if hasattr(actor, "rebuild_pools") else []`, and **no such method
exists on `Actor`** — so a pool's maximum does not resize on the level-up itself. It resizes
on the next `classes.apply`, which runs on every load, so the number is right by the time
anybody looks at the sheet. `tests/test_classbuilder.py` pins both halves rather than the
half that reads better.

**`rules/effectspec.py:VOCAB["bonus_type"]`.** No plain `armour` bonus type exists, which is
one of the nine problems above. Adding `"armour"` to that list would resolve Coagulated
Plate and is the only change in that file this work would ask for.

**`play/templates/play/table.html`.** Nothing is required. An authored class appears on the
Class tab, the level table, the glossary and the ability bar with no special-casing, because
all four read the class file by name rather than by a list of the classes they know. That
was verified by saving the Storm Caller scaffold through the builder and reading it back out
of `/api/create/options` in the running app.
