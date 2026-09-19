# Nobody is invented

Group 8 of the fix pass after the 2026-09-19 play-test
(`docs/playtest-2026-09-18.md`, items 29, 30 and 34). Branch `nobody-is-invented`.
Tests: `tests/test_nobody_is_invented.py` (16).

Three items about one question: **who exists, and on whose word.**

## The player naming somebody is a question (item 29)

**What was wrong.** "I turn to find the mayor" produced *"The mayor stands before you, his
heavy woolen cloak still smelling of woodsmoke."* Traced: the model wrote a target
`"mayor"`, validation raised `refs`, `_INVENTED_REF` matched, and because exactly one ref
was invented the ref became the actor's *name* — a 13-hp Warrior-1 called **mayor**,
carrying a sap. Six repairs in `gm/judgement.py` can create somebody the player named and
not one of them consulted the world, though `World.by_name` and `World.residents` could
answer the whole time; their only caller was the `/gm` lookup tool. The asymmetry was the
bug: a *sale* to an absent person was dropped and the turn survived, an *attack* or a
*talk* invented them.

**Prior art: scope.** Parser interactive fiction settled this decades ago. Inform answers a
thing out of scope with "You can't see any such thing", and the tradition distinguishes the
cases — a thing that exists but is elsewhere gets a different answer from a word the game
does not know
([intfiction on I7 NPC scope](https://intfiction.org/t/i7-npc-scope-and-the-can-see-check/47889)).
Three states, three answers, and never a fourth where the parser conjures the thing to
satisfy the sentence.

**Built.** `rules/scope.py`, and the world's own answer in three forms:

- **here** — nothing to say, they are standing in front of you;
- **elsewhere** — "Gribbet Dunmoor, harbor-reeve, is in Pilfnook, not here", or, for
  somebody in this town, "Drenn Ironvale, healer, is in Vormoor but not in this room";
- **nowhere** — "There is no mayor in Vormoor. Its authority is a local reeve confirmed by
  Kragmoor Horde's central authority", built from the settlement's own `Formal Power` fact.

A vague phrase — "the man", "somebody", "a stranger" — is **not** a question the world can
answer, and scope says nothing about it: a nameless figure in a crowd is a fair thing for
prose to produce. Nor does a trade get the authority clause: "there is no blacksmith in
Vormoor, its authority is a local reeve" was the first version and reads as a non sequitur,
because a town plainly has a smith and the world simply never wrote one up.

Three things reach it. `judgement.person_sought` reads the player's own sentence, because
whose word it was is the whole test. `prompts.scene_brief(absent=…)` states the answer as
fact before the prose is written. And `judgement.answer_the_absent` puts the sentence on
the turn whether or not the plan reached for anybody — it rides on `narrate_only`'s new
code-only `not_here` param, which `_op_narrate_only` prints through `_refuse`. The narrow
exception stays: the *narration* describing people arriving is an arrival, and
`repair_unknown_refs` still creates them.

## The band that arrives (item 30)

**What was wrong**, measured rather than reported: `"a band of twelve raiders"` booked
**zero** — no ledger entry, no actor, not even a `cast_brief` mention — because `raider` was
in no form in `_CAST_ROLES`, while a Raider at CR 2, 29 hp has shipped in the bestiary all
along and `spawn` could reach it. `"a band of twelve soldiers"` was wrong three ways at
once: `_NUMBER_WORDS` had no entry for **twelve**, so the ledger booked a person called
*"twelve soldier"*; the count was clamped to the promotion cap at booking, so nothing
downstream could know the fiction said twelve; and `promote_cast` returned immediately
mid-fight, which is exactly when a band arriving matters. And the drift the player reported
— soldiers becoming raiders — was held by one sentence of prompt text and nothing else.

**Built.**

- **The words prose uses for armed strangers**, in `_CAST_ROLES`: raider, brigand, bandit,
  reaver, marauder, outlaw, looter, sellsword, cutthroat, deserter, pirate, bravo, rider —
  and `figure`, because the reported beat's own words were "a line of figures silhouetted
  against the gray morning light", which matched nothing. `line`, `column` and `row` join
  the collective words for the same reason.
- **`judgement.template_for`**, and the care in it is the point. `npcs.choose` bands by CR
  and would answer every role word, but measured at level 1 it answers "bruiser" with a
  **gnoll** bruiser at CR 3, "fighter" with a *gillman* knife-fighter, "veteran" with a
  veteran *buccaneer* and "merchant" with a Tian merchant *sailor*. Matching one word and
  dragging a species in is worse than the floor. So the corpus's pick stands only when the
  block IS the role word — raider, brigand, bandit, guard, watchman — and everything else
  keeps the hand-written floor. Five copies of the old cue loop existed; they all come
  through this one function now.
- **Every number word prose writes**, up to fifty, in `_NUMBER_WORDS` and in
  `bestiary.split_collective_name`, where a stated number now beats the collective's
  default: "a band of twelve raiders" is twelve raiders and not four.
- **The ledger records what the prose said.** The cap moved to promotion, where bodies are
  made. Twelve is on the books, four are on the board, and `cast_brief` says "raider ×12"
  so the model is no longer told four. Item 33's unit is what resolves the tension.
- **A band arriving mid-fight arrives.** The old early return is gone and the bookkeeping
  rule is kept rather than broken: they walk on as bystanders, outside the initiative, and
  the two doors that already exist take them into the fight — `joiners` when the beat says
  they draw, `attacked_by` when it says they strike. Nobody is quietly inserted into the
  order.
- **`judgement.hold_the_booked_word`.** One armed group booked, a different armed word in
  the beat, and that word booked nowhere: it is repaired to the booked word. Narrow on
  purpose — two bands booked means two bands, and a character may call them whatever they
  like inside quotes.

## Dialogue puts nobody in the room (item 34)

Found during group 7's own live check: the beat said, of the woman being asked her name,
*"Most just call me the stranger"*, and a new actor called **stranger** was booked and
promoted out of her own words about herself. `note_cast` read the whole beat, speech
included.

`narration_quotes_blanked` is the fix, and it is the same idea as `redact_speech` for the
player's input: the narrator's own sentences put people in the room, and dialogue does not
— a person talked about is not a person present, and even a genuine announcement ("'Three
raiders are coming!' he shouts") is a warning about people who have not arrived. The blanked
span keeps its length, so every offset downstream still lines up: `note_cast` reads spans
out of the beat and asks `zone_of_mention` about them, and a shortened string would point
those at the wrong words.

## Measured live, three runs on a copy of the `masta` save

| Run | Result |
|---|---|
| 1 | "I turn to the mayor of the town and ask him what reward he plans to give" — **no mayor, nobody created**. The beat answered from inside the room: the woman in the corner spoke instead. The repair path was never reached, because with the fact in the brief the model did not reach for a mayor ref at all. |
| 2 | "I find the mayor and grab him by the collar" — again no mayor, and again nothing said. A plain `narrate_only` and a paragraph about the room: the *reported* half was fixed and the *asked* half was not. `answer_the_absent` was written for exactly this — the answer is stated whether or not the plan reached for anybody. |
| 3 | **The ruling, working.** "You push through the throng toward the central kiosk where the Reeve's official seal is displayed… He is the one who holds the title of Reeve, the only voice of law in Vormoor's reach." The world's own fact reached the prose and the prose wrote the reeve. |

Run 3 also found two defects that are **not** this group's, recorded as items 35 and 36:
a plan carrying **five `travel` ops** walked the party across town in one turn (the party
ended on the green while the prose described the market), and the ledger booked one man
twice as *merchant* and *shouting merchant*. It did find one that is: the ledger held a
person called **"man in a heavy"**, truncated from "a man in a heavy, grease-stained leather
apron" where a comma stood in the pattern's way. A description that ends on an adjective is
not a description, so the tail is dropped and the man is a man.
