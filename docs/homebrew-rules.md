# Homebrew rules

How a user adds content the app has never heard of — items, creatures, NPCs, classes,
feats, and the rules that come with them — without either writing code or writing
something the engine silently ignores.

Read `intent-protocol.md` first. This document is the same idea pointed at a different
problem: the protocol keeps the *GM* on its side of a line, and this keeps *user-authored
rules* on theirs.

---

## 1. The line

> **A homebrew rule the engine cannot enforce is worse than no homebrew rule at all.**

Not equal to — *worse*. If a feat says "you may feint as a swift action" and the engine
does not know that, the GM will narrate the feint, the player will believe it happened,
and every number downstream will be wrong in a way nobody can see. A missing rule is
visible. A decorative one is not.

So the editor's job is not to accept what the user writes. It is to **prove at save time
that every declared effect maps to something the engine actually reads**, and to refuse —
or explicitly stamp `narrative_only` — anything that does not. This is the same shape as
the protocol's legality check, deliberately.

The mechanism is the same one that has worked everywhere else in this project: *detect
mechanically, repair with a targeted call*. Three registries, built from the running code
rather than from a list somebody maintains by hand:

| Registry | Built from | Answers |
|---|---|---|
| `EVENTS` | every `emit()` site in `rules/` | what a trigger may listen to |
| `CHECKS` | every legality check in `rules/intents.py` | what a permission may relax |
| `OPS` | the intent `OPS` table | what an action may resolve as |

An entry naming something outside its registry does not save. The error names the closest
matches, because the common case is a typo or a synonym, not a genuinely new mechanic.

---

## 2. Four tiers

Everything a user can write falls into one of four bands, in increasing order of what it
demands from the engine. The tiers are worth naming because they let the editor say
*"this part of your class works today, this part needs me"* instead of failing whole.

**Tier 1 — Numbers.** A feat grants +2. A class has d10 hit dice and 3/4 BAB. Pure data;
`rules/tables.py` already models it. Works the day the editor exists.

**Tier 2 — Resources.** A pool with a maximum, gain and spend triggers, and a refresh.
Declarative, because the engine already emits the events a resource needs to hear.

**Tier 3 — Permissions.** "You may do X, which the rules normally forbid." Almost never a
new mechanic: nearly always an existing one with a changed action cost, a dropped
prerequisite, a removed restriction, or an extended range. An enumerable set of
relaxations against named checks.

**Tier 4 — Composed actions.** A new action expressed as existing ops: *"resolves as an
attack roll; on hit, add staggered for 1 round"*. Executable today, because the intent
protocol already resolves everything this way.

Below tier 4 is engine code, and the editor should say so rather than pretend. The
boundary is honest and it is testable: if it cannot be expressed in the shapes in §4, it
needs a developer.

---

## 3. Storage

Homebrew is user data. It lives beside campaigns and characters in the user data
directory, and two rules from `CLAUDE.md` apply directly.

**It merges over the built-in tables; it never replaces them.** World Bible served a
five-day-old stylesheet across four versions because a derived cache in the user data
directory outlived every reinstall. If homebrew ships as a *copy* of `WEAPONS` with the
user's additions, then every future correction to the real weapon table is shadowed by a
stale file the user has no reason to suspect. So: an overlay of additions and named
patches, applied at load, over whatever the current build ships.

**It is version-stamped, and content is compared, not timestamps.** An overlay written
against an older `CHECKS` registry may name a check that no longer exists. That must be
caught at load and reported, not discovered mid-fight.

**Ids are namespaced.** `homebrew:blood-bending`, never `blood-bending`. This keeps user
content from colliding with the tables, and it keeps it clearly separated from Open Game
Content — which matters for the licence, since the user's class is theirs and not OGC.

---

## 4. The shapes

Seven of them. Each one exists because a real ability needed it; the citations are to
Blood Bending, the class this model was designed against (§6).

### 4.1 Class

Tier 1. A table, plus references into the shapes below.

