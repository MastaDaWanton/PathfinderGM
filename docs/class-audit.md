# Class audit — every class, every level, measured

Audit of 2026-10-05, branch `audit/classes` off local master `1f88ada`. **No code or content
was changed.** Everything below was measured by running Python against the real app: the
Django test client over the real endpoints, a scratch `PATHFINDER_GM_DATA`, and the engine
run directly where an op had to be fired. Nothing is estimated; where a claim is a reading
of code rather than a measurement it says so.

The owner's request, verbatim: *"do a pass over all available classes and class abilities
make sure they work and are accessible. for example choosing a domain as a cleric or a
bloodline as a sorcerer. make sure choosing feats and assigning ability points works as a
part of leveling up."*

## The answer in one screen

- **Feats, ability points and spells at level-up work.** 36 characters (11 core classes plus
  Blood Bending, under the book and both house rules) were created through
  `/api/character/create` and levelled 1→20 through `/api/level-up`: **684 level-ups, 774
  feats, 900 ability points and 327 spells taken through the real endpoints, 0 failures, 0
  counts that disagreed with the book or the house rule.** A Constitution point raised hit
  points for every Hit Die already earned in all 36 checks.
- **Skill ranks after 1st level cannot be placed at all.** Nothing owes them, nothing offers
  them, and no endpoint writes them. A 20th-level human barbarian in these runs has the
  **5 ranks** she was made with. The book gives her **100**. This is the worst level-up
  defect, and it hits every class.
- **The cleric's domains and the druid's nature bond are the only class choices that can
  be made.** Bloodline, arcane school, arcane bond, rage powers, rogue talents, mercies,
  divine bond, favoured enemy, favoured terrain, combat style, hunter's bond, weapon
  training and versatile performance have **no picker anywhere**:
  - The forge has no field for them.
  - Sent as `class_choices`, the forge refuses them by name: `'bloodline' is not a choice a
    sorcerer makes; it makes none.`
  - Sent as a top-level key (`"bloodline": "draconic"`), they are accepted and silently
    dropped (200).
  - The class-choice grammar is only ever asked at 1st level (`creation.class_choice_menu`
    → `choices_for(cid, 1)`), and nothing writes `class_choices` after creation.
- **A core class's active abilities cannot be used as actions.**
  - Rage, smite evil, lay on hands, ki, wild shape and bardic performance exist only as pool
    counters. Every one refills on a night's rest, and the generic `resource` op decrements
    it.
  - No op applies their effect.
  - `use_ability` refuses all 14 names tried on every core class: `has no ability called
    rage. They can use: nothing yet.`
  - The ability bar is built for path classes only (`play/views.py:500`).
  - The GM brief lists path abilities only (`gm/prompts.py:1281`). The narrator is never
    told the pools exist.
  - Channel energy and stunning fist do not even have a pool.
- **Passive class numbers mostly never reach the sheet.** Measured at 20th level:
  - The barbarian moves at 30 ft with no damage reduction.
  - The paladin has no Charisma on any save.
  - **The monk punches at −4 "not proficient with unarmed strike", for 1d3, at every level
    1–20, with no Wisdom in his AC.**
- **Counts:** 19 choices cannot be made (A), 3 choices are offered with no mechanics behind
  them (B), 91 features are bare strings (C), 9 are pool-only, and there are 10 distinct
  level-up defects (D). The ranked list is §6, and suggested fix lanes are §8.

---

## 0. Method

