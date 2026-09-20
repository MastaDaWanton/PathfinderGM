# The crowd

Group 9 of the fix pass after the 2026-09-19 play-test
(`docs/playtest-2026-09-18.md` item 33, which also completes item 30). Branch `the-crowd`.
Tests: `tests/test_the_crowd.py`.

**Asked for in as many words.** *"A crowd of people should be spawned as a single unit with
the combined hp of all its members, it should take up however many squares the people would
take up, find a way to display this and allow for them to be killed giving xp, run away and
scatter."*

## A reversal, not a gap

The only collective code in the app did the opposite on purpose.
`bestiary.split_collective_name` turns "a pair of guards" into two actors, and its docstring
records why: a single 11-hp actor called "pair of guards" meant the player "fought half as
many people as the fiction described". That was right for two guards and wrong for a crowd,
so what this group added is a **line** rather than a new opinion — `troops.UNIT_FROM = 5`.
Below five they still arrive as themselves. At five and up the fiction is a crowd, the board
could not hold them as bodies anyway (`_PROMOTED_CAP` is four), and one unit of twelve is a
truer answer than four actors named "twelve soldier".

## Three traditions, each supplying what the others lack

**Pathfinder's troop subtype** ([Archives of Nethys](https://www.aonprd.com/MonsterSubtypes.aspx?ItemName=Troop))
for the shape, and its words are the spec: no attack rolls but "automatic damage to any
creature within reach"; saves "as a single creature"; immune to "any spell or effect that
targets a specific number of creatures"; "half again as much damage (+50%) from spells or
effects that affect an area"; and at 0 hit points it "break[s] up, effectively destroying the
troop".

**One of those is deliberately not implemented as written.** A troop's fixed
20-foot-by-20-foot square is exactly what the player ruled against — "however many squares
the people would take up" — so `troops.size_for` derives the size from the member count:
Medium at one, Large at four, Huge at nine, Gargantuan at twelve, Colossal past sixteen. The
grid and the map already draw whatever comes out.

**13th Age's mooks** for the attrition the troop rules lack: a collective pool equal to the
sum of the members', and every member's worth of damage kills one, with the excess
cascading. That is the "combined hp" of the request exactly, and it is what makes the unit
visibly shrink — twelve raiders are 348 hit points, and 87 of them takes three off their
feet and the footprint down from 4×4 to 3×3.

