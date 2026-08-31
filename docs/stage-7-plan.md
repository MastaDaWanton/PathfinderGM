# Stage 7 — refusals

The plan of record for stage 7 of `docs/compliance-plan.md`. Every number below was
measured against the code and the twelve real campaigns.

## The rule

From `docs/design-contract.md`:

> **Refuse gracefully, never spiral.** A refusal whose reason the player could not have
> known is a printable Outcome ("Nothing is rolled. …"), never a raised error — the
> intent schema may REQUIRE the op the player declared, and required-op meeting
> hard-refusal is a buried-four-times 502 class.
>
> **Validators name the fix, not the fault.** "No pool called 'fury'. Declare it under
> pools, or name one of: ki, rage" — every message tells the author what to type next.

## The mechanism, read out of the source

An `IntentError` carries a `check` kind, and the kind decides what the turn costs:

| kind | count in `rules/engine.py` | what the agent does |
|---|---|---|
| `legality` | **35** | appends the rejection and **regenerates** |
| `refs` | 26 (+2 `reference`) | **repaired in code** — spawns the people the GM described, drops a trade aimed at nobody |
| `schema` | 10 | appends the rejection and regenerates |

Thirty-five is exactly the audit's "35 resolution-time raises": it is the count of
`legality`. Only `refs` has code repairs; everything else costs a model call and asks
again, to a ceiling of **five attempts** for a player turn and three for an NPC.

### The split that matters: 24 are retried, 10 are a 502 on the spot

AST-verified, the file holds **34** legality raises (the audit's 35 was a string count
that caught one occurrence which is not a raise). They divide by *where they fire*, and
the two halves behave nothing alike:

| where | count | what the player gets |
|---|---|---|
| validation — `_check_legality` 10, `_check_cast` 7, `_check_move` 6, `_check_craft` 1 | **24** | up to five model attempts, then a graceful degrade |
| resolution — inside the `_op_*` handlers | **10** | **HTTP 502 immediately, no retry** |

The resolution ten are `_op_use_item` (×3), `_op_attack`, `_op_forage`, `_op_sell`,
`_op_buy`, `_op_use_ability`, `_op_resource`, `_op_cast`. `play/views.py:_advance` catches
them and returns *"The engine refused the GM's intents: …"* with **`c.transcript.pop()`** —
so the player types a sentence, is told the GM failed, and their own words are deleted
from the record. Its comment says reaching there "means validation and resolution have
drifted apart", which is true and is the point: these are not drift, they are ten ordinary
things a player can try. An empty ki pool is not a bug.

That is the buried 502, precisely located, and it is ten sites rather than thirty-five.

Reproduced with the plainest actions in the game, against a real engine:

    use an item they do not have    LEGALITY -> use_item: Kesst is not carrying '…'
    sell something not carried      LEGALITY -> sell: Kesst is not carrying '…'

A player writes "I drink my healing potion" without one and the app answers 502 and
erases what they wrote. Both fire during `run()` *after* `validate()` has passed, so the
five-attempt retry loop never sees them — there is no degrade, no second try, nothing.

Note what is already right: the messages name the fix. *"Kesst is not carrying 'X'. They
have: …"* is exactly the contract's style. **It is the shape that is wrong, not the
wording** — which is why stage 7 is a mechanical change to ten call sites and not a
rewriting exercise.

Exhaustion in the *validation* half has two ends, and only one of them is graceful:

- the normal path degrades to a `narrate_only` plan with an honest sentence — *"You try —
  '…' — but the moment does not answer"*;
- `gm/agent.py`'s corrections branch ends in a **bare `raise` on the last attempt**,
  which escapes `plan_turn` and reaches `play/views.py` as an HTTP 502. That is the
  buried 502 the contract names, and it is a single line.

## What play actually costs — and how it corrects the premise

Across **353 logged turns** in the twelve real campaigns:

- **73 turns (21%) hit at least one rejection**, burning **186 model attempts** — about
  half a wasted call per turn, and on a local model a wasted call is most of a minute.
- 2 turns degraded to *"the moment does not answer"*.

By kind, and this is the finding that reframes the stage:

