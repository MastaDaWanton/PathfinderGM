# The structured turn: models read, code validates

The owner, 2026-10-03, after a day of fixes that each exposed the next: *"we cant really
depend i think on just layering mechanical detection logic on top this will be an endless
loop"*. Then: *"build it all the way through"*.

## What was measured

- **The regex detectors read the player's sentence far worse than the reader.** On the
  first 60 of 220 labelled sentences (`tools/interpreter_bench.py`), the detectors scored
  act F1 **0.52**. The reader (`gm/interpret.py`, gemma-4-12B heretic, schema-enforced)
  scored **0.94**, at a median of **2.3 s**. The detectors still get the last word on
  many turns. Every live bug of 2026-10-03 on the forward side is a regex misreading a
  sentence the reader had read correctly:
  - "…, then tip the coins" (the reading had `take: the coins`);
  - a quoted "It's a deal" (the reading had `sell: the crate → the smith`);
  - "pick the crate back up".
- **deepseek-r1:8b is not the reader.** It scored F1 0.02: it ran out of its 400-token
  reply on most sentences, reasoning even with `think=False`. DeepSeek's own R1 paper
  lists JSON output as a limitation.
- **The reader's own misses are systematic, not random.** It got 19 of 60 frames not
  exactly right:
  - about 8 are strict scoring or a debatable label;
  - 3 are duplicate acts;
  - about 8 are real errors: an "ask where/what X" question lost from `says`, "head for
    <a place>" read as `seek`, and a house's place slot dropped.
- **The backward side harvests facts by parsing prose.** Ten `play/aftermath` steps and
  33 `gm/checks` modules read the narration with regex to make people, places, speakers,
  names and pronouns, and to police claims. 2026-10-03 added "He is a large man", "the
  Forge of the Broken Tide" and "a grumpy man", and each new phrasing needed new code.

## The principle

**A model reads; code validates against what the engine owns; the engine changes
state.** Code may check structure and closed vocabularies:
- refs, place ids and kinds;
- items in the pack;
- the clock;
- numbers;
- whether a slot's words are the player's own.

Code does not interpret English. Where code reads English today, the reading moves to a
schema-constrained model call. Ollama enforces enums and required properties; it did
6 of 6 in memory `ollama-schema-enforcement`. Code then validates the answer.

This narrows CLAUDE.md's "detect mechanically, repair with a targeted call". That rule
came from World Bible's prose-QUALITY defects (formulaic endings, echo), where code
counting a pattern is exact. It was never a licence for code to decide what a sentence
means.

## Prior art

- **FIREBALL** (Zhu et al., ACL 2023): 25k D&D sessions pairing utterances with Avrae
  commands and game state. LLMs can generate executable commands from utterances, which
  is our forward direction.
- **Function calling for AI game masters** (Wordplay 2024, arXiv 2409.06949): the GM
  acts through game-specific function calls, for consistency with rules and state.
- **Plan–Diff–Validate–Apply** ("Orchestrated Reality", arXiv 2606.16014): the model
  proposes structured deltas; each passes schema, permission and rule checks before it
  commits; prose is a projection, never the source of truth. It does not say how new
  entities are admitted, so that part is ours (below).
- **Wang et al. 2024**, "Can Language Models Serve as Text-Based World Simulators?":
  GPT-4 "is still an unreliable world simulator". The engine keeps state. I could not
  extract the per-category numbers from the PDF.
- **PAYADOR** (arXiv 2504.07304): a structured world representation updated each input,
  with the prompt rendered from what the player can see.

## Forward: the player's sentence (lane F)

1. **The reader drives the ops.** A fixed table maps each act and its slots to engine
   ops (`interpret._OP_NEEDS` is the start of it). The table resolves the slots to engine
   things through the engine's own finders:
   - `take` → `give` from the holder of the `object`;
   - `sell` → `sell` of the `object` to the `target`;
   - `drop` → `give` to the floor;
   - `go` → `travel`, or `found` + `travel` for a heard-of place;
   - `talk` → `say`;
   - and the rest of the vocabulary.
2. **The planner proposes; the reading confirms or adds.** A plan op the reading cannot
   stand behind is overruled, as now. A declared act the plan left out is added from the
   table. Nothing is added from a regex over the sentence.
