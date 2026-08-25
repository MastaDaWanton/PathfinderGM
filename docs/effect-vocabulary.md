# The effect vocabulary

`rules/effectspec.py` is the catalogue of everything an authored effect can say. It is
data, and three things read it: the homebrew builder draws its forms from it, `validate()`
accepts or refuses against it, and the engine executes against it. Adding an effect type is
adding an entry there — no form is written by hand, and the editor and the engine cannot
drift, because both sides read the same file.

This document covers the additions made for the spells the vocabulary could not hold: what
each one is, what backs it, a worked example, and — at the end — an honest list of what
still cannot be said.

---

## Why these, and not others

Twenty agents read all 3,040 spells one at a time and converted them into effect specs.
6,476 specs came out validating. **3,134 of them were `narrative`** — an honest refusal
with a reason attached, because the vocabulary had no shape for what the spell did.

The reasons converged. In rough order of how many spells each cost, and what was done:

| Gap | Spells | Answer |
|---|---|---|
| No repeating / per-round damage | ~150 | `trigger: each_round` |
| No recipient — everything landed on "the target" | ~40 | `recipient` on every type |
| Modifier amounts could not scale | ~50 | `amount` accepts a formula |
| No manifested thing (fog, walls, lights, hazards) | ~130 | `manifest` |
| No operation on another spell | ~180 | `spell_operation` |
| No summoning | ~135 | `summon` |
| No exclusive choice between forms | ~45 | `choose_one` + `bundle` |
| No concealment / miss chance | ~90 | `concealment`, and `invisible` |
| Dice-less per-level damage | 3 | `dice` accepts `10/level` |
| Duration shapes the parser refused | ~30 | `rolled`, `base`, `concentration_plus`, weeks/months |
| Negative levels | 31 | `negative_level` (declarative) |
| Attitude | 33 | `attitude` (declarative) |
| Spell resistance granted | ~10 | `spell_resistance` (declarative) |
| Damage to objects | ~40 | `object_damage` |
| `blindsight` missing beside `blindsense` | ~10 | one vocabulary entry |

**Nothing that validated stops validating.** Every addition is optional with a default that
means what an absent value has always meant. `tests/test_effectspec_extensions.py` runs the
whole corpus through `validate()` and asserts zero problems — 6,476 specs in, 0 out.

---

## The two fields that go on everything

These are on `COMMON`, so every type has them. They are on *every* type rather than on the
five that obviously want them because *who an effect lands on* and *when it fires* are
questions every type has an answer to, and putting them on five types means the sixth
silently cannot ask.

### `recipient` — whose sheet it touches

`target` (default) · `self` · `caster` · `attacker` · `ally` · `area`

Every spec used to land on "the target", full stop. That is the root of a whole family of
false conversions the readers kept catching: eruptive pustules, thorn body, planar aegis,
profane nimbus, holy aura, unholy aura, cape of wasps, water shield, life shield and
kinetic reverberation all deal their dice to **whoever strikes you** — and borrow
corruption drains the *caster* while targeting somebody else.

Written without a recipient these are worse than prose. Measured, on the first run of the
executor: thorn body, converted mechanically, produced the tell **"Kesst Vayr takes 5
piercing"** — the spell set fire to the druid it was protecting.

### `trigger` — when it fires

`on_cast` (default) · `each_round` · `when_struck` · `when_grappled` · `on_enter` ·
`on_expiry`

The single largest cause of a *fully stated, unambiguous* spell falling to prose.
Incendiary cloud is 6d6 fire, Reflex half, **every round**; as a plain `save_gate` it fires
once at casting and never again, understating the spell by however many rounds the cloud
stands. Acid fog, acid arrow's continuation, wall of fire's heat, hungry pit, pain strike,
black tentacles, vortex and poison are all this shape.

