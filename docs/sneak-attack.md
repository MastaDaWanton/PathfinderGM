# Sneak attack, applied

Group 15 of the fix pass after the 2026-09-19 play-test: the half of item 27 that group 13
wrote down and deliberately did not claim. Branch `sneak-attack`. Tests:
`tests/test_sneak_attack.py` (22).

`docs/hollow-classes.md` stated the debt plainly: *"Making sneak attack apply itself is a
damage rule the engine has to run rather than a document it reads — it is the one item in
this group that is not finished by writing a table down, and it is not claimed here."*

Before this, the phrase "sneak attack" appeared in the app twice: in `rules/glossary.py` as
a definition nothing read, and in the rogue's new table as a row nothing applied.

## The rule

From the rogue's own page
([d20pfsrd, read 2026-09-20](https://www.d20pfsrd.com/classes/core-classes/rogue/)):

- extra damage "any time her target would be denied a Dexterity bonus to AC … or when the
  rogue flanks her target";
- 1d6 at 1st, another d6 every two levels, to 10d6 at 19th;
- "Ranged attacks can count as sneak attacks only if the target is within 30 feet";
- "A rogue cannot sneak attack while striking a creature with concealment";
- the extra damage "is not multiplied" on a critical hit.

## The thing that is easy to get wrong

**Immunity to critical hits is not immunity to sneak attack.** That was 3.5. In Pathfinder
1e undead and constructs are "not subject to critical hits" and can still be sneak
attacked; only traits that refuse precision damage in as many words stop it. Two could be
quoted from the source:

> **Ooze traits / elemental subtype** — "Not subject to critical hits or flanking. Does not
> take additional damage from precision-based attacks, such as sneak attack."

**Incorporeal and swarm could not be confirmed** on d20pfsrd's own pages: the Universal
Monster Rules entry for Incorporeal does not mention critical hits or precision damage at
all, and that page has no swarm entry. They are honoured anyway, because the corpus's stat
blocks carry the subtype and the claim is widely held — but they live in a constant named
`IMMUNE_SUBTYPES_UNSOURCED`, apart from the quoted ones, so that a sourced rule and an
unsourced one are never mistaken for each other. A test asserts the two sets stay separate.

Immunity is read from the creature's **own document** — its `immune` list and its `subtype`
— rather than from a list of type names kept in the module, on the same argument
`leveling.table_die` makes for reading a table column by name: a creature that ships with
traits nobody here has heard of still behaves correctly.

One further immunity is this project's reading rather than a quoted rule, and says so: **a
troop**. `rules/troops.py` already holds that a unit is immune to anything aimed at a
specific number of creatures; a blow aimed at one vital spot is the same argument, and
there is no single guard to slip past in a crowd.

## Where it lives, and what it is not allowed to duplicate

`rules/precision.py`, for the reason `rules/position.py` gives about itself: none of these
questions can be answered by the sheet. Whether a swing is a sneak attack depends on the
defender's guard, on where both of them are standing, on how far apart, and on what the
defender is made of. Scene in, dice out; nothing mutates.

**The flanking answer is not a second copy.** `position.attack_mods` had the flanking loop
inline; it is now `position.flanking_with`, and both the +2 and the sneak dice read it. A
second copy would have been a rule with two homes, which is the failure CLAUDE.md records
as having shipped a corrected consequence rule beside a stale one. The extraction is
behaviour-identical — `tests/test_position_modifiers.py` passed unchanged.

**The dice come off the class table**, not from arithmetic on the level. Group 13 wrote the
rogue's ladder down; this reads it, so an archetype or a homebrew class that grants sneak
attack on a different ladder is right for free.

## Where it lands in the roll

On the same shelf as the rider die, and for the same reason: extra damage dice do not
multiply on a critical, so both are rolled separately and added **past** the crit
multiplier, never folded into the weapon's notation. That order was learned once already —
a live critical showed "+12 fist die (1d6) x2", the rider doubling alongside Strength — and
this reuses the shape rather than rediscovering it.

The player rolls the dice themselves, as its own popup. `tests/test_engine.py` now records
the whole rule in one line of a player-visible breakdown:

    ["Str x2", "sneak attack (1d6)"]

Strength multiplied by the crit, the sneak dice not.

## Said either way

The "why not" is worth as much as the "why": a rogue who never sees their dice is owed the
reason. Every branch answers in words — *their guard is down*, *flanking with Ally*, *too
far for a precise shot — 45 ft, and a sneak attack reaches 30*, *Foe is concealed*, *Foe has
ooze traits — no anatomy for a precise blow to find* — and the narrator is told it as a fact
of the blow, never as a rule that fired. Third law.

## Proved live

Driven over HTTP on a copy of the save, with the PC made a 5th-level rogue and a swing
taken inside a running fight:

    AWAITING: Attack with unarmed strike | die 1d20 | breakdown ['BAB', 'Str']
    AWAITING: Sneak attack (3d6)         | die 3d6
    AWAITING: Damage (unarmed strike)    | die 1d3 | breakdown ['Str', 'sneak attack (3d6)']

Three dice at 5th level, off the table; handed to the player; named on the damage roll.

## One thing the three-laws ratchet caught

The first version asked `defender.has_condition("invisible")` for concealment, and
`tests/test_three_laws.py` failed on the literal-key ceiling within the hour. It is a
prefix question now — `has_state("state.hidden")` — which covers invisibility and whatever
else anyone hides behind later without this line being edited again. The ratchet working
on new code the day it was written is the whole point of having it.
