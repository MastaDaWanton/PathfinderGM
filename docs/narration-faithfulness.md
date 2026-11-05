# The beat read against its own tells (2026-11-02)

The owner, 2026-11-02:

> "anything we can do about the narration slips? perhaps a extra step in the preparation of
> the narration even if it adds a few seconds"

Seconds are acceptable; accuracy is the goal. This is that step, for the planned narrator
(the default since 2026-10-18).

- `gm/beat_verify.py` — `against_tells`: the read, its validation and the second read.
- `gm/planned.py` — `_tells_kept`: the remake of only the slot that broke a tell.
- `play/corrections.py` — `log_auto`: every caught slot logged for training.
- `tests/test_narration_faithfulness.py` — one test per slip, the log, the switch.

## The slips

Seen live on the integration build on 2026-11-01 (planned narration, gemma-4-12B), each
against the tell it contradicts:

1. **A theft written as failed.** The tell had the bracelet taken ("who did not hand it
   over"); the page had it "remains on the tray". A second tell beside it — "already carries
   the silver bracelet … nothing more is picked up" — was an engine defect: "snatch the
   bracelet … and pocket it" read `steal` then `take: it`, and each built a give. Fixed in
   `acts_to_ops.table` (a pronoun take of a thing an earlier deed of the sentence took is
   not taken twice); reproduced before the fix on the bench's first live run.
2. **A fine garbled.** The tell: the fine paid, the bracelet taken back to its owner. The
   page: "You hold the six gold pieces and the silver bracelet for <her>."
3. **A scheduled hour.** The tell: hanged "at first light". The page, twice: "at six in the
   evening".
4. **A failed Bluff credited to the right person** ("sees through your bluff") — fine, but
   the same shape credited to the wrong person was looked for.

None of these is a shape the read back's typed slots read: a negation claims no change of
hands; a fine is not a sale; `time_of_day` reads the clock now, not an hour something is
set for; the attempt slot reads whether a check succeeded, not who answered it.

### The two reports' own slips

The two player reports of 2026-11-01 (0.2.25) were read beat by beat against their tells
(scratch only; nothing of them is in the repo). 37 shipped slips, sorted by whether today's
read back could catch them:

| | count |
|---|---|
| catchable: a read-back category exists and its question applies | 6 |
| partly: a category exists but the slip's shape falls outside it | 13 |
| not covered by any category | 18 |

By type: invented events 9, omissions of a key fact 6, outcomes flipped 4, invented
people/places/things 4, harm or condition 3, wrong actor 2, move or position 2, wrong item
or amount 1, wrong time now 1, wrong time scheduled 1, other 4.

- Of the 6 catchable, 3 were read and still shipped (a setting, a payment the read back
  took for a sale of the wrong thing, an escape check written as failed), and 1 was never
  read: the unshown-deed backstop writes its line after the read back.
- **At least 7 of the 37 were made by our own repairs**, not the model: two Survival
  checks that found no tracks, rewritten by the attempt repair into tracks found ("the roll
  succeeded" is not "something was found"); a cure rewritten as "your blood still tainted"
  by a power-unbacked false positive; a creature renamed "the stranger" and a clerk renamed
  "the merchant" by the groom and the setting repair; a blow cut by a struck-with false
  positive on a blood armament.
- The owner's two "That's wrong" marks (both 0.2.21, both in each report): a backstop
  fragment ("You \"Ah,\" you say …"), style; and a quest made the player's own goal, which
  two slot-wise remakes failed to remove — `own_goal_sentence` has read that since.

What a per-sentence check against the beat's tells can catch is the contradiction class:
the outcomes flipped, the wrong actor, the wrong item or sum, the wrong scheduled time, a
future act told as done, "you remain in conversation" against "you take your leave". It
cannot catch an omission (a missing sentence contradicts nothing) or an invention no tell
speaks to (a smith promising the work "by the next moon").

## Prior art

Primary sources, checked by a second pass (which discarded one set of numbers a PDF fetch
had invented, for CoVe). Numbers are the papers' own.

- **Granularity: check each sentence.**
  - SummaC (Laban et al., TACL 2022, arXiv 2111.09525): NLI checkers failed on summaries
    because they were trained on sentence pairs and applied to documents. Splitting both
    sides into sentences: SummaC-ZS 72.1 and SummaC-Conv 74.4 balanced accuracy on their
    six-dataset benchmark, against 61.3 for MNLI over the whole document, 62.8 FactCC,
    69.4 QuestEval. ZS is "highly sensitive to extrema": one noisy score flips a verdict.
  - MiniCheck (Tang, Laban & Durrett, EMNLP 2024, arXiv 2404.10774): a 770M checker at
    74.7 against GPT-4's 75.3 on LLM-AggreFact, applied per sentence. **Decomposing
    sentences into atomic facts gave "no clear indication" of helping** (GPT-4 +0.3,
    MiniCheck −1.4, SummaC-CV −3.3) at 2-4x the cost.
  - Xu et al. 2024 (arXiv 2402.12821), LLM judges: sentence-window prompting 57.12 against
    whole-summary 46.24 (macro). Zero-shot Llama-2-7B/13B sat near chance either way.
  - AlignScore (Zha et al., ACL 2023, arXiv 2305.16739): the context side split too finely
    loses inter-sentence context — so the premise here is all of a beat's tells at once.
- **Verify, then edit only what disagreed.**
  - RARR (Gao et al., ACL 2023, arXiv 2210.08726): research, an agreement check per piece of
    evidence, and an edit only on disagreement. Preservation was measured (character
    Levenshtein ~90 for RARR against ~25-46 for editors that rewrote). **Without the
    agreement gate it "leads to over-edits".**
  - Chain-of-Verification (Dhuliawala et al., Findings ACL 2024, arXiv 2309.11495):
    factored verification beat joint (biography FactScore 55.9 → 63.7, 71.4 with
    factor+revise). **Yes/no verification questions underperformed** — "the model tends to
    agree with the way the question is stated" — and joint verification repeated the
    draft's hallucinations. CoVe is closed-book; here the tells are ground truth, which
    makes RARR and CRITIC the closer analogues.
  - NCP-Bench (Ma et al. 2026, arXiv 2608.08160): an LLM auditor checks each narrator turn
    against an active fact ledger, **with a second confirmation step before a conflict
    counts**; experts disputed 4 flags, all at boundaries. Fact conflicts were the top
    failure for every model, 40-68% of turns.
- **Self-critique without grounding does not help.**
  - Huang et al., ICLR 2024 (arXiv 2310.01798): intrinsic self-correction made results
    worse (GPT-3.5 CommonSenseQA 75.8 → 41.8; GPT-4 GSM8K 95.5 → 89.0).
  - CRITIC (Gou et al., ICLR 2024, arXiv 2305.11738): with tool feedback, gains (AmbigNQ
    F1 67.3 → 74.9); with the model's own critique, "marginal (−0.03 and +2.33 F1)".
  - Kamoi et al. (TACL 2024, arXiv 2406.01297): self-correction works with reliable
    external feedback, and "no prior work" shows it with feedback from prompted LLMs alone.
  - Self-Refine (Madaan et al., NeurIPS 2023, arXiv 2303.17651): Vicuna-13B could not
    produce feedback in the required format. Specific feedback beat generic.
- **Small judges are weak and biased; measure them.** SummEdits (Laban et al., EMNLP 2023,
  arXiv 2305.14540): most LLMs "close to random"; many over-flag (low precision, high
  recall); entity swaps are hardest. AFaCTA (ACL 2024, arXiv 2402.11073): 7-13B models
  changed their verdict under argument-order swaps in 97-99% of cases. ReaLMistake (COLM
  2024): even large models detect errors at low recall; majority vote does not help.
- **Game masters.** FIREBALL (Zhu et al., ACL 2023, arXiv 2305.01528): state-to-narration
  models narrated a creature left at reduced HP as killed, "still … frequently" with state
  in the prompt — the wrong-outcome slip, with no repair step. SCORE (arXiv 2503.23512)
  flags items that reappear after being lost, at about 13 s an episode.
- **Could not confirm / not found:** no paper measures a per-sentence verify-and-repair
  pass for a game narrator against engine events with a 7-13B local model; no primary
  source evaluates Gemma 12B as an entailment judge; the direction of a small judge's bias
  (toward "consistent" or toward over-flagging) is model- and prompt-specific in the
  sources, so it is measured below rather than assumed.

## The design

Everything follows from four findings above: per sentence (SummaC, MiniCheck); edit only on
a disagreement (RARR); grounded feedback, never "is this wrong?" (Huang, CRITIC, Kamoi);
confirm with the order swapped and more than yes/no (NCP-Bench, AFaCTA, CoVe).

1. **The read** (`beat_verify.against_tells`). Once the planned beat's slots are written,
   one call reads every sentence (speech kept: a reply's words are what the narrator made
   the speaker say) against all of the beat's tells as numbered facts. The tells pass
   through `narration.page_line` (no roll arithmetic, no damage amount) and lose the XP
   line. The schema holds one required entry per sentence: a verdict from
   `agrees / contradicts / not about it`, the fact (`none` or `F1..Fn`, an enum), and the
   clashing words. Two synthetic demonstrations, neither a bench scenario.
   - "Not about it" is the narrator's licence for colour; only "contradicts" costs
     anything. A supported/unsupported checker would flag every embellishment.
2. **Code validates** (`_clash_quoted`): a contradiction must name a fact on the list and
   quote at least two of the sentence's own words. Otherwise it is dropped and logged.
3. **The second read** (`second_on_tell`): the one fact first, the one sentence after it,
   three answers — `tells it / cannot both be true / says nothing about it`. Kept only on
   "cannot both be true". **Since 2026-11-03 it no longer refuses the first read's
   clashes** (`beat_verify.TELLS_VETO = "none"`); it still judges a remake against the tell
   it was remade for. See "Who may refuse a clash" at the end.
4. **The remake** (`planned._tells_kept`): only a slot holding a confirmed clash is asked
   again — its own kept call (the bytes it was first asked with) plus the clashing sentence,
   the clashing words and the tell it breaks. The remake is read again (both reads). It
   stands if clean. Still clashing, or not remade: the clashing sentences are cut; an act
   slot left empty gets the engine's own line; any other slot goes. Every other slot's words
   stand exactly as written.
5. **The log** (`corrections.log_auto`): every caught slot is a line of
   `<data>/training/auto-corrections.jsonl` — see "Training data" below.

It runs inside `planned.write`, before the page pass, the backstops and the read back, so
the tail sees a beat that already agrees with its tells, and a slot is remade the planned
way (a free-prose rewrite of the whole beat is what rough edge 5 measured going wrong).

**Always on.** The owner's ruling of 2026-11-02: no Settings switch. It was a house rule
`tells_check` for a day, writable through `/api/homebrew/rules` though no page showed it;
that key is gone (`planned.tells_check_on`). Only `PATHFINDER_GM_TELLS_CHECK=0`, which the
app never sets, turns it off: for a bench's before-and-after run, and in the suite.

## Training data

The owner, 2026-11-02: "also log the narration corrections for training." Every slot the
check caught is a label of the kind a player's "That's wrong" is — this text is false, here
is the fact it breaks — made by a machine.

- **Where.** `<data>/training/auto-corrections.jsonl`, beside the player's
  `corrections.jsonl` and never in it: the player's log is reviewed by correction id, and
  their marks must stay theirs. The user's own data folder only; nothing in the repo.
- **What.** One line per caught slot (`corrections.log_auto`): `id`, `campaign`, `beat`,
  `app_version`, `at`, the `input` that wrote the beat (the same record
  `remember_input` keeps — the plan's messages, what every slot wrote and answered, the
  tells, the brief — so each line stands alone), the slot's own call as `prompt` (without the correction
  appended), the rejected slot text and its raw reply, the `clashes` (sentence, tell, the
  clashing words, the second read's verdict), `reason`, the remade text and raw reply,
  `remade_passed`, the text that `stood`, and `label`: `pair` when the remake passed the
  check again, `rejected-only` when it failed, was not made, or the slot was cut.
- **Export.** `tools/corrections_to_pairs.py` reads it beside the log (`convert_auto`) into
  `pairs.tells.dpo.jsonl` (`{prompt, chosen, rejected}`, pairs only) and
  `examples.tells.kto.jsonl` (`{prompt, completion, label}`: every rejected slot false,
  every remake labelled by its re-check) — TRL's shapes, the sets the player's log already
  feeds, kept apart.
- **The report.** "Report a problem" carries it as `training/auto-corrections.jsonl` when
  "Include the save" is ticked (`report.WITH_THE_SAVE`), an intimate beat's prompt withheld
  as `for_report` withholds it.
- **Never costs the turn.** Appended after the beat is on the transcript; a write that
  fails books an `auto-correction-lost` row in the turn log and the turn goes on.
- **The cap.** The last 200 records (`AUTO_KEPT`). Measured on the bench, a record runs
  45-60 KB (the plan, the slot's own call, the brief; every other slot's call is left out,
  which took it from 108-118 KB), so the file stays near 10 MB. The trim reads the file
  only once it is past 200 KB.

## What the bench found first: two of the three slips were ours

The bench drove non-fight planned beats through the real view endpoints in-process, from
scratch copies of a report save (nothing of it is in the repo). It played 17 lines: a
theft seen and one unseen, going quietly, a bluff, the fine, the arrest, a denial, a plea,
the night in the cell, the walk to the gallows, a commission with its price and its date, a
walk, a wait and a purchase. Each was played 3 times per condition from the same snapshot,
51 beats a condition, on gemma-4-12B, with Ollama shared with other sessions throughout.

Reading every slipped beat's slot drafts beside its page settled it:

- **The scheduled hour.** The narrator wrote "at first light". The read back's hour
  judgement took it for the time now (evening), and its repair rewrote it to the evening
  hour. "Until dawn" became "until evening" the same way.
- **The theft written as failed.** The Sleight of Hand check missed and the engine still
  took the thing: a miss is the theft *seen*. The narrator wrote it snatched; the attempt
  judgement, told "what was tried is not done", rewrote it as failing to snatch.
- **Also ours:**
  - "released from" a place became "held in" it (`beat-moves-player`);
  - "arrive to open their counters" became "already here" (`beat-presence`);
  - the unshown-deed backstop wrote a payment on a turn with no tell.

So three fixes come before the extra read:

1. `beat_verify._hour_told`: an hour claim whose words carry the hour a tell of this turn
   names is the tell, not the clock. It takes only the tell's phrase in the claim's own
   words. The first cut (any part of the day a tell named) cost the gold beat `finalized`
   its true alarm: a refusal "opens at first light" beside "the pre-dawn light is just
   beginning".
2. `beat_verify.attempts_of`: a failed check whose deed the engine did anyway (a thing
   taken from somebody into the checker's hands later that turn) is not asked.
3. **The repair gate** (`agent.tells_gate`, in `GMAgent._repair_sentences`):
   - a rewrite the member would keep is read against the beat's own tells;
   - one that breaks a tell the replaced sentence did not is refused;
   - no backstop cuts that sentence afterwards;
   - it costs a read only when a repair happens.

The engine defect behind the duplicate tell is fixed in `acts_to_ops.table`, in its own
commit.

## Measured

**Blind scoring.** Four scorers (separate agents, conditions hidden, items shuffled) used a
fixed eight-code rubric:
- outcome contradicted;
- wrong person;
- wrong thing or sum;
- wrong time;
- invented consequential event;
- omission of a state change;
- invented person or thing;
- position.

Round 1 compared the baseline with the first version (the extra read alone). Round 2, with
a new shuffle, compared the same baseline beats with the final code.

| measure | scorer | baseline | the read alone (v1) | final |
|---|---|---|---|---|
| errors / beat | A | 0.27 (14/51) | 0.25 (13/51) | — |
| errors / beat | B | 0.31 (16/51) | 0.33 (17/51) | — |
| errors / beat | C | 0.29 (15/51) | — | 0.25 (13/51) |
| errors / beat | D | 0.39 (20/51) | — | 0.22 (11/51) |
| beats with any error | A-D | 25-37% | 25-31% | 22-24% |

The approximate 95% intervals on 51 beats are wide: 0.13-0.60 for the baseline across
scorers, 0.09-0.43 for the final code. **The overall drop is within noise.** What moved,
by item (the scorers agree):

| slip | baseline | final |
|---|---|---|
| theft written as failed (theft seen) | 1/3 beats (+1/3 in v1) | 0/3, and 0/3 again on the final code's own rerun |
| scheduled hour rewritten to the evening | 0/6 baseline, 2/6 in v1 | 0/6 on the final code's rerun (denial x3, plea x3: "at first light" every time) |
| arrivals made "already here" (the wait) | 3/3 (C, D) | 1/3 |
| invented payment at the smith (no tell at all) | 3/3 | 1/3 (chance: nothing reads a beat with no tells) |
| breaking the escort's hold on the walk to the gallows | 3/3 | 3/3, **not fixed** |
| goods given back, or the release, left off the fine | 1-2/3 | 2/3 (omissions, not reachable) |

**Fights.** The same harness played a punch declared, then two rounds against the watch:
9 turns a condition, blind-scored. Baseline 0 errors, final 0 errors. No regression.

**The read itself** (`against_tells`). Run offline over all 102 round-1 pages against one
scorer's labels, with the final prompts:

- **Catches:**
  - the theft written as failed (2/2);
  - the scheduled hour rewritten (1/1);
  - a warrant "by evening" against "by morning" (1/1);
  - a hanged man told to buy supplies (twice, true).
- **Misses:**
  - the escort's hold written broken. The tell offers "wrench free" as a way out; the first
    read flags 5 of 6 and the second read refuses all of them, demonstration or not;
  - arrivals told as "already here";
  - "held" against "let go".
- **Recall:** beat-level, on the labelled errors that have a tell to break, about 4 of 22.
- **False alarms kept:** 6 of 71 clean beats (8%), or about 6 of ~350 sentences.
  - Three are arguably true contradictions the scorers chose not to count (held inside a
    place the tell has them led out of).
  - Every false alarm costs a remake of one slot, and the remade slot is read again.
- **One false-alarm class fixed:** the first prompts flagged "the two guards" against "the
  guardsman and the second guardsman" on 5 beats; the second read's demonstrations took
  that to 0.

**Seconds.**
- **The extra read**, over 51 beats on the final code:
  - on a clean planned beat: median 2.5 s, p90 4.8 s;
  - the maximum, with a remake and its re-read: 26.6 s;
  - on a fight turn (several narrated beats): 1.6-14.5 s.
- **The repair gate** read 10 times in 51 beats.
- **Whole-turn wall time** did not move measurably: median 31.6 s baseline, 32.3 s v1,
  33.8 s final. Everything else in the turn, and Ollama contention, dominate it.

**Live**, on the running server with a scratch data dir and the kit's driver over HTTP:
- **The theft** (a missed Sleight of Hand, seen): written snatched and witnessed. 40 s.
- **The fine**: the six gold written paid. The goods going back and the release were left
  out (an omission). 51 s.
- **The sentence and the plea**: both "hanged at first light". 44 s and 39 s.
- **The commission**: the smith's spoiled work was written as the metal flowing "into a
  usable shape". **The read missed it.** 33 s.
- **The price**: "I agree to his price and pay" made no op at all, and the unshown-deed
  backstop wrote the coins onto the smith's bench. 38 s.

## Left, and the owner's calls

- **Omissions, and inventions with no tell, are out of reach of a check against tells.**
  - Examples: the goods going back, the release, a payment on a turn the engine decided
    nothing.
  - These are the read back's `_omissions` (trades only today) and the engine's (the
    commission's price and payment have no op).
- **The second read refuses true clashes that copy the tell's words.** "Wrench free" is in
  the tell as an option. Lexical overlap is the documented weakness of LLM judges (Luo et
  al. 2023). It is not solved here.
- **Our other repairs still wrote slips**, and the fine and the commission had engine
  defects behind them. Fixed in the next lane: see "The repairs that wrote slips" below.
- **The switch.** Removed (the owner's ruling, 2026-11-02): always on.

## The repairs that wrote slips (2026-11-02/03)

The owner, 2026-11-02: "Fix them, then cut." Each was reproduced first, from the bench's own
turn logs (the truth-checks rows name the member, the fact it was given and the rewrite).
Every one had the same cause: the repair or backstop read one engine fact and nothing else
the beat's tells said, or read the wrong engine record. So each now reads the tells or the
record it should have.

| slip | why it fired against the tells | the change |
|---|---|---|
| `beat-moves-player` wrote "held in the guardhouse" after "is let go" | its fact said only "did not move"; the rewrite was shown nothing else | every repair is shown the beat's tells in front of its fact (`agent._repair_tells`, `_truth_repair_messages`); the move fact says "let go and free" when custody ended this turn (`Facts.let_go`) |
| the escort's "lead you out of the guardhouse toward the market" flagged as a move, rewritten "hold you" | the trial's walk leaves the scene at the hold; the tell leads the player out | on the escort's walk (`trial.custody` stage `walk`) no move claim is judged (`Facts.led`) |
| `beat-presence` wrote "already here" over "comes to the market" | the clock's arrival records (`arrives`, `back`, `leaves`) were not in its list | `beat_verify._COMINGS` |
| the hour repair wrote "the early morning" over "through the night" on an 816-minute wait | judged against the hour the clock stopped at | judged against every hour the clock passed this turn (`Facts.passed`) |
| "no time passed this turn" cut the cell night and wrote the rest's refusal | a refused rest was asked before the clock | the clock first: 60 minutes or more passed is time that passed (`time_kept._still`) |
| the unshown-deed backstop wrote a payment no op made | a hand-over the engine moved nothing for was still owed | not owed (`narration.moved_nothing`; a gesture still is) |
| "accepts the commission for 1 gold, 4 silver" and the fine's "accepts your payment" cut as no sale; the first rewritten "for 0 gold" | coin for work or a fine was not a payment to the trade judgement | a commission's `cp` and a fine's `paid_cp` are payments |
| "the damp, cramped cell" rewritten "guardhouse" | the reader files a cell with the cellars | with the player held at the hold, underground is a setting there |

Two engine defects behind them:

- **Paying the fine was a bribe.** "Pay the fine" at the plea was planned as a give of 6 gp
  to the officer, and `trial.bribed` pushed it back beside the sentence's own payment. A give
  of the player's to one of the law while a fine is to come (`acts_to_ops.fine_pending`:
  questioning or plea, no death sentence) is dropped (`fold_the_fine`, in `apply` and again
  after the check injectors); the reading's "pay the fine" builds nothing and refuses
  nothing. The sentence takes the fine, once. A condemned prisoner's coin is still the
  jailer's bribe.
- **A price agreed made no op.** `rules/commission.py` charges when the job is taken, so a
  price agreed is the job taken at the engine's price. Each ask is recorded on the counter's
  own record (`commission.asked_of`: spoiled, unpaid or taken). A `sell` with nothing named,
  or a `give` of no thing or of coin with no amount, at a keeper asked for work today builds
  `commission` with `agree` (`acts_to_ops._agreed_work`), once a keeper a turn; the plan's
  coin beside it is dropped. Agreed after the work is paid: "already has the work in hand
  and paid for … Nothing more is owed", and nothing is taken.

Tests: `tests/test_repairs_write_no_slips.py`, one per slip.

### Measured (2026-11-03)

The same bench (17 non-fight lines x 3, scratch copies of a report save, gemma-4-12B, the
tells check on in both conditions), baseline 37260c8e against this lane. Two items were
rerun: `agree` from a snapshot the new code made (the old one was made by code that kept
no record of the ask, so no code could agree it), both conditions; `fine` on the final
fold. Ollama was shared with another session benching on CPU.

The repairs' own notes, read off the turn logs (not blind):

| item (3 runs) | baseline | after |
|---|---|---|
| night in the cell: move repair over the escort's tell | 3 | 0 |
| the wait: presence repair "already here" | 3 | 0 |
| the wait: hour repair | 1 | 0 |
| the fine: the give read as a bribe ("pushes it back") | 2 | 0 |
| the fine: a true payment cut as "no sale" | 1 | 0 |
| agree: an op at all | 0 | 3 (engine correct; see below) |

Blind, two scorers (agents, conditions hidden, 102 items shuffled, the eight-code rubric):

| scorer | baseline | after |
|---|---|---|
| E | 19 / 51 = 0.37 a beat (beats with an error 31%) | 11 / 51 = 0.22 (22%) |
| F | 23 / 51 = 0.45 (35%) | 13 / 51 = 0.25 (25%) |

The approximate 95% intervals overlap (0.21-0.67 baseline, 0.09-0.43 after, across both
scorers); per scorer the drop is not significant at 5% (sign test on the error counts,
p about 0.1-0.15). The scorers agree on where it fell: the night in the cell 3 -> 0, the
fine 3 -> 0, the wait 5-6 -> 1. Left: the walk to the gallows 2-3 -> 3 (the escort's hold
written broken, unchanged), and `agree` 3 -> 2 — the engine now refuses a second payment
("pays nothing more") and takes nothing, but the narrator still writes the player paying
on 2 of 3 pages; live, the tells check caught "you hand over the coins", and its remake
"you agree to his price and pay the fee" passed the re-read.

Fights (punch, two rounds against the watch, 9 turns a condition, one blind scorer): 3
errors baseline, 5 after; 6 of the 8 are the same omission in both (no warrant named on
the turn the fight starts). The other two, after: a guardsman knocked out a punch early,
and a fourth Grippli invented. Within noise at n = 9.

Seconds a turn (wall, in-process): non-fight median 34.1 s baseline, 33.6 s after (p90
56.3 -> 44.0); fight median 105 s -> 85 s. Nothing measurable added.

### Follow-ups (2026-11-03, the coordinator's calls)

- **An initialled name** (`narration.name_pattern`). "Corvin T." never matched whole (`\b`
  cannot follow a full stop), the first name did, and the engine's line reached the page
  as "Pallo Farrow hits you S. With the mwk guisarme" (1 fight turn baseline, 3 after).
  `pc_to_second_person`, the third-person check and the misgender window share one
  pattern; a stop that ended the sentence stays. Follow-up fight round and live: "Pallo
  Farrow hits you with the mwk guisarme."
- **Released, the player walks out** (`trial.walk_out`): fined, talked out, let go for
  want of proof or cowed, the party is put at the town's own place outside the hold (the
  place an escape comes out at: never the hold, the gallows or the gate), the talk with
  the watch ends, and the tell says where ("… walks out of the guardhouse to the great
  square"). The read back's "did not move" no longer fights the release.
- **Every repair is gated** (`GMAgent._tells_refuse`, `_turn_gate` set per beat in
  `_groom`): outcome claims, state claims, the wrong actor, the misnamed, the deed shown,
  the blow shown and the answer. Only the sentences a repair added are read; the ones it
  removed only when an added one clashes. Refused, each takes its own fallback (cut, the
  engine's line, or the beat as written). Cost: on the 120 bench turns of the first
  measurement these seven repairs wrote on 5 (outcome claims 2, deeds 3), so the gate
  is asked on about 4% of turns; on the 12 follow-up turns it was asked once and
  refused once (a deed passage "… reach into your pouch" beside "pays nothing more").
- **A remake against a refused tell** (`planned._tells_kept`): the remake is told the
  engine REFUSED it ("did not happen: write nothing that has it happen"), and each of its
  sentences is put to the fact-first second read against the tell it was remade for
  (`faith.second`). Follow-up `agree`, 3 runs: no page has the player pay (baseline 3 of
  3); one remake still clashed and was cut, two passed.
- **The escort's walk** is left as it is: no move claim is judged while the player is
  being led to the gallows (`Facts.led`).
- **A scheduled hour from the engine's data** (`beat_verify._hour_told`): the word list
  matched against the page is gone. A death sentence (verdict and sentence) and an escort
  job record the minute they are set for (`scheduled`); an hour claim in that part of the
  day is the appointment. What it gave up: a page saying dawn is breaking now, on a turn
  that sets something for dawn, is not judged either. Opening hours carry no `scheduled`,
  so the gold beat `finalized` keeps its alarm.

Follow-up bench (agree from the new snapshot, the fine, and a bluff at questioning; 3
runs each, base 37260c8e and after): `agree` — base 3 of 3 pages pay with no op, after 0
of 3; the fine — base 1 bribe pushed back and 2 refused gives told on the page, after 0,
each run walking out to the great square; the bluff — neither condition rolled it (the
plan made it a `say`), so it was silence and a verdict in both, not a release. Seconds:
non-fight median 33.1 s base, 32.3 s after; the fight round 80 s median (3 turns).

## Who may refuse a clash (2026-11-03)

A bench of the checkers (102 labelled beats, 22 contradictions a tell can catch, pinned to
their sentences by hand) found that the second read threw away more true catches than false
alarms: both reads caught 5 of 22, the first read alone 11 of 22. The owner, 2026-11-03:
test the first read alone on full turns before 0.2.26. The worry was the page: about twice
as many good beats remade, and every remake that fails twice is a cut.

`PATHFINDER_GM_TELLS_VETO` (a bench's switch; the check itself stays on with no Settings
switch) picks who may refuse a first-read clash: `second` (the second read, as shipped),
`none` (nobody), or `echo` (the second read, except on a clash that repeats two of the
tell's own content words — `beat_verify.echoes_tell`; names and function words do not
count, and there is no stemming, so "guardsmen" is not "guardsman").

### Offline, the 102 beats

Two recorded runs of the first read (the second in brackets); a clash's second-read verdict
is the run's own.

| gate | caught (of 22) | clean beats flagged (of 71) |
|---|---|---|
| both reads, as shipped | 5 (5) | 5 (6) |
| first read alone | 11 (12) | 12 (11) |
| echo: the second read refuses only a clash sharing fewer than two tell words | 9 (9) | 5 (7) |
| echo with one shared word enough | 10 (10) | 5 (7) |
| the reverse: refuse only a clash that does share tell words | 6 (7) | 12 (10) |
| the second read alone on every sentence and tell (the checker bench) | 13 | 22 |

The second read's refusals were of two kinds. Right: people counted differently ("the two
guardsmen" for "the guardsman and the second guardsman", 5 clean beats), sharing no word
with the tell. Wrong: "you wrench your arms free from their grip" beside a tell offering
"slip it or wrench free" as a way out (4 of 4 refused, "tells it"), the lexical-overlap
weakness. The echo rule is fitted to these beats, so the full turns are its held-out test.

### Full turns

In-process through the real view endpoints from scratch copies of a report save, on
gemma-4-12B, every item played under all three vetoes back to back so contention fell on
them alike. Round 1: the non-fight bench (17 lines x 3) and the fight round (punch, two
rounds against the watch, 3 x 3). Round 2: the five lines the check acted on in round 1
(the seen theft, going quietly x 2, the gallows walk, the price agreed), 3 more runs of
`second` and `none`. Blind scoring, two scorers a round, conditions hidden, items shuffled,
the eight-code rubric plus a `Q` tag for a page that reads broken (a dangling reference, an
incoherent jump, a fragment, too thin to tell what happened).

| errors (scorer, scorer) | second | none | echo |
|---|---|---|---|
| round 1, non-fight, 51 beats | 9, 7 | 8, 6 | 8, 6 |
| round 1, fight, 9 turns | 4, 4 | 7, 7 | 4, 4 |
| round 2, 15 beats | 5, 6 | 1, 1 | — |
| `Q` pages, round 1 non-fight | 10, 11 | 8, 8 | 12, 12 |
| `Q` pages, fight / round 2 | 1, 1 / 4, 5 | 1, 1 / 4, 4 | 1, 1 / — |

Bootstrap 95% intervals on round 1 non-fight overlap throughout (0.04-0.29 errors a beat
across conditions and scorers); paired sign tests p = 1.0 in round 1, p = 0.06-0.12 in round 2. **Over the
whole bench the three are within noise.** Read slot by slot, what the veto itself changed:

- **The escort's hold written broken** on the walk to the gallows: shipped on 6 of 6 runs
  with the second read (both scorers, E8, and `Q` where the freed man is hanged anyway), 0
  of 6 with the first read alone, 2 of 3 under echo (missed where the clash quoted only one
  of the tell's words, "wrench").
- **A false alarm that cost a page**: one fight turn under `none` — "nearly unconscious"
  before the blow that knocks him out was flagged, the remake failed, and the cut took the
  first of the two blows (both scorers: E6 and `Q`). The other none-only false alarms (a
  snatch told as a snatch, people counted as "the three of them") were remade or lost a
  sentence of colour with no scorer mark.
- **A true catch whose remake failed twice**: the act slot takes the engine's own line. On 2
  of the 6 `none` gallows runs (and 1 echo run) that line reached the page as "You. Is held
  by the escort … slip it (the stranger) or wrench free (a combat manoeuvre)" — both
  scorers `Q`. Two defects, neither the veto's: the bracketed labels (fixed here: the
  fallback drops them, `planned._BRACKETED`) and `narration.destutter` capitalising after a
  name's initial (the player's own name in that save ends in one), which the second-person
  swap then reads as a sentence end — the same "you. Is hanged" turned up on a round-1 page
  the check never touched. That fix is a separate lane.
- The other differences (a smith's spoiled work told as good, a price agreed told as paid,
  the narrator crediting the player's refused shout to an officer) fell on turns the check
  passed or never saw: narrator variance.

Remakes, by the turn logs:

| | second | none | echo |
|---|---|---|---|
| round 1 non-fight: remakes (passed) | 10 (9) | 10 (6) | 6 (4) |
| fight: remakes (passed) | 0 | 2 (1) | 1 (1) |
| round 2: remakes (passed) | 4 (3) | 9 (7) | — |

**They did not double.** The none-only false alarms were 4 in round 1, 2 in the fight and 1
in round 2 — about one in ten beats — and more of none's remakes fail (the escort's hold is
hard to unwrite: the remake keeps reaching for "wrench free").

Seconds a turn (wall, in-process): non-fight median 31.2 s second, 31.1 s none, 32.0 s echo
(p90 36.5, 35.8, 37.0); the check's own share median 2.5, 2.3, 2.3 s (p90 4.8, 4.0, 3.8). The
fight medians (96, 73, 80 s on 9 turns) move with what the fight did, not the check. Round 2:
32.2 s and 31.8 s. **Nothing measurable.**

### The decision

The first read alone (`TELLS_VETO = "none"`): the one slip class the veto decides went 6 of
6 to 0 of 6, the price was one fight page that lost a blow, the remakes did not double, and
the time did not move. The whole-bench error counts do not separate the conditions, and
that should be said with it: the case rests on the mechanism and on the gallows item, not
on a significant drop overall. Echo was not taken: in between on the item that matters, and
fitted to the offline beats.

Tests: `tests/test_tells_veto.py` (the three vetoes, what echoes a tell, the default, the
fallback's labels).

**Live**, on the running server (the default, no switch set; a scratch data dir and the
kit's driver over HTTP):
- **The gallows walk, twice.** Both times the first read caught "you wrench yourself free
  from their grip". Once the remake passed ("you struggle against their firm grip … as you
  prepare to break free"), 38 s. Once it broke the tell again and the engine's line stood in,
  its labels gone ("slip it or wrench free — or fight") but still opening "You. Is held"
  (the destutter defect above), 50 s.
- **The seen theft.** The first read flagged "shove it into your pocket" beside the tell
  that has the bracelet taken: a false alarm. The remake passed and told the same theft,
  43 s.
- The check's own first read took 2.4-3.2 s a beat.

### Left

- `narration.destutter` and initialled names ("You. Is held"), in its own lane. Until it
  lands, a player named with an initial who triggers the engine-line fallback reads it.
- The escort's hold: the first read now catches it every time, and the remake still fails a
  third of the time. A remake told what the tell offers is a choice, not a fact, may do
  better; not tried.
- The first read misses a payment told in full ("hand over the payment of one gold, four
  silver …") beside "pays nothing more": 2 pages in round 1 (one under none, one under
  echo; the first read is the same in every condition).
