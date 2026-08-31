# Stage 6 — severed tells

The plan of record for stage 6 of `docs/compliance-plan.md`. Every number below was
measured against the real code and the twelve real campaigns, not estimated.

## Law 3, restated from the contract

> Every effect application or removal emits a **tell** — one prose-ready sentence of what
> the engine decided. The narrator is fed tells and nothing else about mechanics; prose
> stating a mechanic **no tell backs** is an outcome-claim and dies in the scrubber.

Three clauses. All three are broken, and — this is the finding that shapes the stage —
**they are broken as one thing.** The tell does not carry the death, so the narrator
cannot know it, so a repair reaches past the tell to recover it, and the scrubber cannot
tell reporting from invention because it has never been shown the tells either.

## What was measured

**The tell for a killing blow does not mention the death.** Driving real damage through
the engine at each 1e threshold:

| damage | result | the tell the narrator gets |
|---|---|---|
| to exactly 0 | `disabled` applied | `'the thug takes 6 slashing damage.'` |
| below 0 | `unconscious` + `dying` applied | `'the thug takes 9 slashing damage.'` |
| past −Con | `dead` applied | `'the thug takes 30 slashing damage.'` |

In every case the condition is present in `outcome.effects` and absent from
`outcome.tell`. The narrator is fed tells, so **the narrator is never told anyone died.**

**That missing tell is the direct cause of the reach-past.** `gm/agent.py:_deaths_from`
walks `getattr(o, "effects", None)`, matches `e.get("condition") == "dead"`, and then
computes `max(0, -int(a.hp) - int(a.ability_score("con")))` off the live actor to
recover how far past dead the blow went. It exists only because the tell never carried
it. `gm/judgement.py:2226` does the same walk to set the "heat" the witnesses feel.

**Both evade the law test twice over.** `test_the_narrator_is_fed_tells_and_never_effects`
inspects exactly one function (`narrate_outcome`) and matches the literal text
`.effects`; both sites are in other functions *and* spell it `getattr(o, "effects", …)`.
`test_an_outcome_with_literal_effects_carries_a_tell` only catches a literal
`effects=[{…}]` inside `rules/engine.py`. Law 3's ratchet is by far the weakest of the
three, which is why this debt survived five stages.

**The scrubber does not run on the prose the player reads.** `_groom` gates it behind a
`claims:` flag:

| site | path | flag |
|---|---|---|
| `agent.py:311` | call-one narration (not the default) | `claims=True` |
| `agent.py:397` | — | `claims=True` |
| `agent.py:913` | inside `narrate_turn` — **the live default** | `claims=False` |
| `agent.py:1001` | consequence prose — *"roughly half of what the player reads"* | `claims=False` |

`GM_INTENTS_FIRST` defaults to `1`, so `narrate_turn` is the live path.

**Measured over the twelve real campaigns: 2,510 GM lines the player actually read, 55
(2.2%) carry something `find_outcome_claims` would flag.** Of those, the large majority
are the **engine's own tells** — "Master Baek pays the stallholder 300 gp for 1x Elysian
Bronze", "Found: Tin ×1 Paid 5 gold pieces, leaving 25 gold pieces", the XP line — being
flagged by a detector written for model prose. Genuine model-authored claims are roughly
23 lines (0.9%): attacks landing and missing, items appearing in the satchel, a
perception result, a skill "deciding" something, a DC stated in prose.

Across 353 logged turns the repair log shows the claim repairs that *did* fire on the
older path (10 "states an escape", 4 "states an attack landing", 3 "states a perception
result"), plus `press_the_death` firing twice — "a kill left off the page" — which is the
model writing wounded-man prose about a corpse because nothing told it otherwise.

## The trap, and why `claims=False` was a reasonable decision

The comment at `agent.py:998` gives the reasoning verbatim: *"the engine has already
resolved the turn, so 'the blow lands' is reporting, not invention."* That is **correct**,
and it is why the naive fix — flipping the flag — is wrong. Two measured consequences:

- `find_outcome_claims(narration)` takes **one argument**. It is tell-blind: it cannot
  distinguish "the blow lands" when the engine landed it from "the blow lands" when it
  did not, so on post-resolution prose it would cut true reporting.
- Scrubbing at the transcript level is worse still: most of what it flags there is the
  engine's own output, so it would cut the engine's tells.

The contract already says the right rule and nobody implemented it: an outcome-claim is
prose stating a mechanic **no tell backs**. The scrubber has to be shown the tells.

## Substages

### 6a — the engine says what it decided
Death, dying, unconsciousness and disabled get tells, and so does every other application
and removal the census finds without one. The tell is a prose-ready sentence in the voice
the shipped tells already use. `apply_hp_state` returns condition keys today; what the
player is told has to travel with them.

Files: `rules/sheet.py`, `rules/engine.py`.

### 6b — the narrator's prompt is tells and nothing else
With 6a landed, `_deaths_from`'s reason for existing is gone: the death, and how far past
dead it went, arrive as a tell. The seam gets stated explicitly, because it is not
"nothing may read effects" — `cut_dead_men_walking` is *given* the dead by design, and
`judgement`'s heat is world state, not prose. The line is: **the narrator's prompt sees
tells; an engine-side repair may know engine facts.** Written down, and ratcheted.

Files: `gm/agent.py`, `gm/judgement.py`, `gm/prompts.py`.

### 6c — the scrubber learns what the tells said
`find_outcome_claims` gains the tells, so a claim they back is reporting and a claim they
do not is invention. Only then does the live path turn it on. Verified against the 23
real model-authored claims already in the transcripts, and against the engine's own lines,
which must survive untouched.

Files: `rules/intents.py`, `gm/agent.py`.

### 6d — tells carry no number the player has not earned
The leak census: hidden roll totals, DCs, an enemy's AC. `Outcome.player_visible` already
strips hidden *rolls*; it does not touch the *tell*, so anything a tell embeds is through.

### 6e — the ratchets
Both law-3 tests widen: every function that builds the narrator's prompt, `getattr` spelt
as well as attribute access, and every `Outcome` with effects however they are built —
not just literals in one file.

## Known already, to be folded in

Two defects surfaced while measuring and are not law-3 debt of their own:

- **A tell shipped with broken grammar**: *"You strips the watchman waving traffic
  through: shortsword, club, chain shirt, 1 sp…"* — in a real campaign the player read.
- **`tick_effects` returns bare names** (`['Shaken']`), not prose-ready sentences, so
  expiry tells are fragments the narrator must rebuild.

Also carried from stage 5's open list, since both are tell-and-refusal shaped: `nauseated`
sits in the same buried-502 class as `cast`, and a clockless hold out of combat has no
route out. Those belong to stage 7, not here, but 6a's tells are a prerequisite for
saying either of them well.
