# The beat read back: verification by round trip (lane V)

The owner, 2026-10-03, after a day of regex checks that each exposed the next:

> "we cant really depend i think on just layering mechanical detection logic on top this
> will be an endless loop"

and then:

> "could we have the interpretor/one of these smaller models read the final text convert
> it back to json and make sure that it matches the expected actions?"

This is that check. It is `docs/structured-turn.md`, Backward §4 ("Policing … the next
step"), built.

- `gm/beat_verify.py` is the reader and the diff.
- `gm/checks/beat_verified.py` is the registry member.
- `tests/beat_verify/gold.py` is the bench.
- `tools/beat_verify_bench.py` runs it.
- `tests/test_beat_verify.py` replays the model's recorded answers.

## The shape

1. **A model reads the finished beat.** It answers one schema-constrained question:
   what does the narration say happened? Every slot is an enum the engine builds at call
   time:
   - `player_ends_at`: one of the places the engine knows, or "somewhere not listed";
   - `changed_hands`: an item from the pack, the props here or this turn's outcomes, or
     "something else"; from and to are refs, "the floor", "nobody" or "someone not
     listed";
   - `trades`: the item, the seller and buyer refs, and `settled`;
   - `harmed`: a ref, and `hurt`, `down` or `dead`;
   - `arrived` and `left`: a ref or "someone not listed";
   - `time_of_day`: night, before dawn, dawn, morning, midday, afternoon, dusk, evening,
     or "unstated".
2. **Code validates the answer.**
   - Every claim carries a `quote`. Code checks that the quote is the page's own
     narration, with speech blanked first, because a character may say anything.
   - The quote must be at least three words long.
   - Every slot must hold the engine's own value. A claim that fails is dropped.
   - A claim stated twice is kept once.
3. **Code compares the claims with the engine.** The engine's side is `resolution.outcomes`
   plus the scene after the turn (`beat_verify.facts_from`). A claim is judged only where
   the engine holds the fact outright. A thing "not listed", a newcomer, or a wound in a
   beat where nothing rolled harm is left alone.
   - **Contradiction:** the page claims what the engine did not do. It is repaired through
     `GMAgent._repair_sentences`: one targeted rewrite of the sentence with the engine's
     fact named, checked by reading the rewrite back. The backstop then cuts the sentence,
     and for a move or a sale puts the engine's own sentence on the page.
   - **Omission:** the engine did something the page never says. Only the trade is judged,
     and only when the page does not even name the thing. The backstop puts the engine's
     refusal before the hand-back.
4. **Each contradiction is asked once more** (`beat_verify.confirm`). It becomes a closed
   yes-or-no question about its one sentence, and is kept only on a yes. The hour is not
   asked again (see below).

## Prior art

A second pass checked every source against the primary paper or model card.

- **Wiseman, Shieber & Rush 2017**, "Challenges in Data-to-Document Generation", EMNLP
  (aclanthology D17-1239).
  - An information-extraction model reads the generated text into (entity, value, type)
    records, which are compared with the source records.
  - Relation generation (RG) is the precision and count of extracted records found in the
    source.
  - Content selection (CS) is precision and recall against the records extracted from the
    gold text.
  - Content ordering (CO) is a normalised Damerau-Levenshtein distance.
  - **The documented weakness:** their extractor scores over 90% accuracy, yet it recalls
    only about 60% of the relations. Run on human-written gold summaries, it scores 91.77%
    RG precision, so about 8% of its "errors" are its own.
  - This is why the bench below scores the READER (per-claim precision and recall)
    before it scores the alarms.
- **QAGS**, Wang, Cho & Lewis 2020, ACL (arXiv 2004.04228).
  - It generates questions from the output, answers them from both the source and the
    output, and compares the answers.
  - Pearson correlation with human judgement is 54.53 on CNN/DM and 17.49 on XSUM.
  - In their own error analysis of 400 XSUM cases, 8.75% of the questions were
    nonsensical and 32.5% of the source-side answers were wrong.
  - Here the source side is never read: the engine's records are the answers. Only the
    page side carries a reader's error.
- **The checker inherits its reader's errors.**
  - FRANK (Pagnoni et al. 2021, NAACL): every metric correlates weakly with human
    judgement (best 0.27 Pearson; QAGS 0.06), and the QA metrics correlate negatively on
    coreference and discourse errors.
  - SummaC (Laban et al. 2022, TACL): granularity decides the result. With the whole
    document as premise, an NLI model gave 0.91 entailment to a summary holding an
    unsupported sentence. That is one reason the second read here asks about **one
    sentence**.
- **LLM claim extraction and verification.**
  - FActScore (Min et al. 2023) splits text into atomic facts. Its automatic estimator is
    within 2% of human scores.
  - SAFE (Wei et al. 2024) agreed with humans on 72.0% of 16,011 facts and won 76 of 100
    disagreements.
  - RefChecker (Hu et al. 2024): claim triplets beat other granularities by 4-9 points.
    Extractor precision and recall were GPT-4 92.4/88.6, zero-shot Mistral-7B 82.2/68.2.
    Triplets cannot carry time qualifiers.
  - Claimify (Metropolitansky & Larson 2025) extracts nothing from a sentence it "cannot
    be disambiguated", and 99% of its claims are entailed by the source.
  - MiniCheck (Tang, Laban & Durrett 2024): a 770M checker reaches GPT-4's level on
    LLM-AggreFact. Claim decomposition showed "no clear indication" of helping.
  - **Taken here:**
    - typed, narrow slots;
    - abstention values ("not listed", "unstated");
    - a verify-each-claim step;
    - time scored on its own row, where FRANK and RefChecker both found it weakest.
- **Games.**
  - Callison-Burch et al. 2022 (EMNLP): a fine-tuned 64B model tracking D&D state
    reached 58% joint accuracy.
  - NCP-Bench (Ma et al. 2026, arXiv 2608.08160) audits narration against an "active fact
    ledger" with an LLM. All 4 of its disputed false positives in a human check of 100 were
    at state transitions.
  - No published work was found that reads typed claims out of game-master narration and
    compares them in code with engine outcome records. Wiseman's RG against box scores is
    the nearest.
- **Small structured-extraction models.** The vendor claims below were verified; there is
  no independent evaluation of either model.
  - **Osmosis-Structure-0.6B** is Qwen3-0.6B trained with RL on 500K synthetic examples.
    It is meant as a second pass that structures another model's free-form answer. Its
    only published results are math benchmarks; there is no benchmark for extraction from
    prose.
  - **NuExtract 2.0** has no Ollama build on this machine, so it was not measured.
- **Could not source:** JSONSchemaBench's numbers; FIREBALL's numbers beyond its abstract;
  how NuMind computes its F-score.

## Schema enforcement probe

Run 2026-10-03 on the real schema: 6 runs per model, the first at temperature 0 and the
rest at 0.7. The passage was built to tempt off-enum answers: a hammer not in the pack,
the street, a boy not listed.

| construct | gemma-4-12B | Osmosis-Structure-0.6B |
|---|---|---|
| required top-level keys | 6/6 | 6/6 |
| nested object, enum + required | 6/6 | 6/6 |
| array of objects, enum slots + required | 6/6 | 6/6 |
| boolean inside array items | 6/6 | 6/6 |
| `maxItems: 6` | 6/6 | 6/6 |

This matches memory `ollama-schema-enforcement`: required properties and enums hold.
Enforcement is not quality, though. Osmosis's answers were in-schema and wrong: invented
quotes, "someone not listed" for everybody, and `player_ends_at: the great square` for a
walk into the street. Its runs took 10-33 s, because it filled `num_predict` with repeated
rows.

## The bench

`tests/beat_verify/gold.py` holds 50 labelled beats.

- **36 tuned beats.** These come from the owner's 2026-10-03 save as played live (the
  `kesst:` and `talk:` sources) and from the Bobby corpus (`bobby:`). Their prose is cut
  to the sentences a label needs; the saves themselves are never committed. A beat marked
  "draft" is the text before a check repaired it: the flagged sentence from the save's
  `truth-checks` row put back. The set includes every case in the brief:
  - "You move toward the anvil";
  - "the smith, Korvu, … takes the crate from you";
  - "The transaction is finalized. The heavy clink of the coin";
  - "The clerk's eyes drop to the floor";
  - "midnight" and "the first hint of dawn" against the clock;
  - "You step out of the heat of the smithy and into … the street";
  - 24 clean beats that must raise nothing.
