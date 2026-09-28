# Printed attacks: a monster fights with what its stat block says

## The defect, as measured

2026-09-27, read-only, through `Engine.run` against the Kesst fixture:
`bestiary.instantiate("ogre")` gave `equipped=None, weapons=[]`, `flat_attack=7`,
`flat_damage="2d8+7"`. Fifty ogre hits came to a **mean of 7.1: 6, 7 and 8, one critical
15, every one an "unarmed strike"**. The ogre's line is `greatclub +7 (2d8+7)`: a minimum
of 9 and a mean of 16.

The chain that produced it:

- `melee` and `ranged` were stripped by `_NOT_ON_THE_SHEET` in `rules/bestiary.py`, and
  nothing read them again.
- `flat_damage` was read by `Actor.damage_dice()` alone, and the engine never called it.
- With no `equipped`, `_op_attack` fell back to `"unarmed"`: 1d3, plus Strength from
  `damage_modifiers`.
- `attack_sequence` returned `[0]` for any `flat_attack`, so `full_attack` gave every
  stat-block creature one swing. An owlbear's line gives it three.

The hand-written guard dog had the same defect in miniature: `equipped: unarmed` beside
`flat_damage: 1d4`, so it punched for 1d3+1.

## How the tools that import stat blocks do it

Researched before designing (primary sources where they could be reached):

- **Combat Manager** (Kyle Olson, `CombatManagerCore/monster.cs`, `Attack.cs`) keeps the
  printed numbers. An attack is a list of printed bonuses, damage, crit range and
  multiplier, riders and a count, and "or" groups are `AttackSet`s. When Strength or size
  changes it applies a *delta* to the printed numbers rather than recomputing them.
- **The PF1 statblock converter (sbc)** for Foundry (`scripts/Parsers/Offense/attack-parser.js`)
  derives each attack from BAB, ability, size, feats and enhancement, then stores
  `printed − derived` as an `attackBonus` labelled "[adjusted by sbc]" so the printed
  total comes out exactly. Its changelog (3.0.3) records a rework after derived attacks
  "regularily achiev[ed] over +50 modifiers". It infers secondary attacks and the
  Strength multiple backwards from the offset.
- **Foundry's PF1 system** derives everything at roll time (BAB + ability + size +
  `attackBonus`, `naturalAttack.secondary` −5 and ×0.5 Str). Its issue #1501 is a primary
  attack still showing the secondary penalty. That is the classic failure of inferring
  the attack's type at the point of use.
- **PCGen** stores dice only and derives the bonus.

Every tool that derives has had to add a fudge field to match the book. The recommended
shape, and the one built, is the Combat Manager one: **the printed totals are the base,
and only what the print cannot know goes on top.** That means conditions, spells, the
board and the water.

The rules this leans on are from the Bestiary's universal monster rules, natural attacks
(aonprd.com). A secondary attack is "base attack bonus –5 and add only 1/2 the creature's
Strength bonus". A lone natural attack takes 1.5× Strength. Natural attacks get no
iteratives. The melee line gives "its attack roll modifier listed after the attack's name
followed by the damage in parentheses" (Bestiary introduction). None of this is
re-derived here: all of it is already inside the printed number. No PF1 primary sentence
was found that defines "or" outright. The monster-entry-format page's Dagon example
("trident … or 2 slams") shows it as alternatives, which is how it is read.

## What was built

- **`rules/statblock_attacks.py`** reads a melee or ranged line into *options* (the book's
  "or") of *attacks* (its commas). Each attack carries:
  - its name and count;
  - every printed bonus (`+11/+6` is two numbers, and the second is the book's, not the
    first minus five);
  - the damage dice and the printed flat bonus;
  - the crit;
  - whether it is a touch attack, and whether it is automatic (a swarm or troop);
  - riders, typed extra dice, and ability damage;
  - the weapons-table weapon the name stands on, or the natural-attack family.

  It normalises the PDF's typography: an en dash for minus and for crit ranges, × for
  multipliers, a size word before an enhancement, and "gra b". It reads **7,053 of the
  7,090** blocks with a melee line. The rest are prose, "none", a truncated parenthesis
  or an attack printed with no bonus. Those keep the old behaviour rather than a guess.
- **`Actor.stat_block_attacks`** reads the lines *live* off `_creature_doc()`, the way
  `movement_modes` reads a climb speed. Correcting a creature on the bench corrects every
  one already standing in a scene, and nothing is copied into a save.
- **`Actor.weapon(key)`** answers a printed attack before the natural-weapon and table
  lookups. The table supplies what the print omits (hands, traits). The print overrides
  the dice (a Large greatclub's 2d8, not the table's 1d10), the crit and the type.
  Natural types follow the UMR table: bite piercing, claw slashing, gore piercing, and
  so on.
- **`Actor.wielded_key`** is `equipped`, then the first printed attack, then the fist.
  Every `equipped or "unarmed"` in the sheet and the attack op now asks it.
