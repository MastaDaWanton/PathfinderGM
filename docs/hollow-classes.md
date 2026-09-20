# The three classes that granted nothing

Group 13 of the fix pass after the 2026-09-19 play-test (`docs/playtest-2026-09-18.md`, the
rest of item 27). Branch `hollow-classes`. Tests: `tests/test_hollow_classes.py`.

**Reported** as a screenshot of the Class tab: *The whole table*, levels 1 to 20, "What it
grants" reading **—** on every row.

## The table was honest; the document was empty

Eight classes live in `content/classes/*.json` with real 20-row `levels` tables. **Cleric,
fighter, wizard and rogue** lived in `rules/tables.CLASSES` — enough to build a character
and nothing more. So no bonus feats, no armour or weapon training, no arcane bond or school,
no channel energy — and **no sneak attack**, a phrase that appeared exactly once in the
whole app, in `rules/glossary.py`, as a definition nothing read.

The cleric shipped with group 12, because its domain slot is part of that arithmetic. These
are the other three.

## Read off the page, not out of memory

Each table was taken from its own rulebook page on 2026-09-20
([fighter](https://www.d20pfsrd.com/classes/core-classes/fighter/),
[rogue](https://www.d20pfsrd.com/classes/core-classes/rogue/),
[wizard](https://www.d20pfsrd.com/classes/core-classes/wizard/)), because a class table is
exactly the kind of thing that is 90% right from memory and wrong in the places that matter.

- **Fighter** — a bonus feat at 1st and every even level; bravery at 2, 6, 10, 14, 18;
  armour training at 3, 7, 11, 15; weapon training at 5, 9, 13, 17; armour mastery at 19 and
  weapon mastery at 20.
- **Rogue** — sneak attack 1d6 at 1st and another d6 every odd level to 10d6 at 19th;
  trapfinding at 1; evasion at 2; a talent every even level; trap sense every third level
  from 3; uncanny dodge at 4 and improved at 8; advanced talents from 10; master strike
  at 20.
- **Wizard** — arcane bond, arcane school, cantrips and Scribe Scroll at 1st, and a bonus
  feat at 5, 10, 15 and 20.

## One thing the stubs were getting wrong quietly

The proficiency lists were not merely thin, they were **wrong in play**: the fighter stub
declared `("simple", "martial")` and no armour at all, so by the app's own
`Actor.is_proficient` every fighter in the game was taking the untrained penalty in his own
plate. The rogue had no light armour either, and the wizard's list named a light crossbow
but not a heavy one. All three now carry the book's list.

## And a wrong number that had been shipping

Writing the tables from the page rather than from memory turned one up. The wizard's
`starting_wealth` stub said **3d6 x 10 gp**; the Core Rulebook's Starting Character Wealth
table says **2d6 x 10 gp**
([d20pfsrd, read 2026-09-20](https://www.d20pfsrd.com/basics-ability-scores/character-creation/)).
Every wizard ever forged got roughly 35 gp too much, and a test had pinned the error as
though it were the rule. The fighter's, rogue's and cleric's lines check out.

This is the argument for the whole exercise: a table nobody has checked against its source
is a table with an unknown number of these in it.

## What was still a document and not a mechanic — done 2026-09-20

These tables say what a level **grants**, in the same shape the other eight classes use, and
that is what the Class tab reads. Making sneak attack apply itself is a damage rule the
engine has to run rather than a document it reads — it was the one item in this group that
was not finished by writing a table down, and it was not claimed here. The table said the
rogue has it, at the right levels, which was the half that was missing from the screen the
player photographed.

**The other half landed as group 15**: `rules/precision.py`, `docs/sneak-attack.md`,
`tests/test_sneak_attack.py`. The dice are read off the table written above rather than
computed from the level, so this document is now the thing the mechanic obeys — which is
the arrangement the whole group was for.
