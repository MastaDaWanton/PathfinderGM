# The ruling judge — bench record

A bounded ruling layer: given the scene's facts, the character's sheet and the player's
line ("I convince the guard I'm the duke's cousin", "a natural 20 means they all agree"),
return a closed verdict — `say_yes`, `roll`, or `refuse` with a reason — that the engine
applies. The owner's design (2026-11-05): models default to leniency, so the restraint
half must be bounded; creativity changes the odds and the routes, never the outcomes.

**Status: bench-only. Not wired into play.** The gate was 85% verdict agreement with the
owner's key on a held-out split. Nothing measured comes near it (results below).

## The bench (tools/ruling_bench/)

| file | what |
|---|---|
| `build_set.py` | freezes the key into `ruling-set.json`, with each source's sha256 |
| `ruling-set.json` | 152 set1 lines (DEV), 40 set2 lines (HELD-OUT), 6 derived lines |
| `run.py` | one arm over one split; JSONL rows with model seconds AND wall seconds |
| `score.py` | verdict agreement with bootstrap 95% CI, the error kinds, `--recombine` |
| `closed.py` | the closed-question judge (this round) and the precedent picker |
| `judge.py`, `specialists.py` | the 2026-11-06 arms, recovered from the archive, unchanged in logic |

Provenance of the set: labelled on the owner's pages 2026-11-05/06
(`C:\Users\natha\pgm-work\ruling-set`). set1 = `answer-key-set1-v2.json` (38 rulings the
owner wrote, 114 Claude drafts the owner saved; 2 owner-flagged lines left out, with the
shot-in-the-dark lines s3-07/s6-06 re-frozen as oracle). set2 = `answer-key-set2.json`
(40 Claude drafts the owner curated; the owner changed only t1-06). The derived split is
six lines Claude labelled from the owner's recorded rulings in memory, each naming its
ruling; it is reported apart and never counts toward the gate. The correction log
(`training/corrections.jsonl`) holds narration rewrites, not rulings, so it gave no lines;
it was not edited.

Reproduce: `python -m tools.ruling_bench.run --model <m> --arm checklist --prec --qv v3
--split set2`, then `python -m tools.ruling_bench.score --recombine <file>`. Temperature 0.

Error kinds reported: LENIENT (key refuses, judge allows), STRICT (key allows, judge
refuses), MISSED roll (key rolls, judge says yes), NEEDLESS roll (key says yes, judge
rolls), REASON (both refuse, for different reasons).

## What the earlier rounds found (2026-11-06, from the archive)

- One call, whole ruling (judge.py): set1 66 → 72% across three prompt versions, but
  leniency see-sawed 47 → 32 → 42% with each instruction. Held-out set2: 60%, LENIENT 77%.
- Four specialists (specialists.py): set1 76% after tuning; held-out set2: 57.5%. They held
  refusals (lenient 31%) but their "stakes" question said yes to watching, listening and
  searching (MISSED 50%, check lines 17%).
- gemma4:26b MoE: no gain over the 12B. The tuned set1 numbers were overfit.
- A bug found on recovery: the old runner hard-coded fights as {s4, s7}, so set2's fight
  (t3) was judged as "not a fight". The set now records `fight` from the scene.

## Prior art used this round

- CoC-Seduce (arXiv 2607.02802): 22 adjudicators, false passes 9.26% overall, 17% under
  pseudo-logic, false checks 0.08%; reasoning models worse in both pairs tested; no
  defence was tested. → refusals are checked first, in code, in a fixed order.
- Field order: reasoning before the answer fields; answer-first schemas drop hardest in
  small models ("Structure Tax", arXiv 2610.12056, abstract only; "Let Me Speak Freely",
  arXiv 2408.02442).
- Fixed, human-written checklists of closed questions steady a judge: CheckEval (arXiv
  2403.18771), TICK (arXiv 2410.03608: 46.4 → 52.2% exact agreement). Small models
  decompose badly on their OWN, so the questions are ours, not the model's.
- Precedents: kNN demonstrations beat random ones (Liu et al., arXiv 2101.06804); prompt
  label frequency and recency bias the answer (Zhao et al., arXiv 2102.09690) → balanced
  two per verdict, most similar last.
- Inform 7's Before/Instead/Check rulebooks: only the check stages may stop an action —
  refusals belong in check rules, ahead of resolution.
- Self-consistency correlates with correctness but a shared bias survives voting (Xiong
  et al., arXiv 2306.13063); not tried here (it multiplies Ollama time by 3-5 on a box
  shared with seven lanes, and the dominant errors are systematic, not noisy).
- Abandoned by others and so not tried: thinking modes on (CoC-Seduce), fine-tuning on
  ~190 items (Mosbach et al., arXiv 2305.16938: no clear gain over in-context learning at
  this size, high variance).
- Could not confirm: PANGeA's (arXiv 2404.19721) reported 28 → 98% validation accuracy
  for Llama-3-8B; no paper was found that measures LLM agreement with a human GM on
  "does this need a check, and against what".

## This round's design (closed.py)

The model answers closed questions under an Ollama JSON schema (required properties and
enums only — the constructs measured as enforced), reason first; code combines them:

1. `power_used` — an enum of the sheet's own spells, `none`, or `another`. `another` →
   refuse (character). The sheet comparison is the CODE's, not the model's (v2).
