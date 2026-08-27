# States, Effects and Tells

The design this app has been converging on since the first playtest, researched against
the one production system that finished the same thought — Unreal's Gameplay Ability
System — and named for what it is here, because we built most of it ourselves before we
knew its name: **a single state vocabulary, a single applicator for every number that
changes, and a presentation layer that may only dress what the engine recorded.**

Not called GAS. GAS is where we checked our working. The convergence is the finding:
`effectspec` is proto-GameplayEffects, the itemised dice popup is the aggregator with
every source named, "model proposes / engine disposes" is server authority, and the
tell/claims machinery is a cue layer enforced harder than Epic's — because our
presentation layer is a language model that will invent a belt.

## The three laws

1. **One vocabulary.** Every state an actor can be in is a hierarchical tag. Systems
   ask questions with prefixes ("anything under `state.down`?") and never match exact
   strings. New systems join play by speaking tags, not by editing each other.
2. **One applicator.** Every change to a number travels as an effect — a document with
   a duration (instant / rounds / until-dismissed), modifiers, granted tags, stacking
   policy, and a source. Remove the effect and its contribution evaporates; nothing is
   ever "added and hopefully subtracted".
3. **Severed tells.** Every effect application emits a tell. The narrator is fed tells
   and nothing else about mechanics; prose that states a mechanic no tell backs is an
   outcome-claim and dies in the scrubber. Presentation never leads mechanics.

## The stages

**Stage 1 — the vocabulary (this commit).** `rules/states.py` maps every condition to
its tags: `dead → state.down.dead + state.unable`, `stunned → state.unable.stunned`,
`blood armament → buff.stance.blood-armament`. Unknown keys self-tag under
`condition.<key>` so homebrew participates without registration. `Actor.has_state`
answers prefix queries; the first consumers are the questions that have already drifted
apart in play — lootability, the walking-dead casualty list, the corpse-attack checks —
each previously its own hand-rolled test of hp and string equality.

**Stage 2 — the effect engine.** One `ActiveEffect` record generalises conditions, temp
pools, coatings and rage bonuses: duration kinds, periodic ticks, stack policies,
granted tags, source-tracked modifiers through the existing modifier lists. Conditions
become effects whose granted tags are their vocabulary entry; the five separately
maintained mechanisms become one applicator and one ticker.

**Stage 3 — abilities as documents.** Activation requirements (tag queries), cost
(pool), action type, applied effects, granted tags, tell. Blood Bending's special cases
(the armament weapon-swap, rage's bonuses) re-expressed as data are the proof; the
classbuilder becomes the editor for the full grammar, and homebrew classes reach parity
without per-class engine code.

**Stage 4 — the aggregator's reward.** Base value vs current value per attribute, with
sourced modifier channels. Magic items become infinite effects granted by a worn slot —
the sheet's own admission ("a ring of protection here will not move your AC") closes.
Meta-attribute damage distribution formalises `_apply_damage`, and "50% physical
resistance while raging" — promised by Blood Bending's own text, currently
undeliverable — becomes a document.

## What was deliberately not taken from GAS

Prediction and replication (a third of GAS is netcode for a problem a single-authority
turn-based game does not have); multiplicative-stacking aggregation order (1e's typed
bonuses — dodge stacks, deflection does not — are the better rule for this game and
belong in stage 4's channels); cosmetic fire-and-forget cues (our narrator must be
*constrained* by tells, not merely informed).

## The bridge to the world state

The watcher owns minds, the engine owns bodies — and tags are the safe crossing:
social states (`attitude.hostile.to-pc`, `knows.pc-name`) may be granted by the
watcher through the same applicator and queried by mechanics (a hostile merchant
refuses the trade panel) without the watcher ever touching a number.