3. **The regex readers of the player's sentence are retired** wherever the reading covers
   their act. They are listed in the lane's report: `inject_goods`, `inject_sale`'s
   sentence reading, `declare_drop`, `declare_emptying`, `as_declarations`,
   `_CLOSES_SALE`, and the rest found. Mechanical guards on STRUCTURE stay: a question is
   no act, slots must be the player's own words, refs must exist.
4. **The reader gets better first, because it now carries the turn.**
   - Demonstrations for the measured systematic errors.
   - A schema that offers each act only its own slots, if Ollama enforces it (probe first).
   - Duplicate acts merged in code.
   - The bench scored two ways: strict, and on the slots the engine acts on.
   - The gate is measured on the 160 labelled sentences the fixes were NOT written from.
5. **Reader acts the table needs and the vocabulary lacks** are added: `drop`, and
   `agree`/`close` for a deal, if measured to be needed.

### Built (lane F, 2026-10-03, branch structured/reader-drives)

**The reader** (`gm/interpret.py`):
- Two new acts. `drop` exists because "I also drop the Brunt of the weight on the ground"
  was read as a `give` to the smith. `offer` exists because "I try to sell the crate to
  Korvu" and "I agree to sell the crate" were both read `sell`. A close is `sell`, so no
  `agree` act was needed.
- Eleven new demonstrations, each written from a measured systematic miss on the first
  60 labelled lines and none taken from the labelled set:
  - "head for <a place>" is `go`, and "head for <a person>" is `seek`;
  - "ask where/what X" keeps all of X in `says`;
  - where somebody lives is a `place`;
  - a gesture is no hand-over;
  - coin is taken out of a container;
  - a thing is set down;
  - "it" refers back to a thing already named;
  - a sale offered against a sale closed in quoted words.
- A per-act schema: an `anyOf` with one object per act, the act a `const` right after the
  span, and only that act's slots.
  - Probed first: Ollama enforced it on 6 of 6 real lines, in both field orders.
  - With the act last, the slot keys chose the act ("I look around" came back `claim`).
  - It was chosen on the dev lines over the flat schema with the same demonstrations:
    engine-relevant 0.833 against 0.767, median 1.4 s against 2.4 s.
- Repeated acts merged in code (`merge_repeats`) when their slots agree.
- A null written as a word ("none") is dropped.

**The bench** scores two ways (`tests/interpreter/score.py`). Strict is as before.
Engine-relevant scores the acts and only the slots some code reads (`ENGINE_SLOTS`). The
first 60 lines are the dev set the fixes were written from. The other 160 are held out:
their misses are never printed or saved (`tools/interpreter_bench.py --held-out-only`).

| gemma-4-12B heretic, 220 lines | strict | engine-relevant | acts in order | act F1 | median |
|---|---|---|---|---|---|
| before, all 220 | 0.582 | 0.750 | 0.868 | 0.920 | 2.2 s |
| after, all 220 | 0.673 | 0.786 | 0.841 | 0.893 | 1.3 s |
| before, held-out 160 | 0.537 | 0.725 | 0.863 | 0.910 | |
| **after, held-out 160** | **0.662** | **0.762** | 0.819 | 0.872 | |
| after with the flat schema, held-out 160 | 0.506 | 0.719 | 0.831 | 0.877 | |
| before, dev 60 | 0.700 | 0.817 | 0.883 | 0.940 | |
| after, dev 60 | 0.700 | 0.850 | 0.900 | 0.940 | |

The gate was about 0.90 engine-relevant on the held-out lines. The reader reached
**0.762**, so the gate is not met.

- Strict whole frames rose by 12.5 points on the held-out lines.
- Acts in order fell by 4.4 points, and the flat schema with the same demonstrations
  fell too (0.831). So the loss comes with the new acts and demonstrations, not the
  schema.
- Lane N shared Ollama during these runs, so the p90 and max timings are contended.
- Reader failures: 0 of 220 in each full run, and 0 of 28 turn rows across both owner
  saves.

**The act→op table** (`gm/acts_to_ops.py`). It reads no English. Slots resolve through
the engine's own finders:
- people through `scope.in_the_room`, and a pronoun against the pronouns the engine
  holds for each person, else the one the player is engaged with or talking to;
