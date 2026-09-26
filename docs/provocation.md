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

## Not built yet

- **Calling the watch** or turning the room against the player. Needs the watch system.
- **Decay.** Regard lost to insults does not recover by itself. DF's lesson is to let
  it fall off faster when nothing new happens.
- **A cooldown after an outburst**, following RimWorld's post-break reset.
- **Insults in the middle of a fight** cost regard but roll nothing, since the blows are
  already the dice's.
