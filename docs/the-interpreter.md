# The interpreter

*2026-09-27. The user's words: "would it be possible to run an interpreter on user
prompts that would pull out user intent more clearly?", and then, "do the interpreter
first — the whole app hinges on consistently good narration and accuracy."*

---

## Why

Today the player's sentence is read twice:

- **By the planner model,** which reads it and writes the turn's ops in one call.
- **By about twenty regex readers** in `gm/judgement.py`, each for one kind of
  declaration: travel, buying, calling on, breaking in, waiting until a time, insults
  and so on. What they find, the schema then requires the plan to contain.

Nearly every live defect of 2026-09-27 was one of those readers misreading English:

| The sentence | What went wrong |
|---|---|
| "I go to the market **and look for** the bread seller" | looked for "market" |
| "the woman **who sold** me bread" | looked for "woman", and missed the irregular past |
| "I ask **her name**" | "her name" became a person to introduce |
| "wait until **ten at night**" | planned as 140 minutes |
| "I find **somewhere** to sleep" | "somewhere" became a person |
| "I go to the market and buy a coil of rope" | no walk planned |

Each was patched, and the list grows by one reader per feature. The code's own comment
names that as the smell.

## What the research found (two passes and a critic; sources below)

- **Put the real state in front of the model.** FIREBALL (ACL 2023, arXiv 2305.01528)
  translated D&D players' words into Avrae bot commands, with GPT-3 Davinci and not a
  local model:

  | Setup | Commands that ran | Right state change |
  |---|---|---|
  | Fine-tuned, with state | 0.726 | 0.65 |
  | Fine-tuned, without state | 0.235 | 0.234 |
  | 3-shot, with state | 0.432 | 0.429 |
  | 3-shot, without state | 0.319 | 0.25 |

  The critic's correction: the paper never calls state "the largest factor", and its
  effect depends on the setting (+0.49 fine-tuned, +0.11 in 3-shot). The unit tests
  were 10 hand-written scenarios.
- **Small models extract slots poorly unprompted, and invent normalised values.**
  Uniphore (COLING 2025 industry): zero-shot Llama-3-8B and Mistral-7B averaged slot F1
  0.52, Gemma-2B 0.40, and fine-tuned Llama-3-8B 0.77. The F1 is lenient, measured on
  in-house call-centre text.
- **Several actions in one sentence is the hard case.** On MixATIS, QLoRA fine-tuned
  7B/13B models reached 53.4% whole-frame accuracy, about 31.5% with three intents. A
  *prompted* ChatGPT 5-shot managed 14.6%. The figures are from v1 of arXiv 2403.04481;
  the current version is a different paper.
- **Parse one action at a time and ground each against the state the last leaves.**
  Inform's DM4 §34: "It's important not to parse them all at once: the meaning of the
  noun phrase 'stone' depends on where the player is by then." adv3Lite executes the
  first predicate and re-parses the rest.
- **Grounding chooses between readings,** and "which do you mean" is asked only on a true
  tie (Inform's does-the-player-mean rules; adv3Lite's `getBestCmd`; Plotkin, 2024).
- **An LLM rewriting input into parser commands substitutes objects** ("examine phone"
  came out as "examine note"), turns bare verbs into other commands, and varies on the
  same input (intfiction.org beta testers). The community verdict: acceptable as a
  preprocessor onto a closed command set, never as the world model.
