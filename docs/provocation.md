# Provocation: what an insult costs, and whether they swing

*Built 2026-09-25. Code: `rules/provocation.py`, `Engine._op_provoke`,
`judgement.inject_provoke`. Tests: `tests/test_provocation.py`.*

## Why

The provoke script (`tools/narrator_audit.py --script provoke`) escalates verbally
against one man for ten turns. On the second run he was insulted nine times and never
struck. The prose held the tension correctly and waited ("He doesn't lunge, but his
knuckles turn white"), but nothing in the world moved: the planner wrote `say` and
`narrate_only`, and no attitude changed. Worse, every exchange earned the +2 regard of a
friendly word (`attitude.REGARD_PER_TALK`), so the insults made him like the player
*more*.

## The ruling

The user chose "option 1, by temper". An insult or provocation lowers the target's
attitude. The worse it gets, the likelier they strike, and how fast depends on their
rolled temper: a hot-tempered man swings after one or two insults, and a placid one may
never swing and does something else.

## What the research found (2026-09-25)

- **RimWorld** ([Social](https://rimworldwiki.com/wiki/Social),
  [Social fight](https://rimworldwiki.com/wiki/Social_fight)): an insult costs −15
  opinion and a slight −5, on −100..100. Each lasts 20 days and stacks up to 10 times,
  with each repeat worth ×0.9. An insult has a 4% chance of starting a fight. Traits and
  states multiply that chance: Bloodlust ×4 (raised from ×2 in Beta 19), drunkenness up
  to ×5, the aggression genes ×0 to ×3. The opinion loss is the same for everyone.
- **Dwarf Fortress** ([facets](https://dwarffortresswiki.org/index.php/DF2014:Personality_facet),
  [Tantrum](https://dwarffortresswiki.org/index.php/Tantrum)): ANGER_PROPENSITY runs from
  "never becomes angry" to "constant internal rage". It picks *which* breakdown stress
  produces. 0.40.17 made stress drop faster the longer no stressors apply.
- **Bethesda** ([Oblivion Aggression](https://en.uesp.net/wiki/Oblivion:Aggression),
  [Skyrim Brawl](https://en.uesp.net/wiki/Skyrim:Brawl)): an Oblivion NPC attacks when
  disposition is more than 5 below its aggression. A Skyrim brawl is fists only; a weapon
  makes it assault. Skyrim's Morality and Assistance values decide who joins in or holds
  back.
- **PF1e** ([Diplomacy](https://www.aonprd.com/Skills.aspx?ItemName=Diplomacy),
  [Intimidate](https://www.aonprd.com/Skills.aspx?ItemName=Intimidate)): attitude moves
  one step on a check. A lapsed Intimidate leaves the target unfriendly and they "may
  report you to local authorities".

Could not verify: RimWorld's exact fight formula from source, and the PF1e primary text
of what a hostile NPC does (the 3.5 SRD table was found only through search snippets).

## The design, and where each part comes from

| rule | value | source |
|---|---|---|
| an insult costs everybody the same regard | 10 (slight 4) of 100 | RimWorld −15 of 200 is 7.5%; less than one band |
| repeats in a day are worth less | ×0.9 each | RimWorld's own stacking factor |
| temper scales the **chance of striking**, not the loss | ×0 below temper 15, ×1 at 50, up to ×3.7 | RimWorld multiplies the chance; DF's "never becomes angry"; Bloodlust ×4 |
| the chance rises as attitude falls | hostile 0.35, unfriendly 0.12, indifferent 0.02 at ×1 | tuned by simulation, below |
| the roll is the response, never the insult | seeded 1d100 | nobody rolls to land an insult in any source |
| the watch looking on | ×0.25 unless temper ≥ 85 | Skyrim Morality and Assistance |
| a provoked blow is fists | `weapon: unarmed` | Skyrim brawl |
| somebody who will not swing turns their back | leaves the conversation | PF1e's "may report you"; the watch waits on the watch system |

**Tuned by simulation (40 seeded runs per temper, insults until blows or a turned back):**

| temper | swung | median insult swung on | turned their back |
|---|---|---|---|
| 5 | 0 | — | 40 |
| 30 | 5 | 3 | 35 |
| 50 | 39 | 4 | 0 |
| 70 | 40 | 3 | 0 |
| 95 | 40 | 2 | 0 |

The first cut (0.45 / 0.20 / 0.06 with a linear multiplier) had an average temper swing
on the first insult in half of twenty runs.

## Built second (2026-09-26): what they do instead, recovery, cooling

The user asked for the "not built yet" list before moving on.

- **What a hostile person who will not swing does.** Their rolled life chooses; nothing
  is rolled.
  - Sociability 65 or more: they **turn the room**. Everybody else here loses a slight's
    worth of regard for the player.
  - Order 60 or more, in a settlement: they **go to the watch**. The player gains the
    town's existing `state.suspected` through the one applicator, with source
    `rule:provocation/<ref>` (docs/wanted.md): prices up 25%, a warning at the gate.
    This is PF1e's lapsed Intimidate, where they "may report you to local authorities".
  - Anyone else only turns their back.
- **Recovery.** What provocation took is held as a *grudge* on the regard effect. It
  comes back through `Scene.advance`, the one clock door, as `(elapsed / 3 days)²` of
  the grudge. That is slow at first and faster the longer nothing new happens (Dwarf
  Fortress 0.40.17), and it is gone in three days. A fresh insult starts the curve over.
  Regard lost to a failed Diplomacy check is the book's and does not return this way.
- **After an outburst.** When a fight ends (`Scene.end_encounter`, the door all eight
  callers use), each person who swung because they were provoked has their coin tossed,
  seeded on who and when: **cathartic** (the grudge cleared, and a step warmer) or
  **embittered** (a step colder). This is RimWorld's +38 or −22. Either way they are
  **cooled** for 8 hours: an insult still costs regard, but they will not rise to it
  again yet (RimWorld's post-break reset; the Dwarf Fortress tantrum spiral is the
  failure it prevents).

Still open: the watch coming *to* the player after a report. Today a report marks the
player suspected, which the gate and the counter read; nobody walks in to make an arrest.

## Live (2026-09-25, gemma-4-12B, the provoke script)

- "I laugh in his face and tell him to do something about it" declared `provoke` on
  Borin Lyraxys, a world character with no rolled life, so temper 50. He was unfriendly
  and the chance was 0.12; the roll was 4. He swung with his fists before the prose
  ("Borin Lyraxys hits Kesst Vayr for 2 bludgeoning"), and the plan declared his later
  blows in the fight that followed.
- The first insult, "I tell the biggest man at the bar that I have seen better fighters
  in a nursery", provoked nobody. Several men were present, nobody was in conversation
  yet, and the words it was spoken at were never looked for. Fixed: they are found
  through the population's finder, without where he stands ("the biggest man" is the
  "large man").
- Writing that fix reused the name `_AIMED_AT`, which already existed 3,800 lines
  earlier, and broke four misaimed-attack repairs. `tests/test_no_silent_shadowing.py`
  now refuses a module-level name rebound without reading its old value.

One run, one seeded roll: this shows the path works end to end in real play, not that
the tuning is right. The simulation table above is the tuning's evidence.

## Live, after the targeting fixes (2026-09-26, the journey-free provoke script)

Every insult outside a fight reached the same man, the laborer: a prose person with no
rolled life, so temper 50. He escalated through the track exactly as the simulation
predicts for an average temper:

| turn | insult | engine |
|---|---|---|
| 1 | "…better fighters in a nursery" | "laborer cools: has no time for you" |
| 2 | "I laugh in his face…" | "laborer takes it badly" |
| 3 | "I call him a coward…" | "laborer cools: wants you gone, and is past talking" (hostile) |
| 4 | "I tell his friends he cried…" | "laborer has had enough", then his fists (missed) |

Turn 4 is an insult about him said to others, aimed at the man being baited. The run
before it had shown the merchant (temper 80) swing on the first insult, the fight end,
and "glares at you, but will not be drawn again so soon" on the next two insults.

Before these fixes a spy on the injector found four insult turns of six provoking
nobody. The model wrote a `say`'s listener in `target`, and only `params.to` was read;
"him" had no reading at all. The first targeting fix had also reused the name
`_AIMED_AT`, which already existed, and broke four unrelated repairs; see
tests/test_no_silent_shadowing.py.

Not yet seen live: turning the room and going to the watch. Both need somebody with a
rolled life who is hostile and too even-tempered to swing, and no script has produced
one yet. Both are covered by `tests/test_provocation.py`.
