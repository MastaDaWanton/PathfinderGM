# Spells

3,040 spells ship with the app. Until now they were *readable* — school, descriptors, class
lists, a paragraph of English — and nothing more: a spell could be found, filtered and cast,
and what it then did was a paragraph for the GM to narrate. This document describes the
structured half that makes a spell a thing the engine can execute and a person can author.

Three files hold it:

| File | What it holds |
| --- | --- |
| `content/spells/spells.json` | The Spell Codex as imported. 3,040 entries, descriptive. Never rewritten. |
| `content/spells/spells-mechanics.json` | The mechanical half read out of the prose: 385 entries carrying `scaling` and `effects`. Layers over the above by id. |
| `rules/spells.py` | The schema, the derivations, the conversion, and `validate_spell` for a UI to call. |

---

## 1. The schema

### Derived, or stored — and why the line is where it is

**Derived at load, never written down.** Anything that is a re-reading of a fact the corpus
already states is computed by `spells.normalise()` every time the shelf loads:

| Field | Read from |
| --- | --- |
| `element` | the energy descriptors, then a converted formula's damage type |
| `level_available` | `lists` + the `domain`, `bloodline` and `patron` columns |
| `spellbooks` | `lists` |
| `range_value` | the printed `range` line |
| `area_value` | the printed `area` line, then `effect` |
| `save`, `save_effect`, `save_harmless` | the printed `saving_throw` line |
| `sr` | the printed `spell_resistance` line |

Storing any of these would put one fact in two places. That is the failure
`rules/creature_effects.py` names about `reductions`: correcting one copy leaves the other
saying the old thing, and nothing reports the disagreement.

**Stored in a file, and flagged.** Anything that is a *machine's guess at English prose* —
`scaling` and `effects` — is written into `spells-mechanics.json` with
`effects_converted: true`. An effect derived at read time is silently overwritten the moment
somebody corrects it, which is exactly why the ingredient corpus stopped deriving at read
time and started shipping a file.

**An authored value always wins.** Every derivation fills a field only when it is absent.

### The fields

```
element          "" | acid | cold | electricity | fire | force | negative | positive
                 | sonic | untyped

level_available  [ {"via": "class"|"domain"|"bloodline"|"patron"|"mystery"
                            |"elemental school",
                    "name": "wizard",        # the class, domain, bloodline, …
                    "level": 3,              # the SPELL level it is granted at
                    "at": 7, "of": "sorcerer"}   # …and the class level, where the
                 ]                               #    source printed one instead

spellbooks       ["sorcerer/wizard", "magus", …]  — the 1e list names

scaling          {"kind": "damage" | "healing",
                  "die": 6,               # d6
                  "dice_per": 1,          # 1d6 …
                  "per_levels": 1,        # … per this many caster levels
                  "cap_dice": 10,         # never more than 10d6
                  "base_dice": 0,         # dice that do not scale (acid arrow's 2d4)
                  "flat_bonus": 0,        # points that do not scale (magic missile's +1)
                  "bonus_per_level": 0,   # points that do (cure light wounds' +1/level)
                  "bonus_cap": 0,         # (maximum +5)
                  "damage_type": "fire",
                  "lethality": "lethal" | "nonlethal"}

range_value      {"kind": "close"|"medium"|"long"|"touch"|"personal"|"fixed"
                          |"per_level"|"unlimited",
                  "feet": 400, "add": 40, "every": 1, "unit": "feet"}

area_value       {"shape": "spread"|"burst"|"emanation"|"cylinder"|"radius"|"cone"
                           |"line"|"cube"|"square"|"wall",
                  "radius": 20, "length": 60, "unit": "feet",
                  "origin": "you"|"point"}

save             "" | fort | ref | will
save_effect      "" | none | negates | half | partial | disbelief | see text
save_harmless    true where the save is there for an unwilling ally
sr               true | false | null   (null where the line says "see text" or nothing)

effects          [ … effectspec specs … ]
effects_converted  true while a machine's reading stands unreviewed
```

### `scaling` is five shapes in one dict

The corpus writes the same idea five ways, and a single "dice per level" field would be
wrong for four of them:

| Spell | Prose | Fields |
| --- | --- | --- |
| fireball | 1d6 per caster level, max 10d6 | `dice_per 1, per_levels 1, cap_dice 10` |
| searing light | 1d8 per **two** caster levels, max 5d8 | `dice_per 1, per_levels 2, cap_dice 5` |
| acid arrow | 2d4, flat | `base_dice 2` |
| magic missile | 1d4+1, flat | `base_dice 1, flat_bonus 1` |
| cure light wounds | 1d8 + 1 point per level, max +5 | `base_dice 1, bonus_per_level 1, bonus_cap 5` |

`spells.scaling_dice(spell, caster_level)` turns any of them into the dice actually rolled —
`"10d6"`, `"1d8+5"`, `"2d4"` — capped, and never fewer than one die. A formula per two levels
at caster level 1 is the spell at its smallest, not a spell that does nothing.

### `level_available`: a domain grants a level exactly as a class list does

The corpus prints three grant columns and **the number does not mean the same thing in all
three**. Reading them alike would have made fireball a 7th-level bloodline spell.

| Column | Example | What the number is | Spell level |
| --- | --- | --- | --- |
| `domain` | `Fire (3)` | the spell level | 3 |
| `bloodline` | `Efreeti (7)` | the *sorcerer* level the bonus spell arrives at (odd, 3–19) | `(n-1)/2` = 3 |
| `bloodline` | `Aberrant (BloodRager) (16)` | the *bloodrager* level (7, 10, 13, 16) | `(n-4)/3` = 4 |
| `patron` | `Elements (6)` | the *witch* level (even, 2–18) | `n/2` = 3 |

Both numbers are kept: `level` is the spell level, `at` is the class level the book printed,
and `of` names whose level it is. 452 domain, 249 bloodline and 280 patron grants come out of
the corpus this way, for free.

`mystery` and `elemental school` are in the vocabulary and carry **no shipped data** — the
Codex export has no columns for them. They are authorable and empty rather than guessed at.

---

## 2. The request's tag notation, mapped

The feature was asked for in a tag notation, using Fireball as the worked example. Every tag
maps onto a real field. `tests/test_spells.py::test_fireball_answers_every_tag_in_the_request`
is this table made executable — if the schema drifts from the notation, that test names which
tag drifted.

| The tag as written | The field | Fireball's value |
| --- | --- | --- |
| `{SCHOOL : evocation}` | `school` | `"evocation"` |
| `{ELEMENT : fire}` | `element` | `"fire"` — derived from the `[fire]` descriptor |
| `{SPELLBOOK : sorcerer/wizard}` | `spellbooks` | `["sorcerer/wizard", "arcanist", "bloodrager", "magus", "occultist"]` |
| `{LEVEL_AVAILABLE : {sorcerer/wizard : 3}}` | `level_available`, `via: class` | wizard 3, sorcerer 3, +4 more |
| `{{Domain : fire} : 3}` | `level_available`, `via: domain` | `{"via": "domain", "name": "fire", "level": 3}` |
| `{{Bloodline : efreeti} : 3}` | `level_available`, `via: bloodline` | `{… "level": 3, "at": 7, "of": "sorcerer"}` |
| `{{Mystery : flame} : 3}` | `level_available`, `via: mystery` | authorable; no shipped data |
| `{{Elemental School : fire} : 3}` | `level_available`, `via: elemental school` | authorable; no shipped data |
| `{Casting Time : 1_standard action}` | `casting_time` | `"standard action"` |
| `{Components : Verbal, Somatic, Material}` | `components` | `["V", "S", "M"]` |
| `[Range] : long (400 ft. + 40 ft./level)` | `range` + `range_value` | `{"kind": "long", "feet": 400, "add": 40, "every": 1}` |
| `[Area] : 20-ft.-radius spread` | `area` + `area_value` | `{"shape": "spread", "radius": 20, "unit": "feet"}` |
| `[Duration] : instantaneous` | `duration` | `"instantaneous"` |
| `[Saving Throw] : Reflex half` | `save`, `save_effect` | `"ref"`, `"half"` |
| `[Spell Resistance] : yes` | `sr` | `true` |
| `[Damage] : 1d6/caster_lvl` | `scaling` | `{die 6, dice_per 1, per_levels 1, cap_dice 10}` |

