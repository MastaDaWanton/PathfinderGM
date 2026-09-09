# Semantic search, RAG and memory: do we need it?

Research record, 2026-09-08. Asked because the intuition that we would eventually
need retrieval has been there since early on, was deferred, and the app has since
grown large and grown the GAS-shaped state system. Four traditions were swept, then
an adversarial critic re-checked every load-bearing claim against primary sources.
The critic overturned the single most important finding, which is corrected below.

## The short answer

**No to retrieval over engine state. No to embedding the rules corpus. Yes to a
memory policy, which we do not have at all and which is a different problem wearing
the same coat.**

The thing that looks like a retrieval problem is a context-budget problem. We pass an
unbounded chat history to a 16k window and nothing anywhere trims, summarises or
prioritises it. That is worth fixing on its own terms, and almost none of the fix is
retrieval.

---

## What we measured about our own system

| Measurement | Value |
|---|---|
| Instructions in the system message | 8,527 chars |
| Few-shot examples, out of combat | 11,540 chars |
| Fixed floor before any scene or history | 20,067 chars, about 5,000 tokens |
| Context window requested from Ollama | 16,384 tokens |
| Room left for the scene brief and all history | about 11,000 tokens |
| History policy | none: `messages.extend(history)`, unbounded |
| Growth per turn | roughly 800 to 1,100 chars of player line plus beat |

There is no trimming, summarisation or windowing anywhere in the codebase. By
arithmetic, not measurement, the prompt reaches the window somewhere around forty
turns of play, before counting the scene brief, which is not measured here.

### What Ollama actually does when the prompt overflows

This mattered enough to read the source rather than trust a summary. From
`server/prompt.go` on main:

> "chatPrompt truncates any messages that exceed the context window of the model,
> making sure to always include 1) the latest message and 2) system messages"

The loop removes messages **from the front** until the prompt fits, and re-collects
every system-role message and prepends it back each time. Truncation is reported only
as a debug log and nothing reaches the API caller.

**Critic correction, and it reverses the sweep's headline claim.** The researchers
reported that Ollama keeps only about five tokens and evicts the system prompt first,
citing a real log line from a real issue. That behaviour lives one layer lower, on
the raw completion path and on single prompts that still overflow after packing. On
the chat endpoint with a system-role message, which is what we use, the system
message is the last thing dropped, not the first.

So for us: our instructions and scene brief survive. What silently disappears is the
oldest history, and before that the few-shot examples, which are user and assistant
messages sitting in front of the history. Losing the examples is not nothing, because
this project has measured that demonstration volume beats instruction volume. But the
catastrophic version of the story is not what our code hits, and we should not build
a workaround for a problem we do not have.

---

## What the shipped tools do

The roleplay tooling ecosystem has more user-hours on this exact question than the
research literature does, and its revealed preference is emphatic.

- **NovelAI Lorebook**: entries fire on keys, plain substring or regex, with a search
  range over recent story text, an insertion order, reserved tokens and a budget. No
  embedding feature appears anywhere in the documentation, after five years.
- **SillyTavern World Info**: the same shape, with primary and secondary keys, boolean
  key logic, scan depth, recursion and a hard token budget. Embedding-based insertion
  exists as one optional per-entry mode.
- **SillyTavern Vector Storage**: off by default, and the documentation says so in
  its own words, that it "does not guarantee a better chatting experience or improved
  memory of any sort". It also warns that vectorisation and prompt caching are
  mutually exclusive because re-ordering the prefix destroys cache hits.
- **KoboldAI**: flat keyword World Info, no vector option, no budget system.
- **AI Dungeon**: the one system using embeddings, and the split is the interesting
  part. Authored lore stays keyword-triggered as Story Cards. Embeddings are used
  only to rank the model's **own auto-generated summaries** of past play.
  **Critic correction:** its Memory Bank is not on by default; the documentation
  tells users to toggle it on.

**The pattern worth copying is that split.** Keyword or structured triggers for
authored reference material; retrieval, if at all, only over generated prose that
nobody indexed by hand.

Our own situation is better than theirs, because our authored material is not prose.
A bestiary entry, a spell, a feat is a record with a name and an id, and the engine
already reaches it by id. And our tag vocabulary is already the exact mechanism a
lorebook key is a crude version of. If we ever want world lore to surface on cue,
`state.wanted.<town>` and place ids are better keys than any embedding, and they are
already there.

---

## Where retrieval measurably hurts

