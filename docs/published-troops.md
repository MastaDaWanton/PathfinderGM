# The corpus's own troop blocks, as crowds

Group 16 of the fix pass after the 2026-09-19 play-test, and the last item
`docs/the-crowd.md` recorded as deliberately unfinished. Branch `published-troops`. Tests:
`tests/test_published_troops.py` (82, most of them one per block).

## What was recorded, and the half of it that was wrong

> "The corpus's own 22 troop-subtype blocks (a goblin troop at 52 hp, an imperial infantry
> troop at 126) still spawn as ordinary actors. Their `subtype` is stripped before the Actor
> is built, which is the easy half to fix — but a published troop's hit points ARE the unit's
> pool and **its member count is nowhere in the data**, so giving them attrition would mean
> inventing a number per block. The troop *rules* without the attrition would leave a readout
> saying '1 of 1'. Left alone rather than half-built."

The count is not in the block. It is in the **subtype**, which the note never went back to
read. From Archives of Nethys, read 2026-09-20
([Monster Subtypes: Troop](https://www.aonprd.com/MonsterSubtypes.aspx?ItemName=Troop)):

> "A troop of Small or Medium creatures consists of approximately **12 to 30 creatures**."
>
> "A single troop occupies a **20-foot-by-20-foot square**, equal in size to a Gargantuan
> creature."

## Sixteen, and why it is not a number anybody chose

Twenty feet is four squares, so the subtype's stated footprint is 4x4 = **sixteen squares**.
`troops.size_for` puts one person in each square — the player's ruling from group 9, which
replaced the subtype's fixed size band with "however many squares the people would take up".

So sixteen is the count at which the published footprint and this app's own ruling agree,
and it sits inside the published band. It is a *ceiling*, not a target: a member's share of
the pool is the pool over sixteen **rounded up**, and the count is then whatever
`members_left` makes of the full pool — the same function that runs attrition in play, so a
block cannot start out disagreeing with itself or overflow the square the rules give it.

Measured over all twenty-three blocks:

| | |
|---|---|
| members | 13 to 16 — every block inside the stated 12–30 |
| footprint | Gargantuan, every block, which is the subtype's own answer |
| a member | 5 hit points in a Cult Rabble, 12 in a Profaned Paladin Troop |
| the pool | the block's published hit points, untouched |

The spread comes from the blocks, not from here. Nothing is invented per block, which was
the objection the note raised.

**The goblin troop the note names arrives as thirteen goblins of four hit points**, out of
its published 52.

And the count was wrong too: the corpus holds **23** troop blocks, not 22.

## Naming a member, and admitting when the name has none

The tells want a singular — "five goblins go down" — and the block's name is the only place
to get one. `troops.one_of` strips the unit word and singularises: "Imperial Archers Troop"
gives an *imperial archer*, "Troop, Cultist" a *cultist*.

Some names do not name anybody. A member of a **Cult Rabble** is not a "cult"; a member of an
**Avalanche Legion** is not an "avalanche"; a member of **Irgal's Axe Troop** is not an
"irgal's axe". Those answer with nothing at all, and `tell_of` already had the right sentence
for that case — "eight of them go down" — which is true and reads properly. Deciding that a
member of a Cult Rabble is a "cultist" would be chasing vocabulary, the losing move CLAUDE.md
records; saying "of them" costs nothing and is never wrong.

## One resolver, after a bug that was exactly the reason for the rule

Three blocks are filed index-style — "Troop, Goblin" rather than "Goblin Troop" — and
imported as `troop-goblin`. They were reachable **only** by that spelling: a spawn asking for
"goblin troop", which is what anybody would write, found nothing. `_index_order` moves the
leading word to the end, which is the whole of the transform the corpus applies.

The first version taught that alias to `lookup` and not to `instantiate`, which had its own
copy of the resolution — so the live check spawned a goblin troop and got **one creature**,
because the caller and the lookup disagreed about what the name meant. That is precisely the
failure CLAUDE.md records about copies of a rule, committed while writing the fix for
something else. There is one resolver now, `bestiary.raw_block`, and both read it.

## Proved live

Spawned through the engine's own `spawn` op — the same one the model emits — then fought
over HTTP:

    UNIT 'Troop, Goblin': hp 52/52 gargantuan | 13/13 x 4 hp | member 'goblin'
    ... 30/52 huge      |  8/13 | fallen 5
    ...  9/52 large     |  3/13 | fallen 10

    "Troop, Goblin are all around Masta — no single blow to parry, and no roll to make."

The footprint steps down as they die, the crowd attacks without an attack roll, and sneak
attack is refused against it.

That run also found two defects no test had: the refusal tell printed **twice** on every
swing, because the damage stage is re-entered on each resume and the tell was unguarded; and
`capitalize()` lowercased the rest of the name, turning "Troop, Goblin" into "Troop,
goblin". Both fixed, both now tests, and both invisible to everything except driving it.
