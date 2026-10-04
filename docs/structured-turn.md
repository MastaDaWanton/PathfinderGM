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
4. **Policing** (the 33 checks) is out of scope for this pass, except where a check
   only existed to guess what the beat reader now declares. Their re-reading of English is
   the same problem, and the follow-up is to have the beat reader answer closed
   questions, with code comparing those answers to the engine's outcomes:
   - "where does the player end up: one of these places, or none";
   - "what changes hands".
   Recorded here as the next step, not done in this pass.

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
