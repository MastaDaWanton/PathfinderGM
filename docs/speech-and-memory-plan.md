# Plan: speech versus action, and the memory policy

2026-09-08. One plan for two workstreams, because they collide in the same file and
the order matters. The reasons live in `docs/speech-vs-action.md` and
`docs/retrieval-and-memory.md`; the memory design lives in `docs/memory-policy.md`.
Nothing here is built.

## Why they are one plan

They are independent in the code. Speech lives in `gm/judgement.py` and the op
vocabulary; memory lives in the prompt assembly. But a `say` op adds an entry to the
sampler enum and probably a worked example, and every worked example is charged
against the same context budget the memory work exists to control. Out of combat the
examples already cost 11,522 chars of a 25,132-char floor.

So the budget comes first. Otherwise we spend it without seeing the bill.

## The measurements this plan is answering

| What was measured | Result |
|---|---|
| Speech lines through `wants_a_fight` | 3 of 9 wrongly open a fight |
| Ops in `rules/intents.py` that carry speech | none of 42 |
| Turn at which the prompt overflows | 46 out of combat |
| What overflow eats first | the worked examples, until turn 57 |
| What it eats after that | one exchange of real play per turn, forever |
| The scene brief | 4,059 to 5,812 chars, bounded |

---

## Workstream A: speech versus action

### A1. Quarantine what the player quoted, before any detector runs

The bug is that `wants_a_fight` scans the whole raw line and its "who is swinging"
test is satisfied by the word "I" inside the quotation. Every tradition solves this
the same way: once a span is known to be speech, it is an opaque payload that no
action grammar ever sees again.

One function, in `gm/judgement.py`, that blanks quoted spans and the complement of a
speech verb, and every detector over player text reads the redacted line instead of
the raw one. Grep for every detector; the file has at least two violence regexes and
a musing guard that is really a verb blacklist doing this job badly.

Test docstring records the measurement: three of nine speech lines opened a fight,
one of them "I tell the guard 'put down your sword, I do not want to fight'".

**Fixes playtest item 2. No prompt cost. Smallest change with the largest effect.**

### A2. Give speech an op

There is no speech op among the 42, so speech can only land in `narrate_only`, which
is why it falls through to the holding line far more often than action does.

- `say` in `OPS` in `rules/intents.py`: who is addressed, and the words.
- A handler and a tell in `rules/engine.py`.
- An entry in the sampler enum built at `gm/prompts.py:1455`.

No roll. Pathfinder 1e already settles this: speaking is a free action, and more than
a few sentences is beyond it. The op exists to give speech a door and a tell, not to
make it cost something.

**Addresses the root of playtest item 5. Costs prompt budget, so it lands after the
budget is under control.**

### A3. Never answer speech with silence

The holding line in `play/views.py` is a parser-error floor being used as a
conversation response. TADS guarantees a lowest-priority catch-all so an
unanticipated topic still gets a designed in-character non-answer; Façade has a
global deflection tier that runs regardless of which beat is active.

A speech turn that produced nothing gets an in-character non-answer that acknowledges
it was heard. A test asserts a speech line never reaches the holding line.

**Fixes the other half of playtest item 5.**

### A4. Mark actions and speech, and colour them

Asterisks for action, quotes for speech, coloured differently in the interface. The
convention is decades old and universal; what could not be sourced is any evidence it
improves model behaviour, so it is justified as readability and as a signal, not as a
quality claim.

The signal is the point: a player who marks their speech has told us where it is, and
A1's quarantine can simply believe them.

Same change fixes the suggestion chips, which currently read as advice from outside
the fiction. They should be the player's own line, first person, marked the same way.

**Fixes playtest item 6.**

### A5. Directed social attempts stay checks

Ordinary talk is free. Persuading, deceiving or threatening is a timed action with a
difficulty, which the engine already resolves as a skill check. The line is drawn in
the Core Rulebook, not by us: one minute to change an attitude, one or more rounds for
a request, a standard action to feint or demoralise in a fight. Mostly a routing
question once A2 exists.

---

## Workstream B: memory

Staged in full in `docs/memory-policy.md`. In short:

- **B0.** One window constant, shared with `gm/client.py`. The budget is the window
  minus the largest completion minus a margin, because the context holds both.
- **B1.** Pack the history ourselves at `gm/prompts.py:933`, newest first, and log
  what was dropped. Protect the examples, which the blind oldest-first rule kills
  before it touches any play.
- **B2.** A ledger, built mechanically from the tells already stored in `turn_log`,
  with no model call and nothing to invent.
- **B3.** One small model call at eviction, for what people said, which the engine
  does not own.
- **B4.** Promote anything recurring onto cards and tags, where the brief regenerates
  it for free.
