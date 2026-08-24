# Spells

3,040 spells ship with the app. Until now they were *readable* — school, descriptors, class
lists, a paragraph of English — and nothing more: a spell could be found, filtered and cast,
and what it then did was a paragraph for the GM to narrate. This document describes the
structured half that makes a spell a thing the engine can execute and a person can author.

Three files hold it:

| File | What it holds |
| --- | --- |
| `content/spells/spells.json` | The Spell Codex as imported. 3,040 entries, descriptive. Never rewritten. |
| `content/spells/spells-mechanics.json` | The mechanical half read out of the prose: 354 entries carrying `scaling` and `effects`. Layers over the above by id. |
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
| Carrying executable `effects` | **354** |
| — with a damage formula | 327 |
| — with a healing formula | 15 |
| — hand-written (buffs, magic missile) | 12 |
| Left as prose | **2,686** |
| Converted specs that fail `effectspec.validate` | **0** |

354 of 3,040 is 11.6%, and it is the honest ceiling of what regular prose gives up.

**It was 385 until the engine started rolling these numbers.** Executing the whole
converted corpus found 31 formulas that a spell *prints* but does not *deal by being cast*,
every one of them invisible for as long as `_op_cast` only narrated. Teleport dealt 1d10 to
whatever you aimed at, because its Mishap row says "You each take 1d10 points of damage".
Thorn body burned its target instead of whoever struck the caster. Blaze of glory, which
heals, was converted as damage because the book writes healing in the vocabulary of damage
— "healed for 1d6 points of damage/2 caster levels". That is CLAUDE.md's "verify end to
end, on real regenerated content" arriving exactly on schedule: the regex metrics said 385
with great confidence and 31 of them were wrong.

The refusals are keyed on **who takes the damage and when**, not on whether the sentence is
conditional. The first version of the veto *was* conditional-based and it refused caustic
eruption and fire storm — both of which deal precisely what they print, once, in an area.
The four categories, all in `spells._VETO_CLAUSE`:

| Category | Example | Spells |
| --- | --- | ---: |
| Mishap | teleport, dream travel — "Mishap: … you each take 1d10" | 2 |
| Retributive | thorn body, sacred nimbus — damage to whoever strikes *you* | 5 |
| A granted natural attack | savage maw's bite, shadow claws' claws — the dice belong to the attack | 13 |
| Repeats every round | call the void, fire of judgment — one hit understates it | 8 |
| Aimed at a third party, or inside a worked example | seer's bane, blood crow strike | 3 |

Everything else is left as prose on purpose:

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

### 5.1 `rules/engine.py` — `_op_cast` executes the effects  ✅ DONE

**Delivered.** `_op_cast` no longer states the numbers and stops. The boundary moved from
per-corpus to **per-spell**: a spell carrying effects is executed, a spell carrying none
takes exactly the path it always took, and an empty `spell.effects` is the honest signal
that this one's mechanics are English.

Three stages, in 1e's own order:

1. **The dice, once.** `spells.casting_plan(spell, caster_level)` reads *what* to roll out
   of the specs — the engine never walks spec shapes — and the caster rolls it a single
   time. A fireball is rolled once and everyone in the area saves against that number;
   rolling per target hands two creatures in one blast different damage. This is also why
   the halving could not simply reuse `_op_save`, which rolls its failure branch per save:
   that is right for a poison gate and wrong for an area spell.
2. **A saving throw per target**, rolled with that creature's own `save_modifiers` against
   the caster's real DC. `_roll_or_suspend_stage` now takes the actor who *makes* the roll,
   so the caster rolls the damage and each target rolls its own save, and the popup only
   ever opens for a roll the player is entitled to make.
3. **The damage**, through `_apply_damage` like every other point of damage in the game —
   so resistance, damage reduction, temporary hit points and interception all apply without
   a line of their own in `_op_cast`.

The three substitutions, as resolved:

1. **The save DC** is `casting.save_dc(actor, level)`. `spells.SAVE_DC_FORMULA` never
   reaches a comparison; `test_the_dc_is_the_casters_own_and_not_the_formula_string` pins
   both halves of that.
2. **The halving** is `rolled // 2` applied to the total that was actually rolled, in
   `_op_cast`, because that is the only place the number exists. `negates` gives 0 on a
   success. `partial` applies **nothing** on a success and says so on the tell — a partial
   save reduces the spell by an amount the spell's own text owns, and inventing one would
   be the failure this whole schema exists to avoid.
