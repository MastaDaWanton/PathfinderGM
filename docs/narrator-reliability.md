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

## The baseline

Measured 2026-08-25, 200 turns, this build, two scripts, two models. Local Ollama,
one RTX-class GPU, nothing else contending.

| model | script | clean | faults | mean turn | worst |
|---|---|---|---|---|---|
| llama3.1:8b | town | **50/50 (100%)** | — | 14.2s | 42s |
| llama3.1:8b | fight | 49/50 (98%) | 1 × `turn-failed` | 15.8s | 72s |
| qwen3-8b-heretic | town | 48/50 (96%) | 2 × `turn-failed` | 25.6s | 54s |
| qwen3-8b-heretic | fight | 49/50 (98%) | 1 × `turn-failed` | 20.5s | 44s |

**196 of 200 turns clean — 98%.**

The four faults are all the same kind, and it is the honest one: the model could not
produce a valid turn in seven attempts (five on the narrator, two on the fallback), and
the player is told so. Nothing crashed and nothing false reached the transcript.

What did *not* happen in 200 turns is the part worth stating plainly: **no invented
names, no invented companions, no third-person slips, no echoed examples, no outcome
claims, and no combat turn that proposed nothing.** Every failure mode this project has
fixed stayed fixed, including the one that cost a whole evening's combat loop the day
this was written.

### Read this before trusting the table

The first fight run reported 47/50 and three `combat-turn-did-nothing`. All three were an
attack that had suspended for the player's d20 — the intent existed and the engine was
waiting on a die, which is the system working. The harness recorded outcomes before
answering the roll and read the gap as the GM proposing nothing, *which is exactly the
failure it was written to detect*. Corrected, that run is 49/50.

A harness that can produce a false positive for the thing it measures is worth more
scepticism than the number it prints. Re-derive a fault before believing it.

### What 200 clean turns did not cover

The day after that table was measured, a player asked her character to look in a mirror
and got a man's chest back — "your pectoralis major muscles" — and, two sentences
earlier, a narrator who had walked into the scene: "Lyra stands beside me... every detail
of my image."

Neither is in the table because nothing was looking for either. Both matter more than the
percentage:

**The second person hides gender completely.** Every check that had ever been written
about who the player is worked on pronouns, and a paragraph addressed to "you" contains
none. The sheet's one relevant fact could not apply to the sentence that got it wrong.
The repair is in two halves — `prompts.scene_brief` now states in plain words what the
character *is*, and `narration.wrong_body` catches anatomy that belongs to another body —
and the first half is the one expected to do the work. The model knows what a woman looks
like. It had never been told this was one.

**A fault the harness cannot see is a fault that does not exist.** Two hundred turns of
"no third-person slips" was true and meant less than it sounded, because the scripts
never asked the narrator to describe the player's body and no check would have scored it
if they had. A clean number measures the checks, not the prose.

## Still open

- 50 turns per script per model is a baseline, not a release gate, and not enough to put
  a confidence interval on a 2% failure rate.
- Both scripts are short and loop. A long session drifts in ways ten repeated lines
  cannot show — which is the gap [Can LLM Agents Stick to the Script?][script] exists to
  measure.
- Nothing here scores whether the prose is any *good*. It scores whether it is true.

[script]: https://arxiv.org/html/2608.08160
[orch]: https://arxiv.org/html/2606.16014
[dnd]: https://arxiv.org/html/2510.18112v1