- **Seven Failure Points of RAG** (arXiv:2401.05856) enumerates missing content,
  missed ranking, consolidation loss, failure to extract, wrong format, wrong
  specificity and incompleteness. Its own conclusion is that a retrieval system can
  only be validated in operation, not designed correct up front.
- **The Power of Noise** (arXiv:2401.14887) is the finding that matters most to us.
  A single **related but wrong** document placed beside the correct one dropped
  accuracy from 56.4% to 45.9%. Random, wholly irrelevant documents did not hurt and
  in some configurations helped. The dangerous case is the near miss, which is
  precisely what a stale description of a room the engine has since changed would be.
- **Astute RAG** (arXiv:2410.07176) measured retrieval making a frontier model worse
  on general questions, 47.1% down to 44.4% on one benchmark and 82.0% down to 76.7%
  on another, for Claude 3.5 Sonnet. **Critic correction:** those are aggregate
  numbers, not a subset restricted to questions the model already knew, which is how
  the sweep framed them.
- **Knowledge conflict has no default resolution.** Every paper on the subject
  proposes a bespoke detector because the base architecture has no rule for which
  source wins. Our second law already forbids the precondition by refusing parallel
  stores of the same fact. A vector index of how things used to be, running beside
  the engine's account of how they are, would reintroduce it by construction.

### The structured-data argument, with the critic's caveat

The TAG paper (arXiv:2408.14717) measured retrieval at 0% exact match against 55% for
a structured pipeline, and the sweep used it to argue that retrieval over game state
is near-useless. **Critic correction: that benchmark is built from queries requiring
counting, ranking, comparison and aggregation.** It is fair evidence that retrieval
cannot do arithmetic over records. It is not fair evidence against simple fact lookup,
and quoting the headline number as a general verdict would be a strawman.

The honest version of the argument does not need TAG. Our state is a dict. Asking
whether a creature is down is `has_state("state.down")`. Semantic search is not a
worse way to answer that; it is a different kind of thing entirely, and the answer it
returns would be a probability where we already hold a fact.

### The two closest academic projects went the other way

FIREBALL (arXiv:2305.01528) improved both automatic metrics and human judgement by
conditioning on **structured game state** and generating executable commands, not by
retrieving rules prose. CALYPSO is scoped to creative brainstorming and explicitly is
not a rules-adjudication system. Neither built rules retrieval, and I could not find
any published work that built retrieval over tabletop rules text and measured it.

---

## What the memory literature actually recommends

- **Generative Agents** (arXiv:2304.03442) score each memory by recency, importance
  and relevance, equally weighted. Recency decays at 0.99 per game hour. Importance
  is the model's own 1-to-10 rating at write time. Relevance is embedding similarity.
  Reflection fires when accumulated importance passes 150 and writes higher-level
  memories from the last hundred observations. **Critic correction:** the claim that
  ablating reflection hurt most is not supported; by their own scores, removing the
  memory component costs more.
- **MemGPT** (arXiv:2310.08560) pages between a fixed window and external storage,
  warns itself at about 70% of the window and folds evicted messages into a recursive
  summary. Its weakness is directly relevant: it depends on the model reliably
  emitting well-formed function calls, and the paper reports weaker models failing at
  exactly that. An 8B local model is that case.
- **On summarisation versus retrieval**, the one direct comparison found puts
  recursive summarisation last, at 35.3%, well behind periodic conversation summaries
  at 78.6% and full context at 94.4%. A rolling summary alone is the weakest of the
  known approaches, though far better than our current policy of keeping everything
  until the server quietly drops it.
- **Effective context.** RULER's methodology defines effective length as the longest
  input at which a model still beats a fixed baseline. Llama 3.1 8B is listed at 128k
  claimed and 32k effective. **Critic correction:** that row is on the maintained
  leaderboard, not in the original paper, which predates the model. Combined with
  Lost in the Middle's U-shaped curve, the practical reading is that facts buried in
  the middle of a long history are the ones the model will fail to use, and the
  oldest and most identity-defining facts are exactly what drifts into that middle.
- **Narrative consistency is hard even with perfect memory.** A recent benchmark
  (arXiv:2608.08160, verified to exist against arXiv metadata after the critic
  flagged the unusual identifier) reports the best model surviving only 42% of runs
  to twenty turns without a fact conflict, with 3.5% reaching a hundred turns clean.
  Its named cause is models reconstructing state from dialogue history rather than
  being handed authoritative state. That is an argument for our architecture, not for
  retrieval.

---

## What it would cost us if we did it anyway

