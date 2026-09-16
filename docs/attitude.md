# Talking somebody round

`rules/attitude.py`, `Engine._sway` and `Engine._set_attitude` in `rules/engine.py`,
`tests/test_attitude.py`. Written 2026-09-16.

## The gap this closed

`rules/states.py` has held 1e's attitude track since the spell import, and its own comment
said what was missing:

> thirty-three spells set one, charm person among them — and it shipped `engine=False`
> with the note "no check in the app consults an attitude yet", because there was nowhere
> for the answer to live.

Three skills a player reaches for constantly — Diplomacy, Intimidate, Bluff — resolved to
a number in a sentence. `_op_check` rolled, printed the margin, paid the XP for beating a
DC, and left the merchant exactly as hostile as they had been.

The engine was also telling the model otherwise. The refusal that stops a plan from simply
declaring somebody helpful (stage 8's provenance gate) ends:

> To move somebody by ordinary means, talk to them and roll it: check skill=diplomacy,
> check skill=intimidate, check skill=bluff.

That sentence described a feature the app did not have.

## The rules, and nothing but

Every number is the Core Rulebook's. None of it is tuned, and none of it is invented.

**Diplomacy — Influence Attitude.** One minute of continuous talk. DC by where they stand
now, plus their Charisma modifier:

| Their attitude | DC |
|---|---|
| hostile | 25 + Cha |
| unfriendly | 20 + Cha |
| indifferent | 15 + Cha |
| friendly | 10 + Cha |
| helpful | 0 + Cha |

Success improves the attitude one step, plus one more step for every 5 the check beat the
DC by, **to a limit of two steps**. Failing by 4 or less moves nobody; failing by 5 or more
costs a step. A shift lasts **1d4 hours**. The same creature may not be influenced twice in
24 hours — and the limit is on *trying*, so a failed attempt spends the day as well. Without
that half the check is free, and a free check is one the player repeats until the dice
agree with them.

**Intimidate — Change Attitude.** One minute of conversation, DC 10 + the target's Hit Dice
+ their Wisdom modifier. Success makes them act friendly for **1d6 × 10 minutes**. Fear's
best hour is talk's worst one, which is the book's own reason to have both skills.

**The DC is the engine's.** A `check` naming a person with `target` and a skill that moves
the track is resolved against these tables, and a plan that also names a `dc` band is
refused. "The GM proposes and the engine disposes" is load-bearing here more than anywhere:
a model that can set the price of changing a mind can talk anybody into anything.

## Bluff is not on this track, deliberately

The book does not put it there. A lie is an opposed check against Sense Motive, which
`check` has supported through `opposed_by` all along; a feint is a combat manoeuvre against
a different DC again. Wiring Bluff to the attitude track because it appears in the same
sentence as the other two would be inventing a rule and calling it Pathfinder.
`test_bluff_is_not_wired_to_the_track_and_that_is_deliberate` asserts the omission so it
reads as a decision rather than an oversight.

## How it lands

Through the one applicator and the one vocabulary, like everything else:

- the shift is an `ActiveEffect` carrying an `attitude.*` tag, applied by
  `Engine._set_attitude` — **one step at a time**, because nobody is hostile and helpful
  at once. Two callers share that method (`condition` for a spell or a power, `check` for
  talking to them), which is CLAUDE.md's "grep for every copy of it" applied before there
  was a copy to grep for;
- remove the effect and the change of heart evaporates, which is what makes a charm
  breakable;
- the tell says how they feel and never how far they moved. "Grix warms: is well disposed
  towards you" is a thing a character notices; "attitude +1" is a number the narrator would
  start doing arithmetic with.

## What reads an attitude

- **The narrator's brief** (`gm/prompts.py`) — "X is friendly towards the player", stated
  as fact, so the prose plays the person the engine is holding. This has existed since the
  spell import and had nothing to read.
- **"Who is here"** on the table page (`play/gm_answers.py`).
- **The counter** (`play/views._counter_refusal`) — a hostile or unfriendly keeper will not
  trade with you, and the refusal names Diplomacy as the way back. 1e gates what a creature
  will do for you on their attitude ("once a creature's attitude is indifferent or better
  you can make requests"), and buying from somebody is a request. Nobody starts unfriendly:
  an attitude is only ever set by something that happened, so a counter the player has not
  poisoned opens exactly as it did before.

## Still open

- **Intimidate's aftermath.** The book has an intimidated creature treat you as unfriendly
  once the friendliness lapses, and possibly report you. Not implemented: there is no
  "when this effect ends" trigger in the engine — wards fire each round or when struck —
  and inventing a third trigger for one rule is how a mechanism ossifies around a special
  case. The friendliness runs out and they are whatever they were.
- **Requests.** The book's request table (simple advice −5, dangerous aid +10, each extra
  request +5) is not implemented. What a friendly creature will actually *do* is currently
  the narrator's judgement, informed by the attitude in the brief.
- **Aid another, and taking 10 or 20** on a social check.
- **Nothing sets a starting attitude from the world.** Every creature begins where nobody
  has said anything, which reads as indifferent. A faction the player has wronged, a
  settlement's own tensions, a scheme's villain — all of them could set one, and none does.
