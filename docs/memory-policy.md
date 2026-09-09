# The memory policy

Design note, 2026-09-08. Follows `docs/retrieval-and-memory.md`, which found that
what looks like a retrieval problem is a context-budget problem. Nothing here is
built yet. No code has changed.

## The problem, stated exactly

`gm/prompts.py` builds every turn as: one system message holding the instructions and
the scene brief, then the few-shot examples as user and assistant pairs, then
`messages.extend(history)`, then the player's line.

`history` is a list on the campaign that only ever grows. Nothing trims it. When the
total passes the 16,384-token window, Ollama removes messages from the front until it
fits, preserving system messages, and says nothing to us about having done it. So the
first thing we lose is the few-shot examples, and after that the oldest play.

Measured 2026-09-08 against the shipped Pangrella export, building a real campaign in
memory and calling the real `scene_brief`. Token figures are chars divided by four,
an estimate, not a tokeniser count.

| The scene brief | Chars |
|---|---|
| A fresh campaign, turn one | 4,059 |
| A market with ten people in it | 5,080 |
| That same market once a fight has opened | 5,080 |
| Twenty-two cards on the table, twelve facts written to each | 5,812 |

The brief is small and it stays small. It does not grow when a fight opens, and
piling twelve quests with twelve facts apiece onto it cost 732 chars, because the
card system already enforces its own budget. The brief is not the problem.

| The whole assembled prompt | Out of combat | In combat |
|---|---|---|
| Floor: instructions, examples and brief, no history | 25,132 chars | 17,477 chars |
| Room left inside a 16,384-token window | 40,404 chars | 48,059 chars |
| Turns of play before it overflows | 44 | 53 |

The turn counts assume 900 chars of player line plus beat, which is what a beat
measures. The out-of-combat floor is larger because its few-shot examples are 11,540
chars against the fight's 3,079. Those examples are the single largest item in the
prompt after the history itself, larger than the brief.

## The idea in one line

**Never remember what the engine can regenerate; remember only the fiction; and do
the cutting ourselves, on a stated budget, so we know what was dropped.**

Most of what a memory system would carry, we do not need to carry, because we hold it
as live state and rebuild it from scratch every turn. That is a structural advantage
over every chat-shaped memory design in the literature, and it means our memory can
be small.

---

## Four tiers

### Tier 1. Regenerated, not remembered

The scene brief already rebuilds the world name and premise, the place and its exits,
who is present with their refs, the cards and quests, conditions, attitudes and usable
abilities. This tier cannot go stale, cannot contradict the engine, and costs one
rebuild per turn. Its own docstring already calls it a budget rather than a dump.

**The policy rule: anything that could live here belongs here, not in history.** When
the narrator needs a fact, the fix is a line in the brief or a tell, never a hope that
an old turn survived in the window.

### Tier 2. The near window

The last few turns, verbatim, because recent prose is what holds voice and thread. It
is bounded in tokens, not in turns, since a fight beat and a market beat are not the
same size. Oldest goes first, cut by us before the call rather than by the server
during it.

### Tier 3. The ledger

What falls out of the window is distilled once into short entries and never
re-summarised. The research is unambiguous here: recursive summarisation measured
worst of every approach tested, at 35.3% against 78.6% for periodic summaries and
94.4% for full context, and the documented cause is detail lost through repeated
re-compression. So we compress each stretch exactly once and leave it alone.

Two things make our ledger cheaper and safer than the usual design.

**Most of it needs no model call.** Every resolved turn already emits tells, which are
one-sentence statements of what the engine decided, and `turn_log` holds every roll.
A factual record of an evicted stretch can be assembled mechanically from tells. A
mechanically assembled record cannot hallucinate, which is the failure SillyTavern
documents for its own summariser.

**The model is only needed for the part the engine does not own.** What an NPC
claimed, what was promised, what the player said they intended. That is a small, well
scoped call, made at eviction rather than every turn, and it stays off the critical
path of a turn that already costs 25 seconds.

**No entry carries a number or a mechanic.** That is the third law. A ledger line
saying the player took nine damage is a second store of a fact the engine holds, and
the moment it disagrees with the sheet we have the near-miss context that the noise
research measured as the worst thing you can put in a prompt.

### Tier 4. Recall, only if the ledger outgrows its budget

Pull a few old entries back when they are relevant now. Keyed on what we already
have, which is place ids, actor refs, quest card ids and the tag vocabulary, not on
embeddings. This is the shape every roleplay tool converged on, and we happen to have
built the key mechanism already. This tier stays unbuilt until the ledger actually
overflows.

---

## Promotion beats remembering

Before anything reaches the ledger, ask whether it has a structured home. We already
have the hooks:

- `knows.*` tags for what the player has learned, granted through the applicator
- quest cards and objectives for promises and tasks
- card facts, through `cards.touch`, for what a card remembers
- scheme instances for authored plots

A thing promoted into one of those is regenerated in tier 1 forever after, is visible
to the player in the interface, and is enforced by the same laws as everything else.
The ledger is only the overflow for fiction with no structured home yet, and if the
ledger grows fast that is a signal we are missing a card type, not that we need a
bigger ledger.

---

---

## What this does to quests

Almost nothing, and the reason is worth stating plainly: **the card system in
`rules/cards.py` is already an implementation of this policy, scoped to situations.**
The design note above proposed things that already exist there.

- **A budget.** `active()` takes `BUDGET_CHARS = 1400` and stops adding cards when it
  is spent. Measured above: twenty-two cards with twelve facts each cost 732 chars.
- **Keyword triggering.** Cards score on whether their keys appear in a scan window of
  the last `SCAN_BEATS = 3` beats, most hits first. This is a lorebook, built here
  before the question was asked.
- **Always-on entries.** `always_on`, and any card whose place is where the party
  stands, is pinned ahead of the keyed ones.
- **A fact cap.** `touch()` dedupes and keeps the last `FACT_CAP = 8` facts.
- **Lingering.** A resolved card stays on the table `LINGER_TURNS = 3` turns so a beat
  can refer back to what just ended.
- **A ledger built mechanically from tells.** `touch_from_outcomes` lands the engine's
  own tells onto the cards they name, with no model call and nothing to hallucinate.
  That is exactly the tier-three mechanism proposed above, already running.

The comment above those constants cites the Stanford agents result for why the window
is small. This territory was researched already.

**Quests are insulated from history truncation, and this is now measured rather than
assumed.** Neither `rules/cards.py` nor `rules/schemes.py` reads the model's message
history at all. Cards live in the scene, reach the model inside the system message,
which Ollama preserves, and their scan window is fed from `c.transcript[-4:]`, which
is a different list from `c.history`. Scheme criteria read engine state and their own
tick counters. So everything that could be dropped today is conversation, never a
quest.

Three real interactions to respect when the policy is built:

1. **The ledger must never restate a card fact.** A card already holds it, and a
   second copy is the parallel store the second law forbids. The ledger covers only
   fiction that has no card, which is the same rule as promotion.
2. **Keep the card scan window off the prompt budget.** It is fed from the transcript
   today. If a squeezed prompt were ever allowed to shrink it, cards would silently
   stop triggering, and the failure would look like the world forgetting rather than
   like a budget being hit.
3. **The asymmetry becomes visible.** Today a quest card survives while the
   conversation that created it can be dropped without a word. That is not wrong, but
   it is currently invisible. With an explicit cut we can log it, and it becomes an
   argument for promoting more fiction onto cards rather than a mystery.

---

## Budget and cut order

The budget is stated in code and enforced before the call, so the server never has to
truncate anything. A proposed order, to be argued about with measurements rather than
opinions:

1. Instructions. Never cut.
2. The scene brief's core: where, who, what is live. Never cut.
3. The near window's most recent two or three turns.
4. The few-shot examples.
5. The rest of the near window.
6. The ledger.
7. The scene brief's optional sections, in a stated order.

Two notes on that order. The examples sit above most of the window because this
project has measured that demonstration volume beats instruction volume, and below
the last few turns because a model that has lost the thread writes the wrong scene
however well-formed it is. And the sampler already enforces the output schema as a
grammar, so the examples are buying quality, not validity.

Raising `num_ctx` is a lever but not a fix. The RULER leaderboard puts Llama 3.1 8B's
effective context at 32k against a claimed 128k, and Lost in the Middle says facts
buried in the middle get used least, so more room mostly buys more middle. It also
doubles the key-value cache, and the existing comment in `gm/client.py` already prices
16k at roughly 1.5 GB.

---

## How we would know it worked

- A test that assembles a two-hundred-turn campaign and asserts the built prompt
  fits the window with room to spare. Mechanical, fast, and it documents the defect:
  today the same test would prove the server is silently dropping our turns.
- A test that asserts no ledger entry contains a digit or a mechanical term, in the
  style of the existing three-laws ratchets.
- A test that a fact promoted to a tag or a card is present in the brief on turn one
  and turn two hundred alike.
- Live, on a real long session: does the narrator still name the right place after
  fifty turns. The project's honest instrument has always been reading real
  regenerated play, and no automatic metric replaces it here. Retrieval-quality
  metrics correlate with human judgement at about 0.55 in applied settings, which is
  not a number to steer by.

## The plan

