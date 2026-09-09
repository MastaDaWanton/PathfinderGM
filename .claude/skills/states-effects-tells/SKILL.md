---
name: states-effects-tells
description: >
  The design contract for everything that changes a number, grants a state, or
  reaches the narrator. Load before touching actor state, conditions, buffs,
  effects, abilities, stacking, magic items, tells, or narration — concretely:
  rules/sheet.py, rules/engine.py, rules/activeeffect.py, rules/states.py,
  rules/dice.py, class documents, gm/agent.py, gm/prompts.py. Also load when
  weighing a design against Unreal's Gameplay Ability System — we converged with
  GAS deliberately and diverged from it deliberately, and both lists are here.
---

# States, Effects and Tells — the working contract

Canonical design record: `docs/states-effects-tells.md`. The three laws are in
CLAUDE.md and enforced by `tests/test_three_laws.py` — **run that file after any
change in this territory; when it blocks you, its docstrings name the incident
that made the rule.** This skill carries what neither can: the GAS mapping, the
shipped/promised/refused ledger, and worked judgment.

## The GAS Rosetta

We built most of this before learning its Unreal name. When reading GAS material
for design input, translate:

| GAS | Here | Enforced / pinned by |
|---|---|---|
| GameplayTags | the tag vocabulary, `rules/states.py` | `Actor.has_state` prefix queries |
| GameplayEffect | `ActiveEffect` | `tests/test_active_effects.py` |
| GameplayAbility | `paths.<path>.grants` documents | `tests/test_ability_documents.py` |
| AbilitySystemComponent | `Actor.apply_effect` / `Actor.tick_effects` | `tests/test_three_laws.py` |
| Attribute aggregator | typed `Modifier` + `dice.stack` | `tests/test_aggregator.py` |
| GameplayCues | tells (`Outcome.tell`) | the claims scrubber, `rules/intents.py` |
| Server authority | model proposes, engine disposes | validators in `gm/judgement.py` |

## Refused from GAS — do not re-import

- **Prediction and replication.** A third of GAS is netcode for a problem a
  single-authority turn-based game does not have.
- **Additive-then-multiplicative aggregation.** 1e's typed bonuses are the rule:
  same named type takes the best; dodge, circumstance and untyped stack;
  penalties always stack. `dice.stack` is the implementation.
- **Cosmetic fire-and-forget cues.** Our presentation layer is a language model
  that will invent a belt. Tells *constrain* the narrator; they do not decorate.

## Shipped / Promised / Refused ledger