**Basic D&D's morale** for running away, because Pathfinder has no general morale rule —
which is why its troops can only be destroyed. The [Old School Essentials
SRD](https://oldschoolessentials.necroticgnome.com/srd/index.php/Morale_(Optional_Rule))
keeps the durable version: 2d6 against a morale score of 2 to 12, higher than the score and
they surrender or flee, checked at the first death and again when half are down, a 12 never
checking and two passes meaning they fight to the death. Published bandits sit at 8, which is
the default here.

## What was built

- **`rules/troops.py`** — the `Troop` record (member template, member hit points, member
  worth, live count, count on arrival, morale, fallen, checks) and the rules as functions:
  `size_for`, `pool_for`, `members_left`, `settle`, `owes_a_check`, `morale_holds`,
  `xp_owed`, `damage_multiplier`, `immune_to_single_target`, and `form`, which builds the
  unit out of one member's stat block so a unit of raiders fights like a raider.
- **`Actor.troop`**, saved and loaded. Hit points stay the ordinary hit-point machinery —
  the shared pool IS hit points — so nothing needed a parallel store.
- **Attrition in the one place hit points leave an actor** (`Actor.take_damage`), which is
  the law about one applicator kept for a number that is not an effect. The blow reports
  `fell` and `members` beside the damage, and the size follows the count down.
- **`Engine._unit_took_it`** for the morale check on top of it, and `Engine._rout` for what
  a broken unit does: out of the sides, out of the initiative, off the board through the one
  destroyer. The survivors scatter, which is the request's own word.
- **The debt outlives them.** A fight's XP settles on the way out of an encounter and a
  routed unit is gone by then, so the amount is written where the scene remembers things
  (`scene.said["routed_xp"]`) and `xp.award_for_fallen` settles it — once, because a second
  fight in the same room must not pay for the first one's dead.
- **The two Pathfinder rules that are not about hit points**, both answered by the corpus
  itself: `casting_plan` now reports `area` and `targets_counted`, because fireball's area
  is "20-foot-radius spread" and magic missile's target is "creatures (up to 5)". A crowd
  takes half again from the first and is immune to the second — and the immunity is *stated*,
  because a caster who wastes a slot on it must be told why.
- **No attack roll**, at the attack's own first stage. This also solves a real engine problem
  the player would have met immediately: twelve raiders would otherwise be twelve NPC turns
  and twelve rolls a round.
- **The readout.** The state payload carries `members` and `members_max`; the token is hatched
  rather than solid and carries the live count as its glyph, with "17 of 24 still standing" in
  the tooltip. A filled 3×3 block reads as one big creature, and the whole point is that it
  is many people standing together.
- **The prose door.** `promote_cast` forms a unit when the ledger's count reaches five, which
  is what finally settles item 30's cap: "a band of twelve raiders" is a unit of twelve.

## Measured live, one fight on a copy of the `masta` save

"I charge the twelve raiders coming up the road and swing at the nearest of them", then a
dozen turns of cutting them down, each dice popup answered through `/api/roll`.

| What was watched | What happened |
|---|---|
| The unit forming | **348 hit points, 12 of 12, Gargantuan, placed on the board** — from `repair_misaimed_attack`'s spawn, through `_bring_in`, as one actor. |
| The map | A hatched, dashed 4×4 foe token glyphed **12**, tooltip "raiders — 348/348 · 12 of 12 still standing", unmistakable beside the single-square tokens. |
| Its attack | "The raider's swing is less of a strike and more of a crushing wall of motion" — automatic damage, no attack roll, and one NPC turn instead of twelve. |
| The attrition | 12 → 11 → 10 → 9 → 8 → 7 → 6 → 5 → 4 → 2 → 0, the footprint stepping **Gargantuan → Huge → Large → Medium** as they fell. |
| The morale | First blood passed, half-strength passed — so by Basic D&D's own rule they fought to the death, and did. |

Two defects the unit tests could not see, both fixed:

- **"I charge the twelve raiders coming up the road" spawned ONE creature**, 29 hit points,
  called *"twelve raiders coming up the road"* — the "twelve soldier" family of bug at a site
  nobody had checked. `repair_misaimed_attack` now reads the count with `opponent_count` and
  strips both the number and the participle clause from the name, so it is twelve of
  *"raiders"* — and at twelve the engine forms the unit.
- **The last beat read "raiders is bleeding out."** A crowd does not bleed out. At 0 members
  a unit breaks up — Pathfinder's own rule — with no dying, no stabilising and no
  round-by-round loss, because what has been reduced is a formation and not a body. The
  first version of this fix wrote a second death path with its own copy of the condition
  ladder, and the three laws' ratchet caught it within the run: what shipped gives the unit
  a different *threshold* on the existing path — zero instead of −Con — so the sentence that
  writes `dead` is still written once.

One thing seen and left alone: the prose promoted a *"lead raider"*, a *"second raider"* and
a *"third raider"* as individuals alongside the unit. That is `note_cast` doing its job on
sentences that single people out of a crowd, and a leader stepping forward is legitimate
fiction. Worth watching in play rather than pre-emptively suppressing.

## Not done here, and why — the blocks, now done (2026-09-20)

**The corpus's own 22 troop-subtype blocks** (a goblin troop at 52 hp, an imperial infantry
troop at 126) still spawn as ordinary actors. Their `subtype` is stripped before the Actor is
built, which is the easy half to fix — but a published troop's hit points ARE the unit's pool
and its member count is nowhere in the data, so giving them attrition would mean inventing a
number per block. The troop *rules* without the attrition would leave a readout saying "1 of
1". Left alone rather than half-built, and recorded here so the next person does not read the
gap as an oversight.

> **Built as group 16** (`docs/published-troops.md`). The paragraph above is right that the
> count is not in the block and wrong that it is nowhere: it is in the **subtype**, as a band
> — "approximately 12 to 30 creatures" — and as a footprint, "a 20-foot-by-20-foot square".
> Twenty feet is four squares, so the stated footprint is sixteen squares, and `size_for`
> puts one person in each. Sixteen is where the published rule and this app's own ruling
> agree; a member's share is the pool over sixteen, and the count falls out of the block's
> own hit points from there. Nothing is invented per block, and the goblin troop this note
> names arrives as thirteen goblins of four hit points. There are **23** of these blocks, not
> 22.

**Swarms** (41 blocks) are a different mechanic — damage reduction against weapons, distraction,
area-only vulnerability — and are not a crowd of people. Nothing here touches them.