- **14 held-out beats.** These come from the scripted sessions of 2026-09-25
  (`tests/replay`). They were labelled before any run, and nothing was tuned on them.

Each beat carries:
- the engine's side, in the shape `facts_from` builds;
- what the narration claims, hand-labelled;
- the alarms a correct comparison raises.

`tools/beat_verify_bench.py` scores three things:
- the reader, per claim category;
- the alarms, per category, before and after the second read;
- the beat-level false-alarm rate on the clean beats.

It also runs the regex checks on the same beats. Their harness is a stub engine with the
same places, pack, clock and outcomes, plus `narration.contradicts_state`, the review's
state reader.

### Results, 2026-10-03

**gemma-4-12B (heretic), 2 runs over all 50 beats.**

Ollama was shared with lanes F and N throughout. An earlier run under heavier contention
had a read median of 8.4 s.

| claims (validated) | precision | recall | precision with no quote check |
|---|---|---|---|
| player ends at | 0.91 | 0.91 | 0.91 |
| changed hands | 0.67 | 0.88 | 0.61 |
| trades | **1.00** | **1.00** | 0.71 |
| harmed | 0.86 | 0.86 | 0.86 |
| time of day | 0.88 | 0.88 | 0.78 |
| all | 0.84 | 0.90 | — |