- **The modifier funnel.** `attack_modifiers` puts in one term, the printed bonus for
  *this* swing, named "greatclub (stat block)". It adds no BAB, Strength, size,
  proficiency or iterative −5, since all of those are inside the print. Conditions,
  buffs, water and position are added exactly as before. `damage_modifiers` puts in the
  printed flat damage instead of Strength. Feats stay suppressed by `_flat_for`, as they
  always were for printed numbers.
- **`Actor.attack_plan`** returns (weapon, iteration) per swing. For a character it is
  `attack_sequence` unchanged. For a monster's full attack it is the whole printed option
  the named attack sits in (owlbear: claw, claw, bite), each entry swung as often as the
  print says. "2 +1 short swords +19/+17/+12/+12/+9" is five swings, not ten: when a
  count comes with that many bonuses, the bonuses already list every blow.
- **The attack op** resolves each swing's own weapon, so the bite of claw-claw-bite rolls
  the bite. It also:
  - resolves touch attacks (243 printed) against touch AC, keeping the water and cover
    terms;
  - gives swarms the troop rule (automatic damage, no roll), since their lines print no
    bonus;
  - rolls typed extra dice ("plus 2d6 cold", 551 attacks) *before* the main die, as the
    rider and sneak dice are, and lands them as their own packet, never multiplied on a
    crit;
  - lands an ability-damage touch ("incorporeal touch +4 (1d6 Str)", 35 attacks) through
    the `ability_damage` op, the one applicator, the way `_natural_riders` lands a race's
    rider.

  Every hit from a printed attack carries `origin: creature:<template>`.
- **Gates.** A monster reaching for a weapon its block does not print is refused, naming
  the ones it has. It used to swing that weapon's dice at its printed +7 with its
  Strength on top, which is neither the book's number nor a derivation.
  `intents._known_weapon` lets printed names ("tendrils", "tail slap") through the parse
  gate, which cannot see the actor, for the engine to decide. That is the arrangement the
  races' natural attacks already had.
- **The NPC turn message** names the creature's printed attacks, by name only: no bonus,
  no dice, because the model never authors a number.

## What this changes for balance

Hit chance did not change: the stat-block creature always rolled `flat_attack`, the
printed primary bonus. What changed is damage per hit and swings per round. Expected
damage before (1d3 + Str, one swing) against after (printed primary; whole first option
on a full attack), over every imported block with a readable melee line:

| CR band  | blocks | before, per hit | after, per hit | × (median) | after, full attack | × (median) |
|----------|-------:|----------------:|---------------:|-----------:|-------------------:|-----------:|
| 1/8 – 1  |    904 |             3.7 |            6.0 |        1.5 |                9.2 |        1.5 |
| 2 – 3    |   1104 |             3.8 |            6.2 |        1.5 |                8.4 |        1.8 |
| 4 – 6    |   1549 |             4.6 |            8.0 |        1.6 |               13.3 |        2.4 |
| 7 – 10   |   1667 |             5.5 |           10.3 |        1.8 |               22.9 |        3.8 |
| 11+      |   1648 |             7.8 |           16.3 |        1.9 |               50.0 |        5.8 |

Named cases: ogre 7.0 → 16.0 a hit; owlbear 6.0 → 22.5 a full attack; troll 7.0 → 26.5.

The XP table (`xp.CR_AWARD`) was never wrong. What was wrong is that every fight played
before this paid full CR experience for monsters doing between two-thirds and a sixth of
their printed damage. The encounter windows in `rules/ontheway.py` (CR level−2 to level+1)
and `rules/gathering.py` (to level+2 for a guardian) were settled against those
half-strength monsters. At level 1 a guardian can be CR 3, and a CR 3 ogre now averages
16 a hit against Kesst's 9 hit points. The windows are the user's to revisit; this change
leaves them alone.

## Not done, on purpose or not yet

- **Riders are carried, not fired.** Grab 650, poison 415, disease 213, paralysis 173,
  energy drain 147, trip 82, bleed 74. The engine's `_natural_riders` resolves trip and
  grab as a Reflex save for races, which is not 1e's free combat manoeuvre, and poison
  and disease need their documents. Each is its own piece of work.
- **A Strength change does not move a printed number.** Ability damage, enlarge person or
  rage on a monster leaves its printed attack where it was, the same as `flat_attack`
  before. Combat Manager's delta (Δmod to hit, Δmod × the attack's Strength multiple to
  damage) is the known answer. It needs the Strength multiple decided once at parse
  (1, 1.5 or 0.5), and inferring that is exactly where Combat Manager's own code is
  wrong (a `"Natual"` typo that never matches).
- **One damage type per blow.** A bite is B/P/S in the book and piercing here, and DR
  bypass by type is not wired for any attack yet.
- **"nonlethal" is parsed and not honoured**, because no weapon's `nonlethal` flag is read
  by the attack op. That is a pre-existing gap: saps and fists deal lethal damage for
  characters too.
- **The 37 unread blocks** keep swinging their fists at `flat_attack`.
- **Printed options are picked by name.** A full attack with no weapon named uses the
  first option. "claws" finds the option whose entry is printed "claws" before one
  holding a lone "claw".
