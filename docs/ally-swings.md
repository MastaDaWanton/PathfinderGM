# An ally's swing, told as a swing at you

*Design record, 2026-10-27. The code is `rules/engine.py` (`Outcome.blows`: every blow's
`ref`), `gm/planned.py` (`blow_facts`, `blows_aimed`, `aimed_line`), `gm/prompts.py`
(`call_two_messages`, `consequence_example`, `CONSEQUENCE_NPC_ASIDE_EXAMPLE`,
`ACTOR_REPAIR_BRIEFING`), `gm/agent.py` (`narrate_outcome`), `gm/beat_verify.py`
(`Facts.aimed`, `_aimed_of`, `aimed_messages`, `aimed_mismatch`, `_aimed_wrong`,
`_aimed_whom`) and `gm/checks/beat_verified.py` (`beat-aimed-wrong`). The tests are
`tests/test_ally_swings.py`.*

## The report

The owner, 2026-10-27: "fix the ally swings narrated at me". The real-jobs lane's road fights
on 0.2.22's code: the caravan's four hired hands carry `bond.travels-with-you` for the job
and join the player's side (`Engine._companions_join`). Their tells were right — "the hired
sword's attack with the halberd misses Toll-Keeper" — and the NPC-turn beats were not:

> The Toll-Keeper feels the rush of air as the hired sword lunges forward, the halberd's
> heavy head whistling toward your chest. You twist your body just enough to turn the
> strike aside…

Read back from the two saves (17 NPC-turn beats with a blow, hand-paired with their
turn-log rows): in the toll-keeper fight **4 of 5 allied misses** reached the page aimed at
the player (and two more such sentences were cut by an unrelated check before shipping);
in the riding-dog fight 0 of 4. **No allied hit** was turned round, and no foe's swing at
the player.

## Why

Three places assumed every creature acting on its own turn is hostile:

1. **A miss named nobody.** `Outcome.blows` carried the target (`ref`) on a hit only, so
   `planned.blow_facts` handed the call "MISS — weapon: halberd; it is evaded". A hit's line
   named the one struck ("Toll-Keeper after it: hurt but steady"), which is why no hit was
   turned round.
2. **The call's one demonstration was the victim's.** `CONSEQUENCE_NPC_EXAMPLE` has the
   ferryman swinging and "you duck under it". The opening said only "the player's
   character is 'you'"; nothing said the blow went anywhere else.
3. **The wrong-actor repair said the player is "the one it is done to".**

## How it was already solved

DikuMUD's descendants write every combat message three times — to the attacker, to the
victim and to the room — and send each reader the one for its part in it (tbaMUD
`src/fight.c`, `dam_message` and `skill_message`: `act(…, TO_CHAR)`, `act(…, TO_VICT)`,
`act(…, TO_NOTVICT)`; the miss message is "$n tries to #w $N, but misses", naming both).
Inform's adaptive text is the same idea for one report: "you" for the player, by name for
anyone else. The call here had only the TO_VICT message.

## The fix

- **The engine records the target of every blow**, hit or miss.
- **Every blow fact opens on who swung at whom**: "MISS — the hired sword at Toll-Keeper —
  weapon: halberd; …", the player as "you".
- **The call says whom the blows were aimed at**, and when none was aimed at the player,
  says so in one plain line, and shows the room's message — `CONSEQUENCE_NPC_ASIDE_EXAMPLE`,
  a deckhand's oar at the ferryman with no "you" in it — picked in code
  (`consequence_example`). Both narrators: the Free call is the same call.
- **The wrong-actor repair** follows the tells for whom the act is done to.
- **The read-back.** On a creature's turn in a fight, a call of its own asks, per sentence
  showing a blow, WHO strikes and at WHOM (people codes, the player as `pc`, "not shown"
  for either). Code compares with the engine's (attacker, target) pairs
  (`aimed_mismatch`): a blow shown at the player when no blow went at the player, or from
  somebody who struck this turn at somebody they did not strike, is `beat-aimed-wrong`. A
  second read of the one sentence, with the passage before it and without the tells,
  decides. Cut-only: the engine's line ("The hired sword's attack with the halberd misses
  Toll-Keeper.") takes the first wrong sentence's place, any other is cut.

Refused: the one-sentence rewrite. On the five wrong sentences of the toll-keeper fight,
three rewrites each, 6 of 15 were right; 9 put the blow on another wrong person or landed
a miss ("the blade strikes the hired sword"), and the re-read of the rewritten sentence
alone passed 6 of those 9 — alone, "the blade" is nobody's, and a blow at somebody other
than the player whose striker is not shown is not judged. The same hole the joined-turn
and struck-at-early lanes measured.

## Measured

gemma-4-12B (`igorls/gemma-4-12B-it-heretic-GGUF`), the recorded consequence calls of both
road fights rebuilt from the turn log and sampled four times each at 0.7 (17 recorded
turns with a blow, plus three synthetic foe-at-ally turns made from the toll-keeper's and
the dog's own recorded swings). "Before" is master d2f0bf7d; labels read by hand.

| | before | after |
|---|---|---|
| toll-keeper fight, allied misses aimed elsewhere | 16 / 20 | 0 / 20 |
| riding-dog fight, allied misses aimed elsewhere | 0 / 16 | 0 / 16 |
| allied hits aimed elsewhere | 0 / 20 | 0 / 20 |
| foe at the player, told at somebody else | 0 / 12 | 0 / 12 |
| foe miss at an ally (synthetic), told at the player | 8 / 8 | 2 / 8 |
| foe hit at an ally (synthetic), told at the player | 0 / 4 | 0 / 4 |

The two "after" misses kept the creature's own recorded reason, "it is desperate and
trying to push you back" — the synthetic case changed the target and not the reason the
planner gave, and a real planner aiming at the ally would not usually write it. The
read-back caught both.

The read-back (first read + second read, temperature 0):

| beats | wrong | caught | sound | false alarms |
|---|---|---|---|---|
| shipped beats of both fights | 4 | 4 (every wrong sentence) | 13 | 0 |
| "before" generations | 24 | 24 | 56 | 0 |
| "after" generations | 2 | 2 | 78 | 0 |

The first version of the read had no "not shown" for a target and guessed one for "The
hired sword lunges forward, swinging the heavy flail in a wide, desperate arc": 3 false
alarms in 56 sound "before" generations and 1 in 78 "after"; with it, none.

`tests/replay` was not used: its 2026-09-25 fight recordings have no allied fighters, no
`Outcome.blows` and no stamped actors, and most of their creature attacks carry no tell.

## Left

- The state-claim check (`gm/state_claims.py`, section 3) cuts true sentences about
  stat-block creatures swinging their printed weapons ("puts a club in a hand that holds
  nothing — nobody facing you here is armed"): 6 of the 17 recorded turns lost one. It
  also stripped the sentence that named the attacker, leaving "the wood whistles … missing
  your form" alone. Logged as its own task.
- A blow from somebody the engine let strike nobody this turn is not judged here (an
  unrolled blow on a creature's turn); `at_you` asks it only on the player's beat.