```yaml
id: homebrew:blood-bending
kind: class
hit_die: 2d8                 # a dice expression, not an int — 1e assumes one die
hit_dice_per_level: 2        # see §6: "per Hit Die" effects need a count, not a size
bab: three_quarters          # named progression, so iteratives are derived not typed
saves: {fort: good_plus_1, ref: good, will: good_minus_1}
skill_ranks: 4
class_skills: [acrobatics, climb, craft, ...]
levels:
  1:  {grants: [bonus_feat, unarmed_strike, homebrew:blood-bond], fist: 1d6, blood: 1d8}
```

`bab: three_quarters` rather than twenty typed integers is not tidiness. A typed column is
twenty chances to introduce an error that only shows up at 14th level, and Blood Bending
arrived with exactly that error (§6).

### 4.2 Resource

Tier 2. Three fields here did not exist in the first draft of this model; each was forced
by an ability that would otherwise have been unimplementable.

```yaml
resources:
  - id: ki
    max: "floor(level/2) + con_mod"     # formula over sheet values, validated on save
    starts: max
    refresh: {on: rest.night}

  - id: blood_stack
    scope: target                       # NEW: lives on the creature it is applied to
    cap: none                           # the class declares "no upper limit" explicitly
    consumed_by: [homebrew:vortex-pull, homebrew:mass-rupture, ...]

  - id: bloodlink
    upkeep:                             # NEW: pay per round or the effect ends
      cost: {resource: nonlethal, amount: 1d10}
      per: round
      action: free
      unpaid: end
```

```yaml
cooldown: {dice: 1d3, unit: turns}      # NEW: a randomised recharge, not an integer
```

`scope: target` is the important one. The first version of this model assumed a resource
belongs to its owner. Blood stacks live on the *enemy*, are applied by one ability and
spent by four others, and the owner never holds them.

### 4.3 Spawned object

Tier 2, and the shape that most nearly broke the model. Not a pool on a sheet and not a
counter on a target: a **thing in a square, with a lifetime and its own interactions**.

```yaml
spawns:
  - id: blood_pool
    occupies: square
    duration: {minutes: 1}
    on_occupied: {spawn_instead: blood_spike}   # never two pools in one square
    affords: [absorb, detonate, convert, attack_origin]
```

`affords` lists what other abilities may do to it, and each verb must be implemented by an
op. An ability referencing an affordance the object does not declare fails to save.

### 4.4 Reaction

Tier 2. An ability that fires on an event rather than on the owner's turn — including
during someone else's.

```yaml
reactions:
  - id: sanguine_spray
    on: damage.taken
    when: "amount >= 10 and single_hit"
    then: [{op: apply_resource, id: blood_stack, area: {cone: 15}, toward: attacker}]
```

The `when:` expression is arithmetic over event fields and sheet values. It is not a
scripting language and must not become one: no assignment, no loops, no calls. If a
condition cannot be written as a comparison over declared fields, the ability needs code.

**Interception is the hard case.** Crimson Guard redirects an attack aimed at an ally onto
the interceptor, which means the damage pipeline has to be *interruptible mid-resolution*
— a reaction that fires between "damage computed" and "damage applied" and can change the
target. That is a base-engine prerequisite (§5), not something the overlay can add.

### 4.5 Relaxation

Tier 3. A named check, and how it bends.

```yaml
relaxes:
  - {check: movement.provokes_aoo, set: never}        # Blood Pool Movement
  - {check: attack.count.standard, add: 1}            # Swift Strikes
  - {check: attack.count.full_round, add: 2}
  - {check: cover.applies, set: never}                # Pool Resonance
```

Four verbs cover everything found so far: `set`, `add`, `allow`, `remove`. A relaxation
naming a check outside `CHECKS` does not save.

### 4.6 Compulsion

Tier 3, and a genuinely new category: **a rule that constrains the GM's choice rather than
the engine's arithmetic.** Nothing in the maths stops an enemy attacking whoever it likes.

```yaml
compels:
  - id: aggressive_draw
    save: {kind: will, dc: standard}
    on_fail: {prefer_target: source, else: {attack: -4}, rounds: 1}
    binding: false                       # a penalty, not a prohibition
```

This is fed to *both* writers: into the scene brief so the GM knows, and into the legality
check so the engine applies the penalty. The two-writers model already assumes the GM will
sometimes ignore what it was told, and this is exactly that case.