- **Embeddings through Ollama cost zero new Python dependencies.** It is a POST to
  the local server we already talk to with stdlib urllib. `nomic-embed-text` is 274 MB
  on disk, 768 dimensions, and Ollama's CPU default allows three loaded models, so the
  narrator should not be evicted by an embedder a fraction of its size.
- **Doing it in process would be the end of the single-exe promise.** Bundling
  sentence-transformers means bundling torch, which has a documented history of
  PyInstaller failures including segmentation faults and dozens of metadata copies,
  and adds hundreds of megabytes at best.
- **No vector database is warranted at our scale.** Brute-force cosine over a numpy
  matrix handles a million vectors in tens of milliseconds. **Critic correction:** the
  sweep's cited 12 ms figure has no source; the critic benchmarked roughly 72 ms for
  a million by 384 on their own machine. Either way, at one to twenty thousand chunks
  we are two orders of magnitude below where a vector store earns its place. Note that
  sqlite-vec has open, unresolved Windows DLL-loading issues, which is disqualifying
  for a frozen exe.
- **Keyword search is a strong baseline for our vocabulary.** BEIR found BM25 robust
  and frequently better than dense retrievers out of domain. Our queries are proper
  nouns: spell names, creature names, place names, the worst case for zero-shot
  embeddings and the best case for exact matching. BM25 is about fifty lines and no
  dependency.
- **We cannot easily measure whether it helped.** RAGAS-style metrics correlate with
  human judgement at about 0.55 in applied settings, and we have no ground truth for
  "was this narration better". Our own instruments, mechanical defect detection and
  reading real regenerated sessions, remain the honest measurement.

---

## The verdict, in the order the work should happen

1. **Give the turn a memory policy.** This is the real finding and it needs no
   retrieval. A bounded history window, plus a rolling summary of what fell out of
   it, plus the facts the engine can regenerate for free every turn because it owns
   them. Today we rely on an inference server silently dropping our oldest turns.
2. **Keep the tells authoritative.** Anything a summary says about mechanics is a
   second store of a fact the engine already holds, and the second law forbids it.
   A summary should carry what happened and who it happened with, never a number.
3. **Do not embed the rules corpus.** Twenty-six megabytes of records with exact
   names, reached by id today. If a lookup is ever needed by name, exact match then
   BM25, in that order.
4. **Do not retrieve over engine state.** It is a dict.
5. **Reconsider retrieval only for our own generated transcript, and only after 1.**
   That is the one place the ecosystem's evidence supports it, it is the one corpus
   nobody indexed by hand, and by then we will know whether the memory policy left a
   defect worth the failure surface.
6. **If we do reach for it, use tags as keys before embeddings as vectors.** We
   already have a hierarchical tag vocabulary and stable ids. That is the lorebook
   the whole roleplay ecosystem converged on, and we built its key mechanism years
   before asking this question.

---

## What could not be sourced

- Any published work building and evaluating retrieval over Pathfinder or D&D rules
  text as a rules-question system. The nearest projects deliberately did something
  else.
- A published CPU latency figure for `nomic-embed-text` through Ollama. Worth
  measuring on the machine rather than citing.
- Whether NovelAI ever tried and removed a semantic lorebook. The current docs simply
  have no such feature; that is not the same as never having tried.
- The maintainers' stated reason for deprecating SillyTavern's older Smart Context
  memory feature. The deprecation is confirmed; the reasoning is not.
- Any benchmark comparing one-record-per-chunk against sliding-window chunking for
  structured records. Treat one record per chunk as sound judgement, not measurement.
- The size of our own scene brief, which is arithmetic in the table above rather than
  a measurement. Worth measuring before designing a window.

## Sources

arXiv:2401.05856 (seven failure points); arXiv:2401.14887 (Power of Noise);
arXiv:2410.07176 (Astute RAG); arXiv:2408.14717 (TAG); arXiv:2304.03442 (Generative
Agents); arXiv:2310.08560 (MemGPT); arXiv:2501.13956 (Zep, for the summarisation
comparison table); arXiv:2404.06654 and the RULER leaderboard; arXiv:2307.03172
(Lost in the Middle); arXiv:2608.08160 (narrative consistency benchmark);
arXiv:2305.01528 (FIREBALL); arXiv:2308.07540 (CALYPSO); arXiv:2104.08663 (BEIR);
Ollama `server/prompt.go` and the API documentation; docs.novelai.net lorebook;
docs.sillytavern.app world info, data bank, chat vectorization and summarize;
help.aidungeon.com memory system; KoboldAI memory and world info wiki.
