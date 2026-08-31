# Stage 7 — refusals

The plan of record for stage 7 of `docs/compliance-plan.md`. Written after a five-agent
reconnaissance with a probe stage, and every number below was measured against the code
and the twelve real campaigns rather than estimated.

## The rule

From `docs/design-contract.md`:

> **Refuse gracefully, never spiral.** A refusal whose reason the player could not have
> known is a printable Outcome ("Nothing is rolled. …"), never a raised error — the
> intent schema may REQUIRE the op the player declared, and required-op meeting
> hard-refusal is a buried-four-times 502 class.
>
> **Validators name the fix, not the fault.** "No pool called 'fury'. Declare it under
> pools, or name one of: ki, rage" — every message tells the author what to type next.

## The census, classified

37 explicit non-suspend raises are reachable from `run()`; 35 more sit inside `validate()`'s
five checkers. Against them stand **18 printable refusals** (15 in `rules/engine.py` with
`effects=[]` and a refusal tell, plus 3 added by stage 5 in `play/downed.py`) — the
audit's 13, plus what later stages added.

Classifying the 37 by the plan's own test — *a raise is correct only when a different
intent would have worked*:

| verdict | count |
|---|---|
| **correct to raise** — the model can name another item, target, biome, seller | **22** |
| **must become printable** | **4** |
| **unreachable in the app** | **11** |

The eleven are dead code of one shape: every `"nobody here to X"` fallback that fires when
`scene.pc()` returns None. `Scene.depart` refuses to remove the PC, so none of them can
happen.

**The four:**

| site | what |
|---|---|
| `_op_resource:2485` | an empty or non-existent pool |
| `_op_cast:3251` | out of slots, failing **mid-list** after earlier slots were spent |
| `_op_buy:3168` | the item is not on this merchant's counter today |
| `_op_loot:2693` | the body departed between validate and run |

An earlier pass of this plan said "ten sites". That was the raw count of `legality` raises
inside `_op_*` handlers, before classification; most of them are correct to raise, because
"you are not carrying that dagger" is a refusal a different intent answers. Four is the
number.

## Why a resolution-time raise is strictly worse than a validate-time one

`play/views.py:_advance` catches it **once**, returns HTTP 502 — *"The engine refused the
GM's intents: …"*, with the raw engine string — and calls **`c.transcript.pop()`**. The
player types a sentence, is told the GM failed, and their own words are deleted from the
record. There is no retry: these fire during `run()`, after `validate()` has passed, so
the five-attempt schedule never sees them.

A validate-time raise at least gets the schedule and the graceful degrade at
`gm/agent.py:339`.

Measured cost of the retry path, from the real campaigns: **261 turn records, 557 model
calls, median 8.7s each**. Five burned planner attempts is about 44 seconds and then a
sentence that answers nothing; the degraded line appears 4 times in the real transcripts.

### And one class that is worse than a 502

`_advance` catches `(IntentError, ValueError)` and **not `KeyError`** — while the NPC path
at `views.py:1207` catches all three. There are 31 `self.scene.actors[…]` subscripts inside
`_op_*` handlers, and four are reachable from a list that already passed validation:
travel-then-damage, travel-then-heal, travel-then-check, travel-then-use_item. Verified
directly:

    travel to the forest, then damage c1  ->  KeyError('c1')

Django has no custom exception middleware, so that is a **500 with a traceback**, not a
502. Only `_op_attack` carries the defensive re-check that converts it to an `IntentError`.

### The mid-list case, measured

Six `cast` intents in one list **pass** validate against two prepared slots, because
`_check_cast` reads the pre-run count and checks the whole list before running any of it.
The third raises at `engine.py:3251` — by which time two slots are gone and two fireballs
have landed. The 502 throws all of it away.

Do **not** fix this by making validate simulate the list. That is a second resolver.

## What play actually pays for

Across **353 logged turns**: 73 (21%) carried at least one rejection, burning **186 model
attempts**. By kind:

| kind | rejections |
|---|---|
| `schema` | **111** |
| `judgement` | 30 |
| `legality` | **4** |
| `refs` | 3 |

The legality four were: two can-act refusals (both about an **NPC**, both retried fine),
`rest: there is a fight going on`, and `attack: a trip needs a target`.

So the buried-502 class is **severe and rare**; the schema class is **mild and constant**.
Stage 7 must address both, and must not be justified as fixing the thing that fires four
times in 353 turns.

### The `nauseated` hole is real, and has never fired

Sweeping all 31 shipped conditions through `downed.state_of` and `validate`, `nauseated`
is the **only** condition where the turn gate calls the PC playable and the guard then
refuses their ops. Every other blocking condition already returns `held` / `dying` /
`stable` / `dead` and never reaches the model — which is what stage 5 fixed.