2. `beyond_world` → world; `rule_claim` → false_rule; `decides_for_other` → npc_choice.
3. `unknown_fact`: `false` → false_fact; `secret` → oracle roll (the owner's
   shot-in-the-dark ruling; the engine owns the odds).
4. `too_much` → too_much.
5. A sheet spell otherwise → say_yes (its own rules roll).
6. `seeks_hidden` → roll; `outcome` could_fail → roll; else say_yes.

Precedents: the two nearest rulings per verdict from OTHER scenes (tf-idf over the line's
words; set1 is leave-one-scene-out, set2 draws from set1 only), with the GM's bracketed
table note as the reason.

## The curve

All on `igorls/gemma-4-12B-it-heretic-GGUF` (the model the game already loads), temperature
0, one run per line. Verdict agreement, bootstrap 95% CI. Every row's JSONL is in
`tools/ruling_bench/runs/`; `score.py --recombine` reproduces the numbers from it.

| arm | set1 DEV (152) | owner-written (37) | set2 HELD-OUT (40) | lenient (held-out) | median s/line |
|---|---|---|---|---|---|
| 2026-11-06 one call (judge.py) | 72% (tuned) | — | 60.0% | 77% | 3.4 |
| 2026-11-06 specialists v2 | 76.3% (tuned) | 86.5% | 57.5% | 31% | 3.8 |
| direct verdict + precedents | 70.4% | 73% | — | (dev 37%) | 4.2 |
| checklist v1, no precedents | 72.5% (first 40 only) | — | — | — | 12.4 |
| checklist v1 + precedents | 71.1% [64-78] | 76% | — | (dev 22%) | 3.2 |
| checklist v2 (sheet powers in code) | 72.4% [65-80] | 81% | — | (dev 25%) | 9.3 |
| checklist v3 (asks are certain) | 74.3% [67-82] | 81% | **70.0% [55-82]** | 38% | 10.9 / 13.5 |
| checklist v4 (+ act kind) | 75.7% [69-82] | 92% | 65.0% [50-80] | 38% | 8.0 / 4.2 |

Derived-from-rulings split (6 lines, Claude's labels): 4 of 6 on both v3 and v4; both
misses are rolls on lines the rulings say refuse/say yes ("stab the priest" with no
priest present; wading back into the stream).

Seconds are wall time per line measured on an Ollama shared with seven other lanes; the
same arm ran at 3-4 s/line when the box was quiet and 10-46 s/line when it was not.

**Other models: not measured.** llama3.1:8b timed out at 600 s per call on two separate
attempts (2026-11-15, set1 and then set2): the shared Ollama kept the 12B loaded for the other lanes and
never swapped. gemma4:12b, qwen3-8b-heretic and gemma4:26b were queued behind it and never
ran. Ollama answered throughout (/api/ps listed the 12B), so it was contention, not a
wedge. Rerun the sweep on a quiet machine:
`for m in llama3.1:8b gemma4:12b R4C3R/qwen3-8b-heretic:q4_k_m gemma4:26b-a4b-it-qat; do
python -m tools.ruling_bench.run --model $m --arm checklist --prec --qv v3 --tag v3
--split set2; done`.

## Where it stalls, and why

1. **Held-out sits at 65-70%, 15-20 points under the gate**, and the CI is ±15 points on
   40 lines. Dev gains past v3 did not carry: v4 gained 1.4 on dev and lost 5 on held-out.
2. **Leniency on argued claims is the persistent error** (38% held-out). The lines that
   get through are a claimed causal rule dressed as fact: "Tengu love shiny things, so
   she'll obviously take my ring"; "It's raining, so their spears are too slippery to
   hold". The model answers rule_claim "no" and decides_for_other "no" on them. This is
   CoC-Seduce's pseudo-logic class exactly (17% there, on frontier models).
3. **The ask / persuade line is the key's own judgement.** Of 13 lines the v4 model
   called ask_or_offer, the key rolls 5 (Diplomacy: "ask her to let me see the locked
   case") and says yes to 8 ("ask what jobs are going"). No closed question separates
   these; the difference is what the request costs the person, which the scene rarely
   states.
4. **Refusal reason** differs on 40-60% of shared refusals: the key's world /
   npc_choice / false_fact boundaries overlap ("duck under a beam so his swing hits it"
   is npc_choice; "put my back to the stair" is world).
5. **The shot in the dark (oracle) was never caught**: 0 of 4 across splits.
6. **Lexical precedents add little**: majority vote of the k nearest key lines scores
   42-47% alone, and with/without precedents tied 29/40 on the same lines.
7. Owner-written rulings agree far more (81-92% on dev) than Claude-drafted, owner-saved
   ones (70-72%). Part of the gap is the key: drafts the owner saved unchanged are not
   the owner's own ruling. Every held-out line is a draft.

## What would move it (not done here)

- More owner-written rulings, especially a held-out set the owner writes. The 92% on
  owner-written dev lines is the most hopeful number here, and it is 37 lines.
- Engine-side refusals for what the engine already knows (CoC-Seduce, Inform's check
  rules): a claimed bonus or state the sheet does not hold (mage armor, cover, flanking),
  a person not present (the priest), a spell not prepared — the sheet comparison that v2
  moved into code is the pattern.
- A precedent picker keyed by the reader's act enum instead of words (the memory's plan
  of 2026-11-06), once there are enough rulings per act.
- The model sweep above, on a quiet machine.