**Compulsions penalise; they do not prohibit.** The engine never refuses an intent for
targeting the wrong creature — it attaches the −4 and lets the attack through. This is the
author's decision and the reasoning is sound on its own terms: an enemy that eats −4 to
swing at somebody else will usually miss, and if it connects, Crimson Guard lets the
Coagulator take the hit anyway. The path pulls aggro through consequences rather than
through a rule that overrides the fiction, which is also the only reading that leaves the
GM free to have a desperate enemy do the desperate thing.

### 4.7 Composed action and judgement bands

Tier 4. A new action written as existing ops.

```yaml
actions:
  - id: blood_javelin
    cost: standard
    pay: {resource: nonlethal, amount: blood_dmg}
    resolves_as:
      - {op: attack, range: 60, damage: "blood_dmg * 2"}
      - {op: apply_resource, id: blood_stack, amount: 2, on: hit}
```

Some costs are not computable — Extracorporeal Blood Manipulation charges
`1d6 × Complexity × Size`, and *complexity is never defined anywhere in the source*. In
most engines that is unimplementable. Here it is the intent protocol working as designed:

```yaml
judgement:
  - id: complexity
    bands: {trivial: 1, simple: 2, complex: 3, intricate: 4}
```

The GM picks a band the way it already picks a DC band; the engine multiplies and charges
the cost. The GM supplies what the fiction determines, the engine supplies what the sheet
determines. A homebrew ability may declare its own bands, and the same reasoning applies
as in the protocol: a model choosing one of four words is doing a classification task,
which it is good at.

### 4.8 Inferred values

Source documents lose things. Blood Bending's `.docx` arrived with every save DC missing —
fourteen empty fields. Rather than blocking on all of them, a value may be marked:

```yaml
dc: {formula: "10 + level/2 + con_mod", inferred: true}
```

Inferred values are used in play, shown in a different colour in the editor, and listed on
the class's page so the user can correct them as they come up. The point is that the
inference is *visible* — a guessed DC that looks identical to an authored one is the same
failure mode as a decorative rule.

---

## 5. What the base engine owes first

These are not homebrew features. They are 1e mechanics any serious campaign hits, they are
missing today, and a whole Blood Bending path is built on each of them. They belong in
`rules/`, not in the overlay, and they block the class.

| Mechanic | Status | Blood Bending demand |
|---|---|---|
| Temporary hit points | absent | Blood Sponge, Clotting Shield, all three Rage tiers, Blood Bond overflow; *Temp HP reaching 0* is itself a trigger |
| Ability score damage | absent | Blood Boil (1d4 CON, twice), Blood Shatter and Mass Rupture (2 CON) |
| Damage reduction | absent | Iron Clot DR 2/5/8/12/−, declared to stack with Blood Buffer |
| Item hardness and HP | absent | Caustic Blood damages equipment; also unblocks sunder |
| Interruptible damage pipeline | absent | Crimson Guard redirects an ally's incoming damage |

Temp HP is the one to build first. It is load-bearing for an entire path, it interacts with
the class's own unconsciousness rule, and it is *core 1e* — every campaign wants it.

---

## 6. The worked example

Blood Bending is the class this model was designed against, and the design changed four
times while reading it. That is the point of a worked example: each shape in §4 exists
because something in this document would otherwise have been unimplementable.

| Shape | Forced by |
|---|---|
| `scope: target` | Blood stacks live on the enemy; four abilities spend what one applies |
| `upkeep` | Bloodlinks cost 1d10 non-lethal per round or they drop |
| `cooldown: {dice}` | Vampiric Recovery and Vortex Pull recharge on 1d3 turns |
| Spawned objects | Blood Pools: a square, a one-minute life, six things that act on them |
| Reactions | Sanguine Spray, Viscous Threat, Blood Sponge, Hemophormic Retribution |
| Compulsion | Aggressive Draw and Exsanguinating Taunt constrain enemy targeting |
| Judgement bands | Extracorporeal Blood Manipulation's undefined "Complexity" |

### Source discrepancies

Two source files exist and they disagree. The **PDF** is authoritative for the progression
table; the **.docx** is authoritative for the ability text, having all four paths where the
PDF has two.

The `.docx` progression table is corrupted — columns shuffled inconsistently, row by row.
By 8th level the `xN` iterative notation has migrated into the Fortitude column, and rows
8–20 of its "Fort Save" are literally the PDF's BAB values.

