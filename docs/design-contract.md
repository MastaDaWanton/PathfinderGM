---
name: pathfinder-gm-design-contract
description: >
  How to think and write code for the Pathfinder GM project (H:\coding\PathfinderGM)
  and its companion World Bible. Load whenever work touches that project — actor
  state, conditions, effects, abilities, dice, magic items, narration, class
  documents, the GM agent — or whenever a design question is weighed against
  Unreal's Gameplay Ability System, game state machines, buff/debuff systems, or
  "how should this mechanic be modelled." Also load for design conversations about
  the project even when no code is open.
---

# The Pathfinder GM design contract

One person plays a Pathfinder 1e campaign inside a generated world. A local model
narrates; a rules engine owns every number. The whole architecture is one sentence:
**the model proposes, the engine disposes** — and everything below is that sentence
applied to state, effects, and prose.

## The three laws

Everything that changes a number, grants a state, or reaches the narrator obeys:

1. **One vocabulary.** Every state an actor can be in is a hierarchical tag
   (`state.down.dead`, `buff.stance.blood-rage`). Systems ask prefix questions —
   `has_state("state.down")` — and never match condition strings. New systems join
   play by speaking tags, not by editing each other. Unknown keys self-tag so
   homebrew participates without registration.
2. **One applicator.** Every change to a number travels as an effect — a document
   with a duration (instant / rounds / until-dismissed), modifiers, granted tags,
   stacking policy, and a source. Remove the effect and its contribution
   evaporates; nothing is ever "added and hopefully subtracted." One store, one
   ticker, one modifier funnel. A new mechanism is a new *kind* of effect, never a
   new field, list, or expiry loop.
3. **Severed tells.** Every effect application or removal emits a tell — one
   prose-ready sentence of what the engine decided. The narrator is fed tells and
   nothing else about mechanics; prose stating a mechanic no tell backs is an
   outcome-claim and dies in the scrubber. Presentation never leads mechanics, and
   no model ever authors a number: models propose documents, validators refuse bad
   ones with the fix named in the message.

## The GAS Rosetta

The design converged with Unreal's Gameplay Ability System before knowing its
name; GAS is where the working gets checked, not where it came from. Translate:

| GAS concept | This project |
|---|---|
| GameplayTags | the tag vocabulary (`rules/states.py`) |
| GameplayEffect | `ActiveEffect` (`rules/activeeffect.py`) |
| GameplayAbility | class ability documents (`paths.<path>.grants`) |
| AbilitySystemComponent | `Actor.apply_effect` / `Actor.tick_effects` |
| Attribute aggregator | typed `Modifier` + `dice.stack` |
| GameplayCues | tells (`Outcome.tell`) |
| Server authority | model proposes, engine disposes |

**Deliberately refused from GAS — do not re-import:**
- Prediction and replication: netcode for a problem a single-authority turn-based
  game does not have.
- Additive-then-multiplicative aggregation: 1e's typed bonuses are the rule —
  same named type takes the best; dodge, circumstance and untyped stack;
  penalties always stack.
- Cosmetic fire-and-forget cues: this presentation layer is a language model that
  will invent a belt. Tells *constrain* the narrator; they do not decorate.

## How code is written here

- **Search for the prior art before designing, every time.** Movement, state
  tracking, stacking, refusals, scene transitions and grounding a narrator are all
  decades-solved in interactive fiction, MUDs, tabletop systems, engines and the
  research literature. First principles produce something plausible that then has
  to be retrofitted, and the retrofit costs more than the search would have.
  Measured: a room model designed here from scratch shipped as a free-text field,
  and a six-tradition sweep the next day named that exact shape as the one thing
  no tradition sanctions. Look hardest for what a tradition **tried and
  abandoned** — Fate shipped weighted zone borders and then deleted them, which
  settles a question faster than any argument for adding them. Cite primary
  sources, say when a claim could not be sourced, and have a second pass check the
  first.
- **Detect mechanically, repair with a targeted call.** Find defects with code (a
  regex, a set comparison, a count); ask a model to fix only what was found.
  Instructing a model to behave differently fails and keeps failing — this
  applies to the model writing the code as much as the one running the game.
- **Refuse gracefully, never spiral.** A refusal whose reason the player could
  not have known is a printable Outcome ("Nothing is rolled. …"), never a raised
  error — the intent schema may REQUIRE the op the player declared, and
  required-op meeting hard-refusal is a buried-four-times 502 class.
- **Validators name the fix, not the fault.** "No pool called 'fury'. Declare it
  under pools, or name one of: ki, rage" — every message tells the author what to
  type next.
- **Tests document the defect with the measurement named.** "Ten of ten
  paragraphs ended the same way." A test that only asserts behaviour gets deleted
  by the next person; one that records what went wrong survives.
- **Zero per-class engine code.** A class ability that needs an engine special
  case actually needs a field in the document grammar, validated and applied
  generically — and a grep-test pinning that the engine names no class ability.
- **Prose copies drift; make claims checkable or make them pointers.** Any prose
  restatement of a rule should either be validated by a test (checked-refs) or
  point at the one canonical copy.
- **Run the whole suite; verify in the running app; report honestly with the
  numbers.** Rebuild the packaged exe and prove it against a throwaway data dir
  before calling packaging work done. Never play in the user's real
  %LOCALAPPDATA%\PathfinderGM data.

## Worked judgment

- *Ongoing poison* → an `ActiveEffect` with `periodic`, never a new Actor field.
- *New fear variant* → a vocabulary entry under `state.fear.*` plus a condition
  row; consumers ask `has_state("state.fear")`, never the key.
- *"Narrator should mention the DR"* → no: the tell carries what landed; the
  narrator dresses the tell. A fact the narrator needs becomes part of a tell.
- *Player attacks out of combat* → the battle opens (initiative, sides, grid) and
  the swing defers to the player's own first combat turn; a whole fight must
  never resolve inside one narrated paragraph.
- *Mercy stroke on the dying* → not a fight being started; finishing words plus a
  downed body silence the fight-making repairs.

## In the repo, before finishing

Run `python -m pytest tests/test_three_laws.py` (then the whole suite). The law
tests enforce the checkable half of this contract; their docstrings name the
incident behind each rule. The project-side skill `states-effects-tells` carries
the current Shipped/Promised/Refused ledger — trust it over memory for what
exists today.
