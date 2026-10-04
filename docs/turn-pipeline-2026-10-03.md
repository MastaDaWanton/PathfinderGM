# The turn pipeline, 2026-10-03 (Lane D, items 17–22)

What was fixed from `docs/playtest-2026-10-03.md` items 17–22, the prior art each fix took
or refused, and what the owner's two saves look like through the fixed code. The saves are
the owner's and stay out of the repository. The replay was a scratch script, not committed.
The tests are in `tests/test_turn_pipeline_2026_10_03.py`.

## Prior art

The primary sources were read for every claim here. Anything that could not be sourced is
said so at the end.

### Repetition in agent loops (item 17)

- **OpenHands `StuckDetector`** compares events by value, never by object. Only the events
  since the last user message count, and the thresholds are 3 to 4 repeats.
  ([source](https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-sdk/openhands/sdk/conversation/stuck_detector.py))
- **Toloka's tolokaforge abandoned matching on arguments alone.** It stopped legitimate
  edit-then-rerun loops, scoring 0.35–0.44 against a 0.61 baseline. The fix added a hash
  of the result, on the rule "same args + different result-bytes is progress"
  ([#1494](https://github.com/Toloka/tolokaforge/issues/1494),
  [PR #1509](https://github.com/Toloka/tolokaforge/pull/1509)).
  - **Taken.** A `say`'s words and addressee are now part of the turn's signature.
- **CrewAI** refuses a repeated tool call once.
  ([tool_usage.py](https://github.com/crewAIInc/crewAI/blob/main/lib/crewai/src/crewai/tools/tool_usage.py))
- **SWE-agent** bounds its requeries (`max_requeries=3`) and then salvages what it has.
  It does not retry forever.
  ([agents.py](https://github.com/SWE-agent/SWE-agent/blob/main/sweagent/agent/agents.py))
  - **Taken from both.** The repeat rule spends one retry a turn.
  - If the same *quiet* plan comes back (narration and speech only), it is accepted.
  - If the same *mechanical* plan comes back, the turn degrades at once. Rolling last
    turn's check again resolves something the player did not ask for.

### Ollama's errors and fallback models (item 18)

- **Ollama answers 404 when the model is not pulled.** `server/routes.go` says
  `model 'x' not found`, and the scheduler says `model "x" not found, try pulling it
  first`. An Ollama that is down gives no HTTP status at all, only a connection error.
  `/api/tags` lists the models available locally.
  ([routes.go](https://github.com/ollama/ollama/blob/main/server/routes.go),
  [api.md](https://github.com/ollama/ollama/blob/main/docs/api.md))
  - **Taken.** A 404 raises `client.ModelNotInstalled`, a subclass of `ModelUnavailable`
    that says "not installed".
- **LiteLLM treats the two failures differently.** It cools a deployment down on a 404
  but not on a connection error, and keeps that state in a cache.
  ([cooldown_handlers.py](https://github.com/BerriAI/litellm/blob/main/litellm/router_utils/cooldown_handlers.py))
  - **Taken.** `client.has_model` caches `/api/tags` for a minute.
  - The fallback is left off the schedule when Ollama does not have it, and that is
    logged once per process.
  - A hosted fallback is never second-guessed, because hosted providers must remain
    possible.

### Validate, then repair (item 19)

- **Instructor re-parses every attempt against the whole response model**, so every
  validator runs again. It raises when the attempts run out.
  ([retry.py](https://github.com/567-labs/instructor/blob/main/instructor/v2/core/retry.py))
- **Guardrails' sequential validators pass a `fix` on to later validators** and never
  show it to the earlier ones. That is exactly our defect.
  ([sequential_validator_service.py](https://github.com/guardrails-ai/guardrails/blob/main/guardrails/validator_service/sequential_validator_service.py))
  - **Taken.** Every polish candidate goes through the same page pass as a first draft:
    the schema cut, refs, stutter, a sentence cut off mid-word, and repeated beats.
  - Each candidate is then judged by the review **and** the registered `gm/checks`.
    Lane B's time-of-day check will therefore judge rewrites as well as drafts.
  - The page pass runs once more after every model repair in `_groom`.
- **Refused: Guardrails returns `None` when its re-asks run out, and Instructor raises.**
  A turn cannot ship nothing. When no candidate holds, the draft stands, which is the best
  earlier candidate.

### Rolling memory (item 22)

- **Wang et al. 2023** (§6.4) name "missing details" as the largest error in generated
  memories: a specific title generalised into a vague preference. "Handed something to
  someone" is that error.
  ([arXiv 2308.15022](https://arxiv.org/html/2308.15022))
- **KoboldAI pins its Memory at the very top, and MemGPT keeps a read-only system block**
  that is never evicted. Letta still never compacts the system prompt or its memory
  blocks.
  ([KoboldAI wiki](https://github-wiki-see.page/m/KoboldAI/KoboldAI-Client/wiki/Memory,-Author's-Note-and-World-Info),
  [arXiv 2310.08560](https://arxiv.org/html/2310.08560),
  [Letta compaction](https://docs.letta.com/v1-sdk/messages/compaction))
  - **Taken.** The opening frame is pinned beside the GM's note.
- **SillyTavern's summariser "may lose some important details or contain
  hallucinations"**, and its BART summariser was discontinued with Extras.
  ([docs](https://docs.sillytavern.app/extensions/summarize/))
  - **Kept as it was.** The ledger is built by the engine, not by a model.

### Could not source

- No measurement of hallucinated *numbers* in summaries specifically.
- No documented reason for Letta moving off MemGPT's recursive summary.
- Whether OpenRouter treats an unknown model id differently from an outage.
- Wang et al.'s error rates come from ChatGPT-class models, so they are not carried over
  to 8B local models.

## What each item does now, measured on the saves

17. **The repeat guard.**
    - The old signature called both lost turns' plans "the same as last turn". On
      market-talk that was 85.5 s and 75.8 s, and five refusals each.
    - The new one passes a `say` carrying the new words: 2 of 2 turns pass.
    - It still objects when last turn's plan is replayed verbatim: 2 of 2 caught.
    - **Also found:** a signature reloaded from a save never compared equal. Its params
      element is a JSON list, and a list is not a tuple. Both sides are now compared
      frozen.
18. **The missing backup narrator.**
    - A 404 now reads "… is not installed on the Ollama at …".
    - The missing fallback is never scheduled. Two turns × two wasted slots went this way
      on market-talk.
19. **Polish rewrites.**
    - The items save holds market-talk's turns as well, and records 14 polish replies.
      Of those, 1 ends mid-sentence under the tightened `ends_unfinished` and 0 did under
      the old rule. It is market-talk's "…sell you a'", trimmed now to
      `…how you want to play this."`.
    - The refs that reached the page are cut by the second page pass: 1 shipped beat, the
      same one in both saves.
    - "Midnight" is Lane B's check, which the rewrite is now judged by.
20. **"Eyes drop".**
    - `narration.felled` lifts the part of somebody that falls (eyes, gaze, voice, face,
      shoulders) before `_FELLED` reads the sentence.
    - The clerk's sentence no longer contradicts the engine.
    - "He drops to the floor" and "the clerk collapses, his gaze dropping to the floor"
      still do.
21. **Declared and not shown.**
    - Verb classes were added (drop: let * fall, release, set * down…; ground: floor,
      dirt…).
    - A deed done to a place keeps the thing in `target` as a cue.
    - Both refused repair passages show the drop, and so did the beat itself, which means
      the deeds call (7.6 s) is no longer made.
22. **The ledger.**
    - Places are written by name ("went from the market to the docks"), and an id it
      cannot name is read as its own slug.
    - Old entries are cleaned on the way into the prompt.
    - An unnamed ref prints as "someone", never "c".
    - Speech names the person in the engine-held conversation.
    - `at` names the spot as well as the settlement.
    - New lines cover `introduce`, `company`, a conversation ending and `journey`.
    - The turn log now says how many ledger lines carried what was cut.
    - The ledger does reach the prompt. On items, the last turn dropped 27 messages and
      carried 6 ledger lines.
    - **Also found:** the opening frame never reached the planner, on any turn of either
      save. `_from_a_user` drops a reply with no player line before it, so "Evening in
      Zhilvarnia… find a bed you can pay for" was "dropped the oldest 1 message(s)" from
      turn one. It is pinned now.

## Left for other lanes

- **Lane A** owns the wording of give, sell, buy and loot. The ledger now hands them
  `{item}` and names. "handed something to Kesst Vayr" for a take, and a `give` that
  moved nothing (count 0, item 8) still writes a line.
- **Lane C** owns the minted "say …" actor, which shows up in the ledger as
  `met say "just trying…"`.