The PDF's table is trustworthy for a checkable reason: its BAB column is
`0,1,2,3,3,4,5,6,6,7,8,9,9,10,11,12,12,13,14,15` — **exactly** standard 3/4 BAB, with `xN`
being the iterative count. Its saves are equally regular: Reflex is textbook good-save
progression, Fortitude is good-save +1, Will is good-save −1.

This is why §4.1 stores `bab: three_quarters` rather than a typed column. The progression
is derivable, and a derived column cannot arrive shuffled.

### Hit dice: size and count are different questions

`hit_die: 2d8` is the *size* of a level's roll. But 1e also uses "Hit Die" as a **count** —
and Blood Bending does too: all three Rage tiers grant *"2/3/4 temporary hit points per Hit
Die"*. In every other class the two are interchangeable, because one level is one die. Here
they are not, and this class is the first thing in the app to make the distinction matter.

**Two Hit Dice per level**, per the author. A 20th-level Blood Bender therefore has 40 HD:
Mighty Blood Rage grants +160 temporary hit points, and the character sits outside the HD
caps on effects like *sleep* and *colour spray* far earlier than their level suggests.
`hit_dice_per_level` is explicit in §4.1 because any effect keyed to HD reads it, and a
class that silently used level would be wrong in both directions.

### Designed for a party of one

The author's stated intent: *this class is designed to take on solo what a four-person
party would normally take on.* That is not a footnote — it resolves a mismatch the app
already has.

Pathfinder's encounter maths assumes a group. The Core Rulebook says so in as many words:
*"these encounter creation guidelines assume a group of four or five PCs."* This app runs
**one** PC. Every CR and APL number in `reference/encounter-design.json` is therefore
calibrated for a party this app does not have, and that is true today, for Kesst, with no
homebrew involved.

So Blood Bending is not merely a class the overlay has to survive. It is a class built to
close exactly the gap between what 1e's encounter tables assume and what a single-player 1e
app actually is. Its hit dice, its three near-good saves, its DR, its temp HP economy and
its self-healing all read differently in that light: not overtuned, but tuned for a party
of one.

Two consequences for the engine, both outside this document's scope but recorded here
because this is where the reasoning lives:

- CR budgeting needs a party-size input, and for this app it is 1 unless a class declares
  otherwise. A class may want to advertise `party_equivalent: 4`.
- Encounter difficulty is one of the few places the GM agent reaches for a number without
  the engine owning it. That is a protocol gap, not a homebrew one.

Values supplied by the author after both files were read:

- Coagulated Plate: armour bonus `3 + control_blood_level` (minimum +4, maximum +8)
- Blood Booster: `2d6` non-lethal per +1, cost doubling per additional +1 — which
  reproduces the PDF's `2d6 / 4d6 / 8d6 / 16d6 / 32d6` table exactly, confirming that
  table was the **cost** and not the bonus
- All remaining missing DCs default to `10 + ½ level + CON mod`, marked `inferred`

---

## 7. Out of scope, deliberately

**Scripting.** `when:` is a comparison over declared fields. The moment it grows
assignment or control flow, this stops being a data format and becomes a language with no
debugger, no tests, and no way to tell a user why their class does nothing.

**Balance.** The engine applies what it is told. Blood Bending has three near-good saves,
2d8 hit dice and +2 CON per five levels; that is the author's decision and the app's job is
to run it faithfully, not to argue.

**Rewriting core resolution.** A ruleset may toggle and override — max HP at 1st level,
crit confirmation off, massive damage off. It may not replace how attacks resolve.

---

## 8. Open

- **How does an overlay written against an older registry heal?** Reporting at load is the
  floor. Offering the closest current check by name is better, and is the same
  nearest-match machinery the editor already needs for typos.
- **Does a homebrew class need its own GM guidance?** A class whose entire economy is
  self-inflicted non-lethal damage will read as suicidal to a narrator that has not been
  told otherwise. Blood Bending's own answer — *"take on solo what a four-person party
  would"* — is a sentence the GM needs, and there is nowhere in the format to put it yet.
- **Where does party size live?** It is not a class fact, a campaign fact or a world fact
  cleanly; it is a property of the table. But nothing can budget an encounter without it.