| What | How | Where |
|---|---|---|
| Level 1→20, every class, three house rules | `/api/homebrew/rules` set to off, `bonus_feats: odd` with `bonus_ability_points: even`, and every/every. Then `/api/character/create` (`begin: true`), then for each level 2-20: `/api/level-up`, `/api/sheet`, `/api/level/feats?pool=`, `/api/level/feats/take`, `/api/level/points`, `/api/spells/learnable`, `/api/spells/learn`, and `/api/sheet` again. | scratchpad `levelrun.py` |
| XP | **No endpoint grants XP** (only the GM's `xp` op). The harness set `pc.xp = xp.total_for(next)` on the live campaign and saved it before each `/api/level-up`. This is the one step not driven over HTTP. | |
| Forge refusals | 22 `/api/character/create` bodies probing each choice | `forgeprobe.py` |
| Engine numbers per level | `creation.build` → `leveling.level_up` ×19 → `full_sheet`. Pools, slots, AC terms, save terms, speed, DR, `class.*` tags. | `playprobe.py` |
| Abilities in play | `Engine.run` with `resource` spend on every pool, `use_ability` on 14 class-ability names, then `rest` (night) | `playprobe.py` |
| Companions, class-feature prerequisites, ranks, sleeping to level | over HTTP | `finalprobe.py` |
| Spell tables | `rules/casting.py` tables cell by cell against d20pfsrd, fetched 2026-10-05 | `tables.py` |

The scripts live in the session scratchpad and are not committed (the brief: one doc, no
code). Each is under 250 lines and is reproducible from the description above.

"Owed, book" means the run with the house rules off. Feats were picked from the first open
row the menu offered; points went to Constitution whenever that raised the modifier, and
otherwise to the casting or attack ability.

Sources:
- **Class pages fetched 2026-10-05:**
  [barbarian](https://www.d20pfsrd.com/classes/core-classes/barbarian/),
  [bard](https://www.d20pfsrd.com/classes/core-classes/bard/),
  [cleric](https://www.d20pfsrd.com/classes/core-classes/cleric/),
  [monk](https://www.d20pfsrd.com/classes/core-classes/monk/),
  [paladin](https://www.d20pfsrd.com/classes/core-classes/paladin/),
  [ranger](https://www.d20pfsrd.com/classes/core-classes/ranger/),
  [sorcerer](https://www.d20pfsrd.com/classes/core-classes/sorcerer/),
  [wizard](https://www.d20pfsrd.com/classes/core-classes/wizard/).
- **Checked earlier and not re-fetched:**
  [fighter](https://www.d20pfsrd.com/classes/core-classes/fighter/) and
  [rogue](https://www.d20pfsrd.com/classes/core-classes/rogue/) (2026-09-20,
  `docs/hollow-classes.md`), and
  [druid](https://www.d20pfsrd.com/classes/core-classes/druid/) (2026-10-04, the class
  file's `_note_wild_shape`).
- **Archives of Nethys:** the same classes at `https://aonprd.com/ClassDisplay.aspx?ItemName=<Class>`.
  These are cited as the equivalent page and were **not** fetched.
- **Choice catalogues:** the option lists live on sub-pages
  ([rage powers](https://www.d20pfsrd.com/classes/core-classes/barbarian/rage-powers/),
  [rogue talents](https://www.d20pfsrd.com/classes/core-classes/rogue/rogue-talents/),
  [bloodlines](https://www.d20pfsrd.com/classes/core-classes/sorcerer/bloodlines/),
  [arcane schools](https://www.d20pfsrd.com/classes/core-classes/wizard/arcane-schools/),
  [domains](https://www.d20pfsrd.com/classes/core-classes/cleric/domains/)). These are cited
  for location and were not fetched in this audit.
- **Blood Bending:** the author's PDF, as imported into `content/classes/blood-bending.json`.

### How a class feature reaches the engine (what "mechanics" means below)

1. **The class table's `grants` become tags.** Every grant string becomes a tag
   `class.<slug>` (`rules/classfeatures.py:99 tags_for`), joined into
   `Actor.standing_tags` (`rules/sheet.py:3410`). A feature has mechanics only if
   something *asks* that tag. Exactly five tags are asked:
   - `uncanny-dodge`: `rules/engine.py:13654 _flat_footed` → `classfeatures.caught_flat_footed`
   - `improved-uncanny-dodge`: `rules/position.py:150`
   - `evasion` and `improved-evasion`: `rules/engine.py:4780` (`_op_save`)
   - `unarmed-strike`: `rules/sheet.py:2261`, the lethality swap only

   Separately, sneak attack's dice are read off the table by `rules/precision.py:67`, and a
   `bonus feat` row is counted by `rules/leveling.py:697`.
2. **Pools** (`pools` in the class file) become resources (`rules/classes.py:420`), refill
   on `rest.night` (`rules/engine.py:15325`), and are spent by the generic `resource` op
   (`rules/engine.py:7634`).
3. **Spellcasting** comes from `rules/casting.py` (`CASTERS`, `PROGRESSIONS`, `slots_for:338`,
   `domain_slots_for:389`, `learning:577`).
4. **Choices** come from `rules/classes.py:143` `CHOICE_KINDS = ("domain", "animal companion")`.
   Those are the only two option kinds.
5. **The sheet** prints every grant as a line (`class_features` and `progression.rows`).
   16 names also have popover text (`rules/glossary.py`). "Line" in the matrices means
   *printed, nothing derived from it*.

**The slug splits ladders into unrelated tags.** `classfeatures._NUMBER` (`:73`) strips a
trailing `+2`, `3d6` or `(…)`, but not `/day`, `ft` or `/-`. So:
- paladin smite evil becomes 7 tags, `class.smite-evil-1-day` through `class.smite-evil-7-day`
- druid wild shape becomes 10 tags
- monk slow fall becomes 9 tags
- barbarian damage reduction becomes 5 tags
- bard lore master becomes 3 tags
- the monk's "fast movement +10 ft" becomes `class.fast-movement-10-ft`

Any future reader asking the prefix `class.smite-evil` finds nothing. This is not a defect
today only because no reader asks these.

---

## 1. Matrices, class by class

Columns:
- **Choice**: whether the book makes the player pick.
- **Forge / Lv-up / Valid.**: whether the choice is offered at creation, offered at
  level-up, and validated.
- **Mechanics**: what reads the feature, at `file:line`.
- **Sheet**: what reaches the sheet.
- **Play**: what an op does with the feature.
- **Gap**: OK, **P** (pool only), **A** (a choice that cannot be made), **B** (offered with
  no mechanics), or **C** (a bare string).

The source for every row is the class page linked in §0, unless the row names another.

### Barbarian ([d20pfsrd](https://www.d20pfsrd.com/classes/core-classes/barbarian/))

| Feature (lv) | Choice | Forge / Lv-up / Valid. | Mechanics | Sheet | Play | Gap |
|---|---|---|---|---|---|---|
| Fast movement (1) | no | — | none: tag `class.fast-movement` is asked by nothing | line + popover | speed 30 at all 20 levels; the book gives 40 | C |
| Rage (1) | no | — | pool `4+Con+2(L−1)` (`classes.py:420`); measured 5 at L1 and 43 at L20; refills on rest | pool | `resource` spends a round. No +4 Str, +4 Con, +2 Will or −2 AC, and no fatigue afterwards. `use_ability rage` is refused. | P |
| Rage powers (2, 4 … 20; ×10) | **yes** | no / no / — | none. Not a choice kind. `class_choices {"rage power":…}` → `'rage power' is not a choice a barbarian makes; it makes none.` ([list](https://www.d20pfsrd.com/classes/core-classes/barbarian/rage-powers/)) | line | — | **A** |
| Uncanny dodge (2) | no | — | `engine.py:13654` | line + popover | cannot be caught flat-footed | OK |
| Trap sense (3–18) | no | — | none (`save` carries no descriptor: `classfeatures.py` docstring) | line | — | C |
| Improved uncanny dodge (5) | no | — | `position.py:150` | line + popover | cannot be flanked | OK |
| DR 1/– … 5/– (7–19) | no | — | none. The tags split per rung. | line | `dr=[]` at L20 | C |
| Greater rage (11), indomitable will (14), tireless rage (17), mighty rage (20) | no | — | none (no rage effect for them to modify) | line | — | C ×4 |

### Bard ([d20pfsrd](https://www.d20pfsrd.com/classes/core-classes/bard/))

| Feature (lv) | Choice | Forge / Lv-up / Valid. | Mechanics | Sheet | Play | Gap |
|---|---|---|---|---|---|---|
| Spells, cantrips (1–20) | spells known | yes / yes / yes | `casting.py` six-level, `BARD_KNOWN`; §3 | slots and known | cast | OK |
| Bardic knowledge (1) | no | — | none | line | — | C |
| Bardic performance (1) | no | — | pool `4+Cha+2(L−1)`; measured 8 at L1 and 46 at L20; refills on rest | pool | `resource` only; `use_ability` is refused | P |
| Countersong, distraction, fascinate, inspire courage (1); inspire competence (3); suggestion (6); dirge of doom (8); inspire greatness (9); soothing performance (12); frightening tune (14); inspire heroics (15); mass suggestion (18); deadly performance (20) | no | — | none: no effect document, no op | line | — | C ×13 |
| Versatile performance (2, 6, 10, 14, 18) | **yes** (a Perform type) | no / no / — | none; no Perform-for-skill substitution | line | — | **A** |
| Well-versed (2) | no | — | none | line | — | C |
| Lore master (5, 11, 17) | no | — | none, and no uses-per-day pool. The tags split ×3. | line | — | C |
| Jack-of-all-trades (10, 16, 19) | no | — | none | line | — | C |

### Cleric ([d20pfsrd](https://www.d20pfsrd.com/classes/core-classes/cleric/))

| Feature (lv) | Choice | Forge / Lv-up / Valid. | Mechanics | Sheet | Play | Gap |
|---|---|---|---|---|---|---|
| Spells, orisons (1–20) | prepared from the list | prepare on the sheet | `casting.py` full; §3 | slots | cast | OK |
| Domains (1) | **yes, two** | **yes** / n/a / **yes** (one: `A cleric takes 2 domains; that is 1.`; none: `…that is 0.`) | `classes.py:165`, `domains.py:97`, domain slot `casting.py:389` (measured one per castable level, L1–L20) | domains, domain spells, domain slots | domain spells prepared into domain slots | OK |
| Domain granted powers | follows the domain | — | **7 of 153** domains are documented (`content/domains/powers.json`: Air, Animal, Earth, Fire, Plant, Water, Weather). Measured: the Fire cleric had a Fire Bolt pool of 7 and `resist.fire.10` → 20 → `immune.fire` at 6/12/20. The Sun domain gave **nothing**. | `domain_powers` (`views.py:1144`) | pool spend only; the attack itself is `not_yet` | **B** |
| Domain list offered | — | forge offers all 153 names | **120** are not core domains, mostly subdomains offered without their parent. **117** of the 153 have no spell at one or more of levels 1–9 (all 33 core domains are complete). Measured: "Ash" has spells at 7 and 9 only. | | an empty domain slot | **B** |
| Channel energy 1d6 … 10d6 (1–19) | (positive/negative by alignment; off by ruling) | — | **no pool** (book 3+Cha/day), no op, no heal or harm | line | — | C |
| Aura (1) | no | — | none (no alignment, by the 2026-09-19 ruling) | line | — | C |
| Spontaneous casting (1) | no | — | `casting.py:749 CONVERTS_TO` "cure", `:765 sacrifice_for` | | cure from a prepared slot | OK |

### Druid ([d20pfsrd](https://www.d20pfsrd.com/classes/core-classes/druid/))

| Feature (lv) | Choice | Forge / Lv-up / Valid. | Mechanics | Sheet | Play | Gap |
|---|---|---|---|---|---|---|
| Spells, orisons | prepared from the list | sheet | full; §3 | slots | cast | OK |
| Nature's bond (1) | **yes**: domain or companion | **yes** / no / **yes** (none: `A druid chooses Nature's Bond…`; Sun: `Sun is not one of a druid's domains…`; bear: `'bear' is not on a druid's companion list…`) | `classes.py:165`; domain → `domains.py`; companion → `animal_companion.py:334 wanted`, `:355 arrive_with` | domain slots and powers / Companions panel | The companion arrives and fights. **It grows only on a reload** (D6). | OK, with D6 |
| Bond: domain powers | follows the domain | — | all 7 druid domains documented, but each attack power is `not_yet` ("no engine op resolves a domain power as an attack yet") | `domain_powers` | pool counted, resist tags | **B** |
| Bond: Animal domain's companion (4) | — | — | `powers.json` `companion_offset −3` exists. `wanted` reads only a `class_choices` companion. Measured: none at druid 6 or after a reload. | not_yet line | never arrives | D7 |
| Nature sense (1), wild empathy (1), woodland stride (2), trackless step (3), resist nature's lure (4), venom immunity (9), a thousand faces (13), timeless body (15) | no | — | none. Venom immunity: no `immune.poison` tag at L20. | line | — | C ×8 |
| Spontaneous summon (1) | no | — | `CONVERTS_TO` druid | | | OK |
| Wild shape (4–20) | form chosen per use | — | pool `1+⌊(L−4)/2⌋`; measured 1 at L4 and 9 at L20 (the book is at will at 20). The only other reader is the claim vocabulary, `gm/judgement.py:3797` (an "I am a wolf" claim is not refused). | pool | no form, no stats; `use_ability` refused | P |

### Fighter ([d20pfsrd](https://www.d20pfsrd.com/classes/core-classes/fighter/))

| Feature (lv) | Choice | Forge / Lv-up / Valid. | Mechanics | Sheet | Play | Gap |
|---|---|---|---|---|---|---|
| Bonus feats (1, 2, 4 … 20) | **yes** | **yes** / **yes** / level-up yes, **forge no** | `leveling.py:697`, `:682 BONUS_FEAT_RULES` "combat" (556 combat feats). Level-up menu and take enforce it. **The forge does not**: Toughness, Iron Will and Great Fortitude were accepted as the 1st-level feats (200). | feats | feats apply | OK, with D3 |
| Bravery (2–18) | no | — | none (no fear descriptor on `save`) | line | — | C |
| Armour training (3–15) | no | — | none (max Dex and ACP are read off the armour row) | line | — | C |
| Weapon training (5–17) | **yes** (a weapon group per rung) | no / no / — | none; the weapon table carries no groups | line | — | **A** |
| Armour mastery (19) | no | — | none | line | — | C |
| Weapon mastery (20) | **yes** (one weapon) | no / no / — | none | line | — | **A** |

### Monk ([d20pfsrd](https://www.d20pfsrd.com/classes/core-classes/monk/))

| Feature (lv) | Choice | Forge / Lv-up / Valid. | Mechanics | Sheet | Play | Gap |
|---|---|---|---|---|---|---|
| Bonus feats (1, 2, 6, 10, 14, 18) | **yes** (monk list) | yes / yes / level-up yes, **forge no** | `BONUS_FEAT_RULES["monk"]`. All 17 ids exist and prerequisites are waived at level-up (`feat_rows(waive=True)`). **Forge:** Toughness accepted as the 1st-level bonus feat (200); Improved Grapple refused, `requires Improved Unarmed Strike` (the waiver is the book's) | feats | apply | OK, with D3 |
| Improved Unarmed Strike and Stunning Fist granted (1) | no | — | **never written to `feats`**. The sheet at L1 holds only the three chosen feats. | — | — | D4 |
| Unarmed strike 1d6 → 2d10 (1–20) | no | — | Only the lethality swap reads the tag (`sheet.py:2261`). **Measured at every level: damage 1d3; `not proficient with unarmed strike −4`** (the monk list has no `simple` and no `unarmed`). The class table also omits the 1d10 at 8th. | the wrong numbers | wrong to-hit and damage | **C (blocker)** |
| AC bonus, Wis + level (1) | no | — | none. Measured AC terms at L20: base 10 and Dex. The table also omits the +1…+5 ladder. | line | — | C |
| Flurry of blows (1) | no | — | none for a PC (`statblock_attacks.py` parses monster blocks) | line | — | C |
| Stunning fist (1) | no | — | none: no pool (book: monk level per day), no op | line | — | C |
| Evasion (2), improved evasion (9) | no | — | `engine.py:4780` | popover | applied on Reflex | OK |
| Fast movement (3) | no | — | none. Speed 30 at L20; the book gives +60 ft. The table names only +10 at 3rd. | line | — | C |
| Maneuver training (3), still mind (3) | no | — | none | line | — | C ×2 |
| Ki pool (4) | no | — | pool `⌊L/2⌋+Wis`; measured 6 at L4 and 14 at L20 | pool | `resource` only; no ki spends (extra attack, +20 ft, +4 dodge) | P |
| Ki strike (4, 7, 10, 16) | no | — | **absent from the class table** | — | — | (content) |
| Slow fall, high jump, purity of body, wholeness of body, diamond body, abundant step, diamond soul, quivering palm, timeless body, tongue of the sun and moon, empty body, perfect self | no | — | none | line | — | C ×12 |

### Paladin ([d20pfsrd](https://www.d20pfsrd.com/classes/core-classes/paladin/))

| Feature (lv) | Choice | Forge / Lv-up / Valid. | Mechanics | Sheet | Play | Gap |
|---|---|---|---|---|---|---|
| Spells (4–20) | prepared from the list | sheet | four-level; **the bonus-only rows are lost** (§3) | slots | cast | D9 |
| Aura of good, detect evil (1) | no | — | none | line | — | C ×2 |
| Smite evil 1–7/day (1–19) | no | — | pool `1+⌊(L−1)/3⌋`; measured 1 → 7 | pool | `resource` only; no +Cha to hit, +level damage or deflection | P |
| Divine grace (2) | no | — | none. Measured save terms L1–L20: no Charisma on any save. | line | — | C |
| Lay on hands (2) | no | — | pool `⌊L/2⌋+Cha`; measured 5 at L2 and 14 at L20 | pool | `resource` only; heals nothing | P |
| Aura of courage, divine health (3) | no | — | none (no `immune.*` tags) | line | — | C ×2 |
| Mercy (3, 6 … 18; ×6) | **yes** | no / no / — | none | line | — | **A** |
| Channel positive energy (4) | no | — | none | line | — | C |
| Divine bond (5) | **yes** (weapon or mount) | no / no / — | none | line | — | **A** |
| Auras of resolve, justice, faith, righteousness (8, 11, 14, 17) | no | — | none | line | — | C ×4 |
| DR 5/evil (17), holy champion (20) | no | — | none (`dr=[]` at L20) | line | — | C ×2 |

### Ranger ([d20pfsrd](https://www.d20pfsrd.com/classes/core-classes/ranger/))

| Feature (lv) | Choice | Forge / Lv-up / Valid. | Mechanics | Sheet | Play | Gap |
|---|---|---|---|---|---|---|
| Spells (4–20) | prepared from the list | sheet | four-level; bonus-only rows lost (§3) | slots | cast | D9 |
| Favoured enemy (1, 5, 10, 15, 20) | **yes** | no / no / — | none. `class_choices {"favored enemy":…}` → `'favored enemy' is not a choice a ranger makes; it makes none.` A top-level `favored_enemy` is accepted and dropped. | line | — | **A** |
| Track, wild empathy (1) | no | — | none ("track" is not in the feat corpus either) | line | — | C ×2 |
| Combat style feats (2, 6, 10, 14, 18) | **yes** (style, then feats) | no / **not owed** / — | `class_bonus_feats_at` counts only the literal "bonus feat". Measured: 0 bonus owed at 2/6/10/14/18. | line | — | **A**, D2 |
| Endurance (3) | no | — | the Endurance feat exists but is **never written** (ranger feats at L3: the chosen three) | line | — | C, D4 |
| Favoured terrain (3, 8, 13, 18) | **yes** | no / no / — | none | line | — | **A** |
| Hunter's bond (4) | **yes** (allies, or a companion at level −3) | no / no / — | none. The grammar *could* carry it: `animal companion` with `level_offset`. | line | — | **A** |
| Evasion (9), improved evasion (16) | no | — | `engine.py:4780` | popover | applied | OK |
| Woodland stride, swift tracker, quarry, camouflage, hide in plain sight, improved quarry, master hunter | no | — | none | line | — | C ×7 |

### Rogue ([d20pfsrd](https://www.d20pfsrd.com/classes/core-classes/rogue/))

| Feature (lv) | Choice | Forge / Lv-up / Valid. | Mechanics | Sheet | Play | Gap |
|---|---|---|---|---|---|---|
| Sneak attack 1d6 … 10d6 | no | — | `precision.py:67, :122`; `engine.py:5373` | popover | applied on a flank or flat-footed target | OK |
| Trapfinding (1) | no | — | none (no trap-finding check exists) | popover | — | C |
| Evasion (2) | no | — | `engine.py:4780` | popover | applied | OK |
| Rogue talents (2, 4 … 20; ×10) | **yes** | no / no / — | none ([list](https://www.d20pfsrd.com/classes/core-classes/rogue/rogue-talents/)) | line | — | **A** |
| Trap sense (3–18) | no | — | none | line | — | C |
| Uncanny dodge (4), improved (8) | no | — | `engine.py:13654`, `position.py:150` | popover | applied | OK |
| Advanced talents (10) | **yes** | no / no / — | none | line | — | **A** |
| Master strike (20) | no | — | none | line | — | C |

### Sorcerer ([d20pfsrd](https://www.d20pfsrd.com/classes/core-classes/sorcerer/))

| Feature (lv) | Choice | Forge / Lv-up / Valid. | Mechanics | Sheet | Play | Gap |
|---|---|---|---|---|---|---|
| Spells, cantrips | spells known | yes / yes / yes | spontaneous full, `SORCERER_KNOWN`; §3 | slots and known | cast | OK |
| Bloodline (1) | **yes** | no / no / — | none. As `class_choices`: `'bloodline' is not a choice a sorcerer makes; it makes none.` As a top-level `bloodline`: 200, dropped. ([list](https://www.d20pfsrd.com/classes/core-classes/sorcerer/bloodlines/)) | line | — | **A** |
| Bloodline powers (1, 3, 9, 15, 20) | follows the bloodline | — | none | line | — | **A** |
| Bloodline spells (3 … 19) | follows the bloodline | — | none. **The corpus already carries them**: 41 bloodlines, 9 of the 10 core ones with a spell at every one of 3, 5 … 19 (no "Aberrant" in the corpus), the same derivation `domains.py:38` uses. | line | — | **A** |
| Bloodline feats (7, 13, 19) | follows the bloodline | — | **not owed**: the grant string is not "bonus feat". Measured: 0 owed at 7/13/19. | line | — | **A**, D2 |
| Bloodline arcana (1) | follows the bloodline | — | **absent from the class table** | — | — | (content) |
| Eschew materials (1) | no | — | the feat is never written; material components are not modelled anyway | line | — | C |

### Wizard ([d20pfsrd](https://www.d20pfsrd.com/classes/core-classes/wizard/))

| Feature (lv) | Choice | Forge / Lv-up / Valid. | Mechanics | Sheet | Play | Gap |
|---|---|---|---|---|---|---|
| Spells; cantrips granted (1) | the book | yes / yes, 2 per level / yes | `creation.py:809` grants every 0-level spell; `learning` (`casting.py:577`); §3 | book and slots | prepare, cast | OK |
| Arcane school (1) | **yes** (school + two opposition, or universalist) | no / no / — | none. A top-level `arcane_school`/`opposition` is accepted and dropped (200). Measured slots equal a **universalist's**, without the universalist's powers. ([list](https://www.d20pfsrd.com/classes/core-classes/wizard/arcane-schools/)) | line | — | **A** |
| Arcane bond (1) | **yes** (familiar or object) | no / no / — | none | line | — | **A** |
| Scribe Scroll (1) | no | — | the feat exists but is **never written** (wizard feats at L1: the chosen two) | line | — | C, D4 |
| Bonus feats (5, 10, 15, 20) | **yes** | n/a / **yes** / **yes** (metamagic, item creation or Spell Mastery; 51 + 1 feats) | `leveling.py:682` | feats | apply | OK |

### Blood Bending (homebrew; `content/classes/blood-bending.json`)

| Feature (lv) | Choice | Forge / Lv-up / Valid. | Mechanics | Sheet | Play | Gap |
|---|---|---|---|---|---|---|
| Path A (1) | **yes** | **yes** / — / **yes** (`leveling.check_paths`) | path tiers through Control Blood | Class tab | `use_ability`, bar, brief | OK |
| Path B (opens at 11) | **yes** | forge only / **no** / — | nothing writes `paths` after creation. Measured: a one-path character at 11 is offered nothing; the line reads "control blood 1b". | line | — | **A** |
| Path abilities (62 across 4 paths) | — | — | 26 carry effect specs and 15 list `needs`. The rest are the author's prose, reported by `_op_use_ability` as narrated. | Class tab | partial | (homebrew, as documented) |
| Bonus feats (any feat) | yes | yes / yes / yes | `leveling.py:697` | feats | apply | OK |
| Unarmed strike, fist column | no | — | `sheet.py` granted weapon off the table column | attacks | applied | OK |
| Blood bond (1) | no | — | `overrides` → `Actor.allows`; +2 Con per 5 levels through `grow_ability` (measured Con 22 at L20) | yes | yes | OK |
| Evasion (2), improved evasion (12) | no | — | `engine.py:4780` | popover | applied | OK |
| Unbalancing strike (3), rapid coagulation (4), stunning strike (13) | no | — | pools (refill on night or `encounter.end`) | pools | `resource` only | P ×3 |
| Blood sense, improved blood sense, fast movement 10/20 ft, combat expertise, combat reflexes, style fusion, blood pool movement, blood teleportation | no | — | none. Combat Expertise and Combat Reflexes are **strings on the table, not feats**, so the feat readers (`reactions.py`) never see them. | line | — | C ×8 |

---

## 2. Level-up, end to end

### What was proven to work

Every one of the 684 level-ups returned 200. After each one the harness took every owed
pick through the real endpoints, and the sheet then owed nothing:
- feats: 774 taken
- bonus feats: inside those 774 (fighter combat, wizard metamagic/item creation, monk list)
- ability points: 900 placed
- spells: 327 learned (the wizard's two a level, and the sorcerer's and bard's per
  spell-level increments)

`analyse.py` compared the owed counts at every level against the book plus the house rule:
**0 mismatches across 36 runs**. Specifically:
- **Book:** a feat at 3, 5 … 19; +1 at 4, 8 … 20; the class table's "bonus feat" rows.
- **odd/even:** +1 feat on odd levels and +2 points on even. The 1st-level share the forge
  did not take is owed on the sheet at once (1F at 1st, as designed in `leveling.py`'s
  header).
- **every/every:** +1 feat and +2 points at every level, 1st included.

Further checks:
- **Hit points:** a Constitution point placed later raised `hp_max` by
  Δmod × Hit Dice in all 36 checks, including Blood Bending's two Hit Dice per level.
- **The level-up line** carries everything still to choose ("1 bonus feat to choose — a
  combat feat (Class tab)", "2 new spells to choose for the spellbook (Spells tab)", "1
  ability point to place (Class tab)").
- **Sleeping on enough XP levels too.** `_op_rest` → `leveling.level_up`
  (`engine.py:15321`), and its tell carries the same owed lines.

### What does not work (the D list)

| # | Defect | Measured | Classes |
|---|---|---|---|
| D1 | **Skill ranks after 1st level are never owed, offered or placeable.** `gains_at` reports `skill_ranks` and nothing reads it. Nothing writes `actor.ranks` after `creation.build`; `POST /api/level/skills`, `/api/level/ranks` and `/api/skills/ranks` all return 404. | Ranks at 20th equal ranks at 1st in all 36 runs: 3–10 against a book total of 60–200 (human barbarian: 5 against 100; rogue: 10 against 200). The level-up line never mentions them. | all 12 |
| D2 | **Bonus feats the class table names as anything but "bonus feat" are not owed.** `class_bonus_feats_at` matches the literal string (`leveling.py:697`). | Ranger combat style feats: 0 owed at 2/6/10/14/18. Sorcerer bloodline feats: 0 owed at 7/13/19. | ranger, sorcerer |
| D3 | **The forge does not hold the 1st-level class bonus feat to the class's rule.** Level-up does. | Fighter with Toughness, Iron Will and Great Fortitude: 200. Monk with Toughness: 200. Monk with Improved Grapple: 400 `requires Improved Unarmed Strike`, though the monk's waiver is the book's. | fighter, monk |
| D4 | **Feats the class grants outright are never written.** | Monk L1 feats: the three chosen, with no Improved Unarmed Strike and no Stunning Fist. Wizard: no Scribe Scroll. Ranger: no Endurance at 3. Sorcerer: no Eschew Materials. Blood Bending: Combat Expertise and Combat Reflexes are strings only. | monk, wizard, ranger, sorcerer, blood bending |
| D5 | **Prerequisites that name a class feature are never checked.** `feats.NOT_YET` holds `class_feature`, so 201 feats come back `unknown`, and `feat_problems` refuses only `unmet`. | A 3rd-level **wizard took Extra Rage Power**: 200 `["extra rage power"]`. The menu lists it as "make sure you qualify". | all |
| D6 | **The animal companion does not advance at level-up.** `animal_companion.sync` runs only on a campaign load (`play/campaign.py:506`); the in-memory campaign is never re-synced by `/api/level-up`. | Druid 7 with a wolf: EDL 1, 2 HD, 13 hp live. After dropping the cached campaign: EDL 7, 6 HD, 51 hp. The level-up line never mentions the companion. | druid |
| D7 | **The Animal domain's companion never arrives.** `wanted` reads only a `class_choices` companion. | Animal-domain druid at 6: none, before and after a reload. Animal-domain cleric at 5: none. Powers.json says it waits on "the level-up writer". | druid, cleric |
| D8 | **Blood Bending's Path B cannot be taken after creation.** | One path at creation; at 11 nothing is offered. | blood bending |
| D9 | **Four-level casters lose their bonus-only rows.** `FOUR_LEVEL` stores the book's "0" as 0 and `slots_for` skips a zero base, so the bonus spell vanishes too. L13 4th-level is 1 where the book has 0. | Paladin with Cha 18: no slots at L4 (book: 1 bonus 1st); no 2nd at L7 (book: 1); no 3rd at L10. At L13 there are 2 4th-level slots (book: 1). Ranger with Wis 18: identical. | paladin, ranger |
| D10 | **Spontaneous casters cannot swap a known spell** (sorcerer at 4, 6, 8 …; bard at 5, 8, 11 …). | No code path: `learn` only adds. | sorcerer, bard |

Observations, not counted as defects:
- **Pool current values at level-up.** A level resizes each pool's maximum but keeps its
  current value until the night (`classes.apply` docstring, on purpose). So a paladin
  levelled 1→20 in a day holds 1 of 7 smites until she sleeps.
- **One level per night.** Sleeping with the XP for two levels takes one (measured: XP for
  +2, slept, +1). The Class card takes the second.
- **The class-choice grammar has a `level` field the forge never reads past 1st**
  (`creation.class_choice_menu` → `choices_for(cid, 1)`). And no endpoint lets an existing
  character answer a choice, so a druid made before 2026-10-04 can never take a bond.

### Every level, every class

Codes in the table:
- **F**: feats owed
- **B**: class bonus feats owed
- **P**: ability points owed
- **S**: spells owed

Every one of these was taken through the endpoints with 200. The last column lists what the
book gives at that level that nothing in the app owes: the class choices of §1, and the
skill ranks (class + Int + 1 for a human).

#### Barbarian — level-up record

Created through `/api/character/create` (200) with 2 feats. Owed on the sheet at 1st: book 0, odd/even 1F 0P, every/every 1F 2P (the forge's house share left for the sheet, as designed).

| Lv | Class grants on the level-up line | Owed, book (all taken: 200) | Owed, odd/even | Owed, every/every | The book's picks this level that nothing owes |
|---|---|---|---|---|---|
| 2 | rage power, uncanny dodge | - | 1F 2P | 2F 4P | rage power, 5 skill ranks |
| 3 | trap sense +1 | 1F | 2F | 2F 2P | 5 skill ranks |
| 4 | rage power | 1P | 3P | 1F 3P | rage power, 5 skill ranks |
| 5 | improved uncanny dodge | 1F | 2F | 2F 2P | 5 skill ranks |
| 6 | rage power, trap sense +2 | - | 2P | 1F 2P | rage power, 5 skill ranks |
| 7 | damage reduction 1/- | 1F | 2F | 2F 2P | 5 skill ranks |
| 8 | rage power | 1P | 3P | 1F 3P | rage power, 5 skill ranks |
| 9 | trap sense +3 | 1F | 2F | 2F 2P | 5 skill ranks |
| 10 | rage power, damage reduction 2/- | - | 2P | 1F 2P | rage power, 5 skill ranks |
| 11 | greater rage | 1F | 2F | 2F 2P | 5 skill ranks |
| 12 | rage power, trap sense +4 | 1P | 3P | 1F 3P | rage power, 5 skill ranks |
| 13 | damage reduction 3/- | 1F | 2F | 2F 2P | 5 skill ranks |
| 14 | rage power, indomitable will | - | 2P | 1F 2P | rage power, 5 skill ranks |
| 15 | trap sense +5 | 1F | 2F | 2F 2P | 5 skill ranks |
| 16 | rage power, damage reduction 4/- | 1P | 3P | 1F 3P | rage power, 5 skill ranks |
| 17 | tireless rage | 1F | 2F | 2F 2P | 5 skill ranks |
| 18 | rage power, trap sense +6 | - | 2P | 1F 2P | rage power, 5 skill ranks |
| 19 | damage reduction 5/- | 1F | 2F | 2F 2P | 5 skill ranks |
| 20 | rage power, mighty rage | 1P | 3P | 1F 3P | rage power, 5 skill ranks |

#### Bard — level-up record

Created through `/api/character/create` (200) with 2 feats. Owed on the sheet at 1st: book 0, odd/even 1F 0P, every/every 1F 2P (the forge's house share left for the sheet, as designed).

| Lv | Class grants on the level-up line | Owed, book (all taken: 200) | Owed, odd/even | Owed, every/every | The book's picks this level that nothing owes |
|---|---|---|---|---|---|
| 2 | versatile performance, well-versed | 2S | 1F 2P 2S | 2F 4P 2S | versatile performance, 7 skill ranks |
| 3 | inspire competence +2 | 1F 2S | 2F 2S | 2F 2P 2S | 7 skill ranks |
| 4 | — | 1P 2S | 3P 2S | 1F 3P 2S | 7 skill ranks |
| 5 | lore master 1/day, inspire courage +2 | 1F 1S | 2F 1S | 2F 2P 1S | 7 skill ranks |
| 6 | suggestion, versatile performance | 1S | 2P 1S | 1F 2P 1S | versatile performance, 7 skill ranks |
| 7 | inspire competence +3 | 1F 3S | 2F 3S | 2F 2P 3S | 7 skill ranks |
| 8 | dirge of doom | 1P 1S | 3P 1S | 1F 3P 1S | 7 skill ranks |
| 9 | inspire greatness | 1F 1S | 2F 1S | 2F 2P 1S | 7 skill ranks |
| 10 | jack-of-all-trades, versatile performance | 3S | 2P 3S | 1F 2P 3S | versatile performance, 7 skill ranks |
| 11 | inspire competence +4, inspire courage +3, lore master 2/day | 1F 2S | 2F 2S | 2F 2P 2S | 7 skill ranks |
| 12 | soothing performance | 1P 1S | 3P 1S | 1F 3P 1S | 7 skill ranks |
| 13 | — | 1F 3S | 2F 3S | 2F 2P 3S | 7 skill ranks |
| 14 | frightening tune, versatile performance | 2S | 2P 2S | 1F 2P 2S | versatile performance, 7 skill ranks |
| 15 | inspire competence +5, inspire heroics | 1F 1S | 2F 1S | 2F 2P 1S | 7 skill ranks |
| 16 | jack-of-all-trades (all skills are class skills) | 1P 3S | 3P 3S | 1F 3P 3S | 7 skill ranks |
| 17 | inspire courage +4, lore master 3/day | 1F 2S | 2F 2S | 2F 2P 2S | 7 skill ranks |
| 18 | mass suggestion, versatile performance | 1S | 2P 1S | 1F 2P 1S | versatile performance, 7 skill ranks |
| 19 | inspire competence +6, jack-of-all-trades (take 10 on any skill) | 1F 1S | 2F 1S | 2F 2P 1S | 7 skill ranks |
| 20 | deadly performance | 1P 2S | 3P 2S | 1F 3P 2S | 7 skill ranks |

#### Cleric — level-up record

Created through `/api/character/create` (200) with 2 feats, domains ['Fire', 'Sun']. Owed on the sheet at 1st: book 0, odd/even 1F 0P, every/every 1F 2P (the forge's house share left for the sheet, as designed).

| Lv | Class grants on the level-up line | Owed, book (all taken: 200) | Owed, odd/even | Owed, every/every | The book's picks this level that nothing owes |
|---|---|---|---|---|---|
| 2 | — | - | 1F 2P | 2F 4P | 3 skill ranks |
| 3 | channel energy 2d6 | 1F | 2F | 2F 2P | 3 skill ranks |
| 4 | — | 1P | 3P | 1F 3P | 3 skill ranks |
| 5 | channel energy 3d6 | 1F | 2F | 2F 2P | 3 skill ranks |
| 6 | — | - | 2P | 1F 2P | 3 skill ranks |
| 7 | channel energy 4d6 | 1F | 2F | 2F 2P | 3 skill ranks |
| 8 | — | 1P | 3P | 1F 3P | 3 skill ranks |
| 9 | channel energy 5d6 | 1F | 2F | 2F 2P | 3 skill ranks |
| 10 | — | - | 2P | 1F 2P | 3 skill ranks |
| 11 | channel energy 6d6 | 1F | 2F | 2F 2P | 3 skill ranks |
| 12 | — | 1P | 3P | 1F 3P | 3 skill ranks |
| 13 | channel energy 7d6 | 1F | 2F | 2F 2P | 3 skill ranks |
| 14 | — | - | 2P | 1F 2P | 3 skill ranks |
| 15 | channel energy 8d6 | 1F | 2F | 2F 2P | 3 skill ranks |
| 16 | — | 1P | 3P | 1F 3P | 3 skill ranks |
| 17 | channel energy 9d6 | 1F | 2F | 2F 2P | 3 skill ranks |
| 18 | — | - | 2P | 1F 2P | 3 skill ranks |
| 19 | channel energy 10d6 | 1F | 2F | 2F 2P | 3 skill ranks |
| 20 | — | 1P | 3P | 1F 3P | 3 skill ranks |

#### Druid — level-up record

Created through `/api/character/create` (200) with 2 feats, {'nature bond': {'option': 'animal companion', 'pick': 'wolf', 'name': 'Grey'}}. Owed on the sheet at 1st: book 0, odd/even 1F 0P, every/every 1F 2P (the forge's house share left for the sheet, as designed).

| Lv | Class grants on the level-up line | Owed, book (all taken: 200) | Owed, odd/even | Owed, every/every | The book's picks this level that nothing owes |
|---|---|---|---|---|---|
| 2 | woodland stride | - | 1F 2P | 2F 4P | 5 skill ranks |
| 3 | trackless step | 1F | 2F | 2F 2P | 5 skill ranks |
| 4 | wild shape 1/day, wild shape (Small or Medium animal), resist nature's lure | 1P | 3P | 1F 3P | 5 skill ranks |
| 5 | — | 1F | 2F | 2F 2P | 5 skill ranks |
| 6 | wild shape 2/day, wild shape (Large or Tiny animal, Small elemental) | - | 2P | 1F 2P | 5 skill ranks |
| 7 | — | 1F | 2F | 2F 2P | 5 skill ranks |
| 8 | wild shape 3/day, wild shape (Huge or Diminutive animal, Medium elemental, Small or Medium plant) | 1P | 3P | 1F 3P | 5 skill ranks |
| 9 | venom immunity | 1F | 2F | 2F 2P | 5 skill ranks |
| 10 | wild shape 4/day, wild shape (Large elemental, Large plant) | - | 2P | 1F 2P | 5 skill ranks |
| 11 | — | 1F | 2F | 2F 2P | 5 skill ranks |
| 12 | wild shape 5/day, wild shape (Huge elemental, Huge plant) | 1P | 3P | 1F 3P | 5 skill ranks |
| 13 | a thousand faces | 1F | 2F | 2F 2P | 5 skill ranks |
| 14 | wild shape 6/day | - | 2P | 1F 2P | 5 skill ranks |
| 15 | timeless body | 1F | 2F | 2F 2P | 5 skill ranks |
| 16 | wild shape 7/day | 1P | 3P | 1F 3P | 5 skill ranks |
| 17 | — | 1F | 2F | 2F 2P | 5 skill ranks |
| 18 | wild shape 8/day | - | 2P | 1F 2P | 5 skill ranks |
| 19 | — | 1F | 2F | 2F 2P | 5 skill ranks |
| 20 | wild shape at will | 1P | 3P | 1F 3P | 5 skill ranks |

#### Fighter — level-up record

Created through `/api/character/create` (200) with 3 feats. Owed on the sheet at 1st: book 0, odd/even 1F 0P, every/every 1F 2P (the forge's house share left for the sheet, as designed).

| Lv | Class grants on the level-up line | Owed, book (all taken: 200) | Owed, odd/even | Owed, every/every | The book's picks this level that nothing owes |
|---|---|---|---|---|---|
| 2 | bonus feat, bravery +1 | 1B | 1F 1B 2P | 2F 1B 4P | 3 skill ranks |
| 3 | armor training 1 | 1F | 2F | 2F 2P | 3 skill ranks |
| 4 | bonus feat | 1B 1P | 1B 3P | 1F 1B 3P | 3 skill ranks |
| 5 | weapon training 1 | 1F | 2F | 2F 2P | weapon training 1, 3 skill ranks |
| 6 | bonus feat, bravery +2 | 1B | 1B 2P | 1F 1B 2P | 3 skill ranks |
| 7 | armor training 2 | 1F | 2F | 2F 2P | 3 skill ranks |
| 8 | bonus feat | 1B 1P | 1B 3P | 1F 1B 3P | 3 skill ranks |
| 9 | weapon training 2 | 1F | 2F | 2F 2P | weapon training 2, 3 skill ranks |
| 10 | bonus feat, bravery +3 | 1B | 1B 2P | 1F 1B 2P | 3 skill ranks |
| 11 | armor training 3 | 1F | 2F | 2F 2P | 3 skill ranks |
| 12 | bonus feat | 1B 1P | 1B 3P | 1F 1B 3P | 3 skill ranks |
| 13 | weapon training 3 | 1F | 2F | 2F 2P | weapon training 3, 3 skill ranks |
| 14 | bonus feat, bravery +4 | 1B | 1B 2P | 1F 1B 2P | 3 skill ranks |
| 15 | armor training 4 | 1F | 2F | 2F 2P | 3 skill ranks |
| 16 | bonus feat | 1B 1P | 1B 3P | 1F 1B 3P | 3 skill ranks |
| 17 | weapon training 4 | 1F | 2F | 2F 2P | weapon training 4, 3 skill ranks |
| 18 | bonus feat, bravery +5 | 1B | 1B 2P | 1F 1B 2P | 3 skill ranks |
| 19 | armor mastery | 1F | 2F | 2F 2P | 3 skill ranks |
| 20 | bonus feat, weapon mastery | 1B 1P | 1B 3P | 1F 1B 3P | weapon mastery, 3 skill ranks |

#### Monk — level-up record

Created through `/api/character/create` (200) with 3 feats. Owed on the sheet at 1st: book 0, odd/even 1F 0P, every/every 1F 2P (the forge's house share left for the sheet, as designed).

| Lv | Class grants on the level-up line | Owed, book (all taken: 200) | Owed, odd/even | Owed, every/every | The book's picks this level that nothing owes |
|---|---|---|---|---|---|
| 2 | bonus feat, evasion | 1B | 1F 1B 2P | 2F 1B 4P | 5 skill ranks |
| 3 | fast movement +10 ft, maneuver training, still mind | 1F | 2F | 2F 2P | 5 skill ranks |
| 4 | ki pool, slow fall 20 ft, unarmed strike 1d8 | 1P | 3P | 1F 3P | 5 skill ranks |
| 5 | high jump, purity of body | 1F | 2F | 2F 2P | 5 skill ranks |
| 6 | bonus feat, slow fall 30 ft | 1B | 1B 2P | 1F 1B 2P | 5 skill ranks |
| 7 | wholeness of body | 1F | 2F | 2F 2P | 5 skill ranks |
| 8 | slow fall 40 ft | 1P | 3P | 1F 3P | 5 skill ranks |
| 9 | improved evasion | 1F | 2F | 2F 2P | 5 skill ranks |
| 10 | bonus feat, slow fall 50 ft | 1B | 1B 2P | 1F 1B 2P | 5 skill ranks |
| 11 | diamond body | 1F | 2F | 2F 2P | 5 skill ranks |
| 12 | abundant step, unarmed strike 2d6, slow fall 60 ft | 1P | 3P | 1F 3P | 5 skill ranks |
| 13 | diamond soul | 1F | 2F | 2F 2P | 5 skill ranks |
| 14 | bonus feat, slow fall 70 ft | 1B | 1B 2P | 1F 1B 2P | 5 skill ranks |
| 15 | quivering palm | 1F | 2F | 2F 2P | 5 skill ranks |
| 16 | slow fall 80 ft, unarmed strike 2d8 | 1P | 3P | 1F 3P | 5 skill ranks |
| 17 | timeless body, tongue of the sun and moon | 1F | 2F | 2F 2P | 5 skill ranks |
| 18 | bonus feat, slow fall 90 ft | 1B | 1B 2P | 1F 1B 2P | 5 skill ranks |
| 19 | empty body | 1F | 2F | 2F 2P | 5 skill ranks |
| 20 | perfect self, unarmed strike 2d10, slow fall any distance | 1P | 3P | 1F 3P | 5 skill ranks |

#### Paladin — level-up record

Created through `/api/character/create` (200) with 2 feats. Owed on the sheet at 1st: book 0, odd/even 1F 0P, every/every 1F 2P (the forge's house share left for the sheet, as designed).

| Lv | Class grants on the level-up line | Owed, book (all taken: 200) | Owed, odd/even | Owed, every/every | The book's picks this level that nothing owes |
|---|---|---|---|---|---|
| 2 | divine grace, lay on hands | - | 1F 2P | 2F 4P | 3 skill ranks |
| 3 | aura of courage, divine health, mercy | 1F | 2F | 2F 2P | mercy, 3 skill ranks |
| 4 | channel positive energy, smite evil 2/day | 1P | 3P | 1F 3P | 3 skill ranks |
| 5 | divine bond | 1F | 2F | 2F 2P | divine bond, 3 skill ranks |
| 6 | mercy | - | 2P | 1F 2P | mercy, 3 skill ranks |
| 7 | smite evil 3/day | 1F | 2F | 2F 2P | 3 skill ranks |
| 8 | aura of resolve | 1P | 3P | 1F 3P | 3 skill ranks |
| 9 | mercy | 1F | 2F | 2F 2P | mercy, 3 skill ranks |
| 10 | smite evil 4/day | - | 2P | 1F 2P | 3 skill ranks |
| 11 | aura of justice | 1F | 2F | 2F 2P | 3 skill ranks |
| 12 | mercy | 1P | 3P | 1F 3P | mercy, 3 skill ranks |
| 13 | smite evil 5/day | 1F | 2F | 2F 2P | 3 skill ranks |
| 14 | aura of faith | - | 2P | 1F 2P | 3 skill ranks |
| 15 | mercy | 1F | 2F | 2F 2P | mercy, 3 skill ranks |
| 16 | smite evil 6/day | 1P | 3P | 1F 3P | 3 skill ranks |
| 17 | aura of righteousness, damage reduction 5/evil | 1F | 2F | 2F 2P | 3 skill ranks |
| 18 | mercy | - | 2P | 1F 2P | mercy, 3 skill ranks |
| 19 | smite evil 7/day | 1F | 2F | 2F 2P | 3 skill ranks |
| 20 | holy champion | 1P | 3P | 1F 3P | 3 skill ranks |

#### Ranger — level-up record

Created through `/api/character/create` (200) with 2 feats. Owed on the sheet at 1st: book 0, odd/even 1F 0P, every/every 1F 2P (the forge's house share left for the sheet, as designed).

| Lv | Class grants on the level-up line | Owed, book (all taken: 200) | Owed, odd/even | Owed, every/every | The book's picks this level that nothing owes |
|---|---|---|---|---|---|
| 2 | combat style feat | - | 1F 2P | 2F 4P | combat style feat, 7 skill ranks |
| 3 | endurance, favored terrain | 1F | 2F | 2F 2P | favored terrain, 7 skill ranks |
| 4 | hunter's bond | 1P | 3P | 1F 3P | hunter's bond, 7 skill ranks |
| 5 | favored enemy (2nd) | 1F | 2F | 2F 2P | favored enemy (2nd), 7 skill ranks |
| 6 | combat style feat | - | 2P | 1F 2P | combat style feat, 7 skill ranks |
| 7 | woodland stride | 1F | 2F | 2F 2P | 7 skill ranks |
| 8 | favored terrain (2nd), swift tracker | 1P | 3P | 1F 3P | favored terrain (2nd), 7 skill ranks |
| 9 | evasion | 1F | 2F | 2F 2P | 7 skill ranks |
| 10 | favored enemy (3rd), combat style feat | - | 2P | 1F 2P | favored enemy (3rd), combat style feat, 7 skill ranks |
| 11 | quarry | 1F | 2F | 2F 2P | 7 skill ranks |
| 12 | camouflage | 1P | 3P | 1F 3P | 7 skill ranks |
| 13 | favored terrain (3rd) | 1F | 2F | 2F 2P | favored terrain (3rd), 7 skill ranks |
| 14 | combat style feat | - | 2P | 1F 2P | combat style feat, 7 skill ranks |
| 15 | favored enemy (4th) | 1F | 2F | 2F 2P | favored enemy (4th), 7 skill ranks |
| 16 | improved evasion | 1P | 3P | 1F 3P | 7 skill ranks |
| 17 | hide in plain sight | 1F | 2F | 2F 2P | 7 skill ranks |
| 18 | favored terrain (4th), combat style feat | - | 2P | 1F 2P | favored terrain (4th), combat style feat, 7 skill ranks |
| 19 | improved quarry | 1F | 2F | 2F 2P | 7 skill ranks |
| 20 | favored enemy (5th), master hunter | 1P | 3P | 1F 3P | favored enemy (5th), 7 skill ranks |

#### Rogue — level-up record

Created through `/api/character/create` (200) with 2 feats. Owed on the sheet at 1st: book 0, odd/even 1F 0P, every/every 1F 2P (the forge's house share left for the sheet, as designed).

| Lv | Class grants on the level-up line | Owed, book (all taken: 200) | Owed, odd/even | Owed, every/every | The book's picks this level that nothing owes |
|---|---|---|---|---|---|
| 2 | evasion, rogue talent | - | 1F 2P | 2F 4P | rogue talent, 10 skill ranks |
| 3 | sneak attack 2d6, trap sense +1 | 1F | 2F | 2F 2P | 10 skill ranks |
| 4 | rogue talent, uncanny dodge | 1P | 3P | 1F 3P | rogue talent, 10 skill ranks |
| 5 | sneak attack 3d6 | 1F | 2F | 2F 2P | 10 skill ranks |
| 6 | rogue talent, trap sense +2 | - | 2P | 1F 2P | rogue talent, 10 skill ranks |
| 7 | sneak attack 4d6 | 1F | 2F | 2F 2P | 10 skill ranks |
| 8 | improved uncanny dodge, rogue talent | 1P | 3P | 1F 3P | rogue talent, 10 skill ranks |
| 9 | sneak attack 5d6, trap sense +3 | 1F | 2F | 2F 2P | 10 skill ranks |
| 10 | advanced talents, rogue talent | - | 2P | 1F 2P | advanced talents, rogue talent, 10 skill ranks |
| 11 | sneak attack 6d6 | 1F | 2F | 2F 2P | 10 skill ranks |
| 12 | rogue talent, trap sense +4 | 1P | 3P | 1F 3P | rogue talent, 10 skill ranks |
| 13 | sneak attack 7d6 | 1F | 2F | 2F 2P | 10 skill ranks |
| 14 | rogue talent | - | 2P | 1F 2P | rogue talent, 10 skill ranks |
| 15 | sneak attack 8d6, trap sense +5 | 1F | 2F | 2F 2P | 10 skill ranks |
| 16 | rogue talent | 1P | 3P | 1F 3P | rogue talent, 10 skill ranks |
| 17 | sneak attack 9d6 | 1F | 2F | 2F 2P | 10 skill ranks |
| 18 | rogue talent, trap sense +6 | - | 2P | 1F 2P | rogue talent, 10 skill ranks |
| 19 | sneak attack 10d6 | 1F | 2F | 2F 2P | 10 skill ranks |
| 20 | master strike, rogue talent | 1P | 3P | 1F 3P | rogue talent, 10 skill ranks |

#### Sorcerer — level-up record

Created through `/api/character/create` (200) with 2 feats. Owed on the sheet at 1st: book 0, odd/even 1F 0P, every/every 1F 2P (the forge's house share left for the sheet, as designed).

| Lv | Class grants on the level-up line | Owed, book (all taken: 200) | Owed, odd/even | Owed, every/every | The book's picks this level that nothing owes |
|---|---|---|---|---|---|
| 2 | — | 1S | 1F 2P 1S | 2F 4P 1S | 3 skill ranks |
| 3 | bloodline power, bloodline spell | 1F 1S | 2F 1S | 2F 2P 1S | bloodline power, bloodline spell, 3 skill ranks |
| 4 | — | 1P 2S | 3P 2S | 1F 3P 2S | 3 skill ranks |
| 5 | bloodline spell | 1F 2S | 2F 2S | 2F 2P 2S | bloodline spell, 3 skill ranks |
| 6 | — | 2S | 2P 2S | 1F 2P 2S | 3 skill ranks |
| 7 | bloodline feat, bloodline spell | 1F 3S | 2F 3S | 2F 2P 3S | bloodline feat, bloodline spell, 3 skill ranks |
| 8 | — | 1P 2S | 3P 2S | 1F 3P 2S | 3 skill ranks |
| 9 | bloodline power, bloodline spell | 1F 3S | 2F 3S | 2F 2P 3S | bloodline power, bloodline spell, 3 skill ranks |
| 10 | — | 2S | 2P 2S | 1F 2P 2S | 3 skill ranks |
| 11 | bloodline spell | 1F 4S | 2F 4S | 2F 2P 4S | bloodline spell, 3 skill ranks |
| 12 | — | 1P 1S | 3P 1S | 1F 3P 1S | 3 skill ranks |
| 13 | bloodline feat, bloodline spell | 1F 3S | 2F 3S | 2F 2P 3S | bloodline feat, bloodline spell, 3 skill ranks |
| 14 | — | 1S | 2P 1S | 1F 2P 1S | 3 skill ranks |
| 15 | bloodline power, bloodline spell | 1F 3S | 2F 3S | 2F 2P 3S | bloodline power, bloodline spell, 3 skill ranks |
| 16 | — | 1P 1S | 3P 1S | 1F 3P 1S | 3 skill ranks |
| 17 | bloodline spell | 1F 2S | 2F 2S | 2F 2P 2S | bloodline spell, 3 skill ranks |
| 18 | — | 1S | 2P 1S | 1F 2P 1S | 3 skill ranks |
| 19 | bloodline feat, bloodline spell | 1F 2S | 2F 2S | 2F 2P 2S | bloodline feat, bloodline spell, 3 skill ranks |
| 20 | bloodline power | 1P 1S | 3P 1S | 1F 3P 1S | bloodline power, 3 skill ranks |

#### Wizard — level-up record

Created through `/api/character/create` (200) with 2 feats. Owed on the sheet at 1st: book 0, odd/even 1F 0P, every/every 1F 2P (the forge's house share left for the sheet, as designed).

| Lv | Class grants on the level-up line | Owed, book (all taken: 200) | Owed, odd/even | Owed, every/every | The book's picks this level that nothing owes |
|---|---|---|---|---|---|
| 2 | — | 2S | 1F 2P 2S | 2F 4P 2S | 7 skill ranks |
| 3 | — | 1F 2S | 2F 2S | 2F 2P 2S | 7 skill ranks |
| 4 | — | 1P 2S | 3P 2S | 1F 3P 2S | 7 skill ranks |
| 5 | bonus feat | 1F 1B 2S | 2F 1B 2S | 2F 1B 2P 2S | 7 skill ranks |
| 6 | — | 2S | 2P 2S | 1F 2P 2S | 7 skill ranks |
| 7 | — | 1F 2S | 2F 2S | 2F 2P 2S | 7 skill ranks |
| 8 | — | 1P 2S | 3P 2S | 1F 3P 2S | 7 skill ranks |
| 9 | — | 1F 2S | 2F 2S | 2F 2P 2S | 7 skill ranks |
| 10 | bonus feat | 1B 2S | 1B 2P 2S | 1F 1B 2P 2S | 7 skill ranks |
| 11 | — | 1F 2S | 2F 2S | 2F 2P 2S | 7 skill ranks |
| 12 | — | 1P 2S | 3P 2S | 1F 3P 2S | 8 skill ranks |
| 13 | — | 1F 2S | 2F 2S | 2F 2P 2S | 8 skill ranks |
| 14 | — | 2S | 2P 2S | 1F 2P 2S | 8 skill ranks |
| 15 | bonus feat | 1F 1B 2S | 2F 1B 2S | 2F 1B 2P 2S | 8 skill ranks |
| 16 | — | 1P 2S | 3P 2S | 1F 3P 2S | 8 skill ranks |
| 17 | — | 1F 2S | 2F 2S | 2F 2P 2S | 8 skill ranks |
| 18 | — | 2S | 2P 2S | 1F 2P 2S | 8 skill ranks |
| 19 | — | 1F 2S | 2F 2S | 2F 2P 2S | 8 skill ranks |
| 20 | bonus feat | 1B 1P 2S | 1B 3P 2S | 1F 1B 3P 2S | 9 skill ranks |

#### Blood Bending — level-up record

Created through `/api/character/create` (200) with 3 feats, paths ['blood spike']. Owed on the sheet at 1st: book 0, odd/even 1F 0P, every/every 1F 2P (the forge's house share left for the sheet, as designed).

| Lv | Class grants on the level-up line | Owed, book (all taken: 200) | Owed, odd/even | Owed, every/every | The book's picks this level that nothing owes |
|---|---|---|---|---|---|
| 2 | bonus feat, evasion, blood sense 60ft | 1B | 1F 1B 2P | 2F 1B 4P | 5 skill ranks |
| 3 | fast movement 10ft, unbalancing strike, control blood 2a | 1F | 2F | 2F 2P | 5 skill ranks |
| 4 | rapid coagulation, combat expertise, bonus feat | 1B 1P | 1B 3P | 1F 1B 3P | 5 skill ranks |
| 5 | control blood 3a, blood bending style fusion | 1F | 2F | 2F 2P | 5 skill ranks |
| 6 | bonus feat | 1B | 1B 2P | 1F 1B 2P | 5 skill ranks |
| 7 | control blood 4a | 1F | 2F | 2F 2P | 5 skill ranks |
| 8 | bonus feat | 1B 1P | 1B 3P | 1F 1B 3P | 5 skill ranks |
| 9 | improved blood sense 120ft | 1F | 2F | 2F 2P | 5 skill ranks |
| 10 | bonus feat, control blood 5a | 1B | 1B 2P | 1F 1B 2P | 5 skill ranks |
| 11 | bonus feat, control blood 1b | 1F 1B | 2F 1B | 2F 1B 2P | control blood 1b, 5 skill ranks |
| 12 | bonus feat, improved evasion | 1B 1P | 1B 3P | 1F 1B 3P | 5 skill ranks |
| 13 | fast movement 20ft, stunning strike, control blood 2b | 1F | 2F | 2F 2P | 5 skill ranks |
| 14 | combat reflexes, bonus feat | 1B | 1B 2P | 1F 1B 2P | 5 skill ranks |
| 15 | control blood 3b, blood pool movement | 1F | 2F | 2F 2P | 5 skill ranks |
| 16 | bonus feat | 1B 1P | 1B 3P | 1F 1B 3P | 5 skill ranks |
| 17 | control blood 4b, blood teleportation | 1F | 2F | 2F 2P | 5 skill ranks |
| 18 | bonus feat | 1B | 1B 2P | 1F 1B 2P | 5 skill ranks |
| 19 | improved blood sense 120ft | 1F | 2F | 2F 2P | 5 skill ranks |
| 20 | bonus feat, control blood 5b | 1B 1P | 1B 3P | 1F 1B 3P | 5 skill ranks |

---

## 3. Spellcasting

**The tables match the book except for one table.** `rules/casting.py` was compared cell by
cell against the d20pfsrd pages fetched 2026-10-05:

| Table | Book | Result |
|---|---|---|
| `FULL_CASTER` (wizard, cleric, druid), 0–9 × 20 | wizard page | 0 cells differ |
| `SPONTANEOUS_FULL` (sorcerer) 1–9 | sorcerer page | 0 |
| `SIX_LEVEL` (bard) 1–6 | bard page | 0 |
| `SORCERER_KNOWN`, `BARD_KNOWN` | sorcerer and bard pages | 0 |
| `FOUR_LEVEL` (paladin, ranger) 1–4 | paladin and ranger pages | 1 cell differs (L13 4th: book 0, code 1). The three bonus-only rows are lost (D9). |

**Bonus spells from the ability** (`casting.py:317`) were checked against measured slots:

| Character | Ability | Level | Measured slots | Book |
|---|---|---|---|---|
| Sorcerer | Cha 18 | 1 | 1st: 4 | 3 + 1 ✓ |
| Sorcerer | Cha 20 | 12 | 1st: 8 | 6 + 2 ✓ |
| Wizard | Int 22 | 20 | 1st: 6 | ✓ |
| Cleric | Wis 18 | 1 | 1st: 2, plus 1 domain slot | ✓ |

**Lists** (spells on each class list in the corpus): wizard 1,897, sorcerer 1,885, cleric
1,143, bard 868, druid 792, ranger 390, paladin 300.

| Class | Slots / known | Choice-driven spells | Gaps |
|---|---|---|---|
| Wizard | ✓; 2 free spells per level, owed and learned at all 19 levels | **School:** no specialist slot, no opposition (two slots to prepare), no school powers, so every wizard is an unnamed universalist. **Bond:** no bonded-object daily cast, no familiar. | A ×2 |
| Sorcerer | ✓; known increments owed per spell level (e.g. L4: +1 cantrip, +1 2nd) | **Bloodline spells:** none, though the corpus carries them (§1). No swap (D10). | A |
| Cleric | ✓ plus a domain slot per castable level (measured L1–L20) | Domain spells ✓. Subdomains offered alone can leave the slot empty (§1). Powers: 7 of 153 domains. | B |
| Druid | ✓; a domain bond gives domain slots (Air druid at L9: 1st–5th, each holding the Air spell) | Companion bond ✓ (D6). | — |
| Bard | ✓; known increments owed and learned at every level | No swap (D10). | — |
| Paladin, ranger | Slots from 4th/5th (D9) | — | D9 |
| Blood Bending | not a caster | — | — |

---

## 4. Pools and per-day abilities

Every class pool is defined from the class file (`classes.py:420`). All of them refilled on
`rest` `kind: night` (measured before and after for every pool on all 12 classes). The
**only** op that spends one is the generic `resource` (`engine.py:7634`), which subtracts
and says how many are left. Nothing applies what the pool is *for*, the GM brief does not
list them, and the ability bar does not show them.

| Pool | Formula | Measured | Book | Spends to an effect? |
|---|---|---|---|---|
| Barbarian rage | 4+Con+2(L−1) | L1 5, L20 43 | ✓ | no |
| Bard performance | 4+Cha+2(L−1) | L1 8, L20 46 | ✓ | no |
| Monk ki | ⌊L/2⌋+Wis, from 4 | L4 6, L20 14 | ✓ | no |
| Paladin smite evil | 1+⌊(L−1)/3⌋ | 1 → 7 | ✓ | no |
| Paladin lay on hands | ⌊L/2⌋+Cha, from 2 | L2 5, L20 14 | ✓ | no (heals nothing) |
| Druid wild shape | 1+⌊(L−4)/2⌋ | L4 1, L20 9 | at will at 20 | no |
| Domain powers (7 domains) | `powers.json`, e.g. Fire Bolt 3+Wis | 7 | ✓ | no (`not_yet`) |
| Blood Bending ×5 | class file | ki, rage, unbalancing strike, stunning strike, rapid coagulation | homebrew | Blood Rage and the path abilities, through `use_ability` |
| **Missing** | — | — | — | Channel energy (3+Cha/day); stunning fist (L/day); lore master (1–3/day); paladin's channel (2 lay on hands); quivering palm 1/day; school powers (3+Int); bloodline powers; bonded object 1/day |

`use_ability` with rage, smite evil, lay on hands, channel energy, wild shape, bardic
performance, inspire courage, stunning fist, flurry of blows, fire bolt, lightning arc, ki
pool, rage power and sneak attack was **refused on all 12 classes**: "has no ability called
X. They can use: nothing yet." The one exception is Blood Bending's own path abilities.

---

## 5. How established PF1e builders handle class choices

This was searched before any of it was designed, per the standing instruction. A research
pass on 2026-10-05 read Foundry PF1's and PCGen's source and data directly, and Hero Lab
through its forums and Authoring Kit wiki. It said plainly where it could not confirm
something.

- **Foundry VTT PF1**
  - **How features attach.** The class item links features by level through
    `system.links.supplements` (`{level, uuid}`), added when the class level crosses them
    (`module/models/item/utils/level.mjs addItems`).
  - **A choice is a placeholder.** The class grants a generic "Sorcerer Bloodline" or
    "Rogue Talents" item, and the player drags the specific one onto the sheet.
  - **What the level-up form asks.** `LevelUpForm` prompts for hit points, ability score
    points and the favoured class bonus only. It lists incoming features read-only and
    never prompts for a class choice.
  - **What it counts.** Only general feats (`getFeatCount`), behind an "experimental"
    strict-counting setting.
  - **What it abandoned.** A separate "class associations" link type, merged into
    supplements (changelog `feature_2877`).
  - **Later effects.** A chosen bloodline can now carry its own level-gated supplements
    (issue #2875), re-checked whenever the class level changes.
- **Hero Lab Classic**
  - **How choices are built.** One "Custom Ability" mechanism covers bloodlines, rage
    powers, rogue talents and versatile performance. It holds a per-level **count** and up
    to five parallel pools per class.
  - **Validation.** It turns the table red until the count is met ("Fighter: Add more Bonus
    Feats.").
  - **Later effects.** A bloodline bootstraps its powers with level conditions. Its FAQ
    records the trap of a bootstrapped feat showing at level 1 without one.
  - **Not confirmed:** the exact "too few rogue talents" wording, and whether the per-level
    rows are cumulative.
- **PCGen**
  - **How choices are built.** Every choice is an `ABILITYCATEGORY` with a `POOL` formula:
    Rogue Talent, Rage Power, Mercy, Favored Enemy, Combat Style, Arcane Bond, Arcane School
    Specialization, Arcane Opposition School.
  - **Example.** `BONUS:ABILITYPOOL|Rogue Talent|RogueTalentLVL/2`.
  - **When.** Adding a level shows a summary only. Unspent pools appear under "Things to be
    Done", to choose at any time.
  - **What it abandoned.** Class features as "hidden feats", replaced in 5.12–5.14.
  - **Later effects.** A bloodline grants its powers with `PREVARGTEQ` on the class level.
  - **A bug worth knowing.** Bug DATA-211: Extra Rogue Talent did not feed the talent pool.

**What they agree on, and what it means here:**
1. **A mid-level choice is a count owed, derived from class level, with selections checked
   against it.** It is not a fixed slot per level. That is exactly the shape
   `leveling.owed` already uses for feats and points: one counter per pool, and the menu
   and take endpoints re-check. It extends to talents, rage powers and mercies without a new
   idea.
2. **No mature builder forces the choice at the moment of level-up.** All of them nag until
   it is made. The Class tab's "To choose from your levels" is already that.
3. **A choice made at 1st whose effects arrive later is one document carrying its own
   level-gated grants**, re-read against the class level. For the bloodline that means:
   powers at 1/3/9/15/20, spells at 3–19 and feats at 7/13/19 are the bloodline
   document's rows, not the sorcerer table's. That is how `content/domains/powers.json`
   already works (`by_level`, read live).
4. **Extra Rogue Talent and the like must feed the same pool** (PCGen's DATA-211). Here,
   D5's class-feature prerequisites and these pools should be built together.

---

## 6. Ranked gaps

### Counts per class

| Class | A: cannot choose | B: chosen, no mechanics | C: bare string | P: pool only | D: level-up defects | OK |
|---|---|---|---|---|---|---|
| Barbarian | 1 (rage powers ×10 picks) | 0 | 7 | 1 | 2 (D1, D5) | 2 |
| Bard | 1 (versatile performance ×5) | 0 | 17 | 1 | 3 (D1, D5, D10) | 1 |
| Cleric | 0 | 2 (powers for 146 domains; subdomains alone) | 2 | 0 | 3 (D1, D5, D7) | 3 |
| Druid | 0 | 1 (domain-bond attack powers) | 8 | 1 | 4 (D1, D5, D6, D7) | 3 |
| Fighter | 2 (weapon training ×4, weapon mastery) | 0 | 3 | 0 | 3 (D1, D3, D5) | 1 |
| Monk | 0 | 0 | 19 | 1 | 4 (D1, D3, D4, D5) | 3 |
| Paladin | 2 (mercy ×6, divine bond) | 0 | 12 | 2 | 3 (D1, D5, D9) | 0 |
| Ranger | 4 (favoured enemy ×5, combat style ×5, favoured terrain ×4, hunter's bond) | 0 | 10 | 0 | 5 (D1, D2, D4, D5, D9) | 2 |
| Rogue | 2 (talents ×10, advanced talents) | 0 | 3 | 0 | 2 (D1, D5) | 4 |
| Sorcerer | 4 (bloodline; its powers, spells and feats) | 0 | 1 | 0 | 5 (D1, D2, D4, D5, D10) | 1 |
| Wizard | 2 (arcane school, arcane bond) | 0 | 1 | 0 | 3 (D1, D4, D5) | 2 |
| Blood Bending | 1 (Path B after creation) | 0 | 8 | 3 | 4 (D1, D4, D5, D8) | 6 |
| **Total** | **19** | **3** | **91** | **9** | **10 distinct** | |

"C" counts distinct features (a ladder like sneak attack 1d6…10d6 is one). Content
omissions not counted above: monk ki strike, monk fast-movement and AC-bonus ladders, the
monk's 1d10 at 8th, and sorcerer bloodline arcana are **absent from the class tables**.

### Worst blockers, in order

1. **D1: no skill ranks after 1st level, every class.** It is quietly the largest number
   on the sheet. A 20th-level character in these runs is missing 57–190 ranks.
2. **A: the named class choices cannot be made.** These are the sorcerer's bloodline and
   the wizard's school (both named by the owner), plus rogue talents, rage powers, mercies,
   and the ranger's whole kit. 19 choices, about 60 individual picks across 1–20.
3. **Core active abilities are counters only.** Rage, smite, lay on hands, ki, wild shape
   and bardic performance have no op, no button and no line in the brief. Channel energy
   and stunning fist have no pool either.
4. **The monk's core attack is wrong at every level:** −4 non-proficient, 1d3, no Wisdom
   to AC, and no IUS or Stunning Fist feats.
5. **Companions:** they grow only on a reload (D6), and the Animal domain's never comes
   (D7).
6. **Passive numbers that never reach the sheet:** barbarian fast movement and DR, paladin
   divine grace and DR, monk speed. These are cheap and visible.
7. **D9:** paladins and rangers cast nothing at 4th whatever their Charisma or Wisdom.
8. **D2–D5:** bonus-feat plumbing — combat-style and bloodline feats are never owed, the
   forge doesn't check the 1st-level bonus feat, feats the class grants are never written,
   and class-feature prerequisites are never checked.

---

## 7. Notes for whoever fixes this

- **Rules that must hold.** The three laws apply to every one of these (CLAUDE.md;
  `states-effects-tells` skill).
  - Rage is an `ActiveEffect` with a tell, not a number the narrator writes.
  - Divine grace is a modifier through the funnel.
  - Fast movement is a speed term.
  - The `buff` op (`engine.py:7014`) takes `amount` from the intent. It must not become the
    way rage lands.
- **Fix the slug before anyone reads the ladders.** `class.smite-evil-1-day` …
  `-7-day` should be one `class.smite-evil` tag with the count read off the table, the way
  sneak attack's dice are.
- **The choice grammar already has the right bones.** `choices` with `level`, `options`,
  `how_many` and `from`, validated by `classes.validate_choices` and stored in
  `class_choices`. What it lacks:
  - option kinds beyond `domain` and `animal companion`
  - a count that grows with level (`at_levels: [2, 4, 6 …]`, the PCGen/Hero Lab pool)
  - a level-up writer and endpoint
  - the forge asking past 1st level
- **The data for bloodline spells is already in the corpus** (41 bloodlines), exactly as
  domain spells were derivable on 2026-09-19.
- **Hunter's bond can reuse `animal companion` with `level_offset: -3`**, which the
  validator already permits. The Animal domain's `companion_offset: -3` should be read by
  the same `animal_companion.wanted`.

---

## 8. Suggested fix lanes

Grouped so that no two lanes edit the same file. Lane 1 should land first: it defines the
option-kind registry the others plug into. After that, 2–4 can run in parallel.

| Lane | Owns (files) | Fixes |
|---|---|---|
| **1. Class choices and level-up plumbing** | `rules/classes.py` (choice grammar: an option-kind registry, counts by level), `rules/leveling.py`, `rules/creation.py`, `rules/feats.py` (class-feature prerequisites read `class.*` tags), `play/views.py` (level endpoints and `/api/level-up` only), `play/static/js/table/05-sheet.js`, `play/templates/play/home.html`, `play/campaign.py` | D1 skill ranks (owed, menu and take, retroactive Int; the Class tab); the class-choice writer and endpoint, with mid-level choices owed as counts; D2 (bonus-feat pools declared per class: combat style, bloodline feats); D3 forge validation and the monk waiver; D4 granted feats; D5 prerequisites; D6 `animal_companion.sync` after `/api/level-up`, said on the line; D8 Path B. Also the option kinds for **rage powers, rogue talents and advanced talents, mercies, favoured enemy and terrain, combat style, versatile performance, weapon training and mastery, divine bond, hunter's bond**: the picker and storage only. Catalogues go in new `content/class-options/*.json`, not in the class files. |
| **2. Spellcasting features** | `rules/casting.py`, `rules/domains.py`, `rules/animal_companion.py`, `content/domains/powers.json`, new `content/bloodlines/`, `content/schools/` | Bloodline documents: spells derived from the corpus, powers by level, arcana. Arcane school: the specialist slot, opposition cost, school powers. Arcane bond. Domain powers for the 33 core domains. Subdomains need their parent (or the picker shows only complete domains). D7, the Animal domain companion (`wanted` reads `companion_offset`). D9 bonus-only rows. D10 spell swap. |
| **3. Martial passives** | `rules/classfeatures.py` (the slug fix and the readers), `rules/sheet.py` (AC, speed, saves and DR channels), `rules/weapons.py` (weapon groups), `content/classes/*.json` (table corrections only) | Fast movement (barbarian, monk, Blood Bending); DR (barbarian, paladin); divine grace; monk AC, unarmed damage ladder and proficiency; armour training and mastery; bravery and trap sense (they need save descriptors from documents); the monk table's omissions (ki strike, the 1d10, the speed and AC ladders); weapon training's numbers once lane 1 stores the group. |
| **4. Actives: abilities, pools and ops** | `rules/engine.py` (`_op_use_ability` for class-ability documents), new `content/class-abilities/*.json`, `gm/prompts.py` (the brief's ability list), `play/views.py` `_usable_abilities` and `_state` only, `play/static/js/table/04-combat-and-turns.js` | Rage (and greater, tireless and mighty), smite evil, lay on hands, channel energy (and its pool), ki spends, stunning fist (and its pool), bardic performances as toggles with tells, wild shape forms, domain-power attacks (the `not_yet` ranged touches). These are written as ability documents in the grammar Blood Bending's paths already prove, so the engine names no class. Lane 1's rage powers, talents and mercies get their *effects* here, as documents. |

**Shared-file warning:** `play/views.py` is split by function between lanes 1 and 4, and
`content/classes/*.json` between lanes 1 (`choices` stanzas) and 3 (table rows). Keep each
lane to its named keys and functions, or serialise those two files.

---

## 9. Lane 1, built: choices at any level, skill ranks, and the read API

Built 2026-10-05 on `fix/class-choices-and-levelup`. Storing each choice is this lane's
job; making it *do* something is lanes 2-4's. Everything below is what they build on.

### What a class document can now say

The `choices` grammar (`rules/classes.py`, header comment) gained:

| Field | Meaning | Used by |
|---|---|---|
| `at_levels: [2, 4 …]` | one pick owed at each listed level (`level` still reads as `[level]`) | rage powers, rogue talents, mercies, favored enemy/terrain, weapon training, versatile performance |
| option `kind: "class option"`, `from: "<catalogue>"` | the picks come from `content/class-options/<catalogue>.json` | every catalogue choice |
| option `kind: "feature"` | an option with nothing further to pick | paladin's bonded weapon, ranger's bond with companions |
| option `id` | tells two options of one kind apart; answers name it in `option` | divine bond `weapon`/`mount` |
| option `from_choice: "<choice id>"` | the picks are another choice's picks (repeats allowed) | favored enemy +2, favored terrain +2 |
| option `raise: {"field", "base", "step"}` | on a `from_choice` option: write `base + step × times raised` onto each source pick (`classes.sync_raises`, on every write) | the ranger's `bonus` on each favored enemy / terrain |
| option `exclude: [ids]` | entries this option never offers | opposition schools exclude universalist |
| `when: {"choice", "not"}` | owed only once that choice is answered, and not with those picks | opposition schools (not for a universalist) |
| `distinct_from: "<choice id>"` | may not repeat that choice's picks | opposition schools are not your own school |

A catalogue entry is `{"id", "name", "text", "min_level"?, "requires"?: [ids],
"repeatable"?, "variants"?: {"name", "from": [{"id", ...}]}}`, plus whatever the lane that
gives it mechanics needs (a bloodline's `class_skill`, `bonus_feats`, `bonus_spells`,
`powers`, `arcana`; a mercy's `condition`; a perform type's `skills`; a weapon group's
`weapons`). `classes.validate_catalogue` judges only the fields lane 1 reads; the rest are
yours to validate. A homebrew catalogue of the same id in the data directory's
`homebrew/class-options/` adds and replaces entries by id.

The eleven catalogues (`content/class-options/`, gathered from the Core Rulebook
reference at legacy.aonprd.com and d20pfsrd, 2026-10-05; Core Rulebook only):
`sorcerer-bloodlines` (10), `arcane-schools` (9), `arcane-bonds` (bonded object with 5
objects, familiar with 11 animals), `rogue-talents` (15 + 8 advanced at `min_level` 10),
`rage-powers` (28), `paladin-mercies` (15), `favored-enemies` (32), `favored-terrains`
(11), `combat-styles` (2), `weapon-groups` (14), `perform-types` (9).

### The read API (the only door — never read `class_choices` directly)

```python
from rules import classes

classes.chosen(actor, "bloodline")
# -> [{"id": "draconic", "name": "Draconic", "level": 1, "variant": "red",
#      "option": "class option", "entry": {...the catalogue's whole document...}}]
classes.chosen_ids(actor, "rage power")      # -> ["intimidating-glare", "scent", ...]
classes.has_chosen(actor, "mercy", "sickened")
classes.catalogue("sorcerer-bloodlines")     # the whole file, merged with homebrew
classes.entry("weapon-groups", "blades-heavy")
classes.has_feature(actor, "Rage power class feature")   # True / False / None
```

`chosen` returns `[]` both for "not chosen yet" and for "this class asks no such thing";
treat them alike. Picks are in the order taken, repeats kept (a favoured enemy raised twice
appears twice in `favored enemy bonus`). For an animal companion option the one pick's `id`
is the animal; for a `feature` option it is the option's id (`weapon`, `companions`); for a
domain option, one pick per domain held.

**What each lane reads:**

- **Lane 2 (spellcasting).** `chosen(a, "bloodline")[0]` — `entry.bonus_spells` (by level,
  spell names), `entry.powers` (names by level), `entry.arcana`, `entry.class_skill`
  (Arcane has `class_skill_from`, the ten knowledges: the player's pick is not modelled
  yet), `variant` for Draconic's dragon (`entry.variants.from[].energy`, `.breath`) and
  Elemental's element. `chosen(a, "arcane school")` (`universalist` is an entry, with
  `opposable: false`), `chosen_ids(a, "opposition schools")`, `chosen(a, "arcane bond")`
  — `id` `bonded-object` or `familiar`, `variant` the object or animal
  (`entry.variants.from[].grants` is the familiar's gift to its master).
- **Lane 3 (martial passives).** `chosen_ids(a, "weapon training")` in order (the first
  group gets +1 more at every later pick: the book's "+1 to each previous group");
  `chosen(a, "favored enemy")` — each pick carries `bonus` (+2, plus +2 for each raise
  the player gave it; also stored on the pick in `class_choices["favored enemy"]["picks"]`
  as `{"pick", "level", "bonus"}`, the shape lane 3's `classfeatures.chosen` reads); the
  raises themselves are `chosen_ids(a, "favored enemy bonus")`. The same for
  `favored terrain` / `favored terrain bonus`; `chosen(a, "versatile performance")`
  `entry.skills` for the substitution. Weapon mastery (fighter 20) is NOT a choice yet: it
  needs a weapon-kind option reading the weapons table, which is yours.
- **Lane 4 (actives).** `chosen_ids(a, "rage power")`, `chosen_ids(a, "rogue talent")`,
  `chosen_ids(a, "mercy")` (`entry.condition` names the condition removed; `acts_as` on
  Diseased/Cursed/Poisoned), `chosen(a, "divine bond")` (`weapon`, or the mount, which
  already arrives as an animal companion). Rage-power entries carry `once_per_rage`;
  rogue talents carry `sneak_attack: true` on those that ride a sneak attack. Talents that
  grant a feat (Combat Trick: a combat feat; Finesse Rogue: Weapon Finesse; Weapon Training:
  Weapon Focus; the advanced Feat) store the talent only — the feat is NOT owed or written
  yet, and should feed the bonus-feat pool when it is (PCGen's bug DATA-211, §5).

### Skill ranks (D1)

`leveling.skill_ranks(actor)` → `{"owed", "per_level", "total", "spent", "max_rank",
"class_ranks", "int_mod", "race_ranks", "class_skills", "skills": [...]}`. No counter is
stored: owed is `(max(1, class + Int mod) + race ranks) × level − ranks held`, the same
arithmetic `sheet.validate` refuses an over-spent sheet with. It reads the BASE Int, so a
permanent increase pays a rank for every level already taken (Pathfinder dropped 3.5's
"not retroactive"; d20pfsrd Ability Scores, fetched 2026-10-05) and a temporary
ActiveEffect never does. `POST /api/level/skills {"ranks": {...}}`; no skill above the
character's level. Not modelled: the favoured-class bonus (+1 hp or +1 rank a level), and
a bloodline's or a perform type's class skill (lane 2/3).

### Endpoints

| Endpoint | Body | Does |
|---|---|---|
| `POST /api/level/skills` | `{"ranks": {skill: n}}` | places owed ranks |
| `GET /api/level/choices?choice=<id>` | — | the picker: options, entries with `open`/`why` |
| `POST /api/level/choose` | `{"choice", "option"?, "picks"?: [id \| {"pick","variant"}], "pick"?, "name"?, "domains"?}` | answers an owed choice; a companion chosen here arrives at once |
| `POST /api/level/path` | `{"path"}` | Blood Bending's Path B once its track opens (D8) |

`leveling.owed(actor)` gained `skills`, `choices` (`owed`, `picks`: one row per pick owed,
`made`: what is chosen, for the Class tab), `paths` (`open`, `at`, `offered`) and
`outstanding` (everything; `total` still means feats and points alone). The level-up line
says each of them.

### The rest of the lane

- **D2.** `BONUS_FEAT_RULES` gained `ranger` (`grant: "combat style feat"`, the chosen
  style's `bonus_feats` by level, prerequisites waived) and `sorcerer` (`grant:
  "bloodline feat"`, the bloodline's eight, prerequisites kept). Owed at 2/6/10/14/18 and
  7/13/19; a pool whose choice is unmade says "Choose your combat style first".
- **D3.** The forge holds the 1st-level class bonus feat to the class rule: the feats past
  the general budget are the bonus ones, and any assignment that satisfies the rule is
  accepted; a monk's bonus feat has its prerequisites waived there too.
- **D4.** `leveling.granted_feats`: a class-table row that IS a feat's name (Scribe
  Scroll, Endurance, Eschew Materials, Stunning Fist, Blood Bending's Combat Expertise and
  Combat Reflexes), plus the monk's Improved Unarmed Strike. Written at the forge and at
  each level (idempotent), so an older character gets them at the next level. Not on a
  campaign load: tried, and the owner's Bobby (a wizard) gained Scribe Scroll on reading,
  which broke the byte-for-byte round trip of four real saves.
- **D5.** `classes.has_feature` answers the 207 "X class feature" prerequisites from the
  class table's tags, the choices made and the domains held. A clause that is not a
  feature's name stays unknown.
- **D6.** `/api/level-up` calls `animal_companion.sync` and says the growth on the line.
- **Not done here.** D7 (the Animal domain's companion), D9, D10 (lane 2). The per-rung
  duplicate tags (`class.smite-evil-1-day`) are lane 3's slug fix; `has_feature` reads a
  rung as its ladder meanwhile. Fighter weapon mastery (a weapon pick). Rogue-talent and
  rage-power feat grants (above).

---

## 10. Lane 2, built: what the spellcasting choices do

Built 2026-10-05 on `fix/class-spellcasting` (off `integrate/2026-10-05`, lanes 1, 3 and 4
merged in). Research before design: Foundry PF1's `spellcasting-model.mjs`/`spell-model.mjs`
and PCGen's `SpellSupportForPCClass.java` and core-rulebook data were read directly; the
CRB text of every domain, bloodline and school power was read from
legacy.aonprd.com (raw HTML) and spot-checked against d20pfsrd; the subdomain map is AoN's
Cleric Domains.

### Having a power and using it are two documents

- **Having** (`rules/grantedpowers.py`): one reader for domains (`content/domains/powers.json`,
  now all 33 core domains), bloodlines (`content/bloodlines/powers.json`, all 10), schools
  (`content/schools/powers.json`, all 9) and arcane bonds (`content/schools/bonds.json`). A
  file names the class choice it answers; the code names no class and no choice. Pools,
  tags (`resist.$energy.5`), passive `modifiers` through the funnel (`Actor._class_mods`),
  `class_skills` (`Actor.class_skills`), `feats` (written by the forge and
  `leveling.grant_class_feats`), `by_level` rungs and `by_variant` (the dragon, the element,
  the familiar). `$energy` and the other variant fields are filled from the catalogue's
  variant.
- **Using** (`content/class-abilities/domains.json`, `bloodlines.json`, `schools.json`): lane
  4's grammar and executor. `class_abilities._docs_for` now joins any file whose `class` is a
  granted-power kind to the powers `grantedpowers.had` lists (`power`, and `entry` where two
  bloodlines share a key — Claws), resolving `by_level` and `$energy`.

### Casting

- **Domain and school slots** are one mechanism (Foundry's "Domain/School Slots"; its 0.75.11
  "free, uncapped" version was replaced by a counted pool a week later): pools `domain slot N`
  / `school slot N`, copies held as `domain:<id>` / `school:<id>`, prepared through
  `/api/spells/prepare` with `slot`, cast by `_op_cast` from whichever slot holds the copy
  (`casting.cast_source`). A domain spell off the class list (a Fire cleric's fireball) goes
  only in the domain slot. Before: the domain slot was a number nothing could fill or spend.
- **Opposition schools** cost two slots to prepare and to cast (`casting.slot_cost`, read by
  every slot count; Foundry's `restrictedSpellSlotMultiplier`).
- **Bloodline spells** are known on top of the table (PCGen's SPELLKNOWN) at 3rd and every
  odd level: derived, never written into `spellbook`, never counted against Spells Known,
  never exchanged. Catalogue names resolve to corpus ids (`casting.spell_named`: "greater
  teleport" → `teleport-greater`, 6 of 90 needed it).
- **D9**: the paladin/ranger table tells "—" (`NO`) from "0" (bonus only), as PCGen's -1/0 does.
- **D10**: `casting.swaps` / `/api/spells/swap` — sorcerer at 4, 6, 8…, bard at 5, 8, 11…
  (bard: a level below his best; the sorcerer has no such limit in PF1 — that was 3.5), one per
  level, offered until used (`Actor.spell_swaps`).
- **Subdomains** (`content/domains/subdomains.json`): a subdomain's gaps fill from its parent,
  it may not be taken with its parent, and the parent's powers stand in for its own (said on
  the sheet). Ruins and Creation (no parent, spells at few levels) are no longer offered.
- **D7**: the cleric's and druid's class documents ask a "domain companion" at 4th, gated by
  a new `when.only` (owed only with Animal), `level_offset: -3` — `animal_companion.wanted`
  reads it with no change.

### Measured

- `tests/test_caster_climb.py`: cleric (Animal + Sun), druid (Air bond), sorcerer (red
  draconic), wizard (evoker, cat familiar), bard, paladin, ranger, 1→20 through
  `/api/level-up` and the Class tab's endpoints, every pick made: slots per day equal the
  book's table plus the bonus of the score as it stands at every level (the paladin/ranger
  table typed apart from the code's), one domain or school slot per castable level, spells
  known equal to the table with the bloodline's on top, the wizard's two a level, the
  bloodline's and school's powers at their levels. 7 of 7 pass.
- Live (scratch data, port 8817): a Fire/Charm cleric prepared Fireball into her 3rd-level
  domain slot from the Spells tab; at the table Fire Bolt (lane 4's document, this lane's
  pool) hit for 5 and Dazing Touch (this lane's document) dazed the cutpurse, each spending
  one of 6 uses, and the sheet showed "5 / 6 today".

### Not done

- Powers whose effect needs a reader nobody has are counted and said in `not_yet`: d20
  rerolls (Luck, Chaos, Law, Destined), miss chance laid on an attacker (Darkness), auras that
  move with the bearer (Destruction, Liberation, Repose, Sun), periodic damage (Death), shaped
  areas (breath weapon, the 9th-level bursts), flight/burrow/swim speeds, spell resistance,
  metamagic, a channel reading the cleric's tags (Sun, Glory, Death), cast-op hooks (Healer's
  Blessing, Intense Spells), morning picks (Abjuration's energy, Transmutation's score).
- The familiar is its gift to the master only; no familiar creature is made. The bonded
  object's daily spell is a counted use; the cast op still asks for a prepared copy.
- Subdomains' own replacement powers are not written (the parent's stand in).
- The Arcane bloodline's own arcane bond is not a choice the sorcerer document asks yet.
- The narrator, asked in words to "use my Fire Bolt", described a hit with no
  `use_ability` emitted (live, 2026-10-05): the declaration side (`gm/judgement.py`) still
  knows path abilities only. The combat bar's route works.
  **Fixed on fix/typed-class-abilities (2026-10-05).** Where it fell out: `inject_ability`
  returned at "no paths" before looking at anything else, `refuse_unknown_ability` needed
  "I use <Capitalised Name>" (so "use my Fire Bolt" with no "I", any lowercase name, and
  any "(bracket)" after the name missed it), and `leveling.find_ability` searched paths
  only. Now `find_ability` asks `class_abilities.find` after the paths; `inject_ability`
  reads a typed class ability first (`_typed_class_ability`: the documents' names and
  aliases, in three grammatical shapes — object of a using verb, the verb itself, the
  instrument after "with"), aims it, drops the model's guessed numbers and puts it before
  the blow it serves; a mode is named in the player's words through each option's
  `aliases` in the document (`class_abilities.option_for`, longest phrase wins).
  Measured on typed lines with the model's reply at `narrate_only`: 4/41 before,
  59/59 after (18 of them written after the first pass); named-but-not-yet 0/3 → 3/3;
  false alarms 0/33 (3/13 on the held-out lines' first run, answered). Not done: the
  reader (`gm/interpret.py`) has no ability slot, so this is still code reading the
  sentence's grammar — the structured-turn direction would add the sheet's ability names
  as an enum to the reading instead (tests/test_typed_class_abilities.py).

---

## 11. The executor fields, built

Built 2026-10-05 on `fix/class-ability-executor` (off `integrate/2026-10-05`). Prior art
read first: Foundry PF1's action model (`areaTemplate` type/size/origin, `range`, `save`,
`touch`) and change targets (`skills` = "All Skills", `strSkills`, `allChecks`); PCGen's
pattern of a power bonusing a variable the channel reads; GAS's removal tag requirements.
Neither Foundry nor PCGen gates a power by the target's Hit Dice or creature type in data,
so `hit_dice` and `only` are this grammar's own. The grammar is in the module docstring of
`rules/class_abilities.py`; every field is validated on load with the fix named.

| Field | Powers it unblocked |
|---|---|
| `area` (cone, line, burst at range; `"$breath"`) laid by `areas.lay_shape` | Breath Weapon (all ten dragons), Elemental Blast, Hellfire, Grasp of the Dead |
| `only` (creature type) and `roll.ignores_dr` | Artificer's Touch (constructs; DR up to level) |
| `target_requires` | Rebuke Death (below 0 hp) |
| `roll.as: heal_nonlethal`, `lifts` | Calming Touch |
| `hit_dice` (`max`, `over`), read off the printed stat block (`hit_dice_of`) | Dazing Touch (Charm, Enchantment), Blinding Ray |
| `charge.category` / `modifiers` / `spent_on` | Destructive Smite; Stunning Fist wasted on a miss |
| skill_mod target `all` (`Actor.skill_modifiers`) | Touch of Good, Inspiring Word, Touch of Destiny, Diviner's Fortune, Aura of Despair; Strength Surge got Climb and Swim |
| `bonus_from`, `healed_instead` | Sun's Blessing (+level), Glory (+2 DC), Death's Embrace |
| modifier `first_hit`, `self.strikes_as` | Smite's doubled first hit vs outsiders/dragons/undead (type, not alignment), DR bypass |
| `self.ends_when` (swept once per batch) | Smite ends on its mark's death; rage ends when the barbarian falls |
| `self.forbids` | Rage refuses Cha/Dex/Int skills but Acrobatics, Fly, Intimidate, Ride |
| `{target}` in tells | sixteen tells that said "the target" |

Measured live (scratch data, port 8857, the combat bar): a 9th-level red draconic
sorcerer's Breath Weapon aimed at the near thug — "The 30-ft cone catches the near thug and
the far thug", both failed DC 16 and took 23 fire, the thug behind untouched at 13/13; the
narrator then wrote the thug behind "thrown back by the heat", so the area tell now names
who is outside it. A 1st-level Charm cleric's Dazing Touch hit the ogre and "the ogre has
4 Hit Dice, more than 1: Dazing Touch has no hold on them". A Death/Sun cleric's harm
channel: "4d6 — 22. Sun's Blessing adds +8 (30)"; her negative channel: "The energy mends
Morwen instead of harming them. Morwen recovers 6 hit points".

Still not_yet (each said in its document): ability checks (no roller reads one), Hellfire's
shaken on the good (no alignment), Grasp of the Dead's hold (no move-only condition),
objects and hardness for Artificer's Touch, rage's "patience or concentration" beyond
skills, the shaped-area overlay on the map (`play/views.py:_latest_areas` reads `cast`
outcomes only), and an imported monster's `Actor.hit_dice` (still 1; the Intimidate DC in
`rules/attitude.py` reads it).