A trigger other than `on_cast` **requires a duration**. Without one, `each_round` has no
rounds and `when_struck` has no window to be struck in, so the effect would be authored,
accepted, and never fire once. (A hazard nested in a manifestation's `on_enter` inherits
the manifestation's lifetime and does not restate it.)

**What backs it:** `Scene.wards`, a list of `Ward` on the scene. `Scene.guards` is the
precedent and the shape is deliberately the same — a standing arrangement is a
*relationship*, and a copy on each creature is two things to keep level. Repeating damage
and retribution turned out to be the same structure with a different event on the front,
and covered a third case (a hazard paid on walking into it) without being asked to.

---

## Formulas

`amount` used to be an int, which put a whole family out of reach: "an insight bonus equal
to your caster level, maximum +5", "+1 per four caster levels", "half your caster level".
Divine favor, divine power, authenticating gaze, lay of the land, liberating command, ward
the faithful, wrath, wave shield and protection from spores all state their bonus as a
formula, and all had to be stored as a flat number with the real rule in a `note` nothing
reads — a spell that silently stops scaling.

`save_gate.dc` has accepted a formula since it was written. This is the same shape, made
general. **An integer still validates exactly as before.**

Variables: `caster_level`, `level`, `spell_level`, `hit_dice`, `casting_mod`, and
`str_mod` … `cha_mod`. Operators: `+ - * /`, brackets, `min()` and `max()`. **Division
floors**, because 1e floors: "+1 per three caster levels" at caster level 5 is +1.

```json
{"type": "combat_mod", "amount": "min(1 + caster_level/3, 3)",
 "bonus_type": "luck", "target": "attack",
 "duration": {"amount": 1, "unit": "minute"}}
```
> *+1 luck to attack rolls per three caster levels, minimum +1, maximum +3* — divine favor.

The list of variables is **closed**. A formula naming something else is refused at
authoring time with the whole list in the message, because `caster_lvl` would otherwise
evaluate to 0 — a +0 bonus, which looks exactly like a spell that did nothing and reports
nothing at all. The evaluator parses with `ast` and whitelists node types, so an authored
string cannot reach attribute access, subscripts, comparisons or any call except min/max.

### Dice that scale

`dice` now also accepts `10/level`, `10/level, max 150` and `1d6/2 levels`. Harm, implosion
and wail of the banshee deal a flat 10 points per caster level; `dice: "10"` is wrong at
every caster level above 1st by a factor of the level. The floor is one die or one point —
"1d8 per two caster levels" at 1st is the smallest the effect can be, not nothing.

For a **spell**, `rules/spells.py`'s `scaling` dict is still the right place: one formula on
the spell, applied by `effects_at`. This is for the other authors — a homebrew feat, a magic
item, a creature ability — which carry effects with no spell around them.

---

## `manifest` — the user's "temp-spawning"

A thing that is now *there*: fog, a wall, a light, an illusion, a lingering hazard.

**What backs it, and why it is executable rather than narrated:** `rules/grid.py`'s `Grid`
already keeps `obscuring`, `blocked` and `difficult` square sets. The tactical map draws
them, `Grid.reachable` routes around them, and `Grid.line_of_sight` reads them. A fog cloud
is twenty feet of obscuring squares; a wall of stone is blocked squares; grease is difficult
squares. Nothing new had to be invented, only written to. `Scene.pools` (`BloodPool`) is the
precedent for the other half — a positioned thing with a lifetime, ticked with the round and
cleared with the encounter.

### Worked example: fog cloud

```json
{"type": "manifest",
 "what": "a bank of fog",
 "terrain": "obscuring",
 "shape": "radius",
 "size": 20,
 "duration": {"amount": 10, "unit": "minute"}}
```
> **A bank of fog — a 20-foot radius spread, blocking sight for 10 minutes**

Cast at caster level 10, measured: **61 squares** enter `Grid.obscuring`, and
`line_of_sight((5,5), (12,5))` flips from `True` to `False`. `rounds_left` is 1,000 — 100
minutes, read out of the printed line "minutes/level (10)" by `spells.parse_duration` and
turned into rounds by `duration_rounds`.

Two details that are easy to get wrong and are handled:

* **Lifting takes only what it added.** A fog cloud rolled over a stone pillar covers the
  pillar's square and did not make it opaque. `Manifestation.added` records what actually
  changed, so the dungeon does not lose its own walls when the fog lifts.
* **A scene with no map still works.** Most scenes have no grid — a conversation in a tavern
  has no squares. The thing exists, expires on the same clock, and the tell says it was
  placed in the fiction only.

### Worked example: incendiary cloud (a hazard that repeats)

`on_enter` holds what happens to whoever is in it. It is registered as an area ward and
fires on the round tick.

```json
{"type": "manifest",
 "what": "a cloud of white-hot embers",
 "terrain": "obscuring", "shape": "radius", "size": 20,
 "duration": {"amount": 1, "unit": "round"},
 "on_enter": [
   {"type": "save_gate", "target": "ref",
    "dc": "10 + spell level + casting ability modifier",
    "recipient": "area", "trigger": "each_round",
    "on_failure": [{"type": "damage", "dice": "6d6", "damage_type": "fire",
                    "lethality": "lethal"}],
    "on_success": [{"type": "damage", "dice": "3d6", "damage_type": "fire",
                    "lethality": "lethal"}]}]}
```

The DC on the spec is `spells.SAVE_DC_FORMULA`, a placeholder string — the spell cannot know
the caster's ability modifier. The ward carries the **computed** DC as a number, so nothing
ever compares a roll against a sentence.

---

## `spell_operation` — the user's "permanency"

Spells whose target is another spell: permanency, dispel magic, break enchantment,
counterspelling, suppression, antimagic, absorbing a rune.

`make_permanent`, `dispel`, `suppress` and `extend` act on the **real lifetimes the engine
keeps** — a `Buff.rounds_left`, a `Condition.rounds_left`, a `Manifestation.rounds_left`.
The caster level check is rolled where the book calls for one.

### Worked example: permanency

```json
{"type": "spell_operation", "operation": "make_permanent", "target": "fog cloud"}
```
> **Make it permanent: fog cloud**

Cast a fog cloud at caster level 11 and it stands for 1,100 rounds. Follow it with the
permanency above and `rounds_left` becomes `None` — measured, and it then survives
`tick_standing(5000)`.

### Worked example: dispel magic

```json
{"type": "spell_operation", "operation": "dispel", "target": "fog cloud",
 "check_dc": "11 + caster_level"}
```

A d20 + caster level against DC 22 at caster level 11. On a failure the magic stands and the
tell says so; on a success the manifestation is lifted and its squares come off the map.

`counter` and `absorb` are **reported, not pretended**: both resolve during another
creature's casting, and the engine has no readied-action step to hang them on. The tell says
the GM adjudicates it rather than answering with a shrug.

---

## `summon`

Routed to `bestiary.instantiate` — the same door the `spawn` op uses — rather than given a
creature system of its own. A summoning spell and a GM saying "two bravos step out of the
dark" are the same event with different fiction attached.

```json
{"type": "summon", "creature": "guard dog", "count": 1, "side": "caster",
 "duration": {"amount": 5, "unit": "round"}}
```

The creature rolls initiative if it arrives mid-fight, and `side: caster` puts it on the
caster's side — without which a wizard's own dog counted against them and the fight could
not end while it was standing. A creature the Bestiary does not carry is **refused by name**:
a summon that quietly produces nothing is a spell the player paid a slot for and cannot tell
did not work.

---

## `choose_one` and `bundle`

"Choose one of these forms." Every polymorph spell (beast shape, elemental body, plant
shape, monstrous physique, vermin shape), blindness/deafness, ego whip (Int, Wis or Cha),
joyful rapture, and wish's nine options. Emitting the branches as separate specs applies all
of them at once — a druid becoming five animals simultaneously.

`bundle` groups a form that is several effects together, so an option can be more than one
thing.

```json
{"type": "choose_one",
 "duration": {"amount": 1, "unit": "minute"},
 "options": [
   {"type": "bundle", "label": "bear",
    "effects": [{"type": "ability_mod", "amount": 2, "bonus_type": "size", "target": "str"},
                {"type": "combat_mod", "amount": 2, "bonus_type": "natural armour",
                 "target": "ac"}]},
   {"type": "bundle", "label": "wolf",
    "effects": [{"type": "ability_mod", "amount": 2, "bonus_type": "size", "target": "dex"}]}]}
```

The caster names which with `{"op": "cast", "params": {"spell": "...", "choose": 1}}`. **A
cast that names none applies none**, and says which options there were — applying all of
them is the failure the type exists to stop. A choice with fewer than two options is
refused: one option is not a choice, it is just that effect.

---

## `concealment`, and `invisible`

Displacement, blur, entropic shield and blurred movement are *entirely* a miss chance and
were entirely inert. Writing 50% as an AC bonus would change **which** attacks land rather
than how many, which is a different spell.

```json
{"type": "concealment", "miss_chance": 50, "blocks_targeting": "no",
 "duration": {"amount": 1, "unit": "round"}}
```

Held as a `Buff` with `kind: "concealment"`, so it expires on the same clock as everything
else. `_op_attack` rolls a percentile after a hit is determined and before damage. The best
source wins — two 20% miss chances are not 40% in 1e and are not 36% either.

Two notes on the design:

* **The engine rolls it, not the player.** A considered exception to "the player rolls their
  own": 1e does not call this an attack roll, and adding a fourth suspension stage to every
  swing to ask for it would cost more than it is worth. The number is in the tell either way.
* **`invisible` finally means something.** It sat on the unimplemented-condition ledger in
  `tests/test_reference.py` for want of exactly this. It now carries `concealment: 50` and
  the book's +2 to hit, and has left that list.

`bleed` also left the ledger: it was waiting on "a per-round damage tick the engine does not
have yet", which `trigger: each_round` is.

---

## Smaller additions

* **`object_damage`** — shatter, warp wood, rusting grasp, heat metal. `rules/sheet.py` gives
  every `Item` a hardness and hit points and `damage_all_gear` already puts damage through
  both; this is the missing way for an authored effect to reach them. Energy is halved
  against objects before hardness — except acid, which bites.
* **`blindsight`** in the sense vocabulary, beside `blindsense`. A real difference in 1e:
  blindsense locates a creature and still leaves it total concealment; blindsight does not.
  A spell granting the better one had to be written as the weaker.
* **Durations.** `spells.parse_duration` gained four shapes: rolled lengths
  (`rounds (2d4)`, `hours (4d12)` — 17 spells, previously refused outright), a fixed base
  with a per-level tail (`rounds (1) + rounds/3 levels (1)` — the base was being dropped),
  `concentration + X` told apart from `concentration, up to X` (they are not the same spell),
  and `weeks` / `months`. Unparsed duration lines went from 107 to 90, and the 90 are honest
  refusals — 74 of them say "see text".
  `roll_duration` rolls a rolled length once, with the engine's seeded dice, at the moment
  the spell is cast; `duration_rounds` stays deterministic because every card, tooltip and
  preview calls it.

### Declared, not executed

These are structured and shown to the GM rather than narrated as prose, and each says in its
`blocked` text exactly what happens instead. A structured statement a GM can read at a glance
beats a paragraph; claiming to apply it would be worse than both.

* **`negative_level`** (31 spells) — counted and shown with what it costs: −1 on every
  attack, save, skill and ability check, −5 hit points, −1 caster level, each. Not applied,
  because a negative level moves eight numbers on the sheet at once and applying seven of
  them would be worse than applying none.
* **`attitude`** (33 spells) — 1e's hostile/unfriendly/indifferent/friendly/helpful track.
  Recorded on the creature. No check in the app consults an attitude yet: Diplomacy is rolled
  against a DC the GM sets, not against a track.
* **`spell_resistance`** — recorded on the sheet. `_op_cast` rolls no check to overcome SR,
  because no creature in the app carries a rating to check against and half a check would be
  worse than none (`docs/spells.md` §5.1).

---

## What the executor does and does not touch

Deliberately narrow. `spells.casting_plan` still owns the rolled dice and the save, and the
6,476 specs the corpus carried before these types existed keep the exact path they had. What
runs is what could not be **said** at all before, plus anything whose trigger is not
`on_cast`.

In particular, **a bless's +1 is still rendered for the GM rather than applied.** That is a
separate argument with its own test pinning the current answer
(`test_a_buff_is_shown_to_the_gm_rather_than_invented`), and it needs a decision about
stacking that this change is not making.

One change was necessary at the source: `casting_plan` used to claim any top-level `damage`
spec as the dice the caster rolls now. A spec aimed at somebody who is not the target, or
waiting on a trigger, is neither — and claiming it is exactly how the thorns landed on the
wrong creature. `_is_the_spells_own` is that guard, and both its fields absent means what
absence has always meant, so all 6,476 existing specs answer `True`.

---

## What still cannot be said

Honestly, and with the reason.

* **Damage of two types at once.** `damage_type` holds one value. Judged not worth a second
  field: an author writes two `damage` specs, which composes and costs nothing. Refused
  deliberately rather than overlooked.
* **Threat range.** The whole keen family — about ten spells. `combat_mod`'s `amount` is a
  number added to something, and "doubled" is not that. It would need its own type with its
  own semantics for ten spells; the ratio is wrong.
* **`slowed`, `cursed`, `diseased`, `poisoned` as conditions.** Asked for, and refused:
  they are not in Appendix 2. `slow` is a spell whose effect is a bundle of modifiers, and a
  curse, a disease and a poison are afflictions with their own rules. Inventing a condition
  the book does not have is the failure `test_the_engines_conditions_all_exist_in_the_book`
  exists to catch.
* **`broken` for objects.** In Appendix 2, but it is an *item* condition and `CONDITIONS` is
  a creature table read by `Actor._condition_mods`. `Item.broken` already exists as a
  property; the gap is a way to *show* it, not a way to hold it.
* **`incorporeal`.** Half damage from everything non-magical, which `Actor.take_damage` has
  no notion of.
* **Fractional damage halving as a spec.** The engine halves the rolled total for a
  successful save because that is where the number exists; `effectspec` still cannot say
  "roll and halve", and the stored success branch carries half the *dice*. Same mean, same
  floor, same ceiling — `docs/spells.md` says so under INTEGRATION NOTES.
* **Removing a sense.** No type takes a sense away.
* **`situational_mod` is still `engine=False`.** Protection from evil/chaos/good/law is +2
  deflection AC and +2 resistance saves *against evil creatures*, and the engine does not
  know a target's alignment. A toggle the GM flips would work and is the right shape; it
  needs a new op and a `Buff.active` flag, and it was cut to keep this change testable.
* **Spell resistance, negative levels and attitude** — declared, not executed. See above.
* **`counter` and `absorb`** — reported, not executed. See above.