- things through `holding.key_in` and the stock shelf, containers through
  `holding.is_container`, coin through `coin_named` with an amount;
- heard-of places through `heard_places.named_in` on the reading's place slot.

What each act becomes:
- **Built whole:**
  - `take`: a `give` to the player, from the holder: a container, a person, or the
    engine's own search of the ground and hands;
  - `drop`: a `give` from the player to the floor;
  - `give`: a `give` to the person, coin by amount;
  - `sell`: a `sell` to the person, with the player's own "75%" as `accept`;
  - `offer`: a `sell` only to somebody who keeps a counter; otherwise a haggle.
- **Op names joined to the plan's `declared` block:** go, leave, journey, call_on,
  break_in, rest, wait with a time, insult, talk with words said, and cast. These use
  `interpret.ops_for` one action at a time.
- **Remaining declarers:** their ops (spell names, the satchel, checks) still stand only
  where an act of the reading stands behind them (`interpret.supported`).

`apply` changes the plan in three ways:
- It replaces any plan op that moves the same thing as a built op.
- It overrules plan ops that no act stands behind. This includes coin paid out under no
  paying act, and a plan op on a thing the reading named that the table found nothing to
  move.
- `order` puts the ops in the words' order.

When every declared deed moves a thing and none can be moved, the turn is a refusal that
says what was not found ("Kesst Vayr is not carrying the lantern"), and no model is
called. Otherwise, what was not found goes into the brief as a fact.

**No reading** (a failed call; in the test suite, none handed in through
`interpret.remember`): the plan stands alone. Only an attached chip declares anything.
No retired regex runs behind it. Rasa's CALM answers failed command generation with a
"cannot handle" pattern, not a second parser.

**Retired**, each replaced by the table's row for its act:

| Retired | Read | Replaced by |
|---|---|---|
| `inject_goods` (`_HANDS_OVER`) | taking and handing over | the `take`/`give` rows |
| `inject_sale`, `_sell_goods_declared`, `_SELLS`, `_SELLS_GOODS`, `_OFFERS_SALE`, `_CLOSES_SALE`, `_JUST_HAGGLING`, `_named_here` | sales, offers, a spoken close | the `sell`/`offer` rows; a buyer through `addressed`; a jar's id through `resolve_sold_items` |
| `declare_drop` (`_DROPS`) | setting down | the `drop` row |
| `declare_emptying` (`_EMPTIES`, `_EMPTIES_BOX`) | coin out of a pouch | the `take` row with a container target |
| `as_declarations` (`_THEN_CLAUSE`, `_PICK_X_UP`) | a second deed with no "I" | one reading action per deed |
| `inject_payment`'s `_PAYS` | "I pay her ten gold" | the `give` row, `coin_amount`; the model's own coin op is still straightened |
| `go_to_heard_place`'s `_GOES_TO` | going verbs | the reading's go, journey, seek or call_on place slot |
| the four goods declarers in `declared_ops` | must-contain give/sell | built ops are never asked of the model |

`_ACQUIRES` stays for `inject_improvised` (a thing thrown), which is not yet the
reading's. Every test that pinned a retired reader now hands the table the reading the
live reader gave the sentence, and keeps its measurement docstring
(`tests/test_acts_to_ops.py` and nine moved files).

**Replayed** (the owner's items save, 22 turns, plus the 2026-10-03 lines; live readings
from this reader; the same reading fed to both paths; the regex path is the tree at
333b5f5):
- Better:
  - the last line no longer refuses a brunt into the prose;
  - "pick the crate back up, then tip the coins" runs in the words' order (it was coins
    first);
  - "I take the brunt of the weight" mints nothing.
- Worse, from the reader:
  - "I take the crate to the man … who will buy it from me" was read
    `take` + `sell: it → the man`, and the crate was sold a turn early. The later "I
    agree to sell…" then refused, because the crate was already gone.
  - "I try to sell the crate to the smith for coin" was read `sell` (the Korvu line was
    read `offer`), so it sold.
- The same on both paths: the drop, the agreed sale and the quoted close.

**Not done:**
- Live turns in the running app.
- `inject_say`, `inject_provoke`, `inject_wait`, `inject_call_on`, `inject_break_in`,
  `inject_travel`, `inject_introduce`, `inject_survival`, `inject_cast` and the rest
  still build their op's params from the sentence. The reading names their ops, and
  their sentence reading is the next retirement.