| kind | rejections in real play |
|---|---|
| `schema` | **111** |
| `judgement` | 30 |
| `legality` | **4** |
| `refs` | 5 |

**The 35 legality raises are not what play is paying for.** Legality fired four times in
353 turns. The cost is overwhelmingly `schema` — the model omitting a required param:
`move: missing required param(s) zone` ×17, `spawn: … template` ×13, `travel: … biome`
×13.

That does not make the legality class unimportant: when it hits, it is severe (a petrified
character's turn burned every attempt and reached the player as a blank page, which is
what stage 5 fixed at the gate rather than at the refusal). It is severe **and rare**.
Schema is mild **and constant**. Stage 7 should say so and address both, rather than
classifying 35 raises that almost never fire and calling the stage done.

### The worst single message

`move: missing required param(s) zone` — 17 occurrences, and the next attempt fixed it
only **12%** of the time. The model is not learning from it. Compare
`give: missing required param(s) item`, which resolved next-attempt 80% of the time. The
difference is not obviously the message: it is worth finding out what it is, because
seventeen occurrences at 12% is roughly forty wasted model calls in twelve campaigns.

### What actually predicts a schema rejection

Missing-param rejections against how often each op was attempted, over the same 353
turns. Every op with a **0%** rate has no required params at all — an op that requires
nothing cannot fail this way — so the comparison that matters is within the rest:

| op | required param | attempts | rejections | rate |
|---|---|---|---|---|
| `move` | `zone` | 2 | 17 | **89%** |
| `sell` / `loot` | `item` / `from_` | 2 / 4 | 2 / 4 | 50% |
| `spawn` / `travel` | `template` / `biome` | 14 / 15 | 13 / 13 | ~47% |
| `begin_encounter` | `sides` | 8 | 4 | 33% |
| `give` | `item` | 14 | 5 | 26% |
| `check` | `skill` | 20 | 6 | 23% |
| `use_ability` | `ability` | 6 | 1 | 14% |
| `attack` | *(none)* | 53 | 0 | 0% |

The pattern is not which ops are demonstrated in the prompt — `attack` is undemonstrated
and never fails, `travel` is demonstrated and fails half the time. It is **what the
required param is made of**. `ability`, `item` and `skill` are things the player's own
sentence names — "I use blood rage", "I give him the dagger". `zone` is engine
vocabulary: the player writes "I back toward the door" and nothing in that maps to
engaged / near / far. `template`, `sides` and `from_` are the same kind of thing.

So the expensive schema failures are the ones where the model is being asked to supply a
value the fiction never contains — which is a job for code, in the shape `refs` repairs
already have, not for another attempt at the same question. (`move`'s denominator is
small — two successes against seventeen rejections — so 89% is directional, not precise.)

### A hypothesis the data did NOT support

The contract's rule invites the obvious test — do messages that name the fix cost fewer
retries than messages that name the fault? Measured: **32% resolved next attempt for
fix-naming messages against 42% for fault-naming ones**, i.e. the opposite direction.
Small samples and a crude classifier, so this is not evidence the rule is wrong; it is
evidence that "name the fix" has not been shown to reduce retry cost, and stage 7 must not
be justified on a claim its own data contradicts.

## Substages (draft, pending the reconnaissance)

### 7a — the buried 502 stops being reachable
The bare `raise` on the last attempt of the corrections branch. One line, and it is the
only path from a refusal to a blank page.

### 7b — the legality raises that no rewrite can satisfy
Classify all 35 by the plan's own test — **a raise is correct only when a different
intent would have worked**. "attack: no such weapon" is repairable and should raise;
"you are nauseated and cannot attack" is not, and must be a printable Outcome. The parked
items land here: `nauseated`, and the `cast` op stage 6 declined to widen the guard into
precisely because it would have added a fourth op to this pile.

### 7c — the schema class, which is where the turns actually go
111 of 150 real rejections. Whether the answer is better messages, code repair in the
shape `refs` already has, or schema defaults, is an open question this plan should answer
with a measurement rather than a preference.

### 7d — the ratchet
A refusal-shape test in the `_CLOCK_SITES` mould: every `legality` raise is either on the
allowlist with a reason, or is a printable Outcome.