Five stages, smallest first, each shippable on its own and each with the measurement
that says whether it worked. Stage one is most of the benefit.

### Stage 0. One number, one place

`num_ctx` is 16,384, written in `gm/client.py`. The packer needs the same number, and
two copies of a constant is the trap CLAUDE.md names. One module-level constant, read
by both.

The budget is **not** the window. Ollama's `num_ctx` has to hold the prompt *and* the
completion, and `num_predict` defaults to 700 with callers passing up to 900. So the
prompt budget is the window minus the largest completion minus a margin. Getting this
wrong is the failure already recorded in the client's own comment, where a 4,086-token
prompt left the model ten tokens of room and it died mid-sentence on every turn.

### Stage 1. Cut on our terms, and say so

There is exactly one choke point. `gm/prompts.py:933`, `messages.extend(history)`,
inside `call_one_messages`. Every other turn builder routes through it, and the NPC
turn already passes an empty list. One function fixes the whole turn path.

The function takes the assembled non-history parts, measures them, fills what is left
with the newest history first, and returns both the packed messages and what it
dropped. The caller logs the drop into `turn_log` the way it logs repairs today.

Tests, in the house style of naming the defect:

- Assemble a two-hundred-turn campaign and assert the built prompt fits the budget.
  Today that test fails, and its docstring records the measurement above: 44 turns out
  of combat before the server started silently dropping our oldest play.
- The newest player line and the system message are present at every history length.
- Dropping is oldest-first and never splits a user and assistant pair.

**Measurement that it worked:** the same two-hundred-turn assembly, plus a real long
session read end to end. If the narrator still names the right place at turn fifty,
the drift item on the playtest list is answered.

### Stage 2. The ledger, built from tells, no model call

`turn_log` already holds entries of kind `resolution` carrying every outcome as a
dict, and an outcome carries its tell. So the record of an evicted turn can be
assembled from data we already store, mechanically, with nothing invented.

- A new `ledger` field on `Campaign`, saved and loaded beside `history` and
  `transcript` in `to_dict` and `from_dict`.
- One entry per evicted stretch: the game time, the place id, the refs involved, and
  the tells, compressed. Written once at eviction and never rewritten, because
  re-summarising a summary is the approach that measured worst.
- Inserted as one block above the near window, inside its own budget.

Tests: no ledger entry contains a digit or a mechanical term, in the style of the
existing three-laws ratchets. An entry exists for exactly the turns that were
dropped. The ledger has a cap and honours it.

### Stage 3. One distillation call, for the part the engine does not own

Tells cover what the engine decided. They do not cover what a person said, promised
or threatened. That is one small model call at eviction, off the turn's critical
path, and it is the only model call in this whole plan.

Its output is prose about fiction and must never carry a number, which the stage-two
ratchet already enforces for anything entering the ledger.

### Stage 4. Promote, and watch the ledger shrink

Anything recurring in the ledger wants a structured home: a `knows.*` tag, a quest
objective, or a card fact through `cards.touch`. Promotion moves a fact into tier one,
where the brief regenerates it forever and the player can see it.

**Measurement:** ledger entries per ten turns, before and after. If it does not fall,
we are missing a card type, and that is the finding.

### Stage 5. Recall, only if stage 4 fails to hold it

Pull old entries back when relevant, keyed on place ids, actor refs and tags. Not
embeddings, for the reasons in `docs/retrieval-and-memory.md`. This stage stays
unbuilt until the ledger actually overflows its budget in real play.

### Not in this plan

- Raising `num_ctx`. It doubles the key-value cache, and the effective-context and
  lost-in-the-middle results say more room mostly buys more middle. Revisit only with
  a measurement.
- Trimming the few-shot examples. It is the largest single win available, 11,540
  chars out of a 25,132-char floor, but it is a quality question, not a memory one,
  and it belongs with `tools/narrator_audit.py` and its 196 of 200 baseline rather
  than here.
- `turn_log` itself is unbounded and saved to disk. It never reaches the model, so it
  is a save-file question, not a context one. Worth its own look later.

## Open questions

- Whether the out-of-combat examples are earning their 11,540 chars, which is the
  largest fixed item in the prompt and more than twice the brief. The narrator audit
  and its 196 of 200 baseline is the instrument that can answer it.
- Whether the near window should be counted in turns or in tokens during combat,
  where a round of six actors is many small beats rather than one large one.
- The token figures here are chars over four. Before the budget is written in code it
  should be checked once against a real count, which Ollama reports as
  `prompt_eval_count` on any call.
- Only Pangrella ships in `fixtures/`, so these numbers are one world. A world with a
  longer premise or more chronology would push the brief up, and the head section and
  what this place remembers are the two parts that would move.