- The quote check made the difference on trades: "the exchange" and "the sound of a
  person who has finished their part in the exchange" both arrived as settled sales.
- Latency of the read: median 4.4 s, p90 6.1 s, max 14.7 s over 100 calls.
- Reads that failed: **0 of 100**. Across every gemma bench run this session it is
  0 of 244.

**The alarms against the regex checks.** Alarm counts are summed over the two runs for
gemma; the regex checks are deterministic and ran once.

| category | regex checks: P / R | read back, first read only: P / R | read back + second read: P / R |
|---|---|---|---|
| move | 1.00 / 1.00 (3/3) | 0.67 / 0.67 | 1.00 / 0.67 (4/6) |
| hands | 1.00 / 0.40 (2/5) | 0.80 / 0.80 | **1.00 / 0.80 (8/10)** |
| trade | 1.00 / 0.50 (2/4) | 1.00 / 1.00 | **1.00 / 1.00 (8/8)** |
| harm | 1.00 / 0.33 (1/3) | 1.00 / 0.33 | 1.00 / 0.33 (2/6) |
| hour | 1.00 / 1.00 (3/3) | 1.00 / 1.00 | **1.00 / 1.00 (6/6)** |
| all | 1.00 / 0.61 | 0.88 / 0.78 | **1.00 / 0.78** |
| clean beats falsely alarmed | 0 of 36 | 2 of 72 | **0 of 72** |
| bad beats fully caught | 7 of 14 | 20 of 28 | 20 of 28 |

The second read asked 24 of the 100 beats, at a median of 3.5 s and a max of 20.9 s. It
refuted both first-read false alarms and no true one:
- "You thrust the heavy crate forward across the workbench" as a hand-over;
- "the sudden, ringing silence of the square" as a move.

The regex checks' 0 false alarms are not free. Each was patched after a live false alarm
on these same beats (`refused_move` for the anvil, `contradicts_state` for the clerk's
eyes), and their misses are the phrasings nobody had patched yet:
- "Korvu takes the crate" with no "from you";
- "the transaction is finalized" on a turn with no `sell`;
- the crate lifted "from the dirt" that the engine never picked up.

**Osmosis-Structure-0.6B, 1 run over all 50 beats.** This ran an earlier build of the
module: before the bench's last fixes (each sentence judged, descriptor names, "left
behind", the pick-up demonstration).
- Claims: precision **0.06**, recall **0.16**.
- 242 claims were dropped by validation, mostly quotes that are not on the page.
- 11 of 50 reads did not parse (22%). It runs to its token limit repeating rows.
- Alarms before the second read: P 0.27, R 0.20, and 6 of 28 clean beats falsely alarmed.
- Read latency: median 3.7 s.

It is a model for re-shaping another model's answer, which is what its card says. It is
not a reader of prose, and it is not used.

**NuExtract 2.0** has no Ollama build on this machine, so it was not measured.

**The pick: gemma-4-12B, the narrator's own model.** The check routes to the narrator's
model and host (`BeatContext.reader`), so it costs no second model in memory.

### What the reader still gets wrong

- **"You are standing where the paths diverge"** (bobby:6) is read as staying at the way
  in, both runs. This is why `refused_move` stays.
- **Held-out harm.** When the player swings at a Commoner and misses, and the page has
  "the man" hit the ground, the reader puts the blow on the man in stained leather, who is
  already down. A hurt claim against a body already down is not judged, so no alarm is
  raised. The regex checks miss both of these beats too.
- **"the pre-dawn gloom" at 01:28** is read as "dawn". The alarm is right either way:
  neither word fits that hour.
- **Hands over-reports.** "He takes the paper back from you" and "closes his hand around
  one of the shards" come back as "something else". Things with no engine name are never
  judged, so these cost nothing.

### The second read, and what it was not allowed to do

The first wording of the questions refused true alarms.
- With "Answer no unless the sentence plainly says it", gemma refused 3 of 5 true
  contradictions on a probe, "The transaction is finalized." among them.
- "Does the crate pass from you to the smith?" was refused for "Korvu takes the crate":
  the sentence never says "from you".