- **B5.** Recall. Only if B4 fails to hold it. Probably never.

---

## The order

1. **B0 and B1.** Removes the largest silent failure and makes every later prompt
   change measurable against a known budget.
2. **A1.** Small, self-contained, no prompt cost, fixes a live bug.
3. **A3.** Small, and it stops the most visible symptom of speech having no home.
4. **B2.** The ledger, mechanical.
5. **A2.** The `say` op, now that its cost in the budget is visible.
6. **A4.** Marking and colour, and the chips.
7. **B3 and B4.** The distillation call, then promotion.
8. **A5.** Social attempts as checks.
9. **B5.** Only if measured to be needed.

## How the playtest list maps

| Item | Covered by |
|---|---|
| 1, cheat granted no experience | Neither. Its own fix. |
| 2, a fight opened on a self-description | A1 |
| 3, the damage card printed a bonus twice | Neither. Its own fix. |
| 4, non-answers then drift to the docks | B1, then A3 |
| 5, speech fails where action works | A2 and A3 |
| 6, chips read as advice | A4 |
| 7, a named person never introduced | Neither. Scheme proactivity. |

## Risks worth stating now

- **A2 may over-route.** A new op in the sampler enum is a new thing the model can
  reach for, and it may reach too often. `tools/narrator_audit.py` and its 196 of 200
  baseline is the instrument.
- **A1 must not swallow real declarations.** "I tell him I will kill him where he
  stands" is a threat, not an attack, and 1e agrees: that is Intimidate. Speech about
  future violence is not violence. The test suite should pin that both ways.
- **Every example costs budget.** Any new worked example added for `say` is charged
  against B0's budget and should be measured, not assumed free.
- **Do not let B2 restate a card fact.** A card already holds it, and a second copy is
  the parallel store the second law forbids.

---

## What was built, 2026-09-08

| Step | State |
|---|---|
| B0, one window constant | done. `prompts.NUM_CTX`, read by `gm/client.py` |
| B1, pack the history ourselves | done. `prompts.pack`, reported into the turn log |
| A1, quarantine quoted speech | done. `judgement.redact_speech`, nine detectors |
| A3, never answer speech with silence | done. `narration.unanswered_speech` |
| B2, the ledger from tells | done. `gm/ledger.py`, saved on the campaign |
| A2, the say op | done. `say` in `OPS`, `_op_say`, `inject_say` as a declarer |
| A4, marking, colour, chips | done. `said()` in the page, 51 suggestions rewritten |
| B3, one distillation call | **superseded, not needed** |
| B4, promotion | not done, and it needs live data first |
| A5, social attempts stay checks | done, as a briefing line |
| B5, recall | not done, and correctly so |

**The token ratio was measured rather than guessed.** `tools/token_ratio.py` asks the
configured model for one token and reads `prompt_eval_count`. On
igorls/gemma-4-12B-it-heretic the worst of three real prompts was 3.79 characters per
token, so `CHARS_PER_TOKEN` is 3.6 and the prompt budget is 51,782 characters against a
16,384-token window, leaving 1,400 tokens for the answer and 600 of margin. Note that
the configured narrator is that gemma tune, not the llama3.1:8b named in the earlier
research briefs.

**B3 turned out to be unnecessary, which is the good kind of surprise.** The plan
reserved one model call at eviction for the part the engine does not own: what people
actually said. Once speech had an op of its own, the words were in an effect the engine
had written, so the ledger keeps them mechanically. No latency on the turn, and nothing
to hallucinate. A promise made forty turns ago is the most useful thing a ledger can
hold and the thing a summariser would most likely have got wrong.

**Two bugs the tests found while being written.** `ledger.keep` returned a truncated
copy instead of truncating in place, so the entry cap read correctly and enforced
nothing on any caller. And `call_prose_messages` used to build the turn prompt and then
replace its system message and its final user message with larger ones, so the tells and
up to two earlier beats arrived after the budget had already decided the prompt fitted.

**One thing found that was nobody's plan.** The test suite reads the player's live house
rules from their real data directory, and `.test-data/` persists between runs, so an
earlier session leaving `point_buy: 0` there made `test_the_point_budget_is_a_wall` fail
on a clean checkout of the code. A suite whose result depends on how the player last set
their game is not a gate. Fixed in `tests/conftest.py`, in the same shape as the
CAMPAIGN_DIR leak fixture beside it.

## Standing rules for all of it

The three laws. Tests name the measurement that made them exist. Run the whole suite,
not the file touched. Verify in the running app, not only in tests. Rebuild the
packaged exe and prove it before calling packaging work done. The playtest bug list
stays on hold until it is handed over.
