# Road ghost: a creature met on the way that "could not be attacked" (fix/road-ghost)

Bench 2026-11-21, job road-jason#1 (travel-bench/after.jsonl, Aurvantis): the road to
Caelholt was stopped by a poltergeist (c17). The next line, "I keep walking toward
Caelholt", came back twice as "The engine refused the GM's intents: attack: 'c17' is not on
the board at resolution time".

## What actually happened (reproduced, tests/test_road_ghost.py)

The plan was `[move, attack c17]`, with the player's declared `journey` merged in ahead of
it (`agent._merge_declared`). The journey resolved and walked on past the poltergeist to the
far town; the poltergeist stayed where it was met and left the scene; the attack then hit
the defensive floor in `_op_attack` and raised `IntentError`. A resolution-time raise refuses
the whole turn, so the player's own walk was lost with the model's invented blow.

Candidates in the brief, checked:
- *Met creature never given a square*: no. `_meet_on_the_way` is the one door for every
  on-the-way meeting (journey, travel/venture hops, hex road checks, sea and sea-hex
  meetings, night camps: all 11 call sites grepped) and places by zone onto the laid grid;
  the forced poltergeist stood at a square on all three fixture worlds (asserted).
- *Board rebuilt and drops it*: only in the sense that the walk on lays new ground at the
  far town and leaves it behind, which is correct.
- *Incorporeal/hidden state takes it off the board*: no; an attack before walking on is a
  real blow (second test).
- *Ref renamed*: no; c17 was the same ref at validate and resolution.

## Sources

- PF1e Poltergeist, Bestiary (d20pfsrd.com/bestiary/monster-listings/undead/poltergeist):
  CR 2, incorporeal, natural invisibility; **site bound**, it "cannot travel more than 120
  feet from the point at which it was created". So a party that walks on leaves it behind by
  the book; it cannot follow down the road.
- PF1e Incorporeal universal monster rule (d20pfsrd.com/bestiary/rules-for-monsters/
  universal-monster-rules): immune to nonmagical attacks, half damage from corporeal magic
  sources, force works normally; it can pass through objects. The rule does not say whether a
  corporeal creature can pass through an incorporeal one's square (could not be sourced either
  way), so this fix does not rule on it: walking on past a creature that is not hostile was
  already allowed, and stays so.
- Inform 7 (ganelson.github.io/inform-website/book/WI_18_29.html and the scope chapter): a
  thing "left behind in the next room" is out of scope and the parser answers "You can't see
  any such thing". Out-of-scope is a printed refusal, never an error, which is this project's
  `_refuse` door already (stage 7).
- Roguelike/MUD practice (NetHack's monsters stay on the level you left; Diku rooms hold
  their mobs): I could not find a primary doc that discusses an action queued *after* leaving,
  so I claim nothing from them beyond "what you left stays where it was".

## Chosen

In `Engine._drive`, the one loop every intent passes: when an op moves the party
(`scene.at` changes), whoever was in the scene before it and is not after is remembered for
the rest of the list; a later intent by or on one of them is a printed refusal
(`_left_behind`, "Poltergeist is not here any more: the way on left them behind, so the
attack does not happen"). The walk keeps its result.

## Rejected

- Validate-time refusal of [walk, act-on-someone-left]: validate would need to project who
  each walk leaves behind (escorts, mounts, company, ships), a second copy of the walk's
  own rule. The model's retry would also re-plan the player's walk, which was never wrong.
- Barring the journey while a creature stands "in the way": a non-hostile creature on a road
  can be walked round; a hostile one already opens a fight, and `_held_by_stopped_walk` holds
  later walks then. Changing that is journey pacing, the travel-pacing lane's ground.
- Dropping the attack silently: a plan op disappearing with no tell breaks severed tells; the
  refusal is a tell the narrator dresses.

Second pass: re-read both d20pfsrd pages after writing; the "site bound 120 ft" quote and the
incorporeal points match. The "pass through a creature" question is marked unsourced above.

Limit: a walk that suspends for the player's die and resumes in a new `_drive` starts with an
empty memory, so an act behind it on somebody it left would still meet the old floor. No
model-planned list can hold `hex_move`/`hex_enter` (code-only ops), and `journey`/`travel`
roll their own dice hidden, so I found no live path that reaches it.
