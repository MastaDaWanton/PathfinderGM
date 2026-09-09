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

## The mind had no gate (2026-09-09)

Reported from the table: "I was able to break the game and use psychic powers to
manipulate the people and story in ways that should not be possible."

Reproduced in one intent, with no ability, no spell, and no document of any kind:

```
{"op": "condition", "actor": "pc", "because": "I bend his mind to my will",
 "params": {"condition": "helpful", "to": "c1"}}

merchant attitude before: indifferent
ACCEPTED — tell: "the merchant is helpful."
merchant attitude after:  helpful
```

The bridge above is the reason this mattered so much. An attitude exists **to be read**
— by the brief, so the narrator writes a merchant who likes you — so a mind changed for
free does not stop at one scene. It rewrites how the world treats you from then on, and
it does it through the one channel we deliberately built to be believed.

### Two holes, one either side of the model

**The engine had no gate on a mind.** Stage 8a refused the seven amount-ops without
provenance: a number needs a document behind it. Nobody asked the same question of a
mind, and `condition` is not an amount-op, so the sampler offers it to the model
directly. The fix is stage 8's own rule with a different noun — a `condition` that would
land an `attitude.*` tag, a `state.fear.*` tag, or anything in the mind-affecting or
sleep families is refused unless the engine stamped an `origin`. That stamp is only ever
written by `Engine.validate(raw, origin=...)`, which only a door that read a real
document calls. In GAS's words, which is how the table asked for it: **an ability that
was never granted cannot be activated.** Here the grant is the document and `origin` is
the record that one was read.

Two lines the gate deliberately does not cross:

- **Bodies are not gated.** Prone, grappled, blinded, stunned, nauseated and eleven
  others still need no document. `dazed`, `stunned`, `staggered` and `nauseated` can all
  be mind-affecting in 1e when a spell causes them and can equally be a blow to the
  head, so gating them would refuse ordinary violence for having a mental cousin.
  Measured: 25 of 25 body conditions pass, 21 of 21 mind conditions are caught.
- **Lifting one is never gated.** The same inversion `_op_condition` already carries a
  scar from — gate a removal and a charm can never be broken, exactly as gating the
  applicator once made 759 undead unkillable by blocking the condition that records
  their death.

**The declaration had no door.** `refuse_unknown_ability` catches "I use Blood Nova on
the merchant" because Blood Nova is a *name* it can look up. "I read his mind" has no
name in it, so nothing looked anything up, and the sentence reached the narrator as
ordinary prose — which wrote it as working. That shape needs no intent at all: no
mechanical claim is ever made, so nothing is there to refuse, and the story simply
bends. `refuse_unnamed_power` turns the declaration into the one it actually is, "I use
<a power>", and the engine's own door answers with the list of what the character really
has.

The line it draws is **what the declaration reaches, not how forceful it is**.
Persuading, threatening, lying, bribing, seducing and pleading are ordinary social play
and are untouched — they are skill checks, and `inject_checks` already routes them.
Speech is redacted first, because a character is entitled to *boast* about powers they
do not have. Measured on a labelled corpus: 32 of 32 psychic declarations caught, 40 of
40 ordinary lines spared.

### What the search said

The prior art splits cleanly, and the half the field reaches for first is the half this
project has already measured as failing. The LLM-GM literature grounds actions by
putting the character sheet in the prompt and asking the model to validate against it —
which is instructing a model to behave differently, and CLAUDE.md's first rule about
working with models is that this fails and keeps failing. The systems tradition enforces
it in code instead: a MUD's cast command looks the spell up on the character before it
dispatches anything.

Inform 7 supplied the framing that was missing. Commanding another character is not an
action the player resolves — it goes to a **persuasion rulebook**, which decides whether
the other party complies, and *its default is refusal*: an "instead" rule written for
another person is treated as a failure, and an "unsuccessful attempt by" rule narrates
it. That is exactly the right shape for reaching into a mind. It is adjudicated, by
something other than the person doing it, and the answer is no unless a rule says
otherwise.

### Found on the way, not looked for

`IMMUNITY_COVERS` spelled the mind-affecting family out four separate times — under
`mind-affecting`, `mind affecting`, `undead traits` and `construct traits` — and the
word "dominate" appeared in none of the four. Dominate person is a mind-affecting
compulsion in the Core Rulebook, so **759 shipped creatures with undead traits were
immune to charm and wide open to domination.** The list is written once now and spliced
into all four, which is CLAUDE.md's "grep for every copy of it" applied to the copy that
had been wrong since the table was written.

### Still open

An attitude can be moved by a spell, an ability, an item or a scheme, and it can no
longer be moved by assertion. It cannot yet be moved by **talking to somebody**: the
`check` op takes no target, and nothing converts a Diplomacy success into a step along
the track — `rules/effectspec.py` has said so since the spell import ("no check in the
app consults an attitude yet"). The refusal names Diplomacy, Intimidate and Bluff as the
ordinary route because those checks are real and do roll; what does not exist is the
rule row that turns one into an attitude step. That is the next piece of this, and it is
a feature rather than a fix.