Over 261 real turns the guard fired exactly **twice**, both times about an NPC, both
retried successfully on the next attempt. **Zero PC firings.**

And the reason those two fired at all is worth more than the hole: `gm/prompts.py`'s
`scene_brief` names hit points, gender, heritage, class, level and class abilities — and
**never names a single condition**, on the PC or on anyone else in the scene. Probed with
a nauseated PC and a shaken NPC, the words "nauseated", "shaken" and "condition" are all
absent. The NPC-turn prompt *does* say "their conditions are: shaken". So on the player-turn
path the model is **structurally unable to know** that c1 is dead, and is then corrected
for not knowing.

## The contract's own example sentence is unimplemented

The design contract's worked example of a good message is verbatim:

> "No pool called 'fury'. Declare it under pools, or name one of: ki, rage"

What the app prints, from `engine.py:2485` via `sheet.py:2018`, is `resource: no fury to
spend.` — **the identical sentence whether the pool is empty or has never existed.**

And the same mechanic already has a correct answer twelve hundred lines away:
`_ability_refusal` refuses an unaffordable ability *printably* — "Blood Spike costs 2 from
the blood pool and Kesst Vayr has 0." — with a docstring naming "the untrained-check /
busy-forage shape". One mechanic, two answers, and the good one is the one nobody reused.

Two more name the fault rather than the fix: `ability_damage: "no such ability 'zzz'"`
does not list the six abilities, and `use_ability: … has no ability called 'x'. Their paths
are none.` names the paths instead of the ability names — while `gm/prompts.py` already
computes exactly the list it should print.

### A hypothesis the data did not support

Do messages that name the fix cost fewer retries than messages that name the fault?
Measured: **32% resolved next attempt for fix-naming messages against 42% for
fault-naming** — the opposite direction. Small samples and a crude classifier, so this is
not evidence the rule is wrong; it is evidence stage 7 must not be *justified* on a claim
its own data contradicts.

### What does predict a schema rejection

Missing-param rejections against attempts, same 353 turns. Every op with a **0%** rate has
no required params — so the comparison is within the rest:

| op | required param | attempts | rejections | rate |
|---|---|---|---|---|
| `move` | `zone` | 2 | 17 | **89%** |
| `sell` / `loot` | `item` / `from_` | 2 / 4 | 2 / 4 | 50% |
| `spawn` / `travel` | `template` / `biome` | 14 / 15 | 13 / 13 | ~47% |
| `give` | `item` | 14 | 5 | 26% |
| `check` | `skill` | 20 | 6 | 23% |
| `attack` | *(none)* | 53 | 0 | 0% |

It is not which ops the prompt demonstrates — `attack` is undemonstrated and never fails;
`travel` is demonstrated and fails half the time. It is **what the required param is made
of**. `ability`, `item` and `skill` are things the player's own sentence names. `zone` is
engine vocabulary: the player writes "I back toward the door" and nothing in that maps to
engaged / near / far. `template`, `sides` and `from_` are the same.

The expensive failures are where the model is asked for a value the fiction never
contains — work for code, in the shape the `refs` repairs already have. (`move`'s
denominator is two; 89% is directional, not precise.)

## Substages

### 7a — the 500 and the 502 stop being reachable
`_advance` catches `KeyError` like the NPC path already does, and the four
travel-then-anything cases get the defensive re-check `_op_attack` already carries. One
handler, one helper.

### 7b — the four refusals become printable Outcomes
`_op_resource`, `_op_cast`, `_op_buy`, `_op_loot`. `_ability_refusal` is the worked
example to copy, not to reinvent. The mid-list cast keeps what it already spent and says
so; validate must not be taught to simulate.

### 7c — the messages that name the fault
The contract's own `fury` sentence, implemented, with the empty-pool and no-such-pool
cases separated. Then `ability_damage` and `use_ability` printing the lists they already
have to hand.

### 7d — the brief names conditions
The player-turn brief says what state everyone is in, so the model stops being corrected
for not knowing. This is the root cause of both real legality firings, and it is a prompt
change with a mechanical check behind it, not a prompt rule.

### 7e — the schema class
111 of 150 real rejections. Params made of engine vocabulary get inferred or defaulted in
code; params the fiction supplies stay the model's to write.

### 7f — the ratchet
Every `legality` raise reachable from `run()` is on an allowlist with a reason, or is a
printable Outcome — the `_CLOCK_SITES` shape. Plus a test that `_advance` catches
everything the NPC path catches.