- **Verbatim spans.** Google's LangExtract aligns each extraction to the input and flags
  what it cannot align. It keeps those (the critic's correction); dropping them is ours.
- **JSON mode helps classification and is contested for reasoning.** "Let Me Speak
  Freely" (arXiv 2408.02442) measured it; dottxt's rebuttal found the prompts differed
  between conditions. Field order matters in constrained output.
- **Not usable as evidence:** Rasa deprecated both its multi-step and its single-step
  LLM command generators, with no reason given.

## What was built

- **`gm/interpret.py`:** one constrained call with the narrator's model (already
  loaded, since a second model's load dominates local latency), temperature 0.
  - **The reply:** an ordered list of actions, each with verbatim slots (`target`,
    `object`, `place`, `time`, `says`) and then an `act` from a closed list of 27,
    including `other`. It also carries `question`, for something asked of the game, and
    `claims`, for outcomes asserted rather than attempted.
  - **The prompt:** twelve demonstrations and the act list. None of the demonstrations
    is in the labelled set.
  - **`interpret.ground`:** drops any slot or claim that is not the player's own words.
- **`tests/interpreter/gold.py`:** the labelled set, 220 lines.
  - Sources: the audit scripts, the playtest write-ups, every live misreading of the
    day, and hand-written hard cases (several actions, relative clauses, times,
    quotations, questions, claims).
  - `tests/test_interpreter_gold.py` holds that every label quotes the sentence.
- **`tests/interpreter/score.py`:** whole-frame match, acts in order, act and slot
  precision, recall and F1, with lenient slot matching.
- **`tools/interpreter_bench.py`:** runs the interpreter and scores today's detectors on
  the same lines.

## Measured

**The detectors, acts only (no model, 220 lines):** acts fully right on 28.6% of
sentences; precision 0.607, recall 0.381, F1 0.468. The recall is not a fair verdict on
them alone, since they were built to catch certain declarations and leave looking and
talking to the planner. But 39% of what they do flag is wrong.

**The interpreter (gemma-4-12B, 220 lines, temperature 0), in the order it was built:**

| Version | Whole frame | Acts in order | Act F1 | Slot P / R / F1 | Median seconds |
|---|---|---|---|---|---|
| slots optional | 5.0% | 83.2% | 0.890 | 1.0 / 0.0 / 0.0 | 1.0 |
| slots required | 10.9% | 85.0% | 0.904 | 0.33 / 0.85 / 0.48 | 1.9 |
| + per-act slots (TADS verb templates) | 33.2% | 85.0% | 0.904 | 0.58 / 0.85 / 0.69 | 1.9 |
| + one phrase, one slot; times checked | 56.4% | 85.0% | 0.904 | 0.76 / 0.79 / 0.77 | 1.9 |
| + a phrase inside another is one description; stray times moved | 59.5% | 85.0% | 0.904 | 0.80 / 0.75 / 0.77 | 1.9 |
| + sharper act lines, four more demonstrations | **60.0%** | **85.0%** | **0.914** | **0.81 / 0.79 / 0.80** | 1.9 (p90 2.7) |

- **Optional slots were never written.** With the slots optional, the constrained
  sampler wrote `span` and `act` and nothing else on 220 of 220 lines, because a
  property the grammar lets it skip is one it skips.
- **Required slots were written everywhere.** Made required, the model filled all five
  and copied one phrase into several: "I punch him again" came back with "him" as the
  target, object and place, and "again" as a time.
- **Each fix after that is mechanical, in `ground`.** No second model call: the slots an
  act can have, one phrase to one slot, a time must be a time, and a phrase inside
  another slot's phrase is part of that description.

**Against the detectors, on acts:** in order on 85.0% of sentences against 28.6%, and act
F1 0.914 against 0.468. Every live misreading of the day is read right. The one wrong
reading among the failure lines: "I ask around where the reeve lives and go there" reads
its second half as `go`, not `call_on`.

**Left as misses rather than bent to fit:** several misses are readings as defensible as
the label ("seek … place=the market", taunting somebody's friends read as talk rather
than insult). The labels were not changed to match the model.

## First integration (2026-09-27)

Additive, as the research advised: keep the fast word-detectors as a second opinion
(Rasa's pattern) and retire each only on a measured comparison.

- **When:** `GMAgent.plan_turn` reads the sentence first. A failed reading is logged
  and changes nothing.
- **What the planner sees:** a fact line of the actions in order ("THE PLAYER'S WORDS,
  READ"), what is only claimed, and whether it was a question.
- **What the schema requires:** the ops the reading grounds (`interpret.ops_for`)
  join `declared_ops`:
  - a `go` to a place this town really has (the model still names it from the brief's
    list);
  - `journey`, `call_on`, `break_in`, `rest`;
  - a `wait` with a time;
  - an `insult` (`provoke`);
  - `talk` with words said.
- **What the readers take from it:** `person_sought` (seeking, calling on, or talking to
  somebody), `purchase_sought`, `called_on` and `breaks_in` consult the reading first,
  and the regex is the fallback.
- **What is logged:** the reading, the ops it grounded, and the detectors' ops, per turn
  (`turn_log` "turn" entries, `reading`).
- **Off in the test suite,** as the written opening is (`interpret.ENABLED`).

## Found on the way: Ollama does not enforce `contains`

Measured 2026-09-27 against the local model, with a prompt that invited the wrong op:

| Construct | Replies holding the required op |
|---|---|
| `allOf` of `contains` (what `turn_schema` used for `must_contain`) | 0 of 6 |
| `prefixItems` | 0 of 6 |
| a required object property | 6 of 6 |

So every declarer's "the reply is unsamplable without one" had only ever been a hint the
model could ignore, and it did: "I go to the market and buy a coil of rope" planned no
walk twice, with the requirement in place.

The ops the player's words commit the turn to are now also required keys of a
`declared` object in the reply (`prompts._declared_op`), merged into the intents where
missing (`GMAgent._merge_declared`):

- a travel goes first, its place held by an enum to the names of this town's real
  places;
- an introduce goes next, before anything that addresses the person it brings in;
- everything else goes after.

**Two defects the first live run of it found, both fixed:**

- **Wrong order:** appended last, a declared introduce followed the model's own `say` to
  new1, every attempt was refused, and the turn fell back to `narrate_only`.
- **A walk owed to where the party stands:** at the market already, a detector's
  `travel` forced the model to walk elsewhere, because the place was held to the other
  places. Where the reading says the named place is the party's own, that `travel` is
  dropped.

**Where the two disagree:** a detector's op stands only when an act of the reading
supports it (`interpret.supported`). The overruled op is logged. Live, a detector
required `give` for "I buy a dragon's egg".

**Latency:** readings took 2 to 3 s on most turns and 16 to 20 s on a few. The model is
the same for every role and `num_ctx` is fixed, so this is not a reload. The likeliest
cause is queueing behind the app's background calls between turns (the watcher); it is
not yet measured.

## The live battery (2026-09-27, gemma-4-12B, 60 turns across five scripts, the reading on)

| Script | Turns clean |
|---|---|
| calling | 12 of 12 |
| homes | 12 of 12 |
| buying | 11 of 12 |
| provoke | 10 of 12 |
| fight | 4 of 12 |

- **No reading failed.** Median time 3.1 s, p90 19.7 s: the spikes are the queueing
  noted above.
- **The reading overruled 7 detector ops, all wrong.** The goods detector reads "pick"
  as picking something up, and required a `give` for "I pick the lock on her door" and
  "I pick a fight with the biggest man in the room". It also required one for "I buy a
  dragon's egg".
- **The reading added ops no detector found:**
  - `provoke` on four insults ("call him a coward", "tell his friends he cried", "tell
    the barkeep he smells", "tell the room he is all talk");
  - `break_in` on both break-ins, and `call_on`;
  - `say` on the questions asked.
- **The fight script's 8 "third-person-pc" turns are not the reading's doing,** as far
  as two runs can show. The control with the reading off had 2 of 12. Every flagged
  sentence in both is the enemy-turn narration giving the character's name to the enemy
  ("Kesst Vayr with the marked knuckles lets out a low, guttural growl", reading off),
  which is written after the plan and never sees the reading. The plans of the two runs
  were near identical. The ON run grappled, and every enemy turn after it repeated the
  confusion. Flagged as its own task — and settled in `docs/wrong-actor.md`: rerun the
  same day, reading on 2 of 12, off 3 of 12, and every flagged sentence in both was put
  there by our own grooming (`creature_nouns_for_pc` swapping "the beast" — the enemy —
  for the player's name, and a name swap that ignored the first name alone).
- **Conjured gifts:** both fight runs, with and without the reading, had the model's own
  `give` conjure things ("Kesst Vayr takes fight", "takes table"). With a reading, a give
  to the player that no act asked for is now dropped (`interpret.drop_unread_gifts`).
