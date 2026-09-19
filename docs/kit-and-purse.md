# The kit and the purse

Group 10 of the fix pass after the 2026-09-19 play-test
(`docs/playtest-2026-09-18.md` item 24, whose price half shipped with group 7). Branch
`kit-and-purse`.

**Reported.** *"Remove the starting items from classes and give them extra starting gold,
we have the outfitter now."*

## The arithmetic that made this a return to the book

Eleven hand-written class kits lived in `rules/creation.KITS`, read at exactly one site.
Nothing else in the app granted gear, and a homebrew class never had a kit at all — so the
eleven shipped classes were the only ones the rule did not apply to.

And starting gold was **already rolled**. `creation.starting_purse` has read each class's
own `starting_wealth` line since 2026-09-07 and rolled it rather than averaging it, so a
character was walking out of the forge with the Core Rulebook's full starting wealth *and*
a free kit on top. A fighter's kit prices at **172 gp** against an average roll of **175**.

That is why the player's "extra starting gold" needed no new grant: the extra gold is the
gold that was always there and had been quietly pre-spent on somebody else's choices. What
the book actually gives is one line — *"each character begins play with an outfit worth 10
gp or less"* — which is `OUTFITS`, and it stays.

## What was built

- **`KITS` deleted.** A new character leaves the forge with their outfit, their purse, and
  their hands: `weapons` is the body's own weapons plus `unarmed`, `armour` and `shield` are
  `none`. The old fallback for a class with no kit was a dagger, and a Blood Bending player
  met it mid-fight — "the panel opened their first attack with a knife they never chose,
  never saw in their inventory, and rightly said they were not carrying". That fallback is
  now the rule for everybody.
- **The class features stay**, because they were never in the kit: a wizard's `spellbook` is
  a field on the sheet, and nothing in the casting rules requires a focus or a component
  pouch as an object. Removing the kits cost no caster anything.
- **The outfitter is reachable on purpose.** It was on the way out of the forge and nowhere
  else, so a character who skipped it had no way back — and now that the purse is the whole
  gear budget, an unspent one is a character with nothing but their hands. The roster card
  has an **Outfit** button, which opens the same page with the same world.

## Measured live

A fighter forged through `/api/character/create` and sent to the shop:

- **At the shop**: `purse 170 gp`, `weapons ["unarmed"]`, `armour "none"`, `shield "none"` —
  the outfit on her back and nothing else.
- **Buying the old kit back**: longsword, dagger, **club**, chain shirt, heavy shield and
  five days' rations came to **139.5 gp**, leaving **30.5 gp** in the purse. The club is the
  one the shop refused to stock until group 7 priced it, so the two halves of item 24 meet
  here.

Under the old scheme she would have had that kit *and* the 170 gp. Now she chooses, which
is the rulebook — and the choice is a real one, since the kit costs most of a fighter's
roll.

The **Outfit** button was driven from the roster in the browser: it opens
`/outfit/?character=…&world=…` for the right character with the right shelf, and the free
weapons print as "free" rather than "0 gp".

## Three documents that were telling authors a falsehood

`starting_wealth` was described as read by nothing, in three places, and had not been true
since the purse was wired up:

| Where | Said |
|---|---|
| `rules/classbuilder.py` (the bench's field help) | "nothing in the app rolls starting gold yet, and a character is created with a kit rather than a purse" |
| `docs/class-creation.md` (the authoring contract) | "**Nothing.** No starting gold is rolled; a new character is given a kit." |
| `tests/test_classbuilder.py` | pinned `starting_wealth` in the set of fields with no consumer |

All three now name `creation.starting_purse` as the consumer and say what the line is for:
a character's whole gear budget, rolled rather than averaged, because a fixed 35 gp for
every fighter is a different game from one where the dice decide whether you can afford the
breastplate.