The braces were not kept as a file format, for one reason: nothing needs to parse them, and
a notation with nesting is a notation with a parser to maintain. **The notation is accepted
anyway** where a person would type it — `parse_level_available` strips `{`, `}` and `:` as
punctuation, so a line pasted straight out of the tag list above is read rather than reported
as an error.

---

## 3. What the conversion covered

Measured over the whole corpus, and pinned in
`tests/test_spells.py::test_the_conversion_covers_what_it_claims_and_no_more`:

| | Count |
| --- | ---: |
| Spells in the corpus | **3,040** |
| Carrying executable `effects` | **385** |
| — with a damage formula | 359 |
| — with a healing formula | 14 |
| — hand-written (buffs, magic missile) | 12 |
| Left as prose | **2,655** |
| Converted specs that fail `effectspec.validate` | **0** |

385 of 3,040 is 12.7%, and it is the honest ceiling of what regular prose gives up.
Everything left is left on purpose:

- **Gated on our own tags.** A spell is only converted if it carries the `damage` or
  `healing` tag. Relaxing that gate to catch magic missile (whose corpus tags say `utility`)
  also caught constricting coils, black tentacles and summon stampede — three per-round
  effects out of five extra spells, all three of which would have been flattened into a
  single hit. Magic missile is hand-written instead.
- **`dot` is a refusal.** `effectspec` has no repeating-damage type beyond `bleed`, and
  turning "2d4 each round" into one 2d4 hit understates the spell by however many rounds it
  runs. 74 spells are refused this way, acid arrow among them.
- **An unrecognised energy word is a refusal, not a guess.** "magical slashing", "dexterity
  and strength" and "hit points of" all appear where the damage type should be. Picking the
  nearest damage type is how a spell ends up dealing the wrong kind with nobody able to see
  why.
- **"an additional 1d4 points of acid damage"** is vetoed by the words before it. On acid maw
  that phrase is a rider on a companion's bite, not the spell's own damage.
- **A maximum is only read within 140 characters of its formula.** Acid pit says "a maximum
  depth of 100 feet" two sentences later, and an unbounded search finds it.

Coverage of the other derived fields, which is much higher because they read structured
columns rather than prose:

| | Spells | Grants |
| --- | ---: | ---: |
| `level_available` via a class list | 3,034 | 21,257 |
| `level_available` via a domain | 452 | 669 |
| `level_available` via a bloodline | 249 | 380 |
| `level_available` via a patron | 280 | 333 |
| — at least one non-class grant | 633 | |
| `element`, from an energy descriptor | 275 | |
| `element`, from a converted formula (all negative and positive arrive here) | 195 | |
| `range_value` | 2,963 | |
| `area_value` | 418 | |
| `save` parsed to fort/ref/will | 1,728 | |
| `sr` true / false / null | 1,705 / 847 / 488 | |
| `spellbooks` | 3,020 | |

The element count deserves saying plainly, because the brief expected "thousands of spells for
free" from the descriptors and **the corpus does not contain that**. Only six of the 28
canonical descriptors are energy types, and they appear on 275 spells between them —
`[mind-affecting]` (436), `[evil]` (138) and `[emotion]` (101) are the common ones and none of
them is an element. 470 spells end up with an element, 195 of those from a converted damage
formula rather than from a descriptor. The other 2,570 have none, because they have none.

### The twelve hand-written entries

`rules.spells.CURATED`, written one at a time because their prose says "+4 armor bonus to AC"
in a sentence and no pattern reading that would stop at these twelve. They are **not** flagged
`effects_converted`: a person wrote them, which is a different state from "a machine read the
prose and nobody has checked".

bless · mage armor · shield of faith · barkskin · resist energy · magic missile ·
bull's strength · cat's grace · bear's endurance · fox's cunning · owl's wisdom ·
eagle's splendor

Cures are *not* in this list — cure light/moderate/serious/critical wounds and their mass
versions convert mechanically, because "cures 1d8 points of damage + 1 point per caster level
(maximum +5)" is a regular sentence.

---

## 4. Authoring one in the app

**Homebrew → Spells → the form.** The `spells` Kind in `rules/registry.py` declares twenty
fields and the builder page draws every input from that declaration, so the form is the tag
list above:

Name · Description · **School** (dropdown, 9) · Subschool · **Element** (dropdown, 9) ·
Descriptors · **Available at** (textarea) · Casting time · **Components** (checkboxes,
V/S/M/F/DF) · Material cost · Range · Area · Effect · Targets · Duration · **Dismissible**
(dropdown) · Saving throw · Spell resistance · **Damage or healing formula** · Effects ·
Source

Two of those are mappings to the engine and text in the form, because the builder has six
field types — text, textarea, number, choice, list-of-fixed-choices, effects — and none of
them edits a mapping. `spells.derive()` renders them out and `spells.normalise()` reads them
back:

**Available at** — one per line, ending in the spell level:

```
wizard 3
sorcerer 3
domain fire 3
bloodline efreeti 3
patron elements 3
mystery flame 3
elemental school fire 3
```

A **class** line is what makes the spell castable: `normalise` writes it into `lists`, which
is the field `rules/casting.py` reads. A spell whose editor said "wizard 3" and whose `lists`
stayed empty would fail `casting.knows` silently — the same failure a homebrew ingredient hit
before the registry existed, where it appeared in the editor when reopened and never reached
play.

**Damage or healing formula** — the book's own notation:

```
1d6/level, max 10d6 fire      →  fireball
1d8/2 levels, max 5d8         →  searing light
2d4 acid                      →  acid arrow
1d8+1/level, max +5           →  cure light wounds
```

**Verified end to end in the running app**, not only in tests: a spell was typed into the real
form at `localhost:8731`, saved to
`%LOCALAPPDATA%\PathfinderGM\homebrew\spells\`, reloaded through `spells.get()`, and came back
with `lists {"wizard": 2}`, `element "fire"`, `area_value {"shape": "burst", "radius": 10}`,
35 ft of range at caster level 5, `5d6` at caster level 5 and `6d6` at 10 — and
`casting.knows()` answering True with a save DC of 16.

**Before saving**, a UI should call `spells.validate_spell(entry) -> list[str]`. It returns
every problem at once rather than the first, for the reason `effectspec.validate` does: a
builder that reports errors one at a time is a builder nobody finishes. It refuses a school
that is not a school, an element that is not an element, a component that is not a component,
a descriptor the book does not have, a spell level outside 0–9, dice that are not dice, an
invalid effect spec — and a level on a class that does not exist, which is not a spell with an
unusual class but a spell nobody can ever cast.

---

## 5. INTEGRATION NOTES

Everything below is in a file this work was not allowed to touch. Each is a specific change
with the reason it is needed.

### 5.1 `rules/engine.py` — `_op_cast` must execute the effects

`_op_cast` today spends the slot, computes caster level and save DC, and stops, "because a
parser guessing mechanics out of three thousand English paragraphs would produce confident
wrong numbers". That reasoning was right and is now narrower: 385 spells carry validated,
executable specs and 2,655 still do not. **The boundary should move to per-spell rather than
per-corpus** — execute what carries effects, narrate what does not.

Concretely, after the slot is spent:

```python
cl = casting.caster_level(actor)
specs = spells_mod.effects_at(spell, cl)      # dice already scaled for this caster
```

Three things `effects_at` hands back need the engine's own numbers substituted:

1. **The save DC.** A `save_gate` carries `dc: "10 + spell level + casting ability modifier"`
   — the string constant `spells.SAVE_DC_FORMULA` — because a spell cannot know the caster's
   ability modifier. Replace it with `casting.save_dc(actor, level)`, which `_op_cast`
   already computes.
2. **The halved branch.** `on_success` on a "Reflex half" spell carries *half the dice*
   (`5d6` where the failure branch has `10d6`). `effectspec` has no way to say "roll the
   full dice and halve the total", and the two have the same mean, floor and ceiling — but
   the engine *does* have the rolled total, so it should roll `on_failure` once and halve it
   rather than rolling the success branch separately. Same expected damage, correct variance,
   and one roll shown to the player instead of two.
3. **Spell resistance.** `spell.sr` is now a real tri-state (`true` / `false` / `null` where
   the source will not say). Nothing in the engine checks SR yet; `rules/creature_effects.py`
   already records each creature's SR as a `narrative` spec, named exactly so this is
   greppable when the check is built.

The `cast` outcome should also carry what it now can: `effects` (the scaled specs),
`element`, `scaling_dice(spell, cl)` as a string for the log, and
`spells.range_feet(spell, cl)`.

**Do not execute a spell with no effects.** `spell.effects` being empty is the honest signal
that this spell is one of the 2,655 whose mechanics are prose; the current narrate-only path
is still exactly right for it. And **show `effects_converted`** — 385 of these were read by a
machine and nobody has checked them, so a GM should be able to see which.

### 5.2 The play page

- **Range and area are drawable now.** `spells.range_feet(spell, caster_level)` gives feet
  (rounding down to the whole increment, as 1e does: close range at caster level 5 is 35 feet,
  not 37), and `spell.area_value` gives `{"shape": "spread", "radius": 20}`. The grid can put a
  real template on the map instead of printing "20-foot-radius spread".
- **Offer the damage before it is rolled.** `scaling_dice(spell, cl)` is the one string a
  player wants on the cast button: "Fireball — 10d6, Reflex DC 19 for half".
- **`search(klass=…)` now matches a domain, bloodline or patron as well as a class list.** A
  cleric with the Fire domain can be shown what their domain grants, which was impossible
  before `level_available` unified the four.
- **`search(executable=True)`** filters to the 385 spells the engine can resolve.

### 5.3 `rules/effectspec.py` — two vocabulary gaps found

Both were hit by real spells and both are one line:

1. **`VOCAB["bonus_type"]` has no armour bonus.** It has `shield`, `deflection` and
   `natural armour` and stops there. Mage armor grants a +4 *armour* bonus to AC, so it is
   currently written `untyped` with a note — which stacks with worn armour when it must not.
   Adding `"armour"` to that tuple fixes it, and `CURATED["mage-armor"]` should then change
   with it.
2. **No effect type takes a parameter chosen at casting.** Resist energy protects against
   "one of five energy types you select", and `resistance` demands its `target` up front.
   Writing `resistance fire` would invent a choice the caster makes, so it is a `narrative`
   spec instead. A `choice_at_cast` field, or a `resistance` whose target may be a list, would
   make it executable.

Neither is urgent. Both are recorded because the alternative was a silently wrong number.

### 5.4 `play/homebrew.py` — the spell bench blurb is now stale

```
"Castable now: slots, caster level and save DCs are the engine's. What a spell still
 does is its prose — the engine will not read \"1d6 per caster level\" out of English
 and turn it into a number."
