# What a hand holds and a body suffers is the state's

*Design record, 2026-09-28. The code is `gm/state_claims.py` (`state_claims`) and
`gm/agent.py` (`_repair_state_claims`, `_changes_from`, the `changes` input to `_groom`).
The tests are `tests/test_state_claims.py`; the corpus count is "state claims flagged" in
`tests/replay/baseline.json`. It follows `docs/maneuver-outcomes.md`, whose live runs
found the defect.*

## The report

A scripted fight through the real `/api/say` loop (gemma-4-12B, the fixture world, a
tavern brawl with Borin Lyraxys, 2026-09-27). The engine's state matched every
manoeuvre's tell. The prose of `narrate_turn` — the door the player reads, written after
the dice — did not, on five sentences:

| tell | prose | state |
|---|---|---|
| Kesst Vayr drops the rapier (the player's failed disarm) | "The rapier clatters against the floorboards, sliding a few feet away as his grip fails." | the PLAYER's hand is empty |
| bull rush: driven against something solid and goes nowhere | "He's left sprawling … and leaving him momentarily stunned." | no prone, no stunned |
| Kesst Vayr's steal fails … by 16 | "sends the purse tumbling from his hip; it hits the floor" | 9 sp still in his purse |
| an unarmed strike | "Your blade whistles through the air" | nothing in the hand; the rapier on the props ledger |
| the overrun fails | "Your rapier slips from your grip as you collide" | it had been on the floor two turns |

None was caught. `rules.intents.find_outcome_claims` reads mechanics off the words and
asks whether the outcomes back that KIND of claim; nothing asked the state WHO holds WHAT,
or whether a body carries the condition it is said to.

## Prior art

- **Rules against a record are precise and incomplete.** Dušek & Kasner (2020): a
  hand-written slot matcher was right on 99.5% of system outputs against NLI's 97.8%, but
  blind to anything it had no pattern for. Dušek et al. (2019): the same matcher 99.5%
  on neural output, 80.5% on human text — a small model's formulaic prose favours rules.
- **Who-did-what is the hard part.** Thomson & Reiter (2020) found RotoWire's
  relation-extraction metric could not see "word" errors at all — the verb and outcome
  words — and the INLG 2021 shared task's pure rule system found them at 0.35 recall /
  0.30 precision in open sports prose. A closed vocabulary (these weapons, these
  conditions, this ledger) is a smaller problem; the literature says to earn recall
  claim type by claim type, measured on recorded sessions — which is what the corpus is.
- **Repair the span, re-check the repair.** RARR edits only what disagrees and kept the
  passage's intent in over 90% of cases where whole-passage revisers kept it in 6-40%.
  Varshney et al. (2023) detected 88% and their repair fixed 57.6% of that, so a repair
  must be checked again and fall back to a cut. Kamoi et al. (2024): prompted
  self-correction does not work without reliable external feedback; the detector is it.
- **FIREBALL** (Zhu et al. 2023): D&D narration models given the state still narrated a
  39/39-HP dog dying — reporting bias toward the dramatic outcome. Our stun and disarm
  lines look like the same prior (an inference, not their finding).
- **Inform 7**: "Report rules must neither block the action nor do anything." The
  narrator is a report rule; this makes it one in code.

## What it does

Three questions, by set comparison against the facts, on prose already in the second
person:

1. **A thing leaving a hand** — a weapon, a shield, a purse, or anything carried here
   by name, as the subject of a leaving verb with a way out of the hand or a floor to land
   on ("tumbling from his hip", "clatters to the floor"), or the object of one ("drops his
   sword", "knocks the blade from his hand"). Backed only by this turn's `dropped`,
   `stolen` or destroyed-item effects — and by the RIGHT hand: a drop given to the enemy's
   grip when the player's was the one that failed is flagged as wrong hands.
2. **A body suffering a condition** — stunned, dazed, prone (sprawling, knocked flat),
   blinded, unconscious, in their physical sense, on the nearest person the sentence
   names. Backed by `has_state` on the condition's tag, a condition effect this turn, or
   the body being down.
3. **A weapon in a hand** — "your blade" when the player's hand is empty, "your rapier"
   when the rapier is not the weapon held; a creature's weapon when nobody here, standing
   or fallen, holds one.

Each finding carries its fact ("your hands are empty — your rapier is lying on the
floor"), and `_repair_state_claims` rewrites that one sentence through the existing
sentence-repair call, checks the rewrite with the same detector, and cuts the sentence if
it still says it. Two calls a beat at most. It runs in `_groom` after the rewrite and the
name swap, so the prose it judges is the prose that ships. `changes` is passed by the two
post-dice doors; setup prose and an NPC's opener pass none, so every drop or stun they
write is their own.

## Measured before trusting it

- The five live sentences: 5 of 5 flagged, each with the right fact.
- The recorded corpus, 142 real drafts, each against its own pre-turn scene and its own
  turn's effects: the first draft fired **4 times, all wrong** — a smith's quoted "when
  the hammer falls", "a stunned, heavy silence", "the city's bustling sprawl", "the
  sprawling, frantic hub". Each narrowed out: what anybody says is blanked; a leaving
  verb needs a way out of the hand or a floor ("the hammer falls" is a blow); sprawl needs
  a preposition; the silence/look exclusions see past two adjectives. Now **0 of 142**,
  pinned in the replay baseline as "state claims flagged".
- The corpus has no drops or stuns in it, so it measures precision only. Recall beyond
  the five is unmeasured.
- **Live, with the repair in** (2026-09-28, the same scripted fight, nine lines, the
  four manoeuvre lines of the report among them): it fired on one turn of nine, twice,
  and both were true. A disarm by 5 against Borin — tell "holds nothing that can be
  knocked loose" — drafted "the weapon he held is tossed aside, clattering onto the
  floor" (the rewrite still said it, so the sentence was cut) and "He is momentarily
  stunned by the loss of his reach" (rewritten to "momentarily conscious of the loss of
  his reach": the stun is gone, the English is clumsy). Nothing true was touched; "the
  heavy mug slips from his grasp, clattering against the table" was let be — a mug is
  nobody's record. The dice gave no successful drop, steal or push this run, so the
  wrong-hands branch has not yet fired live; the five measured sentences are its test.
  The finding's own English said "they is not" with two creatures in the room; fixed.

## Refused

- **A prompt instruction** ("do not narrate drops that did not happen"). The project's
  first law, and FIREBALL's result: the state in the prompt did not stop it.
- **An NLI or LLM judge.** The closed vocabulary is where rules are strongest, and a
  second model call per beat on a local model is a minute of the player's time.
- **A corpse's weapon.** The engine keeps a dead man's sap `equipped`; "his club clatters
  to the floor as he falls" is let be.