**Shipped** (safe to build on): tag vocabulary with homebrew self-tagging; the
one effect store with views (`conditions`/`buffs`/`temp_pools`/`coating`);
ability documents for the battle blood path (requirements, cost, drain, tiered
modifiers, temp HP per HD, granted weapon, tells); typed stacking channels; worn
magic items from slots via `rules/magicitem.py:worn_specs`; percent resistance
in `take_damage`; the battle gate (first violence opens the fight, never
resolves it); finishing-blow detection; the three state questions with one owner
each — `Actor.can_act` (per op, via `states.BLOCKS`), `Actor.is_down`,
`Actor.is_helpless` — and the `recovery.*` families with `Actor.clear_states`;
the `attitude.*` track (hostile → helpful) read by `states.attitude_of` and stated
in the brief; **one spatial coordinate** — `Actor.at` is a place id from
`rules/places.py`, `Scene.people` is the store, `Scene.actors` the derived
read-only view of who is here, `Scene.move`/`Scene.remove` the only doors,
`scene.biome` a parse of the id, refs minted once via `bestiary.next_ref` and
never reused (docs/places-8b-plan.md; ratchet in
`tests/test_one_spatial_authority.py`); **provenance** — `Intent.origin` /
`origin_name` stamped only by `Engine.validate(raw, origin=...)` (`item:<id>`,
`spell:<id>`, `ability:<path>/<key>`, `rule:<id>`, `creature:<template>`,
`author:cheat`, `author:test`), a model-written `origin` refused at parse, the
seven amount-ops plus save-branch dice, guard amounts and pool gains refused
without a stamp and absent from the sampler enum, `ActiveEffect.origin` beside
`source`, effect records and tells naming the document; **feats as documents**
— `content/feats/mechanics/*.json` in the `grants` vocabulary plus `scope`,
`when`, `choice`, `attack_ability`, `budget`, `tags`, `not_yet`, validated on load
by `classbuilder.validate_feat_documents`, read live by `Actor._feat_mods` inside
`_buff_mods(kind, target, ctx)` (never stored), `has_state` reading
`standing_tags()`; **hazards** — `content/rules/hazards.json` rows with a bounded
slot, the `hazard` op (docs/stage-8-plan.md; ratchets in
`tests/test_stage8_provenance.py`, `tests/test_feat_documents.py`); **the mind gate**
— stage 8's rule asked of a mind instead of a number: a `condition` that would land an
`attitude.*` tag, a `state.fear.*` tag, or anything in the mind-affecting or sleep
families is refused without an `origin`, so charm person still charms and "I decide he
likes me" does not (`states.touches_the_mind`, the gate in `Engine._check_legality`);
bodies are NOT gated (25 of 25 pass) and lifting one is never gated; plain-language
psychic declarations — "I read his mind", which has no name for
`refuse_unknown_ability` to look up — are routed to the ability door by
`judgement.refuse_unnamed_power`, which leaves persuading, threatening, lying and
bribing alone (32/32 caught, 40/40 spared; docs/states-effects-tells.md "The mind had
no gate"; ratchet in `tests/test_psychic_powers.py`); **the three
doors places come in by** — a settlement's own words imply spots (`places.IMPLIED`),
the player founds a place with an owner (`found`; the owner holds `holds.place.<slug>`
as an `ActiveEffect`, source `place:<id>`), ground gone into is seeded off its parent
(`venture`); all of it in `Scene.founded`, read back through the one derivation
`places.for_scene` (docs/place-doors.md; `tests/test_place_doors.py`).

**Promised, not built** (do not write code that assumes these exist):
- Watcher-granted social tags (`attitude.*`, `knows.*`) through the applicator —
  the bridge in the doc's last section. No code grants them today.
- `ActiveEffect.periodic` executors beyond `spend_pool` — periodic damage/heal
  is schema-ready with no consumer.
- `grants` documents for blood spike, coagulator and blood commander paths.
- Blood Burst's computed save DC; Rupture Self's blood-pool targeting (see the
  path's `needs` map).
- A proper 1e coup de grâce (full-round, auto-crit, Fortitude save) — today a
  mercy stroke resolves as an ordinary attack on the body.

**Refused** (asked and answered — do not reopen without the user): the three GAS
items above; models authoring numbers anywhere (validators refuse documents with
the fix named, in the classbuilder's message style); presentation leading
mechanics; a stored `ActiveEffect` per feat (Foundry v11 abandoned the copied
effect with an origin pointer — the feat list is the store); `origin` in the
model-writable params (parse pops engine-owned keys silently, so it could not
join that set); a validate-time source check as the primary defence (the sampler
enum is; stage 7 measured what a rejection teaches); GM fiat with no rule row.

**Still open after stage 8** (do not read a passing probe as proof): **no route from a
social check to an attitude** — the mind gate closed assertion, and spells, abilities,
items and schemes still move the track, but `check` takes no target param and no rule
row turns a Diplomacy or Intimidate success into a step, so talking somebody round is
narrated and never recorded (`rules/effectspec.py` has said "no check in the app
consults an attitude yet" since the spell import; the gate's refusal names those checks
as the ordinary route because they do roll); the
`_op_use_ability` instant-effects loop records no per-number origin (the outcome
record carries `ability:<path>/<key>`); wards stamp `ward:<name>`, not a spell id;
Point-Blank Shot's `when.range_ft` waits on the attack op passing range into the
roll context (its term is dropped, per the rule); the wielded-weapon spec channel
(masterwork, enchanted) has no reader — stage 9 — and worse, a weapon record put in
the `hands` slot through the sheet editor lends its enhancement to EVERY weapon
(`_standing_mods` has no weapon scope: a live door, measured by the verifiers);
bestiary special attacks have no locator, so a creature's fight turn keeps
`damage`/`ability_damage` stamped `creature:<template>` (three live thug turns chose
`attack`; the door is open, unused, and logged as `kind: npc-turn` now); feat actions
(Cleave, Vital Strike) have no `find_ability` branch; no level-up feat writer exists;
the claims scrubber let prose describe a struck target after a `cast` that never
resolved (measured once, before the actor fill); "I set off the trap" came back as
`hazard rule=acid` — a cited rule, sanctioned, not the narration the plan predicted.

## Before designing anything: search for how it was already solved

Standing instruction, every time, not only when a problem feels hard. Movement,
state tracking, stacking, refusals, scene transitions and narrator grounding are
decades-solved in interactive fiction, MUDs, tabletop systems, game engines and
the research literature. First principles produce something plausible that has to
be retrofitted later, and the retrofit costs more than the search.

Measured 2026-09-01: a room model designed here shipped as a free-text
`Scene.spot`, and a six-tradition sweep the next day named that exact shape as
the one thing no tradition sanctions — it also supplied the framing the design had
missed (four spatial authorities, none derived) and four ideas worth refusing with
reasons. Look hardest for what a tradition **tried and abandoned**; cite primary
sources; have a second pass check the first, which in that sweep caught two
overclaims in the researchers' own findings.

## Worked judgment

- *"Add an ongoing poison"* → an `ActiveEffect` with `periodic` (build the
  executor first — see Promised), never a new field on Actor. Its application
  and expiry each emit a tell.
- *"Add a new fear condition"* → a `TAGS` entry under `state.fear.*` in
  `rules/states.py` plus a `CONDITIONS` row; never a boolean, and no consumer
  may match the new key as a string — they ask `has_state("state.fear")`. If it
  ends on a night's sleep say so with `recovery.rest`, and if it stops actions
  say *which* in `states.BLOCKS`: a boolean answers with one bit and 1e's
  incapacities are not all total.
- *"Can this creature act?"* → three different questions, and conflating any two
  has cost a bug each. `can_act(op)` is may-I-act-now; `is_down` is
  out-of-the-fight (a stunned enemy is not, and reading it off can-act ended
  encounters around them); `is_helpless` is 1e's "immobilized, unconscious, or
  otherwise incapacitated", the maneuver clause, and is narrower than both.
- *"Everything X cures should be one sweep"* → a `recovery.*` tag, never a
  `state.*` family. `state.unable` contains `dead`, so a night's sleep sweeping
  it raises corpses; `state.held` contains `paralyzed`; `state.senses` contains
  `blinded`. Removal by family is the single most dangerous edit in this file.
- *"The narrator should mention the DR that soaked the hit"* → no: the *tell*
  carries what landed (`_damage_note` names the soak), and the narrator dresses
  the tell. If the narrator needs a fact, the fact becomes part of a tell.
- *"This class ability needs a special case in the engine"* → it does not; it
  needs a field in the `grants` grammar, validated by the classbuilder, applied
  generically. The armament weapon-swap is the worked example, and a grep test
  pins that the engine names no class ability.

<!-- checked-refs
docs/states-effects-tells.md
tests/test_three_laws.py
tests/test_active_effects.py
tests/test_ability_documents.py
tests/test_aggregator.py
rules/states.py:tags_for
rules/states.py:matches
rules/states.py:stops
rules/states.py:BLOCKS
rules/sheet.py:Actor.can_act
rules/sheet.py:Actor.is_down
rules/sheet.py:Actor.is_helpless
rules/sheet.py:Actor.clear_states
rules/activeeffect.py:ActiveEffect
rules/sheet.py:Actor.apply_effect
rules/sheet.py:Actor.tick_effects
rules/sheet.py:Actor.has_state
rules/dice.py:stack
rules/dice.py:Modifier
rules/magicitem.py:worn_specs
rules/leveling.py:ability_doc
rules/leveling.py:granted_weapons
rules/engine.py:Engine._apply_ability_document
rules/engine.py:Engine._ability_refusal
rules/engine.py:_damage_note
rules/intents.py:cut_outcome_claims
gm/judgement.py:is_finishing_blow
content/classes/blood-bending.json
-->