3. **Spell resistance did not land, deliberately.** It needs an SR *number* on the creature
   to check `1d20 + caster level` against, and `Actor` has no such field — `bestiary`
   drops it and `rules/creature_effects.py` records it as a `narrative` spec. Adding the
   field means `rules/sheet.py` and `rules/bestiary.py`, which is not a contained change,
   and a half-check that sometimes ignored SR would be worse than a gap everybody can see.
   The printed line is still reported on the outcome exactly as before.

The `cast` effect carries `element`, `dice` (the scaled notation), `range_feet`, the scaled
`effects` themselves, and `effects_converted` — which is the one a GM most needs, because
354 of these numbers were read by a machine and nobody has checked them.

**Still not applied: the non-damage riders.** Bless's +1 morale bonus, barkskin's natural
armour, the six ability boosts. `casting_plan` returns them under `riders` and `_op_cast`
renders them onto the tell for the GM rather than applying them, because `_op_buff` needs a
duration in **rounds** and a spell's duration is still prose — `"minutes/level (1)"`. The
next contained step is a `duration_value` on the spell, derived from that line the way
`range_value` is derived from the range line; then the riders can go through
`consumables._spec_to_intents` as sub-intents, exactly as `_op_use_item` already does, with
no second copy of the spec→intent mapping.

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
- **`search(executable=True)`** filters to the 354 spells the engine can resolve.

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

It now does exactly that, for 354 spells. This is the second time this blurb has aged past
its subject — it previously read "no spell system" — which is the hazard the test
`test_the_bench_says_where_the_engine_stops` exists to record. The honest replacement is
something like: *354 spells carry effects the engine can roll; the other 2,686 are prose, and
what a converted one does can be corrected on this bench.*

### 5.5 `play/homebrew.py` — most spells cannot be opened by clicking

`rows_for("spells")` caps the shipped listing at the first 200 spells alphabetically, so the
bench's clickable rows stop at "Ablative…". Fireball cannot be opened from the page at all,
even though `/api/bench/spells/open/fireball` serves it correctly. The bench's own search
pane finds any spell but its rows are not wired to the editor. Wiring the search results to
`data-open` would make all 3,040 editable, which matters most for the 354 whose effects a
machine wrote.

### 5.6 `rules/effectspec.py` — the `spell_effect` type's `blocked` text

It says "the engine has no spell system: this is recorded and narrated, and nothing will cast
it". The engine does have a spell system now (slots, caster level, DCs, and effects for 354
spells); what is still true is that `spell_effect` itself has no op. The sentence should be
narrowed rather than deleted.

### 5.8 `rules/intents.py` — `cast` should default to `visibility: "player"`

The op table declares `"cast": (("spell",), (…), "hidden")`. That was right while a cast
rolled nothing. It is now the exact trap the `"attack"` entry two lines above documents:

> `player`, because the PC rolls their own to-hit and their own damage. Defaulting this to
> `hidden` meant the engine silently rolled the player's attacks for them, which
> contradicts the architecture decision outright.

A PC's fireball is in the same position. The mechanism is already in place — a cast
declared `visibility: "player"` suspends for the player's dice and resumes correctly, and
`_force_visibility` still demotes every non-PC caster to hidden — so this is one word.

**It was left alone deliberately**, because `rules/intents.py` was not in scope and the
change is not free: five tests in `tests/test_casting.py` call `cast(e, "fireball")` and
read `.outcomes[0]`, which becomes an empty list the moment the cast suspends. They would
need to resume through the popup the way the attack tests do. Worth doing together, in one
change, by whoever owns both files.

### 5.9 `tests/test_casting.py` — one docstring is now false

`test_the_outcome_states_the_facts_and_not_the_damage` still passes: it reads
`effects[0]`, the cast effect stays first, and it carries no `damage` or `amount` key. But
its docstring says

> The engine will not read "1d6 per caster level" out of English prose and turn it into a
> number — anything mechanical arrives as its own validated intent.

which is no longer true for 354 spells. A test that passes while its stated reason is false
is the same hazard as the bench blurb in §5.4, and it is the third time this particular
sentence has aged. What is still true, and worth keeping a test for, is narrower: the *cast
effect itself* states facts and never damage, because the damage arrives as its own effects
beside it.

### 5.10 `rules/engine.py` — `_op_save` could take a pre-rolled total

The halving rule now exists in two places: `_op_save` rolls its failure branch and halves
it for a poison gate, and `_op_cast` halves the total it already rolled for an area spell.
They are not the same code because they are not the same situation — one roll per save
versus one roll shared across everything in the blast — but they are the same *rule*, and
CLAUDE.md is specific about what happens to a rule with two copies. Giving `_op_save` an
optional pre-rolled total would let the cast path call it and leave one copy.

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