- Future intent read as a deed ("who will buy it from me") wants a demonstration, and
  then a held-out measurement of its own. Done in round 2, below.

### Round 2: commitment (lane F, 2026-10-03)

The coordinator would not merge round 1. In two of its replay regressions the engine acted
on something the player had not committed to:
- "I take the crate to the man … who will buy it from me" was read as a sale, and the
  crate was sold a turn early;
- "I try to sell the crate to the smith" was read `sell` and sold.

**Prior art.** Event annotation marks every event with its *realis*. Rich ERE has three
values: "Actual (asserted), Generic (generic, habitual), and Other (future,
hypothetical, negated, uncertain, etc.)" (Song et al. 2015, "From Light to Rich ERE", ACL
W15-0812). The TAC KBP event-nugget task scored the same three. FactBank grades the same
axis more finely, as certain, probable or possible (Saurí & Pustejovsky 2009). ISO 24617-2
keeps an Offer apart from the Accept Offer that answers it: the acceptance "has a
functional dependence relation to the preceding Offer" (Bunt's annotation guidelines).

**Built:**
- **Commitment is a required enum on every action** (`interpret.COMMITS`). It sits
  between the span and the act in the per-act schema, the same in every alternative, so
  it chooses no act. The values:
  - `done`: performed now;
  - `tried`: attempted now, and 1e rolls the outcome;
  - `intended`: a purpose clause, "I'm going to…", "I want to…", a conditional;
  - `asked`: asked about, not done.
- **Only `done` and `tried` move the engine.** This applies to `ops_for`, `supported`,
  `gets_nothing`/`hands_nothing`, the table, `apply`, `go_to_heard_place`, the words of
  `own_words_only` and the false-claim reader. The brief shows the planner the other two
  as context ("INTENDED, not done this turn: no op for it").
- **A sale tried is an offer, never a sale, at a counter too.** Only an agreement closes
  it, and a plan's sale stands only behind a sale done. Round 1's counter exception (a
  keeper buys whatever is offered) was dropped: the counting house's clerk keeps a
  counter, and the replay sold him the crate on "…who will buy it from me".
- **The `offer` act is withdrawn.** It moved the problem rather than solving it: the live
  reader read one "try to sell" as `offer` and the next as `sell`, and on the held-out
  lines it read a `talk` as `offer`.
- **A sale about to be built is asked again, alone** (`interpret.confirm_sale`). The
  question is one enum, with eight demonstrations, asked of the sale's own span, and
  takes about 0.4 s. Anything but "closed" holds the sale back, and so does a failed
  call. This is CLAUDE.md's "detect mechanically, repair with a targeted call": the frozen
  reader still read both regression lines as sales done.
  - Measured on every labelled line with a sale: the reader's own commitment was right
    on 8 of 9 held-out lines.
  - After the second question, wrongly built sales went from 1 to 0, and both replay
    lines were held back.
  - Cost: one held-out sale the player had agreed was held back as an offer. That is the
    safe direction, since the player can repeat it.
- **A walk carries what it names** (`object` on `go`/`seek`): "I take the crate to the
  man…" picks the crate up first, then walks. Read as a bare walk, the crate never came,
  and the replay had nothing left to sell four turns later.
- **`merge_repeats` narrowed.** It no longer merges when the second action is bare
  (`consume` + bare `consume` is "eat … and drink", two deeds), and it requires the
  commitments to agree.
- **Segmentation demonstrations:** a time ends the deed, a weapon is what the deed is
  done with, and where the player leans or stands is where they do it.
- **The gold set.** Every action carries a commitment. The 70 dev lines and the four
  held-out labels it changed are listed in `tests/interpreter/gold.py`. One held-out
  `give` became `drop`, the act the vocabulary gained for it. New lines:
  - 14 dev lines on segmentation;
  - 28 held-out commitment lines, among them the owner's 2026-10-03 lines, both replay
    regressions included;
  - 30 clean held-out lines, written after the reader froze at 2c8b72b.

