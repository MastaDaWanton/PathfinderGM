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

(numbers below)