The questions now ask only whether the thing moved; the first read supplies the
direction. The hour is not asked again: "is it dawn now?" of "the pre-dawn light" is
correctly answered no, and that is still a true alarm at 01:28.

## Retired, and what stays

Retired where the round trip measured at least as good, at equal precision:

| check | category | regex | read back |
|---|---|---|---|
| `thing_kept` | hands | R 0.40 | R 0.80 |
| `trade_claimed` | trade | R 0.50 | R 1.00 |
| `time_of_day` | hour | R 1.00 | R 1.00, no false alarm |

Kept:
- **`refused_move`** measured better (3/3 against 4/6). Both run. On one sentence the
  heavier finding wins, and the read back goes first at equal weight.
- **`empty_roll`** is equal on harm. It is also the only reader of a victim who is not on
  the actor list ("Dagan Havenstone", G2), a claim this member never judges.
- **Every other check.** The bench has no row for its kind: road, direction, route,
  bearing, land, setting, faces, speech, keepers, hooks, size, and the rest. Those are the
  next rows to label before anything else retires.

`time_of_day`'s repair cost no model call: it swapped the clock's word in. Its
replacement costs the read, plus at most one rewrite of the sentence, and the backstop
cuts. That is a real cost, accepted because the old repair was itself an English reader.

## When the read fails

`beat_verified.find` raises. The registry books a `check-error` row for the member, and
the turn goes on with every other check. On that beat, nothing stands in for the three
retired categories; the brief allowed this, and it is said here plainly.
- Measured on the bench: 0 of 244 gemma reads failed.
- Osmosis failed 11 of 50.

Every live read is logged as a `beat-verify` row in the turn log: claims, dropped claims,
seconds, and the error if there was one. The live failure rate can be read off saves.

## Not done

- Not played live in the running app. The member is proven through `_repair_sentences`
  and `_groom` with scripted replies, and on the bench with the real model.
- The interface for lane N's beat reader is `facts_from` / `read` / `diff`. Folding this
  read into that call is for after lane N merges; whether one call answering both does
  worse than two must be measured, not assumed.
- Omissions are judged for trades only.
- `arrived` and `left` are read, but only a `left` of somebody the engine keeps here is
  judged, and the bench has a single `left` claim. That is too few to say anything.
- The regex checks without a bench row remain English readers.

## The people not here (2026-10-09)

docs/narrator-after-defeat.md has the defect and the runs. The reader had no code for
anybody the engine holds elsewhere, so the raiders who had robbed the player and gone,
written lunging at the wagon an hour later, were "someone not listed" and never judged.

- The people held elsewhere in town (`beat_reader.away_people`) are offered as codes,
  marked "not here" (`Person.here`).
- On a beat with anybody away, and only then, the reader is asked `shown_here`: which of
  them the passage shows here and now. A beat with nobody away is asked word for word
  what it was asked before (all 50 earlier bench beats: identical messages and schema).
- An away person shown here, hurt here, or arriving with no arrival the engine made is an
  `absent` contradiction (`beat-absent`, weight 3). Its second read asks WHO the
  sentence shows, from the codes, and compares in code.
- Bench, 2 runs, 55 beats: `absent` P 1.00 R 5/6; clean beats falsely alarmed 0 of 76;
  every earlier category as on master. An `attacks` slot was tried and taken out: it cost
  harm claims 12/14 → 8/14 on the same beats.

## Somebody here, written gone (2026-10-09)

docs/departed-beast-and-species-name.md has the defect and the runs: a creature the engine
kept on its seam, written *"The Aelzeldra is gone."* while the player slept.

- The `left` slot read it — once the readers were told what the creature is
  (`mentions.what_they_are`: told "human", 0 of 3 reads found a departure; told "monstrous
  humanoid", 3 of 3).
- The second read refused it: *"does this sentence say that Aelzeldra goes out of the
  place?"* was answered no 3 of 3. It asks *"…has gone — left, or no longer here?"* now
  (`question`), probed against both a departure told as a state and one told as an act.
- The `absent` second read (`_shows`) lists the people as the first read does — what they
  are, and "not here" — not by name alone: a goblin standing here was the away "goblin
  with a scarred cheek" 16 of 16 by name, 2 of 16 so.
- The `left` line of the instruction says "or whom it says is no longer there": on our own
  server, the fixed branch's first live rest turn wrote "the beast is no longer within
  your immediate sight" and the reader filed it as an hour (dropped). With the line it is
  read as a departure 2 of 2 on the bench, and the second read refuses it 2 of 2 — out of
  sight is not quite gone, and the engine holds the creature "far"; labelled either way.
- Bench, 2 runs, 59 beats: `presence` R 2/2, `absent` R 6/6, clean beats falsely alarmed 0
  of 82; every other category as on master.