**The split, honestly.** The 160 held-out lines were never read for misses. Twice,
though, I counted held-out act-sequence flips by act name only (no sentence read): once
to find the cause of the acts-in-order drop, and once to categorise the remaining
misses. Both the segmentation demonstrations and the narrowed merge came from those
counts. That makes the 160 a less clean gate than in round 1. I read the clean 30's misses
after their first run; no fix was written from them.

| gemma-4-12B, scored with commitment | strict | engine-relevant | acts in order | commitment |
|---|---|---|---|---|
| pre-lane, held-out 160 | 0.525 | 0.713 | 0.863 | |
| round 1, held-out 160 | 0.650 | 0.750 | 0.819 | |
| round 2 first gate, held-out 160 | 0.694 | 0.812 | 0.850 | 0.994 |
| **round 2 final, held-out 160** | **0.681** | **0.787** | **0.838** | 0.994 |
| round 2 final, held-out commitment 28 | 0.679 | 0.786 | 0.786 | 1.000 |
| round 2 first gate, clean 30 | 0.700 | 0.767 | 0.900 | 0.969 |
| round 2 final, clean 30 (misses seen once) | 0.767 | 0.867 | 1.000 | 1.000 |
| round 2 final, dev 84 | 0.667 | 0.798 | 0.869 | 0.990 |

The final reader differs from the first gate's by a walk's `object` and one demonstration.
On the 160, two runs of nearly the same reader differ by 1.2 to 2.5 points, which is the
noise floor of a single run. Median time per reading was 1.35 s, and no call failed in
any run.

**Not met:**
- **Acts in order** on the held-out 160 is 0.838 to 0.850, against 0.863 before the lane.
- **Engine-relevant** is 0.787 to 0.812, against a target of about 0.90.

Where the final run's 44 held-out engine misses fall:
- 32 are segmentation:
  - 16 extra actions: a posture or a time clause read as its own `wait`, an attack read
    twice;
  - 9 wrong acts;
  - 7 missing actions.
- 11 are a slot, at most 2 of any one kind.
- 1 is commitment.