```

It now does exactly that, for 385 spells. This is the second time this blurb has aged past
its subject — it previously read "no spell system" — which is the hazard the test
`test_the_bench_says_where_the_engine_stops` exists to record. The honest replacement is
something like: *385 spells carry effects the engine can roll; the other 2,655 are prose, and
what a converted one does can be corrected on this bench.*

### 5.5 `play/homebrew.py` — most spells cannot be opened by clicking

`rows_for("spells")` caps the shipped listing at the first 200 spells alphabetically, so the
bench's clickable rows stop at "Ablative…". Fireball cannot be opened from the page at all,
even though `/api/bench/spells/open/fireball` serves it correctly. The bench's own search
pane finds any spell but its rows are not wired to the editor. Wiring the search results to
`data-open` would make all 3,040 editable, which matters most for the 385 whose effects a
machine wrote.

### 5.6 `rules/effectspec.py` — the `spell_effect` type's `blocked` text

It says "the engine has no spell system: this is recorded and narrated, and nothing will cast
it". The engine does have a spell system now (slots, caster level, DCs, and effects for 385
spells); what is still true is that `spell_effect` itself has no op. The sentence should be
narrowed rather than deleted.

### 5.7 Rebuilding the mechanics file

`spells-mechanics.json` is generated. After any change to the conversion:

```python
from rules import spells
spells.write_mechanics()      # returns the coverage report
```

`test_the_converted_file_is_what_the_converter_produces` fails if the shipped file and the
converter disagree, because the file is what loads and the function is what the coverage
tests measure. They drifted apart in the ingredient corpus and the difference was invisible
until a bench showed the old text.
