# Keeping the narrator in check

The product claim this has to support is "the GM basically never gets it wrong". That is
not a claim anybody can make from memory of a few sessions, so this file records three
things: what the field already knows about this failure, what this app does about it, and
how the rate is measured.

## What the failure actually is

It is the central known problem of LLM game masters, and it has a measured rate.

* **Fact conflicts are the most frequent failure mode — 40–68% of interactions** under
  benchmark conditions ([Can LLM Agents Stick to the Script?][script]).
* The diagnosis is architectural: *in essentially every deployed or studied system, the
  narrative voice asserts world state in free prose rather than reading and writing a
  persistent, validated representation* ([Orchestrated Reality][orch]).
* The bias has a direction. Models **rewrite world state to satisfy player expectations**,
  without justification ([Does Reasoning Help LLM Agents Play D&D?][dnd]).

Both halves of that describe things measured in this repo. The stranger in Zhilvarnia
invented a smith called Glimble and the suggestion chips offered to visit him one turn
later; the killing blow in a tavern credited "your companion", who did not exist.

## What this app does

The load-bearing decision is one the literature says almost nobody makes: **the engine
owns the world state and the GM only proposes intents.** Nothing the model says is true
until `rules/intents.py` has validated it and `rules/engine.py` has resolved it. That is
the "canonical world object owned by a singleton orchestrator" design [Orchestrated
Reality][orch] argues for, and it is why the failures here are *narration* bugs rather
than corrupted saves.

On top of that, in the order they run:

| Layer | Where | What it stops |
|---|---|---|
| **Grammar-constrained decoding** | `gm/prompts.turn_schema`, `gm/client.chat(schema=)` | A reply of the wrong shape is never *generated*. Ollama passes `format` to the sampler as a grammar. |
| **Declaration detection** | `gm/judgement.py` | The player said it and the GM ignored it: travel, a fight, an attack, survival, goods. |
| **Prose review** | `gm/narration.review` | Invented names, invented companions, the PC in third person, echoed examples, outcome claims. |
| **Targeted repair** | `gm/agent.polish` | One narrow rewrite of what was found, never a general "do better". |

The schema is built **per turn from the situation**, which is the part that matters. A
static schema can only say "intents is a list". One built from the scene can say: it is
this character's turn in a fight, so the list may not be empty, `narrate_only` is not one
of the choices, and the actor and target enums are this scene's actual cast. The failure
that cost a whole evening's combat loop — narrating a punch and proposing nothing — stops
being something to detect and repair and becomes something the sampler cannot emit.

**The standing rule this all serves** is in CLAUDE.md and was earned the hard way: *detect
mechanically, repair with a targeted call.* Every fix that relied on instructing the model
to behave differently has failed and kept failing. The prompt has told the GM to use the
`travel` op, and to name only people who exist, for months. It does neither reliably.

## How the rate is measured

    python tools/narrator_audit.py --turns 50 --script town
    python tools/narrator_audit.py --turns 50 --script fight --model llama3.1:8b

It drives the real HTTP loop — same endpoints as the browser, same agent, same model —
through a fixed script, answers its own dice, and scores every reply with the app's own
`narration.review` plus three faults review cannot see because they are about the engine:

* `combat-turn-did-nothing` — a fight turn that proposed no action;
* `intent-rejected` — the engine refused what the GM proposed;
* `needed-a-retry` — the turn took more than one model call to survive.

Two scripts because the failures differ: ordinary play is where names get invented, and a
fight is where the engine stops being told anything.

It is not a pytest on purpose. It needs a live Ollama and runs for minutes, and a test
that sometimes needs a GPU is a test people learn to skip.

### What it has already caught

On its first outing, at six and eight turns: a combat turn that resolved to nothing
because the foe was down and the encounter had not closed, and a crash in the *failure*
path itself — `schedule` holds four-tuples and the raise unpacked it as a pair, so
`ValueError` replaced the honest "five attempts, here is what each got wrong" message with
a 500.

## Still open

The numbers below are the baseline to beat, not a pass mark. The honest gap is that no
run yet is long enough to put a confidence interval on: 50 turns per script per model is
a starting point, not a release gate.

[script]: https://arxiv.org/html/2608.08160
[orch]: https://arxiv.org/html/2606.16014
[dnd]: https://arxiv.org/html/2510.18112v1