So the ceiling is how the 12B reader splits a sentence into deeds. Demonstrations moved it
(dev acts 0.845 → 0.869), but not past the pre-lane level on the held-out lines. The
remaining causes are known by act name. The posture class ("I stand at the rail and
watch") carries a `place`, so no structural rule can tell it from a real `wait`.

**The worst engine-damaging class that remains:** "I'm going to <a place>" read as
*intended*, a walk the engine then never makes. It was seen on a dev line and on a clean
line.

**Replayed** against the regex path, with the same final readings fed to both (both
saves; the market save's 7 lines are the items save's first 7):
- Nothing gets worse.
- The crate is acquired at turn 13, as the regex did. The early sale is held back as
  intended, and the sale is made at turn 17, the agreement, as the regex made it.
- Turn 21 no longer refuses a brunt into the prose.
- "Pick the crate back up, then tip the coins" runs in the words' order.
- The one new op: turn 19, "count the coins", is read as taking the coins. The engine
  answers "the payment is already in the purse" and nothing moves.

## Backward: the narration (lane N)

The prose call's JSON is NOT given new fields. It was cut back to one field because
extra demonstrated fields bled escaped JSON into the narration (4 of 8 runs, 2026-09-04;
`prompts.prose_schema`).

1. **One beat reader.** The existing mentions labeller (`gm/mentions.py`, one short
   enum-constrained call after the prose) grows into a structured read of the finished
   beat. It answers, with refs and kinds as enums the engine supplies:
   - who each person mention is (as now);
   - who speaks each quoted line;
   - which people are newly shown here;
   - which places a speaker named that the town does not have, with kind and landmark.
   If one call answering all of these measures worse than two narrower calls, it becomes
   two (CLAUDE.md: a model asked for N things answers in parallel).
2. **Code validates and applies through the engine's doors.** People through
   `judgement.embody`, places through `heard_places.record` and later `found`, lines into
   the conversation log. Refs, kinds and landmarks are checked against the engine.
3. **The regex harvesters retire** as the beat reader covers them: `seen_people`'s phrase
   finding, `speaker_real`'s clause heuristics, `mentioned_elsewhere`, `places_heard`'s
   reading of speech, `pronouns_adopted`, `name_given`.
4. **Policing** (the 33 checks) was out of scope for lane N, except where a check
   only existed to guess what the beat reader now declares. Their re-reading of English is
   the same problem, and the follow-up was to have a reader answer closed questions, with
   code comparing those answers to the engine's outcomes:
   - "where does the player end up: one of these places, or none";
   - "what changes hands".

   **Started in lane V, 2026-10-03** (`docs/beat-verify.md`, branch
   `structured/beat-verify`).
   - `gm/beat_verify.py` reads the finished beat back. Every slot is an enum the engine
     supplies: where the player ends, what changed hands, trades, harm, arrivals and
     departures, and the hour.
   - Every claim's quote is checked in code to be the page's narration.
   - Code diffs the claims against `resolution.outcomes` and the scene. Each
     contradiction is asked once more as a yes-or-no question about its one sentence.
   - `gm/checks/beat_verified.py` runs it behind the registry and repairs through
     `_repair_sentences`.
   - On a 50-beat bench (gemma-4-12B, 2 runs): alarm precision 1.00, recall 0.78, no
     clean beat alarmed. The regex checks scored precision 1.00, recall 0.61.
   - Retired: `thing_kept`, `trade_claimed` and `time_of_day`.
   - Kept: `refused_move`, which measured better, and `empty_roll`, which is equal on
     harm and covers victims who are not listed.
   - Its interface (`facts_from` / `read` / `diff`) is kept separate so it can be folded
     into this beat reader after lane N merges, if one call measures as well as two.

### Built (lane N, branch structured/beat-reader, 2026-10-03)

`gm/beat_reader.py`, measured in docs/beat-reader.md. Two calls, not one: the people
call (mentions, lines, newcomers here or elsewhere, names, arrivals of people known
elsewhere in town, pronouns) and the places call (places named, people placed), run side
by side. Every answer is an enum the engine supplies, or a string that must be on the
page; a failed check drops the answer with the reason in the `beat-reading` row.

| retired | replaced by |
|---|---|
| `judgement.record_people`'s seen/heard reading (`seen_in_beat`, `_shown_in`, `_cue`, `_gendered`, `_said_to_live`, `_shown_again`) and `only_a_predicate` | newcomers "here"/"elsewhere" (`seen_people`); `record_people` is a plain recorder |
| `speaker_real`'s `_from_tags`, `_from_the_page`, `_Room`, `_whose`, `_speaker` | each line's `by`/`to` (`speaker_real`, booking only) |
| `judgement.doubt_tags` | `beat_reader.reconcile_tags` |
| `judgement.hailed_by`'s untagged-line guess | booked lines only |
| `judgement.apply_introductions`, `narration.named_in_apposition` | `names` + `beat_reader.name_refusal` (`seen_people.name_them`) |
| `heard_places.heard_in` and its patterns | the places call (`places_heard`) |
| `mentioned_elsewhere.phrases_at`, `_PRONOUN_AT` | the places call's people (`mentioned_elsewhere`) |
| `pronouns_adopted`'s `_from_mentions`, `_from_tags` | the people call's `pronoun cN` |

Kept, as structure: `mentions.find` (candidate spans from the engine's vocabularies),
`speech.spans`, `name_given` (the brief's exact name on the page), `note_cast` (the
brief's ledger only — next step below), `embody_seen`'s limits.

**When the reader fails** nothing is harvested from the beat and each step writes a
`beat-unread` row; the prose call's own tags still stand.

**Next steps, not done in this pass:** `note_cast` still books the brief's "ALSO
PRESENT" ledger with its own phrase patterns — it should take the reader's newcomers; the
33 policing checks (lane V); `narration.introductions`/`settle_introductions` (read by the
checks and the groom); `speech.vocalisations` (who grunted); the opening's `note_cast`.

## How it is proven

- `tools/interpreter_bench.py` on all 220 labelled sentences: strict and engine-relevant
  scores, against the baseline above; the held-out 160 count.
- A beat-reader bench built the same way, from the two 2026-10-03 saves' beats and the
  Bobby corpus, labelled by hand.
- Both saves replayed turn by turn through the new path: what ops the readings produce
  against what the regex path produced.
- The full suite. Tests that pinned a regex reader's behaviour are moved to the reading's
  behaviour (`interpret.remember`), not deleted.
- Live turns in the running app on copies of both saves.
